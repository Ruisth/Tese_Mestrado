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

# gx ATTEMPT NAME GUEST-COMMAND: run one command on the guest over ssh,
# inside the attempt (stdout/stderr kept). The guest command is passed as an
# argument, never re-quoted.
gx() {
    local a=$1 name=$2
    shift 2
    ex "$a" "$name" env E="$SESSION" bash -c '. "$E/scripts/session_common.sh" && gssh "$1"' _ "$1"
}

# gcp ATTEMPT NAME SRC DEST: scp over the session's pinned host key.
gcp() {
    local a=$1 name=$2
    shift 2
    ex "$a" "$name" env E="$SESSION" bash -c '. "$E/scripts/session_common.sh" && gscp "$1" "$2"' _ "$1" "$2"
}

# The host-side preamble of runbook 6.1, from the clean clone.
HOST_PRE=". $VENV/bin/activate && set -a && . \$HOME/egw-tcg/.env && set +a && export EGW_CLONE=$REPO && . \$HOME/egw-tcg/itest-helpers.sh && . \$HOME/egw-tcg/tunnel.sh && { tunnel_check || tunnel_up; }"

# hx ATTEMPT NAME HOST-SCRIPT: run a host step with the 6.1 preamble loaded.
hx() {
    local a=$1 name=$2
    shift 2
    ex "$a" "$name" bash -c "$HOST_PRE && $1"
}
