"""CLI: Evidence Sufficiency V2, Part 1/2 - failure taxonomy and baseline
false-rejection measurement.

Retrieval V2 (docs/adr/0031-0033) concluded that hybrid_rrf, reranking, and
deterministic query rewriting do not materially improve the real corpora, and
that the chunking-focused corpus now has many answerable failures where the
expected evidence already exists in the retrieved Top-K. This script proves
(rather than assumes) where those remaining failures actually originate: it
runs the SAME retrieval this project already validated (structure_aware
chunking, dense_only, nomic-embed-text-v2-moe, threshold 0.32 - ADR-0032) and
isolates the cases where retrieval already surfaced the expected document(s)
but `app.ai.guardrails.evidence_sufficiency.verify_evidence_sufficiency`
still rejected the case - then classifies each rejection into a concrete
category by inspecting the actual retrieved chunk content, the exact
`ChunkSupportOutcome`s the verifier produced, and the case's own
author-supplied ground truth (category/tags/notes) - never by assumption.

    python -m app.operations.eval_evidence_sufficiency_failure_analysis [--format text|json] [--real] [--keep-db] [--corpus golden|chunking|both]

Mock mode (default): deterministic, credential-free - proves the mechanics
end-to-end, but LocalMockEmbeddingProvider has no semantic content, so
"expected evidence ranks in Top-K" almost never legitimately happens against
it - use --real for an actionable classification.

`--real`: uses EVAL_EMBEDDING_PROVIDER/EVAL_EMBEDDING_MODEL (must already be
set, e.g. ollama/nomic-embed-text-v2-moe) and this project's calibrated
RETRIEVAL_MIN_SIMILARITY_SCORE for that model (0.32 for
nomic-embed-text-v2-moe, docs/adr/0032). Retrieval strategy is pinned to
dense_only with reranking disabled and the query transformer pinned to
identity throughout, matching every other Retrieval V2 bake-off script and
this task's explicit "do not change retrieval strategy" instruction.
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

from app.ai.guardrails.evidence_sufficiency import verify_evidence_sufficiency
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
from app.evaluation.fixtures.loader import load_chunking_fixture_definition, seed_golden_dataset
from app.repositories import evaluation_repository
from app.services.chunking_strategies import ChunkingConfig, build_chunking_strategy
from app.services.embeddings import EmbeddingProvider, EmbeddingProviderError, build_embedding_provider
from app.services.query_transformation import IdentityQueryTransformer, transform_query
from app.services.reranking import NO_RERANKER_PROVIDER, build_reranker
from app.services.retrieval_context import DENSE_ONLY_STRATEGY, assemble_retrieval_context

# Content-inspection vocabularies used only to CLASSIFY an already-observed
# rejection (never to decide sufficiency itself - that stays
# evidence_sufficiency.py's exclusive job). Kept as fixed, narrow, reviewable
# lists rather than a broad keyword net, per this task's "do not create a
# giant permissive keyword list" instruction.
_NEGATION_WORDS = re.compile(r"(?i)\b(not|cannot|can't|no longer|never|except|unless|excluding|without|forfeit|ineligible|does not|is not|are not|were not)\b")
_SUPERSESSION_WORDS = re.compile(r"(?i)\b(supersedes?|superseded|replaces?|replaced|no longer (issued|valid|current)|deprecated|previous(ly)?|as of|until|starting)\b")
_SCOPE_WORDS = re.compile(
    r"(?i)\b(starter|team|business|enterprise|standard|professional|frankfurt|virginia|monthly|annual|eu|european union|severity 1|severity 2|severity 3)\b"
)

# Tags the golden/chunking fixtures already author onto cases as ground truth
# about WHY a case is hard (see chunking_dataset.json's "tags"/"notes" -
# "heading-dependent", "paraphrase", "boundary", "cross-section", "edge-case")
# - reused here as real signal instead of re-deriving a guess.
_TAG_TO_CATEGORY = {
    "heading-dependent": "heading_context_loss",
    "paraphrase": "paraphrase_mismatch",
    "cross-section": "multi_chunk_evidence_requirement",
}


@dataclass
class CaseAnalysis:
    case_id: str
    question: str
    category: str
    tags: list[str]
    expected_document_ids: list[str]
    retrieved_document_ids: list[str]
    hit_at_k: bool
    recall_at_k: float | None
    citation_required: bool
    sufficient: bool
    reason_code: str
    chunk_outcomes: list[str]
    requested_entities: list[str]
    requested_attribute_type: str | None
    taxonomy_category: str


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Evidence Sufficiency V2 Part 1/2 - failure taxonomy and false-rejection baseline.")
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
            raise SystemExit(f"Cannot run a real-embedding failure analysis: {exc}") from exc
        recommended = recommended_min_similarity_score(load_eval_embedding_config_from_env())
        min_similarity_score = recommended if recommended is not None else settings.RETRIEVAL_MIN_SIMILARITY_SCORE
        return provider, min_similarity_score
    return build_embedding_provider(provider_name="local-mock", model_name="evidence-sufficiency-failure-analysis", dimension=8), settings.RETRIEVAL_MIN_SIMILARITY_SCORE


def _classify_taxonomy(*, case, chunk_contents: list[str], recall_at_k: float | None, verdict) -> str:
    """Deterministic, evidence-based classification - never guesses a
    category the verdict/content/ground truth doesn't actually support (this
    task's Part 1 requirement). Every branch below is anchored to one of:
    the verifier's own reason_code/chunk_outcomes, the case's
    author-supplied tags/category (real ground truth, not inferred), or a
    narrow, reviewable content scan for negation/supersession/scope wording
    in the actual retrieved text."""
    if verdict.sufficient:
        return "sufficient_pass"

    combined_text = " ".join(chunk_contents)
    tags = set((case.tags or []))

    if verdict.reason_code.value == "conflicting_evidence":
        if _SUPERSESSION_WORDS.search(combined_text):
            return "superseded_evidence"
        if _SCOPE_WORDS.search(combined_text):
            return "different_scopes_not_conflict"
        return "genuine_conflicting_evidence"

    if verdict.reason_code.value == "related_topic_only":
        # hit_at_k true (this function is only called for such cases) means
        # retrieval already cleared RETRIEVAL_MIN_SIMILARITY_SCORE (0.32) for
        # the expected document, which sits above the off-topic threshold
        # (0.30) - so this combination should be structurally near-impossible
        # and is worth flagging distinctly rather than folding into the
        # generic bucket below.
        return "off_topic_misclassification_despite_hit"

    if case.category == "ambiguous" or "clarification-needed" in tags:
        return "ambiguity_requiring_clarification"

    if verdict.reason_code.value == "requested_fact_absent":
        if "heading-dependent" in tags:
            return "heading_context_loss"
        if case.category == "multi_document" or (recall_at_k is not None and 0.0 < recall_at_k < 1.0):
            return "multi_chunk_evidence_requirement"

        outcomes = set(verdict.chunk_outcomes)
        attribute_type = verdict.requested_fact.attribute_type.value if verdict.requested_fact.attribute_type else None

        if "value_missing" in outcomes:
            if _NEGATION_WORDS.search(combined_text):
                return "negation_handling_gap"
            if attribute_type == "numeric":
                return "numeric_extraction_gap"
            if attribute_type in {"currency", "percentage"}:
                return "currency_percentage_interpretation_gap"
            if attribute_type in {"date", "duration"}:
                return "duration_date_interpretation_gap"
            if attribute_type in {"eligibility", "policy_condition"}:
                return "eligibility_condition_logic_gap"
            if attribute_type == "product":
                return "attribute_value_type_mismatch"
            return "value_extraction_gap"

        if "nearby_but_incomplete" in outcomes:
            return "relationship_proximity_failure"

        if "paraphrase" in tags:
            return "paraphrase_mismatch"

        if "topic_match_only" in outcomes:
            return "entity_mismatch"

        if "insufficient_evidence" in outcomes and not verdict.requested_fact.entities:
            return "paraphrase_mismatch"

        return "unclassified_requested_fact_absent"

    return f"unclassified_{verdict.reason_code.value}"


def _run_analysis(*, use_real: bool, corpus: str, keep_db: bool) -> tuple[list[CaseAnalysis], EmbeddingProvider, float]:
    embedding_provider, min_similarity_score = _build_embedding_provider(use_real=use_real)
    cached_provider = CachingEmbeddingProvider(embedding_provider)
    identity_transformer = IdentityQueryTransformer()
    no_reranker = build_reranker(provider_name=NO_RERANKER_PROVIDER)
    structure_aware_strategy = build_chunking_strategy("structure_aware", embedding_provider=None)

    corpora = ["golden", "chunking"] if corpus == "both" else [corpus]
    all_analyses: list[CaseAnalysis] = []

    for one_corpus in corpora:
        temp_db_path = Path(tempfile.gettempdir()) / f"conversa-evidence-sufficiency-failure-analysis-{one_corpus}-{os.getpid()}.db"
        database_url = f"sqlite:///{temp_db_path}"
        engine = create_engine(database_url, connect_args={"check_same_thread": False})
        Base.metadata.create_all(engine)
        session_factory = sessionmaker(bind=engine)

        if one_corpus == "chunking":
            fixture = load_chunking_fixture_definition()
            chunking_config = ChunkingConfig(chunk_size_words=120, chunk_overlap_words=25, min_chunk_size_words=30, max_chunk_size_words=200, source_type="txt")
        else:
            fixture = None
            chunking_config = ChunkingConfig(chunk_size_words=300, chunk_overlap_words=50, source_type="txt")

        try:
            with session_factory() as db:
                organisation = Organisation(name="Evidence Sufficiency Failure Analysis", slug=f"evidence-sufficiency-failure-{one_corpus}-{os.getpid()}", status="active", plan_key="starter")
                workspace = Workspace(organisation=organisation, name="Workspace", slug="workspace", status="active", default_language="en")
                user = User(email="evidence-sufficiency-failure-analysis@example.test", full_name="Analysis")
                membership = Membership(organisation=organisation, user=user, role="org_owner", status="active")
                db.add_all([organisation, workspace, user, membership])
                db.commit()

                loaded = seed_golden_dataset(
                    db, organisation=organisation, workspace=workspace, embedding_provider=cached_provider, actor_user_id=user.id,
                    fixture=fixture, chunking_strategy=structure_aware_strategy, chunking_config=chunking_config,
                )
                cases = evaluation_repository.list_cases_for_dataset(db, dataset_id=loaded.dataset.id)

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
                    retrieved_document_ids = [block.document_id for block in retrieval.context_blocks]
                    expected = set(case.expected_document_ids)
                    overlap = [doc_id for doc_id in retrieved_document_ids if doc_id in expected]
                    hit_at_k = len(overlap) > 0
                    recall_at_k = len(set(overlap)) / len(expected) if expected else None

                    if not hit_at_k:
                        continue  # Part 1 scope: evidence already in Top-K, not a retrieval-recall failure (that's Retrieval V2's territory)

                    verdict = verify_evidence_sufficiency(
                        question=case.question,
                        chunk_contents=[block.content for block in retrieval.context_blocks],
                        chunk_titles=[block.source_title for block in retrieval.context_blocks],
                        retrieval_scores=[block.score for block in retrieval.context_blocks],
                    )
                    taxonomy_category = _classify_taxonomy(
                        case=case, chunk_contents=[block.content for block in retrieval.context_blocks], recall_at_k=recall_at_k, verdict=verdict,
                    )

                    all_analyses.append(
                        CaseAnalysis(
                            case_id=case.id,
                            question=case.question,
                            category=case.category,
                            tags=list(case.tags or []),
                            expected_document_ids=list(case.expected_document_ids),
                            retrieved_document_ids=retrieved_document_ids,
                            hit_at_k=hit_at_k,
                            recall_at_k=round(recall_at_k, 3) if recall_at_k is not None else None,
                            citation_required=bool((case.metadata_json or {}).get("citation_required")),
                            sufficient=verdict.sufficient,
                            reason_code=verdict.reason_code.value,
                            chunk_outcomes=list(verdict.chunk_outcomes),
                            requested_entities=list(verdict.requested_fact.entities),
                            requested_attribute_type=verdict.requested_fact.attribute_type.value if verdict.requested_fact.attribute_type else None,
                            taxonomy_category=taxonomy_category,
                        )
                    )
        finally:
            engine.dispose()
            if temp_db_path.exists() and not keep_db:
                temp_db_path.unlink()

    return all_analyses, embedding_provider, min_similarity_score


def _print_text_report(analyses: list[CaseAnalysis], *, corpus: str, embedding_provider: EmbeddingProvider, min_similarity_score: float) -> None:
    print(f"Evidence Sufficiency V2 - failure taxonomy - corpus: {corpus} - embedding provider: {embedding_provider.provider_name}/{embedding_provider.model_name} - min_similarity_score: {min_similarity_score}")
    print()
    evidence_present = len(analyses)
    rejected = [a for a in analyses if not a.sufficient]
    print(f"Answerable cases where expected evidence IS in retrieved Top-K: {evidence_present}")
    print(f"  of those, REJECTED by evidence sufficiency (false-rejection candidates): {len(rejected)}")
    if evidence_present:
        print(f"  evidence-present-but-rejected rate: {len(rejected) / evidence_present:.1%}")
    print()

    taxonomy_counts = Counter(a.taxonomy_category for a in rejected)
    print("Taxonomy breakdown of rejected cases:")
    for label, count in taxonomy_counts.most_common():
        print(f"  {label}: {count}")
    print()

    reason_counts = Counter(a.reason_code for a in rejected)
    print("Reason-code breakdown of rejected cases:")
    for label, count in reason_counts.most_common():
        print(f"  {label}: {count}")
    print()

    for a in rejected:
        print(f"[{a.case_id[:8]}] ({a.taxonomy_category} / {a.reason_code}, category={a.category}, tags={a.tags}, recall_at_k={a.recall_at_k}) {a.question!r}")
        print(f"    requested: entities={a.requested_entities} attribute_type={a.requested_attribute_type} chunk_outcomes={a.chunk_outcomes}")


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    analyses, embedding_provider, min_similarity_score = _run_analysis(use_real=args.real, corpus=args.corpus, keep_db=args.keep_db)

    if args.format == "json":
        print(json.dumps({
            "corpus": args.corpus,
            "embedding_provider": {"provider": embedding_provider.provider_name, "model": embedding_provider.model_name},
            "min_similarity_score": min_similarity_score,
            "cases": [asdict(a) for a in analyses],
        }, indent=2, default=str))
    else:
        _print_text_report(analyses, corpus=args.corpus, embedding_provider=embedding_provider, min_similarity_score=min_similarity_score)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
