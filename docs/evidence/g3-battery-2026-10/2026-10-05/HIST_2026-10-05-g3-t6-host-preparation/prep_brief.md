# Preparation of session S4 (test 6 only) — brief for the script streams (2026-10-05)

S = `C:/Users/ruimf/AppData/Local/Temp/claude/C--Users-ruimf-Documents-Projeto-Mestrado/d631a3f3-65ca-4372-97f1-525d6d1e593d/scratchpad`
(from WSL: `/mnt/c/Users/ruimf/AppData/Local/Temp/claude/C--Users-ruimf-Documents-Projeto-Mestrado/d631a3f3-65ca-4372-97f1-525d6d1e593d/scratchpad`)
P = `S/g3/t6prep` — the ONLY directory any stream writes in (plus `/tmp/g3-s4-*` inside WSL for benches).
OT = `C:/Users/ruimf/Documents/Projeto Mestrado/output_test` (read-only for every stream).

## What this is

An MSc project ("edge gateway": an ARM64 Yocto guest under QEMU/TCG on a WSL2 host, six containers). A G3 qualification
battery ran on 2026-10-02/03 (sessions S1, S2) and a session S3 ran tests 8 and 9 on 2026-10-05, all with operator
tooling kept OUTSIDE the repository (`g3_battery.sh` and companions). Test 6 (controller restart, plan entry
`controller_restart-r03`) ran in S2 and was INVALID (the collector's rows inside the restart interval were rejected).
Since then, merged on `dev` as `1fd9792`: test 6's criterion was amended (exactly-once acceptance in the post-drain copy,
recovery within 120 s, every `delta` OK; `lost`/`late` reported only), option A's transition rule
(`--restart-transition-rule 1a-option-a-2026-10-05`), `collector-duration` judged on uptime bounds (new collector
`9e678b02…`), a fresh plan entry `controller_restart-r04` (added by `plan-supplement`), and `acceptance --exactly-once`
wired into test 6's block. One more session, S4, will run ONLY test 6, once. This work prepares the operator tooling for
S4. No guest runs during the preparation.

Read first (all read-only):
- the request draft `P/request-draft.md` — sections 2 to 6 and 8 are the SPECIFICATION of what S4 does;
- the merged runbook blob `P/runbook.1fd9792.md` (sha256 `317165936abed4f3823f53b67b7ac76bafa442cfa1820d4b96479392b280cf0f`,
  1,624 lines); test 6 is "### Test 6" at line 1416, its fenced block lines 1420-1429, the eight `host$` lines 1421-1428;
  the helpers of section 6.1 at lines 610-1154; Appendix B item 24;
- the merged tree, read-only worktree `S/t6m` (detached at `1fd9792bb76f02c6948f33887207dba4837202db`, tree
  `14f89c4d3692aea8ef4f8f1fe29c333a9a7192ec`): `tools/session/*.sh`, `tools/session/guest/*.sh`, `tools/session/*.py`,
  `src/egw_experiments/`, `src/tests/test_runbook_itest_helpers.py` (also copied as `P/test_runbook_itest_helpers.1fd9792.py`),
  `P/preflight.1fd9792.sh`. They are NOT to be modified. Do not run `git` commands that write in any worktree;
- the S3 tooling as it ran (second opening, "S3b"): `S/g3/s3bprep/` (`g3_battery.sh`, README, `operator-procedure.md`,
  `bench/`, `ops/`) and the S3 first preparation `S/g3/s3prep/` (`g3_extract_rows.py`, `g3_check_rows.sh`,
  `g3_rows_dryrun.sh`, `g3_hostprep.sh`, `seal_prep.sh`, `rows-notes.md`, `host-notes.md`, `operator-notes.md`,
  `bench-notes.md`, `check-notes.md`), and the battery's (`S/g3/battery/prep/`, `S/g3/battery/packet.md` section 4 and
  section 5's T6 row) — the battery's operator script ran row t6 in S2; its t6 code paths are still in the S3 script;
- S2's sealed T6 attempt `OT/runs/2026-10-03/20261003T132936Z_g3-qualification-t6_attempt01/` (its `SUMMARY.md`,
  `commands.jsonl`, `console/003-t6.stdout.txt`) and S3b's operator records
  `OT/runs/2026-10-05/HIST_2026-10-05-g3-t8t9-s3-operator-records-attempt02/`.

`P/` already holds a working copy of every script to revise and `P/base/` an untouched copy of each (for diffs).

## Hard rules (every stream)

1. Write ONLY under `P/` (and `/tmp/g3-s4-*` in WSL for benches). Never write under `~/egw-exec`, `~/egw-tcg`, `~/yocto`,
   `OT`, `ChatGPT/`, any repository worktree (`S/t6m`, `S/t6int`, `S/pb`, ...) or the sealed earlier-preparation
   directories (`S/g3/s3prep`, `S/g3/s3bprep`, `S/g3/battery`).
2. No guest, no QEMU, no docker, no ssh to anything, no build. Never run a script of `P/` against the real `HOME`: benches
   run in WSL with `HOME` and every `EGW_*` variable pointing inside `/tmp/g3-s4-<name>`, with stubs first on `PATH`, as
   the S3 benches did (`S/g3/s3bprep/bench/bs3b_setup.sh`). `g3_hostprep.sh` is NOT run by any stream (it writes on the
   host): only `bash -n`, `shellcheck` if available, and static checks.
3. WSL invocation from the Bash tool: `MSYS_NO_PATHCONV=1 wsl -d Ubuntu-24.04 --exec bash -lc '<command>'`. The venv's
   python is `~/egw-exec/venv/bin/python` (read-only use, with `PYTHONDONTWRITEBYTECODE=1`; note it imports
   `egw_experiments` from `~/egw-exec/repo/src`, which is still at `8e49261` today: for the merged code use
   `PYTHONPATH=<S/t6m>/src` or the bench's copy). Do not leave long-lived processes behind.
4. Files are LF-only, UTF-8, no BOM. On Windows never use Python `write_text` without `newline="\n"`: edit with the
   Edit/Write tools, or write bytes. After editing, `grep -c $'\r'` is 0 and `bash -n` passes. Python or shell scripts
   that contain backslashes are created with the Write tool, never through a shell heredoc.
5. No secret on a command line or in a record; never `set -x` anywhere near the simulator (its password is on its argv);
   the step shells use `set -v`: keep that.
6. British English in every text; ISO dates. Do not name any AI tool or vendor in any file.
7. Keep changes minimal and local: these scripts worked through three sessions. Change what S4 needs, nothing else; no
   refactoring, no renaming beyond what is listed; the t8/t9 code may stay where it is if unreachable (say so). Every
   change of behaviour made for S4 stands under a comment naming `S4` and the point of this brief it answers. Where an
   earlier preparation's checks or benches fixed a defect, do not reintroduce it.
8. If this brief contradicts a primary source (the runbook blob, a frozen driver, a sealed record), follow the primary
   source and say so in your notes; do not guess.

## Fixed values

- Tools and procedure: commit `1fd9792bb76f02c6948f33887207dba4837202db`, tree `14f89c4d3692aea8ef4f8f1fe29c333a9a7192ec`.
  The clone moves from `8e492613d36490a560ae56beabd6d5c2c01a8696` (S3's) to it at the host preparation.
- Runbook at that commit: sha256 `317165936abed4f3823f53b67b7ac76bafa442cfa1820d4b96479392b280cf0f`, 1,624 lines. Rule
  source `src/tests/test_runbook_itest_helpers.py` at that commit: sha256
  `b63ef7d88ae22e623bf381ef0dc3e6fbfbf050d966d5b0e09cc961ee169d83be`.
- Unchanged against `8e49261` (verified): helper heredoc `e5eba37e529a47885a8aea0e718d25ac71ce1e31a0c1a381b4520fe4c914b4fb`
  (545 lines, runbook lines 610-1154); `tunnel.sh` `38f5cae9f0a3632e1bf0590f6ac71a9dc46e843f367d8ef9aabe51bedd6fe1d1`;
  `ca.crt` `556e139f1db12be032f6e6877a73526457a96e1872a5f8ea7f7e4a554abcb8ff`; `local_export.py`
  `544c9b3d451f0a6c3391102ac4031fe93bee79a0b0b9bcd6f41c893592d2422b`; `images.lock.env`
  `8a9a05df7c9ca2eeb310e8e7702f16f854fb91771fb089a9a2109d638ae4a648`; `compose.yaml`
  `1a32f6c2bd9e24eee075ef569828aa41ad6a7a7b260d4436e588dc9ca74d5982`; `mosquitto.conf`
  `ea37827cccd94ef3870c62b77ffbe0b34261f7f213f243212f03121219d99615`; `CONTRACTS.md`
  `247e3b02a1ffc8e30da3f9df701db5f851f018505ecb9f907b54562b9cf095c9`; `src/schemas` tree
  `1d5284cf28bbabc5c7ea554d5a5366faec5fcf95`; every other identity the S3 scripts pin (the controller record and archive,
  the launcher, the kernel `4457ef38…`, `qemuboot.conf` `7739c945…`, the QEMU binary `5d389c65…`, the Yocto checkout at
  `489bc9e5b5b0660026ea2630b8d1d124049ba2ce` clean).
- Changed: `drivers_sha256` `2c209b09faf58bb4986cf39b7bb1f13936fae8e94c3b5eb3faf84f722bfe44ed` (38 files; was `4a6a572d…`;
  reproduce with `S/g3/battery/drivers_hash.sh`); collector `src/deployment/scripts/collect-resources.sh`
  `9e678b024bde66bacc65fea936d05ca226a82e73c86d1cc23a9cf9f8fe8d9b97` (was `11444c0a21d6f689965d3c3be7c3eca12be132b8bd3a718e105b43d24c4819a6`);
  the clone's `src/deployment` tree `573e902b67339a3e6bfc784321dc2735cece09fc` (was `e056d389f7dd640c142bf714bb8ceb389ec460c2`;
  the two differ in exactly `README.md` and `scripts/collect-resources.sh`).
- Root file system `.ext4` expected before S4: `6fce1688284b5d5af2d72991176f0fc7a0b4c8d9c7bcd833c2427437cdac6de4` (the value
  S3's second close recorded: `OT/runs/2026-10-05/HIST_2026-10-05-g3-t8t9-s3-operator-records-attempt02/state/session-S3.env`,
  key `rootfs_after_close`; verify it there).
- Plan: `~/egw-tcg/pilot/campaign_plan.json`, today sha256 `c195bd3faa9607aae7c091b1e7e59b451b74afe484fa179cfa2aad7af8f28a60`
  (95 entries). `python -m egw_experiments plan-supplement --plan <plan> --entry g3-t6` (run from the merged `src`) on a
  COPY gave sha256 `61d55940fcccdb942ff508ab6fc920b0fa163837ef7459438d789a1879b1eaac`, 96 entries, the last one
  `{"condition_id": "controller_restart", "cooldown_s": 0, "duration_s": 600, "order": 96, "rate_msg_s": 11.2,
  "repetition": 4, "run_id": "controller_restart-r04", "runner": "simulator", "scenario": "nominal", "seed": 1715385812,
  "status": "planned", "supplement": "g3-t6", "warmup_s": 0}`.
- Session label `S4`. Row: `t6` only (one step file `t6.sh`, the eight `host$` lines 1421-1428 with `host$ ` removed, as
  the battery's `t6.sh` was formed from seven lines; no identifier substitution: `controller_restart-r04` is the
  runbook's own literal). Ceiling 47 min (the packet's, unchanged). State directory default `$EXEC/g3-t6-s4` (the
  `EGW_G3_STATE` override stays); no earlier state directory is written.
- Earlier attempt admitted for row t6: exactly `20261003T132936Z_g3-qualification-t6_attempt01` (S2's invalid one), where
  it is kept (the WSL attempts directory and `OT/runs/2026-10-03/`). The new attempt must be named
  `…_g3-qualification-t6_attempt02` by the export tool, else the row halts before any step.
- Authority text in the row's workload field (key `battery` kept): `G3 qualification, session S4: test 6 only
  (controller_restart-r04; request of 2026-10-05, output_test/decisions/2026-10-05_g3-t6-session-request.md; criterion
  amended on 2026-10-05, LOG #C052; transition rule 1a-option-a-2026-10-05, LOG #C053)`.
- The gate's record of the running images: S3's gate package (`OT/runs/2026-10-05/20261005T115022Z_g2-gate-preconditions_attempt07/environment/container_identities.txt`)
  matched S2's six lines in the three compared fields; keep the S2 constant and its comparison, now before row t6, and
  say in a comment that S3's gate matched it (verify that it did, by reading S3's file).

## Stream ROWS — owns `P/g3_extract_rows.py`, `P/g3_check_rows.sh`, `P/g3_rows_dryrun.sh`, `P/rows/`, `P/rows-notes.md`, `P/rows-record/`

Revise the three scripts for the merged commit, S4 and test 6:
- extraction: `RUNBOOK_COMMIT`, `RUNBOOK_SHA256`, `RUNBOOK_LINES`, `RULE_SOURCE_SHA256`; S4 extracts ONLY test 6 (one
  file `t6.sh`, eight lines from 1421-1428, no substitution: no suffix, the `.diff` file empty or absent as the battery's
  `t6.sh.diff` was); keep the script's own checks of the extraction rule against the test module's functions and of the
  runbook's identity; `session` is `S4`; the manifest keeps its form (runbook identity, rule, substitution rule — none,
  rows, per-file line numbers, sha256, `bash -n`). The manifest's note for t6 says what the block does (r04, the
  transition rule, the exactly-once line) in one or two sentences. Show, in the notes, the diff between the battery's
  `S/g3/battery/prep/rows/t6.sh` (seven lines from `80e833f`) and the new `t6.sh`: exactly the changed RID line, the
  changed harness line and the added `acceptance --exactly-once` line (lines 1, 5, 7 of the new file); quote the diff
  hunks' first 200 characters.
- Run it on `P/runbook.1fd9792.md` (it asserts the sha256) into `P/rows/`; run its `--check` (0 differences).
- checker: commit, hash, line table, file list; keep the clone mode (it reads the blob by `git show` from the clean
  clone and requires the clone's HEAD at the commit) and the `--blob <file>` mode the S3 version added; run it in blob
  mode on `P/runbook.1fd9792.md`.
- dry run: the files it names; under `/tmp/g3-s4-dry-rows.*`.
- Deliver `P/rows-notes.md`: what changed and why (diff sizes against `P/base/`), the consoles of the extraction, of
  `--check`, of the checker (blob mode) and of the dry run saved under `P/rows-record/`, the files with sha256, and the
  proof that `t6.sh` equals runbook lines 1421-1428 with `host$ ` removed, byte for byte.

## Stream OPERATOR — owns `P/g3_battery.sh`, `P/g3_battery.README.md`, `P/operator-procedure.md`, `P/operator-notes.md`

`P/g3_battery.sh` starts as S3b's script (`S/g3/s3bprep/g3_battery.sh`, the one that ran). Required changes:

1. Label: `open S4` only; `S1`, `S2`, `S3` refused with a text saying their authority is consumed. Rows of S4: `t6`
   only (`ROWS_S4="t6"`; `session_rows`, `row_session`, the order check and the usage follow). Preconditions at open: no
   QEMU process, no open session, the root file system at `6fce1688…` (constant renamed for S4, comment naming its
   source as above).
2. Constants: `TOOLS`, `TREE`, `DRIVERS_SHA`, `RUNBOOK_SHA` to the merged values; a new `COLLECTOR_SHA` (`9e678b02…`)
   compared by `verify_candidate` (at open and before the row) against the clone's
   `src/deployment/scripts/collect-resources.sh` (with `want_sha`); the state directory `$EXEC/g3-t6-s4`.
3. Remove S3b's prospective exception (`EXCEPTION_SHA`, `EXCEPTION_PY`, `s3b_preflight_exception.py` and the branch at
   open that applied it): in S4 the frozen preflight at `1fd9792` judges `collector-duration` on the uptime bounds, and a
   preflight that ends non-zero is a halt at open exactly as in S3's first opening (read `S/g3/s3prep/g3_battery.sh` for
   that form). Say in the notes what was removed, with line numbers in `P/base/g3_battery.sh`.
4. `row_harness_id t6` → `controller_restart-r04`. `fresh_plan` as it is (requires `status` `planned` and no raw
   directory, no `$P/$id`, no `$P/$id.*`).
5. `fresh_row`: for `t6`, the one earlier attempt named above is admitted (the WSL attempts directory and
   `OT/runs/2026-10-03/`); any other earlier attempt of t6 is NOT FRESH. The expected attempt suffix for t6 is
   `_g3-qualification-t6_attempt02`, and a different name halts the row before any step (the same mechanism as S3's
   point 9 for t8).
6. The gate images check runs before row t6 (it ran before row t8 in S3).
7. The authority text above in the workload field.
8. Check that the battery's t6 path is intact in the S3b script and works with the merged block: `register_sources`
   (the run directory `$RAWD/controller_restart-r04`, the `$P/$RID.*` siblings, the `.sut` directory), `run_row_steps`
   (snapshot before/after of the plan and `processed/`), the guest-state before/after and `guest_state_delta.py
   --expect-restarted egw-controller-1`, `gate_after`, the keepalive margin (ceiling + 30 min), the cut-off. The block's
   line 1427 (`$REC acceptance … --exactly-once`) and the harness's new flags need nothing from the operator script beyond
   running the step; say so, or fix what does not hold. The harness writes the plan? (Read `run.py`: if it updates the
   plan's `status`, the snapshot before/after shows it; record what you found.)
9. The t8/t9-only code (the wait, the QEMU reading, the markers, test 9's steps) is unreachable in S4: leave it, or
   remove only what is needed for clarity; never change `term`, `close`, the turn lock, the keepalive checks, the
   cut-off, `classify`, or the environment copy beyond what S4 needs.
10. The script never runs `compose up`, `start` or `restart`, nor `docker start`, never re-launches QEMU, never signals
    it. The one stack start of S4 is the frozen preflight's at open; the controller restart at +300 s is the test's own
    fault, issued by the harness's `--restart-cmd` inside the runbook's line, never a restoration.

`P/g3_battery.README.md`: bring it to S4 (subcommands, the S4 flow step by step: open, row t6, classify, close; every
halt with its text and what the operator does next; launch rules; what is unverified). `P/operator-procedure.md`: the S4
operator procedure in one to two pages (sequence; the classification table of the request's section 6 with WHERE each
quantity is read: `manifest.json` `drain.outcome`, `resources_transition_rows`, `resources_proved_down`; the console's
`delta` lines and the `--exactly-once` exit; `per_run.csv` (written by line 1428's `analyze`) `lost`,
`late_confirmations`, `double_accepted`, `restart_functional_recovery_s`, `restart_metrics_endpoint_recovery_s` — check
these column names in `S/t6m/src/egw_experiments/analyze.py`; the operator's comparison of the configuration identity
values with the packet's section 1, as S2 did; the stop conditions of the request's section 5; the controlled close;
what to do when the guest does not answer with QEMU alive: preserve the state, signal nothing, ask Rui).

Deliver `P/operator-notes.md`: each of the 10 points with the line numbers where it is implemented, the `diff --stat`
against `P/base/g3_battery.sh`, anything you could not do and why, and anything in the merged line 1425 or 1427 that
would misbehave in a step shell (`set -v`, stdin closed, process substitution) with evidence.

## Stream HOST — owns `P/g3_hostprep.sh`, `P/seal_prep.sh`, `P/ops/*`, `P/host-notes.md`

- `g3_hostprep.sh` for S4 (start from `P/base/g3_hostprep.sh`; read `P/base/s3b_recheck.sh` for what S3b re-checked):
  refuses when a QEMU process runs or a session is open; fetches from the clone's `origin` (the Windows repository)
  and checks out `1fd9792…` detached — require that the commit exists after the fetch and is an ancestor of, or equal to,
  the fetched `dev` tip (do NOT require the tip to equal it); **if the clone has local changes (a non-empty `git status
  --porcelain`) or its HEAD is neither `8e49261…` nor `1fd9792…`, stop and change nothing**; require tree `14f89c4…`, a
  clean status and unchanged branches afterwards. The read-only "no rebuild" diff against `489bc9e…` stays. Identity
  comparisons against the values above, the new ones included (`drivers_sha256` as the battery's script computed it;
  the collector; the clone's deployment tree `573e902b…` and `git diff --name-only e056d389… 573e902b…` exactly
  `README.md` and `scripts/collect-resources.sh`). Helper regeneration as before (predecessor kept, expected
  `e5eba37e…`, 545 lines).
- The plan entry (new): with the clone at `1fd9792`, if the plan's sha256 is `c195bd3f…`, copy it into the record
  directory as the predecessor, run `cd ~/egw-exec/repo/src && ~/egw-exec/venv/bin/python -m egw_experiments
  plan-supplement --plan ~/egw-tcg/pilot/campaign_plan.json --entry g3-t6` (recorded console), then require sha256
  `61d55940…`, 96 entries, the first 95 entries equal to the predecessor's (a JSON comparison, and the bytes of the
  predecessor's entries — say how), and the r04 entry exactly as above; if the plan is already at `61d55940…` (a re-run
  after the entry was added), record that and change nothing; any other value: stop, change nothing. Never write any
  other file in `~/egw-tcg/pilot/`.
- Freshness of r04: no `~/egw-tcg/pilot/results/raw/controller_restart-r04`, no `~/egw-tcg/itest/controller_restart-r04`
  and no `~/egw-tcg/itest/controller_restart-r04.*`, nothing in `~/egw-tcg/itest-replay` of that name, no
  `…_g3-qualification-t6_attempt02` and no t6 attempt other than S2's attempt01 in the attempts directory, `OT/runs/*/`
  or `OT/incomplete/`; and, offline and read-only (`debugfs -c`, no QEMU running), no
  `/opt/egw/deployment/data/events/controller_restart-r04` on the guest's root file system (the listing of
  `data/events` must show `.` and `..`, as S3's script required, since `debugfs` exits 0 on a missing directory), with
  the root file system hashed before and after (`6fce1688…` both times). The data disk `egw-data.img`: its size
  (34,359,738,368 B) and its ext4 header read-only (as S3's open driver lists it), never hashed.
- The record directory is an argument; it never overwrites its console; the script prints `outcome: prepared` only when
  every check passed.
- `seal_prep.sh` and `ops/seal_ops.sh`, `ops/seal_ops_finish.sh` for S4: package names
  `HIST_<UTC date>-g3-t6-host-preparation` and `HIST_<UTC date>-g3-t6-s4-operator-records`, the S4 file set, the secret
  sweep (it must not match its own pattern line), never overwriting a package (an `-attemptNN` suffix if the name
  exists). `ops/g3_go.sh`, `ops/g3_wait.sh`: the paths of `P/` and S4.
- Deliver `P/host-notes.md`: what changed (with `diff --stat` against `P/base/`), `bash -n` for each script, every
  hard-coded value with where it was taken from, and the exact command lines the operator will run for the host
  preparation and for sealing. Do not run `g3_hostprep.sh`.
