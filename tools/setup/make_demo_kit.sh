#!/bin/bash
# tools/setup/make_demo_kit.sh - build the demonstration kit on the author's machine: one ZIP with the files
# the demonstration needs that the repository does not hold, for tools/setup/prepare_demo_host.sh on
# another PC.
#
#   make_demo_kit.sh --package <yoctoScarthgap folder> [--images <dir>] [--out <dir>] [--date YYYYMMDD]
#                    [--qemu-img <path>]
#
#   --package   the SANITISED portable package of the Yocto image (README.md, BUILDINFO.txt, SHA256SUMS,
#               yoctoScarthgap.qcow2, Image, keys/egw_compare_share and .pub ...). Never the sealed
#               measured image: a package that lists an .ext4 or .wic (also compressed: .ext4.gz ...), a
#               rootfs*, a *rootfs*.ext4* or an .env file is refused.
#   --images    the folder with egw-controller-0.1.0-arm64.tar and its .identity.txt
#               (default $EGW_IMAGES_DIR, else $HOME/egw-images, as in tools/compare/provision_stack.sh)
#   --out       where egw-demo-kit-<date>.zip and egw-demo-kit-<date>.zip.sha256 are written (default
#               $HOME/egw-kit-out); outside the clone; an existing zip is never overwritten
#   --date      the kit's date stamp (default: today, UTC)
#   --qemu-img  the qemu-img that reads the disk images for the secret scan (default
#               $EGW_COMPARE_QEMU_IMG, else the default of tools/compare/lib.sh, else qemu-img on PATH)
#
# The zip holds one folder, egw-demo-kit-<date>/: README.txt; SHA256SUMS (every file); yoctoScarthgap/ (the
# files the package's own SHA256SUMS lists, byte for byte, and that SHA256SUMS); controller/ (the archive
# and its identity record).
# Before anything is zipped:
#   - the package's SHA256SUMS verifies; its BUILDINFO.txt records a clean final secret scan and names the
#     fingerprint of the shipped test key, whose private and public halves match;
#   - the controller archive matches its identity record, from a clean build context;
#   - a secret scan of the staging tree finds nothing: no .env file name, no complete PEM private-key
#     block other than the test key (which must hold that one key and nothing after it), no password
#     assignment with a value - in every file, inside the controller's image layers and the package's
#     tar.gz (compressed members are opened; one this scan cannot read, zstd for example, or a disk image
#     inside an archive or compressed data, is a hit), and in every disk image read through qemu-img: the
#     root file system (there the pilot's known secret files must be absent and authorized_keys must hold
#     the test key only) and any other file with the qcow2 magic (data.qcow2: an empty ext4, only
#     lost+found); a qcow2 with internal snapshots, a backing file or a data file is a hit.
# Any hit refuses the kit; the scan reports where and which rule, never the matched text.
# The staging tree is a temporary folder under ${TMPDIR:-/tmp} (on the Linux file system, so that the
# test key keeps mode 600), removed at the end.
# Exit: 0 kit written; 2 usage or a missing input or tool; 3 an integrity check or the secret scan refused.
set -u
HERE=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
REPO=$(cd "$HERE/../.." && pwd -P)
CONTROLLER_TAR=egw-controller-0.1.0-arm64.tar
CONTROLLER_RECORD=egw-controller-0.1.0-arm64.identity.txt
PKG_REQUIRED="README.md BUILDINFO.txt yoctoScarthgap.qcow2 Image keys/egw_compare_share keys/egw_compare_share.pub"
ALLOWED_KEY=yoctoScarthgap/keys/egw_compare_share
# Files the pilot sessions held on the root file system that the sanitised copy must not hold.
ROOTFS_ABSENT="/opt/egw/deployment/.env /opt/egw/deployment/mosquitto/config/passwd /opt/egw/deployment/mosquitto/config/certs/server.key /opt/egw/deployment/mosquitto/config/certs/ca.key /etc/ssh/ssh_host_rsa_key /etc/ssh/ssh_host_ecdsa_key /etc/ssh/ssh_host_ed25519_key /home/egw/.ash_history"

die() { echo "STOP: $2" >&2; exit "$1"; }
usage() { awk 'NR == 1 { next } /^#/ { sub(/^# ?/, ""); print; next } { exit }' "${BASH_SOURCE[0]}"; }
sha256_of() { sha256sum "$1" | cut -d' ' -f1; }

PKG=
IMAGES=${EGW_IMAGES_DIR:-$HOME/egw-images}
OUT=${EGW_KIT_OUT:-$HOME/egw-kit-out}
DATE=$(date -u +%Y%m%d)
QIMG=${EGW_COMPARE_QEMU_IMG:-}
while [ $# -gt 0 ]; do
    case $1 in
        --package | --images | --out | --date | --qemu-img)
            [ $# -ge 2 ] && [ -n "$2" ] || die 2 "$1 needs a value"
            case $1 in
                --package) PKG=$2 ;;
                --images) IMAGES=$2 ;;
                --out) OUT=$2 ;;
                --date) DATE=$2 ;;
                --qemu-img) QIMG=$2 ;;
            esac
            shift 2
            ;;
        -h | --help) usage; exit 0 ;;
        *) die 2 "unknown argument: $1 (see --help)" ;;
    esac
done
[ -n "$PKG" ] || die 2 "--package <sanitised yoctoScarthgap folder> is required (see --help)"
case $DATE in [0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9]) ;; *) die 2 "--date must be YYYYMMDD" ;; esac
NAME=egw-demo-kit-$DATE
PKG=$(realpath -e -- "$PKG" 2> /dev/null) || die 2 "package folder not found"
[ -d "$PKG" ] || die 2 "$PKG is not a folder"
IMAGES=$(realpath -e -- "$IMAGES" 2> /dev/null) || die 2 "controller images folder not found (--images)"
OUT=$(realpath -m -- "$OUT")
case "$OUT/" in "$REPO"/*) die 2 "--out lies inside the clone ($REPO): the kit never enters the repository" ;; esac
ZIP=$OUT/$NAME.zip
[ ! -e "$ZIP" ] && [ ! -e "$ZIP.sha256" ] || die 2 "$ZIP (or its .sha256) already exists; it is never overwritten"
for t in python3 sha256sum ssh-keygen debugfs od tar; do
    command -v "$t" > /dev/null 2>&1 || die 2 "tool missing: $t"
done
if [ -z "$QIMG" ]; then
    # The default of the comparison tools (their QEMU's sibling); lib.sh only sets variables.
    QIMG=$(
        # shellcheck source=../compare/lib.sh
        . "$REPO/tools/compare/lib.sh" > /dev/null 2>&1
        printf '%s' "${COMPARE_QEMU_IMG:-}"
    )
    [ -x "$QIMG" ] || QIMG=$(command -v qemu-img || true)
fi
[ -n "$QIMG" ] && [ -x "$QIMG" ] || die 2 "qemu-img not found: the root file system cannot be scanned (give --qemu-img)"
export PAGER=__none__ DEBUGFS_PAGER=__none__

# --- 1. the sanitised package --------------------------------------------------------------------
echo "== package: $PKG"
[ -s "$PKG/SHA256SUMS" ] || die 3 "the package has no SHA256SUMS: nothing is taken from an unsealed package"
LISTED=$(awk '{ p = substr($0, 67); sub(/^\.\//, "", p); print p }' "$PKG/SHA256SUMS")
[ -n "$LISTED" ] || die 3 "the package's SHA256SUMS lists nothing"
SEALED="the sealed image (an .ext4 or .wic, compressed or not), a root file system copy or an .env file never goes into the kit"
while IFS= read -r rel; do
    case $rel in
        '' | /* | *..* | *[!A-Za-z0-9._/-]*) die 3 "unexpected path in the package's SHA256SUMS: '$rel'" ;;
    esac
    case /$rel in
        *.ext4 | *.ext4.* | *.wic | *.wic.* | */rootfs* | */.env | */.env.* | *.env) die 3 "the package lists $rel: $SEALED" ;;
    esac
    case ${rel##*/} in *rootfs*.ext4*) die 3 "the package lists $rel: $SEALED" ;; esac
done <<< "$LISTED"
for f in $PKG_REQUIRED; do
    printf '%s\n' "$LISTED" | grep -qxF -- "$f" || die 3 "the package's SHA256SUMS does not list $f"
done
(cd "$PKG" && sha256sum -c --quiet --strict SHA256SUMS > /dev/null 2>&1) || die 3 "the package does not match its own SHA256SUMS"
grep -Eq '^[[:space:]]*final scan clean[[:space:]]*$' "$PKG/BUILDINFO.txt" || die 3 "BUILDINFO.txt records no clean final secret scan: is this the sanitised package?"
[ "$(od -An -tx1 -N4 "$PKG/yoctoScarthgap.qcow2" | tr -d ' \n')" = 514649fb ] || die 3 "yoctoScarthgap.qcow2 is not a qcow2 image"
echo "   SHA256SUMS verified ($(printf '%s\n' "$LISTED" | grep -c .) files); BUILDINFO records a clean final scan"

# --- 2. the controller archive ---------------------------------------------------------------------
echo "== controller: $IMAGES"
[ -s "$IMAGES/$CONTROLLER_TAR" ] && [ -s "$IMAGES/$CONTROLLER_RECORD" ] || die 2 "$IMAGES lacks $CONTROLLER_TAR or $CONTROLLER_RECORD"
REC_SHA=$(sed -n 's/^archive_sha256=//p' "$IMAGES/$CONTROLLER_RECORD" | head -n 1)
[ -n "$REC_SHA" ] || die 3 "the identity record has no archive_sha256 line"
grep -q '^source_tree_state=clean$' "$IMAGES/$CONTROLLER_RECORD" || die 3 "the identity record is not from a clean build context (source_tree_state)"

# --- 3. staging ------------------------------------------------------------------------------------
STAGE=$(mktemp -d "${TMPDIR:-/tmp}/egw-demo-kit.XXXXXX") || die 2 "cannot create a staging folder"
trap 'rm -rf "$STAGE"' EXIT
TOP=$STAGE/$NAME
mkdir -p "$TOP/yoctoScarthgap" "$TOP/controller" || die 2 "cannot create $TOP"
while IFS= read -r rel; do
    mkdir -p "$TOP/yoctoScarthgap/$(dirname "$rel")" && cp "$PKG/$rel" "$TOP/yoctoScarthgap/$rel" || die 2 "cannot copy $rel"
done <<< "$LISTED"
cp "$PKG/SHA256SUMS" "$TOP/yoctoScarthgap/SHA256SUMS" || die 2 "cannot copy SHA256SUMS"
cp "$IMAGES/$CONTROLLER_TAR" "$IMAGES/$CONTROLLER_RECORD" "$TOP/controller/" || die 2 "cannot copy the controller archive"
# Modes as shipped: folders 0755, files 0644, scripts 0755, images 0444, the private test key 0600.
find "$TOP" -type d -exec chmod 0755 {} +
find "$TOP" -type f -exec chmod 0644 {} +
find "$TOP" -type f -name '*.sh' -exec chmod 0755 {} +
chmod 0444 "$TOP/yoctoScarthgap/yoctoScarthgap.qcow2" "$TOP/yoctoScarthgap/Image"
chmod 0600 "$TOP/$ALLOWED_KEY"
# What ships is what was verified: the staged copies are checked again.
(cd "$TOP/yoctoScarthgap" && sha256sum -c --quiet --strict SHA256SUMS > /dev/null 2>&1) || die 3 "the staged copy of the package does not verify"
[ "$(sha256_of "$TOP/controller/$CONTROLLER_TAR")" = "$REC_SHA" ] || die 3 "the controller archive does not match its identity record (archive_sha256)"
tar -tf "$TOP/controller/$CONTROLLER_TAR" 2> /dev/null | grep -qxE '(\./)?(manifest|index)\.json' || die 3 "$CONTROLLER_TAR is not an image archive (no manifest.json or index.json)"
echo "   archive matches its identity record (clean build context)"

# --- 4. the test key -------------------------------------------------------------------------------
KEY=$TOP/$ALLOWED_KEY
FP=$(ssh-keygen -lf "$KEY.pub" 2> /dev/null | awk '{ print $2 }')
case $FP in SHA256:*) ;; *) die 3 "the shipped public key cannot be read" ;; esac
grep -qF -- "$FP" "$PKG/BUILDINFO.txt" || die 3 "BUILDINFO.txt does not name the fingerprint of the shipped test key ($FP)"
PUB=$(awk 'NR == 1 { print $1 " " $2 }' "$KEY.pub")
[ "$(ssh-keygen -y -P '' -f "$KEY" < /dev/null 2> /dev/null | awk 'NR == 1 { print $1 " " $2 }')" = "$PUB" ] \
    || die 3 "the private and public halves of the shipped test key do not match (or the key has a passphrase)"
echo "   test key $FP: halves match, named in BUILDINFO.txt"

# --- 5. README.txt and SHA256SUMS ------------------------------------------------------------------
cat > "$TOP/README.txt" << EOF
EGW demonstration kit - $NAME

The files the demonstration of the EGW gateway needs that are not in the repository:
  yoctoScarthgap/  the shareable (sanitised) copy of the Yocto 5.0 Scarthgap gateway image of the
                   comparison: no stack configuration, no broker keys, no pilot evidence (see
                   yoctoScarthgap/BUILDINFO.txt); the measured image itself is not included
  controller/      the controller's container image (linux/arm64) and its identity record
  SHA256SUMS       the checksum of every file
The SSH key in yoctoScarthgap/keys/ is a TEST key for local use: the only key this copy of the image
accepts. The kit holds no password; the preparation script makes fresh ones on your PC.

Use (Windows 10/11 with WSL 2 and Ubuntu 24.04):
  1. In an Ubuntu terminal, put the repository on the Linux file system (for example ~/egw), not under /mnt/c.
  2. cd ~/egw && bash tools/setup/prepare_demo_host.sh --kit /mnt/c/Users/<you>/Downloads/$NAME.zip
     (keep $NAME.zip.sha256 beside the zip: it is checked; keep both: a re-run reads them again)
  3. Open a new Ubuntu terminal, cd ~/egw, then: bash tools/demo/demo.sh
The demonstration starts the gateway with tools/compare/tf.sh. Running yoctoScarthgap/run-linux.sh is not
needed: it starts a QEMU outside the guards of the comparison tools, which then refuse to start while it runs.
Details: tools/setup/README.md in the repository.
EOF
(cd "$TOP" && find . -type f ! -path ./SHA256SUMS -print0 | LC_ALL=C sort -z | xargs -0 sha256sum > SHA256SUMS) || die 2 "cannot write SHA256SUMS"
(cd "$TOP" && sha256sum -c --quiet --strict SHA256SUMS > /dev/null 2>&1) || die 3 "the kit's SHA256SUMS does not verify"

# --- 6. secret scan --------------------------------------------------------------------------------
echo "== secret scan"
# qcow2_hits LABEL FILE: a HIT line for each part of the qcow2 FILE that its conversion to raw does not read
# (internal snapshots) or that lies outside it (a backing file, an external data file), from qemu-img info;
# returns 1 when there is one (also when qemu-img info gives no answer).
qcow2_hits() {
    local why
    why=$("$QIMG" info -f qcow2 --output=json "$2" 2> /dev/null | python3 -I -c '
import json, sys
try:
    info = json.load(sys.stdin)
except ValueError:
    info = None
if not isinstance(info, dict):
    print("qemu-img info gave no readable answer")
    sys.exit()
if info.get("snapshots"):
    print("%d internal snapshot(s), which the conversion to raw does not read" % len(info["snapshots"]))
if info.get("backing-filename") or info.get("full-backing-filename"):
    print("a backing file, which is not in the kit and not scanned")
if ((info.get("format-specific") or {}).get("data") or {}).get("data-file"):
    print("an external data file, which is not in the kit and not scanned")
')
    [ -n "$why" ] || return 0
    printf '%s\n' "$why" | while IFS= read -r w; do echo "   HIT $1: $w"; done
    return 1
}
qcow2_hits yoctoScarthgap/yoctoScarthgap.qcow2 "$TOP/yoctoScarthgap/yoctoScarthgap.qcow2" || die 3 "the secret scan refused the kit (hits above); nothing was zipped"
RAW=$STAGE/rootfs.raw
"$QIMG" convert -f qcow2 -O raw "$TOP/yoctoScarthgap/yoctoScarthgap.qcow2" "$RAW" > /dev/null 2>&1 || die 3 "qemu-img could not read yoctoScarthgap.qcow2"
[ "$(od -An -tx1 -j1080 -N2 "$RAW" | tr -d ' \n')" = 53ef ] || die 3 "the root file system is not an unpartitioned ext4"
HITS=0
for p in $ROOTFS_ABSENT; do
    if debugfs -R "stat $p" "$RAW" 2> /dev/null | grep -q '^Inode:'; then
        echo "   HIT rootfs:$p: present (the sanitised copy must not hold it)"
        HITS=$((HITS + 1))
    fi
done
AK=$(debugfs -R "cat /home/egw/.ssh/authorized_keys" "$RAW" 2> /dev/null | awk 'NF >= 2 && $1 !~ /^#/ { print $1 " " $2 }' | LC_ALL=C sort -u)
if [ "$AK" != "$PUB" ]; then
    echo "   HIT rootfs:/home/egw/.ssh/authorized_keys: does not hold exactly the shipped test key"
    HITS=$((HITS + 1))
fi
# dir_names RAW DIR: the names in folder DIR of the ext4 image RAW, sorted, on one line (the unused
# entries of a preallocated folder such as lost+found, inode 0, are left out).
dir_names() { debugfs -R "ls -p $2" "$1" 2> /dev/null | awk -F/ 'NF >= 6 && $2 != 0 { print $6 }' | LC_ALL=C sort | paste -sd' ' -; }
# Every other disk image of the kit (data.qcow2, the empty data disk; any staged file with the qcow2 magic,
# whatever its name) is read the same way: it must be an unpartitioned ext4 holding nothing but an empty
# lost+found, and its data goes through the pem and env rules below (label and raw file in pairs).
EXTRA=()
n=0
while IFS= read -r -d '' f; do
    rel=${f#"$TOP"/}
    [ "$rel" != yoctoScarthgap/yoctoScarthgap.qcow2 ] || continue
    [ "$(od -An -tx1 -N4 "$f" | tr -d ' \n')" = 514649fb ] || continue
    qcow2_hits "$rel" "$f" || { HITS=$((HITS + 1)); continue; }
    n=$((n + 1))
    xraw=$STAGE/extra-$n.raw
    "$QIMG" convert -f qcow2 -O raw "$f" "$xraw" > /dev/null 2>&1 || die 3 "qemu-img could not read $rel"
    if [ "$(od -An -tx1 -j1080 -N2 "$xraw" | tr -d ' \n')" != 53ef ]; then
        echo "   HIT $rel: not an unpartitioned ext4 file system, so its contents cannot be checked"
        HITS=$((HITS + 1))
    elif [ "$(dir_names "$xraw" /)" != ". .. lost+found" ] || [ "$(dir_names "$xraw" /lost+found)" != ". .." ]; then
        echo "   HIT $rel: the file system holds more than an empty lost+found (an extra disk ships empty)"
        HITS=$((HITS + 1))
    fi
    EXTRA+=("$rel (raw)" "$xraw")
done < <(find "$TOP" -type f -print0 | LC_ALL=C sort -z)
python3 -I - "$TOP" "$ALLOWED_KEY" "$RAW" "${EXTRA[@]}" << 'PY'
"""Secret scan of the staging tree. Rules (the matched text is never printed):
  name  a file or archive member called .env, *.env or .env.*;
  pem   a COMPLETE PEM private-key block: BEGIN line, line break, at least 64 base64 characters, no NUL,
        the END line of the same type (C string literals of ssh binaries have the markers but no body);
  env   a line-start assignment NAME=value with PASSWORD in an upper-case NAME and a value that is not
        a $reference (every file, archive member and the root file system); a line starts after a line
        break or a NUL byte, and in a disk image also on a 1024-byte boundary (a file's first line
        starts a block, whatever ends the block before it);
  text  in the kit's own text files (not inside archives, whose program sources legitimately hold
        'password=None'): any identifier containing 'password' (any case) assigned '=' a value;
  disk  a disk image (qcow2, VMDK, VHDX, VDI) inside an archive or compressed data, or one other than a
        qcow2 among the kit's files: its contents cannot be read here (a qcow2 file of the kit is read
        through qemu-img before this scan).
Archives (.tar, .tar.gz, .tgz) are read member by member, nested image layers included; data that opens
as a tar with no member (an ext4 image starts with 1024 zero bytes, which read as an empty tar) is scanned
as data instead. Compressed data (gzip, xz, bzip2) is opened, never scanned in compressed form, and what it
holds is scanned again. Archives and compression are opened six levels deep; anything still packed below
that, and data this scan cannot open (zstd, or a damaged stream), is a hit, so that the scan fails closed. The allowed test key
must be one OpenSSH private key and nothing after its END line. The raw disk images (the root file system
and any extra disk, given as label/path pairs after it) are read by their data extents (holes skipped)
with the pem and env rules."""
import bz2
import gzip
import io
import lzma
import os
import re
import sys
import tarfile
import zlib

top, allowed, raw = sys.argv[1], sys.argv[2], sys.argv[3]
extra = list(zip(sys.argv[4::2], sys.argv[5::2]))
PEM_BEGIN = re.compile(rb"-----BEGIN ((?:[A-Z0-9]+ )*)PRIVATE KEY-----")
SSH_BEGIN, SSH_END = b"-----BEGIN OPENSSH PRIVATE KEY-----", b"-----END OPENSSH PRIVATE KEY-----"
NOT_B64 = re.compile(rb"[^A-Za-z0-9+/=]")
# The magic bytes of disk image formats: (offset, magic, name).
DISK_MAGIC = ((0, b"QFI\xfb", "qcow2"), (0, b"KDMV", "VMDK"), (0, b"vhdxfile", "VHDX"), (64, b"\x7f\x10\xda\xbe", "VDI"))
ENV_LINE = re.compile(rb"[ \t]*(?:export[ \t]+)?[A-Z][A-Z0-9_]*PASSWORD[A-Z0-9_]*=[\"']?[^\s\x00\"'$]")
TEXT_ASSIGN = re.compile(rb"(?i)(?<![a-z0-9_])[a-z0-9_]*password[a-z0-9_]*[ \t]*=[ \t]*[\"']?[^\s\"'$]")
# How many levels of archives and compression the scan opens, one inside the other; deeper is a hit.
MAX_DEPTH = 6
hits = []


def bad_name(name):
    base = name.rstrip("/").rsplit("/", 1)[-1]
    return base == ".env" or base.startswith(".env.") or base.endswith(".env")


def pem_offsets(data, base=0):
    found = set()
    for m in PEM_BEGIN.finditer(data):
        end = data.find(b"-----END " + m.group(1) + b"PRIVATE KEY-----", m.end(), m.end() + 65536)
        if end < 0:
            continue
        body = data[m.end():end]
        if body[:1] not in (b"\n", b"\r") or b"\x00" in body or len(NOT_B64.sub(b"", body)) < 64:
            continue
        found.add(base + m.start())
    return found


def env_offsets(data, base=0, block=0):
    """The offsets of the env-rule assignments in DATA (read at offset BASE). A line starts after a line
    break or a NUL byte; with BLOCK (a disk image), also on a BLOCK boundary, where a file's data starts
    whatever ends the block before it."""
    found = set()
    i = data.find(b"PASSWORD")
    while i >= 0:
        lo = max(0, i - 512)
        s = max(data.rfind(b"\n", lo, i), data.rfind(b"\x00", lo, i)) + 1
        b = i - (base + i) % block if block else -1
        if (s > 0 or i < 512) and ENV_LINE.match(data, s):
            found.add(base + s)
        elif b >= 0 and ENV_LINE.match(data, b):
            found.add(base + b)
        i = data.find(b"PASSWORD", i + 8)
    return found


def scan_bytes(where, data, text_rule):
    if pem_offsets(data):
        hits.append(f"{where}: pem (a complete private-key block)")
    if env_offsets(data):
        hits.append(f"{where}: env (a PASSWORD assignment with a value)")
    if text_rule and b"\x00" not in data[:8192]:
        lines = sorted({data.count(b"\n", 0, m.start()) + 1 for m in TEXT_ASSIGN.finditer(data)})
        if lines:
            hits.append(f"{where}: text (password assignment on line(s) {', '.join(map(str, lines[:10]))})")


def open_tar(data):
    try:
        return tarfile.open(fileobj=io.BytesIO(data), mode="r:*")
    except (tarfile.TarError, OSError, EOFError, zlib.error, lzma.LZMAError):
        return None


DECOMPRESS = {"gzip": gzip.decompress, "xz": lzma.decompress, "bzip2": bz2.decompress}


def compression(data):
    """The compression of DATA by its magic bytes, or None."""
    if data[:2] == b"\x1f\x8b":
        return "gzip"
    if data[:6] == b"\xfd7zXZ\x00":
        return "xz"
    if data[:3] == b"BZh" and data[4:10] == b"1AY&SY":
        return "bzip2"
    if data[:4] == b"\x28\xb5\x2f\xfd":
        return "zstd"
    return None


def disk_image(data):
    """The disk image format of DATA by its magic bytes, or None."""
    for off, magic, name in DISK_MAGIC:
        if data[off:off + len(magic)] == magic:
            return name
    return None


def scan_data(where, data, depth, text_rule, top=False):
    """Scan DATA (a file or an archive member): a tar is read member by member and compressed data is
    opened first. TOP: DATA is a file of the kit as it is (a qcow2 there was read through qemu-img).
    Returns the number of nested archive members read."""
    kind = compression(data)
    if kind == "zstd":
        hits.append(f"{where}: zstd-compressed data, which this scan cannot open")
        return 0
    if kind or data[257:262] == b"ustar":
        # Fail closed at the depth limit: what is still packed there is not opened, so it is a hit.
        if depth >= MAX_DEPTH:
            hits.append(f"{where}: an archive or compressed data nested more than {MAX_DEPTH} levels deep, which this scan does not open")
            return 0
        nested = open_tar(data)
        if nested is not None:
            with nested:
                count = scan_archive(where, nested, depth + 1)
            if count:
                return count
            # No member: not a tar after all (an ext4 image starts with zero blocks); scanned as data.
    if kind:
        try:
            data = DECOMPRESS[kind](data)
        except (OSError, EOFError, ValueError, zlib.error, lzma.LZMAError):
            hits.append(f"{where}: unreadable {kind} data")
            return 0
        # The opened data is scanned again: it may itself be compressed or an archive.
        return scan_data(where, data, depth + 1, text_rule=False)
    disk = disk_image(data)
    if disk and not (top and disk == "qcow2"):
        hits.append(f"{where}: disk (a {disk} image, whose contents this scan cannot read)")
    scan_bytes(where, data, text_rule)
    return 0


def scan_archive(where, tf, depth=0):
    count = 0
    for m in tf:
        count += 1
        inner = f"{where}!{m.name}"
        if bad_name(m.name):
            hits.append(f"{inner}: name")
        if m.isfile():
            count += scan_data(inner, tf.extractfile(m).read(), depth, text_rule=False)
    return count


files = members = 0
for dirpath, dirnames, filenames in os.walk(top):
    for name in sorted(dirnames + filenames):
        path = os.path.join(dirpath, name)
        rel = os.path.relpath(path, top)
        if os.path.islink(path):
            hits.append(f"{rel}: symbolic link")
        elif bad_name(rel):
            hits.append(f"{rel}: name")
    for name in sorted(filenames):
        path = os.path.join(dirpath, name)
        rel = os.path.relpath(path, top)
        if os.path.islink(path):
            continue
        files += 1
        if rel.endswith((".tar", ".tar.gz", ".tgz")):
            try:
                tf = tarfile.open(path, "r:*")
            except (tarfile.TarError, OSError, EOFError, zlib.error) as exc:
                hits.append(f"{rel}: unreadable archive ({exc.__class__.__name__})")
                continue
            with tf:
                count = scan_archive(rel, tf)
            members += count
            if count:
                continue
            # No member: not a tar after all (an ext4 image starts with zero blocks); scanned as data.
        with open(path, "rb") as fh:
            data = fh.read()
        if rel == allowed:
            # The one private key that ships: it must be what it claims, ONE OpenSSH key (checked against
            # its public half and BUILDINFO.txt before the scan) and nothing after its END line, which
            # would ship unscanned.
            end = data.find(SSH_END)
            if (not data.startswith(SSH_BEGIN) or len(PEM_BEGIN.findall(data)) != 1 or end < 0
                    or data[end + len(SSH_END):].strip()):
                hits.append(f"{rel}: the allowed test key is not one OpenSSH private key alone")
            continue
        members += scan_data(rel, data, 0, text_rule=True, top=True)


def scan_raw(label, path):
    """The pem and env rules over the data extents of the raw disk image PATH; returns the bytes read."""
    scanned = 0
    pem, env = set(), set()
    with open(path, "rb") as fh:
        fd = fh.fileno()
        size = os.fstat(fd).st_size
        pos = 0
        window, overlap = 64 << 20, 128 << 10
        while pos < size:
            try:
                start = os.lseek(fd, pos, os.SEEK_DATA)
                stop = os.lseek(fd, start, os.SEEK_HOLE)
            except OSError:
                break
            off = start
            while off < stop:
                n = min(window + overlap, stop - off)
                fh.seek(off)
                data = fh.read(n)
                pem |= pem_offsets(data, off)
                # 1024: every ext4 block size is a multiple of it
                env |= env_offsets(data, off, 1024)
                scanned += len(data)
                off += window
            pos = stop
    if pem:
        hits.append(f"{label}: pem ({len(pem)} complete private-key block(s))")
    if env:
        hits.append(f"{label}: env ({len(env)} PASSWORD assignment(s) with a value)")
    return scanned


scanned = scan_raw("rootfs (raw)", raw)
scanned_extra = sum(scan_raw(label, path) for label, path in extra)
for h in hits:
    print("   HIT " + h)
print(f"   scanned {files} files, {members} archive members, {scanned} bytes of root file system data, "
      f"{len(extra)} other disk image(s) ({scanned_extra} bytes of data): {len(hits)} hit(s)")
sys.exit(1 if hits else 0)
PY
rc=$?
rm -f "$RAW" "$STAGE"/extra-*.raw
[ "$rc" = 0 ] && [ "$HITS" = 0 ] || die 3 "the secret scan refused the kit (hits above); nothing was zipped"

# --- 7. the zip ------------------------------------------------------------------------------------
echo "== zip"
mkdir -p "$OUT" || die 2 "cannot create $OUT"
python3 -I - "$STAGE" "$NAME" "$ZIP.part" "$DATE" << 'PY' || { rm -f "$ZIP.part"; die 2 "the zip could not be written"; }
import os
import shutil
import stat
import sys
import zipfile

stage, name, out, date = sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4]
when = (int(date[:4]), int(date[4:6]), int(date[6:8]), 0, 0, 0)
root = os.path.join(stage, name)
entries = []
for dirpath, dirnames, filenames in os.walk(root):
    dirnames.sort()
    rel_dir = os.path.relpath(dirpath, stage).replace(os.sep, "/")
    entries.append((rel_dir + "/", dirpath))
    entries.extend((f"{rel_dir}/{f}", os.path.join(dirpath, f)) for f in sorted(filenames))
with zipfile.ZipFile(out, "x", allowZip64=True) as zf:
    for arcname, path in entries:
        mode = os.stat(path).st_mode
        info = zipfile.ZipInfo(arcname, date_time=when)
        info.create_system = 3
        info.external_attr = (stat.S_IFMT(mode) | stat.S_IMODE(mode)) << 16
        if arcname.endswith("/"):
            info.external_attr |= 0x10
            zf.writestr(info, b"")
            continue
        info.compress_type = zipfile.ZIP_DEFLATED
        with open(path, "rb") as src, zf.open(info, "w", force_zip64=os.path.getsize(path) > (1 << 31)) as dst:
            shutil.copyfileobj(src, dst, 1 << 20)
with zipfile.ZipFile(out) as zf:
    bad = zf.testzip()
    if bad:
        print(f"CRC error in {bad}", file=sys.stderr)
        sys.exit(1)
PY
mv "$ZIP.part" "$ZIP" || die 2 "cannot write $ZIP"
(cd "$OUT" && sha256sum "$NAME.zip" > "$NAME.zip.sha256") || die 2 "cannot write $ZIP.sha256"
echo "KIT $NAME: $ZIP ($(stat -c %s "$ZIP") bytes, sha256 $(cut -d' ' -f1 "$ZIP.sha256")) and $ZIP.sha256"
echo "Give both files and the repository to the other PC; there: bash tools/setup/prepare_demo_host.sh --kit <zip>"
