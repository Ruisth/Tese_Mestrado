# src/ — EGW implementation

All implementation code for the Digital Twin Edge Gateway (C2DTA Tema 1).
Binding interfaces live in [CONTRACTS.md](CONTRACTS.md) (v1.1); the normative
plan is `../../PLANO_DESENVOLVIMENTO_INTEGRADO_EDGE_GATEWAY_2026.md`.

## Layout

| Path | Contents |
|---|---|
| `schemas/` | JSON Schemas (draft 2020-12): common envelope v1 + one schema per wearable |
| `things/` | W3C WoT Thing Descriptions 1.1 (one per wearable) |
| `egw_simulator/` | Unified CLI simulator: 3 deterministic wearable profiles, 6 scenarios |
| `egw_controller/` | MQTT→Ditto bridge: validation, run-scoped dedupe, merge-patch updates, events.jsonl |
| `egw_experiments/` | Campaign harness: plan / run / analyze / verify-checksums |
| `deployment/` | ARM64 compose stack (Mosquitto TLS, Ditto 3.9.4, MongoDB, controller) |
| `yocto/` | kas manifest + `meta-egw` layer for the EGW-OS image (qemuarm64, Scarthgap) |
| `tests/` | pytest suite (unit; no broker/Ditto required) |

## Run the tests

```bash
python -m venv .venv && . .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e .[dev,analysis]
cd src && python -m pytest tests -q
```

The suite is self-contained: every test runs against fakes for MQTT and Ditto,
with schemas loaded from `schemas/`. No broker, no Ditto, no ARM64 host is
required, and none is exercised.

**Integration tests: the marker is configured, ZERO integration tests exist
today.** The `integration` marker is registered and deselected by default via
`addopts` in `pyproject.toml`, so `python -m pytest tests -m integration`
currently collects nothing. Writing live integration/E2E tests against a real
broker, a real Ditto instance and the ARM64 stack is **outstanding work and a
prerequisite for gate G3** (risk R21); until they exist and have been run on
the target environment, no integration-level claim may be made.

Consequently the entire suite is level **M2** evidence (verified locally, unit
level, with fakes, on Windows). M2 closes no gate and validates no claim on its
own — see `../docs/claim_evidence_matrix.md`, where all 15 claims remain
`Pendente — sem evidência`.

## Run the simulator (reference invocation, CONTRACTS §7)

```bash
python -m egw_simulator run --scenario nominal --seed 42 \
  --broker <host> --port 8883 --duration 600 --rate 11.2 --output <dir>
```

## Run the controller locally

```bash
# env vars per CONTRACTS §6 (EGW_*)
python -m egw_controller
```

## Evaluate

See [`../experiments/README.md`](../experiments/README.md) for the campaign
workflow (plan → run on the ARM64 VM → freeze raw → analyze) and
[`deployment/README.md`](deployment/README.md) for the stack runbook.
