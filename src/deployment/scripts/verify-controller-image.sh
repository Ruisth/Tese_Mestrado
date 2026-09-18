#!/bin/sh
# verify-controller-image.sh — compare the controller image held by THIS
# Docker engine with the identity record written by
# scripts/build-controller-image.sh on the provisioning host. Runs ON THE
# GATEWAY after `docker load`; POSIX sh / BusyBox ash; changes nothing.
#
# Compared: image id (digest of the image configuration, which `docker load`
# preserves), architecture, OS and the revision label of the image
# (image_revision_label of the record: the source commit, with "-dirty"
# appended for a dirty build context). A loaded image has no RepoDigests, so
# the image id is its only verifiable identity.
# A record with source_tree_state=dirty is REFUSED unless --allow-dirty is
# given (development only): such an image is not for evidence.
# UNVERIFIED: an engine that uses the containerd image store reports a
# manifest digest as the image id and would not match; the gateway image uses
# the classic store (Docker 25.0.9).
#
# Usage:  sh scripts/verify-controller-image.sh [--allow-dirty] <identity-record>
# Exit:   0 identical and from a clean build context; 1 different, the image
#         is not loaded, or the record is from a dirty build context; 2 usage
#         or unreadable record (nothing was compared).

set -u

ALLOW_DIRTY=0
REC=""
for arg in "$@"; do
    case "$arg" in
        --allow-dirty) ALLOW_DIRTY=1 ;;
        *) REC=$arg ;;
    esac
done
[ -n "$REC" ] && [ -f "$REC" ] && [ -r "$REC" ] ||
    { echo "usage: $0 [--allow-dirty] <identity-record>   (egw-controller-<version>-arm64.identity.txt)" >&2; exit 2; }
command -v docker >/dev/null 2>&1 || { echo "ERROR: docker CLI not found in PATH" >&2; exit 2; }

# field KEY — first value of KEY in the record (key=value lines).
field() { sed -n "s/^$1=//p" "$REC" | head -n 1; }

REF=$(field image_ref)
WANT_ID=$(field image_id)
WANT_ARCH=$(field image_architecture)
WANT_OS=$(field image_os)
WANT_REV=$(field image_revision_label)
TREE_STATE=$(field source_tree_state)
case "$WANT_ID" in
    sha256:*) ;;
    *) echo "ERROR: $REC has no image_id=sha256:... line" >&2; exit 2 ;;
esac
[ -n "$REF" ] && [ -n "$WANT_ARCH" ] && [ -n "$WANT_OS" ] && [ -n "$WANT_REV" ] ||
    { echo "ERROR: $REC lacks image_ref, image_architecture, image_os or image_revision_label" >&2; exit 2; }
case "$TREE_STATE" in
    clean|dirty) ;;
    *) echo "ERROR: $REC has no source_tree_state=clean|dirty line" >&2; exit 2 ;;
esac

if ! HAVE_ID=$(docker image inspect --format '{{.Id}}' "$REF" 2>/dev/null) || [ -z "$HAVE_ID" ]; then
    echo "ERROR: image $REF is not present on this engine" >&2
    echo "       load the archive first: docker load -i $(field archive_file)" >&2
    exit 1
fi
HAVE_ARCH=$(docker image inspect --format '{{.Architecture}}' "$REF" 2>/dev/null)
HAVE_OS=$(docker image inspect --format '{{.Os}}' "$REF" 2>/dev/null)
HAVE_REV=$(docker image inspect \
    --format '{{index .Config.Labels "org.opencontainers.image.revision"}}' "$REF" 2>/dev/null)

failures=0
check() {
    if [ "$2" = "$3" ]; then
        echo "OK: $1 $3"
    else
        echo "ERROR: $1 differs: record $2, engine ${3:-none}" >&2
        failures=$((failures + 1))
    fi
}
check "image id" "$WANT_ID" "$HAVE_ID"
check "architecture" "$WANT_ARCH" "$HAVE_ARCH"
check "os" "$WANT_OS" "$HAVE_OS"
check "revision label" "$WANT_REV" "$HAVE_REV"
if [ "$TREE_STATE" = clean ]; then
    echo "OK: source commit $(field source_commit), clean build context"
elif [ "$ALLOW_DIRTY" -eq 1 ]; then
    echo "WARNING: the record is from a DIRTY build context (--allow-dirty): not for evidence" >&2
else
    echo "ERROR: the record is from a DIRTY build context (source_tree_state=dirty): not for evidence" >&2
    echo "       rebuild from a clean checkout, or pass --allow-dirty (development only)" >&2
    failures=$((failures + 1))
fi
echo "INFO: archive sha256 in the record: $(field archive_sha256); built $(field built_utc)"
echo "INFO: python dependencies: $(field python_dependencies)"

if [ "$failures" -gt 0 ]; then
    echo "CONTROLLER IMAGE IDENTITY: NOT verified ($REF)" >&2
    exit 1
fi
echo "CONTROLLER IMAGE IDENTITY: verified ($REF = $HAVE_ID)"
