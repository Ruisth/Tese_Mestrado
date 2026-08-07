# 0006 — Duplicate-detection state persisted in the twin `ingestion` feature

**Status:** Accepted (2026-08-07) — fixed by plan 5.4; CONTRACTS.md section 4

## Context

MQTT QoS 1 guarantees at-least-once delivery, so redeliveries are expected,
especially in the `dropout-reconnect` scenario. Twin updates must be idempotent:
a repeated `message_id` or a non-increasing `seq` must be rejected as a
duplicate (plan 5.4). A purely in-memory dedup cache in the controller would be
lost on every controller restart — precisely the moment (reconnect/restart
testing, plan 9.1) when duplicates are most likely — silently re-applying old
messages and corrupting both twin state and the accepted/duplicate counters that
feed RQ2.

## Decision

- Each twin carries an **`ingestion` feature** with properties
  `last_message_id`, `last_seq`, `last_ts` and `accepted_count`, updated in the
  same Ditto merge-patch as the measurement features.
- Duplicate rule: reject when `message_id` was already processed or when
  `seq <= last_seq` known for that device.
- The controller keeps a local in-memory cache for speed, but the twin is the
  durable source of truth: after a restart, the cache is **rebuilt by reading
  the twin's `ingestion` feature on the first event of each device**.
- Duplicates are recorded in `events.jsonl` with `outcome: "duplicate"` and no
  Ditto write for the measurement payload.

## Consequences

- Positive: duplicate detection survives controller restarts with no extra
  infrastructure (no Redis/DB) — the twin store (MongoDB via Ditto) already
  persists it; state travels with the twin; the recovery test (claim C12) is
  directly verifiable via the Ditto API.
- Negative: dedup granularity is last-seen state per device (`last_seq` +
  last/processed `message_id`), not a full history — an out-of-order valid
  message with a lower `seq` is rejected as a duplicate; this is acceptable
  because the simulator publishes strictly monotonic `seq` per device
  (CONTRACTS.md section 2) over an ordered QoS 1 session.
- Writing `ingestion` alongside measurements slightly enlarges each merge-patch;
  the cost is part of the measured processing path, uniformly for all events.
- The first event after restart incurs one extra twin read (cache rebuild);
  this appears in latency data and is explainable in the analysis.
