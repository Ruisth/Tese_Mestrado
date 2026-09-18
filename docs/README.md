# docs/ — index

EGW project documentation. The normative source for scope, schedule and gates is
[`governance/INTEGRATED_DEVELOPMENT_PLAN_2026.md`](governance/INTEGRATED_DEVELOPMENT_PLAN_2026.md)
(**version 2.0**, adopted by the student on 2026-09-18 with the QEMU-only
execution amendment). Internal technical contracts:
[`../src/CONTRACTS.md`](../src/CONTRACTS.md).
The single source of operational state for every deliverable is
[`../PROGRESS.md`](../PROGRESS.md); formal gate decisions are recorded solely
in [`governance/gate_decision_log.md`](governance/gate_decision_log.md), which
currently records **G1 as Accepted** (2026-08-14, functional platform layer
only) and every other gate as Not decided.

## Adopted revision — plan v2.0, adopted 2026-09-18 (QEMU-only execution amendment)

The adopted text is at the canonical path named above. The texts under
[`governance/proposals/`](governance/proposals/README.md) are kept as the
record of what was proposed; where they differ from the canonical text, the
canonical text governs.

- [The adopted plan](governance/INTEGRATED_DEVELOPMENT_PLAN_2026.md):
  integrated Yocto evaluation under QEMU/TCG; one execution path with planning
  targets to the planned submission of 2026-10-20 (final deadline 2026-10-31);
  two evidence classes separating emulated results from native ARM64 evidence,
  which does not exist.
- [Scope and RQs](g0/scope_and_rqs.md), version 2.0: the integrated objective
  and working RQ1–RQ3, bounded to the emulated environment and **not agreed
  with the supervisors**.
- [Alignment memo, revised draft](governance/proposals/supervisor_alignment_memo_v2.0_proposal.md):
  draft, not sent.
- [ADR 0008](adr/0008-integrated-yocto-arm64-evaluation.md): Accepted by the
  student for project execution (2026-09-18), as amended for QEMU-only
  execution — not agreed by the supervisors.

**Nothing has been sent to or approved by the supervisors**; D001–D014 are all
`proposed_not_sent`, and the student's adoption is not a supervisor decision.
The services execute inside the Yocto guest; the deployment, runbook and
dissertation adaptations are partly exercised and partly pending. Native ARM64
deployment is documented, unverified future work. Adoption closes no gate and
admits no claim.

## G0 — scope and start-up

| File | Content |
|---|---|
| [`g0/scope_and_rqs.md`](g0/scope_and_rqs.md) | **Version 2.0 (2026-09-18):** the integrated objective and RQ1–RQ3 bounded to the emulated environment, the mandatory P0, explicit exclusions and closed premises. The technical scope is adopted for execution; the title and RQ wording stay **PROPOSED - NOT SENT** pending D001/D011 |
| [`g0/supervisor_email_g0.md`](g0/supervisor_email_g0.md) | Draft of the scope email to the supervisors (gate G0). Its infrastructure escalation for a native ARM64 measurement VM is **historical**: that request was deferred with the native route on 2026-09-18. **Drafted, not sent** — sending is a student action and is required to discharge the G0 communication item. Kept in Portuguese under the language policy's exception for external administrative communication |
| [`g0/two_layer_thesis_proposal.md`](g0/two_layer_thesis_proposal.md) | Versioned proposal for a two-layer title, objective, RQs, abstract and Resumo. **PROPOSED - NOT SENT - NOT APPROVED** and **superseded by the integrated scope** adopted on 2026-09-18; it has no normative effect before D001 |
| [`g0/supervisor_decision_matrix.csv`](g0/supervisor_decision_matrix.csv) | D001-D010: decisions requested from the supervisors, recommended positions and explicit blockers; superseded as a live request by D011–D014 and retained for the record. It contains no mutable state; the authoritative status is in the governance decision log |
| [`g0/supervisor_seven_questions_matrix.md`](g0/supervisor_seven_questions_matrix.md) | Evidence-bounded response matrix for the seven supervisor questions, linked to diagrams and traceability artefacts |
| [`g0/backlog.md`](g0/backlog.md) | Actionable backlog by gate (G0→G7): actions, expected evidence, dependencies and cutting rules — no state |
| [`g0/risks.md`](g0/risks.md) | Historical and current risk register with early signals and mitigation: R1–R33 and RA1–RA15, plus the residual risks of the adopted baseline. Risk identifiers inherited from earlier plan versions are retained for traceability and do not create scope beyond the adopted plan |

## Governance

| File | Content |
|---|---|
| [`governance/language-policy.md`](governance/language-policy.md) | British English as the working language, planned renames and migration order |
| [`governance/INTEGRATED_DEVELOPMENT_PLAN_2026.md`](governance/INTEGRATED_DEVELOPMENT_PLAN_2026.md) | Normative plan **v2.0**, adopted 2026-09-18 with the QEMU-only execution amendment: integrated Yocto scope under QEMU/TCG, evidence classes, the single QEMU execution path, cuts and acceptance contract. Version 1.2 is preserved unmodified in [`governance/archive/`](governance/archive/) |
| [`governance/proposals/`](governance/proposals/README.md) | The [plan v2.0 proposal text](governance/proposals/INTEGRATED_DEVELOPMENT_PLAN_2026_v2.0_proposal.md) — **adopted on 2026-09-18 and kept here as the record of what was proposed**, superseded by the canonical text — together with the [scope and RQs v2.0 proposal](governance/proposals/scope_and_rqs_v2.0_proposal.md) and the draft [alignment memo](governance/proposals/supervisor_alignment_memo_v2.0_proposal.md), which remain a proposal and a draft |
| [`governance/supervisor_decision_log.csv`](governance/supervisor_decision_log.csv) | Preserved D001-D010 history and new D011-D014 integrated-plan requests, all `proposed_not_sent`; a draft or silence is never approval |
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
| [`setup/qemu_integrated_gateway.md`](setup/qemu_integrated_gateway.md) | Runbook for the integrated QEMU/TCG gateway profile (Yocto ARM64 guest emulated on the x86-64 host, six containers inside the guest). Sections 1 to 3.4 (build and boot) were executed once on 2026-09-18 with every acceptance check passing; that record is sealed in [`evidence/integrated-qemu/`](evidence/integrated-qemu/README.md) (sealing is not acceptance). Section 3.5 was exercised the same day in an isolated form (MongoDB 7.0.39 start test) and its record is sealed alongside them, in [`evidence/integrated-qemu/2026-09-18-mongodb7-isolated/`](evidence/integrated-qemu/README.md). Sections 4 to 6 were exercised the same day for the first bounded end-to-end flow; **that record is candidate evidence held outside the repository and unsealed**. Sections 7 to 9 have not been run, so none of the nine integration/recovery test families has been run. Rationale and package audit: [`reviews/2026-09-17-egw-image-audit.md`](reviews/2026-09-17-egw-image-audit.md) |
| [`setup/git_backup_remote.md`](setup/git_backup_remote.md) | Git backup and the private remote (risks R25/RA13) |

## Architecture decisions

| File | Content |
|---|---|
| [`adr/README.md`](adr/README.md) | Index and conventions of the ADRs, including current status and supersession links; ADR 0002 is historical and superseded by plan v1.1 |
| [`adr/0007-three-tier-platform-model.md`](adr/0007-three-tier-platform-model.md) | Three platform tiers: QEMU is functional-only, a burstable ARM64 instance may serve functional integration but never produce numbers, and only a non-burstable native ARM64 instance may produce numbers for RQ3. Extends ADR 0001. **Proposed; superseded for the adopted execution baseline by ADR 0008 (2026-09-18)** and retained as the rule set for any future native work. It was never validated by the supervisors |
