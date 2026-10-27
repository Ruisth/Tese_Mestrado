# Stream OPERATOR — notes (2026-10-04)

Offline only: no guest, no QEMU, no docker, no ssh to anything, no build. Nothing was written outside `P/` and
`/tmp/g3-s3-op-*` in WSL (`operator-record/after.console.txt`: nothing under `~/egw-exec`, `~/egw-tcg`,
`~/egw-images` or `~/yocto` is newer than this stream's first file; no bench process left; the execution clone
still at `80e833f`; `~/egw-exec/g3-t8t9-s3` does not exist).

## 1. Files

| File | What it is | sha256 |
|---|---|---|
| `g3_battery.sh` (2,261 lines) | the steps script finished for S3 | `142a5aad44045912d49fb61321e1724deff307f101bcacf71b374e5a93561745` |
| `g3_battery.README.md` (259 lines) | rewritten for S3 | `9fb4fe26d49f5b970c22466f2c1769e906f437ef1437455c301e153180fda9d5` |
| `operator-procedure.md` (112 lines) | new: the S3 operator procedure | `5fb9a13a41388efd6a842a1bda9e0b49311ab4f3cdccc4403fd78bedce5b82ed` |
| `operator-notes.md` | this file | — |
| `operator-record/` | NOT listed by the brief (section 6, deviation 10): the harness of the isolated exercises (`op_*.sh`) and their consoles | below |

Base: `base/g3_battery.sh` = the draft, `2221ff2f5e2c2671f22e3f5b13455457eb3516f46ea156fe8e55f2fab98d3f3b` (1,982 lines).
`git diff --no-index --stat base/g3_battery.sh g3_battery.sh`: `543 +++++…---`, **411 insertions, 132 deletions**
(README: 222 insertions, 172 deletions). LF only, UTF-8, no BOM, no carriage return (byte count); `bash -n` clean in
Git Bash and in WSL bash 5.2.21; the execution venv's `shellcheck` 0.11.0, read-only: `-S error` exit 0 and
`-S warning` exit 0 (`operator-record/static.console.txt`). No file names a tool or a vendor (the harness derives the
scratchpad path from its own location; the saved consoles show it as `<scratchpad>`).

## 2. The twelve points, where each is implemented (line numbers of the final file)

1. **Label and rows.** `ROWS_S3`, `session_rows`, `row_session`: 124–135. State directory `$EXEC/g3-t8t9-s3`: 106–107.
   `open`: the label case with the "authority is consumed" refusal of `S1`/`S2`: 910–917; the preconditions (no open
   session, no QEMU process; the root file system is the HALT of 957–963) and the removal of the S2-only block:
   924–941. The four loops: 603–605 (`open_label`), 929–930 (`cmd_open`), 2068–2069 (`close_outside`), 2201–2203
   (`cmd_status`), each under a `shellcheck disable=SC2043` (a one-label loop). `row`: 1627–1628 (other rows
   "unknown"). Texts that named S2 or the battery's records: 2023–2032, 2060–2063, 2178–2180. Usage: 2253. The order
   check (t9 only after t8 is classified or interrupted) is the draft's, untouched.
2. **Identifiers and constants.** `TOOLS`, `TREE`, `RUNBOOK_SHA`: 73–80. `ROOTFS_BEFORE_S3`: 85–88, used at 958–963.
   `row_itest_ids` t8, `T8_PREFIX`, `T9_IDS`: 176–182. The authority text in the workload field (`MANIFEST_PY`):
   403–404 (the key `battery` is kept, its value replaced).
3. **Four added identities in `verify_candidate`** (run at `open`, line 945, and before every row, line 1671):
   constants 89–96, paths 117–121, comparisons 659–670 (`want_sha` for the kernel, `qemuboot.conf` and the QEMU
   binary; `git -C "$OLD" rev-parse HEAD` and `status --porcelain` for the Yocto checkout). The paths are the frozen
   open driver's (`guest_session_open.sh` lines 112–119: `$DEP/Image-qemuarm64.bin`,
   `$DEP/…rootfs-20260918120819.qemuboot.conf`, `$BUILD/tmp/work/x86_64-linux/qemu-helper-native/1.0/recipe-sysroot-native/usr/bin/qemu-system-aarch64`,
   `git -C "$OLD"`); the values are those of S2's `001-identities-before-boot.stdout.txt`, read in the primary file.
4. **The gate's record against S2's.** Constant `GATE_IDENTITIES_S2` with its source quoted in the comment: 674–694;
   `gate_images_check`: 696–717; the gate attempt named at `open` (`gate_attempt` in `session-S3.env`): 1011–1014;
   the call before row t8, a halt with no attempt created: 1707–1716. **What is compared:** the six lines
   `identity <container> image=… image_id=… repo_digest=…` (each line of the gate file cut before ` container_id=`),
   as a sorted set, and there must be exactly six `identity` lines of that form. **Not compared:** `container_id`,
   `started`, and the build-identity lines that follow in the file. Read in the primary files: S1's and S2's gate
   records are equal in the three compared fields; their six container ids are also equal (the same container
   objects) and their start instants differ; the build-identity section is byte-identical in both.
5. **`-no-reboot`.** `T8_QEMU_IDENT`, mode `before`: comment 276–282, code 302–312 (exit 3 when found, exit 1 when the
   command line cannot be read); `t8_qemu` returns 3: 1299, 1309–1312; the halt before line a ("class: not started"):
   1347–1359.
6. **The wait.** Constants 99–101; the poll's command `T8_POLL_SH` and the boot id form: 1193–1202; `t8_wait_ssh`:
   1204–1295 (the bounded poll is line 1252; the counting rule 1261–1270; expiry 1244–1248; 74 at 1255–1258); the
   `timeout` check before the reboot: 1340–1345; the instant step a ended: 1361; the call and its halt: 1367–1380.
7. **Both markers after step c:** 1392–1404.
8. **The rule after step f:** 1423–1446 (`t8_reached_smoke` keeps its meaning at 1424; the new key `t8_smoke`).
9. **`fresh_row` and the attempt's name.** `T8_ADMITTED`, `row_attempt_suffix`: 183–187; `fresh_row`: 770–791; the
   name recorded (`attempt_name`): 1724; the halt before any step: 1741–1751.
10. **Unchanged:** the gate's no-comparison rule for T8 (1519–1520) and `t8_evidence` (1450–1460; comment only).
11. **Unchanged** (comment 1909–1914): `term`, `close`, the turn, the keepalive checks, `CUTOFF_S=10800` (97),
    `classify`, the environment copy. `operator-record/fndiff.console.txt` compares every function with the draft's:
    63 are identical, among them `cmd_term`, `take_turn`, `keepalive_check`, `environment_copy`, `cmd_classify`,
    `close_rows`, `gate_after`, `on_signal`, `run_step`, `steps_t9`, `no_stop`; 17 changed and 2 are new
    (`gate_images_check`, `row_attempt_suffix`); in `cmd_close` only the "What remains" lines changed (-2 +3).
12. **Never starts anything.** Stated at 36–39 and 1185–1189 and in the README (second paragraph, and
    "Restorations"). `static.console.txt`: outside comments the only `compose` command is the close's
    `… stop -t 130` (2153); no `compose up`, `start`, `restart`, no `docker start`, no `session_open.sh`; the only
    `kill`s are `kill -0` on the script's own console `tee` (551) and `kill -TERM -- -<row's group>` in `term` (1953).

Text-only changes without an S3 comment of their own: `want_sha`'s message ("the recorded identity is", was "the
packet names"), the comment above `verify_candidate`, step a's halt text (it now names what the merged line a
checks), the `row` line that states the ceiling ("counted from the row's start at up=…"), and the freshness halt of
`row` ("or an earlier attempt of the row that is not admitted exists").

## 3. What was run (all on the final bytes `142a5aad…`; consoles in `operator-record/`)

Harness: `op_setup.sh` (an isolated tree `/tmp/g3-s3-op-<name>`: a copy of `tools/` and `src/egw_experiments` of the
worktree `S/pb`, the runbook blob as the clone's runbook, `HOME` and every `EGW_*` inside, stub `git`, `sha256sum`,
`pgrep`, `ssh`; three real files read and copied, `itest-helpers.sh`, `tunnel.sh`, `ca.crt`, as the first
preparation's bench did; the real venv's python, read-only), `op_env.sh`, `op_funcs.sh` (the script's text loaded
without its last line, so that its functions can be called), `op_labels.sh`, `op_smoke_setup.sh`, `op_smoke.sh`,
`op_smoke_neg.sh`, `op_static.sh`, `op_fndiff.py`, `op_after.sh`. Consoles: `funcs`, `labels`, `smoke`, `smoke-neg`,
`static`, `fndiff`, `after` (`.console.txt`); every console of an exercise names the sha256 of the script it ran.

| Exercise (console) | Result |
|---|---|
| poll text (`funcs`, line 3) | `T8_POLL_SH` is, character for character, the text `gx` records in the frozen `guest_common.sh` (`6c9e7d5c…`): PASS |
| `verify_candidate` (`funcs`, 7–29) | all as recorded: 0, with the drivers, the export tool, the runbook, the helper file, `tunnel.sh` and `ca.crt` hashed for real (so `drivers_sha256` of the merged tree is `4a6a572d…`, and the runbook blob `4acf8de6…`); a differing kernel, `qemuboot.conf`, QEMU binary, Yocto commit, a Yocto checkout or a clone that is not clean: each returns 1 with its `WHY` |
| `gate_images_check` (`funcs`, 31–52) | S2's sealed record, S1's sealed record, and S2's with other container ids and instants: 0. A differing image id, repo digest or image reference, five or seven identity lines, a line of another form, an empty file, no file, no attempt recorded: 1. The constant equals lines 1–6 of S2's file cut before ` container_id=` |
| `fresh_row`, the name rule (`funcs`, 54–93) | the admitted attempt in both places: 0, two `admitted:` lines; another t8 attempt, the admitted name under another date or under `incomplete/`, any t9 attempt, a host file of an identifier: `NOT FRESH`, 1. With attempt01 present the frozen export tool names the new one `…_g3-qualification-t8_attempt02` |
| the QEMU reading (`funcs`, 95–137) | plain: exit 0; `-no-reboot`, `--no-reboot`, `-action reboot=shutdown`, `-action panic=none,reboot=shutdown`: exit 3; an argument that merely contains the word: exit 0; no process: exit 1; through `t8_qemu` (real `ex`): 3, 0, and `after` 0. The fake process was never signalled |
| the wait (`funcs`, 139–257) | printed a new id then ended **124**: NOT counted, the next poll counted (returned 0); the same with **255**; the saved id throughout: expiry, "reboot not shown within the wait", the last poll `timeout 3` with 3 s left; refused throughout with a 12 s budget: `timeout 12`, `timeout 7`, `timeout 2`, expiry; a banner and a two-line answer with exit 0: NOT counted; a saved id that is not a boot id: returned 3, no poll; helpers missing: 97, not counted; capture lost: returned 74; the script's own 20 s and 10 s with a 45 s budget and an ssh that stalls: `timeout 20` (20.0 s), then `timeout 15` (15.0 s: what was left), expiry (the caller read 46 s on the whole-second clock). After every case: no stub ssh and no `sleep 300` left |
| the rules after c and f (`funcs`, 259–373; fixture consoles, the real row files of `rows/`) | both markers: goes on; `CONTAINERS…` then a `STOP:`, only one marker, or the markers only inside the echoed line: HALT naming what is missing. Smoke complete, also with `lost` 3 and `late_confirmations` 41: no halt; a `STOP:`, the complete line followed by a `STOP:`, neither line, the complete line of another id: HALT |
| lines b and c for real (`funcs`, 375–399) | section 5 below |
| labels (`labels.console.txt`) | `open S1`, `open S2`: REFUSED "authority is consumed"; `open S4`, `open`: usage; `row t6`, `row t1-smokes`, `classify t7-ditto`, `term t6`: REFUSED unknown row; `row t8`, `row t9`: REFUSED (S3 not opened); no session or row state file written |
| one whole pass on FAKE rows (`smoke.console.txt`) | `open S3` → `row t8` (18 recorded steps, in order; poll 1 no answer, poll 2 counted; `QEMU PROCESS UNCHANGED`; five carriers; all markers; a fake smoke with `lost` 2: **no halt**; gate pass) → `classify t8 failed valid fail` → `row t9` started as `…t9_attempt01` (gate pass) → `classify` → `close`; exit 0 throughout; nothing started on the stub guest; the fake QEMU process never signalled |
| four negatives on FAKE rows (`smoke-neg.console.txt`) | kernel hash differs: HALT at `open`, nothing started; the gate's record differs: HALT before row t8, no attempt, `row t9` REFUSED; `-no-reboot`: HALT before line a (steps: `guest-state-before`, `t8-qemu-before`, then the gate), nothing rebooted, `row t9` REFUSED; attempt01 absent: the new attempt is `…attempt01`, HALT before any step (no recorded step at all) |

The whole pass and the negatives go beyond "the changed functions in isolation": they were cheap once the harness
existed, and they are not the benches of the real step files (fake rows, stub drivers).

## 4. For the bench stream

- `t8_wait_ssh PRE_ID T0` returns 0 (a poll counted), 1 (expired), 74 (a poll's capture lost), 3 (the saved id is not
  a boot id). `T8_QEMU_IDENT … before` exits 3 for `-no-reboot`; `t8_qemu before` returns 3.
- New state keys: `gate_attempt` (session); `attempt_name`, `t8_wait`, `t8_smoke` (row).
- The short-timing variant changes `T8_SSH_WAIT_S` and `T8_SSH_POLL_S` only (lines 99–100); `T8_SSH_READ_S=20` stays.
- A bench needs, beyond the draft's: a gate stub driver that leaves `environment/container_identities.txt` in its
  attempt (six `identity` lines in the frozen form) and prints the `DRIVER RESULT <run id>:` line; a `git` stub that
  answers `-C <Yocto checkout> rev-parse HEAD` and `status --porcelain`; a `sha256sum` stub (or files) for the
  kernel, `qemuboot.conf` and the QEMU binary under `EGW_YOCTO_CHECKOUT`; the root file system at `22e9da85…`; the
  admitted attempt01 under `<output root>/runs/2026-10-03/` (or in the attempts root) so that the new attempt is
  attempt02. `operator-record/op_smoke_setup.sh` does all of this with fake rows.
- A real `timeout` puts each poll in its own process group: a `pgrep -g <row's group>` does not list a poll.

## 5. The merged lines in a step shell (`set -v`, stdin closed, `exec 2>&1`)

Run for real: the row files `t8-b-wait-boot-id.sh` (`f38f7fad…`) and `t8-c-unaided.sh` (`df4ff611…`) as `rows/` held
them, through the real `run_step` → `hx` → `local_export exec`, with the real helper file and `tunnel.sh`, the host's
`timeout` (coreutils 9.4) and a stub `ssh` (`funcs.console.txt`, lines 375–399). Nothing misbehaved:

- **`[[ =~ ]]`, `timeout`, `ssh -n` (line b).** The first read printed a new id and stalled: the line's own
  `timeout 20` ended it, it was not counted, and the second read gave `REBOOT SHOWN: boot id … -> … (read 2 of at
  most 90, 10 s apart, each bounded to 20 s)`.
- **`<( )` (line c).** `CONTAINERS RETURNED UNAIDED`, then `PERSISTENCE SHOWN: 3 event directories intact;
  /var/lib/docker on /dev/vdb` (the `comm -23 <(…) <(…)` ran), then `observations read, exit 0`. With the
  event-directory read ended by its timeout after printing: `STOP: test 8: persistence NOT shown - a judged read did
  NOT end with exit status 0 (the event directories' read: exit 124; …)`, and the step itself took 20.0 s.
- **`set -v` doubles every marker text.** The row file's own line is echoed before it runs, so each console holds the
  marker twice: "lines that hold 'REBOOT SHOWN' anywhere: 2; at the start of a line: 1" (the same for `PERSISTENCE
  SHOWN`). The script's marker tests are anchored at the line start; an unanchored test would always pass.
- **`STOP:` detection differs by file.** `t8-a-reboot.sh` holds the literal `STOP:` (the runbook's comment line 1495),
  so `no_stop` uses `^STOP:` for step a; the five other t8 files hold none, so for steps b to f ANY `STOP:` in the
  console counts, also one inside a line. Line c prints guest text (the tail of the previous boot's `docker.service`
  journal, `systemctl --failed`): a `STOP:` in it would halt T8 although no helper stopped. S2's own read of that
  evidence (`005-t8-post-reboot-evidence.stdout.txt` of the session package) holds none. The rule is the battery's
  and was not changed; it is the safe direction, at the price of a possible false halt.
- **`timeout` and `term`.** coreutils `timeout` makes itself the leader of a new process group (shown in WSL: under
  `timeout` the child's pgid is `timeout`'s pid, not the caller's). The reads of lines b and c, and the script's own
  polls, therefore sit outside the row's process group: a `term t8` reaches the row's shell and `local_export exec`,
  not a read in flight, which ends by itself within its bound (20 s; 60 s for line c's observations). With
  `--foreground` the read would stay in the group but only its direct child would be ended at the timeout, leaving
  ssh holding the console's pipe: not used.
- **`ssh -n`** changes nothing in a step shell (stdin is already `/dev/null`); it matters only at a terminal.
- Not exercised here on the real files: lines a, d, e and f (they need the stubs of the repository's test module:
  the bench stream). Line a's reboot `ssh` has no `timeout`; in S2 that step returned (exit 0, 140 s with the quiet
  window).

## 6. Deviations from the brief, with reasons

1. **Point 8, the smoke's line.** The brief says the line "ends with `PROCEDURE COMPLETE`". The helper's line
   (runbook line 881, and S1's smoke consoles) is `TEST STATUS <id>: simulator exit=0 transcript (tee) exit=0 post=0
   -> PROCEDURE COMPLETE. This is NOT the verdict: …`. The script requires a line that starts
   `TEST STATUS itest-post-reboot-01-q2: ` and holds ` -> PROCEDURE COMPLETE.` (hard rule 8: the primary source).
2. **Points 7 and 8, "no `STOP:`".** The script uses the battery's `no_stop`: for steps c and f any `STOP:` in the
   console counts, not only one at a line start (section 5). At least as strict as the brief's wording.
3. **Point 5.** Besides `-no-reboot` the reading also stops on `--no-reboot` and on an argument that sets
   `reboot=shutdown` (`-action`): QEMU's other spellings of the same setting. Not asked; it can be cut to the one
   spelling by removing the second `-e` pattern and the `?` (line 305).
4. **Point 6, four additions.** (a) `timeout` must be on `PATH` before line a, else a halt with the reboot not issued
   ("never without `timeout`"). (b) A saved id that is not a boot id returns 3 before any poll: nothing could be
   compared with it. (c) The answer must be, as a whole, one id of the UUID form: stricter than the merged line b's
   `^[0-9a-f-]{36}$` (the draft took the first matching line of the console). (d) The sleep between two polls is cut
   to what is left of the budget, so the wait ends at 900 s and not up to 10 s later. A poll is no longer run through
   `gx`: ssh's 255 is reported as 255, not turned into 97.
5. **Point 2, "`-q2` everywhere".** The table entries of the battery's rows t1 to t7 still hold their `-q1`
   identifiers (lines 168–175 and 1087). No subcommand reaches them (`row`, `classify`, `term` refuse those rows as
   unknown: `labels.console.txt`); removing them would have meant pruning six tables and the harness-row code (hard
   rule 7). Said in the script (124–127) and in the README.
6. **Point 2, the workload field.** The authority text replaces the value; the key is still named `battery`, so that
   the field has the name S1's and S2's packages gave it.
7. **Point 9.** The name is checked right after the attempt is created: under a wrong name nothing else is recorded
   in the attempt (no workload field, no copies), and nothing is registered after the row.
8. **Point 4.** Compared before row t8 only, not also at `open`: a difference is therefore found with the guest up,
   and the session is then closed. The build-identity lines are not compared.
9. **`operator-procedure.md`, the classification table.** A fourth row, "Not started", states the request's sentence
   after its table and its section 5 item 5; the request's table has three rows.
10. **`operator-record/`** is not among the files the brief gives this stream. It holds what was run and its
    consoles, as the brief asks to be recorded.
11. Texts of the unchanged parts still name the battery in places (`open`'s "opens the session for the battery",
    `term`'s "T7's fault job", the environment copy's "harness rows"): left, point 11.

## 7. Not done

- The benches of the real step files and of the final constants (the 900 s expiry, `term t8` during the wait, a
  `STOP:` in each of a to e, test 9's steps): the bench stream.
- Nothing was run against the real `HOME`. Not measured: `git status --porcelain` in the real Yocto checkout (now run
  at `open` and before each row; the frozen open driver runs it once per open).
- No real ssh: how OpenSSH ends when `timeout` sends TERM to its group, and how long a read against a guest that is
  going down takes, are not shown.

## 8. Open points

1. The `-q1` entries of the unreachable rows (deviation 5): keep, or prune in a later preparation.
2. `open` does not require the admitted attempt01 to exist. If it were in neither place, `open` would pass and
   `row t8` would halt on the attempt's name with the guest already up. Today it is in both places (read:
   `~/egw-exec/attempts/20261003T142310Z_g3-qualification-t8_attempt01` and `output_test/runs/2026-10-03/`).
3. Any `STOP:` inside guest text printed by line c halts T8 (section 5): a possible false halt, never a false pass.
4. A poll or a runbook read in flight is not reached by `term` (section 5): it ends within 20 s (60 s).
5. The merged lines' own bounds add up to more than the 135 min ceiling (the request, section 4): the ceiling is the
   binding limit and only the operator's `term` enforces it; the script prints the minutes used when the wait starts
   and `status` prints `PAST ITS CEILING`.
6. The gate comparison rests on the frozen driver's line form. S1's and S2's records have it; another form on S3's
   boot would be a halt before T8 ("not six lines of the recorded form"), not a silent pass.
7. One Windows quoting trap met while working: a `wsl … bash -lc '…'` line that holds a backslash before a double
   quote is cut short by the Windows command line. The README's launch lines hold no backslash.
