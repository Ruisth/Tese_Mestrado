#!/usr/bin/env bash
# Generate the controller's complete, hash-locked runtime dependency set.
#
# Run this ON the campaign ARM64 VM from the repository's src/ directory (or
# from any directory; paths are resolved from this script). It deliberately
# refuses x86_64 and other hosts: committing a lock resolved for the wrong
# platform would give a false reproducibility claim.

set -euo pipefail

SCRIPT_DIR=$(CDPATH='' cd -- "$(dirname -- "$0")" && pwd)
SRC_DIR=$(CDPATH='' cd -- "$SCRIPT_DIR/../.." && pwd)
LOCK_FILE="$SRC_DIR/requirements-runtime.lock"
TMP_LOCK="$SRC_DIR/.requirements-runtime.lock.tmp"
BASE_IMAGE="docker.io/library/python:3.12.13-slim@sha256:229a2c5bfa27522db7815ea81f9bed70af17ccb9de9fc7ad142b1877b5830d36"
PIP_TOOLS_VERSION="7.5.0"

case "$(uname -m)" in
    aarch64|arm64) ;;
    *)
        echo "ERROR: runtime lock generation is restricted to an ARM64 host; got $(uname -m)." >&2
        echo "Run this script on the campaign aarch64 VM. No lock was written." >&2
        exit 2
        ;;
esac

command -v docker >/dev/null 2>&1 || {
    echo "ERROR: docker is required to resolve inside the pinned runtime base image." >&2
    exit 1
}

rm -f -- "$TMP_LOCK"
trap 'rm -f -- "$TMP_LOCK"' EXIT

# Match both architecture and Python base used by src/Dockerfile. Running as
# the invoking uid/gid prevents a root-owned lock in the checkout. pip-tools
# is a generation-only dependency and is intentionally absent from the lock.
docker run --rm \
    --platform linux/arm64 \
    --user "$(id -u):$(id -g)" \
    --env "PIP_TOOLS_VERSION=$PIP_TOOLS_VERSION" \
    --volume "$SRC_DIR:/work" \
    --workdir /work \
    "$BASE_IMAGE" \
    sh -euc '
        test "$(uname -m)" = aarch64
        python -m venv /tmp/egw-lock-venv
        /tmp/egw-lock-venv/bin/python -m pip install --disable-pip-version-check \
            "pip-tools==$PIP_TOOLS_VERSION"
        /tmp/egw-lock-venv/bin/python -m piptools compile \
            --all-build-deps \
            --allow-unsafe \
            --generate-hashes \
            --resolver=backtracking \
            --strip-extras \
            --output-file /work/.requirements-runtime.lock.tmp \
            /work/pyproject.toml
        /tmp/egw-lock-venv/bin/python -m pip install \
            --disable-pip-version-check \
            --require-hashes \
            --only-binary=:all: \
            --requirement /work/.requirements-runtime.lock.tmp
        /tmp/egw-lock-venv/bin/python -m pip install \
            --disable-pip-version-check \
            --no-build-isolation \
            --no-deps \
            /work
        /tmp/egw-lock-venv/bin/python -m pip check
    '

test -s "$TMP_LOCK" || {
    echo "ERROR: resolver produced no lock file." >&2
    exit 1
}
grep -q -- '--hash=sha256:' "$TMP_LOCK" || {
    echo "ERROR: generated file contains no hashes." >&2
    exit 1
}

mv -- "$TMP_LOCK" "$LOCK_FILE"
trap - EXIT
echo "Runtime lock written and hash-verified: $LOCK_FILE"
echo "Next: review it, switch Dockerfile to --require-hashes +"
echo "--no-build-isolation + --no-deps,"
echo "then build on ARM64 and record the image digest and 'pip check' output."
