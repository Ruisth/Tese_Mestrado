# src/: EGW implementation

All the implementation code of the Digital Twin Edge Gateway, the edge gateway of the
Consumer-Controlled Digital Twin Architecture (C2DTA) studied in the dissertation. The binding
interfaces are in [CONTRACTS.md](CONTRACTS.md) (v1.2, 2026-09-24). How the parts fit together is
in [`../docs/architecture.md`](../docs/architecture.md).

## Layout

| Path | Contents |
|---|---|
| `schemas/` | JSON Schemas (draft 2020-12): the common envelope v1 and one schema per wearable |
| `things/` | W3C WoT Thing Descriptions 1.1, one per wearable. They are descriptive and not loaded at runtime |
| `egw_simulator/` | Unified CLI simulator: 3 deterministic wearable profiles, 6 scenarios |
| `egw_controller/` | MQTT→Ditto bridge: validation, run-scoped deduplication, merge-patch updates, `events.jsonl` |
| `egw_experiments/` | Experiment harness and analysis: plan / run / analyze / verify-checksums |
| `deployment/` | Compose stack (Mosquitto TLS, Ditto 3.9.4, MongoDB, controller) that runs inside the emulated ARM64 guest |
| `yocto/` | kas manifests and the `meta-egw` layer for the gateway image (qemuarm64, Scarthgap) |
| `tests/` | pytest suite (unit level; no broker or Ditto needed) |
| `pyproject.toml` | Package metadata. The package root is `src/` |
| `requirements.lock` | Development and test lock, without hashes |
| `requirements-runtime.lock` | Hashed runtime lock for the controller image, installed by the `Dockerfile` with `--require-hashes` |
| `Dockerfile` | Controller image (`linux/arm64`) |

## Run the tests

From the repository root, with Python 3.11 or later. These are the commands of the CI workflow
[`technical-ci.yml`](../.github/workflows/technical-ci.yml):

```bash
python -m venv .venv && . .venv/bin/activate   # Windows: .venv\Scripts\activate
cd src
python -m pip install -e '.[dev,analysis]'
python -m pytest tests -q
```

**The suite is self-contained.** Every test runs against fakes for MQTT and Ditto, with the
schemas loaded from `schemas/`. No broker, no Ditto and no ARM64 host is needed or exercised. Some
comparison-tool tests skip on Windows or without `bash`.

**Integration markers.** The `integration` marker is registered and deselected by default
(`addopts` in `pyproject.toml`), and no test carries it.

**Where the integration testing is.** It was done on the emulated gateway, not in pytest. The test
battery (wearable-to-twin integration with three device types, invalid and repeated messages,
recovery after disconnection, controller restart, database or twin-service failure, gateway reboot
and persistence, broker access control) and the 10-minute run without faults were driven by the test
scripts in [`../tools/session/`](../tools/session/README.md). See
[`../docs/results.md`](../docs/results.md#functional-tests) (Functional tests).

**Test records.** The newest test record in the repository is
[`../docs/evidence/tests/2026-08-11-head-4e67717/`](../docs/evidence/tests/2026-08-11-head-4e67717/):
701 passed at `4e67717`. A later full run, on 2026-10-08, is held locally only
([`../docs/results.md`](../docs/results.md#other-records), Other records). Unit tests do not replace
the tests on the emulated gateway.

## Run the simulator (reference invocation, CONTRACTS §7)

```bash
python -m egw_simulator run --scenario nominal --seed 42 \
  --broker <host> --port 8883 --duration 600 --rate 11.2 --output <dir> \
  --username egw-simulator --ca-cert <ca.crt> --egw-id egw-01 --qos 1
```

- **Password.** Pass the MQTT password through `EGW_MQTT_PASSWORD`, never on the command line.
- **Load.** The duration and rate shown are the `nominal` scenario's experimental parameters, not
  requirements.
- **Devices.** `--devices` takes a comma-separated list of wearables. The default is all three
  profiles: `smartwatch`, `smart_ring` and `smart_clothing`.
- **Against the emulated gateway.** The broker is reached on `127.0.0.1:8883` through QEMU's port
  forward. For a demonstration with one or three wearables, see
  [`../docs/demo.md`](../docs/demo.md).

## Run the controller locally

```bash
# environment variables per CONTRACTS §6 (EGW_*)
python -m egw_controller
```

In the gateway the controller runs as the `controller` container of
[`deployment/compose.yaml`](deployment/compose.yaml). Its image is built from the `Dockerfile`
by `deployment/scripts/build-controller-image.sh`.

## Evaluate

The evaluation reported in the dissertation comprised:

- the test battery on the emulated gateway (see above);
- the Yocto-Debian comparison, run with `tools/compare/measure_*`.

A larger planned series of repeated measurements was not run.

Both use `egw_experiments` to run and analyse. Read:

- [`../docs/results.md`](../docs/results.md) for the results, their data and the code behind them;
- [`../docs/reproduce.md`](../docs/reproduce.md) for how to repeat them;
- [`../experiments/README.md`](../experiments/README.md), the harness manual;
- [`deployment/README.md`](deployment/README.md), the stack runbook.

The harness manual was written for that larger series, which was not run. The stack runbook was
written for a native ARM64 virtual machine that produced no reported result. The deployment steps
of the evaluated system are those of the
[integrated runbook](../docs/setup/qemu_integrated_gateway.md) §4–5, automated by
`tools/compare/provision_stack.sh`.
