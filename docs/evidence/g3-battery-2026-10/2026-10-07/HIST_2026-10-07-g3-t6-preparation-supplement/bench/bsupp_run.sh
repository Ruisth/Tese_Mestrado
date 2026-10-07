#!/bin/bash
# SUPPLEMENT of 2026-10-07 (the Project Manager's order, register line 4937): the ONE offline
# verification of the recorder's emergency cleanup, ops/g3_recorder_cleanup.sh, on the path it
# is for: open S4, row t6 with the harness stand-in asleep, 'term t6' (the recorder unit is left
# active: finding F1 of the preparation's bench), then the new script, then 'close'. Built by
# make_bsupp.py from the sealed bench's bs4_run.sh: its helpers, below, are that file's lines
# 1-241 with only the three path lines changed; bs4_setup.sh and bs4_env.sh are used unchanged.
# In the bench copy only, after the TERM, events_capture.sh is the REAL one of 1fd9792 (the
# module's stub stood for it during the row); the stub guest answers its cleanup script and
# its scp from supp-stubs/ (first on PATH), with one fault per case:
#   supp-ok      none: try 1 keeps the four files; close; the session's package holds them
#   supp-retry   try 1: the scp of cli.stderr fails (3 of 4 copied: the INCOMPLETE staging
#                folder is kept and exported); try 2 keeps the four files; close
#   supp-hang    try 1: the scp of events.jsonl hangs; timeout 120 ends the try (exit 124);
#                try 2 keeps the four files; close
#   supp-halt    the unit is never shown stopped: three tries end 1; HALT; close NOT run by the
#                script; nothing signalled (the fake QEMU unchanged); the session stays open
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
SUPP=$(cd "$(dirname "$0")/.." && pwd)    # <S>/g3/t6supp (the supplement)
SCR=$(cd "$SUPP/../.." && pwd)            # <S>
PREP=$SCR/g3/t6prep                       # <P>, the sealed preparation's working folder
HERE=$PREP/bench                          # the sealed bench: bs4_setup.sh, bs4_env.sh (used unchanged)
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
    bash "$SUPP/bench/bsupp_setup.sh" "$B" > "$ROOT/_logs/$SC.setup.log" 2>&1 || { echo "setup failed:"; tail -n 8 "$ROOT/_logs/$SC.setup.log" | mask; exit 1; }
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

SUPP_SCRIPT=$SUPP/ops/g3_recorder_cleanup.sh
REAL_CAPTURE=$SCR/t6m/tools/session/events_capture.sh
REAL_CAPTURE_SHA=$(sha "$REAL_CAPTURE")
KEEP_NAME=recovery/events-partial-$RID

supp_stubs() {     # the stub guest's answers to the REAL cleanup (first on PATH)
    mkdir -p "$B/supp-stubs" "$B/guest-tmp/egw-events-$RID" || exit 1
    printf '{"status":"die","id":"bench","timeNano":1}\n{"status":"start","id":"bench","timeNano":2}\n' > "$B/guest-tmp/egw-events-$RID/events.jsonl"
    printf 'start epoch=1790000000\nready epoch=1790000001 events_bytes=100 unit=active\n' > "$B/guest-tmp/egw-events-$RID/lifecycle.txt"
    printf 'boot_id=bench\ndocker_mainpid=1\n' > "$B/guest-tmp/egw-events-$RID/start-facts.txt"
    : > "$B/guest-tmp/egw-events-$RID/cli.stderr"
    cat > "$B/supp-stubs/ssh" << 'EOS'
#!/bin/bash
# SUPPLEMENT BENCH WRAPPER of ssh: answers the REAL events_capture.sh cleanup script and the
# new script's read of the unit state from the stub guest's unit file; every other call goes
# to the sealed bench's wrapper unchanged.
S=$EGW_STUB_STATE
cmd="${@: -1}"
R=controller_restart-r04
log() { { printf 'ssh'; for a in "$@"; do printf ' [%s]' "$(printf '%s' "$a" | head -c 160 | tr '\n' ' ')"; done; echo; } >> "$S/ssh.log"; }
case $cmd in
    *unit_state_before_cleanup*)
        log "$@"; [ ! -e "$BENCH/guest.down" ] || { echo "ssh: connect to host: Connection refused" >&2; exit 255; }
        state=$(cat "$S/unit-$R" 2> /dev/null || echo inactive)
        echo "unit_state_before_cleanup=$state"
        rc=0
        case $state in
            inactive | failed) ;;
            *)
                echo "cleanup_stop_requested_guest_epoch=1790000600"
                echo "stop egw-events-$R" >> "$S/supp.unit-stops"
                if [ -e "$BENCH/supp.unit-stuck" ]; then rc=1; else echo inactive > "$S/unit-$R"; fi
                echo "unit_state_after_cleanup=$(cat "$S/unit-$R")" ;;
        esac
        echo "--- the recorder's lifecycle record (/tmp/egw-events-$R/lifecycle.txt; its capture stays in /tmp/egw-events-$R)"
        cat "$BENCH/guest-tmp/egw-events-$R/lifecycle.txt"
        echo "events_lines=$(wc -l < "$BENCH/guest-tmp/egw-events-$R/events.jsonl")"
        echo "cli_stderr_bytes=0"
        exit $rc ;;
    *"systemctl is-active egw-events-$R"*)
        log "$@"; [ ! -e "$BENCH/guest.down" ] || { echo "ssh: connect to host: Connection refused" >&2; exit 255; }
        s=$(cat "$S/unit-$R" 2> /dev/null || echo inactive)
        echo "unit_state=$s"
        case $s in inactive | failed) exit 0 ;; *) exit 1 ;; esac ;;
esac
exec "$BENCH/stubs/ssh" "$@"
EOS
    cat > "$B/supp-stubs/scp" << 'EOS'
#!/bin/bash
# SUPPLEMENT BENCH WRAPPER of scp: copies the recorder's files from the stub guest's /tmp;
# a fault flag of the case acts once (fail: exit 1; hang: sleeps until the try's timeout ends
# it); every other call goes to the module's stub unchanged.
S=$EGW_STUB_STATE
R=controller_restart-r04
src= dest=
for a in "$@"; do case $a in -*) ;; *) [ -z "$src" ] && src=$a || dest=$a ;; esac; done
case $src in
    "egw-tcg:/tmp/egw-events-$R/"*)
        f=${src##*/}
        echo "scp [$src] [$dest]" >> "$S/supp.scp.log"
        if [ -e "$BENCH/supp.scp.fail.$f" ]; then rm -f "$BENCH/supp.scp.fail.$f"; echo "scp: bench fault: $f not copied" >&2; exit 1; fi
        if [ -e "$BENCH/supp.scp.hang.$f" ]; then rm -f "$BENCH/supp.scp.hang.$f"; echo $$ > "$BENCH/supp.scp.hang.pid"; exec /usr/bin/sleep 600; fi
        [ -f "$BENCH/guest-tmp/egw-events-$R/$f" ] || { echo "scp: $src: No such file or directory" >&2; exit 1; }
        cp "$BENCH/guest-tmp/egw-events-$R/$f" "$dest" ;;
    *) exec "$BENCH/mod/stubs/scp" "$@" ;;
esac
EOS
    chmod +x "$B/supp-stubs/ssh" "$B/supp-stubs/scp"
}

term_path() {      # open S4, row t6 with the harness asleep, term t6: the recorder left active (F1)
    st bench_harness_sleep 900
    open_ok
    say "g3_battery.sh row t6 (detached, as ops/g3_go.sh starts it)"
    setsid bash "$G" row t6 < /dev/null > "$B/row.out" 2>&1 &
    ROWPID=$!
    local n=0
    while [ ! -s "$B/harness.started" ] && [ "$n" -lt 480 ] && kill -0 "$ROWPID" 2> /dev/null; do /usr/bin/sleep 1; n=$((n + 1)); done
    is "the harness stand-in is asleep inside the run" "$(exists "$B/harness.started")" exists
    run term t6
    want_rc 0 "term t6"
    n=0
    while kill -0 "$ROWPID" 2> /dev/null && [ "$n" -lt 400 ]; do /usr/bin/sleep 1; n=$((n + 1)); done
    wait "$ROWPID" 2> /dev/null
    want "the row's attempt finished 'interrupted' and exported" "^row t6: attempt finished 'interrupted'; driver code 130; export: verified -> " "$B/row.out"
    is "F1 reproduced: the recorder unit is left active on the stub guest" "$(cat "$EGW_STUB_STATE/unit-$RID" 2> /dev/null)" active
    Q0=$(qemu_state)
    note "the fake QEMU after the term: $Q0"
    # bench only: the REAL events_capture.sh of 1fd9792 in the copy, for the cleanup
    cp "$REAL_CAPTURE" "$B/repo/tools/session/events_capture.sh" || exit 1
    is "bench copy: events_capture.sh is now the REAL one of 1fd9792 (sha256)" "$(sha "$B/repo/tools/session/events_capture.sh")" "$REAL_CAPTURE_SHA"
    supp_stubs
    export PATH=$B/supp-stubs:$PATH
    SESS=$(cat "$EGW_EXEC/current_session")
    KEEP=$SESS/$KEEP_NAME
}

cleanup_run() {    # the new script, as the operator runs it
    say "ops/g3_recorder_cleanup.sh (sha256 $(sha "$SUPP_SCRIPT"))"
    T0=$(cut -d' ' -f1 /proc/uptime)
    EGW_EXEC_REPO=$B/repo setsid bash "$SUPP_SCRIPT" < /dev/null > "$B/cleanup.out" 2>&1
    RC=$?
    T1=$(cut -d' ' -f1 /proc/uptime)
    echo "-> exit $RC after $(awk -v a="$T0" -v b="$T1" 'BEGIN { printf "%.0f", b - a }') s"
    grep -E '^(## |events_capture|KEEP_DIR|try [0-9]|kept INCOMPLETE|OK:|HALT:|REFUSED:|the unit|STOP)' "$B/cleanup.out" | mask | cut -c1-400 | sed 's/^/    | /'
}

keep_complete() {  # the four files in KEEP_DIR, equal to the stub guest's
    local f
    for f in lifecycle.txt start-facts.txt; do
        is "KEEP_DIR/$f equals the guest's" "$(sha "$KEEP/$f")" "$(sha "$B/guest-tmp/egw-events-$RID/$f")"
    done
    is "KEEP_DIR/events.partial.jsonl equals the guest's events.jsonl" "$(sha "$KEEP/events.partial.jsonl")" "$(sha "$B/guest-tmp/egw-events-$RID/events.jsonl")"
    is "KEEP_DIR/cli-stderr.txt equals the guest's cli.stderr" "$(sha "$KEEP/cli-stderr.txt")" "$(sha "$B/guest-tmp/egw-events-$RID/cli.stderr")"
    is "no docker-events.log is written for the partial capture" "$(find "$SESS/recovery" -name docker-events.log | wc -l)" 0
}

session_steps() {  # the session attempt's recorded steps of the cleanup
    note "the session attempt's recorded cleanup steps: $(ls "$SESS/console" | sed -n 's/^[0-9]*-\(recorder-[^.]*\)\.stdout\.txt$/\1/p' | sort -u | tr '\n' ' ')"
}

close_and_package() {   # close; the session's package holds the partial capture
    close_ok
    PKG=$(ls -d "$EGW_OUTPUT_TEST"/runs/*/"$(basename "$SESS")" 2> /dev/null | head -n 1)
    is "the session's package exists" "$([ -n "$PKG" ] && echo exists || echo absent)" exists
    is "the package's SHA256SUMS verify" "$(cd "$PKG" && /usr/bin/sha256sum -c --quiet SHA256SUMS > /dev/null 2>&1 && echo verified || echo FAILED)" verified
    local f
    for f in events.partial.jsonl lifecycle.txt start-facts.txt cli-stderr.txt; do
        is "the package holds $KEEP_NAME/$f, equal to KEEP_DIR's" "$(sha "$PKG/$KEEP_NAME/$f")" "$(sha "$KEEP/$f")"
    done
    want "the package's SHA256SUMS lists the partial capture" "  $KEEP_NAME/events\.partial\.jsonl$" "$PKG/SHA256SUMS"
}

nothing_signalled() {   # nothing stopped, powered off or signalled but the recorder unit
    is "the fake QEMU before the close (same pid and start tick)" "$(qemu_state)" "$Q0"
    is "no stop of the stack or power-off reached the stub guest before close" "$(grep -cE 'stop -t (130|60)|poweroff|shutdown' "$EGW_STUB_STATE/ssh.log")" 0
    is "the script never runs close" "$(grep -c 'g3_battery' "$B/cleanup.out")" 0
}

{
case $SC in
    supp-ok)
        setup
        echo "EXPECTED: after the TERM the recorder is left active (F1); the new script's try 1 stops it and keeps the four files in <session>/$KEEP_NAME; both confirmations hold; 'OK: ... close may run'; a second invocation adds no try; close exports the session's package with the partial capture."
        term_path
        cleanup_run
        want_rc 0 "the new script"
        want "try 1 ended 0" '^try 1: exit 0$' "$B/cleanup.out"
        want "the cleanup kept the four files in KEEP_DIR" "^events_capture: cleanup: the recorder's 4 files kept in $KEEP \(a partial capture, not the run's\)$" "$B/cleanup.out"
        want "OK, close may run" "^OK: the recorder egw-events-$RID is stopped and its partial capture is kept in $KEEP \(try 1\): 'close' may run$" "$B/cleanup.out"
        is "the unit on the stub guest" "$(cat "$EGW_STUB_STATE/unit-$RID")" inactive
        is "stops sent to the unit" "$(wc -l < "$EGW_STUB_STATE/supp.unit-stops")" 1
        keep_complete
        session_steps
        want "the try is a recorded step of the session (commands.jsonl)" "recorder-cleanup-$RID-try1" "$SESS/commands.jsonl"
        want "the try ran under timeout 120 (commands.jsonl)" '"timeout", "120", "bash"' "$SESS/commands.jsonl"
        want "the unit-state confirmation is recorded" "recorder-unit-state-$RID" "$SESS/commands.jsonl"
        want "the listing confirmation is recorded" "recorder-partial-capture-$RID" "$SESS/commands.jsonl"
        nothing_signalled
        cleanup_run
        want_rc 0 "the new script again (idempotent)"
        want "no new try: KEEP_DIR already holds the capture" '^KEEP_DIR already holds the partial capture' "$B/cleanup.out"
        want_no "no try ran the second time" '^## .* try [0-9]' "$B/cleanup.out"
        close_and_package
        ;;
    supp-retry)
        setup
        echo "EXPECTED: try 1 copies 3 of the 4 files (the scp of cli.stderr fails), ends 1, its INCOMPLETE staging folder is kept; try 2 keeps the four files; close; the package holds KEEP_DIR and the incomplete folder."
        term_path
        touch "$B/supp.scp.fail.cli.stderr"
        cleanup_run
        want_rc 0 "the new script"
        want "try 1 ended 1" '^try 1: exit 1$' "$B/cleanup.out"
        want "try 1's STOP names the incomplete copy" "^STOP: events_capture: 3 of the recorder's 4 files copied, kept INCOMPLETE in $KEEP\.copy\." "$B/cleanup.out"
        want "the script names the kept incomplete folder" "^kept INCOMPLETE \(not the run's capture, not KEEP_DIR\): $KEEP\.copy\." "$B/cleanup.out"
        want "try 2 ended 0" '^try 2: exit 0$' "$B/cleanup.out"
        want "OK after try 2" "\(try 2\): 'close' may run$" "$B/cleanup.out"
        INC=$(ls -d "$KEEP".copy.* 2> /dev/null | head -n 1)
        is "the incomplete staging folder holds 3 files" "$(ls "$INC" 2> /dev/null | wc -l)" 3
        keep_complete
        nothing_signalled
        close_and_package
        is "the package also holds the incomplete folder" "$(ls -d "$PKG"/recovery/events-partial-$RID.copy.* 2> /dev/null | wc -l)" 1
        ;;
    supp-hang)
        setup
        echo "EXPECTED: try 1's scp of events.jsonl hangs; timeout 120 ends the try (exit 124) at about 120 s; try 2 keeps the four files; close."
        term_path
        touch "$B/supp.scp.hang.events.jsonl"
        cleanup_run
        want_rc 0 "the new script"
        want "try 1 ended 124 (the bound)" '^try 1: exit 124 \(the 120 s bound: timeout.s TERM\)$' "$B/cleanup.out"
        HP=$(cat "$B/supp.scp.hang.pid" 2> /dev/null)
        is "the hung scp was ended by the try's timeout" "$([ -n "$HP" ] && [ -d "/proc/$HP" ] && echo alive || echo gone)" gone
        D1=$(awk '/^## .* try 1 of/ { split($2, a, "T"); print a[2] }' "$B/cleanup.out" | head -n 1)
        D2=$(awk '/^## .* try 2 of/ { split($2, a, "T"); print a[2] }' "$B/cleanup.out" | head -n 1)
        note "try 1 began at $D1 and try 2 at $D2 (UTC, from the script's own lines)"
        S1=$(awk -v a="$D1" -v b="$D2" 'BEGIN { split(a, x, ":"); split(b, y, ":"); print (y[1]*3600+y[2]*60+y[3]) - (x[1]*3600+x[2]*60+x[3]) }')
        is "try 1 lasted about the 120 s bound (between 118 and 140 s, wall clock)" "$([ "$S1" -ge 118 ] && [ "$S1" -le 140 ] && echo yes || echo "no ($S1 s)")" yes
        want "try 2 ended 0" '^try 2: exit 0$' "$B/cleanup.out"
        keep_complete
        nothing_signalled
        close_and_package
        ;;
    supp-halt)
        setup
        echo "EXPECTED: the unit is never shown stopped: three tries end 1, nothing is copied, HALT ('do NOT run close'); the script runs no close and signals nothing; the session stays open."
        term_path
        touch "$B/supp.unit-stuck"
        cleanup_run
        want_rc 1 "the new script (HALT)"
        is "three tries ran" "$(grep -c '^try [0-9]: exit 1$' "$B/cleanup.out")" 3
        want "each try's STOP: not shown stopped, nothing copied" "^STOP: events_capture: the unit egw-events-$RID was not shown stopped \(exit 1\) - it may still run on the guest; nothing was copied to $KEEP" "$B/cleanup.out"
        want "the HALT tells the operator not to close" "^HALT: 3 tries did not show the recorder stopped with its partial capture kept - do NOT run 'close'; nothing was signalled or powered off; hand back to Rui" "$B/cleanup.out"
        is "KEEP_DIR was not created" "$(exists "$KEEP")" absent
        is "the unit on the stub guest" "$(cat "$EGW_STUB_STATE/unit-$RID")" active
        nothing_signalled
        is "the session is still open (current_session)" "$(exists "$EGW_EXEC/current_session")" exists
        is "the session's state" "$(skey state)" open
        ;;
    *)
        echo "unknown scenario '$SC'"
        exit 2
        ;;
esac
finish
[ "$FAILS" -eq 0 ]
exit
} 2>&1
