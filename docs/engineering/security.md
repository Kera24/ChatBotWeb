# Security — Current / Future / Out of Scope

## Current

No single consolidated security doc exists yet; security posture is currently spread across several sources, which this doc indexes rather than duplicates:

- **AI safety principles**: `docs/00_Foundation/AI_PLATFORM_MANIFESTO.md` (canonical, still current).
- **Rate limiting**: `apps/api/app/access/rate_limit/`, `apps/api/app/auth/rate_limit.py`, config in `Settings` (`RATE_LIMIT_IDENTITY_SECRET`, `RATE_LIMIT_REDIS_PREFIX`, `RATE_LIMIT_LOCAL_FALLBACK_ENABLED`) — governed by ADR 0009 (distributed rate limiting policy, status Proposed).
- **CORS / origin validation**: `apps/api/app/main.py`, `apps/api/app/api/v1/public_widget.py`, governed by ADR 0008 (origin validation policy) and ADR 0005 (public widget security boundary).
- **Secret redaction**: `apps/api/app/operations/logging.py::redact()`/`pseudonymous_identifier()`, extended for AI trace content by `apps/api/app/observability/redaction.py` (`docs/architecture/observability.md`).
- **Tenant isolation**: enforced structurally through `require_organisation_role()` RBAC checks on every route and `organisation_id`/`workspace_id` scoping on every query — not a bolt-on filter.
- **Public widget security**: ADRs 0005-0013 cover the full public-access bounded context (credential storage, anonymous session security, message/RAG boundary).

## Future

- A consolidated `docs/engineering/security.md` → deeper security architecture doc (this file may become that, or spawn one) once ADR 0009's rate-limiting policy moves from Proposed to Accepted.
- Enterprise SSO and compliance controls — see `docs/future/EnterpriseSSO.md` and `docs/future/ComplianceRoadmap.md`.

## Out of scope (not planned)

- A bug-bounty program or formal penetration-testing cadence — not scheduled; would be a compliance-roadmap decision, not an engineering-doc decision.
