# Acceptance and protocol update — proposals of 2026-09-19

**Written:** 2026-09-19.
**Status: PROPOSED — for review, not adopted.**

> **Nothing in this file is adopted, sent to the supervisors or decided.** It is
> the bounded acceptance and protocol update asked for by the project review of
> 2026-09-19 (sections 4.3 and 4.4, and step 3 of section 7). It changes no
> protocol constant, validator, harness behaviour, run result, gate or claim,
> and no command or criterion of a runbook step. The one runbook change made
> alongside it on 2026-09-19 is a change of form only: the two steps that
> stood in prose, the test 4 sequence reset and the test 7 Ditto repeat, were
> moved into fenced blocks with their commands unchanged (item 4). The
> proposals are the Developer's; the principles they implement are set by the
> project review. Each item below names who decides it. Adopting an item is a
> separate, explicit decision of the student, recorded in
> [`LOG.md`](../../../LOG.md) with its date and basis; the canonical texts it
> touches change only afterwards, in a change made for that purpose, the form
> change of item 4 apart. Merging this file adopts nothing.
>
> **Test acceptance remains paused at the student's request, and the guest stays
> off.** Nothing here resumes it, runs a test, admits evidence, closes G2–G7 or
> admits a claim.
>
> **Old runs keep their original rules.** `smoke_sequence-r01` and `-r02` and
> `controller_restart-r01` and `-r02` stay invalid under the rules they were run
> under. The integration battery of 2026-09-18 stays a locally hash-sealed
> candidate archive, not incorporated into or admitted by the project evidence
> record: all 312 entries of its `SHA256SUMS` verify, and an outer archive seal
> does not make a nested invalid run valid. No proposal below is applied
> retroactively.

**Where the facts come from.** Every fact below was verified on 2026-09-19,
read-only, against the run directories under `~/egw-tcg/pilot/results/raw/`,
the candidate archives `~/yocto/evidence-candidates/2026-09-18-integration-tests/`
and `~/yocto/evidence-candidates/2026-09-19-sampler-fix/` (WSL2 home of the
workstation), and the source at `dev` revision `40aae52` and at
`fix/resource-sampler-cgroup` revision `aa7440d`. Line numbers are those of
`dev` at `40aae52` unless another revision is named. Every figure taken from an
invalid run is a **diagnostic count, not a campaign result**, and no figure here
is a performance result: the guest is ARM64 emulated by QEMU/TCG on an x86-64
host ([adopted plan, section 3.5](../INTEGRATED_DEVELOPMENT_PLAN_2026.md)).

## Summary

| # | Item | What the Developer proposes | Who decides |
|---|---|---|---|
| 1 | Short-run selection | Keep the 30-distinct-instant minimum and the 60 s confirmation rule; run the next instrumentation acceptance as a nominal entry with its declared duration unchanged, under a new run identity | The student; a shorter dedicated entry or a change to the counting rule only as a versioned protocol change; the values stay with D007 |
| 2 | Deliberate restart | A designated outage window for the restarted container only, opened and closed by independently recorded lifecycle events and capped, with the ordinary 5 s rule everywhere else; fifteen regression cases | The student adopts or declines the rule, prospectively; its numbers belong to D007; the freeze is G4 |
| 3 | Late delivery | Diagnose under unchanged deadline semantics; confirm the restart queue finding from guest-side evidence; take a separate design decision on the restart path | The student (design decision); a lowered workload only as a prospective protocol decision at G4; the deadline is not open to decision |
| 4 | Test 4 sequence reset | Run `itest-dup-02` after resumption (and the Ditto half of test 7, dropped by the same cause) | The student, when directing resumption |
| 5 | Instrument binding | Every run records the exact helper, deployment configuration, controller image and collector hashes | The student |
| 6 | Acceptance sequence | One fresh bounded acceptance pair first; stop on failure; then only affected or missing checks; then G3 | The student's resumption instruction; gate outcomes only in the gate decision log |

## 1. Short-run selection

### Verified facts

- **The count is taken over the whole resource file, not the measured window.**
  Ingestion requires at least 30 data rows, at least 30 distinct instants
  pooled across containers and, with more than one container, at least 30 per
  container (`MIN_RESOURCE_SAMPLES` and `MIN_DISTINCT_SAMPLE_INSTANTS`,
  [`resources.py`](../../../src/egw_experiments/resources.py) lines 80 and 88;
  counting at lines 382–461). Only span coverage (at least 90 % of the measured
  window) and gaps (at most 5 s, `MAX_SAMPLE_GAP_S`) are judged against the
  window (lines 525–559 and 591–659).
- **The harness stops the collector before the 60 s confirmation window, not
  after it**: the stop hook runs after the measured run and before the wait
  ([`run.py`](../../../src/egw_experiments/run.py) lines 1941–1943). The
  docstring of `RESOURCE_WINDOW_COVERAGE_MIN_FRAC` (`resources.py` lines
  92–95) says the opposite, and so do, on `fix/resource-sampler-cgroup`, the
  collector's header and the runbook's revised collector paragraph.
- **A condition with no warm-up gives the collector almost no pre-roll.** In
  the four timed runs the start hook ended 0.04–0.06 s before the measured
  start, and `run.py`, `cli.py` and `campaign.py` have no pre-roll or post-roll
  option. The collector's first sample only primes the CPU delta and writes no
  row, so the first rows of the r02 files fall **inside** the window: 1.406 s
  after its start in `smoke_sequence-r02` and 1.656 s in
  `controller_restart-r02`.
- **`smoke_sequence-r02` failed only the count rule**: 150 rows, 25 distinct
  instants per container, a 29 s span. Its span coverage (95 %) and its edge
  gap (1.4 s) passed. With that span, even a perfect 1 Hz collector would have
  reached exactly 30 instants, with no margin (derived, not observed).
- **The runbook already has the fall-back.** When a 30 s smoke is marked
  invalid for coverage it says to "repeat with `--run-id` of a nominal entry and
  `--duration` untouched" ([runbook](../../setup/qemu_integrated_gateway.md),
  line 1028). The nominal condition declares a 600 s measured window after a
  120 s warm-up ([`protocol.py`](../../../src/egw_experiments/protocol.py)
  lines 281–282), and the harness starts the collector before the warm-up, so
  the warm-up already gives the collector a pre-roll.

### Proposal

1. Retain the 30-distinct-instant minimum and the 60 s confirmation rule,
   unchanged.
2. Run the next instrumentation acceptance as a **nominal entry of the pilot
   plan with its declared duration unchanged**, under a new run identity, and
   record it as an acceptance of the collector and the harness. It is **not** a
   passed 30-second smoke, and it neither completes nor counts towards the ten
   official `smoke_sequence` repetitions (claim C14).
3. Report its delivery outcome as measured, under the unchanged deadline. With
   the throughput diagnosed in item 3, a 600 s entry at 11.2 msg/s may well
   accumulate a backlog and late confirmations; that would be a delivery
   finding, not an instrumentation failure, and not a reason to change the
   entry.
4. A dedicated shorter acceptance entry may be proposed instead only
   prospectively: versioned in the protocol before it is executed, with an
   explicit margin, and never used to relabel a run already made. For scale only
   (a model, not a measurement): with a collector at about 1 distinct instant
   per second, about 4 s of pre-roll and 2 s of post-roll give at least 32
   instants for a 30 s window; at 0.84 distinct instants per second, 10–12 s of
   pre- and post-roll together give about 30.7–32.4, which is marginal. The
   harness has no pre-roll option today. Wrapping a hook in a shell with a
   `sleep` would be undocumented and would also delay the confirmation wait and
   the event fetch, so it is not proposed.
5. Correct the "stopped after the confirmation window" statements to match the
   code, in the focused sampler change (project review, section 7, step 2).
   This is a factual correction and needs no decision.

### Open questions for the decision

- **Should the count be taken inside the measured window?** Today rows before
  the start and after the end of the window count towards the 30. The r02 smoke
  window contained exactly 30 whole-second stamps, so 30 in-window instants in a
  30 s window would need a perfect 1 Hz collector that never misses; at 0.9
  distinct instants per second or fewer, at most 27 fit. Counting inside the
  window therefore means a longer minimum window for instrumentation acceptance,
  or a minimum scaled to the window. Keeping whole-file counting means that
  rows outside the window keep contributing to a rule that is about the window.
- **Should the validator reject duplicate `(container, ts)` rows?** It does not
  today: such collisions pass ingestion silently and only lower the distinct
  count. The `aa7440d` collector's idle cadence check wrote 29 rows per
  container from 30 samples but only 26 distinct timestamps, so at least three
  sweeps shared a whole-second label; the r02 files, from an earlier collector,
  have none. The alternatives are to reject such rows, or to require sub-second
  timestamps so that separate sweeps cannot collide.

### What stays unchanged

The 30-instant minimum, the 90 % span-coverage rule, the 5 s gap cap, the 60 s
confirmation window, the declared duration of every condition and the
ten-repetition smoke condition. `smoke_sequence-r01` and `-r02` stay invalid.

### Who decides

The student decides whether the next instrumentation acceptance uses the nominal
entry; the option is already in the runbook, so it moves no rule. A dedicated
shorter entry, or a change answering either open question, would be a versioned
protocol change decided by the student before any run uses it. The numerical
values themselves (30 instants, 90 %, 5 s) are among the thresholds that D007
asks the supervisors to confirm before `exp-v1`
([decision log](../supervisor_decision_log.csv)); D007 is unsent.

## 2. Lifecycle-aware rule for a deliberate restart

### Verified facts

- In `controller_restart-r02` the harness recorded the restart command from
  00:18:15.344Z to 00:18:36.134Z, exit code 0. The controller's resource series
  has **one gap of 6.0 s, 00:18:29Z to 00:18:35Z, inside that interval** to the
  resolution of the data (whole-second guest labels against host timestamps in
  milliseconds). It is the only gap above 2 s in any series of the file; the
  controller has 500 distinct instants and each of the other five containers
  504. Ingestion rejected the file, and the rejection names that gap and
  nothing else.
- The controller series kept producing rows until 00:18:29Z, 14 s after the
  command started, and came back at 00:18:35Z with a memory figure that fits a
  freshly started process.
- The same run's `controller_metrics.csv` has **26 failed polls** (recorded in
  the manifest as `poll_errors`, because a failed poll writes no row) and a
  **29.115 s gap**, from 00:18:19.443Z to 00:18:48.558Z. That gap is **not**
  inside the command interval: it begins 4.1 s after the command started and
  ends 12.4 s after the command returned. Every controller counter restarts at 0
  after it (a new process).
- The harness records the restart command only: its text, its start and finish
  times and its exit code ([`run.py`](../../../src/egw_experiments/run.py)
  lines 1210–1233). It records no container or process identity, no readiness
  and no stop or start time of the container. A command that does not exit 0
  already makes the run invalid (lines 1035–1038), and the command is bounded
  by the harness timeout of 300 s (line 224).
- The existing C12 recovery criteria
  ([`analyze.py`](../../../src/egw_experiments/analyze.py), from line 2704)
  already require downtime evidence, the metrics endpoint and ingestion resuming
  within `RESTART_RECOVERY_MAX_S` of the command's finish (120 s,
  [`protocol.py`](../../../src/egw_experiments/protocol.py) line 168, pending
  supervisor sign-off), and progress after the restart.

### Principles set by the project review (all required)

- Unavailable data stays unavailable: never zero-filled, never interpolated.
- The intentional outage is bounded by independently recorded stop and start
  state, identities and timestamps, never by the largest observed gap.
- The ordinary 5 s limit stays for every other container, and for the restarted
  one outside the designated window.
- Downtime, failed polls and time to readiness are recorded as outcomes; the
  window must not censor a slow or a failed recovery.
- Coverage is checked before and after the outage, including the first
  post-start CPU-delta sample.
- `/ready`, data-path recovery and message reconciliation are required, not
  merely a successful restart command; counter and process-clock identities are
  accounted for.
- **Not** an unconditional increase of the gap threshold, to 6 s or to 30 s.

### Proposal: the designated outage window

**Definitions** (one restart per run, one container):

- **O, the opening**: the harness's recorded start of the restart command.
- **F**: the command's recorded finish.
- **Instance identities**: read on the guest immediately before the command and
  again after it — the container id with its `State.StartedAt` and
  `State.FinishedAt`, and the controller's `/metrics` `started_at`. The restart
  must show a new instance (a new `State.StartedAt` and a new `started_at`);
  otherwise no window exists and the restart is not shown.
- **C, the closing**: from O onwards the harness polls `/metrics` and then
  `/ready` at a declared cadence (1 s proposed) and records every attempt with
  its time and result. C is the recorded time of the first successful `/ready`
  in a poll whose `/metrics` answer already carries the new `started_at`. A
  `/ready` answered by the old process therefore cannot close the window; in
  r02 the old process was still answering `/metrics` about 4 s after O.
- **The cap**: C may not be later than F + `RESTART_RECOVERY_MAX_S`, the same
  bound and origin that the existing recovery criteria use, so the exemption can
  never outlast the recovery criterion and no new number is introduced. If no
  qualifying `/ready` has been seen by then, the window closes at the cap and
  **the run fails its recovery criteria**: the window does not grow. The failed
  recovery is retained, analysed and reported as a valid negative result, not
  excluded (project review, section 5.1), and the missing readings after the cap
  are judged by the ordinary rule, not exempted, so neither failure hides the
  other.

**Rules:**

1. **Scope.** Only the container named in the restart record is exempted, and
   only inside [O, C]. Every other container keeps the 5 s rule throughout,
   inside [O, C] included. One designated window per run; any other container
   whose instance changes during the run receives no exemption.
2. **Coverage before and after.** For the restarted container, the existing
   window rule is applied to two sub-windows instead of one: from the measured
   start S to O, and from C to the measured end E. In each, the distance from
   the sub-window's start to its first sample, every consecutive pair of
   samples, and the distance from the last sample to the sub-window's end must
   each be at most 5 s. A pair that straddles O or C is measured only over its
   part outside [O, C]. Rows of the old instance between O and its stop are
   real readings and are kept.
3. **First post-start sample.** The first row of the restarted container after
   the new instance's recorded start must be a CPU delta taken wholly within the
   new instance — at least one sampling interval after that start, because the
   collector's priming sample writes no row — and it must fall no later than 5 s
   after C.
4. **No fabricated readings.** A row of the restarted container timestamped
   after the old instance's recorded stop and before the new instance's recorded
   start is rejected, whatever its values: there was no instance to measure.
   Rows are never zero-filled or interpolated to close a gap, inside or outside
   the window.
5. **Clock domains.** O, F, C and the poll times are on the harness clock;
   resource rows and the container's `StartedAt` and `FinishedAt` are on the
   guest clock, and the rows carry whole-second labels. A comparison within the
   guest clock allows the 1 s label resolution only. A comparison across the two
   clocks also allows a host–guest offset bound measured and recorded for the
   run (proposed: at the start and the stop hooks). The tolerance is declared
   before execution and recorded in the manifest; it is never derived from an
   observed gap, and without a measured offset no window is granted.
6. **Process-clock identity.** The controller's monotonic clock is assumed to
   continue across a container restart; the runbook lists that as reasoned, not
   observed. The offset between the harness clock and the controller clock, from
   `/metrics` reads before and after the restart, must agree within a declared
   tolerance; otherwise records of the old instance cannot be placed against the
   deadline, and the run says so.
7. **Controller metrics.** The same window bounds `controller_metrics.csv`.
   Failed polls inside [O, C] are counted and reported as outcomes; a gap above
   5 s outside it is an instrumentation failure and is reported as one. The
   existing downtime-evidence criterion (a metrics gap above 5 s straddling the
   restart, or a counter reset) is unchanged.
8. **Delivery is not exempted.** Every message published during the run, inside
   the window included, is accounted by identity under the unchanged
   controller-clock deadline. Data-path recovery means that messages published
   after C are accepted by the new instance (the existing functional-recovery
   criterion). The counters of the old and the new instance are separate series
   and no difference is taken across the reset. Because the old instance's last
   counters cannot be observed after its last answered poll — in r02 it wrote
   58 acknowledgements after that poll — reconciliation across the restart is by
   message identity from the event log, not by counters.
9. **Outcomes recorded per run:** O, F and C, and whether C came from `/ready`
   or from the cap; the downtime C − O; the time to readiness from O and from F;
   the failed polls inside the window; the last row of the old instance and the
   first row of the new one; the first `/metrics` answer of the new instance;
   both instance identities; and the measured clock offsets.

**Where it would live.** `validate_resources_csv` in `resources.py` would
receive the window and the identities from the manifest; `run.py` would record
the identities, the polls and the offsets; `analyze.py` would report the
outcomes. The regression cases run against the production thresholds (30
instants, 5 s), not against the reduced fixture of the `aa7440d` cadence test
(8 rows, 4 instants).

**Not evaluable retroactively.** The r02 records carry no `/ready` log, no
instance identity and no measured offset, so they cannot be evaluated under this
rule; they stay invalid under the rule they were run under.

### Regression cases a validator would need

| Case | Input | Expected |
|---|---|---|
| R1 | Restarted container: a 6 s gap wholly inside [O, C]; first post-start row within 5 s of C; ordinary cadence elsewhere | Accepted |
| R2 | As R1, with a 30 s gap wholly inside a 40 s window | Accepted: the window comes from the lifecycle record, not from the gap |
| R3 | Restarted container: a 6 s gap that ends before O, or one that starts after C | Rejected |
| R4 | Last row of the restarted container more than 5 s before O | Rejected (coverage before the outage) |
| R5 | First post-start row more than 5 s after C | Rejected (coverage after the outage) |
| R6 | First post-start row less than one sampling interval after the new instance's recorded start (a CPU delta that would span the restart) | Rejected |
| R7 | No qualifying `/ready` by F + `RESTART_RECOVERY_MAX_S`: the window never closes | Window closed at the cap; rows after it judged by the 5 s rule; recovery criteria fail; run retained and reported as a failed recovery |
| R8 | `/ready` succeeds while `/metrics` still shows the old `started_at` | Does not close the window |
| R9 | A 6 s gap on a non-restarted container, inside [O, C] | Rejected |
| R10 | A zero-filled row: the restarted container with zero CPU and memory, timestamped between the old instance's stop and the new one's start; likewise a row with interpolated values there | Rejected |
| R11 | A gap on the restarted container, but the restart record lacks the instance identities, the `/ready` log or the measured offset | No window: ordinary 5 s rule, rejected |
| R12 | A window claimed for a container other than the one in the restart record, or a second window in the same run | Rejected |
| R13 | A window edge overrun by less than the declared tolerance; by more | Accepted; rejected |
| R14 | Failed metrics polls inside [O, C]; a metrics gap above 5 s outside it | Counted as an outcome; reported as an instrumentation failure |
| R15 | Messages published inside [O, C] with no accepted record by the deadline | Counted as lost or late exactly as outside the window: the window changes no delivery figure |

### What stays unchanged

`MAX_SAMPLE_GAP_S` (5 s) for every series outside the window; `RESTART_RECOVERY_MAX_S`
and the existing C12 criteria; the requirement that the restart command exits
0; delivery accounting and the deadline. The old runs stay invalid under their
original rules. The G0 decision recorded on 2026-09-19 carries the fault-window
rules to G4 as a residual obligation: this is the proposal for that rule, not
its adoption.

### Who decides

The student decides whether to adopt the rule, prospectively, before any
controller-restart run is executed under it. Adoption means a new protocol
version, with the implementation and the regression cases above in a change
made for that purpose. The numerical values it relies on — the cap, the 5 s
limit and the clock tolerances — fall under D007, which asks the supervisors to
confirm the thresholds before `exp-v1` and is unsent. The protocol freeze is the
G4 decision and stays separate.

## 3. Late delivery is its own issue

### Verified diagnostic counts (not campaign results)

Counted by exact `message_id` against the controller-clock deadline of each
run's own manifest (the controller marker plus 60 s); an accepted record later
than the deadline is late and does not rescue the message.

| Run | Unique published | Accepted by the deadline | Accepted after it, in the fetched log | No accepted record in the fetched log |
|---|---:|---:|---:|---:|
| `smoke_sequence-r02` | 336 | 236 | 15 | 85 |
| `controller_restart-r02` | 6,720 | 3,795 | 24 | 2,901 |

- The fetched event log is a single snapshot, taken about 2.6 s after the
  deadline while records were still being appended.
- In the smoke run the 85 are the last 85 messages published, contiguous. The
  controller's accepted counter reached exactly 336 before the next run began,
  so they were a pure backlog, accepted later. That is a check on the counter,
  not on message identities.
- The battery of 2026-09-18 shows the same pattern under the same deadline:
  132 of 1,277 valid events late in test 3; 326 of 2,016 late in test 5; 1,012
  of the 3,298 accepted late in test 7. Test 2 met its criterion with its last
  acknowledgement 3.1 s before the deadline, and an earlier 672-message
  preflight run had 378 late. In every battery run the controller had received
  every message by the marker: the lateness arises in processing, not in
  transport.

### Finding 1 — throughput

Under QEMU/TCG the controller's single consumer, which processes messages one at
a time with one sequential Ditto request each
([`service.py`](../../../src/egw_controller/service.py)), sustained about 3–8
acknowledgements per second against a publishing rate of 11.2 msg/s. The queue
grew by 4.7–10.6 messages per second; latency was 50–86 s at the median and
69–157 s at the 95th percentile. The broker kept up (median transit from publish
to receive 2–14 ms).

### Finding 2 — the restart appears to discard the controller's in-memory queue

- Of restart r02's 2,901 messages without an accepted record, about 765 fit the
  backlog: a contiguous tail published in the last 68 s of the run, which the
  new process still had queued when the log was fetched.
- About 2,136 do not fit it: 1,765 were published before the restart (a
  contiguous tail, from 142 s to 300 s into the run), and about 371 between the
  restart command and the new process's first receive.
- The old process wrote its last acknowledgement about 14.7 s after the command
  started, more than five minutes before the fetch, and the event file is
  append-only and flushed per line, so its complete output is in the fetched
  copy. The new process started with its counters and its queue at 0,
  processed in order and never received a message published before about 33 s
  after the command. No redelivery is visible.
- The mechanism in the code fits this. The queue is an in-memory
  `asyncio.Queue` (`service.py` line 150). The MQTT client hands each message to
  it from its message callback (`mqtt.py` line 187), and the QoS 1
  acknowledgement to the broker follows when that callback returns, that is, on
  enqueue. The client uses the default clean session with a fixed client id,
  `egw-controller-<egw_id>` (`mqtt.py` lines 73–76). Messages queued but not
  processed when the process stopped, and messages published while no session
  existed, would therefore not survive a restart. The last answered poll before
  the restart showed 1,867 queued, which cannot drain at 5–8 per second in the
  seconds a container stop allows.

**Limits of both findings.** They come from two invalid runs and are emulated.
The guest-side event log on the data disk, the twins' `ingestion.accepted_count`
and the container logs were **not read**; the stop timeline is inferred; no
permanent loss is asserted. The controller code is identical between the
harness commit of the r02 runs (`8e88670`) and `dev`, but the commit of the
image deployed in the guest was not verified.

**Why it matters.** Finding 2 bears directly on claim C12, whose acceptance
includes delivery across the restart
([claim matrix](../../claim_evidence_matrix.md)), and on RQ2. It is a design and
data-path issue, not only a matter of emulator speed.

### Proposal

1. Diagnose the processing and load behaviour under **unchanged deadline
   semantics**: the deadline stays the controller marker plus 60 s, and a late
   record stays late.
2. After resumption, and before any restart run is repeated, confirm or refute
   Finding 2 from the guest-side evidence of `controller_restart-r02`: its full
   event log on the data disk, the twins' ingestion counters and the controller
   container logs, read-only.
3. If it is confirmed, take a **separate design decision** on restart-safe
   delivery before C12 evidence is collected again. Directions for that
   decision, none of them assessed here: a persistent MQTT session, so that the
   broker holds QoS 1 messages for the fixed client id while no session exists;
   acknowledging a message to the broker only after it has been processed; a
   shutdown drain bounded against the stop timeout. Each interacts with duplicate
   suppression and with C12, which is why this is a decision and not a patch.
4. Make accounting completeness visible: record the controller's queue depth
   and counters when the event log is fetched, and take a second, diagnostic
   copy of the log after the queue has drained, so that "no accepted record"
   splits into "still queued at the fetch" and "never processed". The verdict
   still uses the deadline exactly as now; the second copy rescues no late or
   missing message.
5. Future QEMU workloads are lowered only through an explicit, prospective QEMU
   protocol decision taken before execution. A deadline is never moved after
   lateness has been observed.

### What stays unchanged

The 60 s confirmation window and the controller-clock deadline; the
classification into in time, late and missing; and the test 5 result, which
fails its stated temporal criterion — 2,016 valid events all eventually
accepted, but only 1,690 within the deadline and 326 late, where the runbook
requires `lost = 0` and `late_confirmations = 0` — and stays a failure. A result
worse than expected at the nominal rate remains a sizing finding for the pilot,
never absorbed by changing the protocol (adopted plan, G3 criteria in section
4.3).

### Who decides

The design decision on the controller's restart path is the student's, recorded
as a separate decision (for example an architecture decision record) once the
guest-side evidence has been read. A lowered QEMU workload is a prospective
protocol decision of the student and belongs to the G4 protocol freeze, where
the loads are carried. The deadline is not open to decision.

## 4. Test 4 sequence-reset coverage

### Verified facts

- The runbook requires a sequence reset, which at `40aae52` stood in the prose
  of test 4's expected results: `run_test itest-dup-02 42 --scenario smoke
  --duration 60` must give `lost = 0` and every `delta` line `OK`
  ([runbook](../../setup/qemu_integrated_gateway.md), line 1085 at `40aae52`).
- **It was not run.** No `itest-dup-02` file and no `dup-02` string exists
  anywhere in the battery archive, and the executed test 4 block has no
  sequence-reset step. The extraction script used for the battery took only
  fenced code blocks, and this step was prose.
- The same cause dropped the Ditto repetition of test 7 (`itest-ditto-fault-01`,
  runbook line 1146): no `ditto-fault` string exists in the archive, so test 7
  covers only its MongoDB half. The same verification found it; it is recorded
  here because it is the same defect.
- On 2026-09-19, in the same change as this file, both prose steps — the test 4
  sequence reset and the test 7 Ditto repeat — were moved into fenced blocks of
  the runbook with their commands unchanged, each with a dated note that it was
  not run. The test 7 repeat sits under a heading of its own, because the
  runbook's tests (`src/tests/test_runbook_itest_helpers.py`) read the fenced
  commands of the test 7 section as a single run. That is a change of form
  only: no command, criterion or result changed, and neither sub-check has been
  run.
- Test 4's duplicate handling itself was demonstrated: 672 duplicates, none
  accepted twice. Its post-replay warning, "IMPLAUSIBLE controller confirmation
  marker", is explained: the deliberate replay is received after the window, and
  the guard compares the deadline with the latest receive time over all records.
  The in-window figures are unaffected.

### Proposal

1. After resumption, run `itest-dup-02` as the runbook states, under its
   unchanged criteria, or map an equivalent record if one is shown to exist;
   none was found in the archive.
2. Run the Ditto half of test 7 in the same way.
3. Keep every executable step of a test inside a fenced block. The two steps
   found in prose were moved on 2026-09-19, as above; a later runbook change
   checks that no other executable step still stands in prose. Treat an
   extraction as incomplete unless it accounts for every step of its section.

### What stays unchanged

Test 4's criteria and its duplicate result of 2026-09-18. The explanation of the
warning changes no figure.

### Who decides

The student, when directing resumption. Both steps are already required by the
runbook, so no rule changes, and moving them into fenced blocks changed their
form only. Whether a mapped equivalent record satisfies the test 4 step is
assessed with G3.

## 5. Binding each run to its exact instrument

### Verified facts

- Both r02 runs used an intermediate collector, sha256
  `f17bdd8c66da3fe376f143016c00e733118abb93879f143d596a429e15e4e47a`, whose
  installation record dates from 00:03:45Z. That hash matches no committed
  version of the collector and no copy found in the workstation's working trees,
  so the code that produced both r02 files is not preserved.
- The pushed `aa7440d` version, sha256
  `b7aeddba68698c894b131789ccca6d144cd47e672ee8200d06b6673cacfc136e`, was
  installed at 00:26:31Z, after both r02 runs had begun (00:09:00Z and
  00:13:14Z). On the guest it was exercised only idle, in a 30-sample cadence
  check; the harness run announced after it (`smoke_sequence-r03`) left no run
  directory.
- Both r02 manifests record the harness commit `8e88670`, whose collector is the
  earlier docker-stats version, and carry no collector hash, so read alone they
  attribute the r02 series to the wrong code. The `aa7440d` commit message cites
  cadence figures ("median gap of 1.0 s per container") that come from the r02
  runs.

### Proposal

Every future run records in its manifest, at run time: the sha256 of the
collector as installed on the guest, read by the start hook; the sha256 of the
host-side helper files the run uses; the hashes of the deployment configuration
(the Compose file and the image lock file, never the secrets); the controller
image digest with its verified build record; and the harness commit with its
clean or dirty state. A run whose collector hash matches no committed version
cannot serve as instrumentation acceptance, and cadence figures are attributed
only to the collector version that produced them.

### What stays unchanged

The identity binding already required of every run by the adopted plan
(conditions common to G2–G7, section 4.3); this adds fields to it and moves no
threshold. The r02 runs stay invalid.

### Who decides

The student adopts or declines the recording requirement. Its implementation is
a harness change, reviewed like any other.

## 6. The acceptance sequence after resumption

### Proposal (project review, section 7, steps 4–6)

1. **Preconditions**: the student's instruction to resume; a decision, to adopt
   or to decline, on items 1, 2 and 5; and the focused sampler change of the
   project review's step 2.
2. **One fresh bounded acceptance pair first**, under new run identities: the
   nominal entry of item 1 and one `controller_restart` entry, under the rule of
   item 2 if it is adopted — the pair mirrors the two r02 attempts. Each entry
   must show **resource ingestion** (a valid `resources.csv` in a sealed run
   directory) **and end-to-end deadline accounting** (every published message
   classified by identity under the controller-clock deadline) **and**, for the
   restart entry, **recovery evidence** (`/ready`, the existing C12 criteria and
   the outcomes of item 2).
3. **Stop escalating on failure.** If either entry fails, diagnose before
   anything else is run; the failed attempt is retained and reported.
4. **Then only the affected or missing checks**: the timed harness parts of
   tests 1 and 6; the test 4 sequence reset and the Ditto half of test 7
   (item 4); and the test 5 deadline issue, after the diagnosis of item 3 and
   under unchanged deadline semantics.
5. **Reuse the unaffected evidence** of 2026-09-18 (tests 2 and 8, the tested
   checks of test 9, the rejection behaviour of test 3, the duplicate handling of
   test 4 and the MongoDB fault behaviour of test 7) only where source and
   configuration identity and the applicability of the criterion are shown for
   it; otherwise rerun.
6. **Then assess G3**, and only after it the bounded pilot and the G4 freeze.
   No jump to the 95 runs or to the 24-hour soak.

### What stays unchanged

The G3 criteria of the adopted plan (section 4.3). No gate outcome changes here.

### Who decides

The student's resumption instruction starts step 1, and nothing here authorises
it. Gate outcomes are recorded only in the
[gate decision log](../gate_decision_log.md), with their decision authority and
their decision record.
