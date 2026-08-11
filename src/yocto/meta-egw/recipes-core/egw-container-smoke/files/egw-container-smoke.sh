#!/bin/sh
# egw-container-smoke.sh — container runtime smoke test (gate-G1 evidence).
#
# Sequence:
#   1. 'docker info' must succeed (daemon running, storage driver usable).
#   2. Execute exactly one container:
#        - default (offline, deterministic): build a minimal single-layer OCI
#          image from the target's own BusyBox binary via 'docker import' and
#          run a command in it. Works without any network/registry access,
#          which is the normal situation inside qemuarm64 + slirp.
#        - online alternative (EGW_SMOKE_ONLINE=1): 'docker run --rm
#          hello-world'. Requires working DNS + registry access and the
#          ca-certificates trust store shipped in egw-image.
#   3. Append a timestamped PASS/FAIL line to /var/log/egw-smoke.log (the
#      same line is printed on stdout so it lands in the recorded QEMU
#      serial console — see src/yocto/scripts/run-qemu.sh).
#
# Exit status: 0 on PASS, 1 on FAIL. Strictly POSIX sh (runs under BusyBox
# ash). Environment overrides:
#   EGW_SMOKE_LOG     log file (default /var/log/egw-smoke.log)
#   EGW_SMOKE_ONLINE  set to 1 to use the hello-world online path

set -u

LOG_FILE="${EGW_SMOKE_LOG:-/var/log/egw-smoke.log}"
ONLINE="${EGW_SMOKE_ONLINE:-0}"
IMAGE_TAG="egw-smoke:local"

ts() {
    date -u +%Y-%m-%dT%H:%M:%SZ
}

log() {
    # $1 = PASS|FAIL|INFO, $2 = message. Mirrored to stdout and the log file.
    printf '%s %s %s\n' "$(ts)" "$1" "$2" | tee -a "$LOG_FILE"
}

fail() {
    log FAIL "$1"
    exit 1
}

mkdir -p "$(dirname "$LOG_FILE")" 2>/dev/null || true

log INFO "egw-container-smoke start (online=${ONLINE})"

# --- Step 1: docker daemon reachable and functional -------------------------
if ! docker info >/dev/null 2>&1; then
    fail "docker info failed (daemon not running or not ready yet; try 'systemctl status docker')"
fi
log INFO "docker info OK"

# --- Step 2 (online variant): docker run hello-world ------------------------
if [ "$ONLINE" = "1" ]; then
    if docker run --rm hello-world >/dev/null 2>&1; then
        log PASS "container executed (docker run --rm hello-world)"
        exit 0
    fi
    fail "docker run hello-world failed (no registry access? retry the default offline mode)"
fi

# --- Step 2 (default, offline): import + run a local BusyBox image ----------
# The target rootfs already contains a static-ish BusyBox for the same
# architecture, so a one-binary rootfs tarball is a valid OCI image source
# for 'docker import'. No network involved.
BUSYBOX_BIN=""
for candidate in /bin/busybox /bin/busybox.nosuid /usr/bin/busybox /usr/bin/busybox.nosuid; do
    if [ -x "$candidate" ]; then
        BUSYBOX_BIN="$candidate"
        break
    fi
done
[ -n "$BUSYBOX_BIN" ] || fail "no busybox binary found to build the offline smoke image"
log INFO "using $BUSYBOX_BIN for the offline smoke image"

WORK_DIR="$(mktemp -d /tmp/egw-smoke.XXXXXX)" || fail "mktemp failed"
trap 'rm -rf "$WORK_DIR"' EXIT INT TERM

mkdir -p "$WORK_DIR/rootfs/bin" || fail "mkdir rootfs failed"
cp "$BUSYBOX_BIN" "$WORK_DIR/rootfs/bin/busybox" || fail "copying busybox failed"
# 'echo' is a busybox-sh builtin, so /bin/sh alone is enough to run the test
# command; the applet links just make the image marginally more useful.
ln -s busybox "$WORK_DIR/rootfs/bin/sh" || fail "symlink sh failed"
ln -s busybox "$WORK_DIR/rootfs/bin/echo" 2>/dev/null || true

# The BusyBox shipped by poky is DYNAMICALLY linked. A rootfs holding only the
# binary makes the kernel fail the exec with ENOENT - reported as
# "exec /bin/sh: no such file or directory", which reads like a missing file
# but is really the missing dynamic loader. Observed on 2026-08-11.
#
# Ask the loader itself which objects the binary needs, so the list is derived
# rather than guessed, and copy each one preserving its path. A statically
# linked BusyBox makes '--list' fail, which is harmless: nothing to copy.
LOADER=""
for candidate in /lib/ld-linux-aarch64.so.1 /lib64/ld-linux-aarch64.so.1 /lib/ld-linux-armhf.so.3; do
    [ -x "$candidate" ] && { LOADER="$candidate"; break; }
done
if [ -n "$LOADER" ] && "$LOADER" --list "$BUSYBOX_BIN" >/dev/null 2>&1; then
    DEPS="$("$LOADER" --list "$BUSYBOX_BIN" 2>/dev/null \
        | tr ' ' '\n' | grep '^/' | sort -u)"
    for lib in $DEPS $LOADER; do
        [ -e "$lib" ] || continue
        mkdir -p "$WORK_DIR/rootfs$(dirname "$lib")" || fail "mkdir for $lib failed"
        cp "$lib" "$WORK_DIR/rootfs$lib" || fail "copying $lib failed"
    done
    log INFO "bundled the dynamic loader and $(echo "$DEPS" | wc -l) shared object(s)"
else
    log INFO "busybox appears statically linked; no shared objects bundled"
fi

( cd "$WORK_DIR/rootfs" && tar -cf "$WORK_DIR/rootfs.tar" . ) \
    || fail "creating rootfs tarball failed"

docker rmi -f "$IMAGE_TAG" >/dev/null 2>&1 || true
docker import "$WORK_DIR/rootfs.tar" "$IMAGE_TAG" >/dev/null 2>&1 \
    || fail "docker import of local rootfs tarball failed"

OUTPUT="$(docker run --rm "$IMAGE_TAG" /bin/sh -c 'echo egw-smoke-ok' 2>&1)"
if [ "$OUTPUT" = "egw-smoke-ok" ]; then
    log PASS "container executed (docker import + run of local busybox image)"
    exit 0
fi
fail "container run failed or produced unexpected output: $OUTPUT"
