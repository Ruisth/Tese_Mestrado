# Bench of the second opening of S3 — notes (2026-10-05; times in UTC)

`Q` is this preparation (`<S>/g3/s3bprep`), `P` the earlier one (`<S>/g3/s3prep`, read-only here), `<S>` the
working path (masked so in every console). Everything ran offline in WSL (Ubuntu-24.04), under
`/tmp/g3-s3b-bench/<scenario>`, with `HOME` and every `EGW_*` inside the bench: no guest, no QEMU, no docker, no real
ssh. Nothing was written outside `Q/bench/` and this note; `Q/g3_battery.sh` and `Q/s3b_preflight_exception.py` were
not edited.

## Result

- **Script run: `Q/g3_battery.sh` sha256 `42de225aedfd25fa0f4975276bf2880e146c2ad66a4624f811487ba61ea0f034`**, in place
  (11 scenarios) or as a byte-identical copy in the bench (e6); every scenario console names it on its first line.
- **Checker: `Q/s3b_preflight_exception.py` sha256 `ab6ee3216f51919105ea8a6c67aa8d8dc2e5d1c1cd860ab3b64451072d6e7a95`**,
  equal to the script's `EXCEPTION_SHA`; unchanged after every scenario (checked at the end of each console).
- **12 scenarios, 12 PASS, 0 checks failed** (557 checks), one pass as one WSL invocation, 11:33:27Z–11:42:40Z
  (`record/pass.driver.txt`; e1 ran in real time, 11:33:32Z–11:42:39Z; the eleven others ended by 11:33:38Z).
- **The checker alone: 13 of 13 as expected** (`record/validator.console.txt`): the unchanged fixture and the real
  WSL attempt directory give `EXCEPTION APPLIES` (exit 0); each of the ten changed fixtures gives `EXCEPTION DOES NOT
  APPLY: … - the halt stands` (exit 1); the checker with one comment appended still applies the exception (which is
  why the script's byte check matters: e6).
- **No defect of the script was seen.** No wrong halt, no missed halt, no false pass. Observations in section 4.
- **The real `~/egw-exec` and `~/egw-tcg` are unchanged** (section 5).

## 1. The bench

Copied from `P/bench` and adapted (each file says so in its header; the scripts are named `bs3b_*` so that they are
not taken for the earlier ones):

| File | From | What changed |
|---|---|---|
| `bs3b_setup.sh` | `bs3_setup.sh` | bench root `/tmp/g3-s3b-bench`; the runbook blob read from `P`; the `sha256sum` stub answers the root file system `b48b010d…` (was `22e9da85…`); the stub `preflight.sh` has a FIXTURE mode (below); `ps` stub text only |
| `bs3b_env.sh` | `bs3_env.sh` | bench root; row files `Q/rows` (identical to `P/rows`: `diff -r` empty; manifest `678b9203…`); **`EGW_G3_STATE` is unset**, so the script uses its own new default `<bench>/egw-exec/g3-t8t9-s3-attempt02` (read by the bench as `BSTATE`) |
| `bs3b_stubs.py` | `bs3_stubs.py` | bench root only (imports the same test module, `fe8baa60…`) |
| `bs3b_untouched.sh` | `bs3_untouched.sh` | bench root; marker per record folder; names both state directories, the real console's and session file's sha256, and every `sleep N` (N ≥ 3600) |
| `bs3b_run.sh` | `bs3_run.sh` | its helpers and its s1 kept in substance (e1); new: the fixture, `open_common`, `open_halted`, `close_after_halt`, the e2 checks, scenarios e1 to e7b |
| `bs3b_all.sh` | `bs3_all.sh` | runs `bs3b_run.sh` |
| new: `bs3b_fixture.sh`, `bs3b_mutate.py`, `bs3b_validator.sh`, `bs3b_pass.sh`, `fixture/S3-preflight.console.txt` | — | below |

Not copied: `bs3_short.sh` (no short-timing variant was needed: only e1 runs the reboot wait, and its stub guest
answers at the third poll), `bs3_sent.sh`, `bs3_final_pass.sh` (replaced by `bs3b_pass.sh`).

**The fixture** (`bs3b_fixture.sh <variant> <dest>`): `<dest>/attempts/20261005T105656Z_live-preflight_attempt11/` is
a `cp -a` copy of the exported package `output_test/runs/2026-10-05/20261005T105656Z_live-preflight_attempt11`
(43 files; the copy is checked against the package's own `SHA256SUMS`, 42 lines, before anything else); the
original is only read. `<dest>/preflight.console.txt` is the driver console as the operator script saw it
(`~/egw-exec/g3-t8t9-s3/S3-preflight.console.txt`, 239 lines, sha256 `bd7bdb37…`, copied read-only to
`Q/bench/fixture/S3-preflight.console.txt` and checked against that sha256 at every use) **without its last line**
`preflight.sh exit=3`, which the script's `run_driver` appends itself; it therefore ends with the `DRIVER RESULT` line.
No renaming was needed: the export tool numbers attempts per scenario slug, so `…_live-preflight_attempt11` collides
with nothing in a bench; the directory name, `attempt.json`'s `run_id` and the `DRIVER RESULT` line are the real ones
and equal. `bs3b_mutate.py` then makes the variant's one change to the copy (every other line of `commands.jsonl` kept
byte for byte) and the fixture prints the sha256 of `attempt.json`, of `commands.jsonl` and a hash of the whole tree
(every file's sha256 and every entry's path, modification time, size and mode).

**The stub `preflight.sh`, FIXTURE mode** (on when `<bench>/fixture/attempts/` exists): it copies every attempt
directory there into the bench's attempts directory with `cp -a` (never over an existing one), prints
`<bench>/fixture/preflight.console.txt` and exits with `<bench>/fixture/exit` (3). It prints nothing of its own and
exports nothing, so the console the script keeps is byte-identical to the real one: checked in e2 and e6
(`bd7bdb37…`), and equal to the fixture's console plus `preflight.sh exit=3` in every scenario. Without the folder the
stub is the earlier bench's (one step, finished valid pass, exit 0): e1.

**Real in every bench**, as in the earlier bench (`P/bench-notes.md` section 1): the step files of `Q/rows`, the
helper file and `tunnel.sh` written by the runbook's own heredocs (`e5eba37e…`, `38f5cae9…`), a copy of `tools/` and
`src/egw_experiments` of the worktree `<S>/pb` (drivers hashed `4a6a572d…` before the four session drivers were
replaced by stubs), the export tool, the execution venv's python (read-only, no bytecode), and, new here, **the
checker itself** (run by the script as `$PY s3b_preflight_exception.py <attempt> <driver console>`). The stubs are the
earlier bench's: the test module's `STUB_*` behind wrappers, the fake QEMU process, `git`, `sha256sum`, `pgrep`,
`openssl`, and the `ps` stub that adds a SYNTHETIC keepalive client (pid 4194301, no process).

**Keepalive:** two real clients ran on the host throughout (pid 305 `sleep 43200` and pid 308 `sleep 43202`, both
started at about 11:22:40Z, not by this stream); the stream started and ended none. The script's `keepalive_check`
lists them and the synthetic one and takes the best; each scenario console checks the synthetic line.

**Switches:** e1 ran with `BENCH_FAST_DRAIN=0` (the helper's real 130 s quiet windows, the host's `sleep` and
`timeout`), as the earlier s1; e2 to e7b with `BENCH_FAST_DRAIN=1`, which has no effect there (no step shell runs a
drain at `open` or `close`). `BENCH_SCALED=0` everywhere.

## 2. The scenarios

Every console (`record/<scenario>.console.txt`) starts with `script run: sha256 42de225a…`. "Halt checks" below means,
in each halting scenario, all of: `open` exit 1; the HALT line; no line `PROCEEDED UNDER`; 0 lines
`preflight_exception=` in `session-S3.env`; `preflight_exit=3`; `preflight_attempt=` the attempt the `DRIVER RESULT`
line names; state `halted`; exactly 1 halt; the line `The session state is 'halted' and nothing was closed. …`; **no
environment copy** (no `## environment input` line, no `S3-environment-copy.txt`, the bench's harness input
`sut_environment.json` with its setup sha256, no kept copy, no `sut_environment*` key); **no gate** (no `gate_health.sh`
line, no gate console, 0 gate attempts, no `gate_health_exit` key); no guest listing; the stub created no attempt of
its own; the kept driver console's sha256 as expected; the placed attempt(s) identical to the fixture (attempt.json,
commands.jsonl, whole tree) after open and after close; `current_session` present after open. Then `close`: exit 0,
`## … session S3 closed (guest_session_close.sh exit 0)` after the recorded `stop -t 130`, state `closed`, still 1
halt, `current_session` removed, the fake QEMU ended, still 0 `preflight_exception` lines. Every halting console also
shows the common open checks: `expected:    b48b010d… (the value the close of S3's first opening recorded)`, `rootfs
ext4: b48b010d…`, ` STATE=<bench>/egw-exec/g3-t8t9-s3-attempt02 ROWS=…`, `session-S3.env` there,
`steps_script_sha256=42de225a…`, and the keepalive line.

| # | What ran (fixture change) | Expected | Observed (decisive console lines) | Result |
|---|---|---|---|---|
| e1 | the stub preflight of the earlier bench (exit 0), no fixture; `open S3`, `row t8`, `classify t8 finished valid pass`, `row t9`, `classify t9 …`, `close`, `status`; real time | open passes and examines nothing; rows and close as in s1 | open: `preflight.sh exit=0`; no `examined` line, no `ok:`/`EXCEPTION` line, no `PROCEEDED UNDER` line, 0 `preflight_exception` lines, no `S3-preflight-exception.txt`, `preflight_exit=0`; the environment copy and the gate ran; `## … session S3 is open`; the two `admitted:` lines for S2's t8 attempt01. Row t8 (11:33:35Z–11:40:27Z): the carriers `<unset>` in the step shell; three `drained: … 27 consecutive readings over 131 s`; polls `+0 s` and `+10 s` 255, `poll 3 at +20 s (bounded to 20 s): exit status 0 and the answer is the boot id bbbbbbbb-…`; `QEMU PROCESS UNCHANGED`; `REBOOT SHOWN: boot id aaaaaaaa-… -> bbbbbbbb-…`; every marker of c to f; `GATE t8: pass`; attempt `…_g3-qualification-t8_attempt02`; 1 reboot command, 0 start/restart commands, 0 pkill; the t8 attempt's workload text names `session S3 (second opening)`; `classified 'pass'; driver code 0; export: verified`. Row t9 (11:40:28Z–11:42:37Z): steps `t9-a t9-b t9-c t9-de t9-exposure`, `GATE t9: pass`, attempt `…_t9_attempt01`, classified pass, exported. `session S3 closed (guest_session_close.sh exit 0)`; 0 halts | PASS (60) |
| e2 | the real failed preflight, unchanged; `open S3`, `status`, `close` | the checker's lines, `PROCEEDED UNDER …`, the key, then the environment copy, the gate, the listing; open ends `session S3 is open`; the attempt not modified | `## … preflight.sh exited 3: the authorised T8/T9 exception for collector-duration is examined (read-only)`; six `ok:` lines (`ok: driver result: 20261005T105656Z_live-preflight_attempt11 exit=3 failed, invalid, inconclusive, exported` … `ok: collector-check: no problem, no unexpected name, six services (43-43 rows each)`, `ok: collector-duration failed on the numeric judgement alone: window 43 s of the declared 45 s, shortfall 2 s (UTC stamps; not a measured early stop)`); `EXCEPTION APPLIES: preflight 20261005T105656Z_live-preflight_attempt11 stays failed and invalid; the session proceeds under the authorised T8/T9 exception (collector-duration only: UTC window 43 s of 45 s declared)`; `PROCEEDED UNDER THE AUTHORISED T8/T9 EXCEPTION: preflight 20261005T105656Z_live-preflight_attempt11 stays failed and invalid (collector-duration only); the environment copy, the gate and every identity check below stay mandatory`; key `preflight_exception=proceeded under the authorised T8/T9 exception (collector-duration only; preflight 20261005T105656Z_live-preflight_attempt11 stays failed and invalid)` (one line), `preflight_exit=3`; the checker's record `S3-preflight-exception.txt` (7 lines); `## environment input …`, `labels: QEMU/TCG and ARM64 EMULATED are present`, `harness input now: <bench>/home/egw-tcg/sut_environment.json sha256 7f713cb2…` (the preflight's capture), `source: …/20261005T105656Z_live-preflight_attempt11/environment/sut_environment.json (preflight package …)`; `gate_health.sh … exit=0`, gate attempt `…_g2-gate-preconditions_attempt01`; five `fresh on the guest:` lines; `## … session S3 is open`, `Next: 'row t8'`; 0 halts; order examined (line 293) < verdict < PROCEEDED < environment copy < gate < open; the kept driver console = the real one (`bd7bdb37…`); `attempt.json` `b031bb65…` and `commands.jsonl` `09a06a54…` equal to the original package's, before (fixture), after open and after close, whole-tree hash `778c7fd0…` unchanged; `close` exit 0, `session S3 closed`, the key kept | PASS (55) |
| e3 | `commands.jsonl` step 7 (stack-health) `exit_code` 0 → 1 | HALT `the authorised exception does NOT apply`, no environment copy, no gate | three `ok:` lines, then `EXCEPTION DOES NOT APPLY: step stack-health ended 1, not 0 - the halt stands`; `HALT: preflight.sh exited 3 and the authorised exception does NOT apply (checker exit 1; see <bench>/egw-exec/g3-t8t9-s3-attempt02/S3-preflight-exception.txt and <bench>/egw-exec/g3-t8t9-s3-attempt02/S3-preflight.console.txt)`; halt checks; close | PASS (44) |
| e4a | `attempt.json` removed | HALT as in e3 | `EXCEPTION DOES NOT APPLY: attempt.json could not be read ([Errno 2] No such file or directory: '<bench>/egw-exec/attempts/20261005T105656Z_live-preflight_attempt11/attempt.json') - the halt stands`; the same HALT line; halt checks; close | PASS (44) |
| e4b | the console's `DRIVER RESULT` line names `…_attempt12`; no attempt of that name exists | a HALT; the exception cannot be examined | no `examined` line, no checker line, no checker record; `HALT: preflight.sh exited 3; see <bench>/egw-exec/g3-t8t9-s3-attempt02/S3-preflight.console.txt` (the script's own halt for a failed preflight: it examines the exception only for an attempt the line names and that exists); `preflight_attempt=<bench>/egw-exec/attempts/20261005T105656Z_live-preflight_attempt12`; halt checks (the placed `…_attempt11` unchanged); close | PASS (43) |
| e4b2 | the same, and a copy of the attempt named `…_attempt12` (its `attempt.json` still says `…_attempt11`) | HALT as in e3 | two `ok:` lines (the driver line; `attempt directory is the driver's: …_attempt12`), then `EXCEPTION DOES NOT APPLY: attempt.json run_id='20261005T105656Z_live-preflight_attempt11', not '20261005T105656Z_live-preflight_attempt12' - the halt stands`; the HALT line of e3; halt checks (both placed attempts unchanged); close | PASS (46) |
| e4c | `collector-check.json` `problems` holds one entry | HALT as in e3 | `EXCEPTION DOES NOT APPLY: collector-check reports problems: ['bench: egw-mongodb-1 has 3 forward gaps in its window (a problem listed by the check)'] - the halt stands`; the HALT line; halt checks; close | PASS (44) |
| e5a | `attempt.json` `capture_failures` holds one record | HALT | `EXCEPTION DOES NOT APPLY: attempt.json records capture failures: [{'note': "bench: the console capture of 'collector-live' was lost", 'seq': 13, 'step': 'collector-live'}] - the halt stands`; the HALT line; halt checks; close | PASS (44) |
| e5b | `commands.jsonl` step 13 (collector-live) stdout capture `state` `truncated` (bytes unchanged) | HALT | `EXCEPTION DOES NOT APPLY: step collector-live: its stdout capture is not complete ({'state': 'truncated', 'bytes_received': 2345, 'bytes_kept': 2345, 'error': None, 'echo': 'written'}) - the halt stands`; the HALT line; halt checks; close | PASS (44) |
| e6 | the fixture unchanged; the script run as a byte-identical copy in `<bench>/script/` beside a copy of the checker with one comment line appended (`4de71079…`) | HALT `is not the prepared one`, the checker not run | `## … is examined (read-only)`, then at once `HALT: preflight.sh exited 3, and the exception's checker <bench>/script/s3b_preflight_exception.py is not the prepared one (sha256 ab6ee321…): the exception was NOT examined; see …/S3-preflight.console.txt`; no `ok:` or `EXCEPTION` line, no checker record; halt checks; the kept driver console = the real one; close | PASS (45) |
| e7a | an observed system fault: `attempt.json` `system_outcome` `fail`, `reason` prefixed with the frozen preflight's `observed system fault(s): the stack is not healthy, … (stack-health exit 3); `, and the console's `DRIVER RESULT` line `system_outcome=fail` (as `driver_status.py` prints it: invalid instrumentation with an observed fault is exit 3) | HALT | no `ok:` line; `EXCEPTION DOES NOT APPLY: the driver's result line does not say system_outcome=inconclusive: DRIVER RESULT 20261005T105656Z_live-preflight_attempt11: exit=3 (…) status=failed instrumentation_validity=invalid system_outcome=fail export=exported - the halt stands`; the HALT line; halt checks; close | PASS (44) |
| e7b | the same change in `attempt.json` only (the console unchanged) | HALT | `EXCEPTION DOES NOT APPLY: attempt.json system_outcome='fail', not 'inconclusive' - the halt stands`; the HALT line; halt checks; close | PASS (44) |

## 3. The checker alone (`record/validator.console.txt`)

`bs3b_validator.sh` runs `Q/s3b_preflight_exception.py` in place with the execution venv's python, as the script calls
it: on `<attempts>/<run id of the DRIVER RESULT line>` and the driver console (the fixture's console plus
`preflight.sh exit=3`). Last lines (exit status):

| Fixture | Exit | Last line |
|---|---|---|
| unchanged | 0 | `EXCEPTION APPLIES: preflight 20261005T105656Z_live-preflight_attempt11 stays failed and invalid; the session proceeds under the authorised T8/T9 exception (collector-duration only: UTC window 43 s of 45 s declared)` |
| step7-exit1 (e3) | 1 | `EXCEPTION DOES NOT APPLY: step stack-health ended 1, not 0 - the halt stands` |
| no-attempt-json (e4a) | 1 | `EXCEPTION DOES NOT APPLY: attempt.json could not be read ([Errno 2] No such file or directory: '<V>/no-attempt-json/attempts/…_attempt11/attempt.json') - the halt stands` |
| other-run-id (e4b; the script does not run the checker; here it is run on the placed `…_attempt11`) | 1 | `EXCEPTION DOES NOT APPLY: the attempt directory <V>/other-run-id/attempts/20261005T105656Z_live-preflight_attempt11 is not the driver's attempt 20261005T105656Z_live-preflight_attempt12 - the halt stands` |
| other-run-id-dir (e4b2) | 1 | `EXCEPTION DOES NOT APPLY: attempt.json run_id='20261005T105656Z_live-preflight_attempt11', not '20261005T105656Z_live-preflight_attempt12' - the halt stands` |
| collector-problem (e4c) | 1 | `EXCEPTION DOES NOT APPLY: collector-check reports problems: ['bench: egw-mongodb-1 has 3 forward gaps in its window (a problem listed by the check)'] - the halt stands` |
| capture-failures (e5a) | 1 | `EXCEPTION DOES NOT APPLY: attempt.json records capture failures: [{…}] - the halt stands` |
| capture-truncated (e5b) | 1 | `EXCEPTION DOES NOT APPLY: step collector-live: its stdout capture is not complete ({'state': 'truncated', …}) - the halt stands` |
| system-fault (e7a) | 1 | `EXCEPTION DOES NOT APPLY: the driver's result line does not say system_outcome=inconclusive: DRIVER RESULT … system_outcome=fail export=exported - the halt stands` |
| system-fault-record (e7b) | 1 | `EXCEPTION DOES NOT APPLY: attempt.json system_outcome='fail', not 'inconclusive' - the halt stands` |
| reason-fault (validator only: the reason alone starts `observed system fault(s): `, `system_outcome` still `inconclusive`) | 1 | `EXCEPTION DOES NOT APPLY: attempt.json's reason is not the frozen preflight's reason for collector-duration as its only failed mandatory step, with nothing observed and nothing skipped: 'observed system fault(s): … ' - the halt stands` |
| the real WSL attempt `~/egw-exec/attempts/…_attempt11` with the real console, read in place (attempt.json `b031bb65…`, commands.jsonl `09a06a54…`, console `bd7bdb37…`, the same before and after) | 0 | `EXCEPTION APPLIES: preflight 20261005T105656Z_live-preflight_attempt11 stays failed and invalid; …` |
| the checker with one comment appended (`4de71079…`), unchanged fixture | 0 | `EXCEPTION APPLIES: …` (the logic is unchanged: what refuses it in e6 is the script's byte check, before the checker runs) |

`VALIDATOR: 13 of 13 as expected; checker sha256 after the runs ab6ee321…`. The WSL attempt's `attempt.json`,
`commands.jsonl`, `collector-check.json`, the collector-duration console and `environment/sut_environment.json` have
the same sha256 as the package's (checked at the start).

## 4. Observations (not defects; nothing to change before the second opening)

1. **e4b:** when the `DRIVER RESULT` line names an attempt that does not exist, the exception is not examined and the
   halt is the script's unchanged `HALT: preflight.sh exited 3; see …` (line 1030), which does not mention the
   exception. It fails closed; the operator reads the console. (`[ -d "$pre" ]` in line 1019 is the gate.)
2. **e6:** the line `## … preflight.sh exited 3: the authorised T8/T9 exception for collector-duration is examined
   (read-only)` (line 1020) is printed before the byte check, so the console says "is examined" and, on the next line,
   "the exception was NOT examined". The halt and its text are right; only the heading precedes the check.
3. `erc` and `excepted` (lines 1018, 1024) are not in `cmd_open`'s `local` list; `cmd_open` runs once per invocation,
   so this has no effect.
4. The checker reads every one of its inputs and wrote nothing in any bench (the placed attempt's whole-tree hash,
   with modification times, is unchanged after open and after close in all 11 fixture scenarios; the real WSL attempt
   too, in the validator). Outside comments the script names the preflight only in `cmd_open` (lines 1005–1031) and
   in `environment_copy`, which `open` calls: `row`, `classify` and `close` read no `preflight_*` key, so an excepted
   session's rows start as after a passing preflight.
5. `status` does not print `preflight_exception`; it is in `session-S3.env`, in the open console and in
   `S3-preflight-exception.txt`.

## 5. The real trees (`record/untouched.start.console.txt`, `untouched.before.console.txt`, `untouched.after.console.txt`)

- `~/egw-exec` and `~/egw-tcg`: 18,846 entries; sha256 of the listing (path, modification time, size)
  `b2e3e64309a6eed50a88d72d5790d931d07e6b3a4346797d5aee8183adc5d109` at this stream's start (11:23:12Z, before any
  bench ran), before the pass (11:33:28Z) and after it (11:42:39Z): **identical**; the before and after listings
  compared line by line: identical; 0 entries newer than the marker of 11:33:28Z; the clone's HEAD `8e492613…`
  unchanged.
- The first opening's state directory `~/egw-exec/g3-t8t9-s3` (12 entries; `S3-preflight.console.txt` `bd7bdb37…`,
  `session-S3.env` `79874647…`, `state=closed`): the same at start, before and after. `~/egw-exec/g3-t8t9-s3-attempt02`
  and `~/egw-exec/current_session` do not exist.
- `/tmp`: nothing new beside `/tmp/g3-s3b-bench`; `/tmp/wrong.key` and `/tmp/wrong.crt` do not exist. Processes that
  name a scenario's bench: 0; processes named `qemu-system-aarch64`: 0; fake QEMU loops: 0.
- Keepalive clients: pid 305 `sleep 43200` and pid 308 `sleep 43202`, before and after (started about 11:22:40Z, not by
  this stream); this stream started and ended none.
- The real WSL attempt `~/egw-exec/attempts/20261005T105656Z_live-preflight_attempt11` was read in place by the
  checker alone (section 3); its `attempt.json` and `commands.jsonl` have the same sha256 after as before, and the
  listing (which holds it) did not change.

## 6. Not benched

1. **Anything real on the guest side**, and the four frozen session drivers (stubs; see `P/bench-notes.md` section 6).
   In particular the real preflight driver ending exit 3: the fixture replays its record and console.
2. **The WSL attempt directory inside the script**: the benches place a copy of the exported PACKAGE (which also holds
   `export_manifest.json`, `SHA256SUMS`, `SUMMARY.md`; the WSL directory holds `export/` and `tests/` instead). The
   checker ignores other files; the real WSL attempt directory was given to the checker alone (section 3), not to the
   script.
3. **A row after an excepted open**: e2 opens and closes only. Rows read nothing of the preflight (section 4, item 4);
   e1 shows both rows on the normal path with this script.
4. The checker absent beside the script (the same branch as e6: `sha_of` fails, so the value differs), the checker
   hanging or interrupted, another python than the execution venv's (3.12.3).
5. A preflight that ends 1, 2, 4 or 5: the exception block is entered for exit 3 only (line 1019), and those statuses
   reach the unchanged halt; not run.
6. The 130 s quiet windows in e2 to e7b (none is reached at `open` or `close`); the earlier bench's 38 scenarios on the
   unchanged parts of the script (not re-run: `diff Q/base/g3_battery.sh Q/g3_battery.sh` touches only the lines marked
   `S3, second opening`).
7. A real keepalive client as the script's only client: two real ones ran, but every check passed on the bench's
   synthetic one as well.
8. `Q/ops/*.sh`, the README and the operator procedure.

## 7. Deviations from the brief, with reasons

1. **Twelve benches for the brief's seven items**: e4 is split into e4a, e4b, e4b2 and e4c (e4b2 makes the checker,
   not only the script, meet a console that names another attempt: e4b alone never reaches the checker); e5 into e5a
   and e5b; e7 into e7a (the record and the driver's line, as the frozen driver would write them) and e7b
   (`attempt.json` only, so that the checker's own `system_outcome` check is reached). `reason-fault` is in the
   validator only.
2. **e1 ran on the final bytes in real time**, not on a short-timing variant: no variant was made.
3. **The driver console is kept in `Q/bench/fixture/`** (16,381 bytes, sha256 `bd7bdb37…`, checked at every use), so
   that the bench does not depend on `~/egw-exec/g3-t8t9-s3` once the first opening's records are sealed; the package
   is read from `output_test` at every use.
4. **The start listing** (`untouched.start.console.txt`, 11:23:12Z, before any bench ran) was taken by an earlier text
   of `bs3b_untouched.sh` whose keepalive line named `sleep 43200` only; the script was then changed to name every
   `sleep N` with N ≥ 3600 (pid 308 runs `sleep 43202`). Nothing else of it changed.
5. Development runs (11:27Z–11:32Z: the validator, e2, the ten halting scenarios, e1 with `BENCH_E1_FAST=1`) ran in
   benches under `/tmp/g3-s3b-bench` before the pass; their consoles were not kept. The pass replaced those benches.
6. `shellcheck` (the execution venv's) reports warnings and infos only: `BSTATE` and `BASE_PATH` used across the
   sourced `bs3b_env.sh`, `ls` on names the bench makes, word splitting of the bench's own pid list.

## 8. Files (sha256)

| File | sha256 |
|---|---|
| `Q/g3_battery.sh` (run, never edited) | `42de225aedfd25fa0f4975276bf2880e146c2ad66a4624f811487ba61ea0f034` |
| `Q/s3b_preflight_exception.py` (run, never edited) | `ab6ee3216f51919105ea8a6c67aa8d8dc2e5d1c1cd860ab3b64451072d6e7a95` |
| `bench/bs3b_run.sh` | `5c9fca40ebc3a0a6b1721e3ace9d024c783992c475d0a98ff024a7ff0d2224ed` |
| `bench/bs3b_setup.sh` | `33eb543d7a71ad5f4b2d61e944f70d30facc1e824d87a7a1a87d53a4820e08c1` |
| `bench/bs3b_env.sh` | `d1c6d829b8397f43879877489863051832a8504f5dc9f5f9340997c0b4b5c0b4` |
| `bench/bs3b_stubs.py` | `047420a051837d7ec4e77d75deecbdca1557446c20bc3b6555fbc1f17019fa57` |
| `bench/bs3b_fixture.sh` | `43b1a1d601fd91ac2982b13110747095cb60591b820f2fc53253ddf65d5f64eb` |
| `bench/bs3b_mutate.py` | `a90d069fe9666026df4ff7149ca3680c6cc68ecfd4019db21cc2384d155dffbb` |
| `bench/bs3b_validator.sh` | `d991e8bbd7fd47f0f8e86a1f8c6db21cf8a1896944c20685ad3d523350ea699c` |
| `bench/bs3b_all.sh` | `333f4872f2df5c160b2d60775a2de729d25a02712b41fc5fb022b358e9bc48b4` |
| `bench/bs3b_pass.sh` | `eb05681d8ebdc826872581a26d6be49761021356ee5c877925cc4668f9d31410` |
| `bench/bs3b_untouched.sh` | `107905efd4d86195f3feab0e12eea5ca76b0f8be433339b8211b1c0e4578cac8` |
| `bench/fixture/S3-preflight.console.txt` (the real driver console, copied) | `bd7bdb373948869d61ea35a48e2292b3ffcb2a93dd848da2936b8fdb1994390c` |
| `bench/record/` | 12 scenario consoles, `validator.console.txt`, `pass.driver.txt`, the three `untouched.*.console.txt`: their sha256 and the bench files' are in `bench/record/record-files.sha256` (28 lines; `sha256sum -c` from `bench/`: all OK; the file's own sha256 `cf0da07e2c1aa5efc4ec8c2455f92b98682d4b5b273b399a945320170907a89c`) |

The consoles name these bench files by the first 16 characters of their sha256 on their third line.

The bench scripts, `bs3b_*.py` and the kept console are LF-only and ASCII; `bash -n` passes for every shell script and
the two Python files parse.

Command line of the pass (WSL, login shell; `<Q>` is the WSL path of this preparation):

```
bash <Q>/bench/bs3b_pass.sh > <Q>/bench/record/pass.driver.txt 2>&1
```

which runs `bs3b_untouched.sh before /tmp/g3-s3b-bench/_untouched`, `bs3b_validator.sh`, `bs3b_all.sh e1 e2 e3 e4a e4b
e4b2 e4c e5a e5b e6 e7a e7b` and `bs3b_untouched.sh after /tmp/g3-s3b-bench/_untouched`. One scenario:
`bash <Q>/bench/bs3b_run.sh e2`.
