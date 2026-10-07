#!/bin/bash
# One final pass of every bench scenario on the final bytes of g3_battery.sh, as bench-notes section 8 lists it,
# launched detached so that 'before' and 'after' fall within one run of the distribution.
set -u
HERE=$(cd "$(dirname "$0")" && pwd)
echo "final pass started $(date -u +%FT%TZ); g3_battery.sh $(sha256sum "$HERE/../g3_battery.sh" | cut -d' ' -f1)"
bash "$HERE/bs3_short.sh" > "$HERE/record/short-variant.txt" 2>&1; echo "short variant exit=$?"
bash "$HERE/bs3_untouched.sh" before /tmp/g3-s3-bench/_untouched > "$HERE/record/untouched.before.console.txt" 2>&1; echo "untouched before exit=$?"
bash "$HERE/bs3_all.sh" s1 s2iii s1b s12 s2i s2ii s2iv s2v s2vi s2vii s3 s4a s4b s5a s5b s5c s5d s5e s6 s7i s7ii s7iii s8a s8b s8c s9 s10a s10b s10c s10d s11 s11b s13 s14 s15 s16 s17 s18
echo "bs3_all exit=$?"
bash "$HERE/bs3_sent.sh" > "$HERE/record/sent-to-guest.all.txt" 2>&1; echo "sent exit=$?"
bash "$HERE/bs3_untouched.sh" after /tmp/g3-s3-bench/_untouched > "$HERE/record/untouched.after.console.txt" 2>&1; echo "untouched after exit=$?"
echo "final pass ended $(date -u +%FT%TZ)"
