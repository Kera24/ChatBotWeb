# Current Sprint

Current phase: Sprint 3B - Public Access Foundation
Current task: TASK-059A - Distributed Rate Limiting Architecture

Source sprint plan:

- `docs/00_Foundation/AI_PLATFORM_MANIFESTO.md`
- `implementation-pack/00_Operating_Model/01_Engineering_Operating_Model.md`
- `implementation-pack/00_Operating_Model/02_Sprint_Plan.md`
- `implementation-pack/00_Operating_Model/03_Architecture_Implementation_Task_Pattern.md`
- `implementation-pack/02_Architecture/01_Public_Access_Layer_Architecture.md`
- `implementation-pack/02_Architecture/02_Credential_Widget_Configuration_Architecture.md`
- `implementation-pack/02_Architecture/03_Origin_Validation_Architecture.md`
- `implementation-pack/02_Architecture/04_Distributed_Rate_Limiting_Architecture.md`
- `implementation-pack/07_Security/02_Public_Widget_Security_Architecture.md`
- `docs/adr/0005-public-widget-security-boundary.md`
- `docs/adr/0006-public-access-layer-bounded-context.md`
- `docs/adr/0007-public-credential-storage-and-widget-configuration.md`
- `docs/adr/0008-origin-validation-policy.md`
- `docs/adr/0009-distributed-rate-limiting-policy.md`
- `docs/04_Engineering/Public_Access_Layer_Foundation.md`
- `docs/04_Engineering/Public_Credentials_and_Widget_Configuration.md`
- `docs/04_Engineering/Origin_Validation.md`
- `planning/epics/EPIC-004-public-access-layer.md`
- `planning/tasks/TASK-055-public-widget-security-architecture.md`
- `planning/tasks/TASK-056A-public-access-layer-architecture.md`
- `planning/tasks/TASK-056B-public-access-layer-implementation.md`
- `planning/tasks/TASK-057A-credential-widget-configuration-architecture.md`
- `planning/tasks/TASK-057B-credential-widget-configuration-implementation.md`
- `planning/tasks/TASK-058A-origin-validation-architecture.md`
- `planning/tasks/TASK-058B-origin-validation-implementation.md`
- `planning/tasks/TASK-059A-distributed-rate-limiting-architecture.md`

## Sprint goal

Introduce the reusable Public Access Layer bounded context and continue the public access foundation with credential, widget configuration, origin-validation, and distributed rate-limiting architecture before exposing public runtime endpoints.

## Active priorities

1. Keep public/external channels separate from authenticated dashboard and internal development APIs.
2. Route future website widget, public REST API, Slack, Teams, WhatsApp, voice, MCP, and external channels through the Public Access Layer.
3. Ensure public/external tenant context is resolved server-side and never trusted from client-supplied tenant IDs.
4. Preserve existing RAG Orchestrator, AI Core, tenant isolation, and current implemented APIs.
5. Keep TASK-059A limited to distributed rate-limiting architecture, ADR, and planning artifacts only.

## Guardrails

- Do not implement Redis client code, Lua scripts, rate-limit middleware, public routes, sessions, RAG calls, quota persistence, billing, or widget UI in TASK-059A.
- No public message/session endpoint may bypass the future distributed limiter.
- Forwarded client-IP headers are trusted only from configured proxies.
- Short-window rate limits are separate from daily/monthly quotas.
- Security-sensitive Redis uncertainty fails closed unless architecture explicitly permits a constrained read-only fallback.
- Do not let public or external channels call RAG Orchestrator directly.
- Do not let public traffic reuse dashboard authentication, development headers, or dashboard tenant parameters.
- Widget state-changing endpoints require a validated `Origin` before future public message/session processing.
- Missing `Origin` fails closed for widget session and message endpoints.
- Origin validation is not authentication; credential resolution, sessions, rate limits, and tenant isolation remain separate controls.
- Partner API credentials use separate secret authentication rules and do not rely on browser-origin validation.

## Definition of done for TASK-059A

- Distributed rate-limiting responsibilities and non-responsibilities are defined.
- Token bucket is selected as the MVP algorithm.
- Limit dimensions and combination rules are explicit.
- Redis key and identity model avoids raw secrets, IPs, sessions, and message content.
- Trusted client-IP extraction model is defined.
- Gateway order is clear.
- Failure policies are explicit by endpoint category.
- Quota boundary is separate from short-window rate limits.
- Threat model, diagrams, and test strategy are complete.
- ADR-0009 records the decision.
- No runtime code is added.

## Next recommended task

Implement `TASK-059B` for rate-limit contracts, policy models, Redis client foundation, token-bucket implementation, trusted IP extraction, and gateway integration. Public message/session endpoints must remain out of scope until sessions and abuse controls are approved.

## Current/Next Planning Task

- `planning/tasks/TASK-059A-distributed-rate-limiting-architecture.md`
