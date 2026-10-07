# 20261002T161432Z_g3-qualification-t4-reset_attempt01

**ARM64 EMULATED (QEMU/TCG)** — observations of an emulated guest, not native ARM64 performance.

| Field | Value |
|---|---|
| Purpose | official |
| Scenario | G3 qualification t4-reset |
| Status | finished |
| Started (UTC) | 2026-10-02T16:14:33.216386Z |
| Ended (UTC) | 2026-10-02T16:21:38.426894Z |
| Duration | 425.2 s |
| Seed | — |
| Workload | battery: G3 qualifying battery (decision packet of 2026-10-01, revision 2; authorised 2026-10-02)<br>egw_clone: /home/ruisth/egw-exec/repo<br>harness_run_id: None<br>helper_sha256: e5eba37e529a47885a8aea0e718d25ac71ce1e31a0c1a381b4520fe4c914b4fb<br>host_uptime_at_row_start_s: 4636<br>host_uptime_baseline_s: 24<br>ids_note: None<br>itest_run_ids: ['itest-dup-02-q1']<br>row: t4-reset<br>row_ceiling_min: 35<br>rows_manifest_sha256: cfca6a9397715d0c95881a2c824cad83a95e73727a500351920faf5552ad230c<br>runbook: {'commit': '80e833f44f647fe9cd8f5e99d3abf3c444de95aa', 'lines': 1614, 'path': 'docs/setup/qemu_integrated_gateway.md', 'sha256': 'c55a2d3b68fe7bc463d99fb2c4456e1d6462ceb7eae8e16495aaf1d1fecd74ae'}<br>session: 20261002T150133Z_guest-session_attempt08<br>session_elapsed_at_row_start_s: 4612<br>session_label: S1<br>step_files: {'t4-reset.sh': '3c5d4ec05701e41517762814f9e7207d5956394496a00c839f0b41596d020681'}<br>step_source_lines: {'t4-reset.sh': '1399'}<br>steps_script_sha256: fd652ec928ce9e9570f03fa526b83473a6706a17d81b5ade9c2dbc6b42e44ac1 |
| Identities | drivers_sha256: 4a6a572dc1e2b54754c3a8dec38e6d2392227efc61ee710886ad9ad5729a39a5<br>export_tool_sha256: 544c9b3d451f0a6c3391102ac4031fe93bee79a0b0b9bcd6f41c893592d2422b<br>repo_commit: 80e833f44f647fe9cd8f5e99d3abf3c444de95aa<br>repo_dirty_lines: 0 |

## Result

Three separate verdicts: whether the instrumentation produced valid evidence, what the system under test did, and whether this copy is intact. The console capture is part of the first: evidence that was not kept in full cannot make an attempt valid.

| Verdict | Value |
|---|---|
| Instrumentation validity | **valid** |
| Validity note | — |
| System outcome | **pass** |
| Console capture | **complete** — every command's stdout and stderr were kept in full |
| Copy verification | **verified** — 36 file(s) copied and verified by SHA-256; 0 excluded for secrets; 0 expected source(s) missing |
| Secret scan | values of the listed variables (names only) and PEM private keys were searched in every file |
| Reason | PASS (packet section 5; decisions 3 and 4). The sequence reset itest-dup-02-q1 (seed 42, scenario smoke, 60 s, 672 messages; the same devices and sequence numbers as itest-dup-01-q1 under a new run id), never run before this battery: PROCEDURE COMPLETE, no STOP, empty stderr. Timed, controller-marker deadline: sent_valid 672, delivered_unique 672, lost 0, late_confirmations 0, duplicates 0, double_accepted 0, failed 0, warnings []; every delta line OK (twins +60/+12/+600 with last_run_id itest-dup-02-q1; /metrics accepted +672, duplicate unchanged at 672). A new run id with the same sequence numbers was accepted, not taken for a duplicate. Gate after the row: pass. With row t4-replay passed, both sub-checks of T4 passed. |
| Next action | row t5 |

## Commands

| # | Name | Exit code | Duration (s) | Console capture | Output |
|---|---|---|---|---|---|
| 1 | guest-state-before | 0 | 11.25 | complete | [stdout](console/001-guest-state-before.stdout.txt) · [stderr](console/001-guest-state-before.stderr.txt) |
| 2 | t4-reset | 0 | 366.458 | complete | [stdout](console/002-t4-reset.stdout.txt) · [stderr](console/002-t4-reset.stderr.txt) |
| 3 | guest-state-after | 0 | 14.826 | complete | [stdout](console/003-guest-state-after.stdout.txt) · [stderr](console/003-guest-state-after.stderr.txt) |
| 4 | guest-state-delta | 0 | 0.022 | complete | [stdout](console/004-guest-state-delta.stdout.txt) · [stderr](console/004-guest-state-delta.stderr.txt) |
| 5 | gate-healthy | 0 | 5.227 | complete | [stdout](console/005-gate-healthy.stdout.txt) · [stderr](console/005-gate-healthy.stderr.txt) |
| 6 | gate-units | 0 | 0.935 | complete | [stdout](console/006-gate-units.stdout.txt) · [stderr](console/006-gate-units.stderr.txt) |
| 7 | gate-tunnel-check | 0 | 0.01 | complete | [stdout](console/007-gate-tunnel-check.stdout.txt) · [stderr](console/007-gate-tunnel-check.stderr.txt) |

The full, sanitised argv of each command is in `commands.jsonl`.

## Contents

- `console/` stdout and stderr of every command; `environment/`, `tests/`, `analysis/` as named.
- `raw/` and `simulator/` hold the original artefacts byte for byte, with their own seals if they had one.
- `export_manifest.json` lists every file with its source path and SHA-256; `SHA256SUMS` seals this package.

A package here is a local copy. It is not published or admitted evidence and it is not an off-machine backup.
