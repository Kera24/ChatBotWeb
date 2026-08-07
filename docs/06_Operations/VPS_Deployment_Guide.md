# VPS Deployment Guide (Conversa / ChatBotWeb)

Single-Linux-VPS, Docker Compose deployment. This is the initial low-cost
production target; Azure remains the documented future-scale target (see
[Future_Azure_Migration_Notes.md](./Future_Azure_Migration_Notes.md)) and its
infrastructure-as-code is untouched by this guide.

## 1. What you need before you start

- A Linux VPS (see [VPS_Capacity_Guide.md](./VPS_Capacity_Guide.md) for sizing) with Docker Engine + the Docker Compose plugin installed, and a non-root user in the `docker` group.
- Three DNS names pointed at the VPS's public IP (A/AAAA records): a web domain, an API domain, and a widget-assets domain. They may be subdomains of one domain (e.g. `app.`, `api.`, `widget.`). See [Domain_and_HTTPS_Guide.md](./Domain_and_HTTPS_Guide.md).
- Outbound HTTPS access from the VPS (for Let's Encrypt and any external AI/embedding provider).
- Ports 80 and 443 open inbound; no other ports need to be public.

## 2. Repository layout for this deployment target

| Path | Purpose |
|---|---|
| `docker-compose.prod.yml` | Production compose stack (root of repo) |
| `.env.production.example` | Template for the real `.env.production` (never commit the real file) |
| `deployment/caddy/Caddyfile` | Reverse proxy / HTTPS / static widget serving |
| `deployment/widget/Dockerfile` | Builds and publishes the widget SDK + iframe bundle into a shared volume |
| `deployment/backup/backup.sh`, `restore.sh` | Postgres + uploads backup/restore |
| `deployment/monitoring/check.sh` | Health/disk/backup-freshness check for cron/uptime monitors |
| `scripts/release-gate.mjs` | Deployment-safe test/eval/guardrail gate (see [Launch_QA_Checklist.md](./Launch_QA_Checklist.md)) |
| `scripts/vps-smoke.mjs` | Post-deploy HTTP smoke test |

`docker-compose.yml` (no `.prod`) remains the local-development file - bind
mounts, `--reload`, published Postgres/Redis ports. It is untouched by this
work and should never be used on a public host.

## 3. First-time deployment

```bash
# On the VPS, as a non-root user in the docker group:
git clone <your-repo-url> conversa && cd conversa

cp .env.production.example .env.production
# Edit .env.production: fill in every REPLACE_WITH_* / example.com placeholder.
# Generate secrets with: openssl rand -hex 32   (repeat per secret - do not reuse one value)
chmod 600 .env.production

# Sanity-check the compose file and env substitution before building anything:
docker compose -f docker-compose.prod.yml --env-file .env.production config >/dev/null

# Build all images (api/migrate share one image; web and widget-assets build separately):
docker compose -f docker-compose.prod.yml --env-file .env.production build

# Bring up data services first, let Postgres/Redis become healthy, then migrate:
docker compose -f docker-compose.prod.yml --env-file .env.production up -d postgres redis
docker compose -f docker-compose.prod.yml --env-file .env.production up migrate
# ^ exits 0 on success; docker compose up (below) also re-runs this automatically
#   as a dependency of api, so this step is a manual confirmation, not required.

# Bring up the rest of the stack:
docker compose -f docker-compose.prod.yml --env-file .env.production up -d

docker compose -f docker-compose.prod.yml --env-file .env.production ps
```

Caddy will attempt to obtain Let's Encrypt certificates for `WEB_DOMAIN`,
`API_DOMAIN`, and `WIDGET_DOMAIN` on first start. If DNS is not yet
propagated, certificate issuance fails and Caddy retries with backoff - fix
DNS and it will recover without a restart.

Verify:

```bash
curl -s https://<API_DOMAIN>/health/live
curl -s https://<API_DOMAIN>/health/ready
curl -s https://<WEB_DOMAIN>/ -o /dev/null -w '%{http_code}\n'
curl -s https://<WIDGET_DOMAIN>/embed/index.html -o /dev/null -w '%{http_code}\n'

# or, once URLs are known:
node scripts/vps-smoke.mjs --base-url https://<WEB_DOMAIN> --api-url https://<API_DOMAIN> --widget-url https://<WIDGET_DOMAIN>
```

## 4. Redeploying (new code / new image)

```bash
git pull
docker compose -f docker-compose.prod.yml --env-file .env.production build
docker compose -f docker-compose.prod.yml --env-file .env.production up migrate   # runs Alembic to head; idempotent, safe to re-run
docker compose -f docker-compose.prod.yml --env-file .env.production up -d --no-deps api web widget-assets caddy
```

`migrate` always runs before `api` (via `depends_on: condition:
service_completed_successfully`), so a plain `up -d` also re-applies
migrations safely - the explicit step above is for visibility, not
correctness.

If a deploy needs to be reversed, see
[Rollback_Runbook.md](./Rollback_Runbook.md) before running anything
destructive.

## 5. What's intentionally out of scope for this compose file

- **Horizontal scaling / Kubernetes** - a single VPS runs one instance of
  each service. The API is stateless aside from Redis/Postgres, so scaling
  out later is possible but is an Azure Container Apps concern today, not a
  Compose concern.
- **A dedicated background worker** - the audit found no
  Celery/RQ/APScheduler process; all AI/RAG/embedding work happens inline in
  request handlers, and the evaluation pipeline (`app/operations/eval_*.py`)
  is a set of one-shot CLIs, not a long-running service. Nothing here needs a
  worker container.
- **Object storage for uploads** - documents are stored on the local
  filesystem (`LOCAL_UPLOAD_ROOT`, default `./local_uploads` inside the
  container) via `app/services/local_storage.py`. `docker-compose.prod.yml`
  mounts this to the `uploads_data` named volume so it survives container
  recreation. This is fine for early-access scale on a single VPS; moving to
  object storage is a future scaling item, not a launch blocker.

## 6. Known limitations carried into this deployment (see full audit report for detail)

- CORS for the authenticated web app supports exactly one origin
  (`WEB_ORIGIN`) - fine for a single web domain, not a multi-origin allowlist.
- Auth-endpoint rate limiting (`/register`, `/login`, `/forgot-password`) is
  in-memory per-process (`app/auth/rate_limit.py`) - correct for the single
  `uvicorn` process this compose file runs, but would need to move to the
  Redis-backed limiter before running more than one API replica.
- No CSRF token mechanism; reliance is on `SameSite=Lax` cookies + the
  single-origin CORS restriction. Acceptable for launch, tracked as a
  hardening item.
- `requirements.txt` is fully unpinned. Every `docker compose build` installs
  whatever the latest compatible versions are at build time - reproducible
  within a single build, not across rebuilds weeks apart. Pin versions before
  scaling past early access.
