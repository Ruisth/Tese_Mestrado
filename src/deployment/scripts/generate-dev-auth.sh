#!/bin/sh
# generate-dev-auth.sh — create the Mosquitto password file for the two dev
# users (CONTRACTS.md §1): egw-simulator (publish-only) and egw-controller
# (subscribe-only). Authorization itself lives in mosquitto/config/acl.
#
# The hashing is done by mosquitto_passwd INSIDE the pinned eclipse-mosquitto
# container (no mosquitto tooling needed on the host). Passwords are taken
# from arguments or environment and are NEVER printed by this script; they
# are handed to the container through its environment, not through the host
# command line.
#
# Usage:
#   ./generate-dev-auth.sh [<simulator-password> <controller-password>]
#
# Without arguments the passwords are read from MOSQUITTO_SIMULATOR_PASSWORD
# and MOSQUITTO_CONTROLLER_PASSWORD (e.g. exported or sourced from .env).
# The output file mosquitto/config/passwd is recreated on every run and is
# never committed (see src/deployment/.gitignore).

set -eu

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
CONF_DIR="${CONF_DIR:-$SCRIPT_DIR/../mosquitto/config}"
LOCK_FILE="${LOCK_FILE:-$SCRIPT_DIR/../images.lock.env}"

SIM_PASS="${1:-${MOSQUITTO_SIMULATOR_PASSWORD:-}}"
CTL_PASS="${2:-${MOSQUITTO_CONTROLLER_PASSWORD:-}}"

if [ -z "$SIM_PASS" ]; then
    echo "ERROR: simulator password missing." >&2
    echo "       Pass it as argument 1 or export MOSQUITTO_SIMULATOR_PASSWORD." >&2
    exit 2
fi
if [ -z "$CTL_PASS" ]; then
    echo "ERROR: controller password missing." >&2
    echo "       Pass it as argument 2 or export MOSQUITTO_CONTROLLER_PASSWORD." >&2
    exit 2
fi

command -v docker >/dev/null 2>&1 || {
    echo "ERROR: docker CLI not found" >&2; exit 1;
}
[ -d "$CONF_DIR" ] || {
    echo "ERROR: config directory not found: $CONF_DIR" >&2; exit 1;
}

# Use the digest-pinned broker image from images.lock.env when available so
# the hash format matches the deployed broker exactly.
#
# EGW_BROKER_IMAGE overrides the reference (same variable as
# prepare-broker-secrets.sh). It is needed on the offline Yocto guest, where
# the image was loaded from an archive and only its tag resolves locally:
#   EGW_BROKER_IMAGE=docker.io/library/eclipse-mosquitto:2.0.22
IMAGE="${EGW_BROKER_IMAGE:-}"
if [ -z "$IMAGE" ] && [ -f "$LOCK_FILE" ]; then
    IMAGE=$(sed -n 's/^IMAGE_MOSQUITTO=//p' "$LOCK_FILE" | head -n 1)
fi
[ -n "$IMAGE" ] || IMAGE="docker.io/library/eclipse-mosquitto:2.0.22"

echo "Creating $CONF_DIR/passwd (users: egw-simulator, egw-controller)"
echo "using image: $IMAGE"

# -e VAR (without =value) forwards the variable from the docker client's own
# environment, so the passwords never appear in the host argv. Inside the
# ephemeral container, -c (re)creates the file, the second call appends.
#
# Ownership: the container runs as root, so the file would be left root:root.
# Mosquitto 2.x opens password_file only AFTER dropping to its unprivileged
# user (https://mosquitto.org/documentation/migrating-to-2-0/), and
# compose.yaml mounts the file read-only, so the image entrypoint cannot
# repair it. The file is therefore handed to the image's own "mosquitto"
# user (uid/gid 1883 in the official 2.0.x image) with mode 0600, resolved by
# NAME inside the image so the ids always match the deployed broker.
SIM_PASS="$SIM_PASS" CTL_PASS="$CTL_PASS" \
docker run --rm -e SIM_PASS -e CTL_PASS \
    -v "$CONF_DIR:/work" "$IMAGE" \
    sh -c 'set -eu
        mosquitto_passwd -c -b /work/passwd egw-simulator "$SIM_PASS"
        mosquitto_passwd -b /work/passwd egw-controller "$CTL_PASS"
        chown mosquitto:mosquitto /work/passwd
        chmod 600 /work/passwd'

echo "Done. Password file written (hashed, owned by the image's mosquitto user, mode 600)."
echo "NEXT: run scripts/prepare-broker-secrets.sh (server.key ownership + read test as the broker uid)."
echo "Keep MOSQUITTO_CONTROLLER_PASSWORD in .env equal to the controller"
echo "password just set, and MOSQUITTO_SIMULATOR_PASSWORD equal to the"
echo "simulator password (the simulator passes it via --password)."
