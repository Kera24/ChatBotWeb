# Epic: Public Access Layer

## Epic ID

EPIC-004

## Status

Draft

## Owner

Platform engineering

## Problem

Future public and external channels need a shared, secure path into tenant-scoped RAG capabilities. Without a reusable Public Access Layer, website widget, public REST API, Slack, Teams, WhatsApp, voice, MCP, and future integrations would duplicate tenant resolution, session validation, rate limiting, cost controls, safe errors, and response projection.

## Goal

Create a reusable Public Access Layer bounded context between external channels and the RAG Orchestrator so every public/external request is tenant-safe, rate-limited, cost-aware, source-grounded, and channel-normalised before reaching AI Core.

## Users

- Public chatbot user
- Organisation owner
- Client admin
- Platform operator
- Future integration developer

## Scope

- Public Access Layer architecture.
- Public identity and tenant-resolution model.
- Channel adapter contract.
- Shared validation, rate-limit, cost, privacy, and error policies.
- Future implementation tasks for service skeleton and channel endpoints.
- ADR for bounded-context decision.

## Out of scope

- Public endpoint implementation.
- Database migrations.
- Widget UI.
- Redis limiter implementation.
- Anonymous sessions.
- Slack, Teams, WhatsApp, voice, or MCP implementation.
- Lead capture.
- Analytics dashboard.

## Requirements

- Public/external tenant context must be resolved server-side.
- Dashboard authentication and development headers must not be accepted by public channels.
- The layer must be reusable across multiple channels.
- The layer must not duplicate RAG Orchestrator responsibilities.
- Safe errors must not reveal tenant existence or internals.
- Future implementation must follow architecture-before-implementation task gating.

## Acceptance criteria

- [ ] Public Access Layer architecture exists and is approved.
- [ ] ADR-0006 records the bounded-context decision.
- [ ] Paired architecture and implementation tasks exist for initial implementation.
- [ ] Planning templates require architecture approval before major implementation tasks.
- [ ] Sprint plan reflects the architecture/implementation split.

## Dependencies

- `implementation-pack/02_Architecture/01_Public_Access_Layer_Architecture.md`
- `implementation-pack/07_Security/02_Public_Widget_Security_Architecture.md`
- `docs/adr/0005-public-widget-security-boundary.md`
- `docs/adr/0006-public-access-layer-bounded-context.md`
- `implementation-pack/00_Operating_Model/03_Architecture_Implementation_Task_Pattern.md`

## Risks

- The layer could become too broad if it absorbs RAG Orchestrator responsibilities.
- Public channel implementation could bypass the layer if guardrails are not followed.
- Overengineering before the first channel could slow delivery.

## Implementation notes

Start with architecture and contracts. Implement the minimal service skeleton only after TASK-056A is approved. Keep the first implementation focused on reusable boundaries, not complete public widget launch.
