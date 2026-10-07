#!/bin/bash
# reviewer: read-only: the helper file's harness_cmd / events_* and the stub recorder of the bench
B=/tmp/g3-s4-bench/pass
A=$(ls -d $B/egw-exec/attempts/*_g3-qualification-t6_attempt02 | head -n 1)
sha256sum "$A/environment/t6.sh" "$B/home/egw-tcg/itest-helpers.sh" "$B/home/egw-tcg/tunnel.sh"
echo "--- harness_cmd / events_start / events_cleanup in the helper file"
awk '/^(harness_cmd|events_start|events_cleanup|stop)\(\)/,/^}/' "$B/home/egw-tcg/itest-helpers.sh" | cut -c1-400
echo "--- stub events_capture.sh of the bench copy"
cat "$B/repo/tools/session/events_capture.sh" | cut -c1-300
echo "--- the stub recorder state after pass"
ls "$B/mod/state"
cat "$B/mod/state/capture.log"
for f in "$B"/mod/state/unit-*; do echo "$f: $(cat "$f")"; done
