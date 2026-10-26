#!/bin/bash
# tools/demo/observe/mqtt.sh <yocto|debian13|yoctoWrynose> - Terminal 2: the MQTT publications as the
# broker sees them. Runs mosquitto_sub INSIDE the broker container of the guest (the procedure of the
# battery's ACL test: TLS on localhost:8883 with the broker's CA, the controller's read-only identity
# on c2dt/#, its own client id); prints "topic payload" per message. The controller's password is read
# on the guest from the deployment's own .env into the container's environment; it is never printed,
# never typed and never reaches the host. While this observer runs, the value is visible in process
# arguments INSIDE the guest and the broker container (docker compose exec -e, mosquitto_sub -P).
# This shows the PUBLICATION observed at the broker, not the twin update (see ditto.sh). Ctrl+C ends
# only this observer.
set -u
. "$(dirname "$0")/../lib.sh"
scenario_check "${1:-}" || exit 2
s=$(scenario_canon "$1")
guest_running "$s" || { echo "STOP: the $s guest is not running"; exit 2; }
say "MQTT observer on $s: broker-side view of c2dt/# (topic c2dt/<egw-id>/<device-uuid>/telemetry; payload JSON). Ctrl+C to stop."
REMOTE='cd /opt/egw/deployment && set -a && . ./.env && set +a && exec docker compose --env-file .env --env-file images.lock.env exec -T -e MQTT_PW="$MOSQUITTO_CONTROLLER_PASSWORD" mosquitto sh -c "exec mosquitto_sub -h localhost -p 8883 --cafile /mosquitto/config/certs/ca.crt -V mqttv311 -i demo-observer-$$ -u egw-controller -P \"\$MQTT_PW\" -t c2dt/# -q 1 -v"'
exec ssh -i "$(demo_key "$s")" -p "$DEMO_SSH_PORT" -o IdentitiesOnly=yes -o BatchMode=yes \
    -o StrictHostKeyChecking=accept-new -o UserKnownHostsFile="$DEMO_COMPARE_ROOT/scenarios/$s/state/known_hosts" \
    -o ConnectTimeout=10 -o ServerAliveInterval=30 -o LogLevel=ERROR egw@127.0.0.1 "$REMOTE"
