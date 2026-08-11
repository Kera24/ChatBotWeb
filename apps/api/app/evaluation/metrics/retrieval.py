"""Deterministic retrieval metrics.

Every function here is pure and only compares dataset-declared expectations
against what the real RAG orchestrator actually retrieved for a case. None of
these fabricate a relevance judgement beyond what the dataset author supplied
- a case with no `expected_document_ids`/`expected_source_labels` simply
produces `None` for the metrics that would require them.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class RetrievalMetrics:
    retrieved_chunk_count: int
    hit_at_k: bool | None
    recall_at_k: float | None
    precision_at_k: float | None
    reciprocal_rank: float | None
    expected_document_retrieved: bool | None
    expected_source_retrieved: bool | None
    duplicate_context_rate: float
    cross_assistant_retrieval_failure: bool
    unauthorised_source_failure: bool
    # Retrieval V2 Phase 1 (docs/future/HybridRetrieval.md) additions - how
    # much of the *multi-item* expected evidence set was covered, not simply
    # whether one relevant chunk/document was found (that's hit_at_k above).
    # Reuses the same expected_document_ids ground truth recall_at_k already
    # uses (fixtures define no chunk-level evidence, so nothing finer is
    # fabricated) - populated only when a case actually declares more than
    # one expected document, otherwise None (no signal to measure).
    evidence_coverage: float | None = None
    retrieval_strategy: str | None = None
    dense_candidate_count: int | None = None
    lexical_candidate_count: int | None = None
    fused_candidate_count: int | None = None
    dense_latency_ms: int | None = None
    lexical_latency_ms: int | None = None
    fusion_latency_ms: int | None = None

    def as_dict(self) -> dict[str, object]:
        return {
            "retrieved_chunk_count": self.retrieved_chunk_count,
            "hit_at_k": self.hit_at_k,
            "recall_at_k": self.recall_at_k,
            "precision_at_k": self.precision_at_k,
            "reciprocal_rank": self.reciprocal_rank,
            "expected_document_retrieved": self.expected_document_retrieved,
            "expected_source_retrieved": self.expected_source_retrieved,
            "duplicate_context_rate": self.duplicate_context_rate,
            "cross_assistant_retrieval_failure": self.cross_assistant_retrieval_failure,
            "unauthorised_source_failure": self.unauthorised_source_failure,
            "evidence_coverage": self.evidence_coverage,
            "retrieval_strategy": self.retrieval_strategy,
            "dense_candidate_count": self.dense_candidate_count,
            "lexical_candidate_count": self.lexical_candidate_count,
            "fused_candidate_count": self.fused_candidate_count,
            "dense_latency_ms": self.dense_latency_ms,
            "lexical_latency_ms": self.lexical_latency_ms,
            "fusion_latency_ms": self.fusion_latency_ms,
        }


def compute_retrieval_metrics(
    *,
    expected_document_ids: list[str] | None,
    expected_source_labels: list[str] | None,
    retrieved_document_ids: list[str],
    retrieved_chunk_ids: list[str],
    retrieved_source_labels: list[str],
    allowed_document_ids: list[str] | None,
    retrieval_strategy: str | None = None,
    dense_candidate_count: int | None = None,
    lexical_candidate_count: int | None = None,
    fused_candidate_count: int | None = None,
    dense_latency_ms: int | None = None,
    lexical_latency_ms: int | None = None,
    fusion_latency_ms: int | None = None,
) -> RetrievalMetrics:
    retrieved_chunk_count = len(retrieved_chunk_ids)
    duplicate_context_rate = _duplicate_rate(retrieved_chunk_ids)

    hit_at_k: bool | None = None
    recall_at_k: float | None = None
    precision_at_k: float | None = None
    reciprocal_rank: float | None = None
    expected_document_retrieved: bool | None = None

    if expected_document_ids:
        expected = set(expected_document_ids)
        overlap = [document_id for document_id in retrieved_document_ids if document_id in expected]
        hit_at_k = len(overlap) > 0
        expected_document_retrieved = hit_at_k
        recall_at_k = len(set(overlap)) / len(expected) if expected else None
        precision_at_k = len(overlap) / len(retrieved_document_ids) if retrieved_document_ids else 0.0
        reciprocal_rank = 0.0
        for rank, document_id in enumerate(retrieved_document_ids, start=1):
            if document_id in expected:
                reciprocal_rank = 1.0 / rank
                break

    evidence_coverage: float | None = None
    if expected_document_ids and len(expected_document_ids) > 1:
        evidence_coverage = recall_at_k

    expected_source_retrieved: bool | None = None
    if expected_source_labels:
        expected_sources = set(expected_source_labels)
        expected_source_retrieved = any(label in expected_sources for label in retrieved_source_labels)

    cross_assistant_retrieval_failure = False
    unauthorised_source_failure = False
    if allowed_document_ids is not None:
        allowed = set(allowed_document_ids)
        unauthorised = [document_id for document_id in retrieved_document_ids if document_id not in allowed]
        cross_assistant_retrieval_failure = len(unauthorised) > 0
        unauthorised_source_failure = cross_assistant_retrieval_failure

    return RetrievalMetrics(
        retrieved_chunk_count=retrieved_chunk_count,
        hit_at_k=hit_at_k,
        recall_at_k=recall_at_k,
        precision_at_k=precision_at_k,
        reciprocal_rank=reciprocal_rank,
        expected_document_retrieved=expected_document_retrieved,
        expected_source_retrieved=expected_source_retrieved,
        duplicate_context_rate=duplicate_context_rate,
        cross_assistant_retrieval_failure=cross_assistant_retrieval_failure,
        unauthorised_source_failure=unauthorised_source_failure,
        evidence_coverage=evidence_coverage,
        retrieval_strategy=retrieval_strategy,
        dense_candidate_count=dense_candidate_count,
        lexical_candidate_count=lexical_candidate_count,
        fused_candidate_count=fused_candidate_count,
        dense_latency_ms=dense_latency_ms,
        lexical_latency_ms=lexical_latency_ms,
        fusion_latency_ms=fusion_latency_ms,
    )


def _duplicate_rate(chunk_ids: list[str]) -> float:
    if not chunk_ids:
        return 0.0
    seen: set[str] = set()
    duplicates = 0
    for chunk_id in chunk_ids:
        if chunk_id in seen:
            duplicates += 1
        seen.add(chunk_id)
    return duplicates / len(chunk_ids)
