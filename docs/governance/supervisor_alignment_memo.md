# Supervisor alignment memo — integrated Yocto ARM64 gateway

**Revised:** 2026-09-16; amended 2026-09-18. **Draft, not sent.** The student has
authorised the technical correction for planning only; this memo does not record
supervisor approval. Plan v2.0 is a proposal published for review and
[plan v1.2](archive/INTEGRATED_DEVELOPMENT_PLAN_2026_v1.2_en.md) remains the plan
in force until the student decides after consulting the supervisors. The August
memo that accompanies plan v1.2 is the previous revision of this file (commit
`e0c67c3`).

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

Please discuss the [proposed objective and RQ1-RQ3](../g0/scope_and_rqs.md) and
[plan v2.0](INTEGRATED_DEVELOPMENT_PLAN_2026.md), in particular:

1. Integrated Yocto/ARM64 evaluation as the thesis artefact, with the retained
   local-core boundary and no physical-board performance claim.
2. Access to an ARM64 platform that can boot our own OS image: a custom AWS
   Graviton AMI is the documented candidate; an institutional ARM64/KVM host
   is an alternative if available. An Ubuntu-only VM is insufficient for the
   final campaign. Account permissions, availability and costs are unconfirmed.
3. Experimental thresholds, independent runs, faults, load levels and the
   24-hour soak, to be frozen after a valid integrated pilot (D007).
4. Review calendar: Chapters 1-4 shared early, complete draft by 11 October,
   feedback requested by 14-15 October, completion target 20 October.
5. Final institutional template and AI declaration/form requirements (D004),
   and any requirement for a separate article before dissertation submission.
6. Evidence classes (plan v2.0, section 10): no native ARM64 virtual machine
   could be obtained on 2026-09-17, so integration will first be attempted on
   the Yocto ARM64 guest emulated under QEMU/TCG on the x86-64 workstation. As
   of 2026-09-18 the image has been built and booted under emulation; the
   six-container stack has not been deployed, nothing has been measured, the
   evidence is candidate evidence and no gate or claim is accepted. Such
   runs give functional and integration evidence only and no ARM64 hardware
   performance conclusion. If no native ARM64 host is obtained in time,
   re-scoping RQ3 or the evaluation to emulated functional evidence needs
   supervisor agreement (D014), as does any academic use of emulated results.

The student reports an extension deadline of 3 November. It is a contingency;
this memo does not certify an extension application or institutional approval.
Remaining work is estimated at 225-345 active hours with 8 hours/day available.
20 October is conditional on native boot/integration and prompt review.

Existing G1 evidence remains valid for functional build/boot only. No
integrated experiment, native or emulated, and no performance result is
claimed. Record actual replies
against D011-D014 and the surviving D004/D006/D007 items in the
[decision log](supervisor_decision_log.csv); sending this memo is a student action.
