# g3_battery.sh / g3_battery.README.md — safety and packet-fidelity verification (2026-10-02)

Verifier's findings. Nothing was edited: not the steps script, not the row files, not the extraction script.

- Verified: `prep/g3_battery.sh` sha256 `51a1ab5e260e4703cacd810497a4dc702ef5e8be455cd442c2ea43ccde8eba70` (1,618 lines,
  `bash -n` clean, no CR), `prep/g3_battery.README.md` sha256 `fcb28f0f4586fae28c06a85742d3f853fa046f671a01b6e92c85b85a14af8cae`.
- Against: packet revision 2 (sections 3, 4, 5), `operator-procedure.md`, the PM's four conditions (register lines
  4140–4213), the frozen `tools/session/{common,guest_common,guest_session_open,guest_session_close,events_capture}.sh`,
  `guest/session_{open,close}.sh`, `local_export.py`, and the helper heredoc of the runbook (lines 610–1154), all read in `$S/cand`.
- Method: every failure path walked by reading; the suspicious ones run in isolated benches under
  `/tmp/g3-dry-safety/{a1,a2,b1,b2,b3,c1,d1,e1,f1}` (the preparation's own `dry/bench_setup.sh` and `dry/bench_run.sh`,
  copied unchanged to `prep/verify-safety/`: stub drivers, stub ssh/scp/curl/git/pgrep/ss, FAKE row files, `HOME` and every
  `EGW_*` inside the bench). My scripts are `prep/verify-safety/vs_*.sh`. The existing record
  `prep/dry/record/dryrun.console.txt` (same script hash) is cited where it already shows a path.
- Two things to disclose about my own run: (1) the first bench run (`a1`) started the bench COPY's real `egw_simulator`
  module once (cwd of `ex` is `<bench>/repo/src`); it tried `127.0.0.1:8883`, got `Connection refused` (no QEMU was running),
  published nothing and wrote only inside the bench; the test was redone with a fake module. (2) one read-only check
  `git -C ~/egw-exec/repo status --porcelain` took and released git's optional index lock (`.git` directory mtime 13:58:52;
  `index` unchanged since 12:49:58; HEAD `80e833f`, 0 porcelain lines). No QEMU, no ssh to the guest, no real driver; no file
  under `~/egw-exec/attempts`, `~/egw-tcg`, `~/egw-images`, `output_test` was created (checked after the runs).

## Verdict

Two material defects, five minor, four nits. The main line of the script is sound (list at the end). The two material
ones are small to correct and should be corrected before S1: `term` prints the simulator password, and the "a row is run
once" guard does not hold for two invocations started within a few seconds of each other.

---

## Material

### M1 — `term <slug>` prints the simulator password and keeps it in the operator records

`g3_battery.sh` lines 1446–1449:

```bash
    members=$(row_group "$ROW_FILE") \
        || refuse "no process of row $ROW_SLUG is left in its process group $pgid ..."
    say "term $ROW_SLUG: the process group $pgid (row state '$(state_get "$ROW_FILE" state)', step '$(state_get "$ROW_FILE" step)')"
    printf '%s\n' "$members" | cut -c1-200
```

`row_group` is `pgrep -g "$pgid" -a`: full command lines. The helpers' simulator line (runbook line 619) is
`SIM="python -m egw_simulator run --broker 127.0.0.1 --port $MQTT_PORT --username egw-simulator --password $MOSQUITTO_SIMULATOR_PASSWORD ..."`,
so the password starts at about column 100 of the member's line, inside the 200 characters `term` prints. `status` (line
1590), `close` (line 1494) and `wait_group` (line 1134) cut at 90 and stop just before the value.

Demonstrated (`vs_a_term_leak.sh`, bench `a2`; the fake row runs the real helper's `$SIM` against a fake module that
sleeps; the bench `.env` holds `MOSQUITTO_SIMULATOR_PASSWORD=bench-value-0000`):

```
--- the simulator stand-in's command line length before the password:
89
status holds the password: no
=== term t1-smokes
## 2026-10-02T12:43:15Z up=309 term t1-smokes: the process group 5012 (row state 'running', step 't1-smokes')
...
5539 python -m egw_simulator run --broker 127.0.0.1 --port 8883 --username egw-simulator --password bench-value-0000 --ca-cert /tmp/g3-dry-safety/a2/home/egw-tcg/ca.crt --egw-id egw-01 --output /tmp/g
TERM sent to the process group 5012 (exit 0). KILL is never sent.
--- grep of the password value in what 'term' printed:
1
--- grep of the password value in the state directory (operator records to be sealed):
egw-exec/g3-battery/console/003-term-t1-smokes.txt
```

Effect: a `term` sent while a simulator of a `run_test` row is publishing (t1-smokes, t2, t3, t4-replay's first run,
t4-reset, t5, t7-mongo, t7-ditto, t8's smoke: the moment a row past its ceiling is most likely to be in) writes
`--password <value>` to the caller's terminal and to `<state>/console/NNN-term-<slug>.txt`, which the README names as
operator records to seal into `output_test` (`HIST_<date>-g3-battery-operator-records`). That file is not an attempt
file, so the frozen export's secret scan never sees it. Packet section 3 ("never `set -x`, as the simulator password is
on its argv") and the README's own claim are defeated by another route. The harness's own command line and T9's
probes carry the value beyond column 200 (by about 20 characters for `nominal-r02`): not printed today, by margin only.

Fix: never print raw command lines. In `cmd_term` (and for the list `wait_group` writes to
`row-<slug>.group-after-signal.txt`, which holds full lines), pass the listing through a mask before any cut, for
example `sed -E 's/(--password[= ])[^ ]+/\1[REDACTED]/g'`, or cut at 90 as the three other places do.

### M2 — two `row <slug>` invocations started close together both run the row

The guard is a test followed, much later, by the write it tests for. Line 1195:

```bash
    [ ! -e "$STATE/row-$ROW_SLUG.env" ] || refuse "row $ROW_SLUG was already started ($STATE/row-$ROW_SLUG.env): a row is run once, never repeated"
```

and the file is first written at lines 1264–1266, after `keepalive_check`, `verify_candidate`, `verify_row_files`,
`tunnel_now`, `fresh_row` and `new_attempt`:

```bash
    A=$(new_attempt "G3 qualification $ROW_SLUG" official) || { A=""; halt ...; exit 1; }
    ROW_FILE=$STATE/row-$ROW_SLUG.env
    row_set slug "$ROW_SLUG"
```

There is no lock anywhere in the script. `fresh_row`'s "earlier attempt of the row" test only sees the first
invocation's attempt once `local_export new` has created it.

Demonstrated (`vs_b_double_row.sh b1 0`: two detached `row t1-smokes` started together):

```
--- how many times the row's step ran (one line per shell that sourced the row file):
2
--- attempts of the row:
egw-exec/attempts/20261002T124351Z_g3-qualification-t1-smokes_attempt01
egw-exec/attempts/20261002T124351Z_g3-qualification-t1-smokes_attempt02
## egw-exec/g3-battery/console/002-row-t1-smokes.txt
## ... row t1-smokes: attempt .../20261002T124351Z_g3-qualification-t1-smokes_attempt02 (ceiling 105 min ...)
## ... row t1-smokes: step t1-smokes (hx: one shell, the row file is sourced)
## egw-exec/g3-battery/console/003-row-t1-smokes.txt
## ... row t1-smokes: attempt .../20261002T124351Z_g3-qualification-t1-smokes_attempt01 (ceiling 105 min ...)
## ... row t1-smokes: step t1-smokes (hx: one shell, the row file is sourced)
--- state
  row t1-smokes: awaiting-classification; gate=pass; class=; driver code=; export=
    attempt /tmp/g3-dry-safety/b1/egw-exec/attempts/20261002T124351Z_g3-qualification-t1-smokes_attempt02
```

Two official attempts, the row file sourced twice, and the single state file names only the last writer (attempt01 is
left open and untracked). The bench's windows, by the delay of the second launch (benches `b4`–`b7`, `b2`, `b3`):

| Delay of the second launch | Result in the bench |
|---|---|
| 0 s, 0.05 s | the row runs twice (2 attempts) |
| 0.1 s, 0.15 s, 0.2 s | the second passes line 1195, then `NOT FRESH: an earlier attempt of row t1-smokes exists` and a `halt=` line is written to `session-S1.env` ("an id of row t1-smokes is not fresh on the host ... halt 1") while the first runs normally: a false halt that blocks every later row without `EGW_G3_RUI_GO` |
| 0.3 s, 1 s | `REFUSED: row t1-smokes was already started` (clean) |

The first window is the time `local_export new` takes; the bench's `output_test` is empty and local. On the real host
`local_export new` scans `output_test/runs` and `incomplete` on `/mnt/c` before it creates the directory; that scan,
timed read-only today, takes 3.9 s and 4.7 s (two runs). So on the real host a second launch within about 4 s of the
first runs the row twice, and one a few seconds later records the false halt.
The README's launch is detached, prints nothing and returns after `sleep 2`: a launch line issued twice is the
plausible trigger. The helpers' write-once files would most likely refuse the second simulator, but the second
official attempt, the overwritten state file (pid, pgid, attempt) and a `close` or `classify` acting on the wrong
process are a mis-run row.

Fix: take one exclusive lock for every subcommand that changes anything (`open`, `row`, `classify`, `close`), before
the first check, for example `exec 9> "$STATE/.lock"; flock -n 9 || refuse "another g3_battery.sh invocation is running"`,
and claim the row atomically (`mkdir "$STATE/row-$ROW_SLUG.claim"` or `set -o noclobber` on the row file) at the point
of line 1195. This also closes m3 below.

---

## Minor

### m1 — with the guest gone, `close` can never complete, prints a wrong instruction, and S2 can then never open

`cmd_close` lines 1509–1514 and 1517–1523: the read-only unit check and the recorded stop both go through `gx`; with no
guest they answer 97, and each is a halt before the frozen close driver:

```bash
    if [ "$rc" -ne 0 ]; then
        halt "close: a recorder or collector unit is active, or the units could not be read (exit $rc: 3 active, 97 the guest did not answer): nothing was stopped. The runbook's own cleanup is the operator's decision; then 'close' again"
        exit 1
```

Demonstrated (`vs_d_guest_lost_close.sh`, bench `d1`: QEMU gone after the open, packet section 4 halt 6):

```
HALT: no qemu-system-aarch64 process could be shown (pgrep exit 1 ...): the guest is lost; row t1-smokes was NOT started (packet section 4, halt 6)
=== close (call 1)
HALT: close: a recorder or collector unit is active, or the units could not be read (exit 97: ...): nothing was stopped. The runbook's own cleanup is the operator's decision; then 'close' again
=== close (call 2)
HALT: close: ... (exit 97 ...) ... then 'close' again
session S1: state=open ...
session attempt: running; exported: 0
```

The same is in the preparation's own record for T8 with a failed re-launch (`dryrun.console.txt`, bench 4: the first
QEMU exited, the re-launch ended 1, then `close` → the same HALT with exit 97, `session S2: state=open`). So in the
cases of packet halt 5 (re-launch STOP) and halt 6 (guest lost) "close again" loops for ever: the session attempt stays
`running` and unexported, `rootfs_after_close` is never recorded, and nothing printed names what does export it, the
frozen `guest_session_close.sh`, which handles a guest that is off (its three steps fail, it finds no QEMU, removes
`current_session`, finishes and exports the session: exit 5).

And once that driver is run by hand, the state cannot be reconciled (`vs_d2_after_hand_close.sh`):

```
=== close
REFUSED: no open session
session S1: state=open ...
=== open S2 with Rui's go            (EGW_G3_RUI_GO set)
REFUSED: session S1 is recorded 'open', not closed (.../session-S1.env)
```

Lines 720–725 refuse on any session not `closed` and `EGW_G3_RUI_GO` does not lift that; the same holds after an
`open` whose boot failed (`state=halted`, no session left, `close` refuses "no open session"). "Until Rui directs
otherwise" then needs a hand edit of the state file.

Fix: in `cmd_close`, read `qemu_procs` first. With no QEMU process: say that there is nothing to stop, record
`stack_stop_130_exit` as not run, and go to the frozen close driver (it exports the session), then mark the session
closed with a halt. With a QEMU process that does not answer (97): halt and hand back with a text that says so, not
"close again". Let a session whose `current_session` is gone and whose QEMU is gone be marked closed-by-hand under
`EGW_G3_RUI_GO`.

### m2 — `close` powers the guest off over a row attempt that is still open

Packet section 4, safe close: "no row or poller running, no recorder or collector unit active, the open attempt
finished and exported as it stands; **then** a recorded stop". Lines 1496–1500 enforce it only for
`awaiting-classification`; any other state with a dead process is a warning and the close goes on:

```bash
            *) echo "WARNING: row $slug is recorded '$st' and its process is gone: its attempt is still open in WSL (the frozen 'local_export recover --interrupt <run id>' marks and exports it)" ;;
```

Demonstrated (`vs_c_dead_row_close.sh`, bench `c1`: the row's group killed from outside, as a crash would):

```
attempt status before the close: running unknown; export receipt:
=== close      exit=0
WARNING: row t1-smokes is recorded 'running' and its process is gone: its attempt is still open in WSL ...
bench docker compose stub: compose --env-file .env --env-file images.lock.env stop -t 130
## ... guest_session_close.sh (frozen driver ...)
## ... session S1 closed (guest_session_close.sh exit 0)
attempt status after the close: running unknown; exported package: 0
session S1: state=closed ...
  row t1-smokes: running; ... its process (pid 12490) is GONE and the attempt was not closed by this script
```

The attempt's own files survive in WSL, but that row's unfetched guest files in `/tmp` (collector CSV, recorder
directory) are lost with the power-off, and the session is recorded `closed` with a row neither classified nor
interrupted. Fix: refuse (exit 2) and print the recover line, or finish the attempt `interrupted` and export it there
(the `driver_interrupt` behaviour), before the stop.

### m3 — `close` is not refused while `open` is still running

`cmd_close` (lines 1485–1501) checks the rows only; it never reads the session's `state`, and `open` records no pid.
Demonstrated (`vs_f_close_during_open.sh`, bench `f1`, stub preflight waiting 25 s):

```
session file while the open runs: state=opening session_attempt=.../20261002T125130Z_guest-session_attempt01
close exit=0
bench docker compose stub: ... stop -t 130
## ... session S1 closed (guest_session_close.sh exit 0)
--- what the open printed after the close took the guest away:
DRIVER RESULT 20261002T125154Z_live-preflight_attempt01: exit=0 ...
## environment input (PM condition 2 of 2026-10-01)        <- the harness input was still replaced
STOP: no open session
HALT: gate_health.sh exited 2; ...
session S1: state=halted ...
```

A `close` issued by mistake while the detached `open` (which prints nothing) is in its preflight stops the stack and
powers the guest off under it. Fix: the lock of M2, or refuse a `close` while the state is `opening`.

### m4 — README restorations: `$DC` is wrong in either quoting, and the bare cleanup loses the recorder's capture

README lines 89–91: restorations are "recorded with the frozen `hx` ...: `bash "$EGW_CLONE/tools/session/events_capture.sh"
cleanup <id>` until 0 (three tries at most), `ssh egw-tcg "$DC start <service>"`, `tunnel_down && tunnel_up`".

(a) `$EGW_CLONE` exists only inside `hx` (single quotes), where `DC` does not exist; in the operator's shell (double
quotes) `DC` is `guest_common.sh`'s, without the `cd /opt/egw/deployment`, and `EGW_CLONE` is empty. Demonstrated
(`vs_h_readme_restoration.sh`, `echo` in front of `ssh`):

```
operator shell after sourcing the drivers: DC=[docker compose --env-file .env --env-file images.lock.env] EGW_CLONE=[<unset>]
--- single-quoted (expanded inside hx):
ssh egw-tcg  start mongodb
inside hx: DC=[<unset>] EGW_CLONE=[/tmp/g3-dry-safety/e1/repo]
--- double-quoted (expanded by the operator's shell):
ssh egw-tcg docker compose --env-file .env --env-file images.lock.env start mongodb
bash /tools/session/events_capture.sh cleanup some-id
```

The first sends `start mongodb` to the guest; the second runs compose outside `/opt/egw/deployment`. Test 7's own
STOP names the right line: `ssh egw-tcg "cd /opt/egw/deployment && docker compose --env-file .env --env-file images.lock.env start <service>"`.

(b) `events_capture.sh cleanup RUN_ID` without `KEEP_DIR` stops the unit and copies nothing (frozen header: "with
KEEP_DIR it then copies what the recorder captured there"; the guest text says "its capture stays in $D"). After a
`term` on t1-harness, t6, t7-mongo or t7-ditto the step's shell is dead, no `events_stop`/`events_cleanup` ran, so the
README's bare line makes the unit inactive, `close`'s unit check then passes, and `/tmp/egw-events-<id>` is lost at
power-off (packet section 4: "Fetches and cleanups run before any close, as the guest's `/tmp` is lost at power-off").
The runbook's own form is the helper `events_cleanup <id> <records dir>`, which passes `$P/<id>.sut/events-partial`.

(c) The operator procedure's fourth restoration, the harness's collector stop (`ssh egw-tcg 'sudo systemctl stop
egw-resources-<run_id>'`), is missing from the README, although `close` halts on an active `egw-resources-*` unit.

Fix: write the three lines out in full in the README, as `hx "$A" <name> '<text>'` with single quotes:
the spelt-out compose `start`; `events_cleanup <id> "$P/<id>.sut"` (itest rows) or
`events_cleanup <id> ~/egw-tcg/pilot/results/raw/<id>/logs/sut` (harness rows); the collector stop.

### m5 — `close` does not check the keepalive

`keepalive_check` is called at lines 775 (`open`, 6 h) and 1221 (`row`, ceiling + 30 min) only. `close` runs a stop of
up to 130 s per service and a power-off with no check that the distro will outlive them; if the client ends during
them, WSL stops with QEMU up and the data disk mounted. The packet asks for the check before every row only, and the
README's 12 h client covers a session, so this is a gap in a guard, not a breach. Fix: `keepalive_check 1800` (or
similar) at the start of `cmd_close`, as a refusal.

---

## Nits

- **n1 — README vs script on `term`.** README line 40 lists "QEMU or the keepalive is in that group" under "Refuses
  (exit 2)"; the script prints `HALT:` and exits 1 (lines 1451–1452, 1461–1462), and that HALT is not written to the
  session file (`cmd_term` never sets `SESSION_FILE`). README line 71 ("records the line in the session's state file")
  is likewise not true for the HALTs of `open`'s checks before the state file exists (lines 752–773), which is the
  intended behaviour but not what the sentence says.
- **n2 — the label check reads two of the three labels.** `environment_copy` (line 670) tests `QEMU`, `TCG` and
  `ARM64 EMULATED`; the PM's condition 2 names the shared-x86-host label too (`shared_vcpu_note`), which is printed
  but not tested. The operator procedure asks for the two, so the script matches it.
- **n3 — `on_signal` says "exported" whatever the export did.** Line 1168 prints "attempt finished 'interrupted' and
  exported (driver code $rc)" also when `rc` is 4 (export failed). The code and the receipt are recorded correctly.
- **n4 — packet section 1, data disk.** "ext4 header listed before each boot and after each close": the frozen close
  lists `ls -l` of the data disk only, and `close` adds nothing. Outside sections 3–5; S2's open lists the header
  before its boot, so only the state after S2's close is not listed.

---

## What was walked and holds

- **QEMU is never signalled.** The only `kill` that signals is line 1468 (`kill -TERM -- "-$pgid"`); `term` refuses
  another WSL boot, a reused group number (leader start instant), its own group, and a group holding a
  `qemu-system-aarch64` or the keepalive. Both boots are started by the frozen `session_open.sh` with `setsid nohup`,
  so QEMU is never in a row's group. T8's wait only reads; `wait_group` signals nothing. No `rm`, `pkill`, `poweroff`
  or `reboot` in the script (the reboot is the runbook's own line in `t8-a-reboot.sh`).
- **No retry, repeat, new id, `ACCEPT_UNACCOUNTED`, `--force`, `set run_id`.** `ACCEPT_UNACCOUNTED` appears only in
  the `unset`; a step is run once; `row` refuses an existing row file and halts on an earlier attempt of the row in
  `attempts`, `runs` or `incomplete`; a halted `open` cannot be opened again. `egw_experiments plan` without `--force`
  refuses the existing plan (cli.py line 759).
- **3 h cutoff.** `UP0` is whole seconds of `/proc/uptime`, read once at `open` before the boot (lines 779–780), kept in
  the session file with the WSL boot id; `row` halts on another boot id, records every `row_clock`, and does not start
  at `elapsed >= 10800` even with `EGW_G3_RUI_GO` (the check comes after the override).
- **Environment copy.** Old file kept as `sut_environment.json.<sha12>` (never overwritten: an existing different file
  is a STOP), capture copied and compared, both hashes and the source package recorded; a capture without the labels
  halts before `gate_health.sh` (bench `a2`; record, bench 6).
- **Stop before close.** Units check, then `stack-stop-130` with both env files as a step of the session attempt, exit
  recorded; any non-zero exit halts before the close driver (record, bench 2: "HALT: stop failed ... the close driver
  was NOT run").
- **T7 on TERM.** The fault job writes to its own file, not to the step's pipe, so its trap survives the death of
  `local_export exec` and restores the service; `on_signal` waits up to 180 s for it, signals nothing, records a halt
  that tells the operator to check services and units (record, bench 1).
- **T8.** Refuses boot records that are not a first boot; after step a, relaunches only when `pgrep` answers 1, the
  first boot's status file exists and ports 2222/8883 are free, else halts after 600 s without signalling; `ex` (no
  ssh) for the wait and the re-launch; no reference to the data disk in the script; step d only after `REBOOT SHOWN`
  with no `STOP:` (the `set -v` echo of the source line cannot match the pattern).
- **Purposes.** `official` only in `new_attempt "G3 qualification $ROW_SLUG" official`; the script creates no other
  attempt.
- **`set -x`.** Absent from the script and the README; `set -v` echoes source lines before expansion, and the helper's
  `$SIM` is expanded inside a function, never echoed.
- **INT/TERM.** Bench `a2`: `row t1-smokes: interrupted; ... driver code=130; export=verified; incomplete`, halt
  recorded. By reading (not run): `on_signal` ignores INT/TERM/HUP first, and what it starts afterwards inherits the
  ignored signals, so a second `term` should not break the export.
- **S2 rows in S1.** `row` needs `session-<own label>.env` in state `open` naming the current session.
- **State directory.** A refused row (exit 2) and a row halted before its attempt leave no row file; `classify` needs
  `awaiting-classification`; an interrupted row is never `classified`; "not started" records a halt. The exception is
  the concurrent case of M2.
- **README detached launch.** A row started with the README's `setsid ... & sleep 2` from its own `wsl.exe` invocation
  was still running when read from another invocation 15 s later (bench `e1`).
