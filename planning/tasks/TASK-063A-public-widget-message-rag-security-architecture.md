# TASK-063A - Public Widget Message and RAG Security Architecture

Status: Complete
Type: Architecture and planning
Sprint: Sprint 3C - Public Channels

## Objective

Design the first public message endpoint that safely connects a validated anonymous widget session to the existing tenant-scoped RAG Orchestrator:

```text
POST /api/v1/widget/{public_key}/messages
```

TASK-063A is architecture only. It does not implement routes, schemas, session validation wiring, RAG calls, abuse controls, cost controls, streaming, widget UI, or migrations.

## Required Boundary

The endpoint must:

- Resolve and validate the widget credential.
- Validate Origin.
- Apply `widget_message_send` rate limits.
- Validate the anonymous public session and all credential, tenant, channel, environment, policy, and Origin bindings.
- Validate and normalise the message.
- Apply low-cost abuse checks before expensive work.
- Consume one atomic session message slot immediately before retrieval/RAG.
- Apply server-owned cost ceilings.
- Attach or reuse the session conversation without trusting a client conversation ID.
- Invoke RAG only through a public-safe adapter.
- Return only sanitised public answer/citation fields.

The endpoint must not accept tenant IDs, credential IDs, conversation IDs, internal session IDs, model/provider/prompt/retrieval/context/token overrides, raw conversation history, tool definitions, PII fields, Origin/IP in the body, or dashboard auth context.

## Key Decisions

- Gateway operation: `message_send`.
- Session validation is mandatory after credential, tenant, Origin, and rate-limit checks.
- Message-slot consumption occurs after validation and low-cost abuse checks, immediately before expensive RAG processing. Provider/RAG failure still consumes the slot.
- Conversation is lazily created on the first accepted message and atomically attached to the public session. Concurrent first messages converge on one conversation.
- MVP idempotency should use a bounded `Idempotency-Key`, scoped by public session and endpoint, persisted as a hash with execution status and safe response reference.
- Abuse checks are lightweight MVP controls and do not claim deterministic prompt-injection prevention.
- Public clients cannot choose tenant, conversation, model, provider, prompt, retrieval, context, output, or token limits.
- Public RAG integration uses a dedicated adapter over the existing RAG Orchestrator.
- Public response sanitisation is a dedicated boundary separate from RAG execution and widget rendering.
- `widget_message_send` Redis uncertainty fails closed; no read-only local fallback.

## Recommended Implementation Split

TASK-063B should be split before coding because the full endpoint spans persistence, safety, RAG, transactions, and public HTTP concerns:

1. `TASK-063B1` - Message contracts, idempotency architecture implementation, session validation/slot preparation, and transaction scaffolding.
2. `TASK-063B2` - Abuse/input safety service and public cost-control service.
3. `TASK-063B3` - Public RAG adapter, conversation attachment, and thin route/CORS wiring.
4. `TASK-063B4` - Public response/citation sanitiser, security integration tests, and documentation hardening.

## Deliverables

- `implementation-pack/02_Architecture/08_Public_Widget_Message_RAG_Architecture.md`
- `docs/adr/0013-public-widget-message-rag-boundary.md`
- `planning/tasks/TASK-063A-public-widget-message-rag-security-architecture.md`
- `.ai/CURRENT_SPRINT.md` update
- `.ai/PROJECT_CONTEXT.md` guardrail update

## Acceptance Criteria

- Endpoint boundary is explicit.
- Session validation is mandatory.
- Message-slot consumption point is selected.
- No tenant/conversation IDs are trusted from the public client.
- Abuse and cost controls are defined.
- RAG integration uses an adapter.
- Public output/citations are sanitised.
- Idempotency/concurrency model is defined.
- Transaction/failure boundaries are complete.
- CORS and rate-limit policies are defined.
- Threat model and diagrams are complete.
- ADR-0013 records the decision.
- Implementation tasks are sequenced.
- No runtime code or route is added.

## Verification

- `git diff --check`
