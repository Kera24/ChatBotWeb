# AI Alert Threshold Guide

Status: implemented (structured events only - no paging/webhook delivery)

## Delivery model

`app.observability.alerts.evaluate_alerts` is a deterministic threshold evaluator, not a running background service. It computes metrics over a trailing window (default 1 hour) and, for each breached threshold, emits a structured JSON log line (via `app.operations.logging.log_operational_event`) and returns the event to the caller. It is invoked:

- On demand via `GET .../observability/alerts` (requires `org_owner`/`client_admin`).
- Optionally on a schedule, by wiring a cron/systemd timer to call it (there is no bundled scheduler in this pass - see Limitations).

This intentionally does not include a webhook/email/PagerDuty integration. The spec this feature was built against explicitly allows "emit structured alert events... no expensive alerting service required" as the initial implementation - structured logs plus the read API are the two delivery mechanisms available today. Forward the structured log lines into your own alerting pipeline (e.g. a Loki alerting rule reading `event_type: "ai_observability.alert"`) if you need paging.

## Thresholds

All configurable via environment variables, all evaluated over the same trailing window, all requiring a minimum sample size (`AI_ALERT_MIN_SAMPLE_SIZE`, default 5 requests) before triggering - a single slow request in an otherwise-quiet window should not page anyone.

| Alert key | Env var | Default | Severity | Fires when |
|---|---|---|---|---|
| `p95_latency_high` | `AI_ALERT_P95_LATENCY_MS` | 8000ms | warning | p95 latency exceeds threshold |
| `provider_error_rate_high` | `AI_ALERT_PROVIDER_ERROR_RATE_PCT` | 10% | critical | provider failure rate exceeds threshold |
| `fallback_rate_high` | `AI_ALERT_FALLBACK_RATE_PCT` | 40% | warning | fallback rate exceeds threshold |
| `evidence_insufficient_rate_high` | `AI_ALERT_EVIDENCE_INSUFFICIENT_RATE_PCT` | 30% | warning | evidence-insufficient rate exceeds threshold |
| `guardrail_block_rate_high` | `AI_ALERT_GUARDRAIL_BLOCK_RATE_PCT` | 20% | warning | guardrail-blocked rate exceeds threshold (includes the top blocking reason code) |
| `cost_per_request_high` | `AI_ALERT_COST_PER_REQUEST_USD` | disabled (0) | warning | average cost/request exceeds threshold, only evaluated when set > 0 |
| `zero_traffic` | `AI_ALERT_ZERO_TRAFFIC_MINUTES` | 60 min | info | no AI requests recorded in the configured window |

Not yet computed from AI trace data (require separate, already-existing signals rather than new AI-trace-derived logic):

- **Embedding error rate** - not separately tracked from provider generation failures in this pass; a provider/embedding failure currently surfaces as a `failed` trace either way. Splitting embedding-specific failures out is a natural extension of `app.observability.metrics`.
- **Invalid citation attempts** - covered by the `citation_policy` guardrail's blocked count, visible via `ai_guardrail_traces`/the dashboard's blocked-rate metric, not yet a dedicated alert key.
- **Backup failure, webhook failure, disk pressure** - these are infrastructure-level, not AI-trace-derived, and are already covered by `deployment/monitoring/check.sh` (disk space, backup freshness, container health) - see that script and `Backup_and_Restore_Runbook.md` rather than this AI-specific evaluator.

## Adding a new threshold

1. Add the env var to `apps/api/app/core/config.py` following the existing `AI_ALERT_*` naming and `_get_float`/`_get_int` pattern.
2. Add the check in `app.observability.alerts.evaluate_alerts`, following the existing `if sufficient_sample and (...) > settings.AI_ALERT_...` shape.
3. Add a test case to `apps/api/tests/test_ai_alert_thresholds.py` covering the boundary (just under vs. just over threshold).

## Operational note

Alert thresholds are intentionally conservative defaults for a low-traffic controlled pilot. Revisit them once real traffic volume and baseline behaviour are established - a `p95_latency_high` threshold tuned for pilot traffic will likely need raising (or the window shortening) as concurrency increases with a real provider (this platform currently only ships a mock provider - see `AI_Observability_Architecture.md`).
