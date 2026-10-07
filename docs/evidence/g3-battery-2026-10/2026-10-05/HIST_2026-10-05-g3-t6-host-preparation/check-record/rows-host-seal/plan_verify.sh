#!/bin/bash
# Independent reviewer's check (read-only on the host): copy of the real plan into /tmp,
# the merged plan-supplement on the copy, then the PLAN_CHECK heredoc cut out of g3_hostprep.sh.
set -u
S=/mnt/c/Users/ruimf/AppData/Local/Temp/claude/C--Users-ruimf-Documents-Projeto-Mestrado/d631a3f3-65ca-4372-97f1-525d6d1e593d/scratchpad
P=$S/g3/t6prep
T=$(mktemp -d /tmp/g3-s4-check-plan2.XXXXXX)
trap 'rm -rf "$T"' EXIT
export PYTHONDONTWRITEBYTECODE=1
mkdir -p "$T/pilot" "$T/code"
tar -x -C "$T/code" -f "$P/check/rows-host-seal/egw_experiments.1fd9792.tar"
cp ~/egw-tcg/pilot/campaign_plan.json "$T/pilot/campaign_plan.json"
cp ~/egw-tcg/pilot/campaign_plan.json "$T/pred.json"
echo "before: $(sha256sum < "$T/pilot/campaign_plan.json")"
(cd "$T/code/src" && PYTHONPATH="$T/code/src" ~/egw-exec/venv/bin/python -c 'import egw_experiments; print(egw_experiments.__file__)')
(cd "$T/code/src" && PYTHONPATH="$T/code/src" ~/egw-exec/venv/bin/python -m egw_experiments plan-supplement --plan "$T/pilot/campaign_plan.json" --entry g3-t6); echo "rc=$?"
echo "after: $(sha256sum < "$T/pilot/campaign_plan.json")"
ls -A1 "$T/pilot"
sed -n '/^"\$PY" - "\$PLAN" "\$PRED" "\$PLAN_BEFORE_SHA" << .PLAN_CHECK./,/^PLAN_CHECK$/p' "$P/g3_hostprep.sh" | sed '1d;$d' > "$T/check.py"
echo "check.py lines: $(wc -l < "$T/check.py")"
echo "== with predecessor"
~/egw-exec/venv/bin/python "$T/check.py" "$T/pilot/campaign_plan.json" "$T/pred.json" c195bd3faa9607aae7c091b1e7e59b451b74afe484fa179cfa2aad7af8f28a60; echo "rc=$?"
echo "== without predecessor"
~/egw-exec/venv/bin/python "$T/check.py" "$T/pilot/campaign_plan.json" - c195bd3faa9607aae7c091b1e7e59b451b74afe484fa179cfa2aad7af8f28a60; echo "rc=$?"
echo "== second plan-supplement (idempotent)"
(cd "$T/code/src" && PYTHONPATH="$T/code/src" ~/egw-exec/venv/bin/python -m egw_experiments plan-supplement --plan "$T/pilot/campaign_plan.json" --entry g3-t6); echo "rc=$?"
echo "after2: $(sha256sum < "$T/pilot/campaign_plan.json")"
echo "== last 30 lines of the new plan"
tail -n 20 "$T/pilot/campaign_plan.json"
echo "== statuses of controller_restart entries"
~/egw-exec/venv/bin/python -c 'import json,sys; p=json.load(open(sys.argv[1])); [print(r["run_id"], r.get("status"), r.get("order")) for r in p["runs"] if r["run_id"].startswith("controller_restart")]; print(sorted(p.keys()))' "$T/pilot/campaign_plan.json"
