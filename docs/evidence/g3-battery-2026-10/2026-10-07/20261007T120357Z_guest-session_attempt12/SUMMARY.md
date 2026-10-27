# 20261007T120357Z_guest-session_attempt12

**ARM64 EMULATED (QEMU/TCG)** — observations of an emulated guest, not native ARM64 performance.

| Field | Value |
|---|---|
| Purpose | engineering |
| Scenario | guest session |
| Status | finished |
| Started (UTC) | 2026-10-07T12:03:57.232432Z |
| Ended (UTC) | 2026-10-07T12:35:03.484817Z |
| Duration | 1866.3 s |
| Seed | — |
| Workload | kind: guest session: boot, stack start, the attempts that reference this session, controlled stop and power-off |
| Identities | drivers_sha256: 2c209b09faf58bb4986cf39b7bb1f13936fae8e94c3b5eb3faf84f722bfe44ed<br>export_tool_sha256: 544c9b3d451f0a6c3391102ac4031fe93bee79a0b0b9bcd6f41c893592d2422b<br>repo_commit: 1fd9792bb76f02c6948f33887207dba4837202db<br>repo_dirty_lines: 0 |

## Result

Three separate verdicts: whether the instrumentation produced valid evidence, what the system under test did, and whether this copy is intact. The console capture is part of the first: evidence that was not kept in full cannot make an attempt valid.

| Verdict | Value |
|---|---|
| Instrumentation validity | **not-applicable** |
| Validity note | — |
| System outcome | **pass** |
| Console capture | **complete** — every command's stdout and stderr were kept in full |
| Copy verification | **verified** — 85 file(s) copied and verified by SHA-256; 0 excluded for secrets; 0 expected source(s) missing |
| Secret scan | values of the listed variables (names only) and PEM private keys were searched in every file |
| Reason | session closed: stack stopped before power-off, journal and final state kept |
| Next action | none |

## Commands

| # | Name | Exit code | Duration (s) | Console capture | Output |
|---|---|---|---|---|---|
| 1 | identities-before-boot | 0 | 1.434 | complete | [stdout](console/001-identities-before-boot.stdout.txt) · [stderr](console/001-identities-before-boot.stderr.txt) |
| 2 | boot | 0 | 34.696 | complete | [stdout](console/002-boot.stdout.txt) · [stderr](console/002-boot.stderr.txt) |
| 3 | guest-state-after-boot | 0 | 3.849 | complete | [stdout](console/003-guest-state-after-boot.stdout.txt) · [stderr](console/003-guest-state-after-boot.stderr.txt) |
| 4 | g3-guest-events-listing | 0 | 0.86 | complete | [stdout](console/004-g3-guest-events-listing.stdout.txt) · [stderr](console/004-g3-guest-events-listing.stderr.txt) |
| 5 | g3-close-units | 0 | 0.879 | complete | [stdout](console/005-g3-close-units.stdout.txt) · [stderr](console/005-g3-close-units.stderr.txt) |
| 6 | stack-stop-130 | 0 | 42.497 | complete | [stdout](console/006-stack-stop-130.stdout.txt) · [stderr](console/006-stack-stop-130.stderr.txt) |
| 7 | tunnel-down | 0 | 0.011 | complete | [stdout](console/007-tunnel-down.stdout.txt) · [stderr](console/007-tunnel-down.stderr.txt) |
| 8 | stack-stop | 0 | 2.486 | complete | [stdout](console/008-stack-stop.stdout.txt) · [stderr](console/008-stack-stop.stderr.txt) |
| 9 | oom-before-poweroff | 0 | 0.766 | complete | [stdout](console/009-oom-before-poweroff.stdout.txt) · [stderr](console/009-oom-before-poweroff.stderr.txt) |
| 10 | session-close | 0 | 12.627 | complete | [stdout](console/010-session-close.stdout.txt) · [stderr](console/010-session-close.stderr.txt) |
| 11 | artefacts-after-poweroff | 0 | 1.224 | complete | [stdout](console/011-artefacts-after-poweroff.stdout.txt) · [stderr](console/011-artefacts-after-poweroff.stderr.txt) |

The full, sanitised argv of each command is in `commands.jsonl`.

## Contents

- `console/` stdout and stderr of every command; `environment/`, `tests/`, `analysis/` as named.
- `raw/` and `simulator/` hold the original artefacts byte for byte, with their own seals if they had one.
- `export_manifest.json` lists every file with its source path and SHA-256; `SHA256SUMS` seals this package.

A package here is a local copy. It is not published or admitted evidence and it is not an off-machine backup.
