#!/bin/sh
# probe_recorder.sh - 1 s recorder of the probe broker's memory cgroup (guest side).
#
# Part of the broker-hold measurement (ADR 0011, condition C3; package D, gate
# item 1, section 7). It runs on the gateway guest under BusyBox ash, as root
# (sudo systemd-run), for the length of the measurement, and writes one CSV
# row per second for the container named on the command line:
#
#   ts_utc,epoch,mem_current,mem_max,mem_peak,anon,file,active_file,inactive_file,
#   ev_max,ev_oom,ev_oom_kill,db_bytes,state,restarts
#
# mem_* and *_file come from the container's cgroup v2 files (memory.current,
# memory.max, memory.peak when the kernel offers it, memory.stat); ev_* from
# memory.events (max, oom, oom_kill); db_bytes is the size of mosquitto.db in
# the probe's own named volume (the persistence store, written at every
# autosave); state and restarts come from 'docker inspect', read every
# INSPECT_EVERY samples because inspect is slow under TCG. A value that could
# not be read is written as '?' - never as 0.
#
# Usage: probe_recorder.sh CONTAINER OUT_CSV VOLUME [INTERVAL_S] [INSPECT_EVERY]
# Exit: 2 when the container or its cgroup cannot be found at start; 0 when
# stopped by SIGTERM (systemctl stop), after writing the closing '# stop' line.
#
# BusyBox: no 'date %N', no EPOCHREALTIME; 'date +%s', 'stat -c %s', 'awk',
# 'sleep' with a whole number of seconds. Nothing here is a bashism.
set -u

CONTAINER=${1:?container name}
OUT=${2:?output csv}
VOLUME=${3:?volume name}
INTERVAL=${4:-1}
INSPECT_EVERY=${5:-10}
CGROUP_ROOT=${PROBE_CGROUP_ROOT:-/sys/fs/cgroup}
DOCKER_ROOT=${PROBE_DOCKER_ROOT:-/var/lib/docker}

samples=0
stopped=0
trap 'stopped=1' TERM INT

# firstfield FILE: the first field of a one-line file, or '?'.
firstfield() {
    [ -r "$1" ] || { echo '?'; return 0; }
    read -r _v _rest < "$1" || { echo '?'; return 0; }
    [ -n "$_v" ] && echo "$_v" || echo '?'
}

# statfield FILE KEY: the value of KEY in a 'key value' file, or '?'.
statfield() {
    [ -r "$1" ] || { echo '?'; return 0; }
    _out=$(awk -v k="$2" '$1 == k { print $2; found = 1; exit } END { if (!found) print "?" }' "$1" 2> /dev/null) || _out='?'
    [ -n "$_out" ] && echo "$_out" || echo '?'
}

ID=$(docker inspect -f '{{.Id}}' "$CONTAINER" 2> /dev/null) || ID=
[ -n "$ID" ] || { echo "STOP: container $CONTAINER not found" >&2; exit 2; }
CG=
for d in "$CGROUP_ROOT/system.slice/docker-$ID.scope" "$CGROUP_ROOT/docker/$ID"; do
    [ -f "$d/memory.current" ] && { CG=$d; break; }
done
[ -n "$CG" ] || { echo "STOP: no memory cgroup found for $CONTAINER ($ID)" >&2; exit 2; }
DB="$DOCKER_ROOT/volumes/$VOLUME/_data/mosquitto.db"

{
    echo "# probe_recorder container=$CONTAINER id=$ID cgroup=$CG volume=$VOLUME interval=$INTERVAL start=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
    echo "ts_utc,epoch,mem_current,mem_max,mem_peak,anon,file,active_file,inactive_file,ev_max,ev_oom,ev_oom_kill,db_bytes,state,restarts"
} > "$OUT" || { echo "STOP: cannot write $OUT" >&2; exit 2; }

state='?'
restarts='?'
while [ "$stopped" -eq 0 ]; do
    if [ $((samples % INSPECT_EVERY)) -eq 0 ]; then
        _ins=$(docker inspect -f '{{.State.Status}} {{.RestartCount}}' "$CONTAINER" 2> /dev/null) || _ins=
        if [ -n "$_ins" ]; then
            state=${_ins%% *}
            restarts=${_ins#* }
        else
            state='?'
            restarts='?'
        fi
    fi
    ts=$(date -u +%Y-%m-%dT%H:%M:%SZ) || ts='?'
    ep=$(date +%s) || ep='?'
    cur=$(firstfield "$CG/memory.current")
    mx=$(firstfield "$CG/memory.max")
    pk=$(firstfield "$CG/memory.peak")
    anon=$(statfield "$CG/memory.stat" anon)
    file=$(statfield "$CG/memory.stat" file)
    af=$(statfield "$CG/memory.stat" active_file)
    inf=$(statfield "$CG/memory.stat" inactive_file)
    evmax=$(statfield "$CG/memory.events" max)
    evoom=$(statfield "$CG/memory.events" oom)
    evkill=$(statfield "$CG/memory.events" oom_kill)
    # 'wc -c' rather than 'stat', and the shell's own word splitting rather
    # than 'tr': every applet used here is one the image's busybox offers
    # (tools/test/make-busybox-wrappers.sh lists them).
    if [ -f "$DB" ]; then
        if db=$(wc -c < "$DB" 2> /dev/null); then
            set -- $db
            db=${1:-?}
        else
            db='?'
        fi
    else
        db=0
    fi
    # A stop that arrived while this sample was being taken interrupted one
    # of its reads (the C3 attempt of 2026-09-23 ended with a 'docker inspect'
    # cut short by the stop, and a row of '?'): a sample the stop interrupted
    # is not an observation and is not written.
    [ "$stopped" -eq 0 ] || break
    echo "$ts,$ep,$cur,$mx,$pk,$anon,$file,$af,$inf,$evmax,$evoom,$evkill,$db,$state,$restarts" >> "$OUT"
    samples=$((samples + 1))
    sleep "$INTERVAL" &
    wait $! 2> /dev/null
done
echo "# stop samples=$samples end=$(date -u +%Y-%m-%dT%H:%M:%SZ)" >> "$OUT"
exit 0
