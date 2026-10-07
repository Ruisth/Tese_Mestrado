#!/bin/bash
# events_capture.sh - the lifecycle of one run's continuous Docker events
# recorder on the guest (proof_events_recorder.sh, the unit egw-events-RUN_ID),
# in ONE place for the finite proof's driver and for the G3 procedures of the
# runbook (docs/setup/qemu_integrated_gateway.md 6.1: events_start,
# events_stop, events_cleanup, harness_cmd).
#
# SOURCED (proof.sh), it defines the two guest commands and nothing else;
# they read RID, RECORDER and RECORDER_SHA when they are called, and proof.sh
# runs them through its own session machinery (gx_bounded, gx, restore):
#   events_recorder_script  the guest command of the start step
#   events_cleanup_script   the guest command of the cleanup of a unit that is
#                           still running
#
# EXECUTED, it runs one of them over 'ssh egw-tcg' (the alias of runbook 6.1):
#   events_capture.sh start RUN_ID
#       prints what the guest printed - 'run_guest_t0=T0' once the recorder is
#       ready - and exits with the guest's status: 0 ready, 1 not started, 3
#       not ready (the unit then stopped), 255 the guest not reached (whether
#       a unit was started is then unknown: run 'cleanup')
#   events_capture.sh cleanup RUN_ID [KEEP_DIR]
#       stops a unit not shown stopped (any state but inactive or failed)
#       and prints the recorder's lifecycle, whatever KEEP_DIR's state (a
#       repeated cleanup, after the guest was not reached or after an
#       interruption, must still stop the unit); with
#       KEEP_DIR it then copies what the recorder captured there -
#       events.partial.jsonl, lifecycle.txt, start-facts.txt, cli-stderr.txt -
#       a partial capture, never named or read as the run's docker-events.log:
#       only once the unit was shown stopped (KEEP_DIR is not even created
#       otherwise, so the cleanup can be repeated) and only into a KEEP_DIR
#       that does not exist yet (write-once: one that exists is not written);
#       the files are copied beside it and become KEEP_DIR only once all four
#       arrived, so a copy that failed leaves no KEEP_DIR and the cleanup can
#       be repeated then too. Non-zero when the unit could not be shown
#       stopped (a STOP then says it may still run), KEEP_DIR exists or a
#       copy failed.
# A usage or a recorder that cannot be sent answers 2, and nothing is run on
# the guest.
#
# THE START (10a of proof.sh). The run's Docker events are captured as they
# happen, from before the workload and the fault to the docker-events fetch
# (proof_fetch_sut_log.sh), never read back from the daemon's bounded history
# at the end (r03: a history query '--since' the session's start began twenty
# minutes late, the fault's kill and start missing, and exited 0).
# events_recorder_script is the guest command of the start: the run id's
# capture directory /tmp/egw-events-RUN_ID is created write-once with the
# recorder's files already in it (owned by the ssh user, so the readiness line
# can be added and the fetch can read them), the clone's
# proof_events_recorder.sh is written there through a quoted here-document and
# checked against its sha256 (RECORDER_SHA), the guest's boot_id and the docker
# unit's MainPID and start stamp are recorded (start-facts.txt: the fetch
# compares them at the stop, since a daemon restarted under live-restore
# leaves the containers' StartedAt as they were), and the recorder is started
# as the unit egw-events-RUN_ID through 'sudo systemd-run --collect', as the
# harness starts the resource collector (no 'nohup' or 'setsid' applet is
# assumed). Its subscription replays the last REPLAY_S seconds, so a live
# daemon answers at once. It is READY when the capture holds an event and the
# unit is active, polled READY_TRIES one-second steps; ready, the step appends
# 'ready epoch=T0' to the lifecycle record and prints 'run_guest_t0=T0', the
# guest epoch from which the run's window is taken (the two logs' '--since',
# the events' coverage). Not ready, the unit is stopped and the step answers
# 3; a directory that exists, a recorder that is not the clone's or a unit
# that could not be started answer 1. Its parameters are plain assignments
# before QUOTED here-documents (BusyBox ash): nothing is expanded twice.
events_recorder_script() {
    printf "SHA='%s'\nD='/tmp/egw-events-%s'\nUNIT='egw-events-%s'\nREADY_TRIES=30\nREPLAY_S=120\n" "$RECORDER_SHA" "$RID" "$RID"
    cat << 'GUEST_EVENTS_START'
[ ! -e "$D" ] || { echo "STOP: $D exists: the events capture of a run id is write-once; nothing was started"; exit 1; }
mkdir "$D" || { echo "STOP: $D could not be created; nothing was started"; exit 1; }
{ : > "$D/lifecycle.txt" && : > "$D/events.jsonl" && : > "$D/cli.stderr"; } \
    || { echo "STOP: the recorder's files could not be created in $D; nothing was started"; exit 1; }
cat > "$D/recorder.sh" << 'EGW_EVENTS_RECORDER'
GUEST_EVENTS_START
    cat "$RECORDER"
    cat << 'GUEST_EVENTS_START'
EGW_EVENTS_RECORDER
got=$(sha256sum "$D/recorder.sh" | cut -d' ' -f1)
echo "recorder_sha256=$got"
[ "$got" = "$SHA" ] || { echo "STOP: the recorder written on the guest is not the clone's (sha256 $got, expected $SHA); nothing was started"; exit 1; }
{
    echo "boot_id=$(cat /proc/sys/kernel/random/boot_id)"
    systemctl show docker -p MainPID -p ExecMainStartTimestampMonotonic
} > "$D/start-facts.txt" || { echo "STOP: the boot and docker facts could not be recorded; nothing was started"; exit 1; }
sed 's/^/start_fact_/' "$D/start-facts.txt"
now=$(date +%s) || { echo "STOP: the guest clock could not be read; nothing was started"; exit 1; }
since=$((now - REPLAY_S))
echo "recorder_since_guest_epoch=$since"
sudo systemd-run --unit "$UNIT" --collect sh "$D/recorder.sh" "$D" "$since" \
    || { echo "STOP: the recorder unit $UNIT could not be started"; exit 1; }
n=0
until [ -s "$D/events.jsonl" ] && systemctl is-active -q "$UNIT"; do
    n=$((n + 1))
    if [ "$n" -gt "$READY_TRIES" ]; then
        echo "NOT READY: the recorder unit $UNIT did not show a live subscription within $READY_TRIES one-second steps (unit $(systemctl is-active "$UNIT" 2> /dev/null), $(wc -c < "$D/events.jsonl") bytes captured); its record follows, and the unit is stopped"
        cat "$D/lifecycle.txt"
        head -n 20 "$D/cli.stderr"
        sudo systemctl stop "$UNIT" 2> /dev/null
        echo "unit_state_after_stop=$(systemctl is-active "$UNIT" 2> /dev/null)"
        exit 3
    fi
    sleep 1
done
t0=$(date +%s) || { echo "STOP: the guest clock could not be read after readiness"; sudo systemctl stop "$UNIT"; exit 1; }
echo "ready epoch=$t0 events_bytes=$(wc -c < "$D/events.jsonl") unit=active" >> "$D/lifecycle.txt"
cat "$D/lifecycle.txt"
echo "run_guest_t0=$t0"
GUEST_EVENTS_START
}
# events_cleanup_script: the guest command of the cleanup, run by proof.sh's
# restoration and by the host command below. Only 'inactive' and 'failed' are
# a unit already stopped (a transient unit that no longer exists answers
# 'inactive', with a non-zero status); any other answer - active, a state
# between (activating, deactivating, reloading) or none at all ('unknown') -
# is a unit not shown stopped by the docker-events fetch (the run ended
# before it, or it failed), so its capture is not the run's: it is stopped
# and its state read again, and the step answers non-zero unless it is then
# 'inactive' or 'failed' (it may still run). Its lifecycle record is printed
# into the console record (the capture itself stays on the guest, in its
# directory).
events_cleanup_script() {
    printf "D='/tmp/egw-events-%s'\nUNIT='egw-events-%s'\n" "$RID" "$RID"
    cat << 'GUEST_EVENTS_CLEANUP'
state=$(systemctl is-active "$UNIT" 2> /dev/null)
echo "unit_state_before_cleanup=${state:-unknown}"
rc=0
case "$state" in
    inactive | failed) ;;
    *)
        echo "cleanup_stop_requested_guest_epoch=$(date +%s)"
        sudo systemctl stop "$UNIT" || rc=1
        state=$(systemctl is-active "$UNIT" 2> /dev/null)
        echo "unit_state_after_cleanup=${state:-unknown}"
        case "$state" in
            inactive | failed) ;;
            *) rc=1 ;;
        esac
        ;;
esac
if [ -d "$D" ]; then
    echo "--- the recorder's lifecycle record ($D/lifecycle.txt; its capture stays in $D)"
    cat "$D/lifecycle.txt" 2> /dev/null
    echo "events_lines=$(wc -l < "$D/events.jsonl" 2> /dev/null)"
    echo "cli_stderr_bytes=$(wc -c < "$D/cli.stderr" 2> /dev/null)"
fi
exit $rc
GUEST_EVENTS_CLEANUP
}

# --- the host command ---------------------------------------------------------
# Only when executed: sourced, the file defines the two functions above and
# returns here.
[ "${BASH_SOURCE[0]}" = "$0" ] || return 0
set -u
# capture_stop MESSAGE: a usage or a recorder that cannot be sent (2): nothing
# was run on the guest.
capture_stop() {
    echo "STOP: events_capture: $1" >&2
    exit 2
}
USAGE="usage: events_capture.sh start RUN_ID, or events_capture.sh cleanup RUN_ID [KEEP_DIR]"
[ "$#" -ge 2 ] || capture_stop "$USAGE: nothing was run on the guest"
ACTION=$1
RID=$2
case "$ACTION" in
    start) [ "$#" -eq 2 ] || capture_stop "$USAGE: nothing was run on the guest" ;;
    cleanup) [ "$#" -le 3 ] || capture_stop "$USAGE: nothing was run on the guest" ;;
    *) capture_stop "'$ACTION' is not start or cleanup: nothing was run on the guest" ;;
esac
case "$RID" in
    '' | *[!A-Za-z0-9._-]* | . | ..) capture_stop "RUN_ID '$RID' is not a plain run id: nothing was run on the guest" ;;
esac
if [ "$ACTION" = start ]; then
    # The recorder travels to the guest inside a quoted here-document that
    # ends at a line of its own, and is checked there against this sha256:
    # a file that cannot be read, or that holds that line, is refused here,
    # as proof.sh refuses it.
    RECORDER=$(dirname "$0")/proof_events_recorder.sh
    RECORDER_SHA=$(sha256sum "$RECORDER" 2> /dev/null | cut -d' ' -f1)
    [[ $RECORDER_SHA =~ ^[0-9a-f]{64}$ ]] || capture_stop "the Docker events recorder $RECORDER cannot be read: nothing was started"
    ! grep -qx 'EGW_EVENTS_RECORDER' "$RECORDER" \
        || capture_stop "the Docker events recorder $RECORDER holds the line that ends its here-document on the guest: nothing was started"
    ssh egw-tcg "$(events_recorder_script)"
    exit $?
fi
KEEP=${3:-}
ssh egw-tcg "$(events_cleanup_script)"
rc=$?
# What the recorder captured is kept only once the unit was shown stopped: a
# partial capture, under names that are never the run's docker-events.log.
[ "$rc" = 0 ] || { echo "STOP: events_capture: the unit egw-events-$RID was not shown stopped (exit $rc) - it may still run on the guest${KEEP:+; nothing was copied to $KEEP}: repeat the cleanup until it ends 0" >&2; exit "$rc"; }
[ -n "$KEEP" ] || exit 0
[ ! -e "$KEEP" ] || { echo "STOP: events_capture: $KEEP exists - NOT overwritten; the unit's cleanup ran above, nothing was copied" >&2; exit 1; }
# The files are copied beside KEEP and the copy becomes KEEP only once all
# four arrived: KEEP holds the whole partial capture or does not exist, so a
# cleanup whose copy failed can be repeated (the guest's files no longer
# change once the unit is shown stopped).
STAGE=
mkdir -p "$(dirname "$KEEP")" && STAGE=$(mktemp -d "$KEEP.copy.XXXXXX") \
    || { echo "STOP: events_capture: $KEEP could not be created - the partial capture was NOT kept" >&2; exit 1; }
# An empty staging directory is removed at the end; one that holds files a
# failed copy did bring back is kept, named as incomplete in the STOP (never
# as KEEP), so what reached the host is not thrown away.
trap 'rmdir "$STAGE" 2> /dev/null' EXIT
kept=0
for pair in events.jsonl:events.partial.jsonl lifecycle.txt:lifecycle.txt start-facts.txt:start-facts.txt \
    cli.stderr:cli-stderr.txt; do
    if scp -q "egw-tcg:/tmp/egw-events-$RID/${pair%%:*}" "$STAGE/${pair#*:}"; then
        kept=$((kept + 1))
    else
        echo "events_capture: /tmp/egw-events-$RID/${pair%%:*} was not copied from the guest" >&2
        rc=1
    fi
done
if [ "$rc" = 0 ] && [ ! -e "$KEEP" ] && mv -T "$STAGE" "$KEEP"; then
    echo "events_capture: cleanup: the recorder's 4 files kept in $KEEP (a partial capture, not the run's)"
    exit 0
fi
incomplete=""
[ "$kept" = 0 ] || incomplete=", kept INCOMPLETE in $STAGE (not the run's capture, not $KEEP)"
echo "STOP: events_capture: $kept of the recorder's 4 files copied$incomplete; NONE kept in $KEEP - repeat the cleanup before the guest powers off (its capture stays in /tmp/egw-events-$RID until then)" >&2
exit 1
