#!/bin/sh
# build.sh — kas checkout + build of egw-image for qemuarm64 (gate G1).
#
# Intended environment: WSL2 Ubuntu 24.04, running from a clone of this
# repository that lives on the Linux ext4 filesystem (NEVER /mnt/c, /mnt/d or
# any Nextcloud-synced path — plan section 5.1). Full environment setup:
# docs/setup/wsl2_ubuntu_yocto.md.
#
# Evidence capture (gate G1, plan section 8): every invocation writes the
# complete kas/BitBake output to a timestamped log under $EGW_LOG_DIR
# (default ~/yocto/logs). Unlogged runs do not count as evidence — copy the
# logs into the experiments evidence area and reference them from the
# claim->evidence matrix after a successful build.
#
# Usage:
#   ./scripts/build.sh              # checkout pinned layers, then build
#   EGW_LOG_DIR=/some/dir ./scripts/build.sh
#
# Strictly POSIX sh.

set -eu

SCRIPT_DIR=$(CDPATH='' cd -- "$(dirname -- "$0")" && pwd)
YOCTO_DIR=$(dirname -- "$SCRIPT_DIR")
KAS_FILE="kas/egw-qemuarm64.yml"
LOG_DIR="${EGW_LOG_DIR:-$HOME/yocto/logs}"

cd "$YOCTO_DIR"

# The url-less 'meta-egw' repo in the kas manifest resolves relative to the
# kas work dir; pin it explicitly so the manifest works regardless of the
# caller's cwd. Remote layers (poky, meta-openembedded, meta-virtualization)
# are cloned here as well — they are ignored by src/yocto/.gitignore.
KAS_WORK_DIR="$YOCTO_DIR"
export KAS_WORK_DIR

# Download and sstate caches. These MUST come from an explicit variable:
# kas replaces HOME with a temporary directory before invoking BitBake, so
# "${HOME}" inside local.conf would point at a directory that is deleted at
# the end of the run (caches silently lost, and a re-run then fails at
# do_unpack). $HOME below is expanded by THIS shell, where it is the real
# home directory. See the 'env:' block in kas/egw-qemuarm64.yml.
: "${EGW_CACHE_DIR:=$HOME/yocto-cache}"
export EGW_CACHE_DIR
mkdir -p "$EGW_CACHE_DIR/downloads" "$EGW_CACHE_DIR/sstate-cache"
echo "Caches : $EGW_CACHE_DIR (downloads + sstate-cache)"

# Refuse to build on Windows-backed filesystems: 9p/drvfs (WSL /mnt/*) and
# NTFS breach both performance and correctness assumptions of BitBake
# (pseudo, hardlinks, case sensitivity). Plan 5.1 requires ext4.
FS_TYPE=$(stat -f -c %T . 2>/dev/null || echo unknown)
case "$FS_TYPE" in
    v9fs|9p|drvfs|msdos|ntfs*|fuseblk)
        echo "ERROR: $YOCTO_DIR sits on '$FS_TYPE' (a Windows-backed mount)." >&2
        echo "Clone the repository onto the WSL2 ext4 filesystem first, e.g.:" >&2
        echo "  git clone <repository-url-or-local-path> ~/yocto/egw" >&2
        echo "and run ~/yocto/egw/src/yocto/scripts/build.sh instead." >&2
        echo "(See docs/setup/wsl2_ubuntu_yocto.md.)" >&2
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

# run_logged LOGFILE CMD [ARGS...]
# Tees stdout+stderr to LOGFILE while PRESERVING the command's exit status
# (a plain 'cmd | tee' would report tee's status; 'pipefail' is not POSIX).
run_logged() {
    _log="$1"
    shift
    # 'set -e' must be OFF around the group: with errexit active the shell
    # aborts at the failing command and never reaches 'echo $?', so the status
    # file is missing precisely when the command FAILED - the one case this
    # function exists for. (Observed 2026-08-11: a failed 'kas build' produced
    # "cat: ...log.status: No such file or directory" and lost the exit code.)
    set +e
    { "$@" 2>&1; echo $? >"$_log.status"; } | tee "$_log"
    set -e
    _rc=$(cat "$_log.status" 2>/dev/null || echo 1)
    rm -f "$_log.status"
    return "$_rc"
}

echo "== kas checkout (pinned revisions from $KAS_FILE + lock file) =="
# kas automatically merges kas/egw-qemuarm64.lock.yml, so the exact commits
# recorded there win over any floating branch refs.
run_logged "$LOG_DIR/kas-checkout-$STAMP.log" kas checkout "$KAS_FILE"

echo "== kas build (target: egw-image, machine: qemuarm64) =="
# The first build compiles the cross toolchain and every package from
# source; how long it takes depends entirely on the host CPU/RAM/disk.
# Later builds reuse DL_DIR/SSTATE_DIR (see local_conf_header) and are far
# faster. Record the real measured duration from this log as evidence —
# never quote an expected number that was not measured.
run_logged "$LOG_DIR/kas-build-$STAMP.log" kas build "$KAS_FILE"

echo "== build finished =="
echo "Logs   : $LOG_DIR/kas-checkout-$STAMP.log"
echo "         $LOG_DIR/kas-build-$STAMP.log"
echo "Images : $YOCTO_DIR/build/tmp/deploy/images/qemuarm64/"
echo "Next   : scripts/run-qemu.sh boot1   (then boot2 — G1 needs two boots)"
