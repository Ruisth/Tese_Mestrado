# docs/governance/proposals/ — proposals and superseded proposal texts

This directory holds governance texts that are **proposals**, and the texts of
proposals that have since been adopted, kept here as the record of what was
proposed. **Nothing in this directory is the text in force.** Where a proposal
has been adopted, the adopted text lives at its canonical path and governs;
where the two differ, the canonical text wins. Merging a pull request that adds
or changes a file here adopts nothing.

**None of these texts has been sent to or approved by the supervisors.** That is
a statement about the files here, not about the supervisor relationship: since
2026-09-19 the repository records the state-of-the-art material as **reported
sent** by the student and twelve items as **reported confirmed**, none of them
dated and none of them a documented supervisor decision. Read
[section 1.1 of the adopted plan](../INTEGRATED_DEVELOPMENT_PLAN_2026.md) for
the current position; the texts below keep their own wording as history.

## What is in force

| Subject | File in force (canonical path) |
|---|---|
| Integrated plan | [`../INTEGRATED_DEVELOPMENT_PLAN_2026.md`](../INTEGRATED_DEVELOPMENT_PLAN_2026.md), **version 2.0, adopted by the student on 2026-09-18** with the QEMU-only execution amendment |
| Scope and research questions | Section 3 of the adopted plan, mirrored by [`../../g0/scope_and_rqs.md`](../../g0/scope_and_rqs.md), **version 2.0 of 2026-09-18**, amended 2026-09-19: its technical scope is adopted, and its title and research-question wording are **reported approved by the student** under D011 — reported, not documented, with the approved verbatim RQ wording held in the student manuscript. The August version 1.1 of 2026-08-13 is preserved in the repository history at `dev` revision `9179612` |
| Supervisor alignment memo | [`../supervisor_alignment_memo.md`](../supervisor_alignment_memo.md), the August memo of record, itself unsent |

"In force" means the text the project executes against. The August memo as a
whole remains **PROPOSED - NOT SENT**. The title and the research-question
wording of the scope document no longer are: since 2026-09-19 they are recorded
as **reported approved by the student** under D011, which is a report and never
a documented supervisor decision. The student's adoption of plan v2.0 settles
execution; it settled no academic wording, and neither the adoption nor a
reported confirmation closes a gate.

The previous canonical text, plan version 1.2, is preserved unmodified at
[`../archive/INTEGRATED_DEVELOPMENT_PLAN_2026_v1.2.md`](../archive/INTEGRATED_DEVELOPMENT_PLAN_2026_v1.2.md)
with SHA-256
`c346e4d958d22fad6d4f4635b4176bc2c1b584407199b165a197f94ef0e9fa53`, verified
byte for byte against `dev` revision `9179612` when it was archived on
2026-09-18.

Gate outcomes are recorded only in the
[gate decision log](../gate_decision_log.md) and supervisor replies only in the
[supervisor decision log](../supervisor_decision_log.csv), whose statuses have
been mixed since 2026-09-19: D001, D007, D008 and D012 remain
`proposed_not_sent`, while the other rows carry a `…_reported_by_student` status
that records what the student reports a supervisor confirmed and never a
documented decision. **Adopting a plan version accepts no gate and admits no
claim, and neither does a reported confirmation.**

## What is in this directory

| File | Content | State |
|---|---|---|
| [`INTEGRATED_DEVELOPMENT_PLAN_2026_v2.0_proposal.md`](INTEGRATED_DEVELOPMENT_PLAN_2026_v2.0_proposal.md) | Plan v2.0: integrated Yocto ARM64 evaluation, evidence classes (emulated QEMU/TCG versus native ARM64), branching forecast schedule and effort forecast | **Adopted 2026-09-18**, with a dated QEMU-only execution amendment; superseded by the canonical text and kept here as the record of what was proposed. Dated correction notes mark the statements that events of 2026-09-18 overtook |
| [`scope_and_rqs_v2.0_proposal.md`](scope_and_rqs_v2.0_proposal.md) | Scope v2.0: integrated objective, proposed title and working RQ1–RQ3 | The technical scope it describes is the execution baseline. Its request for the title and RQ wording is **overtaken**: since 2026-09-19 the student reports both approved, with the title *Blockchain-powered Personal AI – Digital Twin Edge Gateway* and RQ3 evaluated in QEMU. The proposal text itself is history and is not rewritten |
| [`supervisor_alignment_memo_v2.0_proposal.md`](supervisor_alignment_memo_v2.0_proposal.md) | Revised alignment memo for the supervisors | Draft, not sent |
| [`acceptance_protocol_update_2026-09-19.md`](acceptance_protocol_update_2026-09-19.md) | Acceptance and protocol update asked for by the project review of 2026-09-19: short-run selection, a lifecycle-aware rule for a deliberate controller restart with its regression cases, late delivery as its own issue (with the controller-restart queue finding), test 4 sequence-reset coverage, binding each run to its exact instrument, and the acceptance sequence after resumption | **PROPOSED — for review, not adopted** (written 2026-09-19). Nothing in it is adopted, sent or decided, and test acceptance stays paused; each item names who decides it, and its numerical values stay with D007 |

[ADR 0008](../../adr/0008-integrated-yocto-arm64-evaluation.md) belongs to the
same work. Its status is now *Accepted by the student for project execution
(2026-09-18), as amended for QEMU-only execution — not agreed by the
supervisors*, and it stays in `docs/adr/`.

The two dates quoted in the proposal (planned submission 2026-10-20, final
delivery deadline 2026-10-31, with 2026-10-21 to 2026-10-31 as a contingency
window for essential corrections only) rest on the student's confirmation of
2026-09-18 after discussing the dates with the supervisors. That is a
first-party statement, not an administrative document. Every date after
2026-09-18 is a planning target.

## Citing "plan v2.0"

From 2026-09-18, a citation of "plan v2.0" with a section number and no path,
anywhere in the repository, means the **adopted plan at the canonical path**,
[`../INTEGRATED_DEVELOPMENT_PLAN_2026.md`](../INTEGRATED_DEVELOPMENT_PLAN_2026.md).
Citations written before 2026-09-18 that point at the proposal keep their
original meaning and are not rewritten — the same rule the plan already applies
to the v1.1/v1.2 line.

Four files that were on `dev` before 2026-09-18
(`docs/setup/qemu_integrated_gateway.md`,
`src/yocto/kas/egw-qemuarm64-integrated.yml`, the `egw-gateway-image` recipe and
the `egw-gateway-config` recipe) said that the revision is not yet published on
`dev`. **The revision is published: it was adopted on 2026-09-18.** The prose
document, the runbook, is corrected in the change that publishes the adoption,
in its status and authority paragraphs. The three Yocto
build inputs keep their wording until the next functional rebuild and are never
edited on their own, because changing a recipe changes its checksum and forces a
rebuild; that deferred correction is carried in the backlog under the same
never-as-a-standalone-edit rule.

## How a proposal is adopted

1. Adoption is a **separate, explicit decision of the student**, taken after
   consulting the supervisors. A draft, a sent request, silence or the merge of
   a pull request is not adoption.
2. The decision is recorded in [`LOG.md`](../../../LOG.md) with its date and its
   basis, and the supervisors' replies are recorded in the
   [supervisor decision log](../supervisor_decision_log.csv).
3. Only then is the canonical file replaced by the adopted text, in a change
   made for that purpose, and the version it replaces is archived unmodified
   under [`../archive/`](../archive/).
4. Adopting the plan does not settle the decisions reserved for the
   supervisors (D011–D014). Those parts apply only when the supervisors' replies
   are recorded in the decision log, and ADR 0008 reaches a supervisor-agreed
   status only then.
5. Until that happens, every index, banner and README in the repository points
   to the canonical path when it means the plan in force and to this directory
   when it means the proposal text.

**Status of this procedure for plan v2.0, as at 2026-09-19.** Steps 1 to 3 are
complete: the student adopted the plan on 2026-09-18 with the QEMU-only
execution amendment, the decision and its basis are recorded in
[`LOG.md`](../../../LOG.md), the canonical file carries the adopted text, and
version 1.2 is archived unmodified with its verified checksum. **Step 4 is
narrowed but outstanding:** what is still unanswered is D007 (the thresholds and the other numerical
criteria), the open part of D014 and the unresolved halves of D004 and D010:
the QEMU evaluation scope of RQ3 is reported approved — reported by the student, undated, not a documented supervisor decision — and is not re-requested; the open part of D014 is only the wording of the native-evidence limitation and of claims about emulated timing and resource figures, and numerical criteria belong to D007 *(corrected 2026-09-19; previously listed the scope of the
evaluation and any academic use of emulated results as unanswered under D014)*. ADR 0008 has not reached a
supervisor-agreed status, and it will not reach one on a reported confirmation:
the title, the research questions and the other items the student reports
confirmed are recorded as reported, and only a documented supervisor decision
changes that status.

A proposal that is withdrawn or superseded stays here, marked as such, so that
the record of what was proposed is kept.
