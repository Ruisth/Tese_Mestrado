# egw_simulator — Unified wearable telemetry simulator

Deterministic CLI simulator for the three C2DTA wearables (smartwatch,
smart ring, smart clothing). It publishes JSON telemetry over MQTT
(QoS 1, TLS) to `c2dt/{egw_id}/{device_uuid}/telemetry` and writes per-run
evidence outputs. Binding references: `src/CONTRACTS.md` sections 1-3 and 7;
plan sections 4.3, 5.3, 5.6 and 7.1.

Requires Python >= 3.11. Runtime dependencies: `paho-mqtt >= 2.1`,
`jsonschema` (with the `referencing` library it depends on). Tests need no
broker.

## Usage

Reference invocation (CONTRACTS.md section 7):

```text
python -m egw_simulator run --scenario nominal --seed 42 \
  --broker <host> --port 8883 --duration 600 --rate 11.2 --output <dir> \
  [--devices smartwatch,smart_ring,smart_clothing] [--egw-id egw-01] \
  [--run-id <id>] [--username u --password p --ca-cert ca.crt | --no-tls] [--qos 1]
```

Local development against a non-TLS Mosquitto (allowed only on localhost,
never for benchmarks):

```text
python -m egw_simulator run --scenario smoke --seed 42 \
  --broker localhost --port 1883 --no-tls \
  --username egw-simulator --password <dev-password> --output results/raw
```

Load sweep at 100 msg/s aggregate (default duration is already the
five-minute execution of plan section 7.1):

```text
python -m egw_simulator run --scenario load-sweep --seed 42 \
  --broker <host> --port 8883 --rate 100 \
  --username egw-simulator --password <p> --ca-cert ca.crt --output results/raw
```

### Flags

| Flag | Default | Meaning |
|---|---|---|
| `--scenario` | (required) | one of the six scenarios below |
| `--seed` | `42` | determinism seed |
| `--broker` | `$EGW_MQTT_HOST` or `localhost` | broker host |
| `--port` | `$EGW_MQTT_PORT` or `8883` | broker port |
| `--duration` | scenario default | run duration in seconds |
| `--rate` | scenario default | aggregate rate in msg/s (required for `load-sweep`) |
| `--output` | `results/raw` | outputs are written to `<output>/<run_id>/` |
| `--devices` | all three types | comma-separated subset of device types |
| `--egw-id` | `$EGW_ID` or `egw-01` | gateway identifier |
| `--run-id` | `{scenario}-{seed}-{UTC compact timestamp}` | run identifier (`^[A-Za-z0-9._-]{1,64}$`) |
| `--username` / `--password` | `$EGW_MQTT_USERNAME` / `$EGW_MQTT_PASSWORD` | broker credentials (never written to outputs) |
| `--ca-cert` | `$EGW_MQTT_CA_CERT` | CA file for TLS server authentication |
| `--no-tls` | off | disable TLS; allowed only for localhost brokers |
| `--qos` | `1` | MQTT QoS (contract value: 1) |

## Scenarios

| Scenario | Devices | Default duration | Default aggregate rate | Extras |
|---|---|---:|---:|---|
| `smoke` | 3 | 30 s | 11.2 msg/s | short functional check |
| `nominal` | 3 | 600 s | 11.2 msg/s | baseline load (plan section 7.1) |
| `load-sweep` | 3 | 300 s | from `--rate` (required) | five-minute executions per load (plan section 7.1) |
| `dropout-reconnect` | 3 | 600 s | 11.2 msg/s | real disconnect windows with buffered redelivery |
| `invalid-payload` | 3 | 600 s | 11.2 msg/s | deterministic 1-in-20 invalid injection |
| `soak` | 3 | 86400 s | 11.2 msg/s | 24 h stability run |

The aggregate `--rate` is split in the fixed proportion `1 : 0.2 : 10`
across smartwatch : smart_ring : smart_clothing (CONTRACTS.md section 3),
so `--rate 11.2` yields 1.0 + 0.2 + 10.0 msg/s. With a subset of
`--devices` the same weights are renormalised over the selected types.
Each device is paced at `1 / rate_i` on `time.monotonic()` with drift
correction (absolute per-event targets, not accumulated sleeps).

In `invalid-payload`, one event in 20 per device (positions derived from
the seed) is mutated to be schema-invalid (out-of-range value, missing
required field, or wrong type). The marker `intended_invalid: true` exists
only in `sent_events.jsonl`, never in the published payload. All other
payloads are validated against the real JSON Schemas in `src/schemas/`
before publish (plan section 5.6).

In `dropout-reconnect`, the run has deterministic RUN-LEVEL disconnect
windows (roughly one per minute of run time, 2-8 s each; the simulator
holds one MQTT connection for all devices, so windows are shared). At each
window start the simulator drops its MQTT connection for real
(`disconnect()` — DISCONNECT plus socket close). Events scheduled inside
the window are STILL generated on schedule — a real wearable keeps
sampling — and are buffered locally in order. At window end the client
reconnects (same exponential backoff as unplanned losses) and the buffer
is flushed in order BEFORE live publishing resumes. Consequences
(plan section 7.2, 'recuperacao apos restart/reconnect'; claim C10):

- `seq` stays strictly monotonic and gap-free per device;
- every generated event is published exactly once — buffered events are
  published late, at flush time;
- buffered events carry their ACTUAL (late) publish instant in
  `publish_monotonic_ns`, so they are visibly delayed in
  `sent_events.jsonl`;
- PUBACK capture stays best-effort (CONTRACTS.md section 7, v1.1):
  flushed publishes use a zero puback wait budget, so the flush never
  blocks the schedule of live events longer than their own budget.

Broker-side/network-level faults remain test-harness territory: this
scenario exercises the CLIENT-side disconnect/reconnect and buffered
redelivery path only. This scope statement is also recorded verbatim in
the run's `manifest.json` (`note` field), and the harness reads it for
its dropout acceptance rule.

## Determinism guarantees (plan section 5.6)

For a fixed scenario, seed, run_id, egw_id, device set, rate and duration,
the following are byte-identical across runs and hosts:

- the set of device UUIDs (v4-formatted, derived from the seed);
- the per-device payload sequences (measurements and envelope fields except
  `ts`), including `message_id` (UUID v5 of `"{run_id}:{device_uuid}:{seq}"`
  in namespace `6b1a3f52-8c1e-5e2b-9f0d-c2d7a1e4b8a0`);
- the positions and contents of injected invalid events;
- the run-level disconnect windows of `dropout-reconnect` and therefore
  the exact set of events that are buffered (and later flushed) in a run.

Excluded from the determinism guarantee: `ts` (wall-clock RFC 3339 UTC,
millisecond resolution, `Z` suffix), `publish_monotonic_ns` /
`puback_monotonic_ns`, and the manifest timestamps. Payload CONTENT is
deterministic even for buffered events; their publish TIMING is inherently
late (they are flushed at window end instead of at their scheduled time),
which is by design and visible in `sent_events.jsonl`.

## Outputs

Each run writes to `<output>/<run_id>/`:

- `manifest.json` — protocol_version (`1.0`), simulator version, scenario,
  seed, run_id, egw_id, devices with UUIDs, aggregate and per-device rates,
  duration, QoS, broker endpoint without secrets, git commit (best effort,
  else `null`), started/finished UTC timestamps, completion flag, totals
  (`sent`, `intended_invalid`, `buffered_dropout`, `dropout_disconnects`)
  and a `note` field (scenario scope statement for `dropout-reconnect`,
  `null` otherwise).
- `sent_events.jsonl` — one record per published message with exactly:
  `run_id`, `message_id`, `device_uuid`, `device_type`, `seq`,
  `publish_monotonic_ns`, `puback_monotonic_ns`, `intended_invalid`.

`publish_monotonic_ns` is captured immediately before the MQTT publish
call — it is always the ACTUAL publish instant. For `dropout-reconnect`
events buffered during a disconnect window that instant is the (late)
flush time after the reconnect, not the scheduled generation time, so
buffered events are visibly delayed in `sent_events.jsonl`.
`puback_monotonic_ns` capture is best-effort (CONTRACTS.md section 7,
v1.1): each publish waits for the QoS 1 acknowledgement at most for the
free time until the next scheduled event (`max(0, next_event_time - now)`,
possibly 0), so the acknowledgement round-trip never throttles the
publishing schedule; the field is `null` when the PUBACK was not observed
within that budget. paho-mqtt's network thread still handles QoS 1
retransmission for unacknowledged messages, and a bounded end-of-run drain
(default 60 s) waits for the last in-flight message(s) before disconnect.
No primary metric uses `puback_monotonic_ns` — the primary latency of plan
section 7.3 comes from the controller's `events.jsonl`. Monotonic values
are only comparable within the same process.

## Module layout

| Module | Responsibility |
|---|---|
| `envelope.py` | common envelope, `EGW_UUID_NAMESPACE`, `message_id`, `ts` |
| `devices.py` | deterministic device UUIDs, nominal rates, rate split |
| `profiles.py` | deterministic measurement generators per device type |
| `scenarios.py` | `ScenarioSpec` registry, disconnect windows, invalid injection |
| `validation.py` | draft 2020-12 validators over the real project schemas |
| `publisher.py` | `Publisher` protocol (with `disconnect()`/`reconnect()`), `PahoPublisher`, `InMemoryPublisher` |
| `runner.py` | paced deterministic run loop, dropout buffering/flush, evidence writing |
| `output.py` | `manifest.json` and `sent_events.jsonl` writers |
| `cli.py` / `__main__.py` | `python -m egw_simulator run ...` |

## Testing

Broker-free tests live in `src/tests/test_simulator_*.py` (pytest,
`InMemoryPublisher` plus an injectable fake clock). From `src/`:

```text
python -m pytest tests -k simulator -m "not integration"
```
