# Demonstration commands (`tools/demo/`)

Small wrappers for the live demonstration of the gateway: simulate one or three
wearables, watch the MQTT telemetry, query the twins in Ditto, and watch CPU,
memory, disk and logs. The guide that uses them, with the expected output, is
[`docs/demo.md`](../../docs/demo.md).

The environment itself is started, queried and stopped with
[`tools/compare/tf.sh`](../compare/README.md). These scripts do not start,
provision, measure or power off anything. They only talk to a guest that is
already running.

Everything runs on the x86-64 host (WSL2 Ubuntu 24.04), against the ARM64
guest emulated by QEMU/TCG. What these scripts show are observations of a
demonstration, not measurements.

## Origin

These are the existing wrappers of the demonstration recorded in `LOG.md`
entry #C061 (2026-10-20), in their latest local version. Until now they were
kept outside the repository, on the WSL host. The observers, `simulate.sh` and
`stop.sh` keep their logic; the changes are:

- the menu calls `tools/compare/tf.sh` directly (options 1, 2, 9, 8), and
  option 3 shows `tf.sh status` and `/ready`, in place of the three
  `terraform/` wrappers;
- every path is a setting with a default (table below), and the state and
  runs folders default to a place outside the repository;
- messages point at `tools/compare/tf.sh` and at this folder;
- the menu is translated into English, and each option prints the command it
  runs;
- `simulate.sh` refuses a state or runs folder inside the repository.

## Files

| File | Role | Terminal in `docs/demo.md` |
|---|---|---|
| [`lib.sh`](lib.sh) | Shared settings and helpers. Sourced, never run. | — |
| [`wearables/simulate.sh`](wearables/simulate.sh) | Bounded demonstration run of the existing simulator (`python -m egw_simulator run`): one smartwatch, or the three profiles. `--dry-run` prints the parameters and publishes nothing. | 2 |
| [`wearables/stop.sh`](wearables/stop.sh) | Stops only the recorded simulator process (SIGINT, then SIGTERM after 10 s; never SIGKILL). | any |
| [`observe/mqtt.sh`](observe/mqtt.sh) | `mosquitto_sub` inside the broker container: the publications as the broker receives them. | 3 |
| [`observe/ditto.sh`](observe/ditto.sh) | Polls the twins of the current demonstration run through the Ditto HTTP API inside the guest. | 4 |
| [`observe/resources.sh`](observe/resources.sh) | `free -m`, load, `docker stats --no-stream` and `df` of the guest, every N seconds. | 5 |
| [`observe/logs.sh`](observe/logs.sh) | Follows the log of the controller, Ditto, MongoDB or Mosquitto. | 6 |
| [`demo.sh`](demo.sh) | Optional numbered menu over the same commands and `tf.sh`. | 1 |
| [`tests/offline_check.sh`](tests/offline_check.sh) | Offline checks; starts nothing. | — |

Usage: `bash tools/demo/<file> <yocto|debian13|yoctoWrynose> ...`. The
argument formats are in each script's header, and the scripts that take a
scenario print their usage when it is missing. The scripts can be run from
any directory. Their messages show commands relative to the repository root.

## Settings

The wrappers read the same variables as `tools/compare`, so one shell profile
serves both.

| Variable | Default | Used for |
|---|---|---|
| `DEMO_REPO` | the repository root, found from the script's own location | locating `tools/compare` |
| `DEMO_TOOLS` | `$DEMO_REPO/tools/compare` | `compare_env.sh status` (whether the guest runs) and `tf.sh` (menu) |
| `EGW_COMPARE_ROOT` | `$HOME/egw-compare` | the scenario state: `known_hosts`, the broker's `ca.crt`, logs |
| `DEMO_VENV` | `$EGW_EXEC_VENV`, else `${EGW_EXEC:-$HOME/egw-exec}/venv` | the Python that has `egw_simulator` installed |
| `DEMO_SECRETS` | `$EGW_COMPARE_SECRETS_ENV`, else `$HOME/egw-tcg/.env` | the deployment `.env` on the host (template: [`src/deployment/.env.example`](../../src/deployment/.env.example)) |
| `DEMO_STATE_ROOT` | `${XDG_STATE_HOME:-$HOME/.local/state}/egw-demo` | parent of the two folders below |
| `DEMO_STATE` | `$DEMO_STATE_ROOT/state` | `current_run`, `current_scenario`, `sim.pid` |
| `DEMO_RUNS` | `$DEMO_STATE_ROOT/runs` | the simulator's output of each demonstration run |
| `EGW_COMPARE_SSH_KEY` | `$HOME/.ssh/egw_campaign` | ssh key for `yocto` and `debian13` |
| `EGW_WRYNOSE_SSH_KEY` | `$HOME/.ssh/egw_wrynose_share` | ssh key for `yoctowrynose` (its image accepts only its own key) |

Host tools: `bash`, `ssh`, `python3`, `tail`, and `pgrep` (menu option 8 only).
The guest's SSH port is fixed at host `127.0.0.1:2222`, as in `tools/compare`.

## Secrets

- `wearables/simulate.sh` is the only script that reads the host secrets file.
  It sources the file in a subshell, checks that `MOSQUITTO_SIMULATOR_PASSWORD`
  is set, and hands it to the simulator as `EGW_MQTT_PASSWORD` in that
  subshell's environment. The value never appears on a command line and is
  never printed. This is the same pattern as `tools/compare/functional_check.sh`.
- `observe/mqtt.sh` reads the controller's broker password on the guest, from
  the deployment's own `.env`. The value never reaches the host and is never
  printed. While this observer runs, the value can be seen in process arguments
  inside the guest and the broker container (`docker compose exec -e …`,
  `mosquitto_sub -P …`).
- `observe/ditto.sh` sends the header `x-ditto-pre-authenticated:
  pre:egw-controller` from inside the guest. This is Ditto's pre-authenticated
  identity of the controller, not a credential, and it is reachable only on the
  guest's loopback.
- No file in this folder holds a password, a key or a personal path.

## Not brought in

The following wrappers from the same WSL folder were left out:

- `terraform/up.sh` and `terraform/down.sh` add no guard beyond
  `tools/compare/tf.sh`, whose `apply` and `stop` refuse a second guest
  themselves. `terraform/status.sh` printed a readable stack view (guest
  identity, `docker ps`, `/ready`, `/metrics`); it was left out to keep one
  lifecycle entry, and `tf.sh <s> status`, `resources.sh` and `logs.sh` cover
  the demonstration steps.
- `observe/mongo-tunnel.sh` is not needed for the demonstration steps. It would
  expose the guest's MongoDB, which has no authentication, on a host loopback
  port.
- Symbolic links into a local checkout and virtual environment, backup copies,
  and the `runs/` and `state/` folders.

## Checks

```bash
bash tools/demo/tests/offline_check.sh
```

The check runs `bash -n` on every script, and `shellcheck --severity=error`
when it is installed. It tests the `lib.sh` helpers against stubs (scenario
names, path defaults and overrides, ssh and status stubs). It runs
`simulate.sh --dry-run` and `stop.sh` with no live simulation, and it applies
three static rules: no personal paths, secrets read only by `simulate.sh`, and
no forced kill. It boots nothing, connects to nothing and reads no secrets.
It writes only to a temporary directory, which it removes at the end. Unlike
the other files, it is new, written to check the port; it is run by hand. CI
runs only ShellCheck on it, as on every tracked shell script
(`.github/workflows/technical-ci.yml`).
