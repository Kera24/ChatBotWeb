# Azure GitHub OIDC Bootstrap Runbook

## Purpose

This runbook defines the one-time Azure/GitHub identity setup required for TASK-068B2 workflows.

No Azure client secret is used.

## GitHub Environments

Create GitHub environments:

- `staging`
- `production-pilot`

`production-pilot` must require manual reviewers.

## Azure Identity

Create an Entra application/service principal or equivalent deployment identity for GitHub Actions.

Recommended separation:

- staging deployment identity scoped to staging resources
- production-pilot deployment identity scoped to pilot resources

## Federated Credential

Create federated credentials for this repository and environment subjects.

Conceptual subject patterns:

- `repo:Kera24/ChatBotWeb:environment:staging`
- `repo:Kera24/ChatBotWeb:environment:production-pilot`

Follow current GitHub/Azure OIDC setup guidance at implementation time.

## GitHub Variables

Set per environment:

- `AZURE_CLIENT_ID`
- `AZURE_TENANT_ID`
- `AZURE_SUBSCRIPTION_ID`
- `AZURE_LOCATION`
- `AZURE_ACR_NAME`
- `AZURE_ACR_LOGIN_SERVER`
- `AZURE_WIDGET_STORAGE_ACCOUNT`
- `STAGING_APP_URL` / `PILOT_APP_URL`
- `STAGING_API_URL` / `PILOT_API_URL`
- `STAGING_WIDGET_URL` / `PILOT_WIDGET_URL`
- `STAGING_CDN_URL` / `PILOT_CDN_URL`

Use only the variables appropriate to each environment.

## GitHub Secrets

Set per environment:

- `AZURE_POSTGRES_ADMIN_PASSWORD`

Application runtime secrets belong in Azure Key Vault, not GitHub workflow logs.

## Azure Roles

Deployment identity requires least-privilege roles for:

- deployment group/subscription operations for the environment scope
- ACR push/pull as needed
- Container Apps update/job start
- Storage Blob Data Contributor for widget static upload
- Key Vault secret reference setup where needed

Avoid subscription Owner for routine deployments.

## Validation

Run the manual `Azure Infrastructure What-If` workflow before any deployment workflow. It should authenticate through OIDC and produce no credential output.
