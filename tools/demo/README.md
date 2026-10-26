# Demonstration scripts (`tools/demo/`)

Small scripts for the live demonstration of the gateway. The guide that uses them, with the expected
output, is [docs/demo.md](../../docs/demo.md).

- They only talk to a gateway that is already running. They do not start, set up, measure or power off
  anything: the gateway is started, checked and powered off with
  [`tools/compare/tf.sh`](../compare/README.md).
- They run in WSL2 (Ubuntu 24.04) against the ARM64 gateway emulated by QEMU. What they show are
  observations of a demonstration, not measurements.
- They can be run from any directory. Their messages show commands relative to the repository root.

## Scripts

`<s>` is the scenario: `yocto`, `debian13` or `yoctowrynose` (any letter case, for example
`yoctoWrynose`). A script that needs it prints its usage when it is missing. Defaults are shown after `=`.

| Script | Usage | What it does |
|---|---|---|
| [`demo.sh`](demo.sh) | `demo.sh` | Optional numbered menu over the scripts below and `tf.sh`. Prints each command it runs. |
| [`wearables/simulate.sh`](wearables/simulate.sh) | `simulate.sh <s> <1\|3> [duration_s=60] [rate_msg_s] [--dry-run]` | Runs the project's simulator (`python -m egw_simulator run`) for one smartwatch, or for smartwatch + smart ring + smart clothing, then stops by itself. Default rate: 1.0 msg/s for one wearable, 2.24 msg/s in total for three. `--dry-run` prints the settings and sends nothing. |
| [`wearables/stop.sh`](wearables/stop.sh) | `stop.sh [quiet]` | Stops only the recorded simulator process: SIGINT, then SIGTERM after 10 s; never SIGKILL. |
| [`observe/mqtt.sh`](observe/mqtt.sh) | `mqtt.sh <s>` | `mosquitto_sub` on `c2dt/#` inside the broker container: the messages as the broker receives them. |
| [`observe/ditto.sh`](observe/ditto.sh) | `ditto.sh <s> [interval_s=5] [once]` | Reads the twins of the current simulation through Ditto's HTTP API inside the gateway. |
| [`observe/resources.sh`](observe/resources.sh) | `resources.sh <s> [interval_s=10]` | `free -m`, load, `docker stats --no-stream` and `df` of the gateway. |
| [`observe/logs.sh`](observe/logs.sh) | `logs.sh <s> <controller\|ditto\|mongodb\|mosquitto>` | Follows one service's log (`docker logs -f --tail 20`); `ditto` covers its three services. |
| [`lib.sh`](lib.sh) | — | Shared settings and helpers. Sourced, never run. |
| [`tests/offline_check.sh`](tests/offline_check.sh) | `offline_check.sh` | Offline checks (see below). Starts nothing. |

## Settings

The scripts read the same variables as `tools/compare`, so one shell profile serves both.

| Variable | Default | Used for |
|---|---|---|
| `DEMO_REPO` | the repository root, found from the script's own location | locating `tools/compare` |
| `DEMO_TOOLS` | `$DEMO_REPO/tools/compare` | `compare_env.sh status` (whether the gateway runs) and `tf.sh` (menu) |
| `EGW_COMPARE_ROOT` | `$HOME/egw-compare` | the scenario state: `known_hosts`, the broker's `ca.crt`, logs |
| `DEMO_VENV` | `$EGW_EXEC_VENV`, else `${EGW_EXEC:-$HOME/egw-exec}/venv` | the Python that has `egw_simulator` installed |
| `DEMO_SECRETS` | `$EGW_COMPARE_SECRETS_ENV`, else `$HOME/egw-tcg/.env` | the passwords file on the PC (template: [`src/deployment/.env.example`](../../src/deployment/.env.example)) |
| `DEMO_STATE_ROOT` | `${XDG_STATE_HOME:-$HOME/.local/state}/egw-demo` | parent of the two folders below |
| `DEMO_STATE` | `$DEMO_STATE_ROOT/state` | `current_run`, `current_scenario`, `sim.pid` |
| `DEMO_RUNS` | `$DEMO_STATE_ROOT/runs` | the simulator's output of each simulation |
| `EGW_COMPARE_SSH_KEY` | `$HOME/.ssh/egw_campaign` | SSH key for `yocto` and `debian13` |
| `EGW_WRYNOSE_SSH_KEY` | `$HOME/.ssh/egw_wrynose_share` | SSH key for `yoctowrynose` (its image accepts only its own key) |

`simulate.sh` refuses a state or runs folder inside the repository. Host tools: `bash`, `ssh`, `python3`,
`tail`, and `pgrep` (menu option 8 only). The gateway's SSH port is fixed at `127.0.0.1:2222`, as in
`tools/compare`.

## Passwords and identities

- `wearables/simulate.sh` is the only script that reads the passwords file. It loads the file in a
  subshell and passes `MOSQUITTO_SIMULATOR_PASSWORD` to the simulator as `EGW_MQTT_PASSWORD`, in that
  subshell's environment. The value never appears on a command line and is never printed (the same
  pattern as `tools/compare/functional_check.sh`).
- `observe/mqtt.sh` reads the controller's broker password inside the gateway, from the deployment's own
  `.env`. The value never reaches the PC and is never printed. While this observer runs, it can be seen in
  process arguments inside the gateway and the broker container (`docker compose exec -e …`,
  `mosquitto_sub -P …`). Docker does not end that subscriber when the observer's connection closes, so on
  exit, Ctrl+C included, the observer ends it (SIGTERM, matched by its client id, unique to each run).
- `observe/ditto.sh` sends the header `x-ditto-pre-authenticated: pre:egw-controller` from inside the
  gateway. This is Ditto's pre-authenticated identity of the controller, not a password, and it is
  reachable only inside the gateway.
- No file in this folder holds a password, a key or a personal path.

## Offline check

```bash
bash tools/demo/tests/offline_check.sh
```

It starts no gateway, opens no connection and reads no passwords. It runs `bash -n` on every script, and
`shellcheck --severity=error` when installed. It tests the `lib.sh` helpers against stubs, runs
`simulate.sh --dry-run` and `stop.sh` with no simulation running, and checks three rules: no personal
paths, the passwords file read only by `simulate.sh`, and no forced kill. It writes only to a temporary
folder, removed at the end. It is run by hand; CI runs ShellCheck on every shell script.
