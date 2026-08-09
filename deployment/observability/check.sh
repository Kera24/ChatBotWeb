#!/usr/bin/env bash
# Health/readiness check for the optional "recommended tier" observability
# stack (docker-compose.observability.yml) - OTel Collector, Prometheus,
# Tempo, Loki, Grafana. Mirrors deployment/monitoring/check.sh's structure
# (container health + one readiness endpoint per service), kept as a
# separate script rather than folded into that one since this stack is
# entirely optional and not part of the minimum-tier production checklist -
# see docs/06_Operations/Grafana_Prometheus_Loki_Tempo_VPS_Guide.md.
#
# Exit code 0 = healthy, 1 = one or more checks failed. Prints one line per
# check so failures are greppable in cron mail / systemd journal.
#
# Usage: ./deployment/observability/check.sh [--json]

set -uo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$REPO_ROOT"

PROD_COMPOSE_FILE="${PROD_COMPOSE_FILE:-docker-compose.prod.yml}"
OBSERVABILITY_COMPOSE_FILE="${OBSERVABILITY_COMPOSE_FILE:-docker-compose.observability.yml}"
COMPOSE_ENV_FILE="${COMPOSE_ENV_FILE:-.env.production}"
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
	docker compose -f "$PROD_COMPOSE_FILE" -f "$OBSERVABILITY_COMPOSE_FILE" --env-file "$COMPOSE_ENV_FILE" "$@"
}

# --- Container health -------------------------------------------------------
UNHEALTHY="$(compose ps otel-collector prometheus tempo loki grafana --format '{{.Name}} {{.Health}}' 2>/dev/null | awk '$2 != "" && $2 != "healthy" {print $1}')"
if [ -z "$UNHEALTHY" ]; then
	record "containers" "ok" "otel-collector/prometheus/tempo/loki/grafana all reporting healthy (or have no healthcheck defined)"
else
	record "containers" "fail" "unhealthy: $(echo "$UNHEALTHY" | tr '\n' ',')"
fi

# --- OTel Collector readiness (health_check extension, port 13133) ---------
COLLECTOR_STATUS="$(compose exec -T otel-collector wget -qO- http://localhost:13133/ 2>/dev/null)"
if [ -n "$COLLECTOR_STATUS" ]; then
	record "otel_collector_ready" "ok" "$COLLECTOR_STATUS"
else
	record "otel_collector_ready" "fail" "no response from health_check extension on :13133"
fi

# --- Prometheus readiness ---------------------------------------------------
PROMETHEUS_STATUS="$(compose exec -T prometheus wget -qO- http://localhost:9090/-/healthy 2>/dev/null)"
if [ -n "$PROMETHEUS_STATUS" ]; then
	record "prometheus_ready" "ok" "$PROMETHEUS_STATUS"
else
	record "prometheus_ready" "fail" "no response from /-/healthy"
fi

# --- Tempo readiness ---------------------------------------------------------
TEMPO_STATUS="$(compose exec -T tempo wget -qO- http://localhost:3200/ready 2>/dev/null)"
if [ -n "$TEMPO_STATUS" ]; then
	record "tempo_ready" "ok" "$TEMPO_STATUS"
else
	record "tempo_ready" "fail" "no response from /ready"
fi

# --- Loki readiness -----------------------------------------------------------
LOKI_STATUS="$(compose exec -T loki wget -qO- http://localhost:3100/ready 2>/dev/null)"
if [ -n "$LOKI_STATUS" ]; then
	record "loki_ready" "ok" "$LOKI_STATUS"
else
	record "loki_ready" "fail" "no response from /ready"
fi

# --- Grafana readiness ---------------------------------------------------------
GRAFANA_STATUS="$(compose exec -T grafana wget -qO- http://localhost:3000/api/health 2>/dev/null)"
if echo "$GRAFANA_STATUS" | grep -q '"database"'; then
	record "grafana_ready" "ok" "$GRAFANA_STATUS"
else
	record "grafana_ready" "fail" "${GRAFANA_STATUS:-no response from /api/health}"
fi

# --- Output -------------------------------------------------------------------
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
