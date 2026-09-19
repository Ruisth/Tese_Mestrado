# Formal gate-decision log

> **Decision-only authority.** `PROGRESS.md` remains the sole source of current
> operational state. This log records only formal gate outcomes and the dated
> decision record that supports them. Producing evidence, passing CI, merging a
> pull request or remaining silent never changes a gate to accepted. **Adopting
> a plan version accepts no gate and admits no claim.**

Updated: 2026-09-19.

Permitted formal outcomes are `Not decided`, `Accepted`, `Rejected` and `Cut`.
An outcome other than `Not decided` requires a date, the decision authority and
a durable decision record. `LOG.md` may record that the action occurred, but it
is a diary and is not the decision authority.

**A supervisor confirmation reported by the student is not a decision record.**
The confirmations held in
[`supervisor_decision_log.csv`](supervisor_decision_log.csv) under the statuses
`confirmed_reported_by_student` and `partly_confirmed_reported_by_student` carry
no date, no message and no supervisor name. **No gate outcome below changes
because of them**, and no future row may cite one as its decision record.
*(Added 2026-09-19:)* G0's acceptance of that date is no exception: its decision
record is the student's own gate-closure statement, and the reported
confirmations stay reported inside the baseline it accepts.

**Two dates, and what each one means.** The confirmations were recorded in the
project-management record of **2026-09-18**; that is the date a note names when it says
"recorded", "superseded" or "dated note of" 2026-09-18, and it is not the date of
the supervisor conversation, which was not reported. **The convention binds every
document, not only the two registers:** a narrative record — this log, the claim
matrix, `PROGRESS.md`, the risk register, a backlog row — may date the *recording*
of a reported confirmation and may never date the supervisor's act itself, so
"instructed on", "waived on", "settled on", "agreed on", "decided on",
"approved on" and "confirmed on" followed by a date are wrong wherever they
appear — and so are the same verbs with an agent interposed ("waived by the
student on 2026-09-18") and a bare parenthetical date set beside a reported act
*(added 2026-09-19 after such phrasings were found in the narrative documents of
this change and corrected; the list names forms, it does not close the rule)*. The register rows themselves, and every narrative record that cites
them, were **written on 2026-09-19**. The confirmations remain undated.

The **prospective** acceptance criteria for G2 to G7 under the adopted plan
v2.0 and its QEMU-only execution amendment are published in section 4.3 of
[`INTEGRATED_DEVELOPMENT_PLAN_2026.md`](INTEGRATED_DEVELOPMENT_PLAN_2026.md).
They state what would have to be true before a gate decision could be recorded;
they are not decisions and none of them is met. A gate decided on emulated
evidence records that fact in its own row.

| Gate | Formal outcome | Decided at | Decision authority | Evidence available | Decision record | Notes |
|---|---|---|---|---|---|---|
| G0 | **Accepted** | 2026-09-19 | Student (Rui Duarte) | [Decision record and residual obligations](decisions/2026-09-19-g0-closure.md); [current operational state](../../PROGRESS.md) | [`decisions/2026-09-19-g0-closure.md`](decisions/2026-09-19-g0-closure.md), a durable copy of the dated project-management register entry of 2026-09-19 that holds the student's statement and the project manager's concurrence; narrative in `LOG.md` #C035 | Accepted **for project initiation and baseline alignment**. This is a dated change of G0's exit scope, **not** a retroactive pass against the legacy conditions. The decision source is the student's own statement, "Penso que o G0 se pode considerar fechado", with which the project manager concurs; it is not a reported supervisor confirmation, not an inferred supervisor decision and not the merge of pull request #35. The items of the accepted baseline that the student reports confirmed stay reported, undated and undocumented. **Residual obligations are reallocated, not performed** (table in the decision record): integration defects and admissible run evidence to G2/G3; D007 thresholds, fault-window rules, loads, 95-run feasibility and the frozen protocol to G4; genuinely unsettled method or claim detail tracked at G4/G6, with no blanket D014 blocker; scoping-review execution and writing to Chapters 1-4 and G6; template check, AI declaration and final evidence package to G7; the verified off-machine copy, hash and restore path stay an active resilience action owned by the student (risk R25), required at G7 and **neither verified nor waived here**. The alignment package is not marked sent. No other gate, no claim and no evidence is accepted. The state this row replaces is kept under "Superseded row states" below. |
| G1 | **Accepted** | 2026-08-14 | Student (Rui Duarte) | [Clean build and strict five-boot seal](../evidence/g1-yocto-qemu/2026-08-14-clean-build-f0e19d5/README.md) | This row, merged through a pull request under the six required checks; narrative in `LOG.md` #C015 | Accepted against the plan v1.1/v1.2 §4 criterion: clean identified checkout build `f0e19d5` (5,715 tasks) and five strict boots (`qemu-g1r2-01..05`), each passing all seven required assertions with exact `systemd=running`, zero failed units and a clean shutdown; the failed first attempt is preserved in the same capsule. **Scope of the decision:** functional platform layer only. It validates no claim (C01/C02 stay partial pending admission), supports no performance statement, and leaves D006 (second-operator reproduction) a separate supervisor decision. |
| G2 | Not decided | — | — | [Current operational state](../../PROGRESS.md) | — | Native deployment is outside the adopted scope. A bounded end-to-end flow was produced inside the emulated Yocto guest on 2026-09-18; its evidence is held outside the repository and is unsealed, so no acceptance evidence exists. |
| G3 | Not decided | — | — | [Current operational state](../../PROGRESS.md) | — | The nine integration/recovery test families were exercised once on 2026-09-18. *(Corrected 2026-09-19: this note said that seven passed and that tests 1 and 6 carried a failing harness part, and called the record unsealed; re-verification of the per-test records showed the first to overstate the result and the second to be wrong.)* Per test: functional results were demonstrated for test 2 (672 of 672 valid events delivered in time, 0 lost, 0 late, with a margin of 3.1 s) and test 8 (the reboot changed the boot id, the twin counters persisted and a fresh 336-event run reconciled with 0 lost and 0 late), and the tested checks of test 9 passed (wrong CA, wrong password, plaintext and anonymous access refused; ACL probe passed), which is not a general security assurance. The specific behaviour under test was demonstrated for test 3 (67 of 67 intended-invalid payloads rejected, none accepted, no valid one rejected; but 132 of 1,277 valid events were confirmed late), test 4 (672 duplicates, none double-accepted) and test 7 (bounded retry under the MongoDB fault: 62 failed after three attempts and 1,012 of the 3,298 accepted events were late, so not lossless delivery). **Test 5 fails its stated criterion**: all 2,016 valid events were eventually accepted, but 326 after the deadline, where the runbook requires `lost = 0` and `late_confirmations = 0`. **Not run:** the sequence-reset sub-check of test 4 (`itest-dup-02`) and the Ditto repeat of test 7, both written in runbook prose that the extracted test scripts did not include. **Invalid:** the timed harness runs of tests 1 and 6 (r01 and r02), whose resource files were not ingested; test 6 also lost its controller metrics across the restart, so its recovery and delivery are not accepted; of test 1, only three ad-hoc repetitions are recorded. The record is a locally hash-sealed candidate archive held outside the repository (all 312 `SHA256SUMS` entries verify), not incorporated into or admitted by the project evidence record; its outer seal does not make a nested invalid run valid. The battery is **not complete** and nothing has been measured, so no acceptance evidence exists. The instrumentation defect is a separate change. |
| G4 | Not decided | — | — | [Current operational state](../../PROGRESS.md) | — | No bounded pilot and no `exp-v1` protocol freeze have occurred; D007 is unsent. |
| G5 | Not decided | — | — | [Current operational state](../../PROGRESS.md) | — | No frozen emulated functional campaign has occurred. Since 2026-09-19 the 95-run composition, the 24-hour soak included, is the quantity the campaign **attempts to reach** under emulation, subject to the bounded pilot's feasibility check; this supersedes the note that they were not carried over. The attempt is not the frozen protocol and promises no valid run count. The gate stays `Not decided`. |
| G6 | Not decided | — | — | [Current operational state](../../PROGRESS.md) | — | Sealed-data analysis and claim admission have not occurred. |
| G7 | Not decided | — | — | [Current operational state](../../PROGRESS.md) | — | Complete thesis/reproduction package and final review have not occurred. |

The native Yocto boot formerly tracked as **G1B** is withdrawn from the
mandatory gate set and **deferred with the native route** (adopted plan
section 4.2). It has never had a row in this log and none is opened; the
deferral is recorded here so that the history is not lost.

## Superseded row states

Kept verbatim so that a changed outcome never erases the state it replaced.

**G0, until 2026-09-19** — replaced by the acceptance recorded in
[`decisions/2026-09-19-g0-closure.md`](decisions/2026-09-19-g0-closure.md). The
two conditions this row named were reallocated by that decision, not performed:
the alignment package is still unsent and the verified off-machine copy is still
outstanding.

| Gate | Formal outcome | Decided at | Decision authority | Evidence available | Decision record | Notes |
|---|---|---|---|---|---|---|
| G0 | Not decided | — | — | [Current operational state](../../PROGRESS.md) | — | The reduced alignment package — D007, D014 and the unresolved halves of D004 and D010 — remains unsent, and the verified off-machine copy remains outstanding. The confirmations the student reports, recorded on 2026-09-18 and published here on 2026-09-19, narrow what has to be sent; they close nothing here. The university ARM64 request is deferred with the native route and is no longer a condition of this gate. |
