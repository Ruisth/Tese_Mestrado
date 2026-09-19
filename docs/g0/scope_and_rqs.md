# G0 - Scope and research questions (integrated Yocto ARM64 gateway, evaluated under QEMU)

> Scope document under the versioned integrated plan
> ([`../governance/INTEGRATED_DEVELOPMENT_PLAN_2026.md`](../governance/INTEGRATED_DEVELOPMENT_PLAN_2026.md),
> **v2.0, adopted by the student on 2026-09-18 with the QEMU-only execution
> amendment**). The archived v1.0 and v1.2 remain historical. This document
> states the scientific scope for gate G0; it neither accepts the gate nor
> records a supervisor decision. Any approved change requires a plan update and
> an entry in the LOG.

**Version:** 2.0 (2026-09-18), amended 2026-09-19 to record the supervisor
confirmations reported by the student (section 7)

**Supersedes:** version 1.1 (2026-08-13), the two-layer scope. That text is not
rewritten anywhere: it is preserved in the repository history at `dev` commit
`9179612`, and its academic framing survives in
[`two_layer_thesis_proposal.md`](two_layer_thesis_proposal.md) under that
file's supersession banner.

**State:** the **technical scope** below is adopted by the student for project
execution. The **title and the research questions are reported approved**: the
student reports that the title was approved, with the exact wording
*Blockchain-powered Personal AI – Digital Twin Edge Gateway*, and that the
research questions were approved with RQ3 evaluated in QEMU rather than on a
native ARM64 virtual machine (D011). The student also reports that a supervisor
approved proceeding with the QEMU tests. **All of that is reported by the
student** — not a documented supervisor decision, with no date, message or
supervisor name reported — and the student's adoption of the plan is not
supervisor agreement either. The approved verbatim research-question wording
lives in the student manuscript; what section 2 publishes is a **scope summary**
of it.

**Change control:** this document does not change the title or RQs in the
normative dissertation source. The rationale and earlier proposed wording are
recorded in [`two_layer_thesis_proposal.md`](two_layer_thesis_proposal.md), and
the requested decisions and recommendations are D001-D010 in
[`supervisor_decision_matrix.csv`](supervisor_decision_matrix.csv), extended by
D011-D014 for the integrated objective. That matrix contains no mutable status.
The authoritative decision state is kept only in
[`../governance/supervisor_decision_log.csv`](../governance/supervisor_decision_log.csv),
whose statuses have been mixed since 2026-09-19: D001, D007, D008 and D012 stay
`proposed_not_sent`, D002 and D009 are `confirmed_reported_by_student`, and the
remaining rows are `partly_confirmed_reported_by_student`, each naming its
confirmed and its unresolved part. `sent_at` and `response_at` are empty in
every row, because no date was reported for any confirmation.

The August G0 email is drafted in
[`supervisor_email_g0.md`](supervisor_email_g0.md) and **that draft has not been
sent** — sending it is a student action. It does not stand for the whole
supervisor relationship: the student separately reports that the
state-of-the-art material was sent, with no date or copy held. Gate outcomes are recorded solely in
[`../governance/gate_decision_log.md`](../governance/gate_decision_log.md)
(as at 2026-09-18: G1 accepted for the functional platform layer only; G0 and
G2–G7 not decided, and the adoption of plan v2.0 changed none of them); the
state of every deliverable lives in [`../../PROGRESS.md`](../../PROGRESS.md).

---

## 1. Objective

**Title, as reported approved, verbatim:** *Blockchain-powered Personal AI –
Digital Twin Edge Gateway*. The broader blockchain and AI programme named in it
restores nothing to mandatory scope: this dissertation's contribution is the
local gateway described below, and section 5 is unchanged.

Design and experimentally evaluate a versioned ARM64 Edge Gateway for the local
digital-twin core of C2DTA, as **one integrated system under test**: the
Yocto-produced ARM64 kernel and root filesystem booted under QEMU/TCG on the
existing x86-64 workstation, hosting the six-service containerised digital-twin
stack that receives concurrent synthetic wearable data from three wearable
types — published on the literal `/telemetry` topic, the contract name retained
from the interface — validates the events and materialises them as digital
twins in Eclipse Ditto. The simulator and the experiment harness stay outside
the guest.

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
second-operator requirement of D006 is **reported waived** by the student, so no
independent clean reconstruction is owed; because none will exist, the word
`reproducible` stays unavailable and the wording remains *versioned* and
*repeatable build by the author*. The waiver concerns software testing and says
nothing about literature screening.

## 2. Research questions

The student **reports** that the research questions were approved, with RQ3
evaluated in QEMU rather than on a native ARM64 virtual machine (D011). That is
reported by the student and is not a documented supervisor decision. The
**approved verbatim wording lives in the student manuscript** and is not held in
the repository, so the three items below are **scope summaries of the approved
questions** and never supervisor quotations:

1. **RQ1:** *How can a versioned Yocto-based ARM64 gateway image be built,
   deployed and redeployed under QEMU to host the local digital-twin core of
   C2DTA?*
2. **RQ2:** *To what extent can the integrated gateway ingest and materialise
   concurrent synthetic wearable data from three wearable-device types correctly
   and reliably, including under specified fault scenarios?*
3. **RQ3:** *What workload-dependent timing and resource-use behaviour, and
   operational limitations, are observed for the integrated gateway in the
   specified QEMU/TCG environment?*

RQ3 is **bounded to emulation**. It does not retain the earlier claim about
capacity on a non-burstable native ARM64 environment, and no answer to it may
be presented as native ARM64 performance. Two things must not be conflated: the
student **reports** that RQ3 evaluated in QEMU was approved and that a
supervisor approved proceeding with the QEMU tests, and **whether emulated
results may be used as the academic evaluation at all is D014 and remains
unanswered**. Approving the route is not approving the use of its results.

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
  emulated guest, including a **24-hour stability soak attempted** in that
  environment. *(Superseded wording of 2026-09-18: "The 24-hour stability soak
  leaves mandatory scope: it is not transferred to the emulated environment.")*
  Attempting it promises no valid 24-hour run: if the bounded pilot finds it
  infeasible, a shorter emulated stability run is defined in its place and the
  absence of a 24-hour soak is recorded as an explicit limitation, never filled
  with an inferred result.
- An emulated functional campaign inside the specified QEMU/TCG guest,
  selected and documented after the bounded pilot and frozen before execution.
  The **95-run composition of the previous plan is the quantity that campaign
  attempts to reach**, subject to the pilot's feasibility check — see section
  3.3.1 of the adopted plan for the per-condition table. *(Superseded wording of
  2026-09-18: "The 95-run campaign of the previous plan is not carried over.")*
  The attempt is neither the frozen protocol nor a promise of 95 valid runs.
  Every failed or inconclusive attempt is retained, and emulated runs are never
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

- **Amendment of 2026-09-19, within version 2.0.** It changes no scope, gate or
  claim; it records the supervisor confirmations the student reports and marks
  what they supersede. The title recorded in section 1 and the research questions of
  section 2 are **reported approved**, with RQ3 evaluated in QEMU; the approved
  verbatim RQ wording stays in the student manuscript, so the repository
  publishes scope summaries. The second-operator requirement of D006 is reported
  waived, without licensing the word *reproducible*. The 24-hour soak and the
  95-run composition return to section 3 as a **target to attempt** under QEMU,
  subject to the pilot's feasibility check, superseding the version 2.0
  statements that they left mandatory scope; those statements are marked where
  they stand rather than deleted. Section 1 adopts the authorised wearable-data
  wording of
  [`../governance/language-policy.md`](../governance/language-policy.md) while
  keeping the literal `/telemetry` topic. **Every confirmation above is reported
  by the student**: none is a documented supervisor decision, none carries a
  date, and none closes a gate or admits a claim. The academic use of emulated
  results (D014) and the experimental thresholds (D007) remain open.
- **Version 2.0 (2026-09-18).** Published for the student's adoption of plan
  v2.0 with the QEMU-only execution amendment. The two-layer objective becomes
  one integrated system under test; the research questions are rewritten and
  RQ3 is bounded to the specified QEMU/TCG environment; the native ARM64
  measurement environment, the 95-run campaign and the 24-hour soak leave
  mandatory scope and become future work or documented limitations *(the 95-run
  campaign and the soak are superseded by the amendment of 2026-09-19 above)*;
  the dates move to the planned submission of 2026-10-20 with the final deadline
  of 2026-10-31. *(Wording of 2026-09-18, superseded by the amendment above:
  "The supervisors approved none of this. Nothing has been sent to them,
  D001-D014 remain `proposed_not_sent`, the title and RQ wording stay a request
  under D001/D011.")* What holds after that amendment: the title and the RQ
  wording are reported approved by the student, the academic use of emulated
  results stays a request under D014, and D001, D007, D008 and D012 remain
  `proposed_not_sent`. No gate is closed and no claim is admitted.
- **Version 1.1 (2026-08-13).** The two-layer scope, superseded by version 2.0
  and preserved in the repository history.
