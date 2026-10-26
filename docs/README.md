# docs/ — index

Documentation of EGW, the Digital Twin Edge Gateway. Start with the five guides below; each fact has
one primary page, and the others link to it. Every measured figure comes from an ARM64 guest emulated
by QEMU/TCG on an x86-64 host.

## The five guides

| Guide | Use it to | Content |
|---|---|---|
| [architecture.md](architecture.md) | Browse the code | Components, communication, ports, the path of one message, code map |
| [demo.md](demo.md) | Demonstrate the gateway | Preparation, manual commands in independent terminals, expected results |
| [results.md](results.md) | Verify the results | Results presented in the dissertation, each with its table, data and analysis code; data held locally only are declared |
| [reproduce.md](reproduce.md) | Reproduce | Environment, image build, measurement and analysis |
| [history/README.md](history/README.md) | Read the records | Decisions, old plans, proposals, reviews, past runbooks, work logs and the previous front page |

The front page is [`../README.md`](../README.md). Formal gate outcomes are recorded only in the
[gate decision log](governance/gate_decision_log.md): G0, G1, G2 and G3 accepted; G4 to G7 not decided.

## Contracts and architecture decisions

| File | Content |
|---|---|
| [`../src/CONTRACTS.md`](../src/CONTRACTS.md) | Normative interfaces, v1.2 (2026-09-24): topics, envelope, twins, ports, outcomes |
| [`adr/README.md`](adr/README.md) | Index of the ADRs 0001–0011 and their recorded statuses |
| [`../diagrams/README.md`](../diagrams/README.md) | Diagram families: Mermaid views in [`../diagrams/architecture.md`](../diagrams/architecture.md) (drawn against CONTRACTS v1.1) and the PlantUML five-layer C2DTA reference |

## Evidence

Capsules under `docs/evidence/`; none is ever edited. Most have a `README.md` and `SHA256SUMS` at
their root or in their dated subfolders. The exceptions: `compare-a02/` is a derived summary whose
inputs and digests are in its `summary.json`, with its raw package sealed locally; `tests/` has no
README and its first directory (`2026-08-08`) has no seal; the rehearsal is a single note.
`python tools/ci/verify_evidence.py` checks the seals. [results.md](results.md) maps each result to its
capsule and states which data are held outside the repository.

| Capsule | Date | Content |
|---|---|---|
| [`evidence/compare-a02/`](evidence/compare-a02/README.md) | 2026-10-18/19 | Yocto image vs Debian 13, series a02: table, per-execution summary and plan; the raw records are local only |
| [`evidence/g3-battery-2026-10/`](evidence/g3-battery-2026-10/README.md) | 2026-10-02 to 2026-10-07 | The 38 packages of the G3 battery, sessions S1–S4 |
| [`evidence/finite-proof-r03/`](evidence/finite-proof-r03/README.md) | 2026-09-28 | Finite proof of ADR 0011, third attempt: an engineering diagnostic of one run |
| [`evidence/g2-complete-flow/`](evidence/g2-complete-flow/README.md) | 2026-09-20/21 | G2: one smartwatch flow and twin persistence across a whole-stack restart |
| [`evidence/integrated-qemu/`](evidence/integrated-qemu/README.md) | 2026-09-18 | Integrated image build and boots, and an isolated MongoDB 7.0.39 test |
| [`evidence/g1-yocto-qemu/`](evidence/g1-yocto-qemu/README.md) | 2026-08-11 and 2026-08-14 | G1: preliminary build and two boots (2026-08-11); clean-checkout build and five strict boots (2026-08-14) |
| [`evidence/tests/`](evidence/tests/) | 2026-08-08 to 2026-08-11 | Unit-test runs, one directory per commit; the newest in the repository is `2026-08-11-head-4e67717` (701 passed) |
| [`evidence/word-import-2026-09-17/`](evidence/word-import-2026-09-17/README.md) | 2026-09-17 | Verification of the LaTeX import of the Word manuscript |
| [`evidence/rehearsal/`](evidence/rehearsal/2026-08-08-dry-rehearsal.md) | 2026-08-08 | Dry rehearsal of the campaign logistics; no result |

## Setup guides

| File | Content |
|---|---|
| [`setup/wsl2_ubuntu_yocto.md`](setup/wsl2_ubuntu_yocto.md) | WSL2, Ubuntu 24.04, Yocto Scarthgap, kas and QEMU on the build host |
| [`setup/local_test_outputs.md`](setup/local_test_outputs.md) | The local `output_test` folder: one verified package per attempt, failures included |
| [`setup/git_backup_remote.md`](setup/git_backup_remote.md) | Git backup and the private remote |
| [`setup/qemu_integrated_gateway.md`](setup/qemu_integrated_gateway.md) | The manual runbook of 2026-09-18/19. Its §1–2 and §4 remain the preparation steps used by [demo.md](demo.md) and [reproduce.md](reproduce.md); §5.1–5.6 are automated by `tools/compare/provision_stack.sh`; §6.1 is the source of the measurement's helper file. Its status notes are historical |
| [`setup/vm_arm64_hetzner.md`](setup/vm_arm64_hetzner.md) | Record: native ARM64 VM checklist, deferred on 2026-09-18 and never used |

## Governance

| File | Content |
|---|---|
| [`governance/gate_decision_log.md`](governance/gate_decision_log.md) | The only formal record of gate outcomes, with superseded row states kept verbatim |
| [`governance/decisions/`](governance/decisions/) | Decision records of G0 (2026-09-19), G2 (2026-09-21) and G3 (2026-10-07) |
| [`governance/g3-battery-2026-10-results.md`](governance/g3-battery-2026-10-results.md) | G3 battery results, row by row, and the standing rows |
| [`governance/language-policy.md`](governance/language-policy.md) | British English, ISO 8601 dates and the authorised wearable-data terminology |
| [`governance/external_source_register.md`](governance/external_source_register.md) | Checksummed identities of sources held outside the repository |
| [`governance/provenance-history-rewrite.md`](governance/provenance-history-rewrite.md) | Evidence tag, verified bundles and exact-tree mappings across the history rewrite |
| [`governance/INTEGRATED_DEVELOPMENT_PLAN_2026.md`](governance/INTEGRATED_DEVELOPMENT_PLAN_2026.md) | Record: integrated plan v2.1 (2026-09-21); earlier versions in [`governance/archive/`](governance/archive/) |
| [`governance/proposals/`](governance/proposals/README.md) | Record: proposals and the texts of adopted proposals |

Supervisor-request logs, readiness maps and memos are listed in [history/README.md](history/README.md).

## Academic alignment package

| File | Content |
|---|---|
| [`academic/c2dta_p0_traceability.md`](academic/c2dta_p0_traceability.md) | C2DTA paper function to P0 implementation, stub or deferred work (v1.2, 2026-09-18) |
| [`academic/gateway_requirements_and_platform_selection.md`](academic/gateway_requirements_and_platform_selection.md) | Record: REQ-01 to REQ-18 and the Pi 5 / i.MX95 screening (v1.0, 2026-09-21), documentary |
| [`../diagrams/c2dta_five_layer_reference.puml`](../diagrams/c2dta_five_layer_reference.puml) ([SVG](../diagrams/c2dta_five_layer_reference.svg)) | Five-layer C2DTA reference with P0 and deferred status; its "live ARM64 evidence pending" labels predate 2026-09-18 |

## Claim–evidence integrity

| File | Content |
|---|---|
| [`claim_evidence_matrix.md`](claim_evidence_matrix.md) ([CSV](claim_evidence_matrix.csv)) | Claims C01–C15 of the planned campaign and their maintenance rules; the a02 comparison lies outside this matrix |

## G0 — scope and start-up (records)

| File | Content |
|---|---|
| [`g0/scope_and_rqs.md`](g0/scope_and_rqs.md) | Scope and RQ1–RQ3, version 2.0 (2026-09-18); the dissertation holds the current wording |
| [`g0/backlog.md`](g0/backlog.md) | Backlog by gate, G0 to G7 |
| [`g0/risks.md`](g0/risks.md) | Risk register R1–R33 and RA1–RA15 |
| [`g0/supervisor_email_g0.md`](g0/supervisor_email_g0.md) | Draft scope email to the supervisors, in Portuguese; not sent |
| [`g0/two_layer_thesis_proposal.md`](g0/two_layer_thesis_proposal.md) | Two-layer thesis proposal; not adopted |
| [`g0/supervisor_decision_matrix.csv`](g0/supervisor_decision_matrix.csv) | Requests D001–D010 with recommended positions |
| [`g0/supervisor_seven_questions_matrix.md`](g0/supervisor_seven_questions_matrix.md) | Response matrix for the seven supervisor questions |
