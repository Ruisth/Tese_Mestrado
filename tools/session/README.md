# Session drivers — guest sessions and bounded checks, exported as they run

These bash drivers run the bounded checks of the project-management work order
of 2026-09-19 (section 2.C) on the integrated QEMU/TCG gateway, and export every
attempt, at completion and on failure, to the local `output_test` folder
([`docs/setup/local_test_outputs.md`](../../docs/setup/local_test_outputs.md)).
They run on the WSL2 host, from a **clean clone** at an identified commit: the
clone that holds this folder is the `REPO` whose commit every attempt records.

| Driver | Does | Attempt it exports |
|---|---|---|
| `export_checks.sh` | one passing and one deliberately failing test, to check the export | two host-only attempts |
| `backfill.sh` | the historical capsules copied on 2026-09-19 (a record of that run; workstation paths) | one `HIST_...` package each |
| `guest_session_open.sh` | records the OS, launcher, QEMU, clone and image identities, boots the guest with `guest/`, records its state | `guest session` (open until closed) |
| `preflight.sh` | runbook 5.5 interlock and `up -d`, installs the clone's collector, compares the deployed tree with the clone, health, OOM, storage, clocks, broker secrets, SUT environment with the emulation label, then a 45 s collector run with the six expected services, fetched with the repository's `fetch-collector-output.sh` (every mandatory file verified against the guest's own sha256) and checked | `live preflight` |
| `gate_health.sh` | the G2 gate's precondition snapshot, and nothing else (it starts, changes and publishes nothing): the six services **running and healthy**, `/health` 200 with `{"status":"ok"}` and `/ready` 200, every `/metrics` counter and `queue_depth` 0 for an identified controller process, the six container identities with the controller build identity, and the publishing path's TLS material as configuration | `G2 gate preconditions` |
| `slice.sh RUN SEED` | runbook 6.2-6.4: one smartwatch at 1 Hz for 60 s, isolated run id and unused seed, identity reconciliation, twin read-back, `check` and `delta` | `smartwatch slice 1 Hz 60 s` |
| `persistence.sh RUN` | runbook 6.5 on the run the slice produced: quiesce, the state before, `compose down` then `up -d` with the volumes preserved, the restart **shown**, ready and healthy again, the `post-restart` snapshot, `same`, and an independent twin read — with nothing published between the two snapshots | `G2 twin persistence restart` |
| `broker_measure.sh` | the broker-hold measurement of ADR 0011, condition C3 (`tools/probe/README.md`): the stack **stopped**, a throwaway pinned broker on its own volume with measurement copies of the configuration (W = 4,999, Q = 1,000, expiry 1 h), the phases P0–P8 with the probe's own client ids, every record kept, the probe removed, the stack **started** and waited for, the verdict of S1–S5 / R1–R6 applied by `broker_hold.py`; an engineering diagnostic, not a G3 run, and its values are probe settings | `broker hold measurement (C3)` |
| `nominal.sh RUN_ID` | the pilot plan's nominal entry (120 s warm-up, 600 s measured) through `harness_run`, between two records of the guest's container state, then the drain, the post-drain and warm-up event logs, snapshots and an identity accounting (`nominal_account.py`) | `nominal instrumentation 120+600` |
| `guest_session_close.sh` | stops the stack **before** power-off (runbook 3.3), keeps the journal and final state, powers off, checks the G1 artefacts of the sealed **non-integrated** build (`src/yocto/build`, which is what the G1 reference lists) | closes and exports `guest session` |

Each attempt reports instrumentation validity and system outcome separately: a
valid run in which messages were late or lost is a system failure, not invalid
evidence. `regen_helpers.py` regenerates `~/egw-tcg/itest-helpers.sh` from the
runbook's section 6.1 heredoc, keeping the previous file beside it.

The G2 closure session (work order of 2026-09-20, section 4) is one sitting:
`guest_session_open.sh` → `preflight.sh` → `gate_health.sh` →
`slice.sh <fresh run id> <unused seed>` → `persistence.sh <that run id>` →
`guest_session_close.sh`.

**The `running and healthy` wait is written once.** The engineering preflight
passes with a health check that has not concluded, because there a container is
judged by its state alone; G2 requires all six services `running` **and**
`healthy`. That stricter wait lives in `guest_common.sh` as
`healthy_wait_script` / `healthy_wait`, and `gate_health.sh` and
`persistence.sh` both call it, so the gate and the check after the restart can
never drift apart. It polls about every `EGW_HEALTH_STEP_S` seconds until
`EGW_HEALTH_LIMIT_S` has passed and prints **every** sample with its instant, so
a transition (`starting` → `healthy`) is visible in the console record rather
than only its result. Its answer is one of four, and the two that are not a
pass are never mixed: `0` all six running and healthy, `1` the limit passed and
at least one of them was not (the system's own state: `valid` + `fail`, exit 1),
`2` the state of at least one of them could **not be determined at all** (an
inspect that failed for any other reason, a health field that could not be read:
invalid instrumentation, exit 3) and `4` both, where each is recorded in its own
group. Only the daemon's own `No such object` is a container that is gone; of
the health field, `starting`, `unhealthy` and `none` are all simply not
`healthy` here, are polled again and are recorded as the word they are.

**Observing the system fail is a result; failing to observe is an invalid
measurement.** A positively observed fault — a container OOM-killed, restarted,
replaced or gone, a service that is not healthy, a memory-cgroup OOM line, a
drain that never went quiet — makes the **system outcome** `fail`, and the
instrumentation stays as valid as the evidence itself says: that is a valid
negative result (exit 1), which is exactly the observation the dissertation has
to analyse. Such a fault makes the measurement **invalid** only when it breaks
a stated evidence requirement, and then the reason names the requirement, not
the fault: the harness manifest does not call the run valid, the clock domain
the 60 s confirmation deadline rests on is not intact (`controller_marker.ok`
false, or `confirmation_deadline_source` other than `controller-marker`),
mandatory evidence is missing or unreadable, or a console capture was lost. The
observed fault is then kept as a fact beside that invalidity and never turned
into a successful system outcome. Each driver therefore sorts what it finds
into three groups — **observed** (what the system did: the outcome fails),
**mandatory** (evidence missing, unreadable or below a requirement: the
instrumentation is invalid) and **incomplete** (an observation after the sealed
measured window that could not be made: recorded, and the window's own validity
untouched) — and the reason keeps them distinct, in that order. A post-window
drain that does not complete is `incomplete`, never `mandatory`, and is
`observed` as well only when the drain itself **gave up**: the `STOP: drained:
no quiet window of … s within … s` its console record carries. That step
reaches the controller through the tunnel, so its status alone observes nothing
about the queue — a tunnel that dropped, a refused connection, a guest that is
not answering, and the helper's other stop (a `/metrics` that is unreachable or
not JSON, or a response missing one of the thirteen fields `drained` reads or
carrying one of the wrong type) leave the tail simply unobserved. Either way the
measured verdict stands and nothing claims eventual delivery or a complete tail.
`drained` (runbook 6.1, under ADR 0011) reads `queue_depth`, `in_progress`,
`unacked`, `mqtt_subscribed`, `started_at`, `mqtt_connection`, `received`, the
four outcome counters, `dropped` and `processing_errors` from each `/metrics`
response; a reading is quiet only when `queue_depth`, `in_progress` and
`unacked` are 0, `mqtt_subscribed` is true and the accounting identity of
`src/CONTRACTS.md` section 5 holds in that same response, and its window closes
only when `started_at`, `mqtt_connection`, `received` and the six counters
stayed unchanged through it. A reading that is not quiet, or whose identity
fails, opens a new window and is not a stop; the window, the thresholds and
both prefixes are unchanged.

Two rules hold the three groups apart. **A clean pass needs complete
evidence**: while anything is `incomplete` the outcome cannot be `pass`, so it
becomes `inconclusive` (3) when the delivery row would otherwise pass and stays
`fail` (1) when the system failed — and no verdict is ever derived from the
output of a step that failed, so an accounting that did not complete leaves the
delivery row and the clock domain unread and says so. **A fault that was
positively observed is never erased by something else being indeterminate**:
both are recorded, each in its own group. `guest_state_delta.py` prints its
faults whatever its exit status is (0 nothing to report, 1 a fault observed, 2
the records could not be compared, and 2 as well when the comparison itself
failed — never the 1 Python leaves for an unhandled exception), ends every exit
with the summary line `guest-state-delta: faults=N problems=M`, and the driver
reads no verdict from a status that line does not carry and agree with: what a
comparison that crashed left behind is a pair that could not be compared,
mandatory evidence missing, and never a fault nobody observed. The driver keeps
a fault the comparison printed beside the part of it that could not be
completed; an `unknown` field is the opposite case and is a problem, never an
observation. `stack-health` in `preflight.sh` ends 3 for a stack it saw
failing, 1 for a state it could not determine and 4 for both, where the
prerequisite verdict stays what it is and the fault is recorded all the same. A
service container the daemon itself answers `No such object` for is a fault (it
answered: the container is gone), while an inspect that failed for any other
reason, or did not answer, determines nothing about that container. Of the
health field only `unhealthy` is a fault: the state must be `running`, and
`starting` (a healthcheck that has not concluded) and `none` (no healthcheck
declared) are judged by that state alone and recorded as the word they are —
readiness is the `/ready` gate of `controller-health`, not this step. An
observation that stops the steps after it says so in the reason, and never that
the preflight's own evidence is complete.

The drivers call five helpers of their own, all hashed into every attempt's
`drivers_sha256` and copied into the session's `scripts/drivers/`:
`driver_status.py` (the exit statuses), `deployed_vs_clone.py` (the deployed
tree against the clean clone, in both directions),
`junit_one_failure.py` (the deliberate failure's own report),
`collector_shortfall.py` (how far a live collection fell short of the
`duration=` the collector's own `start:` line declares, which only the driver
that started it judges) and
`guest_state_delta.py` (the guest's containers before and after a measured
run, as a pair and in both directions: a container that was OOM-killed, one
that restarted — by its restart count, or by the instant it last started, which
is the only trace an in-place `docker restart` leaves, since Docker increments
`RestartCount` from the restart policy — one that is gone after the run, one
that was replaced — a recreated container object carries a new id and starts
again at restart count 0, so the OOM and restart history goes with the old
object — are the **faults** it reports, while a record that names a container
twice or without its id and start instant, and a *before* record that does not
name every expected service, are the **problems** that leave the pair
uncomparable; an expected service the *before* record does not name is a gap in
that service's baseline and never also a fault about it, while one the *after*
record names and nobody expected is a container that appeared during the run;
in the *after* record that same silence is the fault "gone after
the run", unless that record names no container at all — one nobody could read
shows nothing, and no container is reported gone out of it); `collector_check.py`
and `nominal_account.py` belong to the collector and the accounting, the second
of which is told by the driver whether the post-drain log was fetched, because
a transfer that died mid-way leaves a file that is not a complete tail.

Every attempt records the identity of the clean clone (`repo_identity` in
`common.sh`): the commit, how many lines are dirty, the export tool's sha256
and the sha256 of every driver file. When git cannot read the clone — a
worktree whose `.git` points elsewhere, "detected dubious ownership" — the
identity is recorded as `repo_commit: null`, `repo_dirty_lines: null` and an
`identity_error`, and the driver stops with 2: an identity that was not read is
never written down as a clean clone at no commit.

## Exit statuses

Every driver ends through `driver_status.py`, which is the **one** place where
the table below is applied: no driver invents a code, and no driver turns a
failure into a successful message. Three helpers of `common.sh` reach it:

- `driver_exit` exports the attempt and exits with the code derived from
  `attempt.json`, the export result and the session-close flag. Every driver
  that owns one attempt ends here.
- `driver_code` does the same but *returns* the code instead of exiting, for
  `export_checks.sh`, which judges two attempts and keeps the most serious in
  the precedence order below, not the larger number (2 outranks 3). The
  deliberately failing check's own derived code is 1 (a valid negative result:
  a failed test, exported and verified as failed), which is that check
  behaving as intended and is therefore not the driver's own code.
- `driver_stop CODE REASON` is for an end **before an attempt exists** (a
  prerequisite of the attempt itself: no open session, a missing argument, no
  seed, a raw directory already there, a session or QEMU already running, an
  attempt that could not be created) and for `backfill.sh`, which owns no
  attempt. It prints the same final line with `DRIVER RESULT none`,
  `status=no-attempt` and the three verdicts unknown, so a caller that parses
  that line is never left with nothing to read. `guest_session_open.sh` also
  ends this way, with 3, when the guest is up and a verdict it established
  could not be written to the attempt: the code is then not derived from an
  `attempt.json` that does not carry it, and the reason names the session,
  which stays open for `guest_session_close.sh`.

| Code | Meaning |
|---|---|
| 0 | ran; instrumentation valid (or not applicable); system outcome pass; package exported and verified |
| 1 | valid negative result: ran; instrumentation valid; package exported and verified; system outcome fail |
| 2 | a prerequisite failed: the test did not run (outcome `not-run`), or no attempt could be created |
| 3 | instrumentation invalid, outcome inconclusive/unknown, a mandatory step (capture, fetch, hash, check) failed, or `capture_failures` is non-empty |
| 4 | the local export failed: no verified package in `output_test` (the attempt is kept in WSL; `local_export recover`) |
| 5 | the controlled stop or power-off failed (session close only) |
| 130 | interrupted (INT/TERM): marked interrupted and exported |

When several apply the most serious is returned: **4 > 130 > 5 > 2 > 3 > 1 > 0**.
Each driver prints one final line naming the code, its meaning, the run id and
the three verdicts, for example

```
DRIVER RESULT 20260919T203411Z_live-preflight_attempt01: exit=3 (instrumentation invalid, ...) status=failed instrumentation_validity=invalid system_outcome=inconclusive export=exported
DRIVER RESULT none: exit=2 (a prerequisite failed: the test did not run) status=no-attempt instrumentation_validity=unknown system_outcome=unknown export=none (no open session)
```

An attempt left open on purpose (`export=deferred`, `guest_session_open.sh`)
has recorded no outcome and holds no package, so its line says what it is
instead of the words of a finished run:

```
DRIVER RESULT 20260919T234655Z_guest-session_attempt02: exit=0 (ran; instrumentation valid (or not applicable); the guest session stays OPEN and is exported by guest_session_close.sh) status=running instrumentation_validity=unknown system_outcome=unknown export=deferred
```

`export_checks.sh` prints one such line per attempt (two), followed by its own
`EXPORT CHECKS: exit=...` summary.

The export tool exits 0 for a package it finalised and sealed **without** part
of the evidence the attempt registered — a source root it refused to read
through a link, a declared artefact that was never written, a destination index
that could not be rebuilt — and names that in one field of the attempt's
`export/receipt.json`, `package_state`. `driver_status.py` reads that field
beside `attempt.json`, so **0 and 1 are never printed for a package that is not
`verified`**: such a run ends 3 and its final line carries
`package=INCOMPLETE (...)` instead of "package exported and verified". A
receipt that cannot be read, or that does not carry the field, leaves the
package's state unknown, which is not "verified" either.

A step run through `local_export exec` returns **74** when the command itself
ran but its mandatory console capture failed (the command's own exit code is
kept in `commands.jsonl`). Every driver treats 74 as its own case: the recorded
reason names the capture, never the step, and a prerequisite whose capture was
lost leaves the outcome `inconclusive` (code 3, because `capture_failures` is
not empty), never `not-run`.

A step run through one of the wrappers of `guest_common.sh` (`gx`, `gcp`, `hx`)
answers **97** (`EXIT_NOT_REACHED`, `common.sh`) when it **never reached what
it was to run**: the session's ssh helpers could not be loaded, `ssh` itself
could not connect (its own 255), or the host preamble of runbook 6.1 failed.
The step's command never ran there, so nothing it would have observed was
observed: a driver records "the guest did not answer" (invalid instrumentation)
and never reads a fault out of it. That is what tells a guest that did not
answer from a guest that answered something the gate does not accept — the two
used to arrive as the same status 1.

An attempt may also carry a **`headline`**: one sentence, written by the
driver, naming what the operator has to act on. Two runs can derive the same
code and call for different actions — a controller stuck `starting` and a
controller that was never reached are both non-zero — so `driver_status.py`
prints that sentence, quoted, at the end of the final line. It never changes
the derived code.

**Zero never authorises a dependent test by itself.** A diagnostic command can
exit 0 with `system_outcome=fail`, so the caller reads the verdicts on that
line (or in `attempt.json`) before starting anything that depends on the
result.

### Which step is which

A **prerequisite** decides whether the check can run at all: when one fails the
attempt is closed with outcome `not-run`, the steps that depend on it are
skipped and named as not run, and the driver exits 2. A **mandatory** step is
part of the evidence: when one fails the attempt stays `invalid` and the driver
exits 3, and the remaining steps still record what can be observed. An
**informational** step never changes the verdict.

A step that positively **observes** the system is none of those three: when it
sees a fault, the evidence is sound and it is the *system outcome* that fails
(`valid` + `fail`, exit 1), while the steps that depended on a healthy system
are still skipped — which the reason says, rather than calling that record
complete — and the driver still ends non-zero. A step after the sealed
measured window whose observation could not be made is **incomplete**: it is
recorded, in the reason and in `post_window_observations`, and changes neither
verdict of that window.

| Driver | Observed (system outcome `fail`, exit 1) | Incomplete (recorded, no verdict changed) |
|---|---|---|
| `preflight.sh` | `stack-health` exit 3: a service not running, one reported `unhealthy` or one not there at all, a container OOM-killed, or a memory-cgroup OOM line in this boot (`starting` and `none` are judged by the state alone); exit 4 records the same fault beside a state it could not determine, whose prerequisite verdict stands. The reason names the steps that were then not run | — |
| `nominal.sh` | the faults `guest_state_delta.py` printed (a container OOM-killed, restarted — by its count or by the instant it last started — replaced, gone, or a memory-cgroup OOM line), whether it could complete the comparison (exit 1) or not (exit 2, where the comparison is `mandatory` as well), and a `post-drain` whose own record says it gave up without a quiet window | the `post-drain`, `fetch-post-drain-events`, `fetch-warmup-events`, `after-snapshots`, `identity-accounting`, and a delivery row that was not read or does not carry `sent_valid`, `delivered_unique`, `lost` and `late_confirmations` as whole numbers (the outcome is then `inconclusive`, unless a fault was observed: a failure is not lowered to undecided) |
| `guest_session_close.sh` | `oom-before-poweroff` exit 3: the kernel reports memory-cgroup OOM line(s) in this boot | — |
| `gate_health.sh` | a service that did not reach `running` and `healthy` within the limit (the shared wait's exit 1), `/health` or `/ready` **answering** anything other than 200 with `{"status":"ok"}` (a 503 is the system's answer), a `/metrics` counter or `queue_depth` that is not 0, and a broker whose configuration is not TLS with anonymous access refused. Each names the service, the code or the counter, and the reason names the **first** thing that was not as G2 requires, which is also the `headline` on the final line. A request that never reached the controller is not one of these: curl prints the code `000` and writes an empty body for its own 7 or 28, so each of the three readings keeps curl's status beside the code and a reading that was not made is invalid (3), never "the controller answered 000" | — |
| `persistence.sh` | a `ready-again` whose own record carries `wait_ready`'s give-up (`STOP: wait_ready: /ready answered …, not 200, for … s`) and a stack that did not come back `healthy` — the steps after either are then not run, which the reason says — `$REC same` reporting DIFFERENT, a twin the API answers **404** for after the restart (the volume did not hold it) or one that comes back without the state this run stored in it, and a stored state that did not come back unchanged (`stored-state` exit 1). A `ready-again` that ended any other way (a preamble that failed, a transport that dropped) reported nothing about `/ready`, and a twin that could not be READ at all (the API not reached, another code, a body that is not JSON) is a reading that was not made: both are invalid (3), never the stack failing to come back or the state failing to survive | — |

| Driver | Prerequisites | Mandatory | Informational |
|---|---|---|---|
| `export_checks.sh` | the two attempts can be created, the clone's identity is readable **and recorded in the attempt** (outcome `not-run`, 2) | both checks judged on what they produced: the passing one needs pytest's own code 0 **and** a JUnit report in which at least one case was EXECUTED — collected less skipped less errors, because pytest also exits 0 when every case it collected was skipped (1 when the module fails with pytest's code 1; any other code, or nothing executed, means nothing was checked — invalid, 3), the deliberate failure needs the test file written, exactly one failed test in the report (`junit_one_failure.py`) and pytest's own code 1; both packages export (4 otherwise) | — |
| `backfill.sh` | — | every capsule reaches `output_test` as a verified package (4 otherwise) | — |
| `guest_session_open.sh` | no session open, no `qemu-system-aarch64` running, the attempt, its fields and the clone's identity, the record of the open session in `$EXEC/current_session` (written and read back **before** the boot), the session's own directories and the guest scripts copied into it, the driver copies kept with the session, the identities read before the boot (every artefact, binary and checkout it names, not only the last one read), the boot | the guest state after the boot (recorded on the still-open attempt as invalid instrumentation), every command that record is made of — `systemctl is-system-running`, `docker ps -a` (the six-container stack is what the session is for) and `df` — not only the `dmesg` that ends it, and the writing of each of those verdicts, and of the qemu pid, on the attempt: a `local_export set` that failed leaves the record saying nothing, so the driver ends 3 and names what is missing instead of deriving 0 from an `attempt.json` that never received it | the venv freeze, `uptime`, `free`, the journal grep, `timedatectl` |
| `preflight.sh` | the attempt's fields and the clone's identity, stack-start interlock, deployed tree listing and `deployed_vs_clone.py` in both directions with the listing's own exclusions (only `README.md` may differ), controller readiness, a stack health the step could **determine** at all (a docker that does not answer at all, a health state that is not available, or a `dmesg` that cannot be read — exit 1, and exit 4 when it saw a fault as well; a stack it saw failing, a service container included that docker answers for by not holding it, is exit 3, in the observed table above), broker-secret check, SUT environment capture and fetch | collector copy and install (the installed hash must equal the clone's), the live collector run, the fetch through `fetch-collector-output.sh`, `collector_check.py`, the collector's own window against the `duration=` its own `start:` line declares (`collector_shortfall.py`, run as a step of its own so that its stdout, stderr and exit code are in `console/` and `commands.jsonl`: `collector_check.py` validates a collection against that same window, so a collection that ended early reads clean there and only this comparison sees it — the `--duration 45` the driver passed is not compared with the declaration, so a collector that declares some other duration is not seen), the clock observations — both of them lists of commands, each judged on all of them | — |
| `gate_health.sh` | no argument at all, the open session, `EGW_HEALTH_LIMIT_S` and `EGW_HEALTH_STEP_S` as whole seconds, every guest parameter writable into a guest command as the literal it is, the attempt, its fields and the clone's identity (outcome `not-run`, 2: nothing was read, and this driver changes nothing either way) | all five steps of the snapshot: the shared wait answering at all (97: it never reached the guest, so the state of the six services was not observed), the reading of the three endpoints, the two verdicts over what it kept (each `2` means there is nothing to judge, never the `1` of a system failure, and it names a reading that was not made), the six container identities **and their copy into `environment/`** — including a repo digest an image inspect could not read at all, which is `NOT-READ` and not `none` (an image built on the guest has no repo digest, which its inspect answers) — the fetch of the controller build identity **and its content**, empty being no identity, and the TLS record (`2`: a configuration, a CA fingerprint or a file mode that could not be read) | — |
| `slice.sh` | a run id and a seed, the open session, the attempt's fields, identity and source, `pre` | simulator and marker, the `after` state, the twin read-back, `check` (0 required; 3 = no marker, 1 = not carried out), `delta` (0 and 4 are results, anything else is not), the verdict script (only 0 and 1 are verdicts; 2 = nothing to judge) | — |
| `persistence.sh` | the run id, the open session, the bounded waits as whole seconds, every guest parameter writable as the literal it is, the `after` pair and `sent_events.jsonl` of a slice that completed, a run id whose `persist-before`/`post-restart` snapshots do not exist yet (they are write-once), the attempt's fields, identity and source, `quiesce` (`drained`), and a twin the API answers 404 for **before** the restart (there is no stored state whose survival a restart could demonstrate): each is outcome `not-run`, 2, and **nothing is restarted** | every record the demonstration is made of: the controller process, the container ids and start instants, the independent twin read and the event log count **before** the restart (their failure stops the driver before anything is restarted), the restart command itself, the records after it, `restart-shown` (exit 1 names what did not change, exit 2 means the records could not be judged — either way the persistence was NOT demonstrated: invalid, `inconclusive`, 3), the `post-restart` snapshot, a `same` that did not run at all (the sequence stops there: what follows could not be trusted with a verdict), the twin read after that could not be MADE and the event count after, and `stored-state` exit 3 (something WAS published between the two snapshots, so the requirement the comparison rests on was not held) | — |

`persistence.sh` owns one window in which the guest has no stack at all:
between `compose down` and a `compose up -d` that came back. Every ending of
that driver — its interrupt handler included — reads from what the restart step
itself reported which state the guest is in (`not-restarted`, `refused`,
`down`, `up`, or not known because the step was cut short) and says it in the
reason, in the next action and in the `headline` on the final line, so that a
run which stopped in that window never leaves an operator believing the stack
is up. No volume is ever removed, so the stored state is intact either way.
| `nominal.sh` | a plan run id, the open session, the plan's seed, a fresh raw directory, the attempt's fields, identity and source, the collector copy and sync (the deployed hash must equal the clone's), the guest state **before** the run, `pre` | the harness run (its manifest decides validity), **the copy of the before/after snapshots into `analysis/snapshots/`**, the guest state after, `guest_state_delta.py --expect` when it cannot compare the two records at all (exit 2: a record that does not hold the six expected services in the *before* state, or that names one twice or without its id and start instant — any fault it saw all the same is kept in the observed table above), the clock domain the 60 s confirmation deadline rests on (`controller_marker.ok`, `confirmation_deadline_source`, read only when the accounting that carries them succeeded), and any of these steps whose console capture was lost (74) | — |
| `guest_session_close.sh` | an open session | the stack stop, a `dmesg` that can be read at all for the OOM record (an OOM it *finds* is exit 3 of that step: the record is sound and the system failed — outcome `fail`, exit 1), the power-off (`guest/session_close.sh`, which also checks the sealed G1 artefacts) and no `qemu-system-aarch64` left — each failure gives 5, while a `pgrep` that could not answer at all is not a failed stop but an undecided close (3, below); the record of the artefacts after the power-off (the rootfs hash **and** the data-disk listing, each judged, not only the last command of the step), the boot journal and the final guest state that `guest/session_close.sh` keeps (exit 3: the guest IS off and the record of the close is not complete), and any of these steps whose console capture was lost (74), leave the session closed but its record incomplete: invalid, inconclusive, 3 | the tunnel teardown (a lost console capture of it is still named) |

`$EXEC/current_session` is removed only when no `qemu-system-aarch64` process
remains: a guest still running is never recorded as a closed session. That test
is made in the driver's own shell, whose command line does not hold the
pattern — `pgrep -f` matches full command lines and excludes only itself, so
the same test inside a step run through `local_export exec` would match that
step — and the driver's finding is written into the artefacts record.
`pgrep` answers 1 for "no match" and 2 or more for a usage or fatal error (127
when it is not on `PATH` at all), so only 1 is read as "no qemu process left".
A `pgrep` that could not answer is a third state: the record says that whether
a process is left is unknown, the session is kept, and the close is sealed as
an incomplete record (invalid, inconclusive, 3) — never as a pass and never as
a failed controlled stop.

A `.self-test` marker beside the collector's CSV is explicitly **optional** for
the fetch (its absence never fails it) and a **problem** for
`collector_check.py`: it means the output is not a measurement.

## Before a session

- **Keep WSL alive.** The WSL distro stops when no `wsl.exe` client is
  attached, and a detached QEMU dies with it. Hold one client open for the
  whole session, for example
  `wsl -d Ubuntu-24.04 --exec bash -lc 'while [ ! -e ~/egw-exec/stop-keepalive ]; do sleep 20; done'`,
  and keep Windows from sleeping.
- **Login shell.** `kas` is only on `PATH` in a login shell: run the drivers with
  `wsl -d Ubuntu-24.04 --exec bash -lc 'bash <driver>'`.
- **No competing load during a measured window**: no test suite, build or bulk
  copy while `nominal.sh` or `slice.sh` runs.
- **Fresh identities.** The guest's event log is appended per run id: use a plan
  entry never used on the guest for `nominal.sh`, and an unused run id and
  seed for `slice.sh` (a seed never used on the MongoDB volume gives a fresh
  twin).

## Paths (environment overrides)

| Variable | Default | Meaning |
|---|---|---|
| `EGW_EXEC` | `/home/ruisth/egw-exec` | execution area (virtual environment, attempts) |
| `EGW_EXEC_REPO` | the clone holding this folder | clean clone the attempts run from |
| `EGW_EXEC_VENV` | `$EGW_EXEC/venv` | virtual environment with the clone installed editable |
| `EGW_ATTEMPTS` | `$EGW_EXEC/attempts` | live capture of each attempt (WSL filesystem) |
| `EGW_OUTPUT_TEST` | `/mnt/c/Users/ruimf/Documents/Projeto Mestrado/output_test` | the Windows folder |
| `EGW_SECRETS_ENV` | `~/egw-tcg/.env` | env file whose secret values are never exported |
| `EGW_YOCTO_CHECKOUT` | `/home/ruisth/yocto/egw` | checkout holding `src/yocto/build-integrated` (the OS image) |
| `EGW_DATA_DISK` | `/home/ruisth/yocto/egw-integrated/egw-data.img` | the guest's data disk |
| `EGW_IMAGES_DIR` | `/home/ruisth/egw-images` | controller image archive and identity record |
| `EGW_GUEST_KNOWN_HOSTS`, `EGW_G1_REFERENCE` | the 2026-09-18 capsules | the guest's pinned host key; the G1 artefact checksums |
| `EGW_HEALTH_LIMIT_S` | `1800` | bounded wait for the six services `running` and `healthy` (`gate_health.sh`, `persistence.sh`) |
| `EGW_HEALTH_STEP_S` | `15` | how often that wait takes a sample; every sample is kept |
| `EGW_READY_LIMIT_S` | `3600` | bounded `wait_ready` after the restart (runbook 6.5: an hour is the upper bound for the JVM start-up under TCG) |
| `EGW_DEPLOYED_DIR` | `/opt/egw/deployment` | the deployment tree on the guest |
| `EGW_CONTROLLER_IDENTITY` | `/opt/egw/images/egw-controller-0.1.0-arm64.identity.txt` | the controller build identity recorded on the guest |

Each of the three waits is read as whole seconds or not at all: a value that is
not one stops the driver with 2 and is never silently replaced by the default,
because the driver would then wait for something nobody asked for.

The OS image is not rebuilt by any driver: the launcher runs from
`EGW_YOCTO_CHECKOUT`, whose build directory holds the identified kernel and
rootfs, and the attempt records how that checkout, the clean clone and the
deployed tree differ. The rootfs `.ext4` is booted in place and changes with
every boot; its immutable identity is the build's `.tar.bz2`.
