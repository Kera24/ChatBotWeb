# AI Alert Threshold Guide

Status: implemented (structured events, read API, and proactive delivery via `app.alerting.*`)

## Delivery model

`app.observability.alerts.evaluate_alerts` is a deterministic threshold evaluator, not a running background service. It computes metrics over a trailing window (default 1 hour) and, for each breached threshold, emits a structured JSON log line (via `app.operations.logging.log_operational_event`) and returns the event to the caller. It is invoked:

- On demand via `GET .../observability/alerts` (requires `org_owner`/`client_admin`).
- On a schedule, via `python -m app.operations.alert_dispatch_run --organisation <id> --workspace <id> [--assistant <id>] [--window-hours <float>] [--dry-run]` (cron/systemd timer, same pattern as `observability_retention_cleanup.py`), which additionally *delivers* any triggered alert through the proactive delivery layer below.

`evaluate_alerts` itself is unchanged by the delivery layer - it still only computes and logs. Delivery is a separate, additive consumer.

## Proactive delivery (`app.alerting.*`)

A provider-independent delivery layer sits on top of `evaluate_alerts`'s output - it never re-evaluates a threshold, only converts an already-triggered `AlertEvent` into an `AlertNotification` (`app.alerting.dispatcher.alert_event_to_notification`) and dispatches it.

- **Provider abstraction** - `app.alerting.providers.base.AlertProvider`, selected via `ALERT_PROVIDER` (`app.alerting.dependencies.build_alert_provider`, fail-fast on an explicitly-selected-but-misconfigured provider, mirrors `app.email.dependencies.build_email_provider`):
  - `dev` (default) - logs safe metadata only, never makes an external call. Safe for development/test by default.
  - `email` - reuses the existing transactional email provider abstraction (`app.email.providers.base.TransactionalEmailProvider`), never calls Resend directly. Requires `ALERT_EMAIL_TO` (comma-separated).
  - `slack` - a minimal incoming-webhook client (no Slack SDK). Requires `SLACK_WEBHOOK_URL`.
  - Not yet implemented, but the `AlertProvider` interface is designed for them: Microsoft Teams, Discord, PagerDuty, Opsgenie - each is a new `app/alerting/providers/*.py` file plus a `build_alert_provider` branch, no change to the abstraction.
- **Severity** - `info` / `warning` / `critical` (`app.alerting.contracts.AlertSeverity`), taken directly from `AlertEvent.severity`. `ALERT_MIN_SEVERITY` (default `warning`) filters what actually gets delivered; `evaluate_alerts` still evaluates and logs everything regardless.
- **Deduplication/cooldown** - `app.alerting.cooldown.AlertCooldownStore`, a small JSON state file (`ALERT_COOLDOWN_STATE_PATH`) keyed by organisation/workspace/assistant/alert_key, so a still-triggering condition doesn't re-notify on every cron run within `ALERT_COOLDOWN_SECONDS` (default 1800).
- **Safe payload only** - `AlertNotification` carries alert type, severity, source subsystem, timestamp, tenant/correlation ids, and safe numeric metrics; its `message`/`metrics` fields are redacted on construction via the existing `app.observability.redaction`/`app.operations.logging.redact` paths as a defense-in-depth backstop. Never carries prompts, documents, conversation text, full email addresses, tokens, or API keys.
- **Fail-safe** - a provider failure (raised as a classified `app.alerting.errors.AlertProviderError`, or any unexpected exception) is caught by `app.alerting.dispatcher.dispatch_alerts`, logged as `alert.delivery_failed`, and never propagates - it cannot crash the CLI or any call site.

### Alert categories currently wired

| Category | Source signal | Alert key(s) |
|---|---|---|
| AI provider failure / high error rate | `evaluate_alerts` | `provider_error_rate_high` |
| High latency | `evaluate_alerts` | `p95_latency_high` |
| Guardrail failure | `evaluate_alerts` | `guardrail_block_rate_high` |
| High token/cost usage | `evaluate_alerts` | `cost_per_request_high` |
| Evidence-insufficient / fallback / zero-traffic | `evaluate_alerts` | `evidence_insufficient_rate_high`, `fallback_rate_high`, `zero_traffic` |
| Evaluation gate failure / deployment release-gate failure | `app.evaluation.production_gate.evaluate_production_readiness`'s already-computed verdict, via a fail-safe hook (`app.alerting.hooks.notify_gate_failure`) in `app.operations.eval_release_gate_check` | `evaluation_release_gate_failed` |
| Prompt regression | `app.evaluation.gate.evaluate_gate`'s already-computed verdict, via the same hook in `app.operations.eval_regression_report` | `evaluation_regression_detected` |

**Deliberately not wired** (no existing aggregate signal to reuse without either a schema change or a synchronous call in a customer-facing hot path, both out of scope for this pass): embedding failure, vector DB failure (not separately tracked from provider failures yet, same limitation `evaluate_alerts` already documents below), email provider failure (would require a network call inside the password-reset/verification request path), billing/webhook failure (billing logic is out of bounds without explicit instruction - see `CLAUDE.md`), unhandled exception spike (would require either a new persisted signal or a synchronous call inside the global exception handler, both rejected as risking customer-facing latency/behaviour change).

This intentionally still does not include a Teams/Discord/PagerDuty/Opsgenie integration - see "Provider abstraction" above for how to add one.

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
