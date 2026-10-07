#!/bin/bash
# G3 session S4 (test 6 only) - the emergency cleanup of the run's Docker events recorder,
# with its partial capture kept INSIDE the session's package (supplement of 2026-10-07 to the
# sealed preparation HIST_2026-10-05-g3-t6-host-preparation; the Project Manager's order of
# 2026-10-07, register line 4937).
#
# When: after 'term t6' (the row's 47 min ceiling), or after T6=incomplete (harness_cmd's own
# cleanup failed), BEFORE 'close'. The TERM to the row's group can leave the recorder unit
# egw-events-controller_restart-r04 running, or stopped with its capture still only in the
# guest's /tmp/egw-events-controller_restart-r04, which the guest's power-off at the close
# would lose (bench finding F1 of the preparation).
#
# What: the existing command, unchanged - 'events_capture.sh cleanup RUN_ID KEEP_DIR' of the
# clone (1fd9792) - with KEEP_DIR explicit inside the open session's attempt directory, which
# the frozen guest_session_close.sh exports with the session's package:
#   KEEP_DIR = <session attempt>/recovery/events-partial-controller_restart-r04
# The command stops the unit if it is not shown stopped, then copies the recorder's four files
# (events.partial.jsonl, lifecycle.txt, start-facts.txt, cli-stderr.txt) as a PARTIAL capture,
# never as the run's docker-events.log: write-once, through a staging folder that becomes
# KEEP_DIR only when all four arrived; a staging folder holding some files is kept beside it
# (KEEP_DIR.copy.*), named incomplete, and is exported too.
#
# Each try is one recorded host step of the session's attempt ('ex' of the frozen common.sh),
# bounded by 'timeout 120' (TERM to the command's own process group, which holds its ssh and
# scp); at most three tries; every try's output is in the session's console/ and
# commands.jsonl. After a try that ended 0, two confirmations, each recorded: the unit's state
# read on the guest (inactive or failed) and the four files present in KEEP_DIR (listed with
# their sizes and sha256). Only then does this script say that 'close' may run.
#
# It never runs 'close', never powers anything off, never signals QEMU or any other process,
# and never deletes anything. If the confirmations are not reached within three tries, it ends
# with a HALT: do NOT run 'close'; hand back to Rui (the guest's capture stays in its /tmp
# while the guest is up).
#
# Usage (WSL, login shell; one invocation):
#   EGW_EXEC_REPO=$HOME/egw-exec/repo bash <P>/ops/g3_recorder_cleanup.sh
# Exit: 0 recorder stopped and partial capture kept (close may run); 1 HALT (do not close);
# 2 refused (nothing was run).
set -u
RID=controller_restart-r04
LIMIT_S=120      # the Project Manager's bound for one try
TRIES=3          # the Project Manager's maximum
FILES="events.partial.jsonl lifecycle.txt start-facts.txt cli-stderr.txt"

refuse() { echo "REFUSED: $* - nothing was run"; exit 2; }
halt() {
    echo "HALT: $* - do NOT run 'close'; nothing was signalled or powered off; hand back to Rui (the guest's capture stays in /tmp/egw-events-$RID while the guest is up)"
    exit 1
}

[ -n "${EGW_EXEC_REPO:-}" ] && [ -r "$EGW_EXEC_REPO/tools/session/common.sh" ] \
    && [ -r "$EGW_EXEC_REPO/tools/session/guest_common.sh" ] \
    || refuse "EGW_EXEC_REPO must name the clean clone (\$HOME/egw-exec/repo)"
export EGW_EXEC_REPO
# shellcheck source=/dev/null
. "$EGW_EXEC_REPO/tools/session/common.sh"
# shellcheck source=/dev/null
. "$EGW_EXEC_REPO/tools/session/guest_common.sh"
CAPTURE=$REPO/tools/session/events_capture.sh
[ -r "$CAPTURE" ] || refuse "$CAPTURE cannot be read"
[ -n "$SESSION" ] && [ -d "$SESSION" ] || refuse "no open session (\$EXEC/current_session): there is nothing to keep the capture in"
# No changing subcommand of the steps script may run beside this one: open, row, classify and
# close each hold its turn, recorded in <state>/turn.env (the holder's pid, its start tick and
# the WSL boot); a holder that still lives is a refusal, read as g3_battery.sh's take_turn reads
# it. A row still running is never cleaned up under it.
STATE=${EGW_G3_STATE:-$EXEC/g3-t6-s4}
TURN=$STATE/turn.env
[ -d "$STATE" ] || refuse "the state directory $STATE does not exist: S4 was not opened by g3_battery.sh"
tget() { sed -n "s/^$1=//p" "$TURN" 2> /dev/null | tail -n 1; }
pstart() {
    local s
    s=$(cat "/proc/$1/stat" 2> /dev/null) || return 1
    s=${s##*) }
    # shellcheck disable=SC2086
    set -- $s
    printf '%s' "${20:-}"
}
tpid=$(tget pid)
case $tpid in *[!0-9]*) tpid="" ;; esac
if [ -n "$tpid" ] && [ -n "$(tget pid_start)" ] && [ "$(tget wsl_boot_id)" = "$(cat /proc/sys/kernel/random/boot_id 2> /dev/null)" ] \
    && [ "$(pstart "$tpid")" = "$(tget pid_start)" ]; then
    refuse "g3_battery.sh '$(tget what)' (pid $tpid) still holds the turn: wait for it to end"
fi
KEEP=$SESSION/recovery/events-partial-$RID

echo "## $(date -u +%FT%TZ) recorder cleanup of $RID: session $SESSION"
echo "events_capture.sh: $CAPTURE (sha256 $(sha256sum "$CAPTURE" | cut -d' ' -f1)); this script sha256 $(sha256sum "$0" | cut -d' ' -f1)"
echo "KEEP_DIR: $KEEP; each try bounded by timeout $LIMIT_S s; at most $TRIES tries"

# kept_complete: 0 only when KEEP_DIR holds the four files as regular files.
kept_complete() {
    local f
    [ -d "$KEEP" ] || return 1
    for f in $FILES; do [ -f "$KEEP/$f" ] || return 1; done
}
# confirm: the two recorded confirmations; 0 only when both hold.
confirm() {
    local rc=0
    gx "$SESSION" "recorder-unit-state-$RID" "s=\$(systemctl is-active egw-events-$RID 2> /dev/null); echo \"unit_state=\${s:-unknown}\"; case \$s in inactive | failed) exit 0 ;; *) exit 1 ;; esac" \
        || { echo "the unit egw-events-$RID is not shown stopped by the read (exit $?)"; rc=1; }
    ex "$SESSION" "recorder-partial-capture-$RID" bash -c 'cd "$1" && ls -l . && sha256sum -- *' _ "$KEEP" \
        || { echo "the partial capture in $KEEP could not be listed"; rc=1; }
    kept_complete || { echo "KEEP_DIR does not hold the four files ($FILES)"; rc=1; }
    return "$rc"
}

if [ -e "$KEEP" ]; then
    # A complete KEEP_DIR from an earlier invocation: nothing is copied again (write-once);
    # the confirmations are read again.
    kept_complete || halt "$KEEP exists but does not hold the four files: it is never overwritten"
    echo "KEEP_DIR already holds the partial capture (an earlier invocation): no new try; confirming"
    confirm || halt "the confirmations did not hold"
    echo "OK: the recorder egw-events-$RID is stopped and its partial capture is kept in $KEEP: 'close' may run"
    exit 0
fi

i=0
while [ "$i" -lt "$TRIES" ]; do
    i=$((i + 1))
    echo "## $(date -u +%FT%TZ) try $i of $TRIES (timeout $LIMIT_S s)"
    ex "$SESSION" "recorder-cleanup-$RID-try$i" timeout "$LIMIT_S" bash "$CAPTURE" cleanup "$RID" "$KEEP"
    rc=$?
    echo "try $i: exit $rc$([ "$rc" = 124 ] && echo " (the $LIMIT_S s bound: timeout's TERM)")"
    [ "$rc" != "$EXIT_CAPTURE_LOST" ] || halt "try $i's console capture was lost (exit $rc): its output is not recorded"
    # Any staging folder a try left with files in it is kept and named (never removed).
    for d in "$KEEP".copy.*; do
        [ -d "$d" ] || continue
        if [ -n "$(ls -A "$d")" ]; then
            echo "kept INCOMPLETE (not the run's capture, not KEEP_DIR): $d: $(ls "$d" | tr '\n' ' ')"
        else
            echo "an empty staging folder of an ended try (nothing copied into it), kept as it is: $d"
        fi
    done
    if [ "$rc" = 0 ] && kept_complete; then
        if confirm; then
            echo "OK: the recorder egw-events-$RID is stopped and its partial capture is kept in $KEEP (try $i): 'close' may run"
            exit 0
        fi
        halt "try $i ended 0 but the confirmations did not hold"
    fi
    # A try that ended 0 with an incomplete KEEP_DIR cannot be repeated (write-once).
    [ ! -e "$KEEP" ] || halt "try $i left $KEEP without the four files"
done
halt "$TRIES tries did not show the recorder stopped with its partial capture kept"
