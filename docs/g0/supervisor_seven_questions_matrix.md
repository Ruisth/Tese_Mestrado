# Supervisor seven-question response matrix

**Document version:** 1.1

**Date:** 2026-08-13

**Status:** **PROPOSED - NOT SENT - NOT APPROVED**

This matrix converts the seven questions in the supplied supervisor document
into bounded, verifiable thesis or defence outputs. It is not evidence that a
response has been sent or accepted. Statements about C2DTA are grounded in the
supplied paper (`pinto2026c2dta`); implementation statements are grounded in the
current repository. Commercial forecasts and unsupported implementation-time
estimates are excluded.

| ID | Question theme | Evidence-bounded response | Deliverable and location | Scope consequence | State |
|---|---|---|---|---|---|
| Q1 | Acronyms used in the paper | Use the verified glossary in §1 below. It distinguishes paper terminology from names fixed by governing standards and from this prototype's implemented scope. | Dissertation acronym list plus §1 below | Editorial; no implementation change | Verified draft response |
| Q2 | Editable C2DTA component diagram | Provide the five paper layers - business, ecosystem, peer-to-peer, records and consumer edge - and mark each component as P0 implemented/configured or deferred. A second diagram separates the Yocto/QEMU functional artefact from the native-ARM64 service stack. | [`../../diagrams/c2dta_five_layer_reference.puml`](../../diagrams/c2dta_five_layer_reference.puml) and [`../../diagrams/two_layer_experimental_deployment.puml`](../../diagrams/two_layer_experimental_deployment.puml) | Makes the implementation boundary visible; no claim that the full C2DTA is implemented | Draft artefacts |
| Q3 | Software hosted on the EGW | Answer in two columns. The paper's EGW combines a DT platform, broker, identity agents, ledger interfaces and decentralised-storage transfer. P0 contains Mosquitto, a minimal Eclipse Ditto core, MongoDB and the MQTT-to-Ditto controller on the native-ARM64 service layer; the Yocto/QEMU layer checks an OCI runtime only. | Software inventory in [`../academic/c2dta_p0_traceability.md`](../academic/c2dta_p0_traceability.md) | Prevents conflating paper software with P0 | Draft response |
| Q4 | Difficulty of implementing DIDComm | The bounded technical answer is in §2 below. A framework-based demonstration and an implementation from protocol primitives are materially different tasks; neither effort has been measured in this project, so no calendar estimate is claimed. | Scope/limitations discussion and oral-defence note | No DIDComm implementation is added to the critical path | Technical answer drafted; D002 pending |
| Q5 | Why the EGW is central | The paper assigns the EGW connectivity, twin hosting, ledger interfacing, historical-data transfer, device onboarding and consumer-edge stewardship, while acknowledging it as a single point of failure. State which functions P0 implements and which remain absent. | Function-to-P0 matrix in [`../academic/c2dta_p0_traceability.md`](../academic/c2dta_p0_traceability.md) | Requires an explicit single-point-of-failure limitation | Draft response |
| Q6 | Decentralised computing, peers and thought leaders | The provisional, corpus-limited answer is in §3 below. It separates consumer-edge placement and custody from multi-peer computation, and refuses a ranking of people that the current review method cannot support. | Background/future-work outline; bibliography work item | Context and future work only; no additional P0 feature | Provisional answer; institutional/full-text pass pending |
| Q7 | Career opportunities | Keep this outside the evidence chain. Describe transferable competencies - ARM64/Linux, Yocto, containers, IoT messaging, digital twins, experiment design, evidence controls and technical writing - as motivation or defence material, not as a scientific contribution or labour-market claim. | Defence notes or personal career memo, not the results chapter | No thesis claim and no implementation change | Draft response |

## 1. Q1 — verified acronym glossary

The following forms were checked on 2026-08-13 against the controlled C2DTA
full text or the linked governing source. The list records terminology; it does
not imply that every listed technology is implemented by P0.

| Term | Verified form | Authority and scope note |
|---|---|---|
| C2DTA | Consumer-Controlled Digital Twin Architecture | Supplied full-text paper, controlled as EXT-001 in the [`external-source register`](../governance/external_source_register.md); [version-of-record DOI](https://doi.org/10.1016/j.bcra.2025.100342). This is the reference architecture, not the name of the P0 implementation. |
| DT | Digital Twin | C2DTA paper terminology. |
| EGW | Edge Gateway | C2DTA paper terminology. |
| SD | Smart Device | C2DTA paper terminology. |
| SSI | Self-Sovereign Identity | C2DTA paper terminology; contextual and not executable P0 scope. |
| DID | Decentralized Identifier | [W3C DID Core 1.0](https://www.w3.org/TR/did-core/). The standard's US spelling is retained in the expansion. |
| VC | Verifiable Credential | [W3C Verifiable Credentials Data Model 2.0](https://www.w3.org/TR/vc-data-model-2.0/). |
| DIDComm | DIDComm Messaging | [DIF DIDComm Messaging specification](https://identity.foundation/didcomm-messaging/spec/). It is the official protocol name, not an expansion inferred from the letters. |
| DLT | Distributed Ledger Technology | C2DTA paper terminology. |
| ACA-Py | Aries Cloud Agent - Python | Current [official ACA-Py documentation](https://aca-py.org/latest/). This is the project name used by the maintained implementation; it is not a generic expansion inferred from the acronym. |
| IPFS | InterPlanetary File System | C2DTA paper terminology; decentralised storage is excluded from P0. |
| WoT | Web of Things | [W3C Web of Things Thing Description 1.1](https://www.w3.org/TR/wot-thing-description11/). |

The normative dissertation acronym list now includes C2DTA because Chapter 2
uses the term. Other context-only acronyms should be added there only when they
are actually used in the dissertation text.

## 2. Q4 — bounded technical answer on DIDComm implementation

No defensible estimate in days or weeks follows from the current evidence: the
effort changes materially with the required interoperability, credential and
operational-security boundary. A proof using a maintained framework and an
implementation from protocol primitives are different engineering projects.

Using ACA-Py avoids implementing the low-level cryptography and many exchange
protocols directly, but it does not reduce integration to enabling one option.
An implementation would still have to:

1. choose supported DID methods, key types, resolution and secure key/storage
   arrangements; DID documents expose verification methods and service
   endpoints, while resolution behaviour depends on the DID method
   ([W3C DID Core](https://www.w3.org/TR/did-core/));
2. implement the application controller that drives ACA-Py's HTTP Admin API and
   handles webhook events, then protect that administrative interface; the
   [official ACA-Py architecture and API overview](https://aca-py.org/latest/)
   makes this controller boundary explicit;
3. establish relationships, for example through the
   [Aries out-of-band protocol](https://identity.foundation/aries-rfcs/latest/features/0434-outofband/),
   and select the exact protocol/profile subset to interoperate with;
4. configure and test DIDComm message protection, transport, routing or
   mediation, asynchronous delivery, error handling and recovery against the
   [DIF DIDComm Messaging specification](https://identity.foundation/didcomm-messaging/spec/);
5. add secrets management, persistence/backup, negative tests and
   interoperability tests with another independently configured agent.

Implementing from primitives would additionally make this project responsible
for the plaintext, signed/encrypted envelope processing, cryptographic
algorithm and key-agreement choices, routing and protocol state machines that a
framework supplies. That is a larger and higher-assurance task, not a small
extension of the MQTT-to-Ditto controller. Plan v1.1 §3.4 therefore excludes
DIDComm and ACA-Py from P0 and from every unapproved contingency. D002 asks the
supervisors to confirm that boundary; its pending state is not authority to
implement the feature.

## 3. Q6 — provisional academic answer, limited to the current corpus

This answer is deliberately narrower than a general survey of decentralised
computing. As recorded in [`study_selection.csv`](../../thesis/research/study_selection.csv),
the supplied C2DTA paper is available and assessed in full text, whereas the
general edge-computing seeds by Shi et al. and Satyanarayanan and the recent
high-availability study by Neagu et al. remain at title/abstract assessment.
Institutional searches and the remaining full-text pass have not been
completed. Detailed claims are therefore made only from C2DTA; the other works
identify literature directions, not yet validated conclusions.

Within that verified boundary, C2DTA decentralises placement and custody: it
moves twin hosting and selected ecosystem interactions towards a
consumer-controlled EGW instead of leaving them entirely in a provider cloud.
The same paper explicitly identifies that EGW as a single point of failure.
Consequently, *consumer-edge placement* is supported by the source, but a
resilient multi-peer or multi-EGW computation fabric is not a demonstrated
property of either C2DTA's evaluated deployment or this P0 prototype
([C2DTA DOI](https://doi.org/10.1016/j.bcra.2025.100342)).

The current corpus contains relevant starting points for the broader context:
[Shi et al.](https://doi.org/10.1109/JIOT.2016.2579198) and
[Satyanarayanan](https://doi.org/10.1109/MC.2017.9) for edge computing, and
[Neagu et al.](https://doi.org/10.3390/fi18030137) for high availability of
edge-hosted twins. Until their full texts are assessed under the registered
protocol, this matrix does not attribute a specific architecture, result or
consensus to them. Distributed EGWs, federation, privacy-preserving computation
and multi-EGW resilience remain research directions for the literature pass
and future-work chapter; none becomes a P0 requirement or result.

Finally, the current review is neither bibliometric nor designed to rank
people. It can identify relevant peer-reviewed works and standards bodies, but
cannot defensibly name "thought leaders" or repeat commercial rankings. Any
such mapping would require an explicit, transparent bibliometric method and a
completed corpus; it is not necessary to answer the dissertation's RQs.

## Closure rule

A row closes only when its deliverable exists, has been reviewed against its
source and, where it changes scope, has the corresponding supervisor decision.
Creating the artefact does not imply supervisor acceptance.
