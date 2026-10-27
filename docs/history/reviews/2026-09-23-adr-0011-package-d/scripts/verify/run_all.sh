#!/usr/bin/env bash
# Re-run the refutation scripts of verify_figures.md. Python parts INSIDE WSL Ubuntu-24.04:
#   wsl -d Ubuntu-24.04 --exec bash -lc 'bash "<this directory>/run_all.sh"'
# v10_anchors.sh uses read-only git (show / diff --stat / grep / ls-tree / merge-base --is-ancestor) on the
# Windows worktree and is run from Git Bash:  bash v10_anchors.sh <worktree> > out/v10_anchors.out.txt
# Every source is opened read-only; outputs go to out/ beside this file only.
set -euo pipefail
export PYTHONDONTWRITEBYTECODE=1
HERE=$(cd "$(dirname "$0")" && pwd)
cd "$HERE"
mkdir -p out
PY=~/egw-exec/venv/bin/python
for s in v01_populations v02_rates_queue v03_split_budget v04_little v05_replays v06_resources \
         v08_restart v09_adr_arith v12_reasoning_checks; do
  "$PY" "$s.py" > "out/$s.out.txt" 2>&1
  echo "$s: $(wc -l < "out/$s.out.txt") lines"
done
bash v11_libs.sh > out/v11_libs.out.txt 2>&1
echo "v11_libs: $(wc -l < out/v11_libs.out.txt) lines"
