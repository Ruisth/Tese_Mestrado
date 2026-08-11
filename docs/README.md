# docs/ — index

EGW project documentation. The normative source for scope, schedule and gates is
`PLANO_DESENVOLVIMENTO_INTEGRADO_EDGE_GATEWAY_2026.md` (held in the workspace
OUTSIDE this repository, so it is deliberately not a link; it becomes
`docs/governance/INTEGRATED_DEVELOPMENT_PLAN_2026.md` through the language
migration). Internal technical contracts: [`../src/CONTRACTS.md`](../src/CONTRACTS.md).
The single source of state for every deliverable is
[`../PROGRESS.md`](../PROGRESS.md) — nothing in this folder declares a gate
accepted.

## G0 — scope and start-up

| File | Content |
|---|---|
| [`g0/scope_and_rqs.md`](g0/scope_and_rqs.md) | Objective, RQ1–RQ3, P0/P1 scope, out of scope and closed premises (proposed — awaiting supervisor validation) |
| [`g0/supervisor_email_g0.md`](g0/supervisor_email_g0.md) | Draft of the scope email to the supervisors (gate G0), carrying the plan §8.1 escalation of the missing ARM64 measurement VM. **Drafted, not sent** — sending is a student action and is what discharges §8.1. Kept in Portuguese under the language policy's exception for external administrative communication |
| [`g0/backlog.md`](g0/backlog.md) | Actionable backlog by gate (G0→G7): actions, expected evidence, dependencies and cutting rules — no state |
| [`g0/risks.md`](g0/risks.md) | Risk register with early signals and mitigation: R1–R8 (plan §11), R9–R15 (operational), R16–R27 (external audit), RA1–RA15 (external re-analysis, followed line by line), R28–R31 (real execution) and R32–R33 (technical audit, renumbered on 2026-08-12 to resolve an identifier collision) |

## Governance

| File | Content |
|---|---|
| [`governance/language-policy.md`](governance/language-policy.md) | British English as the working language, planned renames and migration order |

## claim→evidence integrity

| File | Content |
|---|---|
| [`claim_evidence_matrix.csv`](claim_evidence_matrix.csv) | claim→evidence matrix (data source, plan §6.3) |
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
| [`adr/README.md`](adr/README.md) | Index and conventions of the ADRs (0001–0006 accepted on 2026-08-07; 0007 proposed on 2026-08-12) |
| [`adr/0007-three-tier-platform-model.md`](adr/0007-three-tier-platform-model.md) | Three platform tiers: QEMU is functional-only, a burstable ARM64 instance may serve functional integration but never produce numbers, and only a dedicated ARM64 instance may produce numbers for RQ3. Extends ADR 0001. **Proposed** — awaiting supervisor validation |
