# ADR 0011 — review annex

- **Date:** 2026-09-21
- **What this is:** the review history of `adr-0011-controller-restart-recovery.md`, moved out of the record so that the ADR keeps the repository's short form (`docs/adr/README.md`). It is part of the package D review record and does **not** enter `docs/adr/`. It adds no claim: every row points at where the ADR now says what it says.
- **Sources of the findings:** round one, `../verification_figures.md` and `../verification_constraints.md`; round two, `verify_figures.md` (findings X1–X3, R-A1–R-A11 and the figure verdicts A1–A37) and `verify_constraints.md` (findings F1–F19 and section 5), all in the package D working directory.

## 1. Round one: corrections to the draft of 2026-09-20

As it stood in the ADR before this annex was created; rows 4, 11 and 17 are reworded to match the corrected record.

| # | draft | now | source of the finding |
|---:|---|---|---|
| 1 | r01: "1,405 identities with no outcome" | 2,182 without an outcome (1,760 + 422); 1,405 is r01's still-queued-plus-residual (1,404 + 1) | `verification_figures.md` 2.4; [F:R01.1–R01.4] |
| 2 | nominal: "2,841 … turned out to be 0 lost and 2,926 late" | the 2,841 ended 2,841 late; 2,926 is the run's total late, including the 85 already late at the fetch; each population with its collection instant | `verification_figures.md` 2.4; [F:N.1, N.2] |
| 3 | "all 326 … a direct observation, not a deduction" | the 326 cannot be identified by any artefact; what is observed is that all 2,136 have no outcome; the `duplicate`-count argument does not exclude redelivery | `verification_figures.md` A4 |
| 4 | "1,809 proved discarded", "the largest proved loss class" | at least 1,809 by arithmetic on the poll ledger; "still queued at the stop" and "discarded" ASSUMED on the source reading; 151 carries the clock caveat | `verification_constraints.md` B4 |
| 5 | Consequences: classes "disappear", are "closed" | conditional, and only after the decision and the proof | `verification_constraints.md` B3 |
| 6 | promise: redelivery "is idempotent at the twin" | P4: intended; the least supported promise; tested by the proof | `verification_constraints.md` B5 |
| 7 | promise: the overflow path "becomes unreachable" | removed; replaced by the explicit window constraint and recorded broker values | `verification_constraints.md` B6; `verification_figures.md` B6 |
| 8 | "no measured per-message I/O added" | the `ack` cost is unmeasured, not absent | `verification_constraints.md` B7 |
| 9 | "ceiling" of 6.46 and 8.86 msg/s on 154.77 / 112.82 ms budgets | phase rates of one failed run, labelled as such; the 154.77 ms base (19.4 % warm-up acknowledgements) is not used | `verification_constraints.md` B1; `verification_figures.md` B1, A2 |
| 10 | option 2 "per-message cost: none" | none on the controller's path; the broker's cost unmeasured | `verification_figures.md` B7 |
| 11 | proof at 5.0 msg/s, "+1.457 msg/s headroom", restart at t+90 s | 11.2 msg/s, kill at t+150 s, no timing in any criterion; the old sizing assumed a rate the nominal warm-up (4.94) and slowest window block (5.32, event log) fell below, and could have left nothing in flight | `verification_figures.md` B5; [F:N.5, N.7] |
| 12 | proof burst sized from the outage only | the burst of deliveries in flight at the kill is the thing under test (S1) | `verification_constraints.md` 4(e) |
| 13 | "180 s precondition" | the helper's 130 s default quiet window, 490 s where the runbook requires it | `verification_figures.md` 1.9 |
| 14 | three references to "section 6" | "the finite proof" | `verification_constraints.md` B10 |
| 15 | "Gate G3 is not decided, so an ADR-backed change is admissible now" | the plan requires an ADR and regression tests; admission is the student's, with the project manager's review | `verification_constraints.md` B9 |
| 16 | "cannot produce a valid run at all" | unresolved (N8) | `verification_figures.md` C1 |
| 17 | "about 370 s to drain 1,867" (a rate under ingress) | an illustration only: 211 to 378 s at `nominal-r01`'s phase rates, 341 to 370 s at r02's own old-process rates | `verification_figures.md` C2; `verify_figures.md` R-A6; [F:S.2, R02.12] |
| 18 | `src/CONTRACTS.md:284-286` for the marker sentence; `analyze.py:1765` | `:282-283`; `:1766` | `verification_figures.md` 2.1 |
| 19 | the code "byte-identical to the commit deployed" | identical to the harness commits of the runs; the image's own source commit is not recorded (ASSUMED) | `restart_evidence.md` section 8, item 6 |
| 20 | acknowledgement "once and only once, in the consumer's `finally`" | only after an outcome line, never without one, and only on the delivering connection | this record, section "Ordering, duplicates…" |
| 21 | head `ccd5fd6` | merged `dev` `35fe8bb`; no cited file changed between them [C] | [C] |

## 2. Round two: corrections of 2026-09-21, from the second pair of verification reports

| Finding | Before | Now, in the ADR |
|---|---|---|
| X1, F8, A36 — T3 described the round-one probe | "the capacity probe proposed in `backlog_diagnosis.md` section 7 … 5.0 msg/s … 4.94 … 5.35" | T3 cites the diagnosis's section 11 measurement: 2.24 msg/s for 720 s, sized below 4.60 / 3.83 / 3.00 msg/s; not a capacity probe; neither run depends on the other |
| R-A1, F4 — restart counterfactual on `nominal-r01` | "a kill at that instant would have put those 3,593 …", CONSISTENT-WITH | removed; the observed count and the source reading of where it was held (ASSUMED) remain (section 1.7) |
| R-A3, A16, A18, A11, A12, F2 — cross-clock instants and group sizes labelled PROVED | controller stamps mapped through the guest wall and compared with harness instants: 14.646 s, 15.906 s, 10.5 / 10.8 s, 00:18:29.990Z, r01 G2/G3a/G3b 122 / 51 / 182 | every controller stamp compared with a harness instant mapped through `polled_utc`: 14.690 s, 15.791 s, 10.6 / 10.7 s, 00:18:30.034Z; r01 121 / 51 / 183 (52 / 182 with the collector row as recorded); only G1 PROVED, the other cuts CONSISTENT-WITH (sections 1.3, 1.5) |
| R-A10, F2 — "at least 1,809 / 1,404 … PROVED" | PROVED | arithmetic PROVED; "still queued when the process stopped" ASSUMED, with the exception path named (sections 1.1, 1.2) |
| F2 — "written by the new process" | PROVED | the counts PROVED; "written by the new process" ASSUMED from FIFO order (section 1.4) |
| F3 — bounds without labels | unlabelled | the two clock-free ends named (1,809 / 1,404 and 327 / 356); the other ends CONSISTENT-WITH; the class names ASSUMED on 2(e) (section 1.3) |
| R-A11 — "eleven identities per second" from a round-one analysis | cited from `restart_evidence.md` | derived from the offered 11.2 msg/s [F:R02.0, R02.7] (section 1.3) |
| X3 — on time and late not separated in the restart runs | "with an outcome" only | r02 3,819 = 3,795 + 24, fetch 2.534 s after the deadline; r01 4,538 = 4,439 + 99, fetch 8.305 s after it (sections 1.1, 1.2) |
| R-A4, A27 — option 2's "151 to 371" | time-based, above the class's identity bound | the identity-based bounds of section 1.3: at least 151, at most 327 (option 2) |
| F9 — "in no phase … reached 11.2 msg/s" | read as a ceiling | "in none of the three phase averages, and in no 30 s block of the window"; the 11.60 msg/s after ingress stopped stated (option 2) |
| R-A6, F10 — "1,867 need 211 to 378 s" | another run's rates stated as a need | an illustration on `nominal-r01`'s rates, beside r02's own 5.051 and 5.476 msg/s (370 and 341 s) (section 1.8, Consequences, Alternatives rejected) |
| X2, F19, A23 — two constructions of the window's 60 s blocks | 5.35–8.57 msg/s, unstated method | the diagnosis's event-log construction, 5.32–8.55 msg/s [F:N.7] (section 1.8) |
| F1 — "What the controller guarantees today" | a heading that promised a guarantee | "What the controller does today (source reading at `35fe8bb`)" (section 2) |
| F11 — "lost" in the comparison table | the analysis term used for discards | "discarded (source reading)" and "never delivered (clean session, ASSUMED)" (section 3) |
| F7 — "a guest that is already the constraint" | stated twice | "a guest that served below the offered rate in every observed phase of one run" (Decision, Alternatives rejected) |
| R-A5 — P5 and redeliveries | "`latency_ms` keeps its meaning" for every delivery while the window is not full | first deliveries only; redeliveries are timed from their redelivery and reported apart (P5, comparison table, Consequences) |
| R-A7 — acknowledgement order | not discussed | PUBACK gaps and the MQTT 3.1.1 ordering rule noted under "Ordering"; the rule, Mosquitto's behaviour and the choice for a delivery without a line on a live connection made open items (acknowledgement row; "Open before the decision", item 5); a test added |
| F5 — the `drained` precondition tightened as a "must" | "must also require `processing_errors == 0` and `dropped == 0`" | a procedure change for the student, applying to all nine families ("Open before the decision", item 6); `qemu_integrated_gateway.md:1004` added to "What must change"; the test made conditional |
| R-A8, A31 — N8 on r01 | "rejected both … at the restart" | r01's seven gaps, including the 6.0 s gaps at 21:59:30Z–21:59:36Z about four minutes after the restart; a lifecycle-aware rule would not by itself have admitted r01's file (N8) |
| A33, A34, F15 — proof timing | "16 to 28 minutes"; "hard ceiling 35 minutes" | 17 to 29 minutes with the 60 s confirmation wait; a 36-minute planning ceiling, not a bound, with what it excludes (the finite proof) |
| R-A9 — "nothing in option 5 changes those figures" | contradicted N6 | "nothing in option 5 would improve those figures" (Relationship) |
| F6 — T1 paraphrased the plan | "recorded as failed and as a sizing finding, never absorbed …" | the plan quoted (T1) |
| F12 — plan and `PROGRESS.md` anchors | valid at `35fe8bb` only, not said | stated in "Code identity" |
| F13 — format | review-round material and working-directory sources inside the ADR; a title that stated option 5 | the corrections moved to this annex; the title neutral; the review record's committed location stated (Status, Sources and reproduction) |
| F14 — ADR 0010 | its shutdown exclusion and `dropped` amended silently | one bullet under "Contracts and records" |
| F18 — a script path | an absolute path in `adr0011_code_anchors.sh` | the worktree located relative to the script |
| `verify_constraints.md` section 5.2 — what stops a decision | open items listed as follow-ups; effect on G3 stated for tests 5 and 6 only; no C12 statement across options; no time cost | items 1, 2, 5 and 6 of "Open before the decision" marked as gates; the other families and test 8 stated as not assessed; the C12 zero-lost gate expected to fail under every option at 11.2 msg/s (Relationship, option 4); test 6's `delta` rule against N1 (option 5); the calendar cost stated as not established (item 8) |
