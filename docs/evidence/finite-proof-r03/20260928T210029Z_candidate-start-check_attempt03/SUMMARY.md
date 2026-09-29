# 20260928T210029Z_candidate-start-check_attempt03

**ARM64 EMULATED (QEMU/TCG)** — observations of an emulated guest, not native ARM64 performance.

| Field | Value |
|---|---|
| Purpose | engineering |
| Scenario | candidate start check |
| Status | finished |
| Started (UTC) | 2026-09-28T21:00:29.401107Z |
| Ended (UTC) | 2026-09-28T21:00:36.394561Z |
| Duration | 7.0 s |
| Seed | — |
| Workload | — |
| Identities | drivers_sha256: 761df315a4702b5b128d31f9cac546ec7d810125c767bf2c850750cd4450139e<br>export_tool_sha256: 544c9b3d451f0a6c3391102ac4031fe93bee79a0b0b9bcd6f41c893592d2422b<br>repo_commit: b65a06ddc02842cd6464555e319ee4cc5e0d1bfb<br>repo_dirty_lines: 0 |

## Result

Three separate verdicts: whether the instrumentation produced valid evidence, what the system under test did, and whether this copy is intact. The console capture is part of the first: evidence that was not kept in full cannot make an attempt valid.

| Verdict | Value |
|---|---|
| Instrumentation validity | **valid** |
| Validity note | — |
| System outcome | **pass** |
| Console capture | **complete** — every command's stdout and stderr were kept in full |
| Copy verification | **verified** — 8 file(s) copied and verified by SHA-256; 0 excluded for secrets; 0 expected source(s) missing |
| Secret scan | values of the listed variables (names only) and PEM private keys were searched in every file |
| Reason | the broker started after the installation with the candidate's mosquitto.conf and no reload; the controller is the 489bc9e5b5b0660026ea2630b8d1d124049ba2ce image |
| Next action | gate_health.sh with the packet's environment |

## Commands

| # | Name | Exit code | Duration (s) | Console capture | Output |
|---|---|---|---|---|---|
| 1 | start-state | 0 | 6.868 | complete | [stdout](console/001-start-state.stdout.txt) · [stderr](console/001-start-state.stderr.txt) |
| 2 | start-judgement | 0 | 0.037 | complete | [stdout](console/002-start-judgement.stdout.txt) · [stderr](console/002-start-judgement.stderr.txt) |

The full, sanitised argv of each command is in `commands.jsonl`.

## Contents

- `console/` stdout and stderr of every command; `environment/`, `tests/`, `analysis/` as named.
- `raw/` and `simulator/` hold the original artefacts byte for byte, with their own seals if they had one.
- `export_manifest.json` lists every file with its source path and SHA-256; `SHA256SUMS` seals this package.

A package here is a local copy. It is not published or admitted evidence and it is not an off-machine backup.
