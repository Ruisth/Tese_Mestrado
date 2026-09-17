# Tese_Mestrado — EGW: Digital Twin Edge Gateway (Theme 1, C2DTA)

> Consumer-Controlled Digital Twin Architecture — master's dissertation, ISCTE-IUL.
> Workflow: feature branches and pull requests targeting `dev`; `main` receives
> stable versions only, by pull request.

Research and development of an ARM64 Edge Gateway for the Consumer-Controlled
Digital Twin Architecture (C2DTA). The current student-directed technical
target is an integrated gateway: a VM boots the project's Yocto-built Linux
image and runs containerised Mosquitto, the MQTT-to-Ditto controller, Eclipse
Ditto and MongoDB inside that guest. An external simulator supplies synthetic
wearable telemetry. This describes the target system, not an operational
deployment already demonstrated.

## Current project status — 2026-09-17

The Yocto/QEMU functional foundation has been built and accepted. The service
code, simulator and experimental tooling exist, but the integrated native
ARM64 deployment, live end-to-end validation and experimental campaign remain
outstanding. No performance result or research claim has been accepted.

| Workstream | Current state | Remaining evidence or work |
|---|---|---|
| Development environment | WSL2 Ubuntu 24.04 is operational and has produced the recorded Yocto builds | Environment capture for the native ARM64 target |
| Yocto/QEMU platform — G1 | **Accepted on 2026-08-14, functional scope only**: identified clean-checkout build and five strict boots | Native integrated boot is a separate milestone; QEMU evidence is not native performance evidence |
| Native ARM64 Yocto target | **Pending**; no provisioned VM or successful native Yocto boot is recorded | Select and provision a compatible host; adapt the image; verify boot, network, storage, reboot and image identity |
| Digital-twin services — G2 | Controller and deployment configuration exist; controller unit tests use fakes | Run Mosquitto/TLS, controller, Ditto and MongoDB together inside the Yocto guest and preserve a real telemetry-to-twin trace |
| Wearable simulator and recovery — G3 | Three profiles and six scenarios implemented with unit-level checks | Live integration, reconnect, restart and recovery verification; only the smartwatch is paper-aligned, with ring/clothing as dissertation extensions |
| Experimental tooling and pilot — G4 | Campaign runner, collection and analysis code have unit-level evidence | Verify instrumentation against the actual guest, complete the micro-pilot and freeze the protocol |
| Experimental campaign — G5 | **Not executed**; no admitted campaign dataset | Run the approved campaign and soak, validate artefacts and freeze the data |
| Dissertation and analysis — G6 | Introduction and theoretical framework are drafted; remaining chapters are not complete | Author/supervisor review, literature screening, evidence-based evaluation, discussion and conclusions |
| Final release and submission — G7 | **Pending** | Complete dissertation review, reproduction package and submission checks |

G1 is the only formally accepted gate. **0 of 15 research claims are accepted**;
acceptance of the functional platform does not admit C01/C02 or any performance
claim. The latest local planning record, dated 2026-09-16, reports no available
ARM64 VM and no new native deployment, integration run or campaign. Historical
unit-test totals are not live validation and are not presented as fresh results.

## Planning and decision boundary

The published governance baseline remains
[the integrated plan v1.2](docs/governance/INTEGRATED_DEVELOPMENT_PLAN_2026.md).
It specifies separate functional-QEMU and native-service environments. Local
planning prepared on 2026-09-16 instead targets an integrated Yocto guest;
that v2.0 working revision and its supporting decisions are **not yet published
in this branch**. This README records the current technical direction without
silently replacing the versioned plan or implying supervisor approval.

The local working forecast targets readiness on 2026-10-20 and records a
student-reported extension date of 2026-11-03. These are not confirmed
administrative deadlines in the published decision record. Publish and reconcile
the revised architecture, scope, dates and acceptance criteria before treating
them as the execution baseline; do not reuse elapsed August milestones as future
commitments.

[PROGRESS.md](PROGRESS.md) records deliverable-level implementation and evidence;
formal gate outcomes live exclusively in
[the gate decision log](docs/governance/gate_decision_log.md).
This summary does not close G0 or any remaining gate, approve an extension,
or alter the [claim-evidence matrix](docs/claim_evidence_matrix.md).

## Immediate priorities

1. Reconcile and publish the integrated-Yocto plan revision, including supervisor
   decisions, platform feasibility, budget and the confirmed submission date.
2. Obtain native ARM64 access and build/boot a compatible Yocto image. Do not
   assume the existing `qemuarm64` artefact can be imported into a cloud provider
   unchanged.
3. Demonstrate the paper-aligned smartwatch at 1 Hz through MQTT/TLS, controller,
   Ditto and API inside the Yocto guest, with identifiable runtime evidence.
4. Complete the micro-pilot and instrumentation checks before the official
   campaign; keep the simulator outside the measured guest.
5. Continue literature screening and dissertation writing in parallel. Add
   results only after the corresponding data and analysis are admissible.

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
- Dissertation and research records: see [thesis/README.md](thesis/README.md).
- Preparing the environment (WSL2, ARM VM): see [docs/setup/](docs/setup/).
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
