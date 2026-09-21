# Gateway requirements and initial SoC platform selection

**Version:** 1.0 — 2026-09-21
**Owner:** Rui Duarte
**Purpose:** connect gateway requirements, an initial physical-platform choice,
Yocto configuration and the evidence needed to evaluate the C2DTA local twin core.

**Initial engineering recommendation:** use **Raspberry Pi 5 with 8 GB RAM** as
the documentary reference target for a possible physical gateway. Retain the
**NXP IMX95LPD5EVK-19** as an industrial alternative and reject Raspberry Pi 4
for the current MongoDB 7 stack. These are source-based screening decisions,
not results of board execution. The mandatory implementation and evaluation
environment remains the integrated Yocto ARM64 guest under QEMU/TCG.

This matrix implements the student's request of 2026-09-21 to create the matrix
and add the supervisor's deliverables to the plan. The supervisor email pasted
by the student requests requirements, an initial SoC choice, a manageable first
implementation and a build-focused literature review. Its example RQs are
guidance, not a recorded replacement of the previously reported wording.
The original email's sending timestamp and mailbox metadata were not supplied.

The [integrated plan](../governance/INTEGRATED_DEVELOPMENT_PLAN_2026.md) owns
scope and dates; [PROGRESS](../../PROGRESS.md) owns current deliverable state.
This document defines criteria and decisions, not gate acceptance. No hardware
purchase, cloud allocation, native port or change to public contracts follows
from this selection. Any such execution would require a separate scope and
resource decision.

## 1. Environments and interpretation of requirements

| Role | Platform | What it can establish |
|---|---|---|
| Development and build | Existing x86-64 Windows/WSL2 workstation and versioned Yocto configuration | Build and tooling behaviour in the recorded environment |
| Mandatory evaluation | Yocto ARM64 kernel and root filesystem under QEMU/TCG, hosting the six ARM64 containers; generator outside the guest on the same physical host | Bounded functional and integration behaviour; informational timing and resource observations labelled emulated |
| Initial physical reference target | Raspberry Pi 5, 8 GB, subject to the checks in section 4 | Documentary compatibility and a concrete future porting target; no physical behaviour has been measured |
| Optional future ARM cloud | A separately specified native ARM64 platform capable of booting the intended image | Software behaviour on that cloud configuration, if executed; not the selected board's peripherals, power, thermals or secure boot |

Four virtual CPUs and 8 GiB guest RAM are emulator settings, not a demonstrated
equivalence to four physical cores or a minimum RAM requirement. The generator
shares host resources with QEMU. No emulation slowdown factor converts its
results into physical latency, throughput or capacity. Any future native data
must have a separate protocol and must never be pooled with emulated data.

**Priority and authority labels:** P0 means required in the existing execution
scope or the newly requested documentary deliverables. TARGET means a
documentary condition for selecting a future physical target, not a new native
execution obligation. Existing contract and gate criteria keep their current
authority. D007-dependent numerical criteria remain proposals until the
required decision before protocol freeze; a value present in code is not
automatically an approved product requirement. FUTURE capabilities are excluded
from mandatory implementation.

## 2. Requirements and verification matrix

The source abbreviations below refer to repository documents listed in section
6. Hardware sources S1–S11 are listed in section 7. Every acceptance statement
is prospective; consult PROGRESS for actual evidence and outstanding work.

### 2.1 Functional behaviour and recovery

| ID / priority | Requirement and source | Acceptance criterion | Component and evidence / gate |
|---|---|---|---|
| REQ-01 / P0 | Run the gateway on the booted Yocto system. Existing plan sections 3.1 and 4.3 | The identified Yocto kernel/rootfs boots and all six ARM64 services run inside that guest; no host-side substitution | kas, meta-egw, Compose; boot, health and deployment records; G2/G3 |
| REQ-02 / P0 | Demonstrate one complete wearable-to-twin path. Existing G2 criterion | One smartwatch at 1 Hz for 60 s: 60 valid identities accounted for, no loss, late confirmation or double acceptance; twin readable with expected values under the existing confirmation rule | Simulator, broker, controller, Ditto/API; runbook section 6, identity reconciliation and image records; G2 |
| REQ-03 / P0 | Support three wearable profiles. CONTRACTS sections 2–4 | Correct schema and twin fields for smartwatch, smart ring and smart clothing in concurrent execution. The configured 1 + 0.2 + 10 = 11.2 messages/s is an offered workload, not demonstrated capacity | Schemas, simulator, controller and Ditto; integration test 2, per-device identities and twin state; G3 |
| REQ-04 / P0 | Reject invalid events before changing the twin. CONTRACTS section 5 | Invalid schema or inconsistent message_id is rejected; no corresponding Ditto mutation; valid events in the mixed run remain separately accounted for | Validator/controller; integration test 3 and schema/UUID checks; G3 |
| REQ-05 / P0 | Apply each event at most once and scope sequence checks per run. CONTRACTS section 4 | Replay does not double-apply an event; a new run_id permits seq to restart at zero; persisted ingestion state seeds deduplication after restart | Controller and Ditto ingestion feature; integration test 4 including itest-dup-02; G3 |
| REQ-06 / P0 | Retain stored twin state across controlled service restart and guest reboot. Existing G2/G3 criteria | State agrees before/after restart with volumes retained and no intervening publication; reboot recovery is a separate check | MongoDB volumes, Compose and startup; runbook section 6.5 and integration test 8; G2/G3 |
| REQ-07 / P0 | Recover from disconnect and controller restart with explicit event accounting. Existing G3 criteria | Exercise real disconnect/reconnect and restart; reconcile every identity against the applicable unchanged runbook expectations and clock window. Persisted twin state does not prove persistence of an in-flight queue | MQTT, simulator buffers, controller queue and Ditto; integration tests 5–6, pre/post state and failure logs; G3/G4 |
| REQ-08 / P0 | Handle dependency failures with bounded retry and explicit outcomes. CONTRACTS section 5 | Transient failures use the configured three attempts and 200 ms base backoff; 4xx is not retried. Exercise both MongoDB and Ditto faults and record accepted/failed outcomes without assuming lossless delivery | Controller HTTP client/readiness; integration test 7 and itest-ditto-fault-01; G3 |

### 2.2 Hardware, connectivity, security and Yocto

| ID / priority | Requirement and source | Acceptance criterion | Component and evidence / gate |
|---|---|---|---|
| REQ-09 / TARGET | CPU instruction set must support the retained stack. MongoDB 7 production notes, S9 | Document Armv8.2-A or later and availability of the actual linux/arm64 images. ISA compatibility is necessary, not sufficient proof that the full stack runs | Board CPU/BSP plus image identities; candidate screening now, real boot/container execution only in future native work |
| REQ-10 / P0 + TARGET | Size processing and memory from observed demand. Supervisor feedback and current emulator configuration | Record per-service and guest demand, queue behaviour, OOM/restarts and host contention in a pilot. State the proposed RAM budget and its limitations; do not infer a physical CPU/RAM minimum | Guest/containers/JVMs and collector; sizing note at G4. Pi 5 8 GB is an initial reference configuration, subject to native validation |
| REQ-11 / P0 + TARGET | Provide persistent storage for OS, images, state and bounded logs/evidence. Runbook storage and persistence checks | Budget these items separately, define retained data and margin, and verify free space for the selected campaign. The current approximately 32 GiB data-disk setting is not a physical minimum | Filesystem, volumes and log retention; capacity worksheet at G4 and REQ-06. Prefer SSD/eMMC for a future persistent-data deployment, subject to board verification |
| REQ-12 / P0 | Provide IP transport with the contracted MQTT protections. CONTRACTS section 1 | MQTT on TLS port 8883, QoS 1, authenticated access and no anonymous connection; record configured interface and connection path | Mosquitto, simulator and controller; slice plus integration test 9; G2/G3. Ethernet is the initial board route; physical BLE/Wi-Fi integration is FUTURE |
| REQ-13 / P0 | Enforce technical access restrictions and identify the consumer-control boundary. CONTRACTS sections 1, 4 and 8 | Exercise configured ACL and authorisation refusals; document credentials, secret handling and exposed interfaces. Distinguish the service principal from a consumer identity | Broker ACL, Ditto policies and service networks; test 9 and the V1 scope inventory; G3/G6. Functional refusal checks are not a security assurance |
| REQ-14 / P0 + TARGET | Use a documented Yocto release, machine and BSP combination. Current Scarthgap baseline and S3/S6/S11 | Record release, machine, layer dependencies and exact revisions before any board build. Preserve the current QEMU target. Published BSP support alone does not validate meta-egw on a board | kas, meta-egw, kernel/runtime features and boot/storage/network support; documentary platform decision now, separate build/boot verification if native work is authorised |

### 2.3 Configuration, evaluation and traceability

| ID / priority | Requirement and source | Acceptance criterion | Component and evidence / gate |
|---|---|---|---|
| REQ-15 / P0 | Identify the complete runtime and deployment inputs. Plan G4 and deployment scripts | Bind Yocto image, kernel, execution mode, container digests and controller build to each run; complete the Python dependency lock with hashes before freeze | kas/manifests, image lock and controller build record; deployment verification and G4 |
| REQ-16 / P0 | Evaluate against an explicit workload and valid observations. CONTRACTS section 9 and plan G4 | Record requested and achieved load, clock boundaries, per-container CPU/RAM and validity checks; keep controller-reception-to-Ditto-ACK latency distinct from sensor-to-durable-storage latency | Harness, events and collectors; pilot and prospective protocol at G4, admitted data at G5. D007 numeric criteria remain unresolved; timing/resources stay informational under emulation |
| REQ-17 / P0 | Establish bounded stability through a feasible frozen campaign. Plan section 3.3.1 | Pilot verifies feasibility before choosing conditions/repetitions/durations. Retain the reported target of 95 attempts including a 24-hour soak; preserve negative results and document prospective amendments | Pilot, campaign and analysis; G4/G5. Neither the target nor a short pass proves prolonged stability |
| REQ-18 / P0 | Preserve requirements-to-evidence and literature traceability. Supervisor feedback and plan evidence rules | Each retained requirement maps to a decision, component, test and admitted result or explicit limitation; preserve hashes and failed attempts. Record actual searches, screening and the source supporting each build decision | This matrix, scoping-review records, evidence index and claim matrix; documentary work now, reconciliation at G4/G6/G7 |

**Numerical criteria requiring care.** TLS/QoS, the nominal profile rates,
retry settings and the existing 60 s confirmation window are retained contract
values, not new supervisor approvals. The protocol contains candidate
performance, recovery and coverage thresholds pending D007. This matrix neither
approves them nor weakens them. Its hardware selection introduces no maximum
wearable count, physical latency target, energy target, boot-time target or
minimum storage/RAM claim. See the existing
[protocol constants](../../src/egw_experiments/protocol.py) and plan section 4.3.

## 3. Initial comparison of physical platforms

First eliminate incompatible candidates, then compare BSP fit, resources and
integration effort. No weighted score is used: unverified procurement costs,
delivery dates and native behaviour would make an aggregate score misleading.
The comparison is documentary, checked on 2026-09-21.

| Criterion / requirement | Raspberry Pi 5, 8 GB | NXP IMX95LPD5EVK-19 | Raspberry Pi 4 |
|---|---|---|---|
| CPU / REQ-09 | BCM2712, four Cortex-A76 cores; Armv8.2-A [S1–S3] | i.MX95, six Cortex-A55 application cores; Armv8.2-A [S4–S5] | Cortex-A72; explicitly excluded by MongoDB 7 production notes [S9–S10] |
| ISA screening | Pass, documentary only | Pass, documentary only | Reject for the retained MongoDB 7 stack |
| Memory / REQ-10 | Selected variant: 8 GB LPDDR4X [S1]; starting budget, not a proven minimum | EVK has 16 GB LPDDR5 [S4]; additional RAM is not measured efficiency | RAM options do not remove the CPU incompatibility |
| Persistent storage / REQ-11 | microSD; PCIe 2.0 x1 supports NVMe with an additional adapter/HAT [S1] | 64 GB eMMC and microSD [S4] | No further assessment after ISA exclusion |
| Connectivity / REQ-12 | Gigabit Ethernet, Wi-Fi and Bluetooth/BLE [S1]; use Ethernet for initial IP integration | 1 GbE and 10 GbE, Wi-Fi/Bluetooth module [S4] | No further assessment after ISA exclusion |
| Yocto route / REQ-14 | meta-raspberrypi scarthgap contains MACHINE=raspberrypi5 with the Cortex-A76 tune [S3] | NXP documents imx-linux-scarthgap, manifest imx-6.6.52-2.2.0.xml and MACHINE=imx95-19x19-lpddr5-evk [S6] | A BSP cannot repair the retained application's unsupported CPU |
| Physical security capabilities / REQ-13 | Secure boot is documented; vendor notes no hardware secure enclave [S7]. Configuration and validation would be additional work | EdgeLock Secure Enclave [S8]; enabling and validating its services is additional work | Not evaluated |
| Porting effort, engineering judgement | Medium: board machine/BSP, boot, storage, network and all services still need validation | Medium to high: vendor BSP/distribution and firmware integration; NXP warns of limitations when using community Poky [S11] | Do not port the current stack |
| Procurement | Stock, delivered price, supply, cooling, storage and adapter costs not verified | Exact kit/revision, stock, price and lead time not verified | No procurement assessment needed |
| Initial position | Preferred documentary reference target | Reserve alternative if industrial security or connectivity becomes a justified requirement | Excluded under current software choices |

The NXP manifest above is a documented Scarthgap example, not a claim that it is
the latest recommended vendor release. The branch URLs identify the research
route; exact commits must be selected and checked before a build. Neither BSP
has been integrated with this project's pinned layers by this matrix.

## 4. Decision and conditions to revisit it

The initial recommendation is Pi 5 with 8 GB because it passes the required ISA
filter, has a directly documented Scarthgap machine configuration and offers
the IP connectivity and storage expansion needed for the proposed gateway.
The expectation of lower integration effort than the NXP alternative is an
engineering judgement, not a measured benchmark, price comparison or guarantee.
It is deliberately provisional: CPU core count and clock frequency do not
establish throughput, and the shared ARMv8.2 ISA does not make the QEMU machine
a Pi 5 simulator.

Before any physical work, resolve:

1. Exact BSP/layer revisions and compatibility with the project's image,
   runtime and firmware requirements.
2. Measured memory/storage demand and a documented margin; 8 GB remains a
   reference choice until that evidence exists.
3. Total delivered cost, availability, power supply, cooling and storage
   configuration; use a separately authorised budget rather than applying an
   old cloud ceiling to board procurement.
4. Native boot, network, storage, reboot and execution of the actual pinned
   images; no current QEMU result substitutes for these tests.
5. Whether the dissertation needs any native validation at all. The new
   supervisor feedback asks for platform selection but does not explicitly
   withdraw the adopted QEMU evaluation scope.

Revisit the choice if the Pi BSP cannot support the required image, the resource
budget does not fit, procurement makes it impractical, or hardware-rooted
security becomes mandatory. A change to the database solely to enable Pi 4
would reopen compatibility and evidence work; it is not recommended for the
current schedule. None of these future checks blocks continued QEMU integration.

## 5. Research questions, V1 scope and new deliverables

### 5.1 Crosswalk without renumbering approved questions

The existing scope summary and manuscript RQ numbering are preserved. The
supervisor's proposed sequence can be discussed through this crosswalk:

| Supervisor example | Content to prepare | Relationship to the current questions |
|---|---|---|
| Requirements | REQ-01–REQ-18, sources, acceptance and evidence boundaries | Makes explicit the engineering basis currently implicit across all three RQs |
| SoC selection and Yocto configuration | Sections 3–4, machine/BSP decision and versioned configuration | Extends the rationale supporting current RQ1; does not create a native deployment result |
| Compliance under representative workloads | Functional results, informational emulated observations and unverified hardware properties | Current RQ2 and QEMU-bounded RQ3, with requirements traceability |

For implementation tracking, use this mapping to the retained scope summaries:

| Current question | Requirement IDs informing its answer |
|---|---|
| RQ1 — Versioned Yocto gateway and deployment | REQ-01, REQ-09–REQ-15 and REQ-18; physical-platform requirements support the design rationale, not a native execution claim |
| RQ2 — Correct and reliable wearable event handling | REQ-02–REQ-08, REQ-12–REQ-13 and REQ-18 |
| RQ3 — Behaviour and limitations in the specified emulated environment | REQ-10–REQ-11, REQ-16–REQ-18; no physical capacity, efficiency or energy conclusion |

Any replacement wording must be reconciled across the manuscript, scope and
plan in deliverable SUP-04. Preparing that wording does not assert supervisor
approval, renumber claims or turn the proposed SoC into the evaluated platform.

### 5.2 V1 boundary to show in the architecture deliverable

| Treatment | Components or functions |
|---|---|
| Reuse | Mosquitto, Ditto, MongoDB and upstream Yocto components; identify provenance, without implying all code was copied from C2DTA |
| Adapt/configure | Image/kernel/runtime, Compose, networks, persistent volumes, credentials, broker ACL and Ditto service policies |
| Project development | MQTT-to-Ditto controller, wearable schemas/mappings, simulator and evidence tooling, according to their repository provenance |
| V1 technical control | Authenticated ingestion, service permissions and local twin administration/readback; the service subject is pre:egw-controller |
| Deferred consumer/ecosystem functions | Consumer identity/ownership credentials, consent/revocation workflow, authorised twinning/untwinning, DIDComm, ledgers and decentralised data transfer |

Deferred functions remain outside mandatory implementation; this table does
not promise them in a later sprint of this dissertation. Secure boot, physical
Bluetooth, OTA, an application UI and AI execution are likewise not added.
An inventory of technical permissions does not establish consumer sovereignty.

### 5.3 Delivery references

The plan's section 4.1.1 defines SUP-01 (requirements), SUP-02 (platform
decision), SUP-03 (V1 architecture), SUP-04 (RQ/manuscript crosswalk), SUP-05
(demonstrator evidence), SUP-06 (literature-to-decision chart) and SUP-07
(requirements-to-results reconciliation). Dates, dependencies and acceptance
belong to the plan; operational completion belongs to PROGRESS.

## 6. Repository sources

- [Public contracts](../../src/CONTRACTS.md): MQTT, schemas, profiles, policies,
  retry, persistence semantics, metrics and confirmation window.
- [Integrated runbook](../setup/qemu_integrated_gateway.md): deployment,
  first flow, persistence, nine test families and pilot.
- [Current Compose definition](../../src/deployment/compose.yaml) and
  [integrated Yocto profile](../../src/yocto/kas/egw-qemuarm64-integrated.yml):
  configuration, not measured physical requirements.
- [C2DTA traceability](c2dta_p0_traceability.md): local-core boundary and
  differences from the reference architecture.
- [Scoping-review protocol](../../thesis/research/literature_review_protocol.md),
  [search log](../../thesis/research/search_log.csv) and
  [selection register](../../thesis/research/study_selection.csv): preserve real
  search/reading history. Technical web checks supporting this matrix do not
  constitute an executed academic selection search.
- [Scope and RQs](../g0/scope_and_rqs.md),
  [decisions](../governance/supervisor_decision_log.csv) and
  [claim matrix](../claim_evidence_matrix.md): existing wording and admission
  rules remain in force.

## 7. Primary external sources checked on 2026-09-21

| ID | Source and specific use |
|---|---|
| S1 | [Raspberry Pi 5 product specification](https://www.raspberrypi.com/products/raspberry-pi-5/): SoC, RAM variants, interfaces and storage expansion |
| S2 | [Arm Cortex-A76 technical reference manual](https://documentation-service.arm.com/static/5f562083235b3560a01e03bc): architecture features |
| S3 | [meta-raspberrypi Scarthgap machine definition](https://github.com/agherzan/meta-raspberrypi/blob/scarthgap/conf/machine/raspberrypi5.conf): 64-bit machine and Cortex-A76/Armv8.2 tune; maintained BSP source, not a Raspberry Pi hardware-vendor support guarantee |
| S4 | [NXP IMX95LPD5EVK-19 specification](https://www.nxp.com/design/design-center/development-boards-and-designs/IMX95LPD5EVK-19): application cores, memory, eMMC and interfaces of this exact kit |
| S5 | [Arm Cortex-A55 technical reference manual](https://documentation-service.arm.com/static/5e7e09f6a3736a0d2e862d2f): architecture features |
| S6 | [NXP AN14760](https://www.nxp.com/docs/en/application-note/AN14760.pdf), revision 2.0, 2026-04-21, page 4: Scarthgap manifest and machine example for the selected EVK |
| S7 | [Raspberry Pi secure-boot documentation](https://github.com/raspberrypi/usbboot/blob/master/docs/secure-boot.md): configuration route and secure-enclave limitation |
| S8 | [NXP i.MX95](https://www.nxp.com/products/i.MX95): EdgeLock Secure Enclave capability; not project validation |
| S9 | [MongoDB 7 production notes](https://www.mongodb.com/docs/v7.0/administration/production-notes/): Armv8.2-A minimum and explicit Raspberry Pi 4 exclusion |
| S10 | [Raspberry Pi 4 specification](https://www.raspberrypi.com/products/raspberry-pi-4-model-b/): BCM2711/Cortex-A72 identification |
| S11 | [NXP Scarthgap manifest documentation](https://github.com/nxp-imx/imx-manifest/blob/imx-linux-scarthgap/README.md): vendor distribution and community-Poky compatibility caveat |

Source checks establish published capabilities at the stated date. They do not
establish supplier stock, total cost, a successful build or native deployment.
