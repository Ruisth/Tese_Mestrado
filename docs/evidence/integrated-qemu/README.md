# Integrated QEMU/TCG gateway profile — sealed technical evidence (2026-09-18)

Two capsules recorded on 2026-09-18 on the x86-64 WSL2 workstation with the
integrated profile of pull request #28 (`feat/integrated-qemu-profile`):

| Capsule | What it records |
|---|---|
| [`2026-09-18-build-boot/`](2026-09-18-build-boot/README.md) | one failed and one successful build of `egw-gateway-image`, one boot attempt that failed before QEMU started, a no-op rebuild and two successful boots with every build and guest acceptance check passing |
| [`2026-09-18-mongodb7-isolated/`](2026-09-18-mongodb7-isolated/README.md) | an isolated MongoDB 7.0.39 container on that guest: start, write and read, restart, recreation, persistence across a guest power cycle |

**Sealing is not acceptance.** These capsules archive what was observed so
that it can be verified later. They accept no gate and support no claim of the
dissertation. The six-container stack was **not** deployed, nothing was
measured, and the environment is ARM64 **emulated** under QEMU/TCG on an x86-64
host: functional evidence only, never native ARM64 performance evidence. Any
timing in the transcripts is informational.

## Provenance

- Image built at commit `03e333e4ac5f726373d5b56350b46c0b30e3609b`; boot
  wrapper corrected and every boot made at commit
  `3209b17e6483e4bcde2776898edcbfbe15c08be0` (it differs from `03e333e` only in
  `src/yocto/scripts/run-qemu-integrated.sh` and the runbook; the rebuild was a
  no-op with identical checksums); the first, failed build was made at
  `68f9ae7cbd8244f94277503d2a81bdacc03f0364`. All three commits belong to pull
  request #28, which records the run in its audit report (Section 13) and in
  its LOG entry.
- Failed attempts are part of the record and are kept next to the successful
  ones.
- Root file system checksums are recorded **before the first boot**
  (`096e9270…e6e6`), **after the two boots** (`038277f4…45f9`) and after the
  MongoDB test (`325bec69…b85d`). `runqemu` boots the deployed ext4 file in
  place, so it changes with use (host keys, journal, `/opt/egw`); that is the
  expected effect of a writable root file system, not tampering. The kernel
  `Image` is byte-identical to the sealed G1 `Image` (`4457ef38…9037`).
- The sealed G1 build tree was compared with a record taken before the first
  build, after the builds, after the boots and after the MongoDB test: listing
  and checksums are unchanged.
- SSH host-key continuity across the boots was not saved to a file during the
  run; it was recorded afterwards, offline, from the root file system image
  (`2026-09-18-build-boot/2026-09-18-integrated-3209b17/guest/ssh-hostkey-continuity.txt`).

## Layout and verification

The directories are byte-for-byte copies of the candidate evidence kept in the
WSL2 home under `~/yocto/evidence-candidates/`; the names of the inner
directories are the original ones, so a path such as
`../2026-09-18-integrated-3209b17/` inside the MongoDB capsule's README means
`2026-09-18-build-boot/2026-09-18-integrated-3209b17/` here.

Every `SHA256SUMS` file below this directory is verified by
`python tools/ci/verify_evidence.py` (continuous integration, job *contracts,
evidence and links*). Each capsule has a top-level `SHA256SUMS` that covers
every file of the capsule except itself, including the nested manifests.
`.gitattributes` stores everything under this directory without text
conversion: the console transcripts contain the carriage returns and escape
sequences of the pseudo-terminal, which are part of the record. The shell
scripts kept here are captured material and are excluded from ShellCheck.

No private key, password or token is stored here (scan of 2026-09-18). The
files `authorized_keys.in-image.txt` and `known_hosts` hold **public** keys of
a key pair and a guest created for this validation only.
