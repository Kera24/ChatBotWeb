# Public Widget Configuration Endpoint

Status: Implemented in TASK-062B

## Endpoint

```text
GET /api/v1/widget/{public_key}/config
OPTIONS /api/v1/widget/{public_key}/config
```

This public endpoint returns only published, sanitised widget configuration. It does not create an anonymous session, create a conversation, accept a message, call retrieval, call RAG, call AI Core, or expose provider/model/prompt/policy internals.

The only implemented public widget endpoints are now:

- `GET /api/v1/widget/{public_key}/config`
- `POST /api/v1/widget/{public_key}/sessions`
- Route-scoped `OPTIONS` handlers for those paths

## Request

The `GET` request has no body and no functional query parameters. Unsupported query parameters are rejected.

Required HTTP context:

- `Origin` header.
- Server-derived client IP for rate limiting.
- Optional bounded `X-Request-ID`.
- Optional bounded `User-Agent` for operational context only.

The route rejects dashboard bearer tokens, `X-Development-User-Email`, `X-Development-Role`, tenant IDs, credential IDs, session tokens, messages, conversation IDs, policy overrides, model/provider/prompt keys, and branding overrides.

## Gateway Flow

The route is a thin HTTP adapter into the Public Access Gateway in `config_read` mode:

1. Parse route and headers.
2. Reject dashboard/development auth headers.
3. Resolve the widget channel adapter.
4. Resolve the public widget credential and tenant context.
5. Validate request shape and size.
6. Validate Origin.
7. Apply `widget_config_read` rate limits.
8. Load the published widget configuration.
9. Project a sanitised public response.
10. Return with dynamic CORS, ETag, and cache headers.

## Response

Successful response status is `200`:

```json
{
  "widget": {
    "bot_name": "Admissions",
    "welcome_message": "Ask us about courses.",
    "launcher_label": "Chat now",
    "primary_colour": "#0f766e",
    "secondary_colour": "#111827",
    "logo_url": "https://cdn.example.test/logo.png",
    "avatar_url": null,
    "position": "bottom_right",
    "theme_mode": "system",
    "language": "en"
  },
  "behaviour": {
    "suggested_questions": ["How do I apply?"],
    "max_initial_suggestions": 1,
    "show_citations": true,
    "allow_conversation_history": false,
    "session_required": true,
    "messages_enabled": true
  },
  "privacy": {
    "privacy_notice_text": null,
    "privacy_notice_url": null,
    "terms_url": null,
    "fallback_contact_text": null
  },
  "capabilities": {
    "can_create_session": true,
    "can_send_messages": true,
    "citations_enabled": true,
    "conversation_history_enabled": false
  },
  "configuration_version": 1,
  "response_schema_version": "1.0",
  "published_at": "2026-07-15T00:00:00+00:00",
  "request_id": "access_..."
}
```

Excluded fields include organisation ID, workspace ID, credential database ID, internal config ID, allowed origins, policy profile, rate-limit values, retrieval/context/token limits, model/provider/prompt details, internal asset paths, metadata JSON, audit fields, secret/hash values, and environment.

## Origin And CORS

`Origin` is required for GET and OPTIONS. Dynamic CORS is route-scoped:

- `Access-Control-Allow-Origin` echoes only the validated Origin.
- `Vary: Origin` is always included on successful config/preflight responses.
- `Access-Control-Allow-Credentials: false`.
- Allowed methods: `GET, OPTIONS`.
- Allowed headers: `If-None-Match, X-Request-ID`.
- No wildcard Origin is emitted.
- Rejected origins do not receive permissive CORS headers.

## Rate Limiting

The endpoint uses `widget_config_read`. Rules evaluate configured global, channel, credential, workspace, organisation, and IP dimensions where present. Redis-backed decisions are used first. Constrained local fallback is available only when enabled and only for fail modes that permit it. There is no unlimited fail-open.

`429` responses include `Retry-After` when available.

## ETag And Cache

A strong quoted ETag is generated from canonical JSON of the sanitised public projection, excluding `request_id`. It does not include tenant IDs, internal IDs, secrets, paths, or raw public keys.

`If-None-Match` is supported. A matching ETag returns `304 Not Modified` with no body and includes ETag, `Vary: Origin`, validated CORS headers, and `Cache-Control`.

Successful responses use:

```text
Cache-Control: public, max-age=60, stale-while-revalidate=30
```

Public errors use conservative no-store handling.

## Asset Projection

Logo and avatar values are projected through a public-safe boundary:

- HTTPS raster URLs with `.png`, `.jpg`, `.jpeg`, or `.webp` are allowed.
- Relative asset paths are emitted only when `PUBLIC_WIDGET_ASSET_BASE_URL` is configured as a safe HTTPS base URL.
- `file:`, `data:`, `javascript:`, HTTP production URLs, SVG, local paths, and unsafe internal paths are omitted.
- Missing or invalid assets return `null` and do not fail the whole config response.

## Safe Errors

Common public mappings:

- `invalid_widget`: 404
- `origin_required`: 403
- `origin_not_allowed`: 403
- `malformed_origin`: 400
- `rate_limited`: 429
- `temporarily_unavailable`: 503
- `safe_internal_error`: 500

Errors include a safe request ID. They do not expose tenant IDs, configured origins, internal config status, storage paths, Redis/database details, stack traces, raw public keys, or raw origins.

## Observability

Safe events include:

- `widget.config.requested`
- `widget.config.served`
- `widget.config.not_modified`
- `widget.config.rejected`
- `widget.config.origin_denied`
- `widget.config.rate_limited`
- `widget.config.unavailable`
- `widget.config.asset_omitted`
- `widget.config.degraded_rate_limit`

Events do not include raw public key, raw Origin, full config payload, privacy text, session token, asset internal paths, or User-Agent.

## Local Testing

```bash
cd apps/api
python -m pytest tests/test_public_widget_configuration_endpoint.py
```

Example request after creating an active widget key, allowed Origin, and published widget configuration:

```bash
curl -i \
  -H "Origin: http://localhost:3000" \
  http://localhost:8000/api/v1/widget/{public_key}/config
```

Conditional request:

```bash
curl -i \
  -H "Origin: http://localhost:3000" \
  -H 'If-None-Match: "<etag>"' \
  http://localhost:8000/api/v1/widget/{public_key}/config
```

## TASK-067B1 Revision-Aware Public Configuration

The public configuration endpoint now prefers `Widget.active_published_revision_id` and serializes the referenced immutable `WidgetConfigurationRevision`. Draft revisions are never served publicly. A legacy `WidgetConfiguration` fallback remains only for compatibility with pre-revision data during migration rollout.
