# G0 - Scope and research questions (integrated Yocto ARM64 gateway, evaluated under QEMU)

> Scope document under the versioned integrated plan
> ([`../governance/INTEGRATED_DEVELOPMENT_PLAN_2026.md`](../governance/INTEGRATED_DEVELOPMENT_PLAN_2026.md),
> **v2.0, adopted by the student on 2026-09-18 with the QEMU-only execution
> amendment**). The archived v1.0 and v1.2 remain historical. This document
> states the scientific scope for gate G0; it neither accepts the gate nor
> records a supervisor decision. Any approved change requires a plan update and
> an entry in the LOG.

**Version:** 2.0 (2026-09-18)

**Supersedes:** version 1.1 (2026-08-13), the two-layer scope. That text is not
rewritten anywhere: it is preserved in the repository history at `dev` commit
`9179612`, and its academic framing survives in
[`two_layer_thesis_proposal.md`](two_layer_thesis_proposal.md) under that
file's supersession banner.

**State:** the **technical scope** below is adopted by the student for project
execution. The **title and the research-question wording remain PROPOSED - NOT
SENT**, awaiting explicit supervisor validation under D001/D011. The student's
adoption of the plan is not supervisor agreement, and the student's report that
a supervisor advised proceeding with QEMU tests is student-reported advice, not
approval.

**Change control:** this document does not change the title or RQs in the
normative dissertation source. The rationale and earlier proposed wording are
recorded in [`two_layer_thesis_proposal.md`](two_layer_thesis_proposal.md), and
the requested decisions and recommendations are D001-D010 in
[`supervisor_decision_matrix.csv`](supervisor_decision_matrix.csv), extended by
D011-D014 for the integrated objective. That matrix contains no mutable status.
The authoritative decision state is kept only in
[`../governance/supervisor_decision_log.csv`](../governance/supervisor_decision_log.csv),
where D001-D014 are all `proposed_not_sent`.

The G0 email is drafted in
[`supervisor_email_g0.md`](supervisor_email_g0.md) and has not yet been
sent — sending it is a student action. Gate outcomes are recorded solely in
[`../governance/gate_decision_log.md`](../governance/gate_decision_log.md)
(as at 2026-09-18: G1 accepted for the functional platform layer only; G0 and
G2–G7 not decided, and the adoption of plan v2.0 changed none of them); the
state of every deliverable lives in [`../../PROGRESS.md`](../../PROGRESS.md).

---

## 1. Objective

Design and experimentally evaluate a versioned ARM64 Edge Gateway for the local
digital-twin core of C2DTA, as **one integrated system under test**: the
Yocto-produced ARM64 kernel and root filesystem booted under QEMU/TCG on the
existing x86-64 workstation, hosting the six-service containerised digital-twin
stack that receives concurrent synthetic telemetry from three wearable types,
validates the events and materialises them as digital twins in Eclipse Ditto.
The simulator and the experiment harness stay outside the guest.

The operating-system platform and the application services remain a logical
decomposition, not two separately deployed artefacts. A Yocto root filesystem
run in a container or chroot does not satisfy the objective, and neither does a
Yocto image booted while Ditto runs on another Linux installation. Eclipse
Ditto runs inside the Yocto guest: that was demonstrated under emulation on
2026-09-18, and the record of it is candidate evidence held outside the
repository and unsealed, so it admits no claim.

**QEMU produces no performance result.** Timing, observed throughput and
resource use recorded in this environment are informational, labelled emulated,
and describe only the identified emulated configuration; they are never native
ARM capacity, physical-device latency, energy efficiency or performance
superiority. Native ARM64 deployment and native measurement are documented,
unverified future work and are not required to complete this dissertation. The
word `reproducible` remains subject to D006 and is not a demonstrated property
until an independent clean reproduction has succeeded.

## 2. Research questions

**Working wording for academic review. It is not agreed with the supervisors**
and is requested under D001/D011; it is not yet integrated into the normative
dissertation source:

1. **RQ1:** *How can a versioned Yocto-based ARM64 gateway image be built,
   deployed and redeployed under QEMU to host the local digital-twin core of
   C2DTA?*
2. **RQ2:** *To what extent can the integrated gateway ingest and materialise
   concurrent synthetic telemetry from three wearable-device types correctly
   and reliably, including under specified fault scenarios?*
3. **RQ3:** *What workload-dependent timing and resource-use behaviour, and
   operational limitations, are observed for the integrated gateway in the
   specified QEMU/TCG environment?*

RQ3 is **bounded to emulation**. It does not retain the earlier claim about
capacity on a non-burstable native ARM64 environment, and no answer to it may
be presented as native ARM64 performance. Whether emulated results may be used
in the academic evaluation at all is D014 and is unanswered.

ACA-Py and SSI are **not required** to answer any RQ.

## 3. Mandatory scope — P0 (plan §3.3)

- Versioned Linux build environment, version control and claim→evidence matrix
  ([`../claim_evidence_matrix.md`](../claim_evidence_matrix.md)).
- Yocto Project **5.0.19/Scarthgap**, with exact tags and commits pinned in a
  `kas` manifest, without depending on the HEAD of moving branches (Scarthgap is
  the LTS line supported until April 2028, according to the official Yocto Project
  documentation).
- `egw-image` built and booted on `qemuarm64`, with systemd, networking and a
  working OCI runtime (the accepted G1 functional platform).
- The integrated `egw-gateway-image` built from the same pinned layers and
  booted under QEMU/TCG, hosting the container runtime and all six containers
  inside the guest. The published profile specifies four virtual CPUs and
  8 GiB of RAM; these are emulator settings recorded per run, not a
  demonstrated equivalence to a four-core physical gateway.
- Minimal ARM64 stack with Mosquitto, Eclipse Ditto 3.9.4 (`gateway`, `policies` and
  `things`), MongoDB and an MQTT→Ditto controller; `search`, `connectivity` and the UI
  stay excluded while they are not needed by the RQs. Every image and transitive
  dependency verified as `linux/arm64` and pinned by digest.
- A unified CLI simulator for smartwatch, smart ring and smart clothing.
- Scenarios `smoke`, `nominal`, `load-sweep`, `dropout-reconnect`, `invalid-payload`
  and `soak`.
- Unit, integration, E2E and recovery tests, run inside the integrated
  emulated guest. The **24-hour stability soak leaves mandatory scope**: it is
  not transferred to the emulated environment. A bounded emulated stability run
  may be defined at the pilot; the absence of a 24-hour soak is recorded as an
  explicit limitation and is never filled with an inferred result.
- An emulated functional campaign inside the specified QEMU/TCG guest,
  selected and documented after the bounded pilot and frozen before execution.
  The 95-run campaign of the previous plan is **not** carried over. Every
  failed or inconclusive attempt is retained, and emulated runs are never
  pooled with any future native run in one aggregate.
- A complete dissertation in English, with a Resumo in Portuguese if required.
- A versioned evidence and reproduction package with code, configurations, logs,
  data, checksums and the analysis script.

## 4. Reference architecture and future work only (plan §3.4)

**Native ARM64 deployment and native performance evaluation are future work.**
The guest is already ARM64 software, so the recipes, configurations, pinned
layers and compatible ARM64 container images could be reused on a compatible
ARM64 host with KVM or repackaged for a provider-managed ARM64 VM; neither
route is verified, the current direct-kernel and `.ext4` arrangement is not a
firmware-bootable cloud disk, and any adaptation produces a new identified
artefact rather than an edit of the sealed image. Old emulated results never
become native evidence after a successful port. This work is not P0, it closes
no gate, it is not reopened by spare time, and no cloud allocation, spending or
native build is requested.

ACA-Py, DIDComm, SSI, verifiable-credential flows, Fabric, Indy and IPFS are
not implementation scope in the submission path or in any contingency
window. They may appear only as C2DTA reference-architecture components,
explicit interface boundaries and future work. This v1.1 decision supersedes
the conditional P1 option in the archived v1.0; the historical ADR is retained
for traceability and is not an active work authorisation.

## 5. Out of scope (plan §3.4)

- ACA-Py, DIDComm, executable SSI, Hyperledger Indy, Fabric, IPFS as mandatory
  storage, marketplace, ownership transfer, business verifiable credentials,
  AI/MAS, graphical interface, dashboard, Bluetooth, OTA, LUKS, energy
  consumption and evaluation on a physical Raspberry Pi.
- More than three device types.
- A scientific paper and detailed defence preparation before submission. Once
  the thesis is delivered, the remaining time may be used for that work without
  reopening the submitted artefact.

Any contingency (plan §3.4) **never** reintroduces Indy, Fabric, IPFS, the
marketplace, a UI or any other cut function.

## 6. Closed project constraints (plan §§3–5)

- Time baseline: 2026-08-07.
- Availability: 35–45 h/week.
- Planned submission: 2026-10-20; final delivery deadline: 2026-10-31, with
  2026-10-21 to 2026-10-31 a contingency window for essential corrections only.
  Source: the student's first-party confirmation of 2026-09-18 after discussing
  the dates with the supervisors; no administrative document is held. Every
  milestone date is a planning target.
- No Raspberry Pi 5 is available, and no native ARM64 host is available.
- The evaluation is carried out in the integrated emulated environment. QEMU
  gives functional and integration evidence only: timing observed there is
  informational and labelled emulated, and never supports a performance or
  security statement.
- Dissertation in English; Resumo in Portuguese when required.
- CLI simulator, no dashboard.
- ACA-Py, DIDComm, SSI/blockchain and decentralised storage are contextual or
  future work only and are not an implementation contingency.
- The thesis must be defensible entirely from the integrated emulated P0 scope,
  with the absence of native evidence stated as an explicit limitation.
- The word target is indicative, never a substitute for evidence or quality.

## 7. Change record

- **Version 2.0 (2026-09-18).** Published for the student's adoption of plan
  v2.0 with the QEMU-only execution amendment. The two-layer objective becomes
  one integrated system under test; the research questions are rewritten and
  RQ3 is bounded to the specified QEMU/TCG environment; the native ARM64
  measurement environment, the 95-run campaign and the 24-hour soak leave
  mandatory scope and become future work or documented limitations; the dates
  move to the planned submission of 2026-10-20 with the final deadline of
  2026-10-31. **The supervisors approved none of this.** Nothing has been sent
  to them, D001-D014 remain `proposed_not_sent`, the title and RQ wording stay
  a request under D001/D011, and the academic use of emulated results stays a
  request under D014. No gate is closed and no claim is admitted.
- **Version 1.1 (2026-08-13).** The two-layer scope, superseded by version 2.0
  and preserved in the repository history.
