# Architecture Decision Records (ADRs)

Architecture decisions of the EGW project, in MADR-style short form
(Status / Context / Decision / Consequences). ADRs record decisions already
fixed by the normative integrated plan
([`../governance/INTEGRATED_DEVELOPMENT_PLAN_2026.md`](../governance/INTEGRATED_DEVELOPMENT_PLAN_2026.md))
and by [`../../src/CONTRACTS.md`](../../src/CONTRACTS.md); changing an accepted
ADR therefore requires updating those sources first and logging the change in
`LOG.md`.

Conventions:

- Files are numbered `NNNN-short-title.md`; numbers are never reused.
- Statuses: `Proposed`, `Accepted`, `Deprecated`, `Superseded by NNNN`.
- New decisions taken during implementation (G1–G4) get new ADRs; ADRs are due
  with the first version of thesis chapter 4 (plan v1.1 §4, G3 window 24–30 August).

## Index

| ADR | Title | Status |
|---|---|---|
| [0001](0001-qemu-functional-vs-arm64-vm-performance.md) | Separate functional platform (QEMU) from performance platform (native ARM64 VM) | Accepted — extended by 0007 |
| [0002](0002-ssi-acapy-conditional-p1.md) | Historical conditional SSI/ACA-Py option | Superseded by integrated plan v1.1 |
| [0003](0003-flat-measurements-common-envelope-uuidv5.md) | Flat measurement fields with common envelope v1 and UUIDv5 message_id | Accepted |
| [0004](0004-minimal-ditto-preauth.md) | Minimal Ditto deployment (policies/things/gateway) with pre-authentication for the controller | Accepted |
| [0005](0005-latency-measured-in-controller-monotonic.md) | Primary latency measured inside the controller with a monotonic clock | Accepted |
| [0006](0006-duplicate-state-in-twin-ingestion-feature.md) | Duplicate-detection state persisted in the twin `ingestion` feature | Accepted |
| [0007](0007-three-tier-platform-model.md) | Three-tier platform model: only a non-burstable native ARM64 instance may produce numbers for RQ3 | Proposed |
