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

### 2. `scripts/collect-resources.sh` — container resources, one sample per second

> **Updated 2026-09-19.** The sentence this section used to open with — that the
> collector "samples `docker stats` once per second" and should be stopped
> "after the 60 s confirmation window" — no longer describes the script, and its
> CSV schema omitted the `host` column the harness has required since work order
> P1. What follows describes the collector as it now stands (LOG `#C034`).

Appends one row per container per sample to a CSV the analysis reads directly
(`ts_utc,container,cpu_pct,mem_bytes,mem_pct,host`), until SIGTERM,
`--duration` or `--max-samples`:

```sh
# on the VM (or through the harness hooks: see the script header):
sh scripts/collect-resources.sh /tmp/resources-<run_id>.csv --duration 900 \
    --expect-services egw-mosquitto-1,egw-mongodb-1,egw-ditto-policies-1,egw-ditto-things-1,egw-ditto-gateway-1,egw-controller-1
```

**Source.** By default it reads the kernel's cgroup v2 accounting under
`/sys/fs/cgroup` directly — no Docker CLI, no daemon round trip. On the emulated
guest one `docker stats --no-stream` call cost 3-5 s idle and about 21 s under
load (2026-09-18) and 3-4 s idle (2026-09-19), which is why the previous
collector could not reach the harness's 30 distinct instants. `--source docker`
keeps that old path for a host whose cgroup tree is not visible, under the same
stamp rules below: a sample is stamped with the second its call starts in, so a
slow call shows up as forward UTC-gap seconds, and the names it reports count in
the inventory. `auto` (the default) re-checks the source on every sample
and records every change.

**Columns.** `cpu_pct` is docker's single-CPU basis (100 × CPU time / elapsed
time, over 100 for a multi-threaded container) — CPU time the *guest* accounts
to the container, not the host QEMU process and not native performance; the
elapsed time is the `/proc/uptime` reading kept exactly as read, so it does not
lose precision however long the guest has been up. `mem_bytes` is
`memory.current` minus `inactive_file` when that is smaller, otherwise
`memory.current` — docker's cgroup v2 "used"; it is not total cgroup usage and
does not by itself give an OOM margin. `mem_pct` divides by `memory.max`; only an
explicit `max` means unlimited and uses the guest's `MemTotal`. An unreadable or
empty `memory.max` — like any unreadable input — writes **no row** and a
diagnostic: a hole is evidence of a failed sample, a zero would be a claim. The
first sample of a container only primes its CPU delta.

**Cadence and timestamps.** Timestamps have whole-second resolution, so the
collector's job is one sample in every wall-clock second. It works with what the
gateway's busybox 1.36.1 offers — no `$EPOCHREALTIME` (that busybox is built
without `CONFIG_ASH_RANDOM_SUPPORT`), but a builtin fractional `sleep` — and
nothing else:

- the timestamp is the second awk reads with `systime()` as it starts the
  sample (checked against `date +%s` at startup), formatted in UTC by arithmetic:
  no `strftime`, whose UTC flag busybox ignores, and no time zone;
- samples are paced on `/proc/uptime` with the fractional sleep, each aimed 0.5 s
  into a second; the offset between the two clocks is calibrated after the first
  sample by watching the clock the stamps come from (`systime()`, or `date +%s`
  when awk has none) cross a boundary, and again when a sample lands in a second
  it did not aim at, or is withheld — at most once every 10 s, since a
  calibration costs up to a second of clock reads. A stepped or slewed wall clock
  never turns this pacing off;
- the last stamped second is kept in the state file: a sample in that second or
  an earlier one (a clock stepped back) is **withheld** with a diagnostic that
  gives its `/proc/uptime` reading, never written. Timestamps never go back and
  are never invented.

**Two counts that never hold the same seconds**, each with a diagnostic line per
event and a total in the closing `stop:` line:

- `utc_gap_seconds` — the forward gaps between consecutive stamped seconds:
  seconds of UTC, beyond one interval, in which no sample was stamped. A wall
  clock stepped forward adds to it although no time passed unsampled.
- `withheld_samples` and `withheld_elapsed_s` — the samples withheld and, for
  each run of them, the elapsed time on `/proc/uptime` from the last accepted
  sample to the one that ends the run, less one interval and less the UTC-gap
  seconds that same sample adds. After a backward step of D seconds the stamps
  resume at the next second, so the UTC count sees no gap; the elapsed time
  without rows, about D seconds, shows only here. A run whose elapsed time
  cannot be measured is counted in `withheld_runs_unmeasured`, and the samples of
  a run still open when the collector stops in `withheld_open_at_stop`, with a
  line giving its elapsed time so far.

Continuous UTC stamps are therefore not proof of continuous elapsed-time
coverage, and neither count, nor their sum, is a measured coverage: a forward
step inflates the first, and a stamped sample can still write no row for a
container (the priming sample, an unreadable input, a counter reset), which is
diagnosed on its own and is in neither count. A step of a fraction of a second
usually costs one second or one withheld sample; a step of D whole seconds costs
about D, in one count or the other.

Without a fractional sleep it paces on whole seconds and says so; withholding
and counting still apply.

**Files beside the CSV**, all kept after the collector exits:

| File | Holds |
|---|---|
| `<csv>.diagnostics.log` | Every diagnostic, one timestamped line each: the collector's own `sha256` and host at start, the pacing mode and each calibration, source changes, withheld samples with their uptime and the elapsed time each run of them cost, forward UTC gaps, unreadable inputs, a sampler process that failed, the service inventory (`inventory: observed=… expected=… missing=… unnamed_ids=…`, every name observed — in the lifecycle file, or in the CSV for the docker source — whether or not `--expect-services` was given) and a closing summary with both counts |
| `<csv>.lifecycle.csv` | `ts_utc,event,container_id,name`: each container cgroup appearing, disappearing, resetting its CPU counter (a recreated cgroup) and first resolving to a name — the id-to-service mapping and the record of a restart |
| `<csv>.self-test` | Only in a `--self-test` run, naming every substituted input |

Fetch the two companion files with the CSV (`scp 'vm:/tmp/resources-<run_id>.csv*' .`):
they explain every gap the CSV has. The harness's fetch hook in the runbook still
fetches the CSV alone, and its start hook does not yet pass `--expect-services`;
both belong to the acceptance update, not to this script. Only a short excerpt of
the diagnostics reaches stderr.

**Timing against the harness.** `egw_experiments run` starts the collector just
before any warm-up and stops it just after the measured run, **before** the 60 s
confirmation window (`run.py`). The 30-instant rule is counted over the whole
file. A condition with no warm-up — the 30 s `smoke_sequence` — therefore gives
the collector almost no lead and no margin; the runbook's remedy for the
instrumentation acceptance is a `nominal` entry, whose 120 s warm-up gives it the
lead it needs. That is a protocol question, handled by the acceptance update.

**Safety.** One collector per output file (a `mkdir` lock, `<csv>.lock`, naming
the holder's pid); the state is written to a temporary file and moved into
place; a state line that is not numeric is ignored rather than believed; an
unresolved container name is shown as the 12-character id and never cached as if
it were the name; the Docker CLI is called only for a container whose own
`config.v2.json` cannot be read, and a `docker ps` listing counts as naming only
the ids it lists — one it omits is asked for again at the next listing, at most
every 10 s. `--cgroup-root`, `--docker-root`,
`--uptime-from`, `--meminfo-from`, `--stamp-epoch` and `--format-epoch` are
refused without `--self-test`, so a plain invocation can never read substituted
inputs or a substituted clock.

**What has and has not been shown** (2026-09-19), by exact version — two
earlier versions of this script ran on the emulated guest, and neither is the
one described above:

| Version (sha256) | Where it ran | What it showed |
|---|---|---|
| `f17bdd8c…` — an intermediate version, never committed; it slept a whole interval after each sample | Guest, idle and under the harness (00:03-00:24 UTC) | Idle: 40 samples, 39 distinct instants, a CSV that passed `validate_resources_csv` at its production thresholds. Under the harness: a median of 1.0 s between samples but 0.84 distinct instants per second over 600 s (a second skipped about every five, from the interval-plus-cost period); neither run was ingested — `smoke_sequence-r02` held 25 instants where 30 are required, `controller_restart-r02` had a 6 s gap on the deliberately restarted controller |
| `b7aeddba…` — commit `aa7440d`; it paced on whole seconds of `/proc/uptime` | Guest, idle only (00:26 UTC) | 30 samples in 29 s gave 26 distinct instants: two samples sharing a second |
| This version | Not on the guest. Under `src/tests/test_collect_resources.py`: 234 cases under sh, dash, bash **and the gateway image's own busybox 1.36.1** (all but eight host-shell-only cases) (its `sh` and `awk`, sha256 `ebb5f78d…`, run under the build's `qemu-aarch64` user emulator with [`tools/test/make-busybox-wrappers.sh`](../../tools/test/make-busybox-wrappers.sh)) | Exact arithmetic; the long-uptime precision; the `memory.max` rule; forward UTC gaps and withheld samples, from either source, including a clock stepped back and then recovered; the diagnostics, lifecycle and inventory, including docker-sourced names and a partial `docker ps` listing; real-time pacing that never stamps a second twice and records every forward UTC gap, under that busybox too; and a 33-sample run that passes `validate_resources_csv` with its production thresholds and a measured window, under dash and under that busybox. **It has not yet run on the guest**, whose kernel supplies the real cgroup files; under the busybox emulation the kernel, `/proc` and the cgroup trees are the build host's. The test output and a long run are kept in a local evidence capsule on the build host (`/home/ruisth/yocto/evidence-candidates/2026-09-19-collector-pr37/`), outside the published evidence and not admitted |

No run of this version has been ingested: no official campaign has been
completed or admitted, and nothing in this section is a campaign result or
native performance evidence.

The harness's own `--local-resources` sampler measures the load-generator
host and is dev-only (audit 9.1).

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
