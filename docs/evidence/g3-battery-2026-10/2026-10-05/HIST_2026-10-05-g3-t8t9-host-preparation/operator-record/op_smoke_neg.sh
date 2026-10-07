#!/bin/bash
# Stream OPERATOR: four short negative passes of the whole script, each in a bench of its
# own made by op_smoke_setup.sh (stub drivers, FAKE rows). They show that the new halts
# are reached through the subcommands, not only when their functions are called alone.
# The benches of the real step files are the bench stream's work.
#   kernel     the kernel hash differs at open        -> HALT, nothing started
#   gate       the gate's record differs from S2's    -> HALT before row t8, no attempt
#   noreboot   -no-reboot on the fake QEMU's argv     -> HALT before step a, nothing rebooted
#   name       the admitted attempt01 is not there    -> the new attempt is attempt01: HALT before any step
# Usage (WSL): op_smoke_neg.sh /tmp/g3-s3-op-<prefix>     (benches <prefix>-kernel, ... are created)
set -u
ROOT=${1:?usage: op_smoke_neg.sh /tmp/g3-s3-op-<prefix>}
HERE=$(cd "$(dirname "$0")" && pwd)
keep() { grep -E '^(## .*(session S3 is open|row t[89]: attempt|row t[89] ended|step t|QEMU process before)|HALT|REFUSED|NOT STARTED|GATE|row |Next|STOP|poll |QEMU|gate record|  now: identity egw-controller|  S2:  identity egw-controller|admitted|NOT FRESH|kernel|session S3|  row |    HALT)' | sed "s#$B/##g" | cut -c1-360; }
run() {
    echo; echo "=== g3_battery.sh $*"
    bash "$G" "$@" < /dev/null > "$B/last.out" 2>&1
    echo "-> exit $?"
    keep < "$B/last.out"
}
after() {
    echo "--- state directory: $(ls "$EGW_G3_STATE" 2> /dev/null | grep -E '^(session|row)-' | tr '\n' ' ')"
    echo "--- g3-qualification attempts created: $(ls -d "$B"/egw-exec/attempts/*g3-qualification* 2> /dev/null | sed "s#$B/egw-exec/attempts/##" | tr '\n' ' ')"
    A=$(sed -n 's/^attempt=//p' "$EGW_G3_STATE/row-t8.env" 2> /dev/null | tail -n 1)
    [ -z "$A" ] || echo "--- the t8 attempt's steps, in order: $(ls "$A/console" 2> /dev/null | sed -n 's/\.stdout\.txt$//p' | tr '\n' ' ')"
    echo "--- reboot issued by the fake line a (its pre-reboot file exists): $([ -e "$B/home/egw-tcg/itest/itest-reboot-q2.boot_id.pre" ] && echo yes || echo no)"
    pid=$(cat "$B/qemu.pid" 2> /dev/null)
    if [ -n "$pid" ] && [ -d "/proc/$pid" ]; then
        echo "--- the fake process that stands for QEMU: pid $pid still running (not signalled by the script); ended now by the bench itself"
        kill "$pid" 2> /dev/null
    else
        echo "--- the fake process that stands for QEMU: not running"
    fi
}
scenario() {
    local name=$1
    B=$ROOT-$name
    echo; echo "######## scenario $name ($B)"
    bash "$HERE/op_smoke_setup.sh" "$B" > /dev/null || { echo "setup failed"; return 1; }
    EGW_G3_ROWS=$B/rows
    # shellcheck source=/dev/null
    . "$HERE/op_env.sh"
    echo "script under test: <scratchpad>/${G#"$S"/} sha256 $(/usr/bin/sha256sum "$G" | cut -d' ' -f1)"
    case $name in
        kernel)
            echo 0000000000000000000000000000000000000000000000000000000000000000 > "$B/sha.kernel"
            run open S3
            ;;
        gate)
            sed -i 's/image_id=sha256:9a293fe1/image_id=sha256:0a293fe1/' "$B/gate.identities"
            run open S3
            run row t8
            run row t9
            ;;
        noreboot)
            run open S3
            kill "$(cat "$B/qemu.pid")"; sleep 0.3
            bash "$B/stubs/fake_qemu_start.sh" -no-reboot; sleep 0.3
            echo "(bench: the fake process was replaced by one whose argv carries -no-reboot)"
            run row t8
            run classify t8 failed not-applicable not-run "bench: -no-reboot found, the reboot was not issued" "bench: none"
            run row t9
            ;;
        name)
            run open S3
            rmdir "$B/out/runs/2026-10-03/20261003T142310Z_g3-qualification-t8_attempt01"
            echo "(bench: the admitted attempt01 was removed from the bench's output root after the open)"
            run row t8
            run classify t8 failed not-applicable not-run "bench: the attempt has an unexpected name, nothing was run" "bench: none"
            run row t9
            ;;
    esac
    after
}
SAVED_PATH=$PATH
for sc in kernel gate noreboot name; do
    PATH=$SAVED_PATH
    unset EGW_G3_STATE
    scenario "$sc"
done
echo; echo "## $(date -u +%Y-%m-%dT%H:%M:%SZ) ended; processes of the benches left: $(/usr/bin/pgrep -f "$ROOT-" | wc -l)"
