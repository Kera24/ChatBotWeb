# Public Widget Session Endpoint

Status: Implemented in TASK-061B

## Endpoint

```text
POST /api/v1/widget/{public_key}/sessions
OPTIONS /api/v1/widget/{public_key}/sessions
```

This is the only implemented public widget endpoint. It creates an anonymous public session and returns a safe bearer token for future widget message work. It does not accept messages, create conversations, call retrieval, call RAG, call AI Core, or expose widget branding/configuration beyond approved session capability fields.

## Request

The request body is optional and may be empty JSON:

```json
{}
```

Allowed fields are:

- `client_request_id`, optional bounded string for telemetry only.
- `metadata`, optional bounded scalar metadata.
- `requested_language`, optional bounded string for future safe policy use.

The endpoint rejects tenant IDs, credential IDs, conversation/session IDs, message content, email, phone, user identity, origin/IP body fields, provider/model/prompt keys, policy overrides, timeout overrides, and limit overrides.

Required HTTP context:

- `Origin` header.
- JSON content type when a body is sent.
- Peer/client IP resolved server-side using trusted-proxy rules.
- Optional bounded `User-Agent`.
- Optional `X-Request-ID`; otherwise the server generates a request ID.

No cookies, CSRF token, dashboard bearer token, or development auth headers are used.

## Gateway Flow

The route is a thin HTTP adapter into the Public Access Gateway:

1. Parse route and request body.
2. Reject dashboard/development headers.
3. Resolve widget channel adapter.
4. Resolve database-backed public credential and tenant context.
5. Verify active organisation/workspace and policy profile.
6. Verify published widget configuration through the gateway session-creation enrichment hook.
7. Validate `Origin`.
8. Apply `widget_session_create` rate limits.
9. Create an anonymous public session with `PublicSessionService`.
10. Return a safe public response.

## Credential And Configuration Requirements

Session creation requires:

- Credential type `widget_public_key`.
- Credential status `active`.
- Credential not expired, revoked, disabled, deleted, or wrong type.
- Active organisation and workspace, with workspace belonging to the organisation.
- Valid widget policy profile.
- Existing published widget configuration with `published_at` set.
- Active allowed Origin record matching the request Origin.

Invalid, missing, disabled, revoked, expired, wrong-type, inaccessible, unpublished, or missing widget state maps to an enumeration-resistant `invalid_widget` response.

## Response

Successful response status is `201`:

```json
{
  "session_token": "pss_dev_<token_id>.<secret>",
  "expires_at": "2026-07-15T00:30:00+00:00",
  "absolute_expires_at": "2026-07-16T00:00:00+00:00",
  "inactivity_timeout_seconds": 1800,
  "max_messages": 30,
  "remaining_messages": 30,
  "configuration_version": 1,
  "capabilities": {
    "can_send_messages": true,
    "conversation_history_enabled": true,
    "citations_enabled": true
  },
  "request_id": "access_..."
}
```

The response excludes organisation ID, workspace ID, internal session ID, internal credential ID, conversation ID, token ID, token hash, policy profile, rate-limit rules, allowed origins, provider/model/prompt details, internal environment, and internal widget configuration fields.

## Origin And CORS

`Origin` is required for POST and OPTIONS. The route-specific CORS behavior:

- Validates credential and Origin before allowing CORS.
- Echoes only the validated Origin in `Access-Control-Allow-Origin`.
- Adds `Vary: Origin`.
- Allows only `POST` and `OPTIONS`.
- Allows `Content-Type` and `X-Request-ID` headers.
- Sets `Access-Control-Allow-Credentials: false`.
- Never uses wildcard Origin.
- Fails closed without exposing configured origins.

No global permissive CORS middleware is enabled.

## Rate Limiting

POST uses the `widget_session_create` category. Policy rules cover credential, workspace, and IP dimensions, with global/channel/organisation extension points in the rate-limit model. Redis uncertainty fails closed for session creation. `429` responses include safe `Retry-After` where available.

## Safe Errors

Public errors expose a code, safe message, retryability, HTTP status, optional `retry_after_seconds`, and request ID. They do not expose tenant IDs, configured origins, Redis/database details, stack traces, public keys, raw origins, or token material.

Common mappings:

- `invalid_widget`: `404`
- `origin_required`: `403`
- `origin_not_allowed`: `403`
- `malformed_origin`: `400`
- `invalid_request`: `400`
- `request_too_large`: `413`
- `rate_limited`: `429`
- `temporarily_unavailable`: `503`
- `safe_internal_error`: `500`

## Privacy And Observability

The endpoint does not collect PII, message content, referrer, or cookies. Client IP is used for rate limiting and is not returned. Raw public keys, raw origins, session tokens, token secrets, and token hashes are excluded from widget session events.

Safe events include:

- `widget.session.requested`
- `widget.session.created`
- `widget.session.rejected`
- `widget.session.rate_limited`
- `widget.session.origin_denied`
- `widget.session.unavailable`

## Local Testing

```bash
cd apps/api
python -m pytest tests/test_public_widget_session_endpoint.py tests/test_public_access_layer.py tests/test_public_sessions.py
```

Example curl after creating an active credential, allowed origin, and published widget configuration:

```bash
curl -i -X POST \
  -H "Origin: http://localhost:3000" \
  -H "Content-Type: application/json" \
  -d '{}' \
  http://localhost:8000/api/v1/widget/{public_key}/sessions
```