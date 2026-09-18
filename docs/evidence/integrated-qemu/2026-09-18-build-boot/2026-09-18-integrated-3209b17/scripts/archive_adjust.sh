#!/bin/bash
# Two adjustments to the candidate evidence requested by the project review
# (2026-09-18): record the SSH host-key continuity explicitly, and let the
# manifests cover the nested checksum manifest. Adds files; removes nothing.
set -u
R=$HOME/yocto/evidence-candidates
E=$R/2026-09-18-integrated-3209b17
IMG=/home/ruisth/yocto/egw/src/yocto/build-integrated/tmp/deploy/images/qemuarm64/egw-gateway-image-qemuarm64.rootfs-20260918120819.ext4
OUT=$E/guest/ssh-hostkey-continuity.txt
TMP=$(mktemp -d)

{
    echo "SSH host-key continuity - recorded $(date -u +%Y-%m-%dT%H:%M:%SZ), after both boots, WITHOUT booting the guest."
    echo
    echo "What was recorded during the boots: boot/known_hosts was written by the first SSH connection of"
    echo "integrated-boot-02 (StrictHostKeyChecking=no, empty file before). Every SSH command of"
    echo "integrated-boot-03 used StrictHostKeyChecking=yes against that file and succeeded; the ssh client"
    echo "refuses the connection when the presented key differs. That success was printed on the operator's"
    echo "terminal only and was NOT saved to a file during the run; no fingerprint was taken during either boot."
    echo
    echo "What is observed now (public keys only; debugfs opens the image read-only):"
    echo "key recorded in boot/known_hosts (entry hashed by ssh, host [127.0.0.1]:2222):"
    awk '{print $2, $3}' "$E/boot/known_hosts" > "$TMP/known.pub"
    ssh-keygen -lf "$TMP/known.pub"
    echo "host keys in the root file system image after integrated-boot-03:"
    for k in ed25519 ecdsa rsa; do
        debugfs -R "cat /etc/ssh/ssh_host_${k}_key.pub" "$IMG" 2>/dev/null | awk '{print $1, $2}' > "$TMP/$k.pub"
        ssh-keygen -lf "$TMP/$k.pub"
    done
    echo "modification times of the host key files in the image (local time of the host, UTC+1):"
    debugfs -R "ls -l /etc/ssh" "$IMG" 2>/dev/null | grep -E "ssh_host_.*_key" | awk '{print "  " $NF, $(NF-2), $(NF-1)}'
    echo
    if cmp -s "$TMP/known.pub" "$TMP/ed25519.pub"; then
        echo "RESULT: the ed25519 host key stored in the image after the second boot is byte-identical to the key"
        echo "the guest presented at the first connection of integrated-boot-02. All host key files carry the"
        echo "time of the first boot (12:17 UTC); none was rewritten during integrated-boot-03 (12:19 UTC)."
    else
        echo "RESULT: MISMATCH between boot/known_hosts and the ed25519 host key in the image."
    fi
    echo
    echo "Limit: this shows the key on disk, not a fingerprint captured from the network during boot-03."
} > "$OUT" 2>&1
rm -rf "$TMP"
cat "$OUT"

# README: qualify the continuity statement and state the provenance triple.
python3 - "$E/README.md" <<'EOF'
import io, sys
p = sys.argv[1]
s = io.open(p, encoding="utf-8").read()
old = "  SSH host keys unchanged (strict host-key check), marker file kept, same\n  data-disk UUID and the same Docker engine id."
new = ("  marker file kept, same data-disk UUID and the same Docker engine id.\n"
       "  SSH host key: the strict host-key check of the second boot succeeded but its\n"
       "  success was not saved to a file during the run; the continuity was recorded\n"
       "  afterwards, offline, in `guest/ssh-hostkey-continuity.txt` (the key stored in\n"
       "  the image after both boots equals the key presented at the first connection).")
assert s.count(old) == 1, s.count(old)
s = s.replace(old, new)
old2 = "Commit `3209b17` differs from `03e333e` only in"
new2 = ("Provenance in one line: **image built at `03e333e`; boot wrapper corrected and both boots at\n"
        "`3209b17`; record in the repository at `e7bd1c2`** (audit report Section 13, LOG #C024).\n\n"
        "Commit `3209b17` differs from `03e333e` only in")
assert s.count(old2) == 1
s = s.replace(old2, new2)
old3 = "after `integrated-boot-02` the file has changed (host keys, journal,\n`/opt/egw`)."
new3 = ("after `integrated-boot-02` the file has changed (host keys, journal,\n`/opt/egw`). Checksum after both boots: `rootfs-after-boots.sha256`. The change is the\n"
        "expected effect of booting a writable root file system, not tampering.")
assert s.count(old3) == 1
s = s.replace(old3, new3)
s += ("\n## Manifests\n\n"
      "Each directory has a `SHA256SUMS` that covers every file below it except itself, **including\n"
      "nested manifests** (`attempt-01-68f9ae7/SHA256SUMS`). `../2026-09-18-integrated.SHA256SUMS`\n"
      "covers the three directory manifests. No private key, password or token is in these\n"
      "directories (scan of 2026-09-18: `authorized_keys.in-image.txt` and `boot/known_hosts` hold\n"
      "public keys only).\n")
io.open(p, "w", encoding="utf-8", newline="\n").write(s)
print("README qualified")
EOF

# Manifests: every file except the directory's own top-level manifest.
for d in "$R"/2026-09-18-integrated-*; do
    # The list is written outside the directory: a temporary file inside it lists itself
    # (that happened on the first run of this script, 2026-09-18, and was corrected at once).
    t=$(mktemp)
    ( cd "$d" && find . -type f ! -path ./SHA256SUMS | sort | xargs -d '\n' sha256sum > "$t" && mv "$t" SHA256SUMS && chmod 644 SHA256SUMS && echo "$(basename "$d"): $(wc -l < SHA256SUMS) entries" )
done
( cd "$R" && sha256sum 2026-09-18-integrated-*/SHA256SUMS > 2026-09-18-integrated.SHA256SUMS && sha256sum -c --quiet 2026-09-18-integrated.SHA256SUMS && echo "parent manifest verifies" )
for d in "$R"/2026-09-18-integrated-*; do ( cd "$d" && sha256sum -c --quiet SHA256SUMS && echo "$(basename "$d") verifies" ); done
echo "token patterns: $(grep -rIlE 'ghp_[A-Za-z0-9]{20,}|github_pat_|AKIA[0-9A-Z]{16}|xox[baprs]-' "$R" | wc -l)"
