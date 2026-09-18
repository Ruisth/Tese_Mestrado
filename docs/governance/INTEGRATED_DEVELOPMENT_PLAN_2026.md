# Integrated Yocto ARM64 Edge Gateway Dissertation Plan — version 2.0 (adopted 2026-09-18, QEMU-only execution amendment)

> **Status: NORMATIVE FOR PROJECT EXECUTION.** This document controls scope,
> evidence boundaries, gates, cut rules and delivery targets from 2026-09-18,
> the date on which the student adopted it. It carries a dated **QEMU-only
> execution amendment** that takes precedence over any native-host
> prerequisite, native-performance promise or obsolete status statement
> elsewhere in this document, in the proposal text it supersedes or in any
> document that cites them.
> [`PROGRESS.md`](../../PROGRESS.md) is the only source of current operational
> state.
> **The supervisors have approved nothing.** The exact public title and
> research-question wording remain *proposed* until supervisor decisions D001
> and D011 are recorded. The student's adoption settles execution; it does not
> settle academic agreement. Adopting a plan version closes no gate, admits no
> claim and turns no emulated result into native ARM64 evidence.
> The student reported that a supervisor advised proceeding with QEMU tests.
> That is student-reported advice: it is neither approval nor a documented
> supervisor decision, and it is not recorded as one in
> [`supervisor_decision_log.csv`](supervisor_decision_log.csv), where D001–D014
> are all `proposed_not_sent`.
> Every date after 2026-09-18 in this plan is a planning target, not an
> achieved milestone.

**Version:** 2.0 — adopted 2026-09-18 (text of 2026-09-16 with the QEMU-only
execution amendment of 2026-09-18)  
**Supersedes:** version 1.2 — 2026-08-14 (which superseded
version 1.1 — 2026-08-13, which superseded version 1.0 — 2026-08-07)  
**Planned submission:** 2026-10-20  
**Final delivery deadline:** 2026-10-31; 2026-10-21 to 2026-10-31 is a
contingency window for essential corrections only, never the default delivery
period  
**Source of both dates:** the student's confirmation of 2026-09-18 after
discussing them with the supervisors — a first-party statement; no
administrative document has been checked (D013)  
**Repository language:** British English; Portuguese is retained where required

The unchanged Portuguese version 1.0 is archived at
[`archive/PLANO_DESENVOLVIMENTO_INTEGRADO_EDGE_GATEWAY_2026_v1.0_pt.md`](archive/PLANO_DESENVOLVIMENTO_INTEGRADO_EDGE_GATEWAY_2026_v1.0_pt.md)
with SHA-256
`53233a44d6967ded9e33eb6a9c6d2721ff44d0f003ce389fb58cd502a9f64b8d`. The
unmodified version 1.2 is archived at
[`archive/INTEGRATED_DEVELOPMENT_PLAN_2026_v1.2.md`](archive/INTEGRATED_DEVELOPMENT_PLAN_2026_v1.2.md)
with SHA-256
`c346e4d958d22fad6d4f4635b4176bc2c1b584407199b165a197f94ef0e9fa53`, verified
byte for byte against the `dev` revision `9179612` at the moment of archiving
on 2026-09-18.

The `archive/` directory holds plan versions only, because the plan is the
document this project cites by version number. Subordinate documents that are
republished with the plan — the scope document
[`../g0/scope_and_rqs.md`](../g0/scope_and_rqs.md), republished as version 2.0
on 2026-09-18 — are not copied into `archive/`: their superseded text is
preserved in the repository history at the revision each document names, and
each carries a **Supersedes** line pointing at it. Neither route permits
rewriting a superseded text.

## 1. Authority, maintenance and state

| Subject | Authoritative record | Rule |
|---|---|---|
| Scope, schedule, gates and cuts | This plan | A change requires a dated new version; history is never rewritten. |
| Current deliverable and gate state | [`PROGRESS.md`](../../PROGRESS.md) | Only `Pending`, `In progress`, `Blocked`, `Complete` and `Cut` are permitted. |
| Formal gate outcomes | [`gate_decision_log.md`](gate_decision_log.md) | Evidence or a merged change never implies acceptance; every outcome needs a dated decision record. Adopting a plan version accepts no gate. |
| Public implementation interfaces | [`src/CONTRACTS.md`](../../src/CONTRACTS.md) | Version 1.1 is frozen for this restructuring; material changes require an ADR and regression tests. |
| Claims and admissible evidence | [`claim_evidence_matrix.md`](../claim_evidence_matrix.md) | No claim is accepted without the evidence named in the matrix and a recorded gate decision. |
| Supervisor decisions | [`supervisor_decision_log.csv`](supervisor_decision_log.csv) | A draft, sent request, silence or agent recommendation is not approval. |
| Raw experimental records | `experiments/results/raw/` plus checksums | Write once. A correction or repeat receives a new identity. |
| Work diary | [`LOG.md`](../../LOG.md) | Records actions and links to evidence; it does not override state or scope. |

Update `PROGRESS.md` and the applicable evidence records in the same work block
that changes them. An artefact existing in the repository means only
*implemented*. Static checks or unit tests mean *verified locally*. Neither
means a claim or gate is accepted.

### 1.1 What was adopted on 2026-09-18, and by whom

- **The student adopted** this plan, version 2.0, with the QEMU-only execution
  amendment, as the execution baseline of the project. The amendment makes the
  integrated system under test the Yocto-produced ARM64 kernel and root
  filesystem booted under QEMU/TCG on the existing x86-64 workstation. Native
  ARM64 deployment leaves mandatory scope and becomes documented, unverified
  future work (section 8).
- **The supervisors have approved nothing.** They have not agreed the title, the
  research-question wording, the experimental thresholds or the revised academic
  evaluation. No alignment package has been sent; every row of
  [`supervisor_decision_log.csv`](supervisor_decision_log.csv) is
  `proposed_not_sent`.
- **Student-reported advice.** The student reported that a supervisor advised
  proceeding with QEMU tests. It is recorded here as the student's report of
  advice received, and nowhere as an approval or a supervisor decision.
- **Adoption admits nothing.** It closes no gate, admits no claim, seals no
  evidence and makes no emulated result native evidence. Formal gate outcomes
  remain solely in [`gate_decision_log.md`](gate_decision_log.md).
- **Authority basis.** The student is the decision owner for project execution.
  The academic framing remains reserved to the supervisors through D001, D004,
  D006, D007, D011 and D014.

## 2. Baseline at 2026-09-18

This is a dated planning baseline, not a replacement for live state in
`PROGRESS.md`. It replaces the 2026-08-13 baseline of version 1.2, which is
preserved unmodified in the archived v1.2 file and is not rewritten here.

| Area | Baseline | Consequence |
|---|---|---|
| Repository | `Claude/` is the active project and its tree was reconciled with the private GitHub `dev` branch. `ChatGPT/` is a divergent legacy workspace. | No automatic merge from `ChatGPT`; preserve it read-only and migrate only reviewed documentary conclusions. |
| Unit evidence | The latest sealed record reports 701 passing unit tests, all against fakes. **No test of the nine integration/recovery families of the runbook has been run.** | Unit tests against fakes cannot support live-system claims; the integration battery is the next work package. |
| Yocto/QEMU platform (sealed) | The integrated image build (commit `03e333e`), two boots with every acceptance check passing (commit `3209b17`) and an isolated MongoDB 7.0.39 test are sealed under [`docs/evidence/integrated-qemu/`](../evidence/integrated-qemu/). Gate G1 was accepted on 2026-08-14 for the functional platform layer only. | Sealed technical evidence, all emulated. Sealing is not acceptance and G1 is not relabelled as an integrated validation. |
| Service stack in the guest (unsealed) | On 2026-09-18 the six-container stack was deployed inside the emulated Yocto guest and one bounded end-to-end flow passed: one smartwatch at 1 Hz for 60 s; 60 sent, 60 delivered unique, 0 lost, 0 late, 0 duplicate, 0 failed, 0 rejected; twin `org.c2dta:5689c879-…` with `last_seq` 59; reconciliation by identity exited 0. The maximum latency observed, 12,286 ms, is an emulated observation and not a performance result. | **Candidate evidence held outside the repository and unsealed.** It admits no claim, closes no gate and is not citable until sealed and admitted. The statements that the stack has never been deployed and that the first flow has not run are corrected by this row. |
| Defects found by that flow | The controller was attached to the wrong Compose network (fixed in `9ffd365`) and the host shell inherited a relative schema directory (fixed in `dc6d8bb` and `22fb0a9`). | The first live exercise behaved as the harness risk predicted. Fixing the defects closes no gate. |
| Open stability incident | A memory-cgroup OOM killed the `ditto-things` JVM **during the power-off** of that session at a 512 MiB container limit. The diagnosis of 2026-09-18 records the three Ditto services idling at 94–95 % of that limit and reaching 98.1 % after a 672-message workload, and a controlled `docker compose stop -t 60` after that workload producing no OOM anywhere in the boot. | The corrective work — a graceful stop before power-off, and container memory sizing — is **open** and is a separate change. The stack is not described as stable, and stability is not declared before the incident is resolved or its scope explicitly bounded and recorded. |
| Experiments | There are zero official campaign runs and 0 of 15 claims accepted. | No number may enter results or conclusions before protocol and data freezes. |
| Execution environment | The evaluation environment is the emulated integrated guest: ARM64 under QEMU/TCG on the x86-64 workstation (Windows 11, WSL2 Ubuntu-24.04). No native ARM64 host exists and none is required by this plan. | RQ3 is bounded to that environment (section 3.5). Native measurement is documented, unverified future work (section 8); no cloud allocation, spending or native build is requested by this plan version. |
| Academic work | The dissertation skeleton and a substantive Chapter 2 draft exist. Exact title/RQs, template, review label and reproducibility wording are not supervisor-approved. | Send the revised alignment package and track D001–D014. Factual corrections do not wait for approval. |
| G0 external actions | The alignment package is drafted but no sending evidence is recorded. | Sending the alignment package remains a student action that repository changes cannot discharge. Infrastructure procurement is **not** an obligation of this plan version. |

## 3. Scientific contract and evidence boundary

### 3.1 One integrated system under test

The operating-system platform and the application services remain a **logical
decomposition**, but they form **one system under test**: the versioned
Yocto-produced ARM64 kernel and root filesystem, booted under QEMU/TCG on the
existing x86-64 workstation, hosting the six-service local digital-twin stack —
Mosquitto, the MQTT-to-Ditto controller, Eclipse Ditto and MongoDB — as ARM64
containers inside that guest. The simulator and the experimental harness remain
outside the guest.

- A Yocto root filesystem used only as a container or chroot does **not** satisfy
  the objective: the measured kernel would still be the outer host's.
- Booting Yocto while Ditto runs on another Linux installation does **not**
  satisfy it either.
- The published integrated profile specifies four virtual CPUs and 8 GiB of RAM.
  Record the actual command and resources for every run. These are emulator
  settings; they are not a demonstrated equivalence to a four-core physical
  gateway.
- Retain the three wearable profiles, the nominal aggregate of 11.2 messages/s,
  the public JSON/API contracts, MQTT/TLS, authentication, the
  evidence-integrity controls and the fault/recovery scenario families.
- Preserve the controller-side monotonic latency boundary — reception by the
  controller to Ditto's acknowledgement. It is not the full sensor-to-storage
  latency and not proof of durable storage at that acknowledgement time.

The stack runs inside the Yocto guest under emulation: the demonstration of
2026-09-18 is functional evidence, held outside the repository, unsealed, and
admitting no claim. This supersedes the version 1.2 prohibition on claiming that
the Ditto service stack runs inside the Yocto image; that prohibition is
retained only for any *native* deployment, which remains undemonstrated.

### 3.2 Proposed public framing (decisions D001 and D011 pending)

The wording below is **suggested wording for academic review**. It is not
attributed to the supervisors, is not agreed with them, and is not settled by
the student's adoption of this plan.

**Working title:** *Design and Experimental Evaluation of a Yocto-Based ARM64
Edge Gateway for the Local Digital-Twin Core of C2DTA*

1. **RQ1:** How can a versioned Yocto-based ARM64 gateway image be built,
   deployed and redeployed under QEMU to host the local digital-twin core of
   C2DTA?
2. **RQ2:** To what extent can the integrated gateway ingest and materialise
   concurrent synthetic telemetry from three wearable-device types correctly and
   reliably, including under specified fault scenarios?
3. **RQ3:** What workload-dependent timing and resource-use behaviour, and
   operational limitations, are observed for the integrated gateway in the
   specified QEMU/TCG environment?

RQ3 is **bounded to emulation**. It does not retain the version 1.2 claim about
latency, sustainable throughput, saturation and per-container resource
trade-offs on a non-burstable native-ARM64 environment; that claim is withdrawn
from scope and becomes future work (section 8).

Until D001, D011 and D006 are resolved, repository documents may use this
working framing, but the final title must not use *reproducible*. A successful
clean second-operator reconstruction is required before that stronger term
returns; otherwise use *versioned* and *repeatable build by the author*. Agree
the final academic formulation and the evaluation protocol with the supervisors
before presenting either as approved.

### 3.3 Mandatory P0

- Exact, versioned Yocto/Scarthgap manifests; build and strict QEMU functional
  validation of the integrated image.
- Deployment of the six ARM64 containers — Mosquitto with TLS, Eclipse Ditto
  3.9.4, MongoDB and the MQTT-to-Ditto controller — **inside the Yocto guest
  under QEMU/TCG**, using ARM64 images fixed by digest. Digest pinning is
  unchanged.
- A deterministic CLI simulator for smartwatch, smart ring and smart clothing,
  covering smoke, nominal, load sweep, dropout/reconnect, invalid payload,
  restart/recovery and the bounded stability behaviour required by the frozen
  protocol.
- Unit, integration, end-to-end, recovery, load and bounded stability checks
  with sealed evidence, executed in the integrated emulated guest.
- An **emulated functional campaign**, selected and documented after the bounded
  pilot and before protocol freeze, with reproducible analysis and a complete
  English dissertation grounded only in admitted evidence. The 95-run campaign
  and the 24-hour soak of the previous plan are **not carried over** to the
  emulated environment. Every failed or inconclusive attempt is retained.

### 3.4 Explicit exclusions

ACA-Py, DIDComm, Fabric, Indy, IPFS, wallets, executable SSI/blockchain flows,
Bluetooth, OTA, dashboards, UI, AI/multi-agent services, physical Raspberry Pi
measurements, energy measurement, x86 performance comparison and marketplace
features are excluded from the submission path to 2026-10-20 and from the
contingency window of 2026-10-21 to 2026-10-31. They may appear only in the
C2DTA reference architecture, limitations and future work. Reopening any item
requires an explicit new plan version after the thesis core is accepted; spare
time alone is not authority.

Native ARM64 deployment and native performance evaluation are likewise excluded
from mandatory scope. They are documented, unverified future work (section 8),
not a P0 obligation, and spare time does not reopen them.

### 3.5 Evidence classes: emulated QEMU/TCG versus native ARM64

Carried into force from the amendment of 2026-09-18; the same rules are recorded
in [ADR 0008](../adr/0008-integrated-yocto-arm64-evaluation.md).

| Evidence class | Environment | What it may support |
|---|---|---|
| Emulated | ARM64 guest under QEMU/TCG on the x86-64 workstation | Functional and integration evidence only |
| Native | Non-burstable native ARM64 host, or QEMU/KVM on real ARM64 with verified acceleration | Performance and capacity results, and native-boot evidence — **none of which exists** |

1. **What emulated runs may demonstrate.** Build and redeployment of the
   versioned Yocto image; boot; the container runtime; deployment of the
   six-container stack inside the guest; the functional path smartwatch
   simulator → MQTT/TLS → controller → Ditto → API; correctness; fault handling
   and recovery; persistence. Of these, the build, the boot and the isolated
   MongoDB test are demonstrated and sealed; the stack deployment and the
   bounded functional path are demonstrated as unsealed candidate evidence held
   outside the repository (section 2). Timing observed under emulation may be
   recorded only as informational and must be labelled emulated.
2. **Still dependent on native ARM64.** Any statement about ARM hardware
   performance or capacity, and the native-boot evidence of the image (EFI and
   disk layout, the cloud-image route). Section 3.2's RQ3 is deliberately worded
   so that it does not require them.
3. **Permitted performance conclusions.** No conclusion about ARM64 hardware
   performance or capacity may be drawn from an emulated run. At most, relative
   observations may be reported, clearly labelled as emulated and not generalised
   beyond that environment. An emulated result is never native ARM64 performance
   evidence, and **any academic use of emulated results needs supervisor
   agreement** (D014).
4. **QEMU/TCG is never a performance measurement platform.** It yields functional
   and integration evidence only. The presence of the word QEMU does not, by
   itself, identify the execution mode; never infer KVM from the label ARM64 and
   never silently fall back from KVM to TCG.
5. **Reserved for the supervisors.** The academic title and RQ wording (D011),
   and the scope of the evaluation together with any academic use of emulated
   results (D014, now a standing request rather than a contingency). Their rows
   are `proposed_not_sent`; neither may be applied to the dissertation as if it
   were agreed.

**Recording requirements for every run.** Record the QEMU version, the TCG mode
and options, the virtual machine and CPU model, the vCPU count, the memory, the
guest image and kernel identities, the container identities, the workload and
the actual host/WSL configuration. Distinguish guest and container resource
readings from host QEMU-process readings, and never convert between them by an
assumed emulation slowdown factor. `uname -m = aarch64` alone is insufficient
identification. The external generator may share the physical workstation with
QEMU: record that contention and the achieved load, because running outside the
guest does not establish physical resource isolation.

**Never pool execution modes.** Emulated runs and any future native runs are
never combined into one statistic or one aggregate. Changing platform does not
authorise silently changing validity thresholds: the controller-clock
confirmation rule and the latency boundary are preserved.

## 4. Delivery sequence, gates and cut rules

### 4.1 Work packages and planning targets

The native/emulated branching schedule of the proposal text is replaced by a
single QEMU execution path. **The table below is a set of planning targets, not
achieved milestones, and no gate is accepted by it.**

| Work package | Target / acceptance boundary |
|---|---|
| Governance publication | Next focused documentation pull request; parallel to ongoing bounded tests |
| Nine integration/recovery test families | Target 2026-09-21 to 2026-09-24; report per-test evidence, failures and residual risks |
| Stable integrated QEMU baseline | Target 2026-09-25; no unresolved failure incompatible with the claimed stability scope |
| Bounded pilot and protocol freeze | Target 2026-09-26 to 2026-09-29; select run identities, repeats, durations and acceptance criteria prospectively |
| Frozen functional campaign | Target 2026-09-30 to 2026-10-02; only after a reviewed protocol and usable instrumentation |
| Data freeze and analysis | Target 2026-10-03 to 2026-10-05; all figures and tables traceable to immutable evidence |
| Chapters 1–4 sent | Target 2026-10-01; write in parallel, do not wait for all tests |
| Full draft sent | Target 2026-10-08 |
| Feedback, corrections and QA | Target 2026-10-09 to 2026-10-18; supervisor turnaround must be requested, not assumed |
| Packaging and submission | Package 2026-10-19; submit 2026-10-20 |
| Essential contingency only | 2026-10-21 to 2026-10-31; no new features and no native porting work |

Continue the existing bounded integration work; this plan does not require
restarting a valid run or repeating historical G1. Resolve or explicitly verify
the `ditto-things` teardown incident of section 2 before declaring stability.
Preserve the original first-flow evidence and every subsequent failed attempt.

Re-estimate the remaining technical and writing hours after the current
integration battery, splitting the estimate between the hours needed before the
full draft is sent and those after it. The previous range of 225–345 active
hours, estimated on 2026-09-16, is a **superseded estimate**: it was not a fresh
measurement, and one of its assumptions — the availability of a native ARM64
host — has failed. Automated execution time is never counted as the student's
writing capacity.

If a target fails, report the cause, the remaining work and a revised forecast on
the day it happens. Targets are never moved silently to the last day. The full
campaign still requires a reviewed, frozen protocol. No destructive storage
cleanup, remote expenditure or unlimited unattended run is authorised by the
adoption of this plan, and the existing test-operation safeguards remain in
force.

### 4.2 Gate set and current state

The gate names are unchanged: **G0 — authority and provenance**, **G1 —
Yocto/QEMU functional platform**, **G2 — live vertical slice**, **G3 — P0
feature freeze**, **G4 — experimental freeze** (tag `exp-v1`), **G5 — data
freeze** (tag `data-v1`), **G6 — analysis and full draft**, **G7 — release
candidate**, followed by **Submission**.

- **G0** remains *Not decided*. It keeps the alignment-package obligation:
  D001–D014 requested with the revised memo. The university ARM64 request and
  the measurement-host acquisition are **removed as gate conditions** and
  deferred with the native route; they are not deleted from history.
- **G1** remains **Accepted** (2026-08-14), for the functional platform layer
  only. It validated no claim, C01 and C02 remain partial, and nothing in this
  version reopens, relabels or extends it. The native Yocto boot formerly
  tracked as **G1B** is **withdrawn from mandatory scope and deferred** with the
  native route (section 8); it is not deleted, and it has never had a
  gate-decision row.
- **G2 to G7** are *Not decided*. Their prospective acceptance criteria are in
  section 4.3.

Formal gate outcomes live solely in
[`gate_decision_log.md`](gate_decision_log.md); `PROGRESS.md` remains the sole
record of operational state.

### 4.3 Prospective acceptance criteria for G2 to G7

**These criteria are prospective.** They state, before the work is done, what
would have to be true for the student to record a dated gate decision later.
Nothing here accepts a gate, admits a claim or records a supervisor agreement,
and no criterion below is reported as met.

**Conditions common to G2–G7.** A gate is not decidable if any of these fails.

1. **Labelling.** Every artefact, manifest, figure, table and sentence carries
   the emulation label: ARM64 emulated by QEMU/TCG on an x86-64 host; never
   native ARM64, never KVM.
2. **Identity binding.** Each run is bound to the Yocto image, kernel, boot mode,
   virtual machine and container identities.
3. **Sealing.** Evidence is copied write-once, a `SHA256SUMS` covers every file
   of the capsule except itself, and the capsule is verified by the repository's
   evidence check. A new capsule goes under `docs/evidence/<new-name>/` and never
   inside the sealed G1 capsule.
4. **Sealing is not acceptance**, and neither is a green documentation pull
   request.
5. **Failures kept.** Every failed or inconclusive attempt is preserved next to
   the successful ones; a repeat uses a new predefined run identity.
6. **No pooling of execution modes**, and **no result is a performance result**
   (section 3.5).

**G2 — live vertical slice.** One complete and inspectable wearable → MQTT/TLS →
controller → Ditto → API path inside the emulated guest, with: the six services
deployed from the versioned deployment tree and all healthy, the readiness and
health endpoints answering and the counters at zero before the run; every
deployed image `linux/arm64` and identified by its pinned digest, the controller
image verified against its build record before start-up; configuration
validation exiting cleanly with the broker secrets readable by the broker's
unprivileged user; one bounded flow (one smartwatch, 1 Hz, 60 s) meeting the
runbook acceptance list — confirmation deadline from the controller marker,
`lost = 0`, `delivered_unique = sent_valid`, no late confirmation, no
double-accepted record, no intended-invalid record accepted; reconciliation **by
identity** returning zero unaccounted records; every counter delta consistent
per device and per controller process; the twin readable through the API and
matching the contract; persistence across a service restart **shown, not
assumed**; TLS in force on the publishing path; and a complete evidence capsule
whose checksums verify. The flow of 2026-09-18 is candidate evidence held
outside the repository; it is not acceptance evidence, and G2 stays *Not
decided*. G2 establishes no native deployment, no timing or resource figure, no
stability over time and no claim admission.

**G3 — P0 feature freeze.** The nine integration/recovery test families of the
runbook executed in order on **one unchanged image and container set**, each
meeting its own expected list — three wearable types; invalid input rejected and
valid input accepted; duplicate replay detected with no double acceptance;
dropout and reconnection with no loss; controller restart with recovery inside
the bounded window and no record accepted twice; dependency fault and recovery
shown for both the database and the twin service; guest reboot with the
containers returning unaided, persistent state intact and a clean post-reboot
smoke run; and the transport and authorisation refusals, where an inconclusive
outcome is never reported as a pass. In addition: the public contracts frozen;
**no open P0 defect**, with the `ditto-things` memory incident of section 2
either resolved or its scope explicitly bounded and recorded before stability is
declared; every failed run retained; and **no threshold moved** — a result worse
than expected at the nominal rate is recorded as a sizing finding for the pilot,
never absorbed by changing the protocol. G3 establishes no performance, capacity
or efficiency property, no stability over time and no native behaviour.

**G4 — experimental freeze (`exp-v1`).** The bounded pilot complete, in order,
on the integrated emulated system: a short nominal run, the plan's nominal
duration, the load sweep and one bounded soak. The 24-hour soak and the 95-run
campaign are **not executed in this environment**. Generator delivery is checked
on every run; a run whose generator could not sustain the requested rate is a
pilot finding, not a measurement. Pilot data is **non-citable** and no pilot
number enters the dissertation. The measurement instrumentation is in place and
unit-tested: an `execution_mode` field with **no default**, so that an unset
value invalidates the run; the image identity; analysis grouped by execution
mode with pooling refused and every figure stamped with the mode; and a
wrong-provenance regression. Three environment records per run — guest, host
hypervisor (including the exact QEMU command line and the fact that the load
generator is co-located) and load generator. The existing validity rules do not
move, no flag is used to make a failing run pass, and slowness alone never
excludes a run. The frozen set — run identities, repeats, durations, acceptance
criteria and exclusion rules — is chosen prospectively and sealed with a
checksummed protocol package and an annotated tag. **D007 must be decided**
before `exp-v1` is recorded as the frozen protocol of the evaluation. After G4,
no metric, threshold, condition or exclusion rule changes.

**G5 — data freeze (`data-v1`).** The campaign executed is the **frozen emulated
functional set** selected after the pilot and before the freeze — explicitly not
the 95-run plan and not the 24-hour soak. Until that set is selected, G5's scope
is defined by that procedure rather than by a run count. Completeness is checked
**by identity**: the identities of the valid runs match the frozen plan exactly,
and identities missing, extra, duplicated or swapped fail the criterion and are
named. Sealing is mandatory per run; an unsealed or failing run is excluded from
every summary, acceptance and figure. Failures are preserved and only
evidence-invalidated conditions are rerun, under new identities with a recorded
lineage and a dated deviation record. The analysis is regenerated by the
delivered command from the admitted raw data, never pooling execution modes, and
every figure and table carries the emulated label. The freeze is a dated decision
linked from `PROGRESS.md`, with an annotated tag and an immutable raw tree. After
G5 there is no feature work; missing evidence becomes an explicit limitation and
is never replaced by an inferred result.

**G6 — analysis and full draft.** The analysis reproduced from the admitted
sealed raw data by one documented command, with a null difference against the
published artefacts. Every quantitative statement traces through the
claim-evidence matrix, and both forms of the matrix are updated together and
agree. Each research question is answered explicitly and inside its evidence
boundary: RQ1 and RQ2 from the integrated emulated evidence; the RQ3 answer
bounded to the emulated configuration, with the absence of native evidence
recorded as an explicit limitation in the agreed wording and never inferred. No
result enters the results chapters before `data-v1`. Only analysis, reproduction
and writing take place after G5. The full draft is sent, with a copy, the date
and the checksum of the compiled document recorded.

**G7 — release candidate.** A complete dissertation with no placeholders,
complete metadata, rendered diagrams and evidence-bounded answers to all three
research questions. The limitations section states the boundary explicitly: the
evaluation ran on an ARM64 guest emulated by QEMU/TCG on an x86-64 host; native
ARM64 deployment and native performance were not demonstrated; the reuse routes
for a later native target are documented and unverified. A reproduction package
with a versioned archive, its SHA-256, restore instructions, a verified
off-machine location and a restore check actually performed. Independent review
and supervisor contact recorded, including attempts, with silence waiving
neither D001 nor D004. Editorial QA complete, including the institutional AI-use
declaration and form. Every accepted claim traces to admitted evidence; claims
without evidence appear as limitations, never as conclusions. An annotated `rc1`
tag with the document checksum and an independent build/review record. The
deferred recipe-metadata corrections are closed no later than G7, at a
functional rebuild and never as a standalone edit.

**Which gates may be decided on emulated evidence.** The student may record a
dated *technical* outcome for G2 and G3 on emulated evidence, because deployment,
the functional path, correctness, fault handling, recovery and persistence are
exactly what rule 1 of section 3.5 allows an emulated run to demonstrate. For G4
and G5 the pilot and the runs may exist and be sealed, but the frozen set becomes
*the protocol and the data of the evaluation* only once D007 and D014 are
answered. G6 and G7 carry academic weight only with the supervisors' decisions:
D011 and D014 in both cases, D007 and D006 for the analysis and the
reproducibility wording, and D001 and D004 blocking the final academic release. A
gate decided on emulated evidence records that fact in its own row.

**Stated conflict, not resolved here.** The claim-evidence matrix and
`PROGRESS.md` both state that a QEMU result never supports a performance *or
security* statement, while the runbook's authorisation test produces transport
and authorisation evidence in exactly that environment. This plan records the
conflict rather than silently resolving it: until it is settled, that test's
output is treated as functional evidence of configured refusal behaviour in the
emulated guest and supports no security claim. The wording is to be settled with
the supervisors together with D014.

### 4.4 Gate and cut rules

- A gate closes only through a dated decision linked from `PROGRESS.md`; passing
  assertions, sealing evidence or merging a pull request does not close it
  automatically. Adopting a plan version accepts no gate and admits no claim.
- Historical G1 keeps its accepted functional scope. Nothing in this version
  reopens or extends it, and the sealed G1 capsule is never written to.
- After G4, no metric, threshold, condition or exclusion rule changes. A defect
  that invalidates evidence creates a new protocol/data version and reruns the
  affected conditions under new identities.
- After G5, no feature work is permitted. Missing evidence becomes an explicit
  limitation; it is never replaced by an inferred result.
- Emulated and any future native runs are never mixed in one aggregate.
- **Reforecast triggers.** The alignment package not sent by 2026-09-21; the nine
  integration/recovery families not complete by 2026-09-24; no stable integrated
  baseline by 2026-09-25; no bounded pilot by 2026-09-29; no data freeze by
  2026-10-05; the full draft not sent by 2026-10-08; no agreed reviewer window.
  On any trigger, report the failed target, the remaining effort and a revised
  forecast on the day it happens; the contingency window is not used to absorb
  it. Preserve the integrated Yocto objective: reverting to benchmarks on another
  operating system requires a new explicit scope decision, not an unreported
  shortcut.
- **Spending.** This plan requests no cloud allocation, no provisioning and no
  spending. The EUR 30 total ceiling is retained only as a standing limit that
  would apply **if** native work were ever authorised, pending an explicit new
  budget decision (D012). The previous cost estimate is obsolete. The 48-hour
  university-host fallback rule and the native-host decision deadline are
  withdrawn from mandatory scope and deferred with the native route.
- Silence from supervisors is not approval. D001 and D004 block the final
  academic release; D007 blocks `exp-v1`; **D011** (integrated title and RQ
  wording) and **D014** (the scope of the evaluation and any academic use of
  emulated results) also block the final academic release. The student's
  adoption settles execution, not these.

### 4.5 Cutting order

In this order. Nothing below weakens evidence integrity, the validity rules, the
supervisors' review, the AI-use declaration or final QA.

1. Anything outside P0, and the separate article and defence preparation, stay
   out.
2. Non-prerequisite engineering: converting the nine operator-driven tests into
   automated integration tests; the optional host-side sampler of the QEMU
   process; auxiliary APIs.
3. Optional exposition in the text, before evidence or scope.
4. Optional campaign conditions, only as a documented limitation and only
   through a justified amendment recorded before the freeze.
5. **Native performance evidence for RQ3 is outside the adopted scope.** Latency,
   throughput, saturation and resource results as properties of ARM64 hardware
   are an explicit limitation and future work; the wording of that limitation
   needs the supervisors' agreement. Missing evidence becomes an explicit
   limitation; it is never replaced by an inferred result.
6. Never as a shortcut: reverting to benchmarks hosted on another operating
   system; changing thresholds after the freeze; feature work after the data
   freeze; using 2026-10-21 to 2026-10-31 for functionality.

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
- the **guest runtime** — the controller image deployed inside the Yocto guest —
  must have a complete dependency lock with hashes, installed using hash
  enforcement, plus recorded `pip check`, image digests and a guest manifest
  before the protocol freeze. **This is an open blocker today:** the controller
  image installs its Python dependencies with an unlocked, unhashed
  installation, and such an image is not admissible for thesis measurements.

Negative tests must demonstrate rejection of a correct-duration CSV outside the
measured window, insufficient coverage, unordered timestamps, excessive gaps,
reuse of a `run_id`, masked `kas` failure, a degraded or failed-unit boot, a
changed or unhashed runtime dependency, and — once the manifest carries
`execution_mode` and the image identity — a wrong execution mode or wrong image
provenance.

## 6. Academic alignment work

Send the standalone Chapter 2 draft with the revised alignment memo and request
the fourteen decisions, **D001–D014**, in
[`supervisor_decision_log.csv`](supervisor_decision_log.csv). The alignment
package is targeted for 2026-09-21 in section 4.1; it has not been sent. A reply
on the evaluation scope and on the academic use of emulated results (D014) is
needed before the evaluation chapter is written, and a reply on the title and
research questions (D011) before they are treated as final. Silence is not
approval.

Factual changes do not require supervisor permission:

- describe the paper's platform as Eclipse Ditto 3.0.0 and Mosquitto integrated
  with ACA-Py, Fabric, Indy and IPFS, not as a custom ledger-centred twin
  platform;
- report its seven use cases and 88 steps accurately, and state that only its
  telemetry workload uses one simulated smartwatch at 1 Hz. **The paper's
  evaluation hardware instruction-set architecture is unspecified**; earlier x86
  assertions are not carried forward;
- do not compare the paper's reported figures with this dissertation's emulated
  results in either direction;
- maintain two editable diagrams: the full five-layer C2DTA reference
  architecture with implemented/deferred boundaries, and **this experiment's
  integrated deployment** — the Yocto guest under QEMU/TCG with the six
  containers inside it and the generator outside;
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
  checksums/links and LaTeX; long Yocto and integration jobs remain manual.
- G1 has a clean identified build and five strict accepted boots. G2 requires a
  real, identity-reconciled trace produced **inside the emulated Yocto guest**,
  sealed and labelled emulated; fakes do not count, and candidate evidence held
  outside the repository is not admissible until it is sealed.
- The bounded pilot covers all conditions without creating citable results.
- Every planned run has a predeclared identity. Failure is retained, never
  deleted; a repeat has a new identity and lineage.
- Analysis excludes any run lacking its plan identity, manifest, environment
  records, valid measured window or checksum. Emulated and any future native
  runs are never combined in one aggregate.
- No result enters Chapters 5 or 6 before `data-v1`.
- The final dissertation has no TODOs, complete metadata, rendered diagrams,
  explicit limitations and evidence-bounded answers to all three RQs.
- `ChatGPT/` remains an intact read-only legacy area; no automatic code merge is
  permitted.

## 8. Later native deployment: documented, unverified future work

Native ARM64 deployment is **not** a condition for completing the current
implementation, the functional tests or this dissertation. Nothing in this
section is evidence, and nothing in it is required.

The guest is already ARM64 software: the host emulates its instruction set, and
neither the root filesystem nor the ARM64 containers are x86 software. Reuse is
therefore plausible, but it is not a portability guarantee.

- **Compatible QEMU virt on an ARM64 host with KVM.** The existing kernel and
  root filesystem may be reusable if the CPU features, the virtual devices and
  the boot method are compatible. The launcher and the provenance records would
  be adapted to KVM and host-native tools. The present WSL/TCG wrapper is no
  proof that this route works.
- **Provider-managed ARM64 virtual machine.** Expect a target-specific build or
  repackaging from the same Yocto recipes. The current direct-kernel and `ext4`
  root-filesystem arrangement is not a universal firmware-bootable cloud disk.
  The EFI/bootloader arrangement and disk layout, the kernel and platform
  drivers, the console, networking, persistent storage, image import and
  identity provisioning would all have to be checked for the chosen provider.
- **Reuse and preservation.** Reuse the application, the recipes, the pinned
  layers and compatible ARM64 container images. Preserve the original test
  artefacts. Make adaptations in versioned build inputs and generate a new,
  separately identified artefact; never hand-edit a sealed image in place, and
  never share a live container data disk between guests.
- **Revalidation.** Repeat the boot, service, recovery and persistence checks on
  the actual new target. Any native performance evaluation needs its own
  protocol and its own data. **Old emulated results do not become native
  evidence after a successful port.**
- **Rules retained for any future native work.** The distinction between verified
  hardware virtualisation and CPU emulation; the bar on numbers from a burstable
  instance; the tiering rules of [ADR 0007](../adr/0007-three-tier-platform-model.md);
  and the EUR 30 spending ceiling, pending an explicit new budget decision.

Local adaptation candidates for a generic ARM64 target are untracked, absent
from the `dev` tree, and explicitly unbuilt and unbooted. They are not accepted
native support and need not be completed to finish this QEMU-based dissertation.

Technical references consulted for this section: the QEMU ARM `virt` platform
documentation, the Yocto Project BSP guide and the Yocto Project Wic guide. They
establish candidate mechanisms, not this project's successful execution.

## 9. Provenance and change record

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
  guidance rather than an implementation contract.
- **Version 2.0 (adopted 2026-09-18) restores the integrated Yocto objective and
  carries a dated QEMU-only execution amendment.** Relative to version 1.2 it:
  replaces the two separately scoped layers with one integrated system under
  test (section 3.1); makes the execution environment the Yocto guest emulated
  by QEMU/TCG on the existing x86-64 workstation and removes the native ARM64
  host, the procurement dependency, the native-host decision deadline and the
  native G1B from mandatory scope; rewords RQ1 and RQ3 so that RQ3 is bounded to
  the emulated environment, as **suggested wording for academic review**;
  replaces the elapsed August/September gate windows with the work-package
  targets of section 4.1; fixes the evidence classes of section 3.5; does **not**
  carry the 95-run campaign or the 24-hour soak into the emulated environment;
  adds the prospective acceptance criteria of section 4.3; retargets the
  dependency-lock precondition to the guest runtime; extends the decision set to
  D001–D014; and moves native deployment to documented, unverified future work
  (section 8).
  **Authority and boundary.** The *student* adopted this version on 2026-09-18.
  The supervisors approved nothing: not the title, not the research-question
  wording, not the thresholds and not the revised academic evaluation. The
  student reported that a supervisor advised proceeding with QEMU tests; that is
  student-reported advice, recorded as such and never as a supervisor decision.
  The adoption closes no gate, admits no claim, changes no research question by
  itself and makes no emulated result native evidence. Version 1.2 is archived
  unmodified with the SHA-256 recorded above, verified at the time of archiving,
  and the version 2.0 proposal text is retained under
  [`proposals/`](proposals/) as the record of what was proposed.
  **Citation equivalence:** from 2026-09-18 a citation of "plan v2.0" with a
  section number and no path means this canonical file; citations written before
  2026-09-18 that point at the proposal keep their original meaning and are not
  rewritten.
- Section 6's alignment package is read as requesting D001–D014.
