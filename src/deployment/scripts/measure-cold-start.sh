#!/bin/sh
# measure-cold-start.sh — one cold-start sample of the DT stack. Runs ON
# the ARM VM from src/deployment/ (audit 2026-08-08 section 9.6: external
# conditions must produce operator timings the single analysis script can
# ingest — claim C04/C15).
#
# Measurement contract (deployment README "Cold-start timing hooks"):
#   - teardown first: `docker compose ... down -v` — a cold start begins
#     with no running containers and no volumes (twins and broker queue
#     deleted; required before each repetition);
#   - t0: the invocation of `docker compose ... up -d`;
#   - t1: the FIRST `200` from `GET http://127.0.0.1:8000/ready`, polled at
#     1 Hz — the controller only reports ready when MQTT is connected AND
#     Ditto answers (CONTRACTS 5), so this bounds the whole stack;
#   - duration_s = t1 - t0 in whole seconds (VM wall clock, single host,
#     both stamps from the same clock).
#
# Writes/updates a timings.json in the operator format the harness ingests:
#   {"run_id": "...", "condition": "cold_start",
#    "samples": [{"label": "...", "started_utc": "...",
#                 "ended_utc": "...", "duration_s": N}],
#    "method": "...", "notes": "..."}
#
# One invocation = one sample = one plan repetition (cold_start-r01..r10).
# Fetch the file to the harness host and ingest it:
#   scp vm:/opt/egw/timings-cold_start-r01.json .
#   python -m egw_experiments run --run-id cold_start-r01 \
#       --external-timings timings-cold_start-r01.json \
#       [--sut-env-from sut_environment.json]
#
# Usage (ON the VM, from src/deployment/):
#   sh scripts/measure-cold-start.sh <run_id> <output-timings.json> [label]
#
# Exit codes: 0 = sample written; 1 = readiness timeout or compose failure
# (NO timings are written on failure — never fabricate a measurement).
#
# POSIX sh; needs docker compose and curl.

set -u

READY_URL="http://127.0.0.1:8000/ready"
READY_TIMEOUT_S=600

[ $# -ge 2 ] || {
    echo "usage: $0 <run_id> <output-timings.json> [label]" >&2
    exit 2
}
RUN_ID=$1
OUT=$2
LABEL=${3:-$RUN_ID}

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
DEPLOY_DIR=$(CDPATH= cd -- "$SCRIPT_DIR/.." && pwd)
cd "$DEPLOY_DIR" || exit 1

COMPOSE="docker compose --env-file .env --env-file images.lock.env"

echo "[cold-start] teardown (down -v: full reset, per deployment README)" >&2
$COMPOSE down -v >&2 || {
    echo "[cold-start] error: compose down -v failed" >&2
    exit 1
}

started_utc=$(date -u +%Y-%m-%dT%H:%M:%SZ)
t0=$(date +%s)
echo "[cold-start] t0=$started_utc: compose up -d" >&2
$COMPOSE up -d >&2 || {
    echo "[cold-start] error: compose up failed; no timing written" >&2
    exit 1
}

# Poll /ready at 1 Hz until the first 200 (t1) or timeout.
while :; do
    code=$(curl -s -o /dev/null -w '%{http_code}' --max-time 2 "$READY_URL" 2>/dev/null)
    if [ "$code" = "200" ]; then
        break
    fi
    now=$(date +%s)
    if [ $((now - t0)) -ge "$READY_TIMEOUT_S" ]; then
        echo "[cold-start] error: /ready never returned 200 within ${READY_TIMEOUT_S}s; no timing written" >&2
        exit 1
    fi
    sleep 1
done

t1=$(date +%s)
ended_utc=$(date -u +%Y-%m-%dT%H:%M:%SZ)
duration=$((t1 - t0))
echo "[cold-start] t1=$ended_utc: /ready 200 after ${duration}s" >&2

METHOD="docker compose down -v; t0 at 'docker compose up -d' invocation; poll GET ${READY_URL} at 1 Hz; t1 at first HTTP 200; duration_s = t1 - t0 (whole seconds, VM wall clock, single host)"

cat > "$OUT" <<EOF
{
  "run_id": "$RUN_ID",
  "condition": "cold_start",
  "samples": [
    {
      "label": "$LABEL",
      "started_utc": "$started_utc",
      "ended_utc": "$ended_utc",
      "duration_s": $duration
    }
  ],
  "method": "$METHOD",
  "notes": "produced by deployment/scripts/measure-cold-start.sh"
}
EOF

echo "[cold-start] wrote $OUT" >&2
