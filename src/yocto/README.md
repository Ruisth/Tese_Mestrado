# src/yocto — EGW-OS (Yocto/kas) for gate G1

Reproducible build of `egw-image`, the C2DTA Edge Gateway operating-system
image, for the `qemuarm64` machine with Yocto Project 5.0.x "Scarthgap" (LTS)
and the `kas` build tool. This directory is the platform deliverable of gate
G1 (plan sections 4.3, 5.1, 8 and 9.1 "Plataforma").

> **QEMU is functional-only, never performance.** QEMU runs here validate
> build, boot, systemd, networking and the OCI runtime — nothing else. No
> latency, throughput or resource conclusion may ever be derived from QEMU
> (plan section 5.1). Performance work happens exclusively on the native
> ARM64 cloud VM.

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
│   └── run-qemu.sh              # recorded QEMU boot (runqemu nographic slirp)
├── .gitignore
└── README.md
```

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
meta-virtualization pin has a single online source (the OpenEmbedded Layer
Index; the canonical cgit blocked automated fetches) — confirm it once from
WSL2 before the first build:

```sh
git ls-remote https://git.yoctoproject.org/meta-virtualization scarthgap
```

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
`/mnt/*` and never inside the Nextcloud-synced workspace. `scripts/build.sh`
refuses Windows-backed filesystems.

```sh
# 1. Inside WSL2: clone the repository onto ext4
mkdir -p ~/yocto && cd ~/yocto
git clone /mnt/d/Nextcloud/'Edge Gateway'/Claude egw
cd egw/src/yocto

# 2. Build (checkout of pinned layers + bitbake, fully logged)
./scripts/build.sh

# 3. Boot twice, recorded (gate G1 rule)
./scripts/run-qemu.sh boot1     # run in-guest checks, exit with Ctrl+A x
./scripts/run-qemu.sh boot2
```

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

## Gate G1 acceptance checklist (16/08)

Evidence rule: unlogged runs do not count. Every item below must be backed by
a recorded log (build log, `boot1.log`, `boot2.log`, `/var/log/egw-smoke.log`)
copied into the evidence area and referenced from the claim->evidence matrix.

- [ ] `egw-image` builds cleanly from the pinned manifest (`scripts/build.sh` log).
- [ ] The image boots **twice** in QEMU (`boot1.log`, `boot2.log`).
- [ ] systemd reaches multi-user: `systemctl is-system-running` reports
      `running` (a `degraded` result needs a written justification of the
      failed unit).
- [ ] Networking is up: slirp NIC has a `10.0.2.x` DHCP lease (`ip addr`) and
      `ping -c 3 10.0.2.2` reaches the host-side gateway.
- [ ] The OCI runtime executes a container: `egw-container-smoke.sh` logs
      `PASS` (offline `docker import` path by default, or
      `EGW_SMOKE_ONLINE=1` for `docker run hello-world` when the registry is
      reachable).

## Gate G1 fallback (plan 8.1)

If G1 fails on 16/08: reduce `egw-image` to the minimal system plus the OCI
runtime (drop `egw-container-smoke`, `openssh-sftp-server` and any
non-essential package from `IMAGE_INSTALL`) and move deployment/smoke steps
to an external script executed over the console or ssh. If no functional
image exists by 20/08, escalate per the plan (discuss extension or
reformulation with the advisors).

## Raspberry Pi 5 overlay (documented-only)

A Raspberry Pi 5 configuration (meta-raspberrypi BSP, `machine:
raspberrypi5`) could be described in a separate kas overlay file on top of
this manifest. Per plan 5.1 it would be **documentation only**: it is not
built, not booted and not validated in this project, and no claim about
Raspberry Pi behaviour, compatibility or performance is made or may be
derived from it. `egw-image` intentionally carries nothing Pi-specific.
