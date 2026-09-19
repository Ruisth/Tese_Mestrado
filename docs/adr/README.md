# Architecture Decision Records (ADRs)

Architecture decisions of the EGW project, in MADR-style short form
(Status / Context / Decision / Consequences). ADRs record decisions already
fixed by the normative integrated plan
([`../governance/INTEGRATED_DEVELOPMENT_PLAN_2026.md`](../governance/INTEGRATED_DEVELOPMENT_PLAN_2026.md))
and by [`../../src/CONTRACTS.md`](../../src/CONTRACTS.md); changing an accepted
ADR therefore requires updating those sources first and logging the change in
`LOG.md`. An ADR whose status is `Proposed` (0007, 0010) records a proposal, not
a decision fixed by the plan in force. **0008 is accepted by the student for
project execution (2026-09-18), as amended for QEMU-only execution and again on
2026-09-19**, and is fixed by the adopted plan. Its academic framing — the title
and the research-question wording of D011 — is **reported approved by the
student**: reported, undated and not a documented supervisor decision. Under D014, the QEMU evaluation scope of RQ3 is reported approved — reported by the student, undated, not a documented supervisor decision — and is not re-requested; the open part of D014 is only the wording of the native-evidence limitation and of claims about emulated timing and resource figures, and numerical criteria belong to D007 *(corrected 2026-09-19;
previously said the scope of the evaluation and any academic use of emulated
results remained reserved, with the academic-use half unanswered)*.

Conventions:

- Files are numbered `NNNN-short-title.md`; numbers are never reused.
- Statuses: `Proposed`, `Accepted`, `Deprecated`, `Superseded by NNNN`; a
  qualifier may follow the status word.
- New decisions taken during implementation (G1–G4) get new ADRs; ADRs are due
  with the first version of thesis chapter 4, which the adopted plan
  ([v2.0](../governance/INTEGRATED_DEVELOPMENT_PLAN_2026.md), section 4.1)
  targets for 2026-10-01 with Chapters 1–4. That is a planning target.

## Index

| ADR | Title | Status |
|---|---|---|
| [0001](0001-qemu-functional-vs-arm64-vm-performance.md) | Separate functional platform (QEMU) from performance platform (native ARM64 VM) | Accepted — extended by 0007; superseded in part by 0008 (2026-09-18) |
| [0002](0002-ssi-acapy-conditional-p1.md) | Historical conditional SSI/ACA-Py option | Superseded by integrated plan v1.1 |
| [0003](0003-flat-measurements-common-envelope-uuidv5.md) | Flat measurement fields with common envelope v1 and UUIDv5 message_id | Accepted |
| [0004](0004-minimal-ditto-preauth.md) | Minimal Ditto deployment (policies/things/gateway) with pre-authentication for the controller | Accepted |
| [0005](0005-latency-measured-in-controller-monotonic.md) | Primary latency measured inside the controller with a monotonic clock | Accepted |
| [0006](0006-duplicate-state-in-twin-ingestion-feature.md) | Duplicate-detection state persisted in the twin `ingestion` feature | Accepted |
| [0007](0007-three-tier-platform-model.md) | Three-tier platform model: only a non-burstable native ARM64 instance may produce numbers for RQ3 | Proposed; superseded for the adopted baseline by 0008 (2026-09-18); never validated by the supervisors |
| [0008](0008-integrated-yocto-arm64-evaluation.md) | Benchmark the service stack on the Yocto-built ARM64 guest | Accepted by the student for project execution (2026-09-18), as amended for QEMU-only execution and on 2026-09-19 — academic framing and the QEMU evaluation scope of RQ3 reported approved by the student; only D014's limitation and claim wording open (corrected 2026-09-19; previously "academic use of emulated results (D014) not agreed") |
| [0010](0010-controller-progress-counters.md) | Progress counters in the controller's `GET /metrics`: `received`, `in_progress`, `processing_errors` | Proposed |
