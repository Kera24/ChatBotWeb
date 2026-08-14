"""CLI: Retrieval & Answer Pipeline V3 experiment (docs/future/RetrievalOptimisation.md),
Part 13/16 variant F ("V3 + caching") - measures the retrieval cache
(app.services.retrieval_cache) hit rate and latency impact directly, by
replaying the SAME real question set through app.services.retrieval_v3.assemble_v3_retrieval_context
TWICE (simulating repeat traffic - a single evaluation pass over N distinct
questions cannot exercise a cache's value proposition at all, which is why
this is a separate script from app.operations.eval_v3_ablation rather than
another evaluation-framework variant).

    python -m app.operations.eval_v3_cache_benchmark [--corpus golden|chunking|both] [--format text|json]

Requires real embeddings (EVAL_EMBEDDING_PROVIDER=ollama/EVAL_EMBEDDING_MODEL) -
fails loud, never silently substitutes mock.
"""

from __future__ import annotations

import argparse
import json
import os
import tempfile
import time
from dataclasses import asdict, dataclass
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.config import settings
from app.db.base import Base
from app.db import models  # noqa: F401 - import registers every model with Base.metadata
from app.db.models import Membership, Organisation, User, Workspace
from app.evaluation.embedding_cache import CachingEmbeddingProvider
from app.evaluation.embedding_config import build_real_eval_embedding_provider, load_eval_embedding_config_from_env, recommended_min_similarity_score
from app.evaluation.fixtures.loader import load_chunking_fixture_definition, seed_golden_dataset
from app.repositories import evaluation_repository
from app.services.chunking_strategies import ChunkingConfig, build_chunking_strategy
from app.services.embeddings import EmbeddingProviderError
from app.services.reranking import NO_RERANKER_PROVIDER, build_reranker
from app.services.retrieval_cache import InMemoryRetrievalCacheStore, RetrievalCacheKeyParts, knowledge_revision_for_scope
from app.services.retrieval_v3 import assemble_v3_retrieval_context


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="V3 Part 16 variant F - retrieval cache hit-rate/latency benchmark.")
    parser.add_argument("--corpus", default="both", choices=["golden", "chunking", "both"])
    parser.add_argument("--format", default="text", choices=["text", "json"])
    parser.add_argument("--keep-db", action="store_true")
    return parser.parse_args(argv)


@dataclass
class CacheBenchmarkResult:
    corpus: str
    queries: int
    cold_pass_mean_latency_ms: float
    warm_pass_mean_latency_ms: float
    cache_hit_count: int
    cache_miss_count: int
    hit_rate: float
    speedup_factor: float | None


def _run_corpus(*, corpus: str, keep_db: bool) -> CacheBenchmarkResult:
    try:
        embedding_provider = build_real_eval_embedding_provider()
    except EmbeddingProviderError as exc:
        raise SystemExit(f"Cannot run the cache benchmark: {exc}")
    recommended = recommended_min_similarity_score(load_eval_embedding_config_from_env())
    min_similarity_score = recommended if recommended is not None else settings.RETRIEVAL_MIN_SIMILARITY_SCORE

    temp_db_path = Path(tempfile.gettempdir()) / f"conversa-v3-cache-benchmark-{corpus}-{os.getpid()}.db"
    database_url = f"sqlite:///{temp_db_path}"
    engine = create_engine(database_url, connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine)

    cached_embedding_provider = CachingEmbeddingProvider(embedding_provider)
    no_reranker = build_reranker(provider_name=NO_RERANKER_PROVIDER)
    structure_aware_strategy = build_chunking_strategy("structure_aware", embedding_provider=None)
    if corpus == "chunking":
        fixture = load_chunking_fixture_definition()
        chunking_config = ChunkingConfig(chunk_size_words=120, chunk_overlap_words=25, min_chunk_size_words=30, max_chunk_size_words=200, source_type="txt")
    else:
        fixture = None
        chunking_config = ChunkingConfig(chunk_size_words=300, chunk_overlap_words=50, source_type="txt")

    try:
        with session_factory() as db:
            organisation = Organisation(name="V3 Cache Benchmark", slug=f"v3-cache-benchmark-{corpus}-{os.getpid()}", status="active", plan_key="starter")
            workspace = Workspace(organisation=organisation, name="Workspace", slug="workspace", status="active", default_language="en")
            user = User(email="v3-cache-benchmark@example.test", full_name="Benchmark")
            membership = Membership(organisation=organisation, user=user, role="org_owner", status="active")
            db.add_all([organisation, workspace, user, membership])
            db.commit()

            loaded = seed_golden_dataset(
                db, organisation=organisation, workspace=workspace, embedding_provider=cached_embedding_provider, actor_user_id=user.id,
                fixture=fixture, chunking_strategy=structure_aware_strategy, chunking_config=chunking_config,
            )
            questions = [c.question for c in evaluation_repository.list_cases_for_dataset(db, dataset_id=loaded.dataset.id)][:30]

            revision = knowledge_revision_for_scope(db, organisation_id=organisation.id, workspace_id=workspace.id, document_ids=None)
            cache_store = InMemoryRetrievalCacheStore()

            def run_pass() -> list[float]:
                latencies = []
                for question in questions:
                    key_parts = RetrievalCacheKeyParts(
                        query=question, organisation_id=organisation.id, workspace_id=workspace.id, assistant_id=loaded.widget_id,
                        knowledge_revision=revision, embedding_provider=cached_embedding_provider.provider_name,
                        embedding_model=cached_embedding_provider.model_name, retrieval_strategy_version="v3",
                    )
                    started = time.perf_counter()
                    assemble_v3_retrieval_context(
                        db, organisation_id=organisation.id, workspace_id=workspace.id, query=question,
                        provider=cached_embedding_provider, document_ids=None,
                        dense_pool_size=settings.RETRIEVAL_DENSE_CANDIDATE_POOL_SIZE, lexical_pool_size=settings.RETRIEVAL_LEXICAL_CANDIDATE_POOL_SIZE,
                        rrf_k=settings.RETRIEVAL_RRF_K, fused_pool_size=settings.RETRIEVAL_HYBRID_FINAL_TOP_K,
                        reranker=no_reranker, reranker_top_k=settings.RETRIEVAL_MAX_CONTEXT_CHUNKS, reranker_fail_loud=False,
                        max_context_chunks=settings.RETRIEVAL_MAX_CONTEXT_CHUNKS, max_context_chars=settings.RETRIEVAL_MAX_CONTEXT_CHARS,
                        cache_store=cache_store, cache_key_parts=key_parts, cache_ttl_seconds=300,
                    )
                    latencies.append((time.perf_counter() - started) * 1000)
                return latencies

            cold_latencies = run_pass()  # all misses - populates the cache
            warm_latencies = run_pass()  # should be all hits

            stats = cache_store.stats()
            cold_mean = sum(cold_latencies) / len(cold_latencies) if cold_latencies else 0.0
            warm_mean = sum(warm_latencies) / len(warm_latencies) if warm_latencies else 0.0
    finally:
        engine.dispose()
        if temp_db_path.exists() and not keep_db:
            temp_db_path.unlink()

    return CacheBenchmarkResult(
        corpus=corpus, queries=len(questions), cold_pass_mean_latency_ms=round(cold_mean, 3), warm_pass_mean_latency_ms=round(warm_mean, 3),
        cache_hit_count=stats["cache_hit_count"], cache_miss_count=stats["cache_miss_count"],
        hit_rate=round(stats["cache_hit_count"] / (stats["cache_hit_count"] + stats["cache_miss_count"]), 4) if (stats["cache_hit_count"] + stats["cache_miss_count"]) else 0.0,
        speedup_factor=round(cold_mean / warm_mean, 2) if warm_mean > 0 else None,
    )


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    corpora = ["golden", "chunking"] if args.corpus == "both" else [args.corpus]
    results = [_run_corpus(corpus=corpus, keep_db=args.keep_db) for corpus in corpora]

    if args.format == "json":
        print(json.dumps([asdict(r) for r in results], indent=2))
    else:
        for r in results:
            print(f"=== {r.corpus} ===")
            print(f"queries={r.queries} hit_rate={r.hit_rate:.1%} hits={r.cache_hit_count} misses={r.cache_miss_count}")
            print(f"cold_pass_mean_latency_ms={r.cold_pass_mean_latency_ms} warm_pass_mean_latency_ms={r.warm_pass_mean_latency_ms} speedup={r.speedup_factor}x")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
