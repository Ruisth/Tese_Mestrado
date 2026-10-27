#!/bin/bash
# Dry run of the row file of G3 session S4 (test 6 only): t6.sh, the eight host$ lines of the
# merged runbook, sourced in the form of the steps script's hx step (one bash -c, stderr
# joined, the carriers unset as STEP_PRE unsets them, 'set -v', the file sourced, stdin
# closed) against stub helpers, in ten cases: the entry already used (its raw directory, then
# its .sut directory), no seed in the plan, the harness answering 2, 3 and 1, the drain giving
# up, and a quiet sealed run with delta and the exactly-once check answering 0 and 0, 0 and 4,
# 4 and 0. Then a self-test of g3_check_rows.sh in its blob mode on altered copies.
# ISOLATED: everything lives in a temporary directory /tmp/g3-s4-dry-rows.*; HOME of the
# steps and of the checker is inside it (line 2 reads a pilot plan written there, which
# holds the r04 entry of the request, or, for the no-seed case, only r03); EGW_EXEC_REPO and
# EGW_CLONE point inside it (no clone is there: blob mode reads none, and no hook runs); the
# steps run with stub 'ssh', 'scp', 'python', 'timeout', 'sleep', 'curl', 'sudo' and 'docker'
# first on PATH and refuse to go on unless 'ssh' and 'python' resolve to the stubs; the
# helpers (stop, wait_ready, drained, config_identity, harness_cmd) are stub functions sourced
# in the step's shell, and REC is the runbook's own value, so delta and acceptance reach the
# stub 'python'; 'python3' is the system's and reads only files inside the temporary
# directory. The checker runs with a stub 'git' first on PATH that records every call (none
# is expected). Nothing real is contacted: no guest, no ssh, no harness, no clone. The
# temporary directory is removed at the end. The exit status is 0 only when every outcome was
# the expected one.
# Usage (WSL): bash g3_rows_dryrun.sh <rows directory> <g3_check_rows.sh> <runbook blob file> [<the battery's t6.sh>]
set -u
USAGE="usage: g3_rows_dryrun.sh <rows directory> <g3_check_rows.sh> <runbook blob file> [<the battery's t6.sh>]"
ROWS=$(cd "${1:?$USAGE}" && pwd) || exit 2
CHECK=${2:?$USAGE}
BLOB=${3:?$USAGE}
OLD_T6=${4:-}
T=$(mktemp -d /tmp/g3-s4-dry-rows.XXXXXX) || exit 2
trap 'rm -rf "$T"' EXIT
mkdir -p "$T/bin" "$T/bin-check"
miss=0
unexpected() { echo "$*"; miss=$((miss + 1)); }

# every command a row file could reach outside the helpers: it only says that it was called, and fails
for c in ssh scp timeout sleep curl sudo docker; do
    printf '%s\n' '#!/bin/bash' "printf 'STUB $c:'; printf ' [%s]' \"\$@\"; echo" 'exit 1' > "$T/bin/$c"
done
# stub python: delta and acceptance (through REC) answer DRY_DELTA_RC and DRY_ACCEPT_RC; analyze answers 0
cat > "$T/bin/python" <<'EOF'
#!/bin/bash
printf 'STUB python argc=%s:' "$#"; printf ' [%s]' "$@"; echo
case " $* " in
    *" -m egw_experiments.itest_reconcile delta "*) exit "${DRY_DELTA_RC:-0}" ;;
    *" -m egw_experiments.itest_reconcile acceptance "*) exit "${DRY_ACCEPT_RC:-0}" ;;
    *" -m egw_experiments analyze "*) exit 0 ;;
esac
exit 1
EOF
chmod +x "$T/bin"/*
cat > "$T/bin-check/git" <<'EOF'
#!/bin/bash
# stub git for the checker in blob mode: any call is recorded and fails
echo "git $*" >> "$G3_DRY_GIT_CALLS"
echo "STUB git: called (blob mode must not read a clone): $*" >&2
exit 99
EOF
chmod +x "$T/bin-check/git"

# stub helpers of the runbook's helper file (6.1): each says that it was called; harness_cmd also
# prints its environment and leaves what the case asks for (DRY_HARNESS) in the run directory
cat > "$T/helpers.sh" <<'EOF'
P=$HOME/egw-tcg/itest
REC="python -m egw_experiments.itest_reconcile"
stop() { echo "STOP: $*" >&2; return 1; }
wait_ready() { echo "CALLED: wait_ready $*"; }
drained() { echo "CALLED: drained $*"; }
config_identity() { echo "CALLED: config_identity $*"; }
harness_cmd() {
    local raw=$HOME/egw-tcg/pilot/results/raw/$1
    printf 'CALLED: harness_cmd argc=%s:' "$#"; printf ' [%s]' "$@"; echo
    echo "CALLED: harness_cmd environment: EVENTS_EXPECTED=${EVENTS_EXPECTED-<unset>} DRAIN_QUIET_S=${DRAIN_QUIET_S-<unset>} DRAIN_STEP_S=${DRAIN_STEP_S-<unset>} DRAIN_LIMIT_S=${DRAIN_LIMIT_S-<unset>}"
    case $DRY_HARNESS in
        quiet|gave-up)
            mkdir -p "$raw" || return 1
            printf '{"drain": {"outcome": "%s"}, "resources_proved_down": {"applies": true, "why_not": null, "die_utc": "D", "start_utc": "S", "effective_end_utc": "E", "capped": false, "edge_gap_before_s": 1.0, "edge_gap_after_s": 1.0, "rejected_rows": [], "resources_ingested": true}, "resources_transition_rows": {"rule": "1a-option-a-2026-10-05", "admitted": true, "why_not": null, "resources_ingested": true, "count": 2, "instants": ["I1", "I2"]}}\n' "$DRY_HARNESS" > "$raw/manifest.json"
            echo stub > "$raw/SHA256SUMS"
            return 0 ;;
        1|3) mkdir -p "$raw" && echo '{}' > "$raw/manifest.json"; return "$DRY_HARNESS" ;;
        *) return "$DRY_HARNESS" ;;
    esac
}
EOF

# the pilot plan line 2 reads: r03 and the r04 entry of the request (section 3; the brief's fixed values)
R03='{"condition_id": "controller_restart", "run_id": "controller_restart-r03", "seed": 1, "status": "done"}'
R04='{"condition_id": "controller_restart", "cooldown_s": 0, "duration_s": 600, "order": 96, "rate_msg_s": 11.2, "repetition": 4, "run_id": "controller_restart-r04", "runner": "simulator", "scenario": "nominal", "seed": 1715385812, "status": "planned", "supplement": "g3-t6", "warmup_s": 0}'
home() { # home with|without: a fresh HOME holding the pilot plan, with or without the r04 entry
    rm -rf "$T/home"; mkdir -p "$T/home/egw-tcg/pilot/results/raw" "$T/home/egw-tcg/itest"
    if [ "$1" = with ]; then printf '{"runs": [%s, %s]}\n' "$R03" "$R04"; else printf '{"runs": [%s]}\n' "$R03"; fi > "$T/home/egw-tcg/pilot/campaign_plan.json"
}
# the form of the steps script's hx step: one bash -c, stderr joined, the carriers unset (STEP_PRE),
# set -v, the file sourced, stdin closed; the case's controls are set before, and are not echoed
step() { # step <bash text run before the carriers are unset>
    env -i HOME="$T/home" PATH="$T/bin:/usr/bin:/bin" EGW_CLONE="$T/egw-clone" "$(command -v bash)" --norc --noprofile -c \
        "exec 2>&1; [ \"\$(command -v ssh)\" = '$T/bin/ssh' ] && [ \"\$(command -v python)\" = '$T/bin/python' ] || { echo 'STOP: ssh or python is not the stub'; exit 99; }; . '$T/helpers.sh'; $1; unset DEVICES ACCEPT_UNACCOUNTED EVENTS_EXPECTED DRAIN_QUIET_S DRAIN_STEP_S DRAIN_LIMIT_S READY_LIMIT_S; set -v; . '$ROWS/t6.sh'" < /dev/null
    echo "[step t6.sh ended with status $?]"
}
n_of() { printf '%s\n' "$2" | grep -c -- "$1"; }
# case_ <label> <plan: with|without r04> <files made first> <controls> <STOP lines> <harness calls> <delta calls> <acceptance calls> [<pattern the console must hold>...]
case_() {
    local label=$1 plan=$2 files=$3 controls=$4 w_s=$5 w_h=$6 w_d=$7 w_a=$8 out echoed s hc pre dc ac an x ok=1
    shift 8
    home "$plan"
    eval "$files"
    out=$(step "$controls")
    echo "### $label"
    printf '%s\n' "$out" | grep '^STOP: \|^CALLED: \|^STUB \|^test 6: \|^\[step \|^Traceback\|Error' | cut -c1-260
    echoed=$(printf '%s\n' "$out" | grep -cxF -f "$ROWS/t6.sh")
    s=$(n_of '^STOP: ' "$out"); hc=$(n_of '^CALLED: harness_cmd argc=' "$out")
    pre=$(n_of '^CALLED: \(wait_ready\|drained\|config_identity\) ' "$out")
    dc=$(n_of '^STUB python argc=.* \[egw_experiments.itest_reconcile\] \[delta\]' "$out")
    ac=$(n_of '^STUB python argc=.* \[egw_experiments.itest_reconcile\] \[acceptance\]' "$out")
    an=$(n_of '^STUB python argc=.* \[egw_experiments\] \[analyze\]' "$out")
    [ "$echoed" = 8 ] && [ "$s" = "$w_s" ] && [ "$hc" = "$w_h" ] && [ "$pre" = $((3 * w_h)) ] && [ "$dc" = "$w_d" ] && [ "$ac" = "$w_a" ] && [ "$an" = 1 ] || ok=0
    for x in "$@"; do printf '%s\n' "$out" | grep -q -- "$x" || { ok=0; echo "missing from the console: $x"; }; done
    if [ "$ok" = 1 ]; then
        echo "as expected: the 8 lines echoed by set -v; $s STOP: line(s); harness_cmd called $hc time(s), after $pre call(s) of wait_ready, drained and config_identity; delta $dc, acceptance $ac, analyze $an"
    else
        unexpected "NOT AS EXPECTED: $label: echoed $echoed (8), STOP: $s ($w_s), harness_cmd $hc ($w_h), pre-harness calls $pre ($((3 * w_h))), delta $dc ($w_d), acceptance $ac ($w_a), analyze $an (1)"
    fi
    echo
}
RAWQ='\[.*/egw-tcg/pilot/results/raw/controller_restart-r04'
echo "## t6.sh in the step form, ten cases (shown: the lines of the stubs, of stop and of the block's own 'test 6:' prints; set -v's echo of the eight lines is counted, not shown)"
echo
case_ "1. r04 already used, its raw directory exists: line 1 refuses (F6=used), nothing starts, no delta, no acceptance" \
    with 'mkdir -p "$T/home/egw-tcg/pilot/results/raw/controller_restart-r04"' 'DRY_HARNESS=none' 4 0 0 0 \
    '^STOP: test 6: controller_restart-r04 was already used' "^STOP: test 6: controller_restart-r04 refused as already used (F6='used')"
case_ "2. r04 already used, its .sut directory exists: the same refusal" \
    with 'mkdir -p "$T/home/egw-tcg/itest/controller_restart-r04.sut"' 'DRY_HARNESS=none' 4 0 0 0 \
    '^STOP: test 6: controller_restart-r04 was already used' "^STOP: test 6: controller_restart-r04 refused as already used (F6='used')"
case_ "3. the pilot plan without r04: no seed, nothing starts" \
    without : 'DRY_HARNESS=none' 3 0 0 0 \
    "^STOP: test 6: controller_restart-r04 refused as already used (F6='fresh'), no seed"
case_ "4. harness_cmd answers 2 (the harness not started): no manifest is read, T6 not ok" \
    with : 'DRY_HARNESS=2' 3 1 0 0 \
    '^test 6: resources_proved_down: not read - harness_cmd answered 2' '^STOP: test 6: the harness run was not sealed, or it exited 2' \
    "^STOP: test 6: delta NOT run (T6='stop')" "^STOP: test 6: the per-identity exactly-once check was not run (T6='stop')"
case_ "5. harness_cmd answers 3 (the recorder's cleanup failed): T6=incomplete" \
    with : 'DRY_HARNESS=3' 3 1 0 0 \
    '^test 6: resources_proved_down: not recorded' '^test 6: resources_transition_rows: not recorded' \
    '^STOP: test 6: the procedure is INCOMPLETE' "^STOP: test 6: delta NOT run (T6='incomplete')"
case_ "6. harness_cmd answers 1 (an invalid run): T6 not ok" \
    with : 'DRY_HARNESS=1' 3 1 0 0 \
    '^STOP: test 6: the harness run was not sealed, or it exited 1'
case_ "7. harness 0, sealed, the drain gave up: T6=gaveup, no delta, no acceptance" \
    with : 'DRY_HARNESS=gave-up' 3 1 0 0 \
    "^STOP: test 6: the drain gave up (manifest drain.outcome 'gave-up')" "^STOP: test 6: delta NOT run (T6='gaveup')" \
    "^STOP: test 6: the per-identity exactly-once check was not run (T6='gaveup')"
case_ "8. harness 0, sealed, the drain quiet; delta 0; acceptance --exactly-once 0: T6=ok and no STOP" \
    with : 'export DRY_HARNESS=quiet DRY_DELTA_RC=0 DRY_ACCEPT_RC=0' 0 1 1 1 \
    '^CALLED: harness_cmd argc=17: \[controller_restart-r04\] \[--restart-cmd\] ' \
    "\[--restart-cmd\] \[ssh egw-tcg 'cd /opt/egw/deployment && docker compose --env-file .env --env-file images.lock.env restart controller'\] \[--restart-at-s\] \[300\] " \
    '\[--config-identity-from\] \[.*/egw-tcg/itest/controller_restart-r04.config_identity.json\] ' \
    '/tools/session/proof_hook_twins.sh" {run_id} "{dest}" 1715385812\] ' \
    '\[--restart-transition-rule\] \[1a-option-a-2026-10-05\]$' \
    '^CALLED: harness_cmd environment: EVENTS_EXPECTED=die,start DRAIN_QUIET_S= DRAIN_STEP_S= DRAIN_LIMIT_S=$' \
    '^test 6: resources_proved_down: applies=True ' '^test 6: resources_transition_rows: rule=1a-option-a-2026-10-05 admitted=True ' \
    '^test 6: harness exit 0 and the recorder' \
    "\[delta\] $RAWQ\] \[--prefix\] \[.*/egw-tcg/itest/controller_restart-r04\] \[--events\] $RAWQ/events.post-drain.jsonl\] " \
    "\[acceptance\] $RAWQ/logs/simulator/controller_restart-r04\] \[--events\] $RAWQ/events.post-drain.jsonl\] \[--exactly-once\]$" \
    '\[analyze\] \[--base-dir\] \[.*/egw-tcg/pilot/results\] \[--plan\] \[.*/egw-tcg/pilot/campaign_plan.json\]$'
case_ "9. the same, acceptance --exactly-once answers 4 (a valid message absent, duplicate-only or accepted twice): one STOP, line 7's" \
    with : 'export DRY_HARNESS=quiet DRY_DELTA_RC=0 DRY_ACCEPT_RC=4' 1 1 1 1 \
    '^STOP: test 6: the per-identity exactly-once check was not run (T6=.ok.), could not read its inputs (exit 1: test 6 NOT evaluated) or found'
case_ "10. the same, delta answers 4 (MISMATCH): one STOP, line 6's; line 7 still runs (it reads T6 only)" \
    with : 'export DRY_HARNESS=quiet DRY_DELTA_RC=4 DRY_ACCEPT_RC=0' 1 1 1 1 \
    "^STOP: test 6: delta NOT run (T6='ok') or it exited non-zero (4 = MISMATCH)"

echo "## self-test of the checker in blob mode: each altered copy must be refused"
export G3_DRY_GIT_CALLS="$T/git-calls"
: > "$G3_DRY_GIT_CALLS"
check() { # check <blob file> <rows directory>
    env -u EGW_G3_RUNBOOK_BLOB HOME="$T/home" EGW_EXEC_REPO="$T/home/egw-exec/repo" PATH="$T/bin-check:$PATH" bash "$CHECK" --blob "$1" "$2"
}
verdict() { # verdict <label> [<blob file>]: the checker on $T/rows must fail
    if out=$(check "${2:-$BLOB}" "$T/rows" 2>&1); then unexpected "NOT DETECTED: $1"; else echo "detected: $1 -> $(printf '%s\n' "$out" | grep -c '^FAIL') FAIL line(s), first: $(printf '%s\n' "$out" | grep -m1 '^FAIL' | cut -c1-200)"; fi
}
fresh() { rm -rf "$T/rows"; cp -r "$ROWS" "$T/rows"; }
alter() { # alter <label> <file> <sed expression>
    fresh
    sed -i "$3" "$T/rows/$2"
    if cmp -s "$ROWS/$2" "$T/rows/$2"; then unexpected "NOT ALTERED (the expression changed nothing): $1"; return; fi
    verdict "$1"
}
alter "the run id of session S2 (r03) in place of r04 (t6.sh line 1)" t6.sh '1s/^RID=controller_restart-r04; /RID=controller_restart-r03; /'
alter "an earlier session's suffix added to the run id (t6.sh line 1: controller_restart-r04-q2)" t6.sh '1s/^RID=controller_restart-r04; /RID=controller_restart-r04-q2; /'
alter "the exactly-once line removed (t6.sh line 7)" t6.sh '7d'
alter "the transition rule removed from the harness line (t6.sh line 5)" t6.sh '5s/ --restart-transition-rule 1a-option-a-2026-10-05; HR=/; HR=/'
alter "a changed character outside any literal (t6.sh line 5: --restart-at-s 300 -> 301)" t6.sh '5s/--restart-at-s 300 /--restart-at-s 301 /'
alter "a carriage return (t6.sh line 3)" t6.sh '3s/$/\r/'
alter "the manifest naming session S3 for row t6 (rows.manifest.json)" rows.manifest.json '0,/"session": "S4"/s//"session": "S3"/'
fresh; printf '%s\n' '+x' > "$T/rows/t6.sh.diff"
verdict "a non-empty t6.sh.diff"
fresh; printf '%s\n' ':' > "$T/rows/t8-a-reboot.sh"
verdict "a step file of session S3's names left in the directory (t8-a-reboot.sh)"
if [ -n "$OLD_T6" ]; then
    fresh; cp "$OLD_T6" "$T/rows/t6.sh"
    verdict "the battery's t6.sh (80e833f, seven lines, sha256 $(sha256sum < "$OLD_T6" | cut -c1-16)...) in place of S4's"
else
    echo "not run: the battery's t6.sh in place of S4's (no fourth argument)"
fi
fresh
if check "$BLOB" "$T/rows" > /dev/null 2>&1; then echo "the unaltered copy passes"; else unexpected "THE UNALTERED COPY FAILS"; fi
verdict "a blob file that does not exist (the unaltered copy)" "$T/no-such-blob"
printf 'x\n' | cat "$BLOB" - > "$T/blob-plus-one-line"
verdict "a blob file with one line appended (the unaltered copy)" "$T/blob-plus-one-line"
calls=$(wc -l < "$G3_DRY_GIT_CALLS")
[ "$calls" = 0 ] && echo "git calls made by the checker in blob mode: 0 (no clone is read)" || unexpected "git calls made by the checker in blob mode: $calls (0 expected)"
echo
[ "$miss" = 0 ] && echo "DRY RUN AS EXPECTED (0 unexpected outcomes)" || echo "DRY RUN NOT AS EXPECTED ($miss unexpected outcome(s))"
[ "$miss" = 0 ]
