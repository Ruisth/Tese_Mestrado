#!/bin/bash
# Boot the integrated guest and LEAVE IT RUNNING, so that guest-side steps and
# host-side steps (the simulator over hostfwd 8883, the tunnels of runbook 5.7)
# can alternate. Companion scripts: session_run.sh (one guest script),
# session_close.sh (journal, clean power-off, G1 check).
# Usage: session_open.sh <evidence-dir> <run-name>
set -u
E=$1; RUN=$2
KNOWN=${EGW_GUEST_KNOWN_HOSTS:-$HOME/yocto/evidence-candidates/2026-09-18-integrated-3209b17/boot/known_hosts}
REPO=${EGW_YOCTO_CHECKOUT:-/home/ruisth/yocto/egw}
mkdir -p "$E/boot" "$E/guest" "$E/host"
[ -f "$E/boot/known_hosts" ] || cp -p "$KNOWN" "$E/boot/known_hosts"
printf '%s\n' "$RUN" > "$E/.current_run"
. "$E/scripts/session_common.sh"

log "opening session $RUN"
if ss -ltn | grep -qE ':(2222|8883) '; then log "STOP: host port 2222 or 8883 busy"; exit 1; fi
{ echo "source_commit=$(git -C "$REPO" rev-parse HEAD)"
  echo "branch=$(git -C "$REPO" branch --show-current)"
  echo "clone_clean=$([ -z "$(git -C "$REPO" status --porcelain)" ] && echo yes || echo NO)"
  echo "host=$(uname -srm)"; echo "opened=$(date -u +%Y-%m-%dT%H:%M:%SZ)"; } > "$E/source.$RUN.txt"
setsid nohup "$E/scripts/boot_driver.sh" "$E" "$RUN" > /dev/null 2>&1 < /dev/null &
for i in $(seq 1 90); do
    [ -f "$E/boot/$RUN.status" ] && { log "STOP: QEMU wrapper ended early: $(cat "$E/boot/$RUN.status")"; exit 1; }
    gssh true 2>/dev/null && break
    sleep 5
done
gssh true 2>/dev/null || { log "STOP: no SSH for $RUN"; exit 1; }
for i in $(seq 1 40); do
    case "$(gssh systemctl is-system-running 2>/dev/null)" in running|degraded) break;; esac
    sleep 6
done
log "$RUN: guest up, is-system-running=$(gssh systemctl is-system-running 2>/dev/null), uptime=$(gssh uptime 2>/dev/null | sed 's/^ *//')"
log "$RUN: the guest stays up. Watch it with: tail -F $E/boot/$RUN.log   |   ssh into it with: $E/scripts/gssh.sh"
