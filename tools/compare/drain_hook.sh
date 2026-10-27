#!/bin/bash
# tools/compare/drain_hook.sh <secrets.env> <hook> <run-id> - run the drain hook
# (tools/session/proof_hook_drained.sh, or any hook taking the run id) with the deployment's
# environment file exported, as the pilot's host steps had it: the runbook helper file that defines
# `drained` refuses to load unless that file's variables are set. The file is sourced here, in this
# process only, with `set -a`; no value is printed and none goes on a command line. DRAIN_QUIET_S,
# DRAIN_STEP_S, DRAIN_LIMIT_S and CTRL pass through from the caller's environment.
# Exit: the hook's own status; 97 when the secrets file cannot be sourced (nothing run);
#       2 on a usage error.
set -u
[ $# -eq 3 ] || { echo "usage: drain_hook.sh <secrets.env> <hook> <run-id>" >&2; exit 2; }
secrets=$1
hook=$2
rid=$3
[ -r "$secrets" ] || { echo "STOP: drain_hook: secrets file not readable: $secrets" >&2; exit 97; }
[ -s "$hook" ] || { echo "STOP: drain_hook: hook not found: $hook" >&2; exit 97; }
set -a
# shellcheck disable=SC1090
. "$secrets" > /dev/null 2>&1 || { echo "STOP: drain_hook: the secrets file could not be sourced" >&2; exit 97; }
set +a
exec bash "$hook" "$rid"
