# src/ — EGW implementation

All implementation code for the Digital Twin Edge Gateway (C2DTA Tema 1).
Binding interfaces live in [CONTRACTS.md](CONTRACTS.md) (v1.1); the normative
plan is [`../docs/governance/INTEGRATED_DEVELOPMENT_PLAN_2026.md`](../docs/governance/INTEGRATED_DEVELOPMENT_PLAN_2026.md).

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
level, with fakes, on Windows). The current sealed record is `701 passed` over
clean HEAD `4e67717`, archived in
[`../docs/evidence/tests/2026-08-11-head-4e67717/`](../docs/evidence/tests/2026-08-11-head-4e67717/);
earlier figures are historical, each tied to the commit it tested. The current
G1 evidence branch passes 718 tests locally, but that is not a new test seal.

M2 closes no gate and validates no claim on its own. In
`../docs/claim_evidence_matrix.md`, **0 of the 15 claims are accepted**; gate
G1 was accepted on 2026-08-14 for the functional platform layer only (the
decision validated no claim — see
`../docs/governance/gate_decision_log.md`), and every other gate remains
undecided. C01 and C02 now have the preliminary 2026-08-11 seal
and the separate strict 2026-08-14 G1 capsule; neither evidence production nor
merging records formal admission:

| Claim | State |
|---|---|
| C01 | Partial — a clean identified same-operator checkout/build completed all 5,715 tasks and is sealed; gate G1 is accepted, but D006/second-operator treatment and the **formal claim admission** remain pending — accepting the gate admitted no claim |
| C02 | Partial — the two preliminary boots remain sealed; one strict instrumentation failure is preserved and five fresh strict boots each passed 7/7 assertions. The later predefined `data-v1` identities remain pending unless a dated protocol decision admits this set |
| the other 13 | `Pending — no admissible experimental evidence` |

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
