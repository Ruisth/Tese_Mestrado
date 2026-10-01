# G3 pending decisions (2026-09-29)

**Status: ADOPTED by Rui on 2026-09-30, prospectively and with conditions** (see
["The decision of 2026-09-30"](#the-decision-of-2026-09-30) below). Sections 1 to 4 keep the text as proposed on
2026-09-29, as the historical proposal. Where the decision differs from it, the decision governs. *(Until
2026-09-30 this line read: "PROPOSED, for Rui's decision. None of these proposals is adopted.")*

This page covers four decisions that must be taken before a qualifying G3 run. The
[G3 readiness map](../g3-readiness-map-2026-09-29.md) raises them as its decisions 1, 2, 3 and 5. For each one,
the page gives the current rule and where it comes from, the exact wording proposed, the families it affects,
what adopting or declining it does, and a recommendation. The map's decision 4 (lock the candidate and authorise
the battery to resume) stays with Rui and comes after these four.

*The state before 2026-09-30, kept as written. The first bullet is overtaken by the decision of 2026-09-30; the
other three still hold.*

- Merging this page adopts nothing.
- G3 stays paused and `Not decided` ([gate decision log](../gate_decision_log.md)).
- Freezing the candidate and lifting the pause remain a later, explicit decision.
- Nothing below applies the finite proof's own exceptions (E-12 and the N1 naming,
  [ADR 0011](../../adr/0011-controller-restart-recovery.md), decision of 2026-09-29).

**Implementing any of these in validators, `analyze.py`, `delta`, the evaluator or gate criteria needs Rui's
dated decision.** That decision is recorded in [LOG](../../../LOG.md). The implementation then comes as a change
of its own, with its own regression tests. *(2026-09-30: the decision was taken on that date. It is recorded in
LOG #C049, and the change that records it implements it offline, with its own regression tests.)*

## At a glance

| # | Decision | Recommendation | If declined |
|---|---|---|---|
| 1a | A resource gap inside a container-down interval that the captured `die`/`start` events prove, at a restart | Adopt, prospectively, before T6 runs | T6's harness run stays invalid: every restart recorded so far left a 6–9 s gap |
| 1b | T1's harness run on an unused `nominal` entry instead of the 30 s smoke | Adopt | The 30 s smoke runs with no margin for the 30-instant rule |
| 2 | An N1 identity reported in its own column; `lost` and `MISMATCH` unchanged | Adopt the reporting column; no criterion changes | Same verdicts; an N1 case reads as an unexplained loss |
| 3 | The list of timed families; T3 not timed (option 3-A); T6's zero lost taken from C12 | Adopt with option 3-A | T3's status stays ambiguous; T6 keeps two sources that disagree |
| 4 | T4's duplicates judged per identity; redelivery duplicates reported apart | Adopt, prospectively, before T4 runs | One reconnection during the replay can fail T4 |

## The decision of 2026-09-30

### Authority

- On 2026-09-30 Rui adopted the Project Manager's recommendations on this page, with their conditions. They are
  those of the Project Manager's register entry "2026-09-30 17:01 WEST — PR52 favourable; G3 recommendations
  remain prospective", held outside the repository.
- His words: "As minhas respostas são as mesmas dadas pelo Senior Project Manager" ("My answers are the same as
  those given by the Senior Project Manager").
- For the end of T3's collection (decision 3) he chose "Cópia pós-drenagem" ("post-drain copy").
- It is the student's decision. It is not a gate decision: G3 stays paused and `Not decided`
  ([gate decision log](../gate_decision_log.md)). It is not a supervisor decision, and it records none. D007 stays
  unsent.
- Everything below is **prospective**. It applies to runs made after it, never to a run already made.

### The adopted rules

This section records the rules as adopted. Like every page in this directory, it is not itself the text in force:
that is the [runbook](../../setup/qemu_integrated_gateway.md)'s section 7 and the code named below (LOG #C049).
Sections 1 to 4 further down are the proposal as written on 2026-09-29.

**1a. The proved-down interval at a controller restart.**
- *Where it applies.* Only at the harness's run-time ingest of the collector file (`run.ingest_resources`), only in
  a `controller_restart` run, and only when the `StartedAt` record was fetched: the option `--fetch-started-at-cmd`
  was given, and its fetch ended 0 with a non-empty `logs/sut/controller-started-at.txt`. `collect` does not apply
  it, and does not qualify a late file for a run whose restart lifecycle (`die` and `start`) is recorded.
- *Without the option* there is no interval, and every result is byte-identical to the rule before. With the
  option but no usable record there is no interval, and a failed fetch is a validity reason (below). The finite
  proof never passes the option, so it is unchanged.
- *The container.* C is `egw-controller-1`, the container T6's restart names. The capture's `container=` and the
  `StartedAt` record's container must both be C.
- *When the interval exists.* All five must hold. Otherwise there is no interval, the reason is recorded, and the
  ordinary rule decides the file exactly as before.
  1. The restart record shows that the restart ran with return code 0.
  2. The docker-events fetch ended 0 and `logs/sut/docker-events.log` exists. `logs/sut/docker-events.coverage.txt`
     starts with `coverage=complete`, names `container=egw-controller-1`, expects `die` and `start`, and gives
     whole-number bounds t0 and t1 (`requested_since_guest_epoch`, `requested_until_guest_epoch`).
  3. In the capture window [t0, t1 + 1), C has exactly one `die` and exactly one `start`, the start strictly after
     the die, both with the same container id. D is the die, S is the start. None, several, the wrong order or
     different ids: no interval.
  4. The `StartedAt` record parses. Its container id is the pair's, it was read at or after S (its guest epoch is
     taken before the inspect), and |S − `StartedAt`| ≤ 1 s.
  5. C has a row stamped at or before sec(D) and a row stamped after sec(S).
- *The checks on C.*
  - A row stamped after sec(D) and before sec(S) is rejected: no instance was running to measure. Its values do
    not matter.
  - A row stamped in sec(S) itself is rejected: the first row after S must come at least one sampling interval
    (1 s) after sec(S).
  - The one pair (last row at or before sec(D), first row after sec(S)) is replaced by two gaps. Each is judged
    against `MAX_SAMPLE_GAP_S` (5 s), like any other gap. The edge before is sec(D) minus the last row before. The
    edge after is the first row after minus sec(E).
  - When the interval is capped (S later than D + 120 s), the edge after includes the time from D + 120 s to S. A
    restart whose S − D exceeds about 124 s therefore leaves the file rejected.
- *Unchanged.* C's other gaps, the head and tail gaps against the measured window, every other container, the 90 %
  coverage, the 30 distinct instants (per container and overall), and the host, numeric and order checks. No row is
  added, removed, zero-filled or interpolated. The file ingested is the collector's file, byte for byte.
- *Recorded.* The manifest key `resources_proved_down`, for every `controller_restart` run given the option: whether
  the interval applied, or why not; C and its container id; D, S and E (ns and UTC text); `capped`; `StartedAt`
  and S − `StartedAt`; S − D and E − D in seconds; the last row before D and the first row after S; both edge
  gaps; and the rejected rows.
- *Reported only.* No delivery, recovery or C12 figure changes. `analyze.py` is unchanged: its per-run
  `resources_per_container_sufficient` flag still reads false for C when C's gap exceeds 5 s, so no saturation
  reading uses that run.
- *A failed fetch.* A failed `StartedAt` fetch is a failed configured SUT fetch like the others: a validity reason,
  and no interval. The read is `tools/session/fetch_started_at.sh`, which T6's harness line runs against the guest.
- *Limits.* The edges have never been measured under TCG. The guest clock's 1–3 s backward steps are not absorbed.
  Adoption does not make T6 valid or passing.

**1b. T1's harness run.**
- It uses a `nominal` entry of the pilot plan never used on the guest, under its own run identity, instead of
  `smoke_sequence-r01`. The runbook names `nominal-r02`, the first unused entry on the evidence held.
- The harness and the runbook refuse an existing raw directory, so an entry already used is never reused.
- Its declared duration and warm-up are unchanged.
- It is judged by T1's harness Expected list (the artefact chain), under the unchanged ingest rule: 30 distinct
  instants, 90 % coverage, 5 s gaps. Its delivery figures are reported as measured.
- It is not a passed 30 s smoke, not a performance approval and not a successful nominal delivery. It is distinct
  from T1's three wearable functional runs. It does not count towards C14's ten `smoke_sequence` repetitions.

**2. N1 identities, reported only.**
- An identity is reported as `n1_applied_unconfirmed` only if all three hold:
  1. Its only outcome lines are `duplicate` (lines of this run id, in the events copy compared with the post-drain
     `after` snapshot), and it is a valid published identity of the run (in `sent_events.jsonl`, not intended
     invalid).
  2. The run records a source for it. Either a controller death: a restart record whose restart ran with exit 0
     and whose complete capture holds a `die` of `egw-controller-1` inside the capture window (the 120 s replayed
     before RUN_T0 excluded), at most one death per run; it serves an identity only when the run's `/metrics`
     readings (`controller_metrics.csv`) place it first: the new controller process's first reading earlier, on the
     one controller clock, than the identity's first `duplicate` line. Or a connection end that the controller logged under A3
     (the ERROR line "MQTT connection ended by the controller"; an INFO line is a graceful stop, not A3) on the
     identity's own device, whose delivery in progress was received (`received_monotonic_ns`) before the
     identity's first `duplicate` line. Each source explains at most one identity.
  3. On its device, the twin's Δ`accepted_count` between the `before` snapshot and the `after` snapshot taken after
     a quiet drain exceeds the device's `accepted` lines in that events copy by exactly the number of identities
     reported on that device. The twin's `last_seq` is not below each reported identity's `seq`. The absolute
     `accepted_count` is never used.
- *Per device, all or nothing.* If a device has more duplicate-only identities than its surplus, or any of them
  fails a condition, none of them is named: they cannot be told apart.
- *Unexplained.* Every other duplicate-only identity is reported as `duplicate_only_unexplained`, with the failed
  conditions named. When the attribution is not demonstrated (a source not read, a stamp not readable, a death two
  devices would need, a drain not quiet, snapshots not verified), the identity is unexplained, never N1.
- *What it does not change.* The identity stays in `lost` and in every zero-lost criterion. The `delta` line stays
  `MISMATCH`, annotated with the named identities, and the exit codes are unchanged. It is never counted as
  accepted, delivered or on time. There is no exactly-once claim and no fabricated `accepted` record. Without the
  new options, `delta`'s output is byte-identical.
- *Where it lives.* `src/egw_experiments/n1_report.py`; the columns `n1_applied_unconfirmed` and
  `duplicate_only_unexplained` of `processed/recovery_qualification.{csv,json}`; the `itest_reconcile delta` options
  `--n1-report`, `--controller-log FILE` and `--restart-evidence RUN_DIR`.

**3. The timed families, and T3.**
- The timed families of G3 are T1 (each of its three runs), T2, T4's sequence reset `itest-dup-02`, T5, T6 and T8's
  post-reboot smoke.
- Each must meet `lost = 0` and `late_confirmations = 0` under the controller-clock deadline: the marker plus 60 s.
- A family that misses a mandatory deadline is recorded as failed, and G3 is not met on it (ADR 0011, throughput
  choice T1). The miss is also recorded as a sizing finding for the pilot. That record does not turn the failure
  into a pass.
- No deadline, rate, duration or load changes. Sending the throughput question to G4 waives no G3 condition.
- *T6.* Its zero lost is C12's obligation (`delivery_across_restart_zero_lost`: `lost = 0`, late confirmations
  included), read on T6's own `per_run.csv` row (`lost = 0` and `late_confirmations = 0`). It must also meet its
  recovery bound (`RESTART_RECOVERY_MAX_S`, "samples resuming within 120 s"). The Expected list's "reported as
  measured" becomes a report beside that criterion, not a replacement for it. C12's row in
  `acceptance_by_condition.csv` needs the plan's three restart runs, so T6 reads its own row.
- *T3 is not timed:* no delivery deadline is imposed on it. But every valid sent identity of T3's run must have a
  demonstrated `accepted` outcome by the end of the planned collection.
  - That end is the events copy fetched after the run's final drain. `finish` already runs `drained` before its
    fetch, so that copy is T3's post-drain copy. It is kept write-once as `$P/$R.events.post-drain.jsonl` and
    checked by `itest_reconcile acceptance`.
  - A valid identity accepted late, but present as `accepted` in that copy, meets the condition.
  - A valid identity with only `failed`, `duplicate`, other or no outcome lines fails T3.
  - T3 still requires `valid rejected = 0` and every `delta` line `OK`, as written.
  - Its `lost` and `late_confirmations` are reported and decide nothing else for T3.
  - A drain that gives up leaves no post-drain copy. T3 is then not evaluated (a STOP), never passed.
  - This is an explicit prospective reconciliation of the plan's "valid input accepted". It does not claim that the
    old Expected list already checked it.

**4. T4 judged per identity (the replay `itest-dup-01`).**
- *Same process first.* Before any difference of the `after` and `replay` `/metrics` snapshots, the contract's
  same-process checks must hold ([CONTRACTS](../../../src/CONTRACTS.md), "Restart between two readings A and B",
  rule 1): the same `started_at`; `uptime_s` and the cumulative counters `received`, `accepted`, `rejected`,
  `duplicate`, `failed`, `dropped` and `processing_errors` not decreasing; and `mqtt_connection` (cumulative too,
  v1.2) not decreasing. Otherwise the readings are of different processes, and T4 fails.
- *Every replayed identity* (every `message_id` of the replay's `sent_events.jsonl`) must gain at least one
  `duplicate` line from the replay, gain no `accepted` line from the replay, and have at most one `accepted` line
  in total (`double_accepted = 0`, counted on the raw lines).
- *Two counts.* `duplicate_replayed` is the replayed identities that gained a `duplicate` line; it must equal the
  number of replayed identities. `duplicate_redelivery` is every further `duplicate` line added during the replay
  interval.
- *The tolerance.* Extras up to Δ`mqtt_connection` between the `after` and `replay` snapshots are tolerated, and
  labelled "consistent with the reconnection budget". That is a tolerance, not proof that a reconnection caused
  them: Δ`mqtt_connection` counts successful CONNACKs, and an extra duplicate and an unrelated reconnection can
  meet the ceiling together. Extras beyond it fail T4.
- *Reported, deciding nothing.* The `/metrics` Δ`duplicate`, beside the sum of the two counts.
- *Unchanged.* Every other item of test 4's Expected list: `delivered_unique`, `lost`, `late_confirmations` and
  `double_accepted` `UNCHANGED` between the pre- and post-replay accounting; the twins `same` between `after` and
  `replay`; the `/metrics` Δ`accepted` 0, `queue_depth` 0 and the same `started_at`.
- *The sequence reset.* T4 also includes `itest-dup-02` (`run_test itest-dup-02 42 --scenario smoke --duration
  60`), never run so far. It must give `lost = 0`, `late_confirmations = 0` (timed, decision 3) and every `delta`
  line `OK`. A failure of either part is a failure of T4.
- Checked by `itest_reconcile replay-check`. The `after` reading must be quiet (CONTRACTS §5), or the result is not
  demonstrated: a reconnection that reading already counts may be followed by an uncounted redelivery. Then, with k
  reconnections between the `after` and `replay` readings, up to
  k of the added `duplicate` lines may be redeliveries of the first run, so a replayed identity counts only with
  more than k of them; otherwise the result is not demonstrated (exit 5), never a pass. With more than one replayed
  identity, any reconnection during the replay therefore leaves T4 unpassed.

### The conventions pinned for 1a

- **Whole seconds.** The collector stamps whole UTC seconds. sec(x) is the whole second containing x (its floor).
  Every check on C compares whole seconds.
- **One clock.** Every instant of the interval is on the guest clock: the Docker events' `timeNano`,
  `State.StartedAt` and the resource rows.
- **The effective end.** E = min(S, D + 120 s), with 120 s = `RESTART_RECOVERY_MAX_S`. `capped` means S is later
  than D + 120 s. The ordinary edge rule resumes from E, even when S is later.
- **The start's agreement.** |S − `StartedAt`| ≤ 1 s, the resolution of the rows.

### Where the adopted rule differs from the proposal below

- **1a.** The effective end E = min(S, D + 120 s), with the edge after judged from E; the whole-second convention;
  |S − `StartedAt`| ≤ 1 s; exactly one `die` and one `start`, with the same container id, and a `StartedAt` read at
  or after S. The proposal's "If adopted" noted that no step of T6 read `StartedAt` after the restart: T6's harness
  line now does, through `--fetch-started-at-cmd`. The rule applies only at the harness's run-time ingest.
- **3.** Option 3-A as proposed said that a valid message never accepted "shows in `lost`" and decides nothing. The
  adopted rule makes it a failure of T3, judged on the post-drain copy.
- **4.** The proposal's "If adopted" promised that "an unexplained extra duplicate still fails" T4. That promise is
  withdrawn: extras within the reconnection budget are tolerated as "consistent with the reconnection budget", and
  only extras beyond it fail. The full same-process checks are added.
- **1b and 2** are adopted as proposed. The adopted text adds what 1b is not (a performance approval, a successful
  nominal delivery, one of T1's three wearable runs), and states how 2's conditions are read: which lines, which
  sources, and per device all or nothing.

### What it does not change

- **Past runs and verdicts.** No past run, verdict, sealed package or historical figure changes. The finite proof
  runs r01–r03, `controller_restart-r01`/`-r02`, `smoke_sequence-r01`/`-r02`, `nominal-r01` and the battery of
  2026-09-18 keep their records. The past restart runs stay invalid under the rules they were run with.
- **Thresholds and deadlines.** No threshold, deadline, rate, duration, load, coverage or minimum-count rule moves:
  5 s, 120 s, 60 s, 30 instants and 90 % stay, with D007.
- **The finite proof.** Unchanged: ADR 0011's E-12 and N1 naming, `proof_evaluator.py` and the proof's drivers and
  capture scripts. The proof's behaviour stays byte-identical.
- **CONTRACTS v1.2.** Unchanged. Its `lost` (§9) and its "until a separate decision" (§5) still hold: the counting
  decision that ADR 0011 reserves is not taken.
- **`PROTOCOL_VERSION`.** Not bumped: `protocol.py` requires a bump only after G4.

### What it authorises

- Only the offline change that records and implements it (LOG #C049): the harness, the reconcile helper, the
  runbook's test text and their regression tests, run on the host with stubs.
- Nothing on the guest. No session, build, load or run is authorised by it.
- The candidate freeze and the battery's authorisation remain separate decisions (the map's decision 4).
- G3 stays paused.

## 1. Resource gaps at a restart, and the sample count of short runs

These are two separate questions.

### 1a. The interval in which the container is proved to be down

**Current rule.** No sampling gap may exceed `MAX_SAMPLE_GAP_S` = 5 s, in any container's series
([`protocol.py`](../../../src/egw_experiments/protocol.py)). A longer gap makes the validator reject
`resources.csv`, and the harness then marks the run invalid. There is no exemption. The lifecycle-aware rule
proposed on 2026-09-19 ([proposal](acceptance_protocol_update_2026-09-19.md), §2) was never adopted
([runbook](../../setup/qemu_integrated_gateway.md), note to test 6). Every restart recorded so far exceeded
the limit (map, issue 2):

| Run | Gap at the restart |
|---|---|
| `controller_restart-r01` | 9.0 s, plus later 6.0 s gaps while the container was running |
| `controller_restart-r02` | 6.0 s |
| Finite proof r01 / r02 / r03 | 8.0 s / 9.0 s / 8.0 s |

No collector can sample a container that is down. The window proposed on 2026-09-19, however, ran from the
start of the restart command to the first `/ready`. In r02 that window would have included 14 s during which the
old container was still producing rows. This proposal therefore exempts only the interval that the lifecycle
evidence proves.

**Proposed wording.**
> **Proved-down interval.**
>
> *Where it applies.* In a `controller_restart` run, it applies to the single container that the restart record
> names.
>
> *The interval.*
> - D is that container's `die` event and S is its next `start` event.
> - Both events must be in the run's Docker events capture, and `events_coverage.py` must judge that capture
>   `complete`, with the restart operation's actions expected.
> - S must match the container's `State.StartedAt`, read after the restart, to the 1 s resolution of the rows.
> - The interval runs from D to S, or to D + `RESTART_RECOVERY_MAX_S` (120 s) if that comes first. Any row missing
>   after that point is judged by the ordinary rule.
>
> *Checks for that container.*
> - The gap from its last row before D up to D must be at most `MAX_SAMPLE_GAP_S`, and so must the gap from S to
>   its first row after S.
> - That first row after S must come at least one sampling interval after S.
> - A row stamped between D and S is rejected.
>
> *Everything else.* Every other container keeps the 5 s rule, and so does this container outside the interval.
>
> *When there is no interval.* If the capture is not complete, if there is no `die` and `start` pair, or if
> `StartedAt` does not match, no interval exists.
>
> *What stays unchanged.* No row is ever added, zero-filled or interpolated. D, S, the interval's length and both
> edge gaps are reported as outcomes. The rule changes no delivery figure, no recovery figure and no C12 figure.

**Families affected.** T6, and the campaign's `controller_restart` condition. T1 has no restart. T5, T7 and T8
ingest no resource file (map).

**If adopted.**
- T6's harness run can be valid, provided collection kept to the 5 s rule outside the proved interval.
- It needs the events recorder wired into T6's harness command. This pull request does that, but it has not been
  verified on the guest. It also needs the capture to be `complete`.
- It needs a read of `StartedAt` after the restart. No step of T6 reads it after the restart; only the proof's
  restart script does so today.
- A valid T6 is still not guaranteed:
  - nobody has measured whether the edge gaps stay within 5 s under TCG;
  - the guest clock steps back by 1–3 s about every 30 s, and the rule does not absorb those steps.
- Past runs stay invalid, because none of them captured the lifecycle.
- The 5 s and 120 s values remain with D007/G4.

**If declined.** Every restart recorded so far (6–9 s) would make T6's harness run invalid. T6 then cannot pass
under the unchanged rules, and G3 cannot be met on it.

**Recommendation:** adopt 1a prospectively, before T6 runs. Implement it with the regression cases of the
2026-09-19 proposal (§2), rewritten for the interval from D to S.

### 1b. The sample count of short runs

**Current rule.** The validator needs at least 30 distinct sample instants per container, counted over the whole
file ([`resources.py`](../../../src/egw_experiments/resources.py), `MIN_DISTINCT_SAMPLE_INSTANTS`), plus 90 %
coverage and no gap over 5 s. The runbook names `smoke_sequence-r01` for T1's harness run: a 30 s window with no
warm-up. The collector's priming round writes no row, so even a perfect 1 Hz collector reaches exactly 30
instants (proposal, §1). `smoke_sequence-r02` reached 25. After such a failure, the runbook's own fallback is to
run a nominal entry with its duration left unchanged (test 1, harness paragraph).

**Proposed wording.**
> T1's harness run uses a `nominal` entry of the pilot plan never used on the guest, under a new run identity, with
> its declared duration and warm-up unchanged, instead of a `smoke_sequence` entry. It is judged by T1's harness
> Expected list (the artefact chain) under the unchanged ingest rule: 30 distinct instants, 90 % coverage, 5 s
> gaps. Its delivery figures are reported as measured. It is not a passed 30 s smoke, and it does not count
> towards the ten `smoke_sequence` repetitions of C14.

**Families affected.** T1, harness part only.

**If adopted.**
- The runbook's fallback is chosen in advance, instead of after a smoke run that has already failed.
- No rule moves. On 2026-09-19 `nominal-r01` met the ingest rule, with 720 instants over a 722 s window.
- It costs about 12 minutes more of guest time.
- `nominal-r01` itself cannot be reused: its raw directory exists, and the harness and `tools/session/nominal.sh`
  refuse an existing one. The same holds for the runbook's literal IDs `smoke_sequence-r01` (T1) and
  `controller_restart-r01` (T6), both already run in the pilot tree. Choosing unused entries is a procedure point
  for the battery, not a rule change.
- Late confirmations are likely: `nominal-r01` had 3,794 of 6,720 in time. As today, they are reported and are not
  a criterion of T1's harness part.

**If declined.** The 30 s smoke runs with no margin. One missed second makes it invalid. The failed run is kept,
and the fallback follows anyway.

**Recommendation:** adopt 1b. Counting only inside the window, a minimum scaled to the window, or a pre-roll option
would each be a versioned protocol change for D007/G4. None of them is proposed here.

## 2. N1 identities and the twin's surplus

**Current rule.**
- `lost` means a valid message without a unique confirmation within 60 s after the run
  ([CONTRACTS](../../../src/CONTRACTS.md) §9).
- An N1 identity is one that was in progress when the controller was killed, or when a connection ended after the
  identity's `PATCH`. It can reach the twin with only a `duplicate` line. Such an identity is `lost` until a
  separate decision is taken (CONTRACTS §5, "Redelivery (v1.2)"; ADR 0011, N1 and "What must change").
- `delta` compares each twin's Δ`accepted_count` with the `accepted` lines of the device. The twin's surplus
  therefore shows as a `MISMATCH` (exit 4).
- T6 requires zero lost (C12, `delivery_across_restart_zero_lost` in
  [`analyze.py`](../../../src/egw_experiments/analyze.py)) and every `delta` line `OK`.
- The proof's S4 naming belongs to the proof alone. S4's text names the post-drain `accepted_count`; the proof's
  evaluator computes the surplus from the `before`/`after` difference (`proof_evaluator.py`, `device_surplus`).
  The twins' `accepted_count` is cumulative across runs (runbook, §7 preamble), so only a difference describes a
  run.

**What the evidence shows.** The surplus shows that an update was applied, because the twin advanced. It does not
show an observed confirmation: there is no `accepted` line, no latency, and no instant to check against the
deadline.

**Proposed wording.**
> **N1 case (reported, not delivered).**
>
> *When it applies.* An identity is reported in the column `n1_applied_unconfirmed` only if all three conditions
> hold:
>
> 1. Its only outcome lines are `duplicate`.
> 2. The run records a source for it. The source is either a controller death (in the restart record, with its
>    captured `die` event) or a connection end that the controller logged under A3 before the identity's
>    redelivered `duplicate` line. Each source explains at most one identity.
> 3. On its device, the twin's Δ`accepted_count` between the run's `before` snapshot and its `after` snapshot
>    taken after the drain exceeds the device's `accepted` lines in the events `delta` compares with that snapshot
>    (for T6, the post-drain copy) by exactly the number of identities reported this way. The twin's `last_seq` is
>    also not below the identity's `seq`. The absolute `accepted_count` is never used: it is cumulative over every
>    earlier run on the twin.
>
> *What it does not change.* The identity stays in `lost` and in every zero-lost criterion. The `delta` line stays
> `MISMATCH`, annotated with the named identities. The identity is never counted as `accepted`, as delivered, or
> as on time.
>
> *Other duplicate-only identities.* An identity with only `duplicate` lines that fails any of conditions 1 to 3
> is reported as unexplained, never as N1.
>
> *No stronger claim.* The rule asserts no exactly-once delivery.

**Families affected.** T6 first. Also any other family whose run records a controller death, or an A3
connection end after a `PATCH`.

**What it means for T6.**
- T6's restart is graceful (`docker compose restart controller`, `stop_grace_period` 130 s). The controller
  records and acknowledges the message in progress before it disconnects (CONTRACTS §5, Shutdown). An N1 case
  therefore needs either a stop forced after the grace period or an A3 connection end.
- Whether a graceful restart ever produces one is unknown (map, issue 3).
- If there is no N1 case, nothing changes.
- If there is one, T6 records `lost ≥ 1` and a `MISMATCH`. It then fails C12's zero-lost criterion and "every
  `delta` line `OK`", exactly as it would without this proposal. The new column says why, and shows that nothing
  was applied twice.

**If declined.** T6 gets the same verdicts. An N1 case reads as an unexplained loss plus a twin mismatch, unless
someone explains it by hand.

**Not proposed:** counting an N1 identity as delivered, which is the option ADR 0011 reserves. That would change
what the project measures, and the identity would still not be on time. It would need a prospective protocol
decision of its own.

**Recommendation:** adopt the reporting column. No criterion changes.

## 3. Which families have a deadline criterion

**Current rule.**
- **Throughput choice T1** (ADR 0011, decision B). The candidate is frozen with only the recovery change. Every
  timed family that misses its deadline is recorded as failed. The throughput question goes to G4 and resolves no
  G3 criterion.
- **Deadline.** The controller marker plus 60 s (`CONFIRMATION_WINDOW_S`). `lost` includes late confirmations.
- **The plan's G3 text** ([plan](../INTEGRATED_DEVELOPMENT_PLAN_2026.md), G3):
  - it asks for "invalid input rejected and valid input accepted" (the clause of T3);
  - it asks for "no loss" in dropout and reconnection;
  - it asks for "recovery inside the bounded window" at the restart;
  - it asks for "a clean post-reboot smoke run";
  - it asks each family to meet "its own expected list";
  - it says "no threshold moved — a result worse than expected at the nominal rate is recorded as a sizing
    finding for the pilot, never absorbed by changing the protocol".
- **Runbook, test 1.** "if `lost > 0` appears, this is the first sizing finding of the pilot (Section 8), not a
  reason to change the protocol".
- **How the two readings meet.** Those two sentences can be read as "late at the nominal rate is a sizing finding,
  not a G3 failure". Choice T1 of ADR 0011 reads them otherwise: the sizing finding is recorded, and the family
  still fails its deadline. The proposal below follows choice T1.

The Expected lists of the runbook, §7, say the following:

| Family | Deadline item in its Expected list | Timed? |
|---|---|---|
| T1 | Each run: `lost = 0`, `late_confirmations = 0`. The harness run: artefacts only | Yes |
| T2 | `lost = 0`, `late_confirmations = 0` | Yes |
| T3 | **None.** Rejection counts, `delta`, the controller log and `last_seq` only | Open |
| T4 | Replay (`itest-dup-01`): pre- and post-replay figures `UNCHANGED`. Sequence reset (`itest-dup-02`): `lost = 0` | `dup-02` only |
| T5 | `lost = 0`, `late_confirmations = 0` | Yes |
| T6 | Samples resuming within `RESTART_RECOVERY_MAX_S` (120 s), `double_accepted = 0`, every `delta` line `OK`; the loss "is reported as measured, never suppressed". Zero lost is not in this list (see below) | Conflict |
| T7 | `lost` is reported beside `failed`, `late` and `dropped`; it is not required to be 0 | No |
| T8 | Post-reboot smoke: `lost = 0`, `late_confirmations = 0` | Yes |
| T9 | None. The "about 15 s" in (b) and (c) is the simulator's connect timeout, not a deadline | No |

**T6 has two sources that disagree.** Its Expected list reports the loss as measured. The harness's C12 gate,
`delivery_across_restart_zero_lost` in [`analyze.py`](../../../src/egw_experiments/analyze.py), requires
`lost == 0`, late confirmations included, and ADR 0011 ("Relationship with the throughput problem") reads it the
same way. Listing T6 as timed, as proposed below, settles that conflict in favour of C12. That is a decision, not a
restatement of the Expected list.

**Proposed wording.** A general statement, followed by one of two options for T3:
> **Timed families.**
> - The timed families of G3 are:
>   - T1, each of its three runs;
>   - T2;
>   - T4's sequence reset (`itest-dup-02`);
>   - T5;
>   - T6;
>   - T8's post-reboot smoke.
> - Each must meet `lost = 0` and `late_confirmations = 0` under the controller-clock deadline, which is the marker
>   plus 60 s. T6 must also meet its recovery bound (`RESTART_RECOVERY_MAX_S`).
> - A family that misses a mandatory deadline is recorded as failed, and G3 is not met on it (ADR 0011,
>   throughput choice T1). The miss is also recorded as a sizing finding for the pilot; that record does not
>   turn the failure into a pass.
> - No deadline, rate, duration or load changes. Sending the throughput question to G4 waives no G3 condition.
>
> **Option 3-A (T3 is not timed).** T3's acceptance is its Expected list as written. The plan's "valid input
> accepted" is read as that list states it: no valid message rejected (`valid rejected = 0`) and every `delta` line
> `OK`. A valid message confirmed after the deadline was still accepted; one never accepted (dropped, or `failed`
> against Ditto) shows in `lost`. The `lost` and `late_confirmations` of its valid messages are reported with its
> result, and decide nothing for T3.
>
> **Option 3-B (T3 is timed).** T3 must also meet `lost = 0` and `late_confirmations = 0` for its valid messages.

**Families affected.** All nine. T3 is the open case, and T6 has the conflict set out above.

**If adopted.**
- The figures so far are context only; they come from the old candidate or from invalid runs:
  - `nominal-r01` served 6.457 msg/s against 11.2 msg/s offered;
  - T5 had 326 of 2,016 confirmations late;
  - T2 was in time with a margin of 3.1 s.
- On those figures, T1, T2 (in time by 3.1 s only), T4's reset, T5, T6 and T8's smoke may miss their deadlines. Each miss is then recorded as
  a failure, not absorbed.
- Under 3-A, T3's late confirmations (132 of 1,277 on 2026-09-18) are reported, but they do not fail T3.
- Under 3-B, T3 joins the families at risk.
- T6's zero lost is taken from C12, and its Expected list's "reported as measured" becomes a report beside that
  criterion, not a replacement for it.

**If declined.** T3's status stays ambiguous, so any T3 verdict stays open to challenge. T6 keeps two sources that
disagree: the harness still applies C12, and the runbook still says the loss is only reported. The other rows stay
as the Expected lists already state them.

**Recommendation:** adopt the list with option 3-A. For T1, T2, T4's reset, T5 and T8 it states the Expected lists
as they are written; for T6 it chooses C12 over the Expected list, openly. Option 3-A matches the campaign's rule
for invalid payloads, where valid delivery is informational (`analyze.py`, `invalid_payload`). Option 3-B would add
a criterion that neither of them contains.

## 4. T4: controlled replay versus redelivery after a reconnection

**Current rule.**
- After the replay, the runbook's test 4 requires:
  - "`duplicate` equals the number of replayed messages";
  - `double_accepted = 0`;
  - the pre- and post-replay figures `UNCHANGED`;
  - the twins `same`;
  - a `/metrics` difference of `accepted` 0 and `duplicate` equal to the number replayed, with `queue_depth` 0
    and the same `started_at`.
- Under option 5, a reconnection inside one process can add a `duplicate` line. It adds at most one per lost
  connection, coming from the delivery in progress, and it is not a double acceptance (ADR 0011, N2;
  CONTRACTS §5).
- So one reconnection during the replay can break "duplicate = replayed count", even though nothing was applied
  twice.

**Proposed wording** (prospective).
> **T4's duplicate criterion is judged per identity.**
>
> *What every replayed identity must satisfy.* A replayed identity is any `message_id` in the replay's
> `sent_events.jsonl`. Each one:
> - gains at least one `duplicate` line from the replay;
> - gains no `accepted` line from the replay;
> - has at most one `accepted` line in total (`double_accepted = 0`).
>
> *What else must hold.* Every other item of test 4's Expected list is unchanged:
> - `delivered_unique`, `lost`, `late_confirmations` and `double_accepted` are `UNCHANGED` between the pre- and
>   post-replay accounting;
> - the twins are `same` between the `after` and `replay` snapshots;
> - between those snapshots, the `/metrics` difference is `accepted` 0, with `queue_depth` 0 and the same
>   `started_at`.
>
> *Two counts, reported separately.*
> - `duplicate_replayed`: the replayed identities that gained a `duplicate` line. It must equal the number of
>   replayed identities.
> - `duplicate_redelivery`: every further `duplicate` line added during the replay interval.
>
> *When redelivery duplicates are acceptable.* They do not fail T4 if their number does not exceed the change in
> `mqtt_connection` between the `after` and `replay` snapshots (N2: at most one per lost connection). Otherwise T4
> fails.
>
> *Reporting.* The `duplicate` difference in `/metrics` is reported as the sum of the two counts.

**Families affected.** T4 only.

**If adopted.** A reconnection that the contract expects no longer fails T4. Only the duplicate count is judged
differently. A second application, any change in the pre- and post-replay figures (a new lost identity among them),
a queue left behind, a controller restart or an unexplained extra duplicate still fails it. The rule uses only
snapshots that T4 already takes.

**If declined.** The literal count stands. A reconnection during the replay that adds a duplicate fails T4, and it
is recorded as a failure.

**Recommendation:** adopt it prospectively, before T4 runs.

**T4 execution checklist**, for when the battery is authorised:
1. Run `itest-dup-01` as in the runbook's block: the first run, the pre-replay copies, the replay, then its capture
   and evaluation.
2. **Run `itest-dup-02`, the sequence reset. It has never been run.** The command is
   `run_test itest-dup-02 42 --scenario smoke --duration 60`. It must give `lost = 0` and every `delta` line `OK`.
   This is a timed item (decision 3).
3. Keep both results. A failure of either one is a failure of T4.

## Candidate manifest (draft, not a freeze)

| Part | Identity | Status |
|---|---|---|
| Tooling: harness, helpers, drivers, runbook 6.1 | The head of this pull request | Pending until merged. The helper file is regenerated from it and checked by sha256 |
| Controller image | `egw-controller:0.1.0`, `sha256:9a293fe13b1a020560d43fee328632a9ef8d91dec830899f18d3e2d964aa5f46`, `linux/arm64`, built from `489bc9e` | Kept, unchanged since 2026-09-26. No rebuild |
| Other images | Pinned by digest in `src/deployment/images.lock.env` | Unchanged |
| Deployment | `compose.yaml`: controller `stop_grace_period` 130 s, three Ditto services at 768 MiB. `mosquitto.conf`, C1: W 4,999, Q 1,000, expiry 1 h | Hashes recorded for every run (`config_identity`) |
| Guest OS | The integrated image of 2026-09-18 | Hashed by the session drivers before each boot |
| Contracts | `src/CONTRACTS.md` v1.2 (2026-09-24) | A freeze record is still needed: the backlog's cut rule still names v1.1 |

**Open risks, not assumed solved.**
- **Ditto memory and stability.** `ditto-things` runs at its 768 MiB limit. The limit was raised after a
  memory-cgroup OOM on 2026-09-18, which happened during a power-off at the old 512 MiB limit. The risk is
  mitigated, not declared stable. G3 requires it to be resolved, or bounded and recorded.
- **T8 with a held session.** A reboot while the broker holds the controller's persistent session (60 s autosave)
  has not been assessed (ADR 0011, N3 and open item 7).
- **Queue and backlog.** W and Q have not been checked against the backlogs the families produce (ADR 0011, open
  item 3).
- **Timed delivery.** `nominal-r01` confirmed 3,794 of 6,720 in time, and T5 had 326 of 2,016 late. The candidate
  has never been measured against its deadlines on a valid run.

## What still stands between this and G3

The [readiness map](../g3-readiness-map-2026-09-29.md) keeps the full list. In short:
- these four decisions, and the map's fourth (lock the candidate and authorise the battery to resume) *(2026-09-30:
  the four were taken on that date, see "The decision of 2026-09-30", implemented offline and not yet run on the
  guest; the map's fourth remains)*;
- the families' own procedures on the guest: the shared capture helpers (recorder, bounded controller and broker
  reads, closing marker) were verified compatible in one short window, without load or faults (2026-09-30,
  `compat-capture-r01`), but no family's own procedure ran there, and the T6 and T7 event sets, delivery and log
  volume under load, the harness path end to end and an interactive Ctrl-C remain unverified on the guest;
- T6's remaining blockers, including zero lost at 11.2 msg/s;
- the sub-checks never run: `itest-dup-02` and `itest-ditto-fault-01`;
- the open risks listed above;
- the contracts freeze record;
- the blind spot that `drained` used to have, still not assessed in `gate_health.sh`, `accounted` and `delta`;
- the lack of a versioned battery driver.

Only after all of that can the qualifying battery run, on one unchanged candidate. G3 stays paused.
