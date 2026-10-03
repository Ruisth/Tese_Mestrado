# G3 readiness map (2026-09-29)

**A map, not a decision.** For each of the nine integration and recovery
families, this page states what G3 requires, what exists today on the option-5
candidate, and what remains before a qualifying run. It changes no criterion,
threshold, load or scope, runs nothing, and makes none of the decisions it
names. G3 stays `Not decided` in the
[gate decision log](gate_decision_log.md) and the pause on qualifying runs
stays in force ([PROGRESS](../../PROGRESS.md), G3 bullet). The proof's own
exceptions — E-12's admission of the restart sampling gap and the N1 naming of
[ADR 0011](../adr/0011-controller-restart-recovery.md) — apply to the finite
proof only and are assumed nowhere below.

*(Marker added 2026-10-03: the qualifying battery ran on the frozen candidate
`80e833f` in two sessions, S1 on 2026-10-02 (rows T1–T5) and S2 on
2026-10-03 (T6, T7 and T8; T9 not run after the halt at T8). Each family row
below carries a dated "after the battery" note with what its records show —
validity, functional outcome and timed delivery kept apart — and the decision
it still needs; the consolidated table is the
[results addendum](g3-battery-2026-10-results.md) and the packages are
indexed in [`docs/evidence/g3-battery-2026-10/`](../evidence/g3-battery-2026-10/README.md).
The legend's statuses are kept as they were: a dated note is not a new
status, and no family, gate or claim is accepted by this page; LOG #C050.)*

**What G3 requires.** The criterion is the plan's
([integrated plan](INTEGRATED_DEVELOPMENT_PLAN_2026.md), *G3 — P0 feature
freeze*): the nine families of the runbook
([`qemu_integrated_gateway.md`](../setup/qemu_integrated_gateway.md) §7) in
order on **one unchanged image and container set**, each meeting its own
Expected list; the public contracts frozen; no open P0 defect, the
`ditto-things` memory incident resolved or explicitly bounded; every failed run
kept; no threshold moved. The battery of 2026-09-18 ran on an older candidate
and was never admitted; it does not count, and its results below are context
only.

**Legend.** *Ready*: the procedure exists and needs only a qualifying run on
the frozen candidate — procedural readiness, never a passed run. *Pending*:
offline work or an unrun sub-check comes first. *Blocked*: under the unchanged
rules it cannot give a valid pass without a separate decision.

## The nine families

| Family | Status | Current evidence (context only) | Remaining action or blocker | Evidence expected |
|---|---|---|---|---|
| **T1** repeated smoke, harness artefacts | Pending | 2026-09-18 ad-hoc runs on the old candidate; harness runs `smoke_sequence-r01/-r02` invalid; `nominal-r01` (2026-09-19) instrumentation valid, delivery failed its deadline | Capture wired on 2026-09-29 (LOG #C047): the runbook's `harness_cmd` starts the events recorder before the workload and passes the three run-bounded fetches (runbook 6.1 `events_start`, `harness_cmd`); guest-unverified. *(Decisions 1b and 3 adopted 2026-09-30, implemented offline in this change, not yet run on the guest:)* the harness run uses an unused `nominal` entry (`nominal-r02` on the evidence held) under its own run identity, with its duration and warm-up unchanged, instead of `smoke_sequence-r01`, and is judged by its artefact chain under the unchanged ingest rule; it is not a passed smoke, not a performance approval and not counted towards C14. Each of the three runs is timed: `lost = 0` and `late_confirmations = 0`, a miss being a failure and a sizing finding *(until 2026-09-30: "The short-run rule for resource instants is still unadopted (decision page, 1b)")* *(After the battery, 2026-10-03: ran in S1 on 2026-10-02. The three smokes `itest-smoke-01/02/03-q1` are valid and in time — 336 of 336 each, `lost` 0, `late` 0, three device types, every `delta` OK (the first smoke's p95 about 50 s against the 60 s deadline). The harness run `nominal-r02` is valid and sealed: manifest `valid`, no collector problem, 682 instants per service, capture complete; its delivery is reported only, 4,584 of 6,720 in time (`lost` 2,136, 111 late) — the artefact chain, **not** successful nominal delivery and not a performance approval. Class: Pass, in the family's own criteria. Decision needed: none on these records; nothing accepted.)* | Three `TEST STATUS` records with `check`/`delta`; one sealed harness run directory |
| **T2** three wearables | Ready | 672 of 672 in time, the last acknowledgement 3.1 s before the deadline | Run on the frozen candidate; the small margin is a risk, not a blocker *(After the battery, 2026-10-03: ran in S1 as `itest-3dev-01-q1`, valid; 672 of 672 in time, `lost` 0, `late` 0; three twins with `policyId` = `thingId`, no missing property, `egw_id` and `schema_version`; every `delta` OK. Class: Pass. Decision needed: none; nothing accepted.)* | `reconcile.json` with `lost=0`, `late=0`; every `delta` `OK`; twin readback |
| **T3** invalid payloads | Pending (minor) | 67 rejected, none accepted, no valid message rejected; 132 of 1,277 valid messages late | The rejections are now read from the controller log bounded to T3's own run (runbook test 3, `sut_log controller`; a failed read is a STOP); guest-unverified. *(Decision 3 adopted 2026-09-30, implemented offline in this change, not yet run on the guest:)* T3 is not timed, but every valid identity of its run must have an `accepted` line in the events copy fetched after its final drain, kept write-once as `$P/$R.events.post-drain.jsonl` and checked by `itest_reconcile acceptance` (on a run id already used on the guest, test 3 publishes nothing: a STOP); a valid identity never accepted there fails T3, and a drain that gives up leaves T3 not evaluated (a STOP). `valid rejected = 0` and every `delta` `OK` still hold; `lost` and `late_confirmations` are reported only *(until 2026-09-30: "whether T3 is a timed family under throughput choice T1 is an open question (decision 3 below)")* *(After the battery, 2026-10-03: ran in S1 as `itest-invalid-01-q1`, valid; 67 invalid, 67 rejected, none accepted; 1,277 valid, all `accepted` in the post-drain copy (`acceptance` 0), none rejected; `delta` OK; not timed. Class: Pass. Decision needed: none; nothing accepted.)* | `check` fields; run-scoped controller-log excerpt; the post-drain copy and its `acceptance` verdict |
| **T4** duplicates **and sequence reset** | Pending | 672 duplicates, none accepted twice. **`itest-dup-02` (sequence reset) has never run** | Run both parts. Under option 5 a reconnection adds duplicates, which can break "duplicate = replayed count". *(Decisions 3 and 4 adopted 2026-09-30, implemented offline in this change, not yet run on the guest:)* the replay is judged per identity by `itest_reconcile replay-check` — the contract's same-process checks first, then every replayed identity with a `duplicate` line and no new `accepted` line, `duplicate_replayed` equal to the replayed count, and extras (`duplicate_redelivery`) tolerated up to Δ`mqtt_connection` as "consistent with the reconnection budget", a tolerance and not a proven cause, failing beyond it; *(2026-10-01, PR #53's bounded corrections:)* the `after` reading must be quiet, and with k reconnections in the replay interval a replayed identity counts only with more than k added `duplicate` lines, otherwise not demonstrated (exit 5), never a pass, so with T4's hundreds of replayed identities any reconnection during the replay leaves its replay half unpassed; `itest-dup-02` is timed (`lost = 0`, `late_confirmations = 0`) *(until 2026-09-30: "whether such duplicates fail T4 is an open question (decision 5 below)")* *(After the battery, 2026-10-03: both parts ran in S1, valid. Replay `itest-dup-01-q1`: `replay-check` 0 — 672 of 672 with a `duplicate` line, none accepted again, the `after` reading quiet, no reconnection (k = 0), twins identical, accounting unchanged. Reset `itest-dup-02-q1`, its first run ever: 672 of 672 in time, `lost` 0, `late` 0, no duplicate, `delta` OK. Class: Pass, both. Decision needed: none; nothing accepted.)* | dup-01: replay copies, twins `same`, the `replay-check` verdict; **dup-02**: `reconcile` with `lost=0`, `late=0`, every `delta` `OK` |
| **T5** dropout and reconnection | Pending, high risk of failure | **Failed**: 326 of 2,016 late | Run it and record the result; option 5 does not change timing, and under throughput choice T1 (ADR 0011, decision B) a family that misses its deadline is recorded as failed. The broker excerpt now comes from the broker log bounded to T5's own run (runbook test 5, `sut_log broker`); guest-unverified *(After the battery, 2026-10-03: ran in S1 as `itest-dropout-01-q1`, valid; 2,016 of 2,016 in time, `lost` 0, `late` 0, `double_accepted` 0, `delta` OK; 3 deliberate dropouts and 165 buffered in the run's manifest and stderr. Two points stand: (1) the bounded broker log holds 4 connections and **4** disconnection lines — the three dropout cycles plus the simulator's terminal `DISCONNECT`, which the bounded read taken after the run always includes — while the Expected list, marked `UNVERIFIED`, says "N+1 connections and N disconnections" and the packet's §5 assigns a count other than that to *inconclusive*; the row is a sealed Pass with that question open, not an unqualified pass. (2) One `check` warning on C10 is a documented layout mismatch (the reconciliation directory lacks the campaign-style simulator manifest); it is preserved, no campaign C10 acceptance is claimed and the frozen helper is not changed. Decision needed: Rui's explicit admission of the interpretation "N fault disconnects followed by reconnect, plus terminal teardown reported separately" (decision 6 below); no repeat is indicated by the count alone.)* | stderr totals, run-scoped broker excerpt, `lost`/`late`, `delta` |
| **T6** controller restart | Pending, high risk of failure *(Blocked until 2026-09-30; see 'Remaining action or blocker')* | `controller_restart-r01/-r02` invalid; the finite proof r03 supported recovery for that run only, with its harness run invalid and a twin `delta` `MISMATCH` | *(Decisions 1a, 2 and 3 adopted 2026-09-30, implemented offline in this change, not yet run on the guest.)* The restart resource gap no longer blocks it, prospectively: the proved-down interval (issue 2) is applied at the harness's ingest when T6's harness line fetches the controller's `StartedAt` (`--fetch-started-at-cmd`); that line runs `controller_restart-r03`, the first `controller_restart` entry unused on the evidence held, and a used entry is refused before anything starts. A valid T6 still needs a complete capture with exactly one `die` and one `start` of `egw-controller-1`, a `StartedAt` within 1 s of that start and both edge gaps within 5 s, none of it shown on the guest. Two risks remain, and each fails T6 if it occurs: an N1 identity still counts as `lost` and gives a `delta` `MISMATCH` (it is now only reported, issue 3), and zero lost at 11.2 msg/s has never been shown (T6's zero lost is C12's, late confirmations included). Under the adopted rules no further decision is needed for a valid pass, so the legend's *Blocked* no longer applies *(until 2026-09-30: "Three blockers, below: the restart resource gap, N1 under the ordinary rules, and zero-lost at 11.2 msg/s never shown.")*. The log and event capture is wired into its harness command (expected `die`, `start` of the controller, not the proof's SIGKILL) and, with the restart-evidence hooks the harness now runs, covers the drain and the post-drain copy (a drain that gives up included); guest-unverified. The normal-sampler, marker-poll and write-failure defects are repaired (LOG #C046, #C047) *(After the battery, 2026-10-03: ran in S2 as `controller_restart-r03`; **invalid instrumentation** under rule 1a, the inner run unsealed, the package's outer seal not validating it. The rule's preconditions held on the guest for the first time — the restart ran with exit 0, the capture is complete with one `die` (`13:37:14.06Z`) and one `start` (`13:37:18.76Z`) of `egw-controller-1`, `StartedAt` within 1 s of the start, the edge gaps 3.0 s and 1.0 s — but the collector wrote two rows of the controller stamped `13:37:17Z` and `13:37:18Z`, inside the interval and in the start's own second, which the rule as written rejects whatever their values. No row is deleted, the validator is not relaxed, the attempt is not relabelled. Delivery is reported only: 4,718 of 6,720 by the deadline in the initial events copy (`lost` 2,002, 82 late), and in the post-drain copy all 6,720 uniquely accepted with 2,002 beyond the deadline, none absent, none duplicate-only — a deadline metric, not permanent loss; recovery 4.75 s functional, 11.9 s endpoint. Two separate questions follow, and fixing the first cannot cure the second: (a) whether such rows invalidate the run, or a prospective validity rule or collection correction with raw-row retention should apply, set out in a separate one-page proposal that adopts nothing; (b) the timed shortfall at 11.2 msg/s, which any runtime change would turn into a new candidate needing requalification. Decision needed: Rui's, on both (decision 7 below); T6 is not automatically appended to the next session.)* | A sealed **valid** run directory; C12 columns of `per_run.csv` (`lost = 0`, `late_confirmations = 0` on T6's own row); every `delta` `OK`; restart record; run-scoped logs and events; the `StartedAt` record and the manifest's `resources_proved_down` |
| **T7** MongoDB **and Ditto** fault | Pending | MongoDB half only (old candidate): 62 failed, 1,012 of 3,298 late. **`itest-ditto-fault-01` has never run** | Run both halves. The MongoDB result is not reusable: contract v1.2 changed the meaning of `failed`. Watch `ditto-things` at its 768 MiB limit. Each fault's Docker events are recorded and judged on the container it stops (`die`, `stop`, `start` of `egw-mongodb-1`, then `egw-ditto-things-1`; runbook test 7, `events_start`/`events_stop`), guest-unverified. Each sub-check also reads the controller and broker logs bounded to its own run; a capture not shown complete or a failed read keeps T7 from 0, with the observed fault facts kept apart *(After the battery, 2026-10-03: both halves ran in S2, valid, each with a complete capture (`die`, `stop`, `start` of the stopped container). MongoDB `itest-mongo-fault-01-q1`: interruption and recovery shown, 44 `failed` after 3 attempts with HTTP 500, acceptance resumed, `delta` OK, N1 report 0/0. Ditto `itest-ditto-fault-01-q1`, its first run ever: 5 `failed` after 3 attempts with a read timeout, acceptance resumed, `delta` OK, N1 report 0/0, no OOM at 768 MiB. Not timed; reported only, `lost` 1,209 (1,165 late) and `lost` 1,895 (1,890 late). Class: Pass, both; no general lossless or prolonged-stability claim. Decision needed: none; nothing accepted.)* | `fault.txt`, `ready.txt`, outcome counts, `delta`, stop/start events |
| **T8** guest reboot | Pending | Shown on the old candidate: 336 events, 0 lost, 0 late | Not yet assessed: a reboot while the broker holds the controller's persistent session (60 s autosave; ADR 0011 open item). Bound the `ditto-things` power-off incident *(After the battery, 2026-10-03: ran in S2 as `itest-reboot-q1`; **inconclusive, not demonstrated — the halt of the battery** (packet §4, halt 5), the package incomplete because the post-reboot artefacts were never written. The guest did reboot, inside the same QEMU process: boot id `d22195a1…` → `76471e31…`, the previous boot ended cleanly at `14:25:44Z`, the new one began at `14:26:15Z`, and the six containers' start times reach `14:26:46Z` with health read later (a read-only step of the session package; directory counts, not byte-for-byte persistence). The runbook's line 1487 assumed a QEMU exit (`-no-reboot`) that the launcher `run-qemu-integrated.sh` never produces, so the procedure waited 600 s for the exit and halted without signalling QEMU; `REBOOT SHOWN`, twins `same`, the controller's state and the fresh timed smoke were not evaluated. A procedure defect, not proof that the Yocto reboot or the persistence failed, and nothing completes T8 retrospectively. The procedure is corrected offline in this block (runbook test 8: a bounded wait for a different boot id, the unaided return of the same container set before any `compose up`, readiness, state and the smoke, with regression tests; LOG #C050). Decision needed: a separately authorised bounded T8/T9 completion session with fresh identities and the procedural revision recorded, its preparation showing the SUT image, containers and configuration unchanged (decision 8 below).)* | Boot IDs, container state, previous-boot journal (OOM check), twins `same`, post-reboot smoke with `lost=0`, `late=0` |
| **T9** TLS and authorisation | Pending (T9's own sub-checks not run on the guest) | Tested checks passed on the old candidate, anonymous refusal included; negative cases remain G3 work | Run again: the broker configuration changed (C1), the ACL did not (C2 declined). T9(b) and (c) now take their evidence from the broker log bounded to each sub-check (runbook test 9, `sut_log broker`, the bound taken 3 s back for the guest clock's steps), no longer `--tail 20`; guest-unverified *(After the battery, 2026-10-03: **not run** — S2 halted at T8, and the packet's halt rules keep T9 from starting after a T8 halt. Its lines at `80e833f` remain unexercised on the guest. Decision needed: the same separately authorised T8/T9 completion session (decision 8 below).)* | `verdict.txt` = `PASS` (an inconclusive result is never a pass), subscriber outputs, run-scoped broker excerpt for (b) and (c), `/metrics` unchanged |

## The issues the work order names

**1. The normal sampler.** Until 2026-09-29 the default controller-metrics
sampler let a typed `http.client.HTTPException` (such as `IncompleteRead`, a
kill between a response's headers and its body) end its thread, or raise from
the entry poll; for T6 a dead sampler would have removed the post-restart rows
and C12 would have failed on instrumentation. This block repairs it (LOG
#C046): the failure is a counted failed poll in every mode. r03 did not exercise
the defect (its failures were `RemoteDisconnected` and connection resets, which
are `OSError`s). The two items deferred then are repaired on 2026-09-29 (LOG
#C047): a typed failure of `poll_controller_marker` is a named failed
acquisition (no marker, no deadline), and a write failure of either sampler
stream makes the run invalid with a named reason instead of ending the thread
silently.

**2. The resource gap at a restart.** `MAX_SAMPLE_GAP_S` = 5 s applies to every
container series; an excess gap rejects `resources.csv` and the harness marks
the run invalid. Every restart recorded so far exceeded it:

| Run | Gap at the restart |
|---|---|
| `controller_restart-r01` | 9.0 s (and later 6.0 s gaps) |
| `controller_restart-r02` | 6.0 s |
| Finite proof r01 / r02 / r03 | 8.0 s / 9.0 s / 8.0 s |

A collector cannot sample a container that is down, so a faster collector does
not remove the gap. *(Decision 1a adopted 2026-09-30, implemented offline in
this change, not yet run on the guest.)* Rui adopted, prospectively, the
narrower proved-down interval of the
[pending-decisions page](proposals/2026-09-29-g3-pending-decisions.md), not the
2026-09-19 window from the restart command to `/ready`. It applies at the
harness's run-time ingest, in a `controller_restart` run given the controller's
`StartedAt` read (`--fetch-started-at-cmd`), which T6's harness line passes and
the finite proof does not. For `egw-controller-1` only, and only when the
restart ran with exit 0, the capture is `complete`, exactly one `die` (D) and
one `start` (S) of it fall in the capture window with one container id, and
`StartedAt` agrees with S to 1 s: the rows missing between D and
E = min(S, D + 120 s) are not a gap. Both edge gaps keep the 5 s rule, a row
between D and S, or in S's own second, is rejected, and anything ambiguous
grants no interval. No row is added, zero-filled or interpolated, and no
delivery, recovery or C12 figure changes. The past runs stay invalid under the
rules they were run with: none captured the lifecycle. Whether the edge gaps
stay within 5 s under TCG is unmeasured, and the guest clock's 1–3 s backward
steps are not absorbed. The rule touches only T6: T1 has no restart, and T5, T7
and T8 run through `run_test` and ingest no resources *(until 2026-09-30: "The
lifecycle-aware rule is proposed, not adopted. Until a prospective decision,
T6's harness run stays invalid")*. *(After the battery, 2026-10-03: the rule
ran on the guest once, in `controller_restart-r03`. Its preconditions held —
exit 0, a complete capture with one `die` at `13:37:14.06Z` and one `start`
at `13:37:18.76Z`, `StartedAt` 0.06 s before the start, the edge gaps 3.0 s
and 1.0 s — so the interval was derived; the file was then rejected because
two rows of `egw-controller-1`, stamped `13:37:17Z` and `13:37:18Z`, fall
inside it and in the start's own second. The manifest's
`resources_proved_down` records both (`rows_between`,
`rows_in_start_second`). The rows are whole-second, pre-read sample stamps,
so "sampled 1.7 s before Docker's start" is an explanation to qualify, not a
proven timing fact; what the cgroup of a restarting container shows between
Docker's `die` and `start`, and how the collector stamps a row, is the
subject of a separate one-page proposal with the exact rows, options and
bounded regression cases, which adopts nothing. Under the rule as written the
run is invalid; nothing here relaxes it.)*

**3. N1, `delta` and loss under the ordinary rules.** `lost` is a valid message
without a unique confirmation inside the 60 s window. An N1 identity has only a
`duplicate` line, so it **counts as `lost`** until the separate decision ADR
0011 reserves, which fails C12's zero-lost; it also makes `delta` report a twin
surplus as `MISMATCH`, which fails T6's "every `delta` line OK". It is not a
double acceptance. Every proof kill produced one; whether a graceful restart
also does is unknown. *(Decision 2 adopted 2026-09-30, implemented offline in
this change, not yet run on the guest.)* Such an identity is now reported, and
only reported: the column `n1_applied_unconfirmed` of
`processed/recovery_qualification.{csv,json}` counts it and the JSON's per-run
`n1` record names it (the rule is in `src/egw_experiments/n1_report.py`), and
`delta` annotates its `MISMATCH` line through its new options (`--n1-report`,
`--controller-log`, `--restart-evidence`), under three conditions —
duplicate-only lines, a recorded source (the restart's captured `die` or an A3
connection end), and the twin's Δ`accepted_count` surplus with `last_seq` —
judged per device, all or nothing.
Every other duplicate-only identity is `duplicate_only_unexplained`. The
paragraph above still holds: the identity counts as `lost`, the `delta` line
stays `MISMATCH`, and the counting decision ADR 0011 reserves is not taken.

**4. Timed delivery.** The option-5 candidate has never been measured against
its deadlines on a valid run.

| Run | Finding |
|---|---|
| `nominal-r01` (2026-09-19) | 3,794 of 6,720 in the window; 6.457 msg/s served over the measured window (60 s blocks 5.32–8.55 msg/s) against 11.2 offered (ADR 0011, section 1) |
| T5 / T3 / T7 (MongoDB), 2026-09-18 | 326 of 2,016 / 132 of 1,277 / 1,012 of 3,298 late |
| T2, 2026-09-18 | in time, with a 3.1 s margin |
| T6 recovery bound | 120 s (`RESTART_RECOVERY_MAX_S`), never shown on a qualifying run |

Under throughput choice T1 (ADR 0011, decision B) each timed family that misses
its deadline is recorded as failed, so G3 is not met on it. *(Decision 3
adopted 2026-09-30, implemented offline in this change, not yet run on the
guest.)* The timed families are T1 (each of its three runs), T2, T4's sequence
reset `itest-dup-02`, T5, T6 and T8's post-reboot smoke, each needing
`lost = 0` and `late_confirmations = 0` against the marker plus 60 s. A miss is
a failure, and it is also recorded as a sizing finding, which does not turn it
into a pass. T3 is not timed, but a valid identity never accepted by its
post-drain copy fails it (T3 row). No deadline, rate, duration or load changed
*(until 2026-09-30: "whether T3, whose Expected list names no deadline, is one
of them is decision 3 below")*.

*(After the battery, 2026-10-03: the candidate's first measurements against
its deadlines on valid runs, all emulated and informational.)*

| Run (2026-10-02/03) | Finding |
|---|---|
| T1 smokes `itest-smoke-01/02/03-q1` (30 s, timed) | in time, 336 of 336 each; the first smoke's p95 about 50 s and maximum about 51 s against the 60 s deadline, the later runs far lower |
| T1 harness `nominal-r02` (valid; delivery reported only) | 4,584 of 6,720 in time, `lost` 2,136 (111 late): not successful nominal delivery |
| T2 `itest-3dev-01-q1` (timed) | in time, 672 of 672 |
| T3 `itest-invalid-01-q1` (120 s; not timed, reported only) | `lost` 0, `late` 0 for the 1,277 valid identities |
| T4 reset `itest-dup-02-q1` (timed) | in time, 672 of 672 |
| T5 `itest-dropout-01-q1` (timed) | in time, 2,016 of 2,016 (on 2026-09-18, 326 late) |
| T6 `controller_restart-r03` (invalid; reported only) | 4,718 of 6,720 by the deadline in the initial copy (`lost` 2,002, 82 late); post-drain copy: all 6,720 accepted, 2,002 beyond the deadline, none absent — a deadline metric, not permanent loss; recovery 4.75 s functional, 11.9 s endpoint, within the 120 s bound on an invalid run |
| T7 MongoDB / Ditto (not timed; reported only) | `lost` 1,209 (1,165 late) / `lost` 1,895 (1,890 late) |

Every long row at 11.2 msg/s (the harness run and T6 for 600 s, each T7
fault for 300 s) left a large late backlog under TCG; the 30 s, 60 s, 120 s and
180 s rows, at the same rate, were in time. For T6, which is timed, this
is a second question beside its admissibility, and no resource-validity change
answers it; any runtime change makes a new candidate.

**5. Logs and Docker events.** r03's controller and broker logs were not scoped
to the run and its Docker events did not cover the kill. This block, in the
proof driver (`tools/session/proof.sh`), bounds both log copies by the run's
guest-clock boundaries and adds a continuous event recorder whose coverage is
judged, tested with stubs only. On 2026-09-29 (LOG #C047) the same scripts
were wired into the runbook: `harness_cmd` for T1 and T6 (T6's window
covering its drain), the bounded logs of T3, T5, T7 and T9(b)/(c), and each T7
fault's events on its own container; a failed capture, read or cleanup
reaches the procedure's result, and a capture shown complete stays complete
when only the cleanup after it failed (PR #51 bounded review). Every
family path is exercised with stubs only. On 2026-09-30 one authorised session
(`compat-capture-r01`, LOG #C048) verified the shared capture helpers
compatible on the guest in a short window, without load or faults: the
recorder under the guest's systemd and BusyBox, the controller and broker
logs bounded from one T0 (Docker 25.0.9 and Compose v2.26.0 accept
`--since`/`--until` as epoch seconds), the closing marker, and the capture
judged complete under R1–R6 (R7 not exercised). No family's own procedure ran
on the guest: the test lines of T1, T3, T5, T6, T7 and T9(b)/(c) (their own
bounds, STOPs and judgements, T9's bound taken 3 s back among them), the T6
and T7 event sets, delivery and log volume under load, the harness path end
to end and an interactive Ctrl-C remain unverified there. It is not G3
readiness. T8 is not wired. *(After the battery, 2026-10-03: the families'
own lines ran on the guest for the first time in S1 and S2 — the bounded logs
of T3, T5, T7 and the two harness windows of T1 and T6, each capture judged
complete, the T6 and T7 event sets recorded (`die`/`start` of the controller;
`die`, `stop`, `start` of each stopped service), the drains and post-drain
copies of T3 and T6; T9's lines did not run. T8's procedure, not wired to
the capture, failed on its own assumption of a QEMU exit (T8 row) and is
corrected offline in this block.)*

**6. Other G3 conditions.** The candidate lock record is pending. The contracts
are at v1.2 while the backlog's cut rule still names v1.1: a freeze record is
needed. The `ditto-things` incident is mitigated, not declared stable. Whether
`gate_health.sh`, `accounted` and `delta` share `drained`'s former wall-clock
blind spot is not assessed. The broker window and queue (W, Q) against the
families' backlogs is open. There is no versioned battery driver. *(After the
battery, 2026-10-03: the candidate was frozen by the decision packet of
2026-10-01, revision 2, and the battery authorised by Rui on 2026-10-02 (both
held locally under `output_test/decisions/`); the v1.2 freeze record is the
packet's Q1. The battery ran under an operator's steps script,
`g3_battery.sh`, with the row files extracted from the `80e833f` runbook,
verified three ways and benched with stubs before S1; it is sealed in the
host-preparation package, not versioned in this repository. The
`ditto-things` service held at 768 MiB through both sessions, its own fault
included, without a memory-cgroup OOM kill in any of the three boots — a
bounded observation, not stability. W and Q against the backlogs were not
assessed on these records; the arithmetic check remains the only one.)*

## Decisions to surface (none made here)

The four methodology decisions are set out, with exact proposed wording and a
recommendation each, in the
[pending-decisions page](proposals/2026-09-29-g3-pending-decisions.md).

1. Adopt or decline the lifecycle-aware restart rule, prospectively. Until then
   T6 stays invalid.
2. The analysis rule for N1 identities. Until then any N1 in T6 is a loss and a
   `MISMATCH`, and T6 fails.
3. Timed families that miss their deadlines are recorded as failed; which
   families are timed (T3's late confirmations among them) and any change to
   G3's scope need a dated prospective decision.
4. The candidate lock and the authorisation to resume the qualifying battery.
5. Whether duplicates added by a reconnection under option 5 fail T4's
   "duplicate = replayed count", or are reported beside it.

*(Marker added 2026-09-30: decisions 1, 2, 3 and 5 above were taken by Rui on
2026-09-30, prospectively and with conditions — the
[pending-decisions page](proposals/2026-09-29-g3-pending-decisions.md),
"The decision of 2026-09-30"; LOG #C049. Adopted 2026-09-30, implemented
offline in this change, not yet run on the guest. Decision 2 adopted reporting
only, so its consequence above still holds: an N1 identity in T6 is a loss and
a `MISMATCH`, and T6 fails. Decision 4, the candidate lock and the
authorisation to resume the qualifying battery, remains; G3 stays paused.)*

*(Marker added 2026-10-03: decision 4 was taken — the candidate was frozen by
the decision packet of 2026-10-01, revision 2, and the battery authorised by
Rui on 2026-10-02 — and the battery ran in S1 and S2 (LOG #C050). Three
decisions now stand after it, each Rui's and none taken here; the
[results addendum](g3-battery-2026-10-results.md) states them with their
figures:)*

6. *T5's interpretation.* Whether to admit explicitly the reading "N fault
   disconnects followed by reconnect, plus terminal teardown reported
   separately" for a bounded broker log with N+1 connections and N+1
   disconnection lines; until then the row is a sealed Pass with that
   question open, never an unqualified pass.
7. *T6's admissibility and its timed criterion*, two separate questions:
   whether collector rows inside the proved-down interval invalidate a run as
   rule 1a is written, or a prospective validity rule or collection
   correction with raw-row retention applies to future runs (a separate
   one-page proposal, adopting nothing); and the timed shortfall at
   11.2 msg/s, which no resource-validity change cures and which any runtime
   change would turn into a new candidate needing requalification. T6 is not
   automatically appended to the next session.
8. *T8 and T9's completion.* A separately authorised bounded session, with
   fresh run identities and the corrected T8 procedure recorded, whose
   preparation shows the SUT image, containers and configuration unchanged
   and keeps the prior results for assessment.

*(G3 stays `Not decided`; G4 and the campaign are not released; no criterion
is weakened for time and the 2026-10-20 target is not moved by this page.)*
