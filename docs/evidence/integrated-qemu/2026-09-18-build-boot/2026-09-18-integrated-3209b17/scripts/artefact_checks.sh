#!/bin/bash
# Runbook sections 2.3-2.5: acceptance on the built artefacts (no boot) and
# record of the build identity. Usage: artefact_checks.sh <evidence-dir>
set -u
E=$1
REPO=/home/ruisth/yocto/egw
Y=$REPO/src/yocto
B=$Y/build-integrated
DEPLOY=$B/tmp/deploy/images/qemuarm64
G1DEPLOY=$Y/build/tmp/deploy/images/qemuarm64
PREV=$HOME/yocto/evidence-candidates/2026-09-18-integrated-68f9ae7
EV=$E/build
mkdir -p "$EV"
fail=0
check() { # check <name> <command...>
    local name=$1; shift
    if "$@" >/dev/null 2>&1; then echo "PASS  $name"; else echo "FAIL  $name"; fail=$((fail + 1)); fi
}

echo "== 2.3 deploy directory =="
ls -l "$DEPLOY" | tee "$EV/deploy.ls.txt"

echo "== 2.4 manifest packages =="
M=$DEPLOY/egw-gateway-image-qemuarm64.rootfs.manifest
for p in docker-compose curl sudo openssh-sftp-server docker-moby containerd-opencontainers runc-opencontainers egw-gateway-config egw-base-config; do
    check "package $p in manifest" grep -qE "^$p " "$M"
done
grep -E '^(docker-compose|curl|sudo|openssh-sftp-server|docker-moby|containerd-opencontainers|runc-opencontainers|egw-gateway-config|egw-base-config) ' "$M"
echo "kernel-module packages: $(grep -cE '^kernel-module-' "$M")"
echo "manifest packages total: $(wc -l < "$M")"
check "kernel-image NOT in rootfs manifest" sh -c "! grep -qE '^kernel-image' '$M'"
check "rpcbind NOT in rootfs manifest" sh -c "! grep -qE '^rpcbind ' '$M'"

echo "== 2.4 testdata.json =="
python3 - "$DEPLOY/egw-gateway-image-qemuarm64.rootfs.testdata.json" <<'EOF' | tee "$EV/testdata.selected.txt"
import json, sys
d = json.load(open(sys.argv[1]))
for k in ("IMAGE_FEATURES", "DISTRO_FEATURES", "MACHINE_FEATURES", "QB_CPU", "QB_MEM", "QB_SMP", "QB_SLIRP_OPT", "QB_OPT_APPEND", "IMAGE_LINK_NAME"):
    print(k, "=", d.get(k))
EOF
T=$EV/testdata.selected.txt
check "IMAGE_FEATURES without debug-tweaks" sh -c "! grep -E '^IMAGE_FEATURES' '$T' | grep -q debug-tweaks"
check "QB_CPU is cortex-a76" grep -qE '^QB_CPU = -cpu cortex-a76' "$T"
check "QB_MEM is -m 8192" grep -qE '^QB_MEM = -m 8192' "$T"
check "hostfwd 127.0.0.1:2222->22" grep -q 'hostfwd=tcp:127.0.0.1:2222-:22' "$T"
check "hostfwd 127.0.0.1:8883->8883" grep -q 'hostfwd=tcp:127.0.0.1:8883-:8883' "$T"
check "no forward bound to 0.0.0.0" sh -c "! grep -E '^QB_SLIRP_OPT' '$T' | grep -qE 'hostfwd=tcp:(0\.0\.0\.0)?:'"

echo "== 2.4 files inside the rootfs tarball =="
TB=$DEPLOY/egw-gateway-image-qemuarm64.rootfs.tar.bz2
tar -xjOf "$TB" ./etc/shadow | grep -E '^(root|egw):' | sed -E 's/^([^:]+):([^:]*):.*/\1 password-field=[\2]/' | tee "$EV/shadow.fields.txt"
check "egw password field is '*'" grep -qxF 'egw password-field=[*]' "$EV/shadow.fields.txt"
check "root password field is '*'" grep -qxF 'root password-field=[*]' "$EV/shadow.fields.txt"
tar -xjOf "$TB" ./etc/ssh/sshd_config.d/10-egw.conf ./etc/docker/daemon.json ./etc/fstab ./etc/hostname 2>&1 | tee "$EV/rootfs.config-files.txt"
check "fstab has the egw-data entry" grep -qE '^LABEL=egw-data[[:space:]]+/var/lib/docker' "$EV/rootfs.config-files.txt"
tar -tjvf "$TB" ./etc/sudoers.d ./home/egw/.ssh ./var/log 2>&1 | tee "$EV/rootfs.modes.txt"
check "/etc/sudoers.d is 0750" grep -qE '^drwxr-x---.* \./etc/sudoers\.d/?$' "$EV/rootfs.modes.txt"
check "/etc/sudoers.d/egw is 0440" grep -qE '^-r--r-----.* \./etc/sudoers\.d/egw$' "$EV/rootfs.modes.txt"
check "authorized_keys present" grep -qE ' \./home/egw/\.ssh/authorized_keys$' "$EV/rootfs.modes.txt"
tar -xjOf "$TB" ./home/egw/.ssh/authorized_keys > "$EV/authorized_keys.in-image.txt" 2>/dev/null
check "authorized_keys equals ~/.ssh/egw_campaign.pub" cmp -s "$EV/authorized_keys.in-image.txt" "$HOME/.ssh/egw_campaign.pub"

echo "== 2.5 build identity =="
git -C "$REPO" rev-parse HEAD | tee "$EV/source_commit.txt"
git -C "$REPO" status --porcelain > "$EV/git_status.txt"
check "clone is clean" test ! -s "$EV/git_status.txt"
cp -p "$B/conf/local.conf" "$B/conf/bblayers.conf" "$EV/"
cp -p "$M" "$DEPLOY/egw-gateway-image-qemuarm64.rootfs.testdata.json" "$DEPLOY/egw-gateway-image-qemuarm64.rootfs.qemuboot.conf" "$EV/"
LATEST_BUILD_LOG=$(ls -t "$HOME"/yocto/logs/kas-build-integrated-*.log | head -1)
LATEST_CHECKOUT_LOG=$(ls -t "$HOME"/yocto/logs/kas-checkout-integrated-*.log | head -1)
cp -p "$LATEST_BUILD_LOG" "$LATEST_CHECKOUT_LOG" "$EV/"
grep -E 'Sstate summary|Tasks Summary' "$LATEST_BUILD_LOG" | tee "$EV/sstate-summary.txt"
( cd "$DEPLOY" && sha256sum "$(readlink egw-gateway-image-qemuarm64.rootfs.ext4)" "$(readlink egw-gateway-image-qemuarm64.rootfs.tar.bz2)" "$(readlink Image)" ) | tee "$EV/SHA256SUMS.artefacts"
( cd "$DEPLOY" && ls -l egw-gateway-image-qemuarm64.rootfs.ext4 "$(readlink egw-gateway-image-qemuarm64.rootfs.ext4)" ) | tee -a "$EV/deploy.ls.txt" >/dev/null
tar -xjOf "$TB" ./etc/buildinfo > "$EV/buildinfo.txt" 2>/dev/null || echo "no /etc/buildinfo (image-buildinfo not inherited)" > "$EV/buildinfo.txt"
# The sysroots-components binary cannot find libfdt outside a recipe sysroot;
# the image recipe sysroot is the copy runqemu executes.
QEMU=$B/tmp/work/qemuarm64-poky-linux/egw-gateway-image/1.0/recipe-sysroot-native/usr/bin/qemu-system-aarch64
echo "$QEMU" > "$EV/qemu_binary_path.txt"
"$QEMU" --version 2>&1 | head -1 | tee "$EV/qemu_version.txt"
check "QEMU reports a version" grep -q "QEMU emulator version" "$EV/qemu_version.txt"

echo "== kernel Image: G1 versus integrated =="
g1=$(sha256sum "$G1DEPLOY/Image" | cut -d' ' -f1); it=$(sha256sum "$DEPLOY/Image" | cut -d' ' -f1)
echo "G1         $g1"; echo "integrated $it"
check "kernel Image byte-identical to G1" test "$g1" = "$it"

echo "== G1 deploy directory untouched =="
ls -laL --time-style=full-iso "$G1DEPLOY" > "$EV/g1-deploy-after.ls.txt"
check "G1 deploy listing identical to the pre-build record" diff -q "$EV/g1-deploy-after.ls.txt" "$PREV/g1-deploy-before.ls.txt"
( cd "$G1DEPLOY" && sha256sum -c "$PREV/g1-deploy-before.sha256" ) 2>&1 | tee "$EV/g1-deploy-after.sha256check.txt"
check "G1 artefact checksums identical to the pre-build record" sh -c "cd '$G1DEPLOY' && sha256sum -c --quiet '$PREV/g1-deploy-before.sha256'"

echo "== result: $fail failed check(s) =="
echo "failed=$fail" > "$EV/artefact-checks.status"
exit "$fail"
