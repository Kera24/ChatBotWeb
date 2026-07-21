# ADR-0017: Widget Publishing, Configuration, and Embed Management Model

Status: Proposed
Date: 2026-07-20

## Context

The public widget runtime now has configuration delivery, anonymous sessions, public message/RAG handling, iframe SDK/UI, production release artifacts, synthetic real-backend verification, and operational pilot controls.

The next boundary is authenticated administration: how organisation administrators configure and publish widgets without exposing draft state, weakening tenant isolation, conflating pilot controls with publication, or making rollback unsafe.

The current implementation has `PublicCredential`, `CredentialAllowedOrigin`, and a single mutable `WidgetConfiguration` row per credential. That model was enough for early public configuration delivery, but it cannot support durable draft editing and immutable published snapshots at the same time.

## Decision

Use stable widget identity plus immutable versioned configuration revisions with one active published revision.

Separate these concepts:

- Widget identity: stable product object.
- Public key: public access credential, rotatable and not secret.
- Draft configuration: editable authenticated admin state.
- Published configuration revision: immutable public-serving snapshot.
- Operational state: enabled/disabled/archived.
- Pilot state: internal controlled-pilot approval.
- Release channel/version: deployment compatibility control.

Publication promotes or creates an immutable revision and updates the active published revision pointer atomically. Public configuration reads only the active published revision. Draft edits never change public responses until publish.

Rollback creates a new publication event and preferably a new published revision cloned from a previous immutable revision, so active publication versions remain monotonic and audit-friendly.

## Alternatives Considered

### A. Mutable Widget Configuration Row

Rejected as target. It matches the current implementation, but draft edits can invalidate the published snapshot and make rollback/audit weak.

### B. Draft And Published Pair

Rejected as the long-term model. It is simpler than revisions, but keeps only one previous state and makes history, diff, and rollback limited.

### C. Immutable Versioned Configuration Revisions

Chosen. It supports safe drafts, immutable public snapshots, ETag stability, audit, rollback, diff, and future pilot/stable promotion without overbuilding event sourcing.

### D. Full Event Sourcing

Rejected for now. It is powerful, but too complex for the current product phase and implementation capacity.

## Consequences

Positive:

- Draft edits do not leak into public widget config.
- Public configuration ETags can derive from active revision content.
- Previous published configurations are available for rollback.
- Publishing and pilot enablement remain separate.
- Admin diff/review workflows become straightforward.
- Tenant isolation can be tested at widget, revision, origin, and public-key boundaries.

Trade-offs:

- Requires a migration from current one-row configuration.
- Requires publish transactions and active revision pointers.
- Requires admin APIs to handle optimistic concurrency.
- Requires clearer UI around draft, published, disabled, pilot, and release channel states.

## Publication Semantics

Publishing:

1. Authorizes `widget:publish`.
2. Validates exact draft revision.
3. Validates origins, branding, URLs, suggested questions, knowledge readiness, privacy fields, and release compatibility.
4. Creates/promotes immutable published revision.
5. Updates active published pointer.
6. Changes public config ETag.
7. Writes audit event.

Publishing does not automatically pilot-enable the widget.

## Public Key Semantics

Widget public keys are public identifiers, not secrets. They may be shown in admin UI and embed snippets. Security relies on allowed origins, public access validation, anonymous session policy, rate limits, tenant-scoped retrieval, and operational controls.

Rotation is audited and should use immediate cutover initially unless dual-key grace is explicitly implemented later.

## Origin Semantics

Allowed origins remain normalized records separate from the configuration JSON. Initial production administration supports exact HTTPS origins only. Wildcard subdomains require a later review.

## Embed Semantics

Default embed snippets use the platform-managed SDK major alias. Advanced pinned semantic SDK versions may be offered only from supported release manifests. No arbitrary SDK/API/iframe URL override is allowed.

## Preview Semantics

Draft preview uses an authenticated short-lived preview grant tied to widget, tenant, and draft revision. Preview must not expose draft configuration through the public config endpoint and must not create ordinary public anonymous sessions.

## Related Documents

- `implementation-pack/02_Architecture/11_Widget_Administration_Publishing_and_Embed_Management_Architecture.md`
- `implementation-pack/02_Architecture/10_Widget_Controlled_Pilot_Deployment_and_Operations_Architecture.md`
- `docs/adr/0016-widget-deployment-versioning-and-release-model.md`
- `docs/04_Engineering/Public_Widget_Configuration_Endpoint.md`
- `planning/tasks/TASK-067A-widget-administration-publishing-embed-management-architecture.md`
