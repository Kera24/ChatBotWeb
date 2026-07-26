# Azure Staging Live Validation and Rollback Evidence

Status: TASK-068B4 repository harness implemented; live Azure staging execution not recorded in this document until evidence artifacts show successful execution.

## Implementation Facts

TASK-068B4 adds a staging-only validation harness:

- `npm run azure:staging:validate`
- `npm run azure:staging:browser`
- `npm run azure:staging:telemetry`
- `npm run azure:staging:alerts`
- `npm run azure:staging:rollback-drill`
- `.github/workflows/azure-validate-staging.yml`

The scripts reject non-staging environments for direct B4 execution and write redacted evidence under `artifacts/azure-staging-validation/`.

## Live Resource Evidence

Actual Azure staging resource evidence must come from `artifacts/azure-staging-validation/infrastructure.json` after a credentialed run. Safe fields include deployment ID/name, timestamp, region, resource group, resource names, Front Door endpoint, Container App hostnames, Key Vault name, PostgreSQL hostname, storage endpoint, monitoring resource names, and what-if summary.

Do not manually copy secret values, connection strings, access tokens, database passwords, message text, answers, citations, provider prompts, or draft values into this document.

## Validation Architecture

The B4 workflow is manual only and scoped to GitHub environment `staging`. It runs repository gates before Azure validation and uses GitHub OIDC for Azure login. Ordinary PR validation remains static and does not deploy or mutate Azure.

The live checks cover:

- Azure prerequisite and what-if evidence
- full-stack browser smoke through staging Front Door where configured
- synthetic Alpha/Beta tenant isolation
- session, origin, token, cache, CORS, and header validation
- server-side telemetry and privacy canary checks
- workbook, KQL, availability, and alert routing validation
- rollback planning, rollback health, and roll-forward restoration evidence

## Provider Strategy

Staging may use either the actual configured pilot provider with tightly bounded synthetic requests or an architecture-approved deterministic staging provider. If deterministic provider output is used, evidence must state that infrastructure, RAG, session, retrieval, and isolation were real while external provider behavior was not fully validated.

## Source Maps and Browser Telemetry

Public widget and SDK source maps remain disabled. Public widget and admin browser clients do not send direct Application Insights telemetry, session replay, DOM recording, input capture, or behavioral analytics. Staging browser evidence relies on server-side telemetry and synthetic browser assertions.

## Backup and Restore

B4 must verify PostgreSQL backup/PITR configuration before migrations. A separate restore drill may be performed against temporary staging resources when cost and access permit. If not executed, evidence must classify restore testing as deferred, not passed.

## Current Classification

Until a credentialed staging run produces live evidence, the classification is:

`staging deployment blocked before execution`

This is not production-pilot readiness.
