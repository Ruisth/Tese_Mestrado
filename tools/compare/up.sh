#!/bin/bash
# tools/compare/up.sh <scenario> - the whole "bring it up" sequence behind `tf.sh <scenario> apply`:
#   1. start the guest (compare_env.sh start: prepared artefacts, guards, daemonised QEMU; a no-op
#      when this scenario's guest is already running),
#   2. wait for ssh, on the host monotonic clock, up to EGW_COMPARE_SSH_LIMIT_S (450 s),
#   3. provision the application stack if needed and start it (provision_stack.sh: idempotent, the
#      pinned images and the verified controller archive; `up -d` is a no-op on a running stack),
#   4. confirm six healthy services and the controller's /ready,
#   5. report that the environment is available and LEAVE IT RUNNING (`tf.sh <scenario> stop` closes it).
# Exit: 0 environment ready; 1 guest up but no ssh within the limit, or stack not ready within its
#       limit (the guest is left running for inspection, never killed); 2 prerequisite or guard
#       (nothing started); 3 a provisioning step failed; 5 QEMU failed to start.
# Transcript: $EGW_COMPARE_ROOT/scenarios/<scenario>/logs/up-<stamp>.log
set -u
HERE=$(cd "$(dirname "$0")" && pwd)
# shellcheck source=lib.sh
. "$HERE/lib.sh"
[ $# -eq 1 ] || { echo "usage: up.sh <scenario>" >&2; exit 2; }
scenario=$1
scenario_load "$scenario"
scenario_dirs
PROVISION=${EGW_COMPARE_PROVISION_SCRIPT:-$HERE/provision_stack.sh}
SSH_LIMIT_S=${EGW_COMPARE_SSH_LIMIT_S:-450}
LOG=$S_DIR/logs/up-$(stamp).log
exec > >(tee -a "$LOG") 2>&1
echo "UP $scenario: $(utc_now) log $LOG"

bash "$HERE/compare_env.sh" start "$scenario"
rc=$?
[ $rc -eq 0 ] || { echo "UP $scenario: start did not succeed (exit $rc); nothing more is done"; exit $rc; }

t0=$(uptime_s)
until gssh true > /dev/null 2>&1; do
    now=$(uptime_s)
    if awk -v a="$t0" -v b="$now" -v l="$SSH_LIMIT_S" 'BEGIN { exit !(b - a >= l) }'; then
        echo "STOP: no ssh answer from the $scenario guest within $SSH_LIMIT_S s; it is left running - inspect with compare_env.sh status $scenario and the console log, close with tf.sh $scenario stop"
        exit 1
    fi
    sleep 5
done
echo "UP $scenario: guest accessible by ssh after $(awk -v a="$t0" -v b="$(uptime_s)" 'BEGIN { printf "%.0f", b - a }') s"

bash "$PROVISION" "$scenario"
rc=$?
case $rc in
    0) echo "ENVIRONMENT READY: $scenario - stack healthy, controller ready; it stays running. Close with: bash tools/compare/tf.sh $scenario stop" ;;
    1) echo "UP $scenario: the stack is up but was not healthy/ready within its limit; the guest stays running for inspection (exit 1)" ;;
    *) echo "UP $scenario: provisioning failed (exit $rc); the guest stays running for inspection" ;;
esac
exit $rc
