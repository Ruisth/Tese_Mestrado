# EGW ARM64 deployment stack

Compose stack for the Digital Twin Edge Gateway core on the ARM64 campaign VM
(plan 4.3/5.1, CONTRACTS.md 8): Mosquitto (MQTT/TLS), Eclipse Ditto 3.9.4
core (`gateway`, `policies`, `things` only), MongoDB and the locally built
MQTT->Ditto controller. Ditto `search`, `connectivity`, UI and nginx are
deliberately excluded (plan 4.3).

| Service | Image | Port on host |
|---|---|---|
| mosquitto | `eclipse-mosquitto:2.0.22` (digest-pinned) | `8883` on all interfaces — the ONLY public port |
| ditto-gateway | `eclipse/ditto-gateway:3.9.4` (digest-pinned) | `127.0.0.1:8080` (loopback only) |
| ditto-policies | `eclipse/ditto-policies:3.9.4` (digest-pinned) | none (internal) |
| ditto-things | `eclipse/ditto-things:3.9.4` (digest-pinned) | none (internal) |
| mongodb | `mongo:7.0.39` (digest-pinned) | none (internal) |
| controller | built locally from `src/Dockerfile` | `127.0.0.1:8000` (loopback only) |

All pulled images are pinned by multi-arch digest in `images.lock.env` and
must be `linux/arm64`-native (plan 9.2). The digests were read from the
Docker Hub API on 2026-08-07 and MUST be re-verified on the VM before the
first deploy (step 4 below).

## Prerequisites (ARM64 VM, plan 5.1)

- ARM64-native VM (e.g. Hetzner CAX21 or equivalent: 4 vCPU, 8 GiB RAM,
  >= 80 GB disk), Ubuntu 24.04 LTS. Record provider, region, CPU, kernel and
  OS for the run manifest.
- Docker Engine with the `compose` and `buildx` plugins (`docker compose
  version`, `docker buildx version` must both work).
- `openssl` (3.x, in the Ubuntu 24.04 base).
- A checkout of this repository; all commands below run from
  `src/deployment/` unless stated otherwise. If the checkout lost the
  executable bits, restore them once: `chmod +x scripts/*.sh`.
- The controller container runs as uid 1000. `scripts/validate-config.sh`
  creates `data/events/` with the invoking user so the bind mount is
  writable; on a VM whose default user is not uid 1000, `chown -R 1000:1000
  data/` after creation.

Firewall: allow inbound `8883/tcp` only. Ports 8080 and 8000 are bound to
loopback and must never be exposed publicly (see Security notes).

## Deploy runbook

### 1. Create `.env`

```sh
cp .env.example .env
# edit .env: set MOSQUITTO_SIMULATOR_PASSWORD, MOSQUITTO_CONTROLLER_PASSWORD,
# DITTO_DEVOPS_PASSWORD, EGW_MQTT_PASSWORD (= MOSQUITTO_CONTROLLER_PASSWORD)
# and EGW_HOST (public hostname/IP of this VM, for the TLS SAN).
```

`.env` is never committed (`.gitignore` here and at the repository root).

### 2. Generate TLS material

```sh
EGW_HOST=<vm-public-hostname-or-ip> ./scripts/generate-dev-tls.sh
```

Creates a local dev CA and the broker certificate (SAN: `localhost`,
`mosquitto`, `127.0.0.1`, plus `EGW_HOST`) under `mosquitto/config/certs/`;
825-day validity. Copy ONLY `ca.crt` to the machine that runs the simulator
(its `--ca-cert`). Details: `mosquitto/config/certs/README.md`.

### 3. Generate broker credentials

```sh
set -a; . ./.env; set +a
./scripts/generate-dev-auth.sh
```

Creates `mosquitto/config/passwd` (users `egw-simulator`, `egw-controller`)
via `mosquitto_passwd` inside the pinned broker image. Passwords come from
the environment (or two positional arguments) and are never echoed.
Authorization is enforced by `mosquitto/config/acl`: the simulator may only
publish under `c2dt/#`, the controller may only subscribe (CONTRACTS.md 1).

### 4. Verify the image lock (on the VM)

```sh
./scripts/resolve-image-lock.sh
```

Confirms, for every entry in `images.lock.env`, that a `linux/arm64` image
exists and that the tag still resolves to the locked digest. Any mismatch is
a hard failure: investigate and re-pin deliberately, then record the change
in the project LOG. Manual fallback per image:
`docker manifest inspect <repo>:<tag>`.

### 5. Validate the configuration

```sh
./scripts/validate-config.sh
```

Checks `.env` (present, no `CHANGE_ME` left), TLS files, password file,
digest pins and `docker compose config -q`, and creates `data/events/`.

### 6. Start the stack

```sh
docker compose --env-file .env --env-file images.lock.env up -d --build
```

Both `--env-file` flags are required every time (passing any `--env-file`
disables the automatic `.env` loading, and the image references interpolate
from `images.lock.env`).

### 7. Verify readiness

```sh
docker compose --env-file .env --env-file images.lock.env ps   # all healthy?
curl -s http://127.0.0.1:8000/health   # {"status":"ok"} - process alive
curl -s -o /dev/null -w '%{http_code}\n' http://127.0.0.1:8000/ready
# 200 = MQTT connected AND Ditto reachable; 503 otherwise (CONTRACTS.md 5)
```

Optional deeper checks:

```sh
# Ditto API through the gateway (pre-authentication header, CONTRACTS.md 4):
curl -s -H 'x-ditto-pre-authenticated: pre:egw-controller' \
  http://127.0.0.1:8080/api/2/things/org.c2dta:<device_uuid>

# Broker TLS + auth from the simulator machine:
mosquitto_sub -h <EGW_HOST> -p 8883 --cafile ca.crt \
  -u egw-controller -P <password> -t 'c2dt/+/+/telemetry' -C 1
```

Note: the compose healthcheck probes the broker every 30 s with client id
`egw-healthcheck` and an invalid user; those `not authorised` log lines are
expected and must be filtered out of connection-evidence counts.

## Cold-start timing hooks

The `cold_start` experimental condition (10 repetitions, metric
`time_to_readiness_s`) is defined in `src/egw_experiments/protocol.py` and
executed by the experiments harness as an *external* runner. The measurement
contract is:

- t0: invocation of `docker compose ... up -d` on a stopped stack
  (teardown first; a cold start begins with no running containers);
- t1: first `200` from `GET http://127.0.0.1:8000/ready` (polled by the
  harness) — the controller only reports ready when MQTT is connected and
  Ditto answers, so this bounds the whole stack, not one container;
- secondary evidence: `docker events` / `docker compose ps` health
  transitions and per-service healthchecks defined in `compose.yaml`.

No cold-start numbers are recorded in this repository; they are produced
only by the harness on the campaign VM (plan 7.x).

## Teardown

```sh
# stop, keep state (twins in mongodb-data, broker queue in mosquitto-data):
docker compose --env-file .env --env-file images.lock.env down

# full reset (deletes twins and broker persistence - required before each
# cold-start repetition):
docker compose --env-file .env --env-file images.lock.env down -v
```

`data/events/` (the controller's `events.jsonl` per run) lives on the host
and survives both forms; archive it with the run evidence (plan 5.8).

## Security notes

- `8883` (MQTT over TLS, password auth, per-user ACL, no anonymous access)
  is the only port published on non-loopback interfaces.
- `127.0.0.1:8080` (Ditto gateway) must stay loopback-only: with
  `ENABLE_PRE_AUTHENTICATION=true`, anyone who can reach the port can claim
  any authorization subject via the `x-ditto-pre-authenticated` header.
- `127.0.0.1:8000` (controller API) is unauthenticated by design and stays
  loopback-only.
- MongoDB and the Ditto policies/things services publish no host ports.
- Secrets (`.env`, `mosquitto/config/passwd`, everything under
  `mosquitto/config/certs/` except its README) are never committed
  (plan 9.2); `.env.example` documents every variable.
- Every pulled image is `linux/arm64`-native and pinned by digest in
  `images.lock.env` (plan 9.2); the controller base image is digest-pinned
  in `src/Dockerfile`. Never deploy after a failed
  `scripts/resolve-image-lock.sh` run.
