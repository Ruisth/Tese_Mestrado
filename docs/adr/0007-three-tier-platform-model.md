# 0007 — Three-tier platform model: only a non-burstable native ARM64 instance may produce numbers for RQ3

**Status:** Proposed (2026-08-12) — extends [ADR 0001](0001-qemu-functional-vs-arm64-vm-performance.md);
awaiting validation by the supervisors. Nothing here accepts a gate or
validates a claim.

## Context

ADR 0001 separates two platforms: QEMU (`qemuarm64`) for functional validation,
and a native ARM64 cloud VM for the experimental campaign. It draws the line
between **emulated and native**, because that was the only line the market
seemed likely to force.

On 2026-08-11 the performance platform failed to materialise at three providers
on the same day:

- **Oracle Cloud (Always Free, Ampere A1):** the home region is fixed at
  registration and cannot be changed; a free account cannot subscribe another
  region; the home region has no Ampere capacity. Structurally blocked, not
  temporarily full.
- **Hetzner Cloud:** every CAX ARM instance unavailable.
- **Azure for Students:** regions limited to five, and quota `0 of 0` on every
  dedicated ARM family (`Dpsv5`/`Dpsv6`, `Dplsv5`/`Dplsv6`). Only the
  **burstable B series** is obtainable without a quota request.

Quota has been requested for **DPLSv5** and **DPLSv6** (Germany West Central,
4 vCPU), with **AWS `c6g.xlarge`** kept as a fallback at roughly 7 EUR for the
whole campaign.

This produces a shortcut that ADR 0001, as written, does not forbid: a
burstable instance is *native* ARM64, it is available today, and it will run
the containerised stack. The line drawn by ADR 0001 does not exclude it, so the
line has to be redrawn — a burstable vCPU is native silicon governed by a
billing mechanism, and for a load sweep that distinction matters as much as
emulation does.

Meanwhile the functional platform is real: the `egw-image` was built and taken
through two unattended QEMU bring-up boots on 2026-08-11, with the evidence
sealed in `docs/evidence/g1-yocto-qemu/`. That evidence is functional only.
(Gate G1 was later accepted on 2026-08-14, on the strict five-boot capsule,
for the functional platform layer only — decision in
`../governance/gate_decision_log.md`.)

## Decision

Three platform tiers, with a single rule about numbers:

| Tier | Role | Platform | Numbers in the dissertation |
|---|---|---|---|
| 1 | Functional (build, boot, systemd, networking, OCI runtime) | QEMU `qemuarm64` on WSL2/ext4 | **Never** (plan §5.1, ADR 0001) |
| 2 | Functional integration on ARM64 (deployment, wiring, end-to-end trace, `aarch64` images and digests) | a **burstable** ARM64 instance, e.g. Azure `B4pls_v2` | **Never** |
| 3 | Measurement (RQ3) | a **non-burstable native** ARM64 instance — `Dplsv5`/`Dplsv6` if the quota is approved, otherwise AWS `c6g.xlarge` | **Exclusively from here** |

- A burstable ARM64 instance **may** be used for functional integration work,
  and its use must be recorded as such.
- No latency, throughput or resource figure from tier 1 or tier 2 enters the
  dissertation, a chapter, an abstract or the claim→evidence matrix.
- Timed runs of the campaign are executed on a non-burstable family only
  (`Dplsv5`, `c6g`, `m6g`); `Bpsv2` and `t4g` are excluded from the protocol.
  The early signal of a violation is a timed run whose `sut_environment.json`
  reports a burstable family. This ADR records the protocol rule; it claims no
  automated enforcement and changes no code.
- Mixing data from different tiers in one analysis stays prohibited, as in
  ADR 0001. Every piece of evidence states its tier.
- Nothing in this decision alters any threshold, percentile, confidence-interval
  method, the 60 s confirmation window or the saturation criterion.

## Consequences

- **Why the bar on tier 2 exists.** A burstable instance runs on CPU credits:
  once the credits are exhausted, the billing model throttles the vCPU. The
  load sweep to 250 msg/s and the saturation criterion (sustained CPU above
  90 %) would then be measuring credit exhaustion instead of the gateway. Worse
  than being wrong, it would be *invisible*: in the collected series a throttled
  vCPU and a genuinely saturated one both read as CPU at the ceiling, so the
  contamination cannot be detected after the fact or corrected in the analysis.
  It can only be excluded beforehand, which is what this ADR does.
- Positive: ARM64 integration work (the G2/G3 vertical slice) can start on an
  instance that is available today, without putting a single contaminated
  number anywhere near RQ3; the separation established by ADR 0001 survives
  contact with the market instead of being quietly eroded by availability.
- Positive: the exclusion is methodological, not financial — the non-burstable
  fallback costs roughly 7 EUR for the campaign, so "it was free" is never an
  argument for publishing a burstable number.
- Negative: a third environment must be provisioned, described and recorded in
  the environment manifests; work done on tier 2 cannot be reused as pilot
  numbers, so parts of the pilot are executed twice.
- **Residual risk, stated plainly: no non-burstable native ARM64 instance has
  been obtained.** The measurement platform does not exist, which leaves RQ3 with no
  admissible data source, makes this the single blocking dependency from gate G2
  onwards, and means the campaign's logistical floor has to fit on an instance
  acquired late. The corresponding entries in the risk register are R28 and R29
  (dedicated ARM64 market unavailability; a burstable instance used as the
  measurement platform). This ADR bars the
  shortcut; it does not obtain the machine, and no reformulation of the platform
  model can substitute for that acquisition.
- The escalation rule has since been superseded: archived plan v1.0 §8.1
  required the risk to be reported with no VM on 2026-08-12; plan v1.1 §4
  replaces it with the university-first procedure — no university host
  confirmed within 48 hours of the request triggers a price quotation for a
  non-burstable public ARM64 instance, never above the EUR 30 total ceiling,
  with AWS `c6g.xlarge` as the default fallback. Both the request and any
  provisioning are student actions and are recorded in `LOG.md` when they
  happen.
