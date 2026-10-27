# Stream BENCH — notes (2026-10-04; re-run on the corrected script 2026-10-05; times in UTC)

`S`, `P` and `OT` are the brief's three directories. Everything here ran offline in WSL (Ubuntu-24.04, bash 5.2.21,
coreutils 9.4): no guest, no QEMU, no docker, no real ssh, no build. Each scenario has a bench of its own under
`/tmp/g3-s3-bench/<scenario>`, with `HOME` and every `EGW_*` variable inside it. The first pass ran on 2026-10-04
(22:09Z–23:24Z) on `142a5aad…`. After a bounded review corrected the script (O1 to O4 below), every scenario was run
again on 2026-10-05 (09:01Z–09:31:16Z) on the corrected bytes `6009da1e…`, and six scenarios were added. That re-run
showed one defect of the correction (D1, section 3); it was corrected in the script (final bytes `a77bd201…`) and every
scenario was run once more, 09:34:38Z–09:51:37Z, by `bench/bs3_final_pass.sh` (its output:
`bench/record/final-pass.driver.txt`). This note describes those two passes; every earlier console is kept under
`bench/record/superseded/`.

What the bounded check of 2026-10-05 changed in `P/g3_battery.sh` (each place carries a comment `bounded check of
2026-10-05`):

- **O1** `cmd_row` (line 1686): a recorded halt of S3 refuses every further row; `EGW_G3_RUI_GO` no longer lets a row
  start after a halt (it is still read by `close` for a session closed outside the script).
- **O2** a line `TUNNEL UP` printed by the preamble of `hx` is a restoration and a halt: (a) `gate_after`, in the
  console of `gate-tunnel-check`, adds a gate failure (line 1572); (b) `steps_t8`, in the console of `t8-e-state`
  (line 1421) or `t8-f-smoke` (line 1441); (c) `steps_t9`, in the console of any step (line 1486). Steps b and c of T8
  are excluded on purpose (their preamble reopens the tunnel the reboot killed), and so is step d (its own line prints
  `TUNNEL UP`).
- **O3** `cmd_classify`: a row classified `invalid instrumentation` records a halt (line 1918; before, a NOTE only).
- **O4** the README's text.

## Result

- **Final bytes: `P/g3_battery.sh` sha256 `a77bd201a54d02620e625a620d2da796a8834289ec67daa808ed15324950f5cb`.**
  The bench stream did not edit the script; D1 was corrected after its re-run, by the preparation's owner, in one place
  (`cmd_classify`: a halt of classify's own now prints `Next: 'close', then hand back to Rui: …` before exit 1), and the
  README's table of halts names the new halt.
- **Final pass on those bytes: 38 scenarios, 38 PASS, 0 checks failed** (`bench/record/<scenario>.console.txt`;
  `bench/record/final-pass.driver.txt`). s18 now passes (`Next: 'close', then hand back to Rui: session S3 has a
  recorded halt, and no further row starts.`).
- **The re-run on `6009da1e…` (09:14Z–09:31Z) gave 37 PASS, 1 FAIL (833 checks, 1 failed)**; its consoles are under
  `record/superseded/`. The defect it showed (section 3, D1): since O3, `classify <row> failed invalid
  unknown` records its halt and ends with exit 1 BEFORE the line that names `close` as the next step; when the row's
  gate passed, that invocation names no next step at all (s18; the same ending is recorded, not checked, in s2vii and
  s7iii; in s12, whose gate failed, the gate's NOTE still says `'close' and hand back to Rui`). The halt itself is
  recorded and honoured: `row t9` is refused and `close` closes. No wrong halt, no missed halt, no false pass was
  seen.
- **Expectations changed because of O1 to O3: s12, s2vii and s7iii** (each classifies row t8 `failed invalid unknown`,
  which is now a halt of classify's own). No other existing scenario's expected behaviour changed: none lost the
  tunnel after line d (so none expected `GATE t8: pass` with the tunnel NOTE; s1b loses it at the reboot, before line
  d, where O2 does not apply), and none set `EGW_G3_RUI_GO`. No expectation was weakened.
- **No keepalive client of wsl.exe ran on the host this morning** (the `sleep 43200` the first pass found had ended;
  the distribution had stopped before 09:00Z), and this stream neither started nor ended one. The script's own
  keepalive check therefore refused `open S3` in the first attempt (09:09Z: every scenario `REFUSED: the keepalive
  client is not attached (see above); nothing was started`; those consoles are under `record/superseded/`). In the
  re-run the check is answered inside each bench by a `ps` stub that adds a SYNTHETIC client: no process (section 1).
- Every scenario ran on the **real step files of `P/rows`**, read in place (manifest `678b9203…`); the helpers come
  from the helper file written by the runbook's own heredoc (`e5eba37e…`, 545 lines); the commands they call are the
  stubs of the repository's test module, imported from it.
- s1 and s2iii ran on the **final bytes in real time** (the helper's 130 s quiet windows, the host's own `sleep` and
  `timeout`); the 36 others on the short variant `c9adaf5f…` made from them.
- A keepalive client of wsl.exe was started again before the final pass (pid 272); the `ps` stub of each bench still
  answers the script's keepalive check inside the bench.
- The real `~/egw-exec` and `~/egw-tcg`: the listing (18,690 entries: path, modification time, size) is
  **identical** before and after the final pass (`untouched.after.console.txt`, 09:51:37Z), with the same sha256,
  `4ca11377…`, as at this stream's start (09:01:50Z); 0 entries are newer than the marker; the clone's HEAD is
  `8e492613…` before and after; no `/tmp/wrong.key` or `.crt`, no S3 state directory, no bench or QEMU process.

## 1. The bench

Scripts (in `bench/`): `bs3_setup.sh` builds one bench; `bs3_stubs.py` imports the test module; `bs3_env.sh` is the
environment; `bs3_run.sh <scenario>` runs one scenario and prints its console, which starts with the sha256 of the
script run, states what is expected, quotes the decisive lines, and ends `SCENARIO <name>: PASS|FAIL (n checks)`;
`bs3_all.sh` runs several side by side; `bs3_short.sh` makes the short-timing variant; `bs3_sent.sh` (added
2026-10-05) reads afterwards, from each bench, what went to the stub guest; `bs3_untouched.sh` is the before/after
look at the real trees.

**Real in every bench:** the six step files of test 8 and the five of test 9 as `rows/` holds them; the helper file
and `tunnel.sh`, written with `HOME` in the bench by the runbook's own heredocs (the module's `helpers_heredoc` and
`tunnel_heredoc`) and compared with the recorded sha256; a copy of `tools/` and `src/egw_experiments` of the worktree
`S/pb` (the merged tree), so the frozen `common.sh`, `guest_common.sh`, `guest/session_common.sh`, `nominal.sh`,
`guest_state_delta.py`, `driver_status.py` and `local_export.py`; the runbook blob as the clone's runbook (hashed
for real: `4acf8de6…`); bash, `flock`, `ps` (except the one question below), the real `pgrep -g`; and the execution
venv's python (read-only, no bytecode).

**From the test module** (`src/tests/test_runbook_itest_helpers.py`, sha256 asserted `fe8baa60…`, imported, not
copied): `STUB_SSH`, `STUB_CURL`, `STUB_PYTHON`, `STUB_SCP`, `STUB_SS`, `STUB_SLEEP`, `STUB_TIMEOUT`,
`STUB_FETCH_SUT_LOG`, installed by its own `Bench` class; the stub guest's state from its `t8_prepare` (boot ids
`aaaaaaaa-…a` / `bbbbbbbb-…b`, six container ids, three event directories, `/dev/vdb`, a controller that is a new
process after the reboot), and its `full_run` for the smoke under the S3 run id. A scenario changes the outcome
through the module's own state files (`guest_never_answers`, `boot_id_then_stall_calls`, `containers.post`,
`events.post`, `rec_same_rc`, `master_alive`, `master_open_fails`, …).

**Added by the bench, because the module does not hold them** (each says so in its own text):

| Bench piece | What it stands for |
|---|---|
| a bash loop named `qemu-system-aarch64` (real `/proc/PID/cmdline` and `stat`) and a `pgrep` stub that names it | QEMU. It is started by the stub open driver and ended by the stub close driver or by the bench; the script never signalled it in any scenario |
| four stub session drivers in the COPY (`guest_session_open`, `preflight`, `gate_health`, `guest_session_close`) | the frozen drivers, which need a guest. The copy's drivers were hashed before they were replaced: `4a6a572d…`, the recorded `drivers_sha256`; in the bench that stream is answered by the `sha256sum` stub |
| `sha256sum` and `git` stubs | the recorded values for the kernel, `qemuboot.conf`, the QEMU binary, the root file system, a placeholder `ca.crt` and the two checkouts (a flag file makes one differ); every other file is hashed for real |
| a wrapper of `ssh` | canned answers for the steps script's OWN guest reads (the open's listing, the gate's guest state, the healthy wait, the units, the close's stop, the previous boot's journal) and for test 9's probe and its two exposure reads; every other call goes to the module's `STUB_SSH` unchanged. These answers stop (255) when the case says the guest is gone |
| a wrapper of `scp` | the evidence directory of test 9 (d)+(e); every other call goes to the module's `STUB_SCP` |
| a stub `openssl` | test 9(a) writes a key and a certificate at fixed paths under `/tmp`, outside the bench: the stub logs the call and writes nothing |
| a bench venv (`activate`, `python`, `python3`) | `python -m egw_simulator` and `-m egw_experiments.itest_reconcile` go to the module's `STUB_PYTHON`; everything else (the script's `$PY`, the export tool, the row files' `python3`) to the execution venv's real python |
| **a `ps` stub (added 2026-10-05)** | the keepalive client of wsl.exe that `keepalive_check` (`open`, `row`, `close`) looks for: an `exec sleep N` whose parent's name starts `Relay`. For that one question (`ps -eo pid=,ppid=,args=`) a synthetic line `4194301 4194300 sleep 43200` is ADDED to the real listing, and the two follow-up reads are answered (its elapsed time, counted from the bench's setup plus 60 s; its parent's name `Relay(bench)`). No process is started and nothing outside the bench's `PATH` sees the line; if either pid exists, nothing is added. Every other `ps` call is the real one. Each console says so at its top (`bench keepalive: …`, with the count of `sleep N` processes of 3,600 s or more on the host: 0) and shows the script's own line, for example `keepalive: pid 4194301 'sleep 43200', parent 4194300 (Relay(bench)), running for 61 s, about 43139 s left` |
| **a hook in the bench venv's `python` (added 2026-10-05)** | `bench_hook.exec.<step>`: a shell fragment sourced once, just before the export tool records the step `<step>` (`local_export exec --name <step>`), renamed `….done` and logged in `<bench>/hooks.log`. s14 to s17 use it to end the host's tunnel master between two recorded steps with the module's own mechanism (`master_alive` removed, the control socket left behind, stale), as s1b's reboot hook does at the reboot |

**Switches, stated at the top of every console:**

- *The short-timing variant* (`bench/g3_battery.short.sh`, sha256 `1fe0f20e2dbe1269d64b5de093fae835cda3fce354698666ce28a352d1f2a858`,
  made at 09:09:18Z by `bs3_short.sh` from the final bytes): the final bytes with two lines changed,
  `T8_SSH_WAIT_S` 900 → 48 and `T8_SSH_POLL_S` 10 → 3 (lines 99 and 100; `record/short-variant.txt` holds the diff).
  `T8_SSH_READ_S=20` is the final value. Used by every scenario except s1 and s2iii; `bs3_run.sh` refuses a variant
  that differs from the final bytes in other than two lines.
- *`BENCH_FAST_DRAIN=1`*: a bench device, in every scenario except s1 and s2iii. The script unsets `DRAIN_QUIET_S`
  in every step shell, so each `drained` of the helper waits 130 s of `/proc/uptime`; with the device the bench venv's
  `activate` makes `DRAIN_QUIET_S` and `DRAIN_STEP_S` read-only at 0 (the values the repository's own tests give
  them). It is visible in every step console of those scenarios: two lines `unset: DRAIN_QUIET_S: cannot unset:
  readonly variable` and `carriers after the unset: … DRAIN_QUIET_S=0 DRAIN_STEP_S=0 …`.
- *`BENCH_SCALED=1`*: the module's `STUB_SLEEP` (50 ms for each second) and `STUB_TIMEOUT` (real time) on `PATH`,
  in s5b and s5c only, where a runbook line makes its 90 reads 10 s apart. Everywhere else the host's own `sleep`
  and `timeout` are used, so that the script's wait and the lines' `timeout 20` run in real time.

**What changed in the bench scripts on 2026-10-05:** `bs3_setup.sh`: the `ps` stub and the exec hook above.
`bs3_run.sh`: the six scenarios s13 to s18; the scenario part of the file is one `{ … }` group, which bash reads whole
before running it (an edit of the file while s2iii runs cannot change what it executes); helpers `halts`,
`classify_invalid` (O3), `hook_exec`, `hook_ran`, `reopened_in`, `sim_calls`; `t9_refused` takes an optional pattern
of the halt the refusal must quote; the console keeps the script's keepalive lines and states the synthetic client;
s1 checks the keepalive line of `open`; s12, s2vii and s7iii call `classify_invalid` (section 2). `bs3_sent.sh` is
new (the table it prints was made by hand in the first pass). `bs3_env.sh`, `bs3_stubs.py`, `bs3_all.sh`,
`bs3_short.sh` and `bs3_untouched.sh` are unchanged.

## 2. The scenarios

"Script": F = the final bytes `6009da1e…`; S = the short variant `1fe0f20e…`. Quoted lines are from the consoles.
In every scenario that halts row t8, `row t9` was then tried and answered `REFUSED: NOT STARTED: session S3 has a
recorded halt (…). In S3 a halt ends the session (decision summary, choice 2; request, section 5): classify the row
if it awaits classification, then 'close', then hand back to Rui`, exit 2, with no attempt of t9 created. The checks
`commands that start, restart or bring up anything, sent to the stub guest: 0` (the module's own pattern, over every
ssh call of the bench) and `pkill or killall calls: 0` are in the consoles of 25 scenarios (s1, s1b, s17 and every
one in which row t8 halts after a recorded step or is interrupted). For all 38 benches the same
counts were read afterwards from each bench's own logs (`record/sent-to-guest.all.txt`, by `bs3_sent.sh`): 0 and 0
everywhere; one reboot command where line a ran and none elsewhere (s3, s5a, s8a, s8b, s8c, s9); the only `compose`
commands are the close's `stop` (the script's `stop -t 130` and the stub close driver's own: 2; 1 in s4b, where no
QEMU was left; 0 in s2iii and s5b, where the guest was gone, and in s8a, never opened). The table's second column,
headed "ssh calls logged", counts LINES of each bench's `ssh.log` (an argument that holds a script of several lines
continues on the next lines), not calls, so it is not comparable with the first pass's counts. `bs3_sent.sh` was then
corrected to count calls (lines starting `ssh [`; its sha256 in section 8 is the corrected one), but the table could
not be made again: the distribution restarted right after the pass and `/tmp` was emptied with it.

| # | Scenario (script) | What was run and expected | Observed (decisive lines) | Result |
|---|---|---|---|---|
| 1 | **s1** success (F, real time, 09:14:18Z–09:23:37Z) | `open S3`, `row t8`, `classify`, `row t9`, `classify`, `close`; every marker, no halt | `keepalive: pid 4194301 'sleep 43200', parent 4194300 (Relay(bench)), running for 61 s, …` (the synthetic client); `admitted: the one earlier attempt of row t8 …` twice (attempts directory, output root); `QEMU COMMAND LINE: no -no-reboot …`; three `drained: … 27 consecutive readings over 130 s` in row t8 and one in row t9; polls at +0, +10, +20 s: 255, 255, then `poll 3 … exit status 0 and the answer is the boot id bbbbbbbb-…`; `QEMU PROCESS UNCHANGED`; `REBOOT SHOWN: boot id aaaaaaaa-… -> bbbbbbbb-…`; `CONTAINERS RETURNED UNAIDED`; `PERSISTENCE SHOWN: 3 event directories intact; /var/lib/docker on /dev/vdb`; `CONTROLLER PROCESS NEW`; `TEST STATUS itest-post-reboot-01-q2: … -> PROCEDURE COMPLETE.`; `GATE t8: pass`; attempt `…_g3-qualification-t8_attempt02`; row t8 427 s. Row t9: steps `t9-a t9-b t9-c t9-de t9-exposure`, `exit=1` three times, `probe exit=0`, `controller untouched by the probe`, `root ssh exit=255`, `ss exit=0`, `docker ps exit=0`, `GATE t9: pass`, attempt `…_t9_attempt01`, 133 s. `session S3 closed`. Both rows `export: verified`. Carriers `<unset>` in the step shell | PASS (42) |
| 1 | **s1b** added (S) | the same pass with the host's tunnel master ending at the reboot (in the other scenarios the stub's master outlives it) | step b's console: `tunnel: connection refused on … - stale socket file removed`, `TUNNEL UP` (the preamble), then `REBOOT SHOWN`; step d: `TUNNEL CLOSED`, `TUNNEL UP`; a to f, no halt; `GATE t8: pass` (the tunnel was reopened before line d, where O2 does not apply) | PASS (24) |
| 2(i) | **s2i** (S) | a poll prints the new id, then stalls: 124, not counted; the next counts | `poll 3 at +27 s (bounded to 20 s): NOT counted - it printed the boot id bbbbbbbb-…, other than the saved one, and then ended with exit status 124: a read that does not end with exit status 0 is no answer whatever it printed (kept as a diagnostic: …/006-t8-wait-ssh.stdout.txt)`; `poll 4 at +30 s (bounded to 18 s): exit status 0 and the answer is the boot id bbbbbbbb-…`; the row goes on to f, no halt | PASS (22) |
| 2(ii) | **s2ii** (S) | the same with 255 | `poll 3 at +7 s … NOT counted - it printed the boot id bbbbbbbb-… and then ended with exit status 255`; `poll 4 at +10 s … exit status 0 and the answer is the boot id …` | PASS (22) |
| 2(iii) | **s2iii** expiry on the final constants (F, real time, 09:14:18Z–09:31:15Z) | the guest never answers: one poll every 10 s for 900 s, then the halt; b to f not run; `close` halts | 90 polls, all `no answer (exit status 255 …)`, all run by `timeout`: 88 with `timeout 20`, then `poll 89 at +889 s (bounded to 12 s)`, `poll 90 at +899 s (bounded to 1 s)`; step a ended at up=266, the halt at up=1166: 900 s; `HALT: row t8: reboot not shown within the wait: in the 900 s after step a ended, none of the 90 poll(s) … (90 ended with another status - no answer, whatever they printed; …) … An operational cut-off: inconclusive / not demonstrated, not by itself a failure of the system … Line b was NOT run, nor steps c to f, and T9 is not run. QEMU was NOT signalled …`; `QEMU PROCESS UNCHANGED`; `start_up` recorded once, ceiling 135; the gate fails (97); then `HALT: close: the guest did not answer (exit 97) although a qemu-system-aarch64 process is running … nothing was stopped`, the fake QEMU still the same process | PASS (26) |
| 2(iv) | **s2iv** (S) | every answering poll stalls; with less than 20 s left the bound is the remainder | four polls bounded `20, 20, 20, 18` s (`timeout 18` on the last: 18 s were left); both stalled polls `NOT counted … exit status 124`; expiry 48 s after step a ended. Smaller remainders in other consoles: `timeout 1` (s2v), `timeout 3` (s2vi), `timeout 12` and `timeout 1` (s2iii); never 0 | PASS (21) |
| 2 | **s2v** added (S) | every poll ends 0 with the SAVED id | 16 polls `the guest answers with the boot id aaaaaaaa-…, the saved pre-reboot id: it has not gone down yet, or did not reboot - waiting on`; bounds `20 16 13 10 7 4 1`; halt `(0 ended with another status …; 16 answered the saved id; 0 ended 0 without one boot id …)` | PASS (17) |
| 2 | **s2vi** added (S) | every poll ends 0 with a banner line | 15 polls `exit status 0, but the answer is not one boot id of the kernel's form (…) - NOT counted, waiting on`; bounds `20 19 16 13 10 7 3`; halt `(…; 0 answered the saved id; 15 ended 0 without one boot id as the answer)` | PASS (17) |
| 2 | **s2vii** added (S); **expectation changed (O3)** | a poll whose status is 74 (see "Not benched", item 3); then `classify t8 failed invalid unknown` | `HALT: row t8: poll 3 of the wait answered 74: its console capture was lost, so what the guest answered is not on record (invalid instrumentation …). Line b was NOT run …`, although that poll had printed the new id. Classify: exit 1, `row t8: classified 'invalid instrumentation'; driver code 3; export: verified`, `HALT: row t8 is classified invalid instrumentation (request, section 5 item 2; decision summary, choice 2): no further row of S3 starts`, one more halt recorded; the refusal of `row t9` now quotes that halt | PASS (21) |
| 3 | **s3** (S) | `-no-reboot` on the fake QEMU's command line | `STOP: -no-reboot (or its equivalent) is on the command line of the QEMU process …, as argument number:text 15:-no-reboot …`; `HALT: row t8: -no-reboot … Step a was NOT run: the reboot was NOT issued (class: not started …`; steps `guest-state-before t8-qemu-before` then the gate; 0 reboot commands; no pre-reboot file | PASS (18) |
| 4 | **s4a** (S) | another QEMU process after the wait (the bench ends the first and starts a second during the reboot) | `STOP: the qemu-system-aarch64 process is not the one recorded before step a (before: pid=… start=…; now: pid=… start=…)`; `HALT: row t8: the qemu-system-aarch64 process after the wait is not the one recorded before step a, or none could be shown (t8-qemu-after exit 1 …) … steps b to f were NOT run`; steps end `t8-wait-ssh x3 t8-qemu-after` then the gate | PASS (15) |
| 4 | **s4b** (S) | no QEMU process after the wait | `STOP: no qemu-system-aarch64 process (pgrep exit 1) … nothing is re-launched by this script`; the same halt; `close`: `HALT: close S3: no qemu-system-aarch64 process is left …`, then the close driver alone, `session S3 closed` | PASS (16) |
| 5a | **s5a** (S) | five running containers before the reboot | step a: `STOP: test 8: no pre-reboot /metrics reading … not six running containers … - the guest was NOT rebooted`; `HALT: row t8: step a printed STOP: …`; no wait, 0 reboot commands. Step a's console holds `STOP:` on 2 lines, 1 at the start of a line (the other is the file's own comment, echoed by `set -v`): only the anchored one counts, and in s1 the same console gives no halt | PASS (17) |
| 5b | **s5b** (S, scaled pauses) | the guest dies after the wait counted a poll | step b: `STOP: test 8: reboot NOT shown - the guest never answered a boot id read that ended with exit status 0 in 90 reads …`; `HALT: row t8: step b does not show REBOOT SHOWN with no STOP: …`; no step c; the gate fails too (97); `close`: the 97 halt, QEMU untouched | PASS (18) |
| 5c | **s5c** (S, scaled pauses) | five of the six containers return | step c: `STOP: test 8: the containers did NOT return unaided within 90 reads …`; `HALT: row t8: step c does not show both … - a STOP: line was printed (or the step left no console); no line CONTAINERS RETURNED UNAIDED; no line PERSISTENCE SHOWN …`; no step d | PASS (16) |
| 5d | **s5d** (S) | the tunnel cannot be reopened at line d | step d: `TUNNEL CLOSED`, `STOP: ssh exited non-zero - the tunnel was NOT opened`, `STOP: test 8: tunnel NOT reopened …`; `HALT: row t8: step d printed STOP: (tunnel NOT reopened …): steps e and f were NOT run`; no `t8-tunnel-check`; the gate: `tunnel_check through hx ended 97` | PASS (16) |
| 5e | **s5e** (S) | the twins differ (`same` exits 4) | step e: `STOP: test 8: persistence across the reboot NOT verified …`; `HALT: row t8: step e printed STOP: … step f, the post-reboot smoke, was NOT run`; 0 simulator calls | PASS (16) |
| 6 | **s6** (S) | one event directory missing after the reboot | step c: `CONTAINERS RETURNED UNAIDED: …`, then `STOP: test 8: persistence NOT shown - 1 of the 3 event directories … are NOT listed after it: itest-ev-01`; no line starts with `PERSISTENCE SHOWN` (the text stands once in the console, inside the echoed line); `HALT: … - a STOP: line was printed (or the step left no console); no line PERSISTENCE SHOWN …` (the container marker is not named as missing); no step d | PASS (19) |
| 7(i) | **s7i** (S) | the smoke completes with `lost` 3 and `late_confirmations` 41 | step f: `  "lost": 3,`, `  "late_confirmations": 41,`, `TEST STATUS itest-post-reboot-01-q2: … -> PROCEDURE COMPLETE.`; `row t8: step f shows … and no STOP: - this script records no halt for the smoke. That is NOT a verdict …`; `classify t8 failed valid fail`: `classified 'valid SUT failure'`, 0 halts recorded; `row t9` then starts and runs all five steps, `GATE t9: pass` | PASS (39) |
| 7(ii) | **s7ii** (S) | the smoke's post-processing fails | `STOP: finish itest-post-reboot-01-q2: check exit=3 …`, `STOP: TEST STATUS itest-post-reboot-01-q2: … post=1 -> FAILED …`; `HALT: row t8: step f, the post-reboot smoke itest-post-reboot-01-q2, printed STOP: … T9 is not run` | PASS (16) |
| 7(iii) | **s7iii** (S); **expectation changed (O3)** | neither line: the step shell is ended when the simulator starts (the real line f always prints one of the two; a shell that dies is the one way to neither); then `classify t8 failed invalid unknown` | step f status 137, 0 lines starting `STOP:`, 0 starting `TEST STATUS`; `HALT: row t8: step f printed no STOP: but its console does not show the line 'TEST STATUS itest-post-reboot-01-q2: ... -> PROCEDURE COMPLETE' …`. Classify: exit 1, `HALT: row t8 is classified invalid instrumentation …: no further row of S3 starts`, one more halt recorded | PASS (20) |
| 8 | **s8a** (S) | the kernel's sha256 differs at `open` | `HALT: kernel (…/Image-qemuarm64.bin) is 0000…, the recorded identity is 4457ef38… (packet section 4, halt 6); nothing was started`; no state file, no session, no fake QEMU started | PASS (7) |
| 8 | **s8b** (S) | the gate's record differs from S2's (the controller's image id) | `open S3` passes; `row t8`: `  now: identity egw-controller-1 … image_id=sha256:0a293fe1…`, `HALT: the gate package's record of the running images (… 6 identity line(s)) differs from S2's …: row t8 was NOT started and no attempt was created`; `row t9`: `REFUSED: the previous row t8 is 'not started', not classified` | PASS (13) |
| 8 | **s8c** added (S) | the QEMU binary's sha256 differs after the open (the identities are compared before every row) | `HALT: qemu-system-aarch64 (…) is ffff…, the recorded identity is 5d389c65…: row t8 was NOT started and no attempt was created (packet section 4, halt 6 …` | PASS (12) |
| 9 | **s9** (S) | labels, freshness, the attempt's name | `open S1`, `open S2`: `REFUSED: session S1 is a session of the battery of 2026-10-02/03, whose authority is consumed …`, exit 2, no state directory. With a second earlier t8 attempt: `NOT FRESH: an earlier attempt of row t8 exists: …_g3-qualification-t8_attempt02`, two `admitted:` lines for attempt01, `HALT: an id of S3 is not fresh on the host; nothing was started`. With an attempt05 two levels down in a package of the output root (not seen by the freshness check, seen by the export tool's numbering): `HALT: row t8: the new attempt is named …_g3-qualification-t8_attempt06, which does not end '_g3-qualification-t8_attempt02' … No step of the row was run`; 0 recorded steps | PASS (23) |
| 10 | **s10a** (S) | a `STOP:` in (a) — printed by the stub `openssl`, because the real line (a) holds no helper call that prints one | steps `t9-a` only; `row t9: step t9-a printed STOP: (or left no console): t9-b and every later step were NOT run`; `step_not_run=t9-b and later` | PASS (24) |
| 10 | **s10b** (S) | (b)'s bounded broker log cannot be read | `STOP: sut_log broker itest-auth-wrongpw-q2: … was NOT read …`, `STOP: test 9(b): the broker log bounded to (b) was NOT read …`; steps `t9-a t9-b`; `t9-c and every later step were NOT run` | PASS (24) |
| 10 | **s10c** (S) | the same in (c) | `STOP: sut_log broker itest-notls-q2: … was NOT read …`; steps `t9-a t9-b t9-c`; `t9-de and every later step were NOT run` | PASS (24) |
| 10 | **s10d** (S) | the ACL probe ends 1 | `probe exit=1 …`, `STOP: test 9(d): probe exit=1 - NOT a pass …`; steps `t9-a t9-b t9-c t9-de`; `t9-exposure and every later step were NOT run`. The exposure step ran in s1 and s7i, after a clean (d)+(e) | PASS (24) |
| 11 | **s11** (S) | `term t8` during the wait (polls refused at once) | `TERM sent to the process group … (exit 0). KILL is never sent.`; the row ended 0.5 s later with exit 130: `row t8: interrupted by a signal (TERM)`, `row t8: attempt finished 'interrupted'; driver code 130; export: verified; …`; the attempt's own status `interrupted`; the package is under the bench's output root; the fake QEMU the same process; `row t9` refused; `close`: `session S3 closed` | PASS (19) |
| 11 | **s11b** added (S) | `term t8` while a poll is in flight (a read that stalls under `timeout 20`) | before TERM the poll is outside the row's group (`timeout 20 env E=…` in a group of its own); the row ended 0.5 s after `term`, exit 130, exported `interrupted`; right after, the poll was still running; 22 s later no process of the bench was left. The attempt carries the export tool's own record of that poll: `capture_failures … "no command record: the command never reached commands.jsonl (interrupted …)"` | PASS (20) |
| — | **s12** added (S); **expectation changed (O3)** | the tunnel master ends with the reboot and cannot be reopened; then `classify t8 failed invalid unknown` | the wait counts poll 3 (it needs no tunnel); step b: `STOP: ssh exited non-zero - the tunnel was NOT opened`, `STOP: the host preamble of runbook 6.1 … could not be loaded: the step never ran`; `HALT: row t8: step t8-b-wait-boot-id answered 97: the host preamble of runbook 6.1 (venv, secrets, helpers, tunnel) did not load, the step never ran`; no step c; the gate fails (97). Classify: exit 1, `HALT: row t8 is classified invalid instrumentation …: no further row of S3 starts`, one more halt recorded (three in all) | PASS (22) |
| O1 | **s13** added 2026-10-05 (S) | T8 halts in its steps (a `STOP:` in step e: the twins differ); `classify t8 failed valid fail` (a class that records no halt of its own); then `row t9` with `EGW_G3_RUI_GO` set to some words and exported | `HALT: row t8: step e printed STOP: …`; one halt; classify exit 0, `Next: 'close', then hand back to Rui: session S3 has a recorded halt …`; `row t9`: exit 2, `REFUSED: NOT STARTED: session S3 has a recorded halt (up=… row=t8 row t8: step e printed STOP: (…)). In S3 a halt ends the session …: classify the row if it awaits classification, then 'close', then hand back to Rui`; no line `EGW_G3_RUI_GO is set and is recorded`; no `row-t9.env`, no attempt of t9, no file of the state directory holds the words, 0 simulator calls of test 9; `close`: `session S3 closed` | PASS (26) |
| O2 b | **s14** added 2026-10-05 (S) | the tunnel master ends after `t8-tunnel-check` (which found it: `TUNNEL CHECK: the master answers …`) and before step e (hook before `t8-e-state`) | step e's console: `tunnel: connection refused on …/tunnel.ctl (no process listens on it) - stale socket file removed`, `TUNNEL UP`, then its own line (`CONTROLLER PROCESS NEW: …`), 0 lines `STOP:`; `HALT: row t8: the preamble of hx reopened a lost tunnel before step e (TUNNEL UP in its console; request, section 5, items 7 and 9): step f was NOT run, and T9 is not run`; steps end `t8-tunnel-check t8-e-state`, then the evidence reads and the gate; 0 simulator calls; `GATE t8: pass` (the tunnel was up again); one halt; classify `failed unknown inconclusive` (no halt of its own); `row t9`: `REFUSED: NOT STARTED: session S3 has a recorded halt (up=… row=t8 row t8: the preamble of hx reopened a lost tunnel before step e …` | PASS (27) |
| O2 b | **s15** added 2026-10-05 (S) | the same after step e and before step f (hook before `t8-f-smoke`) | no `TUNNEL UP` in step e; step f's console: the stale-socket line, `TUNNEL UP`, and then the smoke itself, because the preamble runs in the step's own shell before the line: one simulator call, `TEST STATUS itest-post-reboot-01-q2: simulator exit=0 transcript (tee) exit=0 post=0 -> PROCEDURE COMPLETE.`, 0 lines `STOP:`; `HALT: row t8: the preamble of hx reopened a lost tunnel before step f (TUNNEL UP in its console; request, section 5, items 7 and 9): T9 is not run; the row is classified by what its consoles show`; the script's no-halt line for the smoke is not printed; `t8_smoke=halt: the preamble of hx reopened a lost tunnel before the smoke`; `GATE t8: pass`; one halt; `row t9` refused, quoting it | PASS (30) |
| O2 c | **s16** added 2026-10-05 (S) | row t8 complete and classified pass; in row t9 the master ends after (a) and before (b) (hook before `t9-b`) | no `TUNNEL UP` in (a); (b)'s console: the stale-socket line, `TUNNEL UP`; `HALT: row t9: the preamble of hx reopened a lost tunnel before step t9-b (TUNNEL UP in its console; request, section 5, items 7 and 9): every later step of T9 was NOT run`; steps `guest-state-before t9-a t9-b`, then the gate; 0 simulator calls of `itest-notls-q2`, 0 ACL probe calls, no exposure step, no `step_not_run` line (a halt, not the rule for a `STOP:`); `GATE t9: pass`; `HALT recorded for session S3: classify this row, then 'close' …`; one halt | PASS (35) |
| O2 a | **s17** added 2026-10-05 (S) | row t8 a to f with every marker; the master ends after step f (hook before `t8-previous-boot-journal`, the first recorded step after f), so the first `hx` after it is the gate's tunnel check | no halt in the steps; the smoke's no-halt line; no `TUNNEL UP` in step f; the gate's console: the stale-socket line, `TUNNEL UP`, `TUNNEL CHECK: the master answers …`; `NOTE: the tunnel was DOWN after the row and the preamble of hx reopened it (TUNNEL UP in the gate's console): a restoration, and in S3 a halt`; `HALT: row t8: the gate did NOT pass (packet section 4, halt 3): the tunnel was found down after the row and reopened by the preamble of hx (request, section 5, items 7 and 9); ` (the only part that failed); no `GATE t8: pass`; `gate=failed: …`, `gate_tunnel=found down after the row and reopened by the preamble of hx`; one halt; classify `failed unknown inconclusive`: `NOTE: this row's gate did not pass (…)`, `Next: 'close', then hand back to Rui …`; `row t9` refused, quoting the gate's halt | PASS (36) |
| O3 | **s18** added 2026-10-05 (S) | row t8 complete, no halt, its gate passed; the operator classifies it `failed invalid unknown`: classify records a halt, prints the `close` next line, and `row t9` is refused | 0 halts before classify; classify: exit 1, `row t8: classified 'invalid instrumentation'; driver code 3; export: verified -> …_t8_attempt02`, `HALT: row t8 is classified invalid instrumentation (request, section 5 item 2; decision summary, choice 2): no further row of S3 starts`, one halt recorded, row state `classified`; **no line `Next: 'close', …`: the invocation ends with the HALT line** (`CHECK FAILED: classify prints the 'close' next line`); `row t9`: exit 2, `REFUSED: NOT STARTED: session S3 has a recorded halt (up=… row=t8 row t8 is classified invalid instrumentation …)`, no attempt; `close`: `session S3 closed` | **FAIL** (1 of 29: D1) |

The classification a scenario gives a halted row (`failed valid fail`, `failed unknown inconclusive`, …) is the
bench's, chosen to reach the next subcommand (and, in s13 to s17, chosen so that classify records no halt of its own
and the refusal of `row t9` can be traced to the halt under test); it says nothing about how the operator classifies.

**The changed expectations (O3), and why.** s12, s2vii and s7iii classify row t8 `failed invalid unknown`. Before
the bounded check that printed a NOTE and `Next: 'close' …`, and the bench checked only the class line (s12, s2vii) or
nothing (s7iii). Since O3 it is a halt of classify's own, so these three now check, through `classify_invalid`: exit
status 1, the class and the export receipt, the line `HALT: row t8 is classified invalid instrumentation (request,
section 5 item 2; decision summary, choice 2): no further row of S3 starts`, exactly one more halt in the session's
state file, and the row `classified`. The one check of the class line is kept inside `classify_invalid`; nothing was
removed. The `close` line is NOT checked there (it is the subject of s18), but each of these consoles records the
last lines classify printed: in s2vii and s7iii (gate passed) they end with the HALT line, as in s18; in s12 (gate
failed) with the gate's NOTE, which names `close`. s1's added keepalive check comes from the `ps`
stub, not from O1 to O3.

## 3. Defects, corrections, re-runs

**D1 — after O3, `classify … invalid unknown` names no next step (s18). Corrected after the re-run** (by the
preparation's owner: `cmd_classify` prints `Next: 'close', then hand back to Rui: …` before it exits on a halt of its
own, which also covers `not started` and a failed export; final bytes `a77bd201…`; s18 PASS in the final pass). The
s18 console of the re-run on `6009da1e…`, the classify invocation:

```
=== g3_battery.sh classify t8 failed invalid unknown bench: scenario s18 bench: none
-> exit 1
## …Z up=… classify t8: invalid instrumentation (failed, invalid/unknown)
row t8: classified 'invalid instrumentation'; driver code 3; export: verified -> <bench>/out/runs/2026-10-05/…_g3-qualification-t8_attempt02
HALT: row t8 is classified invalid instrumentation (request, section 5 item 2; decision summary, choice 2): no further row of S3 starts
…
CHECK FAILED: classify prints the 'close' next line - no line matches: ^Next: 'close', then hand back to Rui
```

Cause, in `P/g3_battery.sh` (`6009da1e…`): line 1918 calls `halt`, which sets `HALTED=1`; line 1924
`[ "$HALTED" -eq 0 ] || exit 1` then ends the invocation before lines 1927–1931, the only place that prints `Next:
'close', then hand back to Rui: …`. Before O3 this class printed (old line 1892) `NOTE: invalid instrumentation of
the shared chain is a halt condition … 'close' and hand back to Rui.` and then that `Next:` line. Since O3, when the
row's gate passed, no line of that invocation names `close` or any next step; the halt text says only `no further row
of S3 starts` (when the gate failed, line 1922's NOTE still ends `'close' and hand back to Rui.`: s12). Effect:
guidance only. The halt is recorded (one more `halt=` line), `row t9` is refused (exit 2, no attempt), and `close`
closes the session. The README states the rule (line 175: `A row classified invalid instrumentation records a halt
too`; line 176: after any halt, classify, then `close`), but its table of halts (line 204, the row `classify`) lists
only `the export FAILED` and `classified not started`. The same ending (a halt, exit 1, no `Next:` line) exists for
the class `not started` since the battery's script (s3, s5a, s9). Evidence of the same ending without a check: the
`--- the last lines classify printed:` lines of s2vii and s7iii (their gates passed), which end with the HALT line;
in s12 (gate failed) that line ends with the gate's NOTE.

Seen in the consoles, NOT corrected (none is a wrong halt, a missed halt or a false pass; items 1 to 6 are the first
pass's and still hold on `6009da1e…`):

1. `classify` after a halt before any step (s9, the name of the attempt) prints `NOTE: this row's gate did not pass
   (): no further row starts …` with empty brackets: the gate was not run, which is not "did not pass". Line 1922.
2. When a session records several halts, the `REFUSED` text of the next `row` quotes the LAST one only (`state_get …
   halt` reads the last line); `status` lists them all. With O3 this is now the usual case after an invalid
   classification: the refusal quotes classify's halt, not the row's cause (s12, s2vii, s7iii, s18); after `not
   started` the same (s3, s5a, s9).
3. A poll's line says `poll N at +X s`, where X is the instant the poll ENDED: in s2i `poll 3 at +27 s (bounded to
   20 s)` started at +7 s. The same instant goes into `t8_ssh_answered`.
4. After a halt before line a (s3, s5a) the row's gate still runs and can print `GATE t8: pass`; the halt stands
   and `row t9` is refused.
5. A `term` during a poll in flight (s11b) leaves that poll running for at most its 20 s, as the README says, and
   the exported attempt then holds a capture-failure record for it. The row itself ends at once.
6. The gate's record is compared at `row t8`, with the guest up (stream OPERATOR's deviation 8): s8b.
7. (new) O2 b and c are read from the step's console AFTER the step: the step's own line has then already run on the
   reopened tunnel. s14: step e's line ran (`CONTROLLER PROCESS NEW: …` in its console); s15: the smoke ran to
   `… -> PROCEDURE COMPLETE.` (one simulator call) before the halt; s16: (b)'s line ran. Nothing later runs; the halt
   text for f says the row is classified by what its consoles show.
8. (new) After a halt of O2 b or c the row's gate can pass (s14, s15: `GATE t8: pass`; s16: `GATE t9: pass`), because
   the tunnel is up again by then; the halt stands, as in item 4.

The bench's own failures: the first attempt of the re-run (09:09Z: s1, s2iii, s12 to s18, s2vii, s7iii) was refused
at `open S3` by the script's keepalive check, because no keepalive client ran on the host: the script did what it
must; the bench then got the `ps` stub. In that attempt two consoles also show faults of the bench itself on a session
that never opened: s1's `t9_ok` read a missing `openssl.log` (an error line), and s2iii stopped at `$1: unbound
variable` (no poll to count, under `set -u`) before its `SCENARIO` line. Neither path is reached once `open` passes.
A development pass of s12 to s18, s2vii and s7iii (09:12Z) gave the results of the final pass. All those consoles are
under `record/superseded/`.

## 4. The final sha256 and the consoles

`P/g3_battery.sh`: **`a77bd201a54d02620e625a620d2da796a8834289ec67daa808ed15324950f5cb`**, printed by the final pass at
its start (`final-pass.driver.txt`, 09:34:38Z).

- `record/s1.console.txt` and `record/s2iii.console.txt` name it on their first line (`script run: the FINAL bytes
  …, sha256 a77bd201…`).
- The 36 other scenario consoles name on their first line the short variant `c9adaf5f…` and on their second the final
  bytes it was made from, `a77bd201…`, with the two differing lines; `record/short-variant.txt` names both.
- **Every scenario console of `record/` names `a77bd201…`, directly (2) or through the short variant (36).** The
  files of `record/` that name no script, because they run none: `untouched.before.console.txt` and
  `untouched.after.console.txt` (the real trees), `sent-to-guest.all.txt` (the benches' logs) and
  `record-files.sha256`.
- All 38 scenario consoles name the same bench scripts (`bs3_run.sh affd2cb4…`, `bs3_setup.sh 995fab22…`,
  `bs3_env.sh ff64ecf1…`, `bs3_stubs.py ccdf6b9c…`).
- `record/superseded/` (86 files) keeps every earlier console: the 29 of the first pass's development (on
  `142a5aad…` or its variant `a5d6d662…`); the 32 consoles, `short-variant.txt`, `sent-to-guest.all.txt` and the two
  `untouched` consoles of the first pass (moved there today, the time of the move in each name); and today's earlier
  passes on `6009da1e…`/`1fe0f20e…` (09:09Z refused at the keepalive, 09:12Z development) with the `before` console
  of 09:01:50Z.

## 5. After the benches (`record/untouched.before.console.txt`, `record/untouched.after.console.txt`)

- `~/egw-exec` and `~/egw-tcg`: 18,690 entries; sha256 of the listing (path, modification time, size)
  `4ca11377bec752d564de598cbe1ae5975bb712d283f5cef96152472b74a45b95` before (09:14:17Z) and after (09:31:15Z):
  **identical**; 0 entries newer than the marker made at 09:14:18Z; the clone's HEAD
  `8e492613d36490a560ae56beabd6d5c2c01a8696` before and after (the host preparation had moved it there earlier today,
  before this stream; its rewrite of the helper file at 09:41 local time is in both listings alike);
  `~/egw-exec/g3-t8t9-s3` does not exist.
- The listing taken at this stream's start (09:01:50Z; console
  `record/superseded/untouched.before.20261005T091417Z.console.txt`) had the same sha256 and the same 18,690 entries.
  Its listing file was lost with `/tmp` when the distribution restarted (section 7, item 7), so the comparison with it
  is by sha256 only: the two trees did not change from this stream's start to its end.
- Processes whose command line names a scenario's bench: 0; processes named `qemu-system-aarch64`: 0; bash loops that
  stood for QEMU: 0. Every fake process was ended by its bench (the stub close driver, or the bench itself where the
  session could not be closed).
- `/tmp`: nothing new beside `/tmp/g3-s3-bench`; `/tmp/wrong.key` and `/tmp/wrong.crt` do not exist.
- Keepalive client of wsl.exe: none, at the start and at the end (`keepalive client (not started and not ended by
  this stream):` is empty); this stream started and ended none.
- `/tmp/g3-s3-bench` itself no longer exists: the distribution restarted right after the pass (09:31:16Z) and emptied
  `/tmp`, so the benches (their full consoles, attempts and exported packages) are gone; the record is what remains.

## 6. Not benched

1. **Anything real on the guest side**: ssh itself (how OpenSSH ends when `timeout` sends TERM; how long a read
   against a guest going down takes), the simulator, the reconcile tool (the smoke's `lost` and
   `late_confirmations` lines of s7i are the bench's text), `probe-acl.sh`, the bounded log reads, a real tunnel
   master (the stale master and the port-busy case of line d are not reproduced: in s1b, s12 and s14 to s17 the
   stub's master simply ends, leaving its socket, or cannot be opened).
2. **The four frozen session drivers** and `proof_fetch_sut_log.sh`: stubs in the copy. `drivers_sha256` is
   therefore answered by a stub in the benches (the copy hashed for real before the replacement gave the recorded
   value; stream OPERATOR's `funcs` console shows `verify_candidate` with the real drivers hashed).
3. **The export tool's own detection of a lost console capture** (74): in s2vii the status of one recorded poll is
   replaced by 74 after the real tool ran, so the script's reaction is shown, not the tool's detection.
4. **Test 9(a)'s real `openssl`**, and so the registration of a new `/tmp/wrong.crt` as a source after row t9: the
   stub writes nothing outside the bench.
5. **The 130 s quiet windows** in 36 of the 38 scenarios (the bench device); s1 and s2iii have them.
6. **A real keepalive client.** In the re-run `keepalive_check` reads the bench's synthetic client; the real check on
   a host without a client was seen once, outside any scenario's plan (09:09Z, refused). A real WSL relay as the
   parent, and the refusal for too little time left, are not benched.
7. Unchanged parts of the battery's script that no scenario reaches: the 3 h cut-off, `EGW_G3_RUI_GO` with `close`
   for a session closed outside the script (its non-effect on `row` is s13), `close` outside the script, a row whose
   process died without its trap, a recorder unit active at the gate or the close, a guest-state difference at T9's
   gate, `term t9`.
8. O2 where a scenario cannot reach it: a `TUNNEL UP` in (a), (c), (d)+(e) or the exposure step of T9 (the same
   check as s16, for another step), and a tunnel lost after the last step of T9, which is the gate check of s17 in
   `gate_after`, the one function for both rows.
9. `-no-reboot`'s two other spellings and the wait's refusal of a saved id that is not a boot id (shown one function
   at a time by stream OPERATOR).
10. `g3_hostprep.sh`, the sealing scripts, `ops/g3_go.sh` and `ops/g3_wait.sh`: not this stream's. Every subcommand
    was started the way the launcher starts it (`setsid`, stdin closed, one per invocation).

## 7. Deviations from the brief, with reasons

1. **Thirteen scenarios beyond the eleven of the brief**: the first pass's seven (s1b, s2v, s2vi, s2vii, s8c, s11b,
   s12), each one branch of a rule the brief states, and the six of 2026-10-05 (s13 to s18), asked for with the
   correction O1 to O3.
2. **`STUB_SLEEP` and `STUB_TIMEOUT` are on `PATH` in two scenarios only**; the others use the host's `sleep` and
   `timeout`, so that the script's own wait is real. The brief asks to reuse them: they are reused where a runbook
   loop had to be shortened.
3. **The bench device `BENCH_FAST_DRAIN`** (section 1): without it every run of line a costs 130 s and the smoke
   260 s. It changes what the step shell's `unset` does for two names, visibly; s1 and s2iii run without it.
4. **The module's stubs are imported and run, not rewritten**, but two sit behind wrappers (`ssh`, `scp`) and
   `STUB_PYTHON` behind the bench venv's `python`, with four hooks of the bench (a fragment run at one simulator
   call; text printed before `itest_reconcile check`; the 74 of "Not benched", item 3; and, since 2026-10-05, a
   fragment run before one recorded step). The module's `STUB_FETCH_SUT_LOG` replaces `proof_fetch_sut_log.sh` in
   the copy, as the module's own stub clone does.
5. **`ca.crt` is a placeholder** whose recorded sha256 the stub answers; the first preparation's bench copied the
   real file. Nothing under the real `HOME` is read by a bench except the execution venv's python.
6. **The keepalive client is a synthetic one in the re-run** (section 1, the `ps` stub): the brief of this run said a
   client was running and that none is to be started or ended; none was running, so the script's check would refuse
   every scenario at `open`. A stub that answers the check inside the bench starts nothing and cannot be taken for a
   keepalive by anything outside the bench.
7. **WSL stopped between this stream's calls, and every start of the distribution empties `/tmp`** (`D /tmp` in
   `/usr/lib/tmpfiles.d/tmp.conf`): the first pass's `/tmp/g3-s3-bench` (144 MB) was gone at 09:00Z, and the listing of
   the `before` taken at 09:01:50Z was lost at the next start (its console, with the listing's sha256, is kept in
   `record/superseded/`). The final pass (`before`, the 38 scenarios, `bs3_sent.sh`, `after`) therefore ran as ONE
   WSL invocation (09:14:17Z–09:31:16Z), which kept the distribution running; its `before` has the sha256 of the
   09:01:50Z listing, so this stream's start is covered too.
8. **Read-only looks at the real host**, outside any bench: `bs3_untouched.sh` (a `find` over `~/egw-exec` and
   `~/egw-tcg`, `ls /tmp`, the clone's `HEAD` file), the process list, the distribution's boot list, and the
   execution venv's `shellcheck` on the bench scripts.
9. **Consoles are filtered**: a console keeps the script's own lines, the halts, the markers, the keepalive lines and
   the checks, with the bench and scratchpad paths shown as `<bench>` and `<scratchpad>`. The full consoles were in
   each bench (`state/console/`, the attempts), under `/tmp`. Two superseded consoles of the 09:09Z attempt
   (`s1.20261005T091418Z`, `s2iii.20261005T091418Z`) each held one bash error line of `bs3_run.sh` itself, which
   `mask` does not see, with the scratchpad's full path (it holds a tool's name: hard rule 6). The same mask was
   applied afterwards to those two lines (paths to `<scratchpad>` and `<bench>`); nothing else of them was changed.
   (The first pass deleted two such consoles; these were kept.)
10. Three `shellcheck` warnings are left in `bs3_run.sh` (a variable that the sourced `bs3_env.sh` uses; two `ls |
    grep` on names the bench itself makes); `bs3_env.sh` has no shebang (it is sourced; clean with `-s bash`); the
    other shell scripts give none.

## 8. Files (sha256)

| File | sha256 |
|---|---|
| `g3_battery.sh` (final; D1 corrected after the re-run) | `a77bd201a54d02620e625a620d2da796a8834289ec67daa808ed15324950f5cb` |
| `bench/bs3_final_pass.sh` (the final pass's driver) | `f3753c7191a6b1854a7cc943917e50c5a254a1b9345de97d131f1ddd461a6344` |
| `bench/bs3_run.sh` (changed 2026-10-05) | `affd2cb43b5a4487085ccdc812f2e61b633caf4c9b0c480facdf3b069346fc24` |
| `bench/bs3_setup.sh` (changed 2026-10-05) | `995fab22d656906d85d7fd5a8448fe1b67760aa9e9f95301c917fc523c60a8ef` |
| `bench/bs3_sent.sh` (new 2026-10-05; corrected after the pass, section 2) | `8d52b26441b0b7fd66c6143a69f5b1aaa87669b90486d25020281d835c0d575b` (the version that made `record/sent-to-guest.all.txt`: `913af11ad49e7e40bb7e3e112c3d54c83cea359fba1e7953249bae7c143fb92a`) |
| `bench/bs3_env.sh` | `ff64ecf1b6400ca31490046c43944badd6b9f7c083d8ff7a804a7b464222d121` |
| `bench/bs3_stubs.py` | `ccdf6b9c31640ceee9f9b9e2d9bbd31f70512f84c669954933cff87907ea2d7c` |
| `bench/bs3_all.sh` | `6807f7052c273c9a8cff77e8dd88db61b8021c92758342e02daef9c7c553d076` |
| `bench/bs3_short.sh` | `eb052c5e17b7ccd63fc7bc0e853f6faa177fc39402ddc2d69f3e5d0dca9ae018` |
| `bench/bs3_untouched.sh` | `a0137f507ba2b0c70c3423d510122ea68aa9d10afe4dc42b894917ac620cee15` |
| `bench/g3_battery.short.sh` (generated from `a77bd201…`) | `c9adaf5f7d984895becf68644c82a37f753b6ae25a75d32ae3cde1221cd3f14b` |
| `bench/record/` | 38 scenario consoles, `final-pass.driver.txt`, `short-variant.txt`, `sent-to-guest.all.txt`, the two `untouched.*.console.txt`, 125 files under `superseded/` (every earlier console and the earlier checksum file): their sha256, and the ten bench files', are in `bench/record/record-files.sha256` (178 lines; `sha256sum -c` from `bench/`: all OK; the file's own sha256 `d0abaf83e74355f4964c8ad4a1b475a8b6802e7a2b5d3aeb29fec7ee0dcc272d`) |

The bench scripts, the variant and every console are LF-only and ASCII, without BOM (this note is UTF-8);
`bash -n` passes for the seven shell scripts and the variant, and `bs3_stubs.py` parses.

Command lines of the passes (WSL, login shell; `<P>` is the WSL path of the preparation folder). They run as ONE
invocation, so that `before` and `after` fall in one start of the distribution; the final pass ran them through
`bench/bs3_final_pass.sh`, launched detached (`setsid nohup … &`) with its output in `record/final-pass.driver.txt`:

```
bash <P>/bench/bs3_short.sh > <P>/bench/record/short-variant.txt     # makes bench/g3_battery.short.sh
bash <P>/bench/bs3_untouched.sh before /tmp/g3-s3-bench/_untouched > <P>/bench/record/untouched.before.console.txt
bash <P>/bench/bs3_all.sh s1 s2iii s1b s12 s2i s2ii s2iv s2v s2vi s2vii s3 s4a s4b s5a s5b s5c s5d s5e s6 s7i s7ii s7iii s8a s8b s8c s9 s10a s10b s10c s10d s11 s11b s13 s14 s15 s16 s17 s18
bash <P>/bench/bs3_sent.sh > <P>/bench/record/sent-to-guest.all.txt
bash <P>/bench/bs3_untouched.sh after /tmp/g3-s3-bench/_untouched > <P>/bench/record/untouched.after.console.txt
```

s1 and s2iii run in real time (about 10 and 17 minutes); the 36 others end within about a minute and a half.

## 9. Open points

1. **D1** (section 3): whoever next touches the script decides whether `classify` should print its `Next: 'close' …`
   line after the halts it records itself (invalid instrumentation, and `not started`), and whether the README's
   table of halts should list the O3 halt. Until then, the operator follows the README: after any halt, `close`.
2. If `g3_battery.sh` is edited after this (even a comment), the short variant, every console and this note's
   sha256 are stale: `bs3_short.sh`, then the one invocation of section 8, about 20 minutes.
3. **Before S3 a real keepalive client must be attached**: the script refuses `open S3` without one (seen at
   09:09Z), and without one the distribution stops between commands, which empties `/tmp`.
4. Items 1 to 3 and 7 of section 3 are for whoever next touches the script; none needs a change before S3.
5. On the day the first hx step after the reboot (step b) will find the tunnel as the real reboot leaves it. The
   benches show both endings the stubs can give (reopened by the preamble: s1b; not reopened: 97 and a halt, s12),
   not the stale-master case the README describes at line d. After line d, a lost tunnel is now a halt wherever the
   preamble reopens it (s14 to s17).
6. A `term t8` issued while a poll is in flight leaves a capture-failure record in the exported attempt (s11b):
   expected, and worth one line in the result note if it happens.
7. The sealing script copies `bench/` whole: the superseded consoles go with it (about 1.3 MB).
