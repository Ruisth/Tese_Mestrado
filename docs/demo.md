# Demonstration guide

This guide runs the gateway live and follows each message from a simulated wearable to its digital twin:
simulator → Mosquitto (MQTT) → controller → Ditto, with MongoDB as Ditto's storage
([architecture.md](architecture.md)). The short version is in the [main README](../README.md); this page
adds the preparation, every option and default, the expected output and where files are written.

> The gateway runs on an ARM64 computer emulated by QEMU on an x86-64 PC. A demonstration measures
> nothing: the observers show observations, not results. The message rates below are demonstration
> settings, not requirements and not the load used in the comparison. Results: [results.md](results.md).
> Repeating a measurement: [reproduce.md](reproduce.md).

## 1. One-time preparation

Done once per PC; none of it is stored in the repository. The variable in brackets tells the scripts where
each item is. Settings and defaults: [tools/compare](../tools/compare/README.md) and
[tools/demo](../tools/demo/README.md). Runbook: [setup/qemu_integrated_gateway.md](setup/qemu_integrated_gateway.md).

1. **WSL2 with Ubuntu 24.04** and the host packages listed in `tools/compare/README.md` (Yocto build host:
   [setup/wsl2_ubuntu_yocto.md](setup/wsl2_ubuntu_yocto.md)).
2. **The Yocto gateway image** (`egw-gateway-image`, Yocto Project 5.0 Scarthgap): kernel `Image` and
   root file system (`EGW_YOCTO_DEPLOY`), and QEMU 8.2.7 from the same build (`EGW_COMPARE_QEMU`).
   See [reproduce.md](reproduce.md) and runbook §2.
3. **The SSH key** of the gateway user, whose public half is built into the image (`EGW_COMPARE_SSH_KEY`;
   runbook §1.5).
4. **The controller's container image**: an archive and its identity record, built with Docker Desktop for
   `linux/arm64` (`EGW_IMAGES_DIR`; runbook §4.1–4.3).
5. **The passwords file**, a `.env` made from [src/deployment/.env.example](../src/deployment/.env.example)
   (`EGW_COMPARE_SECRETS_ENV`). It never enters the repository.
6. **A Python virtual environment** with the project installed from `src/`, in which
   `import egw_simulator` works (`EGW_EXEC_VENV`).
7. **Terraform 1.16.6** in `$EGW_COMPARE_ROOT/bin`, then `bash tools/compare/tf.sh yocto init` (it also
   runs by itself the first time). The provider lock file is already in the repository.
8. **Debian 13 only:** a one-off download of the pinned Debian 13 cloud image and its first boot (about
   4 minutes): `EGW_COMPARE_ALLOW_DOWNLOAD=1 bash tools/compare/compare_env.sh prepare debian13`.
9. **`yoctowrynose` only:** its image package (`EGW_WRYNOSE_PACKAGE`) and its own SSH key
   (`EGW_WRYNOSE_SSH_KEY`), both kept locally.

## 2. Before each session

- Open WSL **login** shells (`bash -l`), so that the `EGW_*` settings of your profile apply, and go to the
  root of the repository clone. Keep the clone on the WSL file system, not under `/mnt/c`.
- Run **one gateway at a time**. The start command refuses a second one.
- Choose a scenario. In the commands below, `<s>` stands for it.

| Scenario `<s>` | What it starts | Use |
|---|---|---|
| `yocto` | The project's Yocto image (`egw-gateway-image`, Scarthgap) | Measured in the comparison |
| `debian13` | Debian 13 (genericcloud arm64), set up once for the same services | Measured in the comparison |
| `yoctowrynose` | A Yocto 6.0.3 (Wrynose) image started through UEFI (the demonstration scripts also accept `yoctoWrynose`) | **Extra scenario, not measured.** Demonstration and functional use only. Its start includes firmware and an initramfs, so its times cannot be compared with the other two. |

## 3. Step by step

The terminal numbers are those of the main README. Each observer (terminals 2, 3, 4 and 6) first checks
that the gateway is running, then runs until Ctrl+C, which ends only that observer.

### Terminal 1: start the gateway

```bash
bash tools/compare/tf.sh yocto apply     # or debian13, or yoctowrynose (extra scenario, not measured)
bash tools/compare/tf.sh yocto status    # the live state as JSON, e.g. "running": "true", "lock_holder": "yocto"
```

`apply` prepares the work disks if needed and starts the emulated computer. It waits for SSH (checked
every 5 s, for up to 450 s), sets up the six services if needed, starts them, and checks that they are
healthy and that the controller answers `/ready`. Terraform then ends and the gateway **keeps running**.
A second `apply` on a running gateway changes nothing. The last lines (Terraform may prefix them with the
resource name):

```text
STARTED yocto: pid <pid> console <path>
UP yocto: guest accessible by ssh after <n> s (probe step 5 s)
PROVISION yocto: result=ok log=<path>/logs/provision-<stamp>.log
ENVIRONMENT READY: yocto - stack healthy, controller ready; it stays running. Close with: bash tools/compare/tf.sh yocto stop
```

On the PC used for this work this took about 6 to 7 minutes (about 9 for the first `yoctowrynose` start).
The first start of a scenario also copies the base images and downloads the five pinned container images.

**If the start is refused** (exit 2), a `STOP:` line gives the reason: another `qemu-system-aarch64` is
running, the ports are already in use, or another scenario holds the lock. Power that gateway off first
(see *Finish*), then run `apply` again; it first runs a controlled stop, which does nothing if no gateway
is running. A failed `apply` leaves the gateway running for inspection; close it with `stop`.

### Terminal 2: the MQTT messages

```bash
bash tools/demo/observe/mqtt.sh yocto
```

It runs `mosquitto_sub -v` on `c2dt/#` inside the broker container, as the controller's read-only client.
One line per message, `topic payload`. This is what the broker received; it does not yet prove that the
twin changed. On Ctrl+C it also ends that subscriber inside the container, found by its own client id.

```text
c2dt/egw-01/<device-uuid>/telemetry {<JSON: schema_version, run_id, message_id, seq, ts, egw_id, device_uuid, device_type, measurements>}
```

### Terminal 3: the twins in Ditto

```bash
bash tools/demo/observe/ditto.sh yocto          # a query every 5 s (the default)
bash tools/demo/observe/ditto.sh yocto 5 once   # a single query
```

It takes the devices of the current simulation and reads each twin through Ditto's HTTP API inside the
gateway (`GET /api/2/things/org.c2dta:<uuid>`). Each query prints, per twin:

```text
HH:MM:SS  smartwatch      org.c2dta:<uuid>  seq <n>  accepted <n>  last_ts <ts>  UPDATED BY THIS RUN
           values: vitals {"heart_rate_bpm": ...} location {"lat": ..., "lon": ...}
```

Before any simulation it prints `waiting for a demonstration run`. A twin just created shows
`CREATED, waiting for its first update`. Only a simulation run against the same scenario is shown. This is
a repeated query of the twin state, not a stream of events.

### Terminal 4: CPU, memory and disk

```bash
bash tools/demo/observe/resources.sh yocto 10   # every 10 s (the default)
```

Every interval it prints three blocks: `-- GUEST (whole VM)` (`free -m` and the load averages),
`-- CONTAINERS` (`docker stats --no-stream`: CPU % and memory per container) and `-- DISK` (space used on
`/` and on `/var/lib/docker`). Under emulation, `docker stats` takes a few seconds.

### Terminal 5: the simulated wearables

```bash
bash tools/demo/wearables/simulate.sh yocto 1                # one smartwatch
bash tools/demo/wearables/simulate.sh yocto 3                # smartwatch + smart ring + smart clothing
bash tools/demo/wearables/simulate.sh yocto 3 120 --dry-run  # show the settings and the command; send nothing
```

| Setting | Default |
|---|---|
| Arguments | `<s> <1\|3> [duration_s] [rate_msg_s] [--dry-run]` |
| Duration | 60 s; the simulator then stops by itself |
| Rate, one wearable | 1.0 msg/s |
| Rate, three wearables | 2.24 msg/s in total, split 1 : 0.2 : 10: smartwatch 0.2, smart ring 0.04, smart clothing 2.0 msg/s |
| Connection | broker `127.0.0.1:8883`, TLS, QoS 1, user `egw-simulator` |
| Simulator | `python -m egw_simulator run`, scenario `smoke`, seed = the current time |

Before sending, the script checks the Python environment, the passwords file, the broker certificate, the
controller's `/ready` (200) and that no other simulation is running. The broker password reaches the
simulator only through the environment; it is never printed.

```text
== demonstration run (not an experiment)
run id     : demo-<UTC>-w3
devices    : smartwatch,smart_ring,smart_clothing  (3 wearable(s); one simulated device per profile)
published  smartwatch      seq 0     device <uuid>  message <uuid>
== simulator ended (exit 0); run demo-<UTC>-w3; sent <n> message(s) - see the observers ...
```

### Terminal 6 (optional): service logs

```bash
bash tools/demo/observe/logs.sh yocto controller   # or ditto, mongodb, mosquitto
```

It follows `docker logs -f --tail 20` of one service; `ditto` follows its three services. Each line starts
with the container name, for example `[egw-controller-1]`. The broker's own health check (every 30 s) is
hidden on the PC side; the log inside the gateway is unchanged. MongoDB has no port outside the gateway:
its log and its row in terminal 4 show that Ditto's storage is running. A log line does not prove that a
twin changed; terminal 3 does.

### Finish

```bash
bash tools/demo/wearables/stop.sh          # only if a simulation is still running
bash tools/compare/tf.sh yocto stop        # controlled power-off
bash tools/compare/tf.sh yocto status      # "running": "false"
pgrep -af '^(\S*/)?qemu-system-aarch64( |$)' || echo "no QEMU process left"
```

- `stop.sh` signals only the recorded simulator (SIGINT, then SIGTERM after 10 s; never SIGKILL). It
  prints `simulation stopped (run demo-...); the guest keeps running`, or `no demonstration simulation recorded`.
- `tf.sh <s> stop` stops the services (`docker compose stop -t 60`), powers the gateway off over SSH and
  waits up to 180 s for QEMU to end: `STOPPED yocto: pid <pid> ended (ssh-poweroff)`. Disks, settings
  and logs are kept, so the twins of earlier simulations are still there at the next start.
- If the stop fails, it exits 5 with `STOP: QEMU pid <pid> ... was NOT killed`. **Never kill QEMU.** Read
  `$EGW_COMPARE_ROOT/scenarios/<s>/logs/stop-*.log` and the console log, then decide.
- `tf.sh <s> destroy` is not part of normal use: it deletes the work disks, so the next `apply` sets
  everything up again.

A one-message check without the observers is `tools/compare/functional_check.sh`, described in
[tools/compare/README.md](../tools/compare/README.md).

## 4. Optional menu

```bash
bash tools/demo/demo.sh
```

| Option | Action |
|---|---|
| 1, 2, 9 | Start `yocto`, `debian13` or `yoctowrynose` (extra scenario, not measured) |
| 3 | Gateway state, and whether the controller answers `/ready` |
| 4, 5 | Simulate 1 or 3 wearables for 60 s |
| 6 | One query of the twins |
| 7 | Stop the simulation |
| 8 | After a `[y/N]` question: stop the simulation, power off, then check that no QEMU process is left |
| 0 | Leave; the gateway keeps running |

Each option prints the command it runs. Options 3 to 6 and 8 use the scenario of the running gateway, or
ask for one. The menu opens no terminals; start the observers yourself.

## 5. Where files are written

| Folder | Holds |
|---|---|
| `$EGW_COMPARE_ROOT/scenarios/<s>/` (default `~/egw-compare`) | Disks, state, logs (`up-`, `provision-`, `stop-`, `console-<stamp>.log`) and results |
| `$DEMO_STATE_ROOT` (default `~/.local/state/egw-demo`) | The current simulation (`state/`) and the simulator's output (`runs/<run>/sent_events.jsonl`) |

Nothing is committed. Inside the clone, only Terraform's working folder
`tools/compare/terraform/.terraform/` is written, and Git ignores it. Demonstration output is not
evidence.
