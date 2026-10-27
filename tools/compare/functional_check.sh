#!/bin/bash
# tools/compare/functional_check.sh - ONE synthetic event from one test device to its twin on the
# running guest of a comparison scenario, with the project's own simulator; no campaign, no
# confirmation window, no harness accounting. It shows the path works (a reachability check,
# never a slice PASS in the project's sense).
#
#   functional_check.sh <scenario> <run-id> <seed>
#
# Host inputs (overridable):
#   EGW_EXEC_VENV              venv whose python has egw_simulator installed (default $HOME/egw-exec/venv)
#   EGW_COMPARE_SECRETS_ENV    the .env (default $HOME/egw-tcg/.env); only MOSQUITTO_SIMULATOR_PASSWORD
#                              is read, in a subshell, and handed to the simulator through the
#                              environment (EGW_MQTT_PASSWORD) - never on a command line, never printed
#   EGW_COMPARE_ACCEPT_LIMIT_S seconds allowed for the controller to count the event (default 120)
# Needs $S_DIR/state/ca.crt (fetched by provision_stack.sh), ssh, curl, ss and python3 on the host.
#
# Steps: ssh tunnel to the guest's loopback APIs (8000 controller, 8080 Ditto) on the scenario's
# own control socket; /metrics before; the simulator for one smartwatch message (smoke scenario,
# 1 msg/s for 1 s, QoS 1, TLS); poll /metrics until `accepted` grew by one; GET the twin
# org.c2dta:<device_uuid> and look for the run id in features.ingestion.properties.last_run_id.
# Output: $S_DIR/results/functional-<stamp>-<run-id>/ with metrics.before.json, metrics.after.json,
# sim/<run-id>/sent_events.jsonl, simulator.stderr.txt, twin.json, check.json, functional.log.
# Exit: 0 pass; 1 fail (the event was not accepted or the twin does not carry the run id);
#       2 a prerequisite is missing (venv, secrets, CA, tunnel, controller not reachable).
# The last line printed is always: FUNCTIONAL <scenario> <run-id>: result=pass|fail ...
set -u
HERE=$(cd "$(dirname "$0")" && pwd)
# shellcheck source=lib.sh
. "$HERE/lib.sh"

usage() { sed -n '2,27p' "$0" | sed 's/^# \{0,1\}//' >&2; exit 2; }
[ $# -eq 3 ] || usage
scenario=$1
run=$2
seed=$3
scenario_load "$scenario"
printf '%s' "$run" | grep -Eq '^[A-Za-z0-9._-]{1,64}$' || die "run-id '$run' is not ^[A-Za-z0-9._-]{1,64}$ (the simulator's rule)"
printf '%s' "$seed" | grep -Eq '^[0-9]{1,18}$' || die "seed '$seed' is not a non-negative integer"

VENV=${EGW_EXEC_VENV:-$HOME/egw-exec/venv}
PY=$VENV/bin/python
SECRETS=${EGW_COMPARE_SECRETS_ENV:-$HOME/egw-tcg/.env}
CA=$S_DIR/state/ca.crt
TUNNEL_CTL=$S_DIR/state/tunnel.ctl
ACCEPT_LIMIT_S=${EGW_COMPARE_ACCEPT_LIMIT_S:-120}
ACCEPT_STEP_S=${EGW_COMPARE_ACCEPT_STEP_S:-3}
CTRL=http://127.0.0.1:8000
DITTO=http://127.0.0.1:8080
OUT=$S_DIR/results/functional-$(stamp)-$run
LOG=$OUT/functional.log

# --- prerequisites -------------------------------------------------------------------------------
for tool in ssh curl ss python3; do
    command -v "$tool" > /dev/null 2>&1 || die "host tool missing: $tool"
done
[ -x "$PY" ] || die "venv python missing: $PY (EGW_EXEC_VENV)"
"$PY" -c 'import egw_simulator' > /dev/null 2>&1 || die "egw_simulator is not importable from $PY"
[ -r "$SECRETS" ] || die "secrets file missing or unreadable: $SECRETS"
# Read in a subshell with nothing exported: only the presence of the one value is learnt here.
# shellcheck disable=SC1090
( . "$SECRETS" > /dev/null 2>&1 && [ -n "${MOSQUITTO_SIMULATOR_PASSWORD:-}" ] ) || die "MOSQUITTO_SIMULATOR_PASSWORD is not set in $SECRETS"
[ -s "$CA" ] || die "broker CA missing: $CA (run provision_stack.sh $scenario first)"
[ ! -e "$OUT" ] || die "output directory exists: $OUT"
mkdir -p "$OUT/sim" || die "cannot create $OUT"
: > "$LOG"
log() { log_line "$LOG" "$1"; }
say() { echo "$1"; log "$1"; }
log "functional_check.sh scenario=$SCENARIO run=$run seed=$seed venv=$VENV"

# --- the tunnel ----------------------------------------------------------------------------------
# Opened as an ssh master on this scenario's own control socket and closed through it (never by
# process name); ExitOnForwardFailure makes a busy port a refusal, never a silent miss.
TUNNEL_OPEN=0
tunnel_ssh() { ssh -S "$TUNNEL_CTL" -O "$1" -o LogLevel=ERROR egw@127.0.0.1; }
tunnel_close() {
    [ "$TUNNEL_OPEN" -eq 1 ] || return 0
    TUNNEL_OPEN=0
    if tunnel_ssh exit > /dev/null 2>&1; then log "tunnel closed ($TUNNEL_CTL)"; else log "WARNING: the tunnel master did not answer 'exit' ($TUNNEL_CTL)"; fi
}
trap tunnel_close EXIT
if tunnel_ssh check > /dev/null 2>&1; then
    die "a tunnel master already answers on $TUNNEL_CTL - close it first: ssh -S $TUNNEL_CTL -O exit egw@127.0.0.1"
fi
busy=$(ss -ltn 2> /dev/null | grep -E '[:.](8000|8080) ' || true)
[ -z "$busy" ] || { printf '%s\n' "$busy" >> "$LOG"; die "host port 8000 or 8080 already has a listener (ss -ltn); the tunnel cannot be opened"; }
log "host\$ ssh -f -N -M -S $TUNNEL_CTL -o ExitOnForwardFailure=yes -L 8000:127.0.0.1:8000 -L 8080:127.0.0.1:8080 egw@127.0.0.1"
if ! ssh -f -N -M -S "$TUNNEL_CTL" -o ExitOnForwardFailure=yes -i "$COMPARE_SSH_KEY" -p "$COMPARE_SSH_PORT" \
    -o IdentitiesOnly=yes -o BatchMode=yes -o StrictHostKeyChecking=accept-new -o UserKnownHostsFile="$S_KNOWN_HOSTS" \
    -o ConnectTimeout=10 -o LogLevel=ERROR -L 8000:127.0.0.1:8000 -L 8080:127.0.0.1:8080 egw@127.0.0.1 >> "$LOG" 2>&1; then
    die "ssh exited non-zero: the tunnel was NOT opened (see $LOG)"
fi
TUNNEL_OPEN=1
tunnel_ssh check > /dev/null 2>&1 || die "ssh went to the background but no master answers on $TUNNEL_CTL"
log "tunnel open ($TUNNEL_CTL)"

# --- metrics before ------------------------------------------------------------------------------
# accepted_of FILE: the integer `accepted` of one /metrics reading (empty when absent/invalid).
accepted_of() {
    python3 - "$1" << 'PY'
import json, sys
try:
    v = json.load(open(sys.argv[1], encoding="utf-8")).get("accepted")
except (OSError, ValueError):
    v = None
print(v if isinstance(v, int) and not isinstance(v, bool) else "")
PY
}
curl -fsS --max-time 30 "$CTRL/metrics" > "$OUT/metrics.before.json" 2>> "$LOG" || die "GET $CTRL/metrics failed through the tunnel (stack not ready?)"
accepted_before=$(accepted_of "$OUT/metrics.before.json")
[ -n "$accepted_before" ] || die "/metrics carries no integer 'accepted' ($OUT/metrics.before.json)"
log "metrics before: accepted=$accepted_before"

# --- the simulator: one message ------------------------------------------------------------------
# The password reaches the simulator as EGW_MQTT_PASSWORD (its --password default) from a subshell
# that sourced the .env without exporting it; no secret is on any command line.
sim_rc=0
sent=0
device_uuid=
message_id=
seconds_to_accept=null
accepted_after=
accepted_delta=0
twin_ok=false
twin_path=
uptime_accepted=null
uptime_twin=null
t_sim=$(uptime_s)
log "host\$ $PY -m egw_simulator run --scenario smoke --seed $seed --devices smartwatch --rate 1.0 --duration 1 --run-id $run --broker 127.0.0.1 --port $COMPARE_MQTT_PORT --username egw-simulator --ca-cert $CA --egw-id egw-01 --output $OUT/sim --qos 1"
(
    # shellcheck disable=SC1090
    . "$SECRETS" > /dev/null 2>&1 || exit 97
    [ -n "${MOSQUITTO_SIMULATOR_PASSWORD:-}" ] || exit 98
    EGW_MQTT_PASSWORD=$MOSQUITTO_SIMULATOR_PASSWORD
    export EGW_MQTT_PASSWORD
    exec "$PY" -m egw_simulator run --scenario smoke --seed "$seed" --devices smartwatch --rate 1.0 --duration 1 \
        --run-id "$run" --broker 127.0.0.1 --port "$COMPARE_MQTT_PORT" --username egw-simulator --ca-cert "$CA" \
        --egw-id egw-01 --output "$OUT/sim" --qos 1
) > "$OUT/simulator.stdout.txt" 2> "$OUT/simulator.stderr.txt"
sim_rc=$?
cat "$OUT/simulator.stderr.txt" >> "$LOG"
say "simulator exit=$sim_rc"
sent_file=$OUT/sim/$run/sent_events.jsonl
if [ -s "$sent_file" ]; then
    sent=$(grep -c . "$sent_file")
    read -r device_uuid message_id < <(python3 - "$sent_file" << 'PY'
import json, sys
with open(sys.argv[1], encoding="utf-8") as f:
    first = json.loads(f.readline())
print(first.get("device_uuid", ""), first.get("message_id", ""))
PY
    )
fi
log "sent=$sent device_uuid=${device_uuid:-none} message_id=${message_id:-none}"

# --- the controller counted it -------------------------------------------------------------------
if [ "$sim_rc" -eq 0 ] && [ "$sent" -ge 1 ]; then
    while :; do
        if curl -fsS --max-time 30 "$CTRL/metrics" > "$OUT/metrics.after.json.tmp" 2>> "$LOG"; then
            mv "$OUT/metrics.after.json.tmp" "$OUT/metrics.after.json"
            accepted_after=$(accepted_of "$OUT/metrics.after.json")
        fi
        now=$(uptime_s)
        if [ -n "$accepted_after" ] && [ "$accepted_after" -ge $((accepted_before + 1)) ]; then
            accepted_delta=$((accepted_after - accepted_before))
            uptime_accepted=$now
            seconds_to_accept=$(awk -v a="$t_sim" -v b="$now" 'BEGIN { printf "%.2f", b - a }')
            say "accepted $accepted_before -> $accepted_after after $seconds_to_accept s"
            break
        fi
        if awk -v a="$t_sim" -v b="$now" -v l="$ACCEPT_LIMIT_S" 'BEGIN { exit !(b - a >= l) }'; then
            say "accepted did not grow within $ACCEPT_LIMIT_S s (before=$accepted_before after=${accepted_after:-unread})"
            break
        fi
        sleep "$ACCEPT_STEP_S"
    done
fi

# --- the twin ------------------------------------------------------------------------------------
if [ -n "$device_uuid" ]; then
    if curl -fsS --max-time 30 -H 'x-ditto-pre-authenticated: pre:egw-controller' "$DITTO/api/2/things/org.c2dta:$device_uuid" > "$OUT/twin.json.tmp" 2>> "$LOG"; then
        mv "$OUT/twin.json.tmp" "$OUT/twin.json"
        # Expected path first (CONTRACTS 4, ditto.py); then every string equal to the run id, by path.
        twin_verdict=$(python3 - "$OUT/twin.json" "$run" << 'PY'
import json, sys
twin = json.load(open(sys.argv[1], encoding="utf-8"))
run = sys.argv[2]
expected = "features.ingestion.properties.last_run_id"
def walk(node, path):
    if isinstance(node, dict):
        for k, v in node.items():
            yield from walk(v, f"{path}.{k}" if path else k)
    elif isinstance(node, list):
        for i, v in enumerate(node):
            yield from walk(v, f"{path}[{i}]")
    elif node == run:
        yield path
found = list(walk(twin, ""))
if expected in found:
    print(f"true {expected}")
else:
    print(f"false {','.join(found) or 'none'}")
PY
        ) || twin_verdict="false unreadable"
        twin_ok=${twin_verdict%% *}
        twin_path=${twin_verdict#* }
        [ "$twin_ok" = true ] && uptime_twin=$(uptime_s)
        say "twin org.c2dta:$device_uuid: run id at ${twin_path} -> twin_ok=$twin_ok"
    else
        rm -f "$OUT/twin.json.tmp"
        say "GET $DITTO/api/2/things/org.c2dta:$device_uuid failed"
        twin_path=get-failed
    fi
fi

# --- the record ----------------------------------------------------------------------------------
result=fail
[ "$sim_rc" -eq 0 ] && [ "$sent" -ge 1 ] && [ "$accepted_delta" -ge 1 ] && [ "$twin_ok" = true ] && result=pass
python3 - "$OUT/check.json" "$SCENARIO" "$run" "$seed" "$device_uuid" "$message_id" "$sent" "$sim_rc" \
    "$accepted_before" "${accepted_after:-}" "$accepted_delta" "$twin_ok" "$twin_path" "$seconds_to_accept" "$result" "$(utc_now)" \
    "$t_sim" "$uptime_accepted" "$uptime_twin" "$ACCEPT_STEP_S" << 'PY'
import json, sys
(path, scenario, run, seed, uuid, msg, sent, sim_rc, before, after, delta, twin_ok, twin_path, secs, result, utc,
 up_sim, up_acc, up_twin, step) = sys.argv[1:]
record = {
    "scenario": scenario, "run_id": run, "seed": int(seed), "device_uuid": uuid or None, "message_id": msg or None,
    "sent": int(sent), "simulator_exit": int(sim_rc), "accepted_before": int(before),
    "accepted_after": int(after) if after else None, "accepted_delta": int(delta), "twin_ok": twin_ok == "true",
    "twin_run_id_path": twin_path or None, "seconds_to_accept": None if secs == "null" else float(secs),
    "result": result, "utc": utc,
    # host monotonic instants (the comparison's single clock) and the acceptance probe cadence
    "uptime_simulator_start_s": float(up_sim), "uptime_accepted_s": None if up_acc == "null" else float(up_acc),
    "uptime_twin_s": None if up_twin == "null" else float(up_twin), "accept_step_s": float(step),
}
with open(path, "w", encoding="utf-8") as f:
    json.dump(record, f, indent=2)
    f.write("\n")
PY
tunnel_close
trap - EXIT
echo "FUNCTIONAL $SCENARIO $run: result=$result sent=$sent accepted_delta=$accepted_delta twin_ok=$twin_ok seconds_to_accept=$seconds_to_accept out=$OUT"
[ "$result" = pass ]
