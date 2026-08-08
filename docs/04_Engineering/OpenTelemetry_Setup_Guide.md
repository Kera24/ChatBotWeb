# OpenTelemetry Setup Guide

Status: implemented

## Two mutually exclusive paths

`app.operations.telemetry.configure_observability(app)` (called once from `app.main.create_app`) chooses between two OpenTelemetry configurations, never both:

1. **Azure Monitor OTel Distro** - active when `AZURE_MONITOR_OPEN_TELEMETRY_ENABLED=true` and `APPLICATIONINSIGHTS_CONNECTION_STRING` is set. Unchanged from the existing pilot setup (see `Azure_Observability_Telemetry_and_Alerts.md`).
2. **Generic OTLP export** - active when `OTEL_ENABLED=true` and Azure Monitor is not active.

If both are configured, Azure Monitor wins and a warning is logged. This is not a preference call - the OpenTelemetry SDK can only ever have one global `TracerProvider` registered per process; the Azure Monitor distro already calls `trace.set_tracer_provider()` internally, so attempting to configure a second one afterward would either silently no-op or partially reconfigure shared span processors.

## Environment variables

| Variable | Default | Meaning |
|---|---|---|
| `OTEL_ENABLED` | `false` | Enables the generic (non-Azure) OTel path. |
| `OTEL_EXPORTER_OTLP_ENDPOINT` | empty | OTLP/HTTP endpoint (e.g. `http://otel-collector:4318`). If unset, spans are created but never exported ("local/no-export mode"). |
| `OTEL_SERVICE_NAME` | empty (falls back to `SERVICE_NAME`) | Resource attribute `service.name`. |
| `OTEL_RESOURCE_ATTRIBUTES` | empty | Comma-separated `key=value` pairs merged into the OTel `Resource`, standard OTel format. |
| `OTEL_CONSOLE_EXPORT` | `false` | If true (and no OTLP endpoint set), spans print to stdout - debug mode. |
| `AI_TRACE_RETENTION_DAYS` | `90` | See `AI_Trace_Retention_and_Redaction_Guide.md`. |
| `AI_TRACE_CONTENT_MODE` | `metadata_only` | See `AI_Trace_Data_and_Privacy_Policy.md`. |

## Modes, concretely

- **Disabled** (`OTEL_ENABLED=false`, Azure inactive) - identical to today's default. `telemetry_span()` calls remain safe no-ops (the OTel API's default global tracer is a no-op proxy until something calls `set_tracer_provider()`).
- **Enabled, no endpoint** - a real `TracerProvider` is registered (so `FastAPIInstrumentor`/`SQLAlchemyInstrumentor` auto-instrumentation is active and span attributes are computed) but no span processor is attached, so spans are created and discarded in-process. Useful for exercising the instrumentation path without paying for export.
- **Enabled, console export** (`OTEL_CONSOLE_EXPORT=true`) - spans print to stdout via `ConsoleSpanExporter`. Useful for local debugging.
- **Enabled, OTLP endpoint set** - spans batch-export to the given endpoint (typically an OTel Collector - see the VPS guide). HTTP exporter (`opentelemetry-exporter-otlp-proto-http`), not gRPC, to keep the API's Docker image dependency footprint small.

## Failure safety

Bad configuration (unreachable endpoint, malformed URL) never crashes app startup or breaks a request:

- Setup itself is wrapped in the same `try/except Exception: logger.warning(...)` shape as the existing Azure Monitor path.
- `BatchSpanProcessor` exports asynchronously on its own background thread; export failures are caught and logged inside the OTel SDK itself, never propagated into request handling.
- The OTLP exporter does not validate the endpoint URL eagerly - a malformed value is only ever discovered inside the background export attempt, never at request time.

## Metrics

When an OTLP endpoint is configured, a small number of counters are exported alongside traces (requests, guardrail blocks, provider failures) - deliberately minimal, not a full metrics-SDK integration. Route this through the OTel Collector's Prometheus exporter to get them into Grafana (see the VPS guide).

## Azure compatibility

This does not remove or alter the existing Azure Monitor path in any way - `configure_azure_monitor(app)` is still the exact function that runs when Azure Monitor is active, with the exact same behaviour, tests (`test_azure_observability.py`), and config validation (`validate_telemetry_config`) as before. See `Azure_Monitor_Application_Insights_Mapping.md` for how the two paths compare and how a deployment can migrate from one to the other.
