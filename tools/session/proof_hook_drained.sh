#!/bin/bash
# The finite proof of ADR 0011: the harness's drain hook (--drain-cmd, run.py
# execute_run), run after the confirmation window and the harness events
# fetch, before the post-drain fetch and the after snapshot. The harness runs
# this file as one argv split without a shell (shlex.split, run.py
# execute_collector_hook) and classifies what it printed by two byte-stable
# line prefixes (run.py DRAIN_QUIET_LINE_PREFIX, DRAIN_GAVE_UP_LINE_PREFIX):
# the quiet line of the runbook's 'drained' on stdout, its give-up STOP on
# stderr. This hook therefore runs 'drained' and prints its lines UNCHANGED,
# and ends with the helper's own status: 0 for a quiet window, non-zero for
# the give-up or the helper's other stop (a /metrics it could not read, or a
# controller build without the thirteen fields).
# Usage: proof_hook_drained.sh RUN_ID
#
# The quiet window, the step and the limit are the helper's DRAIN_QUIET_S,
# DRAIN_STEP_S and DRAIN_LIMIT_S, read from the environment the driver
# exported (the values it recorded before the first 'drained' started). A
# DRAIN_QUIET_S below the runbook's 130 s is refused before anything is
# polled: the runbook says of that figure 'Never lower it' (6.1), and a
# proof drained under a shorter window would read a false quiet.
#
# The hook inherits the environment of the driver's host step (the venv on
# PATH, the .env exported, EGW_CLONE) but not the helper functions of runbook
# 6.1, which are defined by the deployed helper file: it sources that file
# itself. A helper file that cannot be loaded means the hook never reached
# what it was to run, and it answers 97 (EXIT_NOT_REACHED of common.sh,
# written literally here because common.sh is not sourced): neither line is
# then printed, which the harness records as a drain that ended in error.
set -u

# hook_stop CODE MESSAGE: print the STOP line and end with CODE.
hook_stop() {
    echo "STOP: proof_hook_drained: $2" >&2
    exit "$1"
}

[ "$#" -eq 1 ] || hook_stop 2 "usage: proof_hook_drained.sh RUN_ID"
RID=$1
case "$RID" in
    '' | *[!A-Za-z0-9._-]*) hook_stop 2 "RUN_ID '$RID' is not a plain run id (letters, digits, '.', '_' and '-')" ;;
esac
# A value that is set and is not a whole number of seconds is never silently
# replaced by the helper's default: the driver would then wait for something
# nobody asked (as healthy_seconds of guest_common.sh treats its limits).
for name in DRAIN_QUIET_S DRAIN_STEP_S DRAIN_LIMIT_S; do
    value=${!name:-}
    [ -z "$value" ] && continue
    case "$value" in
        *[!0-9]*) hook_stop 2 "$name='$value' is not a whole number of seconds: nothing was polled" ;;
    esac
done
if [ -n "${DRAIN_QUIET_S:-}" ] && [ "$DRAIN_QUIET_S" -lt 130 ]; then
    hook_stop 2 "DRAIN_QUIET_S=$DRAIN_QUIET_S is below the runbook's 130 s ('Never lower it', 6.1): nothing was polled"
fi

HELPERS=$HOME/egw-tcg/itest-helpers.sh
# The helper file is written for a shell without 'set -u' (it expands the
# variables of .env as they stand), so it is loaded with that option off.
set +u
if [ ! -r "$HELPERS" ]; then
    hook_stop 97 "the helper file $HELPERS is not readable: the hook never reached 'drained', nothing was polled"
fi
# shellcheck disable=SC1090
. "$HELPERS" || hook_stop 97 "the helper file $HELPERS could not be loaded: the hook never reached 'drained', nothing was polled"
set -u
declare -F drained > /dev/null || hook_stop 97 "the helper file $HELPERS defines no 'drained': it is not the runbook's 6.1 file, nothing was polled"

echo "proof_hook_drained: $RID: drained with DRAIN_QUIET_S=${DRAIN_QUIET_S:-130} DRAIN_STEP_S=${DRAIN_STEP_S:-5} DRAIN_LIMIT_S=${DRAIN_LIMIT_S:-900}"
# The helper's own lines, unchanged, and its own status.
drained
exit $?
