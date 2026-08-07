# Initial VPS Capacity Guide

Sizing guidance for the single-VPS Docker Compose deployment
(`docker-compose.prod.yml`). This is a starting point for early access, not a
scaling plan - see [Future_Azure_Migration_Notes.md](./Future_Azure_Migration_Notes.md)
for what comes after a single VPS stops being enough.

## What's running on the box

Seven containers: `caddy`, `web` (Next.js), `api` (FastAPI/uvicorn, single
process, no `--workers`), `postgres` (pgvector), `redis`, plus two one-shot
build/migration jobs (`migrate`, `widget-assets`) that exit after running.
The resource limits already set in `docker-compose.prod.yml`
(`deploy.resources.limits`) sum to a ceiling of about 4.5 vCPU / 3.4GB RAM
across the always-on services - that's a ceiling, not a working-set
requirement; actual usage at early-access traffic is much lower.

## Minimum (early access, single tenant testing, a handful of pilot orgs)

| Resource | Minimum |
|---|---|
| CPU | 2 vCPU |
| RAM | 4GB |
| Disk | 40GB SSD |
| Swap | 2GB |
| OS | Ubuntu 22.04/24.04 LTS or Debian 12 (whatever your Docker Engine install docs target) |
| Expected capacity | A handful of pilot organisations, low concurrent chat volume (single-digit concurrent conversations), document libraries in the tens-of-MB-to-low-GB range |

At this tier, keep the mock/local embedding provider or a lightweight
external provider - a heavyweight local model (e.g. running your own
embedding/generation model on-box) is not what 2 vCPU/4GB is sized for.

## Preferred (comfortable early-access launch, room to grow before re-sizing)

| Resource | Preferred |
|---|---|
| CPU | 4 vCPU |
| RAM | 8GB |
| Disk | 80-120GB SSD (NVMe preferred for Postgres I/O) |
| Swap | 4GB |
| OS | Ubuntu 24.04 LTS |
| Expected capacity | Tens of pilot organisations, moderate concurrent widget + authenticated-chat traffic, document libraries up to a few GB total, headroom for daily backups to run without starving the app of CPU/disk I/O |

## Why swap, given a modern host

Swap here is a safety margin, not a performance strategy: Postgres,
`pg_dump` during backups, and `npm run web:build` (if you ever build on the
same box rather than in CI) can each transiently spike memory. A few GB of
swap turns "OOM-killed container" into "briefly slower," which is the right
trade-off for a single-VPS launch where an unplanned restart is more
disruptive than a scheduling hiccup. Building `web`'s Next.js image
elsewhere and just running the resulting image on the VPS (rather than
building on-box) is the simplest way to keep build-time memory spikes off
the production host - the shipped `docker compose ... build` command builds
locally for simplicity, but nothing prevents building in CI and pushing an
image instead once that infrastructure exists.

## Disk sizing components

- Postgres data volume: starts small (tens of MB with the schema alone); grows with chunk/embedding storage - a 1536-dimension mock embedding is ~6KB/vector before indexing overhead, so document volume (not user count) is the dominant driver once real documents are uploaded.
- `uploads_data` volume: bounded by `MAX_UPLOAD_BYTES` (default 10MB) times however many documents get uploaded - budget generously here since it's the least predictable number.
- `backups_data`/local `backups/` directory: two full Postgres dumps + two upload-volume archives per retention cycle by default (`RETENTION_DAYS=14`, one backup/day) - budget roughly 2x your largest single day's uploads-volume size plus a modest, slow-growing amount for compressed SQL dumps.
- Caddy's `caddy_data` volume: negligible (certificates + ACME state only).
- Docker image layers: budget 5-10GB for the accumulated image history across rebuilds; prune periodically with `docker image prune -f` if disk gets tight.

## When to move off a single VPS

Signs it's time to look at the Azure path (or a bigger/second VPS) rather
than re-tuning this one: sustained CPU near the compose resource-limit
ceiling during normal (non-backup) hours, Postgres disk I/O becoming the
bottleneck for chat latency, or needing more than one API replica for
availability (which also requires moving the in-memory auth rate limiter to
the Redis-backed one first - see the VPS Deployment Guide's "known
limitations" section).
