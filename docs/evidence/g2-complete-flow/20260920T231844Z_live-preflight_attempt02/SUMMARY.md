# 20260920T231844Z_live-preflight_attempt02

**ARM64 EMULATED (QEMU/TCG)** — observations of an emulated guest, not native ARM64 performance.

| Field | Value |
|---|---|
| Purpose | engineering |
| Scenario | live preflight |
| Status | failed |
| Started (UTC) | 2026-09-20T23:18:44.492663Z |
| Ended (UTC) | 2026-09-20T23:21:22.786882Z |
| Duration | 158.3 s |
| Seed | — |
| Workload | collector_samples: 45 s at 1 s<br>expected_services: egw-mosquitto-1,egw-mongodb-1,egw-ditto-policies-1,egw-ditto-things-1,egw-ditto-gateway-1,egw-controller-1<br>session: 20260920T231756Z_guest-session_attempt02 |
| Identities | drivers_sha256: e1c26c66628ebb959ee1a8b3238be799873042014f2ee2a96b831d6e32e9ee3f<br>export_tool_sha256: 544c9b3d451f0a6c3391102ac4031fe93bee79a0b0b9bcd6f41c893592d2422b<br>repo_commit: b7e0c83c3277f7469c05336f91949e7d1b89489a<br>repo_dirty_lines: 0 |

## Result

Three separate verdicts: whether the instrumentation produced valid evidence, what the system under test did, and whether this copy is intact. The console capture is part of the first: evidence that was not kept in full cannot make an attempt valid.

| Verdict | Value |
|---|---|
| Instrumentation validity | **invalid** |
| Validity note | — |
| System outcome | **not-run** |
| Console capture | **complete** — every command's stdout and stderr were kept in full |
| Copy verification | **verified** — 13 file(s) copied and verified by SHA-256; 0 excluded for secrets; 0 expected source(s) missing |
| Secret scan | values of the listed variables (names only) and PEM private keys were searched in every file |
| Reason | prerequisite failed: the deployed tree differs from the clean clone; not run: controller-health stack-health broker-secrets-check clock-offset guest-clock sut-environment sut-environment-fetch collector-live fetch-collector-output collector-check collector-duration |
| Next action | STOP: fix before any longer test; the preflight did not run as a check |

## Commands

| # | Name | Exit code | Duration (s) | Console capture | Output |
|---|---|---|---|---|---|
| 1 | stack-start-interlock | 0 | 154.124 | complete | [stdout](console/001-stack-start-interlock.stdout.txt) · [stderr](console/001-stack-start-interlock.stderr.txt) |
| 2 | collector-copy | 0 | 1.237 | complete | [stdout](console/002-collector-copy.stdout.txt) · [stderr](console/002-collector-copy.stderr.txt) |
| 3 | collector-install | 0 | 1.719 | complete | [stdout](console/003-collector-install.stdout.txt) · [stderr](console/003-collector-install.stderr.txt) |
| 4 | deployed-tree-hashes | 0 | 0.978 | complete | [stdout](console/004-deployed-tree-hashes.stdout.txt) · [stderr](console/004-deployed-tree-hashes.stderr.txt) |
| 5 | deployed-vs-clone | 1 | 0.026 | complete | [stdout](console/005-deployed-vs-clone.stdout.txt) · [stderr](console/005-deployed-vs-clone.stderr.txt) |

The full, sanitised argv of each command is in `commands.jsonl`.

## Contents

- `console/` stdout and stderr of every command; `environment/`, `tests/`, `analysis/` as named.
- `raw/` and `simulator/` hold the original artefacts byte for byte, with their own seals if they had one.
- `export_manifest.json` lists every file with its source path and SHA-256; `SHA256SUMS` seals this package.

A package here is a local copy. It is not published or admitted evidence and it is not an off-machine backup.
