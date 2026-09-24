# Integrated QEMU/TCG gateway — executable runbook

**Status (2026-09-18):** Sections 1 to 3.4 were executed once on 2026-09-18: the image was built from commit `03e333e` and booted twice from commit `3209b17` (which changes only the boot wrapper and this runbook); every acceptance check of 2.4 and 3.4 passed, the data disk and the journal persisted across the two boots, and the candidate evidence (logs, checksums, guest transcripts, with `SHA256SUMS`) was sealed the same day in `docs/evidence/integrated-qemu/2026-09-18-build-boot/`, a byte-for-byte copy of the directories `~/yocto/evidence-candidates/2026-09-18-integrated-{68f9ae7,03e333e,3209b17}/` of the WSL2 home; sealing is not acceptance (`docs/reviews/2026-09-17-egw-image-audit.md`, Section 13). That run used the commands of Sections 2-3 as they stood before the guard rewrite of the same day: the compound guards of 3.1 and 3.3, and every guard and helper of Sections 7-9, have **not** been executed on the real host or guest, and the `UNVERIFIED:` marks of Sections 1-3 were not revisited against the run (Appendix B items 20 and 22). Whether the guards and helpers of Sections 4 to 6 were pasted as written during the first-flow session described below is **not recorded in this repository**; verify against the run record before restating it either way. **Section 3.5 was exercised in a different form on 2026-09-18** (isolated MongoDB 7.0.39 test: the image was pulled by the pinned digest of `images.lock.env` **inside the guest**, and start, write and read, restart, recreation and persistence across a guest power cycle passed — 35 checks, none failed; record in the evidence capsule `docs/evidence/integrated-qemu/2026-09-18-mongodb7-isolated/`). **Sections 4 to 6 were exercised once later the same day** for the first bounded end-to-end flow: the six-container stack was deployed inside the emulated guest and the flow passed — one smartwatch at 1 Hz for 60 s; 60 sent, 60 delivered unique, 0 lost, 0 late, 0 duplicate, 0 failed, 0 rejected; twin `org.c2dta:5689c879-…` with `last_seq` 59; reconciliation by identity exited 0; maximum latency 12,286 ms, **emulated and informational, never a performance result**. That record is **candidate evidence held outside the repository and unsealed**, so it admits no claim and closes no gate. The run exposed two defects, both since fixed on `dev` (the controller on the wrong Compose network; a relative schema directory inherited by the host shell), and a memory-cgroup OOM killed the `ditto-things` JVM **during the power-off** of that session at the 512 MiB container limit; the corrective work is a separate change and remains open, so no stability is claimed. **No pilot and no instrumentation change have been run from Section 7 onwards, and nothing has been measured**; the nine integration/recovery test families had not been run when this paragraph was first written, and the dated note below records what happened later the same day. Every command is to be executed by the student in WSL2 (Ubuntu-24.04, user `ruisth`) or on the Windows host as stated; every "expected" value is a prediction to be confirmed or refuted by the evidence the step produces. Where a step depends on a design decision of the integrated profile that is not yet fixed, the assumption is stated in the step and collected in Appendix A. Anything not verified against the pinned checkout or the repository is marked `UNVERIFIED:` and listed in Appendix B.

**Status note (2026-09-19) — three corrections to the paragraph above and to Section 8.** (a) The statement about Section 7 in the paragraph above was written in this change and is corrected there rather than preserved and superseded, because it never stood on `dev`. What happened: later on 2026-09-18 the nine integration/recovery test families were exercised once. Functional results were demonstrated for test 2 (672 valid events, 0 lost, 0 late; the last confirmation 3.1 s before the deadline), test 8 (reboot and persistence) and the tested checks of test 9; the specific behaviours of test 3 (rejection of invalid payloads — but 132 of its 1,277 valid events were confirmed late), test 4 (duplicate handling) and test 7 (bounded retry under a MongoDB fault — not lossless delivery: 62 failed, 1,012 late) were demonstrated; **test 5 fails its deadline criterion** (326 of 2,016 valid events confirmed late); **the sequence-reset sub-check of test 4 and the Ditto repeat of test 7 were not run** (both steps stood in prose, and the tooling that extracted the battery's commands took only fenced code blocks); and **the timed harness runs of tests 1 and 6 are invalid** (r01 in the battery, r02 repeated on 2026-09-19 with an interim collector: their resource files were not ingested, and the restart runs also had controller-metrics outages), so the recovery and delivery of test 6 are not accepted. That record is a locally hash-sealed candidate archive held outside the repository, not incorporated into or admitted by the project evidence record; the battery is **not complete**, no official campaign has been completed or admitted (its diagnostic measurements are not accepted campaign results or native performance evidence), no pilot has been run, and the resource-sampler defect is addressed under its own change, which is not merged into `dev`. Whether the steps of Sections 7 to 9 were pasted as written is **not recorded in this repository**, beyond what tests 4 and 7 now record (the battery took its commands from fenced code blocks only); verify against the run record before restating it either way. *(Corrected on 2026-09-19: this note first said "seven passed, and tests 1 and 6 carry a failing harness part"; re-reading the record test by test showed that to be an overstatement, and the per-test state above replaces it. Tests 4 to 7 carry dated notes.)* (b) The exclusions "The 95-run campaign is **not** started on this environment" in the paragraph below and "Never the 24 h soak and never the 95 runs of `experiments/campaign_plan.json` on this environment" in Section 8, rule 1, are kept where they stand and are **superseded**: the student reports an instruction to attempt the historical 95-run composition, the 24-hour soak included, under QEMU. It is a target to attempt, subject to the bounded pilot's feasibility check, and it is separate both from the frozen protocol and from the actual valid run count. Nothing in the superseded rule's ordering changes: no part of that quantity is started before the nine families are complete, the pilot has reported and the protocol is frozen prospectively. See section 3.3.1 of the adopted plan, `docs/governance/INTEGRATED_DEVELOPMENT_PLAN_2026.md`. (c) Three statements of the paragraph above stood on `dev`; they are kept where they stand and are **superseded**. The first-flow record it calls unsealed is a locally hash-sealed candidate (all 51 `SHA256SUMS` entries verify), outside the published evidence package and not admitted. The corrective work it calls open — 768 MiB for the three Ditto services and the stop of the stack before power-off in Section 3.3 — has since been merged into `dev` through pull request #34; only bounded observations follow from it, and no general or prolonged stability is claimed. And "nothing has been measured" is too broad: no official campaign has been completed or admitted, and the diagnostic measurements are not accepted campaign results or native performance evidence.

Authority: project work order of 2026-09-17 (items 1-9) and the integrated-Yocto working revision of 2026-09-16 (plan v2.0 §5 and ADR 0008, as that revision was drafted; its text is kept at `docs/governance/proposals/`). That revision **was adopted by the student on 2026-09-18 with the QEMU-only execution amendment** and published as plan v2.0 at `docs/governance/INTEGRATED_DEVELOPMENT_PLAN_2026.md`, superseding v1.2; where this runbook and the adopted plan differ, the adopted plan governs. Adoption is a decision of the student: it records no supervisor approval, and this runbook accepts no gate and no claim. Staging: Sections 0-3 (profile, build, boot) are delivered with the integrated-profile change set; Sections 4-9 additionally need the deployment and harness changes of later pull requests (`scripts/prepare-broker-secrets.sh` and `scripts/probe-acl.sh`, on `dev`; `egw_experiments/itest_reconcile.py` and the prebuilt controller image, LOG `#C030`) — Section 5.1 checks for them and stops if they are missing. Fixed names come from the work order and are not renegotiated here: manifest `src/yocto/kas/egw-qemuarm64-integrated.yml` (+ `.lock.yml`), images `egw-gateway-image` / `egw-gateway-image-dev`, configuration recipe `egw-gateway-config`, build directory `src/yocto/build-integrated/` selected with `KAS_BUILD_DIR`.

Conventions:

- `host$` — bash on the WSL2 host, repository clone at `/home/ruisth/yocto/egw` (the Windows checkout `C:\Users\ruimf\Documents\Projeto Mestrado\Claude` is read-only for this work; the WSL clone is where the change set is applied on a branch and where kas runs).
- `PS>` — Windows PowerShell with Docker Desktop started; `gitbash$` — Git Bash on the same host (4.1).
- `guest$` — BusyBox ash (`/bin/sh -> busybox.nosuid`) inside the Yocto guest as user `egw`; `guest#` — root on the serial console of the `-dev` image only.
- Never run `bitbake`, `kas build` or `kas checkout` against `src/yocto/build/` (the sealed G1 tree). Every kas command below carries `KAS_BUILD_DIR=$PWD/build-integrated`.
- **Guards stop what they guard.** The commands are pasted one line at a time into an interactive shell, where a failed check on one line cannot prevent the next pasted line from running. A precondition and the action it protects are therefore always **one** compound command (`if <check>; then <action>; else echo "STOP: ..."; fi`, or a helper function that prints a line starting with `STOP:` and returns non-zero, chained with `&&`). This applies to: the QEMU start (3.3), the archive load and the identity verdict (4.4), the deployment-tree copy (5.1), the `.env` copy (5.2), `up -d` (5.5), the tunnels (5.7, test 8), and every snapshot, simulator start and reboot of Sections 6 and 7 (helpers of 6.1). When a line prints `STOP:`, do not paste the following lines: resolve the cause and repeat that line. A guarded line that prints neither its success token (`COPIED`, `TUNNEL UP`, `up exit=0`, `TEST STATUS ... PROCEDURE COMPLETE`, ...) nor `STOP:` has not succeeded either. Where a test of Section 7 (or the blocks of 6.5 and 6.6) spans several pasted lines, the outcome of its first line is carried in a shell variable (`RT`, `T4`/`REPLAYED`, `T6`, `T7`, `EV6`, `R65`) that every later line of that test checks first, so the lines after a `STOP` refuse to run instead of relying on the operator's attention; in a new shell the variable is empty and they refuse as well. Checks that remain prose ("must print", "expected") are not interlocked and are the operator's responsibility. `UNVERIFIED:` none of these constructs has been executed on the real host or guest (Appendix B, item 20).

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

The integrated build shares `DL_DIR`/`SSTATE_DIR` under `~/yocto-cache` with G1 (same pinned commits, same MACHINE/tune), so the extra space is the new `build-integrated/tmp` (order of 30-60 GB, estimate) plus the controller image archive (`docker save` output is not compressed; `UNVERIFIED:` a few hundred MB) plus the sparse 32 GiB data disk of Section 3.2 (grows only as the guest writes to it). Keep at least 120 GB free before starting (`df -h ~`). The WSL2 VHDX does not shrink automatically (see `docs/setup/wsl2_ubuntu_yocto.md` §2).

### 1.3 `.wslconfig` and host headroom

The guest (`QB_MEM = "-m 8192"`, integrated manifest — an 8 GiB guest) and QEMU/TCG (4 vCPU threads plus I/O threads) run inside the WSL2 VM alongside the simulator; the WSL2 VM must therefore have RAM for the guest **and** the host-side processes. State checked read-only on 2026-09-18: the workstation has about 64 GiB of RAM (63.4 GiB reported by Windows), no `%UserProfile%\.wslconfig` exists, and the WSL2 VM therefore has the default 50 %, i.e. the 31 GiB that `free -g` shows — enough for the 8 GiB guest as it is, so **do not create a `.wslconfig` just for this profile**. `memory=20GB` is a lower bound that applies only if a limit is ever set there: below it, `memory=16GB` would leave only about 8 GiB for QEMU's own overhead, the simulator, the harness and the page cache. If a smaller guest is needed for a bring-up boot, `EGW_QEMU_EXTRA="-m 6144"` on the wrapper (3.3) overrides `QB_MEM` for that boot only and runqemu mirrors it into `mem=`; never use a smaller guest for evidence runs. Never run a Yocto build while the guest is up (work order item 9). Check after `wsl --shutdown`:

```bash
host$ free -g; nproc
```

### 1.4 Docker Desktop (image preparation host)

Verified 2026-09-17: Docker Desktop client 29.7.2 is installed on Windows; the daemon was not running; the Ubuntu-24.04 distro has no working `docker` (WSL integration disabled — the `/mnt/c/.../resources/bin/docker` shim prints "could not be found in this WSL 2 distro"). The image steps of Section 4 need a running daemon, and the `docker buildx`/`docker save` client flags `--platform` (verified on the 29.7.2 client help). Choose ONE of:

- **Option A (Git Bash):** start Docker Desktop, wait until `docker version` shows the Server section, run 4.1 in Git Bash from a clean checkout, then copy the archive and its identity record into WSL via `/mnt/c` (4.3).
- **Option B (WSL):** start Docker Desktop, enable *Settings -> Resources -> WSL integration -> Ubuntu-24.04*, apply, reopen the WSL shell, confirm `docker version` and `docker buildx inspect default | grep -i platforms` lists `linux/arm64`, then run 4.1 in bash from a clean clone with the WSL paths.

Docker Desktop builds `linux/arm64` images with its bundled binfmt/QEMU user-mode emulation (audit report `docs/reviews/2026-09-17-egw-image-audit.md`, sections 1 and 4); this is a *build* aid on the provisioning host and says nothing about the measured guest.

`UNVERIFIED:` whether the Docker Desktop engine that starts is configured with the containerd image store (the default for recent installs) — it changes the meaning of `docker image inspect --format '{{.Id}}'` on the host (manifest digest instead of config digest). `scripts/build-controller-image.sh` (4.1) therefore reads the identity from the saved archive's `manifest.json`, which is store-independent, and host `.Id` is never compared against guest `.Id` directly.

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
host$ $KAS_BUILD_DIR/tmp/work/qemuarm64-poky-linux/egw-gateway-image/1.0/recipe-sysroot-native/usr/bin/qemu-system-aarch64 --version > $EV/qemu_version.txt
```

The last line records the QEMU version of the build tree (8.2.7, the same recipe as G1, restored from sstate). It uses the copy in the image recipe's native sysroot because the `tmp/sysroots-components/x86_64/qemu-system-native/` binary cannot run on its own: it fails with `libfdt.so.1: cannot open shared object file` outside a recipe sysroot (observed on 2026-09-18). The binary `runqemu` actually executes is printed in its `Running ...` line (3.3).

---

## 3. Boot

### 3.1 Before starting QEMU

```bash
host$ if ss -ltn | grep -E ':(2222|8883|8000|8080) '; then echo "STOP: the host ports listed above are busy - free them before 3.3"; else echo "ports free"; fi
```

`runqemu` silently re-maps a forwarded host port that is already in use and logs `Port forward changed: 2222 -> 2223` (verified, runqemu lines 1118-1136). A stale `ssh -L` tunnel or a second runqemu will therefore move SSH or MQTT to another port. Before booting, identify the owner of 2222/8883 with `ss -ltnp` and close that process only (this project's tunnel: `tunnel_down`, 5.7), and after every boot read the actual mapping (3.3). This line only reports; the interlock is in the boot line of 3.3, which repeats the check for 2222/8883 and does not start QEMU while either is busy.

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
host$ if ss -ltn | grep -E ':(2222|8883) '; then echo "STOP: host port 2222 or 8883 is busy (line above) - QEMU was NOT started"; else ./scripts/run-qemu-integrated.sh $BOOT; fi
```

That is the whole boot command for evidence runs (the `if` is the port guard of 3.1 made binding: with a busy port the wrapper is not started at all, instead of booting with a silently re-mapped port). The wrapper (bash, `set -euo pipefail`) exports `KAS_WORK_DIR`, `KAS_BUILD_DIR=$PWD/build-integrated` and `EGW_CACHE_DIR`, refuses to run when `build-integrated/tmp/deploy/images/qemuarm64/egw-gateway-image-qemuarm64.rootfs.qemuboot.conf` is missing, creates and formats the data disk when absent, verifies its label with `blkid`, warns if host ports 2222/8883 are busy, writes a header (date, host, `qb_*` lines of the qemuboot.conf, the disk file's apparent and on-disk size, the exact runqemu command) to `~/yocto/logs/$BOOT.log`, and then runs:

```
kas shell kas/egw-qemuarm64-integrated.yml -c 'runqemu $KAS_BUILD_DIR/tmp/deploy/images/qemuarm64/egw-gateway-image-qemuarm64.rootfs.qemuboot.conf nographic slirp qemuparams="-drive id=disk1,file=$HOME/yocto/egw-integrated/egw-data.img,if=none,format=raw -device virtio-blk-pci,drive=disk1"' 2>&1 | tee -a ~/yocto/logs/$BOOT.log
```

The equivalent explicit line (only for diagnosing the wrapper itself; the wrapper is the record) is that command with the same three exports set by hand and the disk file already formatted. Notes (all verified in `poky/scripts/runqemu`):

- `kas shell` runs its command **from `$KAS_BUILD_DIR`** with the BitBake environment sourced (`oe-init-build-env`). The wrapper hands `runqemu` the **explicit path** of the image's own `.qemuboot.conf` in `build-integrated/tmp/deploy/images/qemuarm64/`, which also selects the deployed `egw-gateway-image-qemuarm64.rootfs.ext4` (same base name), never the `-dev` image's conf. The form `runqemu egw-gateway-image qemuarm64 ...` does **not** work with the pinned `runqemu`: the machine argument makes it run a target-less `bitbake -e`, which carries no `IMAGE_LINK_NAME`, and it stops with `IMAGE_LINK_NAME wasn't set to find corresponding .qemuboot.conf file` (reported for the first boot attempt of 2026-09-18, which ended before QEMU started: audit report section 13.1, attempt 3 - not re-checked for this revision, Appendix B item 22; the G1 wrapper never passed an image name).
- Memory is set in ONE place: `QB_MEM = "-m 8192"` from the qemuboot.conf, or `EGW_QEMU_EXTRA="-m 6144"` (bring-up only), which runqemu parses (line 823) and mirrors into the kernel `mem=` argument (line 843). Never pass `mem=` yourself via `bootparams=`.
- To try a different CPU model without rebuilding, `EGW_QEMU_EXTRA="-cpu neoverse-n1"` is appended *after* the `QB_CPU` option (line 1557-1559); `UNVERIFIED:` QEMU honours the last `-cpu` given. Prefer changing `QB_CPU` in the manifest and rebuilding the image (only the qemuboot.conf changes) so the record in `testdata.json` matches the boot.
- For the `-dev` image (root console login) use `EGW_IMAGE=egw-gateway-image-dev ./scripts/run-qemu-integrated.sh $BOOT-dev`; it attaches the same data disk and is for bring-up only, never for evidence runs.
- Exit QEMU with `Ctrl+A` then `x` (the wrapper's stdin stays attached to the terminal; stdout/stderr are teed into the log).
- **Stop the stack before powering the guest off**, whenever it is running:
  `ssh egw-tcg 'cd /opt/egw/deployment && docker compose --env-file .env --env-file images.lock.env stop -t 60'`, then `ssh egw-tcg 'sync; sudo -n poweroff'`. A power-off with the containers still running leaves the JVMs to be stopped by the shutdown of `docker.service`, and on 2026-09-18 the kernel killed the `ditto-things` JVM that way (memory-cgroup OOM during teardown). The same run stopped cleanly in 19 to 42 s when the stack was stopped first, with no OOM in the whole boot. `docker compose stop` keeps the containers and volumes; the stack comes back with `start` at the next boot.

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

Needs the `mongo:7.0.39` image inside the guest, pulled through slirp's NAT by the pinned digest of `images.lock.env` (`IMAGE_MONGODB`; the digest pin selects the arm64 child, and a pulled-by-digest image has no tag, so every command names the full reference):

```sh
guest$ M=docker.io/library/mongo:7.0.39@sha256:35a5926f71f8b6cb19206bee928c5a85f241a8be99f20c81abe35ae78a73415d
guest$ docker pull --platform linux/arm64 $M
guest$ docker image inspect --format '{{.Id}} {{.Architecture}} {{.Os}} {{.RepoDigests}}' $M
guest$ docker run --rm --platform linux/arm64 $M mongod --version
guest$ docker run -d --name mongo-cpu-test --memory 512m $M mongod --storageEngine wiredTiger --noscripting
guest$ sleep 30; docker inspect --format '{{.State.Status}} exit={{.State.ExitCode}}' mongo-cpu-test
guest$ docker logs mongo-cpu-test 2>&1 | grep -iE 'illegal|SIGILL|Waiting for connections|error' | head -n 5
guest$ docker rm -f mongo-cpu-test
```

Expected under an ARMv8.2-A model: `mongod --version` prints `db version v7.0.39`, the container is `running exit=0` and the log contains `Waiting for connections`. Expected failure signature under the G1 `cortex-a57` profile (`UNVERIFIED:` exact wording): immediate exit with code 132 (SIGILL) or an "Illegal instruction" line — that is the work-order item 2 blocker, and it must never be "fixed" by relaxing the architecture check on the images.

Observed on 2026-09-18: the guest **can** reach the registry through slirp's NAT, and a pull by the pinned digest took 65 s and produced `RepoDigests` equal to the pin (`mongo@sha256:35a5926f…415d`, image id `sha256:d58a07b4b2ec…`, `arm64/v8`). A pull **by digest** therefore gives a verifiable identity — stronger than `docker load`, which restores a tag only — and the project review of 2026-09-18 decided that the five external images take this route (Section 4).

---

## 4. Images

Goal: the five pinned images and the prebuilt controller are in the guest's engine with a **verifiable identity**, and nothing is ever built on the gateway (work order item 4, plan v2.0 §5 item 3). Route decided by the project review of 2026-09-18 and implemented in `src/deployment` (LOG `#C030`): the five external images are **pulled by their pinned digests inside the guest** (4.2; observed for MongoDB in 3.5); the controller is built on the provisioning host, enters the guest as one checksummed archive and is loaded (4.1, 4.3, 4.4) — no registry holds it.

Facts that shape this section (audit report `docs/reviews/2026-09-17-egw-image-audit.md`, section 4): an image pulled by digest carries a `RepoDigests` entry equal to the pin, and that is its identity; `docker load` restores `repository:tag` only, never a `RepoDigest`, so the controller's identity is its **image ID** (config digest), which is what the guest's docker-moby 25.0.9 (overlay2 graphdriver) reports as `.Id`, compared against the identity record written next to the archive on the provisioning host. `compose.yaml` accordingly takes the five references `repo:tag@sha256:...` from `images.lock.env` and gives the controller `image: egw-controller:0.1.0`, `pull_policy: never` and no `build:` (lines 220-222, verified).

The offline route of the earlier revision of this section (all six images as `docker save` archives, a tag-only `images.offline.env`) is **not implemented** in `src/deployment` and was removed here; it remains in the history of this file (commit `0e536cd`) should isolation from the registry ever be required.

### 4.1 Build the controller for linux/arm64 (provisioning host: Docker Desktop, Git Bash)

```bash
gitbash$ cd /c/Users/ruimf/egw-clean && git rev-parse HEAD && git status --porcelain -- src     # example path: a fresh clone or `git worktree add` of the commit to deploy (based on the merged `dev`), NEVER the working tree of the conventions; the status must print nothing
gitbash$ docker version            # Server section must be present (daemon running)
gitbash$ sh src/deployment/scripts/build-controller-image.sh /c/Users/ruimf/egw-images
```

The script (deployment README step 4b) refuses a build context `src/` with modified or untracked files, or with git-ignored files below a path that `src/Dockerfile` copies (exit 3; `--allow-dirty` is for development and never for evidence), builds `egw-controller:0.1.0` for `linux/arm64` with `buildx` (`--no-cache --provenance=false --sbom=false --load`, label `org.opencontainers.image.revision=<commit>`), exports it with `docker save` and writes, next to `egw-controller-0.1.0-arm64.tar`, the identity record `egw-controller-0.1.0-arm64.identity.txt` (key=value: `image_id` read from the archive's `manifest.json`, `source_commit`, `source_tree_state`, `image_revision_label`, `dockerfile_base_image`, `archive_sha256`, `python_version`, repeated `pip_freeze=` lines, Docker and `buildx` versions, `built_utc`). It pushes nothing and never overwrites: the output directory must not already hold the two files. It must print two `OK:` lines (the archive and the record, each followed by an indented detail line) and exit 0; three further lines naming the `docker load` and verification commands follow them, so the two `OK:` lines are not the tail of the output. On any failure, and on an interruption (exit 129, 130 or 143 for `HUP`, `INT`, `TERM` — the clean-up runs in every POSIX shell), nothing is left behind. `UNVERIFIED:` never executed against a Docker engine (stub `docker` only, `src/tests/test_deployment_prebuilt_controller.py`); Appendix B item 3.

**Reproducibility caveat (first-round review, audit report `docs/reviews/2026-09-17-egw-image-audit.md` section 11):** `src/Dockerfile` still runs `RUN pip install .` and says so: the Python dependencies of this image are **unlocked**, the record says `python_dependencies=UNLOCKED` and its `pip_freeze=` lines document that one build without making it reproducible. Such an image is acceptable for this functional integration and for the pilot's mechanics, **not** for thesis measurements: before the experimental freeze `requirements-runtime.lock` must be generated (`scripts/generate-runtime-lock.sh` refuses non-aarch64 hosts), reviewed, committed, and the Dockerfile switched to `--require-hashes` (deployment README, "Runtime Python lock").

### 4.2 The five pinned images: pulled inside the guest (commands in 5.2a)

`docker compose ... pull` interpolates `compose.yaml`, so it needs the deployment tree and `.env` on the guest; the commands are therefore in **5.2a**, after 5.2 and before the broker scripts of 5.4 (which run one-shot containers of the broker image). Pulling `repo:tag@sha256:<manifest-list digest>` on the arm64 guest selects the arm64 child (the digests in `images.lock.env` are manifest-list digests, verified header); the pulled image has no tag and a `RepoDigests` entry equal to the pin (observed on the guest for `mongo`, 3.5).

Also archive the complete verification that plan v2.0 §5 item 3 asks for on the provisioning host: `docker buildx imagetools inspect <repo:tag>` for each of the five images (this needs registry access and buildx, both present on Docker Desktop and absent on the guest) into `/c/Users/ruimf/egw-images/imagetools-<name>.txt`; `scripts/resolve-image-lock.sh` can run there too, and its output is the archived digest verification.

### 4.3 Copy the archive into WSL and check it against its record (bash)

```bash
host$ cp /mnt/c/Users/ruimf/egw-images/egw-controller-0.1.0-arm64.tar /mnt/c/Users/ruimf/egw-images/egw-controller-0.1.0-arm64.identity.txt ~/egw-images/ && echo "COPIED" || echo "STOP: cp failed - ~/egw-images is INCOMPLETE"
host$ cp /mnt/c/Users/ruimf/egw-images/imagetools-*.txt ~/egw-images/ && echo "COPIED (digest verification of the five external images, 4.2)" || echo "STOP: the imagetools-*.txt files of 4.2 were NOT copied - 4.4 and 6.6 cannot keep them as evidence"
host$ ctl_ok() { (cd ~/egw-images && s=$(sed -n 's/^archive_sha256=//p' egw-controller-0.1.0-arm64.identity.txt) && [ -n "$s" ] && echo "$s  egw-controller-0.1.0-arm64.tar" | sha256sum -c - && grep -qx 'source_tree_state=clean' egw-controller-0.1.0-arm64.identity.txt) || { echo "STOP: the archive does not match its identity record, or the record is not from a clean build context"; return 1; }; }
host$ ctl_ok && grep -E '^(image_id|image_architecture|image_os|source_commit|archive_sha256|python_version|python_dependencies|built_utc)=' ~/egw-images/egw-controller-0.1.0-arm64.identity.txt
host$ CLONE=/home/ruisth/yocto/egw; SRCC=$(sed -n 's/^source_commit=//p' ~/egw-images/egw-controller-0.1.0-arm64.identity.txt)
host$ if [ -n "$SRCC" ] && git -C $CLONE fetch --quiet origin && git -C $CLONE checkout --quiet "$SRCC" && [ "$(git -C $CLONE rev-parse HEAD)" = "$SRCC" ] && [ -z "$(git -C $CLONE status --porcelain -- src ':(exclude)src/yocto')" ]; then echo "$SRCC" > ~/egw-tcg/deploy_source_commit.txt && echo "DEPLOY TREE AT $SRCC"; else echo "STOP: $CLONE is not at the controller image's commit, or what it would give to 4.4, 5.1 and 6.1 is not clean - the deployment tree, the scripts and the harness must NOT be taken from it"; fi
```

The record maps the archive to the image ID the guest must report after `docker load` (the config digest; `Config` is `<hex>.json` in the legacy layout or `blobs/sha256/<hex>` in the OCI layout — the script accepts both and re-hashes the blob). `source_commit` must be the commit of 4.1.

**One commit for the image and for everything copied from the clone.** 4.1 builds from a separate checkout on the Windows host (`/c/Users/ruimf/egw-clean`), while `verify-controller-image.sh` (4.4), the deployment tree (5.1) and the harness with `egw_experiments.itest_reconcile` (6.1) are all taken from the WSL clone; without the last two lines above, image and procedure could come from different commits unnoticed. The guard brings the clone to the commit named in the identity record (a detached `HEAD` at that commit; a checkout leaves untracked files where they are, and it refuses — so the guard prints `STOP:` — while uncommitted work would be overwritten) and then refuses unless everything the clone gives to 4.4, 5.1 and 6.1 is clean. `src/yocto` is excluded from that test, and only it: the build directory of Section 2 lives there as `src/yocto/build-integrated/`, which `.gitignore` does not cover (it lists `src/yocto/build/`), so the plain `-- src` form would report it as untracked and stop on every clone that has built the image; nothing under `src/yocto` is copied to the guest or installed on the host. The commit is written to `~/egw-tcg/deploy_source_commit.txt`, which 6.6 copies into the evidence: it is the commit of the deployment tree and of the harness, distinct from the `source_commit.txt` of the Yocto image build (2.5).

### 4.4 Stream the archive over hostfwd 2222 into the engine, verify its identity

The archive is **not** staged on the guest: the root file system has only the 2 GiB `IMAGE_ROOTFS_EXTRA_SPACE` headroom shared with `/opt/egw` and the journal, and the data disk is mounted only at `/var/lib/docker`; `docker load` reads its stdin (size of the archive: `archive_size_bytes` of the record; `UNVERIFIED:` a few hundred MB). The checksum guard of 4.3 runs again in front of the load:

```bash
host$ ssh egw-tcg 'df -h / /var/lib/docker'                       # before
host$ if ctl_ok; then ssh egw-tcg docker load < ~/egw-images/egw-controller-0.1.0-arm64.tar && echo "LOADED" || echo "STOP: docker load failed - the controller image is NOT in the guest"; else echo "STOP: NOTHING was loaded (in a new shell define ctl_ok again, 4.3)"; fi
host$ ssh egw-tcg 'mkdir -p /opt/egw/images' && scp ~/egw-images/egw-controller-0.1.0-arm64.identity.txt /home/ruisth/yocto/egw/src/deployment/scripts/verify-controller-image.sh egw-tcg:/opt/egw/images/ && echo "COPIED" || echo "STOP: the identity record and verify-controller-image.sh did NOT reach the guest (a clone without the script copies nothing)"     # a few KB
host$ ssh egw-tcg 'mkdir -p /opt/egw/evidence && cd /opt/egw/images && sh verify-controller-image.sh egw-controller-0.1.0-arm64.identity.txt > /opt/egw/evidence/controller-image-verify.txt 2>&1; rc=$?; cat /opt/egw/evidence/controller-image-verify.txt; exit $rc' || echo "STOP: controller image identity NOT verified - do not continue with Section 5"
```

Modern OpenSSH `scp` uses the SFTP protocol; the guest's `sftp-server` is at `/usr/libexec/sftp-server` (poky packages it as `${libexecdir}/sftp-server`, `openssh_9.6p1.bb` line 189 — same path in the G1 rootfs; assumption A8 that the new image keeps `openssh-sftp-server`); if the copy is refused, add `-O`. Throughput under slirp+TCG is low. Fallback if streaming through `ssh` misbehaves: `scp` the archive to `/opt/egw/images`, `docker load -i` it, delete it, with `df -h /` between steps.

The last line must print five `OK:` lines (image id, architecture `arm64`, os `linux`, the image's revision label against `image_revision_label` of the record, and the source commit with `clean build context`) and `CONTROLLER IMAGE IDENTITY: verified (egw-controller:0.1.0 = sha256:...)`; the script (POSIX sh, changes nothing) exits 1 when the image is absent, when any of the four compared values differs, or when the record comes from a **dirty** build context (`source_tree_state=dirty`), and 2 when the record is unreadable. The same check stands in front of `up -d` in 5.5; the transcript kept as evidence is the one this line writes into `/opt/egw/evidence/controller-image-verify.txt` on the guest, which 6.6 fetches (the run inside the 5.5 interlock prints to the terminal and leaves that file alone). A mismatch means the archive was altered, the wrong platform was saved, or the guest engine re-computed a different config — stop and investigate; never proceed with an unverified image. The script's `--allow-dirty` option exists for development and has no place in this procedure: the authorisation requires a build from a clean, identified checkout, which is also what the host-side `ctl_ok` of 4.3 already refuses to accept otherwise. Keep the identity record, the `imagetools-*.txt` files, the pull transcript of 5.2a (`/opt/egw/evidence/images-pull-identity.txt`) and the verification transcripts in the evidence directory: together they are the "identity of all images known" acceptance of work order item 4 (external images: manifest-list digest -> `RepoDigests` in the guest; controller: source commit -> archive sha256 -> image ID in the guest).

`UNVERIFIED:` docker-moby 25.0.9 `docker load` accepts the OCI-layout tar that a 29.x `docker save` may produce (moby's `load.go` reads `manifest.json` `RepoTags`, verified; OCI-layout import support in 25.0 not checked). If `docker load` reports an unknown format, re-save from a legacy-format engine or with the containerd store disabled.

### 4.5 The compose adjustment — state of the points proposed here (2026-09-18, LOG `#C030`)

The earlier revision proposed six edits to `src/deployment` for the offline route. With the route of this section:

1. **Done.** `compose.yaml`, service `controller`: no `build:`, `image: egw-controller:0.1.0`, `platform: linux/arm64`, plus `pull_policy: never` (a missing image is a named failure, never a pull or a build); header comment, README step 6 and the last echo of `scripts/validate-config.sh` say `up -d` without `--build`.
2. **Superseded.** No `images.offline.env`: `images.lock.env` stays the only source of the five references and the second `--env-file` of every compose command.
3. **Superseded** for the five external images (their identity is the `RepoDigests` check of 5.2a); **done in a smaller form** for the controller: the identity record of `scripts/build-controller-image.sh` and the guest-side `scripts/verify-controller-image.sh` (4.4). No `images.identity.env`.
4. **Done** (on `dev`): `scripts/generate-dev-auth.sh` and `scripts/prepare-broker-secrets.sh` honour `EGW_BROKER_IMAGE` (and `LOCK_FILE`). On this guest the variable is no longer set: after 5.2a the digest-pinned `IMAGE_MOSQUITTO` of `images.lock.env` resolves locally. `UNVERIFIED:` never executed against a Docker engine.
5. **Superseded.** No second env file to validate; `scripts/validate-config.sh` gained step 7 instead (the controller image must be present on the engine).
6. **Done.** `scripts/probe-acl.sh` (POSIX sh, runs on the guest; the ACL proof with known traffic of integration test 9(d)) is on `dev`, reaches the guest with the `scp -r` of 5.1 and now takes `images.lock.env` as its default second env file; `src/egw_experiments/itest_reconcile.py` (host side, `python -m egw_experiments.itest_reconcile`) is versioned with unit tests (`src/tests/test_experiments_itest_reconcile.py`, fakes only). It applies the harness's own confirmation rule and the before/after counter comparisons to the ad-hoc `itest-*` runs of Sections 6 and 7, imports `CONFIRMATION_WINDOW_S`, `poll_controller_marker` and `compute_run_metrics` from the harness, never takes the window from a file, and changes no existing module. Neither was ever executed against the real stack.

**Still open:** the runtime lock of the controller's Python dependencies (4.1); the `compose.tcg.yaml` override of 5.5 (only if needed); the README's `/opt/egw/src/deployment` path (5.1); `.github/workflows/manual-arm64-integration.yml` (line 30 runs `validate-config.sh`, whose step 7 now fails on a runner without the controller image, and line 34 still says `up -d --build` with nothing to build) — that workflow is `workflow_dispatch` on a self-hosted runner that does not exist, and it is not on the path of this runbook; the header comments of `src/Dockerfile` (lines 3-5) and `src/.dockerignore` (line 2), which still name the compose build context that `compose.yaml` no longer has. That comment edit belongs **before** the evidence build: the identity record's `dockerfile_sha256` hashes the whole file.

Guest command shape: `docker compose --env-file .env --env-file images.lock.env up -d`; Sections 5 to 7 use it.

---

## 5. Deploy

### 5.1 Copy the deployment tree

Fixed guest layout (first-round review, audit report `docs/reviews/2026-09-17-egw-image-audit.md` section 11): the deployment tree lives at **`/opt/egw/deployment`**; the README's `/opt/egw/src/deployment` and the collector header's `/opt/egw/scripts` examples must be updated in the deployment PR, and until then every harness hook passes the explicit path.

```bash
host$ chk_deploy='ls scripts/prepare-broker-secrets.sh scripts/probe-acl.sh scripts/verify-controller-image.sh >/dev/null && grep -q "3b\." scripts/validate-config.sh && grep -q "chown mosquitto:mosquitto" scripts/generate-dev-auth.sh'
host$ if (cd /home/ruisth/yocto/egw/src/deployment && eval "$chk_deploy"); then scp -r /home/ruisth/yocto/egw/src/deployment egw-tcg:/opt/egw/ && echo "COPIED" || echo "STOP: scp failed - the copy on the guest may be PARTIAL; resolve the cause and repeat this line"; else echo "STOP: this clone does not carry the broker-permission change set - NOTHING was copied"; fi
host$ ssh egw-tcg 'ls -la /opt/egw/deployment; stat -c "%U:%G %n" /opt/egw/deployment'
host$ if ssh egw-tcg "cd /opt/egw/deployment && $chk_deploy"; then echo "guest deployment tree carries the change set"; else echo "STOP: stale or missing deployment tree on the guest - do not continue with 5.2"; fi
```

Guard on the change set: the copy happens **inside** the guard, so a clone without the change set copies nothing (the first version of this step printed `STOP` and then ran `scp` on the next line regardless). The second line must print `COPIED` and the fourth `guest deployment tree carries the change set`; neither may print `STOP`. The same three tests are repeated in front of `up -d` in 5.5, which is the point where a stale tree would do damage, so a `STOP` overlooked here still cannot start the stack. `prepare-broker-secrets.sh`, `probe-acl.sh`, step 3b of `validate-config.sh` and the `chown` of `generate-dev-auth.sh` are on `dev` since `0e536cd`, and `verify-controller-image.sh` comes with LOG `#C030`; the clone reaches that state through the checkout of 4.3, which is the only step that fixes which commit the tree copied here belongs to. Until it has run, the clone can still hold the seven scripts of 10 August. A stale tree fails loudly in 5.4a (missing script), but its `validate-config.sh` has no broker read test (step 3b) and would let `up -d` proceed into the broker restart loop that 5.4a exists to prevent — hence the check here, before anything is generated on the guest.

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
host$ V='MOSQUITTO_SIMULATOR_PASSWORD|MOSQUITTO_CONTROLLER_PASSWORD|EGW_MQTT_PASSWORD|DITTO_DEVOPS_PASSWORD'; if [ ! -s ~/egw-tcg/.env ]; then echo "STOP: ~/egw-tcg/.env is missing or empty - nothing was copied"; elif grep -nE '^[A-Za-z_][A-Za-z0-9_]*=.*CHANGE_ME' ~/egw-tcg/.env; then echo "STOP: placeholder value(s) on the line(s) above - .env was NOT copied"; elif [ "$(grep -cE "^($V)=.{16,}\$" ~/egw-tcg/.env)" != 4 ]; then echo "STOP: one of the four passwords is empty or shorter than 16 characters (did openssl fail?) - .env was NOT copied"; else chmod 600 ~/egw-tcg/.env && scp ~/egw-tcg/.env egw-tcg:/opt/egw/deployment/.env && echo "COPIED" || echo "STOP: chmod or scp failed - .env was NOT copied"; fi
```

The last line is the guard. It looks for `CHANGE_ME` in **assignments only** (`NAME=...CHANGE_ME...`): line 3 of `.env.example` is a comment that contains the word (`# Copy to .env, fill in the CHANGE_ME values, ...`), and the first version of this guard (`grep -n CHANGE_ME`) matched it, so it would have printed `STOP` on every correctly filled file - a guard that always fires is a guard that gets bypassed. It also refuses a missing or empty file and any of the four passwords that is empty or shorter than 16 characters (a failed `openssl rand` would otherwise replace a placeholder by nothing and pass), and a failed `chmod`/`scp` prints `STOP` instead of nothing. It must print `COPIED`. Step 1 of `scripts/validate-config.sh` now applies the same rule (`grep -Eq '^[A-Za-z_][A-Za-z0-9_]*=.*CHANGE_ME'`); until that correction it matched the comment too, so the interlock of 5.5 could never have passed with the `.env` this step produces.

`EGW_HOST` stays empty: the simulator connects to `127.0.0.1` (hostfwd) and the default SAN already contains `IP:127.0.0.1`. `EGW_MQTT_PASSWORD` must equal `MOSQUITTO_CONTROLLER_PASSWORD` (compose wires the latter into the controller). Keep `~/egw-tcg/.env` on the host: the simulator and harness read the simulator password from it.

### 5.2a Pull the five external images by their pinned digests (guest)

```sh
guest$ cd /opt/egw/deployment
guest$ docker compose --env-file .env --env-file images.lock.env pull mosquitto mongodb ditto-policies ditto-things ditto-gateway; echo "pull exit=$?"
guest$ mkdir -p /opt/egw/evidence
guest$ { n=0; bad=0; for ref in $(sed -n 's/^IMAGE_[A-Z_]*=//p' images.lock.env); do
           n=$((n+1)); got=$(docker image inspect --format '{{.RepoDigests}} {{.Architecture}}/{{.Os}}' "$ref" 2>/dev/null)
           case "$got" in *"@${ref##*@}"*" arm64/linux") echo "OK   $ref";; *) echo "FAIL $ref got=$got"; bad=$((bad+1));; esac
         done; if [ "$bad" = 0 ] && [ "$n" = 5 ]; then echo "IMAGE IDENTITY: all $n pulled images carry their pinned digest"; else echo "STOP: image identity NOT verified ($bad FAIL, $n checked, 5 expected) - do not continue with 5.3"; fi; } | tee /opt/egw/evidence/images-pull-identity.txt
```

Must print `pull exit=0`, five `OK` lines and `IMAGE IDENTITY: all 5 ...` (4.2). The verdict is the pinned-digest half of 4.4's identity acceptance, so the whole group is written through `tee` into `/opt/egw/evidence/images-pull-identity.txt`, which 6.6 fetches; the counters `n` and `bad` live inside the group, which the pipe runs in a subshell, and nothing after it reads them. The pull names the five services because the controller is never pulled (`pull_policy: never`); `UNVERIFIED:` how a bare `pull` treats that service in Compose 2.26.0, the duration under slirp+TCG (65 s for `mongo` alone, 3.5), and that the `mongo` image of 3.5 is not downloaded again. `docker image inspect` of a `repo:tag@sha256:` reference was observed on this guest (`docs/evidence/integrated-qemu/2026-09-18-mongodb7-isolated/guest/phase1.txt`).

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

The broker image was pulled in 5.2a, so both broker scripts resolve the digest-pinned `IMAGE_MOSQUITTO` of `images.lock.env` locally and `EGW_BROKER_IMAGE` stays unset (it is the override for a host that holds the image only as a loaded tag):

```sh
guest$ cd /opt/egw/deployment
guest$ set -a; . ./.env; set +a
guest$ sh scripts/generate-dev-auth.sh
guest$ stat -c '%u:%g %a %n' mosquitto/config/passwd        # expected: 1883:1883 600
```

The script runs `mosquitto_passwd` as root inside a one-shot container of that image and then, still inside it, `chown mosquitto:mosquitto` and `chmod 600` on the file, so the hash file belongs to the broker's unprivileged user (uid/gid 1883) and to nobody else; the passwords travel through the environment, never through argv or files. `egw` can no longer read `passwd` — intended.

### 5.4a Broker secrets: ownership, modes and read test as the broker uid

```sh
guest$ cd /opt/egw/deployment
guest$ sh scripts/prepare-broker-secrets.sh --acl
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
guest$ stat -c '%u:%g %n' data/events           # expected 1000:1000 (created by egw); otherwise: sudo chown -R 1000:1000 data
guest$ docker compose --env-file .env --env-file images.lock.env config --images   # UNVERIFIED: --images flag in Compose 2.26; else omit
guest$ if ls scripts/prepare-broker-secrets.sh scripts/probe-acl.sh >/dev/null && grep -q '3b\.' scripts/validate-config.sh && sh scripts/verify-controller-image.sh /opt/egw/images/egw-controller-0.1.0-arm64.identity.txt && sh scripts/validate-config.sh; then docker compose --env-file .env --env-file images.lock.env up -d; echo "up exit=$?"; else echo "STOP: stale deployment tree, unverified controller image or validate-config.sh failed - the stack was NOT started"; fi
guest$ L=$(docker compose --env-file .env --env-file images.lock.env logs --no-color mosquitto) && [ -n "$L" ] && { echo "$L" | grep -E 'Error|Warning'; echo "grep exit=$? (expected 1: no such line in a broker log that WAS read, $(echo "$L" | wc -l) lines)"; } || echo "STOP: the broker log was NOT read (docker compose logs failed or printed nothing) - the absence of Error/Warning lines is NOT shown"
```

The third line is the interlock: `up -d` runs only if the tree carries the change set of 5.1 (the two scripts, and step 3b in `validate-config.sh`), the loaded controller image matches its identity record in all four compared values, the record's revision label included, and that record is from a clean build context (4.4), **and** `validate-config.sh` exits 0 (step 1 looks for `CHANGE_ME` in assignments only, 5.2; step 3b = `prepare-broker-secrets.sh --check`, changes nothing, no sudo; step 4 reads `images.lock.env` for the digest-format check; `compose config -q` pulls nothing; step 7 requires the controller image on the engine and, when it is absent, names `docker load -i <archive>` as the only remedy — never a build, never a pull). `up -d` itself pulls nothing when 5.2a was done (`UNVERIFIED:` that Compose 2.26.0 finds the images pulled as `repo:tag@sha256:` without contacting the registry again). It must print `up exit=0`. `validate-config.sh` must end with `OK: configuration is complete and consistent`; a failure of step 3b means the broker's unprivileged user (uid 1883) cannot read `server.key`/`passwd` or a secret is open to others — go back to 5.4a, never work around it by running the broker as root or by `chmod 644`. The last command is the post-start confirmation: a permission problem appears in the broker log as `Error: Unable to load server key file`, `Error: Unable to open pwfile` or `Error: Unable to open acl_file` (strings from the Mosquitto 2.0.22 sources), and the container then restart-loops and never becomes `healthy`, which also blocks the controller (`depends_on: service_healthy`). The 30-second healthcheck lines (`egw-healthcheck ... not authorised`) are expected and are assumed to contain neither `Error` nor `Warning` (`UNVERIFIED:` exact log wording).

**TCG start-up caveat.** The Ditto healthchecks are `start_period: 120s, interval 30s, retries 4` and the controller `depends_on` mosquitto and ditto-gateway with `condition: service_healthy` (verified compose.yaml). Under TCG the three JVMs start much more slowly than natively (`UNVERIFIED:` how much; tens of minutes is the earlier estimate); if a Ditto service is marked unhealthy before it answers `/alive`, `up -d` fails with "dependency failed to start". If that happens, do **not** touch the protocol or the compose file itself: create a documented TCG profile override `compose.tcg.yaml` (proposed, deployment PR) that only raises `start_period`/`retries` of the three Ditto healthchecks and of the controller, and run `docker compose --env-file .env --env-file images.lock.env -f compose.yaml -f compose.tcg.yaml up -d`. Record the override in the evidence; work order item 7 allows exactly this ("documented profile") and forbids silent changes to confirmation windows or loss criteria.

### 5.6 Health checks (guest)

```sh
guest$ docker compose --env-file .env --env-file images.lock.env ps
guest$ curl -s http://127.0.0.1:8000/health; echo
guest$ curl -s -o /dev/null -w '%{http_code}\n' http://127.0.0.1:8000/ready
guest$ curl -s http://127.0.0.1:8000/metrics; echo
guest$ docker compose --env-file .env --env-file images.lock.env logs --no-color --tail 20 mongodb | grep -iE 'illegal|error|Waiting for connections'
```

Expected: six services, all `healthy`; `{"status":"ok"}`; `200` (MQTT connected and Ditto reachable — CONTRACTS §5); counters at zero. `curl` must be in the image (assumption A11; `measure-cold-start.sh` line 74 needs it). Fallback if it is missing: `wget -q -O - http://127.0.0.1:8000/health` and `wget -S -q -O /dev/null http://127.0.0.1:8000/ready 2>&1 | head -n 1` (BusyBox wget, present) — but then `measure-cold-start.sh` cannot run, which is a defect of the image, not of the runbook.

Record `docker compose ps`, `docker system df -v` and `du -sh /var/lib/docker` for the sizing acceptance of item 2.

### 5.7 SSH tunnels for the loopback-only APIs (host)

Ports 8080 (Ditto gateway) and 8000 (controller) are bound to `127.0.0.1` **inside the guest**; forwarding them at the QEMU NIC would not expose them (work order item 5), so they are reached through SSH:

```bash
host$ cat > ~/egw-tcg/tunnel.sh <<'EOF'
# ~/egw-tcg/tunnel.sh - HOST side (bash). Source it, never execute it. The tunnel of this project is identified by ITS OWN
# control socket and by nothing else: no command here matches processes by name, so no other ssh session is ever touched.
TUNNEL_SOCK=${TUNNEL_SOCK:-$HOME/egw-tcg/tunnel.ctl}

# tunnel_check: 0 only when an ssh master answers on this project's control socket. A non-zero status shows only that no
# answer was obtained: ssh exits 255 for a stale socket, for a missing socket AND when the client cannot run at all
# (for example an error in ~/.ssh/config), so it is never read as "no master exists".
tunnel_check() { ssh -S "$TUNNEL_SOCK" -O check egw-tcg 2>/dev/null; }

# tunnel_down: closes the master behind this project's socket ('-O exit'), or removes the socket file when ssh reports
# "Connection refused" on it (no process listens: stale). Any other failure of the check leaves the file alone (STOP).
# Anything at that path that is not a socket is left alone and reported.
tunnel_down() {
  local e
  if [ ! -e "$TUNNEL_SOCK" ] && [ ! -L "$TUNNEL_SOCK" ]; then echo "tunnel: no control socket at $TUNNEL_SOCK - nothing to close"; return 0; fi
  if tunnel_check; then
    ssh -S "$TUNNEL_SOCK" -O exit egw-tcg && echo "TUNNEL CLOSED" && return 0
    echo "STOP: 'ssh -O exit' failed on $TUNNEL_SOCK - the tunnel may still be open"; return 1
  fi
  if [ -S "$TUNNEL_SOCK" ]; then
    e=$(LC_ALL=C ssh -S "$TUNNEL_SOCK" -O check egw-tcg 2>&1)
    case $e in *"Connection refused"*) ;; *) echo "STOP: 'ssh -O check' on $TUNNEL_SOCK could not be evaluated ($e) - the socket file was left alone; a master may still be running behind it"; return 1;; esac
    rm -f "$TUNNEL_SOCK" && echo "tunnel: connection refused on $TUNNEL_SOCK (no process listens on it) - stale socket file removed" && return 0
    echo "STOP: the stale socket file $TUNNEL_SOCK could not be removed"; return 1
  fi
  echo "STOP: $TUNNEL_SOCK exists and is not a socket - NOT removed; look at it before anything else"; return 1
}

# tunnel_up: opens the two forwards as a master on this project's socket. An answering master is reported, never doubled.
# "TUNNEL UP" is printed only for a master opened by this call (ssh exit 0 with ExitOnForwardFailure AND an answering master).
tunnel_up() {
  if tunnel_check; then echo "MASTER ANSWERS on $TUNNEL_SOCK ('ssh -O check' asks the master process only: its connection and forwards are NOT tested and nothing was reopened; 'tunnel_down && tunnel_up' reopens it)"; return 0; fi
  tunnel_down || return 1
  if ss -ltn | grep -E ':(8000|8080) '; then echo "STOP: host port busy (line above) - the tunnel was NOT opened. No master answers on $TUNNEL_SOCK, so the owner of the port is not known here: identify it with 'ss -ltnp' and close THAT process only"; return 1; fi
  ssh -f -N -M -S "$TUNNEL_SOCK" -o ExitOnForwardFailure=yes -L 8000:127.0.0.1:8000 -L 8080:127.0.0.1:8080 egw-tcg || { echo "STOP: ssh exited non-zero - the tunnel was NOT opened"; return 1; }
  tunnel_check && echo "TUNNEL UP" && return 0
  echo "STOP: ssh went to the background but no master answers on $TUNNEL_SOCK - a forwarder may be running outside the control of tunnel_down: look at 'ss -ltnp'"; return 1
}
EOF
host$ bash -n ~/egw-tcg/tunnel.sh && . ~/egw-tcg/tunnel.sh && tunnel_up
host$ curl -s -o /dev/null -w '%{http_code}\n' http://127.0.0.1:8000/ready
host$ curl -s http://127.0.0.1:8000/metrics | python3 -m json.tool
host$ curl -s -o /dev/null -w '%{http_code}\n' http://127.0.0.1:8080/health   # Ditto gateway; UNVERIFIED: exact path of the gateway health endpoint (the compose healthcheck uses port 7626 inside the container)
```

With a busy local port an `ssh -L` without `ExitOnForwardFailure=yes` only warns and stays up without that forward, so the `curl` lines below would talk to whatever else listens on 8000/8080; the option (OpenSSH `ssh_config`) makes ssh exit non-zero instead, and the line then prints `STOP:` and not `TUNNEL UP`. If other local ports must be used, export `CTRL=http://127.0.0.1:<port>` and `DITTO=http://127.0.0.1:<port>` before sourcing the helpers of 6.1 (they pass both on to `$REC`) and, in the explicit `$REC` lines of Sections 6 and 7, add `--controller-url $CTRL` to `mark` and `wait` and `--ditto-url $DITTO` to `snap`. `check` accepts `--controller-url` and does not use it (it reads files only); `delta` and `same` take neither option, so adding one to them is a usage error (exit 2). The five explicit `snap` lines of 6.5 and of tests 6 and 8 carry no `--ditto-url` and would otherwise read `http://127.0.0.1:8080`, so they must be edited as well. The profile's sshd drop-in keeps the tunnel alive (`ClientAliveInterval 60`, assumption A12).

The tunnel is opened as an ssh master (`-M`) on a control socket that belongs to this project only, `~/egw-tcg/tunnel.ctl` (`-S`), and it is checked and closed **through that socket** (`ssh -S ... -O check`, `-O exit`): `tunnel_check`, `tunnel_down`, `tunnel_up`. No process is ever matched by name (project review of 2026-09-18). `tunnel_down` closes only the master that answers on this socket; a socket file is removed as stale only when `ssh -O check` reports `Connection refused` on it (no process listens: the master died with the guest) — ssh exits 255 for that, for a missing socket and for a client that cannot run at all (an error in `~/.ssh/config`), so any other failure is a `STOP:` and the file is left alone; a path that is not a socket is reported with `STOP:` and left alone; with a busy port and no answering master the owner is not known, it is reported and nothing is killed. `-O check` asks the master **process** only (`ssh(1)`): an answering master is reported as `MASTER ANSWERS`, not as `TUNNEL UP`, and after a guest stop or reboot the tunnel is reopened with `tunnel_down && tunnel_up`. Stop the tunnel later with `tunnel_down`. In a new shell, `. ~/egw-tcg/tunnel.sh` again (the helper file of 6.1 does it as well). `UNVERIFIED:` `-M`, `-S`, `-O check` and `-O exit` are documented `ssh(1)` options; their combination with `-f -N -o ExitOnForwardFailure=yes` on the host's OpenSSH 9.6 was exercised with a stub `ssh` only, except `-O check` on a stale and on a missing socket file, which was run with the real client (Appendix B item 20).

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

Fill the two `<from runqemu log>` values from the `Running ...` line of 3.3. Fetch it (the copy is evidence, so its failure is printed): `host$ scp egw-tcg:/opt/egw/evidence/sut_environment.json ~/egw-tcg/ && [ -s ~/egw-tcg/sut_environment.json ] && echo "FETCHED" || echo "STOP: sut_environment.json was NOT fetched"`.

---

## 6. First full flow (work order item 6 — the first decisive deliverable)

### 6.1 Host tooling

```bash
host$ python3 -m venv ~/egw-venv && . ~/egw-venv/bin/activate
host$ pip install -e /home/ruisth/yocto/egw/src          # paho-mqtt, jsonschema, httpx, fastapi, uvicorn (pyproject.toml)
host$ python -m egw_simulator run --help | head -n 5
host$ scp egw-tcg:/opt/egw/deployment/mosquitto/config/certs/ca.crt ~/egw-tcg/ca.crt
host$ set -a; . ~/egw-tcg/.env; set +a                   # exports MOSQUITTO_SIMULATOR_PASSWORD etc. into this shell
host$ export EGW_SCHEMA_DIR=/home/ruisth/yocto/egw/src/schemas   # .env carries the host-side default EGW_SCHEMA_DIR=src/schemas, which resolves only from the clone root; the simulator dies with FileNotFoundError on the envelope schema otherwise (observed 2026-09-18)
```

The simulator must run in **WSL**, not in Windows: runqemu binds the hostfwd listeners on the WSL side's `127.0.0.1`.

**Shell helpers for Sections 6 and 7.** Write them once to a file outside the repository and source it in every new host shell (after the venv and the `.env` line above). The heredoc is quoted, so the file holds the text `$MOSQUITTO_SIMULATOR_PASSWORD`, never the password; it may be copied into the evidence (6.6). `$REC` is the host-side helper of 4.5 item 6 (`egw_experiments.itest_reconcile`), which reuses the harness rule (6.4).

```bash
host$ cat > ~/egw-tcg/itest-helpers.sh <<'EOF'
# ~/egw-tcg/itest-helpers.sh - HOST side: bash on the WSL2 host, inside the venv. Source it, never execute it:
#     set -a; . ~/egw-tcg/.env; set +a; . ~/egw-tcg/itest-helpers.sh
# Rule: every function returns non-zero and prints a line starting with "STOP:" when a precondition or a step
# fails. Chain calls with && or if/else so that nothing runs after a STOP. No secret is stored in this file.
P=$HOME/egw-tcg/itest
CTRL=${CTRL:-http://127.0.0.1:8000}        # controller through the tunnel of 5.7
DITTO=${DITTO:-http://127.0.0.1:8080}      # Ditto gateway through the tunnel of 5.7
MQTT_PORT=${MQTT_PORT:-8883}               # the forwarded host port (3.3: set it first if runqemu re-mapped 8883)
REC="python -m egw_experiments.itest_reconcile"
SIM="python -m egw_simulator run --broker 127.0.0.1 --port $MQTT_PORT --username egw-simulator --password $MOSQUITTO_SIMULATOR_PASSWORD --ca-cert $HOME/egw-tcg/ca.crt --egw-id egw-01 --output $P --qos 1"
mkdir -p "$P"
[ ! -r "$HOME/egw-tcg/tunnel.sh" ] || . "$HOME/egw-tcg/tunnel.sh"     # tunnel_up / tunnel_down / tunnel_check of 5.7

stop() { echo "STOP: $*" >&2; return 1; }

# wait_ready [limit_s]: GET /ready must answer 200 (MQTT subscribed AND Ditto reachable, CONTRACTS 5).
wait_ready() {
  local limit=${1:-60} t0=$SECONDS code
  while :; do
    code=$(curl -s -o /dev/null -w '%{http_code}' --max-time 30 "$CTRL/ready")
    [ "$code" = 200 ] && return 0
    [ $((SECONDS - t0)) -ge "$limit" ] && { stop "wait_ready: /ready answered '$code', not 200, for ${limit} s (tunnel of 5.7 down? stack not healthy?)"; return 1; }
    sleep 5
  done
}

# One /metrics reading on one line, THIRTEEN fields in this fixed order:
#   queue_depth in_progress unacked mqtt_subscribed started_at mqtt_connection received accepted rejected duplicate failed dropped processing_errors
# No line and a non-zero status on any HTTP, connection or JSON problem and when any of the thirteen is missing or of
# the wrong type (CONTRACTS 5: an absent progress field is never read as zero). Status 3, WITH the line, when the
# accounting identity of CONTRACTS 5 does not hold in that same response:
#   received == accepted + rejected + duplicate + failed + dropped + processing_errors + in_progress + queue_depth
# ("do not trust this reading": it is a reading that is never quiet, not a STOP). unacked is not a term of it.
_mline() {
  curl -fsS --max-time 30 "$CTRL/metrics" | python3 -c '
import json, sys
m = json.load(sys.stdin)
ints = ("queue_depth", "in_progress", "unacked", "mqtt_connection", "received", "accepted", "rejected", "duplicate", "failed", "dropped", "processing_errors")
for k in ints:
    v = m.get(k)
    if not isinstance(v, int) or isinstance(v, bool) or v < 0:
        sys.exit(2)
if not isinstance(m.get("mqtt_subscribed"), bool):
    sys.exit(2)
s = m.get("started_at")
if not isinstance(s, str) or not s or s.split() != [s]:
    sys.exit(2)
print(m["queue_depth"], m["in_progress"], m["unacked"], str(m["mqtt_subscribed"]).lower(), s, m["mqtt_connection"], m["received"], *(m[k] for k in ("accepted", "rejected", "duplicate", "failed", "dropped", "processing_errors")))
sys.exit(0 if m["received"] == sum(m[k] for k in ("accepted", "rejected", "duplicate", "failed", "dropped", "processing_errors", "in_progress", "queue_depth")) else 3)'
}

# drained: a TEMPORARY PRECAUTION, NOT proof that processing has finished (Section 7, "The 130 s quiet window").
# It reports one observation: EVERY reading taken during one unbroken quiet window of DRAIN_QUIET_S seconds was QUIET -
# queue_depth, in_progress and unacked 0, mqtt_subscribed true and the accounting identity holding in that response -
# and showed the same started_at, mqtt_connection, received, accepted, rejected, duplicate, failed, dropped and
# processing_errors. A reading that is not quiet, a reading whose identity fails, any movement of those nine fields,
# a new connection or a controller restart opens a new window. What a reading cannot show: a message still being handed
# over from the MQTT thread to the event loop, and a message the broker holds and has not sent (CONTRACTS 5; Section 7).
# DRAIN_QUIET_S stays ABOVE the NOMINAL longest time one message can be in progress (130 s > 122.4 s with the default
# retry settings); that figure is NOT a bound (Section 7 (b)): the per-phase sum is 40 s per attempt, 482.4 s for a
# first-contact message - export DRAIN_QUIET_S=490 to cover it. Never lower it. What a run's messages ended in is
# settled per identity by 'accounted' (below) and by '$REC check'.
drained() {
  local quiet=${DRAIN_QUIET_S:-130} step=${DRAIN_STEP_S:-5} limit=${DRAIN_LIMIT_S:-900}
  local t0=$SECONDS since=$SECONDS ref= cur rc n=0 q qd ip un sub rest
  while :; do
    cur=$(_mline); rc=$?
    case $rc in
      0) read -r qd ip un sub rest <<< "$cur"; q=0
         [ "$qd" = 0 ] && [ "$ip" = 0 ] && [ "$un" = 0 ] && [ "$sub" = true ] && q=1;;
      3) q=0;;
      *) stop "drained: GET $CTRL/metrics failed or was not valid JSON, or a field was missing or of the wrong type (tunnel of 5.7 down? controller stopped? a controller build without the thirteen fields?)"; return 1;;
    esac
    if [ "$q" != 1 ] || [ "$cur" != "$ref" ]; then
      ref=$cur; since=$SECONDS; n=1
    else
      n=$((n + 1))
      if [ $((SECONDS - since)) -ge "$quiet" ]; then
        echo "drained: queue_depth 0 and identical counters on $n consecutive readings over $((SECONDS - since)) s ($cur) - also in_progress 0, unacked 0, mqtt_subscribed true, the identity held and started_at, mqtt_connection, received and the counters unchanged; an observation, not proof that processing has finished"
        return 0
      fi
    fi
    [ $((SECONDS - t0)) -ge "$limit" ] && { stop "drained: no quiet window of ${quiet} s within ${limit} s (last reading: $cur) - do not take snapshots, do not start a run"; return 1; }
    sleep "$step"
  done
}

fetch()   { scp -q "egw-tcg:/opt/egw/deployment/data/events/$1/events.jsonl" "$P/$1/events.jsonl" || stop "fetch $1: scp of events.jsonl failed"; }
twin()    { local f="$P/$1.twin.$2.json"; curl -fsS --max-time 30 -H 'x-ditto-pre-authenticated: pre:egw-controller' "$DITTO/api/2/things/org.c2dta:$2" > "$f.tmp" && mv "$f.tmp" "$f" || { rm -f "$f.tmp"; stop "twin $1 $2: GET failed - no file was written"; return 1; }; }

# keep <source> <destination>: write-once copy. Refuses a missing or empty source and an existing destination.
keep() {
  [ -s "$1" ] || { stop "keep: $1 is missing or empty - nothing was copied"; return 1; }
  [ ! -e "$2" ] || { stop "keep: $2 exists - NOT overwritten"; return 1; }
  cp "$1" "$2" || { stop "keep: cp $1 $2 failed"; return 1; }
}

# metrics <run-id> <label>: ONE /metrics reading in <run-id>.metrics.<label>.json. Write-once (an existing file is never
# overwritten: a failed precondition must not destroy the record of an earlier run) and atomic (written to .tmp,
# validated, then renamed: a failed curl or a non-JSON answer leaves no file behind).
metrics() {
  local f="$P/$1.metrics.$2.json"
  [ ! -e "$f" ] || { stop "metrics $1 $2: $f exists - run id and label already used; nothing was overwritten"; return 1; }
  curl -fsS --max-time 30 "$CTRL/metrics" > "$f.tmp" \
    && python3 -c 'import json,sys; m=json.load(open(sys.argv[1])); [m[k] for k in ("queue_depth","started_at","accepted","rejected","duplicate","failed","dropped")]' "$f.tmp" \
    && mv "$f.tmp" "$f" || { rm -f "$f.tmp"; stop "metrics $1 $2: GET /metrics failed or returned no valid JSON - no file was written"; return 1; }
}

# snap_pair <run-id> <label> [snap args...]: the /metrics reading AND the twin snapshot of one label - both or neither.
# If the twin snapshot fails, the /metrics reading just taken is set aside (renamed, never deleted), so that a label
# never keeps a /metrics file and a twins file that were not taken at the same instant.
snap_pair() {
  local id=$1 label=$2 f; shift 2; f="$P/$id.metrics.$label.json"
  metrics "$id" "$label" || return 1
  $REC snap --prefix "$P/$id" --label "$label" "$@" --ditto-url "$DITTO" && return 0
  mv "$f" "$f.unpaired-$(date -u +%Y%m%dT%H%M%SZ)"
  stop "snap_pair $id $label: the twin snapshot failed; the /metrics reading was set aside as $f.unpaired-<time>"
}

# accounted <run-id>: reconciles THIS run by IDENTITY. A published record (one line of sent_events.jsonl) counts as
# finished only when the fetched events.jsonl of this run holds a record with the SAME message_id, this run_id and one
# of the four outcomes (accepted, rejected, duplicate, failed: events.py, OUTCOMES). Every
# simulator record carries message_id (output.py, SENT_EVENT_FIELDS) and the invalid payloads keep their envelope
# (scenarios.py, InvalidInjector.mutate), so accepted, rejected, duplicate and failed all leave a record with that id
# (service.py, _emit). A message dropped at a full queue, one that ended in the except branch of the consumer loop and
# one that never reached the controller leave NO record: they are named and the function ends non-zero. A published
# record without a usable message_id, or whose message_id occurs more than once in sent_events.jsonl, is reported as
# NOT RECONCILABLE, never as OK. Totals decide nothing: the movement of the five counters since
# <run-id>.metrics.before.json is printed as a labelled secondary consistency figure only (A accepted and then received
# again as a duplicate, B without any outcome: the counters move by 2 for 2 published records, and B is still missing).
# Whether an outcome is an in-window confirmation is judged by '$REC check' (controller-clock deadline), not here.
# This function does not state that the controller has no other work pending: that is not observable (Section 7).
# It does not loop. ACCEPT_UNACCOUNTED=1 lets the capture go on when the operator accepts the absence (the log cannot
# tell a permanent absence from a transient one), records the fact in <run-id>.unaccounted.txt and makes 'finish' end
# non-zero; the 6.4 line refuses on that file as well.
accounted() {
  local id=$1 now rc
  [ -s "$P/$id/sent_events.jsonl" ] && [ -s "$P/$id/events.jsonl" ] && [ -s "$P/$id.metrics.before.json" ] \
    || { stop "accounted $id: sent_events.jsonl, the fetched events.jsonl or metrics.before.json is missing or empty - nothing to reconcile against"; return 1; }
  now=$(curl -fsS --max-time 30 "$CTRL/metrics") || { stop "accounted $id: GET $CTRL/metrics failed"; return 1; }
  python3 -c '
import json, sys
from collections import Counter
rid, run_dir, before_path, now_json, accept = sys.argv[1:6]
def jl(path):
    with open(path, encoding="utf-8") as fh:
        return [json.loads(line) for line in fh if line.strip()]
sent = jl(run_dir + "/sent_events.jsonl")
logged = {e.get("message_id") for e in jl(run_dir + "/events.jsonl") if isinstance(e.get("message_id"), str)
          and e.get("run_id") == rid and e.get("outcome") in ("accepted", "rejected", "duplicate", "failed")}
seen = Counter(r.get("message_id") for r in sent if isinstance(r.get("message_id"), str))
def usable(r):
    m = r.get("message_id")
    return isinstance(m, str) and m != "" and seen[m] == 1
def name(r):
    return "%s (%s seq=%s)" % (r.get("message_id"), r.get("device_type"), r.get("seq"))
good = [r for r in sent if usable(r)]
bad = [r for r in sent if not usable(r)]
missing = [r for r in good if r["message_id"] not in logged]
b = json.load(open(before_path, encoding="utf-8"))
a = json.loads(now_json)
keys = ("accepted", "rejected", "duplicate", "failed", "dropped")
print("OUTCOME RECONCILIATION %s: published=%d with_logged_outcome=%d without_logged_outcome=%d not_reconcilable=%d queue_depth=%s"
      % (rid, len(sent), len(good) - len(missing), len(missing), len(bad), a["queue_depth"]))
if a["started_at"] == b["started_at"]:
    d = {k: a[k] - b[k] for k in keys}
    print("  counters since the before reading (secondary consistency figure, decides nothing): total=%d %s" % (sum(d.values()), d))
else:
    print("  counters since the before reading: not comparable (started_at differs: the controller process restarted)")
for label, rows in (("NO LOGGED OUTCOME", missing), ("NOT RECONCILABLE", bad)):
    for r in rows[:20]:
        print("  %s: %s" % (label, name(r)))
    if len(rows) > 20:
        print("  %s: ... and %d more" % (label, len(rows) - 20))
if a["queue_depth"] != 0:
    print("-> queue_depth=%s at this reading: messages are still queued" % a["queue_depth"]); sys.exit(6)
if not sent:
    print("-> no published record was read from sent_events.jsonl: nothing was reconciled"); sys.exit(7)
if not missing and not bad:
    print("-> OK: every published record of this run has a logged outcome in the fetched event log"); sys.exit(0)
if accept == "1":
    print("-> %d published record(s) without a logged outcome, %d not reconcilable - accepted by the operator (ACCEPT_UNACCOUNTED=1): report as measured" % (len(missing), len(bad))); sys.exit(5)
print("-> %d published record(s) of this run have NO logged outcome in the fetched event log, %d cannot be reconciled by identity" % (len(missing), len(bad))); sys.exit(4)
' "$id" "$P/$id" "$P/$id.metrics.before.json" "$now" "${ACCEPT_UNACCOUNTED:-0}"; rc=$?
  case $rc in
    0) return 0;;
    5) echo "$(date -u +%FT%TZ) accounted $id: published records without a logged outcome accepted by the operator (see the OUTCOME RECONCILIATION lines)" >> "$P/$id.unaccounted.txt" \
         || { stop "accounted $id: $P/$id.unaccounted.txt could not be written - the operator's decision is NOT recorded, nothing was captured"; return 1; }
       return 0;;
    4) stop "accounted $id: published records of this run are named above as having no logged outcome in the fetched event log, or as not reconcilable. Repeat 'finish $id' later; if the same records are named again the absence MAY be permanent (dropped at a full queue, ended without a record, or never delivered) - the log cannot tell: 'ACCEPT_UNACCOUNTED=1 finish $id' captures the state and reports the run as FAILED"; return 1;;
    6) stop "accounted $id: queue_depth was not 0 at this reading - repeat 'finish $id' later"; return 1;;
    *) stop "accounted $id: the reconciliation could not be evaluated (python3 exit=$rc: unreadable or malformed input, or no published record) - nothing was decided"; return 1;;
  esac
}

# pre <run-id> <seed> [device types, comma-separated]: the 'before' state. Nothing may be published if it fails.
# The run id must be FRESH: checked first, before anything is read or written (and before the 130 s of 'drained').
pre() {
  local x
  [ -n "$1" ] && [ -n "$2" ] || { stop "pre: usage: pre <run-id> <seed> [device types]"; return 1; }
  for x in "$P/$1" "$P/$1.metrics.before.json" "$P/$1.twins.before.json" "$P/$1.marker.json"; do
    [ ! -e "$x" ] || { stop "pre $1: $x exists - this run id was already used and its artefacts are write-once: choose a NEW run id. Nothing was read, written or published"; return 1; }
  done
  wait_ready "${READY_LIMIT_S:-60}" && drained && snap_pair "$1" before --seed "$2" ${3:+--devices "$3"} \
    || { stop "pre $1: precondition failed - the simulator must NOT be started for this run id"; return 1; }
}

# _after <run-id>: the 'after' pair, taken once. A repeated 'finish' keeps an existing pair and never retakes it.
_after() {
  local m="$P/$1.metrics.after.json" t="$P/$1.twins.after.json"
  if [ -s "$m" ] && [ -s "$t" ]; then echo "finish $1: the 'after' snapshots already exist - kept, NOT retaken"; return 0; fi
  [ ! -e "$m" ] && [ ! -e "$t" ] || { stop "finish $1: only one of $m and $t exists (or one is empty) - they would not describe the same instant; set it aside (mv <file> <file>.unpaired) and repeat"; return 1; }
  snap_pair "$1" after
}

# finish <run-id>: everything after the marker. Safe to repeat after a STOP: the write-once window file and an
# existing 'after' pair are kept; 'drained', the fetch and 'accounted' are repeated.
finish() {
  local id=$1 c d
  { [ -f "$P/$id.window-closed.json" ] || $REC wait "$P/$id" --controller-url "$CTRL"; } && drained && fetch "$id" && accounted "$id" && _after "$id" \
    || { stop "finish $id: the 'after' state was NOT captured; once the cause is fixed run: finish $id"; return 1; }
  $REC check "$P/$id"; c=$?
  $REC delta "$P/$id"; d=$?
  [ "$c" = 0 ] && [ "$d" = 0 ] || { stop "finish $id: check exit=$c (3 = not a protocol check) delta exit=$d (4 = MISMATCH or queue not empty)"; return 1; }
  [ ! -e "$P/$id.unaccounted.txt" ] || { stop "finish $id: captured, but with published records without a logged outcome accepted by the operator ($P/$id.unaccounted.txt) - report as measured, not as complete"; return 1; }
}

# post <run-id>: the marker FIRST (it must be the very next command after the simulator), then finish.
post() {
  $REC mark "$P/$1" --controller-url "$CTRL" || { stop "post $1: the controller marker was not read - this run can only be an eventual-delivery observation (6.4)"; return 1; }
  finish "$1"
}

# sim_post <run-id> <simulator args...>: simulator, then post IMMEDIATELY and ALWAYS (also after a simulator
# failure: the marker and the evidence are still needed), then one status line. Non-zero if any of them failed.
# The transcript is evidence: if <run-id>.stderr.txt cannot be created the simulator is NOT started, and the status
# of 'tee' is read as well as the simulator's (EVERY element of PIPESTATUS, copied at once into an array: the next
# command would overwrite it). A transcript that was not written completely makes the run FAILED.
sim_post() {
  local id=$1 sim_rc tee_rc post_rc; local -a st; shift
  : > "$P/$id.stderr.txt" || { stop "TEST STATUS $id: the transcript $P/$id.stderr.txt cannot be written -> simulator NOT started, nothing published"; return 1; }
  $SIM "$@" --run-id "$id" 2>&1 | tee "$P/$id.stderr.txt"; st=("${PIPESTATUS[@]}"); sim_rc=${st[0]}; tee_rc=${st[1]}
  post "$id"; post_rc=$?
  if [ "$sim_rc" = 0 ] && [ "$tee_rc" = 0 ] && [ -s "$P/$id.stderr.txt" ] && [ "$post_rc" = 0 ]; then
    echo "TEST STATUS $id: simulator exit=0 transcript (tee) exit=0 post=0 -> PROCEDURE COMPLETE. This is NOT the verdict: compare the values printed above with the test's Expected list."
    return 0
  fi
  stop "TEST STATUS $id: simulator exit=$sim_rc transcript (tee) exit=$tee_rc post=$post_rc -> FAILED (a transcript exit other than 0, or an empty $id.stderr.txt, means that the evidence of this run is incomplete). Do not start another run before the cause is understood."
}

# run_test <run-id> <seed> [simulator args...]: pre, and only if pre succeeded, sim_post. The seed (and DEVICES,
# if set in the environment) is given ONCE and passed both to the 'before' snapshot and to the simulator.
run_test() {
  local id=$1 seed=$2
  [ -n "$id" ] && [ -n "$seed" ] || { stop "run_test: usage: run_test <run-id> <seed> [simulator args...]"; return 1; }
  shift 2
  pre "$id" "$seed" "${DEVICES:-}" || { stop "TEST STATUS $id: precondition failed -> simulator NOT started, nothing published"; return 1; }
  sim_post "$id" --seed "$seed" ${DEVICES:+--devices "$DEVICES"} "$@"
}

# harness_run <plan-run-id> [extra 'egw_experiments run' args...]: one harness run against the pilot plan (tests 1 and 6).
# The collector is told the six services the run must account for (--expect-services, handed to it as {expect_services});
# the fetch hook copies its CSV with the .diagnostics.log and .lifecycle.csv companions (and a .self-test marker, if any),
# each checked against the guest's sha256, with the fetch script of the checkout in EGW_CLONE (set below).
harness_run() {
  local id=$1; shift
  python -m egw_experiments run --run-id "$id" --plan ~/egw-tcg/pilot/campaign_plan.json --base-dir ~/egw-tcg/pilot/results \
    --broker 127.0.0.1 --port "$MQTT_PORT" --username egw-simulator --password "$MOSQUITTO_SIMULATOR_PASSWORD" --ca-cert ~/egw-tcg/ca.crt \
    --controller-url "$CTRL" --sut-env-from ~/egw-tcg/sut_environment.json \
    --fetch-events-cmd 'scp egw-tcg:/opt/egw/deployment/data/events/{run_id}/events.jsonl "{dest}"' \
    --expect-services egw-mosquitto-1,egw-mongodb-1,egw-ditto-policies-1,egw-ditto-things-1,egw-ditto-gateway-1,egw-controller-1 \
    --collector-start-cmd "ssh egw-tcg 'sudo systemd-run --unit egw-resources-{run_id} --collect sh /opt/egw/deployment/scripts/collect-resources.sh /tmp/resources-{run_id}.csv --duration {duration_s} --expect-services {expect_services}'" \
    --collector-stop-cmd "ssh egw-tcg 'sudo systemctl stop egw-resources-{run_id}'" \
    --collector-fetch-cmd "sh \"${EGW_CLONE:-$HOME/yocto/egw}/src/deployment/scripts/fetch-collector-output.sh\" egw-tcg /tmp/resources-{run_id}.csv \"{dest}\"" "$@" \
    || stop "harness_run $id: egw_experiments run exited non-zero"
}

# .env sets EGW_SCHEMA_DIR=src/schemas, which resolves only from the clone root: an
# absolute value here keeps the simulator working from any directory (2026-09-18).
# EGW_CLONE must name the checkout the harness runs from (the clean clone, e.g. export EGW_CLONE=$HOME/egw-exec/repo
# before sourcing this file): harness_run's fetch hook runs that checkout's fetch-collector-output.sh. The default
# below is the older Yocto clone.
EGW_CLONE=${EGW_CLONE:-/home/ruisth/yocto/egw}
case "${EGW_SCHEMA_DIR:-}" in
    /*) ;;
    *)  if [ -f "$EGW_CLONE/src/schemas/telemetry-envelope-v1.schema.json" ]; then
            export EGW_SCHEMA_DIR="$EGW_CLONE/src/schemas"
        else
            # No clone at that path: drop the relative value so the schemas shipped next to
            # the installed egw_simulator package are used (validation.py DEFAULT_SCHEMA_DIR).
            unset EGW_SCHEMA_DIR
        fi ;;
esac
[ -n "$MOSQUITTO_SIMULATOR_PASSWORD" ] || stop "MOSQUITTO_SIMULATOR_PASSWORD is empty: run 'set -a; . ~/egw-tcg/.env; set +a', then source this file again"
EOF
host$ bash -n ~/egw-tcg/itest-helpers.sh && . ~/egw-tcg/itest-helpers.sh && $REC --help >/dev/null && echo "helpers loaded, reconcile helper importable"
```

**`EGW_CLONE` must name the checkout the harness runs from** — the clean clone whose editable install `python -m egw_experiments` imports, for example `export EGW_CLONE=$HOME/egw-exec/repo` before the helper file is sourced. `harness_run` builds its fetch hook from `$EGW_CLONE/src/deployment/scripts/fetch-collector-output.sh`, and the manifest records the sha256 of the script that ran (`collector.fetch_helper_sha256`, with `collector.fetch_helper_path`), so a fetch run with another checkout's script is identifiable. The default kept in the helper file, `/home/ruisth/yocto/egw`, is the older Yocto clone; while it does not carry the fetch script, the fetch hook exits non-zero there and every `harness_run` ends invalid.

How the helpers enforce the order (what each one refuses to do):

| Helper | Does | Stops (prints `STOP:`, returns non-zero) when |
|---|---|---|
| `wait_ready [s]` | polls `GET /ready` until 200 | no 200 within the limit (default 60 s) |
| `drained` | waits until every `/metrics` reading of one unbroken quiet window showed `queue_depth`, `in_progress` and `unacked` 0, `mqtt_subscribed` true and the accounting identity of CONTRACTS §5 holding in that same response, with `started_at`, `mqtt_connection`, `received` and the six counters (`accepted`, `rejected`, `duplicate`, `failed`, `dropped`, `processing_errors`) unchanged: a **temporary precaution, not proof that processing has finished** (Section 7, "The 130 s quiet window"). A reading that is not quiet, or whose identity fails, opens a new window and is not a stop | `/metrics` unreachable or not JSON, or a field missing or of the wrong type (a controller build without the thirteen fields `_mline` reads); no quiet window of `DRAIN_QUIET_S` (130 s) within `DRAIN_LIMIT_S` (900 s) |
| `metrics`, `twin`, `fetch` | one file each; `metrics` and `twin` write to `.tmp` and rename, so a failed request leaves no file | HTTP error, connection error, invalid JSON, `scp` failure (the first version used `curl -s` without `-f` and ignored all of these); `metrics` also when `<run-id>.metrics.<label>.json` **exists** — it is write-once like the twin snapshots (the second version truncated it with `>` before the write-once `snap` refused, destroying the earlier run's reading) |
| `keep <src> <dst>` | write-once copy | source missing or empty; destination exists |
| `snap_pair <run-id> <label> [snap args]` | `metrics <label>` then `$REC snap --label <label>`: both or neither | either fails; if only the twin snapshot fails, the `/metrics` reading just taken is renamed `...unpaired-<time>` (kept, never deleted) |
| `accounted <run-id>` | reconciliation **by identity** for one run: every record of `sent_events.jsonl` must have a record with the same `message_id`, this run id and one of the four outcomes in the fetched `events.jsonl`; prints the `OUTCOME RECONCILIATION` lines and names every record without one (Section 7). The movement of the five counters is printed as a secondary consistency figure and decides nothing | a published record has no logged outcome, or cannot be reconciled by identity (no usable or no unique `message_id`); `queue_depth` not 0; `/metrics` unreachable; an input file missing or malformed; `<run-id>.unaccounted.txt` not writable. `ACCEPT_UNACCOUNTED=1` continues, records `<run-id>.unaccounted.txt` and makes `finish` **and the 6.4 line** end non-zero |
| `pre <run-id> <seed> [types]` | run-id freshness first (run directory, `metrics.before`, `twins.before`, `marker` must not exist), then `wait_ready && drained && snap_pair before` | the run id was already used (nothing is read or written, no 130 s wait), or any of the three fails — the simulator must then not be started |
| `post <run-id>` | `mark` first, then `finish` | `mark` fails (nothing else is attempted: no marker, no protocol check) |
| `finish <run-id>` | `wait && drained && fetch && accounted && snap_pair after`, then `check` **and** `delta` (both always run) | any capture step fails, `check` exits non-zero (3 = not a protocol check) or `delta` exits non-zero (4 = `MISMATCH` or queue not empty), or published records without a logged outcome were accepted by the operator; repeatable after the cause is fixed — an existing `after` pair is kept, never retaken; a lone `after` file is a `STOP` |
| `sim_post <run-id> <sim args>` | simulator (stderr teed to `<run-id>.stderr.txt`), then `post` immediately **whatever the simulator's exit status**, then one `TEST STATUS` line | the transcript file cannot be created (the simulator is then **not** started); simulator exit ≠ 0, `tee` exit ≠ 0, an empty transcript or `post` ≠ 0 — the marker and the evidence are still collected |
| `run_test <run-id> <seed> [sim args]` | `pre`, and only then `sim_post` with the same seed (and `DEVICES`, if set) | `pre` fails: `TEST STATUS <id>: precondition failed -> simulator NOT started` |
| `harness_run <plan-run-id> [args]` | one `egw_experiments run` against the pilot plan, with the six expected services and the fetch of the collector's CSV and companions (Section 7, test 1) | the harness exits non-zero, which includes an invalid run: a collector hook that exits non-zero, a missing companion or an expected service without rows makes the run invalid |

`TEST STATUS ... PROCEDURE COMPLETE` means only that every step ran and that `check` and `delta` exited 0. It is **not** the verdict of a test: `check` exits 0 also when `lost > 0` (it reports, it does not judge — `itest_reconcile.py`, `cmd_check`), so the acceptance of each test remains its **Expected** list, read from the printed values. No helper relaxes or replaces an acceptance criterion.

### 6.2 One smartwatch at 1 Hz for 60 s

```bash
host$ RUN=itest-flow-01
host$ if pre $RUN 42 smartwatch && : > $P/$RUN.stderr.txt; then $SIM --scenario smoke --seed 42 --devices smartwatch --rate 1.0 --duration 60 --run-id $RUN 2>&1 | tee $P/$RUN.stderr.txt; ST=("${PIPESTATUS[@]}"); $REC mark $P/$RUN; MARK_RC=$?; echo "FLOW STATUS $RUN: simulator exit=${ST[0]} transcript (tee) exit=${ST[1]} mark exit=$MARK_RC (all three must be 0)"; [ "${ST[0]}" = 0 ] && [ "${ST[1]}" = 0 ] && [ -s $P/$RUN.stderr.txt ] && [ "$MARK_RC" = 0 ] || stop "6.2: simulator, transcript or marker failed - 6.3/6.4 can then not be read as a protocol check"; else echo "STOP: precondition failed, or $P/$RUN.stderr.txt cannot be written - the simulator was NOT started"; fi
```

`pre` (6.1) first refuses a run id that was already used, then waits for `/ready` = 200, then for `drained`, then writes `$P/$RUN.metrics.before.json` and the `before` twin snapshot (which identifies the device and records whether its twin already exists); the simulator starts only if all of them succeeded. `$SIM` is the fixed part of the simulator command line (`--broker 127.0.0.1 --port $MQTT_PORT --username egw-simulator --password ... --ca-cert ~/egw-tcg/ca.crt --egw-id egw-01 --output $P --qos 1`, defined in the helper file). This section keeps `mark`, `wait`, the snapshots, `check` and `delta` as separate steps because it explains them; Section 7 runs the same sequence through `run_test`. `ST=("${PIPESTATUS[@]}")` copies **both** statuses of the pipe at once (the next command would overwrite `PIPESTATUS`): `${ST[0]}` is the simulator's own exit status, which the `tee` would otherwise hide, and `${ST[1]}` is the status of `tee`, i.e. of the transcript. The transcript is evidence: if it cannot be created the simulator is not started (`: > ...` in the guard), and a `tee` that fails later, or an empty transcript, fails the line.

With `--devices smartwatch` the 1:0.2:10 split is renormalised over the selected type, so `--rate 1.0` is exactly 1 Hz (simulator README). The `--port` is the forwarded host port (2222/8883 or the re-mapped values). Expected stderr: `tls=True qos=1 ... devices=smartwatch` and finally `done sent=60 intended_invalid=0 buffered_dropout=0 dropout_disconnects=0` (±1 at the boundary). Exit code 0. TLS verification stays on (paho `tls_set(ca_certs=...)`, no insecure flag in `publisher.py`, verified).

`$REC mark` must be the very next command after the simulator, on the same line (only the array assignment `ST=(...)`, a shell builtin, stands between them), and it runs **whether or not the simulator succeeded** — a failed run still needs its marker and its evidence; the failure is carried by `simulator exit=` in the status line. It reads the controller's `monotonic_ns` from `GET /metrics` with the harness's own `poll_controller_marker` (`run.py`) and fixes the confirmation deadline at marker + `CONFIRMATION_WINDOW_S` (60 s, `protocol.py` line 58) **on the controller clock**, the same arithmetic as `egw_experiments run` (`run.py`, `confirmation_deadline_monotonic_ns`, clock domain `"controller"`). The marker file `$P/$RUN.marker.json` is write-once (a second poll would move the deadline later). `mark` prints the lag between the simulator's `finished_utc` and the poll; above 2 s (`CONTROLLER_MARKER_LAG_TOLERANCE_S`) the effective window was longer than the protocol's and the result must be reported with that lag. The `before` snapshot shows `exists: false` on the first use of seed 42 on this MongoDB volume and the accumulated state on any repetition; both are valid starting points for the checks below. Both `/metrics` and the twin snapshot go through the tunnels of 5.7.

### 6.3 Controller and Ditto through the tunnel

```bash
host$ { [ -f $P/$RUN.window-closed.json ] || $REC wait $P/$RUN; } && drained && fetch $RUN && accounted $RUN && snap_pair $RUN after || stop "6.3: the 'after' state was NOT captured - do not run 6.4 on it"
host$ python3 -m json.tool $P/$RUN.metrics.after.json
host$ UUID=$(python3 -c "import json;print(json.loads(open('$HOME/egw-tcg/itest/$RUN/sent_events.jsonl').readline())['device_uuid'])")
host$ twin $RUN $UUID && python3 -m json.tool $P/$RUN.twin.$UUID.json || stop "6.3: the twin of '$UUID' was NOT saved (empty UUID, GET failed, or the file could not be written)"
```

`$REC wait` returns when the **controller** clock has passed marker + 60 s (it replaces a host-side sleep). The closed window says nothing about work still queued or in progress — under TCG a backlog can outlive it — so the `after` snapshots are taken only once the quiet window of `drained` has passed (a temporary precaution, not proof) **and** `accounted` has found, identity by identity, a logged outcome in the fetched event log for every published record of this run, or the operator has accepted the named records with `ACCEPT_UNACCOUNTED=1`, which 6.4 then reports with a `STOP` (Section 7, "Reconciliation by identity"; `fetch` therefore moved from 6.4 to this line, and the `[ -f ...window-closed.json ] ||` lets the line be repeated after a `STOP` without a second, refused, `wait`). `snap_pair` writes `$P/$RUN.metrics.after.json` and the `after` twin snapshot together, both write-once. The last line saves the twin with the `twin` helper (`$P/$RUN.twin.<uuid>.json`, written through a temporary file, through `$DITTO`) and only then prints it. The confirmation deadline is unaffected, because `check` judges every record against the marker deadline, not against the time of the snapshot.

Expected twin (CONTRACTS §4): `thingId org.c2dta:<uuid>`, attributes `device_type: smartwatch`, `egw_id: egw-01`, `schema_version`; features `vitals` (heart_rate_bpm), `location` (lat, lon), `ingestion` with `last_run_id: itest-flow-01` and `last_seq` = the highest accepted `seq` of this run (59 when 60 events were sent and accepted). `accepted_count` is **cumulative over the life of the twin** (it survives runs, controller restarts and guest reboots; only deleting the thing or the `mongodb-data` volume resets it), so its absolute value is 60 only when the `before` snapshot shows `exists: false`; the acceptance is the before/after difference computed in 6.4. The `/metrics` counters are per controller **process** (zero again after every controller restart) and global over all run ids, so they too are read as a before/after difference, valid only while `started_at` is the same in both snapshots.

### 6.4 Reconcile sent, processed, confirmed — protocol rule, controller clock

```bash
host$ if [ -s $P/$RUN.metrics.after.json ] && [ -s $P/$RUN.twins.after.json ] && [ -s $P/$RUN/events.jsonl ]; then $REC check $P/$RUN; C=$?; $REC delta $P/$RUN; D=$?; U=no; [ ! -e $P/$RUN.unaccounted.txt ] || U=yes; echo "FLOW STATUS $RUN: check exit=$C delta exit=$D unaccounted.txt present=$U (both exits must be 0 and the file absent; then compare the printed values with the acceptance below)"; [ "$C" = 0 ] && [ "$D" = 0 ] && [ "$U" = no ] || stop "6.4: check or delta exited non-zero, or published records without a logged outcome were accepted by the operator in 6.3 ($RUN.unaccounted.txt) - report as measured, not as complete"; else echo "STOP: 6.3 did not complete (no 'after' pair or no fetched events.jsonl) - check and delta were NOT run"; fi
```

The guard requires what only a completed 6.3 leaves behind (the `after` pair and the fetched `events.jsonl`). `check` refuses a log fetched before the window closed. `check` is the harness accounting (`egw_experiments.analyze.compute_run_metrics`) with the marker deadline; `delta` is the per-device twin delta and the per-process `/metrics` delta against `events.jsonl`. Both always run, and both exit codes are shown on one line, together with the presence of `$RUN.unaccounted.txt`: 6.3 calls `accounted` directly, not `finish`, so this line is where an `ACCEPT_UNACCOUNTED=1` decision made in 6.3 ends the flow non-zero.

`check` does not re-implement the rule: it places copies of `sent_events.jsonl` and `events.jsonl` and a manifest carrying `confirmation_deadline_monotonic_ns` (marker + `CONFIRMATION_WINDOW_S`) with `confirmation_deadline_clock_domain: "controller"` in `$P/$RUN.reconcile/` (labelled `itest-adhoc-reconcile (NOT a harness run)`) and calls the harness's unmodified `compute_run_metrics`. A message is delivered only if an `accepted` record for its `message_id` has `ditto_ack_monotonic_ns` ≤ the deadline; a later confirmation leaves the message **lost** and is reported separately under `late_confirmations` (`analyze.py`: `ack > deadline_ns`); `duplicate` outcomes and repeated `accepted` records (`double_accepted`) never add deliveries. Waiting longer before the fetch therefore changes nothing: the wait only ensures that every in-window confirmation is already in the file. The result is printed and saved as `$P/$RUN.reconcile.json`. Because an ad-hoc run directory carries no seal, `check` also puts in `warnings` what the accounting cannot see: records of either file carrying another `run_id` than the simulator manifest, a `sent_events.jsonl` shorter than the manifest's `totals.sent`, a manifest whose `completed` is not `true`, and a controller clock that decreases along `events.jsonl` (a guest reboot: the marker deadline is not a protocol check for the records after it). The row carries `sim_completed` and `sim_totals`; the exit status is unchanged — `check` reports, the operator judges.

Acceptance (protocol compliance, plan §7.3 / CONTRACTS §9): `confirmation_deadline_source = controller-marker`; `lost = 0`; `delivered_unique = sent_valid`; `late_confirmations = 0`; `double_accepted = 0`; `intended_invalid_accepted = 0`; `marker_lag_s` ≤ 2 s (otherwise state the lag next to the result). `late_confirmations > 0` with `lost > 0` is a finding about the emulated guest's speed and is reported as measured; it is never turned into a pass by waiting longer. Latency is printed only with the emulated label.

Acceptance (counters): every `delta` line ends in `OK` — per device, Δ`accepted_count` between the `before` and `after` snapshots equals the number of `accepted` records of that device in `events.jsonl` (all of them, late ones included, because the controller increments the counter once per accepted outcome), `last_run_id` is this run and `last_seq` its highest accepted `seq`; per controller process, the `/metrics` deltas of `accepted`, `rejected`, `duplicate` and `failed` equal the outcome counts of `events.jsonl`, and `dropped` did not move. With `drained` in front of the `after` snapshots (6.3) a `queue_depth` other than 0 there should no longer occur; `delta` still checks it and exits 4 if it does, in which case wait for `drained` again, fetch again and take new snapshots under another label (`--to`). `delta` exits 4 as well when a device with accepted records in `events.jsonl` is **absent** from the `from` snapshot — a snapshot taken with another seed or another `--devices` than the run, which would otherwise close over the wrong twins and report `OK` for a device that never published — and it refuses (exit 1) a snapshot that holds no device and a `/metrics` reading without an integer `queue_depth`. When only one of the two `/metrics` readings exists it prints `/metrics: NOT compared (<path> missing)` instead of passing over it in silence, and still checks the queue of the reading it has.

If `mark` could not read the marker (controller unreachable at the end of the run), this step can only be labelled an **eventual-delivery check, not protocol compliance**: `check` then falls back to the harness's legacy event-derived deadline, prints `NOT a protocol check` and exits 3 (`wait` has no marker to wait for in that case; a plain `sleep 65` before the fetch is then only a fetch delay and proves nothing about the 60 s window). Prefer repeating the run under a new run id.

### 6.5 Restart the services and verify twin persistence

```bash
host$ started_at() { curl -fsS --max-time 30 $CTRL/metrics | python3 -c 'import json,sys; print(json.load(sys.stdin)["started_at"])'; }
host$ R65=stop; S0=$(started_at) && [ -n "$S0" ] && ssh egw-tcg 'cd /opt/egw/deployment && docker compose --env-file .env --env-file images.lock.env down && docker compose --env-file .env --env-file images.lock.env up -d' && R65=ok || stop "6.5: started_at was not read before the restart, or down/up ended non-zero - the restart is NOT shown"
host$ [ "$R65" = ok ] && wait_ready 3600 && S1=$(started_at) && [ -n "$S1" ] && [ "$S1" != "$S0" ] && echo "RESTART SHOWN: controller started_at $S0 -> $S1" && $REC snap --prefix $P/$RUN --label post-restart --like after && $REC same --prefix $P/$RUN after post-restart || stop "6.5: persistence across a restart NOT verified (restart not shown: R65='$R65' or started_at unchanged; stack not ready; snapshot failed; or 'same' reported DIFFERENT)"
host$ curl -s http://127.0.0.1:8000/metrics | python3 -m json.tool      # new started_at, all counters 0: /metrics is per process and is not persisted
```

The restart must be **shown**, not assumed: the second line keeps the status of `down && up -d` in `R65`, and the third line takes the snapshot only when `R65` is `ok` **and** the controller's `started_at` differs from the value read before the restart (stamped once, when the application is built: `metrics.py` line 55, `app.py` line 129; a new value shows a new controller process, not by itself that the other five containers were recreated — that rests on the exit status of `down && up -d`). `wait_ready 3600` polls `/ready` through the tunnel until it answers 200 (re-open the tunnel with `tunnel_down && tunnel_up` (5.7) if the ssh session dropped; one hour is an upper bound for the JVM start-up under TCG, `UNVERIFIED:` Appendix B item 9), and the snapshot is taken only then. `down` (without `-v`) keeps `mongodb-data` and `mosquitto-data`; `same` must report every device `identical` (the whole `ingestion` feature, `accepted_count` included, lives in the twin). A `down -v` is the destructive reset reserved for cold-start repetitions and is limited to those two named volumes (work order item 8: destructive resets only on identified test volumes); it is also the only operation in this runbook that returns `accepted_count` to zero.

### 6.6 Save the evidence

```bash
host$ EV6=stop; EVR=~/egw-tcg/evidence/flow-01-$(date -u +%Y%m%dT%H%M%SZ) && mkdir -p $EVR/guest && EV6=ok || stop "6.6: the evidence directory was NOT created"
host$ [ "$EV6" = ok ] && cp ~/yocto/logs/$BOOT.log $EVR/ || { EV6=stop; stop "6.6: boot log NOT copied (or an earlier 6.6 line stopped) - the evidence directory is INCOMPLETE"; }                                  # console + runqemu command line
host$ [ "$EV6" = ok ] && cp ~/egw-tcg/evidence/build-*/SHA256SUMS.artefacts ~/egw-tcg/evidence/build-*/qemu_version.txt ~/egw-tcg/evidence/build-*/source_commit.txt $EVR/ || { EV6=stop; stop "6.6: build identity NOT copied (or an earlier 6.6 line stopped)"; }     # source_commit.txt is the commit of the YOCTO IMAGE build (2.5), not of the deployment tree
host$ [ "$EV6" = ok ] && cp -r $P/$RUN $P/$RUN.* $EVR/ || { EV6=stop; stop "6.6: run artefacts NOT copied completely (or an earlier 6.6 line stopped)"; }        # run directory plus its siblings: stderr, marker, window-closed, metrics/twins snapshots, twin.<uuid>.json, reconcile.json, reconcile/
host$ [ "$EV6" = ok ] && cp ~/egw-tcg/sut_environment.json ~/egw-tcg/itest-helpers.sh ~/egw-tcg/tunnel.sh ~/egw-tcg/deploy_source_commit.txt ~/egw-images/egw-controller-0.1.0-arm64.identity.txt ~/egw-images/imagetools-*.txt $EVR/ || { EV6=stop; stop "6.6: environment/identity files NOT copied (or an earlier 6.6 line stopped)"; }     # the two helper files hold no secret (5.7, 6.1); deploy_source_commit.txt is the commit of the deployment tree and the harness (4.3)
host$ [ "$EV6" = ok ] && ssh egw-tcg 'mkdir -p /opt/egw/evidence && cd /opt/egw/deployment && docker compose --env-file .env --env-file images.lock.env ps > /opt/egw/evidence/compose-ps.txt && docker compose --env-file .env --env-file images.lock.env logs --no-color > /opt/egw/evidence/compose-logs.txt && docker info > /opt/egw/evidence/docker-info.txt && docker compose version > /opt/egw/evidence/compose-version.txt && docker image inspect --format "{{.RepoTags}} {{.RepoDigests}} {{.Id}} {{.Architecture}}" $(docker images -q | sort -u) > /opt/egw/evidence/image-identities.txt && cp .env.example images.lock.env mosquitto/config/certs/ca.crt /opt/egw/evidence/' || { EV6=stop; stop "6.6: the guest-side capture ended non-zero at its first failing command (or an earlier 6.6 line stopped) - /opt/egw/evidence is INCOMPLETE"; }
host$ [ "$EV6" = ok ] && scp -r egw-tcg:/opt/egw/evidence/ $EVR/guest/ || { EV6=stop; stop "6.6: guest evidence NOT fetched (or an earlier 6.6 line stopped)"; }
host$ [ "$EV6" = ok ] && (cd $EVR && find . -type f ! -name SHA256SUMS -exec sha256sum {} + > SHA256SUMS) && echo "EVIDENCE SAVED: $EVR" || stop "6.6: SHA256SUMS NOT written, or an earlier 6.6 line stopped - $EVR is INCOMPLETE and must not be sealed"
```

Every line of this block is bound to the previous ones through `EV6` (conventions, "Guards stop what they guard"): a copy, a guest-side redirect or the `scp` that fails prints `STOP:` and the checksum line then refuses, so a `SHA256SUMS` is never written over an incomplete directory. The guest-side commands are chained with `&&` (`images.lock.env` exists on any guest that ran Section 5, since every compose command there names it). `UNVERIFIED:` never executed on the real host or guest (Appendix B item 20).

Never copy `.env`, `mosquitto/config/passwd`, `ca.key`, `server.key` or `~/.ssh/egw_campaign*` into `$EVR`. Write `$EVR/README.md` with the Section 0 label, the runqemu command line, the image identities and the reconciliation numbers. This directory, not the G1 capsule, is where the integrated evidence accumulates; when sealed it goes under `docs/evidence/<new-name>/` in the deployment/test PR, never inside `docs/evidence/g1-yocto-qemu/`.

---

## 7. The nine integration tests (work order item 8)

Principles: real stack, existing simulator and harness only (no fakes); run ids prefixed `itest-` so they can never be confused with `campaign_plan.json` run ids; every test produces a directory under `~/egw-tcg/itest/` plus the fetched `events.jsonl`, twin-ingestion and `/metrics` snapshots before and after, the controller marker and the `reconcile.json` produced by the harness accounting; destructive actions are limited to `docker compose stop/restart/down` and to the two named volumes; the emulated label applies to every artefact. Shell preamble (host, in the venv): the helper file of 6.1, sourced after the `.env` line.

```bash
host$ set -a; . ~/egw-tcg/.env; set +a; . ~/egw-tcg/itest-helpers.sh && type run_test >/dev/null && echo "helpers loaded"
```

**Shape of every ad-hoc test.** One call: `run_test <run-id> <seed> [simulator arguments]`. It runs `pre <run-id> <seed>`; **only if `pre` returned 0** it starts the simulator (`$SIM --seed <seed> ... --run-id <run-id>`, stderr teed to `<run-id>.stderr.txt`) and, as the very next command, `post <run-id>`, so that the marker is read at the end of the run; it ends with one `TEST STATUS` line and a non-zero status if anything failed. The earlier form `pre ...; $SIM ...; post ...` is not used any more: with `;` a failed `pre` (controller not drained, `before` snapshot refused because the run id was already used, tunnel down) did not prevent the simulator from publishing. Three rules are built into the helpers (table in 6.1):

1. A failed precondition publishes nothing: `pre` fails → `TEST STATUS <id>: precondition failed -> simulator NOT started`. In a loop, `run_test ... || { stop "..."; break; }` ends the loop.
2. `post` runs immediately after the simulator **even when the simulator exits non-zero** — the marker and the evidence of a failed run are still needed — but the status is then non-zero and the line reads `TEST STATUS <id>: simulator exit=<n> transcript (tee) exit=<t> post=<m> -> FAILED`. The transcript is evidence: a `tee` that exits non-zero or an empty `<run-id>.stderr.txt` fails the run in the same way, and a transcript file that cannot be created stops `sim_post` before the simulator is started.
3. Inside `post`: if `mark` fails, nothing else is attempted (that run can only be described as an eventual-delivery observation, not as protocol compliance); `wait`, `drained`, `fetch`, `accounted` and the `after` snapshots are chained with `&&`; `check` and `delta` both always run and either non-zero exit makes `post` non-zero. After a `STOP` in the capture chain, `finish <run-id>` repeats it without touching the write-once marker.
4. A `STOP` also binds the **following lines of the same test**. `stop` can only print and return non-zero; it cannot prevent the next pasted line from running. Every test whose block continues after `run_test` therefore stores the status (`run_test ...; RT=$?`, or `T4`/`REPLAYED`, `T6`, `T7` set to a token only on success), and each later line starts with a test of that variable. This matters most where a later line publishes again (the replay of test 4) or consumes a write-once label (`replay`, `after`); for the read-only evaluation lines it prevents the files of an **earlier** execution of the same run id from being read as the result of a run that never started. After `TEST STATUS ... FAILED` (as opposed to `precondition failed`) the artefacts do belong to this run and may be inspected by hand for the diagnosis; they are not an evaluation.
5. Nothing a helper writes is overwritten: twin snapshots, marker and window file (`save_new` in `itest_reconcile.py`), and now also `<run-id>.metrics.<label>.json` (`metrics`) and the pre-/post-replay copies of test 4 (`keep`). `pre` checks the freshness of the run id **before** anything else, so a reused run id costs no 130 s wait and changes no file. Only derived files are rewritten: `<run-id>.reconcile.json` and `<run-id>.reconcile/` by every `check`, `events.jsonl` by every `fetch`.

`TEST STATUS ... PROCEDURE COMPLETE` is not a verdict (6.1): the acceptance of each test is its **Expected** list. `post` applies the confirmation deadline on the controller clock through the harness's own accounting (6.4) and compares counters only as before/after differences: the twins' `accepted_count` is cumulative per device over the life of the twin, the simulator derives the device identities from the seed alone (one device per type, `egw_simulator/devices.py`; there is no device-id option), and several tests share seed 42, so an absolute `accepted_count` never describes a single run. The `before` snapshot records `exists: true|false` per device, so freshness is documented rather than assumed. `run_test` passes the seed once to both the `before` snapshot and the simulator, so the two can no longer disagree.

**The 130 s quiet window (`drained`): a temporary precaution, not proof that processing has finished.** The project review of 2026-09-18 allows the wait to stay as a precaution and rejects it as evidence that processing is complete; its length and mechanics are unchanged, only what is claimed for it. Both `pre` (before the `before` snapshots) and `finish` (before the fetch and the `after` snapshots) call `drained`. Without it, a backlog of the previous run that outlives its 60 s window under TCG would be logged to the previous run's `events.jsonl` but counted in this run's Δ`accepted_count` and `/metrics` differences: a false `MISMATCH` (never a false `OK`), since `delta` itself checks `queue_depth` only in the `to` snapshot. What `GET /metrics` offers for this, as the controller serves it with the progress counters of ADR 0010 and the three session fields of ADR 0011 (CONTRACTS §5; the controller sources were first read on 2026-09-18, nothing was run):

- **`received`, `in_progress` and `processing_errors` are exposed, and the accounting identity is evaluated on every reading.** `/metrics` is `MetricsCounters.snapshot()` plus `queue_depth` (`app.py`) and, with ADR 0011, the bridge's `mqtt_subscribed`, `mqtt_connection` and `unacked`, all taken in one step of the event loop, so one response is one snapshot (CONTRACTS §5, "Progress counters in `GET /metrics`"). `_mline` (6.1) refuses a response in which any of its thirteen fields is missing or of the wrong type — an absent field is never read as zero — and evaluates `received == accepted + rejected + duplicate + failed + dropped + processing_errors + in_progress + queue_depth` from that same response; a failed identity means "do not trust this reading", so that reading is never quiet and opens a new window, and it is not a `STOP`. `unacked` is not a term of the identity: it is counted by the bridge at `on_message`, on the MQTT network thread, and covers what `received` cannot see — the hand-over to the event loop and a delivery discarded for want of a running loop. `mqtt_subscribed`, `mqtt_connection` and `unacked` cover the session: a reading is quiet only on a subscribed connection with nothing handed to the client and not yet acknowledged, and a change of `mqtt_connection` inside the window opens a new one. (For one ad-hoc run the host still knows what it published; that is what `accounted` uses, below.)
- **`queue_depth` excludes the message being processed.** It is `asyncio.Queue.qsize()` (`service.py`). The single consumer removes a message with `await self._queue.get()` and only then awaits `process()` (one pipeline task), so during a Ditto request `queue_depth` can be 0 while one message is in progress — which the reading shows as `in_progress` 1, and a reading with `in_progress` above 0 is never quiet. At most **one** message is in progress at any time.
- **A counter moves only when processing has ended.** Every return path of `process()` calls `_emit` exactly once, and `_emit` writes the event record and then increments the outcome counter as its last actions. Retries in progress are invisible: `attempts` appears only in the final event. `dropped` is incremented at enqueue time when the queue is full; under ADR 0011 such a delivery is not acknowledged and `dropped` means "left for redelivery at the next session resumption".
- **A message that ends without an outcome counter is counted, not lost from view.** Processing that ends without any outcome counter having moved is counted in `processing_errors` (CONTRACTS §5), so the identity still holds for it; under ADR 0011 such a delivery is not acknowledged, `unacked` stays above 0 while its connection lasts, and the controller ends that connection so that the broker resends it. A delivery discarded before the bridge has its loop is counted in `unacked` and ends the connection the same way. The identity of such a message is still not in `/metrics`: after a run, `accounted` names its record.
- **Two equal readings 5 s apart prove nothing on their own.** A Ditto request that was taken from the queue before the first reading and is still waiting (slow Ditto under TCG, a timeout, a retry back-off) leaves `queue_depth` 0 and all counters unchanged on both readings — the defect of the first version of this helper. The reading shows that message as `in_progress` 1, which is why a quiet reading requires `in_progress` 0; the window is kept all the same (below).

The invariant is evaluated on every reading, and the window is kept unchanged (ADR 0011, condition C5): `drained` stays a **temporary precaution** — a **quiet window longer than the nominal longest time one message can be in progress** — because one reading is one snapshot and cannot show a message still being handed over from the MQTT network thread to the event loop or one the broker holds and has not sent (CONTRACTS §5, "What the counters are not"), and because a broker with nothing in flight to a session that stays connected is assumed, not shown, to hold nothing queued for it (the residual assumption of ADR 0011, condition C5, stated there as ASSUMED). It lowers the chance that the snapshots are taken while a message is in progress; it does not show that none is. Nominally — assuming that one 10 s timeout phase dominates each attempt, see (b) below — one logical Ditto request is at most `EGW_RETRY_MAX` attempts of 10 s each (`DEFAULT_TIMEOUT_S`, `ditto.py` line 24; `from_settings` passes no other timeout, lines 170-187) plus the back-off sleeps `EGW_RETRY_BACKOFF_MS` × (2^(n−1)) between them (`ditto.py` lines 202-203 and 228-250): with the defaults 3 and 200 ms (`config.py` lines 75-76; `.env.example` lines 63-64) that is 3 × 10 + 0.2 + 0.4 = 30.6 s. One message issues at most four logical requests — first contact: `get_twin`, then policy `PUT` and thing `PUT` in `ensure_twin`, then the `PATCH` (`service.py` lines 269-271, 299 and 357-364; `ditto.py` lines 311-320) — hence at most 4 × 30.6 = **122.4 s**; any other message needs at most 30.6 s. `drained` therefore returns 0 only when **every** reading (one about every 5 s, some two dozen in all) over an unbroken window of `DRAIN_QUIET_S` = 130 s was quiet — `queue_depth`, `in_progress` and `unacked` 0, `mqtt_subscribed` true and the identity holding — and showed identical `started_at`, `mqtt_connection`, `received`, `accepted`, `rejected`, `duplicate`, `failed`, `dropped` and `processing_errors`; a reading that is not quiet, a reading whose identity fails, any movement of those nine fields, a new connection or a new `started_at` opens a new window; an unreachable or non-JSON `/metrics`, or a response with one of the thirteen fields missing or of the wrong type, is a `STOP`, never a reading; without a quiet window within `DRAIN_LIMIT_S` = 900 s it gives up with `STOP` (a sizing observation for Section 8) and the run must not be started. What the window is expected to catch (an expectation, not a proof): a message that was in progress at the first reading of the window ends — nominally — within 122.4 s, and it ends either in an outcome counter (the window is then broken and restarts) or without one (`processing_errors` moves and, under ADR 0011, `unacked` stays above 0 and the connection is ended: the window is broken either way; no record is written — after a run, `accounted` names that record, and `delta` shows a `MISMATCH`). If `EGW_RETRY_MAX` or `EGW_RETRY_BACKOFF_MS` is changed, recompute 4 × (R × 10 + B/1000 × (2^(R−1) − 1)) and export a larger `DRAIN_QUIET_S`; never a smaller one. Cost: at least 130 s before and after every ad-hoc run.

What the procedure still **cannot** see (`UNVERIFIED:`, Appendix B item 21): (a) a message delivered to the controller after the last reading of the window — it was in no reading's `queue_depth`, `in_progress` or `unacked`; this is excluded by the operator's rule that no simulator, harness run or probe is publishing while `drained` runs, together with the three session fields of every reading — `mqtt_subscribed` true (the controller is subscribed on the current connection), `mqtt_connection` unchanged across the window (the same connection throughout, so no redelivery of an earlier connection's unacknowledged deliveries began inside it) and `unacked` 0 (nothing handed to the client on this connection awaits its acknowledgement) — and with what ADR 0011 (condition C5) leaves ASSUMED: that a broker with nothing in flight to a session that stays connected holds nothing queued for it, the documented meaning of the broker's queue, not observed here; (b) **122.4 s is a nominal figure, not a bound.** `httpx.AsyncClient(timeout=10.0)` (`ditto.py` lines 165-167) sets the connect, write, read and pool timeouts to 10 s **each**, and the phases of one attempt are sequential: with no misbehaviour at all, an attempt that spends almost 10 s connecting and almost 10 s waiting for the response lasts about 20 s, and the per-phase sum is 40 s, i.e. 3 × 40 + 0.6 = 120.6 s per logical request and 4 × 120.6 = **482.4 s** for a first-contact message — above the default `DRAIN_QUIET_S`. On top of that the read timeout applies per read, so a response that trickles in can keep one attempt alive longer still. The default stays at 130 s because a window of 490 s before and after every ad-hoc run would add about 12 minutes to each of them, because the failure it guards against is conservative (a message of the previous run still in progress at the `before` snapshot produces a false `MISMATCH`, never a false `OK`), and because `finish` no longer rests on the window alone (`accounted`, below); `export DRAIN_QUIET_S=490` covers the per-phase sum whenever a `MISMATCH` has to be excluded as a timing artefact; (c) work inside Ditto or MongoDB after Ditto's 2xx is outside the controller's view altogether (the twin snapshots read Ditto's own API, which is the state the tests assert). The instantaneous check the project review asked for is made on every reading (Section 9 item 7: ADR 0010's counters and ADR 0011's session fields, evaluated by `_mline`); the window stays as a precaution for the hand-over and for the assumption of (a), and **no helper states that nothing is pending**: in `pre` nothing can be reconciled, since what ran before is not known to this run; in `finish` the run's own records are reconciled by identity (`accounted`, below). `UNVERIFIED:` never executed against the real controller (stubbed `curl` only, Appendix B item 20).

**Reconciliation by identity in `finish`: `accounted`.** The first version of this helper compared totals — N published records against M, the movement of `accepted + rejected + duplicate + failed + dropped` since the `before` reading — and printed that every message had reached a terminal counter when M ≥ N. The project review of 2026-09-18 refuted it with two messages: A is accepted and then received again as a duplicate, B has no outcome; M = 2 = N, the helper returned 0, and B was missing. Totals cannot carry the decision, because one message can move the counters more than once (QoS 1 redelivery, a replay) and because the counters are global over all run ids. `accounted <run-id>` (6.1) therefore decides on **identities**: a record of `sent_events.jsonl` counts as finished only when the fetched `events.jsonl` of the run holds a record with the same `message_id`, this `run_id` and one of the four outcomes `accepted`, `rejected`, `duplicate`, `failed` (`events.py` line 32). What the sources say about the two files (read on 2026-09-18, nothing run):

- **Every published record carries `message_id`.** `SentEventsWriter.write` refuses a record without the exact field set (`output.py` lines 20-29 and 70-76) and the value is the envelope's (`runner.py` line 381). The intentionally invalid payloads are no exception: `InvalidInjector.mutate` touches measurement fields only (`scenarios.py` lines 211-231), so the controller reads `run_id` and `message_id` from them (`_extract_identity`, `service.py` lines 111-123 and 209) and writes the `rejected` record, with that id, into this run's file (`events.py` lines 75-82 and 112-119).
- **`accepted`, `rejected`, `duplicate` and `failed` each end in exactly one `_emit`**, which writes the record and then increments the counter (`service.py` lines 393-394). A `duplicate` record carries the id of the message it repeats (lines 282-293), which is why a second record for A says nothing about B.
- **Three endings leave no record:** a message dropped at a full queue (`dropped` counter only, `service.py` lines 156-159); a message whose processing raised into the `except Exception` branch of the consumer loop (logged to stderr, no event, no counter, lines 175-181 — for example an `OSError` from the event log); and a message that never reached the controller (`mqtt.py` lines 191-193, or the broker). All three are reported the same way: the record is **named** under `NO LOGGED OUTCOME` and the function ends non-zero.

A published record whose `message_id` is missing, empty or not unique within `sent_events.jsonl` cannot be reconciled by identity. With the simulator as read above no such class exists; if one appears it is printed under `NOT RECONCILABLE` and the function ends non-zero — never `OK`. Output: `OUTCOME RECONCILIATION <run-id>: published=N with_logged_outcome=K without_logged_outcome=U not_reconcilable=X queue_depth=Q`, then the counter movement labelled `secondary consistency figure, decides nothing` (or `not comparable` when `started_at` changed: the identity reconciliation itself needs no counters and stays evaluable across a controller restart, since the log is opened in append mode, `events.py` line 108), then up to 20 named records per class, then the result. Only `-> OK: every published record of this run has a logged outcome in the fetched event log`, or the operator's recorded `ACCEPT_UNACCOUNTED=1` decision (below), lets `finish` take the `after` snapshots. That sentence is the whole claim; with no published record read at all it is not printed (non-zero, `nothing was reconciled`). It says nothing about the **kind** or the **time** of an outcome — whether each valid record has an in-window `accepted` is judged by `$REC check` with the controller-clock deadline (6.4), which `accounted` neither repeats nor replaces — and it does **not** say that the controller has no other work pending, which is not observable today (Section 9 item 7). Limits: (i) the fetched log is a copy taken just before, so a record written after the `fetch` is not seen until `finish` is repeated; (ii) a record without a logged outcome may be transient (still queued or in progress) or permanent (the three endings above), and the log cannot tell which, so `accounted` reports and stops, it does not loop, and two readings that name the same records do not show that the absence is permanent (one message can nominally be in progress for 482.4 s, (b) above); (iii) `message_id` is a function of run id, device and `seq`, the guest log is opened in append mode (`events.py` line 108) and `pre` checks the freshness of a run id **on the host only**, so a run id used again after its host artefacts were removed (not a step of this runbook) finds the records of the earlier execution and is reported `OK`, whatever happened to the messages of the second one. Repeat `finish <run-id>` once later; if the same records are named again, `ACCEPT_UNACCOUNTED=1 finish <run-id>` captures the `after` state, records the decision in `<run-id>.unaccounted.txt` and **still ends non-zero**, as does the 6.4 line of the first flow, which calls `accounted` outside `finish` (`check` reports the valid ones among them as `lost`); if that file cannot be written, nothing is captured. `UNVERIFIED:` never executed against the real controller (stubs and hand-written logs only, Appendix B items 20 and 21).

**No test file in `src/tests/` carries the `integration` marker today** (verified: `pyproject.toml` defines the marker with `-m 'not integration'` in `addopts`, but `grep pytest.mark.integration src/tests` finds nothing). The tests below are therefore operator-driven with the simulator/harness; turning them into `@pytest.mark.integration` tests that read `EGW_*` from the environment is a candidate for the deployment/test PR, not a prerequisite.

### Test 1 — repeated smoke, complete artefacts

```bash
host$ for i in 01 02 03; do run_test itest-smoke-$i 42 --scenario smoke || { stop "test 1 interrupted at itest-smoke-$i - the remaining repetitions were NOT started"; break; }; done
```

The loop ends at the first repetition whose `run_test` returns non-zero (precondition, simulator, marker, capture, `check` or `delta`); repeat the missing repetitions under **new** run ids once the cause is understood (the artefacts of a run id are write-once).

Expected per run: exit 0, `lost = 0`, `late_confirmations = 0`, `delivered_unique = sent_valid`, all three device types, `sent ≈ 336` (30 s x 11.2 msg/s), every `delta` line `OK` (the three runs share seed 42, so the second and third start from `exists: true` and a non-zero `accepted_count`). Note that 11.2 msg/s under TCG may already stress the guest; if `lost > 0` appears, this is the first sizing finding of the pilot (Section 8), not a reason to change the protocol.

Then one run through the **harness** to prove the artefact chain (events fetch, SUT environment, collector hooks) on this guest. The harness only accepts run ids from a plan, so generate a *pilot* plan in a separate directory (never `experiments/campaign_plan.json`):

```bash
host$ python -m egw_experiments plan --master-seed 42 --output ~/egw-tcg/pilot/campaign_plan.json
host$ python3 -c "import json;p=json.load(open('$HOME/egw-tcg/pilot/campaign_plan.json'));print([r['run_id'] for r in p['runs'] if r.get('condition_id')=='smoke_sequence'][:3])"   # plan entries carry condition_id (plan_gen.py _run_entry); expected ['smoke_sequence-r01', 'smoke_sequence-r02', 'smoke_sequence-r03']
host$ RID=smoke_sequence-r01        # run ids are deterministic: '{condition_id}-rNN' (plan_gen.py line 93), so the literal is safe
host$ wait_ready && drained && harness_run $RID || stop "test 1 (harness): not ready, not drained, or the harness exited non-zero"
```

`harness_run` (6.1) is the full `python -m egw_experiments run` command line: the pilot plan and `--base-dir ~/egw-tcg/pilot/results`, the broker/TLS arguments, `--controller-url`, `--sut-env-from ~/egw-tcg/sut_environment.json`, the `scp` fetch of `events.jsonl`, `--expect-services` with the six Compose container names and the three collector hooks (`sudo systemd-run --unit egw-resources-{run_id} ... collect-resources.sh ... --expect-services {expect_services}`, `sudo systemctl stop`, and `src/deployment/scripts/fetch-collector-output.sh`). The harness runs the start hook before the warm-up, the stop hook right after the measured run and **before** the 60 s confirmation window (`execute_run` in `src/egw_experiments/run.py`, the call `_run_collector_hook("stop", ...)`), and the fetch hook after that window.

The fetch hook runs `fetch-collector-output.sh` from the checkout named by `EGW_CLONE` (6.1); that checkout must contain the script, otherwise the hook exits non-zero and the run is invalid. It copies up to four files from the guest's `/tmp` into `results/raw/<run_id>/logs/collector/`: `resources-<run_id>.csv`, `resources-<run_id>.csv.diagnostics.log` and `resources-<run_id>.csv.lifecycle.csv`, which are mandatory, and `resources-<run_id>.csv.self-test` if the collector wrote one. For each file it asks the guest whether the file exists, copies it and compares the guest's `sha256sum` with the local one, and it prints one `fetch:` line per file (kept in `logs/collector/hook-fetch.stdout.txt`, next to the full output of the other two hooks). It exits 3 if a mandatory file is absent, 4 on a hash mismatch, 5 on an ssh or scp failure and 6 if a local file already exists. Guest `/tmp` is a tmpfs, so these files are lost when the guest powers off: the fetch hook is the only copy. Right after the fetch, and before anything is sealed, the harness records in the manifest (`collector`) each file's presence, size and sha256, the `collector_sha256` of the collector that ran (the diagnostics `start:` line), the collector's `inventory:` line, its closing `stop:` line and the number of rows of each expected service. The run is marked **invalid** when any collector hook exits non-zero, when a mandatory companion is missing, when a `.self-test` marker is present (the output is not a measurement), when the `start:` line is missing or declares a different set of services, when the inventory names a missing service or is absent (the collector did not stop cleanly), when the closing `stop:` line is absent, duplicated or carries no integer `samples=` count (2026-09-19: an incomplete closing record no longer passes), when the three records are not written in the collector's own file order — the `start:` record first, the `inventory:` record when the stop hook's SIGTERM ends it and the closing record last, only the records that are there being compared (2026-09-20: the whole chain is compared, and by the same function in both halves, so a diagnostics whose inventory comes before its start is no longer refused by the preflight check while being sealed here) — or when an expected service has no rows in the CSV. The closing record is read further (2026-09-20), by the same rule as `tools/session/collector_check.py` applies to the preflight's output — the two halves call one function, so a record one refuses is not a record the other seals, and where a kind of record occurs more than once both halves read the FIRST one, so the window the manifest carries and the window `analysis/collector/collector-check.json` carries for one set of bytes are one window (2026-09-20). Every figure the record carries (`utc_gap_seconds`, `withheld_samples`, `withheld_elapsed_s`, `withheld_runs_unmeasured`, `withheld_open_at_stop`) is recorded in the manifest, in the collector's own words, and the run is invalid: when one of them is absent or written as `unknown` (the collector could not read its own state file when it closed); when `withheld_runs_unmeasured` or `withheld_open_at_stop` is above zero (elapsed time in neither count, i.e. withheld samples no accepted sample has measured); when `withheld_elapsed_s` is above zero while `withheld_samples` reads zero (the record contradicts itself: that zero is what the closing `awk` writes when it cannot read the count); when any of the three records carries no strictly valid leading UTC timestamp `YYYY-MM-DDTHH:MM:SSZ`, so its bounds cannot be trusted; when the CSV has no `ts_utc` column, so its rows cannot be placed in the collector's window; when the reconciliation of the record with the CSV could not be made at all, which is reported as `closing_record_reconciliation: "not run: …"` and is a reason of its own (the reasons: bounds that are not two valid UTC timestamps, a stop that is not after the start (a reversed or empty window), instants that could not be read, no integer `samples=`, no integer `withheld_samples=`, or more rounds withheld than taken, which no readable record can state since `samples=` counts the withheld rounds too); and when the record contradicts itself in one of three ways — more stamped rounds (`samples` less `withheld_samples`) than the seconds of the collector's own window can hold (an accepted round stamps a second strictly after the last stamped one, so a window of N seconds holds at most N + 1 of them, and one second more is allowed for the closing record's own stamp); more distinct instants inside that window than those stamped rounds (a round stamps at most one instant and a withheld round none at all); or not one instant inside it while the record accounts for more than the single priming round (a record accounting for exactly one stamped round is exempt: that round is the priming one, which writes no row at all, so a CSV with no instant inside the window is then what the collector is expected to have left). What is recorded and reported WITHOUT invalidating anything: a forward `utc_gap_seconds`, which the collector documents as costing no unsampled time (a wall clock stepped forward adds to it); `withheld_samples`, the pacing artefact it recalibrates after; more rounds than the interval the `start:` line declares implies over that window (`rounds_the_declared_interval_implies`, since a collector may pace otherwise than it declared, which the rule on the stamped seconds above does not punish); rounds that wrote no row at all, i.e. fewer instants than stamped rounds, one of which is always the priming round (the two capsules of 2026-09-19: the 45 s preflight closed with `samples=46` and carries 45 instants, `nominal-r01` with `samples=721` and 720); a rate below the declared interval; and a window shorter than the declared `duration=` (the stop hook ends the collector after the measured run: `nominal-r01` declared 840 s and closed a 722 s window), whose size is the manifest's `declared_duration_shortfall_s` — the same field at the top level of `analysis/collector/collector-check.json` in the preflight, where the collector's own window is the only window the coverage is judged over, so a collection that ended early is validated against itself and the figure is there for the driver, which knows what duration it asked for. The authority on the spacing and the coverage of the evidence stays the ingest validation below, on the real instants of the CSV. Rows of a service outside the list only give a warning. These reasons do not withhold `SHA256SUMS`: the fetched files are sealed as they arrived, so the reasons stay verifiable. The CSV then goes through the unchanged ingest validation (30 instants, 90 % coverage, 5 s gaps). A condition without a warm-up, such as `smoke_sequence`, therefore gives the collector almost no lead before the measured window, and its first (priming) sample falls inside it: in `smoke_sequence-r02` (2026-09-19) the first row came 1.4 s after the window opened. *(Added on 2026-09-19: other descriptions of these hooks say that the collector is stopped after the confirmation window; the code stops it before.)*

Expected: `manifest.json` with `validity: "valid"`, `SHA256SUMS` written, `resources.csv` with the `host` column equal to the guest hostname (the harness rejects it otherwise — `collect-resources.sh` header), `controller_metrics.csv`, `sut_environment.json` copied in, and in `logs/collector/` the CSV with its two companions and a `hook-<hook>.stdout.txt` and `hook-<hook>.stderr.txt` for each of the three hooks, all listed in `SHA256SUMS`; in the manifest, `collector.problems` empty, `collector.inventory` containing `missing=none` (the line ends in `unnamed_ids=N`), `collector.fetch_helper_sha256` equal to the `sha256sum` of `$EGW_CLONE/src/deployment/scripts/fetch-collector-output.sh`, and every `collector.rows_per_expected_service` value above 0. `sudo systemd-run` is used because the collector must outlive the SSH session and stop cleanly on `systemctl stop`; `egw` has NOPASSWD sudo (assumption A13). A 30 s smoke satisfies the collector's minimum of 30 distinct instants only just; if the run is marked invalid for coverage, repeat with `--run-id` of a nominal entry and `--duration` untouched (the plan fixes durations). The harness applies the confirmation deadline itself (manifest `confirmation_deadline_clock_domain: "controller"`), so no `pre`/`post` is used here; read the result with `python -m egw_experiments analyze --base-dir ~/egw-tcg/pilot/results --plan ~/egw-tcg/pilot/campaign_plan.json` and the columns `confirmation_deadline_source`, `sent_valid`, `delivered_unique`, `lost`, `late_confirmations`, `double_accepted` of `~/egw-tcg/pilot/results/processed/per_run.csv` (acceptance rows of conditions that were not run are expected to fail on completeness in a pilot tree).

### Test 2 — three wearables, valid events and correct twin properties

```bash
host$ R=itest-3dev-01; run_test $R 7 --scenario smoke --duration 60; RT=$?
host$ if [ "$RT" = 0 ]; then for U in $(python3 -c "import json;print(' '.join(sorted({json.loads(l)['device_uuid'] for l in open('$HOME/egw-tcg/itest/$R/sent_events.jsonl')})))"); do twin $R $U || { RT=twin; break; }; done; else stop "test 2: run_test did not complete (RT='$RT') - the twins were NOT read"; fi     # a twin that could not be saved sets RT=twin, so the evaluation line below refuses instead of judging two twins out of three
host$ [ "$RT" = 0 ] && python3 - ~/egw-tcg/itest/$R.twin.*.json <<'EOF' || stop "test 2: not evaluated (RT='$RT') or the evaluation script failed"
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
host$ R=itest-invalid-01; run_test $R 42 --scenario invalid-payload --duration 120; RT=$?
host$ [ "$RT" = 0 ] && python3 - ~/egw-tcg/itest/$R <<'EOF' || stop "test 3: not evaluated (RT='$RT') or the evaluation script failed"
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
host$ R=itest-dup-01; T4=stop; REPLAYED=stop; run_test $R 42 --scenario smoke --duration 60 && keep $P/$R.reconcile.json $P/$R.reconcile.pre-replay.json && keep $P/$R/events.jsonl $P/$R.events.pre-replay.jsonl && T4=ok || stop "test 4: the first run did not complete, or its pre-replay copies were not saved - do NOT replay (T4=$T4)"   # the copies keep the pre-replay accounting: the second fetch and the second check below overwrite both originals
host$ replay() { python -m egw_simulator run --scenario smoke --seed 42 --duration 60 --run-id $R --output ~/egw-tcg/itest-replay --broker 127.0.0.1 --port $MQTT_PORT --username egw-simulator --password "$MOSQUITTO_SIMULATOR_PASSWORD" --ca-cert ~/egw-tcg/ca.crt --egw-id egw-01 --qos 1; }
host$ if [ "$T4" = ok ] && wait_ready && drained; then T4=replayed; replay; RC=$?; echo "replay simulator exit=$RC (must be 0)"; [ "$RC" = 0 ] && REPLAYED=ok || stop "test 4: the replay simulator failed - do not evaluate; repeat the whole test under a new run id"; else stop "test 4: T4='$T4' is not 'ok' (the first line of this test did not complete, or the replay was already published once), or the controller is not ready and drained - the replay was NOT published"; fi
host$ [ "$REPLAYED" = ok ] && drained && fetch $R && snap_pair $R replay && $REC same --prefix $P/$R after replay && REPLAYED=captured || stop "test 4: replay not published (REPLAYED='$REPLAYED'), replay state not captured, or twins DIFFERENT"    # 'drained' replaces the former 'sleep 65; repeat until queue_depth is 0': not a deadline, the replay can add no delivery
host$ [ "$REPLAYED" = captured ] && python3 -c "import json;a=json.load(open('$P/$R.metrics.after.json'));b=json.load(open('$P/$R.metrics.replay.json'));print({k:b[k]-a[k] for k in ('accepted','rejected','duplicate','failed','dropped')},'same controller process:',a['started_at']==b['started_at'])" || stop "test 4: not evaluated (REPLAYED='$REPLAYED')"
host$ [ "$REPLAYED" = captured ] && $REC check $P/$R && keep $P/$R.reconcile.json $P/$R.reconcile.post-replay.json || stop "test 4: second check not run (REPLAYED='$REPLAYED') or non-zero, or the post-replay copy already exists"      # check again, on the re-fetched log: duplicates = replayed messages, double_accepted = 0, delivered_unique unchanged
host$ [ "$REPLAYED" = captured ] && python3 -c "import json;a=json.load(open('$P/$R.reconcile.pre-replay.json'));b=json.load(open('$P/$R.reconcile.post-replay.json'));[print(k,'pre-replay',a[k],'post-replay',b[k],'' if k=='duplicates' else ('UNCHANGED' if a[k]==b[k] else 'CHANGED')) for k in ('sent_valid','delivered_unique','lost','late_confirmations','double_accepted','duplicates')]" || stop "test 4: not evaluated (REPLAYED='$REPLAYED')"
host$ [ "$REPLAYED" = captured ] && python3 -c "import json,collections; ev=[json.loads(l) for l in open('$HOME/egw-tcg/itest/$R/events.jsonl')]; print(collections.Counter(e['outcome'] for e in ev)); print('accepted unique:', len({e['message_id'] for e in ev if e['outcome']=='accepted'}), 'accepted total:', sum(e['outcome']=='accepted' for e in ev))" || stop "test 4: not evaluated (REPLAYED='$REPLAYED')"
```

Interlock (the replay is a **second publication**, so it is bound to the outcome of the first run, not to the existence of files): `T4` becomes `ok` only when `run_test` returned 0 **and** both write-once pre-replay copies were saved by `keep`; the replay line publishes only while `T4` is `ok` and sets it to `replayed` before publishing, so pasting that line twice cannot publish a second replay; `REPLAYED` becomes `ok` only when the replay simulator exited 0 and `captured` only when the `replay` pair was taken and `same` reported the twins identical; every evaluation line tests it. The earlier form inferred the state from two non-empty files: after `TEST STATUS ... FAILED` (where `check` has still written `reconcile.json`), or after a `precondition failed` on a reused run id, the plain `cp` succeeded — overwriting the saved pre-replay accounting of the earlier execution — and the replay was published.

Expected: after the replay, `duplicate` equals the number of replayed messages (every replayed event has a known `message_id` and a `seq <= last_seq` within the same `run_id` — CONTRACTS §4; the per-device LRU holds 1024 ids and a 60 s smoke sends at most 600 per device, so both mechanisms apply), `accepted unique == accepted total` (no double acceptance; `check`: `double_accepted = 0`, and the side-by-side line prints `delivered_unique`, `lost`, `late_confirmations` and `double_accepted` as `UNCHANGED` between `<run>.reconcile.pre-replay.json` and `<run>.reconcile.post-replay.json` — `check` rewrites `<run>.reconcile.json` and rebuilds `<run>.reconcile/` on every call and the second `fetch` overwrites `events.jsonl`, so the two copies and `<run>.events.pre-replay.jsonl` are the saved artefacts of this comparison), `same` reports the three twins `identical` between the `after` and `replay` snapshots (a duplicate never patches the twin), and the `/metrics` difference between those two snapshots is `accepted 0` and `duplicate` = number of replayed messages, with `queue_depth 0` and the same `started_at`. Then the **sequence reset**, the block below, which must give `lost = 0` and every `delta` line `OK`, proving the run-scoped seq floor:

```bash
host$ run_test itest-dup-02 42 --scenario smoke --duration 60
```

*Note (2026-09-19):* until this date the sequence-reset step stood in the prose of the paragraph above, and it was **not run** in the battery of 2026-09-18: the commands for that battery were extracted from the fenced code blocks of this document only, and its archive holds no `itest-dup-02` record. The step is now a fenced block so that it cannot be skipped the same way; the command is unchanged. Test 4's sequence-reset sub-check remains open.

### Test 5 — MQTT disconnect/reconnect: real disconnection, buffering, reconciliation

```bash
host$ R=itest-dropout-01; run_test $R 42 --scenario dropout-reconnect --duration 180; RT=$?
host$ [ "$RT" = 0 ] && python3 -c "import json;m=json.load(open('$HOME/egw-tcg/itest/$R/manifest.json'));print(m.get('note'))" || stop "test 5: not evaluated (RT='$RT')"
host$ if [ "$RT" != 0 ]; then stop "test 5: broker log NOT read (RT='$RT')"; elif ssh egw-tcg "cd /opt/egw/deployment && docker compose --env-file .env --env-file images.lock.env logs --no-color mosquitto | grep -E 'egw-simulator-$R'" > ~/egw-tcg/itest/$R.broker.txt && [ -s ~/egw-tcg/itest/$R.broker.txt ]; then wc -l ~/egw-tcg/itest/$R.broker.txt; else stop "test 5: the broker log excerpt was NOT saved (ssh or grep non-zero, no matching line, or $R.broker.txt could not be written)"; fi
```

Expected: stderr `dropout_disconnects = N` with N ≈ 3 (one window per minute, `dropout_windows`), `buffered_dropout > 0`; the manifest carries the `DROPOUT_SCOPE_NOTE`; the broker log shows N+1 connections and N disconnections for the client id `egw-simulator-<run_id>` (`UNVERIFIED:` exact Mosquitto wording — "New client connected from ... as egw-simulator-..." and "Client egw-simulator-... disconnected"/"closed its connection"); `lost = 0` and `late_confirmations = 0` under the controller-clock deadline (buffered events are published late but must be confirmed inside the window), and every `delta` line `OK`. In the `OUTCOME RECONCILIATION` lines of this test the secondary counter figure may exceed `published` by the number of redelivered copies (`duplicate` movement); that has no bearing on the result, which is decided per `message_id` (Section 7, `accounted`). If `lost > 0`, `late_confirmations` says directly how many accepted records were confirmed after the deadline — a guest-speed finding under TCG, reported as measured; `duplicates` (QoS 1 redelivery after reconnect) are not failures, `double_accepted` must be 0.

*Note (2026-09-19):* the one execution of 2026-09-18 (`itest-dropout-01`) **failed the deadline criterion above**: all 2,016 valid events were eventually accepted, but only 1,690 were confirmed within the controller-clock deadline — **326 late**, so `lost = 326` and `late_confirmations = 326`. Three deliberate disconnects and 165 buffered events were observed. Its reconciliation also warned that the simulator manifest of the harness layout is absent, although the simulator totals appended to the same result show the dropout figures: two validation paths disagree. The result is reported as measured; the criterion is unchanged.

### Test 6 — controller restart with recovery and traceability

Use the harness hook so the restart instant is recorded in the manifest, with the pilot plan's first `controller_restart` run id:

```bash
host$ RID=controller_restart-r01    # deterministic (controller_restart-r01..r03); the condition is 600 s nominal, so --restart-at-s 300 is mid-run (protocol.py)
host$ SEED=$(python3 -c "import json;p=json.load(open('$HOME/egw-tcg/pilot/campaign_plan.json'));print(next(r['seed'] for r in p['runs'] if r['run_id']=='$RID'))")
host$ RESTART="ssh egw-tcg 'cd /opt/egw/deployment && docker compose --env-file .env --env-file images.lock.env restart controller'"
host$ T6=stop; if [ -n "$SEED" ] && wait_ready && drained && $REC snap --prefix $P/$RID --label before --seed $SEED; then harness_run $RID --restart-cmd "$RESTART" --restart-at-s 300 && T6=ok; else stop "test 6: no seed, not ready, not drained or no 'before' snapshot - the harness run was NOT started"; fi     # the plan's derived seed, not 42: these are other devices
host$ [ "$T6" = ok ] && drained && $REC snap --prefix $P/$RID --label after && T6=captured || stop "test 6: harness run not complete (T6='$T6') or 'after' snapshot NOT taken - do not run delta"
host$ [ "$T6" = captured ] && $REC delta ~/egw-tcg/pilot/results/raw/$RID --prefix $P/$RID || stop "test 6: delta NOT run (T6='$T6') or it exited non-zero (4 = MISMATCH)"     # twins only: no /metrics snapshots are given, and the process counters restart from zero at the restart anyway
host$ python -m egw_experiments analyze --base-dir ~/egw-tcg/pilot/results --plan ~/egw-tcg/pilot/campaign_plan.json
```

(Manual equivalent without the harness: `run_test <id> 42 --scenario nominal --duration 600` and, 300 s after the simulator's first stderr line (not after the command was entered: `pre` first waits for `drained`), the same `ssh ... restart controller` from a second terminal; `delta` then reports that the controller process restarted and skips the `/metrics` comparison; `accounted` stays evaluable, because it reconciles identities and not counters, and it names every record that the restart left without a logged outcome — the run then ends `FAILED`, which is the measured result and not a defect of the procedure.) The confirmation deadline is applied by the harness itself (`per_run.csv`: `confirmation_deadline_source = controller-marker`, `lost`, `late_confirmations`, `double_accepted = 0`, `restart_*` columns). Every `delta` line must be `OK`: across the restart each twin's `accepted_count` grew by exactly that device's accepted records, i.e. the counter continued from the value stored in the twin instead of restarting — the traceable evidence that the dedupe state was rebuilt from the `ingestion` feature. `/metrics` counters are per process; they restart from zero at the restart and are not compared across it. (`controller_restart` has `warmup_s=0`. For a condition with a warm-up, such as `nominal`, the warm-up runs under the run id `<run_id>.warmup` with the same seed (`run.py`, warm-up note), so it patches the same twins, and its log exists only on the guest: the controller writes one file per run id and the harness fetch hook copies the measured run's file only. Fetch it and pass it to `delta`, with `RID` set to that condition's run id and the `before` snapshot taken before the harness run, as above — `UNVERIFIED:` never executed:

```bash
host$ scp "egw-tcg:/opt/egw/deployment/data/events/$RID.warmup/events.jsonl" $P/$RID.warmup.events.jsonl && [ -s $P/$RID.warmup.events.jsonl ] && $REC delta ~/egw-tcg/pilot/results/raw/$RID --prefix $P/$RID --also $P/$RID.warmup.events.jsonl || stop "test 6: the warm-up log was NOT fetched (delta was then not run), or delta exited non-zero (4 = MISMATCH)"
```

Without `--also`, every device line of such a run is a `MISMATCH` by exactly the warm-up's accepted records.) `UNVERIFIED:` that the controller's `time.monotonic_ns()` continues across a *container* restart (kernel `CLOCK_MONOTONIC`, no time namespace by default; reasoned, not observed) — the marker is read after the run in any case. Expected evidence: the manifest's restart record with timestamps and exit code 0; `controller_metrics.csv` with a sampling gap or counter reset around the restart and samples resuming within 120 s (`RESTART_RECOVERY_MAX_S`, protocol.py); `events.jsonl` continues in the same file (the logger opens it in append mode — `events.py` line 108) with no `message_id` accepted twice (dedupe state is rebuilt from the twin's `ingestion` feature); the delivery loss across the restart, if any, is reported as measured, never suppressed. As in test 5's list: `duplicate` records after the restart — the broker's redelivery, on the resumed session, of the deliveries the stopped process had not acknowledged, which the new process classifies against the twin's `ingestion` feature — are not failures, and `double_accepted` must be 0 (a statement of what is expected, not a change of criterion).

*Note (2026-09-19):* the timed harness runs of this test, `controller_restart-r01` (2026-09-18) and `controller_restart-r02` (2026-09-19), are **invalid**, so neither the recovery nor the delivery of this test is accepted. In `r02` the resource file was rejected for one 6.0 s gap in the controller's series (00:18:29Z to 00:18:35Z, inside the recorded restart interval) against the 5 s limit (`MAX_SAMPLE_GAP_S`), and `controller_metrics.csv` has a 29.115 s gap with 26 failed polls recorded in the manifest. A lifecycle-aware rule for the deliberately restarted container is **proposed, not adopted**, in `docs/governance/proposals/acceptance_protocol_update_2026-09-19.md`. Until it is decided, the ordinary 5 s limit applies to every container; whatever is decided, both runs stay invalid under the rules they were run with.

### Test 7 — temporary Ditto/MongoDB failure: fault handling and recovery per contract

```bash
host$ R=itest-mongo-fault-01; SVC=mongodb
host$ DC="cd /opt/egw/deployment && docker compose --env-file .env --env-file images.lock.env"
host$ svc_state() { local s; s=$(ssh egw-tcg "c=\$($DC ps -aq $SVC) && [ -n \"\$c\" ] && docker inspect --format '{{.State.Status}}' \$c" 2>/dev/null | tail -n 1); echo "${s:-unknown}"; }
host$ fault_recover() { local rc s0 s; s0=$(svc_state); ssh egw-tcg "$DC start $SVC"; rc=$?; s=$(svc_state); echo "start exit=$rc state_after_start=$s state_before_start=$s0 $(date -u +%FT%TZ)"; if [ "$rc" = 0 ] && [ "$s" = running ] && [ "$s0" = exited ]; then echo "RECOVERY SHOWN: $SVC is 'running' after start (it was 'exited' before the start)"; elif [ "$rc" = 0 ] && [ "$s" = running ]; then echo "NO RECOVERY TO SHOW: $SVC is 'running' after start, but it was '$s0' before the start - a return from 'exited' was not observed"; return 1; else echo "STOP: the recovery of $SVC is NOT shown (start exit=$rc, state '$s') - start it by hand before anything else: ssh egw-tcg \"$DC start $SVC\""; return 1; fi; }
host$ fault() {
        local rc s0 s1 bad=0
        trap 'echo "STOP: the fault job was interrupted - the recovery is attempted now"; fault_recover; exit 1' INT TERM HUP
        sleep 90 & wait $!
        if pgrep -f "egw_simulator run .*--run-id $R( |\$)" >/dev/null; then
          s0=$(svc_state); ssh egw-tcg "$DC stop $SVC"; rc=$?; s1=$(svc_state)
          echo "stop exit=$rc state_before=$s0 state_after_stop=$s1 $(date -u +%FT%TZ)"
          if [ "$rc" = 0 ] && [ "$s0" = running ] && [ "$s1" = exited ]; then echo "INTERRUPTION SHOWN: $SVC went from 'running' to 'exited'"; else echo "STOP: the interruption of $SVC is NOT shown (stop exit=$rc, state '$s0' -> '$s1') - this run is not a fault test"; bad=1; fi
          sleep 45 & wait $!
        else
          echo "STOP: no simulator process for $R at +90 s - the fault was NOT injected"; bad=1
        fi
        fault_recover || bad=1
        return $bad
      }
host$ readyp() { while :; do printf '%s %s\n' "$(date -u +%FT%TZ)" "$(curl -s -o /dev/null -w '%{http_code}' --max-time 10 $CTRL/ready)"; sleep 2; done; }
host$ T7=stop; if pre $R 42; then fault > $P/$R.fault.txt 2>&1 < /dev/null & FAULTP=$!; readyp > $P/$R.ready.txt < /dev/null & READYP=$!; sim_post $R --seed 42 --scenario nominal --duration 300; SP=$?; wait $FAULTP; FW=$?; kill $READYP; RK=$?; cat $P/$R.fault.txt; if [ "$SP" = 0 ] && [ "$FW" = 0 ] && grep -q '^INTERRUPTION SHOWN' $P/$R.fault.txt && grep -q '^RECOVERY SHOWN' $P/$R.fault.txt && ! grep -q '^STOP' $P/$R.fault.txt && [ "$RK" = 0 ] && [ -f $P/$R.ready.txt ] && [ -s $P/$R.ready.txt ]; then T7=0; else T7="failed:sim_post=$SP,fault_job=$FW,readyp_kill=$RK"; stop "test 7: NOT accepted (sim_post exit=$SP, fault job exit=$FW, kill of the /ready poller exit=$RK; a fault job exit other than 0, a STOP line above, a missing INTERRUPTION SHOWN or RECOVERY SHOWN line, a /ready poller that was no longer running at the end (kill exit other than 0: $R.ready.txt does not cover the run), or an empty $R.fault.txt/$R.ready.txt) - check that $SVC is running: ssh egw-tcg \"$DC ps $SVC\""; fi; else stop "test 7: precondition failed - NO fault was injected and nothing was published"; fi
host$ [ "$T7" = 0 ] && python3 -c "import json,collections;ev=[json.loads(l) for l in open('$HOME/egw-tcg/itest/$R/events.jsonl')];print(collections.Counter((e['outcome'],e.get('attempts')) for e in ev)); print([e['error'] for e in ev if e['outcome']=='failed'][:3])" || stop "test 7: not evaluated (T7='$T7': only 0 = run complete AND interruption shown AND recovery shown)"
```

Expected: during the 45 s outage the controller records `failed` outcomes with `attempts: 3` and a 5xx/timeout `error` (bounded retry, CONTRACTS §5) — or, if Ditto's things service answers 4xx, `failed` with `attempts: 1`; `/ready` may drop to 503 if the gateway stops answering (record either); after `start mongodb` accepted outcomes resume and every `delta` line is `OK`: per device, Δ`accepted_count` between the `before` and `after` snapshots equals the accepted records of this run (the absolute value also contains every earlier seed-42 run, so it is never compared with this run alone), and the `/metrics` differences of `accepted` and `failed` equal the outcome counts provided `started_at` is unchanged (the controller is not restarted in this test). `lost` is reported together with the quantities `check` and `delta` print next to it: `failed` (bounded retry exhausted, CONTRACTS §5), `late_confirmations` (confirmed after the controller-clock deadline) and the `/metrics` `dropped` difference (queue overflow). `lost` need not equal `failed`: `lost` is "valid sent without a unique in-window confirmation" (`analyze.py`), so it also contains late confirmations, queue-overflow drops and messages that never reached the controller, none of which is a `failed` record. That is the contract's behaviour, to be reported, not hidden. `UNVERIFIED:` if Ditto applies a patch whose 2xx answer is lost, the event is `failed` while the twin was already changed; whether the per-device delta then still closes has not been observed — report a `MISMATCH` as measured. Repeat once for Ditto, with the block under the next heading, "Repeat of test 7 for Ditto": it sets `R=itest-ditto-fault-01; SVC=ditto-things` and pastes **the `T7=stop; if pre ...` line and the evaluation line after it** again, unchanged (`svc_state`, `fault_recover`, `fault` and `readyp` read `$R`, `$SVC` and `$DC` when they run, so they need not be redefined).

**Test 7 is accepted only when the interruption and the recovery are both shown.** (i) both exit codes are kept and printed (`stop exit=`, `start exit=`), and next to each the **state of the service read over ssh after the step** (`svc_state`: the container id from `docker compose ps -aq <service>`, then `docker inspect --format '{{.State.Status}}'`): `INTERRUPTION SHOWN` needs `stop` exit 0 **and** the state going from `running` to `exited`; `RECOVERY SHOWN` needs `start` exit 0 **and** the state going from `exited` (read just before the `start`, printed as `state_before_start=`) to `running`; a service that is `running` after the `start` but was not `exited` before it — the paths of (ii) on which nothing was stopped — gives the line `NO RECOVERY TO SHOW:` and a non-zero fault job, never `RECOVERY SHOWN` (no recovery was observed there); anything else, an unreadable state (`unknown`) included, is one `STOP:` line; (ii) the recovery is attempted **on every path the fault job itself controls** — after a failed `stop`, when the simulator process is gone at +90 s (nothing is stopped then, and `start` on a running service changes nothing), and when the job receives `INT`, `TERM` or `HUP` (trap; the two sleeps are `sleep N & wait $!` so that the trap is not held back by them). A job that is killed with `KILL`, or stopped, cannot recover anything: the test line then sees a non-zero `wait` status and says how to check the service. Both background jobs run with `< /dev/null`: in an interactive shell a background job keeps the terminal as its stdin, and an `ssh` without `-n` that reads it is stopped by `SIGTTIN` as soon as a line is typed — before the `stop` (no fault) or at the `start` (service left `exited`; `wait` status 149); (iii) the status of `wait $FAULTP` is used (`FW`), and `T7` becomes 0 **only** when `sim_post` and the fault job both returned 0, `fault.txt` holds both `... SHOWN` lines and no `STOP` line, `ready.txt` is a non-empty regular file, and the `/ready` poller was **still running** when the line killed it (`RK`, the status of `kill $READYP`, is 0: a poller that ended early, for example because its redirect failed, leaves a `ready.txt` that does not cover the outage; what `/ready` answered during the outage is read by the operator, the line does not judge it). In every other case `T7` is `failed:...`, one `STOP:` line is printed by the test line, and the evaluation line refuses. The fault job still injects nothing unless the simulator process of this run id is alive 90 s after the start (`pgrep`, procps, part of Ubuntu-24.04; a simulator that failed at once therefore leaves MongoDB alone while `post` captures the state). `UNVERIFIED:` the values `running` and `exited` of `.State.Status` and the `-a`/`-q` flags of `docker compose ps` are documented Docker behaviour, not observed on Compose 2.26.0 / docker-moby 25.0.9 (if the state strings differ on the guest, the test stops instead of passing); the block was run with stubs only, in a non-interactive bash and, for `< /dev/null`, in an interactive bash on a pty with a stub `ssh` that reads its stdin; the real OpenSSH client was not used (Appendix B item 20). If the test line is interrupted (Ctrl-C), bash abandons the rest of it and the poller keeps appending to `ready.txt`: run `kill $READYP; wait $FAULTP; cat $P/$R.fault.txt` before anything else (`T7` is still `stop`; the fault job restarts the service on its own). `UNVERIFIED:` which of the two error shapes Ditto 3.9.4 produces when MongoDB is down.

*Note (2026-09-19):* the one execution of 2026-09-18 covered the MongoDB fault only. `itest-mongo-fault-01` showed bounded retry and fault behaviour, not lossless delivery: 62 events failed after three attempts (HTTP 500 from Ditto), and 1,012 of the 3,298 accepted events were confirmed after the controller-clock deadline. The repeat for Ditto (`itest-ditto-fault-01`) was **not run**: until this date it stood in the prose of the expected results above, the commands for that battery were extracted from the fenced code blocks of this document only, and its archive holds no `ditto-fault` record. The repeat is now the fenced block under the next heading, with its commands unchanged, so that it cannot be skipped the same way; it has a heading of its own because the runbook's tests (`src/tests/test_runbook_itest_helpers.py`) read the fenced commands of this section as a single run. Test 7's Ditto repeat remains open.

### Repeat of test 7 for Ditto — the same fault on `ditto-things`

The repeat for Ditto called for in the expected results of test 7, pasted in the same shell right after test 7, whose helpers it reuses. Its second and third lines are test 7's test line and evaluation line, unchanged.

```bash
host$ R=itest-ditto-fault-01; SVC=ditto-things
host$ T7=stop; if pre $R 42; then fault > $P/$R.fault.txt 2>&1 < /dev/null & FAULTP=$!; readyp > $P/$R.ready.txt < /dev/null & READYP=$!; sim_post $R --seed 42 --scenario nominal --duration 300; SP=$?; wait $FAULTP; FW=$?; kill $READYP; RK=$?; cat $P/$R.fault.txt; if [ "$SP" = 0 ] && [ "$FW" = 0 ] && grep -q '^INTERRUPTION SHOWN' $P/$R.fault.txt && grep -q '^RECOVERY SHOWN' $P/$R.fault.txt && ! grep -q '^STOP' $P/$R.fault.txt && [ "$RK" = 0 ] && [ -f $P/$R.ready.txt ] && [ -s $P/$R.ready.txt ]; then T7=0; else T7="failed:sim_post=$SP,fault_job=$FW,readyp_kill=$RK"; stop "test 7: NOT accepted (sim_post exit=$SP, fault job exit=$FW, kill of the /ready poller exit=$RK; a fault job exit other than 0, a STOP line above, a missing INTERRUPTION SHOWN or RECOVERY SHOWN line, a /ready poller that was no longer running at the end (kill exit other than 0: $R.ready.txt does not cover the run), or an empty $R.fault.txt/$R.ready.txt) - check that $SVC is running: ssh egw-tcg \"$DC ps $SVC\""; fi; else stop "test 7: precondition failed - NO fault was injected and nothing was published"; fi
host$ [ "$T7" = 0 ] && python3 -c "import json,collections;ev=[json.loads(l) for l in open('$HOME/egw-tcg/itest/$R/events.jsonl')];print(collections.Counter((e['outcome'],e.get('attempts')) for e in ev)); print([e['error'] for e in ev if e['outcome']=='failed'][:3])" || stop "test 7: not evaluated (T7='$T7': only 0 = run complete AND interruption shown AND recovery shown)"
```

### Test 8 — guest reboot: stack start-up and persistence

```bash
host$ if wait_ready && drained && $REC snap --prefix $P/itest-reboot --label pre-reboot --seed 42 && ssh egw-tcg cat /proc/sys/kernel/random/boot_id > $P/itest-reboot.boot_id.pre && [ -s $P/itest-reboot.boot_id.pre ]; then ssh egw-tcg 'sudo journalctl --list-boots | tail -n 2; ls /opt/egw/deployment/data/events; sudo systemctl reboot'; else stop "test 8: no pre-reboot snapshot or no boot id - the guest was NOT rebooted"; fi     # all three seed-42 twins, whatever earlier tests left in them; the ssh status is not tested: the connection drops with the reboot
# QEMU exits (-no-reboot). Re-launch exactly as in 3.3 (./scripts/run-qemu-integrated.sh <new run name>) with the SAME data-disk file
# (default $HOME/yocto/egw-integrated/egw-data.img — do not touch EGW_DATA_DISK between the two boots), then:
host$ ssh egw-tcg 'systemctl is-system-running; systemctl --failed --no-legend; sudo journalctl --list-boots | tail -n 3; sudo journalctl -b -1 -u docker.service --no-pager | tail -n 5; docker ps --format "{{.Names}} {{.Status}}"; ls /opt/egw/deployment/data/events; df -h / /var/lib/docker; findmnt -no SOURCE /var/lib/docker'
host$ tunnel_down && tunnel_up || stop "test 8: tunnel NOT reopened (tunnel_down/tunnel_up of 5.7; only this project's control socket is touched)"
host$ [ -s $P/itest-reboot.boot_id.pre ] && B1=$(ssh egw-tcg cat /proc/sys/kernel/random/boot_id) && [ -n "$B1" ] && [ "$B1" != "$(cat $P/itest-reboot.boot_id.pre)" ] && echo "REBOOT SHOWN: boot id $(cat $P/itest-reboot.boot_id.pre) -> $B1" && wait_ready 3600 && $REC snap --prefix $P/itest-reboot --label post-reboot --like pre-reboot && $REC same --prefix $P/itest-reboot pre-reboot post-reboot || stop "test 8: persistence across a reboot NOT verified (reboot not shown: boot id missing, unreadable or unchanged; stack not ready; snapshot failed; or 'same' reported DIFFERENT)"
host$ R=itest-post-reboot-01; run_test $R 42 --scenario smoke --duration 30
```

Expected: `REBOOT SHOWN` with two different kernel boot ids (the status of the `reboot` ssh cannot be tested, so the persistence line refuses unless `/proc/sys/kernel/random/boot_id` read after the re-launch differs from the value saved in `itest-reboot.boot_id.pre`; `UNVERIFIED:` that file on the guest kernel — if it cannot be read the test stops, it cannot pass); the six containers come back on their own (`restart: unless-stopped` plus `docker.service` enabled), `sudo journalctl --list-boots` shows the previous boot (persistent journal — assumption A14; `sudo` is required because `egw` is not in the `systemd-journal` group and would otherwise see only its user journal), `/var/lib/docker` is again on `/dev/vdb`, `same` reports the three seed-42 twins `identical` across the reboot (the comparison is between the two snapshots; the values themselves are whatever the earlier tests accumulated — a snapshot taken before any seed-42 run would show `exists: false` and prove nothing, so run this test after 6.2 or test 1), old `data/events/*` directories are intact, and the fresh smoke run gives `lost = 0`, `late_confirmations = 0` and every `delta` line `OK`, starting from the persisted `accepted_count`; `/metrics` starts from zero with a new `started_at` (new controller process), and the controller's monotonic clock restarted with the guest, which is harmless because each run's marker is read after that run. No manual step between reboot and a working stack is the acceptance of work order item 3.

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
host$ ssh egw-tcg 'cd /opt/egw/deployment && docker compose --env-file .env --env-file images.lock.env logs --no-color --tail 20 mosquitto' | tee ~/egw-tcg/itest/itest-auth.broker.txt; ST=("${PIPESTATUS[@]}"); [ "${ST[0]}" = 0 ] && [ "${ST[1]}" = 0 ] && [ -s ~/egw-tcg/itest/itest-auth.broker.txt ] || stop "test 9(b)/(c): the broker log was NOT saved (ssh exit=${ST[0]}, tee exit=${ST[1]}, or an empty file) - (b) and (c) have no evidence"
# (d)+(e) ACL proven in both directions with concurrent known traffic, and anonymous refusal. Runs in the guest, inside the
# broker container (mosquitto_pub/mosquitto_sub of the image; nothing to install on the host; no 'timeout' applet needed).
# Precondition, enforced by the next line: controller ready and 'drained' (no simulator/harness run may be in progress: the operator's rule).
host$ T=$(date -u +%Y%m%dT%H%M%SZ); PR=stop; if wait_ready && drained && metrics itest-acl-$T before; then ssh egw-tcg "sh /opt/egw/deployment/scripts/probe-acl.sh $T"; PR=$?; echo "probe exit=$PR (0 PASS, 1 FAIL, 3 INCONCLUSIVE, 2 usage/precondition: nothing was run and there is no verdict.txt, 255 ssh failed: nothing is known; about 100 s)"; metrics itest-acl-$T after; [ "$PR" = 0 ] || stop "test 9(d): probe exit=$PR - NOT a pass (1 FAIL, 3 INCONCLUSIVE, anything else: the probe did not run to its end)"; else stop "test 9(d): precondition failed - the probe was NOT run"; fi
host$ [ "${PR:-stop}" != stop ] && scp -r egw-tcg:/opt/egw/evidence/itest-acl-$T ~/egw-tcg/itest/ || stop "test 9(d): probe not run (PR='$PR') or scp failed - no evidence was copied"
host$ B=~/egw-tcg/itest/itest-acl-$T.metrics.before.json; A=~/egw-tcg/itest/itest-acl-$T.metrics.after.json; if [ "${PR:-stop}" != stop ] && [ -s $B ] && [ -s $A ] && [ -s ~/egw-tcg/itest/itest-acl-$T/verdict.txt ]; then python3 -c 'import json,sys; b,a=(json.load(open(p)) for p in sys.argv[1:3]); d=[k for k in ("started_at","accepted","rejected","duplicate","failed","dropped") if a[k]!=b[k]]; print("changed fields:", d); sys.exit(1 if d else 0)' $B $A && echo "controller untouched by the probe" || stop "test 9(d): controller counters or started_at changed during the probe, or a snapshot is not valid /metrics JSON"; else stop "test 9(d): probe not run (PR='$PR'), or a metrics snapshot or verdict.txt is missing or empty - NOTHING was compared"; fi
host$ [ "${PR:-stop}" != stop ] && { cat ~/egw-tcg/itest/itest-acl-$T/verdict.txt ~/egw-tcg/itest/itest-acl-$T/ctl-sub.out && wc -c ~/egw-tcg/itest/itest-acl-$T/sim-sub.out ~/egw-tcg/itest/itest-acl-$T/anon.out && cat ~/egw-tcg/itest/itest-acl-$T/broker.txt; } || stop "test 9(d): nothing to show (PR='$PR') or an evidence file is missing"
```

Expected: (a) exit 1, `connection failed` with a certificate-verify error; (b) and (c) exit 1 **after about 15 s** with `egw_simulator: connection failed: MQTT connect to 127.0.0.1:8883 not acknowledged within 15 s` — the simulator's `_on_connect` discards the failure reason code and `connect()` only reports the 15 s timeout (`publisher.py` lines 235 and 251-256, `cli.py` line 246), so "not authorised" never appears in its stderr; the evidence is the broker log captured above (`connection_messages true`, `log_type notice/information` in `mosquitto.conf`): a "not authorised" line for (b) and a TLS/socket error for (c) (`UNVERIFIED:` exact Mosquitto 2.0.22 wording); (d) `scripts/probe-acl.sh` exits 0 and `verdict.txt` ends with `verdict=PASS`. What it does: inside the broker container (`docker compose exec -T`, `-h localhost -p 8883 --cafile /mosquitto/config/certs/ca.crt`; `localhost` is in the certificate SAN) it starts two **concurrent** subscribers on `c2dt/#` — `egw-controller` (ACL `read`) and `egw-simulator` (ACL `write` only) — waits until the broker log shows both subscriptions, then publishes four uniquely tagged QoS 1, non-retained messages on `c2dt/acl-probe/<tag>`: P1 as `egw-simulator`, P2 as `egw-controller` (MQTT 3.1.1), P3 as `egw-controller` (MQTT 5), P4 as `egw-simulator`. Pass criteria: `ctl-sub.out` contains exactly the P1 and P4 lines (`c2dt/acl-probe/<tag> acl-probe <tag> P1 user=egw-simulator`, likewise P4) and neither P2 nor P3; `sim-sub.out` is 0 bytes (`deliveries=0 stdout_bytes=0` in `verdict.txt`). A **delivery** is a line that starts with `c2dt/`: all three subscribers run `mosquitto_sub -v` on `c2dt/#`, so every delivered message is printed as `<topic> <payload>`. One such line in `sim-sub.out` is a FAIL. Any other byte there is neither a delivery nor silence and makes the run inconclusive — the Docker engine writes exec start-up errors (for example `… exec: "mosquitto_sub": executable file not found in $PATH`) to the exec's **stdout** stream (moby v25.0.9, `api/server/router/container/exec.go`, `postContainerExecStart`; read in the sources, `UNVERIFIED:` on this engine), so bytes on stdout do not prove that a message arrived; both subscribers end with rc 27 (`MOSQ_ERR_TIMEOUT`: ended by `-W`, not by an error) and the broker log shows **exactly one** subscription line for **each** of them (`<client id> 1 c2dt/#`), logged before P1 — counted per client, so two lines of one subscriber cannot stand in for the other, and a second line (a reconnection, i.e. a gap in which a message could have been missed) makes the run inconclusive; all four publishers exit 0; and the `liveness:` line of `verdict.txt` reads `covered=yes`. Subscribed-before-P1 and rc 27 say how a subscriber ended, not **when**, so the probe bounds the end in time (whole seconds from `/proc/uptime`; `date +%s` where `/proc` is absent): rc 27 means that `SIGALRM` fired `-W` seconds after an `alarm()` which `mosquitto_sub` sets after it was started (`client/sub_client.c`, tag v2.0.22; sources, not observed), so neither session can have ended before `sub_start + window`; P4 must have **returned** at least 2 s before that instant (`p4_end + 2 <= earliest_timeout`), and the `docker compose exec` of **each** subscriber must be seen to return after P4 did (`exec_end > p4_end`; an upper bound of the session's end, hence necessary and not sufficient on its own). For the authorised subscriber the delivery of P1 and P4 already shows this; for the unauthorised one, whose expected output is silence, nothing else does. A slow readiness wait under TCG that pushes P4 past the bound therefore gives `covered=no` and exit 3, never a pass. P1/P4 are the positive control that brackets the denied publishes: the read restriction is proven by the same tagged message reaching the authorised subscriber and not the unauthorised one, the write restriction by P2/P3 reaching nobody while P1/P4 do. Three Mosquitto 2.0.22 behaviours (checked in the sources at tag v2.0.22, not yet observed on this stack) must not be misread: the built-in `acl_file` check grants **every** SUBSCRIBE (`src/security_default.c`) and filters at delivery, so `broker.txt` shows a subscribe line (`<client id> 1 c2dt/#`) for `egw-simulator` as well — expected, not a failure; a denied PUBLISH is logged only at debug level (`src/handle_publish.c`), which `mosquitto.conf` does not enable, so `broker.txt` carries no "denied" line; and under MQTT 3.1.1 the denied QoS 1 publish is acknowledged normally (P2 exits 0 with no error), whereas the MQTT 5 publisher P3 is expected to print `Warning: Publish 1 failed: Not authorized.` and still exit 0 (`client/pub_client.c`; `UNVERIFIED:` on this stack; recorded in `verdict.txt`, not a pass criterion). Exit 3 (`INCONCLUSIVE`) means that a precondition, the positive control, the *execution* of one of the probes or the *collection of the evidence* failed, and proves nothing either way: every claim needs positive evidence, and a command that did not run, or that ended in any way other than the expected one, is never read as a refusal. The counts taken from the broker log (subscription lines per subscriber, the accepted-session line of the anonymous client) are evidence only when the collection is shown to cover the run; a zero from a failed or partial collection is absence of evidence. The probe therefore reads the last broker log line **before** it starts the first subscriber (the anchor, `broker_anchor.txt`, with the engine's per-line timestamp: `docker compose logs --timestamps`, `UNVERIFIED:` on the guest — if the option is refused the collection fails and the exit is 3; what the two `docker compose logs` calls wrote to stderr is kept in `broker_logs.err`, recorded for the operator and not evaluated) and accepts the collection made after the run only when `docker compose logs` returned 0, the output is not empty, the anchor occurs exactly once in the last 400 lines (so the `--tail` window still starts before the run), `grep` did not fail and `broker.txt` has as many lines as a recount of the collection. It also writes a known line to the evidence directory and reads it back, before the run (failure: exit 2, nothing was run) and after the collection (failure: exit 3); this is necessary and not sufficient — a write lost during the run to a file whose expected content is 0 bytes cannot be told from silence. The `evidence:` line of `verdict.txt` records every check and reads `broker_log=complete` or `broker_log=incomplete (<reasons>)`. An incomplete collection is exit 3 unless a security failure was positively observed (a delivery, an accepted anonymous session, also as a line found in a partial log): FAIL keeps precedence. If `verdict.txt` itself cannot be written completely, the verdict is printed on the terminal with a note on stderr and a PASS is downgraded to exit 3. Typical causes are `docker compose exec` start-up under TCG consuming the window (`liveness: covered=no`, or a subscriber rc other than 27), output on a subscriber's stdout that is not a delivery (`deliveries=0` with `stdout_bytes` above 0: read the `.out` file, it is usually an exec error), and any anonymous-probe outcome other than the two described under (e). Read the `liveness:`, `anonymous:`, `deliveries=`/`stdout_bytes=` and `rc=` fields of `verdict.txt` to see which part failed, repeat with a new tag and, for the window case, `ACL_PROBE_WINDOW=180` (e.g. `ssh egw-tcg "ACL_PROBE_WINDOW=180 sh /opt/egw/deployment/scripts/probe-acl.sh $T"`); never report exit 3 as a pass. A FAIL condition takes precedence over an inconclusive one. The probe topic has three levels and cannot match the controller's filter `c2dt/+/+/telemetry`, so the controller receives none of the probe messages: the `/metrics` comparison must print `changed fields: []` and `controller untouched by the probe` (identical `accepted/rejected/duplicate/failed/dropped` and identical `started_at`, i.e. the same controller process). That line compares only when the probe was started (`PR`) and both snapshots and `verdict.txt` exist and are non-empty, and it reads the six fields from the parsed JSON: the first version (`diff <(... | grep) <(... | grep) && echo ...`) printed the acceptance sentence after a failed precondition as well, because two missing files give two empty streams and `diff` of nothing with nothing is 0. The Mosquitto clients accept a password only through `-P`, so while the probe runs the two dev passwords are on the argv of the clients inside the broker container and of `docker compose exec` in the guest (the same class of exposure as the simulator's `--password` on the host); nothing written to the evidence directory contains them. (e) The anonymous client (no `-u`/`-P`, MQTT 3.1.1 pinned with `-V mqttv311` so that the refusal has a single form) counts as refused **only when the refusal itself is observed**: `anon.rc` is 5, `anon.err` contains the exact line `Connection error: Connection Refused: not authorised.`, `anon.out` is 0 bytes and `broker.txt` has no `New client connected … as egw-acl-<tag>-anon (` line in a **complete** broker log collection (`evidence: broker_log=complete`; with an incomplete one the anonymous case is `inconclusive`); `verdict.txt` then reads `anonymous: refused rc=5 refusal_lines=1 deliveries=0 stdout_bytes=0 …`. This is what the Mosquitto 2.0.22 sources prescribe, not yet observed on this stack (`UNVERIFIED:`): with `allow_anonymous false` and no user name `mosquitto_unpwd_check` returns `MOSQ_ERR_AUTH` and the broker answers CONNACK 5 (`src/security.c`, `src/handle_connect.c`); `mosquitto_sub` prints `Connection error: ` followed by `mosquitto_connack_string(5)` and its `main()` returns the CONNACK code (`client/sub_client.c`, `lib/strings_mosq.c`). An **accepted** session is a FAIL (exit 1): rc 0, rc 27 (`MOSQ_ERR_TIMEOUT`: alive when `-W 10` expired), a delivery in `anon.out` (a line that starts with `c2dt/`; the anonymous subscriber also runs with `-v`), or the broker's `New client connected` line for the anonymous client id. **Every other outcome is INCONCLUSIVE (exit 3), never a pass**: `docker compose exec` errors (1, 125, 126, 127, 137) **whether their text lands on stderr or on stdout** — bytes in `anon.out` that are not a delivery are an execution error, not an accepted session and not a refusal (the refusal needs a 0-byte `anon.out`) —, `Error: Problem setting TLS options…` (rc 1); any failure of the connect itself — TLS handshake, socket, name lookup — which `client_connect()` reports as `Unable to connect (<reason>).` or `Error: <strerror>` (`client/client_shared.c`) and which also ends in **rc 1**, because `main()` of `mosquitto_sub` 2.0.22 jumps to `cleanup:` and returns 1 when `client_connect()` fails (`client/sub_client.c`); `Error: <mosquitto_strerror>` with rc 7, 8 or 14 only for a failure **after** the connection was established (the return value of `mosquitto_loop_forever`); rc 5 with an empty or different stderr, the MQTT 5 wording, or a missing file — in none of them did the client receive the CONNACK 5 that the test is about. The broker's own line for the refused CONNECT (`Client … disconnected, not authorised.`, `src/loop.c`) is recorded as `broker_lines=` for corroboration only: whether it carries the client id or `<unknown>` is `UNVERIFIED:`, so it is not a criterion. Also keep `ssh -p 2222 root@127.0.0.1` refused and `nmap`-free port evidence: `ss -ltn` on the host shows only 2222 and 8883 forwarded by QEMU; inside the guest `docker ps` shows `127.0.0.1:8080` and `127.0.0.1:8000` bindings and MongoDB with no published port (work order item 5).

---

## 8. Pilot and load rules (work order item 9)

1. **Order.** Only after tests 1-9 pass: one short nominal run (`--scenario nominal --duration 120`), then the plan's nominal duration (600 s), then `load-sweep` at 10 and 50 msg/s (300 s each), then a short soak (`--scenario soak --duration 3600`). Never the 24 h soak and never the 95 runs of `experiments/campaign_plan.json` on this environment. **Superseded on 2026-09-19** as to the last sentence only: the 24-hour soak and the 95-run composition are now a target to **attempt** under QEMU, subject to this pilot's feasibility finding and to a prospectively frozen protocol (adopted plan, section 3.3.1). The ordering rule itself is unchanged — neither is started here, before tests 1-9 are complete and the pilot has reported — and the attempt is neither the frozen protocol nor a promise of 95 valid runs.
2. **Generator delivery check** on every run: `sent / duration` from `sent_events.jsonl` versus the requested rate; if the simulator cannot sustain the rate (host CPU shared with QEMU), the run is a pilot finding, not a measurement.
3. **Label.** Every manifest, figure and table produced from these runs carries "ARM64 emulated (QEMU 8.2.7/TCG on x86-64)"; the `sut_environment.json` fields of 5.8 carry it until Section 9 adds `execution_mode`.
4. **Resource competition.** QEMU/TCG (4 vCPU threads plus I/O and the display-less console), the simulator, the harness sampler and the SSH tunnels all share the WSL2 VM's 16 CPUs and its memory limit; container `cpu_pct` from `docker stats` inside the guest is relative to the *emulated* CPUs, and the QEMU process's host utilisation is a different quantity — document both (Section 9). No Yocto build, no Windows sleep/hibernate, no Docker Desktop builds during a pilot run.
5. **Validity rules unchanged.** Missing `sut_environment.json`, missing or short `resources.csv`, collector hook failures, collector output that cannot be accounted for (`collector.problems` in the manifest, Section 7, test 1) and checksum mismatches still invalidate runs; no `--allow-missing-*` flag is used to make a pilot run pass. Slowness alone never excludes a run.
6. **Supervisor alignment** on the open part of D014 — the wording of the limitation that records the absence of native evidence and of any claim about emulated timing and resource figures — is obtained before any of these numbers enter the dissertation (ADR 0008; work order item 9). The QEMU evaluation scope of RQ3 is reported approved (reported by the student, undated, not a documented supervisor decision) and is not re-requested; the numerical criteria belong to D007. *(Corrected 2026-09-19; previously listed the academic use of emulated results as open.)*

---

## 9. Instrumentation changes required (described, not implemented — deliverable 3)

1. **`src/deployment/scripts/capture-sut-environment.sh`** — add fields: `execution_mode` (`tcg-emulated` | `native-kvm` | `native-metal`, from an `EGW_EXECUTION_MODE` variable with **no default**: an unset value must make the harness mark the run invalid), `hypervisor` (`systemd-detect-virt` output, present in the G1 rootfs), `cpu_part` (from `/proc/cpuinfo`), `cpu_features`, `kernel_cmdline` (`/proc/cmdline`, which carries `mem=` and `root=`), `image_identity` (`/etc/buildinfo` content or `IMAGE_NAME`, rootfs sha256 from the build evidence passed as `EGW_IMAGE_SHA256`), `container_image_ids` (`docker image inspect --format '{{.RepoTags}} {{.Id}}'` of the six images), `docker_info_cgroup_version`, `cfs_bandwidth` (recorded as disabled per plan v2.0 §5 item 2).
2. **A host-side capture** (new `scripts/capture-hypervisor-environment.sh`, run on the WSL host, output `hypervisor_environment.json`): QEMU version (`qemu_version.txt`), the exact runqemu command line (machine, `-cpu`, `-smp`, `-m`, `-netdev`), the disk file and its size, WSL kernel `uname -a`, Windows build, host CPU model and `nproc`, `.wslconfig` limits, and `colocated_with_loadgen: true`. The harness references it from the manifest next to `sut_environment.json` and `loadgen_environment.json` (three environments for emulated runs; work order item 7).
3. **`src/egw_experiments/environment.py`** — extend `REQUIRED_SUT_FIELDS` with `execution_mode` and `image_identity`; `run.py` copies `execution_mode` into the manifest top level and records the hypervisor file; `plan_gen`/`campaign` refuse to run plan entries when `execution_mode == tcg-emulated` unless `--pilot` is given (recorded as a deviation).
4. **`src/egw_experiments/analyze.py`** — group by `execution_mode`; refuse to pool runs of different modes into one statistic; write processed outputs under `processed/<execution_mode>/`; stamp every figure with the mode; treat `tcg-emulated` as `performance_claims_allowed = False` at the condition level exactly as `qemu_boots` already is; a wrong-provenance regression test (native manifest with an emulated SUT file must be rejected).
5. **Collectors** — `collect-resources.sh` unchanged (it already stamps `host`); add an optional host-side sampler for the QEMU process (`top -b -n 1 -p <pid>` at 1 Hz on the WSL host into `qemu_process.csv`) so emulated-CPU utilisation and host utilisation are never confused.
6. **TCG timing profile** — if start-up timeouts must change (Section 5.5), they live in `compose.tcg.yaml` and in a documented harness profile; the confirmation window (60 s), loss criteria and saturation rules do not change.
7. **Controller: make "no work in progress" observable** — **implemented in the controller on 2026-09-18** (`received`, `in_progress`, `processing_errors`: CONTRACTS §5, sub-section "Progress counters in `GET /metrics`"; `docs/adr/0010-controller-progress-counters.md`; unit tests with fakes only, never deployed or run on the gateway). Under ADR 0011 (`docs/adr/0011-controller-restart-recovery.md`, work items 14 and 19) `/metrics` also carries `mqtt_subscribed`, `mqtt_connection` and `unacked`, and the helpers of this runbook read the new fields: `_mline` reads the thirteen fields of 6.1, refuses a response missing one or carrying one of the wrong type, and evaluates the accounting identity on every reading; `drained` calls a reading quiet only as 6.1 states and keeps its window, thresholds and message prefixes unchanged; `accounted` is unchanged, and the counters show the controller's internal state only and never replace identity reconciliation. What follows is the proposal as it was written before the implementation; where the two differ — `processing_errors` is the residual recorded when processing ends without any outcome counter having moved, not only the `except` branch, and the "single reading" form of `drained` proposed below is superseded, since the identity is evaluated on every reading of a window that ADR 0011 (condition C5) keeps unchanged — CONTRACTS §5 and 6.1 are authoritative. Proposal text: (additive to CONTRACTS §5, like `dropped` and the marker; it changes no existing field and no latency stamp). Today `/metrics` cannot show a message that has left the queue and has not yet reached a counter (Section 7, "The 130 s quiet window"), which is why the 130 s quiet window is kept as a temporary precaution (a nominal figure, not a bound, and not proof that processing has finished: Section 7 (b)) and why the only positive statement is the per-run reconciliation by identity that `accounted` does on the host, after a run and never before one. The project review of 2026-09-18 decided that these counters come as a separate, delimited observability change; they show the controller's internal state and do **not** replace the reconciliation of identities between published records and logged outcomes. Proposed: `received` — incremented in `ControllerService.submit()` for every message handed over by the bridge, before `put_nowait` (so `dropped` messages are included); `in_progress` — 1 between `self._queue.get()` and the end of `process()` in `run()`, else 0; `processing_errors` — incremented in the `except Exception` branch of `run()`, the one path that today ends a message without any counter. `drained` then becomes a check on a **single** reading — `queue_depth == 0`, `in_progress == 0` and `received == accepted + rejected + duplicate + failed + dropped + processing_errors` — repeated once only to cover the hand-over between the paho thread and the event loop (`mqtt.py` line 199). Needs unit tests for the three counters and an update of `itest_reconcile.py` (`COUNTERS`) and of the harness's `controller_metrics.csv` columns.

---

## 10. Native route pointer

The native ARM64 route (work order deliverable order: subsequent step) is carried by the native-route change set, which is held back for a later pull request and is not part of the first pull request (limited to the integrated QEMU/TCG profile): `src/yocto/kas/egw-genericarm64.yml` (+ `.lock.yml`, MACHINE `genericarm64`, target `egw-gateway-image`, build directory `src/yocto/build-genericarm64/`; unbuilt), and by plan v2.0 §4 prerequisites; `docs/setup/vm_arm64_hetzner.md` is the superseded provider checklist. What changes when a native host appears:

- **Boot artefact and firmware:** a GPT/EFI `.wic` (ESP + systemd-boot + initramfs + ext4 root) instead of `-kernel Image` plus raw ext4; `runqemu ... kvm` with `QB_CPU_KVM = -cpu host -machine gic-version=3` on an ARM64/KVM host, or the cloud's UEFI on a Graviton/UEFI VM (`import-snapshot`/`register-image --architecture arm64 --boot-mode uefi`).
- **Docker data disk:** the native image keeps the same design (`EGW_DOCKER_DATA_DISK = "1"` in `kas/egw-genericarm64.yml`): `/var/lib/docker` lives on a second ext4 device labelled `egw-data`, and the root partition is sized at build time and never grown. On a KVM host the disk file is created and formatted on the host as here; on a cloud VM a blank volume must be formatted once from inside the guest (`sudo mkfs.ext4 -L egw-data /dev/<blank-device>`, which is why that manifest adds `e2fsprogs-mke2fs`), and until then `docker.service` fails by design while boot and SSH continue.
- **Networking:** a real NIC with DHCP replaces slirp; no hostfwd; the simulator targets the VM's address, so the broker certificate needs `--host <address>` (or `EGW_HOST`) in `generate-dev-tls.sh`; 8080/8000 stay loopback-only and are still reached through `ssh -L`; a host firewall allowing only 22 and 8883 becomes necessary.
- **Identity and labelling:** `execution_mode` becomes `native-kvm` or `native-metal`; `sut_environment.json` records provider, region, instance type and the shared-vCPU caveat as the script already asks; `/proc/cpuinfo` shows the real core (Neoverse/Graviton `UNVERIFIED` part numbers); `qemu_version` is absent or refers to the host's QEMU under KVM.
- **What stays identical:** Sections 4-7 (controller archive, pulls by digest, identity verification, `.env`, TLS, auth, compose, first flow, the nine tests) run unchanged on the native guest; that is the point of doing them here first.
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
2. Size of the controller's `docker save` archive, and slirp transfer times under TCG for it and for the pull of the five external images (5.2a; 65 s observed for `mongo` alone).
3. Docker Desktop engine image store (containerd vs graphdriver) and whether the default builder attaches attestation manifests without `--provenance=false --sbom=false`; `scripts/build-controller-image.sh` and `scripts/verify-controller-image.sh` (4.1, 4.4) were exercised with a stub `docker` only, never against an engine, under Git Bash or under BusyBox ash (`src/tests/test_deployment_prebuilt_controller.py`, 35 cases, of which 28 run the two scripts under `dash` and `bash` on Linux). Unrun against an engine, and therefore still `UNVERIFIED:` in their effect, are the build script's refusal of git-ignored files below a path the Dockerfile copies, its clean-up on `HUP`/`INT`/`TERM` (exit 129/130/143), and the verify script's comparison of the image's revision label and its refusal of a record from a dirty build context.
4. Compose 2.26.0 on the guest: `pull_policy: never` with the controller image loaded, `up -d` finding the five images pulled as `repo:tag@sha256:` without contacting the registry, and a `pull` limited to named services (5.2a, 5.5).
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
17. The ad-hoc reconciliation helper `egw_experiments.itest_reconcile` (6.1-6.5, tests 1-8) has been exercised only by its unit tests (`src/tests/test_experiments_itest_reconcile.py`: fakes for the controller, Ditto and the clock, the unmodified `compute_run_metrics`; in-window, on-deadline, late and missing confirmations; matching and mismatching counter deltas) and was never run against the real controller or Ditto. Unobserved: that `GET /metrics` through the SSH tunnel answers within the harness's marker timeout under TCG; the marker lag obtained with `; $REC mark` after a piped simulator command (harness tolerance 2 s); that the Ditto gateway answers 404 for an unknown thing through the tunnel.
18. That the controller's `time.monotonic_ns()` continues across a controller *container* restart (kernel `CLOCK_MONOTONIC`, no time namespace; reasoned, not observed — CONTRACTS words the guarantee per process). `$REC wait` fails loudly if the controller clock is seen going backwards.
19. `scripts/probe-acl.sh` (test 9(d)/(e)): parsed with `sh -n`, `dash -n` and `bash -n` and exercised only against mock `docker`/`mosquitto_*` stubs (argument plumbing and verdict logic, not broker or engine behaviour; 2026-09-18: 69 stubbed cases under dash and under bash — the 43 earlier ones with unchanged verdicts, 21 on the broker log collection (`--timestamps` refused by the stub → INCONCLUSIVE with the refusal text kept in `broker_logs.err`, and FAIL when a delivery was recorded as well; non-zero status with output that looks complete, empty output, a `--tail` window that no longer contains the anchor, no anchor, anchor twice, `grep` error, `broker.txt` shorter than the collection → INCONCLUSIVE; a saturated 400-line window that still contains the anchor → PASS; an incomplete collection together with a delivery, an accepted anonymous session or an accepted-session line → FAIL) and 5 on an evidence directory that cannot be written (created without permission → exit 2; made read-only during the run by the stub, as a non-root user → INCONCLUSIVE, or FAIL when a delivery had been recorded; verdict on the terminal only; a full disk was not simulated), and a 355-case matrix under dash, including anonymous rc 1/125/126/127/137/7/8/14/15/135, rc 5 with empty or different stderr, and exec error text on the **stdout** of the anonymous or of the unauthorised subscriber → INCONCLUSIVE; rc 0/27, a `c2dt/` delivery line or an accepted-session log line → FAIL; a subscriber that ended before P4 returned, or P4 returning later than `sub_start + window − 2 s` → INCONCLUSIVE); execution under BusyBox ash 1.36.1 and `docker compose exec -T -e KEY=VALUE` in Compose 2.26 are documented behaviour, not run. Three further assumptions are read in sources and not observed: that the engine writes exec start-up errors to the exec's stdout (moby v25.0.9 `api/server/router/container/exec.go`) — the verdict does not depend on it, since a non-empty stdout without a `c2dt/` line is inconclusive wherever the text came from; that `mosquitto_sub -v` prints every delivered message as `<topic> <payload>`, so that a delivery on `c2dt/#` always starts a line with `c2dt/`; and that rc 27 is returned only after `alarm(-W)` has fired (`client/sub_client.c`), on which the liveness bound `sub_start + window` rests. The liveness clock is `/proc/uptime` (whole seconds; assumed readable on the guest, with `date +%s` as fallback — the fallback was stub-tested on a copy of the script with the path replaced, not on a system without `/proc`). The anonymous pass criterion (rc 5 **and** `Connection error: Connection Refused: not authorised.`) is derived from the Mosquitto sources at tag v2.0.22, not observed; the exit codes that `docker compose exec` returns for its own failures are documented Docker behaviour, not observed here — the verdict does not depend on them, since anything that is not the expected refusal is inconclusive. The per-client "exactly one subscription line" criterion assumes the `log_type subscribe` line format `<client id> 1 c2dt/#` (sources, not observed) only; that the last 400 broker log lines cover the run is not assumed but checked against an anchor line read before the run, which relies on `docker compose logs --timestamps` giving the same text for the same line in two calls (documented Compose option, `UNVERIFIED:` on the guest; a failure of this check gives INCONCLUSIVE, never a pass). Poky's BusyBox defconfig has no `timeout` applet (`# CONFIG_TIMEOUT is not set`, verified), which is why the probe uses `mosquitto_sub -W`. The verdict logic is also covered by the executable cases of `src/tests/test_probe_acl_verdict.py` (94 cases under dash and bash with a stub `docker`, including a `.env` that the shell cannot read to its end, which must give exit 2 with nothing run); continuous integration runs them on Linux.
20. The guards and host-side helpers (conventions; 3.3, 4.4, 5.1, 5.2, 5.5, 5.7; the helper file of 6.1; Sections 6 and 7), **none executed on the real host or guest**. What was done on 2026-09-18, on the workstation only: the helper file, extracted from this document, and every changed `host$` line were parsed with `bash -n` (bash 5.2) and exercised against stub `curl`, `python`, `scp` and `ssh` commands (80 assertions: `drained` with steady counters, with a counter that moves after two equal readings — the case the first version accepted —, with counters that keep moving, with a non-empty queue, with a changed `started_at`, with an unreachable and with a non-JSON `/metrics`; `run_test` with `/ready` 503, a refused `before` snapshot and an undrained controller — the simulator stub is never called —, with a simulator exit 1 — `mark` is the next call and the status is non-zero —, with a failing `mark`, `check` exit 3, `delta` exit 4 and a failing fetch followed by `finish`; the loop of test 1 and the guarded lines of 6.2 and tests 4, 6, 7, 8 and 9(d), taken verbatim, with a failing precondition — no simulator, harness, fault-injection, reboot or probe call is made). The guest lines of 4.4, 5.1 and 5.5 were parsed and run under `dash` with a stub `docker`; **BusyBox ash was not available** and remains untested (constructs used: `if`/`while read`/`$(( ))`/`grep -q`, no bashism). A third pass on 2026-09-18 (same workstation; Git Bash bash 5.2.37, GNU grep 3.0, native Python 3.14; 188 assertions, again stubs for `curl`, `python`, `scp`, `ssh`, `pgrep`, `ss` and shortened `sleep`s) re-tested every helper and `host$` line changed after the adversarial review, the lines taken verbatim from this document: `metrics` write-once and atomic (an existing file is kept byte for byte; a failed or non-JSON answer leaves no file and no `.tmp`); `snap_pair` (a failed twin snapshot sets the `/metrics` reading aside); `keep`; `pre` on a reused run id (stops before any `curl`, no drain wait, earlier `metrics.before.json` untouched); `accounted` with M = N, M < N (stops before the `after` snapshots; a later `finish` succeeds; a further `finish` keeps the pair), a permanent shortfall with `ACCEPT_UNACCOUNTED=1`, M > N, a changed `started_at`, a non-empty queue, an unreachable `/metrics`, missing inputs, and a published id without event record; test 4 in the two traces of the review (first run `FAILED` with `delta` exit 4; re-execution over the artefacts of an earlier execution) plus an unset `T4`, a replay line pasted twice and a failing replay simulator — in none of them is a replay published, a saved copy overwritten or the `replay` label consumed; the `RT`-bound lines of tests 2, 3 (including their heredoc form) and 5; `T6`; the fault job of test 7 (no simulator process at +90 s, failed `start`); the test 9(d) lines after a failed precondition (the acceptance sentence is **not** printed), with a moved counter and with probe exit 3; 6.2-6.4 including a repeated 6.3; the 5.2 guard against the **real text of `src/deployment/.env.example` of the Windows working tree** (filled, unfilled, one empty password, missing file, failing `scp`; the first version of the guard printed `STOP` on the correctly filled file because of the comment on line 3 — the WSL clone's copy of the file was not read); 5.1 and 5.7 with a failing `scp`/`ssh`. Not covered even by stubs: `pgrep -f` against a real simulator command line (pattern `egw_simulator run .*--run-id <id>( |$)`), `wait` on the background fault job in an interactive shell with job control, tilde expansion of `B=~/...; A=~/...` on the host (standard bash), and the reconciliation of `accounted` against a real `/metrics` and real `sent_events.jsonl`/`events.jsonl`. Stubs prove the control flow only. Unknown until run: whether 900 s (`DRAIN_LIMIT_S`) suffice for a backlog under TCG and what the two 130 s quiet windows per run cost in practice; that `curl --max-time 30` is long enough for `/metrics` and `/ready` through the tunnel under TCG; `ssh -o ExitOnForwardFailure=yes` with `-f` on the host's OpenSSH (documented `ssh_config` option, not run); the behaviour of the simulator's own exit codes through `tee` (`PIPESTATUS`) on the real command; the pre-/post-replay copies (`keep`) and the side-by-side line of test 4 (the latter exercised only against two hand-written JSON files), and the fetch of `<run_id>.warmup/events.jsonl` for `delta --also` in test 6 (path derived from the controller's one-file-per-`run_id` rule in `events.py` and from `run.py`'s warm-up run id, not observed on a guest). A fourth pass on 2026-09-18 followed the project review of that day (four residual defects) and **supersedes the `accounted`, test 7 and tunnel cases listed above**, whose helpers were rewritten: the two helper files (`itest-helpers.sh`, the new `tunnel.sh`) and every changed `host$` line were again extracted verbatim from this document and run against stub `curl`, `python -m ...`, `ssh`, `scp`, `pgrep`, `ss` and shortened `sleep`s, under Git Bash (bash 5.2.37, Python 3.14; 178 assertions, the socket cases skipped) and, copied to `/tmp`, under WSL Ubuntu-24.04 (bash 5.2.21, Python 3.12.3; 186 assertions); still nothing on the real host or guest. Covered: `accounted` with the review's case (A accepted and then duplicate, B without record, counter movement equal to the published records — ends non-zero and names B), all identities logged, counters above the published records, a dropped message, `ACCEPT_UNACCOUNTED=1` (capture goes on, `finish` ends non-zero) and an unwritable `unaccounted.txt`, records without a usable or unique `message_id`, a non-empty queue, a changed `started_at` with and without a missing record, a malformed log, an unreachable `/metrics`; `sim_post` and the 6.2 line with a transcript that cannot be created (simulator not started), a `tee` that exits 1 and a simulator that exits non-zero; the evidence lines of 4.3, 4.4, 5.8, 6.3, 6.6 and tests 2, 5, 6 and 9 with a failing copy, `scp`, `ssh`, `tee` or an unwritable target; test 7 with stop/start both succeeding, `stop` failing, `start` failing, both failing, a `stop` that exits 0 without changing the state, an unreadable state, no simulator process, a non-zero `wait` status next to a clean `fault.txt`, `TERM` sent to the fault job, a failing `sim_post`, a failing `pre` and an unwritable `fault.txt` — `T7` is 0 in the first case only; the tunnel functions with a stub `ssh` (open, second open, close, close twice, a regular file at the socket path, a busy port, a failing open, a failing `-O exit`, a background process named `ssh -f -N ...` and a control socket at another path left untouched) and, under WSL only, a stale socket file and a missing one checked with the **real** OpenSSH 9.6 client (`-O check` exits 255, the stale file is removed). Not covered: `-M -S` opening a real master and `-O exit` closing it; the `INT`/`HUP` traps and `wait` in an interactive shell with job control (under Git Bash the `TERM` trap ran the recovery twice, harmless because `start` is idempotent; once under Linux); `svc_state` against a real `docker compose ps -aq` / `docker inspect`; and everything the earlier passes list as unknown. A fifth pass on 2026-09-18 (verification of the fourth; same method, 252 assertions under Git Bash with the socket cases skipped, 272 under WSL; still nothing on the real host or guest) covers what changed after it: `accounted` with a record of another `run_id`, with an outcome outside the four, without an `outcome` field and with a `sent_events.jsonl` of blank lines (non-zero in all four); 6.3 followed by 6.4 with `ACCEPT_UNACCOUNTED=1` (6.4 ends non-zero), without it and with all records logged; 6.5 with a failing `down`/`up`, an unchanged `started_at`, an unreadable `/metrics` (no snapshot in any of them) and a changed `started_at`; test 7 with a `/ready` poller that ended early and with `ready.txt` unwritable (`T7` not 0), and — in an **interactive** bash on a pty, with a stub `ssh` that reads its stdin — a line typed before the `stop` and during the outage (no stopped job, `T7` 0) and Ctrl-C during the outage (service restarted, poller left running: the clean-up sentence of test 7); test 8 with an unchanged, an unreadable and a changed boot id; the display line of test 9(d) with a missing file; the 5.5 broker-log line under `dash` with a stub `docker` (clean, `Warning`, failing, empty); `tunnel_down` with a live master and an `ssh -O check` that cannot run — stub text and, under WSL, the **real** OpenSSH 9.6 client with a broken `-F` file: the socket file is kept — and `tunnel_up` with an `ssh -M` that exits 0 without an answering master. Still not covered: the real OpenSSH client as a background job reading the terminal, `/proc/sys/kernel/random/boot_id` on the guest, and the wording `Connection refused` from any OpenSSH other than 9.6p1. A sixth pass on 2026-09-18 (independent cases, `src/tests/test_runbook_itest_helpers.py`: 64 cases, 13 positive and 51 negative, which read the tunnel file of 5.7, the helper file of 6.1 and the lines of 6.2–6.4 and tests 7, 8 and 9 verbatim from this document; WSL Ubuntu-24.04, non-interactive bash, stub `curl`, `python`, `ssh`, `scp`, `ss`, `sleep`; 64 passed, none expected to fail; still nothing on the real host or guest) found one wording defect, corrected here: `fault_recover` of test 7 printed `RECOVERY SHOWN` on the paths on which nothing had been stopped; it now reads the state before the `start` and prints that label only for `exited` → `running` (the verdict was not affected: `T7` was already `failed:...` on those paths). For LOG `#C030` the lines of 4.3, 4.4 and 5.2a and the interlock of 5.5 were rewritten for the pull-by-digest route, so the passes above no longer cover them; they were run once, verbatim, under WSL (bash; `dash` for the guest lines) against stub `ssh` and `docker` commands (21 assertions: matching, mismatching, dirty and missing identity record, a failing load, a new shell; wrong digest, absent image, wrong architecture and an empty lock file in 5.2a; an unverified controller image, a failing `validate-config.sh` and a tree without the verify script in 5.5 — no load and no `up -d` in the refused cases), and the sixth-pass module passed afterwards (64 cases) with `images.lock.env` in the lines of tests 7 and 9 that it reads. The changed lines of 3.5, 5.1 and 6.6 were not exercised; still nothing on the real host or guest. A seventh pass on 2026-09-18 followed the project review's findings on this pull request and covers the lines changed for them: the two clone lines and the `imagetools-*.txt` copy of 4.3, the verification line of 4.4 and the `tee` group of 5.2a were extracted verbatim from this document and run under WSL against stub `git`, `ssh` and `docker` commands (17 assertions, the guest group under `dash` **and** `bash`: clone at the record's commit, `HEAD` elsewhere, a dirty working tree, a failing `fetch`, a failing `checkout` and a missing identity record — `deploy_source_commit.txt` is written in the first case only, and the missing record stops before any `git` call; the cleanliness test carries the `src/yocto` exclusion; `imagetools-*.txt` present and absent; `verify-controller-image.sh` exit 0 and exit 1 — the transcript is written and printed in both; five matching digests, one wrong digest and an empty lock file — the verdict reaches the screen and `images-pull-identity.txt` in all three). One substitution was made for the guest paths (`/opt/egw` under a temporary directory, which is not writable here); nothing else was altered, and `src/tests/test_runbook_itest_helpers.py` passed afterwards under Linux (64 cases). That `git status --porcelain -- src` lists `src/yocto/build-integrated/` while the same command with `':(exclude)src/yocto'` lists nothing was observed once against a throw-away repository (git 2.43.0), not against the WSL clone. The changed lines of 6.6 were again not exercised.
21. The 130 s quiet window and the reconciliation by identity (Section 7). `/metrics` carries `received`, `in_progress` and `processing_errors` (ADR 0010) and, under ADR 0011, `mqtt_subscribed`, `mqtt_connection` and `unacked`; `_mline` evaluates the accounting identity of CONTRACTS §5 on every reading, and `queue_depth` excludes the message being processed, which `in_progress` shows. The quiet window of `drained` remains a **temporary precaution and not proof that processing has finished** (project review of 2026-09-18); no helper states that nothing is pending. In `finish`, `accounted` reconciles the run **by identity** — every record of `sent_events.jsonl` needs a record with the same `message_id`, this `run_id` and one of the four outcomes in the fetched `events.jsonl`; the counter movement is printed as a secondary figure and decides nothing — and it is itself unexecuted on the real stack (hand-written logs and a stub `curl` only). What it cannot do: tell a record that is still queued or in progress from one that ended without a record (dropped at a full queue, `service.py` lines 156-159; exception swallowed in `run()`, lines 175-181; message before the bridge has its loop, `mqtt.py` lines 191-193; never delivered by the broker) — both are named and both end non-zero, the operator decides with `ACCEPT_UNACCOUNTED=1`, and `finish` (or the 6.4 line) still ends non-zero; see a record written after the `fetch`; tell this execution's records from those of an earlier execution under the same run id (`pre` checks freshness on the host only); or say anything about work that does not belong to this run. That every simulator record carries a usable, unique `message_id`, and that a rejected invalid payload is logged under this run with that id, is read in the sources (`output.py` lines 20-29 and 70-76, `runner.py` line 381, `scenarios.py` lines 211-231, `service.py` lines 111-123 and 209, `events.py` lines 75-82), not observed. Unverified parts of the precaution: (a) that no message reaches the controller after the last reading of the window — rests on the operator's rule that nothing is publishing and on the three session fields of each reading, `mqtt_subscribed` true, `mqtt_connection` unchanged across the window and `unacked` 0 (under ADR 0011 the bridge asks the broker for a persistent session and acknowledges each delivery only after its outcome line is written), with the residual assumption, ASSUMED and not observed, that a broker with nothing in flight to a session that stays connected holds nothing queued for it (ADR 0011, condition C5); (b) that one message is in progress for at most 122.4 s — this is **not a bound**: `DEFAULT_TIMEOUT_S = 10.0` is httpx's per-phase timeout (connect/write/read/pool, 10 s each, sequential), so one attempt can last up to about 40 s without any trickling (realistically connect + read, about 20 s) and the per-phase sum for a first-contact message is 4 × (3 × 40 + 0.6) = 482.4 s, above the default `DRAIN_QUIET_S` of 130 s, which is kept for its cost and because a miss yields a false `MISMATCH`, never a false `OK` (`DRAIN_QUIET_S=490` covers the sum; a slowly trickling response can exceed even that); the figure also assumes `EGW_RETRY_MAX=3` and `EGW_RETRY_BACKOFF_MS=200` as the controller container actually receives them; (c) work inside Ditto/MongoDB after Ditto's 2xx. The check on a single reading is made by `_mline` on every reading of the window (Section 9 item 7; ADR 0010 and ADR 0011), and the window itself is kept unchanged (ADR 0011, condition C5); neither replaces the reconciliation by identity.
22. The build-and-boot record of 2026-09-18 referred to in the Status paragraph and in the `IMAGE_LINK_NAME` note of 3.3 is taken from `docs/reviews/2026-09-17-egw-image-audit.md` section 13. Its evidence (sealed afterwards in `docs/evidence/integrated-qemu/`) was not opened for this revision, and the `UNVERIFIED:` marks of Sections 1-3 and items 1-13 of this appendix were **not** revisited against it; nothing in Sections 4-9 is covered by it.
