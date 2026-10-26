#!/bin/bash
# tools/demo/observe/resources.sh <yocto|debian13|yoctoWrynose> [interval_s=10] - Terminal 4: resources of
# the guest and of the containers, every interval, from the guest's own tools (free, /proc/loadavg,
# df -P -k, docker stats --no-stream). Three blocks kept apart: GUEST (whole VM), CONTAINERS, DISK (/ and
# /var/lib/docker separately). These are observations of the demonstration, not measurements and not
# comparison results. docker stats takes a few seconds under emulation. Ctrl+C ends only this.
set -u
. "$(dirname "$0")/../lib.sh"
scenario_check "${1:-}" || exit 2
s=$(scenario_canon "$1")
interval=${2:-10}
guest_running "$s" || { echo "STOP: the $s guest is not running"; exit 2; }
say "resources observer on $s every $interval s - observations of the demonstration, not measurements. Ctrl+C to stop."
REMOTE='echo "-- GUEST (whole VM) $(date -u +%H:%M:%S)"; free -m | sed -n "1,2p"; printf "load (1/5/15 min): %s\n" "$(cut -d" " -f1-3 /proc/loadavg)"; echo "-- CONTAINERS (docker stats, one sample)"; docker stats --no-stream --format "table {{.Name}}\t{{.CPUPerc}}\t{{.MemUsage}}"; echo "-- DISK (df -P -k: used KiB)"; df -P -k / /var/lib/docker | awk "NR==1 || /\\/$/ || /docker/ {printf \"%-12s used %10s KiB  avail %10s KiB  %s\\n\", \$6, \$3, \$4, \$5}"'
while :; do
    dssh "$s" "$REMOTE" || echo "$(date -u +%H:%M:%S)  ssh did not answer"
    echo
    sleep "$interval"
done
