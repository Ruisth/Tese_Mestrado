# Documentation index

Start with the [main README](../README.md); the five guides below give more detail. Every measured
figure comes from an ARM64 computer emulated by QEMU on an ordinary PC.

## The five guides

| Guide | Read it to |
|---|---|
| [architecture.md](architecture.md) | See how the parts fit together and find the code |
| [demo.md](demo.md) | Prepare the PC and run the demonstration |
| [results.md](results.md) | Check each result, its data and the code that analysed it |
| [reproduce.md](reproduce.md) | Rebuild the image and repeat the measurements |
| [history/README.md](history/README.md) | Read the project's records: earlier plans, reviews and work logs |

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
| [`evidence/compare-a02/`](evidence/compare-a02/README.md) | 2026-10-18/19 | Yocto image vs Debian 13: table, one row per run and the plan; the raw records are kept locally |
| [`evidence/g3-battery-2026-10/`](evidence/g3-battery-2026-10/README.md) | 2026-10-02 to 2026-10-07 | The functional tests: 38 record folders |
| [`evidence/finite-proof-r03/`](evidence/finite-proof-r03/README.md) | 2026-09-28 | A diagnostic run of the controller's recovery after a restart |
| [`evidence/g2-complete-flow/`](evidence/g2-complete-flow/README.md) | 2026-09-20/21 | One smartwatch end to end, and its twin kept across a restart of the six containers |
| [`evidence/integrated-qemu/`](evidence/integrated-qemu/README.md) | 2026-09-18 | Integrated image build and boots, and an isolated MongoDB 7.0.39 test |
| [`evidence/g1-yocto-qemu/`](evidence/g1-yocto-qemu/README.md) | 2026-08-11 and 2026-08-14 | The base image: a preliminary build and two starts; a clean build and five checked starts |
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
| [`governance/gate_decision_log.md`](governance/gate_decision_log.md) | The formal record of the project's decisions |
| [`governance/decisions/`](governance/decisions/) | Decision records |
| [`governance/g3-battery-2026-10-results.md`](governance/g3-battery-2026-10-results.md) | The functional tests, run by run |
| [`governance/language-policy.md`](governance/language-policy.md) | British English, ISO 8601 dates and the authorised wearable-data terminology |
| [`governance/external_source_register.md`](governance/external_source_register.md) | Checksummed identities of sources held outside the repository |
| [`governance/provenance-history-rewrite.md`](governance/provenance-history-rewrite.md) | Evidence tag, verified bundles and exact-tree mappings across the history rewrite |
| [`governance/INTEGRATED_DEVELOPMENT_PLAN_2026.md`](governance/INTEGRATED_DEVELOPMENT_PLAN_2026.md) | Record: integrated plan v2.1 (2026-09-21); earlier versions in [`governance/archive/`](governance/archive/) |
| [`governance/proposals/`](governance/proposals/README.md) | Record: proposals and the texts of adopted proposals |

Supervisor-request logs, readiness maps and memos are listed in [history/README.md](history/README.md).

## Academic alignment package

| File | Content |
|---|---|
| [`academic/c2dta_p0_traceability.md`](academic/c2dta_p0_traceability.md) | Each C2DTA function: implemented, stub or not implemented |
| [`academic/gateway_requirements_and_platform_selection.md`](academic/gateway_requirements_and_platform_selection.md) | Record: REQ-01 to REQ-18 and the Pi 5 / i.MX95 screening (v1.0, 2026-09-21), documentary |
| [`../diagrams/c2dta_five_layer_reference.puml`](../diagrams/c2dta_five_layer_reference.puml) ([SVG](../diagrams/c2dta_five_layer_reference.svg)) | Five-layer C2DTA reference drawing, marking what is implemented; its "live ARM64 evidence pending" labels are out of date |

## Claim–evidence integrity

| File | Content |
|---|---|
| [`claim_evidence_matrix.md`](claim_evidence_matrix.md) ([CSV](claim_evidence_matrix.csv)) | Claims of a larger planned measurement series that was not run; the Yocto–Debian comparison is outside it |

## Scope and start-up (records)

| File | Content |
|---|---|
| [`g0/scope_and_rqs.md`](g0/scope_and_rqs.md) | Scope and RQ1–RQ3, version 2.0 (2026-09-18); the dissertation holds the current wording |
| [`g0/backlog.md`](g0/backlog.md) | Backlog of the planned work |
| [`g0/risks.md`](g0/risks.md) | Risk register |
| [`g0/supervisor_email_g0.md`](g0/supervisor_email_g0.md) | Draft scope email to the supervisors, in Portuguese; not sent |
| [`g0/two_layer_thesis_proposal.md`](g0/two_layer_thesis_proposal.md) | Two-layer thesis proposal; not adopted |
| [`g0/supervisor_decision_matrix.csv`](g0/supervisor_decision_matrix.csv) | Questions for the supervisors, with recommended positions |
| [`g0/supervisor_seven_questions_matrix.md`](g0/supervisor_seven_questions_matrix.md) | Response matrix for the seven supervisor questions |
