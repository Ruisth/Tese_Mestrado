#!/bin/bash
# tools/compare/measure_series.sh <plan.json> - the six executions of the minimal comparison, in the
# plan's order, one guest at a time, each by measure_run.sh; then the harness analysis of the six raw
# runs and the summary (measure_summary.py). The plan given is the SEALED one: it is copied once to
# $EGW_COMPARE_ROOT/measure/<plan name>.working.json (the harness rewrites entry statuses there) and its
# sha256 is recorded. Before each execution the previous guest must be gone (no QEMU at all). The
# series stops at the first instrumentation failure or failed stop (data preserved, nothing repeated,
# nothing replaced); a result of the system under test never stops it. It never repeats an entry: an
# entry that is not `planned` in the working plan is skipped with a line saying so, which is how a
# series interrupted by hand is resumed.
# Exit: 0 every planned entry ran and the summary was written; 1 stopped at a failure; 2 prerequisite.
# Transcript: $EGW_COMPARE_ROOT/measure/logs/series-<stamp>.log
set -u
HERE=$(cd "$(dirname "$0")" && pwd)
# shellcheck source=lib.sh
. "$HERE/lib.sh"
[ $# -eq 1 ] || { echo "usage: measure_series.sh <plan.json>" >&2; exit 2; }
SEALED=$1
MEASURE=$COMPARE_ROOT/measure
SEALED_NAME=$(basename "$SEALED")
WORKING=$MEASURE/${SEALED_NAME%.json}.working.json   # one working copy per sealed plan, never shared
HARNESS=$MEASURE/harness
VENV=${EGW_EXEC_VENV:-$COMPARE_EXEC/venv}
PY=$VENV/bin/python
[ -r "$SEALED" ] || die "plan not readable: $SEALED"
mkdir -p "$MEASURE/logs"
LOG=$MEASURE/logs/series-$(stamp).log
exec > >(tee -a "$LOG") 2>&1
echo "SERIES: $(utc_now) plan $SEALED sha256 $(sha256sum "$SEALED" | cut -d' ' -f1)"
if [ -e "$WORKING" ]; then
    echo "working plan exists ($WORKING): continuing it; entries already run are skipped"
else
    cp -p "$SEALED" "$WORKING" || die "cannot write the working plan"
fi

ORDER=$(python3 - "$WORKING" << 'PY'
import json, sys
plan = json.load(open(sys.argv[1], encoding="utf-8"))
comp = plan.get("comparison", {}).get("runs", {})
for r in plan.get("runs", []):
    rid = r["run_id"]
    sc = (comp.get(rid) or r.get("comparison") or {}).get("scenario", "")
    print(rid, sc, r.get("status", ""))
PY
) || die "the plan could not be read"

while read -r rid sc status; do
    [ -n "$rid" ] || continue
    if [ "$status" != planned ]; then echo "== $rid ($sc): status '$status', skipped (never repeated)"; continue; fi
    [ -n "$sc" ] || die "the plan names no scenario for $rid (comparison block)"
    if o=$(qemu_others); then echo "$o"; echo "STOP: a QEMU is running before $rid; the series stops"; exit 1; elif [ $? -eq 2 ]; then echo "STOP: pgrep could not answer"; exit 1; fi
    echo "== $rid ($sc): $(utc_now)"
    bash "$HERE/measure_run.sh" "$sc" "$rid" "$WORKING"
    rc=$?
    echo "== $rid ($sc): measure_run exit $rc at $(utc_now)"
    if [ "$rc" -ne 0 ]; then echo "STOP: the series stops after $rid (exit $rc): data preserved, nothing repeated; inspect $MEASURE/runs/$rid"; exit 1; fi
done <<< "$ORDER"

echo "== analysis of the raw runs ($HARNESS)"
"$PY" -m egw_experiments analyze --base-dir "$HARNESS" --plan "$WORKING" > "$MEASURE/logs/analyze-$(stamp).log" 2>&1 || echo "WARNING: the analyser exited non-zero (see the analyze log); the summary uses what it wrote"
OUT=$MEASURE/summary-$(stamp)
python3 "$HERE/measure_summary.py" --measure-root "$MEASURE" --per-run-csv "$HARNESS/processed/per_run.csv" --out "$OUT" || { echo "STOP: the summary failed"; exit 1; }
echo "SERIES: done; summary in $OUT"
