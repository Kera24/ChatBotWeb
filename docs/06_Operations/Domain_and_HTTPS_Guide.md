# Domain and HTTPS Guide

No real domain is hardcoded anywhere in this repository - `deployment/caddy/Caddyfile`
reads `WEB_DOMAIN`, `API_DOMAIN`, `WIDGET_DOMAIN`, and `TLS_EMAIL` from the
environment (see `.env.production.example`).

## Option A - three subdomains (recommended, matches the shipped Caddyfile)

```
app.example.com     -> WEB_DOMAIN     -> web (Next.js)
api.example.com     -> API_DOMAIN     -> api (FastAPI)
widget.example.com  -> WIDGET_DOMAIN  -> static widget SDK + iframe bundle
```

Create three A (and/or AAAA) records pointing at the VPS's public IP before
starting the stack - Caddy requests a Let's Encrypt certificate per domain on
first request to it, and DNS must already resolve or issuance fails (it
retries automatically once DNS is fixed, no restart needed).

## Option B - two domains, widget under an API path

If you'd rather not manage a third subdomain, widget assets can be served
under the API domain at a path prefix (e.g. `api.example.com/widget-assets/`)
instead of `WIDGET_DOMAIN`. This requires moving the widget `handle` blocks
from the `{$WIDGET_DOMAIN}` site block into the `{$API_DOMAIN}` block in
`deployment/caddy/Caddyfile` and updating `WIDGET_PUBLIC_ORIGIN`/
`WIDGET_SDK_PUBLIC_ORIGIN` to the API origin with that path. Not shipped by
default because keeping widget asset delivery on its own origin matches the
Cross-Origin-Resource-Policy headers already defined in
`deployment/widget/headers.json` and keeps a future CDN swap (as used in the
Azure Front Door setup) a pure DNS/origin change rather than a path rewrite.

## Certificate renewal

Caddy renews Let's Encrypt certificates automatically in the background; the
`caddy_data` named volume persists both certificates and the ACME account
key across container recreation. Nothing to schedule manually. Confirm it's
working with:

```bash
docker compose -f docker-compose.prod.yml --env-file .env.production exec caddy caddy list-certificates 2>/dev/null || \
docker compose -f docker-compose.prod.yml --env-file .env.production logs caddy | grep -i certificate
```

## Security headers already applied at the edge

Per domain, from `deployment/caddy/Caddyfile`:

- `Strict-Transport-Security` (HSTS), `X-Content-Type-Options: nosniff`,
  `Referrer-Policy`, and `-Server` (hides the Caddy version banner) on every
  site.
- Widget domain additionally applies the exact cache/CSP/Permissions-Policy
  headers documented in `deployment/widget/headers.json` (immutable SDK
  caching, no-cache iframe HTML, a locked-down iframe CSP,
  `Cross-Origin-Resource-Policy: cross-origin`).

These were **not present anywhere in the API or Next.js app itself** before
this audit (`apps/web/next.config.mjs` set no headers; FastAPI only ever set
CORS headers) - the reverse proxy is now the sole place enforcing them.
Do not remove `deployment/caddy/Caddyfile` header blocks without adding an
equivalent at the application layer first.

## Request limits and AI-response timeouts

`deployment/caddy/Caddyfile` sets `request_body { max_size }` per domain (5MB
web, 15MB API) as a coarse edge backstop; the real, feature-specific limits
(`MAX_UPLOAD_BYTES`, `PUBLIC_MESSAGE_MAX_BYTES`) are enforced by the
application and are the ones that matter for correctness. The API's
`reverse_proxy` block uses a 180s read/write timeout and `flush_interval -1`
(stream immediately, no buffering) so long AI-provider round trips or
SSE-style streaming responses aren't cut off or delayed by the proxy.

## Reverse-proxy rate limiting

Caddy's official Docker image does not include a rate-limiting module.
Public-endpoint rate limiting for this launch is enforced at the application
layer instead (Redis-backed token bucket for the public widget - see
`app/access/rate_limit/`; in-memory limiter for auth endpoints - see
`app/auth/rate_limit.py`), which is already origin/tenant-aware in a way a
generic edge limiter isn't. If you later want edge-level rate limiting too
(e.g. as DDoS backstop), build a custom Caddy image with
`github.com/mholt/caddy-ratelimit` - not done here to keep the proxy image
the stock, easily-updated `caddy:2-alpine`.
