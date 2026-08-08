from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models.ai_trace import AIGuardrailTrace, AIRetrievalTrace, AITrace
from app.repositories.observability_repository import TraceFilters, list_traces_for_metrics

# Terminology note (per the AI Metrics Dictionary): these are deterministic,
# rule-based signals derived from guardrail/retrieval outcomes already
# computed by app.ai.rag_orchestrator - never a claim about whether an answer
# was factually correct. Do not rename these to "hallucination rate" or
# similar without a review/evaluation-confirmed methodology behind it.


@dataclass(frozen=True)
class AIObservabilityMetrics:
    request_volume: int
    p50_latency_ms: float | None
    p95_latency_ms: float | None
    total_tokens: int
    total_estimated_cost: Decimal | None
    cost_currency: str
    unknown_cost_request_count: int
    answered_count: int
    fallback_count: int
    blocked_count: int
    failed_count: int
    fallback_rate: float
    blocked_rate: float
    provider_failure_rate: float
    citation_coverage: float | None
    evidence_insufficient_rate: float


def _percentile(sorted_values: list[int], pct: float) -> float | None:
    if not sorted_values:
        return None
    if len(sorted_values) == 1:
        return float(sorted_values[0])
    rank = pct * (len(sorted_values) - 1)
    lower = int(rank)
    upper = min(lower + 1, len(sorted_values) - 1)
    weight = rank - lower
    return sorted_values[lower] * (1 - weight) + sorted_values[upper] * weight


def compute_metrics(db: Session, *, filters: TraceFilters) -> AIObservabilityMetrics:
    traces = list_traces_for_metrics(db, filters=filters)
    trace_ids = [trace.id for trace in traces]
    total = len(traces)

    latencies = sorted(trace.total_latency_ms for trace in traces if trace.total_latency_ms is not None)
    total_tokens = sum(trace.total_tokens or 0 for trace in traces)
    known_costs = [trace.estimated_cost for trace in traces if trace.estimated_cost is not None]
    total_estimated_cost = sum(known_costs) if known_costs else None
    unknown_cost_request_count = sum(1 for trace in traces if trace.status == "completed" and trace.estimated_cost is None)

    answered_count = sum(1 for trace in traces if trace.answer_state == "answered")
    failed_count = sum(1 for trace in traces if trace.answer_state == "failed" or trace.status == "failed")

    blocked_trace_ids: set[str] = set()
    evidence_insufficient_trace_ids: set[str] = set()
    if trace_ids:
        guardrail_rows = db.execute(
            select(AIGuardrailTrace.trace_id, AIGuardrailTrace.guardrail_name, AIGuardrailTrace.blocked).where(
                AIGuardrailTrace.trace_id.in_(trace_ids), AIGuardrailTrace.blocked.is_(True)
            )
        ).all()
        for trace_id, guardrail_name, _blocked in guardrail_rows:
            blocked_trace_ids.add(trace_id)
            if guardrail_name == "evidence_sufficiency":
                evidence_insufficient_trace_ids.add(trace_id)

    fallback_count = sum(1 for trace in traces if trace.fallback_used and trace.id not in blocked_trace_ids)
    blocked_count = len(blocked_trace_ids)

    citation_coverage: float | None = None
    if answered_count and trace_ids:
        answered_ids = [trace.id for trace in traces if trace.answer_state == "answered"]
        cited_ids = set(
            db.execute(
                select(AIRetrievalTrace.trace_id).where(AIRetrievalTrace.trace_id.in_(answered_ids), AIRetrievalTrace.selected.is_(True)).distinct()
            ).scalars().all()
        )
        citation_coverage = len(cited_ids) / len(answered_ids) if answered_ids else None

    return AIObservabilityMetrics(
        request_volume=total,
        p50_latency_ms=_percentile(latencies, 0.50),
        p95_latency_ms=_percentile(latencies, 0.95),
        total_tokens=total_tokens,
        total_estimated_cost=total_estimated_cost,
        cost_currency=traces[0].cost_currency if traces else "USD",
        unknown_cost_request_count=unknown_cost_request_count,
        answered_count=answered_count,
        fallback_count=fallback_count,
        blocked_count=blocked_count,
        failed_count=failed_count,
        fallback_rate=(fallback_count / total) if total else 0.0,
        blocked_rate=(blocked_count / total) if total else 0.0,
        provider_failure_rate=(failed_count / total) if total else 0.0,
        citation_coverage=citation_coverage,
        evidence_insufficient_rate=(len(evidence_insufficient_trace_ids) / total) if total else 0.0,
    )
