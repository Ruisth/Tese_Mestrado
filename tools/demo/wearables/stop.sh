#!/bin/bash
# tools/demo/wearables/stop.sh [quiet] - stop the demonstration's simulator, and ONLY it: the pid in
# $DEMO_STATE/sim.pid is signalled only if its command line is the simulator of the current
# demonstration run (SIGINT, then SIGTERM after 10 s; never SIGKILL); QEMU, the guest and every other
# process are never touched.
set -u
. "$(dirname "$0")/../lib.sh"
quiet=${1:-}
pidf=$DEMO_STATE/sim.pid
if [ ! -s "$pidf" ]; then [ "$quiet" = quiet ] || echo "no demonstration simulation recorded"; exit 0; fi
pid=$(tr -dc '0-9' < "$pidf")
run=$(current_run)
if ! kill -0 "$pid" 2> /dev/null; then echo "simulation pid $pid is not running (run $run); record cleared"; rm -f "$pidf"; exit 0; fi
cmd=$(tr '\0' ' ' < "/proc/$pid/cmdline" 2> /dev/null)
case $cmd in
    *"egw_simulator run"*"$run"*) ;;
    *) echo "STOP: pid $pid is not the simulator of run $run ($cmd); nothing signalled"; exit 2 ;;
esac
echo "stopping the simulator of run $run (pid $pid): SIGINT"
kill -INT "$pid" 2> /dev/null
for _ in 1 2 3 4 5 6 7 8 9 10; do kill -0 "$pid" 2> /dev/null || break; sleep 1; done
if kill -0 "$pid" 2> /dev/null; then echo "still running after 10 s: SIGTERM"; kill -TERM "$pid" 2> /dev/null; sleep 2; fi
kill -0 "$pid" 2> /dev/null && { echo "STOP: the simulator did not end; it was not killed with SIGKILL"; exit 1; }
rm -f "$pidf"
echo "simulation stopped (run $run); the guest keeps running"
