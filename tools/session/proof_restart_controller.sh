#!/bin/bash
# The finite proof of ADR 0011: the fault. "At t+150 s, SIGKILL of the
# controller's container followed by a start, issued through the harness
# restart hook (--restart-cmd, --restart-at-s) so that both instants are in
# the manifest" (ADR 0011, The finite proof). The harness runs this file as
# one argv split without a shell (shlex.split, run.py _execute_restart_cmd)
# and keeps in the manifest's restart record its exit status, the last 500
# characters of its stderr and the host instants around it (started_utc,
# started_monotonic_ns, finished_utc). Everything else this hook observes is
# written to the record below, which the driver packages with the snapshots.
# Usage: proof_restart_controller.sh RUN_ID
#
# WHAT IT RECORDS, AND IN WHICH ORDER. $P/RUN_ID.restart.txt, write-once: a
# run id gets one fault, and a record that already exists stops the hook
# before anything is killed. The guest clock (epoch and UTC) and the
# controller container's id, StartedAt and status are read on the guest and
# written BEFORE the fault is dispatched, so that a hook which dies in the
# fault still leaves the record of what it found and of what it issued
# (intent before dispatch, as persistence.sh and broker_measure.sh keep it);
# a container that could not be read means nothing is killed. Then the fault
# itself, one ssh session:
#   cd /opt/egw/deployment && docker kill --signal=KILL egw-controller-1 \
#     && docker compose --env-file .env --env-file images.lock.env start controller
# then the same reading again. The two guest instants are printed on stderr,
# which the manifest's stderr_tail keeps. A 'docker kill' followed by a
# 'start' keeps the container OBJECT: the same id with a later StartedAt is
# what the driver's restart-shown step expects (contrast persistence.sh,
# whose 'down'/'up -d' expects new ids). The record notes whether the id was
# the same and whether StartedAt moved, as observations; the verdict that
# the restart was shown belongs to the driver, which reads its own
# containers-after record.
#
# Design flag V-1 (to record before the session, not decided here): the exact
# command - 'docker kill' against 'docker compose kill' - and whether the
# stack's 'restart: unless-stopped' policy (compose.yaml) starts the
# container again by itself before the explicit 'start' reaches it; a
# 'start' of a container the policy already started is a no-op that exits
# 0, so the sequence ends with a started container either way, and the
# restart-shown step observes the effect whatever the command did.
#
# The hook inherits the environment of the driver's host step (the venv on
# PATH, the .env exported, EGW_CLONE) but not the helper functions of runbook
# 6.1, which are defined by the deployed helper file: it sources that file
# itself for $P, the runbook's prefix directory, and reaches the guest as the
# runbook helpers do, through the 'egw-tcg' alias of ~/.ssh/config. A helper
# file that cannot be loaded means the hook never reached what it was to run,
# and it answers 97 (EXIT_NOT_REACHED of common.sh, written literally here
# because common.sh is not sourced): nothing is killed.
set -u

# hook_stop CODE MESSAGE: print the STOP line and end with CODE.
hook_stop() {
    echo "STOP: proof_restart_controller: $2" >&2
    exit "$1"
}

[ "$#" -eq 1 ] || hook_stop 2 "usage: proof_restart_controller.sh RUN_ID; nothing was killed"
RID=$1
case "$RID" in
    '' | *[!A-Za-z0-9._-]*) hook_stop 2 "RUN_ID '$RID' is not a plain run id (letters, digits, '.', '_' and '-'); nothing was killed" ;;
esac

HELPERS=$HOME/egw-tcg/itest-helpers.sh
# The helper file is written for a shell without 'set -u' (it expands the
# variables of .env as they stand), so it is loaded with that option off.
set +u
if [ ! -r "$HELPERS" ]; then
    hook_stop 97 "the helper file $HELPERS is not readable: the hook never reached the guest, nothing was killed"
fi
# shellcheck disable=SC1090
. "$HELPERS" || hook_stop 97 "the helper file $HELPERS could not be loaded: the hook never reached the guest, nothing was killed"
set -u
[ -n "${P:-}" ] || hook_stop 97 "the helper file $HELPERS did not define P: it is not the runbook's 6.1 file, nothing was killed"

RECORD=$P/$RID.restart.txt
[ ! -e "$RECORD" ] || hook_stop 1 "$RECORD exists - a run id gets one fault and its record is write-once; nothing was killed"

# read_script: the guest command that reads the guest clock and the
# controller container. It runs under BusyBox ash and holds no bashism; its
# STOP lines go to stderr, so that the captured stdout holds only the
# key=value lines of a reading that was made. Each field is its own
# 'docker inspect' (as persistence.sh reads them): one template with the
# three fields would shift them when one is empty, and an empty StartedAt
# must reach the host as empty, never as the status.
read_script() {
    cat << 'GUEST_READ'
epoch=$(date +%s) || { echo 'STOP: the guest clock could not be read' >&2; exit 3; }
utc=$(date -u +%Y-%m-%dT%H:%M:%SZ) || { echo 'STOP: the guest clock could not be read' >&2; exit 3; }
cid=$(docker inspect -f '{{.Id}}' egw-controller-1) || { echo 'STOP: docker inspect egw-controller-1 (.Id) failed on the guest' >&2; exit 4; }
sat=$(docker inspect -f '{{.State.StartedAt}}' egw-controller-1) || { echo 'STOP: docker inspect egw-controller-1 (.State.StartedAt) failed on the guest' >&2; exit 4; }
st=$(docker inspect -f '{{.State.Status}}' egw-controller-1) || { echo 'STOP: docker inspect egw-controller-1 (.State.Status) failed on the guest' >&2; exit 4; }
echo "guest_epoch=$epoch"
echo "guest_utc=$utc"
echo "container_id=$cid"
echo "started_at=$sat"
echo "status=$st"
GUEST_READ
}

# parse_reading TEXT: sets R_EPOCH, R_UTC, R_ID, R_STARTED, R_STATUS from the
# key=value lines of one reading; non-zero, naming the field, when a value is
# missing or not of the expected form (an empty StartedAt is a reading that
# was not made, never an instant).
parse_reading() {
    local key value
    R_EPOCH='' R_UTC='' R_ID='' R_STARTED='' R_STATUS=''
    while IFS='=' read -r key value; do
        case "$key" in
            guest_epoch) R_EPOCH=$value ;;
            guest_utc) R_UTC=$value ;;
            container_id) R_ID=$value ;;
            started_at) R_STARTED=$value ;;
            status) R_STATUS=$value ;;
        esac
    done <<< "$1"
    [[ $R_EPOCH =~ ^[0-9]+$ ]] || { echo "proof_restart_controller: guest_epoch '$R_EPOCH' is not a whole number" >&2; return 1; }
    [ -n "$R_UTC" ] || { echo "proof_restart_controller: guest_utc is empty" >&2; return 1; }
    [[ $R_ID =~ ^[0-9a-f]{64}$ ]] || { echo "proof_restart_controller: container_id '$R_ID' is not a 64-hex container id" >&2; return 1; }
    [ -n "$R_STARTED" ] || { echo "proof_restart_controller: started_at is empty: the instant was not read" >&2; return 1; }
    [ -n "$R_STATUS" ] || { echo "proof_restart_controller: status is empty: the state was not read" >&2; return 1; }
}

# record LINES...: append to the write-once record, or stop.
record() {
    printf '%s\n' "$@" >> "$RECORD" || hook_stop 1 "$RECORD could not be written"
}

# --- before the fault --------------------------------------------------
before=$(ssh egw-tcg "$(read_script)")
rc=$?
[ "$rc" -eq 0 ] || hook_stop 1 "the controller container was NOT read on the guest before the fault (ssh egw-tcg exit $rc): nothing was killed"
parse_reading "$before" || hook_stop 1 "the reading before the fault is not of the expected form (the line above names the field): nothing was killed"
# The record is created write-once ('set -C': the redirection refuses an
# existing file), and holds the reading before anything is dispatched.
( set -C; printf '%s\n' "run_id=$RID" "container=egw-controller-1" "phase=before" > "$RECORD" ) \
    || hook_stop 1 "$RECORD could not be created write-once: nothing was killed"
record "$before"
echo "proof_restart_controller: before the fault: guest $R_UTC (epoch $R_EPOCH), egw-controller-1 id $R_ID started $R_STARTED status $R_STATUS" >&2
before_id=$R_ID
before_started=$R_STARTED

# --- the fault: SIGKILL of the controller's container, then a start -----
FAULT_CMD='cd /opt/egw/deployment && docker kill --signal=KILL egw-controller-1 && docker compose --env-file .env --env-file images.lock.env start controller'
record "phase=fault" "fault_command=$FAULT_CMD" "fault_dispatched_host_utc=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
ssh egw-tcg "$FAULT_CMD"
frc=$?
record "fault_exit=$frc"
[ "$frc" -eq 0 ] || hook_stop 1 "the fault command exited $frc (kill --signal=KILL then compose start controller): whether the controller was killed and started again is NOT established by this record; the driver's containers-after record says what the guest holds"

# --- after the fault ---------------------------------------------------
after=$(ssh egw-tcg "$(read_script)")
rc=$?
[ "$rc" -eq 0 ] || hook_stop 1 "the controller container was NOT read on the guest after the fault (ssh egw-tcg exit $rc): the fault command exited 0, and the instant after it is not recorded"
parse_reading "$after" || hook_stop 1 "the reading after the fault is not of the expected form (the line above names the field): the fault command exited 0, and the instant after it is not recorded"
record "phase=after" "$after"
same_id=no
[ "$R_ID" != "$before_id" ] || same_id=yes
moved=no
[ "$R_STARTED" = "$before_started" ] || moved=yes
record "phase=observation" "container_id_same=$same_id" "started_at_changed=$moved"
echo "proof_restart_controller: after the fault: guest $R_UTC (epoch $R_EPOCH), egw-controller-1 id $R_ID started $R_STARTED status $R_STATUS (container_id_same=$same_id started_at_changed=$moved; the restart-shown step decides)" >&2
echo "proof_restart_controller: $RID: the fault was issued and both readings are in $RECORD"
