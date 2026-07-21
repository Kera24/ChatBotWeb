# TASK-060A: Anonymous Public Session Architecture

Status: Complete
Type: Architecture task
Sprint: Sprint 3B - Public Access Foundation

## Objective

Design the anonymous public-session subsystem for future widget and browser-based public channels without implementing runtime code, database models, migrations, public endpoints, Redis session storage, widget code, CORS changes, or RAG calls.

The design must securely bind public browser sessions to one public credential, organisation, workspace, channel, origin, and policy profile. Public session traffic must never trust client-supplied tenant IDs or raw conversation IDs.

## Required Reading

- `docs/00_Foundation/AI_PLATFORM_MANIFESTO.md`
- `implementation-pack/02_Architecture/01_Public_Access_Layer_Architecture.md`
- `implementation-pack/02_Architecture/02_Credential_Widget_Configuration_Architecture.md`
- `implementation-pack/02_Architecture/03_Origin_Validation_Architecture.md`
- `implementation-pack/02_Architecture/04_Distributed_Rate_Limiting_Architecture.md`
- `implementation-pack/07_Security/02_Public_Widget_Security_Architecture.md`
- `implementation-pack/00_Operating_Model/03_Architecture_Implementation_Task_Pattern.md`
- `docs/adr/0005-public-widget-security-boundary.md`
- `docs/adr/0006-public-access-layer-bounded-context.md`
- `docs/adr/0007-public-credential-storage-and-widget-configuration.md`
- `docs/adr/0008-origin-validation-policy.md`
- `docs/adr/0009-distributed-rate-limiting-policy.md`
- `planning/tasks/TASK-055-public-widget-security-architecture.md`
- `planning/tasks/TASK-056A-public-access-layer-architecture.md`
- `planning/tasks/TASK-056B-public-access-layer-implementation.md`
- `planning/tasks/TASK-057A-credential-widget-configuration-architecture.md`
- `planning/tasks/TASK-057B-credential-widget-configuration-implementation.md`
- `planning/tasks/TASK-058A-origin-validation-architecture.md`
- `planning/tasks/TASK-058B-origin-validation-implementation.md`
- `planning/tasks/TASK-059A-distributed-rate-limiting-architecture.md`
- `planning/tasks/TASK-059B-distributed-rate-limiting-implementation.md`
- `docs/04_Engineering/Public_Access_Layer_Foundation.md`
- `docs/04_Engineering/Public_Credentials_and_Widget_Configuration.md`
- `docs/04_Engineering/Origin_Validation.md`
- `docs/04_Engineering/Distributed_Rate_Limiting.md`
- `.ai/PROJECT_CONTEXT.md`
- `.ai/CURRENT_SPRINT.md`

## Deliverables

- `implementation-pack/02_Architecture/05_Anonymous_Public_Session_Architecture.md`
- `docs/adr/0010-anonymous-public-session-security.md`
- `.ai/CURRENT_SPRINT.md` updated to TASK-060A
- `.ai/PROJECT_CONTEXT.md` updated with anonymous public-session guardrails

## Architecture Decisions

- Use opaque public bearer session tokens with a public token ID and high-entropy secret component.
- Store only token ID and keyed secret hash server-side; never store the full token in plaintext.
- Use PostgreSQL as the source of truth for session records, with optional Redis cache acceleration later.
- Bind every session to credential, organisation, workspace, channel, environment, policy profile, and validated origin context.
- Validate sessions after credential resolution, tenant resolution, request validation, origin validation, and rate limiting.
- Lazily attach the existing tenant-scoped conversation on the first accepted message instead of creating empty conversations on session creation.
- Do not trust client-submitted conversation IDs for public widget messages.
- Prefer sessionStorage for the future iframe/widget MVP, with in-memory storage as stricter mode and no default localStorage or cookie session design.

## Explicit Non-Goals

Do not implement:

- SQLAlchemy session model
- Alembic migration
- token generator
- hashing code
- session repository/service
- gateway session stage
- public session endpoint
- Redis session cache
- widget storage code
- RAG calls
- cleanup job
- CORS changes

## Future Implementation Sequence

1. TASK-060B: public session schema and token service implementation.
2. Session repository/service with tenant-safe lookup and lifecycle transitions.
3. Public Access Gateway session-stage integration.
4. Session creation internal contracts and validation flow.
5. Atomic message-count and first-conversation attachment protections.
6. Cleanup and retention extension points.
7. Public session endpoint only after route-level public API architecture approval.
8. Security tests for token storage, binding, replay, expiry, and safe errors.

## Acceptance Criteria

TASK-060A is complete when:

- Token model is selected.
- Persistent session schema is defined.
- Credential, origin, channel, and tenant binding are explicit.
- Session lifecycle and expiry are defined.
- Conversation relationship is decided.
- Concurrency and replay risks are covered.
- Safe errors and events are defined.
- Threat model and diagrams are complete.
- ADR-0010 records the decision.
- No runtime code or public endpoint is added.

## Verification

Run:

```bash
git diff --check
```
