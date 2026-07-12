# TASK-049 - Conversation Message Schema Foundation

Status: Implemented

## Objective

Create the database and repository foundation for tenant-scoped conversations, ordered messages, and assistant citations without implementing the final RAG/chat endpoint, widget endpoint, retrieval invocation, or AI provider invocation.

## Scope Implemented

- `chat_sessions` model for tenant/workspace-scoped conversation lifecycle state.
- `chat_messages` model for deterministic message ordering and assistant execution metadata.
- `citations` model linking assistant messages to tenant-scoped source chunks, documents, and document versions.
- Alembic migration `0005_conversation_schema` for PostgreSQL with SQLite smoke-test compatibility.
- Tenant-safe conversation repository functions that never fetch conversations, messages, or citations by ID alone.
- Conversation service for starting conversations, appending user and assistant messages, status transitions, last-message timestamps, and assistant citation attachment.
- Tests covering tenant isolation, sequencing, duplicate sequence rejection, citation validation, assistant metadata, monetary precision, status lifecycle, and migration upgrade.
- Engineering documentation for the conversation data model.

## Out of Scope

- Final chat endpoint.
- Public widget endpoint.
- RAG orchestration or retrieval invocation.
- AI provider invocation from the conversation service.
- Conversation memory summarisation.
- Streaming.
- Tool-message execution beyond future-compatible role storage.
- Billing, analytics UI, database-backed provider health, or database-backed usage accounting.

## Verification

Required commands:

- `docker compose up -d postgres redis`
- `cd apps/api && python -m alembic upgrade head`
- `npm run api:test`
- `npm run verify`
