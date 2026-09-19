#!/bin/bash
# Close the open guest session: stop the stack first (runbook 3.3), keep the
# journal and final state, power off, record the rootfs afterwards, export.
set -u
. "$(dirname "$0")/common.sh"
. "$(dirname "$0")/guest_common.sh"
S=$SESSION
[ -n "$S" ] && [ -d "$S" ] || { echo "STOP: no open session" >&2; exit 1; }
fails=0
hx "$S" tunnel-down 'tunnel_down || true'
gx "$S" stack-stop "cd /opt/egw/deployment && $DC stop -t 60; echo \"stop exit=\$?\"; docker ps -a --format '{{.Names}} {{.Status}}'" || fails=$((fails + 1))
gx "$S" oom-before-poweroff 'sudo -n dmesg | grep -i "memory cgroup out of memory" || echo "no memory-cgroup OOM in this boot"'
ex "$S" session-close bash "$S/scripts/session_close.sh" "$S" || fails=$((fails + 1))
ex "$S" artefacts-after-poweroff bash -c "sha256sum '$ROOTFS_EXT4'; ls -l '$DATA_DISK'; pgrep -af qemu-system-aarch64 || echo 'no qemu process left'"
if [ "$fails" -eq 0 ]; then
    (cd "$REPO/src" && $LE finish --attempt "$S" --status finished --validity not-applicable --outcome pass \
        --reason "session closed: stack stopped before power-off, journal and final state kept" --next-action "none")
else
    (cd "$REPO/src" && $LE finish --attempt "$S" --status failed --validity not-applicable --outcome fail \
        --reason "session close had $fails failing step(s); see console/" --next-action "check the guest state before the next boot")
fi
rm -f "$EXEC/current_session"
export_attempt "$S"
