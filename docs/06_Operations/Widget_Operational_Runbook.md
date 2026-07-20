# Widget Operational Runbook

Status: TASK-066B3 provider-neutral pilot operations

## Service Overview

The public widget surface includes:

- static SDK and iframe release artifacts
- public widget configuration endpoint
- anonymous public session endpoint
- public widget message endpoint

The iframe owns public API calls and session storage. The host page must not receive tokens, messages, answers, citations, or backend responses.

## Health Checks

Liveness:

```text
GET /health/live
```

Returns only:

```json
{"status":"ok"}
```

Readiness:

```text
GET /health/ready
```

Checks database connectivity, retrieval-provider construction, and public-widget service initialization. It does not create sessions, run retrieval, or call a model provider.

## Correlation IDs

Public widget routes accept `X-Request-ID` only when it matches the safe bounded format. Invalid, long, or control-character values are replaced by a server-generated opaque ID.

Operators may use request IDs for troubleshooting. They must not request session tokens or browser storage dumps.

## Structured Logs

Allowed operational fields include request ID, route/event type, outcome, safe error category, latency, channel, and pseudonymous widget reference.

Never log:

- session tokens
- Authorization headers
- cookies
- raw message bodies
- answers
- citation quotes
- prompts
- retrieved context
- database URLs
- provider credentials

## Metrics and Events

The repository provides vendor-neutral in-memory counters for tests and future adapter wiring. Safe labels are route and status category only. Do not label metrics by raw public key, origin, session token, request ID, or message text.

## Pilot Enablement

Initial pilot allowlisting is server-side configuration:

- `PUBLIC_WIDGET_PILOT_ENFORCEMENT_ENABLED`
- `PUBLIC_WIDGET_PILOT_ALLOWLIST`

When enforcement is enabled, a widget public identifier must be listed before public config/session/message access is allowed.

## Kill Switches

Global service:

- `PUBLIC_WIDGETS_ENABLED=false`

Disables config, session, and message routes.

Global message sending:

- `PUBLIC_WIDGET_MESSAGES_ENABLED=false`

Keeps config/session behavior as configured but rejects message sends, including existing sessions.

Widget-specific disablement:

- `PUBLIC_WIDGET_DISABLED_WIDGETS=wpk_...`

Rejects public widget access for listed widget public identifiers.

Environment-based switches require process restart/reload unless the deployment platform provides dynamic configuration.

## Safe Diagnostics

Operators may ask for:

- request ID
- approximate timestamp
- customer website origin
- public widget identifier where appropriate
- screenshot of generic error state

Operators must not ask for:

- session token
- Authorization header
- raw browser storage
- secrets
- conversation content unless intentionally supplied through an approved support process

## Post-Change Verification

After operational changes:

```bash
npm run widget:ops:validate
npm run widget:pilot:verify
npm run widget:pilot:readiness
```

Production/staging deployments must also run post-deploy real smoke in that environment.

