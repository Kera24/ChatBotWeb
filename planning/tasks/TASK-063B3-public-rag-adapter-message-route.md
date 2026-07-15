# TASK-063B3 - Public RAG Adapter And Message Route

## Objective

Implement the first public widget message endpoint and connect the secured Public Access message pipeline to the existing tenant-scoped RAG Orchestrator.

## Scope

- `POST /api/v1/widget/{public_key}/messages` and route-scoped `OPTIONS`.
- Strict public message request schema with required `Idempotency-Key` header.
- Widget adapter and Public Access Gateway `message_send` flow through credential, tenant, Origin, rate limit, session, idempotency, abuse, and cost controls.
- Dedicated public RAG adapter calling the existing RAG Orchestrator with server-owned tenant, conversation, model, prompt, retrieval, context, and output limits.
- Idempotency completion/failure storage using public-safe response snapshots only.
- Provisional plain-text public response and citation projection.
- Tests and docs for route security, idempotency, RAG behavior, CORS, and provisional response safety.

## Non-Goals

- No full Markdown/output sanitisation engine; that remains TASK-063B4.
- No widget SDK/UI, streaming, file uploads, tool calling, public conversation history, lead capture, feedback, or analytics UI.
- No client model/provider/prompt/retrieval/context/token override support.
- No new provider integration or schema migration.

## Acceptance Criteria

- Public message route exists only under the public widget path.
- Route invokes Public Access Gateway in `message_send` mode.
- Valid requests validate session, consume a slot once, reuse/attach the server-owned conversation, call RAG once, complete idempotency, and return a public-safe response.
- Completed duplicates return the stored safe snapshot without consuming a slot or creating messages.
- Rejections and failures expose only safe public errors.
- No internal tenant/session/conversation/message/provider/prompt/retrieval metadata is returned publicly.