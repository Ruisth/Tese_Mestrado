#!/usr/bin/env bash
# Runs the four read-only checks behind ../../verify_constraints.md and writes
# only ../../out/verify_constraints/<script>.out.txt. Starts no guest, touches
# no network, runs no git command that changes state.
# From Git Bash on Windows:  bash <this file>
# (vc01, vc03 and vc04 are run inside WSL; vc02 reads the Windows worktree.)
set -u
HERE="$(cd "$(dirname "$0")" && pwd)"
OUT="$HERE/../../out/verify_constraints"
mkdir -p "$OUT"
to_wsl() { wsl -d Ubuntu-24.04 --exec wslpath -a "$1" | tr -d '\r'; }
H=$(to_wsl "$HERE"); O=$(to_wsl "$OUT")
wsl -d Ubuntu-24.04 --exec bash -lc "bash '$H/vc01_resolve_citations.sh' > '$O/vc01_resolve_citations.out.txt' 2>&1"
bash "$HERE/vc02_merged_dev_differences.sh" > "$OUT/vc02_merged_dev_differences.out.txt" 2>&1
wsl -d Ubuntu-24.04 --exec bash -lc "~/egw-exec/venv/bin/python '$H/vc03_wording_scan.py' > '$O/vc03_wording_scan.out.txt' 2>&1"
wsl -d Ubuntu-24.04 --exec bash -lc "~/egw-exec/venv/bin/python '$H/vc04_cross_document.py' > '$O/vc04_cross_document.out.txt' 2>&1"
ls -l "$OUT"
