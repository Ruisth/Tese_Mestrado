#!/bin/sh
# collect-resources.sh — SUT container resource collector, one sample per
# wall-clock second. Runs ON the ARM VM (the system under test), never on the
# harness host (audit 2026-08-08 section 9.1: the harness's local docker-stats
# sampler measures the load-generator host by default — the wrong system for
# RQ3).
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
#     30 DISTINCT ts_utc instants (MIN_DISTINCT_SAMPLE_INSTANTS), pooled and
#     per container, counted over the WHOLE FILE — not only inside the
#     measured window. One sample writes one row per container, so 30 rows
#     can be five seconds of six containers,
#   - consecutive samples of one container are at most MAX_SAMPLE_GAP_S
#     (5 s) apart around and inside the measured window,
#   - the sampled instants span at least 90% of the run's measured window
#     (RESOURCE_WINDOW_COVERAGE_MIN_FRAC, pending advisor sign-off), overall
#     and per container,
#   - every host value equals the node/hostname recorded in
#     sut_environment.json (when that file provides one).
# The validator does not reject two rows of one container in the same
# second; this collector does not write them (see Cadence).
#
# What the harness actually does with it (src/egw_experiments/run.py): the
# start hook runs just before any warm-up, the stop hook runs just after the
# measured run and BEFORE the 60 s confirmation window, and the fetch hook
# runs after that window. A condition with no warm-up therefore gives the
# collector almost no lead: its first sample only primes the CPU delta (see
# below) and falls inside the measured window. A 30 s condition with no
# warm-up has no margin for the 30-instant rule; the runbook's remedy is a
# nominal entry, whose 120 s warm-up gives the collector its lead.
#
# ---------------------------------------------------------------------
# Sampling source (changed 2026-09-19; LOG entry #C034)
# ---------------------------------------------------------------------
# Until 2026-09-19 every sample ran `docker stats --no-stream`. On the
# emulated ARM64 guest (QEMU/TCG) one such call cost 3-5 s idle and about
# 21 s while the stack was working (session of 2026-09-18), because the
# Docker CLI must round-trip the daemon and the daemon itself samples every
# container. The collector produced about 7 distinct instants in 150 s.
#
# The default source is now the kernel's own cgroup v2 accounting, read
# straight from /sys/fs/cgroup: no daemon, no CLI, a few small file reads
# per sample. The columns keep their previous meaning:
#
#   cpu_pct   100 * delta(cpu.stat usage_usec) / delta(elapsed time), i.e.
#             docker's single-CPU basis (can exceed 100 for a
#             multi-threaded container); the harness analysis normalizes
#             it by nproc from sut_environment.json (audit 9.7). Elapsed
#             time comes from /proc/uptime, kept exactly as read (never
#             re-rounded), which no clock step moves. The figure is the CPU
#             time the GUEST accounts to the container; it is not the host
#             QEMU process's CPU and not native performance.
#   mem_bytes memory.current minus memory.stat's inactive_file when the
#             latter is smaller, otherwise memory.current — docker's cgroup v2
#             "used" definition; it is not total cgroup usage and does not by
#             itself give an OOM margin.
#   mem_pct   100 * mem_bytes / memory.max. Only an explicit "max" in
#             memory.max means unlimited, and only then is the guest's
#             MemTotal used as the denominator, as `docker stats` does. An
#             unreadable or empty memory.max is NOT unlimited: that sample
#             writes no row and a diagnostic.
#
# A sample whose inputs cannot be read writes NO ROW for that container
# and a diagnostic: a hole is evidence of a failed sample, a zero would be
# a claim. The first sample of a container only primes its CPU delta and
# writes no row either, so --max-samples N yields at most N-1 rows per
# container.
#
# ---------------------------------------------------------------------
# Cadence and timestamps (changed 2026-09-19)
# ---------------------------------------------------------------------
# Timestamps have whole-second resolution, so two samples in one wall-clock
# second collapse into one instant and a slipped sample leaves a second
# without one. Two earlier versions showed both on the guest: commit
# aa7440d paced on elapsed whole seconds and gave 26 distinct instants from
# 30 samples in 29 s (samples sharing a second); an uncommitted intermediate
# version slept a whole interval after each sample and gave 0.84 distinct
# instants per second over 600 s (a second skipped about every five).
#
# This version works with what the gateway's busybox 1.36.1 offers — its
# ash has no $EPOCHREALTIME (CONFIG_ASH_RANDOM_SUPPORT is off) but has a
# builtin fractional `sleep` (CONFIG_FLOAT_DURATION) — and nothing else:
#   - the timestamp of a sample is the wall-clock second awk reads with
#     systime() as it starts the sample (verified against `date +%s` at
#     startup; `date` per sample if awk lacks systime), formatted in UTC by
#     arithmetic: no strftime (whose UTC flag busybox ignores), no time zone;
#   - samples are paced on /proc/uptime in centiseconds with the fractional
#     sleep, each aimed 0.5 s into a wall-clock second. The offset between
#     /proc/uptime and the wall clock is calibrated after the first sample, by
#     watching the same clock the stamps come from (awk systime(), or `date +%s`
#     when awk has none) cross a second boundary, and again when a sample lands
#     in a second other than the one it aimed at — at most once every 10 s, since
#     a calibration costs up to a second of clock reads. A wall clock that is
#     stepped or slewed (NTP, a hypervisor's time sync) costs a recalibration and
#     at most a skipped second, which is counted; it never turns this pacing off;
#   - awk keeps the last stamped second in the state file and WITHHOLDS a
#     sample stamped with that second or an earlier one (a clock stepped
#     back, or two samples in one second), with a diagnostic; every second
#     left without a sample is counted and written to the diagnostics, in
#     every mode, so the closing summary's skipped-second count is measured.
# Without a fractional sleep the collector paces on whole seconds and says
# so; the withholding and the counting still apply.
#
# ---------------------------------------------------------------------
# Files written beside <output.csv>
# ---------------------------------------------------------------------
#   <output.csv>.diagnostics.log  every diagnostic, one timestamped line
#                                 each, appended and never deleted: the
#                                 collector's own sha256 and the host at
#                                 start, the pacing mode and calibrations,
#                                 source changes, withheld samples, seconds
#                                 without a sample, unreadable inputs, a
#                                 sampler process that failed, the service
#                                 inventory and a closing summary
#   <output.csv>.lifecycle.csv    ts_utc,event,container_id,name — one row
#                                 when a container cgroup appears, when it
#                                 disappears, when its CPU counter resets (a
#                                 recreated cgroup) and when an id first
#                                 resolves to a name: the full id-to-service
#                                 mapping and the evidence of a restart
#   <output.csv>.self-test        only in a self-test run (see below)
# Fetch the first two with the CSV: they explain every gap in it. Only a
# short excerpt of the diagnostics reaches stderr.
#
# Container names come from the container's own config.v2.json under the
# Docker data root (no daemon call). Only when that file is unreadable for
# some container — an unprivileged collector — is a `docker ps` listing
# taken, at most once every 10 s. Until a name resolves, rows carry the
# 12-character container id, which keeps the non-empty-name rule of the
# ingest validation; the id is never cached as if it were the name.
#
# --expect-services NAME,NAME,... names the services the run must observe
# (for the gateway stack, the six Compose container names). When the
# collector stops, it writes one "inventory:" line to the diagnostics: every
# name observed, the expected names, the expected names never observed, and
# how many container ids never resolved to a name. The collector records; whether a missing service
# invalidates a run is the harness's and the protocol's decision.
#
# `--source docker` restores the old docker-stats loop, for a host whose
# cgroup v2 tree is not visible. `auto` (the default) re-evaluates the source
# ON EVERY SAMPLE and records every change. `--no-docker` forbids the CLI.
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
#                           [--expect-services NAME,NAME,...]
#
# --state-file keeps the CPU-delta state (and the last stamped second) at a
# chosen path. By default the state lives beside the process and is deleted
# when it exits, so a restarted collector re-primes and costs one sample.
#
# Self-test options, refused unless --self-test is given as well:
#   --self-test --cgroup-root DIR --docker-root DIR --uptime-from FILE
#               --meminfo-from FILE
#   --self-test --stamp-epoch SECONDS   (with --max-samples 1 only)
#   --self-test --format-epoch SECONDS  (prints that instant in UTC, exits)
# They point the collector at a synthetic tree and clock so its arithmetic
# can be checked without containers (src/tests/test_collect_resources.py). A
# self-test run is NOT a measurement: it says so on stderr and writes
# <output>.self-test beside the CSV naming every substituted input, so a
# file produced that way can always be told from a measured one.
#
# Orchestration (sprint P5): the harness drives this script per run through
# its collector hooks and records every hook's exit code in the manifest:
#
#   python -m egw_experiments campaign ... \
#     --collector-start-cmd "ssh vm 'systemd-run --unit egw-resources-{run_id} \
#         --collect sh /opt/egw/deployment/scripts/collect-resources.sh \
#         /tmp/resources-{run_id}.csv --duration {duration_s} \
#         --expect-services egw-mosquitto-1,egw-mongodb-1,egw-ditto-policies-1,egw-ditto-things-1,egw-ditto-gateway-1,egw-controller-1'" \
#     --collector-stop-cmd  "ssh vm 'systemctl stop egw-resources-{run_id}'" \
#     --collector-fetch-cmd 'scp vm:/tmp/resources-{run_id}.csv {dest}'
#
# The fetch hook above collects the CSV alone; fetch the two companion files
# as well (`scp 'vm:/tmp/resources-<run_id>.csv*' .`) until the harness does.
#
# Timed runs WITHOUT this collector's output are marked validity 'invalid'
# by the harness (override only with --allow-missing-resources).
#
# POSIX sh + awk: tested under dash, bash and the gateway image's own busybox
# ash and awk. Every facility beyond POSIX is checked at startup.

set -u

usage() {
    echo "usage: $0 <output.csv> [--duration SECONDS] [--interval SECONDS]" >&2
    echo "          [--source auto|cgroup|docker] [--max-samples N] [--no-docker]" >&2
    echo "          [--state-file FILE] [--expect-services NAME,NAME,...]" >&2
    echo "       self-test only: --self-test [--cgroup-root DIR] [--docker-root DIR]" >&2
    echo "          [--uptime-from FILE] [--meminfo-from FILE] [--stamp-epoch SECONDS]" >&2
    echo "          [--format-epoch SECONDS]" >&2
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
EXPECT_SERVICES=
FORMAT_EPOCH=
STAMP_EPOCH=

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
        --expect-services)
            [ $# -ge 2 ] || usage
            EXPECT_SERVICES=$2
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
        --stamp-epoch)
            [ $# -ge 2 ] || usage
            STAMP_EPOCH=$2
            SUBSTITUTED="$SUBSTITUTED stamp-epoch=$2"
            shift 2
            ;;
        --format-epoch)
            [ $# -ge 2 ] || usage
            FORMAT_EPOCH=$2
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
case "$EXPECT_SERVICES" in
    *[!A-Za-z0-9_.,-]*) usage ;;
esac
case "$STAMP_EPOCH$FORMAT_EPOCH" in
    *[!0-9]*) usage ;;
esac
[ "$INTERVAL" -ge 1 ] || usage

# UTC from an integer epoch by civil-calendar arithmetic (days from
# 1970-01-01 to year/month/day), shared by every awk program below. It needs
# no strftime, whose UTC flag busybox awk ignores, and no time zone.
AWK_UTC='
function utc(t,   days, secs, z, era, doe, yoe, y, doy, mp, d, mo) {
    days = int(t / 86400)
    secs = t - days * 86400
    z = days + 719468
    era = int(z / 146097)
    doe = z - era * 146097
    yoe = int((doe - int(doe / 1460) + int(doe / 36524) - int(doe / 146096)) / 365)
    y = yoe + era * 400
    doy = doe - (365 * yoe + int(yoe / 4) - int(yoe / 100))
    mp = int((5 * doy + 2) / 153)
    d = doy - int((153 * mp + 2) / 5) + 1
    mo = (mp < 10) ? mp + 3 : mp - 9
    if (mo <= 2) y++
    return sprintf("%04d-%02d-%02dT%02d:%02d:%02dZ", y, mo, d, int(secs / 3600), int((secs % 3600) / 60), secs % 60)
}
'

# A measurement never reads its inputs from a substituted path or clock.
# Without this guard a plain invocation could produce a file that carries the
# real hostname around invented numbers, and no rule of the ingest validation
# could tell it from a measured one.
if { [ -n "$SUBSTITUTED" ] || [ -n "$FORMAT_EPOCH" ]; } && [ "$SELF_TEST" -eq 0 ]; then
    echo "error: --cgroup-root, --docker-root, --uptime-from, --meminfo-from, --stamp-epoch and" >&2
    echo "       --format-epoch are self-test options and need --self-test; a run that reads" >&2
    echo "       substituted inputs is not a measurement" >&2
    exit 2
fi
if [ -n "$STAMP_EPOCH" ] && [ "$MAX_SAMPLES" != 1 ]; then
    echo "error: --stamp-epoch fixes one sample's second and needs --max-samples 1" >&2
    exit 2
fi

if [ -n "$FORMAT_EPOCH" ]; then
    awk -v T="$FORMAT_EPOCH" "$AWK_UTC"'BEGIN { print utc(T + 0) }'
    exit $?
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
ERR_FILE="$STATE_FILE.err"
DIAG_FILE="$OUT.diagnostics.log"
LIFE_FILE="$OUT.lifecycle.csv"

# Working files only: the diagnostics and the lifecycle file are evidence
# and are never removed.
cleanup() {
    rm -f "$LIST_FILE" "$NAMES_FILE" "$NAMES_FILE.tmp" "$STATE_FILE.tmp" "$ERR_FILE"
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
if [ ! -s "$LIFE_FILE" ]; then
    echo "ts_utc,event,container_id,name" > "$LIFE_FILE"
fi
: >> "$DIAG_FILE" || {
    echo "error: cannot write $DIAG_FILE" >&2
    exit 1
}

# A diagnostic from the shell itself: rare (start, calibrations, source
# changes, failed sampler processes, stop), so one `date` per line is
# affordable.
diag() {
    echo "$(date -u '+%Y-%m-%dT%H:%M:%SZ') $*" >> "$DIAG_FILE"
}

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

# The whole per-sample computation is one awk program. It takes the sample's
# second (systime(), or EPOCH from the shell), refuses a second that is not
# after the last one it stamped, reads every container's cgroup files,
# resolves names, prints the CSV rows, records lifecycle events and seconds
# left without a sample, and writes the next state to a temporary file the
# shell moves into place.
#
# State file lines: "#last<TAB>second<TAB>skipped-seconds-total" and, per
# container, "id<TAB>usage_usec<TAB>uptime<TAB>name", where the uptime is the
# /proc/uptime token exactly as read and "-" marks a container seen but not
# yet primed.
#
# Exit status: 0 clean; 10 a diagnostic was written; 11 the sample was
# withheld (state untouched); 12 rows written but the sample landed in a
# second other than EXPECT (the shell recalibrates); 3 no usable clock or
# uptime (reason in ERRF, no rows).
AWK_CGROUP="$AWK_UTC"'
function warn(msg) {
    print TS " " msg >> DIAG
    WARNED = 1
}
function life(event, id, name) {
    print TS "," event "," id "," name >> LIFE
}
function fail(msg) {
    print msg > ERRF
    close(ERRF)
    exit 3
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
    if (EPOCH != "") stamp = EPOCH + 0
    else if (USE_SYSTIME == 1) stamp = systime()
    else fail("no wall clock: neither a stamp from the shell nor systime(); no rows")
    if (stamp < 1000000000 && EPOCH == "") fail("implausible wall clock " stamp "; no rows")
    TS = utc(stamp)

    LAST = ""
    SKIPPED = 0
    while ((getline line < STATE) > 0) {
        n = split(line, a, "\t")
        if (a[1] == "#last") {
            if (a[2] ~ /^[0-9]+$/) LAST = a[2] + 0
            if (a[3] ~ /^[0-9]+$/) SKIPPED = a[3] + 0
            continue
        }
        if (n < 3) continue
        if (a[2] == "-" && a[3] == "-") {
            SEEN[a[1]] = 1
            UNPRIMED[a[1]] = 1
        } else {
            if (a[2] !~ /^[0-9]+$/) continue
            if (a[3] !~ /^[0-9]+(\.[0-9]+)?$/) continue
            PREV_USAGE[a[1]] = a[2]
            PREV_WALL[a[1]] = a[3]
            SEEN[a[1]] = 1
        }
        PREV_NAME[a[1]] = (n >= 4) ? a[4] : ""
        if (PREV_NAME[a[1]] != "") NAME[a[1]] = PREV_NAME[a[1]]
    }
    close(STATE)

    # A second already stamped, or an earlier one, is never stamped again:
    # the sample is withheld and the state left as it was.
    if (LAST != "" && stamp <= LAST) {
        warn("sample withheld: it fell in second " TS ", not after the last stamped second " utc(LAST) " (a clock stepped back, or two samples in one second)")
        exit 11
    }

    wallstr = firstfield(UPTIME)
    if (wallstr !~ /^[0-9]+(\.[0-9]+)?$/) fail("cannot read an elapsed-time clock from " UPTIME "; no rows")
    wall = wallstr + 0

    MEMTOTAL = ""
    state = ""
    while ((getline dir < LIST) > 0) {
        if (dir == "") continue
        id = idof(dir)
        PRESENT[id] = 1
        usage = statfield(dir "/cpu.stat", "usage_usec")
        current = firstfield(dir "/memory.current")
        name = resolve(id)
        label = (name == "" ? substr(id, 1, 12) : name)
        if (!(id in SEEN)) life("appeared", id, name)
        else if (PREV_NAME[id] == "" && name != "") life("named", id, name)
        if (usage !~ /^[0-9]+$/ || current !~ /^[0-9]+$/) {
            # Keep the previous reading (or the unprimed marker), so one
            # unreadable sample costs one row and not two, and the container
            # stays known: a later good read is not a second appearance.
            if ((id in SEEN) && !(id in UNPRIMED)) {
                state = state id "\t" PREV_USAGE[id] "\t" PREV_WALL[id] "\t" name "\n"
            } else {
                state = state id "\t-\t-\t" name "\n"
            }
            warn("unreadable cpu.stat or memory.current for " label "; no row")
            continue
        }
        if ((id in SEEN) && !(id in UNPRIMED)) {
            dwall = wall - (PREV_WALL[id] + 0)
            dusage = usage - (PREV_USAGE[id] + 0)
            if (dwall <= 0) {
                warn("no elapsed time since the previous sample for " label "; no row")
            } else if (dusage < 0) {
                life("counter_reset", id, name)
                warn("cpu.stat went backwards for " label " (a recreated cgroup); no row, delta re-primed")
            } else {
                inactive = statfield(dir "/memory.stat", "inactive_file")
                raw = firstfield(dir "/memory.max")
                # Only an explicit "max" means unlimited; an unreadable or
                # empty memory.max is a failed read, never permission to use
                # MemTotal.
                limit = (raw == "max") ? memtotal() : raw
                if (inactive !~ /^[0-9]+$/) {
                    warn("unreadable memory.stat for " label "; no row (a zero would not be a measurement)")
                } else if (raw == "") {
                    warn("unreadable or empty memory.max for " label "; no row (only \"max\" means unlimited)")
                } else if (raw == "max" && limit == "") {
                    warn("memory.max is \"max\" (unlimited) for " label " but MemTotal is unreadable; no row")
                } else if (limit !~ /^[0-9]+$/ || limit + 0 <= 0) {
                    warn("memory.max is not a usable number for " label " (" raw "); no row")
                } else {
                    # docker (cgroup v2): subtract inactive_file only when it
                    # is smaller than the usage.
                    used = (inactive + 0 < current + 0) ? current - inactive : current + 0
                    printf "%s,%s,%.2f,%.0f,%.2f,%s\n", TS, label, \
                        100 * dusage / (dwall * 1000000), used, \
                        100 * used / (limit + 0), HOST
                }
            }
        }
        # The uptime is stored exactly as read: re-formatting it as a number
        # would round it (CONVFMT) once the guest has been up for hours.
        state = state id "\t" usage "\t" wallstr "\t" name "\n"
    }
    close(LIST)
    for (id in SEEN) {
        if (!(id in PRESENT)) life("disappeared", id, PREV_NAME[id])
    }
    if (LAST != "" && stamp - LAST > INTERVAL) {
        gap = stamp - LAST - INTERVAL
        SKIPPED += gap
        warn("no sample in the " gap " second(s) before this one (previous sample in " utc(LAST) ")")
    }
    # Written to a temporary file the shell moves into place: a collector
    # killed mid-write must not leave a truncated state line behind.
    printf("#last\t%d\t%d\n%s", stamp, SKIPPED, state) > STATETMP
    close(STATETMP)
    if (EXPECT != "" && stamp != EXPECT + 0) {
        warn("clock phase: aimed at second " utc(EXPECT + 0) " and sampled in " TS "; recalibrating")
        exit 12
    }
    # 10 tells the shell that this sample wrote a diagnostic, so it can show
    # an excerpt without searching the file on every sample.
    if (WARNED) exit 10
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

# The inventory, once, when the collector stops: expected services against
# the names the lifecycle file recorded, and ids that never got a name.
AWK_INVENTORY='
BEGIN { FS = "," }
NR > 1 && ($2 == "appeared" || $2 == "named") {
    ids[$3] = 1
    if ($4 != "") { seen[$4] = 1; named[$3] = 1 }
}
END {
    n = split(EXPECT, want, ",")
    missing = ""
    for (i = 1; i <= n; i++) {
        if (want[i] == "") continue
        if (!(want[i] in seen)) missing = missing (missing == "" ? "" : ",") want[i]
    }
    # Every observed name, in a stable (sorted) order without asort().
    k = 0
    for (name in seen) names[++k] = name
    for (i = 2; i <= k; i++) {
        v = names[i]
        for (j = i - 1; j >= 1 && names[j] > v; j--) names[j + 1] = names[j]
        names[j + 1] = v
    }
    observed = ""
    for (i = 1; i <= k; i++) observed = observed (observed == "" ? "" : ",") names[i]
    unnamed = 0
    for (id in ids) if (!(id in named)) unnamed++
    print "inventory: observed=" (observed == "" ? "none" : observed) " expected=" (EXPECT == "" ? "none-declared" : EXPECT) " missing=" (missing == "" ? "none" : missing) " unnamed_ids=" unnamed
    for (i = 1; i <= n; i++) {
        if (want[i] != "" && !(want[i] in seen)) {
            print "expected service never observed: " want[i] (unnamed > 0 ? " (" unnamed " container id(s) never resolved to a name)" : "")
        }
    }
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

# ---------------------------------------------------------------------------
# Clocks
# ---------------------------------------------------------------------------
# /proc/uptime in centiseconds, read with the shell's own `read`: no fork.
UP_CS=0
uptime_cs() {
    read -r _u _rest < /proc/uptime 2> /dev/null || return 1
    _i=${_u%%.*}
    case $_u in
        *.*) _f=${_u#*.}00 ;;
        *) _f=00 ;;
    esac
    _f=${_f%"${_f#??}"}
    case $_f in
        0?) _f=${_f#0} ;;
    esac
    UP_CS=$((_i * 100 + _f))
}
pad2() {
    _p=00$1
    PAD2=${_p#"${_p%??}"}
}

# awk's systime() is the sample's wall clock when it agrees with `date +%s`.
USE_SYSTIME=0
_a=$(awk 'BEGIN { print systime() }' 2> /dev/null) || _a=
_d=$(date +%s)
case "$_a" in
    '' | *[!0-9]*) ;;
    *) [ $((_a - _d)) -le 1 ] && [ $((_d - _a)) -le 1 ] && USE_SYSTIME=1 ;;
esac
wall_now() {
    if [ "$USE_SYSTIME" -eq 1 ]; then
        awk 'BEGIN { print systime() }'
    else
        date +%s
    fi
}

FRAC_SLEEP=0
sleep 0.01 2> /dev/null && FRAC_SLEEP=1
[ -r /proc/uptime ] && uptime_cs || FRAC_SLEEP=0

# Calibration: the /proc/uptime reading (centiseconds) at which the wall
# clock enters a new second, found by watching `date`/awk cross a boundary.
# Its error is one loop turn, well inside the 0.5 s the samples aim for.
PHASE_CS=
PHASE_S=
calibrate() {
    PHASE_CS=
    _c0=$(wall_now) || return 1
    _k=0
    while [ "$stop" -eq 0 ]; do
        uptime_cs || return 1
        _before=$UP_CS
        _c=$(wall_now) || return 1
        if [ "$_c" != "$_c0" ]; then
            PHASE_CS=$_before
            PHASE_S=$_c
            return 0
        fi
        _k=$((_k + 1))
        [ "$_k" -ge 1000 ] && return 1
    done
    return 1
}

STEP_CS=$((INTERVAL * 100))
SLOT_M=
LAST_M=
SLOT_CS=0
EXPECT_S=
# The next slot at least 0.3 s ahead and after the previous one: slot m is
# at uptime PHASE_CS + m*STEP_CS + 50, inside wall second PHASE_S + m*INTERVAL.
next_slot() {
    uptime_cs
    _num=$((UP_CS + 30 - PHASE_CS - 50))
    if [ "$_num" -le 0 ]; then
        _m=0
    else
        _m=$(((_num + STEP_CS - 1) / STEP_CS))
    fi
    if [ -n "$LAST_M" ] && [ "$_m" -le "$LAST_M" ]; then
        _m=$((LAST_M + 1))
    fi
    SLOT_M=$_m
    SLOT_CS=$((PHASE_CS + _m * STEP_CS + 50))
    EXPECT_S=$((PHASE_S + _m * INTERVAL))
}

# The exact instrument: every run records the hash of the collector that
# produced it, so a file is never attributed to a later or earlier version.
SELF_HASH=$(sha256sum "$0" 2> /dev/null) || SELF_HASH=unavailable
SELF_HASH=${SELF_HASH%% *}
if [ "$FRAC_SLEEP" -eq 1 ]; then
    PACING="wall-clock seconds: each sample aimed 0.5 s into a second, paced on /proc/uptime with a fractional sleep"
else
    PACING="whole seconds (fallback: no fractional sleep or no /proc/uptime)"
fi
STAMPS="awk systime()"
[ "$USE_SYSTIME" -eq 1 ] || STAMPS="date +%s per sample (awk has no usable systime)"
[ -n "$STAMP_EPOCH" ] && STAMPS="substituted (--stamp-epoch, self-test)"
diag "start: collector_sha256=$SELF_HASH host=$HOST source=$SOURCE interval=${INTERVAL}s duration=${DURATION}s pacing: $PACING; timestamps: $STAMPS; expected services: ${EXPECT_SERVICES:-none declared}"
echo "collecting container resources into $OUT (source: $SOURCE, one sample every ${INTERVAL}s, duration: ${DURATION}s, 0 = until SIGTERM)" >&2
echo "pacing: $PACING; diagnostics: $DIAG_FILE; lifecycle: $LIFE_FILE" >&2

# One cgroup sample: one awk process, then a rename of the state file (a
# second, short process). The status decides what happens to the state and
# whether the phase must be recalibrated.
RECAL=0
sample_cgroup() {
    : > "$ERR_FILE"
    awk -v EPOCH="$1" -v USE_SYSTIME="$USE_SYSTIME" -v EXPECT="$2" \
        -v INTERVAL="$INTERVAL" -v HOST="$HOST" \
        -v STATE="$STATE_FILE" -v STATETMP="$STATE_FILE.tmp" \
        -v LIST="$LIST_FILE" -v NAMES="$NAMES_FILE" -v DIAG="$DIAG_FILE" \
        -v LIFE="$LIFE_FILE" -v ERRF="$ERR_FILE" -v UPTIME="$UPTIME_FILE" \
        -v MEMINFO="$MEMINFO_FILE" -v DOCKERROOT="$DOCKER_ROOT" \
        "$AWK_CGROUP" >> "$OUT"
    _rc=$?
    case $_rc in
        0 | 10)
            [ -f "$STATE_FILE.tmp" ] && mv "$STATE_FILE.tmp" "$STATE_FILE"
            ;;
        12)
            [ -f "$STATE_FILE.tmp" ] && mv "$STATE_FILE.tmp" "$STATE_FILE"
            RECAL=1
            ;;
        11)
            rm -f "$STATE_FILE.tmp"
            ;;
        3)
            rm -f "$STATE_FILE.tmp"
            _why=
            read -r _why < "$ERR_FILE" 2> /dev/null || :
            diag "sample $((samples + 1)): ${_why:-the sampler found no usable clock}"
            ;;
        *)
            rm -f "$STATE_FILE.tmp"
            diag "sample $((samples + 1)): the sampler process exited with status $_rc; no rows written for this sample"
            ;;
    esac
    [ "$_rc" -ne 0 ] && new_diag=1
    return 0
}

last_names=
named_ids=
samples=0
effective=
excerpt=0
calibrations=0
phase_ok=0
uptime_cs
started_cs=$UP_CS
last_cal_cs=$((UP_CS - 1000))

while [ "$stop" -eq 0 ]; do
    new_diag=0
    expect=
    # Pace every sample after the first. The first is taken at once; the
    # phase is calibrated after it (and again after a withheld or mis-landed
    # sample), and each later sample is aimed 0.5 s into a wall-clock second.
    if [ "$samples" -ge 1 ]; then
        # A full calibration costs up to a second of clock reads, so after the
        # first one it runs at most once every 10 s; in between, the samples
        # keep the current phase, and the withholding and the counting protect
        # the file. Nothing here ever turns the wall-clock pacing off for good.
        uptime_cs
        if [ "$FRAC_SLEEP" -eq 1 ] && { [ "$phase_ok" -eq 0 ] || { [ "$RECAL" -eq 1 ] && [ $((UP_CS - last_cal_cs)) -ge 1000 ]; }; }; then
            if calibrate; then
                calibrations=$((calibrations + 1))
                phase_ok=1
                LAST_M=
                RECAL=0
                uptime_cs
                last_cal_cs=$UP_CS
                pad2 $((PHASE_CS % 100))
                diag "calibrated: wall second $PHASE_S began at uptime $((PHASE_CS / 100)).$PAD2 s (calibration $calibrations)"
            elif [ "$stop" -eq 0 ]; then
                uptime_cs
                last_cal_cs=$UP_CS
                RECAL=0
                diag "calibration failed: no wall-clock second boundary seen; $([ "$phase_ok" -eq 1 ] && echo "keeping the previous phase" || echo "whole-second pacing") until the next attempt in 10 s"
                new_diag=1
            fi
        fi
        [ "$stop" -eq 0 ] || break
        if [ "$FRAC_SLEEP" -eq 1 ] && [ "$phase_ok" -eq 1 ]; then
            next_slot
            _w=$((SLOT_CS - UP_CS))
            if [ "$_w" -gt 0 ]; then
                pad2 $((_w % 100))
                sleep "$((_w / 100)).$PAD2"
            fi
            LAST_M=$SLOT_M
            expect=$EXPECT_S
        else
            uptime_cs
            _rest=$(((loop_cs + STEP_CS - UP_CS + 99) / 100))
            [ "$_rest" -gt 0 ] && sleep "$_rest"
        fi
        [ "$stop" -eq 0 ] || break
    fi
    uptime_cs
    loop_cs=$UP_CS

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
            cgroup) msg="sampling source: cgroup v2 under $CGROUP_ROOT" ;;
            docker) msg="sampling source: docker stats (no container cgroup under $CGROUP_ROOT)" ;;
            none) msg="no sampling source: no container cgroup and no docker CLI" ;;
        esac
        echo "sample $((samples + 1)): $msg" >&2
        diag "sample $((samples + 1)): $msg"
        effective=$this
    fi

    if [ "$this" = cgroup ]; then
        printf '%s' "$DIRS" > "$LIST_FILE"
        # A docker ps listing only for a container whose own config.v2.json
        # cannot be read, never more than once every 10 s.
        if [ "$USE_DOCKER_NAMES" -eq 1 ] && { [ -z "$last_names" ] || [ $((loop_cs - last_names)) -ge 1000 ]; }; then
            _need=0
            for _id in $IDS; do
                [ -r "$DOCKER_ROOT/containers/$_id/config.v2.json" ] && continue
                case " $named_ids " in
                    *" $_id "*) continue ;;
                esac
                _need=1
                break
            done
            if [ "$_need" -eq 1 ]; then
                if docker ps -a --no-trunc --format '{{.ID}} {{.Names}}' \
                    > "$NAMES_FILE.tmp" 2> /dev/null && [ -s "$NAMES_FILE.tmp" ]; then
                    mv "$NAMES_FILE.tmp" "$NAMES_FILE"
                    named_ids="$named_ids $IDS"
                else
                    rm -f "$NAMES_FILE.tmp"
                fi
                last_names=$loop_cs
            fi
        fi
        _stamp=$STAMP_EPOCH
        [ -z "$_stamp" ] && [ "$USE_SYSTIME" -eq 0 ] && _stamp=$(date +%s)
        sample_cgroup "$_stamp" "$expect"
    elif [ -s "$STATE_FILE" ]; then
        # The containers that were being sampled are gone: one pass over an
        # empty list records their disappearance and clears the state.
        : > "$LIST_FILE"
        _stamp=$STAMP_EPOCH
        [ -z "$_stamp" ] && [ "$USE_SYSTIME" -eq 0 ] && _stamp=$(date +%s)
        sample_cgroup "$_stamp" ""
    fi
    if [ "$this" = docker ]; then
        # --format json is JSON-lines on Docker >= 23; older CLIs accept
        # the equivalent '{{json .}}' template.
        ts=$(date -u '+%Y-%m-%dT%H:%M:%SZ')
        lines=$(docker stats --no-stream --format json 2>/dev/null)
        if [ -z "$lines" ]; then
            lines=$(docker stats --no-stream --format '{{json .}}' 2>/dev/null)
        fi
        if [ -n "$lines" ]; then
            printf '%s\n' "$lines" | awk -v TS="$ts" -v HOST="$HOST" "$AWK_DOCKER" >> "$OUT" \
                || { diag "sample $((samples + 1)): the docker-stats parser failed; no rows"; new_diag=1; }
        else
            echo "$ts docker stats returned nothing; no row" >> "$DIAG_FILE"
            new_diag=1
        fi
    fi

    # A short excerpt reaches stderr (the journal of a transient unit);
    # the diagnostics file holds everything.
    if [ "$excerpt" -eq 0 ] && [ "$new_diag" -eq 1 ]; then
        echo "diagnostics (first lines; all of them are in $DIAG_FILE):" >&2
        grep -v -e ' start: ' -e ' sampling source: ' -e ' calibrated: ' "$DIAG_FILE" | sed -n '1,5p' >&2
        excerpt=1
    fi

    samples=$((samples + 1))
    if [ "$MAX_SAMPLES" -gt 0 ] && [ "$samples" -ge "$MAX_SAMPLES" ]; then
        break
    fi
    uptime_cs
    if [ "$DURATION" -gt 0 ] && [ $(((UP_CS - started_cs) / 100)) -ge "$DURATION" ]; then
        break
    fi
done

# The service inventory, and the closing summary with the measured count of
# seconds that had no sample (kept by awk in the state file).
awk -v EXPECT="$EXPECT_SERVICES" "$AWK_INVENTORY" "$LIFE_FILE" 2> /dev/null | while IFS= read -r _line; do
    diag "$_line"
done
skipped=unknown
if [ -r "$STATE_FILE" ]; then
    while IFS= read -r _line; do
        case $_line in
            "#last"*)
                skipped=${_line##*	}
                break
                ;;
        esac
    done < "$STATE_FILE"
fi
diag "stop: samples=$samples skipped_seconds=$skipped calibrations=$calibrations pacing=$([ "$FRAC_SLEEP" -eq 1 ] && echo wall-clock || echo whole-seconds)"
lines_total=$(grep -c . "$DIAG_FILE" 2> /dev/null || echo 0)
echo "collector stopped after $samples samples ($skipped second(s) without a sample; $lines_total diagnostic line(s) in $DIAG_FILE); output: $OUT" >&2
