# Two-layer thesis framing proposal

> **Superseded on 2026-09-18.** The student adopted the integrated objective with the QEMU-only execution amendment as [plan v2.0](../governance/INTEGRATED_DEVELOPMENT_PLAN_2026.md), and the scope it governs is [`scope_and_rqs.md`](scope_and_rqs.md) version 2.0. The two-layer framing below is therefore historical. Neither the adopted plan nor this unapproved August proposal has been sent to or agreed by the supervisors: the academic title and research-question wording remain a request under D001/D011, and the student's adoption settles execution only. Preserved text below is historical, including its unsupported x86 attribution for the base paper — the paper's evaluation hardware ISA is unspecified and that attribution is not carried forward; do not reuse any of it as a current factual description.

**Document version:** 1.0

**Date:** 2026-08-13

**Status:** **PROPOSED - NOT SENT - NOT APPROVED**

**Decision owner:** supervisors and student

**Normative effect:** none

This memo isolates a proposed academic reframing for supervisor review. It does
not modify the title, objective, research questions, abstract or Resumo in the
normative LaTeX dissertation. Integration is blocked on an explicit decision
for D001. The companion
[`supervisor_decision_matrix.csv`](supervisor_decision_matrix.csv) describes
the requested decisions and recommendations; the single authoritative record
of their state is
[`../governance/supervisor_decision_log.csv`](../governance/supervisor_decision_log.csv).
Silence is not approval.

## 1. Problem addressed by the proposal

The repository currently contains two related but distinct artefact layers:

1. a Yocto/QEMU functional platform that builds and boots `egw-image` and checks
   systemd, networking and an OCI runtime; and
2. a containerised digital-twin stack intended for a separate native-ARM64
   machine: Mosquitto, Eclipse Ditto, MongoDB and the MQTT-to-Ditto controller.

The current evidence does not show Eclipse Ditto running inside the Yocto
image. Treating the layers separately prevents the title and RQ1 from implying
that deployment. The layers retain a common repository, versioned contracts and
claim-to-evidence chain, but each has its own deployment and acceptance test.

## 2. Proposed title

> **Design and Experimental Evaluation of a Two-Layer ARM64 Edge Gateway
> Prototype for the Local Digital-Twin Core of C2DTA**

This title deliberately uses `prototype`, not `reproducible`. The latter remains
reserved until the artefacts have been reproduced from a clean checkout by an
independent second operator, or until the supervisors approve a narrower and
explicit operational definition under D006.

## 3. Proposed objective

Design and experimentally evaluate a versioned, two-layer ARM64 Edge Gateway
prototype for the local digital-twin core of C2DTA. The first layer provides a
Yocto/QEMU functional platform for repeatable build and boot checks. The second
layer deploys the containerised twin services separately on native ARM64 to
ingest, validate and materialise concurrent synthetic telemetry from three
wearable-device types. Functional correctness, reliability, sustainable
throughput, saturation and per-container resource use are evaluated without
treating QEMU or burstable instances as performance platforms.

## 4. Proposed research questions

1. **RQ1:** *How can a two-layer ARM64 Edge Gateway prototype be designed, built
   and redeployed when its Yocto/QEMU functional platform and native-ARM64
   containerised digital-twin stack are treated as separate artefact layers?*
2. **RQ2:** *To what extent can the prototype ingest and materialise concurrent
   synthetic telemetry from three wearable-device types correctly and
   reliably, including under specified fault scenarios?*
3. **RQ3:** *What latency, sustainable-throughput, saturation and per-container
   resource trade-offs constrain the digital-twin stack on a non-burstable
   native-ARM64 environment?*

## 5. Proposed abstract wording

> **PROPOSED TEXT - no results or conclusion may be added before `data-v1`.**
>
> The Consumer-Controlled Digital Twin Architecture (C2DTA) moves a smart
> device's digital twin to the consumer edge, but its published implementation
> evaluates a broad identity-, ledger- and storage-enabled architecture on an
> x86 virtual machine. This dissertation proposes a two-layer ARM64 Edge
> Gateway prototype for the local digital-twin core of C2DTA. The first layer
> is a versioned Yocto/QEMU platform used only to verify image construction,
> boot, networking, systemd and an OCI runtime. The second is a separately
> deployed native-ARM64 container stack comprising Eclipse Mosquitto, Eclipse
> Ditto, MongoDB and an MQTT-to-Ditto controller. A deterministic simulator
> generates concurrent telemetry for a smartwatch, smart ring and smart
> clothing under nominal, load and fault scenarios. A pre-specified protocol
> evaluates functional correctness, reliability, controller-side latency,
> sustainable throughput, saturation and per-container resource use. QEMU and
> burstable cloud instances are excluded from performance inference. SSI,
> DIDComm, blockchain ledgers, decentralised storage and marketplace functions
> are represented as C2DTA context and future integration boundaries, not as
> implemented or evaluated contributions. Results and conclusions will be
> inserted only from the sealed `data-v1` campaign.

## 6. Proposed Resumo wording

> **TEXTO PROPOSTO - sem resultados ou conclusão antes de `data-v1`.**
>
> A Consumer-Controlled Digital Twin Architecture (C2DTA) transfere o gémeo
> digital de um dispositivo inteligente para a periferia sob controlo do
> consumidor, mas a implementação publicada avalia uma arquitetura mais ampla,
> com identidade, registos distribuídos e armazenamento, numa máquina virtual
> x86. Esta dissertação propõe um protótipo ARM64 de Edge Gateway com duas
> camadas para o núcleo local de gémeos digitais do C2DTA. A primeira camada é
> uma plataforma Yocto/QEMU versionada, usada apenas para verificar a construção
> da imagem, o arranque, a rede, o systemd e um runtime OCI. A segunda é uma
> pilha de contentores instalada separadamente em ARM64 nativo, composta por
> Eclipse Mosquitto, Eclipse Ditto, MongoDB e um controlador MQTT-to-Ditto. Um
> simulador determinístico gera telemetria concorrente de smartwatch, smart
> ring e smart clothing em cenários nominais, de carga e de falha. Um protocolo
> pré-especificado avalia correção funcional, fiabilidade, latência interna do
> controlador, débito sustentável, saturação e recursos por contentor. QEMU e
> instâncias cloud burstable não suportam inferências de desempenho. SSI,
> DIDComm, blockchains, armazenamento descentralizado e marketplace são contexto
> arquitetural e fronteiras de integração futura, não contribuições
> implementadas ou avaliadas. Os resultados e as conclusões serão acrescentados
> apenas a partir da campanha selada `data-v1`.

## 7. Scope boundary carried by the wording

- **Evaluated P0:** Yocto/QEMU functional checks; separate native-ARM64
  Mosquitto-to-controller-to-Ditto path; three synthetic wearable types;
  specified nominal, load, recovery and soak conditions.
- **Reference architecture only:** ACA-Py, DIDComm, Hyperledger Fabric,
  Hyperledger Indy, verifiable credentials, IPFS, marketplace, ownership
  transfer, Bluetooth, physical Raspberry Pi and AI/MAS.
- **No cross-platform causal claim:** the paper's x86 deployment describes the
  predecessor implementation; it is not a performance baseline for ARM64.
- **No premature result claim:** the wording above contains methods and intended
  measurements only. Results remain absent until sealed evidence exists.

## 8. Integration rule after review

If D001 is explicitly approved, update the LaTeX title, objective, RQs,
abstract, Resumo, contribution statement and RQ-to-claim matrix in one reviewable
change. If D001 is rejected or revised, replace this proposal with a new
version; do not partially integrate it. D006 independently controls use of the
word `reproducible`.
