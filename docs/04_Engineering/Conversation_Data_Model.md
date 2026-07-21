# Conversation Data Model

Version: 0.1
Status: Implemented Foundation

## Purpose

The conversation data model stores tenant-scoped chat sessions, ordered messages, and citation links for future grounded RAG answers. It is a persistence foundation only; it does not call retrieval, prompt assembly, AI providers, streaming, billing, or analytics.

## Tables

### chat_sessions

`chat_sessions` represents one conversation in an organisation workspace.

Important fields:

- `organisation_id` and `workspace_id` define tenant scope.
- `channel` records the source surface: `dashboard_test`, `widget`, `api`, or `future_integration`.
- `status` records lifecycle: `active`, `completed`, `abandoned`, or `archived`.
- `anonymous_user_id` and `external_user_id` support public and future integration identities without requiring production auth in this slice.
- `title` and `metadata_json` are optional descriptive metadata.
- `started_at`, `last_message_at`, and `ended_at` track lifecycle timing.

### chat_messages

`chat_messages` stores immutable conversation turns.

Important fields:

- `organisation_id`, `workspace_id`, and `conversation_id` enforce tenant and parent scope.
- `role` supports `system`, `user`, `assistant`, and future-compatible `tool` messages.
- `sequence_number` is unique per conversation and determines display/order semantics.
- Assistant metadata fields preserve model, provider, prompt, execution, usage, estimated cost, latency, finish reason, and error state.
- `metadata_json` stores provider-neutral execution details that do not yet warrant first-class columns.

### citations

`citations` links assistant messages to source chunks.

Important fields:

- `organisation_id`, `workspace_id`, `conversation_id`, and `message_id` keep the citation tenant-scoped and tied to the assistant answer.
- `chunk_id`, `document_id`, and `document_version_id` preserve source traceability.
- `citation_index` gives deterministic citation ordering within an answer.
- `source_title`, `source_type`, `page_number`, `section_title`, and `quoted_text` preserve user-facing source details.

## Relationships

```text
workspaces -> chat_sessions -> chat_messages -> citations
chunks -> citations
documents -> citations
document_versions -> citations
```

The repository validates citation chunks using the same `organisation_id` and `workspace_id` as the target message. A citation cannot be attached to a user message.

## Lifecycle

Conversations start as `active`. Valid transitions are:

- `active` to `completed`, `abandoned`, or `archived`
- `completed` to `archived`
- `abandoned` to `archived`

`archived` is terminal. Completing or archiving a conversation sets `ended_at`.

## Tenant Isolation

Repository and service methods require `organisation_id`, `workspace_id`, and parent identifiers. Conversations, messages, and citations are not fetched by ID alone. Message creation first validates that the conversation belongs to the requested organisation/workspace. Citation creation validates that the target message and referenced chunk belong to the same tenant/workspace.

## Sequence Rules

Messages are ordered by `sequence_number`, not by timestamp. The service allocates the next sequence number as `max(sequence_number) + 1` within the tenant-scoped conversation. The database enforces `conversation_id + sequence_number` uniqueness so duplicate ordering is rejected.

## Future RAG Population

Future RAG orchestration will append an assistant message after retrieval, prompt rendering, model routing, and provider execution complete. It should populate:

- `answer_state`
- `model_key`, `provider_key`, and `provider_model_name`
- `prompt_key`, `prompt_version`, and `prompt_hash`
- `execution_id`
- token counts and `estimated_cost`
- `latency_ms`, `finish_reason`, and `error_code`
- citations for the retrieved chunks used as evidence

## Out of Scope

This foundation does not implement the final chat endpoint, public widget endpoint, retrieval invocation, provider invocation, streaming, memory summarisation, billing, analytics UI, or database-backed provider health/usage accounting.
