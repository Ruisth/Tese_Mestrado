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

# repo_identity: one-line JSON with the clean clone's commit and state.
repo_identity() {
    local head dirty
    head=$(git -C "$REPO" rev-parse HEAD)
    dirty=$(git -C "$REPO" status --porcelain | wc -l)
    printf '{"repo_commit": "%s", "repo_dirty_lines": %s, "export_tool_sha256": "%s", "drivers_sha256": "%s"}' \
        "$head" "$dirty" "$(sha256sum "$REPO/src/egw_experiments/local_export.py" | cut -d' ' -f1)" \
        "$(cat "$DRIVERS"/*.sh | sha256sum | cut -d' ' -f1)"
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

# export_attempt ATTEMPT: export, and say so; never changes the test verdict.
export_attempt() {
    (cd "$REPO/src" && $LE export --attempt "$1" --dest-root "$OUT" --secrets-env "$SECRETS_ENV") \
        || echo "EXPORT FAILED for $1 (the attempt is kept in WSL; run 'local_export recover')" >&2
}
