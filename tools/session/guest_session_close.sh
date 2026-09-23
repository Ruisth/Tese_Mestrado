#!/bin/bash
# Close the open guest session: stop the stack first (runbook 3.3), keep the
# journal and final state, power off, record the rootfs afterwards, export.
#
# The controlled stop is what this driver is for: the stack stop, a readable
# dmesg for the OOM record, the power-off and "no qemu-system-aarch64 left"
# are all mandatory, and any of them failing ends the driver with exit 5.
# Finding an OOM in that record is not one of those failures: the close read
# the system correctly and the SYSTEM is what failed, so the session is sealed
# with the instrumentation not-applicable and the outcome fail (exit 1, the
# valid negative result). Only a dmesg that could not be read at all - the OOM
# state of the boot is then UNKNOWN, which is not "no OOM" - keeps the 5.
# A step whose own command ran while its mandatory console capture was lost
# (74) is never recorded as that step having failed: its own exit code is kept
# in commands.jsonl, and when no qemu-system-aarch64 process is left the close
# is sealed as an incomplete record (invalid, inconclusive, exit 3), never as
# a failed controlled stop. The record of the artefacts after the power-off and
# guest/session_close.sh's own "the guest is off, but a record of the close was
# not kept" (exit 3) are read the same way.
# $EXEC/current_session is kept while a qemu-system-aarch64 process remains,
# and also when whether one remains could not be decided at all, so that a
# guest still running is never mistaken for a closed session.
set -u
. "$(dirname "$0")/common.sh"
. "$(dirname "$0")/guest_common.sh"
S=$SESSION
[ -n "$S" ] && [ -d "$S" ] || driver_stop "$EXIT_PREREQUISITE" "no open session"
# The stop and the power-off are the long steps of a TCG session: an interrupt
# here marks the session attempt interrupted and exports it (130), instead of
# leaving the whole session's evidence unexported and current_session dangling.
trap 'driver_interrupt "$S"' INT TERM
# Three lists, because they are three different facts. 'fails' is the
# controlled stop itself failing (code 5); 'incomplete' is a step whose own
# command ran while its mandatory console capture was lost (74, common.sh
# interface 1), or a record of the close that could not be kept; 'observed' is
# what the session's own records SHOW the system doing - a memory-cgroup OOM in
# this boot - which is a system outcome of that session (a valid negative
# result, code 1) and not a failure of the close or of its record. A lost
# capture is never written down as the step having failed, so a stack that WAS
# stopped and a guest that WAS powered off are never sealed as "the controlled
# stop failed".
fails=()
incomplete=()
observed=()
hx "$S" tunnel-down 'tunnel_down || true'
tunnel_rc=$?
[ "$tunnel_rc" -ne "$EXIT_CAPTURE_LOST" ] || incomplete+=("$(capture_note tunnel-down)")
gx "$S" stack-stop "cd /opt/egw/deployment && $DC stop -t 60; rc=\$?; echo \"stop exit=\$rc\"; docker ps -a --format '{{.Names}} {{.Status}}'; exit \$rc"
stop_rc=$?
case "$stop_rc" in
    0) ;;
    "$EXIT_CAPTURE_LOST") incomplete+=("$(capture_note stack-stop)") ;;
    *) fails+=("the stack was not stopped (exit $stop_rc)") ;;
esac
# The OOM record of this boot, read before the power-off takes it with it. The
# guest command separates the three cases instead of passing either way: none
# found (0), found (3: a fact about the system, kept in the verdict), and a
# dmesg that cannot be read (1: the OOM state is UNKNOWN, which is not "no
# OOM", and is an evidence failure of the controlled close as it has always
# been).
gx "$S" oom-before-poweroff "if KMSG=\$(sudo -n dmesg 2>/dev/null); then N=\$(printf '%s\n' \"\$KMSG\" | grep -ci 'memory cgroup out of memory' || true); printf '%s\n' \"\$KMSG\" | grep -i 'memory cgroup out of memory' || echo 'no memory-cgroup OOM in this boot'; echo \"memory-cgroup OOM lines: \$N\"; [ \"\$N\" = 0 ] || exit 3; else echo 'dmesg could not be read: the OOM state of this boot is UNKNOWN, which is not \"no OOM\"'; exit 1; fi"
oom_rc=$?
case "$oom_rc" in
    0) ;;
    "$EXIT_CAPTURE_LOST") incomplete+=("$(capture_note oom-before-poweroff)") ;;
    # The kernel OOM-killed something in this boot: the close read that
    # correctly, so the record is sound and the SYSTEM is what failed.
    3) observed+=("the kernel reports memory-cgroup OOM line(s) in this boot (oom-before-poweroff exit 3): a service was OOM-killed during this session; see console/") ;;
    *) fails+=("the OOM state of this boot could not be read before the power-off (exit $oom_rc)") ;;
esac
ex "$S" session-close bash "$S/scripts/session_close.sh" "$S"
close_rc=$?
case "$close_rc" in
    0) ;;
    "$EXIT_CAPTURE_LOST") incomplete+=("$(capture_note session-close)") ;;
    # guest/session_close.sh's own code for "the guest IS off, but a record of
    # the close was not kept" (its boot journal or its final state): the
    # controlled stop did not fail, the record of it is incomplete.
    "$EXIT_INVALID") incomplete+=("the guest was powered off, but a record of the close was not kept (exit $close_rc); see guest/") ;;
    *) fails+=("the controlled power-off failed (exit $close_rc)") ;;
esac
# Whether a qemu-system-aarch64 process is left is decided HERE, in the driver's
# own shell, by the executable at the start of the command line (qemu_procs,
# guest_common.sh): a match on the whole command line would match any shell
# whose command line holds the pattern - the artefacts step's own 'bash -c',
# the local_export process above it and, as the C3 session of 2026-09-23
# showed, the very shell that invoked this driver - and a match on the
# process name can never see a name of 19 characters (Linux keeps 15). The
# driver's own finding is passed into the record instead. pgrep answers 1 for
# "no match" and 2 or more for a usage or fatal error (127 when it is not on
# PATH at all), so only 1 is "no qemu process left": a pgrep that could not
# ANSWER is its own state, never a closed guest, because the record must not
# assert what the command did not establish.
QEMU_LEFT=$(qemu_procs)
pgrep_rc=$?
case "$pgrep_rc" in
    0)
        QEMU_NOTE="a qemu-system-aarch64 process is STILL running after the power-off:
$QEMU_LEFT"
        ;;
    1)
        QEMU_LEFT=""
        QEMU_NOTE="no qemu process left"
        ;;
    *)
        QEMU_LEFT=""
        QEMU_UNKNOWN=1
        QEMU_NOTE="whether a qemu-system-aarch64 process is left is UNKNOWN: pgrep exited $pgrep_rc"
        ;;
esac
# The identity of the two artefacts the whole session ran on. The step is a
# LIST of commands, so its own status is accumulated (as the identity group of
# guest_session_open.sh and nominal.sh's GUEST_STATE do): a rootfs that cannot
# be hashed or a data disk that cannot be listed must not disappear behind the
# status of the last command in the list.
ex "$S" artefacts-after-poweroff bash -c 'rc=0; sha256sum "$1" || rc=1; ls -l "$2" || rc=1; printf "%s\n" "$3"; exit $rc' \
    _ "$ROOTFS_EXT4" "$DATA_DISK" "$QEMU_NOTE"
artefacts_rc=$?
case "$artefacts_rc" in
    0) ;;
    "$EXIT_CAPTURE_LOST") incomplete+=("$(capture_note artefacts-after-poweroff)") ;;
    *) incomplete+=("the artefacts after the power-off were not recorded (exit $artefacts_rc)") ;;
esac
if [ -n "$QEMU_LEFT" ]; then
    fails+=("a qemu-system-aarch64 process is still running: the session is NOT closed")
    echo "STOP: qemu-system-aarch64 is still running; $EXEC/current_session is kept" >&2
elif [ "${QEMU_UNKNOWN:-0}" -ne 0 ]; then
    # Undecidable, so neither "still running" (a failed stop) nor "none left"
    # (a closed session): the record of the close is incomplete and the session
    # is kept, because a guest that may still be up must stay reachable.
    incomplete+=("whether a qemu-system-aarch64 process is left could not be decided (pgrep exit $pgrep_rc); $EXEC/current_session is kept")
    echo "STOP: whether a qemu-system-aarch64 process is left could not be decided (pgrep exit $pgrep_rc); $EXEC/current_session is kept" >&2
else
    rm -f "$EXEC/current_session"
fi

# What the session's records SHOW the system doing is stated first, in every
# branch: it is never lost behind a verdict about the close itself.
seen=""
[ "${#observed[@]}" -eq 0 ] || seen="observed system fault(s) during this session: $(printf '%s; ' "${observed[@]}")"

if [ "${#fails[@]}" -ne 0 ]; then
    note="${seen}the controlled stop failed: $(printf '%s; ' "${fails[@]}")"
    [ "${#incomplete[@]}" -eq 0 ] || note="$note$(printf '%s; ' "${incomplete[@]}")"
    (cd "$REPO/src" && $LE finish --attempt "$S" --status failed --validity not-applicable --outcome fail \
        --reason "${note}see console/" \
        --next-action "check the guest state before the next boot")
    driver_exit "$S" 1
elif [ "${#incomplete[@]}" -ne 0 ]; then
    # The controlled stop did not fail; what is missing is part of the record,
    # and the step's own exit code is in commands.jsonl. That is invalid
    # instrumentation (3), never a failed controlled stop (5). The sentence
    # says which of the two it is: "the guest is off" is claimed only when
    # pgrep answered that no process is left.
    if [ "${QEMU_UNKNOWN:-0}" -eq 0 ]; then
        seal_head="the guest is off and no qemu-system-aarch64 process is left, but the record of the close is incomplete: "
        seal_next="read commands.jsonl for each step's own exit code; the session IS closed"
    else
        seal_head="the stack was stopped and the power-off ran, but the record of the close is incomplete: "
        seal_next="read commands.jsonl for each step's own exit code; check for a qemu-system-aarch64 process by hand before the next boot: whether the guest is off was NOT established"
    fi
    # A fault the session's records showed all the same is the system outcome;
    # what is invalid is the record of the close, never that observation.
    seal_outcome=inconclusive
    [ "${#observed[@]}" -eq 0 ] || seal_outcome=fail
    (cd "$REPO/src" && $LE finish --attempt "$S" --status failed --validity invalid --outcome "$seal_outcome" \
        --reason "${seen}${seal_head}$(printf '%s; ' "${incomplete[@]}")see console/ and commands.jsonl" \
        --next-action "$seal_next")
    driver_exit "$S"
elif [ "${#observed[@]}" -ne 0 ]; then
    # The close itself is complete and its record is sound: what failed is the
    # system the session was running. The instrumentation stays not-applicable
    # and the driver ends 1, the valid negative result, never 5.
    (cd "$REPO/src" && $LE finish --attempt "$S" --status failed --validity not-applicable --outcome fail \
        --reason "${seen}session closed: stack stopped before power-off, journal and final state kept; see console/" \
        --next-action "read console/ for the OOM record of this boot: this is a system failure of the session, not a failed close")
    driver_exit "$S"
else
    (cd "$REPO/src" && $LE finish --attempt "$S" --status finished --validity not-applicable --outcome pass \
        --reason "session closed: stack stopped before power-off, journal and final state kept" --next-action "none")
    driver_exit "$S"
fi
