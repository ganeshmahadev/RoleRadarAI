#!/usr/bin/env bash
# Daily discovery run (PRD §84, BACKLOG P14-008): start the stack and OpenJev, run one
# "scheduled" discovery (search → import → score within the configured budget), then stop
# OpenJev again to free ~15 GB of memory. Safe to run by hand.
#
#   scripts/daily-discovery.sh            # full run
#   DRY_RUN=1 scripts/daily-discovery.sh  # only check that the stack and settings are ready
#
# Log: ~/Library/Logs/roleradar-discovery.log
set -euo pipefail

REPO="$(cd "$(dirname "$0")/.." && pwd)"
API="${ROLERADAR_API:-http://localhost:8000/api/v1}"
OPENJEV_DIR="${OPENJEV_DIR:-$HOME/models/openjev}"
OPENJEV_URL="${OPENJEV_URL:-http://127.0.0.1:4100}"
MAX_MINUTES="${MAX_MINUTES:-70}"   # hard stop; the run's own budget is set on /discover
LOG="${LOG:-$HOME/Library/Logs/roleradar-discovery.log}"
export PATH="/Applications/Docker.app/Contents/Resources/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"

mkdir -p "$(dirname "$LOG")"
exec >>"$LOG" 2>&1
log() { echo "$(date '+%Y-%m-%d %H:%M:%S') $*"; }
wait_for() { # url seconds
  local i
  for ((i = 0; i < $2; i += 5)); do
    curl -fsS -m 5 "$1" >/dev/null 2>&1 && return 0
    sleep 5
  done
  return 1
}

STARTED_OPENJEV=0
cleanup() {
  if [ "$STARTED_OPENJEV" = 1 ]; then
    log "stopping OpenJev"
    "$OPENJEV_DIR/stop-openjev.sh" || true
  fi
  log "done"
}
trap cleanup EXIT

log "=== daily discovery (dry run: ${DRY_RUN:-0}) ==="

if ! docker info >/dev/null 2>&1; then
  log "starting Docker Desktop"
  open -ga Docker
  for _ in $(seq 1 36); do docker info >/dev/null 2>&1 && break; sleep 5; done
fi
docker compose --project-directory "$REPO" up -d
wait_for "$API/health" 180 || { log "API did not become healthy"; exit 1; }

settings="$(curl -fsS "$API/discovery/settings")"
log "settings: $(echo "$settings" | jq -c '{terms: .effective_terms, sites, jobspy_enabled, eures: (.eures_enabled and .eures_available), total_budget_minutes}')"
if [ "$(echo "$settings" | jq '.effective_terms | length')" = 0 ]; then
  log "no search terms (set them on /discover or as target roles in the profile)"; exit 1
fi
if [ "${DRY_RUN:-0}" = 1 ]; then log "dry run: stack ready, not starting a run"; exit 0; fi

if ! curl -fsS -m 5 "$OPENJEV_URL/v1/version" >/dev/null 2>&1; then
  log "starting OpenJev"
  "$OPENJEV_DIR/start-openjev.sh"
  STARTED_OPENJEV=1
  wait_for "$OPENJEV_URL/v1/version" 600 || log "OpenJev not ready; jobs will be imported but not scored"
fi

response="$(curl -sS -w '\n%{http_code}' -X POST "$API/discovery-runs" \
  -H 'Content-Type: application/json' -d '{"trigger":"scheduled"}')"
code="$(echo "$response" | tail -n1)"
body="$(echo "$response" | sed '$d')"
if [ "$code" != 202 ]; then log "could not start ($code): $body"; exit 1; fi
run_id="$(echo "$body" | jq -r .id)"
log "run $run_id started"

deadline=$(($(date +%s) + MAX_MINUTES * 60))
while :; do
  sleep 60
  run="$(curl -fsS "$API/discovery-runs/$run_id" || echo '{}')"
  status="$(echo "$run" | jq -r '.status // "UNKNOWN"')"
  case "$status" in
    DONE | CANCELLED | FAILED) break ;;
  esac
  if [ "$(date +%s)" -ge "$deadline" ]; then
    log "hard time limit reached; cancelling"
    curl -fsS -X POST "$API/discovery-runs/$run_id/cancel" >/dev/null || true
    sleep 30
    run="$(curl -fsS "$API/discovery-runs/$run_id" || echo '{}')"
    break
  fi
done

log "result: $(echo "$run" | jq -c '{status, phase, error_message,
  sources: [.sources[]? | {source, term, status, found, created, message}],
  scored: (.scoring.counts.DONE // 0), new_jobs: (.new_jobs | length)}')"
