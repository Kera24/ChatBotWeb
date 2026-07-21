# ADR-0006: Public Access Layer Bounded Context

Status: Accepted for planning
Date: 2026-07-13

## Context

The platform is expanding from internal dashboard RAG flows toward public and external channels. The website widget is only one future channel; the platform also needs to support public REST API clients, Slack, Microsoft Teams, WhatsApp, voice, MCP clients, and other integrations.

If each channel calls the RAG Orchestrator directly, tenant resolution, abuse controls, session handling, safe errors, and public response projection will be duplicated and inconsistent. This increases cross-tenant leakage and denial-of-wallet risk.

## Decision

Introduce a reusable Public Access Layer bounded context between external channels and the existing RAG Orchestrator.

```text
External Channels
    ?
Public Access Layer
    ?
RAG Orchestrator
    ?
Knowledge Platform
    ?
AI Core
```

The Public Access Layer owns external identity resolution, tenant mapping, channel/session validation, request normalisation, rate and cost policy checks, public-safe error mapping, public-safe response projection, and channel security/observability events.

The RAG Orchestrator remains responsible for tenant-scoped retrieval, prompt rendering, provider execution, conversation persistence, and citations.

## Consequences

Positive:

- One reusable boundary for all public and external channels.
- Public tenant resolution is server-owned and never trusts client-supplied tenant IDs.
- Security, rate limiting, cost controls, and safe errors are centralised.
- Future channels can be added with adapters instead of bespoke RAG paths.
- Dashboard and public access paths remain separate.

Trade-offs:

- Adds an additional internal abstraction before public channels launch.
- Requires careful contract design so it does not duplicate RAG Orchestrator logic.
- Requires paired architecture and implementation tasks for each major channel capability.

## Non-Goals

This ADR does not implement public endpoints, database migrations, Redis rate limiting, anonymous sessions, widget UI, public RAG, Slack/Teams/WhatsApp integrations, voice, MCP support, or product features.

## Related Documents

- `implementation-pack/02_Architecture/01_Public_Access_Layer_Architecture.md`
- `implementation-pack/07_Security/02_Public_Widget_Security_Architecture.md`
- `docs/adr/0005-public-widget-security-boundary.md`
- `implementation-pack/00_Operating_Model/03_Architecture_Implementation_Task_Pattern.md`
