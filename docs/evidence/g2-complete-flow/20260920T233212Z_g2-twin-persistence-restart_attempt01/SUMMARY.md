# 20260920T233212Z_g2-twin-persistence-restart_attempt01

**ARM64 EMULATED (QEMU/TCG)** — observations of an emulated guest, not native ARM64 performance.

| Field | Value |
|---|---|
| Purpose | engineering |
| Scenario | G2 twin persistence restart |
| Status | finished |
| Started (UTC) | 2026-09-20T23:32:12.132809Z |
| Ended (UTC) | 2026-09-20T23:38:35.357124Z |
| Duration | 383.2 s |
| Seed | — |
| Workload | gate: G2<br>itest_run_id: itest-g2-01<br>procedure: runbook 6.5: compose down then up -d, volumes preserved<br>publishes: nothing: the simulator is never started<br>restarts: egw-mosquitto-1,egw-mongodb-1,egw-ditto-policies-1,egw-ditto-things-1,egw-ditto-gateway-1,egw-controller-1<br>session: 20260920T231756Z_guest-session_attempt02 |
| Identities | drivers_sha256: e1c26c66628ebb959ee1a8b3238be799873042014f2ee2a96b831d6e32e9ee3f<br>export_tool_sha256: 544c9b3d451f0a6c3391102ac4031fe93bee79a0b0b9bcd6f41c893592d2422b<br>repo_commit: b7e0c83c3277f7469c05336f91949e7d1b89489a<br>repo_dirty_lines: 0 |

## Result

Three separate verdicts: whether the instrumentation produced valid evidence, what the system under test did, and whether this copy is intact. The console capture is part of the first: evidence that was not kept in full cannot make an attempt valid.

| Verdict | Value |
|---|---|
| Instrumentation validity | **valid** |
| Validity note | — |
| System outcome | **pass** |
| Console capture | **complete** — every command's stdout and stderr were kept in full |
| Copy verification | **verified** — 60 file(s) copied and verified by SHA-256; 0 excluded for secrets; 0 expected source(s) missing |
| Secret scan | values of the listed variables (names only) and PEM private keys were searched in every file |
| Reason | the restart was shown (a new controller process and six new container objects, each started later), the stack came back ready and healthy, and the twin's stored state is the same on both sides of it with nothing published between the two snapshots |
| Next action | publish the G2 evidence capsule and present the gate for the decision; the acceptance itself stays with Rui |

## Commands

| # | Name | Exit code | Duration (s) | Console capture | Output |
|---|---|---|---|---|---|
| 1 | quiesce | 0 | 130.957 | complete | [stdout](console/001-quiesce.stdout.txt) · [stderr](console/001-quiesce.stderr.txt) |
| 2 | metrics-before | 0 | 0.023 | complete | [stdout](console/002-metrics-before.stdout.txt) · [stderr](console/002-metrics-before.stderr.txt) |
| 3 | containers-before | 0 | 4.775 | complete | [stdout](console/003-containers-before.stdout.txt) · [stderr](console/003-containers-before.stderr.txt) |
| 4 | twin-before | 0 | 0.498 | complete | [stdout](console/004-twin-before.stdout.txt) · [stderr](console/004-twin-before.stderr.txt) |
| 5 | events-before | 0 | 0.697 | complete | [stdout](console/005-events-before.stdout.txt) · [stderr](console/005-events-before.stderr.txt) |
| 6 | snapshot-before | 0 | 0.239 | complete | [stdout](console/006-snapshot-before.stdout.txt) · [stderr](console/006-snapshot-before.stderr.txt) |
| 7 | restart-down-up | 0 | 179.142 | complete | [stdout](console/007-restart-down-up.stdout.txt) · [stderr](console/007-restart-down-up.stderr.txt) |
| 8 | ready-again | 0 | 23.028 | complete | [stdout](console/008-ready-again.stdout.txt) · [stderr](console/008-ready-again.stderr.txt) |
| 9 | services-healthy-again | 0 | 26.508 | complete | [stdout](console/009-services-healthy-again.stdout.txt) · [stderr](console/009-services-healthy-again.stderr.txt) |
| 10 | metrics-after | 0 | 0.129 | complete | [stdout](console/010-metrics-after.stdout.txt) · [stderr](console/010-metrics-after.stderr.txt) |
| 11 | containers-after | 0 | 5.968 | complete | [stdout](console/011-containers-after.stdout.txt) · [stderr](console/011-containers-after.stderr.txt) |
| 12 | restart-shown | 0 | 0.017 | complete | [stdout](console/012-restart-shown.stdout.txt) · [stderr](console/012-restart-shown.stderr.txt) |
| 13 | snapshot-after | 0 | 9.23 | complete | [stdout](console/013-snapshot-after.stdout.txt) · [stderr](console/013-snapshot-after.stderr.txt) |
| 14 | twin-state-same | 0 | 0.055 | complete | [stdout](console/014-twin-state-same.stdout.txt) · [stderr](console/014-twin-state-same.stderr.txt) |
| 15 | twin-after | 0 | 0.384 | complete | [stdout](console/015-twin-after.stdout.txt) · [stderr](console/015-twin-after.stderr.txt) |
| 16 | events-after | 0 | 0.834 | complete | [stdout](console/016-events-after.stdout.txt) · [stderr](console/016-events-after.stderr.txt) |
| 17 | stored-state | 0 | 0.017 | complete | [stdout](console/017-stored-state.stdout.txt) · [stderr](console/017-stored-state.stderr.txt) |

The full, sanitised argv of each command is in `commands.jsonl`.

## Expected artefacts

- `environment/metrics.persist-before.json`: present
- `environment/containers.persist-before.txt`: present
- `environment/twin.persist-before.json`: present

## Contents

- `console/` stdout and stderr of every command; `environment/`, `tests/`, `analysis/` as named.
- `raw/` and `simulator/` hold the original artefacts byte for byte, with their own seals if they had one.
- `export_manifest.json` lists every file with its source path and SHA-256; `SHA256SUMS` seals this package.

A package here is a local copy. It is not published or admitted evidence and it is not an off-machine backup.
