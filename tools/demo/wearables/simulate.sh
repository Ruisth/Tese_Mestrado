#!/bin/bash
# tools/demo/wearables/simulate.sh <yocto|debian13|yoctoWrynose> <1|3> [duration_s] [rate_msg_s] [--dry-run]
# Terminal 5: the EXISTING simulator (python -m egw_simulator run, in the venv) publishes telemetry for
# one smartwatch (1) or the three profiles smartwatch + smart_ring + smart_clothing (3) to the running
# guest's broker (TLS on the host's 127.0.0.1:8883, forwarded by QEMU to the guest; QoS 1). A short,
# bounded demonstration run: its parameters are printed before anything is published, the run id is
# unique to the demonstration (demo-<UTC>-w1|w3, never an experimental id) and is written to
# $DEMO_STATE/current_run for the observers.
# The rate is a demonstration parameter (default 1.0 msg/s for one device, 2.24 msg/s in total for the
# three, split 1 : 0.2 : 10 as the simulator does); it is not a requirement and not the comparison's load.
# The password reaches the simulator from $DEMO_SECRETS through the environment of a subshell; it is
# never printed and never on a command line. --dry-run prints the parameters and the command and exits.
# Stop early with tools/demo/wearables/stop.sh (only this process is signalled).
# Settings: tools/demo/lib.sh (DEMO_VENV, DEMO_SECRETS, EGW_COMPARE_ROOT, DEMO_STATE_ROOT ...).
set -u
. "$(dirname "$0")/../lib.sh"
scenario_check "${1:-}" || exit 2
dry=0
args=()
for a in "$@"; do if [ "$a" = --dry-run ]; then dry=1; else args+=("$a"); fi; done
set -- "${args[@]}"
s=$(scenario_canon "$1")
n=${2:-1}
duration=${3:-60}
rate=${4:-}
case $n in
    1) devices=smartwatch; [ -n "$rate" ] || rate=1.0 ;;
    3) devices=smartwatch,smart_ring,smart_clothing; [ -n "$rate" ] || rate=2.24 ;;
    *) echo "usage: simulate.sh <yocto|debian13|yoctoWrynose> <1|3> [duration_s] [rate_msg_s] [--dry-run]" >&2; exit 2 ;;
esac
case $duration in '' | *[!0-9.]*) echo "duration must be a number of seconds" >&2; exit 2 ;; esac
PY=$DEMO_VENV/bin/python
CA=$DEMO_COMPARE_ROOT/scenarios/$s/state/ca.crt
for d in "$DEMO_STATE" "$DEMO_RUNS"; do
    if inside_repo "$d"; then
        echo "STOP: $d is inside the repository; set DEMO_STATE_ROOT (or DEMO_STATE and DEMO_RUNS) to a folder outside it" >&2
        exit 2
    fi
done
mkdir -p "$DEMO_STATE" "$DEMO_RUNS"
RUN=demo-$(date -u +%Y%m%dT%H%M%SZ)-w$n
SEED=$(date -u +%s)
say "demonstration run (not an experiment)"
cat << EOF
scenario   : $s (broker 127.0.0.1:8883, TLS, QoS 1; CA $CA)
run id     : $RUN
devices    : $devices  ($n wearable(s); one simulated device per profile)
rate       : $rate msg/s in total - a demonstration parameter, split 1 : 0.2 : 10 between the profiles; not a requirement
duration   : $duration s  (bounded: the simulator stops by itself)
seed       : $SEED (device identities derive from it)
output     : $DEMO_RUNS/$RUN/sent_events.jsonl  (outside the repository and outside the experimental evidence)
path       : simulator -> MQTT/Mosquitto -> controller -> Ditto (twin) -> MongoDB (Ditto's storage)
EOF
CMD=("$PY" -m egw_simulator run --scenario smoke --seed "$SEED" --devices "$devices" --rate "$rate" --duration "$duration" \
    --run-id "$RUN" --broker 127.0.0.1 --port 8883 --username egw-simulator --ca-cert "$CA" --egw-id egw-01 --output "$DEMO_RUNS" --qos 1)
echo "command    : ${CMD[*]}   (password: environment only)"
[ "$dry" = 1 ] && { echo "dry run: nothing published"; exit 0; }
# --- preconditions: the stack is ready, no demonstration simulation already runs --------------------
[ -x "$PY" ] || { echo "STOP: venv python missing: $PY (set DEMO_VENV or EGW_EXEC_VENV)"; exit 2; }
"$PY" -c 'import egw_simulator' 2> /dev/null || { echo "STOP: egw_simulator not importable from $PY"; exit 2; }
[ -r "$DEMO_SECRETS" ] || { echo "STOP: secrets file not readable: $DEMO_SECRETS (set DEMO_SECRETS or EGW_COMPARE_SECRETS_ENV)"; exit 2; }
[ -s "$CA" ] || { echo "STOP: broker CA missing: $CA (the stack was never provisioned on this scenario)"; exit 2; }
guest_running "$s" || { echo "STOP: the $s guest is not running (terminal 1: bash tools/compare/tf.sh $s apply)"; exit 2; }
stack_ready "$s" || { echo "STOP: the controller does not answer /ready 200 yet (bash tools/compare/tf.sh $s status; bash tools/demo/observe/logs.sh $s controller)"; exit 2; }
if [ -s "$DEMO_STATE/sim.pid" ] && kill -0 "$(cat "$DEMO_STATE/sim.pid")" 2> /dev/null; then
    echo "STOP: a demonstration simulation is already running (pid $(cat "$DEMO_STATE/sim.pid"), run $(current_run)); stop it first: bash tools/demo/wearables/stop.sh"; exit 2
fi
echo "$RUN" > "$DEMO_STATE/current_run"
echo "$s" > "$DEMO_STATE/current_scenario"
say "publishing ($duration s) - Ctrl+C stops only the simulator"
(
    # shellcheck disable=SC1090
    . "$DEMO_SECRETS" > /dev/null 2>&1 || exit 97
    [ -n "${MOSQUITTO_SIMULATOR_PASSWORD:-}" ] || exit 98
    EGW_MQTT_PASSWORD=$MOSQUITTO_SIMULATOR_PASSWORD
    export EGW_MQTT_PASSWORD
    exec "${CMD[@]}"
) &
SIM=$!
echo "$SIM" > "$DEMO_STATE/sim.pid"
trap 'kill -INT "$SIM" 2> /dev/null' INT TERM
# live view of what is being published (device, seq, message id), from the simulator's own record;
# 'tail --pid' stops following once the simulator has exited, and the reader then sees end of input,
# so the view ends by itself instead of being left behind
sleep 2
F=$DEMO_RUNS/$RUN/sent_events.jsonl
( tail -n +1 -F --pid="$SIM" "$F" 2> /dev/null | python3 -u -c '
import json, sys
for line in sys.stdin:
    try:
        d = json.loads(line)
    except ValueError:
        continue
    t = d.get("device_type", "?"); q = d.get("seq", "?"); u = d.get("device_uuid", "?"); m = d.get("message_id", "?")
    print(f"published  {t:15} seq {q:<5} device {u}  message {m}", flush=True)
' ) &
TAIL=$!
wait "$SIM"
rc=$?
# bounded wait for the view to end; if it has not, signal (TERM) only its own processes: the tail and the
# reader are children of the view's subshell, which a signal to the subshell alone would leave running
for _ in 1 2 3 4 5 6 7 8 9 10; do kill -0 "$TAIL" 2> /dev/null || break; sleep 1; done
if kill -0 "$TAIL" 2> /dev/null; then
    for p in $(ps -o pid= --ppid "$TAIL" 2> /dev/null); do kill "$p" 2> /dev/null; done
    kill "$TAIL" 2> /dev/null
fi
wait "$TAIL" 2> /dev/null
rm -f "$DEMO_STATE/sim.pid"
say "simulator ended (exit $rc); run $RUN; sent $(grep -c . "$F" 2> /dev/null || echo 0) message(s) - see the observers for the MQTT publications and the Ditto twins"
exit $rc
