#!/bin/bash
# tools/demo/demo.sh - OPTIONAL numbered menu over the independent demonstration commands: the
# lifecycle of tools/compare/tf.sh and the scripts of this folder, nothing else. Each option prints the
# command it runs (relative to the repository root), so every step can also be typed by hand
# (docs/demo.md). It opens no terminals: the observers (MQTT, Ditto, resources, logs) are meant for
# their own WSL terminals; option 6 is a single snapshot of the twins. Leaving the menu does NOT power
# the environment off (option 8 does, through the controlled stop of tf.sh).
set -u
. "$(dirname "$0")/lib.sh"
H=$DEMO_DIR
T=$DEMO_TOOLS
pick_scenario() {   # the scenario of the running guest, else ask
    for s in yocto debian13 yoctowrynose; do guest_running "$s" && { echo "$s"; return; }; done
    printf 'scenario [yocto|debian13|yoctoWrynose]: ' > /dev/tty
    read -r s < /dev/tty
    scenario_canon "$s"
}
act() {   # act LABEL CMD...: print the equivalent command from the repository root, then run it
    local label=$1
    shift
    printf '\n$ %s\n' "$label"
    "$@"
}
while :; do
    cat << 'EOF'

========== Prototype demonstration (ARM64 guest emulated by QEMU/TCG) ==========
 1 - Start Yocto                  5 - Simulate 3 wearables (60 s)
 2 - Start Debian 13              6 - Show the twins (one query)
 3 - Environment status           7 - Stop the simulation
 4 - Simulate 1 wearable (60 s)   8 - Power the environment off
 9 - Start yoctoWrynose (additional scenario, not measured)
 0 - Leave (the environment keeps running)
Observers, each in its own WSL terminal (from the repository root):
  bash tools/demo/observe/mqtt.sh <s> | ditto.sh <s> | resources.sh <s> | logs.sh <s> <service>
================================================================================
EOF
    printf 'option: '
    read -r opt || { echo; echo "end of input; the environment, if running, keeps running"; exit 0; }
    case $opt in
        1) act "bash tools/compare/tf.sh yocto apply" bash "$T/tf.sh" yocto apply ;;
        2) act "bash tools/compare/tf.sh debian13 apply" bash "$T/tf.sh" debian13 apply ;;
        9) act "bash tools/compare/tf.sh yoctowrynose apply" bash "$T/tf.sh" yoctowrynose apply ;;
        3)
            s=$(pick_scenario)
            act "bash tools/compare/tf.sh $s status" bash "$T/tf.sh" "$s" status
            if guest_running "$s" && stack_ready "$s"; then echo "STACK READY ($s): controller /ready 200"; else echo "stack not ready (or the $s guest is not running)"; fi
            ;;
        4) s=$(pick_scenario); act "bash tools/demo/wearables/simulate.sh $s 1 60" bash "$H/wearables/simulate.sh" "$s" 1 60 ;;
        5) s=$(pick_scenario); act "bash tools/demo/wearables/simulate.sh $s 3 60" bash "$H/wearables/simulate.sh" "$s" 3 60 ;;
        6) s=$(pick_scenario); act "bash tools/demo/observe/ditto.sh $s 5 once" bash "$H/observe/ditto.sh" "$s" 5 once ;;
        7) act "bash tools/demo/wearables/stop.sh" bash "$H/wearables/stop.sh" ;;
        8)
            s=$(pick_scenario)
            printf 'power %s off in a controlled way? [y/N] ' "$s"
            read -r ok
            case $ok in
                y | Y)
                    act "bash tools/demo/wearables/stop.sh quiet" bash "$H/wearables/stop.sh" quiet
                    act "bash tools/compare/tf.sh $s stop" bash "$T/tf.sh" "$s" stop
                    act "bash tools/compare/tf.sh $s status" bash "$T/tf.sh" "$s" status
                    if any_qemu; then
                        echo "STOP: a qemu-system-aarch64 process is still present. Do NOT kill it: read $DEMO_COMPARE_ROOT/scenarios/$s/logs/stop-*.log and the console log, and report."
                    else
                        echo "QEMU ended: no qemu-system-aarch64 process"
                    fi
                    ;;
                *) echo "nothing done" ;;
            esac
            ;;
        0) echo "leaving the menu; the environment, if running, keeps running (option 8 powers it off)"; exit 0 ;;
        *) echo "invalid option" ;;
    esac
done
