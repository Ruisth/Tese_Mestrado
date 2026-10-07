# Stream OPERATOR — notes (S4 preparation, 2026-10-05)

Offline only: no guest, no QEMU, no docker, no ssh to anything, no build, no git write. Written: the four files of
this stream in `P/`, the bench and its consoles in `P/operator-record/`, and, in WSL, `/tmp/g3-s4-op-src` (the merged
tree extracted read-only with `git archive 1fd9792`), `/tmp/g3-s4-op/<scenario>` and `/tmp/g3-s4-op.run1/` (the
benches). After the benches (`operator-record/static.console.txt`): no bench process left; nothing under
`~/egw-exec`, `~/egw-tcg`, `~/yocto/egw-integrated` or `output_test` (depth 3) newer than the bench source; the
execution clone still at `8e49261`; `~/egw-exec/g3-t6-s4` absent. Read-only reads of the real host: the listings of
`~/egw-exec/attempts/*_g3-qualification-t6_attempt*` and of `~/egw-tcg/pilot/results/raw/controller_restart-r0*`, and
the execution venv's `python` and `shellcheck`.

## 1. Files

| File | What it is | sha256 |
|---|---|---|
| `g3_battery.sh` (2,356 lines) | the steps script finished for S4 | `7a63b361af2f25bd8ab81101ca10ec79fcb05a6e6f0cf0a70bc2ec63f3f8425c` |
| `g3_battery.README.md` (216 lines) | rewritten for S4 | `2dd119bf4c1ec5f1ed1e147b638688c82ff54efccaa6598034e2fd5695e67fdd` |
| `operator-procedure.md` (112 lines) | the S4 operator procedure | `67f41d772d2905010f008dc55a1acd3a3a1fe11d1359def6d8765ef9863356db` |
| `operator-notes.md` | this file | — |
| `operator-record/bs4_op.sh` | NOT listed by the brief: the isolated bench (eight scenarios), as S3's `operator-record/` | `104783449e3979658068d3e354032c8c5484b5d176629927ae7489085480531f` |
| `operator-record/<scenario>.console.txt` (8) and `static.console.txt` | the bench's consoles on the final bytes (paths masked as `<bench>` and `<S>`) and the static checks | listed in the stream's return |

Base: `base/g3_battery.sh` `42de225aedfd25fa0f4975276bf2880e146c2ad66a4624f811487ba61ea0f034` (2,316 lines), byte-identical
to `S/g3/s3bprep/g3_battery.sh`, the script S3's second opening ran.
`git diff --no-index --stat base/g3_battery.sh g3_battery.sh`: **230 lines, 135 insertions, 95 deletions**.
README: 150 insertions, 213 deletions; procedure: 95 insertions, 103 deletions. LF only, UTF-8, no BOM, no carriage
return (byte count 0); `bash -n` clean (WSL bash 5.2.21); the execution venv's `shellcheck` 0.11.0, read-only: `-S
error` exit 0, `-S warning` exit 0, and the same info-level findings as the base (6 SC2012, 4 SC2015, 7 SC2016, 5
SC2329). No file names a tool or a vendor.

Function by function against the base: byte-identical are `take_turn`, `keepalive_check`, `cmd_term`, `close_rows`,
`environment_copy`, `on_signal`, `wait_group`, `run_step`, `snapshot`, `register_sources`, `register_late`,
`fresh_plan`, `plan_entry`, `fresh_itest`, `gate_images_check`, `check_guest_state`, `run_driver`, `open_halt`,
`halt`, `start_log`, `finish_log`, `row_alive`, `row_group`, `data_disk_header`, `rootfs_after_close`, every T8 and
T9 function, and the texts `SNAPSHOT`, `GUEST_STATE`, `STEP_PRE`, `T8_QEMU_IDENT`, `T8_POLL_SH`. Changed: `cmd_open`
(49 diff lines, most of them the removed exception), `cmd_row` (17), `run_row_steps` (5, a comment), `fresh_row`
(4), `gate_after` (4: a comment and the note's label), `cmd_close` (6: texts), `cmd_classify` (3: a text),
`cmd_status` (3) and `close_outside` (2: the label), `verify_candidate` (2), `MANIFEST_PY` (the authority text).

## 2. The ten points, where each is implemented (line numbers of the final file)

1. **Label, rows, preconditions.** `ROWS_S4="t6"`, `session_rows`, `row_session`: 148–160. `open`: the label case
   956–966 (`S1`/`S2` refused at 963 and `S3` at 964, each "authority is consumed"; anything else the usage); the
   preconditions: no open session 977, `session-S4.env` absent 978, the one-label loop 979–985, no QEMU process
   986–991 (refusals), and the root file system as a HALT of the checks 1007–1013 against `ROOTFS_BEFORE_S4`
   (106–109; source named in the comment: `rootfs_after_close` of `session-S3.env` in
   `OT/runs/2026-10-05/HIST_2026-10-05-g3-t8t9-s3-operator-records-attempt02/state/`, read there: line 26,
   `6fce1688…`). `row`: the unknown-row refusal 1710–1712; the order check 1725–1738 is the base's and, with one row,
   finds no previous row. The loops over the label: 635–637 (`open_label`), 980, 2162 (`close_outside`), 2297
   (`cmd_status`). Usage: 2346–2348. Texts that named S3 or its records: 1747–1749, 1631–1634, 1982–1984, 2116,
   2271–2273.
2. **Constants.** `TOOLS`, `TREE`, `DRIVERS_SHA`, `RUNBOOK_SHA`: 86–96; `COLLECTOR_SHA`: 101–105; the comparison in
   `verify_candidate`: 684–685 (after the runbook, `want_sha collector … "$REPO/src/deployment/scripts/collect-resources.sh"`),
   run at `open` (995) and before the row (1758). State directory `$EXEC/g3-t6-s4` (the `EGW_G3_STATE` override
   kept): 129–132. Every value was reproduced from git blobs, read-only: `drivers_hash.sh <t6m> 1fd9792 C` →
   38 files, `2c209b09…` (and `4a6a572d…` at `8e49261`); the runbook blob `31716593…`, the collector blob `9e678b02…`,
   `local_export.py` `544c9b3d…`; the deployment trees `573e902b…`/`e056d389…` differ in `README.md` and
   `scripts/collect-resources.sh` only.
3. **The exception removed.** Removed from `base/g3_battery.sh`: lines 3–5 (the header's "second opening" note), 92–94
   (`EXCEPTION_SHA` and its comment), 115 (`EXCEPTION_PY=$SELF_DIR/s3b_preflight_exception.py`), 1010–1030 (the
   comment 1010–1017, `excepted=no` 1018, the branch 1019–1029 that hashed and ran the checker and recorded
   `preflight_exception`, and the combined test 1030), and the exception's mention in the workload text (412). In
   their place: the comment 110–111 and, at 1052–1056, `[ "$rc" -eq 0 ] || open_halt "preflight.sh exited $rc; see
   $DRIVER_CONSOLE"`, the form of S3's first opening (`S/g3/s3prep/g3_battery.sh` line 1002). `s3b_preflight_exception.py`
   is not in `P/` and nothing refers to it. Bench `preflight3`: a preflight ending 3 halts `open`, no exception is
   examined, no environment copy and no gate are run, `session-S4.env` says `halted` and `preflight_exit=3`, `row t6`
   is refused.
4. **r04.** `row_harness_id t6` → `controller_restart-r04`: 218–219. `fresh_plan` (798–806) and `plan_entry`
   (767–782) unchanged: `status` `planned`, no `$RAWD/$id`, no `$P/$id`, no `$P/$id.*`. The guest listing at `open`
   checks the same id (1081).
5. **Freshness and the attempt's name.** `T6_ADMITTED` and `row_attempt_suffix` (t6 → `_g3-qualification-t6_attempt02`):
   212–216; `fresh_row`, the t6 clause: 813–815 (comment), 825–828; the name check before any step: 1829–1841 (the
   base's mechanism of S3's point 9, comment 1833–1834). Read on the host today: S2's attempt01 is the only t6 attempt
   in `~/egw-exec/attempts/` and the only one anywhere under `output_test` (`find -name '*_g3-qualification-t6_attempt*'`).
   Benches `fresh` (another t6 attempt, the admitted one in another date folder, r04 `running`, `$P/<r04>.sut`, the
   raw directory: five halts; all restored, `open` passes) and `suffix` (the admitted attempt absent from both places:
   `open` passes, `row t6` halts on `…_attempt01` before any step; the plan untouched; no restart reached the guest).
6. **The gate's image record before row t6.** The comment with S3's verification: 723–727; the constant
   `GATE_IDENTITIES_S2` and `gate_images_check` (739–756) unchanged; the call before t6: 1794–1804; the gate attempt
   recorded at `open`: 1063–1070. **Verified by reading S3's file:**
   `OT/runs/2026-10-05/20261005T115022Z_g2-gate-preconditions_attempt07/environment/container_identities.txt`
   (sha256 `a713c8ba…`, LF, six `identity` lines): cut before ` container_id=` and sorted, it equals S2's six lines
   (`…_attempt06`, `60f7e99b…`) and the script's constant. Bench `pass` used S3's sealed file as the gate record (the
   check passed); bench `gate` changed one image id (halt before the attempt, no row state file).
7. **Authority text.** `MANIFEST_PY`, mode `workload`: 433–435 (key `battery` kept). Bench `pass` read it back from
   `attempt.json`, equal to the brief's text, with `harness_run_id` `controller_restart-r04` and `itest_run_ids` `[]`.
8. **The t6 path with the merged block — nothing to fix.** Only a comment was added (1564–1568).
   - `register_sources` (1126–1149, t6 at 1137–1140): the raw directory `$RAWD/controller_restart-r04`, and
     `$P/controller_restart-r04.config_identity.json` with the siblings glob `controller_restart-r04.*`, which takes
     the twin hook's `.twins.before.json`/`.twins.after.json` and the `.sut/` directory. The eight merged lines write
     no other host artefact (the harness writes `RAW6`; line 1428 `processed/`; line 1427 writes nothing).
   - `run_row_steps` t6 (1563–1572): `snapshot before both`, the one step `t6`, `snapshot after both`.
     **The harness writes the plan:** `run.py` `update_plan_status` (4065–4081) sets `running` when the run directory
     is created (4757) and `completed`/`failed` with `result_dir`, `finished_utc` and `validity` at the end
     (5959–5966). S2's sealed snapshots show exactly that (`planned` → `failed`, `validity: invalid`, `result_dir`,
     `finished_utc`). So the plan's sha256 is not `61d55940…` after S4.
   - The gate: `guest-state-before` (1874–1882), `gate_after` (1589–1637) with `row_restarted t6` → `egw-controller-1`
     (222–227) passed as `--expect-restarted` (1602–1604): bench `pass` shows `EXPECTED-RESTART` and
     `faults=0 problems=0`.
   - Keepalive margin: `row_ceiling_min t6` = 47 (184), `need` = 47 × 60 + 1,800 = 4,620 s (1751–1753; bench:
     "needed: 4620 s"). Cut-off: 1770–1778, unchanged.
   - Line 1427 (`$REC acceptance … --exactly-once`) and the harness's `--restart-transition-rule` need nothing from
     the script beyond running the step. Both exist only at `1fd9792` (`--exactly-once`: 0 occurrences in
     `itest_reconcile.py` at `8e49261`, 6 at `1fd9792`; `--restart-transition-rule` in `cli.py`: 0 and 2), so at
     `8e49261` the step would end in an argparse usage error: `verify_candidate` refuses any clone not at
     `1fd9792`/`14f89c4`, at `open` and again before the row.
9. **T8/T9 code.** Left as it was and unreachable (`row_session` admits only `t6`): `T8_QEMU_IDENT` 313,
   `t8_wait_ssh` 1284, `t8_qemu` 1358, `steps_t8` 1387, `t8_evidence` 1521, `steps_t9` 1529, `register_late` 1155
   (returns at once for t6), the t8 cases of `gate_after` (1598) and `cmd_row` (1890). `term`, `close`, the turn, the
   keepalive checks, the cut-off, `classify` and the environment copy are byte-identical but for the label texts of
   point 1 (section 1 above).
10. **No start, restart or signal.** The header 49–52. The script holds no `compose up`, `start`, `restart` or `docker
    start` command (the only matches are words inside two halt texts, 1457 and 1609). Bench `pass`: the stub ssh log
    holds exactly one `docker compose … restart controller`, issued by the row's step before the after-state read,
    and no `up`, `start` or `docker start`.

## 3. The bench (`operator-record/bs4_op.sh`; consoles beside it)

Eight scenarios, each in its own `/tmp/g3-s4-op/<scenario>`, HOME and every `EGW_*` inside it, stubs first on PATH
(`git`, `sha256sum`, `pgrep`, `ps`, `ssh`), the execution venv's python read-only, a fake QEMU process, four stub
session drivers in a copy of the merged tree (its 38 drivers hashed to `2c209b09…` before the stubs replaced four),
the helper file and `tunnel.sh` written from the runbook blob's heredocs (`e5eba37e…`, `38f5cae9…`), S3's sealed gate
record, and a **stand-in `t6.sh`** that writes what the block leaves on the host and issues the restart through ssh.
On the final bytes (`7a63b361…`): labels 19 checks, pass 41, preflight3 12, collector 4, rootfs 4, fresh 14, suffix 9,
gate 6 — **109 checks, 0 failed**. The runbook's block itself was not run (it needs the guest, the broker and the
harness).

## 4. Lines 1425 and 1427 in a step shell (`set -v`, stdin closed, process substitution)

Nothing found that misbehaves. Evidence:

- **Process substitution:** none in lines 1421–1428 (`grep '<(\|>('`: 0); none in the helper file (lines 610–1154),
  whose stdin uses are a file redirect (`read … < /proc/uptime`) and a here-string (`read … <<< "$cur"`), neither of
  which reads the shell's stdin.
- **Stdin closed:** `local_export exec` starts every step with `stdin=subprocess.DEVNULL` (`local_export.py`
  1218–1219). Lines 1421–1428 read no stdin (no `read`, no `-` operand, no heredoc; the one `read -` match is inside an
  echo text). `harness_cmd` gives the harness and its hooks their arguments, not stdin; `acceptance` reads two files.
  S2's step `t6` ran the same construct (line 1425 without the new flag) under the same `hx` and completed: harness
  run, hooks, fetches and the StartedAt read all ended 0 (S2's classification note).
- **`set -v`:** it echoes the row file's text as read, not expanded. Lines 1421–1428 hold no `--password` and no
  `MOSQUITTO_SIMULATOR_PASSWORD` (`grep`: 0); the password appears only in `harness_cmd`'s body, in the helper file,
  sourced by the preamble before `set -v`. S2's package: "0 excluded for secrets". The bench's step console begins
  with the carriers line and then the echoed `RID=controller_restart-r04; …`.
- **The carriers the step shell unsets:** line 1425 passes `DRAIN_QUIET_S=$DRAIN_QUIET_S …` with the three unset, so
  empty strings reach the hook. `drained` (`local quiet=${DRAIN_QUIET_S:-130} …`, runbook line 689) and
  `proof_hook_drained.sh` (`${DRAIN_QUIET_S:-130}`, its line 68) read an empty value as the default. S2's sealed hook
  transcript (`raw/controller_restart-r03/logs/sut/hook-drain.stdout.txt`): "drained with DRAIN_QUIET_S=130
  DRAIN_STEP_S=5 DRAIN_LIMIT_S=900", `drain.outcome` `quiet`. `EVENTS_EXPECTED=die,start` is an assignment in front of
  a function call: in bash it is in the function's environment for that call (S2's capture held one `die` and one
  `start`).
- **Exit statuses:** lines 1426 and 1427 do not print their exit code; it is read from the line before the `STOP`
  (`-> FAIL` for 4, `error:` for 1, a usage text for 2): written into `operator-procedure.md`. The step's own status
  is line 1428's `analyze`; the script reads only 97 and 74 from it.

## 5. Not done, open issues, deviations

- **Not done:** the runbook's block was not run, and `term t6` during the harness was not exercised (TERM to the
  whole group; `harness_cmd`'s trap and cleanup): both are as the battery designed them and need the guest.
- **The interface with the ROWS stream:** the script needs `rows/rows.manifest.json` with `rows[]` holding
  `{"row": "t6", "session": "S4", "steps": ["t6.sh"]}` and `files["t6.sh"]` with `row` `t6`, `session` `S4`,
  `step_order` 1 and `sha256_after` (`MANIFEST_PY` verify mode, lines 373–416); any other session label or step name
  is a HALT at `open`. `P/rows/` appeared late in this stream's work; checked read-only at 2026-10-05T18:55Z with the
  script's own `MANIFEST_PY`: `verify … S4 t6 t6.sh` exit 0 (`t6.sh` `ec8ac010…`, 12,167 bytes, manifest `7d2a0f0d…`),
  and `workload` builds with `step_source_lines` `1421-1428`; `t6.sh.diff` is present and empty (copied into the
  attempt as the battery's was). The benches used their own stand-in row file, not these.
- **For the HOST stream:** `ops/g3_go.sh` and `ops/g3_wait.sh` must use the state directory `~/egw-exec/g3-t6-s4` and
  `row t6`; the plan's sha256 changes during S4 (the harness's status rewrite), so nothing after S4 may expect
  `61d55940…`.
- **Recovery within 120 s:** the request does not say which `per_run.csv` column decides it. The packet's T6 row of
  2026-10-01 names the endpoint recovery (`restart_metrics_endpoint_recovery_s`); `analyze.py` calls the functional
  one (`restart_functional_recovery_s`) "the readiness gate". The procedure reads both and leaves a split verdict to
  Rui.
- **Numbering:** `local_export` numbers an attempt over `output_test/runs` and `incomplete` at any depth (`rglob`),
  `fresh_row` looks one level deep; a deeper copy named `…_g3-qualification-t6_attemptNN` would make the attempt's
  number differ, and the name check halts the row before any step (as designed). None exists today.
- **Deviations from the brief:** (a) the bench and its consoles are written in `P/operator-record/`, which the brief
  does not list for this stream (S3's operator stream did the same); (b) the result note's name
  `<date>_g3-t6-results.md` in the close's last message and the README is this stream's choice (the request names
  none); (c) texts that named S3 (refusals, halts, the close's last message) now name S4, each under an `S4 (point 1)`
  comment, beyond the strict list of point 1.
