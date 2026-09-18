# G0 — Integrated Yocto ARM64 scope and research questions

**Version/date:** 2.0 — 2026-09-16. Technical direction authorised by the
student; final title/RQ wording and retained C2DTA local-core boundary await
supervisor agreement. No gate, experiment or approval is claimed here.

**Status — proposal published for review (2026-09-18).** This scope belongs to the
proposed [integrated plan v2.0](../governance/INTEGRATED_DEVELOPMENT_PLAN_2026.md).
[Plan v1.2](../governance/archive/INTEGRATED_DEVELOPMENT_PLAN_2026_v1.2_en.md)
remains the plan in force until the student decides after consulting the
supervisors; the August scope v1.1 on which it relies is the previous revision
of this file (commit `b5b1c42`). Nothing here has been sent to or approved by
the supervisors. The [decision log](../governance/supervisor_decision_log.csv)
preserves the old requests (D001-D010) and records the new ones (D011-D014)
separately, all `proposed_not_sent`.

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
  the scope changes reserved for the supervisors are fixed in plan v2.0,
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
- Ready-to-submit target: 20 October 2026. Extension deadline reported by the
  student: 3 November. Availability: about 8 h daily, weekends included.
- Estimated remaining effort: 225-345 active hours; the target is conditional
  on prompt platform access, native boot, valid pilot and supervisor review.

This revision updates planning text only. Existing dissertation drafts require
the explicit integration revision listed in plan section 5; they are not
silently treated as aligned or approved.
