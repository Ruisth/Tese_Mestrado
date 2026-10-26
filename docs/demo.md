# Demonstration guide

This guide runs the gateway live and shows the whole message path:
simulator → MQTT/Mosquitto → controller → Ditto, with MongoDB as Ditto's
storage ([`architecture.md`](architecture.md) §4). Each step is an independent
command in its own terminal. There is also an optional menu.

> The system runs in an ARM64 guest emulated by QEMU/TCG on an x86-64 host. A
> demonstration measures nothing. What the observers print are observations,
> not results. The simulator's rates on this page are demonstration
> parameters, not requirements, and not the load used in the comparison. The
> results are in [`results.md`](results.md).

## Three kinds of work

| Kind | When | Where |
|---|---|---|
| **Initial preparation** | Once per host | [Section 1](#1-initial-preparation-once-per-host) below, which links the detailed runbooks |
| **Normal use** (the demonstration) | Every time | [Sections 2–4](#2-before-each-session) below |
| **Experimental reproduction** | Only to repeat a recorded measurement | [`reproduce.md`](reproduce.md) and [`tools/compare/README.md`](../tools/compare/README.md) §9–10. Not part of this guide. |

Normal use starts no build, takes no measurement and changes no recorded
evidence.

## 1. Initial preparation (once per host)

Everything below stays on the host and is never committed. Each item links to
the place where it is described in full.

1. A WSL2 Ubuntu 24.04 host with the packages of
   [`tools/compare/README.md`](../tools/compare/README.md) §3. For the Yocto
   build host, see [`docs/setup/wsl2_ubuntu_yocto.md`](setup/wsl2_ubuntu_yocto.md).
2. The integrated Yocto build. It provides the deploy directory (kernel
   `Image` and the root file system of `egw-gateway-image`) and QEMU 8.2.7 from
   its `qemu-helper-native` sysroot ([`reproduce.md`](reproduce.md); runbook
   [`qemu_integrated_gateway.md`](setup/qemu_integrated_gateway.md) §2).
3. The operator SSH key pair, whose public half is built into the image
   (runbook §1.5; setting `EGW_COMPARE_SSH_KEY`).
4. The controller image archive and its identity record, built by Docker
   Desktop for `linux/arm64` (runbook §4.1–4.3; setting `EGW_IMAGES_DIR`).
5. The deployment `.env` with the four passwords, created from
   [`src/deployment/.env.example`](../src/deployment/.env.example) (setting
   `EGW_COMPARE_SECRETS_ENV`). It never enters the repository.
6. A Python virtual environment with the project installed from `src/`, in
   which `import egw_simulator` works (setting `EGW_EXEC_VENV`).
7. Terraform 1.16.6 in `$EGW_COMPARE_ROOT/bin`, then
   `bash tools/compare/tf.sh yocto init` (`tools/compare/README.md` §3). The
   provider lock file is already committed.
8. For `debian13`, a one-off download of the dated Debian image and its
   provisioning first boot (about 4 min recorded on 2026-10-18):
   `EGW_COMPARE_ALLOW_DOWNLOAD=1 bash tools/compare/compare_env.sh prepare debian13`
   (`tools/compare/README.md` §4).
9. For `yoctowrynose` only, the image package (setting `EGW_WRYNOSE_PACKAGE`)
   and its own SSH key (setting `EGW_WRYNOSE_SSH_KEY`). The package is kept
   locally and is never committed (`tools/compare/README.md` §11).

The first `apply` of each scenario copies the base images and pulls the five
pinned container images, so it takes longer than later ones. The settings and
their defaults are listed in `tools/compare/README.md` §3 and
[`tools/demo/README.md`](../tools/demo/README.md).

## 2. Before each session

- Open WSL **login** shells (`bash -l`), so that the profile's `EGW_*`
  settings apply, and change to the root of the repository checkout. Use a
  clone on the WSL ext4 file system, never under `/mnt/c`
  ([reproduce.md](reproduce.md) §2.1).
- Run **one guest at a time**. The lifecycle refuses a second guest.
- Choose a scenario:

| Scenario | What it boots | Status |
|---|---|---|
| `yocto` | The project's Yocto image (`egw-gateway-image`, Scarthgap) | Measured in series a02 |
| `debian13` | Debian 13 genericcloud arm64, provisioned once for the same stack | Measured in series a02 |
| `yoctowrynose` | A Yocto 6.0.3 Wrynose image booted through UEFI | **Additional scenario, not measured.** For demonstration and functional use only. Its boot includes firmware and an initramfs, so its times cannot be compared with series a02. |

- One terminal per role:

| Terminal | Role | Command |
|---|---|---|
| 1 | Lifecycle: start, status, power-off | `bash tools/compare/tf.sh <s> apply / status / stop` |
| 2 | Wearable simulator | `bash tools/demo/wearables/simulate.sh <s> 1` or `3` |
| 3 | MQTT telemetry | `bash tools/demo/observe/mqtt.sh <s>` |
| 4 | Twins in Ditto | `bash tools/demo/observe/ditto.sh <s>` |
| 5 | CPU, memory, disk | `bash tools/demo/observe/resources.sh <s>` |
| 6 | Logs (optional) | `bash tools/demo/observe/logs.sh <s> <service>` |

In the commands, `<s>` is `yocto`, `debian13` or `yoctowrynose`. The wrappers
also accept `yoctoWrynose`.

## 3. The six steps

### Step 1. Start one environment (terminal 1)

```bash
bash tools/compare/tf.sh yocto apply      # or: debian13, or yoctowrynose (not measured)
bash tools/compare/tf.sh yocto status     # the live state, at any time
```

`apply` prepares the work disks if they are missing, boots the guest, waits
for SSH and brings the stack up. It then confirms six healthy services and
the controller's `/ready`. The guest **stays running** and Terraform ends.
A second `apply` on a running environment changes nothing.

Expected output, among Terraform's own lines (Terraform may prefix them with
the resource name):

```text
STARTED yocto: pid <pid> console <path>
UP yocto: guest accessible by ssh after <n> s (probe step 5 s)
PROVISION yocto: result=ok log=<path>/logs/provision-<stamp>.log
ENVIRONMENT READY: yocto - stack healthy, controller ready; it stays running. Close with: bash tools/compare/tf.sh yocto stop
```

`status` prints one JSON object of strings, for example
`"running": "true"`, `"lock_holder": "yocto"`, `"last_provision": "ok"`.

How long it takes, as recorded on the emulated guest (for information only):

- `yocto`: `ENVIRONMENT READY` 383 s after launch, on the first provisioning
  of its data disk (2026-10-18);
- `debian13`: 376 s after launch (2026-10-18);
- `yoctowrynose`: about 9 min for the first `apply` and 6–7 min for later
  ones (2026-10-20).

`tools/compare/README.md` §9 and §11 hold these records.

If a guest is already running, the start is refused (exit 2), with one of
these lines:

```text
STOP: another qemu-system-aarch64 is running and is never stopped by this tool: ...
STOP: host port(s) of the profile already have a listener: ...
STOP: the profile's lock is held by scenario '<other>'
UP debian13: start did not succeed (exit 2); nothing more is done
```

Stop the other guest first (step 6), then run `apply` again. After a refused
or failed `apply`, Terraform marks the power resource as tainted. The next
`apply` runs a controlled stop, which does nothing if the guest is not running,
and then starts again (`tools/compare/README.md` §5). A failed `apply` leaves
the guest running so that it can be inspected. Close it with `stop`.

### Step 2. Simulate one or three wearables (terminal 2)

```bash
bash tools/demo/wearables/simulate.sh yocto 1               # one smartwatch, 60 s, 1.0 msg/s
bash tools/demo/wearables/simulate.sh yocto 3               # smartwatch + smart ring + smart clothing, 60 s, 2.24 msg/s in total
bash tools/demo/wearables/simulate.sh yocto 3 120 --dry-run # print the parameters and the command; publish nothing
```

The arguments are `<s> <1|3> [duration_s] [rate_msg_s] [--dry-run]`. The
script runs the project's simulator (`python -m egw_simulator run`, scenario
`smoke`, QoS 1, TLS) against the broker on `127.0.0.1:8883`.

- The aggregate rate is split 1 : 0.2 : 10 between the three profiles. At
  2.24 msg/s, that is 0.2, 0.04 and 2.0 msg/s.
- The run id is `demo-<UTC>-w1` or `demo-<UTC>-w3`, and the seed is the
  current time.
- The output is written to `$DEMO_RUNS` (default
  `~/.local/state/egw-demo/runs`), outside the repository.

Before publishing, the script checks the venv, the secrets file, the broker
CA, that the guest is running, that `/ready` returns 200, and that no other
demonstration run is active. The broker password reaches the simulator only
through the environment of a subshell. It is never printed.

Expected output:

```text
== demonstration run (not an experiment)
scenario   : yocto (broker 127.0.0.1:8883, TLS, QoS 1; CA <path>/ca.crt)
run id     : demo-<UTC>-w3
devices    : smartwatch,smart_ring,smart_clothing  (3 wearable(s); one simulated device per profile)
...
published  smartwatch      seq 0     device <uuid>  message <uuid>
published  smart_clothing  seq 0     device <uuid>  message <uuid>
...
== simulator ended (exit 0); run demo-<UTC>-w3; sent <n> message(s) - see the observers ...
```

On 2026-10-20, 60 of 60 messages with one wearable and 135 of 135 with three
were confirmed in the twins, for each of the three scenarios (`LOG.md`
#C061).

### Step 3. Watch the MQTT telemetry (terminal 3)

```bash
bash tools/demo/observe/mqtt.sh yocto
```

The script runs `mosquitto_sub -v` on `c2dt/#` inside the broker container.
It uses the broker's CA, the controller's read-only identity and its own
client id. Each message is printed as `topic payload`:

```text
c2dt/egw-01/<device-uuid>/telemetry {<JSON envelope: schema_version, run_id, message_id, seq, ts, egw_id, device_uuid, device_type, and the measurements>}
```

This is what the broker received, not a twin update. The password is read on
the guest from the deployment's `.env`, and it is visible in process arguments
inside the guest while the observer runs ([`tools/demo/README.md`](../tools/demo/README.md)).

### Step 4. Query the twins in Ditto (terminal 4)

```bash
bash tools/demo/observe/ditto.sh yocto          # every 5 s
bash tools/demo/observe/ditto.sh yocto 5 once   # a single query
```

The script reads the device UUIDs from the current demonstration run. For
each device it runs `GET /api/2/things/org.c2dta:<uuid>` inside the guest,
through Ditto's HTTP API with the controller's pre-authenticated identity.
Ditto keeps the twins in MongoDB. Each poll prints:

```text
HH:MM:SS  smartwatch      org.c2dta:<uuid>  seq <n>  accepted <n>  last_ts <ts>  UPDATED BY THIS RUN
           values: vitals {"heart_rate_bpm": ...} location {"lat": ..., "lon": ...}
```

Until a run starts it prints `waiting for a demonstration run`. A twin that
was just created shows `CREATED, waiting for its first update`. This is a poll
of the twin state, not an event stream.

**Without the wrappers.** `functional_check.sh` sends one smartwatch event and
reads its twin back through an SSH tunnel:

```bash
bash tools/compare/functional_check.sh yocto "demo-func-$(date -u +%Y%m%dT%H%M%SZ)" "$(date -u +%s)"
```

Use a new run id each time: the same run id and seed repeat the same
`message_id`, which the controller records as a duplicate, so a repeat ends
`result=fail`. Host ports 8000 and 8080 must be free. The last line is
`FUNCTIONAL yocto demo-func-<UTC>: result=pass sent=1 accepted_delta=1 twin_ok=true ...`.
The record is written under `$EGW_COMPARE_ROOT/scenarios/<s>/results/`.

### Step 5. Watch CPU, memory, disk and logs (terminals 5 and 6)

```bash
bash tools/demo/observe/resources.sh yocto 10          # every 10 s
bash tools/demo/observe/logs.sh yocto controller       # or: ditto | mongodb | mosquitto
```

`resources.sh` prints three blocks every interval:

- `-- GUEST (whole VM)`: `free -m` and the load averages;
- `-- CONTAINERS`: `docker stats --no-stream`, giving CPU % and memory per
  container;
- `-- DISK`: space used on `/` and on `/var/lib/docker`.

Under TCG, `docker stats` takes a few seconds.

`logs.sh` follows `docker logs -f --tail 20` of one service. `ditto` covers
its three services. Each line is prefixed with the container name, for example
`[egw-controller-1] ...`. The broker's periodic health-probe lines are hidden
on the host; the guest's log is unchanged. MongoDB has no port outside the
guest. Its log and its row in `docker stats` show that Ditto's storage
service is running. A log line is not proof of a twin update; step 4 is.

### Step 6. Stop the simulator, then power off (any terminal)

```bash
bash tools/demo/wearables/stop.sh                      # only if a simulation is still running
bash tools/compare/tf.sh yocto stop                    # controlled power-off
bash tools/compare/tf.sh yocto status                  # "running": "false"
pgrep -af '^(\S*/)?qemu-system-aarch64( |$)' || echo "no QEMU process left"
```

- `stop.sh` signals only the recorded simulator process (SIGINT, then SIGTERM
  after 10 s) and prints
  `simulation stopped (run demo-...); the guest keeps running`. With no
  simulation running it prints `no demonstration simulation recorded`.
- End each observer with Ctrl+C in its own terminal.
- `tf.sh <s> stop` stops the stack (`docker compose stop -t 60`), powers the
  guest off over SSH and waits up to 180 s for QEMU to end. It prints
  `STOPPED yocto: pid <pid> ended (ssh-poweroff)`. Disks, configuration and
  logs are kept. The twins and controller event logs of earlier
  demonstration runs stay on the guest's work disks.
- If the stop fails, it exits 5 and prints `STOP: QEMU pid <pid> ... was NOT
  killed`. **Never kill QEMU.** Read
  `$EGW_COMPARE_ROOT/scenarios/<s>/logs/stop-*.log` and the console log, then
  decide.
- `tf.sh <s> destroy` is not part of normal use. It removes the work disks,
  so the next `apply` provisions everything again.

## 4. Optional menu

```bash
bash tools/demo/demo.sh
```

The menu is a numbered list over the same commands:

- 1, 2, 9: start `yocto`, `debian13` or `yoctowrynose`;
- 3: status;
- 4, 5: simulate 1 or 3 wearables for 60 s;
- 6: one query of the twins;
- 7: stop the simulation;
- 8: power off, after a `[y/N]` confirmation;
- 0: leave.

Each option prints the command it runs. The menu opens no terminals; start
the observers in their own terminals. Leaving the menu does not power the
environment off. Option 8 runs `stop.sh quiet`, `tf.sh <s> stop` and
`tf.sh <s> status`, then checks that no QEMU process is left.

## 5. Where things are written

- `$EGW_COMPARE_ROOT/scenarios/<s>/` holds disks, state, logs (`up-`,
  `provision-`, `stop-`, `console-<stamp>.log`) and results
  (`tools/compare/README.md` §2).
- `$DEMO_STATE_ROOT` (default `~/.local/state/egw-demo`) holds the current
  demonstration run and the simulator's output.
- Nothing is written into the repository. Demonstration output is not
  evidence.

## 6. Detailed runbooks (linked, not copied)

- [`tools/compare/README.md`](../tools/compare/README.md): commands (§0, §4),
  layout (§2), prerequisites (§3), Terraform behaviour and guards (§5),
  secrets (§7), validation records (§9), `yoctowrynose` (§11).
- [`tools/demo/README.md`](../tools/demo/README.md): the wrappers, their
  settings and their offline check.
- [`docs/setup/qemu_integrated_gateway.md`](setup/qemu_integrated_gateway.md):
  the original manual runbook. It covers the build, boot, image archive,
  deployment steps 5.1–5.8 and SSH tunnels (§5.7); `provision_stack.sh`
  automates 5.1–5.6 and `functional_check.sh` opens the §5.7 tunnels itself.
  Its status notes date from 2026-09-18/19.
- [`architecture.md`](architecture.md): components, ports and the message
  path.
