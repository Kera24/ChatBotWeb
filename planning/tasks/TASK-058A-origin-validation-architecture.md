# TASK-058A - Origin Validation Architecture

## Task ID

TASK-058A

## Linked epic/story

- EPIC-004 - Public Access Layer
- ADR-0005 - Public Widget Security Boundary
- ADR-0006 - Public Access Layer Bounded Context
- ADR-0007 - Public Credential Storage and Widget Configuration
- ADR-0008 - Origin Validation Policy

## Type

Architecture task. Must be approved before TASK-058B implementation starts.

## Status

Proposed architecture complete.

## Objective

Design the runtime origin-validation system used by future widget and browser-based public channels.

The design is strict enough for production use, compatible with local development, and reusable across future browser-based channels.

## Required reading

- `docs/00_Foundation/AI_PLATFORM_MANIFESTO.md`
- `implementation-pack/02_Architecture/01_Public_Access_Layer_Architecture.md`
- `implementation-pack/02_Architecture/02_Credential_Widget_Configuration_Architecture.md`
- `implementation-pack/07_Security/02_Public_Widget_Security_Architecture.md`
- `implementation-pack/00_Operating_Model/03_Architecture_Implementation_Task_Pattern.md`
- `docs/adr/0005-public-widget-security-boundary.md`
- `docs/adr/0006-public-access-layer-bounded-context.md`
- `docs/adr/0007-public-credential-storage-and-widget-configuration.md`
- `planning/tasks/TASK-055-public-widget-security-architecture.md`
- `planning/tasks/TASK-056A-public-access-layer-architecture.md`
- `planning/tasks/TASK-056B-public-access-layer-implementation.md`
- `planning/tasks/TASK-057A-credential-widget-configuration-architecture.md`
- `planning/tasks/TASK-057B-credential-widget-configuration-implementation.md`
- `docs/04_Engineering/Public_Access_Layer_Foundation.md`
- `docs/04_Engineering/Public_Credentials_and_Widget_Configuration.md`
- `.ai/PROJECT_CONTEXT.md`
- `.ai/CURRENT_SPRINT.md`

## Deliverables

- `implementation-pack/02_Architecture/03_Origin_Validation_Architecture.md`
- `docs/adr/0008-origin-validation-policy.md`
- `.ai/CURRENT_SPRINT.md` updated to Sprint 3B / TASK-058A
- `.ai/PROJECT_CONTEXT.md` updated with origin-validation guardrails

## Scope

Origin validation owns:

- `Origin` header parsing.
- Limited `Referer` fallback policy.
- Exact-origin matching.
- Controlled subdomain wildcard matching.
- Scheme and port matching.
- Environment-aware localhost rules.
- Missing-Origin decisions.
- Browser/non-browser distinction.
- Normalised origin comparison.
- Public error generation.
- Security event and metric definitions.
- Cache behaviour for allowed origins.

Origin validation does not own:

- Credential resolution.
- Rate limiting.
- Anonymous sessions.
- RAG.
- Widget rendering.
- Dashboard authentication.
- DNS ownership verification.
- Public routes.
- CORS implementation.

## Architecture decisions

- Use `Origin` as the primary browser-origin signal.
- Require `Origin` for future widget session and message endpoints.
- Fail closed when `Origin` is missing for widget session and message endpoints.
- Disable `Referer` fallback for state-changing widget endpoints.
- Allow policy-gated `Referer` fallback only for future public configuration GET if explicitly approved.
- Never infer client origin from `Host`.
- Trust forwarded headers only from configured trusted proxies.
- Canonicalise origins as scheme, hostname, and effective port.
- Match exact origins before one-label wildcard subdomains.
- Reject production HTTP, public-suffix wildcards, global wildcards, wildcard localhost, and wildcard IPs.
- Treat origin validation as a browser control, not authentication.

## Proposed future modules

Future implementation should add:

```text
apps/api/app/access/origin_validation/
  __init__.py
  contracts.py
  normalisation.py
  matcher.py
  service.py
  errors.py
  cache.py
```

## Proposed future contracts

`OriginValidationRequest` should include:

- credential ID
- credential environment
- policy profile
- `Origin` header
- optional `Referer` header
- optional trusted proxy context
- request method
- channel
- endpoint kind

`OriginValidationResult` should include:

- allowed flag
- canonical origin
- matched origin ID
- match type
- decision source
- reason code
- safe metadata

## Runtime order

1. Credential resolved.
2. Policy resolved.
3. Origin headers extracted.
4. Input normalised.
5. Environment restrictions applied.
6. Exact matches checked.
7. Wildcard matches checked.
8. Missing-Origin policy applied.
9. Decision emitted.
10. Security event recorded.
11. CORS layer consumes decision.
12. Request proceeds or fails safely.

## Future implementation sequence

1. `TASK-058B` origin normalisation and matcher implementation.
2. Public Access Gateway integration.
3. Admin origin cache invalidation hooks.
4. CORS policy integration.
5. Security and tenant-isolation tests.
6. Future domain ownership verification architecture.

## Explicit non-implementation constraint

Do not implement in this task:

- Python origin matcher.
- Middleware.
- CORS changes.
- Database migrations.
- Public routes.
- Redis.
- Sessions.
- Widget UI.
- DNS verification.

## Verification

Run:

```bash
git diff --check
```

No automated runtime tests are required because this is planning-only.

## Acceptance criteria

- [x] Header trust model is explicit.
- [x] Normalisation rules are complete.
- [x] Exact and wildcard matching are defined.
- [x] Missing-Origin policy is chosen.
- [x] Environment behaviour is defined.
- [x] CORS relationship is clear.
- [x] Cache and failure policies are explicit.
- [x] Threat model and diagrams are complete.
- [x] ADR records the decision.
- [x] No runtime code is added.
