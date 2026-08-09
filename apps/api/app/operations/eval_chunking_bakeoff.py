"""CLI: Knowledge Pipeline V2 controlled bake-off.

Evaluates the current `fixed_word` chunking baseline against the
`structure_aware` and `structure_semantic` candidates over the SAME corpus,
embedding model, retrieval configuration, generation provider, prompts,
guardrails, and evaluation cases - only the chunking strategy varies between
runs. Reuses the existing evaluation framework end to end
(`app.evaluation.engine.run_evaluation`, `app.evaluation.gate.evaluate_gate`)
- this script adds no new scoring logic, it only re-seeds the same corpus
three times, once per strategy, and reports the three runs side by side.
See docs/engineering/chunking.md Phases 7-8.

    python -m app.operations.eval_chunking_bakeoff [--format text|json] [--real] [--keep-db] [--corpus golden|chunking]

`--corpus golden` (default): `golden_dataset.json`, the general
launch/regression corpus. Every document there is shorter than
`CHUNK_SIZE_WORDS`, so every strategy already produces exactly one chunk per
document - useful as a regression check that nothing breaks, but it cannot
differentiate chunking strategies. To preserve this script's original,
already-relied-upon behavior exactly, the baseline (`fixed_word`) run on
this corpus still uses `seed_golden_dataset`'s one-chunk-per-document
shortcut (`chunking_strategy=None`) rather than invoking the real chunker.

`--corpus chunking`: `chunking_dataset.json`, a separate, deliberately long
and structurally rich synthetic corpus (20 documents, ~360 words average,
headings/lists/tables/code fences, conflicting/superseded facts,
cross-section and cross-document facts) built specifically so chunking
strategy actually matters. On this corpus every strategy - including the
baseline - is run through the real `ChunkingStrategy.chunk()` call (not the
one-chunk-per-document shortcut), using the SAME `ChunkingConfig`
(`chunk_size_words=120`, deliberately smaller than the `CHUNK_SIZE_WORDS=300`
production default so even this corpus's shorter documents still split into
several chunks) across all three strategies, so the comparison is a fair,
apples-to-apples multi-chunk one.

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
from app.evaluation.fixtures.loader import load_chunking_fixture_definition, seed_golden_dataset
from app.evaluation.gate import evaluate_gate
from app.evaluation.policy import load_policy_from_env
from app.evaluation.summary_builder import build_run_summary
from app.services.chunking_strategies import ChunkingConfig, DEFAULT_STRATEGY_KEY, build_chunking_strategy
from app.services.embeddings import EmbeddingProvider, EmbeddingProviderError, build_embedding_provider

STRATEGY_KEYS = [DEFAULT_STRATEGY_KEY, "structure_aware", "structure_semantic"]


class _CountingEmbeddingProvider:
    """Wraps a real EmbeddingProvider only to count `.embed()` calls for the
    bake-off's own reporting (Phase 7's "embedding calls" metric) - never
    changes what gets embedded or returned.

    Also caches by exact text: `app.services.vector_search._search_sqlite`
    (the dev/test SQLite retrieval backend, used by every shadow database
    this script creates) has no vector index and re-embeds every candidate
    chunk on every single query, so a corpus with N chunks makes N redundant
    identical embed() calls per evaluation case. Embedding is a deterministic
    function of (model, text), so caching changes nothing about correctness -
    it only avoids re-paying an identical network round-trip repeatedly, the
    same benefit a production Postgres+pgvector deployment gets for free by
    storing vectors instead of recomputing them. `call_count` reports the
    real (post-cache) API call volume, itself a genuine performance/cost
    signal: a strategy producing more chunks pays for more of them."""

    def __init__(self, inner: EmbeddingProvider) -> None:
        self._inner = inner
        self.call_count = 0
        self._cache: dict[str, list[float]] = {}

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
        cached = self._cache.get(text)
        if cached is not None:
            return cached
        self.call_count += 1
        vector = self._inner.embed(text)
        self._cache[text] = vector
        return vector


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
    average_recall_at_k: float | None
    latency_p50_ms: int | None
    latency_p95_ms: int | None
    total_tokens: int
    gate_passed: bool
    gate_reasons: list[str] = field(default_factory=list)
    document_count: int = 0
    chunk_count: int = 0
    avg_chunks_per_document: float = 0.0
    avg_chunk_size_words: float = 0.0
    min_chunk_size_words: int = 0
    max_chunk_size_words: int = 0
    embedding_call_count: int = 0
    ingestion_seconds: float = 0.0


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Controlled bake-off: current chunking baseline vs. structure-aware vs. structure+semantic candidates.")
    parser.add_argument("--format", default="text", choices=["text", "json"], help="Report output format.")
    parser.add_argument("--real", action="store_true", help="Use EVAL_EMBEDDING_PROVIDER/MODEL (a real embedding runtime) instead of the deterministic mock.")
    parser.add_argument("--keep-db", action="store_true", help="Do not delete the per-strategy temp SQLite files afterwards.")
    parser.add_argument(
        "--corpus",
        default="golden",
        choices=["golden", "chunking"],
        help="'golden' (default, unchanged behavior): golden_dataset.json, every doc shorter than one chunk. "
        "'chunking': chunking_dataset.json, a longer/structurally-rich corpus built to genuinely exercise multi-chunk documents.",
    )
    return parser.parse_args(argv)


def _build_embedding_provider(*, use_real: bool) -> EmbeddingProvider:
    if use_real:
        try:
            return build_real_eval_embedding_provider()
        except EmbeddingProviderError as exc:
            raise SystemExit(f"Cannot run a real-embedding bake-off: {exc}") from exc
    return build_embedding_provider(provider_name="local-mock", model_name="chunking-bakeoff", dimension=8)


def _run_one_strategy(strategy_key: str, *, embedding_provider: EmbeddingProvider, keep_db: bool, corpus: str) -> StrategyBakeoffResult:
    temp_db_path = Path(tempfile.gettempdir()) / f"conversa-chunking-bakeoff-{corpus}-{strategy_key}-{os.getpid()}.db"
    database_url = f"sqlite:///{temp_db_path}"
    engine = create_engine(database_url, connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine)

    counting_provider = _CountingEmbeddingProvider(embedding_provider)
    strategy = build_chunking_strategy(strategy_key, embedding_provider=counting_provider if strategy_key == "structure_semantic" else None)

    # `golden` preserves this script's original behavior exactly: the
    # baseline uses seed_golden_dataset's one-chunk-per-document shortcut
    # (chunking_strategy=None), since every golden_dataset.json document is
    # already shorter than one chunk anyway. `chunking` corpus documents are
    # genuinely multi-chunk, so ALL THREE strategies - including the
    # baseline - are run through the real chunker with the SAME config, for
    # a fair comparison. chunk_size_words=120 (smaller than the
    # CHUNK_SIZE_WORDS=300 production default) so even this corpus's
    # ~360-word average documents reliably split into several chunks.
    if corpus == "chunking":
        fixture = load_chunking_fixture_definition()
        config = ChunkingConfig(chunk_size_words=120, chunk_overlap_words=25, min_chunk_size_words=30, max_chunk_size_words=200, source_type="txt")
        chunking_strategy_arg = strategy
    else:
        fixture = None
        config = ChunkingConfig(chunk_size_words=300, chunk_overlap_words=50, source_type="txt") if strategy_key != DEFAULT_STRATEGY_KEY else None
        chunking_strategy_arg = strategy if strategy_key != DEFAULT_STRATEGY_KEY else None

    try:
        with session_factory() as db:
            organisation = Organisation(name=f"Chunking Bakeoff {strategy_key}", slug=f"chunking-bakeoff-{corpus}-{strategy_key}-{os.getpid()}", status="active", plan_key="starter")
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
                fixture=fixture,
                chunking_strategy=chunking_strategy_arg,
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
                #
                # case_timeout_seconds is raised well above the engine's 30s
                # default for a real embedding provider: SQLite's
                # _search_sqlite has no pgvector index, so it re-embeds every
                # candidate chunk on every single query at retrieval time. A
                # multi-chunk corpus (this bake-off's whole point) multiplies
                # that per-query embedding-call volume directly, and a case
                # that times out leaves its worker thread's shadow_db
                # connection running in the background, which then collides
                # with a later case's write and raises "database is locked" -
                # so undersizing this timeout doesn't just lose one case, it
                # can corrupt the rest of the run. This is a real, measured
                # SQLite-testing-backend cost characteristic (see the bake-off
                # report's performance/cost section), not a chunking defect.
                options=EvaluationRunOptions(
                    mode="mock",
                    policy=load_policy_from_env(),
                    shadow_database_url=database_url,
                    embedding_provider=counting_provider,
                    case_timeout_seconds=180.0 if corpus == "chunking" else 30.0,
                ),
            )
            summary = build_run_summary(db, run_id=run.id)
            gate = evaluate_gate(summary, policy=load_policy_from_env(), run_status=run.status)

        # strategy.strategy_key/strategy_version are the same recorded
        # constants ("fixed_word"/"mvp-word-v1") whether or not the golden
        # corpus's one-chunk-per-document shortcut was actually used for
        # seeding - build_chunking_strategy(DEFAULT_STRATEGY_KEY) always
        # returns a FixedWordChunkingStrategy with these exact values.
        resolved_strategy_key = strategy.strategy_key
        resolved_strategy_version = strategy.strategy_version
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
            average_recall_at_k=summary.average_recall_at_k,
            latency_p50_ms=summary.latency_p50_ms,
            latency_p95_ms=summary.latency_p95_ms,
            total_tokens=summary.total_tokens,
            gate_passed=gate.passed,
            gate_reasons=list(gate.reasons),
            document_count=document_count,
            chunk_count=chunk_count,
            avg_chunks_per_document=chunk_count / document_count if document_count else 0.0,
            avg_chunk_size_words=sum(chunk_words) / len(chunk_words) if chunk_words else 0.0,
            min_chunk_size_words=min(chunk_words) if chunk_words else 0,
            max_chunk_size_words=max(chunk_words) if chunk_words else 0,
            embedding_call_count=counting_provider.call_count,
            ingestion_seconds=ingestion_seconds,
        )
    finally:
        engine.dispose()
        if temp_db_path.exists() and not keep_db:
            temp_db_path.unlink()


def _print_text_report(results: list[StrategyBakeoffResult], *, embedding_provider: EmbeddingProvider, corpus: str) -> None:
    print(f"Knowledge Pipeline V2 bake-off - corpus: {corpus} - embedding provider: {embedding_provider.provider_name}/{embedding_provider.model_name} (dimension {embedding_provider.dimension})")
    print()
    header = (
        f"{'strategy':18s} {'pass_rate':>9s} {'hard_fail':>9s} {'hit_rate':>9s} {'recall@k':>9s} {'citation':>9s} {'fallback':>9s} "
        f"{'chunks/doc':>10s} {'avg/min/max':>14s} {'embeds':>7s} {'ingest_s':>9s} {'p50/p95 ms':>12s} {'tokens':>8s} {'gate':>7s}"
    )
    print(header)
    for r in results:
        hit_rate = f"{r.retrieval_hit_rate:.1%}" if r.retrieval_hit_rate is not None else "n/a"
        recall = f"{r.average_recall_at_k:.1%}" if r.average_recall_at_k is not None else "n/a"
        citation = f"{r.citation_coverage:.1%}" if r.citation_coverage is not None else "n/a"
        fallback = f"{r.fallback_rate_on_answerable:.1%}" if r.fallback_rate_on_answerable is not None else "n/a"
        latency = f"{r.latency_p50_ms or 0}/{r.latency_p95_ms or 0}"
        size_summary = f"{r.avg_chunk_size_words:.0f}/{r.min_chunk_size_words}/{r.max_chunk_size_words}"
        print(
            f"{r.strategy_key:18s} {r.pass_rate:8.1%} {r.hard_failure_cases:9d} {hit_rate:>9s} {recall:>9s} {citation:>9s} {fallback:>9s} "
            f"{r.avg_chunks_per_document:10.2f} {size_summary:>14s} {r.embedding_call_count:7d} {r.ingestion_seconds:9.3f} "
            f"{latency:>12s} {r.total_tokens:8d} {'PASS' if r.gate_passed else 'FAIL':>7s}"
        )
    print()
    baseline = results[0]
    for candidate in results[1:]:
        print(f"--- {candidate.strategy_key} vs {baseline.strategy_key} ---")
        identical_chunks = candidate.chunk_count == baseline.chunk_count and candidate.avg_chunk_size_words == baseline.avg_chunk_size_words
        if identical_chunks:
            print("  Chunk counts/sizes are IDENTICAL to the baseline for this corpus (every document here is shorter than")
            print("  the configured chunk size, so every strategy already produces exactly one chunk per document - see")
            print("  docs/engineering/chunking.md for corpus-specific notes).")
        new_hard_failures = candidate.hard_failure_cases - baseline.hard_failure_cases
        pass_rate_delta = candidate.pass_rate - baseline.pass_rate
        hit_rate_delta = (
            (candidate.retrieval_hit_rate - baseline.retrieval_hit_rate)
            if candidate.retrieval_hit_rate is not None and baseline.retrieval_hit_rate is not None
            else None
        )
        recall_delta = (
            (candidate.average_recall_at_k - baseline.average_recall_at_k)
            if candidate.average_recall_at_k is not None and baseline.average_recall_at_k is not None
            else None
        )
        citation_delta = (
            (candidate.citation_coverage - baseline.citation_coverage)
            if candidate.citation_coverage is not None and baseline.citation_coverage is not None
            else None
        )
        print(f"  hard_failure_cases delta: {new_hard_failures:+d}  pass_rate delta: {pass_rate_delta:+.1%}")
        print(f"  hit_rate delta: {hit_rate_delta:+.1%}" if hit_rate_delta is not None else "  hit_rate delta: n/a")
        print(f"  recall@k delta: {recall_delta:+.1%}" if recall_delta is not None else "  recall@k delta: n/a")
        print(f"  citation_coverage delta: {citation_delta:+.1%}" if citation_delta is not None else "  citation_coverage delta: n/a")
        # Phase 8 promotion rule (see docs/engineering/chunking.md): no new hard
        # failures, perfect citation behaviour maintained, and retrieval quality
        # (hit rate AND recall) not measurably worse than the baseline. This is a
        # necessary, not sufficient, check - a human must still judge whether any
        # improvement is attributable to chunking rather than provider noise
        # (see the bake-off's case-by-case analysis, not just this table).
        non_regressive = (
            new_hard_failures <= 0
            and pass_rate_delta >= -0.001
            and (hit_rate_delta is None or hit_rate_delta >= -0.001)
            and (recall_delta is None or recall_delta >= -0.001)
            and (citation_delta is None or citation_delta >= -0.001)
        )
        print(f"  Phase 8 promotion check: {'non-regressive' if non_regressive else 'REGRESSION'}")
    print()


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    embedding_provider = _build_embedding_provider(use_real=args.real)

    results = [
        _run_one_strategy(strategy_key, embedding_provider=embedding_provider, keep_db=args.keep_db, corpus=args.corpus) for strategy_key in STRATEGY_KEYS
    ]

    if args.format == "json":
        print(
            json.dumps(
                {
                    "corpus": args.corpus,
                    "embedding_provider": {"provider": embedding_provider.provider_name, "model": embedding_provider.model_name, "dimension": embedding_provider.dimension},
                    "results": [asdict(r) for r in results],
                },
                indent=2,
                default=str,
            )
        )
    else:
        _print_text_report(results, embedding_provider=embedding_provider, corpus=args.corpus)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
