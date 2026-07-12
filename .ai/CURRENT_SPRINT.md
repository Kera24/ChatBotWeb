# Current Sprint

Current phase: Sprint 2B ? AI Core Foundation
Current task: TASK-050

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

## Sprint goal

Implement the internal reusable RAG orchestration path that coordinates retrieval, prompt rendering, AI Core execution, conversation persistence, citations, fallback, and provider failure handling without exposing the public widget endpoint.

## Active priorities

1. Keep the orchestrator tenant-safe and provider-neutral.
2. Reuse existing retrieval, prompt registry, AI Core, accounting, and conversation services.
3. Preserve existing document pipeline, vector search, prompt assembly, RBAC, and API behaviour.
4. Use deterministic mock provider behaviour only; no external network LLM calls.
5. Persist conversation state consistently for success, fallback, and provider failure paths.

## Guardrails

- Do not implement real OpenAI, Anthropic, Gemini, Azure OpenAI, Ollama, or other provider integrations yet.
- Do not expose a public widget endpoint.
- Do not implement streaming, memory/history injection, query rewriting, hybrid search, reranking, citation LLM validation, tool calling, agents, billing, analytics UI, or background workers.
- Do not hide mutable registries, health stores, accounting repositories, or orchestrator dependencies in module globals.
- Do not break tenant isolation, existing RBAC, current APIs, document pipeline, retrieval behaviour, prompt behaviour, AI Core provider neutrality, accounting, health handling, or existing tests.

## Definition of done for TASK-050

- RAG orchestrator service exists with explicit request/result contracts.
- Internal dashboard-test RAG answer endpoint exists under workspace scope.
- User and assistant messages are persisted in deterministic sequence.
- Retrieved citation candidates are persisted only for assistant messages and tenant-scoped chunks.
- Empty retrieval produces a persisted fallback answer and zero citations.
- Provider failures preserve the user message and failed assistant state.
- Tests cover success, conversation reuse, tenant isolation, RBAC, fallback, limits, metadata, provider failure, and timeout handling.
- `npm run api:test`, `npm run verify`, and PostgreSQL Alembic upgrade have been run or reported with blockers.

## Next recommended task

Add the first dashboard chat-history/read model or prepare the public widget API boundary only after TASK-050 is reviewed.

## Current/Next Planning Task

- `planning/tasks/TASK-050-rag-orchestrator-implementation.md`
