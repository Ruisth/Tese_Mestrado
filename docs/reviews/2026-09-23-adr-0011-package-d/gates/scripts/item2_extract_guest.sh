#!/bin/bash
# item2_extract_guest.sh -- package D, gate item 2 (r02 guest-side evidence).
#
# Copies, READ-ONLY, the guest-side files that bear on controller_restart-r02
# out of the guest's two disk images, without starting the guest:
#   - the rootfs image (journal, the guest copy of the r02 event log);
#   - nothing from the data disk (its containers were recreated on
#     2026-09-20, see the gate note).
# debugfs is used in catalog mode (-c), which opens the image read-only and
# never replays or writes the ext4 journal. Nothing is mounted, nothing is
# written to either image. Output goes only to gates/item2_extract/.
#
# Run from WSL:  bash item2_extract_guest.sh
set -eu
ROOTFS=/home/ruisth/yocto/egw/src/yocto/build-integrated/tmp/deploy/images/qemuarm64/egw-gateway-image-qemuarm64.rootfs-20260918120819.ext4
HERE=$(cd "$(dirname "$0")" && pwd)
OUT="$HERE/../item2_extract"
mkdir -p "$OUT"

if pgrep -f qemu-system-aarch64 >/dev/null; then
    echo "STOP: a qemu-system-aarch64 process is running; the images are in use" >&2
    exit 1
fi

J=/var/log/journal/164be2431eb24037a415dd1641011fa6
FILES="
$J/system@1ce5b55b1e384e95abac528e90f476a9-0000000000002896-00065bcaad24f26b.journal
$J/system@1ce5b55b1e384e95abac528e90f476a9-0000000000002a76-00065bcaad8a43ea.journal
$J/user-1000@1ce5b55b1e384e95abac528e90f476a9-0000000000002a75-00065bcaad86cf14.journal
/opt/egw/deployment/data/events/controller_restart-r02/events.jsonl
/opt/egw/deployment/data/events/controller_restart-r01/events.jsonl
"
{
    echo "# item2 extraction record"
    echo "extracted_utc=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
    echo "rootfs=$ROOTFS"
    stat -c 'rootfs_size=%s rootfs_mtime=%y' "$ROOTFS"
    debugfs -V 2>&1 | head -1
    for f in $FILES; do
        base=$(echo "$f" | sed 's#^/##; s#/#__#g')
        debugfs -c -R "dump $f $OUT/$base" "$ROOTFS" 2>/dev/null
        echo "--- $f"
        debugfs -c -R "stat $f" "$ROOTFS" 2>/dev/null | grep -E '^(Inode|User|Links|.*time:)' || true
        sha256sum "$OUT/$base"
    done
} > "$OUT/extraction_record.txt"
cat "$OUT/extraction_record.txt"
