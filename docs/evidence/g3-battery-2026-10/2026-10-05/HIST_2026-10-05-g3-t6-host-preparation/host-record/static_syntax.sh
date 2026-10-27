#!/bin/bash
# Syntax and byte checks of the six scripts of stream HOST (S4) and of this stream's
# record scripts (WSL; read-only): bash -n, CR bytes, a byte-order mark, non-ASCII
# bytes, and shellcheck (the binary unpacked into /tmp/g3-s4-host-sc) on each script
# and on the copy its revision started from (base/), so that a warning the revision
# brought in shows apart from those the base already had. Nothing is run but the checks.
# Usage (WSL): bash host-record/static_syntax.sh   (from the preparation folder)
set -u
cd "$(dirname "$0")/.." || exit 2
SC=/tmp/g3-s4-host-sc/shellcheck
MINE="g3_hostprep.sh seal_prep.sh ops/seal_ops.sh ops/seal_ops_finish.sh ops/g3_go.sh ops/g3_wait.sh"
RECS="host-record/plan_check_bench.sh host-record/static_values.sh host-record/static_syntax.sh host-record/seal_bench.sh"
BAD=0
for f in $MINE $RECS; do
    sha=$(sha256sum "$f" | cut -c1-64)
    if bash -n "$f" 2> /tmp/g3-s4-host-sc/bash-n.err; then n=ok; else n="FAILED: $(head -c 300 /tmp/g3-s4-host-sc/bash-n.err)"; BAD=1; fi
    cr=$(tr -cd '\r' < "$f" | wc -c)
    bom=$(head -c 3 "$f" | od -An -tx1 | tr -d ' \n')
    [ "$bom" = efbbbf ] && bom=yes || bom=no
    na=$(LC_ALL=C grep -c '[^ -~	]' "$f")
    [ "$cr" -eq 0 ] && [ "$bom" = no ] && [ "$na" -eq 0 ] || BAD=1
    echo "$f: sha256 $sha; bash -n $n; CR bytes $cr; BOM $bom; lines with non-ASCII bytes $na"
done
echo
if [ -x "$SC" ]; then
    echo "shellcheck $("$SC" --version | sed -n 's/^version: //p') (-s bash, default severity), new script against its base copy:"
    for f in $MINE; do
        "$SC" -s bash -f gcc "$f" 2>&1 | sed 's/^[^:]*:[0-9]*:[0-9]*: //' | sort | uniq -c > /tmp/g3-s4-host-sc/new.txt
        if [ -f "base/$f" ]; then
            "$SC" -s bash -f gcc "base/$f" 2>&1 | sed 's/^[^:]*:[0-9]*:[0-9]*: //' | sort | uniq -c > /tmp/g3-s4-host-sc/base.txt
        else : > /tmp/g3-s4-host-sc/base.txt; fi
        echo "== $f: $(awk '{s += $1} END {print s + 0}' /tmp/g3-s4-host-sc/new.txt) finding(s); base: $(awk '{s += $1} END {print s + 0}' /tmp/g3-s4-host-sc/base.txt)"
        sed 's/^/   now:  /' /tmp/g3-s4-host-sc/new.txt
        diff /tmp/g3-s4-host-sc/base.txt /tmp/g3-s4-host-sc/new.txt > /dev/null || sed 's/^/   base: /' /tmp/g3-s4-host-sc/base.txt
    done
    echo "== the record scripts:"
    for f in $RECS; do echo "   $f: $("$SC" -s bash -f gcc "$f" 2>&1 | grep -c .) finding(s)"; "$SC" -s bash -f gcc "$f" 2>&1 | sed 's/^[^:]*:/      line /'; done
else
    echo "shellcheck: not available at $SC"
fi
echo
echo "summary: $([ "$BAD" -eq 0 ] && echo 'bash -n passes, no CR, no BOM, ASCII only, for every script' || echo 'a script FAILED one of the checks above')"
[ "$BAD" -eq 0 ]
