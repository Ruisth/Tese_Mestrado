#!/bin/bash
# Work order 2.B exit condition: one successful and one deliberately failed
# local test, both exported as inspectable, checksum-verified packages.
set -u
. "$(dirname "$0")/common.sh"
rc_all=0

# 1. A real test module that passes: the export tool's own tests.
A=$(new_attempt "export check success" engineering) || exit 1
(cd "$REPO/src" && $LE set --attempt "$A" "identities=$(repo_identity)" \
    'workload={"kind": "unit tests on the host (WSL); no guest, no QEMU"}' 'emulated=false')
ex "$A" pytest-local-export "$PY" -m pytest "$REPO/src/tests/test_local_export.py" -q -p no:cacheprovider \
    --junitxml="$A/tests/junit.xml"
rc=$?
if [ "$rc" -eq 0 ]; then
    (cd "$REPO/src" && $LE finish --attempt "$A" --status finished --validity valid --outcome pass \
        --reason "the export tool's test module passed (exit 0)" --next-action "none")
else
    (cd "$REPO/src" && $LE finish --attempt "$A" --status failed --validity valid --outcome fail \
        --reason "the export tool's test module failed (exit $rc)" --next-action "fix the failing test")
    rc_all=1
fi
export_attempt "$A"

# 2. A deliberately failing test: the package must keep the failure.
B=$(new_attempt "export check deliberate failure" engineering) || exit 1
(cd "$REPO/src" && $LE set --attempt "$B" "identities=$(repo_identity)" \
    'workload={"kind": "one deliberately failing unit test; no guest, no QEMU"}' 'emulated=false')
mkdir -p "$B/tests/deliberate"
cat > "$B/tests/deliberate/test_deliberate_failure.py" <<'PYEOF'
"""A test written to fail, so that the export of a failed test can be checked."""


def test_this_fails_on_purpose():
    assert 1 + 1 == 3, "deliberate failure: checks that a failed test is exported as failed"
PYEOF
ex "$B" pytest-deliberate-failure "$PY" -m pytest "$B/tests/deliberate/test_deliberate_failure.py" -q \
    -p no:cacheprovider --junitxml="$B/tests/junit.xml"
rc=$?
if [ "$rc" -ne 0 ]; then
    (cd "$REPO/src" && $LE finish --attempt "$B" --status failed --validity valid --outcome fail \
        --reason "deliberate failure: pytest exited $rc, as intended" --next-action "none; this attempt exists to show a failed test exported as failed")
else
    (cd "$REPO/src" && $LE finish --attempt "$B" --status finished --validity invalid --outcome inconclusive \
        --reason "the deliberately failing test passed, so the check itself is broken")
    rc_all=1
fi
export_attempt "$B"
echo "attempts: $A $B"
exit $rc_all
