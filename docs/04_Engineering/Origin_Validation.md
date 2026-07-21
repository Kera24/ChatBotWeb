# Origin Validation

Status: Implemented foundation. No public widget endpoint or CORS middleware exists.

## Module Layout

TASK-058B adds the origin-validation package under `apps/api/app/access/origin_validation`:

- `contracts.py` defines `OriginValidationRequest`, `CanonicalOrigin`, `AllowedOriginRecord`, and `OriginValidationResult`.
- `normalisation.py` parses and canonicalises browser origin values.
- `matcher.py` performs exact and controlled wildcard matching.
- `repository.py` reads active allowed-origin records from `credential_allowed_origins` by credential and environment.
- `service.py` coordinates policy checks, normalisation, environment restrictions, matching, safe errors, and events.
- `errors.py` contains origin-specific exception helpers.

## Normalisation

The canonical runtime form is:

```text
<scheme>://<hostname>:<effective_port>
```

Rules:

- Only `http` and `https` are accepted.
- Scheme and hostname are lowercased.
- IDNs are converted to ASCII punycode.
- Trailing hostname dots are removed.
- Default ports are resolved to `80` for HTTP and `443` for HTTPS.
- Explicit non-default ports are preserved.
- IPv4, bracketed IPv6, localhost, and loopback addresses are handled without DNS lookup.
- Userinfo, paths other than empty or `/`, query strings, fragments, unsupported schemes, missing hosts, malformed Unicode, and malformed IPv6 are rejected.

## Matching

Exact matching requires:

- Same scheme.
- Same normalised hostname.
- Same effective port.
- Active origin record.
- Same credential environment.
- Same resolved credential ID after service-level defensive filtering.

Wildcard matching is one label only:

- `*.example.com` allows `app.example.com`.
- It does not allow `example.com`, `a.b.example.com`, `evil-example.com`, or `example.com.evil.org`.
- Scheme and port must still match.
- Wildcards for localhost, IP addresses, global patterns, and a conservative set of common public suffixes are rejected at runtime even if legacy data exists.

The public-suffix check is intentionally conservative and dependency-free for MVP. A full public-suffix-list integration can be added later if origin policy becomes more complex.

## Environment Rules

Development:

- Explicit configured localhost and loopback origins may match.
- Port matching is required.
- Development origins never match staging or production credentials.

Staging:

- Localhost and loopback are rejected by default.

Production:

- HTTPS is required.
- HTTP origins are rejected with `insecure_origin`.
- Loopback origins are rejected.

## Missing-Origin Policy

- Widget policies with `origin_required = true` reject missing Origin with `origin_required`.
- Partner API policies with `origin_required = false` bypass browser-origin validation; partner secret authentication remains future work.
- Internal test policy can skip origin validation in isolated tests only.
- Referer fallback remains an extension point and is not enabled for state-changing widget behaviour.

## Gateway Integration

`PublicAccessGateway` accepts an optional injected `OriginValidationService`. When present, the gateway validates origin after tenant and policy resolution and after request/message limit checks.

The gateway still stops before:

- rate limiting
- anonymous sessions
- abuse checks
- cost enforcement
- RAG orchestration
- response generation

No public route was added.

## Safe Errors

The public error catalog includes:

- `origin_required`
- `origin_not_allowed`
- `malformed_origin`
- `insecure_origin`
- `unsupported_origin_scheme`
- `temporarily_unavailable`

Errors do not include configured origin lists, organisation IDs, workspace IDs, raw headers, stack traces, or database details.

## Events

The service emits safe operational events through the existing access event sink:

- `origin.validation.allowed`
- `origin.validation.denied`
- `origin.validation.missing`
- `origin.validation.malformed`
- `origin.validation.wildcard_matched`
- `origin.validation.development_exception`

Events include request ID, trace ID, channel, credential ID, outcome, and reason code. Raw Origin and Referer headers are not logged by default.

## Cache and Invalidation Extension Point

TASK-058B uses repository reads directly. No Redis cache is implemented.

The service accepts an origin lookup callable, which is the extension point for future cache-backed lookup. Existing origin add/remove admin operations already emit audit events; a later cache task can subscribe to those service boundaries or add explicit invalidation wiring.

## Limitations

- Origin validation is not authentication.
- Server-to-server callers can spoof Origin headers.
- Domain ownership verification is not implemented.
- CORS middleware is not implemented.
- Public widget endpoints are not implemented.
- Redis rate limiting and anonymous sessions are not implemented.
- Referer fallback is not enabled for widget message/session behaviour.

## Local Tests

Focused origin-validation tests:

```bash
cd apps/api
python -m pytest tests/test_origin_validation.py
```

Repository verification:

```bash
npm run api:test
npm run verify
```
