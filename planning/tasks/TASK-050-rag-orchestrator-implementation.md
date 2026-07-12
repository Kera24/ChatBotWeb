# TASK-050 - RAG Orchestrator Implementation

Status: Implemented

## Objective

Implement the internal RAG orchestration service that coordinates tenant validation, conversation persistence, retrieval context assembly, prompt-registry rendering through AI Core, provider-neutral execution, citation persistence, and stable internal responses.

## Scope Implemented

- Reusable `app.ai.rag_orchestrator` service with explicit input/output contracts.
- Internal dashboard-test endpoint: `POST /api/v1/workspaces/{workspace_id}/rag/answer?organisation_id=...`.
- Conversation creation or tenant-scoped conversation reuse.
- User message persistence before retrieval/execution.
- Tenant-scoped retrieval context assembly using the existing retrieval service.
- Prompt rendering and provider execution through existing AI Core service and registries.
- Assistant message persistence with model, prompt, usage, cost, latency, execution ID, finish reason, and error metadata.
- Citation persistence for authorised retrieved context candidates.
- Safe empty-retrieval fallback with zero citations and no provider call.
- Provider failure/timeout handling that preserves user message and failed assistant state.
- Endpoint RBAC using existing development membership policy for `org_owner`, `client_admin`, and `viewer`.
- Tests covering success, existing conversation reuse, tenant isolation, RBAC, fallback, limits, metadata, and provider failure/timeout.

## Out of Scope

- Real OpenAI-compatible provider.
- Public website widget endpoint.
- Streaming.
- Conversation memory or history injection.
- Query rewriting, hybrid search, reranking, or citation LLM validation.
- Tool calling, multi-agent workflows, billing, analytics UI, or background workers.

## Verification

Required commands:

- `npm run api:test`
- `npm run verify`
- `docker compose up -d postgres redis`
- `cd apps/api && python -m alembic upgrade head` with PostgreSQL `DATABASE_URL`
