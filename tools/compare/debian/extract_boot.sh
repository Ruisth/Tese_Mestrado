#!/bin/bash
# tools/compare/debian/extract_boot.sh - take Debian's own kernel, initrd and root file-system UUID
# out of a genericcloud qcow2 image, without root privileges and without mounting anything.
#
#   extract_boot.sh <image.qcow2> <outdir>
#
# Writes to <outdir>: vmlinuz, initrd.img, root-uuid.txt, partitions.txt, boot-files.sha256, and
# prints the kernel file name and the UUID. Exit codes: 0 done; 2 usage or a missing tool;
# 3 unexpected image layout (no GPT, no Linux root partition, zero or several kernels in /boot);
# 4 extraction failed.
#
# How: qemu-img ($EGW_COMPARE_QEMU_IMG, else qemu-img on PATH) converts the qcow2 to a sparse raw
# copy; python3 (standard library) parses the GPT at LBA 1, checks both CRCs and picks the largest
# "Linux filesystem" partition as the root; dd copies that partition sparsely into its own file;
# debugfs (e2fsprogs, read only, user mode) lists /boot and dumps the single vmlinuz-*/initrd.img-*
# pair; blkid (or debugfs's stats) reads the ext4 UUID the kernel command line needs
# (root=UUID=...). The temporary base.raw and root.part are removed on exit.
#
# Debian's arm64 /boot/vmlinuz-* is a gzip-compressed kernel Image. QEMU 8.2's aarch64 -kernel
# loader accepts a raw Image and a gzip-compressed one alike (it inflates the latter before placing
# it), so the file is kept exactly as dumped and its magic is recorded in partitions.txt
# (1f8b = gzip; 'ARM\x64' at offset 56 = raw Image).
set -u

QEMU_IMG=${EGW_COMPARE_QEMU_IMG:-qemu-img}

usage() { sed -n '2,10p' "$0" | sed 's/^# \{0,1\}//' >&2; exit 2; }
stop() { echo "STOP: $2" >&2; exit "$1"; }

[ $# -eq 2 ] || usage
img=$1
out=$2
if [ -z "$img" ] || [ -z "$out" ]; then usage; fi
[ -r "$img" ] || stop 2 "image not readable: $img"
case $out in
    *[[:space:]]*) stop 2 "output directory must not contain white space (debugfs splits its request on it): $out" ;;
esac
for tool in "$QEMU_IMG" python3 dd debugfs sha256sum od; do
    command -v "$tool" > /dev/null 2>&1 || stop 2 "tool missing: $tool"
done
mkdir -p "$out" || stop 2 "cannot create $out"

raw=$out/base.raw
part=$out/root.part
table=$out/partitions.txt
cleanup() { rm -f "$raw" "$part"; }
trap cleanup EXIT

# 1. qcow2 -> sparse raw copy (qemu-img writes holes for unallocated clusters).
rm -f "$raw"
"$QEMU_IMG" convert -O raw "$img" "$raw" || stop 4 "qemu-img convert failed for $img"
[ -s "$raw" ] || stop 4 "qemu-img produced no raw image"

# 2. GPT: header at LBA 1, entry array where the header says; the largest Linux filesystem
#    partition is the root. Prints 'index start_bytes size_bytes'; writes the table.
geometry=$(python3 - "$raw" "$table" << 'PY'
import os
import struct
import sys
import uuid
import zlib

raw, table = sys.argv[1], sys.argv[2]
LINUX_FS = uuid.UUID("0FC63DAF-8483-4772-8E79-3D69D16ADBBF")
KNOWN = {
    LINUX_FS: "Linux filesystem",
    uuid.UUID("C12A7328-F81F-11D2-BA4B-00A0C93EC93B"): "EFI System",
    uuid.UUID("21686148-6449-6E6F-744E-656564454649"): "BIOS boot",
    uuid.UUID("0657FD6D-A4AB-43C4-84E5-0933C84B4F4F"): "Linux swap",
    uuid.UUID("BC13C2FF-59E6-4262-A352-B275FD6F7172"): "Linux extended boot",
}


def stop(code, msg):
    print("STOP: " + msg, file=sys.stderr)
    sys.exit(code)


size = os.path.getsize(raw)
with open(raw, "rb") as fh:
    mbr = fh.read(512)
    sector = None
    for candidate in (512, 4096):
        fh.seek(candidate)
        if fh.read(8) == b"EFI PART":
            sector = candidate
            break
    if sector is None:
        stop(3, "no GPT header at LBA 1 (512- or 4096-byte sectors): not a GPT image")
    fh.seek(sector)
    fixed = fh.read(92)
    (_sig, _rev, hsize, hcrc, _res, _cur, _bak, first_usable, last_usable, disk_guid,
     entries_lba, count, esize, ecrc) = struct.unpack("<8sIIIIQQQQ16sQIII", fixed)
    if hsize < 92 or hsize > sector:
        stop(3, f"GPT header size {hsize} is out of range")
    fh.seek(sector)
    header = fh.read(hsize)
    if zlib.crc32(header[:16] + b"\0\0\0\0" + header[20:]) != hcrc:
        stop(3, "GPT header CRC32 mismatch")
    if not 1 <= count <= 1024 or esize < 128 or esize % 8:
        stop(3, f"GPT entry array {count} x {esize} bytes is out of range")
    fh.seek(entries_lba * sector)
    entries = fh.read(count * esize)
    if len(entries) != count * esize:
        stop(3, "GPT partition entry array is truncated")
    if zlib.crc32(entries) != ecrc:
        stop(3, "GPT partition entry array CRC32 mismatch")

protective = mbr[510:512] == b"\x55\xaa" and 0xEE in (mbr[450], mbr[466], mbr[482], mbr[498])
rows = []
for i in range(count):
    entry = entries[i * esize:(i + 1) * esize]
    type_guid = uuid.UUID(bytes_le=entry[0:16])
    if type_guid.int == 0:
        continue
    first, last = struct.unpack_from("<QQ", entry, 32)
    name = entry[56:128].decode("utf-16-le", "replace").split("\0", 1)[0]
    if last < first or (last + 1) * sector > size:
        stop(3, f"partition {i + 1} ({name!r}) lies outside the image: LBA {first}..{last}")
    rows.append((i + 1, type_guid, first, last, name))
if not rows:
    stop(3, "GPT holds no partition")
linux = [r for r in rows if r[1] == LINUX_FS]
if not linux:
    stop(3, "no Linux filesystem partition (type 0FC63DAF-8483-4772-8E79-3D69D16ADBBF) in the GPT")
root = max(linux, key=lambda r: r[3] - r[2])

lines = [
    f"# GPT of {os.path.basename(raw)} ({size} bytes, {sector}-byte sectors): header crc ok, "
    f"entries at LBA {entries_lba} ({count} x {esize} bytes, crc ok), protective MBR {'yes' if protective else 'no'}",
    f"# disk GUID {uuid.UUID(bytes_le=disk_guid)}; usable LBAs {first_usable}..{last_usable}",
    "# index  type-guid  (type)  first-lba  last-lba  bytes  name",
]
for index, type_guid, first, last, name in rows:
    kind = KNOWN.get(type_guid, "other")
    lines.append(f"{index}  {str(type_guid).upper()}  ({kind})  {first}  {last}  {(last - first + 1) * sector}  {name!r}")
lines.append(f"root: index={root[0]} first_lba={root[2]} start_bytes={root[2] * sector} "
             f"size_bytes={(root[3] - root[2] + 1) * sector} name={root[4]!r}")
with open(table, "w", encoding="utf-8") as fh:
    fh.write("\n".join(lines) + "\n")
print(root[0], root[2] * sector, (root[3] - root[2] + 1) * sector)
PY
)
rc=$?
[ "$rc" -eq 0 ] || exit "$rc"
read -r root_index start size <<< "$geometry"
[ -n "${size:-}" ] || stop 3 "GPT parser printed no geometry"

# 3. The root partition alone, sparsely (holes stay holes).
rm -f "$part"
dd if="$raw" of="$part" bs=1M iflag=skip_bytes,count_bytes skip="$start" count="$size" conv=sparse status=none \
    || stop 4 "dd of partition $root_index failed"
[ -s "$part" ] || stop 4 "partition $root_index copy is empty"

# 4. /boot listing (debugfs 'ls -p': /inode/mode/uid/gid/name/size/), one kernel and its initrd.
listing=$(debugfs -R "ls -p /boot" "$part" 2> /dev/null)
[ -n "$listing" ] || stop 3 "debugfs could not list /boot of partition $root_index (not an ext2/3/4 root?)"
kernels=$(printf '%s\n' "$listing" | awk -F/ '$6 ~ /^vmlinuz-/ { print $6 }')
initrds=$(printf '%s\n' "$listing" | awk -F/ '$6 ~ /^initrd\.img-/ { print $6 }')
nkernels=$(printf '%s\n' "$kernels" | grep -c .)
if [ "$nkernels" -ne 1 ]; then
    stop 3 "expected exactly one vmlinuz-* in /boot, found $nkernels:$(printf ' %s' $kernels)"
fi
kernel=$kernels
initrd=initrd.img-${kernel#vmlinuz-}
printf '%s\n' "$initrds" | grep -qx -- "$initrd" || stop 3 "/boot/$initrd is not next to /boot/$kernel"

dump_one() {
    rm -f "$2"
    debugfs -R "dump /boot/$1 $2" "$part" > /dev/null 2>&1
    [ -s "$2" ] || { echo "STOP: debugfs could not dump /boot/$1" >&2; return 1; }
}
dump_one "$kernel" "$out/vmlinuz" || exit 4
dump_one "$initrd" "$out/initrd.img" || exit 4

# 5. Root file-system UUID for root=UUID=... (blkid reads a plain file unprivileged).
uuid=
if command -v blkid > /dev/null 2>&1; then
    uuid=$(blkid -o value -s UUID "$part" 2> /dev/null)
fi
if [ -z "$uuid" ]; then
    uuid=$(debugfs -R stats "$part" 2> /dev/null | sed -n 's/^Filesystem UUID:[[:space:]]*//p' | sed -n '1p')
fi
printf '%s\n' "$uuid" | grep -qE '^[0-9a-f]{8}(-[0-9a-f]{4}){3}-[0-9a-f]{12}$' \
    || stop 4 "root file-system UUID not found on partition $root_index"
printf '%s\n' "$uuid" > "$out/root-uuid.txt"

# 6. Record what was dumped: sizes, magic bytes, checksums.
magic4() { od -An -tx1 -N4 "$1" | tr -d ' \n'; }
kmagic=$(magic4 "$out/vmlinuz")
case $kmagic in
    1f8b*) kkind="gzip-compressed Image (QEMU -kernel inflates it)" ;;
    *)
        if [ "$(od -An -tx1 -j56 -N4 "$out/vmlinuz" | tr -d ' \n')" = "41524d64" ]; then
            kkind="raw arm64 Image"
        else
            kkind="unknown"
        fi
        ;;
esac
imagic=$(magic4 "$out/initrd.img")
case $imagic in
    1f8b*) ikind=gzip ;;
    28b52ffd) ikind=zstd ;;
    fd377a58) ikind=xz ;;
    04224d18) ikind=lz4 ;;
    30373037*) ikind=cpio ;;
    *) ikind=unknown ;;
esac
{
    printf 'kernel=%s bytes=%s magic=%s kind=%s\n' "$kernel" "$(wc -c < "$out/vmlinuz" | tr -d ' ')" "$kmagic" "$kkind"
    printf 'initrd=%s bytes=%s magic=%s kind=%s\n' "$initrd" "$(wc -c < "$out/initrd.img" | tr -d ' ')" "$imagic" "$ikind"
    printf 'root_uuid=%s\n' "$uuid"
} >> "$table"
(cd "$out" && sha256sum vmlinuz initrd.img > boot-files.sha256) || stop 4 "sha256sum failed"

echo "kernel=$kernel initrd=$initrd root_uuid=$uuid root_partition=$root_index kernel_kind=$kkind"
