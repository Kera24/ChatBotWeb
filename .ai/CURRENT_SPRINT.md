# Current Sprint

Current phase: Sprint 2B - AI Core Foundation.
Current task: TASK-046.

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

## Sprint goal

Create the first reusable provider-neutral AI Core foundation without connecting to an external LLM provider and without exposing a public chat or final RAG answer endpoint.

## Active priorities

1. Keep AI Core provider-neutral and testable.
2. Preserve existing document pipeline, embeddings, vector search, retrieval context, and prompt assembly behaviour.
3. Use deterministic mock generation for local development and automated tests.
4. Keep provider, model, and prompt registries explicit and isolated.
5. Preserve existing temporary development RBAC boundaries and tenant isolation.

## Guardrails

- Do not implement real OpenAI, Anthropic, Gemini, Azure OpenAI, Ollama, or other provider integrations yet.
- Do not add external LLM API keys or secrets.
- Do not expose a public chat endpoint.
- Do not implement chat sessions, message storage, final grounded-answer generation, widget, billing, or analytics UI.
- Do not hide mutable registries in module globals.
- Do not break tenant isolation, existing RBAC, current APIs, document pipeline, retrieval behaviour, or existing tests.

## Definition of done for TASK-046

- Provider-neutral AI contracts exist and serialise cleanly.
- Mock provider is deterministic, local-only, and failure/timeout testable.
- Provider, model, and prompt registries are explicit and isolated.
- Default grounded answer prompt is registered as an immutable prompt version.
- AI Core service can render prompts, resolve model/provider, execute mock generation, and return metadata.
- Internal `POST /api/v1/ai/generate` endpoint is super-admin only.
- Local development documentation exists.
- `npm run api:test` and `npm run verify` have been run or reported with any blockers.

## Next recommended task

Define the next implementation slice for real-provider adapter planning or AI Core persistence only after TASK-046 is reviewed.

## Current/Next Planning Task

- `planning/tasks/TASK-046-ai-core-foundation-implementation.md`
