#!/bin/sh
# build-profile.sh — kas checkout + build of a NON-G1 kas profile in its OWN
# build directory. Companion of scripts/build.sh, which stays reserved for
# the gate-G1 target (kas/egw-qemuarm64.yml, build/) and is not modified.
#
# Profiles (PM work order 2026-09-17, fixed names):
#   integrated    kas/egw-qemuarm64-integrated.yml  -> build-integrated/
#                 (Yocto ARM64 guest + full container stack under QEMU/TCG
#                 on the x86-64 WSL2 host; ARM64 EMULATED, never native)
#   genericarm64  kas/egw-genericarm64.yml          -> build-genericarm64/
#                 (native ARM64 route, second deliverable)
# The build directory is selected with KAS_BUILD_DIR, which kas 5.4 reads in
# kas/context.py line 85 (default <KAS_WORK_DIR>/build). It is exported
# here so the G1 build/ is never written by these profiles. Downloads and
# sstate (EGW_CACHE_DIR, default ~/yocto-cache) are SHARED with G1: nothing
# whose task hash is unchanged is rebuilt.
#
# Intended environment: WSL2 Ubuntu 24.04, running from a clone of this
# repository on the Linux ext4 filesystem (never /mnt/c; see
# docs/setup/wsl2_ubuntu_yocto.md).
#
# Evidence capture: every invocation writes the complete kas/BitBake output
# to a timestamped log under $EGW_LOG_DIR (default ~/yocto/logs). Unlogged
# runs do not count as evidence.
#
# Usage:
#   EGW_AUTHORIZED_KEYS_FILE=$HOME/.ssh/egw_campaign.pub ./scripts/build-profile.sh integrated
#   ./scripts/build-profile.sh integrated --target egw-gateway-image-dev
#   ./scripts/build-profile.sh genericarm64
# Extra arguments after the profile name are passed to 'kas build'.
#
# Strictly POSIX sh.

set -eu

SCRIPT_DIR=$(CDPATH='' cd -- "$(dirname -- "$0")" && pwd)
YOCTO_DIR=$(dirname -- "$SCRIPT_DIR")
LOG_DIR="${EGW_LOG_DIR:-$HOME/yocto/logs}"

PROFILE="${1:-}"
if [ -z "$PROFILE" ]; then
    echo "Usage: $0 <integrated|genericarm64> [extra 'kas build' arguments]" >&2
    exit 2
fi
shift

case "$PROFILE" in
    integrated)
        KAS_FILE="kas/egw-qemuarm64-integrated.yml"
        BUILD_SUBDIR="build-integrated"
        ;;
    genericarm64)
        KAS_FILE="kas/egw-genericarm64.yml"
        BUILD_SUBDIR="build-genericarm64"
        ;;
    *)
        echo "ERROR: unknown profile '$PROFILE' (expected integrated or genericarm64)." >&2
        exit 2
        ;;
esac

cd "$YOCTO_DIR"

if [ ! -f "$KAS_FILE" ]; then
    echo "ERROR: $YOCTO_DIR/$KAS_FILE does not exist." >&2
    exit 1
fi

# The url-less 'meta-egw' repo in the kas manifest resolves relative to the
# kas work dir; pin it explicitly so the manifest works regardless of the
# caller's cwd. Remote layers are cloned here as well (git-ignored).
KAS_WORK_DIR="$YOCTO_DIR"
export KAS_WORK_DIR

# Separate build directory — the whole point of this wrapper. Refuse to
# proceed if it would collide with the G1 build directory.
KAS_BUILD_DIR="$YOCTO_DIR/$BUILD_SUBDIR"
export KAS_BUILD_DIR
if [ "$KAS_BUILD_DIR" = "$YOCTO_DIR/build" ]; then
    echo "ERROR: KAS_BUILD_DIR must not be the G1 build directory ($YOCTO_DIR/build)." >&2
    exit 1
fi

# Download and sstate caches: same directory as G1 (see scripts/build.sh and
# the 'env:' block of the kas manifests for why this must be an explicit
# variable and never ${HOME} inside local.conf).
: "${EGW_CACHE_DIR:=$HOME/yocto-cache}"
export EGW_CACHE_DIR
mkdir -p "$EGW_CACHE_DIR/downloads" "$EGW_CACHE_DIR/sstate-cache"

# Operator SSH public key (build-time input of egw-gateway-image.bb). The
# campaign image fails its build without it; the -dev image only warns.
if [ -z "${EGW_AUTHORIZED_KEYS_FILE:-}" ]; then
    echo "WARNING: EGW_AUTHORIZED_KEYS_FILE is unset. egw-gateway-image will FAIL its build;" >&2
    echo "         only egw-gateway-image-dev (console access) builds without a key." >&2
    echo "         Example: ssh-keygen -t ed25519 -f ~/.ssh/egw_campaign -C egw-campaign &&" >&2
    echo "                  export EGW_AUTHORIZED_KEYS_FILE=\$HOME/.ssh/egw_campaign.pub" >&2
else
    export EGW_AUTHORIZED_KEYS_FILE
    if [ ! -r "$EGW_AUTHORIZED_KEYS_FILE" ]; then
        echo "ERROR: EGW_AUTHORIZED_KEYS_FILE='$EGW_AUTHORIZED_KEYS_FILE' is not readable." >&2
        exit 1
    fi
    if grep -q "PRIVATE KEY" "$EGW_AUTHORIZED_KEYS_FILE"; then
        echo "ERROR: EGW_AUTHORIZED_KEYS_FILE points at a PRIVATE key; pass the .pub file." >&2
        exit 1
    fi
fi

# Refuse to build on Windows-backed filesystems (same rule as build.sh).
FS_TYPE=$(stat -f -c %T . 2>/dev/null || echo unknown)
case "$FS_TYPE" in
    v9fs|9p|drvfs|msdos|ntfs*|fuseblk)
        echo "ERROR: $YOCTO_DIR sits on '$FS_TYPE' (a Windows-backed mount)." >&2
        echo "Clone the repository onto the WSL2 ext4 filesystem first (docs/setup/wsl2_ubuntu_yocto.md)." >&2
        exit 1
        ;;
esac

command -v kas >/dev/null 2>&1 || {
    echo "ERROR: 'kas' not found. Install it first (pipx install kas)," >&2
    echo "see docs/setup/wsl2_ubuntu_yocto.md section 5." >&2
    exit 1
}

mkdir -p "$LOG_DIR"
STAMP=$(date -u +%Y%m%dT%H%M%SZ)

# run_logged LOGFILE CMD [ARGS...] — tee while preserving the exit status
# (same construction as scripts/build.sh; see the comment there).
run_logged() {
    _log="$1"
    shift
    set +e
    { "$@" 2>&1; echo $? >"$_log.status"; } | tee "$_log"
    set -e
    _rc=$(cat "$_log.status" 2>/dev/null || echo 1)
    rm -f "$_log.status"
    return "$_rc"
}

echo "Profile   : $PROFILE ($KAS_FILE)"
echo "Build dir : $KAS_BUILD_DIR (KAS_BUILD_DIR)"
echo "Caches    : $EGW_CACHE_DIR (downloads + sstate-cache, shared with G1)"
echo "SSH key   : ${EGW_AUTHORIZED_KEYS_FILE:-<none>}"

echo "== kas checkout (pinned revisions from $KAS_FILE + lock file) =="
run_logged "$LOG_DIR/kas-checkout-$PROFILE-$STAMP.log" kas checkout "$KAS_FILE"

echo "== kas build ($KAS_FILE${1:+ $*}) =="
# The first build of a profile compiles what the shared sstate cannot
# provide (for 'integrated': docker-compose, sudo, the new config recipe
# and the image; curl, openssh and e2fsprogs were already built by G1 and
# are restored like everything else). Record the real
# measured duration from the log — never quote an expected number.
run_logged "$LOG_DIR/kas-build-$PROFILE-$STAMP.log" kas build "$KAS_FILE" "$@"

echo "== build finished =="
# Build acceptance (kas/egw-qemuarm64-integrated.yml block 22): BitBake's
# closing 'Sstate summary: Wanted N Local N ... Missed N Current N' line
# records how much of the shared G1 sstate was reused. Copy it into the
# build evidence together with the log; a 'Missed' count in the hundreds
# means a global variable reached the G1 recipes' signatures.
echo "== Sstate summary (record with the build evidence) =="
grep -h "Sstate summary" "$LOG_DIR/kas-build-$PROFILE-$STAMP.log" || echo "(no 'Sstate summary' line in the log)"
# Second acceptance check of block 22 (integrated profile only): the kernel
# Image of build-integrated/ is predicted to be byte-identical to the G1
# one, because no variable of the profile reaches the kernel signature and
# do_deploy is restored from the shared sstate. Both files are only READ.
if [ "$PROFILE" = "integrated" ]; then
    G1_IMAGE="$YOCTO_DIR/build/tmp/deploy/images/qemuarm64/Image"
    NEW_IMAGE="$KAS_BUILD_DIR/tmp/deploy/images/qemuarm64/Image"
    if [ -f "$G1_IMAGE" ] && [ -f "$NEW_IMAGE" ]; then
        echo "== kernel Image sha256, G1 build/ vs build-integrated/ (predicted equal) =="
        sha256sum "$G1_IMAGE" "$NEW_IMAGE"
    else
        echo "== kernel Image comparison skipped (G1 or new Image not found) =="
    fi
fi
echo "Logs   : $LOG_DIR/kas-checkout-$PROFILE-$STAMP.log"
echo "         $LOG_DIR/kas-build-$PROFILE-$STAMP.log"
echo "Images : $KAS_BUILD_DIR/tmp/deploy/images/"
if [ "$PROFILE" = "integrated" ]; then
    echo "Next   : ./scripts/run-qemu-integrated.sh <run-name>   (boots egw-gateway-image; EGW_IMAGE=egw-gateway-image-dev for the bring-up variant)"
fi
