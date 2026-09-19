# Tese_Mestrado — EGW: Digital Twin Edge Gateway (Theme 1, C2DTA)

> Consumer-Controlled Digital Twin Architecture — master's dissertation, ISCTE-IUL.
> Workflow: feature branches and pull requests targeting `dev`; `main` receives
> stable versions only, by pull request.

Research and development of an ARM64 Edge Gateway for the Consumer-Controlled
Digital Twin Architecture (C2DTA). The adopted execution baseline is an
integrated gateway: the project's Yocto-built ARM64 kernel and root filesystem
boot under QEMU/TCG on the existing x86-64 workstation, and containerised
Mosquitto, the MQTT-to-Ditto controller, Eclipse Ditto and MongoDB run inside
that guest. An external simulator supplies synthetic wearable data from outside
the guest, published on the `/telemetry` topic — the literal contract name
retained from the interface. The stack was deployed and exercised once in that guest on
2026-09-18; the environment is emulated, so it yields functional and
integration evidence only, and no gate or claim follows from it.

## Current project status — 2026-09-19

> **Corrected on 2026-09-19.** G0 is now recorded as accepted (first row
> below), and the account of the integration battery of 2026-09-18 is
> corrected: the earlier statement that seven of the nine families passed
> overstated the record ([LOG `#C035`](LOG.md)).

The Yocto/QEMU functional foundation has been built and accepted. The service
code, simulator and experimental tooling exist, and the first bounded
end-to-end flow ran inside the emulated Yocto guest on 2026-09-18, with its
record held outside the repository. Completing the nine integration/recovery
test families, the bounded pilot, the protocol freeze and the functional
campaign remains outstanding, and test acceptance is paused at the student's
request. No performance result or research claim has been accepted, and
nothing has been measured.

| Workstream | Current state | Remaining evidence or work |
|---|---|---|
| Governance and baseline alignment — G0 | **Accepted on 2026-09-19** by the student, with the project manager's concurrence, for project initiation and baseline alignment ([decision record](docs/governance/decisions/2026-09-19-g0-closure.md)). It is a dated change of G0's exit scope, not a retroactive pass against the legacy criteria: the historical alignment package and the off-machine copy are **not** marked as performed | The residual obligations are reallocated in the decision record (section 3): integration defects, missing sub-checks, timely delivery and admissible run evidence to G2/G3; the D007 thresholds, prospective fault-window rules, loads and durations, the 95-run feasibility and the frozen protocol to G4, before `exp-v1`; any genuinely unsettled method or claim detail tracked at G4/G6, with no blanket D014 blocker; executing the scoping review and writing and analysing the dissertation to Chapters 1–4 and G6; the template check against the institution's original, final PDF compliance and the AI-use declaration to G7; local source, configuration, log and data copies as an ongoing execution control, with the final evidence and reproduction package at G7. Verifying the off-machine copy, its hash and the restore path stays an active resilience action owned by the student, retained in the risks and backlog and required at G7 — not verified or waived by this decision |
| Development environment | WSL2 Ubuntu 24.04 is operational and has produced the recorded Yocto builds | Full environment capture for each recorded emulated run |
| Yocto/QEMU platform — G1 | **Accepted on 2026-08-14, functional scope only**: identified clean-checkout build and five strict boots | Unchanged by the adoption; QEMU evidence is not native performance evidence |
| Integrated QEMU/TCG gateway profile | Built and booted on 2026-09-18, with build, boot and an isolated MongoDB 7 test sealed under `docs/evidence/integrated-qemu/` | Seal the first-flow record; resolve the `ditto-things` teardown OOM and container memory sizing before any stability statement |
| Native ARM64 Yocto target | **Future work under the adopted plan**: documented and unverified. No provisioned host or native Yocto boot is recorded, and none is required to complete this dissertation | Nothing is owed. If native work is ever authorised: adapt the image, verify boot, network, storage, reboot and image identity, each under its own protocol |
| Digital-twin services — G2 | Six containers were deployed inside the emulated Yocto guest on 2026-09-18 and a bounded telemetry-to-twin trace was produced; that record is **candidate evidence outside the repository and unsealed** | Seal it, then demonstrate MQTT/TLS → controller → Ditto → API with identity-reconciled evidence labelled emulated |
| Wearable simulator and recovery — G3 | Three profiles and six scenarios implemented with unit-level checks. The nine integration/recovery test families were exercised once on 2026-09-18: functional results were shown for tests 2 and 8 and for the tested checks of test 9, and the specific behaviours of tests 3, 4 (duplicate handling) and 7 (the MongoDB fault only). The record is a locally hash-sealed candidate archive held outside the repository, not admitted to the project evidence record. *Corrected 2026-09-19: the earlier "seven passing" overstated it* | Complete the nine families — the battery is **not complete**: test 5 fails its deadline criterion (326 of 2,016 valid events confirmed late), two sub-checks were not run — the sequence-reset sub-check of test 4 (`itest-dup-02`) and the Ditto repeat of test 7 (`itest-ditto-fault-01`), both runbook prose steps that the extracted test commands did not include — and the timed harness parts of tests 1 and 6 are invalid. Two diagnostic findings recorded on 2026-09-19 are open: a delivery backlog under QEMU/TCG, and a controller restart that appears to discard the controller's in-memory queue (bears on C12). Only the smartwatch is paper-aligned, with ring/clothing as dissertation extensions |
| Experimental tooling and pilot — G4 | Campaign runner, collection and analysis code have unit-level evidence | Verify instrumentation against the emulated guest, generate the hashed runtime lock for the controller image, complete the bounded pilot and freeze the protocol |
| Experimental campaign — G5 | **Not executed**; no admitted campaign dataset | Select the emulated functional campaign at the pilot and run it frozen. The 95-run composition, the 24-hour soak included, is the quantity that campaign **attempts to reach** under QEMU, subject to the pilot's feasibility check — superseding the earlier position that it was not carried over; it is neither the frozen protocol nor a promise of 95 valid runs |
| Dissertation and analysis — G6 | Introduction and theoretical framework are drafted; remaining chapters are not complete | Author/supervisor review, literature screening, evidence-based evaluation, discussion and conclusions |
| Final release and submission — G7 | **Pending** | Complete dissertation review, reproduction package and submission checks |

Two gates are formally accepted: G1 (2026-08-14, functional platform layer
only) and G0 (2026-09-19, project initiation and baseline alignment only;
*updated 2026-09-19 with the G0 decision*). **0 of 15 research claims are accepted**;
acceptance of the functional platform does not admit C01/C02 or any performance
claim. Historical unit-test totals are not live validation and are not
presented as fresh results.

## Planning and decision boundary

The plan in force is
[the integrated plan v2.0](docs/governance/INTEGRATED_DEVELOPMENT_PLAN_2026.md),
**adopted by the student on 2026-09-18 with a dated QEMU-only execution
amendment**. It replaces the separate functional-QEMU and native-service
environments of version 1.2 with one integrated system under test: the
Yocto-produced ARM64 kernel and root filesystem booted under QEMU/TCG on the
existing x86-64 workstation, hosting the six-service digital-twin stack.
Version 1.2 is preserved unmodified in
[`docs/governance/archive/`](docs/governance/archive/), and the texts under
[`docs/governance/proposals/`](docs/governance/proposals/README.md) are kept as
the record of what was proposed. [ADR 0008](docs/adr/0008-integrated-yocto-arm64-evaluation.md)
is *Accepted by the student for project execution (2026-09-18), amended
2026-09-19 — academic framing reported approved by the student*; the QEMU
evaluation scope of RQ3 is reported approved, and only the open part of D014 —
the wording of the native-evidence limitation and of claims about emulated
timing and resource figures — remains to be agreed *(corrected 2026-09-19;
previously listed the academic use of emulated results (D014) as not agreed)*.

**The adoption settles execution only.** What remains unsent is the alignment
package covering the open rows: the experimental thresholds (D007); the open
part of D014, which is only the wording of the native-evidence limitation and of
claims about emulated timing and resource figures — the QEMU evaluation scope of
RQ3 is reported approved (reported by the student, undated, not a documented
supervisor decision) and is not re-requested, and the numerical criteria belong
to D007; the authenticity of the local template copy inside D004; and the
storage semantics inside D010 *(corrected 2026-09-19; previously listed the
scope of the evaluation and any academic use of emulated results (D014) as
open)*.
D001, D007, D008 and D012 stay `proposed_not_sent`. Against that, the student
**reports** that the state-of-the-art material was sent, that a supervisor
approved proceeding with the QEMU tests, and that twelve further items were
confirmed: the title, the research questions with RQ3 evaluated in QEMU, the
local-core scope, a scoping review as the review method, an attempt at the
historical 95-run quantity, no second operator, the review schedule, the
mandatory institutional template, a mandatory AI-use declaration, an optional
article, the authorised wearable-data terminology and a local evidence copy.
**All of that is reported by the student**: none of it is a documented
supervisor decision, none carries a date, a message or a supervisor name, and
none of it changes what the decision log may assert. Adoption and these
confirmations close no gate and admit no claim.

The adopted plan separates two evidence classes. ARM64 emulated under QEMU/TCG
on the x86-64 workstation gives functional and integration evidence only:
correctness, fault handling, recovery, persistence, deployment and
repeatability may be assessed there against explicit criteria, while timing,
observed throughput and resource use are informational, labelled emulated, and
describe only the identified emulated configuration. They are never native ARM
capacity, physical-device latency, energy efficiency or performance
superiority. Native deployment and native measurement are documented,
unverified future work, and their absence is an explicit limitation.
Demonstrated by 2026-09-18, all emulated: the image build, two boots and an
isolated MongoDB 7.0.39 test, sealed under `docs/evidence/integrated-qemu/`;
and, held **outside the repository and unsealed**, the deployment of the
six-container stack in the guest and the first bounded end-to-end functional
test (one smartwatch, 1 Hz, 60 s; 60 sent, 60 delivered unique, 0 lost, 0 late,
0 duplicate, 0 failed, 0 rejected; twin `last_seq` 59; reconciliation by
identity exit 0; maximum latency 12,286 ms, emulated and informational). That
run exposed two defects, both fixed on `dev`, and a memory-cgroup OOM killed
the `ditto-things` JVM during the power-off of the session; the corrective work
is open, so no stability is claimed. The nine integration/recovery test families
were exercised once on 2026-09-18 *(corrected 2026-09-19: the earlier statement
that seven passed overstated the record)*. Functional results were demonstrated
for tests 2 and 8 and for the tested checks of test 9, and the specific
behaviours of tests 3, 4 (duplicate handling) and 7 (the MongoDB fault only)
were demonstrated; test 5 fails its deadline criterion, neither the
sequence-reset sub-check of test 4 nor the Ditto repeat of test 7 was run, and
the timed harness parts of tests 1 and 6 are invalid. That record is a
locally hash-sealed candidate archive held outside the repository, not
incorporated into or admitted by the project evidence record; the battery is
not complete, the instrumentation defect is a separate change, and nothing has
been measured.

Dates for current planning: planned submission **2026-10-20** and final delivery
deadline **2026-10-31**; the days from 2026-10-21 to 2026-10-31 are a contingency
window for essential corrections only, not the default delivery period and not
time for optional scope. Source: the student's confirmation of 2026-09-18 after
discussing the dates with the supervisors, which is a first-party statement; no
administrative record is held in the repository. The pair supersedes the
2026-09-29 internal cut-off and the 2026-09-30 baseline, which survive only in
the archived version 1.2 and in dated historical records. The work packages
between now and the submission are in the adopted plan and are planning
targets, not completed milestones. The revised architecture and acceptance
criteria are the execution baseline; the QEMU evaluation scope of RQ3 is
reported approved, and the open part of D014 — the wording of the
native-evidence limitation and of claims about emulated timing and resource
figures — still has to be reconciled with the supervisors before being
presented as agreed *(corrected 2026-09-19; previously listed the evaluation
scope as still to be reconciled)*. Do not reuse elapsed August milestones as
future commitments.

[PROGRESS.md](PROGRESS.md) records deliverable-level implementation and evidence;
formal gate outcomes live exclusively in
[the gate decision log](docs/governance/gate_decision_log.md).
This summary closes no gate — G0's acceptance of 2026-09-19 is recorded in the
gate log and in its
[decision record](docs/governance/decisions/2026-09-19-g0-closure.md) — approves
no extension and does not alter the
[claim-evidence matrix](docs/claim_evidence_matrix.md).

## Immediate priorities

1. Obtain the supervisor decisions still owed at the gates that now own them
   *(reallocated on 2026-09-19 by the G0 decision; the historical alignment
   package is not marked as sent)*: the thresholds, fault-window rules, loads
   and frozen protocol (D007) at G4, before `exp-v1`; any genuinely unsettled
   method or claim detail — the open part of D014 — tracked specifically at
   G4/G6 rather than as a blanket blocker; the authenticity of the local
   template copy inside D004 at G7; and the storage semantics inside D010. The
   title, the research questions and the review window are reported confirmed
   and are not re-requested. Functional integration work under QEMU/TCG
   proceeds in parallel and does not wait for those replies.
2. Seal the first-flow record of 2026-09-18 inside the repository, then resolve
   the `ditto-things` teardown OOM and the container memory sizing. Claim no
   stability until that is done.
3. Complete the nine integration/recovery test families in the emulated guest
   once test acceptance resumes (it is paused at the student's request): run
   the two sub-checks that were not run — the sequence-reset sub-check of
   test 4 (`itest-dup-02`) and the Ditto repeat of test 7
   (`itest-ditto-fault-01`) — obtain valid timed harness runs for tests 1 and 6, and diagnose the deadline failure of test 5 and the two
   diagnostic findings — the delivery backlog under QEMU/TCG and the controller
   restart that appears to discard the in-memory queue — under unchanged
   deadline semantics, following the proposed
   [acceptance sequence](docs/governance/proposals/acceptance_protocol_update_2026-09-19.md)
   (proposed, not adopted). Then the bounded pilot and the protocol freeze; keep
   the simulator outside the guest and record the host contention that sharing
   the workstation creates.
4. Generate and enforce the hashed runtime lock for the controller image before
   the protocol freeze: an image installed with `pip install .` is not
   admissible for thesis measurements.
5. Run the scoping review — the review type the student reports settled — and
   continue dissertation writing in parallel: dated protocol by 2026-09-21,
   search and selection by 2026-09-26, synthesis by 2026-09-30, feeding the
   chapters sent on 2026-10-01. Those are working targets. Add results only
   after the corresponding data and analysis are admissible.

Native ARM64 access and a natively booted image are **future work**, outside
the critical path. Do not assume the existing `qemuarm64` artefact can be
imported into a cloud provider unchanged: the current direct-kernel and `.ext4`
arrangement is not a firmware-bootable cloud disk, and any adaptation produces
a new identified artefact rather than an edit of the sealed image.

## Structure (follows the C2DTA Student Repository Template)

```
./
├─ src/                  # implementation (simulator, controller, deployment, Yocto, experiments)
│  ├─ CONTRACTS.md       # shared normative interfaces (topics, envelope, twins, ports)
│  ├─ schemas/           # versioned JSON Schemas (envelope + 3 wearables)
│  ├─ things/            # W3C WoT Thing Descriptions 1.1
│  ├─ egw_simulator/     # unified CLI simulator (3 wearables, 6 scenarios)
│  ├─ egw_controller/    # MQTT→Ditto bridge (FastAPI + validation + idempotency)
│  ├─ egw_experiments/   # experimental campaign harness + analysis
│  ├─ deployment/        # ARM64 compose (Mosquitto TLS, Ditto 3.9.4, MongoDB, controller)
│  ├─ yocto/             # kas manifest + meta-egw layer (Scarthgap 5.0.x, qemuarm64)
│  └─ tests/             # unit tests (against fakes; there are no integration tests)
├─ docs/                 # G0, governance, ADRs, setup guides, claim→evidence matrix
├─ thesis/               # dissertation sources, generated mirrors and research records
├─ experiments/results/  # raw/ (immutable after the freeze), processed/, figures/
├─ diagrams/             # PlantUML/Mermaid
├─ paper/                # IEEE article — out of scope before the thesis is submitted
├─ ai/                   # prompt kits (coding/writing agents)
├─ PROGRESS.md           # state of each plan item, with evidence
└─ LOG.md                # work diary (format of LOG_Projeto.md)
```

## Getting started

- Python implementation (simulator, controller, harness): see [src/README.md](src/README.md).
- Deploying the DT stack on ARM64: see [src/deployment/README.md](src/deployment/README.md).
- Yocto/QEMU build: see [src/yocto/README.md](src/yocto/README.md).
- The integrated gateway end to end (build, boot and the six containers inside
  the guest): see [docs/setup/qemu_integrated_gateway.md](docs/setup/qemu_integrated_gateway.md).
- Dissertation and research records: see [thesis/README.md](thesis/README.md).
- Preparing the environment (WSL2; the native ARM VM checklist is retained for
  future work only): see [docs/setup/](docs/setup/).
- Documentation index, including the risk register and the claim→evidence
  matrix: see [docs/README.md](docs/README.md).

## Rules of this repository

- Nothing is declared "Done" without verifiable evidence (commit, log, test, data).
- `experiments/results/raw/` is immutable after the data freeze (`data-v1`).
- No quantitative figure enters the dissertation without raw data, a manifest
  and an analysis script.
- The recorded QEMU/TCG evidence is functional only; it does not support a
  performance statement.
- Treat the current QEMU/TCG build and any future native or hardware-accelerated
  ARM64 guest as distinct environments with their own recorded provenance.
- Secrets never enter Git; `src/deployment/.env.example` exists for that purpose.
- British English is the working language of the repository
  ([docs/governance/language-policy.md](docs/governance/language-policy.md)); the
  mandatory Portuguese Resumo and drafts of external administrative
  communication are the exceptions.
