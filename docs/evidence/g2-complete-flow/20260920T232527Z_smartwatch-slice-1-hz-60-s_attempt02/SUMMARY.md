# 20260920T232527Z_smartwatch-slice-1-hz-60-s_attempt02

**ARM64 EMULATED (QEMU/TCG)** — observations of an emulated guest, not native ARM64 performance.

| Field | Value |
|---|---|
| Purpose | engineering |
| Scenario | smartwatch slice 1 Hz 60 s |
| Status | finished |
| Started (UTC) | 2026-09-20T23:25:28.023277Z |
| Ended (UTC) | 2026-09-20T23:31:54.649041Z |
| Duration | 386.6 s |
| Seed | 20260921 |
| Workload | devices: 1 smartwatch<br>duration_s: 60<br>itest_run_id: itest-g2-01<br>rate_hz: 1.0<br>scenario: smoke<br>session: 20260920T231756Z_guest-session_attempt02 |
| Identities | drivers_sha256: e1c26c66628ebb959ee1a8b3238be799873042014f2ee2a96b831d6e32e9ee3f<br>export_tool_sha256: 544c9b3d451f0a6c3391102ac4031fe93bee79a0b0b9bcd6f41c893592d2422b<br>repo_commit: b7e0c83c3277f7469c05336f91949e7d1b89489a<br>repo_dirty_lines: 0 |

## Result

Three separate verdicts: whether the instrumentation produced valid evidence, what the system under test did, and whether this copy is intact. The console capture is part of the first: evidence that was not kept in full cannot make an attempt valid.

| Verdict | Value |
|---|---|
| Instrumentation validity | **valid** |
| Validity note | — |
| System outcome | **pass** |
| Console capture | **complete** — every command's stdout and stderr were kept in full |
| Copy verification | **verified** — 32 file(s) copied and verified by SHA-256; 0 excluded for secrets; 0 expected source(s) missing |
| Secret scan | values of the listed variables (names only) and PEM private keys were searched in every file |
| Reason | every published identity accounted; lost 0, late 0, twin and /metrics deltas OK |
| Next action | nominal entry 120 s + 600 s |

## Commands

| # | Name | Exit code | Duration (s) | Console capture | Output |
|---|---|---|---|---|---|
| 1 | pre | 0 | 132.413 | complete | [stdout](console/001-pre.stdout.txt) · [stderr](console/001-pre.stderr.txt) |
| 2 | simulator-and-mark | 0 | 59.437 | complete | [stdout](console/002-simulator-and-mark.stdout.txt) · [stderr](console/002-simulator-and-mark.stderr.txt) |
| 3 | after | 0 | 194.146 | complete | [stdout](console/003-after.stdout.txt) · [stderr](console/003-after.stderr.txt) |
| 4 | twin-readback | 0 | 0.23 | complete | [stdout](console/004-twin-readback.stdout.txt) · [stderr](console/004-twin-readback.stderr.txt) |
| 5 | check | 0 | 0.058 | complete | [stdout](console/005-check.stdout.txt) · [stderr](console/005-check.stderr.txt) |
| 6 | delta | 0 | 0.054 | complete | [stdout](console/006-delta.stdout.txt) · [stderr](console/006-delta.stderr.txt) |
| 7 | verdict | 0 | 0.017 | complete | [stdout](console/007-verdict.stdout.txt) · [stderr](console/007-verdict.stderr.txt) |

The full, sanitised argv of each command is in `commands.jsonl`.

## Expected artefacts

- `simulator/*/sent_events.jsonl`: present
- `simulator/*/events.jsonl`: present
- `simulator/*.marker.json`: present
- `simulator/*.metrics.before.json`: present
- `simulator/*.metrics.after.json`: present
- `simulator/*.twins.before.json`: present
- `simulator/*.twins.after.json`: present
- `simulator/*.reconcile.json`: present

## Contents

- `console/` stdout and stderr of every command; `environment/`, `tests/`, `analysis/` as named.
- `raw/` and `simulator/` hold the original artefacts byte for byte, with their own seals if they had one.
- `export_manifest.json` lists every file with its source path and SHA-256; `SHA256SUMS` seals this package.

A package here is a local copy. It is not published or admitted evidence and it is not an off-machine backup.
