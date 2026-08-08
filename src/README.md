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

The suite is self-contained (fakes for MQTT/Ditto; schemas loaded from
`schemas/`). Live integration tests are marked `integration` and deselected
by default via `addopts` in `pyproject.toml`; run them against a live stack
with `python -m pytest tests -m integration`. Unit results with fakes are
level M2 evidence only — they never close a gate on their own (see
`../docs/claim_evidence_matrix.md`).

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
