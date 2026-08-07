# WSL2 + Ubuntu 24.04 + Yocto Scarthgap setup guide

Step-by-step guide to prepare the Yocto build environment required for gate G1
(plan sections 5.1 and 8). Target: build `egw-image` for `qemuarm64` with Yocto
Project 5.0.x "Scarthgap" using a `kas` manifest, and boot it in QEMU.

**Hard rule (plan 5.1):** the Yocto build directory MUST live on the WSL2 Linux
ext4 filesystem (e.g. under `~/`), never on `/mnt/c` or `/mnt/d`, and never
inside the Nextcloud-synced workspace. NTFS-backed paths (`/mnt/*`) are slow and
break the build; Nextcloud sync corrupts intermediate artifacts.

---

## 1. Install Ubuntu 24.04 LTS on WSL2

From an elevated PowerShell on the Windows host:

```powershell
wsl --version                 # confirm WSL2 is available; update if needed:
wsl --update
wsl --list --online           # confirm "Ubuntu-24.04" is listed
wsl --install -d Ubuntu-24.04
```

Create the UNIX user when prompted. Then verify:

```powershell
wsl -l -v
# Ubuntu-24.04 must show VERSION 2
```

If it shows version 1: `wsl --set-version Ubuntu-24.04 2`.

Make it the default distribution (the initial state of this machine only had
`docker-desktop`):

```powershell
wsl --set-default Ubuntu-24.04
```

Inside the new distribution, confirm the release:

```bash
lsb_release -a       # Ubuntu 24.04.x LTS
uname -a             # WSL2 kernel
```

## 2. Disk-space sizing (>= 120 GB)

A Scarthgap build for `qemuarm64` (downloads + sstate-cache + `tmp/`) needs on
the order of 100 GB of working space; provision **at least 120 GB free** on the
drive that hosts the WSL2 virtual disk (usually `C:`). Check before building:

```powershell
# Windows: free space on the drive holding the WSL VHDX
Get-PSDrive C
```

```bash
# Inside WSL: free space seen by the distro
df -h ~
```

Notes:

- The WSL2 VHDX grows on demand (default limit 1 TB) but never shrinks
  automatically. Reclaim space after large deletions with
  `wsl --manage Ubuntu-24.04 --set-sparse true` (host PowerShell) or
  `Optimize-VHD` (requires Hyper-V tooling).
- Keep `downloads/` and `sstate-cache/` between builds (they make rebuilds fast);
  `tmp/` can be deleted to reclaim space (`rm -rf ~/yocto/build/tmp`).

## 3. `.wslconfig` memory and CPU advice

BitBake parallelism is memory-hungry; too little RAM causes OOM kills mid-build,
and WSL2's default is only a fraction of host RAM. Create/edit
`%UserProfile%\.wslconfig` on the Windows host:

```ini
[wsl2]
# Give the build as much RAM as the host can spare while leaving headroom for
# Windows (rule of thumb: host RAM minus 8 GB; never less than 8 GB for Yocto).
memory=16GB
# All host cores speed up BitBake; reduce if the host must stay responsive.
processors=8
swap=16GB
```

Adjust `memory`/`processors` to the actual host hardware. Apply with:

```powershell
wsl --shutdown
# then reopen the Ubuntu terminal
```

Verify inside WSL: `free -h` and `nproc`. If OOM still occurs, lower BitBake
parallelism in the build config (`BB_NUMBER_THREADS`, `PARALLEL_MAKE`) instead of
raising swap further.

## 4. Required apt packages for Yocto Scarthgap

Per the Scarthgap reference manual (Ubuntu/Debian essentials):

```bash
sudo apt update && sudo apt upgrade -y
sudo apt install -y build-essential chrpath cpio debianutils diffstat file gawk \
  gcc git iputils-ping libacl1 liblz4-tool locales python3 python3-git \
  python3-jinja2 python3-pexpect python3-pip python3-subunit socat texinfo \
  unzip wget xz-utils zstd
```

Configure a UTF-8 locale (BitBake refuses to run without one):

```bash
sudo locale-gen en_US.UTF-8
export LANG=en_US.UTF-8   # add to ~/.bashrc
```

Git identity (used by BitBake fetchers and for evidence commits):

```bash
git config --global user.name  "Rui Duarte"
git config --global user.email "ruimfduarte94@gmail.com"
```

## 5. Install kas

Ubuntu 24.04 pip is PEP 668 "externally managed"; use `pipx`:

```bash
sudo apt install -y pipx
pipx ensurepath
pipx install kas
# reopen the shell, then:
kas --version
```

(Alternative: `python3 -m venv ~/.venvs/kas && ~/.venvs/kas/bin/pip install kas`.)

## 6. Build layout on ext4

Sources of this repository stay in the Windows workspace; the Yocto build lives
entirely in the Linux home directory:

```bash
mkdir -p ~/yocto
cd ~/yocto
# Copy ONLY the kas manifest + meta-egw layer from the workspace (read via /mnt),
# or clone the project repo natively into ext4 — never build under /mnt/d:
git clone /mnt/d/Nextcloud/"Edge Gateway"/Claude egw   # local clone onto ext4
cd egw/src/yocto
```

Sanity check that you are on ext4 before any build:

```bash
df -T . | tail -1    # filesystem type must be ext4 (or ext4-backed), NOT 9p/drvfs
```

Run the build via kas (manifest file name per `src/yocto/`):

```bash
kas build kas-egw-qemuarm64.yml 2>&1 | tee ~/yocto/logs/kas-build-$(date -u +%Y%m%dT%H%M%SZ).log
```

The kas manifest pins Scarthgap (Yocto 5.0.19) layer revisions to exact
tags/commits (plan 4.3); never build from moving branch HEADs.

## 7. QEMU usage inside WSL2 (functional validation only)

QEMU is used exclusively for build/boot/systemd/network/OCI-runtime functional
validation — never for performance claims (plan 5.1). After a successful build:

```bash
# From the kas/poky environment shell:
kas shell kas-egw-qemuarm64.yml -c "runqemu qemuarm64 nographic slirp"
```

Notes:

- `nographic` keeps the serial console in the terminal; `slirp` uses user-mode
  networking, which needs no root/TAP setup inside WSL2.
- Exit QEMU with `Ctrl+A`, then `x`.
- Inside the guest, the G1 functional checks are:

```bash
systemctl is-system-running        # expect "running" (or "degraded" + justification)
ip addr                            # network interface up (slirp: 10.0.2.x)
ping -c 3 10.0.2.2                 # reach the host-side gateway
# OCI runtime check (runtime name per the image recipe, e.g. podman or docker):
podman run --rm docker.io/library/hello-world || docker run --rm hello-world
```

## 8. Capturing evidence for gate G1

G1 (16/08) requires: the image boots **twice** and executes a test container.
Record everything; unlogged runs do not count as evidence (plan section 1).

```bash
mkdir -p ~/yocto/logs
# Boot 1 — capture the full serial console including the in-guest checks:
kas shell kas-egw-qemuarm64.yml -c "runqemu qemuarm64 nographic slirp" \
  2>&1 | tee ~/yocto/logs/boot1.log
# Repeat for boot2.log.
```

Checksums and environment manifest:

```bash
cd ~/yocto/egw/src/yocto
sha256sum $(find . -name "*.rootfs*" -o -name "Image*" 2>/dev/null) \
  > ~/yocto/logs/SHA256SUMS 2>/dev/null || true
{ date -u +%Y-%m-%dT%H:%M:%SZ; uname -a; lsb_release -a; kas --version; \
  git -C ~/yocto/egw rev-parse HEAD; } > ~/yocto/logs/environment.txt 2>&1
```

Then copy `~/yocto/logs/` into the workspace evidence area, e.g.
`experiments/results/raw/g1-boot-01/logs/`, add a `manifest.json` (scenario,
commit, environment, timestamps) and reference it from `PROGRESS.md` and the
claim→evidence matrix (claims C01/C02 in `docs/claim_evidence_matrix.md`).

## 9. Troubleshooting quick list

- `bitbake: command not found` — always enter the environment through
  `kas shell`/`kas build`; do not source poky manually unless debugging.
- Locale errors (`Please use a locale setting which supports UTF-8`) — redo
  section 4 locale steps.
- `No space left on device` — check `df -h ~`; delete `tmp/`, keep
  `downloads/` + `sstate-cache/`; re-check the 120 GB budget.
- Extremely slow build — verify with `df -T .` you are NOT on `/mnt/*` (drvfs/9p).
- OOM / gcc killed — raise `.wslconfig` memory or lower `BB_NUMBER_THREADS` /
  `PARALLEL_MAKE`.
