#!/bin/bash
# tools/demo/observe/logs.sh <yocto|debian13|yoctoWrynose> <controller|ditto|mongodb|mosquitto> - Terminal 6
# (optional): follow one service's log in the guest (docker logs -f --tail 20). "ditto" follows the
# three Ditto services. MongoDB's log is additional observation only: it is Ditto's storage, not the
# transport, and a log line is not proof of a twin update (ditto.sh is). Ctrl+C ends only this.
# The broker's own health probe (every 30 s, client "egw-healthcheck" with a deliberately wrong
# password, refused as "not authorised") is hidden: its "Client egw-healthcheck ..." line and the
# "New connection from 127.0.0.1:..." line just before it. Other connections from 127.0.0.1, such as
# the mqtt.sh observer, are still shown. The filter runs on the host; the guest's log is unchanged.
set -u
. "$(dirname "$0")/../lib.sh"
scenario_check "${1:-}" || exit 2
s=$(scenario_canon "$1")
case ${2:-} in
    controller) c="egw-controller-1" ;;
    mosquitto) c="egw-mosquitto-1" ;;
    mongodb) c="egw-mongodb-1" ;;
    ditto) c="egw-ditto-gateway-1 egw-ditto-things-1 egw-ditto-policies-1" ;;
    *) echo "usage: logs.sh <yocto|debian13|yoctoWrynose> <controller|ditto|mongodb|mosquitto>" >&2; exit 2 ;;
esac
guest_running "$s" || { echo "STOP: the $s guest is not running"; exit 2; }
say "logs of $c on $s (docker logs -f, last 20 lines first; broker health-probe lines hidden). Ctrl+C to stop."
# Prefix each line with the container name and drop the health-probe pairs. A "New connection from
# 127.0.0.1" line is held until the next line shows whose it is, or for at most 2 s.
FILTER='
import os, select, sys
name = sys.argv[1]
fd = sys.stdin.fileno()
buf, held = b"", None
def out(line):
    sys.stdout.write("[" + name + "] " + line + "\n")
    sys.stdout.flush()
while True:
    ready, _, _ = select.select([fd], [], [], 2.0)
    if not ready:
        if held is not None:
            out(held)
            held = None
        continue
    chunk = os.read(fd, 65536)
    if not chunk:
        break
    buf += chunk
    while b"\n" in buf:
        raw, buf = buf.split(b"\n", 1)
        line = raw.decode("utf-8", "replace").rstrip("\r")
        if "egw-healthcheck" in line:
            held = None
            continue
        if held is not None:
            out(held)
            held = None
        if "New connection from 127.0.0.1:" in line:
            held = line
            continue
        out(line)
if held is not None:
    out(held)
if buf:
    out(buf.decode("utf-8", "replace"))
'
for name in $c; do
    dssh "$s" "docker logs -f --tail 20 $name 2>&1" | python3 -u -c "$FILTER" "$name" &
done
trap 'kill $(jobs -p) 2> /dev/null' INT TERM
wait
