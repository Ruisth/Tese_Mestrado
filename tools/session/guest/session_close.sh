#!/bin/bash
# Collect the boot journal and the stack state, power the guest off cleanly and
# confirm the sealed G1 build artefacts are untouched.
# Usage: session_close.sh <evidence-dir> [keep-stack-state]
set -u
E=$1
. "$E/scripts/session_common.sh"
RUN=$(run_name)
REPO=${EGW_YOCTO_CHECKOUT:-/home/ruisth/yocto/egw}
PREV=${EGW_G1_REFERENCE:-$HOME/yocto/evidence-candidates/2026-09-18-integrated-68f9ae7}
RESULT=0

if gssh true 2>/dev/null; then
    log "$RUN: collecting the final guest state"
    gssh 'sudo -n journalctl -b --no-pager' > "$E/guest/journal-$RUN.txt" 2>&1
    gssh 'cd /opt/egw/deployment 2>/dev/null && docker compose --env-file .env --env-file images.lock.env ps -a; docker ps -a; docker images --digests; df -h /var/lib/docker' > "$E/guest/final-state-$RUN.txt" 2>&1
    gssh 'sync; sudo -n poweroff' > /dev/null 2>&1
else
    log "$RUN: the guest was already unreachable over SSH"
    RESULT=1
fi
for i in $(seq 1 60); do [ -f "$E/boot/$RUN.status" ] && break; sleep 3; done
if [ -f "$E/boot/$RUN.status" ]; then
    log "$RUN: QEMU ended: $(cat "$E/boot/$RUN.status")"
else
    log "$RUN: STOP: QEMU did not end; it is still running"
    RESULT=1
fi
( cd "$REPO/src/yocto/build/tmp/deploy/images/qemuarm64" && sha256sum -c "$PREV/g1-deploy-before.sha256" ) > "$E/g1-after-$RUN.sha256check.txt" 2>&1 || RESULT=1
grep -q FAILED "$E/g1-after-$RUN.sha256check.txt" && RESULT=1
echo "exit=$RESULT closed=$(date -u +%Y-%m-%dT%H:%M:%SZ)" > "$E/$RUN.session.status"
log "$RUN: session closed: $(cat "$E/$RUN.session.status")"
exit "$RESULT"
