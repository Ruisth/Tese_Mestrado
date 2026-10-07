# g3_battery.sh — the operator's steps script of the G3 qualifying battery

Authority: Rui's authorisation of 2026-10-02 under the decision packet of 2026-10-01 (revision 2) and the operator
procedure. The candidate is frozen at `80e833f` (tree `dad725d`); the script edits nothing of it and records only
through the frozen `common.sh` / `guest_common.sh` functions and `local_export`. It kills no QEMU, deletes nothing,
repeats no row, retries no step, and never uses `ACCEPT_UNACCOUNTED`, `--force` or `local_export set run_id=…`.

## Launch (one subcommand per `wsl.exe` invocation)

`P` is the WSL path of this folder (`/mnt/c/Users/ruimf/AppData/Local/Temp/claude/…/scratchpad/g3/battery/prep`).

```bash
# short subcommands (status, classify, term), in the foreground:
MSYS_NO_PATHCONV=1 wsl -d Ubuntu-24.04 --exec bash -lc 'EGW_EXEC_REPO=$HOME/egw-exec/repo bash "<P>/g3_battery.sh" status'
# long subcommands (open, row, close), detached from the client that starts them:
MSYS_NO_PATHCONV=1 wsl -d Ubuntu-24.04 --exec bash -lc 'EGW_EXEC_REPO=$HOME/egw-exec/repo setsid bash "<P>/g3_battery.sh" row t1-smokes > /dev/null 2>&1 < /dev/null & sleep 2'
```

- `MSYS_NO_PATHCONV=1` always (Git Bash rewrites `/home/…` otherwise); `bash -lc` (login shell).
- A detached run prints nothing to the caller: its whole console is `<state>/console/NNN-<subcommand>-<arg>.txt`
  (`status` names the latest). Follow it with `tail`, and wait for `status` to show the row
  `awaiting-classification`. A row started as a plain background task also works, but the tool's own time limit
  (2 h at most) would then hang it up before T8's 135 min ceiling.
- One subcommand per invocation: a row's process group must be its own (`term` signals that group).
- **One changing subcommand at a time.** `open`, `row`, `classify` and `close` each take the turn
  (`<state>/turn.env`: the pid, its start instant and the WSL boot of the holder, written under a short `flock`) and
  are refused (`REFUSED: another invocation of this script is still running: …`, exit 2, nothing started or changed)
  while another of them is still running. A launch line issued twice therefore runs the row once, and a `close`
  cannot take the guest away under a running `open`. `status` and `term` take no turn. A turn whose holder ended is
  simply taken; nothing is deleted.
- **Keepalive:** before `open`, start a dedicated client and leave it running until after `close`:
  `MSYS_NO_PATHCONV=1 wsl -d Ubuntu-24.04 --exec bash -lc 'exec sleep 43200'` (a background task). `open` wants
  6 h left on it, each `row` its ceiling plus 30 min and `close` 30 min; the script checks the `sleep` and its WSL
  relay parent. The `~/egw-exec/stop-keepalive` sentinel is not touched. Without a client the distro stops, and
  QEMU with it.
- **Keep-awake:** Windows must not sleep or hibernate for the whole session. It cannot be seen from WSL: it is the
  operator's own check before `open` and before every `row`. No other load on the host (no build, no pytest).
- Never edit the script, the row files or the manifest while a session is open: a `row` refuses a changed script.

## Subcommands

| Subcommand | What it does | Refuses (exit 2) when |
|---|---|---|
| `open S1\|S2` | Checks: clone `80e833f`/`dad725d` clean, `drivers_sha256`, export tool, runbook, helper file (`e5eba37e…`, 545 lines), `tunnel.sh`, `ca.crt`, the guest-state command against `nominal.sh`; the session's row files against `rows.manifest.json`; every id of the session unused on the host; the root file system hash (S1: `c49500a9…`; S2: S1's post-close value); the keepalive. Records `UP0`. Then the frozen drivers `guest_session_open.sh`, `preflight.sh`, the environment copy of PM condition 2, `gate_health.sh`, and one read-only listing of the guest's event directories (ids unused there too). | a session is open; the session's state file exists; a QEMU process runs; the keepalive is missing; for S2, S1 did not end without a halt (unless `EGW_G3_RUI_GO`) |
| `row <slug>` | One attempt (`G3 qualification <slug>`, purpose `official`): identities and a `workload` field, the step files and manifest entries copied to `environment/`, the sources registered, the gate's read before, each step as one `hx` shell that sources its file (`set -v`, carriers unset and printed), the gate after. Leaves the attempt OPEN. | the session is not open; the previous row is not classified; the row was already started; the script or manifest changed; the session has a recorded halt (unless `EGW_G3_RUI_GO`); the keepalive is short |
| `classify <slug> <finished\|failed> <validity> <outcome> <reason> <next-action>` | `local_export finish`, a headline, the export (`driver_code`: prints `DRIVER RESULT`), the row marked classified. Pairs of packet §5 only: `valid/pass`, `valid/fail`, `invalid/unknown`, `valid/inconclusive`, `unknown/inconclusive`, `not-applicable/not-run`. A reason or next action given as `@FILE` is read from that file. | the row does not await classification; the pair is not one of §5 |
| `term <slug>` | TERM, never KILL, to the row's recorded process group, after listing it (command lines cut at 90 columns, the value after every `--password` hidden). The row's trap finishes the attempt `interrupted` and exports it (after letting the group's own traps end, 180 s at most, and one guest-state read). If a QEMU process or the keepalive client is in that group it prints `HALT:` (exit 1, recorded in the session's and the row's state files) and signals nothing. | no process of the row is left; the recorded group is the caller's own |
| `close` | No unit `egw-events-*` / `egw-resources-*` active (read-only); the recorded `compose stop -t 130` with both env files, as step `stack-stop-130` of the session attempt; then the frozen `guest_session_close.sh`. Records the post-close root file system hash and lists the data disk's ext4 header (read-only, only with no QEMU process left). With **no QEMU process left** (the guest was lost, or T8's re-launch failed) there is nothing to read or stop: it records a HALT, skips the unit check and the stop, and runs the frozen close driver, which finishes and exports the session attempt as it stands. | another changing subcommand is running; a row is running or awaits classification; a process is left in a row's group; a row's process died and its attempt is still open (the refusal prints the frozen `local_export recover … --interrupt <run id>` line); the keepalive has less than 30 min left; no session is open (see "A session closed outside the script") |
| `status` | The sessions, elapsed host uptime against the 3 h cutoff, each row's state, gate, class and export, a running row's minutes against its ceiling, every recorded halt. Read-only. | — |

`row` never judges: a step's exit status is the status of its last line. The row's ceilings (minutes: T1 smokes 105,
harness 35, T2 36, T3 37, T4 replay 67, reset 35, T5 38, T6 47, each T7 41, T8 135, T9 25) are recorded and shown by
`status`; the operator enforces them with `term`.

Row specifics. *t1-harness:* the plan and `processed/` are copied into `other/` before the harness, the plan after
it, then the analyze step (only if the harness step printed no `STOP:`), then both again. *t6:* the same copies
before and after its one step. *t6, t7-mongo, t7-ditto:* the gate expects the controller, MongoDB or `ditto-things`
restarted in place (`--expect-restarted`). *t8:* step a; at most 10 min for the first QEMU to exit and ports
2222/8883 to free (never killed); the re-launch `session_open.sh <session> s2`; step b; step c only if
`tunnel_check` passes; step d only if b and c show `REBOOT SHOWN` and no `STOP:`; the previous boot's journal and
OOM lines (evidence); no guest-state comparison. *t9:* a, b, c, d+e and the exposure step, each only if the one
before printed no `STOP:` (so after a STOP of d+e the three read-only exposure reads are not in the package); its
sources are registered after the row (what exists: a refusal leaves no directory).

*t8, step b, a tunnel signature to know.* Runbook line 1490 (`tunnel_down && tunnel_up`) was written for a master
the reboot had killed. Under `hx` the step's preamble has already reopened the tunnel, so line 1490 closes a LIVE
master and reopens it a few milliseconds later. If the old master has not finished exiting, `tunnel_up` can print
`MASTER ANSWERS … nothing was reopened` (status 0, and the tunnel is then down) or `STOP: host port busy`. Neither
is silent: the `t8-tunnel-check` step after step b then halts the row ("step c and step d were NOT run"). Classify
that as a tunnel event of the host (invalid instrumentation), not as an observation of the SUT. First exercised by
the battery; not reproduced on a real ssh master.

## State files (`${EGW_G3_STATE:-~/egw-exec/g3-battery}`; `key=value` lines, never sourced)

- `session-<S1|S2>.env`: label, `state` (opening, open, halted, closed, close-failed), `up0`, the WSL boot id, the
  session and preflight attempts, each driver's exit, the environment copy's hashes, `rootfs_before_boot`,
  `rootfs_after_close`, every `row_clock=` reading and every `halt=` line.
- `row-<slug>.env`: the attempt, `start_up`, `ceiling_min`, `pid`/`pgid` with their start instants, `state`
  (preparing, running, gate, awaiting-classification, classified, interrupted), the current `step`, every
  `step_done=`, the `gate`, the class, the driver code and the export receipt.
- `turn.env` and the empty `turn.lock`: who holds, or last held, the turn of the changing subcommands.
- `row-<slug>.group-after-signal.txt`: the last reading of an interrupted row's process group (passwords hidden).
- `console/NNN-….txt` (one per invocation), `<label>-<driver>.console.txt`, `<label>-environment-copy.txt`,
  copies of the script and manifest as opened. Together with the classification notes these are the operator
  records to seal as `HIST_<date>-g3-battery-operator-records`.

No process listing reaches these files, or the caller's terminal, with a password: the simulator, the replay, the
harness and T9's probes carry it on their argv after `--password`, and every listing (`term`, `status`, `close`,
the reading after a signal) is passed through a mask; all but the reading after a signal are also cut at 90 columns. The frozen export's secret scan reads
attempts only, never the state directory.

## What a `HALT:` line means

A halt condition of packet §4: the script stops there, closes nothing (except at `close` with the guest gone,
below), and records the line in the session's state file once the session is in use. The HALTs of `open`'s checks
before anything was started are printed only: nothing ran, no state file exists, and `open` is run again once the
cause is corrected. No further row starts in that session (and S2 does not open) until Rui directs otherwise; with
his explicit go, the next `row` or `open S2` is run with `EGW_G3_RUI_GO="<his words>"`, which is recorded. After a
HALT: classify the row if it awaits classification, then `close`, then hand back.

- Before anything started (`open`'s checks): an identity, a row file or an id differs — nothing ran.
- `open`: a driver exited non-zero or the environment copy failed — the guest may be UP: `status`, then `close`.
- `row`: step status 97 (preamble or tunnel not loaded) or 74 (console capture lost); the gate did not pass (OOM
  kill, unexpected restart, a service not healthy within 900 s, a unit active, tunnel); T8's QEMU not exited, a
  failed re-launch, or no `REBOOT SHOWN`; `NOT STARTED: the 3 h cutoff`; guest, tunnel or WSL lost; an interrupt.
- `classify`: the export failed, or the class is "not started". Its last line says `Next: 'close', then hand back
  to Rui` whenever the session holds a halt or the row's gate did not pass.
- `term`: a QEMU process or the keepalive client is in the row's process group — nothing was signalled.
- `close`:
  - a unit is active (exit 3): the runbook's cleanup first (below), then `close` again;
  - the guest did not answer (exit 97) although a QEMU process runs: nothing was stopped, and `close` answers the
    same for as long as the guest does not answer — hand back to Rui (QEMU is never killed without his decision);
  - `HALT: stop failed` — the close driver was NOT run and QEMU is never forced off;
  - no QEMU process is left: the HALT is recorded, the unit check and the stop are not run (there is nothing to
    read or stop) and the frozen close driver finishes and exports the session attempt as it stands (expect its
    exit 5); the session is then recorded `closed` with that halt, and S2 opens only on Rui's go;
  - a row's process had died and its attempt was finished outside the script: recorded `interrupted`, with a halt;
  - the close driver ended non-zero.

`REFUSED:` (exit 2) is not a halt: nothing was started or recorded; fix the cause and run the same line again.
One exception: a `close` refused for a short keepalive may already have recorded a dead, recovered row as
`interrupted` with its halt (that check runs first); nothing was stopped.
The script records only the halts it detects. A halt the operator reads from a console (for example invalid
instrumentation of the shared chain) is honoured by not starting the next row and is written in the result note.

### A row whose process died without its trap

Its state file still says `running` (or `preparing`, `gate`), `status` says `its process … is GONE`, and its attempt
is still open in WSL. `close` refuses on it (packet §4: the open attempt is finished and exported BEFORE the stop)
and prints the frozen line, with this host's paths, that marks and exports it:
`(cd ~/egw-exec/repo/src && ~/egw-exec/venv/bin/python -m egw_experiments.local_export recover --attempts-root
~/egw-exec/attempts --dest-root "<output_test>" --secrets-env ~/egw-tcg/.env --interrupt <run id>)`. First fetch what
the row left on the guest (restorations below: the guest's `/tmp` is lost at power-off). Then `close` again: it
finds the attempt finished and exported, records the row `interrupted` with a halt, and goes on.

### A session closed outside the script

If the frozen `guest_session_close.sh` was run by hand (or an `open` halted before any session existed), no session
is open and the state file still says `open` or `halted`: `close` then answers `REFUSED: no open session … recorded
'open'`, and `open S2` refuses on that record. Only on Rui's explicit direction:
`EGW_G3_RUI_GO="<his words>" … g3_battery.sh close` records the session `closed` with a halt (his words recorded),
and only if no `current_session` exists, no QEMU process runs and no row is running or unfinished. The post-close
root file system hash is taken from the session attempt's own record; without it S2 does not open.

### Restorations

Only the runbook's own, run by hand and recorded with the frozen `hx` on the row's attempt while it is open (state
`awaiting-classification`; `status` prints its path), on the session attempt (`cat ~/egw-exec/current_session`)
once the row's attempt is finished. In a WSL login shell:

```bash
export EGW_EXEC_REPO=$HOME/egw-exec/repo
. "$EGW_EXEC_REPO/tools/session/common.sh"; . "$EGW_EXEC_REPO/tools/session/guest_common.sh"
A=<the attempt directory>
# 1. a recorder unit egw-events-<id> left active - until it ends 0, three tries at most (packet §4, halt 3).
#    The second argument makes the cleanup KEEP what the recorder captured (events-partial/); a bare
#    'events_capture.sh cleanup <id>' stops the unit and copies nothing, and the guest's /tmp is lost at power-off.
hx "$A" restore-events-<id> 'events_cleanup <id> "$P/<id>.sut"'                                  # itest ids (T7)
hx "$A" restore-events-<id> 'events_cleanup <id> ~/egw-tcg/pilot/results/raw/<id>/logs/sut'      # plan entries (T1 harness, T6)
# 2. a service left stopped (T7's own STOP names this line; services: mongodb, ditto-things, controller)
hx "$A" restore-start-<service> 'ssh egw-tcg "cd /opt/egw/deployment && docker compose --env-file .env --env-file images.lock.env start <service>"'
# 3. the harness's collector egw-resources-<plan entry> left active (the harness's own stop command)
hx "$A" restore-collector-<id> "ssh egw-tcg 'sudo systemctl stop egw-resources-<id>'"
# 4. the tunnel
hx "$A" restore-tunnel 'tunnel_down && tunnel_up'
```

The texts are in single quotes on purpose: `events_cleanup`, `$P` and `$EGW_CLONE` exist only inside `hx`'s shell
(the helpers are loaded there), and the `$DC` of the operator's shell is `guest_common.sh`'s, without the
`cd /opt/egw/deployment` — so the compose line is written out in full. Any restoration is itself a halt (packet §4,
halt 4): restore, record, `close`, hand back. A TERM also ends `local_export exec`, so a trap that prints to the
step's console may die before it restores (after a `term` on t1-harness, t6, t7-mongo or t7-ditto no `events_stop`
ran): after any `term`, check the services and the units before `close`.

## The operator's sequence

**S1** (rows 1–7): keepalive and keep-awake on → `open S1` → for each of `t1-smokes`, `t1-harness`, `t2`, `t3`,
`t4-replay`, `t4-reset`, `t5`: `row <slug>` → read `<attempt>/console/` and the files → `classify <slug> …`
(packet §5) → next row only if the gate passed and no halt condition holds → `close` → seal the operator records,
write `output_test/decisions/<date>_g3-battery-s1-results.md`, release keepalive and keep-awake.

**S2** (rows 8–12), only if S1 reached its planned end without a halt: the same with `open S2` and `t6`, `t7-mongo`,
`t7-ditto`, `t8`, `t9`. T6: compare the printed configuration identity with packet §1 by hand (a difference is
halt 6). T9 runs only if T8 showed the reboot.
