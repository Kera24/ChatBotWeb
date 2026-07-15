# API Specification

Version: 0.2
Status: Draft
Last updated for: TASK-062B

## 1. Purpose

Define the currently implemented REST API surface for the ChatBotWeb / Yoranix AI Platform foundation.

This specification documents only endpoints that exist in the application today. Planned upload, storage, ingestion, retrieval, RAG, chat runtime, analytics, and unimplemented widget APIs are explicitly marked as not implemented.

## 2. API style

Initial API style: REST over JSON.

Common response wrapper:

```json
{
  "success": true,
  "data": {},
  "meta": {}
}
```

Common error responses are returned by FastAPI using the standard `detail` field.

## 3. Base paths

Implemented API base paths:

```text
/health
/api/v1/system
/api/v1/admin
/api/v1/orgs
/api/v1/workspaces
/api/v1/widget
```

Planned but not implemented API base paths:

```text
/api/v1/knowledge
/api/v1/chat
/api/v1/analytics
```

## 4. Authentication model

Authentication is currently a development-only placeholder.

Protected routes accept these temporary headers:

| Header | Default | Purpose |
| --- | --- | --- |
| `X-Development-User-Email` | `dev-super-admin@example.test` | Supplies the current development user email. |
| `X-Development-Role` | `super_admin` | Supplies the current development role. |

Important development-only constraints:

- This is not production authentication.
- These headers exist only to develop and test RBAC and tenant-isolation behaviour before hosted auth is integrated.
- `super_admin` bypasses organisation membership checks.
- Non-`super_admin` requests require an active user matching `X-Development-User-Email` and a valid organisation membership for routes guarded by organisation roles.

Current role gates:

| Role gate | Allowed roles |
| --- | --- |
| Super admin | `super_admin` |
| Workspace manager | `super_admin`, `org_owner`, `client_admin` |
| Workspace/document viewer | `super_admin`, `org_owner`, `client_admin`, `viewer` |
| Audit reader | `super_admin`, `org_owner`, `client_admin` |

## 5. Tenant context rules

Routes nested under `/api/v1/orgs/{organisation_id}` receive tenant context from the `organisation_id` path parameter.

Workspace-scoped routes under `/api/v1/workspaces
/api/v1/workspaces/{workspace_id}` require an `organisation_id` query parameter:

```text
?organisation_id={organisation_id}
```

This query parameter is required until production authentication can safely infer organisation access. The API validates that the workspace belongs to the supplied organisation before returning workspace, document, chunk, lifecycle, or audit data.

## 6. System APIs

### GET /health

Returns the service health status.

Authentication: none.

### GET /api/v1/system/info

Returns system metadata for the running API service.

Authentication: none.

## 7. Organisation APIs

### GET /api/v1/admin/organisations

Lists active organisations.

Required role: `super_admin`.

### POST /api/v1/admin/organisations

Creates an organisation.

Required role: `super_admin`.

Request body:

```json
{
  "name": "Example College",
  "slug": "example-college"
}
```

Response data fields include:

- `id`
- `name`
- `slug`
- `status`
- `plan_key`
- `created_at`
- `updated_at`

Conflict behaviour: returns `409` when the organisation slug already exists.

## 8. Workspace APIs

### GET /api/v1/orgs/{organisation_id}/workspaces

Lists workspaces for an organisation.

Required role: workspace manager.

### POST /api/v1/orgs/{organisation_id}/workspaces

Creates a workspace for an organisation.

Required role: workspace manager.

Request body:

```json
{
  "name": "Admissions Assistant",
  "slug": "admissions",
  "default_language": "en"
}
```

Response data fields include:

- `id`
- `organisation_id`
- `name`
- `slug`
- `status`
- `default_language`
- `created_at`
- `updated_at`

Conflict behaviour: returns `409` when the workspace slug already exists for the organisation.

### GET /api/v1/workspaces
/api/v1/workspaces/{workspace_id}?organisation_id={organisation_id}

Returns one workspace by ID within the supplied organisation.

Required role: workspace/document viewer.

Tenant requirement: `organisation_id` query parameter is required.

## 9. Document Metadata APIs

Document APIs currently manage metadata records only. They do not upload files, persist object storage assets, extract text, chunk content, create embeddings, or run ingestion pipelines.

### GET /api/v1/workspaces
/api/v1/workspaces/{workspace_id}/documents?organisation_id={organisation_id}

Lists document metadata records for a workspace.

Required role: workspace/document viewer.

Tenant requirement: `organisation_id` query parameter is required.

### POST /api/v1/workspaces
/api/v1/workspaces/{workspace_id}/documents?organisation_id={organisation_id}

Creates a document metadata record for a workspace.

Required role: workspace manager.

Tenant requirement: `organisation_id` query parameter is required.

Request body:

```json
{
  "title": "Admissions Guide",
  "source_type": "manual",
  "source_key": "admissions-guide",
  "category": "admissions",
  "visibility": "workspace",
  "metadata_json": {}
}
```

Response data fields include:

- `id`
- `organisation_id`
- `workspace_id`
- `title`
- `source_type`
- `source_key`
- `status`
- `category`
- `visibility`
- `created_by_user_id`
- `active_document_version_id`
- `metadata_json`
- `archived_at`
- `expires_at`
- `deleted_at`
- `created_at`
- `updated_at`

### GET /api/v1/workspaces
/api/v1/workspaces/{workspace_id}/documents/{document_id}?organisation_id={organisation_id}

Returns one document metadata record by ID within a workspace.

Required role: workspace/document viewer.

Tenant requirement: `organisation_id` query parameter is required.

## 10. Document Version APIs

Document version APIs currently read existing metadata only. Version creation and file processing are not implemented as public endpoints.

### GET /api/v1/workspaces
/api/v1/workspaces/{workspace_id}/documents/{document_id}/versions?organisation_id={organisation_id}

Lists document versions for a document.

Required role: workspace/document viewer.

Tenant requirement: `organisation_id` query parameter is required.

### GET /api/v1/workspaces
/api/v1/workspaces/{workspace_id}/documents/{document_id}/versions/{version_id}?organisation_id={organisation_id}

Returns one document version by ID within a document.

Required role: workspace/document viewer.

Tenant requirement: `organisation_id` query parameter is required.

Response data fields include:

- `id`
- `organisation_id`
- `workspace_id`
- `document_id`
- `version_number`
- `original_file_path`
- `extracted_text_path`
- `checksum`
- `processing_status`
- `processing_error`
- `effective_from`
- `expires_at`
- `created_by_user_id`
- `metadata_json`
- `created_at`
- `updated_at`

## 11. Chunk Metadata APIs

Chunk APIs currently read chunk metadata and stored chunk content only. They do not create chunks, generate embeddings, or perform retrieval.

### GET /api/v1/workspaces
/api/v1/workspaces/{workspace_id}/documents/{document_id}/versions/{version_id}/chunks?organisation_id={organisation_id}

Lists chunks for a document version.

Required role: workspace/document viewer.

Tenant requirement: `organisation_id` query parameter is required.

### GET /api/v1/workspaces
/api/v1/workspaces/{workspace_id}/documents/{document_id}/versions/{version_id}/chunks/{chunk_id}?organisation_id={organisation_id}

Returns one chunk by ID within a document version.

Required role: workspace/document viewer.

Tenant requirement: `organisation_id` query parameter is required.

Response data fields include:

- `id`
- `organisation_id`
- `workspace_id`
- `document_id`
- `document_version_id`
- `chunk_index`
- `content`
- `content_hash`
- `token_count`
- `source_type`
- `source_title`
- `language`
- `chunking_strategy_version`
- `heading_path`
- `section_title`
- `page_number`
- `parser_name`
- `parser_version`
- `status`
- `metadata_json`
- `embedding_model`
- `embedding_provider`
- `embedding_dimension`
- `embedding_created_at`
- `created_at`
- `updated_at`

## 12. Lifecycle Transition APIs

Lifecycle transition APIs update document and document-version statuses and create audit events for successful transitions.

### POST /api/v1/workspaces
/api/v1/workspaces/{workspace_id}/documents/{document_id}/transition?organisation_id={organisation_id}

Transitions a document status.

Required role: workspace manager.

Tenant requirement: `organisation_id` query parameter is required.

Request body:

```json
{
  "target_status": "processing"
}
```

Allowed document transitions:

- `uploaded` -> `processing`
- `processing` -> `ready`, `failed`
- `ready` -> `archived`, `expired`

Response metadata includes `previous_status` and `new_status`.

### POST /api/v1/workspaces
/api/v1/workspaces/{workspace_id}/documents/{document_id}/versions/{version_id}/transition?organisation_id={organisation_id}

Transitions a document version processing status.

Required role: workspace manager.

Tenant requirement: `organisation_id` query parameter is required.

Request body:

```json
{
  "target_status": "queued",
  "error_message": null
}
```

Allowed document-version transitions:

- `pending` -> `queued`
- `queued` -> `extracting`
- `extracting` -> `chunking`, `failed`
- `chunking` -> `embedding`, `failed`
- `embedding` -> `ready`, `failed`
- `ready` -> `superseded`

Response metadata includes `previous_status` and `new_status`.

## 13. Audit Read APIs

Audit read APIs expose metadata-only audit events with tenant scoping. They do not implement audit UI or analytics dashboards.

### GET /api/v1/orgs/{organisation_id}/audit-events?limit=100

Lists audit events for an organisation.

Required role: audit reader.

Query parameters:

- `limit`: optional result cap. Values are bounded to `1..500`. Default is `100`.

### GET /api/v1/workspaces
/api/v1/workspaces/{workspace_id}/audit-events?organisation_id={organisation_id}&limit=100

Lists audit events for a workspace.

Required role: audit reader.

Tenant requirement: `organisation_id` query parameter is required.

Query parameters:

- `limit`: optional result cap. Values are bounded to `1..500`. Default is `100`.

Response data fields include:

- `id`
- `organisation_id`
- `workspace_id`
- `actor_user_id`
- `action`
- `entity_type`
- `entity_id`
- `document_id`
- `document_version_id`
- `previous_status`
- `new_status`
- `metadata_json`
- `created_at`
- `updated_at`

## 14. Conversation History APIs

Conversation history APIs expose read-only dashboard access to tenant-scoped conversations created by internal RAG flows. They are not public widget endpoints.

### GET /api/v1/workspaces
/api/v1/workspaces/{workspace_id}/conversations?organisation_id={organisation_id}

Lists conversation summaries for a workspace.

Required role: workspace/document viewer (`org_owner`, `client_admin`, or `viewer`; `super_admin` bypasses membership in development auth).

Tenant requirement: `organisation_id` query parameter is required.

Optional query parameters:

- `status`
- `channel`
- `limit`: default `50`, maximum `100`
- `offset`: default `0`
- `started_after`
- `started_before`

Response data fields include:

- `id`
- `organisation_id`
- `workspace_id`
- `channel`
- `status`
- `title`
- `started_at`
- `last_message_at`
- `ended_at`
- `message_count`
- `last_message_preview`
- `metadata`

### GET /api/v1/workspaces
/api/v1/workspaces/{workspace_id}/conversations/{conversation_id}?organisation_id={organisation_id}

Returns one conversation by ID within the supplied organisation/workspace, with ordered messages and citations attached to assistant messages.

Required role: workspace/document viewer.

Tenant requirement: `organisation_id` query parameter is required. Cross-tenant or missing conversations return a safe `404`.

Message response fields include:

- `id`
- `role`
- `content`
- `sequence_number`
- `answer_state`
- model, provider, prompt, execution, token, cost, latency, finish, and error metadata
- `created_at`
- `citations`

Excluded fields include raw prompts, message metadata JSON, anonymous/external user identifiers, provider internals, secrets, and stack traces.

A separate message-list endpoint is not implemented for MVP because conversation detail returns ordered messages and citations in one response.

## 15. Unanswered Review APIs

Unanswered review APIs expose dashboard access to assistant answers that need human review. Review candidates are derived from existing assistant messages where `answer_state` is `fallback`, `failed`, or `low_confidence`.

### GET /api/v1/workspaces
/api/v1/workspaces/{workspace_id}/review/unanswered?organisation_id={organisation_id}

Lists review items for a workspace.

Required role: workspace/document viewer (`org_owner`, `client_admin`, or `viewer`; `super_admin` bypasses membership in development auth).

Optional query parameters:

- `answer_state`: one of `fallback`, `failed`, `low_confidence`
- `review_status`: one of `open`, `reviewed`, `dismissed`, `knowledge_gap`
- `channel`
- `created_after`
- `created_before`
- `limit`: default `50`, maximum `100`
- `offset`: default `0`

Response items include the conversation ID, assistant message ID, preceding user question, assistant answer, answer state, error code, channel, conversation status, model/provider/prompt identity, citation count, safe citations, created time, estimated cost, latency, review status, reviewer note, and review timestamps.

### GET /api/v1/workspaces
/api/v1/workspaces/{workspace_id}/review/unanswered/{assistant_message_id}?organisation_id={organisation_id}

Returns one review item by assistant message ID with tenant-safe conversation context and citations. Cross-tenant or missing items return a safe `404`.

Required role: workspace/document viewer.

### PATCH /api/v1/workspaces
/api/v1/workspaces/{workspace_id}/review/unanswered/{assistant_message_id}?organisation_id={organisation_id}

Updates review status and optional reviewer note.

Required role: review updater (`org_owner` or `client_admin`; `super_admin` bypasses membership in development auth).

Request body:

```json
{
  "review_status": "knowledge_gap",
  "reviewer_note": "Add a clearer source article."
}
```

Successful updates create a `review.status.changed` audit event. The original user and assistant message content is not mutated.

Excluded fields include raw prompts, rendered prompts, provider internals, secrets, stack traces, and message metadata JSON.

## 16. Not Implemented Yet

The following API areas remain planned but are not implemented:

- File upload endpoints.
- Object storage endpoints.
- Document ingestion endpoints.
- Text extraction and parsing endpoints.
- Chunk creation endpoints.
- Embedding generation endpoints.
- Public RAG runtime endpoints.
- Authenticated chat write endpoints beyond the internal dashboard-test RAG answer endpoint.
- Public widget message endpoints.
- Analytics dashboard endpoints.
- Widget settings endpoints.
- Production authentication and token/session handling.

## 17. API security rules

1. Every protected route uses the development-only auth placeholder until production auth exists.
2. Every tenant-scoped route validates organisation membership or `super_admin` role.
3. Every workspace-scoped route validates the workspace belongs to the supplied organisation.
4. Workspace-scoped routes under `/api/v1/workspaces
/api/v1/workspaces/{workspace_id}` require `organisation_id` as a query parameter.
5. Successful lifecycle transitions and review status changes create tenant-scoped audit events.
6. Upload, public chat, RAG, and widget routes must not be documented as available until implemented.

## TASK-057B Update - Public Credentials and Widget Configuration Admin APIs

Implemented authenticated dashboard/admin endpoints under `/api/v1/workspaces
/api/v1/workspaces/{workspace_id}`. These are not public widget endpoints and still require development dashboard authentication and organisation membership.

Required role: `org_owner` or `client_admin`. `viewer`, `contributor`, and non-members are denied.

Credential management:

- `GET /api/v1/workspaces
/api/v1/workspaces/{workspace_id}/public-credentials?organisation_id={organisation_id}`
- `POST /api/v1/workspaces
/api/v1/workspaces/{workspace_id}/public-credentials?organisation_id={organisation_id}`
- `GET /api/v1/workspaces
/api/v1/workspaces/{workspace_id}/public-credentials/{credential_id}?organisation_id={organisation_id}`
- `PATCH /api/v1/workspaces
/api/v1/workspaces/{workspace_id}/public-credentials/{credential_id}?organisation_id={organisation_id}`
- `POST /api/v1/workspaces
/api/v1/workspaces/{workspace_id}/public-credentials/{credential_id}/activate?organisation_id={organisation_id}`
- `POST /api/v1/workspaces
/api/v1/workspaces/{workspace_id}/public-credentials/{credential_id}/disable?organisation_id={organisation_id}`
- `POST /api/v1/workspaces
/api/v1/workspaces/{workspace_id}/public-credentials/{credential_id}/revoke?organisation_id={organisation_id}`
- `POST /api/v1/workspaces
/api/v1/workspaces/{workspace_id}/public-credentials/{credential_id}/rotate?organisation_id={organisation_id}`

Allowed origins:

- `GET /api/v1/workspaces
/api/v1/workspaces/{workspace_id}/public-credentials/{credential_id}/origins?organisation_id={organisation_id}`
- `POST /api/v1/workspaces
/api/v1/workspaces/{workspace_id}/public-credentials/{credential_id}/origins?organisation_id={organisation_id}`
- `DELETE /api/v1/workspaces
/api/v1/workspaces/{workspace_id}/public-credentials/{credential_id}/origins/{origin_id}?organisation_id={organisation_id}`

Widget configuration:

- `GET /api/v1/workspaces
/api/v1/workspaces/{workspace_id}/public-credentials/{credential_id}/widget-config?organisation_id={organisation_id}`
- `PUT /api/v1/workspaces
/api/v1/workspaces/{workspace_id}/public-credentials/{credential_id}/widget-config?organisation_id={organisation_id}`
- `POST /api/v1/workspaces
/api/v1/workspaces/{workspace_id}/public-credentials/{credential_id}/widget-config/publish?organisation_id={organisation_id}`

Credential create request example:

```json
{
  "credential_type": "widget_public_key",
  "display_name": "Website widget",
  "environment": "development",
  "policy_profile": "widget",
  "capabilities": ["widget_config"]
}
```

Credential response includes the public identifier for widget keys because it is intentionally public. Responses exclude `secret_hash`, raw secret-bearing credential values, hidden metadata, and unrelated tenant data.

Origin create request example:

```json
{
  "origin": "https://www.example.edu",
  "wildcard_subdomains": false
}
```

Widget configuration upsert request example:

```json
{
  "bot_name": "Admissions Assistant",
  "welcome_message": "Ask about admissions.",
  "launcher_label": "Ask us",
  "primary_colour": "#111827",
  "suggested_questions_json": ["How do I apply?"],
  "max_initial_suggestions": 1
}
```

The migration creates no credentials automatically. No workspace becomes public by default.


## Public Widget Configuration API

### GET /api/v1/widget/{public_key}/config

Returns published, sanitised public widget configuration for an active website widget credential.

Authentication: none. This route does not accept dashboard development headers or bearer tokens.

Required HTTP context:

- `Origin` header.
- Server-derived client IP for rate limiting.
- Optional `X-Request-ID`.

Request body: none.

Functional query parameters: none. Unsupported query parameters are rejected.

Successful response: `200`.

```json
{
  "widget": {
    "bot_name": "Admissions",
    "welcome_message": "Ask us about courses.",
    "launcher_label": "Chat now",
    "primary_colour": "#0f766e",
    "secondary_colour": "#111827",
    "logo_url": null,
    "avatar_url": null,
    "position": "bottom_right",
    "theme_mode": "system",
    "language": "en"
  },
  "behaviour": {
    "suggested_questions": ["How do I apply?"],
    "max_initial_suggestions": 1,
    "show_citations": true,
    "allow_conversation_history": false,
    "session_required": true,
    "messages_enabled": true
  },
  "privacy": {
    "privacy_notice_text": null,
    "privacy_notice_url": null,
    "terms_url": null,
    "fallback_contact_text": null
  },
  "capabilities": {
    "can_create_session": true,
    "can_send_messages": true,
    "citations_enabled": true,
    "conversation_history_enabled": false
  },
  "configuration_version": 1,
  "response_schema_version": "1.0",
  "published_at": "2026-07-15T00:00:00+00:00",
  "request_id": "access_..."
}
```

The response excludes organisation ID, workspace ID, credential database ID, internal config ID, allowed origins, policy profile, rate-limit values, retrieval/context/token limits, model/provider/prompt details, internal asset paths, metadata JSON, audit fields, secret/hash values, and environment.

The route emits dynamic validated-Origin CORS headers, `Vary: Origin`, `ETag`, and `Cache-Control: public, max-age=60, stale-while-revalidate=30`. Matching `If-None-Match` returns `304 Not Modified` with no response body.

### OPTIONS /api/v1/widget/{public_key}/config

Route-scoped preflight. Credential and Origin are validated before CORS headers are emitted. Allowed methods are `GET, OPTIONS`; allowed headers are `If-None-Match, X-Request-ID`; browser credentials are disabled.
## Public Widget Session API

### POST /api/v1/widget/{public_key}/sessions

Creates an anonymous public session for an active published website widget credential.

Authentication: none. This route does not accept dashboard development headers or bearer tokens.

Required HTTP context:

- `Origin` header.
- JSON content type when a body is sent.
- Server-derived client IP for rate limiting.

Request body may be empty:

```json
{}
```

Allowed optional fields:

- `client_request_id`
- `metadata`
- `requested_language`

The route rejects organisation IDs, workspace IDs, credential IDs, conversation IDs, session IDs, messages, PII fields, Origin/IP body fields, model/provider/prompt keys, policy overrides, timeout overrides, and limit overrides.

Successful response: `201`.

```json
{
  "session_token": "pss_dev_<token_id>.<secret>",
  "expires_at": "2026-07-15T00:30:00+00:00",
  "absolute_expires_at": "2026-07-16T00:00:00+00:00",
  "inactivity_timeout_seconds": 1800,
  "max_messages": 30,
  "remaining_messages": 30,
  "configuration_version": 1,
  "capabilities": {
    "can_send_messages": true,
    "conversation_history_enabled": true,
    "citations_enabled": true
  },
  "request_id": "access_..."
}
```

The route does not create a conversation, accept a chat message, call retrieval, call RAG, call AI Core, set cookies, or expose widget branding/configuration details beyond the listed capabilities.

### OPTIONS /api/v1/widget/{public_key}/sessions

Handles route-scoped CORS preflight. The response allows CORS only after credential and Origin validation. It never returns wildcard Origin and sets `Access-Control-Allow-Credentials: false`.

No other public widget route is implemented.
