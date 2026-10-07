#!/bin/bash
# Work order 2.B exit condition: one successful and one deliberately failed
# local test, both exported as inspectable, checksum-verified packages.
#
# This driver checks the export itself, so its two attempts are judged
# together: each one ends through driver_status.py, exactly as every other
# driver does, and the driver keeps the most serious of the two codes. BOTH
# checks are judged on what the run PRODUCED - the test file was written, the
# report holds the cases it should and pytest returned one of its two result
# codes (0 every test passed, 1 a test failed) - never on "pytest exited
# non-zero", which is also true of a check that never ran, nor on how many
# cases were COLLECTED, which is also true of a module every case of which was
# skipped. A failed export is never reported as success, and every end of this
# driver after the first attempt has been judged goes through the precedence of
# README.md and prints the EXPORT CHECKS summary line.
set -u
. "$(dirname "$0")/common.sh"
rc_all=$EXIT_PASS
CURRENT=""       # the attempt an interrupt must mark, if one is open

# rank CODE: where a code stands in the precedence order of README.md,
# 4 > 130 > 5 > 2 > 3 > 1 > 0, which the numbers themselves do not give (a
# prerequisite that failed, 2, outranks invalid instrumentation, 3).
rank() {
    case "$1" in
        4) echo 6 ;;
        130) echo 5 ;;
        5) echo 4 ;;
        2) echo 3 ;;
        3) echo 2 ;;
        1) echo 1 ;;
        *) echo 0 ;;
    esac
}

# worst CODE: keep the most serious code seen, in that order.
worst() { [ "$(rank "$1")" -gt "$(rank "$rc_all")" ] && rc_all=$1; return 0; }

# pytest_meaning RC: what pytest's own exit code means. Only 0 (everything it
# collected passed) and 1 (a test failed) are results; every other code says
# that nothing was checked, so it is never recorded as a test having failed.
pytest_meaning() {
    case "$1" in
        0) echo "pytest exited 0: every test it collected passed" ;;
        1) echo "pytest exited 1: at least one test failed" ;;
        2) echo "pytest exited 2: the run was interrupted before the module was finished" ;;
        3) echo "pytest exited 3: an internal error stopped the run" ;;
        4) echo "pytest exited 4: the test module was not collected (file or directory not found)" ;;
        5) echo "pytest exited 5: no test was collected" ;;
        *) echo "pytest exited $1: the run produced no test result" ;;
    esac
}

# junit_field REPORT NAME: one counter of the JUnit report's <testsuite>
# element (tests, skipped, errors), or an empty string when the report cannot
# be read. "exit 0" is also true of a module every case of which was SKIPPED,
# so what proves tests ran is what ran: tests less skipped less errors.
junit_field() {
    "$PY" -c 'import sys, xml.etree.ElementTree as ElementTree
root = ElementTree.parse(sys.argv[1]).getroot()
suite = root if root.tag == "testsuite" else root.find(".//testsuite")
print(int(suite.get(sys.argv[2], 0)))' "$1" "$2" 2> /dev/null
}

# executed_cases TOTAL SKIPPED ERRORS: how many of the report's cases actually
# ran, or an empty string when any of the three counters could not be read.
executed_cases() {
    local total=$1 skipped=$2 errors=$3
    [ -n "$total" ] && [ -n "$skipped" ] && [ -n "$errors" ] || return 0
    echo $((total - skipped - errors))
}

# stop_late CODE REASON: end the driver AFTER at least one attempt has been
# judged. driver_stop exits with its own code and never consults rc_all, so a
# package that did not reach output_test (4) would be thrown away by the
# prerequisite (2) that stopped the second block, or by an interrupt between
# the two. This keeps the precedence of README.md and still prints the summary
# line a caller parses.
stop_late() {
    echo "STOP: $2" >&2
    "$PY" "$DRIVERS/driver_status.py" --stop "$1" "$2" || true
    worst "$1"
    echo "EXPORT CHECKS: exit=$rc_all attempts: ${A:-none} ${B:-none}"
    exit "$rc_all"
}

# interrupt: mark and export the attempt that is open, if any (130), keeping
# the code of an attempt already judged when it is the more serious one.
interrupt() {
    [ -n "$CURRENT" ] || stop_late "$EXIT_INTERRUPTED" "interrupted before an attempt was created"
    (cd "$REPO/src" && $LE finish --attempt "$CURRENT" --status interrupted --outcome interrupted \
        --reason "driver interrupted" 2> /dev/null)
    driver_code "$CURRENT"
    worst $?
    echo "EXPORT CHECKS: exit=$rc_all attempts: ${A:-none} ${B:-none}"
    exit "$rc_all"
}
trap interrupt INT TERM

# 1. A real test module that passes: the export tool's own tests.
A=$(new_attempt "export check success" engineering) \
    || stop_late "$EXIT_PREREQUISITE" "the attempt for the passing check could not be created"
CURRENT=$A
IDENTITY_FAILED=0
IDENTITIES=$(repo_identity) || IDENTITY_FAILED=1
# The write of that identity is a prerequisite here as it is in every other
# driver: an attempt whose fields could not be recorded holds no commit, no
# dirty-line count and no export-tool hash, so what it seals is not provably
# this clone's check. Nothing is run when it failed.
SET_FAILED=0
(cd "$REPO/src" && $LE set --attempt "$A" "identities=$IDENTITIES" \
    'workload={"kind": "unit tests on the host (WSL); no guest, no QEMU"}' 'emulated=false') \
    || SET_FAILED=1
rc=0
cases=""
skipped=""
errors=""
executed=""
if [ "$SET_FAILED" -eq 0 ]; then
    ex "$A" pytest-local-export "$PY" -m pytest "$REPO/src/tests/test_local_export.py" -q -p no:cacheprovider \
        --junitxml="$A/tests/junit.xml"
    rc=$?
    cases=$(junit_field "$A/tests/junit.xml" tests)
    skipped=$(junit_field "$A/tests/junit.xml" skipped)
    errors=$(junit_field "$A/tests/junit.xml" errors)
    executed=$(executed_cases "$cases" "$skipped" "$errors")
fi
if [ "$SET_FAILED" -ne 0 ]; then
    (cd "$REPO/src" && $LE finish --attempt "$A" --status failed --validity invalid --outcome not-run \
        --reason "the attempt fields could not be recorded; the check did NOT run" \
        --next-action "make room in the attempts area and run the check again")
elif [ "$IDENTITY_FAILED" -ne 0 ]; then
    (cd "$REPO/src" && $LE finish --attempt "$A" --status failed --validity invalid --outcome not-run \
        --reason "the identity of the clean clone could not be read (see identities.identity_error); the check did NOT run" \
        --next-action "check the clone git can read before trusting any check")
elif [ "$rc" -eq "$EXIT_CAPTURE_LOST" ]; then
    (cd "$REPO/src" && $LE finish --attempt "$A" --status failed --validity invalid --outcome inconclusive \
        --reason "$(capture_note pytest-local-export)" \
        --next-action "read commands.jsonl for pytest's own exit code; this check proves nothing")
elif [ "$rc" -eq 0 ] && [ "${executed:-0}" -gt 0 ]; then
    (cd "$REPO/src" && $LE finish --attempt "$A" --status finished --validity valid --outcome pass \
        --reason "the export tool's test module passed (exit 0; $executed of $cases test case(s) in tests/junit.xml ran, $skipped skipped, $errors error(s))" \
        --next-action "none")
elif [ "$rc" -eq 1 ]; then
    (cd "$REPO/src" && $LE finish --attempt "$A" --status failed --validity valid --outcome fail \
        --reason "the export tool's test module failed (exit 1: at least one test failed)" \
        --next-action "fix the failing test")
elif [ "$rc" -eq 0 ]; then
    (cd "$REPO/src" && $LE finish --attempt "$A" --status failed --validity invalid --outcome inconclusive \
        --reason "the export tool's test module executed no test case (exit 0, tests=${cases:-unreadable}, skipped=${skipped:-unreadable}, errors=${errors:-unreadable} in tests/junit.xml): nothing was checked" \
        --next-action "run the module by hand; this check proves nothing")
else
    (cd "$REPO/src" && $LE finish --attempt "$A" --status failed --validity invalid --outcome inconclusive \
        --reason "$(pytest_meaning "$rc"), so the export tool's test module was NOT checked" \
        --next-action "run the module by hand; this check proves nothing")
fi
driver_code "$A"
worst $?
CURRENT=""

# 2. A deliberately failing test: the package must keep the failure.
B=$(new_attempt "export check deliberate failure" engineering) \
    || stop_late "$EXIT_PREREQUISITE" "the attempt for the deliberate failure could not be created"
CURRENT=$B
IDENTITY_FAILED=0
IDENTITIES=$(repo_identity) || IDENTITY_FAILED=1
SET_FAILED=0
(cd "$REPO/src" && $LE set --attempt "$B" "identities=$IDENTITIES" \
    'workload={"kind": "one deliberately failing unit test; no guest, no QEMU"}' 'emulated=false') \
    || SET_FAILED=1
DELIBERATE=$B/tests/deliberate/test_deliberate_failure.py
JUNIT=$B/tests/junit.xml
broken=""
mkdir -p "$B/tests/deliberate" || broken="the folder for the deliberately failing test could not be created"
cat > "$DELIBERATE" <<'PYEOF'
"""A test written to fail, so that the export of a failed test can be checked."""


def test_this_fails_on_purpose():
    assert 1 + 1 == 3, "deliberate failure: checks that a failed test is exported as failed"
PYEOF
[ -s "$DELIBERATE" ] || broken=${broken:-"the deliberately failing test file could not be written"}

if [ "$SET_FAILED" -ne 0 ]; then
    (cd "$REPO/src" && $LE finish --attempt "$B" --status failed --validity invalid --outcome not-run \
        --reason "the attempt fields could not be recorded; the check did NOT run" \
        --next-action "make room in the attempts area and run the check again")
elif [ "$IDENTITY_FAILED" -ne 0 ]; then
    (cd "$REPO/src" && $LE finish --attempt "$B" --status failed --validity invalid --outcome not-run \
        --reason "the identity of the clean clone could not be read (see identities.identity_error); the check did NOT run" \
        --next-action "check the clone git can read before trusting any check")
elif [ -n "$broken" ]; then
    (cd "$REPO/src" && $LE finish --attempt "$B" --status failed --validity invalid --outcome inconclusive \
        --reason "$broken: the deliberate failure check did NOT run" \
        --next-action "make room in the attempts area and run the check again")
else
    ex "$B" pytest-deliberate-failure "$PY" -m pytest "$DELIBERATE" -q \
        -p no:cacheprovider --junitxml="$JUNIT"
    rc=$?
    "$PY" "$DRIVERS/junit_one_failure.py" "$JUNIT"
    junit_rc=$?
    if [ "$rc" -eq "$EXIT_CAPTURE_LOST" ]; then
        (cd "$REPO/src" && $LE finish --attempt "$B" --status failed --validity invalid --outcome inconclusive \
            --reason "$(capture_note pytest-deliberate-failure)" \
            --next-action "read commands.jsonl for pytest's own exit code; this check proves nothing")
    elif [ "$rc" -eq 1 ] && [ "$junit_rc" -eq 0 ]; then
        (cd "$REPO/src" && $LE finish --attempt "$B" --status failed --validity valid --outcome fail \
            --reason "deliberate failure: pytest exited 1 and its report holds exactly one failed test, as intended" \
            --next-action "none; this attempt exists to show a failed test exported as failed")
    else
        (cd "$REPO/src" && $LE finish --attempt "$B" --status failed --validity invalid --outcome inconclusive \
            --reason "the deliberate failure did not behave as intended ($(pytest_meaning "$rc"); report check exit $junit_rc): a failed test was not proved" \
            --next-action "read tests/junit.xml and console/; the export of a failed test is unproven")
    fi
fi
driver_code "$B"
b=$?
# Attempt B is written to fail, so the code ITS OWN verdicts derive is 1 (a
# valid negative result, exported and verified): that is this check behaving as
# intended, and the work order's exit condition stays 0. Any other code is this
# driver's own problem: 0 would mean the failing test did not fail.
if [ "$b" -eq "$EXIT_NEGATIVE" ]; then
    :
elif [ "$b" -eq "$EXIT_PASS" ]; then
    worst "$EXIT_INVALID"
else
    worst "$b"
fi
CURRENT=""
echo "EXPORT CHECKS: exit=$rc_all attempts: $A $B"
exit "$rc_all"
