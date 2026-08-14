"""Tests for the Prometheus/Grafana half of the observability architecture:

- app.observability.otel_metrics: fail-safe metric recording, no raise even
  without a configured MeterProvider, and every emitted attribute stays
  within the cardinality policy (app.observability.otel_metrics's own
  module docstring / docs/architecture/observability.md).
- app.observability.ai_trace_recorder.MetricsEmittingAITraceRecorder: wraps
  any AITraceRecorder, forwards every call unchanged, and additionally
  records the expected metric.
- app.operations.telemetry's OTel Collector wiring: MeterProvider gets
  registered (so FastAPIInstrumentor's http.server.* metrics populate, the
  gap the existing "Conversa API Overview" Grafana dashboard was built
  against but that nothing wired until now), and the OTLP exporter endpoint
  bug (the endpoint= constructor kwarg is used verbatim, unlike the
  OTEL_EXPORTER_OTLP_ENDPOINT env var, so the /v1/traces, /v1/metrics
  per-signal paths must be appended explicitly) is fixed for both signals.
"""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

import pytest
from fastapi import FastAPI
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import InMemoryMetricReader

from app.ai.contracts import TokenUsage
from app.ai.model_registry import ModelConfig
from app.core.config import settings
from app.observability import otel_metrics
from app.observability.ai_trace_recorder import MetricsEmittingAITraceRecorder, NoOpAITraceRecorder
from app.observability.context import AITraceContext, new_trace_id
from app.operations.telemetry import _otlp_signal_endpoint, configure_observability


@pytest.fixture()
def in_memory_metrics(monkeypatch: pytest.MonkeyPatch):
    # OpenTelemetry's global MeterProvider can only ever be set ONCE per
    # process (opentelemetry.metrics.set_meter_provider silently no-ops on a
    # second call, logging a warning) - the same "set once" limitation
    # app.operations.telemetry's existing TracerProvider wiring already has,
    # which is why tests/test_otel_generic_export.py never asserts on
    # provider identity either. Monkeypatching otel_metrics._meter directly
    # to a locally-constructed MeterProvider's Meter sidesteps the global
    # registry entirely, giving each test full isolation.
    reader = InMemoryMetricReader()
    provider = MeterProvider(metric_readers=[reader])
    meter = provider.get_meter(otel_metrics._METER_NAME)
    monkeypatch.setattr(otel_metrics, "_meter", lambda: meter)
    otel_metrics._instruments.clear()
    try:
        yield reader
    finally:
        otel_metrics._instruments.clear()


def _collected_points(reader: InMemoryMetricReader, metric_name: str) -> list:
    data = reader.get_metrics_data()
    points = []
    if data is None:
        return points
    for rm in data.resource_metrics:
        for sm in rm.scope_metrics:
            for m in sm.metrics:
                if m.name == metric_name:
                    points.extend(m.data.data_points)
    return points


# --- fail-safe: never raises, even with no MeterProvider configured ---------


def test_record_functions_never_raise_without_a_configured_meter_provider() -> None:
    otel_metrics.record_ai_stage_latency(stage="retrieval", status="ok", latency_ms=42)
    otel_metrics.record_ai_model_call(provider="openrouter", model="openrouter-default", outcome="success", latency_ms=120)
    otel_metrics.record_ai_request_completed(
        status="completed", answer_state="answered", fallback_used=False, provider="openrouter", model="openrouter-default",
        total_tokens=100, estimated_cost_usd=0.002,
    )
    otel_metrics.record_guardrail_outcome(layer="citation_policy", guardrail="citation_required", verdict="passed", blocked=False)
    otel_metrics.record_evaluation_gate_outcome(gate="release_gate", passed=False)
    otel_metrics.record_email_delivery(provider="resend", email_type="password_reset", success=False, error_code="EMAIL_PROVIDER_UNAVAILABLE")
    otel_metrics.record_unhandled_exception(route="/api/v1/widget/{public_key}/messages", exception_type="ValueError")


# --- metrics actually populate once a MeterProvider is configured -----------


def test_ai_stage_latency_is_recorded(in_memory_metrics: InMemoryMetricReader) -> None:
    otel_metrics.record_ai_stage_latency(stage="retrieval", status="ok", latency_ms=42)
    points = _collected_points(in_memory_metrics, "ai_stage_latency_ms")
    assert len(points) == 1
    assert dict(points[0].attributes) == {"stage": "retrieval", "status": "ok"}


def test_ai_request_completed_records_tokens_and_cost(in_memory_metrics: InMemoryMetricReader) -> None:
    otel_metrics.record_ai_request_completed(
        status="completed", answer_state="answered", fallback_used=False, provider="openrouter", model="openrouter-default",
        total_tokens=150, estimated_cost_usd=0.0031,
    )
    request_points = _collected_points(in_memory_metrics, "ai_requests_total")
    token_points = _collected_points(in_memory_metrics, "ai_tokens_total")
    cost_points = _collected_points(in_memory_metrics, "ai_estimated_cost_usd_total")
    assert dict(request_points[0].attributes) == {"status": "completed", "answer_state": "answered", "fallback": "false"}
    assert dict(token_points[0].attributes) == {"provider": "openrouter", "model": "openrouter-default"}
    assert token_points[0].value == 150
    assert cost_points[0].value == pytest.approx(0.0031)


def test_evaluation_gate_outcome_is_recorded(in_memory_metrics: InMemoryMetricReader) -> None:
    otel_metrics.record_evaluation_gate_outcome(gate="regression", passed=False)
    points = _collected_points(in_memory_metrics, "evaluation_gate_outcomes_total")
    assert dict(points[0].attributes) == {"gate": "regression", "result": "failed"}


def test_email_delivery_is_recorded(in_memory_metrics: InMemoryMetricReader) -> None:
    otel_metrics.record_email_delivery(provider="resend", email_type="password_reset", success=False, error_code="EMAIL_PROVIDER_UNAVAILABLE")
    points = _collected_points(in_memory_metrics, "email_delivery_total")
    assert dict(points[0].attributes) == {
        "provider": "resend", "email_type": "password_reset", "status": "failure", "error_code": "EMAIL_PROVIDER_UNAVAILABLE",
    }


def test_unhandled_exception_is_recorded(in_memory_metrics: InMemoryMetricReader) -> None:
    otel_metrics.record_unhandled_exception(route="/api/v1/widget/{public_key}/messages", exception_type="ValueError")
    points = _collected_points(in_memory_metrics, "api_unhandled_exceptions_total")
    assert dict(points[0].attributes) == {"route": "/api/v1/widget/{public_key}/messages", "exception_type": "ValueError"}


# --- cardinality policy: no high-cardinality attribute ever appears ---------


_FORBIDDEN_LABEL_NAMES = {"organisation_id", "workspace_id", "assistant_id", "conversation_id", "request_id", "user_id"}


def test_no_high_cardinality_labels_are_ever_attached(in_memory_metrics: InMemoryMetricReader) -> None:
    otel_metrics.record_ai_stage_latency(stage="retrieval", status="ok", latency_ms=42)
    otel_metrics.record_ai_model_call(provider="openrouter", model="openrouter-default", outcome="success", latency_ms=120)
    otel_metrics.record_ai_request_completed(
        status="completed", answer_state="answered", fallback_used=True, provider="openrouter", model="openrouter-default",
        total_tokens=10, estimated_cost_usd=None,
    )
    otel_metrics.record_guardrail_outcome(layer="citation_policy", guardrail="citation_required", verdict="blocked", blocked=True)
    otel_metrics.record_evaluation_gate_outcome(gate="release_gate", passed=True)
    otel_metrics.record_email_delivery(provider="dev", email_type="email_verification", success=True, error_code=None)
    otel_metrics.record_unhandled_exception(route="/api/v1/observability/alerts", exception_type="RuntimeError")
    otel_metrics.record_query_transformation_outcome(
        enabled=True, strategy="model_assisted", provider="model_assisted", model="fake-model", status="ok",
        latency_ms=250, generated_query_count=2, raw_candidate_count=10, deduplicated_candidate_count=7,
    )

    data = in_memory_metrics.get_metrics_data()
    for rm in data.resource_metrics:
        for sm in rm.scope_metrics:
            for m in sm.metrics:
                for point in m.data.data_points:
                    assert _FORBIDDEN_LABEL_NAMES.isdisjoint(point.attributes.keys()), f"{m.name} attached a high-cardinality label: {point.attributes}"


# --- Retrieval V2 Phase 3 (docs/future/QueryRewrite.md): query-transformation
# metrics never carry a raw query string or tenant identifier -------------


def test_query_transformation_metrics_never_carry_raw_query_text(in_memory_metrics: InMemoryMetricReader) -> None:
    # Part 9 requirement: raw/transformed query text must never reach a
    # Prometheus label - only the closed strategy/provider/model/status
    # vocabulary and numeric counts/latencies are recorded.
    raw_query_text = "what is the refund window for a customer named Alice Smith at acme-corp-12345"
    otel_metrics.record_query_transformation_outcome(
        enabled=True, strategy="deterministic", provider="deterministic", model="builtin", status="ok",
        latency_ms=5, generated_query_count=2, raw_candidate_count=8, deduplicated_candidate_count=6,
    )
    data = in_memory_metrics.get_metrics_data()
    seen_metric = False
    for rm in data.resource_metrics:
        for sm in rm.scope_metrics:
            for m in sm.metrics:
                if not m.name.startswith("query_transformation_"):
                    continue
                for point in m.data.data_points:
                    seen_metric = True
                    assert _FORBIDDEN_LABEL_NAMES.isdisjoint(point.attributes.keys())
                    assert set(point.attributes.keys()) <= {"strategy", "provider", "model", "status", "enabled"}
                    assert raw_query_text not in point.attributes.values()
    assert seen_metric


# --- MetricsEmittingAITraceRecorder: forwards + records ----------------------


def _model_config(**overrides) -> ModelConfig:
    defaults = dict(
        model_key="openrouter-default", provider_key="openrouter", provider_model_name="openai/gpt-4o-mini",
        display_name="Default", context_window=128_000,
        input_cost_per_million_tokens=Decimal("1.00"), output_cost_per_million_tokens=Decimal("2.00"),
        cost_calc_version="v1",
    )
    defaults.update(overrides)
    return ModelConfig(**defaults)


def _ctx() -> AITraceContext:
    return AITraceContext(trace_id=new_trace_id(), conversation_id=None, request_id="req-1", eval_run_id=None, eval_case_id=None)


def test_wrapper_forwards_every_call_to_the_inner_recorder() -> None:
    class _RecordingInner:
        def __init__(self) -> None:
            self.calls: list[str] = []

        def start_trace(self, *a, **k) -> None:
            self.calls.append("start_trace")

        def record_stage(self, *a, **k) -> None:
            self.calls.append("record_stage")

        def record_retrieval(self, *a, **k) -> None:
            self.calls.append("record_retrieval")

        def record_model_call(self, *a, **k) -> None:
            self.calls.append("record_model_call")

        def record_guardrail(self, *a, **k) -> None:
            self.calls.append("record_guardrail")

        def finish_trace(self, *a, **k) -> None:
            self.calls.append("finish_trace")

    inner = _RecordingInner()
    wrapper = MetricsEmittingAITraceRecorder(inner)
    ctx = _ctx()

    wrapper.start_trace(ctx, organisation_id="org-1", workspace_id="ws-1", assistant_id="asst-1", channel="widget")
    wrapper.record_stage(ctx, "retrieval", status="ok", latency_ms=10)
    wrapper.record_retrieval(ctx, entries=[])
    wrapper.record_model_call(
        ctx, model=_model_config(), provider_model_name="openai/gpt-4o-mini", prompt_key="grounded_rag_answer", prompt_version="v1",
        prompt_hash="hash", token_usage=TokenUsage(input_tokens=10, output_tokens=5, total_tokens=15, estimated=False),
        latency_ms=200, finish_reason="stop", outcome="success",
    )
    wrapper.record_guardrail(ctx, layer="citation_policy", guardrail_name="citation_required", verdict="passed", blocked=False)
    wrapper.finish_trace(
        ctx, status="completed", answer_state="answered", fallback_used=False, total_latency_ms=500,
        provider_key="openrouter", model_key="openrouter-default", total_tokens=15, estimated_cost=Decimal("0.001"),
    )

    assert inner.calls == ["start_trace", "record_stage", "record_retrieval", "record_model_call", "record_guardrail", "finish_trace"]


def test_wrapper_emits_metrics_alongside_the_wrapped_noop_recorder(in_memory_metrics: InMemoryMetricReader) -> None:
    wrapper = MetricsEmittingAITraceRecorder(NoOpAITraceRecorder())
    ctx = _ctx()

    wrapper.record_stage(ctx, "retrieval", status="ok", latency_ms=33)
    wrapper.record_guardrail(ctx, layer="citation_policy", guardrail_name="citation_required", verdict="passed", blocked=False)
    wrapper.finish_trace(
        ctx, status="completed", answer_state="answered", fallback_used=False, total_latency_ms=500,
        provider_key="openrouter", model_key="openrouter-default", total_tokens=15, estimated_cost=Decimal("0.001"),
    )

    assert len(_collected_points(in_memory_metrics, "ai_stage_latency_ms")) == 1
    assert len(_collected_points(in_memory_metrics, "ai_guardrail_outcomes_total")) == 1
    assert len(_collected_points(in_memory_metrics, "ai_requests_total")) == 1


# --- OTel Collector wiring: MeterProvider registration + endpoint path fix --


def _reset_env(**overrides: str) -> dict[str, str]:
    original = {
        "AZURE_MONITOR_OPEN_TELEMETRY_ENABLED": settings.AZURE_MONITOR_OPEN_TELEMETRY_ENABLED,
        "APPLICATIONINSIGHTS_CONNECTION_STRING": settings.APPLICATIONINSIGHTS_CONNECTION_STRING,
        "OTEL_ENABLED": settings.OTEL_ENABLED,
        "OTEL_EXPORTER_OTLP_ENDPOINT": settings.OTEL_EXPORTER_OTLP_ENDPOINT,
        "OTEL_CONSOLE_EXPORT": settings.OTEL_CONSOLE_EXPORT,
    }
    for key, value in {
        "AZURE_MONITOR_OPEN_TELEMETRY_ENABLED": "false", "APPLICATIONINSIGHTS_CONNECTION_STRING": "",
        "OTEL_ENABLED": "false", "OTEL_EXPORTER_OTLP_ENDPOINT": "", "OTEL_CONSOLE_EXPORT": "false", **overrides,
    }.items():
        object.__setattr__(settings, key, value)
    return original


def _restore_env(original: dict[str, str]) -> None:
    for key, value in original.items():
        object.__setattr__(settings, key, value)


def test_otlp_signal_endpoint_appends_the_correct_per_signal_path() -> None:
    assert _otlp_signal_endpoint("http://otel-collector:4318", "v1/traces") == "http://otel-collector:4318/v1/traces"
    assert _otlp_signal_endpoint("http://otel-collector:4318/", "v1/metrics") == "http://otel-collector:4318/v1/metrics"
    assert _otlp_signal_endpoint("http://otel-collector:4318", "v1/logs") == "http://otel-collector:4318/v1/logs"


def test_generic_otel_log_handler_installation_is_idempotent() -> None:
    import logging as std_logging

    from opentelemetry.sdk._logs import LoggingHandler

    original = _reset_env(OTEL_ENABLED="true", OTEL_CONSOLE_EXPORT="true")
    root_logger = std_logging.getLogger()
    try:
        app = FastAPI()
        configure_observability(app)
        configure_observability(app)  # a second call must replace, not stack
        otel_handlers = [h for h in root_logger.handlers if isinstance(h, LoggingHandler)]
        assert len(otel_handlers) == 1
    finally:
        _restore_env(original)


def test_generic_otel_console_export_registers_a_meter_provider_without_raising() -> None:
    # OpenTelemetry's global MeterProvider can only be set once per process
    # (see the in_memory_metrics fixture's comment) - this test, like every
    # test in tests/test_otel_generic_export.py, therefore asserts on
    # app.state.telemetry_enabled rather than provider identity. The actual
    # metric-emission behaviour once a MeterProvider is registered is
    # covered directly (bypassing global registration) by the
    # in_memory_metrics-based tests above.
    original = _reset_env(OTEL_ENABLED="true", OTEL_CONSOLE_EXPORT="true")
    try:
        app = FastAPI()
        configure_observability(app)  # must not raise
        assert app.state.telemetry_enabled is True
    finally:
        _restore_env(original)


def test_generic_otel_with_endpoint_uses_signal_specific_paths(monkeypatch: pytest.MonkeyPatch) -> None:
    captured_trace_endpoint = {}
    captured_metric_endpoint = {}
    captured_log_endpoint = {}

    from opentelemetry.exporter.otlp.proto.http._log_exporter import OTLPLogExporter
    from opentelemetry.exporter.otlp.proto.http.metric_exporter import OTLPMetricExporter
    from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter

    original_trace_init = OTLPSpanExporter.__init__
    original_metric_init = OTLPMetricExporter.__init__
    original_log_init = OTLPLogExporter.__init__

    def _patched_trace_init(self, *args, **kwargs):
        captured_trace_endpoint["endpoint"] = kwargs.get("endpoint")
        return original_trace_init(self, *args, **kwargs)

    def _patched_metric_init(self, *args, **kwargs):
        captured_metric_endpoint["endpoint"] = kwargs.get("endpoint")
        return original_metric_init(self, *args, **kwargs)

    def _patched_log_init(self, *args, **kwargs):
        captured_log_endpoint["endpoint"] = kwargs.get("endpoint")
        return original_log_init(self, *args, **kwargs)

    monkeypatch.setattr(OTLPSpanExporter, "__init__", _patched_trace_init)
    monkeypatch.setattr(OTLPMetricExporter, "__init__", _patched_metric_init)
    monkeypatch.setattr(OTLPLogExporter, "__init__", _patched_log_init)

    original = _reset_env(OTEL_ENABLED="true", OTEL_EXPORTER_OTLP_ENDPOINT="http://otel-collector:4318")
    try:
        app = FastAPI()
        configure_observability(app)  # must not raise
        assert captured_trace_endpoint["endpoint"] == "http://otel-collector:4318/v1/traces"
        assert captured_metric_endpoint["endpoint"] == "http://otel-collector:4318/v1/metrics"
        assert captured_log_endpoint["endpoint"] == "http://otel-collector:4318/v1/logs"
    finally:
        _restore_env(original)
