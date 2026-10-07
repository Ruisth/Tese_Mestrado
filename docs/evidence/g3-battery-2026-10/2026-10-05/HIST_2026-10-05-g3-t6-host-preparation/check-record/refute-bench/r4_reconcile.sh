#!/bin/bash
# reviewer: read-only: does the REAL itest_reconcile say its verdict/exit in its output (delta, acceptance --exactly-once)?
F=/tmp/g3-s4-bench/_src/src/egw_experiments/itest_reconcile.py
sha256sum "$F"; wc -l "$F"
grep -nE 'return [0-9]|sys\.exit|EXIT_|exit [0-9]|print\(.*(MISMATCH|FAIL|OK|PASS|exactly|verdict|result)' "$F" | cut -c1-200 | head -n 120
echo "--- the module stub python (STUB_PYTHON) - how it answers delta/acceptance"
grep -n 'itest_reconcile' /tmp/g3-s4-bench/pass/mod/stubs/python | cut -c1-200 | head -n 30
