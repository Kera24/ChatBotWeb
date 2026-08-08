from __future__ import annotations

import logging
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any, Iterator

from fastapi import FastAPI, Request

from app.core.config import settings
from app.operations.logging import redact

logger = logging.getLogger("chatbotweb.telemetry")

SENSITIVE_ROUTE_GROUPS = {
    "/api/v1/widget/{public_key}/config",
    "/api/v1/widget/{public_key}/sessions",
    "/api/v1/widget/{public_key}/messages",
}
APPROVED_ATTRIBUTE_KEYS = {
    "service.name",
    "deployment.environment",
    "service.version",
    "http.route",
    "http.request.method",
    "http.response.status_code",
    "request.id",
    "operation.name",
    "event.type",
    "event.outcome",
    "error.category",
    "latency.ms",
    "answer_state",
    "retrieval_result_count",
}


@dataclass(frozen=True)
class TelemetryConfig:
    enabled: bool
    connection_string_present: bool
    environment: str
    service_name: str
    release_version: str
    sampling_ratio: float

    @property
    def export_enabled(self) -> bool:
        return self.enabled and self.connection_string_present


def telemetry_config() -> TelemetryConfig:
    return TelemetryConfig(
        enabled=settings.AZURE_MONITOR_OPEN_TELEMETRY_ENABLED.strip().lower() in {"1", "true", "yes", "on"},
        connection_string_present=bool(settings.APPLICATIONINSIGHTS_CONNECTION_STRING.strip()),
        environment=settings.APP_ENV,
        service_name=settings.SERVICE_NAME,
        release_version=settings.VERSION,
        sampling_ratio=max(0.0, min(1.0, settings.AZURE_MONITOR_SAMPLING_RATIO)),
    )


def validate_telemetry_config(config: TelemetryConfig | None = None) -> list[str]:
    config = config or telemetry_config()
    failures: list[str] = []
    require_connection = settings.AZURE_MONITOR_REQUIRE_CONNECTION_STRING.strip().lower() in {"1", "true", "yes", "on"}
    if config.environment in {"staging", "production", "pilot"} and require_connection and not config.connection_string_present:
        failures.append("Application Insights connection string is required for monitored Azure environments.")
    if not config.service_name:
        failures.append("Telemetry service name is required.")
    if not config.release_version or config.release_version in {"latest", "bootstrap-placeholder"}:
        failures.append("Telemetry release version must be an immutable release or Git SHA for staging/pilot.")
    if config.sampling_ratio <= 0 or config.sampling_ratio > 1:
        failures.append("Telemetry sampling ratio must be greater than 0 and at most 1.")
    return failures


def normalise_route(request: Request) -> str:
    route = request.scope.get("route")
    path = getattr(route, "path", None)
    if isinstance(path, str) and path:
        return path
    path_value = request.url.path
    if path_value.startswith("/api/v1/widget/") and path_value.endswith("/messages"):
        return "/api/v1/widget/{public_key}/messages"
    if path_value.startswith("/api/v1/widget/") and path_value.endswith("/sessions"):
        return "/api/v1/widget/{public_key}/sessions"
    if path_value.startswith("/api/v1/widget/") and path_value.endswith("/config"):
        return "/api/v1/widget/{public_key}/config"
    return path_value


def safe_attributes(attributes: dict[str, Any]) -> dict[str, Any]:
    redacted = redact(attributes)
    return {key: value for key, value in redacted.items() if key in APPROVED_ATTRIBUTE_KEYS and value is not None}


def _truthy(value: str) -> bool:
    return value.strip().lower() in {"1", "true", "yes", "on"}


def configure_azure_monitor(app: FastAPI) -> None:
    config = telemetry_config()
    app.state.telemetry_config = config
    app.state.telemetry_config_failures = validate_telemetry_config(config)
    app.state.telemetry_enabled = False
    if not config.export_enabled:
        return
    try:
        from azure.monitor.opentelemetry import configure_azure_monitor as configure_exporter
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
        from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
    except Exception as exc:
        logger.warning("Azure Monitor OpenTelemetry packages unavailable; telemetry export disabled: %s", exc)
        return
    try:
        configure_exporter(
            connection_string=settings.APPLICATIONINSIGHTS_CONNECTION_STRING,
            resource_attributes={
                "service.name": config.service_name,
                "deployment.environment": config.environment,
                "service.version": config.release_version,
            },
        )
        FastAPIInstrumentor.instrument_app(app, excluded_urls="/health/live,/health/ready")
        SQLAlchemyInstrumentor().instrument(enable_commenter=False)
        app.state.telemetry_enabled = True
    except Exception as exc:
        logger.warning("Azure Monitor OpenTelemetry initialization failed; continuing without export: %s", exc)


def configure_observability(app: FastAPI) -> None:
    """Entry point called once at app startup (replaces a direct
    `configure_azure_monitor(app)` call in app.main.create_app).

    Precedence: Azure Monitor OTel Distro (if configured) always wins over the
    generic OTLP/console/no-export path below - only one global OTel
    `TracerProvider` can ever be registered process-wide, and the Azure
    Monitor distro already calls `trace.set_tracer_provider()` internally, so
    attempting both would either silently no-op or partially reconfigure
    shared processors. If neither is configured, behavior is identical to
    today: spans are created (via `telemetry_span()`) but never exported,
    because the OTel API's default global tracer provider is a no-op proxy
    until something calls `set_tracer_provider()`.
    """
    config = telemetry_config()
    otel_generic_requested = _truthy(settings.OTEL_ENABLED)

    if config.export_enabled:
        if otel_generic_requested:
            logger.warning(
                "Both Azure Monitor OTel and OTEL_ENABLED are configured; Azure Monitor takes "
                "precedence to avoid registering a second global TracerProvider."
            )
        configure_azure_monitor(app)
        return

    # Azure Monitor path is inactive (disabled, or enabled without a
    # connection string) - still record its own state for the
    # /system health/config surface, exactly as configure_azure_monitor does.
    app.state.telemetry_config = config
    app.state.telemetry_config_failures = validate_telemetry_config(config)
    app.state.telemetry_enabled = False

    if otel_generic_requested:
        _configure_generic_otel(app)


def _configure_generic_otel(app: FastAPI) -> None:
    try:
        from opentelemetry import trace
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
        from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter
    except Exception as exc:
        logger.warning("Generic OpenTelemetry SDK packages unavailable; telemetry export disabled: %s", exc)
        return

    try:
        config = telemetry_config()
        resource_attributes = {
            "service.name": settings.OTEL_SERVICE_NAME or config.service_name,
            "deployment.environment": config.environment,
            "service.version": config.release_version,
            **_parse_otel_resource_attributes(settings.OTEL_RESOURCE_ATTRIBUTES),
        }
        provider = TracerProvider(resource=Resource.create(resource_attributes))

        endpoint = settings.OTEL_EXPORTER_OTLP_ENDPOINT.strip()
        if endpoint:
            from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter

            provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter(endpoint=endpoint)))
        elif _truthy(settings.OTEL_CONSOLE_EXPORT):
            provider.add_span_processor(BatchSpanProcessor(ConsoleSpanExporter()))
        # else: no span processor registered - spans are created but
        # discarded in-process ("local/no-export mode" from the spec).

        trace.set_tracer_provider(provider)
        FastAPIInstrumentor.instrument_app(app, excluded_urls="/health/live,/health/ready")
        SQLAlchemyInstrumentor().instrument(enable_commenter=False)
        app.state.telemetry_enabled = bool(endpoint or _truthy(settings.OTEL_CONSOLE_EXPORT))
    except Exception as exc:
        logger.warning("Generic OpenTelemetry initialization failed; continuing without export: %s", exc)


def _parse_otel_resource_attributes(raw: str) -> dict[str, str]:
    attributes: dict[str, str] = {}
    for pair in raw.split(","):
        if "=" not in pair:
            continue
        key, _, value = pair.partition("=")
        key = key.strip()
        value = value.strip()
        if key and value:
            attributes[key] = value
    return attributes


@contextmanager
def telemetry_span(name: str, attributes: dict[str, Any] | None = None) -> Iterator[None]:
    try:
        from opentelemetry import trace

        tracer = trace.get_tracer("chatbotweb.api")
        with tracer.start_as_current_span(name) as span:
            for key, value in safe_attributes(attributes or {}).items():
                span.set_attribute(key, value)
            yield
    except Exception:
        yield


def record_access_event(event_type: str, *, request_id: str, trace_id: str, outcome: str | None = None, error_code: str | None = None, latency_ms: int | None = None) -> None:
    attributes = safe_attributes(
        {
            "event.type": event_type,
            "request.id": request_id,
            "event.outcome": outcome,
            "error.category": error_code,
            "latency.ms": latency_ms,
        }
    )
    try:
        from opentelemetry import trace

        span = trace.get_current_span()
        if span and span.is_recording():
            span.add_event(event_type, attributes)
    except Exception:
        return
