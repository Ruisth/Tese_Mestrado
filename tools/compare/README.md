# Comparison environments — the Yocto image and Debian 13 under one QEMU/TCG profile

## 0. Two commands per scenario

The scripts are the files of this folder, `tools/compare/` in the repository;
on the WSL host they run from a checkout such as `~/egw-exec/compare-repo`, and everything they create lives
under `$EGW_COMPARE_ROOT` (default `~/egw-compare`, section 2). From the root
of the clone, in a WSL login shell, one scenario at a time:

```bash
bash tools/compare/tf.sh yocto apply      # up: prepare if absent, boot, ssh, stack up, healthy; stays running
bash tools/compare/tf.sh yocto stop       # down: stack stop, power-off, QEMU confirmed ended; disks and logs kept
bash tools/compare/tf.sh debian13 apply   # the same for Debian 13, only after yocto is off (one guest at a time)
bash tools/compare/tf.sh debian13 stop
```

A third scenario, `yoctowrynose`, boots the yoctoWrynose image (Yocto Project 6.0.3, a UEFI disk) with the same
two commands, for demonstration and functional use; it is not part of the measured comparison (section 11).

`apply` runs, with no prompt, the whole sequence of [`up.sh`](up.sh):
(1) work copies prepared if absent (`compare_env.sh prepare`); (2) the guest
booted under QEMU/TCG with the fixed machine profile of section 6; (3) ssh
awaited, up to 450 s; (4) the stack prepared where needed, reusing the pinned
images and the configuration already on the data disk (`provision_stack.sh`,
idempotent by markers); (5) Mosquitto, MongoDB, Ditto and the controller
started; (6) six services `healthy` and the controller's `/ready` confirmed;
(7) `ENVIRONMENT READY` reported and the guest left running. Repeating
`apply` on a running environment starts no second process and reinstalls
nothing: Terraform finds nothing to change. A failure is reported with its
exit code and the guest is left running for inspection; `stop` closes it.
Neither command removes a disk. `stop` stops the stack (`compose stop -t 60`),
powers the guest off, confirms the QEMU process ended and keeps disks,
configuration and logs. Transcripts: `scenarios/<s>/logs/up-<stamp>.log`,
`stop-<stamp>.log`, `provision-<stamp>.log`, `console-<stamp>.log`; the live
state at any moment: `bash tools/compare/tf.sh <s> status`. The validation
result of each scenario is in section 9.

## 1. Purpose and status

This folder prepares, starts, stops and removes two isolated ARM64 guests under
the **same** emulated machine: `yocto`, the project's `egw-gateway-image` as the
pilot sessions booted it, and `debian13`, a dated Debian 13 genericcloud image
provisioned once for the same application stack. One bash CLI
(`compare_env.sh`) owns the lifecycle; a thin Terraform module records the
desired state and reads the live one; `provision_stack.sh`,
`functional_check.sh` and `validate.sh` bring the stack up, push one synthetic
event to its twin and record the result.

What it is **not**: the lifecycle commands of sections 0–5 measure nothing and
claim nothing. The measured comparison is the separate procedure of section 10,
executed once as series a02 on 2026-10-18/19
([`docs/results.md`](../../docs/results.md), R9). [`PROTOCOL.md`](PROTOCOL.md)
is the earlier proposal and was not executed as written; its pilot figures are
planning inputs and are not citable. Section 9 records the validations of
2026-10-18.

## 2. Layout on disk

Everything lives under `$EGW_COMPARE_ROOT` (default `~/egw-compare`), outside
the clone and outside the pilot's directories (`~/egw-tcg`, `~/egw-exec`,
`~/yocto`), which these scripts never write to.

| Path | Holds | Lifetime |
|---|---|---|
| `base/<scenario>/` | immutable base copies, mode 0444, each listed in `SHA256SUMS` — `yocto`: `Image`, `rootfs.ext4`; `debian13`: the downloaded `.qcow2`, `vmlinuz`, `initrd.img`, `root-uuid.txt`, `partitions.txt`, `boot-files.sha256`, `prepared.qcow2` | preserved; verified with `sha256sum -c` at every `prepare` and `start` (a changed base is exit 3) |
| `scenarios/<s>/disks/` | `<image>.rootfs.qcow2` (overlay on the base, named after the base image so the harness identifies the rootfs drive), `data.img` (32 GiB raw ext4, label `egw-data`), `firstboot.qcow2` (Debian, transient) | disposable: removed by `destroy` |
| `scenarios/<s>/state/` | `qemu.pid`, `monitor.sock`, `known_hosts` (the guest's pinned host key), `argv.txt`, `started` (host uptime), `started_utc`, `console` (path), `seed/` (Debian), `ca.crt`, `provision.json` | removed by `destroy`, after copying `argv.txt`, `started*`, `provision.json` and the manifest to `results/destroy-<stamp>/` |
| `scenarios/<s>/logs/` | `lifecycle.log`, `console-<stamp>.log`, `start-`, `stop-`, `provision-<stamp>.log`, `firstboot-*` | preserved |
| `scenarios/<s>/results/` | `validate-<stamp>/` (with `SHA256SUMS`), `functional-*`, `destroy-<stamp>/` | preserved |
| `scenarios/<s>/manifest.json` | the scenario's identity: base paths and sha256, QEMU path/version/sha256, machine arguments, disks, host, repository commit, script hashes | written by the first `prepare` and rewritten by any `prepare` that (re)creates the work disks (for example after a `destroy`); kept by `destroy`, with a copy under `results/destroy-<stamp>/` |
| `lock/active/holder` | the one-guest lock; content = the scenario that holds the profile's ports | released by `stop`/`destroy`; a stale lock (holder without a pid file) is taken over |
| `tfstate/<scenario>/terraform.tfstate` | Terraform state, one workspace per scenario (local backend, `workspace_dir`) | preserved |
| `bin/terraform`, `plugin-cache/` | the pinned Terraform binary; `TF_PLUGIN_CACHE_DIR` | preserved |

Inside the clone only `tools/compare/terraform/.terraform/` (provider binaries,
backend settings) appears; it is ignored by git. The lock file
`tools/compare/terraform/.terraform.lock.hcl` is the one generated file that
belongs in the repository (section 3).

## 3. Prerequisites

- WSL2 Ubuntu-24.04 host (the scripts use GNU userland, `/proc`, `ss`,
  `pgrep`), with `e2fsprogs` (`mkfs.ext4`, `debugfs`), `util-linux` (`blkid`),
  `python3`, `curl`, `unzip`, `ssh`/`scp`, `tar`.
- QEMU 8.2.7 from poky's `qemu-helper-native` sysroot:
  `~/yocto/egw/src/yocto/build-integrated/tmp/work/x86_64-linux/qemu-helper-native/1.0/recipe-sysroot-native/usr/bin/qemu-system-aarch64`
  (sha256 `5d389c65…`, recorded in each manifest) and its sibling `qemu-img`
  — overridable with `EGW_COMPARE_QEMU` / `EGW_COMPARE_QEMU_IMG`.
- The Yocto deploy directory of the integrated build (`EGW_YOCTO_DEPLOY`,
  default `~/yocto/egw/src/yocto/build-integrated/tmp/deploy/images/qemuarm64`)
  with `Image` and `egw-gateway-image-qemuarm64.rootfs-20260918120819.ext4`.
- The operator key pair `~/.ssh/egw_campaign` and `~/.ssh/egw_campaign.pub`
  (`EGW_COMPARE_SSH_KEY`); the Debian seed carries the public half only.
- For the stack: `~/egw-tcg/.env` with the four passwords set
  (`EGW_COMPARE_SECRETS_ENV`), `~/egw-images/egw-controller-0.1.0-arm64.tar`
  and its `.identity.txt` (`EGW_IMAGES_DIR`), and the virtual environment
  `~/egw-exec/venv` with the project installed (`import egw_simulator` must
  work; `EGW_EXEC_VENV`).
- No pilot session open (`~/egw-exec/current_session` absent), no other
  `qemu-system-aarch64` running, host ports 2222 and 8883 free.

### Terraform 1.16.6, installed to `$EGW_COMPARE_ROOT/bin/terraform`

The archive, the two providers and the Debian image are downloads; they run
only under an authorised download.

```bash
mkdir -p ~/egw-compare/bin && cd ~/egw-compare/bin
curl -fLO https://releases.hashicorp.com/terraform/1.16.6/terraform_1.16.6_linux_amd64.zip
curl -fLO https://releases.hashicorp.com/terraform/1.16.6/terraform_1.16.6_SHA256SUMS
grep ' terraform_1.16.6_linux_amd64.zip$' terraform_1.16.6_SHA256SUMS | sha256sum -c -
# expected: terraform_1.16.6_linux_amd64.zip: OK
#           (sha256 38034b38d03096399a7a1264a14561a8029b2b496fd1f169452656e53968f1b7)
unzip -o terraform_1.16.6_linux_amd64.zip terraform && chmod 0755 terraform && ./terraform version
```

`tf.sh` uses `EGW_COMPARE_TERRAFORM`, else `$EGW_COMPARE_ROOT/bin/terraform`,
else `terraform` on `PATH`.

### `init` and the provider lock

```bash
cd <clone>
bash tools/compare/tf.sh yocto init        # downloads hashicorp/local 2.9.1 and hashicorp/external 2.4.2,
                                           # state under ~/egw-compare/tfstate, selects workspace `yocto`
~/egw-compare/bin/terraform -chdir=tools/compare/terraform providers lock \
    -platform=linux_amd64 -platform=linux_arm64 -platform=darwin_arm64 \
    -platform=darwin_amd64 -platform=windows_amd64
```

`providers lock` writes `tools/compare/terraform/.terraform.lock.hcl` with the
checksums of both providers for the five platforms; that file is committed so
that every later `init` verifies the same bytes. A tree without it means this
step has not been done yet. `init` is per clone; the `debian13` workspace is
created by the first `tf.sh debian13 plan|apply` (`workspace select -or-create`).
Changing `EGW_COMPARE_ROOT` afterwards needs `tf.sh <scenario> init -reconfigure`.

## 4. Commands

Through Terraform (`apply` and `stop` run without a prompt; `destroy` asks for
confirmation unless `EGW_COMPARE_AUTO_APPROVE=1`; `init` runs by itself the
first time; any further arguments go to Terraform):

```bash
bash tools/compare/tf.sh <yocto|debian13> plan      # what apply would do
bash tools/compare/tf.sh <s> apply                  # prepare (idempotent) + up.sh: start, ssh, stack up, healthy; stays running
bash tools/compare/tf.sh <s> status                 # compare_env.sh status: the LIVE state, one JSON object
bash tools/compare/tf.sh <s> output                 # terraform output -json of that workspace
bash tools/compare/tf.sh <s> stop                   # apply -var desired_state=stopped: stack stop, power-off, QEMU ended
bash tools/compare/tf.sh <s> destroy                # controlled stop, then remove work disks and state only
bash tools/compare/tf.sh <s> apply -replace='terraform_data.power[0]'   # restart a guest that ended on its own
```

The same by hand (what Terraform calls; `s` = `yocto` or `debian13`):

```bash
bash tools/compare/compare_env.sh prepare  <s>   # 0 prepared or already prepared; 2 prerequisite; 3 integrity
bash tools/compare/compare_env.sh start    <s>   # 0 running or already running; 2 refused by a guard; 5 failed
bash tools/compare/up.sh <s>                     # what apply runs: start, wait for ssh, provision_stack.sh, healthy; 0 ready, 1 not ready in time, 2 refused, 3 step failed, 5 QEMU failed
bash tools/compare/compare_env.sh status   <s>   # always 0; JSON of strings (section 5)
bash tools/compare/compare_env.sh stop     <s>   # 0 stopped or not running; 5 still running (nothing killed)
bash tools/compare/compare_env.sh destroy  <s>   # 0 removed; 5 refused while running
bash tools/compare/compare_env.sh manifest <s>   # prints the manifest path
```

**Debian base, first `prepare` only.** The image
`debian-13-genericcloud-arm64-20261017-2634.qcow2` is fetched from
`cloud.debian.org` and checked against its published SHA512 only when
`EGW_COMPARE_ALLOW_DOWNLOAD=1` is set (an authorised download); without it
`prepare debian13` stops at exit 2 and names the URL. Then `debian/extract_boot.sh`
takes `vmlinuz`, `initrd.img` and the root UUID out of the image with `qemu-img`,
a GPT parser and `debugfs` (no root, nothing mounted), and the **provisioning
first boot** runs: the seed rendered by `debian/render_seed.py`
(`user-data`, `meta-data`, `vendor-data`) is served from `127.0.0.1:8099`
(`EGW_COMPARE_SEED_PORT`; the guest reaches it as `http://10.0.2.2:8099/` through
slirp, `ds=nocloud` on the kernel command line); QEMU runs in the foreground on a
throwaway overlay under `timeout 1800` (`EGW_COMPARE_FIRSTBOOT_LIMIT_S`), with
the same guards and lock as `start`. cloud-init creates the user `egw` (uid 1000,
key-only, sudo), installs `docker.io docker-compose docker-cli containerd runc
curl openssl ca-certificates e2fsprogs sudo` after `apt update` against the
image's own sources, mounts the data disk at `/var/lib/docker` with the image's
fstab line before docker's first start, writes the eight configuration files of
`egw-gateway-config`/`egw-base-config` byte for byte, masks `apt-daily` and
`apt-daily-upgrade`, records `dpkg-query -W` in `/etc/egw-buildinfo.packages`,
writes `/etc/cloud/cloud-init.disabled` and powers off.
`debian/firstboot_check.py` accepts the console log only when cloud-init's
completion line precedes `reboot: Power down` and no private-key material
appears; otherwise `prepare` exits 3 and **no** `prepared.qcow2` is written. On
success the overlay is flattened (`qemu-img convert`) into
`base/debian13/prepared.qcow2` (0444, sha256 in `SHA256SUMS`), and the work
overlay is created on it. The data disk attached to that first boot (where
Docker initialised `/var/lib/docker`) is discarded and a fresh `data.img` is
created, so both scenarios start their comparison from an empty data disk.

**The authorised functional sequence** (one attempt, no repetition, no load):

```bash
bash tools/compare/validate.sh <s>              # 0 pass; 1 a phase failed (guest closed); 2 not started; 5 close failed
bash tools/compare/validate.sh --resume <s>     # the same phases on a guest already running (no second boot)
```

Start a driver detached from the shell that launches it (`setsid nohup bash … &`),
otherwise it dies with that shell while the daemonised guest lives on.

Phases, each a numbered file under `scenarios/<s>/results/validate-<stamp>/`
(`steps.tsv` keeps rc and host-monotonic seconds): prerequisites →
`tf.sh apply` → ssh answers (≤ 450 s) and `systemctl is-system-running` in
`{running, degraded}` (≤ 240 s more, recorded, not fatal) → guest facts →
`provision_stack.sh` (a second, idempotent run that confirms the stack the
apply brought up) → SUT environment record → `functional_check.sh` →
final state and journal → `tf.sh stop` → own pid gone and no other QEMU →
`SHA256SUMS`. The close is attempted even after a failure; nothing is killed.

`provision_stack.sh <s>` runs the runbook's 5.1–5.6 over ssh with the
deployment's own POSIX scripts, idempotently (markers under
`/opt/egw/evidence/provision/`): guest facts (uid 1000, docker, compose,
`/var/lib/docker` on the `egw-data` label), deployment tree (content sha256),
`.env`, the five pinned images pulled and checked by `RepoDigests`, the
controller archive loaded and verified against its identity record, TLS, auth,
broker secrets with ACL, `validate-config.sh`, `up -d`, then six
`running/healthy` and `/ready` 200 within `EGW_COMPARE_HEALTH_LIMIT_S`
(1800 s). It writes `state/provision.json` (steps, `seconds_to_healthy`,
`seconds_to_ready`, host monotonic from `up -d`) and fetches `ca.crt`. Exit 0
healthy and ready; 1 up but not ready in time; 2 host prerequisites; 3 a step
failed. `functional_check.sh <s> <run-id> <seed>` opens an ssh master tunnel
(`state/tunnel.ctl`; host ports 8000 and 8080 must be free) to the guest's
loopback APIs, reads `/metrics`, publishes one message from one simulated
smartwatch over TLS on 8883 (`egw_simulator`, smoke scenario, QoS 1), waits up
to `EGW_COMPARE_ACCEPT_LIMIT_S` (120 s) for `accepted` to grow by one, reads the
twin `org.c2dta:<device_uuid>` back from Ditto and requires the run id at
`features.ingestion.properties.last_run_id`. Records go to
`results/functional-<stamp>-<run-id>/` (`metrics.before/after.json`,
`sim/<run-id>/sent_events.jsonl`, `twin.json`, `check.json`, `functional.log`);
exit 0 pass, 1 fail, 2 prerequisite. It is a reachability check, not a slice
pass in the project's sense.

## 5. What Terraform does and does not do

- **Desired versus live.** Terraform records the desire: `terraform_data.prepared`
  (input = scenario, hashes of the scenario file, `compare_env.sh` and `lib.sh`;
  create → `prepare`; destroy-time → `destroy`; replaced only when the scenario
  or its `.env` file changes) and `terraform_data.power` (`count` = 1 when
  `desired_state = running`; create → `start`; destroy-time → `stop`). The live
  state is **read, never inferred**: `data.external.status` runs
  `compare_env.sh status` after the power step, and its JSON — `scenario`,
  `prepared`, `running`, `pid`, `lock_holder`, `started_uptime_s`, `root_disk`,
  `data_disk`, `base_sha256`, `manifest`, `console`, `last_provision` (the
  result of the last provisioning run on this scenario), all strings — is the
  `status` output. `running` is true only when the pid file names a live
  process (a zombie counts as gone) whose command line is a
  `qemu-system-aarch64` carrying this scenario's pid-file path — a pid reused
  by another QEMU is never claimed.
- **`check "live_state_matches_desired"`** re-reads `status` at plan and apply
  and emits a **warning** (never an error) when the live state disagrees: a
  guest that ended on its own, or one started by hand. Terraform does not
  detect such a guest otherwise; `apply -replace='terraform_data.power[0]'`
  (stop, which returns 0 when nothing runs, then start) restores agreement.
- **Second `apply` = no-op.** With nothing changed no resource is created or
  destroyed and no provisioner runs; only the data sources are re-read. Editing
  a script changes the recorded input in place and runs nothing; it never
  destroys disks.
- **A failed `apply`** (no ssh within 450 s, a provisioning step failed, the
  stack not healthy within its limit) leaves the power resource tainted and
  the guest running for inspection: nothing is killed, no disk is touched.
  `stop` closes it; the next `apply` runs the controlled stop and `up.sh`
  again, and the markers on the data disk make the provisioning skip what is
  already done.
- **`stop`** (`desired_state = stopped`) destroys only the power resource:
  stack `compose stop -t 60` where a deployment exists, `sync; sudo poweroff`
  over ssh, else `system_powerdown` through the monitor socket, then a wait of
  `EGW_COMPARE_STOP_WAIT_S` (180 s) on the host's monotonic clock. Disks,
  results and the manifest stay.
- **A failed stop** is exit 5: the pid file and the lock are kept, `logs/stop-<stamp>.log`
  says what was tried, **no QEMU process is ever killed**, the Terraform apply
  fails and the resource stays in state (the state stays honest). The operator
  inspects the console and decides.
- **`destroy`** stops first (same rules), then `compare_env.sh destroy`, which
  removes only `disks/` and `state/` and refuses (exit 5, nothing removed)
  while the guest runs. Bases, `logs/`, `results/` and `manifest.json` are
  untouched; `tfstate/` keeps the (now empty) workspace.
- **One guest at a time** — `start` (and the Debian first boot) refuse with
  exit 2 when: `~/egw-exec/current_session` exists (a pilot session), any other
  `qemu-system-aarch64` runs (`pgrep`; an unanswerable `pgrep` also refuses),
  a listener sits on 2222 or 8883 (`ss -ltn`), or the lock is held by the other
  scenario with a live pid file. Nothing else is ever touched.
- `start` re-verifies every file in `base/<s>/SHA256SUMS` before booting; for
  `debian13` that is several GiB and takes a while.

## 6. Equal conditions and known differences

Equal for both scenarios (fixed in `lib.sh`/`compare_env.sh`, recorded in each
manifest and in `state/argv.txt`): the same QEMU binary and sha256; `-machine
virt -accel tcg -cpu cortex-a76 -smp 4 -m 8192`; `virtio-net-pci` with MAC
`52:54:00:12:35:02` and `-netdev user,…,hostfwd=tcp:127.0.0.1:2222-:22,hostfwd=tcp:127.0.0.1:8883-:8883`;
`virtio-rng-pci` from `/dev/urandom`; two `virtio-blk-pci` disks (root overlay,
32 GiB raw ext4 data disk labelled `egw-data`, mounted at `/var/lib/docker` by
the same fstab line); `virtio-gpu-pci` with `-display none`; serial to a file,
monitor on a Unix socket, `-no-reboot`; direct kernel boot (`-kernel`,
`-append`, no firmware); `mem=8192M`, `console=ttyAMA0`, `swiotlb=0`; user `egw`
uid 1000 with key-only ssh and the same eight configuration files; the same
deployment tree, `images.lock.env` digests, controller archive, limits and
secrets (`provision_stack.sh`); one guest at a time on the same host.

| Aspect | `yocto` | `debian13` |
|---|---|---|
| Base | the deploy `rootfs.ext4` **as it is on disk today** (booted read-write by the pilot sessions; sha256 recorded at copy time, which is not the build's) — a pristine rebuild is a Yocto build and is not authorised | official image 20261017-2634, SHA512-verified, then one cloud-init boot → `prepared.qcow2` (sha256 recorded) |
| Kernel / initrd | 6.6.142-yocto-standard, no initramfs | `linux-image-6.12.113+deb13-cloud-arm64` with its initrd (extracted) |
| Native boot path | direct kernel (as the pilot) | UEFI + GRUB; here direct kernel, recorded as a difference |
| Root device / disk | `root=/dev/vda`; raw ext4, no partition table, 2,621,364,224 bytes (2.44 GiB), 344 MiB used at first boot | `root=UUID=…`; 3.0 GiB GPT image (ESP + root), root grown by `cloud-initramfs-growroot` at first boot; used size to be read from `df` |
| Kernel command line | `root=/dev/vda rw mem=8192M ip=dhcp console=ttyAMA0 console=hvc0 swiotlb=0` | `root=UUID=<uuid> rw mem=8192M console=ttyAMA0 swiotlb=0` |
| Init | systemd 255.21 | systemd 257.13 |
| Userland | BusyBox 1.36.1 `ash`, glibc 2.39, 614 packages, no package manager | GNU coreutils, `dash`, glibc 2.41, apt (`apt update` at first boot, no snapshot pin); package count from `/etc/egw-buildinfo.packages` |
| Container engine | docker-moby 25.0.9, containerd 2.0.10, runc 1.1.14, Compose v2.26.0 | `docker.io 26.1.5+dfsg1-9+deb13u1`, `docker-compose 2.26.1-4`, Debian's containerd and runc (exact versions from the package manifest after the first boot) |
| OpenSSH | 9.6p1 | 10.0p1 |
| iptables | legacy xtables backend | nft backend |
| cloud-init | absent | 25.1.4, disabled after the first boot (`/etc/cloud/cloud-init.disabled`) |
| Timers | systemd's own only | `apt-daily*` masked; `e2scrub_all`, `fstrim`, `man-db`, `dpkg-db-backup`, `logrotate` left as shipped and listed in the guest facts |
| Configuration paths | `/usr/lib/tmpfiles.d`, `/usr/lib/systemd/system/docker.service.d` | the same bytes under `/etc` |
| Provenance file | `/etc/buildinfo` (image-buildinfo) | `/etc/egw-buildinfo` + `/etc/egw-buildinfo.packages` |

The Debian versions above were read from the trixie archive on 2026-10-18; the
guest's package manifest is the record. Every difference is recorded in the
manifests and the guest facts and must appear in the limitations of any
comparison that uses these environments.

## 7. Secrets

`~/egw-tcg/.env` is copied host → guest (`scp` to `/opt/egw/deployment/.env`,
mode 600). On the host, `provision_stack.sh` checks only that its four names
are assigned and carry no `CHANGE_ME` (no value is read), and
`functional_check.sh` sources it in a subshell to hand
`MOSQUITTO_SIMULATOR_PASSWORD` to the simulator through the environment
(`EGW_MQTT_PASSWORD`), never on a command line and never printed; the broker
passwords are derived **on the guest** (`generate-dev-auth.sh` with
`set -a; . ./.env`).
The seed holds the public key only (`render_seed.py` refuses a file with
`-----BEGIN`); `firstboot_check.py` fails the first boot if private-key
material reaches the console log. Manifests, `status`, `provision.json`, the
Terraform state (variables, paths, hashes, the status JSON) and every log carry
paths, hashes, versions and times, never a password or a key. Only `ca.crt`
leaves the guest. The Yocto base copy may carry whatever the pilot sessions left
on that root file system; it stays under `$EGW_COMPARE_ROOT` and nothing here
reads it.

## 8. Tests and static checks

```bash
cd src && python -m pytest tests/test_compare_env.py tests/test_compare_debian.py tests/test_compare_provision.py -q
```

All three run against stubs on a temporary `PATH` and say nothing about a real
guest. `test_compare_env.py` (the CLI as Terraform runs it) skips as a module on
`win32`, without `bash` or without Linux `/proc`; `test_compare_provision.py`
(`provision_stack.sh` and `functional_check.sh` with a stub ssh whose "guest" is
a fake root on this machine) skips as a module on `win32` or without `bash`;
`test_compare_debian.py` runs the seed renderer and the first-boot judge on any
platform and skips only its `extract_boot.sh` cases on `win32` or without
`bash`, `dd`, `od` and `sha256sum`. The shellcheck tests skip without
`shellcheck`; `test_terraform_fmt_check` skips without `terraform`;
`test_terraform_validate` needs `terraform` **and** `EGW_COMPARE_TF_INIT=1`
(its `init -backend=false` downloads the pinned providers).

```bash
git ls-files -z -- 'tools/compare/*.sh' | xargs -0 shellcheck --severity=error
terraform fmt -check -recursive tools/compare/terraform
terraform -chdir=tools/compare/terraform validate        # after init
python tools/ci/check_markdown_links.py
```

## 9. Validation records

One validation per scenario is authorised (the Debian provisioning first boot
declared separately). Each record names the `results/validate-<stamp>/`
directory, its `SHA256SUMS`, the manifest's `base_root_sha256`, and whether the
run was **real** (a guest booted on the host) or only **simulated** (the stub
tests of section 8). The rows below are the records of 2026-10-18: the three
runs under the first form of `apply` (start only; the validation driver then
provisioned), and the two runs **by the final commands** of section 0, in
which `apply` itself brought the stack up. Both final-command runs passed
every phase: the completion criterion — one distribution up with a working
stack and down again with two commands, no manual step between — holds for
both scenarios.

| Scenario | Boot | Configuration | Stack | Functional path | Close | Results dir / seal | Real or simulated |
|---|---|---|---|---|---|---|---|
| `yocto` — first form of `apply`, 1st attempt (2026-10-18 16:25–16:31Z) | pass: `tf.sh apply`, ssh in ~30 s, `is-system-running` = running, no failed unit | pass: 6.6.142-yocto-standard, 4 vCPU, `/var/lib/docker` on `/dev/vdb` ext4 31.2 G, Docker 25.0.9 | **not run**: the provisioning pre-check read an empty label through `findmnt -no LABEL` (a tooling defect, fixed afterwards: `lsblk`/`blkid` fallbacks) and stopped before the stack | not attempted | pass: `tf.sh stop`, QEMU ended, no other QEMU | `scenarios/yocto/results/validate-20261018T162515Z` (boot, facts; the driver was lost with its launching shell) and `validate-20261018T163102Z` (resumed on the same guest; `SHA256SUMS`); base `rootfs.ext4` sha256 `bd15040f…` | real (one boot) |
| `debian13` — first boot (2026-10-18 16:32:39–16:36:53Z) | pass: direct kernel boot of 6.12.113, cloud-init `init-local` at +25 s | pass: packages installed from the archive (docker.io 26.1.5, docker-compose 2.26.1, …), the eight files written, user `egw` uid 1000 | — | — | pass: `reboot: Power down` after `Cloud-init … finished`; one warning: `part-001: empty cloud config` (the empty `vendor-data`) | `scenarios/debian13/logs/firstboot-*`; `base/debian13/prepared.qcow2` sha256 `4b8a0fb6…` (1,881,604,096 bytes) | real |
| `debian13` — first form of `apply` (2026-10-18 16:37:48–16:47:44Z) | pass: `tf.sh apply`, ssh in 50 s, running, no failed unit | pass: 6.12.113+deb13-cloud-arm64, 4 vCPU, MemTotal 8,197,128 kB, `/var/lib/docker` on `/dev/vdb` ext4 31.2 G label `egw-data`, Docker 26.1.5+dfsg1, Compose 2.26.1-4, 356 packages, `apt-daily*` masked | pass: provisioned in 444 s (pull 118 s, controller load 53 s, `up -d` 166 s, six healthy at +211 s, `/ready` 200 at +222 s) | pass: one event accepted in 15.9 s, twin `features.ingestion.properties.last_run_id` = run id | pass: `tf.sh stop` in 54 s, QEMU ended, no other QEMU | `scenarios/debian13/results/validate-20261018T163748Z` (32 files, `SHA256SUMS` `cd10bf30…`) | real |
| `yocto` — **by the final commands** (2026-10-18 17:42:49–17:51:34Z, 525 s) | pass: `tf.sh yocto apply` ran prepare (nothing to recreate), start and `up.sh`: ssh in 22 s; first provisioning on this data disk — images 101 s, controller load 34 s, `up -d` 153 s, six healthy at +187 s, `/ready` 200 at +195 s; `ENVIRONMENT READY` 383 s after launch; `running`, no failed unit | pass: 6.6.142-yocto-standard, 4 vCPU, 8012 MiB, `/var/lib/docker` on `/dev/vdb` ext4 31.2 G (2.0 G used after the stack), Docker 25.0.9, Compose v2.26.0 | pass: the idempotent second run skipped every step by marker (the five images already verify), six healthy in 7 s, 53 s in all — a repeated `apply` reinstalls nothing | pass: one event (run `cmpval-yocto-20261018T175019Z`) accepted in 15.75 s, twin `last_run_id` = run id | pass: `tf.sh yocto stop` — `compose stop` exit 0, `sudo poweroff`, QEMU ended after 48 s, no other QEMU | `scenarios/yocto/results/validate-20261018T174249Z` (37 files, `SHA256SUMS` `dc9cb457…`) | real |
| `debian13` — **by the final commands** (2026-10-18 17:51:52–18:01:27Z, 575 s) | pass: `tf.sh debian13 apply` ran prepare (nothing to recreate), start and `up.sh`: ssh in 46 s; tree and the five images already on this data disk from the afternoon run (skipped by marker), controller image present; `up -d` 194 s, six healthy at +238 s, `/ready` 503 at +250 s then 200 at +270 s; `ENVIRONMENT READY` 376 s after launch; `running`, no failed unit | pass: 6.12.113+deb13-cloud-arm64, 4 vCPU, 8005 MiB, root `/dev/vda1` 2.8 G (1.5 G used), `/var/lib/docker` on `/dev/vdb` ext4 31.2 G label `egw-data` (2.0 G used after the stack), Docker 26.1.5+dfsg1, Compose 2.26.1-4, 356 packages | pass: every step skipped or already present (tree marker, the five images verify, controller image present), six healthy in 8.8 s, `/ready` in 13.1 s, 86 s in all | pass: one event (run `cmpval-debian13-20261018T175956Z`) accepted in 25.13 s, twin `last_run_id` = run id | pass: `tf.sh debian13 stop` — `compose stop` exit 0, `sudo poweroff`, QEMU ended after 51 s, no other QEMU | `scenarios/debian13/results/validate-20261018T175152Z` (36 files, `SHA256SUMS` `132c76a9…`) | real |

## 10. Minimal comparison — six measured executions

The order of 2026-10-18 (after PR #62): three pairs of executions, Yocto →
Debian, Debian → Yocto, Yocto → Debian, every metric collected in each, no
other campaign. Everything reuses the tools above and the project's harness;
the files under `measure_*` and `guest_meminfo_sampler.sh` are the minimal
instrumentation that was missing. Results are **exploratory** (n = 3 per
scenario, one QEMU/TCG profile): no statistical significance, no maximum
capacity, nothing about physical ARM.

```bash
# once per scenario, guest off: the measured base (fresh disks, stack installed by `apply`, closed by `stop`, copied + sha256)
bash tools/compare/measure_base.sh yocto
bash tools/compare/measure_base.sh debian13
# the plan: six nominal entries, one seed per pair (equal in both distributions), write-once
PYTHONPATH=src ~/egw-exec/venv/bin/python tools/compare/measure_plan.py write --out ~/egw-compare/measure/plan.json --seeds S1 S2 S3
# the six executions in the plan's order, then the harness analysis and the summary
bash tools/compare/measure_series.sh ~/egw-compare/measure/plan.json
# one execution by hand (the series calls exactly this)
bash tools/compare/measure_run.sh <scenario> <run-id> ~/egw-compare/measure/plan.working.json
```

Each execution (`measure_run.sh`, record under `measure/runs/<run-id>/`,
`timeline.json` + `SHA256SUMS`): disks restored from the measured base and
verified → `tf.sh <s> apply` (instants on the host monotonic clock: `launch`
immediately before the QEMU exec, first ssh success, six healthy, first
`/ready` 200; probe cadences recorded) → `functional_check.sh` with its own run
id `<run-id>.func` (instant of the confirmed twin) → 120 s at rest with the
whole-guest memory sampled at 1 Hz (`MemTotal − MemAvailable`), then
`df -P -k / /var/lib/docker` and the SUT environment record → the harness run
of the plan entry (frozen `nominal`: 120 s warm-up, 600 s at 11.2 msg/s, 60 s
confirmation; per-container collector; memory sampled meanwhile) → the
runbook's drain helper through `tools/session/proof_hook_drained.sh` (130 s
quiet, cap 900 s — reaching the cap is a result) → events after the drain,
final `/metrics` and guest state → `tf.sh <s> stop`, QEMU confirmed ended. A
result of the system (a drain at its cap, late or lost confirmations, a failed
harness verdict) is recorded and never stops the series; an instrumentation
failure preserves the data, closes the guest and stops it. Nothing is repeated
or replaced by a script.

Boot times are never the duration of `terraform apply`. Latency is the
controller's reception → Ditto confirmation. `lost` is "no confirmation within
the deadline", not definitive loss (the post-drain events file is kept).
Memory is the whole gateway guest. Virtual capacity, image file size and space
used in the guest are three different measures (`compare_env.sh disks`,
`host-disks-before-load.txt`, `df-before-load.txt`). The validations of
section 9 are not comparison results: their preparation differed.

Two calculation rules of `measure_summary.py`, after the first measured
execution showed the host wall clock stepping back 13 s inside a run:

- **The load window is delimited on monotonic clocks only.** Its duration is
  `finished_monotonic_ns − measured_started_monotonic_ns` of the harness
  manifest (host clock); its position on the guest clock comes from the
  controller marker the harness polls at the run end (`controller_marker`,
  guest `monotonic_ns` paired with the host instant, lag within tolerance),
  cross-checked against the message pairing `received_monotonic_ns −
  publish_monotonic_ns` over at least 100 identities (agreement within 1 s).
  Memory samples carry the guest's `/proc/uptime` and count only inside that
  window. Without a demonstrable correspondence the window and every metric
  that depends on it are left unavailable with the reason; nothing is filled
  with zero and 600 s is never assumed. UTC stamps are reported, never used.
- **Rates are estimates between two boundary samples.** The acceptance rate is
  the difference of the controller's cumulative `accepted` between the last
  metrics sample at or before each bound, both within 5 s of their bound, the
  file ordered by the guest's monotonic clock and the counter never
  decreasing; the covered span and both gaps are reported, and the figure is
  named an estimate between samples, not an exact count inside the window.
  The published rate is `sent_valid` over the monotonic load duration.

**Results of series a02 (2026-10-18 21:37Z – 2026-10-19 00:39Z, six valid
executions, plan `plan-a02.json` sha256 `94fc9691…`):**
[`docs/evidence/compare-a02/`](../../docs/evidence/compare-a02/README.md)
holds the table, the CSV and the JSON; the raw records are in the sealed
`output_test` package named there. The load, 11.2 msg/s, is the synthetic
load of the existing nominal scenario, inherited so that the executions are
reproducible and comparable; it is not a requirement, a target or a pass
threshold, and the figures describe the observed processing capacity under
the load tried, never a maximum capacity. Median of three, Yocto vs
Debian 13: boot to ssh 15.8 s vs 46.3 s; stack ready 241.3 s vs 322.3 s;
memory inside the window 1 922.7 vs 2 304.3 MiB; root filesystem 489 vs
1 458 MiB; observed acceptance rate 7.76 vs 4.95 msg/s (1.57×); confirmed by
the end-of-load marker + 60 s 4 426 vs 2 394 of 6 720 (1.85×), the rest
confirmed during the drain in the five executions whose post-drain log was
verified; controller latency p50 220 s vs 351 s over those confirmations only;
drain 344 s vs 668 s. In these emulated conditions the Yocto configuration
showed shorter start-up times, lower memory and disk use and a higher observed
acceptance rate than the Debian 13 configuration; exploratory, whole
configurations with different kernels and runtimes, nothing about maximum
capacity, physical ARM or an isolated effect of the distribution. The first
attempt (`cmp-p1-yocto`, invalid by instrumentation) and the two stops of the
series are recorded in the decision note; nothing was repeated.

## 11. Third scenario — `yoctowrynose` (UEFI disk, demonstration only)

`yoctowrynose` boots the yoctoWrynose image: Yocto Project 6.0.3 "Wrynose", MACHINE `genericarm64`, one GPT disk in
qcow2 (an EFI system partition with systemd-boot, the kernel and an initramfs, and an ext4 root). Its base kind,
`uefi-disk`, copies three files from the sealed image package (default `~/images/yoctoWrynose`, overridable with
`EGW_WRYNOSE_PACKAGE`) after checking the package's own `SHA256SUMS`: the disk, the edk2 firmware code and the
variable-store template. Each scenario boots a writable copy of the template (`disks/uefi-vars.fd`, removed by
`destroy`); QEMU receives the firmware as two pflash drives, the code read-only first, and no `-kernel`/`-append`:
the kernel command line is the one of the disk's systemd-boot entry. The machine profile, devices, ports, data disk,
provisioning and controlled stop are those of the other two scenarios. The image authorises its own test key
(`~/.ssh/egw_wrynose_share`, overridable with `EGW_WRYNOSE_SSH_KEY`); the scenario file sets it, so the other
scenarios keep the campaign key.

```bash
bash tools/compare/tf.sh yoctowrynose apply
bash tools/compare/tf.sh yoctowrynose stop
```

The first `apply` copies the bases and pulls the five pinned images onto a fresh data disk, so it takes longer than
the later ones (about 9 min against 6-7 min observed on 2026-10-20). Known differences are listed in
`scenarios/yoctowrynose.env` and recorded in the manifest; among them, the boot includes firmware and initramfs, so
its boot times are not comparable with series a02. The measured runs of section 10 remain `yocto` and `debian13`:
the harness identity check I1 needs a kernel passed by QEMU, and `measure_plan.py`/`measure_summary.py` know the
measured pair only.
