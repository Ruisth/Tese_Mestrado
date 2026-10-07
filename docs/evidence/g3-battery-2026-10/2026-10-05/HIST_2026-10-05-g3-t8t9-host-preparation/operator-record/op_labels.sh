#!/bin/bash
# Stream OPERATOR: the script itself (its dispatch included) on the subcommands that are
# refused before anything is started, in the isolated tree made by op_setup.sh. 'open S3'
# is NOT run here (it would start the session drivers: that is the bench stream's work,
# with stub drivers).
# Usage (WSL): op_labels.sh /tmp/g3-s3-op-<name>
set -u
B=${1:?usage: op_labels.sh /tmp/g3-s3-op-<name>}
HERE=$(cd "$(dirname "$0")" && pwd)
# shellcheck source=/dev/null
. "$HERE/op_env.sh"
echo "## $(date -u +%Y-%m-%dT%H:%M:%SZ) script under test: <scratchpad>/${G#"$S"/} sha256 $(/usr/bin/sha256sum "$G" | cut -d' ' -f1)"
run() {
    echo "--- g3_battery.sh $*"
    bash "$G" "$@" < /dev/null 2>&1 | sed "s#$B/##g" | cut -c1-420
    echo "-> exit ${PIPESTATUS[0]}"
}
echo "state directory before: $(ls -A "$EGW_G3_STATE" 2> /dev/null | tr '\n' ' ')"
run open S1
run open S2
run open S4
run open
run row t6
run row t1-smokes
run classify t7-ditto finished valid pass reason next
run term t6
run row t8
run row t9
run classify t8 finished valid pass reason next
run term t8
run restart
run status
echo "state directory after: $(ls -A "$EGW_G3_STATE" 2> /dev/null | tr '\n' ' ')"
echo "session or row state files written: $(ls "$EGW_G3_STATE"/session-*.env "$EGW_G3_STATE"/row-t?.env 2> /dev/null | wc -l)"
echo "## $(date -u +%Y-%m-%dT%H:%M:%SZ) ended"
