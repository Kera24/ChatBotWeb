# Production Environment Variables Guide

Companion doc to `.env.production.example` (repo root). That file is the
source of truth for defaults - this doc explains *why* each group exists and
what happens if you get it wrong. Read
[VPS_Deployment_Guide.md](./VPS_Deployment_Guide.md) first for the deployment
sequence this fits into.

## Mandatory - required for a correct, secure launch

| Variable | Consumed by | Wrong value causes |
|---|---|---|
| `WEB_DOMAIN`, `API_DOMAIN`, `WIDGET_DOMAIN`, `TLS_EMAIL` | `deployment/caddy/Caddyfile` | Caddy cannot obtain/renew TLS certs; site unreachable over HTTPS |
| `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD` | `postgres` service (first-run init only) | Wrong password after first init requires a DB user password change, not a redeploy |
| `DATABASE_URL` | `apps/api/app/core/config.py` | Must match the above three exactly (`postgresql+psycopg://user:pass@postgres:5432/db`) or the API/migrate containers fail to connect |
| `REDIS_URL` | rate limiting (`app/access/rate_limit`), idempotency | If wrong, rate limiting fails closed (`temporarily_unavailable`) for public widget messages |
| `APP_ENV=production` | `app/core/config.py`, `app/api/v1/auth.py` | If unset/wrong, the session cookie's `Secure` flag is **not** set - session cookies would be sent over plain HTTP |
| `WEB_ORIGIN` | CORS on `/api/v1/auth/*` (`app/main.py`) | Must exactly equal `https://<WEB_DOMAIN>` or the web app cannot call the authenticated API (CORS rejected) |
| `NEXT_PUBLIC_API_BASE_URL` | Next.js build (baked in at `web` image build time) | Must equal `https://<API_DOMAIN>`; changing it after build requires rebuilding the `web` image, not just restarting the container |
| `AUTH_SESSION_HASH_SECRET`, `RATE_LIMIT_IDENTITY_SECRET`, `PUBLIC_SESSION_TOKEN_HASH_SECRET`, `PUBLIC_MESSAGE_IDEMPOTENCY_HASH_SECRET` | auth/session/rate-limit/idempotency hashing | Each ships a `dev-...-change-me` default in code (`app/core/config.py`) - **nothing enforces overriding them**. Leaving any at its default is a real credential-forgery / session-hijack risk. Generate independently with `openssl rand -hex 32`; do not reuse one value across all four. |
| `LOCAL_UPLOAD_ROOT` | document storage (`app/services/local_storage.py`) | Must point at the mounted `uploads_data` volume path (`/app/apps/api/local_uploads`) or uploads are lost on container recreation |
| `WIDGET_PUBLIC_ORIGIN`, `WIDGET_PUBLIC_API_ORIGIN`, `WIDGET_SDK_PUBLIC_ORIGIN` | `deployment/widget/Dockerfile` build (`apps/widget/scripts/release-config.mjs`) | Must be real HTTPS, non-localhost origins - the release-config validator rejects the build otherwise |
| `EMBEDDING_PROVIDER`/`DEFAULT_AI_PROVIDER_KEY` | RAG pipeline | Left at `local-mock`/`mock`, the product works but with placeholder (non-semantic) embeddings/answers - fine for a controlled early-access cohort validated against the golden evaluation, not for broad public launch on real customer data |

## Optional - safe defaults exist

Everything under the "OPTIONAL" section of `.env.production.example`:
session lifetimes, rate-limit tuning, upload/chunking/retrieval limits,
public-message quotas, and the `EVAL_*` evaluation thresholds. The `EVAL_*`
defaults are the same numbers validated in the 83-case golden evaluation
(`docs/04_Engineering/Evaluation_Success_Criteria.md`); only change them if
you re-run and re-approve that evaluation against the new numbers - a looser
threshold with no re-validation is a silent quality regression, not a
config tweak.

`LOG_LEVEL` is passed straight to uvicorn's `--log-level` flag (wired in
`docker-compose.prod.yml`); default `info`.

## Billing (Stripe) - optional at launch

Leave `STRIPE_SECRET_KEY`/`STRIPE_WEBHOOK_SECRET` empty to launch without
billing enforcement: checkout/portal endpoints return 400, the webhook
endpoint returns 503, and everything else in the product works normally
(confirmed by `apps/api/tests/test_billing_api.py`). See
[Stripe_Setup_Checklist.md](./Stripe_Setup_Checklist.md) for turning it on.

## Development-only - must be unset in production

`NEXT_PUBLIC_DEVELOPMENT_*` and `MOCK_PROVIDER_FAILURE_MODE` exist purely to
make local development frictionless (impersonating a user/org without
logging in, injecting synthetic provider failures). They are commented out in
`.env.production.example` on purpose - do not uncomment them on a public
deployment.

## Future Azure variables

`APPLICATIONINSIGHTS_CONNECTION_STRING` and the `AZURE_MONITOR_*` variables
are read by `app/operations/telemetry.py`, which no-ops gracefully if they
are absent (confirmed: it's wrapped in a broad try/except and gated by
`AZURE_MONITOR_OPEN_TELEMETRY_ENABLED=false` by default). They are listed in
`.env.production.example` only so the two deployment targets share one
documented variable surface - see
[Future_Azure_Migration_Notes.md](./Future_Azure_Migration_Notes.md). Leave
them unset on the VPS.
