# Azure Widget Domain and TLS Runbook

## Purpose

This runbook defines the DNS and TLS process for the Azure controlled pilot. It is planning/runbook content only until a later task explicitly authorizes DNS changes.

## Required Hostnames

| Host | Purpose | Target |
| --- | --- | --- |
| `app.<domain>` | authenticated dashboard/admin | Azure Front Door |
| `api.<domain>` | authenticated API | Azure Front Door |
| `widget-api.<domain>` | public widget API | Azure Front Door |
| `widget.<domain>` | widget iframe app | Azure Front Door |
| `cdn.<domain>` | SDK and static widget assets | Azure Front Door |

## DNS Records

Use CNAME records from each hostname to the Azure Front Door endpoint host.

Front Door custom-domain validation may require additional TXT/CNAME records. Create only the records shown by Azure during custom-domain validation.

## TLS

Preferred policy:

- Azure-managed Front Door certificates
- HTTPS redirect enabled
- HSTS only after successful validation
- No manually committed certificate or private key

## Validation Order

1. Deploy or validate Front Door endpoint.
2. Add one staging custom domain first.
3. Add required validation record.
4. Wait for validation.
5. Confirm managed certificate issuance.
6. Confirm HTTPS response.
7. Confirm route origin behavior.
8. Repeat for remaining hostnames.
9. Run header/cache checks.
10. Enable HSTS only after all HTTPS checks pass.

## CORS/CSP Relationships

- `app.<domain>` may call `api.<domain>` through authenticated API CORS policy.
- `widget.<domain>` may call `widget-api.<domain>` for public widget routes.
- Customer host origins are validated by application-level allowed-origin policy.
- `cdn.<domain>` serves SDK/static assets.
- No wildcard production API CORS.

## HSTS Guardrail

Do not enable long-lived HSTS before:

- certificates are issued
- HTTP-to-HTTPS redirects are correct
- widget iframe and SDK asset hosts respond correctly
- rollback plan is confirmed

## No External DNS Automation in B1

TASK-068B1 does not configure external DNS providers. DNS changes require a later approved deployment task and operator review.
