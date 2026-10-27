# 20260928T205459Z_live-preflight_attempt07

**ARM64 EMULATED (QEMU/TCG)** — observations of an emulated guest, not native ARM64 performance.

| Field | Value |
|---|---|
| Purpose | engineering |
| Scenario | live preflight |
| Status | finished |
| Started (UTC) | 2026-09-28T20:55:00.089470Z |
| Ended (UTC) | 2026-09-28T21:00:16.874846Z |
| Duration | 316.8 s |
| Seed | — |
| Workload | collector_samples: 45 s at 1 s<br>expected_services: egw-mosquitto-1,egw-mongodb-1,egw-ditto-policies-1,egw-ditto-things-1,egw-ditto-gateway-1,egw-controller-1<br>session: 20260928T205412Z_guest-session_attempt06 |
| Identities | drivers_sha256: 761df315a4702b5b128d31f9cac546ec7d810125c767bf2c850750cd4450139e<br>export_tool_sha256: 544c9b3d451f0a6c3391102ac4031fe93bee79a0b0b9bcd6f41c893592d2422b<br>repo_commit: b65a06ddc02842cd6464555e319ee4cc5e0d1bfb<br>repo_dirty_lines: 0 |

## Result

Three separate verdicts: whether the instrumentation produced valid evidence, what the system under test did, and whether this copy is intact. The console capture is part of the first: evidence that was not kept in full cannot make an attempt valid.

| Verdict | Value |
|---|---|
| Instrumentation validity | **valid** |
| Validity note | — |
| System outcome | **pass** |
| Console capture | **complete** — every command's stdout and stderr were kept in full |
| Copy verification | **verified** — 40 file(s) copied and verified by SHA-256; 0 excluded for secrets; 0 expected source(s) missing |
| Secret scan | values of the listed variables (names only) and PEM private keys were searched in every file |
| Reason | stack up through the interlock; dev collector deployed and live-checked with six services |
| Next action | smartwatch slice, then the nominal entry |

## Commands

| # | Name | Exit code | Duration (s) | Console capture | Output |
|---|---|---|---|---|---|
| 1 | stack-start-interlock | 0 | 184.917 | complete | [stdout](console/001-stack-start-interlock.stdout.txt) · [stderr](console/001-stack-start-interlock.stderr.txt) |
| 2 | collector-copy | 0 | 1.046 | complete | [stdout](console/002-collector-copy.stdout.txt) · [stderr](console/002-collector-copy.stderr.txt) |
| 3 | collector-install | 0 | 1.838 | complete | [stdout](console/003-collector-install.stdout.txt) · [stderr](console/003-collector-install.stderr.txt) |
| 4 | deployed-tree-hashes | 0 | 1.137 | complete | [stdout](console/004-deployed-tree-hashes.stdout.txt) · [stderr](console/004-deployed-tree-hashes.stderr.txt) |
| 5 | deployed-vs-clone | 0 | 0.03 | complete | [stdout](console/005-deployed-vs-clone.stdout.txt) · [stderr](console/005-deployed-vs-clone.stderr.txt) |
| 6 | controller-health | 0 | 22.983 | complete | [stdout](console/006-controller-health.stdout.txt) · [stderr](console/006-controller-health.stderr.txt) |
| 7 | stack-health | 0 | 24.324 | complete | [stdout](console/007-stack-health.stdout.txt) · [stderr](console/007-stack-health.stderr.txt) |
| 8 | broker-secrets-check | 0 | 6.64 | complete | [stdout](console/008-broker-secrets-check.stdout.txt) · [stderr](console/008-broker-secrets-check.stderr.txt) |
| 9 | clock-offset | 0 | 2.215 | complete | [stdout](console/009-clock-offset.stdout.txt) · [stderr](console/009-clock-offset.stderr.txt) |
| 10 | guest-clock | 0 | 2.155 | complete | [stdout](console/010-guest-clock.stdout.txt) · [stderr](console/010-guest-clock.stderr.txt) |
| 11 | sut-environment | 0 | 4.091 | complete | [stdout](console/011-sut-environment.stdout.txt) · [stderr](console/011-sut-environment.stderr.txt) |
| 12 | sut-environment-fetch | 0 | 0.721 | complete | [stdout](console/012-sut-environment-fetch.stdout.txt) · [stderr](console/012-sut-environment-fetch.stderr.txt) |
| 13 | collector-live | 0 | 55.658 | complete | [stdout](console/013-collector-live.stdout.txt) · [stderr](console/013-collector-live.stderr.txt) |
| 14 | fetch-collector-output | 0 | 8.24 | complete | [stdout](console/014-fetch-collector-output.stdout.txt) · [stderr](console/014-fetch-collector-output.stderr.txt) |
| 15 | collector-check | 0 | 0.099 | complete | [stdout](console/015-collector-check.stdout.txt) · [stderr](console/015-collector-check.stderr.txt) |
| 16 | collector-duration | 0 | 0.017 | complete | [stdout](console/016-collector-duration.stdout.txt) · [stderr](console/016-collector-duration.stderr.txt) |

The full, sanitised argv of each command is in `commands.jsonl`.

## Contents

- `console/` stdout and stderr of every command; `environment/`, `tests/`, `analysis/` as named.
- `raw/` and `simulator/` hold the original artefacts byte for byte, with their own seals if they had one.
- `export_manifest.json` lists every file with its source path and SHA-256; `SHA256SUMS` seals this package.

A package here is a local copy. It is not published or admitted evidence and it is not an off-machine backup.
