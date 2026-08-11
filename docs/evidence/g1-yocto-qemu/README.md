# Gate G1 evidence — Yocto build and QEMU boots

Produced 2026-08-11. **Functional validation only.** Everything here supports
build, boot, systemd, networking and OCI-runtime statements. Nothing here
supports a performance statement: the plan separates the QEMU platform from the
measurement platform, and no timing in these files is reportable.

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

| Boot | Outcome | Clean power down | Checks |
|---|---|---|---|
| `boot1` | pass | yes | 9 of 9 |
| `boot2` | pass | yes | 9 of 9 |

Checks, in order: architecture and release; systemd state after
`is-system-running --wait`; target list showing `multi-user.target` active;
failed units (none); networking with a slirp lease; gateway reachability;
container runtime reporting a server version; the in-image container smoke
test; and recorded smoke diagnostics.

The container smoke test builds a single-layer OCI image from the target's own
BusyBox, imports it, runs a command inside it and removes it — so the runtime
is exercised end to end without any registry access.

## What this evidence does NOT establish

- **It does not close gate G1.** Merging or archiving demonstrates
  implementation and verification; accepting a gate is a separate decision
  recorded in `PROGRESS.md` and in the plan's Annex C.
- These are the **two bring-up boots** the gate asks for. The campaign's five
  QEMU boots are a different, later set, produced under the frozen protocol.
- Nothing here says anything about latency, throughput or resource
  consumption.

## Reproducing

```bash
cd src/yocto
./scripts/build.sh
python3 scripts/boot_check.py boot1
python3 scripts/boot_check.py boot2
```

Requires WSL2 Ubuntu 24.04 with the build tree on ext4; see
`docs/setup/wsl2_ubuntu_yocto.md`. The driver exits non-zero if any required
check fails, so it can be relied on by a caller.

## Integrity

`SHA256SUMS` covers every file in this directory. Verify with:

```bash
sha256sum -c SHA256SUMS
```
