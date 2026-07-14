# Current Sprint

Current phase: Sprint 3B - Public Access Foundation
Current task: TASK-057A - Credential and Widget Configuration Architecture

Source sprint plan:

- `docs/00_Foundation/AI_PLATFORM_MANIFESTO.md`
- `implementation-pack/00_Operating_Model/01_Engineering_Operating_Model.md`
- `implementation-pack/00_Operating_Model/02_Sprint_Plan.md`
- `implementation-pack/00_Operating_Model/03_Architecture_Implementation_Task_Pattern.md`
- `implementation-pack/02_Architecture/01_Public_Access_Layer_Architecture.md`
- `implementation-pack/02_Architecture/02_Credential_Widget_Configuration_Architecture.md`
- `implementation-pack/03_AI/03_AI_Core_Architecture.md`
- `implementation-pack/07_Security/02_Public_Widget_Security_Architecture.md`
- `docs/adr/0005-public-widget-security-boundary.md`
- `docs/adr/0006-public-access-layer-bounded-context.md`
- `docs/adr/0007-public-credential-storage-and-widget-configuration.md`
- `planning/epics/EPIC-004-public-access-layer.md`
- `planning/tasks/TASK-055-public-widget-security-architecture.md`
- `planning/tasks/TASK-056A-public-access-layer-architecture.md`
- `planning/tasks/TASK-056B-public-access-layer-implementation.md`
- `planning/tasks/TASK-057A-credential-widget-configuration-architecture.md`

## Sprint goal

Introduce the reusable Public Access Layer bounded context and define the persistent credential/widget configuration architecture needed before any public widget endpoint exists.

## Active priorities

1. Keep public/external channels separate from authenticated dashboard and internal development APIs.
2. Route future website widget, public REST API, Slack, Teams, WhatsApp, voice, MCP, and external channels through the Public Access Layer.
3. Ensure public/external tenant context is resolved server-side and never trusted from client-supplied tenant IDs.
4. Preserve existing RAG Orchestrator, AI Core, tenant isolation, and current implemented APIs.
5. Keep TASK-057A limited to architecture and planning for credential storage, widget configuration, origin storage, lifecycle, rotation, RBAC, and safe public config.

## Guardrails

- Do not implement public endpoints, migrations, Redis limiters, widget UI, session tokens, public RAG, real channel adapters, or product features in TASK-057A.
- Do not let public or external channels call RAG Orchestrator directly.
- Do not let public traffic reuse dashboard authentication, development headers, or dashboard tenant parameters.
- Do not create credentials automatically.
- Do not make workspaces public by default.
- Treat widget public keys as identifiers, not secrets.
- Show secret-bearing credential values only once and store only hashes.

## Definition of done for TASK-057A

- Credential and widget configuration architecture document exists.
- ADR-0007 records the public credential storage and widget configuration decision.
- TASK-057A records scope, RBAC, test strategy, implementation sequence, and non-implementation constraints.
- `.ai/PROJECT_CONTEXT.md` records public credential guardrails.
- No code, migration, endpoint, or widget UI is added.

## Next recommended task

Review and approve TASK-057A, then create/implement TASK-057B for credential/widget schema implementation only.

## Current/Next Planning Task

- `planning/tasks/TASK-057A-credential-widget-configuration-architecture.md`
