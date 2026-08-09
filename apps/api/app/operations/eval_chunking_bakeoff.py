"""CLI: Knowledge Pipeline V2 controlled bake-off.

Evaluates the current `fixed_word` chunking baseline against the
`structure_aware` and `structure_semantic` candidates over the SAME golden
corpus (`golden_dataset.json`), embedding model, retrieval configuration,
generation provider, prompts, guardrails, and evaluation cases - only the
chunking strategy varies between runs. Reuses the existing evaluation
framework end to end (`app.evaluation.engine.run_evaluation`,
`app.evaluation.gate.evaluate_gate`) - this script adds no new scoring
logic, it only re-seeds the same corpus three times, once per strategy, and
reports the three runs side by side. See docs/engineering/chunking.md
Phases 7-8.

    python -m app.operations.eval_chunking_bakeoff [--format text|json] [--real] [--keep-db]

Mock mode (default): deterministic, credential-free, no external calls -
proves the mechanics (chunking, seeding, retrieval, scoring) work
end-to-end for every strategy, but `LocalMockEmbeddingProvider` has no
semantic content (SHA-256 hash), so a "topic shift" the semantic strategy
detects under mock embeddings is not meaningful - only the structural
(non-embedding) differences between fixed_word and structure_aware are.

`--real`: uses `EVAL_EMBEDDING_PROVIDER`/`EVAL_EMBEDDING_MODEL` (must
already be set - e.g. `ollama`/`nomic-embed-text-v2-moe`, see
docs/04_Engineering/Evaluation_Real_Embedding_Provider.md) for a genuinely
semantically meaningful comparison, including of the semantic strategy's
own topic-shift boundaries. Requires a reachable embedding runtime; fails
clearly (never silently falls back to mock) if unavailable.

Exits 0 regardless of any individual strategy's gate result (this is a
comparison report, not a pass/fail gate for one strategy) - see the printed
Phase 8 promotion recommendation for the actual accept/reject call.
"""

from __future__ import annotations

import argparse
import json
import os
import tempfile
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path

from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.db.base import Base
from app.db import models  # noqa: F401 - import registers every model with Base.metadata
from app.db.models import Chunk, Membership, Organisation, User, Workspace
from app.evaluation.embedding_config import build_real_eval_embedding_provider
from app.evaluation.engine import EvaluationRunOptions, run_evaluation
from app.evaluation.fixtures.loader import seed_golden_dataset
from app.evaluation.gate import evaluate_gate
from app.evaluation.policy import load_policy_from_env
from app.evaluation.summary_builder import build_run_summary
from app.services.chunking_strategies import ChunkingConfig, DEFAULT_STRATEGY_KEY, build_chunking_strategy
from app.services.embeddings import EmbeddingProvider, EmbeddingProviderError, build_embedding_provider

STRATEGY_KEYS = [DEFAULT_STRATEGY_KEY, "structure_aware", "structure_semantic"]


class _CountingEmbeddingProvider:
    """Wraps a real EmbeddingProvider only to count `.embed()` calls for the
    bake-off's own reporting (Phase 7's "embedding calls" metric) - never
    changes what gets embedded or returned."""

    def __init__(self, inner: EmbeddingProvider) -> None:
        self._inner = inner
        self.call_count = 0

    @property
    def provider_name(self) -> str:
        return self._inner.provider_name

    @property
    def model_name(self) -> str:
        return self._inner.model_name

    @property
    def dimension(self) -> int:
        return self._inner.dimension

    def embed(self, text: str) -> list[float]:
        self.call_count += 1
        return self._inner.embed(text)


@dataclass
class StrategyBakeoffResult:
    strategy_key: str
    strategy_version: str
    total_cases: int
    passed_cases: int
    failed_cases: int
    hard_failure_cases: int
    pass_rate: float
    retrieval_hit_rate: float | None
    citation_coverage: float | None
    fallback_rate_on_answerable: float | None
    correct_fallback_rate_on_unanswerable: float | None
    latency_p50_ms: int | None
    latency_p95_ms: int | None
    total_tokens: int
    gate_passed: bool
    gate_reasons: list[str] = field(default_factory=list)
    document_count: int = 0
    chunk_count: int = 0
    avg_chunks_per_document: float = 0.0
    avg_chunk_size_words: float = 0.0
    embedding_call_count: int = 0
    ingestion_seconds: float = 0.0


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Controlled bake-off: current chunking baseline vs. structure-aware vs. structure+semantic candidates.")
    parser.add_argument("--format", default="text", choices=["text", "json"], help="Report output format.")
    parser.add_argument("--real", action="store_true", help="Use EVAL_EMBEDDING_PROVIDER/MODEL (a real embedding runtime) instead of the deterministic mock.")
    parser.add_argument("--keep-db", action="store_true", help="Do not delete the per-strategy temp SQLite files afterwards.")
    return parser.parse_args(argv)


def _build_embedding_provider(*, use_real: bool) -> EmbeddingProvider:
    if use_real:
        try:
            return build_real_eval_embedding_provider()
        except EmbeddingProviderError as exc:
            raise SystemExit(f"Cannot run a real-embedding bake-off: {exc}") from exc
    return build_embedding_provider(provider_name="local-mock", model_name="chunking-bakeoff", dimension=8)


def _run_one_strategy(strategy_key: str, *, embedding_provider: EmbeddingProvider, keep_db: bool) -> StrategyBakeoffResult:
    temp_db_path = Path(tempfile.gettempdir()) / f"conversa-chunking-bakeoff-{strategy_key}-{os.getpid()}.db"
    database_url = f"sqlite:///{temp_db_path}"
    engine = create_engine(database_url, connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine)

    counting_provider = _CountingEmbeddingProvider(embedding_provider)
    strategy = build_chunking_strategy(strategy_key, embedding_provider=counting_provider if strategy_key == "structure_semantic" else None)
    config = ChunkingConfig(chunk_size_words=300, chunk_overlap_words=50, source_type="txt") if strategy_key != DEFAULT_STRATEGY_KEY else None

    try:
        with session_factory() as db:
            organisation = Organisation(name=f"Chunking Bakeoff {strategy_key}", slug=f"chunking-bakeoff-{strategy_key}-{os.getpid()}", status="active", plan_key="starter")
            workspace = Workspace(organisation=organisation, name="Workspace", slug="workspace", status="active", default_language="en")
            user = User(email=f"bakeoff-{strategy_key}@example.test", full_name="Bakeoff")
            membership = Membership(organisation=organisation, user=user, role="org_owner", status="active")
            db.add_all([organisation, workspace, user, membership])
            db.commit()

            ingestion_started = time.perf_counter()
            loaded = seed_golden_dataset(
                db,
                organisation=organisation,
                workspace=workspace,
                embedding_provider=counting_provider,
                actor_user_id=user.id,
                chunking_strategy=strategy if strategy_key != DEFAULT_STRATEGY_KEY else None,
                chunking_config=config,
            )
            ingestion_seconds = time.perf_counter() - ingestion_started

            chunks = db.execute(select(Chunk).where(Chunk.organisation_id == organisation.id)).scalars().all()
            document_count = len(loaded.document_ids)
            chunk_count = len(chunks)
            chunk_words = [len(chunk.content.split()) for chunk in chunks]

            run = run_evaluation(
                db,
                dataset=loaded.dataset,
                organisation_id=organisation.id,
                workspace_id=workspace.id,
                widget_id=loaded.widget_id,
                # embedding_provider MUST match what the chunks were seeded
                # with above - run_evaluation otherwise falls back to
                # settings.EMBEDDING_PROVIDER/MODEL/DIMENSION (the ambient
                # app-wide default), which would silently retrieve zero
                # chunks (exact provider/model/dimension match required -
                # see app.services.vector_search._search_sqlite) rather than
                # actually exercising this strategy's chunks.
                options=EvaluationRunOptions(
                    mode="mock", policy=load_policy_from_env(), shadow_database_url=database_url, embedding_provider=counting_provider
                ),
            )
            summary = build_run_summary(db, run_id=run.id)
            gate = evaluate_gate(summary, policy=load_policy_from_env(), run_status=run.status)

        resolved_strategy_key = DEFAULT_STRATEGY_KEY if strategy_key == DEFAULT_STRATEGY_KEY else strategy.strategy_key
        resolved_strategy_version = "mvp-word-v1" if strategy_key == DEFAULT_STRATEGY_KEY else strategy.strategy_version
        return StrategyBakeoffResult(
            strategy_key=resolved_strategy_key,
            strategy_version=resolved_strategy_version,
            total_cases=summary.total_cases,
            passed_cases=summary.passed_cases,
            failed_cases=summary.failed_cases,
            hard_failure_cases=summary.hard_failure_cases,
            pass_rate=summary.pass_rate,
            retrieval_hit_rate=summary.retrieval_hit_rate,
            citation_coverage=summary.citation_coverage,
            fallback_rate_on_answerable=summary.fallback_rate_on_answerable,
            correct_fallback_rate_on_unanswerable=summary.correct_fallback_rate_on_unanswerable,
            latency_p50_ms=summary.latency_p50_ms,
            latency_p95_ms=summary.latency_p95_ms,
            total_tokens=summary.total_tokens,
            gate_passed=gate.passed,
            gate_reasons=list(gate.reasons),
            document_count=document_count,
            chunk_count=chunk_count,
            avg_chunks_per_document=chunk_count / document_count if document_count else 0.0,
            avg_chunk_size_words=sum(chunk_words) / len(chunk_words) if chunk_words else 0.0,
            embedding_call_count=counting_provider.call_count,
            ingestion_seconds=ingestion_seconds,
        )
    finally:
        engine.dispose()
        if temp_db_path.exists() and not keep_db:
            temp_db_path.unlink()


def _print_text_report(results: list[StrategyBakeoffResult], *, embedding_provider: EmbeddingProvider) -> None:
    print(f"Knowledge Pipeline V2 bake-off - embedding provider: {embedding_provider.provider_name}/{embedding_provider.model_name} (dimension {embedding_provider.dimension})")
    print()
    header = f"{'strategy':18s} {'pass_rate':>9s} {'hard_fail':>9s} {'hit_rate':>9s} {'citation':>9s} {'fallback':>9s} {'chunks/doc':>10s} {'avg_words':>9s} {'embeds':>7s} {'ingest_s':>9s} {'p50/p95 ms':>12s} {'tokens':>8s} {'gate':>7s}"
    print(header)
    for r in results:
        hit_rate = f"{r.retrieval_hit_rate:.1%}" if r.retrieval_hit_rate is not None else "n/a"
        citation = f"{r.citation_coverage:.1%}" if r.citation_coverage is not None else "n/a"
        fallback = f"{r.fallback_rate_on_answerable:.1%}" if r.fallback_rate_on_answerable is not None else "n/a"
        latency = f"{r.latency_p50_ms or 0}/{r.latency_p95_ms or 0}"
        print(
            f"{r.strategy_key:18s} {r.pass_rate:8.1%} {r.hard_failure_cases:9d} {hit_rate:>9s} {citation:>9s} {fallback:>9s} "
            f"{r.avg_chunks_per_document:10.2f} {r.avg_chunk_size_words:9.1f} {r.embedding_call_count:7d} {r.ingestion_seconds:9.3f} "
            f"{latency:>12s} {r.total_tokens:8d} {'PASS' if r.gate_passed else 'FAIL':>7s}"
        )
    print()
    baseline = results[0]
    for candidate in results[1:]:
        print(f"--- {candidate.strategy_key} vs {baseline.strategy_key} ---")
        identical_chunks = candidate.chunk_count == baseline.chunk_count and candidate.avg_chunk_size_words == baseline.avg_chunk_size_words
        if identical_chunks:
            print("  Chunk counts/sizes are IDENTICAL to the baseline for this corpus (every golden document is shorter than")
            print("  CHUNK_SIZE_WORDS, so every strategy already produces exactly one chunk per document here - see")
            print("  docs/engineering/chunking.md for why this corpus cannot differentiate chunking strategies).")
        new_hard_failures = candidate.hard_failure_cases - baseline.hard_failure_cases
        pass_rate_delta = candidate.pass_rate - baseline.pass_rate
        print(f"  hard_failure_cases delta: {new_hard_failures:+d}  pass_rate delta: {pass_rate_delta:+.1%}")
        non_regressive = new_hard_failures <= 0 and pass_rate_delta >= -0.001
        print(f"  Phase 8 promotion check: {'non-regressive' if non_regressive else 'REGRESSION'}")
    print()


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    embedding_provider = _build_embedding_provider(use_real=args.real)

    results = [_run_one_strategy(strategy_key, embedding_provider=embedding_provider, keep_db=args.keep_db) for strategy_key in STRATEGY_KEYS]

    if args.format == "json":
        print(
            json.dumps(
                {
                    "embedding_provider": {"provider": embedding_provider.provider_name, "model": embedding_provider.model_name, "dimension": embedding_provider.dimension},
                    "results": [asdict(r) for r in results],
                },
                indent=2,
                default=str,
            )
        )
    else:
        _print_text_report(results, embedding_provider=embedding_provider)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
