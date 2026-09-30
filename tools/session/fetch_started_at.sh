#!/bin/bash
# The StartedAt read of decision 1a (adopted 2026-09-30, prospective): the
# harness's --fetch-started-at-cmd hook (run.py STARTED_AT_FETCH_FLAGS), run
# right after the run's docker-events fetch and before the harness ingests
# the SUT resources, so that the proved-down interval of the restarted
# controller can be derived (egw_experiments.proved_down: its container id
# must be the one of the capture's die and start, its StartedAt within 1 s of
# the start, read after it). The harness runs this file as one argv split
# without a shell (shlex.split, run.py execute_collector_hook).
# Usage: fetch_started_at.sh DEST [CONTAINER]
#   DEST       the file the harness expects (<run dir>/logs/sut/controller-started-at.txt)
#   CONTAINER  the container read, egw-controller-1 when absent (the one test
#              6's restart names)
#
# WHAT IS READ, AND IN WHICH ORDER. One ssh session to the guest ('egw-tcg',
# the alias of ~/.ssh/config the runbook's helpers use) reads the container's
# id and its State.StartedAt, each with its own 'docker inspect' exactly as
# proof_restart_controller.sh reads them (as the session's own user, without
# elevation; one template per field, so an empty StartedAt reaches the host
# as empty and never as another field),
# and then the guest's clock ('date +%s'), AFTER them: the epoch is an instant
# at or after the read. The guest command runs under BusyBox ash and holds no
# bashism; its STOP lines go to stderr.
#
# WHAT IS WRITTEN. DEST, write-once (a DEST that exists stops the hook before
# the guest is reached), as four lines:
#   container=<CONTAINER>
#   container_id=<64 lower-case hex>
#   started_at=<RFC 3339 ending Z, at most nine fractional digits>
#   guest_epoch=<whole seconds>
# The lines are written to a temporary file beside DEST and moved into place
# only once every value is of its form. Anything missing or malformed - a
# session that failed, an inspect that failed or answered nothing, a value of
# another form - leaves NO file, prints a STOP line naming it on stderr and
# ends non-zero: the harness then records a failed fetch (a validity reason)
# and grants no interval.
set -u

hook_stop() {
    echo "STOP: fetch_started_at: $2" >&2
    exit "$1"
}

[ "$#" -ge 1 ] && [ "$#" -le 2 ] || hook_stop 2 "usage: fetch_started_at.sh DEST [CONTAINER]; nothing was read"
DEST=$1
C=${2:-egw-controller-1}
[ -n "$DEST" ] || hook_stop 2 "usage: fetch_started_at.sh DEST [CONTAINER]: DEST is empty; nothing was read"
case "$C" in
    '' | *[!A-Za-z0-9._-]*) hook_stop 2 "CONTAINER '$C' is not a plain container name (letters, digits, '.', '_' and '-'); nothing was read" ;;
esac
[ ! -e "$DEST" ] || hook_stop 1 "$DEST exists - the StartedAt record is write-once; nothing was read"

# read_script: the guest command, with the container's name (checked above)
# in place of @CONTAINER@.
read_script() {
    sed "s/@CONTAINER@/$C/g" << 'GUEST_READ'
cid=$(docker inspect -f '{{.Id}}' @CONTAINER@) || { echo 'STOP: docker inspect @CONTAINER@ (.Id) failed on the guest' >&2; exit 4; }
sat=$(docker inspect -f '{{.State.StartedAt}}' @CONTAINER@) || { echo 'STOP: docker inspect @CONTAINER@ (.State.StartedAt) failed on the guest' >&2; exit 4; }
epoch=$(date +%s) || { echo 'STOP: the guest clock could not be read' >&2; exit 3; }
echo "container_id=$cid"
echo "started_at=$sat"
echo "guest_epoch=$epoch"
GUEST_READ
}

reading=$(ssh egw-tcg "$(read_script)")
rc=$?
[ "$rc" -eq 0 ] || hook_stop 1 "the container $C was NOT read on the guest (ssh egw-tcg exit $rc; the guest's STOP line, if any, is above): no $DEST"

# Exactly the three lines of a reading, each once, each of its form.
R_ID='' R_STARTED='' R_EPOCH='' n_id=0 n_started=0 n_epoch=0 other=0
while IFS= read -r line; do
    case "$line" in
        container_id=*) R_ID=${line#container_id=}; n_id=$((n_id + 1)) ;;
        started_at=*) R_STARTED=${line#started_at=}; n_started=$((n_started + 1)) ;;
        guest_epoch=*) R_EPOCH=${line#guest_epoch=}; n_epoch=$((n_epoch + 1)) ;;
        *) other=$((other + 1)) ;;
    esac
done <<< "$reading"
[ "$n_id" -eq 1 ] && [ "$n_started" -eq 1 ] && [ "$n_epoch" -eq 1 ] && [ "$other" -eq 0 ] \
    || hook_stop 1 "the reading of $C is not exactly one container_id=, started_at= and guest_epoch= line: no $DEST"
[[ $R_ID =~ ^[0-9a-f]{64}$ ]] || hook_stop 1 "container_id '$R_ID' of $C is not a 64 lower-case hex container id: no $DEST"
[[ $R_STARTED =~ ^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}(\.[0-9]{1,9})?Z$ ]] \
    || hook_stop 1 "started_at '$R_STARTED' of $C is not an RFC 3339 instant ending Z (at most nine fractional digits): the instant was not read, no $DEST"
[[ $R_EPOCH =~ ^[0-9]+$ ]] || hook_stop 1 "guest_epoch '$R_EPOCH' is not a whole number of seconds: the guest clock was not read, no $DEST"

TMP=$DEST.tmp.$$
cleanup_tmp() { rm -f "$TMP"; }
printf '%s\n' "container=$C" "container_id=$R_ID" "started_at=$R_STARTED" "guest_epoch=$R_EPOCH" > "$TMP" \
    || { cleanup_tmp; hook_stop 1 "$TMP could not be written: no $DEST"; }
[ ! -e "$DEST" ] || { cleanup_tmp; hook_stop 1 "$DEST appeared during the read - the StartedAt record is write-once; it is left as it is"; }
mv -n "$TMP" "$DEST" || { cleanup_tmp; hook_stop 1 "$TMP could not be moved to $DEST: no $DEST"; }
# 'mv -n' leaves the temporary file in place when DEST appeared in between.
[ ! -e "$TMP" ] || { cleanup_tmp; hook_stop 1 "$DEST appeared during the read - the StartedAt record is write-once; it is left as it is"; }
echo "fetch_started_at: $C id ${R_ID:0:12} started $R_STARTED, read at guest epoch $R_EPOCH; written to $DEST"
