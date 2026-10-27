# Comparative protocol — Yocto image versus Debian 13 under one QEMU/TCG profile (proposal)

**Status: a proposal to be approved later. Nothing in it is executed, authorised or
scheduled by this document.** It names what a comparison between the two environments of
[`README.md`](README.md) would measure, how, and what it would cost, so that a decision can be
taken on it. The pilot figures below are planning inputs, not results, and are not citable.

## 1. Profiles

- **A — system at rest.** Both guests booted from a fresh work overlay and a fresh data disk,
  without the application stack. The services present are identified (`systemctl
  list-units --type=service --state=running`, `list-timers --all`, `docker info`) and then
  left alone for the window.
- **B — full gateway stack.** The same six services from the same images and digests
  (`images.lock.env`, the controller archive and its identity record), the same `compose.yaml`
  and memory limits, the same `.env`, the same initial data state (fresh `data.img`, fresh
  volumes), the same load: the existing nominal condition — 120 s warm-up, 600 s measured at
  11.2 msg/s with the nominal device mix, 60 s confirmation window — with the same device
  count in every repetition and, as the order of 2026-10-18 fixed it, one seed per pair of
  executions, equal in both distributions (three seeds, fixed before the first boot;
  `measure_plan.py`), driven by the existing harness (`python -m egw_experiments run`) from
  the host.

## 2. Metrics and their clocks

| Metric | Definition | Where / clock |
|---|---|---|
| Guest memory used | `MemTotal − MemAvailable` from `/proc/meminfo`, sampled every second over the window; median, p95 and last sample reported | guest, `/proc/uptime` as the sample clock |
| Host QEMU process RSS | `VmRSS` (and `VmHWM`) from `/proc/<pid>/status` of the scenario's QEMU, sampled every second | host, `/proc/uptime`; reported **separately**, never added to guest figures |
| Idle CPU | from two readings of `/proc/stat` (first line) at the window's ends: `(idle + iowait) / total` of the deltas; also the per-cpu lines | guest, window bounded by its own `/proc/uptime` |
| Host CPU of the guest | `utime + stime` of `/proc/<pid>/stat` over the window divided by the window | host, `/proc/uptime`; reported separately |
| Filesystem used | `df -B1 / /var/lib/docker`, `du -s /var/lib/docker`, `docker system df`, taken at the end of settle and at the end of the window | guest |
| Time to operational | host monotonic (`/proc/uptime`) from QEMU start (`state/started`) → first ssh answer → `systemctl is-system-running` ∈ {`running`, `degraded`} → in B, controller `/ready` 200; the polls run every second (the `validate.sh` polls are coarser and are not used for this) | host |
| Per-container CPU and memory | the existing collector `src/deployment/scripts/collect-resources.sh` (cgroup v2, one sample per second, `ts_utc`), with its validity rules (≥ 30 distinct instants, gaps ≤ 5 s, ≥ 90 % coverage of the window) | guest, UTC stamps; validity judged by the harness |
| Accepted messages, throughput, latency | the controller's `/metrics` counters and `events.jsonl`, read by the existing harness; latency as the controller measures it (ADR 0005, monotonic) | controller / harness, unchanged |

The guest samplers for memory, `/proc/stat` and the host-side process sampler are not in the
tooling; they are to be approved with this protocol and recorded with their sha256.

## 3. Design

- Three repetitions per scenario and profile; order **Y-D-D-Y-Y-D** within each profile
  (profile A's six first, then profile B's six), so that neither scenario always follows the
  other.
- Equal initial states: every repetition starts from `destroy` + `prepare` (fresh overlay on
  the unchanged base, fresh 32 GiB data disk), then `start`; in B the stack is provisioned
  afresh on that state. The bases' sha256 are the same in all twelve repetitions.
- One guest at a time, host otherwise idle (no build, no other QEMU, no pilot session, no
  other load on the workstation); the manifest, `argv.txt`, the host facts and the window
  bounds are recorded for each repetition.
- Durations: A — settle 120 s after `is-system-running`, then a 600 s window. B — the nominal
  condition as it exists (120 s + 600 s + 60 s), then the existing drain until quiet.

## 4. Cost estimate per repetition (seconds; m = measured in the pilot, e = extrapolated)

| Phase | Yocto | Debian 13 |
|---|---|---|
| destroy + prepare (overlay, 32 GiB sparse disk, base re-hash) | 60–180 e | 60–180 e (larger base to re-hash) |
| boot to operational | ≤ 434 m (the pilot's session open, which includes its own records; a boot alone is shorter) | X |
| A: settle + window | 720 | 720 |
| B: stack provisioned to healthy and `/ready` | 300–900 e ("several minutes" under TCG, m, no single figure) | X |
| B: nominal row slot (warm-up, measured, confirmation, fetches) | ≈ 1,306 m | X (the slot is load-bound, the same if the guest keeps up) |
| B: post-run drain | 131–888 m | X |
| controlled stop (A) / `compose stop -t 60` + power-off (B) | 30–180 e / 90–240 e | X |
| **A, per repetition** | **≈ 1,240–1,510 (21–25 min)** | X |
| **B, per repetition** | **≈ 2,320–3,950 (39–66 min)** | X |

Yocto side, twelve repetitions: about 3.0–4.6 h of machine time; Debian side: X until its first
boot, provisioning and stop have been timed once. Operator time (alternation, checks, records)
is extra — about 10–15 min per repetition, e — so the whole is a matter of several sittings,
during which the workstation is not available for anything else.

## 5. What is not comparable, and is said so

- Boot time includes no firmware and no GRUB in either scenario (direct kernel boot for both;
  Debian's native UEFI/GRUB path is not exercised).
- `mem=8192M` is a fixed guest memory for both; `MemTotal` differs by what each kernel reserves.
- The Debian root disk is larger (3.0 GiB GPT, grown at first boot) than the Yocto root
  (2.44 GiB raw ext4); image size is not a metric, used space is.
- Docker/containerd/runc/compose versions differ (README section 6); any difference in B may
  come from the engine as much as from the operating system.
- Everything is TCG emulation on one x86-64 host: no figure is native ARM64 capacity.

## 6. Acceptance and reporting

- A repetition is **accepted** when its instrumentation is valid — collector coverage, the
  samplers' files complete, manifests and `argv.txt` present, the results directory sealed with
  `SHA256SUMS` — **regardless of its result**. A repetition in which the system failed is a
  result; a repetition whose records are incomplete is repeated.
- Tables per profile and metric with the three per-repetition values and the median for each
  scenario; differences stated with their direction ("Debian used N MiB more", never
  "better") and with the medians they come from; never pooled across scenarios or profiles.
- The comparison may show an advantage, an equivalence or a disadvantage for either scenario;
  the protocol does not presume one.
