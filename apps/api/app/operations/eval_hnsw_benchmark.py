"""CLI: Retrieval & Answer Pipeline V3 experiment, Part 6 - empirically
measure pgvector HNSW (alembic/versions/0022_pgvector_hnsw_index.py) against
exact search on THIS project's real corpora, using REAL nomic-embed-text-v2-moe
embeddings (not mock) against a REAL PostgreSQL/pgvector database - not a
claim, a measurement. Never asserts O(log n) complexity; HNSW is treated
throughout as approximate acceleration whose recall/latency trade-off must be
measured, and this script's whole job is producing that measurement.

    python -m app.operations.eval_hnsw_benchmark [--corpus golden|chunking|both] [--top-k 10] [--format text|json]

Requires a reachable Postgres/pgvector server (see
tests/test_vector_search_postgres_integration.py's POSTGRES_TEST_DATABASE_URL
convention - `docker compose up -d postgres`) and EVAL_EMBEDDING_PROVIDER=ollama/
EVAL_EMBEDDING_MODEL set. Fails loud (SystemExit(2)), never silently degrades
to a fake/mock comparison, if either is unavailable.

Real embeddings from Ollama (768-dim, nomic-embed-text-v2-moe) are zero-padded
up to PRODUCTION_EMBEDDING_DIMENSION (1536, the fixed `vector(1536)` column
width - see app.db.models.chunk.Chunk) before insertion - a shared all-zero
suffix on both operands of a cosine-similarity comparison contributes 0 to the
dot product and does not change either vector's direction, so this preserves
the exact real-embedding cosine ranking (same technique
tests/test_vector_search_postgres_integration.py's ControlledEmbeddingProvider
uses, reused here for a real, not hand-picked, provider).

Exact vs ANN comparison method: Postgres planner GUCs (`SET LOCAL
enable_indexscan/enable_bitmapscan = off` forces a sequential (exact) scan;
leaving them at their default `on` lets the planner use the HNSW index when
it judges that cheaper) toggled around the SAME, completely unmodified
app.services.vector_search.search_embedded_chunks() call - this script does
not duplicate or fork that query, and does not touch vector_search.py at all.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from dataclasses import asdict, dataclass, field
from statistics import mean, median

from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings
from app.db.base import Base
from app.db import models  # noqa: F401 - import registers every model with Base.metadata
from app.db.models import Membership, Organisation, User, Workspace
from app.evaluation.embedding_config import build_real_eval_embedding_provider, load_eval_embedding_config_from_env
from app.evaluation.fixtures.loader import load_chunking_fixture_definition, seed_golden_dataset
from app.repositories import evaluation_repository
from app.services.chunking_strategies import ChunkingConfig, build_chunking_strategy
from app.services.embeddings import EmbeddingProvider, EmbeddingProviderError
from app.services.vector_search import search_embedded_chunks

PRODUCTION_EMBEDDING_DIMENSION = 1536
HNSW_INDEX_NAME = "ix_chunks_embedding_vector_hnsw"

POSTGRES_TEST_DATABASE_URL = os.environ.get(
    "POSTGRES_TEST_DATABASE_URL", "postgresql+psycopg://postgres:postgres@localhost:5432/chatbotweb_test"
)


@dataclass(frozen=True)
class PaddedRealEmbeddingProvider:
    """Wraps a real embedding provider (e.g. Ollama nomic-embed-text-v2-moe,
    768-dim) and zero-pads its output up to the fixed Postgres `vector(1536)`
    column width - see this module's docstring for why padding preserves the
    real cosine-similarity ranking exactly."""

    inner: EmbeddingProvider
    dimension: int = PRODUCTION_EMBEDDING_DIMENSION

    @property
    def provider_name(self) -> str:
        return self.inner.provider_name

    @property
    def model_name(self) -> str:
        return self.inner.model_name

    def embed(self, text_value: str) -> list[float]:
        vector = self.inner.embed(text_value)
        if len(vector) > self.dimension:
            raise ValueError(f"Real embedding dimension {len(vector)} exceeds padded target {self.dimension}.")
        return list(vector) + [0.0] * (self.dimension - len(vector))


@dataclass
class QueryComparison:
    question: str
    exact_top_k: list[str]
    ann_top_k: list[str]
    exact_latency_ms: float
    ann_latency_ms: float
    agreement_count: int
    agreement_rate: float
    recall_at_k: float  # fraction of exact's top-k that ANN also returned (anywhere in ANN's own top-k)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="V3 Part 6 - empirical pgvector HNSW vs exact-search benchmark.")
    parser.add_argument("--corpus", default="chunking", choices=["golden", "chunking", "both"])
    parser.add_argument("--top-k", type=int, default=10)
    parser.add_argument("--format", default="text", choices=["text", "json"])
    return parser.parse_args(argv)


def _require_postgres() -> Session:
    try:
        admin_url = make_url(POSTGRES_TEST_DATABASE_URL).set(database="postgres")
        admin_engine = create_engine(admin_url, connect_args={"connect_timeout": 3})
        with admin_engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        admin_engine.dispose()
    except Exception as exc:  # noqa: BLE001
        print(f"MISSING PREREQUISITE: Postgres/pgvector not reachable at {POSTGRES_TEST_DATABASE_URL!r}: {exc}", file=sys.stderr)
        print("Run `docker compose up -d postgres` first, or set POSTGRES_TEST_DATABASE_URL.", file=sys.stderr)
        raise SystemExit(2)

    url = make_url(POSTGRES_TEST_DATABASE_URL)
    admin_engine = create_engine(url.set(database="postgres"), isolation_level="AUTOCOMMIT")
    with admin_engine.connect() as conn:
        exists = conn.execute(text("SELECT 1 FROM pg_database WHERE datname = :name"), {"name": url.database}).scalar()
        if not exists:
            conn.execute(text(f'CREATE DATABASE "{url.database}"'))
    admin_engine.dispose()

    engine = create_engine(POSTGRES_TEST_DATABASE_URL)
    with engine.connect() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        conn.commit()
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)(), engine


def _build_real_padded_provider() -> PaddedRealEmbeddingProvider:
    try:
        inner = build_real_eval_embedding_provider()
    except EmbeddingProviderError as exc:
        print(f"MISSING PREREQUISITE: real embedding provider not available: {exc}", file=sys.stderr)
        raise SystemExit(2)
    return PaddedRealEmbeddingProvider(inner=inner)


def _build_hnsw_index(engine) -> tuple[float, int]:
    """Returns (build_seconds, index_size_bytes). Drops first so this is
    idempotent across repeated runs against the same test database."""
    with engine.connect() as conn:
        conn.execute(text(f"DROP INDEX IF EXISTS {HNSW_INDEX_NAME}"))
        conn.commit()
        started = time.perf_counter()
        conn.execute(
            text(
                f"CREATE INDEX {HNSW_INDEX_NAME} ON chunks USING hnsw (embedding_vector vector_cosine_ops) "
                f"WITH (m = {settings.PGVECTOR_HNSW_M}, ef_construction = {settings.PGVECTOR_HNSW_EF_CONSTRUCTION})"
            )
        )
        conn.commit()
        build_seconds = time.perf_counter() - started
        size_bytes = conn.execute(text(f"SELECT pg_relation_size('{HNSW_INDEX_NAME}')")).scalar_one()
    return build_seconds, int(size_bytes)


def _force_scan_mode(db: Session, *, exact: bool) -> None:
    # Session-level (not SET LOCAL - this script issues each search as its
    # own statement, not wrapped in one explicit transaction block, and
    # SET LOCAL's effect ends at the next COMMIT) GUC toggle, reset after
    # each measurement. Never applied inside app.services.vector_search
    # itself - this is benchmark-only, exercised on this script's own
    # session, not the production query path.
    db.execute(text(f"SET enable_indexscan = {'off' if exact else 'on'}"))
    db.execute(text(f"SET enable_bitmapscan = {'off' if exact else 'on'}"))


def _run_corpus(*, corpus: str, provider: PaddedRealEmbeddingProvider, top_k: int) -> dict:
    db, engine = _require_postgres()
    try:
        organisation = Organisation(name="HNSW Benchmark", slug=f"hnsw-benchmark-{corpus}-{os.getpid()}", status="active", plan_key="starter")
        workspace = Workspace(organisation=organisation, name="Workspace", slug="workspace", status="active", default_language="en")
        user = User(email="hnsw-benchmark@example.test", full_name="Benchmark")
        membership = Membership(organisation=organisation, user=user, role="org_owner", status="active")
        db.add_all([organisation, workspace, user, membership])
        db.commit()

        structure_aware_strategy = build_chunking_strategy("structure_aware", embedding_provider=None)
        if corpus == "chunking":
            fixture = load_chunking_fixture_definition()
            chunking_config = ChunkingConfig(chunk_size_words=120, chunk_overlap_words=25, min_chunk_size_words=30, max_chunk_size_words=200, source_type="txt")
        else:
            fixture = None
            chunking_config = ChunkingConfig(chunk_size_words=300, chunk_overlap_words=50, source_type="txt")

        seed_started = time.perf_counter()
        loaded = seed_golden_dataset(
            db, organisation=organisation, workspace=workspace, embedding_provider=provider, actor_user_id=user.id,
            fixture=fixture, chunking_strategy=structure_aware_strategy, chunking_config=chunking_config,
        )
        seed_seconds = time.perf_counter() - seed_started
        chunk_count = db.execute(text("SELECT count(*) FROM chunks WHERE organisation_id = :oid"), {"oid": organisation.id}).scalar_one()

        build_seconds, index_size_bytes = _build_hnsw_index(engine)

        cases = [c for c in evaluation_repository.list_cases_for_dataset(db, dataset_id=loaded.dataset.id) if c.expected_document_ids and c.expected_answerability == "answerable"]

        comparisons: list[QueryComparison] = []
        for case in cases:
            _force_scan_mode(db, exact=True)
            exact_started = time.perf_counter()
            exact_matches = search_embedded_chunks(
                db, organisation_id=organisation.id, workspace_id=workspace.id, query=case.question,
                limit=top_k, provider=provider, document_ids=None, min_similarity_score=0.0,
            )
            exact_latency_ms = (time.perf_counter() - exact_started) * 1000

            _force_scan_mode(db, exact=False)
            ann_started = time.perf_counter()
            ann_matches = search_embedded_chunks(
                db, organisation_id=organisation.id, workspace_id=workspace.id, query=case.question,
                limit=top_k, provider=provider, document_ids=None, min_similarity_score=0.0,
            )
            ann_latency_ms = (time.perf_counter() - ann_started) * 1000

            exact_ids = [m.chunk_id for m in exact_matches]
            ann_ids = [m.chunk_id for m in ann_matches]
            overlap = set(exact_ids) & set(ann_ids)
            comparisons.append(
                QueryComparison(
                    question=case.question, exact_top_k=exact_ids, ann_top_k=ann_ids,
                    exact_latency_ms=round(exact_latency_ms, 3), ann_latency_ms=round(ann_latency_ms, 3),
                    agreement_count=len(overlap),
                    agreement_rate=round(len(overlap) / len(exact_ids), 4) if exact_ids else 1.0,
                    recall_at_k=round(len(overlap) / len(exact_ids), 4) if exact_ids else 1.0,
                )
            )
        db.execute(text("RESET enable_indexscan"))
        db.execute(text("RESET enable_bitmapscan"))
    finally:
        db.close()
        Base.metadata.drop_all(engine)
        engine.dispose()

    exact_latencies = [c.exact_latency_ms for c in comparisons]
    ann_latencies = [c.ann_latency_ms for c in comparisons]
    return {
        "corpus": corpus,
        "chunk_count": int(chunk_count),
        "seed_seconds": round(seed_seconds, 2),
        "index_build_seconds": round(build_seconds, 4),
        "index_size_bytes": index_size_bytes,
        "queries_compared": len(comparisons),
        "mean_exact_latency_ms": round(mean(exact_latencies), 3) if exact_latencies else None,
        "median_exact_latency_ms": round(median(exact_latencies), 3) if exact_latencies else None,
        "mean_ann_latency_ms": round(mean(ann_latencies), 3) if ann_latencies else None,
        "median_ann_latency_ms": round(median(ann_latencies), 3) if ann_latencies else None,
        "mean_agreement_rate": round(mean(c.agreement_rate for c in comparisons), 4) if comparisons else None,
        "mean_recall_at_k": round(mean(c.recall_at_k for c in comparisons), 4) if comparisons else None,
        "perfect_agreement_query_count": sum(1 for c in comparisons if c.agreement_rate >= 0.999),
        "comparisons": [asdict(c) for c in comparisons],
    }


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    provider = _build_real_padded_provider()
    corpora = ["golden", "chunking"] if args.corpus == "both" else [args.corpus]

    results = {}
    for corpus in corpora:
        results[corpus] = _run_corpus(corpus=corpus, provider=provider, top_k=args.top_k)

    if args.format == "json":
        print(json.dumps({"embedding_provider": {"provider": provider.provider_name, "model": provider.model_name, "padded_dimension": provider.dimension}, "results": results}, indent=2, default=str))
    else:
        for corpus, r in results.items():
            print(f"=== {corpus} corpus ===")
            print(f"chunks={r['chunk_count']} index_build_seconds={r['index_build_seconds']} index_size_bytes={r['index_size_bytes']} ({r['index_size_bytes']/1024:.1f} KiB)")
            print(f"queries_compared={r['queries_compared']}")
            print(f"mean_exact_latency_ms={r['mean_exact_latency_ms']} mean_ann_latency_ms={r['mean_ann_latency_ms']}")
            print(f"median_exact_latency_ms={r['median_exact_latency_ms']} median_ann_latency_ms={r['median_ann_latency_ms']}")
            print(f"mean_agreement_rate={r['mean_agreement_rate']} mean_recall_at_k={r['mean_recall_at_k']} perfect_agreement_queries={r['perfect_agreement_query_count']}/{r['queries_compared']}")
            if r["chunk_count"] < 1000:
                print(f"NOTE: corpus has only {r['chunk_count']} chunks - too small to demonstrate a meaningful HNSW speed advantage over exact sequential scan; see report.")
            print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
