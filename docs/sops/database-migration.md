# SOP: Database Migration

## Purpose

Change the database schema safely, following the repository's Alembic conventions.

## When to use

Only when explicitly instructed (`CLAUDE.md`: "Never modify database schema or write a migration without being asked to").

## Step-by-step process

1. Numbered-filename convention (`NNNN_description.py`, revision id == filename stem), chained `down_revision` to the current head.
2. Follow the SQLite/Postgres dialect-guard pattern from the most recent existing migration for FK/JSON/Numeric column creation (SQLite test compatibility).
3. Never edit a migration already referenced by another migration's `down_revision` — add a new one instead.
4. Migration must be backward-compatible and forward-safe (per `docs/adr/0018`'s "database rollback is avoided as a routine mechanism" principle) — avoid destructive changes in the same migration as the code that depends on them; prefer expand-then-contract for renames/removals.
5. Run migration preflight before deploying.
6. The one-shot `migrate` job in `docker-compose.prod.yml` runs the migration to head before `api` starts — never rely on every API instance running migrations itself.

## Validation

`npm run api:test` (in-memory SQLite tests use `Base.metadata.create_all`); a real upgrade/downgrade cycle test against the migration.

## Rollback

Prefer forward-fixing over reversing a migration in production; if a schema reversal is truly required, it's a new migration, not an automatic revert of the old one.

## Success criteria

Migration applies cleanly on both SQLite (test) and Postgres (production) dialects; upgrade/downgrade cycle verified; no destructive change without an explicit expand-then-contract plan.
