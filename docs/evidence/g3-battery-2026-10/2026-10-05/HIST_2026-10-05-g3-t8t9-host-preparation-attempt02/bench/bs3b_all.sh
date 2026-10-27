#!/bin/bash
# Bench of the second opening of S3: runs the named scenarios of bs3b_run.sh side by side
# (each in a bench of its own under /tmp/g3-s3b-bench/<scenario>) and keeps each console as
# record/<scenario>.console.txt. A console that exists is never overwritten: it is moved to
# record/superseded/ under a name that holds the time it was moved.
# Usage (WSL): bs3b_all.sh <scenario>...
set -u
HERE=$(cd "$(dirname "$0")" && pwd)
REC=$HERE/record
mkdir -p "$REC" || exit 1
[ "$#" -gt 0 ] || { echo "usage: bs3b_all.sh <scenario>..."; exit 2; }
for sc in "$@"; do
    f=$REC/$sc.console.txt
    if [ -e "$f" ]; then
        mkdir -p "$REC/superseded" || exit 1
        mv "$f" "$REC/superseded/$sc.$(date -u +%Y%m%dT%H%M%SZ).console.txt"
    fi
    bash "$HERE/bs3b_run.sh" "$sc" > "$f" 2>&1 &
done
wait
for sc in "$@"; do
    f=$REC/$sc.console.txt
    printf '%-5s %s | %s\n' "$sc" "$(tail -n 1 "$f" | cut -c1-90)" "$(head -n 1 "$f" | sed 's/^script run: sha256 //' | cut -c1-64)"
    grep -n 'CHECK FAILED' "$f" | cut -c1-300
done
