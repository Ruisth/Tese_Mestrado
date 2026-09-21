#!/bin/bash
# Run one script on the running guest and keep its transcript.
# Usage: session_run.sh <evidence-dir> <guest-script> <transcript-name>
set -u
E=$1; SCRIPT=$2; OUT=$3
. "$E/scripts/session_common.sh"
RUN=$(run_name)
[ -f "$SCRIPT" ] || { log "STOP: guest script $SCRIPT not found"; exit 1; }
gssh true 2>/dev/null || { log "STOP: the guest is not reachable over SSH"; exit 1; }
log "$RUN: running $(basename "$SCRIPT") -> guest/$OUT"
gssh 'sh -s' < "$SCRIPT" > "$E/guest/$OUT" 2>&1
RC=$?
LAST=$(grep -aE ' RESULT: ' "$E/guest/$OUT" | tail -1)
log "$RUN: $(basename "$SCRIPT") ssh exit=$RC ; ${LAST:-no RESULT line}"
[ "$RC" = 0 ] || exit "$RC"
case "$LAST" in *failed_checks=0) exit 0;; "") exit 0;; *) exit 1;; esac
