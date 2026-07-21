# Azure CI/CD Release Promotion and Rollback

## Purpose

TASK-068B2 implements the Azure release-orchestration foundation for staging and controlled-production-pilot deployment. It does not deploy production automatically or enable customer pilot widgets.

## Workflow Architecture

Workflows:

- `azure-validate.yml` - static Azure IaC validation, release-tool tests, and pinned Azure CLI Bicep build.
- `azure-deploy-staging.yml` - manual staging release candidate workflow.
- `azure-promote-pilot.yml` - manual protected production-pilot promotion workflow.
- `azure-rollback.yml` - manual rollback planning/execution workflow.
- `verify.yml` - normal repository gate, now including Azure infrastructure validation and release-tool tests.

## GitHub Environments

Required environments:

- `staging`
- `production-pilot`

`production-pilot` must have required reviewers configured in GitHub. This cannot be fully enforced by repository files, so it is an operational prerequisite.

## OIDC Model

Azure workflows use:

```yaml
permissions:
  contents: read
  id-token: write
```

and `azure/login@v2` with environment-scoped variables:

- `AZURE_CLIENT_ID`
- `AZURE_TENANT_ID`
- `AZURE_SUBSCRIPTION_ID`

No Azure client secret or ACR admin password is used.

## Image Build and Digest Strategy

Staging builds:

- `chatbotweb-api:<git-sha>`
- `chatbotweb-web:<git-sha>`

Images are pushed to ACR and resolved to RepoDigest values. Deployment manifests record the digest-bearing image refs.

Do not deploy `latest`.

## Build Once, Promote Same Artifact

Production-pilot promotion consumes the staged workflow artifact:

- deployment manifest
- widget release artifacts
- deployment evidence reports

It does not rebuild API/web images or widget static assets.

Important caveat: widget artifacts currently embed configured public origins. Do not promote staging-origin widget assets to pilot. Use a release manifest whose origins match the target environment or implement safe runtime-origin resolution in a future task.

## Deployment Manifest

`npm run azure:release:manifest` writes:

- `artifacts/deployment-release/manifest.json`
- `artifacts/azure-deployment/<environment>/report.json`

Fields include:

- Git SHA
- API/web image refs and digests
- SDK version
- SDK checksum and SRI
- iframe checksum
- protocol major
- public API version
- Alembic head
- admin readiness status
- pilot verification/readiness status

No secrets are included.

## Migration Execution

`npm run azure:migrate -- --environment staging --image <api-digest> --execute` updates the B1 migration Container Apps Job to the target API image and starts it.

The migration job is manual-triggered and separate from API startup.

## Container App Revision Deployment

`npm run azure:deploy:apps -- --environment staging --api-image <digest> --web-image <digest> --execute` updates API and web Container Apps to new image refs.

Container Apps revision history remains the rollback mechanism. Health and smoke checks must pass before marking a release known-good.

## Static Widget Publication

`npm run azure:widget:publish` validates the B1 widget release manifest/checksums and publishes files in safe order:

1. immutable SDK semantic loader
2. iframe HTML
3. hashed iframe assets
4. SDK major alias
5. alias metadata
6. release manifest

Immutable paths fail if an existing file has a different checksum. Major alias and iframe HTML are mutable.

## Deployed Smoke Hook

`npm run azure:smoke` checks configured deployed HTTPS endpoints:

- API `/health/live`
- API `/health/ready`
- web availability
- widget iframe HTML
- SDK major alias

If endpoint variables are absent, the smoke script records `skipped_no_urls`. TASK-068B4 must replace this with full live FastAPI browser smoke.

## Rollback

`npm run azure:rollback:plan` compares current and target deployment manifests.

Automatic rollback is blocked when:

- protocol major differs
- public API version differs
- database migration head differs

Rollback does not downgrade databases.

## CI Security

- No `pull_request_target` workflows are used for privileged Azure deployment.
- Deployment workflows are manual.
- Production-pilot uses the protected `production-pilot` environment.
- Concurrency prevents overlapping environment deployment/rollback.
- Workflow tests reject `:latest` image references.
- Azure deployment commands use OIDC and environment variables, not committed secrets.

## Current Limitations

- Real Azure what-if was not executed in B2.
- Staging deployment was not executed.
- Full live FastAPI browser smoke remains TASK-068B4.
- Pilot custom domains and DNS remain TASK-068B5.
- Monitoring alert implementation remains TASK-068B3.

## Command Invocation Note

Local npm on Windows may treat unknown forwarded flags as npm configuration and pass values positionally. The Azure scripts support both named and positional arguments for dry-run use. Mutating workflow steps call the Node scripts directly so `--execute` and validation flags are preserved exactly.
