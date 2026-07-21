# Widget Incident Response Runbook

Status: TASK-066B3 provider-neutral incident guidance

## Severity

Critical:

- suspected tenant isolation failure
- suspected session-token leakage
- public widget service unavailable
- sustained public API 5xx spike

Incident:

- synthetic smoke repeatedly failing
- session creation error spike
- message error spike
- retrieval/provider dependency outage

Warning:

- elevated latency
- elevated rate limiting
- abnormal origin-denial spike

## Common Flow

1. Classify the incident.
2. Preserve safe evidence: request IDs, timestamps, status codes, safe error categories.
3. Contain the smallest safe scope.
4. Run relevant synthetic verification.
5. Roll back or disable if needed.
6. Restore only after verification passes.
7. Record outcome and residual risk.

## Containment Modes

One widget incident:

- add the widget public identifier to `PUBLIC_WIDGET_DISABLED_WIDGETS`

One tenant incident:

- disable the tenant's public widget credentials through existing credential/status controls where available

Message/RAG/provider incident:

- set `PUBLIC_WIDGET_MESSAGES_ENABLED=false`

Public widget platform incident:

- set `PUBLIC_WIDGETS_ENABLED=false`

Bad frontend release:

- plan rollback with `npm run widget:rollback:plan`
- repoint the SDK major alias or iframe release mapping in deployment infrastructure

Bad backend release:

- roll back backend artifact through deployment infrastructure

## Tenant or Token Leakage

Treat as critical.

Actions:

- disable affected widget/tenant or all public widgets
- preserve safe request IDs and operational logs
- do not print token values
- run B2 tenant/session/retrieval isolation suite
- assess whether public key rotation or session signing-key response is required
- document whether the public key was exposed; public keys are identifiers, not secrets

## Abuse or Rate-Limit Incident

Actions:

- verify rate-limit signals
- avoid logging hostile Origin values verbatim
- disable message sending globally if provider cost or abuse risk is active
- keep evidence to safe categories and request IDs
