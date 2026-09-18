# Build-and-boot validation of the integrated QEMU/TCG profile — candidate evidence

- Date: 2026-09-18 (all times UTC)
- Status: **candidate evidence, not sealed**. No gate is accepted and no claim
  is supported by this directory. The environment is ARM64 **emulated** under
  QEMU/TCG on an x86-64 WSL2 host: functional evidence only, never native
  ARM64 performance evidence.
- Scope authorised: build and boot only. The six-container stack was **not**
  deployed, no image was loaded, no campaign was run.
- Host: WSL2 Ubuntu 24.04, kernel 6.6.87.2-microsoft-standard-WSL2, 31 GiB,
  kas 5.4. Clone `/home/ruisth/yocto/egw`, build directory
  `src/yocto/build-integrated/`, shared caches `~/yocto-cache`.
- SSH key: `~/.ssh/egw_campaign` (ED25519, created for this validation; no
  existing key was overwritten). Data disk:
  `~/yocto/egw-integrated/egw-data.img` (32 GiB sparse, label `egw-data`,
  created by the wrapper; no existing disk file was overwritten).

## Sequence of attempts (every attempt is preserved)

| # | Source commit | Step | Outcome | Where |
|---|---|---|---|---|
| 1 | `68f9ae7` | build | **failed** in `egw-gateway-image:do_rootfs`: RPM file conflict on `/etc/sudoers.d` between `egw-gateway-config` (0755) and `sudo-lib` (0750) | `../2026-09-18-integrated-68f9ae7/attempt-01-68f9ae7/` |
| 2 | `03e333e` | build | succeeded (5556 tasks; 98 % of wanted sstate objects restored) | `../2026-09-18-integrated-03e333e/` |
| 3 | `03e333e` | boot `integrated-boot-01` | **failed before QEMU started**: `runqemu <image> <machine>` cannot resolve `IMAGE_LINK_NAME` with the pinned runqemu; the root file system was not touched (checksum unchanged) | `../2026-09-18-integrated-03e333e/boot/` |
| 4 | `3209b17` | rebuild | no-op (100 % sstate, 0 missed); artefact checksums identical to attempt 2 | `build-driver.log`, `build/` |
| 5 | `3209b17` | boot `integrated-boot-02` | guest up, SSH after 19 s, all acceptance checks passed, clean power-off (exit 0) | `boot/`, `guest/` |
| 6 | `3209b17` | boot `integrated-boot-03` | persistence verified, clean power-off (exit 0) | `boot/`, `guest/persistence-boot-03.txt` |

Provenance in one line: **image built at `03e333e`; boot wrapper corrected and both boots at
`3209b17`; record in the repository at `e7bd1c2`** (audit report Section 13, LOG #C024).

Commit `3209b17` differs from `03e333e` only in
`src/yocto/scripts/run-qemu-integrated.sh` and the runbook; no build input of
the image changed.

## Artefacts (before the first boot)

See `build/SHA256SUMS.artefacts`. `runqemu` boots the deployed ext4 file in
place, so its checksum identifies the artefact **before its first boot only**;
after `integrated-boot-02` the file has changed (host keys, journal,
`/opt/egw`). Checksum after both boots: `rootfs-after-boots.sha256`. The change is the
expected effect of booting a writable root file system, not tampering.

The kernel `Image` is byte-identical to the G1 `Image`
(`4457ef38…9037`). The kernel tasks were nevertheless re-executed in
`build-integrated/`: meta-virtualization signs the whole `DISTRO_FEATURES`
value into `do_kernel_metadata`, and the profile removes `nfs`
(`../2026-09-18-integrated-68f9ae7/kernel-sigdiff.do_kernel_metadata.txt`).

## Acceptance results

- Artefact checks (runbook 2.3–2.5): `build/artefact-checks.txt` — 0 failed.
- G1 build artefacts untouched: listing and checksums identical to the record
  taken before the first build (`build/g1-deploy-after.*`,
  `g1-after-boots.sha256check.txt`).
- QEMU command line (from `boot/integrated-boot-02.log`): `-machine virt
  -cpu cortex-a76 -smp 4 -m 8192`, kernel `mem=8192M`, forwards
  `127.0.0.1:2222->22` and `127.0.0.1:8883->8883` only, second virtio disk.
- SSH: key login as `egw` (uid 1000, group `docker`) works; `root` login and
  password authentication are refused (`guest/root-login-attempt.txt`,
  `guest/password-login-attempt.txt`); `sudo -n true` works; `visudo -c`
  parses `/etc/sudoers.d/egw`.
- Guest (`guest/guest-checks.txt`): `systemctl is-system-running` = running,
  no failed unit; 6.6.142-yocto-standard aarch64; `MemTotal` 8,204,356 kB;
  4 CPUs, CPU part `0xd0b` with `atomics fphp asimdhp asimdrdm asimddp`;
  `/var/lib/docker` on `/dev/vdb` (ext4, label `egw-data`, 31.2 GiB after
  growfs); Docker 25.0.9, overlay2, cgroup v2, root dir `/var/lib/docker`;
  `docker compose version` = v2.26.0; NTP synchronised; nothing listens on
  port 111.
- Persistence (`guest/persistence-boot-03.txt`): two boots in the journal,
  marker file kept, same data-disk UUID and the same Docker engine id.
  SSH host key: the strict host-key check of the second boot succeeded but its
  success was not saved to a file during the run; the continuity was recorded
  afterwards, offline, in `guest/ssh-hostkey-continuity.txt` (the key stored in
  the image after both boots equals the key presented at the first connection).

## Observations that are not acceptance failures

- `avahi-daemon` listens on UDP 5353 (the `zeroconf` distro feature is still
  enabled). The guest is behind slirp NAT; for a physical gateway this is
  exposure to review.
- Two lines of my first guest transcript report errors caused by the check
  script, not by the image: a wrong path (`/opt/egw/data`; the tree is
  `/opt/egw/deployment/data/events`) and BusyBox `command -v` accepting one
  name only. `guest/guest-checks-supplement.txt` repeats both correctly.
- `systemd-analyze` and the rpm database are not in the image (by design).
- Not exercised: MongoDB 7 start test (runbook 3.5), any container, any
  traffic on 8883.

## Manifests

Each directory has a `SHA256SUMS` that covers every file below it except itself, **including
nested manifests** (`attempt-01-68f9ae7/SHA256SUMS`). `../2026-09-18-integrated.SHA256SUMS`
covers the three directory manifests. No private key, password or token is in these
directories (scan of 2026-09-18: `authorized_keys.in-image.txt` and `boot/known_hosts` hold
public keys only).
