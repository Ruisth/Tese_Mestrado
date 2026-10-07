#!/bin/bash
# reviewer: read-only: which packages the pass bench exported (session, preflight, gate, row), and the close's "What remains" text
B=/tmp/g3-s4-bench/pass
ls -1 $B/out/runs/*/ $B/out/incomplete 2>&1
echo "--- attempts directory"
ls -1 $B/egw-exec/attempts
echo "--- last.out of the close (What remains)"
sed -n '/What remains/,$p' $B/last.out | cut -c1-300
echo "--- the guest-state stub lines: is OOM / unexpected restart ever varied by any scenario?"
grep -l 'oomkilled=true\|guest.down\|git.dirty\|git.head\|sha.drivers\|events_start_rc' /tmp/g3-s4-bench/*/mod/state/* /tmp/g3-s4-bench/*/ 2>/dev/null | head
ls /tmp/g3-s4-bench/*/guest.down /tmp/g3-s4-bench/*/git.dirty /tmp/g3-s4-bench/*/git.head 2>&1 | head
