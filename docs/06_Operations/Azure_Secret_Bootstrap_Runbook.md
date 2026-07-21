# Azure Secret Bootstrap Runbook

## Purpose

This runbook defines how production and staging secrets are bootstrapped for the Azure controlled pilot without committing secret values to the repository.

## Secret Store

Use Azure Key Vault created by the Bicep foundation.

No production secret belongs in:

- Git history
- `.env` files
- Bicep parameter files
- Docker images
- browser bundles
- CI logs

## Required Secret Names

API:

- `api-database-url`
- `api-redis-url`
- `rate-limit-identity-secret`
- `public-session-token-hash-secret`
- `public-message-idempotency-hash-secret`
- `preview-grant-signing-secret`

Web:

- `web-auth-secret`

Provider/runtime:

- AI provider credentials according to approved provider abstraction
- SMTP/email credentials if email is enabled
- storage credentials only if managed identity cannot be used
- monitoring connection string only if not supplied through managed configuration

## PostgreSQL Password

The PostgreSQL administrator password is supplied as a secure deployment parameter. It is not checked into `*.bicepparam` files.

Use the approved secret manager/password process to provide:

```bash
AZURE_POSTGRES_ADMIN_PASSWORD=<secret>
```

## GitHub Actions OIDC

Use GitHub OIDC rather than a long-lived Azure client secret.

Bootstrap requirements:

- Azure app/service principal or deployment identity
- Federated credential scoped to this repository and GitHub environment
- Minimal role assignments for infrastructure deployment
- Separate `staging` and `production-pilot` GitHub environments

Required GitHub environment variables:

- `AZURE_CLIENT_ID`
- `AZURE_TENANT_ID`
- `AZURE_SUBSCRIPTION_ID`
- `AZURE_LOCATION`

Required GitHub environment secrets:

- `AZURE_POSTGRES_ADMIN_PASSWORD`

Do not create a shared global production secret bucket.

## Runtime Managed Identity Access

Grant Container App identities only the roles they need:

- Key Vault Secrets User for secret references
- AcrPull for image pull
- Storage Blob Data Contributor or Reader where required by application storage behavior

## Rotation

Rotation steps:

1. Create new secret version in Key Vault.
2. Deploy/restart affected Container App revision if required.
3. Verify readiness.
4. Run synthetic smoke.
5. Disable old version when safe.
6. Record operational evidence.

Never print secret values during rotation.

## Emergency Secret Response

If a secret is suspected compromised:

1. Disable affected widget/message surface if applicable.
2. Rotate the secret.
3. Redeploy/restart affected services.
4. Run pilot verification and synthetic smoke.
5. Preserve safe request IDs and audit evidence.
6. Review logs for exposure without extracting tokens unnecessarily.
