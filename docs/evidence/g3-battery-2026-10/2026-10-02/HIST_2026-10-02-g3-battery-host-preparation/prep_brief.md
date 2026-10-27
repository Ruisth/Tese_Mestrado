# G3 battery — host preparation, part 2: the row files and the operator's steps script

`$S` = `C:/Users/ruimf/AppData/Local/Temp/claude/C--Users-ruimf-Documents-Projeto-Mestrado/d631a3f3-65ca-4372-97f1-525d6d1e593d/scratchpad`
(in WSL: `/mnt/c/Users/ruimf/AppData/Local/Temp/claude/C--Users-ruimf-Documents-Projeto-Mestrado/d631a3f3-65ca-4372-97f1-525d6d1e593d/scratchpad`).
Everything you write goes under `$S/g3/battery/prep/` (LF line endings only, no CRLF; UTF-8).

## Authority and what is fixed

Rui authorised on 2026-10-02 the freeze of the candidate and the G3 qualifying battery
(`C:/Users/ruimf/Documents/Projeto Mestrado/output_test/decisions/2026-10-02_g3-freeze-and-battery-authorisation.md`),
under the packet `…/output_test/decisions/2026-10-01_g3-candidate-freeze-and-battery-packet.md` (revision 2; READ IT
IN FULL: §2 the twelve rows and ids, §3 execution and evidence, §4 limits, halts and safe close, §5 classification)
and the operator procedure `$S/g3/battery/operator-procedure.md` (READ IT IN FULL). Per-family detail extracted
from the runbook: `$S/g3/battery/fam-A.md` (T1–T3), `fam-B.md` (T4–T6), `fam-C.md` (T7–T9), `host.md` (session
mechanics, §3 and §4), `ident.md`.

The candidate is FROZEN at `80e833f` (tree `dad725d`). Read-only copies: `$S/cand` (Windows worktree, for reading) and
the WSL execution clone `~/egw-exec/repo` (already at `80e833f`, clean; host preparation part 1 is done and recorded
in `$S/g3/battery/prep/record/console.txt`).

## HARD RULES (a breach can burn a run id or dirty the frozen clone)

1. NEVER write, create or delete anything in `~/egw-exec/repo`, `~/egw-exec/attempts`, `~/egw-exec/venv`,
   `~/egw-tcg` (the real run directory: any file `~/egw-tcg/itest/<id>*` makes that run id used),
   `~/egw-images`, `~/yocto`, `output_test/`, `ChatGPT/`, or `$S/cand`. Never run pytest or any command that writes
   caches inside `~/egw-exec/repo` or `$S/cand`.
2. NEVER start QEMU, never `ssh`/`scp` to `egw-tcg` or 127.0.0.1:2222, never run the session drivers for real.
3. A dry run uses an isolated tree only: `export HOME=<a temp dir you create under /tmp/g3-dry-<name>>`, with
   `EGW_EXEC`, `EGW_ATTEMPTS`, `EGW_OUTPUT_TEST`, `EGW_SECRETS_ENV`, `EGW_EXEC_REPO` pointing inside it, a COPY of the
   repository there (`git -C <WSL path of $S/cand> archive HEAD | tar -x -C <temp>/repo`), and stub `ssh`, `scp`,
   `curl`, `docker`, `python -m egw_simulator` etc. first on `PATH` (see how `src/tests/test_session_drivers.py`,
   `test_runbook_itest_helpers.py` and `test_runbook_capture_wiring.py` build their stub benches). Use the real
   venv's python read-only (`~/egw-exec/venv/bin/python` with `PYTHONDONTWRITEBYTECODE=1` and `PYTHONPATH=<temp>/repo/src`).
4. WSL commands from the Bash tool: `MSYS_NO_PATHCONV=1 wsl -d Ubuntu-24.04 --exec bash -lc '…'`. Scripts with
   backslashes are written with the Write tool, never through a shell heredoc.
5. Do not edit frozen code and do not propose to. No change of criteria, thresholds, `DRAIN_*`.

## Fixed names

Row and step files, in `$S/g3/battery/prep/rows/` (one LF-only bash text per step; each is SOURCED by the steps
script inside one `hx` shell, so carriers chain within a file):

| Row (slug) | Session | Step files, in order |
|---|---|---|
| `t1-smokes` | S1 | `t1-smokes.sh` |
| `t1-harness` | S1 | `t1-harness.sh`, then `t1-harness-analyze.sh` (prose-only step, runbook line 1320) |
| `t2` | S1 | `t2.sh` |
| `t3` | S1 | `t3.sh` |
| `t4-replay` | S1 | `t4-replay.sh` |
| `t4-reset` | S1 | `t4-reset.sh` |
| `t5` | S1 | `t5.sh` |
| `t6` | S2 | `t6.sh` |
| `t7-mongo` | S2 | `t7-mongo.sh` |
| `t7-ditto` | S2 | `t7-ditto.sh` (opens with test 7's definition lines verbatim, no action, then the Ditto repeat's lines) |
| `t8` | S2 | `t8-a-reboot.sh`; the re-launch (steps script); `t8-b-return.sh`; `t8-c-snapshot.sh` (only if the tunnel is up); `t8-d-smoke.sh` (only after `REBOOT SHOWN` and no `STOP:`) |
| `t9` | S2 | `t9-a.sh`, `t9-b.sh`, `t9-c.sh`, `t9-de.sh` (each only if the one before printed no `STOP:`), then `t9-exposure.sh` (prose-only checks) |

Ids (packet §2): every runbook literal gains `-q1`: `itest-smoke-$i` → `itest-smoke-$i-q1`, `itest-3dev-01-q1`,
`itest-invalid-01-q1`, `itest-dup-01-q1`, `itest-dup-02-q1`, `itest-dropout-01-q1`, `itest-mongo-fault-01-q1`,
`itest-ditto-fault-01-q1`, T8's prefix `itest-reboot` → `itest-reboot-q1` (all 8 literals together) and
`itest-post-reboot-01-q1`, `itest-tls-wrongca-q1`, `itest-auth-wrongpw-q1`, `itest-notls-q1`. NOT changed:
`nominal-r02`, `controller_restart-r03`, `itest-acl-$T`, the directory name `itest-replay`.

Steps script: `$S/g3/battery/prep/g3_battery.sh`; extraction script: `$S/g3/battery/prep/g3_extract_rows.py`;
manifest: `$S/g3/battery/prep/rows/rows.manifest.json`; ids-only diffs: `$S/g3/battery/prep/rows/<file>.diff`.

## The steps script's design (the operator runs ONE subcommand per invocation and classifies between rows)

`g3_battery.sh <subcommand>`, run in WSL as `bash -lc 'EGW_EXEC_REPO=$HOME/egw-exec/repo bash <path>/g3_battery.sh …'`.
It sources the frozen `tools/session/common.sh` and `guest_common.sh` (see operator-procedure "Loading the drivers";
set `DRIVERS=$REPO/tools/session` after sourcing) and uses ONLY their functions and `local_export` to record.
State directory: `${EGW_G3_STATE:-$EXEC/g3-battery}` (a `session-<S1|S2>.env` with the session label, UP0 and the
session attempt; one `row-<slug>.env` per row with its attempt directory, start uptime, pgid and state).

- `open S1|S2`: refuse if a session is open or a state file for that session exists; verify the clone
  (`80e833f`/`dad725d`, clean), the helper file (`e5eba37e…`, 545 lines), every id of that session still fresh on
  the host (the same checks as `prep/g3_hostprep.sh`), the row files against `rows.manifest.json` (sha256), and that
  a keepalive `wsl.exe` client is attached (a process check the operator procedure names; if it cannot be checked
  from inside WSL, print what the operator must check). Record `UP0` (whole seconds of `/proc/uptime`). Then run the
  frozen drivers in order, each as a child `bash "$REPO/tools/session/<driver>.sh"` with its console teed into the
  state directory: `guest_session_open.sh`, `preflight.sh`; then the environment copy of PM condition 2 (operator
  procedure "Environment input": the old file kept beside itself under its sha256, the preflight attempt's
  `environment/sut_environment.json` copied in, the labels checked, hashes recorded); then `gate_health.sh`. Any
  non-zero driver exit or failed check prints `HALT: …` and exits non-zero WITHOUT closing (the operator decides and
  runs `close`).
- `row <slug>`: refuse unless that session is open, the previous row of the session is classified (state), this
  row is not started yet, the clock allows it (`NOW − UP0 < 10800`, else print `NOT STARTED: the 3 h cutoff` and
  exit), and the tunnel/keepalive checks pass. Create the attempt
  (`new_attempt "G3 qualification <slug>" official`), record identities and a `workload` field (never `run_id`),
  copy the row's step files and their manifest entries into `$A/environment/`, register the sources
  (`add-source`: `simulator` for each itest id with `--siblings-glob "<id>.*"`, `raw` for the harness capsule,
  `other` for the replay directory, T8's prefix files, T9's ACL directory, the plan and `processed/` snapshots:
  see host.md §4.3 item 3 and fam-*.md section (e)), run the gate's BEFORE read, then each step as
  `hx "$A" <step> "exec 2>&1; unset DEVICES ACCEPT_UNACCOUNTED EVENTS_EXPECTED DRAIN_QUIET_S DRAIN_LIMIT_S READY_LIMIT_S; set -v; . '$A/environment/<step>.sh'"`
  (`$A` expanded by the steps script; never `set -x`, no `set -e`), with the row-specific conditions of the table
  above (T8's re-launch and conditions; T9's "no STOP so far"; T1 harness then analyze with plan and `processed/`
  copied before and after), then the gate's AFTER read and checks (operator procedure "The gate inside each
  attempt"). It then prints where the console and files are and leaves the attempt OPEN for the operator's
  classification. A step status 97 or 74, a failed gate, or a needed restoration prints `HALT: …`.
  INT/TERM: the frozen `driver_interrupt` behaviour (attempt finished `interrupted`, exported).
- `classify <slug> <status> <validity> <outcome> <reason> <next-action>`: `local_export finish` with the operator's
  classification (packet §5 mapping), `headline`, export (`driver_exit` semantics but WITHOUT exiting the battery
  state: record the export result), mark the row classified.
- `term <slug>`: send TERM (never KILL) to the recorded process group of a running row.
- `close`: refuse if a row is running; check no `egw-events-*`/`egw-resources-*` unit is active (read-only `gx`);
  the recorded `compose stop -t 130` step on the session attempt (operator procedure, exact command with BOTH env
  files); a non-zero exit prints `HALT: stop failed` and does NOT continue to the close driver; then
  `bash "$REPO/tools/session/guest_session_close.sh"`; record its exit; print what remains for the operator
  (seal operator records, release keepalive and keep-awake).
- `status`: print the session state, elapsed host uptime, rows done/classified.

Nothing in it kills QEMU, deletes anything, repeats a row, retries a failed step, or uses `ACCEPT_UNACCOUNTED`,
`--force`, `local_export set run_id=…`. Every halt leaves the decision to the operator.
