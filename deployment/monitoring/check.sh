#!/usr/bin/env bash
# Low-cost operational health check for the single-VPS deployment.
# Designed to be run from cron/systemd-timer every few minutes and/or hit by
# an external uptime monitor (see docs/06_Operations/Monitoring_Runbook.md).
#
# Exit code 0 = healthy, 1 = one or more checks failed. Prints one line per
# check so failures are greppable in cron mail / systemd journal / any
# log-shipping agent.
#
# Usage: ./deployment/monitoring/check.sh [--json]

set -uo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$REPO_ROOT"

COMPOSE_FILE="${COMPOSE_FILE:-docker-compose.prod.yml}"
COMPOSE_ENV_FILE="${COMPOSE_ENV_FILE:-.env.production}"
BACKUP_DIR="${BACKUP_DIR:-$REPO_ROOT/backups}"
DISK_WARN_MB="${DISK_WARN_MB:-2048}"
JSON_OUTPUT=0
[ "${1:-}" = "--json" ] && JSON_OUTPUT=1

FAILED=0
RESULTS=()

record() {
	local name="$1" status="$2" detail="$3"
	RESULTS+=("$name|$status|$detail")
	if [ "$status" != "ok" ]; then FAILED=1; fi
}

compose() {
	docker compose -f "$COMPOSE_FILE" --env-file "$COMPOSE_ENV_FILE" "$@"
}

# --- Container health ---------------------------------------------------
UNHEALTHY="$(compose ps --format '{{.Name}} {{.Health}}' 2>/dev/null | awk '$2 != "" && $2 != "healthy" {print $1}')"
if [ -z "$UNHEALTHY" ]; then
	record "containers" "ok" "all containers reporting healthy"
else
	record "containers" "fail" "unhealthy: $(echo "$UNHEALTHY" | tr '\n' ',')"
fi

# --- API readiness (includes database/embedding-provider/redis checks) ---
API_READY_JSON="$(compose exec -T api python -c "
import urllib.request
print(urllib.request.urlopen('http://localhost:8000/health/ready', timeout=5).read().decode())
" 2>/dev/null)"
if echo "$API_READY_JSON" | grep -q '"status": *"ready"' || echo "$API_READY_JSON" | grep -q '"status":"ready"'; then
	record "api_ready" "ok" "$API_READY_JSON"
else
	record "api_ready" "fail" "${API_READY_JSON:-no response}"
fi

# --- Disk space -----------------------------------------------------------
AVAILABLE_KB="$(df -Pk "$REPO_ROOT" | tail -n1 | awk '{print $4}')"
AVAILABLE_MB=$((AVAILABLE_KB / 1024))
if [ "$AVAILABLE_MB" -ge "$DISK_WARN_MB" ]; then
	record "disk_space" "ok" "${AVAILABLE_MB}MB free"
else
	record "disk_space" "fail" "${AVAILABLE_MB}MB free (below ${DISK_WARN_MB}MB threshold)"
fi

# --- Last backup freshness (warn if no successful backup in >26h) --------
if [ -d "$BACKUP_DIR/postgres" ]; then
	LATEST="$(find "$BACKUP_DIR/postgres" -name '*.sql.gz' -mmin -1560 2>/dev/null | head -n1)"
	if [ -n "$LATEST" ]; then
		record "backup_freshness" "ok" "recent backup found: $(basename "$LATEST")"
	else
		record "backup_freshness" "fail" "no postgres backup younger than 26h in $BACKUP_DIR/postgres"
	fi
else
	record "backup_freshness" "fail" "$BACKUP_DIR/postgres does not exist - backups have never run"
fi

# --- Output ---------------------------------------------------------------
if [ "$JSON_OUTPUT" -eq 1 ]; then
	printf '{"generated_at":"%s","checks":[' "$(date -u +%FT%TZ)"
	first=1
	for r in "${RESULTS[@]}"; do
		IFS='|' read -r name status detail <<<"$r"
		[ "$first" -eq 0 ] && printf ','
		printf '{"name":"%s","status":"%s","detail":%s}' "$name" "$status" "$(printf '%s' "$detail" | python3 -c 'import json,sys; print(json.dumps(sys.stdin.read()))' 2>/dev/null || echo '""')"
		first=0
	done
	printf ']}\n'
else
	for r in "${RESULTS[@]}"; do
		IFS='|' read -r name status detail <<<"$r"
		echo "[$status] $name: $detail"
	done
fi

exit $FAILED
