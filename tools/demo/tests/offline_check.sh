#!/bin/bash
# tools/demo/tests/offline_check.sh - offline checks of the demonstration scripts. It starts nothing:
# no guest, QEMU, Terraform, Docker, ssh connection or secrets file is used.
#   1. bash -n on every script under tools/demo;
#   2. shellcheck --severity=error on the same scripts when shellcheck is installed (CI runs it on
#      every tracked script; here it is skipped when absent);
#   3. lib.sh helpers against stubs, in a clean environment with a throw-away HOME: scenario_canon,
#      scenario_check, the path defaults and their overrides, demo_key, current_run, inside_repo,
#      guest_running (stub compare_env.sh) and stack_ready (stub ssh on PATH);
#   4. wearables/simulate.sh --dry-run and wearables/stop.sh with no live simulation;
#   5. static rules: no personal paths, the secrets file sourced by simulate.sh only, no forced kill.
# Everything written goes to a temporary directory (under $TMPDIR when set) removed at the end.
# Exit 0 when every check passes, 1 otherwise.
set -u
HERE=$(cd "$(dirname "$0")" && pwd)
DEMO=$(cd "$HERE/.." && pwd)
REPO=$(cd "$DEMO/../.." && pwd)
TMP=$(mktemp -d "${TMPDIR:-/tmp}/egw-demo-check.XXXXXX") || { echo "cannot create a temporary directory"; exit 1; }
trap 'rm -rf "$TMP"' EXIT
H=$TMP/home
mkdir -p "$H" "$TMP/bin" "$TMP/stubtools"
pass=0
fail=0
skip=0
ok() { pass=$((pass + 1)); printf 'ok    %s\n' "$1"; }
ko() { fail=$((fail + 1)); printf 'FAIL  %s\n' "$1"; }
sk() { skip=$((skip + 1)); printf 'skip  %s\n' "$1"; }
# same NAME EXPECTED ACTUAL
same() { if [ "$2" = "$3" ]; then ok "$1"; else ko "$1 (expected '$2', got '$3')"; fi; }
# lib_eval [VAR=value ...] CODE: CODE run by bash with lib.sh sourced, in a clean environment whose
# HOME is the throw-away one and whose PATH starts with the stub directory.
lib_eval() {
    local assigns=()
    while [ $# -gt 1 ]; do assigns+=("$1"); shift; done
    env -i PATH="$TMP/bin:$PATH" HOME="$H" "${assigns[@]}" bash -c '. "$1" && eval "$2"' lib "$DEMO/lib.sh" "$1"
}
# rc_of CMD...: the exit status of CMD, output discarded.
rc_of() { "$@" > /dev/null 2>&1; echo $?; }

SCRIPTS=()
while IFS= read -r f; do SCRIPTS+=("$f"); done < <(find "$DEMO" -type f -name '*.sh' | sort)

echo "== 1. bash -n (${#SCRIPTS[@]} scripts)"
for f in "${SCRIPTS[@]}"; do
    if bash -n "$f" 2> "$TMP/syntax.err"; then ok "bash -n ${f#"$REPO"/}"; else ko "bash -n ${f#"$REPO"/}: $(head -n 1 "$TMP/syntax.err")"; fi
done

echo "== 2. shellcheck --severity=error"
if command -v shellcheck > /dev/null 2>&1; then
    if shellcheck --severity=error "${SCRIPTS[@]}"; then ok "shellcheck --severity=error"; else ko "shellcheck --severity=error"; fi
else
    sk "shellcheck not installed (CI runs it on every tracked script)"
fi

echo "== 3. lib.sh helpers (stubs, clean environment)"
# path defaults
same "default DEMO_REPO is the repository root" "$REPO" "$(lib_eval 'printf %s "$DEMO_REPO"')"
same "default DEMO_TOOLS is tools/compare" "$REPO/tools/compare" "$(lib_eval 'printf %s "$DEMO_TOOLS"')"
same "tf.sh exists under DEMO_TOOLS" 0 "$(rc_of test -f "$REPO/tools/compare/tf.sh")"
same "default comparison root" "$H/egw-compare" "$(lib_eval 'printf %s "$DEMO_COMPARE_ROOT"')"
same "default venv" "$H/egw-exec/venv" "$(lib_eval 'printf %s "$DEMO_VENV"')"
same "default secrets path" "$H/egw-tcg/.env" "$(lib_eval 'printf %s "$DEMO_SECRETS"')"
same "default state root" "$H/.local/state/egw-demo" "$(lib_eval 'printf %s "$DEMO_STATE_ROOT"')"
same "default state folder" "$H/.local/state/egw-demo/state" "$(lib_eval 'printf %s "$DEMO_STATE"')"
same "default runs folder" "$H/.local/state/egw-demo/runs" "$(lib_eval 'printf %s "$DEMO_RUNS"')"
same "default state folder is outside the repository" 1 "$(lib_eval 'inside_repo "$DEMO_STATE"; echo $?')"
same "default runs folder is outside the repository" 1 "$(lib_eval 'inside_repo "$DEMO_RUNS"; echo $?')"
same "default key for yocto" "$H/.ssh/egw_campaign" "$(lib_eval 'demo_key yocto')"
same "default key for debian13" "$H/.ssh/egw_campaign" "$(lib_eval 'demo_key debian13')"
same "default key for yoctowrynose" "$H/.ssh/egw_wrynose_share" "$(lib_eval 'demo_key yoctowrynose')"
# overrides
same "XDG_STATE_HOME moves the state root" "/x/state/egw-demo" "$(lib_eval XDG_STATE_HOME=/x/state 'printf %s "$DEMO_STATE_ROOT"')"
same "DEMO_STATE_ROOT moves the runs" "/y/runs" "$(lib_eval DEMO_STATE_ROOT=/y 'printf %s "$DEMO_RUNS"')"
same "DEMO_RUNS is honoured" "/z/r" "$(lib_eval DEMO_RUNS=/z/r 'printf %s "$DEMO_RUNS"')"
same "EGW_COMPARE_ROOT is honoured" "/c" "$(lib_eval EGW_COMPARE_ROOT=/c 'printf %s "$DEMO_COMPARE_ROOT"')"
same "EGW_EXEC moves the venv" "/e/venv" "$(lib_eval EGW_EXEC=/e 'printf %s "$DEMO_VENV"')"
same "EGW_EXEC_VENV is honoured" "/v" "$(lib_eval EGW_EXEC=/e EGW_EXEC_VENV=/v 'printf %s "$DEMO_VENV"')"
same "DEMO_VENV wins over EGW_EXEC_VENV" "/d" "$(lib_eval EGW_EXEC_VENV=/v DEMO_VENV=/d 'printf %s "$DEMO_VENV"')"
same "EGW_COMPARE_SECRETS_ENV is honoured" "/s/.env" "$(lib_eval EGW_COMPARE_SECRETS_ENV=/s/.env 'printf %s "$DEMO_SECRETS"')"
same "DEMO_SECRETS wins" "/t/.env" "$(lib_eval EGW_COMPARE_SECRETS_ENV=/s/.env DEMO_SECRETS=/t/.env 'printf %s "$DEMO_SECRETS"')"
same "DEMO_REPO moves DEMO_TOOLS" "/r/tools/compare" "$(lib_eval DEMO_REPO=/r 'printf %s "$DEMO_TOOLS"')"
same "EGW_COMPARE_SSH_KEY is honoured" "/k" "$(lib_eval EGW_COMPARE_SSH_KEY=/k 'demo_key yocto')"
same "EGW_WRYNOSE_SSH_KEY is honoured" "/w" "$(lib_eval EGW_WRYNOSE_SSH_KEY=/w 'demo_key yoctowrynose')"
# scenario_canon
while read -r given expected; do
    [ "$expected" = '-' ] && expected=
    [ "$given" = '-' ] && given=
    same "scenario_canon '$given'" "$expected" "$(lib_eval "scenario_canon '$given'")"
done << 'EOF'
yocto yocto
YOCTO yocto
debian13 debian13
Debian13 debian13
yoctowrynose yoctowrynose
yoctoWrynose yoctowrynose
YoctoWrynose yoctowrynose
wrynose yoctowrynose
yoctowrinose yoctowrynose
ubuntu ubuntu
- -
EOF
# scenario_check
for name in yocto debian13 yoctoWrynose WRYNOSE; do
    same "scenario_check accepts $name" 0 "$(lib_eval "scenario_check '$name' 2> /dev/null; echo \$?")"
done
for name in '' ubuntu yocto2 debian; do
    same "scenario_check refuses '$name'" 2 "$(lib_eval "scenario_check '$name' 2> /dev/null; echo \$?")"
done
case $(lib_eval "scenario_check bogus 2>&1 > /dev/null") in
    usage:*) ok "scenario_check prints its usage on stderr" ;;
    *) ko "scenario_check prints its usage on stderr" ;;
esac
# inside_repo
same "inside_repo: the repository itself" 0 "$(lib_eval 'inside_repo "$DEMO_REPO"; echo $?')"
same "inside_repo: a folder under it" 0 "$(lib_eval 'inside_repo "$DEMO_REPO/x/y"; echo $?')"
same "inside_repo: a sibling with the same prefix" 1 "$(lib_eval 'inside_repo "$DEMO_REPO-other"; echo $?')"
same "inside_repo: a relative path from the repository" 0 "$(lib_eval 'cd "$DEMO_REPO" && inside_repo runs; echo $?')"
same "inside_repo: the temporary directory" 1 "$(lib_eval "inside_repo '$TMP'; echo \$?")"
# current_run
same "current_run with no state" "" "$(lib_eval DEMO_STATE="$TMP/st" 'current_run')"
mkdir -p "$TMP/st" && echo demo-20261020T120000Z-w1 > "$TMP/st/current_run"
same "current_run reads the recorded run" "demo-20261020T120000Z-w1" "$(lib_eval DEMO_STATE="$TMP/st" 'current_run')"
# guest_running against a stub compare_env.sh (needs a working python3 on the host)
cat > "$TMP/stubtools/compare_env.sh" << 'EOF'
#!/bin/bash
printf '{"scenario": "%s", "running": "%s"}\n' "$2" "${STUB_RUNNING:-false}"
EOF
if python3 -c 'import json' > /dev/null 2>&1; then
    same "guest_running: stub status running=true" 0 "$(lib_eval DEMO_TOOLS="$TMP/stubtools" STUB_RUNNING=true 'guest_running yocto; echo $?')"
    same "guest_running: stub status running=false" 1 "$(lib_eval DEMO_TOOLS="$TMP/stubtools" STUB_RUNNING=false 'guest_running yocto; echo $?')"
else
    sk "guest_running stubs: no working python3 on this host"
fi
# stack_ready against a stub ssh that answers with an HTTP code
cat > "$TMP/bin/ssh" << 'EOF'
#!/bin/bash
printf '%s' "${STUB_HTTP:-000}"
EOF
chmod +x "$TMP/bin/ssh"
same "stack_ready: stub /ready 200" 0 "$(lib_eval STUB_HTTP=200 'stack_ready yocto; echo $?')"
same "stack_ready: stub /ready 503" 1 "$(lib_eval STUB_HTTP=503 'stack_ready yocto; echo $?')"

echo "== 4. simulate.sh --dry-run and stop.sh (no guest)"
sim() { env -i PATH="$TMP/bin:$PATH" HOME="$H" "$@"; }
out=$(sim bash "$DEMO/wearables/simulate.sh" yoctoWrynose 3 60 --dry-run 2>&1)
rc=$?
same "simulate.sh 3 --dry-run exits 0" 0 "$rc"
case $out in *"dry run: nothing published"*) ok "simulate.sh --dry-run publishes nothing" ;; *) ko "simulate.sh --dry-run publishes nothing" ;; esac
case $out in *"devices    : smartwatch,smart_ring,smart_clothing"*) ok "three wearables = the three profiles" ;; *) ko "three wearables = the three profiles" ;; esac
case $out in *"rate       : 2.24 msg/s"*) ok "three wearables: default 2.24 msg/s in total" ;; *) ko "three wearables: default 2.24 msg/s in total" ;; esac
case $out in *"scenario   : yoctowrynose"*) ok "scenario name made canonical" ;; *) ko "scenario name made canonical" ;; esac
case $out in *"--password"*) ko "no password flag on the printed command" ;; *) ok "no password flag on the printed command" ;; esac
same "dry run records no current run" 1 "$(rc_of test -e "$H/.local/state/egw-demo/state/current_run")"
out=$(sim bash "$DEMO/wearables/simulate.sh" debian13 1 --dry-run 2>&1)
case $out in *"devices    : smartwatch  (1 wearable"*"rate       : 1.0 msg/s"*) ok "one wearable: smartwatch at 1.0 msg/s" ;; *) ko "one wearable: smartwatch at 1.0 msg/s" ;; esac
same "simulate.sh refuses 2 wearables" 2 "$(rc_of sim bash "$DEMO/wearables/simulate.sh" yocto 2 --dry-run)"
same "simulate.sh refuses an unknown scenario" 2 "$(rc_of sim bash "$DEMO/wearables/simulate.sh" ubuntu 1 --dry-run)"
same "simulate.sh refuses a non-numeric duration" 2 "$(rc_of sim bash "$DEMO/wearables/simulate.sh" yocto 1 1m --dry-run)"
same "simulate.sh refuses a state root inside the repository" 2 "$(rc_of sim DEMO_STATE_ROOT="$REPO/.demo-check-should-not-exist" bash "$DEMO/wearables/simulate.sh" yocto 1 --dry-run)"
same "nothing was created inside the repository" 1 "$(rc_of test -e "$REPO/.demo-check-should-not-exist")"
out=$(sim DEMO_STATE="$TMP/st2" bash "$DEMO/wearables/stop.sh" 2>&1)
rc=$?
same "stop.sh with no simulation exits 0" 0 "$rc"
same "stop.sh with no simulation says so" "no demonstration simulation recorded" "$out"
same "stop.sh quiet prints nothing" "" "$(sim DEMO_STATE="$TMP/st2" bash "$DEMO/wearables/stop.sh" quiet 2>&1)"
mkdir -p "$TMP/st3"
sleep 30 &
other=$!
if [ -r "/proc/$other/cmdline" ]; then
    echo "$other" > "$TMP/st3/sim.pid"
    echo demo-20261020T120000Z-w1 > "$TMP/st3/current_run"
    same "stop.sh refuses a pid that is not the simulator" 2 "$(rc_of sim DEMO_STATE="$TMP/st3" bash "$DEMO/wearables/stop.sh")"
    same "that process was not signalled" 0 "$(rc_of kill -0 "$other")"
else
    sk "stop.sh pid check: no /proc/<pid>/cmdline on this host"
fi
kill "$other" 2> /dev/null
wait "$other" 2> /dev/null
echo 999999 > "$TMP/st3/sim.pid"
same "stop.sh clears the record of a pid that is not running" 0 "$(rc_of sim DEMO_STATE="$TMP/st3" bash "$DEMO/wearables/stop.sh")"
same "the stale record is removed" 1 "$(rc_of test -e "$TMP/st3/sim.pid")"

echo "== 4b. a full simulate.sh run against stubs leaves no live-view process behind"
# A bounded stub simulator (fake venv python), a stub secrets file and CA, the stub compare_env.sh
# (running) and the stub ssh (/ready 200): simulate.sh runs end to end without any guest. After it
# exits, no 'tail -F' on the run's file and no live-view reader may be left running (PR #65 review).
if command -v ps > /dev/null 2>&1 && ps -eo pid=,args= > /dev/null 2>&1 && python3 -c 'import json' > /dev/null 2>&1; then
    mkdir -p "$TMP/venv/bin" "$TMP/cmp/scenarios/yocto/state"
    cat > "$TMP/venv/bin/python" << 'EOF'
#!/bin/bash
[ "$*" = "-c import egw_simulator" ] && exit 0
while [ $# -gt 0 ]; do case $1 in --run-id) run=$2; shift ;; --output) out=$2; shift ;; esac; shift; done
mkdir -p "$out/$run"
for i in 1 2 3; do printf '{"device_type": "smartwatch", "seq": %s}\n' "$i" >> "$out/$run/sent_events.jsonl"; sleep 1; done
EOF
    chmod +x "$TMP/venv/bin/python"
    echo 'MOSQUITTO_SIMULATOR_PASSWORD=stub-not-a-secret' > "$TMP/stub.env"
    echo stub-ca > "$TMP/cmp/scenarios/yocto/state/ca.crt"
    # output to a file, not a command substitution: a left-over view process would keep a pipe open
    # and hang this check instead of failing it
    sim DEMO_VENV="$TMP/venv" DEMO_SECRETS="$TMP/stub.env" EGW_COMPARE_ROOT="$TMP/cmp" DEMO_TOOLS="$TMP/stubtools" \
        STUB_RUNNING=true STUB_HTTP=200 DEMO_STATE_ROOT="$TMP/ds" bash "$DEMO/wearables/simulate.sh" yocto 1 3 > "$TMP/sim.out" 2>&1
    rc=$?
    out=$(cat "$TMP/sim.out")
    same "simulate.sh end to end against stubs exits 0" 0 "$rc"
    case $out in *"published  smartwatch      seq 3"*) ok "the live view printed the published records" ;; *) ko "the live view printed the published records" ;; esac
    sleep 1
    left=$(ps -eo pid=,args= | grep -F -e "$TMP/ds/runs" -e 'for line in sys.stdin' | grep -v grep || true)
    if [ -z "$left" ]; then
        ok "no live-view process left after simulate.sh exits"
    else
        ko "live-view processes left after simulate.sh exits: $left"
        for p in $(printf '%s\n' "$left" | awk '{print $1}'); do kill "$p" 2> /dev/null; done
    fi
    same "the simulation record is cleared" 1 "$(rc_of test -e "$TMP/ds/state/sim.pid")"
else
    sk "end-to-end stub run: needs ps with -eo and python3"
fi

echo "== 5. static rules"
personal=$(grep -rnE '/home/[A-Za-z]|[A-Za-z]:[\\/]Users[\\/]' "$DEMO" --include='*.sh' --include='*.md' | grep -v '^[^:]*/tests/' || true)
if [ -z "$personal" ]; then ok "no personal paths"; else ko "personal paths: $personal"; fi
sourcing=$(grep -rlE '^[[:space:]]*\. "\$DEMO_SECRETS"' "$DEMO" --include='*.sh' | sed "s|^$DEMO/||" | tr '\n' ' ')
same "only wearables/simulate.sh sources the secrets file" "wearables/simulate.sh " "$sourcing"
forced=$(grep -rnE 'kill -(9|KILL)|pkill|killall' "$DEMO" --include='*.sh' | grep -v '^[^:]*/tests/' || true)
if [ -z "$forced" ]; then ok "no forced kill"; else ko "forced kill: $forced"; fi

echo
echo "offline_check: $pass passed, $fail failed, $skip skipped"
[ "$fail" -eq 0 ]
