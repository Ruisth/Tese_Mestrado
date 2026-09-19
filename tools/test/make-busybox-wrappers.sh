#!/bin/sh
# make-busybox-wrappers.sh — run the collector's tests under the gateway
# image's own busybox (ash, awk and applets) on an x86-64 build host.
#
# Creates a directory of one-line wrappers, each of which runs one busybox
# applet of the built image under the Yocto build's qemu-aarch64 user-mode
# emulator. With EGW_TEST_BUSYBOX_DIR pointing at that directory, the cases of
# src/tests/test_collect_resources.py also run under that exact busybox, with
# PATH holding nothing else, so no host shell or awk can stand in for it. Four
# cases stay host-shell only: they put a fake awk or docker ahead of the real
# one on PATH, or run two collectors side by side.
#
# What it reproduces: the guest's shell and awk (the same binary). What it does
# not: the guest kernel — /proc and the synthetic cgroup trees are the host's.
#
# Usage:
#   sh tools/test/make-busybox-wrappers.sh <image-rootfs-dir> <qemu-aarch64> [<out-dir>]
#   EGW_TEST_BUSYBOX_DIR=<out-dir> python -m pytest src/tests/test_collect_resources.py
#
# For the integrated profile built under src/yocto/build-integrated/:
#   rootfs:      tmp/work/qemuarm64-poky-linux/egw-gateway-image/1.0/rootfs
#   qemu-aarch64: tmp/sysroots-components/x86_64/qemu-native/usr/bin/qemu-aarch64

set -eu

[ $# -ge 2 ] || {
    echo "usage: $0 <image-rootfs-dir> <qemu-aarch64> [<out-dir>]" >&2
    exit 2
}
ROOTFS=$1
QEMU=$2
OUT=${3:-/tmp/egw-bb}
BUSYBOX=$ROOTFS/usr/bin/busybox.nosuid

[ -x "$QEMU" ] || { echo "error: no executable qemu-aarch64 at $QEMU" >&2; exit 1; }
[ -f "$BUSYBOX" ] || { echo "error: no busybox at $BUSYBOX" >&2; exit 1; }

mkdir -p "$OUT"
for applet in sh awk date grep sed head mv rm rmdir mkdir hostname uname sha256sum cat sleep wc cut env; do
    printf '#!/bin/sh\nexec "%s" -L "%s" "%s" %s "$@"\n' "$QEMU" "$ROOTFS" "$BUSYBOX" "$applet" > "$OUT/$applet"
    chmod 0755 "$OUT/$applet"
done

echo "busybox sha256: $(sha256sum "$BUSYBOX" | cut -d' ' -f1)"
env -i PATH="$OUT" "$OUT/sh" -c 'echo "check: EPOCHREALTIME=[${EPOCHREALTIME:-}] awk systime=$(awk "BEGIN { print systime() }") date=$(date +%s)"'
echo "EGW_TEST_BUSYBOX_DIR=$OUT"
