# EGW ARM64 deployment stack

Compose stack for the Digital Twin Edge Gateway core on the ARM64 campaign VM
(plan 4.3/5.1, CONTRACTS.md 8): Mosquitto (MQTT/TLS), Eclipse Ditto 3.9.4
core (`gateway`, `policies`, `things` only), MongoDB and the prebuilt
MQTT->Ditto controller. Ditto `search`, `connectivity`, UI and nginx are
deliberately excluded (plan 4.3). Nothing is built on the gateway: the five
external images are pulled by their pinned digests and the controller image
is loaded from an archive (step 4b).

| Service | Image | Port on host |
|---|---|---|
| mosquitto | `eclipse-mosquitto:2.0.22` (digest-pinned) | `8883` on all interfaces — the ONLY public port |
| ditto-gateway | `eclipse/ditto-gateway:3.9.4` (digest-pinned) | `127.0.0.1:8080` (loopback only) |
| ditto-policies | `eclipse/ditto-policies:3.9.4` (digest-pinned) | none (internal) |
| ditto-things | `eclipse/ditto-things:3.9.4` (digest-pinned) | none (internal) |
| mongodb | `mongo:7.0.39` (digest-pinned) | none (internal) |
| controller | `egw-controller:0.1.0`, prebuilt from `src/Dockerfile` and loaded (`pull_policy: never`, no `build:`) | `127.0.0.1:8000` (loopback only) |

All pulled images are pinned by multi-arch digest in `images.lock.env` and
must be `linux/arm64`-native (plan 9.2). The digests were read from the
Docker Hub API on 2026-08-07 and MUST be re-verified on the VM before the
first deploy (step 4 below).

## Prerequisites (ARM64 VM, plan 5.1)

- ARM64-native VM (e.g. Hetzner CAX21 or equivalent: 4 vCPU, 8 GiB RAM,
  >= 80 GB disk), Ubuntu 24.04 LTS. Record provider, region, CPU, kernel and
  OS for the run manifest.
- Docker Engine with the `compose` plugin (`docker compose version` must
  work). `buildx` is needed on the provisioning host that builds the
  controller image (step 4b), not on the gateway; without it
  `scripts/resolve-image-lock.sh` still checks for `linux/arm64` but cannot
  compare the tag with the locked digest (it prints a WARNING).
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
`server.key` is created `0600` for the invoking user and is **not yet readable
by the broker**; step 3b fixes and verifies that. `--force` removes and
regenerates all four files (run step 3b again afterwards).

### 3. Generate broker credentials

```sh
set -a; . ./.env; set +a
./scripts/generate-dev-auth.sh
```

Creates `mosquitto/config/passwd` (users `egw-simulator`, `egw-controller`)
via `mosquitto_passwd` inside the pinned broker image and hands the file to
the image's unprivileged `mosquitto` user (uid/gid 1883, mode `0600`).
Passwords come from the environment (or two positional arguments) and are
never echoed. `EGW_BROKER_IMAGE=<reference>` overrides the image (offline
hosts that only hold a loaded tag). Authorization is enforced by
`mosquitto/config/acl`: the simulator may only publish under `c2dt/#`, the
controller may only subscribe (CONTRACTS.md 1).

### 3b. Hand the broker its secrets and verify readability

```sh
./scripts/prepare-broker-secrets.sh
```

The broker does not read its key as root. Mosquitto 2.x drops to its
unprivileged user right after loading `mosquitto.conf` and opens `keyfile`,
`certfile`, `password_file` and `acl_file` only afterwards
(<https://mosquitto.org/documentation/migrating-to-2-0/>). In the official
`eclipse-mosquitto` 2.0.x image that user is uid/gid 1883
(`docker/2.0-openssl/Dockerfile` in
<https://github.com/eclipse-mosquitto/mosquitto>), and the image entrypoint
cannot `chown` the read-only bind mounts of `compose.yaml`. The script
therefore sets `passwd` and `certs/server.key` to owner `1883:1883`, mode
`0600` (using `sudo` only if something has to change; `EGW_BROKER_PRIV=docker`
does it from a one-shot root container instead), refuses any secret with a
permission bit for "others", and then proves readability by reading every
broker input as `--user 1883:1883` in a one-shot container of the pinned
broker image with the same read-only mounts as `compose.yaml`. It also fails
if that uid can read `ca.key`. Exit code 0 is required before step 6. The
broker keeps its default privilege drop to uid 1883 (no `user: root` in
`compose.yaml`, no `user root` in `mosquitto.conf`; the container still starts
as root, reads `mosquitto.conf` and then drops), and no key is made
world-readable. Not yet executed against a Docker engine (written 2026-09-18).

`EGW_BROKER_UID` / `EGW_BROKER_GID` override the numeric ids (the read test
fails if the default differs from the image's `mosquitto` user). `--check`
verifies without changing anything. `--acl` additionally hands `acl` to uid
1883 (mode `0640`), which silences Mosquitto's ownership warnings for
`acl_file`; use it only on a deployed copy, never in a git working tree
(`acl` is a tracked file). Re-run this step after every step 2 (`--force`)
or step 3.

### 4. Verify the image lock (on the VM)

```sh
./scripts/resolve-image-lock.sh
```

Confirms, for every entry in `images.lock.env`, that a `linux/arm64` image
exists and that the tag still resolves to the locked digest. Any mismatch is
a hard failure: investigate and re-pin deliberately, then record the change
in the project LOG. Manual fallback per image:
`docker manifest inspect <repo>:<tag>`.

### 4b. Provide the controller image (prebuilt; never built on the gateway)

`compose.yaml` gives the controller `image: egw-controller:0.1.0` with
`pull_policy: never` and no `build:`. The gateway has no build context, no
`buildx` and no `pip`; the image is built elsewhere and loaded.

On a **provisioning host** (Docker with `buildx` and `linux/arm64`, natively
or through emulation; Docker Desktop on Windows through Git Bash works), from
a clean checkout of the commit to deploy:

```sh
sh src/deployment/scripts/build-controller-image.sh <output-dir>
```

The script refuses a build context (`src/`) with modified or untracked files,
or with git-ignored files below a path that `src/Dockerfile` copies, unless
`--allow-dirty` is given (development only; the record then says
`source_tree_state=dirty`), builds `linux/arm64` with `buildx` and without
cache, exports the image with `docker save` and writes, next to
`egw-controller-0.1.0-arm64.tar`, the identity record
`egw-controller-0.1.0-arm64.identity.txt`: source commit and tree state,
base-image reference of `src/Dockerfile`, image id (digest of the image
configuration, read from the archive), architecture and OS, archive SHA-256
and size, `python --version` and `pip freeze --all` taken from the built
image, Docker and `buildx` versions, UTC time. It pushes nothing; no registry
holds this image. `<output-dir>` must lie outside `src/`.

On the **gateway**, load the archive and compare the loaded image with the
record (copy the record, or both files, to the gateway first):

```sh
docker load -i egw-controller-0.1.0-arm64.tar
# or, without storing the archive on the gateway, from the provisioning host:
#   ssh <gateway> docker load < egw-controller-0.1.0-arm64.tar
sh scripts/verify-controller-image.sh egw-controller-0.1.0-arm64.identity.txt
```

Exit code 0 (`CONTROLLER IMAGE IDENTITY: verified`) is required before
step 6. The check compares image id, architecture, OS and revision label, and
refuses a record with `source_tree_state=dirty` unless `--allow-dirty` is
given (development only, never for evidence). A loaded image has a tag and an
image id but no `RepoDigests`; the image id is therefore its identity. Keep
the record with the run evidence.
Neither script has been executed against a Docker engine yet (written
2026-09-18).

**Limitation, stated plainly:** the Python dependencies of this image are
**not locked**. `src/Dockerfile` runs `pip install .` without hashes, so the
`pip_freeze` lines of the record say what was installed in that one build;
they do not make it reproducible. This is accepted for the first functional
demonstration only and is to be resolved before the experimental freeze with
`scripts/generate-runtime-lock.sh` (see "Runtime Python lock" below).

### 5. Validate the configuration

```sh
./scripts/validate-config.sh
```

Checks `.env` (present, no `CHANGE_ME` left), TLS files, password file,
readability of the broker's secrets as uid 1883 (step 3b in `--check` mode:
changes nothing), digest pins, `docker compose config -q` and the presence of
the controller image of step 4b, and creates `data/events/`.

### 6. Start the stack

```sh
# optional, makes the download a separate, visible step (the five external
# services, by their pinned digests; the controller is never pulled):
docker compose --env-file .env --env-file images.lock.env pull \
    mosquitto mongodb ditto-policies ditto-things ditto-gateway

docker compose --env-file .env --env-file images.lock.env up -d
```

Both `--env-file` flags are required every time (passing any `--env-file`
disables the automatic `.env` loading, and the image references interpolate
from `images.lock.env`). Never add `--build`: `compose.yaml` has nothing to
build, and a missing controller image is a named failure (`pull_policy:
never`), answered by step 4b. UNVERIFIED on the gateway's Compose 2.26.0:
that `up -d` finds the images pulled by `repo:tag@sha256:` without contacting
the registry again, and how a bare `pull` treats a `pull_policy: never`
service (hence the service names above).

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

# ACL proof with known traffic, on the VM/guest (exit 0 PASS, 1 FAIL,
# 3 INCONCLUSIVE, 2 usage/precondition = nothing run; evidence under
# /opt/egw/evidence/itest-acl-<tag>/):
sh scripts/probe-acl.sh <tag>
```

`scripts/probe-acl.sh` runs `mosquitto_sub`/`mosquitto_pub` inside the broker
container: an authorised (`egw-controller`) and an unauthorised
(`egw-simulator`) subscriber listen concurrently on `c2dt/#` while tagged
messages are published as each user on `c2dt/acl-probe/<tag>` (outside the
controller's filter `c2dt/+/+/telemetry`, not retained). Mosquitto's built-in
`acl_file` check grants every SUBSCRIBE and filters at delivery, so only
delivery of known traffic proves the restriction. It reads `.env` from
`EGW_DEPLOY_DIR` (default `/opt/egw/deployment`) and uses
`images.lock.env` as second `--env-file` unless `EGW_COMPOSE_ENV` names
another file. Not yet executed against a broker (written 2026-09-18).

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

### Runtime Python lock — blocking before `exp-v1`

The digest-pinned Python base is not sufficient while `src/Dockerfile` still
runs the broad `pip install .`: transitive dependencies can change without a
repository change. Therefore a controller image built in the current state is
acceptable for development only and **must not be used for thesis
measurements**.

The first end-to-end functional demonstration (one device, emulated ARM64
guest, labelled as emulated functional evidence, not a measurement) uses such
an image, with **unlocked Python dependencies**. What was installed is
recorded as `pip freeze --all` in the identity record of step 4b; that
documents one build and does not make it reproducible. This is to be resolved
before the experimental freeze, by the procedure below.

Generate the lock on an `aarch64` host (the helper refuses other
architectures). Under the plan adopted on 2026-09-18 that host is the
integrated Yocto ARM64 guest emulated under QEMU/TCG, in which the controller
image is deployed; the plan makes the complete hashed dependency lock of that
guest runtime a precondition before the protocol freeze, and no native campaign
VM is required for it:

```sh
cd /opt/egw/src
./deployment/scripts/generate-runtime-lock.sh
git diff -- requirements-runtime.lock
```

The helper resolves runtime and PEP 517 build dependencies inside the exact
digest-pinned Python 3.12 ARM64 base, writes
`src/requirements-runtime.lock`, requires a SHA-256 hash for every resolved
distribution, installs that lock with
`--require-hashes --only-binary=:all:`, builds the project with isolation
disabled, and runs `pip check` in the disposable container. It does not
generate a placeholder on Windows/x86.

Before `exp-v1`, review and commit that real lock, then change the Dockerfile
to copy it and install in two explicit steps:

```dockerfile
COPY requirements-runtime.lock ./
RUN pip install --require-hashes --only-binary=:all: \
        -r requirements-runtime.lock \
    && pip install --no-build-isolation --no-deps . \
    && pip check
```

Build on ARM64, record the resulting controller image digest and archive the
full `pip check`/build log with the run environment. The lock includes the
`pyproject.toml` build-system requirements; disabling build isolation is
mandatory so the build cannot download an unsealed `setuptools` or other
backend dependency. Any change to `pyproject.toml`, the base-image digest or
target Python version invalidates the lock and requires regeneration. Until
this checklist is complete, the runtime-lock gate remains explicitly
**blocked (ARM64 VM absent)**.

## SUT-side evidence collection (experiments harness)

The experiments harness (`src/egw_experiments/`, see `experiments/README.md`)
runs OFF this VM (plan 5.1). Three scripts in `scripts/` run ON the VM and
produce the SUT-side evidence the harness ingests (2026-08-08 audit, section
9). Timed runs without the first two are marked `validity: "invalid"` by the
harness.

### 1. `scripts/capture-sut-environment.sh` — SUT environment manifest

Captures the environment of the system under test (`uname -a`, OS
`PRETTY_NAME`, `nproc`, CPU model, `MemTotal`, Docker/Compose versions,
capture time) plus the plan 5.1 normative fields passed via environment
variables (`EGW_PROVIDER`, `EGW_REGION`, `EGW_INSTANCE_TYPE`,
`EGW_SHARED_VCPU_NOTE` — the shared-vCPU caveat is mandatory):

```sh
EGW_PROVIDER="Hetzner Cloud" EGW_REGION="fsn1" \
EGW_INSTANCE_TYPE="CAX21 (4 vCPU ARM64, 8 GiB)" \
EGW_SHARED_VCPU_NOTE="shared vCPU; neighbor load may affect results" \
sh scripts/capture-sut-environment.sh sut_environment.json
```

Fetch the file to the harness host and pass `--sut-env-from` on every timed
run. The harness writes its own host capture as `loadgen_environment.json`;
the run manifest references both (two-environments rule, audit 9.2). The
analysis also uses `nproc` from this file to normalize docker-stats CPU
percentages to host-level utilization (audit 9.7). Re-capture after any VM
change (resize, kernel or Docker update).

### 2. `scripts/collect-resources.sh` — 1 Hz container resources

Samples `docker stats` once per second into a CSV the analysis reads
directly (`ts_utc,container,cpu_pct,mem_bytes,mem_pct`), until SIGTERM or
`--duration`. **Superseded on 2026-09-19 in two points** (the sentence is kept
as the record of what the collector did until then): the default sampling
source is no longer `docker stats` but the kernel's cgroup v2 accounting, and
the CSV carries a sixth column, `host`, so the header is
`ts_utc,container,cpu_pct,mem_bytes,mem_pct,host`. Start it before the run's
warm-up, stop it after the 60 s confirmation window, fetch the CSV and ingest
with `--resources-from`:

```sh
# on the VM (or via ssh/systemd-run; see the script header):
sh scripts/collect-resources.sh /tmp/resources-<run_id>.csv --duration 900
```

The harness's own `--local-resources` sampler measures the load-generator
host and is dev-only (audit 9.1).

#### Why the source changed (2026-09-19)

On the emulated ARM64 guest (QEMU/TCG) one `docker stats --no-stream` call
cost 3 to 5 s while the stack was idle and about 21 s while it was working,
because the CLI must round-trip the daemon and the daemon samples every
container: the collector produced **7 distinct sample instants across 42 rows
in a 150 s window**, against `MIN_DISTINCT_SAMPLE_INSTANTS = 30` and
`MIN_RESOURCE_SAMPLES = 30` (`src/egw_experiments/resources.py`).
`egw_experiments run` therefore refused the timed run, marked it `invalid` and
withheld `SHA256SUMS`. The harness was behaving correctly; the sampler was the
defect. Those figures were observed on 2026-09-18 and recorded in a
candidate-evidence note held **outside** this repository and unsealed; they are
not evidence in this repository and no claim rests on them.

#### What each column now holds

Reading the cgroup files costs no daemon round trip: a few small file reads per
sample. The columns keep exactly the meaning they had, so ingested files from
before and after this change are the same quantity.

| Column | Default source (`cgroup`) | `--source docker` |
|---|---|---|
| `ts_utc` | `date -u` taken once per sample, before the readings | same |
| `container` | the container's own `config.v2.json` under the Docker data root; failing that a `docker ps` listing refreshed only when an unknown container id appears and at most once every 10 s; as a last resort the 12-character container id, which keeps the non-empty-name rule of the ingest validation | the `Name` field of `docker stats` |
| `cpu_pct` | `100 × Δ(cpu.stat usage_usec) / Δ(wall clock)` — docker's single-CPU basis, so a multi-threaded container exceeds 100 and the analysis normalises by `nproc` from `sut_environment.json` (audit 9.7). Wall time comes from `/proc/uptime`, so a clock step does not corrupt it (it still corrupts `ts_utc`, which the harness catches: a timestamp going backwards is refused) | `CPUPerc` |
| `mem_bytes` | `memory.current` minus `memory.stat`'s `inactive_file` — the same "used" part `docker stats` reports on cgroup v2 | the used half of `MemUsage`, converted to bytes |
| `mem_pct` | `100 × mem_bytes / memory.max`, falling back to `MemTotal` when the cgroup is unlimited, as `docker stats` does | `MemPerc` |
| `host` | `hostname` of the machine the sample was taken on; verified at ingestion against `sut_environment.json` | same |

Both cgroup driver layouts are sampled: `system.slice/docker-<id>.scope`
(systemd driver) and `docker/<id>` (cgroupfs driver). The CSV schema, the
header rule, the host provenance column and the append/restart refusal are
unchanged, and the script remains POSIX sh + awk with no bashism and no gawk
extension (the gateway image ships busybox 1.36.1).

**The first sample only primes.** With a fresh state file the first cgroup
sample records the CPU counters and writes no row, because a rate needs two
readings. Collection therefore starts one interval after the script does, and
a collector must run one interval longer than the window it has to cover. The
harness hooks start it before the warm-up and stop it after the confirmation
window, so that interval falls outside the measured window.

#### Options

| Option | Default | Effect |
|---|---|---|
| `--duration SECONDS` | `0` (run until SIGTERM/SIGINT) | whole seconds; checked after each sample |
| `--interval SECONDS` | `1` | whole seconds, at least 1. The loop sleeps this long **after** each sample, so the achieved period is the interval plus the cost of one sample; there is no compensation |
| `--source auto\|cgroup\|docker` | `auto` | `cgroup` reads `/sys/fs/cgroup`; `docker` restores the previous `docker stats --no-stream` loop unchanged, for a host whose cgroup v2 tree is not visible (cgroup v1, or a Docker the collector cannot see into); `auto` picks `cgroup` when a container cgroup is discoverable and `docker` otherwise |
| `--max-samples N` | `0` (no limit) | the priming sample counts against the limit, so a cgroup run writes **N−1** rows |
| `--no-docker` | off | never call `docker ps` for names; names then come from `config.v2.json` or from the 12-character id |
| `--cgroup-root`, `--docker-root`, `--state-file`, `--uptime-from`, `--meminfo-from` | the real paths | synthetic-tree options, for `src/tests/test_collect_resources.py` only. **They are never used in a run:** they let the collector read its measurements from any directory, and the CSV records neither the sampling source nor the roots, so a file produced with them is indistinguishable at ingestion from a measured one |

#### Reading which source was chosen

Before the loop the collector writes one line to stderr naming the source in
force for the whole run:

```text
collecting container resources from cgroup at one sample every 1s into /tmp/resources-<run_id>.csv (duration: 900s, 0 = until SIGTERM)
```

`from cgroup` or `from docker` is the whole statement. Under `--source auto`
the choice is made **once**, before the first sample, and is never
re-evaluated; when no container cgroup is discoverable the collector first
prints

```text
note: no container cgroup found under /sys/fs/cgroup; falling back to docker stats
```

and then runs the docker-stats loop for the rest of the run. Read that line
wherever the orchestration sends the collector's stderr — the log file of the
manual `nohup` form, or `journalctl -u egw-resources-<run_id>` on the VM for
the `systemd-run` form. **The CSV does not record it**, so a run whose stderr
was not kept cannot be shown afterwards to have used the cgroup source.

#### State of this change, stated plainly (2026-09-19)

`src/tests/test_collect_resources.py` covers the cgroup path with eleven
scenarios against a synthetic cgroup tree, each run under every POSIX shell
present (`sh`, `dash`, `bash`): `33 passed` on WSL2 Ubuntu 24.04, Python
3.12.3, pytest 9.1.1, in about 15 s. They include the priming sample writing no
row, 0.5 s of CPU over 1.0 s of wall clock reading `50.00`, a container using
three cores reading `300.00`, the `MemTotal` fallback, both cgroup driver
layouts, the name fallback chain, a container that disappears, a counter that
goes backwards, a foreign CSV header, and a five-sample cadence case whose
output passes `validate_resources_csv` with only the two threshold arguments
relaxed to the sample count. A smoke run against the workstation's own cgroup
tree found no container cgroup there and so exercised the fallback to docker
stats only. `shellcheck` is not installed on that workstation; the error-level
gate runs in CI.

**Not done:** the collector has never run on the emulated guest, the harness
parts of integration tests 1 and 6 have **not** been re-run, the test battery
is therefore not complete and nothing is measured. No gate is closed and no
claim is admitted; the re-run is the acceptance step and it comes after this
change.

Limitations found by the review of 2026-09-19 and not addressed here (they
live in `src/`, which this change does not reopen; risk R34 in
[`../../docs/g0/risks.md`](../../docs/g0/risks.md) carries them):

- the period is the interval **plus** the cost of a sample, with no
  compensation and no upper bound — a per-sample cost above 4 s would put every
  consecutive pair beyond `MAX_SAMPLE_GAP_S = 5.0` and invalidate the run
  again, from a different cause; the cost has never been measured on the guest;
- `--source auto` decides once, before the warm-up, so a collector started
  while the containers are still coming up selects docker stats for the whole
  run and says so only on stderr;
- a container name that fails to resolve once is cached, including the
  12-character-id fallback, so one failed resolution can split a container into
  two series and fail the per-container ingest rules;
- an unreadable `memory.stat` or a missing `MemTotal` substitutes zero instead
  of skipping the row, which passes the ingest gate as a measurement;
- nothing stops two collectors appending to the same CSV;
- `--source docker` is not byte-for-byte the previous loop: it sleeps the full
  interval after a call that already costs seconds, where the old loop slept
  only when the call had cost nothing.

### 3. `scripts/measure-cold-start.sh` — cold-start sample (claim C04)

One invocation performs one cold start (`down -v`, `up -d`, poll
`GET /ready` until the first 200) and writes an operator `timings.json` the
harness ingests as an external run:

```sh
sh scripts/measure-cold-start.sh cold_start-r01 timings-cold_start-r01.json
# then, on the harness host:
python -m egw_experiments run --run-id cold_start-r01 \
    --external-timings timings-cold_start-r01.json
```

On timeout or compose failure it writes nothing — measurements are never
fabricated.

### Controller /metrics sampling through an SSH tunnel

Port `8000` is loopback-only on this VM (see Security notes), so the
harness samples `GET /metrics` (1 Hz, `queue_depth` for the queue-growth
saturation criterion, CONTRACTS v1.1) through an SSH tunnel opened from the
harness host:

```sh
ssh -N -L 8000:127.0.0.1:8000 <vm> &
python -m egw_experiments run --run-id <run_id> ... \
    --controller-url http://127.0.0.1:8000
```

### Fetching the controller event log automatically

The controller writes `data/events/` per run on this VM. Give the harness a
fetch template so collection is automatic after the confirmation window
(retried 3 times with backoff; recovery via `python -m egw_experiments
collect`):

```sh
python -m egw_experiments run --run-id <run_id> ... \
    --fetch-events-cmd 'scp vm:/opt/egw/src/deployment/data/events/{run_id}/events.jsonl {dest}'
```
