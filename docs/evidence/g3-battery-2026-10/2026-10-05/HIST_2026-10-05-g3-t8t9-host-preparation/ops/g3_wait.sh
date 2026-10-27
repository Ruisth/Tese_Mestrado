#!/bin/bash
# Operator's waiter for session S3 (G3, tests 8 and 9) (read-only): returns
# when a detached g3_battery.sh subcommand has ended, then prints the end of
# its console and the script's own 'status'. It signals nothing and writes
# nothing.
# Usage (WSL): g3_wait.sh <open|row|close> <S3|slug> [max minutes]
set -u
KIND=${1:?} NAME=${2:?} MAX=${3:-170}
STATE=${EGW_G3_STATE:-$HOME/egw-exec/g3-t8t9-s3}
P=$(cd "$(dirname "$0")/.." && pwd)     # S3: the folder that holds ops/ and the steps script (no fixed path)
case $KIND in
    open | close) pat="g3_battery.sh $KIND" ;;
    row) pat="g3_battery.sh row $NAME" ;;
    *) echo "usage: g3_wait.sh <open|row|close> <name> [max minutes]"; exit 2 ;;
esac
read -r up0 _ < /proc/uptime; up0=${up0%.*}
sleep 5
while pgrep -f -- "$pat" > /dev/null 2>&1; do
    read -r now _ < /proc/uptime; now=${now%.*}
    if [ $(((now - up0) / 60)) -ge "$MAX" ]; then
        echo "WAITER: $pat still running after $MAX min of host uptime - the waiter ends, the subcommand goes on"
        break
    fi
    sleep 10
done
read -r now _ < /proc/uptime; now=${now%.*}
echo "WAITER: '$pat' ended or the waiter timed out after $((now - up0)) s (host uptime)"
last=$(ls -1 "$STATE"/console/*.txt 2> /dev/null | tail -n 1)
echo "== last console: $last"
tail -n "${G3_TAIL:-70}" "$last" 2> /dev/null
echo "== status"
EGW_EXEC_REPO=$HOME/egw-exec/repo bash "$P/g3_battery.sh" status 2>&1 | tail -n 60
