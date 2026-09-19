# Supervisor alignment memo — integrated Yocto ARM64 gateway (draft for the plan v2.0 proposal)

**Revised:** 2026-09-16; amended 2026-09-18; amended again 2026-09-18 (moved
under `docs/governance/proposals/`; dates and facts); revised again 2026-09-18
after the student adopted plan v2.0 with the QEMU-only execution amendment;
two sentences corrected in place 2026-09-19.
**Dated banner, 2026-09-19 — what this memo must still carry, and what it must
not.** The memo stays a **draft and is not sent**, and its body below is not
rewritten except at the two places this banner records as corrected in place on
2026-09-19: the QEMU sentence in the paragraph below and the statement of fact
in item 6. Both were written in this change, not carried over from the memo of
2026-09-16, so neither is preserved draft wording. What it still has to request is only the rows that remain open: the
experimental thresholds (D007), the scope of the evaluation and any academic use
of emulated results (D014), the authenticity of the local `Template_LaTeX` copy
with its cover and metadata (the open half of D004), and the operational
storage semantics (the open half of D010). What it must **not** re-request is
what the student reports confirmed: the title, the research questions with RQ3
in QEMU, the local-core scope, the scoping-review method, the experimental
quantity to attempt, the second-operator waiver, the review schedule, the
template obligation, the AI-use declaration, the optional article, the
terminology policy and the local evidence copy. All of that is **reported by the
student**, undated, and is not a documented supervisor decision. Item 3 below is
also overtaken: the 95-run campaign and the 24-hour soak are now a target to
attempt under QEMU, subject to the pilot's feasibility check. One statement of
fact in item 6 was written in this change, was wrong, and is corrected there
rather than preserved: the draft said "None of the nine integration/recovery test
families has been run" — later on
2026-09-18 the nine were exercised once, seven passed, and tests 1 and 6 carry a
failing harness part from the resource sampler under emulation. That record is
held outside the repository and unsealed, so the battery is **not complete** and
nothing has been measured; item 6 below now states both halves.

**Draft, not sent.** This memo does not record supervisor approval. On
2026-09-18 the student adopted [plan v2.0](../INTEGRATED_DEVELOPMENT_PLAN_2026.md)
with a dated QEMU-only execution amendment, and that adopted text at the
canonical path is the plan in force. The student's adoption settles execution
only: the title, the research-question wording, the thresholds and the scope of
the evaluation are not agreed with the supervisors. The student reports supervisor approval to
proceed with the QEMU tests, recorded at D008 and D014 of the decision log:
reported by the student, undated, with no message and no supervisor name, and
not a documented supervisor decision. *(Written in this change and corrected
here on 2026-09-19; the earlier draft of this paragraph called it
student-reported advice rather than approval. It is not preserved memo
wording.)* The August memo stays unmodified at
[`docs/governance/supervisor_alignment_memo.md`](../supervisor_alignment_memo.md).

The original Theme 1 objective is to develop/test a custom Yocto distribution
supporting wearable digital twins on ARM. Under the adopted plan the evaluation
boots the Yocto-produced kernel and root filesystem **under QEMU/TCG on the
existing x86-64 workstation** and runs Mosquitto, the controller, Ditto and
MongoDB inside that guest. Native ARM64 deployment is documented, unverified
future work; it is not a condition for completing the implementation or the
functional tests. The operating-system and service layers remain a logical
decomposition and are evaluated together.

The earlier separately evaluated two-layer proposal is retained as history and
was not recorded as approved. Its absence of integrated evidence must not be
confused with removal of integration from the original objective.

Please discuss the
[proposed objective and RQ1-RQ3](scope_and_rqs_v2.0_proposal.md) and the
[plan v2.0 proposal](INTEGRATED_DEVELOPMENT_PLAN_2026_v2.0_proposal.md), in
particular:

1. Integrated Yocto/ARM64 evaluation as the thesis artefact, with the retained
   local-core boundary and no physical-board performance claim.
2. For information only, and **not a request**: native ARM64 deployment is
   outside the scope of this dissertation and is documented as unverified
   future work. No platform access, allocation or spending is asked of you, and
   the evaluation does not wait on one.
3. Experimental thresholds, independent runs, faults and load levels, to be
   frozen after a valid bounded pilot on the integrated emulated system (D007).
   The 95-run campaign and the 24-hour soak of the earlier plan are not carried
   over to the emulated environment; the functional campaign is selected and
   documented after the pilot and before the freeze. *(Superseded on 2026-09-19 and not
   to be sent as written: the student reports an instruction to attempt the
   historical 95-run composition, the 24-hour soak included, under QEMU,
   subject to the bounded pilot's feasibility check. The ordering is unchanged:
   nothing is started before the pilot has reported and the protocol is frozen.)*
4. Review calendar (a request; the dates are the student's forecast of
   2026-09-18, not a commitment assumed on your behalf): Chapters 1-4 shared
   on 2026-10-01, complete draft on 2026-10-08, feedback requested between
   2026-10-09 and 2026-10-14, corrections and final checks from 2026-10-15 to
   2026-10-19, planned submission 2026-10-20 (D013).
5. Final institutional template and AI declaration/form requirements (D004),
   and any requirement for a separate article before dissertation submission.
6. Evidence classes and the scope of the evaluation (adopted plan, section 3.5).
   No native ARM64 virtual machine could be obtained, so the evaluation is
   carried out on the Yocto ARM64 guest emulated under QEMU/TCG on the x86-64
   workstation. As of 2026-09-18 the image has been built and booted twice under
   emulation and an isolated MongoDB 7.0.39 test has passed on that guest; those
   records are sealed as technical evidence on `dev` (sealing is not
   acceptance). The same day the six-container stack was deployed inside that
   guest and the first bounded end-to-end functional test ran and passed: one
   smartwatch at 1 Hz for 60 s; 60 sent, 60 delivered unique, 0 lost, 0 late, 0
   duplicate, 0 failed, 0 rejected; the twin readable through the API with
   `last_seq` 59; reconciliation by identity exited 0. **That evidence is
   candidate evidence held outside the repository and is unsealed**, so it
   admits no claim and closes no gate. Two defects were found by the run and
   fixed. A memory-cgroup OOM killed the twin service's JVM during the power-off
   of that session; the corrective work is open, and no stability is claimed.
   **The nine integration/recovery test families were exercised once on
   2026-09-18: seven passed, and tests 1 and 6 carry a failing harness part from
   the resource sampler under emulation. That record is held outside the
   repository and unsealed, so the battery is not complete and nothing has been
   measured.** *(Written in this change and corrected here on 2026-09-19; the
   earlier draft sentence said none of the nine families had been run. It is not
   preserved memo wording.)* Emulated runs give functional and integration
   evidence only and support no ARM64 hardware performance conclusion; the
   maximum latency observed in the flow above is an emulated observation and not
   a performance result. **The request to you (D014, reworded as a standing
   request rather than a contingency):** agreement that the evaluation is
   carried out on the integrated emulated system, that RQ3 is bounded to that
   environment, and on any academic use of emulated results. A reply is
   requested by 2026-10-01 so that the evaluation chapter is written against an
   agreed scope. These are requests, not commitments assumed on your behalf.

Dates, as the student understands them after discussing them with you and as
confirmed by the student on 2026-09-18: planned submission 2026-10-20 and final
delivery deadline 2026-10-31, the days from 2026-10-21 to 2026-10-31 being kept
for essential corrections and submission recovery only. Please correct this if
it is not your understanding; this memo certifies no administrative record.
Remaining work was estimated on 2026-09-16 at 225-345 active hours with
8 hours/day available; that estimate is **superseded pending re-estimation**
after the current integration battery. The 2026-10-20 submission is conditional
on the integration battery, a valid pilot, your agreement on the evaluation
scope (D014) and prompt review. Every date after 2026-09-18 is a planning
target.

Existing G1 evidence remains valid for functional build/boot only. The
integrated evidence produced so far is emulated, functional, and in the case of
the deployment and the first flow held outside the repository and unsealed. **No
performance result is claimed**, and no gate or claim is accepted. Record actual
replies against D011-D014 and the surviving D004/D006/D007 items in the
[decision log](../supervisor_decision_log.csv); sending this memo is a student action.
