# G3 battery — operator procedure (draft for the host-preparation package)

Moved out of the decision packet of 2026-10-01 so that the packet stays short. It is the detail behind packet §3, §4
and §7 and goes into `HIST_<date>-g3-battery-host-preparation/` and the operator records; it changes no rule of the
packet.

## Running the runbook lines

- **Extraction** (at preparation): whole fenced blocks of the `80e833f` blob, with the `host$ ` prompt removed (the
  `_host_commands` rule of `src/tests/test_runbook_itest_helpers.py`). The only edits are the packet's §2 ids.
- **One attempt and one exec per step:** `hx "$A" <step> "exec 2>&1; set -v; . '$A/environment/<step>.sh'"`.
  `$A` is expanded by the steps script (double quotes): no driver exports `A`, and `local_export exec` passes only the
  inherited environment, so a single-quoted `$A` would be empty inside `hx`'s `bash -c`.
  - `hx` loads `~/egw-exec/venv`, `.env`, `EGW_CLONE=~/egw-exec/repo`, the helpers and the tunnel in one bash, so
    carriers chain within the step (the runbook's `~/egw-venv` and the default `EGW_CLONE` point at `489bc9e`).
  - stdin is `/dev/null` (an `ssh` without `-n` would swallow the remaining lines); the text is sourced from a file,
    so no run id sits in an argv that T7's `pgrep -f` could match.
  - `set -v`, never `set -x` (the simulator password is on its argv); no `set -e`, `-u` or `pipefail`; `DEVICES`,
    `ACCEPT_UNACCOUNTED`, `EVENTS_EXPECTED`, `DRAIN_*`, `READY_LIMIT_S` unset and printed.
- **Line 15 within a row.** Within one test, the runbook's carriers (`RT`, `T1H`, `F3`/`C3`, `T4`/`REPLAYED`,
  `F6`/`T6`, `T7`) decide which later lines run after a STOP. T9's lines carry none, so T9 is four steps, each started
  only when the step before it printed no `STOP:`.
- **Rows with more than one step.**
  - *T1 harness:* lines 1310–1313, then line 1320's `analyze` as a recorded step, with the plan and `processed/`
    copied before and after. Line 1310 exits 2 on the existing plan, as expected; `--force` is never used. A
    `T1H=stop` halts the battery (no fallback entry).
  - *T7 Ditto:* its file opens with lines 1440–1458 verbatim (definitions only, no action), so it runs in its own
    shell after the MongoDB gate.
  - *T8:* line 1486; a wait of at most 10 min for the first QEMU to exit and ports 2222/8883 to free; the re-launch
    `ex "$A" t8-relaunch bash "$SESSION/scripts/session_open.sh" "$SESSION" s2` (same data disk; `.current_run`
    rewritten, so the close powers off the second boot); lines 1489–1490; line 1491 only if the tunnel is up; line
    1492 only after `REBOOT SHOWN` with no STOP. Nothing is done inside the guest before the stack is ready.
  - *T9:* (a) lines 1501–1502; (b) lines 1503–1516; (c) lines 1517–1519; (d)+(e) lines 1520–1526; each only after the
    one before printed no `STOP:`. Then the exposure checks (`ssh -n -o BatchMode=yes … -p 2222 root@127.0.0.1 true`,
    where only "Permission denied" counts; `ss -ltnp`; the guest's `docker ps` ports).

## The gate inside each attempt

- Before and after the row: the read-only `guest-state` command of `nominal.sh` (container ids, start instants,
  restart counts, `OOMKilled`, memory-cgroup OOM lines).
- After the row: `guest_state_delta.py --expect` the six containers, with `--expect-restarted` for `egw-controller-1`
  (T6), `egw-mongodb-1` (T7a) and `egw-ditto-things-1` (T7b), and no comparison across T8's reboot; `healthy_wait`
  (900 s); no active `egw-events-*` or `egw-resources-*` unit; `tunnel_check`.

## What a stop leaves, and the restorations

Host artefacts are write-once and stay; guest event logs persist; the guest's `/tmp` (collector CSVs, recorder
directory) is lost at power-off, so a row's fetches and cleanups run before any close. Only the runbook's own
restorations are used: `events_capture.sh cleanup <id>` until 0 (three tries at most), `ssh egw-tcg "$DC start
<service>"`, the harness's collector stop command, `tunnel_down && tunnel_up`. QEMU is never killed without Rui's
decision: the data disk is at stake.

**Controlled close.** (1) No row running and no `readyp` poller on the host. (2) No active recorder or collector unit.
(3) The open attempt finished and exported as it stands. (4) The recorded stop with the controller's 130 s allowance
(PM condition 4 of 2026-10-01): `gx "$S" stack-stop-130 "cd /opt/egw/deployment && docker compose --env-file .env
--env-file images.lock.env stop -t 130; rc=\$?; echo \"stop exit=\$rc\"; docker ps -a --format '{{.Names}} {{.Status}}';
exit \$rc"` (the `$DC` of `guest_common.sh` line 12 spelt out, as `guest_session_close.sh` line 48 uses it, with
`-t 130`; both env files are required, since `compose.yaml` interpolates the pinned images from `images.lock.env`); its exit status and the container states
are recorded; a non-zero exit is a halt and hand-back, never a forced power-off. (5) `guest_session_close.sh` on the
boot named in `.current_run`: tunnel down, `compose stop -t 60` (idempotent after step 4), OOM state, power-off, G1
check, no QEMU left, rootfs hashed, session exported. (6) Operator records sealed; keepalive and keep-awake released.

**Environment input (PM condition 2).** After each session's preflight and before its first qualifying row:
`cp ~/egw-tcg/sut_environment.json ~/egw-tcg/sut_environment.json.<sha256 first 12>` (kept, never overwritten), then
`cp <preflight attempt>/environment/sut_environment.json ~/egw-tcg/sut_environment.json`, then its sha256 and the
preflight package name recorded in the session's operator records; the harness rows (T1, T6) then read it through the
runbook's unchanged `--sut-env-from ~/egw-tcg/sut_environment.json`. The copy must carry the `ARM64 EMULATED` and
QEMU/TCG labels the preflight sets (`preflight.sh` lines 255–257); if it does not, halt.

**Purpose (PM condition 1).** The 12 qualifying row attempts are created with `local_export new --purpose official`
and the scenario "G3 qualification <row>"; the session, preflight, health, preparation and operator-record packages
stay `engineering` (their scenarios are hard-coded in the frozen drivers), linked to the battery by run id in the
operator records and the result note; the preparation and operator `HIST` records carry the battery in their names.

**Session clock (PM condition 3).** On the WSL host at the session open, `read -r UP0 _ < /proc/uptime;
UP0=${UP0%.*}` (whole seconds, recorded); before each row, `NOW=$(cut -d. -f1 /proc/uptime); [ $((NOW - UP0)) -lt
10800 ]` or the row is not started (a row already running keeps its ceiling); each `NOW` is recorded. The guest's
reboot in T8 does not touch it.

**Loading the drivers.** The steps script exports `EGW_EXEC_REPO=$HOME/egw-exec/repo` (and `EGW_EXEC` if the default
differs) before it sources `$EGW_EXEC_REPO/tools/session/common.sh` and `guest_common.sh`, because `common.sh` derives
`REPO` from `$0` and would otherwise point at the steps script's own directory (`ex` would fail before recording
anything and `hx` would export the wrong `EGW_CLONE`); it then sets `S=$SESSION`. The three values are recorded at the
start of the operator records.

## Preparation commands (packet §7, step 1)

```bash
R=~/egw-exec/repo; git -C "$R" status --porcelain | wc -l            # 0
git -C "$R" fetch origin refs/remotes/origin/dev                      # FETCH_HEAD = 80e833f…
git -C "$R" checkout --detach 80e833f44f647fe9cd8f5e99d3abf3c444de95aa
git -C "$R" rev-parse HEAD 'HEAD^{tree}'; git -C "$R" status --porcelain | wc -l   # dad725d0…, 0
~/egw-exec/venv/bin/python -c 'import egw_experiments.n1_report, egw_experiments.proved_down, egw_experiments.itest_reconcile'
```

Helpers: `regen_helpers.py docs/setup/qemu_integrated_gateway.md ~/egw-tcg/itest-helpers.sh` (it keeps
`itest-helpers.sh.39403ead5a81`); `proof_helpers_check.py` prints `HELPERS OK`; sha256 `e5eba37e…`, 545 lines, `bash
-n` clean. Freshness on the guest root file system offline: `debugfs -c -R "ls -l /opt/egw/deployment/data/events"`,
only with no `qemu-system-aarch64` and no `current_session`.
