# Stream HOST: notes (2026-10-05, session S4, test 6 only)

Scope: `g3_hostprep.sh`, `seal_prep.sh`, `ops/seal_ops.sh`, `ops/seal_ops_finish.sh`, `ops/g3_go.sh`, `ops/g3_wait.sh`,
revised for session S4 (test 6 only, plan entry `controller_restart-r04`). `P` is the preparation folder named in the
first lines of the brief; `P/base/` holds the copies each revision started from. **`g3_hostprep.sh` was not run**
(section 5 says what was).

## 1. Deliverables

| File | sha256 | `diff --stat` against `P/base/` |
|---|---|---|
| `g3_hostprep.sh` | `ad214aeba54f6ede31dc3bbb8272cc55ff3e3645583e062ca0277a20292845ec` | 233 insertions, 71 deletions (370 lines; base 208) |
| `seal_prep.sh` | `8ea6f7040c6e492bb5aaec4f7a9bb025adf5058b537d932384214075801a3fff` | 56 insertions, 37 deletions |
| `ops/seal_ops.sh` | `d8b3de3cff5bfc210f64b4f0eb91d630812194f6e63875d4bf1a8048d4d72044` | 23 insertions, 16 deletions |
| `ops/seal_ops_finish.sh` | `97f50ceb4ae8e0319e34b6d7c064b88dc40f54b591032ae9083c5edf3b99b51b` | 13 insertions, 13 deletions |
| `ops/g3_go.sh` | `cb77af8965ba00d844c40328944f3a16d4b5a9ba07b953368bf663f2cfe10625` | 4 insertions, 4 deletions |
| `ops/g3_wait.sh` | `28dc98ce620b80f677b3e13e20a0292b62419f1a711c5810bebeb290f8ee2415` | 3 insertions, 3 deletions |

Where the base copies come from (each compared byte for byte with `cmp`, read-only, against `output_test/runs/2026-10-05/`):
`base/g3_hostprep.sh` (sha256 `6613f152…`, the script whose record ended `outcome=prepared` on 2026-10-05) and
`base/seal_prep.sh` equal those sealed in `HIST_2026-10-05-g3-t8t9-host-preparation`; the four `base/ops/*.sh` equal
those sealed in `HIST_2026-10-05-g3-t8t9-host-preparation-attempt02/ops/`, and `g3_go.sh`, `g3_wait.sh`, `seal_ops.sh`
also equal the copies in S3's operator records (`HIST_2026-10-05-g3-t8t9-s3-operator-records-attempt02/operator/`).

Records of this stream, in `P/host-record/` (a folder the brief does not list; section 7, item 2):

| File | sha256 |
|---|---|
| `ro_look.console.txt` (read-only look at the host, 2026-10-05T18:35Z) | `4c7645bdcc4f72c2fc6ede2aee2ee3bb37e26339ac5ed3d701489f4d7e933d92` |
| `plan_check_bench.sh` | `db5be657bf1399a69dd5486ff3de7b38b387b339c7719c930fca752bc61ac523` |
| `plan_check_bench.console.txt` (17 PASS, 0 FAIL) | `b430ca492289e44d161d458fb6fc66c989f3a17eef488726e85ee5d61971c101` |
| `static_values.sh` | `a9f3b5488aa0f88e13f9dcac0a41e50996ea4b65ab2909fc03ce6d6279c82f42` |
| `static_values.console.txt` (61 same, 0 DIFFERENT) | `f68a946967a7f8464b1164a60bf0067d0c42187c7b359907b1d5636205983477` |
| `static_syntax.sh` | `c0a3e27e72214e084adb35afae414cd2312cf6e790638e763ea416be67421fbd` |
| `static_syntax.console.txt` | `ad34977a36dd943671b21a48991f67f30cf879206a501ee9d02f11c8442cd348` |
| `seal_bench.sh` | `c016a38c8e0dddaa433e598d5d1595d92f8bce73f9460d5bad77db61eeb02c28` |
| `seal_bench.console.txt` (83 PASS, 0 FAIL) | `5cdf170ceed7bfa3d029e9fe232f0a82a93ad9c1f37be47ef53bb5a9e5810104` |

Every console was made on the final bytes listed above (each begins with, or lists, the sha256 of what it checked).

## 2. What changed, and why

Every change of behaviour stands under a comment naming `S4` and the part of the brief it answers.

### 2.1 `g3_hostprep.sh`

- **Constants (lines 18-55).** `TOOLS=1fd9792…`, `TREE=14f89c4…`; `PREVIOUS=8e49261…` (S3's commit, the only other HEAD the
  clone may be at; it replaces S3's `BATTERY=80e833f…`, which is no longer admitted: section 7, item 8);
  `REVIEWED=e375026…` (the reviewed head of PR #57); `ROOTFS_SHA=6fce1688…`; new: `DRIVERS_SHA`, `COLLECTOR_SHA`,
  `DEPLOY_TREE`, `DEPLOY_TREE_CANDIDATE`, `PLAN`, `PLAN_BEFORE_SHA`, `PLAN_AFTER_SHA`, `RID`, `DATA_DISK`,
  `DATA_DISK_SIZE`, `T6_ADMITTED`. S3's five `-q2` identifiers and `T8_ADMITTED` are gone. Sources: section 4.
- **The gate on the clone (lines 76-87), unchanged in form.** Before anything is fetched, a non-empty `git status
  --porcelain` is a stop, and so is a HEAD that is neither `8e49261…` nor `1fd9792…`; nothing is discarded, reset or
  stashed anywhere. Up to that point the script has written only `branches-before.txt` in the record, and the status is
  read with `GIT_OPTIONAL_LOCKS=0`, so the gate itself does not rewrite the clone's index: "stop and change nothing".
- **Fetch and checkout (lines 89-107), unchanged mechanics.** `git fetch origin refs/remotes/origin/dev` (the Windows
  repository's view of the remote `dev`; into `FETCH_HEAD` only, no local ref changes); `1fd9792…` must be in the clone
  after the fetch and an ancestor of, or equal to, the fetched tip (the tip is NOT required to be the commit; today the
  Windows repository's `origin/dev` is `1fd9792…` itself, `ro_look.console.txt`); detached checkout of `1fd9792…`, never
  of the tip; HEAD and tree `14f89c4…` compared; clean status; every branch unchanged (`cmp` of the two listings); the
  reviewed head's tree compared with `14f89c4…`.
- **Files that differ from S3's commit (lines 108-115): recorded, no longer judged.** S3 stopped on any file under
  `tools/` or under `src/` outside `src/tests`, because S3's tools were the battery's. S4's tools changed by design
  (request section 2): 41 files differ today (34 modified, 7 added), among them `tools/session/{collector_check.py,
  collector_shortfall.py,preflight.sh,README.md}`, `src/deployment/{README.md,scripts/collect-resources.sh}` and six
  modules of `src/egw_experiments`. What changed is fixed by `TREE` and compared by hash below.
- **No rebuild (lines 116-126).** The read-only loop against `489bc9e…` keeps eight of its nine paths (controller,
  simulator, schemas, Dockerfile, the two locks, `pyproject.toml`, `CONTRACTS.md`). `src/deployment` left the loop: it
  now differs from the image commit, and is required to differ by exactly `src/deployment/README.md` and
  `src/deployment/scripts/collect-resources.sh` (line 124: an exact comparison of the name list).
- **The venv (lines 127-133).** S3 printed the module path the venv imports; S4 compares it with
  `$C/src/egw_experiments/__init__.py` and requires `g3-t6` among `plan_gen.SUPPLEMENTS`: the plan step below and the
  harness of row t6 run the merged modules through this venv (the brief's note: the venv imports from the clone).
- **Identities (lines 135-183).** The runbook `31716593…` and its 1,624 lines; the rule source `b63ef7d8…`; the
  unchanged ones as in S3; new: the collector `9e678b02…` (line 146), the deployment tree `573e902b…`, the image commit's
  deployment tree `e056d389…` and the difference of the two trees, exactly `README.md` and
  `scripts/collect-resources.sh` (lines 155-161); `drivers_sha256` `2c209b09…` read through the clone's own
  `repo_identity` (`common.sh`), which is how the steps script computes and compares it (`verify_candidate`; reproduced
  from the git blobs with `drivers_hash.sh`, both collations); the root file system at `6fce1688…` (line 183). The
  campaign plan is no longer "recorded, not compared" here: it has its own step; `sut_environment.json` is still
  recorded, not compared.
- **Helper regeneration (lines 185-192): unchanged text.** Expected `e5eba37e…`, 545 lines, predecessor kept. Since S3
  the predecessor's name, `itest-helpers.sh.e5eba37e529a`, already exists with the same bytes: `regen_helpers.py`
  keeps an existing predecessor file as it is (`if not os.path.exists(keep)`) and rewrites the helper with the same
  bytes.
- **`controller_restart-r04` unused on the host (lines 194-210).** The run directory `pilot/results/raw/<id>`,
  `itest/<id>`, `itest/<id>.*`, `itest-replay/<id>`, `itest-replay/<id>.*`; then a search by NAME (`find -name
  "*<id>*"`) under the attempts directory, the whole of `output_test`, `itest`, `itest-replay` and `pilot/results`
  (a folder that does not exist is said so and skipped), skipping a sealed S4 preparation package
  (`HIST_*-g3-t6-host-preparation*`). A search that fails is a stop, never "fresh".
- **Earlier attempts of row t6 (lines 212-237).** Every `*_g3-qualification-*_attempt*` under the three roots the export
  tool numbers from (searched recursively, as its `rglob` does) is listed into the record. The attempts of other rows
  are admitted as they are. For row t6, exactly `20261003T132936Z_g3-qualification-t6_attempt01` is admitted, and only
  where it is kept (`<attempts>/…` and `output_test/runs/2026-10-03/…`: the two paths the steps script's `fresh_row`
  admits, brief point 5 of stream OPERATOR); any other t6 attempt, `attempt02` included, or the admitted name anywhere
  else, is a stop; so is the admitted attempt found nowhere (the new one would then not be `attempt02`).
- **The guest root file system (lines 239-252).** Hashed immediately before the listing (new) and after it (and once
  more in the identity section): `6fce1688…` each time. Offline `debugfs -c` listing of
  `/opt/egw/deployment/data/events`; the `.` and `..` entries are required (S3's rule: `debugfs` ends 0 on a missing
  directory); `controller_restart-r04` as a name and as a prefix of a name is a stop.
- **The data disk (lines 254-262, new).** `ls -l`, the size by `stat -c %s` compared with 34,359,738,368 B, and the
  ext4 header read with `/usr/sbin/dumpe2fs -h` and printed with the same `grep` as `guest_session_open.sh` line 115
  (prefixed `data disk header: `). Never hashed. The header is recorded, not judged (a `dumpe2fs` that cannot read it
  is a stop).
- **The plan entry (lines 264-361, new), LAST.** It runs only when every check above has passed, so that the plan is
  changed only for an identifier shown fresh everywhere (the brief lists it before the freshness checks; nothing in it
  depends on that order). The top level of `~/egw-tcg/pilot` is listed before and after (`ls -A1`, hidden names
  included). On `c195bd3f…`: the plan is copied into the record as `campaign_plan.predecessor.json` (never over an
  existing one; `cmp` with the plan), then `cd $C/src && $PY -m egw_experiments plan-supplement --plan <plan> --entry
  g3-t6`, its console kept as `plan-supplement.console.txt` and shown in the record, its exit status required 0. On
  `61d55940…` (a re-run after the entry was added): said so, nothing run or changed. Any other value: a stop with
  nothing run. Then: the same top-level names (the tool writes its new text into a hidden temporary file beside the
  plan and moves it over the plan in one step; a leftover would show here), sha256 `61d55940…`, and the content check:
  - **bytes**: the plan is the canonical serialisation (`plan_gen.plan_to_json`: indent 2, sorted keys, `runs` the last
    key), so it ends with the 7 bytes `\n  ]\n}\n` and an entry of `runs` is preceded by `,\n    {\n`. Cutting the plan at
    the last such separator and closing it with the 7 bytes gives the predecessor exactly: its sha256 must be
    `c195bd3f…` and, when this record kept the predecessor, it must equal the kept copy byte for byte, whose first
    `size - 7` bytes are then the plan's first `size - 7` bytes. So every byte of the 95 entries (and of everything
    before them) is unchanged and at the same offset; in a re-run the sha256 alone proves it.
  - **JSON**: 95 entries before, 96 after; the first 95 equal to the predecessor's as JSON values; every field other than
    `runs` equal; the last entry, serialised with sorted keys, equal to the request's entry
    (`{"condition_id": "controller_restart", "cooldown_s": 0, "duration_s": 600, "order": 96, "rate_msg_s": 11.2,
    "repetition": 4, "run_id": "controller_restart-r04", "runner": "simulator", "scenario": "nominal", "seed":
    1715385812, "status": "planned", "supplement": "g3-t6", "warmup_s": 0}`: a string comparison, so `0` and `0.0`
    differ); `controller_restart-r04` held exactly once.
  Nothing else under `~/egw-tcg/pilot` is written.
- **The end (lines 363-367, new).** The clone is still at `1fd9792…`, tree `14f89c4…`, clean: the venv import and
  `plan-supplement` ran with `PYTHONDONTWRITEBYTECODE=1` and wrote nothing in it.
- **Kept**: the record directory is the argument and its `console.txt` is never overwritten (line 57, exit 2); the
  outcome line is printed only at the very end and only when no `fail` ran; its form stays S3's `outcome=prepared (at
  …)` (section 7, item 1); `fail` prints `STOP: …` and `outcome=failed (at …)` and exits 1.

### 2.2 `seal_prep.sh`

- **Name**: `…/<date>/HIST_<date>-g3-t6-host-preparation[-attemptNN]` under a folder of the same date; anything else is
  refused, nothing created. **Never overwritten**: an existing package is refused (exit 2) and the refusal names the
  first free `-attemptNN` name (lines 21-27; section 7, item 9).
- **The S4 file set (lines 36-48)**: the six scripts, the four `ops/` scripts, `seal_prep.sh`, the four notes
  (`rows-notes.md`, `operator-notes.md`, `host-notes.md`, `bench-notes.md`), `brief.md`, `bench-brief.md` (new: the bench
  stream's brief), `runbook.1fd9792.md` (was `runbook.8e49261.md`), `rows/rows.manifest.json`, `rows-record/`,
  `bench/record/`, `host-record/`, the `base/` copies and the hostprep record; all looked for before anything is
  created. `prep_brief.md` and `prep_bench_brief.md` are the two briefs; every other `*.md` of `P` (the request draft
  included) goes to `verification/`; the runbook blob and the operator procedure are at the top.
- **Diffs**: each revised file against its `base/` copy, and (new) the operator procedure against
  `base/operator-procedure.md` (lines 86-93): 12 diffs.
- **Not copied, and named** in the console and the README: `base/` and the two copies of repository files given for
  reading (`preflight.1fd9792.sh`, `test_runbook_itest_helpers.1fd9792.py`); S3's fixed text naming
  `operator-procedure.battery.md` is gone.
- **README**: authority (the request of 2026-10-05 and the register entry after the merges of #55, #56, #57), the
  record's outcome line and its count of `STOP:` lines, the S4 lines of the record verbatim (collector, deployment trees,
  data disk, `plan before/after`, `plan check`, `added …`, `plan-supplement exit=`, `row t6:`, the three `HEAD=` lines),
  the step-file table, and the sentence that test 6's merged lines have not run on the guest.
- **Unchanged**: the sweep (values through a file descriptor, never on a command line; names only printed; the
  private-key pattern that does not match its own text), the CR check, exit 3 for a record that is not `prepared`.

### 2.3 `ops/seal_ops.sh`, `ops/seal_ops_finish.sh`

Label `S4` only (`S1`, `S2`, `S3`: "the records of S1, S2 and S3 are sealed"); state directory
`${EGW_G3_STATE:-$HOME/egw-exec/g3-t6-s4}` (the steps script's, brief "Fixed values"); package
`HIST_<date>-g3-t6-s4-operator-records[-attemptNN]`; the preparation package must be a sealed
`HIST_*-g3-t6-host-preparation*`; README texts name S4, `state/session-S4.env`, `state/S4-g3_battery.sh`,
`state/S4-rows.manifest.json` (the names the steps script gives its copies "as opened": `$STATE/$LABEL-…`).
`seal_ops.sh` names the next free `-attemptNN` name when the package exists. Nothing else changed: the sweep, the
completeness comparison and the "not a way round the sweep" rule of `seal_ops_finish.sh` are S3's.

### 2.4 `ops/g3_go.sh`, `ops/g3_wait.sh`

Usage texts `open S4|row t6|close`; the waiter's default state directory `g3-t6-s4`. The paths of `P/` are derived from
the scripts' own place, as in S3 (no fixed path). The launcher still starts ONE subcommand with `setsid`, no terminal,
`EGW_EXEC_REPO=$HOME/egw-exec/repo`; the waiter signals nothing; the default wait stays 170 min (a waiter that times
out leaves the subcommand running).

## 3. `bash -n`, line ends, shellcheck

`static_syntax.console.txt` (WSL, final bytes): `bash -n` passes for the six scripts and the four record scripts; 0 CR
bytes, no BOM, ASCII only in each. shellcheck 0.11.0 (unpacked into `/tmp/g3-s4-host-sc`), against each base copy:

- `g3_hostprep.sh`: 7 findings, base 5. The two added are of kinds the base already had and are intended: SC2231 at
  line 199 (the unquoted `$RID.*` must glob, as S3's `$id.*`) and SC2015 at line 283 (`cp && cmp || fail`; `fail`
  exits). The rest as in the base (SC1091, SC2034 for `common.sh`'s variables, SC2015 at line 247).
- `seal_prep.sh` 2 (base 2), `seal_ops.sh` 2 (2), `seal_ops_finish.sh` 3 (3), `g3_go.sh` 0 (0), `g3_wait.sh` 1 (1): the
  same notes as the base copies.

A sweep of the six scripts and of `host-record/` for the names of AI tools and vendors found none; no record holds an
absolute path of the scratchpad, a fake secret value of the bench or a private-key header (checked with the sealing
scripts' own expression).

## 4. Hard-coded values of `g3_hostprep.sh` and where each was taken from

`static_values.sh` reads each value out of the script's text and compares it with its source: **61 same, 0 DIFFERENT**
(`static_values.console.txt`, script sha256 `ad214aeb…`).

| Value | Source |
|---|---|
| `TOOLS` `1fd9792b…`, `TREE` `14f89c4d…`, `REVIEWED` `e375026d…` | the read-only worktree's HEAD, its tree and the merge's second parent; `refs/remotes/origin/dev` of the Windows repository is `1fd9792b…` today; the reviewed head's tree is `14f89c4d…` |
| `PREVIOUS` `8e492613…` | S3's sealed host-preparation record (the clone after its checkout); an ancestor of `TOOLS`; the clone's HEAD today (`ro_look`) |
| `IMAGE` `489bc9e5…` | S3's sealed record: `source_commit=` of the controller identity, and the Yocto checkout |
| runbook `31716593…`, 1,624 lines; rule source `b63ef7d8…`; `local_export.py` `544c9b3d…` (also in the `repo_identity` comparison); `fetch_started_at.sh` `9c6dc824…`; `images.lock.env`, `compose.yaml`, `mosquitto.conf`, `CONTRACTS.md` | `git cat-file blob 1fd9792:<path>` hashed |
| `COLLECTOR_SHA` `9e678b02…` | the blob of `src/deployment/scripts/collect-resources.sh` at `1fd9792` |
| `DEPLOY_TREE` `573e902b…`, `DEPLOY_TREE_CANDIDATE` `e056d389…`, the two-name difference, `src/schemas` `1d5284cf…` | `git rev-parse <commit>:<path>`, `git diff --name-only`; `e056d389…` also in S3's sealed record |
| no-rebuild paths | `git diff --stat 489bc9e 1fd9792 -- <path>`: empty for the eight, the two names for `src/deployment` |
| `DRIVERS_SHA` `2c209b09…` | `S/g3/battery/drivers_hash.sh` on the worktree at `1fd9792` (38 files; C and en collations agree) |
| helper `e5eba37e…`, 545 lines | the section 6.1 heredoc cut out of the runbook blob at `1fd9792` by `regen_helpers.py`'s rule |
| `ROOTFS_SHA` `6fce1688…` | `rootfs_after_close` of `session-S3.env` in `HIST_2026-10-05-g3-t8t9-s3-operator-records-attempt02/state/`; the host today (`ro_look`) |
| tunnel.sh, ca.crt, controller record and archive, image id `9a293fe1…`, launcher, kernel, `qemuboot.conf`, QEMU binary | S3's sealed host-preparation record (the host on 2026-10-05 08:41Z) |
| `PLAN_BEFORE_SHA` `c195bd3f…` | the plan today (`ro_look`) |
| `PLAN_AFTER_SHA` `61d55940…`, the expected r04 entry | the merged `plan-supplement` run on a copy of today's plan (`plan_check_bench.console.txt`, P1) |
| `RID` `controller_restart-r04` | the runbook blob, line 1421 (`host$ RID=controller_restart-r04; …`) |
| `DATA_DISK`, `DATA_DISK_SIZE` 34,359,738,368 | `guest_common.sh`'s default path; S3's second open (`20261005T114428Z_guest-session_attempt11`, console 001) and the host today |
| `T6_ADMITTED` | `output_test/runs/2026-10-03/20261003T132936Z_g3-qualification-t6_attempt01` and the attempts directory today; the only t6 attempt under `output_test`; no name holding `controller_restart-r04` under `output_test` |
| paths under `/home/ruisth` and of `output_test` | unchanged from S3; `Y`, `BUILD`, `DEP` as `guest_common.sh` |

## 5. What was run, and what was not

Run:

1. **`ro_look`** (inline read-only commands in WSL against the real host, NOT a script of `P/`; console
   `ro_look.console.txt`): no QEMU process, no `current_session`; the clone at `8e49261…`, tree `2f05148…`, 0 porcelain
   lines, two branches; the origin's `refs/remotes/origin/dev` is `1fd9792…`, which is not in the clone yet; the venv
   imports `egw_experiments` from `/home/ruisth/egw-exec/repo/src`; the plan `c195bd3f…`, `pilot/` holds
   `campaign_plan.json` and `results` only; none of the r04 paths exists, no name holding r04 under the attempts
   directory, `itest`, `itest-replay`, `pilot/results`; one t6 attempt in the attempts directory (S2's attempt01); no
   state directory `g3-t6-s4`; the root file system `6fce1688…`; the data disk 34,359,738,368 B, `dumpe2fs -h` 0,
   state clean. Its one write: a copy of the plan into `/tmp/g3-s4-host-plan`.
2. **`plan_check_bench.sh`** (WSL, `/tmp/g3-s4-host-plan`, `HOME` inside it, the merged module copied from the
   worktree, no bytecode): **17 PASS, 0 FAIL**. The merged `plan-supplement` on the copy gives `61d55940…` and leaves no
   other name in the folder (P1a, P1b); the content check cut out of `g3_hostprep.sh` passes with the predecessor (P1c)
   and without it (P2b); `plan-supplement` again on the result leaves it unchanged (P2a); the check refuses an earlier
   entry changed, the new entry's seed changed, a field added to it, a field outside `runs` changed, a non-canonical
   plan, an entry after r04, a kept predecessor that differs, and today's plan itself (P3a-P3h).
3. **`static_values.sh`** (Windows shell, read-only git on the worktree, read-only `output_test`): section 4.
4. **`static_syntax.sh`** (WSL): section 3.
5. **`seal_bench.sh`** (WSL, `/tmp/g3-s4-host-seal-XXXXXX`, fake HOME, fake `.env` with fake values, a stub `grep` that
   logs its command line; adapted from S3's): **83 PASS, 0 FAIL**. `seal_prep.sh`: seals and verifies a folder laid out
   as `P` is today (A1: 44 files, 12 diffs, the two briefs, the request draft in `verification/`, the S4 lines of the
   record in the README, the left-out entries named); a second sealing refused, unchanged, the next free name given
   (A2); seven refusals that create nothing, S3's package name among them (A3); a secret value and a private-key header
   each stop it without printing the value (A4, A5); a failed record sealed with exit 3 (A6); the next free name skips
   every existing suffix (A7). `seal_ops.sh`: sealed with the S4 state directory by default (B1); refusals (same name,
   label S3, S3's names, an unsealed or S3's preparation package, a missing state directory) create nothing (B2); a
   secret value and a header stop it, and `seal_ops_finish.sh` is not a way round (B3, B4a); no notes (B4b).
   `seal_ops_finish.sh`: finishes an interrupted copy in place (C1), refusals (C2), a state directory changed after the
   copy (C3). Launcher and waiter beside a stub steps script: `open S4` and `row t6` started in their own session with the
   clone named, the S4 state directory read, `status` run; the usage; no process left (D0-D3).

NOT run: `g3_hostprep.sh`, as a whole or as a fragment, except the content check of the plan step (item 2). Never
executed: the refusal on QEMU or a session, the clone gate, fetch and checkout, the identity section, the venv check,
the helper regeneration, the freshness, attempt and guest passages, the data disk passage, the plan step's shell part
(its `case`, the predecessor copy, the `ls -A1` comparison). Their logic is S3's (which ran on 2026-10-05) except where
section 2.1 says otherwise. The sealing scripts were never run on the real folders or with the real `.env`.

## 6. Command lines for the operator

Each block is ONE invocation from the Windows shell, `MSYS_NO_PATHCONV=1 wsl -d Ubuntu-24.04 --exec bash -lc '…'`
(login shell), beginning with its own assignments: a new `bash -lc` keeps no variable of a previous one. `P` is the WSL
path of the preparation folder.

**Host preparation** (no QEMU, no open session). It writes: in the clone, the fetched objects, `FETCH_HEAD`, HEAD with
its reflog, the index and the 41 working-tree files that differ between `8e49261…` and `1fd9792…`;
`~/egw-tcg/itest-helpers.sh`, rewritten with the same bytes; `~/egw-tcg/pilot/campaign_plan.json`, through
`plan-supplement` (entry `controller_restart-r04`); the record folder; nothing else.

    P=<WSL path of t6prep>; bash "$P/g3_hostprep.sh" "$P/record"; echo "exit=$?"

Expected: last line `outcome=prepared (at …)`, exit 0. A `STOP:` line ends it with `outcome=failed` and exit 1; exit 2
means the record folder already holds a console (use another folder: nothing is overwritten). A stop after the checkout
leaves the clone at `1fd9792…` (nothing is reverted). A stop before the plan step leaves the plan at `c195bd3f…`; a stop
inside it after `plan-supplement` ended 0 leaves the plan as `plan-supplement` wrote it and its predecessor in
`$P/record/campaign_plan.predecessor.json`: report it, change nothing (a second run then stops on "neither … nor …"
unless the plan is `61d55940…`).

**Then** the row checker in clone mode and the dry run, consoles kept in the record folder (which `seal_prep.sh` copies
whole); both must end with exit 0 before sealing. The authoritative argument lists are those of `rows-notes.md`; in
S3's form:

    P=<WSL path of t6prep>; bash "$P/g3_check_rows.sh" "$P/rows" > "$P/record/rows-check-clone-mode.console.txt" 2>&1; echo "exit=$?" | tee -a "$P/record/rows-check-clone-mode.console.txt"
    P=<WSL path of t6prep>; bash "$P/g3_rows_dryrun.sh" "$P/rows" "$P/g3_check_rows.sh" "$P/runbook.1fd9792.md" > "$P/record/rows-dryrun.console.txt" 2>&1; echo "exit=$?" | tee -a "$P/record/rows-dryrun.console.txt"

**Seal the preparation** (writes `output_test`; reads the real `.env` for the sweep, printing names only):

    P=<WSL path of t6prep>; OT="/mnt/c/Users/ruimf/Documents/Projeto Mestrado/output_test"; D=$(date -u +%F); bash "$P/seal_prep.sh" "$P" "$P/operator-procedure.md" "$OT/runs/$D/HIST_$D-g3-t6-host-preparation"; rc=$?; echo "exit=$rc"; { [ $rc -eq 0 ] || [ $rc -eq 3 ]; } && (cd "$OT/runs/$D/HIST_$D-g3-t6-host-preparation" && sha256sum -c --quiet SHA256SUMS && echo verified)

Exit 0: sealed, record `prepared`. Exit 3: sealed, record not `prepared`. Exit 2: refused, nothing created (the text
says what is missing; for an existing name it gives the next free `-attemptNN` name, to be used in place of the last
path above). Exit 1: a secret value or a private-key header is in the copy, which is left unsealed: report it, delete
nothing. After a FAILED host preparation, seal its record first (exit 3 expected), then, after a second run into
another record folder, seal that one under the `-attempt02` name with the new record folder as fourth argument; the
session uses the package whose record ends `prepared`.

**During S4** (only after Rui's authorisation and his go in the window):

    P=<WSL path of t6prep>; bash "$P/ops/g3_go.sh" open S4     # then: row t6, then close
    P=<WSL path of t6prep>; bash "$P/ops/g3_wait.sh" row t6    # waits again for a subcommand already launched

For `open` and `row` an optional third argument is the wait in minutes (default 170); for `close` it is given as
`close session <minutes>`.

**Seal the operator records after the close.** `DP` is the date in the name of the SEALED preparation package and `PN`
its full name (with `-attemptNN` if it has one; literals, not recomputed on the day of S4); `DS` is the UTC date folder
that holds the session's packages. The classification notes are expected in `$P/ops/notes/` as in S1-S3.

    P=<WSL path of t6prep>; OT="/mnt/c/Users/ruimf/Documents/Projeto Mestrado/output_test"; DP=<date of the preparation package>; PN=<its name>; DS=<UTC date folder of the session>; bash "$P/ops/seal_ops.sh" S4 "$P/ops" "$OT/runs/$DS/HIST_$DS-g3-t6-s4-operator-records" "$OT/runs/$DP/$PN"; rc=$?; echo "exit=$rc"; [ $rc -eq 0 ] && (cd "$OT/runs/$DS/HIST_$DS-g3-t6-s4-operator-records" && sha256sum -c --quiet SHA256SUMS && echo verified)

Only if `seal_ops.sh` was interrupted after its copy began (never to pass a sweep that stopped):

    P=<WSL path of t6prep>; OT="/mnt/c/Users/ruimf/Documents/Projeto Mestrado/output_test"; DP=<…>; PN=<…>; DS=<…>; bash "$P/ops/seal_ops_finish.sh" S4 "$OT/runs/$DS/HIST_$DS-g3-t6-s4-operator-records" "$OT/runs/$DP/$PN"; echo "exit=$?"

A half-made operator-records package that `seal_ops_finish.sh` also refuses is left as it is; the records are then sealed
again under the next free `-attemptNN` name (both scripts accept it), and the half-made one is named in the result note.

## 7. Deviations from the brief

1. **The outcome line keeps S3's form, `outcome=prepared (at …)`**, where the brief writes `outcome: prepared`. Primary
   source: S3's sealed host-preparation record (`HIST_2026-10-05-g3-t8t9-host-preparation/part1-record/console.txt`,
   last line) and the sealing script, which reads that form (`^outcome=`); the meaning is the brief's (printed only when
   every check passed).
2. **A folder the brief does not list: `P/host-record/`** (this stream's check and bench scripts and their consoles, as
   S3's stream HOST had). `seal_prep.sh` copies it with every `*-record/` folder.
3. **A read-only look at the real host** (`ro_look.console.txt`): inline commands, not a script of `P/` (hard rule 2),
   reading only (`git rev-parse`, `git status` with `GIT_OPTIONAL_LOCKS=0`, `git ls-remote`, `git cat-file -e`,
   `sha256sum`, `ls`, `stat`, `find`, `pgrep`, `dumpe2fs -h`, the venv's import with no bytecode), plus one copy of the
   plan into `/tmp/g3-s4-host-plan`. Nothing was written under HOME or `output_test`. Reason: the script that makes these
   comparisons cannot be run, and a wrong path or value would only show on the day.
4. **A fragment of `g3_hostprep.sh` was executed**: the plan step's content check, cut out of the script and run on
   copies in `/tmp` (section 5, item 2), which is more than "`bash -n` and static checks only". The script itself was not
   run. Reason: the byte rule and the JSON rule are logic that no syntax check exercises, and the bench is also what
   confirms `61d55940…` with the merged code.
5. **`g3_hostprep.sh` checks more than the brief lists**: the venv's module path and its `g3-t6` supplement, the clone
   clean at the end, the top level of `~/egw-tcg/pilot` before and after, the name search into `itest`, `itest-replay`
   and `pilot/results`, the prefix rule on the guest, the image commit's deployment tree, the admitted attempt found at
   least once. Each is a stop on a mismatch.
6. **Admission of S2's t6 attempt by exact path**, not by name anywhere as S3's script admitted its t8 attempt: the
   steps script (`fresh_row`, brief point 5 of stream OPERATOR) admits it only in the attempts directory and under
   `output_test/runs/2026-10-03/`, so a copy elsewhere would halt the row; the preparation stops on it first.
7. **The list of files that differ from S3's commit is recorded, not judged** (section 2.1). S3's rule (no file under
   `tools/` or `src/` outside `src/tests`) would stop S4 by design; the hash comparisons cover what changed.
8. **`BATTERY` renamed `PREVIOUS`** (hard rule 7 allows no renaming beyond what is listed): its value is now S3's
   commit, and the old name would have printed "the battery's commit" for it. The comment on line 23 says so.
9. **No automatic `-attemptNN` name**: the brief's "an `-attemptNN` suffix if the name exists" is implemented as S3's
   rule (the operator gives the name; a suffix is accepted; an existing name is refused) plus the next free name printed
   in the refusal. The operator records name the preparation package by its path, so the name must be the operator's.
10. **`seal_prep.sh` requires `bench-brief.md`** and copies it as `prep_bench_brief.md` (the bench stream's brief, which
    appeared in `P` during this work), and adds the operator procedure's diff against `base/`.

## 8. Open points

- **The plan step's first run on the real plan is the host preparation itself.** On a copy, the merged code gave
  `61d55940…` and the content check passed. If the real plan has changed by then (any value other than `c195bd3f…` or
  `61d55940…`), the step stops with nothing run.
- **The data disk's header is recorded, not judged** (today: state clean, last mounted on `/var/lib/docker`).
- **The name search reads all of `output_test`** (6,266 entries today; S3's record shows about 2 s for a search of the same kind) and stops on any name
  holding `controller_restart-r04` outside a sealed S4 preparation package. Today there is none; a record of another
  stream sealed into `output_test` under such a name before the host preparation would stop it.
- `seal_prep.sh` requires, by name, the four notes, `bench/record/`, `rows/rows.manifest.json`, `rows-record/`,
  `host-record/`, the six scripts, the four `ops` scripts, the two briefs, the runbook blob, the `base/` copies and the
  operator procedure. A stream that delivers under another name makes the sealing refuse (exit 2, nothing created) until
  the name or the script is corrected. `operator-record/`, which stream OPERATOR created, is copied as a `*-record/`
  folder.
- The operator documents (`g3_battery.README.md`, `operator-procedure.md`) should give the sealing command lines of
  section 6: `seal_ops.sh` takes four arguments and the label `S4`, and the preparation package by its full name.
- The real `.env` was not read: whether a secret-named variable holds a value that also appears innocently in a record
  is unknown (S1-S3's sealed READMEs state 0 files for the same rule).
- Observation, no change: the controller image's Dockerfile copies `egw_experiments/` (line 45), which differs from the
  image commit (8 files at S3's commit, 9 at `1fd9792`); the controller imports nothing of it, the image is not rebuilt
  and the running image is identified by its id, and the "no rebuild" list (unchanged since S3) does not include it.
