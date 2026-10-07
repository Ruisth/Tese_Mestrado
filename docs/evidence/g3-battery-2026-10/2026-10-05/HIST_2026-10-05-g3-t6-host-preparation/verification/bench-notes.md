# Bench of the S4 operator script (test 6 only) — notes (2026-10-05; times in UTC)

`P` is this preparation (`<S>/g3/t6prep`), `<S>` the scratchpad (masked so in every console). Everything ran offline in
WSL (Ubuntu-24.04), under `/tmp/g3-s4-bench/<scenario>`, with `HOME` and every `EGW_*` inside the bench: no guest, no
QEMU, no docker, no real ssh, no build, no git command. Written: `P/bench/` (scripts and consoles), this note, and
`/tmp/g3-s4-bench/` in WSL. `P/g3_battery.sh` and `P/rows/` were not edited.

## Result

- **Script run: `P/g3_battery.sh` sha256 `7a63b361af2f25bd8ab81101ca10ec79fcb05a6e6f0cf0a70bc2ec63f3f8425c`** (2,356 lines),
  in place, with its own `P/rows/` (`rows.manifest.json` `7d2a0f0d…`, `t6.sh` `ec8ac010…`, the REAL step file) and its
  own default state directory `<bench>/egw-exec/g3-t6-s4`. Every scenario console names it on its first line and checks
  at its end that the script and `t6.sh` are unchanged.
- **25 scenarios, 25 PASS, 1,222 checks, 0 failed** (`P/bench/record/all.console.txt`, one pass on the final bytes,
  2026-10-05T19:58:57Z–20:03:18Z), plus one labelled experiment on a copy (`term-pipe-exp`, PASS, section 4).
- **No defect of `P/g3_battery.sh` was corrected**: no bench showed a wrong halt, a missed halt or a false pass of the
  script's own logic. **One finding** (section 4, F1): `term t6` while `harness_cmd` runs leaves the Docker events
  recorder unit `egw-events-controller_restart-r04` active on the guest, because the TERM to the row's group also ends
  the step's console capture and `harness_cmd`'s own interruption cleanup is then killed by SIGPIPE. It is not corrected
  here (reasons in section 4); a one-line remedy was shown to work on a copy and is left to a decision.
- **The final sha256 of `P/g3_battery.sh` is `7a63b361af2f25bd8ab81101ca10ec79fcb05a6e6f0cf0a70bc2ec63f3f8425c`**, the
  operator stream's (unchanged by this stream).
- **The real `~/egw-exec`, `~/egw-tcg` (plan `c195bd3f…`) and `output_test` are untouched** (section 6); no bench
  process is left.

## 1. The bench (`P/bench/`)

Built on S3b's bench (`<S>/g3/s3bprep/bench/`); each file says in its header what it took and what changed for S4.

| File | sha256 | From | What it is |
|---|---|---|---|
| `bs4_src.sh` | `265bdcb3…` | new | makes `/tmp/g3-s4-bench/_src` once, read-only: `tools/` and `src/{egw_experiments,egw_simulator,deployment,schemas}` of the read-only worktree `<S>/t6m` (1fd9792, tree 14f89c4), the runbook blob `P/runbook.1fd9792.md` as the clone's runbook; checks the runbook (`31716593…`, 1,624 lines), the export tool (`544c9b3d…`), the collector (`9e678b02…`), the 38 drivers in `repo_identity`'s order (`2c209b09…`) and the test module (`b63ef7d8…`) — `record/src.console.txt` |
| `bs4_setup.sh` | `256a58ea…` | `bs3b_setup.sh` | one bench: the repository copy (drivers hashed `2c209b09…` before six files become stubs), the module's stubs, the helper file and `tunnel.sh` by the runbook's own heredocs, a copy of the REAL plan (`c195bd3f…`) to which the merged `plan-supplement --entry g3-t6` adds r04 (`61d55940…`, 96 entries, checked), S3's sealed gate record, the stubs, the venv wrapper, four stub session drivers |
| `bs4_env.sh` | `826b47e6…` | `bs3b_env.sh` | the environment: `HOME`, every `EGW_*` in the bench; `EGW_G3_STATE` and `EGW_G3_ROWS` unset (the script's defaults); S3b's `BENCH_FAST_DRAIN` device removed |
| `bs4_stubs.py` | `664b1471…` | `bs3b_stubs.py` | imports the worktree's test module (`b63ef7d8…`) and installs its stubs and state; writes the two host files with its `tunnel_heredoc`/`helpers_heredoc` (`38f5cae9…`, `e5eba37e…`, 545 lines); adds `capture_text()` as the configuration identity |
| `bs4_harness.py` | `679dc276…` | new | the stand-in of `python -m egw_experiments run` and `analyze` (section 2) |
| `bs4_run.sh` | `116aaa90…` | `bs3b_run.sh` | the scenarios (helpers kept in substance) |
| `bs4_all.sh` | `c713d205…` | `bs3b_all.sh` | runs scenarios side by side; a console that exists is moved to `record/superseded/`, never overwritten |
| `bs4_untouched.sh` | `8b544713…` | `bs3b_untouched.sh` | the real trees before and after (section 6) |
| `bs4_sigpipe.sh` | `94bc15e1…` | new | a minimal experiment on the mechanism of finding F1 (`record/sigpipe.console.txt`) |

The operator stream's own bench (`P/operator-record/bs4_op.sh`) was read: its stub `ssh`, `sha256sum`, `git`, `ps`,
`pgrep`, the four stub drivers and the use of S3's sealed gate record were reused in substance; its stand-in `t6.sh`
was not (this bench runs the real one).

## 2. What is real and what is a stand-in

| Real (the code that will run in S4) | Stand-in or stub |
|---|---|
| `P/g3_battery.sh` itself, in place; `P/rows/t6.sh` (lines 1421–1428) sourced in the `hx` step shell (`STEP_PRE`, `set -v`, carriers unset) | the four session drivers (`guest_session_open.sh`, `preflight.sh` with modes pass/fail/invalid, `gate_health.sh`, `guest_session_close.sh`), in the copy only |
| the frozen `common.sh`, `guest_common.sh` (`hx`, `gx`, `ex`, `healthy_wait`, `driver_code`, `driver_interrupt`), `local_export.py` (new, exec, set, add-source, finish, export with its verification and secret scan), `driver_status.py`, `guest_state_delta.py`, `nominal.sh`'s `GUEST_STATE` (compared) | `events_capture.sh` and `proof_fetch_sut_log.sh` in the copy: the module's `STUB_EVENTS_CAPTURE` and `STUB_FETCH_SUT_LOG` |
| the helper file regenerated by the runbook's heredoc: `wait_ready`, `drained` (its real 130 s window on `/proc/uptime`, twice in `pass`), `config_identity` (its remote text answered by the module's stub, its validation and write real), `harness_cmd`, `events_start`, `events_cleanup`, `stop`; `tunnel.sh` (`tunnel_check`/`tunnel_up` against the module's ssh stub) | `ssh` (a wrapper: the script's own guest reads, the close's stop, test 6's restart recorded, the rest to the module's `STUB_SSH`), `curl`, `scp`, `ss`, `sudo`, `docker`, `git`, `sha256sum`, `pgrep`, `ps` (a synthetic keepalive client, as S3b's) |
| the checkout's `proof_hook_twins.sh` and `proof_hook_drained.sh`, run in `pass` by the stand-in exactly as `run.py` renders and splits them (`format_collector_template`, `shlex.split`, no shell, own session) | **the harness** (`bs4_harness.py run`): writes `~/egw-tcg/pilot/results/raw/controller_restart-r04/` (`manifest.json` with `drain.outcome`, `resources_proved_down`, `resources_transition_rows`, a `bench_stand_in` key; `SHA256SUMS` when its case ends 0; `events.jsonl`, `events.post-drain.jsonl`, `logs/simulator/<rid>/sent_events.jsonl` and `manifest.json`, `logs/sut/`), runs the `--restart-cmd` at once (not at +300 s) and exits with the case's code; it uses the merged `run.update_plan_status` for the plan entry (`running`, then `completed`/`failed` with `result_dir`, `finished_utc`, `validity`) |
| the merged `plan-supplement` (at setup only, on the bench's copy of the real plan) | **analyze** (`bs4_harness.py analyze`): writes `processed/per_run.csv` with the columns test 6 is read by |
| | `$REC delta` and `$REC acceptance --exactly-once`: the module's `STUB_PYTHON` (`rec_delta_rc`, `rec_acceptance_rc`); `plan-supplement` called by the row would be refused (99): it never was |

## 3. The scenarios (consoles `P/bench/record/<scenario>.console.txt`)

Each console starts with `script run: sha256 7a63b361…`, states what is expected, quotes the decisive lines and ends
with `SCENARIO <name>: PASS (<n> checks)`.

| Brief | Scenario | Run and expected | Observed (decisive lines, masked) | Result |
|---|---|---|---|---|
| 1 | `pass` (99 checks) | open S4; row t6 (harness 0 with the real twin and drain hooks, drain quiet, delta 0, `--exactly-once` 0, analyze 0); classify valid/pass; close | open: `collector: 9e678b02…  <bench>/repo/src/deployment/scripts/collect-resources.sh`, two `admitted: …20261003T132936Z_g3-qualification-t6_attempt01` lines, `fresh on the guest: controller_restart-r04`. Row: `gate record: the image reference, the image id and the repo digest of the six containers equal S2's`; `row t6: attempt …_g3-qualification-t6_attempt02 (ceiling 47 min…`; step console: `carriers after the unset: DEVICES=<unset> … DRAIN_QUIET_S=<unset> …`, `drained: queue_depth 0 and identical counters on N consecutive readings over 13x s`, `config_identity: wrote …/controller_restart-r04.config_identity.json`, `test 6: resources_proved_down: applies=True why_not=None D=2026-10-05T20:05:00.400000000Z …`, **`test 6: resources_transition_rows: rule=1a-option-a-2026-10-05 admitted=True why_not=None resources_ingested=True count=2 instants=[…]`**, `test 6: harness exit 0 and the recorder's cleanup done, run directory sealed, the drain quiet (manifest drain.outcome)`, `itest_reconcile stub: delta exit=0`, `itest_reconcile stub: acceptance exit=0`, no `STOP:`. Drain hook transcript: `proof_hook_drained: controller_restart-r04: drained with DRAIN_QUIET_S=130 DRAIN_STEP_S=5 DRAIN_LIMIT_S=900`. Calls: `… itest_reconcile acceptance <RAW6>/logs/simulator/controller_restart-r04 --events <RAW6>/events.post-drain.jsonl --exactly-once`; the harness got `--restart-at-s 300`, `--restart-transition-rule 1a-option-a-2026-10-05`, `--password <hidden>`. Snapshots: before `61d55940…` (r04 `planned`), after `completed validity=valid result_dir=set finished_utc=set`, `no processed/ tree at this moment` before, `processed.after/per_run.csv` after. Gate: `EXPECTED-RESTART: egw-controller-1 was restarted in place during the run, as expected: …`, `guest-state-delta: faults=0 problems=0`, commands.jsonl holds `"--expect-restarted", "egw-controller-1"`, `GATE t6: pass`. Workload `battery` = the brief's authority text, `harness_run_id` r04, `itest_run_ids` `[]`. Classify: `row t6: classified 'pass'; driver code 0; export: verified -> <bench>/out/runs/2026-10-05/…_attempt02` (package and the run directory's own `SHA256SUMS` verify; no password value in it). Close: `the recorded stop with the controller's 130 s allowance`, the stub guest received `docker compose --env-file .env --env-file images.lock.env stop -t 130`, `session S4 closed (guest_session_close.sh exit 0)`; exactly one restart reached the guest, between the before and after reads; no `up`/`start` | PASS |
| 2 | `labels` (58) | open S1/S2/S3 refused with the consumed text; open S5, open (no label); row t8/t9/t5, classify t8, term t9 refused; open S4 twice; open S4 after close | `REFUSED: session S1 is a session of the battery of 2026-10-02/03, whose authority is consumed: … This script opens S4 only: g3_battery.sh open S4` (S2 the same); `REFUSED: session S3 (tests 8 and 9, 2026-10-05) is closed and its authority is consumed: …`; `REFUSED: unknown row 't8' (S4: t6 only; the rows of S1, S2 and S3 are not run again)` (t9, t5 the same); all exit 2, no state directory created; second open: `REFUSED: a session is open (…)`; after close: `REFUSED: <bench>/egw-exec/g3-t6-s4/session-S4.env exists: session S4 was already opened …` | PASS |
| 3a–d | `fresh-a` … `fresh-d` (52 each) | r04's raw directory / r04 not in the plan (the real `c195bd3f…`) / r04 `running` / `<P>/controller_restart-r04.twins.before.json`: open halts, nothing started; open passing, row t6 halts before the attempt; a second row refused; close | open: `NOT FRESH: <bench>/home/egw-tcg/pilot/results/raw/controller_restart-r04 exists (controller_restart-r04)` / `plan entry controller_restart-r04: NOT in the plan` / `plan entry controller_restart-r04: status=running seed=1715385812 …` / `NOT FRESH: …/itest/controller_restart-r04.twins.before.json exists`, then `HALT: an id of S4 is not fresh on the host; nothing was started` (no state file, no session, no fake QEMU, no attempt). Row: the same cause line, `HALT: an id of row t6 is not fresh on the host, or an earlier attempt of the row that is not admitted exists: the row was NOT started and no attempt was created (packet section 4, halt 1)`; no row file, no attempt, no recorder, no harness, no restart, plan unchanged by the row; second row: `REFUSED: NOT STARTED: session S4 has a recorded halt (…)` | PASS ×4 |
| 3e | `fresh-e` (43) | S2's attempt01 admitted where it is kept; the same found under `runs/2026-10-04/` or `incomplete/`: NOT FRESH | `NOT FRESH: an earlier attempt of row t6 exists: <bench>/out/runs/2026-10-04/20261003T132936Z_g3-qualification-t6_attempt01` (and `…/out/incomplete/…`), halt, nothing started; restored: exactly two `admitted:` lines, no `NOT FRESH`, open passes | PASS |
| 3f | `fresh-f` (41) | another earlier t6 attempt: NOT FRESH at open and at the row | `NOT FRESH: an earlier attempt of row t6 exists: <bench>/egw-exec/attempts/20261004T120000Z_g3-qualification-t6_attempt05` (open halts); later `… <bench>/out/incomplete/…_attempt05` (row halts before the attempt) | PASS |
| 3g | `fresh-g` (38) | an attempt one level deeper under `output_test/runs` (counted by the export tool, not seen by `open`): the new attempt is attempt03, halt before any step | `HALT: row t6: the new attempt is named …_g3-qualification-t6_attempt03, which does not end '_g3-qualification-t6_attempt02' (the name the request of 2026-10-05, section 3, expects): … No step of the row was run`; no step recorded in the attempt, no harness, no restart, plan `61d55940…`, row awaits classification; classify not-applicable/not-run; close | PASS |
| 4a | `id-a` (40) | the clone's collector changed: open halts; also at the row | `HALT: collector (<bench>/repo/src/deployment/scripts/collect-resources.sh) is <64 hex>, the recorded identity is 9e678b02… (packet section 4, halt 6); nothing was started`; at the row: `HALT: collector (…) is …, the recorded identity is 9e678b02…: row t6 was NOT started and no attempt was created (packet section 4, halt 6: …)` | PASS |
| 4b | `id-b` (33) | `drivers_sha256` differs | `HALT: drivers_sha256 is not 2c209b09… (packet section 4, halt 6); nothing was started` | PASS |
| 4c | `id-c` (35) | root file system differs from `6fce1688…` | `rootfs ext4: 1111…`, `expected:    6fce1688… (the value the close of S3's second opening recorded)`, `HALT: the guest root file system is not the expected one, … nothing was started` | PASS |
| 4d, 8 | `id-d` (43) | the gate record differs from S2's (controller image id): halt before t6; a second row refused | open passes; row: `  S2:  identity egw-controller-1 image=egw-controller:0.1.0 image_id=sha256:9a293fe1…`, `HALT: the gate package's record of the running images (…container_identities.txt: 6 identity line(s)) differs from S2's … : row t6 was NOT started and no attempt was created (request of 2026-10-05, section 5 item 1: …)`; no row file, no attempt; second row: `REFUSED: NOT STARTED: session S4 has a recorded halt (… the gate package's record …)`; close | PASS |
| 5 | `pf-1`, `pf-3` (37 each) | the stub preflight's attempt ends valid/fail (driver exit 1) / failed/invalid (exit 3): HALT at open, no environment copy, no gate | the script holds 0 lines with `EXCEPTION`, 0 with `s3b_preflight_exception`, and three lines with `exception` in any case, all comments saying it was removed (7, 110, 1052); `preflight.sh exit=1` / `exit=3`, `HALT: preflight.sh exited N; see <bench>/egw-exec/g3-t6-s4/S4-preflight.console.txt`; no `## environment input`, `S4-environment-copy.txt` absent, `sut_environment.json` unchanged, no gate console, no gate attempt, no guest listing; `state=halted`, `preflight_exit=N`, one halt; `row t6` → `REFUSED: session S4 is recorded 'halted', not open`; close closes the guest | PASS ×2 |
| 6 | `out-h1` (50) | harness exit 1 | `[harness] INVALID: bench case: harness exit 1 …`, `STOP: test 6: the harness run was not sealed, or it exited 1 …`, delta and acceptance NOT called (their STOP lines name `T6='stop'`), analyze ran; no `SHA256SUMS`; plan after: `failed validity=invalid`; gate passes, no halt by the row; classify invalid/unknown → `HALT: row t6 is classified invalid instrumentation …` (classify's own) | PASS |
| 6 | `out-h2` (55) | harness exit 2 | `test 6: resources_proved_down: not read - harness_cmd answered 2, the harness was not started (…)`, `STOP: test 6: the harness run was not sealed, or it exited 2 (… 2: the harness was not started …)`; no delta, no acceptance, no raw directory, no restart, plan untouched (`planned`); **the row records a halt**: the gate's pair cannot show the expected restart of egw-controller-1 (`guest-state-delta: faults=0 problems=1`), `HALT: row t6: the gate did NOT pass (packet section 4, halt 3): guest-state-delta exit 2 …`; second row refused; classify not-applicable/not-run → `export: verified; incomplete: … 1 registered artefact(s) that were never written …` (the raw directory) and the classify halt | PASS |
| 6 | `out-h3` (53) | harness 0, the recorder's cleanup fails: `harness_cmd` 3 | `STOP: harness_cmd controller_restart-r04: the harness answered 0, and the Docker events recorder's cleanup after it FAILED …`, `STOP: test 6: the procedure is INCOMPLETE - …`; no delta, no acceptance; **the row records a halt**: `HALT: row t6: the gate did NOT pass …: a recorder or collector unit is still active (gate-units exit 3)`; classify unknown/inconclusive (no classify halt); `close` → `HALT: close: a recorder or collector unit is active (exit 3): nothing was stopped` (no stop sent, session open); the README's one prescribed restoration (the runbook's cleanup, by hand) → `close` closes | PASS |
| 6 | `out-gaveup` (47) | drain `gave-up` | `STOP: test 6: the drain gave up (manifest drain.outcome 'gave-up'): a failed recovery …`; delta and acceptance NOT called (`T6='gaveup'`); gate passes, no halt; classify valid/fail | PASS |
| 6 | `out-delta4` (48) | delta 4 | `itest_reconcile stub: delta exit=4`, `STOP: test 6: delta NOT run (T6='ok') or it exited non-zero (4 = MISMATCH)`, and line 1427 still ran: `itest_reconcile stub: acceptance exit=0` (called once); gate passes; classify valid/fail | PASS |
| 6 | `out-eo4`, `out-eo1` (48 each) | `--exactly-once` 4 / 1 | `itest_reconcile stub: acceptance exit=4` (`=1`) and `STOP: test 6: the per-identity exactly-once check was not run (T6='ok'), could not read its inputs (exit 1: test 6 NOT evaluated) or found … (exit 4: test 6 FAILS)`; delta 0; gate passes; classify valid/fail (eo4), invalid/unknown (eo1, a classify halt) | PASS ×2 |
| 7 | `term` (47) | `term t6` while the harness stand-in sleeps | the stand-in is in the row's group, the fake QEMU is not; `TERM sent to the process group N (exit 0). KILL is never sent.`, no halt of `term`; the row ended ~1 s later: `row t6: interrupted by a signal (TERM)`, `HALT: row t6 was interrupted by a signal (TERM) during 't6' …`, `DRIVER RESULT …_attempt02: exit=130 (interrupted: marked interrupted and exported) … capture_failures=2`, `row t6: attempt finished 'interrupted'; driver code 130; export: verified -> …`; `attempt.json` status `interrupted`; the fake QEMU the same pid and start tick; the host's keepalive client (pid 400) the same pid, start tick and command; **finding F1**: the recorder unit left active, `close` halts on it and stops nothing (section 4); after the bench's own cleanup, close closes | PASS (with F1) |
| 8 | `afterhalt` (47); also `id-d`, `fresh-a…d`, `out-h2` | a halt inside the row; a second row refused; classify; close | `HALT: row t6: the new attempt is named …_attempt03 …`; `row t6` → `REFUSED: row t6 was already started (…/row-t6.env): a row is run once, never repeated`; `status` shows the HALT; classify not-applicable/not-run → `HALT: row t6 is classified not started …`, `Next: 'close', then hand back to Rui: …`; `row t6` refused again; `close` → closed; `open S4` → refused (`session-S4.env exists`). The halts before the attempt (id-d, fresh-a…d) refuse the second row with `REFUSED: NOT STARTED: session S4 has a recorded halt (…)` | PASS |
| 9 | `integrity` (67) | with `EGW_G3_ROWS` naming a byte-identical copy of `P/rows`: t6.sh changed at open; then the script, the manifest, t6.sh changed while open | open: `STOP: t6.sh: sha256 … is not the manifest sha256_after ec8ac010…`, `HALT: the row files of t6 are not the manifest's; nothing was started`; open (restored) passes; (a) a changed copy of the script: `REFUSED: this steps script is not the one session S4 was opened with (sha256 7a63b361…)`; (b) the manifest: `REFUSED: rows.manifest.json is not the one session S4 was opened with`; (c) t6.sh: `HALT: the row files of t6 are not the manifest's: the row was NOT started and no attempt was created`; (d) restored: `REFUSED: NOT STARTED: session S4 has a recorded halt …`; nothing started in any; close | PASS |

Where a halt is recorded, and by whom (scenario 6): the **row** records one only in `out-h2` (the gate: the expected
restart is not shown when the harness never started) and in `out-h3` (the gate: the recorder unit still active);
**classify** records one for invalid/unknown (`out-h1`, `out-eo1`) and not-applicable/not-run (`out-h2`); `out-gaveup`,
`out-delta4` and `out-eo4` record none (their outcome is the operator's classification). In every outcome the row
ends `awaiting-classification`, and the step's own status is 0 (line 1428's analyze), never a verdict.

## 4. Findings, defects, corrections

**No defect of `P/g3_battery.sh` was shown by a bench; nothing was corrected; the script's sha256 is unchanged.** The
bench's own scripts were corrected during the trials (none of these is a defect of the operator script): the ssh log
also holds the module stub clone's `capture [...]`/`fetch [...]` lines (the start/up count now leaves them out); the
package check named the run directory's own `manifest.json` exactly; the keepalive comparison in `term` uses the start
tick of `/proc/PID/stat` (the `ps lstart` of the same process moved by 9 s between two readings, as WSL steps its wall
clock); the export line of `out-h2` is `verified; incomplete: …` (the never-written raw directory), now expected; a
listing was cut before it was masked. The consoles of the two earlier full runs on the same script bytes (19:47Z and
19:52Z, all 25 PASS) are in `record/superseded/` (two cut paths masked there afterwards); the first trials' logs stay
in `/tmp/g3-s4-bench/_logs/`.

**F1 — `term t6` during the harness leaves the recorder unit running (not corrected; decision needed).**
- *What the bench showed* (`term`, `record/term.console.txt`; two trial runs, `record/superseded/term.*`): `cmd_term`
  sends TERM to the row's whole process group (`g3_battery.sh` line 2046), as the request specifies (section 4: "the row
  receives TERM to its process group"). That group holds `local_export exec`, the python process that owns the step's
  console pipes, which dies at once (no SIGTERM handler; `capture_failures=2`, the step `t6` never reaches
  `commands.jsonl`). `harness_cmd`'s subshell survives the TERM by its trap, but everything it writes afterwards goes
  into those closed pipes and it is killed by SIGPIPE at its first write: in a trial run before it called `events_cleanup`
  (no `capture [cleanup]`; `/tmp/g3-s4-bench/_logs/try-term.txt`), in the three recorded runs after it (the cleanup was called and its child died at its first write, before it marked the unit stopped). Either way the unit
  `egw-events-controller_restart-r04` stays **active**, and `close` then halts: `HALT: close: a recorder or collector
  unit is active (exit 3): nothing was stopped`. The trap's own line `harness_cmd …: interrupted` never reaches the
  attempt. The mechanism alone is shown by `bs4_sigpipe.sh` (`record/sigpipe.console.txt`): the same chain, the cleanup
  stand-in runs only when SIGPIPE is ignored in the step shell.
- *Why it matters in S4*: the README's close table prescribes the runbook's cleanup only for
  `egw-events-controller_restart-r04` *after `T6=incomplete`*; after a `term` it says "no prescribed cleanup in S4 …
  hand back to Rui". So a row that reaches its 47 min ceiling while the harness runs cannot be closed by the operator
  alone; the guest stays up with the recorder running until Rui decides. The failure mode is safe (nothing is stopped
  or forced; QEMU untouched). The real harness also dies at the TERM (`run.py` installs no SIGTERM handler), so its
  collector unit `egw-resources-controller_restart-r04` may be active too until its own `--duration` ends it (not
  benched: the stand-in starts no collector).
- *Remedy shown on a copy* (`term-pipe-exp`, an EXPERIMENT, NOT the script under test; its console names the copy's
  sha256): the same `term` on a copy whose `STEP_PRE` begins `trap "" PIPE;` (two diff lines): `harness_cmd`'s own
  cleanup ran and stopped the unit (`unit=inactive`), and `close` closed with no restoration.
- *Why not applied*: (1) the request's section 4 specifies TERM to the process group, `term` is among what point 9 of
  the brief keeps unchanged "beyond what S4 needs", and the step shell (`STEP_PRE`) is the one the three earlier
  sessions ran (hard rule 7: change what S4 needs, nothing else); (2) ignoring SIGPIPE changes the environment
  of the measured block's every process on the normal path too (the hooks the harness runs get SIGPIPE back from
  python's `subprocess`, but `ssh`, `scp` and the bash helpers the step runs directly would inherit it), which no
  guest has run; (3) the path is the ceiling path (expected row 20–25 min against 47) and fails safe. The decision is
  Rui's (or the operator stream's for the README): either the one-line `STEP_PRE` change (then every scenario re-run),
  or a README entry for `close` after `term t6` naming `egw-events-controller_restart-r04` (and possibly
  `egw-resources-controller_restart-r04`) with the runbook's own cleanup, or the hand-back as it stands.
- *Resolution in the preparation (2026-10-05, after this bench; documents only, the script unchanged)*: the README entry.
  `g3_battery.README.md` (the `close` row and "What is unverified"), `operator-procedure.md` (controlled close, item 2)
  and the request (section 4) now prescribe, after `term t6`, the runbook's own recorder cleanup of
  `egw-events-controller_restart-r04` through `hx` on the session's attempt, three tries at most, recorded, then `close`
  again; the collector unit ends by itself at its 600 s bound; any other unit is handed back. `fixes-record/fix_bench1.py`.

**Observations (no change needed):**
- O1 — The merged `run.update_plan_status` rewrites only r04's lines of the plan (diff of the snapshots in `pass`: four
  lines — `status`, `validity`, `result_dir`, `finished_utc`); the other 95 entries are byte-identical; the plan after
  the row is not `61d55940…` (as the operator notes say).
- O2 — A harness that never starts (`out-h2`) also fails the gate, because `--expect-restarted egw-controller-1`
  demands a restart the pair cannot show (`PROBLEM`, exit 2): the classification is by cause (not started), the halt is
  the gate's. This is the battery's design and the README's gate line lists it.
- O3 — Line 1425's carriers are passed empty to the drain hook and read as the runbook's defaults (130/5/900), shown on
  the real hook in `pass`.
- O4 — The interrupted attempt of `term` is `instrumentation_validity=invalid` with two capture failures (the step's
  console); it is exported and verified.

## 5. What was NOT benched, and why

- The real harness (`run.py`: the simulator workload, the collector start/stop/fetch hooks, the restart at +300 s
  timing, the transition rule's own computation of `resources_transition_rows`, `resources_proved_down`, the manifest's
  validity reasons), the real `analyze`, and the real `itest_reconcile delta` and `acceptance --exactly-once` (their
  verdicts on files): stand-ins or stubs return the case's codes and files. `fetch_started_at.sh` was not run (the
  stand-in does not run the `--fetch-started-at-cmd` hook).
- The frozen session drivers (the stack start, the collector's install, `collector-duration` on the uptime bounds, the
  real gate): stubs. Their exit statuses through the frozen `driver_status.py` were real.
- Anything on a guest: ssh, docker, systemd units, Docker events (the module's stubs), the tunnel's real ssh master.
- The 47 min ceiling and the 3 h cut-off as times (unchanged code; `term` was sent by the bench); the keepalive's
  absence or shortness (a synthetic client is always present, as in S3b); a WSL restart; a lost tunnel; a guest not
  answering (97) at the gate or at `close`; `close` with no QEMU left; `close` outside the script (`EGW_G3_RUI_GO`);
  a row whose process died without its trap (`local_export recover`); an export failure; step statuses 97 and 74 —
  all code paths unchanged from S3b's script (S4's diff does not touch them) and benched there or in the battery.
- The data disk header after the close (the bench's disk is a text file: `dumpe2fs` cannot read it, as the console
  says); the Windows keep-awake.
- `term t6` on the real harness, and the collector unit after a term (F1).

## 6. Untouchedness (`record/untouched.before.console.txt`, `record/untouched.after.console.txt`)

Taken before any bench (marker 2026-10-05T19:26:02Z) and after the last one (2026-10-05T20:03:32Z), with the real `HOME`,
read-only (`bs4_untouched.sh`; it writes only under `/tmp/g3-s4-bench/_untouched`):
- `~/egw-exec` and `~/egw-tcg`: 19,216 entries, listing (path, modification time, size) sha256 `a3ab5c41…` before and
  after, **identical**; 0 entries newer than the marker; the clone's HEAD `8e492613…` unchanged;
- **the plan `~/egw-tcg/pilot/campaign_plan.json` sha256 `c195bd3faa9607aae7c091b1e7e59b451b74afe484fa179cfa2aad7af8f28a60`
  before and after**; `~/egw-exec/g3-t6-s4`, `~/egw-exec/current_session` and the raw directory of r04 absent; the only
  t6 attempt in `~/egw-exec/attempts` is S2's attempt01;
- `output_test`: 6,266 entries, listing sha256 `87633ddc…` before and after, **identical**; 0 entries newer;
- no process naming `/tmp/g3-s4-bench` left, no `qemu-system-aarch64` process and no fake QEMU loop on the host; the
  host's keepalive client (pid 400, `sleep 43200`, not started or ended by this stream) still running; no new entry in `/tmp`.

Read, not written, outside the bench: the worktree `<S>/t6m` (copied by `bs4_src.sh`), the real plan (copied once per
bench) and S3's sealed gate record `output_test/runs/2026-10-05/20261005T115022Z_g2-gate-preconditions_attempt07/
environment/container_identities.txt` (`a713c8ba…`, copied per bench). Every bench file and console is LF-only, UTF-8;
no console holds the bench's password value.
