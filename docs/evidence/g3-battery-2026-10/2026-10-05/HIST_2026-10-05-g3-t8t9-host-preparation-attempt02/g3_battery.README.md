# g3_battery.sh — the operator's steps script of session S3 (test 8 and test 9 only)

Authority: the request of 2026-10-04 and its decision summary
(`output_test/decisions/2026-10-04_g3-t8-t9-s3-decision-summary.md`: four choices, two conditions). The session itself
starts only on Rui's explicit authorisation and his go in the attended window («estou presente»), after the sealed
preparation package has been delivered. The authority of 2026-10-02 (S1, S2, the `-q1` identifiers) is consumed:
`open` accepts `S3` only. Procedure and tools: the merged commit `8e49261` (tree `2f05148`); the candidate (controller
image, pinned images, deployment, guest OS) is unchanged, and the script edits nothing of it. It records only through
the frozen `common.sh` / `guest_common.sh` functions and `local_export`. It kills no QEMU, deletes nothing, repeats no
row, retries no step, and never uses `ACCEPT_UNACCOUNTED`, `--force` or `local_export set run_id=…`. G3 stays
`Not decided` whatever S3 shows.

**Second opening of S3 (authorisation of 2026-10-05,
`output_test/decisions/2026-10-05_g3-s3b-exception-authorisation.md`).** This copy differs from the sealed S3 script
(`a77bd201…`) in three places only, each marked `S3, second opening` in the script: (1) the root file system expected
before the boot is `b48b010d…`, the value the first opening's close recorded; (2) the state directory is
`~/egw-exec/g3-t8t9-s3-attempt02` (the first opening's, `~/egw-exec/g3-t8t9-s3`, is kept as it is); (3) the authorised
exception for `collector-duration`: when the frozen `preflight.sh` ends exit 3, `open` checks the sha256 of
`s3b_preflight_exception.py` (beside the script) and runs it, read-only, on the preflight attempt and the driver's
console. It goes on ONLY when the checker shows the attempt identified and complete (its own DRIVER RESULT line,
exported), the fifteen other steps ended 0 with every capture complete, `collector-check` with no problem and six
services, no observed system fault and nothing skipped, and the sole failure the numeric duration judgement of
`collector-duration` on a readable, consistent report. Then it records `preflight_exception=proceeded under the
authorised T8/T9 exception …` and prints `PROCEEDED UNDER THE AUTHORISED T8/T9 EXCEPTION`; the preflight stays failed
and invalid, and the environment copy, the fresh gate, every identity check and the units' absence stay mandatory.
Anything else is the halt it always was (`HALT: preflight.sh exited 3 and the authorised exception does NOT apply`).
The checker's lines are kept in `<state>/S3-preflight-exception.txt`. The exception covers this session only.

**What the script never does (decision summary, condition B).** It never runs `compose up`, `start` or `restart`, nor
`docker start`; it never re-launches QEMU and never signals it. The one stack start of S3 is the frozen preflight
driver's, at `open`: that is the prescribed one. After the reboot of test 8 nothing on the guest is started, restarted
or recreated by hand, by the script or by the operator: between the reboot and line c it would make the containers'
return an aided one, which line c cannot detect and test 8 does not accept, and after a failed row it would be a
recovery that lets the row go on. Line d's tunnel step (`tunnel_down && tunnel_up`, on the host) and the safe-close
operations (the recorded `compose stop -t 130`, then the close driver's own stop and power-off) stay; none of them is
ever presented as unaided recovery of the containers.

## Launch (one subcommand per `wsl.exe` invocation)

`<P>` is the WSL path of the folder that holds this script (the preparation folder, `…/scratchpad/g3/s3prep`).

```bash
# short subcommands (status, classify, term), in the foreground:
MSYS_NO_PATHCONV=1 wsl -d Ubuntu-24.04 --exec bash -lc 'EGW_EXEC_REPO=$HOME/egw-exec/repo bash "<P>/g3_battery.sh" status'
# long subcommands (open, row, close), detached from the client that starts them:
MSYS_NO_PATHCONV=1 wsl -d Ubuntu-24.04 --exec bash -lc 'EGW_EXEC_REPO=$HOME/egw-exec/repo setsid bash "<P>/g3_battery.sh" row t8 > /dev/null 2>&1 < /dev/null & sleep 2'
```

- `MSYS_NO_PATHCONV=1` always (Git Bash rewrites `/home/…` otherwise); `bash -lc` (login shell).
- A detached run prints nothing to the caller: its whole console is `<state>/console/NNN-<subcommand>-<arg>.txt`
  (`status` names the latest). Follow it with `tail`, and wait for `status` to show the row
  `awaiting-classification`. `ops/g3_go.sh` and `ops/g3_wait.sh` wrap this launch and this wait. A row
  started as a plain background task would be hung up by the tool's own time limit (2 h at most) before T8's
  135 min ceiling.
- One subcommand per invocation: a row's process group must be its own (`term` signals that group).
- **One changing subcommand at a time.** `open`, `row`, `classify` and `close` each take the turn
  (`<state>/turn.env`, written under a short `flock`) and are refused (`REFUSED: another invocation of this script is
  still running: …`, exit 2, nothing started or changed) while another of them is still running. `status` and `term`
  take no turn. A turn whose holder ended is simply taken; nothing is deleted.
- **Keepalive:** before `open`, start a dedicated client and leave it running until after `close`:
  `MSYS_NO_PATHCONV=1 wsl -d Ubuntu-24.04 --exec bash -lc 'exec sleep 43200'` (a background task), and a second one as
  the request asks. `open` wants 6 h left on one of them, `row t8` 2 h 45 min (its ceiling plus 30 min), `row t9`
  55 min and `close` 30 min; the script checks the `sleep` and its WSL relay parent. Without a client the distro
  stops, and QEMU with it.
- **Keep-awake:** Windows must not sleep or hibernate for the whole session. It cannot be seen from WSL: it is the
  operator's own check before `open` and before every `row`. No other load on the host (no build, no pytest).
- Never edit the script, the row files or the manifest while a session is open: a `row` refuses a changed script.

## Subcommands

| Subcommand | What it does | Refuses (exit 2) when |
|---|---|---|
| `open S3` | Checks, each a HALT with nothing started when it fails: the clone at `8e49261`/`2f05148` and clean, `drivers_sha256`, the export tool, the runbook (`4acf8de6…`), the helper file (`e5eba37e…`, 545 lines), `tunnel.sh`, `ca.crt`, **the kernel, `qemuboot.conf`, the QEMU binary and the Yocto checkout (`489bc9e`, clean)**, the guest-state command against `nominal.sh`; the row files of t8 and t9 against `rows.manifest.json`; the five `-q2` identifiers unused on the host and no earlier attempt of either row except S2's one t8 attempt; the root file system at `22e9da85…` (the value S2's close recorded). Then the keepalive, `UP0`, and the frozen drivers `guest_session_open.sh`, `preflight.sh`, the environment copy of PM condition 2, `gate_health.sh` (its attempt is named in the state file), and one read-only listing of the guest's event directories (identifiers unused there too). | the label is not `S3` (`S1` and `S2`: "… whose authority is consumed"); a session is open; `session-S3.env` exists; a QEMU process runs or that could not be determined; the keepalive is missing |
| `row t8`, then `row t9` | One attempt (`G3 qualification <slug>`, purpose `official`): identities and a `workload` field that names the authority of S3, the step files and manifest entries copied to `environment/`, the sources registered, the gate's read before, each step as one `hx` shell that sources its file (`set -v`, carriers unset and printed), the gate after. Leaves the attempt OPEN. | the row is not t8 or t9; the session is not open; t9 before t8 is classified; the row was already started; the script or manifest changed; the session has a recorded halt (in S3 without exception); the keepalive is short |
| `classify <slug> <finished\|failed> <validity> <outcome> <reason> <next-action>` | `local_export finish`, a headline, the export (`driver_code`: prints `DRIVER RESULT`), the row marked classified. Pairs of packet §5 only: `valid/pass`, `valid/fail`, `invalid/unknown`, `valid/inconclusive`, `unknown/inconclusive`, `not-applicable/not-run`. A reason or next action given as `@FILE` is read from that file. | the row does not await classification; the pair is not one of the six |
| `term <slug>` | TERM, never KILL, to the row's recorded process group, after listing it (command lines cut at 90 columns, the value after every `--password` hidden). The row's trap finishes the attempt `interrupted` and exports it (after letting the group end by itself, 180 s at most, and one guest-state read). If a QEMU process or the keepalive client is in that group it prints `HALT:` and signals nothing. | no process of the row is left; the recorded group is the caller's own |
| `close` | No unit `egw-events-*` / `egw-resources-*` active (read-only); the recorded `docker compose --env-file .env --env-file images.lock.env stop -t 130` as step `stack-stop-130` of the session attempt; then the frozen `guest_session_close.sh`. Records the post-close root file system hash and lists the data disk's ext4 header (read-only, only with no QEMU process left). With **no QEMU process left** there is nothing to read or stop: it records a HALT, skips the unit check and the stop, and runs the frozen close driver, which finishes and exports the session attempt as it stands. | another changing subcommand is running; a row is running or awaits classification; a process is left in a row's group; a row's process died and its attempt is still open; the keepalive has less than 30 min left; no session is open |
| `status` | The session, elapsed host uptime against the 3 h cut-off, each row's state, gate, class and export, a running row's minutes against its ceiling, every recorded halt. Read-only. | — |

`row` never judges: a step's exit status is the status of its last line. The battery's rows t1 to t7 are not rows of
this script (`REFUSED: unknown row`); their entries in the script's tables are left as they were and reached by nothing.

**The ceilings (135 min for t8, 25 min for t9) are counted from the row's start** — the instant recorded as `start_up`
when `row` begins, before the attempt exists — and are shared by everything the row does: for t8 the preamble, step a,
the wait, steps b to f, the evidence reads and the gate. Nothing in the script resets `start_up` or `ceiling_min`; the
wait's 900 s are inside the 135 min, not added to them. The ceilings are recorded and shown by `status`
(`PAST ITS CEILING`); no timer enforces them: the operator does, with `term`. No row starts at or after 3 h
(`CUTOFF_S=10800`) of host uptime counted from `UP0`.

## The S3 flow, step by step

1. **Before.** The preparation package sealed and delivered; Rui's authorisation of S3 and his «estou presente»; two
   keepalive clients; Windows kept awake; no other load; no QEMU process and no open session.
2. **`open S3`** (about 7 min in S1 and S2). Ends `session S3 is open` and `Next: 'row t8'`.
3. **`row t8`.** Before the attempt, each a HALT with no attempt created: the identities again, the row files, the
   WSL boot, the cut-off, a QEMU process, the tunnel, the identifiers, and **the gate package's record of the running
   images against S2's** (`environment/container_identities.txt` of the gate attempt of this `open`: for each of the
   six containers the image reference, the image id and the repo digest must equal S2's; container ids and start
   instants are not compared). Then the attempt, which must be named `…_g3-qualification-t8_attempt02`
   (attempt01 is S2's halted one, the one earlier attempt admitted, in the WSL attempts directory and under
   `output_test/runs/2026-10-03/`); under another name the row halts before any step. Then:
   - `t8-qemu-before`: the one QEMU process recorded (pid, start instant, the `file=` of its `-drive`s) and its
     command line read for `-no-reboot` (also `--no-reboot` and `-action … reboot=shutdown`, the same setting):
     found, the row halts and **line a is not run**;
   - **step a** (`t8-a-reboot.sh`): readiness, quiet window, pre-reboot `/metrics` reading and twin snapshot, the boot
     id, the six container ids, the event directory names and the mount source saved, `sudo systemctl reboot`;
   - **the wait** (`t8-wait-ssh`, the script's own; next section);
   - `t8-qemu-after`: the SAME process and disks, or a HALT;
   - **step b** (`REBOOT SHOWN`), **step c** (`CONTAINERS RETURNED UNAIDED` **and** `PERSISTENCE SHOWN`), **step d**
     (the tunnel line, then `t8-tunnel-check` without the `hx` preamble), **step e** (readiness within 3,600 s,
     post-reboot reading and snapshot, `same`, `CONTROLLER PROCESS NEW`), **step f** (the fresh timed smoke
     `itest-post-reboot-01-q2`), each an `hx` step run only if the one before printed no `STOP:` and showed its
     marker. The runbook's carrier `T8` does not cross `hx` shells, so the script sets it for each step to the value
     the step before left (`rebooting`, `rebooted`, `returned`, `reconnected`, `ok`) and prints that it did;
   - after step f: a HALT unless the smoke's console shows, at the start of a line, the helper's
     `TEST STATUS itest-post-reboot-01-q2: … -> PROCEDURE COMPLETE` and no `STOP:`. With that line and no `STOP:`
     the script records **no** halt, whatever `lost` and `late_confirmations` read: a value above 0 is a failure of
     T8 that the operator classifies, and T9 may then run;
   - the previous boot's journal and its kernel OOM lines (evidence, read once the rebooted guest answered); the gate
     after the row: the guest state recorded and **not compared** across the reboot, six services healthy within
     900 s, no recorder or collector unit active, the tunnel.
4. **The operator reads** the consoles, the prefix files `itest-reboot-q2.*`, the smoke's files, the state recorded
   after T8 and the previous boot's OOM lines, then **`classify t8 …`** with the class of `operator-procedure.md`.
   An OOM kill found in either reading, or a restart after the reboot, is a halt of the operator's own: T9 is not run.
5. **`row t9`**, only with t8 classified, no recorded halt and T8's gate passed: its attempt must be named
   `…_g3-qualification-t9_attempt01`; steps (a), (b), (c), (d)+(e), each only if the one before printed no `STOP:`,
   then the three read-only exposure checks only if (d)+(e) printed none; its sources are registered after the row
   (a refusal leaves no directory); the gate with the guest-state comparison. An inconclusive probe is **not**
   repeated with a new tag. Then **`classify t9 …`**.
6. **`close`.** Then: every export verified (the export tool's own verification, then `sha256sum -c` in each
   package), the operator records sealed as `HIST_<UTC date>-g3-t8t9-s3-operator-records`, the result note
   `output_test/decisions/<date>_g3-t8-t9-results.md`, keepalive and keep-awake released.

### The wait before line b (decision summary, condition A)

- Budget: 900 s (`T8_SSH_WAIT_S`) on `/proc/uptime`, whole seconds, counted from the instant step a ended; one poll
  every 10 s (`T8_SSH_POLL_S`).
- Every poll is one recorded step `t8-wait-ssh` of the row's attempt and is run by the host's `timeout` for
  min(20 s, what is left of the budget): never 0, never without `timeout`. With less than 1 s left there is no
  further poll. The poll's command is the one `gx` records (`env E=<session> bash -c '<load the session's ssh helpers;
  gssh "$1">' _ 'cat /proc/sys/kernel/random/boot_id'`) with `timeout <seconds>` in front of it: `gx` itself is a shell
  function and cannot be run by `timeout`.
- A poll counts only when it ended with exit status 0 **and** its whole answer is one boot id of the kernel's form
  **and** that id is not the saved one (`~/egw-tcg/itest/itest-reboot-q2.boot_id.pre`). A poll that printed such an id
  and then ended 124 (its timeout), 255 (ssh) or any other non-zero status is said `NOT counted`, its console stays in
  the attempt, and the wait goes on. An answer with the saved id is printed and the wait goes on.
- Expiry is the HALT `reboot not shown within the wait: …`: an operational cut-off (inconclusive / not demonstrated),
  not by itself a failure of the system; line b is not run. A poll whose console capture was lost (74) is a HALT of
  its own, at once.
- Under `timeout` a poll runs in a process group of its own (coreutils `timeout` makes itself a group leader), so a
  `term t8` during the wait does not reach a poll in flight: it ends by itself within its bound (20 s at most).
- `QEMU` is never signalled and nothing is re-launched or started, whatever the wait answers; the reading
  `t8-qemu-after` is recorded in every case.

### The known host tunnel case at line d

Runbook line d (`tunnel_down && tunnel_up`) was written for a master the reboot had killed. Under `hx` the preamble
of step b or c (`tunnel_check || tunnel_up`) has already reopened the tunnel, so step d closes a LIVE master and
reopens it a few milliseconds later. If the old master has not finished exiting, `tunnel_up` can print `MASTER ANSWERS
… nothing was reopened` (status 0, and the tunnel is then down) or `STOP: host port busy`. Neither is silent: a `STOP:`
halts at step d, and the `t8-tunnel-check` step after it halts the row otherwise ("step e … and step f were NOT run").
Classify that as a tunnel event of the host (invalid instrumentation), not as an observation of the SUT. Nothing is
restored by hand to let the row go on. Not reproduced on a real ssh master.

## State files (`${EGW_G3_STATE:-~/egw-exec/g3-t8t9-s3}`; `key=value` lines, never sourced)

The battery's state directory `~/egw-exec/g3-battery` is never written.

- `session-S3.env`: label, `state` (opening, open, halted, closed, close-failed), `up0`, the WSL boot id, the session,
  preflight and gate attempts (`gate_attempt`), each driver's exit, the environment copy's hashes,
  `rootfs_before_boot`, `rootfs_after_close`, every `row_clock=` reading and every `halt=` line.
- `row-<slug>.env`: the attempt and its name (`attempt_name`), `start_up`, `ceiling_min`, `pid`/`pgid` with their
  start instants, `state` (preparing, running, gate, awaiting-classification, classified, interrupted), the current
  `step`, every `step_done=`, the `gate`, the class, the driver code and the export receipt; for t8 also `t8_run`,
  `t8_qemu_before`, `t8_wait`, `t8_ssh_answered`, `t8_qemu_after`, `t8_reached_smoke` (step f was reached) and
  `t8_smoke` (what the rule after step f found).
- `turn.env` and the empty `turn.lock`; `row-<slug>.group-after-signal.txt` (passwords hidden);
  `console/NNN-….txt` (one per invocation), `S3-<driver>.console.txt`, `S3-environment-copy.txt`, copies of the script
  and manifest as opened. Together with the classification notes these are the operator records.

No process listing reaches these files, or the caller's terminal, with a password: every listing is passed through a
mask and cut at 90 columns. The frozen export's secret scan reads attempts only, never the state directory.

## Every `HALT:` and what the operator does next

A halt before a row's steps ends the invocation there. A halt inside the steps ends the row's steps, but the
evidence reads and the gate still run, after which the row awaits classification. Nothing is closed, except at
`close` with the guest gone. Every halt is recorded in the session's state file once the session is in use. **No
further row of S3 starts after a halt** (no variable lifts this; `EGW_G3_RUI_GO` is read only by `close` for a
session closed outside the script). A tunnel that the preamble of `hx` reopens after line d (steps e and f, every
step of T9, the gate after a row) is a restoration and a halt. A row classified invalid instrumentation records a
halt too. **After any halt: classify the row if it awaits classification (class by
its cause, `operator-procedure.md`), then `close`, then hand back to Rui. Nothing is repeated and nothing is fixed.**
`REFUSED:` (exit 2) is not a halt: nothing was started or recorded.

| Where | The text begins | What it means | Next |
|---|---|---|---|
| `open`, checks | `HALT: <identity> … is …, the recorded identity is …`; `the clone … is not at …`; `… is not clean`; `the Yocto checkout … is at …`; `… (packet section 4, halt 6); nothing was started` | an identity of the request's section 2 differs | nothing ran and no state file exists; report to Rui; `open S3` is run again only on his direction |
| `open`, checks | `HALT: the row files of <slug> are not the manifest's` | a step file or the manifest changed | the same |
| `open`, checks | `HALT: an id of S3 is not fresh on the host` (the `NOT FRESH:` lines above it name the file or the attempt) | an identifier has a host artefact, or an earlier attempt that is not the admitted one exists | the same |
| `open`, checks | `HALT: the guest root file system is not the expected one` | the `.ext4` is not at `22e9da85…` | the same |
| `open`, drivers | `guest_session_open.sh exited N`; `preflight.sh exited N`; `the preflight's attempt could not be named`; `the environment copy … failed`; `gate_health.sh exited N`; `the guest's event directories could not be listed`; `an id of S3 has an event directory on the guest`; `open S3 was interrupted by a signal` | the session is used and recorded `halted` | `status`; if `current_session` exists the guest is UP: `close`; hand back |
| `row`, before the attempt | `<identity>: row <slug> was NOT started and no attempt was created`; `the row files of …`; `WSL was restarted since …`; `NOT STARTED: the 3 h cutoff`; `no qemu-system-aarch64 process could be shown`; `tunnel_check failed before row`; `an id of row … is not fresh on the host, or an earlier attempt …` | section 5, items 1, 7 or 8 of the request | `close`; hand back |
| `row t8`, before the attempt | `the gate package's record of the running images … differs from S2's …` or `… could not be read …: row t8 was NOT started` | the images the gate found running are not S2's, or the record is not there | `close`; hand back |
| `row`, attempt created | `the new attempt is named …, which does not end '_g3-qualification-t8_attempt02'` (`…t9_attempt01`) `… No step of the row was run` | an attempt of the row exists that was not accounted for | classify `not-applicable/not-run`; `close`; hand back |
| `row`, attempt created | `the attempt fields could not be recorded`; `… could not be copied into the attempt`; `a source could not be registered`; `the guest state before the row was not recorded` | no step of the row was run | classify by cause; `close`; hand back |
| any step | `step <step> answered 97` (the preamble of runbook 6.1 or the tunnel did not load: the step never ran); `step <step> answered 74` (its console capture was lost) | instrumentation | classify `invalid/unknown`; `close`; hand back |
| t8, before a | `the session's boot records are not those of a boot still running`; `the host's 'timeout' is not on PATH`; `-no-reboot (or its equivalent) is on the command line of the running QEMU process … Step a was NOT run`; `one qemu-system-aarch64 process could not be recorded before step a, or its command line could not be read` | the reboot was NOT issued | class "not started"; `close`; hand back |
| t8, a | `step a printed STOP: … the guest was NOT rebooted` | a precondition of line a | by its `STOP:` text: "not started" (not six running containers, no event directory, no mount source, the stack not ready or not quiet) or invalid instrumentation (the boot id unreadable, the reading or the snapshot failed); `close`; hand back |
| t8, the wait | `reboot not shown within the wait: …` | the guest did not answer with another boot id in 900 s | class "inconclusive / not demonstrated" (a hang is reported as an observation of the SUT). If the guest does not answer and QEMU runs: **signal nothing, power nothing off, ask Rui** (below) |
| t8, the wait | `poll N of the wait answered 74 …`; `the boot id step a saved … is not a boot id of the kernel's form` | instrumentation; line b not run | classify `invalid/unknown`; `close` if the guest answers; hand back |
| t8, after the wait | `the qemu-system-aarch64 process after the wait is not the one recorded before step a, or none could be shown` | QEMU exited, another launcher ran, or several processes | class "inconclusive / not demonstrated"; nothing is re-launched; `close` (with no QEMU left: its own path); hand back |
| t8, b | `step b does not show REBOOT SHOWN with no STOP:` | line b's own bound passed, or the answer was not a boot id | by its `STOP:` text: reboot not shown (inconclusive), or the boot id unreadable or not saved (invalid instrumentation) |
| t8, c | `step c does not show both CONTAINERS RETURNED UNAIDED and PERSISTENCE SHOWN with no STOP: - <what is missing>` | the set did not return, an event directory or the mount source is not as before, or a judged read did not end 0 | by its `STOP:` text (the table of `operator-procedure.md`); nothing is started by hand |
| t8, d | `step d printed STOP: (tunnel NOT reopened …)`; `the tunnel is not up after step d` | the host tunnel (the case above) | invalid instrumentation; `close`; hand back |
| t8, e | `step e printed STOP: …` | readiness within 3,600 s, the snapshot, `same` or `started_at` | by its `STOP:` text |
| t8, f | `step f, the post-reboot smoke …, printed STOP:`; `step f printed no STOP: but its console does not show the line 'TEST STATUS … PROCEDURE COMPLETE'` | the smoke did not complete its procedure | by cause (request, section 5 item 5); T9 is not run |
| any row | `the gate did NOT pass: …` | a service not healthy within 900 s, a unit active, the tunnel, the guest state not recorded; in T9 also an OOM kill, a restart or a replaced container | classify; `close`; hand back |
| any row | `row <slug> was interrupted by a signal` | `term`, or a lost terminal: the attempt is finished `interrupted` and exported; it is not classified again | `status`; `close`; hand back |
| `classify` | `the export FAILED`; `row <slug> is classified not started`; `row <slug> is classified invalid instrumentation` | the attempt is kept in WSL for `local_export recover`; a row not started is not attempted again; an instrumentation failure does not permit continuation (decision summary, choice 2) | `close`; hand back |
| `term` | `a qemu-system-aarch64 process is in the row's process group`; `the keepalive client … is in the row's process group` | nothing was signalled | hand back |
| `close` | `a recorder or collector unit is active (exit 3): nothing was stopped` | not expected in S3 (no row of S3 starts one) | report; the runbook's own cleanup is a restoration and a halt of its own |
| `close` | `the guest did not answer (exit 97) although a qemu-system-aarch64 process is running: … nothing was stopped` | the guest cannot be closed safely | **preserve the state, signal nothing, claim no controlled close, ask Rui** |
| `close` | `stop failed (stack-stop-130 exit N): the close driver was NOT run and QEMU is NOT forced off` | the recorded stop did not end 0 | hand back; never a forced power-off |
| `close` | `no qemu-system-aarch64 process is left …` | the guest was lost before the close: the frozen close driver alone finishes and exports the session attempt (expect its exit 5) | hand back; nothing is re-launched |
| `close` | `guest_session_close.sh exited N …`; `… current_session is kept: the session is NOT closed`; `row <slug>: its process died without its trap …`; `session S3 was not closed by this script …` | the close driver's own result, or a record made on Rui's direction | read the driver's console; hand back |

The script records only the halts it detects. A halt the operator reads from a console or from the evidence (an OOM
kill in the state after T8 or in the previous boot's kernel lines, a restart after the reboot, invalid
instrumentation of the shared chain) is honoured by not starting the next row and is written in the result note.

### A guest that does not answer while QEMU runs

During the wait of test 8, at a gate, or at `close` (exit 97 with a QEMU process running): nothing is stopped or
powered off from the host. QEMU is left running and is not signalled, the session stays open, no controlled close is
claimed, and what is done with QEMU is Rui's decision in the window (the data disk is at stake). `close` answers the
same for as long as the guest does not answer.

### A row whose process died without its trap

Its state file still says `running` (or `preparing`, `gate`), `status` says `its process … is GONE`, and its attempt is
still open in WSL. `close` refuses on it and prints the frozen line that marks and exports it
(`local_export recover … --interrupt <run id>`, with this host's paths). First fetch what the row left on the guest
(the guest's `/tmp` is lost at power-off). Then `close` again: it finds the attempt finished and exported, records the
row `interrupted` with a halt, and goes on.

### A session closed outside the script

If the frozen `guest_session_close.sh` was run by hand (or an `open` halted before any session existed), no session is
open and the state file still says `open` or `halted`: `close` answers `REFUSED: no open session … recorded 'open'`.
Only on Rui's explicit direction: `EGW_G3_RUI_GO="<his words>" … g3_battery.sh close` records the session `closed`
with a halt (his words recorded), and only if no `current_session` exists, no QEMU process runs and no row is running
or unfinished.

### Restorations

None is expected in S3, and any restoration is itself a halt (request, section 5 item 9): record, halt, hand back.
Only the runbook's own exist — a capture cleanup, `tunnel_down && tunnel_up` outside line d — and each is run by hand
through the frozen `hx` on the attempt that is open, never to let a failed row go on. **No service is started,
restarted or recreated on the guest at any point of S3** (`compose up`, `start`, `restart`, `docker start`): the
battery's restoration line for a service left stopped does not apply to S3.

## What is unverified

- **On the guest, nothing of the S3 changes has run.** The changed functions were exercised one at a time against
  stubs (`operator-notes.md`, `operator-record/`) and the whole flow in the benches (`bench-notes.md`, `bench/`), with
  stub `ssh`, `curl` and guest tools. Never run for real: the wait through the session's ssh
  under `timeout` against a rebooting guest (how ssh ends when `timeout` sends TERM to its group; how long a read
  against a guest that is going down takes); the reading of the real QEMU's command line; `git status` in the Yocto
  checkout at `open` and before each row (its duration is not measured; the frozen open driver runs the same command
  once per open); the form of the gate's record on S3's boot (S1's and S2's records have the same form).
- The `-no-reboot` reading knows three spellings of the one setting. Another way of making QEMU exit at a guest
  reboot is not looked for; `t8-qemu-after` then halts the row after the wait.
- Line c cannot tell a `docker start` of the same container objects from their own return: that nothing is started by
  hand between the reboot and line c is the operator's rule, not something the script detects.
- The tunnel case at line d is reasoned, not reproduced on a real ssh master.
- The merged lines' own assumptions (runbook Appendix B item 25): the output form of `docker ps` on the guest, the
  bounded ssh against a booting guest, the exit statuses the lines rely on, `wait_ready 3600` after a reboot.
- A hung `open` or `close` holds the turn until it ends; the script offers no way to end one (`term` is for rows).
