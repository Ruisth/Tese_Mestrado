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
| `proof.sh RUN_ID EXPECTED_SOURCE_COMMIT` | the finite proof of ADR 0011 ("The finite proof"; see [The finite proof](#the-finite-proof-proofsh) below): one harness run of a one-entry diagnostic plan (`proof_plan.py`: the `controller_restart` condition's load, 300 s, no warm-up) with SIGKILL of the controller's container followed by a start at t+150 s through the harness restart hook, the twin snapshots, the drain, the post-drain copy and the three SUT logs through the `proof_*` hook wrappers, then the restart **shown**, the `/metrics` reading after, the runbook's `delta` on the post-drain copy, the guest state after with the controller's one restart expected, the stack running and healthy again (the restoration, never cut short), the session facts (`proof_session.py`) and, last, the proof's evaluator (`egw_experiments.proof_evaluator`: S1–S6, R1–R4, the inconclusive rule); an engineering diagnostic, not a G3 run, run only inside an authorised session | `finite proof (ADR 0011)` |
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
than only its result. A sample's instant is read when the sample starts, before
its inspections; the sample that finds all six healthy is followed by one more
line, `<instant> completed (sample N)`, read after its last inspection, so the
record also says by when that healthy observation had completed (whole
seconds). Its answer is one of four, and the two that are not a
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

The drivers call eight helpers of their own, all hashed into every attempt's
`drivers_sha256` (`driver_files` in `common.sh`: every `*.sh` and `*.py` of
this folder and every `guest/*.sh`, so the four `proof_*.sh` hook wrappers of
the finite proof count too) and copied into the session's `scripts/drivers/`:
`driver_status.py` (the exit statuses), `deployed_vs_clone.py` (the deployed
tree against the clean clone, in both directions),
`junit_one_failure.py` (the deliberate failure's own report),
`collector_shortfall.py` (how far a live collection fell short of the
`duration=` the collector's own `start:` line declares, which only the driver
that started it judges),
`proof_plan.py` (the one-entry diagnostic plan of the finite proof, built by
`plan_gen`'s own entry function and refusing any run id the pilot or campaign
plan holds), `proof_session.py` (the proof's session facts,
`analysis/proof_session.json`: the values, the two stop rules and whether
either was reached, the clocks, the instants, the restart-shown record, the
restoration and the extension, written once and updated through a rename so
the file is a whole document at every step), `proof_helpers_check.py` (the
deployed `~/egw-tcg/itest-helpers.sh` byte for byte against the runbook's
section 6.1 heredoc, extracted as `regen_helpers.py` extracts it) and
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
shows nothing, and no container is reported gone out of it; a driver that
itself restarts a container during the run — the proof session of ADR 0011
kills the controller's container and starts it again — names it with
`--expect-restarted NAME`, once per container, and the one in-place restart of
that container (the same container id, a later start instant, the restart count
and the OOM state untouched) is then an **expected restart** under a heading of
its own and not a fault, while an OOM kill, a replacement, a restart count that
moved or any other container's restart stays the fault it is, and a named
container the pair shows no restart of at all is a problem — an expectation the
pair does not confirm is never satisfied by silence; without the option every
line is what it always was); `collector_check.py`
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
| `proof.sh` | the evaluator's **refutation** (exit 1: one of R1–R4 rests on something observed — a valid negative result, "recorded and preserved, never re-run away"), and the faults `guest_state_delta.py --expect-restarted egw-controller-1` printed beside the proof's own restart (a container OOM-killed, replaced or gone, a restart count that moved, any other container's restart), whether it could complete the comparison (exit 1) or not (exit 2, where the comparison is `mandatory` as well) | the `/metrics` reading after (`metrics-after`), a `delta` that did not run (0 and 4 are both results: a named N1 case gives 4 by exactly one, and the evaluator applies S5's tolerance — design flag P-9), a live observation ended by `timeout` when the attempt's allowance ran out (its record kept as partial), and, after the attempt's stop rule, every live observation not yet made — the controller process and the containers after, the reading after, the delta, the guest state after — which are then not started, and the offline comparisons one of whose input records the rule kept from being taken whole — the restart-shown check, the guest-state delta — which are then not run; all are listed by name (P-10), and a comparison whose records were taken whole still runs after the expiry, so a fault it shows is still observed; the outcome is then `inconclusive` unless a refutation or a fault was observed |

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
| `proof.sh` | a fresh run id and a 7–40 hex source commit, the open session, `timeout` on the host, every value of the table below as a whole number (a quiet window below 130 s, a rate that is not a number, a master seed that is not set, an extension flag other than `yes`/`no`), `EGW_PROOF_RESTART_AT_S` strictly between 0 and `EGW_PROOF_DURATION_S` and equal to the ADR's 150 s, which the evaluator requires (P-13), a results base and a plan that do not lie under `~/egw-tcg/pilot/` (P-14), a drivers' path the hook templates can hold double-quoted, a run directory, a plan and prefix files that do not exist yet (write-once), the attempt, its fields, identity and sources, the deployed helper file byte-equal to the runbook's 6.1 heredoc (`proof_helpers_check.py`), the collector copy and sync, the guest clock read as a whole number, the session facts written, the containers before (their ids and `StartedAt`, read **before** the wait: the candidate's start is their earliest `StartedAt` — P-15), the first stop rule established from that start (`healthy-rule`: the remainder of `EGW_HEALTH_LIMIT_S` from the candidate's start bounds the wait; spent, the rule is **reached** before the wait can start; an earlier healthy transition named with `EGW_PROOF_HEALTHY_RECORD` establishes it only when it is of this same start; an unknown start or transition cannot establish it), the stack running and healthy within that remainder (the **first stop rule**: reached — before the wait, within it, by the remaining allowance ending the wait's acquisition, or at its first healthy observation — it is recorded in `proof_session.json`, the harness is not started and the proof is recorded `inconclusive`, exit 3, never `not-run`) and its first healthy observation **completed** within `EGW_HEALTH_LIMIT_S` of the candidate's start (`healthy-rule-check`), the SUT environment captured and fetched, the guest state before, the controller process read (`_mline`), the diagnostic plan written (a run id the pilot plan holds is refused; the load equals the plan's), `ready` (`wait_ready`, a step of its own before the attempt's clock starts — P-10), `pre` (`drained`, `metrics before`, `config_identity`; the instant the 50-minute rule runs from is taken immediately before it, and `pre` runs under that allowance: spent before it, `pre` is not started; ended by `timeout`, the rule was reached during it — either way the second stop rule was reached, which is **not** `not-run` but the proof recorded `inconclusive` (exit 3, the instrumentation invalid), as the ADR's stop-rule text says, the harness is not started and the rule is recorded once, with the step) and the identity check (the expected source commit, `broker_reloaded` false, W readable): each is outcome `not-run`, 2, but for a stop rule reached (the 20-minute rule, the 50-minute rule before or during `pre`: `inconclusive`, 3) and for a prerequisite that fails once the 50-minute rule has been reached (`pre` ending at the deadline, then failing itself or followed by a failed identity check or mandatory record: `inconclusive`, 3, with the rule named beside the prerequisite), and **the harness is not started** | `tunnel-ready` (the 6.1 preamble loaded under the allowance just before the harness, P-10) ending other than 0 or by the allowance — the preamble could not be loaded (97) or its capture was lost (74): the tunnel is then not known to be up, the harness step is not dispatched and the harness is not started — the harness run (exit 2 or any code other than 0, 1, 124, 137: 1 is admitted only as the eligibility step reads it, and 124/137 are the second stop rule), the **eligibility** of the run read from the manifest (P-16: the simulator exited 0, the harness copy of the events fetched with its file, the collector file present — `resources.csv`, or in the sampling-gap form the file the ingest rejected, where the admission names it — the post-drain copy fetched and verified, both twin snapshots verified, the three SUT logs fetched, the fault record executed and 0, and a harness validity admitted as E-12 states by the evaluator's own `harness_admission`: `valid`, or the campaign's `MAX_SAMPLE_GAP_S` deviation in the one form the harness records it), the restart **shown** from the driver's own records (the controller's `started_at` changed, its container the same object started later; not shown means the fault was not applied, and a pair that cannot be judged is the same requirement failed), the copy of the prefix snapshots into `analysis/snapshots/`, the session facts updated, the evaluator that could not run (exit 2: not evaluated), the proof's evidence complete (`proof_verdict.json` `instrumentation.proof_evidence.complete`), the guest state after, `guest_state_delta.py` when it cannot compare the records or the expected restart is not shown by the pair (exit 2), whether the stack is healthy again could not be determined, and any of these steps whose console capture was lost (74) | the clocks' offset, `environment/containers.*.txt`, `environment/healthy-record.txt` (the earlier transition named, kept as given), the extension when it was not asked for |
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

## The finite proof (`proof.sh`)

`proof.sh RUN_ID EXPECTED_SOURCE_COMMIT` runs the finite proof of ADR 0011
("The finite proof"): one bounded engineering diagnostic, not a G3 qualifying
run, not a repetition of any pilot run and not a campaign, soak or pilot; it
changes no threshold, deadline, load or rule, and one run supports the
property for that run only. It runs inside a session opened by
`guest_session_open.sh` and never boots or powers off the guest, never
builds, pulls, loads or retags an image, never edits the pilot plan or writes
under `~/egw-tcg/pilot/` (the plan is read only to refuse a run id it holds;
a results base or a plan given there, as written or as it resolves, is
refused before anything starts — P-14),
never repeats C3, never runs a second attempt by itself (a repeat is the
student's decision), never lowers `DRAIN_QUIET_S` below 130 s and never runs
the optional extension unless the student sets `EGW_PROOF_EXTENSION=yes`.

**Three verdicts, never merged.** The attempt's **instrumentation validity**
is `valid` only when every mandatory record was made *and* the proof's
evidence is complete — the evaluator's
`instrumentation.proof_evidence.complete` in `analysis/proof_verdict.json`:
both twin snapshots verified, a verified drain, the post-drain copy fetched
and verified, the three SUT logs fetched, the configuration identity
embedded with W, a readable pre-kill reading, the run directory sealed (in
the sampling-gap form below, the collector file where the harness kept it and
the seal the harness withheld for it, each accepted with the reason stated).
The harness's **own** `validity` is quoted verbatim in the reason ("manifest
validity invalid (no SUT resources: …) kept as recorded, admitted for the
proof only as E-12 states (harness_admission form 'sampling-gap-only')") and
is admitted for the proof only as the evaluator's rule **E-12** states,
through the one function both parts apply,
`egw_experiments.proof_evaluator.harness_admission`, so the driver and the
evaluator cannot disagree on it: `valid`, or the campaign's
`MAX_SAMPLE_GAP_S` deviation in the one form the harness records it — its
ingest rejected the collector file, so `resources.csv` is never written,
`resource_source` is `none`, the two reasons are `no SUT resources` and
`mandatory artefact(s) missing … resources.csv`, `MAX_SAMPLE_GAP_S` appears
only in the rejection's warning, the rejected file stays at
`logs/collector/resources-RUN_ID.csv` and `SHA256SUMS` is withheld (the
archived r02 manifest has exactly this shape). That deviation "belongs to the
campaign rules and is kept as recorded" (ADR 0011, "What the proof cannot
show"); any other invalidity is not admitted. Design flag **P-8** read the
harness's validity as never decisive; that blanket reading was not confirmed
by the Project Manager and is withdrawn in favour of E-12 (**P-16**): the
`eligibility` step reads the admission and, beside it, the manifest for
everything else the ADR requires of the execution and the evidence (a
completed publication, the harness copy of the events, the collector file,
the post-drain copy, the twin snapshots, the SUT logs, the fault record),
each absence an evidence requirement not met. The **system
outcome** is the evaluator's exit code — 0 supports →
`pass`, 1 refutes → `fail` (a valid negative result, exit 1, "never re-run
away"), 3 inconclusive → `inconclusive`, 2 not evaluated → `inconclusive`
with a mandatory record missing — and, beside it, any fault of the guest
state the run positively showed (`guest_state_delta.py --expect-restarted
egw-controller-1`: the controller's one in-place restart is expected; an OOM
kill, a replacement, a moved restart count or any other container's restart
is a fault and makes the outcome `fail`). The **restoration outcome** is the
field `restoration=stack=<healthy|not-healthy|unknown>
restart_shown=<yes|no|unknown>`: the six services running and healthy again
after the run, through the shared `healthy_wait`, never cut short by the
attempt's allowance; a `pass` is never reported when the stack is not
healthy again (it becomes `inconclusive` with "the guest was NOT fully
restored"), and every reason — the interrupt handler's included — ends with
the state the guest was left in. The evaluator runs only after that wait,
so the write-once `analysis/proof_verdict.json` echoes in its `restoration`
section the state the driver observed (it decides nothing on it); the
extension's own restoration, after its second kill + start, is recorded
apart as `extension.restoration` in the session facts, whose top-level
`restoration` is the state the guest was finally left in. An evaluator
that exits 2 without an `error:` line (the not-evaluated document of a seal
that does not verify prints only its `[proof]` summary) has that summary,
or "no reason printed on stderr", as the cause in the mandatory note. The
reason keeps the groups in this order:
observed system fault(s); evidence requirement(s) not met; post-window
observation(s) incomplete; stop rule(s) reached; the proof's result with the
criteria that failed, the refutations and the inconclusive reasons; the
manifest's validity as recorded; the extension, if chosen; the restoration.
The next action names the ADR's consequence for the attempt's **final**
verdicts, never the evaluator's raw result (**P-17**): outcome `pass` → the
result stands for this run only and the candidate freeze is a separate
decision; `fail` → a refutation, or a fault the guest state showed, is a
valid negative result, never re-run away, and the option is re-decided by
the student (option 4 next best, never automatic); `inconclusive` → the
attempt is not passing, and when the evaluator's component result was
`supports` the text says what downgraded it (a stop rule, an evidence
requirement not met, a fault observed, an observation not made, the guest
not fully restored) and never that the supporting result stands; the
student decides whether to repeat (recorded as a repeat, this run kept) or
to re-decide. An invalid attempt and a stack left other than healthy are
named on the same line.

**The values, recorded before anything starts.** Every value is read from
the environment as a whole number (or the driver stops with 2 before
anything starts) and recorded on the attempt (`workload.values`) and in
`analysis/proof_session.json` before the first `drained`; the student may
set other values before the session, as the ADR allows.

| Variable | Default | The ADR figure it comes from |
|---|---|---|
| `DRAIN_QUIET_S` | `130` | the quiet window of the runbook's `drained` under C5 ("quiet window 130 s by default; 490 s where a first-contact message may be in progress"); never lowered below 130 |
| `DRAIN_STEP_S` | `5` | the helper's polling step (runbook 6.1) |
| `DRAIN_LIMIT_S` | `900` | the helper's limit, the 900 s of the planning ceiling "900 + 300 + 60 + 900 s" |
| `EGW_HEALTH_LIMIT_S` | `1200` | the first stop rule: "the stack with the candidate healthy within 20 minutes of its start (as for the broker measurement, and on the same records)" — measured **from the candidate's start**, the earliest `StartedAt` of the six expected services read before the wait, never from the first poll (P-15): the wait runs under what is left of this allowance from that start (time already spent counts; a late poll never resets it), and its acquisition as a whole is bounded on the host by that remainder, so an inspection that blocks is ended by it (the rule reached) — except the precondition poll run when an earlier record named with `EGW_PROOF_HEALTHY_RECORD` establishes the rule, which keeps only the guest wait's own limit (an inspection that blocks there holds the driver before the attempt's clock starts, nothing yet mutated, and an interrupt still restores); a first healthy observation that **completed** past start + limit — judged on the instant the wait reads after the healthy sample's last inspection, never on the sample's start — is not accepted, and an unknown start cannot establish the rule; reached, the harness is not started and the proof is recorded `inconclusive` (exit 3), never `not-run` ("If a stop rule is reached, the session stops and the proof is recorded inconclusive"); the same wait, under the full limit, bounds the restoration (`broker_measure.sh` uses 1200 too; `gate_health.sh` and `persistence.sh` default to 1800) |
| `EGW_PROOF_HEALTHY_RECORD` | none | the path of a console record of the shared healthy wait made earlier in this session (`gate_health.sh`'s `services-healthy`), whose `ALL HEALTHY` transition establishes the first stop rule instead of the driver's own poll — only when its healthy sample began after the latest `StartedAt` of the six services, which makes it a transition of this same start, and **completed** (its `completed (sample N)` line) by the candidate's start + `EGW_HEALTH_LIMIT_S` (P-15); a transition of this start completed beyond the allowance is the rule reached (`inconclusive`, 3), and a transition of another start, a record without a readable transition, or a record that does not say when its healthy sample completed (one made before the wait recorded it: its sample's start alone does not prove a timely observation) cannot establish the rule and is refused (not-run, stated), and a file that cannot be read is refused before anything starts; the record named is kept as `environment/healthy-record.txt`; with the rule established by it, the driver's own poll before the run is the precondition of a healthy stack under the full limit, and its failure is a precondition failed, not the rule reached (P-15) |
| `EGW_HEALTH_STEP_S` | `15` | how often that wait samples; every sample is kept |
| `EGW_READY_LIMIT_S` | `300` | none: the ADR gives no `/ready` figure — its planning figure "excludes the `/ready` wait", and the 300 s in "900 + 300 + 60 + 900 s" are the publication. 300 s is the driver's own choice for the `ready` step (`wait_ready`), above the runbook's `wait_ready` default of 60 s; that wait runs before the attempt's clock starts, so it is no part of the 50-minute rule (P-10) |
| `EGW_PROOF_ATTEMPT_LIMIT_S` | `3000` | the second stop rule: "the attempt stopped 50 minutes after its first `drained` starts — the 36 minutes of the helper's limits plus 14 minutes"; measured on `/proc/uptime` from the instant taken immediately before `pre`, whose first command is `drained` (the `/ready` wait comes before it, in the `ready` step, and is not counted — P-10; the instant is recorded as `instants.first_drained_started_*`), and enforced as **one monotonic deadline** on `pre` itself and on every live proof step after it — `tunnel-ready` (the 6.1 preamble loaded under the bound just before the harness), the harness run, the controller process and the containers after, the `/metrics` reading after, the `delta`, the guest state after: the remainder is checked before each is dispatched, each runs under `timeout` of the positive remainder (a spent allowance leaves the step unstarted, never `timeout 0`; the harness step's own 6.1 preamble runs inside that bound with the harness, and the harness's own bound is computed from the absolute deadline after that preamble), and the expiry is recorded once with its instant and the step it fell before, during (124 or 137) or after (`instants.attempt_limit_reached_*`). After it no further proof or fault step starts, the optional extension included (the steps not made are listed by name, `instants.not_started_after_stop_rule`), the partial records and the stop reason are kept, the restoration and the shutdown still run and are never force-killed to meet the elapsed time, the offline comparisons of records already taken (the restart-shown check, the guest-state delta) still run when their records were taken whole, and the packaging, hashing and evaluation may finish afterwards without acquiring a new live observation and without hiding the rule reached (the outcome is `inconclusive` with the rule named, whenever the rule is reached — an allowance spent before `pre` could be dispatched included, and a prerequisite that fails after the rule was reached, named beside it, never `not-run`). The step's host shell keeps `timeout` and the command as a job and forwards the driver's interrupt to them: `timeout` moves itself and the command into a process group of their own, which the terminal's Ctrl-C would otherwise never reach (the harness would then go on to apply the fault after the driver ended) |
| `EGW_PROOF_RESTART_AT_S` | `150` | "at t+150 s, SIGKILL of the controller's container followed by a start" (`--restart-at-s`, passed explicitly); the evaluator requires the manifest's `restart.requested_at_s` to be 150 (E-11), so any other value is refused before anything starts, as a load that differs from the plan is — a run with the fault at another instant could never support the proof, and the driver changes no fault instant; it is also refused unless strictly between 0 and `EGW_PROOF_DURATION_S`, because the harness cancels its restart timer when the measured run ends and the fault would then never fire (P-13) |
| `EGW_PROOF_DURATION_S` | `300` | "300 s of publication = 3,360 messages"; fixed by `proof_plan.py`, so a different value stops the driver (it changes no load) |
| `EGW_PROOF_RATE` | `11.2` | "the `nominal` scenario at 11.2 msg/s, three wearables, no warm-up"; fixed by `proof_plan.py` likewise |
| `EGW_PROOF_MASTER_SEED` | none | the master seed the plan's entry seed is derived from (`derive_run_seed`): the student's decision, so it has no default and the driver stops without it |
| `EGW_PROOF_EXTENSION` | `no` | the optional extension of item 4 §9 ("it changes the proof's plan, so it is the student's decision; it is not needed to decide"); `yes` runs it after the restoration — the second kill + start, `wait_ready` and one `/metrics` reading (the restart shown only against the `started_at` the driver read after the run, P-12), `drained` with nothing published, the `/metrics` reading after it that decides `received`, the second post-drain fetch; every step under what is left of `EGW_PROOF_EXTENSION_LIMIT_S` and, besides, the restart command and the second fetch under the ADR's two per-step stop rules (P-11), and the second restoration wait after it, recorded apart as `extension.restoration` — and records its result apart (`extension` on the attempt and in the session facts: `not-refuted`, `refutes`, `inconclusive`), never changing the proof's three verdicts. Chosen but not runnable (a stop rule reached, the attempt's allowance spent before it could start — during the restoration or the evaluation, which are never bounded, so no live step recorded it: its kill + start is a fault step and its readings are live, so it does not start after the expiry, and this is the extension's reason, not a stop rule of the proof, whose live observations all ended in time — the stack not healthy again after the run, no post-drain copy to compare with, no baseline `started_at` read after the run — `controller-process-after` failed — or no `stop_grace_period` readable as seconds), it is recorded `inconclusive` with the reason, never `not-chosen` |
| `EGW_PROOF_EXTENSION_LIMIT_S` | `1790` | the extension's ceiling, "the `stop_grace_period` recorded under C6 plus 1,660 s" with the 130 s grace period C6 recorded. Inside it, the ADR's two per-step stop rules "imposed by design, not measured durations" (P-11): `ext-restart` under "the restart command within the grace period plus 5 minutes" — the `stop_grace_period` the configuration identity captured at `pre` reports, the value the guest reported (`130s` read as 130 s), plus 300 s — and `ext-fetch` under "the second fetch within 5 minutes", 300 s; each step runs under the smaller of its rule's bound and what is left of the ceiling, under `timeout`, and reaching a rule records the extension `inconclusive` with the rule named (`extension.stop_rules`, `extension.stop_rule_reached` in the session facts) |
| `extension_restart_limit_after_grace_s`, `extension_fetch_limit_s` | `300`, `300` (constants, not environment values) | the ADR's two per-step stop rules of the extension ("the restart command within the grace period plus 5 minutes", "the second fetch within 5 minutes"), recorded among the values before anything starts so the bounds in force are on the record whether or not the extension is chosen; the grace period itself is read from the configuration identity at `pre` (P-11) |
| `EGW_PROOF_BASE` | `~/egw-tcg/proof/results` | the harness results base of the proof, apart from the pilot's (`--base-dir`); the run directory is `raw/RUN_ID` under it, write-once |
| `EGW_PROOF_PLAN` | `~/egw-tcg/proof/plan-RUN_ID.json` | the one-entry diagnostic plan `proof_plan.py` writes, write-once, "never an edit of the pilot plan" |
| `EGW_PROOF_RUNBOOK` | the clone's `docs/setup/qemu_integrated_gateway.md` | the runbook whose section 6.1 heredoc the deployed `~/egw-tcg/itest-helpers.sh` must equal byte for byte (a path override for the bench; the sha256 of both is in `environment/helpers-check.txt`) |

W (`max_inflight_messages`) is not a value the student sets: it is read from
the configuration identity captured on the guest by `config_identity` and
recorded beside them. The harness command line is the runbook's `harness_cmd`
(6.1) argument for argument — the proof's own plan, results base and SUT
environment capture in the place of the pilot's — with the proof's hooks
appended: `--restart-cmd` (`proof_restart_controller.sh`, the SIGKILL then
`compose start`, write-once record `RUN_ID.restart.txt`), `--restart-at-s`,
`--config-identity-from`, `--twin-snapshot-cmd` (`proof_hook_twins.sh`,
the plan's seed for `before`, `--like before` for `after`), `--drain-cmd`
(`proof_hook_drained.sh`, the runbook's `drained` with the three `DRAIN_*`
values exported into the step), `--post-drain-fetch-cmd` and the three
`--fetch-*-log-cmd` (`proof_fetch_sut_log.sh`, bounded from the guest epoch
the driver read: a failed or empty read leaves no file). The harness splits
each template without a shell (`shlex.split`), so the hook's path and
`"{dest}"` are double-quoted in every template, as the runbook's
`harness_cmd` quotes its own `"{dest}"`: a results base with a space in its
path works, and a drivers' path holding a double quote or a backslash is
refused before anything starts. A test pins the fixed arguments to the
runbook's function line by line, and another renders the templates as the
harness does against a base with a space.

**Rules of the driver's own, by label** (beside the design flags P-1 to
P-9 of the evaluator and the driver, each to be confirmed by the Project
Manager):

- **P-10** — the 50-minute rule is measured from the instant taken
  immediately before `pre`, whose first command is `drained`; the `/ready`
  wait is a step of its own (`ready`) before it and is not counted. It is
  one monotonic deadline (`/proc/uptime`) that bounds `pre` itself,
  `tunnel-ready` and every live proof observation after it (the harness
  run, the controller process and the containers after, the `/metrics`
  reading after, the `delta`, the guest state after): the remainder is checked before each is
  dispatched, each runs under `timeout` of the positive remainder (a spent
  allowance means the step is not started, never a zero or negative
  timeout), and the expiry is recorded once, with its instant and the step
  it fell before, during or after — in the driver's own shell: the
  remainder is answered in a variable (`LIVE_REST`), never through a
  command substitution, so the latch, the stop rule and the headline are
  never set in a subshell and lost, and the step the facts name is the
  first one skipped. The live host steps (`pre`, `tunnel-ready`, the
  controller process after, the `/metrics` reading after, the `delta`)
  load the runbook's 6.1 preamble inside that bound (handed to the bounded
  shell as the value of `EGW_HOST_PRE` and loaded with `eval`), so a
  preamble that blocks — a `tunnel_up` whose ssh never completes — is ended
  by the allowance too. The harness step is preceded by `tunnel-ready`, a
  live step with a trivial body that loads the same preamble under the
  bound, sharing the remainder checked before the harness is dispatched: a
  tunnel that wedges there is ended by the allowance (the rule is recorded
  as reached during `tunnel-ready`, and neither the harness nor its fault
  is started). The harness step is dispatched only when `tunnel-ready`
  ended 0 and something of the allowance is still left; a `tunnel-ready`
  that ended otherwise — the preamble could not be loaded (97), or its
  console capture was lost (74) — leaves the tunnel not known to be up, so
  the harness step is not dispatched either (an evidence requirement not
  met, the harness not started). `tunnel-ready` is not an observation of
  the system and is not listed with the observations not made; its exit
  and bound are recorded (`instants.tunnel_ready_exit`,
  `tunnel_ready_allowance_s`). A successful `tunnel-ready` is no substitute
  for bounding the preamble that actually precedes the harness: the
  harness step runs **its own** 6.1 preamble and its body together under
  `timeout` of the positive remainder checked just before it is
  dispatched (the preamble handed to the bounded shell as the value of
  `EGW_HOST_PRE` and loaded with `eval`, the body — its text pinned to the
  runbook's `harness_cmd` — as that shell's argument, run with `eval`
  after it). A tunnel that drops after `tunnel-ready` and whose reopening
  blocks is therefore ended by the allowance (124, or 137 after the 30 s
  grace of `timeout -k 30`) before the harness starts: the rule is recorded
  once as reached during `harness-run`, the harness and its fault are not
  started, and the restoration is still attempted
  (`instants.harness_step_exit`, `harness_step_allowance_s`). The harness
  step is also handed the absolute deadline (the instant before `pre` plus
  `EGW_PROOF_ATTEMPT_LIMIT_S`, on `/proc/uptime`): it computes the
  harness's own bound after its preamble, so a preamble that took its time
  is charged to the allowance — the harness receives only what is left
  then, never a fresh budget — and with nothing left the harness and its
  fault hook are not started (the step answers 98 and the rule is recorded
  as reached before `harness-run`); the step prints the harness's own
  start instant, on both clocks, and the bound it runs under immediately
  before the harness starts, and the session facts record those
  (`instants.harness_started_utc`, `harness_started_host_uptime_s`,
  `harness_allowance_s`) beside the dispatch instant
  (`harness_step_dispatched_utc`). The driver's interrupt is forwarded
  through both bounds to the harness. After the expiry no further proof or
  fault step starts — the optional extension included: an allowance spent
  after the proof's last live observation, during the restoration or the
  evaluation (never bounded, so no live step records it), keeps the
  extension from starting, with that as the extension's reason and not as
  a stop rule of the proof, whose live observations all ended in time. The
  partial records and the stop reason are kept, the restoration and the
  shutdown still run unbounded, and the offline work may finish afterwards
  but acquires no new live observation and never hides that the deadline
  was reached: the eligibility reading, the packaging, hashing and
  evaluation, and the two offline comparisons of records already taken —
  the restart-shown check and the guest-state delta, which run unbounded
  and still run after the expiry when their input records were taken whole
  (an OOM kill or a replacement the complete records show is judged), and
  are not run, and listed with the observations not made, when the rule
  kept one of those records from being taken whole. Whenever the rule is
  reached — before `pre` could be dispatched, during it, between it and
  the harness, during or after any later step — the proof is recorded
  `inconclusive` with the rule named (exit 3, the harness not started when
  it was reached before it), as the ADR's stop-rule text says ("If a stop
  rule is reached, the session stops and the proof is recorded
  inconclusive"); `not-run` is a prerequisite failed, never a stop rule
  reached: a prerequisite that fails once the rule has been reached (`pre`
  ending at the deadline and then failing, or followed by a failed identity
  check or mandatory record) is recorded `inconclusive` with the rule named
  beside it, never `not-run` (the read-only re-check of round 4 found it
  `not-run`, the rule unnamed), and a console capture of `pre` or of the
  identity check lost after the rule was reached ends the attempt invalid
  and `inconclusive`, as every lost capture does, with the rule named in
  the final reason beside it (it was in the session facts, but the reason
  omitted it). (Until these corrections the rule reached
  during `pre`, and then an allowance spent before `pre` was dispatched,
  ended the attempt `not-run`; the tests that expected it encoded that
  wrong rule and are corrected.)
- **P-11** — the extension's restart command is bounded by the
  `stop_grace_period` the configuration identity captured at `pre` reports
  (the guest's value, read as whole seconds) plus 300 s, and its second fetch
  by 300 s, each under `timeout` and inside the extension's ceiling; a rule
  reached records the extension `inconclusive` with the rule named. A
  `stop_grace_period` not readable as seconds keeps the extension from
  running (it is recorded `inconclusive`) and touches nothing of the proof.
- **P-12** — the extension's restart is shown only against the recorded
  baseline, the `started_at` read after the run; without it the extension
  is not run and is `inconclusive` ("the restart cannot be shown"), never
  `not-refuted`.
- **P-13** — `EGW_PROOF_RESTART_AT_S` must be the ADR's fault instant,
  150 s ("fault | at t+150 s"), which the evaluator requires of the run
  (E-11: the manifest's `restart.requested_at_s` must be
  `egw_experiments.proof_evaluator.PROOF_RESTART_AT_S`; a test pins the
  driver's value to it), and must lie strictly between 0 and
  `EGW_PROOF_DURATION_S`; any other value is refused before anything
  starts, as a load that differs from the plan is refused, so a session
  that could never support the proof is never started. The driver changes
  no fault instant. (P-13 used to admit any instant strictly between 0 and
  the duration, which the evaluator then refused.)
- **P-14** — `EGW_PROOF_BASE` and `EGW_PROOF_PLAN` must not lie under
  `~/egw-tcg/pilot/`, as given or as they resolve, or the driver refuses
  before anything starts.
- **P-15** — the 20-minute rule is measured from the candidate stack's
  actual start, never from the first poll: the candidate's start is the
  earliest `StartedAt` of the six expected services, read from the
  containers record taken before the wait (the guest clock in that same
  record says how much is already spent); the wait runs under the positive
  remainder of `EGW_HEALTH_LIMIT_S` from that start (spent, the rule is
  reached before the wait can start), and its acquisition as a whole runs
  under `timeout` of that remainder on the host's monotonic clock (from
  the instant just before the containers record, less the time since;
  `healthy_rule.acquisition_bound_s`): the wait checks its own limit only
  between samples, so an inspection that blocks is ended by the remaining
  allowance there — no sample completed healthy in time, the rule reached,
  never a pass. The first healthy observation is judged by when it
  **completed**: a sample's instant is read at its start, before its
  inspections of the six services, so it does not show when the
  observation was made; the shared wait follows its healthy sample with
  the instant it reads after the last inspection (`completed (sample N)`,
  whole seconds, so the observation completed before that instant + 1 s),
  and that upper bound is compared with start + `EGW_HEALTH_LIMIT_S`: a
  sample that began before the deadline and completed after it has not
  shown the stack healthy in time (the rule reached), and a record without
  the completion line cannot place the observation (not-run, stated). A
  late poll never resets the allowance. A healthy transition of this same
  start demonstrated earlier in the session (a console record of the
  shared wait named with `EGW_PROOF_HEALTHY_RECORD`) is reused instead
  only when its healthy sample began after the latest `StartedAt` of the
  six and completed by start + `EGW_HEALTH_LIMIT_S`; a healthy guest's
  later idle time is then not charged as boot delay. A record made before
  the wait recorded the completion (only the sample's start) does not
  prove such a transition — nothing is guessed — and is refused (not-run,
  stated); records already made are never rewritten. The rule **reached**
  — the allowance from the candidate's start spent before the wait, the
  stack not running and healthy within its remainder (or the acquisition
  ended by it), the first healthy observation completed past start +
  `EGW_HEALTH_LIMIT_S`, or a named earlier transition of this start
  completed past it — is a stop rule reached: the harness is not started and the proof is
  recorded `inconclusive` (status failed, the instrumentation invalid,
  exit 3) with the rule named, as the ADR's stop-rule text says, never
  `not-run` (which it was until this correction; the tests that expected
  it encoded that wrong rule and are corrected). An unknown start or
  transition cannot establish the rule (not-run, stated): it is a
  prerequisite not met, not the rule reached; nothing is guessed. Docker's zero `StartedAt`,
  `0001-01-01T00:00:00Z` (with or without its nanoseconds), which it reports
  for a container created but never started, is such an unknown start —
  never read as a start in year 1, which would record the rule reached with
  a candidate start two thousand years ago. Every instant compared is
  read on the guest wall clock, which on this host is stepped backwards by
  2–3 s about every 30 s: an instant that precedes another by no more than
  the 3 s band the evaluator applies to host instants is read as
  simultaneous and noted (`clock_step_note`), a larger regression is a
  clock that is not consistent (not-run), and the deadline is judged on the
  instants as read (a backwards step only makes them read earlier). The
  check records both instants of the first healthy observation
  (`first_healthy_utc`, the sample's start; `first_healthy_completed_utc`
  and `completed_upper_elapsed_s`, its completion and the upper bound
  judged), the span from the previous sample's instant
  (`previous_sample_span_s`, as information) and a note
  (`first_healthy_instant_note`). (Until this correction the check judged
  the sample's start and recorded that span as the only bound of the bias:
  a sample that began at +1,199 s of a 1,200 s allowance and completed at
  +1,205 s was accepted.) When
  the rule was established by the earlier record, the driver's own poll
  before the run runs under the full `EGW_HEALTH_LIMIT_S` (as the
  restoration's does) as the precondition of a healthy stack, not as the
  allowance's remainder: a stack no longer healthy then fails that
  precondition (not-run, stated, with the service named), and the rule is
  not recorded as reached by a poll that did not measure it. The reading is
  recorded as `healthy_rule` in the session facts.
- **P-16** — the harness's validity is admitted for the proof only as the
  evaluator's **E-12** states, read by the very function the evaluator
  applies to the same run directory,
  `egw_experiments.proof_evaluator.harness_admission` (imported from the
  clean clone), never by a match of the reason texts: `valid`, or the
  campaign's `MAX_SAMPLE_GAP_S` deviation in the one form the harness
  records it (`sampling-gap-only`: the two reasons `run.compute_validity`
  writes for a collector file its ingest rejected, `resource_source`
  `none`, `missing_mandatory_artifacts` `['resources.csv']`, exactly one
  rejection warning whose every problem is a sampling gap over
  `MAX_SAMPLE_GAP_S`, the rejected file present and non-empty at
  `logs/collector/resources-RUN_ID.csv`, no `resources.csv` at the top of
  the run directory, and `SHA256SUMS` withheld for that alone or present
  and verifying). After the harness step the `eligibility` step reads the
  admission and the manifest and requires the prescribed publication
  completed (`simulator_returncode` 0), the harness copy of the events
  fetched (`events_fetch.ok`, its file present — the first of the two
  copies the ADR keeps apart, which a successful post-drain copy never
  replaces), the collector file present — `resources.csv`, or in the
  sampling-gap form the file the ingest rejected, at the admission's
  `collector_file`, instead — the post-drain copy fetched and verified,
  both twin snapshots verified, the three SUT logs fetched with their
  files, the fault record executed and 0, and the harness validity
  admitted. Anything else — a validity not admitted, a rejection that also
  lists another problem, a further reason, the rejected file missing — is
  the proof's execution or evidence incomplete: mandatory, the attempt
  invalid, never a pass; an admission that cannot be read is never
  admitted (exit 2 when nothing else is amiss). The reading, with the
  admission as the function returns it (`eligibility.harness_admission`:
  its form, its reasons, the collector file, what the seal was withheld
  for), is written into the session facts (`eligibility`, beside
  `harness_exit`) before the evaluator runs; the verdict document records
  the same admission, so the two parts cannot disagree on it. In the
  sampling-gap form the package's declared artefacts follow the same
  inventory: `expected_artefacts`, declared before anything starts, is
  amended once after the eligibility reading, with what was changed and why
  on the attempt (`expected_artefacts_amended`) — the collector file where
  the admission names it in the place of `raw/*/resources.csv`, and no
  `raw/*/SHA256SUMS` when the harness withheld it — never in any other
  form. (P-16 used to admit an invalid run whose every reason named
  `MAX_SAMPLE_GAP_S` beside a `resources.csv` at the top: a form the harness
  never writes, while the form it does write was always refused.)
- **P-17** — the next action is chosen from the attempt's final validity,
  outcome and restoration state, never the evaluator's raw result, which
  stays visible in the reason as the component it is: a supporting
  component result downgraded by an unshown restart, an incomplete
  restoration, a stop rule, a missing record or an observed fault gives an
  inconclusive (or failed) attempt whose next action says so and never that
  the supporting result stands.

The package holds the harness capsule byte for byte under `raw/RUN_ID/`,
the prefix files (`RUN_ID.config_identity.json`, `.metrics.before/.after.json`,
`.twins.before/.after.json`, `.restart.txt`, and `.extension.restart.txt` when the extension ran) under `analysis/snapshots/`
and as `simulator/` siblings, `analysis/proof_session.json` and
`analysis/proof_verdict.json`, and under `environment/` the plan and its
sha256, the SUT environment, the clocks (guest and host, their offset
informational: no criterion involves timing), the containers before and
after, and the helper file check.

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
| `EGW_HEALTH_LIMIT_S` | `1800` | bounded wait for the six services `running` and `healthy` (`gate_health.sh`, `persistence.sh`; `broker_measure.sh` and `proof.sh` default to `1200`, the 20-minute rule of ADR 0011) |
| `EGW_HEALTH_STEP_S` | `15` | how often that wait takes a sample; every sample is kept |
| `EGW_READY_LIMIT_S` | `3600` | bounded `wait_ready` after the restart (runbook 6.5: an hour is the upper bound for the JVM start-up under TCG; `proof.sh` defaults to `300`, its own choice for its `ready` step: the ADR gives no `/ready` figure) |
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
