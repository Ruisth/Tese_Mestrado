# G3 battery — independent verification of the row files and of `g3_extract_rows.py`

Verifier run of 2026-10-02 (WSL Ubuntu-24.04, bash 5.2.21; Git Bash for a second `bash -n`).
Nothing was edited in `g3_battery.sh`, `rows/` or `g3_extract_rows.py`. No QEMU, no `ssh`/`scp` to the guest, no
session driver. The frozen clone was read with `git show` only and is still clean at `80e833f` (0 porcelain lines,
checked after every run); `~/egw-tcg` holds no `-q1` id and no `nominal-r02` / `controller_restart-r03` directory.

**Result: no material finding.** The eighteen runbook step files are, with every `-q1` removed, byte-identical to
the output of the real `_host_commands`; the ids are the packet's and nothing else changed; every step file is
complete for a fresh shell; the two prose-only files do what lines 1320 and 1529 say. Two minor findings and
three nits are listed at the end; none is in the text of a row file.

## What was verified (hashes at the time of the verification)

`verify-rows/verified-hashes.txt` holds the sha256 of the 20 step files, the manifest
(`11f5a54ddfcc…`), `g3_extract_rows.py` (`84914da4d240…`, equal to the manifest's `generator_sha256`) and
`g3_battery.sh` as read (`51a1ab5e260e…`; statements about the steps script refer to that text).

## Isolation (rule 3)

`verify-rows/setup.sh` builds `/tmp/g3-dry-rows`: a copy of the repository (`git archive 80e833f` from the Windows
repository's object store — WSL git cannot read the `$S/cand` worktree, its `.git` names a `C:/` path — tree
`dad725d0…` asserted), and the two frozen blobs read with
`git -C ~/egw-exec/repo show 80e833f:docs/setup/qemu_integrated_gateway.md` and
`…:src/tests/test_runbook_itest_helpers.py`. Both blobs are byte-identical (`cmp`) to the copy's files; the runbook is
`c55a2d3b…`, 1614 lines; the rule source is `da8d31dd…`. Python is the real venv's, read-only
(`PYTHONDONTWRITEBYTECODE=1`, `-B`, `HOME=/tmp/g3-dry-rows/home`, `PYTHONPATH=/tmp/g3-dry-rows/repo/src`). No pytest.

## 1. Byte identity with the real `_host_commands` (`verify_rows.py` → `verify_rows.console.txt`)

The real module is imported from the copy (`/tmp/g3-dry-rows/repo/src/tests/test_runbook_itest_helpers.py`; its
`RUNBOOK` is asserted byte-identical to the frozen blob). The mapping of commands to files is restated BY COMMAND
INDEX, independently of the extraction script's line table:

| File | Real `_host_commands` output it must equal after `-q1` is removed | Result |
|---|---|---|
| `t1-smokes.sh` | Test 1, command 1 | identical (176 B, `4152442bd512…`) |
| `t1-harness.sh` | Test 1, commands 2–5 | identical (1496 B) |
| `t2.sh` | Test 2, all 3 | identical (`0526d9691e25…`) |
| `t3.sh` | Test 3, all 5 | identical (`e593ab0e8f04…`) |
| `t4-replay.sh` | Test 4, commands 1–9 | identical |
| `t4-reset.sh` | Test 4, command 10 | identical |
| `t5.sh` | Test 5, all 3 | identical (`3f23d8bef765…`) |
| `t6.sh` | Test 6, all 7 | identical (`ebc9700c8968…`) |
| `t7-mongo.sh` | Test 7, all 9 | identical (`df7366ab5369…`) |
| `t7-ditto.sh` | Test 7, commands 2–6 + the Repeat heading's 4 | identical |
| `t8-a-reboot.sh` | Test 8, command 1 (with its two comment lines) | identical |
| `t8-b-return.sh` | Test 8, commands 2–3 | identical |
| `t8-c-snapshot.sh` | Test 8, command 4 | identical |
| `t8-d-smoke.sh` | Test 8, command 5 | identical |
| `t9-a.sh` | Test 9, command 1 + the first line of command 2 | identical |
| `t9-b.sh` | the 12 trailing comment lines of command 2 + command 3 + the first line of command 4 | identical |
| `t9-c.sh` | the trailing comment line of command 4 + command 5 + the first line of command 6 | identical |
| `t9-de.sh` | the 3 trailing comment lines of command 6 + commands 7–10 | identical |

Also shown there:

- **Families whole.** For T1, T2, T3, T4, T5, T6, T7, T8 and T9 the step files concatenated (ids reverted) are the
  heading's entire `_host_commands` output (5, 3, 5, 10, 3, 7, 9, 5, 10 commands): nothing is lost between files and
  nothing is duplicated, except test 7's definitions in `t7-ditto.sh`.
- **Cuts only before comments.** The three places where a command is cut between two files (after T9 commands 2, 4
  and 6) are followed by 12, 1 and 3 lines that all start with `#`.
- **Ids.** `-q1` stands 2, 1, 1, 1, 1, 1, 1, 1, 3, 5, 1, 1, 4, 3 times in the fourteen files that carry one and 0
  times in `t1-harness.sh`, `t6.sh`, `t8-b-return.sh`, `t9-de.sh`; every occurrence is the suffix of one of that
  file's expected ids and is not followed by a name character or a hyphen; no old literal stands without it;
  `nominal-r02`, `controller_restart-r03`, `itest-acl-$T`, `itest-replay` are untouched. The token census of
  `verify2.console.txt` §5: `itest-reboot-q1` ×8, `itest-smoke-$i-q1` ×2, `itest-auth-wrongpw-q1` ×4,
  `itest-notls-q1` ×3, the other nine once each; `itest-acl-$T` ×11, `itest-replay` ×2; plan literals without a suffix.
- **Line numbers.** Searching each reverted line in the blob gives exactly the manifest's `source_line_numbers`
  for all 18 files (1300; 1310–1313; 1325–1337; 1345–1373; 1383–1391; 1399; 1407–1409; 1421–1427; 1439–1461;
  1440–1458 + 1477–1480; 1486–1488; 1489–1490; 1491; 1492; 1501–1502; 1503–1516; 1517–1519; 1520–1526).
- **Manifest and diffs.** `sha256_before` recomputed from the real `_host_commands` text, `sha256_after`,
  `diff_sha256` all match; every diff's `-` lines are its `+` lines without `-q1`, and its `+` lines are the file's
  changed lines.
- **The ids are valid run ids:** `^[A-Za-z0-9._-]{1,64}$` (envelope schema, `egw_simulator/runner.py:65`,
  `egw_controller/events.py:49`, `sut_log`/`events_start` of the helpers) accepts every one.

`g3_extract_rows.py --check` on a copy of `rows/` with the frozen blob and rule source: `39 files compared, 0 differ`
(exit 0). It refuses an altered blob (sha256) and, with the real `HOME`, every forbidden output directory, creating
nothing (`verify2.console.txt` §1).

## 2. `t7-ditto.sh` (`verify2.console.txt` §2, `verify_ditto_composition.console.txt`)

- Its 23 lines are `[ln for ln in t7[:-3] if not ln.startswith("R=")] + ditto` — the **frozen test's own
  composition** of the Ditto repeat (`_ditto_body`, `test_runbook_itest_helpers.py`), which is how the runbook's
  tests exercise it ("pasted in the same shell right after test 7, whose helpers it reuses", line 1474).
- Trace of the first 19 lines (DEBUG trap, `env -i`, empty `PATH`): the only command executed at source time is
  `DC="cd /opt/egw/deployment && docker compose --env-file .env --env-file images.lock.env"`; afterwards
  `declare -F` lists `fault`, `fault_recover`, `readyp`, `svc_state`; `R`, `SVC`, `T7` are unset. No action.
- Lines 1–19 equal lines 2–20 of `t7-mongo.sh`; lines 21–23 equal lines 21–23 of `t7-mongo.sh`; line 20 is
  `R=itest-ditto-fault-01-q1; SVC=ditto-things`.
- Everything lines 1477–1480 use is set: `R`, `SVC` (line 20); `DC`, the four functions (lines 1–19); `T0_7`,
  `FAULTP`, `READYP`, `SP`, `FW`, `RK`, `LC`, `LB`, `EV`, `T7` (set by the test line itself); `P`, `REC`, `CTRL`,
  `pre`, `events_start`, `sim_post`, `sut_log`, `events_stop`, `stop` (helper file); `HOME`. The stub bench ran the
  whole path (`pre` → `events_start` → `fault` → `svc_state`/`fault_recover` → `sut_log` ×2 →
  `events_stop … die,stop,start egw-ditto-things-1`) under an added `set -u` with no unbound variable on the success
  pass.

## 3. Every file in a fresh shell (`vars.console.txt`, `fresh_shell_bench.console.txt`, `verify2.console.txt` §4, `real_helpers_bench.console.txt`)

The helper and tunnel files used are the ones the real test module extracts from the copy's runbook: sha256
`e5eba37e…` (545 lines) and `38f5cae9…`, equal to the deployed `~/egw-tcg/itest-helpers.sh` and `tunnel.sh`.

Static (`vars.py`): for each file, every shell variable it reads is set in the file itself, by the helper file
(`P`, `CTRL`, `DITTO`, `MQTT_PORT`, `REC`, `EGW_CLONE`) or by the hx preamble (`HOME`, the exported `.env`
password). The one name flagged, `c` in the two T7 files, is `\$c` inside the guest command of `svc_state` (a guest
variable). Every helper called exists in the helper or tunnel file.

Dynamic (`fresh_shell_bench.sh`): each of the 20 files sourced in its own `env -i` bash, the steps script's
`exec 2>&1; unset …; set -v`, stub helpers and stub commands, **`set -u` added**, two passes (everything succeeds /
everything fails): 0 `command not found`; 3 `unbound variable` lines, all three the runbook's own design and
harmless without `set -u`:

- `t6.sh` line 5, `DRAIN_QUIET_S=$DRAIN_QUIET_S …` after the steps script's unset: the runbook reads "this shell's"
  values, empty when unset. Shown separately (`verify2` §3): `harness_cmd`'s children then see `DRAIN_*=` (empty) and
  `EVENTS_EXPECTED=die,start`, and the frozen `proof_hook_drained.sh` run with the three empty prints
  `drained with DRAIN_QUIET_S=130 DRAIN_STEP_S=5 DRAIN_LIMIT_S=900` (the helper's `${…:-130}`; `run.py` reads none
  of them).
- `t7-mongo.sh` / `t7-ditto.sh` line 23 on the failed-precondition path: `$LC` inside the STOP text only (the
  runbook's "LC alone may be left in this shell"); in a fresh shell it prints `''`.

Per split row:

| Step | What it reads from another step | How it gets it | Shown |
|---|---|---|---|
| `t1-harness-analyze.sh` | nothing (the literal `nominal-r02`, absolute paths) | — | bench: `analyze exit=0`, one row printed, `per_run read exit=0`; `run_id` and the six columns exist in `PER_RUN_COLUMNS` (`analyze.py:1074`) |
| `t8-b-return.sh` | nothing | `tunnel_down`, `tunnel_up`, `stop` from the preamble | real-helper bench: `Exit request sent.` / `TUNNEL CLOSED` / `TUNNEL UP` |
| `t8-c-snapshot.sh` | the boot id before the reboot; the pre-reboot twins | the FILE `$P/itest-reboot-q1.boot_id.pre` and the snapshot files step a left (no shell variable); `B1` is set in the line | fresh shell: `REBOOT SHOWN: boot id aaaaaaaa-… -> bbbbbbbb-…`, then `wait_ready 3600`, `snap … --like pre-reboot`, `same`; with the unchanged boot id it refuses (`STOP: test 8: persistence across a reboot NOT verified`) |
| `t8-d-smoke.sh` | nothing (`R` set in the line) | — | `run_test itest-post-reboot-01-q1 42 --scenario smoke --duration 30` |
| `t9-b.sh` | nothing (`T0_9B` set in the file) | — | real helpers: `guest_epoch 3` → `1789999997`, probe `exit=1`, `sut_log broker itest-auth-wrongpw-q1 1789999997`, the log printed; files `itest-auth-wrongpw-q1.sut/broker.{log,fetch.txt}` |
| `t9-c.sh` | nothing (`T0_9C` set in the file) | — | same, `itest-notls-q1` |
| `t9-de.sh` | nothing (`T`, `PR`, `B`, `A` set in the file; `${PR:-stop}`) | — | `metrics itest-acl-<stamp> before`, the probe, `metrics … after`, `scp -r`, the comparison refusing on missing files |
| `t9-exposure.sh` | nothing | — | below |

Carriers: `RT` (t2 line 1 → 2, 3; t3 line 1 → 4, 5; t5 line 1 → 2, 3), `T1H` (t1-harness 3 → 4), `F3`/`C3`
(t3 1 → 2 → 3), `T4`/`REPLAYED`/`T4RC` (t4-replay 1 → 3 → 4 … 9, with `replay()` defined on line 2), `F6`/`T6`
(t6 1 → 5 → 6, with `SEED`, `RESTART`, `RAW6`), `T7` (t7 21 → 22, 23), and `T0_3`, `T0_5`, `T0_7`: each is set and
read inside ONE file. No carrier crosses a file; where the runbook's lines of one test are split (T8, T9, T1's
analyze) no line reads a variable of an earlier one.

The steps script's `no_stop` (which decides T1's analyze, T8's later steps and T9's chain) treats any `STOP:` in the
console as a stop when the step file itself holds no `STOP:` text: none of `t1-harness.sh`, `t8-a/b/c`, `t9-a/b/c/de`
holds the string (`grep -c 'STOP:'` = 0; only the two T7 files do, and they are not chained), so the `set -v` echo of a
file is never taken for a STOP. `plan`'s refusal on the existing plan (t1-harness line 1) prints `error: … already
exists`, exit 2, no `STOP:` (`cli.py:759`).

## 4. The two prose-only files

- **`t1-harness-analyze.sh`** — line 4 quotes the sentence that stands on runbook line 1320; command 1 is,
  character for character, the fenced line 1427 followed by `; echo "analyze exit=$?"`; command 2 reads
  `~/egw-tcg/pilot/results/processed/per_run.csv` and prints the six columns line 1320 names for `run_id ==
  nominal-r02`, exit 0 only for exactly one row. It writes nothing itself; `analyze` rewrites `processed/` as the
  runbook's own command does (the steps script snapshots it before and after). No id, no `-q1`.
- **`t9-exposure.sh`** — line 4 quotes the last sentence of line 1529. Three reads: (1) `ssh -n -o BatchMode=yes
  -o ConnectTimeout=20 -o StrictHostKeyChecking=yes -o UpdateHostKeys=no -o UserKnownHostsFile=…/known_hosts_egw_tcg
  -o IdentitiesOnly=yes -i …/egw_campaign -p 2222 root@127.0.0.1 true` (no prompt, nothing added to the pinned file,
  stdin not read); (2) `ss -ltnp`; (3) `ssh -n egw-tcg 'docker ps --format "{{.Names}} {{.Ports}}"'`. Each prints its
  exit status; none judges; none writes. The file names are the runbook's (lines 78, 86–93) and the host's
  (`~/.ssh/config`: `HostName 127.0.0.1`, `Port 2222`, the same key and known-hosts file); `ssh-keygen -F
  '[127.0.0.1]:2222' -f ~/.ssh/known_hosts_egw_tcg` finds the pinned ed25519 key, so with `StrictHostKeyChecking=yes`
  check (1) reaches authentication and can print `Permission denied` (a local read; no connection was made).

## 5. `bash -n`

All 20 files pass in WSL bash 5.2.21 and in Git Bash. All are LF-only, UTF-8, one final newline, no tab; the only
non-ASCII character is the em dash in the comment on line 3 of `t8-a-reboot.sh` (runbook line 1488).

## Findings

No material finding.

### Minor

**M1 — `g3_extract_rows.py`: the output-directory guard follows `$HOME`.** `forbidden_out()` builds its four roots
from `os.path.expanduser("~")`. With `HOME` redirected (as every rule-3 dry run does) the real directories are no
longer refused: called as a pure function with `HOME=/tmp/g3-dry-rows/home`, `forbidden_out("/home/ruisth/egw-tcg/itest")`,
`…/egw-exec/repo/rows`, `…/egw-exec/attempts/x` and `…/yocto/x` all return `None` (with the real `HOME` each is
refused). Bounded: it needs both a redirected `HOME` and an `--out` typed into one of those trees; the recorded run
used neither. Fix: also refuse by path component (`egw-exec`, `egw-tcg`, `egw-images`, `yocto`), as it already does for
`output_test`, `ChatGPT`, `cand`, or resolve the roots from `pwd.getpwuid(os.getuid()).pw_dir`.

**M2 — `t8-b-return.sh` line 2 under hx always closes a LIVE master (first exercised by the battery; not
reproduced on real OpenSSH).** The runbook's line 1490 (`tunnel_down && tunnel_up`) follows a reboot that killed the
master. Under the steps script each step's hx preamble runs `tunnel_check || tunnel_up` first, so when step b starts
the tunnel has just been reopened (the real-helper bench shows `TUNNEL UP` from the preamble, then `Exit request
sent.` / `TUNNEL CLOSED` / `TUNNEL UP` from line 2). `tunnel_up` runs `ssh -O check` and `ss -ltn | grep ':(8000|8080) '`
a few milliseconds after `ssh -O exit` returned; if the old master has not finished exiting it answers `MASTER
ANSWERS … nothing was reopened` (status 0, no STOP, and the tunnel is then down) or `STOP: host port busy`. Neither
is silent: the steps script's `t8-tunnel-check` after step b halts the row ("step c and step d were NOT run"), so
no false evidence results, but T8 would end as invalid instrumentation and T9 would not run. The window is very small;
the row file is the runbook's text and is right. Fix (no row change): name this signature in the README's T8 notes so
the operator classifies it as a tunnel event and not as a SUT observation.

### Nits

**N1 — manifest row note of `t9` (and the brief's table) do not say that `t9-exposure.sh` is gated too.** The
manifest says "Each of t9-a, t9-b, t9-c, t9-de only if the one before printed no STOP:. t9-exposure.sh is the
prose-only step"; `steps_t9` and the README gate the exposure step as well (a `STOP:` in `t9-de`'s console — any probe
result but PASS prints one — skips it, "runbook line 15"). Consequence to know when classifying: after a (d)+(e) STOP
the three read-only exposure reads are not in the package. Fix: add "t9-exposure.sh likewise" to the `ROWS` note of
the extraction script, or state the choice in the result note.

**N2 — manifest note 4 says hx "loads the same preamble from the clean clone".** Line 1260 sources `~/egw-tcg/.env`
and `~/egw-tcg/itest-helpers.sh`; hx's `HOST_PRE` (defined in the clone's `guest_common.sh`) activates the venv,
exports `.env` and `EGW_CLONE`, sources the DEPLOYED helper file and `tunnel.sh` and checks the tunnel. A superset,
and the helper file is `~/egw-tcg/itest-helpers.sh` (`e5eba37e…`), not a file of the clone. Wording only.

**N3 — `only_defines()` proves less than its docstring says.** For a function it checks the head `name() {` and that
the text ends with `}`; a text such as `f() { :; }; action; g() { :; }` would pass. For the five actual commands it is
right, and the DEBUG trace (here and in `g3_check_rows.sh`) is the real proof. Wording of the docstring, or leave.

## What this verification does not show

- Nothing ran on the guest; every "UNVERIFIED" of the runbook stays as it is.
- The steps script was read only for how it uses the row files (step names, `STEP_PRE`, `no_stop`, the T8/T9/T1
  conditions); its own logic (state, gate, registration, close) is another verification.
- M2 is reasoned from `tunnel.sh` and the stub bench, not reproduced with a real ssh master.

## Files of this verification (`prep/verify-rows/`)

`setup.sh`, `verify_rows.py` + `.console.txt`, `extract_helpers.py`, `vars.py` + `.console.txt`,
`fresh_shell_bench.sh` + `.console.txt` + `bench-out/` (40 transcripts), `verify2.sh` + `.console.txt`,
`verify_ditto_composition.py` + `.console.txt`, `real_helpers_bench.sh` + `.console.txt`,
`itest-helpers.from-copy.sh`, `tunnel.from-copy.sh`, `verified-hashes.txt`.
