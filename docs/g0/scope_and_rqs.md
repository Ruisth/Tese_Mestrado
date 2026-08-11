# G0 — Scope and research questions (proposed — awaiting supervisor validation)

> Derived from the integrated plan (`../../../PLANO_DESENVOLVIMENTO_INTEGRADO_EDGE_GATEWAY_2026.md`,
> v1.0 — 2026-08-07, NORMATIVE), sections 4 and 12. This document fixes the scope for
> gate **G0 (2026-08-10)**. Any change requires the plan to be updated and an entry in the LOG.

**State:** proposed, awaiting supervisor validation. The G0 email is drafted in
[`supervisor_email_g0.md`](supervisor_email_g0.md) and has not yet been
sent — sending it is a student action. **No gate has been accepted**, G0
included; the state of every deliverable lives in
[`../../PROGRESS.md`](../../PROGRESS.md).

---

## 1. Objective (plan §4.1)

Design, implement and evaluate a reproducible ARM64 Edge Gateway, based on Yocto
and containerised services, able to receive concurrent synthetic telemetry from
three wearables, validate the events and materialise them as digital twins in
Eclipse Ditto.

## 2. Definitive research questions (plan §4.2)

The RQs are fixed in English, exactly as they will appear in the dissertation:

1. **RQ1:** *How can a reproducible Yocto-based ARM64 edge gateway be designed to
   host containerised digital-twin services?*
2. **RQ2:** *To what extent can the gateway ingest and materialise concurrent
   synthetic telemetry from three wearable-device types correctly and reliably?*
3. **RQ3:** *What latency, throughput and resource-consumption trade-offs constrain
   deployment of the proposed platform on an ARM64 edge-class environment?*

ACA-Py and SSI are **not required** to answer any RQ.

## 3. Mandatory scope — P0 (plan §4.3)

- Reproducible Linux environment, version control and claim→evidence matrix
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
- A reproducibility package with code, configurations, logs, data, checksums and
  the analysis script.

## 4. Conditional scope — P1 (plan §4.4)

ACA-Py may only proceed **after gate G3 (2026-08-30)**, with a maximum total timebox
of **12 hours**, and under the cutting rules of plan §8.1:

- it only proceeds if the QEMU build/boot, a clean ARM deployment, three devices,
  the scenarios, tests, metrics and soak are complete and **free of P0 defects**;
- use the image `ghcr.io/openwallet-foundation/acapy-agent:py3.13-1.6-lts`, pinned
  by the digest verified for ARM64, and `askar-anoncreds` instead of the deprecated
  `askar` wallet;
- confirm ARM64 support **before** any implementation;
- run two local agents, `did:peer`, an Out-of-Band invitation and a basic DIDComm
  message;
- do not use a public ledger, Indy, credential issuance or ownership logic;
- cut immediately if there is no ARM64 image, if any P0 gate is red or if the
  timebox ends; automatic cut after 12 h or on **2026-09-03**, whichever comes
  first.

The thesis has to be defensible even with the whole of P1 cut; see
[`../adr/0002-ssi-acapy-conditional-p1.md`](../adr/0002-ssi-acapy-conditional-p1.md).

## 5. Out of scope (plan §4.5)

- Hyperledger Indy, Fabric, IPFS as mandatory storage, marketplace, ownership
  transfer, business verifiable credentials, AI/MAS, graphical interface,
  dashboard, Bluetooth, OTA, LUKS, energy consumption and evaluation on a physical
  Raspberry Pi.
- More than three device types.
- A scientific paper and detailed defence preparation before submission. If the
  thesis is delivered in September, October may be used for that work without
  reopening the submitted artefact.

The contingency extension (plan §10) **never** reintroduces Indy, Fabric, IPFS,
the marketplace, a UI or any other cut function.

## 6. Closed premises (plan §12)

- Time baseline: 2026-08-07.
- Availability: 35–45 h/week.
- Official deadline: 2026-09-30; internal deadline: 2026-09-29 at 17:00.
- No Raspberry Pi 5 is available.
- Performance evaluation on an ARM64 VM; QEMU is functional only.
- Dissertation in English; Resumo in Portuguese when required.
- CLI simulator, no dashboard.
- ACA-Py is strictly conditional and dispensable for every RQ.
- The thesis has to be defensible even if the whole P1 scope is cut.
- The word target is indicative, never a substitute for evidence or quality.
