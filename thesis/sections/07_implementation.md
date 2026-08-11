<!-- GENERATED FILE - DO NOT EDIT.
     Source: latex/chapters/04_architecture.tex (implementation sections)
     Regenerate with: python thesis/tools/generate_sections.py
     The LaTeX tree under thesis/latex/ is the single edited source. -->

# Implementation

## Platform Layer: EGW-OS

The platform image is defined by a custom Yocto layer (`meta-egw`) and targets the `qemuarm64` machine, described by a `kas` manifest that pins every layer to an exact revision of the Scarthgap (5.0) LTS line, rather than tracking moving branches. The image is specified to provide systemd, networking and an OCI container runtime — the minimum required to host the service layer. Its validation procedure, fixed in the experimental protocol, is functional only and consists of booting the built image under QEMU and executing a test container; that validation is to be performed as part of the campaign and reported in Chapter . Emulation is reserved exclusively for build and functional validation; no performance conclusions are to be drawn from it. **\[TODO: Record the exact pinned revisions and image recipe contents from src/yocto/ once frozen at the platform gate.\]**

## Service Layer: Digital-Twin Stack

The stack is intentionally minimal. The composition includes only three Ditto services — `gateway`, `policies` and `things` — with MongoDB as persistence; Ditto’s `search`, `connectivity` and user-interface services are excluded because no research question requires them. All third-party container images are pinned by digest in a lock file (`images.lock.env`), and the deployment procedure requires each image to be native `linux/arm64`, a property checked when the lock file is populated; the controller image is built locally for `linux/arm64`. Externally, only the broker’s TLS port is exposed; the Ditto gateway (port 8080) and the controller API (port 8000) bind to the internal network or localhost.

## Ingestion Controller

The controller is the bridge between MQTT and Ditto. Its processing pipeline, per message, is: asynchronous MQTT receive (QoS 1); schema validation *before* any Ditto interaction; idempotency check; conversion to a JSON merge patch; twin update via `PATCH` to the Ditto things API; structured event logging.

### Idempotency

Because QoS 1 delivery is at-least-once, duplicates are expected. Deduplication is *run-scoped* (contract version 1.1) and uses two complementary guards. The first guard is replay detection: the controller rejects any `message_id` it has already processed (a bounded per-device history), and this rejection applies unconditionally — since `message_id` is a UUID v5 of `run_id`, `device_uuid` and `seq`, a replayed message is recognised regardless of which run it belongs to. The second guard is a sequence floor: an event whose `seq` is not greater than the last accepted sequence for that device is rejected as a duplicate, but this floor holds *only within the same* `run_id`. When an event arrives whose `run_id` differs from the device’s recorded `last_run_id`, the sequence floor is reset, because each new execution legitimately restarts `seq` at zero — as happens in the ten consecutive `smoke` executions and in the warm-up phase that precedes every measured run. Without the run scoping, a warm-up run using the same seed (and therefore the same device identifiers) would raise the sequence floor and cause the first messages of the subsequent measured run to be wrongly rejected as duplicates, corrupting the delivery-rate metric. The deduplication state (last accepted `message_id`, `seq`, `run_id` and timestamp, plus an accepted-events counter) is stored *in the twin itself*, under a dedicated `ingestion` feature, so that it survives controller restarts; after a restart the local cache is rebuilt by reading the twin on the first event of each device.

### Failure Handling and Observability

Ditto updates are retried a bounded number of times (default three attempts with exponential backoff) and only for transient errors (timeouts, connection failures, server-side 5xx responses); client-side 4xx responses are not retried. The controller logs structured JSON and maintains counters for accepted, rejected, duplicate and failed events. Its HTTP API exposes: `GET /health` (process liveness); `GET /ready` (returns success only when both the broker and Ditto are reachable); `GET /twins/{device_id}` (normalised twin read-back); and `GET /metrics` (counters and uptime, as JSON).

### Evidence Log

For every processed message the controller appends one record to a per-run `events.jsonl` file containing the run and message identifiers, device information, two monotonic-clock readings (at MQTT receive and after the Ditto acknowledgement), the derived latency in milliseconds, the outcome (`accepted`, `rejected`, `duplicate` or `failed`), the number of attempts and the error, if any. This file is the primary source for the latency and reliability metrics of Chapter ; rejected, duplicate and failed events carry no latency value.

## Simulator

The workload generator is a single CLI package (`egw_simulator`) covering the three device types and six scenarios: `smoke`, `nominal`, `load-sweep`, `dropout-reconnect`, `invalid-payload` and `soak`. All experimental parameters — scenario, seed, broker, duration, aggregate rate, device set, credentials, QoS — are explicit CLI arguments, and all except the credentials are recorded in a per-run manifest (secrets are never written to evidence files). Generation is deterministic: the same seed yields the same per-device payload sequence. Every payload is validated locally against its schema before publication; the `invalid-payload` scenario deliberately injects invalid events and marks them as intended-invalid in the simulator’s own send log (never in the payload), so that correct rejections can be distinguished from losses. The simulator writes its own evidence file per run (`sent_events.jsonl`) with one record per message, carrying the message identifiers, the device type (added in contract version 1.1 so that per-type analyses need no join with the manifest), the publish monotonic timestamp and, when observed in time, the broker-acknowledgement monotonic timestamp; acknowledgement capture is best-effort — the wait for the MQTT acknowledgement is bounded by the time available before the next scheduled event, the field is null when not observed, and no primary metric depends on it.

## Reproducibility and Evidence Structure

Every experimental run produces an immutable directory of raw evidence, `results/raw/{run_id}/`, containing the controller event log, the per-second resource samples, service logs, a manifest (scenario, seed, commit, image digests, environment, configuration, timestamps, protocol version) and SHA-256 checksums. Raw data becomes immutable at the data freeze; processed tables and figures are regenerated exclusively by a single analysis script, so that every number in Chapter  has a recorded provenance chain from raw file to figure. **\[TODO: Reference the final harness and analysis script paths in src/egw_experiments/ once frozen.\]**
