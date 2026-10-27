#!/bin/bash
# Stream OPERATOR: the functions of g3_battery.sh that changed for S3, exercised one at a
# time in the isolated tree made by op_setup.sh (brief, hard rule 2). The script's own
# text is loaded WITHOUT its last line (the dispatch 'main "$@"; exit $?'), so that its
# functions can be called directly; the frozen common.sh, guest_common.sh and
# local_export of the copy record for real, inside the bench.
# Usage (WSL): op_funcs.sh /tmp/g3-s3-op-<name> <test>...
#   polltext  the wait's poll command against the frozen gx
#   wait      the wait before line b (counting rule, bounds, expiry)
#   qemu      the QEMU reading before step a (-no-reboot)
#   markers   steps_t8's rules after steps c and f (fixture consoles, the real row files)
#   steps     the real row files of lines b and c through the real run_step/hx (stub ssh)
#   gate      the gate package's record against S2's
#   fresh     fresh_row and the name of the new attempt
#   ident     verify_candidate with the four added identities
set -u
B=${1:?usage: op_funcs.sh /tmp/g3-s3-op-<name> <test>...}
shift
HERE=$(cd "$(dirname "$0")" && pwd)
# shellcheck source=/dev/null
. "$HERE/op_env.sh"
OT="/mnt/c/Users/ruimf/Documents/Projeto Mestrado/output_test"
echo "## $(date -u +%Y-%m-%dT%H:%M:%SZ) script under test: <scratchpad>/${G#"$S"/} sha256 $(/usr/bin/sha256sum "$G" | cut -d' ' -f1)"
[ "$(tail -n 1 "$G")" = 'main "$@"; exit $?' ] || { echo "the last line of the script is not its dispatch: nothing was loaded"; exit 1; }

# The session the frozen guest_common.sh names at load time: a directory of the bench with
# the frozen ssh helpers, and a boot that is recorded as still running.
SES=$B/egw-exec/attempts/00000000T000000Z_guest-session_bench
mkdir -p "$SES/scripts" "$SES/boot" "$B/state"
cp "$B/repo/tools/session/guest/session_common.sh" "$SES/scripts/session_common.sh"
echo s1 > "$SES/.current_run"
echo "$SES" > "$B/egw-exec/current_session"

LIB=$B/g3_battery.lib.sh
head -n -1 "$G" > "$LIB"
TESTS=("$@")
set --
# shellcheck source=/dev/null
. "$LIB"
PY3=$EGW_EXEC_VENV/bin/python

OLD_ID=11111111-1111-4111-8111-111111111111
NEW_ID=22222222-2222-4222-8222-222222222222

mk_row() {   # mk_row NAME: a fresh attempt and a row state file of its own
    A=$(new_attempt "G3 qualification t8" official) || { echo "the attempt could not be created"; exit 1; }
    ROW_SLUG=t8
    ROW_FILE=$STATE/row-t8.$1.env
    : > "$ROW_FILE"
    row_set start_up "$(up_now)"
    row_set ceiling_min 135
    HALTED=0
    SESSION_FILE=""
}

commands() {   # the attempt's recorded steps: name, the first words of the argv, exit, duration
    "$PY3" - "$A/commands.jsonl" << 'EOF'
import json, sys
for line in open(sys.argv[1]):
    r = json.loads(line)
    argv = r["argv"]
    head = " ".join(argv[:5]) if argv and argv[0] == "timeout" else argv[0]
    print("  step %03d %-14s exit=%-4s %6.1f s  argv: %s ..." % (r["seq"], r["name"], r["exit_code"], r["duration_s"], head))
EOF
}

left_over() { echo "  stub ssh processes left: $(/usr/bin/pgrep -f "$B/stubs/ssh" | wc -l); 'sleep 300' left: $(/usr/bin/pgrep -fx 'sleep 300' | wc -l)"; }

t_polltext() {
    local frozen
    echo; echo "######## polltext: T8_POLL_SH against gx of the frozen guest_common.sh"
    frozen=$(sed -n '/^gx() {$/,/^}$/p' "$EGW_EXEC_REPO/tools/session/guest_common.sh")
    case $frozen in
        *"ex \"\$a\" \"\$name\" env E=\"\$SESSION\" bash -c '$T8_POLL_SH' _ \"\$1\""*) echo "PASS: gx records  env E=\"\$SESSION\" bash -c '<T8_POLL_SH>' _ \"\$1\"  - the poll's text is gx's, character for character" ;;
        *) echo "FAIL: the poll's text is not the text gx records" ;;
    esac
    echo "guest_common.sh sha256: $(/usr/bin/sha256sum "$EGW_EXEC_REPO/tools/session/guest_common.sh" | cut -d' ' -f1); session_common.sh: $(/usr/bin/sha256sum "$EGW_EXEC_REPO/tools/session/guest/session_common.sh" | cut -d' ' -f1)"
}

one_wait() {   # one_wait NAME WAIT POLL READ PRE GUEST_ID DEFAULT_MODE SEQ...
    local name=$1 w=$2 p=$3 r=$4 pre=$5 gid=$6 mode=$7 t0 rc
    shift 7
    echo; echo "#### wait/$name: budget $w s, a poll every $p s, each read at most $r s; saved id '${pre}'; the guest's id $gid; ssh: ${*:-} then $mode"
    T8_SSH_WAIT_S=$w
    T8_SSH_POLL_S=$p
    T8_SSH_READ_S=$r
    printf '%s\n' "$gid" > "$B/guest/boot_id"
    printf '%s\n' "$mode" > "$B/ssh.mode"
    : > "$B/ssh.seq"
    [ "$#" -eq 0 ] || printf '%s\n' "$@" > "$B/ssh.seq"
    mk_row "wait-$name"
    T8_WAIT_WHY=""
    t0=$(up_now)
    t8_wait_ssh "$pre" "$t0"
    rc=$?
    echo "-> t8_wait_ssh returned $rc after $(($(up_now) - t0)) s; T8_WAIT_WHY: ${T8_WAIT_WHY:-<empty>}"
    echo "-> the row's state file: $(grep -E '^(t8_|step=|start_up=|ceiling_min=)' "$ROW_FILE" | tr '\n' ';')"
    commands
    left_over
}

t_wait() {
    echo; echo "######## wait: t8_wait_ssh"
    one_wait printed-then-124 60 2 4 "$OLD_ID" "$NEW_ID" ok print-then-hang ok
    one_wait printed-then-255 60 2 4 "$OLD_ID" "$NEW_ID" ok print-then-255 ok
    one_wait old-id-expiry 15 3 4 "$OLD_ID" "$OLD_ID" ok
    one_wait refuse-expiry 12 5 20 "$OLD_ID" "$NEW_ID" refuse
    one_wait not-an-id 60 1 4 "$OLD_ID" "$NEW_ID" ok banner two-lines ok
    one_wait saved-id-empty 30 2 4 "" "$NEW_ID" ok
    echo; echo "#### wait/helpers-missing: the session's ssh helpers cannot be loaded (97)"
    mv "$SES/scripts/session_common.sh" "$SES/scripts/session_common.sh.away"
    one_wait helpers-missing 5 2 4 "$OLD_ID" "$NEW_ID" ok
    mv "$SES/scripts/session_common.sh.away" "$SES/scripts/session_common.sh"
    echo; echo "#### wait/capture-lost: ex answers 74 (the frozen ex replaced by a function that returns 74)"
    (
        ex() { return 74; }
        T8_SSH_WAIT_S=30; T8_SSH_POLL_S=2; T8_SSH_READ_S=4
        mk_row wait-capture-lost
        t8_wait_ssh "$OLD_ID" "$(up_now)"
        echo "-> t8_wait_ssh returned $? ; T8_WAIT_WHY: $T8_WAIT_WHY"
    )
}

t_wait20() {
    echo; echo "######## wait20: the script's own 20 s read bound and 10 s poll, budget 45 s, an ssh that stalls"
    one_wait stall-remainder 45 10 20 "$OLD_ID" "$NEW_ID" hang
}

qemu_case() {   # qemu_case NAME [extra argv of the fake process...]
    local name=$1 rc pid
    shift
    bash "$B/stubs/fake_qemu_start.sh" "$@"
    sleep 0.3
    pid=$(cat "$B/qemu.pid")
    echo "--- qemu/$name: fake process $pid, extra arguments: ${*:-<none>}"
    bash -c "$T8_QEMU_IDENT" _ before "$QEMU_EXE_RE" | cut -c1-330
    rc=${PIPESTATUS[0]}
    echo "-> exit $rc; the fake process is $([ -d "/proc/$pid" ] && echo 'still running (not signalled)' || echo GONE)"
    kill "$pid" 2> /dev/null
}

t_qemu() {
    local rc pid
    echo; echo "######## qemu: T8_QEMU_IDENT 'before' (the command line read for -no-reboot)"
    qemu_case plain
    qemu_case no-reboot -no-reboot
    qemu_case double-dash --no-reboot
    qemu_case action-reboot-shutdown -action reboot=shutdown
    qemu_case action-list -action panic=none,reboot=shutdown
    qemu_case action-other -action panic=pause-on-panic -name guest=no-reboot-is-only-a-name
    echo "--- qemu/none: no process"
    rm -f "$B/qemu.pid"
    bash -c "$T8_QEMU_IDENT" _ before "$QEMU_EXE_RE" | cut -c1-200
    echo "-> exit ${PIPESTATUS[0]}"
    echo "--- qemu/through-t8_qemu: the recorded step (real ex), with -no-reboot, then without, then 'after'"
    mk_row qemu
    bash "$B/stubs/fake_qemu_start.sh" -no-reboot; sleep 0.3; pid=$(cat "$B/qemu.pid")
    t8_qemu before > /dev/null; rc=$?
    echo "-> t8_qemu before returned $rc; row key: $(grep '^t8_qemu_before=' "$ROW_FILE")"
    kill "$pid" 2> /dev/null
    bash "$B/stubs/fake_qemu_start.sh"; sleep 0.3; pid=$(cat "$B/qemu.pid")
    t8_qemu before > /dev/null; rc=$?
    echo "-> t8_qemu before returned $rc; row key: $(grep '^t8_qemu_before=' "$ROW_FILE" | cut -c1-200)"
    t8_qemu after | grep -E '^(QEMU PROCESS UNCHANGED|STOP)' | cut -c1-120; rc=${PIPESTATUS[0]}
    echo "-> t8_qemu after returned $rc; row key: $(grep '^t8_qemu_after=' "$ROW_FILE")"
    kill "$pid" 2> /dev/null
    commands
}

rows_into_attempt() {
    local f
    for f in t8-a-reboot t8-b-wait-boot-id t8-c-unaided t8-d-tunnel t8-e-state t8-f-smoke; do
        cp "$ROWS_DIR/$f.sh" "$A/environment/$f.sh" || { echo "the row file $ROWS_DIR/$f.sh is not there"; exit 1; }
    done
}

markers_case() {   # markers_case NAME C_FIXTURE F_FIXTURE
    local name=$1 cfix=$2 ffix=$3
    echo; echo "#### markers/$name: step c fixture '$cfix', step f fixture '$ffix'"
    (
        mk_row "markers-$name"
        rows_into_attempt
        printf '%s\n' "$OLD_ID" > "$P/$T8_PREFIX.boot_id.pre"
        n=0
        run_step() {
            local step=$1 src
            n=$((n + 1))
            case $step in
                t8-c-unaided) src=$B/fix/c.$cfix ;;
                t8-f-smoke) src=$B/fix/f.$ffix ;;
                *) src=$B/fix/$step.ok ;;
            esac
            # the console of a step under 'set -v': the row file's own text, then what it printed
            { cat "$A/environment/$step.sh"; cat "$src"; } > "$A/console/$(printf '%03d' "$n")-$step.stdout.txt"
            echo "[fixture] step $step ran${2:+ with $2}"
            return 0
        }
        t8_qemu() { return 0; }
        t8_wait_ssh() { return 0; }
        ex() { return 0; }
        steps_t8 > "$B/markers.out.txt" 2>&1      # not through a pipe: HALTED must stay in this shell
        cut -c1-420 "$B/markers.out.txt"
        echo "-> HALTED=$HALTED; t8 keys: $(grep -E '^t8_(reached_smoke|smoke)=' "$ROW_FILE" | cut -c1-150 | tr '\n' ';')"
        rm -f "$P/$T8_PREFIX.boot_id.pre"
    )
}

t_markers() {
    echo; echo "######## markers: the rules after step c (point 7) and step f (point 8), real row files from <scratchpad>/${ROWS_DIR#"$SCR"/}"
    for f in t8-a-reboot t8-b-wait-boot-id t8-c-unaided t8-d-tunnel t8-e-state t8-f-smoke; do
        echo "row file $f.sh: sha256 $(/usr/bin/sha256sum "$ROWS_DIR/$f.sh" | cut -d' ' -f1); lines holding 'STOP:': $(grep -c 'STOP:' "$ROWS_DIR/$f.sh")"
    done
    printf 'reboot command sent (status not tested) 2026-10-04T00:00:00Z: boot id %s, 6 running container ids, 35 event directory names and /var/lib/docker on /dev/vdb saved\n' "$OLD_ID" > "$B/fix/t8-a-reboot.ok"
    printf 'REBOOT SHOWN: boot id %s -> %s (read 1 of at most 90, 10 s apart, each bounded to 20 s)\n' "$OLD_ID" "$NEW_ID" > "$B/fix/t8-b-wait-boot-id.ok"
    printf 'TUNNEL CLOSED\nTUNNEL UP\n' > "$B/fix/t8-d-tunnel.ok"
    printf 'CONTROLLER PROCESS NEW: started_at 2026-10-04T00:00:00.000Z -> 2026-10-04T00:05:00.000Z\n' > "$B/fix/t8-e-state.ok"
    printf 'CONTAINERS RETURNED UNAIDED: the 6 container ids saved before the reboot are listed running again (read 3 of at most 90, 10 s apart, each bounded to 20 s; these lines started nothing)\nPERSISTENCE SHOWN: 35 event directories intact; /var/lib/docker on /dev/vdb\nrunning\nobservations read, exit 0 (not a judgement: the set, the directories and the mount source above are)\n' > "$B/fix/c.both"
    printf 'CONTAINERS RETURNED UNAIDED: the 6 container ids saved before the reboot are listed running again (read 3 of at most 90, 10 s apart, each bounded to 20 s; these lines started nothing)\nSTOP: test 8: persistence NOT shown - a judged read did NOT end with exit status 0 (the event directories read: exit 124; the mount source read: exit 0)\n' > "$B/fix/c.containers-then-stop"
    printf 'CONTAINERS RETURNED UNAIDED: the 6 container ids saved before the reboot are listed running again (read 3 of at most 90)\n' > "$B/fix/c.containers-only"
    printf 'PERSISTENCE SHOWN: 35 event directories intact; /var/lib/docker on /dev/vdb\n' > "$B/fix/c.persistence-only"
    : > "$B/fix/c.echo-only"
    printf '{\n  "lost": 0,\n  "late_confirmations": 0,\n}\nTEST STATUS itest-post-reboot-01-q2: simulator exit=0 transcript (tee) exit=0 post=0 -> PROCEDURE COMPLETE. This is NOT the verdict: compare the values printed above with the test'"'"'s Expected list.\n' > "$B/fix/f.complete"
    printf '{\n  "lost": 3,\n  "late_confirmations": 41,\n}\nTEST STATUS itest-post-reboot-01-q2: simulator exit=0 transcript (tee) exit=0 post=0 -> PROCEDURE COMPLETE. This is NOT the verdict: compare the values printed above with the test'"'"'s Expected list.\n' > "$B/fix/f.complete-lost-late"
    printf 'STOP: finish itest-post-reboot-01-q2: check exit=0 (3 = not a protocol check) delta exit=4 (4 = MISMATCH or queue not empty)\nSTOP: TEST STATUS itest-post-reboot-01-q2: simulator exit=0 transcript (tee) exit=0 post=1 -> FAILED (a transcript exit other than 0, or an empty itest-post-reboot-01-q2.stderr.txt, means that the evidence of this run is incomplete). Do not start another run before the cause is understood.\n' > "$B/fix/f.stop"
    printf 'TEST STATUS itest-post-reboot-01-q2: simulator exit=0 transcript (tee) exit=0 post=0 -> PROCEDURE COMPLETE. This is NOT the verdict.\nSTOP: a later line of the same console\n' > "$B/fix/f.complete-and-stop"
    printf '{\n  "lost": 0\n}\n' > "$B/fix/f.neither"
    printf 'TEST STATUS itest-post-reboot-01: simulator exit=0 transcript (tee) exit=0 post=0 -> PROCEDURE COMPLETE. This is NOT the verdict.\n' > "$B/fix/f.complete-other-id"
    markers_case c-both-f-complete both complete
    markers_case c-containers-then-stop containers-then-stop complete
    markers_case c-containers-only containers-only complete
    markers_case c-persistence-only persistence-only complete
    markers_case c-echo-only echo-only complete
    markers_case f-complete-lost-late both complete-lost-late
    markers_case f-stop both stop
    markers_case f-complete-and-stop both complete-and-stop
    markers_case f-neither both neither
    markers_case f-complete-other-id both complete-other-id
}

t_steps() {
    local f
    echo; echo "######## steps: the real row files of lines b and c through the real run_step and hx (step shell: stdin closed, exec 2>&1, set -v), stub ssh, the host's timeout"
    mk_row steps
    rows_into_attempt
    printf '%s\n' "$OLD_ID" > "$P/$T8_PREFIX.boot_id.pre"
    printf '%s\n' "$NEW_ID" > "$B/guest/boot_id"
    printf 'c0ffee%02d\n' 1 2 3 4 5 6 > "$B/guest/containers"
    cp "$B/guest/containers" "$P/$T8_PREFIX.containers.pre"
    printf 'itest-a\nitest-b\nitest-c\n' > "$B/guest/events"
    cp "$B/guest/events" "$P/$T8_PREFIX.events.pre"
    printf '/dev/vdb\n' > "$B/guest/mount"
    cp "$B/guest/mount" "$P/$T8_PREFIX.docker-mount.pre"
    printf 'ok\n' > "$B/ssh.mode"
    printf 'print-then-hang\n' > "$B/ssh.seq"       # line b's first read prints the new id and stalls: its own 'timeout 20' must end it
    echo "--- line b (the first read stalls after printing the new id; the second answers)"
    run_step t8-b-wait-boot-id T8=rebooting > /dev/null
    f=$(console_of t8-b-wait-boot-id)
    echo "console $f: $(wc -l < "$f") lines"
    grep -n -E '^(REBOOT SHOWN|STOP:|carrier)' "$f" | cut -c1-200
    echo "lines that hold 'REBOOT SHOWN' anywhere: $(grep -c 'REBOOT SHOWN' "$f"); at the start of a line: $(grep -c '^REBOOT SHOWN' "$f")"
    t8_shown t8-b-wait-boot-id '^REBOOT SHOWN: boot id [0-9a-f-]+ -> [0-9a-f-]+' && echo "-> t8_shown for step b: shown, no STOP:" || echo "-> t8_shown for step b: NOT shown"
    echo "--- line c (three judged reads answer, then the observations)"
    run_step t8-c-unaided T8=rebooted > /dev/null
    f=$(console_of t8-c-unaided)
    echo "console $f: $(wc -l < "$f") lines"
    grep -n -E '^(CONTAINERS RETURNED UNAIDED|PERSISTENCE SHOWN|STOP:|carrier|observations read)' "$f" | cut -c1-200
    echo "lines that hold 'PERSISTENCE SHOWN' anywhere: $(grep -c 'PERSISTENCE SHOWN' "$f"); at the start of a line: $(grep -c '^PERSISTENCE SHOWN' "$f")"
    no_stop t8-c-unaided && echo "-> no_stop for step c: no STOP:" || echo "-> no_stop for step c: a STOP: was found"
    echo "--- line c again in a new attempt, the event-directory read ending 124 after printing (its own 'timeout 20')"
    mk_row steps2
    rows_into_attempt
    rm -f "$P/$T8_PREFIX.containers.post" "$P/$T8_PREFIX.events.post" "$P/$T8_PREFIX.docker-mount.post"
    printf 'ok\nprint-then-hang\n' > "$B/ssh.seq"
    run_step t8-c-unaided T8=rebooted > /dev/null
    f=$(console_of t8-c-unaided)
    grep -n -E '^(CONTAINERS RETURNED UNAIDED|PERSISTENCE SHOWN|STOP:)' "$f" | cut -c1-260
    no_stop t8-c-unaided && echo "-> no_stop for step c: no STOP:" || echo "-> no_stop for step c: a STOP: was found (the halt names 'no line PERSISTENCE SHOWN')"
    commands
    left_over
    rm -f "$P/$T8_PREFIX".*
}

gate_case() {   # gate_case NAME: the bench's gate attempt holds $B/gate/NAME as its record
    local rc
    rm -rf "$B/gate/attempt"
    mkdir -p "$B/gate/attempt/environment"
    [ ! -e "$B/gate/$1" ] || cp "$B/gate/$1" "$B/gate/attempt/environment/container_identities.txt"
    WHY=""
    gate_images_check > "$B/gate/out.txt"; rc=$?
    echo "--- gate/$1: returned $rc; $(grep -c '^  now: ' "$B/gate/out.txt") line(s) read; $(tail -n 1 "$B/gate/out.txt" | cut -c1-150)"
    [ "$rc" -eq 0 ] || echo "    WHY: $(printf '%s' "$WHY" | sed "s#$B/##g" | cut -c1-330)"
}

t_gate() {
    local s2 s1
    echo; echo "######## gate: gate_images_check"
    s2="$OT/runs/2026-10-03/20261003T132836Z_g2-gate-preconditions_attempt06/environment/container_identities.txt"
    s1="$OT/runs/2026-10-02/20261002T150720Z_g2-gate-preconditions_attempt05/environment/container_identities.txt"
    mkdir -p "$B/gate"
    cp "$s2" "$B/gate/s2-as-sealed"
    cp "$s1" "$B/gate/s1-as-sealed"
    echo "S2's record: sha256 $(/usr/bin/sha256sum "$s2" | cut -d' ' -f1); the constant's six lines equal its lines 1-6 cut before ' container_id=': $([ "$(sed -n '1,6p' "$s2" | sed 's/ container_id=.*$//')" = "$GATE_IDENTITIES_S2" ] && echo yes || echo NO)"
    sed 's/container_id=[0-9a-f]*/container_id=0000000000000000000000000000000000000000000000000000000000000000/; s/started=.*$/started=2026-10-05T10:00:00.000000001Z/' "$s2" > "$B/gate/other-container-ids-and-instants"
    sed '6s/image_id=sha256:9a293fe1/image_id=sha256:0a293fe1/' "$s2" > "$B/gate/controller-image-id-differs"
    sed '2s/repo_digest=mongo@sha256:35a5/repo_digest=mongo@sha256:45a5/' "$s2" > "$B/gate/mongo-digest-differs"
    sed '1s/eclipse-mosquitto:2.0.22@/eclipse-mosquitto:2.0.23@/' "$s2" > "$B/gate/mosquitto-reference-differs"
    sed '4d' "$s2" > "$B/gate/five-identity-lines"
    sed '6p' "$s2" > "$B/gate/seven-identity-lines"
    sed '3s/ repo_digest=[^ ]*//' "$s2" > "$B/gate/a-line-of-another-form"
    : > "$B/gate/empty-file"
    SESSION_FILE=$STATE/session-S3.env
    : > "$SESSION_FILE"
    state_set "$SESSION_FILE" gate_attempt "$B/gate/attempt"
    for c in s2-as-sealed s1-as-sealed other-container-ids-and-instants controller-image-id-differs mongo-digest-differs mosquitto-reference-differs five-identity-lines seven-identity-lines a-line-of-another-form empty-file no-file; do
        gate_case "$c"
    done
    : > "$SESSION_FILE"
    cp "$B/gate/s2-as-sealed" "$B/gate/attempt/environment/container_identities.txt"
    WHY=""; gate_images_check > /dev/null; echo "--- gate/attempt-not-recorded-at-open: returned $?; WHY: $(printf '%s' "$WHY" | cut -c1-200)"
    SESSION_FILE=""
}

fresh_case() {   # fresh_case NAME SLUG: fresh_row on the bench's own attempts and output roots
    local rc
    fresh_row "$2" > "$B/fresh/out.txt"; rc=$?
    echo "--- fresh/$1: fresh_row $2 returned $rc"
    sed "s#$B/##g; s/^/    /" "$B/fresh/out.txt" | grep -E 'admitted|NOT FRESH' | cut -c1-200
}

t_fresh() {
    local name ok
    echo; echo "######## fresh: fresh_row (point 9) on roots of the bench (ATTEMPTS and OUT set to $B/fresh/...)"
    ATTEMPTS=$B/fresh/attempts
    OUT=$B/fresh/out
    mkdir -p "$ATTEMPTS" "$OUT/runs/2026-10-03" "$OUT/runs/2026-10-04" "$OUT/incomplete"
    fresh_case nothing-anywhere t8
    mkdir -p "$ATTEMPTS/$T8_ADMITTED" "$OUT/runs/2026-10-03/$T8_ADMITTED"
    fresh_case the-admitted-attempt-in-both-places t8
    fresh_case t9-with-only-t8-attempts t9
    mkdir -p "$ATTEMPTS/20261004T101010Z_g3-qualification-t8_attempt02"
    fresh_case another-t8-attempt-in-wsl t8
    rmdir "$ATTEMPTS/20261004T101010Z_g3-qualification-t8_attempt02"
    mkdir -p "$OUT/runs/2026-10-04/$T8_ADMITTED"
    fresh_case the-admitted-name-under-another-date t8
    rmdir "$OUT/runs/2026-10-04/$T8_ADMITTED"
    mkdir -p "$OUT/incomplete/$T8_ADMITTED"
    fresh_case the-admitted-name-under-incomplete t8
    rmdir "$OUT/incomplete/$T8_ADMITTED"
    mkdir -p "$OUT/runs/2026-10-03/20261003T150000Z_g3-qualification-t8_attempt01"
    fresh_case another-stamp-attempt01-in-output t8
    rmdir "$OUT/runs/2026-10-03/20261003T150000Z_g3-qualification-t8_attempt01"
    mkdir -p "$OUT/runs/2026-10-04/20261004T101010Z_g3-qualification-t9_attempt01"
    fresh_case an-earlier-t9-attempt t9
    rmdir "$OUT/runs/2026-10-04/20261004T101010Z_g3-qualification-t9_attempt01"
    : > "$P/$T8_PREFIX.boot_id.pre"
    fresh_case a-host-file-of-the-prefix t8
    rm -f "$P/$T8_PREFIX.boot_id.pre"
    mkdir -p "$P/itest-notls-q2.sut"
    fresh_case a-host-file-of-a-t9-id t9
    rmdir "$P/itest-notls-q2.sut"
    echo "--- fresh/ids: row_fresh_ids t8 = $(row_fresh_ids t8); row_fresh_ids t9 = $(row_fresh_ids t9); row_workload_ids t8 = $(row_workload_ids t8)"
    echo "--- fresh/attempt-name: the rule 'row' applies to the new attempt's name"
    for name in t8:20261005T100000Z_g3-qualification-t8_attempt02 t8:20261005T100000Z_g3-qualification-t8_attempt01 t8:20261005T100000Z_g3-qualification-t8_attempt03 t9:20261005T110000Z_g3-qualification-t9_attempt01 t9:20261005T110000Z_g3-qualification-t9_attempt02 t9:20261005T110000Z_g3-qualification-t8_attempt02; do
        case ${name#*:} in *"$(row_attempt_suffix "${name%%:*}")") ok="accepted" ;; *) ok="HALT before any step" ;; esac
        echo "    row ${name%%:*}, attempt ${name#*:}: $ok"
    done
    echo "--- fresh/numbering: what the frozen export tool names a new t8 attempt when $T8_ADMITTED exists in both roots"
    name=$(new_attempt "G3 qualification t8" official) && echo "    $(basename "$name")"
    ATTEMPTS=$EGW_ATTEMPTS
    OUT=$EGW_OUTPUT_TEST
}

ident_case() {   # ident_case NAME
    local rc
    WHY=""
    verify_candidate > "$B/ident.out.txt" 2>&1; rc=$?
    echo "--- ident/$1: verify_candidate returned $rc${WHY:+; WHY: $(printf '%s' "$WHY" | sed "s#$B/##g" | cut -c1-260)}"
}

t_ident() {
    echo; echo "######## ident: verify_candidate (point 3) - the drivers, the export tool, the runbook, the helper file, tunnel.sh and ca.crt are hashed for real"
    ident_case all-as-recorded
    sed "s#$B/##g" "$B/ident.out.txt" | cut -c1-230
    echo 0000000000000000000000000000000000000000000000000000000000000000 > "$B/sha.kernel"; ident_case kernel-differs; rm -f "$B/sha.kernel"
    echo 0000000000000000000000000000000000000000000000000000000000000000 > "$B/sha.qemuboot"; ident_case qemuboot-differs; rm -f "$B/sha.qemuboot"
    echo 0000000000000000000000000000000000000000000000000000000000000000 > "$B/sha.qemu"; ident_case qemu-binary-differs; rm -f "$B/sha.qemu"
    echo 80e833f44f647fe9cd8f5e99d3abf3c444de95aa > "$B/git.yocto.head"; ident_case yocto-commit-differs; rm -f "$B/git.yocto.head"
    : > "$B/git.yocto.dirty"; ident_case yocto-not-clean; rm -f "$B/git.yocto.dirty"
    : > "$B/git.dirty"; ident_case clone-not-clean; rm -f "$B/git.dirty"
    ident_case all-as-recorded-again
}

for t in "${TESTS[@]}"; do
    case $t in
        polltext | wait | wait20 | qemu | markers | steps | gate | fresh | ident) "t_$t" ;;
        *) echo "unknown test $t" ;;
    esac
done
echo; echo "## $(date -u +%Y-%m-%dT%H:%M:%SZ) ended; processes of the bench left: $(/usr/bin/pgrep -f "$B/" | wc -l)"
