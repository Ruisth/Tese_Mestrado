#!/usr/bin/env bash
# run-qemu-integrated.sh — boot the INTEGRATED test-gateway image
# (egw-gateway-image, kas/egw-qemuarm64-integrated.yml, build-integrated/)
# under QEMU/TCG with a persistent data disk attached and the serial console
# recorded to a log file. Companion of scripts/run-qemu.sh, which stays
# reserved for the gate-G1 image and is not modified.
#
# THIS IS ARM64 EMULATED ON AN x86-64 HOST (QEMU/TCG, no KVM). Results are
# functional and integration evidence for the six-container stack running
# inside the Yocto guest; they are never native ARM64 performance figures.
#
# What the boot uses (all recorded in <image>.qemuboot.conf at build time
# and printed by runqemu into the log): -machine virt, -cpu cortex-a76
# (ARMv8.2-A, required by MongoDB 7), -smp 4, -m 8192 with the matching
# kernel mem=8192M, slirp with hostfwd 2222->22 (SSH) and 8883->8883
# (MQTT/TLS). This wrapper adds the data disk:
#   -drive id=disk1,file=$EGW_DATA_DISK,if=none,format=raw -device virtio-blk-pci,drive=disk1
# The guest mounts it on /var/lib/docker by label 'egw-data' (fstab entry
# from egw-gateway-image.bb; docker.service waits for it).
#
# Environment (all optional):
#   EGW_DATA_DISK       ABSOLUTE path of the data-disk file, OUTSIDE the
#                       repository. Default: $HOME/yocto/egw-integrated/egw-data.img.
#                       A relative path is refused: QEMU opens 'file=' from
#                       the directory 'kas shell' starts in (the build
#                       directory), not from src/yocto.
#                       The path is canonicalised before anything is created
#                       ('..' and symlinked directories resolved); it is
#                       refused when the result lies inside the clone, when
#                       the file name itself is a symlink, when an existing
#                       file has more than one hard link, or when the path
#                       holds anything but ASCII letters, digits and
#                       '_' '.' '/' '+' '@' '-' (so no white space, quotes,
#                       commas or shell metacharacters). QEMU receives the
#                       canonical path.
#                       Created sparse and formatted ext4 (label egw-data)
#                       when missing. Delete or rename the file for a
#                       destructive reset of every image, volume and
#                       container log (never delete evidence).
#   EGW_DATA_DISK_SIZE  size for a NEW disk file (truncate syntax), default
#                       32G. Grow an existing file with 'truncate -s 64G',
#                       the guest resizes the file system at the next boot.
#   EGW_IMAGE           egw-gateway-image (default) or egw-gateway-image-dev.
#   EGW_QEMU_EXTRA      extra QEMU arguments appended to qemuparams, e.g.
#                       "-m 6144" (runqemu then also sets mem=6144M).
#   EGW_LOG_DIR         console-log directory, default ~/yocto/logs.
# Usage:
#   ./scripts/run-qemu-integrated.sh <run-name>      # e.g. integrated-smoke-01
# Exit QEMU with: Ctrl+A, then x.
#
# Bash is intentional: pipefail is required so a failed 'kas shell' can never
# be hidden by a successful tee process.

set -euo pipefail

SCRIPT_DIR=$(CDPATH='' cd -- "$(dirname -- "$0")" && pwd)
YOCTO_DIR=$(dirname -- "$SCRIPT_DIR")
KAS_FILE="kas/egw-qemuarm64-integrated.yml"
BUILD_SUBDIR="build-integrated"
LOG_DIR="${EGW_LOG_DIR:-$HOME/yocto/logs}"
IMAGE="${EGW_IMAGE:-egw-gateway-image}"
MACHINE="qemuarm64"
DISK="${EGW_DATA_DISK:-$HOME/yocto/egw-integrated/egw-data.img}"
DISK_SIZE="${EGW_DATA_DISK_SIZE:-32G}"
DISK_LABEL="egw-data"

RUN_NAME="${1:-integrated-$(date -u +%Y%m%dT%H%M%SZ)}"
LOG_FILE="$LOG_DIR/$RUN_NAME.log"

die() { echo "ERROR: $*" >&2; exit 1; }

case "$IMAGE" in
    egw-gateway-image|egw-gateway-image-dev) ;;
    *) die "EGW_IMAGE must be egw-gateway-image or egw-gateway-image-dev (got '$IMAGE')." ;;
esac

disk_path_is_plain() {
    # $DISK travels inside qemuparams="-drive ...,file=$DISK,..." through
    # 'kas shell -c' and runqemu: white space and quotes split the argument,
    # '$', '`' and '\' are expanded by that shell, and ',' ends the value
    # of QEMU's file= option. A whitelist instead of a list of known-bad
    # characters: nothing the shell, runqemu or QEMU could interpret gets
    # through, whatever their internals do. LC_ALL=C keeps the ranges ASCII.
    local LC_ALL=C
    case "$1" in
        *[!A-Za-z0-9_./+@-]*) return 1 ;;
    esac
    return 0
}

resolve_data_disk() {
    # Replaces $DISK by its canonical path and refuses it unless it is
    # provably outside the clone. Creates and changes nothing, so it runs
    # before any mkdir/truncate/mkfs.
    #
    # Absolute path only: QEMU resolves 'file=' from the working directory
    # of 'kas shell' (KAS_BUILD_DIR), so a relative path would be created
    # here (src/yocto) and opened elsewhere.
    case "$DISK" in
        /*) ;;
        *) die "EGW_DATA_DISK must be an absolute path (got '$DISK')." ;;
    esac
    disk_path_is_plain "$DISK" \
        || die "EGW_DATA_DISK path may contain only ASCII letters, digits and _ . / + @ - (it is passed through runqemu qemuparams); got '$DISK'."
    local base parent
    base=$(basename -- "$DISK")
    case "$DISK" in */) base="" ;; esac
    case "$base" in
        ""|.|..|/) die "EGW_DATA_DISK must name a file, not a directory (got '$DISK')." ;;
    esac
    # A textual comparison is not enough: '..' components and symlinked
    # directories can lead back into the clone. Canonicalise the parent
    # directory (realpath -m: the directory may not exist yet; symlinks in
    # the components that do exist are resolved, '..' is applied after
    # them) and re-append the file name. The file name itself must not be a
    # symlink, otherwise truncate/mkfs/QEMU would follow it anywhere.
    parent=$(realpath -m -- "$(dirname -- "$DISK")") \
        || die "cannot resolve the directory of EGW_DATA_DISK='$DISK'."
    local requested="$DISK"
    DISK="${parent%/}/$base"
    [[ ! -L "$DISK" ]] || die "EGW_DATA_DISK='$DISK' is a symbolic link; name the real file."
    [[ ! -e "$DISK" || -f "$DISK" ]] || die "EGW_DATA_DISK='$DISK' exists and is not a regular file."
    # A second hard link could live inside the clone; the directory checks
    # below cannot see that, so an existing file must have exactly one name.
    if [[ -f "$DISK" ]]; then
        local links
        links=$(stat -c %h -- "$DISK") || die "cannot stat EGW_DATA_DISK='$DISK'."
        [[ "$links" == 1 ]] || die "EGW_DATA_DISK='$DISK' has $links hard links; use a file with a single name."
    fi
    # The canonical path goes to QEMU, so it has to be plain as well (a
    # symlink target may contain what the requested path did not).
    disk_path_is_plain "$DISK" \
        || die "EGW_DATA_DISK='$requested' resolves to '$DISK', which contains characters other than ASCII letters, digits and _ . / + @ -."
    # The disk file must live outside the repository checkout: it is
    # runtime state, not a build artefact, and must survive 'git clean'.
    # Compare against the top of the clone (src/yocto is two levels below
    # it), not only against src/yocto, so <clone>/docs/x.img is refused too.
    # Both sides are canonical (YOCTO_DIR comes from a logical 'pwd').
    local repo_top yocto_real
    repo_top=$(git -C "$YOCTO_DIR" rev-parse --show-toplevel 2>/dev/null) \
        || repo_top=$(CDPATH='' cd -- "$YOCTO_DIR/../.." && pwd)
    repo_top=$(realpath -e -- "$repo_top") || die "cannot resolve the top of the clone ($repo_top)."
    yocto_real=$(realpath -e -- "$YOCTO_DIR") || die "cannot resolve $YOCTO_DIR."
    case "$DISK" in
        "${repo_top%/}"/*|"${yocto_real%/}"/*) die "EGW_DATA_DISK='$requested' resolves to '$DISK', inside the repository ($repo_top); keep it outside (default $HOME/yocto/egw-integrated/egw-data.img)." ;;
    esac
    # Same test by device and inode on every existing ancestor directory:
    # covers what a string comparison cannot see (bind mounts, a
    # case-insensitive file system).
    local dir="$parent"
    while :; do
        if [[ -d "$dir" ]] && [[ "$dir" -ef "$repo_top" || "$dir" -ef "$yocto_real" ]]; then
            die "EGW_DATA_DISK='$requested': its directory '$dir' is the repository ($repo_top) under another name; keep the disk outside."
        fi
        [[ "$dir" != / ]] || break
        dir=$(dirname -- "$dir")
    done
    if [[ "$DISK" != "$requested" ]]; then
        echo "== EGW_DATA_DISK '$requested' resolved to '$DISK' ==" >&2
    fi
}

prepare_data_disk() {
    # From here on $DISK is canonical and outside the clone; the same value
    # is what main() hands to QEMU.
    resolve_data_disk
    if [[ ! -e "$DISK" ]]; then
        command -v mkfs.ext4 >/dev/null 2>&1 || die "mkfs.ext4 not found (apt install e2fsprogs)."
        mkdir -p "$(dirname -- "$DISK")"
        echo "== creating data disk $DISK ($DISK_SIZE, sparse) and formatting it ext4 (label $DISK_LABEL) =="
        truncate -s "$DISK_SIZE" "$DISK"
        mkfs.ext4 -q -F -L "$DISK_LABEL" "$DISK"
    fi
    if command -v blkid >/dev/null 2>&1; then
        local label
        label=$(blkid -o value -s LABEL "$DISK" 2>/dev/null || true)
        if [[ "$label" != "$DISK_LABEL" ]]; then
            die "$DISK carries label '${label:-<none>}', expected '$DISK_LABEL' (not an EGW data disk, or unreadable)."
        fi
    fi
}

check_ports() {
    # runqemu re-maps a busy host port and only logs 'Port forward changed:
    # 2222 -> 2223'. Warn beforehand so the operator reads the mapping.
    local p
    for p in 2222 8883; do
        if command -v ss >/dev/null 2>&1 && ss -ltn 2>/dev/null | grep -q ":$p "; then
            echo "WARNING: host port $p is in use; runqemu will forward to another port — read 'Port forward' in the log." >&2
        fi
    done
}

main() {
    cd "$YOCTO_DIR"
    KAS_WORK_DIR="$YOCTO_DIR"
    KAS_BUILD_DIR="$YOCTO_DIR/$BUILD_SUBDIR"
    export KAS_WORK_DIR KAS_BUILD_DIR
    : "${EGW_CACHE_DIR:=$HOME/yocto-cache}"
    export EGW_CACHE_DIR

    command -v kas >/dev/null 2>&1 || die "'kas' not found (see docs/setup/wsl2_ubuntu_yocto.md)."

    local deploy="$KAS_BUILD_DIR/tmp/deploy/images/$MACHINE"
    local qbconf="$deploy/$IMAGE-$MACHINE.rootfs.qemuboot.conf"
    [[ -f "$qbconf" ]] || die "no deployed $IMAGE found ($qbconf) — run ./scripts/build-profile.sh integrated first."

    prepare_data_disk
    check_ports
    mkdir -p "$LOG_DIR"

    local qemu_extra="-drive id=disk1,file=$DISK,if=none,format=raw -device virtio-blk-pci,drive=disk1${EGW_QEMU_EXTRA:+ $EGW_QEMU_EXTRA}"
    # runqemu: <image> <machine> nographic slirp qemuparams="..."; the image
    # name selects $IMAGE-$MACHINE.rootfs.ext4 and its qemuboot.conf in the
    # deploy directory of THIS build directory (KAS_BUILD_DIR).
    local cmd="runqemu $IMAGE $MACHINE nographic slirp qemuparams=\"$qemu_extra\""

    {
        echo "== run-qemu-integrated: $RUN_NAME"
        echo "== date (UTC)   : $(date -u +%Y-%m-%dT%H:%M:%SZ)"
        echo "== host         : $(uname -srm) (WSL2, x86-64; guest is ARM64 EMULATED under QEMU/TCG)"
        echo "== host memory  : $(free -g 2>/dev/null | awk '/^Mem:/ {print $2 " GiB total, " $7 " GiB available"}')"
        echo "== build dir    : $KAS_BUILD_DIR"
        echo "== image        : $IMAGE -> $(readlink -f "$deploy/$IMAGE-$MACHINE.rootfs.ext4")"
        echo "== qemuboot     : $qbconf"
        grep -E '^(qb_cpu|qb_smp|qb_mem|qb_machine|qb_slirp_opt|qb_opt_append|qb_system_name) ' "$qbconf" | sed 's/^/==   /' || true
        echo "== data disk    : $DISK ($(stat -c %s "$DISK") bytes apparent, $(du -h --apparent-size "$DISK" | cut -f1) / $(du -h "$DISK" | cut -f1) on disk)"
        echo "== runqemu cmd  : $cmd"
        echo "== exit with Ctrl+A then x; keep this log as run evidence =="
    } | tee "$LOG_FILE"

    # Interactive stdin stays attached to the terminal; stdout/stderr are
    # teed so the full session (runqemu's own 'Running ...' command line,
    # kernel, systemd, the operator's commands) lands in the evidence log.
    kas shell "$KAS_FILE" -c "$cmd" 2>&1 | tee -a "$LOG_FILE"

    echo "== QEMU session ended; console log: $LOG_FILE =="
}

if [[ "${BASH_SOURCE[0]}" == "$0" ]]; then
    main
fi
