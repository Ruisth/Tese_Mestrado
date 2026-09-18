# Supervisor alignment memo — integrated Yocto ARM64 gateway (draft for the plan v2.0 proposal)

**Revised:** 2026-09-16; amended 2026-09-18; amended again 2026-09-18 (moved
under `docs/governance/proposals/`; dates and facts). **Draft, not sent.** The
student has authorised the technical correction for planning only; this memo
does not record supervisor approval. Plan v2.0 is a proposal, kept with this
draft under `docs/governance/proposals/`, and
[plan v1.2](../INTEGRATED_DEVELOPMENT_PLAN_2026.md), at its canonical path,
remains the plan in force until the student decides after consulting the
supervisors. The August memo that accompanies plan v1.2 stays unmodified at
[`docs/governance/supervisor_alignment_memo.md`](../supervisor_alignment_memo.md).

The original Theme 1 objective is to develop/test a custom Yocto distribution
supporting wearable digital twins on ARM. Under the proposal, the final
evaluation would therefore boot the Yocto-produced kernel/root filesystem in a
native ARM64 VM and run Mosquitto, controller, Ditto and MongoDB inside that
guest; item 6 covers the case in which no native host is obtained in time
(D014). The operating-system and service layers remain a logical decomposition
and are evaluated together.

The earlier separately evaluated two-layer proposal is retained as history and
was not recorded as approved. Its absence of integrated evidence must not be
confused with removal of integration from the original objective.

Please discuss the
[proposed objective and RQ1-RQ3](scope_and_rqs_v2.0_proposal.md) and the
[plan v2.0 proposal](INTEGRATED_DEVELOPMENT_PLAN_2026_v2.0_proposal.md), in
particular:

1. Integrated Yocto/ARM64 evaluation as the thesis artefact, with the retained
   local-core boundary and no physical-board performance claim.
2. Access to an ARM64 platform that can boot our own OS image: a custom AWS
   Graviton AMI is the documented candidate; an institutional ARM64/KVM host
   is an alternative if available. An Ubuntu-only VM is insufficient for the
   final campaign. Account permissions, availability and costs are unconfirmed.
3. Experimental thresholds, independent runs, faults, load levels and the
   24-hour soak, to be frozen after a valid integrated pilot (D007).
4. Review calendar (a request; the dates are the student's forecast of
   2026-09-18, not a commitment assumed on your behalf): Chapters 1-4 shared
   on 2026-10-01, complete draft on 2026-10-08, feedback requested between
   2026-10-09 and 2026-10-14, corrections and final checks from 2026-10-15 to
   2026-10-19, planned submission 2026-10-20 (D013).
5. Final institutional template and AI declaration/form requirements (D004),
   and any requirement for a separate article before dissertation submission.
6. Evidence classes (plan v2.0, section 10): no native ARM64 virtual machine
   could be obtained on 2026-09-17, so integration will first be attempted on
   the Yocto ARM64 guest emulated under QEMU/TCG on the x86-64 workstation. As
   of 2026-09-18 the image has been built and booted twice under emulation and
   an isolated MongoDB 7.0.39 test has passed on that guest; the records are
   sealed as technical evidence on `dev` (sealing is not acceptance). The
   six-container stack has not been deployed; the first bounded end-to-end
   functional test (one smartwatch, 1 Hz, 60 s) is authorised and in
   preparation and has not run; nothing has been measured and no gate or claim
   is accepted. Emulated runs give functional and integration evidence only
   and no ARM64 hardware performance conclusion. If no native ARM64 host is
   obtained in time, re-scoping RQ3 or the evaluation to emulated functional
   evidence needs supervisor agreement (D014), as does any academic use of
   emulated results. In the student's forecast of 2026-09-18, "in time" means
   a host in hand by the end of 2026-09-25; without one the student would ask
   you for the D014 contingency on that date, and a reply is requested by
   2026-10-01 so that the evaluation chapter is written against an agreed
   scope. These are requests, not commitments assumed on your behalf.

Dates, as the student understands them after discussing them with you and as
confirmed by the student on 2026-09-18: planned submission 2026-10-20 and final
delivery deadline 2026-10-31, the days from 2026-10-21 to 2026-10-31 being kept
for essential corrections and submission recovery only. Please correct this if
it is not your understanding; this memo certifies no administrative record.
Remaining work was estimated on 2026-09-16 at 225-345 active hours with
8 hours/day available. The 2026-10-20 submission is conditional on
integration, on the native boot or an agreed contingency (D014), and on prompt
review.

Existing G1 evidence remains valid for functional build/boot only. No
integrated experiment, native or emulated, and no performance result is
claimed. Record actual replies against D011-D014 and the surviving
D004/D006/D007 items in the
[decision log](../supervisor_decision_log.csv); sending this memo is a student action.
