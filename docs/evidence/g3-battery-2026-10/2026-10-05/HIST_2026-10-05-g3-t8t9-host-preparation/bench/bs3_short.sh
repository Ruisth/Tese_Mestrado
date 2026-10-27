#!/bin/bash
# Stream BENCH: the short-timing variant of g3_battery.sh, used by every scenario other
# than the success pass (s1) and the 900 s expiry (s2iii), which run the final bytes.
# ONLY the two wait constants differ: T8_SSH_WAIT_S (900 -> 48) and T8_SSH_POLL_S (10 -> 3).
# T8_SSH_READ_S (20) and everything else are the final bytes'. The variant is written
# beside this file, and its sha256, the final bytes' sha256 and the two differing lines
# are printed (kept in record/short-variant.txt by the caller).
# Usage: bs3_short.sh            (run from anywhere; writes g3_battery.short.sh here)
set -u
HERE=$(cd "$(dirname "$0")" && pwd)
FINAL=$HERE/../g3_battery.sh
SHORT=$HERE/g3_battery.short.sh
sed -e 's/^T8_SSH_WAIT_S=900 /T8_SSH_WAIT_S=48  /' -e 's/^T8_SSH_POLL_S=10 /T8_SSH_POLL_S=3  /' "$FINAL" > "$SHORT.tmp" || exit 1
mv "$SHORT.tmp" "$SHORT" || exit 1
chmod +x "$SHORT"
echo "## $(date -u +%Y-%m-%dT%H:%M:%SZ) the short-timing variant"
echo "final bytes:   g3_battery.sh           sha256 $(sha256sum "$FINAL" | cut -d' ' -f1)  $(wc -l < "$FINAL") lines"
echo "short variant: bench/g3_battery.short.sh sha256 $(sha256sum "$SHORT" | cut -d' ' -f1)  $(wc -l < "$SHORT") lines"
echo "differing lines ($(diff "$FINAL" "$SHORT" | grep -c '^[<>]') lines of diff output: '<' final, '>' variant):"
diff "$FINAL" "$SHORT"
n=$(diff "$FINAL" "$SHORT" | grep -c '^<')
bash -n "$SHORT" && echo "bash -n: clean" || { echo "bash -n FAILED"; exit 1; }
[ "$n" = 2 ] || { echo "REFUSED: $n lines differ, not 2"; exit 1; }
echo "carriage returns in the variant: $(tr -cd '\r' < "$SHORT" | wc -c)"
