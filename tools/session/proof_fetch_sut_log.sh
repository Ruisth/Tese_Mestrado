#!/bin/bash
# The finite proof of ADR 0011: the three SUT log fetches of the harness
# (--fetch-broker-log-cmd, --fetch-controller-log-cmd,
# --fetch-docker-events-cmd; run.py SUT_LOG_FETCH_FLAGS), run last, after the
# drain, so that they cover it, and each expected to write its file under
# logs/sut/ (run.py SUT_LOG_FILES) before the seal. The harness runs this
# file as one argv split without a shell (shlex.split, run.py
# execute_collector_hook).
# Usage: proof_fetch_sut_log.sh broker|controller DEST RUN_T0
#        proof_fetch_sut_log.sh docker-events DEST RUN_T0 RUN_ID [EXPECTED]
#   KIND   broker         the broker's log, as test 5 collects it (runbook):
#                         'docker compose ... logs --no-color --timestamps
#                         mosquitto', bounded to the run (below)
#          controller     the controller container's log, 'docker logs
#                         --timestamps egw-controller-1', stderr merged on the
#                         guest: the controller logs its JSON lines to stderr
#                         (logging_config.py); bounded to the run (below)
#          docker-events  the run's continuous Docker events capture: the
#                         recorder unit egw-events-RUN_ID that proof.sh
#                         started before the workload and the fault
#                         (proof_events_recorder.sh) is stopped here, its
#                         files are fetched and its coverage is judged
#                         (events_coverage.py); never a history query
#   DEST   the file the harness expects (<run dir>/logs/sut/broker.log,
#          controller.log or docker-events.log)
#   RUN_T0 the guest epoch, in whole seconds, from which the run's window is
#          taken: the instant proof.sh recorded when the events recorder was
#          found ready, before tunnel-ready, the harness, the twin snapshot
#          before the run, the load and the fault (instants.run_guest_t0)
#   RUN_ID the harness run id ({run_id}): it names the recorder's unit and
#          its guest directory /tmp/egw-events-RUN_ID (docker-events only)
#   EXPECTED  the Docker actions of egw-controller-1 the run's scenario
#          generates, comma-separated (the proof's fault: kill,die,start);
#          given only for a scenario that issues a fault, never for a
#          fault-free run, and then required within [RUN_T0, the stop]
#
# THE LOG WAS READ, OR IT WAS NOT. The output is written to DEST.tmp and
# becomes DEST only when the ssh session ended 0 AND the output is not empty:
# a non-zero status or an empty output says the log was NOT read on the
# guest, and what that log would show is then neither observed nor excluded
# (the rule of config_identity's broker-log read, runbook 6.1, review of
# 2026-09-25 item D2). The hook then prints the last 400 bytes of whatever
# the failed read answered (the controller read merges the daemon's error
# into its output, so that is where its reason is), removes the temporary
# file, prints a STOP line and exits 1, so that DEST is absent: a fetch that
# exits 0 without its file is a validity reason for the harness (ADR 0011
# item 18), and an empty DEST would be read as a log that showed nothing. A
# read that answered nothing has nothing to excerpt. On success the line
# count and the sha256 of DEST are printed, so the manifest's hook record and
# the capsule's SHA256SUMS can be read against each other. The harness keeps
# this hook's full stdout and stderr as logs/sut/hook-<hook>.stdout.txt and
# .stderr.txt, so the STOP line stays in the capsule.
#
# THE TWO LOGS ARE THE RUN'S, NOT THE CONTAINER'S WHOLE HISTORY. A container's
# log spans every session it has lived through (r03's controller.log held
# 11,862 lines, 3,934 of them of its session; its broker.log began six days
# earlier), and the controller's received_monotonic_ns of another boot is not
# comparable with this one's: an old A5 line on the same device could be
# read as this run's. Both reads are therefore bounded on the GUEST clock:
# '--since RUN_T0' and '--until UNTIL', UNTIL being the guest's own 'date +%s'
# read by this hook just before the read and printed. Before the read, the
# hook records what the bound leaves out, without transferring it: the line
# count and the sha256 of what 'docker logs --until RUN_T0' answers on the
# guest (the exclusion witness). After it, the HOST checks every line it
# received - a leading ESC[2K (compose's line erase, present in r03's broker
# log) and the broker's 'mosquitto-1  | ' prefix stripped - for an RFC 3339
# UTC stamp whose second lies in [RUN_T0, UNTIL]: '--since' alone is no
# evidence of the bound (r03's events read had one), so a read that answered
# a line outside the window, or a line without a stamp, is a read NOT bounded
# to the run, and fails as a failed read does (DEST absent, exit 1). One
# exception follows the daemon's own rule: since Docker 23 the log reader
# applies '--since' only until the first line at or after it and then passes
# every later line ("message timestamps might not be monotonic"), and the
# guest's wall clock steps back by 1-3 s about every 30 s (r03's controller
# log shows 14 such steps in seven minutes). A line stamped before RUN_T0 by
# no more than CLOCK_STEP_BAND_S (3 s, the band events_coverage.py and
# proof.sh use for the same clock) and AFTER a line inside the window is
# this run's, stepped back: it is kept and counted apart
# (stepped_back_before_since=N), never read as a line of an earlier session.
# A line before RUN_T0 that comes first, or older than the band, still
# fails the read. The offending line is named by its number and stamp only,
# never excerpted: its content is what the bound keeps out of the capsule. The bounds, the first
# and last stamps and the witness are printed on stdout (a witness whose
# own read did not end 0 is printed 'unknown', never the count of an error
# message). Converting RUN_T0 and
# UNTIL to UTC text on the host is arithmetic on the guest's numbers, never a
# reading of the host clock.
#
# THE EVENTS WERE CAPTURED THROUGHOUT, OR THEY WERE NOT. On the guest the
# hook asks for the stop of the recorder unit, recording the guest epoch of
# that request (the window's end), the unit's state before it, the guest's
# boot_id and the docker daemon's MainPID and start stamp; it waits (up to 45
# one-second steps) for an event stamped after the second of the request -
# the closing witness, which shows the subscription live to the window's
# end; then 'sudo systemctl stop' and the unit's state after it. It then
# copies the recorder's four files (events.jsonl, lifecycle.txt,
# start-facts.txt, cli.stderr) one by one and hands them, with the stop
# record, to events_coverage.py (rules R1-R7). DEST (JSON lines, as the CLI
# wrote them) is written only when the checker says 'complete', and the
# stop, every transfer and the checker all ended 0. Anything else - a
# coverage 'incomplete' or 'unknown', a stop or a transfer that failed - is
# a capture NOT shown complete: DEST is absent, the hook exits 1, and what
# was captured is kept as docker-events.partial.jsonl, so that nothing
# reads a partial capture as the run's. Whatever the ending, the records of
# the capture are kept beside it, write-once: docker-events.lifecycle.txt,
# .start-facts.txt, .cli-stderr.txt, .stop.txt and .coverage.txt (the
# verdict, the requested interval on the guest clock, the provenance and
# one line per rule). The host's own instants of the fetch are the
# manifest's hook record, never written into these files.
#
# The hook inherits the environment of the driver's host step (the venv on
# PATH, the .env exported, EGW_CLONE) but not the helper functions of runbook
# 6.1, which are defined by the deployed helper file: it sources that file
# itself, as the other proof hooks do, and reaches the guest as they do,
# through the 'egw-tcg' alias of ~/.ssh/config (runbook 6.1 fetch,
# config_identity). A helper file that cannot be loaded means the hook never
# reached what it was to run, and it answers 97 (EXIT_NOT_REACHED of
# common.sh, written literally here because common.sh is not sourced).
set -u

# hook_stop CODE MESSAGE: print the STOP line and end with CODE.
hook_stop() {
    echo "STOP: proof_fetch_sut_log: $2" >&2
    exit "$1"
}

USAGE="usage: proof_fetch_sut_log.sh broker|controller DEST RUN_T0, or proof_fetch_sut_log.sh docker-events DEST RUN_T0 RUN_ID [EXPECTED]"
[ "$#" -ge 3 ] || hook_stop 2 "$USAGE"
KIND=$1
DEST=$2
SINCE=$3
case "$KIND" in
    broker | controller) [ "$#" -eq 3 ] || hook_stop 2 "$USAGE: nothing was read" ;;
    docker-events) [ "$#" -eq 4 ] || [ "$#" -eq 5 ] || hook_stop 2 "$USAGE: nothing was read" ;;
    *) hook_stop 2 "KIND '$KIND' is not broker, controller or docker-events: nothing was read" ;;
esac
[ -n "$DEST" ] || hook_stop 2 "DEST is empty: nothing was read"
case "$SINCE" in
    '' | *[!0-9]*) hook_stop 2 "RUN_T0 '$SINCE' is not a whole number of seconds (the guest epoch of the run's start): nothing was read" ;;
esac
SUTDIR=$(dirname "$DEST")
KEEP=()
if [ "$KIND" = docker-events ]; then
    RID=$4
    EXPECTED=${5:-}
    case "$RID" in
        '' | *[!A-Za-z0-9._-]* | . | ..) hook_stop 2 "RUN_ID '$RID' is not a plain run id: nothing was read" ;;
    esac
    [[ -z $EXPECTED || $EXPECTED =~ ^[a-z_]+(,[a-z_]+)*$ ]] \
        || hook_stop 2 "EXPECTED '$EXPECTED' is not a comma-separated list of Docker actions: nothing was read"
    # The records kept beside DEST, write-once like it.
    KEEP=(lifecycle.txt start-facts.txt cli-stderr.txt stop.txt coverage.txt partial.jsonl)
fi
[ ! -e "$DEST" ] || hook_stop 1 "$DEST exists - NOT overwritten; nothing was read"
for kept in "${KEEP[@]}"; do
    [ ! -e "$SUTDIR/docker-events.$kept" ] || hook_stop 1 "$SUTDIR/docker-events.$kept exists - NOT overwritten; nothing was read"
done

HELPERS=$HOME/egw-tcg/itest-helpers.sh
# The helper file is written for a shell without 'set -u' (it expands the
# variables of .env as they stand), so it is loaded with that option off.
set +u
if [ ! -r "$HELPERS" ]; then
    hook_stop 97 "the helper file $HELPERS is not readable: the hook never reached the guest, the $KIND log was not read"
fi
# shellcheck disable=SC1090
. "$HELPERS" || hook_stop 97 "the helper file $HELPERS could not be loaded: the hook never reached the guest, the $KIND log was not read"
set -u

mkdir -p "$SUTDIR" || hook_stop 1 "the directory of $DEST could not be created: nothing was read"
# iso EPOCH: a guest epoch as UTC text (arithmetic, never a clock reading).
iso() { date -u -d "@$1" +%Y-%m-%dT%H:%M:%SZ; }

# --- the docker events: stop the recorder, fetch it, judge its coverage ---------
if [ "$KIND" = docker-events ]; then
    D=/tmp/egw-events-$RID
    UNIT=egw-events-$RID
    WORK=$(mktemp -d "${TMPDIR:-/tmp}/proof_fetch_events.XXXXXX") || hook_stop 1 "no temporary directory on the host: nothing was read"
    trap 'rm -rf "$WORK"' EXIT
    # The stop, on the guest (BusyBox ash): the parameters as plain
    # assignments before a QUOTED here-document, so nothing inside is
    # expanded twice. Its stdout is the stop record; its stderr reaches this
    # hook's stderr, and so the capsule.
    STOP_SCRIPT="$(printf "D='%s'\nUNIT='%s'\nWITNESS_S=45\n" "$D" "$UNIT")
$(cat << 'GUEST_STOP'
[ -d "$D" ] || { echo "STOP: $D is not on the guest: no events recorder was started for this run id" >&2; exit 3; }
t1=$(date +%s) || { echo "STOP: the guest clock could not be read: the recorder was NOT stopped" >&2; exit 3; }
echo "stop_requested_guest_epoch=$t1"
state=$(systemctl is-active "$UNIT" 2> /dev/null)
echo "unit_state_before_stop=${state:-unknown}"
echo "boot_id=$(cat /proc/sys/kernel/random/boot_id 2> /dev/null)"
systemctl show docker -p MainPID -p ExecMainStartTimestampMonotonic 2> /dev/null
rc=0
if [ "$state" = active ]; then
    # The closing witness: an event stamped after the second of the request
    # (nanoseconds compared by stripping nine digits, never by arithmetic).
    witness=no
    n=0
    while [ "$n" -lt "$WITNESS_S" ]; do
        t=$(tail -n 20 "$D/events.jsonl" 2> /dev/null | sed -n 's/.*"timeNano":\([0-9][0-9]*\).*/\1/p' | tail -n 1)
        t=${t%?????????}
        if [ -n "$t" ] && [ "$t" -gt "$t1" ]; then
            witness=yes
            break
        fi
        n=$((n + 1))
        sleep 1
    done
    echo "closing_witness_seen=$witness"
    sudo systemctl stop "$UNIT" || { echo "STOP: 'systemctl stop $UNIT' failed" >&2; rc=1; }
fi
after=$(systemctl is-active "$UNIT" 2> /dev/null)
echo "unit_state_after_stop=${after:-unknown}"
exit $rc
GUEST_STOP
)"
    ssh egw-tcg "$STOP_SCRIPT" > "$WORK/stop.txt"
    stop_rc=$?
    host_problems=()
    [ "$stop_rc" -eq 0 ] || host_problems+=("the stop of the recorder unit $UNIT on the guest exited $stop_rc (ssh egw-tcg)")
    for f in events.jsonl lifecycle.txt start-facts.txt cli.stderr; do
        scp -q "egw-tcg:$D/$f" "$WORK/$f" || host_problems+=("$D/$f was not copied from the guest")
    done
    if [ "${#host_problems[@]}" -eq 0 ]; then
        python3 "$(dirname "$0")/events_coverage.py" "$WORK" --run-t0 "$SINCE" ${EXPECTED:+--expected "$EXPECTED"} \
            > "$WORK/coverage.txt"
        cov_rc=$?
    else
        # Not judged: what the checker would read is not all here, or the stop
        # was not shown to have happened.
        cov_rc=2
        {
            echo "coverage=unknown"
            echo "requested_since_guest_epoch=$SINCE"
            echo "requested_since_utc=$(iso "$SINCE")"
            echo "expected=${EXPECTED:-none}"
            for p in "${host_problems[@]}"; do echo "reason=$p: the capture was not judged"; done
        } > "$WORK/coverage.txt"
    fi
    coverage=$(sed -n '1s/^coverage=//p' "$WORK/coverage.txt")
    [ -n "$coverage" ] || coverage=unknown
    # The records of the capture, whatever its ending.
    for pair in lifecycle.txt:lifecycle.txt start-facts.txt:start-facts.txt cli.stderr:cli-stderr.txt \
        stop.txt:stop.txt coverage.txt:coverage.txt; do
        [ ! -f "$WORK/${pair%%:*}" ] || mv "$WORK/${pair%%:*}" "$SUTDIR/docker-events.${pair#*:}" \
            || host_problems+=("the record ${pair#*:} could not be kept")
    done
    if [ "$cov_rc" -eq 0 ] && [ "$coverage" = complete ] && [ "${#host_problems[@]}" -eq 0 ]; then
        mv "$WORK/events.jsonl" "$DEST" || hook_stop 1 "the capture was shown complete but $DEST could not be written"
        lines=$(wc -l < "$DEST") || lines=unreadable
        bytes=$(wc -c < "$DEST") || bytes=unreadable
        sha=$(sha256sum "$DEST" | cut -d ' ' -f 1) || sha=unreadable
        echo "proof_fetch_sut_log: docker-events: coverage=complete from RUN_T0 $SINCE ($(iso "$SINCE")) to the stop request; expected=${EXPECTED:-none}; the rules are in $SUTDIR/docker-events.coverage.txt"
        echo "proof_fetch_sut_log: docker-events: $lines line(s), $bytes bytes, sha256 $sha, written to $DEST"
        exit 0
    fi
    kept_as=""
    if [ -f "$WORK/events.jsonl" ] && mv "$WORK/events.jsonl" "$SUTDIR/docker-events.partial.jsonl"; then
        kept_as="; what was captured is kept as $SUTDIR/docker-events.partial.jsonl"
    fi
    for p in "${host_problems[@]}"; do echo "proof_fetch_sut_log: docker-events: $p" >&2; done
    [ ! -f "$SUTDIR/docker-events.coverage.txt" ] || sed -n 's/^reason=/proof_fetch_sut_log: docker-events: /p' "$SUTDIR/docker-events.coverage.txt" >&2
    hook_stop 1 "the docker-events capture is NOT shown complete (coverage=$coverage, checker exit $cov_rc): what the run's window held is neither observed nor excluded - $DEST was NOT written$kept_as"
fi

# --- the two logs, bounded to the run on the guest clock ----------------------
# The guest command of each kind. Every one runs under the guest's own shell
# (BusyBox ash) and holds no bashism; the controller's '2>&1' merges the
# container's stderr stream on the guest, where 'docker logs' replays it,
# so ssh's own stderr stays apart and reaches this hook's stderr. '--since'
# and '--until' take the guest epochs as whole seconds (to verify on the
# guest's docker 25.0.9 and compose 2.26.0 before the session, as design
# flag V-3 was).
case "$KIND" in
    broker)
        READ='cd /opt/egw/deployment && docker compose --env-file .env --env-file images.lock.env logs --no-color --timestamps'
        TARGET=mosquitto
        MERGE='' ;;
    controller)
        READ='docker logs --timestamps'
        TARGET=egw-controller-1
        MERGE=' 2>&1' ;;
esac
# UNTIL, the guest's own clock now, and the exclusion witness: what the bound
# leaves out, counted and hashed on the guest, nothing transferred. The
# witness reads the same stream as the main read ($MERGE: the controller's
# two streams merged on the guest, the broker's compose stderr left apart),
# and each of its two reads writes its own exit status to a small file on
# the guest (no pipefail is relied on): a witness that did not end 0 is
# reported 'unknown', never the count and hash of an error message.
BOUNDS=$(ssh egw-tcg "u=\$(date +%s) || exit 3
echo \"until_guest_epoch=\$u\"
w=/tmp/egw-excluded-witness.\$\$
echo \"excluded_before_since_lines=\$({ $READ --until $SINCE $TARGET$MERGE; echo \$? > \$w.1; } | wc -l)\"
echo \"excluded_sha256=\$({ $READ --until $SINCE $TARGET$MERGE; echo \$? > \$w.2; } | sha256sum | cut -d' ' -f1)\"
echo \"excluded_read_rc=\$(cat \$w.1 2> /dev/null || echo unread),\$(cat \$w.2 2> /dev/null || echo unread)\"
rm -f \$w.1 \$w.2")
bounds_rc=$?
UNTIL=$(printf '%s\n' "$BOUNDS" | sed -n 's/^until_guest_epoch=//p' | head -n 1)
EXCLUDED_LINES=$(printf '%s\n' "$BOUNDS" | sed -n 's/^excluded_before_since_lines=//p' | head -n 1 | tr -d ' ')
EXCLUDED_SHA=$(printf '%s\n' "$BOUNDS" | sed -n 's/^excluded_sha256=//p' | head -n 1)
EXCLUDED_RC=$(printf '%s\n' "$BOUNDS" | sed -n 's/^excluded_read_rc=//p' | head -n 1 | tr -d ' ')
if [ "$EXCLUDED_RC" != "0,0" ]; then
    EXCLUDED_LINES=unknown
    EXCLUDED_SHA=unknown
fi
case "$UNTIL" in
    '' | *[!0-9]*) hook_stop 1 "the $KIND log was NOT read on the guest (the guest clock that bounds the read was not read: ssh egw-tcg exit $bounds_rc): what it would show is neither observed nor excluded - $DEST was NOT written" ;;
esac
[ "$UNTIL" -ge "$SINCE" ] \
    || hook_stop 1 "the $KIND log was NOT read on the guest (the guest clock now, $UNTIL, precedes RUN_T0 $SINCE: the window is empty or the guest clock is not consistent): what it would show is neither observed nor excluded - $DEST was NOT written"
SINCE_ISO=$(iso "$SINCE")
UNTIL_ISO=$(iso "$UNTIL")

TMP=$DEST.tmp
: > "$TMP" || hook_stop 1 "$TMP could not be written: nothing was read"
ssh egw-tcg "$READ --since $SINCE --until $UNTIL $TARGET$MERGE" > "$TMP"
rc=$?
bytes=$(wc -c < "$TMP" 2> /dev/null) || bytes=unreadable
if [ "$rc" -ne 0 ] || [ "$bytes" = unreadable ] || [ "$bytes" -eq 0 ]; then
    if [ "$bytes" != unreadable ] && [ "$bytes" -gt 0 ]; then
        # A failed read that answered something: the controller read merges
        # the daemon's stderr on the guest, so its reason ('No such
        # container', 'permission denied') is in the output and nowhere
        # else. The last 400 bytes go to this hook's stderr before the file
        # does, so that the capsule (hook-<hook>.stderr.txt, the manifest's
        # stderr_tail) says what the guest answered, and the STOP line
        # stays the last line.
        echo "proof_fetch_sut_log: the $KIND read exited $rc after answering $bytes bytes; the last of them (up to 400) follow:" >&2
        tail -c 400 "$TMP" >&2
        [ -z "$(tail -c 1 "$TMP")" ] || echo >&2
    fi
    rm -f "$TMP"
    hook_stop 1 "the $KIND log was NOT read on the guest (ssh egw-tcg exit $rc, $bytes bytes): what it would show is neither observed nor excluded - $DEST was NOT written"
fi
# Every line within [RUN_T0, UNTIL], by the second of its stamp (RFC 3339
# UTC compares as text).
CLOCK_STEP_BAND_S=3
BAND_ISO=$(iso "$((SINCE - CLOCK_STEP_BAND_S))")
CHECK=$(awk -v since="${SINCE_ISO%Z}" -v band="${BAND_ISO%Z}" -v until="${UNTIL_ISO%Z}" -v kind="$KIND" -v esc="$(printf '\033')" '
{
    line = $0
    if (substr(line, 1, 4) == esc "[2K") line = substr(line, 5)
    if (kind == "broker") sub(/^mosquitto-[0-9]+ *\| /, "", line)
    if (line !~ /^[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]T[0-9][0-9]:[0-9][0-9]:[0-9][0-9](\.[0-9]+)?Z /) {
        unstamped++
        if (!fu) fu = NR
        next
    }
    stamp = substr(line, 1, index(line, " ") - 1)
    second = substr(line, 1, 19)
    # Before RUN_T0 but after a line inside the window, within the clock
    # step band: the daemon passes it (its since check ends at the first
    # line at or after since), and it is a line of this run stepped back.
    if (second < since && first != "" && second >= band) {
        stepped++
        last = stamp
        next
    }
    if (second < since || second > until) {
        outside++
        if (!fo) { fo = NR; fos = stamp }
        next
    }
    if (first == "") first = stamp
    last = stamp
}
END {
    printf "lines=%d outside=%d unstamped=%d stepped=%d first=%s last=%s first_outside_line=%s first_outside_stamp=%s first_unstamped_line=%s\n",
        NR, outside + 0, unstamped + 0, stepped + 0, (first == "" ? "null" : first), (last == "" ? "null" : last),
        (fo ? fo : "null"), (fos == "" ? "null" : fos), (fu ? fu : "null")
}' "$TMP")
check_rc=$?
field() { printf '%s\n' "$CHECK" | tr ' ' '\n' | sed -n "s/^$1=//p" | head -n 1; }
OUTSIDE=$(field outside)
UNSTAMPED=$(field unstamped)
BOUNDS_LINE="since_guest_epoch=$SINCE ($SINCE_ISO) until_guest_epoch=$UNTIL ($UNTIL_ISO) first=$(field first) last=$(field last) excluded_before_since_lines=${EXCLUDED_LINES:-unknown} excluded_sha256=${EXCLUDED_SHA:-unknown} outside=${OUTSIDE:-unknown} unstamped=${UNSTAMPED:-unknown} stepped_back_before_since=$(field stepped) excluded_read_rc=${EXCLUDED_RC:-unread}"
if [ "$check_rc" -ne 0 ] || [ "$OUTSIDE" != 0 ] || [ "$UNSTAMPED" != 0 ]; then
    echo "proof_fetch_sut_log: the $KIND read answered $(field lines) line(s) ($bytes bytes), of which ${OUTSIDE:-an unknown number} lie outside [$SINCE_ISO, $UNTIL_ISO] (first: line $(field first_outside_line), stamp $(field first_outside_stamp)) and ${UNSTAMPED:-an unknown number} carry no timestamp (first: line $(field first_unstamped_line)); the lines themselves are not excerpted" >&2
    rm -f "$TMP"
    hook_stop 1 "the $KIND log was NOT read as bounded to the run [$SINCE_ISO, $UNTIL_ISO] on the guest: what the run's window would show is neither observed nor excluded - $DEST was NOT written"
fi
mv "$TMP" "$DEST" || { rm -f "$TMP"; hook_stop 1 "the $KIND log was read ($bytes bytes) but $DEST could not be written"; }
lines=$(wc -l < "$DEST") || lines=unreadable
sha=$(sha256sum "$DEST" | cut -d ' ' -f 1) || sha=unreadable
echo "proof_fetch_sut_log: $KIND: bounds $BOUNDS_LINE"
echo "proof_fetch_sut_log: $KIND: $lines line(s), $bytes bytes, sha256 $sha, written to $DEST"
