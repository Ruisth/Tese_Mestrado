#!/bin/bash
# Stream BENCH: what went to the stub guest and the stub host commands, read after the
# benches from each bench as its scenario left it (/tmp/g3-s3-bench/<scenario>), in the
# form of record/sent-to-guest.all.txt. Read-only; prints the table on stdout. It must run
# in the same WSL boot as the benches (/tmp is emptied at every boot of the distribution).
# Usage (WSL): bs3_sent.sh > record/sent-to-guest.all.txt
set -u
HERE=$(cd "$(dirname "$0")" && pwd)
ROOT=/tmp/g3-s3-bench
echo "## $(date -u +%Y-%m-%dT%H:%M:%SZ) read after the benches, from each bench as its scenario left it (mod/state/ssh.log: every ssh call of the bench, the wrapper and the test module stub alike; mod/state/calls.log: the stub host commands)"
echo "## columns: scenario | ssh calls logged | reboot commands | calls matching the test module pattern for a command that starts, restarts or brings up something | compose stop calls (the close) | pkill or killall calls | the consoles own check of the same count"
for d in "$ROOT"/s[0-9]*/; do
    sc=$(basename "$d")
    s=$d/mod/state
    # one call = one line starting 'ssh [' (an argument that holds a script of several lines
    # continues on the next lines of the log; the version that made the table of 2026-10-05
    # counted lines, not calls, in this column)
    n_ssh=$(grep -c '^ssh \[' "$s/ssh.log" 2> /dev/null)
    n_reboot=$(grep -c 'sudo systemctl reboot' "$s/ssh.log" 2> /dev/null)
    n_up=$(grep -c -E '(docker( compose)?|\$DC|systemctl)\b[^"'"'"';]*\b(up|start|restart)\b' "$s/ssh.log" 2> /dev/null)
    n_stop=$(grep -c -E 'stop -t [0-9]+' "$s/ssh.log" 2> /dev/null)
    n_kill=$(grep -c 'PATTERN-KILL' "$s/calls.log" 2> /dev/null)
    own=$(grep -c '^CHECK ok: commands that start, restart or bring up anything, sent to the stub guest' "$HERE/record/$sc.console.txt" 2> /dev/null)
    if [ "${own:-0}" -gt 0 ]; then own="in the console ($own)"; else own="not in the console"; fi
    printf '%-6s | %4s | %s | %s | %s | %s | %s\n' "$sc" "${n_ssh:-0}" "${n_reboot:-0}" "${n_up:-0}" "${n_stop:-0}" "${n_kill:-0}" "$own"
done
