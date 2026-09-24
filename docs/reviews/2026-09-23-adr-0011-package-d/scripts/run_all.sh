#!/usr/bin/env bash
# Re-run every package-D v2 script and keep its standard output beside it.
# Run INSIDE WSL Ubuntu-24.04 from any directory, for example:
#   wsl -d Ubuntu-24.04 --exec bash -lc 'bash "<this directory>/run_all.sh"'
# Read-only against every source; writes only ../out/<script>.out.txt.
set -euo pipefail
export PYTHONDONTWRITEBYTECODE=1   # no __pycache__ beside the scripts
HERE=$(cd "$(dirname "$0")" && pwd)
OUT="$HERE/../out"
mkdir -p "$OUT"
PY=~/egw-exec/venv/bin/python
for s in s01_populations s02_rates_and_queue s03_wait_and_budget s04_little_identity \
         s05_warmup_inheritance s06_resources s07_probe_sizing s08_corrections; do
  "$PY" "$HERE/$s.py" > "$OUT/$s.out.txt" 2>&1
  echo "$s: exit 0, $(wc -l < "$OUT/$s.out.txt") lines -> out/$s.out.txt"
done
