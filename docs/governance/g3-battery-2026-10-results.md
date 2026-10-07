# G3 qualifying battery of 2026-10-02 and 2026-10-03, its T8/T9 completion of 2026-10-05 and its T6 session of 2026-10-07 — results addendum

**A record, not a decision.** This page consolidates what the two sessions of
the G3 qualifying battery recorded, row by row, keeping three things apart
that the result notes and the Project Manager's assessment keep apart:
whether the row's evidence chain is **valid**, what its **functional outcome**
was, and whether its **timed delivery** was met where the family is timed. It
changes no criterion, threshold, deadline, load or rule; it re-labels no
attempt; it accepts no family, no gate and no claim. G3 stays `Not decided` in
the [gate decision log](gate_decision_log.md), and the pause on qualifying
runs stays in force ([PROGRESS](../../PROGRESS.md), G3 bullet). The authority,
sessions and packages are the two result notes held locally
(`output_test/decisions/2026-10-02_g3-battery-s1-results.md`,
`2026-10-03_g3-battery-s2-results.md`) and the Project Manager's register
entry of 2026-10-03, 15:50 WEST (`ChatGPT/PROJECT_MANAGEMENT_INSTRUCTION_REGISTER.md`,
held outside the repository); the packages are indexed, with their seals, in
[`docs/evidence/g3-battery-2026-10/`](../evidence/g3-battery-2026-10/README.md).
Narrative: LOG #C050. *(2026-10-07: the page now covers sessions S1 to S4;
the standing row of each family, apart from the historical attempts, is in
"Standing rows as of 2026-10-07" below; the packages and the result notes
are published byte for byte in the capsule; LOG #C054.)*

## Candidate and sessions

| Item | Identity |
|---|---|
| Tools | `80e833f` (tree `dad725d`), the merge of PR #53; `repo_dirty_lines: 0` in every attempted qualifying row |
| Helpers | the runbook's section 6.1 heredoc, `e5eba37e…` (545 lines), regenerated in the host preparation |
| Controller image | `egw-controller:0.1.0` `sha256:9a293fe1…`, arm64, built from `489bc9e`; already on the guest's data disk; no build, no load |
| Guest | the integrated image of 2026-09-18 under QEMU 8.2.7 **TCG**, `-cpu cortex-a76 -smp 4 -m 8192` (ARM64 **emulated** on an x86-64 WSL2 host, the load generator on the same machine); the launcher `run-qemu-integrated.sh` at `489bc9e`, unchanged at `80e833f` |
| Authority | Rui's authorisation of 2026-10-02 under the decision packet of 2026-10-01, revision 2; "arranca a S1" (2026-10-02) and "arranca a S2" (2026-10-03) |
| S1 | 2026-10-02, 15:01:30Z to 16:34:13Z (1 h 33 min); rows 1–7; no halt condition; controlled close exit 0, root file system `f59a60ff…` after it |
| S2 | 2026-10-03, 13:22:49Z to 14:39:43Z (1 h 17 min); opened on S1's post-close root file system; rows 8–11; **halt 5 of the packet's §4 at row 11 (T8)**; controlled close exit 0, root file system `22e9da85…` after it |

Nothing changed on the candidate during or between the sessions. Every
timing below is an observation of an emulated guest and is informational.

## The rows

Validity is the row's own evidence chain (the harness or the row's checks);
"reported only" marks a figure the row records without judging it; the class
is the packet's §5 as the result notes applied it. A timed family must meet
`lost = 0` and `late_confirmations = 0` against the marker plus 60 s.

| # | Row | Run id | Validity | Functional outcome | Timed delivery | Class | Package (`output_test/runs/`) |
|---|---|---|---|---|---|---|---|
| 1 | T1 smokes ×3 | `itest-smoke-01/02/03-q1` | valid | each: 336 sent, 336 delivered, three device types, every `delta` OK, `double_accepted` 0 | **met** ×3: `lost` 0, `late` 0 (first smoke p95 about 50 s against the 60 s deadline) | Pass | `2026-10-02/20261002T150829Z_g3-qualification-t1-smokes_attempt01` |
| 2 | T1 harness | `nominal-r02` | valid, sealed: manifest `valid`, no collector problem, 682 instants per service, capture complete | the artefact chain only (decision 1b): not a passed smoke, not a performance approval | **reported only**: 4,584 of 6,720 in time (`lost` 2,136, 111 of them late) — **not** successful nominal delivery | Pass (artefact chain) | `2026-10-02/20261002T152710Z_g3-qualification-t1-harness_attempt01` |
| 3 | T2 | `itest-3dev-01-q1` | valid | 672 of 672; three twins with `policyId` = `thingId`, no missing property, `egw_id`, `schema_version`; `delta` OK | **met**: `lost` 0, `late` 0 | Pass | `2026-10-02/20261002T154427Z_g3-qualification-t2_attempt01` |
| 4 | T3 | `itest-invalid-01-q1` | valid | 67 invalid, 67 rejected, none accepted; 1,277 valid, all `accepted` in the post-drain copy (`acceptance` 0), none rejected; `delta` OK | not timed (decision 3); reported only: `lost` 0, `late` 0 | Pass | `2026-10-02/20261002T155313Z_g3-qualification-t3_attempt01` |
| 5 | T4 replay | `itest-dup-01-q1` | valid | `replay-check` 0: 672 of 672 with a `duplicate` line, none accepted again, `after` reading quiet, k = 0; twins identical; accounting unchanged | not timed (the replay half) | Pass | `2026-10-02/20261002T160154Z_g3-qualification-t4-replay_attempt01` |
| 6 | T4 reset | `itest-dup-02-q1` | valid | 672 of 672, no duplicate; `delta` OK (first run of this sub-check) | **met**: `lost` 0, `late` 0 | Pass | `2026-10-02/20261002T161432Z_g3-qualification-t4-reset_attempt01` |
| 7 | T5 | `itest-dropout-01-q1` | valid; one `check` warning (C10, a documented layout mismatch, see below) | 2,016 of 2,016, `double_accepted` 0, `delta` OK; 3 deliberate dropouts, 165 buffered (the run's manifest and stderr); the bounded broker log holds 4 connections and **4** disconnection lines | **met**: `lost` 0, `late` 0 | Pass as sealed, **interpretation pending** (below) | `2026-10-02/20261002T162159Z_g3-qualification-t5_attempt01` |
| 8 | T6 | `controller_restart-r03` | **invalid** under rule 1a: two rows of `egw-controller-1` stamped `13:37:17Z` and `13:37:18Z` inside the proved-down interval (die `13:37:14.06Z`, start `13:37:18.76Z`); unsealed inner run; the package's outer seal does not validate it | the restart ran with exit 0, capture complete, `StartedAt` within 1 s of the start, both edge gaps within 5 s; recovery 4.75 s functional, 11.9 s endpoint; engineering evidence, not a qualifying result | **reported only**: 4,718 of 6,720 by the deadline in the initial events copy (`lost` 2,002, 82 late); the post-drain copy holds all 6,720 uniquely accepted, 2,002 of them beyond the deadline, none absent, none duplicate-only | Invalid instrumentation | `2026-10-03/20261003T132936Z_g3-qualification-t6_attempt01` |
| 9 | T7 MongoDB | `itest-mongo-fault-01-q1` | valid; capture complete (`die`, `stop`, `start` of `egw-mongodb-1`) | interruption and recovery shown; 44 `failed` after 3 attempts with HTTP 500, acceptance resumed; `delta` OK; N1 report 0/0 | not timed; reported only: `lost` 1,209 (1,165 late) | Pass | `2026-10-03/20261003T135147Z_g3-qualification-t7-mongo_attempt01` |
| 10 | T7 Ditto | `itest-ditto-fault-01-q1` | valid; capture complete | interruption and recovery shown (first run of this half); 5 `failed` after 3 attempts with a read timeout, acceptance resumed; `delta` OK; N1 report 0/0; no OOM at 768 MiB | not timed; reported only: `lost` 1,895 (1,890 late) | Pass | `2026-10-03/20261003T140639Z_g3-qualification-t7-ditto_attempt01` |
| 11 | T8 | `itest-reboot-q1` | **incomplete**: the post-reboot artefacts were never written | the guest rebooted inside the same QEMU process (boot id `d22195a1…` → `76471e31…`; previous boot ended `14:25:44Z`, new boot `14:26:15Z`); container start times reach `14:26:46Z`, health read later; the procedure waited 600 s for a QEMU exit that the launcher never produces and halted. `REBOOT SHOWN`, the twin comparison, the controller's state and the fresh smoke were **not evaluated** | smoke not run | Inconclusive / not demonstrated — **HALT** (packet §4, halt 5) | `2026-10-03/20261003T142310Z_g3-qualification-t8_attempt01` (the session package holds the read-only post-reboot step) |
| 12 | T9 | — | — | not run after the halt | — | Not run | — |

The session, preflight, gate and operator-records packages of each day, and
the host preparation, are listed with the rows in the
[evidence index](../evidence/g3-battery-2026-10/README.md).

## The T8/T9 completion of 2026-10-05

Authority: Rui's authorisation of one session S3 (tests 8 and 9 only) under
the request of 2026-10-04 and its decision summary, and of a second opening
under a prospective exception for `collector-duration` authorised the same day
(the records are held locally under `output_test/decisions/`, dated
2026-10-04 and 2026-10-05); the Project Manager's register entries of
2026-10-05, 12:09 and 13:42 WEST. The candidate is the battery's, unchanged:
controller image `9a293fe1…` from `489bc9e`, the pinned images, the deployment
tree, the guest image under QEMU 8.2.7 TCG. The procedure and tools are the
merge of PR #54, `8e49261` (runbook `4acf8de6…`, helpers `e5eba37e…`): test 8
in its corrected form (lines a to f), every identifier with the suffix `-q2`.
Narrative: LOG #C051.

| Opening | Time (UTC) | What happened |
|---|---|---|
| First | 10:56–11:03 | **Halted at open, before any row.** The frozen preflight ended exit 3 (instrumentation invalid, outcome inconclusive) on its `collector-duration` step alone: the check measured 43 s between the collector's UTC `start:` and `stop:` stamps against the 45 s the collector runs on `/proc/uptime`, and the collector's calibration lines record 38 s of UTC against 40.69 s of uptime in the same interval — a clock-basis mismatch, not a measured early stop. No row ran, no `-q2` identifier was used; controlled close; root file system `b48b010d…` after it. |
| Second | 11:44–12:13 | The preflight passed normally (44 s of 45 s, within its tolerance): the authorised exception was **not** used. T8 and T9 ran; controlled close (recorded stop and close driver exit 0, no QEMU left); root file system `6fce1688…` after it. |

| # | Row | Run id | Validity | Functional outcome | Timed delivery | Class | Package (`output_test/runs/`) |
|---|---|---|---|---|---|---|---|
| 13 | T8 | `itest-reboot-q2`; smoke `itest-post-reboot-01-q2` | valid | reboot inside the same QEMU process on the same disks (no `-no-reboot` on its command line; boot id `fc85c700…` → `0a780c6e…`); the same six container objects listed running again with nothing started by hand; the 35 event-directory names and `/var/lib/docker` on `/dev/vdb` persisted; the three existing seed-42 twins identical; the controller's `started_at` changed | **met**: 336 sent, 336 accepted, `lost` 0, `late` 0, every `delta` OK; the latest acknowledgement 1.338 s before the controller-marker deadline | Pass | `2026-10-05/20261005T115131Z_g3-qualification-t8_attempt02` |
| 14 | T9 | `itest-tls-wrongca-q2`, `itest-auth-wrongpw-q2`, `itest-notls-q2`, `itest-acl-20261005T120642Z` | valid | (a) wrong CA rejected; (b) wrong password refused, the named client "not authorised" in the broker log bounded to (b); (c) plaintext on the TLS listener rejected; (d) ACL probe PASS, no delivery to the unauthorised subscriber, controller counters and process unchanged; (e) anonymous client refused; the exposure observations recorded | not timed | Pass | `2026-10-05/20261005T120537Z_g3-qualification-t9_attempt01` |

Boundaries the Project Manager states for these rows:

- **T8.** The persistence shown is of the event-directory names, not a
  verification of every file's bytes. Zero restart counters and no reported
  OOM do not mean that the prescribed reboot did not occur. The smoke's
  latency percentiles (p95 57.6 s, maximum 58.8 s) are descriptive; the
  timeliness criterion is `lost` and `late` against the marker plus 60 s.
- **T9** demonstrates the tested controls, not a security audit. The ssh
  observation is the refusal of one root login with one key, not proof of a
  root-login policy; the exposure evidence concerns the WSL/QEMU loopback
  forwarding and the guest's publication as observed, not Windows or LAN
  reachability, nor a firewall.
- **The first opening's preflight stays invalid.** The second opening's pass
  validates it in no way and does not settle the measurement debt of
  `collector-duration` (UTC stamps judged against a duration run on uptime),
  which is recorded for correction before any resource-dependent run relies
  on that check.
- Seven families now have favourable technical evidence on this candidate
  (T1–T4 and T7–T9). That is not a G3 decision.

## Test 6 under the amended criterion: session S4 of 2026-10-07

Authority: Rui's authorisation of one session S4 (test 6 only) on
2026-10-07, under the request of 2026-10-05 and its preparation supplement
of 2026-10-07 (published byte for byte in the capsule's
[`records/`](../evidence/g3-battery-2026-10/records/));
the Project Manager's register entries of 2026-10-05, 21:56 WEST, and
2026-10-07, 14:19 WEST. The candidate is the battery's, unchanged:
controller image `9a293fe1…` from `489bc9e`, the pinned images, the guest
image under QEMU 8.2.7 TCG. The procedure and tools are the merge of PR #57,
`1fd9792` (runbook `31716593…`, helpers `e5eba37e…`): test 6 on a fresh plan
entry, `controller_restart-r04` (seed 1715385812), judged by the criterion
amended on 2026-10-05, with the transition rule `1a-option-a-2026-10-05`.
The one change on the guest is instrumentation: at the open the frozen
preflight installed the collector of `1fd9792` (`11444c0a…` → `9e678b02…`).
Narrative: LOG #C054.

| Part | Time (UTC) | What happened |
|---|---|---|
| Open | 12:03:48–12:10:52 | Every identity equal (clone `1fd9792`, drivers `2c209b09…`, root file system `6fce1688…` as S3's second close left it). The preflight passed: the new collector installed, the deployed tree equal to the clone but `README.md`, `collector-duration` 45.54 s on the guest's monotonic clock for the declared 45 s. The gate passed: six services healthy, the running images equal to the record. |
| Row t6 | 12:11:14–12:32:30 | 1,239 s on the host's uptime clock (the ceiling's basis; the UTC stamps span 1,276 s) against the 47 min ceiling; no `STOP:` line; the gate after it passed; classified at 12:33:23. The recorder's emergency cleanup of the supplement was not needed. |
| Close | 12:34:01–12:35:30 | `stop -t 130` exit 0, no OOM, QEMU ended exit 0 with no process left, close driver exit 0; root file system `1605905b…` after it. |

| # | Row | Run id | Validity | Functional outcome | Timed delivery | Class | Package (`output_test/runs/`) |
|---|---|---|---|---|---|---|---|
| 15 | T6 | `controller_restart-r04` | valid: manifest `valid` with no reason against it; the inner run sealed (46 files); drain `quiet` | one restart at +300 s, returncode 0; the capture one `die` and one `start` of `egw-controller-1`, the gate after `EXPECTED-RESTART` on the same container, restart count 0, no OOM kill; endpoint recovery 12.134 s (within 120 s); every `delta` OK (600, 120, 6,000 accepted), N1 report 0/0; `acceptance --exactly-once`: 6,720 accepted exactly once, 0 more than once, 0 never; `double_accepted` 0; configuration identity equal to the packet | not a pass condition of test 6 since 2026-10-05; **reported only**, a sizing finding: 4,567 of 6,720 by the deadline (`lost` 2,153, the 67 late among them; below) | Pass (the criterion amended on 2026-10-05) | `2026-10-07/20261007T121121Z_g3-qualification-t6_attempt02` |

**The delay numbers of row 15, read correctly.** Both are counted against
the controller marker plus 60 s on the timed copy of the events
(`events.jsonl`, fetched after the confirmation window). `lost` is the valid
messages sent less those confirmed by the deadline in that copy:
6,720 − 4,567 = 2,153. `late_confirmations` counts that copy's accepted
lines acknowledged after the deadline: 67 of its 4,634. A late line is
never counted as confirmed, so the 67 are among the 2,153 and are never
added to them; the other 2,086 were accepted after the timed copy was
taken, during the drain (`src/egw_experiments/analyze.py`: a late
acceptance is counted and skipped before it can be confirmed, and
`lost = sent_valid - delivered_unique`). None of the 2,153 is a permanent
loss: all 6,720 valid messages were accepted exactly once by the end of the
drain (`events.post-drain.jsonl`, of which the timed copy is a byte
prefix). Functional recovery was demonstrated in this run (20.04 s,
reported beside the endpoint figure); timely delivery at the nominal load
(11.2 msg/s, deadline = controller marker + 60 s) was not.

Boundaries the Project Manager states for this row:

- "Exactly once" is one accepted result per valid sent identity of this
  run, not a general MQTT exactly-once guarantee. The endpoint recovery runs
  from the end of the restart command to the first `/metrics` answer; it is
  not the time from the fault to functional recovery.
- The N1 options exercised with N1 = 0 do not prove every N1 branch; no OOM
  in this session is not prolonged stability. The recorder's emergency
  cleanup was not needed and stays tested offline only.
- Row 8 stays invalid and is not re-judged. The analyser's global line
  `restart_recovery_observed_every_run: FAILED - 1/4` (r01–r03 not
  evidenced) is kept unchanged: row 15 neither accepts the campaign nor
  requalifies an earlier run.
- With row 15 all nine families have favourable technical evidence in their
  own adopted criteria. That is not a G3 decision: full gate admission
  remains Rui's dated decision, after the review of the
  [closing proposal](proposals/2026-10-07-g3-closing-proposal.md).

The session, preflight, gate and operator-records packages of S4, its host
preparation of 2026-10-05 and the supplement of 2026-10-07 are published
with the other 31 packages in the
[evidence index](../evidence/g3-battery-2026-10/README.md).

## Standing rows as of 2026-10-07

The current row of each family and sub-check, on its own adopted criterion,
apart from the historical attempts. Nothing is re-labelled: every row keeps
the class it was recorded with.

| Family | Sub-check | Standing row | Run | Class as recorded |
|---|---|---|---|---|
| T1 | three smokes | 1 (S1) | `itest-smoke-01/02/03-q1` | Pass |
| T1 | harness | 2 (S1) | `nominal-r02` | Pass (artefact chain; delivery reported only) |
| T2 | three wearables | 3 (S1) | `itest-3dev-01-q1` | Pass |
| T3 | invalid payloads | 4 (S1) | `itest-invalid-01-q1` | Pass |
| T4 | replay | 5 (S1) | `itest-dup-01-q1` | Pass |
| T4 | sequence reset | 6 (S1) | `itest-dup-02-q1` | Pass |
| T5 | dropout and reconnection | 7 (S1) | `itest-dropout-01-q1` | Pass, as sealed (reading admitted 2026-10-05) |
| T6 | controller restart | 15 (S4) | `controller_restart-r04` | Pass (the criterion amended on 2026-10-05) |
| T7 | MongoDB fault | 9 (S2) | `itest-mongo-fault-01-q1` | Pass |
| T7 | Ditto fault | 10 (S2) | `itest-ditto-fault-01-q1` | Pass |
| T8 | guest reboot | 13 (S3, second opening) | `itest-reboot-q2`, smoke `itest-post-reboot-01-q2` | Pass |
| T9 | TLS and authorisation | 14 (S3, second opening) | five sub-checks and the exposure observations | Pass |

Historical attempts, kept as recorded and not standing: row 8 (T6
`controller_restart-r03`, invalid instrumentation), row 11 (T8
`itest-reboot-q1`, inconclusive, halted), row 12 (T9 in S2, not run), and
S3's first opening (halted at its preflight, no row run). The executions of
2026-09-18 and `controller_restart-r01`/`-r02` keep their records outside
this battery.

## Boundaries the Project Manager states

- **T1–T4** are technically favourable in their own criteria, every required
  sub-check reported. `nominal-r02` validates the artefact chain only: 4,584
  of 6,720 timely is **not** successful nominal delivery. T3 is not timed. T4
  covers replay and sequence reset.
- **T5**: the delivery and fault evidence is favourable (2,016 of 2,016
  timely, three deliberate dropouts, 165 buffered). Its classification waits
  on the interpretation below; the sealed Pass is not overwritten and is not
  presented as an unqualified pass before that ruling. The `check` warning
  about C10 is a documented layout mismatch: the reconciliation directory
  lacks the campaign-style simulator manifest, while the original manifest
  and stderr hold the 3/165 totals. The warning is preserved; no campaign
  C10 acceptance is claimed and the frozen helper is not changed to hide it.
- **T6** is invalid under the adopted resource rule; the outer 95-entry seal
  does not seal or validate the inner harness run. Rows are not deleted, the
  validator is not relaxed and the attempt is not relabelled. "Acquired
  1.7 s before Docker's start" is stronger than the whole-second, pre-read
  sample stamps establish: an early cgroup read is an explanation to
  qualify, not a proven timing fact. `lost` 2,002 is the deadline metric of
  an invalid run, not 2,002 proven permanent losses, and 82 is not the total
  eventual lateness (the post-drain copy has 2,002 beyond the deadline).
  Fixing resource validity alone cannot cure that timing shortfall. These are
  observations on an invalid qualifying run, not a new qualifying failure
  verdict and not a capacity claim.
- **T7**: both faults demonstrated with the expected `failed` outcomes,
  resumed acceptance and `delta` OK. Not timed; no general lossless or
  prolonged-stability claim.
- **T8** is not demonstrated: the reboot was observed, the required checks
  were not finished. A **procedure defect** (the runbook's line 1487 assumed
  `-no-reboot`, absent from the launcher's QEMU command line), **not** proof
  that the Yocto reboot or the persistence failed. Health was checked later,
  not proved at the instant the containers started; the extra read shows
  directory counts, not byte-for-byte persistence of every event directory.
  Neither those observations nor the successful close complete T8
  retrospectively.
- **T9** did not run after the halt, which the packet's halt rules required.
- **Throughput.** Every long row at 11.2 msg/s (the T1 harness run and T6
  for 600 s, each T7 fault for 300 s) left a large late backlog under TCG;
  the 30 s, 60 s, 120 s and 180 s rows, at the same rate, were in time. A sizing
  finding, recorded; it turns no row into a pass and no pass into a capacity
  claim.

## Outstanding decisions (Rui's; none taken here)

1. **T5, the interpretation.** The bounded broker log records four
   connections and four disconnection lines: three disconnect/reconnect
   cycles, then the simulator's terminal `DISCONNECT`, which the bounded read
   taken after the run always includes. The packet's §5 assigns a count other
   than "N+1 connections and N disconnections" to *inconclusive*. The
   recommendation is that Rui explicitly admit the reading "N fault
   disconnects followed by reconnect, plus terminal teardown reported
   separately"; until then the row is a sealed Pass with that question open,
   never an unqualified pass. No repeat is technically indicated by this
   count alone. *(2026-10-05: the Project Manager recommends admitting that
   reading in a dated decision that keeps the 2,016 timely messages and
   admits no C10 claim; the decision is Rui's.)* **Decided 2026-10-05:** the
   reading is admitted; row 7 is a Pass as sealed, the 2,016 timely messages
   kept, no C10 claim admitted
   ([decision record](g3-t5-t6-decisions-2026-10-05.md); LOG #C052).
2. **T6, its admissibility and its timed criterion** — two separate
   questions. (a) Whether collector rows that fall inside the proved-down
   interval invalidate the run as rule 1a is written, or whether a
   prospective validity rule or a collection correction (raw rows retained)
   should apply to future runs: a one-page proposal is prepared separately
   for this decision and adopts nothing. (b) The timed shortfall at
   11.2 msg/s, which no resource-validity change addresses; any runtime
   change makes a new candidate and needs an explicit requalification plan.
   T6 is **not** automatically appended to the next session. *(2026-10-05:
   a one-page choice for T6 — satisfy the current criterion with valid new
   evidence, or seek a prospective, explicit, scoped amendment before any
   implementation or run — is prepared for Rui separately; nothing is
   decided here.)* **Decided 2026-10-05 (option 2):** for runs made after
   that date, test 6 passes on recovery within 120 s, every valid message
   accepted exactly once in the post-drain copy and every `delta` OK; `lost`
   and `late_confirmations` are reported as a sizing finding. Row 8 stays
   invalid; a valid new run still needs a collection-validity rule, the
   `collector-duration` correction and a new plan entry
   ([decision record](g3-t5-t6-decisions-2026-10-05.md); LOG #C052).
   *(Later on 2026-10-05: option A adopted with the Project Manager's
   conditions; the three prerequisites and the exactly-once check implemented
   offline; LOG #C053.)* *(2026-10-07: run in session S4 as
   `controller_restart-r04`, a Pass under the amended criterion — row 15;
   row 8 stays invalid; LOG #C054.)*
3. **T8 and T9, completion — fulfilled on 2026-10-05; nothing outstanding.**
   Both rows pass (section above), and the Project Manager sees no reason to
   repeat them on this configuration. The conditions set after S2, all met by
   that session: T8's procedure corrected offline (LOG #C050) to the
   in-process reboot the launcher actually produces; a separately authorised
   bounded session with fresh run identities (`-q2`) and the procedural
   revision recorded (`8e49261`); its preparation showing the SUT image,
   containers and configuration unchanged; the prior results preserved.
4. **G3 itself.** *(2026-10-07)* With row 15 every family has a favourable
   row in its own adopted criteria; the
   [closing proposal](proposals/2026-10-07-g3-closing-proposal.md) sets out
   G3's criteria clause by clause for Rui's dated decision. Nothing is
   decided here.

G3 remains `Not decided`; G4 and the campaign are not released. No promise
that another run closes G3, no automatic move of the 2026-10-20 target, and no
weakening of a criterion for time.
