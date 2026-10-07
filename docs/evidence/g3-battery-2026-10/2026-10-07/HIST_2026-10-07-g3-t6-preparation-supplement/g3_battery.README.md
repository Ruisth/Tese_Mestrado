# g3_battery.sh — the operator's steps script of session S4 (test 6 only)

Authority: the request of 2026-10-05 (`output_test/decisions/2026-10-05_g3-t6-session-request.md`) and Rui's
authorisation of ONE attempt of test 6. The session starts only on his explicit authorisation and his go in the
attended window («estou presente»), after the sealed preparation package has been delivered. The authorities of S1,
S2 (the battery of 2026-10-02/03) and S3 (tests 8 and 9, 2026-10-05) are consumed: `open` accepts `S4` only. Test 6
is judged under the criterion amended on 2026-10-05 (LOG #C052) with option A's transition rule
`1a-option-a-2026-10-05` (LOG #C053). Procedure and tools: the merged commit `1fd9792` (tree `14f89c4`); the
candidate (controller image, pinned images, deployment, guest OS) is unchanged, except the collector that the frozen
preflight installs at `open`; the script edits nothing of it. It records only through the frozen `common.sh` /
`guest_common.sh` functions and `local_export`. It kills no QEMU, deletes nothing, repeats no row, retries no step,
and never uses `ACCEPT_UNACCOUNTED`, `--force` or `local_export set run_id=…`. G3 stays `Not decided` whatever S4
shows.

**What changed against the script S3's second opening ran** (each change stands under a comment naming `S4` and the
point of the preparation's brief): the label `S4` and its one row `t6`; the merged identities (`TOOLS`, `TREE`,
`DRIVERS_SHA` `2c209b09…`, `RUNBOOK_SHA` `31716593…`) and a new `COLLECTOR_SHA` `9e678b02…`; the root file system
expected `6fce1688…`; the state directory `~/egw-exec/g3-t6-s4`; S3's prospective exception for `collector-duration`
removed (a preflight that ends non-zero is a halt, as in S3's first opening); `controller_restart-r04`; S2's t6
attempt admitted and `…_g3-qualification-t6_attempt02` required; the gate's record of the running images compared
before row t6; the authority text of S4 in the attempt's `workload` field. Test 8's and test 9's code is left as it
was and is reached by nothing.

**What the script never does.** It never runs `compose up`, `start` or `restart`, nor `docker start`; it never
re-launches QEMU and never signals it. The one stack start of S4 is the frozen preflight driver's, at `open`. The
controller restart at +300 s is test 6's own fault, issued by the harness's `--restart-cmd` inside the runbook's line
that `t6.sh` holds: it is the test, never a restoration. Nothing else on the guest is started, restarted or recreated,
by the script or by the operator.

## Launch (one subcommand per `wsl.exe` invocation)

`<P>` is the WSL path of the folder that holds this script (the preparation folder, `…/scratchpad/g3/t6prep`).

```bash
# short subcommands (status, classify, term), in the foreground:
MSYS_NO_PATHCONV=1 wsl -d Ubuntu-24.04 --exec bash -lc 'EGW_EXEC_REPO=$HOME/egw-exec/repo bash "<P>/g3_battery.sh" status'
# long subcommands (open, row, close), detached from the client that starts them:
MSYS_NO_PATHCONV=1 wsl -d Ubuntu-24.04 --exec bash -lc 'EGW_EXEC_REPO=$HOME/egw-exec/repo setsid bash "<P>/g3_battery.sh" row t6 > /dev/null 2>&1 < /dev/null & sleep 2'
```

- `MSYS_NO_PATHCONV=1` always (Git Bash rewrites `/home/…` otherwise); `bash -lc` (login shell).
- A detached run prints nothing to the caller: its whole console is `<state>/console/NNN-<subcommand>-<arg>.txt`
  (`status` names the latest). Follow it with `tail`, and wait for `status` to show the row
  `awaiting-classification`. `ops/g3_go.sh` and `ops/g3_wait.sh` wrap this launch and this wait.
- One subcommand per invocation: a row's process group must be its own (`term` signals that group).
- **One changing subcommand at a time.** `open`, `row`, `classify` and `close` each take the turn
  (`<state>/turn.env`, written under a short `flock`) and are refused (`REFUSED: another invocation of this script is
  still running: …`, exit 2, nothing started or changed) while another of them is still running. `status` and `term`
  take no turn. A turn whose holder ended is simply taken; nothing is deleted.
- **Keepalive:** before `open`, start a dedicated client and leave it running until after `close`:
  `MSYS_NO_PATHCONV=1 wsl -d Ubuntu-24.04 --exec bash -lc 'exec sleep 43200'` (a background task). `open` wants 6 h
  left on one of them, `row t6` 77 min (its 47 min ceiling plus 30 min) and `close` 30 min; the script checks the
  `sleep` and its WSL relay parent. Without a client the distro stops, and QEMU with it.
- **Keep-awake:** Windows must not sleep or hibernate for the whole session. It cannot be seen from WSL: it is the
  operator's own check before `open` and before `row t6`. No other load on the host (no build, no pytest).
- Never edit the script, the row file or the manifest while a session is open: `row` refuses a changed script.

## Subcommands

| Subcommand | What it does | Refuses (exit 2) when |
|---|---|---|
| `open S4` | Checks, each a HALT with nothing started when it fails: the clone at `1fd9792`/`14f89c4` and clean, `drivers_sha256` `2c209b09…`, the export tool `544c9b3d…`, the runbook `31716593…`, **the clone's collector `src/deployment/scripts/collect-resources.sh` `9e678b02…`**, the helper file `e5eba37e…` (545 lines, `bash -n`), `tunnel.sh`, `ca.crt`, the kernel, `qemuboot.conf`, the QEMU binary, the Yocto checkout (`489bc9e`, clean), the guest-state command against `nominal.sh`; `t6.sh` against `rows.manifest.json`; `controller_restart-r04` `planned` in the pilot plan with no raw directory and no `~/egw-tcg/itest/controller_restart-r04` or `….*`; no earlier t6 attempt except S2's one; the root file system at `6fce1688…`. Then the keepalive, `UP0`, the frozen `guest_session_open.sh`, `preflight.sh` (any non-zero exit is a HALT: there is no exception in S4), the environment copy of PM condition 2, `gate_health.sh` (its attempt is named in the state file), and one read-only listing of the guest's event directories (`controller_restart-r04` unused there too). | the label is not `S4` (`S1`, `S2`: "… whose authority is consumed"; `S3`: "… is closed and its authority is consumed"); a session is open; `session-S4.env` exists; a QEMU process runs or that could not be determined; the keepalive is missing |
| `row t6` | Before the attempt (each a HALT, no attempt created): the identities again (the collector included), the row file, the WSL boot, the cut-off, a QEMU process, the tunnel, the freshness of r04 and of the row, **the gate's record of the running images against S2's**. Then one attempt (`G3 qualification t6`, purpose `official`), which must be named `…_g3-qualification-t6_attempt02`; its identities and a `workload` field naming S4's authority; `t6.sh` and its manifest entry copied to `environment/`; the sources registered; the gate's read before; the plan and `processed/` copied; the one step (`hx`: one shell sources `t6.sh`, `set -v`, carriers unset and printed); the plan and `processed/` copied again; the gate after. Leaves the attempt OPEN. | the row is not `t6`; the session is not open; the row was already started; the script or manifest changed; the session has a recorded halt; the keepalive is short |
| `classify t6 <finished\|failed> <validity> <outcome> <reason> <next-action>` | `local_export finish`, a headline, the export (`driver_code`: prints `DRIVER RESULT`), the row marked classified. Pairs: `valid/pass`, `valid/fail`, `invalid/unknown`, `valid/inconclusive`, `unknown/inconclusive`, `not-applicable/not-run`. A reason or next action given as `@FILE` is read from that file. | the row does not await classification; the pair is not one of the six |
| `term t6` | TERM, never KILL, to the row's recorded process group, after listing it (command lines cut at 90 columns, the value after every `--password` hidden). The row's trap finishes the attempt `interrupted` and exports it (after letting the group end by itself, 180 s at most, and one guest-state read). If a QEMU process or the keepalive client is in that group it prints `HALT:` and signals nothing. | no process of the row is left; the recorded group is the caller's own |
| `close` | No unit `egw-events-*` / `egw-resources-*` active (read-only); the recorded `docker compose --env-file .env --env-file images.lock.env stop -t 130` as step `stack-stop-130` of the session attempt; then the frozen `guest_session_close.sh`. Records the post-close root file system hash and lists the data disk's ext4 header (read-only, only with no QEMU process left). With **no QEMU process left** there is nothing to read or stop: it records a HALT, skips the unit check and the stop, and runs the frozen close driver, which finishes and exports the session attempt as it stands. | another changing subcommand is running; the row is running or awaits classification; a process is left in the row's group; the row's process died and its attempt is still open; the keepalive has less than 30 min left; no session is open |
| `status` | The session, elapsed host uptime against the 3 h cut-off, the row's state, gate, class and export, a running row's minutes against its ceiling, every recorded halt. Read-only. | — |

`row` never judges: the step's exit status is the status of its last line (line 1428's `analyze`). Every other row
(the battery's t1 to t7, S3's t8 and t9) is not a row of this script (`REFUSED: unknown row`).

**The ceiling (47 min) is counted from the row's start** — the instant recorded as `start_up` when `row` begins,
before the attempt exists — and is shared by everything the row does (the checks, the snapshots, the step, the
gate). It is recorded and shown by `status` (`PAST ITS CEILING`); no timer enforces it: the operator does, with
`term t6`. No row starts at or after 3 h (`CUTOFF_S=10800`) of host uptime counted from `UP0`.

## The S4 flow, step by step

1. **Before.** The preparation package sealed and delivered; Rui's authorisation of S4 and his «estou presente»; a
   keepalive client with at least 6 h left; Windows kept awake; no other load; no QEMU process and no open session;
   the clone at `1fd9792` and the plan holding r04 (the host preparation, `g3_hostprep.sh`, recorded both).
2. **`open S4`** (about 7–10 min in S1–S3). The frozen preflight starts the stack through its interlock, copies the
   clone's collector to the guest and installs it (the previous one kept in `/opt/egw/evidence/collector-previous/`),
   compares the deployed tree with the clone (`README.md` excepted), checks health, runs 45 s of live collection and
   judges `collector-duration` on the uptime bounds of the collector's own `start:` and `stop:` records. It ends
   `session S4 is open` and `Next: 'row t6'`.
3. **`row t6`** (about 20–25 min; ceiling 47 min). The gate record (`gate record: … equal S2's`), the attempt
   (`…_g3-qualification-t6_attempt02`), the gate's read before, `snapshot-before`, the step `t6`, `snapshot-after`,
   the gate after. Inside the step, the eight runbook lines run in one shell:
   - line 1421: `RID=controller_restart-r04` and `F6=fresh` unless the raw directory or `$P/$RID.sut` exists;
   - line 1422: the seed from the plan (1715385812); lines 1423–1424: `RESTART` (the compose restart of the controller
     through `ssh egw-tcg`) and `RAW6`;
   - line 1425: `wait_ready`, `drained`, `config_identity`, then `harness_cmd` (the Docker events recorder, the 600 s
     run at 11.2 msg/s, the controller restart at +300 s, the twin hook, the drain with the runbook's 130 s / 5 s /
     900 s, the post-drain copy, the StartedAt read, `--restart-transition-rule 1a-option-a-2026-10-05`); it prints
     `resources_proved_down` and `resources_transition_rows` from the manifest and sets `T6` (`ok`, `gaveup`,
     `incomplete`, `stop`);
   - line 1426: `delta` on the post-drain copy (only when `T6=ok`);
   - line 1427: `acceptance … --exactly-once` on the post-drain copy (only when `T6=ok`);
   - line 1428: `analyze` (always), which rewrites `processed/` (`per_run.csv`).
   The harness rewrites the plan entry itself (`run.py` `update_plan_status`: `running`, then `completed` or `failed`
   with `result_dir`, `finished_utc` and `validity`): `other/campaign_plan.before.json` and `.after.json` show it, and
   the plan's sha256 is no longer `61d55940…` after S4. The gate after the row compares the guest state before and
   after with `guest_state_delta.py --expect-restarted egw-controller-1`: the controller's one in-place restart (same
   container id, later start instant, restart count unchanged, no OOM) is `EXPECTED-RESTART`; anything else about it,
   or any change of another container, is a fault and fails the gate.
4. **The operator reads** the step's console and the files, compares the configuration identity with the packet's
   section 1, and classifies with the table of `operator-procedure.md`: **`classify t6 …`**.
5. **`close`.** Then: every export verified (the export tool's own verification, then `sha256sum -c` in each
   package), the operator records sealed as `HIST_<UTC date>-g3-t6-s4-operator-records` (an `-attemptNN` suffix if
   that name exists), the result note `output_test/decisions/<date>_g3-t6-results.md`, keepalive and keep-awake
   released.

## State files (`${EGW_G3_STATE:-~/egw-exec/g3-t6-s4}`; `key=value` lines, never sourced)

The battery's state directory `~/egw-exec/g3-battery` and S3's (`~/egw-exec/g3-t8t9-s3`,
`~/egw-exec/g3-t8t9-s3-attempt02`) are never written.

- `session-S4.env`: label, `state` (opening, open, halted, closed, close-failed), `up0`, the WSL boot id, the session,
  preflight and gate attempts (`gate_attempt`), each driver's exit, the environment copy's hashes,
  `rootfs_before_boot`, `rootfs_after_close`, every `row_clock=` reading and every `halt=` line.
- `row-t6.env`: the attempt and its name (`attempt_name`), `start_up`, `ceiling_min`, `pid`/`pgid` with their start
  instants, `state` (preparing, running, gate, awaiting-classification, classified, interrupted), the current `step`,
  every `step_done=`, the `gate`, the class, the driver code and the export receipt.
- `turn.env` and the empty `turn.lock`; `row-t6.group-after-signal.txt` (passwords hidden); `console/NNN-….txt` (one
  per invocation), `S4-<driver>.console.txt`, `S4-environment-copy.txt`, copies of the script and manifest as opened.
  Together with the classification notes these are the operator records.

No process listing reaches these files, or the caller's terminal, with a password: every listing is passed through a
mask and cut at 90 columns. The frozen export's secret scan reads attempts only, never the state directory.

## Every `HALT:` and what the operator does next

A halt before the row's step ends the invocation there. A halt inside the row ends the row's steps, but the gate
still runs, after which the row awaits classification. Nothing is closed, except at `close` with the guest gone.
Every halt is recorded in the session's state file once the session is in use, and **a halt ends S4**: no variable
lifts it (`EGW_G3_RUI_GO` is read only by `close` for a session closed outside the script). A row classified invalid
instrumentation or not started records a halt too. **After any halt: classify the row if it awaits classification
(class by its cause, `operator-procedure.md`), then `close`, then hand back to Rui. Nothing is repeated and nothing is
fixed.** `REFUSED:` (exit 2) is not a halt: nothing was started or recorded.

| Where | The text begins | What it means | Next |
|---|---|---|---|
| `open`, checks | `HALT: <identity> (<path>) is …, the recorded identity is …`; `the clone … is not at …`; `… is not clean`; `the Yocto checkout … is at …`; `drivers_sha256 is not …`; `… (packet section 4, halt 6); nothing was started` | an identity of the request's section 2 differs (the collector `9e678b02…` included: `HALT: collector (…collect-resources.sh) is …`) | nothing ran and no state file exists; report to Rui; `open S4` is run again only on his direction |
| `open`, checks | `HALT: the row files of t6 are not the manifest's` | `t6.sh` or the manifest changed | the same |
| `open`, checks | `HALT: an id of S4 is not fresh on the host` (the `NOT FRESH:` or `plan entry …: status=…` lines above it name the cause) | r04 not `planned`, its raw directory, `$P/controller_restart-r04` or `….*` exists, or an earlier t6 attempt that is not S2's admitted one exists (or S2's is found in another place) | the same |
| `open`, checks | `HALT: the guest root file system is not the expected one` | the `.ext4` is not at `6fce1688…` | the same |
| `open`, drivers | `guest_session_open.sh exited N`; **`preflight.sh exited N`** (a failed `collector-duration` included: there is no exception in S4); `the preflight's attempt could not be named`; `the environment copy … failed`; `gate_health.sh exited N`; `the guest's event directories could not be listed`; `an id of S4 has an event directory on the guest`; `open S4 was interrupted by a signal` | the session is used and recorded `halted`; test 6 is not run | `status`; if `current_session` exists the guest is UP: `close`; hand back |
| `row`, before the attempt | `<identity>: row t6 was NOT started and no attempt was created`; `the row files of …`; `WSL was restarted since …`; `NOT STARTED: the 3 h cutoff`; `no qemu-system-aarch64 process could be shown`; `tunnel_check failed before row`; `an id of row t6 is not fresh on the host, or an earlier attempt …` | the request's section 5, items 1 and 5 | `close`; hand back |
| `row`, before the attempt | `the gate package's record of the running images … differs from S2's …` or `… could not be read …: row t6 was NOT started` | the images the gate found running are not S2's (S3's matched them), or the record is not there | `close`; hand back |
| `row`, attempt created | `the new attempt is named …, which does not end '_g3-qualification-t6_attempt02' … No step of the row was run` | an attempt of t6 exists that was not accounted for, or S2's attempt01 is not where it is kept | classify `not-applicable/not-run`; `close`; hand back |
| `row`, attempt created | `the attempt fields could not be recorded`; `… could not be copied into the attempt`; `a source could not be registered`; `the guest state before the row was not recorded`; `the plan and processed/ could not be copied before the harness` | no step of the row was run | classify `invalid/unknown` (instrumentation; the same in the operator procedure); `close`; hand back |
| the step | `step t6 answered 97` (the preamble of runbook 6.1 or the tunnel did not load: the step never ran); `step t6 answered 74` (its console capture was lost) | instrumentation | classify `invalid/unknown`; `close`; hand back |
| after the step | `the plan and processed/ could not be copied after the row` | a snapshot failure (instrumentation) | classify by the step's console and this failure; `close`; hand back |
| the gate after | `the gate did NOT pass: …` | a service not healthy within 900 s, a unit active, the tunnel down and reopened, the guest state not recorded, an OOM kill, an unexpected restart or replacement, or the controller's restart not shown by the pair | classify; `close`; hand back |
| any time in the row | `row t6 was interrupted by a signal` | `term t6` (the ceiling) or a lost terminal: the attempt is finished `interrupted` and exported; it is not classified again | `status`; `close`; hand back |
| `classify` | `the export FAILED`; `row t6 is classified not started`; `row t6 is classified invalid instrumentation` | the attempt is kept in WSL for `local_export recover`; a halt is recorded | `close`; hand back |
| `term` | `a qemu-system-aarch64 process is in the row's process group`; `the keepalive client … is in the row's process group` | nothing was signalled | hand back |
| `close` | `a recorder or collector unit is active (exit 3): nothing was stopped` | read the unit's name in the `g3-close-units` console. Only `egw-events-controller_restart-r04` has a prescribed remedy: after `T6=incomplete` (`harness_cmd`'s cleanup failed), and after `term t6` (S4, bench F1: the TERM to the row's group also ends the step's console pipe, so `harness_cmd`'s own cleanup can die before it runs) | for that unit only: `ops/g3_recorder_cleanup.sh` (supplement of 2026-10-07; below, "The recorder's emergency cleanup"), then `close` again only after its `OK:` line; its `HALT:` means do NOT close: hand back to Rui. The harness's collector unit `egw-resources-controller_restart-r04` ends by itself at its `--duration 600` bound: wait for it read-only and run `close` again. Any other active unit (an `egw-resources-*` one, or another run id): no prescribed cleanup in S4; record it, stop nothing by hand, hand back to Rui |
| `close` | `the guest did not answer (exit 97) although a qemu-system-aarch64 process is running: … nothing was stopped` | the guest cannot be closed safely | **preserve the state, signal nothing, claim no controlled close, ask Rui** |
| `close` | `stop failed (stack-stop-130 exit N): the close driver was NOT run and QEMU is NOT forced off` | the recorded stop did not end 0 | hand back; never a forced power-off |
| `close` | `no qemu-system-aarch64 process is left …` | the guest was lost before the close: the frozen close driver alone finishes and exports the session attempt (expect its exit 5) | hand back; nothing is re-launched |
| `close` | `guest_session_close.sh exited N …`; `… current_session is kept: the session is NOT closed`; `row t6: its process died without its trap …`; `session S4 was not closed by this script …` | the close driver's own result, or a record made on Rui's direction | read the driver's console; hand back |

The script records only the halts it detects. What the operator reads from the console or the files (a `STOP:` of
the step, a configuration value that differs from the packet's section 1) is classified and written in the result
note; there is no further row in S4 in any case.

### A guest that does not answer while QEMU runs

At the gate or at `close` (exit 97 with a QEMU process running), or in the step (the harness's reads failing):
nothing is stopped or powered off from the host. QEMU is left running and is not signalled, the session stays open,
no controlled close is claimed, and what is done with QEMU is Rui's decision in the window (the data disk is at
stake). `close` answers the same for as long as the guest does not answer.

### A row whose process died without its trap

Its state file still says `running` (or `preparing`, `gate`), `status` says `its process … is GONE`, and its attempt is
still open in WSL. `close` refuses on it and prints the frozen line that marks and exports it
(`local_export recover … --interrupt <run id>`, with this host's paths). First fetch what the row left on the guest
(the guest's `/tmp` is lost at power-off). Then `close` again: it finds the attempt finished and exported, records the
row `interrupted` with a halt, and goes on.

### A session closed outside the script

If the frozen `guest_session_close.sh` was run by hand (or an `open` halted before any session existed), no session is
open and the state file still says `open` or `halted`: `close` answers `REFUSED: no open session … recorded 'open'`.
Only on Rui's explicit direction: `EGW_G3_RUI_GO="<his words>" … g3_battery.sh close` records the session `closed`
with a halt (his words recorded), and only if no `current_session` exists, no QEMU process runs and no row is running
or unfinished.

### Restorations

None is expected in S4, and any restoration is itself a halt (request, section 5 item 6): record, halt, hand back.
Only the runbook's own exist — the recorder's capture cleanup after `harness_cmd` answered 3 or after `term t6`
(bench F1), run by `ops/g3_recorder_cleanup.sh` (below), and `tunnel_down && tunnel_up`, run by hand through the
frozen `hx` on the attempt that is open — never to let the row go on.

### The recorder's emergency cleanup (supplement of 2026-10-07)

**When:** after `term t6` (the ceiling) and after `T6=incomplete` (`harness_cmd` answered 3), **always, before
`close`** — also when no unit is listed active: a recorder stopped with its capture still only in the guest's
`/tmp/egw-events-controller_restart-r04` would pass the close's unit check and be lost at the power-off.

**Launch (one invocation, foreground):** `MSYS_NO_PATHCONV=1 wsl -d Ubuntu-24.04 --exec bash -lc 'EGW_EXEC_REPO=$HOME/egw-exec/repo bash <P>/ops/g3_recorder_cleanup.sh'`

**What it does:** the existing command, unchanged, `events_capture.sh cleanup controller_restart-r04 KEEP_DIR` of the
clone, with `KEEP_DIR` = `<session attempt>/recovery/events-partial-controller_restart-r04`, inside the session's
attempt, which the frozen close driver exports with the session's package. The command stops the unit if it is not
shown stopped, then copies the recorder's four files (`events.partial.jsonl`, `lifecycle.txt`, `start-facts.txt`,
`cli-stderr.txt`) as a partial capture, never as the run's `docker-events.log`, write-once; a staging folder that
holds some files (`KEEP_DIR.copy.*`) is kept and exported too. Each try is a recorded step of the session's attempt
(`recorder-cleanup-controller_restart-r04-tryN`) bounded by `timeout 120`; at most three tries. After a try that
ended 0, two recorded confirmations: the unit's state on the guest (`inactive` or `failed`) and the four files listed
with their sha256.

**Its answers:** `OK: … 'close' may run` (exit 0): run `close`. `HALT: … do NOT run 'close' …` (exit 1): stop there;
nothing was signalled or powered off; the guest's capture stays in its `/tmp` while the guest is up; hand back to
Rui (no forced power-off, no signal to QEMU). `REFUSED:` (exit 2): nothing ran (no open session, no S4 state
directory, or a subcommand of `g3_battery.sh` still holds its turn). A second invocation after an `OK` adds no try:
it confirms again. The script never runs `close`, never powers anything off and never signals any process.
**No service is started, restarted or recreated on the guest by hand at any point of S4** (`compose up`, `start`,
`restart`, `docker start`). A controller left stopped by the test's own restart is a failure the record shows, not
something to repair before the close.

## What is unverified

- **On the guest, nothing of the S4 changes has run.** The changed paths were exercised in two isolated benches:
  the operator stream's (`operator-record/bs4_op.sh`, eight scenarios, a stand-in `t6.sh`) and the bench of the final
  script (`bench/`, `bench-notes.md`: the REAL `t6.sh` through the script with the real helper functions, 25 scenarios
  PASS, 1,222 checks), both with stub `ssh`, `git`, `pgrep`, `ps`, `sha256sum` and four stub session drivers. The harness, `analyze`
  and `itest_reconcile` were stand-ins giving each case's files and exit codes: the real harness, the transition
  rule's computation, `delta` and `acceptance --exactly-once` on real files were not run by this preparation.
- The block's behaviour in a step shell (`set -v`, stdin closed, the `DRAIN_*` carriers unset) is shown for the same
  construct by S2's sealed attempt (`20261003T132936Z_g3-qualification-t6_attempt01`, console `003-t6`: the drain hook
  ran with 130 s / 5 s / 900 s); the new parts (`--restart-transition-rule`, line 1427) were read, not run.
- `term t6` during the harness (TERM to the whole group, `harness_cmd`'s own trap and cleanup) is the battery's design.
  The bench of the final script (`bench-notes.md`, F1) ran it against the test module's stubs: the TERM also ends the
  step's console pipe, `harness_cmd`'s cleanup died of SIGPIPE and the recorder unit stayed active, so `close` halted.
  With the real `events_capture.sh` (its guest command goes over `ssh`) the outcome is a race, not shown. The script
  is not changed for it: the close row above prescribes the runbook's own recorder cleanup, recorded, before `close`
  runs again. On the real harness and guest the path has never run.
- The merged lines' own assumptions (runbook Appendix B items 23 and 24): the transition rule on a live restart, the
  collector's uptime bounds, the exactly-once line on a real post-drain copy, `fetch_started_at.sh` on the guest, the
  Docker events of a compose restart on the guest's engine.
- A hung `open` or `close` holds the turn until it ends; the script offers no way to end one (`term` is for the row).
