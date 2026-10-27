# 20261002T160154Z_g3-qualification-t4-replay_attempt01

**ARM64 EMULATED (QEMU/TCG)** — observations of an emulated guest, not native ARM64 performance.

| Field | Value |
|---|---|
| Purpose | official |
| Scenario | G3 qualification t4-replay |
| Status | finished |
| Started (UTC) | 2026-10-02T16:01:54.360139Z |
| Ended (UTC) | 2026-10-02T16:14:05.548074Z |
| Duration | 731.2 s |
| Seed | — |
| Workload | battery: G3 qualifying battery (decision packet of 2026-10-01, revision 2; authorised 2026-10-02)<br>egw_clone: /home/ruisth/egw-exec/repo<br>harness_run_id: None<br>helper_sha256: e5eba37e529a47885a8aea0e718d25ac71ce1e31a0c1a381b4520fe4c914b4fb<br>host_uptime_at_row_start_s: 3835<br>host_uptime_baseline_s: 24<br>ids_note: None<br>itest_run_ids: ['itest-dup-01-q1']<br>row: t4-replay<br>row_ceiling_min: 67<br>rows_manifest_sha256: cfca6a9397715d0c95881a2c824cad83a95e73727a500351920faf5552ad230c<br>runbook: {'commit': '80e833f44f647fe9cd8f5e99d3abf3c444de95aa', 'lines': 1614, 'path': 'docs/setup/qemu_integrated_gateway.md', 'sha256': 'c55a2d3b68fe7bc463d99fb2c4456e1d6462ceb7eae8e16495aaf1d1fecd74ae'}<br>session: 20261002T150133Z_guest-session_attempt08<br>session_elapsed_at_row_start_s: 3811<br>session_label: S1<br>step_files: {'t4-replay.sh': 'fb646091cbc47287eee6d7d960eb15eae8c390309c766dbfb8aa784d56ac2954'}<br>step_source_lines: {'t4-replay.sh': '1383-1391'}<br>steps_script_sha256: fd652ec928ce9e9570f03fa526b83473a6706a17d81b5ade9c2dbc6b42e44ac1 |
| Identities | drivers_sha256: 4a6a572dc1e2b54754c3a8dec38e6d2392227efc61ee710886ad9ad5729a39a5<br>export_tool_sha256: 544c9b3d451f0a6c3391102ac4031fe93bee79a0b0b9bcd6f41c893592d2422b<br>repo_commit: 80e833f44f647fe9cd8f5e99d3abf3c444de95aa<br>repo_dirty_lines: 0 |

## Result

Three separate verdicts: whether the instrumentation produced valid evidence, what the system under test did, and whether this copy is intact. The console capture is part of the first: evidence that was not kept in full cannot make an attempt valid.

| Verdict | Value |
|---|---|
| Instrumentation validity | **valid** |
| Validity note | — |
| System outcome | **pass** |
| Console capture | **complete** — every command's stdout and stderr were kept in full |
| Copy verification | **verified** — 43 file(s) copied and verified by SHA-256; 0 excluded for secrets; 0 expected source(s) missing |
| Secret scan | values of the listed variables (names only) and PEM private keys were searched in every file |
| Reason | PASS (packet section 5; decision 4 with PR #53 F1). itest-dup-01-q1 (seed 42, scenario smoke, 60 s, 672 messages), then the same 672 messages replayed once: both simulator runs exit 0, no STOP, empty stderr. First run: delivered_unique 672, lost 0, late_confirmations 0, every delta line OK. Replay check exit 0: one controller process between the after and replay readings (same started_at, counters non-decreasing); the after reading quiet; k = 0 reconnections (mqtt_connection 1 -> 1); duplicate_replayed 672 of 672; no replayed identity gained an accepted line; none has more than one accepted line; duplicate_redelivery 0; /metrics accepted unchanged (11693), duplicate +672, queue_depth 0. Twins identical between after and replay (three devices). Pre- and post-replay accounting UNCHANGED for sent_valid, delivered_unique, lost, late_confirmations and double_accepted (0). The log holds 672 accepted and 672 duplicate lines. Gate after the row: pass. T4 as a family also needs the sequence reset (row t4-reset). |
| Next action | row t4-reset |

## Commands

| # | Name | Exit code | Duration (s) | Console capture | Output |
|---|---|---|---|---|---|
| 1 | guest-state-before | 0 | 12.884 | complete | [stdout](console/001-guest-state-before.stdout.txt) · [stderr](console/001-guest-state-before.stderr.txt) |
| 2 | t4-replay | 0 | 674.669 | complete | [stdout](console/002-t4-replay.stdout.txt) · [stderr](console/002-t4-replay.stderr.txt) |
| 3 | guest-state-after | 0 | 10.452 | complete | [stdout](console/003-guest-state-after.stdout.txt) · [stderr](console/003-guest-state-after.stderr.txt) |
| 4 | guest-state-delta | 0 | 0.026 | complete | [stdout](console/004-guest-state-delta.stdout.txt) · [stderr](console/004-guest-state-delta.stderr.txt) |
| 5 | gate-healthy | 0 | 6.391 | complete | [stdout](console/005-gate-healthy.stdout.txt) · [stderr](console/005-gate-healthy.stderr.txt) |
| 6 | gate-units | 0 | 1.185 | complete | [stdout](console/006-gate-units.stdout.txt) · [stderr](console/006-gate-units.stderr.txt) |
| 7 | gate-tunnel-check | 0 | 0.01 | complete | [stdout](console/007-gate-tunnel-check.stdout.txt) · [stderr](console/007-gate-tunnel-check.stderr.txt) |

The full, sanitised argv of each command is in `commands.jsonl`.

## Contents

- `console/` stdout and stderr of every command; `environment/`, `tests/`, `analysis/` as named.
- `raw/` and `simulator/` hold the original artefacts byte for byte, with their own seals if they had one.
- `export_manifest.json` lists every file with its source path and SHA-256; `SHA256SUMS` seals this package.

A package here is a local copy. It is not published or admitted evidence and it is not an off-machine backup.
