# Conversation Lifecycle — Current / Future / Out of Scope

## Current

`ChatSession` (table `chat_sessions`): `status` defaults to `active`, tracks `started_at`/`last_message_at`/`ended_at`/`metadata_json`. `ChatMessage` (table `chat_messages`): `role`, `sequence_number`, `answer_state`, `prompt_key`/`prompt_version`/`prompt_hash`, token/cost/latency fields, plus `Citation` rows attached to assistant messages.

Service layer `apps/api/app/services/conversation.py`:
- `start_conversation()` creates a `ChatSession`.
- `append_user_message()` / `append_assistant_message()` both route through a private `_append_message()`.
- `mark_conversation_completed()` / `archive_conversation()` transition status via `_transition_conversation()`, which enforces an explicit allowed-status graph through `_validate_status_transition()` — invalid transitions raise (`InvalidConversationStatusTransition`, `InvalidConversationRole`, `InvalidAnswerState`) rather than silently succeeding, mirroring the document-lifecycle pattern (`docs/architecture/knowledge-ingestion.md`).
- `attach_citations_to_assistant_message()` links `Citation` rows to a persisted assistant message.

There is no automatic time-based expiry/TTL job today — archival is an explicit call, not a background sweep.

## Future

- Time-based auto-archival for stale/abandoned conversations (currently explicit-call only).
- Conversation-scoped memory built on top of this lifecycle — see `docs/engineering/memory.md` and `docs/future/MemoryV2.md`.

## Out of scope (not planned)

- Mutating a persisted `ChatMessage`'s content after creation (e.g. "edit message") — the lifecycle model is append-only; corrections happen via new messages, not in-place edits, to preserve evaluation/citation/observability trace integrity.
