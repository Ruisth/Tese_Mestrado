#!/bin/sh
# resolve-image-lock.sh — verify (or populate) the OCI digests pinned in
# images.lock.env against the registry, ON THE ARM64 VM (plan §9.2: the
# deploy uses only linux/arm64-native images pinned by digest).
#
# For every IMAGE_<NAME>=<repo>:<tag>[@sha256:<digest>] entry:
#   1. fetch the manifest list of <repo>:<tag> (docker manifest inspect);
#   2. confirm a linux/arm64 entry exists — hard failure otherwise;
#   3. compare the current manifest-list digest of the tag with the locked
#      digest — hard failure on mismatch (a moved tag must be investigated
#      and re-pinned deliberately, never silently);
#   4. entries without a digest are reported; with --update the resolved
#      digest is written back into images.lock.env.
#
# Usage:
#   ./resolve-image-lock.sh            # verify only (CI/pre-deploy mode)
#   ./resolve-image-lock.sh --update   # additionally pin missing digests
#
# Requires: docker CLI; `docker buildx` for digest comparison (present in
# docker-ce on Ubuntu 24.04). Manual fallback per image:
#   docker manifest inspect <repo>:<tag>

set -u

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
LOCK_FILE="${LOCK_FILE:-$SCRIPT_DIR/../images.lock.env}"
UPDATE=0

for arg in "$@"; do
    case "$arg" in
        --update) UPDATE=1 ;;
        -h|--help) sed -n '2,21p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
        *) echo "ERROR: unknown argument: $arg" >&2; exit 2 ;;
    esac
done

[ -f "$LOCK_FILE" ] || { echo "ERROR: lock file not found: $LOCK_FILE" >&2; exit 1; }
command -v docker >/dev/null 2>&1 || { echo "ERROR: docker CLI not found" >&2; exit 1; }

BUILDX=0
if docker buildx version >/dev/null 2>&1; then
    BUILDX=1
else
    echo "WARNING: 'docker buildx' unavailable; tag-drift comparison degraded." >&2
fi

# Current manifest-list digest of a tag (empty on failure).
current_list_digest() {
    if [ "$BUILDX" -eq 1 ]; then
        docker buildx imagetools inspect "$1" --format '{{.Manifest.Digest}}' 2>/dev/null || true
    fi
}

# True if the referenced manifest (list) advertises a linux/arm64 image.
has_arm64() {
    docker manifest inspect "$1" 2>/dev/null \
        | grep -Eq '"architecture":[[:space:]]*"arm64"'
}

failures=0
entries=0

while IFS= read -r line; do
    case "$line" in
        IMAGE_*=*) ;;
        *) continue ;;
    esac
    entries=$((entries + 1))
    name=${line%%=*}
    ref=${line#*=}
    case "$ref" in
        *@sha256:*)
            repo_tag=${ref%%@*}
            locked=${ref#*@}
            ;;
        *)
            repo_tag=$ref
            locked=""
            ;;
    esac

    printf '== %s (%s)\n' "$name" "$repo_tag"

    if ! docker manifest inspect "$repo_tag" >/dev/null 2>&1; then
        echo "   ERROR: cannot fetch manifest list for $repo_tag"
        echo "          run manually: docker manifest inspect $repo_tag"
        failures=$((failures + 1))
        continue
    fi

    if ! has_arm64 "$repo_tag"; then
        echo "   ERROR: no linux/arm64 entry in the manifest list of $repo_tag"
        echo "          this image is unusable for the ARM64 deploy (plan 9.2)."
        failures=$((failures + 1))
        continue
    fi
    echo "   linux/arm64: present"

    current=$(current_list_digest "$repo_tag")

    if [ -n "$locked" ]; then
        if ! has_arm64 "$repo_tag@$locked"; then
            echo "   ERROR: locked digest $locked is not resolvable (or lost arm64)"
            echo "          in the registry; re-verify and re-pin deliberately."
            failures=$((failures + 1))
            continue
        fi
        if [ -z "$current" ]; then
            echo "   OK: locked digest resolvable and arm64-capable"
            echo "       (buildx unavailable: tag drift not compared)"
        elif [ "$current" = "$locked" ]; then
            echo "   OK: tag still resolves to the locked digest"
        else
            echo "   ERROR: DIGEST MISMATCH for $name"
            echo "          locked : $locked"
            echo "          current: $current"
            echo "          The tag has moved in the registry. Investigate the new"
            echo "          release, then re-pin manually (edit images.lock.env)"
            echo "          and record the change in the project LOG."
            failures=$((failures + 1))
        fi
    else
        if [ -z "$current" ]; then
            echo "   ERROR: entry unpinned and digest could not be resolved."
            echo "          run: docker buildx imagetools inspect $repo_tag"
            failures=$((failures + 1))
        elif [ "$UPDATE" -eq 1 ]; then
            # GNU sed (Ubuntu VM). Digest chars are [a-f0-9:], safe with '|'.
            sed -i "s|^$name=.*|$name=$repo_tag@$current|" "$LOCK_FILE"
            echo "   PINNED: $name=$repo_tag@$current"
        else
            echo "   ERROR: entry is not pinned by digest."
            echo "          resolved digest: $current"
            echo "          re-run with --update to write it into images.lock.env"
            failures=$((failures + 1))
        fi
    fi
done < "$LOCK_FILE"

echo
if [ "$entries" -eq 0 ]; then
    echo "ERROR: no IMAGE_* entries found in $LOCK_FILE" >&2
    exit 1
fi
if [ "$failures" -gt 0 ]; then
    echo "FAILED: $failures of $entries image(s) did not verify. Do NOT deploy." >&2
    exit 1
fi
echo "OK: all $entries image(s) are arm64-capable and digest-verified."
