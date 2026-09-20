#!/bin/bash
# Collect the boot journal and the stack state, power the guest off cleanly and
# confirm the sealed G1 build artefacts are untouched.
# Usage: session_close.sh <evidence-dir> [keep-stack-state]
#
# Two exit statuses, because they are two different facts. RESULT=1 is the
# controlled stop itself failing (an unreachable guest, a QEMU that did not end,
# G1 artefacts that were not confirmed), which guest_session_close.sh reports as
# a failed controlled stop. RECORD=1 is the guest going off as asked while a
# record of the close was NOT kept (its boot journal, its final state): the
# script then exits 3, which the driver reads as an incomplete record, never as
# a failed stop. A collection is kept only when the command succeeded AND wrote
# something: its error text goes beside the file, never into it.
set -u
E=$1
. "$E/scripts/session_common.sh"
RUN=$(run_name)
REPO=${EGW_YOCTO_CHECKOUT:-/home/ruisth/yocto/egw}
PREV=${EGW_G1_REFERENCE:-$HOME/yocto/evidence-candidates/2026-09-18-integrated-68f9ae7}
RESULT=0
RECORD=0

# kept FILE WHAT: the collection reached FILE and is not empty.
kept() {
    [ -s "$1" ] && return 0
    log "$RUN: STOP: $2 is empty ($1)"
    RECORD=1
}

if gssh true 2>/dev/null; then
    log "$RUN: collecting the final guest state"
    gssh 'sudo -n journalctl -b --no-pager' > "$E/guest/journal-$RUN.txt" 2> "$E/guest/journal-$RUN.err" \
        || { log "$RUN: STOP: the boot journal was not collected (see guest/journal-$RUN.err)"; RECORD=1; }
    kept "$E/guest/journal-$RUN.txt" "the boot journal"
    gssh 'cd /opt/egw/deployment 2>/dev/null && docker compose --env-file .env --env-file images.lock.env ps -a; docker ps -a; docker images --digests; df -h /var/lib/docker' > "$E/guest/final-state-$RUN.txt" 2> "$E/guest/final-state-$RUN.err" \
        || { log "$RUN: STOP: the final guest state was not collected (see guest/final-state-$RUN.err)"; RECORD=1; }
    kept "$E/guest/final-state-$RUN.txt" "the final guest state"
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
# The G1 reference lists the G1 artefacts (Image, egw-image-qemuarm64.rootfs
# .ext4), which the NON-integrated build produced: they live in
# src/yocto/build, not in the build-integrated directory this session boots
# from. An absent directory or an absent reference is its own message, never a
# checksum that "failed": each still keeps RESULT at 1, because the artefacts
# were not confirmed untouched.
G1=$REPO/src/yocto/build/tmp/deploy/images/qemuarm64
CHECK=$E/g1-after-$RUN.sha256check.txt
if [ ! -d "$G1" ]; then
    echo "STOP: the G1 build directory is absent: $G1 (the sealed G1 artefacts were NOT checked)" > "$CHECK"
    RESULT=1
elif [ ! -f "$PREV/g1-deploy-before.sha256" ]; then
    echo "STOP: the G1 reference file is absent: $PREV/g1-deploy-before.sha256 (nothing to check against)" > "$CHECK"
    RESULT=1
else
    ( cd "$G1" && sha256sum -c "$PREV/g1-deploy-before.sha256" ) > "$CHECK" 2>&1 || RESULT=1
    grep -q FAILED "$CHECK" && RESULT=1
fi
log "$RUN: G1 artefacts: $(tail -n 1 "$CHECK")"
# A failed controlled stop outranks a record that was not kept: the driver
# reads 1 as the stop having failed (5) and 3 as the close being recorded
# incompletely (invalid, inconclusive, 3).
STATUS=$RESULT
[ "$RESULT" -ne 0 ] || [ "$RECORD" -eq 0 ] || STATUS=3
echo "exit=$STATUS closed=$(date -u +%Y-%m-%dT%H:%M:%SZ)" > "$E/$RUN.session.status"
log "$RUN: session closed: $(cat "$E/$RUN.session.status")"
exit "$STATUS"
