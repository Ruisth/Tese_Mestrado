# Integrated Edge Gateway Dissertation Plan — version 1.2

> **Status: NORMATIVE FOR PROJECT EXECUTION.** This document controls scope,
> evidence boundaries, gates, cut rules and delivery dates from 2026-08-13.
> [`PROGRESS.md`](../../PROGRESS.md) is the only source of current operational
> state. Exact public title and research-question wording remain proposed until
> supervisor decision D001 is recorded.

**Version:** 1.2 — 2026-08-14  
**Supersedes:** version 1.1 — 2026-08-13 (which superseded version 1.0 — 2026-08-07)  
**Official deadline:** 2026-09-30  
**Internal submission cut-off:** 2026-09-29, 17:00 Europe/Lisbon  
**Contingency:** 2026-10-31 only if formally available; no scope growth  
**Repository language:** British English; Portuguese is retained where required

The unchanged Portuguese version 1.0 is archived at
[`archive/PLANO_DESENVOLVIMENTO_INTEGRADO_EDGE_GATEWAY_2026_v1.0_pt.md`](archive/PLANO_DESENVOLVIMENTO_INTEGRADO_EDGE_GATEWAY_2026_v1.0_pt.md)
with SHA-256
`53233a44d6967ded9e33eb6a9c6d2721ff44d0f003ce389fb58cd502a9f64b8d`.

## 1. Authority, maintenance and state

| Subject | Authoritative record | Rule |
|---|---|---|
| Scope, schedule, gates and cuts | This plan | A change requires a dated new version; history is never rewritten. |
| Current deliverable and gate state | [`PROGRESS.md`](../../PROGRESS.md) | Only `Pending`, `In progress`, `Blocked`, `Complete` and `Cut` are permitted. |
| Formal gate outcomes | [`gate_decision_log.md`](gate_decision_log.md) | Evidence or a merged change never implies acceptance; every outcome needs a dated decision record. |
| Public implementation interfaces | [`src/CONTRACTS.md`](../../src/CONTRACTS.md) | Version 1.1 is frozen for this restructuring; material changes require an ADR and regression tests. |
| Claims and admissible evidence | [`claim_evidence_matrix.md`](../claim_evidence_matrix.md) | No claim is accepted without the evidence named in the matrix and a recorded gate decision. |
| Supervisor decisions | [`supervisor_decision_log.csv`](supervisor_decision_log.csv) | A draft, sent request, silence or agent recommendation is not approval. |
| Raw experimental records | `experiments/results/raw/` plus checksums | Write once. A correction or repeat receives a new identity. |
| Work diary | [`LOG.md`](../../LOG.md) | Records actions and links to evidence; it does not override state or scope. |

Update `PROGRESS.md` and the applicable evidence records in the same work block
that changes them. An artefact existing in the repository means only
*implemented*. Static checks or unit tests mean *verified locally*. Neither
means a claim or gate is accepted.

## 2. Baseline at 2026-08-13

This is a dated planning baseline, not a replacement for live state in
`PROGRESS.md`.

| Area | Baseline | Consequence |
|---|---|---|
| Repository | `Claude/` is the active project and its tree was reconciled with the private GitHub `dev` branch. `ChatGPT/` is a divergent legacy workspace. | No automatic merge from `ChatGPT`; preserve it read-only and migrate only reviewed documentary conclusions. |
| Unit evidence | The latest sealed record reports 701 passing unit tests. No live integration test has been executed. | The implementation is predominantly M1–M2; unit tests against fakes cannot support live-system claims. |
| Yocto/QEMU | An `egw-image` build and two automated bring-up boots are sealed. The exact build commit is protected by `evidence/g1-yocto-build-5770c0a`. | G1 has preliminary functional evidence but remains **In progress** until its new acceptance campaign and formal decision. QEMU supports no performance claim. |
| Service stack | Compose, controller, simulator and harness exist; there is no recorded live MQTT→controller→Ditto trace. | G2 and later gates remain blocked or pending on a real ARM64 environment. |
| Experiments | There are zero official campaign runs and 0 of 15 claims accepted. | No number may enter results or conclusions before protocol and data freezes. |
| ARM64 measurement host | No non-burstable measurement VM is recorded. | A burstable host may be used for integration only; RQ3 data require the fixed measurement class below. |
| Academic work | The dissertation skeleton and a substantive Chapter 2 draft exist. Exact title/RQs, template, review label and reproducibility wording are not supervisor-approved. | Send the alignment pack and track D001–D008. Factual corrections do not wait for approval. |
| G0 external actions | The supervisor email is drafted but no sending evidence is recorded; the ARM64 risk-report cut date has elapsed. | Sending and infrastructure procurement remain student actions. Repository changes cannot discharge them. |

## 3. Scientific contract and evidence boundary

### 3.1 Two-layer artefact

The dissertation evaluates two complementary but separately scoped layers:

1. **Functional platform layer:** a versioned Yocto/Scarthgap `qemuarm64`
   container-host image, tested for build, boot, systemd health, networking and
   an OCI smoke container.
2. **Digital-twin service layer:** Mosquitto, Eclipse Ditto, MongoDB, the
   MQTT-to-Ditto controller, simulator and experimental harness deployed on a
   fixed native ARM64 VM.

The dissertation must not claim that the Ditto service stack runs inside the
Yocto image unless separate future evidence demonstrates that deployment.
Likewise, QEMU observations must never be used for latency, throughput or
resource conclusions.

### 3.2 Proposed public framing (decision D001 pending)

**Working title:** *Design and Experimental Evaluation of a Two-Layer ARM64
Edge Gateway Prototype for the Local Digital-Twin Core of C2DTA*

1. **RQ1:** How can a two-layer ARM64 Edge Gateway prototype be designed, built
   and redeployed when its Yocto/QEMU functional platform and native-ARM64
   containerised digital-twin stack are treated as separate artefact layers?
2. **RQ2:** To what extent can the prototype ingest and materialise concurrent
   synthetic telemetry from three wearable-device types correctly and
   reliably, including under specified fault scenarios?
3. **RQ3:** What latency, sustainable-throughput, saturation and per-container
   resource trade-offs constrain the digital-twin stack on a non-burstable
   native-ARM64 environment?

Until D001 and D006 are resolved, repository documents may use this working
framing, but the final title must not use *reproducible*. A successful clean
second-operator reconstruction is required before that stronger term returns;
otherwise use *versioned* and *repeatable build by the author*.

### 3.3 Mandatory P0

- Exact, versioned Yocto/Scarthgap manifests; build and strict QEMU functional
  validation.
- Native ARM64 deployment of Mosquitto TLS, Eclipse Ditto 3.9.4, MongoDB and
  the MQTT-to-Ditto controller using ARM64 images fixed by digest.
- A deterministic CLI simulator for smartwatch, smart ring and smart clothing,
  covering smoke, nominal, load sweep, dropout/reconnect, invalid payload,
  restart/recovery and soak behaviour required by the frozen protocol.
- Unit, live integration, end-to-end, recovery, load and stability checks with
  sealed evidence.
- A fixed ARM64 experimental campaign, reproducible analysis and a complete
  English dissertation grounded only in admitted evidence.

### 3.4 Explicit exclusions

ACA-Py, DIDComm, Fabric, Indy, IPFS, wallets, executable SSI/blockchain flows,
Bluetooth, OTA, dashboards, UI, AI/multi-agent services, physical Raspberry Pi
measurements, energy measurement, x86 performance comparison and marketplace
features are excluded from both the September path and any October
contingency. They may appear only in the C2DTA reference architecture,
limitations and future work. Reopening any item requires an explicit new plan
version after the thesis core is accepted; spare time alone is not authority.

## 4. Delivery sequence and gates

| Window | Gate | Required result | Baseline state on 2026-08-13 |
|---|---|---|---|
| 13–15 Aug | **G0 — authority and provenance** | Alignment email sent; D001–D008 requested; plan v1.1 and immutable provenance records versioned; university ARM64 request made. | **Blocked:** sending and measurement-host actions have no recorded evidence. |
| 13–18 Aug | **G1 — Yocto/QEMU functional platform** | Evidence-integrity blockers fixed; a clean identified build; five strict boots, each with `systemd=running`, zero failed units, required network/runtime checks and a clean shutdown; evidence checksums pass; decision recorded. | **In progress:** one build and two bring-up boots exist; the five-boot acceptance set and gate decision do not. |
| 15–23 Aug | **G2 — live vertical slice** | Native ARM64 deployment with TLS and an inspectable wearable→MQTT→controller→Ditto→API trace; live integration tests pass. | **Blocked:** no measurement VM and no live trace. |
| 24–30 Aug | **G3 — P0 feature freeze** | Three wearables and all mandatory nominal/failure/reconnect/restart behaviours run live; contracts frozen; no open P0 defect. | **Pending.** |
| 31 Aug–6 Sep | **G4 — experimental freeze** | A complete non-citable micro-pilot succeeds; environment, protocol, run plan, thresholds, exclusions and analysis are sealed as `exp-v1`. | **Pending; D007 blocks freeze.** |
| 7–13 Sep | **G5 — data freeze** | The complete 95-run campaign, including soak, is captured write-once with manifests and verified checksums as `data-v1`. | **Pending.** |
| 14–18 Sep | **G6 — analysis and full draft** | Analysis regenerated solely from admitted raw data; tables, figures, confidence intervals and claim states updated; complete draft sent. | **Pending.** |
| 19–25 Sep | **G7 — release candidate** | Complete thesis with no placeholders; independent review and reproduction package; all accepted claims trace to evidence. | **Pending.** |
| 26–29 Sep | **Submission** | Blocking corrections only; stable promotion, final release, off-machine bundle, final PDF and submission receipt by 29 Sep 17:00. | **Pending.** |

### Gate and cut rules

- A gate closes only through a dated decision linked from `PROGRESS.md`; passing
  assertions does not close it automatically.
- If no university measurement host is confirmed within 48 hours of the
  request, obtain a price quotation for a non-burstable public ARM64 instance
  with 4 vCPU, 8 GiB RAM and at least 80 GB. AWS `c6g.xlarge` is the default
  fallback. Do not provision above the student's EUR 30 total ceiling.
- A burstable instance may unblock G2 integration but no measurement from it is
  admissible in the dissertation.
- If G2 has no valid vertical slice by 25 August, record a serious September
  risk and reforecast without adding scope.
- After G4, no metric, threshold, condition or exclusion rule changes. A defect
  that invalidates evidence creates a new protocol/data version and reruns the
  affected conditions.
- After G5, no feature work is permitted. Missing evidence becomes an explicit
  limitation; it is never replaced by an inferred result.
- Silence from supervisors is not approval. D001 and D004 block final academic
  release; D007 blocks `exp-v1`.

## 5. Preconditions before live evidence

The following are blockers, not optional quality improvements:

- resource CSV validation must use the actual measured UTC start/end, require
  temporal overlap, at least 90% coverage and the frozen maximum gap;
- a simulator `run_id` must be write-once and fail before opening any existing
  raw artefact;
- the QEMU wrapper must propagate `kas` failure through `tee`;
- an accepted boot requires `systemd=running` and zero failed units; a reviewed,
  exact predeclared allow-list is the only possible exception;
- gateway ping remains an observation, not a scientific gate, until a supervisor
  decision changes that status;
- the native ARM64 runtime must have a complete dependency lock with hashes,
  installed using hash enforcement, plus recorded `pip check`, image digests and
  host manifest before `exp-v1`.

Negative tests must demonstrate rejection of a correct-duration CSV outside the
measured window, insufficient coverage, unordered timestamps, excessive gaps,
reuse of a `run_id`, masked `kas` failure, degraded/failed-unit boot, and a
changed or unhashed runtime dependency.

## 6. Academic alignment work

Send the standalone Chapter 2 draft with
[`supervisor_alignment_memo.md`](supervisor_alignment_memo.md) and request the
eight decisions in [`supervisor_decision_log.csv`](supervisor_decision_log.csv).
Follow up on 18 August and request a short meeting on 20 August if no response is
recorded.

Factual changes do not require supervisor permission:

- describe the paper's platform as Eclipse Ditto 3.0.0 and Mosquitto integrated
  with ACA-Py, Fabric, Indy and IPFS, not as a custom ledger-centred twin
  platform;
- report its seven use cases/88 steps and x86 evaluation accurately, and state
  that only its telemetry workload uses one simulated smartwatch at 1 Hz;
- do not compare its x86 figures directly with the ARM64 campaign;
- maintain two editable diagrams: the full five-layer C2DTA reference
  architecture with implemented/deferred boundaries, and this experiment's
  two-layer deployment;
- map each Edge Gateway function in the paper to the P0 component, retained
  interface/stub and future work;
- treat the seven supervisor questions as glossary, architecture, hosted
  software, DIDComm feasibility/exclusion, EGW importance and single-point-of-
  failure analysis, academically sourced decentralised-computing discussion,
  and professional relevance outside experimental results;
- complete institutional searches and full-text assessment before making
  corpus-wide novelty claims.

## 7. Acceptance contract

- A clean checkout installs the documented dependencies, runs the full test
  suite and builds all release documents without unresolved references.
- CI covers Python 3.11 and 3.14, schemas/contracts, shell safety, evidence
  checksums/links and LaTeX; long Yocto and ARM64 jobs remain manual.
- G1 has a clean identified build and five strict accepted boots. G2 has a real
  live trace; fakes do not count.
- The micro-pilot covers all conditions without creating citable results.
- Every planned run has a predeclared identity. Failure is retained, never
  deleted; a repeat has a new identity and lineage.
- Analysis excludes any run lacking its plan identity, manifest, host record,
  valid measured window or checksum.
- No result enters Chapters 5 or 6 before `data-v1`.
- The final dissertation has no TODOs, complete metadata, rendered diagrams,
  explicit limitations and evidence-bounded answers to all three RQs.
- `ChatGPT/` remains an intact read-only legacy area; no automatic code merge is
  permitted.

## 8. Provenance and change record

- External inputs and local-only binaries are registered in
  [`external_source_register.md`](external_source_register.md); they are not
  copied into the repository.
- Bundles, rewritten-history equivalences and the protected G1 build identity
  are registered in
  [`provenance-history-rewrite.md`](provenance-history-rewrite.md).
- The 8 August reviews are condensed as non-normative historical input at
  [`../reviews/historical/2026-08-08-legacy-review-synthesis.md`](../reviews/historical/2026-08-08-legacy-review-synthesis.md).
- Version 1.1 removes ACA-Py from conditional delivery, makes the two-layer
  evidence boundary explicit, rebases gates on 13 August, and separates state,
  decision and scope authorities. It does not retrospectively alter any raw
  evidence or accepted decision.
- **Version 1.2 (2026-08-14) is a governance correction with no substantive
  change: it changes no scope, schedule, gate, cut rule or authority beyond
  what is recorded here.** It exists because the published version 1.1 was
  amended in place on 2026-08-14 (merge `c6668a8`, pull request #19), which
  added the "Formal gate outcomes" row to the authority table in section 1 —
  a change to gate governance that, under this plan's own maintenance rule,
  required a dated new version at the time. Version 1.2 records that amendment
  retroactively and regularises the version line. The final state of version
  1.1 is the file as of merge `c6668a8`, recoverable from git history.
  **Citation equivalence:** references to "plan v1.1" in documents dated
  before 2026-08-14 — including sealed evidence, which is never edited —
  refer to the v1.1/v1.2 line and remain valid; they are not rewritten.
- Version 1.2 also registers two non-blocking supervisor confirmations added
  to the decision set on 2026-08-14: D009 (the term `telemetry` stays the
  versioned contract term in topics, schemas and CONTRACTS, while thesis prose
  prefers "wearable event data") and D010 (the EGW stack persists twin state
  and sealed run evidence locally by design, consistent with the C2DTA paper's
  data-steward role for the EGW). Both concern documented deviations from the
  repository template, which the external source register classifies as
  guidance rather than an implementation contract. Section 6's alignment
  package is read as requesting D001–D010.
