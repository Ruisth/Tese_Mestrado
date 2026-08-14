# Tese_Mestrado — EGW: Digital Twin Edge Gateway (Theme 1, C2DTA)

> Consumer-Controlled Digital Twin Architecture — master's dissertation, ISCTE-IUL.
> Workflow: commits and pull requests on `dev`; `main` receives stable versions
> only, by pull request.

Implementation and dissertation of a versioned two-layer ARM64 Edge Gateway
prototype: a Yocto/Scarthgap functional platform plus a separately deployed
native-ARM64 digital-twin service layer. The service layer receives synthetic
telemetry from three wearable device types, validates the events and
materialises them as digital twins in Eclipse Ditto.

**Normative source:**
[the integrated plan v1.2](docs/governance/INTEGRATED_DEVELOPMENT_PLAN_2026.md)
(v1.1/v1.2 line, baseline 2026-08-13; v1.2 of 2026-08-14 is a governance
correction with no substantive change). The unchanged Portuguese v1.0 is
retained in its archive;
[PROGRESS.md](PROGRESS.md) is the only source of current gate/deliverable
state, and formal gate outcomes live in
[the gate decision log](docs/governance/gate_decision_log.md).

## Structure (follows the C2DTA Student Repository Template)

```
Claude/
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
├─ thesis/               # LaTeX dissertation (ISCTE template) + review protocol
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
- Preparing the environment (WSL2, ARM VM): see [docs/setup/](docs/setup/).
- Documentation index, including the risk register and the claim→evidence
  matrix: see [docs/README.md](docs/README.md).

## Rules of this repository

- Nothing is declared "Done" without verifiable evidence (commit, log, test, data).
- `experiments/results/raw/` is immutable after the data freeze (`data-v1`).
- No quantitative figure enters the dissertation without raw data, a manifest
  and an analysis script.
- QEMU evidence is functional only: it never supports a performance statement.
- Secrets never enter Git; `src/deployment/.env.example` exists for that purpose.
- British English is the working language of the repository
  ([docs/governance/language-policy.md](docs/governance/language-policy.md)); the
  mandatory Portuguese Resumo and drafts of external administrative
  communication are the exceptions.
