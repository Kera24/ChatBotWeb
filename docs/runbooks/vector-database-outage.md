# Runbook: Vector Database Outage

## Symptoms

Retrieval failing platform-wide; since vectors live in the same Postgres instance as everything else (`docs/adr/0019-postgresql-pgvector-over-dedicated-vector-database.md`), this typically presents as a general Postgres outage, not an isolated vector-store failure.

## Diagnosis

1. Confirm Postgres reachability/health directly (`docker compose -p chatbotweb-prod ps`, connection test).
2. Check disk space (pgvector indexes can be large) and connection pool exhaustion.
3. Check for a long-running query blocking others (a bad `top_k`/similarity query, or a migration left running).

## Recovery

1. Follow `docs/runbooks/database-recovery.md` — since this *is* a Postgres incident given the current architecture (no separate vector store exists yet).
2. If a specific query is the cause, terminate it and identify the request pattern that triggered it.
3. Once `docs/future/QdrantMigration.md` is implemented, this runbook will need to split into a genuinely separate vector-store-outage path — not yet applicable.

## Validation

Retrieval succeeds again; Postgres health checks green; no long-running blocking queries remain.

## Escalation

Sustained/recurring vector-query performance issues escalate to `docs/adr/0020-delay-qdrant-migration.md`'s reconsideration-trigger discussion.

## Post-incident review

Was this attributable to a specific bad query pattern (fixable) or genuine scale pressure (feeds the Qdrant-migration trigger evidence)?
