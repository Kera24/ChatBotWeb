# ADR-0005: Public Widget Security Boundary

Status: Accepted for future implementation planning
Date: 2026-07-13

## Context

The platform will eventually provide an embeddable public website chatbot. Public traffic is anonymous, internet-facing, and potentially high-volume. It must not reuse authenticated dashboard APIs, development headers, or dashboard tenant parameters. The public widget must support many customer websites while preserving tenant isolation, source grounding, cost controls, and abuse resistance.

## Decision

We will implement public widget APIs as a separate security boundary from dashboard and internal development APIs.

Public widget requests will resolve tenant context only through a server-side public widget key lookup:

```text
public_widget_key -> active widget configuration -> active workspace -> active organisation
```

The public key is not a secret and does not grant dashboard or administrative access. Public APIs will not trust client-supplied `organisation_id`, `workspace_id`, provider keys, prompt keys, document IDs, or chunk IDs.

The preferred MVP delivery approach is a sandboxed iframe widget.

## Rationale

A sandboxed iframe gives the clearest isolation from customer-site JavaScript and CSS, avoids most styling conflicts, supports independent deployment/versioning, and creates a clearer postMessage and CSP boundary. Script-injected DOM widgets are simpler but share the host page context and have higher XSS/styling risk. Web components reduce styling conflict but still execute in the page context.

Separating public widget APIs prevents dashboard authentication confusion and blocks anonymous callers from reaching administrative capabilities. Server-side tenant resolution preserves multi-tenant invariants and makes rate limiting, cost control, and audit/security monitoring enforceable.

## Consequences

Positive:

- Public and dashboard access paths remain unambiguous.
- Public widget keys can be rotated or revoked without changing dashboard auth.
- Tenant isolation is enforced before retrieval or AI execution.
- Domain validation, anonymous sessions, rate limits, and cost ceilings can be applied consistently.
- The iframe shell can evolve independently of dashboard UI.

Trade-offs:

- Iframe focus management and responsive sizing require careful implementation.
- Customer CSP configuration may require explicit `frame-src` and `connect-src` allowlisting.
- The public key can still be copied, so domain checks must be combined with rate limits and abuse detection.

## Non-Goals

This ADR does not implement database migrations, public endpoints, Redis limiters, widget UI, anonymous sessions, lead capture, provider moderation, or analytics dashboards.

## Required Future Controls

- Public widget key lifecycle with audit events.
- Allowed-domain validation using Origin as the primary browser signal.
- Redis layered rate limiting.
- Cryptographically random anonymous session tokens with server-side workspace binding.
- Request validation and message-size ceilings.
- Tenant-scoped retrieval and conversation persistence.
- Prompt-injection and citation-manipulation controls.
- Safe public error model.
- Sanitised rendering and safe link handling.
- Cost ceilings and emergency kill switches.

## Related Documents

- `implementation-pack/07_Security/02_Public_Widget_Security_Architecture.md`
- `docs/06_Security/01_Security_and_RBAC_Model.md`
- `docs/00_Foundation/AI_PLATFORM_MANIFESTO.md`
