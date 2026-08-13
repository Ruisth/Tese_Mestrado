# C2DTA paper-to-P0 traceability and software inventory

**Document version:** 1.1

**Date:** 2026-08-13

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
that the native-ARM64 service stack has passed a live test or that a gate has
been accepted.

## 1. Edge Gateway function traceability

| EGW function in the paper | P0 implementation or closest bounded analogue | Executable stub/interface status | Deferred integration or research |
|---|---|---|---|
| Consumer-edge connectivity hub linking smart devices and controller agents to the ecosystem through DIDComm | Synthetic devices publish MQTT/TLS telemetry to Mosquitto; the controller consumes the contracted topic. This is a telemetry path, not a DIDComm replacement. | No DIDComm stub. [`Plan v1.1` §3.4](../governance/INTEGRATED_DEVELOPMENT_PLAN_2026.md) is the normative exclusion; D002 remains a proposed supervisor confirmation in the authoritative [`decision log`](../governance/supervisor_decision_log.csv). ADR 0002 is superseded historical context, not implementation authority. | ACA-Py agents, OOB establishment, DIDs and DIDComm messaging |
| Host the smart-device digital-twin platform | Native-ARM64 Compose configuration contains Eclipse Ditto 3.9.4 gateway, policies and things, MongoDB and the controller. Live ARM64 deployment remains pending. | Real P0 service configuration and controller code exist; only unit/fake evidence is current. | Validate the live vertical slice; full C2DTA Ditto service set only if a later research scope requires it |
| Interface with the ecosystem ledger for device status | Not implemented. Ditto's local ingestion feature and experiment manifests do not constitute an ecosystem ledger. | None | Hyperledger Fabric transactions, lifecycle state and chaincode integration |
| Interface with the identity ledger for credential verification and issuance | Not implemented. Ditto pre-authentication is a local deployment mechanism, not SSI or credential verification. | None | Hyperledger Indy or another approved DID/VC registry and credential flows |
| Transfer historical twin data to decentralised storage | Not implemented. Local event logs and experiment raw data are evidence artefacts, not the paper's decentralised dataset service. | No dataset-export or IPFS interface is contracted in P0. | Dataset builder, provenance metadata and IPFS/decentralised-storage transfer |
| Authorise smart-device onboarding before twinning and untwinning | The controller creates a Ditto policy and thing on the first valid event. This is deterministic P0 provisioning, not C2DTA ownership or SSI authorisation. | Real first-contact policy/thing flow; no owner credential, agent or twinning/untwinning protocol stub | Consumer/device agents, ownership credentials and authorised twin/untwin lifecycle |
| Support one or multiple smart devices | The simulator and schemas cover smartwatch, smart ring and smart clothing with stable identifiers; live concurrent ingestion is not yet evidenced. | Real simulator, schemas and thing identifiers; current evidence is unit-level | Physical devices, discovery/Bluetooth and wider device-model catalogue |
| Move compute and twin custody towards the consumer edge | The design targets a native-ARM64 edge-class service host and a separately versioned Yocto/QEMU functional platform. No physical household gateway has been evaluated. | Deployment artefacts exist; the measurement VM is not provisioned and QEMU is functional-only. | Physical consumer-controlled hardware, redundancy, failover and multi-EGW federation |
| Protect integrity/privacy while remaining a single point of failure | MQTT/TLS, broker ACLs, validation and Ditto policies are configured. They do not establish the full paper security model, and no security evaluation or failover claim exists. | Security configuration exists; live verification and recovery evidence are pending. | Threat-model validation, key lifecycle, redundancy and recovery across EGWs |

## 2. Software and platform inventory

| Concern | Supplied C2DTA paper | Current P0 repository | Evidence boundary |
|---|---|---|---|
| Host platform | Docker on a Proxmox/QEMU/KVM-based x86 VM, reported as 16 GB RAM and 32 CPUs | Layer A: Yocto Scarthgap/`qemuarm64` functional image. Layer B: separate native-ARM64 VM target | G1 contains a Yocto build and two QEMU boots; no live Layer-B deployment exists |
| Telemetry broker | Eclipse Mosquitto; MQTT over SSL for the smartwatch path | Eclipse Mosquitto 2.0.22, digest-pinned; MQTT/TLS on port 8883, QoS 1 | Configuration exists; live end-to-end evidence is pending |
| Digital-twin platform | Eclipse Ditto 3.0.0 with gateway/routing, connectivity, things, policies, search and database services | Eclipse Ditto 3.9.4 minimal core: gateway, policies and things | Digest-pinned Compose configuration exists; no current live ARM64 evidence |
| Persistence | Ditto database and encrypted-at-rest deployment; historical datasets transferred to decentralised storage | MongoDB 7.0.39 for Ditto state; local append-only experiment artefacts are a separate concern | MongoDB image is pinned; decentralised historical-data transfer is absent |
| Gateway controller | EGW agent/controller participates in device onboarding, twinning and ecosystem interactions | Python MQTT-to-Ditto controller validates schemas, handles first contact, applies updates and records outcomes | Controller behaviour has unit/fake evidence; no live broker-to-Ditto trace yet |
| Identity and secure agent messaging | ACA-Py/Hyperledger Aries agents, controllers and wallets; DIDs, VCs, OOB and DIDComm | Not implemented | Excluded from P0 and every unapproved contingency by [`plan v1.1` §3.4](../governance/INTEGRATED_DEVELOPMENT_PLAN_2026.md); D002 is pending supervisor confirmation, not permission to implement |
| Ecosystem ledger | Hyperledger Fabric | Not implemented | No stub or result claim |
| Identity ledger | British Columbia Test Indy Network | Not implemented | No stub or result claim |
| Decentralised storage | IPFS | Not implemented | No dataset builder or IPFS interface in P0 |
| Workload generator | Dedicated smartwatch simulator producing heart rate, geolocation and timestamp data at 1 Hz | Deterministic simulator for smartwatch, smart ring and smart clothing across six planned scenarios | Simulator is unit-tested; official live campaign has not run |
| Evaluation automation | Gherkin scripts and ACA-Py Test Harness; eight scenarios defined, first seven evaluated across 88 steps | Pytest suite plus a custom experimental harness and pre-specified run plan | 701 unit tests are sealed; no live integration campaign or `data-v1` exists |

The Mosquitto version typography in the supplied paper appears as `2.0.1.5` in
the extracted manuscript text. This inventory therefore names the paper's
broker without normalising that version; any exact version copied into the
dissertation must first be checked against the version of record.

## 3. Comparison rules for the dissertation

1. Compare architecture, scope and evaluation method, not raw x86 and ARM64
   performance values.
2. State that the paper defines eight lifecycle scenarios and evaluates the
   first seven across 88 steps; do not compress this into an ambiguous claim
   that the architecture has only seven use cases.
3. State that the smartwatch's 1 Hz telemetry path is one part of the broader
   C2DTA evaluation, not its entire workload.
4. Label repository artefacts, static tests, live integration evidence and
   accepted scientific evidence separately.
5. Do not describe MQTT/TLS or Ditto pre-authentication as substitutes for
   DIDComm, SSI or verifiable credentials.
