#!/bin/bash
# tools/compare/measure_series.sh <plan.json> - the six executions of the minimal comparison, in the
# plan's order, one guest at a time, each by measure_run.sh; then the harness analysis of the six raw
# runs and the summary (measure_summary.py). The plan given is the SEALED one: it is copied once to
# $EGW_COMPARE_ROOT/measure/<plan name>.working.<sha256 prefix>.json (the harness rewrites entry statuses
# there; a sidecar .source names the sealed plan it came from, and a working copy is continued only for
# the plan it was made from) and its sha256 is recorded. Before each execution the previous guest must be gone (no QEMU at all). The
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
[ -r "$SEALED" ] || die "plan not readable: $SEALED"
SEALED_SHA=$(sha256sum "$SEALED" | cut -d' ' -f1)
SEALED_NAME=$(basename "$SEALED")
# One working copy per sealed plan, keyed by the plan's own digest: two sealed plans that share a file
# name never share a working copy, and a working copy is continued only for the bytes it came from.
WORKING=$MEASURE/${SEALED_NAME%.json}.working.${SEALED_SHA:0:12}.json
HARNESS=$MEASURE/harness
VENV=${EGW_EXEC_VENV:-$COMPARE_EXEC/venv}
PY=$VENV/bin/python
MEASURE_RUN=${EGW_COMPARE_MEASURE_RUN:-$HERE/measure_run.sh}
mkdir -p "$MEASURE/logs"
LOG=$MEASURE/logs/series-$(stamp).log
exec > >(tee -a "$LOG") 2>&1
echo "SERIES: $(utc_now) plan $SEALED sha256 $(sha256sum "$SEALED" | cut -d' ' -f1)"
if [ -e "$WORKING" ]; then
    # The sidecar names the sealed plan the working copy came from; a mismatch is a refusal, never a guess.
    src=$(sed -n 's/^sha256 //p' "$WORKING.source" 2> /dev/null)
    [ "$src" = "$SEALED_SHA" ] || die "working plan $WORKING exists but was not made from this sealed plan (source sha256 '${src:-none}', given $SEALED_SHA)"
    echo "working plan exists ($WORKING, from sealed sha256 $SEALED_SHA): continuing it; entries already run are skipped"
else
    cp -p "$SEALED" "$WORKING" || die "cannot write the working plan"
    printf 'path %s\nsha256 %s\nutc %s\n' "$SEALED" "$SEALED_SHA" "$(utc_now)" > "$WORKING.source"
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
    # stdin from /dev/null: the driver (and the tools it runs) must never read the loop's own input,
    # which once swallowed the remaining entries and ended a series after its second execution.
    bash "$MEASURE_RUN" "$sc" "$rid" "$WORKING" < /dev/null
    rc=$?
    echo "== $rid ($sc): measure_run exit $rc at $(utc_now)"
    if [ "$rc" -ne 0 ]; then echo "STOP: the series stops after $rid (exit $rc): data preserved, nothing repeated; inspect $MEASURE/runs/$rid"; exit 1; fi
done <<< "$ORDER"

echo "== analysis of the raw runs ($HARNESS)"
"$PY" -m egw_experiments analyze --base-dir "$HARNESS" --plan "$WORKING" > "$MEASURE/logs/analyze-$(stamp).log" 2>&1 || echo "WARNING: the analyser exited non-zero (see the analyze log); the summary uses what it wrote"
OUT=$MEASURE/summary-$(stamp)
python3 "$HERE/measure_summary.py" --measure-root "$MEASURE" --plan "$WORKING" --per-run-csv "$HARNESS/processed/per_run.csv" --out "$OUT" || { echo "STOP: the summary failed"; exit 1; }
echo "SERIES: done; summary in $OUT"
