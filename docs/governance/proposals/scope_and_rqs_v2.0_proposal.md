# G0 — Integrated Yocto ARM64 scope and research questions (proposal, v2.0)

**Version/date:** 2.0 — 2026-09-16; amended 2026-09-18 (moved under
`docs/governance/proposals/`; dates). Technical direction authorised by the
student; final title/RQ wording and retained C2DTA local-core boundary await
supervisor agreement. No gate, experiment or approval is claimed here.

**Dated banner, 2026-09-19 — the title and RQ request below is overtaken.** The
student **reports** that the title was approved, with the exact wording
*Blockchain-powered Personal AI – Digital Twin Edge Gateway*, and that the
research questions were approved with RQ3 evaluated in QEMU rather than on a
native ARM64 virtual machine. That is reported by the student, carries no date,
message or supervisor name, and is not a documented supervisor decision. It
supersedes this proposal's request for those items; the proposal text itself,
including the wording below, is **history and is not rewritten**. The current
position is in
[section 3.2 of the adopted plan](../INTEGRATED_DEVELOPMENT_PLAN_2026.md) and in
[`docs/g0/scope_and_rqs.md`](../../g0/scope_and_rqs.md).

**Status — superseded proposal text (2026-09-18).** This scope belongs to the
[plan v2.0 proposal](INTEGRATED_DEVELOPMENT_PLAN_2026_v2.0_proposal.md) and is
kept with it under `docs/governance/proposals/`. **On 2026-09-18 the student
adopted plan v2.0 with a dated QEMU-only execution amendment**; the scope in
force is section 3 of the adopted plan at
[`../INTEGRATED_DEVELOPMENT_PLAN_2026.md`](../INTEGRATED_DEVELOPMENT_PLAN_2026.md),
and where that text and this one differ the adopted text governs. The technical
scope described here is the execution baseline, **but the title and the
research-question wording are not agreed**: they remain a request to the
supervisors (D001, D011) and are not settled by the student's adoption. Two
statements below are superseded by the amendment: the measured guest is the
Yocto-produced kernel and root filesystem booted **under QEMU/TCG on the
existing x86-64 workstation**, not a native ARM64 virtual machine, so RQ1 and
RQ3 are reworded in the adopted plan with RQ3 bounded to emulation; and the
possibility of measuring a native ARM64 guest with verified hardware
virtualisation is documented, unverified future work rather than a live option.
The distinction between verified hardware virtualisation and CPU emulation
remains a standing rule. The canonical scope document
[`docs/g0/scope_and_rqs.md`](../../g0/scope_and_rqs.md) is now version 2.0 of
2026-09-18; the August scope v1.1 is preserved in the repository history at
`dev` revision `9179612`. **Nothing here has been
sent to or approved by the supervisors.** The
[decision log](../supervisor_decision_log.csv) preserves the old requests
(D001-D010) and records the new ones (D011-D014) separately, all
`proposed_not_sent`.

## Objective and proposed title

Design, build and experimentally evaluate an integrated Yocto-based ARM64
Edge Gateway hosting the local digital-twin core of C2DTA. The final VM boots
the kernel/root filesystem produced by Yocto, and runs Mosquitto, the
controller, Eclipse Ditto and MongoDB as ARM64 containers on that guest.

*Design and Experimental Evaluation of a Yocto-Based ARM64 Edge Gateway for
the Local Digital-Twin Core of C2DTA*.

## Working research questions

1. **RQ1:** How can a versioned Yocto-based ARM64 gateway image be built,
   deployed and redeployed in an ARM64 virtual machine to host the local
   digital-twin core of C2DTA?
2. **RQ2:** To what extent can the integrated gateway ingest and materialise
   concurrent synthetic telemetry from three wearable-device types correctly
   and reliably, including under specified fault scenarios?
3. **RQ3:** What latency, sustainable-throughput, saturation and per-container
   resource trade-offs characterise the integrated gateway under controlled
   loads on the selected ARM64 virtual machine?

## Evidence boundary and delivery

- Logical operating-system and service layers are evaluated together.
- Emulated QEMU/TCG runs give functional and integration evidence only and
  support no ARM64 hardware performance conclusion; the evidence classes and
  the scope changes reserved for the supervisors are fixed in the
  [plan v2.0 proposal](INTEGRATED_DEVELOPMENT_PLAN_2026_v2.0_proposal.md),
  section 10.
- Existing QEMU/TCG checks remain preliminary and functional. A native ARM64
  guest using verified hardware virtualisation may be measured; QEMU/KVM is
  distinguished from CPU emulation. No Graviton nested-KVM capability is assumed.
- Keep the three wearable profiles, nominal 11.2 messages/s and current public
  message/API contracts. Collect measurements inside the Yocto guest; place the
  load generator outside it. Freeze image/runtime/protocol before the campaign.
- SSI, DIDComm, ledgers, IPFS and AI remain contextual/future integration under
  the retained local-core boundary, to be discussed with the supervisors.
- Claims apply to the selected VM and integrated configuration. Future physical
  deployment requires the selected board's BSP/kernel/drivers and new tests.
- Use versioned/redeployable wording; independent reproducibility is not yet
  demonstrated. No comparison proves Yocto superior to another OS.
- Planned submission: 2026-10-20. Final delivery deadline: 2026-10-31; the days
  from 2026-10-21 to 2026-10-31 are a contingency window for essential
  corrections only. Source of both dates: the student's confirmation of
  2026-09-18 after discussing the dates with the supervisors (a first-party
  statement; no administrative document was checked). Availability: about 8 h
  daily, weekends included.
- Estimated remaining effort: 225-345 active hours (estimate of 2026-09-16, not
  re-estimated); the planned submission is conditional on integration, on the
  native boot or an agreed contingency (D014), on a valid pilot and on
  supervisor review. The milestone dates in section 6 of the plan v2.0
  proposal are forecasts.

  > **Correction of 2026-09-18 (adoption).** The native-boot condition is
  > removed. The planned submission is conditional on the integration battery, a
  > valid pilot, the supervisors' agreement on the evaluation scope and any
  > academic use of emulated results (D014), and their review. The effort range
  > is a **superseded estimate** pending re-estimation after the integration
  > battery. Every date after 2026-09-18 is a planning target.

This revision updates planning text only. Existing dissertation drafts require
the explicit integration revision listed in section 5 of the plan v2.0
proposal; they are not silently treated as aligned or approved.
