# Supervisor alignment memo — Edge Gateway P0

> **State: PROPOSAL, NOT SENT.** This memo is not evidence of supervisor
> approval. Responses become authoritative only when recorded in
> [`supervisor_decision_log.csv`](supervisor_decision_log.csv).

**Proposed working title:** *Design and Experimental Evaluation of a Two-Layer
ARM64 Edge Gateway Prototype for the Local Digital-Twin Core of C2DTA*  
**Target submission:** 2026-09-30  
**Internal cut-off:** 2026-09-29, 17:00 Europe/Lisbon

## Scientific contract to confirm

The thesis treats the Edge Gateway prototype as two complementary, separately
scoped layers:

1. a container-ready Yocto ARM64 platform validated functionally in QEMU; and
2. an MQTT-to-Ditto service stack evaluated on a fixed native ARM64 VM.

The thesis will not claim that the Ditto stack runs on the Yocto image without
new evidence. QEMU and a burstable ARM host will not support performance
conclusions. The method is Design Science Research with controlled experiments;
it does not reimplement the complete SSI/blockchain C2DTA platform.

### Proposed research questions

1. How can a two-layer ARM64 Edge Gateway prototype be designed, built and
   redeployed when its Yocto/QEMU functional platform and native-ARM64
   containerised digital-twin stack are treated as separate artefact layers?
2. To what extent can the prototype ingest and materialise concurrent synthetic
   telemetry from three wearable-device types correctly and reliably,
   including under specified fault scenarios?
3. What latency, sustainable-throughput, saturation and per-container resource
   trade-offs constrain the digital-twin stack on a non-burstable native-ARM64
   environment?

### Explicit P0 exclusions

ACA-Py/DIDComm, Fabric, Indy, IPFS, wallets, Raspberry Pi measurements, x86
comparison, Bluetooth/OTA, marketplace, federated learning, AI/multi-agent
services and dashboards remain excluded through September and any October
contingency.

## Treatment of the seven questions

1. Verify paper acronyms in the dissertation glossary.
2. Provide an editable five-layer C2DTA diagram with implemented and deferred
   boundaries, plus the two-layer experimental deployment diagram.
3. Add a Chapter 4 table of hosted software, versions and responsibilities.
4. Discuss DIDComm implementation difficulty from primary/academic sources and
   justify its P0 exclusion; make no implemented-agent claim.
5. Analyse the EGW as local twin host, connectivity/policy boundary and possible
   single point of failure.
6. Ground decentralised-computing discussion in academic sources and separate
   it from market forecasts.
7. Keep professional relevance in motivation/conclusion and defence material,
   not as an experimental result.

## Decisions requested

- D001: title, objective, RQs and the two-layer boundary.
- D002: exclusion of executable SSI/blockchain from P0.
- D003: structured scoping/narrative review label.
- D004: current official template and cover metadata.
- D005: review cadence and complete-draft feedback date.
- D006: second-operator reconstruction or weaker repeatability wording.
- D007: experimental thresholds and acceptance rules before `exp-v1`.
- D008: QEMU, burstable ARM64 and non-burstable ARM64 platform roles.

The companion evidence for review is the standalone Chapter 2 draft. A follow-up
is planned for 2026-08-18 and, if no response is recorded, a short meeting will
be requested on 2026-08-20. Silence will not be treated as approval.
