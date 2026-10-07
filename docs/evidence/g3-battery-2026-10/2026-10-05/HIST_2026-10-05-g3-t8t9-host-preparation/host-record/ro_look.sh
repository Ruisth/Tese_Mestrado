#!/bin/bash
# Read-only look at the host, made while g3_hostprep.sh was being revised for
# S3 (2026-10-04): it shows that the paths the script names exist and what they
# hold today. It writes nothing (git runs with GIT_OPTIONAL_LOCKS=0, no fetch,
# no checkout, no helper regeneration, no debugfs) and is NOT the host
# preparation: g3_hostprep.sh makes the recorded comparisons.
# Usage (WSL, login shell): ro_look.sh
set -u
export GIT_OPTIONAL_LOCKS=0
C=/home/ruisth/egw-exec/repo
Y=/home/ruisth/yocto/egw
BUILD=$Y/src/yocto/build-integrated
DEP=$BUILD/tmp/deploy/images/qemuarm64
OUT="/mnt/c/Users/ruimf/Documents/Projeto Mestrado/output_test"
ATT=/home/ruisth/egw-exec/attempts
echo "## $(date -u +%FT%TZ) clone"
echo "HEAD=$(git -C "$C" rev-parse HEAD) porcelain_lines=$(git -C "$C" status --porcelain | wc -l)"
echo "## the four added identities and the launcher"
ls -l "$DEP/Image-qemuarm64.bin" "$DEP/egw-gateway-image-qemuarm64.rootfs-20260918120819.qemuboot.conf" \
    "$BUILD/tmp/work/x86_64-linux/qemu-helper-native/1.0/recipe-sysroot-native/usr/bin/qemu-system-aarch64" \
    "$Y/src/yocto/scripts/run-qemu-integrated.sh" "$DEP/egw-gateway-image-qemuarm64.rootfs-20260918120819.ext4"
sha256sum "$DEP/Image-qemuarm64.bin" "$DEP/egw-gateway-image-qemuarm64.rootfs-20260918120819.qemuboot.conf" \
    "$BUILD/tmp/work/x86_64-linux/qemu-helper-native/1.0/recipe-sysroot-native/usr/bin/qemu-system-aarch64" \
    "$Y/src/yocto/scripts/run-qemu-integrated.sh"
echo "yocto checkout: $(git -C "$Y" rev-parse HEAD) porcelain_lines=$(git -C "$Y" status --porcelain | wc -l)"
echo "## root file system"
sha256sum "$DEP/egw-gateway-image-qemuarm64.rootfs-20260918120819.ext4"
echo "## host files"
sha256sum /home/ruisth/egw-tcg/itest-helpers.sh /home/ruisth/egw-tcg/tunnel.sh /home/ruisth/egw-tcg/ca.crt \
    /home/ruisth/egw-tcg/pilot/campaign_plan.json /home/ruisth/egw-tcg/sut_environment.json \
    /home/ruisth/egw-images/egw-controller-0.1.0-arm64.identity.txt
wc -l < /home/ruisth/egw-tcg/itest-helpers.sh
ls -l /home/ruisth/egw-tcg/itest-helpers.sh*
cat /home/ruisth/egw-tcg/deploy_source_commit.txt
echo "## -q2 identifiers on the host"
for id in itest-reboot-q2 itest-post-reboot-01-q2 itest-tls-wrongca-q2 itest-auth-wrongpw-q2 itest-notls-q2; do
    ls -d /home/ruisth/egw-tcg/itest/$id /home/ruisth/egw-tcg/itest/$id.* /home/ruisth/egw-tcg/itest-replay/$id \
        /home/ruisth/egw-tcg/pilot/results/raw/$id 2> /dev/null
    echo "looked: $id"
done
t0=$(date +%s)
find "$ATT" "$OUT" -name '*-q2*' 2> /dev/null | head -n 20
echo "names holding -q2 under the attempts directory and output_test: listed above ($(($(date +%s) - t0)) s)"
echo "## g3-qualification attempts"
t0=$(date +%s)
find "$ATT" "$OUT/runs" "$OUT/incomplete" -name '*_g3-qualification-*_attempt*' 2> /dev/null | sort
echo "(recursive listing took $(($(date +%s) - t0)) s)"
ls -d "$OUT/incomplete" 2>&1
echo "## state directories and tools"
ls -ld /home/ruisth/egw-exec/g3-battery /home/ruisth/egw-exec/g3-t8t9-s3 2>&1
command -v debugfs timeout sha256sum git
