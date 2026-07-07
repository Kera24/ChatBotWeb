# ADR 0001: Build a Multi-Tenant AI Knowledge Platform

Status: Accepted

## Context

The business receives repeated requests for client-specific chatbots that answer questions from a changing knowledge base. Building every chatbot from scratch creates repeated engineering effort and long-term maintenance overhead.

## Decision

Build a single multi-tenant AI knowledge platform instead of separate chatbot projects.

Each client will be represented as a tenant or workspace. All knowledge, users, documents, chat sessions, vector records, analytics, and settings must be scoped to that tenant.

## Consequences

### Positive

- Faster client onboarding
- Shared infrastructure
- Reusable RAG pipeline
- Easier maintenance
- Centralised analytics
- Foundation for future AI agents

### Negative

- Higher upfront architecture effort
- Tenant isolation must be designed carefully
- More complex permissions model
- More operational responsibility

## Alternatives considered

### Build one chatbot per client

Rejected because it does not scale and creates repeated maintenance work.

### Use an existing chatbot SaaS only

Rejected because the company needs control over custom workflows, integrations, white-label options, and long-term product ownership.

### Build only an internal tool

Rejected because the commercial opportunity is stronger as a client-facing platform.

## Implementation notes

The MVP should prioritise:

- Tenant model
- Document upload
- RAG pipeline
- Website widget
- Source citations
- Basic analytics

Advanced agents, integrations, and billing should come later.
