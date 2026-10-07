# fix-notes — corrections after the three verifications (2026-10-02)

Fixer's record. Inputs: `verify-rows.md`, `verify-iface.md`, `verify-safety.md`. Every finding was reproduced in an
isolated bench or confirmed against the source before anything was changed. Scripts and records of this work:
`prep/fix/` (`fx_*.sh`, `fx_*.py`, the three files as verified, their diffs, `record/`).

**Result.** The two material findings, every minor one (safety m1–m5, rows M1–M2, iface F1) and seven nits are
corrected; two nits are declined (reasons below). No guard was weakened. The 20 step files and the 18 diffs are
byte-identical to the verified ones; only the manifest changed (three lines). `bash -n` and `shellcheck` are clean.

| File | sha256 as verified | sha256 now |
|---|---|---|
| `g3_battery.sh` (1,618 → 1,854 lines) | `51a1ab5e260e…` | `fd652ec928ce9e9570f03fa526b83473a6706a17d81b5ade9c2dbc6b42e44ac1` |
| `g3_battery.README.md` (105 → 182 lines) | `fcb28f0f4586…` | `a4acb56c9bb48b559dfc80ddf27bf24643c4c672b11edc7aac2aae8a839a2cf4` |
| `g3_extract_rows.py` | `84914da4d240…` | `6940366cca642d8f824092278e82e500112d8a3f9df36ed6d32cbc6595ead304` |
| `rows/rows.manifest.json` | `11f5a54ddfcc…` | `cfca6a9397715d0c95881a2c824cad83a95e73727a500351920faf5552ad230c` |
| the 20 step files, the 18 diffs | — | unchanged (`fix/rows.before.sha256`: 38 of 38 `OK`) |

The earlier verifications describe the script at `51a1ab5e…`. What changed is listed here and in `fix/g3_battery.diff`
(278 lines added, 42 removed or moved), `fix/g3_battery.README.diff`, `fix/g3_extract_rows.diff`.

## 1. Findings, how each was confirmed, what was done

| Finding | Confirmed | Action |
|---|---|---|
| **safety M1 / iface F1** (material): `term` prints the simulator password and keeps it in the operator records | Reproduced, `record/repro-before-1`, test a: the value on 1 line of `term`'s output and in `console/003-term-t1-smokes.txt` | **Fixed** (1.1) |
| **safety M2** (material): two `row <slug>` started together both run the row | Reproduced, tests b0 and b1: at 0 s the row file was sourced twice and two official attempts exist; at 0.15 s a false `halt=` line is written | **Fixed** (1.2) |
| safety m1: with the guest gone `close` loops on exit 97; after a hand close S2 can never open | Reproduced, `record/repro-before-2`, test d | **Fixed** (1.3) |
| safety m2: `close` powers off over a row attempt still open | Reproduced, test c: session `closed`, the attempt `running`, 0 packages | **Fixed** (1.4) |
| safety m3: `close` is not refused while `open` runs | Reproduced, test f: the stack stopped under the preflight | **Fixed** by 1.2 |
| safety m4: README restorations (`$DC`, bare cleanup, collector stop missing) | Read: `guest_common.sh` lines 12 and 67; helper `events_cleanup` (runbook 958–972) and `harness_cmd` (1049, 1055); `events_capture.sh` header | **Fixed** in the README (1.5); the four lines run through the frozen `hx` in bench r |
| safety m5: `close` does not check the keepalive | Read: `keepalive_check` was called by `open` and `row` only | **Fixed**: checked before anything is stopped (30 min); a refusal |
| safety n1: README says "refuses" where `term` halts; the halt is not recorded | Read | **Fixed**: the halt is recorded in the session's and the row's state files; README corrected, also for the HALTs of `open`'s checks |
| safety n2: the label check tests two of three labels | Read | **Declined** (2) |
| safety n3: `on_signal` says "exported" whatever the export did | Read | **Fixed**: the line names the driver code and the receipt, and says `export FAILED` on code 4 |
| safety n4: data disk header not listed after the close | Read: `guest_session_close.sh` line 116 lists `ls -l` only; `guest_session_open.sh` line 115 has the `dumpe2fs` form | **Fixed** (1.6) |
| iface F2: `classify` ends with "Next: the next row…" after a failed gate | Read; bench h | **Fixed**: `Next: 'close', then hand back to Rui` when the row's gate did not pass or the session holds a halt |
| iface F3: the brief's `git archive` line cannot run in WSL | Read: `$S/cand/.git` is `gitdir: C:/Users/…/worktrees/cand` | **Declined** (2) |
| rows M1: `forbidden_out()` follows `$HOME` | Reproduced as a pure function, `record/forbidden-out.console.txt`: with `HOME` redirected the four real trees answer `None` | **Fixed**: the four names are refused by path component as well |
| rows M2: `t8-b-return.sh` line 2 closes a live master under `hx` | Read: `tunnel.sh` lines 31–37, the row file's line 2, `HOST_PRE`. Not reproduced on a real ssh master (as the verifier) | **README note** ("a tunnel signature to know"); no row change, as asked |
| rows N1: the manifest does not say `t9-exposure.sh` is gated too | Read: `steps_t9` | **Fixed**: the row note of `ROWS` in the extraction script; the README says it as well. The gating itself is kept |
| rows N2: manifest note 4 ("the same preamble from the clean clone") | Read: runbook line 1260; `guest_common.sh` line 67 | **Fixed**: reworded (a superset; the helper file is the deployed one) |
| rows N3: `only_defines()` proves less than its docstring says | Read | **Fixed**: docstring reworded; code unchanged |

### 1.1 The password (M1 / F1)

`mask_argv` (`sed -E 's/(--password)([= ]+)[^ ]+/\1\2<hidden>/g'`) is applied to every listing of a row's
processes that is printed or written, and each is cut at 90 columns: `term` (was 200, unmasked), `status`, `close`,
and the file `row-<slug>.group-after-signal.txt` (was the whole `pgrep -a` reading). In `wait_group` the reading is
now `pgrep -g <group>` alone (pids only), and the command lines are read afterwards with `ps -p`: a filter in the
same pipeline would itself be a member of the group being waited for.

After (`record/repro-final-1`, test a; the bench `.env` holds only the placeholder `bench-value-0000`):

```
62320 python -m egw_simulator run --broker 127.0.0.1 --port 8883 --username egw-simulator 
term output holds the value: 0 line(s)
--- files of the state directory (the operator records) that hold the value:
(end of list)
```

Limit: the mask is by the option name. Every host-side argv of the helpers and the row files at `80e833f` carries
the password after `--password` (simulator, replay, harness, T9's probes; grep of the runbook); the guest-side `-P`
of the Mosquitto clients never stands on a host argv. Another form would be caught only by the 90-column cut.

### 1.2 One changing subcommand at a time (M2, m3)

`take_turn`: `open`, `row`, `classify` and `close` each take the turn before their first check. The turn is a
record (`<state>/turn.env`: pid, its start instant, the WSL boot id, what, when), read and rewritten under a `flock`
on `<state>/turn.lock` that is released at once; its holder is the process the record names while that process
lives. A second changing invocation is refused (exit 2, nothing started or changed). `status` and `term` take no
turn. Why not hold the `flock` for the whole invocation: the descriptor would be inherited by QEMU (started by
`open` and by T8's re-launch with `setsid nohup`) and the lock would never be released. Nothing is deleted: a turn
whose holder ended is taken over. `flock` missing is a refusal. The verifier's second proposal (a claim file for the
row) was not added: with the turn it is not needed, and a claim that stays would block the legitimate re-run after
a refusal ("fix the cause and run the same line again").

`start_log` now creates its console file with `noclobber`, so two invocations started at the same moment never
write one console (seen in this reproduction at 0 s: both wrote `002-row-t1-smokes.txt`).

After (tests b0, b1, f, and the whole dry run):

```
times the row's step ran (one line per shell that sourced the row file): 1
attempts of the row: 1
REFUSED: another invocation of this script is still running: 'row t1-smokes' (pid 63311, since …). One changing subcommand at a time: nothing was started or changed. …
halt lines in the session file: 0
--- f: close while open runs
REFUSED: another invocation of this script is still running: 'open S1' (pid 68368, …)        close exit=2
## … session S1 is open: …                                                                   (the open went on to its end)
```

`status` prints one line for the turn (`last taken by '…' …; that invocation: ended | STILL RUNNING`).

### 1.3 `close` with the guest gone (m1)

- **No QEMU process** (`qemu_procs` answers 1): there is nothing to read or stop. `close` records a HALT
  (`stack_stop_130_exit=not run: no qemu-system-aarch64 process`), does not run the unit check or the stop, and
  runs the frozen `guest_session_close.sh`, which finishes and exports the session attempt as it stands. The
  session is then `closed` with that halt, the post-close rootfs hash is recorded, and S2 opens only on Rui's go.
  Read in the frozen `guest/session_close.sh` (lines 30–49): with the guest unreachable it logs that, waits up to
  180 s for the boot's status file, checks the G1 artefacts, and signals nothing.
- **QEMU runs but the guest does not answer (97):** the HALT now says so, says that `close` again answers the same,
  and hands back to Rui. Exit 3 (a unit active) keeps "cleanup, then `close` again"; any other exit has its own text.
- **A session closed outside the script** (the driver run by hand, or an `open` that left no session):
  `close` answers `REFUSED: no open session … recorded 'open'`. With `EGW_G3_RUI_GO` set, and only if no
  `current_session` exists, no QEMU process runs (a running one, or an undetermined answer, is a refusal) and no
  row is running or unfinished, it records the session `closed`, with a halt and Rui's words. The rootfs hash is
  read from the session attempt's own record; without it S2 still does not open.

After (tests d and o): the first `close` ends the session (`state=closed`, 1 session package, halt recorded,
exit 1); `open S2` is refused without Rui's go and opens with it. In test o: refused without the go; refused with
the go while a QEMU process is shown; recorded with the go otherwise.

### 1.4 `close` over a row attempt still open (m2)

A row recorded `preparing`, `running` or `gate` whose process is gone: `close` now **refuses** (exit 2, nothing
stopped) while the attempt's own `attempt.json` says `running` or its export receipt is not `complete`, and prints
the frozen line that marks and exports it (`local_export recover … --interrupt <run id>`, with the host's paths).
Once that was done, `close` reads the attempt as finished and exported, records the row `interrupted` with a
halt, and goes on. Test c: refused; after the recover line (bench paths) `attempt: interrupted`, 1 package;
`close` again closes the session with exit 1 and the halt.

### 1.5 README

Rewritten or added: the turn; the keepalive at `close`; the `term` and `close` rows of the table; the T8 tunnel
signature; `turn.env` and the masked listings under "State files"; what a HALT records; three subsections ("A row
whose process died without its trap", "A session closed outside the script", "Restorations"). The restorations
are written out as four `hx` lines in single quotes, with the loader lines and which attempt to use:
`events_cleanup <id> "$P/<id>.sut"` (itest ids) or `… ~/egw-tcg/pilot/results/raw/<id>/logs/sut` (plan entries),
the compose `start` spelt out, the harness's collector stop, `tunnel_down && tunnel_up`. Bench r, through the
frozen `hx` (the bench copy's `events_capture.sh` replaced by a stub that prints its arguments):

```
BENCH events_capture.sh stub: cleanup itest-mongo-fault-01-q1 home/egw-tcg/itest/itest-mongo-fault-01-q1.sut/events-partial
BENCH events_capture.sh stub: cleanup nominal-r02 home/egw-tcg/itest/nominal-r02.sut/events-partial
bench docker compose stub: compose --env-file .env --env-file images.lock.env start mongodb
bench systemctl stub: stop egw-resources-nominal-r02
TUNNEL CLOSED / TUNNEL UP
```

### 1.6 Data disk header after the close (n4)

`data_disk_header`, after the close driver: `ls -l` and `/usr/sbin/dumpe2fs -h … | grep -E "state|features|mount
count|Last mount"`, the frozen open driver's own form. Read-only, only when `qemu_procs` answers 1, printed to the
invocation's console (an operator record; the session attempt is already exported). `record/datadisk-final`: on an
8 MiB ext4 image made inside the bench the fields are printed and the image's sha256 is unchanged; with a QEMU
process shown it prints `NOT listed`. This is the script's only reference to the data disk.

## 2. Declined

- **safety n2** (test the shared-host label too). The operator procedure ("Environment input") and packet §1 name
  the `ARM64 EMULATED` and QEMU/TCG labels as the halt condition, and the script matches them; `shared_vcpu_note`
  is printed. A third test would be a new halt criterion (brief, rule 5: no change of criteria).
- **iface F3** (the brief's `git archive` line). `prep_brief.md` is not one of the three files this task corrects.
  The line that works is `git -C ~/egw-exec/repo archive HEAD | tar -x -C <temp>/repo` (read-only on the clone; it
  is what `bench_setup.sh` uses).
- **Not changed although mentioned:** the row files (rows M2 asks for none); the gating of `t9-exposure.sh`
  (rows N1 is about the wording); a value-based mask reading `.env` (the steps script reads no secret).

## 3. Checks re-run on the final files

- `bash -n g3_battery.sh`: clean in WSL bash 5.2.21 and in Git Bash. No CR in the three files or in `rows/`.
- `shellcheck` 0.11.0 (the execution venv's, run read-only): `-S error` exit 0; `-S warning` exit 0 as well.
- **Rows.** `g3_extract_rows.py --check` before regenerating: only `rows.manifest.json` differs. Regenerated
  with `--replace` (inputs: `git show 80e833f:<path>` from the clean clone, read only; `c55a2d3b…`, `da8d31dd…`);
  a second run and a run into a fresh directory wrote byte-identical files; `--check` 39 files, 0 differ
  (`record/rows-extract-after`). Manifest diff: `generator_sha256`, the t9 row note, note 4.
  `g3_check_rows.sh`: 118 `ok`, 0 `FAIL` (`record/rows-check-after`). `g3_rows_dryrun.sh`: as its earlier record,
  the six altered copies detected. `fx_rows_final.py`: no CR, no old literal without `-q1`, the four unchanged
  names untouched, every `sha256_after` and `diff_sha256` equal to the file's (`record/rows-final-check`).
  The steps script's own check through `open` on the real rows, S1 and S2: 20 `row file … = sha256_after of the
  manifest` lines, 0 row attempts created (`record/repro-final-1`, test m).
- **Whole dry run** (`dry/bench_all.sh`, six fresh benches, final script): `record/dryrun-final.console.txt`.
  Against the preparation's own record, normalised (`record/dryrun.before-final.diff`), the differences are the
  intended ones: the turn's refusal instead of "row … is running" for a `close` during a row, the new `Next:` line
  of `classify`, the keepalive lines at `close`, the split unit HALT, bench 4 (failed re-launch) now closing
  through the frozen driver, the `status` turn line, and cut widths.
- Final reproductions: `record/repro-final-1` (m, a, b0, b1), `record/repro-final-2` (c, d, f, o, k, h, r).

## 4. What is shown, and what is not

- Every correction was exercised only in benches (stub drivers, stub ssh, FAKE rows). In particular the
  guest-gone `close` ran the bench's stub close driver, which answers 0; the frozen driver's behaviour with a dead
  guest was read, not run (expected exit 5).
- rows M2's tunnel race is still reasoned, not reproduced on a real ssh master.
- A `flock` on `~/egw-exec/g3-battery` (ext4) was not exercised on the real state directory (it does not exist
  yet); the benches used `/tmp`, the same file system type.
- A hung `open` or `close` holds the turn until it ends; the script offers no way to end one (`term` is for rows).

## 5. What this work touched

- Written: `prep/g3_battery.sh`, `prep/g3_battery.README.md`, `prep/g3_extract_rows.py`, `prep/rows/rows.manifest.json`
  (the 38 other files of `rows/` rewritten with identical bytes), `prep/fix/**`, this file; in WSL only
  `/tmp/g3-dry-fix/**`, `/tmp/g3-dry-fixr1..6`, `/tmp/g3-dry-fixs1..6` (benches; lost when WSL stops).
- Read only: the clean clone (`git rev-parse`, `git archive HEAD`, `git show`, and the `git status --porcelain`
  of `g3_check_rows.sh`; `.git/index` still 12:49:58, HEAD `80e833f`, 0 porcelain lines); `~/egw-tcg/itest-helpers.sh`,
  `tunnel.sh`, `ca.crt` (copied into the benches by `bench_setup.sh`); the execution venv's `python` and
  `shellcheck` (`PYTHONDONTWRITEBYTECODE=1`).
- No QEMU, no `ssh`/`scp` to the guest, no session driver run for real, no pytest. Afterwards: `pgrep` for
  `qemu-system-aarch64` answers 1; `~/egw-tcg/itest` holds 0 `-q1` entries; `~/egw-exec/attempts` holds 0
  `g3-qualification` attempts; `~/egw-exec/g3-battery` and `current_session` do not exist; nothing under
  `~/egw-exec`, `~/egw-tcg`, `~/egw-images` (whole trees) or `~/yocto` (to depth 3) is newer than the start of this
  work; `output_test/runs` has no 2026-10-02 folder.
- WSL had stopped before this work (uptime 4 s at the first command: no keepalive was attached). A keepalive
  `exec sleep 43200` client was started for the bench runs and ended with them.
