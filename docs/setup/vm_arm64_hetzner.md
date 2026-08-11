# ARM64 performance VM checklist (Hetzner CAX21 or equivalent)

Checklist to provision the temporary native-ARM64 VM used for the entire
experimental campaign (plan 5.1). This document gives instructions only; account
creation, payment and any console actions are performed by the student.

**Deadline (plan 8.1, G0):** VM created and `aarch64` access validated by
**10/08**. If the chosen provider cannot deliver on that day, switch provider or
region; if no VM exists by **12/08**, report the risk to the advisors.

**Role separation (plan 5.1, ADR 0001):** this VM is the performance platform.
QEMU on WSL2 is functional-only. During benchmarks the simulator runs OUTSIDE
this VM; the primary latency metric is measured inside the controller (MQTT
receive to Ditto ack), so the external link is not part of the gateway
processing measurement.

---

## 1. Instance selection

Target: **Hetzner Cloud CAX21** — 4 shared vCPU (Ampere, ARM64), 8 GB RAM,
80 GB NVMe disk — or an equivalent native-ARM64 instance from another provider
(4 vCPU / 8 GiB / >= 80 GB minimum per plan 5.1). Requirements:

- [ ] CPU is native ARM64 (`aarch64`) — no emulation of any kind.
- [ ] At least 4 vCPU and 8 GiB RAM (Ditto + MongoDB + Mosquitto + controller).
- [ ] At least 80 GB disk.
- [ ] OS image: **Ubuntu 24.04 LTS (arm64)**.
- [ ] Region: pick one close to you (e.g. Falkenstein/Nuremberg/Helsinki for
      Hetzner) and note that ARM (CAX) availability varies by region.
- [ ] SSH key uploaded at creation time (never password-only access).

Reference: https://www.hetzner.com/cloud/ (CAX line). Pricing is hourly with a
monthly cap; check the current price on the provider page — do not hardcode
prices into the thesis.

## 2. First-login validation and environment manifest

Immediately after first SSH login, capture the environment manifest. These exact
fields are required by plan 5.1 and go into every experiment `manifest.json`:

```bash
mkdir -p ~/manifest && cd ~/manifest
uname -a                | tee kernel.txt          # kernel
uname -m                | tee arch.txt            # MUST print: aarch64
lscpu                   | tee cpu.txt             # exposed CPU (e.g. Neoverse-N1)
cat /etc/os-release     | tee os.txt              # OS name/version
free -h                 | tee memory.txt
df -h /                 | tee disk.txt
date -u +%Y-%m-%dT%H:%M:%SZ | tee provisioned_at.txt
```

Record additionally (manually, in the same directory or in the run manifests):

- [ ] Provider (e.g. Hetzner Cloud) and instance type (e.g. CAX21).
- [ ] Region/datacenter (e.g. `fsn1`).
- [ ] **Shared-vCPU caveat:** CAX instances use shared vCPUs; performance can
      vary with neighbour load. This limitation must be recorded in the
      environment manifest and reported in the thesis (plan 5.1); mitigate by
      treating each run as the statistical unit and reporting dispersion across
      repeated runs (plan 7.3).
- [ ] `aarch64` validation output — this is the G0 gate evidence; copy
      `~/manifest/` into `experiments/results/` evidence and reference it in
      `PROGRESS.md`.

## 3. Basic hardening (before deploying anything)

SSH keys only, no root password login:

```bash
sudo adduser egw && sudo usermod -aG sudo egw
# copy your key to the new user, then:
sudo nano /etc/ssh/sshd_config
#   PasswordAuthentication no
#   PermitRootLogin no
sudo systemctl restart ssh
```

Firewall (ufw): allow SSH, and MQTT 8883 only from the machine that runs the
simulator; Ditto (8080) and the controller API (8000) stay bound to
localhost/the internal Docker network and are never exposed publicly
(CONTRACTS.md section 8):

```bash
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw allow OpenSSH
sudo ufw allow from <SIMULATOR_PUBLIC_IP> to any port 8883 proto tcp
sudo ufw enable
sudo ufw status verbose
```

Keep the base system patched:

```bash
sudo apt update && sudo apt upgrade -y
sudo apt install -y unattended-upgrades
```

Note: MQTT itself is TLS + username/password with no anonymous access
(CONTRACTS.md section 1); ufw is defence in depth, not a substitute.

## 4. Docker Engine on Ubuntu 24.04 arm64

Install Docker Engine + Compose plugin from the official Docker apt repository
(the `arm64` packages are selected automatically by `dpkg --print-architecture`):

```bash
sudo apt update
sudo apt install -y ca-certificates curl
sudo install -m 0755 -d /etc/apt/keyrings
sudo curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
sudo chmod a+r /etc/apt/keyrings/docker.asc
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] \
  https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo "$VERSION_CODENAME") stable" \
  | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
sudo apt update
sudo apt install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
sudo usermod -aG docker egw   # re-login afterwards
docker version && docker compose version
docker info | grep -i architecture   # expect aarch64
```

Verify every stack image is native `linux/arm64` and record digests before any
deployment (plan 4.3; claim C03):

```bash
docker manifest inspect eclipse/ditto-gateway:3.9.4 | grep -A3 arm64
# repeat for ditto-policies, ditto-things, eclipse-mosquitto, mongo, controller base
```

Pin the verified digests in `src/deployment/images.lock.env`.

## 5. During the campaign

- [ ] Freeze the VM: no package upgrades, no resizes, no snapshots restored
      between `exp-v1` (06/09) and `data-v1` (13/09).
- [ ] Collect per-container CPU/RAM at 1-second intervals in every timed run
      (plan 7.1); store under `experiments/results/raw/<run_id>/resources.csv`.
- [ ] Watch steal time (`top`, `%st`) — persistent high steal is the early
      signal of the shared-vCPU risk (risk R13 in `docs/g0/riscos.md`).
- [ ] Copy raw results + `SHA256SUMS` off the VM after every session (the VM is
      disposable; the data is not).

## 6. Teardown and cost notes

- The VM is temporary (plan 4.3): keep it only while needed for G1–G5 evidence
  and the official campaign; hourly billing means a stopped-but-not-deleted
  server may still incur charges (Hetzner bills allocated resources until the
  server is deleted) — **delete**, not just power off, when done.
- Before deletion:
  - [ ] All raw data, logs, manifests and checksums copied off and verified
        (`sha256sum -c SHA256SUMS`).
  - [ ] Environment manifest (`~/manifest/`) archived with the evidence.
  - [ ] Optionally take a final provider snapshot only if re-runs are plausible
        (snapshots are billed per GB; delete it after `data-v1` is confirmed).
- After `data-v1` (13/09) the raw data is immutable; if a defect forces re-runs,
  a new VM with the SAME recorded specification is provisioned and the affected
  conditions repeated (plan 8, G5 week rules).
