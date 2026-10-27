# 0005 — Primary latency measured inside the controller with a monotonic clock

**Status:** Accepted (2026-08-07) — fixed by plan 5.1, 5.8 and 7.3; CONTRACTS.md section 5

## Context

RQ3 requires latency figures for the gateway's twin-materialisation path. During
benchmarks the simulator runs outside the ARM VM (ADR 0001), so any end-to-end
timestamp difference would include the external network link and, worse, the
clock offset between two machines. The simulator's payload field `ts` is a
wall-clock value from a different host and is neither monotonic nor synchronised
to the controller's clock. Cross-host clock comparison (NTP-dependent) is not
defensible at millisecond resolution.

## Decision

- The **primary latency metric** is measured entirely inside the controller
  process, between the MQTT message callback and the Ditto acknowledgement:
  - `received_monotonic_ns` = `time.monotonic_ns()` in the MQTT callback;
  - `ditto_ack_monotonic_ns` = `time.monotonic_ns()` after the Ditto 2xx
    response;
  - `latency_ms = (ditto_ack_monotonic_ns - received_monotonic_ns) / 1e6`.
- Both timestamps come from the **same monotonic clock in the same process**;
  wall-clock time is never used for latency.
- The simulator's `ts` field is **never** used in this measurement; it remains
  in the payload only as event data.
- Per-event records go to `events.jsonl` (one file per `run_id`); `rejected`,
  `duplicate` and `failed` outcomes carry `null` ack/latency fields.
- Reported statistics: p50/p95/p99 per run; the run (not the message) is the
  statistical unit (plan 7.3).

## Consequences

- Positive: immune to cross-host clock skew, NTP steps and wall-clock
  adjustments; measures exactly the gateway processing segment
  (validation + conversion + Ditto write + ack) that RQ3 asks about; trivially
  reproducible from raw `events.jsonl`.
- Negative: end-to-end (device-to-twin) latency including the network link is
  not the primary metric and can only be discussed qualitatively or via
  separate simulator-side publish/puback timings (`sent_events.jsonl`), never
  by mixing clocks across hosts.
- The measurement points are part of the controller contract; refactoring the
  controller must preserve callback-to-ack instrumentation in one process.
