#!/bin/bash
# Bench of the plan step of g3_hostprep.sh (S4) on COPIES only (WSL). The content
# check is cut out of g3_hostprep.sh (the text between the line ending "<< 'PLAN_CHECK'"
# and the line "PLAN_CHECK") and run on copies of the pilot plan under
# /tmp/g3-s4-host-plan; plan-supplement is the merged module, copied from the read-only
# worktree of 1fd9792 into the bench folder. HOME points inside the bench folder; the
# real HOME is neither read nor written by this script (the plan copy it starts from
# was made beforehand by a read-only cp: ro_look.console.txt). g3_hostprep.sh itself is
# not run.
# Usage (WSL): bash host-record/plan_check_bench.sh   (from the preparation folder)
set -u
cd "$(dirname "$0")/.." || exit 2
B=/tmp/g3-s4-host-plan
case $B in /tmp/g3-s4-*) ;; *) echo "refused: $B"; exit 2 ;; esac
PYV=/home/ruisth/egw-exec/venv/bin/python   # read-only use: no bytecode, the module comes from the bench copy
export HOME=$B/home PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=$B/src
ORIG=$B/campaign_plan.json
BEFORE=c195bd3faa9607aae7c091b1e7e59b451b74afe484fa179cfa2aad7af8f28a60
AFTER=61d55940fcccdb942ff508ab6fc920b0fa163837ef7459438d789a1879b1eaac
[ -f "$ORIG" ] || { echo "no plan copy at $ORIG"; exit 2; }
PASS=0 FAIL=0
ok() { echo "PASS $*"; PASS=$((PASS + 1)); }
ko() { echo "FAIL $*"; FAIL=$((FAIL + 1)); }
sha() { sha256sum "$1" | cut -d' ' -f1; }

echo "g3_hostprep.sh sha256 $(sha g3_hostprep.sh) (the bytes the check was cut from)"
echo "plan copy: sha256 $(sha "$ORIG")"
[ "$(sha "$ORIG")" = "$BEFORE" ] && ok "P0 the copy is the plan of today ($BEFORE)" || ko "P0 the copy is not $BEFORE"
rm -rf "$B/src" "$B/cases" "$B/home" "$B/plan_check.py"
mkdir -p "$B/src" "$B/cases" "$HOME" || exit 2
cp -r ../../t6m/src/egw_experiments "$B/src/" || exit 2
rm -rf "$B/src/egw_experiments/__pycache__"
echo "module copy: plan_gen.py sha256 $(sha "$B/src/egw_experiments/plan_gen.py"), cli.py sha256 $(sha "$B/src/egw_experiments/cli.py")"
sed -n "/<< 'PLAN_CHECK'/,/^PLAN_CHECK\$/p" g3_hostprep.sh | sed '1d;$d' > "$B/plan_check.py"
echo "content check cut out: $(wc -l < "$B/plan_check.py") lines, sha256 $(sha "$B/plan_check.py")"
check() {   # check <plan> <predecessor or -> : the content check's exit status, its console indented
    "$PYV" "$B/plan_check.py" "$1" "$2" "$BEFORE" > "$B/check.out" 2>&1
    local rc=$?
    sed 's/^/    | /' "$B/check.out"
    return "$rc"
}
supplement() {   # supplement <plan>: the merged plan-supplement, as the host preparation runs it (from src)
    (cd "$B/src" && "$PYV" -m egw_experiments plan-supplement --plan "$1" --entry g3-t6) > "$B/supp.out" 2>&1
    local rc=$?
    sed "s|$B|<bench>|g; s/^/    | /" "$B/supp.out"
    return "$rc"
}

echo; echo "## P1 the plan of today plus the entry, with the predecessor kept"
mkdir -p "$B/cases/p1" && cp -p "$ORIG" "$B/cases/p1/campaign_plan.json" && cp -p "$ORIG" "$B/cases/p1/predecessor.json"
ls -A1 "$B/cases/p1" > "$B/cases/p1.before"
supplement "$B/cases/p1/campaign_plan.json"; rc=$?
ls -A1 "$B/cases/p1" > "$B/cases/p1.after"
echo "plan-supplement exit=$rc; plan-supplement on the copy: sha256 $(sha "$B/cases/p1/campaign_plan.json")"
[ "$rc" -eq 0 ] && [ "$(sha "$B/cases/p1/campaign_plan.json")" = "$AFTER" ] && ok "P1a plan-supplement adds the entry: sha256 $AFTER" || ko "P1a plan-supplement"
cmp -s "$B/cases/p1.before" "$B/cases/p1.after" && ok "P1b the folder holds the same names before and after (its temporary file is gone)" || ko "P1b the folder changed"
check "$B/cases/p1/campaign_plan.json" "$B/cases/p1/predecessor.json" && ok "P1c the content check passes with the predecessor" || ko "P1c the content check"
grep -q '^plan check: OK' "$B/check.out" && ok "P1d the check says OK" || ko "P1d no OK line"
cmp -s "$ORIG" "$B/cases/p1/predecessor.json" && ok "P1e the predecessor copy is unchanged by the check" || ko "P1e predecessor changed"

echo; echo "## P2 a re-run: the plan already holds the entry"
cp -p "$B/cases/p1/campaign_plan.json" "$B/cases/p1.with-entry"
supplement "$B/cases/p1/campaign_plan.json"; rc=$?
[ "$rc" -eq 0 ] && cmp -s "$B/cases/p1/campaign_plan.json" "$B/cases/p1.with-entry" && grep -q 'already holds' "$B/supp.out" \
    && ok "P2a plan-supplement leaves a plan that holds the entry unchanged (exit 0, 'already holds')" || ko "P2a re-run"
check "$B/cases/p1/campaign_plan.json" - && ok "P2b the content check passes without a predecessor (bytes proved by the sha256)" || ko "P2b"
grep -q 'no predecessor in this record' "$B/check.out" && ok "P2c it says that no predecessor was compared" || ko "P2c"

GOOD=$B/cases/p1.with-entry
mutate() {   # mutate <case> <python expression on the text t>: a modified copy of the good plan
    mkdir -p "$B/cases/$1"
    "$PYV" -c 'import sys; t = open(sys.argv[1], "rb").read().decode(); exec("t = " + sys.argv[3]); open(sys.argv[2], "wb").write(t.encode())' \
        "$GOOD" "$B/cases/$1/campaign_plan.json" "$2"
}
refused() {   # refused <id> <text> <plan> <predecessor>: the check must end 1 with a NOT OK line or its own stop line
    if check "$3" "$4"; then ko "$1 $2: the check passed"
    elif grep -qE '^plan check: (NOT OK|the plan does not end)' "$B/check.out"; then ok "$1 $2: refused"
    else ko "$1 $2: ended non-zero without its own line"; fi
}

echo; echo "## P3 what the check must refuse"
mutate p3a 't.replace("\"status\": \"completed\"", "\"status\": \"planned\"", 1) if "\"status\": \"completed\"" in t else t.replace("\"status\": \"planned\"", "\"status\": \"excluded\"", 1)'
refused P3a "an earlier entry's status changed" "$B/cases/p3a/campaign_plan.json" -
mutate p3b 't.replace("\"seed\": 1715385812", "\"seed\": 1715385813")'
refused P3b "the new entry's seed changed" "$B/cases/p3b/campaign_plan.json" -
mutate p3c 't.replace("\"supplement\": \"g3-t6\",", "\"supplement\": \"g3-t6\",\n      \"extra\": 1,")'
refused P3c "a field added to the new entry" "$B/cases/p3c/campaign_plan.json" -
mutate p3d 't.replace("\"master_seed\": ", "\"master_seed\": 1", 1)'
refused P3d "a field outside 'runs' changed" "$B/cases/p3d/campaign_plan.json" -
mutate p3e '__import__("json").dumps(__import__("json").loads(t))'
refused P3e "a plan not in the canonical form" "$B/cases/p3e/campaign_plan.json" -
mkdir -p "$B/cases/p3f" && cp -p "$GOOD" "$B/cases/p3f/campaign_plan.json"
"$PYV" -c 'import sys; p = sys.argv[1]; t = open(p, "rb").read(); open(p, "wb").write(t.replace(b"\"warmup_s\": 0\n    }\n  ]", b"\"warmup_s\": 0\n    },\n    {\n      \"run_id\": \"x\"\n    }\n  ]", 1) if t.endswith(b"\"warmup_s\": 0\n    }\n  ]\n}\n") else t)' "$B/cases/p3f/campaign_plan.json"
refused P3f "an entry after controller_restart-r04" "$B/cases/p3f/campaign_plan.json" -
mkdir -p "$B/cases/p3g" && "$PYV" -c 'import sys; t = open(sys.argv[1], "rb").read(); i = t.index(b"\"seed\": "); open(sys.argv[2], "wb").write(t[:i] + b"\"seed\": 1" + t[i + 8:])' "$ORIG" "$B/cases/p3g/predecessor.json"
refused P3g "a kept predecessor that is not the plan without its last entry" "$GOOD" "$B/cases/p3g/predecessor.json"
refused P3h "the plan of today itself (no entry added)" "$ORIG" -

echo
echo "summary: $PASS PASS, $FAIL FAIL"
rm -rf "$B/src" "$B/home"
[ "$FAIL" -eq 0 ]
