# C2DTA paper-to-P0 traceability and software inventory

**Document version:** 1.2

**Date:** 2026-09-18 (version 1.1 of 2026-08-13 retargeted at the integrated
emulated system adopted on 2026-09-18)

**Status:** academic support document - non-normative

**Primary comparison source:** `pinto2026c2dta` (controlled full-text source
EXT-001 in the
[`external-source register`](../governance/external_source_register.md), with
the version of record identified by
[DOI 10.1016/j.bcra.2025.100342](https://doi.org/10.1016/j.bcra.2025.100342))

This document prevents two common category errors: treating the local P0 core
as an implementation of the full C2DTA, and treating repository configuration
or unit tests as evidence of a live deployment. `Implemented/configured` below
means that code or configuration exists in the repository. It does not mean
that the service stack in the integrated emulated guest has passed a live test
or that a gate has been accepted.

The system under test is the Yocto-produced ARM64 guest booted under QEMU/TCG
on an x86-64 workstation (adopted plan v2.0, 2026-09-18). Evidence produced
there is functional and integration evidence only. On 2026-09-18 the stack was
deployed in that guest and one bounded end-to-end flow completed; that record
is **candidate evidence held outside the repository and unsealed**, so
throughout this document "emulated evidence of 2026-09-18" means exactly that
and admits no claim.

## 1. Edge Gateway function traceability

| EGW function in the paper | P0 implementation or closest bounded analogue | Executable stub/interface status | Deferred integration or research |
|---|---|---|---|
| Consumer-edge connectivity hub linking smart devices and controller agents to the ecosystem through DIDComm | Synthetic devices publish MQTT/TLS telemetry to Mosquitto; the controller consumes the contracted topic. This is a telemetry path, not a DIDComm replacement. | No DIDComm stub. The exclusions section of [the adopted plan v2.0](../governance/INTEGRATED_DEVELOPMENT_PLAN_2026.md) is the normative exclusion; D002 remains a proposed supervisor confirmation in the authoritative [`decision log`](../governance/supervisor_decision_log.csv). ADR 0002 is superseded historical context, not implementation authority. | ACA-Py agents, OOB establishment, DIDs and DIDComm messaging |
| Host the smart-device digital-twin platform | The ARM64 Compose configuration contains Eclipse Ditto 3.9.4 gateway, policies and things, MongoDB and the controller. On 2026-09-18 the six containers were deployed and exercised **inside the Yocto guest under emulation**; that record is candidate evidence outside the repository and admits no claim. | Real P0 service configuration and controller code exist; the emulated evidence of 2026-09-18 is unsealed, and the remaining evidence is unit/fake. | Seal the emulated vertical slice and run the nine integration/recovery families; full C2DTA Ditto service set only if a later research scope requires it |
| Interface with the ecosystem ledger for device status | Not implemented. Ditto's local ingestion feature and experiment manifests do not constitute an ecosystem ledger. | None | Hyperledger Fabric transactions, lifecycle state and chaincode integration |
| Interface with the identity ledger for credential verification and issuance | Not implemented. Ditto pre-authentication is a local deployment mechanism, not SSI or credential verification. | None | Hyperledger Indy or another approved DID/VC registry and credential flows |
| Transfer historical twin data to decentralised storage | Not implemented. Local event logs and experiment raw data are evidence artefacts, not the paper's decentralised dataset service. | No dataset-export or IPFS interface is contracted in P0. | Dataset builder, provenance metadata and IPFS/decentralised-storage transfer |
| Authorise smart-device onboarding before twinning and untwinning | The controller creates a Ditto policy and thing on the first valid event. This is deterministic P0 provisioning, not C2DTA ownership or SSI authorisation. | Real first-contact policy/thing flow; no owner credential, agent or twinning/untwinning protocol stub | Consumer/device agents, ownership credentials and authorised twin/untwin lifecycle |
| Support one or multiple smart devices | The simulator and schemas cover smartwatch, smart ring and smart clothing with stable identifiers; live concurrent ingestion is not yet evidenced. | Real simulator, schemas and thing identifiers; current evidence is unit-level | Physical devices, discovery/Bluetooth and wider device-model catalogue |
| Move compute and twin custody towards the consumer edge | The design targets one integrated gateway: the Yocto-produced ARM64 guest hosting the six containers, evaluated under emulation. No physical household gateway and no native ARM64 host have been evaluated. | Deployment artefacts exist and ran in the emulated guest on 2026-09-18; QEMU is functional-only, and native deployment is documented, unverified future work. | Native ARM64 deployment; physical consumer-controlled hardware, redundancy, failover and multi-EGW federation |
| Protect integrity/privacy while remaining a single point of failure | MQTT/TLS, broker ACLs, validation and Ditto policies are configured. They do not establish the full paper security model, and no security evaluation or failover claim exists. | Security configuration exists; live verification and recovery evidence are pending. | Threat-model validation, key lifecycle, redundancy and recovery across EGWs |

## 2. Software and platform inventory

| Concern | Supplied C2DTA paper | Current P0 repository | Evidence boundary |
|---|---|---|---|
| Host platform | Docker on a Proxmox/QEMU/KVM-based virtual machine, reported as 16 GB RAM and 32 CPUs. **The paper does not specify the evaluation hardware ISA**, so none is attributed to it here | One integrated system: the Yocto Scarthgap `qemuarm64` kernel and root filesystem booted under QEMU/TCG on an x86-64 workstation, hosting the six containers inside the guest | The functional platform is complete for its scope: the preliminary seal (build + two bring-up boots) plus the 2026-08-14 clean-checkout build and five strict boots; gate G1 accepted 2026-08-14, admitting no claim. The integrated profile was built and booted on 2026-09-18 (sealed) and hosted the stack and one bounded flow the same day (unsealed, outside the repository). No native ARM64 deployment exists |
| Telemetry broker | Eclipse Mosquitto; MQTT over SSL for the smartwatch path | Eclipse Mosquitto 2.0.22, digest-pinned; MQTT/TLS on port 8883, QoS 1 | Configuration exists; live end-to-end evidence is pending |
| Digital-twin platform | Eclipse Ditto 3.0.0 with gateway/routing, connectivity, things, policies, search and database services | Eclipse Ditto 3.9.4 minimal core: gateway, policies and things | Digest-pinned Compose configuration exists; emulated ARM64 evidence of 2026-09-18, unsealed and outside the repository |
| Persistence | Ditto database and encrypted-at-rest deployment; historical datasets transferred to decentralised storage | MongoDB 7.0.39 for Ditto state; local append-only experiment artefacts are a separate concern | MongoDB image is pinned; decentralised historical-data transfer is absent |
| Gateway controller | EGW agent/controller participates in device onboarding, twinning and ecosystem interactions | Python MQTT-to-Ditto controller validates schemas, handles first contact, applies updates and records outcomes | A bounded live broker-to-Ditto trace exists from the emulated guest (2026-09-18, 60/60 accounted, unsealed and outside the repository); the remaining controller evidence is unit/fake |
| Identity and secure agent messaging | ACA-Py/Hyperledger Aries agents, controllers and wallets; DIDs, VCs, OOB and DIDComm | Not implemented | Excluded from P0 and every contingency window by the exclusions section of [the adopted plan v2.0](../governance/INTEGRATED_DEVELOPMENT_PLAN_2026.md); D002 is pending supervisor confirmation, not permission to implement |
| Ecosystem ledger | Hyperledger Fabric | Not implemented | No stub or result claim |
| Identity ledger | British Columbia Test Indy Network | Not implemented | No stub or result claim |
| Decentralised storage | IPFS | Not implemented | No dataset builder or IPFS interface in P0 |
| Workload generator | Dedicated smartwatch simulator producing heart rate, geolocation and timestamp data at 1 Hz | Deterministic simulator for smartwatch, smart ring and smart clothing across six planned scenarios | Simulator is unit-tested; official live campaign has not run |
| Evaluation automation | Gherkin scripts and ACA-Py Test Harness; eight scenarios defined, first seven evaluated across 88 steps | Pytest suite plus a custom experimental harness and pre-specified run plan | 701 unit tests are sealed; no live integration campaign or `data-v1` exists. The nine integration/recovery test families were exercised once on 2026-09-18 — seven passed, tests 1 and 6 carry a failing harness part from the resource sampler under emulation — and that record is held outside the repository and unsealed, so the battery is not complete and supports no claim |

The Mosquitto version typography in the supplied paper appears as `2.0.1.5` in
the extracted manuscript text. This inventory therefore names the paper's
broker without normalising that version; any exact version copied into the
dissertation must first be checked against the version of record.

## 3. Comparison rules for the dissertation

1. Compare architecture, scope and evaluation method, **not raw performance
   values in either direction**. The paper's evaluation hardware ISA is
   unspecified, and this dissertation's results are emulated.
2. State that the paper defines eight lifecycle scenarios and evaluates the
   first seven across 88 steps; do not compress this into an ambiguous claim
   that the architecture has only seven use cases.
3. State that the smartwatch's 1 Hz telemetry path is one part of the broader
   C2DTA evaluation, not its entire workload.
4. Label repository artefacts, static tests, live integration evidence and
   accepted scientific evidence separately.
5. Do not describe MQTT/TLS or Ditto pre-authentication as substitutes for
   DIDComm, SSI or verifiable credentials.
6. **Workload lineage.** The smartwatch profile is the workload aligned with
   the paper's published evaluation (one simulated smartwatch at 1 Hz over
   MQTT/SSL). The smart-ring and smart-clothing profiles are **extensions
   introduced by this dissertation** and have no counterpart in the published
   evaluation; never present the three-device concurrent workload as
   something the paper already evaluated.
7. **`twin_creation` is first-contact technical provisioning**, not the
   C2DTA business twinning ceremony. The measured condition covers the
   controller creating the Ditto policy/thing pair on the first valid event
   of an unknown `device_uuid` and the twin becoming readable. The paper's
   twinning scenario — Ownership Verifiable Credential matched against the
   Genesis Verifiable Credential, with ledger participation — is not
   implemented and is not what this condition measures. The scenario name is
   a frozen contract identifier and stays as it is; the delimitation lives in
   prose wherever a `twin_creation` number would be interpreted.
8. **The system under test is emulated.** It is an ARM64 guest emulated on an
   x86-64 workstation, and its four virtual CPUs and 8 GiB are emulator
   settings, not a demonstrated equivalence to a four-core physical gateway
   and not a consumer-controlled physical gateway. No native ARM64 host was
   used, so no statement about ARM hardware capacity, physical-device
   latency or energy efficiency follows from this work. State this as a
   limitation wherever deployment conclusions are drawn.
