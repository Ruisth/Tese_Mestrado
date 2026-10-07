# 20261003T132836Z_g2-gate-preconditions_attempt06

**ARM64 EMULATED (QEMU/TCG)** — observations of an emulated guest, not native ARM64 performance.

| Field | Value |
|---|---|
| Purpose | engineering |
| Scenario | G2 gate preconditions |
| Status | finished |
| Started (UTC) | 2026-10-03T13:28:36.410438Z |
| Ended (UTC) | 2026-10-03T13:29:01.809940Z |
| Duration | 25.4 s |
| Seed | — |
| Workload | expected_services: egw-mosquitto-1,egw-mongodb-1,egw-ditto-policies-1,egw-ditto-things-1,egw-ditto-gateway-1,egw-controller-1<br>gate: G2<br>healthy_limit_s: 1800<br>healthy_step_s: 15<br>publishes: nothing: this driver only reads<br>session: 20261003T132249Z_guest-session_attempt09 |
| Identities | drivers_sha256: 4a6a572dc1e2b54754c3a8dec38e6d2392227efc61ee710886ad9ad5729a39a5<br>export_tool_sha256: 544c9b3d451f0a6c3391102ac4031fe93bee79a0b0b9bcd6f41c893592d2422b<br>repo_commit: 80e833f44f647fe9cd8f5e99d3abf3c444de95aa<br>repo_dirty_lines: 0 |

## Result

Three separate verdicts: whether the instrumentation produced valid evidence, what the system under test did, and whether this copy is intact. The console capture is part of the first: evidence that was not kept in full cannot make an attempt valid.

| Verdict | Value |
|---|---|
| Instrumentation validity | **valid** |
| Validity note | — |
| System outcome | **pass** |
| Console capture | **complete** — every command's stdout and stderr were kept in full |
| Copy verification | **verified** — 24 file(s) copied and verified by SHA-256; 0 excluded for secrets; 0 expected source(s) missing |
| Secret scan | values of the listed variables (names only) and PEM private keys were searched in every file |
| Reason | the six expected services are running and healthy, /health answers 200 with status ok, /ready answers 200, every counter and queue_depth is 0 for the identified controller process, the six container identities and the controller build identity are recorded, and the publishing path is TLS with anonymous access refused |
| Next action | run the G2 flow on this gate: slice.sh <fresh run id> <a seed never used on this MongoDB volume> |

## Commands

| # | Name | Exit code | Duration (s) | Console capture | Output |
|---|---|---|---|---|---|
| 1 | services-healthy | 0 | 5.872 | complete | [stdout](console/001-services-healthy.stdout.txt) · [stderr](console/001-services-healthy.stderr.txt) |
| 2 | controller-endpoints | 0 | 0.569 | complete | [stdout](console/002-controller-endpoints.stdout.txt) · [stderr](console/002-controller-endpoints.stderr.txt) |
| 3 | endpoints-verdict | 0 | 0.019 | complete | [stdout](console/003-endpoints-verdict.stdout.txt) · [stderr](console/003-endpoints-verdict.stderr.txt) |
| 4 | counters-verdict | 0 | 0.016 | complete | [stdout](console/004-counters-verdict.stdout.txt) · [stderr](console/004-counters-verdict.stderr.txt) |
| 5 | container-identities | 0 | 15.512 | complete | [stdout](console/005-container-identities.stdout.txt) · [stderr](console/005-container-identities.stderr.txt) |
| 6 | controller-build-identity | 0 | 1.023 | complete | [stdout](console/006-controller-build-identity.stdout.txt) · [stderr](console/006-controller-build-identity.stderr.txt) |
| 7 | tls-configuration | 0 | 2.043 | complete | [stdout](console/007-tls-configuration.stdout.txt) · [stderr](console/007-tls-configuration.stderr.txt) |

The full, sanitised argv of each command is in `commands.jsonl`.

## Expected artefacts

- `environment/health.json`: present
- `environment/ready.json`: present
- `environment/metrics.json`: present
- `environment/container_identities.txt`: present
- `environment/egw-controller-build-identity.txt`: present
- `environment/tls_configuration.txt`: present

## Contents

- `console/` stdout and stderr of every command; `environment/`, `tests/`, `analysis/` as named.
- `raw/` and `simulator/` hold the original artefacts byte for byte, with their own seals if they had one.
- `export_manifest.json` lists every file with its source path and SHA-256; `SHA256SUMS` seals this package.

A package here is a local copy. It is not published or admitted evidence and it is not an off-machine backup.
