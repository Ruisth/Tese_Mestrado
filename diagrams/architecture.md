# EGW architecture diagrams

Source of truth: `PLANO_DESENVOLVIMENTO_INTEGRADO_EDGE_GATEWAY_2026.md` section 5
(normative) and `src/CONTRACTS.md` v1.0. These diagrams show only contracted
behaviour (topics, ports, endpoints, outcomes); they make no performance claims.

## 1. Logical component diagram

Plan sections 5.2-5.5; CONTRACTS sections 1, 4, 5 and 8. The simulator is a load
generator external to the gateway stack; the controller is the MQTT-to-Ditto
bridge with mandatory JSON Schema validation and idempotent twin updates.

```mermaid
flowchart LR
    subgraph LOADGEN["Load generator (runs outside the gateway stack)"]
        SIM["egw_simulator<br/>python -m egw_simulator run<br/>scenarios: smoke, nominal, load-sweep,<br/>dropout-reconnect, invalid-payload, soak<br/>output: manifest.json + sent_events.jsonl"]
    end

    subgraph STACK["Edge Gateway stack (docker compose, linux/arm64 images pinned by digest)"]
        MOSQ["Mosquitto broker<br/>:8883 TLS, QoS 1<br/>password_file + ACL<br/>(no anonymous access)"]
        CTRL["egw_controller (MQTT-to-Ditto bridge)<br/>1. JSON Schema validation (draft 2020-12)<br/>2. dedupe: message_id + seq vs twin ingestion<br/>3. merge-patch conversion<br/>counters: accepted / rejected / duplicate / failed"]
        DGW["Ditto gateway<br/>:8080 (localhost-only on host)<br/>pre-authentication pre:egw-controller"]
        DPOL["Ditto policies<br/>(internal)"]
        DTHG["Ditto things<br/>(internal)"]
        MONGO[("MongoDB<br/>(internal)")]
    end

    SCHEMAS["src/schemas/*.schema.json<br/>(EGW_SCHEMA_DIR)"]
    API["Controller HTTP API :8000 (localhost-only)<br/>GET /health - GET /ready<br/>GET /twins/(device_id) - GET /metrics"]
    EVT["events.jsonl (one per run_id, EGW_EVENT_LOG_DIR)<br/>run_id, message_id, seq, received_monotonic_ns,<br/>ditto_ack_monotonic_ns, latency_ms, outcome, attempts, error"]

    SIM -- "PUBLISH mqtts, QoS 1<br/>c2dt/(egw_id)/(device_uuid)/telemetry" --> MOSQ
    MOSQ -- "subscription c2dt/+/+/telemetry" --> CTRL
    CTRL -- "PATCH /api/2/things/org.c2dta:(device_uuid)<br/>content-type: application/merge-patch+json<br/>policy+thing created on first event" --> DGW
    DGW --> DPOL
    DGW --> DTHG
    DPOL --> MONGO
    DTHG --> MONGO
    SCHEMAS -. "loaded at startup" .-> CTRL
    CTRL -- "append per event" --> EVT
    CTRL --- API
```

Notation: `(egw_id)` and `(device_uuid)` stand for the `{egw_id}` and
`{device_uuid}` placeholders of the CONTRACTS topic and thingId templates
(parentheses avoid Mermaid brace parsing).

## 2. Deployment diagram — two platforms (plan 5.1, CONTRACTS 8)

The functional platform (WSL2 + QEMU) validates build, boot, systemd, network
and the OCI runtime only; no performance conclusions come from it. All
measurements run on the ARM64 cloud VM, with the simulator executing off-VM so
the external link is excluded from the controller-side latency measurement.

```mermaid
flowchart TB
    subgraph FUNC["Functional platform - build/boot validation only, no performance claims (plan 5.1)"]
        subgraph WSL["Windows 11 host / WSL2 Ubuntu 24.04 LTS (build tree on ext4)"]
            KAS["kas manifest (qemuarm64)<br/>BitBake build of egw-image"]
            QEMU["QEMU aarch64 boot<br/>systemd, network, OCI runtime<br/>functional checks"]
        end
        KAS --> QEMU
    end

    subgraph PERF["Performance platform - all benchmark runs (plan 5.1)"]
        subgraph VM["Hetzner cloud VM, native ARM64 (CAX21-class: 4 vCPU, 8 GiB RAM, >= 80 GB disk; shared-CPU limitation documented)"]
            CSTACK["docker compose (linux/arm64):<br/>Mosquitto :8883 exposed<br/>Ditto gateway :8080 localhost-only<br/>Ditto policies / things + MongoDB internal<br/>controller :8000 localhost-only"]
        end
        OPS["Operator machine (off-VM, plan 5.1)<br/>egw_simulator + experiment harness<br/>collects results/raw/(run_id)/"]
        OPS -- "mqtts :8883<br/>TLS + username/password" --> CSTACK
        OPS -. "ssh: harness control,<br/>resources.csv, logs" .-> VM
    end

    FUNC -. "same source tree and contracts;<br/>no measurements transferred" .- PERF
```

Primary latency is measured inside the controller process on the VM, between
MQTT receive and the Ditto 2xx acknowledgement (plan 5.1 and 5.8; CONTRACTS 5).

## 3. Sequence diagram — one telemetry event (accepted, duplicate and invalid branches)

Plan sections 5.4-5.5; CONTRACTS sections 4-5.

```mermaid
sequenceDiagram
    autonumber
    participant SIM as egw_simulator (off-VM)
    participant MQ as Mosquitto :8883 (TLS, QoS 1)
    participant CT as egw_controller
    participant DT as Ditto gateway :8080
    participant DB as MongoDB (via policies/things)
    participant EL as events.jsonl

    SIM->>MQ: PUBLISH c2dt/(egw_id)/(device_uuid)/telemetry
    MQ-->>SIM: PUBACK (simulator records publish/puback ns in sent_events.jsonl)
    MQ->>CT: deliver message (subscription c2dt/+/+/telemetry)
    Note over CT: received_monotonic_ns = time.monotonic_ns()
    CT->>CT: JSON Schema validation (draft 2020-12, before any Ditto call)

    alt payload invalid
        CT->>EL: outcome=rejected (ditto_ack ns and latency_ms null)
    else duplicate: message_id already processed or seq <= last_seq
        Note over CT: dedupe state from twin ingestion feature;<br/>local cache rebuilt from twin after controller restart
        CT->>EL: outcome=duplicate (ditto_ack ns and latency_ms null)
    else valid and new
        opt first event for this device_uuid
            CT->>DT: create policy + thing org.c2dta:(device_uuid)
            DT->>DB: persist policy and thing
        end
        CT->>DT: PATCH /api/2/things/org.c2dta:(device_uuid) (merge-patch+json)
        Note over CT,DT: transient errors (timeout, 5xx): retry up to EGW_RETRY_MAX,<br/>exponential backoff base EGW_RETRY_BACKOFF_MS; 4xx not retried
        DT->>DB: persist feature update + ingestion (last_message_id, last_seq, last_ts, accepted_count)
        DT-->>CT: 2xx acknowledgement
        Note over CT: ditto_ack_monotonic_ns; latency_ms = (ack - received) / 1e6
        CT->>EL: outcome=accepted (latency_ms, attempts)
    end

    Note over CT,EL: exhausted retries or non-retryable errors are logged as outcome=failed
```
