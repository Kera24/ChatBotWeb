"""Deterministic per-arm metric aggregation for a prompt experiment - rate,
latency, and cost only, no statistical significance testing. This is an
explicit, documented MVP scope cut (see docs/architecture/prompts.md): results
are always directional, and `sufficient_sample` gates whether the UI may
present a "winner" at all. Mirrors app.evaluation.feedback_metrics's
pure-aggregation style - reads only, no writes."""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models.ai_trace import AIModelCallTrace, AITrace
from app.prompts.experiment_assignment import ARM_CANDIDATE, ARM_CONTROL

MIN_SAMPLE_SIZE_PER_ARM = 100


@dataclass(frozen=True)
class ArmMetrics:
    arm: str
    request_count: int
    fallback_count: int
    fallback_rate: float | None
    failed_count: int
    avg_latency_ms: float | None
    avg_total_tokens: float | None
    avg_estimated_cost: float | None
    sufficient_sample: bool


def compute_experiment_metrics(db: Session, *, experiment_id: str) -> list[ArmMetrics]:
    return [_compute_arm_metrics(db, experiment_id=experiment_id, arm=arm) for arm in (ARM_CONTROL, ARM_CANDIDATE)]


def _compute_arm_metrics(db: Session, *, experiment_id: str, arm: str) -> ArmMetrics:
    traces = (
        db.execute(
            select(AITrace)
            .join(AIModelCallTrace, AIModelCallTrace.trace_id == AITrace.id)
            .where(AIModelCallTrace.experiment_id == experiment_id, AIModelCallTrace.experiment_arm == arm)
        )
        .scalars()
        .unique()
        .all()
    )
    count = len(traces)
    fallback_count = sum(1 for trace in traces if trace.fallback_used)
    failed_count = sum(1 for trace in traces if trace.answer_state == "failed")
    latencies = [trace.total_latency_ms for trace in traces if trace.total_latency_ms is not None]
    tokens = [trace.total_tokens for trace in traces if trace.total_tokens is not None]
    costs = [float(trace.estimated_cost) for trace in traces if trace.estimated_cost is not None]
    return ArmMetrics(
        arm=arm,
        request_count=count,
        fallback_count=fallback_count,
        fallback_rate=(fallback_count / count) if count else None,
        failed_count=failed_count,
        avg_latency_ms=(sum(latencies) / len(latencies)) if latencies else None,
        avg_total_tokens=(sum(tokens) / len(tokens)) if tokens else None,
        avg_estimated_cost=(sum(costs) / len(costs)) if costs else None,
        sufficient_sample=count >= MIN_SAMPLE_SIZE_PER_ARM,
    )
