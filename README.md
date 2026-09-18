# Tese_Mestrado — EGW: Digital Twin Edge Gateway (Theme 1, C2DTA)

> Consumer-Controlled Digital Twin Architecture — master's dissertation, ISCTE-IUL.
> Workflow: feature branches and pull requests targeting `dev`; `main` receives
> stable versions only, by pull request.

Research and development of an ARM64 Edge Gateway for the Consumer-Controlled
Digital Twin Architecture (C2DTA). The adopted execution baseline is an
integrated gateway: the project's Yocto-built ARM64 kernel and root filesystem
boot under QEMU/TCG on the existing x86-64 workstation, and containerised
Mosquitto, the MQTT-to-Ditto controller, Eclipse Ditto and MongoDB run inside
that guest. An external simulator supplies synthetic wearable telemetry from
outside the guest. The stack was deployed and exercised once in that guest on
2026-09-18; the environment is emulated, so it yields functional and
integration evidence only, and no gate or claim follows from it.

## Current project status — 2026-09-18

The Yocto/QEMU functional foundation has been built and accepted. The service
code, simulator and experimental tooling exist, and the first bounded
end-to-end flow ran inside the emulated Yocto guest on 2026-09-18, with its
record held outside the repository. The nine integration/recovery test
families, the bounded pilot, the protocol freeze and the functional campaign
remain outstanding. No performance result or research claim has been accepted,
and nothing has been measured.

| Workstream | Current state | Remaining evidence or work |
|---|---|---|
| Development environment | WSL2 Ubuntu 24.04 is operational and has produced the recorded Yocto builds | Full environment capture for each recorded emulated run |
| Yocto/QEMU platform — G1 | **Accepted on 2026-08-14, functional scope only**: identified clean-checkout build and five strict boots | Unchanged by the adoption; QEMU evidence is not native performance evidence |
| Integrated QEMU/TCG gateway profile | Built and booted on 2026-09-18, with build, boot and an isolated MongoDB 7 test sealed under `docs/evidence/integrated-qemu/` | Seal the first-flow record; resolve the `ditto-things` teardown OOM and container memory sizing before any stability statement |
| Native ARM64 Yocto target | **Future work under the adopted plan**: documented and unverified. No provisioned host or native Yocto boot is recorded, and none is required to complete this dissertation | Nothing is owed. If native work is ever authorised: adapt the image, verify boot, network, storage, reboot and image identity, each under its own protocol |
| Digital-twin services — G2 | Six containers were deployed inside the emulated Yocto guest on 2026-09-18 and a bounded telemetry-to-twin trace was produced; that record is **candidate evidence outside the repository and unsealed** | Seal it, then demonstrate MQTT/TLS → controller → Ditto → API with identity-reconciled evidence labelled emulated |
| Wearable simulator and recovery — G3 | Three profiles and six scenarios implemented with unit-level checks | The nine integration/recovery test families in the guest — **none has been run**; only the smartwatch is paper-aligned, with ring/clothing as dissertation extensions |
| Experimental tooling and pilot — G4 | Campaign runner, collection and analysis code have unit-level evidence | Verify instrumentation against the emulated guest, generate the hashed runtime lock for the controller image, complete the bounded pilot and freeze the protocol |
| Experimental campaign — G5 | **Not executed**; no admitted campaign dataset | Select the emulated functional campaign at the pilot and run it frozen; the 95-run campaign and the 24-hour soak of the previous plan are not carried over |
| Dissertation and analysis — G6 | Introduction and theoretical framework are drafted; remaining chapters are not complete | Author/supervisor review, literature screening, evidence-based evaluation, discussion and conclusions |
| Final release and submission — G7 | **Pending** | Complete dissertation review, reproduction package and submission checks |

G1 is the only formally accepted gate. **0 of 15 research claims are accepted**;
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
is *Accepted by the student for project execution (2026-09-18) — not agreed by
the supervisors*.

**The adoption settles execution only.** Nothing has been sent to the
supervisors: decisions D001–D014 are all `proposed_not_sent`, and nothing is
approved by them. The title and research-question wording remain proposed
(D001/D011), and the scope of the evaluation and any academic use of emulated
results remain D014. The student reported that a supervisor advised proceeding
with QEMU tests; that is student-reported advice, not approval and not a
documented supervisor decision. Adoption closes no gate and admits no claim.

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
is open, so no stability is claimed. None of the nine integration/recovery test
families has been run and nothing has been measured.

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
criteria are the execution baseline; the **academic** wording and the
evaluation scope still have to be reconciled with the supervisors before being
presented as agreed. Do not reuse elapsed August milestones as future
commitments.

[PROGRESS.md](PROGRESS.md) records deliverable-level implementation and evidence;
formal gate outcomes live exclusively in
[the gate decision log](docs/governance/gate_decision_log.md).
This summary does not close G0 or any remaining gate, approve an extension,
or alter the [claim-evidence matrix](docs/claim_evidence_matrix.md).

## Immediate priorities

1. Send the alignment package to the supervisors and obtain D004, D007, D011,
   D013 and D014 — the title and RQ wording, the thresholds, the review window,
   and the scope of the evaluation and any academic use of emulated results —
   before the planned submission of 2026-10-20. Functional integration work
   under QEMU/TCG proceeds in parallel and does not wait for that reply.
2. Seal the first-flow record of 2026-09-18 inside the repository, then resolve
   the `ditto-things` teardown OOM and the container memory sizing. Claim no
   stability until that is done.
3. Run the nine integration/recovery test families in the emulated guest, then
   the bounded pilot and the protocol freeze; keep the simulator outside the
   guest and record the host contention that sharing the workstation creates.
4. Generate and enforce the hashed runtime lock for the controller image before
   the protocol freeze: an image installed with `pip install .` is not
   admissible for thesis measurements.
5. Continue literature screening and dissertation writing in parallel. Add
   results only after the corresponding data and analysis are admissible.

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
