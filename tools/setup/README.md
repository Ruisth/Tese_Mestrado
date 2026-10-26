# Demonstration on another PC (`tools/setup/`)

These scripts let someone else run the [demonstration](../../docs/demo.md) on their own Windows PC. They
receive two things: this repository and a **kit** (one ZIP file with its `.sha256`). They run one script
in an Ubuntu terminal. Then the menu `bash tools/demo/demo.sh`, or the manual commands of the
[main README](../../README.md), work with no other preparation.

| Script | Who runs it | What it does |
|---|---|---|
| [`make_demo_kit.sh`](make_demo_kit.sh) | the author, once | Builds the kit ZIP from the sanitised image package and the controller archive, after a secret scan |
| [`prepare_demo_host.sh`](prepare_demo_host.sh) | the other person, once | Prepares the PC from the kit and the clone. It can be run again safely |
| [`tests/offline_check.sh`](tests/offline_check.sh) | anyone | Offline checks of both scripts. It starts nothing |

## What the other PC needs

- **Windows 10 or 11 with WSL 2 and Ubuntu 24.04.** In a PowerShell opened as administrator, run
  `wsl --install -d Ubuntu-24.04` (this is the one admin step; Windows may ask for a restart). Then open
  Ubuntu and create the user it asks for.
- **Hardware virtualisation turned on** in the PC's firmware (BIOS/UEFI settings). Without it, WSL 2 does
  not install (error `0x80370102`).
- **16 GB of RAM in the PC.** The emulated gateway is given 8 GiB. By default WSL gets only half of the
  PC's memory, so on a 16 GB PC raise it: create `%UserProfile%\.wslconfig` with the two lines `[wsl2]`
  and `memory=12GB`, then run `wsl --shutdown` in PowerShell. The script warns below 12 GiB.
- **About 25 GB of free disk** in WSL.
- **Internet during the preparation.** It downloads Ubuntu packages, Terraform, Python packages and the
  Debian 13 image. The first start of each scenario also pulls five container images.
- **The repository on the Linux file system**, for example `git clone <repository URL> ~/egw` inside
  Ubuntu. Not under `/mnt/c` (or any other Windows drive), and not a copy checked out by Git for Windows
  (Windows line endings break the scripts; the script refuses both). If the repository is private, you
  need access to it, or the author gives you a copy that you unpack inside Ubuntu.
- **A PC without its own comparison set-up.** The script refuses a WSL that already runs the comparison
  tools (the `EGW_*` settings, `~/egw-compare` without the script's marker, the measurement key
  `~/.ssh/egw_campaign` or `~/egw-exec`). It would otherwise take that set-up over. To try it on such a
  PC, use a separate WSL distribution (for example a `wsl --import` of a clean Ubuntu 24.04).

## What the kit holds

| In the ZIP (`egw-demo-kit-<date>/`) | What it is |
|---|---|
| `yoctoScarthgap/` | The shareable copy of the Yocto 5.0 (Scarthgap) gateway image of the comparison, unchanged. It was sanitised before it was shared: no stack configuration, no broker keys, no pilot evidence, new SSH host keys at first boot (see its `BUILDINFO.txt`) |
| `yoctoScarthgap/keys/egw_compare_share` | A **test** SSH key, the only key that copy of the image accepts. It is not the key of the measurements |
| `controller/` | The controller's container image for `linux/arm64` and its identity record |
| `SHA256SUMS`, `README.txt` | Checksums of every file; a short note |

The kit holds **no password**: the preparation script creates fresh ones on the PC. It does **not** hold
the sealed image used in the measurements, which keeps real passwords and keys, nor the `yoctowrynose`
image (that scenario is not available on a PC prepared with the kit).

## Prepare the PC

In an Ubuntu terminal, from the root of the clone:

```bash
bash tools/setup/prepare_demo_host.sh --kit /mnt/c/Users/<you>/Downloads/egw-demo-kit-<date>.zip
```

Keep the `.sha256` file next to the ZIP; it is checked. Keep both after the preparation too: a re-run
reads them again. `--dry-run` reports every step and changes nothing. `--no-debian` leaves out the
Debian 13 scenario (step 10). The script prints one line per step: `OK`, `SKIP` (already done), `WOULD`
(dry run) or `STOP: <reason>`. Run again after a stop: finished steps are skipped and nothing is changed
twice. `sudo` asks for your Ubuntu password once, for `apt-get`.

| Step | What it does |
|---|---|
| 1 host checks | WSL 2, Ubuntu 24.04, the clone on the Linux file system, not root, no comparison set-up of its own (see above); checks the ZIP against its `.sha256` and its layout; warns on memory and disk |
| 2 apt packages | Installs the packages below (waiting if another apt holds the lock); checks that QEMU offers the CPU and devices of the machine profile |
| 3 terraform | Terraform 1.16.6 into `~/egw-compare/bin`, checked against HashiCorp's `SHA256SUMS`; marks `~/egw-compare` as made by this script |
| 4 kit | Unpacks the ZIP to `~/egw-kit`, checks `SHA256SUMS`, converts the image to the raw ext4 file the `yocto` scenario reads, checks the controller archive |
| 5 ssh key | Installs the test key as `~/.ssh/egw_compare_share` (mode 600); never replaces a different key |
| 6 secrets file | Creates `~/.config/egw-demo/deployment.env` from `src/deployment/.env.example` with fresh random passwords (mode 600); never overwrites it and never prints a value |
| 7 python venv | `~/.local/share/egw-demo/venv` with the project installed from `src/` |
| 8 settings | Writes `~/.config/egw-demo/env.sh` (paths only) and one marked line that loads it in `~/.profile` (or in `~/.bash_profile` when that file exists) |
| 9 terraform init | `tf.sh yocto init` and `tf.sh debian13 init` |
| 10 debian 13 | Downloads the pinned Debian 13 image (checked against its published SHA512) and boots it once to install Docker, as [tools/compare](../compare/README.md) describes. Several minutes. Refused while another QEMU runs |
| 11 summary | The next commands |

Step 10 is optional. The image URL is pinned to one dated Debian build, which Debian may remove in time,
and the first boot must finish within 30 minutes (`EGW_COMPARE_FIRSTBOOT_LIMIT_S`, 1800 s) on your PC. If it
fails, run the script again with `--no-debian` to finish the preparation without the `debian13` scenario.

Ubuntu packages and why: `qemu-system-arm` (the `qemu-system-aarch64` emulator), `qemu-utils`
(`qemu-img`), `ipxe-qemu` (the option ROM QEMU loads for the virtio network card), `python3` and
`python3-venv` (the scripts' helpers, the seed server and the venv), `unzip` (the kit and Terraform),
`curl` and `ca-certificates` (downloads), `openssh-client` (`ssh`, `scp`, `ssh-keygen`), `e2fsprogs`
(`mkfs.ext4` and `debugfs` for the data disk and the Debian boot files), `iproute2` (`ss`, the port
guard), `procps` (`pgrep`, the one-guest guard) and `git` (the commit recorded in each manifest).

Then start the demonstration in a **new** Ubuntu terminal, so that the settings apply:

```bash
cd ~/egw
bash tools/demo/demo.sh                 # the menu
bash tools/compare/tf.sh yocto apply    # or start the Yocto gateway directly
```

The settings reach login shells only (a new Ubuntu terminal, or `bash -l`). In a terminal that is not a
login shell, such as some editor terminals or `wsl -e bash`, run `. ~/.config/egw-demo/env.sh` first.

The first `apply` of each scenario pulls the five pinned container images onto a fresh data disk and
loads the controller image, so it takes longer than later ones (about 10 minutes under emulation).

The demonstration starts the gateway with `tf.sh`. You do not need the kit's own
`yoctoScarthgap/run-linux.sh`: it starts a QEMU outside the guards of `tools/compare`, and while it runs
`tf.sh ... apply` and step 10 of the script refuse to start.

## Tested

On 2026-10-26, on the author's PC, in a new Ubuntu 24.04 WSL distribution with nothing else installed
(31 GiB of memory for WSL), from a clone of this repository and the kit `egw-demo-kit-20261026`:

| What | Result |
|---|---|
| The preparation | 11 of 11 steps OK in 8.5 minutes, Debian 13 included |
| First `tf.sh yocto apply` | ssh after 17 s; `ENVIRONMENT READY` after 5 min 49 s |
| Demonstration on Yocto | 3 wearables for 60 s: 135 messages sent, 135 seen by the MQTT observer, the 3 twins updated by the run; menu options 3, 6 and 8 |
| First `tf.sh debian13 apply` | ssh after 40 s; `ENVIRONMENT READY` after 9 min 3 s |
| Demonstration on Debian 13 | the same: 135 sent, 135 seen, 3 twins updated |
| Power-off | both gateways by `ssh-poweroff`; no QEMU process left |
| A second run of the script | steps 2 to 10 `SKIP` in 2 s; no file changed |

Not tested: a 16 GB PC with the `.wslconfig` limit above, and an Ubuntu user whose `sudo` asks for a
password (the script then asks for it once).

## Limits

- **A demonstration, not a reproduction of the measurements.** The PC uses Ubuntu 24.04's QEMU 8.2.x. The
  recorded measurements used QEMU 8.2.7 from the Yocto build. The kit's image is the sanitised copy, so
  the base `sha256` recorded in each manifest differs from the measured one, and the scenario's own notes
  (`tools/compare/scenarios/yocto.env`) still describe the author's base.
- **One gateway at a time**, as everywhere in [tools/compare](../compare/README.md).
- The demonstration measures nothing; see [docs/demo.md](../../docs/demo.md).

## Where things are written

| Path | Contents |
|---|---|
| `~/egw-kit/egw-demo-kit-<date>/` | The unpacked kit, and `deploy/` with the converted image and kernel |
| `~/egw-compare/` | Terraform, its state, the scenarios' disks, logs and results (`EGW_COMPARE_ROOT`); `.egw-demo-host` marks it as made by the script |
| `~/.config/egw-demo/` | `env.sh` (settings) and `deployment.env` (passwords, mode 600) |
| `~/.local/share/egw-demo/venv/` | The Python virtual environment |
| `~/.local/state/egw-demo/setup/` | Transcripts of apt, the downloads, pip, Terraform and the Debian preparation |
| `~/.ssh/egw_compare_share`, `.pub` | The test key |

Inside the clone the script creates only `tools/compare/terraform/.terraform/` and `src/egw.egg-info/`;
git ignores both. (Running the demonstration later also writes `__pycache__/` folders, also ignored.) To
undo: power every guest off (`tf.sh <s> stop`), remove the folders above, the test key and the marked
line in the profile. The Ubuntu packages stay installed.

## Build the kit (author)

On the author's WSL host, with the sanitised package and the controller archive:

```bash
bash tools/setup/make_demo_kit.sh --package <sanitised yoctoScarthgap folder> --out <folder> \
    [--images ~/egw-images] [--date YYYYMMDD] [--qemu-img <path>]
```

It writes `egw-demo-kit-<date>.zip` and `egw-demo-kit-<date>.zip.sha256`. Before zipping, it verifies the
package's `SHA256SUMS`, its record of a clean secret scan, the test key's two halves and the controller
archive against its identity record. It then scans every file, the image layers (compressed members are
opened; one it cannot open, such as zstd, refuses the kit) and every disk image of the package, read
through `qemu-img`: the root file system and the data disk, which must be an empty ext4. It looks for
`.env` files, private keys other than the test key and password assignments. Any hit refuses the kit,
and no matched text is printed. A package that lists an `.ext4` or `rootfs` file (the sealed image) is
refused.

## Offline check

```bash
bash tools/setup/tests/offline_check.sh
```

It uses stubs for QEMU, `qemu-img`, `sudo`, `apt-get`, `curl`, `findmnt`, `tf.sh` and `compare_env.sh`, a
stand-in clone and a throw-away `HOME`. Its last section sources the settings it writes into the real
`tools/compare/lib.sh` and `tools/demo/lib.sh`, so a renamed variable on either side fails it. It needs
`bash`, `python3`, `unzip`, `ssh-keygen` and `e2fsprogs` (`mkfs.ext4 -d`, `debugfs`), and runs
`shellcheck` when installed. It needs no network, no `sudo` and no guest.
