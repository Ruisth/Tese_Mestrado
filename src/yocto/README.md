# src/yocto — EGW-OS (Yocto/kas) for gate G1

Reproducible build of `egw-image`, the C2DTA Edge Gateway operating-system
image, for the `qemuarm64` machine with Yocto Project 5.0.x "Scarthgap" (LTS)
and the `kas` build tool. This directory is the platform deliverable of gate
G1 (plan sections 4.3, 5.1, 8 and 9.1 "Plataforma").

> **QEMU is functional-only, never performance.** QEMU runs here validate
> build, boot, systemd, networking and the OCI runtime — nothing else. No
> latency, throughput or resource conclusion may ever be derived from QEMU, and
> a QEMU result never supports a performance or security statement (plan
> section 5.1). Measurement happens exclusively on a dedicated native-ARM64
> instance, the third tier of the platform model — which **does not exist yet**
> (see [`docs/setup/vm_arm64_hetzner.md`](../../docs/setup/vm_arm64_hetzner.md));
> a burstable ARM64 instance is admitted for functional integration only and
> never for numbers.

## Layout

```
src/yocto/
├── kas/
│   ├── egw-qemuarm64.yml        # kas manifest (machine/distro/target, pinned layers)
│   └── egw-qemuarm64.lock.yml   # kas lock file (exact commits; wins over branches)
├── meta-egw/                    # local Yocto layer
│   ├── conf/layer.conf
│   └── recipes-core/
│       ├── images/egw-image.bb              # the image recipe
│       ├── egw-base-config/                 # networkd DHCP + docker.service enablement
│       └── egw-container-smoke/             # gate-G1 container smoke test
├── scripts/
│   ├── build.sh                 # kas checkout + build with evidence logging
│   ├── boot_check.py            # unattended boot driver — PATH OF RECORD for the G1 boots
│   └── run-qemu.sh              # interactive QEMU boot (runqemu nographic slirp)
├── .gitignore
└── README.md
```

`boot_check.py` is what produced the sealed G1 boot evidence: it attaches to
the serial console, logs in, runs a fixed list of checks, records the whole
session and decides pass or fail from the command output, exiting non-zero if
any required assertion fails. Its check list separates **required assertions**
(currently 7, which decide the outcome) from **supplementary observations**
(currently 2, recorded for diagnosis, which assert nothing and are never
counted as verification). The sealed 2026-08-11 evidence used the earlier
6/3 classification at commit `32f6604`; those immutable result files are not
retroactively relabelled. The current driver promotes `failed_units` to a
required zero-failures assertion.
Its verdict logic has its own test file, `src/tests/test_yocto_boot_check.py`.

## What is in the image

`egw-image` (see `meta-egw/recipes-core/images/egw-image.bb`) is deliberately
minimal: systemd as init, systemd-networkd with DHCP on wired interfaces,
OpenSSH server, CA certificates, the moby/docker OCI runtime from
meta-virtualization (plus the container kernel modules), and the two local
packages `egw-base-config` and `egw-container-smoke`. It contains **no
Raspberry Pi specific packages** — no `hwcodecs`, no Pi firmware (plan 5.1).

`IMAGE_FEATURES` includes `debug-tweaks` (passwordless root on the console)
strictly for the G1 bring-up in QEMU; never describe this image as hardened.

## Pinned revisions

Plan 4.3 forbids building from moving branch HEADs. The manifest pins:

| Repo | Ref | Commit |
|---|---|---|
| poky | tag `yocto-5.0.19` | `bb98354685781296e3b3737e7762412100f359c2` |
| meta-openembedded | branch `scarthgap` | `ef3df29f2cfca6a9513b51ebcdccf82b6c8a836f` |
| meta-virtualization | branch `scarthgap` | `0d9fb7fef86c5cbc177045c7b86bc71948f8657d` |

Verification sources and dates are recorded as comments in
`kas/egw-qemuarm64.yml` (all checked online on 2026-08-07). The
meta-virtualization pin had a single online source at pinning time (the
OpenEmbedded Layer Index; the canonical cgit blocked automated fetches), so it
needed one confirmation from WSL2 before the first build.

**That confirmation is done.** The build resolved the pin on real
infrastructure: `docs/evidence/g1-yocto-qemu/kas-checkout.log` records
`Repository meta-virtualization checked out to`
`0d9fb7fef86c5cbc177045c7b86bc71948f8657d`, the commit pinned above, and the
image was then built from that checkout. No further manual `git ls-remote`
check is required for this pin; the equivalent confirmation is owed again only
after a deliberate layer update.

Note that `kas/egw-qemuarm64.lock.yml` still carries the pre-build instruction
to confirm this pin by hand — that comment is now stale.

`kas checkout` fails loudly if a pinned commit does not exist. After any
deliberate layer update, re-lock with:

```sh
kas dump --lock --inplace kas/egw-qemuarm64.yml
```

## Build procedure (WSL2 Ubuntu 24.04)

Environment setup — WSL2 install, disk sizing, `.wslconfig`, host packages,
kas install — is documented step by step in
[`docs/setup/wsl2_ubuntu_yocto.md`](../../docs/setup/wsl2_ubuntu_yocto.md).
The authoritative manifest path is `src/yocto/kas/egw-qemuarm64.yml`
(wherever that guide refers to the kas manifest generically).

Hard rule (plan 5.1): builds run on the WSL2 **ext4** filesystem, never on
`/mnt/*` (the workspace itself lives on NTFS). `scripts/build.sh`
refuses Windows-backed filesystems.

```sh
# 1. Inside WSL2: clone the repository onto ext4
mkdir -p ~/yocto && cd ~/yocto
git clone "/mnt/c/Users/ruimf/Documents/Projeto Mestrado/Claude" egw
cd egw/src/yocto

# 2. Build (checkout of pinned layers + bitbake, fully logged)
./scripts/build.sh

# 3. Boot twice, unattended and recorded (gate G1 rule) — path of record
python3 scripts/boot_check.py boot1
python3 scripts/boot_check.py boot2
```

Step 3 is the **reproduction path of record**: the sealed evidence in
`docs/evidence/g1-yocto-qemu/` was produced by exactly these two commands, and
nothing else reproduces it. Each run writes `<name>.log` (the complete serial
session) and `<name>.result.json` (per-check verdicts and the overall outcome)
under `EGW_LOG_DIR`, default `~/yocto/logs`. The driver exits non-zero if any
required assertion fails, so a caller can rely on its status.

`./scripts/run-qemu.sh boot1` remains available as the **interactive
alternative**: it boots the same image with the console tee'd to a log, and the
in-guest checks are then typed by hand (exit with Ctrl+A, then x). Use it to
explore the running image or to diagnose a failure. It is not the path to the
G1 evidence — a hand-driven session is not reproducible by a reader, which is
why the sealed boots were driven by `boot_check.py`.

Both paths validate build, boot, systemd, networking and the OCI runtime only.
Neither produces a number that may appear in the thesis.

Layer checkouts (`poky/`, `meta-openembedded/`, `meta-virtualization/`) and
the `build/` tree are created inside `src/yocto/` of the ext4 clone and are
git-ignored. Downloads and sstate live outside the checkout
(`~/yocto-cache/`, see `local_conf_header` in the manifest) so re-clones stay
cheap.

**Build duration:** the first build bootstraps a cross toolchain and compiles
every package from source; it takes a long time and depends entirely on the
host CPU, RAM and disk. No specific duration is claimed here — record the
actual duration from the timestamped build log as evidence. Subsequent builds
reuse the shared sstate cache and are much faster.

## Gate G1 acceptance checklist (2026-08-16)

Evidence rule: unlogged runs do not count. Every item below must be backed by
a recorded log copied into the evidence area and referenced from the
claim->evidence matrix. All evidence items were produced on 2026-08-11 and are
sealed in [`docs/evidence/g1-yocto-qemu/`](../../docs/evidence/g1-yocto-qemu/)
(`SHA256SUMS` verifies from a clean clone). The image was built from the tree
at commit `5770c0a`; both boots were driven by `scripts/boot_check.py` at
commit `32f6604`.

**Evidence — produced and sealed:**

- [x] `egw-image` builds cleanly from the pinned manifest — 5715 BitBake tasks,
      all successful; rootfs 382 MiB, kernel 23 MiB, 639 packages
      (`kas-checkout.log`, `kas-build.log`, `image-packages.manifest`).
- [x] The image boots **twice** in QEMU, both driven unattended by
      `scripts/boot_check.py`, each with 6 of 6 required assertions passed,
      3 of 3 supplementary observations recorded and a clean power-down
      confirmed (`boot1.log`, `boot1.result.json`, `boot2.log`,
      `boot2.result.json`).
- [x] Architecture and release are as pinned: the guest reports `aarch64`
      (required assertion `kernel_and_release`).
- [x] systemd reaches multi-user: `systemctl is-system-running --wait` and the
      target list showing `multi-user.target` active (required assertions
      `systemd_state` and `systemd_targets`). Both sealed boots reported
      exactly `running` and an empty failed-unit listing. Current reruns are
      stricter: `degraded` fails and `failed_units` is a required assertion
      that accepts only zero failed units.
- [x] Networking is up: the slirp NIC holds a `10.0.2.x` DHCP lease (required
      assertion `networking`). Host-gateway reachability (`ping -c 3 10.0.2.2`)
      is recorded as a **supplementary observation** and asserts nothing.
- [x] The OCI runtime is live and executes a container: `docker info` reports a
      server version, and `egw-container-smoke.sh` exits 0 (required assertions
      `container_runtime` and `container_smoke`; the offline `docker import`
      path by default, or `EGW_SMOKE_ONLINE=1` for `docker run hello-world`
      when the registry is reachable).

**Gate decision — genuinely pending:**

- [ ] **G1 accepted.** Not ticked. Producing and sealing the evidence above
      demonstrates implementation and verification; accepting the gate is a
      separate decision, recorded in `PROGRESS.md` and in Annex C of the plan.
      No gate has been accepted, and none of the 15 claims is accepted: the
      build evidence moved C01 to partial (a rebuild from an independent clean
      checkout is pending and belongs to G4) and the boots gave C02 bring-up
      evidence (the campaign's five `qemu_boots` runs remain).

## Gate G1 fallback (plan 8.1)

Not invoked: a functional image exists and both bring-up boots passed. Retained
because the gate decision is still open. If G1 fails on 2026-08-16: reduce
`egw-image` to the minimal system plus the OCI runtime (drop
`egw-container-smoke`, `openssh-sftp-server` and any non-essential package from
`IMAGE_INSTALL`) and move deployment/smoke steps to an external script executed
over the console or ssh. If no functional image exists by 2026-08-20, escalate
per the plan (discuss extension or reformulation with the advisors).

## Raspberry Pi 5 overlay (documented-only)

A Raspberry Pi 5 configuration (meta-raspberrypi BSP, `machine:
raspberrypi5`) could be described in a separate kas overlay file on top of
this manifest. Per plan 5.1 it would be **documentation only**: it is not
built, not booted and not validated in this project, and no claim about
Raspberry Pi behaviour, compatibility or performance is made or may be
derived from it. `egw-image` intentionally carries nothing Pi-specific.
