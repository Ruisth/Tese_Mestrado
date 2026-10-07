#!/bin/bash
# Bench of the second opening of S3: the exception's checker ALONE (no operator script), on
# the unchanged fixture and on each changed fixture of the scenarios, as the script would
# call it: '<python> s3b_preflight_exception.py <attempts>/<run id of the DRIVER RESULT line>
# <driver console>', where the driver console is the fixture's console plus the line
# 'preflight.sh exit=3' that run_driver appends. For each: the exit status and the checker's
# last line, against what is expected. Also, read in place and read-only: the real WSL attempt
# directory with the real driver console (what the first opening's script would have handed
# the checker), and the checker with one comment appended (the bytes e6 refuses) on the
# unchanged fixture. Fixtures live under /tmp/g3-s3b-bench/_validator/.
# Usage (WSL): bs3b_validator.sh   (the console is kept by the caller as record/validator.console.txt)
set -u
HERE=$(cd "$(dirname "$0")" && pwd)
SCR=$(cd "$HERE/../../.." && pwd)
PREP=$SCR/g3/s3bprep
CHECKER=$PREP/s3b_preflight_exception.py
REAL_PY=/home/ruisth/egw-exec/venv/bin/python
V=/tmp/g3-s3b-bench/_validator
RID=20261005T105656Z_live-preflight_attempt11
TMPROOT=$(dirname "$(dirname "$(dirname "$(dirname "$SCR")")")")
mask() { sed "s#$V#<V>#g; s#$SCR#<S>#g; s#$TMPROOT/[^ ;|]*#<S, cut>#g"; }
sha() { /usr/bin/sha256sum "$1" | cut -d' ' -f1; }
WANT_SHA=$(sed -n 's/^EXCEPTION_SHA=//p' "$PREP/g3_battery.sh")
echo "checker run: sha256 $(sha "$CHECKER") (<S>/g3/s3bprep/s3b_preflight_exception.py, in place); the script's EXCEPTION_SHA $WANT_SHA ($([ "$(sha "$CHECKER")" = "$WANT_SHA" ] && echo equal || echo DIFFERENT)); g3_battery.sh sha256 $(sha "$PREP/g3_battery.sh")"
echo "## $(date -u +%Y-%m-%dT%H:%M:%SZ) the checker alone; python: the execution venv's ($REAL_PY, $("$REAL_PY" --version 2>&1)), PYTHONDONTWRITEBYTECODE=1"
export PYTHONDONTWRITEBYTECODE=1
[ ! -e "$V" ] || rm -rf "$V"
mkdir -p "$V" || exit 1
N=0
GOOD=0
# check NAME EXPECTED_EXIT EXPECTED_LAST_LINE_REGEX ATTEMPT_DIR CONSOLE [CHECKER]
check() {
    local out rc last
    N=$((N + 1))
    out=$("$REAL_PY" "${6:-$CHECKER}" "$4" "$5" 2>&1)
    rc=$?
    last=$(printf '%s\n' "$out" | tail -n 1)
    echo "  checker exit $rc; lines: $(printf '%s\n' "$out" | wc -l) ($(printf '%s\n' "$out" | grep -c '^ok: ') 'ok:')"
    echo "  last line: $last" | mask | cut -c1-600
    if [ "$rc" = "$2" ] && printf '%s\n' "$last" | grep -Eq -- "$3"; then
        GOOD=$((GOOD + 1))
        echo "  as expected (exit $2; last line matches: $3)"
    else
        echo "  NOT AS EXPECTED: wanted exit $2 and a last line matching: $3"
    fi
}
# variant NAME EXPECTED_EXIT REGEX: make the fixture, then check it as the script would
variant() {
    local d=$V/$1 con pre_id
    echo
    echo "=== fixture $1"
    bash "$HERE/bs3b_fixture.sh" "$1" "$d" 2>&1 | grep -E '^(fixture variant|FIXTURE|refused)' | mask | cut -c1-400
    con=$d/driver.console.txt
    { cat "$d/preflight.console.txt"; echo "preflight.sh exit=3"; } > "$con"
    pre_id=$(sed -n 's/^DRIVER RESULT \([^: ]*\):.*/\1/p' "$con" | tail -n 1)
    if [ -d "$d/attempts/$pre_id" ]; then
        echo "  the console names $pre_id; that directory exists: the script would run the checker on it"
        check "$1" "$2" "$3" "$d/attempts/$pre_id" "$con"
    else
        echo "  the console names $pre_id; NO such directory: the script would NOT run the checker (its plain halt 'preflight.sh exited 3'); the checker alone, on the attempt the stub placed ($RID), with that console:"
        check "$1" "$2" "$3" "$d/attempts/$RID" "$con"
    fi
}
variant unchanged 0 "^EXCEPTION APPLIES: preflight $RID stays failed and invalid; the session proceeds under the authorised T8/T9 exception \(collector-duration only: UTC window 43 s of 45 s declared\)$"
variant step7-exit1 1 '^EXCEPTION DOES NOT APPLY: step stack-health ended 1, not 0 - the halt stands$'
variant no-attempt-json 1 '^EXCEPTION DOES NOT APPLY: attempt.json could not be read \(.*No such file or directory.*\) - the halt stands$'
variant other-run-id 1 "^EXCEPTION DOES NOT APPLY: the attempt directory .* is not the driver's attempt 20261005T105656Z_live-preflight_attempt12 - the halt stands$"
variant other-run-id-dir 1 "^EXCEPTION DOES NOT APPLY: attempt.json run_id='$RID', not '20261005T105656Z_live-preflight_attempt12' - the halt stands$"
variant collector-problem 1 '^EXCEPTION DOES NOT APPLY: collector-check reports problems: \[.*\] - the halt stands$'
variant capture-failures 1 "^EXCEPTION DOES NOT APPLY: attempt.json records capture failures: \[.*\] - the halt stands$"
variant capture-truncated 1 "^EXCEPTION DOES NOT APPLY: step collector-live: its stdout capture is not complete \(.*'state': 'truncated'.*\) - the halt stands$"
variant system-fault 1 "^EXCEPTION DOES NOT APPLY: the driver's result line does not say system_outcome=inconclusive: DRIVER RESULT .* - the halt stands$"
variant system-fault-record 1 "^EXCEPTION DOES NOT APPLY: attempt.json system_outcome='fail', not 'inconclusive' - the halt stands$"
variant reason-fault 1 "^EXCEPTION DOES NOT APPLY: attempt.json's reason is not the frozen preflight's reason for collector-duration as its only failed mandatory step, with nothing observed and nothing skipped: .* - the halt stands$"

echo
echo "=== the real WSL attempt directory with the real driver console (read in place, read-only)"
RA=/home/ruisth/egw-exec/attempts/$RID
RC=/home/ruisth/egw-exec/g3-t8t9-s3/S3-preflight.console.txt
if [ -d "$RA" ] && [ -f "$RC" ]; then
    echo "  $RA: attempt.json $(sha "$RA/attempt.json"), commands.jsonl $(sha "$RA/commands.jsonl"); console $(sha "$RC")"
    check wsl-attempt 0 "^EXCEPTION APPLIES: preflight $RID stays failed and invalid" "$RA" "$RC"
    echo "  after: attempt.json $(sha "$RA/attempt.json"), commands.jsonl $(sha "$RA/commands.jsonl"); console $(sha "$RC")"
else
    echo "  not there: $RA or $RC"
fi

echo
echo "=== the checker with one comment line appended (the bytes e6 refuses), on the unchanged fixture"
cp -p "$CHECKER" "$V/s3b_preflight_exception.changed.py"
printf '%s\n' '# bench: a comment appended (scenario e6): the bytes differ, the logic does not' >> "$V/s3b_preflight_exception.changed.py"
echo "  changed copy: sha256 $(sha "$V/s3b_preflight_exception.changed.py") (not $WANT_SHA)"
check changed-checker 0 "^EXCEPTION APPLIES: " "$V/unchanged/attempts/$RID" "$V/unchanged/driver.console.txt" "$V/s3b_preflight_exception.changed.py"
echo "  (it still applies the exception: the logic is unchanged; what refuses it in e6 is the script's check of the bytes, before the checker is run)"

echo
echo "## $(date -u +%Y-%m-%dT%H:%M:%SZ) VALIDATOR: $GOOD of $N as expected; checker sha256 after the runs $(sha "$CHECKER")"
[ "$GOOD" -eq "$N" ]
