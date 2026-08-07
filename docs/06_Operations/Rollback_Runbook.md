# Rollback Runbook (VPS deployment)

Two independent things can need rolling back: the **application code/images**,
and the **database schema**. Handle them separately - do not assume rolling
back one automatically rolls back the other.

## 1. Application rollback (code/images) - low risk, do this first

Docker Compose does not version images by default in this setup (each
`build` overwrites the local `chatbotweb-prod-*` image tags), so the
rollback mechanism is git + rebuild, not an image registry swap:

```bash
git log --oneline -10                 # find the last known-good commit
git checkout <known-good-commit>      # or: git revert <bad-commit> for a clean history
docker compose -f docker-compose.prod.yml --env-file .env.production build
docker compose -f docker-compose.prod.yml --env-file .env.production up -d --no-deps api web widget-assets caddy
node scripts/vps-smoke.mjs --base-url https://<WEB_DOMAIN> --api-url https://<API_DOMAIN> --widget-url https://<WIDGET_DOMAIN>
```

This is safe to do repeatedly and does not touch data. If you want image-tag
based rollback instead (faster, no rebuild), tag images explicitly at deploy
time (`docker tag chatbotweb-prod-api:latest chatbotweb-prod-api:<git-sha>`)
before each `up` and keep the last few tags around - not done by default here
to keep the compose file simple, but straightforward to add once you have a
release cadence that benefits from it.

## 2. Database rollback - higher risk, confirm before running

Two scenarios:

**A. The new code's migration hasn't run yet / just ran and needs reverting**
(no new data has been written under the new schema):

```bash
docker compose -f docker-compose.prod.yml --env-file .env.production run --rm migrate \
  python -m app.operations.database_migration
# Alembic supports downgrading to a specific revision:
docker compose -f docker-compose.prod.yml --env-file .env.production run --rm migrate \
  python -c "from app.operations.database_migration import _config; from alembic import command; command.downgrade(_config(), '<previous-revision-id>')"
```

Find `<previous-revision-id>` from `apps/api/alembic/versions/` (filenames
are prefixed with the revision id) or `alembic history` inside the
container. Alembic downgrades are only as safe as each migration's
`downgrade()` implementation - check the specific revision file before
relying on this for anything with a destructive `downgrade()` (e.g. a
migration that drops a column).

**B. Data has already been written under the new schema and a downgrade
would lose it** - do not run an Alembic downgrade. Instead:

```bash
# Restore the pre-deploy backup taken before this deploy started:
./deployment/backup/restore.sh --db backups/postgres/conversa-<pre-deploy-timestamp>.sql.gz
```

This is why [Backup_and_Restore_Runbook.md](./Backup_and_Restore_Runbook.md)'s
advice to take a manual backup immediately before any deploy that includes a
migration matters - `./deployment/backup/backup.sh` right before
`docker compose ... up migrate` gives you a known-good restore point with
minimal extra effort.

## 3. Decision guide

| Situation | Action |
|---|---|
| Bad code, same DB schema | App rollback only (§1) |
| Bad code + new migration, no real user data written since | App rollback (§1) + Alembic downgrade (§2A) |
| Bad code + new migration, real user data written since | App rollback (§1) + restore from pre-deploy backup (§2B) - accept loss of anything written between the deploy and the restore point, or reconcile it manually from the backup diff if that matters |
| Widget/SDK release only, API/web unaffected | Rebuild just `widget-assets` + restart `caddy`: `docker compose -f docker-compose.prod.yml --env-file .env.production up -d --build widget-assets && docker compose -f docker-compose.prod.yml --env-file .env.production restart caddy` |

## 4. After any rollback

- Run `node scripts/vps-smoke.mjs ...` to confirm the app is actually serving correctly again.
- Run `./deployment/monitoring/check.sh` to confirm container/DB/Redis health.
- If the rollback was due to a quality regression, run `npm run vps:release:gate` before attempting the fixed forward-deploy again.
