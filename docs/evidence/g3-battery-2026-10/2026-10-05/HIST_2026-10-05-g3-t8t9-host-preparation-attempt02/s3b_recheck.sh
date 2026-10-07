#!/bin/bash
# Read-only recheck before the second opening of S3 (authorisation of 2026-10-05): no guest, no
# open session, the execution clone and the helper as sealed, the root file system at the value
# the first opening's close recorded, and the five -q2 identifiers unused on the host and on the
# guest's root file system (read offline with debugfs -c). Writes only its console.
# Usage (WSL): s3b_recheck.sh <record dir>   (the directory must not hold a console.txt yet)
set -u
REC=${1:?usage: s3b_recheck.sh <record dir>}
mkdir -p "$REC" || exit 2
[ ! -e "$REC/console.txt" ] || { echo "STOP: $REC/console.txt exists - never overwritten"; exit 2; }
exec > >(tee -a "$REC/console.txt") 2>&1
OUTCOME=checked
fail() { echo "STOP: $*"; OUTCOME=failed; }
say() { echo; echo "## $(date -u +%Y-%m-%dT%H:%M:%SZ) $*"; }
TOOLS=8e492613d36490a560ae56beabd6d5c2c01a8696
TREE=2f0514837f267d8975f7071041aad14a5c18dcab
HELPER_SHA=e5eba37e529a47885a8aea0e718d25ac71ce1e31a0c1a381b4520fe4c914b4fb
ROOTFS_WANT=b48b010d571689ae03d610175fd1b127f6ef6b30f78b25448e6f32a3096de093
ROOTFS=$HOME/yocto/egw/src/yocto/build-integrated/tmp/deploy/images/qemuarm64/egw-gateway-image-qemuarm64.rootfs-20260918120819.ext4
OT="/mnt/c/Users/ruimf/Documents/Projeto Mestrado/output_test"
IDS="itest-reboot-q2 itest-post-reboot-01-q2 itest-tls-wrongca-q2 itest-auth-wrongpw-q2 itest-notls-q2"
echo "s3b_recheck.sh sha256 $(sha256sum "$0" | cut -d' ' -f1)"

say "no guest, no open session"
if pgrep -f qemu-system-aarch64 > /dev/null; then fail "a qemu-system-aarch64 process runs"; else echo "no qemu-system-aarch64 process"; fi
if [ -e "$HOME/egw-exec/current_session" ]; then fail "a session is open"; else echo "no current_session"; fi

say "execution clone and helper"
H=$(git -C "$HOME/egw-exec/repo" rev-parse HEAD); T=$(git -C "$HOME/egw-exec/repo" rev-parse 'HEAD^{tree}')
D=$(GIT_OPTIONAL_LOCKS=0 git -C "$HOME/egw-exec/repo" status --porcelain | wc -l)
echo "clone HEAD=$H tree=$T porcelain lines=$D"
[ "$H" = "$TOOLS" ] && [ "$T" = "$TREE" ] && [ "$D" = 0 ] || fail "the clone is not at $TOOLS, tree $TREE, clean"
hs=$(sha256sum "$HOME/egw-tcg/itest-helpers.sh" | cut -d' ' -f1); hl=$(wc -l < "$HOME/egw-tcg/itest-helpers.sh")
echo "helper sha256=$hs lines=$hl"
[ "$hs" = "$HELPER_SHA" ] && [ "$hl" = 545 ] || fail "the helper file is not $HELPER_SHA (545 lines)"

say "root file system before the listing"
r1=$(sha256sum "$ROOTFS" | cut -d' ' -f1)
echo "rootfs-ext4: $r1  $ROOTFS"
echo "expected:    $ROOTFS_WANT (rootfs_after_close of the first opening of S3)"
[ "$r1" = "$ROOTFS_WANT" ] || fail "the root file system is not the expected one"

say "the -q2 identifiers on the host (file names under ~/egw-tcg, ~/egw-exec/attempts and output_test)"
for id in $IDS; do
    hits=$(find "$HOME/egw-tcg" "$HOME/egw-exec/attempts" "$OT" -path "*/HIST_*-g3-t8t9-host-preparation*" -prune -o -name "*$id*" -print 2> /dev/null | head -5)
    if [ -n "$hits" ]; then echo "NOT FRESH on the host: $id"; echo "$hits"; fail "$id has a host file"; else echo "fresh on the host: $id"; fi
done

say "earlier attempts of rows t8 and t9"
find "$HOME/egw-exec/attempts" "$OT/runs" "$OT/incomplete" -maxdepth 2 \( -name '*_g3-qualification-t8_attempt*' -o -name '*_g3-qualification-t9_attempt*' \) 2> /dev/null | sort | tee "$REC/t8-t9-attempts.txt"
n8=$(grep -c '_g3-qualification-t8_attempt' "$REC/t8-t9-attempts.txt"); n9=$(grep -c '_g3-qualification-t9_attempt' "$REC/t8-t9-attempts.txt")
other=$(grep '_g3-qualification-t8_attempt' "$REC/t8-t9-attempts.txt" | grep -vc '20261003T142310Z_g3-qualification-t8_attempt01$')
echo "t8 attempts listed: $n8 (other than S2's attempt01: $other); t9 attempts listed: $n9"
[ "$other" = 0 ] && [ "$n9" = 0 ] || fail "an attempt of t8 other than S2's attempt01, or an attempt of t9, exists"

say "the -q2 identifiers on the guest root file system (offline, read-only: debugfs -c)"
/usr/sbin/debugfs -c -R "ls -l /opt/egw/deployment/data/events" "$ROOTFS" > "$REC/guest-events-listing.txt" 2> "$REC/guest-events-listing.stderr.txt"
awk 'NF >= 9 {print $NF}' "$REC/guest-events-listing.txt" | sort > "$REC/guest-events-names.txt"
grep -qxF -- . "$REC/guest-events-names.txt" && grep -qxF -- .. "$REC/guest-events-names.txt" || fail "the guest listing shows no '.' and '..': the directory was not read"
echo "guest event directories listed: $(wc -l < "$REC/guest-events-names.txt") names"
for id in $IDS; do
    if grep -q -- "$id" "$REC/guest-events-names.txt"; then fail "NOT FRESH on the guest: $id"; else echo "fresh on the guest: $id"; fi
done
r2=$(sha256sum "$ROOTFS" | cut -d' ' -f1)
echo "rootfs-ext4-after-listing: $r2"
[ "$r2" = "$ROOTFS_WANT" ] || fail "the root file system changed during the listing"

echo
echo "outcome=$OUTCOME (at $(date -u +%Y-%m-%dT%H:%M:%SZ))"
[ "$OUTCOME" = checked ]
