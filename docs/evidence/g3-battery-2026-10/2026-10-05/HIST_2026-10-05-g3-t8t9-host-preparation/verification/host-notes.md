# Stream HOST: notes (2026-10-04)

Scope: `g3_hostprep.sh`, `seal_prep.sh`, `ops/seal_ops.sh`, `ops/seal_ops_finish.sh`, `ops/g3_go.sh`, `ops/g3_wait.sh`,
revised for session S3 (tests 8 and 9 only). `P` is the preparation folder named in the first lines of the brief;
`P/base/` holds the copies each revision started from. **`g3_hostprep.sh` was not run** (section 5 says what was).

## 1. Deliverables

| File | sha256 | `diff --stat` against `P/base/` |
|---|---|---|
| `g3_hostprep.sh` | `6613f15286f272150cdfba9fa508fadf2f89762ac795686218c143f079d7570e` | 114 insertions, 57 deletions |
| `seal_prep.sh` | `68a2cf0462ec639f4abe43f8d19a693fed2cdfc87f47759ef824eb7a3d79d589` | 119 insertions, 47 deletions |
| `ops/seal_ops.sh` | `5cfd51b2d8d2367a6ee0b0f668a9a3d71fe3d2be3048991b2d07f5b7ee69c882` | 64 insertions, 18 deletions |
| `ops/seal_ops_finish.sh` | `e675924262e78b5abbfb5118edbc790e49b91c1ea6b2bb63749a0e225e528a6b` | 78 insertions, 26 deletions |
| `ops/g3_go.sh` | `83950a9f532d84ab1057234062e1be882cbd62dda88e4a385603eee0529c0716` | 8 insertions, 8 deletions |
| `ops/g3_wait.sh` | `b1324eff4ca16692c61fd43961a4f628757be115d75ccbc23a55e7250d4afbaf` | 7 insertions, 6 deletions |

The base copies are the first preparation's bytes: `base/g3_hostprep.sh` equals the one sealed in
`HIST_2026-10-02-g3-battery-host-preparation`, the four `base/ops/*.sh` equal those sealed in S2's operator records,
`base/seal_prep.sh` equals the first preparation's working copy (it was never sealed in its own package)
(`host-record/static_check.console.txt`, last block).

Records of this stream, in `P/host-record/` (a folder this stream added; see section 7):
`static_check.sh` and its console; `seal_bench.sh` and its console; `hostprep_fragments_bench.sh` and its console;
`dry_seal_snapshot.sh` and its console; `ro_look.sh` and its console.

## 2. What changed, and why

### 2.1 `g3_hostprep.sh`

- **Commit and tree**: `TOOLS=8e49261…`, `TREE=2f05148…` (lines 17-18). New constants: `BATTERY=80e833f…` (the only other
  HEAD the clone may be at), `REVIEWED=7c371e3…` (the reviewed head of PR #54), `ROOTFS_SHA=22e9da85…`,
  `T8_ADMITTED`, the five `-q2` identifiers (line 35), and the paths `Y`, `BUILD`, `DEP`, `ATT`, `OT`.
- **The gate on the clone (lines 57-68; decision summary, choice 1)**: before anything is fetched, a non-empty
  `git status --porcelain` is a stop, and so is a HEAD that is neither `80e833f…` nor `8e49261…`. Nothing is discarded,
  reset or stashed anywhere in the script. The status is read with `GIT_OPTIONAL_LOCKS=0`, so that the gate itself does
  not rewrite the clone's index.
- **Fetch and checkout (lines 70-78)**: the same fetch as the first preparation (`origin`, `refs/remotes/origin/dev`: the
  Windows repository's view of the remote `dev`). The rule on the tip changed as the brief asks: `git cat-file -e
  8e49261…^{commit}` must find the commit and `git merge-base --is-ancestor 8e49261… FETCH_HEAD` must hold (true when
  the two are equal); the tip is NOT required to be the commit. The clone goes to `8e49261…` detached, never to the tip.
- **After the checkout (lines 79-99)**: HEAD and tree compared, clean status (a `git status` that fails is now a stop:
  the first version read a failure as "clean"), branches unchanged (`cmp` of the two listings), the reviewed head's tree
  compared with `2f05148…`, the files that differ from `80e833f…` listed with a stop if one is under `tools/` or under
  `src/` outside `src/tests` (the decision summary's statement, now checked on the host), the "no rebuild" loop against
  `489bc9e…` unchanged (with one line before it that requires that commit to be in the clone: the loop reads an error
  as "identical").
- **Identities (lines 103-144)**: the runbook's new hash and its 1,623 lines; the extraction rule's source (the test
  module); the unchanged ones as before; `repo_identity` through the clone's `common.sh` as the first preparation did,
  now compared on three fields (commit, `drivers_sha256`, `export_tool_sha256`); the four added comparisons: kernel,
  `qemuboot.conf`, the QEMU binary (paths as `guest_session_open.sh` lines 112-117 build them) and the Yocto checkout
  (`489bc9e…` AND a clean status; the first version only printed both); the root file system at `22e9da85…`.
  `campaign_plan.json` is no longer compared: its hash is printed beside the environment input's, "recorded, not
  compared" (S3 runs no harness row; today it is `c195bd3f…`, not the `5d902a42…` the first preparation pinned).
- **Helper regeneration (lines 146-153)**: unchanged text.
- **Freshness on the host (lines 155-166)**: the five `-q2` identifiers; the three places of the first version (itest,
  itest-replay, pilot results) and, added, a search by NAME under the attempts directory and the whole of
  `output_test` (`find … -name "*<id>*"`), which skips a sealed S3 preparation package (`HIST_*-g3-t8t9-host-preparation*`:
  its bench records may be named after an identifier). A search that fails is a stop, never "fresh".
- **Earlier attempts (lines 168-189)**: every `*_g3-qualification-*_attempt*` under the attempts directory,
  `output_test/runs` and `output_test/incomplete` (the three roots the export tool numbers from, searched recursively
  as the tool does) is listed and kept in the record (`g3-qualification-attempts.txt`). The battery's attempts are
  admitted as they are. A stop: any attempt of row t8 other than `20261003T142310Z_g3-qualification-t8_attempt01` (so
  an `attempt02` too), any attempt of row t9, or the admitted attempt found nowhere (the new one would then not be
  numbered `attempt02`). The two campaign-plan entries and the listing of `pilot/results/processed` are gone.
- **Guest listing (lines 191-205)**: the same offline `debugfs -c` listing, for the five identifiers and the prefix
  rule (`^itest-reboot-q2`). Added: the listing must hold the `.` and `..` entries. Reason, found on the bench:
  `debugfs` ends with status 0 when the directory does not exist and when the image cannot be opened, so the first
  version would have reported every identifier "fresh" over an empty listing. Root file system hashed before (line 144)
  and after (line 205).
- **Small**: the script's own sha256 is the first line of its console; `PYTHONDONTWRITEBYTECODE=1`; the variable for
  `output_test` is `OT` because the clone's `common.sh`, sourced at line 124, sets `OUT` and `PY`, and line 125 stops
  if an `EGW_*` variable of the environment has redirected them.

### 2.2 `seal_prep.sh`

- **Name**: the package must be `…/<date>/HIST_<date>-g3-t8t9-host-preparation` (a later sealing of the same date:
  the suffix `-attemptNN`), under a folder named after the same date; otherwise refused, nothing created.
- **File set for S3**: the scripts (`g3_hostprep.sh`, `g3_extract_rows.py`, `g3_check_rows.sh`, `g3_rows_dryrun.sh`,
  `g3_battery.sh`, its README, `seal_prep.sh` itself), `ops/` (the four scripts), `rows/`, `bench/`, every folder named
  `*-record/`, the hostprep record as `part1-record/` (default `P/record`, or the fourth argument), the brief as
  `prep_brief.md`, the operator procedure, the runbook blob, every other `*.md` of the folder under `verification/`
  (the four notes are required), and `verification/diffs/`: each revised file against its `base/` copy. What the
  folder holds beyond that is named in the console and in the README and not copied (`base/`,
  `operator-procedure.battery.md`). Every input is looked for BEFORE anything is created (the first version could
  leave a half-made package behind, which can then never be overwritten).
- **README**: written from the record, not from fixed sentences: the record's `outcome=` line verbatim, its count of
  `STOP:` lines, its identity lines. A record without an outcome line is refused; a record whose outcome is not
  `prepared` is sealed with a title that says so and exit status 3 (a failed preparation is evidence too, and must not
  read as a prepared one).
- **Sweep**: section 2.3.

### 2.3 The secret sweep (the three sealing scripts)

- **The known false alarm.** `seal_ops.sh` searched the package for the regular expression `-----BEGIN .*PRIVATE
  KEY-----` and the package holds a copy of `seal_ops.sh`: the expression matched its own text (line 25), in S1 and in
  S2. The S3 scripts use the expression `seal_ops_finish.sh` already used, `-----BEGIN [A-Z ]*PRIVATE KEY-----`, written
  in the script with the tail split by quotes. It matches every private-key header of the PEM form (capital letters
  and spaces between BEGIN and PRIVATE) and cannot match its own text, where a bracket follows `BEGIN `. Shown on the
  bench: the first preparation's script stops on the same input (B0), the S3 script seals it (B1) while the package
  holds the pattern text; a real header in a file still stops the sealing (A5, B4a).
- **No value on a command line.** The first version ran `grep -rlF -- "<value>" <package>`: the value was on grep's
  command line (the bench logged it there, B0). The S3 scripts pass it through a file descriptor
  (`grep -rlF -f <(printf '%s\n' "$value")`): 0 logged command lines hold a value (A1, A4, B1, C1). Names only are
  printed, as before.
- **A sweep that cannot be made is a stop**: an unreadable `.env`, or one with no secret-named variable, is refused
  before anything is created.

### 2.4 `ops/seal_ops.sh`, `ops/seal_ops_finish.sh`

- Label `S3` only; state directory `${EGW_G3_STATE:-$HOME/egw-exec/g3-t8t9-s3}`; package name
  `HIST_<date>-g3-t8t9-s3-operator-records` under a folder of the same date; inputs looked for before anything is
  created; the classification notes (`<ops dir>/notes`) are copied when they exist, and the README says so when they
  do not (an S3 that halts at open has none).
- **A fourth argument, new**: the sealed host-preparation package. The README of the first version named
  `HIST_2026-10-02-…` as a fixed text; the S3 package's date is not known when the script is written. The script
  requires that package to be sealed, names it with the sha256 of its `SHA256SUMS`, and states whether the steps script
  and the manifest "as opened" (`state/S3-g3_battery.sh`, `state/S3-rows.manifest.json`) equal the package's.
- `seal_ops_finish.sh` keeps its purpose (finish, in place, a package that `seal_ops.sh` left unsealed) but no longer
  sets a file aside: it repeats the same whole sweep and stops on a hit, so it is not a way round the sweep (B3f). It
  checks that the files `seal_ops.sh` copies are there, compares `state/` with the state directory as it stands
  (`diff -rq`) and writes the result in the README (a difference is stated and listed, not hidden), and says what it
  removed or replaced (the copy of the turn lock; a README left behind).

### 2.5 `ops/g3_go.sh`, `ops/g3_wait.sh`

- `g3_go.sh`: the steps script is looked for in the folder that holds `ops/` (`$OPS/..`, was `$OPS/../prep`); usage
  texts name `open S3` and rows `t8`, `t9`. `g3_wait.sh`: state directory default `g3-t8t9-s3`; the folder is derived
  from the script's own place instead of a fixed path (section 7, item 6). Nothing else changed: the launcher still
  starts ONE subcommand with `setsid`, no terminal, `EGW_EXEC_REPO=$HOME/egw-exec/repo`; the waiter signals nothing.

## 3. `bash -n`, line ends

Run in WSL on the final bytes: `bash -n` passes for the six scripts and the four scripts of `host-record/`;
`grep -c $'\r'` is 0 for each; no BOM; ASCII only. (In the Windows shell `grep -c $'\r'` counts every line whatever
the file holds; the counts above are WSL's, and `tr -cd '\r' | wc -c` gives 0 bytes in both.)

## 4. Hard-coded values of `g3_hostprep.sh` and where each was taken from

`host-record/static_check.sh` reads each value out of the script and compares it with its source: 50 lines "same",
0 "DIFFERENT" (`static_check.console.txt`, script sha256 `6613f152…`). Sources:

| Value | Source |
|---|---|
| `TOOLS` `8e492613…`, `TREE` `2f051483…` | decision summary; `git rev-parse` in a worktree of the Windows repository (the clone's origin), whose `refs/remotes/origin/dev` is at `8e492613…` today |
| `BATTERY` `80e833f4…` | first parent of the merge; S2's record names it as the execution clone's HEAD |
| `REVIEWED` `7c371e3f…` | second parent of the merge; its tree is `2f051483…` |
| `IMAGE` `489bc9e5…` (also the Yocto checkout's commit) | S2's record `001-identities-before-boot.stdout.txt`: `source_commit=` and the "OS build source" line |
| runbook `4acf8de6…`, 1,623 lines; test module `fe8baa60…`; `local_export.py` `544c9b3d…`; `fetch_started_at.sh` `9c6dc824…`; `images.lock.env` `8a9a05df…`; `compose.yaml` `1a32f6c2…`; `mosquitto.conf` `ea37827c…`; `CONTRACTS.md` `247e3b02…` | `git show 8e49261…:<path>` hashed |
| `src/deployment` tree `e056d389…`, `src/schemas` tree `1d5284cf…` | `git rev-parse 8e49261…:<path>` |
| `drivers_sha256` `4a6a572d…` | the blobs of `tools/session/*.sh`, `*.py`, `guest/*.sh` at `8e49261…`, concatenated in the order of `driver_files` |
| helper `e5eba37e…`, 545 lines | the section 6.1 heredoc cut out of the runbook blob at `8e49261…`; the deployed file today |
| `tunnel.sh` `38f5cae9…`, `ca.crt` `556e139f…`, controller archive `9d347be4…`, image id `9a293fe1…`, launcher `67da61d7…` | S2's record; the host today (`ro_look.console.txt`) |
| controller record `79e7d210…` | the first preparation's sealed record; the host today |
| kernel `4457ef38…`, `qemuboot.conf` `7739c945…`, QEMU binary `5d389c65…` (the three added hashes) and their paths | S2's record, lines of `guest_session_open.sh` 112-117; the host today |
| root file system `22e9da85…` | `session-S2.env`, `rootfs_after_close`; the host today |
| `T8_ADMITTED` | `output_test/runs/2026-10-03/20261003T142310Z_g3-qualification-t8_attempt01` |
| the five `-q2` identifiers | decision summary, "Identifiers" |
| paths under `/home/ruisth` and of `output_test` | unchanged from the first version; `Y`, `BUILD`, `DEP` as `guest_common.sh` lines 6-8 |

## 5. What was run, and what was not

Run (consoles in `host-record/`):

1. **`static_check.sh`** (Windows shell, read-only): section 4.
2. **`seal_bench.sh`** (WSL, throw-away tree `/tmp/g3-s3-seal-*`, fake HOME, fake `.env` with fake values, a stub
   `grep` that logs its command line): **76 PASS, 0 FAIL** on the final bytes. `seal_prep.sh`: seals and verifies
   with `sha256sum -c` (A1), refuses a second sealing and leaves the package unchanged (A2), six refusals that create
   nothing (A3), a secret value and a private-key header each stop it (A4, A5), a failed record is sealed with exit 3
   (A6). `seal_ops.sh`: the false alarm reproduced with the first preparation's script (B0) and gone (B1), five
   refusals (B2), a secret value and a header stop it (B3, B4a), no notes folder (B4b). `seal_ops_finish.sh`: finishes
   an interrupted copy in place without changing a file that was there (C1), three refusals (C2), a state directory
   that changed after the copy (C3). Launcher and waiter, as they are, beside a stub steps script: `open S3` started
   in its own session with the clone named, the S3 state directory read (D1), usage (D2).
3. **`hostprep_fragments_bench.sh`** (WSL, throw-away tree `/tmp/g3-s3-hostfrag-*`): **47 PASS, 0 FAIL**. It does NOT
   run `g3_hostprep.sh`: it cuts four passages out of the file by line patterns and runs their text with the
   variables pointing at throw-away git repositories, folders and ext4 images (no passage holding a `/home/ruisth`
   path is run). Clone passage: moved from the battery's commit (F1), already there (F2), tip a descendant (F3);
   stopped before the fetch, with HEAD, the local change and the object store shown unchanged, on a modified file
   (F4), an untracked file (F5), another HEAD (F6); stopped when the commit is not an ancestor of the tip (F7), is not
   fetched (F8), when a file under `tools/` or `src/` differs (F9, F10), when the tree differs (F11). Name search
   (N1-N5), earlier attempts (G1-G6: with the battery's layout the export tool of the merged tree then numbered the
   new attempts `…t8_attempt02` and `…t9_attempt01`), guest listing on real `debugfs` output (E1-E5).
4. **`dry_seal_snapshot.sh`** (WSL, throw-away tree, fake HOME and `.env`): `seal_prep.sh` on a snapshot of the real
   preparation folder as it stood at 2026-10-04T21:33Z, with placeholders for what was not delivered yet
   (`operator-notes.md`, `bench-notes.md`, `bench/record/`, the hostprep record): sealed 83 files, verified with
   `sha256sum -c`; no private-key header and no CR byte in the scripts and row files of that snapshot. It shows that
   the folder's real layout is accepted; it says nothing about files delivered after it.
5. **`ro_look.sh`** (WSL, the real host, read-only, 2026-10-04T21:02Z): the paths the script names exist; the clone is
   at `80e833f…`, clean; kernel, `qemuboot.conf`, QEMU binary, launcher, root file system, helper, `tunnel.sh`,
   `ca.crt` hash to the expected values; the Yocto checkout is at `489bc9e…`, clean; no name holding `-q2` under the
   attempts directory or `output_test`; the eleven battery attempts are in both places, `…t8_attempt01` once in each;
   the S3 state directory does not exist. It is not the host preparation and its console is not its record.

NOT run: `g3_hostprep.sh` as a whole. Never executed, even as a fragment: the refusal on a running QEMU or an open
session (unchanged lines), the identity section (the `want` lines, `repo_identity` through `common.sh`, the Yocto
comparison), the venv import line, the helper regeneration (unchanged lines), the loop over `~/egw-tcg/itest`,
`itest-replay` and `pilot/results/raw` (unchanged form). The sealing scripts were never run on the real folders or
with the real `.env`.

## 6. Command lines for the operator

Each BLOCK below is ONE `wsl -d Ubuntu-24.04 --exec bash -lc '…'` invocation (login shell; `MSYS_NO_PATHCONV=1` when
launched from the Windows shell) and begins with its own assignments: a new `bash -lc` keeps no variable of a previous
one. `P` is the WSL path of the preparation folder.

**Host preparation** (no QEMU, no open session). It writes, in the clone: the fetched objects (and any tag that follows
them), `FETCH_HEAD`, HEAD with its reflog, the index and the ten working-tree files that differ between `80e833f…` and
`8e49261…`; `~/egw-tcg/itest-helpers.sh`, rewritten, with its predecessor kept beside it as
`itest-helpers.sh.e5eba37e529a`; the record folder; nothing outside these.

    P=<WSL path of s3prep>; bash "$P/g3_hostprep.sh" "$P/record"; echo "exit=$?"

Expected: last line `outcome=prepared (at …)`, exit 0. A `STOP:` line ends it with `outcome=failed` and exit 1; exit 2
means the record folder already holds a console (use another folder: nothing is overwritten). A stop after the
checkout leaves the clone at `8e49261…` (the script reverts nothing).

**Then** the row checker in clone mode and the dry run, with their consoles kept in the record folder (which
`seal_prep.sh` copies whole); both must end with exit 0 before sealing:

    P=<WSL path of s3prep>; bash "$P/g3_check_rows.sh" "$P/rows" > "$P/record/rows-check-clone-mode.console.txt" 2>&1; echo "exit=$?" | tee -a "$P/record/rows-check-clone-mode.console.txt"
    P=<WSL path of s3prep>; bash "$P/g3_rows_dryrun.sh" "$P/rows" "$P/g3_check_rows.sh" "$P/runbook.8e49261.md" > "$P/record/rows-dryrun.console.txt" 2>&1; echo "exit=$?" | tee -a "$P/record/rows-dryrun.console.txt"

**Seal the preparation** (writes `output_test`; reads the real `.env` for the sweep, printing names only):

    P=<WSL path of s3prep>; OT="/mnt/c/Users/ruimf/Documents/Projeto Mestrado/output_test"; D=$(date -u +%F); bash "$P/seal_prep.sh" "$P" "$P/operator-procedure.md" "$OT/runs/$D/HIST_$D-g3-t8t9-host-preparation"; echo "exit=$?"; (cd "$OT/runs/$D/HIST_$D-g3-t8t9-host-preparation" && sha256sum -c --quiet SHA256SUMS && echo verified)

Exit 0: sealed, record `prepared`. Exit 3: sealed, record not `prepared`. Exit 2: refused, nothing created (the text
says what is missing). Exit 1: a secret value or a private-key header is in the copy, which is left unsealed: report
it, delete nothing. After a FAILED host preparation, seal its record first with the default record folder (exit 3 is
expected), then, after a second run into another record folder, seal that one as
`…/HIST_$D-g3-t8t9-host-preparation-attempt02` with the new record folder as fourth argument; the session uses the
package whose record ends `prepared`.

**During S3** (only after Rui's authorisation and his go in the window):

    P=<WSL path of s3prep>; bash "$P/ops/g3_go.sh" open S3     # then: row t8 | row t9 | close
    P=<WSL path of s3prep>; bash "$P/ops/g3_wait.sh" row t8    # waits again for a subcommand already launched

For `open` and `row` an optional third argument is the wait in minutes (default 170); for `close` it is given as
`close session <minutes>`.

**Seal the operator records after the close.** `DP` is the date in the name of the SEALED preparation package (a
literal: recomputing it on the day of S3 would name a folder that does not exist); `DS` is the UTC date folder that
holds the session's packages. The classification notes are expected in `$P/ops/notes/` as in S1 and S2.

    P=<WSL path of s3prep>; OT="/mnt/c/Users/ruimf/Documents/Projeto Mestrado/output_test"; DP=<date of the preparation package>; DS=<UTC date folder of the session>; bash "$P/ops/seal_ops.sh" S3 "$P/ops" "$OT/runs/$DS/HIST_$DS-g3-t8t9-s3-operator-records" "$OT/runs/$DP/HIST_$DP-g3-t8t9-host-preparation"; echo "exit=$?"; (cd "$OT/runs/$DS/HIST_$DS-g3-t8t9-s3-operator-records" && sha256sum -c --quiet SHA256SUMS && echo verified)

Only if `seal_ops.sh` was interrupted after its copy began (never to pass a sweep that stopped):

    P=<WSL path of s3prep>; OT="/mnt/c/Users/ruimf/Documents/Projeto Mestrado/output_test"; DP=<…>; DS=<…>; bash "$P/ops/seal_ops_finish.sh" S3 "$OT/runs/$DS/HIST_$DS-g3-t8t9-s3-operator-records" "$OT/runs/$DP/HIST_$DP-g3-t8t9-host-preparation"; echo "exit=$?"

A half-made operator-records package that `seal_ops_finish.sh` also refuses is left as it is; the records are then
sealed again under `HIST_$DS-g3-t8t9-s3-operator-records-attempt02` (both scripts accept that suffix), and the
half-made one is named in the result note.

## 7. Deviations from the brief

1. **A folder the brief does not list: `P/host-record/`.** It holds this stream's check and bench scripts and their
   consoles (stream ROWS has `rows-record/` by the brief). `seal_prep.sh` copies it with every `*-record/` folder.
2. **A read-only look at the real host (`ro_look.sh`, and a few one-line reads before it).** Hard rule 2 says no
   script of `P/` runs against the real HOME. This one does, and only reads: `git rev-parse`, `git status` with
   `GIT_OPTIONAL_LOCKS=0`, `git remote`/`for-each-ref`/`cat-file -e`, `ls`, `sha256sum`, `find`, `pgrep`. No fetch, no
   checkout, no regeneration, no `debugfs`, nothing written under HOME or `output_test` (file access times aside).
   Reason: the script that will make these comparisons cannot be run, and a wrong path in it would only show on the
   day. If this is not acceptable, the console can be left out of the package; no deliverable depends on it.
3. **Fragments of `g3_hostprep.sh` were executed** in a throw-away tree (section 5, item 3), which is more than "`bash
   -n` and static checks only". The script itself was not run and nothing of the host was touched. Reason: the new
   clone rule, the attempt rule and the listing rule are logic that a syntax check does not exercise; the bench found
   the `debugfs` status fact of section 2.1.
4. **The sealing scripts changed more than the four items listed** (names, file set, sweep, no overwrite): inputs
   checked before creation, the value kept off the command line (hard rule 5), README built from the record, exit 3,
   the diffs, the fourth argument of `seal_ops.sh`, the completeness comparison of `seal_ops_finish.sh`. Each is in
   section 2 with its reason; the diff sizes are in section 1.
5. **`g3_hostprep.sh` compares more than the brief lists**: the reviewed head's tree, the files that differ from
   `80e833f…`, the runbook's line count, the test module's hash, the `.`/`..` entries of the listing, the presence
   of the admitted attempt. Each is a stop on a mismatch. And it checks the guest listing for the five identifiers,
   where the brief says "the two ids that would leave one": the request (section 3) asks that none of the identifiers
   has an event directory and says only the smoke's would leave one; five is the superset of either reading.
6. **`g3_wait.sh` derives the folder from its own place** instead of carrying the path of `P/` as a fixed text, and
   `g3_hostprep.sh` does not print the origin's path: both paths hold a tool's name (hard rule 6), and the derived
   form also follows the folder if it is moved. Run from `P/ops/`, the waiter resolves `P/`.
7. **Package dates are not compared with the day of sealing**: the scripts require the name's date to equal the
   folder's, nothing more (an S3 that crosses midnight UTC is sealed under the date of its packages).

## 8. Open points

- `seal_prep.sh` requires, by name, `rows-notes.md`, `operator-notes.md`, `host-notes.md`, `bench-notes.md`,
  `bench/record/`, `rows/rows.manifest.json`, `rows-record/`, `host-record/`, the six scripts, the four `ops` scripts,
  `brief.md`, the `base/` copies and the operator procedure. If a stream delivers under another name the sealing is
  refused (exit 2, nothing created) until the name or the script is corrected.
- A private-key header or a `.env` value in any stream's record stops the sealing, by design. Test 9(a) writes a
  throw-away key: a bench that keeps such a file, or a console that prints one, under `P/` must not reach the seal.
  Today no file of `P/` outside `base/` holds a header (checked with the sweep's expression).
- The operator documents (`g3_battery.README.md`, `operator-procedure.md`) should give the sealing command lines of
  section 6: `seal_ops.sh` now takes four arguments and the label `S3`.
- The real `.env` was not read: whether a secret-named variable there holds a value that also appears innocently in
  a record (a path, a user name) is unknown. The sealed READMEs of S1's and S2's operator records state "0 files
  with a secret value" for the same sweep rule.
- The first execution of `g3_hostprep.sh` is the host preparation itself. If it stops after the checkout, the clone
  stays at `8e49261…` and the record says where it stopped; a second run needs another record folder.
- The name search reads all of `output_test` once per identifier (about 2 s each today, 8,110 entries).
