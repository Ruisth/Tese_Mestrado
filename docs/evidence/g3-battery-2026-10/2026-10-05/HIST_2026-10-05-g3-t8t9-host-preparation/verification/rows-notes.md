# Stream ROWS — notes (preparation of G3 session S3, 2026-10-04)

`S`, `P` and `OT` are the brief's three directories. Everything here was done offline, in WSL (Ubuntu-24.04,
bash 5.2.21, the system `python3` 3.12.3 with `PYTHONDONTWRITEBYTECODE=1`), with `HOME` and `EGW_EXEC_REPO` inside
`/tmp/g3-s3-rows-record.*` and `/tmp/g3-s3-dry-rows.*` (both removed when the run ended). No guest, no QEMU, no
docker, no ssh, no build. Nothing was written outside `P/rows`, `P/rows-record`, `P/rows-notes.md`, the three scripts
of this stream and those two temporary directories.

## Result

- The three scripts are revised for the merged commit `8e49261`, session `S3` and the suffix `-q2`.
- The extraction ran on `P/runbook.8e49261.md` (sha256 asserted) into `P/rows`: **22 files** — six step files of
  test 8, four fenced step files of test 9, their ten diffs, `t9-exposure.sh` and `rows.manifest.json`. Its `--check`
  finds 0 differences. The rule was checked against the test module's own `_section` and `_host_commands`.
- The checker in blob mode on `P/runbook.8e49261.md`: 68 `ok`, 0 `FAIL`, `ROW FILES OK`; it called `git` 0 times.
- The dry run: every outcome as expected, exit 0.
- Not done here, by design: the checker's clone mode against the execution clone (it cannot pass before the clone
  is at `8e49261`; see "Open points").

## 1. What changed, and why

Sizes against `P/base/` (`git diff --no-index --numstat`; `diff -u | wc -l`):

| Script | base sha256 | new sha256 | lines | added / removed | `diff -u` lines |
|---|---|---|---|---|---|
| `g3_extract_rows.py` | `6940366c…ead304` | `11c19af75faf43994c6f68f1ca7b6bdfc1aa7c0e56e1939b7c8dc52173604598` | 776 → 716 | 169 / 229 | 577 |
| `g3_check_rows.sh` | `1173e78c…8ddc26` | `2f1863b0f3b85f7ab2b8db65745f2d7a5d802ed0031fbcdb94e5cd666b64b11d` | 175 → 204 | 110 / 81 | 275 |
| `g3_rows_dryrun.sh` | `bf0fac2c…e9523bb` | `fbbca2f638f8a7b7364efcdd7756203504227c989708874c570c5339c48503e3` | 75 → 121 | 83 / 37 | 152 |

The three base copies equal the first preparation's sealed scripts (same sha256 in
`OT/runs/2026-10-02/HIST_2026-10-02-g3-battery-host-preparation/`), and are untouched.

### `g3_extract_rows.py`

- Constants: `RUNBOOK_COMMIT` `8e492613…`, `RUNBOOK_SHA256` `4acf8de6…`, `RUNBOOK_LINES` 1623, `RULE_SOURCE_SHA256`
  `fe8baa60…`, `SUFFIX = "-q2"`.
- `HEADS`: only `### Test 8` (6 commands, 15 lines, `3de0b928e211de74`) and `### Test 9` (10 commands, 26 lines,
  `9518fefe751c3d93`). Test 9's value is the one the battery's script asserted on the blob of `80e833f`, kept on
  purpose: the extraction itself now asserts that the block is unchanged. Test 8's value was computed apart from
  the script (`sed -n '1486,1500p' | sed 's/^host\$ //' | sha256sum`) before it was pinned.
- `OLD_IDS`, `TOTAL_COUNTS`: the five ids of the request's section 3 (60, 1, 1, 4, 3). `UNCHANGED`: `itest-acl-$T`.
  `PLAN_LITERALS`: empty (tests 8 and 9 name no plan entry). The set of `itest-` literals of the extracted text is
  asserted to be exactly those five and `itest-acl-$T`.
- `STEPS`: ten files, session `S3`. Asserted per file: `t8-a-reboot.sh` 1486–1495, 15; `t8-b-wait-boot-id.sh` 1496,
  8; `t8-c-unaided.sh` 1497, 32; `t8-d-tunnel.sh` 1498, none; `t8-e-state.sh` 1499, 5; `t8-f-smoke.sh` 1500,
  `itest-post-reboot-01` 1; `t9-a.sh` 1509–1510, 1; `t9-b.sh` 1511–1524, 4; `t9-c.sh` 1525–1527, 3; `t9-de.sh`
  1528–1534, none. `ROWS`: `t8` (six steps) and `t9` (five), session `S3`. The note of `t8` describes the corrected
  flow: no wait for a QEMU exit, nothing re-launched, the carrier `T8` set by the steps script.
- Asserted totals: 41 extracted lines, 10 step files, 41 lines in them; no line stands in two files.
- Removed: the rows of tests 1 to 7, and the prose-only step of test 1 with its constants (it read line 1427, no
  longer extracted). `T9_LINE` is 1537; the exposure step's body and header text are the same constants as before.
- The manifest keeps its form and schema name; `how` says "two headings"; the notes are rewritten for S3 (eleven).
- Kept and not called: `only_defines()` and the `definitions` branch (only the battery's `t7-ditto.sh` used them);
  one sentence in the docstring says so. No refactoring.
- Three small additions, each for S3 (see "Deviations"): `pb` joins the refused path components; a directory that
  holds the row files of another commit is never written (`other_commit_rows`); the extracted text and the
  prose-only body must hold no `-q1`.

### `g3_check_rows.sh`

- The commit, the hash, 1623 lines, the line table of ten files, the five ids, `-q2`, the prose table
  (`t9-exposure.sh|1537`), "22 expected files", "2 rows", "10 runbook files". The `t7-ditto.sh` trace and the
  `t1-harness-analyze.sh` line are gone with their files.
- **Blob mode**: `--blob <file>` (also `--blob=<file>`, or `EGW_G3_RUNBOOK_BLOB`). The blob is then `cat` of that
  file, its sha256 asserted like the clone's blob; `git` is never called; the two clone checks are replaced by a
  line that says the clone was not read; the last line names the mode. Without `--blob` the script is what it was:
  `git show` from the clean clone, HEAD required at the commit before and the clone clean at it after.
- The header and the usage text say which mode proves what: clone mode, that the row files are the lines of the
  runbook the execution clone holds at its checked-out commit; blob mode, that they are the lines of a file with
  the pinned sha256, and nothing about any clone.
- Added checks: no `-q1` in the blob's extracted lines nor in any step file; line 3 of `t9-exposure.sh` names
  `8e49261`, the blob's sha256 and line 1537; the manifest's runbook identity, suffix and session (`t8`, `t9`, `S3`);
  `itest-acl-$T` stands 11 times in `t9-de.sh`.

### `g3_rows_dryrun.sh`

- Runs under `/tmp/g3-s3-dry-rows.*`; takes a third argument, the blob file, and self-tests the checker in blob
  mode with a stub `git` first on `PATH` (0 calls recorded) and `HOME`/`EGW_EXEC_REPO` inside the temporary
  directory. The battery's version ran the checker against the real clone with the real `HOME`; this one does not.
- The files it names: `t8-b…` to `t8-f…` each sourced in a new shell without the carrier (each prints one `STOP:`
  and calls nothing); `t8-f-smoke.sh` with `T8=ok` (the stub `run_test` receives `itest-post-reboot-01-q2 42
  --scenario smoke --duration 30`); `t9-exposure.sh` with stub `ssh` and `ss`. The steps run with stub `ssh`,
  `scp`, `ss`, `python`, `timeout`, `sleep`, `curl`, `sudo`, `docker` first on `PATH`.
- Thirteen alterations, each detected: an id without its suffix; one of line c's 32 literals not substituted;
  `timeout 20` changed to `timeout 21`; a comment line of line a removed; `itest-acl-$T` suffixed; a carriage
  return; a suffix where no id stands; a `-q1` id; the exposure header naming `80e833f`; the manifest naming `S2`;
  a battery file name left in the directory; a blob file that does not exist; a blob with one line appended. An
  expression that changes nothing is reported as such, and the exit status is 0 only when every outcome held.

## 2. The record (`P/rows-record/`)

One driver, `run-record.sh`, produced every console in one run (2026-10-04, 21:19:44Z to 21:20:10Z); each console
opens with the sha256 of the script it ran. In the consoles the driver's filter abbreviates three long paths
(`<S>`, `<OT>`, `<WINREPO>`) and changes nothing else.

| Console | What it holds | Outcome |
|---|---|---|
| `rows-extract.console.txt` | the extraction into `P/rows` (`--replace`); `--check`; `--check` with the blob on stdin and no rule source; a blob and a rule source with one byte appended; nine forbidden output directories; a copy of the battery's rows as output | exit 0; 0 differ; 1 (only the manifest, as expected); refused; refused, nothing created; refused twice, the copy's 39 files unchanged |
| `rows-check.console.txt` | the checker, **blob mode**, on `P/runbook.8e49261.md` and `P/rows`; the same through the environment variable; two usage errors | 68 `ok`, 0 `FAIL`, exit 0, 0 `git` calls; exit 0; exit 2 twice |
| `rows-dryrun.console.txt` | the dry run | `DRY RUN AS EXPECTED (0 unexpected outcomes)`, exit 0, no directory left |
| `rows-proofs.console.txt` | the proofs of section 4 (`rows-proofs.sh`, other tools than the checker's) | `PROOFS HOLD (0 differences)`, exit 0 |
| `rows-check-clone-mode.console.txt` | the checker's **clone mode** against a throw-away clone under `/tmp` (see "Deviations"), never the execution clone: at `8e49261` clean; with an untracked file; at `80e833f`; no clone; the extraction refusing the blob of `80e833f`; `--check` with both inputs read by `git show` | 69 `ok`, exit 0; `FAIL clone state`; `FAIL clone HEAD` and `clone state`; 35 `FAIL`; refused; 0 differ |
| `manifest-compat.console.txt` | the steps script's own `MANIFEST_PY verify`, taken out of `P/base/g3_battery.sh` and of `P/g3_battery.sh` as it stood (sha256 `acbb5988…`, another stream's file, still changing), run on `P/rows` | `S3 t8` and `S3 t9` accepted; label `S2` and the battery's four t8 names refused |
| `rows-static.console.txt` | every script and row file: CR bytes 0, no BOM, valid UTF-8, final newline, `bash -n` / Python syntax; the numstat above | all as stated |
| `rows-untouched.console.txt` | `stat` of `~/egw-exec`, its clone, `.git`, `HEAD`, `index`, `attempts`, `~/egw-tcg`, `itest` before and after | identical |
| `rows-files.sha256` | sha256 of the three scripts, the 22 row files and the three record scripts | `sha256sum -c`: 28 of 28 `OK` |

Command lines, as the driver ran them (in WSL; `HOME` redirected):

```
python3 -B P/g3_extract_rows.py --runbook P/runbook.8e49261.md --rule-source S/pb/src/tests/test_runbook_itest_helpers.py --out P/rows --replace
python3 -B P/g3_extract_rows.py --runbook P/runbook.8e49261.md --rule-source S/pb/src/tests/test_runbook_itest_helpers.py --out P/rows --check
bash P/g3_check_rows.sh --blob P/runbook.8e49261.md P/rows
bash P/g3_rows_dryrun.sh P/rows P/g3_check_rows.sh P/runbook.8e49261.md
bash P/rows-record/rows-proofs.sh P/rows OT/runs/2026-10-02/HIST_2026-10-02-g3-battery-host-preparation/rows P/runbook.8e49261.md
```

## 3. Files, with sha256

Scripts: see the table of section 1. Record scripts: `rows-record/run-record.sh`
`c1f4199b291c69d659bac414446a2ecbc7efe13986cd0c7c791ec19f21df344e`, `rows-record/rows-proofs.sh`
`dff17b59f9b2653c63ee5e83ed1e766f0986b22a8fdd3499d84e3913a8176700`, `rows-record/manifest-compat.py`
`c8400f61aba781a1a1d2ca942c5a2819f8795ba4569b331452ca1d0e41d9292c`.

`P/rows/` (the manifest's `generator_sha256` is the extraction script's `11c19af7…`):

| File | sha256 |
|---|---|
| `rows.manifest.json` | `678b92031e09213780bc3790be1473358746693fc1d86088891ff2697f340c5d` |
| `t8-a-reboot.sh` | `00ff23db999e4ad5460c93010721e393d60c34fd4e596666cef9fd35fda8aa43` |
| `t8-a-reboot.sh.diff` | `60784efd0af97084dd6d70291c20c9a4f789933eb00f4553d7ae1e4ec62f6bd9` |
| `t8-b-wait-boot-id.sh` | `f38f7fad40980359b6f3ea59142f8a2f0199a3d80a942e7b36826ddfdd9cade7` |
| `t8-b-wait-boot-id.sh.diff` | `3df5f8b0b3f7b0c07e6d887fa8fc9bd05968f150f4973a14ea104c077474569b` |
| `t8-c-unaided.sh` | `df4ff611057b4f5a7df40b8b8f0fb2818eed43011c2c10109d7cc0881a7da39d` |
| `t8-c-unaided.sh.diff` | `c9b2ae06962748ccb62016ae485f5437a1cbc914717dc7bbad28f93608edb0a7` |
| `t8-d-tunnel.sh` | `dbffd3defbdfbbadce3218bde6c4562d77b0e1813bd70a0562e6f921844809f5` |
| `t8-d-tunnel.sh.diff` (empty) | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| `t8-e-state.sh` | `00d100f7232b93fe5e425f603b7915514b24e67258b692603fa335b99293f593` |
| `t8-e-state.sh.diff` | `8b88bbd8c8ace5f472242599187fa4c040215c4e74f604a7691177471abc3d5f` |
| `t8-f-smoke.sh` | `874ef658228e30e19b561a6f5306b698e0665f3701c2fb28ab0d13feddb6dc76` |
| `t8-f-smoke.sh.diff` | `a52e5794df568565d5c49a59c2c40c165fd14a4ac0a61ad0cd7c8460c6275f95` |
| `t9-a.sh` | `34be9077366b587ae976db89e7aaaeda2bcdbcf8d3976af8254d5a5219169dac` |
| `t9-a.sh.diff` | `85ad2aaf417599d240455c14a33090dfa815359c673c1d7fce8f2486e839f9c5` |
| `t9-b.sh` | `29e7e98099e9bb30c58c4b141b87b4bf886ccd082a42da31a0c3b8656a4c4d5b` |
| `t9-b.sh.diff` | `1c08cb2a9581d6cc8fd1bb4037443d8dea141682da94f03027d380688d1592b5` |
| `t9-c.sh` | `e95f9f153a766f0ab0f21fefb4b93e0893578be80d863b411c1dfc1f64fbbf43` |
| `t9-c.sh.diff` | `3f2207e566057351b83f60e3ca7c34218df1f25969dfd37c4a751596b61d08e8` |
| `t9-de.sh` | `4ad835244e065df402034f3f552938ce2e7b7c50a43f776db4b4c06078c2b6ae` |
| `t9-de.sh.diff` (empty) | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| `t9-exposure.sh` | `ec18b22a643203a1c2d9bc9a9519b5b4a6f69de65df9944d832f09744428fe9c` |

Consoles (they change with every run of the driver; these are the ones of the run named above):
`rows-extract` `9cbee027…`, `rows-check` `52b4e865…`, `rows-dryrun` `4ef6d840…`, `rows-proofs` `2f461e02…`,
`rows-check-clone-mode` `545cff34…`, `manifest-compat` `00403f4e…`, `rows-static` `24c06f71…`, `rows-untouched`
`8de3414a…`, `rows-files.sha256` `937dd628…`.

## 4. Proofs (`rows-record/rows-proofs.console.txt`)

The first preparation's files are read from the sealed package
`OT/runs/2026-10-02/HIST_2026-10-02-g3-battery-host-preparation/rows/` (its own `SHA256SUMS` re-checked for the
files used: `OK`).

**Test 9 — each fenced file equals the first preparation's file with `-q1` replaced by `-q2`** (`sed 's/-q1/-q2/g'`
of the sealed file, `cmp` with the S3 file):

| File | first preparation (sealed) | S3 file = the sealed file with `-q1` → `-q2` | `-q1` → `-q2` | Result |
|---|---|---|---|---|
| `t9-a.sh` | `3ff28763…6b5869` | `34be9077…169dac` | 1 → 1 | IDENTICAL, 387 bytes |
| `t9-b.sh` | `d6d86b25…a93c8e` | `29e7e980…4c4d5b` | 4 → 4 | IDENTICAL, 1940 bytes |
| `t9-c.sh` | `9a3ae72b…7632b7` | `e95f9f15…fbbf43` | 3 → 3 | IDENTICAL, 630 bytes |
| `t9-de.sh` | `4ad83524…c2b6ae` | `4ad83524…c2b6ae` | 0 → 0 | IDENTICAL (the same file), 2228 bytes |

**`t9-exposure.sh`** differs from the sealed file (`484f3fdf…c76f85`) in one line of eighteen, line 3:

```
< # It derives from docs/setup/qemu_integrated_gateway.md at 80e833f (sha256 c55a2d3b…fecd74ae), line 1529 (the last sentence of test 9's Expected), which says:
> # It derives from docs/setup/qemu_integrated_gateway.md at 8e49261 (sha256 4acf8de6…68f2a9db), line 1537 (the last sentence of test 9's Expected), which says:
```

(the hashes are printed in full in the console). The sealed line 3 with those three replacements is the S3 line 3;
the three commands (the lines that are not comments) have the same sha256 in both files (`430a94f2…85c6c7`). The
quoted sentence stands on line 1537 of the blob, which is byte-identical to line 1529 of the blob of `80e833f`.

**Test 8 — each file with every `-q2` removed is the blob's lines, the prompt removed, byte for byte** (Python
slicing of the blob; the checker shows the same with `awk`, `sed` and `cmp`):

| File | runbook lines | sha256 of the lines, prompt removed = sha256 of the file without `-q2` | bytes | `-q2` |
|---|---|---|---|---|
| `t8-a-reboot.sh` | 1486–1495 | `9798ae61f69fb86563b62db6ce9332c57b74f598ad9f86c424a1697ad958c410` | 3188 | 15 |
| `t8-b-wait-boot-id.sh` | 1496 | `f42e3fcb3715df71ea6b4c7d2a76aff62cfb5163352098138027db8f4c19c656` | 3059 | 8 |
| `t8-c-unaided.sh` | 1497 | `92826e477d8b162443c8b6845fedad1106e9bb037b90b3fcd15f227e2206768a` | 4811 | 32 |
| `t8-d-tunnel.sh` | 1498 | `dbffd3defbdfbbadce3218bde6c4562d77b0e1813bd70a0562e6f921844809f5` | 252 | 0 |
| `t8-e-state.sh` | 1499 | `ba95574eaa7d1754f139975093afdd7c373dbe7d2e94b12f292f97f0d2eb8fea` | 1001 | 5 |
| `t8-f-smoke.sh` | 1500 | `3ebdac904a7f50258821af49a990e9b01f50081f962c03d98451da3125a2c75c` | 296 | 1 |

The six files in order, without `-q2`, are lines 1486–1500 with the prompt removed (sha256 `3de0b928…c5bb15`): the
whole fenced block of test 8 (line 1485 opens the fence, line 1501 closes it). The four fenced files of test 9 are
likewise the blob's lines 1509–1510, 1511–1524, 1525–1527 and 1528–1534.

## 5. Fixed values, checked against the primary sources

- `P/runbook.8e49261.md`: sha256 `4acf8de6…`, 1,623 lines, no CR; equal to `git show 8e49261:docs/setup/…` in `S/pb`.
  The test module: `fe8baa60…`, worktree file and `git show` alike. `_section` and `_host_commands` are unchanged
  between `80e833f` and `8e49261` (their source text, from `def _section(` to `return cmds`, has the same sha256 in
  both blobs), and `tools/` does not differ at all.
- Commands start on lines 1486, 1496–1500 (test 8) and 1509, 1510, 1523, 1524, 1526, 1527, 1531–1534 (test 9);
  fences 1485/1501 and 1507/1535. Counts per line: `itest-reboot` 15, 8, 32, 0, 5; `itest-post-reboot-01` 1 (line
  1500); `itest-tls-wrongca` 1 (1510); `itest-auth-wrongpw` 4 (1517, 1523, 1524 twice); `itest-notls` 3 (1526, 1527
  twice); `itest-acl-$T` 11 (1531–1534). All as the brief gives them.
- Old lines 1497–1529 (`80e833f`) and new lines 1505–1537 are byte-identical: test 9's heading, fence and Expected.
- The blob holds `-q1` on lines 1503 and 1623 only (prose; neither is extracted) and no `-q2`.
- Not a contradiction, but to be exact: the worktree `S/pb` has HEAD `7c371e3` (the head of the merged branch), not
  `8e49261`; both have the tree `2f051483…`, and `8e49261` is readable there.

## 6. Deviations from the brief, with the reason

1. **Three guards added to the extraction script** (not asked): the path component `pb` is refused like `cand`
   (the read-only worktree is now `S/pb`); an output directory whose `rows.manifest.json` is of another commit is
   never written, `--replace` or not (two generations of row directories now exist, and the first preparation's
   command line used `--replace`: a mistyped `--out` could otherwise overwrite the battery's rows); the extracted
   text must hold no `-q1`. Each is exercised in `rows-extract.console.txt`.
2. **Checks added to the checker** beyond the constants (listed in section 1), and the dry run takes a third
   argument and returns a meaningful exit status.
3. **Clone mode was exercised against a throw-away clone**, not asked by the brief: `git clone -s --no-checkout`
   of the Windows repository into `/tmp/g3-s3-rows-record.*`, sparse, detached at `8e49261` (tree `2f051483…`,
   clean). Reason: the clone-mode path was edited and is the one the host will run; without this it would have
   been delivered untested. It reads the Windows repository's objects and writes nothing there (the newest entry
   of its `.git` is of 19:37, before this stream). It shows nothing about `~/egw-exec/repo`.
4. **The system `python3`** was used, not the venv's (the scripts import the standard library only, and the venv
   lives under the real `HOME`).
5. **Extra record files**: `run-record.sh`, `rows-proofs.sh`, `manifest-compat.py` and their consoles.
6. `grep -c $'\r'` (rule 4) was **not** the check used from Git Bash: there it returns the file's line count (the
   pattern arrives empty), a false alarm. CR bytes were counted with `tr -cd '\r' | wc -c` and in WSL: 0 everywhere.
7. Rule 6: this stream's files name no tool or vendor. The one match of a name sweep is the project's own
   directory that rule 1 lists beside `output_test`, as a refused path component of the extraction script
   (unchanged from the sealed script) and in the console that shows the refusal.

## 7. For the other streams

- **File names and session label are the ones the steps script expects**: `manifest-compat.console.txt`.
- **`t8-a-reboot.sh` holds the text `STOP:` once**, in its last comment line (runbook line 1495: "…printed no
  STOP:."). The battery's T8 files held none. The steps script's `no_stop` then anchors its pattern at the line
  start for step a, as it did for the battery's T7 files; no line of any of the eleven files starts with `STOP:`,
  and the helper's `stop` prints `STOP: ` at the line start (on stderr, which the step shell joins). Worth one
  bench case on the real file.
- **Lines b to f refuse in a new shell** (shown on the real files): the carrier must be set before the file is
  sourced, in the same shell.
- **The manifest's sha256 follows the extraction script's**: any edit of `g3_extract_rows.py`, a comment included,
  changes `generator_sha256` and so `rows.manifest.json`; the step files and diffs do not change. After such an
  edit `run-record.sh` must be run again.
- The sealing script already names `rows-record`, `rows/rows.manifest.json` and `rows-notes.md`; nothing else of
  this stream needs a place.

## 8. Open points

1. **Clone mode on the execution clone is still to be run**, after the host preparation has moved
   `~/egw-exec/repo` to `8e49261`: `bash g3_check_rows.sh <rows directory>` (no `--blob`), and, if wanted, the
   extraction's `--check` with both inputs read by `git show` from that clone (form (vi) of the clone-mode
   console; the rule source written to a temporary file first). Until then the row files are shown equal to a
   file of the pinned sha256, not to what the execution clone holds.
2. **Nothing here ran test 8's or test 9's lines with the real helpers**: the dry run only shows the refusals,
   the smoke's start under its id and the exposure step against stubs. Lines a to e on the real helper file and
   the repository's own stubs are the bench stream's work.
3. `t9-exposure.sh` keeps its header text ("G3 battery, row t9, step 5 of 5", "Decision packet of 2026-10-01
   (revision 2)…"): the brief allows only the commit, the hash and the line number to change. A reader of S3's
   package should know that this wording is the battery's.
4. The manifest's schema name is still `g3-battery-rows-manifest/1` (form kept).
5. Observed, not caused by this stream: the directory `~/egw-exec/repo/.git` has the modification time
   2026-10-04 21:52:45 +0100, while `HEAD`, `index` and `FETCH_HEAD` are of 2026-10-02. This stream's first command
   came later, and its before and after listings are identical. A `git status` without `--no-optional-locks`
   leaves such a trace (a lock file made and removed); who ran it is not known here.
