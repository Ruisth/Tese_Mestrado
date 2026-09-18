#!/bin/sh
# build-controller-image.sh — build, export and identify the prebuilt
# controller image. Runs on a PROVISIONING HOST (Docker Desktop on Windows
# through Git Bash, or any Linux with Docker and buildx), never on the
# gateway: the gateway only loads the archive (deployment README step 4b) and
# compose.yaml has no "build:" for the controller.
#
# What it does, in order:
#   1. identifies the source: git commit of the checkout and the state of the
#      build context src/ (the only directory that reaches the image; see
#      src/.dockerignore). A build context with modified or untracked files,
#      or with git-ignored files below a path the Dockerfile copies, is
#      REFUSED unless --allow-dirty is given; changes outside src/ cannot
#      reach the image and are only counted in the record;
#   2. builds egw-controller:0.1.0 for linux/arm64 with buildx from
#      src/Dockerfile, without cache (so that built_utc bounds the moment the
#      Python dependencies were resolved), without provenance/SBOM
#      attestations (the archive must hold one plain image), with the commit
#      as label org.opencontainers.image.revision;
#   3. reads architecture and OS back from the built image and refuses
#      anything other than linux/arm64;
#   4. takes `python --version` and `pip freeze --all` FROM the built image
#      (one-shot containers, no network);
#   5. exports the image with `docker save` and reads the image id (the
#      digest of the image configuration) from the archive itself: that is
#      the id a classic Docker engine reports after `docker load`, whatever
#      image store the build host uses (with the containerd image store of
#      Docker Desktop `docker image inspect` reports a manifest digest
#      instead; it is recorded as builder_image_id for information);
#   6. writes the identity record next to the archive.
# It pushes nothing and needs no registry credentials.
#
# The Python dependencies of this image are NOT locked: src/Dockerfile runs
# `pip install .` without hashes. The pip_freeze lines of the record say what
# was installed; they do not make the build reproducible. To be resolved
# before the experimental freeze (scripts/generate-runtime-lock.sh, README
# "Runtime Python lock").
#
# Output (in <output-dir>, which must lie outside src/; existing files are
# never overwritten):
#   egw-controller-0.1.0-arm64.tar            docker save archive
#   egw-controller-0.1.0-arm64.identity.txt   key=value lines, one value per
#       line; the pip freeze is carried as repeated pip_freeze=<line> entries
#       (recover it with: sed -n 's/^pip_freeze=//p' <record>)
#
# Usage:
#   sh build-controller-image.sh [--allow-dirty] <output-dir>
#
# Exit codes: 0 = archive and record written; 1 = a step failed; 2 = usage or
# missing tool; 3 = dirty build context; 129, 130, 143 = interrupted (HUP,
# INT, TERM). Nothing is left in <output-dir> unless the exit code is 0.
#
# POSIX sh; needs docker with buildx, git, tar and sha256sum.
# UNVERIFIED: not yet executed against a Docker engine (written 2026-09-18);
# the decision logic is exercised with a stub docker in
# src/tests/test_deployment_prebuilt_controller.py.

set -eu

IMAGE="egw-controller:0.1.0"
PLATFORM="linux/arm64"
BASENAME="egw-controller-0.1.0-arm64"

ALLOW_DIRTY=0
OUT_ARG=""
for arg in "$@"; do
    case "$arg" in
        --allow-dirty) ALLOW_DIRTY=1 ;;
        -h|--help) sed -n '2,56p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
        -*) echo "ERROR: unknown option: $arg" >&2; exit 2 ;;
        *)
            [ -z "$OUT_ARG" ] || { echo "ERROR: more than one output directory given" >&2; exit 2; }
            OUT_ARG=$arg
            ;;
    esac
done
[ -n "$OUT_ARG" ] || { echo "usage: $0 [--allow-dirty] <output-dir>" >&2; exit 2; }

for tool in docker git tar sha256sum; do
    command -v "$tool" >/dev/null 2>&1 || { echo "ERROR: $tool not found in PATH" >&2; exit 2; }
done
docker buildx version >/dev/null 2>&1 || { echo "ERROR: 'docker buildx' is not available" >&2; exit 2; }

SCRIPT_DIR=$(CDPATH='' cd -- "$(dirname -- "$0")" && pwd)
SRC_DIR=$(CDPATH='' cd -- "$SCRIPT_DIR/../.." && pwd)
[ -f "$SRC_DIR/Dockerfile" ] || { echo "ERROR: $SRC_DIR/Dockerfile not found" >&2; exit 1; }

mkdir -p -- "$OUT_ARG" || { echo "ERROR: cannot create $OUT_ARG" >&2; exit 1; }
OUT_DIR=$(CDPATH='' cd -- "$OUT_ARG" && pwd)
case "$OUT_DIR/" in
    "$SRC_DIR"/*)
        echo "ERROR: the output directory must lie outside the build context $SRC_DIR" >&2
        exit 2
        ;;
esac
ARCHIVE="$BASENAME.tar"
RECORD="$BASENAME.identity.txt"
for f in "$ARCHIVE" "$RECORD"; do
    [ ! -e "$OUT_DIR/$f" ] || { echo "ERROR: refusing to overwrite $OUT_DIR/$f" >&2; exit 2; }
done

# --- 1. source identity --------------------------------------------------------
if ! COMMIT=$(git -C "$SRC_DIR" rev-parse --verify HEAD 2>/dev/null); then
    echo "ERROR: $SRC_DIR is not inside a git checkout: the source cannot be identified" >&2
    exit 1
fi
# "-- ." limits the status to src/, the build context; untracked files count
# (they would be copied into the image unless .dockerignore excludes them).
CONTEXT_CHANGES=$(git -C "$SRC_DIR" status --porcelain -- .)
ALL_CHANGES=$(git -C "$SRC_DIR" status --porcelain)
count_lines() { if [ -n "$1" ]; then printf '%s\n' "$1" | wc -l | tr -d ' '; else echo 0; fi; }
N_OUTSIDE=$(( $(count_lines "$ALL_CHANGES") - $(count_lines "$CONTEXT_CHANGES") ))
# git-ignored files are not in that status, yet the root .gitignore ignores
# names that src/.dockerignore lets through (data/, .env, *.log, *.pem ...):
# below a path the Dockerfile copies they reach /app. They count as changes.
# __pycache__/ and *.egg-info/ are excluded by .dockerignore at every depth.
# "--ignored=matching" names the path that matches the rule, not a parent
# directory that holds nothing else.
PREFIX=$(git -C "$SRC_DIR" rev-parse --show-prefix)
COPY_SOURCES=$(sed -n 's/^COPY[[:space:]]\{1,\}\([^[:space:]]\{1,\}\)[[:space:]].*/\1/p' "$SRC_DIR/Dockerfile")
[ -n "$COPY_SOURCES" ] || { echo "ERROR: no COPY line found in $SRC_DIR/Dockerfile" >&2; exit 1; }
if ! WITH_IGNORED=$(git -C "$SRC_DIR" status --porcelain --ignored=matching -- .); then
    echo "ERROR: 'git status --ignored=matching' failed (git 2.16 or later is needed)" >&2
    exit 1
fi
IGNORED_IN_IMAGE=$(printf '%s\n' "$WITH_IGNORED" | sed -n 's/^!! "\{0,1\}//p' |
    while IFS= read -r entry; do
        case "$entry" in
            *__pycache__/*|*.egg-info/*) continue ;;
        esac
        for copied in $COPY_SOURCES; do
            case "$entry" in
                "$PREFIX$copied"*) printf '!! %s\n' "$entry" ;;
            esac
        done
    done)
if [ -n "$IGNORED_IN_IMAGE" ]; then
    CONTEXT_CHANGES=$(printf '%s\n%s' "$CONTEXT_CHANGES" "$IGNORED_IN_IMAGE" | sed '/^$/d')
fi
N_CONTEXT=$(count_lines "$CONTEXT_CHANGES")
TREE_STATE=clean
REVISION=$COMMIT
if [ "$N_CONTEXT" -gt 0 ]; then
    TREE_STATE=dirty
    REVISION="$COMMIT-dirty"
    if [ "$ALLOW_DIRTY" -ne 1 ]; then
        echo "ERROR: the build context $SRC_DIR has $N_CONTEXT modified, untracked or git-ignored (!!) path(s):" >&2
        printf '%s\n' "$CONTEXT_CHANGES" >&2
        echo "       build from a clean checkout, or pass --allow-dirty (development only:" >&2
        echo "       the record will say source_tree_state=dirty)." >&2
        exit 3
    fi
    echo "WARNING: building from a DIRTY build context (--allow-dirty): not for evidence" >&2
fi

BASE_IMAGE=$(sed -n 's/^FROM[[:space:]]\{1,\}\([^[:space:]]\{1,\}\).*/\1/p' "$SRC_DIR/Dockerfile")
case "$BASE_IMAGE" in
    *@sha256:*) ;;
    *) echo "ERROR: expected exactly one digest-pinned FROM line in $SRC_DIR/Dockerfile, got: $BASE_IMAGE" >&2; exit 1 ;;
esac
[ "$(count_lines "$BASE_IMAGE")" -eq 1 ] ||
    { echo "ERROR: more than one FROM line in $SRC_DIR/Dockerfile" >&2; exit 1; }
DOCKERFILE_SHA256=$(sha256sum "$SRC_DIR/Dockerfile" | awk '{print $1}')

# Nothing of a failed or interrupted run stays behind: an archive without a
# record is an unidentified image. dash does not run the EXIT trap when a
# signal ends it, hence the explicit exits.
DONE=0
cleanup() {
    rm -f -- "$OUT_DIR/$RECORD.tmp" "$OUT_DIR/$BASENAME.pip-freeze.tmp"
    [ "$DONE" -eq 1 ] || rm -f -- "$OUT_DIR/$ARCHIVE" "$OUT_DIR/$RECORD"
}
trap cleanup EXIT
trap 'exit 129' HUP
trap 'exit 130' INT
trap 'exit 143' TERM

# --- 2. build --------------------------------------------------------------------
# Relative paths from inside src/: nothing for Git Bash to convert.
echo "[build] $IMAGE for $PLATFORM from commit $REVISION" >&2
(cd "$SRC_DIR" && docker buildx build \
    --platform "$PLATFORM" \
    --provenance=false \
    --sbom=false \
    --no-cache \
    --load \
    --label "org.opencontainers.image.revision=$REVISION" \
    --tag "$IMAGE" \
    --file Dockerfile \
    .) >&2
BUILT_UTC=$(date -u +%Y-%m-%dT%H:%M:%SZ)

# --- 3. what was built -----------------------------------------------------------
IMAGE_ARCH=$(docker image inspect --format '{{.Architecture}}' "$IMAGE")
IMAGE_OS=$(docker image inspect --format '{{.Os}}' "$IMAGE")
BUILDER_IMAGE_ID=$(docker image inspect --format '{{.Id}}' "$IMAGE")
if [ "$IMAGE_OS/$IMAGE_ARCH" != "$PLATFORM" ]; then
    echo "ERROR: built image is $IMAGE_OS/$IMAGE_ARCH, expected $PLATFORM" >&2
    exit 1
fi

# --- 4. interpreter and installed distributions, from the image itself ---------
PYTHON_VERSION=$(docker run --rm --platform "$PLATFORM" --network none \
    --entrypoint python "$IMAGE" --version)
docker run --rm --platform "$PLATFORM" --network none \
    --entrypoint python "$IMAGE" -m pip freeze --all >"$OUT_DIR/$BASENAME.pip-freeze.tmp"
[ -s "$OUT_DIR/$BASENAME.pip-freeze.tmp" ] || { echo "ERROR: pip freeze returned nothing" >&2; exit 1; }
PIP_FREEZE_SHA256=$(sha256sum "$OUT_DIR/$BASENAME.pip-freeze.tmp" | awk '{print $1}')

# --- 5. export, and the image id as the archive states it ----------------------
# Work inside the output directory with bare file names: GNU tar reads a
# colon in an archive name (C:/...) as a remote host.
cd "$OUT_DIR"
if docker save --help 2>/dev/null | grep -q -- '--platform'; then
    docker save --platform "$PLATFORM" -o "$ARCHIVE" "$IMAGE"
else
    docker save -o "$ARCHIVE" "$IMAGE"
fi
[ -s "$ARCHIVE" ] || { echo "ERROR: docker save wrote no archive" >&2; exit 1; }

MANIFEST=$(tar -xOf "$ARCHIVE" manifest.json)
CONFIG_PATH=$(printf '%s' "$MANIFEST" | tr ',{' '\n\n' |
    sed -n 's/^[[:space:]]*"Config"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p')
[ "$(count_lines "$CONFIG_PATH")" -eq 1 ] ||
    { echo "ERROR: manifest.json of the archive does not describe exactly one image" >&2; exit 1; }
printf '%s' "$MANIFEST" | grep -q -F "\"$IMAGE\"" ||
    { echo "ERROR: manifest.json of the archive does not carry the tag $IMAGE" >&2; exit 1; }
# Both archive layouts name the configuration by its digest:
# blobs/sha256/<hex> (OCI layout) or <hex>.json (legacy layout).
CONFIG_HEX=${CONFIG_PATH##*/}
CONFIG_HEX=${CONFIG_HEX%.json}
case "$CONFIG_HEX" in
    *[!0-9a-f]*|'') echo "ERROR: unexpected Config entry in manifest.json: $CONFIG_PATH" >&2; exit 1 ;;
esac
[ "${#CONFIG_HEX}" -eq 64 ] ||
    { echo "ERROR: unexpected Config entry in manifest.json: $CONFIG_PATH" >&2; exit 1; }
CONFIG_SHA256=$(tar -xOf "$ARCHIVE" "$CONFIG_PATH" | sha256sum | awk '{print $1}')
[ "$CONFIG_SHA256" = "$CONFIG_HEX" ] ||
    { echo "ERROR: the image configuration in the archive does not hash to its name ($CONFIG_PATH)" >&2; exit 1; }
IMAGE_ID="sha256:$CONFIG_HEX"

ARCHIVE_SHA256=$(sha256sum "$ARCHIVE" | awk '{print $1}')
ARCHIVE_SIZE=$(wc -c <"$ARCHIVE" | tr -d ' ')

# --- 6. identity record ----------------------------------------------------------
DOCKER_CLIENT=$(docker version --format '{{.Client.Version}}')
DOCKER_SERVER=$(docker version --format '{{.Server.Version}}')
BUILDX_VERSION=$(docker buildx version)
{
    echo "identity_format=1"
    echo "image_ref=$IMAGE"
    echo "image_id=$IMAGE_ID"
    echo "image_architecture=$IMAGE_ARCH"
    echo "image_os=$IMAGE_OS"
    echo "builder_image_id=$BUILDER_IMAGE_ID"
    echo "source_commit=$COMMIT"
    echo "source_tree_state=$TREE_STATE"
    echo "source_tree_scope=src/ (the build context); files changed outside it: $N_OUTSIDE"
    echo "image_revision_label=$REVISION"
    echo "dockerfile_base_image=$BASE_IMAGE"
    echo "dockerfile_sha256=$DOCKERFILE_SHA256"
    echo "archive_file=$ARCHIVE"
    echo "archive_sha256=$ARCHIVE_SHA256"
    echo "archive_size_bytes=$ARCHIVE_SIZE"
    echo "python_version=$PYTHON_VERSION"
    echo "python_dependencies=UNLOCKED (pip install . without hashes; to be resolved before the experimental freeze)"
    echo "pip_freeze_sha256=$PIP_FREEZE_SHA256"
    echo "docker_client_version=$DOCKER_CLIENT"
    echo "docker_server_version=$DOCKER_SERVER"
    echo "buildx_version=$BUILDX_VERSION"
    echo "build_host=$(uname -srm)"
    echo "built_utc=$BUILT_UTC"
    sed 's/^/pip_freeze=/' "$BASENAME.pip-freeze.tmp"
} >"$RECORD.tmp"
mv -- "$RECORD.tmp" "$RECORD"
DONE=1

echo "OK: $OUT_DIR/$ARCHIVE"
echo "    sha256 $ARCHIVE_SHA256, $ARCHIVE_SIZE bytes"
echo "OK: $OUT_DIR/$RECORD"
echo "    image_id $IMAGE_ID ($IMAGE_OS/$IMAGE_ARCH), commit $REVISION"
echo "Next, on the gateway (no registry is involved for this image):"
echo "    docker load -i $ARCHIVE        # or: ssh <gateway> docker load < $ARCHIVE"
echo "    sh scripts/verify-controller-image.sh $RECORD"
