# Azure Infrastructure Deployment Runbook

## Purpose

This runbook describes how operators will validate and deploy the Azure infrastructure foundation for staging and controlled-production-pilot environments.

TASK-068B1 does not deploy production infrastructure. Use this runbook only when a later TASK-068B implementation explicitly authorizes deployment.

## Prerequisites

- Approved Azure subscription
- Approved region, initially `australiaeast` unless changed by architecture review
- Azure CLI installed
- Bicep support available through Azure CLI
- GitHub OIDC bootstrap completed
- Required GitHub environments configured:
  - `staging`
  - `production-pilot`
- Required Key Vault secret values prepared but not committed
- Approved production domain before pilot custom-domain deployment

## 1. Select Subscription

```bash
az account set --subscription <subscription-id>
az account show
```

Confirm the subscription is non-production before staging work, or the approved controlled-pilot subscription before pilot work.

## 2. Validate Bicep Locally

```bash
npm run infra:azure:validate
```

This must pass before any Azure what-if or deployment.

## 3. Run What-If

Staging:

```bash
export AZURE_SUBSCRIPTION_ID=<subscription-id>
export AZURE_POSTGRES_ADMIN_PASSWORD=<secret-from-approved-vault-or-password-manager>
npm run infra:azure:whatif -- staging
```

Pilot:

```bash
export AZURE_SUBSCRIPTION_ID=<subscription-id>
export AZURE_POSTGRES_ADMIN_PASSWORD=<secret-from-approved-vault-or-password-manager>
npm run infra:azure:whatif -- pilot
```

Do not proceed if what-if shows unexpected destructive changes.

## 4. Review Resource Changes

Review:

- Resource group name
- ACR
- Container Apps environment
- API and web Container Apps
- Migration job
- PostgreSQL Flexible Server
- Storage accounts
- Key Vault
- Front Door
- Optional Redis
- Log Analytics and Application Insights

Check that no secret values appear in outputs.

## 5. Deploy Staging

Staging deployment belongs to TASK-068B2/B4. When authorized, use reviewed Bicep and secure parameters only. After deployment:

- Record outputs
- Insert Key Vault secrets
- Configure role assignments
- Build and deploy images
- Run migration job
- Publish widget static artifacts
- Run live staging smoke

## 6. Configure DNS When Approved

DNS records are not changed by B1. Follow `docs/06_Operations/Azure_Widget_Domain_and_TLS_Runbook.md` after domain approval.

## 7. Deploy Pilot Only With Approval

Pilot deployment requires:

- Staging deployment success
- Live staging browser smoke success
- Rollback target identified
- Admin release gate pass
- Widget pilot readiness pass
- Security review of what-if
- Manual `production-pilot` environment approval

## 8. Rollback and Teardown

Infrastructure rollback should use Bicep changes reviewed through what-if. Runtime rollback uses the widget/API/web rollback process in `docs/06_Operations/Widget_Rollback_Runbook.md` and the Azure automation added in TASK-068B2.

Do not tear down pilot PostgreSQL, Key Vault, or document storage without explicit data-retention approval.
