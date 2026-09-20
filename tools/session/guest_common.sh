#!/bin/bash
# Guest-session helpers for the work-order drivers (source after common.sh).
# The session's own attempt directory holds scripts/, boot/, guest/, host/;
# its path is kept in $EXEC/current_session while the guest is up.
EC=${EGW_EVIDENCE_CANDIDATES:-/home/ruisth/yocto/evidence-candidates}
OLD=${EGW_YOCTO_CHECKOUT:-/home/ruisth/yocto/egw}   # the checkout that holds build-integrated/
BUILD=$OLD/src/yocto/build-integrated
DEP=$BUILD/tmp/deploy/images/qemuarm64
ROOTFS_EXT4=$DEP/egw-gateway-image-qemuarm64.rootfs-20260918120819.ext4
DATA_DISK=${EGW_DATA_DISK:-/home/ruisth/yocto/egw-integrated/egw-data.img}
EXPECT_SERVICES=egw-mosquitto-1,egw-mongodb-1,egw-ditto-policies-1,egw-ditto-things-1,egw-ditto-gateway-1,egw-controller-1
DC='docker compose --env-file .env --env-file images.lock.env'
SESSION=$(cat "$EXEC/current_session" 2> /dev/null || true)

# A STEP THAT NEVER REACHED WHAT IT WAS TO RUN IS NOT AN ANSWER.
# The three wrappers below each load something before the step's own command
# runs: gx and gcp the session's ssh helpers, hx the host preamble of runbook
# 6.1. When that loading fails - a session helper that is gone, a tunnel that
# is down - or when ssh itself cannot connect (its own 255), the step's command
# never ran, and the status the wrapper would otherwise return is
# indistinguishable from the command's own. Each wrapper therefore answers with
# EXIT_NOT_REACHED (97, common.sh) and says on stderr what was not reached, so
# that a driver records "the guest did not answer" rather than reading a fault
# out of a step that observed nothing. 97 is written literally in the one-line
# shells below, which cannot see the shell variable.

# gx ATTEMPT NAME GUEST-COMMAND: run one command on the guest over ssh,
# inside the attempt (stdout/stderr kept). The guest command is passed as an
# argument, never re-quoted.
gx() {
    local a=$1 name=$2 rc
    shift 2
    ex "$a" "$name" env E="$SESSION" bash -c '. "$E/scripts/session_common.sh" || { echo "STOP: the session ssh helpers ($E/scripts/session_common.sh) could not be loaded: NOTHING was run on the guest" >&2; exit 97; }
gssh "$1"' _ "$1"
    rc=$?
    # ssh's own 255 is 'the connection was not made', never a guest command's
    # status: the guest scripts of these drivers answer 0, 1, 2 or 4.
    [ "$rc" -ne 255 ] || rc=$EXIT_NOT_REACHED
    return "$rc"
}

# gcp ATTEMPT NAME SRC DEST: scp over the session's pinned host key.
gcp() {
    local a=$1 name=$2
    shift 2
    ex "$a" "$name" env E="$SESSION" bash -c '. "$E/scripts/session_common.sh" || { echo "STOP: the session ssh helpers ($E/scripts/session_common.sh) could not be loaded: NOTHING was copied from the guest" >&2; exit 97; }
gscp "$1" "$2"' _ "$1" "$2"
}

# The host-side preamble of runbook 6.1, from the clean clone.
HOST_PRE=". $VENV/bin/activate && set -a && . \$HOME/egw-tcg/.env && set +a && export EGW_CLONE=$REPO && . \$HOME/egw-tcg/itest-helpers.sh && . \$HOME/egw-tcg/tunnel.sh && { tunnel_check || tunnel_up; }"

# hx ATTEMPT NAME HOST-SCRIPT: run a host step with the 6.1 preamble loaded.
# The preamble is a group of its own, so a HOST-SCRIPT of several lines runs
# only when it succeeded, and a preamble that failed is 97 and not the step's
# own status.
hx() {
    local a=$1 name=$2
    shift 2
    ex "$a" "$name" bash -c "{ $HOST_PRE ; } || { echo 'STOP: the host preamble of runbook 6.1 (the venv, the secrets, the helpers and the tunnels) could not be loaded: the step never ran' >&2; exit 97; }
$1"
}

# --- the 'running and healthy' wait the two G2 drivers share ----------------
# G2 requires all six expected services RUNNING and HEALTHY. That is stricter
# than the engineering preflight, which judges a container whose health check
# has not concluded ('starting') by its state alone. There is ONE
# implementation of the stricter wait, here: gate_health.sh records it as the
# gate's precondition and persistence.sh uses the same wait after the restart,
# so the two never drift apart.

# healthy_seconds NAME DEFAULT: a bounded wait read from the environment, in
# whole seconds. Prints nothing and returns non-zero when the value is not a
# whole number: a limit that could not be read is never silently replaced by
# the default, because the driver would then wait for something nobody asked.
healthy_seconds() {
    local value=${!1:-}
    [ -n "$value" ] || value=$2
    case "$value" in
        '' | *[!0-9]*)
            echo "healthy_seconds: $1='$value' is not a whole number of seconds" >&2
            return 1
            ;;
    esac
    printf '%s' "$value"
}

# guest_literal VALUE: non-zero when VALUE cannot be written into a guest
# script as a single-quoted literal, because it holds a single quote or a
# newline. A driver checks the parameters it passes to the guest ONCE, before
# it starts anything, rather than writing a script that would mean something
# else than it says.
guest_literal() {
    case $1 in *\'*) return 1 ;; esac
    [ "$1" = "${1%%$'\n'*}" ] || return 1
    return 0
}

# healthy_wait_script LIMIT STEP: the guest command that polls until the six
# expected services are 'running' AND 'healthy'. It runs under BusyBox ash, so
# it holds no bashism, and its three parameters are written as plain
# assignments in front of a QUOTED here-document: nothing inside the script is
# expanded twice, and no quoting of the driver's own text can reach it.
#
# Every sample is printed with its instant, so the transition is visible in the
# console record. The answer is one of four, and the two that are not a pass
# are never mixed, because observing the system fail is a result while failing
# to observe is not:
#   0  every expected service is running and healthy
#   1  the limit passed and at least one of them was not: the system's state
#   2  the state of at least one of them could NOT be determined at all
#   4  both at the limit: neither observation erases the other
healthy_wait_script() {
    printf "EXPECT='%s'\nLIMIT='%s'\nSTEP='%s'\n" "$EXPECT_SERVICES" "$1" "$2"
    cat << 'GUEST_HEALTHY_WAIT'
t0=$(date +%s) || { echo 'STOP: the guest clock could not be read'; exit 2; }
n=0
while :; do
    n=$((n + 1))
    now=$(date -u +%Y-%m-%dT%H:%M:%SZ) || now=unreadable-instant
    line=
    notready=
    undetermined=
    IFS=,
    set -- $EXPECT
    unset IFS
    for s in "$@"; do
        # 'docker inspect' fails both for a container the daemon does not hold
        # and for a daemon that did not answer at all, and the two are not the
        # same observation: only the daemon's own 'No such object' says the
        # container is gone; anything else determines nothing about it.
        if out=$(docker inspect -f '{{.State.Status}}' "$s" 2>&1); then
            st=$out
            [ -n "$st" ] || st=indeterminate
        else
            case "$out" in
                *'No such object'* | *'No such container'* | *'no such object'* | *'no such container'*)
                    st=absent ;;
                *) st=indeterminate ;;
            esac
        fi
        hl=$(docker inspect -f '{{if .State.Health}}{{.State.Health.Status}}{{else}}none{{end}}' "$s" 2> /dev/null) || hl=unreadable
        [ -n "$hl" ] || hl=unreadable
        line="$line $s=$st/$hl"
        case "$st" in
            running)
                # G2 asks for 'healthy'. A health check that has not concluded
                # ('starting'), one that is failing ('unhealthy') and a
                # container that declares none ('none') are all NOT healthy,
                # and this driver changes nothing, so each is kept as the word
                # it is and polled again until the limit decides.
                case "$hl" in
                    healthy) ;;
                    starting | unhealthy | none) notready="$notready $s(status=$st health=$hl)" ;;
                    *) undetermined="$undetermined $s(its health could not be read)" ;;
                esac
                ;;
            absent) notready="$notready $s(the daemon does not hold this container)" ;;
            indeterminate) undetermined="$undetermined $s(its status could not be read)" ;;
            *) notready="$notready $s(status=$st health=$hl)" ;;
        esac
    done
    echo "$now sample $n:$line"
    if [ -z "$notready" ] && [ -z "$undetermined" ]; then
        echo "ALL HEALTHY: the $# expected services are running and healthy (sample $n)"
        exit 0
    fi
    t=$(date +%s) || { echo 'STOP: the guest clock could not be read'; exit 2; }
    if [ $((t - t0)) -ge "$LIMIT" ]; then
        [ -z "$notready" ] || echo "NOT HEALTHY after $((t - t0)) s and $n sample(s):$notready"
        [ -z "$undetermined" ] || echo "NOT DETERMINED after $((t - t0)) s and $n sample(s):$undetermined"
        [ -z "$notready" ] || [ -z "$undetermined" ] || exit 4
        [ -z "$undetermined" ] || exit 2
        exit 1
    fi
    sleep "$STEP"
done
GUEST_HEALTHY_WAIT
}

# healthy_wait ATTEMPT NAME LIMIT STEP: run that wait as one recorded step.
# Returns the guest script's own answer (0, 1, 2, 4), the lost-capture status
# of 'local_export exec' (74), or 3 when the expected service list is not a
# list of plain names and the wait was therefore never started.
healthy_wait() {
    local a=$1 name=$2 limit=$3 step=$4
    case "$EXPECT_SERVICES" in
        '' | *[!A-Za-z0-9,._-]*)
            echo "healthy_wait: EXPECT_SERVICES='$EXPECT_SERVICES' is not a list of service names" >&2
            return 3
            ;;
    esac
    case "$limit$step" in
        '' | *[!0-9]*)
            echo "healthy_wait: the limit '$limit' and the step '$step' must be whole seconds" >&2
            return 3
            ;;
    esac
    gx "$a" "$name" "$(healthy_wait_script "$limit" "$step")"
}
