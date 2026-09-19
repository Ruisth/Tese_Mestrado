#!/bin/bash
# Open a guest session as its own attempt: record the identities of what is
# about to run, boot the integrated guest with the existing session scripts,
# record the guest's state, and leave it up. guest_session_close.sh stops the
# stack, powers the guest off and exports the session.
set -u
. "$(dirname "$0")/common.sh"
. "$(dirname "$0")/guest_common.sh"
if [ -n "$SESSION" ] && [ -d "$SESSION" ]; then
    echo "STOP: a session is already open: $SESSION" >&2
    exit 1
fi
if pgrep -f qemu-system-aarch64 > /dev/null; then
    echo "STOP: a qemu-system-aarch64 process is already running" >&2
    exit 1
fi
S=$(new_attempt "guest session" engineering) || exit 1
SESSION=$S
echo "$S" > "$EXEC/current_session"
RUN=s1
mkdir -p "$S/scripts" "$S/boot" "$S/guest" "$S/host"
cp "$DRIVERS/guest/"{session_common.sh,session_open.sh,boot_driver.sh,session_close.sh,session_run.sh,gssh.sh} "$S/scripts/"
mkdir -p "$S/scripts/drivers" && cp "$DRIVERS/"*.sh "$S/scripts/drivers/"
(cd "$REPO/src" && $LE set --attempt "$S" "identities=$(repo_identity)" \
    'workload={"kind": "guest session: boot, stack start, the attempts that reference this session, controlled stop and power-off"}')

# Identities, read before the boot (the rootfs ext4 is booted in place and
# changes; the immutable identity of the built rootfs is its tar.bz2).
ex "$S" identities-before-boot bash -c '
set -u
echo "## host"; uname -a; cat /proc/version; nproc; free -m; df -h / /mnt/c
echo "## ports (2222 8883 8000 8080 must be free)"; ss -ltn | grep -E ":(2222|8883|8000|8080) " || echo "none listening"
echo "## OS build artefacts ('"$DEP"')"
cd "'"$DEP"'" && sha256sum Image-qemuarm64.bin egw-gateway-image-qemuarm64.rootfs-20260918120819.tar.bz2 \
  egw-gateway-image-qemuarm64.rootfs-20260918120819.ext4 egw-gateway-image-qemuarm64.rootfs-20260918120819.qemuboot.conf \
  egw-gateway-image-qemuarm64.rootfs-20260918120819.manifest
echo "## data disk"; ls -l "'"$DATA_DISK"'"; /usr/sbin/dumpe2fs -h "'"$DATA_DISK"'" 2>/dev/null | grep -E "state|features|mount count|Last mount"
echo "## rootfs ext4 state"; /usr/sbin/dumpe2fs -h "'"$ROOTFS_EXT4"'" 2>/dev/null | grep -E "state|features|mount count|Last mount"
echo "## QEMU"; Q="'"$BUILD"'/tmp/work/x86_64-linux/qemu-helper-native/1.0/recipe-sysroot-native/usr/bin/qemu-system-aarch64"; sha256sum "$Q"; "$Q" --version | head -n 1
echo "## OS build source (Yocto checkout, launcher and kas)"; git -C "'"$OLD"'" rev-parse HEAD; git -C "'"$OLD"'" status --porcelain | wc -l
cd "'"$OLD"'/src/yocto" && sha256sum scripts/run-qemu-integrated.sh kas/egw-qemuarm64-integrated.yml kas/egw-qemuarm64-integrated.lock.yml
echo "## execution clone"; git -C "'"$REPO"'" rev-parse HEAD; git -C "'"$REPO"'" status --porcelain | wc -l
cd "'"$REPO"'/src" && sha256sum deployment/scripts/collect-resources.sh deployment/images.lock.env deployment/compose.yaml
echo "## host helpers"; sha256sum "$HOME/egw-tcg/itest-helpers.sh" "$HOME/egw-tcg/tunnel.sh" "$HOME/egw-tcg/ca.crt"
echo "## controller image record"; I="${EGW_IMAGES_DIR:-/home/ruisth/egw-images}"; sha256sum "$I/egw-controller-0.1.0-arm64.tar"; cat "$I/egw-controller-0.1.0-arm64.identity.txt"
'
cp "$EXEC/venv-freeze.txt" "$S/environment/venv-freeze.txt"
"$PY" -m pip freeze > "$S/environment/venv-freeze-now.txt" 2>&1

ex "$S" boot bash "$S/scripts/session_open.sh" "$S" "$RUN"
rc=$?
QPID=$(pgrep -f qemu-system-aarch64 | head -n 1)
(cd "$REPO/src" && $LE set --attempt "$S" "pid=${QPID:-0}")
if [ "$rc" -ne 0 ] || [ -z "$QPID" ]; then
    (cd "$REPO/src" && $LE finish --attempt "$S" --status failed --validity not-applicable --outcome fail \
        --reason "boot failed (session_open exit $rc; qemu pid '${QPID:-none}')" --next-action "read boot/ and console/")
    rm -f "$EXEC/current_session"
    export_attempt "$S"
    exit 1
fi
gx "$S" guest-state-after-boot 'set -u; systemctl is-system-running; uptime; free -m; df -h / /var/lib/docker /tmp;
  echo "## journal replay / fsck"; sudo -n journalctl -b --no-pager | grep -iE "recover|EXT4-fs" | head -n 40;
  echo "## docker"; docker ps -a --format "{{.Names}} {{.Status}} {{.Image}}";
  echo "## clock"; timedatectl show; date -u +%Y-%m-%dT%H:%M:%SZ;
  echo "## OOM so far this boot"; sudo -n dmesg | grep -ci "memory cgroup out of memory" || true'
echo "session open: $S (qemu pid $QPID)"
