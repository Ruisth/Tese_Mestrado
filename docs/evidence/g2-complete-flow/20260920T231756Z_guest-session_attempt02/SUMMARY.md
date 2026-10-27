# 20260920T231756Z_guest-session_attempt02

**ARM64 EMULATED (QEMU/TCG)** — observations of an emulated guest, not native ARM64 performance.

| Field | Value |
|---|---|
| Purpose | engineering |
| Scenario | guest session |
| Status | finished |
| Started (UTC) | 2026-09-20T23:17:56.296762Z |
| Ended (UTC) | 2026-09-20T23:39:27.215815Z |
| Duration | 1290.9 s |
| Seed | — |
| Workload | kind: guest session: boot, stack start, the attempts that reference this session, controlled stop and power-off |
| Identities | drivers_sha256: e1c26c66628ebb959ee1a8b3238be799873042014f2ee2a96b831d6e32e9ee3f<br>export_tool_sha256: 544c9b3d451f0a6c3391102ac4031fe93bee79a0b0b9bcd6f41c893592d2422b<br>repo_commit: b7e0c83c3277f7469c05336f91949e7d1b89489a<br>repo_dirty_lines: 0 |

## Result

Three separate verdicts: whether the instrumentation produced valid evidence, what the system under test did, and whether this copy is intact. The console capture is part of the first: evidence that was not kept in full cannot make an attempt valid.

| Verdict | Value |
|---|---|
| Instrumentation validity | **not-applicable** |
| Validity note | — |
| System outcome | **pass** |
| Console capture | **complete** — every command's stdout and stderr were kept in full |
| Copy verification | **verified** — 66 file(s) copied and verified by SHA-256; 0 excluded for secrets; 0 expected source(s) missing |
| Secret scan | values of the listed variables (names only) and PEM private keys were searched in every file |
| Reason | session closed: stack stopped before power-off, journal and final state kept |
| Next action | none |

## Commands

| # | Name | Exit code | Duration (s) | Console capture | Output |
|---|---|---|---|---|---|
| 1 | identities-before-boot | 0 | 3.077 | complete | [stdout](console/001-identities-before-boot.stdout.txt) · [stderr](console/001-identities-before-boot.stderr.txt) |
| 2 | boot | 0 | 33.175 | complete | [stdout](console/002-boot.stdout.txt) · [stderr](console/002-boot.stderr.txt) |
| 3 | guest-state-after-boot | 0 | 2.853 | complete | [stdout](console/003-guest-state-after-boot.stdout.txt) · [stderr](console/003-guest-state-after-boot.stderr.txt) |
| 4 | tunnel-down | 0 | 0.013 | complete | [stdout](console/004-tunnel-down.stdout.txt) · [stderr](console/004-tunnel-down.stderr.txt) |
| 5 | stack-stop | 0 | 15.943 | complete | [stdout](console/005-stack-stop.stdout.txt) · [stderr](console/005-stack-stop.stderr.txt) |
| 6 | oom-before-poweroff | 0 | 0.942 | complete | [stdout](console/006-oom-before-poweroff.stdout.txt) · [stderr](console/006-oom-before-poweroff.stderr.txt) |
| 7 | session-close | 0 | 10.74 | complete | [stdout](console/007-session-close.stdout.txt) · [stderr](console/007-session-close.stderr.txt) |
| 8 | artefacts-after-poweroff | 0 | 2.659 | complete | [stdout](console/008-artefacts-after-poweroff.stdout.txt) · [stderr](console/008-artefacts-after-poweroff.stderr.txt) |

The full, sanitised argv of each command is in `commands.jsonl`.

## Contents

- `console/` stdout and stderr of every command; `environment/`, `tests/`, `analysis/` as named.
- `raw/` and `simulator/` hold the original artefacts byte for byte, with their own seals if they had one.
- `export_manifest.json` lists every file with its source path and SHA-256; `SHA256SUMS` seals this package.

A package here is a local copy. It is not published or admitted evidence and it is not an off-machine backup.
