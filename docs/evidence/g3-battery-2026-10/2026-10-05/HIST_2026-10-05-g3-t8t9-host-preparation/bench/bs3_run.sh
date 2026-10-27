#!/bin/bash
# Stream BENCH: one scenario of the bench of g3_battery.sh (session S3) on the REAL step
# files of rows/, in a bench of its own made by bs3_setup.sh (/tmp/g3-s3-bench/<scenario>).
# Brief, hard rule 2: HOME and every EGW_* inside the bench, stubs first on PATH, no guest,
# no QEMU, no docker, no real ssh. The console (stdout) starts with the sha256 of the
# script run, states what is expected, quotes the decisive lines and ends with the
# scenario's result; the caller keeps it under record/.
# Usage (WSL): bs3_run.sh <scenario>
#   s1      success on the FINAL bytes, real time, carriers really unset: open S3, row t8
#           (a to f, every marker), classify, row t9 (four steps and the exposure step), close
#   s1b     (added) the same pass, short timing, with the host's tunnel master ending at the
#           reboot: the preamble of step b reopens the tunnel
#   s12     (added) the tunnel cannot be reopened after the reboot: step b answers 97, halt
#   s2i     the wait: a poll that prints a valid different id and ends 124 is not counted,
#           a later genuine success is
#   s2ii    the same with 255
#   s2iii   the wait expires on the FINAL constants (the real 900 s budget, real time)
#   s2iv    with less than 20 s left the poll's timeout is the remainder, never 0
#   s2v     (added) polls that end 0 with the SAVED boot id are not counted: expiry
#   s2vi    (added) polls that end 0 with an answer that is not a boot id are not counted: expiry
#   s2vii   (added) a poll whose status is 74 (console capture lost): a halt of its own
#   s3      -no-reboot on the fake QEMU's command line: halt before line a
#   s4a     a different QEMU process after the wait: halt, b to f not run
#   s4b     no QEMU process after the wait: halt, b to f not run
#   s5a..s5e  a STOP: in step a, b, c, d, e: halt, no later step, 'row t9' refused
#   s6      step c without PERSISTENCE SHOWN: halt
#   s7i     the smoke completes with lost above 0: no halt, 'row t9' starts after classification
#   s7ii    a STOP: in the smoke: halt, 'row t9' refused
#   s7iii   neither line in the smoke's console: halt
#   s8a     a kernel hash that differs at open: halt
#   s8b     a gate record that differs from S2's: halt before t8
#   s8c     (added) an identity that differs after the open: 'row t8' halts, no attempt
#   s9      labels and freshness: open S1 / open S2 refused; another earlier t8 attempt
#           refused; the new attempt's name not attempt02: halt
#   s10a..s10d  test 9: a STOP: in (a), (b), (c), (d)+(e) stops the later steps
#   s11     'term t8' during the wait: TERM to the row's group, the attempt exported as
#           interrupted, the fake QEMU untouched
#   s11b    the same while a poll is in flight under its timeout (what is left running)
# Added for the bounded check of 2026-10-05 (O1 to O3 of g3_battery.sh):
#   s13     (O1) T8 halts in its steps (a STOP: in step e), the row is classified, then 'row
#           t9' is run WITH EGW_G3_RUI_GO set to some words: refused, no attempt of t9
#   s14     (O2) the host's tunnel master ends after the check that follows step d: the
#           preamble of step e reopens it (TUNNEL UP): halt naming step e, f not run
#   s15     (O2) the same before step f: halt naming step f (what of f ran is shown)
#   s16     (O2) the master ends during T9, before step t9-b: halt naming t9-b, the later
#           steps of T9 not run
#   s17     (O2) the master ends after the last step of T8: only the gate's preamble
#           reopens it: GATE t8 does not pass, a halt, 'row t9' refused
#   s18     (O3) T8 completes with no halt and its gate passes; classified invalid
#           instrumentation: classify records a halt, 'row t9' refused
# s12, s2vii and s7iii classify row t8 invalid instrumentation: since O3 they also check
# that classify records that halt (classify_invalid).
# Every scenario but s1 and s2iii runs the short-timing variant (bs3_short.sh) with the
# bench device BENCH_FAST_DRAIN=1 (bs3_setup.sh, venv/bin/activate).
set -u
SC=${1:?usage: bs3_run.sh <scenario>}
HERE=$(cd "$(dirname "$0")" && pwd)
SCR=$(cd "$HERE/../../.." && pwd)
PREP=$SCR/g3/s3prep
ROOT=/tmp/g3-s3-bench
B=$ROOT/$SC
FINAL=$PREP/g3_battery.sh
SHORT=$HERE/g3_battery.short.sh
REAL_PY=/home/ruisth/egw-exec/venv/bin/python
BASE_PATH=$PATH
CHECKS=0
FAILS=0
RC=0
SMOKE=itest-post-reboot-01-q2
POST_ID=bbbbbbbb-0000-4000-8000-00000000000b
PRE_ID=aaaaaaaa-0000-4000-8000-00000000000a

sha() { /usr/bin/sha256sum "$1" | cut -d' ' -f1; }
# mask: the bench and the scratchpad are shown by name, never by path; a path of the
# scratchpad's own tree that a listing cut short is shown as cut.
TMPROOT=$(dirname "$(dirname "$(dirname "$(dirname "$SCR")")")")
mask() { sed "s#$B#<bench>#g; s#$SCR#<scratchpad>#g; s#$TMPROOT/[^ ;|]*#<a path of the scratchpad, cut>#g"; }
say() { echo; echo "=== $*"; }
note() { echo "--- $*" | mask; }
ok() { CHECKS=$((CHECKS + 1)); echo "CHECK ok: $*" | mask; }
bad() { CHECKS=$((CHECKS + 1)); FAILS=$((FAILS + 1)); echo "CHECK FAILED: $*" | mask; }
keep() {
    grep -E '^(## |HALT|REFUSED|NOT STARTED|GATE|row t|NOTE|Next|STOP|poll |QEMU|REBOOT|CONTAINERS|PERSISTENCE|CONTROLLER PROCESS|TEST STATUS|TUNNEL|MASTER|keepalive|KEEPALIVE|not a keepalive|carrier set|gate record|admitted|NOT FRESH|session S3|  HALT|  row |    HALT|    attempt|    RUNNING|TERM sent|exit=|probe exit|root ssh exit|ss exit|docker ps exit|controller untouched|reboot command sent|drained:|observations read|  "lost"|  "late_confirmations"|still in the row|waiting for the row|no attempt existed|  .*\.txt:[0-9]+:STOP:)' \
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
attempt_of() { sed -n 's/^attempt=//p' "$EGW_G3_STATE/row-$1.env" 2> /dev/null | tail -n 1; }
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
row_key() { sed -n "s/^$2=//p" "$EGW_G3_STATE/row-$1.env" 2> /dev/null | tail -n 1; }
qemu_state() {
    local pid
    pid=$(cat "$B/qemu.pid" 2> /dev/null)
    if [ -n "$pid" ] && [ -d "/proc/$pid" ]; then echo "pid $pid alive, start tick $(cut -d' ' -f22 "/proc/$pid/stat")"; else echo "pid ${pid:-none} not running"; fi
}
reboots() { grep -c 'sudo systemctl reboot' "$EGW_STUB_STATE/ssh.log" 2> /dev/null; }
# What went to the stub guest and the stub host commands, read after a row.
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
shown = polls if len(polls) <= 8 else polls[:3] + polls[-5:]
for i, r in enumerate(polls, 1):
    if r in shown:
        print("  poll %d (step %03d): command starts '%s', exit status %s, %.1f s" % (i, r["seq"], " ".join(r["argv"][:2]), r["exit_code"], r["duration_s"]))
    elif i == 4:
        print("  ... (%d more polls)" % (len(polls) - 8))
bounds = [int(r["argv"][1]) for r in polls if r["argv"][0] == "timeout" and r["argv"][1].isdigit()]
codes = sorted(set(r["exit_code"] for r in polls))
print("polls: %d; run by the host's timeout: %d; bounds used (s): %s; smallest %s, largest %s; exit statuses seen: %s"
      % (len(polls), len(bounds), " ".join(str(b) for b in sorted(set(bounds), reverse=True)),
         min(bounds) if bounds else "-", max(bounds) if bounds else "-", " ".join(str(c) for c in codes)))
print("POLLFACTS %d %d %s %s" % (len(polls), len(bounds), min(bounds) if bounds else -1, max(bounds) if bounds else -1))
EOF
}
setup() {          # setup VARIANT FAST SCALED: the bench, the script under test, the environment
    local variant=$1
    export BENCH_FAST_DRAIN=$2 BENCH_SCALED=$3
    if [ -e "$B" ]; then
        for p in $(cat "$B/qemu.pids.all" 2> /dev/null); do kill -- "-$p" 2> /dev/null; done
        rm -rf "$B"
    fi
    mkdir -p "$ROOT" || exit 1
    case $variant in
        final) G=$FINAL; echo "script run: the FINAL bytes, <scratchpad>/g3/s3prep/g3_battery.sh, sha256 $(sha "$G")" ;;
        short)
            G=$SHORT
            echo "script run: the short-timing variant, <scratchpad>/g3/s3prep/bench/g3_battery.short.sh, sha256 $(sha "$G")"
            echo "  it differs from the final bytes (g3_battery.sh, sha256 $(sha "$FINAL")) in $(diff "$FINAL" "$G" | grep -c '^<') lines: $(diff "$FINAL" "$G" | grep '^>' | cut -c3-36 | tr -s ' ' | tr '\n' ';')"
            [ "$(diff "$FINAL" "$G" | grep -c '^<')" = 2 ] || { echo "REFUSED: the variant is not the final bytes with two lines changed (run bs3_short.sh)"; exit 2; }
            ;;
    esac
    echo "## $(date -u +%Y-%m-%dT%H:%M:%SZ) scenario $SC; host uptime $(cut -d' ' -f1 /proc/uptime) s; row files: the real <scratchpad>/g3/s3prep/rows (manifest sha256 $(sha "$PREP/rows/rows.manifest.json"))"
    echo "bench scripts (sha256, first 16 characters): bs3_run.sh $(sha "$HERE/bs3_run.sh" | cut -c1-16), bs3_setup.sh $(sha "$HERE/bs3_setup.sh" | cut -c1-16), bs3_env.sh $(sha "$HERE/bs3_env.sh" | cut -c1-16), bs3_stubs.py $(sha "$HERE/bs3_stubs.py" | cut -c1-16)"
    echo "bench switches: BENCH_FAST_DRAIN=$2 (1: 'drained' returns after two readings; 0: its real 130 s quiet window), BENCH_SCALED=$3 (1: the test module's STUB_SLEEP and STUB_TIMEOUT, ${EGW_STUB_MS_PER_S:-1000} ms and ${EGW_STUB_TIMEOUT_MS_PER_S:-1000} ms for each second; 0: the host's sleep and timeout)"
    echo "bench keepalive: no keepalive client of wsl.exe runs on the host (2026-10-05) and the bench starts none: the steps script's keepalive_check is answered by the bench's ps stub, which adds a SYNTHETIC client (pid 4194301 'sleep 43200', parent 4194300 'Relay(bench)'; no process) to the listing that check reads; processes 'sleep N' with N of 3600 or more now on the host: $(/usr/bin/ps -eo args= 2> /dev/null | awk '$1 == "sleep" && NF == 2 && $2 >= 3600' | wc -l)"
    bash "$HERE/bs3_setup.sh" "$B" > "$ROOT/$SC.setup.log" 2>&1 || { echo "setup failed:"; tail -n 5 "$ROOT/$SC.setup.log"; exit 1; }
    grep -E '^(drivers of the copy|test module imported|tunnel.sh:|itest-helpers.sh:)' "$ROOT/$SC.setup.log" | mask
    # shellcheck source=/dev/null
    . "$HERE/bs3_env.sh"
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
    echo
    if [ "$FAILS" -eq 0 ]; then
        echo "## $(date -u +%Y-%m-%dT%H:%M:%SZ) SCENARIO $SC: PASS ($CHECKS checks)"
    else
        echo "## $(date -u +%Y-%m-%dT%H:%M:%SZ) SCENARIO $SC: FAIL ($FAILS of $CHECKS checks failed)"
    fi
}

# --- the common passages -------------------------------------------------------------------
open_s3() {
    run open S3
    want_rc 0 "open S3"
    want "the session is open" '^## .* session S3 is open'
    Q0=$(qemu_state)
    note "the fake process that stands for QEMU after the open: $Q0"
}
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
t9_refused() {     # after a halt of row t8, 'row t9' must be refused: nothing started, no attempt
    # t9_refused [REGEX]: REGEX, when given, is what the refusal must quote of the halt
    # (the session's last recorded halt, in brackets after 'has a recorded halt ').
    run row t9
    want_rc 2 "row t9 after the halt of row t8 (refused: nothing was started)"
    want "row t9 is refused because of the recorded halt" '^REFUSED: NOT STARTED: session S3 has a recorded halt'
    [ -z "${1:-}" ] || want "the refusal quotes the halt that ends the session" "^REFUSED: NOT STARTED: session S3 has a recorded halt $1"
    is "attempts of row t9 created" "$(ls -d "$EGW_ATTEMPTS"/*_g3-qualification-t9_attempt* 2> /dev/null | wc -l)" 0
}
halts() { grep -c '^halt=' "$EGW_G3_STATE/session-S3.env" 2> /dev/null; }   # halts recorded for the session
# classify_invalid ROW (O3 of 2026-10-05): 'invalid instrumentation' is a halt recorded by
# classify itself; the export and the class are recorded as for any other pair.
classify_invalid() {
    local before
    before=$(halts)
    classify_ok "$1" failed invalid unknown
    want_rc 1 "classify $1 as invalid instrumentation (classify records a halt: exit 1)"
    want "row $1 is classified invalid instrumentation and exported" "^row $1: classified 'invalid instrumentation'; driver code [0-9]+; export: verified"
    want "classify records the halt of that class" "^HALT: row $1 is classified invalid instrumentation \(request, section 5 item 2; decision summary, choice 2\): no further row of S3 starts"
    is "halts recorded for the session by this classify" "$(($(halts) - before))" 1
    is "the row's state after classify" "$(row_key "$1" state)" classified
    note "the last lines classify printed: $(tail -n 3 "$B/last.out" | cut -c1-200 | tr '\n' '|')"
}
# hook_exec STEP TEXT: the host's tunnel master ends just before the export tool records
# STEP (bs3_setup.sh, the bench venv's python: bench_hook.exec.<step>); its control socket
# stays behind, stale, as in s1b. TEXT says where that is.
hook_exec() {
    printf '%s\n' "# BENCH: the host's tunnel master ends $2 (its control socket stays behind, stale)" \
        'rm -f "$EGW_STUB_STATE/master_alive"' > "$EGW_STUB_STATE/bench_hook.exec.$1"
}
hook_ran() {       # hook_ran STEP: the hook of hook_exec ran, once, before STEP was recorded
    is "the bench hook ran before the step $1 was recorded (the master ended there)" \
        "$([ -e "$EGW_STUB_STATE/bench_hook.exec.$1.done" ] && [ ! -e "$EGW_STUB_STATE/bench_hook.exec.$1" ] && grep -c "before the step $1 was recorded" "$B/hooks.log")" 1
}
reopened_in() {    # reopened_in ROW STEP: the preamble of STEP found the socket stale and reopened the tunnel
    want "the preamble of $2 found the master gone (the socket stale)" '^tunnel: connection refused on .*tunnel\.ctl \(no process listens on it\) - stale socket file removed' "$(console "$1" "$2")"
    want "the preamble of $2 reopened the tunnel (TUNNEL UP at the start of a line)" '^TUNNEL UP$' "$(console "$1" "$2")"
}
sim_calls() { grep -c -- "-m egw_simulator.*--run-id $1" "$EGW_STUB_STATE/calls.log" 2> /dev/null; }
t8_halted() {      # t8_halted HALT-REGEX STEPS-REGEX: a row t8 that halts; then classify, and row t9 refused
    run row t8
    want_rc 1 "row t8 (a halt)"
    want "the halt of row t8" "$1"
    want_steps t8 "$2"
    is "the fake QEMU process after the row" "$(qemu_state)" "$Q0"
    sent_to_guest
}
close_ok() {
    run close
    want_rc "${1:-0}" "close"
    want "the session is closed" '^## .* session S3 closed'
}
status_now() {
    say "g3_battery.sh status"
    setsid bash "$G" status < /dev/null 2>&1 | grep -E '^(open session|qemu pgrep|session S3|  |    )' | mask | cut -c1-300
}

# --- the scenarios -------------------------------------------------------------------------
# Everything from here to the end is ONE group, which bash reads whole before running it:
# an edit of this file while a scenario runs (s2iii takes 15 min) cannot change what that
# scenario executes.
{
case $SC in
    s1)
        setup final 0 0
        echo "EXPECTED: open S3 admits the one earlier attempt of row t8; row t8 runs a to f with every marker and no halt (the wait: two refused polls, the third counted); classify; row t9 runs its four fenced steps and the exposure step; close. Real time: the helper's 130 s quiet windows, the host's sleep and timeout."
        open_s3
        want "the keepalive check of open found the bench's synthetic client (the ps stub; no process)" "^keepalive: pid 4194301 'sleep 43200', parent 4194300 \(Relay\(bench\)\), running for [0-9]+ s, about [0-9]+ s left"
        want "the one earlier attempt admitted in the attempts directory" "^admitted: .*: $EGW_ATTEMPTS/20261003T142310Z_g3-qualification-t8_attempt01$"
        want "the one earlier attempt admitted under the output root" "^admitted: .*: $EGW_OUTPUT_TEST/runs/2026-10-03/20261003T142310Z_g3-qualification-t8_attempt01$"
        t8_ok
        sent_to_guest
        note "the first line of step a's console: $(head -n 1 "$(console t8 t8-a-reboot)" | cut -c1-250)"
        want "the carriers are really unset in the step shell" '^carriers after the unset: DEVICES=<unset> ACCEPT_UNACCOUNTED=<unset> EVENTS_EXPECTED=<unset> DRAIN_QUIET_S=<unset> DRAIN_STEP_S=<unset> DRAIN_LIMIT_S=<unset> READY_LIMIT_S=<unset>' "$(console t8 t8-a-reboot)"
        polls t8 | grep -v '^POLLFACTS'
        is "lines starting with STOP: in step a's console (the file's own comment holds the text)" "$(grep -c '^STOP:' "$(console t8 t8-a-reboot)")" 0
        note "the workload field's authority text: $("$REAL_PY" -c 'import json,sys; print(json.load(open(sys.argv[1]))["workload"]["battery"])' "$(attempt_of t8)/attempt.json")"
        classify_ok t8 finished valid pass
        want_rc 0 "classify t8"
        want "row t8 is classified pass and exported (the export tool's own verification)" "^row t8: classified 'pass'; driver code 0; export: verified -> $EGW_OUTPUT_TEST/runs/"
        t9_ok
        classify_ok t9 finished valid pass
        want_rc 0 "classify t9"
        close_ok
        status_now
        note "packages under the bench's output root: $(ls "$B/out/runs"/*/ 2> /dev/null | grep -v '^$' | grep -v ':$' | tr '\n' ' ')"
        ;;
    s2i | s2ii)
        setup short 1 0
        if [ "$SC" = s2i ]; then
            st boot_id_then_stall_calls 1
            code=124
            echo "EXPECTED: polls 1 and 2 are refused (255); poll 3 prints the new boot id and then stalls, its timeout ends it (124): NOT counted; poll 4 ends 0 with the new id: counted; the row goes on to f with no halt."
        else
            st boot_id_then_exit_calls 1
            code=255
            echo "EXPECTED: polls 1 and 2 are refused (255); poll 3 prints the new boot id and then ends 255: NOT counted; poll 4 ends 0 with the new id: counted; the row goes on to f with no halt."
        fi
        open_s3
        t8_ok
        want "the poll that printed the new id and ended $code is NOT counted" "^poll 3 at \+[0-9]+ s \(bounded to [0-9]+ s\): NOT counted - it printed the boot id $POST_ID, other than the saved one, and then ended with exit status $code:"
        want "the next poll, ended 0 with the new id, is counted" "^poll 4 at \+[0-9]+ s \(bounded to [0-9]+ s\): exit status 0 and the answer is the boot id $POST_ID"
        is "polls recorded as steps of the attempt" "$(ls "$(attempt_of t8)"/console/*-t8-wait-ssh.stdout.txt | wc -l)" 4
        note "the console of poll 3, kept as the recorded step it is: $(ls "$(attempt_of t8)"/console/*-t8-wait-ssh.stdout.txt | sed -n 3p | xargs cat)"
        polls t8 | grep -v '^POLLFACTS'
        note "the row's record of the wait: $(row_key t8 t8_ssh_answered)"
        classify_ok t8 finished valid pass
        want_rc 0 "classify t8"
        close_ok
        ;;
    s2iii)
        setup final 0 0
        st guest_never_answers
        echo "EXPECTED: the guest never answers after the reboot: every poll ends 255 at once, one poll every 10 s, for 900 s of /proc/uptime from the end of step a; the last polls are bounded to what is left (below 20 s, never 0); then HALT 'reboot not shown within the wait', line b not run, QEMU not signalled; 'row t9' refused; 'close' halts because the guest does not answer."
        open_s3
        t8_halted '^HALT: row t8: reboot not shown within the wait: in the 900 s after step a ended, none of the [0-9]+ poll\(s\) both ended with exit status 0 and answered' \
            '^guest-state-before t8-qemu-before t8-a-reboot t8-wait-ssh x[0-9]+ t8-qemu-after guest-state-after gate-healthy gate-units gate-tunnel-check$'
        want "the halt says it is not by itself a failure of the system" 'inconclusive / not demonstrated, not by itself a failure of the system'
        want "the halt says line b was not run and nothing was signalled or started" 'Line b was NOT run, nor steps c to f, and T9 is not run\. QEMU was NOT signalled'
        want "the QEMU reading after the wait: the same process" '^QEMU PROCESS UNCHANGED' "$(console t8 t8-qemu-after)"
        facts=$(polls t8)
        printf '%s\n' "$facts" | grep -v '^POLLFACTS'
        # shellcheck disable=SC2046
        set -- $(printf '%s\n' "$facts" | sed -n 's/^POLLFACTS //p')
        is "polls not run by the host's timeout" "$(($1 - $2))" 0
        if [ "$3" -ge 1 ] && [ "$3" -lt 20 ]; then ok "the smallest bound of a poll is $3 s: the remainder of the budget, below 20 and never 0"; else bad "the smallest bound of a poll is $3 s"; fi
        is "the largest bound of a poll (s)" "$4" 20
        a_end=$(row_key t8 t8_wait | sed -n 's/.*after step a ended (up=\([0-9]*\)).*/\1/p')
        h_up=$(sed -n 's/^halt=up=\([0-9]*\) row t8: reboot not shown.*/\1/p' "$EGW_G3_STATE/row-t8.env" | head -n 1)
        note "step a ended at up=$a_end; the halt was recorded at up=$h_up: $((h_up - a_end)) s"
        if [ $((h_up - a_end)) -ge 900 ] && [ $((h_up - a_end)) -le 905 ]; then ok "the wait expired 900 s (to within 5 s) after step a ended"; else bad "the wait expired $((h_up - a_end)) s after step a ended"; fi
        is "the row's start instant is recorded once and was not reset" "$(grep -c '^start_up=' "$EGW_G3_STATE/row-t8.env")" 1
        is "the row's ceiling as recorded (min)" "$(row_key t8 ceiling_min)" 135
        note "the row's record of the wait: $(row_key t8 t8_wait)"
        is "reboot commands sent to the stub guest" "$(reboots)" 1
        classify_ok t8 failed unknown inconclusive
        want "row t8 is classified inconclusive / not demonstrated" "^row t8: classified 'inconclusive / not demonstrated'"
        t9_refused
        run close
        want_rc 1 "close with a guest that does not answer and the QEMU process alive (a halt)"
        want "close: the guest did not answer, nothing was stopped, QEMU is not killed" '^HALT: close: the guest did not answer \(exit 97\) although a qemu-system-aarch64 process is running'
        is "the fake QEMU process after the close" "$(qemu_state)" "$Q0"
        status_now
        ;;
    s2iv)
        setup short 1 0
        st boot_id_then_stall_always
        echo "EXPECTED (budget 48 s, one poll every 3 s, each bounded to 20 s or to what is left): polls 1 and 2 are refused (255); every later poll prints the new boot id and stalls until its timeout ends it (124): none is counted; the first of them is bounded to 20 s, the next to the remainder of the budget (below 20 s, never 0); then HALT 'reboot not shown within the wait'."
        open_s3
        t8_halted '^HALT: row t8: reboot not shown within the wait: in the 48 s after step a ended' \
            '^guest-state-before t8-qemu-before t8-a-reboot t8-wait-ssh x[0-9]+ t8-qemu-after guest-state-after gate-healthy gate-units gate-tunnel-check$'
        facts=$(polls t8)
        printf '%s\n' "$facts" | grep -v '^POLLFACTS'
        # shellcheck disable=SC2046
        set -- $(printf '%s\n' "$facts" | sed -n 's/^POLLFACTS //p')
        is "polls not run by the host's timeout" "$(($1 - $2))" 0
        if [ "$3" -ge 1 ] && [ "$3" -lt 20 ]; then ok "the smallest bound of a poll is $3 s: the remainder of the budget, below 20 and never 0"; else bad "the smallest bound of a poll is $3 s"; fi
        is "the largest bound of a poll (s)" "$4" 20
        want "a poll that printed the new id and was ended by its timeout is not counted" "^poll [0-9]+ at \+[0-9]+ s \(bounded to 20 s\): NOT counted - it printed the boot id $POST_ID, other than the saved one, and then ended with exit status 124:"
        want "a poll bounded to the remainder is said so" '^poll [0-9]+ at \+[0-9]+ s \(bounded to (1?[0-9]) s\): NOT counted'
        want_no "no poll was counted" '^poll [0-9]+ .*: exit status 0 and the answer is the boot id'
        a_end=$(row_key t8 t8_wait | sed -n 's/.*after step a ended (up=\([0-9]*\)).*/\1/p')
        h_up=$(sed -n 's/^halt=up=\([0-9]*\) row t8: reboot not shown.*/\1/p' "$EGW_G3_STATE/row-t8.env" | head -n 1)
        if [ $((h_up - a_end)) -ge 48 ] && [ $((h_up - a_end)) -le 51 ]; then ok "the wait expired $((h_up - a_end)) s after step a ended (budget 48 s)"; else bad "the wait expired $((h_up - a_end)) s after step a ended (budget 48 s)"; fi
        classify_ok t8 failed unknown inconclusive
        t9_refused
        close_ok
        ;;
    s1b | s12)
        setup short 1 0
        if [ "$SC" = s1b ]; then
            printf '%s\n' '#!/bin/bash' '# BENCH: the tunnel master ends with the reboot; its control socket stays behind, stale' \
                'rm -f "$EGW_STUB_STATE/master_alive"' > "$B/hooks/reboot.sh"
            echo "EXPECTED: the host's tunnel master ends with the reboot (in the other scenarios the stub's master outlives it): the preamble of step b finds the tunnel down, removes the stale socket and reopens it; the row then runs a to f with every marker and no halt."
        else
            printf '%s\n' '#!/bin/bash' '# BENCH: the tunnel master ends with the reboot and no new master can be opened' \
                'rm -f "$EGW_STUB_STATE/master_alive"; : > "$EGW_STUB_STATE/master_open_fails"' > "$B/hooks/reboot.sh"
            echo "EXPECTED: the host's tunnel master ends with the reboot and cannot be reopened: the wait counts a poll (it needs no tunnel), then the preamble of step b fails: the step answers 97 and never runs; HALT, steps c to f not run; 'row t9' refused."
        fi
        chmod +x "$B/hooks/reboot.sh"
        open_s3
        if [ "$SC" = s1b ]; then
            t8_ok
            want "the preamble of step b removed the stale socket" '^tunnel: connection refused on .*tunnel\.ctl \(no process listens on it\) - stale socket file removed' "$(console t8 t8-b-wait-boot-id)"
            want "the preamble of step b reopened the tunnel" '^TUNNEL UP$' "$(console t8 t8-b-wait-boot-id)"
            want "step d closed that master and opened another" '^TUNNEL CLOSED$' "$(console t8 t8-d-tunnel)"
            sent_to_guest
            classify_ok t8 finished valid pass
            want_rc 0 "classify t8"
            close_ok
        else
            run row t8
            want_rc 1 "row t8 (a halt)"
            want "the halt of row t8" '^HALT: row t8: step t8-b-wait-boot-id answered 97: the host preamble of runbook 6\.1 \(venv, secrets, helpers, tunnel\) did not load, the step never ran'
            want_steps t8 '^guest-state-before t8-qemu-before t8-a-reboot t8-wait-ssh x3 t8-qemu-after t8-b-wait-boot-id t8-previous-boot-journal t8-previous-boot-oom guest-state-after gate-healthy gate-units gate-tunnel-check$'
            want "the wait itself counted a poll (the session's ssh needs no tunnel)" "^poll 3 at \+[0-9]+ s \(bounded to [0-9]+ s\): exit status 0 and the answer is the boot id $POST_ID"
            want_no "line b itself never ran: no REBOOT SHOWN at the start of a line" '^REBOOT SHOWN' "$(console t8 t8-b-wait-boot-id)"
            want "the gate did not pass either (no tunnel)" '^HALT: row t8: the gate did NOT pass .*tunnel_check through hx ended 97'
            is "the fake QEMU process after the row" "$(qemu_state)" "$Q0"
            sent_to_guest
            # O3 of 2026-10-05: the classification is now a halt of its own (classify_invalid)
            classify_invalid t8
            t9_refused
            close_ok
        fi
        ;;
    s2vii)
        setup short 1 0
        st bench_capture_lost_poll 3
        echo "EXPECTED: poll 3 prints the new boot id and ends 0, and its status reaches the script as 74 (the bench replaces the status of that one recorded poll by the one 'local_export exec' answers for a lost console capture; the frozen tool's own detection of a lost capture is not exercised): a HALT of its own at once, the poll is not counted, line b not run; 'row t9' refused."
        open_s3
        t8_halted '^HALT: row t8: poll 3 of the wait answered 74: its console capture was lost, so what the guest answered is not on record \(invalid instrumentation' \
            '^guest-state-before t8-qemu-before t8-a-reboot t8-wait-ssh x3 t8-qemu-after guest-state-after gate-healthy gate-units gate-tunnel-check$'
        want "the halt says line b was not run" 'Line b was NOT run, nor steps c to f, and T9 is not run'
        want_no "no poll was counted" '^poll [0-9]+ .*: exit status 0 and the answer is the boot id'
        note "the console of poll 3 (what the stub guest printed): $(ls "$(attempt_of t8)"/console/*-t8-wait-ssh.stdout.txt | sed -n 3p | xargs cat)"
        # O3 of 2026-10-05: the classification is now a halt of its own (classify_invalid)
        classify_invalid t8
        t9_refused
        close_ok
        ;;
    s2v | s2vi)
        setup short 1 0
        st guest_down_calls 0
        if [ "$SC" = s2v ]; then
            st boot_id.post "$PRE_ID"
            poll_re="^poll [0-9]+ at \+[0-9]+ s \(bounded to [0-9]+ s\): the guest answers with the boot id $PRE_ID, the saved pre-reboot id: it has not gone down yet, or did not reboot - waiting on"
            counts='\(0 ended with another status - no answer, whatever they printed; [0-9]+ answered the saved id; 0 ended 0 without one boot id as the answer\)'
            echo "EXPECTED (budget 48 s): after the reboot command the stub guest keeps answering, exit status 0, the SAVED boot id: no poll is counted; HALT 'reboot not shown within the wait', line b not run."
        else
            st boot_id.post "Welcome to the gateway (a banner line, not the kernel file)"
            poll_re="^poll [0-9]+ at \+[0-9]+ s \(bounded to [0-9]+ s\): exit status 0, but the answer is not one boot id of the kernel's form .* - NOT counted, waiting on"
            counts='\(0 ended with another status - no answer, whatever they printed; 0 answered the saved id; [0-9]+ ended 0 without one boot id as the answer\)'
            echo "EXPECTED (budget 48 s): after the reboot command the stub guest answers, exit status 0, a line that is not a boot id: no poll is counted; HALT 'reboot not shown within the wait', line b not run."
        fi
        open_s3
        t8_halted '^HALT: row t8: reboot not shown within the wait: in the 48 s after step a ended' \
            '^guest-state-before t8-qemu-before t8-a-reboot t8-wait-ssh x[0-9]+ t8-qemu-after guest-state-after gate-healthy gate-units gate-tunnel-check$'
        want "what each poll is said to be" "$poll_re"
        want "the halt counts the polls by kind" "$counts"
        want_no "no poll was counted" '^poll [0-9]+ .*: exit status 0 and the answer is the boot id'
        polls t8 | grep -v '^POLLFACTS'
        classify_ok t8 failed unknown inconclusive
        t9_refused
        close_ok
        ;;
    s3)
        setup short 1 0
        printf '%s\n' -no-reboot > "$B/qemu.extra"
        echo "EXPECTED: the fake QEMU's command line holds -no-reboot: row t8 halts before line a (class: not started), the reboot command is never sent, nothing is signalled; 'row t9' refused."
        open_s3
        note "the fake QEMU's command line: $(tr '\0' ' ' < "/proc/$(cat "$B/qemu.pid")/cmdline" | cut -c1-260)"
        t8_halted '^HALT: row t8: -no-reboot \(or its equivalent\) is on the command line of the running QEMU process .* Step a was NOT run: the reboot was NOT issued \(class: not started' \
            '^guest-state-before t8-qemu-before guest-state-after gate-healthy gate-units gate-tunnel-check$'
        want "the reading itself says where the option stands" '^STOP: -no-reboot \(or its equivalent\) is on the command line of the QEMU process [0-9]+, as argument number:text [0-9]+:-no-reboot' "$(console t8 t8-qemu-before)"
        is "reboot commands sent to the stub guest" "$(reboots)" 0
        is "the pre-reboot boot id file of line a exists" "$([ -e "$HOME/egw-tcg/itest/itest-reboot-q2.boot_id.pre" ] && echo yes || echo no)" no
        classify_ok t8 failed not-applicable not-run
        want "row t8 is classified not started" "^row t8: classified 'not started'"
        t9_refused
        close_ok
        ;;
    s4a | s4b)
        setup short 1 0
        if [ "$SC" = s4a ]; then
            printf '%s\n' '#!/bin/bash' '# BENCH: during the reboot the QEMU process ends and ANOTHER one is started (another launcher)' \
                '/usr/bin/sleep 1; kill -- "-$(cat "$BENCH/qemu.pid")"; /usr/bin/sleep 1; bash "$BENCH/stubs/fake_qemu_start.sh"' > "$B/hooks/reboot.sh"
            stopre='^STOP: the qemu-system-aarch64 process is not the one recorded before step a'
            echo "EXPECTED: the QEMU process recorded before step a is gone after the reboot command and another one runs: the wait counts a poll (the stub guest answers), the reading after the wait is a STOP, HALT, steps b to f not run; 'row t9' refused."
        else
            printf '%s\n' '#!/bin/bash' '# BENCH: during the reboot the QEMU process ends and nothing replaces it' \
                '/usr/bin/sleep 1; kill -- "-$(cat "$BENCH/qemu.pid")"' > "$B/hooks/reboot.sh"
            stopre='^STOP: no qemu-system-aarch64 process \(pgrep exit 1\)'
            echo "EXPECTED: the QEMU process recorded before step a is gone after the reboot command and none runs: the reading after the wait is a STOP, HALT, steps b to f not run, nothing re-launched; 'row t9' refused; 'close' finds no QEMU process."
        fi
        chmod +x "$B/hooks/reboot.sh"
        open_s3
        run row t8
        want_rc 1 "row t8 (a halt)"
        want "the halt of row t8" '^HALT: row t8: the qemu-system-aarch64 process after the wait is not the one recorded before step a, or none could be shown \(t8-qemu-after exit 1'
        want_steps t8 '^guest-state-before t8-qemu-before t8-a-reboot t8-wait-ssh x3 t8-qemu-after guest-state-after gate-healthy gate-units gate-tunnel-check$'
        want "the reading after the wait" "$stopre" "$(console t8 t8-qemu-after)"
        note "the fake process recorded before step a: $Q0; now: $(qemu_state) (ended, and in s4a replaced, by the bench's own hook, not by the script)"
        is "processes started by the bench for QEMU (the script re-launches nothing)" "$(wc -l < "$B/qemu.pids.all")" "$([ "$SC" = s4a ] && echo 2 || echo 1)"
        sent_to_guest
        classify_ok t8 failed unknown inconclusive
        t9_refused
        if [ "$SC" = s4b ]; then
            run close
            want_rc 1 "close with no QEMU process left (a halt, then the close driver alone)"
            want "close: no QEMU process is left, nothing to stop" '^HALT: close S3: no qemu-system-aarch64 process is left'
            want "the session is recorded closed" '^## .* session S3 closed'
        else
            close_ok
        fi
        ;;
    s5a)
        setup short 1 0
        head -n 5 "$EGW_STUB_STATE/containers.pre" > "$EGW_STUB_STATE/containers.pre.5" && mv "$EGW_STUB_STATE/containers.pre.5" "$EGW_STUB_STATE/containers.pre"
        echo "EXPECTED: the stub guest lists five running containers, not six: line a prints its STOP: (the helper's line, at the start of a line) and sends no reboot command; HALT, no wait, no later step; 'row t9' refused. The file of step a holds the text 'STOP:' in its last comment line, which 'set -v' echoes: only a line that STARTS with STOP: counts."
        open_s3
        t8_halted '^HALT: row t8: step a printed STOP: ' '^guest-state-before t8-qemu-before t8-a-reboot guest-state-after gate-healthy gate-units gate-tunnel-check$'
        want "step a's own STOP: line" '^STOP: test 8: no pre-reboot /metrics reading or twin snapshot, no boot id' "$(console t8 t8-a-reboot)"
        is "lines of step a's console that hold STOP: anywhere / at the start of a line" "$(grep -c 'STOP:' "$(console t8 t8-a-reboot)") / $(grep -c '^STOP:' "$(console t8 t8-a-reboot)")" "2 / 1"
        is "reboot commands sent to the stub guest" "$(reboots)" 0
        classify_ok t8 failed not-applicable not-run
        t9_refused
        close_ok
        ;;
    s5b | s5c)
        export EGW_STUB_MS_PER_S=50 EGW_STUB_TIMEOUT_MS_PER_S=1000
        setup short 1 1
        if [ "$SC" = s5b ]; then
            st guest_dies_after_calls 3
            echo "EXPECTED (the runbook's 10 s pauses run as 0.5 s: STUB_SLEEP): the wait counts poll 3; then the stub guest answers nothing more: line b makes its 90 reads and prints its STOP:; HALT, steps c to f not run; 'row t9' refused."
            open_s3
            run row t8
            want_rc 1 "row t8 (a halt)"
            want "the halt of row t8" '^HALT: row t8: step b does not show REBOOT SHOWN with no STOP:'
            want_steps t8 '^guest-state-before t8-qemu-before t8-a-reboot t8-wait-ssh x3 t8-qemu-after t8-b-wait-boot-id t8-previous-boot-journal t8-previous-boot-oom guest-state-after gate-healthy gate-units gate-tunnel-check$'
            want "step b's own STOP: line" '^STOP: test 8: reboot NOT shown - the guest never answered a boot id read that ended with exit status 0 in 90 reads' "$(console t8 t8-b-wait-boot-id)"
            want "the gate did not pass either (the stub guest is gone)" '^HALT: row t8: the gate did NOT pass'
        else
            head -n 5 "$EGW_STUB_STATE/containers.pre" > "$EGW_STUB_STATE/containers.post"
            echo "EXPECTED (the runbook's 10 s pauses run as 0.5 s: STUB_SLEEP): step b shows the reboot; after it the stub guest lists five of the six saved containers: line c makes its 90 reads and prints its STOP:; HALT naming both markers as missing, steps d to f not run; 'row t9' refused."
            open_s3
            run row t8
            want_rc 1 "row t8 (a halt)"
            want "the halt of row t8 names what is missing" '^HALT: row t8: step c does not show both CONTAINERS RETURNED UNAIDED and PERSISTENCE SHOWN with no STOP: - a STOP: line was printed \(or the step left no console\); no line CONTAINERS RETURNED UNAIDED; no line PERSISTENCE SHOWN '
            want_steps t8 '^guest-state-before t8-qemu-before t8-a-reboot t8-wait-ssh x3 t8-qemu-after t8-b-wait-boot-id t8-c-unaided t8-previous-boot-journal t8-previous-boot-oom guest-state-after gate-healthy gate-units gate-tunnel-check$'
            want "step c's own STOP: line" '^STOP: test 8: the containers did NOT return unaided within 90 reads' "$(console t8 t8-c-unaided)"
        fi
        is "the fake QEMU process after the row" "$(qemu_state)" "$Q0"
        sent_to_guest
        is "simulator calls (the smoke was not started)" "$(grep -c -- '-m egw_simulator' "$EGW_STUB_STATE/calls.log")" 0
        classify_ok t8 failed valid fail
        t9_refused
        if [ "$SC" = s5b ]; then
            run close
            want_rc 1 "close with a guest that does not answer and the QEMU process alive (a halt)"
            want "close: the guest did not answer, nothing was stopped, QEMU is not killed" '^HALT: close: the guest did not answer \(exit 97\) although a qemu-system-aarch64 process is running'
            is "the fake QEMU process after the close" "$(qemu_state)" "$Q0"
        else
            close_ok
        fi
        ;;
    s5d)
        setup short 1 0
        echo "EXPECTED: the tunnel cannot be reopened at line d (the stub's master does not open): line d prints its STOP:; HALT, the tunnel check and steps e and f not run; the gate does not pass (no tunnel); 'row t9' refused."
        open_s3
        st master_open_fails
        note "bench: from here on the stub refuses to open a tunnel master (the tunnel opened at 'open' stays up until line d closes it)"
        run row t8
        want_rc 1 "row t8 (a halt)"
        want "the halt of row t8" '^HALT: row t8: step d printed STOP: \(tunnel NOT reopened'
        want_steps t8 '^guest-state-before t8-qemu-before t8-a-reboot t8-wait-ssh x3 t8-qemu-after t8-b-wait-boot-id t8-c-unaided t8-d-tunnel t8-previous-boot-journal t8-previous-boot-oom guest-state-after gate-healthy gate-units gate-tunnel-check$'
        want "step d's own STOP: line" '^STOP: test 8: tunnel NOT reopened' "$(console t8 t8-d-tunnel)"
        want "the gate did not pass (the tunnel is down)" '^HALT: row t8: the gate did NOT pass .*tunnel_check through hx ended 97'
        is "the fake QEMU process after the row" "$(qemu_state)" "$Q0"
        sent_to_guest
        classify_ok t8 failed valid fail
        t9_refused
        close_ok
        ;;
    s5e)
        setup short 1 0
        st rec_same_rc 4
        echo "EXPECTED: the twins differ across the reboot (the stub's 'same' exits 4): line e prints its STOP:; HALT, the smoke (step f) not run; 'row t9' refused."
        open_s3
        t8_halted '^HALT: row t8: step e printed STOP: ' \
            '^guest-state-before t8-qemu-before t8-a-reboot t8-wait-ssh x3 t8-qemu-after t8-b-wait-boot-id t8-c-unaided t8-d-tunnel t8-tunnel-check t8-e-state t8-previous-boot-journal t8-previous-boot-oom guest-state-after gate-healthy gate-units gate-tunnel-check$'
        want "step e's own STOP: line" '^STOP: test 8: persistence across the reboot NOT verified' "$(console t8 t8-e-state)"
        is "simulator calls (the smoke was not started)" "$(grep -c -- '-m egw_simulator' "$EGW_STUB_STATE/calls.log")" 0
        classify_ok t8 failed valid fail
        t9_refused
        close_ok
        ;;
    s6)
        setup short 1 0
        printf '%s\n' itest-dup-02 itest-smoke-01 > "$EGW_STUB_STATE/events.post"
        echo "EXPECTED: the six containers return unaided, but one of the three event directories saved before the reboot is not listed after it: step c prints CONTAINERS RETURNED UNAIDED and then its STOP: (persistence NOT shown), never PERSISTENCE SHOWN; HALT naming that marker as missing, steps d to f not run; 'row t9' refused."
        open_s3
        t8_halted '^HALT: row t8: step c does not show both CONTAINERS RETURNED UNAIDED and PERSISTENCE SHOWN with no STOP: - a STOP: line was printed \(or the step left no console\); no line PERSISTENCE SHOWN ' \
            '^guest-state-before t8-qemu-before t8-a-reboot t8-wait-ssh x3 t8-qemu-after t8-b-wait-boot-id t8-c-unaided t8-previous-boot-journal t8-previous-boot-oom guest-state-after gate-healthy gate-units gate-tunnel-check$'
        want "step c: CONTAINERS RETURNED UNAIDED is there" '^CONTAINERS RETURNED UNAIDED: ' "$(console t8 t8-c-unaided)"
        want_no "step c: PERSISTENCE SHOWN is not, at the start of any line" '^PERSISTENCE SHOWN' "$(console t8 t8-c-unaided)"
        is "lines of step c's console that hold PERSISTENCE SHOWN anywhere (the line 'set -v' echoes)" "$(grep -c 'PERSISTENCE SHOWN' "$(console t8 t8-c-unaided)")" 1
        want "step c's own STOP: line" '^STOP: test 8: persistence NOT shown - 1 of the 3 event directories' "$(console t8 t8-c-unaided)"
        want_no "the halt does not name the container marker as missing" 'no line CONTAINERS RETURNED UNAIDED'
        classify_ok t8 failed valid fail
        t9_refused
        close_ok
        ;;
    s7i)
        setup short 1 0
        printf '%s\n' '{' '  "lost": 3,' '  "late_confirmations": 41,' '  "bench": "printed by the bench before the stub of itest_reconcile check"' '}' > "$EGW_STUB_STATE/bench_rec_check_text"
        echo "EXPECTED: the smoke's console shows 'TEST STATUS $SMOKE: ... -> PROCEDURE COMPLETE.', no STOP:, and lost 3 and late_confirmations 41: NO halt; the operator classifies T8 as failed (valid/fail), and 'row t9' then starts and runs."
        open_s3
        t8_ok
        want "the smoke's console shows lost above 0" '^  "lost": 3,$' "$(console t8 t8-f-smoke)"
        want "the smoke's console shows late_confirmations above 0" '^  "late_confirmations": 41,$' "$(console t8 t8-f-smoke)"
        want "the script says that it records no halt for the smoke and that this is not a verdict" "^row t8: step f shows 'TEST STATUS $SMOKE: \.\.\. -> PROCEDURE COMPLETE' and no STOP: - this script records no halt for the smoke"
        note "the row's keys: t8_smoke=$(row_key t8 t8_smoke); t8_reached_smoke=$(row_key t8 t8_reached_smoke | cut -c1-60)..."
        classify_ok t8 failed valid fail
        want_rc 0 "classify t8 as failed"
        want "row t8 is classified a valid failure of the system" "^row t8: classified 'valid SUT failure'"
        is "halts recorded for the session" "$(grep -c '^halt=' "$EGW_G3_STATE/session-S3.env")" 0
        t9_ok
        classify_ok t9 finished valid pass
        want_rc 0 "classify t9"
        close_ok
        ;;
    s7ii)
        setup short 1 0
        st rec_check_rc 3
        echo "EXPECTED: the smoke's post-processing fails (the stub's 'check' exits 3): the helper prints STOP: lines and 'TEST STATUS ... -> FAILED' behind a STOP:; HALT, 'row t9' refused."
        open_s3
        t8_halted "^HALT: row t8: step f, the post-reboot smoke $SMOKE, printed STOP: " "$T8_ALL"
        want "the helper's STOP: for the smoke" "^STOP: TEST STATUS $SMOKE: simulator exit=0 transcript \(tee\) exit=0 post=1 -> FAILED" "$(console t8 t8-f-smoke)"
        want_no "no line of a completed procedure at the start of a line" "^TEST STATUS $SMOKE: .* -> PROCEDURE COMPLETE" "$(console t8 t8-f-smoke)"
        note "the row's keys: t8_smoke=$(row_key t8 t8_smoke)"
        classify_ok t8 failed valid fail
        t9_refused
        close_ok
        ;;
    s7iii)
        setup short 1 0
        printf '%s\n' '# BENCH: the step shell is ended at the moment the simulator starts (KILL to the parent of this stub): the' \
            '# helper prints neither its status line nor a STOP:.' 'kill -KILL "$PPID"; exit 1' > "$EGW_STUB_STATE/bench_hook.sim.$SMOKE"
        echo "EXPECTED: the smoke's step shell ends before the helper prints anything (the bench ends it when the simulator starts): the console holds neither 'TEST STATUS ... PROCEDURE COMPLETE' nor a STOP:; HALT, 'row t9' refused. (The real line f always ends with one of the two lines; a shell that dies is the one way to neither.)"
        open_s3
        t8_halted "^HALT: row t8: step f printed no STOP: but its console does not show the line 'TEST STATUS $SMOKE: \.\.\. -> PROCEDURE COMPLETE'" "$T8_ALL"
        is "lines of the smoke's console that start with STOP: / with TEST STATUS" "$(grep -c '^STOP:' "$(console t8 t8-f-smoke)") / $(grep -c '^TEST STATUS' "$(console t8 t8-f-smoke)")" "0 / 0"
        note "the row's keys: t8_smoke=$(row_key t8 t8_smoke); the step's record: $(grep '^step_done=t8-f-smoke' "$EGW_G3_STATE/row-t8.env")"
        # O3 of 2026-10-05: the classification is now a halt of its own (classify_invalid)
        classify_invalid t8
        t9_refused
        close_ok
        ;;
    s8a)
        setup short 1 0
        echo 0000000000000000000000000000000000000000000000000000000000000000 > "$B/sha.kernel"
        echo "EXPECTED: the kernel's sha256 is not the recorded one: 'open S3' halts at the identities, nothing is started, no session is recorded."
        run open S3
        want_rc 1 "open S3 (a halt)"
        want "the halt of open" '^HALT: kernel \(.*Image-qemuarm64\.bin\) is 0{64}, the recorded identity is 4457ef38e4cb6b8c2f0061ec504a23666490781ca3b4facd15a588b7a9609037 \(packet section 4, halt 6\); nothing was started'
        is "session state file written" "$([ -e "$EGW_G3_STATE/session-S3.env" ] && echo yes || echo no)" no
        is "an open session (current_session)" "$([ -e "$EGW_EXEC/current_session" ] && echo yes || echo no)" no
        is "a fake QEMU process was started" "$([ -e "$B/qemu.pids.all" ] && echo yes || echo no)" no
        is "attempts created" "$(ls "$EGW_ATTEMPTS" | grep -c -v '^20261003T142310Z_g3-qualification-t8_attempt01$')" 0
        ;;
    s8b)
        setup short 1 0
        sed -i 's/image_id=sha256:9a293fe1/image_id=sha256:0a293fe1/' "$B/gate.identities"
        echo "EXPECTED: the gate driver's record of the running images differs from S2's in the controller's image id: 'open S3' passes (the record is compared before row t8), 'row t8' halts before any attempt exists; 'row t9' refused."
        open_s3
        run row t8
        want_rc 1 "row t8 (a halt before the attempt)"
        want "the halt of row t8" "^HALT: the gate package's record of the running images \(.*container_identities.txt: 6 identity line\(s\)\) differs from S2's .*: row t8 was NOT started and no attempt was created"
        want "the differing line is printed beside S2's" '^  now: identity egw-controller-1 image=egw-controller:0.1.0 image_id=sha256:0a293fe1'
        is "row state file of t8" "$([ -e "$EGW_G3_STATE/row-t8.env" ] && echo exists || echo absent)" absent
        is "attempts of row t8 created" "$(ls -d "$EGW_ATTEMPTS"/*_g3-qualification-t8_attempt02 2> /dev/null | wc -l)" 0
        is "reboot commands sent to the stub guest" "$(reboots)" 0
        run row t9
        want_rc 2 "row t9 (refused)"
        want "row t9 is refused: row t8 is not classified" "^REFUSED: the previous row t8 is 'not started', not classified"
        close_ok
        ;;
    s8c)
        setup short 1 0
        echo "EXPECTED: 'open S3' passes; then the QEMU binary's sha256 is no longer the recorded one: 'row t8' halts at the identities (they are compared again before every row), no attempt is created; 'row t9' refused."
        open_s3
        echo ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff > "$B/sha.qemu"
        note "bench: from here on the stub answers another sha256 for the QEMU binary"
        run row t8
        want_rc 1 "row t8 (a halt before the attempt)"
        want "the halt of row t8" '^HALT: qemu-system-aarch64 \(.*/usr/bin/qemu-system-aarch64\) is f{64}, the recorded identity is 5d389c653449d338397f56b3ffa24fb387ec4aab5cd205b2f1a735aa14391061: row t8 was NOT started and no attempt was created \(packet section 4, halt 6'
        is "row state file of t8" "$([ -e "$EGW_G3_STATE/row-t8.env" ] && echo exists || echo absent)" absent
        is "attempts of row t8 created" "$(ls -d "$EGW_ATTEMPTS"/*_g3-qualification-t8_attempt02 2> /dev/null | wc -l)" 0
        is "reboot commands sent to the stub guest" "$(reboots)" 0
        run row t9
        want_rc 2 "row t9 (refused)"
        want "row t9 is refused: row t8 is not classified" "^REFUSED: the previous row t8 is 'not started', not classified"
        close_ok
        ;;
    s9)
        setup short 1 0
        echo "EXPECTED: 'open S1' and 'open S2' are refused (authority consumed) and write nothing; with a second earlier attempt of row t8 'open S3' halts (NOT FRESH) while the recorded attempt01 is admitted; with an attempt of row t8 that the freshness check does not see (nested in a sealed package) the export tool numbers the new attempt attempt06: 'row t8' halts before any step."
        for l in S1 S2; do
            run open "$l"
            want_rc 2 "open $l (refused)"
            want "open $l is refused: its authority is consumed" "^REFUSED: session $l is a session of the battery of 2026-10-02/03, whose authority is consumed"
        done
        is "state directory after the two refusals" "$([ -e "$EGW_G3_STATE" ] && ls "$EGW_G3_STATE" | tr '\n' ' ' || echo absent)" absent
        mkdir "$EGW_ATTEMPTS/20261004T101010Z_g3-qualification-t8_attempt02"
        note "bench: a second earlier attempt of row t8 is put in the attempts directory"
        run open S3
        want_rc 1 "open S3 with another earlier attempt of row t8 (a halt)"
        want "the other earlier attempt is NOT FRESH" '^NOT FRESH: an earlier attempt of row t8 exists: .*/20261004T101010Z_g3-qualification-t8_attempt02$'
        is "admitted lines for the recorded attempt01 (attempts directory and output root)" "$(grep -c '^admitted: the one earlier attempt of row t8' "$B/last.out")" 2
        want "the halt of open" '^HALT: an id of S3 is not fresh on the host; nothing was started'
        is "session state file written" "$([ -e "$EGW_G3_STATE/session-S3.env" ] && echo yes || echo no)" no
        rmdir "$EGW_ATTEMPTS/20261004T101010Z_g3-qualification-t8_attempt02"
        mkdir -p "$EGW_OUTPUT_TEST/runs/2026-10-03/HIST_bench-sealed-copy/20261003T150000Z_g3-qualification-t8_attempt05"
        note "bench: that attempt is removed; an attempt05 of row t8 is put two levels down in a package of the output root, where the freshness check does not look and the export tool's numbering does"
        open_s3
        run row t8
        want_rc 1 "row t8 (a halt before any step)"
        want "the halt of row t8" "^HALT: row t8: the new attempt is named [0-9TZ]+_g3-qualification-t8_attempt06, which does not end '_g3-qualification-t8_attempt02'"
        want_steps t8 '^$'
        is "reboot commands sent to the stub guest" "$(reboots)" 0
        note "the row's record: attempt_name=$(row_key t8 attempt_name)"
        classify_ok t8 failed not-applicable not-run
        want "row t8 is classified not started" "^row t8: classified 'not started'"
        t9_refused
        close_ok
        ;;
    s10a | s10b | s10c | s10d)
        setup short 1 0
        case $SC in
            s10a) echo "EXPECTED: a line starting with STOP: in the console of (a) (printed by the stub openssl: the real line (a) has no helper call that prints one): (b), (c), (d)+(e) and the exposure step are not run." ;;
            s10b) echo "EXPECTED: the bounded broker log of (b) cannot be read: (b) prints its STOP:; (c), (d)+(e) and the exposure step are not run." ;;
            s10c) echo "EXPECTED: the bounded broker log of (c) cannot be read: (c) prints its STOP:; (d)+(e) and the exposure step are not run." ;;
            s10d) echo "EXPECTED: the ACL probe ends 1: (d)+(e) prints its STOP:; the exposure step is not run." ;;
        esac
        open_s3
        t8_ok
        classify_ok t8 finished valid pass
        want_rc 0 "classify t8"
        t9_refuses
        case $SC in
            s10a) st bench_openssl_stop; t9steps='t9-a'; first=t9-a; next=t9-b ;;
            s10b) st fetch_broker_rc 1; t9steps='t9-a t9-b'; first=t9-b; next=t9-c ;;
            s10c) printf '%s\n' '# BENCH: from the simulator call of (c) on, the bounded read of the broker log fails' 'echo 1 > "$EGW_STUB_STATE/fetch_broker_rc"' > "$EGW_STUB_STATE/bench_hook.sim.itest-notls-q2"; t9steps='t9-a t9-b t9-c'; first=t9-c; next=t9-de ;;
            s10d) st bench_probe_rc 1; t9steps='t9-a t9-b t9-c t9-de'; first=t9-de; next=t9-exposure ;;
        esac
        run row t9
        want_rc 0 "row t9 (its later steps are not run; the row itself records no halt)"
        want_steps t9 "^guest-state-before $t9steps guest-state-after guest-state-delta gate-healthy gate-units gate-tunnel-check\$"
        want "the script says which steps were not run" "^## .* row t9: step $first printed STOP: \(or left no console\): $next and every later step were NOT run"
        note "STOP: lines of step $first: $(grep -h '^STOP:' "$(console t9 "$first")" | cut -c1-200 | tr '\n' '|')"
        want "a line starting with STOP: in the console of $first" '^STOP:' "$(console t9 "$first")"
        is "the exposure step was run" "$([ -n "$(console t9 t9-exposure)" ] && echo yes || echo no)" no
        note "the row's record: $(grep '^step_not_run=' "$EGW_G3_STATE/row-t9.env")"
        classify_ok t9 failed valid fail
        close_ok
        ;;
    s11 | s11b)
        setup short 1 0
        if [ "$SC" = s11 ]; then
            st guest_never_answers
            echo "EXPECTED: during the wait (every poll refused at once, one every 3 s) 'term t8' sends TERM, never KILL, to the row's process group; the row's own trap finishes its attempt 'interrupted' and exports it; the fake QEMU process is untouched; then the guest answers again and 'close' closes the session."
        else
            st guest_down_calls 0
            st boot_id_stall_always
            echo "OBSERVED CASE (no fixed expectation for what is left running): 'term t8' while a poll is in flight - a read that stalls under its 20 s timeout, in a process group of its own. Expected: TERM reaches the row, the attempt is finished 'interrupted' and exported, the fake QEMU is untouched; the poll in flight is not reached by TERM and ends by its own timeout."
        fi
        open_s3
        say "g3_battery.sh row t8 (detached, in a session of its own, as the launcher starts it)"
        setsid bash "$G" row t8 < /dev/null > "$B/row.out" 2>&1 &
        rowpid=$!
        for _ in $(seq 1 240); do
            a=$(attempt_of t8)
            [ -n "$a" ] && [ "$(ls "$a"/console/*-t8-wait-ssh.stdout.txt 2> /dev/null | wc -l)" -ge "$([ "$SC" = s11 ] && echo 2 || echo 1)" ] && break
            /usr/bin/sleep 0.5
        done
        [ "$SC" = s11 ] || /usr/bin/sleep 4
        note "the row is in its wait: step '$(row_key t8 step)', $(ls "$(attempt_of t8)"/console/*-t8-wait-ssh.stdout.txt 2> /dev/null | wc -l) poll(s) so far; the row's process group: $(row_key t8 pgid) (the row's pid: $rowpid)"
        status_now
        note "members of the row's process group before TERM: $(/usr/bin/pgrep -g "$(row_key t8 pgid)" -a | cut -c1-70 | tr '\n' '|')"
        note "processes of the bench outside that group (a poll under 'timeout' is in a group of its own): $(/usr/bin/pgrep -af "$B/" | grep -v qemu-system-aarch64 | awk '{print $1}' | while read -r p; do [ "$(ps -o pgid= -p "$p" 2> /dev/null | tr -d ' ')" = "$(row_key t8 pgid)" ] || ps -o pid=,pgid=,args= -p "$p" 2> /dev/null | cut -c1-90; done | tr '\n' '|')"
        t_term=$(cut -d' ' -f1 /proc/uptime)
        run term t8
        want_rc 0 "term t8"
        want "TERM is sent to the row's process group, and KILL never" "^TERM sent to the process group $(row_key t8 pgid) \(exit 0\)\. KILL is never sent\."
        wait "$rowpid"
        RC=$?
        t_end=$(cut -d' ' -f1 /proc/uptime)
        say "the row's own console after TERM"
        echo "-> exit $RC (the row ended $(echo "$t_end $t_term" | awk '{printf "%.1f", $1 - $2}') s after 'term' was issued)"
        keep < "$B/row.out" | tail -n 12
        want_rc 130 "row t8 after TERM (interrupted)"
        want "the row's trap ran" '^## .* row t8: interrupted by a signal' "$B/row.out"
        want "the attempt is finished interrupted and exported (the export tool's own verification)" "^row t8: attempt finished 'interrupted'; driver code 130; export: verified" "$B/row.out"
        is "the row's state" "$(row_key t8 state)" interrupted
        is "the attempt's own status" "$("$REAL_PY" -c 'import json,sys; print(json.load(open(sys.argv[1]))["status"])' "$(attempt_of t8)/attempt.json")" interrupted
        is "the exported package exists under the bench's output root" "$(ls -d "$EGW_OUTPUT_TEST"/runs/*/"$(row_key t8 attempt_name)" 2> /dev/null | wc -l)" 1
        is "the fake QEMU process after TERM" "$(qemu_state)" "$Q0"
        want_no "no line b ran" 't8-b-wait-boot-id' <(steps_of "$(attempt_of t8)")
        echo "recorded steps of row t8, in order: $(steps_of "$(attempt_of t8)")"
        note "processes of the bench right after the row ended (the fake QEMU aside): $(/usr/bin/pgrep -af "$B/" | grep -v qemu-system-aarch64 | cut -c1-110 | tr '\n' '|')"
        if [ "$SC" = s11b ]; then
            note "the poll in flight: commands.jsonl holds $(grep -c '"name": "t8-wait-ssh"' "$(attempt_of t8)/commands.jsonl") record(s) of t8-wait-ssh for $(ls "$(attempt_of t8)"/console/*-t8-wait-ssh.stdout.txt | wc -l) console file(s)"
            note "the attempt's validity and capture failures after the export: $("$REAL_PY" -c 'import json,sys; d=json.load(open(sys.argv[1])); print("validity=%s outcome=%s capture_failures=%s" % (d.get("validity"), d.get("outcome"), json.dumps(d.get("capture_failures"))[:300]))' "$(attempt_of t8)/attempt.json")"
            /usr/bin/sleep 22
            note "22 s later: processes of the bench (the fake QEMU aside): $(/usr/bin/pgrep -af "$B/" | grep -v qemu-system-aarch64 | cut -c1-110 | tr '\n' '|')"
            is "processes of the bench left 22 s after the row ended (the fake QEMU aside)" "$(/usr/bin/pgrep -af "$B/" | grep -c -v qemu-system-aarch64)" 0
        fi
        sent_to_guest
        rm -f "$EGW_STUB_STATE/guest_never_answers" "$EGW_STUB_STATE/boot_id_stall_always"
        note "bench: the stub guest answers again"
        run row t9
        want_rc 2 "row t9 after the interrupted row t8 (refused)"
        want "row t9 is refused because of the recorded halt" '^REFUSED: NOT STARTED: session S3 has a recorded halt'
        close_ok
        status_now
        ;;
    s13)
        setup short 1 0
        st rec_same_rc 4
        echo "EXPECTED (O1 of 2026-10-05): row t8 halts in its steps (the twins differ: step e prints STOP:); the row is classified with a class that records no halt of its own (failed valid fail); then 'row t9' is run WITH EGW_G3_RUI_GO set to some words: REFUSED, exit 2, 'NOT STARTED: session S3 has a recorded halt', the words are not taken as a go and not recorded, no attempt of row t9 is created. (Before the bounded check that variable let the row start.)"
        open_s3
        t8_halted '^HALT: row t8: step e printed STOP: ' \
            '^guest-state-before t8-qemu-before t8-a-reboot t8-wait-ssh x3 t8-qemu-after t8-b-wait-boot-id t8-c-unaided t8-d-tunnel t8-tunnel-check t8-e-state t8-previous-boot-journal t8-previous-boot-oom guest-state-after gate-healthy gate-units gate-tunnel-check$'
        want "step e's own STOP: line" '^STOP: test 8: persistence across the reboot NOT verified' "$(console t8 t8-e-state)"
        is "simulator calls (the smoke was not started)" "$(grep -c -- '-m egw_simulator' "$EGW_STUB_STATE/calls.log")" 0
        is "halts recorded for the session after row t8" "$(halts)" 1
        classify_ok t8 failed valid fail
        want_rc 0 "classify t8 (a class that records no halt of its own)"
        want "classify names 'close' as the next step" "^Next: 'close', then hand back to Rui: session S3 has a recorded halt"
        is "halts recorded for the session after classify" "$(halts)" 1
        export EGW_G3_RUI_GO="bench words standing for an explicit go of Rui to run T9 after the halt"
        note "bench: EGW_G3_RUI_GO is set, and exported, for the next invocation: '$EGW_G3_RUI_GO'"
        t9_refused '\(up=[0-9]+ row=t8 row t8: step e printed STOP: '
        unset EGW_G3_RUI_GO
        want "the refusal says what follows a halt in S3" "In S3 a halt ends the session \(decision summary, choice 2; request, section 5\): classify the row if it awaits classification, then 'close', then hand back to Rui"
        want_no "the variable is not taken as a go" 'EGW_G3_RUI_GO is set and is recorded'
        is "row t9's state file" "$([ -e "$EGW_G3_STATE/row-t9.env" ] && echo exists || echo absent)" absent
        is "files of the state directory that hold the words" "$(grep -rl 'standing for an explicit go' "$EGW_G3_STATE" 2> /dev/null | wc -l)" 0
        is "simulator calls of test 9" "$(grep -c -- '-m egw_simulator.*itest-\(tls-wrongca\|auth-wrongpw\|notls\)-q2' "$EGW_STUB_STATE/calls.log")" 0
        close_ok
        ;;
    s14 | s15)
        setup short 1 0
        if [ "$SC" = s14 ]; then
            step=t8-e-state
            hook_exec "$step" "after the check that follows step d (t8-tunnel-check found it) and before step e"
            halt_re='^HALT: row t8: the preamble of hx reopened a lost tunnel before step e \(TUNNEL UP in its console; request, section 5, items 7 and 9\): step f was NOT run, and T9 is not run'
            steps='^guest-state-before t8-qemu-before t8-a-reboot t8-wait-ssh x3 t8-qemu-after t8-b-wait-boot-id t8-c-unaided t8-d-tunnel t8-tunnel-check t8-e-state t8-previous-boot-journal t8-previous-boot-oom guest-state-after gate-healthy gate-units gate-tunnel-check$'
            refused_re='\(up=[0-9]+ row=t8 row t8: the preamble of hx reopened a lost tunnel before step e '
            echo "EXPECTED (O2 b of 2026-10-05): the host's tunnel master ends after the check that follows step d and before step e: the preamble of step e reopens it and prints TUNNEL UP; HALT naming step e, step f (the smoke) not run; the gate finds the tunnel up again; 'row t9' refused, quoting that halt."
        else
            step=t8-f-smoke
            hook_exec "$step" "after step e and before step f"
            halt_re='^HALT: row t8: the preamble of hx reopened a lost tunnel before step f \(TUNNEL UP in its console; request, section 5, items 7 and 9\): T9 is not run; the row is classified by what its consoles show'
            steps=$T8_ALL
            refused_re='\(up=[0-9]+ row=t8 row t8: the preamble of hx reopened a lost tunnel before step f '
            echo "EXPECTED (O2 b of 2026-10-05): the host's tunnel master ends after step e and before step f: the preamble of step f reopens it and prints TUNNEL UP; HALT naming step f; 'row t9' refused, quoting that halt. The preamble runs in the step's own shell BEFORE the step's line, so the smoke itself runs on the reopened tunnel: what ran is shown (the script reads the console after the step)."
        fi
        open_s3
        t8_halted "$halt_re" "$steps"
        hook_ran "$step"
        want "the check after step d found the master up (it ended after that check)" '^TUNNEL CHECK: the master answers' "$(console t8 t8-tunnel-check)"
        reopened_in t8 "$step"
        is "lines starting with STOP: in the console of $step" "$(grep -c '^STOP:' "$(console t8 "$step")")" 0
        if [ "$SC" = s14 ]; then
            want_no "no TUNNEL UP in the console of step d's check" '^TUNNEL UP$' "$(console t8 t8-tunnel-check)"
            note "what of step e ran after its preamble: $(grep -E '^(CONTROLLER PROCESS NEW|STOP:|TUNNEL)' "$(console t8 t8-e-state)" | cut -c1-120 | tr '\n' '|')"
            is "simulator calls (the smoke, step f, was not started)" "$(grep -c -- '-m egw_simulator' "$EGW_STUB_STATE/calls.log")" 0
        else
            want_no "no TUNNEL UP in the console of step e (the master was up then)" '^TUNNEL UP$' "$(console t8 t8-e-state)"
            n=$(sim_calls "$SMOKE")
            if [ "${n:-0}" -ge 1 ]; then ok "what ran: the smoke's simulator was started $n time(s), after the preamble, in the step's own shell"; else bad "the smoke's simulator was not started ($n calls): the preamble and the step's line are not what this scenario assumes"; fi
            want "what ran: the smoke's line printed its status line" "^TEST STATUS $SMOKE: simulator exit=0 transcript \(tee\) exit=0 post=0 -> PROCEDURE COMPLETE\." "$(console t8 t8-f-smoke)"
            want_no "the script's no-halt line for the smoke is not printed" "^row t8: step f shows 'TEST STATUS"
            is "the row's t8_smoke" "$(row_key t8 t8_smoke)" "halt: the preamble of hx reopened a lost tunnel before the smoke"
            note "the row's t8_reached_smoke: $(row_key t8 t8_reached_smoke | cut -c1-70)..."
        fi
        want_no "the gate found no lost tunnel (the preamble of $step had reopened it)" '^NOTE: the tunnel was DOWN after the row'
        want "the gate of row t8 passed: the halt is the step's alone" '^## .* GATE t8: pass'
        is "halts recorded for the session after row t8" "$(halts)" 1
        classify_ok t8 failed unknown inconclusive
        want_rc 0 "classify t8 (a class that records no halt of its own)"
        is "halts recorded for the session after classify" "$(halts)" 1
        t9_refused "$refused_re"
        close_ok
        ;;
    s16)
        setup short 1 0
        echo "EXPECTED (O2 c of 2026-10-05): row t8 completes and passes its gate and is classified pass; in row t9 the host's tunnel master ends after (a) and before (b): the preamble of (b) reopens it and prints TUNNEL UP; HALT naming t9-b; (c), (d)+(e) and the exposure step are not run."
        open_s3
        t8_ok
        classify_ok t8 finished valid pass
        want_rc 0 "classify t8"
        t9_refuses
        hook_exec t9-b "after step t9-a and before step t9-b"
        run row t9
        want_rc 1 "row t9 (a halt)"
        want "the halt of row t9" '^HALT: row t9: the preamble of hx reopened a lost tunnel before step t9-b \(TUNNEL UP in its console; request, section 5, items 7 and 9\): every later step of T9 was NOT run'
        want_steps t9 '^guest-state-before t9-a t9-b guest-state-after guest-state-delta gate-healthy gate-units gate-tunnel-check$'
        hook_ran t9-b
        want_no "no TUNNEL UP in the console of t9-a (the master was up then)" '^TUNNEL UP$' "$(console t9 t9-a)"
        reopened_in t9 t9-b
        is "simulator calls of (c), itest-notls-q2 ((c) was not run)" "$(sim_calls itest-notls-q2)" 0
        is "ACL probe calls ((d)+(e) was not run)" "$(grep -c 'probe-acl.sh' "$EGW_STUB_STATE/ssh.log")" 0
        is "the exposure step was run" "$([ -n "$(console t9 t9-exposure)" ] && echo yes || echo no)" no
        want_no "the halt is not the rule for a STOP: (no step_not_run line)" '^step_not_run=' "$EGW_G3_STATE/row-t9.env"
        want_no "the gate found no lost tunnel (the preamble of t9-b had reopened it)" '^NOTE: the tunnel was DOWN after the row'
        want "the gate of row t9 passed: the halt is the step's alone" '^## .* GATE t9: pass'
        want "the row ends with the halt's next steps" "^HALT recorded for session S3: classify this row, then 'close'"
        is "halts recorded for the session" "$(halts)" 1
        classify_ok t9 failed unknown inconclusive
        want_rc 0 "classify t9"
        close_ok
        ;;
    s17)
        setup short 1 0
        hook_exec t8-previous-boot-journal "after step f, the last step of T8, and before the evidence reads and the gate"
        echo "EXPECTED (O2 a of 2026-10-05): row t8 runs a to f with every marker and no halt in its steps; then the host's tunnel master ends, and the first hx after it is the gate's tunnel check, whose preamble reopens it (TUNNEL UP): the gate says so and does NOT pass, a halt is recorded; 'row t9' refused, quoting the gate's halt. (Before the bounded check this gave 'GATE t8: pass' with a NOTE.)"
        open_s3
        run row t8
        want_rc 1 "row t8 (a halt: its gate)"
        want_no "no halt in the steps of row t8" '^HALT: row t8: (step|the preamble|the qemu|reboot|poll|-no-reboot|one qemu|the session|the host)'
        want_steps t8 "$T8_ALL"
        t8_markers
        want "the smoke's rule records no halt" "^row t8: step f shows 'TEST STATUS $SMOKE: \.\.\. -> PROCEDURE COMPLETE' and no STOP: - this script records no halt for the smoke"
        hook_ran t8-previous-boot-journal
        want_no "no TUNNEL UP in the console of step f (the master was up then)" '^TUNNEL UP$' "$(console t8 t8-f-smoke)"
        reopened_in t8 gate-tunnel-check
        want "the gate's check itself then answered" '^TUNNEL CHECK: the master answers' "$(console t8 gate-tunnel-check)"
        want "the gate says the tunnel was found down and reopened" "^NOTE: the tunnel was DOWN after the row and the preamble of hx reopened it \(TUNNEL UP in the gate's console\): a restoration, and in S3 a halt"
        want "the gate did NOT pass, and that is the halt" '^HALT: row t8: the gate did NOT pass \(packet section 4, halt 3\): the tunnel was found down after the row and reopened by the preamble of hx \(request, section 5, items 7 and 9\); $'
        want_no "no 'GATE t8: pass'" '^## .* GATE t8: pass'
        is "the row's gate" "$(row_key t8 gate | sed 's/ *$//')" "failed: the tunnel was found down after the row and reopened by the preamble of hx (request, section 5, items 7 and 9);"
        is "the row's gate_tunnel" "$(row_key t8 gate_tunnel)" "found down after the row and reopened by the preamble of hx"
        is "halts recorded for the session" "$(halts)" 1
        is "the fake QEMU process after the row" "$(qemu_state)" "$Q0"
        sent_to_guest
        classify_ok t8 failed unknown inconclusive
        want_rc 0 "classify t8 (a class that records no halt of its own)"
        want "classify says the gate did not pass" "^NOTE: this row's gate did not pass \(failed: the tunnel was found down after the row"
        want "classify names 'close' as the next step" "^Next: 'close', then hand back to Rui"
        t9_refused '\(up=[0-9]+ row=t8 row t8: the gate did NOT pass \(packet section 4, halt 3\): the tunnel was found down after the row'
        close_ok
        ;;
    s18)
        setup short 1 0
        echo "EXPECTED (O3 of 2026-10-05): row t8 completes with no halt and its gate passes; the operator classifies it 'failed invalid unknown' (invalid instrumentation): classify records a halt, prints the 'close' next line, and 'row t9' is refused, quoting that halt."
        open_s3
        t8_ok
        is "halts recorded for the session after row t8" "$(halts)" 0
        classify_invalid t8
        want "classify prints the 'close' next line" "^Next: 'close', then hand back to Rui"
        t9_refused '\(up=[0-9]+ row=t8 row t8 is classified invalid instrumentation '
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
