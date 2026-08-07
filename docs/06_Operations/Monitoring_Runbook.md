# Monitoring Runbook (low-cost, VPS deployment)

Goal: enough visibility to catch a launch-blocking failure before a user
reports it, without a mandatory paid managed service. Everything below is
free/open-source or has a generous free tier.

## What already exists in the application

| Signal | Where | Notes |
|---|---|---|
| Structured operational events | `app/operations/logging.py` (`log_operational_event`, `redact()`) | JSON-shaped, with a secret-redaction pass (`authorization`, `cookie`, `api_key`, `session_token`, widget keys, `pss_` session tokens) - but only for code paths that explicitly call `log_operational_event`, not a global logging middleware. Ad hoc `logger.*` calls elsewhere are not guaranteed to pass through `redact()` - worth an audit pass if you add new logging. |
| Liveness | `GET /health/live` | Always 200 if the process is up |
| Readiness | `GET /health/ready` | Checks database, embedding provider, and (as of this audit) Redis. Redis failure is reported but does not flip overall status to `not_ready` - see `apps/api/app/api/health.py` and the accompanying test `test_readiness_reports_redis_failure_visibly_without_failing_closed`. |
| Guardrail triggers | `app/ai/guardrails/*` | Each guardrail decision is part of the evaluation/response pipeline; visibility today is via application logs, not a dedicated metrics counter - see "Gaps" below. |
| Billing webhook failures | `app/api/v1/billing_webhook.py` | Returns 400/503 on bad signature/missing secret; Stripe's own Dashboard shows webhook delivery failures/retries independently - use that as the source of truth, it's free and already exists. |

## Container-level: logs, health, restarts

- **Log rotation**: `docker-compose.prod.yml` sets `json-file` logging with `max-size: 10m, max-file: 5` on every service (`x-logging` anchor) - bounded to 50MB/service, no external log shipper required to avoid filling disk.
- **Container health**: every service has a `healthcheck:`; `docker compose -f docker-compose.prod.yml ps` shows `healthy`/`unhealthy` per container.
- **Restart policy**: `restart: unless-stopped` on all long-running services - a crashed container comes back without manual intervention; `docker compose logs <service> --since 1h` for the crash reason.

## Uptime / external monitoring

`scripts/vps-smoke.mjs` hits `/health/live`, `/health/ready`, the web root,
the widget iframe, and the SDK loader, and exits non-zero on failure - point
any of these at it, or hit the URLs directly:

- **Free-tier uptime checkers** (UptimeRobot, Better Uptime free tier, etc.): point at `https://<API_DOMAIN>/health/ready` and `https://<WEB_DOMAIN>/`. 5-minute interval is enough for early access.
- **Self-hosted cron alternative** (zero external dependency): run `deployment/monitoring/check.sh` via cron/systemd timer (see below) and alert on non-zero exit through whatever channel you already have (email via cron's own MAILTO, a webhook curl, etc).

## `deployment/monitoring/check.sh`

Single script covering container health, API readiness (which itself checks
DB/embedding/Redis), disk space, and backup freshness (fails if no Postgres
backup younger than 26h exists) - see the script for exact checks. Run it:

```bash
./deployment/monitoring/check.sh          # human-readable, one line per check
./deployment/monitoring/check.sh --json   # machine-readable, for a log shipper/alert webhook
```

Cron example (every 5 minutes, mails on any non-zero exit via cron's default behavior when the command produces output):

```cron
*/5 * * * * conversa cd /home/conversa/app && ./deployment/monitoring/check.sh
```

## Database and disk

- `deployment/monitoring/check.sh`'s `disk_space` check covers the repo root filesystem; Postgres/Redis data volumes live under Docker's data root (`/var/lib/docker/volumes`), typically the same filesystem on a single-VPS setup - if you separate them onto another mount, extend the script's `df -Pk` target accordingly.
- Postgres itself: `docker compose -f docker-compose.prod.yml exec postgres psql -U $POSTGRES_USER -d $POSTGRES_DB -c "SELECT pg_size_pretty(pg_database_size(current_database()));"` for a quick manual size check; no automated DB-growth alerting is included in this launch - add one before the database is large enough that "disk fills up" becomes a plausible near-term failure mode.

## Gaps / things this launch does *not* give you (be aware, not necessarily blocking)

- **No dedicated metrics counters for guardrail-trigger rate or fallback rate in production.** The evaluation framework computes these against the golden dataset (`app/evaluation/metrics`), but there's no equivalent live dashboard counting "% of live public-widget answers that fell back" in real traffic. If a high fallback rate in production would be a business-critical signal, add a counter before/soon after launch - not implemented here because it requires choosing a metrics backend, which is a scope decision beyond an audit.
- **No dedicated log aggregation/search.** `docker compose logs` and cron-mailed check output are sufficient for early-access single-VPS scale; if/when volume makes `docker compose logs` impractical, a low-cost option is shipping the existing `json-file` logs to a self-hosted Loki+Grafana stack or a generous-free-tier SaaS (both keep this "low-cost" per the brief) - not set up here since it's a meaningful new moving part, not a config toggle.
- **Azure Monitor/Application Insights code paths exist but are unused on the VPS** (`app/operations/telemetry.py`, gated by `AZURE_MONITOR_OPEN_TELEMETRY_ENABLED=false` by default) - intentionally left inert per the brief's instruction not to reintroduce Azure costs.
