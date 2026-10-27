#!/bin/bash
# tools/compare/tf.sh - run Terraform for ONE comparison scenario with the workspace, the variable
# file and the state location fixed, so that the two scenarios can never share state.
#
#   tf.sh <scenario> init                 terraform init (state under $EGW_COMPARE_ROOT/tfstate) + workspace
#   tf.sh <scenario> plan [args]          terraform plan
#   tf.sh <scenario> apply [args]         terraform apply: prepare (idempotent), start the guest, wait for
#                                         ssh, bring the stack up and confirm it healthy; it stays running
#   tf.sh <scenario> stop [args]          terraform apply with desired_state=stopped: stack stop, power-off,
#                                         QEMU confirmed ended; disks, configuration and logs are kept
#   tf.sh <scenario> destroy [args]       controlled stop, then remove ONLY work disks and state
#   tf.sh <scenario> status               the live state (compare_env.sh status), never inferred
#   tf.sh <scenario> output               terraform output -json of that workspace
#
# `apply` and `stop` run without a confirmation prompt (their plan is fixed by the scenario and the
# desired state); `destroy` prompts unless EGW_COMPARE_AUTO_APPROVE=1. `init` runs by itself when the
# module is not initialised yet. Repeating `apply` on a running environment changes nothing.
# The Terraform binary: $EGW_COMPARE_TERRAFORM, else $EGW_COMPARE_ROOT/bin/terraform, else PATH.
set -u
HERE=$(cd "$(dirname "$0")" && pwd)
# shellcheck source=lib.sh
. "$HERE/lib.sh"

usage() { sed -n '2,19p' "$0" | sed 's/^# \{0,1\}//' >&2; exit 2; }
[ $# -ge 2 ] || usage
scenario=$1
cmd=$2
shift 2
scenario_load "$scenario"

TERRAFORM=${EGW_COMPARE_TERRAFORM:-}
if [ -z "$TERRAFORM" ]; then
    if [ -x "$COMPARE_ROOT/bin/terraform" ]; then TERRAFORM=$COMPARE_ROOT/bin/terraform; else TERRAFORM=$(command -v terraform || true); fi
fi
[ -n "$TERRAFORM" ] && [ -x "$TERRAFORM" ] || die "terraform not found (install 1.16.6 to $COMPARE_ROOT/bin/terraform, see README)"

export TF_IN_AUTOMATION=1 TF_INPUT=0
export TF_PLUGIN_CACHE_DIR=${TF_PLUGIN_CACHE_DIR:-$COMPARE_ROOT/plugin-cache}
mkdir -p "$TF_PLUGIN_CACHE_DIR" "$COMPARE_ROOT/tfstate"

tf() { "$TERRAFORM" -chdir="$HERE/terraform" "$@"; }
destroy_approve=()
[ "${EGW_COMPARE_AUTO_APPROVE:-0}" = 1 ] && destroy_approve=(-auto-approve)
vars=(-var-file="scenarios/$scenario.tfvars" -var "scenario=$scenario")
[ -n "${EGW_COMPARE_ROOT:-}" ] && vars+=(-var "compare_root=$COMPARE_ROOT")

ensure_init() {   # a module not initialised yet (fresh clone) is initialised once, offline when the plugin cache holds the providers
    [ -d "$HERE/terraform/.terraform/providers" ] && [ -e "$HERE/terraform/.terraform/terraform.tfstate" ] && return 0
    echo "tf.sh: initialising the module (state under $COMPARE_ROOT/tfstate)"
    tf init -input=false -backend-config="workspace_dir=$COMPARE_ROOT/tfstate" || die "terraform init failed"
}
select_workspace() {
    ensure_init
    tf workspace select -or-create "$scenario" > /dev/null || die "could not select workspace '$scenario' (run: tf.sh $scenario init)"
}

case $cmd in
    init)
        tf init -input=false -backend-config="workspace_dir=$COMPARE_ROOT/tfstate" "$@" || exit $?
        select_workspace
        echo "workspace: $(tf workspace show)"
        ;;
    plan)
        select_workspace
        tf plan -input=false "${vars[@]}" "$@"
        ;;
    apply)
        select_workspace
        tf apply -input=false -auto-approve "${vars[@]}" "$@"
        ;;
    stop)
        select_workspace
        tf apply -input=false -auto-approve "${vars[@]}" -var desired_state=stopped "$@"
        ;;
    destroy)
        select_workspace
        tf destroy -input=false "${vars[@]}" "${destroy_approve[@]}" "$@"
        ;;
    status)
        bash "$HERE/compare_env.sh" status "$scenario"
        ;;
    output)
        select_workspace
        tf output -json
        ;;
    *) usage ;;
esac
