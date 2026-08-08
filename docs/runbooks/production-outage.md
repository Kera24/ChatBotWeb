# Runbook: Production Outage

## Symptoms

API/web unreachable, elevated 5xx rate, or `/observability` showing zero traffic where traffic is expected.

## Diagnosis

1. Check Caddy/edge status (`deployment/caddy/Caddyfile`) — is TLS/routing itself down, or is `api`/`web` unresponsive behind it?
2. Check `docker compose -p chatbotweb-prod ps` for container health.
3. Check the most recent deployment — is this correlated with a release?
4. Check Postgres/Redis reachability (both are hard dependencies for `api`).

## Recovery

1. If correlated with a recent deploy: `docs/sops/rollback.md` immediately.
2. If a container crashed: restart it; if it crash-loops, check logs for the root cause before just restarting repeatedly.
3. If Postgres/Redis is down: see `docs/runbooks/database-recovery.md` / restart Redis (stateless for rate-limiting/cache purposes — safe to restart).
4. If the edge (Caddy/TLS) is the problem: check certificate validity and `WEB_DOMAIN`/`API_DOMAIN`/`WIDGET_DOMAIN` env config.

## Validation

Smoke checks pass; `/observability` shows traffic flowing again; 5xx rate back to baseline.

## Escalation

If root cause isn't found within the outage-severity SLA window, escalate for a second engineer; if it's a VPS-level failure (disk, network, host), see `docs/runbooks/vps-recovery.md`.

## Post-incident review

Document root cause, time-to-detect, time-to-recover; identify what alert (if any) should have fired sooner; add to `docs/operations/continuous-improvement.md`'s loop.
