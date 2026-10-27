# Documentation index

Start with the [main README](../README.md); the four guides below give more detail. Every measured
figure comes from an ARM64 computer emulated by QEMU on an ordinary PC.

## The four guides

| Guide | Read it to |
|---|---|
| [architecture.md](architecture.md) | See how the parts fit together and find the code |
| [demo.md](demo.md) | Prepare the PC and run the demonstration |
| [results.md](results.md) | Check each result, its data and the code that analysed it |
| [reproduce.md](reproduce.md) | Rebuild the image and repeat the measurements |

## Interfaces and design decisions

| File | Content |
|---|---|
| [`../src/CONTRACTS.md`](../src/CONTRACTS.md) | Normative interfaces, v1.2 (2026-09-24): topics, envelope, twins, ports, outcomes |
| [`adr/README.md`](adr/README.md) | Index of the architecture decision records 0001–0011 (there is no 0009), with the recorded status of each |
| [`../diagrams/README.md`](../diagrams/README.md) | Diagram families: Mermaid views in [`../diagrams/architecture.md`](../diagrams/architecture.md) (drawn against CONTRACTS v1.1) and the PlantUML five-layer C2DTA reference |

## Evidence

The recorded data are the folders under [`evidence/`](evidence/). Each is a byte-for-byte copy of the
records of one piece of work, and none is ever edited. Most have a `README.md` and `SHA256SUMS` at
their root or in their dated subfolders. The exceptions: `compare-a02/` is a derived summary whose
inputs and digests are in its `summary.json`, with its raw package sealed locally; `tests/` has no
README and its first directory (`2026-08-08`) has no seal; the rehearsal is a single note.
`python tools/ci/verify_evidence.py` checks the seals.

[results.md](results.md) maps each result to its folder and to the dissertation's sections and tables,
and states which data are held outside the repository. The folder names are the original identifiers
and never change, so the table below gives a descriptive name first and the folder in parentheses.

| Records (folder) | Date | Content |
|---|---|---|
| [Yocto–Debian 13 comparison](evidence/compare-a02/README.md) (`compare-a02/`) | 2026-10-18/19 | Yocto image vs Debian 13: table, one row per run and the plan; the raw records are kept locally |
| [Test battery](evidence/g3-battery-2026-10/README.md) (`g3-battery-2026-10/`) | 2026-10-02 to 2026-10-07 | The functional tests: 38 record folders |
| [Controller restart, diagnostic run](evidence/finite-proof-r03/README.md) (`finite-proof-r03/`) | 2026-09-28 | A diagnostic run of the controller's recovery after a restart |
| [Wearable-to-twin integration](evidence/g2-complete-flow/README.md) (`g2-complete-flow/`) | 2026-09-20/21 | One smartwatch end to end, and its twin kept across a restart of the six containers |
| [Gateway image](evidence/integrated-qemu/README.md) (`integrated-qemu/`) | 2026-09-18 | Integrated image build and boots, and an isolated MongoDB 7.0.39 test |
| [Base image](evidence/g1-yocto-qemu/README.md) (`g1-yocto-qemu/`) | 2026-08-11 and 2026-08-14 | A preliminary build and two starts; a clean build and five checked starts |
| [Unit tests](evidence/tests/) (`tests/`) | 2026-08-08 to 2026-08-11 | Unit-test runs, one directory per commit; the newest in the repository is `2026-08-11-head-4e67717` (701 passed) |
| [Word manuscript import](evidence/word-import-2026-09-17/README.md) (`word-import-2026-09-17/`) | 2026-09-17 | Verification of the LaTeX import of the Word manuscript |
| [Dry rehearsal](evidence/rehearsal/2026-08-08-dry-rehearsal.md) (`rehearsal/`) | 2026-08-08 | Dry rehearsal of the campaign logistics; no result |

## Setup runbooks

These are still used by the guides.

| File | Content |
|---|---|
| [`setup/wsl2_ubuntu_yocto.md`](setup/wsl2_ubuntu_yocto.md) | WSL2, Ubuntu 24.04, Yocto Scarthgap, kas and QEMU on the build host |
| [`setup/qemu_integrated_gateway.md`](setup/qemu_integrated_gateway.md) | The manual runbook of 2026-09-18/19. Its §1–2 and §4 remain the preparation steps used by [demo.md](demo.md) and [reproduce.md](reproduce.md); §5.1–5.6 are automated by `tools/compare/provision_stack.sh`; §6.1 is the source of the measurement's helper file. Its status notes are historical |
| [`setup/local_test_outputs.md`](setup/local_test_outputs.md) | The local `output_test` folder: one verified package per attempt, failures included. It holds the data that [results.md](results.md) lists as kept locally |

## C2DTA academic notes

| File | Content |
|---|---|
| [`academic/c2dta_p0_traceability.md`](academic/c2dta_p0_traceability.md) | Each C2DTA function: implemented, stub or not implemented (v1.2, 2026-09-18). Its evidence statements predate the wearable-to-twin integration and the test battery |
| [`academic/gateway_requirements_and_platform_selection.md`](academic/gateway_requirements_and_platform_selection.md) | An earlier version of the dissertation's requirements list, REQ-01 to REQ-18, and the Pi 5 / i.MX95 screening (v1.0, 2026-09-21); documentary |
| [`../diagrams/c2dta_five_layer_reference.puml`](../diagrams/c2dta_five_layer_reference.puml) ([SVG](../diagrams/c2dta_five_layer_reference.svg)) | Five-layer C2DTA reference drawing, marking what is implemented; its "live ARM64 evidence pending" labels are out of date |

## Tools

| Folder | Content |
|---|---|
| [`tools/compare/`](../tools/compare/README.md) | Start, check and power off each configuration (`tf.sh`, `functional_check.sh`, `scenarios/`), and the comparison measurements (`measure_*`) |
| [`tools/demo/`](../tools/demo/README.md) | The demonstration: the menu (`demo.sh`), the simulated devices (`wearables/`) and the observers (`observe/`) |
| [`tools/setup/`](../tools/setup/README.md) | Preparing another PC for the demonstration from a kit (`prepare_demo_host.sh`, `make_demo_kit.sh`) |
| [`tools/session/`](../tools/session/README.md) | Scripts that drove the earlier test runs. The comparison measurement calls two of them (`proof_hook_drained.sh` and `nominal_account.py`), and [reproduce.md](reproduce.md) runs a third, `regen_helpers.py`, to write the helper file. Keep this folder where it is |
| [`tools/probe/`](../tools/probe/README.md) | A diagnostic of how the broker holds messages while the controller is away (ADR 0011). Not needed to run or measure |
| `tools/ci/`, `tools/test/` | The checks run by the automatic workflow (`verify_evidence.py`, `check_markdown_links.py`); BusyBox test helpers |

## Project records

How the project reached its current state is kept apart from this index, in
[history/README.md](history/README.md): the work log and the progress record, the governance and
supervision records, the reviews, the start-up records, the historical LaTeX conversion (`thesis/`)
and the deferred article (`paper/`). They are records: a dated statement in one of them describes the
project on that date. `docs/governance/` stays at its path because sealed evidence links to it; the
history index lists its files.
