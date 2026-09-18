# Build and boot of the integrated QEMU/TCG profile — capsule of 2026-09-18

**Functional evidence only; sealing is not acceptance.** No gate is accepted,
no claim is supported, the stack was not deployed and nothing was measured.
ARM64 is **emulated** under QEMU/TCG on an x86-64 WSL2 host.

The full record, with the table of attempts and the acceptance results, is
[`2026-09-18-integrated-3209b17/README.md`](2026-09-18-integrated-3209b17/README.md).

| Directory | Source commit | Content |
|---|---|---|
| `2026-09-18-integrated-68f9ae7/` | `68f9ae7` | record of the G1 deploy directory **before** anything was built; the first build, which **failed** in `egw-gateway-image:do_rootfs` (RPM directory-mode conflict on `/etc/sudoers.d`), preserved in `attempt-01-68f9ae7/`; the comparison of the kernel task signatures with G1 |
| `2026-09-18-integrated-03e333e/` | `03e333e` | the successful build (5,556 tasks), the artefact acceptance checks, and the first boot attempt, which **failed before QEMU started** (`runqemu` could not resolve `IMAGE_LINK_NAME`) |
| `2026-09-18-integrated-3209b17/` | `3209b17` | the no-op rebuild, the artefact checks again, two boots with the guest acceptance transcript, the persistence check, the offline SSH host-key record, and the root file system checksum after the boots |
| `2026-09-18-integrated.SHA256SUMS` | — | checksums of the three directory manifests |

Artefacts before the first boot (sha256):

- root file system `egw-gateway-image-qemuarm64.rootfs-20260918120819.ext4`:
  `096e9270114f18ab87abfbcd6719240f5d9dd77c03295a1a72ac12c6be8ce6e6`;
- kernel `Image`: `4457ef38e4cb6b8c2f0061ec504a23666490781ca3b4facd15a588b7a9609037`
  (byte-identical to the sealed G1 `Image`, although its tasks were re-executed:
  see `2026-09-18-integrated-68f9ae7/kernel-sigdiff.do_kernel_metadata.txt`).

After the two boots the root file system is
`038277f4d32449e36a8debca323d171c74fefc0a2e705f26af1ea5649b3d45f9`: `runqemu`
boots the file in place, so the change is expected.

`SHA256SUMS` in this directory covers every file below it except itself.
