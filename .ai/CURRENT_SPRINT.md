# Current Sprint

Current phase: Sprint 3C - Public Channels
Current task: TASK-061B - Public Widget Session Endpoint Implementation

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
- `docs/04_Engineering/Public_Widget_Session_Endpoint.md`
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
- `planning/tasks/TASK-061B-public-widget-session-endpoint-implementation.md`

## Sprint goal

Implement the first public widget endpoint as session creation only, using the Public Access Gateway security stages and preserving the no-message/no-RAG boundary.

## Active priorities

1. Keep public/external channels separate from authenticated dashboard and internal development APIs.
2. Expose only `POST /api/v1/widget/{public_key}/sessions` and its route-scoped `OPTIONS` preflight.
3. Require credential resolution, tenant resolution, published widget configuration, Origin validation, rate limiting, and anonymous session creation through the Public Access Gateway.
4. Preserve credential, origin-validation, distributed rate-limiting, anonymous session, RAG Orchestrator, AI Core, and tenant-isolation boundaries.
5. Keep TASK-061B strictly limited to the public widget session creation endpoint, route-scoped CORS, gateway wiring, tests, and docs.

## Guardrails

- Do not implement a public widget config endpoint, public widget message endpoint, RAG call, retrieval call, AI Core call, conversation creation, chat-message persistence, widget SDK/UI, migration, Redis session cache, hard idempotency store, cookies, or global permissive CORS in TASK-061B.
- The first public endpoint is session creation only.
- Public session creation must use the Public Access Gateway.
- The endpoint must not create a conversation, accept a message, or call RAG.
- No public route may accept tenant IDs, workspace IDs, conversation IDs, policy overrides, dashboard bearer tokens, or dashboard development headers.
- Public widget routes use no cookies and require a validated `Origin`.
- Route-scoped dynamic CORS must echo only validated origins and must not use wildcard origins or credentials.
- Do not let public traffic reuse dashboard authentication, development headers, or dashboard tenant parameters.

## Definition of done for TASK-061B

- Public widget session route and preflight are implemented under `/api/v1/widget/{public_key}/sessions` only.
- Request is minimal and excludes tenant, conversation, message, PII, origin, and policy override input.
- Gateway usage is mandatory and implemented.
- Route-scoped dynamic CORS is implemented.
- Credential/config eligibility, session policy, response contract, safe errors, and rate-limit dimensions are documented.
- Tests cover success, safe rejection, Origin/CORS, rate limiting, no conversation creation, response exclusions, and route boundary preservation.
- `git diff --check` passes.
- No public widget message/config endpoint, RAG call, conversation creation, widget SDK/UI, migration, or global CORS middleware is added.

## Next recommended task

The next task should design the public widget message endpoint architecture. It must wait for an approved architecture task before wiring session validation to RAG orchestration.