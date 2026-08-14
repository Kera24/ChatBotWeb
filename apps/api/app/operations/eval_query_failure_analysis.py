"""CLI: Retrieval V2 Phase 3, Part 1 - failure analysis FIRST, before
implementing any query transformation. Runs the existing evaluation
framework (dense_only + identity transformer - today's exact production
baseline) against a corpus, then classifies every answerable_factual case
where retrieval did not surface the expected evidence, by inspecting the
actual retrieval candidates (not by assumption) for lexical-mismatch signals:
terminology mismatch, acronym/abbreviation mismatch, conversational-vs-formal
wording, and canonical-term absence.

Does NOT assume query rewriting will help - this only classifies WHY the
baseline failed, using deterministic, inspectable heuristics over the real
question text and the real expected-document content. The mechanism labels
this script assigns are signals for later manual/case-level review, not a
guarantee that any given case is fixable by query transformation.

    python -m app.operations.eval_query_failure_analysis [--format text|json] [--real] [--keep-db] [--corpus golden|chunking] [--wide-pool-size 50]

Mock mode (default): deterministic, credential-free - proves the mechanics
end-to-end, but LocalMockEmbeddingProvider has no semantic content, so
"expected evidence ranks poorly" vs. "absent entirely" is not a meaningful
signal against it - use --real for an actionable classification.

`--real`: uses EVAL_EMBEDDING_PROVIDER/EVAL_EMBEDDING_MODEL (must already be
set, e.g. ollama/nomic-embed-text-v2-moe) and this project's calibrated
RETRIEVAL_MIN_SIMILARITY_SCORE for that model (0.32 for
nomic-embed-text-v2-moe, docs/adr/0032).
"""

from __future__ import annotations

import argparse
import json
import os
import re
import tempfile
from collections import Counter
from dataclasses import asdict, dataclass, field
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.config import settings
from app.db.base import Base
from app.db import models  # noqa: F401 - import registers every model with Base.metadata
from app.db.models import Chunk, Membership, Organisation, User, Workspace
from app.evaluation.embedding_cache import CachingEmbeddingProvider
from app.evaluation.embedding_config import (
    build_real_eval_embedding_provider,
    load_eval_embedding_config_from_env,
    recommended_min_similarity_score,
)
from app.evaluation.engine import EvaluationRunOptions, run_evaluation
from app.evaluation.fixtures.loader import load_chunking_fixture_definition, seed_golden_dataset
from app.repositories import evaluation_repository
from app.services.chunking_strategies import ChunkingConfig, build_chunking_strategy
from app.services.embeddings import EmbeddingProvider, EmbeddingProviderError, build_embedding_provider
from app.services.vector_search import search_embedded_chunks

# Reproduced here rather than imported from app.services.query_transformation
# deliberately - this analysis must classify the ORIGINAL question's wording
# independent of whatever the transformer's own normalization does, so it
# stays a fixed reference vocabulary even if the transformer's list evolves.
_CONVERSATIONAL_PREFIXES = [
    r"^can you (please )?tell me\s+",
    r"^could you (please )?(explain|tell me)\s+",
    r"^i (want|need|would like) to know\s+",
    r"^i'?m (trying to find out|wondering)\s+",
    r"^do you know\s+",
    r"^please (tell me|explain)\s+",
    r"^what about\s+",
    r"^how do i\s+",
]
_ACRONYM_PATTERN = re.compile(r"\b[A-Z]{2,6}\b")
_STOPWORDS = {
    "a", "an", "the", "is", "are", "was", "were", "do", "does", "did", "of", "for", "to", "in", "on",
    "and", "or", "what", "when", "how", "many", "much", "can", "could", "i", "you", "me", "my", "it",
    "this", "that", "with", "at", "be", "if", "not", "no", "yes",
}


@dataclass
class CaseAnalysis:
    case_id: str
    question: str
    category: str
    expected_document_ids: list[str]
    passed: bool
    hit_at_k: bool | None
    retrieval_status: str  # "hit" | "absent_from_wide_pool" | "below_similarity_threshold" | "ranks_poorly" | "no_expected_documents"
    best_rank_in_wide_pool: int | None
    final_top_k: int
    token_overlap_ratio: float | None
    mechanism_signals: list[str] = field(default_factory=list)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Retrieval V2 Phase 3 Part 1 - baseline dense_only failure classification.")
    parser.add_argument("--format", default="text", choices=["text", "json"], help="Report output format.")
    parser.add_argument("--real", action="store_true", help="Use EVAL_EMBEDDING_PROVIDER/MODEL (a real embedding runtime) instead of the deterministic mock.")
    parser.add_argument("--keep-db", action="store_true", help="Do not delete the temp SQLite file afterwards.")
    parser.add_argument(
        "--corpus", default="chunking", choices=["golden", "chunking"],
        help="'chunking' (default): chunking_dataset.json, the corpus purpose-built to exercise the retrieval-recall gap (104 cases). "
        "'golden': golden_dataset.json, the general launch/regression corpus.",
    )
    parser.add_argument("--wide-pool-size", type=int, default=50, help="Dense candidate pool size used to distinguish 'absent' from 'ranks poorly'.")
    return parser.parse_args(argv)


def _build_embedding_provider(*, use_real: bool) -> tuple[EmbeddingProvider, float]:
    if use_real:
        try:
            provider = build_real_eval_embedding_provider()
        except EmbeddingProviderError as exc:
            raise SystemExit(f"Cannot run a real-embedding failure analysis: {exc}") from exc
        recommended = recommended_min_similarity_score(load_eval_embedding_config_from_env())
        min_similarity_score = recommended if recommended is not None else settings.RETRIEVAL_MIN_SIMILARITY_SCORE
        return provider, min_similarity_score
    return build_embedding_provider(provider_name="local-mock", model_name="query-failure-analysis", dimension=8), settings.RETRIEVAL_MIN_SIMILARITY_SCORE


def _tokenize(text: str) -> set[str]:
    return {token for token in re.findall(r"[a-z0-9]+", text.lower()) if token not in _STOPWORDS and len(token) > 1}


def _is_conversational(question: str) -> bool:
    return any(re.match(pattern, question, flags=re.IGNORECASE) for pattern in _CONVERSATIONAL_PREFIXES)


def _classify_mechanism(*, question: str, expected_content: str, token_overlap_ratio: float) -> list[str]:
    signals: list[str] = []
    if _is_conversational(question):
        signals.append("conversational_wording")
    if token_overlap_ratio < 0.35:
        signals.append("low_lexical_overlap")

    question_acronyms = set(_ACRONYM_PATTERN.findall(question))
    content_acronyms = set(_ACRONYM_PATTERN.findall(expected_content))
    if content_acronyms - question_acronyms:
        signals.append("acronym_or_abbreviation_in_source_absent_from_question")
    if question_acronyms - content_acronyms:
        signals.append("acronym_or_abbreviation_in_question_absent_from_source")

    # A "canonical term" heuristic: a capitalised multi-word phrase (Title
    # Case bigram/trigram) that appears in the source but not in the
    # question at all - a proxy for a formal product/policy name the
    # question never uses.
    canonical_phrases = re.findall(r"\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,2})\b", expected_content)
    question_lower = question.lower()
    if any(phrase.lower() not in question_lower for phrase in canonical_phrases):
        signals.append("canonical_term_absent_from_question")

    if not signals and token_overlap_ratio < 0.6:
        signals.append("unclassified_lexical_mismatch")
    return signals


def _run_failure_analysis(*, use_real: bool, corpus: str, keep_db: bool, wide_pool_size: int) -> list[CaseAnalysis]:
    temp_db_path = Path(tempfile.gettempdir()) / f"conversa-query-failure-analysis-{corpus}-{os.getpid()}.db"
    database_url = f"sqlite:///{temp_db_path}"
    engine = create_engine(database_url, connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine)

    embedding_provider, min_similarity_score = _build_embedding_provider(use_real=use_real)
    cached_provider = CachingEmbeddingProvider(embedding_provider)

    structure_aware_strategy = build_chunking_strategy("structure_aware", embedding_provider=None)
    if corpus == "chunking":
        fixture = load_chunking_fixture_definition()
        chunking_config = ChunkingConfig(chunk_size_words=120, chunk_overlap_words=25, min_chunk_size_words=30, max_chunk_size_words=200, source_type="txt")
    else:
        fixture = None
        chunking_config = ChunkingConfig(chunk_size_words=300, chunk_overlap_words=50, source_type="txt")

    analyses: list[CaseAnalysis] = []
    try:
        with session_factory() as db:
            organisation = Organisation(name="Query Failure Analysis", slug=f"query-failure-{corpus}-{os.getpid()}", status="active", plan_key="starter")
            workspace = Workspace(organisation=organisation, name="Workspace", slug="workspace", status="active", default_language="en")
            user = User(email="query-failure-analysis@example.test", full_name="Analysis")
            membership = Membership(organisation=organisation, user=user, role="org_owner", status="active")
            db.add_all([organisation, workspace, user, membership])
            db.commit()

            loaded = seed_golden_dataset(
                db, organisation=organisation, workspace=workspace, embedding_provider=cached_provider, actor_user_id=user.id,
                fixture=fixture, chunking_strategy=structure_aware_strategy, chunking_config=chunking_config,
            )

            run = run_evaluation(
                db, dataset=loaded.dataset, organisation_id=organisation.id, workspace_id=workspace.id, widget_id=loaded.widget_id,
                options=EvaluationRunOptions(
                    mode="mock",
                    shadow_database_url=database_url,
                    embedding_provider=cached_provider,
                    min_similarity_score=min_similarity_score,
                    case_timeout_seconds=180.0 if corpus == "chunking" else 60.0,
                ),
            )

            results_by_case_id = {result.case_id: result for result in evaluation_repository.list_results_for_run(db, run_id=run.id)}
            cases = evaluation_repository.list_cases_for_dataset(db, dataset_id=loaded.dataset.id)

            for case in cases:
                if not case.expected_document_ids or case.expected_answerability != "answerable":
                    continue
                result = results_by_case_id.get(case.id)
                if result is None:
                    continue
                retrieval_metrics = result.retrieval_metrics_json or {}
                hit_at_k = retrieval_metrics.get("hit_at_k")
                if hit_at_k:
                    continue  # not a failure case Phase 3 is meant to address

                # min_similarity_score=0.0 here is deliberate (Part 1: distinguish
                # "absent" from "ranks poorly"), but that means this pool is a
                # SUPERSET of what the real, threshold-gated evaluation run
                # actually searched - a candidate can rank highly here purely
                # because nothing else scored higher, while still sitting below
                # the calibrated min_similarity_score that would have excluded
                # it from the real run entirely (exactly ADR-0032's "a
                # similarity floor can only exclude matches, never promote a
                # low-ranked correct one higher" mechanism). Rank alone is
                # therefore not sufficient to call a case a "hit" - the
                # candidate's actual score must also clear the same threshold
                # the real run enforced, or this would silently misclassify
                # every threshold-excluded case as "cleared retrieval".
                wide_matches = search_embedded_chunks(
                    db, organisation_id=organisation.id, workspace_id=workspace.id, query=case.question,
                    limit=wide_pool_size, provider=cached_provider, document_ids=None, min_similarity_score=0.0,
                )
                expected_ids = set(case.expected_document_ids)
                best_rank = None
                best_score = None
                for rank, match in enumerate(wide_matches, start=1):
                    if match.document_id in expected_ids:
                        best_rank = rank
                        best_score = match.score
                        break

                final_top_k = settings.RETRIEVAL_MAX_CONTEXT_CHUNKS
                if best_rank is None:
                    retrieval_status = "absent_from_wide_pool"
                elif best_score is not None and best_score < min_similarity_score:
                    retrieval_status = "below_similarity_threshold"
                elif best_rank > final_top_k:
                    retrieval_status = "ranks_poorly"
                else:
                    retrieval_status = "hit"  # cleared retrieval; failure came from elsewhere (guardrail/generation), out of Phase 3 scope

                expected_content = " ".join(
                    match.content for match in wide_matches if match.document_id in expected_ids
                )
                question_tokens = _tokenize(case.question)
                content_tokens = _tokenize(expected_content)
                token_overlap_ratio = (
                    len(question_tokens & content_tokens) / len(question_tokens) if question_tokens and expected_content else 0.0
                )

                mechanism_signals: list[str] = []
                if retrieval_status in {"absent_from_wide_pool", "below_similarity_threshold", "ranks_poorly"}:
                    mechanism_signals = _classify_mechanism(
                        question=case.question, expected_content=expected_content, token_overlap_ratio=token_overlap_ratio,
                    )

                analyses.append(
                    CaseAnalysis(
                        case_id=case.id,
                        question=case.question,
                        category=case.category,
                        expected_document_ids=list(case.expected_document_ids),
                        passed=bool(result.passed),
                        hit_at_k=hit_at_k,
                        retrieval_status=retrieval_status,
                        best_rank_in_wide_pool=best_rank,
                        final_top_k=final_top_k,
                        token_overlap_ratio=round(token_overlap_ratio, 3) if expected_content else None,
                        mechanism_signals=mechanism_signals,
                    )
                )
    finally:
        engine.dispose()
        if temp_db_path.exists() and not keep_db:
            temp_db_path.unlink()
    return analyses


def _print_text_report(analyses: list[CaseAnalysis], *, corpus: str, embedding_provider: EmbeddingProvider) -> None:
    print(f"Retrieval V2 Phase 3 Part 1 - baseline dense_only failure analysis - corpus: {corpus} - embedding provider: {embedding_provider.provider_name}/{embedding_provider.model_name}")
    print()
    addressable = [a for a in analyses if a.retrieval_status in {"absent_from_wide_pool", "below_similarity_threshold", "ranks_poorly"}]
    print(f"Total answerable_factual retrieval failures: {len(analyses)}")
    print(f"  absent_from_wide_pool:       {sum(1 for a in analyses if a.retrieval_status == 'absent_from_wide_pool')}")
    print(f"  below_similarity_threshold: {sum(1 for a in analyses if a.retrieval_status == 'below_similarity_threshold')}")
    print(f"  ranks_poorly:                {sum(1 for a in analyses if a.retrieval_status == 'ranks_poorly')}")
    print(f"  hit (non-retrieval failure, out of Phase 3 scope): {sum(1 for a in analyses if a.retrieval_status == 'hit')}")
    print()
    mechanism_counts = Counter(signal for a in addressable for signal in a.mechanism_signals)
    print("Mechanism signal counts (a case may carry more than one signal):")
    for signal, count in mechanism_counts.most_common():
        print(f"  {signal}: {count}")
    print()
    print(f"Baseline cases Phase 3 is intended to address (retrieval failure + at least one mechanism signal): {sum(1 for a in addressable if a.mechanism_signals)}")
    print()
    for analysis in addressable:
        print(f"[{analysis.case_id[:8]}] ({analysis.retrieval_status}, best_rank={analysis.best_rank_in_wide_pool}, overlap={analysis.token_overlap_ratio}) {analysis.question!r}")
        print(f"    signals: {', '.join(analysis.mechanism_signals) or 'none'}")


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    embedding_provider, _min_similarity_score = _build_embedding_provider(use_real=args.real)
    analyses = _run_failure_analysis(use_real=args.real, corpus=args.corpus, keep_db=args.keep_db, wide_pool_size=args.wide_pool_size)

    if args.format == "json":
        print(json.dumps({
            "corpus": args.corpus,
            "embedding_provider": {"provider": embedding_provider.provider_name, "model": embedding_provider.model_name},
            "cases": [asdict(a) for a in analyses],
        }, indent=2, default=str))
    else:
        _print_text_report(analyses, corpus=args.corpus, embedding_provider=embedding_provider)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
