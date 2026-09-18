# egw_controller

MQTT-to-Ditto bridge of the C2DTA Edge Gateway. Subscribes to wearable
telemetry (QoS 1), validates every payload against the JSON Schemas (draft
2020-12), deduplicates by `message_id` (across runs) and by `seq` within the
same `run_id` (CONTRACTS 4, v1.1 run scoping), updates the Eclipse Ditto twin
via merge-patch and records one line per message in an append-only
`events.jsonl` (primary latency source of the experiments).

The binding contracts are `../CONTRACTS.md` (MQTT, envelope, twin layout,
retry policy, event fields, environment variables) and the schemas in
`../schemas/`. This README does not restate them.

## Module map

| Module | Responsibility |
|---|---|
| `config.py` | `Settings.from_env()` for all `EGW_*` variables (CONTRACTS 6) |
| `topic.py` | Parse/validate `c2dt/{egw_id}/{device_uuid}/telemetry` |
| `schema.py` | Draft 2020-12 validators per `device_type`, `$ref` via Registry |
| `dedupe.py` | Run-scoped per-device `last_seq` + bounded message-id LRU, seeded from the twin |
| `ditto.py` | Async Ditto client: ensure/get/patch twin, bounded retries, readiness |
| `events.py` | Append-only `events.jsonl` per `run_id`, exact contract fields |
| `metrics.py` | Thread-safe outcome and progress counters + uptime |
| `service.py` | Pipeline: validate -> dedupe -> Ditto update -> event log + counters |
| `mqtt.py` | paho-mqtt v2 bridge (own network thread) into the asyncio queue |
| `app.py` | FastAPI: `/health`, `/ready`, `/twins/{device_id}`, `/metrics` |
| `__main__.py` | `python -m egw_controller` (uvicorn on `EGW_HTTP_PORT`) |

## Run locally

From the `src/` directory, with Python >= 3.11:

```bash
pip install -e .[dev]

# Local dev example (no TLS is allowed only on localhost, never in benchmarks)
export EGW_MQTT_HOST=localhost
export EGW_MQTT_TLS=false
export EGW_MQTT_USERNAME=egw-controller
export EGW_MQTT_PASSWORD=<dev password>
export EGW_DITTO_BASE_URL=http://localhost:8080
export EGW_SCHEMA_DIR=./schemas
export EGW_EVENT_LOG_DIR=./data/events

python -m egw_controller
```

The full environment variable table (names, defaults, semantics) is normative
in `../CONTRACTS.md`, section 6.

## HTTP API (port `EGW_HTTP_PORT`, default 8000)

- `GET /health` - process alive, always `{"status": "ok"}`.
- `GET /ready` - 200 only when the MQTT subscription was granted (SUBACK at
  QoS 0/1) and Ditto answers; 503 otherwise.
- `GET /twins/{device_id}` - twin read normalized by the controller; accepts a
  bare `device_uuid` or the full `org.c2dta:{device_uuid}` thing id; ids that
  are not a lowercase UUID v4 are answered 404 without calling Ditto.
- `GET /metrics` - the four contract counters
  `accepted`/`rejected`/`duplicate`/`failed`, plus `dropped` (messages
  discarded on inbound queue overflow), `queue_depth`, `started_at`,
  `uptime_s`, `monotonic_ns` and `wall_utc`, and the progress counters
  `received` (messages handed to the pipeline, counted before the
  queue-capacity decision), `in_progress` (taken from the queue, processing
  not ended, retries included) and `processing_errors` (processing ended with
  no outcome recorded). In one response of a running controller
  `received == accepted + rejected + duplicate + failed + dropped +
  processing_errors + in_progress + queue_depth`. The progress counters show
  the internal state of one controller process only and never replace the
  reconciliation of sent messages with recorded outcomes by identity; see
  CONTRACTS 5.

## Event log

One `events.jsonl` per `run_id` under `EGW_EVENT_LOG_DIR/{run_id}/`, flushed
per line, with exactly the fields of CONTRACTS 5. `latency_ms` is
`(ditto_ack_monotonic_ns - received_monotonic_ns) / 1e6`, both captured in
this process; `rejected`/`duplicate`/`failed` events carry null ack/latency.

## Tests

```bash
cd src
python -m pytest tests -k controller -m "not integration"
```

Unit tests are network-free (fake transports/clients) and run on Windows.
