# Current Sprint

Current phase: Sprint 3A ? Public Access Layer Architecture
Current task: TASK-056A

Source sprint plan:

- `docs/00_Foundation/AI_PLATFORM_MANIFESTO.md`
- `implementation-pack/00_Operating_Model/01_Engineering_Operating_Model.md`
- `implementation-pack/00_Operating_Model/02_Sprint_Plan.md`
- `implementation-pack/00_Operating_Model/03_Architecture_Implementation_Task_Pattern.md`
- `implementation-pack/02_Architecture/01_Public_Access_Layer_Architecture.md`
- `implementation-pack/03_AI/03_AI_Core_Architecture.md`
- `implementation-pack/07_Security/02_Public_Widget_Security_Architecture.md`
- `docs/adr/0005-public-widget-security-boundary.md`
- `docs/adr/0006-public-access-layer-bounded-context.md`
- `planning/epics/EPIC-004-public-access-layer.md`
- `planning/tasks/TASK-055-public-widget-security-architecture.md`
- `planning/tasks/TASK-056A-public-access-layer-architecture.md`
- `planning/tasks/TASK-056B-public-access-layer-implementation.md`

## Sprint goal

Introduce the reusable Public Access Layer bounded context and formalise the architecture-before-implementation task pattern for Sprint 3 and future major features.

## Active priorities

1. Keep public/external channels separate from authenticated dashboard and internal development APIs.
2. Route future website widget, public REST API, Slack, Teams, WhatsApp, voice, MCP, and external channels through the Public Access Layer.
3. Ensure public/external tenant context is resolved server-side and never trusted from client-supplied tenant IDs.
4. Require architecture tasks to be approved before implementation tasks begin.
5. Preserve existing RAG Orchestrator, AI Core, tenant isolation, and current implemented APIs.

## Guardrails

- Do not implement public endpoints, migrations, Redis limiters, widget UI, session tokens, public RAG, channel adapters, or product features in TASK-056A.
- Do not let public or external channels call RAG Orchestrator directly.
- Do not let public traffic reuse dashboard authentication, development headers, or dashboard tenant parameters.
- Do not start TASK-056B until TASK-056A is approved.

## Definition of done for TASK-056A

- Public Access Layer architecture document exists.
- ADR-0006 records the bounded-context decision.
- EPIC-004 and TASK-056A/TASK-056B exist.
- Operating model and templates require architecture-before-implementation for major features.
- `.ai/PROJECT_CONTEXT.md` records the new gate for future Codex sessions.

## Next recommended task

Review and approve TASK-056A, then implement only the internal Public Access Layer contracts and service skeleton in TASK-056B.

## Current/Next Planning Task

- `planning/tasks/TASK-056A-public-access-layer-architecture.md`
