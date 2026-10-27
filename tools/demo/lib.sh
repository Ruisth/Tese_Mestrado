# shellcheck shell=bash
# tools/demo/lib.sh - shared settings and helpers of the demonstration commands in tools/demo/.
# Sourced by the other scripts, never run directly. Everything here points at EXISTING tools and
# data: the lifecycle scripts of tools/compare (tf.sh, compare_env.sh), the project's simulator in a
# virtual environment and the scenario state under $EGW_COMPARE_ROOT. Nothing is copied or changed,
# and no secret value is read here.
#
# Settings (environment; every path can be overridden):
#   DEMO_REPO            the repository checkout (default: the root two levels above this file)
#   DEMO_TOOLS           the lifecycle scripts (default $DEMO_REPO/tools/compare)
#   EGW_COMPARE_ROOT     the comparison state root, as in tools/compare/lib.sh (default $HOME/egw-compare)
#   DEMO_VENV            the venv whose python has egw_simulator (default $EGW_EXEC_VENV, else
#                        ${EGW_EXEC:-$HOME/egw-exec}/venv, as in tools/compare/measure_run.sh)
#   DEMO_SECRETS         the deployment .env on the host (default $EGW_COMPARE_SECRETS_ENV, else
#                        $HOME/egw-tcg/.env); read by wearables/simulate.sh only, in a subshell; no
#                        value is ever printed
#   DEMO_STATE_ROOT      the demonstration's own state and runs, outside the repository
#                        (default ${XDG_STATE_HOME:-$HOME/.local/state}/egw-demo)
#   DEMO_STATE           current_run, current_scenario, sim.pid (default $DEMO_STATE_ROOT/state)
#   DEMO_RUNS            the simulator's output of each demonstration run (default $DEMO_STATE_ROOT/runs)
#   EGW_COMPARE_SSH_KEY  private key of the guest user egw for yocto and debian13
#                        (default $HOME/.ssh/egw_campaign)
#   EGW_WRYNOSE_SSH_KEY  private key for yoctowrynose, whose image authorises only its own key
#                        (default $HOME/.ssh/egw_wrynose_share)

DEMO_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
DEMO_REPO=${DEMO_REPO:-$(cd "$DEMO_DIR/../.." && pwd)}
DEMO_TOOLS=${DEMO_TOOLS:-$DEMO_REPO/tools/compare}
DEMO_COMPARE_ROOT=${EGW_COMPARE_ROOT:-$HOME/egw-compare}
DEMO_VENV=${DEMO_VENV:-${EGW_EXEC_VENV:-${EGW_EXEC:-$HOME/egw-exec}/venv}}
DEMO_SECRETS=${DEMO_SECRETS:-${EGW_COMPARE_SECRETS_ENV:-$HOME/egw-tcg/.env}}
DEMO_STATE_ROOT=${DEMO_STATE_ROOT:-${XDG_STATE_HOME:-$HOME/.local/state}/egw-demo}
DEMO_STATE=${DEMO_STATE:-$DEMO_STATE_ROOT/state}
DEMO_RUNS=${DEMO_RUNS:-$DEMO_STATE_ROOT/runs}
DEMO_SSH_KEY=${EGW_COMPARE_SSH_KEY:-$HOME/.ssh/egw_campaign}
DEMO_SSH_PORT=2222

# scenario_canon NAME: the tools' name of a scenario: yocto, debian13 or yoctowrynose. The third one is
# accepted in any letter case (yoctoWrynose, YoctoWrynose, wrynose ...); any other name is echoed as given.
scenario_canon() {
    case $(printf '%s' "${1:-}" | tr '[:upper:]' '[:lower:]') in
        yocto) echo yocto ;;
        debian13) echo debian13 ;;
        yoctowrynose | yoctowrinose | wrynose) echo yoctowrynose ;;
        *) printf '%s\n' "${1:-}" ;;
    esac
}

# scenario_check NAME: yocto, debian13 or yoctoWrynose, nothing else.
scenario_check() {
    case $(scenario_canon "${1:-}") in
        yocto | debian13 | yoctowrynose) return 0 ;;
        *) echo "usage: $0 <yocto|debian13|yoctoWrynose> ..." >&2; return 2 ;;
    esac
}

# demo_key SCENARIO: the private key of the guest user egw for that scenario. The yoctoWrynose image
# authorises only its own test key; the measured scenarios authorise the campaign key.
demo_key() {
    case ${1:-} in
        yoctowrynose) echo "${EGW_WRYNOSE_SSH_KEY:-$HOME/.ssh/egw_wrynose_share}" ;;
        *) echo "$DEMO_SSH_KEY" ;;
    esac
}

# dssh SCENARIO CMD...: one ssh command on the guest of that scenario (the same options the tools use:
# the scenario's own known_hosts, key, port; no password prompt ever).
dssh() {
    local s=$1
    shift
    ssh -i "$(demo_key "$s")" -p "$DEMO_SSH_PORT" -o IdentitiesOnly=yes -o BatchMode=yes \
        -o StrictHostKeyChecking=accept-new -o UserKnownHostsFile="$DEMO_COMPARE_ROOT/scenarios/$s/state/known_hosts" \
        -o ConnectTimeout=10 -o ServerAliveInterval=30 -o LogLevel=ERROR egw@127.0.0.1 "$@"
}

# guest_running SCENARIO: 0 when the scenario's guest is up (the tools' own status, never inferred).
guest_running() {
    [ "$(bash "$DEMO_TOOLS/compare_env.sh" status "$1" 2> /dev/null | python3 -c 'import json, sys; print(json.load(sys.stdin).get("running", "false"))' 2> /dev/null)" = true ]
}

# stack_ready SCENARIO: 0 when the controller answers /ready with 200 inside the guest.
stack_ready() {
    [ "$(dssh "$1" "curl -s -o /dev/null -w '%{http_code}' --max-time 15 http://127.0.0.1:8000/ready" 2> /dev/null)" = 200 ]
}

# any_qemu: prints the qemu-system-aarch64 processes (0) or nothing (1); never stops anything.
any_qemu() { pgrep -af '^(\S*/)?qemu-system-aarch64( |$)'; }

# current_run: the demonstration's current run id (empty when none).
current_run() { cat "$DEMO_STATE/current_run" 2> /dev/null || true; }

# inside_repo PATH: 0 when PATH is the repository or lies under it. The demonstration never writes
# there: its state and runs belong outside the checkout, like everything tools/compare creates.
inside_repo() {
    local p=${1:-}
    case $p in /*) ;; *) p=$PWD/$p ;; esac
    case "$p/" in
        "$DEMO_REPO"/*) return 0 ;;
        *) return 1 ;;
    esac
}

say() { printf '\n== %s\n' "$*"; }
