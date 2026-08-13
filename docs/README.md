# docs/ — index

EGW project documentation. The normative source for scope, schedule and gates is
[`governance/INTEGRATED_DEVELOPMENT_PLAN_2026.md`](governance/INTEGRATED_DEVELOPMENT_PLAN_2026.md).
Internal technical contracts: [`../src/CONTRACTS.md`](../src/CONTRACTS.md).
The single source of state for every deliverable is
[`../PROGRESS.md`](../PROGRESS.md) — nothing in this folder declares a gate
accepted.

## G0 — scope and start-up

| File | Content |
|---|---|
| [`g0/scope_and_rqs.md`](g0/scope_and_rqs.md) | Proposed objective and RQ1–RQ3, mandatory two-layer P0, explicit exclusions and closed premises (awaiting supervisor validation) |
| [`g0/supervisor_email_g0.md`](g0/supervisor_email_g0.md) | Draft of the scope email to the supervisors (gate G0), including the plan §§4–5 escalation for the missing ARM64 measurement VM. **Drafted, not sent** — sending is a student action and is required to discharge the G0 communication item. Kept in Portuguese under the language policy's exception for external administrative communication |
| [`g0/two_layer_thesis_proposal.md`](g0/two_layer_thesis_proposal.md) | Versioned proposal for a two-layer title, objective, RQs, abstract and Resumo. **PROPOSED - NOT SENT - NOT APPROVED**; it has no normative effect before D001 |
| [`g0/supervisor_decision_matrix.csv`](g0/supervisor_decision_matrix.csv) | D001-D008: decisions requested from the supervisors, recommended positions and explicit blockers. It contains no mutable state; the authoritative status is in the governance decision log |
| [`g0/supervisor_seven_questions_matrix.md`](g0/supervisor_seven_questions_matrix.md) | Evidence-bounded response matrix for the seven supervisor questions, linked to diagrams and traceability artefacts |
| [`g0/backlog.md`](g0/backlog.md) | Actionable backlog by gate (G0→G7): actions, expected evidence, dependencies and cutting rules — no state |
| [`g0/risks.md`](g0/risks.md) | Historical and current risk register with early signals and mitigation: R1–R33 and RA1–RA15. Risk identifiers inherited from earlier plan versions are retained for traceability and do not create scope beyond plan v1.1 |

## Governance

| File | Content |
|---|---|
| [`governance/language-policy.md`](governance/language-policy.md) | British English as the working language, planned renames and migration order |
| [`governance/INTEGRATED_DEVELOPMENT_PLAN_2026.md`](governance/INTEGRATED_DEVELOPMENT_PLAN_2026.md) | Normative plan v1.1: two-layer scope, rebased gates, cuts and acceptance contract |
| [`governance/supervisor_decision_log.csv`](governance/supervisor_decision_log.csv) | D001-D008 state; a draft or silence is never approval |
| [`governance/external_source_register.md`](governance/external_source_register.md) | Checksummed identities and redistribution controls for sources held outside the repository |
| [`governance/provenance-history-rewrite.md`](governance/provenance-history-rewrite.md) | Evidence tag, verified bundles and exact-tree mappings across the history rewrite |

## Academic alignment package

| File | Content |
|---|---|
| [`academic/c2dta_p0_traceability.md`](academic/c2dta_p0_traceability.md) | Paper EGW function -> P0 implementation -> stub/interface -> future integration matrix, software inventory and rules preventing causal x86/ARM64 comparisons |
| [`../diagrams/c2dta_five_layer_reference.puml`](../diagrams/c2dta_five_layer_reference.puml) ([SVG](../diagrams/c2dta_five_layer_reference.svg)) | Editable five-layer C2DTA reference architecture with P0/deferred status |
| [`../diagrams/two_layer_experimental_deployment.puml`](../diagrams/two_layer_experimental_deployment.puml) ([SVG](../diagrams/two_layer_experimental_deployment.svg)) | Editable two-layer experimental deployment proposal |

## claim→evidence integrity

| File | Content |
|---|---|
| [`claim_evidence_matrix.csv`](claim_evidence_matrix.csv) | claim→evidence matrix supporting the plan §7 acceptance contract |
| [`claim_evidence_matrix.md`](claim_evidence_matrix.md) | Readable view of the matrix and its maintenance rules |
| [`evidence/tests/`](evidence/tests/) | Sealed records of suite runs (JUnit + stdout + environment + `SHA256SUMS`). **M2** evidence: unit tests, with fakes, on Windows — it closes no gate and validates no claim. Only the newest directory is current; the earlier ones are historical, each tied to the commit it tested |
| [`evidence/g1-yocto-qemu/`](evidence/g1-yocto-qemu/) | Sealed G1 evidence: `egw-image` build and the two QEMU bring-up boots. **Functional only** — it supports no performance or security statement, and gate acceptance is pending |

## Setup guides (executed by the student)

| File | Content |
|---|---|
| [`setup/wsl2_ubuntu_yocto.md`](setup/wsl2_ubuntu_yocto.md) | WSL2 + Ubuntu 24.04 + Yocto Scarthgap + kas + QEMU, and the evidence for G1 |
| [`setup/vm_arm64_hetzner.md`](setup/vm_arm64_hetzner.md) | ARM64 measurement-VM checklist, environment manifest, Docker, hardening and teardown. **Provider not yet secured**: the file keeps its Hetzner filename but is now provider-neutral, since Hetzner has no ARM capacity — see R28 in [`g0/risks.md`](g0/risks.md) and [`adr/0007-three-tier-platform-model.md`](adr/0007-three-tier-platform-model.md) |
| [`setup/git_backup_remote.md`](setup/git_backup_remote.md) | Git backup and the private remote (risks R25/RA13) |

## Architecture decisions

| File | Content |
|---|---|
| [`adr/README.md`](adr/README.md) | Index and conventions of the ADRs, including current status and supersession links; ADR 0002 is historical and superseded by plan v1.1 |
| [`adr/0007-three-tier-platform-model.md`](adr/0007-three-tier-platform-model.md) | Three platform tiers: QEMU is functional-only, a burstable ARM64 instance may serve functional integration but never produce numbers, and only a dedicated ARM64 instance may produce numbers for RQ3. Extends ADR 0001. **Proposed** — awaiting supervisor validation |
