# Integrated QEMU/TCG gateway — executable runbook

**Status (2026-09-18):** proposal. Nothing in this document has been built, booted or run. Every command is to be executed by the student in WSL2 (Ubuntu-24.04, user `ruisth`) or on the Windows host as stated; every "expected" value is a prediction to be confirmed or refuted by the evidence the step produces. Where a step depends on a design decision of the integrated profile that is not yet fixed, the assumption is stated in the step and collected in Appendix A. Anything not verified against the pinned checkout or the repository is marked `UNVERIFIED:` and listed in Appendix B.

Authority: project work order of 2026-09-17 (items 1-9) and the integrated-Yocto working revision of 2026-09-16 (plan v2.0 §5 and ADR 0008). That revision is **not yet published on `dev`**, where plan v1.2 (`docs/governance/INTEGRATED_DEVELOPMENT_PLAN_2026.md`) remains the published plan; this runbook accepts no gate and no claim. Staging: Sections 0-3 (profile, build, boot) are delivered with the integrated-profile change set; Sections 4-9 additionally need the deployment and harness changes that follow in later pull requests (`scripts/prepare-broker-secrets.sh`, `scripts/probe-acl.sh`, `egw_experiments/itest_reconcile.py`, the prebuilt controller image) — Section 5.1 checks for them and stops if they are missing. Fixed names come from the work order and are not renegotiated here: manifest `src/yocto/kas/egw-qemuarm64-integrated.yml` (+ `.lock.yml`), images `egw-gateway-image` / `egw-gateway-image-dev`, configuration recipe `egw-gateway-config`, build directory `src/yocto/build-integrated/` selected with `KAS_BUILD_DIR`.

Conventions:

- `host$` — bash on the WSL2 host, repository clone at `/home/ruisth/yocto/egw` (the Windows checkout `C:\Users\ruimf\Documents\Projeto Mestrado\Claude` is read-only for this work; the WSL clone is where the change set is applied on a branch and where kas runs).
- `PS>` — Windows PowerShell with Docker Desktop started.
- `guest$` — BusyBox ash (`/bin/sh -> busybox.nosuid`) inside the Yocto guest as user `egw`; `guest#` — root on the serial console of the `-dev` image only.
- Never run `bitbake`, `kas build` or `kas checkout` against `src/yocto/build/` (the sealed G1 tree). Every kas command below carries `KAS_BUILD_DIR=$PWD/build-integrated`.

---

## 0. Scope and labelling

**What this environment is.** The Yocto ARM64 guest (`egw-gateway-image`, MACHINE `qemuarm64`, linux-yocto 6.6.142, Poky 5.0.19 Scarthgap) booted by `runqemu` with **QEMU 8.2.7 in TCG mode on the x86-64 WSL2 host** (qemu-system-native from the build tree; no `qemu-system-aarch64` is installed in Ubuntu-24.04 itself — verified 2026-09-17). Inside that guest the six containers of the digital-twin core (Mosquitto 2.0.22, MongoDB 7.0.39, Ditto 3.9.4 gateway/policies/things, the controller) run under docker-moby 25.0.9 with Compose V2. The simulator and the experiments harness stay **outside** the guest, on the WSL2 host, and reach the guest through slirp port forwarding.

**Label to use everywhere** (evidence README, `sut_environment.json`, run manifests, figures, dissertation text):

> ARM64 **emulated** by QEMU 8.2.7/TCG on an x86-64 host (Windows 11, WSL2 Ubuntu-24.04). Never native ARM64, never KVM. The x86 KVM of the WSL2 kernel cannot accelerate an aarch64 guest.

**What this evidence can support:** that the versioned Yocto image boots the real stack; that the stack is functionally correct (MQTT/TLS -> controller -> Ditto -> API, three profiles, invalid input, duplicates, disconnect/reconnect, controller restart, fault recovery, persistence, authorisation); that the deployment, collectors and harness hooks work unchanged on the Yocto guest; that the image, kernel, container and QEMU identities can be bound to every run.

**What it cannot support:** any latency, throughput, saturation, cold-start or resource number as a property of ARM64 hardware or of a native ARM64 VM (ADR 0008: "QEMU/TCG emulation ... contributes no ARM hardware performance result"). Numbers produced here characterise *this emulated configuration only* and are admissible in the dissertation only with that label and only after supervisor alignment (work order item 9). The 95-run campaign is **not** started on this environment.

**Relation to G1.** The sealed G1 evidence (`docs/evidence/g1-yocto-qemu/2026-08-14-clean-build-f0e19d5/`) used `-cpu cortex-a57` and `-m 256`; MongoDB 7 requires ARMv8.2-A, so the full stack was never runnable in that profile (audit report `docs/reviews/2026-09-17-egw-image-audit.md`, sections 1 and 4). The integrated profile is a *new* configuration with its own build directory, image name, run identifiers and evidence directory; the G1 inputs listed in the work order remain byte-identical and the G1 directory is never written to.

---

## 1. Prerequisites

### 1.1 WSL2 host packages

State on 2026-09-17 (verified): Ubuntu-24.04, kernel 6.6.87.2-microsoft-standard-WSL2, 16 CPUs, 31 GiB RAM, 818 GB free on the ext4 volume, Python 3.12.3, `python3-venv` installed, `kas 5.4` via pipx, `sfdisk`, `truncate`, `ss`, `gzip`, `sha256sum`, `ssh`, `scp` present; `qemu-img`, `parted`, `bmaptool`, `mosquitto-clients` absent; no `docker` command usable in the distro.

The boot wrapper of the integrated profile `scripts/run-qemu-integrated.sh` needs `mkfs.ext4` (package `e2fsprogs`) to create the data disk and uses `blkid` (package `util-linux`) to check its label; both packages are part of a standard Ubuntu-24.04 installation. Confirm before the first boot:

```bash
host$ command -v mkfs.ext4 blkid truncate ss kas      # all five must print a path
# mosquitto-clients is NOT needed on the host: integration test 9(d) runs mosquitto_pub/mosquitto_sub
# inside the broker container in the guest (scripts/probe-acl.sh).
# qemu-utils / parted are NOT needed for the qemuarm64 raw-ext4 profile: the data disk is a
# raw file created with coreutils 'truncate' and formatted with mkfs.ext4 by the wrapper;
# 'wic ls' does not apply (no .wic is produced for MACHINE qemuarm64).
```

### 1.2 Disk space

The integrated build shares `DL_DIR`/`SSTATE_DIR` under `~/yocto-cache` with G1 (same pinned commits, same MACHINE/tune), so the extra space is the new `build-integrated/tmp` (order of 30-60 GB, estimate) plus the image archives (about 2 GB uncompressed for the five pinned images plus the controller — `docker save` output is not compressed; `UNVERIFIED:` estimate) plus the sparse 32 GiB data disk of Section 3.2 (grows only as the guest writes to it). Keep at least 120 GB free before starting (`df -h ~`). The WSL2 VHDX does not shrink automatically (see `docs/setup/wsl2_ubuntu_yocto.md` §2).

### 1.3 `.wslconfig` and host headroom

The guest (`QB_MEM = "-m 8192"`, integrated manifest — an 8 GiB guest) and QEMU/TCG (4 vCPU threads plus I/O threads) run inside the WSL2 VM alongside the simulator; the WSL2 VM must therefore have RAM for the guest **and** the host-side processes. State checked read-only on 2026-09-18: the workstation has about 64 GiB of RAM (63.4 GiB reported by Windows), no `%UserProfile%\.wslconfig` exists, and the WSL2 VM therefore has the default 50 %, i.e. the 31 GiB that `free -g` shows — enough for the 8 GiB guest as it is, so **do not create a `.wslconfig` just for this profile**. `memory=20GB` is a lower bound that applies only if a limit is ever set there: below it, `memory=16GB` would leave only about 8 GiB for QEMU's own overhead, the simulator, the harness and the page cache. If a smaller guest is needed for a bring-up boot, `EGW_QEMU_EXTRA="-m 6144"` on the wrapper (3.3) overrides `QB_MEM` for that boot only and runqemu mirrors it into `mem=`; never use a smaller guest for evidence runs. Never run a Yocto build while the guest is up (work order item 9). Check after `wsl --shutdown`:

```bash
host$ free -g; nproc
```

### 1.4 Docker Desktop (image preparation host)

Verified 2026-09-17: Docker Desktop client 29.7.2 is installed on Windows; the daemon was not running; the Ubuntu-24.04 distro has no working `docker` (WSL integration disabled — the `/mnt/c/.../resources/bin/docker` shim prints "could not be found in this WSL 2 distro"). The image steps of Section 4 need a running daemon, and the `docker buildx`/`docker save` client flags `--platform` (verified on the 29.7.2 client help). Choose ONE of:

- **Option A (PowerShell):** start Docker Desktop, wait until `docker version` shows the Server section, run the Section 4 commands in PowerShell against the Windows checkout, then copy the archives into WSL via `/mnt/c`.
- **Option B (WSL):** start Docker Desktop, enable *Settings -> Resources -> WSL integration -> Ubuntu-24.04*, apply, reopen the WSL shell, confirm `docker version` and `docker buildx inspect default | grep -i platforms` lists `linux/arm64`, then run the Section 4 commands in bash with the WSL paths.

Docker Desktop builds `linux/arm64` images with its bundled binfmt/QEMU user-mode emulation (audit report `docs/reviews/2026-09-17-egw-image-audit.md`, sections 1 and 4); this is a *build* aid on the provisioning host and says nothing about the measured guest.

`UNVERIFIED:` whether the Docker Desktop engine that starts is configured with the containerd image store (the default for recent installs) — it changes the meaning of `docker image inspect --format '{{.Id}}'` on the host (manifest digest instead of config digest). Section 4.3 therefore derives the identity from the saved archive's `manifest.json`, which is store-independent, and never compares host `.Id` against guest `.Id` directly.

### 1.5 SSH key pair outside the repository

```bash
host$ ssh-keygen -t ed25519 -f ~/.ssh/egw_campaign -C egw-campaign-tcg -N ''
host$ ls -l ~/.ssh/egw_campaign ~/.ssh/egw_campaign.pub
```

Neither file is ever copied into `/home/ruisth/yocto/egw` or into an evidence directory. The public key reaches the image at build time through the build-time variable the integrated manifest exposes (assumption A1: `EGW_AUTHORIZED_KEYS_FILE`, as in the earlier draft; if the integrated profile chose another name, substitute it in Section 2.1). Because the guest's host key changes with every rebuilt image, keep a dedicated known-hosts file:

```bash
host$ cat >> ~/.ssh/config <<'EOF'
Host egw-tcg
    HostName 127.0.0.1
    Port 2222
    User egw
    IdentityFile ~/.ssh/egw_campaign
    IdentitiesOnly yes
    UserKnownHostsFile ~/.ssh/known_hosts_egw_tcg
    StrictHostKeyChecking accept-new
EOF
```

If `runqemu` re-maps port 2222 (Section 3.3), edit `Port` in this block before continuing; every `ssh egw-tcg`/`scp egw-tcg:` below then follows automatically. After every image rebuild the guest generates new host keys: `rm -f ~/.ssh/known_hosts_egw_tcg` before the first connection to the new image, otherwise ssh refuses with a host-key mismatch.

### 1.6 Working directories on the host

```bash
host$ mkdir -p ~/yocto/logs ~/egw-images ~/egw-tcg/itest ~/egw-tcg/evidence
host$ cd /home/ruisth/yocto/egw && git status --short && git log --oneline -1
```

The WSL clone was at commit `32f6604` on 2026-09-18. Apply the integrated-profile change set on a branch (`git checkout -b feat/qemuarm64-integrated`) and confirm the G1 inputs are untouched: `git diff --stat HEAD -- src/yocto/kas/egw-qemuarm64.yml src/yocto/kas/egw-qemuarm64.lock.yml src/yocto/meta-egw/recipes-core/images/egw-image.bb src/yocto/meta-egw/recipes-core/egw-base-config src/yocto/meta-egw/recipes-core/egw-container-smoke src/yocto/scripts` must print nothing.

---

## 2. Build

### 2.1 Environment

```bash
host$ cd /home/ruisth/yocto/egw/src/yocto
host$ export KAS_WORK_DIR=$PWD
host$ export KAS_BUILD_DIR=$PWD/build-integrated        # verified: kas 5.4 context.py line 85 reads KAS_BUILD_DIR
host$ export EGW_CACHE_DIR=$HOME/yocto-cache             # shared downloads + sstate (same as scripts/build.sh)
host$ export EGW_AUTHORIZED_KEYS_FILE=$HOME/.ssh/egw_campaign.pub   # assumption A1 (variable name of the integrated manifest)
host$ mkdir -p "$EGW_CACHE_DIR/downloads" "$EGW_CACHE_DIR/sstate-cache"
host$ df -T . | tail -1      # must be ext4, never 9p/drvfs
```

`kas build --help` (kas 5.4, verified) has no `--build-dir` option; the environment variable is the only way, and `scripts/build.sh` hard-codes the G1 manifest, so it is not used here (work order: wrapper script rather than editing `build.sh`). The integrated profile provides `scripts/build-profile.sh`: `./scripts/build-profile.sh integrated` and `./scripts/build-profile.sh integrated --target egw-gateway-image-dev` are equivalent to the commands of 2.2 (the wrapper exports `KAS_WORK_DIR`, `KAS_BUILD_DIR=$PWD/build-integrated` and `EGW_CACHE_DIR` itself, validates `EGW_AUTHORIZED_KEYS_FILE`, runs `kas checkout` then `kas build`, and prints the log paths it wrote — `~/yocto/logs/kas-checkout-integrated-<its STAMP>.log` and `kas-build-integrated-<its STAMP>.log`). If the wrapper is used, set `STAMP` from those names before 2.5, e.g. `STAMP=$(ls -t ~/yocto/logs/kas-build-integrated-*.log | head -1 | sed -E 's/.*integrated-(.*)\.log/\1/')`; the wrapper's second invocation for the `-dev` image writes its own pair of logs with a later STAMP.

### 2.2 Checkout and build

```bash
host$ set -o pipefail      # bash: keep kas's exit status through tee
host$ STAMP=$(date -u +%Y%m%dT%H%M%SZ)
host$ kas checkout kas/egw-qemuarm64-integrated.yml 2>&1 | tee ~/yocto/logs/kas-checkout-integrated-$STAMP.log
host$ kas build kas/egw-qemuarm64-integrated.yml       2>&1 | tee ~/yocto/logs/kas-build-integrated-$STAMP.log
host$ kas build kas/egw-qemuarm64-integrated.yml --target egw-gateway-image-dev 2>&1 | tee ~/yocto/logs/kas-build-integrated-dev-$STAMP.log
```

kas auto-merges `kas/egw-qemuarm64-integrated.lock.yml`; the resolved commits printed in the checkout log must be `bb98354685781296e3b3737e7762412100f359c2` (poky), `ef3df29f2cfca6a9513b51ebcdccf82b6c8a836f` (meta-openembedded) and `0d9fb7fef86c5cbc177045c7b86bc71948f8657d` (meta-virtualization) — the same pins as G1. The layer clones already exist under `src/yocto/` from G1; `kas checkout` re-uses them.

**Expected sstate reuse.** MACHINE and tune are unchanged (qemuarm64 / cortexa57), so every target package that G1 built is served from `~/yocto-cache/sstate-cache` unless its inputs changed. New work is confined to: `docker-compose` (never built in this tree — its build is an open item, `UNVERIFIED:` docker-compose_git.bb v2.26.0 builds cleanly with the pinned layers), `sudo` (never built in this tree either), `egw-gateway-config`, the two image recipes (`curl`, `openssh` and `e2fsprogs` were already built by G1 — their work directories exist under `build/tmp/work/cortexa57-poky-linux/` — so their packages come from the shared sstate), and the kernel only if the integrated profile added a qemuarm64-affecting kernel change (the work order forbids that outside `:genericarm64` overrides). Read the "Sstate summary" line at the end of the build log and record it; a "missed" count in the thousands means the tune or a global variable changed — stop and investigate before booting.

### 2.3 Expected outputs

```bash
host$ DEPLOY=$KAS_BUILD_DIR/tmp/deploy/images/qemuarm64
host$ ls -l $DEPLOY
```

Expected: `egw-gateway-image-qemuarm64.rootfs.ext4`, `.tar.bz2`, `.manifest`, `.testdata.json`, `.qemuboot.conf` (each also with a `-<timestamp>` twin), the same set for `egw-gateway-image-dev-...`, `Image`, `Image-qemuarm64.bin`, `modules-qemuarm64.tgz`. No `.wic`, no EFI files (qemu.inc sets `IMAGE_FSTYPES += "tar.bz2 ext4"`). The G1 deploy directory `src/yocto/build/tmp/deploy/images/qemuarm64/` must still contain exactly its previous files (compare `ls -l --time-style=full-iso` before and after).

### 2.4 Acceptance on the artefacts (no boot)

```bash
host$ M=$DEPLOY/egw-gateway-image-qemuarm64.rootfs.manifest
host$ grep -E '^(docker-compose|curl|sudo|openssh-sftp-server|docker-moby|containerd-opencontainers|runc-opencontainers) ' $M
host$ grep -cE '^kernel-module-' $M
host$ python3 - "$DEPLOY/egw-gateway-image-qemuarm64.rootfs.testdata.json" <<'EOF'
import json, sys
d = json.load(open(sys.argv[1]))
for k in ("IMAGE_FEATURES", "DISTRO_FEATURES", "MACHINE_FEATURES", "QB_CPU", "QB_MEM", "QB_SMP", "QB_SLIRP_OPT", "IMAGE_LINK_NAME"):
    print(k, "=", d.get(k))
EOF
host$ tar -xjOf $DEPLOY/egw-gateway-image-qemuarm64.rootfs.tar.bz2 ./etc/shadow | grep -E '^(root|egw):'
host$ tar -xjOf $DEPLOY/egw-gateway-image-qemuarm64.rootfs.tar.bz2 ./etc/ssh/sshd_config.d/10-egw.conf ./etc/docker/daemon.json ./etc/fstab 2>&1 | head -n 60
```

Expected: the six packages listed; `IMAGE_FEATURES` of `egw-gateway-image` **without** `debug-tweaks` (the `-dev` testdata has it); `QB_CPU` = an ARMv8.2-A model (`-cpu cortex-a76` — assumption A2; `cortex-a76`, `neoverse-n1/n2/v1` and `max` are the models QEMU 8.2.7 in the build tree offers; audit report `docs/reviews/2026-09-17-egw-image-audit.md`, section 5); `QB_MEM` = `-m 8192` (integrated manifest, A3); `QB_SLIRP_OPT` containing `hostfwd=tcp:127.0.0.1:2222-:22` **and** `hostfwd=tcp:127.0.0.1:8883-:8883` (assumption A4; without it the simulator cannot reach the broker, verified runqemu lines 1107-1145); `root:*:` and `egw:*:` in `/etc/shadow` — **not** `egw:!:`, which poky's OpenSSH (no PAM) treats as a locked account and refuses even with a valid key (first-round review, audit report `docs/reviews/2026-09-17-egw-image-audit.md` section 11; the `useradd ... -p '*'` idiom in `EXTRA_USERS_PARAMS` is the fix). If the shadow line shows `!`, do not boot — fix the image recipe first.

### 2.5 Record the build identity

```bash
host$ EV=~/egw-tcg/evidence/build-$STAMP && mkdir -p $EV
host$ git -C /home/ruisth/yocto/egw rev-parse HEAD > $EV/source_commit.txt
host$ git -C /home/ruisth/yocto/egw status --porcelain > $EV/git_status.txt      # must be empty on the branch
host$ cp ~/yocto/logs/kas-checkout-integrated-$STAMP.log ~/yocto/logs/kas-build-integrated-$STAMP.log $EV/
host$ cp $KAS_BUILD_DIR/conf/local.conf $KAS_BUILD_DIR/conf/bblayers.conf $EV/
host$ cp $DEPLOY/egw-gateway-image-qemuarm64.rootfs.manifest $DEPLOY/egw-gateway-image-qemuarm64.rootfs.testdata.json $DEPLOY/egw-gateway-image-qemuarm64.rootfs.qemuboot.conf $EV/
host$ (cd $DEPLOY && sha256sum $(readlink egw-gateway-image-qemuarm64.rootfs.ext4) $(readlink Image) ) > $EV/SHA256SUMS.artefacts
host$ tar -xjOf $DEPLOY/egw-gateway-image-qemuarm64.rootfs.tar.bz2 ./etc/buildinfo > $EV/buildinfo.txt 2>/dev/null || echo "no /etc/buildinfo (image-buildinfo not inherited)" > $EV/buildinfo.txt
host$ ls -d $KAS_BUILD_DIR/tmp/work/x86_64-linux/qemu-system-native/*/ > $EV/qemu_native_version_dir.txt
host$ $KAS_BUILD_DIR/tmp/sysroots-components/x86_64/qemu-system-native/usr/bin/qemu-system-aarch64 --version > $EV/qemu_version.txt
```

The last line records the QEMU that `runqemu` will execute (verified path layout in the G1 tree: `build/tmp/sysroots-components/x86_64/qemu-system-native/usr/bin/qemu-system-aarch64`, version 8.2.7; the integrated tree uses the same recipe from sstate). If the sysroots-components path does not exist in `build-integrated`, use `$KAS_BUILD_DIR/tmp/work/x86_64-linux/qemu-system-native/8.2.7/build/qemu-system-aarch64 --version`.

---

## 3. Boot

### 3.1 Before starting QEMU

```bash
host$ ss -ltn | grep -E ':(2222|8883|8000|8080) ' || echo "ports free"
```

`runqemu` silently re-maps a forwarded host port that is already in use and logs `Port forward changed: 2222 -> 2223` (verified, runqemu lines 1118-1136). A stale `ssh -L` tunnel or a second runqemu will therefore move SSH or MQTT to another port. Kill whatever holds 2222/8883 before booting, and after every boot read the actual mapping (3.3).

### 3.2 Disk layout (integrated profile: separate data disk, verified)

the integrated profile fixed the storage layout; there is no choice to make here:

- The root file system is the deployed raw ext4 file, with `IMAGE_ROOTFS_EXTRA_SPACE = "2097152"` (2 GiB of headroom, `egw-gateway-image.bb`) for the OS, `/opt/egw` (deployment tree, `data/events`), `/home/egw` and the journal capped at 256 MiB. It has **no** growfs entry and is never grown or copied: `runqemu` boots the deployed `.ext4` **in place** (no `-snapshot`), so the sha256 recorded in 2.5 identifies the artefact *before its first boot* only; after the first boot the file has changed (journal, host keys, `/opt/egw` content). Record that fact in the evidence README rather than re-hashing the file.
- `/var/lib/docker` (image layers under overlay2, the `mongodb-data` and `mosquitto-data` named volumes, the json-file container logs) is a **second virtio disk**: `egw_add_data_disk_fstab` in `egw-gateway-image.bb` appends `LABEL=egw-data  /var/lib/docker  ext4  defaults,nofail,x-systemd.growfs,x-systemd.device-timeout=30s  0  0` to `/etc/fstab`, and the `egw-gateway-config` drop-in `10-egw-data-disk.conf` sets `RequiresMountsFor=/var/lib/docker` on `docker.service`. Consequences: (i) **without the disk attached, `docker.service` fails visibly** (`systemctl --failed` shows it; the boot continues and SSH stays up) and nothing from 3.4 onwards can run; (ii) the disk file is created, formatted (`mkfs.ext4 -L egw-data`) and attached by `scripts/run-qemu-integrated.sh` — the guest has no `mkfs.ext4`, only `resize2fs` and `e2fsck`; (iii) growing the file on the host (`truncate -s 64G <path>`) is applied by `systemd-growfs@var-lib-docker.service` at the next boot; (iv) deleting or renaming the file is the destructive reset of every image, volume and container log (work order item 8: identified test volumes only — never delete evidence).
- The wrapper's defaults: disk file `$HOME/yocto/egw-integrated/egw-data.img` (outside the repository — the script refuses a path inside it), size `32G` sparse, label `egw-data`. Overrides (documented in the script header): `EGW_DATA_DISK`, `EGW_DATA_DISK_SIZE` (new files only), `EGW_IMAGE` (`egw-gateway-image` | `egw-gateway-image-dev`), `EGW_QEMU_EXTRA` (extra QEMU arguments appended to `qemuparams`), `EGW_LOG_DIR` (default `~/yocto/logs`).

Sizing check for the stack on the 32 GiB data disk: six images (about 2 GB uncompressed, `UNVERIFIED:` estimate), MongoDB data, container logs (up to 50 MiB x 3 files x 6 services) — ample. Note that runqemu adds `-no-reboot` for ext4 root images (verified, runqemu line 1319): a guest `reboot` ends the QEMU process, and the next wrapper run re-attaches the same data-disk file and boots the same (already mutated) root file system — state persists on both, which is the persistence test of Section 7, test 8.

### 3.3 Start the guest

```bash
host$ cd /home/ruisth/yocto/egw/src/yocto
host$ BOOT=integrated-boot-$(date -u +%Y%m%dT%H%M%SZ)
host$ ./scripts/run-qemu-integrated.sh $BOOT
```

That is the whole boot command for evidence runs. The wrapper (bash, `set -euo pipefail`) exports `KAS_WORK_DIR`, `KAS_BUILD_DIR=$PWD/build-integrated` and `EGW_CACHE_DIR`, refuses to run when `build-integrated/tmp/deploy/images/qemuarm64/egw-gateway-image-qemuarm64.rootfs.qemuboot.conf` is missing, creates and formats the data disk when absent, verifies its label with `blkid`, warns if host ports 2222/8883 are busy, writes a header (date, host, `qb_*` lines of the qemuboot.conf, the disk file's apparent and on-disk size, the exact runqemu command) to `~/yocto/logs/$BOOT.log`, and then runs:

```
kas shell kas/egw-qemuarm64-integrated.yml -c 'runqemu egw-gateway-image qemuarm64 nographic slirp qemuparams="-drive id=disk1,file=$HOME/yocto/egw-integrated/egw-data.img,if=none,format=raw -device virtio-blk-pci,drive=disk1"' 2>&1 | tee -a ~/yocto/logs/$BOOT.log
```

The equivalent explicit line (only for diagnosing the wrapper itself; the wrapper is the record) is that command with the same three exports set by hand and the disk file already formatted. Notes (all verified in `poky/scripts/runqemu`):

- `kas shell` runs its command **from `$KAS_BUILD_DIR`** with the BitBake environment sourced (`oe-init-build-env`), so `runqemu` resolves `egw-gateway-image qemuarm64` against `build-integrated/tmp/deploy/images/qemuarm64/` — the deployed `egw-gateway-image-qemuarm64.rootfs.ext4` and its own `.qemuboot.conf` (same base name), never the `-dev` image's conf.
- Memory is set in ONE place: `QB_MEM = "-m 8192"` from the qemuboot.conf, or `EGW_QEMU_EXTRA="-m 6144"` (bring-up only), which runqemu parses (line 823) and mirrors into the kernel `mem=` argument (line 843). Never pass `mem=` yourself via `bootparams=`.
- To try a different CPU model without rebuilding, `EGW_QEMU_EXTRA="-cpu neoverse-n1"` is appended *after* the `QB_CPU` option (line 1557-1559); `UNVERIFIED:` QEMU honours the last `-cpu` given. Prefer changing `QB_CPU` in the manifest and rebuilding the image (only the qemuboot.conf changes) so the record in `testdata.json` matches the boot.
- For the `-dev` image (root console login) use `EGW_IMAGE=egw-gateway-image-dev ./scripts/run-qemu-integrated.sh $BOOT-dev`; it attaches the same data disk and is for bring-up only, never for evidence runs.
- Exit QEMU with `Ctrl+A` then `x` (the wrapper's stdin stays attached to the terminal; stdout/stderr are teed into the log).

Immediately after boot, from a second host terminal:

```bash
host$ grep -E 'Port forward|runqemu - INFO - Running' ~/yocto/logs/$BOOT.log
```

The `Running ...` line is the exact QEMU command line (machine, `-cpu`, `-smp`, `-m`, drives, netdev with hostfwd, kernel `mem=`): copy it verbatim into the evidence — it is the "pinned QEMU version, machine model, CPU, memory, disk and boot parameters" record required by work order item 1, together with `qemu_version.txt` from 2.5. If `Port forward changed:` appears, update `~/.ssh/config` (`Port`) and the simulator `--port` accordingly.

### 3.4 Acceptance inside the guest (BusyBox ash)

Log in over SSH (the campaign image has no console login):

```bash
host$ ssh egw-tcg 'id; hostname; sudo -n true && echo SUDO_OK'
```

Expected: `uid=1000(egw) gid=1000(egw) groups=1000(egw),NNN(docker)`, the hostname `egw-qemu-integrated` (`EGW_HOSTNAME` in the integrated manifest, written by `egw_set_hostname` in `egw-gateway-image.bb`, A6), `SUDO_OK`. `ssh -p 2222 root@127.0.0.1` must be refused (key-only, `PermitRootLogin no`).

Then, in one SSH session, run and save the whole transcript (`ssh egw-tcg 'sh -s' < checks.sh > guest-checks.txt` or interactively with `tee`):

```sh
# --- system ---------------------------------------------------------------
systemctl is-system-running           # expected: running
systemctl --failed --no-legend        # expected: empty
uname -a                              # aarch64, 6.6.142-yocto-standard
cat /etc/os-release | head -n 4
cat /etc/buildinfo 2>/dev/null        # if image-buildinfo is inherited (assumption A7)
# --- memory: QEMU RAM and kernel mem= must agree (work order item 2) --------
free -m                               # BusyBox free: CONFIG_FREE=y; -m accepted
head -n 1 /proc/meminfo               # MemTotal within ~5 % of the -m value minus kernel reservations
cat /proc/cmdline                     # shows mem=NNNNM injected by runqemu
# --- CPU ------------------------------------------------------------------
nproc                                 # expected 4 (-smp 4)
grep -m1 '^CPU part' /proc/cpuinfo    # 0xd0b = Cortex-A76 (0xd07 = the G1 Cortex-A57)
grep -m1 '^Features' /proc/cpuinfo    # must list at least: atomics asimdhp fphp (ARMv8.1 LSE / ARMv8.2 FP16)
# --- storage --------------------------------------------------------------
df -h / /var/lib/docker /opt/egw      # / = the deployed rootfs (2 GiB headroom); /var/lib/docker on /dev/vdb (LABEL=egw-data, ~32G)
findmnt /var/lib/docker               # expected SOURCE /dev/vdb, FSTYPE ext4, OPTIONS containing rw (util-linux findmnt, present in the G1 rootfs)
findmnt -no SOURCE,FSTYPE,OPTIONS /
lsblk                                 # vda = root image, vdb = data disk
systemctl status docker var-lib-docker.mount --no-pager   # both active; the mount unit is generated from /etc/fstab
systemctl status systemd-growfs@var-lib-docker.service --no-pager 2>&1 | head -n 5   # ran once (grows the fs to the file size)
# --- container runtime ----------------------------------------------------
docker info 2>/dev/null | grep -E 'Server Version|Storage Driver|Backing Filesystem|Cgroup Driver|Cgroup Version|Architecture|Total Memory|CPUs|Docker Root Dir|Live Restore'
docker compose version                # expected: Docker Compose version v2.26.0
docker info --format '{{.Architecture}} {{.OSType}} {{.KernelVersion}}'
findmnt -no FSTYPE /sys/fs/cgroup     # expected cgroup2 (BusyBox 'stat -f %T' has no cgroup2 entry and prints UNKNOWN)
# --- network / DNS / time ---------------------------------------------------
ip -o addr show                       # BusyBox ip (no iproute2 in the image; -br is not accepted): enp0s1 10.0.2.15/24 (slirp) + docker0
cat /etc/resolv.conf                  # symlink to /run/systemd/resolve/resolv.conf; nameserver 10.0.2.3 (slirp DNS)
resolvectl status 2>/dev/null | head -n 20
nslookup registry-1.docker.io 2>&1 | tail -n 3     # slirp gives outbound name resolution; pass/fail both recorded
timedatectl                           # NTP service: active; System clock synchronized: yes (may take a minute; UDP 123 via slirp)
timedatectl show
date -u
# --- operator access and permissions ---------------------------------------
ls -ld /opt/egw /home/egw             # egw:egw
command -v curl openssl sudo resize2fs e2fsck 2>&1          # all five expected; mkfs.ext4 is NOT in the image (the host formats the disk)
ls -l /usr/libexec/sftp-server; grep -i '^Subsystem' /etc/ssh/sshd_config   # poky packages sftp-server at ${libexecdir}/sftp-server (openssh_9.6p1.bb line 189), not in PATH
```

Record every line. Acceptance for item 2 of the work order is: `MemTotal` consistent with the QEMU `-m 8192` value (both QEMU RAM and `mem=` follow `QB_MEM`, so a 256 MiB guest cannot occur unless the profile still says `-m 256`); `nproc` = 4; CPU part `0xd0b` (or the neoverse part if `max`/`neoverse-*` was chosen); Cgroup Version 2 in `docker info`; overlay2; `Docker Root Dir: /var/lib/docker` with `findmnt` showing it on `/dev/vdb`; `docker compose version` prints v2.26.0. For the fail-visibly design of item 3 (docker never starts on the root file system when the disk is missing), record `systemctl show -p Requires,After docker.service | grep var-lib-docker.mount` — the dependency the drop-in adds; a boot without the disk is not exercised by the wrapper (it always creates and attaches the file) and is not needed for acceptance.

`UNVERIFIED:` which exact `/proc/cpuinfo` feature flags mongod 7.0 depends on; the decisive check is 3.5. (The `0xd0b` part number and the `atomics`/`asimdhp`/`fphp` flags for Cortex-A76 come from general Arm knowledge, not from a document in the pinned checkout.)

### 3.5 MongoDB 7 start test

Needs the `mongo:7.0.39` image inside the guest. The guest has **no registry access by design** for evidence runs (offline, verifiable identity); the image arrives as a `docker save` archive prepared on the Docker Desktop host and loaded with `docker load` (Section 4). Do Section 4.1-4.4 for at least the MongoDB archive, then:

```sh
guest$ docker image inspect --format '{{.Id}} {{.Architecture}} {{.Os}} {{.RepoTags}}' docker.io/library/mongo:7.0.39
guest$ docker run --rm --platform linux/arm64 docker.io/library/mongo:7.0.39 mongod --version
guest$ docker run -d --name mongo-cpu-test --memory 512m docker.io/library/mongo:7.0.39 mongod --storageEngine wiredTiger --noscripting
guest$ sleep 30; docker inspect --format '{{.State.Status}} exit={{.State.ExitCode}}' mongo-cpu-test
guest$ docker logs mongo-cpu-test 2>&1 | grep -iE 'illegal|SIGILL|Waiting for connections|error' | head -n 5
guest$ docker rm -f mongo-cpu-test
```

Expected under an ARMv8.2-A model: `mongod --version` prints `db version v7.0.39`, the container is `running exit=0` and the log contains `Waiting for connections`. Expected failure signature under the G1 `cortex-a57` profile (`UNVERIFIED:` exact wording): immediate exit with code 132 (SIGILL) or an "Illegal instruction" line — that is the work-order item 2 blocker, and it must never be "fixed" by relaxing the architecture check on the images.

Slirp alternative (diagnostic only, never for identity-verified runs): `docker pull --platform linux/arm64 docker.io/library/mongo:7.0.39@sha256:35a5926f71f8b6cb19206bee928c5a85f241a8be99f20c81abe35ae78a73415d` works through slirp's NAT if Docker Hub is reachable, and the digest pin selects the arm64 child; record that the image came from the registry if you use it.

---

## 4. Images

Goal: the five pinned images and the prebuilt controller enter the guest as checksummed archives with a **verifiable identity**, without registry access from the guest and without rebuilding the controller on every run (work order item 4, plan v2.0 §5 item 3).

Facts that shape this section (audit report `docs/reviews/2026-09-17-egw-image-audit.md`, section 4): `docker load` restores `repository:tag` only, never a `RepoDigest`; a compose reference `repo:tag@sha256:...` (the form used by `images.lock.env`) is **not** satisfied by a loaded archive and triggers a registry pull. Identity is therefore verified by the **image ID** (config digest), which is what the guest's docker-moby 25.0.9 (overlay2 graphdriver) reports as `.Id`, compared against the `Config` entry of the archive's `manifest.json` recorded on the provisioning host.

### 4.1 Build the controller for linux/arm64 (Docker Desktop, PowerShell)

```powershell
PS> $Src = "C:\Users\ruimf\Documents\Projeto Mestrado\Claude\src"
PS> $Out = "C:\Users\ruimf\egw-images"
PS> New-Item -ItemType Directory -Force $Out | Out-Null
PS> docker version            # Server section must be present (daemon running)
PS> docker buildx build --platform linux/arm64 --provenance=false --sbom=false --load `
      -t egw-controller:0.1.0 -f "$Src\Dockerfile" $Src 2>&1 | Tee-Object "$Out\buildx-controller.log"
PS> docker image inspect --format '{{.Architecture}} {{.Os}} {{.Id}}' egw-controller:0.1.0
```

Build context is `src/` (the Dockerfile copies `pyproject.toml`, the three packages and `schemas/`, verified). `--provenance=false --sbom=false` keeps the result a single-platform image so the archive has one manifest entry (`UNVERIFIED:` that Docker Desktop's default builder would otherwise attach an attestation manifest that `docker save --platform` includes). `--load` puts the image into the local engine so `docker save` can export it.

**Reproducibility caveat (first-round review, audit report `docs/reviews/2026-09-17-egw-image-audit.md` section 11):** `src/Dockerfile` still runs `RUN pip install .` and says so: an image built from it is acceptable for this functional integration and for the pilot's mechanics, **not** for thesis measurements. Before any run whose numbers might be cited, `requirements-runtime.lock` must be generated (`scripts/generate-runtime-lock.sh` refuses non-aarch64 hosts — the emulated guest may run it, recording that it was emulated: it has docker but no git/python outside containers, so run the helper from `/opt/egw/src` after copying `src/` in, or wait for a native host), reviewed, committed, and the Dockerfile switched to `--require-hashes`. Record in `buildx-controller.log` which Dockerfile state was built (`git -C ... rev-parse HEAD`).

Record the archive with `docker save` (client 29.7.2 supports `--platform`, verified in `docker save --help`):

```powershell
PS> docker save --platform linux/arm64 -o "$Out\egw-controller-0.1.0-arm64.tar" egw-controller:0.1.0
```

### 4.2 Pull, tag and save the five pinned images (PowerShell)

Pulling `repo:tag@sha256:<manifest-list digest>` with `--platform linux/arm64` selects the arm64 child (the digests in `images.lock.env` are manifest-list digests, verified header). A pull by digest leaves the image without the tag, so tag it explicitly before saving — the archive must carry `RepoTags` for the guest's compose file to find it:

```powershell
PS> Get-Content "$Src\deployment\images.lock.env" | ForEach-Object {
      if ($_ -match '^IMAGE_([A-Z_]+)=([^@]+)@(sha256:[0-9a-f]{64})$') {
        $name = $Matches[1]; $repoTag = $Matches[2]; $digest = $Matches[3]
        $repo = $repoTag.Substring(0, $repoTag.LastIndexOf(':'))
        docker pull --platform linux/arm64 "$repoTag@$digest"
        docker tag "$repo@$digest" $repoTag
        $file = (($repoTag -replace '^docker\.io/(library/)?','') -replace '[/:]','_') + '-arm64.tar'
        docker save --platform linux/arm64 -o "$Out\$file" $repoTag
        "$name $repoTag $digest $file" | Add-Content "$Out\pull-record.txt"
      }
    }
PS> Get-Content "$Out\pull-record.txt"
PS> Get-ChildItem $Out
```

Expected files: `eclipse-mosquitto_2.0.22-arm64.tar`, `mongo_7.0.39-arm64.tar`, `eclipse_ditto-policies_3.9.4-arm64.tar`, `eclipse_ditto-things_3.9.4-arm64.tar`, `eclipse_ditto-gateway_3.9.4-arm64.tar`, `egw-controller-0.1.0-arm64.tar`, `pull-record.txt`, `buildx-controller.log`. `UNVERIFIED:` `docker tag "<repo>@<digest>" <repo:tag>` accepted as the source reference form by the 29.7.2 client (documented Docker behaviour; not exercised here). If it is refused, use `docker images --digests --format '{{.ID}} {{.Digest}}'` to find the pulled image's ID and tag by ID.

Also archive the complete verification that plan v2.0 §5 item 3 asks for on the provisioning host: `docker buildx imagetools inspect <repo:tag>` for each of the five images (this needs registry access and buildx, both present on Docker Desktop) into `$Out\imagetools-<name>.txt`; `scripts/resolve-image-lock.sh` can run here too once WSL integration is on (Option B), and its output is the archived digest verification.

### 4.3 Copy into WSL, checksum, derive identities (bash)

```bash
host$ cp /mnt/c/Users/ruimf/egw-images/*.tar /mnt/c/Users/ruimf/egw-images/*.txt /mnt/c/Users/ruimf/egw-images/*.log ~/egw-images/
host$ cd ~/egw-images && sha256sum *.tar > SHA256SUMS && cat SHA256SUMS
host$ python3 - *.tar > archive-identity.txt <<'EOF'
import json, re, subprocess, sys
for tar in sys.argv[1:]:
    m = json.loads(subprocess.check_output(["tar", "-xOf", tar, "manifest.json"]))
    assert len(m) == 1, f"{tar}: {len(m)} manifest entries (expected 1: single platform, no attestations)"
    cfg = re.search(r"([0-9a-f]{64})", m[0]["Config"]).group(1)
    print(f"{tar} sha256:{cfg} {','.join(m[0].get('RepoTags') or [])}")
EOF
host$ cat archive-identity.txt
```

`archive-identity.txt` maps each archive to the image ID the guest must report after `docker load` (the config digest; `Config` is `<hex>.json` in the legacy layout or `blobs/sha256/<hex>` in the OCI layout — both matched). If an archive has more than one manifest entry, re-save it with `--platform linux/arm64` and without attestations.

### 4.4 Stream the archives over hostfwd 2222 into the engine

The archives are **not** staged on the guest: `docker save` output is uncompressed layer tars (about 2 GB for the six images, `UNVERIFIED:` estimate — mongo:7 arm64 alone unpacks to several hundred MB), and the root file system has only the 2 GiB `IMAGE_ROOTFS_EXTRA_SPACE` headroom shared with `/opt/egw` and the journal; the data disk is mounted only at `/var/lib/docker`. Copying them to `/opt/egw/images` would fill `/`. Instead, verify the checksums on the host (4.3 already wrote `SHA256SUMS`) and stream each archive straight into `docker load`, which reads its stdin:

```bash
host$ cd ~/egw-images && sha256sum -c SHA256SUMS
host$ ssh egw-tcg 'df -h / /var/lib/docker'                       # before
host$ for f in ~/egw-images/*.tar; do echo "== $f"; ssh egw-tcg docker load < "$f" || break; done
host$ ssh egw-tcg 'df -h / /var/lib/docker'                       # after: / unchanged, /var/lib/docker grown
host$ ssh egw-tcg 'mkdir -p /opt/egw/images'
host$ scp ~/egw-images/archive-identity.txt ~/egw-images/SHA256SUMS egw-tcg:/opt/egw/images/     # a few KB; the identity loop below reads it
```

Modern OpenSSH `scp` uses the SFTP protocol; the guest's `sftp-server` is at `/usr/libexec/sftp-server` (poky packages it as `${libexecdir}/sftp-server`, `openssh_9.6p1.bb` line 189 — same path in the G1 rootfs; assumption A8 that the new image keeps `openssh-sftp-server`); if the copy is refused, add `-O`. Throughput under slirp+TCG is low; about 2 GB may take tens of minutes (`UNVERIFIED:` estimate). Fallback if streaming through `ssh` misbehaves: `scp` **one** archive at a time to `/opt/egw/images`, `docker load -i` it, delete it, then the next, with `df -h /` between steps. Then in the guest:

```sh
guest$ cd /opt/egw/images
guest$ docker images --format '{{.Repository}}:{{.Tag}}\t{{.ID}}\t{{.Size}}'
guest$ while read -r tar id tags; do
         for t in $(echo "$tags" | tr ',' ' '); do
           got=$(docker image inspect --format '{{.Id}}' "$t" 2>/dev/null)
           arch=$(docker image inspect --format '{{.Architecture}}/{{.Os}}' "$t" 2>/dev/null)
           if [ "$got" = "$id" ] && [ "$arch" = "arm64/linux" ]; then echo "OK   $t $got"; else echo "FAIL $t expected=$id got=$got arch=$arch"; fi
         done
       done < archive-identity.txt
```

Every line must be `OK`. A `FAIL` means the archive was altered, the wrong platform was saved, or the guest engine re-computed a different config — stop and investigate; never proceed with an unverified image. Keep `archive-identity.txt`, `SHA256SUMS`, `pull-record.txt`, the `imagetools-*.txt` files and the verification transcript in the evidence directory: together they are the "identity of all images known" acceptance of work order item 4 (manifest-list digest -> arm64 child -> archive sha256 -> image ID in the guest).

`UNVERIFIED:` docker-moby 25.0.9 `docker load` accepts the OCI-layout tar that a 29.x `docker save` may produce (moby's `load.go` reads `manifest.json` `RepoTags`, verified; OCI-layout import support in 25.0 not checked). If `docker load` reports an unknown format, re-save from a legacy-format engine or with the containerd store disabled.

### 4.5 The compose adjustment — proposed change to `src/deployment` (not written by this work)

The guest cannot satisfy `image: repo:tag@sha256:...` from loaded archives, and `compose.yaml` still carries a `build:` stanza for the controller (lines ~210-212) that `up -d --build` would try to execute on a guest with no git, pip or buildx. Proposed edits, to be made in the deployment PR (work order deliverable 2):

1. `src/deployment/compose.yaml`, service `controller`: delete the three lines `build:` / `context: ..` / `dockerfile: Dockerfile` and the comment "Built locally from src/Dockerfile"; keep `image: egw-controller:0.1.0` and `platform: linux/arm64`. Update the header comment and README step 6 to `up -d` (no `--build`), and the last echo line of `scripts/validate-config.sh`.
2. New file `src/deployment/images.offline.env` — the same five `IMAGE_*` names with **tag-only** references, e.g. `IMAGE_MONGODB=docker.io/library/mongo:7.0.39`, header stating that it is valid only together with the identity verification of point 3 and that `images.lock.env` remains the source of truth for digests.
3. New file `src/deployment/images.identity.env` (generated on the provisioning host, committed per image set): one block per image with `IMAGE_<NAME>_LOCK=<manifest-list digest>`, `IMAGE_<NAME>_ARM64=<arm64 child digest from imagetools>`, `IMAGE_<NAME>_ID=sha256:<config digest from archive-identity.txt>`, `IMAGE_<NAME>_ARCHIVE_SHA256=<sha256 of the .tar>`, plus `IMAGES_PROVISIONED_BY=<host, docker version, date>`; and a new POSIX-sh script `scripts/verify-loaded-images.sh` that, in the guest, runs the loop of 4.4 against this file and exits 1 on any mismatch. Until it exists, the manual loop of 4.4 is the check.
4. `scripts/generate-dev-auth.sh` and the new `scripts/prepare-broker-secrets.sh` honour `EGW_BROKER_IMAGE` (and `LOCK_FILE`): on the guest export `EGW_BROKER_IMAGE=docker.io/library/eclipse-mosquitto:2.0.22` (the loaded tag) so that neither script tries to pull the digest-pinned reference. Unlike points 1-3 and 5, this one is already in the working tree (written on 2026-09-18 for PM correction 1, together with step 3b of `validate-config.sh` and the corrected privilege comment in `generate-dev-tls.sh`); `UNVERIFIED:` never executed against a Docker engine.
5. `scripts/validate-config.sh`: keep step 4 (digest format of `images.lock.env`) and add an optional `--images-env <file>` used only for the `docker compose config -q` step, so the offline file is validated with the same invocation shape as `up`.
6. Two test helpers, also already in the working tree and never executed against the real stack: `scripts/probe-acl.sh` (POSIX sh, runs on the guest; the ACL proof with known traffic of integration test 9(d)) reaches the guest with the `scp -r` of 5.1; `src/egw_experiments/itest_reconcile.py` (host side, `python -m egw_experiments.itest_reconcile`) applies the harness's own confirmation rule and the before/after counter comparisons to the ad-hoc `itest-*` runs of Sections 6 and 7. It imports `CONFIRMATION_WINDOW_S`, `poll_controller_marker` and `compute_run_metrics` from the harness and changes no existing module.

Guest command shape after the change: `docker compose --env-file .env --env-file images.offline.env up -d`. Section 5 uses that shape; if the deployment PR is not yet merged, apply points 1-2 locally on the guest copy of the deployment tree and record the diff in the evidence.

---

## 5. Deploy

### 5.1 Copy the deployment tree

Fixed guest layout (first-round review, audit report `docs/reviews/2026-09-17-egw-image-audit.md` section 11): the deployment tree lives at **`/opt/egw/deployment`**; the README's `/opt/egw/src/deployment` and the collector header's `/opt/egw/scripts` examples must be updated in the deployment PR, and until then every harness hook passes the explicit path.

```bash
host$ cd /home/ruisth/yocto/egw/src/deployment && ls scripts/prepare-broker-secrets.sh scripts/probe-acl.sh \
        && grep -c '3b\.' scripts/validate-config.sh && grep -c 'chown mosquitto:mosquitto' scripts/generate-dev-auth.sh \
        || echo 'STOP: this clone does not carry the broker-permission change set; do not copy it'
host$ scp -r /home/ruisth/yocto/egw/src/deployment egw-tcg:/opt/egw/
host$ ssh egw-tcg 'ls -la /opt/egw/deployment; stat -c "%U:%G %n" /opt/egw/deployment'
host$ ssh egw-tcg "cd /opt/egw/deployment && ls scripts/prepare-broker-secrets.sh scripts/probe-acl.sh && grep -c '3b\.' scripts/validate-config.sh && grep -c 'chown mosquitto:mosquitto' scripts/generate-dev-auth.sh || echo 'STOP: stale deployment tree on the guest'"
```

Guard on the change set: both checks must list the two scripts and print two non-zero counts, and must not print `STOP`. As read on 2026-09-18 the WSL clone's `src/deployment/scripts` still holds the seven scripts of 10 August (no `prepare-broker-secrets.sh`, no `probe-acl.sh`, `validate-config.sh` without step 3b, `generate-dev-auth.sh` without the `chown`); the corrected files exist only in the Windows working tree until the deployment branch is applied in the clone. A stale tree fails loudly in 5.4a (missing script), but its `validate-config.sh` has no broker read test (step 3b) and would let `up -d` proceed into the broker restart loop that 5.4a exists to prevent — hence the check here, before anything is generated on the guest.

`/opt/egw` is created at boot for `egw` by the profile's tmpfiles entry (assumption A9); everything copied as `egw` is owned by uid 1000, which is the uid the controller container runs as (`src/Dockerfile`: `useradd --uid 1000`).

### 5.2 `.env`

`generate-dev-auth.sh` exits 2 without the two passwords, `validate-config.sh` fails without `.env`, and compose refuses a missing `--env-file` (verdict major 4). Create `.env` **before** anything else. Either edit on the guest (`vi` is BusyBox vi) or prepare it on the host and copy it — it is git-ignored and never enters the evidence:

```bash
host$ cd /home/ruisth/yocto/egw/src/deployment && cp .env.example ~/egw-tcg/.env
host$ SIM=$(openssl rand -base64 24 | tr -d '/+='); CTL=$(openssl rand -base64 24 | tr -d '/+='); DEV=$(openssl rand -base64 24 | tr -d '/+=')
host$ sed -i -e "s|^MOSQUITTO_SIMULATOR_PASSWORD=.*|MOSQUITTO_SIMULATOR_PASSWORD=$SIM|" \
             -e "s|^MOSQUITTO_CONTROLLER_PASSWORD=.*|MOSQUITTO_CONTROLLER_PASSWORD=$CTL|" \
             -e "s|^EGW_MQTT_PASSWORD=.*|EGW_MQTT_PASSWORD=$CTL|" \
             -e "s|^DITTO_DEVOPS_PASSWORD=.*|DITTO_DEVOPS_PASSWORD=$DEV|" ~/egw-tcg/.env
host$ grep -c CHANGE_ME ~/egw-tcg/.env      # must print 0
host$ chmod 600 ~/egw-tcg/.env && scp ~/egw-tcg/.env egw-tcg:/opt/egw/deployment/.env
```

`EGW_HOST` stays empty: the simulator connects to `127.0.0.1` (hostfwd) and the default SAN already contains `IP:127.0.0.1`. `EGW_MQTT_PASSWORD` must equal `MOSQUITTO_CONTROLLER_PASSWORD` (compose wires the latter into the controller). Keep `~/egw-tcg/.env` on the host: the simulator and harness read the simulator password from it.

### 5.3 TLS material (on the guest; only `ca.crt` ever leaves it)

`generate-dev-tls.sh` takes **no positional argument** (verdict major 5); the host goes through `--host` or `EGW_HOST`. For the hostfwd address nothing is needed:

```sh
guest$ cd /opt/egw/deployment
guest$ sh scripts/generate-dev-tls.sh
guest$ openssl x509 -in mosquitto/config/certs/server.crt -noout -subject -enddate -ext subjectAltName
```

Expected SAN: `DNS:localhost, DNS:mosquitto, IP Address:127.0.0.1`. Only if the simulator will use another address (a real NIC on the native route) run `sh scripts/generate-dev-tls.sh --host <that address>`; the port is not part of the SAN, so a re-mapped 8883 needs no change. Requires `openssl` in the guest (`openssl-bin`, present in G1; assumption A10 it stays).

At this point `server.key` is `0600` and owned by `egw` (uid 1000): **the broker cannot read it yet**. The broker does *not* read its key as root: Mosquitto 2.x loads the configuration file and immediately drops to its unprivileged user, and opens `keyfile`, `certfile`, `password_file` and `acl_file` only afterwards ("The only files Mosquitto will access as root are the configuration files", <https://mosquitto.org/documentation/migrating-to-2-0/>, "Use of root/privileged user"; start-up order `drop_privileges` before `listeners__start` in `src/mosquitto.c` at tag v2.0.22). In the official `eclipse-mosquitto:2.0.22` image that user is uid/gid 1883 (`docker/2.0-openssl/Dockerfile` of <https://github.com/eclipse-mosquitto/mosquitto>), and the image entrypoint's `chown -R mosquitto:mosquitto /mosquitto || true` cannot change the read-only bind mounts of `compose.yaml`. Section 5.4a hands the key over and verifies it; starting the stack before that ends in a broker restart loop (5.5).

### 5.4 Broker credentials

The guest has the broker image only as a loaded tag, so point both broker scripts at it instead of the digest-pinned reference of `images.lock.env` (which would trigger a pull):

```sh
guest$ cd /opt/egw/deployment
guest$ set -a; . ./.env; set +a
guest$ export EGW_BROKER_IMAGE=docker.io/library/eclipse-mosquitto:2.0.22
guest$ sh scripts/generate-dev-auth.sh
guest$ stat -c '%u:%g %a %n' mosquitto/config/passwd        # expected: 1883:1883 600
```

The script runs `mosquitto_passwd` as root inside a one-shot container of that image and then, still inside it, `chown mosquitto:mosquitto` and `chmod 600` on the file, so the hash file belongs to the broker's unprivileged user (uid/gid 1883) and to nobody else; the passwords travel through the environment, never through argv or files. `egw` can no longer read `passwd` — intended.

### 5.4a Broker secrets: ownership, modes and read test as the broker uid

```sh
guest$ cd /opt/egw/deployment
guest$ sh scripts/prepare-broker-secrets.sh --acl          # EGW_BROKER_IMAGE still exported from 5.4
guest$ stat -c '%u:%g %a %n' mosquitto/config/passwd mosquitto/config/acl mosquitto/config/certs/ca.key \
       mosquitto/config/certs/server.key mosquitto/config/certs/ca.crt mosquitto/config/certs/server.crt
```

Expected ownership and modes (`UNVERIFIED:` never executed):

| File | owner:group | mode | Read by |
|---|---|---|---|
| `passwd` | 1883:1883 | 600 | broker only |
| `certs/server.key` | 1883:1883 | 600 | broker only |
| `acl` (with `--acl`, guest copy only) | 1883:1883 | 640 | broker only |
| `certs/ca.key` | 1000:1000 | 600 | operator only — the broker must **not** be able to read it |
| `certs/ca.crt`, `certs/server.crt` | 1000:1000 | 644 | public material (healthcheck, controller and the 6.1 copy to the host read `ca.crt`) |

What the script does: (1) changes owner/mode only where they differ — directly as root, else through `sudo`, else (`sudo -n true` fails and there is no terminal, or `EGW_BROKER_PRIV=docker`) from a one-shot root container of the broker image, which needs no sudo because `egw` is in the `docker` group; (2) fails if any secret (`passwd`, `server.key`, `ca.key`) carries a permission bit for "others"; (3) starts a one-shot container of the broker image as `--user 1883:1883 --network none` with the same four read-only mounts as `compose.yaml` and reads `mosquitto.conf`, `acl`, `passwd`, `ca.crt`, `server.crt`, `server.key`; it also fails if that uid can read `ca.key` or if 1883 is not the image's `mosquitto` uid. Exit code 0 and the final line `OK: the broker user (1883:1883) can read ...` are the acceptance; any `ERROR:` / `FAILED: broker secrets are not ready. Do NOT start the stack.` stops the deployment here. If `sudo` is not usable on the guest (assumption A13), run `EGW_BROKER_PRIV=docker sh scripts/prepare-broker-secrets.sh --acl`. The broker keeps its default privilege drop to uid 1883 (the container's PID 1 still starts as root, reads `mosquitto.conf` and only then drops; there is no `user: root` in `compose.yaml`, which is unchanged, and no `user root` in `mosquitto.conf`), and no key is made world-readable.

`--acl` is used here because `/opt/egw/deployment` is an scp copy, not a git checkout: with `acl` owned by uid 1883 and not world-readable, Mosquitto 2.0.22 logs none of its "owner is not mosquitto" / "world readable permissions" warnings for `acl_file` (non-fatal in 2.0.22; its ChangeLog announces that future versions will refuse such files). Never use `--acl` in a git working tree. After any later `generate-dev-tls.sh --force` or `generate-dev-auth.sh`, run `prepare-broker-secrets.sh --acl` again before `up`. A later `scp -r` of the whole deployment tree over this copy (5.1) would fail on the three broker-owned files; copy single files instead.

### 5.5 Validate, ownership, start

```sh
guest$ cd /opt/egw/deployment
guest$ export EGW_BROKER_IMAGE=docker.io/library/eclipse-mosquitto:2.0.22   # needed again in a new shell: step 3b of validate-config.sh runs the broker read test
guest$ sh scripts/validate-config.sh            # step 3b = prepare-broker-secrets.sh --check (changes nothing, no sudo); step 4 reads images.lock.env for the digest-format check; compose config -q pulls nothing
guest$ stat -c '%u:%g %n' data/events           # expected 1000:1000 (created by egw); otherwise: sudo chown -R 1000:1000 data
guest$ docker compose --env-file .env --env-file images.offline.env config --images   # UNVERIFIED: --images flag in Compose 2.26; else omit
guest$ docker compose --env-file .env --env-file images.offline.env up -d
guest$ docker compose --env-file .env --env-file images.offline.env logs --no-color mosquitto | grep -E 'Error|Warning'; echo "grep exit=$? (expected 1: no such line)"
```

`validate-config.sh` must end with `OK: configuration is complete and consistent`; a failure of step 3b means the broker's unprivileged user (uid 1883) cannot read `server.key`/`passwd` or a secret is open to others — go back to 5.4a, never work around it by running the broker as root or by `chmod 644`. The last command is the post-start confirmation: a permission problem appears in the broker log as `Error: Unable to load server key file`, `Error: Unable to open pwfile` or `Error: Unable to open acl_file` (strings from the Mosquitto 2.0.22 sources), and the container then restart-loops and never becomes `healthy`, which also blocks the controller (`depends_on: service_healthy`). The 30-second healthcheck lines (`egw-healthcheck ... not authorised`) are expected and are assumed to contain neither `Error` nor `Warning` (`UNVERIFIED:` exact log wording).

**TCG start-up caveat.** The Ditto healthchecks are `start_period: 120s, interval 30s, retries 4` and the controller `depends_on` mosquitto and ditto-gateway with `condition: service_healthy` (verified compose.yaml). Under TCG the three JVMs start much more slowly than natively (`UNVERIFIED:` how much; tens of minutes is the earlier estimate); if a Ditto service is marked unhealthy before it answers `/alive`, `up -d` fails with "dependency failed to start". If that happens, do **not** touch the protocol or the compose file itself: create a documented TCG profile override `compose.tcg.yaml` (proposed, deployment PR) that only raises `start_period`/`retries` of the three Ditto healthchecks and of the controller, and run `docker compose --env-file .env --env-file images.offline.env -f compose.yaml -f compose.tcg.yaml up -d`. Record the override in the evidence; work order item 7 allows exactly this ("documented profile") and forbids silent changes to confirmation windows or loss criteria.

### 5.6 Health checks (guest)

```sh
guest$ docker compose --env-file .env --env-file images.offline.env ps
guest$ curl -s http://127.0.0.1:8000/health; echo
guest$ curl -s -o /dev/null -w '%{http_code}\n' http://127.0.0.1:8000/ready
guest$ curl -s http://127.0.0.1:8000/metrics; echo
guest$ docker compose --env-file .env --env-file images.offline.env logs --no-color --tail 20 mongodb | grep -iE 'illegal|error|Waiting for connections'
```

Expected: six services, all `healthy`; `{"status":"ok"}`; `200` (MQTT connected and Ditto reachable — CONTRACTS §5); counters at zero. `curl` must be in the image (assumption A11; `measure-cold-start.sh` line 74 needs it). Fallback if it is missing: `wget -q -O - http://127.0.0.1:8000/health` and `wget -S -q -O /dev/null http://127.0.0.1:8000/ready 2>&1 | head -n 1` (BusyBox wget, present) — but then `measure-cold-start.sh` cannot run, which is a defect of the image, not of the runbook.

Record `docker compose ps`, `docker system df -v` and `du -sh /var/lib/docker` for the sizing acceptance of item 2.

### 5.7 SSH tunnels for the loopback-only APIs (host)

Ports 8080 (Ditto gateway) and 8000 (controller) are bound to `127.0.0.1` **inside the guest**; forwarding them at the QEMU NIC would not expose them (work order item 5), so they are reached through SSH:

```bash
host$ ss -ltn | grep -E ':(8000|8080) ' && echo "host port busy: pick other local ports and adapt --controller-url"
host$ ssh -f -N -L 8000:127.0.0.1:8000 -L 8080:127.0.0.1:8080 egw-tcg
host$ curl -s -o /dev/null -w '%{http_code}\n' http://127.0.0.1:8000/ready
host$ curl -s http://127.0.0.1:8000/metrics | python3 -m json.tool
host$ curl -s -o /dev/null -w '%{http_code}\n' http://127.0.0.1:8080/health   # Ditto gateway; UNVERIFIED: exact path of the gateway health endpoint (the compose healthcheck uses port 7626 inside the container)
```

The profile's sshd drop-in keeps the tunnel alive (`ClientAliveInterval 60`, assumption A12). Stop it later with `pkill -f 'ssh -f -N -L 8000'`.

### 5.8 Environment manifest of the SUT (guest)

Until Section 9 extends the script, use the existing fields to carry the emulation label:

```sh
guest$ cd /opt/egw/deployment
guest$ EGW_PROVIDER="QEMU 8.2.7 TCG (qemu-system-native) on WSL2 Ubuntu-24.04, Windows 11 x86-64" \
       EGW_REGION="local-workstation" \
       EGW_INSTANCE_TYPE="qemu -machine virt -cpu <from runqemu log> -smp 4 -m <from runqemu log>; ARM64 EMULATED" \
       EGW_SHARED_VCPU_NOTE="TCG emulation on a shared x86-64 host; load generator co-located; never native ARM64" \
       sh scripts/capture-sut-environment.sh /opt/egw/evidence/sut_environment.json
guest$ cat /opt/egw/evidence/sut_environment.json
```

Fill the two `<from runqemu log>` values from the `Running ...` line of 3.3. Fetch it: `host$ scp egw-tcg:/opt/egw/evidence/sut_environment.json ~/egw-tcg/`.

---

## 6. First full flow (work order item 6 — the first decisive deliverable)

### 6.1 Host tooling

```bash
host$ python3 -m venv ~/egw-venv && . ~/egw-venv/bin/activate
host$ pip install -e /home/ruisth/yocto/egw/src          # paho-mqtt, jsonschema, httpx, fastapi, uvicorn (pyproject.toml)
host$ python -m egw_simulator run --help | head -n 5
host$ scp egw-tcg:/opt/egw/deployment/mosquitto/config/certs/ca.crt ~/egw-tcg/ca.crt
host$ set -a; . ~/egw-tcg/.env; set +a                   # exports MOSQUITTO_SIMULATOR_PASSWORD etc. into this shell
host$ REC="python -m egw_experiments.itest_reconcile"   # host-side helper (4.5 item 6); reuses the harness rule, see 6.4
host$ P=$HOME/egw-tcg/itest
host$ $REC --help >/dev/null && echo "helper importable"
```

The simulator must run in **WSL**, not in Windows: runqemu binds the hostfwd listeners on the WSL side's `127.0.0.1`.

### 6.2 One smartwatch at 1 Hz for 60 s

```bash
host$ RUN=itest-flow-01
host$ curl -s http://127.0.0.1:8000/metrics > $P/$RUN.metrics.before.json
host$ $REC snap --prefix $P/$RUN --label before --seed 42 --devices smartwatch     # identifies the device and records whether its twin already exists
host$ python -m egw_simulator run --scenario smoke --seed 42 --devices smartwatch --rate 1.0 --duration 60 \
        --broker 127.0.0.1 --port 8883 --username egw-simulator --password "$MOSQUITTO_SIMULATOR_PASSWORD" \
        --ca-cert ~/egw-tcg/ca.crt --egw-id egw-01 --run-id $RUN --output $P --qos 1 \
        2>&1 | tee $P/$RUN.stderr.txt; $REC mark $P/$RUN
```

With `--devices smartwatch` the 1:0.2:10 split is renormalised over the selected type, so `--rate 1.0` is exactly 1 Hz (simulator README). The `--port` is the forwarded host port (2222/8883 or the re-mapped values). Expected stderr: `tls=True qos=1 ... devices=smartwatch` and finally `done sent=60 intended_invalid=0 buffered_dropout=0 dropout_disconnects=0` (±1 at the boundary). Exit code 0. TLS verification stays on (paho `tls_set(ca_certs=...)`, no insecure flag in `publisher.py`, verified).

`$REC mark` must be the very next command after the simulator, on the same line: it reads the controller's `monotonic_ns` from `GET /metrics` with the harness's own `poll_controller_marker` (`run.py`) and fixes the confirmation deadline at marker + `CONFIRMATION_WINDOW_S` (60 s, `protocol.py` line 58) **on the controller clock**, the same arithmetic as `egw_experiments run` (`run.py`, `confirmation_deadline_monotonic_ns`, clock domain `"controller"`). The marker file `$P/$RUN.marker.json` is write-once (a second poll would move the deadline later). `mark` prints the lag between the simulator's `finished_utc` and the poll; above 2 s (`CONTROLLER_MARKER_LAG_TOLERANCE_S`) the effective window was longer than the protocol's and the result must be reported with that lag. The `before` snapshot shows `exists: false` on the first use of seed 42 on this MongoDB volume and the accumulated state on any repetition; both are valid starting points for the checks below. Both `/metrics` and the twin snapshot go through the tunnels of 5.7.

### 6.3 Controller and Ditto through the tunnel

```bash
host$ $REC wait $P/$RUN     # returns when the CONTROLLER clock has passed marker + 60 s; replaces a host-side sleep
host$ curl -s http://127.0.0.1:8000/metrics | tee $P/$RUN.metrics.after.json | python3 -m json.tool
host$ $REC snap --prefix $P/$RUN --label after
host$ UUID=$(python3 -c "import json;print(json.loads(open('$HOME/egw-tcg/itest/$RUN/sent_events.jsonl').readline())['device_uuid'])")
host$ curl -s -H 'x-ditto-pre-authenticated: pre:egw-controller' "http://127.0.0.1:8080/api/2/things/org.c2dta:$UUID" | python3 -m json.tool | tee $P/$RUN.twin.json
```

Expected twin (CONTRACTS §4): `thingId org.c2dta:<uuid>`, attributes `device_type: smartwatch`, `egw_id: egw-01`, `schema_version`; features `vitals` (heart_rate_bpm), `location` (lat, lon), `ingestion` with `last_run_id: itest-flow-01` and `last_seq` = the highest accepted `seq` of this run (59 when 60 events were sent and accepted). `accepted_count` is **cumulative over the life of the twin** (it survives runs, controller restarts and guest reboots; only deleting the thing or the `mongodb-data` volume resets it), so its absolute value is 60 only when the `before` snapshot shows `exists: false`; the acceptance is the before/after difference computed in 6.4. The `/metrics` counters are per controller **process** (zero again after every controller restart) and global over all run ids, so they too are read as a before/after difference, valid only while `started_at` is the same in both snapshots.

### 6.4 Reconcile sent, processed, confirmed — protocol rule, controller clock

```bash
host$ scp "egw-tcg:/opt/egw/deployment/data/events/$RUN/events.jsonl" $P/$RUN/events.jsonl    # only after '$REC wait' returned
host$ $REC check $P/$RUN     # harness accounting (egw_experiments.analyze.compute_run_metrics) with the marker deadline
host$ $REC delta $P/$RUN     # per-device twin delta and per-process /metrics delta against events.jsonl
```

`check` does not re-implement the rule: it places copies of `sent_events.jsonl` and `events.jsonl` and a manifest carrying `confirmation_deadline_monotonic_ns` (marker + `CONFIRMATION_WINDOW_S`) with `confirmation_deadline_clock_domain: "controller"` in `$P/$RUN.reconcile/` (labelled `itest-adhoc-reconcile (NOT a harness run)`) and calls the harness's unmodified `compute_run_metrics`. A message is delivered only if an `accepted` record for its `message_id` has `ditto_ack_monotonic_ns` ≤ the deadline; a later confirmation leaves the message **lost** and is reported separately under `late_confirmations` (`analyze.py`: `ack > deadline_ns`); `duplicate` outcomes and repeated `accepted` records (`double_accepted`) never add deliveries. Waiting longer before the fetch therefore changes nothing: the wait only ensures that every in-window confirmation is already in the file. The result is printed and saved as `$P/$RUN.reconcile.json`.

Acceptance (protocol compliance, plan §7.3 / CONTRACTS §9): `confirmation_deadline_source = controller-marker`; `lost = 0`; `delivered_unique = sent_valid`; `late_confirmations = 0`; `double_accepted = 0`; `intended_invalid_accepted = 0`; `marker_lag_s` ≤ 2 s (otherwise state the lag next to the result). `late_confirmations > 0` with `lost > 0` is a finding about the emulated guest's speed and is reported as measured; it is never turned into a pass by waiting longer. Latency is printed only with the emulated label.

Acceptance (counters): every `delta` line ends in `OK` — per device, Δ`accepted_count` between the `before` and `after` snapshots equals the number of `accepted` records of that device in `events.jsonl` (all of them, late ones included, because the controller increments the counter once per accepted outcome), `last_run_id` is this run and `last_seq` its highest accepted `seq`; per controller process, the `/metrics` deltas of `accepted`, `rejected`, `duplicate` and `failed` equal the outcome counts of `events.jsonl`, and `dropped` did not move. A `queue_depth` other than 0 in the `after` snapshot means the controller was still draining: fetch again and take new snapshots under another label (`--to`).

If `mark` could not read the marker (controller unreachable at the end of the run), this step can only be labelled an **eventual-delivery check, not protocol compliance**: `check` then falls back to the harness's legacy event-derived deadline, prints `NOT a protocol check` and exits 3 (`wait` has no marker to wait for in that case; a plain `sleep 65` before the fetch is then only a fetch delay and proves nothing about the 60 s window). Prefer repeating the run under a new run id.

### 6.5 Restart the services and verify twin persistence

```bash
host$ ssh egw-tcg 'cd /opt/egw/deployment && docker compose --env-file .env --env-file images.offline.env down && docker compose --env-file .env --env-file images.offline.env up -d'
# wait for /ready = 200 through the tunnel (re-open the tunnel if the ssh session dropped), then:
host$ $REC snap --prefix $P/$RUN --label post-restart --like after
host$ $REC same --prefix $P/$RUN after post-restart
host$ curl -s http://127.0.0.1:8000/metrics | python3 -m json.tool      # new started_at, all counters 0: /metrics is per process and is not persisted
```

`down` (without `-v`) keeps `mongodb-data` and `mosquitto-data`; `same` must report every device `identical` (the whole `ingestion` feature, `accepted_count` included, lives in the twin). A `down -v` is the destructive reset reserved for cold-start repetitions and is limited to those two named volumes (work order item 8: destructive resets only on identified test volumes); it is also the only operation in this runbook that returns `accepted_count` to zero.

### 6.6 Save the evidence

```bash
host$ EVR=~/egw-tcg/evidence/flow-01-$(date -u +%Y%m%dT%H%M%SZ) && mkdir -p $EVR/guest
host$ cp ~/yocto/logs/$BOOT.log $EVR/                                   # console + runqemu command line
host$ cp ~/egw-tcg/evidence/build-*/SHA256SUMS.artefacts ~/egw-tcg/evidence/build-*/qemu_version.txt ~/egw-tcg/evidence/build-*/source_commit.txt $EVR/
host$ cp -r $P/$RUN $P/$RUN.* $EVR/        # run directory plus its siblings: stderr, marker, window-closed, metrics/twins snapshots, twin.json, reconcile.json, reconcile/
host$ cp ~/egw-tcg/sut_environment.json ~/egw-images/archive-identity.txt ~/egw-images/SHA256SUMS $EVR/
host$ ssh egw-tcg 'cd /opt/egw/deployment && docker compose --env-file .env --env-file images.offline.env ps > /opt/egw/evidence/compose-ps.txt; docker compose --env-file .env --env-file images.offline.env logs --no-color > /opt/egw/evidence/compose-logs.txt; docker info > /opt/egw/evidence/docker-info.txt; docker compose version > /opt/egw/evidence/compose-version.txt; docker image inspect --format "{{.RepoTags}} {{.Id}} {{.Architecture}}" $(docker images -q | sort -u) > /opt/egw/evidence/image-identities.txt; cp .env.example /opt/egw/evidence/; cp images.lock.env images.offline.env /opt/egw/evidence/ 2>/dev/null; cp mosquitto/config/certs/ca.crt /opt/egw/evidence/'
host$ scp -r egw-tcg:/opt/egw/evidence/ $EVR/guest/
host$ (cd $EVR && find . -type f ! -name SHA256SUMS -exec sha256sum {} + > SHA256SUMS)
```

Never copy `.env`, `mosquitto/config/passwd`, `ca.key`, `server.key` or `~/.ssh/egw_campaign*` into `$EVR`. Write `$EVR/README.md` with the Section 0 label, the runqemu command line, the image identities and the reconciliation numbers. This directory, not the G1 capsule, is where the integrated evidence accumulates; when sealed it goes under `docs/evidence/<new-name>/` in the deployment/test PR, never inside `docs/evidence/g1-yocto-qemu/`.

---

## 7. The nine integration tests (work order item 8)

Principles: real stack, existing simulator and harness only (no fakes); run ids prefixed `itest-` so they can never be confused with `campaign_plan.json` run ids; every test produces a directory under `~/egw-tcg/itest/` plus the fetched `events.jsonl`, twin-ingestion and `/metrics` snapshots before and after, the controller marker and the `reconcile.json` produced by the harness accounting; destructive actions are limited to `docker compose stop/restart/down` and to the two named volumes; the emulated label applies to every artefact. Common shell preamble (host, in the venv, after `set -a; . ~/egw-tcg/.env; set +a`):

```bash
host$ P=$HOME/egw-tcg/itest; REC="python -m egw_experiments.itest_reconcile"
host$ SIM="python -m egw_simulator run --broker 127.0.0.1 --port 8883 --username egw-simulator --password $MOSQUITTO_SIMULATOR_PASSWORD --ca-cert $HOME/egw-tcg/ca.crt --egw-id egw-01 --output $P --qos 1"
host$ fetch() { scp "egw-tcg:/opt/egw/deployment/data/events/$1/events.jsonl" $P/$1/events.jsonl; }
host$ metrics() { curl -s http://127.0.0.1:8000/metrics > $P/$1.metrics.$2.json; }
host$ twin() { curl -s -H 'x-ditto-pre-authenticated: pre:egw-controller' "http://127.0.0.1:8080/api/2/things/org.c2dta:$2" > $P/$1.twin.$2.json; }
host$ drained() { local i a b; for i in $(seq 1 60); do a=$(curl -s http://127.0.0.1:8000/metrics | python3 -c "import json,sys;m=json.load(sys.stdin);print(m['queue_depth'],*(m[k] for k in ('accepted','rejected','duplicate','failed','dropped')))") || return 1; [ "${a%% *}" = 0 ] && [ "$a" = "$b" ] && return 0; b=$a; sleep 5; done; echo "controller NOT drained after 300 s (queue_depth and counters: $a): do not start the next run" >&2; return 1; }
host$ pre()  { drained && metrics $1 before && $REC snap --prefix $P/$1 --label before --seed $2 ${3:+--devices $3}; }      # pre <run-id> <seed> [device types, comma-separated]
host$ post() { $REC mark $P/$1 && $REC wait $P/$1 && fetch $1 && metrics $1 after && $REC snap --prefix $P/$1 --label after && { $REC check $P/$1; $REC delta $P/$1; }; }
```

Every ad-hoc test has the shape `pre <run-id> <seed>; $SIM ... --seed <seed> --run-id <run-id>; post <run-id>`, with `post` as the very next command after the simulator so that the marker is read at the end of the run. `post` applies the confirmation deadline on the controller clock through the harness's own accounting (6.4) and compares counters only as before/after differences: the twins' `accepted_count` is cumulative per device over the life of the twin, the simulator derives the device identities from the seed alone (one device per type, `egw_simulator/devices.py`; there is no device-id option), and several tests share seed 42, so an absolute `accepted_count` never describes a single run. The `before` snapshot records `exists: true|false` per device, so freshness is documented rather than assumed. If `mark` fails, `post` stops: that run can then only be described as an eventual-delivery observation, not as protocol compliance. `pre` first calls `drained`: it takes the `before` snapshots only after two consecutive `/metrics` readings 5 s apart show `queue_depth 0` and identical counters (`queue_depth` is the queue size only — `service.py` `queue_depth()` — so the message being processed is not in it; the unchanged counters cover that one). Without this, a backlog of the previous run that outlives its 60 s window under TCG would be logged to the previous run's `events.jsonl` but counted in this run's Δ`accepted_count` and `/metrics` differences: a false `MISMATCH` (never a false `OK`), since `delta` itself checks `queue_depth` only in the `to` snapshot. If `drained` gives up after 300 s, `pre` stops and the run must not be started; that is a sizing observation for Section 8. `UNVERIFIED:` never executed.

**No test file in `src/tests/` carries the `integration` marker today** (verified: `pyproject.toml` defines the marker with `-m 'not integration'` in `addopts`, but `grep pytest.mark.integration src/tests` finds nothing). The tests below are therefore operator-driven with the simulator/harness; turning them into `@pytest.mark.integration` tests that read `EGW_*` from the environment is a candidate for the deployment/test PR, not a prerequisite.

### Test 1 — repeated smoke, complete artefacts

```bash
host$ for i in 01 02 03; do R=itest-smoke-$i; pre $R 42; $SIM --scenario smoke --seed 42 --run-id $R 2>&1 | tee $P/$R.stderr.txt; post $R; done
```

Expected per run: exit 0, `lost = 0`, `late_confirmations = 0`, `delivered_unique = sent_valid`, all three device types, `sent ≈ 336` (30 s x 11.2 msg/s), every `delta` line `OK` (the three runs share seed 42, so the second and third start from `exists: true` and a non-zero `accepted_count`). Note that 11.2 msg/s under TCG may already stress the guest; if `lost > 0` appears, this is the first sizing finding of the pilot (Section 8), not a reason to change the protocol.

Then one run through the **harness** to prove the artefact chain (events fetch, SUT environment, collector hooks) on this guest. The harness only accepts run ids from a plan, so generate a *pilot* plan in a separate directory (never `experiments/campaign_plan.json`):

```bash
host$ python -m egw_experiments plan --master-seed 42 --output ~/egw-tcg/pilot/campaign_plan.json
host$ python3 -c "import json;p=json.load(open('$HOME/egw-tcg/pilot/campaign_plan.json'));print([r['run_id'] for r in p['runs'] if r.get('condition_id')=='smoke_sequence'][:3])"   # plan entries carry condition_id (plan_gen.py _run_entry); expected ['smoke_sequence-r01', 'smoke_sequence-r02', 'smoke_sequence-r03']
host$ RID=smoke_sequence-r01        # run ids are deterministic: '{condition_id}-rNN' (plan_gen.py line 93), so the literal is safe
host$ python -m egw_experiments run --run-id $RID --plan ~/egw-tcg/pilot/campaign_plan.json --base-dir ~/egw-tcg/pilot/results \
        --broker 127.0.0.1 --port 8883 --username egw-simulator --password "$MOSQUITTO_SIMULATOR_PASSWORD" --ca-cert ~/egw-tcg/ca.crt \
        --controller-url http://127.0.0.1:8000 \
        --sut-env-from ~/egw-tcg/sut_environment.json \
        --fetch-events-cmd 'scp egw-tcg:/opt/egw/deployment/data/events/{run_id}/events.jsonl {dest}' \
        --collector-start-cmd "ssh egw-tcg 'sudo systemd-run --unit egw-resources-{run_id} --collect sh /opt/egw/deployment/scripts/collect-resources.sh /tmp/resources-{run_id}.csv --duration {duration_s}'" \
        --collector-stop-cmd  "ssh egw-tcg 'sudo systemctl stop egw-resources-{run_id}'" \
        --collector-fetch-cmd 'scp egw-tcg:/tmp/resources-{run_id}.csv {dest}'
```

Expected: `manifest.json` with `validity: "valid"`, `SHA256SUMS` written, `resources.csv` with the `host` column equal to the guest hostname (the harness rejects it otherwise — `collect-resources.sh` header), `controller_metrics.csv`, `sut_environment.json` copied in. `sudo systemd-run` is used because the collector must outlive the SSH session and stop cleanly on `systemctl stop`; `egw` has NOPASSWD sudo (assumption A13). A 30 s smoke satisfies the collector's minimum of 30 distinct instants only just; if the run is marked invalid for coverage, repeat with `--run-id` of a nominal entry and `--duration` untouched (the plan fixes durations). The harness applies the confirmation deadline itself (manifest `confirmation_deadline_clock_domain: "controller"`), so no `pre`/`post` is used here; read the result with `python -m egw_experiments analyze --base-dir ~/egw-tcg/pilot/results --plan ~/egw-tcg/pilot/campaign_plan.json` and the columns `confirmation_deadline_source`, `sent_valid`, `delivered_unique`, `lost`, `late_confirmations`, `double_accepted` of `~/egw-tcg/pilot/results/processed/per_run.csv` (acceptance rows of conditions that were not run are expected to fail on completeness in a pilot tree).

### Test 2 — three wearables, valid events and correct twin properties

```bash
host$ R=itest-3dev-01; pre $R 7; $SIM --scenario smoke --seed 7 --duration 60 --run-id $R; post $R
host$ for U in $(python3 -c "import json;print(' '.join(sorted({json.loads(l)['device_uuid'] for l in open('$HOME/egw-tcg/itest/$R/sent_events.jsonl')})))"); do twin $R $U; done
host$ python3 - ~/egw-tcg/itest/$R.twin.*.json <<'EOF'
import json, sys
want = {"smartwatch": {"vitals": ["heart_rate_bpm"], "location": ["lat", "lon"]},
        "smart_ring": {"thermo": ["skin_temp_c"], "oximetry": ["spo2_pct"]},
        "smart_clothing": {"motion": ["accel_x", "accel_y", "accel_z"], "respiration": ["breathing_rpm"]}}
for f in sys.argv[1:]:
    t = json.load(open(f)); dt = t["attributes"]["device_type"]; feats = t["features"]
    missing = [(fe, p) for fe, props in want[dt].items() for p in props if p not in feats.get(fe, {}).get("properties", {})]
    ing = feats["ingestion"]["properties"]
    print(f, dt, "policyId" , t.get("policyId"), "missing:", missing, "ingestion:", {k: ing.get(k) for k in ("last_run_id", "last_seq", "accepted_count")})
EOF
```

Expected: three twins, `policyId == thingId`, no missing feature property, attributes `egw_id`/`schema_version` present, `lost = 0` and `late_confirmations = 0` from `check`, and every `delta` line `OK` (per device, Δ`accepted_count` = that device's accepted records in `events.jsonl`; seed 7 is used by no other test, so on the first execution the `before` snapshot shows the three seed-7 twins with `exists: false` and the absolute values printed by the inline script equal the deltas — on a repetition only the deltas hold).

### Test 3 — invalid payloads: controlled rejection, no undue twin change

```bash
host$ R=itest-invalid-01; pre $R 42; $SIM --scenario invalid-payload --seed 42 --duration 120 --run-id $R; post $R
host$ python3 - ~/egw-tcg/itest/$R <<'EOF'
import json, sys
d = sys.argv[1]
sent = {json.loads(l)["message_id"]: json.loads(l) for l in open(f"{d}/sent_events.jsonl")}
ev = [json.loads(l) for l in open(f"{d}/events.jsonl")]
inv = {m for m, s in sent.items() if s.get("intended_invalid")}
rej = {e["message_id"] for e in ev if e["outcome"] == "rejected"}
acc = {e["message_id"] for e in ev if e["outcome"] == "accepted"}
print("intended_invalid:", len(inv), "rejected:", len(rej), "intended_invalid accepted:", len(inv & acc), "valid rejected:", len(rej - inv))
EOF
```

Expected: `intended_invalid accepted = 0`, `valid rejected = 0`, `rejected == intended_invalid` (1 in 20 per device, deterministic; `check`: `rejected_intended_invalid = intended_invalid_sent`, `intended_invalid_accepted = 0`, `rejected_valid = 0`; `delta`: `/metrics rejected` difference = rejected records, twin Δ`accepted_count` = accepted records only), controller stderr (`docker compose logs controller`) shows schema-validation rejections, and each twin's `last_seq` equals the last *valid* seq of that device (rejected events never reach Ditto — CONTRACTS §5).

### Test 4 — duplicates and sequence per the idempotence contract

The simulator has no replay scenario, but it is deterministic: the same scenario, seed, run id, egw id, devices, rate and duration produce byte-identical `message_id`s (UUID v5 of `run_id:device_uuid:seq`). Publish the same run twice, the second time into a different output directory (the write-once guard refuses the same `--output`):

```bash
host$ R=itest-dup-01; pre $R 42; $SIM --scenario smoke --seed 42 --duration 60 --run-id $R; post $R
host$ cp $P/$R.reconcile.json $P/$R.reconcile.pre-replay.json; cp $P/$R/events.jsonl $P/$R.events.pre-replay.jsonl   # keep the pre-replay accounting: the second fetch and the second check below overwrite both originals
host$ python -m egw_simulator run --scenario smoke --seed 42 --duration 60 --run-id $R --output ~/egw-tcg/itest-replay \
        --broker 127.0.0.1 --port 8883 --username egw-simulator --password "$MOSQUITTO_SIMULATOR_PASSWORD" --ca-cert ~/egw-tcg/ca.crt --egw-id egw-01 --qos 1
host$ sleep 65; metrics $R replay; python3 -c "import json;print('queue_depth', json.load(open('$P/$R.metrics.replay.json'))['queue_depth'])"    # plain drain wait, not a deadline: the replay can add no delivery; repeat until queue_depth is 0
host$ fetch $R; $REC snap --prefix $P/$R --label replay; $REC same --prefix $P/$R after replay
host$ python3 -c "import json;a=json.load(open('$P/$R.metrics.after.json'));b=json.load(open('$P/$R.metrics.replay.json'));print({k:b[k]-a[k] for k in ('accepted','rejected','duplicate','failed','dropped')},'same controller process:',a['started_at']==b['started_at'])"
host$ $REC check $P/$R      # again, on the re-fetched log: duplicates = replayed messages, double_accepted = 0, delivered_unique unchanged
host$ cp $P/$R.reconcile.json $P/$R.reconcile.post-replay.json
host$ python3 -c "import json;a=json.load(open('$P/$R.reconcile.pre-replay.json'));b=json.load(open('$P/$R.reconcile.post-replay.json'));[print(k,'pre-replay',a[k],'post-replay',b[k],'' if k=='duplicates' else ('UNCHANGED' if a[k]==b[k] else 'CHANGED')) for k in ('sent_valid','delivered_unique','lost','late_confirmations','double_accepted','duplicates')]"
host$ python3 -c "
import json,collections; ev=[json.loads(l) for l in open('$HOME/egw-tcg/itest/$R/events.jsonl')]; print(collections.Counter(e['outcome'] for e in ev)); print('accepted unique:', len({e['message_id'] for e in ev if e['outcome']=='accepted'}), 'accepted total:', sum(e['outcome']=='accepted' for e in ev))"
```

Expected: after the replay, `duplicate` equals the number of replayed messages (every replayed event has a known `message_id` and a `seq <= last_seq` within the same `run_id` — CONTRACTS §4; the per-device LRU holds 1024 ids and a 60 s smoke sends at most 600 per device, so both mechanisms apply), `accepted unique == accepted total` (no double acceptance; `check`: `double_accepted = 0`, and the side-by-side line prints `delivered_unique`, `lost`, `late_confirmations` and `double_accepted` as `UNCHANGED` between `<run>.reconcile.pre-replay.json` and `<run>.reconcile.post-replay.json` — `check` rewrites `<run>.reconcile.json` and rebuilds `<run>.reconcile/` on every call and the second `fetch` overwrites `events.jsonl`, so the two copies and `<run>.events.pre-replay.jsonl` are the saved artefacts of this comparison), `same` reports the three twins `identical` between the `after` and `replay` snapshots (a duplicate never patches the twin), and the `/metrics` difference between those two snapshots is `accepted 0` and `duplicate` = number of replayed messages, with `queue_depth 0` and the same `started_at`. Then the **sequence reset**: `pre itest-dup-02 42; $SIM --scenario smoke --seed 42 --duration 60 --run-id itest-dup-02; post itest-dup-02` must give `lost = 0` and every `delta` line `OK`, proving the run-scoped seq floor.

### Test 5 — MQTT disconnect/reconnect: real disconnection, buffering, reconciliation

```bash
host$ R=itest-dropout-01; pre $R 42; $SIM --scenario dropout-reconnect --seed 42 --duration 180 --run-id $R 2>&1 | tee $P/$R.stderr.txt; post $R
host$ python3 -c "import json;m=json.load(open('$HOME/egw-tcg/itest/$R/manifest.json'));print(m.get('note'))"
host$ ssh egw-tcg "cd /opt/egw/deployment && docker compose --env-file .env --env-file images.offline.env logs --no-color mosquitto | grep -E 'egw-simulator-$R'" > ~/egw-tcg/itest/$R.broker.txt; wc -l ~/egw-tcg/itest/$R.broker.txt
```

Expected: stderr `dropout_disconnects = N` with N ≈ 3 (one window per minute, `dropout_windows`), `buffered_dropout > 0`; the manifest carries the `DROPOUT_SCOPE_NOTE`; the broker log shows N+1 connections and N disconnections for the client id `egw-simulator-<run_id>` (`UNVERIFIED:` exact Mosquitto wording — "New client connected from ... as egw-simulator-..." and "Client egw-simulator-... disconnected"/"closed its connection"); `lost = 0` and `late_confirmations = 0` under the controller-clock deadline (buffered events are published late but must be confirmed inside the window), and every `delta` line `OK`. If `lost > 0`, `late_confirmations` says directly how many accepted records were confirmed after the deadline — a guest-speed finding under TCG, reported as measured; `duplicates` (QoS 1 redelivery after reconnect) are not failures, `double_accepted` must be 0.

### Test 6 — controller restart with recovery and traceability

Use the harness hook so the restart instant is recorded in the manifest, with the pilot plan's first `controller_restart` run id:

```bash
host$ RID=controller_restart-r01    # deterministic (controller_restart-r01..r03); the condition is 600 s nominal, so --restart-at-s 300 is mid-run (protocol.py)
host$ SEED=$(python3 -c "import json;p=json.load(open('$HOME/egw-tcg/pilot/campaign_plan.json'));print(next(r['seed'] for r in p['runs'] if r['run_id']=='$RID'))")
host$ drained && $REC snap --prefix $P/$RID --label before --seed $SEED          # the plan's derived seed, not 42: these are other devices
host$ python -m egw_experiments run --run-id $RID --plan ~/egw-tcg/pilot/campaign_plan.json --base-dir ~/egw-tcg/pilot/results \
        --broker 127.0.0.1 --port 8883 --username egw-simulator --password "$MOSQUITTO_SIMULATOR_PASSWORD" --ca-cert ~/egw-tcg/ca.crt \
        --controller-url http://127.0.0.1:8000 --sut-env-from ~/egw-tcg/sut_environment.json \
        --fetch-events-cmd 'scp egw-tcg:/opt/egw/deployment/data/events/{run_id}/events.jsonl {dest}' \
        --collector-start-cmd "ssh egw-tcg 'sudo systemd-run --unit egw-resources-{run_id} --collect sh /opt/egw/deployment/scripts/collect-resources.sh /tmp/resources-{run_id}.csv --duration {duration_s}'" \
        --collector-stop-cmd "ssh egw-tcg 'sudo systemctl stop egw-resources-{run_id}'" --collector-fetch-cmd 'scp egw-tcg:/tmp/resources-{run_id}.csv {dest}' \
        --restart-cmd "ssh egw-tcg 'cd /opt/egw/deployment && docker compose --env-file .env --env-file images.offline.env restart controller'" --restart-at-s 300
host$ $REC snap --prefix $P/$RID --label after
host$ $REC delta ~/egw-tcg/pilot/results/raw/$RID --prefix $P/$RID     # twins only: no /metrics snapshots are given, and the process counters restart from zero at the restart anyway
host$ python -m egw_experiments analyze --base-dir ~/egw-tcg/pilot/results --plan ~/egw-tcg/pilot/campaign_plan.json
```

(Manual equivalent without the harness: `pre <id> 42; $SIM --scenario nominal --seed 42 --duration 600 --run-id <id>; post <id>` and, at 300 s, the same `ssh ... restart controller` from a second terminal; `delta` then reports that the controller process restarted and skips the `/metrics` comparison.) The confirmation deadline is applied by the harness itself (`per_run.csv`: `confirmation_deadline_source = controller-marker`, `lost`, `late_confirmations`, `double_accepted = 0`, `restart_*` columns). Every `delta` line must be `OK`: across the restart each twin's `accepted_count` grew by exactly that device's accepted records, i.e. the counter continued from the value stored in the twin instead of restarting — the traceable evidence that the dedupe state was rebuilt from the `ingestion` feature. `/metrics` counters are per process; they restart from zero at the restart and are not compared across it. (`controller_restart` has `warmup_s=0`. For a condition with a warm-up, such as `nominal`, the warm-up runs under the run id `<run_id>.warmup` with the same seed (`run.py`, warm-up note), so it patches the same twins, and its log exists only on the guest: the controller writes one file per run id and the harness fetch hook copies the measured run's file only. Fetch it and pass it to `delta`, with `RID` set to that condition's run id and the `before` snapshot taken before the harness run, as above — `UNVERIFIED:` never executed:

```bash
host$ scp "egw-tcg:/opt/egw/deployment/data/events/$RID.warmup/events.jsonl" $P/$RID.warmup.events.jsonl
host$ $REC delta ~/egw-tcg/pilot/results/raw/$RID --prefix $P/$RID --also $P/$RID.warmup.events.jsonl
```

Without `--also`, every device line of such a run is a `MISMATCH` by exactly the warm-up's accepted records.) `UNVERIFIED:` that the controller's `time.monotonic_ns()` continues across a *container* restart (kernel `CLOCK_MONOTONIC`, no time namespace by default; reasoned, not observed) — the marker is read after the run in any case. Expected evidence: the manifest's restart record with timestamps and exit code 0; `controller_metrics.csv` with a sampling gap or counter reset around the restart and samples resuming within 120 s (`RESTART_RECOVERY_MAX_S`, protocol.py); `events.jsonl` continues in the same file (the logger opens it in append mode — `events.py` line 108) with no `message_id` accepted twice (dedupe state is rebuilt from the twin's `ingestion` feature); the delivery loss across the restart, if any, is reported as measured, never suppressed.

### Test 7 — temporary Ditto/MongoDB failure: fault handling and recovery per contract

```bash
host$ R=itest-mongo-fault-01
host$ ( sleep 90; ssh egw-tcg 'cd /opt/egw/deployment && docker compose --env-file .env --env-file images.offline.env stop mongodb'; date -u; sleep 45; ssh egw-tcg 'cd /opt/egw/deployment && docker compose --env-file .env --env-file images.offline.env start mongodb'; date -u ) > ~/egw-tcg/itest/$R.fault.txt 2>&1 &
host$ ( while :; do printf '%s %s\n' "$(date -u +%FT%TZ)" "$(curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:8000/ready)"; sleep 2; done ) > ~/egw-tcg/itest/$R.ready.txt &
host$ pre $R 42; $SIM --scenario nominal --seed 42 --duration 300 --run-id $R; post $R; kill %2
host$ python3 -c "import json,collections;ev=[json.loads(l) for l in open('$HOME/egw-tcg/itest/$R/events.jsonl')];print(collections.Counter((e['outcome'],e.get('attempts')) for e in ev)); print([e['error'] for e in ev if e['outcome']=='failed'][:3])"
```

Expected: during the 45 s outage the controller records `failed` outcomes with `attempts: 3` and a 5xx/timeout `error` (bounded retry, CONTRACTS §5) — or, if Ditto's things service answers 4xx, `failed` with `attempts: 1`; `/ready` may drop to 503 if the gateway stops answering (record either); after `start mongodb` accepted outcomes resume and every `delta` line is `OK`: per device, Δ`accepted_count` between the `before` and `after` snapshots equals the accepted records of this run (the absolute value also contains every earlier seed-42 run, so it is never compared with this run alone), and the `/metrics` differences of `accepted` and `failed` equal the outcome counts provided `started_at` is unchanged (the controller is not restarted in this test). `lost` is reported together with the quantities `check` and `delta` print next to it: `failed` (bounded retry exhausted, CONTRACTS §5), `late_confirmations` (confirmed after the controller-clock deadline) and the `/metrics` `dropped` difference (queue overflow). `lost` need not equal `failed`: `lost` is "valid sent without a unique in-window confirmation" (`analyze.py`), so it also contains late confirmations, queue-overflow drops and messages that never reached the controller, none of which is a `failed` record. That is the contract's behaviour, to be reported, not hidden. `UNVERIFIED:` if Ditto applies a patch whose 2xx answer is lost, the event is `failed` while the twin was already changed; whether the per-device delta then still closes has not been observed — report a `MISMATCH` as measured. Repeat once with `stop ditto-things` instead of `mongodb` (`itest-ditto-fault-01`). `UNVERIFIED:` which of the two error shapes Ditto 3.9.4 produces when MongoDB is down.

### Test 8 — guest reboot: stack start-up and persistence

```bash
host$ $REC snap --prefix $P/itest-reboot --label pre-reboot --seed 42          # all three seed-42 twins, whatever earlier tests left in them
host$ ssh egw-tcg 'sudo journalctl --list-boots | tail -n 2; ls /opt/egw/deployment/data/events; sudo systemctl reboot'
# QEMU exits (-no-reboot). Re-launch exactly as in 3.3 (./scripts/run-qemu-integrated.sh <new run name>) with the SAME data-disk file
# (default $HOME/yocto/egw-integrated/egw-data.img — do not touch EGW_DATA_DISK between the two boots), then:
host$ ssh egw-tcg 'systemctl is-system-running; systemctl --failed --no-legend; sudo journalctl --list-boots | tail -n 3; sudo journalctl -b -1 -u docker.service --no-pager | tail -n 5; docker ps --format "{{.Names}} {{.Status}}"; ls /opt/egw/deployment/data/events; df -h / /var/lib/docker; findmnt -no SOURCE /var/lib/docker'
host$ ssh -f -N -L 8000:127.0.0.1:8000 -L 8080:127.0.0.1:8080 egw-tcg
host$ $REC snap --prefix $P/itest-reboot --label post-reboot --like pre-reboot      # only after /ready = 200 through the new tunnel
host$ $REC same --prefix $P/itest-reboot pre-reboot post-reboot
host$ R=itest-post-reboot-01; pre $R 42; $SIM --scenario smoke --seed 42 --duration 30 --run-id $R; post $R
```

Expected: the six containers come back on their own (`restart: unless-stopped` plus `docker.service` enabled), `sudo journalctl --list-boots` shows the previous boot (persistent journal — assumption A14; `sudo` is required because `egw` is not in the `systemd-journal` group and would otherwise see only its user journal), `/var/lib/docker` is again on `/dev/vdb`, `same` reports the three seed-42 twins `identical` across the reboot (the comparison is between the two snapshots; the values themselves are whatever the earlier tests accumulated — a snapshot taken before any seed-42 run would show `exists: false` and prove nothing, so run this test after 6.2 or test 1), old `data/events/*` directories are intact, and the fresh smoke run gives `lost = 0`, `late_confirmations = 0` and every `delta` line `OK`, starting from the persisted `accepted_count`; `/metrics` starts from zero with a new `started_at` (new controller process), and the controller's monotonic clock restarted with the guest, which is harmless because each run's marker is read after that run. No manual step between reboot and a working stack is the acceptance of work order item 3.

### Test 9 — TLS and authorisation: wrong certificate, credentials and topics rejected

```bash
# (a) wrong CA -> TLS verification fails
host$ openssl req -x509 -newkey rsa:2048 -nodes -keyout /tmp/wrong.key -out /tmp/wrong.crt -days 1 -subj '/CN=wrong' 2>/dev/null
host$ python -m egw_simulator run --scenario smoke --seed 42 --duration 10 --run-id itest-tls-wrongca --output ~/egw-tcg/itest --broker 127.0.0.1 --port 8883 --username egw-simulator --password "$MOSQUITTO_SIMULATOR_PASSWORD" --ca-cert /tmp/wrong.crt; echo "exit=$?"
# (b) wrong password -> CONNACK not authorised
host$ python -m egw_simulator run --scenario smoke --seed 42 --duration 10 --run-id itest-auth-wrongpw --output ~/egw-tcg/itest --broker 127.0.0.1 --port 8883 --username egw-simulator --password wrong --ca-cert ~/egw-tcg/ca.crt; echo "exit=$?"
# (c) plaintext against the TLS listener
host$ python -m egw_simulator run --scenario smoke --seed 42 --duration 10 --run-id itest-notls --output ~/egw-tcg/itest --broker 127.0.0.1 --port 8883 --no-tls --username egw-simulator --password "$MOSQUITTO_SIMULATOR_PASSWORD"; echo "exit=$?"
# the broker log is the actual evidence for (b) and (c): the simulator discards the CONNACK reason
host$ ssh egw-tcg 'cd /opt/egw/deployment && docker compose --env-file .env --env-file images.offline.env logs --no-color --tail 20 mosquitto' | tee ~/egw-tcg/itest/itest-auth.broker.txt
# (d)+(e) ACL proven in both directions with concurrent known traffic, and anonymous refusal. Runs in the guest, inside the
# broker container (mosquitto_pub/mosquitto_sub of the image; nothing to install on the host; no 'timeout' applet needed).
# Precondition: no simulator/harness run in progress and the last one fully drained (queue_depth 0 in /metrics).
host$ T=$(date -u +%Y%m%dT%H%M%SZ); metrics itest-acl-$T before
host$ ssh egw-tcg "sh /opt/egw/deployment/scripts/probe-acl.sh $T"; echo "exit=$?"      # about 100 s; 0 PASS, 1 FAIL, 3 INCONCLUSIVE
host$ metrics itest-acl-$T after
host$ scp -r egw-tcg:/opt/egw/evidence/itest-acl-$T ~/egw-tcg/itest/
host$ F='"(accepted|rejected|duplicate|failed|dropped|started_at)"'; diff <(python3 -m json.tool ~/egw-tcg/itest/itest-acl-$T.metrics.before.json | grep -E "$F") <(python3 -m json.tool ~/egw-tcg/itest/itest-acl-$T.metrics.after.json | grep -E "$F") && echo "controller untouched by the probe"
host$ cat ~/egw-tcg/itest/itest-acl-$T/verdict.txt ~/egw-tcg/itest/itest-acl-$T/ctl-sub.out; wc -c ~/egw-tcg/itest/itest-acl-$T/sim-sub.out; cat ~/egw-tcg/itest/itest-acl-$T/broker.txt
```

Expected: (a) exit 1, `connection failed` with a certificate-verify error; (b) and (c) exit 1 **after about 15 s** with `egw_simulator: connection failed: MQTT connect to 127.0.0.1:8883 not acknowledged within 15 s` — the simulator's `_on_connect` discards the failure reason code and `connect()` only reports the 15 s timeout (`publisher.py` lines 235 and 251-256, `cli.py` line 246), so "not authorised" never appears in its stderr; the evidence is the broker log captured above (`connection_messages true`, `log_type notice/information` in `mosquitto.conf`): a "not authorised" line for (b) and a TLS/socket error for (c) (`UNVERIFIED:` exact Mosquitto 2.0.22 wording); (d) `scripts/probe-acl.sh` exits 0 and `verdict.txt` ends with `verdict=PASS`. What it does: inside the broker container (`docker compose exec -T`, `-h localhost -p 8883 --cafile /mosquitto/config/certs/ca.crt`; `localhost` is in the certificate SAN) it starts two **concurrent** subscribers on `c2dt/#` — `egw-controller` (ACL `read`) and `egw-simulator` (ACL `write` only) — waits until the broker log shows both subscriptions, then publishes four uniquely tagged QoS 1, non-retained messages on `c2dt/acl-probe/<tag>`: P1 as `egw-simulator`, P2 as `egw-controller` (MQTT 3.1.1), P3 as `egw-controller` (MQTT 5), P4 as `egw-simulator`. Pass criteria: `ctl-sub.out` contains exactly the P1 and P4 lines (`c2dt/acl-probe/<tag> acl-probe <tag> P1 user=egw-simulator`, likewise P4) and neither P2 nor P3; `sim-sub.out` is 0 bytes; both subscribers end with rc 27 (`MOSQ_ERR_TIMEOUT`: still connected when `-W` expired, so their output or silence covers the whole publish sequence); all four publishers exit 0. P1/P4 are the positive control that brackets the denied publishes: the read restriction is proven by the same tagged message reaching the authorised subscriber and not the unauthorised one, the write restriction by P2/P3 reaching nobody while P1/P4 do. Three Mosquitto 2.0.22 behaviours (checked in the sources at tag v2.0.22, not yet observed on this stack) must not be misread: the built-in `acl_file` check grants **every** SUBSCRIBE (`src/security_default.c`) and filters at delivery, so `broker.txt` shows a subscribe line (`<client id> 1 c2dt/#`) for `egw-simulator` as well — expected, not a failure; a denied PUBLISH is logged only at debug level (`src/handle_publish.c`), which `mosquitto.conf` does not enable, so `broker.txt` carries no "denied" line; and under MQTT 3.1.1 the denied QoS 1 publish is acknowledged normally (P2 exits 0 with no error), whereas the MQTT 5 publisher P3 is expected to print `Warning: Publish 1 failed: Not authorized.` and still exit 0 (`client/pub_client.c`; `UNVERIFIED:` on this stack; recorded in `verdict.txt`, not a pass criterion). Exit 3 (`INCONCLUSIVE`) means the positive control or a precondition failed — typically `docker compose exec` start-up under TCG consumed the window — and proves nothing either way: repeat with a new tag and `ACL_PROBE_WINDOW=180` (e.g. `ssh egw-tcg "ACL_PROBE_WINDOW=180 sh /opt/egw/deployment/scripts/probe-acl.sh $T"`), never report it as a pass. The probe topic has three levels and cannot match the controller's filter `c2dt/+/+/telemetry`, so the controller receives none of the probe messages: the `/metrics` diff must print `controller untouched by the probe` (identical `accepted/rejected/duplicate/failed/dropped` and identical `started_at`, i.e. the same controller process). The Mosquitto clients accept a password only through `-P`, so while the probe runs the two dev passwords are on the argv of the clients inside the broker container and of `docker compose exec` in the guest (the same class of exposure as the simulator's `--password` on the host); nothing written to the evidence directory contains them. (e) The anonymous client is refused: `anon.rc` is 5 and `anon.err` reports a not-authorised connection refusal (`allow_anonymous false`; `UNVERIFIED:` exact wording). Also keep `ssh -p 2222 root@127.0.0.1` refused and `nmap`-free port evidence: `ss -ltn` on the host shows only 2222 and 8883 forwarded by QEMU; inside the guest `docker ps` shows `127.0.0.1:8080` and `127.0.0.1:8000` bindings and MongoDB with no published port (work order item 5).

---

## 8. Pilot and load rules (work order item 9)

1. **Order.** Only after tests 1-9 pass: one short nominal run (`--scenario nominal --duration 120`), then the plan's nominal duration (600 s), then `load-sweep` at 10 and 50 msg/s (300 s each), then a short soak (`--scenario soak --duration 3600`). Never the 24 h soak and never the 95 runs of `experiments/campaign_plan.json` on this environment.
2. **Generator delivery check** on every run: `sent / duration` from `sent_events.jsonl` versus the requested rate; if the simulator cannot sustain the rate (host CPU shared with QEMU), the run is a pilot finding, not a measurement.
3. **Label.** Every manifest, figure and table produced from these runs carries "ARM64 emulated (QEMU 8.2.7/TCG on x86-64)"; the `sut_environment.json` fields of 5.8 carry it until Section 9 adds `execution_mode`.
4. **Resource competition.** QEMU/TCG (4 vCPU threads plus I/O and the display-less console), the simulator, the harness sampler and the SSH tunnels all share the WSL2 VM's 16 CPUs and its memory limit; container `cpu_pct` from `docker stats` inside the guest is relative to the *emulated* CPUs, and the QEMU process's host utilisation is a different quantity — document both (Section 9). No Yocto build, no Windows sleep/hibernate, no Docker Desktop builds during a pilot run.
5. **Validity rules unchanged.** Missing `sut_environment.json`, missing or short `resources.csv`, collector hook failures and checksum mismatches still invalidate runs; no `--allow-missing-*` flag is used to make a pilot run pass. Slowness alone never excludes a run.
6. **Supervisor alignment** on the academic use of emulated results is obtained before any of these numbers enter the dissertation (ADR 0008; work order item 9).

---

## 9. Instrumentation changes required (described, not implemented — deliverable 3)

1. **`src/deployment/scripts/capture-sut-environment.sh`** — add fields: `execution_mode` (`tcg-emulated` | `native-kvm` | `native-metal`, from an `EGW_EXECUTION_MODE` variable with **no default**: an unset value must make the harness mark the run invalid), `hypervisor` (`systemd-detect-virt` output, present in the G1 rootfs), `cpu_part` (from `/proc/cpuinfo`), `cpu_features`, `kernel_cmdline` (`/proc/cmdline`, which carries `mem=` and `root=`), `image_identity` (`/etc/buildinfo` content or `IMAGE_NAME`, rootfs sha256 from the build evidence passed as `EGW_IMAGE_SHA256`), `container_image_ids` (`docker image inspect --format '{{.RepoTags}} {{.Id}}'` of the six images), `docker_info_cgroup_version`, `cfs_bandwidth` (recorded as disabled per plan v2.0 §5 item 2).
2. **A host-side capture** (new `scripts/capture-hypervisor-environment.sh`, run on the WSL host, output `hypervisor_environment.json`): QEMU version (`qemu_version.txt`), the exact runqemu command line (machine, `-cpu`, `-smp`, `-m`, `-netdev`), the disk file and its size, WSL kernel `uname -a`, Windows build, host CPU model and `nproc`, `.wslconfig` limits, and `colocated_with_loadgen: true`. The harness references it from the manifest next to `sut_environment.json` and `loadgen_environment.json` (three environments for emulated runs; work order item 7).
3. **`src/egw_experiments/environment.py`** — extend `REQUIRED_SUT_FIELDS` with `execution_mode` and `image_identity`; `run.py` copies `execution_mode` into the manifest top level and records the hypervisor file; `plan_gen`/`campaign` refuse to run plan entries when `execution_mode == tcg-emulated` unless `--pilot` is given (recorded as a deviation).
4. **`src/egw_experiments/analyze.py`** — group by `execution_mode`; refuse to pool runs of different modes into one statistic; write processed outputs under `processed/<execution_mode>/`; stamp every figure with the mode; treat `tcg-emulated` as `performance_claims_allowed = False` at the condition level exactly as `qemu_boots` already is; a wrong-provenance regression test (native manifest with an emulated SUT file must be rejected).
5. **Collectors** — `collect-resources.sh` unchanged (it already stamps `host`); add an optional host-side sampler for the QEMU process (`top -b -n 1 -p <pid>` at 1 Hz on the WSL host into `qemu_process.csv`) so emulated-CPU utilisation and host utilisation are never confused.
6. **TCG timing profile** — if start-up timeouts must change (Section 5.5), they live in `compose.tcg.yaml` and in a documented harness profile; the confirmation window (60 s), loss criteria and saturation rules do not change.

---

## 10. Native route pointer

The native ARM64 route (work order deliverable order: subsequent step) is carried by the native-route change set, which is held back for a later pull request and is not part of the first pull request (limited to the integrated QEMU/TCG profile): `src/yocto/kas/egw-genericarm64.yml` (+ `.lock.yml`, MACHINE `genericarm64`, target `egw-gateway-image`, build directory `src/yocto/build-genericarm64/`; unbuilt), and by plan v2.0 §4 prerequisites; `docs/setup/vm_arm64_hetzner.md` is the superseded provider checklist. What changes when a native host appears:

- **Boot artefact and firmware:** a GPT/EFI `.wic` (ESP + systemd-boot + initramfs + ext4 root) instead of `-kernel Image` plus raw ext4; `runqemu ... kvm` with `QB_CPU_KVM = -cpu host -machine gic-version=3` on an ARM64/KVM host, or the cloud's UEFI on a Graviton/UEFI VM (`import-snapshot`/`register-image --architecture arm64 --boot-mode uefi`).
- **Docker data disk:** the native image keeps the same design (`EGW_DOCKER_DATA_DISK = "1"` in `kas/egw-genericarm64.yml`): `/var/lib/docker` lives on a second ext4 device labelled `egw-data`, and the root partition is sized at build time and never grown. On a KVM host the disk file is created and formatted on the host as here; on a cloud VM a blank volume must be formatted once from inside the guest (`sudo mkfs.ext4 -L egw-data /dev/<blank-device>`, which is why that manifest adds `e2fsprogs-mke2fs`), and until then `docker.service` fails by design while boot and SSH continue.
- **Networking:** a real NIC with DHCP replaces slirp; no hostfwd; the simulator targets the VM's address, so the broker certificate needs `--host <address>` (or `EGW_HOST`) in `generate-dev-tls.sh`; 8080/8000 stay loopback-only and are still reached through `ssh -L`; a host firewall allowing only 22 and 8883 becomes necessary.
- **Identity and labelling:** `execution_mode` becomes `native-kvm` or `native-metal`; `sut_environment.json` records provider, region, instance type and the shared-vCPU caveat as the script already asks; `/proc/cpuinfo` shows the real core (Neoverse/Graviton `UNVERIFIED` part numbers); `qemu_version` is absent or refers to the host's QEMU under KVM.
- **What stays identical:** Sections 4-7 (archives, identity verification, `.env`, TLS, auth, compose, first flow, the nine tests) run unchanged on the native guest; that is the point of doing them here first.
- **What becomes admissible:** only on the native host, and only after the pilot and freeze of plan v2.0 §5 item 5, do timed runs become candidate evidence for RQ3; the emulated results remain functional/integration evidence and a rehearsal of the procedure.

---

## Appendix A — design facts of the integrated profile this runbook relies on (all fifteen checked against the final change-set files on 2026-09-18; re-check after any change to the profile)

| Id | Assumption | Where it matters |
|---|---|---|
| A1 | The manifest passes the public-key path through `EGW_AUTHORIZED_KEYS_FILE` (as in the earlier draft) | 2.1 |
| A2 | `QB_CPU` = `-cpu cortex-a76` (or another ARMv8.2-A model QEMU 8.2.7 offers) for the integrated image | 2.4, 3.4, 3.5 |
| A3 | `QB_MEM` = `-m 8192` (integrated manifest, verified in `kas/egw-qemuarm64-integrated.yml`) | 1.3, 3.3, 3.4 |
| A4 | `QB_SLIRP_OPT` forwards `2222->22` and `8883->8883` on `127.0.0.1` | 3.1, 3.3, 6.2 |
| A5 | Separate data disk for `/var/lib/docker` (verified: `EGW_DOCKER_DATA_DISK ?= "1"` in `egw-gateway-image.bb`, fstab `LABEL=egw-data ... nofail,x-systemd.growfs`, `RequiresMountsFor=/var/lib/docker` drop-in), created and formatted on the host by `scripts/run-qemu-integrated.sh`; the root file system is not grown | 1.1, 3.2, 3.3, 3.4, test 8 |
| A6 | Guest hostname `egw-qemu-integrated` (verified: `EGW_HOSTNAME = "egw-qemu-integrated"` in the integrated manifest, written to `/etc/hostname` and `/etc/hosts` by `egw_set_hostname` in `egw-gateway-image.bb` and recorded in `/etc/buildinfo`; `hostname:pn-base-files` is deliberately not used) | 3.4, collectors |
| A7 | `image-buildinfo` inherited (`/etc/buildinfo`) | 2.5, 5.8 |
| A8 | `openssh-sftp-server` installed | 4.4, 5.1 |
| A9 | tmpfiles entry creating `/opt/egw` owned by `egw` | 4.4, 5.1 |
| A10 | `openssl-bin` installed | 5.3 |
| A11 | `curl` installed | 5.6, `measure-cold-start.sh` |
| A12 | sshd drop-in with key-only login, `AllowUsers egw`, keepalives | 3.4, 5.7 |
| A13 | `egw` has NOPASSWD sudo (needed for `systemd-run`, `systemctl reboot`, `chown`; `prepare-broker-secrets.sh` falls back to a one-shot root container with `EGW_BROKER_PRIV=docker` if it does not work) | 3.4, 5.4a, 7 |
| A14 | Persistent journal (`EGW_PERSISTENT_VAR_LOG = "1"`: `egw_persistent_var_log` in `egw-gateway-image.bb` replaces the `/var/log -> volatile/log` symlink with a directory and pre-creates `/var/log/journal`; journald drop-in `Storage=persistent` from `egw-gateway-config`; the global `VOLATILE_LOG_DIR` is deliberately not changed) | Test 8 |
| A15 | `egw` is created with `-p '*'` (not a locked `!` password field) | 2.4 |

## Appendix B — `UNVERIFIED:` items in this runbook

1. docker-compose_git.bb (v2.26.0) builds cleanly with the pinned layers (never built in this tree).
2. Size of the six uncompressed `docker save` archives (estimate about 2 GB) and slirp transfer time for them under TCG.
3. Docker Desktop engine image store (containerd vs graphdriver) and whether the default builder attaches attestation manifests without `--provenance=false --sbom=false`.
4. `docker tag <repo>@<digest> <repo:tag>` accepted as the source form by the 29.7.2 client.
5. docker-moby 25.0.9 `docker load` of the archive format written by a 29.x `docker save --platform`.
6. `docker compose config --images` availability in Compose 2.26.
7. QEMU honouring the last `-cpu` when `qemuparams="-cpu ..."` is appended after `QB_CPU`.
8. Exact `/proc/cpuinfo` feature flags mongod 7.0 requires and the exact SIGILL/"Illegal instruction" signature on a cortex-a57 model.
9. JVM start-up duration under TCG and whether the Ditto healthcheck `start_period 120s` is exceeded.
10. Ditto gateway HTTP health endpoint path on port 8080 (the compose healthcheck uses pekko-management on 7626).
11. Mosquitto 2.0.22 log wording for connect/disconnect (`connection_messages true`), for the wrong-password and plaintext refusals of test 9(b)/(c) and for the 30-second healthcheck lines on this stack. For ACL denials the 2.0.22 sources settle the question that was open here: a denied PUBLISH is logged only at `debug` and a delivery skipped by a `read` denial is not logged at all, so at the configured log levels there is **no** denial line; and the built-in `acl_file` check never denies a SUBSCRIBE, so the `subscribe` log line appears for `egw-simulator` too (test 9(d)). Still unobserved on the real stack: the `mosquitto_sub -W` exit code 27 and the presence of `mosquitto_sub` in the Alpine build of the image (that of `mosquitto_pub` is implied by the compose healthcheck), the exact subscribe-line format with `log_timestamp_format` (pattern used by the probe: `<client id> 1 c2dt/#`), the MQTT 5 `Not authorized` warning of `mosquitto_pub`, the anonymous refusal wording and exit code 5, and whether a 90 s window suffices for the `docker compose exec` start-ups under TCG.
12. Error shape (5xx/timeout vs 4xx) the controller sees from Ditto while MongoDB is stopped; and whether the per-device `accepted_count` delta still closes when a Ditto patch was applied but its 2xx answer was lost (test 7).
13. Cortex-A76 part number `0xd0b` and Graviton core part numbers (general Arm knowledge, not from a document in the checkout).
14. Broker secret hand-over (5.4/5.4a/5.5): `scripts/prepare-broker-secrets.sh`, the modified `generate-dev-auth.sh` and step 3b of `validate-config.sh` were syntax-checked (`sh -n`/`dash -n`) and exercised with stub `docker`/`stat` binaries only; no run against a real engine, no ShellCheck, no BusyBox ash run (the applets used — `stat -c`, `id`, `sed`, `head`, `chown`, `chmod` — are `=y` in the pinned poky BusyBox defconfig). The uid/gid 1883 comes from `docker/2.0-openssl/Dockerfile` of the Mosquitto repository (the directory the Docker official-images manifest names for the 2.0 tags), read on 2026-09-18; that the digest pinned in `images.lock.env` was built from those lines is confirmed only at run time by the script's `id -u mosquitto` comparison. Docker 25.0.9 accepting `--network none --user --entrypoint` together is standard but was not run.
15. Whether `sudo -n true` works for `egw` on the guest (A13); fallback `EGW_BROKER_PRIV=docker`.
16. Behaviour of Mosquitto releases later than 2.0.22 towards a `password_file`/`acl_file` not owned by the broker user (the 2.0.x ChangeLog announces a refusal "in future versions"; 2.0.22 only warns).
17. The ad-hoc reconciliation helper `egw_experiments.itest_reconcile` (6.1-6.5, tests 1-8) has been exercised only by a synthetic self-test against a local HTTP stub and the unmodified `compute_run_metrics` (in-window, on-deadline, late and missing confirmations; matching and mismatching counter deltas); it has no unit test in `src/tests/` and was never run against the real controller or Ditto. Unobserved: that `GET /metrics` through the SSH tunnel answers within the harness's marker timeout under TCG; the marker lag obtained with `; $REC mark` after a piped simulator command (harness tolerance 2 s); that the Ditto gateway answers 404 for an unknown thing through the tunnel.
18. That the controller's `time.monotonic_ns()` continues across a controller *container* restart (kernel `CLOCK_MONOTONIC`, no time namespace; reasoned, not observed — CONTRACTS words the guarantee per process). `$REC wait` fails loudly if the controller clock is seen going backwards.
19. `scripts/probe-acl.sh` (test 9(d)): parsed with `dash -n` and exercised only against mock `docker`/`mosquitto_*` stubs (argument plumbing and verdict logic, not broker behaviour); execution under BusyBox ash 1.36.1 and `docker compose exec -T -e KEY=VALUE` in Compose 2.26 are documented behaviour, not run. Poky's BusyBox defconfig has no `timeout` applet (`# CONFIG_TIMEOUT is not set`, verified), which is why the probe uses `mosquitto_sub -W`.
20. The host-side additions of Section 7, none executed: the `drained` function of the preamble (parsed with `bash -n` and exercised only against a stubbed `curl`, as was the side-by-side line against two hand-written JSON files; whether 300 s suffice for a backlog under TCG is unknown), the pre-/post-replay copies and the side-by-side line of test 4, and the fetch of `<run_id>.warmup/events.jsonl` for `delta --also` in test 6 (path derived from the controller's one-file-per-`run_id` rule in `events.py` and from `run.py`'s warm-up run id, not observed on a guest). Likewise the change-set guard of 5.1 (`grep -c` under BusyBox ash is documented behaviour, not run).
