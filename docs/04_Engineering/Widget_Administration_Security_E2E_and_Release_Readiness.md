# Widget Administration Security, E2E, and Release Readiness

TASK-067B5 hardens the authenticated widget administration lifecycle and defines the controlled-pilot administration release gate.

## Test Architecture

The current repository has API integration tests and web component tests, plus Playwright coverage for the public widget runtime. B5 adds a dedicated API hardening suite and extends the widget admin frontend test suite. The admin browser release gate is represented by `npm run widget:admin:e2e`, which currently runs the authenticated admin component workflow coverage. A future hosted-auth task should replace this with full Playwright navigation against a real web server.

## Auth Fixture

Administration tests use the existing development-only dashboard headers and real tenant membership rows. This does not disable auth globally and does not add a production bypass. The backend still resolves organisation membership server-side and rejects unauthorized roles.

## Tenant Fixtures

Synthetic Alpha/Beta tenants, workspaces, users, widgets, origins, credentials, documents, and revisions are created in isolated test databases. No production data or customer records are used.

## Security Evidence

| Control | Implementation | Automated evidence | Status |
| --- | --- | --- | --- |
| Tenant isolation | Admin routes load widgets through organisation/workspace scope | Cross-tenant route matrix in `test_widget_admin_b5_hardening.py` | Covered |
| RBAC | `org_owner` and `client_admin` dependencies protect widget admin routes | Viewer create/read/rotate denial tests | Covered |
| Optimistic concurrency | Draft publish uses draft ID and concurrency version | Stale publish rejected with 409 | Covered |
| Rollback concurrency | Rollback requires expected active published revision ID | Stale rollback rejected with 409 | Covered |
| Immutable revisions | No mutation route exists for historical revisions | Historical revision PATCH returns 405 | Covered |
| Knowledge isolation | Draft scope accepts only same-tenant documents | Beta document ID rejected for Alpha widget | Covered |
| Knowledge readiness | Publish validation checks current selected documents | Deleted/unavailable selected document blocks publish | Covered |
| Preview grant | Grant is short-lived, signed, tenant/widget/draft/actor-bound | Cross-tenant and non-draft grant tests; token not in audit/frontend DOM | Covered |
| Public key rotation | Immediate cutover revokes old credential | Old key denied; new key must re-observe installation | Covered |
| Embed security | Server-controlled managed/pinned snippets rendered as text | Frontend inert snippet and no `latest` assertions | Covered |
| Audit | Widget admin mutations write safe audit events | Required actions asserted; raw public keys/tokens absent | Covered |

## Accessibility Evidence

| Area | Evidence | Status |
| --- | --- | --- |
| Form labels | Admin settings tests query labelled inputs | Covered |
| Dialog labels | Publish and rotate dialogs use accessible names | Covered |
| Status messages | Save, conflict, publish, rollback, and copy statuses use visible text/roles | Covered |
| Preview iframe | Iframe has a title and constrained sandbox | Covered |
| Keyboard operation | Controls are native buttons/inputs/selects with no mouse-only custom controls | Covered by component structure |
| Responsive behavior | Admin CSS uses grid/list wrapping and scrollable code blocks; public widget browser matrix remains active | Covered, manual viewport review still required before GA |
| Manual AT | NVDA/VoiceOver/manual zoom review | Required before GA |

## Readiness Commands

```bash
npm run widget:admin:e2e
npm run widget:admin:a11y
npm run widget:admin:security
npm run widget:admin:release:verify
```

`npm run widget:admin:release:verify` runs API hardening tests, admin frontend tests, web lint/build, public widget pilot verification, pilot readiness, and writes `artifacts/widget-admin-readiness/report.json`.

## Readiness Report

`artifacts/widget-admin-readiness/report.json` contains safe status fields for admin API, tenant isolation, RBAC, draft concurrency, publish, rollback, knowledge isolation, preview security, embed security, audit, accessibility, responsive behavior, and public widget regression. It does not include preview tokens, session tokens, credentials, raw conversation content, or customer data.

## CI

The verify workflow runs the widget admin release gate and uploads `artifacts/widget-admin-readiness` with seven-day retention. Failure artifacts remain limited to synthetic test data.

## Residual Risks

- Full conversational/RAG draft preview is deferred; the current preview is configuration-faithful.
- Admin Playwright coverage is represented by component workflow tests until hosted authenticated web-server fixtures are introduced.
- Automated accessibility checks do not replace manual assistive-technology testing.
- Controlled-pilot readiness is not GA readiness and does not imply production deployment.
