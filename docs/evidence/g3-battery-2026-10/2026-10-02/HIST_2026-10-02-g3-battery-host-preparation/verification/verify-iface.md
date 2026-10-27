# verify-iface — `g3_battery.sh` against the frozen interfaces, and its dry run

Verifier's record, 2026-10-02. Subject: `prep/g3_battery.sh`, sha256
`51a1ab5e260e4703cacd810497a4dc702ef5e8be455cd442c2ea43ccde8eba70` (1,618 lines, LF only, `bash -n` clean).
Frozen side read in `$S/cand` (`80e833f`): `tools/session/common.sh`, `guest_common.sh`, `guest_session_open.sh`,
`preflight.sh`, `gate_health.sh`, `guest_session_close.sh`, `nominal.sh`, `proof.sh` (the `guest_state_delta.py`
calls), `driver_status.py`, `guest_state_delta.py`, `guest/*.sh`, `src/egw_experiments/local_export.py`,
`src/deployment/scripts/capture-sut-environment.sh`; the host's `~/egw-tcg/itest-helpers.sh` and `tunnel.sh` (read only).

**Result: no material defect was demonstrated. One minor defect (F1) and two nits (F2, F3).** Nothing was edited in
`g3_battery.sh`, the row files or the extraction script.

## 1. Findings

### F1 — minor — `term` prints and keeps the simulator's password (`g3_battery.sh` line 1449; also line 1133)

`cmd_term` prints the row's process group with `pgrep -g … -a | cut -c1-200`. For every row that runs the helper's
`$SIM` (t1-smokes, t2, t3, t4-replay, t4-reset, t5, t7-mongo, t7-ditto, t8 step d) the simulator's command line is
`python -m egw_simulator run --broker 127.0.0.1 --port 8883 --username egw-simulator --password <value> …`: the value
starts at about column 102, inside the 200 columns. It goes to the caller's terminal and into
`<state>/console/NNN-term-<slug>.txt`, which the operator records seal. `wait_group` (line 1133) writes the whole,
uncut `pgrep -a` reading to `<state>/row-<slug>.group-after-signal.txt` (the last reading is kept: it holds the line
only if a simulator is still alive at that reading). `status` and `close` cut at 90 columns and do not reach the value.

This is what the operator procedure's "`set -v`, never `set -x` (the simulator password is on its argv)" exists to
prevent. Bounded: only when `term` is used while a simulator runs (the case `term` is for: a row past its ceiling);
the frozen export would exclude that console file from a sealed package and keep a sanitised copy.

Demonstrated in bench `h2` (fake row running the REAL helper's `$SIM` string; a stub module that only sleeps stands
for the simulator; the bench `.env` holds the placeholder `bench-value-0000`, shown below as `<SECRET>`):

```
--- the simulator stand-in as the kernel shows it
23217 python -m egw_simulator run --broker 127.0.0.1 --port 8883 --username egw-simulator --password <SECRET> --ca-cert /tmp/g3-dry-iface/h2/home/egw-tcg/ca.crt --egw-id egw-01 --output … --qos 1 --seed 7 --scenario smoke
status output holds the secret value: 0 line(s)
=== h: term t2
## 2026-10-02T12:59:12Z up=1309 term t2: the process group 22841 (row state 'running', step 't2')
…
23217 python -m egw_simulator run --broker 127.0.0.1 --port 8883 --username egw-simulator --password <SECRET> --ca-cert /tmp/g3-dry-iface/h2/home/egw-tcg/ca.crt --egw-id egw-01 --output /tmp/g
TERM sent to the process group 22841 (exit 0). KILL is never sent.
term output (the caller's terminal) holds the secret value: 1 line(s)
=== h: where the value is on disk afterwards (file: number of lines holding it)
egw-exec/g3-battery/console/002-term-t2.txt:1
```

Fix (one of): cut the listing in `cmd_term` at 90 columns as `status` does, or pass every member listing that is
printed or written (`cmd_term` line 1449, `wait_group` line 1133) through
`sed -E 's/(--password)[ =][^ ]+/\1 <redacted>/g'`.

### F2 — nit — `classify` ends with "Next: the next row…" for a row whose gate failed (line 1431)

`HALTED` is 0 in the `classify` invocation (the gate's halt was recorded by the `row` invocation), so after the NOTE
"no further row starts; 'close' and hand back to Rui" the last line still says
`Next: the next row of session S1, or 'close' after the last one.` The guard itself holds: the next `row` is refused
on the recorded halt. Bench `g`, case 11:

```
NOTE: this row's gate did not pass (failed: guest-state-delta exit 1 (faults and problems: 1 0): … a recorder or collector unit is still active (gate-units exit 3) …
Next: the next row of session S1, or 'close' after the last one.
REFUSED: NOT STARTED: session S1 has a recorded halt (up=1153 row=t2 row t2: the gate did NOT pass (packet section 4, halt 3) …
```

Fix: print the "Next:" line only when the row's gate is `pass` and the session file holds no `halt=` line; otherwise
print "Next: 'close', then hand back to Rui".

### F3 — nit — `prep_brief.md` rule 3: the archive command cannot run in WSL

`git -C <WSL path of $S/cand> archive HEAD` fails: the worktree's `.git` names a Windows path.

```
gitdir: C:/Users/ruimf/Documents/Projeto Mestrado/Claude/.git/worktrees/cand
fatal: not a git repository: /mnt/c/…/scratchpad/cand/C:/Users/ruimf/Documents/Projeto Mestrado/Claude/.git/worktrees/cand
```

The same commit was archived from the WSL clone, which was only read (`git -C ~/egw-exec/repo archive HEAD`), and the
copy was proved to be the frozen tree (section 3). Fix: name `git -C ~/egw-exec/repo archive HEAD` in the brief.

## 2. Interface by interface (reading; the bench evidence is in section 3)

| Call in `g3_battery.sh` | Frozen interface | Verdict |
|---|---|---|
| sourcing `common.sh`, `guest_common.sh`; `DRIVERS=$REPO/tools/session`; `export EGW_EXEC_REPO` (l. 39–50) | `common.sh` l. 7–15 derives `DRIVERS` from `$0`, `REPO` from `EGW_EXEC_REPO`; `guest_common.sh` l. 13 reads `SESSION` | correct; `drivers_sha256` read through the reset `DRIVERS` is the packet's `4a6a572d…` (bench a) |
| `new_attempt "G3 qualification $ROW_SLUG" official` (l. 1264) | `new_attempt SCENARIO PURPOSE` (`common.sh` l. 98); `PURPOSES` holds `official`; slug `g3-qualification-<slug>` (`scenario_slug`) | correct; the `fresh_row` glob `*_g3-qualification-<slug>_attempt*` matches that slug |
| `$LE set --attempt "$A" "pid=$$" "identities=$ids" "workload=$json"` (l. 1293) | `set KEY=VALUE`, value parsed as JSON when possible, dicts merged (`local_export.py` l. 2711, 912) | correct: `identities` and `workload` arrive as objects, `pid` as a number; `run_id` is never set (grep: comments and the plan reader only) |
| `add_src` → `$LE add-source --attempt --kind --path [--siblings-glob] --role` (l. 865–871) | l. 2738–2743; kinds `raw`, `simulator`, `other` | correct; every write target of the 20 row files is under a registered source (section 3, test f) |
| `ex "$A" NAME CMD…` (snapshots, T8 wait, re-launch, delta) | `ex ATTEMPT NAME CMD...` (`common.sh` l. 103) | correct |
| `gx "$A"/"$S" NAME GUEST-COMMAND` (guest state, units, stop, journals, listing) | `gx ATTEMPT NAME GUEST-COMMAND`, 255 → 97 (`guest_common.sh` l. 46) | correct; the guest command reaches ssh as one argument (bench a `commands.jsonl`) |
| `hx "$A" "$step" "$STEP_PRE; . '$A/environment/$step.sh'"` (l. 948) | `hx ATTEMPT NAME HOST-SCRIPT`; body appended after the preamble group (`guest_common.sh` l. 73–78) | correct; `$A` is expanded by the steps script and single-quoted in the body (bench a argv) |
| `healthy_wait "$A" gate-healthy 900 15` (l. 1105) | `healthy_wait ATTEMPT NAME LIMIT STEP` (l. 210) | correct |
| `repo_identity` (l. 514, 1287) | one-line JSON, non-zero when unread (`common.sh` l. 60) | correct |
| `headline "$A" TEXT`; `driver_code "$A"` (l. 1407–1408) | `headline ATTEMPT TEXT`; `driver_code` returns, `driver_exit` exits (`common.sh` l. 126–139, 200) | correct: `classify` uses `driver_code`, so the battery state is written after the export |
| `(driver_interrupt "$A")` in a subshell (l. 1164) | `driver_interrupt` finishes `interrupted` and calls `driver_exit` (l. 219) | correct: the subshell absorbs the `exit`; 130 recorded (bench c) |
| `$LE finish --attempt --status --validity --outcome --reason --next-action` (l. 1404) | l. 2749–2755; pairs of packet §5 | correct; a pair outside §5 is refused before `finish` |
| `guest_state_delta.py --expect "$EXPECT_SERVICES" [--expect-restarted NAME] BEFORE AFTER` (l. 1091–1094) | `parse()` l. 358–387; `nominal.sh` l. 289 and `proof.sh` l. 2325 use the same form; exit 0/1/2 and the summary line | correct; container names are those of `EXPECT_SERVICES` |
| drivers: `bash "$REPO/tools/session/<name>.sh" < /dev/null 2>&1 \| tee` (l. 642) | none takes an argument (`gate_health.sh` l. 57 refuses any); 0 is the only pass | correct |
| preflight attempt: `driver_run_id` → `$ATTEMPTS/<run id>`; `environment/sut_environment.json` (l. 650, 809–815) | `preflight.sh` l. 31 and 257; `driver_status.py` l. 213 prints `DRIVER RESULT <run_id>:` | correct (function-level test e) |
| labels check: `provider` holds QEMU and TCG, `instance_type` holds `ARM64 EMULATED` | `preflight.sh` l. 255; keys of `capture-sut-environment.sh` l. 96–98 | correct (test e, with the frozen capture script) |
| T8 re-launch `ex "$A" t8-relaunch bash "$SESSION/scripts/session_open.sh" "$SESSION" s2` (l. 996) | `guest_session_open.sh` l. 136 (`ex "$S" boot bash "$S/scripts/session_open.sh" "$S" "$RUN"`); `guest/session_open.sh` usage `<evidence-dir> <run-name>` | correct (bench d, with the frozen `session_open.sh` and `boot_driver.sh`) |
| T8 wait: `boot/<run>.status`, `pgrep -af "$QEMU_EXE_RE"`, ports 2222/8883 | `guest/boot_driver.sh` writes `boot/$RUN.status` when the launcher returns; `QEMU_EXE_RE` of `guest_common.sh` l. 26 | correct |
| close: `gx "$S" stack-stop-130 "cd /opt/egw/deployment && docker compose --env-file .env --env-file images.lock.env stop -t 130; …"` (l. 1517) | `$DC` of `guest_common.sh` l. 12; `guest_session_close.sh` l. 48 | correct; both env files reach the guest (bench a `docker.log`) |
| close: rootfs hash read from `*-artefacts-after-poweroff.stdout.txt` (l. 1528–1531) | `guest_session_close.sh` l. 116 (`sha256sum "$1"` first) | correct (bench a) |
| `set -u` | the frozen drivers run under `set -u` too; `tunnel.sh` holds no unguarded variable | no hazard found on any path that was run or read |
| `bash -lc`, non-interactive, detached (`setsid … < /dev/null`) | — | works (benches c, h2: own process group, console in the state directory) |

Not a defect, noted: a registered source that was never written makes the package "verified; incomplete", and
`driver_status.py` then derives 3 for a `valid/pass` or `valid/fail` classification. For a row that ran, every
pre-registered root exists; it shows only for rows that stopped before the simulator (bench b: `not-applicable/not-run`
→ exit 2, `package=INCOMPLETE`, which the script records as it is).

## 3. Dry run (hard rule 3)

Tree: `/tmp/g3-dry-iface/` only. `repo/` is `git -C ~/egw-exec/repo archive HEAD | tar -x`, made a checkout inside
the bench (`git init`, `git add -A -f`, `git write-tree`, the frozen commit object written with
`git hash-object -t commit -w`): no file of the copy was changed, so the frozen drivers ran unmodified and their real
sha256 was checked.

```
tree of the copy: dad725d0bebc25c91712af2aa2705d5eeb92044f (frozen: dad725d0bebc25c91712af2aa2705d5eeb92044f)
commit object written in the copy: 80e833f44f647fe9cd8f5e99d3abf3c444de95aa
copy: HEAD=80e833f44f647fe9cd8f5e99d3abf3c444de95aa tree=dad725d0bebc25c91712af2aa2705d5eeb92044f porcelain lines=0
```

Each bench `/tmp/g3-dry-iface/<name>`: `HOME`, `EGW_EXEC`, `EGW_ATTEMPTS`, `EGW_OUTPUT_TEST`, `EGW_SECRETS_ENV` inside
it, `EGW_EXEC_REPO=/tmp/g3-dry-iface/repo`; copies of the real `itest-helpers.sh`, `tunnel.sh`, `ca.crt`; a stub `.env`;
stub `ssh`, `scp`, `curl`, `pgrep` first on `PATH`; stub guest `docker`, `systemctl`, `sudo`, `dmesg`, `journalctl`,
`df`, `poweroff`; `$PY` a wrapper of the real venv interpreter (`PYTHONDONTWRITEBYTECODE=1`,
`PYTHONPATH=<bench repo>/src`; `python -m egw_simulator` a stub); a FAKE open session (an attempt of the frozen export
tool with the frozen `guest/*.sh` copied as `guest_session_open.sh` copies them) and the state files an `open` would
have left. Launch: `MSYS_NO_PATHCONV=1 wsl -d Ubuntu-24.04 --exec bash -lc 'bash …/verify-iface/run.sh <bench> <subcommand>'`.
Scripts and records: `prep/verify-iface/` (`bench_setup.sh`, `run.sh`, `test_c.sh` … `test_h.sh`, `stubs/`,
`fakerows/`, `record/<bench>/`).

### n — no session

```
=== n: status
open session (current_session): none; host uptime now: 278 s; WSL boot fb8dd28d-…
qemu pgrep exit=1 (0 running, 1 none)
session S1: not opened
session S2: not opened
exit=0
=== n: row t2 (no session)
REFUSED: session S1 was not opened by this script (/tmp/g3-dry-iface/n/egw-exec/g3-battery/session-S1.env is absent)
exit=2
```

`row nosuch`, `classify t2 …`, `close`, `term t2`, no subcommand: each `REFUSED`/usage, exit 2. Afterwards the bench
holds no row attempt, no row state file, nothing in `output_test`, nothing in `egw-tcg/itest`.

### a — one complete ad-hoc row `t2` (fake row file), `classify`, `close`

`row t2` with `t1-harness` not classified: `REFUSED: the previous row t1-harness is 'not started'…`, exit 2. Then
(with `DRAIN_QUIET_S=7 ACCEPT_UNACCOUNTED=1` exported on purpose in the caller's environment):

```
keepalive: attached, about 43140 s left (needed: 3960 s). …
clone /tmp/g3-dry-iface/repo: HEAD=80e833f44f647fe9cd8f5e99d3abf3c444de95aa tree=dad725d0bebc25c91712af2aa2705d5eeb92044f
clone: clean (0 porcelain lines)
repo_identity: {"repo_commit": "80e833f…", "repo_dirty_lines": 0, "export_tool_sha256": "544c9b3d…", "drivers_sha256": "4a6a572dc1e2b54754c3a8dec38e6d2392227efc61ee710886ad9ad5729a39a5"}
runbook: c55a2d3b…  helpers: e5eba37e… (545 lines, bash -n clean)  tunnel.sh: 38f5cae9…  ca.crt: 556e139f…
guest-state command: identical to GUEST_STATE of /tmp/g3-dry-iface/repo/tools/session/nominal.sh
session clock: NOW=287 UP0=267 elapsed=20 s (cutoff 10800 s)
## … row t2: attempt /tmp/g3-dry-iface/a/egw-exec/attempts/20261002T124254Z_g3-qualification-t2_attempt01 …
carriers after the unset: DEVICES=<unset> ACCEPT_UNACCOUNTED=<unset> EVENTS_EXPECTED=<unset> DRAIN_QUIET_S=<unset> DRAIN_STEP_S=<unset> DRAIN_LIMIT_S=<unset> READY_LIMIT_S=<unset>; EGW_CLONE=/tmp/g3-dry-iface/repo …
bench here-document reads /tmp/g3-dry-iface/a/home/egw-tcg/itest/itest-3dev-01-q1.twin.a.json
carrier RT=0 is still set on a later line (one shell); DRAIN_QUIET_S=<unset> ACCEPT_UNACCOUNTED=<unset>; stdin: /dev/null
guest-state-delta: faults=0 problems=0
ALL HEALTHY: the 6 expected services are running and healthy (sample 1)
no egw-events-* and no egw-resources-* unit is active
TUNNEL CHECK: the master answers on /tmp/g3-dry-iface/a/home/egw-tcg/tunnel.ctl
## … GATE t2: pass (guest state compared, six services healthy, no recorder or collector unit active, tunnel up)
## … row t2 ended after 1 s; the attempt is OPEN for the operator's classification
```

`attempt.json`: `"purpose": "official"`, `"scenario": "G3 qualification t2"`, `"status": "running"`,
`"pid"` the script's, `identities` an object, `workload` an object with `itest_run_ids: ["itest-3dev-01-q1"]`,
`harness_run_id: null`, `rows_manifest_sha256`, `step_files`, `steps_script_sha256`, `host_uptime_baseline_s`; no
`run_id` was set. `sources.json`: `simulator /…/itest/itest-3dev-01-q1`, `siblings_glob "itest-3dev-01-q1.*"`.
`environment/`: `t2.sh`, `t2.sh.diff`, `rows.manifest.json`, `rows.manifest.t2.json`, `g3_battery.sh`.
`commands.jsonl` (argv as recorded):

```
2 t2 exit 0  argv: ["bash", "-c", "{ . /tmp/g3-dry-iface/a/egw-exec/venv/bin/activate && set -a && . $HOME/egw-tcg/.env && set +a && export EGW_CLONE=/tmp/g3-dry-iface/repo && . $HOME/egw-tcg/itest-helpers.sh && . $HOME/egw-tcg/tunnel.sh && { tunnel_check || tunnel_up; } ; } || { echo 'STOP: the host preamble …' >&2; exit 97; }\nexec 2>&1; unset DEVICES ACCEPT_UNACCOUNTED EVENTS_EXPECTED DRAIN_QUIET_S DRAIN_STEP_S DRAIN_LIMIT_S READY_LIMIT_S; echo \"carriers after the unset: …\"; set -v; . '/tmp/g3-dry-iface/a/egw-exec/attempts/20261002T124254Z_g3-qualification-t2_attempt01/environment/t2.sh'"]
4 guest-state-delta exit 0  argv: ["/tmp/g3-dry-iface/a/egw-exec/venv/bin/python", "/tmp/g3-dry-iface/repo/tools/session/guest_state_delta.py", "--expect", "egw-mosquitto-1,egw-mongodb-1,egw-ditto-policies-1,egw-ditto-things-1,egw-ditto-gateway-1,egw-controller-1", "…/console/001-guest-state-before.stdout.txt", "…/console/003-guest-state-after.stdout.txt"]
```

`classify`:

```
=== classify with a pair outside section 5
REFUSED: validity/outcome 'valid/unknown' is not a pair of packet section 5 (…)            exit=2
=== classify t2 valid/pass
exported 20261002T124254Z_g3-qualification-t2_attempt01: /tmp/g3-dry-iface/a/out/runs/2026-10-02/20261002T124254Z_g3-qualification-t2_attempt01 (verified, 25 files, 0 excluded)
DRIVER RESULT 20261002T124254Z_g3-qualification-t2_attempt01: exit=0 (… package exported and verified) status=finished instrumentation_validity=valid system_outcome=pass export=exported headline="G3 qualification t2: pass. …"
row t2: classified 'pass'; driver code 0; export: verified -> /tmp/g3-dry-iface/a/out/runs/2026-10-02/…
```

The package in the temp `output_test` holds `console/001…007` (stdout and stderr), `environment/` (the five files),
`simulator/itest-3dev-01-q1/sent_events.jsonl`, `simulator/itest-3dev-01-q1.marker.json`,
`simulator/itest-3dev-01-q1.twin.a.json`, `attempt.json`, `commands.jsonl`, `sources.json`, `SUMMARY.md`,
`SHA256SUMS`, `export_manifest.json`; receipt `package_state: verified`. `classify` again and `row t2` again: refused.

`close`, with the FROZEN `guest_session_close.sh` (and the frozen `guest/session_close.sh`) against the stubs:

```
bench docker compose stub, argv: compose --env-file .env --env-file images.lock.env stop -t 130
stop exit=0
## … guest_session_close.sh (frozen driver, /tmp/g3-dry-iface/repo/tools/session/guest_session_close.sh; console …/S1-guest_session_close.console.txt)
DRIVER RESULT 20261002T124234Z_guest-session_attempt01: exit=0 (…) status=finished instrumentation_validity=not-applicable system_outcome=pass export=exported
guest_session_close.sh exit=0
rootfs ext4 after the close: 2f40460b… (S2 opens only on this value)
## … session S1 closed (guest_session_close.sh exit 0)
```

Session attempt's steps: `g3-close-units`, `stack-stop-130`, `tunnel-down`, `stack-stop`, `oom-before-poweroff`,
`session-close`, `artefacts-after-poweroff`. The guest stub's log: `docker [compose] [--env-file] [.env] [--env-file]
[images.lock.env] [stop] [-t] [130]`, then the close driver's own `… [stop] [-t] [60]`. State: `state=closed`,
`stack_stop_130_exit=0`, `guest_session_close_exit=0`, `rootfs_after_close=…`.

### b — the REAL `rows/t2.sh` and `rows.manifest.json`, the real helpers, stub `curl`/`ssh`/`scp`/simulator

```
row file t2.sh: sha256 43fa83f2fc17b52dd41cb6d4f902ce2276ee2a0fae1e104b8692fe044f59e3b6 = sha256_after of the manifest (row t2, step 1, 1370 bytes)
R=itest-3dev-01-q1; run_test $R 7 --scenario smoke --duration 60; RT=$?
drained: queue_depth 0 and identical counters on 27 consecutive readings over 131 s (…) … elapsed 131.31 s (required 130 s …)
error: GET thing fb141468-… failed: <urlopen error [Errno 111] Connection refused>
STOP: snap_pair itest-3dev-01-q1 before: the twin snapshot failed; …
STOP: pre itest-3dev-01-q1: precondition failed - the simulator must NOT be started for this run id
STOP: TEST STATUS itest-3dev-01-q1: precondition failed -> simulator NOT started, nothing published
STOP: test 2: run_test did not complete (RT='1') - the twins were NOT read
[ "$RT" = 0 ] && python3 - ~/egw-tcg/itest/$R.twin.*.json <<'EOF' || stop "test 2: not evaluated (RT='$RT') or the evaluation script failed"
…
STOP: test 2: not evaluated (RT='1') or the evaluation script failed
## … row t2: step t2 ended; hx status 1 (the status of its last line; never a verdict)
## … GATE t2: pass …
```

The caller's `DRAIN_QUIET_S=7 ACCEPT_UNACCOUNTED=1 DEVICES=smartwatch READY_LIMIT_S=1` did not reach the row: the
drain waited the runbook's 130 s. The carrier `RT` chained across lines; the here-document was read; `STOP:` lines
landed in the one console. `classify t2 failed not-applicable not-run @reason.txt …`: exported, `DRIVER RESULT … exit=2
… package=INCOMPLETE (… 1 registered artefact(s) that were never written …)`, `HALT: row t2 is classified not started
(packet section 4, halt 1)`, exit 1; `row t3` then `REFUSED: NOT STARTED: session S1 has a recorded halt`.
`close` with an active unit: `HALT: close: a recorder or collector unit is active …`, nothing stopped; `close` with a
failing stop: `HALT: stop failed (stack-stop-130 exit 1): the close driver was NOT run and QEMU is NOT forced off`,
`current_session` kept, no close-driver console written.

### c — a detached row (`setsid`, no terminal), `term`, the interrupt

```
RUNNING: pid 14392 group 14392, step 't2', 0 min of its 36 min ceiling
=== close while the row runs      REFUSED: row t2 is running (pid 14392, state 'running'): 'term t2' sends TERM, never KILL   exit=2
=== classify while the row runs   REFUSED: row t2 is 'running', not awaiting classification …                                 exit=2
=== term t2                       TERM sent to the process group 14392 (exit 0). KILL is never sent.                          exit=0
## … row t2: interrupted by a signal (TERM)
HALT: row t2 was interrupted by a signal (TERM) during 't2' (packet section 4, halt 7). …
exported 20261002T124804Z_g3-qualification-t2_attempt01: … (verified, 16 files, 0 excluded, 2 console stream(s) not kept in full)
DRIVER RESULT 20261002T124804Z_g3-qualification-t2_attempt01: exit=130 (interrupted: marked interrupted and exported) status=interrupted instrumentation_validity=invalid system_outcome=interrupted export=exported capture_failures=2
```

The package holds the registered source as far as it was written (`simulator/itest-3dev-01-q1/sent_events.jsonl`,
`…marker.json`). `term` again, `classify` of the interrupted row and `row t3`: refused. `close`: session closed, exit 0.

### d — row `t8` (steps a, c, d fake; step b the REAL `t8-b-return.sh`); the re-launch through the FROZEN
`guest/session_open.sh` and `guest/boot_driver.sh` against a stub launcher (no QEMU)

```
sample 1 at +0 s: qemu pgrep exit=0 …; …/boot/s1.status absent; ports 2222/8883 free
sample 2 at +5 s: qemu pgrep exit=1 …; …/boot/s1.status present: exit=0 finished=bench; ports 2222/8883 free
QEMU EXITED: no qemu-system-aarch64 process, the first boot wrote its status file, ports 2222 and 8883 are free
[2026-10-02T12:50:51Z] opening session s2
[2026-10-02T12:50:56Z] s2: guest up, is-system-running=running, …
t8-relaunch argv: ["bash", "…/20261002T125045Z_guest-session_attempt01/scripts/session_open.sh", "…/20261002T125045Z_guest-session_attempt01", "s2"]
TUNNEL UP   (the preamble of step b reopened it; step b's own tunnel_down && tunnel_up: TUNNEL CLOSED, TUNNEL UP)
REBOOT SHOWN: boot id 11111111-1111-1111-1111-111111111111 -> fb8dd28d-3841-4fd2-8fd1-def2986ea7cd
gate: no guest-state comparison for T8 (the reboot replaces every start instant; packet section 3)
## … GATE t8: pass (guest state recorded and NOT compared across the reboot, …)
```

Steps recorded: `guest-state-before`, `t8-a-reboot`, `t8-wait-qemu-exit`, `t8-relaunch`, `t8-qemu-after-relaunch`,
`t8-b-return`, `t8-tunnel-check`, `t8-c-snapshot`, `t8-d-smoke`, `t8-previous-boot-journal`, `t8-previous-boot-oom`,
`guest-state-after`, `gate-healthy`, `gate-units`, `gate-tunnel-check` (all exit 0). `.current_run` = `s2`. Sources:
`simulator …/itest-post-reboot-01-q1` (+ `itest-post-reboot-01-q1.*`), `other …/itest-reboot-q1.boot_id.pre`
(+ `itest-reboot-q1.*`); the package holds `other/itest-reboot-q1.boot_id.pre`, `…twins.pre-reboot.json`,
`…twins.post-reboot.json`, `simulator/itest-post-reboot-01-q1/sent_events.jsonl`. `classify t8 … valid pass`: exit 0.
The close then ran the frozen close driver on run `s2` (`s2: collecting the final guest state`, `s2: QEMU ended`).
Its exit 3 in this bench is a bench artefact (my stub `poweroff` wrote `boot/s2.status` before the stub launcher had
ended, so the frozen `boot_driver.sh` had not yet removed its FIFO when the export ran); the script reported it as it
must (`session S2 closed (guest_session_close.sh exit 3)` and a HALT naming the driver console).

### e, f — function level (the script evaluated without its last line; no subcommand run)

- `driver_run_id` on the line the frozen `driver_status.py` prints → the attempt directory of the "live preflight"
  attempt (`THE preflight attempt`); on a `--stop` line → `none`.
- `environment_copy` on a capture written by the frozen `capture-sut-environment.sh` with the four `EGW_*` values
  of `preflight.sh` line 255: `labels: QEMU/TCG and ARM64 EMULATED are present`; `previous input kept:
  …/sut_environment.json.4c14c3a001c1`; `harness input now: … sha256 f7b5b7bb…`; a second run keeps the first capture
  under its own sha256; a capture without labels → `STOP`, exit 1, nothing replaced; no capture → `STOP`, exit 1.
- All twelve rows: `verify_row_files` against the real manifest, exit 0; every `-q1` id in the 20 row files is one
  the script names for freshness and sources, and the reverse; `manifest_tool sha` equals `sha256sum`;
  `verify_candidate` exit 0; `fresh_row` sees a planted sibling (`NOT FRESH`).

### g — the guards of `row` (each leaves 0 attempts, no row state file, no host artefact of the id)

| Case | Answer |
|---|---|
| another WSL boot id in the session file | `HALT: WSL was restarted since session S1 was opened …`, exit 1 |
| `UP0` 10,800 s before now | `NOT STARTED: the 3 h cutoff (row t2: 10800 s …)`, exit 1, halt recorded |
| no qemu process | `HALT: no qemu-system-aarch64 process could be shown …`, exit 1 |
| tunnel down | `HALT: tunnel_check failed before row t2 …`, exit 1 |
| untracked file in the (bench) clone | `HALT: the clone … is not clean (1 porcelain line(s)) …`, exit 1 |
| a sibling of the id on the host | `NOT FRESH …`, `HALT: an id of row t2 is not fresh on the host …`, exit 1 |
| helper file changed | `HALT: helpers (…) is d893a8f8…, the packet names e5eba37e… …`, exit 1 |
| script sha256 differs from the session's | `REFUSED: this steps script is not the one session S1 was opened with`, exit 2 |
| row file differs from the manifest | `HALT: the row files of t2 are not the manifest's …`, exit 1 |
| recorded halt, no `EGW_G3_RUI_GO` | `REFUSED: NOT STARTED: session S1 has a recorded halt …`, exit 2 |
| with `EGW_G3_RUI_GO`; an OOM-killed container and an active unit after the row | the row ran; `rui_go=` recorded; `HALT: row t2: the gate did NOT pass (packet section 4, halt 3): guest-state-delta exit 1 (faults and problems: 1 0) …; a recorder or collector unit is still active (gate-units exit 3) …`, exit 1 |

## 4. What this verification touched

- Written: only `/tmp/g3-dry-iface/**` (WSL) and `prep/verify-iface/**`, and this file.
- Read only: `$S/cand`, `~/egw-exec/repo` (`git archive HEAD`, `git cat-file commit`, `git rev-parse`,
  `git status --porcelain`), `~/egw-tcg/itest-helpers.sh`, `tunnel.sh`, `ca.crt` (copied into the benches),
  variable NAMES of `~/egw-tcg/.env` (a count; no value read out), the real venv's interpreter.
  The two `git status --porcelain` reads of the real clone moved the modification time of its `.git` directory
  (a transient `index.lock`); `.git/index` (12:49:58, before this verification), `HEAD`, the objects and the working
  tree are unchanged: HEAD `80e833f…`, 0 porcelain lines. `find -newer` over `~/egw-exec`, `~/egw-tcg`, `~/egw-images`
  and `~/yocto` shows nothing else.
- No QEMU, no `ssh`/`scp` to the guest, no real driver run: `pgrep` for `qemu-system-aarch64` answered 1 before and
  after. `~/egw-tcg/itest` holds 0 `-q1` entries, `~/egw-exec/attempts` 0 `g3-qualification` attempts, and
  `~/egw-exec/g3-battery` does not exist.
- A keepalive `exec sleep 9000` client was started from Windows for the dry run (two others were already attached).
- `open` was not run as a subcommand (it needs the whole preflight bench); its two readings of the frozen preflight
  were exercised at function level (e), and its driver calls were verified by reading and, for the close and the
  re-launch, by running the frozen scripts against stubs (a, c, d).
