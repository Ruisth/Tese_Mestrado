# 0004 — Minimal Ditto deployment (policies/things/gateway) with pre-authentication for the controller

**Status:** Accepted (2026-08-07) — fixed by plan 4.3 and CONTRACTS.md sections 4 and 8

## Context

Eclipse Ditto 3.9.4 ships as multiple services (gateway, policies, things,
things-search, connectivity, UI). The performance platform is a 4 vCPU / 8 GiB
ARM64 VM shared by Mosquitto, MongoDB, the controller and Ditto itself; Ditto
memory pressure is an identified risk (plan section 11, "Ditto excede
recursos"). The research questions require twin materialisation and retrieval,
not search queries, managed connections or a UI. The controller is the only
Ditto client and talks to it over the internal Docker network; the Ditto HTTP
port is never exposed beyond localhost.

## Decision

- Deploy only **`gateway`, `policies` and `things`** (plus MongoDB as their
  store). `search`, `connectivity` and the UI are excluded from the core and
  stay out unless an RQ requires them (plan 4.3).
- All images are Ditto **3.9.4**, verified `linux/arm64` and pinned by digest in
  `images.lock.env` (CONTRACTS.md section 8).
- The controller authenticates to the Ditto gateway via **pre-authentication**
  with subject `pre:egw-controller` (`EGW_DITTO_AUTH_MODE=pre`); each twin's
  policy grants that subject READ+WRITE on `thing:/` and `policy:/`. Basic auth
  remains available as a fallback mode (`EGW_DITTO_AUTH_MODE=basic`).
- MQTT-to-twin bridging is done by our own controller over Ditto's HTTP API, not
  by Ditto `connectivity` — keeping the measurement point (ADR 0005) and the
  validation/idempotency logic (ADR 0006) in one auditable process.

## Consequences

- Positive: smallest resource footprint that still answers RQ2/RQ3; fewer
  containers to pin, monitor and account for in per-container CPU/RAM metrics;
  pre-authentication avoids managing user credentials between two co-located
  containers while keeping the gateway port internal.
- Negative: no Ditto search API (twin reads go through
  `GET /twins/{device_id}` on the controller or direct thing lookup by id); no
  Ditto-managed MQTT connection, so reconnect/backpressure handling is the
  controller's responsibility and is tested explicitly (`dropout-reconnect`).
- Security note: pre-authentication is acceptable only because the Ditto port is
  reachable solely on the internal network/localhost (deployment contract); if
  that boundary ever changes, this ADR must be revisited.
