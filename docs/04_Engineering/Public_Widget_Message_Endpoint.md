# Public Widget Message Endpoint

TASK-063B3 implements the first public widget message endpoint:

```text
POST /api/v1/widget/{public_key}/messages
OPTIONS /api/v1/widget/{public_key}/messages
```

The endpoint sends one anonymous-session-bound widget message through the Public Access Gateway and the existing tenant-scoped RAG Orchestrator. It does not expose tenant IDs, conversation IDs, model/provider/prompt controls, retrieval limits, raw context, token/cost data, or internal execution metadata.

## Request

`POST` requires `Content-Type: application/json`, a validated `Origin`, and an `Idempotency-Key` header.

Allowed JSON fields:

```json
{
  "session_token": "pss_dev_token.secret",
  "message": "What are the admissions dates?",
  "client_request_id": "optional-safe-client-id",
  "metadata": {"optional": "bounded safe values"}
}
```

Unknown fields are rejected. Public clients cannot submit organisation, workspace, credential, conversation, internal session, model, provider, prompt, retrieval, context, output-token, system-instruction, Origin, IP, file, tool, or conversation-history fields.

## Gateway Flow

The route is a thin HTTP adapter. The Public Access Gateway performs the security sequence:

1. Resolve the widget credential and tenant server-side.
2. Reject dashboard/development headers.
3. Validate request shape and message limits.
4. Validate Origin.
5. Apply `widget_message_send` rate limits.
6. Validate the public session and bindings.
7. Resolve idempotency.
8. Consume one message slot for new work.
9. Create or attach one tenant-scoped widget conversation.
10. Run abuse and cost controls.
11. Invoke the public RAG adapter.
12. Store a safe idempotency response snapshot.

Rate denial, invalid Origin, invalid session, duplicate in-progress requests, idempotency conflicts, abuse rejection, and quota rejection stop before RAG.

## RAG Adapter

`PublicWidgetRAGAdapter` accepts `SecuredPublicMessage` and calls the existing `RAGOrchestrator`. It passes only server-resolved tenant/workspace/conversation context, the canonical message, channel `widget`, effective retrieval/context/output ceilings, and safe internal metadata. It does not reproduce retrieval, prompt rendering, provider execution, citation persistence, or message persistence logic.

The RAG Orchestrator persists the user message, assistant message, citations, fallback state, and execution metadata. Completed idempotent duplicates return the stored safe response without another RAG call or new messages.

## Response

The provisional response is plain-text oriented until TASK-063B4 adds full output/Markdown sanitisation:

```json
{
  "response_id": "pmr_...",
  "answer": "Plain text answer",
  "answer_state": "answered",
  "citations": [],
  "remaining_messages": 29,
  "fallback_used": false,
  "request_id": "req_...",
  "response_schema_version": "1.0"
}
```

Citations are projected from authorised RAG citations only. They are ordered, deduplicated, capped, and stripped of database IDs, storage paths, similarity scores, tenant identifiers, and internal metadata. Quoted citation text is bounded.

## CORS And Rate Limits

`OPTIONS` validates the widget credential and Origin but does not validate the session, consume a slot, or call RAG. Valid preflight responses include dynamic `Access-Control-Allow-Origin`, `Vary: Origin`, `Access-Control-Allow-Credentials: false`, `POST, OPTIONS`, and only `Content-Type`, `Idempotency-Key`, and `X-Request-ID` request headers.

`POST` uses the `widget_message_send` category. Rate limiting runs before session preparation and RAG. Rejections include safe `Retry-After` where applicable and do not expose Redis policy details.

## Failure Behaviour

- Empty retrieval returns `200` with fallback answer and zero citations.
- Provider/RAG failure returns a safe unavailable response, marks idempotency failed, and leaves the consumed slot intact.
- Completed duplicate requests return the stored safe response snapshot.
- In-progress duplicate requests return a safe in-progress error.
- Idempotency conflicts do not consume another slot or call RAG.

## Explicit Limitations

Full Markdown/link sanitisation, rich output safety, streaming, widget UI, file uploads, tools, public conversation history, feedback, and analytics remain future work. TASK-063B4 owns the full output sanitisation boundary.