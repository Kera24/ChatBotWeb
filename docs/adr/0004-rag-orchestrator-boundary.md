# ADR 0004: Separate RAG Orchestration from Chat and Provider Layers

Status: Accepted

## Context

The platform will expose AI through multiple products, including website chat, internal assistants, APIs, future voice interfaces, and workflow agents.

If retrieval, prompt assembly, provider invocation, citation validation, and chat persistence are implemented inside one endpoint or UI-specific service, the logic will be difficult to reuse and test.

## Decision

Create a dedicated RAG orchestrator boundary.

The orchestrator coordinates:

1. Tenant and workspace validation
2. Retrieval
3. Context assembly
4. Prompt resolution and rendering
5. Model/provider resolution
6. Provider execution
7. Citation and output validation
8. Usage and cost recording
9. Stable response creation

The orchestrator does not own:

- Website widget UI
- Dashboard UI
- Provider-specific HTTP logic
- Vector database implementation details
- Conversation presentation

## Alternatives considered

### Put all logic in the chat endpoint

Rejected because it couples reusable AI behaviour to one interface.

### Split every stage into a separate network service immediately

Rejected because it creates premature distributed-system complexity.

## Consequences

### Positive

- Reusable across products
- Easier deterministic testing
- Clear observability by stage
- Provider and retrieval implementations remain replaceable
- Future agent workflows can reuse the same core

### Negative

- Requires clear internal contracts
- Adds an orchestration abstraction
- Error handling must normalise failures across stages

## Rules

- Every request entering the orchestrator must include tenant context.
- Orchestrator responses must remain provider-neutral.
- Retrieval and provider execution must be independently testable.
- Chat session persistence should call the orchestrator, not be embedded inside it.
