# Azure Database Migration Runbook

## Purpose

This runbook covers Alembic migration execution for Azure staging and controlled-production-pilot deployments.

Migrations are executed by a single Container Apps Job. They are not run automatically by every API replica.

## Migration Head

Determine current Alembic head locally:

```bash
python -m alembic heads
```

Deployment manifests also record the head automatically through `npm run azure:release:manifest`.

## Execution

Dry-run planning:

```bash
npm run azure:migrate -- --environment staging --image <api-image-digest>
```

Execute after approval:

```bash
npm run azure:migrate -- --environment staging --image <api-image-digest> --execute
```

## Required Preconditions

- Repository gates passed
- Infrastructure validation passed
- Key Vault database secret exists
- PostgreSQL backup/restore point confirmed according to environment policy
- Migration reviewed for destructive operations
- No other migration/deployment running for the environment

## Failure Behavior

If migration fails:

1. Stop deployment.
2. Do not deploy the new API/web revisions.
3. Do not update SDK major alias.
4. Preserve current running release.
5. Capture safe migration job status/log references.
6. Escalate with request ID/workflow run ID.

Do not automatically downgrade the database.

## pgvector

pgvector is enabled by Alembic revision `0002_enable_pgvector_extension`:

```sql
CREATE EXTENSION IF NOT EXISTS vector;
```

The database role used by migrations must be allowed to create the extension or a one-time DBA/bootstrap process must run it before application migrations.

## Expand/Migrate/Contract

If future migrations are not backward-compatible, split them into explicit phases:

1. expand schema
2. deploy compatible app
3. migrate data
4. deploy final app behavior
5. contract old schema after rollback window

Do not collapse a destructive migration into a single production-pilot deploy.
