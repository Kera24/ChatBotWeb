# TASK-066A - Widget Controlled-Pilot Deployment and Operations Architecture

Status: Proposed
Sprint: Sprint 3F - Widget Pilot and Operations
Task type: Architecture and planning only

## Objective

Define the production deployment, delivery, versioning, security-header, caching, rollback, smoke-testing, observability, and controlled-pilot operating architecture for the Yoranix embeddable widget and public widget APIs.

The architecture creates a clear path from the locally verified widget to a controlled production pilot without deploying infrastructure, provisioning cloud resources, changing DNS, modifying runtime behavior, changing public APIs, or adding an admin/publishing UI.

## Source Documents Read

- `docs/00_Foundation/AI_PLATFORM_MANIFESTO.md`
- `implementation-pack/02_Architecture/09_Embeddable_Widget_SDK_Architecture.md`
- `implementation-pack/05_Design/02_Widget_UI_Interaction_Architecture.md`
- `implementation-pack/00_Operating_Model/03_Architecture_Implementation_Task_Pattern.md`
- `docs/adr/0014-widget-sdk-and-iframe-delivery.md`
- `docs/adr/0015-widget-ui-rendering-and-interaction-model.md`
- `docs/04_Engineering/Widget_Responsive_Visual_and_Release_Readiness.md`
- Related public widget API, security, SDK, browser-test, and release-readiness documents listed in the request.

## Scope

This task defines domain topology, environment and controlled-pilot model, SDK/iframe/API versioning, cache/CORS/CSP/security-header policy, real-backend smoke tests, tenant-isolation smoke tests, observability, privacy-preserving logs, alerting, SLO, incident, rollback, kill-switch architecture, pilot gates, ADR-0016, and implementation split.

## Out Of Scope

This task does not implement or change production infrastructure, DNS, CDN configuration, backend runtime behavior, public APIs, monitoring vendors, admin UI, publishing UI, telemetry collection, analytics, widget features, or deployment automation.

## Architecture Decisions

- Use production-grade infrastructure for pilot with explicit tenant/widget allowlisting, not a permanently divergent pilot stack.
- Use separate public domains for administration, authenticated API, widget iframe, SDK/static assets, and public widget API.
- Deliver immutable versioned SDK loader assets plus a major-version alias; avoid uncontrolled `latest` in production customer snippets.
- Keep iframe app independently deployable behind a compatible release channel while maintaining protocol-major compatibility with loader SDK v1.
- Cache immutable hashed/versioned assets for one year; keep iframe HTML short-cache/revalidated; mark session/message responses `no-store`.
- Keep session tokens, drafts, messages, answers, citations, and idempotency keys inside the iframe boundary.
- Classify the widget as controlled-pilot ready, not GA.

## Required Future Implementation Tasks

- `TASK-066B1` - Production deployment configuration, domains/environment wiring, CDN/static delivery, security headers, caching/versioning.
- `TASK-066B2` - Synthetic widget/tenant, real-backend smoke tests, tenant-isolation smoke tests, release verification.
- `TASK-066B3` - Operational metrics/logging/health checks, alerts, runbooks, rollback and kill-switch operational controls.

## Acceptance Criteria

TASK-066A is complete when deployment topology, domain boundaries, SDK/iframe/API delivery, versioning, cache policy, CORS/security headers, pilot model, synthetic smoke, tenant-isolation smoke, logging/privacy, observability, alerting, rollback, release channels, pilot/GA gates, ADR-0016, implementation split, and diagrams are documented, and no production infrastructure is deployed.