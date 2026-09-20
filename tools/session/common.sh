#!/bin/bash
# Shared settings of the session drivers (source it; bash). The drivers run
# from a clean clone at an identified commit: REPO is the clone that holds
# this folder. Every attempt lives under ATTEMPTS (WSL filesystem) and is
# exported to OUT, the Windows folder output_test (docs/setup/local_test_outputs.md).
# Each default can be overridden through the environment.
DRIVERS=$(cd "$(dirname "$0")" && pwd)
REPO=${EGW_EXEC_REPO:-$(cd "$DRIVERS/../.." && pwd)}
EXEC=${EGW_EXEC:-/home/ruisth/egw-exec}
VENV=${EGW_EXEC_VENV:-$EXEC/venv}
PY=$VENV/bin/python
ATTEMPTS=${EGW_ATTEMPTS:-$EXEC/attempts}
OUT=${EGW_OUTPUT_TEST:-"/mnt/c/Users/ruimf/Documents/Projeto Mestrado/output_test"}
SECRETS_ENV=${EGW_SECRETS_ENV:-$HOME/egw-tcg/.env}
LE="$PY -m egw_experiments.local_export"

# The driver exit statuses of README.md, "Exit statuses". They are derived in
# ONE place, by driver_status.py, from the attempt's own recorded verdicts, the
# export result and the session-close flag; no driver invents a code. Zero
# never authorises a dependent test by itself: the caller reads the verdicts.
EXIT_PASS=0            # ran, valid, outcome pass, package exported and verified
EXIT_NEGATIVE=1        # valid negative result: ran, valid, exported, outcome fail
EXIT_PREREQUISITE=2    # a prerequisite failed: the test did not run
EXIT_INVALID=3         # invalid instrumentation, or a mandatory step failed
EXIT_EXPORT=4          # the local export failed: no verified package
EXIT_STOP=5            # the controlled stop or power-off failed (session close)
EXIT_INTERRUPTED=130   # interrupted: marked interrupted and exported

# 'local_export exec' returns this when the command itself ran but its mandatory
# console capture failed (interface 1): the command's own exit code is kept in
# commands.jsonl, and the attempt carries the capture failure. A step that ends
# this way is never recorded as the step itself having failed.
EXIT_CAPTURE_LOST=74

# driver_files: every file the drivers are made of, in a fixed order (the shell
# drivers, the Python helpers they call, the guest scripts they copy). Printed
# one per line; non-zero when one of them is not a readable file.
driver_files() {
    local f
    for f in "$DRIVERS"/*.sh "$DRIVERS"/*.py "$DRIVERS"/guest/*.sh; do
        [ -f "$f" ] || { echo "driver_files: $f is not a readable driver file" >&2; return 1; }
        printf '%s\n' "$f"
    done
}

# repo_identity: one-line JSON with the clean clone's commit and state, the
# sha256 of the export tool and the sha256 of every driver file. It FAILS
# (non-zero, and every field it could not read is null beside an
# identity_error) when git or a hash cannot be read: an identity that was not
# read is never recorded as a clean clone at an unnamed commit.
repo_identity() {
    local head="" dirty=0 tool="" drivers="" error="" porcelain listing files=()
    head=$(git -C "$REPO" rev-parse HEAD 2> /dev/null) || error="git rev-parse HEAD failed in $REPO"
    if porcelain=$(git -C "$REPO" status --porcelain 2> /dev/null); then
        [ -z "$porcelain" ] || dirty=$(printf '%s\n' "$porcelain" | wc -l)
    else
        error=${error:-"git status --porcelain failed in $REPO"}
    fi
    if tool=$(sha256sum "$REPO/src/egw_experiments/local_export.py" 2> /dev/null); then
        tool=${tool%% *}
    else
        tool=""
        error=${error:-"the export tool could not be hashed"}
    fi
    if listing=$(driver_files); then
        mapfile -t files <<< "$listing"
        if drivers=$(cat "${files[@]}" | sha256sum); then
            drivers=${drivers%% *}
        else
            drivers=""
            error=${error:-"the drivers could not be hashed"}
        fi
    else
        error=${error:-"the driver files could not be listed"}
    fi
    if [ -n "$error" ]; then
        echo "repo_identity: $error" >&2
        error=${error//\\/\\\\}      # the path may hold characters JSON escapes
        error=${error//\"/\\\"}
        printf '{"repo_commit": null, "repo_dirty_lines": null, "export_tool_sha256": "%s", "drivers_sha256": "%s", "identity_error": "%s"}' \
            "$tool" "$drivers" "$error"
        return 1
    fi
    printf '{"repo_commit": "%s", "repo_dirty_lines": %s, "export_tool_sha256": "%s", "drivers_sha256": "%s"}' \
        "$head" "$dirty" "$tool" "$drivers"
}

# new_attempt SCENARIO PURPOSE: prints the attempt directory.
new_attempt() {
    (cd "$REPO/src" && $LE new --attempts-root "$ATTEMPTS" --scenario "$1" --purpose "$2" --dest-root "$OUT")
}

# ex ATTEMPT NAME CMD...: run one command inside the attempt (output kept).
ex() {
    local a=$1 name=$2
    shift 2
    (cd "$REPO/src" && $LE exec --attempt "$a" --name "$name" --secrets-env "$SECRETS_ENV" -- "$@")
}

# export_attempt ATTEMPT: export the attempt. NON-ZERO when no verified package
# reached output_test; the attempt is then kept in WSL for 'local_export
# recover'. A failed export is never reported as a successful message, and an
# export never changes a test verdict.
export_attempt() {
    if (cd "$REPO/src" && $LE export --attempt "$1" --dest-root "$OUT" --secrets-env "$SECRETS_ENV"); then
        return 0
    fi
    echo "EXPORT FAILED for $1 (the attempt is kept in WSL; run 'local_export recover')" >&2
    return 1
}

# driver_code ATTEMPT [STOP_FAILED]: export the attempt, print the one final
# line and RETURN the derived code. A driver that judges more than one attempt
# (export_checks.sh) uses this and keeps the most serious code; every other
# driver uses driver_exit, which ends there. STOP_FAILED is 1 only for a session
# close whose controlled stop or power-off failed (code 5).
driver_code() {
    local a=$1 stop_failed=${2:-0} result=exported
    export_attempt "$a" || result=failed
    "$PY" "$DRIVERS/driver_status.py" "$a/attempt.json" "$result" "$stop_failed"
    return $?
}

# driver_exit ATTEMPT [STOP_FAILED]: the end of every driver that owns one
# attempt. Exports it, prints the one final line and exits with the code
# derived from attempt.json.
driver_exit() {
    driver_code "$@"
    exit $?
}

# driver_stop CODE REASON: the end of a driver that stops BEFORE an attempt
# exists (a prerequisite the attempt itself depends on), or that owns no
# attempt at all (backfill.sh). It prints the same final line as driver_exit,
# with no run id, status 'no-attempt' and the three verdicts unknown, so a
# caller that parses that line is never left with nothing. CODE is still the
# code the driver exits with, even if the helper cannot be run.
driver_stop() {
    [ "$1" -eq 0 ] || echo "STOP: $2" >&2
    "$PY" "$DRIVERS/driver_status.py" --stop "$1" "$2" || true
    exit "$1"
}

# capture_stop ATTEMPT NAME NOTE: end the driver because the mandatory console
# capture of NAME failed (EXIT_CAPTURE_LOST) although NAME's own command ran.
# The evidence is incomplete, so the attempt is invalid (code 3), but the step
# is never recorded as having failed and the outcome is never 'not-run'.
capture_stop() {
    (cd "$REPO/src" && $LE finish --attempt "$1" --status failed --validity invalid --outcome inconclusive \
        --reason "$(capture_note "$2"); $3" \
        --next-action "read commands.jsonl for the step's own exit code; the console record of this run is incomplete")
    driver_exit "$1"
}

# capture_note NAME: how a lost console capture is written into the evidence.
capture_note() {
    printf "the console capture of '%s' failed (exit %s): '%s' itself ran, but its console record is incomplete" \
        "$1" "$EXIT_CAPTURE_LOST" "$1"
}

# step_note NAME RC TEXT: what is recorded for a step that did not end 0. A
# lost console capture is named as such instead of blaming the step; anything
# else keeps the driver's own text.
step_note() {
    if [ "$2" -eq "$EXIT_CAPTURE_LOST" ]; then
        capture_note "$1"
    else
        printf '%s' "$3"
    fi
}

# driver_exit_open ATTEMPT: the end of guest_session_open.sh. The session
# attempt stays open on purpose, so nothing is exported yet (the close driver
# exports it) and that absence is not an export failure.
driver_exit_open() {
    "$PY" "$DRIVERS/driver_status.py" "$1/attempt.json" deferred 0
    exit $?
}

# driver_interrupt ATTEMPT: the INT/TERM handler. The attempt is marked
# interrupted, exported, and the driver ENDS here (130, or 4 if the export
# failed); it never goes on to the next step.
driver_interrupt() {
    (cd "$REPO/src" && $LE finish --attempt "$1" --status interrupted --outcome interrupted \
        --reason "driver interrupted" 2> /dev/null)
    driver_exit "$1"
}
