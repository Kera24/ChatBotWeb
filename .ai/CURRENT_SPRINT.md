# Current Sprint

Current phase: Sprint 3C - Public Channels
Current task: TASK-063B3 - Public RAG Adapter and Message Route

## Active Objective

Implement the public widget message route and the dedicated public RAG adapter that connects the secured Public Access message pipeline to the tenant-scoped RAG Orchestrator.

## Guardrails

- `POST /api/v1/widget/{public_key}/messages` must use the Public Access Gateway in `message_send` mode.
- Public clients must provide a valid public session token and `Idempotency-Key`.
- Public clients never choose tenant, conversation, model, provider, prompt, retrieval, context, output-token, or cost settings.
- The route must not expose internal tenant/session/conversation/message/provider/prompt/retrieval metadata.
- Full Markdown/link/output sanitisation remains TASK-063B4.

## Definition Of Done

- Planning task file exists.
- Public route and strict schema exist.
- Gateway invokes preparation, abuse/cost controls, and the public RAG adapter.
- Idempotency completes with public-safe snapshots.
- Provisional response/citation projection is safe and tested.
- Docs are updated.
- Verification commands pass or failures are reported.