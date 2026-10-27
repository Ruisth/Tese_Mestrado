#!/bin/bash
# Operator's launcher for the G3 battery: starts ONE long subcommand of
# g3_battery.sh detached (as its README prescribes: setsid, no terminal), then
# waits read-only for it to end and prints the end of its console and the
# status. It decides nothing.
# Usage (WSL login shell): g3_go.sh <open S1|row <slug>|close> [max minutes]
set -u
OPS=$(cd "$(dirname "$0")" && pwd)
P=$(cd "$OPS/../prep" && pwd)
KIND=${1:?} NAME=${2:-} MAX=${3:-170}
case $KIND in
    open | row) [ -n "$NAME" ] || { echo "usage: g3_go.sh <open S1|row <slug>|close> [max minutes]"; exit 2; }
        EGW_EXEC_REPO=$HOME/egw-exec/repo setsid bash "$P/g3_battery.sh" "$KIND" "$NAME" > /dev/null 2>&1 < /dev/null & ;;
    close) NAME=${NAME:-session}
        EGW_EXEC_REPO=$HOME/egw-exec/repo setsid bash "$P/g3_battery.sh" close > /dev/null 2>&1 < /dev/null & ;;
    *) echo "usage: g3_go.sh <open S1|row <slug>|close> [max minutes]"; exit 2 ;;
esac
echo "launched '$KIND $NAME' detached at $(date -u +%FT%TZ)"
exec bash "$OPS/g3_wait.sh" "$KIND" "$NAME" "$MAX"
