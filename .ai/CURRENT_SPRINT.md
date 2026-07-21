# Current Sprint

Current phase:
Sprint 3H - Controlled Production Pilot Deployment

Current task:
TASK-068B1 - Azure Production Infrastructure-as-Code and Hosting Foundation

## Guardrails

- Implement Azure infrastructure-as-code and repository configuration foundation only.
- Do not deploy production infrastructure, change DNS, provision live resources, add production credentials, or create customer data.
- Prefer validation, dry-run, and what-if workflows over live changes.
- Preserve Azure architecture from ADR-0018, exact-origin policy, tenant isolation, pilot controls, immutable SDK delivery, and public/private configuration boundaries.
- Next recommended task: TASK-068B2 - Azure CI/CD Deployment Pipeline, Database Migrations, Release Promotion, and Rollback Automation.
