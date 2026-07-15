# Current Sprint

Current phase: Sprint 3C - Public Channels
Current task: TASK-061A - Public Widget Session Endpoint Architecture

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
- `implementation-pack/02_Architecture/06_Public_Widget_Session_Endpoint_Architecture.md`
- `implementation-pack/07_Security/02_Public_Widget_Security_Architecture.md`
- `docs/adr/0005-public-widget-security-boundary.md`
- `docs/adr/0006-public-access-layer-bounded-context.md`
- `docs/adr/0007-public-credential-storage-and-widget-configuration.md`
- `docs/adr/0008-origin-validation-policy.md`
- `docs/adr/0009-distributed-rate-limiting-policy.md`
- `docs/adr/0010-anonymous-public-session-security.md`
- `docs/adr/0011-public-widget-session-endpoint.md`
- `docs/04_Engineering/Public_Access_Layer_Foundation.md`
- `docs/04_Engineering/Public_Credentials_and_Widget_Configuration.md`
- `docs/04_Engineering/Origin_Validation.md`
- `docs/04_Engineering/Distributed_Rate_Limiting.md`
- `docs/04_Engineering/Anonymous_Public_Sessions.md`
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
- `planning/tasks/TASK-060B-anonymous-public-session-implementation.md`
- `planning/tasks/TASK-061A-public-widget-session-endpoint-architecture.md`

## Sprint goal

Design the first public widget endpoint boundary before any runtime route is exposed. The endpoint is session creation only and must reuse the Public Access Gateway security stages.

## Active priorities

1. Keep public/external channels separate from authenticated dashboard and internal development APIs.
2. Define `POST /api/v1/widget/{public_key}/sessions` as a minimal public session-creation endpoint.
3. Require credential resolution, tenant resolution, Origin validation, rate limiting, and anonymous session creation through the Public Access Gateway.
4. Preserve credential, origin-validation, distributed rate-limiting, anonymous session, RAG Orchestrator, AI Core, and tenant-isolation boundaries.
5. Keep TASK-061A strictly limited to architecture, planning, ADR, and context documentation.

## Guardrails

- Do not implement a FastAPI public route, widget channel adapter, public schemas, CORS helper/middleware, RAG call, conversation creation, public config endpoint, widget SDK/UI, migration, or Redis change in TASK-061A.
- The first public endpoint is session creation only.
- Public session creation must use the Public Access Gateway.
- The endpoint must not create a conversation, accept a message, or call RAG.
- No public route may accept tenant IDs, workspace IDs, conversation IDs, policy overrides, dashboard bearer tokens, or dashboard development headers.
- Public widget routes use no cookies and require a validated `Origin`.
- Dynamic CORS behaviour is architectural only in TASK-061A and must be implemented in a later approved implementation task.
- Do not let public traffic reuse dashboard authentication, development headers, or dashboard tenant parameters.

## Definition of done for TASK-061A

- Endpoint boundary is explicit.
- Request is minimal and excludes tenant, conversation, message, PII, origin, and policy override input.
- Gateway usage is mandatory.
- CORS policy is defined but not implemented.
- Credential/config eligibility, session policy, response contract, safe errors, and rate-limit dimensions are documented.
- Threat model, failure matrix, and diagrams are complete.
- ADR-0011 records the route design decision.
- `git diff --check` passes.
- No runtime code or public endpoint is added.

## Next recommended task

TASK-061B should implement the public widget session creation endpoint exactly within the TASK-061A boundary. Public widget message endpoints must wait until a later approved public API task wires session validation and RAG orchestration together.
