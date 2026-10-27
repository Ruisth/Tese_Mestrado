#!/bin/bash
# The finite proof of ADR 0011: the three SUT log fetches of the harness
# (--fetch-broker-log-cmd, --fetch-controller-log-cmd,
# --fetch-docker-events-cmd; run.py SUT_LOG_FETCH_FLAGS), run last, after the
# drain, so that they cover it, and each expected to write its file under
# logs/sut/ (run.py SUT_LOG_FILES) before the seal. The harness runs this
# file as one argv split without a shell (shlex.split, run.py
# execute_collector_hook).
# Usage: proof_fetch_sut_log.sh KIND DEST SINCE_GUEST_EPOCH
#   KIND   broker         the broker's log, as test 5 collects it (runbook):
#                         'docker compose ... logs --no-color --timestamps mosquitto'
#          controller     the controller container's log, 'docker logs
#                         --timestamps egw-controller-1', stderr merged on the
#                         guest: the controller logs its JSON lines to stderr
#                         (logging_config.py)
#          docker-events  'docker events' for the controller container from
#                         SINCE_GUEST_EPOCH to the guest's now: bounded on both
#                         sides, so the read ends by itself instead of following
#                         the daemon
#   DEST   the file the harness expects (<run dir>/logs/sut/broker.log,
#          controller.log or docker-events.log)
#   SINCE_GUEST_EPOCH  the guest clock, in whole seconds since the epoch, at
#          the start of the session (the driver's own reading); used by
#          docker-events, required as a whole number for every kind so that
#          the three templates take the same arguments
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

[ "$#" -eq 3 ] || hook_stop 2 "usage: proof_fetch_sut_log.sh KIND DEST SINCE_GUEST_EPOCH (KIND is broker, controller or docker-events)"
KIND=$1
DEST=$2
SINCE=$3
case "$KIND" in
    broker | controller | docker-events) ;;
    *) hook_stop 2 "KIND '$KIND' is not broker, controller or docker-events: nothing was read" ;;
esac
[ -n "$DEST" ] || hook_stop 2 "DEST is empty: nothing was read"
case "$SINCE" in
    '' | *[!0-9]*) hook_stop 2 "SINCE_GUEST_EPOCH '$SINCE' is not a whole number of seconds: nothing was read" ;;
esac
[ ! -e "$DEST" ] || hook_stop 1 "$DEST exists - NOT overwritten; nothing was read"

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

# The guest command of each kind. Every one runs under the guest's own shell
# (BusyBox ash) and holds no bashism; the controller's '2>&1' merges the
# container's stderr stream on the guest, where 'docker logs' replays it,
# so ssh's own stderr stays apart and reaches this hook's stderr. The events
# read is bounded on both sides: '--since' is the driver's guest instant and
# '--until' the guest's own clock when the read starts, so 'docker events'
# returns instead of following the daemon (to verify on the guest's docker
# 25.0.9 before the session: design flag V-3).
case "$KIND" in
    broker)
        GUEST_CMD='cd /opt/egw/deployment && docker compose --env-file .env --env-file images.lock.env logs --no-color --timestamps mosquitto' ;;
    controller)
        GUEST_CMD='docker logs --timestamps egw-controller-1 2>&1' ;;
    docker-events)
        GUEST_CMD="docker events --filter container=egw-controller-1 --since $SINCE --until \$(date +%s)" ;;
esac

TMP=$DEST.tmp
mkdir -p "$(dirname "$DEST")" || hook_stop 1 "the directory of $DEST could not be created: nothing was read"
: > "$TMP" || hook_stop 1 "$TMP could not be written: nothing was read"
ssh egw-tcg "$GUEST_CMD" > "$TMP"
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
mv "$TMP" "$DEST" || { rm -f "$TMP"; hook_stop 1 "the $KIND log was read ($bytes bytes) but $DEST could not be written"; }
lines=$(wc -l < "$DEST") || lines=unreadable
sha=$(sha256sum "$DEST" | cut -d ' ' -f 1) || sha=unreadable
echo "proof_fetch_sut_log: $KIND: $lines line(s), $bytes bytes, sha256 $sha, written to $DEST"
