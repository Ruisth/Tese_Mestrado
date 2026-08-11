<!-- GENERATED FILE - DO NOT EDIT.
     Source: latex/chapters/04_architecture.tex (design sections)
     Regenerate with: python thesis/tools/generate_sections.py
     The LaTeX tree under thesis/latex/ is the single edited source. -->

# Architecture

## Overview

The system comprises two environments and five runtime components. The *platform layer* is `egw-image`, a minimal Linux image defined with the Yocto Project (Scarthgap LTS line) from a pinned `kas` manifest; its functional validation — boot to systemd with networking and an OCI container runtime on `qemuarm64` — is prescribed by the experimental protocol (Section ) and is to be reported in Chapter . The *service layer* is a containerised digital-twin stack designed for deployment on a native ARM64 environment: Mosquitto (MQTT broker with TLS), a purpose-built ingestion controller, Eclipse Ditto 3.9.4 (gateway, policies and things services) and MongoDB. A deterministic CLI simulator generates the wearable telemetry.

**\[TODO: Insert final component-and-dataflow diagram from diagrams/ (logical architecture: simulator to broker to controller to Ditto to MongoDB, with the evidence log path).\]**

Telemetry flows as follows: the simulator publishes device events over MQTT with QoS 1 to a per-device topic; the controller subscribes, validates each event against its schema, enforces idempotency, converts the event to a merge patch and updates the corresponding Ditto twin over HTTP; every processed message is appended to a structured event log that is the primary measurement source of the evaluation.

## Normative Interfaces

### MQTT Transport

The broker exposes port 8883 with TLS and mandatory username/password authentication; anonymous access is prohibited. Telemetry is published with QoS 1 to the normative topic `c2dt/{egw_id}/{device_uuid}/telemetry`; the controller subscribes with the filter `c2dt/+/+/telemetry`. Access control is least-privilege: the simulator account may only publish under the telemetry namespace, and the controller account may only subscribe. A `--no-tls` profile exists for local development only and is never used in benchmarks.

### Common Event Envelope

Every telemetry payload carries a common envelope (`schema_version` 1.0.0) alongside the device-specific measurements:

| **Field** | **Type / rule** |
|:---|:---|
| `schema_version` | semantic version string, `1.0.0` |
| `run_id` | string, immutable per experimental run |
| `message_id` | UUID v5 derived from `run_id`, `device_uuid` and `seq` under a fixed project namespace |
| `seq` | integer $`\geq 0`$, monotonically increasing per device |
| `ts` | RFC 3339 UTC timestamp with `Z` suffix, millisecond resolution |
| `egw_id` | gateway identifier string |
| `device_uuid` | stable UUID v4 of the device |
| `device_type` | one of `smartwatch`, `smart_ring`, `smart_clothing` |

Common event envelope (from `src/schemas/telemetry-envelope-v1.schema.json`). {#tab:envelope}

Deriving `message_id` deterministically from the run, device and sequence number makes duplicate detection exact and makes the entire workload reproducible from the manifest alone.

### Device Measurement Schemas

Each device type adds its measurement fields at the top level of the payload, validated by a dedicated JSON Schema (draft 2020-12, with `unevaluatedProperties: false` so that unknown fields are rejected): the smartwatch reports heart rate and geographic position; the smart ring reports skin temperature and blood-oxygen saturation; the smart clothing reports three-axis acceleration and breathing rate. Nominal emission rates are in the fixed proportion 1 : 0.2 : 10 (smartwatch : ring : clothing), and the simulator’s aggregate rate parameter is split across devices in that proportion. Each device type also has a WoT TD 1.1 document aligned with its schema (`src/things/`).

## Twin Model

Each device maps to one Ditto thing with identifier `org.c2dta:{device_uuid}` and a dedicated policy of the same name, created on the first event of that device. Twin attributes record the device type, gateway identifier and schema version. Measurements are organised into features per device type: the smartwatch twin has `vitals` and `location`; the smart ring has `thermo` and `oximetry`; the smart clothing has `motion` and `respiration`; and all twins share the `ingestion` bookkeeping feature described above, whose properties are `last_message_id`, `last_seq`, `last_run_id`, `last_ts` and `accepted_count` — `last_run_id` being the property that anchors the run-scoped sequence floor of Section . The controller authenticates to Ditto as a pre-authenticated subject with read/write permission on the thing and policy resources.

## Security Considerations

The security baseline is deliberate and modest: TLS with server authentication on the external MQTT listener, mandatory client credentials, per-account topic ACLs, internal-only exposure of Ditto and the controller API, and no secrets in version control (an `.env.example` documents required variables). No claims are made about security properties beyond this configuration baseline; a security evaluation is out of scope (Section ).
