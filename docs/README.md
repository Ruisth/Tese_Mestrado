# docs/ — index

EGW project documentation. The normative source for scope, schedule and gates is
[`governance/INTEGRATED_DEVELOPMENT_PLAN_2026.md`](governance/INTEGRATED_DEVELOPMENT_PLAN_2026.md)
(**version 2.1**, requirements and delivery amendment of 2026-09-21,
retaining the QEMU-only execution baseline adopted on 2026-09-18). Internal technical contracts:
[`../src/CONTRACTS.md`](../src/CONTRACTS.md).
The single source of operational state for every deliverable is
[`../PROGRESS.md`](../PROGRESS.md); formal gate decisions are recorded solely
in [`governance/gate_decision_log.md`](governance/gate_decision_log.md), which
currently records **G1 as Accepted** (2026-08-14, functional platform layer
only), **G0 as Accepted** (2026-09-19, project initiation and baseline
alignment only; [decision record](governance/decisions/2026-09-19-g0-closure.md))
and every other gate as Not decided *(G0 added on 2026-09-19)*.

## Requirements and platform selection added on 2026-09-21

- [Gateway requirements and initial platform matrix](academic/gateway_requirements_and_platform_selection.md):
  18 requirements, source/criterion/test links, Pi 5 versus i.MX95 screening,
  Pi 4 exclusion and a conditional initial reference target.
- [Plan v2.1](governance/INTEGRATED_DEVELOPMENT_PLAN_2026.md), section 4.1.1:
  SUP-01–SUP-07 with owners, dates, dependencies and acceptance criteria.
- [Preserved v2.0](governance/archive/INTEGRATED_DEVELOPMENT_PLAN_2026_v2.0_2026-09-19.md):
  exact source revision before this additive amendment.

## Execution baseline retained from version 2.0

The current version 2.1 at the canonical path retains the execution decisions
below. The original adopted text is preserved in
[the version 2.0 archive](governance/archive/INTEGRATED_DEVELOPMENT_PLAN_2026_v2.0_2026-09-19.md).
The texts under
[`governance/proposals/`](governance/proposals/README.md) are kept as the
record of what was proposed; where they differ from the canonical text, the
canonical text governs.

- [The adopted plan](governance/INTEGRATED_DEVELOPMENT_PLAN_2026.md):
  integrated Yocto evaluation under QEMU/TCG; one execution path with planning
  targets to the planned submission of 2026-10-20 (final deadline 2026-10-31);
  two evidence classes separating emulated results from native ARM64 evidence,
  which does not exist.
- [Scope and RQs](g0/scope_and_rqs.md), version 2.0: the integrated objective
  and RQ1–RQ3, bounded to the emulated environment. The title and the research
  questions are **reported approved** by the student, with RQ3 evaluated in
  QEMU; the approved verbatim wording lives in the student manuscript, so what
  the repository publishes is a scope summary.
- [Alignment memo, revised draft](governance/proposals/supervisor_alignment_memo_v2.0_proposal.md):
  draft, not sent.
- [ADR 0008](adr/0008-integrated-yocto-arm64-evaluation.md): Accepted by the
  student for project execution (2026-09-18), as amended for QEMU-only
  execution and again on 2026-09-19 — academic framing reported approved by the
  student; the QEMU evaluation scope of RQ3 is reported approved, and only the
  open part of D014 — the wording of the native-evidence limitation and of
  claims about emulated timing and resource figures — remains to be agreed
  *(corrected 2026-09-19; previously listed the academic use of emulated
  results (D014) as not agreed)*.

**The supervisor position has two halves.** The alignment package covering what
remains open — the thresholds (D007); the open part of D014, which is only the
wording of the native-evidence limitation and of claims about emulated timing
and resource figures (the QEMU evaluation scope of RQ3 is reported approved —
reported by the student, undated, not a documented supervisor decision — and is
not re-requested, and the numerical criteria belong to D007); the authenticity
of the local template copy inside D004; and the storage semantics inside D010 —
**has not been sent** *(corrected 2026-09-19; previously listed the academic
use of emulated results (D014) as open)*, and D001, D007, D008 and D012 are
`proposed_not_sent`. Against that, the student **reports** that the
state-of-the-art material was sent, that a supervisor approved proceeding with
the QEMU tests, and that twelve further items were confirmed — the title, the
research questions with RQ3 in QEMU, the local-core scope, a scoping review as
the review method, an attempt at the historical 95-run quantity, no second
operator, the review schedule, the mandatory institutional template, a mandatory
AI-use declaration, an optional article, the authorised wearable-data
terminology and a local evidence copy. Every one of those is **reported by the
student**, none is a documented supervisor decision and none carries a date; the
student's adoption is not a supervisor decision either.
The services execute inside the Yocto guest; the deployment, runbook and
dissertation adaptations are partly exercised and partly pending. Native ARM64
deployment is documented, unverified future work. Adoption closes no gate and
admits no claim.

## G0 — scope and start-up

| File | Content |
|---|---|
| [`g0/scope_and_rqs.md`](g0/scope_and_rqs.md) | **Version 2.0 (2026-09-18):** the integrated objective and RQ1–RQ3 bounded to the emulated environment, the mandatory P0, explicit exclusions and closed premises. The technical scope is adopted for execution; the title and the research-question wording are **reported approved by the student** under D011 — reported, not a documented supervisor decision — with the approved verbatim wording held in the student manuscript rather than here |
| [`g0/supervisor_email_g0.md`](g0/supervisor_email_g0.md) | Draft of the scope email to the supervisors (gate G0). Its infrastructure escalation for a native ARM64 measurement VM is **historical**: that request was deferred with the native route on 2026-09-18. **Drafted, not sent** — sending is a student action. *Corrected 2026-09-19: it no longer discharges a G0 item, because G0 was accepted on that date under a revised exit scope that does not require proof that this draft was sent; the draft is not marked as sent.* Kept in Portuguese under the language policy's exception for external administrative communication |
| [`g0/two_layer_thesis_proposal.md`](g0/two_layer_thesis_proposal.md) | Versioned proposal for a two-layer title, objective, RQs, abstract and Resumo. **PROPOSED - NOT SENT - NOT APPROVED** and **superseded by the integrated scope** adopted on 2026-09-18; it has no normative effect, and the title and RQs the student reports approved are the integrated ones of D011, not this two-layer framing |
| [`g0/supervisor_decision_matrix.csv`](g0/supervisor_decision_matrix.csv) | D001-D010: decisions requested from the supervisors, recommended positions and explicit blockers; superseded as a live request by D011–D014 and retained for the record. It contains no mutable state; the authoritative status is in the governance decision log |
| [`g0/supervisor_seven_questions_matrix.md`](g0/supervisor_seven_questions_matrix.md) | Evidence-bounded response matrix for the seven supervisor questions, linked to diagrams and traceability artefacts |
| [`g0/backlog.md`](g0/backlog.md) | Actionable backlog by gate (G0→G7): actions, expected evidence, dependencies and cutting rules — no state |
| [`g0/risks.md`](g0/risks.md) | Historical and current risk register with early signals and mitigation: R1–R33 and RA1–RA15, plus the residual risks of the adopted baseline and, since 2026-09-19, the findings of the integration battery and the diagnostic attempts (the controller-restart queue finding and the delivery backlog under emulation), registered against existing identifiers. Risk identifiers inherited from earlier plan versions are retained for traceability and do not create scope beyond the adopted plan |

## Governance

| File | Content |
|---|---|
| [`governance/INTEGRATED_DEVELOPMENT_PLAN_2026.md`](governance/INTEGRATED_DEVELOPMENT_PLAN_2026.md) | Normative plan **v2.0**, adopted 2026-09-18 with the QEMU-only execution amendment: integrated Yocto scope under QEMU/TCG, evidence classes, the single QEMU execution path, cuts and acceptance contract. Version 1.2 is preserved unmodified in [`governance/archive/`](governance/archive/) |
| [`governance/decisions/2026-09-19-g0-closure.md`](governance/decisions/2026-09-19-g0-closure.md) | Durable copy of the G0 decision: **Accepted on 2026-09-19** by the student, with the project manager's concurrence, for project initiation and baseline alignment, quoting the dated project-management register entry it comes from. It is a dated change of G0's exit scope, not a retroactive pass against the legacy criteria, and it carries the residual-obligation table (G2/G3, G4, G4/G6, Chapters 1–4 and G6, G7, and the off-machine copy as an active resilience action owned by the student). It closes no other gate and admits no claim |
| [`governance/proposals/acceptance_protocol_update_2026-09-19.md`](governance/proposals/acceptance_protocol_update_2026-09-19.md) | **PROPOSED — for review, not adopted.** Acceptance and protocol proposals after the integration battery of 2026-09-18 and the invalid timed attempts of 2026-09-19: short-run selection, a lifecycle-aware rule for a deliberate restart, late delivery as its own issue (the delivery backlog under QEMU/TCG and the controller-restart queue finding), the test 4 sequence-reset coverage (with the Ditto repeat of test 7, also not run), binding each run to its exact instrument and the acceptance sequence after resumption; each item names who decides it. It resumes no test and admits no evidence |
| [`governance/proposals/`](governance/proposals/README.md) | The [plan v2.0 proposal text](governance/proposals/INTEGRATED_DEVELOPMENT_PLAN_2026_v2.0_proposal.md) — **adopted on 2026-09-18 and kept here as the record of what was proposed**, superseded by the canonical text — together with the [scope and RQs v2.0 proposal](governance/proposals/scope_and_rqs_v2.0_proposal.md) and the draft [alignment memo](governance/proposals/supervisor_alignment_memo_v2.0_proposal.md), which remain a proposal and a draft |
| [`governance/supervisor_decision_log.csv`](governance/supervisor_decision_log.csv) | Preserved D001-D010 history and new D011-D014 integrated-plan requests, with **mixed statuses** since 2026-09-19. The `status` column takes exactly three values: `proposed_not_sent` (D001, D007, D008, D012), `confirmed_reported_by_student` (D002, D009) and `partly_confirmed_reported_by_student` (the rest, each row naming its confirmed and its unresolved part). The two `…_reported_by_student` values record **what the student reports a supervisor confirmed** and are never a documented supervisor decision; `sent_at` and `response_at` are empty in every row, because no date was reported. A note inside a row dated 2026-09-18 names the project-management record the confirmations were recorded in; the rows themselves were written on 2026-09-19, and the confirmations are undated (the convention is stated in [`governance/gate_decision_log.md`](governance/gate_decision_log.md)). A draft or silence is never approval for the rows that stay open |
| [`governance/language-policy.md`](governance/language-policy.md) | British English, ISO 8601 dates and — since 2026-09-19 — the **authorised wearable-data terminology** for active prose, with the literal `/telemetry` topic, interface identifiers, reference titles, quotations and sealed evidence preserved. It is the single place that policy is written down |
| [`governance/external_source_register.md`](governance/external_source_register.md) | Checksummed identities and redistribution controls for sources held outside the repository |
| [`governance/provenance-history-rewrite.md`](governance/provenance-history-rewrite.md) | Evidence tag, verified bundles and exact-tree mappings across the history rewrite |

## Academic alignment package

| File | Content |
|---|---|
| [`academic/c2dta_p0_traceability.md`](academic/c2dta_p0_traceability.md) | Paper EGW function -> P0 implementation -> stub/interface -> future integration matrix, software inventory and rules preventing causal performance comparisons between the paper and this dissertation |
| [`../diagrams/c2dta_five_layer_reference.puml`](../diagrams/c2dta_five_layer_reference.puml) ([SVG](../diagrams/c2dta_five_layer_reference.svg)) | Editable five-layer C2DTA reference architecture with P0/deferred status. Its "live ARM64 evidence pending" labels predate 2026-09-18 and are corrected in [`../diagrams/README.md`](../diagrams/README.md) pending a rendering pass |
| [`../diagrams/two_layer_experimental_deployment.puml`](../diagrams/two_layer_experimental_deployment.puml) ([SVG](../diagrams/two_layer_experimental_deployment.svg)) | Editable two-layer experimental deployment proposal — **historical**, superseded by the integrated emulated deployment in [`../diagrams/architecture.md`](../diagrams/architecture.md) |

## claim→evidence integrity

| File | Content |
|---|---|
| [`claim_evidence_matrix.csv`](claim_evidence_matrix.csv) | claim→evidence matrix supporting the plan §7 acceptance contract |
| [`claim_evidence_matrix.md`](claim_evidence_matrix.md) | Readable view of the matrix and its maintenance rules |
| [`evidence/tests/`](evidence/tests/) | Sealed records of suite runs (JUnit + stdout + environment + `SHA256SUMS`). **M2** evidence: unit tests, with fakes, on Windows — it closes no gate and validates no claim. Only the newest directory is current; the earlier ones are historical, each tied to the commit it tested |
| [`evidence/integrated-qemu/`](evidence/integrated-qemu/README.md) | Sealed technical evidence of 2026-09-18 for the integrated QEMU/TCG gateway profile of pull request #28: build (one failed attempt preserved) and two boots of `egw-gateway-image` with every acceptance check passing, and an isolated MongoDB 7.0.39 test on that guest. **Functional only, ARM64 emulated on x86-64.** The capsule covers build, boot and that isolated MongoDB test: it contains no stack deployment, no end-to-end flow and no measurement. The first-flow record of 2026-09-18 is candidate evidence held **outside the repository** and is not in this capsule. Sealing is not acceptance: no gate is accepted and no claim is supported |
| [`evidence/g1-yocto-qemu/`](evidence/g1-yocto-qemu/) | Sealed G1 evidence: the 2026-08-11 bring-up seal (`egw-image` build, two preliminary boots) and the 2026-08-14 strict capsule (`2026-08-14-clean-build-f0e19d5/`: clean identified checkout build, five strict boots with seven required assertions each, failed first attempt preserved). **Functional only** — it supports no performance or security statement; the gate outcome is recorded solely in [`governance/gate_decision_log.md`](governance/gate_decision_log.md) |

## Setup guides (executed by the student)

| File | Content |
|---|---|
| [`setup/wsl2_ubuntu_yocto.md`](setup/wsl2_ubuntu_yocto.md) | WSL2 + Ubuntu 24.04 + Yocto Scarthgap + kas + QEMU, and the evidence for G1 |
| [`setup/vm_arm64_hetzner.md`](setup/vm_arm64_hetzner.md) | ARM64 measurement-VM checklist, environment manifest, Docker, hardening and teardown. **Deferred with the native route on 2026-09-18**: no host is secured, none is requested by the adopted plan, and the file is retained as a checklist for any future native work — see R28 in [`g0/risks.md`](g0/risks.md) and [`adr/0007-three-tier-platform-model.md`](adr/0007-three-tier-platform-model.md) |
| [`setup/qemu_integrated_gateway.md`](setup/qemu_integrated_gateway.md) | Runbook for the integrated QEMU/TCG gateway profile (Yocto ARM64 guest emulated on the x86-64 host, six containers inside the guest). Sections 1 to 3.4 (build and boot) were executed once on 2026-09-18 with every acceptance check passing; that record is sealed in [`evidence/integrated-qemu/`](evidence/integrated-qemu/README.md) (sealing is not acceptance). Section 3.5 was exercised the same day in an isolated form (MongoDB 7.0.39 start test) and its record is sealed alongside them, in [`evidence/integrated-qemu/2026-09-18-mongodb7-isolated/`](evidence/integrated-qemu/README.md). Sections 4 to 6 were exercised the same day for the first bounded end-to-end flow; **that record is a locally hash-sealed candidate held outside the published evidence package, not admitted**. The nine integration/recovery test families of Sections 7 to 9 were exercised once on 2026-09-18 — functional results shown for tests 2 and 8 and the tested checks of test 9, and the specific behaviours of tests 3, 4 (duplicate handling) and 7 (the MongoDB fault only); test 5 fails its deadline criterion, neither the sequence-reset sub-check of test 4 nor the Ditto repeat of test 7 was run, and the timed harness parts of tests 1 and 6 are invalid *(corrected 2026-09-19: the earlier "seven passed" overstated the record)* — and that record is a locally hash-sealed candidate archive held outside the repository, not admitted to the project evidence record, so the battery is **not complete**; whether the Section 7 to 9 steps were pasted as written is not recorded here. Rationale and package audit: [`reviews/2026-09-17-egw-image-audit.md`](reviews/2026-09-17-egw-image-audit.md) |
| [`setup/local_test_outputs.md`](setup/local_test_outputs.md) | The local `output_test` folder: one verified package per test attempt, failures included, exported from WSL to Windows; layout, run ids, the three separate verdicts and the export rules |
| [`setup/git_backup_remote.md`](setup/git_backup_remote.md) | Git backup and the private remote (risks R25/RA13) |

## Architecture decisions

| File | Content |
|---|---|
| [`adr/README.md`](adr/README.md) | Index and conventions of the ADRs, including current status and supersession links; ADR 0002 is historical and superseded by plan v1.1 |
| [`adr/0007-three-tier-platform-model.md`](adr/0007-three-tier-platform-model.md) | Three platform tiers: QEMU is functional-only, a burstable ARM64 instance may serve functional integration but never produce numbers, and only a non-burstable native ARM64 instance may produce numbers for RQ3. Extends ADR 0001. **Proposed; superseded for the adopted execution baseline by ADR 0008 (2026-09-18)** and retained as the rule set for any future native work. It was never validated by the supervisors |
