#!/bin/bash
# The finite proof of ADR 0011: the harness's twin-snapshot hook
# (--twin-snapshot-cmd, run.py execute_run). The harness runs this file once
# before the measured run and once after the drain, as one argv split without
# a shell (shlex.split, run.py execute_collector_hook), and reads the file it
# writes at {dest} as the snapshot of that label.
# Usage: proof_hook_twins.sh RUN_ID DEST SEED
#   DEST   the file the harness expects: <run dir>/twins.before.json or
#          <run dir>/twins.after.json (run.py TWIN_SNAPSHOT_FILES); the label
#          is read from its name and nothing else
#   SEED   the plan entry's seed, which 'before' derives the device set from;
#          'after' is taken --like before and carries no seed of its own
#
# The snapshot is the runbook's own (6.1: '$REC snap', as snap_pair takes it):
# it is written first as the prefix sibling $P/RUN_ID.twins.<label>.json, the
# write-once record beside the run's other snapshots, and then copied into
# DEST with the runbook's 'keep', so that the harness's copy and the sibling
# the driver packages are the same bytes. A sibling or a DEST that already
# exists stops the hook before anything is read: a run id and a label are
# used once. When the snapshot fails, DEST is NOT written: a hook that exits 0
# without its file is a validity reason (ADR 0011 item 18), and one that
# leaves a file behind after failing would be read as a snapshot it did not
# take.
#
# The hook inherits the environment of the driver's host step (the venv on
# PATH, the .env exported, EGW_CLONE) but not the helper functions of runbook
# 6.1, which are defined by the deployed helper file: it sources that file
# itself. A helper file that cannot be loaded means the hook never reached
# what it was to run, and it answers 97 (EXIT_NOT_REACHED of common.sh,
# written literally here because common.sh is not sourced), never a status
# that could be read as the snapshot failing.
set -u

# hook_stop CODE MESSAGE: print the STOP line and end with CODE.
hook_stop() {
    echo "STOP: proof_hook_twins: $2" >&2
    exit "$1"
}

[ "$#" -eq 3 ] || hook_stop 2 "usage: proof_hook_twins.sh RUN_ID DEST SEED (DEST names twins.before.json or twins.after.json)"
RID=$1
DEST=$2
SEED=$3
case "$RID" in
    '' | *[!A-Za-z0-9._-]*) hook_stop 2 "RUN_ID '$RID' is not a plain run id (letters, digits, '.', '_' and '-')" ;;
esac
case "$(basename "$DEST")" in
    twins.before.json) LABEL=before ;;
    twins.after.json) LABEL=after ;;
    *) hook_stop 2 "DEST '$DEST' is neither twins.before.json nor twins.after.json: no label can be read from it, nothing was taken" ;;
esac
case "$SEED" in
    '' | *[!0-9]*) hook_stop 2 "SEED '$SEED' is not a whole number: nothing was taken" ;;
esac

HELPERS=$HOME/egw-tcg/itest-helpers.sh
# The helper file is written for a shell without 'set -u' (it expands the
# variables of .env as they stand), so it is loaded with that option off.
set +u
if [ ! -r "$HELPERS" ]; then
    hook_stop 97 "the helper file $HELPERS is not readable: the hook never reached the snapshot, nothing was taken"
fi
# shellcheck disable=SC1090
. "$HELPERS" || hook_stop 97 "the helper file $HELPERS could not be loaded: the hook never reached the snapshot, nothing was taken"
set -u
declare -F keep > /dev/null || hook_stop 97 "the helper file $HELPERS defines no 'keep': it is not the runbook's 6.1 file, nothing was taken"
[ -n "${P:-}" ] && [ -n "${REC:-}" ] && [ -n "${DITTO:-}" ] \
    || hook_stop 97 "the helper file $HELPERS did not define P, REC and DITTO: it is not the runbook's 6.1 file, nothing was taken"

SIBLING=$P/$RID.twins.$LABEL.json
[ ! -e "$SIBLING" ] || hook_stop 1 "$SIBLING exists - run id and label already used; nothing was overwritten and $DEST was NOT written"
[ ! -e "$DEST" ] || hook_stop 1 "$DEST exists - NOT overwritten; no snapshot was taken"
if [ "$LABEL" = after ]; then
    [ -s "$P/$RID.twins.before.json" ] \
        || hook_stop 1 "$P/$RID.twins.before.json is missing or empty: 'after' is taken --like before, so no device set is known; $DEST was NOT written"
fi

# The runbook's own command lines (6.1 snap_pair; nominal.sh after-snapshots):
# 'before' derives the device set from the seed, 'after' from the before
# snapshot. $REC is the helper's word-split command, as the runbook uses it.
if [ "$LABEL" = before ]; then
    # shellcheck disable=SC2086
    $REC snap --prefix "$P/$RID" --label before --seed "$SEED" --ditto-url "$DITTO"
else
    # shellcheck disable=SC2086
    $REC snap --prefix "$P/$RID" --label after --like before --ditto-url "$DITTO"
fi
rc=$?
[ "$rc" -eq 0 ] || hook_stop 1 "the $LABEL twin snapshot was not taken (\$REC snap exited $rc): $DEST was NOT written"
[ -s "$SIBLING" ] || hook_stop 1 "\$REC snap exited 0 and left no $SIBLING: $DEST was NOT written"
keep "$SIBLING" "$DEST" || hook_stop 1 "the $LABEL snapshot was taken as $SIBLING but $DEST was NOT written (keep failed)"
echo "proof_hook_twins: $RID $LABEL: snapshot kept as $SIBLING and $DEST"
