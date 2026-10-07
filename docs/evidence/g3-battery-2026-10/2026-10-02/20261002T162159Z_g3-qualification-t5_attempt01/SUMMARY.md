# 20261002T162159Z_g3-qualification-t5_attempt01

**ARM64 EMULATED (QEMU/TCG)** — observations of an emulated guest, not native ARM64 performance.

| Field | Value |
|---|---|
| Purpose | official |
| Scenario | G3 qualification t5 |
| Status | finished |
| Started (UTC) | 2026-10-02T16:21:59.671837Z |
| Ended (UTC) | 2026-10-02T16:32:29.195841Z |
| Duration | 629.5 s |
| Seed | — |
| Workload | battery: G3 qualifying battery (decision packet of 2026-10-01, revision 2; authorised 2026-10-02)<br>egw_clone: /home/ruisth/egw-exec/repo<br>harness_run_id: None<br>helper_sha256: e5eba37e529a47885a8aea0e718d25ac71ce1e31a0c1a381b4520fe4c914b4fb<br>host_uptime_at_row_start_s: 5109<br>host_uptime_baseline_s: 24<br>ids_note: None<br>itest_run_ids: ['itest-dropout-01-q1']<br>row: t5<br>row_ceiling_min: 38<br>rows_manifest_sha256: cfca6a9397715d0c95881a2c824cad83a95e73727a500351920faf5552ad230c<br>runbook: {'commit': '80e833f44f647fe9cd8f5e99d3abf3c444de95aa', 'lines': 1614, 'path': 'docs/setup/qemu_integrated_gateway.md', 'sha256': 'c55a2d3b68fe7bc463d99fb2c4456e1d6462ceb7eae8e16495aaf1d1fecd74ae'}<br>session: 20261002T150133Z_guest-session_attempt08<br>session_elapsed_at_row_start_s: 5085<br>session_label: S1<br>step_files: {'t5.sh': '31572a360b1db5a2e7c39845421f80d6d66b4293d715b803b30f15de44ffe555'}<br>step_source_lines: {'t5.sh': '1407-1409'}<br>steps_script_sha256: fd652ec928ce9e9570f03fa526b83473a6706a17d81b5ade9c2dbc6b42e44ac1 |
| Identities | drivers_sha256: 4a6a572dc1e2b54754c3a8dec38e6d2392227efc61ee710886ad9ad5729a39a5<br>export_tool_sha256: 544c9b3d451f0a6c3391102ac4031fe93bee79a0b0b9bcd6f41c893592d2422b<br>repo_commit: 80e833f44f647fe9cd8f5e99d3abf3c444de95aa<br>repo_dirty_lines: 0 |

## Result

Three separate verdicts: whether the instrumentation produced valid evidence, what the system under test did, and whether this copy is intact. The console capture is part of the first: evidence that was not kept in full cannot make an attempt valid.

| Verdict | Value |
|---|---|
| Instrumentation validity | **valid** |
| Validity note | — |
| System outcome | **pass** |
| Console capture | **complete** — every command's stdout and stderr were kept in full |
| Copy verification | **verified** — 39 file(s) copied and verified by SHA-256; 0 excluded for secrets; 0 expected source(s) missing |
| Secret scan | values of the listed variables (names only) and PEM private keys were searched in every file |
| Reason | PASS (packet section 5; decision 3, timed), with two points stated for review. itest-dropout-01-q1 (seed 42, scenario dropout-reconnect, 180 s, 2016 messages): PROCEDURE COMPLETE, no STOP, empty stderr. The fault was delivered: dropout_disconnects 3, buffered_dropout 165 (simulator stderr and its manifest totals, which also carries the dropout scope note). Timed, controller-marker deadline: sent_valid 2016, delivered_unique 2016, lost 0, late_confirmations 0, duplicates 0, double_accepted 0, failed 0; latency p95 about 6.6 s, max about 7.4 s (ARM64 emulated, informational); every delta line OK (twins +180/+36/+1800; /metrics accepted +2016). The broker log bounded to this test was read (outside 0, unstamped 0, excluded_read_rc 0,0) and its excerpt holds 8 lines of the client egw-simulator-itest-dropout-01-q1: 4 'New client connected' lines and 4 'Client ... disconnected' lines. Gate after the row: pass. POINT 1, the Expected wording 'N+1 connections and N disconnections' (marked UNVERIFIED in the runbook): with N = 3 the log shows N+1 = 4 connections, the 3 disconnections of the dropout windows (16:25:04, 16:25:42, 16:26:18Z, each followed by a new connection) and one more disconnection line at 16:27:09Z, the client's own end when the simulator finished; the bounded read is taken after the run, so that last line is always inside it. I read the item as met (the three dropout disconnections and the four connections are shown); read literally, the count of disconnection lines is N+1, not N. POINT 2, the check's one warning: 'dropout run without simulator-manifest totals (logs/simulator/.../manifest.json) ... the C10 acceptance criterion fails for this run'. It concerns the campaign criterion C10 and the harness layout, which an ad-hoc run does not have; the totals themselves are in this run's own manifest and stderr (3 and 165) and in the reconcile's sim_totals. It is not an item of test 5's Expected list. |
| Next action | close S1; the two stated points go to the Project Manager's review in the S1 result note |

## Commands

| # | Name | Exit code | Duration (s) | Console capture | Output |
|---|---|---|---|---|---|
| 1 | guest-state-before | 0 | 13.157 | complete | [stdout](console/001-guest-state-before.stdout.txt) · [stderr](console/001-guest-state-before.stderr.txt) |
| 2 | t5 | 0 | 489.772 | complete | [stdout](console/002-t5.stdout.txt) · [stderr](console/002-t5.stderr.txt) |
| 3 | guest-state-after | 0 | 11.221 | complete | [stdout](console/003-guest-state-after.stdout.txt) · [stderr](console/003-guest-state-after.stderr.txt) |
| 4 | guest-state-delta | 0 | 0.023 | complete | [stdout](console/004-guest-state-delta.stdout.txt) · [stderr](console/004-guest-state-delta.stderr.txt) |
| 5 | gate-healthy | 0 | 6.752 | complete | [stdout](console/005-gate-healthy.stdout.txt) · [stderr](console/005-gate-healthy.stderr.txt) |
| 6 | gate-units | 0 | 0.816 | complete | [stdout](console/006-gate-units.stdout.txt) · [stderr](console/006-gate-units.stderr.txt) |
| 7 | gate-tunnel-check | 0 | 0.009 | complete | [stdout](console/007-gate-tunnel-check.stdout.txt) · [stderr](console/007-gate-tunnel-check.stderr.txt) |

The full, sanitised argv of each command is in `commands.jsonl`.

## Contents

- `console/` stdout and stderr of every command; `environment/`, `tests/`, `analysis/` as named.
- `raw/` and `simulator/` hold the original artefacts byte for byte, with their own seals if they had one.
- `export_manifest.json` lists every file with its source path and SHA-256; `SHA256SUMS` seals this package.

A package here is a local copy. It is not published or admitted evidence and it is not an off-machine backup.
