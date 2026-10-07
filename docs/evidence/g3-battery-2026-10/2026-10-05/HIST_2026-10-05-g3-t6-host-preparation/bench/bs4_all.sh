#!/bin/bash
# Bench of the S4 operator script (stream BENCH of the S4 preparation, 2026-10-05): runs the
# named scenarios of bs4_run.sh side by side (each in a bench of its own under
# /tmp/g3-s4-bench/<scenario>) and keeps each console as record/<scenario>.console.txt. A
# console that exists is never overwritten: it is moved to record/superseded/ under a name
# that holds the time it was moved. Adapted from S3b's bench/bs3b_all.sh.
# Usage (WSL): bs4_all.sh <scenario>...   (or 'all' for every scenario)
set -u
HERE=$(cd "$(dirname "$0")" && pwd)
REC=$HERE/record
ALL="pass labels fresh-a fresh-b fresh-c fresh-d fresh-e fresh-f fresh-g id-a id-b id-c id-d pf-1 pf-3 out-h1 out-h2 out-h3 out-gaveup out-delta4 out-eo4 out-eo1 term afterhalt integrity"
mkdir -p "$REC" || exit 1
[ "$#" -gt 0 ] || { echo "usage: bs4_all.sh <scenario>... | all"; exit 2; }
[ "$1" != all ] || set -- $ALL
[ -d /tmp/g3-s4-bench/_src ] || { echo "refused: run bs4_src.sh first"; exit 2; }
echo "## $(date -u +%Y-%m-%dT%H:%M:%SZ) bs4_all.sh: $*; script under test sha256 $(sha256sum < "$HERE/../g3_battery.sh" | cut -d' ' -f1)"
for sc in "$@"; do
    f=$REC/$sc.console.txt
    if [ -e "$f" ]; then
        mkdir -p "$REC/superseded" || exit 1
        mv "$f" "$REC/superseded/$sc.$(date -u +%Y%m%dT%H%M%SZ).console.txt"
    fi
    bash "$HERE/bs4_run.sh" "$sc" > "$f" 2>&1 &
done
wait
echo "## $(date -u +%Y-%m-%dT%H:%M:%SZ) every scenario ended"
for sc in "$@"; do
    f=$REC/$sc.console.txt
    printf '%-11s %s | %s\n' "$sc" "$(tail -n 1 "$f" | cut -c1-90)" "$(head -n 1 "$f" | sed 's/^script run: sha256 //' | cut -c1-64)"
    grep -n 'CHECK FAILED' "$f" | cut -c1-300
done
