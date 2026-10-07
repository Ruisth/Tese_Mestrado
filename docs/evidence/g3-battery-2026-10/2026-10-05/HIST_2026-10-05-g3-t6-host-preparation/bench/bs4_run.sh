#!/bin/bash
# Bench of the S4 operator script (stream BENCH of the S4 preparation, 2026-10-05): one
# scenario, in a bench of its own made by bs4_setup.sh (/tmp/g3-s4-bench/<scenario>).
# Adapted from S3b's bench/bs3b_run.sh (its helpers kept in substance; the scenarios are
# S4's). The script under test runs IN PLACE (<P>/g3_battery.sh, its rows <P>/rows: the
# REAL step file t6.sh), with its own default state directory <bench>/egw-exec/g3-t6-s4;
# scenario 'integrity' alone runs, besides, a changed copy of it and a copy of rows/. The
# REAL helper functions of the regenerated helper file run in the step shell (wait_ready,
# drained, config_identity, harness_cmd, events_start, events_cleanup, stop, ...); what
# they call is stubbed (the test module's stubs; the harness and analyze are the bench's
# stand-in, bs4_harness.py). HOME and every EGW_* inside the bench, stubs first on PATH, no
# guest, no QEMU, no docker, no real ssh. The console (stdout) starts with the sha256 of the
# script run, states what is expected, quotes the decisive lines and ends with the result.
# Usage (WSL): bs4_run.sh <scenario>
#   pass         open S4, row t6 (harness 0 with the real twin and drain hooks, drain quiet,
#                delta 0, --exactly-once 0, analyze 0), classify valid/pass, close
#   labels       open S1|S2|S3 (consumed), open S5, open, row t8|t9|t5, classify t8, term t9
#                refused; open S4; open S4 again refused while open; close; open S4 refused
#   fresh-a..d   r04's raw directory / r04 not in the plan / r04 not 'planned' / the sibling
#                <P>/r04.twins.before.json: open halts, nothing started; then, open passing,
#                row t6 halts before the attempt; a second row refused; close
#   fresh-e      S2's attempt01 admitted where it is kept; found in another place: NOT FRESH
#   fresh-f      another earlier t6 attempt: NOT FRESH at open, and at the row
#   fresh-g      the export tool names the new attempt _attempt03: halt before any step
#   id-a..d      the clone's collector / drivers_sha256 / the root file system differ: open
#                halts, nothing started (id-a also at the row); the gate record differs from
#                S2's: row t6 halts before the attempt
#   pf-1, pf-3   the stub preflight ends 1 / 3: HALT at open, no environment copy, no gate
#   out-h1 out-h2 out-h3 out-gaveup out-delta4 out-eo4 out-eo1
#                the runbook's own lines through the operator script, one outcome each
#   term         'term t6' while the harness stand-in sleeps
#   term-pipe-exp  EXPERIMENT, not the script under test: 'term' on a copy whose step shell
#                ignores SIGPIPE (the evidence for a remedy of the finding of 'term')
#   afterhalt    a halt inside the row: a second row refused, classify, close
#   integrity    the script, the manifest, a row file changed while the session is open
set -u
SC=${1:?usage: bs4_run.sh <scenario>}
case $SC in '' | _* | *[!a-z0-9-]*) echo "refused: '$SC' is not a scenario name"; exit 2 ;; esac
HERE=$(cd "$(dirname "$0")" && pwd)       # <P>/bench
PREP=$(cd "$HERE/.." && pwd)              # <P>
SCR=$(cd "$PREP/../.." && pwd)            # <S>
ROOT=/tmp/g3-s4-bench
B=$ROOT/$SC
FINAL=$PREP/g3_battery.sh
G=$FINAL
REAL_PY=/home/ruisth/egw-exec/venv/bin/python
BASE_PATH=$PATH
CHECKS=0
FAILS=0
RC=0
RID=controller_restart-r04
SEED=1715385812
ADMITTED=20261003T132936Z_g3-qualification-t6_attempt01
DRIVERS_SHA=2c209b09faf58bb4986cf39b7bb1f13936fae8e94c3b5eb3faf84f722bfe44ed
RUNBOOK_SHA=317165936abed4f3823f53b67b7ac76bafa442cfa1820d4b96479392b280cf0f
COLLECTOR_SHA=9e678b024bde66bacc65fea936d05ca226a82e73c86d1cc23a9cf9f8fe8d9b97
ROOTFS=6fce1688284b5d5af2d72991176f0fc7a0b4c8d9c7bcd833c2427437cdac6de4
PLAN_R04_SHA=61d55940fcccdb942ff508ab6fc920b0fa163837ef7459438d789a1879b1eaac
AUTH='G3 qualification, session S4: test 6 only (controller_restart-r04; request of 2026-10-05, output_test/decisions/2026-10-05_g3-t6-session-request.md; criterion amended on 2026-10-05, LOG #C052; transition rule 1a-option-a-2026-10-05, LOG #C053)'

sha() { if [ -f "$1" ]; then /usr/bin/sha256sum "$1" | cut -d' ' -f1; else echo absent; fi; }
mask() { sed "s#$B#<bench>#g; s#$SCR#<S>#g"; }
say() { echo; echo "=== $*" | mask; }
note() { echo "--- $*" | mask; }
ok() { CHECKS=$((CHECKS + 1)); echo "CHECK ok: $*" | mask | cut -c1-600; }
bad() { CHECKS=$((CHECKS + 1)); FAILS=$((FAILS + 1)); echo "CHECK FAILED: $*" | mask | cut -c1-600; }
show() {           # show FILE REGEX: the lines of FILE that match, masked, each cut at 400
    grep -E -- "$2" "$1" 2> /dev/null | mask | cut -c1-400 | sed 's/^/    | /'
}
DECISIVE='^(## [0-9]{4}-|HALT|REFUSED|NOT STARTED|GATE|NOTE|Next|STOP|admitted|NOT FRESH|fresh on|plan entry|gate record|  now:|  S2: |collector:|runbook:|rootfs ext4:|expected: |session S4|row t6|  HALT|    HALT|    attempt|    RUNNING|TERM sent|still in the|waiting for|no attempt existed|attempt:|[a-z_]+\.sh exit=|harness input now|labels:|usage:|keepalive:|KEEPALIVE|The session state|STOP lines|  [^ ]+\.txt:[0-9]+:STOP:|guest-state-delta|What remains|rootfs ext4 after|row file )'
# run SUBCOMMAND...: one subcommand in a session of its own, as the launcher starts it.
run() {
    say "g3_battery.sh $*$([ "$G" = "$FINAL" ] || echo "   (the script run: $G)")"
    setsid bash "$G" "$@" < /dev/null > "$B/last.out" 2>&1
    RC=$?
    echo "-> exit $RC"
    grep -E "$DECISIVE" "$B/last.out" | mask | cut -c1-430
}
want_rc() { if [ "$RC" = "$1" ]; then ok "exit status $RC: $2"; else bad "exit status $RC, expected $1: $2"; fi; }
want() { if grep -Eq -- "$2" "${3:-$B/last.out}" 2> /dev/null; then ok "$1"; else bad "$1 - no line matches: $2"; fi; }
want_no() { if grep -Eq -- "$2" "${3:-$B/last.out}" 2> /dev/null; then bad "$1 - a line matches: $2"; grep -E -- "$2" "${3:-$B/last.out}" | head -n 3 | mask | cut -c1-300 | sed 's/^/    | /'; else ok "$1"; fi; }
is() { if [ "$2" = "$3" ]; then ok "$1: $2"; else bad "$1: '$2', expected '$3'"; fi; }
count() { local c; c=$(grep -cE -- "$1" "$2" 2> /dev/null); echo "${c:-0}"; }
st() { printf '%s\n' "${2:-}" > "$EGW_STUB_STATE/$1"; }      # one state file of the stub guest / the stand-in
exists() { if [ -e "$1" ]; then echo exists; else echo absent; fi; }
skey() { sed -n "s/^$1=//p" "$BSTATE/session-S4.env" 2> /dev/null | tail -n 1; }
skeys() { count "^$1=" "$BSTATE/session-S4.env"; }
halts() { skeys halt; }
row_key() { sed -n "s/^$1=//p" "$BSTATE/row-t6.env" 2> /dev/null | tail -n 1; }
attempt_of() { row_key attempt; }
console() { ls "$(attempt_of)"/console/*-"$1".stdout.txt 2> /dev/null | tail -n 1; }
restarts() { count 'restart controller' "$EGW_STUB_STATE/ssh.log"; }
t6_attempts() { ls -d "$EGW_ATTEMPTS"/*_g3-qualification-t6_attempt* 2> /dev/null | grep -vc "/$ADMITTED$"; }
qemu_state() {
    local pid
    pid=$(cat "$B/qemu.pid" 2> /dev/null)
    if [ -n "$pid" ] && [ -d "/proc/$pid" ]; then echo "pid $pid alive, start tick $(cut -d' ' -f22 "/proc/$pid/stat")"; else echo "pid ${pid:-none} not running"; fi
}
plan_r04() {       # plan_r04 FILE: r04's entry in a plan file, as 'status validity result_dir-set finished-set'
    "$REAL_PY" -c '
import json, sys
try:
    p = json.load(open(sys.argv[1]))
except (OSError, ValueError) as exc:
    print("unreadable: %s" % exc); sys.exit(0)
e = [r for r in p.get("runs", []) if r.get("run_id") == "controller_restart-r04"]
print("absent" if not e else "%s validity=%s result_dir=%s finished_utc=%s" % (e[0].get("status"), e[0].get("validity"), "set" if e[0].get("result_dir") else "none", "set" if e[0].get("finished_utc") else "none"))' "$1"
}
steps_of() {       # the recorded steps of an attempt, in order
    ls "$1/console" 2> /dev/null | sed -n 's/^[0-9]*-\(.*\)\.stdout\.txt$/\1/p' | tr '\n' ' ' | sed 's/ $//'
}
status_now() {
    say "g3_battery.sh status"
    setsid bash "$G" status < /dev/null 2>&1 | grep -E '^(state directory|open session|qemu pgrep|session S4|  |    )' | mask | cut -c1-300
}

# setup: the bench and the environment (EGW_G3_STATE and EGW_G3_ROWS unset: the script's defaults).
setup() {
    local p
    if [ -e "$B" ]; then
        for p in $(cat "$B/qemu.pids.all" 2> /dev/null); do kill -- "-$p" 2> /dev/null; done
        rm -rf "$B"
    fi
    mkdir -p "$ROOT/_logs" || exit 1
    if [ "$SC" = term-pipe-exp ]; then
        echo "script run: sha256 $(sed 's/^STEP_PRE='"'"'exec 2>&1; /STEP_PRE='"'"'trap "" PIPE; exec 2>\&1; /' "$FINAL" | /usr/bin/sha256sum | cut -d' ' -f1) (EXPERIMENT, NOT the script under test: a copy of <S>/g3/t6prep/g3_battery.sh, sha256 $(sha "$FINAL"), whose STEP_PRE ignores SIGPIPE; its rows: <S>/g3/t6prep/rows, t6.sh sha256 $(sha "$PREP/rows/t6.sh"))"
    else
        echo "script run: sha256 $(sha "$G") (<S>/g3/t6prep/g3_battery.sh, run in place; its rows: <S>/g3/t6prep/rows, manifest sha256 $(sha "$PREP/rows/rows.manifest.json"), t6.sh sha256 $(sha "$PREP/rows/t6.sh"))"
    fi
    echo "## $(date -u +%Y-%m-%dT%H:%M:%SZ) scenario $SC; host uptime $(cut -d' ' -f1 /proc/uptime) s"
    echo "bench scripts (sha256, first 16 characters): bs4_run.sh $(sha "$HERE/bs4_run.sh" | cut -c1-16), bs4_setup.sh $(sha "$HERE/bs4_setup.sh" | cut -c1-16), bs4_env.sh $(sha "$HERE/bs4_env.sh" | cut -c1-16), bs4_stubs.py $(sha "$HERE/bs4_stubs.py" | cut -c1-16), bs4_harness.py $(sha "$HERE/bs4_harness.py" | cut -c1-16), bs4_src.sh $(sha "$HERE/bs4_src.sh" | cut -c1-16)"
    bash "$HERE/bs4_setup.sh" "$B" > "$ROOT/_logs/$SC.setup.log" 2>&1 || { echo "setup failed:"; tail -n 8 "$ROOT/_logs/$SC.setup.log" | mask; exit 1; }
    grep -E '^(drivers of the copy|collector of the copy|test module imported|tunnel.sh:|itest-helpers.sh:|gate record:|real plan copied|bench plan after)' "$ROOT/_logs/$SC.setup.log" | mask | cut -c1-300
    # shellcheck source=/dev/null
    . "$HERE/bs4_env.sh"
    SUT0=$(sha "$HOME/egw-tcg/sut_environment.json")
    PLAN0=$(sha "$HOME/egw-tcg/pilot/campaign_plan.json")
    printf 'bench: scenario %s\n' "$SC" > "$B/reason.txt"
    printf 'bench: none\n' > "$B/next.txt"
}
finish() {         # the end of every scenario: the bench's own fake processes are ended
    local p left
    say "the end of the bench"
    for p in $(cat "$B/qemu.pids.all" 2> /dev/null); do
        if [ -d "/proc/$p" ]; then kill -- "-$p" 2> /dev/null; echo "the fake process $p that stood for QEMU was still running: ended now by the bench itself"; fi
    done
    /usr/bin/sleep 1
    left=$(/usr/bin/pgrep -f "$B/" | wc -l)
    [ "$left" -eq 0 ] || { /usr/bin/sleep 20; left=$(/usr/bin/pgrep -f "$B/" | wc -l); }
    is "processes of this bench left" "$left" 0
    [ "$left" -eq 0 ] || /usr/bin/pgrep -af "$B/" | mask | cut -c1-200
    is "the script under test after the scenario (sha256)" "$(sha "$FINAL")" "$SCRIPT0"
    is "the row file after the scenario (sha256)" "$(sha "$PREP/rows/t6.sh")" "$ROWS0"
    echo
    if [ "$FAILS" -eq 0 ]; then
        echo "## $(date -u +%Y-%m-%dT%H:%M:%SZ) SCENARIO $SC: PASS ($CHECKS checks)"
    else
        echo "## $(date -u +%Y-%m-%dT%H:%M:%SZ) SCENARIO $SC: FAIL ($FAILS of $CHECKS checks failed)"
    fi
}
SCRIPT0=$(sha "$FINAL")
ROWS0=$(sha "$PREP/rows/t6.sh")

# --- the common passages ---------------------------------------------------------------------
open_ok() {        # open S4 passing every check
    run open S4
    want_rc 0 "open S4"
    want "the session is open" '^## .* session S4 is open: '
    want "the clone's collector is compared with S4's COLLECTOR_SHA" "^collector: $COLLECTOR_SHA  $B/repo/src/deployment/scripts/collect-resources\.sh$"
    want "the runbook is the merged blob" "^runbook: $RUNBOOK_SHA  "
    want "repo_identity names the merged drivers" "\"drivers_sha256\": \"$DRIVERS_SHA\""
    want "S2's t6 attempt admitted in the WSL attempts directory" "^admitted: the one earlier attempt of row t6 \(S2's invalid one, plan entry controller_restart-r03, kept as sealed\): $EGW_ATTEMPTS/$ADMITTED$"
    want "S2's t6 attempt admitted under output_test/runs/2026-10-03/" "^admitted: the one earlier attempt of row t6 .*: $EGW_OUTPUT_TEST/runs/2026-10-03/$ADMITTED$"
    want "r04 is 'planned' in the plan" "^plan entry $RID: status=planned seed=$SEED condition=controller_restart duration_s=600 warmup_s=0$"
    want "r04 is fresh on the host" "^fresh on the host: $RID \(planned, no raw directory, no "
    want "r04 is fresh on the guest" "^fresh on the guest: $RID$"
    want "the root file system read is 6fce1688..." "^rootfs ext4: $ROOTFS  "
    want "the expected root file system is S4's" "^expected:    $ROOTFS \(the value the close of S3's second opening recorded\)$"
    want "the preflight driver ended 0" '^preflight\.sh exit=0$'
    want "the environment copy ran" '^harness input now: '
    want "the gate driver ran" 'gate_health\.sh \(frozen driver'
    want_no "no exception is examined or applied (case-insensitive 'exception')" '[Ee][Xx][Cc][Ee][Pp][Tt][Ii][Oo][Nn]'
    is "the session's state" "$(skey state)" open
    is "the state file is in the script's default state directory <EXEC>/g3-t6-s4" "$(exists "$BSTATE/session-S4.env")" exists
    is "steps_script_sha256 recorded by open" "$(skey steps_script_sha256)" "$(sha "$G")"
    Q0=$(qemu_state)
    note "the fake process that stands for QEMU after the open: $Q0"
}
nothing_started() {   # after a halt or a refusal of 'open' before the session is used
    is "no session state file" "$(exists "$BSTATE/session-S4.env")" absent
    is "no current_session" "$(exists "$EGW_EXEC/current_session")" absent
    is "no fake QEMU process was started" "$(exists "$B/qemu.pid")" absent
    is "no attempt was created (besides S2's admitted one)" "$(ls "$EGW_ATTEMPTS" | grep -vc "^$ADMITTED$")" 0
}
row_not_started() {   # after a halt or a refusal of 'row' before the attempt exists
    is "no row state file" "$(exists "$BSTATE/row-t6.env")" absent
    is "no new attempt of row t6" "$(t6_attempts)" 0
    is "the harness was not started" "$(exists "$EGW_STUB_STATE/harness.argv.json")" absent
    is "the Docker events recorder was not started" "$(count 'capture \[start\]' "$EGW_STUB_STATE/capture.log")" 0
    is "no restart reached the stub guest" "$(restarts)" 0
}
close_ok() {
    run close
    want_rc "${1:-0}" "close"
    want "the session is closed" '^## .* session S4 closed \(guest_session_close\.sh exit 0\)'
    is "the session's state after close" "$(skey state)" closed
    is "an open session (current_session) after close" "$(exists "$EGW_EXEC/current_session")" absent
    is "the fake QEMU after close" "$(qemu_state | sed 's/^pid [0-9a-z]* //')" "not running"
}
sent_to_guest() {     # what reached the stub guest: test 6's one restart, never an up or a start
    # (ssh.log also holds the module stub clone's own 'capture [...]' and 'fetch [...]' lines,
    # which it writes there for their order; they are not commands sent to the guest)
    is "commands that bring up or start anything, sent to the stub guest" "$(grep -vE '^(capture|fetch) \[' "$EGW_STUB_STATE/ssh.log" 2> /dev/null | grep -cE '(docker( compose)?|\$DC|systemctl)\b[^"'"'"';]*\b(up|start)\b')" 0
    is "pkill or killall calls" "$(count 'PATTERN-KILL' "$EGW_STUB_STATE/calls.log")" 0
}
row_ran() {        # row_ran EXIT: row t6 ran its one step; the common checks
    run row t6
    want_rc "$1" "row t6"
    want "the gate record is compared before t6 and equals S2's" "^gate record: the image reference, the image id and the repo digest of the six containers equal S2's"
    A=$(attempt_of)
    is "the new attempt's name ends _g3-qualification-t6_attempt02" "$(row_key attempt_name | sed 's/^[0-9TZ]*//')" "_g3-qualification-t6_attempt02"
    C=$(console t6)
    is "the recorded steps of the row, in order" "$(steps_of "$A")" "guest-state-before snapshot-before t6 snapshot-after guest-state-after guest-state-delta gate-healthy gate-units gate-tunnel-check"
    want "the step shell unset the carriers and printed them" '^carriers after the unset: DEVICES=<unset> ACCEPT_UNACCOUNTED=<unset> EVENTS_EXPECTED=<unset> DRAIN_QUIET_S=<unset> DRAIN_STEP_S=<unset> DRAIN_LIMIT_S=<unset> READY_LIMIT_S=<unset>; EGW_CLONE=' "$C"
    want "set -v echoes the row file's first line as read" '^RID=controller_restart-r04; F6=used; if ' "$C"
    want "line 1425's own 'drained' ran its real quiet window (130 s on /proc/uptime)" '^drained: queue_depth 0 and identical counters on [0-9]+ consecutive readings over 1[3-9][0-9] s' "$C"
    want "config_identity wrote the identity before the harness" "^config_identity: wrote $HOME/egw-tcg/itest/$RID\.config_identity\.json$" "$C"
    note "the step's 'test 6:' and 'STOP:' lines and the stub lines of \$REC (console $(basename "$C")):"
    show "$C" '^(test 6:|STOP:|itest_reconcile stub:|\[harness\] (BENCH|INVALID|run |error|refused)|\[analyze\]|harness_cmd )'
    is "row state" "$(row_key state)" awaiting-classification
}
step_calls() {     # what $REC was asked, and the harness's argv (passwords hidden)
    note "\$REC calls of the step (calls.log of the stub python):"
    show "$EGW_STUB_STATE/calls.log" 'itest_reconcile (delta|acceptance)'
}
classify_as() {    # classify_as STATUS VALIDITY OUTCOME
    run classify t6 "$1" "$2" "$3" "@$B/reason.txt" "@$B/next.txt"
}

# --- the scenarios ---------------------------------------------------------------------------
# Everything from here to the end is ONE group, which bash reads whole before running it.
{
case $SC in
    pass)
        setup
        st bench_hooks real
        echo "EXPECTED: open S4 (stub drivers end 0; every identity check passes); row t6 runs the REAL t6.sh in one step shell with the REAL helpers: line 1425's wait_ready, drained (real 130 s window), config_identity and harness_cmd (the recorder stub, the harness stand-in running the checkout's REAL twin and drain hooks - another 130 s window - and the controller restart through ssh), T6=ok; line 1426 delta 0; line 1427 acceptance --exactly-once 0; line 1428 analyze 0; the snapshots show r04 planned -> completed; the gate after shows EXPECTED-RESTART of egw-controller-1 and passes; classify valid/pass exports; close runs 'compose stop -t 130' and the close driver."
        open_ok
        row_ran 0
        want "the attempt is named in the console" "^## .* row t6: attempt $EGW_ATTEMPTS/[0-9TZ]+_g3-qualification-t6_attempt02 \(ceiling 47 min"
        want_no "no line starting STOP: in the step's console" '^STOP:' "$C"
        want "line 1425: the manifest's resources_proved_down, read-only" '^test 6: resources_proved_down: applies=True why_not=None D=2026-10-05T20:05:00\.400000000Z S=2026-10-05T20:05:06\.300000000Z E=2026-10-05T20:05:06\.300000000Z capped=False edge_before_s=0\.4 edge_after_s=1\.2 rejected_rows=0 resources_ingested=True$' "$C"
        want "line 1425: the transition record, read-only (rule 1a-option-a-2026-10-05)" '^test 6: resources_transition_rows: rule=1a-option-a-2026-10-05 admitted=True why_not=None resources_ingested=True count=2 instants=\[' "$C"
        want "line 1425: T6=ok" "^test 6: harness exit 0 and the recorder's cleanup done, run directory sealed, the drain quiet \(manifest drain\.outcome\)$" "$C"
        want "line 1426: delta ran and ended 0" '^itest_reconcile stub: delta exit=0$' "$C"
        want "line 1427: acceptance --exactly-once ran and ended 0" '^itest_reconcile stub: acceptance exit=0$' "$C"
        want "line 1428: analyze ran" '^\[analyze\] BENCH STAND-IN' "$C"
        for h in twin_snapshot_before drain post_drain twin_snapshot_after broker controller docker_events; do
            want "the harness stand-in ran the hook '$h' line 1425 handed it, exit 0" "^\[harness\] \(bench stand-in\) hook $h: exit 0$" "$C"
        done
        RAW=$HOME/egw-tcg/pilot/results/raw/$RID
        want "the drain hook (proof_hook_drained.sh) read the carriers line 1425 passed empty as the runbook's defaults" "^proof_hook_drained: $RID: drained with DRAIN_QUIET_S=130 DRAIN_STEP_S=5 DRAIN_LIMIT_S=900$" "$RAW/logs/sut/hook-drain.stdout.txt"
        want "the drain hook's own 'drained' found its 130 s quiet window" '^drained: queue_depth 0 and identical counters on [0-9]+ consecutive readings over 1[3-9][0-9] s' "$RAW/logs/sut/hook-drain.stdout.txt"
        want "the twin hook 'before' kept the snapshot with the plan's seed" "^proof_hook_twins: $RID before: snapshot kept as $HOME/egw-tcg/itest/$RID\.twins\.before\.json and $RAW/twins\.before\.json$" "$RAW/logs/sut/hook-twin_snapshot_before.stdout.txt"
        want "the twin snapshot 'before' was asked with seed $SEED" "itest_reconcile snap --prefix $HOME/egw-tcg/itest/$RID --label before --seed $SEED " "$EGW_STUB_STATE/calls.log"
        step_calls
        want "line 1426's delta: the post-drain copy, the twin prefix, the controller log and the run directory" "^python -m egw_experiments\.itest_reconcile delta $RAW --prefix $HOME/egw-tcg/itest/$RID --events $RAW/events\.post-drain\.jsonl --controller-log $RAW/logs/sut/controller\.log --restart-evidence $RAW$" "$EGW_STUB_STATE/calls.log"
        want "line 1427's acceptance: the simulator's directory in the run directory, the post-drain copy, --exactly-once" "^python -m egw_experiments\.itest_reconcile acceptance $RAW/logs/simulator/$RID --events $RAW/events\.post-drain\.jsonl --exactly-once$" "$EGW_STUB_STATE/calls.log"
        want_no "plan-supplement was never called by the row" 'plan-supplement' "$EGW_STUB_STATE/calls.log"
        note "the harness's argv as line 1425 built it (the stand-in's record, every --password value hidden): the options and the four values S4 adds"
        "$REAL_PY" -c '
import json, sys
a = json.load(open(sys.argv[1]))
print("    | options: " + " ".join(x for x in a if x.startswith("--")))
for k in ("--run-id", "--restart-at-s", "--restart-transition-rule", "--config-identity-from", "--password", "--restart-cmd"):
    print("    | %s %s" % (k, a[a.index(k) + 1] if k in a else "ABSENT"))' "$EGW_STUB_STATE/harness.argv.json" | mask | cut -c1-300
        want "the harness was handed --restart-transition-rule 1a-option-a-2026-10-05" '"--restart-transition-rule",$' "$EGW_STUB_STATE/harness.argv.json"
        is "the value after --restart-transition-rule" "$("$REAL_PY" -c 'import json,sys; a=json.load(open(sys.argv[1])); print(a[a.index("--restart-transition-rule")+1])' "$EGW_STUB_STATE/harness.argv.json")" 1a-option-a-2026-10-05
        is "the value after --restart-at-s" "$("$REAL_PY" -c 'import json,sys; a=json.load(open(sys.argv[1])); print(a[a.index("--restart-at-s")+1])' "$EGW_STUB_STATE/harness.argv.json")" 300
        note "the recorder and the bounded reads (the module's stub clone, capture.log):"
        show "$EGW_STUB_STATE/capture.log" '.'
        want "the recorder was started for r04 before the harness" "^capture \[start\] \[$RID\]$" "$EGW_STUB_STATE/capture.log"
        want "the docker-events fetch demanded die,start of the controller (EVENTS_EXPECTED of line 1425)" "^fetch \[docker-events\] \[$RAW/logs/sut/docker-events\.log\] \[1790000000\] \[$RID\] \[die,start\]$" "$EGW_STUB_STATE/capture.log"
        want "harness_cmd's cleanup ran after the harness" "^capture \[cleanup\] \[$RID\]$" "$EGW_STUB_STATE/capture.log"
        is "controller restarts that reached the stub guest (test 6's own, from the harness's --restart-cmd)" "$(restarts)" 1
        note "the guest reads and the restart, in order (ssh.log):"
        grep -nE 'State\.OOMKilled|restart controller' "$EGW_STUB_STATE/ssh.log" | sed 's/^\([0-9]*\):.*\(State\.OOMKilled\|restart controller\).*/ssh.log line \1: \2/' | sed 's/^/    | /'
        o=$(grep -nE 'State\.OOMKilled|restart controller' "$EGW_STUB_STATE/ssh.log" | sed 's/^\([0-9]*\):.*\(OOMKilled\|restart controller\).*/\2/' | tr '\n' ' ')
        is "the order: guest state before, the row's restart, guest state after" "$o" "OOMKilled restart controller OOMKilled "
        sent_to_guest
        say "the snapshots of the plan and processed/ before and after the step"
        show "$(console snapshot-before)" '.'
        show "$(console snapshot-after)" '.'
        is "r04 in the plan copied BEFORE the step" "$(plan_r04 "$A/other/campaign_plan.before.json")" "planned validity=None result_dir=none finished_utc=none"
        is "r04 in the plan copied AFTER the step (the harness's rewrite, run.update_plan_status)" "$(plan_r04 "$A/other/campaign_plan.after.json")" "completed validity=valid result_dir=set finished_utc=set"
        is "the plan before the step is the prepared one (61d55940...)" "$(sha "$A/other/campaign_plan.before.json")" "$PLAN_R04_SHA"
        note "the plan after the step: sha256 $(sha "$A/other/campaign_plan.after.json") (not 61d55940...: the harness rewrote r04's status)"
        is "the 95 entries before r04, before and after the step (JSON)" "$("$REAL_PY" -c 'import json,sys; a=json.load(open(sys.argv[1]))["runs"]; b=json.load(open(sys.argv[2]))["runs"]; print("equal" if a[:95]==b[:95] and len(a)==len(b)==96 else "DIFFERENT")' "$A/other/campaign_plan.before.json" "$A/other/campaign_plan.after.json")" equal
        want "no processed/ tree before the step" '^no processed/ tree at this moment' "$(console snapshot-before)"
        is "processed/per_run.csv copied after the step" "$(exists "$A/other/processed.after/per_run.csv")" exists
        note "per_run.csv after the step (the analyze stand-in): $(tr '\n' ' ' < "$A/other/processed.after/per_run.csv")"
        say "the gate after the row"
        D=$(console guest-state-delta)
        show "$D" '^(EXPECTED-RESTART|FAULT|PROBLEM|guest-state-delta)'
        want "guest_state_delta.py was given --expect-restarted egw-controller-1" '"--expect-restarted", "egw-controller-1"' "$A/commands.jsonl"
        want "the pair shows the controller's expected restart" '^EXPECTED-RESTART: .*egw-controller-1' "$D"
        want "guest-state-delta: no fault, no problem" '^guest-state-delta: faults=0 problems=0$' "$D"
        want "the gate passed" '^## .* GATE t6: pass \(guest state compared, six services healthy, no recorder or collector unit active, tunnel up\)$'
        is "the row's gate" "$(row_key gate)" pass
        is "halts recorded" "$(halts)" 0
        is "the workload field: S4's authority, r04, no itest id, session S4" "$("$REAL_PY" -c 'import json,sys; w=json.load(open(sys.argv[1]))["workload"]; w=json.loads(w) if isinstance(w,str) else w; print("ok" if w["battery"]==sys.argv[2] and w["harness_run_id"]=="controller_restart-r04" and w["itest_run_ids"]==[] and w["session_label"]=="S4" and w["row_ceiling_min"]==47 else "NOT: %r" % w)' "$A/attempt.json" "$AUTH")" ok
        note "the workload field's 'battery': $("$REAL_PY" -c 'import json,sys; w=json.load(open(sys.argv[1]))["workload"]; w=json.loads(w) if isinstance(w,str) else w; print(w["battery"])' "$A/attempt.json")"
        want "the raw directory is a registered source" "\"path\": \"$RAW\"" "$A/sources.json"
        want "the configuration identity with the r04.* siblings is a registered source" "\"siblings_glob\": \"$RID\.\*\"" "$A/sources.json"
        status_now
        classify_as finished valid pass
        want_rc 0 "classify t6 valid/pass (a bench classification)"
        want "classified and exported, the export tool's own verification" "^row t6: classified 'pass'; driver code 0; export: verified -> $EGW_OUTPUT_TEST/runs/"
        PKG=$(ls -d "$EGW_OUTPUT_TEST"/runs/*/"$(basename "$A")" 2> /dev/null | head -n 1)
        note "package: $PKG"
        is "the package holds the sealed run directory's manifest" "$(exists "$PKG/raw/$RID/manifest.json")" exists
        is "the package holds the run directory's SHA256SUMS" "$(exists "$PKG/raw/$RID/SHA256SUMS")" exists
        is "the run directory's own SHA256SUMS verifies in the package" "$(cd "$PKG/raw/$RID" && /usr/bin/sha256sum -c --quiet SHA256SUMS > /dev/null 2>&1 && echo verified || echo FAILED)" verified
        is "the package holds the configuration identity" "$(find "$PKG" -name "$RID.config_identity.json" | grep -c .)" 1
        is "the package holds the twin siblings" "$(find "$PKG" -name "$RID.twins.*.json" | grep -c .)" 2
        is "the package holds the .sut directory's start record" "$(find "$PKG" -path "*/$RID.sut/events-start.txt" | grep -c .)" 1
        is "the package holds the plan snapshots" "$(find "$PKG" -name 'campaign_plan.*.json' | grep -c .)" 2
        is "the package's SHA256SUMS verifies" "$(cd "$PKG" && /usr/bin/sha256sum -c --quiet SHA256SUMS > /dev/null 2>&1 && echo verified || echo FAILED)" verified
        is "the bench's password value is in no file of the package" "$(grep -rl 'bench-value-0000' "$PKG" 2> /dev/null | wc -l)" 0
        close_ok
        want "the recorded stop with the controller's 130 s allowance ran" '^## .* the recorded stop with the controller.s 130 s allowance'
        want "the stub guest received 'compose ... stop -t 130'" 'docker compose --env-file \.env --env-file images\.lock\.env stop -t 130' "$EGW_STUB_STATE/ssh.log"
        is "rootfs_after_close recorded" "$(skey rootfs_after_close)" "$ROOTFS"
        is "halts after close" "$(halts)" 0
        is "controller restarts that reached the stub guest after close (still only the row's)" "$(restarts)" 1
        ;;
    labels)
        setup
        echo "EXPECTED: open S1, open S2, open S3 refused (exit 2) with the consumed-authority text; open S5 and open with no label refused (usage); row t8, row t9, row t5 refused as unknown (S4: t6 only); classify t8 and term t9 refused as unknown; nothing created by any refusal; open S4 passes; open S4 again refused while it is open; after close, open S4 refused because session-S4.env exists."
        for l in S1 S2; do
            run open "$l"
            want_rc 2 "open $l refused"
            want "open $l: the battery's authority is consumed, S4 only" "^REFUSED: session $l is a session of the battery of 2026-10-02/03, whose authority is consumed: nothing of S1 or S2 is re-run or replaced\. This script opens S4 only: g3_battery\.sh open S4$"
        done
        run open S3
        want_rc 2 "open S3 refused"
        want "open S3: its authority is consumed, S4 only" "^REFUSED: session S3 \(tests 8 and 9, 2026-10-05\) is closed and its authority is consumed: nothing of S3 is re-run or replaced\. This script opens S4 only: g3_battery\.sh open S4$"
        run open S5
        want_rc 2 "open S5 refused"
        want "open S5: the usage" '^REFUSED: usage: g3_battery\.sh open S4$'
        run open
        want_rc 2 "open with no label refused"
        for r in t8 t9 t5; do
            run row "$r"
            want_rc 2 "row $r refused"
            want "row $r: unknown row (S4: t6 only)" "^REFUSED: unknown row '$r' \(S4: t6 only; the rows of S1, S2 and S3 are not run again\)$"
        done
        run classify t8 finished valid pass x y
        want_rc 2 "classify t8 refused"
        want "classify t8: unknown row" "^REFUSED: unknown row 't8'$"
        run term t9
        want_rc 2 "term t9 refused"
        want "term t9: unknown row" "^REFUSED: unknown row 't9'$"
        is "no state directory was created by any refusal" "$(exists "$BSTATE")" absent
        nothing_started
        open_ok
        run open S4
        want_rc 2 "open S4 a second time, while S4 is open"
        want "refused: a session is open" "^REFUSED: a session is open \($EGW_EXEC/current_session names "
        run open S3
        want_rc 2 "open S3 while S4 is open"
        want "open S3: the consumed-authority text, not a session check" "^REFUSED: session S3 \(tests 8 and 9, 2026-10-05\) is closed and its authority is consumed"
        is "halts recorded" "$(halts)" 0
        close_ok
        run open S4
        want_rc 2 "open S4 after S4 was closed"
        want "refused: session-S4.env exists (a session is opened once)" "^REFUSED: $BSTATE/session-S4\.env exists: session S4 was already opened"
        ;;
    fresh-a | fresh-b | fresh-c | fresh-d)
        setup
        PLANF=$HOME/egw-tcg/pilot/campaign_plan.json
        case $SC in
            fresh-a) what="r04's raw directory ~/egw-tcg/pilot/results/raw/$RID exists"; line="^NOT FRESH: $HOME/egw-tcg/pilot/results/raw/$RID exists \($RID\)$"
                apply() { mkdir -p "$HOME/egw-tcg/pilot/results/raw/$RID"; }; clear() { rmdir "$HOME/egw-tcg/pilot/results/raw/$RID"; } ;;
            fresh-b) what="r04 is not in the plan (the real plan before the preparation's plan-supplement, c195bd3f..., 95 entries)"; line="^plan entry $RID: NOT in the plan$"
                apply() { cp "$B/plan.c195.json" "$PLANF"; }; clear() { cp "$B/plan.r04.json" "$PLANF"; } ;;
            fresh-c) what="r04's status is 'running', not 'planned'"; line="^plan entry $RID: status=running seed=$SEED "
                apply() { "$REAL_PY" -c 'import json,sys; f=sys.argv[1]; p=json.load(open(f)); [r.update(status="running") for r in p["runs"] if r["run_id"]=="controller_restart-r04"]; open(f,"w").write(json.dumps(p, indent=2)+"\n")' "$PLANF"; }
                clear() { cp "$B/plan.r04.json" "$PLANF"; } ;;
            fresh-d) what="the sibling ~/egw-tcg/itest/$RID.twins.before.json exists"; line="^NOT FRESH: $HOME/egw-tcg/itest/$RID\.twins\.before\.json exists \($RID\)$"
                apply() { mkdir -p "$HOME/egw-tcg/itest"; echo '{}' > "$HOME/egw-tcg/itest/$RID.twins.before.json"; }; clear() { mv "$HOME/egw-tcg/itest/$RID.twins.before.json" "$B/hold/"; } ;;
        esac
        echo "EXPECTED: $what. (1) open S4 halts (exit 1, 'HALT: an id of S4 is not fresh on the host; nothing was started'): no state file, no session, no fake QEMU. (2) The condition removed, open S4 passes. (3) The condition restored, row t6 halts (exit 1) before the attempt: no row state file, no attempt, no recorder, no harness, no restart. (4) A second row t6 is refused: the session has a recorded halt. (5) close."
        apply
        run open S4
        want_rc 1 "open S4 with the condition"
        want "the line that names the cause" "$line"
        want "the halt of open" '^HALT: an id of S4 is not fresh on the host; nothing was started$'
        nothing_started
        clear
        open_ok
        apply
        P1=$(sha "$PLANF")
        run row t6
        want_rc 1 "row t6 with the condition"
        want "the line that names the cause" "$line"
        want "the halt of row" '^HALT: an id of row t6 is not fresh on the host, or an earlier attempt of the row that is not admitted exists: the row was NOT started and no attempt was created \(packet section 4, halt 1\)$'
        row_not_started
        is "the plan was not changed by the row" "$(sha "$PLANF")" "$P1"
        is "halts recorded" "$(halts)" 1
        run row t6
        want_rc 2 "a second row t6 after the recorded halt"
        want "refused: the session has a recorded halt" '^REFUSED: NOT STARTED: session S4 has a recorded halt \(up=[0-9]+ row=t6 an id of row t6 is not fresh'
        row_not_started
        close_ok
        is "halts after close (no new one)" "$(halts)" 1
        ;;
    fresh-e)
        setup
        echo "EXPECTED: S2's attempt01 is admitted in the two places where it is kept (the WSL attempts directory and output_test/runs/2026-10-03/): open passes and prints two 'admitted:' lines. The same attempt found in another place (output_test/runs/2026-10-04/, output_test/incomplete/) is NOT FRESH: open halts, nothing started."
        mkdir -p "$EGW_OUTPUT_TEST/runs/2026-10-04"
        cp -r "$EGW_OUTPUT_TEST/runs/2026-10-03/$ADMITTED" "$EGW_OUTPUT_TEST/runs/2026-10-04/"
        run open S4
        want_rc 1 "open S4 with S2's attempt also under runs/2026-10-04/"
        want "NOT FRESH names it" "^NOT FRESH: an earlier attempt of row t6 exists: $EGW_OUTPUT_TEST/runs/2026-10-04/$ADMITTED$"
        want "the two admitted places are still admitted" "^admitted: .*: $EGW_OUTPUT_TEST/runs/2026-10-03/$ADMITTED$"
        want "the halt of open" '^HALT: an id of S4 is not fresh on the host; nothing was started$'
        nothing_started
        mv "$EGW_OUTPUT_TEST/runs/2026-10-04/$ADMITTED" "$B/hold/e1"
        cp -r "$EGW_ATTEMPTS/$ADMITTED" "$EGW_OUTPUT_TEST/incomplete/"
        run open S4
        want_rc 1 "open S4 with S2's attempt also under incomplete/"
        want "NOT FRESH names it" "^NOT FRESH: an earlier attempt of row t6 exists: $EGW_OUTPUT_TEST/incomplete/$ADMITTED$"
        nothing_started
        mv "$EGW_OUTPUT_TEST/incomplete/$ADMITTED" "$B/hold/e2"
        open_ok
        is "'admitted:' lines of open (the two places)" "$(count '^admitted: ' "$B/last.out")" 2
        want_no "no NOT FRESH line" '^NOT FRESH'
        close_ok
        ;;
    fresh-f)
        setup
        X=20261004T120000Z_g3-qualification-t6_attempt05
        echo "EXPECTED: another earlier attempt of row t6 ($X) in the WSL attempts directory: open halts NOT FRESH, nothing started; removed, open passes; then one under output_test/incomplete/: row t6 halts before the attempt; close."
        mkdir -p "$EGW_ATTEMPTS/$X"
        run open S4
        want_rc 1 "open S4 with another t6 attempt"
        want "NOT FRESH names it" "^NOT FRESH: an earlier attempt of row t6 exists: $EGW_ATTEMPTS/$X$"
        want "the halt of open" '^HALT: an id of S4 is not fresh on the host; nothing was started$'
        is "no session state file" "$(exists "$BSTATE/session-S4.env")" absent
        is "no current_session" "$(exists "$EGW_EXEC/current_session")" absent
        is "no fake QEMU process was started" "$(exists "$B/qemu.pid")" absent
        mv "$EGW_ATTEMPTS/$X" "$B/hold/f1"
        open_ok
        mkdir -p "$EGW_OUTPUT_TEST/incomplete/$X"
        run row t6
        want_rc 1 "row t6 with another t6 attempt under incomplete/"
        want "NOT FRESH names it" "^NOT FRESH: an earlier attempt of row t6 exists: $EGW_OUTPUT_TEST/incomplete/$X$"
        want "the halt of row" '^HALT: an id of row t6 is not fresh on the host, or an earlier attempt of the row that is not admitted exists: the row was NOT started and no attempt was created'
        row_not_started
        close_ok
        ;;
    fresh-g | afterhalt)
        setup
        DEEP=$EGW_OUTPUT_TEST/runs/2026-10-04/held/20261004T120000Z_g3-qualification-t6_attempt02
        echo "EXPECTED: an attempt of t6 that 'open' does not see (one level deeper under output_test/runs, which the export tool's numbering counts) makes the export tool name the new attempt _attempt03: row t6 halts after the attempt is created and before any step (no guest read, no snapshot, no step, no harness, no restart, no gate), and awaits classification; $([ "$SC" = afterhalt ] && echo "then a second row t6 is refused (already started); status shows the halt; classify not-applicable/not-run records 'classified not started' and names close; row t6 still refused; close closes; open S4 is refused (opened once)" || echo "classify not-applicable/not-run; close")."
        mkdir -p "$DEEP"
        open_ok
        want_no "open sees no other t6 attempt" '^NOT FRESH'
        run row t6
        want_rc 1 "row t6"
        want "the halt names the attempt's name and the expected one" "^HALT: row t6: the new attempt is named [0-9TZ]+_g3-qualification-t6_attempt03, which does not end '_g3-qualification-t6_attempt02' \(the name the request of 2026-10-05, section 3, expects\): an attempt of this row exists that was not accounted for, or the admitted one is not where it is kept\. No step of the row was run$"
        A=$(attempt_of)
        is "the attempt recorded" "$(row_key attempt_name | sed 's/^[0-9TZ]*//')" "_g3-qualification-t6_attempt03"
        is "steps recorded in the attempt (none)" "$(steps_of "$A")" ""
        is "the harness was not started" "$(exists "$EGW_STUB_STATE/harness.argv.json")" absent
        is "no restart reached the stub guest" "$(restarts)" 0
        is "the plan is the prepared one, untouched" "$(sha "$HOME/egw-tcg/pilot/campaign_plan.json")" "$PLAN_R04_SHA"
        is "row state" "$(row_key state)" awaiting-classification
        is "halts recorded" "$(halts)" 1
        if [ "$SC" = afterhalt ]; then
            run row t6
            want_rc 2 "a second row t6 after the halt"
            want "refused: the row was already started" "^REFUSED: row t6 was already started \($BSTATE/row-t6\.env\): a row is run once, never repeated$"
            status_now
            classify_as failed not-applicable not-run
            want_rc 1 "classify t6 not started (a halt of classify's own)"
            want "classified and exported" "^row t6: classified 'not started'; driver code [0-9]+; export: verified -> "
            want "the halt of a row classified not started" '^HALT: row t6 is classified not started \(packet section 4, halt 1\): it is not attempted again under this approval$'
            want "classify names the next step" "^Next: 'close', then hand back to Rui: session S4 has a recorded halt, and no further row starts\.$"
            run row t6
            want_rc 2 "row t6 after the classification"
            close_ok
            is "halts after close" "$(halts)" 2
            run open S4
            want_rc 2 "open S4 after the close"
            want "refused: opened once" "^REFUSED: $BSTATE/session-S4\.env exists"
        else
            classify_as failed not-applicable not-run
            want_rc 1 "classify t6 not started"
            close_ok
        fi
        ;;
    id-a | id-b | id-c)
        setup
        case $SC in
            id-a) what="the clone's collector differs from 9e678b02... (one line appended to the bench copy)"; line="^HALT: collector \($B/repo/src/deployment/scripts/collect-resources\.sh\) is [0-9a-f]{64}, the recorded identity is $COLLECTOR_SHA \(packet section 4, halt 6\); nothing was started$"
                apply() { echo '# bench: one line appended' >> "$B/repo/src/deployment/scripts/collect-resources.sh"; }
                clear() { cp /tmp/g3-s4-bench/_src/src/deployment/scripts/collect-resources.sh "$B/repo/src/deployment/scripts/collect-resources.sh" && chmod u+w "$B/repo/src/deployment/scripts/collect-resources.sh"; } ;;
            id-b) what="drivers_sha256 differs from 2c209b09... (the bench's sha256sum stub answers another value for the drivers' stream)"; line="^HALT: drivers_sha256 is not $DRIVERS_SHA \(packet section 4, halt 6\); nothing was started$"
                apply() { echo 0000000000000000000000000000000000000000000000000000000000000000 > "$B/sha.drivers"; }; clear() { rm -f "$B/sha.drivers"; } ;;
            id-c) what="the root file system differs from 6fce1688..."; line='^HALT: the guest root file system is not the expected one, or the expected value is not recorded \(packet section 4, halt 6\); nothing was started$'
                apply() { echo 1111111111111111111111111111111111111111111111111111111111111111 > "$B/sha.rootfs"; }; clear() { rm -f "$B/sha.rootfs"; } ;;
        esac
        echo "EXPECTED: $what: open S4 halts (exit 1) with nothing started$([ "$SC" = id-a ] && echo "; then, restored, open passes and the change made again halts row t6 before the attempt (verify_candidate before the row)"); close."
        apply
        run open S4
        want_rc 1 "open S4 with the identity changed"
        want "the halt names the identity" "$line"
        nothing_started
        if [ "$SC" = id-c ]; then
            want "the root file system read" '^rootfs ext4: 1111111111111111111111111111111111111111111111111111111111111111  '
            want "the expected value" "^expected:    $ROOTFS \(the value the close of S3's second opening recorded\)$"
        fi
        clear
        open_ok
        if [ "$SC" = id-a ]; then
            apply
            run row t6
            want_rc 1 "row t6 with the collector changed after open"
            want "the halt names the collector, and no attempt" "^HALT: collector \($B/repo/src/deployment/scripts/collect-resources\.sh\) is [0-9a-f]{64}, the recorded identity is $COLLECTOR_SHA: row t6 was NOT started and no attempt was created \(packet section 4, halt 6: an identity differing from section 1\)$"
            row_not_started
            clear
        fi
        close_ok
        ;;
    id-d)
        setup
        echo "EXPECTED: the gate driver's record of the running images differs from S2's in the controller's image id: open passes (the gate driver compares nothing); row t6 halts before the attempt is created ('the gate package's record ... differs from S2's ...: row t6 was NOT started and no attempt was created'); a second row t6 is refused (the recorded halt); close."
        sed -i 's/^\(identity egw-controller-1 .* image_id=sha256:\)9a293fe1/\100000000/' "$B/gate.identities"
        note "the bench's gate record changed: $(grep -c '^identity egw-controller-1 .*image_id=sha256:00000000' "$B/gate.identities") line"
        open_ok
        run row t6
        want_rc 1 "row t6"
        want "the record is shown against S2's" '^  S2:  identity egw-controller-1 image=egw-controller:0\.1\.0 image_id=sha256:9a293fe1'
        want "the halt, before the attempt" "^HALT: the gate package's record of the running images \(.*container_identities\.txt: 6 identity line\(s\)\) differs from S2's in an image reference, an image id or a repo digest, or is not six lines of the recorded form: row t6 was NOT started and no attempt was created \(request of 2026-10-05, section 5 item 1: an identity differing from the recorded candidate\)$"
        row_not_started
        is "halts recorded" "$(halts)" 1
        run row t6
        want_rc 2 "a second row t6 after the recorded halt"
        want "refused: the session has a recorded halt" "^REFUSED: NOT STARTED: session S4 has a recorded halt \(up=[0-9]+ row=t6 the gate package's record"
        row_not_started
        close_ok
        ;;
    pf-1 | pf-3)
        setup
        n=${SC#pf-}
        case $n in 1) echo fail > "$B/preflight.mode" ;; 3) echo invalid > "$B/preflight.mode" ;; esac
        echo "EXPECTED: the stub preflight's attempt ends $([ "$n" = 1 ] && echo 'valid/fail (collector-duration ended 1), which the frozen driver_status derives as 1' || echo 'failed/invalid, which the frozen driver_status derives as 3'): open S4 HALTS 'preflight.sh exited $n'; no exception exists (the script holds no EXCEPTION and no s3b_preflight_exception), so no environment copy, no gate, no guest listing; the session is recorded halted; row t6 refused; close closes the guest."
        say "the script under test, read: the exception of S3b is gone"
        is "lines of the script holding 'EXCEPTION'" "$(count 'EXCEPTION' "$FINAL")" 0
        is "lines of the script holding 's3b_preflight_exception'" "$(count 's3b_preflight_exception' "$FINAL")" 0
        note "lines of the script holding 'exception' in any case (each a comment that says it was removed):"
        grep -ni 'exception' "$FINAL" | cut -c1-200 | sed 's/^/    | /'
        is "lines holding 'exception' in any case that are not comments" "$(grep -i 'exception' "$FINAL" | grep -cv '^[[:space:]]*#')" 0
        run open S4
        want_rc 1 "open S4"
        want "the preflight driver's exit" "^preflight\.sh exit=$n$"
        want "the halt of open, S3's first opening's form" "^HALT: preflight\.sh exited $n; see $BSTATE/S4-preflight\.console\.txt$"
        want "the operator's next step" "^The session state is 'halted' and nothing was closed\. If '.*current_session' exists the guest is UP: decide, then run 'close'\.$"
        want_no "no exception is examined or applied" '[Ee][Xx][Cc][Ee][Pp][Tt][Ii][Oo][Nn]'
        want_no "no environment copy" '^## environment input'
        is "the environment copy's record" "$(exists "$BSTATE/S4-environment-copy.txt")" absent
        is "the harness input sut_environment.json (unchanged since the setup)" "$(sha "$HOME/egw-tcg/sut_environment.json")" "$SUT0"
        is "sut_environment keys in the session's state file" "$(skeys 'sut_environment[a-z_]*')" 0
        want_no "the gate driver is NOT run" 'gate_health\.sh \(frozen driver'
        is "the gate driver's console" "$(ls "$BSTATE"/S4-gate_health.console*.txt 2> /dev/null | wc -l)" 0
        is "gate attempts created" "$(ls -d "$EGW_ATTEMPTS"/*_g2-gate-preconditions_attempt* 2> /dev/null | wc -l)" 0
        is "gate_health_exit in the session's state file" "$(skeys gate_health_exit)" 0
        want_no "the guest listing is NOT run" 'unused on the guest'
        is "the session's state" "$(skey state)" halted
        is "preflight_exit recorded" "$(skey preflight_exit)" "$n"
        is "the preflight attempt recorded exists" "$([ -d "$(skey preflight_attempt)" ] && echo exists || echo absent)" exists
        is "halts recorded" "$(halts)" 1
        is "an open session (current_session): the guest is up" "$(exists "$EGW_EXEC/current_session")" exists
        run row t6
        want_rc 2 "row t6 after the halted open"
        want "refused: the session is recorded halted" "^REFUSED: session S4 is recorded 'halted', not open$"
        row_not_started
        run close
        want_rc 0 "close"
        want "the session is closed" '^## .* session S4 closed \(guest_session_close\.sh exit 0\)'
        is "the session's state after close" "$(skey state)" closed
        is "halts after close (no new one)" "$(halts)" 1
        is "the fake QEMU after close" "$(qemu_state | sed 's/^pid [0-9a-z]* //')" "not running"
        ;;
    out-h1 | out-h2 | out-h3 | out-gaveup | out-delta4 | out-eo4 | out-eo1)
        setup
        case $SC in
            out-h1) st bench_harness_rc 1; exp="the harness ends 1 (INVALID; no SHA256SUMS): T6=stop ('the harness run was not sealed, or it exited 1'); no delta and no acceptance are called (their two STOP lines name T6='stop'); analyze runs; the gate passes (the restart ran inside the harness); classify invalid/unknown (a halt of classify)" ;;
            out-h2) st bench_harness_rc 2; exp="the harness refuses (exit 2; nothing written): the line prints 'resources_proved_down: not read - harness_cmd answered 2', T6=stop ('... exited 2 ...'); no delta, no acceptance; no restart reached the guest, so the gate's guest-state pair does not show the expected restart: the gate fails and the row records a halt; a second row t6 refused; classify not-applicable/not-run" ;;
            out-h3) st bench_harness_rc 0; st events_cleanup_rc 1; exp="the harness ends 0 but the recorder's cleanup fails: harness_cmd answers 3, T6=incomplete ('the procedure is INCOMPLETE'); no delta, no acceptance; the recorder unit is left active on the stub guest, so the gate fails (a unit active) and the row records a halt; classify unknown/inconclusive; close halts on the active unit; the runbook's own cleanup by hand (the README's one prescribed restoration); close again" ;;
            out-gaveup) st bench_drain_outcome gave-up; exp="the harness ends 0 with drain.outcome 'gave-up': T6=gaveup ('the drain gave up'); no delta, no acceptance; the gate passes; classify valid/fail" ;;
            out-delta4) st rec_delta_rc 4; exp="T6=ok; delta ends 4 ('delta NOT run (T6='ok') or it exited non-zero (4 = MISMATCH)'), and --exactly-once still runs (line 1427 reads T6 only) and ends 0; the gate passes; classify valid/fail" ;;
            out-eo4) st rec_acceptance_rc 4; exp="T6=ok; delta 0; acceptance --exactly-once ends 4: its STOP line ('... (exit 4: test 6 FAILS)'); the gate passes; classify valid/fail" ;;
            out-eo1) st rec_acceptance_rc 1; exp="T6=ok; delta 0; acceptance --exactly-once ends 1: its STOP line ('... (exit 1: test 6 NOT evaluated) ...'); the gate passes; classify invalid/unknown (a halt of classify)" ;;
        esac
        echo "EXPECTED: open S4; row t6 runs the REAL t6.sh with the REAL helpers (line 1425's drained runs its real 130 s window; the harness stand-in writes its files itself); $exp. In each the attempt stays open for classification (state awaiting-classification); a halt is recorded only where the script records one."
        open_ok
        case $SC in out-h2 | out-h3) row_ran 1 ;; *) row_ran 0 ;; esac
        RAW=$HOME/egw-tcg/pilot/results/raw/$RID
        step_calls
        case $SC in
            out-h1)
                want "the harness's INVALID line" '^\[harness\] INVALID: bench case: harness exit 1' "$C"
                want "T6=stop: the run was not sealed or the harness exited 1" '^STOP: test 6: the harness run was not sealed, or it exited 1 ' "$C"
                is "the run directory is not sealed (no SHA256SUMS)" "$(exists "$RAW/SHA256SUMS")" absent
                is "r04 in the plan after the step" "$(plan_r04 "$A/other/campaign_plan.after.json")" "failed validity=invalid result_dir=set finished_utc=set" ;;
            out-h2)
                want "the line reads no manifest" '^test 6: resources_proved_down: not read - harness_cmd answered 2, the harness was not started' "$C"
                want "T6=stop: the harness exited 2" '^STOP: test 6: the harness run was not sealed, or it exited 2 \(the \[harness\] INVALID lines above name the reasons, a drain that ended in error among them; 2: the harness was not started' "$C"
                is "no run directory" "$(exists "$RAW")" absent
                is "no restart reached the stub guest" "$(restarts)" 0
                is "r04 in the plan after the step (untouched)" "$(plan_r04 "$A/other/campaign_plan.after.json")" "planned validity=None result_dir=none finished_utc=none"
                want "the gate's pair does not show the expected restart (a problem)" '^PROBLEM: .*egw-controller-1' "$(console guest-state-delta)"
                want "the gate failed and the row recorded a halt" '^HALT: row t6: the gate did NOT pass \(packet section 4, halt 3\): guest-state-delta exit 2'
                is "halts recorded" "$(halts)" 1
                run row t6
                want_rc 2 "a second row t6 after the halt"
                want "refused: the row was already started" '^REFUSED: row t6 was already started' ;;
            out-h3)
                want "harness_cmd: the harness answered 0, the cleanup failed, status 3" "^STOP: harness_cmd $RID: the harness answered 0, and the Docker events recorder's cleanup after it FAILED" "$C"
                want "T6=incomplete" '^STOP: test 6: the procedure is INCOMPLETE - the Docker events recorder.s cleanup failed after the harness' "$C"
                is "the stub recorder unit is left active" "$(cat "$EGW_STUB_STATE/unit-$RID")" active
                want "the gate failed on the active unit and the row recorded a halt" '^HALT: row t6: the gate did NOT pass \(packet section 4, halt 3\): a recorder or collector unit is still active \(gate-units exit 3\)'
                is "halts recorded" "$(halts)" 1 ;;
            out-gaveup)
                want "T6=gaveup" "^STOP: test 6: the drain gave up \(manifest drain\.outcome 'gave-up'\): a failed recovery" "$C" ;;
            out-delta4)
                want "delta ended 4" '^itest_reconcile stub: delta exit=4$' "$C"
                want "line 1426's STOP" "^STOP: test 6: delta NOT run \(T6='ok'\) or it exited non-zero \(4 = MISMATCH\)$" "$C"
                want "line 1427 still ran (T6=ok) and ended 0" '^itest_reconcile stub: acceptance exit=0$' "$C"
                want_no "no STOP of line 1427" '^STOP: test 6: the per-identity exactly-once check' "$C" ;;
            out-eo4 | out-eo1)
                n=${SC#out-eo}
                want "delta ended 0" '^itest_reconcile stub: delta exit=0$' "$C"
                want "acceptance --exactly-once ended $n" "^itest_reconcile stub: acceptance exit=$n$" "$C"
                want "line 1427's STOP" "^STOP: test 6: the per-identity exactly-once check was not run \(T6='ok'\), could not read its inputs \(exit 1: test 6 NOT evaluated\) or found a valid message never accepted or accepted more than once in the post-drain copy \(exit 4: test 6 FAILS\)$" "$C"
                want_no "no STOP of line 1426" '^STOP: test 6: delta' "$C" ;;
        esac
        case $SC in
            out-h1 | out-h2 | out-h3 | out-gaveup)
                is "line 1426: delta was NOT called" "$(count 'itest_reconcile delta' "$EGW_STUB_STATE/calls.log")" 0
                is "line 1427: acceptance was NOT called" "$(count 'itest_reconcile acceptance' "$EGW_STUB_STATE/calls.log")" 0
                want "line 1426's STOP names T6" "^STOP: test 6: delta NOT run \(T6='(stop|incomplete|gaveup)'\)" "$C"
                want "line 1427's STOP names T6" "^STOP: test 6: the per-identity exactly-once check was not run \(T6='(stop|incomplete|gaveup)'\)" "$C" ;;
            *)
                is "line 1426: delta was called once" "$(count 'itest_reconcile delta' "$EGW_STUB_STATE/calls.log")" 1
                is "line 1427: acceptance --exactly-once was called once" "$(count 'itest_reconcile acceptance .* --exactly-once$' "$EGW_STUB_STATE/calls.log")" 1 ;;
        esac
        want "line 1428: analyze ran in every case" '^\[analyze\] BENCH STAND-IN' "$C"
        is "the step's own status (analyze's, never a verdict)" "$(sed -n 's/^step_done=t6 exit=\([0-9]*\) .*/\1/p' "$BSTATE/row-t6.env")" 0
        case $SC in
            out-h2 | out-h3) ;;
            *)
                want "the gate passed (the restart ran inside the harness)" '^## .* GATE t6: pass'
                is "halts recorded by the row" "$(halts)" 0 ;;
        esac
        case $SC in
            out-h1) cls="failed invalid unknown"; crc=1 ;;
            out-h2) cls="failed not-applicable not-run"; crc=1 ;;
            out-h3) cls="failed unknown inconclusive"; crc=0 ;;
            out-gaveup | out-delta4 | out-eo4) cls="finished valid fail"; crc=0 ;;
            out-eo1) cls="failed invalid unknown"; crc=1 ;;
        esac
        # shellcheck disable=SC2086
        classify_as $cls
        want_rc "$crc" "classify t6 $cls"
        want "classified and exported (the export tool's own verification)" "^row t6: classified '[^']+'; driver code [0-9]+; export: verified(; incomplete: [^>]*)? -> "
        if [ "$SC" = out-h2 ]; then
            want "the package names the one registered artefact never written: the raw directory the refused harness never made" "^row t6: classified 'not started'; driver code [0-9]+; export: verified; incomplete: 0 registered source root\(s\), 0 registered artefact\(s\) below one, 0 file\(s\) or folder\(s\) of the attempt itself, 1 registered artefact\(s\) that were never written and 0 declared expected artefact\(s\) are NOT in this package -> "
        fi
        if [ "$SC" = out-h3 ]; then
            run close
            want_rc 1 "close with the recorder unit active"
            want "close halts on the active unit, nothing stopped" '^HALT: close: a recorder or collector unit is active \(exit 3\): nothing was stopped'
            is "the session is still open" "$(skey state)" open
            is "no stop was sent" "$(count 'stop -t 130' "$EGW_STUB_STATE/ssh.log")" 0
            say "the operator's one prescribed restoration (README): the runbook's own cleanup of the recorder of r04, by hand"
            rm -f "$EGW_STUB_STATE/events_cleanup_rc"
            bash "$B/repo/tools/session/events_capture.sh" cleanup "$RID"
            echo "-> cleanup exit $?"
            close_ok
        else
            close_ok
        fi
        ;;
    term | term-pipe-exp)
        setup
        st bench_harness_sleep 900
        if [ "$SC" = term-pipe-exp ]; then
            # EXPERIMENT, not the script under test: a copy of the final bytes whose step shell
            # ignores SIGPIPE ('trap "" PIPE' in front of STEP_PRE's text), run with <P>/rows.
            mkdir -p "$B/script" || exit 1
            sed 's/^STEP_PRE='"'"'exec 2>&1; /STEP_PRE='"'"'trap "" PIPE; exec 2>\&1; /' "$FINAL" > "$B/script/g3_battery.sh" || exit 1
            G=$B/script/g3_battery.sh
            export EGW_G3_ROWS=$PREP/rows
            is "EXPERIMENT: the copy differs from the final bytes in STEP_PRE only (diff lines)" "$(diff "$FINAL" "$G" | grep -c '^[<>]')" 2
            note "EXPERIMENT: the copy's STEP_PRE begins: $(grep '^STEP_PRE=' "$G" | cut -c1-60)"
        fi
        echo "EXPECTED: open S4; row t6 started detached as the launcher starts it; once the harness stand-in sleeps inside the run, 'term t6' sends TERM (never KILL) to the row's recorded process group; the row's trap finishes the attempt 'interrupted' and exports it; the fake QEMU (its own session) and the keepalive clients are untouched; then status and close.$([ "$SC" = term-pipe-exp ] && echo " EXPERIMENT (a copy whose step shell ignores SIGPIPE): harness_cmd's own cleanup stops the recorder, and close needs no restoration.")"
        open_ok
        # The host's keepalive clients, each named by pid, start tick (field 22 of /proc/PID/stat:
        # 'ps lstart' moves with this host's wall clock, which WSL steps) and command line.
        keepalives() {
            local pid
            for pid in $(/usr/bin/ps -eo pid=,args= 2> /dev/null | awk '$2 == "sleep" && NF == 3 && $3 >= 3600 { print $1 }'); do
                echo "pid $pid start tick $(cut -d' ' -f22 "/proc/$pid/stat" 2> /dev/null) '$(tr '\0' ' ' < "/proc/$pid/cmdline" 2> /dev/null | sed 's/ $//')'"
            done | tr '\n' ';'
        }
        K0=$(keepalives)
        say "g3_battery.sh row t6 (detached, as ops/g3_go.sh starts it)"
        setsid bash "$G" row t6 < /dev/null > "$B/row.out" 2>&1 &
        ROWPID=$!
        n=0
        while [ ! -s "$B/harness.started" ] && [ "$n" -lt 480 ] && kill -0 "$ROWPID" 2> /dev/null; do /usr/bin/sleep 1; n=$((n + 1)); done
        is "the harness stand-in is sleeping inside the run" "$(exists "$B/harness.started")" exists
        HPID=$(cat "$B/harness.started" 2> /dev/null)
        PG=$(row_key pgid)
        note "after $n s: the row's process group $PG (pgrep -g, command lines cut at 100):"
        /usr/bin/pgrep -g "$PG" -a 2> /dev/null | sed -E 's/(--password)([= ]+)[^ ]+/\1\2<hidden>/g' | mask | cut -c1-100 | sed 's/^/    | /'
        is "the harness stand-in is in the row's process group" "$(ps -o pgid= -p "$HPID" 2> /dev/null | tr -d ' ')" "$PG"
        is "the fake QEMU is NOT in the row's process group" "$(ps -o pgid= -p "$(cat "$B/qemu.pid")" 2> /dev/null | tr -d ' ' | grep -cx "$PG")" 0
        run term t6
        want_rc 0 "term t6"
        want "TERM, never KILL, to the recorded group" "^TERM sent to the process group $PG \(exit 0\)\. KILL is never sent\.$"
        want_no "term recorded no halt (no QEMU, no keepalive in the group)" '^HALT'
        n=0
        while kill -0 "$ROWPID" 2> /dev/null && [ "$n" -lt 400 ]; do /usr/bin/sleep 1; n=$((n + 1)); done
        wait "$ROWPID" 2> /dev/null
        note "the row process ended $n s after the TERM (exit $?); its console (decisive lines):"
        grep -E "$DECISIVE|interrupted|driver code" "$B/row.out" | mask | cut -c1-300 | sed 's/^/    | /'
        want "the row's trap ran" '^## .* row t6: interrupted by a signal \((TERM|HUP|INT)\)$' "$B/row.out"
        want "the halt of the interrupt" '^HALT: row t6 was interrupted by a signal \((TERM|HUP|INT)\) during ' "$B/row.out"
        want "the attempt finished 'interrupted' and exported" "^row t6: attempt finished 'interrupted'; driver code 130; export: verified -> $EGW_OUTPUT_TEST/runs/" "$B/row.out"
        A=$(attempt_of)
        is "row state" "$(row_key state)" interrupted
        is "attempt.json status" "$("$REAL_PY" -c 'import json,sys; print(json.load(open(sys.argv[1])).get("status"))' "$A/attempt.json")" interrupted
        is "the package exists" "$(ls -d "$EGW_OUTPUT_TEST"/runs/*/"$(basename "$A")" 2> /dev/null | wc -l)" 1
        is "the harness stand-in is gone" "$([ -d "/proc/$HPID" ] && echo alive || echo gone)" gone
        is "the fake QEMU process after the term (same pid and start tick)" "$(qemu_state)" "$Q0"
        K1=$(keepalives)
        note "keepalive clients of the host before the row: ${K0:-none}"
        note "keepalive clients of the host after the term: ${K1:-none}"
        is "the host's keepalive clients (pid, start tick, command line) unchanged" "$K1" "$K0"
        is "the bench's synthetic keepalive client (pid 4194301) was never a process" "$(exists /proc/4194301)" absent
        note "the step console after the TERM (last lines; harness_cmd's trap line 'harness_cmd $RID: interrupted - ...' is not among them):"
        tail -n 6 "$(console t6)" 2> /dev/null | mask | cut -c1-300 | sed 's/^/    | /'
        note "the attempt's capture failures (the TERM also ended local_export exec, which held the step's console pipes): $("$REAL_PY" -c 'import json,sys; print(json.load(open(sys.argv[1])).get("capture_failures"))' "$A/attempt.json" | cut -c1-300)"
        note "what the stub recorder was asked (capture.log) and the unit's state: $(tr '\n' ' ' < "$EGW_STUB_STATE/capture.log" 2> /dev/null); unit-$RID=$(cat "$EGW_STUB_STATE/unit-$RID" 2> /dev/null)"
        note "harness_cmd's trap line ('harness_cmd $RID: interrupted - ...') in the step's console: $(count "^harness_cmd $RID: interrupted" "$(console t6)"); its events_cleanup invoked (capture.log): $(count 'capture \[cleanup\]' "$EGW_STUB_STATE/capture.log")"
        if [ "$(cat "$EGW_STUB_STATE/unit-$RID" 2> /dev/null)" = active ]; then
            note "FINDING (bench-notes section 4; record/sigpipe.console.txt): harness_cmd's own interruption cleanup did NOT stop the recorder - the TERM to the group also ended the console capture (local_export exec), and what harness_cmd runs after its trap writes into that closed pipe and is killed by SIGPIPE at its first write (the subshell itself, or the cleanup's child); the recorder unit egw-events-$RID is left ACTIVE on the (stub) guest"
        else
            note "the recorder unit egw-events-$RID was stopped by harness_cmd's own cleanup after the TERM"
        fi
        if [ "$SC" = term-pipe-exp ]; then
            is "EXPERIMENT: with SIGPIPE ignored in the step shell, harness_cmd's cleanup stopped the recorder unit" "$(cat "$EGW_STUB_STATE/unit-$RID" 2> /dev/null)" inactive
        fi
        note "the group's last reading (row-t6.group-after-signal.txt): $(tr '\n' ';' < "$BSTATE/row-t6.group-after-signal.txt" 2> /dev/null | mask | cut -c1-300)"
        status_now
        run close
        if [ "$RC" = 0 ]; then
            ok "close after the term: exit 0"
            want "the session is closed" '^## .* session S4 closed \(guest_session_close\.sh exit 0\)'
        else
            note "close after the term: exit $RC (see above)"
            if grep -q '^HALT: close: a recorder or collector unit is active' "$B/last.out"; then
                ok "close halts on the recorder unit left active, and stops nothing (exit $RC)"
                is "no stop was sent to the stub guest" "$(count 'stop -t 130' "$EGW_STUB_STATE/ssh.log")" 0
                is "the session is still open" "$(skey state)" open
                note "bench only: the runbook's own cleanup of the recorder of r04, by hand (the README prescribes it after T6=incomplete; after a 'term' it is Rui's decision), so that the bench can show the close that follows"
                bash "$B/repo/tools/session/events_capture.sh" cleanup "$RID"
                close_ok
            else
                bad "close after the term ended $RC"
            fi
        fi
        is "the session's state after close" "$(skey state)" closed
        ;;
    integrity)
        setup
        mkdir -p "$B/rows" "$B/script" || exit 1
        cp -p "$PREP"/rows/* "$B/rows/" || exit 1
        export EGW_G3_ROWS=$B/rows
        echo "EXPECTED: with EGW_G3_ROWS naming a byte-identical copy of <P>/rows: a changed t6.sh halts open (nothing started); restored, open passes; then, the session open: (a) a changed copy of the script is refused for 'row' (exit 2); (b) a changed manifest is refused (exit 2); (c) a changed t6.sh halts row t6 before the attempt (the manifest's check); (d) row t6, all restored, is refused (the recorded halt); close."
        is "the bench's copy of t6.sh (sha256)" "$(sha "$B/rows/t6.sh")" "$ROWS0"
        is "the bench's copy of the manifest (sha256)" "$(sha "$B/rows/rows.manifest.json")" "$(sha "$PREP/rows/rows.manifest.json")"
        echo '# bench: one line appended' >> "$B/rows/t6.sh"
        run open S4
        want_rc 1 "open S4 with t6.sh changed"
        want "the manifest's check names the file" '^STOP: t6\.sh: sha256 [0-9a-f]{64} is not the manifest sha256_after [0-9a-f]{64}$'
        want "the halt of open" "^HALT: the row files of t6 are not the manifest's; nothing was started$"
        nothing_started
        cp -p "$PREP/rows/t6.sh" "$B/rows/t6.sh"
        open_ok
        want "open verified the row file" "^row file t6\.sh: sha256 $ROWS0 = sha256_after of the manifest \(row t6, step 1, [0-9]+ bytes\)$"
        cp -p "$FINAL" "$B/script/g3_battery.sh"
        echo '# bench: one comment appended' >> "$B/script/g3_battery.sh"
        G=$B/script/g3_battery.sh
        run row t6
        want_rc 2 "(a) row t6 with a changed copy of the script"
        want "refused: not the script the session was opened with" "^REFUSED: this steps script is not the one session S4 was opened with \(sha256 $SCRIPT0\)$"
        row_not_started
        G=$FINAL
        cp -p "$B/rows/rows.manifest.json" "$B/hold/manifest.json"
        echo >> "$B/rows/rows.manifest.json"
        run row t6
        want_rc 2 "(b) row t6 with the manifest changed"
        want "refused: not the manifest the session was opened with" '^REFUSED: rows\.manifest\.json is not the one session S4 was opened with$'
        row_not_started
        cp -p "$B/hold/manifest.json" "$B/rows/rows.manifest.json"
        echo '# bench: one line appended' >> "$B/rows/t6.sh"
        run row t6
        want_rc 1 "(c) row t6 with t6.sh changed"
        want "the manifest's check names the file" '^STOP: t6\.sh: sha256 [0-9a-f]{64} is not the manifest sha256_after [0-9a-f]{64}$'
        want "the halt: the row was not started" "^HALT: the row files of t6 are not the manifest's: the row was NOT started and no attempt was created$"
        row_not_started
        is "halts recorded" "$(halts)" 1
        cp -p "$PREP/rows/t6.sh" "$B/rows/t6.sh"
        run row t6
        want_rc 2 "(d) row t6, all restored"
        want "refused: the recorded halt" '^REFUSED: NOT STARTED: session S4 has a recorded halt'
        row_not_started
        close_ok
        ;;
    *)
        echo "unknown scenario '$SC'"
        exit 2
        ;;
esac
finish
[ "$FAILS" -eq 0 ]
exit
}
