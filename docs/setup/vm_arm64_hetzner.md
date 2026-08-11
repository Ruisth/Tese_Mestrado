# ARM64 measurement VM checklist (provider not yet secured)

Checklist to provision the temporary native-ARM64 instance used for the entire
experimental campaign (plan 5.1). This document gives instructions only; account
creation, payment and any console actions are performed by the student.

> **Status on 2026-08-12: the measurement VM DOES NOT EXIST.** Three providers
> failed on the same day (risk R28, materialised):
>
> | Provider | Outcome |
> |---|---|
> | Oracle Cloud | Home region fixed at registration, no Ampere capacity there, and a free account cannot subscribe to another region |
> | Hetzner Cloud | Every CAX (ARM) instance type unavailable — this is why `CAX21` is no longer the plan of record |
> | Azure for Students | Regions limited to five; quota `0 of 0` on every dedicated ARM family (`Dpsv5`/`Dpsv6`, `Dplsv5`/`Dplsv6`). Only the burstable B series is obtainable, and it is barred from measurement |
>
> **Deadline (plan 8.1, G0):** VM created and `aarch64` access validated by
> **2026-08-10** — that date passed with no VM, so the plan's own rule applies:
> the risk is reported formally to the advisors on **2026-08-12**. The VM must
> be operational before G2 (2026-08-23); it is the single blocking dependency
> for G2 onwards.

## 0. Platform model — three tiers (extends ADR 0001)

The unavailability of dedicated ARM64 forced a distinction between an
*integration* platform and a *measurement* platform. This document covers the
third row only.

| Role | Platform | Numbers in the thesis |
|---|---|---|
| Functional (OS/boot) | QEMU `qemuarm64` on WSL2 | **Never** (plan 5.1) — a QEMU result never supports a performance or security statement |
| ARM64 integration | A burstable ARM64 instance (Azure `B4pls_v2`) | **Never** — CPU-credit throttling would corrupt the load sweep and the saturation criterion (risk R29) |
| Measurement (RQ3) | A **dedicated** ARM64 instance | **Exclusively from here** |

During benchmarks the simulator runs OUTSIDE the measurement instance; the
primary latency metric is measured inside the controller (MQTT receive to Ditto
ack), so the external link is not part of the gateway processing measurement.

---

## 1. Instance selection

Target: a **dedicated** (non-burstable) native-ARM64 instance of
4 vCPU / 8 GiB RAM / >= 80 GB disk (plan 5.1). Current candidates, in order:

| Candidate | Notes |
|---|---|
| Azure `D4pls_v5` | Quota requested for the `DPLSv5` and `DPLSv6` families (Germany West Central, 4 vCPU). Usable only if the quota is granted |
| AWS `c6g.xlarge` | Fallback: 4 vCPU Graviton2, 8 GiB, dedicated; roughly 7 EUR for the whole campaign |

Barred as measurement platforms: `Bpsv2` and `t4g` (burstable, credit-throttled)
and anything emulated. Hetzner `CAX21` remains an acceptable specification if
capacity ever returns, but it is no longer the plan of record.

Requirements, whichever provider is used:

- [ ] CPU is native ARM64 (`aarch64`) — no emulation of any kind.
- [ ] Instance family is **dedicated**, not burstable (no CPU credits).
- [ ] At least 4 vCPU and 8 GiB RAM (Ditto + MongoDB + Mosquitto + controller).
- [ ] At least 80 GB disk.
- [ ] OS image: **Ubuntu 24.04 LTS (arm64)**.
- [ ] Region: one that actually has ARM capacity, preferably close to you; ARM
      availability varies by region and is the constraint that blocked this VM.
- [ ] SSH key uploaded at creation time (never password-only access).

Pricing is hourly on all three providers; check the current price on the
provider page — do not hardcode prices into the thesis.

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

- [ ] Provider and instance type (e.g. Azure `D4pls_v5`, AWS `c6g.xlarge`).
- [ ] Region/datacenter identifier as the provider names it.
- [ ] Whether the family is dedicated or burstable — a burstable instance
      invalidates every timed run taken on it.
- [ ] **Shared-vCPU caveat (provider-dependent):** some ARM instance types
      expose shared vCPUs, so performance can vary with neighbour load. Check
      what the chosen type actually provides and record it: where it applies,
      the limitation must appear in the environment manifest and be reported in
      the thesis (plan 5.1); mitigate by treating each run as the statistical
      unit and reporting dispersion across repeated runs (plan 7.3).
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
(CONTRACTS.md section 1); ufw is defence in depth, not a substitute. Providers
also have their own network layer (Azure NSG, AWS security group) — where one
exists, it is configured to the same rule set, not instead of ufw.

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

- [ ] Freeze the instance: no package upgrades, no resizes, no snapshots
      restored between `exp-v1` (2026-09-06) and `data-v1` (2026-09-13).
- [ ] Collect per-container CPU/RAM at 1-second intervals in every timed run
      (plan 7.1); store under `experiments/results/raw/<run_id>/resources.csv`.
- [ ] Watch steal time (`top`, `%st`) — persistent high steal is the early
      signal of the shared-vCPU risk (risk R13 in the G0 risk register).
- [ ] Confirm from `sut_environment.json` that the run really happened on the
      dedicated family: a timed run recorded on a burstable instance is
      excluded, not corrected (risk R29).
- [ ] Copy raw results + `SHA256SUMS` off the instance after every session (the
      instance is disposable; the data is not).

## 6. Teardown and cost notes

- The instance is temporary (plan 4.3): keep it only while needed for G1–G5
  evidence and the official campaign. Billing is hourly and, on every candidate
  provider, a stopped-but-not-deleted machine can still incur charges for the
  resources it holds (disk, reserved capacity, public IP) — **delete**, not just
  power off, when done.
- Before deletion:
  - [ ] All raw data, logs, manifests and checksums copied off and verified
        (`sha256sum -c SHA256SUMS`).
  - [ ] Environment manifest (`~/manifest/`) archived with the evidence.
  - [ ] Optionally take a final provider snapshot only if re-runs are plausible
        (snapshots are billed per GB; delete it after `data-v1` is confirmed).
- After `data-v1` (2026-09-13) the raw data is immutable; if a defect forces
  re-runs, a new instance with the SAME recorded specification is provisioned
  and the affected conditions repeated (plan 8, G5 week rules). "Same
  specification" includes the provider and instance type: results from two
  different families are not pooled.
