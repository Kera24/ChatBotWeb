# Current Sprint

Current phase: Sprint 3B - Public Access Foundation
Current task: TASK-058A - Origin Validation Architecture

Source sprint plan:

- `docs/00_Foundation/AI_PLATFORM_MANIFESTO.md`
- `implementation-pack/00_Operating_Model/01_Engineering_Operating_Model.md`
- `implementation-pack/00_Operating_Model/02_Sprint_Plan.md`
- `implementation-pack/00_Operating_Model/03_Architecture_Implementation_Task_Pattern.md`
- `implementation-pack/02_Architecture/01_Public_Access_Layer_Architecture.md`
- `implementation-pack/02_Architecture/02_Credential_Widget_Configuration_Architecture.md`
- `implementation-pack/02_Architecture/03_Origin_Validation_Architecture.md`
- `implementation-pack/07_Security/02_Public_Widget_Security_Architecture.md`
- `docs/adr/0005-public-widget-security-boundary.md`
- `docs/adr/0006-public-access-layer-bounded-context.md`
- `docs/adr/0007-public-credential-storage-and-widget-configuration.md`
- `docs/adr/0008-origin-validation-policy.md`
- `docs/04_Engineering/Public_Access_Layer_Foundation.md`
- `docs/04_Engineering/Public_Credentials_and_Widget_Configuration.md`
- `planning/epics/EPIC-004-public-access-layer.md`
- `planning/tasks/TASK-055-public-widget-security-architecture.md`
- `planning/tasks/TASK-056A-public-access-layer-architecture.md`
- `planning/tasks/TASK-056B-public-access-layer-implementation.md`
- `planning/tasks/TASK-057A-credential-widget-configuration-architecture.md`
- `planning/tasks/TASK-057B-credential-widget-configuration-implementation.md`
- `planning/tasks/TASK-058A-origin-validation-architecture.md`

## Sprint goal

Introduce the reusable Public Access Layer bounded context and continue the public access foundation with explicit credential, widget configuration, and origin-validation boundaries before exposing public runtime endpoints.

## Active priorities

1. Keep public/external channels separate from authenticated dashboard and internal development APIs.
2. Route future website widget, public REST API, Slack, Teams, WhatsApp, voice, MCP, and external channels through the Public Access Layer.
3. Ensure public/external tenant context is resolved server-side and never trusted from client-supplied tenant IDs.
4. Preserve existing RAG Orchestrator, AI Core, tenant isolation, and current implemented APIs.
5. Keep TASK-058A limited to origin-validation architecture, ADR, and planning artifacts only.

## Guardrails

- Do not implement runtime origin validation, middleware, CORS changes, public endpoints, Redis limiters, widget UI, session tokens, public RAG, or DNS verification in TASK-058A.
- Do not let public or external channels call RAG Orchestrator directly.
- Do not let public traffic reuse dashboard authentication, development headers, or dashboard tenant parameters.
- Widget state-changing endpoints require a validated `Origin` before future implementation.
- Missing `Origin` fails closed for widget session and message endpoints.
- Origin validation is not authentication; credential resolution, sessions, rate limits, and tenant isolation remain separate controls.
- Partner API credentials use separate secret authentication rules and do not rely on browser-origin validation.
- Do not create credentials automatically.
- Do not make workspaces public by default.
- Treat widget public keys as identifiers, not secrets.

## Definition of done for TASK-058A

- Origin-validation responsibilities and non-responsibilities are defined.
- Header trust model is explicit.
- Normalisation, exact matching, wildcard matching, and environment rules are complete.
- Missing-Origin and Referer fallback decisions are recorded.
- CORS relationship is documented without implementation.
- Cache, failure, security event, threat model, and future test strategy are defined.
- ADR-0008 records the chosen policy.
- No runtime code is added.

## Next recommended task

Implement `TASK-058B` for origin normalisation and matcher foundations, still without exposing public widget message/session endpoints unless a separate approved task explicitly adds them.

## Current/Next Planning Task

- `planning/tasks/TASK-058A-origin-validation-architecture.md`
