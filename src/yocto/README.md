# src/yocto — EGW-OS (Yocto/kas) for gate G1

Versioned, repeatable same-operator build of `egw-image`, the C2DTA Edge
Gateway operating-system image, for the `qemuarm64` machine with Yocto Project
5.0.x "Scarthgap" (LTS) and the `kas` build tool. Independent-operator
reconstruction remains decision D006, so this directory makes no stronger
reproducibility claim. It is the platform deliverable of gate G1 (plan
sections 4.3, 5.1, 8 and 9.1 "Plataforma").

> **QEMU is functional-only, never performance.** QEMU runs here validate
> build, boot, systemd, networking and the OCI runtime — nothing else. No
> latency, throughput or resource conclusion may ever be derived from QEMU, and
> a QEMU result never supports a performance or security statement (plan
> section 5.1). Measurement happens exclusively on a non-burstable native-ARM64
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

# 3. Run five strict unattended boots with a fresh identity prefix
g1_campaign="qemu-g1-$(date -u +%Y%m%dT%H%M%SZ)"
egw_boot_rc=0
for run in 01 02 03 04 05; do
    python3 scripts/boot_check.py "${g1_campaign}-${run}" || egw_boot_rc=$?
done
(exit "$egw_boot_rc")
```

Step 3 is the **current acceptance path of record**. Each run writes
`<name>.log` (the complete serial session) and `<name>.result.json`
(per-check verdicts and the overall outcome) under `EGW_LOG_DIR`, default
`~/yocto/logs`. The driver exits non-zero if any required assertion fails, so
a caller can rely on its status. The preliminary sealed evidence in
`docs/evidence/g1-yocto-qemu/` used the same driver for two bring-up boots;
those historical boots are preserved but do not replace the five-run campaign.
The 2026-08-14 execution likewise preserves the failed `qemu-boot-01` attempt
and uses five new `qemu-g1r2-01` to `qemu-g1r2-05` identities after the driver
fix. Never reuse a prior identity. The accumulator lets every predefined boot
identity leave its evidence and still returns non-zero after the loop when any
one of the five boots failed.

`./scripts/run-qemu.sh boot1` remains available as the **interactive
alternative**: it boots the same image with the console tee'd to a log, and the
in-guest checks are then typed by hand (exit with Ctrl+A, then x). Use it to
explore the running image or to diagnose a failure. It is not the path to the
G1 evidence — a hand-driven session is not independently repeatable by a
reader, which is why the sealed boots were driven by `boot_check.py`.

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

## Gate G1 acceptance checklist (plan v1.1, 13–18 August)

Evidence rule: unlogged runs do not count. Every item below must be backed by a
recorded log copied into the evidence area and referenced from the
claim->evidence matrix. There are two immutable scopes:

- the [2026-08-11 preliminary seal](../../docs/evidence/g1-yocto-qemu/README.md)
  records the build at `5770c0a` and two bring-up boots driven at `32f6604`;
- the [2026-08-14 strict seal](../../docs/evidence/g1-yocto-qemu/2026-08-14-clean-build-f0e19d5/README.md)
  records the clean-checkout build at `f0e19d5`, the preserved failed
  instrumentation attempt and five fresh passes driven at `9fe38ff`.

Each scope has its own `SHA256SUMS`, and both verify from a clean clone.

**Evidence — produced and sealed:**

- [x] A new checkout, layer tree and build directory at `f0e19d5` completed all
      5,715 BitBake tasks successfully. External downloads/sstate were shared
      by design; 2,261 tasks did not need rerun, so this is not described as a
      cold-cache build. The rootfs and kernel SHA-256 values, 639-package
      manifest and full logs are in the strict seal.
- [x] Five fresh QEMU boots (`qemu-g1r2-01` to `qemu-g1r2-05`) were driven
      unattended at `9fe38ff`; each passed 7 of 7 required assertions, recorded
      2 of 2 supplementary observations, reached the console and powered down
      cleanly. The preceding `qemu-boot-01` remains an outcome `fail` and is not
      counted: its guest output was correct, but the old predicate rejected the
      PTY carriage returns. PR #18 fixed the predicate before the five reruns.
- [x] Architecture and release are as pinned: the guest reports `aarch64`
      (required assertion `kernel_and_release`).
- [x] systemd reaches multi-user: `systemctl is-system-running --wait` and the
      target list showing `multi-user.target` active (required assertions
      `systemd_state` and `systemd_targets`). All five strict boots reported
      exactly `running`; `degraded` fails. `failed_units` is a seventh required
      assertion and accepts only zero failed units.
- [x] Networking is up: the slirp NIC holds a `10.0.2.x` DHCP lease (required
      assertion `networking`). Host-gateway reachability (`ping -c 3 10.0.2.2`)
      is recorded as a **supplementary observation** and asserts nothing.
- [x] The OCI runtime is live and executes a container: `docker info` reports a
      server version, and `egw-container-smoke.sh` exits 0 (required assertions
      `container_runtime` and `container_smoke`; the offline `docker import`
      path by default, or `EGW_SMOKE_ONLINE=1` for `docker run hello-world`
      when the registry is reachable).

**Gate decision:**

- [x] **G1 accepted, 2026-08-14.** Producing and sealing the evidence above
      demonstrates implementation and verification; accepting the gate was a
      separate decision, recorded in
      `docs/governance/gate_decision_log.md` with a dated decision record;
      `PROGRESS.md` mirrors the current operational state.
      The acceptance covers the functional platform layer only and validated
      no claim; none of the 15 claims is accepted. C01 now
      has a same-operator clean-checkout build but remains partial pending D006
      and formal claim admission (a separate decision from the gate). C02 has the strict five-boot G1 set, but the later
      predefined `data-v1` identities remain separate unless a dated protocol
      decision explicitly admits this set.

## Gate G1 cut rule (plan v1.1)

The clean identified build and five passing strict boots were produced and
sealed on 2026-08-14, inside the 18 August window. The absence-of-evidence cut
condition therefore did not trigger, and the formal decision followed the same
day: **G1 was accepted on 2026-08-14** (recorded in
`docs/governance/gate_decision_log.md`, functional scope only); D006 is
separate and still pending. Any future failure or scope
reduction must preserve its evidence and pass through the normal review/CI path
without weakening the strict systemd, failed-unit or container assertions.

## Integrated QEMU/TCG gateway profile (unbuilt proposal, separate from G1)

A second kas profile prepares the image that is meant to host the six-container
digital-twin stack **inside** the Yocto guest. It follows the student-directed
integrated-Yocto target; the plan revision that describes that target is not
yet published on `dev`, so this profile accepts no gate and supports no claim.
**Nothing in it has been built or booted.**

| File | Role |
|---|---|
| `kas/egw-qemuarm64-integrated.yml` (+ `.lock.yml`) | Same machine, layers and pinned commits as G1; target `egw-gateway-image`; runqemu profile `-cpu cortex-a76`, `-m 8192`, `-smp 4`, host forwards 2222→22 and 8883→8883; builds in `build-integrated/` through `KAS_BUILD_DIR`, never in `build/` |
| `meta-egw/recipes-core/images/egw-gateway-image.bb` | Campaign image: Docker with the Compose V2 plugin, `curl`, `sudo`, key-only SSH for the operator `egw` (uid 1000), persistent journal, no `debug-tweaks`; the build fails without `EGW_AUTHORIZED_KEYS_FILE` |
| `meta-egw/recipes-core/images/egw-gateway-image-dev.bb` | Bring-up variant for QEMU only (adds `debug-tweaks` and the G1 smoke package); never evidence |
| `meta-egw/recipes-core/egw-gateway-config/` | journald, timesyncd and sshd drop-ins, `daemon.json`, sudoers rule, tmpfiles entries for `/opt/egw`, and the docker.service drop-in that requires the data disk |
| `scripts/build-profile.sh` | `kas checkout` + `kas build` of a non-G1 profile in its own build directory; refuses `build/` |
| `scripts/run-qemu-integrated.sh` | Boots the integrated image with a persistent ext4 data disk (label `egw-data`, outside the clone) mounted on `/var/lib/docker` |

The G1 inputs (`kas/egw-qemuarm64.yml`, its lock file, `egw-image.bb`,
`egw-base-config`, `egw-container-smoke`, `scripts/build.sh`, `scripts/run-qemu.sh`,
`scripts/boot_check.py`) are byte-identical, so the sealed G1 evidence stays
reproducible from its own manifest. This environment is ARM64 **emulated** on an
x86-64 host: whatever it produces is functional and integration evidence, never
native ARM64 performance evidence. Procedure:
[`docs/setup/qemu_integrated_gateway.md`](../../docs/setup/qemu_integrated_gateway.md);
rationale and package audit:
[`docs/reviews/2026-09-17-egw-image-audit.md`](../../docs/reviews/2026-09-17-egw-image-audit.md).

## Raspberry Pi 5 overlay (documented-only)

A Raspberry Pi 5 configuration (meta-raspberrypi BSP, `machine:
raspberrypi5`) could be described in a separate kas overlay file on top of
this manifest. Per plan 5.1 it would be **documentation only**: it is not
built, not booted and not validated in this project, and no claim about
Raspberry Pi behaviour, compatibility or performance is made or may be
derived from it. `egw-image` intentionally carries nothing Pi-specific.
