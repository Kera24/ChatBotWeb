#!/usr/bin/env bash
# Backs up the Postgres database and the uploaded-document volume for the
# single-VPS Conversa deployment (docker-compose.prod.yml).
#
# Usage (run on the VPS host, from the repository root):
#   ./deployment/backup/backup.sh
#
# Env overrides:
#   BACKUP_DIR       host directory to write backups to (default ./backups)
#   RETENTION_DAYS   delete local backups older than this many days (default 14)
#   COMPOSE_FILE      compose file to target (default docker-compose.prod.yml)
#   COMPOSE_ENV_FILE  env file to pass to compose (default .env.production)
#
# Exit code is non-zero if either the database or upload-volume backup fails,
# so this script is safe to wire directly into cron/systemd failure alerting
# (see docs/06_Operations/Monitoring_Runbook.md).

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$REPO_ROOT"

BACKUP_DIR="${BACKUP_DIR:-$REPO_ROOT/backups}"
RETENTION_DAYS="${RETENTION_DAYS:-14}"
DISK_WARN_MB="${DISK_WARN_MB:-2048}"
COMPOSE_FILE="${COMPOSE_FILE:-docker-compose.prod.yml}"
COMPOSE_ENV_FILE="${COMPOSE_ENV_FILE:-.env.production}"
TIMESTAMP="$(date -u +%Y%m%dT%H%M%SZ)"

compose() {
	docker compose -f "$COMPOSE_FILE" --env-file "$COMPOSE_ENV_FILE" "$@"
}

mkdir -p "$BACKUP_DIR/postgres" "$BACKUP_DIR/uploads"

echo "[backup] $(date -u +%FT%TZ) starting backup run"

# --- Postgres dump -----------------------------------------------------------
DB_DUMP_FILE="$BACKUP_DIR/postgres/conversa-${TIMESTAMP}.sql.gz"
POSTGRES_USER_VALUE="$(grep -E '^POSTGRES_USER=' "$COMPOSE_ENV_FILE" | tail -n1 | cut -d= -f2-)"
POSTGRES_DB_VALUE="$(grep -E '^POSTGRES_DB=' "$COMPOSE_ENV_FILE" | tail -n1 | cut -d= -f2-)"

if [ -z "$POSTGRES_USER_VALUE" ] || [ -z "$POSTGRES_DB_VALUE" ]; then
	echo "[backup] FAILED: could not read POSTGRES_USER/POSTGRES_DB from $COMPOSE_ENV_FILE" >&2
	exit 1
fi

if ! compose exec -T postgres pg_dump -U "$POSTGRES_USER_VALUE" -d "$POSTGRES_DB_VALUE" --format=plain \
	| gzip -9 > "$DB_DUMP_FILE.partial"; then
	echo "[backup] FAILED: pg_dump did not complete successfully" >&2
	rm -f "$DB_DUMP_FILE.partial"
	exit 1
fi
mv "$DB_DUMP_FILE.partial" "$DB_DUMP_FILE"
echo "[backup] database dump written to $DB_DUMP_FILE ($(du -h "$DB_DUMP_FILE" | cut -f1))"

# --- Uploaded document volume -------------------------------------------------
UPLOADS_ARCHIVE="$BACKUP_DIR/uploads/uploads-${TIMESTAMP}.tar.gz"
# docker-compose.prod.yml sets an explicit project `name: chatbotweb-prod`, so
# Compose always names this volume "chatbotweb-prod_uploads_data" regardless
# of which directory it is run from. Fall back to a suffix lookup only if
# that project name is ever changed.
UPLOADS_VOLUME="chatbotweb-prod_uploads_data"
if ! docker volume inspect "$UPLOADS_VOLUME" >/dev/null 2>&1; then
	UPLOADS_VOLUME="$(docker volume ls --format '{{.Name}}' | grep -E 'uploads_data$' | head -n1)"
fi
if [ -z "$UPLOADS_VOLUME" ]; then
	echo "[backup] FAILED: could not find the uploads_data volume" >&2
	exit 1
fi

if ! docker run --rm \
	-v "$UPLOADS_VOLUME:/data:ro" \
	-v "$BACKUP_DIR/uploads:/backup" \
	alpine:3.20 \
	tar czf "/backup/uploads-${TIMESTAMP}.tar.gz.partial" -C /data .; then
	echo "[backup] FAILED: uploads volume archive did not complete successfully" >&2
	rm -f "$BACKUP_DIR/uploads/uploads-${TIMESTAMP}.tar.gz.partial"
	exit 1
fi
mv "$BACKUP_DIR/uploads/uploads-${TIMESTAMP}.tar.gz.partial" "$UPLOADS_ARCHIVE"
echo "[backup] uploads archive written to $UPLOADS_ARCHIVE ($(du -h "$UPLOADS_ARCHIVE" | cut -f1))"

# --- Retention -----------------------------------------------------------
find "$BACKUP_DIR/postgres" -name '*.sql.gz' -mtime "+${RETENTION_DAYS}" -print -delete
find "$BACKUP_DIR/uploads" -name '*.tar.gz' -mtime "+${RETENTION_DAYS}" -print -delete

# --- Disk space warning ----------------------------------------------------
AVAILABLE_KB="$(df -Pk "$BACKUP_DIR" | tail -n1 | awk '{print $4}')"
AVAILABLE_MB=$((AVAILABLE_KB / 1024))
if [ "$AVAILABLE_MB" -lt "$DISK_WARN_MB" ]; then
	echo "[backup] WARNING: less than ${DISK_WARN_MB}MB free at $BACKUP_DIR (${AVAILABLE_MB}MB available)" >&2
fi

echo "[backup] $(date -u +%FT%TZ) backup run complete"
echo "[backup] REMINDER: copy $BACKUP_DIR off this VPS regularly (encrypted, offsite) - a local-disk-only backup does not protect against VPS loss."
