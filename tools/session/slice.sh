#!/bin/bash
# Work order 2.C step 2: one fresh bounded vertical slice (runbook 6.2-6.4):
# one smartwatch at 1 Hz for 60 s, identity-based reconciliation and API
# readback, with an isolated run id and a seed never used on this MongoDB
# volume (a fresh twin); the counter baseline is the 'before' snapshot.
# Usage: slice.sh RUN SEED
#
# Prerequisites (failure: outcome not-run, exit 2) are the open session, the
# attempt's own fields and 'pre'. The simulator and marker, the 'after' state,
# the twin read-back, 'check', 'delta' and the verdict are MANDATORY: any of
# them failing leaves the slice invalid (exit 3). A valid negative result
# (exit 1) needs every mandatory step to have been carried out.
set -u
. "$(dirname "$0")/common.sh"
. "$(dirname "$0")/guest_common.sh"
# A missing argument is a prerequisite (2), never the 1 of a valid negative
# result: '${1:?...}' would end the shell with 1 before any check could run.
[ "$#" -eq 2 ] || driver_stop "$EXIT_PREREQUISITE" "usage: slice.sh RUN SEED (a fresh run id and a seed never used on this volume)"
RUN=$1
SEED=$2
[ -n "$SESSION" ] || driver_stop "$EXIT_PREREQUISITE" "no open session"
A=$(new_attempt "smartwatch slice 1 Hz 60 s" engineering) \
    || driver_stop "$EXIT_PREREQUISITE" "the attempt could not be created"
trap 'driver_interrupt "$A"' INT TERM

# not_run REASON: a prerequisite failed, so the slice did not run.
not_run() {
    (cd "$REPO/src" && $LE finish --attempt "$A" --status failed --validity invalid --outcome not-run \
        --reason "$1" --next-action "read console/; the slice did not run as a protocol check")
    driver_exit "$A"
}

# The identity of the clean clone is part of the result: a git that cannot be
# read is recorded as such (identity_error) and stops the slice.
IDENTITIES=$(repo_identity) || IDENTITY_FAILED=1
(cd "$REPO/src" && $LE set --attempt "$A" "pid=$$" "seed=$SEED" "identities=$IDENTITIES" \
    "workload={\"session\": \"$(basename "$SESSION")\", \"itest_run_id\": \"$RUN\", \"devices\": \"1 smartwatch\", \"rate_hz\": 1.0, \"duration_s\": 60, \"scenario\": \"smoke\"}" \
    'expected_artefacts=["simulator/*/sent_events.jsonl", "simulator/*/events.jsonl", "simulator/*.marker.json", "simulator/*.metrics.before.json", "simulator/*.metrics.after.json", "simulator/*.twins.before.json", "simulator/*.twins.after.json", "simulator/*.reconcile.json"]') \
    || not_run "the attempt fields could not be recorded; nothing was started"
[ "${IDENTITY_FAILED:-0}" -eq 0 ] \
    || not_run "the identity of the clean clone could not be read (see identities.identity_error); nothing was started"
P=$HOME/egw-tcg/itest
(cd "$REPO/src" && $LE add-source --attempt "$A" --kind simulator --path "$P/$RUN" --siblings-glob "$RUN.*" \
    --role "ad-hoc run directory and its sibling files (runbook 6.1 helpers)") \
    || not_run "the simulator source could not be registered; nothing was started"

mandatory=()      # failed mandatory steps: the slice is invalid
hx "$A" pre "pre $RUN $SEED smartwatch"
pre_rc=$?
if [ "$pre_rc" -eq "$EXIT_CAPTURE_LOST" ]; then
    capture_stop "$A" pre "the simulator was NOT started"
elif [ "$pre_rc" -ne 0 ]; then
    not_run "precondition failed (pre exit $pre_rc); the simulator was NOT started"
fi

hx "$A" simulator-and-mark ": > \$P/$RUN.stderr.txt && \$SIM --scenario smoke --seed $SEED --devices smartwatch --rate 1.0 --duration 60 --run-id $RUN 2>&1 | tee \$P/$RUN.stderr.txt; ST=(\"\${PIPESTATUS[@]}\"); \$REC mark \$P/$RUN; MARK_RC=\$?; echo \"FLOW STATUS $RUN: simulator exit=\${ST[0]} transcript (tee) exit=\${ST[1]} mark exit=\$MARK_RC\"; [ \"\${ST[0]}\" = 0 ] && [ \"\${ST[1]}\" = 0 ] && [ -s \$P/$RUN.stderr.txt ] && [ \"\$MARK_RC\" = 0 ]"
sim_rc=$?
[ "$sim_rc" -eq 0 ] || mandatory+=("$(step_note simulator-and-mark "$sim_rc" "the simulator, its transcript or the controller marker failed (exit $sim_rc)")")

after_rc=1
if [ "$sim_rc" -eq 0 ]; then
    hx "$A" after "{ [ -f \$P/$RUN.window-closed.json ] || \$REC wait \$P/$RUN; } && drained && fetch $RUN && accounted $RUN && snap_pair $RUN after"
    after_rc=$?
    [ "$after_rc" -eq 0 ] || mandatory+=("$(step_note after "$after_rc" "the 'after' state was not captured (exit $after_rc)")")
    hx "$A" twin-readback "UUID=\$(python3 -c \"import json;print(json.loads(open('\$P/$RUN/sent_events.jsonl').readline())['device_uuid'])\") && twin $RUN \$UUID && python3 -m json.tool \$P/$RUN.twin.\$UUID.json"
    twin_rc=$?
    [ "$twin_rc" -eq 0 ] || mandatory+=("$(step_note twin-readback "$twin_rc" "the twin read-back failed")")
else
    mandatory+=("the 'after' state and the twin read-back were not run")
fi

C=9; D=9; U=unknown
if [ "$after_rc" -eq 0 ]; then
    # check: 0 is required; 3 = no marker, 1 = the check was not carried out.
    hx "$A" check "\$REC check \$P/$RUN"
    C=$?
    [ "$C" -eq 0 ] || mandatory+=("$(step_note check "$C" "the protocol check was not carried out (check exit $C)")")
    # delta: 0 and 4 (MISMATCH or queue not empty) are results; anything else
    # means the comparison itself did not happen.
    hx "$A" delta "\$REC delta \$P/$RUN"
    D=$?
    case "$D" in 0 | 4) ;; *) mandatory+=("$(step_note delta "$D" "the counter/twin delta was not evaluated (delta exit $D)")") ;; esac
    [ -e "$P/$RUN.unaccounted.txt" ] && U=yes || U=no
else
    mandatory+=("'check' and 'delta' were not run")
fi

# Verdicts, from the reconciliation file (never from exit codes alone). The
# snippet exits 0 PASS, 1 FAIL and 2 for ANY content it cannot judge: a file
# that is missing, is not an object, or whose decisive counters are absent.
ex "$A" verdict "$PY" -c '
import json, sys
p, C, D, U = sys.argv[1], int(sys.argv[2]), int(sys.argv[3]), sys.argv[4]
keys = ["confirmation_deadline_source", "sent_valid", "delivered_unique", "lost", "late_confirmations",
        "double_accepted", "intended_invalid_accepted", "marker_lag_s"]
decisive = ["sent_valid", "delivered_unique", "lost", "late_confirmations", "double_accepted"]
try:
    r = json.load(open(p))
    row = r.get("row", r)
    fields = {k: row.get(k) for k in keys}
    absent = [k for k in decisive if not isinstance(fields[k], int)]
    if absent:
        raise ValueError("no usable " + ", ".join(absent))
except Exception as e:
    print(f"the reconciliation file cannot be judged: {e}"); sys.exit(2)
print(json.dumps(fields, indent=2))
ok = (C == 0 and D == 0 and U == "no" and fields["lost"] == 0 and fields["late_confirmations"] == 0
      and fields["delivered_unique"] == fields["sent_valid"] and fields["double_accepted"] == 0)
print("SLICE", "PASS" if ok else "FAIL", f"check={C} delta={D} unaccounted={U}")
sys.exit(0 if ok else 1)
' "$P/$RUN.reconcile.json" "$C" "$D" "$U"
vrc=$?
# Only 0 and 1 are verdicts: 2 (nothing to judge), 74 (the verdict's own
# console record was lost) and anything unexpected leave the slice unjudged.
case "$vrc" in
    0 | 1) ;;
    *) mandatory+=("$(step_note verdict "$vrc" "the reconciliation file was not judged (verdict exit $vrc): there is nothing to conclude from")") ;;
esac

if [ "${#mandatory[@]}" -ne 0 ]; then
    (cd "$REPO/src" && $LE finish --attempt "$A" --status failed --validity invalid --outcome inconclusive \
        --reason "the slice ran, but mandatory steps failed: $(printf '%s; ' "${mandatory[@]}")(check $C, delta $D, unaccounted $U)" \
        --next-action "read console/; these measurements are not usable")
elif [ "$vrc" -eq 0 ]; then
    (cd "$REPO/src" && $LE finish --attempt "$A" --status finished --validity valid --outcome pass \
        --reason "every published identity accounted; lost 0, late 0, twin and /metrics deltas OK" \
        --next-action "nominal entry 120 s + 600 s")
else
    (cd "$REPO/src" && $LE finish --attempt "$A" --status finished --validity valid --outcome fail \
        --reason "instrumentation complete but the delivery or counter criteria failed (check $C, delta $D, unaccounted $U)" \
        --next-action "diagnose before the nominal entry")
fi
driver_exit "$A"
