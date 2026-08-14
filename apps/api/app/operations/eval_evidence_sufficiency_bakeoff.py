"""CLI: Evidence Sufficiency V2, Part 8/9 - controlled bake-off comparing the
V1 (production baseline) and V2 (docs/future/GuardrailsV2.md task) evidence-
sufficiency verifiers over the SAME corpus, chunking strategy
(structure_aware - ADR-0031), embedding model, calibrated similarity
threshold (ADR-0032), retrieval strategy (dense_only, reranker disabled,
query transformer identity - this task's explicit "do not change retrieval
strategy" instruction), generation provider/prompts, and citation/guardrail
chain. Only the evidence-sufficiency verifier varies between runs. Reuses the
existing evaluation framework end to end (app.evaluation.engine.run_evaluation)
against the FULL dataset (not just answerable_factual) so isolation,
citation, prompt-injection, and similar-but-absent categories are exercised
too - Part 10's promotion criteria need all of them, not just the answerable
cases the failure analysis focused on.

    python -m app.operations.eval_evidence_sufficiency_bakeoff [--format text|json] [--real] [--keep-db] [--corpus golden|chunking|both]

Mock mode (default): deterministic, credential-free - proves the mechanics
end-to-end, but LocalMockEmbeddingProvider has no semantic content, so this
comparison is not representative of V2's real effect - use --real.

`--real`: uses EVAL_EMBEDDING_PROVIDER/EVAL_EMBEDDING_MODEL (must already be
set, e.g. ollama/nomic-embed-text-v2-moe) and this project's calibrated
RETRIEVAL_MIN_SIMILARITY_SCORE for that model (0.32, docs/adr/0032).

Also reproduces, for every answerable case where V1's own retrieval already
surfaced the expected evidence (app.ai.guardrails.evidence_sufficiency
directly, independent of run_evaluation - the same technique
app.operations.eval_evidence_sufficiency_failure_analysis uses, since
EvaluationResult does not persist a guardrail reason_code column), a
case-level V1-vs-V2 reason-code transition table (Part 9) - this is the only
way to see the exact reason code before/after without a schema change,
which this task does not ask for.

Exits 0 regardless of any individual variant's gate result (this is a
comparison report, not a pass/fail gate) - see the printed promotion check
for the actual accept/reject call (Part 10 policy).
"""

from __future__ import annotations

import argparse
import json
import os
import tempfile
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.ai.guardrails.evidence_sufficiency import (
    EvidenceSufficiencyV1Verifier,
    EvidenceSufficiencyV2Verifier,
    EvidenceVerifier,
    verify_evidence_sufficiency,
    verify_evidence_sufficiency_v2,
)
from app.core.config import settings
from app.db.base import Base
from app.db import models  # noqa: F401 - import registers every model with Base.metadata
from app.db.models import Membership, Organisation, User, Workspace
from app.evaluation.embedding_cache import CachingEmbeddingProvider
from app.evaluation.embedding_config import (
    build_real_eval_embedding_provider,
    load_eval_embedding_config_from_env,
    recommended_min_similarity_score,
)
from app.evaluation.engine import EvaluationRunOptions, run_evaluation
from app.evaluation.fixtures.loader import load_chunking_fixture_definition, seed_golden_dataset
from app.evaluation.gate import evaluate_gate
from app.evaluation.policy import load_policy_from_env
from app.evaluation.summary_builder import build_run_summary
from app.repositories import evaluation_repository
from app.services.chunking_strategies import ChunkingConfig, build_chunking_strategy
from app.services.embeddings import EmbeddingProvider, EmbeddingProviderError, build_embedding_provider
from app.services.query_transformation import IdentityQueryTransformer, transform_query
from app.services.reranking import NO_RERANKER_PROVIDER, build_reranker
from app.services.retrieval_context import DENSE_ONLY_STRATEGY, assemble_retrieval_context


@dataclass(frozen=True)
class Variant:
    label: str
    verifier: EvidenceVerifier


@dataclass
class VariantResult:
    label: str
    evidence_verifier_version: str
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
    average_precision_at_k: float | None
    latency_p50_ms: int | None
    latency_p95_ms: int | None
    total_tokens: int
    gate_passed: bool
    gate_reasons: list[str] = field(default_factory=list)
    failure_reason_counts: dict[str, int] = field(default_factory=dict)
    category_pass_rate: dict[str, float] = field(default_factory=dict)
    run_seconds: float = 0.0


@dataclass
class CaseTransition:
    case_id: str
    question: str
    category: str
    tags: list[str]
    v1_sufficient: bool
    v1_reason_code: str
    v2_sufficient: bool
    v2_reason_code: str
    change: str  # "fixed" | "newly_broken" | "unchanged_pass" | "unchanged_fail"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Evidence Sufficiency V2 Part 8/9 - controlled V1 vs V2 bake-off.")
    parser.add_argument("--format", default="text", choices=["text", "json"], help="Report output format.")
    parser.add_argument("--real", action="store_true", help="Use EVAL_EMBEDDING_PROVIDER/MODEL (a real embedding runtime) instead of the deterministic mock.")
    parser.add_argument("--keep-db", action="store_true", help="Do not delete the temp SQLite file(s) afterwards.")
    parser.add_argument("--corpus", default="both", choices=["golden", "chunking", "both"], help="Which corpus/corpora to analyse.")
    return parser.parse_args(argv)


def _build_embedding_provider(*, use_real: bool) -> tuple[EmbeddingProvider, float]:
    if use_real:
        try:
            provider = build_real_eval_embedding_provider()
        except EmbeddingProviderError as exc:
            raise SystemExit(f"Cannot run a real-embedding bake-off: {exc}") from exc
        recommended = recommended_min_similarity_score(load_eval_embedding_config_from_env())
        min_similarity_score = recommended if recommended is not None else settings.RETRIEVAL_MIN_SIMILARITY_SCORE
        return provider, min_similarity_score
    return build_embedding_provider(provider_name="local-mock", model_name="evidence-sufficiency-bakeoff", dimension=8), settings.RETRIEVAL_MIN_SIMILARITY_SCORE


def _category_pass_rates(db, *, run_id: str) -> dict[str, float]:
    totals: dict[str, int] = {}
    passed: dict[str, int] = {}
    for result in evaluation_repository.list_results_for_run(db, run_id=run_id):
        category = result.case.category if result.case is not None else "unknown"
        totals[category] = totals.get(category, 0) + 1
        if result.passed:
            passed[category] = passed.get(category, 0) + 1
    return {category: passed.get(category, 0) / total for category, total in totals.items()}


def _failure_reason_counts(db, *, run_id: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for result in evaluation_repository.list_results_for_run(db, run_id=run_id):
        for reason in result.failure_reasons_json or []:
            counts[reason] = counts.get(reason, 0) + 1
    return counts


def _run_bakeoff_for_corpus(*, corpus: str, embedding_provider: EmbeddingProvider, min_similarity_score: float, keep_db: bool) -> tuple[list[VariantResult], list[CaseTransition]]:
    variants = [
        Variant(label="v1", verifier=EvidenceSufficiencyV1Verifier()),
        Variant(label="v2", verifier=EvidenceSufficiencyV2Verifier()),
    ]

    temp_db_path = Path(tempfile.gettempdir()) / f"conversa-evidence-sufficiency-bakeoff-{corpus}-{os.getpid()}.db"
    database_url = f"sqlite:///{temp_db_path}"
    engine = create_engine(database_url, connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine)

    cached_provider = CachingEmbeddingProvider(embedding_provider)
    no_reranker = build_reranker(provider_name=NO_RERANKER_PROVIDER)
    identity_transformer = IdentityQueryTransformer()
    structure_aware_strategy = build_chunking_strategy("structure_aware", embedding_provider=None)

    if corpus == "chunking":
        fixture = load_chunking_fixture_definition()
        chunking_config = ChunkingConfig(chunk_size_words=120, chunk_overlap_words=25, min_chunk_size_words=30, max_chunk_size_words=200, source_type="txt")
    else:
        fixture = None
        chunking_config = ChunkingConfig(chunk_size_words=300, chunk_overlap_words=50, source_type="txt")

    results: list[VariantResult] = []
    transitions: list[CaseTransition] = []
    try:
        with session_factory() as db:
            organisation = Organisation(name="Evidence Sufficiency Bakeoff", slug=f"evidence-sufficiency-bakeoff-{corpus}-{os.getpid()}", status="active", plan_key="starter")
            workspace = Workspace(organisation=organisation, name="Workspace", slug="workspace", status="active", default_language="en")
            user = User(email="evidence-sufficiency-bakeoff@example.test", full_name="Bakeoff")
            membership = Membership(organisation=organisation, user=user, role="org_owner", status="active")
            db.add_all([organisation, workspace, user, membership])
            db.commit()

            loaded = seed_golden_dataset(
                db, organisation=organisation, workspace=workspace, embedding_provider=cached_provider, actor_user_id=user.id,
                fixture=fixture, chunking_strategy=structure_aware_strategy, chunking_config=chunking_config,
            )
            cases = evaluation_repository.list_cases_for_dataset(db, dataset_id=loaded.dataset.id)

            for variant in variants:
                started_at = time.perf_counter()
                run = run_evaluation(
                    db, dataset=loaded.dataset, organisation_id=organisation.id, workspace_id=workspace.id, widget_id=loaded.widget_id,
                    options=EvaluationRunOptions(
                        mode="mock",
                        policy=load_policy_from_env(),
                        shadow_database_url=database_url,
                        embedding_provider=cached_provider,
                        min_similarity_score=min_similarity_score,
                        case_timeout_seconds=180.0 if corpus == "chunking" else 60.0,
                        retrieval_strategy_override=DENSE_ONLY_STRATEGY,
                        reranker_override=no_reranker,
                        query_transformer_override=identity_transformer,
                        evidence_verifier_override=variant.verifier,
                    ),
                )
                run_seconds = time.perf_counter() - started_at
                summary = build_run_summary(db, run_id=run.id)
                gate = evaluate_gate(summary, policy=load_policy_from_env(), run_status=run.status)

                results.append(
                    VariantResult(
                        label=variant.label,
                        evidence_verifier_version=variant.verifier.version,
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
                        average_precision_at_k=summary.average_precision_at_k,
                        latency_p50_ms=summary.latency_p50_ms,
                        latency_p95_ms=summary.latency_p95_ms,
                        total_tokens=summary.total_tokens,
                        gate_passed=gate.passed,
                        gate_reasons=list(gate.reasons),
                        failure_reason_counts=_failure_reason_counts(db, run_id=run.id),
                        category_pass_rate=_category_pass_rates(db, run_id=run.id),
                        run_seconds=run_seconds,
                    )
                )

            # Part 9 case-level transition table: direct verifier calls (not
            # run_evaluation - EvaluationResult does not persist a guardrail
            # reason_code, and this task does not ask for that schema
            # change), reusing the exact retrieval assemble_retrieval_context
            # call the orchestrator itself makes, for every answerable case
            # whose expected document(s) are actually in Top-K.
            for case in cases:
                if not case.expected_document_ids or case.expected_answerability != "answerable":
                    continue
                query_plan = transform_query(identity_transformer, query=case.question)
                retrieval = assemble_retrieval_context(
                    db, organisation_id=organisation.id, workspace_id=workspace.id, query=case.question,
                    search_limit=settings.RETRIEVAL_MAX_CONTEXT_CHUNKS, max_context_chunks=settings.RETRIEVAL_MAX_CONTEXT_CHUNKS,
                    max_context_chars=settings.RETRIEVAL_MAX_CONTEXT_CHARS, provider=cached_provider, document_ids=None,
                    min_similarity_score=min_similarity_score, retrieval_strategy=DENSE_ONLY_STRATEGY, reranker=no_reranker,
                    query_plan=query_plan,
                )
                retrieved_document_ids = {block.document_id for block in retrieval.context_blocks}
                if not retrieved_document_ids & set(case.expected_document_ids):
                    continue
                contents = [block.content for block in retrieval.context_blocks]
                titles = [block.source_title for block in retrieval.context_blocks]
                scores = [block.score for block in retrieval.context_blocks]
                v1_verdict = verify_evidence_sufficiency(question=case.question, chunk_contents=contents, chunk_titles=titles, retrieval_scores=scores)
                v2_verdict = verify_evidence_sufficiency_v2(question=case.question, chunk_contents=contents, chunk_titles=titles, retrieval_scores=scores)
                if v1_verdict.sufficient == v2_verdict.sufficient:
                    change = "unchanged_pass" if v1_verdict.sufficient else "unchanged_fail"
                elif v2_verdict.sufficient:
                    change = "fixed"
                else:
                    change = "newly_broken"
                transitions.append(
                    CaseTransition(
                        case_id=case.id, question=case.question, category=case.category, tags=list(case.tags or []),
                        v1_sufficient=v1_verdict.sufficient, v1_reason_code=v1_verdict.reason_code.value,
                        v2_sufficient=v2_verdict.sufficient, v2_reason_code=v2_verdict.reason_code.value,
                        change=change,
                    )
                )
    finally:
        engine.dispose()
        if temp_db_path.exists() and not keep_db:
            temp_db_path.unlink()
    return results, transitions


def _print_text_report(all_results: dict[str, list[VariantResult]], all_transitions: dict[str, list[CaseTransition]], *, embedding_provider: EmbeddingProvider, min_similarity_score: float) -> None:
    print(f"Evidence Sufficiency V2 - V1 vs V2 bake-off - embedding provider: {embedding_provider.provider_name}/{embedding_provider.model_name} - min_similarity_score: {min_similarity_score}")
    print()
    for corpus, results in all_results.items():
        print(f"=== corpus: {corpus} ===")
        header = f"{'variant':8s} {'pass_rate':>9s} {'hard_fail':>9s} {'hit_rate':>9s} {'citation':>9s} {'fallback':>9s} {'p50/p95 ms':>12s} {'tokens':>8s} {'run_s':>7s} {'gate':>7s}"
        print(header)
        for r in results:
            hit_rate = f"{r.retrieval_hit_rate:.1%}" if r.retrieval_hit_rate is not None else "n/a"
            citation = f"{r.citation_coverage:.1%}" if r.citation_coverage is not None else "n/a"
            fallback = f"{r.fallback_rate_on_answerable:.1%}" if r.fallback_rate_on_answerable is not None else "n/a"
            latency = f"{r.latency_p50_ms or 0}/{r.latency_p95_ms or 0}"
            print(
                f"{r.label:8s} {r.pass_rate:8.1%} {r.hard_failure_cases:9d} {hit_rate:>9s} {citation:>9s} {fallback:>9s} "
                f"{latency:>12s} {r.total_tokens:8d} {r.run_seconds:7.1f} {'PASS' if r.gate_passed else 'FAIL':>7s}"
            )
            print(f"    category_pass_rate: {{{', '.join(f'{k}: {v:.0%}' for k, v in sorted(r.category_pass_rate.items()))}}}")
            print(f"    failure_reason_counts: {r.failure_reason_counts}")

        if len(results) == 2:
            v1, v2 = results
            print(f"  --- v2 vs v1 ---")
            print(f"  pass_rate delta: {v2.pass_rate - v1.pass_rate:+.1%}   hard_failure delta: {v2.hard_failure_cases - v1.hard_failure_cases:+d}")
            citation_delta = None if v1.citation_coverage is None or v2.citation_coverage is None else v2.citation_coverage - v1.citation_coverage
            print(f"  citation_coverage delta: {'n/a' if citation_delta is None else f'{citation_delta:+.1%}'}")

        transitions = all_transitions.get(corpus, [])
        fixed = [t for t in transitions if t.change == "fixed"]
        broken = [t for t in transitions if t.change == "newly_broken"]
        print(f"  evidence-present-but-rejected candidates analysed: {len(transitions)}")
        print(f"  FIXED by V2: {len(fixed)}   NEWLY BROKEN by V2: {len(broken)}")
        for t in fixed:
            print(f"    [FIXED] {t.question!r} ({t.category}, {t.tags}) v1={t.v1_reason_code} -> v2={t.v2_reason_code}")
        for t in broken:
            print(f"    [NEWLY BROKEN] {t.question!r} ({t.category}, {t.tags}) v1={t.v1_reason_code} -> v2={t.v2_reason_code}")
        print()


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    embedding_provider, min_similarity_score = _build_embedding_provider(use_real=args.real)
    corpora = ["golden", "chunking"] if args.corpus == "both" else [args.corpus]

    all_results: dict[str, list[VariantResult]] = {}
    all_transitions: dict[str, list[CaseTransition]] = {}
    for corpus in corpora:
        results, transitions = _run_bakeoff_for_corpus(corpus=corpus, embedding_provider=embedding_provider, min_similarity_score=min_similarity_score, keep_db=args.keep_db)
        all_results[corpus] = results
        all_transitions[corpus] = transitions

    if args.format == "json":
        print(json.dumps({
            "embedding_provider": {"provider": embedding_provider.provider_name, "model": embedding_provider.model_name},
            "min_similarity_score": min_similarity_score,
            "results": {corpus: [asdict(r) for r in results] for corpus, results in all_results.items()},
            "transitions": {corpus: [asdict(t) for t in transitions] for corpus, transitions in all_transitions.items()},
        }, indent=2, default=str))
    else:
        _print_text_report(all_results, all_transitions, embedding_provider=embedding_provider, min_similarity_score=min_similarity_score)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
