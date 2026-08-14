"""Cardinality-safe OpenTelemetry metric emission - the Prometheus/Grafana
half of the observability architecture, alongside the existing OTel tracing
(`app.operations.telemetry`) and the existing Postgres-backed AI trace/alert
system (`app.observability.ai_trace_recorder`, `app.observability.alerts`,
`app.alerting.*`). This module does not compute or evaluate anything itself -
every function here only *records* a value its caller already computed, via
whichever `Meter` the process-global `MeterProvider` currently is (a no-op
proxy until `app.operations.telemetry.configure_observability` registers a
real one - see that module for exporter wiring).

CARDINALITY POLICY (see docs/architecture/observability.md): every label
attached here must be a small, closed vocabulary - service/environment
names, provider/model keys, pipeline stage names, outcome/status/verdict
enums. Never attach organisation_id, workspace_id, assistant_id,
conversation_id, request_id, user_id, prompt_version, or experiment_id as a
metric attribute - those stay in logs/traces (Loki/Tempo/Postgres AI
traces), which are built for high-cardinality, per-request lookup. A
reviewer adding a new `record_*` function here must keep every attribute
value drawn from a bounded enum, not a tenant/request identifier.

Fail-safe by construction: every public function catches every exception. A
metrics-recording bug must never be able to affect the request it is
observing - same guarantee `app.observability.ai_trace_recorder` and
`app.operations.telemetry.telemetry_span` already provide for trace/log
recording.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger("chatbotweb.observability.otel_metrics")

_METER_NAME = "chatbotweb.api"
_instruments: dict[str, Any] = {}


def _meter() -> Any:
    from opentelemetry import metrics

    return metrics.get_meter(_METER_NAME)


def _histogram(name: str, *, unit: str, description: str) -> Any:
    key = f"histogram:{name}"
    instrument = _instruments.get(key)
    if instrument is None:
        instrument = _meter().create_histogram(name, unit=unit, description=description)
        _instruments[key] = instrument
    return instrument


def _counter(name: str, *, unit: str, description: str) -> Any:
    key = f"counter:{name}"
    instrument = _instruments.get(key)
    if instrument is None:
        instrument = _meter().create_counter(name, unit=unit, description=description)
        _instruments[key] = instrument
    return instrument


def _label(value: str | None) -> str:
    return value if value else "unknown"


def record_ai_stage_latency(*, stage: str, status: str, latency_ms: int) -> None:
    """One AI pipeline stage's latency (embedding/retrieval/generation/... -
    see app.observability.context's STAGE_* constants, a fixed vocabulary).
    Reuses app.observability.ai_trace_recorder's already-computed
    stage_name/status/latency_ms - never re-times anything."""
    try:
        _histogram(
            "ai_stage_latency_ms", unit="ms", description="Latency of one AI pipeline stage."
        ).record(latency_ms, {"stage": _label(stage), "status": _label(status)})
    except Exception:
        logger.debug("record_ai_stage_latency failed", exc_info=True)


def record_ai_model_call(*, provider: str | None, model: str | None, outcome: str, latency_ms: int) -> None:
    """One AI provider model call's latency and outcome. Token/cost totals
    are recorded once per request in record_ai_request_completed instead
    (using the already-aggregated finish_trace values), not duplicated
    here."""
    try:
        labels = {"provider": _label(provider), "model": _label(model), "outcome": _label(outcome)}
        _histogram("ai_model_call_latency_ms", unit="ms", description="Latency of one AI provider model call.").record(latency_ms, labels)
        _counter("ai_model_call_total", unit="1", description="Count of AI provider model calls.").add(1, labels)
    except Exception:
        logger.debug("record_ai_model_call failed", exc_info=True)


def record_ai_request_completed(
    *,
    status: str,
    answer_state: str | None,
    fallback_used: bool,
    provider: str | None,
    model: str | None,
    total_tokens: int | None,
    estimated_cost_usd: float | None,
) -> None:
    """One finished AI request (app.observability.ai_trace_recorder.finish_trace),
    reusing its already-aggregated total_tokens/estimated_cost - the single
    place token/cost counters are incremented, so a request with multiple
    model-call attempts is not double-counted."""
    try:
        outcome_labels = {"status": _label(status), "answer_state": _label(answer_state), "fallback": str(bool(fallback_used)).lower()}
        _counter("ai_requests_total", unit="1", description="Completed AI requests by outcome.").add(1, outcome_labels)

        provider_labels = {"provider": _label(provider), "model": _label(model)}
        if total_tokens is not None:
            _counter("ai_tokens_total", unit="1", description="AI tokens consumed per completed request.").add(total_tokens, provider_labels)
        if estimated_cost_usd is not None:
            _counter("ai_estimated_cost_usd_total", unit="usd", description="Estimated AI spend per completed request.").add(
                estimated_cost_usd, provider_labels
            )
    except Exception:
        logger.debug("record_ai_request_completed failed", exc_info=True)


def record_retrieval_fusion(
    *, strategy: str, dense_candidate_count: int, lexical_candidate_count: int, fused_candidate_count: int, selected_top_k: int
) -> None:
    """One retrieval call's candidate-generation shape (Retrieval V2 Phase 1,
    docs/future/HybridRetrieval.md) - `strategy` is the closed
    "dense_only"/"hybrid_rrf" vocabulary from settings.RETRIEVAL_STRATEGY,
    never a tenant/request id, per this module's CARDINALITY POLICY."""
    try:
        labels = {"strategy": _label(strategy)}
        _counter("retrieval_requests_total", unit="1", description="Completed retrieval calls by strategy.").add(1, labels)
        _histogram("retrieval_dense_candidate_count", unit="1", description="Dense channel candidate pool size before fusion.").record(
            dense_candidate_count, labels
        )
        _histogram("retrieval_lexical_candidate_count", unit="1", description="Lexical channel candidate pool size before fusion.").record(
            lexical_candidate_count, labels
        )
        _histogram("retrieval_fused_candidate_count", unit="1", description="Candidate count after fusion/dedup.").record(
            fused_candidate_count, labels
        )
        _histogram("retrieval_selected_top_k", unit="1", description="Chunks actually selected into the context window.").record(
            selected_top_k, labels
        )
    except Exception:
        logger.debug("record_retrieval_fusion failed", exc_info=True)


def record_reranker_outcome(
    *, enabled: bool, provider: str | None, model: str | None, candidate_count: int, selected_count: int, latency_ms: int, status: str | None
) -> None:
    """One retrieval call's reranking shape (Retrieval V2 Phase 2,
    docs/future/Reranking.md) - `provider`/`model`/`status` are the closed
    "none"/"cross_encoder" and "ok"/"no_reranker"/"empty_candidates"/"failed"
    vocabularies from app.services.reranking, never a tenant/request id, per
    this module's CARDINALITY POLICY. Recorded even when reranking is
    disabled (enabled=False) so the "disabled" state is itself visible in the
    same dashboards, not just inferred from absence."""
    try:
        labels = {"provider": _label(provider), "model": _label(model), "status": _label(status), "enabled": str(bool(enabled)).lower()}
        _counter("reranker_requests_total", unit="1", description="Completed reranker calls by provider/status.").add(1, labels)
        if enabled:
            _histogram("reranker_candidate_count", unit="1", description="Candidate pool size handed to the reranker.").record(
                candidate_count, labels
            )
            _histogram("reranker_selected_count", unit="1", description="Candidates selected after reranking.").record(selected_count, labels)
            _histogram("reranker_latency_ms", unit="ms", description="Latency of one reranker call.").record(latency_ms, labels)
    except Exception:
        logger.debug("record_reranker_outcome failed", exc_info=True)


def record_query_transformation_outcome(
    *,
    enabled: bool,
    strategy: str | None,
    provider: str | None,
    model: str | None,
    status: str | None,
    latency_ms: int,
    generated_query_count: int,
    raw_candidate_count: int = 0,
    deduplicated_candidate_count: int = 0,
) -> None:
    """One RAG request's retrieval query transformation shape (Retrieval V2
    Phase 3, docs/future/QueryRewrite.md) - `strategy`/`provider`/`model`/
    `status` are the closed "identity"/"deterministic"/"model_assisted" and
    "ok"/"unchanged"/"identity"/"failed"/"timeout"/"malformed_output"/
    "unavailable"/"empty_rewrite" vocabularies from
    app.services.query_transformation, never a tenant/request id or raw query
    text, per this module's CARDINALITY POLICY. Recorded even when
    transformation is disabled/a no-op (enabled=False) so that state is
    itself visible in the same dashboards, not just inferred from absence."""
    try:
        labels = {"strategy": _label(strategy), "provider": _label(provider), "model": _label(model), "status": _label(status), "enabled": str(bool(enabled)).lower()}
        _counter("query_transformation_requests_total", unit="1", description="Completed query transformation calls by strategy/status.").add(1, labels)
        _histogram("query_transformation_latency_ms", unit="ms", description="Latency of one query transformation call.").record(latency_ms, labels)
        _histogram(
            "query_transformation_generated_query_count", unit="1", description="Retrieval query count produced by the transformer (including the original)."
        ).record(generated_query_count, labels)
        if enabled:
            _histogram("query_transformation_raw_candidate_count", unit="1", description="Total dense candidates across all retrieval queries before merge.").record(
                raw_candidate_count, labels
            )
            _histogram(
                "query_transformation_deduplicated_candidate_count", unit="1", description="Distinct chunk count after the multi-query merge."
            ).record(deduplicated_candidate_count, labels)
    except Exception:
        logger.debug("record_query_transformation_outcome failed", exc_info=True)


def record_evidence_verifier_outcome(
    *, version: str, verdict: str, reason_code: str | None, chunks_considered: int, conflict_detected: bool, latency_ms: int
) -> None:
    """One evidence-sufficiency verifier call (Evidence Sufficiency V2 task,
    docs/future/GuardrailsV2.md) - `version` ("v1"/"v2"), `verdict`
    ("sufficient"/"insufficient"), and `reason_code` are the closed
    GuardrailReasonCode vocabulary from app.ai.guardrails.evidence_sufficiency,
    never a tenant/request id or raw question/chunk text, per this module's
    CARDINALITY POLICY. `chunks_considered` is bucketed (not the raw count)
    since it is otherwise an effectively unbounded histogram dimension
    combined with the other labels."""
    try:
        bucket = "0" if chunks_considered == 0 else "1-3" if chunks_considered <= 3 else "4-10" if chunks_considered <= 10 else "10+"
        labels = {
            "version": _label(version), "verdict": _label(verdict), "reason_code": _label(reason_code),
            "chunks_considered_bucket": bucket, "conflict_detected": str(bool(conflict_detected)).lower(),
        }
        _counter("evidence_verifier_outcomes_total", unit="1", description="Evidence-sufficiency verifier verdicts.").add(1, labels)
        _histogram("evidence_verifier_latency_ms", unit="ms", description="Latency of one evidence-sufficiency verifier call.").record(
            latency_ms, {"version": _label(version)}
        )
    except Exception:
        logger.debug("record_evidence_verifier_outcome failed", exc_info=True)


def record_evidence_confidence_outcome(*, decision: str, confidence_band: str, conflicting_evidence: bool, clarification_required: bool) -> None:
    """One Retrieval & Answer Pipeline V3 experiment (docs/future/RetrievalOptimisation.md)
    Evidence Confidence / AnswerConstraints outcome - `decision`
    ("answer"/"fallback"/"clarification_required") and `confidence_band`
    ("high"/"medium"/"low"/"none") are the closed vocabularies from
    app.ai.guardrails.answer_constraints/evidence_confidence, never a
    tenant/request id or raw question/answer text, per this module's
    CARDINALITY POLICY. Only emitted when the V3 experimental pipeline is
    active (opt-in, not the production baseline)."""
    try:
        _counter("evidence_confidence_outcomes_total", unit="1", description="V3 evidence-confidence/answer-constraint decisions.").add(
            1,
            {
                "decision": _label(decision), "confidence_band": _label(confidence_band),
                "conflicting_evidence": str(bool(conflicting_evidence)).lower(), "clarification_required": str(bool(clarification_required)).lower(),
            },
        )
    except Exception:
        logger.debug("record_evidence_confidence_outcome failed", exc_info=True)


def record_guardrail_outcome(*, layer: str, guardrail: str, verdict: str, blocked: bool) -> None:
    """One guardrail layer verdict (app.observability.ai_trace_recorder.record_guardrail) -
    layer/guardrail_name/verdict are already a fixed vocabulary (see
    docs/architecture/guardrails.md's layers A-H)."""
    try:
        _counter("ai_guardrail_outcomes_total", unit="1", description="Guardrail layer verdicts.").add(
            1, {"layer": _label(layer), "guardrail": _label(guardrail), "verdict": _label(verdict), "blocked": str(bool(blocked)).lower()}
        )
    except Exception:
        logger.debug("record_guardrail_outcome failed", exc_info=True)


def record_evaluation_gate_outcome(*, gate: str, passed: bool) -> None:
    """One evaluation/release-gate verdict (app.operations.eval_release_gate_check /
    eval_regression_report's already-computed GateVerdict) - `gate` is one of
    a small fixed set ("release_gate", "regression"), never a dataset/run id."""
    try:
        _counter("evaluation_gate_outcomes_total", unit="1", description="Evaluation/release gate verdicts.").add(
            1, {"gate": _label(gate), "result": "passed" if passed else "failed"}
        )
    except Exception:
        logger.debug("record_evaluation_gate_outcome failed", exc_info=True)


def record_email_delivery(*, provider: str, email_type: str, success: bool, error_code: str | None) -> None:
    """One transactional email send attempt (app.email.service._send) -
    provider/email_type/error_code are all closed vocabularies (see
    app.email.contracts.EmailType, app.email.errors)."""
    try:
        _counter("email_delivery_total", unit="1", description="Transactional email delivery attempts.").add(
            1,
            {
                "provider": _label(provider),
                "email_type": _label(email_type),
                "status": "success" if success else "failure",
                "error_code": _label(error_code) if not success else "none",
            },
        )
    except Exception:
        logger.debug("record_email_delivery failed", exc_info=True)


def record_unhandled_exception(*, route: str, exception_type: str) -> None:
    """One unhandled exception reaching the global handler
    (app.api.exception_handlers) - `route` is the normalised route template
    (app.operations.telemetry.normalise_route), never a raw path containing
    an id."""
    try:
        _counter("api_unhandled_exceptions_total", unit="1", description="Unhandled exceptions reaching the global handler.").add(
            1, {"route": _label(route), "exception_type": _label(exception_type)}
        )
    except Exception:
        logger.debug("record_unhandled_exception failed", exc_info=True)
