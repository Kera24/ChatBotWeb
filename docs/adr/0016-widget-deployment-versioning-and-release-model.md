# ADR-0016: Widget Deployment, Versioning, and Release Model

Status: Proposed
Date: 2026-07-18

## Context

The embeddable widget is locally verified through the loader SDK, sandboxed iframe application, iframe-owned public API client, token-isolated session storage, functional Preact UI, accessibility/security browser tests, visual regression, and production bundle inspection. It is classified as release-ready for controlled pilot, not general availability.

The next architectural boundary is how to deploy and operate the widget in production-like conditions without weakening tenant isolation, token isolation, CORS/Origin controls, caching, rollback, or customer upgrade safety.

## Decision

Use versioned immutable SDK loader assets with an independently deployable backward-compatible iframe application, protocol-major compatibility, and controlled release channels.

External delivery model:

- `cdn.yoranix.com` serves immutable SDK/static assets.
- `widget.yoranix.com` serves the iframe HTML/application shell.
- `widget-api.yoranix.com` serves anonymous public widget config/session/message APIs.
- `app.yoranix.com` and `api.yoranix.com` remain separate authenticated administration/dashboard surfaces.

Versioning model:

- SDK loader uses semver and immutable paths such as `/widget-sdk/v1.2.3/loader.js`.
- SDK major alias `/widget-sdk/v1/loader.js` may receive backward-compatible updates and emergency rollback with short TTL and CDN purge.
- The iframe app is deployed independently behind environment/channel routing, provided it supports the active protocol major and public API v1.
- postMessage protocol versioning is separate from SDK package versioning.
- Public widget API remains `/api/v1` compatible until a separately approved v2.

Pilot model:

- Use production-grade infrastructure with explicit tenant/widget allowlisting, not a permanently divergent pilot stack.
- Start with a synthetic tenant/widget and a small number of approved customer widgets.
- Require real-backend smoke, tenant-isolation smoke, rollback path, monitoring, alerting, and release checklist signoff before pilot exposure.

## Alternatives Considered

### A. Single Unversioned SDK And Iframe

Rejected. It is simple, but not reproducible and has weak rollback/support characteristics.

### B. Fully Coupled Versioned SDK And Iframe

Rejected. It is deterministic, but every iframe fix would require SDK/customer rollout friction.

### C. Versioned Immutable SDK Plus Independently Deployable Compatible Iframe

Chosen. It supports customer pinning, major-alias compatible fixes, iframe rollback without embed-code changes, and a testable protocol-major contract.

### D. Customer-Pinned Full Release Bundles

Rejected as default. It provides maximum customer control but slows security remediation and pilot velocity. Pinned SDK remains optional.

## Consequences

Positive: releases and rollbacks are practical, immutable assets are cacheable/auditable, the iframe can receive fixes independently, public widget traffic is separated from authenticated dashboard traffic, and pilot exposure can be limited while using production-grade infrastructure.

Trade-offs: strict compatibility tests, CDN cache discipline, operational ownership of aliases/channels, and explicit remediation for customers pinned to broken immutable versions are required.

## Required Controls

- No uncontrolled production `latest` loader path.
- Immutable SDK and hashed static assets never mutate after release.
- Major SDK alias uses short TTL and purge capability.
- Iframe HTML is short-cache/revalidated, not one-year immutable.
- Session/message responses use `no-store`.
- Public config uses ETag and cache keys scoped by widget/environment/origin where relevant.
- Public APIs use explicit CORS, no credentials, and no cookies.
- Production origins require HTTPS and exact Origin matching.
- Session tokens never cross iframe boundary.
- Production bundles exclude test hooks, localhost hosts, mock responses, and normal console logging.
- Rollback uses previous known-good artifacts without rebuild.
- Pilot enablement is server-authoritative and audited.
- Real-backend smoke and tenant-isolation smoke are required before pilot enablement.

## Related Documents

- `implementation-pack/02_Architecture/10_Widget_Controlled_Pilot_Deployment_and_Operations_Architecture.md`
- `implementation-pack/02_Architecture/09_Embeddable_Widget_SDK_Architecture.md`
- `implementation-pack/05_Design/02_Widget_UI_Interaction_Architecture.md`
- `docs/adr/0014-widget-sdk-and-iframe-delivery.md`
- `docs/adr/0015-widget-ui-rendering-and-interaction-model.md`
- `docs/04_Engineering/Widget_Responsive_Visual_and_Release_Readiness.md`
- `docs/07_Testing/Widget_Release_Readiness_Checklist.md`
- `planning/tasks/TASK-066A-widget-controlled-pilot-deployment-operations-architecture.md`