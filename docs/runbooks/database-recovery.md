# Runbook: Database Recovery

## Symptoms

Postgres unreachable, corrupted, or in an inconsistent state.

## Diagnosis

1. Check container health and logs for the `postgres` service.
2. Check disk space (a full disk is a common Postgres-outage cause on a single-VPS deployment).
3. Determine if this is a transient issue (restart resolves it) or requires restore from backup.

## Recovery

1. Transient: restart the `postgres` container; verify data integrity after restart.
2. Corruption/data loss: restore via `deployment/backup/restore.sh` — requires explicit `--db`/`--uploads` paths and interactive confirmation (or `--yes`); terminates connections, drops/recreates the DB, replays the dump.
3. Run `database_migration preflight` after any restore, per `docs/architecture/deployment.md`.
4. Restart `api` only after Postgres is confirmed healthy (the one-shot `migrate` job must complete cleanly first in a full-stack restart).

## Validation

Postgres health check green; migration preflight clean; application smoke checks pass; spot-check recently active tenant data for completeness.

## Escalation

Any data loss beyond the last backup's retention window is a major incident — escalate immediately and assess customer impact/notification needs.

## Post-incident review

How much data (if any) was lost between the last backup and the incident? Consider whether backup frequency (currently daily-cadence-oriented, 14-day retention) needs revisiting.
