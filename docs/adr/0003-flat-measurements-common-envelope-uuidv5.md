# 0003 — Flat measurement fields with common envelope v1 and UUIDv5 message_id

**Status:** Accepted (2026-08-07) — fixed by CONTRACTS.md sections 2–3 (plan 5.3)

## Context

Three wearable types (smartwatch, smart ring, smart clothing) publish telemetry
that must be validated per device type, correlated across simulator, controller
and Ditto, and deduplicated under QoS 1 redelivery. The reference payloads from
the C2DTA paper and `INTERFACES.md` carry measurements as top-level fields. A
correlation identifier is needed that both ends can compute independently and
deterministically, without coordination or storage on the publisher side.

## Decision

- **Common envelope v1** (`schema_version 1.0.0`): every payload carries
  `schema_version`, `run_id`, `message_id`, `seq`, `ts` (RFC 3339 UTC, ms
  resolution), `egw_id`, `device_uuid`, `device_type`.
- **Flat measurement fields:** device measurements (`heart_rate_bpm`, `lat`,
  `lon`; `skin_temp_c`, `spo2_pct`; `accel_x/y/z`, `breathing_rpm`) live at the
  top level of the payload next to the envelope, not in a nested object —
  preserving continuity with the reference payload shape of the prior work.
- **Deterministic `message_id`:** UUID v5 over the project namespace
  `6b1a3f52-8c1e-5e2b-9f0d-c2d7a1e4b8a0` with name
  `"{run_id}:{device_uuid}:{seq}"`. The same logical message always yields the
  same id; redelivered messages are detectable as duplicates by id equality.
- One JSON Schema per device type (draft 2020-12) composed with the envelope
  schema, with `unevaluatedProperties: false` so unknown fields are rejected.

## Consequences

- Positive: duplicates are detectable without publisher-side state (id is
  recomputable from `run_id`/`device_uuid`/`seq`); `seq` gives a per-device
  monotonic order check; validation is a single flat-object check; simulator
  `sent_events.jsonl` and controller `events.jsonl` join naturally on
  `message_id`.
- Negative: flat fields mean device schemas and Ditto feature mappings must be
  maintained per type (no generic `measurements` blob); adding a device type
  requires a new schema version and a features mapping (acceptable: device
  count is capped at three, plan 4.5).
- Any envelope change requires a new `schema_version` and coordinated updates to
  simulator, controller, schemas, TDs and tests (CONTRACTS.md header rule).
