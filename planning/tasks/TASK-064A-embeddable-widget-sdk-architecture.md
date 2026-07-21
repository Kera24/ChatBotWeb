# TASK-064A - Embeddable Widget SDK Architecture

Status: Planning
Phase: Sprint 3D - Embeddable Widget

## Objective

Design the embeddable browser SDK that customer websites will install to load and control the future Yoranix website-chat widget. This task is architecture and planning only.

## Sources Read

- `docs/00_Foundation/AI_PLATFORM_MANIFESTO.md`
- Public Access, widget session/config/message architecture documents through `08_Public_Widget_Message_RAG_Architecture.md`
- `implementation-pack/07_Security/02_Public_Widget_Security_Architecture.md`
- `implementation-pack/00_Operating_Model/03_Architecture_Implementation_Task_Pattern.md`
- ADRs `0005`, `0011`, `0012`, `0013`
- TASK-061B, TASK-062B, TASK-063B3, TASK-063B4 planning and engineering docs
- Web app package/config/design context files

## Scope

Create planning artifacts for:

- Loader SDK and visual widget boundary.
- Sandboxed iframe delivery decision.
- Installation contract.
- SDK API and lifecycle.
- SDK/iframe postMessage protocol.
- API ownership and token storage decisions.
- CSP, iframe sandbox, accessibility, versioning, deployment, and performance budgets.
- Threat model, failure matrix, diagrams, and future implementation split.

## Non-Goals

Do not implement JavaScript bundles, iframe pages, widget UI, package publishing, build tooling, public history, analytics, lead capture, or backend changes.

## Architecture Decision Summary

MVP uses a small versioned loader SDK plus a platform-hosted sandboxed iframe. The iframe owns public config/session/message API calls and stores anonymous public session tokens in iframe-origin `sessionStorage` with an in-memory fallback. Session tokens never enter the host page JavaScript context, never cross postMessage, and never appear in iframe URLs.

The visual widget UI is a separate future application. The SDK owns bootstrap, mounting, lifecycle, postMessage transport, safe controls, and failure fallback only.

## Future Implementation Tasks

- `TASK-064B1` - SDK package/build foundation.
- `TASK-064B2` - Iframe shell and secure handshake.
- `TASK-064B3` - SDK lifecycle, mounting, public API, and host integration.
- `TASK-064B4` - Iframe API client and session storage.
- `TASK-064B5` - Browser integration and security tests.
- `TASK-065A` - Widget UI and Interaction Architecture.
- `TASK-065B` - Widget UI Implementation.

## Acceptance Criteria

- SDK and UI boundaries are explicit.
- Iframe delivery decision is recorded.
- Session token remains inside iframe origin.
- API-call ownership is defined.
- postMessage protocol is complete.
- Lifecycle, failure, CSP, accessibility, versioning, performance, threat model, and diagrams are documented.
- ADR-0014 records the decision.
- No runtime code is added.