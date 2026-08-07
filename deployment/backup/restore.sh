#!/usr/bin/env bash
# Restores a Postgres dump and/or uploaded-document archive produced by
# deployment/backup/backup.sh.
#
# THIS SCRIPT OVERWRITES THE TARGET DATABASE/VOLUME. Only run it against a
# throwaway/staging environment unless you are deliberately performing a
# disaster-recovery restore, and always confirm the environment first.
#
# Usage:
#   ./deployment/backup/restore.sh --db backups/postgres/conversa-<ts>.sql.gz \
#       [--uploads backups/uploads/uploads-<ts>.tar.gz] [--yes]
#
# Env overrides: COMPOSE_FILE, COMPOSE_ENV_FILE (same defaults as backup.sh).

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$REPO_ROOT"

COMPOSE_FILE="${COMPOSE_FILE:-docker-compose.prod.yml}"
COMPOSE_ENV_FILE="${COMPOSE_ENV_FILE:-.env.production}"

DB_DUMP=""
UPLOADS_ARCHIVE=""
CONFIRMED=0

while [ $# -gt 0 ]; do
	case "$1" in
	--db) DB_DUMP="$2"; shift 2 ;;
	--uploads) UPLOADS_ARCHIVE="$2"; shift 2 ;;
	--yes) CONFIRMED=1; shift ;;
	*) echo "Unknown argument: $1" >&2; exit 2 ;;
	esac
done

if [ -z "$DB_DUMP" ] && [ -z "$UPLOADS_ARCHIVE" ]; then
	echo "Usage: $0 --db <path-to-dump.sql.gz> [--uploads <path-to-archive.tar.gz>] [--yes]" >&2
	exit 2
fi

compose() {
	docker compose -f "$COMPOSE_FILE" --env-file "$COMPOSE_ENV_FILE" "$@"
}

if [ "$CONFIRMED" -ne 1 ]; then
	echo "This will OVERWRITE the current database/uploads targeted by $COMPOSE_FILE / $COMPOSE_ENV_FILE."
	read -r -p "Type 'restore' to continue: " reply
	if [ "$reply" != "restore" ]; then
		echo "Aborted."
		exit 1
	fi
fi

if [ -n "$DB_DUMP" ]; then
	if [ ! -f "$DB_DUMP" ]; then
		echo "[restore] FAILED: dump file not found: $DB_DUMP" >&2
		exit 1
	fi
	POSTGRES_USER_VALUE="$(grep -E '^POSTGRES_USER=' "$COMPOSE_ENV_FILE" | tail -n1 | cut -d= -f2-)"
	POSTGRES_DB_VALUE="$(grep -E '^POSTGRES_DB=' "$COMPOSE_ENV_FILE" | tail -n1 | cut -d= -f2-)"
	echo "[restore] restoring $DB_DUMP into database '$POSTGRES_DB_VALUE'"
	compose exec -T postgres psql -U "$POSTGRES_USER_VALUE" -d "$POSTGRES_DB_VALUE" -c \
		"SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = '$POSTGRES_DB_VALUE' AND pid <> pg_backend_pid();" >/dev/null || true
	compose exec -T postgres dropdb -U "$POSTGRES_USER_VALUE" --if-exists "$POSTGRES_DB_VALUE"
	compose exec -T postgres createdb -U "$POSTGRES_USER_VALUE" "$POSTGRES_DB_VALUE"
	if ! gunzip -c "$DB_DUMP" | compose exec -T postgres psql -U "$POSTGRES_USER_VALUE" -d "$POSTGRES_DB_VALUE" -v ON_ERROR_STOP=1; then
		echo "[restore] FAILED: database restore did not complete successfully" >&2
		exit 1
	fi
	echo "[restore] database restore complete"
fi

if [ -n "$UPLOADS_ARCHIVE" ]; then
	if [ ! -f "$UPLOADS_ARCHIVE" ]; then
		echo "[restore] FAILED: uploads archive not found: $UPLOADS_ARCHIVE" >&2
		exit 1
	fi
	UPLOADS_VOLUME="chatbotweb-prod_uploads_data"
	if ! docker volume inspect "$UPLOADS_VOLUME" >/dev/null 2>&1; then
		UPLOADS_VOLUME="$(docker volume ls --format '{{.Name}}' | grep -E 'uploads_data$' | head -n1)"
	fi
	if [ -z "$UPLOADS_VOLUME" ]; then
		echo "[restore] FAILED: could not find the uploads_data volume" >&2
		exit 1
	fi
	echo "[restore] restoring $UPLOADS_ARCHIVE into volume $UPLOADS_VOLUME"
	if ! docker run --rm \
		-v "$UPLOADS_VOLUME:/data" \
		-v "$(cd "$(dirname "$UPLOADS_ARCHIVE")" && pwd):/backup:ro" \
		alpine:3.20 \
		sh -c "rm -rf /data/* && tar xzf /backup/$(basename "$UPLOADS_ARCHIVE") -C /data"; then
		echo "[restore] FAILED: uploads volume restore did not complete successfully" >&2
		exit 1
	fi
	echo "[restore] uploads restore complete"
fi

echo "[restore] done. Validate with: docker compose -f $COMPOSE_FILE --env-file $COMPOSE_ENV_FILE exec api python -m app.operations.database_migration preflight"
