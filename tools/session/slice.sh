#!/bin/bash
# Work order 2.C step 2: one fresh bounded vertical slice (runbook 6.2-6.4):
# one smartwatch at 1 Hz for 60 s, identity-based reconciliation and API
# readback, with an isolated run id and a seed never used on this MongoDB
# volume (a fresh twin); the counter baseline is the 'before' snapshot.
# Usage: slice.sh RUN SEED
set -u
. "$(dirname "$0")/common.sh"
. "$(dirname "$0")/guest_common.sh"
RUN=${1:?run id, e.g. itest-slice-01}
SEED=${2:?seed never used on this volume}
[ -n "$SESSION" ] || { echo "STOP: no open session" >&2; exit 1; }
A=$(new_attempt "smartwatch slice 1 Hz 60 s" engineering) || exit 1
trap '(cd "$REPO/src" && $LE finish --attempt "$A" --status interrupted --outcome interrupted --reason "driver interrupted" 2>/dev/null); export_attempt "$A"' INT TERM
(cd "$REPO/src" && $LE set --attempt "$A" "pid=$$" "seed=$SEED" "identities=$(repo_identity)" \
    "workload={\"session\": \"$(basename "$SESSION")\", \"itest_run_id\": \"$RUN\", \"devices\": \"1 smartwatch\", \"rate_hz\": 1.0, \"duration_s\": 60, \"scenario\": \"smoke\"}" \
    'expected_artefacts=["simulator/*/sent_events.jsonl", "simulator/*/events.jsonl", "simulator/*.marker.json", "simulator/*.metrics.before.json", "simulator/*.metrics.after.json", "simulator/*.twins.before.json", "simulator/*.twins.after.json", "simulator/*.reconcile.json"]')
P=$HOME/egw-tcg/itest
(cd "$REPO/src" && $LE add-source --attempt "$A" --kind simulator --path "$P/$RUN" --siblings-glob "$RUN.*" \
    --role "ad-hoc run directory and its sibling files (runbook 6.1 helpers)")

hx "$A" pre "pre $RUN $SEED smartwatch"
pre_rc=$?
sim_rc=1
if [ "$pre_rc" -eq 0 ]; then
    hx "$A" simulator-and-mark ": > \$P/$RUN.stderr.txt && \$SIM --scenario smoke --seed $SEED --devices smartwatch --rate 1.0 --duration 60 --run-id $RUN 2>&1 | tee \$P/$RUN.stderr.txt; ST=(\"\${PIPESTATUS[@]}\"); \$REC mark \$P/$RUN; MARK_RC=\$?; echo \"FLOW STATUS $RUN: simulator exit=\${ST[0]} transcript (tee) exit=\${ST[1]} mark exit=\$MARK_RC\"; [ \"\${ST[0]}\" = 0 ] && [ \"\${ST[1]}\" = 0 ] && [ -s \$P/$RUN.stderr.txt ] && [ \"\$MARK_RC\" = 0 ]"
    sim_rc=$?
fi
after_rc=1
if [ "$sim_rc" -eq 0 ]; then
    hx "$A" after "{ [ -f \$P/$RUN.window-closed.json ] || \$REC wait \$P/$RUN; } && drained && fetch $RUN && accounted $RUN && snap_pair $RUN after"
    after_rc=$?
    hx "$A" twin-readback "UUID=\$(python3 -c \"import json;print(json.loads(open('\$P/$RUN/sent_events.jsonl').readline())['device_uuid'])\") && twin $RUN \$UUID && python3 -m json.tool \$P/$RUN.twin.\$UUID.json"
fi
C=9; D=9; U=unknown
if [ "$after_rc" -eq 0 ]; then
    hx "$A" check "\$REC check \$P/$RUN"
    C=$?
    hx "$A" delta "\$REC delta \$P/$RUN"
    D=$?
    [ -e "$P/$RUN.unaccounted.txt" ] && U=yes || U=no
fi

# Verdicts, from the reconciliation file (never from exit codes alone).
ex "$A" verdict "$PY" -c '
import json, sys
p, C, D, U = sys.argv[1], int(sys.argv[2]), int(sys.argv[3]), sys.argv[4]
try:
    r = json.load(open(p))
except Exception as e:
    print(f"no reconciliation file: {e}"); sys.exit(2)
row = r.get("row", r)
keys = ["confirmation_deadline_source", "sent_valid", "delivered_unique", "lost", "late_confirmations",
        "double_accepted", "intended_invalid_accepted", "marker_lag_s"]
print(json.dumps({k: row.get(k) for k in keys}, indent=2))
ok = (C == 0 and D == 0 and U == "no" and row.get("lost") == 0 and row.get("late_confirmations") == 0
      and row.get("delivered_unique") == row.get("sent_valid") and row.get("double_accepted") == 0)
print("SLICE", "PASS" if ok else "FAIL", f"check={C} delta={D} unaccounted={U}")
sys.exit(0 if ok else 1)
' "$P/$RUN.reconcile.json" "$C" "$D" "$U"
vrc=$?

if [ "$pre_rc" -ne 0 ] || [ "$sim_rc" -ne 0 ]; then
    (cd "$REPO/src" && $LE finish --attempt "$A" --status failed --validity invalid --outcome not-run \
        --reason "precondition or simulator/marker failed (pre exit $pre_rc, simulator step exit $sim_rc)" \
        --next-action "read console/; the slice did not run as a protocol check")
elif [ "$after_rc" -ne 0 ] || [ "$C" -eq 3 ]; then
    (cd "$REPO/src" && $LE finish --attempt "$A" --status failed --validity invalid --outcome inconclusive \
        --reason "the after state or the controller marker was not captured (after exit $after_rc, check exit $C)" \
        --next-action "read console/")
elif [ "$vrc" -eq 0 ]; then
    (cd "$REPO/src" && $LE finish --attempt "$A" --status finished --validity valid --outcome pass \
        --reason "every published identity accounted; lost 0, late 0, twin and /metrics deltas OK" \
        --next-action "nominal entry 120 s + 600 s")
else
    (cd "$REPO/src" && $LE finish --attempt "$A" --status finished --validity valid --outcome fail \
        --reason "instrumentation complete but the delivery or counter criteria failed (check $C, delta $D, unaccounted $U)" \
        --next-action "diagnose before the nominal entry")
fi
export_attempt "$A"
