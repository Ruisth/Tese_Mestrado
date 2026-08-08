#!/bin/sh
# collect-resources.sh — 1 Hz SUT container resource collector. Runs ON the
# ARM VM (the system under test), never on the harness host (audit
# 2026-08-08 section 9.1: the harness's local docker-stats sampler measures
# the load-generator host by default — the wrong system for RQ3).
#
# Samples `docker stats --no-stream --format json` once per second and
# appends CSV rows compatible with the harness analysis reader
# (egw_experiments.analyze.read_resources_csv):
#
#   ts_utc,container,cpu_pct,mem_bytes,mem_pct,host
#
# host (work order P1): the hostname of the machine every sample was taken
# on — provenance the harness VERIFIES at ingestion. `run/collect
# --resources-from` rejects the file (and treats SUT resources as missing,
# invalidating the timed run) unless:
#   - the header is exactly the 6 columns above,
#   - it carries at least 30 data rows (MIN_RESOURCE_SAMPLES,
#     egw_experiments/resources.py),
#   - every host value equals the node/hostname recorded in
#     sut_environment.json (when that file provides one).
# So this script MUST run on the SUT VM itself; a CSV produced anywhere
# else will fail the host check by construction.
#
# cpu_pct keeps docker's single-CPU basis (can exceed 100 for
# multi-threaded containers); the harness analysis normalizes it by nproc
# from sut_environment.json (audit 9.7). mem_bytes is the used part of
# MemUsage converted to bytes.
#
# Runs until SIGTERM/SIGINT or until --duration expires.
#
# Usage (ON the VM):
#   sh collect-resources.sh <output.csv> [--duration SECONDS]
#
# Typical remote orchestration from the harness host, around one timed run
# (start before the warm-up, stop after the confirmation window, fetch,
# then ingest with `run/collect --resources-from`):
#
#   # start (backgrounded on the VM; survives the ssh session):
#   ssh vm 'nohup sh /opt/egw/scripts/collect-resources.sh \
#       /tmp/resources-<run_id>.csv --duration 900 \
#       >/tmp/collect-<run_id>.log 2>&1 & echo $!'
#
#   # or as a transient systemd unit (clean SIGTERM on stop):
#   ssh vm 'systemd-run --unit egw-resources-<run_id> --collect \
#       sh /opt/egw/scripts/collect-resources.sh /tmp/resources-<run_id>.csv'
#   ssh vm 'systemctl stop egw-resources-<run_id>'   # after the run
#
#   # fetch and ingest:
#   scp vm:/tmp/resources-<run_id>.csv .
#   python -m egw_experiments run --run-id <run_id> ... \
#       --resources-from resources-<run_id>.csv
#
# Timed runs WITHOUT this collector's output are marked validity 'invalid'
# by the harness (override only with --allow-missing-resources).
#
# POSIX sh + awk; docker must be usable by the invoking user.

set -u

usage() {
    echo "usage: $0 <output.csv> [--duration SECONDS]" >&2
    exit 2
}

[ $# -ge 1 ] || usage
OUT=$1
shift
DURATION=0
while [ $# -gt 0 ]; do
    case "$1" in
        --duration)
            [ $# -ge 2 ] || usage
            DURATION=$2
            shift 2
            ;;
        *) usage ;;
    esac
done
case "$DURATION" in
    *[!0-9]*) usage ;;
esac

command -v docker >/dev/null 2>&1 || {
    echo "error: docker CLI not found" >&2
    exit 1
}

stop=0
trap 'stop=1' TERM INT

# Host provenance (work order P1): recorded on every row and verified by
# the harness against sut_environment.json at ingestion.
HOST=$(hostname 2>/dev/null || uname -n)

# Header only when creating a fresh file (append mode allows restarts) —
# but never append to a file with a different (e.g. pre-host-column)
# header: the ingest validation would reject the mixed schema anyway.
HEADER="ts_utc,container,cpu_pct,mem_bytes,mem_pct,host"
if [ ! -s "$OUT" ]; then
    echo "$HEADER" > "$OUT"
elif [ "$(head -n 1 "$OUT")" != "$HEADER" ]; then
    echo "error: $OUT exists with a different header (old schema?); refusing to append" >&2
    exit 1
fi

started_epoch=$(date +%s)
echo "collecting docker stats at 1 Hz into $OUT (duration: ${DURATION:-0}s, 0 = until SIGTERM)" >&2

# Parse docker's JSON-lines output with awk (no jq on the minimal VM):
# every line is a flat object with "Name":"...", "CPUPerc":"1.23%",
# "MemUsage":"126.4MiB / 7.628GiB", "MemPerc":"1.61%".
AWK_PARSE='
function field(line, name,    re, v) {
    re = "\"" name "\":\"[^\"]*\""
    if (match(line, re) == 0) return ""
    v = substr(line, RSTART, RLENGTH)
    sub("\"" name "\":\"", "", v)
    sub("\"$", "", v)
    return v
}
function pct(s) { sub(/%$/, "", s); return s }
function bytes(s,    n, u, mult) {
    # "126.4MiB / 7.628GiB" -> used part -> bytes (integer)
    sub(/ \/.*$/, "", s)
    sub(/^[ \t]+/, "", s); sub(/[ \t]+$/, "", s)
    n = s; u = s
    sub(/[A-Za-z].*$/, "", n)
    sub(/^[0-9.eE+-]*/, "", u)
    mult = 1
    if      (u == "B")   mult = 1
    else if (u == "kB")  mult = 1000
    else if (u == "KiB") mult = 1024
    else if (u == "MB")  mult = 1000000
    else if (u == "MiB") mult = 1048576
    else if (u == "GB")  mult = 1000000000
    else if (u == "GiB") mult = 1073741824
    else if (u == "TB")  mult = 1000000000000
    else if (u == "TiB") mult = 1099511627776
    else if (u != "")    return ""
    return sprintf("%.0f", n * mult)
}
{
    name = field($0, "Name")
    if (name == "") next
    printf "%s,%s,%s,%s,%s,%s\n", TS, name, pct(field($0, "CPUPerc")), \
        bytes(field($0, "MemUsage")), pct(field($0, "MemPerc")), HOST
}
'

# --format json is JSON-lines on Docker >= 23; older CLIs accept the
# equivalent '{{json .}}' template. The modern form is tried first on
# every sample so a CLI downgrade mid-campaign still degrades gracefully.
while [ "$stop" -eq 0 ]; do
    loop_start=$(date +%s)
    ts=$(date -u +%Y-%m-%dT%H:%M:%SZ)
    lines=$(docker stats --no-stream --format json 2>/dev/null)
    if [ -z "$lines" ]; then
        lines=$(docker stats --no-stream --format '{{json .}}' 2>/dev/null)
    fi
    if [ -n "$lines" ]; then
        printf '%s\n' "$lines" | awk -v TS="$ts" -v HOST="$HOST" "$AWK_PARSE" >> "$OUT"
    fi
    if [ "$DURATION" -gt 0 ]; then
        now=$(date +%s)
        if [ $((now - started_epoch)) -ge "$DURATION" ]; then
            break
        fi
    fi
    # Keep ~1 Hz cadence: docker stats itself takes time to sample.
    loop_end=$(date +%s)
    if [ $((loop_end - loop_start)) -eq 0 ]; then
        sleep 1
    fi
done

echo "collector stopped; output: $OUT" >&2
