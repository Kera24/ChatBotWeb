# Grafana / Prometheus / Loki / Tempo VPS Guide

Status: implemented, not required for launch

## Minimum vs. recommended tier

**Minimum** (what runs by default with just `docker-compose.prod.yml`): structured JSON logs (stdout, captured by Docker's `json-file` driver), AI traces persisted in Postgres (`ai_traces` and friends), the existing `/health/live`/`/health/ready` checks, `deployment/monitoring/check.sh`'s uptime/disk/backup cron check, and the `/observability` dashboard/API reading directly from Postgres. This is enough to operate the product and investigate individual requests.

**Recommended** (this stack, `docker-compose.observability.yml`): adds an OpenTelemetry Collector, Prometheus, Loki, Tempo, and Grafana for infra-level dashboards, log search, and distributed traces alongside the AI-specific trace data. Entirely optional - the core product runs fully without it.

## Bringing it up

```
docker compose -f docker-compose.prod.yml -f docker-compose.observability.yml --env-file .env.production up -d
```

Then point the API at the collector in `.env.production`:

```
OTEL_ENABLED=true
OTEL_EXPORTER_OTLP_ENDPOINT=http://otel-collector:4318
```

and set a real `GRAFANA_ADMIN_PASSWORD` (the compose file refuses to start without one - no default is provided).

Grafana is published only on `127.0.0.1:3001` on the host, not to the internet. Reach it via an SSH tunnel (`ssh -L 3001:localhost:3001 <vps-host>`) or add your own Caddy route with basic auth / an access-restricted subdomain if you want browser access without a tunnel. Never expose Grafana directly without authentication in front of it.

## What's provisioned out of the box

- **Datasources**: Prometheus, Tempo, Loki (`deployment/observability/grafana-provisioning/datasources/datasources.yaml`), each with an explicit `uid:` (`Prometheus`/`Tempo`/`Loki`) that the dashboard/alert-rule JSON in this same tree references literally - no manual setup needed. Tempo is provisioned with trace-to-logs and trace-to-metrics correlation, so a trace panel in Grafana can jump straight to the matching Loki logs / Prometheus metrics.
- **Three dashboards** (`deployment/observability/grafana-provisioning/dashboards/*.json`, folder "Conversa"):
  - **Conversa API Overview**: HTTP request rate by route, p95 latency, 5xx rate, unhandled exceptions, a "no traffic" stat panel, and a recent-traces panel.
  - **Conversa AI Observability**: AI request outcomes, AI provider call failure rate, per-stage latency (embedding/retrieval/generation/...), model call latency, token usage, estimated cost, fallback rate, guardrail outcomes, and evaluation/release-gate outcomes.
  - **Conversa Platform Health**: email delivery outcomes/failure rate, unhandled exceptions by type, and a live Loki log panel (error/warning severity).

  Not an exhaustive multi-dashboard suite - build out further dashboards for your own operational needs as they come up (see `docs/architecture/observability.md`'s cardinality policy before adding a new panel/metric).
- **Alert rules** (`deployment/observability/grafana-provisioning/alerting/rules.yaml`, Grafana's own unified alerting, not Alertmanager): elevated 5xx rate, AI provider failure rate, sustained HTTP p95 latency degradation, AI cost burn-rate spike, evaluation/release-gate regression, OTel Collector unavailable, and no-API-telemetry. Every rule aggregates over a time window with a `for:` sustained-condition duration - see `docs/architecture/observability.md`'s "Alert responsibility split" for how these relate to `app.alerting`'s existing per-tenant email/Slack notifications. **No contact point is provisioned** (no real email server/Slack workspace/PagerDuty account exists to configure safely without inventing one) - rules fire and are visible in the Grafana UI regardless, but wiring a real notification destination requires configuring a contact point + notification policy via Grafana's Alerting UI (Alerting -> Contact points), or by adding your own `deployment/observability/grafana-provisioning/alerting/contact-points.yaml` following Grafana's provisioning schema.

## Resource estimate (small VPS)

Approximate combined footprint for all five services at controlled-pilot traffic volumes (see ADR `0018`), on top of the core product's own `docker-compose.prod.yml` footprint:

| Service | CPU limit | Memory limit |
|---|---|---|
| otel-collector | 0.5 | 384MB |
| prometheus | 0.5 | 512MB |
| tempo | 0.5 | 384MB |
| loki | 0.25 | 256MB |
| grafana | 0.25 | 256MB |
| **Total** | **~2 vCPU** | **~1.8GB** |

A VPS with 4 vCPU / 8GB RAM comfortably runs the core product (`docker-compose.prod.yml`) plus this full stack. On a smaller instance, consider running only the OTel Collector + Prometheus + Grafana (skip Loki/Tempo) if log/trace search isn't needed yet - structured JSON logs are still fully readable via `docker compose logs` without Loki.

## Retention

- Prometheus: 15 days (`--storage.tsdb.retention.time=15d`).
- Tempo: 7 days (`block_retention: 168h`).
- Loki: 7 days (`retention_period: 168h`).

All configured for local filesystem storage (no S3/object store) - appropriate for a single VPS, not for horizontal scaling. Increase retention only if disk headroom allows; monitor disk pressure (see the Alert Threshold Guide).

## Networking

These services join the `internal` network already defined in `docker-compose.prod.yml` (the same network `api` uses), so the collector can receive OTLP from the API without any port published to the internet. Only Grafana publishes a host port, and only on `127.0.0.1`.

## Health/readiness checks

`./deployment/observability/check.sh [--json]` checks container health plus each service's own readiness endpoint (the OTel Collector's `health_check` extension on :13133, Prometheus's `/-/healthy`, Tempo's `/ready`, Loki's `/ready`, Grafana's `/api/health`) - same exit-code/output convention as `deployment/monitoring/check.sh` (0 = healthy, 1 = a check failed, one line per check). Run it after `docker compose ... up -d` to confirm the stack actually came up, and optionally from the same cron/systemd-timer schedule as the core product's health check. This stack being down never affects `deployment/monitoring/check.sh`'s own result - the two are independent, matching this stack's fully-optional status.

## What this stack does NOT include

- **Log shipping from the `api`/`web` containers into Loki** - now included via a different mechanism than originally planned: rather than a Promtail sidecar scraping Docker's `json-file` logs, `app.operations.telemetry` bridges Python's root logger directly into the OTel logs pipeline (a `LoggingHandler` -> `LoggerProvider` -> OTLP -> the collector's existing `logs` pipeline -> Loki), active whenever `OTEL_ENABLED=true`. `docker compose logs` remains available regardless, and is unaffected either way.
- **Alertmanager** - Grafana's own unified alerting (`deployment/observability/grafana-provisioning/alerting/rules.yaml`) is provisioned instead of a separate Alertmanager instance; see the Alert Threshold Guide for the complementary application-level, per-tenant threshold evaluator and proactive delivery layer (`app.observability.alerts` + `app.alerting`) this platform also uses.
- A pre-configured Grafana contact point/notification policy - see "What's provisioned out of the box" above.
- High-availability or clustered configurations for any of these components - single-instance, single-VPS only.

## See also

`docs/architecture/observability.md`'s "Full telemetry architecture" section for the complete signal-flow diagram, the cardinality policy new metrics must follow, the alert responsibility split between this stack and `app.alerting`, the investigation workflow, the customer-vs-internal visibility model, and future managed-backend (Azure Monitor/Datadog/Honeycomb/New Relic) portability notes.
