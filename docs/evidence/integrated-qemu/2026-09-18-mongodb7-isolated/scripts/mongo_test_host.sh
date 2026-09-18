#!/bin/bash
# Host-side driver of the isolated MongoDB 7 test (authorised 2026-09-18):
# boot the integrated guest, run phase 1, power off, boot again, run phase 2,
# power off. No stack deployment, no campaign, no gate. Usage:
#   mongo_test_host.sh <evidence-dir>
set -u
E=$1
REPO=/home/ruisth/yocto/egw
BOOT_DRIVER=$E/scripts/boot_driver.sh
SSHO=(-i "$HOME/.ssh/egw_campaign" -p 2222 -o IdentitiesOnly=yes -o BatchMode=yes -o StrictHostKeyChecking=yes
      -o UserKnownHostsFile="$E/boot/known_hosts" -o ConnectTimeout=10 -o ServerAliveInterval=30 -o LogLevel=ERROR)
mkdir -p "$E/boot" "$E/guest"
log() { echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] $*" | tee -a "$E/driver.log"; }

boot() { # boot <run-name>
    local run=$1 i
    if ss -ltn | grep -qE ':(2222|8883) '; then log "STOP: host port 2222 or 8883 busy"; return 1; fi
    setsid nohup "$BOOT_DRIVER" "$E" "$run" > /dev/null 2>&1 < /dev/null &
    for i in $(seq 1 90); do
        [ -f "$E/boot/$run.status" ] && { log "STOP: QEMU wrapper ended early: $(cat "$E/boot/$run.status")"; return 1; }
        ssh "${SSHO[@]}" egw@127.0.0.1 true 2>/dev/null && break
        sleep 5
    done
    ssh "${SSHO[@]}" egw@127.0.0.1 true 2>/dev/null || { log "STOP: no SSH for $run"; return 1; }
    for i in $(seq 1 40); do
        case "$(ssh "${SSHO[@]}" egw@127.0.0.1 systemctl is-system-running 2>/dev/null)" in running|degraded) break;; esac
        sleep 6
    done
    log "$run: guest up, is-system-running=$(ssh "${SSHO[@]}" egw@127.0.0.1 systemctl is-system-running 2>/dev/null)"
}

poweroff() { # poweroff <run-name>
    local run=$1 i
    ssh "${SSHO[@]}" egw@127.0.0.1 'sync; sudo -n poweroff' >/dev/null 2>&1
    for i in $(seq 1 60); do [ -f "$E/boot/$run.status" ] && break; sleep 3; done
    log "$run: $(cat "$E/boot/$run.status" 2>/dev/null || echo 'NO STATUS FILE - QEMU may still be running')"
    [ -f "$E/boot/$run.status" ]
}

date -u +%Y-%m-%dT%H:%M:%SZ > "$E/test.started"
{ echo "source_commit=$(git -C "$REPO" rev-parse HEAD)"; echo "branch=$(git -C "$REPO" branch --show-current)"; echo "clone_clean=$([ -z "$(git -C "$REPO" status --porcelain)" ] && echo yes || echo NO)"; } > "$E/source.txt"
# The host key of the guest is the one recorded during integrated-boot-02.
cp -p "$HOME/yocto/evidence-candidates/2026-09-18-integrated-3209b17/boot/known_hosts" "$E/boot/known_hosts"

RESULT=0
if boot mongo-boot-01; then
    log "phase 1 starts"
    ssh "${SSHO[@]}" egw@127.0.0.1 'sh -s' < "$E/scripts/mongo_guest_phase1.sh" > "$E/guest/phase1.txt" 2>&1
    log "phase 1 ssh exit=$? ; $(grep -E '^PHASE 1 RESULT' "$E/guest/phase1.txt" || echo 'PHASE 1 RESULT line missing')"
    ssh "${SSHO[@]}" egw@127.0.0.1 'sudo -n journalctl -b --no-pager' > "$E/guest/journal-mongo-boot-01.txt" 2>&1
    poweroff mongo-boot-01 || RESULT=1
else
    RESULT=1
fi

if [ "$RESULT" = 0 ] && grep -q '^PHASE 1 RESULT: failed_checks=0$' "$E/guest/phase1.txt"; then
    if boot mongo-boot-02; then
        log "phase 2 starts"
        ssh "${SSHO[@]}" egw@127.0.0.1 'sh -s' < "$E/scripts/mongo_guest_phase2.sh" > "$E/guest/phase2.txt" 2>&1
        log "phase 2 ssh exit=$? ; $(grep -E '^PHASE 2 RESULT' "$E/guest/phase2.txt" || echo 'PHASE 2 RESULT line missing')"
        ssh "${SSHO[@]}" egw@127.0.0.1 'sudo -n journalctl -b --no-pager' > "$E/guest/journal-mongo-boot-02.txt" 2>&1
        poweroff mongo-boot-02 || RESULT=1
    else
        RESULT=1
    fi
else
    log "phase 2 NOT run: phase 1 did not end with failed_checks=0 (stop and report)"
    RESULT=1
fi

# The sealed G1 build tree must be untouched.
PREV=$HOME/yocto/evidence-candidates/2026-09-18-integrated-68f9ae7
( cd "$REPO/src/yocto/build/tmp/deploy/images/qemuarm64" && sha256sum -c "$PREV/g1-deploy-before.sha256" ) > "$E/g1-after-mongo-test.sha256check.txt" 2>&1 || RESULT=1
grep -q '^PHASE 2 RESULT: failed_checks=0$' "$E/guest/phase2.txt" 2>/dev/null || RESULT=1
echo "exit=$RESULT finished=$(date -u +%Y-%m-%dT%H:%M:%SZ)" > "$E/test.status"
log "done: $(cat "$E/test.status")"
