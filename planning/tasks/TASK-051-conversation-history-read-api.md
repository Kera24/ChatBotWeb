# TASK-051 - Conversation History Read API

Status: Implemented

## Objective

Expose tenant-safe dashboard APIs for reading conversations, messages, and citations created by the internal RAG endpoint without implementing public widget access or frontend integration.

## Scope Implemented

- Workspace-scoped conversation list endpoint.
- Workspace-scoped conversation detail endpoint with ordered messages and assistant citations.
- Tenant-safe repository read helpers for paginated summaries, message counts, latest-message previews, ordered detail messages, and grouped citations.
- Current development RBAC for `org_owner`, `client_admin`, and `viewer`.
- Privacy-safe responses that omit anonymous/external identifiers, raw prompts, message metadata JSON, provider internals, secrets, and stack traces.
- Documentation for conversation history API behaviour, filtering, pagination, privacy, and future retention/redaction.
- API specification update for implemented conversation history endpoints.

## Endpoints

- `GET /api/v1/workspaces/{workspace_id}/conversations?organisation_id=...`
- `GET /api/v1/workspaces/{workspace_id}/conversations/{conversation_id}?organisation_id=...`

A separate message-list endpoint is not implemented for MVP because conversation detail returns ordered messages and citations in one tenant-scoped response.

## Out of Scope

- Frontend live API calls.
- Public widget or anonymous conversation history.
- Public chat sessions.
- Streaming.
- Conversation deletion.
- Redaction workflows.
- Analytics aggregation.
- Search across conversations.
- Export.
- Real LLM providers.
- Memory summarisation.

## Verification

Required commands:

- `npm run api:test`
- `npm run verify`
