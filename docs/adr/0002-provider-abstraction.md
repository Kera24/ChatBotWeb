# ADR 0002: Use a Provider-Abstraction Layer for LLM Access

Status: Accepted

## Context

The platform must support a deterministic mock provider for tests and an OpenAI-compatible provider for the first production integration. Future clients may require Azure OpenAI, Anthropic, Gemini, Ollama, or local models.

Coupling the RAG pipeline directly to one provider would make provider changes expensive and would spread provider-specific response formats, errors, credentials, and retry rules through the application.

## Decision

All model calls will use a provider-neutral interface.

Provider adapters must normalise:

- request messages
- model identifiers
- response text
- usage data
- finish status
- provider errors
- timeout and retry behaviour

The deterministic mock provider will be the first implementation. An OpenAI-compatible adapter will be the first external provider.

## Alternatives considered

### Call one provider directly

Rejected because it creates deep vendor coupling.

### Adopt a large third-party routing framework immediately

Rejected for the MVP because it adds operational and conceptual complexity before core requirements are proven.

## Consequences

### Positive

- Provider portability
- Deterministic testing
- Consistent accounting
- Centralised retry and error handling
- Future tenant-level provider policy

### Negative

- Additional abstraction work
- Lowest-common-denominator risk
- Provider-specific features require capability flags

## Rules

- Provider credentials remain server-side.
- Provider adapters may not perform tenant retrieval.
- Adapters return a stable internal result contract.
- Provider-specific capabilities must be declared explicitly.
