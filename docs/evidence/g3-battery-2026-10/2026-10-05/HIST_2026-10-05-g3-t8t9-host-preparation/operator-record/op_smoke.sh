#!/bin/bash
# Stream OPERATOR: one light pass of the whole script in the bench of op_smoke_setup.sh
# (stub drivers, FAKE rows): open S3, row t8, classify t8, row t9, classify t9, close.
# The fake smoke of t8 prints lost and late_confirmations above 0 with PROCEDURE COMPLETE:
# no halt is expected, and t9 must start after t8 is classified as failed.
# Usage (WSL): op_smoke.sh /tmp/g3-s3-op-<name>
set -u
B=${1:?usage: op_smoke.sh /tmp/g3-s3-op-<name>}
HERE=$(cd "$(dirname "$0")" && pwd)
EGW_G3_ROWS=$B/rows
# shellcheck source=/dev/null
. "$HERE/op_env.sh"
grep -q 'BENCH STUB' "$B/repo/tools/session/guest_session_open.sh" || { echo "refused: the bench's drivers are not the stubs"; exit 2; }
echo "## $(date -u +%Y-%m-%dT%H:%M:%SZ) script under test: <scratchpad>/${G#"$S"/} sha256 $(/usr/bin/sha256sum "$G" | cut -d' ' -f1)"
keep() { grep -E '^(## |HALT|REFUSED|NOT STARTED|GATE|row |NOTE|Next|STOP|poll |QEMU|REBOOT|CONTAINERS|PERSISTENCE|TEST STATUS|TUNNEL|carrier|gate record|admitted|fresh|session |rootfs|expected|kernel|qemuboot|qemu-system|Yocto|  row |    HALT|    attempt|What remains|  [123]\.)' | sed "s#$B/##g" | cut -c1-330; }
run() {
    echo; echo "=== g3_battery.sh $*"
    bash "$G" "$@" < /dev/null > "$B/last.out" 2>&1
    echo "-> exit $?"
    keep < "$B/last.out"
}
run open S3
run row t8
A=$(sed -n 's/^attempt=//p' "$EGW_G3_STATE/row-t8.env" | tail -n 1)
echo "--- the t8 attempt's steps, in order: $(ls "$A/console" 2> /dev/null | sed -n 's/\.stdout\.txt$//p' | tr '\n' ' ')"
echo "--- the row's state file: $(grep -E '^(attempt_name|start_up|ceiling_min|t8_|gate=|state=|halt=)' "$EGW_G3_STATE/row-t8.env" | sed "s#$B/##g" | cut -c1-200 | tr '\n' ';')"
echo "--- the workload field's authority text: $("$EGW_EXEC_VENV/bin/python" -c 'import json,sys; print(json.load(open(sys.argv[1]))["workload"]["battery"])' "$A/attempt.json")"
echo "--- the fake process that stands for QEMU: $(pid=$(cat "$B/qemu.pid" 2> /dev/null); [ -n "$pid" ] && [ -d "/proc/$pid" ] && echo "pid $pid still running (never signalled by the script)" || echo "not running")"
run classify t8 failed valid fail "bench: the fake smoke printed lost and late_confirmations above 0" "bench: none"
run row t9
A9=$(sed -n 's/^attempt=//p' "$EGW_G3_STATE/row-t9.env" | tail -n 1)
echo "--- the t9 attempt's steps, in order: $(ls "$A9/console" 2> /dev/null | sed -n 's/\.stdout\.txt$//p' | tr '\n' ' ')"
run classify t9 finished valid pass "bench: fake rows" "bench: none"
run close
run status
echo; echo "--- packages under the bench's output root: $(ls "$B/out/runs"/*/ 2> /dev/null | grep -v '^$' | tr '\n' ' ')"
echo "--- 'compose up', 'start' or 'restart' sent to the stub guest: $(grep -c -E 'compose .*(up|start|restart)|docker start' "$B/ssh.log")"
echo "--- processes of the bench left: $(/usr/bin/pgrep -f "$B/" | wc -l)"
echo "## $(date -u +%Y-%m-%dT%H:%M:%SZ) ended"
