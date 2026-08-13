# Gate G1 evidence — Yocto build and QEMU boots

The files immediately in this directory were produced on 2026-08-11 and are
the sealed preliminary build/two-boot evidence described below. The later
clean-checkout build and strict five-boot set are preserved under
[`2026-08-14-clean-build-f0e19d5/`](2026-08-14-clean-build-f0e19d5/README.md),
with their own provenance record and checksum scope.

**Functional validation only.** Everything here supports build, boot, systemd,
networking and OCI-runtime statements. Nothing here supports a performance
statement: the plan separates the QEMU platform from the measurement platform,
and no timing in these files is reportable.

## What was produced

| Artefact | Value |
|---|---|
| Image | `egw-image-qemuarm64.rootfs.ext4`, sha256 `9e9b8e8ca8fd85889c322c0032fdaac1787410da86eba274bf0489d8ce535005` |
| Kernel | `Image` (linux-yocto 6.6.142), sha256 `4457ef38e4cb6b8c2f0061ec504a23666490781ca3b4facd15a588b7a9609037` |
| Packages in the image | 639, listed in `image-packages.manifest` |
| Distribution | Poky 5.0.19 (scarthgap), target `qemuarm64`, `aarch64` |
| Layer revisions | pinned in `src/yocto/kas/egw-qemuarm64.yml`; resolution recorded in `kas-checkout.log` |

## Boots

Both boots were driven by `src/yocto/scripts/boot_check.py`, which attaches to
the serial console, logs in, runs a fixed list of checks and decides the
outcome from the output. The full console session and the per-check verdicts
are archived here.

| Boot | Outcome | Required assertions | Supplementary observations | Clean power down |
|---|---|---|---|---|
| `boot1` | pass | 6 of 6 passed | 3 of 3 recorded | confirmed |
| `boot2` | pass | 6 of 6 passed | 3 of 3 recorded | confirmed |

**Required assertions** are what was verified: architecture and release;
systemd state after `is-system-running --wait`; the target list showing
`multi-user.target` active; networking with a slirp lease; the container
runtime reporting a server version; and the in-image container smoke test.

**Supplementary observations** are recorded but assert nothing, and are
deliberately not counted as verification: the failed-unit list (empty in both
boots), gateway reachability, and the smoke diagnostics. An earlier version of
this file said "9 of 9 checks", which counted the observations as if they were
assertions; that overstated what had been verified.

One observation is worth naming: the interpreter probe reports
`INTERP=unavailable` because neither `strings` nor the `tr` fallback is usable
in this image, which carries no binutils. It reports that plainly rather than a
fabricated value. The dynamic loader is instead evidenced by the smoke test
succeeding, which cannot happen unless the loader resolves inside the
container.

The container smoke test builds a single-layer OCI image from the target's own
BusyBox, imports it, runs a command inside it and removes it — so the runtime
is exercised end to end without any registry access.

## What this evidence does NOT establish

- **It does not close gate G1.** Merging or archiving demonstrates
  implementation and verification; accepting a gate is a separate decision
  recorded in `PROGRESS.md` and in the plan's Annex C.
- These are the historical **two bring-up boots**. A clean build plus five new
  strict boots was produced on 2026-08-14 and has a separate nested seal. The
  later `data-v1` experimental identities remain distinct unless a dated
  protocol decision explicitly admits that set.
- Nothing here says anything about latency, throughput or resource
  consumption.

## Historical reproduction command

```bash
cd src/yocto
./scripts/build.sh
python3 scripts/boot_check.py boot1
python3 scripts/boot_check.py boot2
```

Requires WSL2 Ubuntu 24.04 with the build tree on ext4; see
`docs/setup/wsl2_ubuntu_yocto.md`. The current five-boot acceptance command and
strict seven-assertion driver are documented in `src/yocto/README.md`. The
driver exits non-zero if any required check fails, so it can be relied on by a
caller.

## Integrity

The top-level `SHA256SUMS` covers the immediate 2026-08-11 evidence files. The
2026-08-14 capsule has its own `SHA256SUMS`; neither seal silently absorbs the
other. Verify each from its corresponding directory with:

```bash
sha256sum -c SHA256SUMS
```
