#!/bin/bash
# Boot the integrated guest, run one guest script over SSH, keep its transcript,
# save the boot journal, power the guest off cleanly and confirm the sealed G1
# build artefacts are untouched. Usage:
#   guest_session.sh <evidence-dir> <run-name> <guest-script> <transcript-name>
set -u
E=$1; RUN=$2; GUEST_SCRIPT=$3; OUT=$4
REPO=/home/ruisth/yocto/egw
PREV=$HOME/yocto/evidence-candidates/2026-09-18-integrated-68f9ae7
KNOWN=$HOME/yocto/evidence-candidates/2026-09-18-integrated-3209b17/boot/known_hosts
mkdir -p "$E/boot" "$E/guest"
[ -f "$E/boot/known_hosts" ] || cp -p "$KNOWN" "$E/boot/known_hosts"
SSHO=(-i "$HOME/.ssh/egw_campaign" -p 2222 -o IdentitiesOnly=yes -o BatchMode=yes -o StrictHostKeyChecking=yes
      -o UserKnownHostsFile="$E/boot/known_hosts" -o ConnectTimeout=10 -o ServerAliveInterval=30 -o LogLevel=ERROR)
log() { echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] $*" | tee -a "$E/driver.log"; }

RESULT=0
if ss -ltn | grep -qE ':(2222|8883) '; then log "STOP: host port 2222 or 8883 busy"; exit 1; fi
{ echo "source_commit=$(git -C "$REPO" rev-parse HEAD)"; echo "branch=$(git -C "$REPO" branch --show-current)"; echo "clone_clean=$([ -z "$(git -C "$REPO" status --porcelain)" ] && echo yes || echo NO)"; } > "$E/source.$RUN.txt"
setsid nohup "$E/scripts/boot_driver.sh" "$E" "$RUN" > /dev/null 2>&1 < /dev/null &
for i in $(seq 1 90); do
    [ -f "$E/boot/$RUN.status" ] && { log "STOP: QEMU wrapper ended early: $(cat "$E/boot/$RUN.status")"; exit 1; }
    ssh "${SSHO[@]}" egw@127.0.0.1 true 2>/dev/null && break
    sleep 5
done
ssh "${SSHO[@]}" egw@127.0.0.1 true 2>/dev/null || { log "STOP: no SSH for $RUN"; exit 1; }
for i in $(seq 1 40); do
    case "$(ssh "${SSHO[@]}" egw@127.0.0.1 systemctl is-system-running 2>/dev/null)" in running|degraded) break;; esac
    sleep 6
done
log "$RUN: guest up, is-system-running=$(ssh "${SSHO[@]}" egw@127.0.0.1 systemctl is-system-running 2>/dev/null)"

ssh "${SSHO[@]}" egw@127.0.0.1 'sh -s' < "$GUEST_SCRIPT" > "$E/guest/$OUT" 2>&1
log "$RUN: guest script ssh exit=$? ; $(grep -aE ' RESULT: ' "$E/guest/$OUT" | tail -1)"
ssh "${SSHO[@]}" egw@127.0.0.1 'sudo -n journalctl -b --no-pager' > "$E/guest/journal-$RUN.txt" 2>&1
ssh "${SSHO[@]}" egw@127.0.0.1 'sync; sudo -n poweroff' >/dev/null 2>&1
for i in $(seq 1 60); do [ -f "$E/boot/$RUN.status" ] && break; sleep 3; done
log "$RUN: $(cat "$E/boot/$RUN.status" 2>/dev/null || echo 'NO STATUS FILE - QEMU may still be running')"
[ -f "$E/boot/$RUN.status" ] || RESULT=1
( cd "$REPO/src/yocto/build/tmp/deploy/images/qemuarm64" && sha256sum -c "$PREV/g1-deploy-before.sha256" ) > "$E/g1-after-$RUN.sha256check.txt" 2>&1 || RESULT=1
grep -aqE ' RESULT: failed_checks=0$' "$E/guest/$OUT" || RESULT=1
echo "exit=$RESULT finished=$(date -u +%Y-%m-%dT%H:%M:%SZ)" > "$E/$RUN.session.status"
log "$RUN: session done: $(cat "$E/$RUN.session.status")"
