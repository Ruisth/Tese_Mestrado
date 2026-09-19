# Session drivers — guest sessions and bounded checks, exported as they run

These bash drivers run the bounded checks of the project-management work order
of 2026-09-19 (section 2.C) on the integrated QEMU/TCG gateway, and export every
attempt, at completion and on failure, to the local `output_test` folder
([`docs/setup/local_test_outputs.md`](../../docs/setup/local_test_outputs.md)).
They run on the WSL2 host, from a **clean clone** at an identified commit: the
clone that holds this folder is the `REPO` whose commit every attempt records.

| Driver | Does | Attempt it exports |
|---|---|---|
| `export_checks.sh` | one passing and one deliberately failing test, to check the export | two host-only attempts |
| `backfill.sh` | the historical capsules copied on 2026-09-19 (a record of that run; workstation paths) | one `HIST_...` package each |
| `guest_session_open.sh` | records the OS, launcher, QEMU, clone and image identities, boots the guest with `guest/`, records its state | `guest session` (open until closed) |
| `preflight.sh` | runbook 5.5 interlock and `up -d`, installs the clone's collector, compares the deployed tree with the clone, health, OOM, storage, clocks, broker secrets, SUT environment with the emulation label, then a 45 s collector run with the six expected services and its companions checked | `live preflight` |
| `slice.sh RUN SEED` | runbook 6.2-6.4: one smartwatch at 1 Hz for 60 s, isolated run id and unused seed, identity reconciliation, twin read-back, `check` and `delta` | `smartwatch slice 1 Hz 60 s` |
| `nominal.sh RUN_ID` | the pilot plan's nominal entry (120 s warm-up, 600 s measured) through `harness_run`, then the drain, the post-drain and warm-up event logs, snapshots and an identity accounting (`nominal_account.py`) | `nominal instrumentation 120+600` |
| `guest_session_close.sh` | stops the stack **before** power-off (runbook 3.3), keeps the journal and final state, powers off, checks the G1 artefacts | closes and exports `guest session` |

Each attempt reports instrumentation validity and system outcome separately: a
valid run in which messages were late or lost is a system failure, not invalid
evidence. `regen_helpers.py` regenerates `~/egw-tcg/itest-helpers.sh` from the
runbook's section 6.1 heredoc, keeping the previous file beside it.

## Before a session

- **Keep WSL alive.** The WSL distro stops when no `wsl.exe` client is
  attached, and a detached QEMU dies with it. Hold one client open for the
  whole session, for example
  `wsl -d Ubuntu-24.04 --exec bash -lc 'while [ ! -e ~/egw-exec/stop-keepalive ]; do sleep 20; done'`,
  and keep Windows from sleeping.
- **Login shell.** `kas` is only on `PATH` in a login shell: run the drivers with
  `wsl -d Ubuntu-24.04 --exec bash -lc 'bash <driver>'`.
- **No competing load during a measured window**: no test suite, build or bulk
  copy while `nominal.sh` or `slice.sh` runs.
- **Fresh identities.** The guest's event log is appended per run id: use a plan
  entry never used on the guest for `nominal.sh`, and an unused run id and
  seed for `slice.sh` (a seed never used on the MongoDB volume gives a fresh
  twin).

## Paths (environment overrides)

| Variable | Default | Meaning |
|---|---|---|
| `EGW_EXEC` | `/home/ruisth/egw-exec` | execution area (virtual environment, attempts) |
| `EGW_EXEC_REPO` | the clone holding this folder | clean clone the attempts run from |
| `EGW_EXEC_VENV` | `$EGW_EXEC/venv` | virtual environment with the clone installed editable |
| `EGW_ATTEMPTS` | `$EGW_EXEC/attempts` | live capture of each attempt (WSL filesystem) |
| `EGW_OUTPUT_TEST` | `/mnt/c/Users/ruimf/Documents/Projeto Mestrado/output_test` | the Windows folder |
| `EGW_SECRETS_ENV` | `~/egw-tcg/.env` | env file whose secret values are never exported |
| `EGW_YOCTO_CHECKOUT` | `/home/ruisth/yocto/egw` | checkout holding `src/yocto/build-integrated` (the OS image) |
| `EGW_DATA_DISK` | `/home/ruisth/yocto/egw-integrated/egw-data.img` | the guest's data disk |
| `EGW_IMAGES_DIR` | `/home/ruisth/egw-images` | controller image archive and identity record |
| `EGW_GUEST_KNOWN_HOSTS`, `EGW_G1_REFERENCE` | the 2026-09-18 capsules | the guest's pinned host key; the G1 artefact checksums |

The OS image is not rebuilt by any driver: the launcher runs from
`EGW_YOCTO_CHECKOUT`, whose build directory holds the identified kernel and
rootfs, and the attempt records how that checkout, the clean clone and the
deployed tree differ. The rootfs `.ext4` is booted in place and changes with
every boot; its immutable identity is the build's `.tar.bz2`.
