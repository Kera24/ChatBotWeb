# Current Sprint

Current phase: Sprint 3B - Public Access Foundation
Current task: TASK-060B - Anonymous Public Session Implementation

Source sprint plan:

- `docs/00_Foundation/AI_PLATFORM_MANIFESTO.md`
- `implementation-pack/00_Operating_Model/01_Engineering_Operating_Model.md`
- `implementation-pack/00_Operating_Model/02_Sprint_Plan.md`
- `implementation-pack/00_Operating_Model/03_Architecture_Implementation_Task_Pattern.md`
- `implementation-pack/02_Architecture/01_Public_Access_Layer_Architecture.md`
- `implementation-pack/02_Architecture/02_Credential_Widget_Configuration_Architecture.md`
- `implementation-pack/02_Architecture/03_Origin_Validation_Architecture.md`
- `implementation-pack/02_Architecture/04_Distributed_Rate_Limiting_Architecture.md`
- `implementation-pack/02_Architecture/05_Anonymous_Public_Session_Architecture.md`
- `implementation-pack/07_Security/02_Public_Widget_Security_Architecture.md`
- `docs/adr/0005-public-widget-security-boundary.md`
- `docs/adr/0006-public-access-layer-bounded-context.md`
- `docs/adr/0007-public-credential-storage-and-widget-configuration.md`
- `docs/adr/0008-origin-validation-policy.md`
- `docs/adr/0009-distributed-rate-limiting-policy.md`
- `docs/adr/0010-anonymous-public-session-security.md`
- `docs/04_Engineering/Public_Access_Layer_Foundation.md`
- `docs/04_Engineering/Public_Credentials_and_Widget_Configuration.md`
- `docs/04_Engineering/Origin_Validation.md`
- `docs/04_Engineering/Distributed_Rate_Limiting.md`
- `planning/epics/EPIC-004-public-access-layer.md`
- `planning/tasks/TASK-055-public-widget-security-architecture.md`
- `planning/tasks/TASK-056A-public-access-layer-architecture.md`
- `planning/tasks/TASK-056B-public-access-layer-implementation.md`
- `planning/tasks/TASK-057A-credential-widget-configuration-architecture.md`
- `planning/tasks/TASK-057B-credential-widget-configuration-implementation.md`
- `planning/tasks/TASK-058A-origin-validation-architecture.md`
- `planning/tasks/TASK-058B-origin-validation-implementation.md`
- `planning/tasks/TASK-059A-distributed-rate-limiting-architecture.md`
- `planning/tasks/TASK-059B-distributed-rate-limiting-implementation.md`
- `planning/tasks/TASK-060A-anonymous-public-session-architecture.md`

## Sprint goal

Continue the Public Access Foundation by implementing the internal anonymous public-session foundation before any widget session, widget message, or public RAG endpoint is exposed.

## Active priorities

1. Keep public/external channels separate from authenticated dashboard and internal development APIs.
2. Ensure public session tokens never contain trusted tenant IDs or raw conversation IDs.
3. Bind future public sessions to credential, organisation, workspace, channel, environment, policy, and validated origin context.
4. Preserve credential, origin-validation, distributed rate-limiting, RAG Orchestrator, AI Core, and tenant-isolation boundaries.
5. Keep TASK-060B strictly limited to internal session model, token, repository/service, gateway-stage, tests, and docs.

## Guardrails

- Do not implement public session endpoints, public message endpoints, public config endpoints, Redis session cache, widget code, RAG calls, cleanup jobs, or CORS changes in TASK-060B.
- Public session tokens must not contain trusted tenant IDs.
- Widget message requests must validate a credential-bound public session.
- Browsers must not submit trusted conversation IDs for public widget message processing.
- Public sessions are designed as PostgreSQL-backed and revocable.
- Session validation occurs after credential resolution, tenant resolution, request validation, origin validation, and rate limiting.
- No public session endpoint may be added before TASK-060A is reviewed and approved and a later implementation task explicitly authorises it.
- Do not let public traffic reuse dashboard authentication, development headers, or dashboard tenant parameters.

## Definition of done for TASK-060B

- Token model is selected.
- Persistent session schema is defined.
- Credential, origin, channel, and tenant binding are explicit.
- Session lifecycle and expiry are defined.
- Conversation relationship is decided.
- Concurrency and replay risks are covered.
- Safe errors and events are defined.
- Threat model and diagrams are complete.
- ADR-0010 records the decision.
- `git diff --check` passes.
- No runtime code or public endpoint is added.

## Next recommended task

TASK-061A should define the public widget session endpoint architecture before any route is exposed. Public widget message endpoints must wait until a later approved public API task wires credential resolution, origin validation, rate limiting, session validation, and RAG orchestration together.
