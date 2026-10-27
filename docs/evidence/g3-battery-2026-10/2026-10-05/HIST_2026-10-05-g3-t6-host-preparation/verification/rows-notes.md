# Stream ROWS — notes (preparation of G3 session S4, test 6 only, 2026-10-05)

`S`, `P` and `OT` are the brief's three directories. Everything here was done offline, in WSL (Ubuntu-24.04,
bash 5.2.21, the system `python3` 3.12.3 with `PYTHONDONTWRITEBYTECODE=1`), with `HOME` and `EGW_EXEC_REPO` inside
`/tmp/g3-s4-rows-record.*` and `/tmp/g3-s4-dry-rows.*` (both removed when the run ended). No guest, no QEMU, no
docker, no ssh, no build, no git write in any worktree. Nothing was written outside `P/rows`, `P/rows-record`,
`P/rows-notes.md`, the three scripts of this stream and those temporary directories.

## Result

- The three scripts are revised for the merged commit `1fd9792`, session `S4` and test 6 only. Nothing is
  substituted: `controller_restart-r04` is the runbook's own literal.
- The extraction ran on `P/runbook.1fd9792.md` (sha256 asserted) into `P/rows`: **3 files** — `t6.sh` (the eight
  `host$` lines 1421–1428, prompt removed), `t6.sh.diff` (empty, as the battery's was) and `rows.manifest.json`.
  Its `--check` finds **0 differences**. The rule was checked against the test module's own `_section` and
  `_host_commands` (rule source `b63ef7d8…`, the worktree file and its copy in `P` alike).
- The checker in **blob mode** on `P/runbook.1fd9792.md`: 22 `ok`, 0 `FAIL`, `ROW FILES OK`; `git` called 0 times.
- The dry run: ten step-form cases of `t6.sh` as expected, twelve altered copies refused by the checker, the
  unaltered copy accepted, 0 `git` calls; `DRY RUN AS EXPECTED`, exit 0, no directory left.
- The proofs: `t6.sh` is runbook lines 1421–1428 with `host$ ` removed, byte for byte (two tools); against the
  battery's `t6.sh` the diff is exactly hunks `1c1`, `5c5`, `6a7`. `PROOFS HOLD`.
- Not done here, by design: the checker's clone mode against the execution clone (it cannot pass before the clone
  is at `1fd9792`; see "Open points"). It was exercised on a throw-away clone.

## 1. What changed, and why

Sizes against `P/base/` (`git diff --no-index --numstat`; `diff -u | wc -l`; from `rows-static.console.txt`):

| Script | base sha256 | new sha256 | lines | added / removed | `diff -u` lines |
|---|---|---|---|---|---|
| `g3_extract_rows.py` | `11c19af7…604598` | `e3aa669d38c6320db1bfa853fd25834ac4d848e6fb04c6e9f341fbfd39c23050` | 716 → 598 | 131 / 249 | 515 |
| `g3_check_rows.sh` | `2f1863b0…b64b11d` | `ae7038d3e046afa921ca7084240388bd8e87fe4c34797b9c750bffedc4d48494` | 204 → 200 | 68 / 72 | 224 |
| `g3_rows_dryrun.sh` | `fbbca2f6…8c503e3` | `1f32c56c32895b5d2cfd466b5e18db8cc3465a295df61085527294f75983c994` | 121 → 213 | 163 / 71 | 276 |

The three base copies equal S3's first-preparation scripts (`S/g3/s3prep/`, same sha256) and are untouched. Every
change of behaviour stands under a comment naming `S4`.

### `g3_extract_rows.py`

- Constants: `RUNBOOK_COMMIT` `1fd9792b…`, `RUNBOOK_SHA256` `31716593…`, `RUNBOOK_LINES` 1624, `RULE_SOURCE_SHA256`
  `b63ef7d8…`.
- No substitution: `SUFFIX = None`, `OLD_IDS = []`, `TOTAL_COUNTS = {}`, `UNCHANGED = ["controller_restart-r04"]`.
  With no id the token's alternation would be empty and match the empty string everywhere, so `TOKEN` is then a
  pattern that never matches (`(?!)`). The per-file assertion is now: the step file is the extracted text, byte
  for byte. `EARLIER_SUFFIXES` (`-q1` of S1/S2, `-q2` of S3) replaces `BATTERY_SUFFIX`: neither may stand in the
  extracted text nor follow the run id.
- `HEADS`: only `### Test 6` (8 commands, 8 lines, `ec8ac010d79ba87f`). The value was computed apart from the
  script (`sed -n '1421,1428p' | sed 's/^host\$ //' | sha256sum`, recomputed at the top of
  `rows-extract.console.txt`) before it was pinned.
- Literals asserted: the plan-entry literals of the text are exactly `controller_restart-r01` (in line 1421's
  comment) and `controller_restart-r04`, once each (`PLAN_COUNTS`); no `itest-` id. Three markers (`MARKERS`) name
  what the block does: line 1421 opens with `RID=controller_restart-r04; F6=used; `, line 1425 holds
  ` --restart-transition-rule 1a-option-a-2026-10-05; HR=$?; ` once, line 1427 opens with the exactly-once check.
- `STEPS`: one file, `t6.sh`, row `t6`, session `S4`, lines 1421–1428, every line a command start. `ROWS`: `t6`
  (session `S4`) with a one-sentence note saying what the block does (r04 with its seed, the restart at +300 s
  under rule `1a-option-a-2026-10-05`, then — each only when `T6=ok` — `delta` and `acceptance --exactly-once` on
  the post-drain copy, and `analyze`). Asserted totals: 8 extracted lines, 1 file, 8 lines in it.
- Removed with test 9's row: the prose-only step `t9-exposure.sh` and its constants (`T9_LINE`, `T9_QUOTE`,
  `T9_BODY`, `OPERATOR_T9`) — S4 has no prose-only step, as S3 removed test 1's. The STEPS and ROWS of tests 8 and 9
  are gone with them.
- `forbidden_out`: the path components `t6m`, `t6int` (this preparation's read-only worktrees) and `s3prep`,
  `s3bprep`, `battery` (the sealed earlier preparations, hard rule 1) are refused as well. `other_commit_rows` is
  unchanged; it now protects S3's rows of `8e49261` as well as the battery's.
- The manifest keeps its form and schema name: runbook identity, rule (with `checked_against_the_frozen_functions`),
  `families`, `substitution_rule` (now `suffix` null, `ids` [], `token` "none: session S4 substitutes no id", and
  what is asserted), `rows`, per-file line numbers, sha256 before/after (equal), diff (empty) and `bash_n`. The
  notes are rewritten for S4 (nine).
- Kept and not called: `only_defines()` and the `definitions` branch (a sentence in its docstring says so for S4).

### `g3_check_rows.sh`

- Commit `1fd9792…`, blob sha256 `31716593…`, 1624 lines; the line table is one row, `t6.sh|NR>=1421&&NR<=1428|`
  (no id); "exactly the 3 expected files (1 step, 1 diff, the manifest)"; the manifest must hold one row `t6` of
  session `S4`, runbook 1624 lines, substitution none (no suffix, no id, `sha256_before` = `sha256_after`, diff
  0 bytes).
- Byte identity is now `cmp` of the file itself with the blob's lines (no `-q2` to remove).
- The clone mode and the `--blob` mode are kept as S3 left them; usage text and header name `1fd9792`.
- Added for S4: the heading on 1416, the one fence 1420/1429 before test 7's heading on 1437 and eight `host$`
  lines 1421–1428; no `-q1`/`-q2` in those lines nor in any step file; `controller_restart-r04` once, opening line
  1; the plan-entry literals exactly r01 and r04; no `itest-` id; line 5 and no other hands the harness
  `--restart-transition-rule 1a-option-a-2026-10-05`; line 7 and no other is the exactly-once check, run only when
  `T6=ok`; 8 lines; no `STOP:` text in the file.
- Removed with their files: the five-id table, the `-q2` token checks, `itest-acl-$T`, the prose table and its
  checks. The second branch of the diff check (files with ids) stays, unreachable in S4 (a comment says so).

### `g3_rows_dryrun.sh`

- Runs under `/tmp/g3-s4-dry-rows.*`; arguments: rows directory, checker, blob, and (new, optional) the battery's
  `t6.sh`.
- The file it names is `t6.sh`, sourced in the steps script's step form (one `bash -c`, `exec 2>&1`, the carriers
  unset as `STEP_PRE` unsets them, `set -v`, stdin closed), with stub helpers (`stop`, `wait_ready`, `drained`,
  `config_identity`, `harness_cmd`), the runbook's own `REC` value, stub `python` (delta, acceptance, analyze) and
  stub `ssh`, `scp`, `timeout`, `sleep`, `curl`, `sudo`, `docker` first on `PATH`; the step refuses to run unless
  `ssh` and `python` resolve to the stubs. `HOME` holds a two-entry plan (r03 and the request's r04 entry).
- Ten cases (each must echo the eight lines through `set -v`, give the stated number of `STOP:` lines and the
  stated calls, and call `analyze` once):

| # | Case | `STOP:` | harness | delta | acceptance |
|---|---|---|---|---|---|
| 1 | r04's raw directory exists (line 1 refuses, `F6=used`) | 4 | 0 | 0 | 0 |
| 2 | r04's `.sut` directory exists | 4 | 0 | 0 | 0 |
| 3 | the plan without r04 (no seed) | 3 | 0 | 0 | 0 |
| 4 | `harness_cmd` answers 2 (no manifest read) | 3 | 1 | 0 | 0 |
| 5 | `harness_cmd` answers 3 (`T6=incomplete`) | 3 | 1 | 0 | 0 |
| 6 | `harness_cmd` answers 1 | 3 | 1 | 0 | 0 |
| 7 | harness 0, sealed, drain `gave-up` (`T6=gaveup`) | 3 | 1 | 0 | 0 |
| 8 | harness 0, sealed, drain `quiet`; delta 0; acceptance 0 | 0 | 1 | 1 | 1 |
| 9 | as 8, `acceptance --exactly-once` answers 4 | 1 (line 7's) | 1 | 1 | 1 |
| 10 | as 8, `delta` answers 4 (MISMATCH) | 1 (line 6's) | 1 | 1 | 1 |

  Case 8 also requires the harness's 17 arguments (r04, the restart command, `--restart-at-s 300`, the
  configuration identity file, the twin hook with seed 1715385812, `--restart-transition-rule
  1a-option-a-2026-10-05` last), its environment `EVENTS_EXPECTED=die,start` with the three `DRAIN_*` empty, the
  `resources_proved_down` and `resources_transition_rows` prints, and the `delta`, `acceptance … --events
  …/events.post-drain.jsonl --exactly-once` and `analyze` argument lists.
- Checker self-test (blob mode, stub `git`): twelve copies refused — r03 in place of r04; `-q2` on the run id; line
  7 removed; the transition rule removed from line 5; `--restart-at-s 300` → `301`; a CR; the manifest naming
  `S3`; a non-empty `t6.sh.diff`; S3's `t8-a-reboot.sh` left in the directory; the battery's `t6.sh` in place of
  S4's; a missing blob; a blob with one line appended. The unaltered copy passes; 0 `git` calls.

## 2. The record (`P/rows-record/`)

One driver, `run-record.sh`, produced every console in one run (2026-10-05, 18:43:54Z to 18:44:05Z); each console
opens with the sha256 of the script it ran. The driver's filter abbreviates three long paths (`<S>`, `<OT>`,
`<WINREPO>`) and changes nothing else.

| Console | What it holds | Outcome |
|---|---|---|
| `rows-extract.console.txt` | the family value by `sed`; the extraction into `P/rows` (`--replace`); `--check` with the worktree's rule source and with its copy in `P`; `--check` without a rule source; a blob and a rule source with one byte appended; fourteen forbidden output directories; copies of the battery's and of S3's sealed rows as output | exit 0; 0 differ twice; 1 (only the manifest, as expected); refused twice, nothing created; refused fourteen times, nothing created; refused four times, the copies' 39 and 22 files unchanged |
| `rows-check.console.txt` | the checker, **blob mode**, on `P/runbook.1fd9792.md` and `P/rows`; the same through `EGW_G3_RUNBOOK_BLOB`; two usage errors | 22 `ok`, 0 `FAIL`, exit 0, 0 `git` calls; exit 0; exit 2 twice |
| `rows-dryrun.console.txt` | the dry run (section 1) | `DRY RUN AS EXPECTED (0 unexpected outcomes)`, exit 0, no directory left |
| `rows-proofs.console.txt` | the proofs of section 4 (`rows-proofs.sh`; other tools than the checker's) | `PROOFS HOLD (0 differences)`, exit 0 |
| `rows-check-clone-mode.console.txt` | the checker's **clone mode** against a throw-away clone under `/tmp`, never the execution clone: at `1fd9792` clean (tree `14f89c4…`); with an untracked file; at S3's `8e49261`; no clone; the extraction refusing the blob of `8e49261`; `--check` with both inputs read by `git show` | exit 0; `FAIL clone state`; `FAIL clone HEAD` and `clone state`; 8 `FAIL`; refused; 0 differ |
| `manifest-compat.console.txt` | the steps script's own `MANIFEST_PY` (`verify`, `entries`) taken out of `P/base/g3_battery.sh` and of `P/g3_battery.sh` as it stood (sha256 `bb086f6a…`, the OPERATOR stream's file, still changing), run on `P/rows` | `S4 t6` accepted; labels `S3`, `S2` and row `t8` under `S4` refused; `entries t6` reports suffix null, lines 1421–1428, diff 0 bytes |
| `rows-static.console.txt` | every script and row file: CR bytes 0, no BOM, valid UTF-8, final newline, `bash -n` / Python syntax; the numstat above | all as stated (`t6.sh.diff` empty) |
| `rows-untouched.console.txt` | `stat` of `~/egw-exec`, its clone, `.git`, `HEAD`, `index`, `attempts`, `~/egw-tcg`, `itest`, `pilot`, `pilot/campaign_plan.json` before and after | identical |
| `rows-files.sha256` | sha256 of the three scripts, the 3 row files and the three record scripts | — |

Command lines, as the driver ran them (in WSL; `HOME` redirected):

```
python3 -B P/g3_extract_rows.py --runbook P/runbook.1fd9792.md --rule-source S/t6m/src/tests/test_runbook_itest_helpers.py --out P/rows --replace
python3 -B P/g3_extract_rows.py --runbook P/runbook.1fd9792.md --rule-source S/t6m/src/tests/test_runbook_itest_helpers.py --out P/rows --check
bash P/g3_check_rows.sh --blob P/runbook.1fd9792.md P/rows
bash P/g3_rows_dryrun.sh P/rows P/g3_check_rows.sh P/runbook.1fd9792.md S/g3/battery/prep/rows/t6.sh
bash P/rows-record/rows-proofs.sh P/rows S/g3/battery/prep/rows/t6.sh P/runbook.1fd9792.md OT/runs/2026-10-02/HIST_2026-10-02-g3-battery-host-preparation/rows/t6.sh OT/runs/2026-10-03/20261003T132936Z_g3-qualification-t6_attempt01/environment/t6.sh
```

## 3. Files, with sha256

| File | sha256 |
|---|---|
| `g3_extract_rows.py` | `e3aa669d38c6320db1bfa853fd25834ac4d848e6fb04c6e9f341fbfd39c23050` |
| `g3_check_rows.sh` | `ae7038d3e046afa921ca7084240388bd8e87fe4c34797b9c750bffedc4d48494` |
| `g3_rows_dryrun.sh` | `1f32c56c32895b5d2cfd466b5e18db8cc3465a295df61085527294f75983c994` |
| `rows/t6.sh` | `ec8ac010d79ba87ff7f2b4c828c4fbe85c7f0c765d6869670552a6c1ba326377` (8 lines, 12,167 bytes) |
| `rows/t6.sh.diff` (empty) | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| `rows/rows.manifest.json` | `7d2a0f0d940c1d2f978a33693869fe4372cf7c63c4592d3d911d1440bdb8fb47` (its `generator_sha256` is the extraction script's `e3aa669d…`) |
| `rows-record/run-record.sh` | `7ffe2535e2cc7a40cdd8d8bf825394486d58c7e00e726824ccc34f610d7cce31` |
| `rows-record/rows-proofs.sh` | `1e806e1fef3238ba02d82833caf439f3a548b0d01e05bdc63ad3913eb28dc037` |
| `rows-record/manifest-compat.py` | `82451baf0972498f642fdac7b32b7164c40048d92f2640bd400ff84f15f35acd` |

Consoles of the run named above (they change with every run of the driver): `rows-extract` `dac0c4bc…`,
`rows-check` `4cfd2d7a…`, `rows-dryrun` `07975c7e…`, `rows-proofs` `27ef27c6…`, `rows-check-clone-mode`
`5cd01b0b…`, `manifest-compat` `3c44b762…`, `rows-static` `9e426309…`, `rows-untouched` `4025dee9…`,
`rows-files.sha256` `a3a184ee…`.

## 4. Proofs (`rows-record/rows-proofs.console.txt`)

**`t6.sh` is runbook lines 1421–1428 with `host$ ` removed, byte for byte.** Python slicing of the blob's bytes:
lines 1421–1428, all eight with the prompt, prompt removed → sha256 `ec8ac010…6377`, 12,167 bytes; `t6.sh` →
the same sha256 and size (`IDENTICAL`). The same with `sed -n '1421,1428p' | sed 's/^host\$ //' | cmp - t6.sh`: no
difference. Line 1420 is `` ```bash ``, line 1429 is `` ``` `` and line 1416 is test 6's heading: the file is the
whole fenced block. `t6.sh.diff` is 0 bytes. The checker shows the same a third way (`awk`, `sed`, `cmp`), and the
extraction asserts it against the test module's own functions.

**The battery's `t6.sh` against S4's.** The battery's file (`S/g3/battery/prep/rows/t6.sh`, sha256 `ebc9700c…3400`,
7 lines, 8,897 bytes, runbook lines 1421–1427 of `80e833f`) is byte-identical to the first preparation's sealed
copy and to the copy in S2's attempt (`OT/…/20261003T132936Z_g3-qualification-t6_attempt01/environment/t6.sh`), both
also checked against their packages' `SHA256SUMS` (`OK`). The diff (battery `<`, S4 `>`), each line cut at its
first 200 characters, as the console holds it:

```
1c1
< RID=controller_restart-r03; F6=used; if [ -e ~/egw-tcg/pilot/results/raw/$RID ] || [ -e $P/$RID.sut ]; then stop "test 6: $RID was already used (~/egw-tcg/pilot/results/raw/$RID or $P/$RID.sut exist
---
> RID=controller_restart-r04; F6=used; if [ -e ~/egw-tcg/pilot/results/raw/$RID ] || [ -e $P/$RID.sut ]; then stop "test 6: $RID was already used (~/egw-tcg/pilot/results/raw/$RID or $P/$RID.sut exist
5c5
< T6=stop; if [ "$F6" = fresh ] && [ -n "$SEED" ] && wait_ready && drained && config_identity $P/$RID.config_identity.json; then DRAIN_QUIET_S=$DRAIN_QUIET_S DRAIN_STEP_S=$DRAIN_STEP_S DRAIN_LIMIT_S=$
---
> T6=stop; if [ "$F6" = fresh ] && [ -n "$SEED" ] && wait_ready && drained && config_identity $P/$RID.config_identity.json; then DRAIN_QUIET_S=$DRAIN_QUIET_S DRAIN_STEP_S=$DRAIN_STEP_S DRAIN_LIMIT_S=$
6a7
> [ "$T6" = ok ] && $REC acceptance $RAW6/logs/simulator/$RID --events $RAW6/events.post-drain.jsonl --exactly-once || stop "test 6: the per-identity exactly-once check was not run (T6='$T6'), could n
```

Exactly three hunks (`1c1 5c5 6a7`; unified `@@ -1,7 +1,8 @@`): the changed RID line (new line 1), the changed
harness line (new line 5) and the added `acceptance --exactly-once` line (new line 7). Battery lines 2, 3, 4, 6 and
7 equal S4 lines 2, 3, 4, 6 and 8. Line 5's first 200 characters are the same on both sides; where the two changed
lines differ (`difflib`, the command being the text before the first four-space `#`):

- Line 1: in the command only `controller_restart-r03` → `-r04` (one character, position 25); the trailing comment
  grows from 318 to 783 characters (r03 named as used; the plan's supplementary entry r04 and how the preparation
  adds it).
- Line 5: the command gains exactly two insertions — ` --restart-transition-rule 1a-option-a-2026-10-05` after
  the `--fetch-started-at-cmd` argument (position 724), and a second read-only `python3 -c` print of the manifest's
  `resources_transition_rows` beside the existing `resources_proved_down` print; the trailing comment grows from
  2,053 to 2,774 characters (the rule described).

## 5. Fixed values, checked against the primary sources

- `P/runbook.1fd9792.md`: sha256 `31716593…`, 1,624 lines, no CR; equal to `git show 1fd9792:docs/setup/…` read in
  `S/t6m` and to the worktree's file. The test module: `b63ef7d8…` (worktree file, `git show`, `P` copy alike).
  `S/t6m`: HEAD `1fd9792b…`, tree `14f89c4d…`; the throw-away clone at `1fd9792` has the same tree.
- Test 6: heading on line 1416, fence 1420/1429, eight `host$` lines 1421–1428, next heading (test 7) on 1437 — as
  the brief gives. Line 1260 (section 7's preamble) is not extracted, by the rule.
- The blob holds `-q1` on lines 1504 and 1624 only (prose, not extracted) and no `-q2`.
- The plan-entry literals of lines 1421–1428: `controller_restart-r04` once (the run id) and
  `controller_restart-r01` once (line 1421's comment, "controller_restart-r01 ran on 2026-09-18, r02 on … and r03
  on 2026-10-03"); r02 and r03 stand only as "r02", "r03".
- No contradiction between the brief and the primary sources was found for this stream.

## 6. Deviations from the brief, with the reason

1. **Guards and assertions added to the extraction script** (not asked): the path components `t6m`, `t6int`,
   `s3prep`, `s3bprep` and `battery` are refused (hard rule 1 names those directories); the plan-entry literal
   counts and three line markers are asserted (they restate, line by line, what the brief says the block holds).
   Each refusal is exercised in `rows-extract.console.txt`.
2. **The prose-only step and its constants were removed** (the brief lists the t6 file only): `t9-exposure.sh`
   belonged to test 9's row; leaving the code would have written a second file or asserted a sentence on a line
   that moved (1537 → 1538). S3 removed test 1's prose step the same way.
3. **The dry run was rewritten around `t6.sh`** in the step form with ten cases, and takes an optional fourth
   argument (the battery's `t6.sh`) for one alteration. The brief says only "the files it names"; S3's cases
   (test 8's carriers, the exposure step) have no counterpart in S4.
4. **Clone mode was exercised against a throw-away clone** (`git clone -s --no-checkout` of the Windows repository
   into `/tmp/g3-s4-rows-record.*`, sparse, detached at `1fd9792`, clean), as S3's record did: the clone-mode path
   was edited (commit, line count) and is the one the host will run. It writes nothing in the source and shows
   nothing about `~/egw-exec/repo`.
5. **The system `python3`** was used, not the venv's (the scripts import the standard library only, and the venv
   lives under the real `HOME`).
6. **Extra record files**: `run-record.sh`, `rows-proofs.sh`, `manifest-compat.py` and their consoles.
7. Rule 4's `grep -c $'\r'` was not the check used from Git Bash (there the pattern arrives empty); CR bytes were
   counted with `tr -cd '\r' | wc -c` in WSL: 0 in every file.
8. Rule 6: this stream's files name no tool or vendor. The one match of a name sweep is the project's own
   directory that hard rule 1 lists beside `output_test`, as a refused path component of the extraction script
   (unchanged from the sealed script), in the driver that tests the refusal and in the console that shows it.

## 7. For the other streams

- **Names and label are the ones the steps script expects**: `row_files t6` → `t6.sh`; `MANIFEST_PY verify` of
  both `P/base/g3_battery.sh` and `P/g3_battery.sh` (`bb086f6a…` at the reading) accepts `S4 t6` and refuses `S3`
  and `S2` (`manifest-compat.console.txt`). If the OPERATOR stream changes `MANIFEST_PY`, run the driver again.
- **`t6.sh` holds no `STOP:` text**: every console line that opens with `STOP:` is the helpers' `stop`.
- **Line 7 runs after a failed `delta`** (it reads `T6` only): with `delta` 4 the console holds line 6's `STOP:` and
  then the exactly-once check's own result (case 10). **Line 8 (`analyze`) runs in every case**, whatever `T6` is.
- **The harness receives `DRAIN_QUIET_S`, `DRAIN_STEP_S`, `DRAIN_LIMIT_S` empty** (STEP_PRE unsets them and line 5
  passes them through) and `EVENTS_EXPECTED=die,start` — the prefix is unchanged from S2's line.
  `tools/session/proof_hook_drained.sh` at `1fd9792` skips an empty value in its whole-number check (lines 46–47)
  and reads the three with `:-` (lines 52, 68 and 80), so empty means the runbook's 130 s, 5 s and 900 s.
- **With no seed** (no r04 in the plan) line 2's `python3` prints a traceback before line 5's `STOP:` (case 3).
- **The manifest's sha256 follows the extraction script's**: any edit of `g3_extract_rows.py`, a comment included,
  changes `generator_sha256` and so `rows.manifest.json`; `t6.sh` and its diff do not change. After such an edit run
  `bash P/rows-record/run-record.sh` again.
- `seal_prep.sh` (HOST stream) already copies `rows/`, `rows-record/` and `rows-notes.md`; nothing else of this
  stream needs a place.

## 8. Open points

1. **Clone mode on the execution clone is still to be run**, after the host preparation has moved
   `~/egw-exec/repo` to `1fd9792`: `bash g3_check_rows.sh <rows directory>` (no `--blob`), and, if wanted, the
   extraction's `--check` with both inputs read by `git show` from that clone (form (vi) of the clone-mode console;
   the rule source written to a temporary file first). Until then the row file is shown equal to a file of the
   pinned sha256, not to what the execution clone holds.
2. **Nothing here ran `t6.sh` with the real helpers**: the dry run shows the control flow of the eight lines
   against stubs. The real helper file and the harness are exercised by the repository's tests and the bench
   stream; the guest is untouched until S4.
3. The manifest's schema name is still `g3-battery-rows-manifest/1` (form kept).
4. Observed, not caused by this stream: `~/egw-exec/repo/.git` has the modification time 2026-10-05 19:20:04 +0100,
   before this stream's first command; this stream's before and after listings are identical.
5. Observed, read-only (`git --no-optional-locks status` from Windows): the worktree `S/t6m` reports 99 entries
   (97 modified, 2 deleted), all under `docs/evidence/`, with a "Filename too long" warning — a Windows checkout
   limit. None is a file this stream reads; the runbook and the test module there equal their blobs at `1fd9792`.
