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

- **Datasources**: Prometheus, Tempo, Loki (`deployment/observability/grafana-provisioning/datasources/datasources.yaml`) - no manual setup needed.
- **One starter dashboard** ("Conversa API Overview" - `deployment/observability/grafana-provisioning/dashboards/conversa-api-overview.json`): HTTP request rate by route, p95 latency, 5xx rate, and a recent-traces panel. This is intentionally minimal, not a polished multi-dashboard suite - build out further dashboards for your own operational needs as they come up.

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

## What this stack does NOT include

- Log shipping from the `api`/`web` containers into Loki (Docker's `json-file` driver captures stdout; wiring a log-forwarding sidecar like Promtail is a follow-up if Loki-based log search becomes a priority - `docker compose logs` remains available regardless).
- Alertmanager / Prometheus alerting rules - see the Alert Threshold Guide for the application-level threshold evaluator this platform uses instead (structured JSON alert events, not a separate alerting service).
- High-availability or clustered configurations for any of these components - single-instance, single-VPS only.
