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

**Two dates, and what each one means.** The confirmations were recorded in the
project-management record of **2026-09-18**; that is the date a note names when it says
"recorded", "superseded" or "dated note of" 2026-09-18, and it is not the date of
the supervisor conversation, which was not reported. **The convention binds every
document, not only the two registers:** a narrative record — this log, the claim
matrix, `PROGRESS.md`, the risk register, a backlog row — may date the *recording*
of a reported confirmation and may never date the supervisor's act itself, so
"instructed on", "waived on", "approved on" and "confirmed on" followed by a date
are wrong wherever they appear *(added 2026-09-19 after six such phrasings were
found in the narrative documents of this change and corrected)*. The register rows themselves, and every narrative record that cites
them, were **written on 2026-09-19**. The confirmations remain undated.

The **prospective** acceptance criteria for G2 to G7 under the adopted plan
v2.0 and its QEMU-only execution amendment are published in section 4.3 of
[`INTEGRATED_DEVELOPMENT_PLAN_2026.md`](INTEGRATED_DEVELOPMENT_PLAN_2026.md).
They state what would have to be true before a gate decision could be recorded;
they are not decisions and none of them is met. A gate decided on emulated
evidence records that fact in its own row.

| Gate | Formal outcome | Decided at | Decision authority | Evidence available | Decision record | Notes |
|---|---|---|---|---|---|---|
| G0 | Not decided | — | — | [Current operational state](../../PROGRESS.md) | — | The reduced alignment package — D007, D014 and the unresolved halves of D004 and D010 — remains unsent, and the verified off-machine copy remains outstanding. The confirmations the student reports (2026-09-19) narrow what has to be sent; they close nothing here. The university ARM64 request is deferred with the native route and is no longer a condition of this gate. |
| G1 | **Accepted** | 2026-08-14 | Student (Rui Duarte) | [Clean build and strict five-boot seal](../evidence/g1-yocto-qemu/2026-08-14-clean-build-f0e19d5/README.md) | This row, merged through a pull request under the six required checks; narrative in `LOG.md` #C015 | Accepted against the plan v1.1/v1.2 §4 criterion: clean identified checkout build `f0e19d5` (5,715 tasks) and five strict boots (`qemu-g1r2-01..05`), each passing all seven required assertions with exact `systemd=running`, zero failed units and a clean shutdown; the failed first attempt is preserved in the same capsule. **Scope of the decision:** functional platform layer only. It validates no claim (C01/C02 stay partial pending admission), supports no performance statement, and leaves D006 (second-operator reproduction) a separate supervisor decision. |
| G2 | Not decided | — | — | [Current operational state](../../PROGRESS.md) | — | Native deployment is outside the adopted scope. A bounded end-to-end flow was produced inside the emulated Yocto guest on 2026-09-18; its evidence is held outside the repository and is unsealed, so no acceptance evidence exists. |
| G3 | Not decided | — | — | [Current operational state](../../PROGRESS.md) | — | The nine integration/recovery test families were exercised once on 2026-09-18: seven passed, and tests 1 and 6 carry a failing harness part, because the resource sampler under test cannot reach the harness's minimum sample count under emulation. That record is held outside the repository and unsealed, the battery is **not complete** and nothing has been measured, so no acceptance evidence exists. The instrumentation defect is a separate change. |
| G4 | Not decided | — | — | [Current operational state](../../PROGRESS.md) | — | No bounded pilot and no `exp-v1` protocol freeze have occurred; D007 is unsent. |
| G5 | Not decided | — | — | [Current operational state](../../PROGRESS.md) | — | No frozen emulated functional campaign has occurred. Since 2026-09-19 the 95-run composition, the 24-hour soak included, is the quantity the campaign **attempts to reach** under emulation, subject to the bounded pilot's feasibility check; this supersedes the note that they were not carried over. The attempt is not the frozen protocol and promises no valid run count. The gate stays `Not decided`. |
| G6 | Not decided | — | — | [Current operational state](../../PROGRESS.md) | — | Sealed-data analysis and claim admission have not occurred. |
| G7 | Not decided | — | — | [Current operational state](../../PROGRESS.md) | — | Complete thesis/reproduction package and final review have not occurred. |

The native Yocto boot formerly tracked as **G1B** is withdrawn from the
mandatory gate set and **deferred with the native route** (adopted plan
section 4.2). It has never had a row in this log and none is opened; the
deferral is recorded here so that the history is not lost.
