# G0 - Scope and research questions (two-layer proposal)

> Working proposal under the versioned integrated plan
> ([`../governance/INTEGRATED_DEVELOPMENT_PLAN_2026.md`](../governance/INTEGRATED_DEVELOPMENT_PLAN_2026.md),
> v1.1 - 2026-08-13). The archived v1.0 remains historical. This document
> proposes the scientific scope for gate G0; it neither accepts the gate nor
> records a supervisor decision. Any approved change requires a plan update and
> an entry in the LOG.

**Version:** 1.1 (2026-08-13)

**State:** **PROPOSED - NOT SENT**, awaiting explicit supervisor validation.

**Change control:** this proposal does not change the title or RQs in the
normative dissertation source. The rationale and proposed wording are recorded
in [`two_layer_thesis_proposal.md`](two_layer_thesis_proposal.md), and the
requested decisions and recommendations are D001-D008 in
[`supervisor_decision_matrix.csv`](supervisor_decision_matrix.csv). That matrix
contains no mutable status. The authoritative decision state is kept only in
[`../governance/supervisor_decision_log.csv`](../governance/supervisor_decision_log.csv).

The G0 email is drafted in
[`supervisor_email_g0.md`](supervisor_email_g0.md) and has not yet been
sent — sending it is a student action. **No gate has been accepted**, G0
included; the state of every deliverable lives in
[`../../PROGRESS.md`](../../PROGRESS.md).

---

## 1. Proposed objective

Design and experimentally evaluate a versioned, two-layer ARM64 Edge Gateway
prototype for the local digital-twin core of C2DTA. The first artefact layer is
a Yocto/QEMU functional platform for build, boot, networking, systemd and an OCI
runtime. The second is a separately deployed native-ARM64 container stack that
receives concurrent synthetic telemetry from three wearable types, validates
the events and materialises them as digital twins in Eclipse Ditto.

The two layers share repository provenance and contracts, but the proposal does
not claim that Eclipse Ditto runs inside the Yocto image. QEMU produces no
performance result. The word `reproducible` remains subject to D006 and is not a
demonstrated property until an independent clean reproduction has succeeded.

## 2. Proposed research questions

The following wording is proposed for D001; it is not yet integrated into the
normative dissertation source:

1. **RQ1:** *How can a two-layer ARM64 Edge Gateway prototype be designed, built
   and redeployed when its Yocto/QEMU functional platform and native-ARM64
   containerised digital-twin stack are treated as separate artefact layers?*
2. **RQ2:** *To what extent can the prototype ingest and materialise concurrent
   synthetic telemetry from three wearable-device types correctly and reliably,
   including under specified fault scenarios?*
3. **RQ3:** *What latency, sustainable-throughput, saturation and per-container
   resource trade-offs constrain the digital-twin stack on a non-burstable
   native-ARM64 environment?*

ACA-Py and SSI are **not required** to answer any RQ.

## 3. Mandatory scope — P0 (plan §3.3)

- Versioned Linux build environment, version control and claim→evidence matrix
  ([`../claim_evidence_matrix.md`](../claim_evidence_matrix.md)).
- Yocto Project **5.0.19/Scarthgap**, with exact tags and commits pinned in a
  `kas` manifest, without depending on the HEAD of moving branches (Scarthgap is
  the LTS line supported until April 2028, according to the official Yocto Project
  documentation).
- `egw-image` image built and booted on `qemuarm64`, with systemd, networking and a
  working OCI runtime.
- Minimal ARM64 stack with Mosquitto, Eclipse Ditto 3.9.4 (`gateway`, `policies` and
  `things`), MongoDB and an MQTT→Ditto controller; `search`, `connectivity` and the UI
  stay excluded while they are not needed by the RQs. Every image and transitive
  dependency verified as `linux/arm64` and pinned by digest.
- A unified CLI simulator for smartwatch, smart ring and smart clothing.
- Scenarios `smoke`, `nominal`, `load-sweep`, `dropout-reconnect`, `invalid-payload`
  and `soak`.
- Unit, integration, E2E, recovery, load and 24-hour stability tests.
- An experimental campaign on a temporary ARM64 VM (native, not emulated).
- A complete dissertation in English, with a Resumo in Portuguese if required.
- A versioned evidence and reproduction package with code, configurations, logs,
  data, checksums and the analysis script.

## 4. Reference architecture and future work only (plan §3.4)

ACA-Py, DIDComm, SSI, verifiable-credential flows, Fabric, Indy and IPFS are
not implementation scope in September or in any unapproved October
contingency. They may appear only as C2DTA reference-architecture components,
explicit interface boundaries and future work. This v1.1 decision supersedes
the conditional P1 option in the archived v1.0; the historical ADR is retained
for traceability and is not an active work authorisation.

## 5. Out of scope (plan §3.4)

- ACA-Py, DIDComm, executable SSI, Hyperledger Indy, Fabric, IPFS as mandatory
  storage, marketplace, ownership transfer, business verifiable credentials,
  AI/MAS, graphical interface, dashboard, Bluetooth, OTA, LUKS, energy
  consumption and evaluation on a physical Raspberry Pi.
- More than three device types.
- A scientific paper and detailed defence preparation before submission. If the
  thesis is delivered in September, October may be used for that work without
  reopening the submitted artefact.

Any contingency (plan §3.4) **never** reintroduces Indy, Fabric, IPFS, the
marketplace, a UI or any other cut function.

## 6. Closed project constraints (plan §§3–5)

- Time baseline: 2026-08-07.
- Availability: 35–45 h/week.
- Official deadline: 2026-09-30; internal deadline: 2026-09-29 at 17:00.
- No Raspberry Pi 5 is available.
- Performance evaluation on an ARM64 VM; QEMU is functional only.
- Dissertation in English; Resumo in Portuguese when required.
- CLI simulator, no dashboard.
- ACA-Py, DIDComm, SSI/blockchain and decentralised storage are contextual or
  future work only and are not an implementation contingency.
- The thesis must be defensible entirely from the two-layer P0 scope.
- The word target is indicative, never a substitute for evidence or quality.
