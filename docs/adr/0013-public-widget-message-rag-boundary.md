# ADR-0013: Public Widget Message RAG Boundary

Status: Proposed
Date: 2026-07-15

## Context

The platform now has the Public Access Layer foundation, public widget credentials/configuration, Origin validation, distributed rate limiting, anonymous public sessions, public session creation, and public configuration delivery. The next public widget capability will be message sending, which is the first public path to tenant-scoped RAG execution.

This boundary is higher risk than config or session creation because it can create cost, persist conversation content, retrieve tenant knowledge, prompt a model, and return generated output. It must preserve tenant isolation, source grounding, provider independence, prompt secrecy, safe citations, and public-safe error handling.

## Decision

Design the future endpoint as a thin public widget route using the Public Access Gateway for all public security stages, then a dedicated public RAG adapter that calls the existing RAG Orchestrator:

```text
POST /api/v1/widget/{public_key}/messages
```

The endpoint requires a validated credential-bound anonymous public session. Public clients never supply trusted tenant IDs, conversation IDs, model/provider/prompt choices, retrieval limits, context limits, output-token limits, or raw conversation history.

The Public Access Gateway operation is `message_send` and must run credential resolution, tenant resolution, request validation, Origin validation, `widget_message_send` rate limiting, public-session validation, low-cost abuse checks, cost ceilings, and atomic message-slot consumption before RAG execution.

The public RAG adapter owns translation from validated public context to the existing tenant-scoped RAG Orchestrator. It does not duplicate retrieval, prompt rendering, provider execution, citation persistence, or conversation logic.

Public output and citations pass through a dedicated sanitisation boundary before returning to the browser.

## Alternatives Considered

### A. Public Route Calls RAG Orchestrator Directly

Pros:

- Fewer layers.
- Faster single endpoint implementation.

Cons:

- Duplicates or bypasses credential, tenant, Origin, rate-limit, and session controls.
- Makes future channels inconsistent.
- Increases risk of public clients reaching RAG with untrusted tenant context.

Rejected.

### B. Public Route Uses Public Access Gateway Then Public RAG Adapter

Pros:

- Reuses the established public-channel security boundary.
- Keeps route handlers thin.
- Keeps RAG Orchestrator reusable and tenant-scoped.
- Creates clear boundaries for idempotency, abuse checks, cost controls, and output sanitisation.
- Preserves future channel reuse and service extraction.

Cons:

- Requires explicit adapter contracts and more tests.
- Requires careful transaction and idempotency design.

Chosen.

### C. Separate Public-Message Microservice Immediately

Pros:

- Strong operational isolation.
- Independent scaling path.

Cons:

- Premature distributed-system complexity.
- Still needs access to tenant, session, conversation, rate-limit, and RAG contracts.
- Slower to implement safely for MVP.

Rejected for MVP. Future extraction remains possible.

### D. Client Directly Calls Internal Conversation/RAG API

Pros:

- Minimal backend work.

Cons:

- Exposes internal APIs and assumptions.
- Cannot safely trust tenant/conversation/model/prompt input.
- Breaks Public Access Layer and RAG Orchestrator boundaries.

Rejected.

## Consequences

Positive:

- Public message traffic receives the same credential, tenant, Origin, session, and rate-limit checks as other public widget operations.
- RAG execution remains tenant-scoped and source-grounded.
- Public clients cannot choose AI internals.
- Idempotency and transaction boundaries can be made explicit before implementation.
- Output sanitisation prevents internal metadata and unsafe model output from becoming public by default.

Trade-offs:

- Implementation should be split into smaller tasks.
- Idempotency likely requires a new persistence table.
- Message-slot consumption before RAG means provider/RAG failures consume a slot.
- Public answer sanitisation may replace some generated answers with fallback responses.

## Required Controls

- Public session validation is mandatory.
- The route must use the Public Access Gateway `message_send` operation.
- The route must use `widget_message_send` rate limits and fail closed on Redis uncertainty.
- Message slots are consumed after low-cost validation/abuse checks and immediately before expensive RAG processing.
- Provider/RAG failure still consumes the slot.
- Conversation ID is never accepted from the browser.
- Conversation creation/attachment is server-owned and concurrency-safe.
- Idempotency uses bounded, hashed, session-scoped keys with durable status/result tracking.
- Public clients cannot override model, provider, prompt, retrieval, context, output, token, tenant, or conversation policy.
- Public output/citations must be sanitised.
- Public events must not include raw messages, answers, tokens, raw origins, prompts, or internal execution metadata by default.

## Implementation Split

Recommended future tasks:

1. `TASK-063B1` - Message contracts, idempotency persistence, session validation/slot preparation, transaction scaffolding.
2. `TASK-063B2` - Abuse/input safety service and public cost-control service.
3. `TASK-063B3` - Public RAG adapter, conversation attachment, thin route, and CORS.
4. `TASK-063B4` - Public output/citation sanitiser, security tests, and docs.

## Non-Goals

This ADR does not implement:

- Public message route.
- Request/response schemas.
- Idempotency model or migration.
- Abuse service.
- Cost-control service.
- Public RAG adapter.
- Output sanitiser.
- CORS code.
- Widget SDK/UI.
- Streaming.
- Tool calling.
- New provider integration.

## Related Documents

- `implementation-pack/02_Architecture/08_Public_Widget_Message_RAG_Architecture.md`
- `implementation-pack/02_Architecture/01_Public_Access_Layer_Architecture.md`
- `implementation-pack/02_Architecture/05_Anonymous_Public_Session_Architecture.md`
- `implementation-pack/03_AI/01_RAG_Implementation_Standards.md`
- `docs/adr/0004-rag-orchestrator-boundary.md`
- `docs/adr/0005-public-widget-security-boundary.md`
- `docs/adr/0006-public-access-layer-bounded-context.md`
- `docs/adr/0010-anonymous-public-session-security.md`
- `docs/adr/0011-public-widget-session-endpoint.md`
- `docs/adr/0012-public-widget-configuration-delivery.md`
- `planning/tasks/TASK-063A-public-widget-message-rag-security-architecture.md`
