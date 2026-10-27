#!/bin/bash
# Bench of the S4 operator script (stream BENCH, 2026-10-05): a minimal experiment, outside
# the script under test, on WHY harness_cmd's interruption cleanup did not run in scenario
# 'term'. It rebuilds the process chain of a row's step - a python parent holding the
# step's stdout and stderr pipes (as 'local_export exec' does), its 'bash -c' step shell,
# and in it a subshell with harness_cmd's own trap ('intr=1; echo ... >&2' on INT TERM HUP)
# running a foreground child, after which it runs a stand-in of events_cleanup - all in one
# process group, and sends TERM to that group, as 'term' does. Two variants: the step shell
# as the operator script makes it (SIGPIPE at its default), and the same with SIGPIPE
# ignored in the step shell ('trap "" PIPE'). It writes only under /tmp/g3-s4-bench/_exp.
# Usage (WSL): bs4_sigpipe.sh
set -u
D=/tmp/g3-s4-bench/_exp
[ ! -e "$D" ] || { echo "refused: $D exists"; exit 2; }
mkdir -p "$D" || exit 1
PY=/home/ruisth/egw-exec/venv/bin/python
for variant in default ignored; do
    rm -f "$D/cleanup.$variant" "$D/trap.$variant"
    pre=":"
    [ "$variant" = default ] || pre="trap '' PIPE"
    step="$pre; ( intr=; trap 'intr=1; echo \"harness_cmd: interrupted - the Docker events recorder is stopped next\" >&2; date +%s > $D/trap.$variant' INT TERM HUP; /usr/bin/sleep 60; rc=\$?; echo \"events_cleanup stand-in: unit stopped (harness status \$rc)\"; date +%s > $D/cleanup.$variant; exit \$rc )"
    setsid "$PY" -c '
import subprocess, sys, time
p = subprocess.Popen(["bash", "-c", sys.argv[1]], stdout=subprocess.PIPE, stderr=subprocess.PIPE, stdin=subprocess.DEVNULL)
p.wait()' "$step" < /dev/null > /dev/null 2>&1 &
    leader=$!
    /usr/bin/sleep 2
    echo "variant $variant: the group $leader before the TERM:"
    /usr/bin/pgrep -g "$leader" -a | cut -c1-110 | sed 's/^/    | /'
    kill -TERM -- "-$leader"
    /usr/bin/sleep 3
    echo "variant $variant: after the TERM: processes left in the group: $(/usr/bin/pgrep -g "$leader" | wc -l); the trap ran: $([ -e "$D/trap.$variant" ] && echo yes || echo no); the cleanup stand-in ran: $([ -e "$D/cleanup.$variant" ] && echo yes || echo NO)"
    /usr/bin/pgrep -g "$leader" > /dev/null && kill -TERM -- "-$leader" 2> /dev/null
done
