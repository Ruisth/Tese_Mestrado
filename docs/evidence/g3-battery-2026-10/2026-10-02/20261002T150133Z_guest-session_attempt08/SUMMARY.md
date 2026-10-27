# 20261002T150133Z_guest-session_attempt08

**ARM64 EMULATED (QEMU/TCG)** — observations of an emulated guest, not native ARM64 performance.

| Field | Value |
|---|---|
| Purpose | engineering |
| Scenario | guest session |
| Status | finished |
| Started (UTC) | 2026-10-02T15:01:33.652975Z |
| Ended (UTC) | 2026-10-02T16:33:50.136852Z |
| Duration | 5536.5 s |
| Seed | — |
| Workload | kind: guest session: boot, stack start, the attempts that reference this session, controlled stop and power-off |
| Identities | drivers_sha256: 4a6a572dc1e2b54754c3a8dec38e6d2392227efc61ee710886ad9ad5729a39a5<br>export_tool_sha256: 544c9b3d451f0a6c3391102ac4031fe93bee79a0b0b9bcd6f41c893592d2422b<br>repo_commit: 80e833f44f647fe9cd8f5e99d3abf3c444de95aa<br>repo_dirty_lines: 0 |

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
| 1 | identities-before-boot | 0 | 1.553 | complete | [stdout](console/001-identities-before-boot.stdout.txt) · [stderr](console/001-identities-before-boot.stderr.txt) |
| 2 | boot | 0 | 32.328 | complete | [stdout](console/002-boot.stdout.txt) · [stderr](console/002-boot.stderr.txt) |
| 3 | guest-state-after-boot | 0 | 3.75 | complete | [stdout](console/003-guest-state-after-boot.stdout.txt) · [stderr](console/003-guest-state-after-boot.stderr.txt) |
| 4 | g3-guest-events-listing | 0 | 0.766 | complete | [stdout](console/004-g3-guest-events-listing.stdout.txt) · [stderr](console/004-g3-guest-events-listing.stderr.txt) |
| 5 | g3-close-units | 0 | 1.055 | complete | [stdout](console/005-g3-close-units.stdout.txt) · [stderr](console/005-g3-close-units.stderr.txt) |
| 6 | stack-stop-130 | 0 | 40.144 | complete | [stdout](console/006-stack-stop-130.stdout.txt) · [stderr](console/006-stack-stop-130.stderr.txt) |
| 7 | tunnel-down | 0 | 0.013 | complete | [stdout](console/007-tunnel-down.stdout.txt) · [stderr](console/007-tunnel-down.stderr.txt) |
| 8 | stack-stop | 0 | 2.792 | complete | [stdout](console/008-stack-stop.stdout.txt) · [stderr](console/008-stack-stop.stderr.txt) |
| 9 | oom-before-poweroff | 0 | 0.791 | complete | [stdout](console/009-oom-before-poweroff.stdout.txt) · [stderr](console/009-oom-before-poweroff.stderr.txt) |
| 10 | session-close | 0 | 10.722 | complete | [stdout](console/010-session-close.stdout.txt) · [stderr](console/010-session-close.stderr.txt) |
| 11 | artefacts-after-poweroff | 0 | 1.317 | complete | [stdout](console/011-artefacts-after-poweroff.stdout.txt) · [stderr](console/011-artefacts-after-poweroff.stderr.txt) |

The full, sanitised argv of each command is in `commands.jsonl`.

## Contents

- `console/` stdout and stderr of every command; `environment/`, `tests/`, `analysis/` as named.
- `raw/` and `simulator/` hold the original artefacts byte for byte, with their own seals if they had one.
- `export_manifest.json` lists every file with its source path and SHA-256; `SHA256SUMS` seals this package.

A package here is a local copy. It is not published or admitted evidence and it is not an off-machine backup.
