#!/bin/bash
# Stream OPERATOR: static readings of g3_battery.sh (nothing is run from it but 'bash -n').
# Usage (WSL): op_static.sh
set -u
HERE=$(cd "$(dirname "$0")" && pwd)
P=$(cd "$HERE/.." && pwd)
G=$P/g3_battery.sh
SC=$HOME/egw-exec/venv/bin/shellcheck      # the execution venv's, run read-only
echo "## $(date -u +%Y-%m-%dT%H:%M:%SZ) g3_battery.sh sha256 $(sha256sum "$G" | cut -d' ' -f1), $(wc -l < "$G") lines, $(grep -c $'\r' "$G") line(s) with a carriage return"
bash -n "$G" && echo "bash -n: clean (bash $BASH_VERSION)"
"$SC" -S error "$G" > /dev/null; echo "shellcheck $("$SC" --version | sed -n 's/^version: //p') -S error: exit $?"
"$SC" -S warning "$G" > /dev/null; echo "shellcheck -S warning: exit $? (four SC2043 directives stand above the one-label loops)"
echo
echo "--- diff against base/g3_battery.sh (the draft, sha256 $(sha256sum "$P/base/g3_battery.sh" | cut -d' ' -f1))"
diff "$P/base/g3_battery.sh" "$G" | grep -c '^<' | sed 's/^/lines removed or changed (<): /'
diff "$P/base/g3_battery.sh" "$G" | grep -c '^>' | sed 's/^/lines added or changed (>): /'
echo
echo "--- comments that name S3, by point"
grep -n -o -E 'S3 \((point [0-9]+|condition B[^)]*)[^)]*\)|^# S3:' "$G" | sed 's/^/  /'
echo
echo "--- point 12: every line that holds 'compose', 'docker start', 'restart' or 'session_open.sh' outside a comment"
grep -n -E 'compose|docker start|restart|session_open\.sh' "$G" | grep -v -E '^[0-9]+:[[:space:]]*#' | cut -c1-200 | sed 's/^/  /'
echo
echo "--- every 'kill' outside a comment"
grep -n -E '(^|[^a-z_-])kill( |$)' "$G" | grep -v -E '^[0-9]+:[[:space:]]*#' | cut -c1-200 | sed 's/^/  /'
echo
echo "--- every 'timeout' as a command word outside a comment"
grep -n -E '(^|[ (;])timeout "?\$|command -v timeout' "$G" | grep -v -E '^[0-9]+:[[:space:]]*#' | cut -c1-200 | sed 's/^/  /'
echo
echo "--- identifiers: -q2 on lines that are not comments"
grep -n -E -- '-q2' "$G" | grep -v -E '^[0-9]+:[[:space:]]*#' | cut -c1-160 | sed 's/^/  /'
echo "--- identifiers: -q1 on lines that are not comments (the battery's rows, reached by no row of S3)"
grep -n -E -- '-q1' "$G" | grep -v -E '^[0-9]+:[[:space:]]*#' | cut -c1-160 | sed 's/^/  /'
echo
echo "--- labels: every 'for l in' and every use of the row lists"
grep -n -E 'for l in |ROWS_S[0-9]' "$G" | cut -c1-160 | sed 's/^/  /'
