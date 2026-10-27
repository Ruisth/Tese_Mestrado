#!/bin/bash
# Bench of the second opening of S3: one scenario of the authorised T8/T9 exception at
# 'open', run on g3_battery.sh of this preparation (the copy of the sealed S3 script with
# the three changes marked 'S3, second opening'), in a bench of its own made by
# bs3b_setup.sh (/tmp/g3-s3b-bench/<scenario>). Adapted 2026-10-05 from the earlier
# preparation's bench/bs3_run.sh (its helpers and its s1, unchanged in substance).
# HOME and every EGW_* inside the bench, stubs first on PATH, no guest, no QEMU, no docker,
# no real ssh. The console (stdout) starts with the sha256 of the script run, states what is
# expected, quotes the decisive lines and ends with the scenario's result.
# The script is run IN PLACE (<S>/g3/s3bprep/g3_battery.sh, so the checker beside it is the
# prepared s3b_preflight_exception.py), except in e6, which runs a byte-identical copy in the
# bench beside a changed copy of the checker. Every scenario runs the final bytes (no
# short-timing variant: only e1 runs the reboot wait, whose stub guest answers at the third
# poll). The state directory is the script's own default, <bench>/egw-exec/g3-t8t9-s3-attempt02.
# Usage (WSL): bs3b_run.sh <scenario>
#   e1     normal pass: the stub preflight ends 0 (the earlier bench's): open, no exception
#          examined; row t8, classify, row t9, classify, close, as the earlier bench's s1
#          (real time; BENCH_E1_FAST=1 for a quicker development run only)
#   e2     the sole permitted duration failure: the real failed preflight, unchanged: the
#          checker applies the exception, open goes on (environment copy, gate, listing)
#          and ends 'session is open'; the preflight attempt is not modified; close
#   e3     the same with step 7 (stack-health) exit_code 1: HALT, no environment copy, no gate
#   e4a    attempt.json removed: HALT
#   e4b    the console's DRIVER RESULT line names another run id (no such attempt): HALT
#          (the exception is not examined: the script's own halt for a failed preflight)
#   e4b2   the same, with a directory of that other name holding this attempt: HALT
#   e4c    collector-check.json lists a problem: HALT
#   e5a    attempt.json capture_failures non-empty: HALT
#   e5b    one step's stdout capture state 'truncated': HALT
#   e6     the checker's bytes changed (one comment appended to the bench's copy): HALT
#          'is not the prepared one', the checker not run
#   e7a    an observed system fault: attempt.json system_outcome 'fail', its reason starting
#          'observed system fault(s): ', and the driver's line saying so: HALT
#   e7b    the same in attempt.json only (the console unchanged): HALT
# After every halt at open, 'close' is run as the operator would, the stub guest answering.
set -u
SC=${1:?usage: bs3b_run.sh <scenario>}
HERE=$(cd "$(dirname "$0")" && pwd)
SCR=$(cd "$HERE/../../.." && pwd)
PREP=$SCR/g3/s3bprep
ROOT=/tmp/g3-s3b-bench
B=$ROOT/$SC
FINAL=$PREP/g3_battery.sh
CHECKER=$PREP/s3b_preflight_exception.py
REAL_PY=/home/ruisth/egw-exec/venv/bin/python
BASE_PATH=$PATH
CHECKS=0
FAILS=0
RC=0
SMOKE=itest-post-reboot-01-q2
POST_ID=bbbbbbbb-0000-4000-8000-00000000000b
PRE_ID=aaaaaaaa-0000-4000-8000-00000000000a
ROOTFS_NEW=b48b010d571689ae03d610175fd1b127f6ef6b30f78b25448e6f32a3096de093
RID=20261005T105656Z_live-preflight_attempt11
OTHER=20261005T105656Z_live-preflight_attempt12
REAL_CONSOLE_SHA=bd7bdb373948869d61ea35a48e2292b3ffcb2a93dd848da2936b8fdb1994390c
EXC_SHA=$(sed -n 's/^EXCEPTION_SHA=//p' "$FINAL")

sha() { if [ -f "$1" ]; then /usr/bin/sha256sum "$1" | cut -d' ' -f1; else echo absent; fi; }
# mask: the bench and the scratchpad are shown by name, never by path; a path of the
# scratchpad's own tree that a listing cut short is shown as cut.
TMPROOT=$(dirname "$(dirname "$(dirname "$(dirname "$SCR")")")")
mask() { sed "s#$B#<bench>#g; s#$SCR#<S>#g; s#$TMPROOT/[^ ;|]*#<S, cut>#g"; }
say() { echo; echo "=== $*"; }
note() { echo "--- $*" | mask; }
ok() { CHECKS=$((CHECKS + 1)); echo "CHECK ok: $*" | mask; }
bad() { CHECKS=$((CHECKS + 1)); FAILS=$((FAILS + 1)); echo "CHECK FAILED: $*" | mask; }
keep() {
    grep -E '^(## [0-9]{4}-|## environment input|HALT|REFUSED|NOT STARTED|GATE|row t|NOTE|Next|STOP|poll |QEMU|REBOOT|CONTAINERS|PERSISTENCE|CONTROLLER PROCESS|TEST STATUS|TUNNEL|MASTER|keepalive|KEEPALIVE|not a keepalive|carrier set|gate record|admitted|NOT FRESH|session S3|  HALT|  row |    HALT|    attempt|    RUNNING|TERM sent|exit=|probe exit|root ssh exit|ss exit|docker ps exit|controller untouched|reboot command sent|drained:|observations read|  "lost"|  "late_confirmations"|still in the row|waiting for the row|no attempt existed|  .*\.txt:[0-9]+:STOP:|ok: |EXCEPTION|PROCEEDED|rootfs ext4:|expected: |EGW_EXEC_REPO=|labels:|harness input now|source: |previous input|fresh on the guest|The session state|DRIVER RESULT|[a-z_]+\.sh exit=)' \
        | mask | cut -c1-430
}
# run SUBCOMMAND...: one subcommand in a session of its own, as the launcher starts it.
run() {
    say "g3_battery.sh $*"
    setsid bash "$G" "$@" < /dev/null > "$B/last.out" 2>&1
    RC=$?
    echo "-> exit $RC"
    keep < "$B/last.out"
}
want_rc() { if [ "$RC" = "$1" ]; then ok "exit status $RC: $2"; else bad "exit status $RC, expected $1: $2"; fi; }
want() { if grep -Eq -- "$2" "${3:-$B/last.out}"; then ok "$1"; else bad "$1 - no line matches: $2"; fi; }
want_no() { if grep -Eq -- "$2" "${3:-$B/last.out}"; then bad "$1 - a line matches: $2"; else ok "$1"; fi; }
is() { if [ "$2" = "$3" ]; then ok "$1: $2"; else bad "$1: '$2', expected '$3'"; fi; }
st() { printf '%s\n' "${2:-}" > "$EGW_STUB_STATE/$1"; }      # one state file of the module's stub guest
exists() { if [ -e "$1" ]; then echo exists; else echo absent; fi; }
attempt_of() { sed -n 's/^attempt=//p' "$BSTATE/row-$1.env" 2> /dev/null | tail -n 1; }
steps_of() {
    ls "$1/console" 2> /dev/null | sed -n 's/^[0-9]*-\(.*\)\.stdout\.txt$/\1/p' | uniq -c \
        | awk '{ if ($1 > 1) printf "%s x%s ", $2, $1; else printf "%s ", $2 }' | sed 's/ $//'
}
want_steps() {     # want_steps ROW REGEX: the recorded steps of the row's attempt, in order
    local a got
    a=$(attempt_of "$1")
    got=$(steps_of "$a")
    echo "recorded steps of row $1, in order: ${got:-<none>}"
    if [[ $got =~ $2 ]]; then ok "the steps of row $1 are the expected ones"; else bad "the steps of row $1 are not: $2"; fi
}
console() { ls "$(attempt_of "$1")"/console/*-"$2".stdout.txt 2> /dev/null | tail -n 1; }
row_key() { sed -n "s/^$2=//p" "$BSTATE/row-$1.env" 2> /dev/null | tail -n 1; }
skey() { sed -n "s/^$1=//p" "$BSTATE/session-S3.env" 2> /dev/null | tail -n 1; }   # one key of the session's state file
skeys() { grep -c "^$1=" "$BSTATE/session-S3.env" 2> /dev/null; }                  # how many lines of that key
halts() { skeys halt; }
qemu_state() {
    local pid
    pid=$(cat "$B/qemu.pid" 2> /dev/null)
    if [ -n "$pid" ] && [ -d "/proc/$pid" ]; then echo "pid $pid alive, start tick $(cut -d' ' -f22 "/proc/$pid/stat")"; else echo "pid ${pid:-none} not running"; fi
}
reboots() { grep -c 'sudo systemctl reboot' "$EGW_STUB_STATE/ssh.log" 2> /dev/null; }
sent_to_guest() {
    local n
    n=$(grep -c -E '(docker( compose)?|\$DC|systemctl)\b[^"'"'"';]*\b(up|start|restart)\b' "$EGW_STUB_STATE/ssh.log" 2> /dev/null)
    is "commands that start, restart or bring up anything, sent to the stub guest (the test module's own pattern)" "${n:-0}" 0
    n=$(grep -c 'PATTERN-KILL' "$EGW_STUB_STATE/calls.log" 2> /dev/null)
    is "pkill or killall calls" "${n:-0}" 0
}
polls() {          # polls ROW: the wait's polls, read from the attempt's commands.jsonl
    "$REAL_PY" - "$(attempt_of "$1")" << 'EOF'
import json, sys
rows = [json.loads(line) for line in open(sys.argv[1] + "/commands.jsonl", encoding="utf-8") if line.strip()]
polls = [r for r in rows if r["name"] == "t8-wait-ssh"]
for i, r in enumerate(polls, 1):
    print("  poll %d (step %03d): command starts '%s', exit status %s, %.1f s" % (i, r["seq"], " ".join(r["argv"][:2]), r["exit_code"], r["duration_s"]))
bounds = [int(r["argv"][1]) for r in polls if r["argv"][0] == "timeout" and r["argv"][1].isdigit()]
print("polls: %d; run by the host's timeout: %d; bounds used (s): %s" % (len(polls), len(bounds), " ".join(str(b) for b in sorted(set(bounds), reverse=True))))
EOF
}
# tree_hash DIR: every file's sha256, every entry's path, mtime, size and mode (as bs3b_fixture.sh)
tree_hash() {
    [ -d "$1" ] || { echo absent; return; }
    (cd "$1" && { find . -type f -print0 | LC_ALL=C sort -z | xargs -0 /usr/bin/sha256sum; find . -printf '%P %T@ %s %m\n' | LC_ALL=C sort; }) | /usr/bin/sha256sum | cut -d' ' -f1
}
hashes_of() { echo "attempt.json $(sha "$1/attempt.json") commands.jsonl $(sha "$1/commands.jsonl") tree $(tree_hash "$1")"; }

# setup MODE FAST: the bench, the script under test (MODE inplace: the final bytes where they
# are; copy: a byte-identical copy in <bench>/script/ beside a copy of the checker), the environment
setup() {
    local mode=$1
    export BENCH_FAST_DRAIN=$2 BENCH_SCALED=0
    if [ -e "$B" ]; then
        for p in $(cat "$B/qemu.pids.all" 2> /dev/null); do kill -- "-$p" 2> /dev/null; done
        rm -rf "$B"
    fi
    mkdir -p "$ROOT" || exit 1
    case $mode in
        inplace)
            G=$FINAL
            echo "script run: sha256 $(sha "$G") (<S>/g3/s3bprep/g3_battery.sh, run in place; the checker beside it: s3b_preflight_exception.py sha256 $(sha "$CHECKER"), the script's EXCEPTION_SHA $EXC_SHA)" ;;
        copy)
            G=$B/script/g3_battery.sh
            echo "script run: sha256 $(sha "$FINAL") (<bench>/script/g3_battery.sh, a byte-identical copy of <S>/g3/s3bprep/g3_battery.sh, beside a copy of s3b_preflight_exception.py with one comment line appended; the script's EXCEPTION_SHA $EXC_SHA)" ;;
    esac
    echo "## $(date -u +%Y-%m-%dT%H:%M:%SZ) scenario $SC; host uptime $(cut -d' ' -f1 /proc/uptime) s; row files: the real <S>/g3/s3bprep/rows (manifest sha256 $(sha "$PREP/rows/rows.manifest.json"))"
    echo "bench scripts (sha256, first 16 characters): bs3b_run.sh $(sha "$HERE/bs3b_run.sh" | cut -c1-16), bs3b_setup.sh $(sha "$HERE/bs3b_setup.sh" | cut -c1-16), bs3b_env.sh $(sha "$HERE/bs3b_env.sh" | cut -c1-16), bs3b_stubs.py $(sha "$HERE/bs3b_stubs.py" | cut -c1-16), bs3b_fixture.sh $(sha "$HERE/bs3b_fixture.sh" | cut -c1-16), bs3b_mutate.py $(sha "$HERE/bs3b_mutate.py" | cut -c1-16)"
    echo "bench switches: BENCH_FAST_DRAIN=$2 (1: 'drained' returns after two readings; 0: its real 130 s quiet window), BENCH_SCALED=0 (the host's sleep and timeout)"
    echo "bench keepalive: the steps script's keepalive_check is answered by the bench's ps stub, which adds a SYNTHETIC client (pid 4194301 'sleep 43200', parent 4194300 'Relay(bench)'; no process) to the listing that check reads; the bench starts and ends no client; processes 'sleep N' with N of 3600 or more now on the host: $(/usr/bin/ps -eo args= 2> /dev/null | awk '$1 == "sleep" && NF == 2 && $2 >= 3600' | wc -l)"
    bash "$HERE/bs3b_setup.sh" "$B" > "$ROOT/$SC.setup.log" 2>&1 || { echo "setup failed:"; tail -n 5 "$ROOT/$SC.setup.log" | mask; exit 1; }
    grep -E '^(drivers of the copy|test module imported|tunnel.sh:|itest-helpers.sh:)' "$ROOT/$SC.setup.log" | mask
    if [ "$mode" = copy ]; then
        mkdir "$B/script" || exit 1
        cp -p "$FINAL" "$B/script/g3_battery.sh" && cp -p "$CHECKER" "$B/script/s3b_preflight_exception.py" || exit 1
        printf '%s\n' '# bench: a comment appended (scenario e6): the bytes differ, the logic does not' >> "$B/script/s3b_preflight_exception.py"
        is "the bench's copy of the script is byte-identical to the final bytes" "$(sha "$G")" "$(sha "$FINAL")"
        note "the bench's copy of the checker: sha256 $(sha "$B/script/s3b_preflight_exception.py") (the prepared one: $(sha "$CHECKER")); its last line: $(tail -n 1 "$B/script/s3b_preflight_exception.py")"
    fi
    # shellcheck source=/dev/null
    . "$HERE/bs3b_env.sh"
    SUT0=$(sha "$HOME/egw-tcg/sut_environment.json")
}
finish() {         # the end of every scenario: the bench's own fake processes are ended
    local p left
    say "the end of the bench"
    for p in $(cat "$B/qemu.pids.all" 2> /dev/null); do
        if [ -d "/proc/$p" ]; then kill -- "-$p" 2> /dev/null; echo "the fake process $p that stood for QEMU was still running: ended now by the bench itself"; fi
    done
    /usr/bin/sleep 1
    left=$(/usr/bin/pgrep -f "$B/" | wc -l)
    [ "$left" -eq 0 ] || { /usr/bin/sleep 22; left=$(/usr/bin/pgrep -f "$B/" | wc -l); }
    is "processes of this bench left" "$left" 0
    [ "$left" -eq 0 ] || /usr/bin/pgrep -af "$B/" | cut -c1-200 | mask
    is "the prepared checker after the scenario" "$(sha "$CHECKER")" "$EXC_SHA"
    echo
    if [ "$FAILS" -eq 0 ]; then
        echo "## $(date -u +%Y-%m-%dT%H:%M:%SZ) SCENARIO $SC: PASS ($CHECKS checks)"
    else
        echo "## $(date -u +%Y-%m-%dT%H:%M:%SZ) SCENARIO $SC: FAIL ($FAILS of $CHECKS checks failed)"
    fi
}

# --- the fixture -----------------------------------------------------------------------------
# fixture VARIANT: <bench>/fixture (bs3b_fixture.sh), which the stub preflight places and prints
fixture() {
    bash "$HERE/bs3b_fixture.sh" "$1" "$B/fixture" > "$B/fixture.log" 2>&1 || { echo "fixture failed:"; mask < "$B/fixture.log"; exit 1; }
    mask < "$B/fixture.log" | cut -c1-430
    FIX_CONSOLE_SHA=$({ cat "$B/fixture/preflight.console.txt"; echo "preflight.sh exit=3"; } | /usr/bin/sha256sum | cut -d' ' -f1)
    note "the driver console the script will keep (the fixture's console plus the line 'preflight.sh exit=3' its run_driver appends): sha256 $FIX_CONSOLE_SHA ($([ "$FIX_CONSOLE_SHA" = "$REAL_CONSOLE_SHA" ] && echo "the real console's" || echo "NOT the real console's $REAL_CONSOLE_SHA: the variant changed it"))"
}
# attempts_unchanged WHEN: every attempt the stub placed is, in the attempts directory, what
# the fixture holds (attempt.json, commands.jsonl, the whole tree with modification times)
attempts_unchanged() {
    local f n
    for f in "$B"/fixture/attempts/*/; do
        f=${f%/}
        n=${f##*/}
        is "$1: the preflight attempt $n in the attempts directory, against the fixture it was copied from" "$(hashes_of "$EGW_ATTEMPTS/$n")" "$(hashes_of "$f")"
    done
}

# --- the common passages ---------------------------------------------------------------------
open_common() {    # what every 'open' of the second opening shows before the drivers
    want "the expected root file system is the second opening's (b48b010d...)" "^expected:    $ROOTFS_NEW \(the value the close of S3's first opening recorded\)$"
    want "the root file system read (the stub) is that value" "^rootfs ext4: $ROOTFS_NEW "
    want "the state directory is the script's new default (EGW_G3_STATE unset)" " STATE=$BSTATE ROWS="
    is "the session's state file in the default state directory g3-t8t9-s3-attempt02" "$(exists "$BSTATE/session-S3.env")" exists
    is "steps_script_sha256 recorded by open" "$(skey steps_script_sha256)" "$(sha "$G")"
    want "the keepalive check of open found the bench's synthetic client (the ps stub; no process)" "^keepalive: pid 4194301 'sleep 43200', parent 4194300 \(Relay\(bench\)\), running for [0-9]+ s, about [0-9]+ s left"
}
EXAMINED='^## .* preflight\.sh exited 3: the authorised T8/T9 exception for collector-duration is examined \(read-only\)$'
# open_halted HALT-REGEX CHECKER-LAST-REGEX|none|not-run-after-examined
open_halted() {
    local pre_id
    run open S3
    want_rc 1 "open S3 (a halt)"
    open_common
    want "the halt of open" "$1"
    pre_id=$(sed -n 's/^DRIVER RESULT \([^: ]*\):.*/\1/p' "$B/fixture/preflight.console.txt" | tail -n 1)
    case $2 in
        none)
            want_no "the exception is NOT examined (the console names no attempt that exists)" "$EXAMINED"
            is "the checker's record in the state directory" "$(exists "$BSTATE/S3-preflight-exception.txt")" absent
            want_no "no line of the checker" '^(ok: |EXCEPTION )' ;;
        not-run-after-examined)
            want "the exception's examination starts" "$EXAMINED"
            is "the checker's record in the state directory (the checker was NOT run)" "$(exists "$BSTATE/S3-preflight-exception.txt")" absent
            want_no "no line of the checker" '^(ok: |EXCEPTION )' ;;
        *)
            want "the exception is examined" "$EXAMINED"
            want "the checker's last line" "$2"
            want "the checker's record in the state directory ends with that line" "$2" <(tail -n 1 "$BSTATE/S3-preflight-exception.txt" 2> /dev/null)
            want_no "the checker does not apply the exception" '^EXCEPTION APPLIES' ;;
    esac
    want_no "no line 'PROCEEDED UNDER THE AUTHORISED T8/T9 EXCEPTION'" '^PROCEEDED UNDER'
    is "preflight_exception lines in the session's state file" "$(skeys preflight_exception)" 0
    is "preflight_exit recorded" "$(skey preflight_exit)" 3
    is "preflight_attempt recorded (the attempt the DRIVER RESULT line names)" "$(skey preflight_attempt)" "$EGW_ATTEMPTS/$pre_id"
    is "the session's state" "$(skey state)" halted
    is "halts recorded for the session" "$(halts)" 1
    want "the operator's next step" "^The session state is 'halted' and nothing was closed\. If '.*current_session' exists the guest is UP: decide, then run 'close'\.$"
    # no environment copy
    want_no "no environment copy (its heading)" '^## environment input'
    is "the environment copy's record in the state directory" "$(exists "$BSTATE/S3-environment-copy.txt")" absent
    is "the harness input sut_environment.json (sha256 unchanged since the setup)" "$(sha "$HOME/egw-tcg/sut_environment.json")" "$SUT0"
    is "kept copies of the harness input" "$(ls "$HOME"/egw-tcg/sut_environment.json.* 2> /dev/null | wc -l)" 0
    is "sut_environment keys in the session's state file" "$(grep -c '^sut_environment' "$BSTATE/session-S3.env")" 0
    # no gate, no listing
    want_no "the gate driver is NOT run" 'gate_health\.sh \(frozen driver'
    is "the gate driver's console" "$(ls "$BSTATE"/S3-gate_health.console*.txt 2> /dev/null | wc -l)" 0
    is "gate attempts created" "$(ls -d "$EGW_ATTEMPTS"/*_g2-gate-preconditions_attempt* 2> /dev/null | wc -l)" 0
    is "gate_health_exit in the session's state file" "$(skeys gate_health_exit)" 0
    want_no "the guest listing is NOT run" 'run ids of S3 unused on the guest'
    # what the stub placed, and the console the script kept
    is "attempts of 'live preflight' in the attempts directory (the fixture's only; the stub created none)" "$(ls -d "$EGW_ATTEMPTS"/*_live-preflight_attempt* 2> /dev/null | wc -l)" "$(ls -d "$B"/fixture/attempts/*/ | wc -l)"
    is "the driver console kept by the script" "$(sha "$BSTATE/S3-preflight.console.txt")" "$FIX_CONSOLE_SHA"
    attempts_unchanged "after open"
    is "an open session (current_session)" "$(exists "$EGW_EXEC/current_session")" exists
    Q0=$(qemu_state)
    note "the fake process that stands for QEMU after the halted open: $Q0"
}
close_after_halt() {
    run close
    want_rc 0 "close (the stub guest answers)"
    want "the session is closed" '^## .* session S3 closed \(guest_session_close\.sh exit 0\)'
    want "the recorded stop with the 130 s allowance was run" '^## .* the recorded stop with the controller'"'"'s 130 s allowance'
    is "the session's state after close" "$(skey state)" closed
    is "halts recorded for the session after close (no new one)" "$(halts)" 1
    is "an open session (current_session) after close" "$(exists "$EGW_EXEC/current_session")" absent
    is "the fake QEMU after close" "$(qemu_state | sed 's/^pid [0-9a-z]* //')" "not running"
    is "preflight_exception lines after close" "$(skeys preflight_exception)" 0
    attempts_unchanged "after close"
}
close_ok() {
    run close
    want_rc "${1:-0}" "close"
    want "the session is closed" '^## .* session S3 closed'
}
status_now() {
    say "g3_battery.sh status"
    setsid bash "$G" status < /dev/null 2>&1 | grep -E '^(state directory|open session|qemu pgrep|session S3|  |    )' | mask | cut -c1-300
}
line_of() { grep -n -E -m 1 -- "$1" "$B/last.out" | cut -d: -f1; }

T8_ALL='^guest-state-before t8-qemu-before t8-a-reboot t8-wait-ssh( x[0-9]+)? t8-qemu-after t8-b-wait-boot-id t8-c-unaided t8-d-tunnel t8-tunnel-check t8-e-state t8-f-smoke t8-previous-boot-journal t8-previous-boot-oom guest-state-after gate-healthy gate-units gate-tunnel-check$'
t8_markers() {     # every marker of a complete test 8, each at the start of a line of its step's console
    want "step b: REBOOT SHOWN" "^REBOOT SHOWN: boot id $PRE_ID -> $POST_ID" "$(console t8 t8-b-wait-boot-id)"
    want "step c: CONTAINERS RETURNED UNAIDED" '^CONTAINERS RETURNED UNAIDED: the 6 container ids' "$(console t8 t8-c-unaided)"
    want "step c: PERSISTENCE SHOWN" '^PERSISTENCE SHOWN: 3 event directories intact; /var/lib/docker on /dev/vdb' "$(console t8 t8-c-unaided)"
    want "step e: CONTROLLER PROCESS NEW" '^CONTROLLER PROCESS NEW: started_at ' "$(console t8 t8-e-state)"
    want "step f: the smoke's status line of a completed procedure" "^TEST STATUS $SMOKE: simulator exit=0 transcript \(tee\) exit=0 post=0 -> PROCEDURE COMPLETE\." "$(console t8 t8-f-smoke)"
    want "the QEMU process after the wait is the one recorded before step a" '^QEMU PROCESS UNCHANGED: the same process as before step a' "$(console t8 t8-qemu-after)"
}
t8_ok() {          # a complete row t8 with no halt
    run row t8
    want_rc 0 "row t8"
    want_no "no halt was recorded by row t8" '^HALT'
    want_steps t8 "$T8_ALL"
    t8_markers
    want "the gate of row t8 passed" '^## .* GATE t8: pass'
    is "the name of the new attempt ends _g3-qualification-t8_attempt02" "$(row_key t8 attempt_name | sed 's/^[0-9TZ]*//')" "_g3-qualification-t8_attempt02"
    is "reboot commands sent to the stub guest" "$(reboots)" 1
    is "the fake QEMU process after the row" "$(qemu_state)" "$Q0"
}
T9_ALL='^guest-state-before t9-a t9-b t9-c t9-de t9-exposure guest-state-after guest-state-delta gate-healthy gate-units gate-tunnel-check$'
t9_refuses() {     # from here on the stub simulator refuses, as the broker refuses test 9's three probes
    rm -f "$EGW_STUB_STATE/sent_events.jsonl" "$EGW_STUB_STATE/sim_manifest.json"
    st sim_rc 1
    note "bench: from here on the stub simulator leaves no directory and exits 1 (a refused connection)"
}
t9_ok() {          # a complete row t9: (a), (b), (c), (d)+(e) and the exposure step
    t9_refuses
    run row t9
    want_rc 0 "row t9"
    want_no "no halt was recorded by row t9" '^HALT'
    want_steps t9 "$T9_ALL"
    want "(a) the probe's exit status is printed" '^exit=1$' "$(console t9 t9-a)"
    want "(b) the bounded broker log was read" 'not authorised' "$(console t9 t9-b)"
    want "(c) the probe's exit status is printed" '^exit=1$' "$(console t9 t9-c)"
    want "(d)+(e) the probe ran to its end" '^probe exit=0 ' "$(console t9 t9-de)"
    want "(d)+(e) the controller is untouched by the probe" '^controller untouched by the probe' "$(console t9 t9-de)"
    want "exposure: root over ssh refused" '^root ssh exit=255$' "$(console t9 t9-exposure)"
    want "exposure: the host's sockets listed" '^ss exit=0$' "$(console t9 t9-exposure)"
    want "exposure: the guest's published ports listed" '^docker ps exit=0$' "$(console t9 t9-exposure)"
    want "the gate of row t9 passed" '^## .* GATE t9: pass'
    is "the name of the new attempt ends _g3-qualification-t9_attempt01" "$(row_key t9 attempt_name | sed 's/^[0-9TZ]*//')" "_g3-qualification-t9_attempt01"
    want_no "no private-key header in the attempt of row t9" 'BEGIN [A-Z ]*PRIVATE KEY' <(grep -rh 'PRIVATE KEY' "$(attempt_of t9)" 2> /dev/null)
    note "the stub openssl was called $(wc -l < "$B/openssl.log" 2> /dev/null) time(s) and wrote nothing; /tmp/wrong.key and /tmp/wrong.crt: $(ls /tmp/wrong.key /tmp/wrong.crt 2> /dev/null | tr '\n' ' ')$(ls /tmp/wrong.key /tmp/wrong.crt > /dev/null 2>&1 || echo 'neither exists')"
}
classify_ok() {    # classify_ok ROW STATUS VALIDITY OUTCOME
    run classify "$1" "$2" "$3" "$4" "bench: scenario $SC" "bench: none"
}

# --- the scenarios ---------------------------------------------------------------------------
# Everything from here to the end is ONE group, which bash reads whole before running it.
{
case $SC in
    e1)
        setup inplace "${BENCH_E1_FAST:-0}"
        echo "EXPECTED: the stub preflight ends 0 (the earlier bench's stub; no fixture): open S3 passes and examines no exception (no 'examined' line, no checker line, no 'PROCEEDED UNDER' line, no preflight_exception key, no checker record); row t8 runs a to f with every marker and no halt; classify; row t9 runs its four fenced steps and the exposure step; classify; close. $([ "${BENCH_E1_FAST:-0}" = 1 ] && echo 'DEVELOPMENT RUN: the bench device BENCH_FAST_DRAIN=1.' || echo "Real time: the helper's 130 s quiet windows, the host's sleep and timeout.")"
        run open S3
        want_rc 0 "open S3"
        want "the session is open" '^## .* session S3 is open'
        open_common
        want "the one earlier attempt admitted in the attempts directory" "^admitted: .*: $EGW_ATTEMPTS/20261003T142310Z_g3-qualification-t8_attempt01$"
        want "the one earlier attempt admitted under the output root" "^admitted: .*: $EGW_OUTPUT_TEST/runs/2026-10-03/20261003T142310Z_g3-qualification-t8_attempt01$"
        want "the preflight driver ended 0" '^preflight\.sh exit=0$'
        want_no "the exception is NOT examined" "$EXAMINED"
        want_no "no line of the checker" '^(ok: |EXCEPTION )'
        want_no "no line 'PROCEEDED UNDER THE AUTHORISED T8/T9 EXCEPTION'" '^PROCEEDED UNDER'
        is "preflight_exception lines in the session's state file" "$(skeys preflight_exception)" 0
        is "the checker's record in the state directory" "$(exists "$BSTATE/S3-preflight-exception.txt")" absent
        is "preflight_exit recorded" "$(skey preflight_exit)" 0
        want "the environment copy ran" '^harness input now: '
        want "the gate driver ran" 'gate_health\.sh \(frozen driver'
        is "the session's state after open" "$(skey state)" open
        Q0=$(qemu_state)
        note "the fake process that stands for QEMU after the open: $Q0"
        t8_ok
        sent_to_guest
        if [ "$BENCH_FAST_DRAIN" = 0 ]; then
            want "the carriers are really unset in the step shell" '^carriers after the unset: DEVICES=<unset> ACCEPT_UNACCOUNTED=<unset> EVENTS_EXPECTED=<unset> DRAIN_QUIET_S=<unset> DRAIN_STEP_S=<unset> DRAIN_LIMIT_S=<unset> READY_LIMIT_S=<unset>' "$(console t8 t8-a-reboot)"
        else
            note "development run: the carriers DRAIN_QUIET_S and DRAIN_STEP_S are the bench device's read-only 0: $(grep -m 1 '^carriers after the unset' "$(console t8 t8-a-reboot)")"
        fi
        polls t8
        want "the workload field of the t8 attempt names the second opening" 'session S3 \(second opening\)' <("$REAL_PY" -c 'import json,sys; print(json.load(open(sys.argv[1]))["workload"]["battery"])' "$(attempt_of t8)/attempt.json")
        classify_ok t8 finished valid pass
        want_rc 0 "classify t8"
        want "row t8 is classified pass and exported (the export tool's own verification)" "^row t8: classified 'pass'; driver code 0; export: verified -> $EGW_OUTPUT_TEST/runs/"
        t9_ok
        classify_ok t9 finished valid pass
        want_rc 0 "classify t9"
        close_ok
        is "halts recorded for the session" "$(halts)" 0
        is "preflight_exception lines after close" "$(skeys preflight_exception)" 0
        status_now
        note "packages under the bench's output root: $(ls "$B/out/runs"/*/ 2> /dev/null | grep -v '^$' | grep -v ':$' | tr '\n' ' ')"
        ;;
    e2)
        setup inplace 1
        fixture unchanged
        echo "EXPECTED: the stub preflight places the real failed preflight $RID (unchanged) and prints its console, exit 3: the checker's six 'ok:' lines and 'EXCEPTION APPLIES', then 'PROCEEDED UNDER THE AUTHORISED T8/T9 EXCEPTION', the key preflight_exception recorded, then the environment copy, the gate and the guest listing, and open ends 'session S3 is open'; the preflight attempt is not modified; close."
        run open S3
        want_rc 0 "open S3"
        open_common
        want "the exception is examined" "$EXAMINED"
        want "checker: the driver's result line" "^ok: driver result: $RID exit=3 failed, invalid, inconclusive, exported$"
        want "checker: the attempt directory is the driver's" "^ok: attempt directory is the driver's: $RID$"
        want "checker: attempt.json" '^ok: attempt\.json: failed, invalid, inconclusive; no capture failure; the only failed mandatory step is collector-duration; nothing observed, nothing skipped$'
        want "checker: the sixteen steps" '^ok: sixteen steps in the frozen order, each capture complete; fifteen ended 0, collector-duration ended 1$'
        want "checker: collector-check" '^ok: collector-check: no problem, no unexpected name, six services \(43-43 rows each\)$'
        want "checker: the numeric judgement alone" '^ok: collector-duration failed on the numeric judgement alone: window 43 s of the declared 45 s, shortfall 2 s'
        want "checker: its last line" "^EXCEPTION APPLIES: preflight $RID stays failed and invalid; the session proceeds under the authorised T8/T9 exception \(collector-duration only: UTC window 43 s of 45 s declared\)$"
        is "lines of the checker's record in the state directory (six 'ok:' and the verdict)" "$(wc -l < "$BSTATE/S3-preflight-exception.txt" 2> /dev/null)" 7
        want "the checker's record ends with the verdict" '^EXCEPTION APPLIES: ' <(tail -n 1 "$BSTATE/S3-preflight-exception.txt")
        want "the script's line" "^PROCEEDED UNDER THE AUTHORISED T8/T9 EXCEPTION: preflight $RID stays failed and invalid \(collector-duration only\); the environment copy, the gate and every identity check below stay mandatory$"
        is "preflight_exception in the session's state file" "$(skey preflight_exception)" "proceeded under the authorised T8/T9 exception (collector-duration only; preflight $RID stays failed and invalid)"
        is "preflight_exception lines" "$(skeys preflight_exception)" 1
        want_no "no line says the preflight passed" '[Pp]reflight (passed|PASS)'
        is "preflight_exit recorded (the preflight stays failed)" "$(skey preflight_exit)" 3
        is "preflight_attempt recorded" "$(skey preflight_attempt)" "$EGW_ATTEMPTS/$RID"
        # the environment copy
        want "the environment copy runs" '^## environment input \(PM condition 2 of 2026-10-01\)$'
        want "its labels" '^labels: QEMU/TCG and ARM64 EMULATED are present$'
        want "the previous harness input is kept" '^previous input kept: '
        want "the harness input is now the preflight's capture" "^harness input now: .*/egw-tcg/sut_environment\.json sha256 $(sha "$B/fixture/attempts/$RID/environment/sut_environment.json")$"
        want "its source is the preflight's attempt" "^source: $EGW_ATTEMPTS/$RID/environment/sut_environment\.json \(preflight package $RID\)$"
        is "the harness input in the bench's HOME (sha256)" "$(sha "$HOME/egw-tcg/sut_environment.json")" "$(sha "$B/fixture/attempts/$RID/environment/sut_environment.json")"
        is "sut_environment_source in the session's state file" "$(skey sut_environment_source)" "$EGW_ATTEMPTS/$RID/environment/sut_environment.json"
        # the gate and the listing
        want "the gate driver runs" 'gate_health\.sh \(frozen driver'
        is "gate_health_exit" "$(skey gate_health_exit)" 0
        is "the gate attempt recorded" "$(skey gate_attempt | sed 's#.*/##; s/^[0-9TZ]*//')" "_g2-gate-preconditions_attempt01"
        want "the guest listing runs" 'run ids of S3 unused on the guest \(read-only listing\)'
        want "the ids are fresh on the guest" '^fresh on the guest: '
        want "the session is open" '^## .* session S3 is open'
        want "the next step is row t8" "^Next: 'row t8'"
        is "the session's state" "$(skey state)" open
        is "halts recorded for the session" "$(halts)" 0
        want_no "no halt" '^HALT'
        a=$(line_of "$EXAMINED"); b=$(line_of '^EXCEPTION APPLIES'); c=$(line_of '^PROCEEDED UNDER'); d=$(line_of '^## environment input'); e=$(line_of 'gate_health\.sh \(frozen driver'); f=$(line_of '^## .* session S3 is open')
        note "lines of open's console: examined $a, checker verdict $b, PROCEEDED $c, environment copy $d, gate $e, session open $f"
        is "the order: examined, verdict, PROCEEDED, environment copy, gate, open" "$([ -n "$a$b$c$d$e$f" ] && [ "$a" -lt "$b" ] && [ "$b" -lt "$c" ] && [ "$c" -lt "$d" ] && [ "$d" -lt "$e" ] && [ "$e" -lt "$f" ] && echo in-order || echo NOT)" in-order
        is "the driver console kept by the script is the real one (sha256)" "$(sha "$BSTATE/S3-preflight.console.txt")" "$REAL_CONSOLE_SHA"
        is "attempts of 'live preflight' in the attempts directory (the stub created none)" "$(ls -d "$EGW_ATTEMPTS"/*_live-preflight_attempt* 2> /dev/null | wc -l)" 1
        note "the preflight attempt before (the fixture): $(hashes_of "$B/fixture/attempts/$RID")"
        note "the preflight attempt after open:          $(hashes_of "$EGW_ATTEMPTS/$RID")"
        is "attempt.json of the preflight attempt, against the original package's" "$(sha "$EGW_ATTEMPTS/$RID/attempt.json")" "$(sha "/mnt/c/Users/ruimf/Documents/Projeto Mestrado/output_test/runs/2026-10-05/$RID/attempt.json")"
        is "commands.jsonl of the preflight attempt, against the original package's" "$(sha "$EGW_ATTEMPTS/$RID/commands.jsonl")" "$(sha "/mnt/c/Users/ruimf/Documents/Projeto Mestrado/output_test/runs/2026-10-05/$RID/commands.jsonl")"
        attempts_unchanged "after open"
        Q0=$(qemu_state)
        status_now
        close_ok
        is "the session's state after close" "$(skey state)" closed
        is "halts recorded after close" "$(halts)" 0
        is "preflight_exception kept after close" "$(skeys preflight_exception)" 1
        is "an open session (current_session) after close" "$(exists "$EGW_EXEC/current_session")" absent
        attempts_unchanged "after close"
        note "the preflight attempt after close:         $(hashes_of "$EGW_ATTEMPTS/$RID")"
        ;;
    e3 | e4a | e4b | e4b2 | e4c | e5a | e5b | e7a | e7b)
        setup inplace 1
        HALT_NA='^HALT: preflight\.sh exited 3 and the authorised exception does NOT apply \(checker exit 1; see .*/g3-t8t9-s3-attempt02/S3-preflight-exception\.txt and .*/g3-t8t9-s3-attempt02/S3-preflight\.console\.txt\)$'
        case $SC in
            e3) v=step7-exit1; what="step 7 (stack-health) ended 1 in commands.jsonl"; halt=$HALT_NA; last='^EXCEPTION DOES NOT APPLY: step stack-health ended 1, not 0 - the halt stands$' ;;
            e4a) v=no-attempt-json; what="attempt.json removed"; halt=$HALT_NA; last='^EXCEPTION DOES NOT APPLY: attempt\.json could not be read \(.*No such file or directory.*attempt\.json.*\) - the halt stands$' ;;
            e4b) v=other-run-id; what="the console's DRIVER RESULT line names $OTHER, which no attempt directory bears"; halt='^HALT: preflight\.sh exited 3; see .*/g3-t8t9-s3-attempt02/S3-preflight\.console\.txt$'; last=none ;;
            e4b2) v=other-run-id-dir; what="the console's DRIVER RESULT line names $OTHER, and a directory of that name holds this attempt (its attempt.json run_id is $RID)"; halt=$HALT_NA; last="^EXCEPTION DOES NOT APPLY: attempt\.json run_id='$RID', not '$OTHER' - the halt stands$" ;;
            e4c) v=collector-problem; what="collector-check.json lists a problem"; halt=$HALT_NA; last='^EXCEPTION DOES NOT APPLY: collector-check reports problems: \[.*\] - the halt stands$' ;;
            e5a) v=capture-failures; what="attempt.json records one capture failure"; halt=$HALT_NA; last='^EXCEPTION DOES NOT APPLY: attempt\.json records capture failures: \[.*\] - the halt stands$' ;;
            e5b) v=capture-truncated; what="step 13 (collector-live): stdout capture state 'truncated'"; halt=$HALT_NA; last="^EXCEPTION DOES NOT APPLY: step collector-live: its stdout capture is not complete \(.*'state': 'truncated'.*\) - the halt stands$" ;;
            e7a) v=system-fault; what="an observed system fault: attempt.json system_outcome 'fail', the reason starting 'observed system fault(s): ', and the driver's line saying system_outcome=fail"; halt=$HALT_NA; last="^EXCEPTION DOES NOT APPLY: the driver's result line does not say system_outcome=inconclusive: DRIVER RESULT $RID: .* system_outcome=fail export=exported - the halt stands$" ;;
            e7b) v=system-fault-record; what="attempt.json alone: system_outcome 'fail', the reason starting 'observed system fault(s): ' (the console unchanged)"; halt=$HALT_NA; last="^EXCEPTION DOES NOT APPLY: attempt\.json system_outcome='fail', not 'inconclusive' - the halt stands$" ;;
        esac
        fixture "$v"
        if [ "$SC" = e4b ]; then
            echo "EXPECTED: $what. The script examines the exception only for an attempt the DRIVER RESULT line names and that exists: none does, so the exception is NOT examined and open halts with its own halt for a failed preflight ('preflight.sh exited 3; see ...'); no 'PROCEEDED UNDER' line, no preflight_exception key, no environment copy, no gate; the attempt the stub placed is not modified; then 'close' closes."
        else
            echo "EXPECTED: $what. The checker refuses (exit 1, 'EXCEPTION DOES NOT APPLY: ... - the halt stands'); open halts 'the authorised exception does NOT apply'; no 'PROCEEDED UNDER' line, no preflight_exception key, no environment copy, no gate; the preflight attempt is not modified; then 'close' closes."
        fi
        open_halted "$halt" "$last"
        close_after_halt
        ;;
    e6)
        setup copy 1
        fixture unchanged
        echo "EXPECTED: the real failed preflight, unchanged, but the checker beside the script is not the prepared one (one comment line appended): open halts 'is not the prepared one' BEFORE running the checker (no checker line, no checker record); no 'PROCEEDED UNDER' line, no preflight_exception key, no environment copy, no gate; the preflight attempt is not modified; then 'close' closes."
        open_halted "^HALT: preflight\.sh exited 3, and the exception's checker $B/script/s3b_preflight_exception\.py is not the prepared one \(sha256 $EXC_SHA\): the exception was NOT examined; see .*/g3-t8t9-s3-attempt02/S3-preflight\.console\.txt$" not-run-after-examined
        is "the driver console kept by the script is the real one (sha256)" "$(sha "$BSTATE/S3-preflight.console.txt")" "$REAL_CONSOLE_SHA"
        close_after_halt
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
