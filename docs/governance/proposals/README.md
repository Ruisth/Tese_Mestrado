# docs/governance/proposals/ — proposals, not in force

This directory holds governance texts that are **proposals**. Nothing in it is
in force, nothing in it has been sent to or approved by the supervisors, and
merging a pull request that adds or changes a file here adopts nothing.

## What is in force

| Subject | File in force (canonical path) |
|---|---|
| Integrated plan | [`../INTEGRATED_DEVELOPMENT_PLAN_2026.md`](../INTEGRATED_DEVELOPMENT_PLAN_2026.md), **version 1.2** (2026-08-14) |
| Scope and research questions | [`../../g0/scope_and_rqs.md`](../../g0/scope_and_rqs.md), version 1.1 (2026-08-13), on which plan v1.2 relies |
| Supervisor alignment memo | [`../supervisor_alignment_memo.md`](../supervisor_alignment_memo.md), the August memo that accompanies plan v1.2 |

"In force" means the text on which plan v1.2 relies. The August scope and the
August memo are themselves **PROPOSED - NOT SENT** (decision D001), and nothing
in them is approved by the supervisors.

These three files are unmodified. Gate outcomes are recorded only in the
[gate decision log](../gate_decision_log.md) and supervisor replies only in the
[supervisor decision log](../supervisor_decision_log.csv), in which decisions
D001–D014 are all `proposed_not_sent`.

## What is proposed here

| File | Content | State |
|---|---|---|
| [`INTEGRATED_DEVELOPMENT_PLAN_2026_v2.0_proposal.md`](INTEGRATED_DEVELOPMENT_PLAN_2026_v2.0_proposal.md) | Plan v2.0: integrated Yocto ARM64 evaluation, evidence classes (emulated QEMU/TCG versus native ARM64), forecast schedule for the planned submission of 2026-10-20 (final delivery deadline 2026-10-31) and effort forecast | Proposal, not in force |
| [`scope_and_rqs_v2.0_proposal.md`](scope_and_rqs_v2.0_proposal.md) | Scope v2.0: integrated objective, proposed title and working RQ1–RQ3 | Proposal, not in force |
| [`supervisor_alignment_memo_v2.0_proposal.md`](supervisor_alignment_memo_v2.0_proposal.md) | Revised alignment memo for the supervisors | Draft, not sent |

[ADR 0008](../../adr/0008-integrated-yocto-arm64-evaluation.md) belongs to the
same proposal. It stays in `docs/adr/` with the status Proposed, because the ADR
convention already carries proposals.

The two dates quoted in the proposal (planned submission 2026-10-20, final
delivery deadline 2026-10-31, with 2026-10-21 to 2026-10-31 as a contingency
window for essential corrections only) rest on the student's confirmation of
2026-09-18 after discussing the dates with the supervisors. That is a
first-party statement, not an administrative document. Every milestone date in
the proposal is a forecast.

A citation of "plan v2.0" with a section number and no path, anywhere in the
repository, means the plan proposal in this directory. Four files that were on
`dev` before 2026-09-18 (`docs/setup/qemu_integrated_gateway.md`,
`docs/reviews/2026-09-17-egw-image-audit.md`,
`src/yocto/kas/egw-qemuarm64-integrated.yml` and the `egw-gateway-image`
recipe) say that the revision is not yet published on `dev`. Those notes
predate this directory and are left as written: the revision is published here
as a proposal only, and plan v1.2 remains in force.

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
   supervisors (D011–D014; section 10 rule 4 of the plan proposal). Those parts
   apply only when the supervisors' replies are recorded in the decision log,
   and ADR 0008 changes status only then.
5. Until that happens, every index, banner and README in the repository points
   to the canonical path when it means the plan in force and to this directory
   when it means the proposal.

A proposal that is withdrawn or superseded stays here, marked as such, so that
the record of what was proposed is kept.
