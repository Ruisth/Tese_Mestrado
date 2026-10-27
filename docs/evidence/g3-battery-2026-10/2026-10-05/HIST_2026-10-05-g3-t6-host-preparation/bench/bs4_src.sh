#!/bin/bash
# Bench of the S4 operator script (stream BENCH of the S4 preparation, 2026-10-05): the
# one read-only source every bench copies its repository from, /tmp/g3-s4-bench/_src.
# Taken from the read-only worktree <S>/t6m (detached at 1fd9792, tree 14f89c4): tools/,
# src/egw_experiments, src/egw_simulator, src/deployment and src/schemas; the clone's
# runbook is the blob <P>/runbook.1fd9792.md. Every identity a bench relies on is checked
# here, once, before anything else: the runbook (31716593...), the export tool
# (544c9b3d...), the collector (9e678b02...), the 38 driver files hashed the way
# common.sh's repo_identity hashes them (2c209b09...), and the test module of the
# worktree (b63ef7d8...), which bs4_stubs.py imports. The copy is then made read-only.
# Nothing of the worktree is written (cp reads only; no git command is run).
# Usage (WSL): bs4_src.sh
set -u
ROOT=/tmp/g3-s4-bench
D=$ROOT/_src
HERE=$(cd "$(dirname "$0")" && pwd)       # <P>/bench
PREP=$(cd "$HERE/.." && pwd)              # <P>
SCR=$(cd "$PREP/../.." && pwd)            # <S>
WT=$SCR/t6m
RUNBOOK_SHA=317165936abed4f3823f53b67b7ac76bafa442cfa1820d4b96479392b280cf0f
EXPORT_TOOL_SHA=544c9b3d451f0a6c3391102ac4031fe93bee79a0b0b9bcd6f41c893592d2422b
COLLECTOR_SHA=9e678b024bde66bacc65fea936d05ca226a82e73c86d1cc23a9cf9f8fe8d9b97
DRIVERS_SHA=2c209b09faf58bb4986cf39b7bb1f13936fae8e94c3b5eb3faf84f722bfe44ed
MODULE_SHA=b63ef7d88ae22e623bf381ef0dc3e6fbfbf050d966d5b0e09cc961ee169d83be
[ ! -e "$D" ] || { echo "refused: $D exists"; exit 2; }
mkdir -p "$D/src" "$D/docs/setup" || exit 1
cp -r "$WT/tools" "$D/tools" || exit 1
for x in egw_experiments egw_simulator deployment schemas; do cp -r "$WT/src/$x" "$D/src/$x" || exit 1; done
cp "$PREP/runbook.1fd9792.md" "$D/docs/setup/qemu_integrated_gateway.md" || exit 1
find "$D" -name __pycache__ -prune -exec rm -rf {} +
bad=0
want() {   # want LABEL EXPECTED GOT
    if [ "$2" = "$3" ]; then echo "ok: $1 $3"; else echo "NOT AS RECORDED: $1 $3 (expected $2)"; bad=1; fi
}
want "runbook (the blob, as the clone's docs/setup/qemu_integrated_gateway.md)" "$RUNBOOK_SHA" "$(sha256sum < "$D/docs/setup/qemu_integrated_gateway.md" | cut -d' ' -f1)"
want "runbook lines" 1624 "$(wc -l < "$D/docs/setup/qemu_integrated_gateway.md")"
want "the worktree's own runbook" "$RUNBOOK_SHA" "$(sha256sum < "$WT/docs/setup/qemu_integrated_gateway.md" | cut -d' ' -f1)"
want "export tool src/egw_experiments/local_export.py" "$EXPORT_TOOL_SHA" "$(sha256sum < "$D/src/egw_experiments/local_export.py" | cut -d' ' -f1)"
want "collector src/deployment/scripts/collect-resources.sh" "$COLLECTOR_SHA" "$(sha256sum < "$D/src/deployment/scripts/collect-resources.sh" | cut -d' ' -f1)"
# The driver files in common.sh's own order (driver_files: *.sh, *.py, guest/*.sh).
want "drivers (38 files, repo_identity's order)" "$DRIVERS_SHA" "$(cd "$D/tools/session" && cat ./*.sh ./*.py ./guest/*.sh | sha256sum | cut -d' ' -f1)"
want "driver files counted" 38 "$(cd "$D/tools/session" && ls ./*.sh ./*.py ./guest/*.sh | wc -l)"
want "test module src/tests/test_runbook_itest_helpers.py of the worktree" "$MODULE_SHA" "$(sha256sum < "$WT/src/tests/test_runbook_itest_helpers.py" | cut -d' ' -f1)"
chmod -R a-w "$D" || exit 1
[ "$bad" -eq 0 ] || { echo "the source is NOT the merged tree's: no bench may use it"; exit 1; }
echo "source ready (read-only): $D"
