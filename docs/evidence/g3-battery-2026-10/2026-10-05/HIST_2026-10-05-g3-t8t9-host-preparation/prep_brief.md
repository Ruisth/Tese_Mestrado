# Preparation of session S3 (tests 8 and 9 only) — brief for the script streams (2026-10-04)

S = `<S>`
(from WSL: `<S>`)
P = `S/g3/s3prep` — the ONLY directory any stream writes in (plus `/tmp/g3-s3-*` inside WSL for benches).
OT = `C:/Users/ruimf/Documents/Projeto Mestrado/output_test` (read-only for the streams).

## What this is

An MSc project ("edge gateway": an ARM64 Yocto guest under QEMU/TCG on a WSL2 host, six containers). A G3 qualification
battery ran on 2026-10-02/03 (sessions S1, S2) with operator tooling kept OUTSIDE the repository. Test 8 (persistence across
a guest reboot) halted because its procedure assumed QEMU exits on reboot; the procedure was corrected in the runbook and
merged as `8e49261`. Test 9 was not run. One more session, S3, will run ONLY test 8 and test 9, with fresh identifiers.
This work prepares the operator tooling for S3. No guest runs during the preparation.

Read first (all read-only):
- the decision summary `OT/decisions/2026-10-04_g3-t8-t9-s3-decision-summary.md` (one page: four choices, two conditions);
- the request `OT/decisions/2026-10-04_g3-t8-t9-session-request.md` (sections 2 to 7 are the specification of what S3 does);
- the merged runbook blob `P/runbook.8e49261.md` (sha256 `4acf8de6…`, 1,623 lines; section 7 "### Test 8" lines 1484-1503,
  "### Test 9" lines 1505-1537; the helpers of section 6.1 around lines 609-1155);
- the frozen drivers at the merged commit: worktree `S/pb` (`tools/session/*.sh`, `tools/session/guest/*.sh`,
  `src/egw_experiments/local_export.py`); they are NOT to be modified;
- the tooling of the first preparation, as sealed: `S/g3/battery/prep/` (scripts, `rows/`, `verify-*.md`, README) and
  `S/g3/battery/ops/`; the DRAFT of the operator script for the corrected test 8 with its notes: `S/g3/post/`
  (`g3_battery.sh`, `g3_battery.README.md`, `D-notes.md`, `bench/`);
- facts already extracted, as leads only (they may be wrong; check the primary file): `S/g3/t8t9/facts-tooling.md`,
  `facts-procedure.md`, `facts-sut.md`, `facts-rules.md`.

`P/` already holds a working copy of every script to revise, and `P/base/` an untouched copy of each (for diffs).

## Hard rules (every stream)

1. Write ONLY under `P/` (and `/tmp/g3-s3-*` in WSL for benches). Never write under `~/egw-exec`, `~/egw-tcg`, `~/yocto`,
   `output_test`, `ChatGPT/`, the repository worktrees (`S/pb`, `S/cand`, ...) or the sealed first-preparation directories.
2. No guest, no QEMU, no docker, no ssh to anything, no build. Never run a script of `P/` against the real `HOME`:
   benches run in WSL with `HOME` and every `EGW_*` variable pointing inside `/tmp/g3-s3-<name>`, with stub `ssh`, `scp`,
   `curl`, `pgrep`, `ss`, `git`, `sha256sum` and so on first on `PATH`, exactly as the first preparation's benches did
   (`S/g3/battery/prep/verify-safety/bench_setup.sh`, `S/g3/post/bench/bt8_setup.sh`). `g3_hostprep.sh` is NOT run by any
   stream (it writes on the host): only `bash -n` and static checks.
3. WSL invocation from the Bash tool: `MSYS_NO_PATHCONV=1 wsl -d Ubuntu-24.04 --exec bash -lc '<command>'`. The venv's
   python is `~/egw-exec/venv/bin/python` (read-only use, with `PYTHONDONTWRITEBYTECODE=1`). Do not start long-lived
   background processes that outlive your stream; end every fake process a bench started.
4. Files are LF-only, UTF-8, no BOM. On Windows never use Python `write_text` without `newline="\n"` (it writes CRLF):
   edit with the Edit/Write tools, or write bytes. After editing, check `grep -c $'\r'` is 0 and `bash -n` passes.
   Python or shell scripts that contain backslashes are created with the Write tool, never through a shell heredoc.
5. No secret on a command line or in a record; never `set -x` anywhere near the simulator (its password is on its argv);
   the sealed scripts use `set -v` in step shells: keep that.
6. British English in every text; ISO dates. Do not name any AI tool or vendor in any file.
7. Keep changes minimal and local: the battery's scripts worked through two sessions. Change what S3 needs, nothing else;
   no refactoring, no renaming beyond what is listed. Where the first preparation's verifications
   (`S/g3/battery/prep/verify-*.md`, `fix-notes.md`) fixed a defect, do not reintroduce it.
8. If something in this brief contradicts a primary source (the runbook blob, a frozen driver, a sealed record), follow
   the primary source and say so in your notes; do not guess.

## Fixed values

- Tools and procedure: commit `8e492613d36490a560ae56beabd6d5c2c01a8696`, tree `2f0514837f267d8975f7071041aad14a5c18dcab`.
- Runbook `docs/setup/qemu_integrated_gateway.md` at that commit: sha256
  `4acf8de679d26024dd463dd8c096a5c3e66b7ab5ec5a397f1a7bf08768f2a9db`, 1,623 lines. The extraction rule's source, the test
  module `src/tests/test_runbook_itest_helpers.py` at that commit: sha256
  `fe8baa60d41a088807e071a462d4ff36674f7325ed18a9e480159b14db719ff1`.
- Unchanged since `80e833f` (verify, do not assume): helper heredoc `e5eba37e529a47885a8aea0e718d25ac71ce1e31a0c1a381b4520fe4c914b4fb`
  (545 lines); `tunnel.sh` `38f5cae9f0a3632e1bf0590f6ac71a9dc46e843f367d8ef9aabe51bedd6fe1d1`; `ca.crt`
  `556e139f1db12be032f6e6877a73526457a96e1872a5f8ea7f7e4a554abcb8ff`; `drivers_sha256`
  `4a6a572dc1e2b54754c3a8dec38e6d2392227efc61ee710886ad9ad5729a39a5`; `local_export.py`
  `544c9b3d451f0a6c3391102ac4031fe93bee79a0b0b9bcd6f41c893592d2422b`; every other identity the battery's scripts pin
  (images.lock.env, compose.yaml, mosquitto.conf, CONTRACTS.md, the controller record and archive, the deployment and
  schemas trees, the launcher).
- Root file system `.ext4` expected before S3: `22e9da8533541582a2e4549f4c37f2b80f0f6a9bd3a5f0dd5e13605d7269efcd` (the value
  S2's close recorded: `OT/runs/2026-10-03/HIST_2026-10-03-g3-battery-s2-operator-records/state/session-S2.env`).
- Added comparisons for S3 (today only recorded by `guest_session_open.sh` lines 112-119; take the paths from there and
  from S2's record `OT/runs/2026-10-03/20261003T132249Z_guest-session_attempt09/console/001-identities-before-boot.stdout.txt`):
  kernel `Image-qemuarm64.bin` `4457ef38e4cb6b8c2f0061ec504a23666490781ca3b4facd15a588b7a9609037`; `qemuboot.conf`
  `7739c945f9b1400e216341d924d81642b807ae213cb685e34a5d3e51e6fc90e4`; the QEMU binary `qemu-system-aarch64`
  `5d389c653449d338397f56b3ffa24fb387ec4aab5cd205b2f1a735aa14391061`; the Yocto checkout at
  `489bc9e5b5b0660026ea2630b8d1d124049ba2ce` with a clean status.
- Session label `S3`. Rows: `t8`, then `t9`. State directory default `$EXEC/g3-t8t9-s3` (the `EGW_G3_STATE` override
  stays); the battery's state directory `~/egw-exec/g3-battery` is never written.
- Identifier suffix `-q2`: prefix `itest-reboot-q2` (60 literals in test 8's lines: 15, 8, 32, 0, 5 on runbook lines 1486,
  1496, 1497, 1498, 1499), smoke run id `itest-post-reboot-01-q2` (1, line 1500); test 9: `itest-tls-wrongca-q2` (1),
  `itest-auth-wrongpw-q2` (4), `itest-notls-q2` (3); `itest-acl-$T` is never changed.
- Test 8's six step files (one runbook `host$` command each; line 1486 carries its comment lines 1487-1495):
  `t8-a-reboot.sh` (1486-1495), `t8-b-wait-boot-id.sh` (1496), `t8-c-unaided.sh` (1497), `t8-d-tunnel.sh` (1498),
  `t8-e-state.sh` (1499), `t8-f-smoke.sh` (1500).
- Test 9's block is byte-identical to the frozen one, 8 lines lower (old 1501-1526 = new 1509-1534; the exposure
  sentence old line 1529 = new line 1537): `t9-a.sh`, `t9-b.sh`, `t9-c.sh`, `t9-de.sh` (verify each range against the
  old row files, which must come out byte-identical except for the suffix), and the prose-only `t9-exposure.sh` (written
  from the same constant as before; only the commit, sha256 and line number in its header change).
- Authority text recorded in each row's workload field (replaces the battery's): `G3 qualification, session S3: tests 8
  and 9 only (request of 2026-10-04; decision summary output_test/decisions/2026-10-04_g3-t8-t9-s3-decision-summary.md)`.
- Earlier attempt admitted for row t8: exactly `20261003T142310Z_g3-qualification-t8_attempt01` (S2's halted one). The new
  attempt is expected to be numbered `attempt02` by the export tool (it numbers by scenario slug).

## Stream ROWS — owns `P/g3_extract_rows.py`, `P/g3_check_rows.sh`, `P/g3_rows_dryrun.sh`, `P/rows/`

Revise the three scripts for the merged commit, S3 and `-q2`:
- extraction: `RUNBOOK_COMMIT`, `RUNBOOK_SHA256`, `RUNBOOK_LINES`, `RULE_SOURCE_SHA256`, `SUFFIX = "-q2"`; S3 extracts ONLY
  test 8 (six files) and test 9 (four fenced files and the exposure step): remove the rows of tests 1 to 7 from what is
  written and from the asserted totals, but keep the script's own checks of the extraction rule against the test
  module's functions and of the runbook's identity; `session` is `S3` for both rows; the counts above are asserted per
  file; the manifest keeps its form (runbook identity, rule, substitution rule with counts, rows, per-file line numbers,
  sha256 before and after, diff hash, `bash -n`). The manifest's note for t8 describes the corrected flow (no QEMU-exit
  wait, no re-launch).
- Run it on `P/runbook.8e49261.md` (it asserts the sha256) into `P/rows/`; run its `--check` (0 differences).
- checker: the commit, hash, line table, file list and `-q2`; it still reads the blob by `git show` from the clean
  clone and requires that clone's HEAD at the commit, so it cannot pass before the clone moves: make it runnable ALSO
  with an explicit `--blob <file>` (or an environment variable) that reads the blob from a file whose sha256 it asserts,
  and run it that way on `P/runbook.8e49261.md`; say in its usage which mode proves what.
- dry run: the files it names; it runs in WSL under `/tmp/g3-s3-dry-rows.*`.
- Deliver in `P/rows-notes.md`: what changed and why (with `diff` sizes against `P/base/`), the consoles of the
  extraction, of `--check`, of the checker (blob mode) and of the dry run saved under `P/rows-record/`, the list of files
  with sha256, and for each test 9 file the proof that it equals the first preparation's file with `-q1` replaced by
  `-q2` (and the header of `t9-exposure.sh`), and for each test 8 file the proof that removing `-q2` gives the runbook
  lines byte for byte.

## Stream OPERATOR — owns `P/g3_battery.sh`, `P/g3_battery.README.md`, `P/operator-procedure.md` (new, for S3)

`P/g3_battery.sh` starts as the DRAFT (`S/g3/post/g3_battery.sh`, sha256 `2221ff2f…`), written before the merged lines
gained `timeout 20`, the judged event-directory and mount reads, `PERSISTENCE SHOWN` and the exit-status rule. Finish it
for S3. Required changes (each must be findable by a comment naming S3):

1. Label: `open S3` only. `S1` and `S2` are refused with a text saying their authority is consumed. Rows of S3: `t8`, `t9`,
   in that order (the order check stays). Remove the S2-only precondition; S3's preconditions: no QEMU process, no open
   session, the root file system at the expected value above. The four `for l in S1 S2` loops and the usage follow.
2. Identifiers `-q2` everywhere (`row_itest_ids`, `T8_PREFIX`, the smoke id, `T9_IDS`); the constants `TOOLS`, `TREE`,
   `RUNBOOK_SHA`, the root file system value; the authority text above in the workload field.
3. `verify_candidate` (run at open and before every row) additionally compares the kernel, `qemuboot.conf`, the QEMU
   binary and the Yocto checkout (commit and clean status) with the values above; a difference is a halt of the same
   kind as the existing identities (packet section 4, halt 6).
4. Before row t8 starts its steps: compare the gate package's record of the running images with S2's. The frozen
   `gate_health.sh` writes `environment/container_identities.txt` in its attempt; S2's is
   `OT/runs/2026-10-03/20261003T132836Z_g2-gate-preconditions_attempt06/environment/container_identities.txt`. Compare, per
   service, the image reference, the image id and the repo digest (not the container ids or anything time-dependent)
   against constants taken from S2's file (quote the source lines in a comment); a difference is a halt and row t8 is
   not started. Decide from the file's real form what is stable; say what you compared.
5. Test 8, before line a: the existing QEMU reading (pid, start instant, disks) also reads the command line for
   `-no-reboot`; if it is there, halt before the reboot is issued (class "not started"), line a not run.
6. The wait before line b (decision summary, condition A; do not weaken the merged lines' own rule):
   - budget 900 s measured on `/proc/uptime` (whole seconds) from the instant step a ended; one poll every 10 s;
   - EVERY poll bounded by the host's `timeout` with a duration of min(20, the budget that remains) seconds, never 0 and
     never without `timeout` (when less than 1 s remains there is no further poll: the wait has expired);
   - a poll counts only when it ended with exit status 0 AND its answer is a boot id of the kernel's form AND that id
     differs from the saved one (`$P/$T8_PREFIX.boot_id.pre`); a poll that printed a matching-looking id and then ended
     124 or 255 (or any non-zero) does not count, its console is kept as the recorded step it already is, and the wait
     goes on;
   - `gx` is a shell function of the frozen `guest_common.sh` and cannot be wrapped by `timeout` directly: bound the
     command it records (read `S/pb/tools/session/guest_common.sh` lines 40-80 and `tools/session/guest/session_common.sh`
     for `gssh`), keeping each poll a recorded step of the row's attempt and keeping status 74 (console capture lost) a
     halt of its own;
   - expiry is a halt whose text says "reboot not shown" within the wait (inconclusive / not demonstrated, not by itself
     a failure of the system); line b is then not run;
   - the wait, its preamble and the later steps share the row's 135 min ceiling: nothing may reset the row's start
     instant or its recorded ceiling; say in the README that the ceiling is counted from the row's start.
7. After step c: require BOTH `CONTAINERS RETURNED UNAIDED` and `PERSISTENCE SHOWN` at line start and no `STOP:`; the halt
   text names which is missing.
8. After step f: record a halt unless the smoke's console shows a line starting
   `TEST STATUS itest-post-reboot-01-q2:` that ends with `PROCEDURE COMPLETE` (see the helper `run_test`/`sim_post` in the
   runbook around lines 870-895 for the exact line) and shows no line starting `STOP:`. With that line and no `STOP:`
   no halt is recorded even when `lost` or `late_confirmations` is above 0 (the operator classifies T8 as failed; T9
   may then run after the gate). The key `t8_reached_smoke` keeps its meaning (step f was reached).
9. `fresh_row`: for `t8`, the one earlier attempt named above is admitted (in the WSL attempts directory and under
   `output_test/runs/2026-10-03/`), any other earlier attempt of the slug is NOT FRESH; for `t9` none is admitted.
   After the row's attempt is created, its name is recorded; if it does not end `_g3-qualification-t8_attempt02`
   (`_g3-qualification-t9_attempt01` for t9) the row halts before any step.
10. The no-comparison gate for T8 and the previous-boot journal and kernel OOM reads stay as the draft has them.
11. Nothing else changes: `term` (TERM to the row's group, never KILL, refusal when QEMU or the keepalive is in the
    group), `close` (the recorded `compose stop -t 130` with both env files, then the frozen close driver; the paths for
    a guest that does not answer and for no QEMU left), the turn lock, the keepalive checks, the cut-off
    (`CUTOFF_S=10800` on `/proc/uptime`), `classify` (the six pairs), the environment copy at open.
12. The script never runs `compose up`, `start`, `restart` or `docker start`, never re-launches QEMU, never signals it.
    State this in the README together with condition B of the decision summary: the frozen preflight driver's stack
    start at open is the prescribed one; after the reboot nothing on the guest is started, restarted or recreated by
    hand; line d's tunnel step and the safe-close operations stay and are never presented as unaided recovery.

`P/g3_battery.README.md`: bring it to S3 (subcommands, the S3 flow step by step, every halt with its text and what the
operator does next, the known host tunnel case at line d, launch rules, what is unverified). `P/operator-procedure.md`:
the S3 operator procedure in one to two pages (sequence, the classification table of the request's section 6, the stop
conditions of its section 5 with item 9 as clarified, the controlled close, what to do when the guest does not answer
with QEMU alive: preserve the state, signal nothing, ask Rui).

Deliver `P/operator-notes.md`: each of the 12 points with the line numbers where it is implemented, the `diff --stat`
against `P/base/g3_battery.sh`, anything you could not do and why, and anything in the merged lines that would misbehave
in a step shell (`set -v`, stdin closed: process substitution `<( )`, `[[ =~ ]]`, `timeout`, `ssh -n`) with evidence.

## Stream HOST — owns `P/g3_hostprep.sh`, `P/seal_prep.sh`, `P/ops/*`

- `g3_hostprep.sh` for S3: refuses when a QEMU process runs or a session is open; fetches from the clone's `origin` (the
  Windows repository) and checks out `8e49261…` detached — fetch the remote branch and require that the commit is an
  ancestor of, or equal to, the fetched tip and that `git cat-file -e` finds it (do NOT require the tip to equal it);
  **if the clone has local changes (a non-empty `git status --porcelain`) or its HEAD is neither `80e833f…` nor
  `8e49261…`, stop and change nothing: nothing is discarded** (decision summary, choice 1); requires tree `2f05148…`, a
  clean status and unchanged branches afterwards. The read-only "no rebuild" diff against `489bc9e…` stays. Identity
  comparisons against the values above, including the four added ones, the new runbook hash and the expected root file
  system value; `drivers_sha256` computed the way the battery's script did. Helper regeneration as before (predecessor
  kept, expected `e5eba37e…`, 545 lines). Freshness: the five `-q2` identifiers with no host artefact (itest, itest-replay,
  pilot results, output_test, attempts); the earlier-attempt check admits the battery's attempts as they are and
  requires that no `…_g3-qualification-t8_attempt02` and no `…_g3-qualification-t9_attempt*` exists; the two campaign-plan
  entries of the battery are not checked (S3 runs no harness row). The offline, read-only `debugfs -c` listing of the
  guest's event directories for the two ids that would leave one, with the root file system hashed before and after.
  The record directory is an argument; it never overwrites its console.
- `seal_prep.sh` and `ops/seal_ops.sh`, `ops/seal_ops_finish.sh` for S3: package names
  `HIST_<UTC date>-g3-t8t9-host-preparation` and `HIST_<UTC date>-g3-t8t9-s3-operator-records`, the S3 file set, the secret
  sweep (and fix the known false alarm: `seal_ops.sh` stopped on its own private-key pattern text in both sessions; the
  sweep must not match the script's own pattern line), never overwriting a package.
- `ops/g3_go.sh`, `ops/g3_wait.sh`: the paths of `P/` instead of the first preparation's.
- Deliver `P/host-notes.md`: what changed (with `diff --stat` against `P/base/`), `bash -n` for each script, every
  hard-coded value with where it was taken from, and the exact command lines the operator will run for the host
  preparation and for sealing. Do not run `g3_hostprep.sh`.

## Stream BENCH (after ROWS and OPERATOR) — owns `P/bench/`; may correct `P/g3_battery.sh` for defects the benches show

Bench the FINAL bytes of `P/g3_battery.sh` in WSL under `/tmp/g3-s3-bench/<scenario>`, building on
`S/g3/post/bench/bt8_setup.sh` / `bt8_run.sh` and `S/g3/battery/prep/verify-safety/bench_setup.sh` (fake QEMU process with
real `/proc/PID/cmdline`, stub commands, `HOME` and `EGW_*` inside the bench, the real venv python).
Use the REAL step files of `P/rows/` for test 8 and test 9: the helpers they call (`wait_ready`, `drained`, `metrics`,
`$REC`, `run_test`, `tunnel_up`, `stop`, ...) come from the real helper file regenerated from the runbook blob, and the
commands those helpers call are stubs; the repository's own test module holds stubs written for exactly these lines
(`S/pb/src/tests/test_runbook_itest_helpers.py`: `STUB_SSH`, `STUB_CURL`, `STUB_PYTHON`, `STUB_SCP`, `STUB_SS`, `STUB_SLEEP`,
`STUB_TIMEOUT`, the `Bench` class and `t8_prepare`): reuse them (import the module's constants from a small Python
script) rather than writing new ones. If a part cannot run on the real step files, say exactly which and why, and
bench that part with a fake file.

Scenarios, each with its console saved under `P/bench/record/` (the console starts with the sha256 of the script run):
 1. success: open S3, row t8 (a to f with every marker), classify, row t9 (four steps and the exposure step), close;
 2. the wait: (i) a poll that prints a valid different id and ends 124 is not counted, a later genuine success is;
    (ii) the same with 255; (iii) expiry on the final constants (the real 900 s budget; this one bench takes 15 min: run
    it once on the final bytes); (iv) with less than 20 s left the poll's `timeout` is the remainder and never 0;
 3. `-no-reboot` on the fake QEMU's command line: halt before line a, nothing rebooted;
 4. a different QEMU process, or none, after the wait: halt, b to f not run;
 5. a `STOP:` in each of a, b, c, d, e in turn: halt, no later step, `row t9` refused;
 6. step c without `PERSISTENCE SHOWN`: halt;
 7. the smoke: (i) `PROCEDURE COMPLETE`, no `STOP:`, `lost` above 0: no halt, `row t9` starts after classification;
    (ii) a `STOP:` in the smoke: halt, `row t9` refused; (iii) neither line: halt;
 8. identities: a kernel hash that differs at open: halt; a gate record that differs from S2's: halt before t8;
 9. freshness and labels: the recorded attempt01 admitted; another earlier t8 attempt refused; `open S1`/`open S2`
    refused; the new attempt's name not `attempt02`: halt;
 10. test 9: a `STOP:` in (a), (b), (c) or (d)+(e) stops the later steps; the exposure step only after (d)+(e) clean;
 11. `term t8` during the wait: TERM to the row's group, the attempt exported as interrupted, the fake QEMU untouched.
A short-timing variant of the script (the two wait constants only) may be used for scenarios other than 2(iii); record
its sha256 and the two differing lines, as the draft's bench did.
After the benches: no fake process left, nothing written outside `/tmp/g3-s3-bench` and `P/bench/`, the real
`~/egw-exec` and `~/egw-tcg` untouched (show the listing times or hashes before and after).
Deliver `P/bench-notes.md`: per scenario what was run, the expected and the observed (quote the decisive console lines),
PASS or FAIL, every defect found with the correction made to `P/g3_battery.sh` (line numbers) and the re-run, the final
sha256 of `P/g3_battery.sh`, and what was NOT benched.
