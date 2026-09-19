#!/bin/sh
# collect-resources.sh — 1 Hz SUT container resource collector. Runs ON the
# ARM VM (the system under test), never on the harness host (audit
# 2026-08-08 section 9.1: the harness's local docker-stats sampler measures
# the load-generator host by default — the wrong system for RQ3).
#
# Appends CSV rows compatible with the harness analysis reader
# (egw_experiments.analyze.read_resources_csv):
#
#   ts_utc,container,cpu_pct,mem_bytes,mem_pct,host
#
# host (work order P1): the hostname of the machine every sample was taken
# on — provenance the harness VERIFIES at ingestion. `run/collect
# --resources-from` (and the harness's --collector-fetch-cmd hook) rejects
# the file — treating SUT resources as missing and invalidating the timed
# run — unless ALL of the following hold
# (egw_experiments.resources.validate_resources_csv):
#   - the header is exactly the 6 columns above,
#   - every data row carries all 6 columns and a non-empty container name,
#   - ts_utc parses as RFC 3339 and never goes back in time,
#   - cpu_pct, mem_bytes and mem_pct are numeric on every row,
#   - it carries at least 30 data rows (MIN_RESOURCE_SAMPLES) AND at least
#     30 DISTINCT ts_utc instants (MIN_DISTINCT_SAMPLE_INSTANTS): one
#     sample writes ONE ROW PER CONTAINER, so 30 rows can be five seconds
#     of six containers — row count alone is not evidence of a sampled run
#     (sprint P5, report 5.4). At the 1 Hz cadence below that means at
#     least ~30 s of continuous collection,
#   - consecutive samples of one container are at most MAX_SAMPLE_GAP_S
#     (5 s) apart, so a sample that costs more than a few seconds
#     invalidates the run even when the instants are numerous enough,
#   - the sampled instants span at least 90% of the run's measured window
#     (RESOURCE_WINDOW_COVERAGE_MIN_FRAC, pending advisor sign-off), which
#     is why the collector must be STARTED BEFORE the warm-up and stopped
#     only AFTER the confirmation window,
#   - every host value equals the node/hostname recorded in
#     sut_environment.json (when that file provides one).
# So this script MUST run on the SUT VM itself; a CSV produced anywhere
# else will fail the host check by construction.
#
# ---------------------------------------------------------------------
# Sampling source (changed 2026-09-19; LOG entry #C034)
# ---------------------------------------------------------------------
# Until 2026-09-19 every sample ran `docker stats --no-stream`. On the
# emulated ARM64 guest (QEMU/TCG) one such call costs 3-5 s idle and about
# 21 s while the stack is working, because the Docker CLI must round-trip
# the daemon and the daemon itself samples every container. The collector
# therefore produced roughly 7 distinct instants in 150 s, far below
# MIN_DISTINCT_SAMPLE_INSTANTS, and every timed run was rejected as
# invalid with SHA256SUMS withheld. The harness was right; the sampler was
# the defect (integration tests 1 and 6 of 2026-09-18).
#
# The default source is now the kernel's own cgroup v2 accounting, read
# straight from /sys/fs/cgroup: no daemon, no CLI, a few small file reads
# per second. The columns keep their previous meaning:
#
#   cpu_pct   100 * delta(cpu.stat usage_usec) / delta(wall clock), i.e.
#             docker's single-CPU basis (can exceed 100 for a
#             multi-threaded container); the harness analysis normalizes
#             it by nproc from sut_environment.json (audit 9.7). Wall
#             time comes from /proc/uptime, which no clock step moves —
#             ts_utc does come from the clock, and a backward step makes
#             the harness reject the file, which is the intended failure.
#   mem_bytes memory.current minus memory.stat's inactive_file — the same
#             "used" part that `docker stats` reports on cgroup v2.
#   mem_pct   100 * mem_bytes / memory.max, falling back to MemTotal when
#             the cgroup is unlimited, as `docker stats` does.
#
# A sample whose inputs cannot be read writes NO ROW for that container
# and a line in the diagnostics file: a hole is evidence of a failed
# sample, a zero would be a claim. The first sample of a fresh state file
# only primes the CPU delta and writes no row either, so --max-samples N
# yields N-1 rows per container.
#
# Container names come from the container's own config.v2.json under the
# Docker data root (no daemon call). When that file is unreadable — an
# unprivileged collector — the names are taken from a `docker ps` listing
# refreshed only when a container id appears that is not yet named, and at
# most once every 10 s, so a slow CLI can never dominate the cadence.
# Until a name resolves, rows carry the 12-character container id, which
# keeps the non-empty-name rule of the ingest validation; the id is never
# cached as if it were the name, so every sample retries the real sources.
#
# `--source docker` restores the old docker-stats loop, for a host whose
# cgroup v2 tree is not visible (cgroup v1, or Docker inside a VM the
# collector cannot see into). `auto` (the default) re-evaluates the source
# ON EVERY SAMPLE and says on stderr whenever it changes: the collector is
# started before the warm-up, so the containers may not exist yet when it
# begins, and a source chosen once would keep the whole run on the slow
# path. `--no-docker` forbids the CLI altogether — neither the
# docker-stats source nor the name listing — for a collector that must
# not depend on the daemon.
#
# Runs until SIGTERM/SIGINT, until --duration expires or until
# --max-samples samples have been taken. One collector per output file:
# the output is locked, so a retried start hook or a forgotten manual
# collector cannot interleave rows into one CSV.
#
# Usage (ON the VM):
#   sh collect-resources.sh <output.csv> [--duration SECONDS]
#                           [--interval SECONDS] [--source auto|cgroup|docker]
#                           [--max-samples N] [--no-docker] [--state-file FILE]
#
# --state-file keeps the CPU-delta state at a chosen path. By default the
# state lives beside the process and is deleted when it exits, so a
# restarted collector re-primes and costs one sample.
#
# Self-test options, refused unless --self-test is given as well:
#   --self-test --cgroup-root DIR --docker-root DIR --uptime-from FILE
#               --meminfo-from FILE
# They point the collector at a synthetic tree so its arithmetic can be
# checked without containers (src/tests/test_collect_resources.py). A
# self-test run is NOT a measurement: it says so on stderr and writes
# <output>.self-test beside the CSV naming every substituted path, so a
# file produced that way can always be told from a measured one.
#
# Preferred orchestration (sprint P5): let the harness drive this script
# per run through its collector hooks — `run` and `campaign` start it
# BEFORE the warm-up, stop it AFTER the measured run and fetch its output
# AFTER the confirmation window, recording every hook's exit code in the
# run manifest:
#
#   python -m egw_experiments campaign ... \
#     --collector-start-cmd "ssh vm 'systemd-run --unit egw-resources-{run_id} \
#         --collect sh /opt/egw/src/deployment/scripts/collect-resources.sh \
#         /tmp/resources-{run_id}.csv --duration {duration_s}'" \
#     --collector-stop-cmd  "ssh vm 'systemctl stop egw-resources-{run_id}'" \
#     --collector-fetch-cmd 'scp vm:/tmp/resources-{run_id}.csv {dest}'
#
# Manual equivalent, around one timed run (start before the warm-up, stop
# after the confirmation window, fetch, then ingest with
# `run/collect --resources-from`):
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
# Keep the collector's own stderr (the `>/tmp/collect-<run_id>.log` above,
# or the unit's journal): it carries the chosen source, every source
# change and the diagnostics of skipped samples.
#
# Timed runs WITHOUT this collector's output are marked validity 'invalid'
# by the harness (override only with --allow-missing-resources).
#
# POSIX sh + awk only: the gateway image ships busybox, so no bashism, no
# gawk extension (no systime/strftime/gensub) and no coreutils-only flag
# is used. In cgroup mode the docker CLI is not required at all.

set -u

usage() {
    echo "usage: $0 <output.csv> [--duration SECONDS] [--interval SECONDS]" >&2
    echo "          [--source auto|cgroup|docker] [--max-samples N] [--no-docker]" >&2
    echo "          [--state-file FILE]" >&2
    echo "       self-test only: --self-test [--cgroup-root DIR] [--docker-root DIR]" >&2
    echo "          [--uptime-from FILE] [--meminfo-from FILE]" >&2
    exit 2
}

[ $# -ge 1 ] || usage
OUT=$1
shift

DURATION=0
INTERVAL=1
MAX_SAMPLES=0
SOURCE=auto
USE_DOCKER_NAMES=1
SELF_TEST=0
CGROUP_ROOT=/sys/fs/cgroup
DOCKER_ROOT=/var/lib/docker
UPTIME_FILE=/proc/uptime
MEMINFO_FILE=/proc/meminfo
STATE_FILE=
SUBSTITUTED=

while [ $# -gt 0 ]; do
    case "$1" in
        --duration)
            [ $# -ge 2 ] || usage
            DURATION=$2
            shift 2
            ;;
        --interval)
            [ $# -ge 2 ] || usage
            INTERVAL=$2
            shift 2
            ;;
        --max-samples)
            [ $# -ge 2 ] || usage
            MAX_SAMPLES=$2
            shift 2
            ;;
        --source)
            [ $# -ge 2 ] || usage
            SOURCE=$2
            shift 2
            ;;
        --no-docker)
            USE_DOCKER_NAMES=0
            shift
            ;;
        --self-test)
            SELF_TEST=1
            shift
            ;;
        --state-file)
            [ $# -ge 2 ] || usage
            STATE_FILE=$2
            shift 2
            ;;
        --cgroup-root)
            [ $# -ge 2 ] || usage
            CGROUP_ROOT=$2
            SUBSTITUTED="$SUBSTITUTED cgroup-root=$2"
            shift 2
            ;;
        --docker-root)
            [ $# -ge 2 ] || usage
            DOCKER_ROOT=$2
            SUBSTITUTED="$SUBSTITUTED docker-root=$2"
            shift 2
            ;;
        --uptime-from)
            [ $# -ge 2 ] || usage
            UPTIME_FILE=$2
            SUBSTITUTED="$SUBSTITUTED uptime-from=$2"
            shift 2
            ;;
        --meminfo-from)
            [ $# -ge 2 ] || usage
            MEMINFO_FILE=$2
            SUBSTITUTED="$SUBSTITUTED meminfo-from=$2"
            shift 2
            ;;
        *) usage ;;
    esac
done

case "$DURATION" in
    *[!0-9]*) usage ;;
esac
case "$INTERVAL" in
    *[!0-9]*) usage ;;
esac
case "$MAX_SAMPLES" in
    *[!0-9]*) usage ;;
esac
case "$SOURCE" in
    auto | cgroup | docker) ;;
    *) usage ;;
esac
[ "$INTERVAL" -ge 1 ] || usage

# A measurement never reads its inputs from a substituted path. Without
# this guard a plain invocation could produce a file that carries the real
# hostname and real timestamps around invented numbers, and no rule of the
# ingest validation could tell it from a measured one.
if [ -n "$SUBSTITUTED" ] && [ "$SELF_TEST" -eq 0 ]; then
    echo "error: --cgroup-root, --docker-root, --uptime-from and --meminfo-from are self-test options" >&2
    echo "       and need --self-test; a run that reads substituted inputs is not a measurement" >&2
    exit 2
fi

# Host provenance (work order P1): recorded on every row and verified by
# the harness against sut_environment.json at ingestion.
HOST=$(hostname 2>/dev/null || uname -n)

# One collector per output file: two of them appending to one CSV produce
# duplicate rows that satisfy every ingest rule.
LOCK_DIR="$OUT.lock"
if ! mkdir "$LOCK_DIR" 2> /dev/null; then
    echo "error: $LOCK_DIR exists: another collector is writing $OUT (or one was killed)." >&2
    echo "       Check with 'cat $LOCK_DIR/pid' and remove the directory only when no collector is running." >&2
    exit 1
fi
echo "$$" > "$LOCK_DIR/pid" 2> /dev/null || :

if [ -z "$STATE_FILE" ]; then
    STATE_FILE="${TMPDIR:-/tmp}/collect-resources.$$.state"
    STATE_IS_OURS=1
else
    STATE_IS_OURS=0
fi
LIST_FILE="$STATE_FILE.dirs"
NAMES_FILE="$STATE_FILE.names"
WARN_FILE="$STATE_FILE.warn"

cleanup() {
    rm -f "$LIST_FILE" "$NAMES_FILE" "$NAMES_FILE.tmp" "$WARN_FILE" "$STATE_FILE.tmp"
    [ "$STATE_IS_OURS" -eq 1 ] && rm -f "$STATE_FILE"
    rm -f "$LOCK_DIR/pid"
    rmdir "$LOCK_DIR" 2> /dev/null || :
}
stop=0
trap 'stop=1' TERM INT
trap cleanup EXIT

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

if [ "$SELF_TEST" -eq 1 ]; then
    echo "SELF-TEST RUN: inputs are substituted ($SUBSTITUTED); this output is NOT a measurement" >&2
    {
        echo "self_test=1"
        echo "started_utc=$(date -u '+%Y-%m-%dT%H:%M:%SZ')"
        echo "host=$HOST"
        for s in $SUBSTITUTED; do echo "$s"; done
    } > "$OUT.self-test"
fi

: > "$LIST_FILE" || {
    echo "error: cannot write working file $LIST_FILE" >&2
    exit 1
}
: > "$WARN_FILE" || :

# Container cgroups live either under the systemd driver's scopes or under
# the cgroupfs driver's own directory. DIRS is newline separated; IDS is
# the space separated id list. Both are set by this function; POSIX shell
# functions run in the current shell, so no subshell is forked per sample.
DIRS=
IDS=
cgroup_discover() {
    DIRS=
    IDS=
    for _d in "$CGROUP_ROOT"/system.slice/docker-*.scope "$CGROUP_ROOT"/docker/*; do
        [ -d "$_d" ] || continue
        [ -f "$_d/cpu.stat" ] || continue
        [ -f "$_d/memory.current" ] || continue
        _b=${_d##*/}
        _b=${_b#docker-}
        _b=${_b%.scope}
        [ -n "$_b" ] || continue
        DIRS="$DIRS$_d
"
        IDS="$IDS $_b"
    done
}

# The whole per-sample computation is one awk program: it reads the state
# file, every container's cpu.stat/memory.current/memory.stat/memory.max,
# resolves names, prints the CSV rows and writes the next state to a
# temporary file the shell moves into place. Reading the files in awk
# keeps the sample to a single process.
AWK_CGROUP='
function warn(msg) {
    print TS " " msg >> WARNF
}
function firstfield(f,   line, a, v) {
    v = ""
    if ((getline line < f) > 0) {
        split(line, a, " ")
        v = a[1]
    }
    close(f)
    return v
}
function statfield(f, key,   line, a, v) {
    v = ""
    while ((getline line < f) > 0) {
        split(line, a, " ")
        if (a[1] == key) {
            v = a[2]
            break
        }
    }
    close(f)
    return v
}
function memtotal(   line, a, v) {
    if (MEMTOTAL != "") return MEMTOTAL
    MEMTOTAL = ""
    while ((getline line < MEMINFO) > 0) {
        split(line, a, " ")
        if (a[1] == "MemTotal:") {
            v = a[2]
            if (v !~ /^[0-9]+$/) break
            if (a[3] == "kB") v = v * 1024
            MEMTOTAL = v ""
            break
        }
    }
    close(MEMINFO)
    return MEMTOTAL
}
function idof(d,   n, parts, b) {
    n = split(d, parts, "/")
    b = parts[n]
    sub(/^docker-/, "", b)
    sub(/\.scope$/, "", b)
    return b
}
# Returns the real name, or "" when it cannot be resolved yet. The
# 12-character id used in that case is never cached: a container whose
# name becomes readable later (an unprivileged collector, a container
# recreated mid-run) must not keep an id as its label for the whole run.
function resolve(id,   f, line, v, b, got) {
    if (id in NAME && NAME[id] != "") return NAME[id]
    v = ""
    f = DOCKERROOT "/containers/" id "/config.v2.json"
    if ((getline line < f) > 0) {
        if (match(line, /[,{]"Name":"\/[^"]+"/)) {
            v = substr(line, RSTART + 9, RLENGTH - 10)
        } else if (match(line, /"Name":"\/[^"]+"/)) {
            v = substr(line, RSTART + 8, RLENGTH - 9)
        }
        sub(/^\//, "", v)
    }
    close(f)
    if (v == "") {
        while ((getline line < NAMES) > 0) {
            got = split(line, b, " ")
            if (got >= 2 && substr(id, 1, length(b[1])) == b[1]) {
                v = b[2]
                break
            }
        }
        close(NAMES)
    }
    if (v != "") NAME[id] = v
    return v
}
BEGIN {
    # An empty TS means the shell verified at startup that this awk
    # formats UTC correctly, and left the timestamp to it: one process per
    # sample instead of two.
    if (TS == "") TS = strftime("%Y-%m-%dT%H:%M:%SZ", systime(), 1)
    if (TS !~ /^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z$/) {
        warn("refusing to write a row without a well-formed UTC timestamp")
        exit 3
    }
    while ((getline line < STATE) > 0) {
        n = split(line, a, "\t")
        if (n < 3) continue
        if (a[2] !~ /^[0-9]+$/) continue
        if (a[3] !~ /^[0-9]+(\.[0-9]+)?$/) continue
        PREV_USAGE[a[1]] = a[2] + 0
        PREV_WALL[a[1]] = a[3] + 0
        SEEN[a[1]] = 1
        if (n >= 4 && a[4] != "") NAME[a[1]] = a[4]
    }
    close(STATE)

    wall = firstfield(UPTIME)
    if (wall !~ /^[0-9]+(\.[0-9]+)?$/) {
        warn("cannot read a wall clock from " UPTIME "; no sample taken")
        exit 3
    }
    wall = wall + 0

    MEMTOTAL = ""
    state = ""
    while ((getline dir < LIST) > 0) {
        if (dir == "") continue
        id = idof(dir)
        usage = statfield(dir "/cpu.stat", "usage_usec")
        current = firstfield(dir "/memory.current")
        name = resolve(id)
        label = (name == "" ? substr(id, 1, 12) : name)
        if (usage !~ /^[0-9]+$/ || current !~ /^[0-9]+$/) {
            # Keep the previous reading, so one unreadable sample costs one
            # row and not two (the next delta simply spans a longer interval).
            if (id in SEEN) {
                state = state id "\t" PREV_USAGE[id] "\t" PREV_WALL[id] "\t" name "\n"
            }
            warn("unreadable cpu.stat or memory.current for " label "; no row")
            continue
        }
        usage = usage + 0
        current = current + 0
        if (id in SEEN) {
            dwall = wall - PREV_WALL[id]
            dusage = usage - PREV_USAGE[id]
            if (dwall > 0 && dusage >= 0) {
                inactive = statfield(dir "/memory.stat", "inactive_file")
                limit = firstfield(dir "/memory.max")
                if (limit == "" || limit == "max") limit = memtotal()
                if (inactive !~ /^[0-9]+$/) {
                    warn("unreadable memory.stat for " label "; no row (a zero would not be a measurement)")
                } else if (limit !~ /^[0-9]+$/ || limit + 0 <= 0) {
                    warn("no memory limit and no MemTotal for " label "; no row")
                } else {
                    used = current - (inactive + 0)
                    if (used < 0) used = 0
                    printf "%s,%s,%.2f,%.0f,%.2f,%s\n", TS, label, \
                        100 * dusage / (dwall * 1000000), used, \
                        100 * used / (limit + 0), HOST
                }
            }
        }
        state = state id "\t" usage "\t" wall "\t" name "\n"
    }
    close(LIST)
    # Written to a temporary file the shell moves into place: a collector
    # killed mid-write must not leave a truncated state line behind.
    printf("%s", state) > STATETMP
    close(STATETMP)
}
'

# docker stats parser, kept for --source docker: every line is a flat JSON
# object with "Name":"...", "CPUPerc":"1.23%", "MemUsage":"126.4MiB /
# 7.628GiB", "MemPerc":"1.61%".
AWK_DOCKER='
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

# --no-docker means exactly that: neither the docker-stats source nor the
# name listing may call the CLI.
have_docker() {
    [ "$USE_DOCKER_NAMES" -eq 1 ] && command -v docker > /dev/null 2>&1
}

if [ "$SOURCE" = docker ] && [ "$USE_DOCKER_NAMES" -eq 0 ]; then
    echo "error: --source docker and --no-docker contradict each other" >&2
    exit 2
fi
if [ "$SOURCE" = docker ] && ! have_docker; then
    echo "error: --source docker needs the docker CLI, which is not on PATH" >&2
    exit 1
fi
if ! have_docker; then
    USE_DOCKER_NAMES=0
fi

# Pacing clock. Every process the loop forks costs real time on an
# emulated guest — that is what made the previous sampler unusable — so
# the elapsed time is read from /proc/uptime with the shell's own `read`,
# which forks nothing, and falls back to `date` only where /proc is not
# readable. This clock paces the loop; it is never written into a row.
PACE_FROM_UPTIME=0
[ -r /proc/uptime ] && PACE_FROM_UPTIME=1
NOW_S=0
now_s() {
    if [ "$PACE_FROM_UPTIME" -eq 1 ]; then
        read -r _u _rest < /proc/uptime 2> /dev/null || {
            NOW_S=$(date +%s)
            return
        }
        NOW_S=${_u%%.*}
    else
        NOW_S=$(date +%s)
    fi
}

# The sample's timestamp can come from awk itself, saving the only other
# process the cgroup path needs. It is used only when awk's own UTC
# formatting is verified here against `date -u`, twice, so an awk without
# systime/strftime or one whose strftime ignores the UTC flag falls back
# to `date` instead of writing local time into the evidence.
TS_FROM_AWK=0
_awk_ts='BEGIN { t = systime(); if (t < 1000000000) exit 1; print strftime("%Y-%m-%dT%H:%M:%SZ", t, 1) }'
for _try in 1 2; do
    _a=$(awk "$_awk_ts" 2> /dev/null) || continue
    [ -n "$_a" ] || continue
    if [ "$_a" = "$(date -u '+%Y-%m-%dT%H:%M:%SZ')" ]; then
        TS_FROM_AWK=1
        break
    fi
done

now_s
started_pace=$NOW_S
last_names=0
named_ids=
samples=0
effective=
warned=0
echo "collecting container resources into $OUT (source: $SOURCE, one sample every ${INTERVAL}s, duration: ${DURATION}s, 0 = until SIGTERM; timestamps from $([ "$TS_FROM_AWK" -eq 1 ] && echo awk || echo date))" >&2

while [ "$stop" -eq 0 ]; do
    now_s
    loop_start=$NOW_S

    # The source is re-evaluated on every sample in auto mode: the
    # collector starts before the containers exist.
    if [ "$SOURCE" = auto ]; then
        cgroup_discover
        if [ -n "$DIRS" ]; then
            this=cgroup
        elif have_docker; then
            this=docker
        else
            this=none
        fi
    else
        this=$SOURCE
        [ "$this" = cgroup ] && cgroup_discover
    fi
    if [ "$this" != "$effective" ]; then
        case "$this" in
            cgroup) echo "sample $((samples + 1)): sampling source: cgroup v2 under $CGROUP_ROOT" >&2 ;;
            docker) echo "sample $((samples + 1)): sampling source: docker stats (no container cgroup under $CGROUP_ROOT)" >&2 ;;
            none) echo "sample $((samples + 1)): no sampling source: no container cgroup and no docker CLI" >&2 ;;
        esac
        effective=$this
    fi

    # `date` is forked only when awk cannot produce the timestamp itself,
    # and always for the docker path, which does not run the awk program
    # that would.
    if [ "$TS_FROM_AWK" -eq 1 ] && [ "$this" = cgroup ]; then
        ts=
    else
        ts=$(date -u '+%Y-%m-%dT%H:%M:%SZ')
    fi

    if [ "$this" = cgroup ]; then
        printf '%s' "$DIRS" > "$LIST_FILE"
        # Refresh the docker name listing only for an id that is still
        # unnamed, only when the listing succeeds, and never more than
        # once every 10 s: config.v2.json normally answers first and this
        # stays unused.
        if [ "$USE_DOCKER_NAMES" -eq 1 ] && [ $((loop_start - last_names)) -ge 10 ]; then
            for _id in $IDS; do
                case " $named_ids " in
                    *" $_id "*) ;;
                    *)
                        if docker ps -a --no-trunc --format '{{.ID}} {{.Names}}' \
                            > "$NAMES_FILE.tmp" 2> /dev/null && [ -s "$NAMES_FILE.tmp" ]; then
                            mv "$NAMES_FILE.tmp" "$NAMES_FILE"
                            named_ids="$named_ids $IDS"
                        else
                            rm -f "$NAMES_FILE.tmp"
                        fi
                        last_names=$loop_start
                        break
                        ;;
                esac
            done
        fi
        if awk -v TS="$ts" -v HOST="$HOST" -v STATE="$STATE_FILE" \
            -v STATETMP="$STATE_FILE.tmp" -v LIST="$LIST_FILE" \
            -v NAMES="$NAMES_FILE" -v WARNF="$WARN_FILE" \
            -v UPTIME="$UPTIME_FILE" -v MEMINFO="$MEMINFO_FILE" \
            -v DOCKERROOT="$DOCKER_ROOT" "$AWK_CGROUP" >> "$OUT"; then
            [ -f "$STATE_FILE.tmp" ] && mv "$STATE_FILE.tmp" "$STATE_FILE"
        fi
    elif [ "$this" = docker ]; then
        # --format json is JSON-lines on Docker >= 23; older CLIs accept
        # the equivalent '{{json .}}' template. The modern form is tried
        # first on every sample so a CLI downgrade mid-campaign still
        # degrades gracefully.
        lines=$(docker stats --no-stream --format json 2>/dev/null)
        if [ -z "$lines" ]; then
            lines=$(docker stats --no-stream --format '{{json .}}' 2>/dev/null)
        fi
        if [ -n "$lines" ]; then
            printf '%s\n' "$lines" | awk -v TS="$ts" -v HOST="$HOST" "$AWK_DOCKER" >> "$OUT"
        fi
    fi

    if [ "$warned" -eq 0 ] && [ -s "$WARN_FILE" ]; then
        echo "diagnostics (first lines; the rest are counted at the end):" >&2
        sed -n '1,5p' "$WARN_FILE" >&2
        warned=1
    fi

    samples=$((samples + 1))
    if [ "$MAX_SAMPLES" -gt 0 ] && [ "$samples" -ge "$MAX_SAMPLES" ]; then
        break
    fi
    now_s
    if [ "$DURATION" -gt 0 ] && [ $((NOW_S - started_pace)) -ge "$DURATION" ]; then
        break
    fi
    # Sleep only the remainder of the interval: the period must be the
    # interval, not the interval plus the cost of the sample. Consecutive
    # samples of one container more than MAX_SAMPLE_GAP_S apart invalidate
    # the run however many instants it holds.
    rest=$((INTERVAL - (NOW_S - loop_start)))
    [ "$rest" -gt 0 ] && sleep "$rest"
done

skipped=0
[ -s "$WARN_FILE" ] && skipped=$(wc -l < "$WARN_FILE")
echo "collector stopped after $samples samples ($skipped skipped-sample diagnostics); output: $OUT" >&2
