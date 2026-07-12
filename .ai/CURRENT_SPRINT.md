# Current Sprint

Current phase: Sprint 2C ? Dashboard Integration
Current task: TASK-052

Source sprint plan:

- `implementation-pack/00_Operating_Model/02_Sprint_Plan.md`
- `docs/07_Roadmap/01_MVP_Implementation_Plan.md`
- `docs/00_Foundation/AI_PLATFORM_MANIFESTO.md`
- `implementation-pack/03_AI/03_AI_Core_Architecture.md`
- `docs/adr/0002-provider-abstraction.md`
- `docs/adr/0003-prompt-versioning.md`
- `docs/adr/0004-rag-orchestrator-boundary.md`
- `planning/tasks/TASK-001-complete-monorepo-foundation.md`
- `planning/tasks/TASK-002-backend-foundation.md`
- `planning/tasks/TASK-017-docker-compose-foundation.md`
- `planning/tasks/TASK-018-root-test-and-api-db-hardening.md`
- `planning/tasks/TASK-019-developer-verification-script.md`
- `planning/tasks/TASK-020-ci-verify-workflow.md`
- `planning/tasks/TASK-021-pgvector-foundation.md`
- `planning/tasks/TASK-022-document-chunk-schema.md`
- `planning/tasks/TASK-023-document-management-api-foundation.md`
- `planning/tasks/TASK-024-document-version-api-foundation.md`
- `planning/tasks/TASK-025-chunk-metadata-api-foundation.md`
- `planning/tasks/TASK-026-document-lifecycle-status-transitions.md`
- `planning/tasks/TASK-027-lifecycle-transition-api.md`
- `planning/tasks/TASK-028-audit-event-foundation.md`
- `planning/tasks/TASK-029-audit-event-read-api.md`
- `planning/tasks/TASK-030-api-documentation-update.md`
- `planning/tasks/TASK-031-file-upload-api-foundation.md`
- `planning/tasks/TASK-032-document-text-extraction-foundation.md`
- `planning/tasks/TASK-033-manual-extraction-pipeline-integration.md`
- `planning/tasks/TASK-034-chunking-foundation.md`
- `planning/tasks/TASK-035-embedding-job-foundation.md`
- `planning/tasks/TASK-036-vector-search-foundation.md`
- `planning/tasks/TASK-037-retrieval-context-assembly.md`
- `planning/tasks/TASK-038-prompt-assembly-foundation.md`
- `planning/tasks/TASK-039-ai-provider-framework-architecture.md`
- `planning/tasks/TASK-046-ai-core-foundation-implementation.md`
- `planning/tasks/TASK-047-token-cost-accounting-foundation.md`
- `planning/tasks/TASK-048-provider-execution-hardening.md`
- `planning/tasks/TASK-050-rag-orchestrator-implementation.md`
- `planning/tasks/TASK-049-conversation-message-schema-foundation.md`
- `planning/tasks/TASK-051-conversation-history-read-api.md`
- `planning/tasks/TASK-052-dashboard-conversation-history-integration.md`

## Sprint goal

Connect the dashboard to tenant-scoped conversation history using the implemented API while preserving controlled Expressionism, accessibility, privacy exclusions, and current temporary-auth boundaries.

## Active priorities

1. Centralise dashboard API calls and development auth headers.
2. Track explicit organisation and workspace context in temporary development configuration.
3. Render conversation list/detail views with clear loading, empty, access-denied, missing-config, and retry states.
4. Preserve source citations, answer states, and safe technical execution metadata.
5. Keep public widget, production auth, analytics aggregation, and frontend features outside this task.

## Guardrails

- Do not implement production auth, public widget, live public chat, deletion, export, feedback capture, analytics aggregation, search, streaming, real external LLM providers, prompt editing UI, or model configuration UI.
- Do not scatter development headers across components.
- Do not attach dashboard auth headers to any public-widget client.
- Do not expose raw prompts, secrets, provider internals, or hidden metadata.

## Definition of done for TASK-052

- Dashboard API client foundation exists under `apps/web/lib/api`.
- Development tenant/session configuration exists and is explicit.
- `/conversations` and `/conversations/[conversationId]` routes render API-backed states.
- Conversations navigation item exists alongside Analytics.
- Conversation messages, citations, status badges, and technical details render accessibly.
- Documentation and safe environment placeholders are updated.
- `npm run web:lint`, `npm run web:build`, `npm run api:test`, and `npm run verify` have been run or reported with blockers.

## Next recommended task

Add dashboard conversation feedback/fallback review workflows or introduce a dedicated frontend testing foundation before expanding dashboard integrations.

## Current/Next Planning Task

- `planning/tasks/TASK-052-dashboard-conversation-history-integration.md`
