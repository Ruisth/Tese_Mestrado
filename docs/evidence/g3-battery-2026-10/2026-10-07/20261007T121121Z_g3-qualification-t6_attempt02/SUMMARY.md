# 20261007T121121Z_g3-qualification-t6_attempt02

**ARM64 EMULATED (QEMU/TCG)** — observations of an emulated guest, not native ARM64 performance.

| Field | Value |
|---|---|
| Purpose | official |
| Scenario | G3 qualification t6 |
| Status | finished |
| Started (UTC) | 2026-10-07T12:11:21.389364Z |
| Ended (UTC) | 2026-10-07T12:33:23.430845Z |
| Duration | 1322.0 s |
| Seed | — |
| Workload | battery: G3 qualification, session S4: test 6 only (controller_restart-r04; request of 2026-10-05, output_test/decisions/2026-10-05_g3-t6-session-request.md; criterion amended on 2026-10-05, LOG #C052; transition rule 1a-option-a-2026-10-05, LOG #C053)<br>egw_clone: /home/ruisth/egw-exec/repo<br>harness_run_id: controller_restart-r04<br>helper_sha256: e5eba37e529a47885a8aea0e718d25ac71ce1e31a0c1a381b4520fe4c914b4fb<br>host_uptime_at_row_start_s: 3746<br>host_uptime_baseline_s: 3318<br>ids_note: None<br>itest_run_ids: []<br>row: t6<br>row_ceiling_min: 47<br>rows_manifest_sha256: 7d2a0f0d940c1d2f978a33693869fe4372cf7c63c4592d3d911d1440bdb8fb47<br>runbook: {'commit': '1fd9792bb76f02c6948f33887207dba4837202db', 'lines': 1624, 'path': 'docs/setup/qemu_integrated_gateway.md', 'sha256': '317165936abed4f3823f53b67b7ac76bafa442cfa1820d4b96479392b280cf0f'}<br>session: 20261007T120357Z_guest-session_attempt12<br>session_elapsed_at_row_start_s: 428<br>session_label: S4<br>step_files: {'t6.sh': 'ec8ac010d79ba87ff7f2b4c828c4fbe85c7f0c765d6869670552a6c1ba326377'}<br>step_source_lines: {'t6.sh': '1421-1428'}<br>steps_script_sha256: 7a63b361af2f25bd8ab81101ca10ec79fcb05a6e6f0cf0a70bc2ec63f3f8425c |
| Identities | drivers_sha256: 2c209b09faf58bb4986cf39b7bb1f13936fae8e94c3b5eb3faf84f722bfe44ed<br>export_tool_sha256: 544c9b3d451f0a6c3391102ac4031fe93bee79a0b0b9bcd6f41c893592d2422b<br>repo_commit: 1fd9792bb76f02c6948f33887207dba4837202db<br>repo_dirty_lines: 0 |

## Result

Three separate verdicts: whether the instrumentation produced valid evidence, what the system under test did, and whether this copy is intact. The console capture is part of the first: evidence that was not kept in full cannot make an attempt valid.

| Verdict | Value |
|---|---|
| Instrumentation validity | **valid** |
| Validity note | — |
| System outcome | **pass** |
| Console capture | **complete** — every command's stdout and stderr were kept in full |
| Copy verification | **verified** — 95 file(s) copied and verified by SHA-256; 0 excluded for secrets; 0 expected source(s) missing |
| Secret scan | values of the listed variables (names only) and PEM private keys were searched in every file |
| Reason | PASS under the criterion amended on 2026-10-05 (request of 2026-10-05, section 6, with the supplement of 2026-10-07). Plan entry controller_restart-r04 (seed 1715385812, 600 s at 11.2 msg/s, 6,720 messages), F6 fresh. T6=ok: harness exit 0 with the recorder cleanup done, run directory sealed (46 files, verified), drain quiet. The controller restarted once mid-run: restart record at +300 s, returncode 0; the capture shows one die and one start of egw-controller-1 (kill, stop and restart of a graceful restart beside them); the gate after shows EXPECTED-RESTART, same container, restart count unchanged, no OOM, six services healthy. Recovery: restart_metrics_endpoint_recovery_s 12.134 s (within 120 s; from the end of the restart command to the first /metrics answer); functional recovery 20.04 s (events-accepted-monotonic), reported only. delta: all three device lines OK (600, 120, 6,000 accepted); N1 report 0/0. acceptance --exactly-once: 6,720 valid messages accepted exactly once in events.post-drain.jsonl, 0 more than once, 0 never; double_accepted 0. Configuration identity equal to the packet (broker ea37827c, W 4999, Q 1000, byte limits 0, expiry 1h, sys_interval 10, not reloaded, stop grace 130s, controller image 9a293fe1 from 489bc9e, paho 2.1.0, A3 a). Transition rule 1a-option-a-2026-10-05: 2 rows admitted (12:19:26Z, 12:19:27Z); proved-down interval applied, 0 rows rejected. Reported beside the result, deciding nothing (sizing finding): lost 2,153 and late_confirmations 67 against the controller marker plus 60 s. |
| Next action | close (the recorded compose stop -t 130, then the frozen close driver); the result note in output_test/decisions; no G3 claim: the evidence is consolidated and the closing opinion follows separately. |

## Commands

| # | Name | Exit code | Duration (s) | Console capture | Output |
|---|---|---|---|---|---|
| 1 | guest-state-before | 0 | 13.698 | complete | [stdout](console/001-guest-state-before.stdout.txt) · [stderr](console/001-guest-state-before.stderr.txt) |
| 2 | snapshot-before | 0 | 0.011 | complete | [stdout](console/002-snapshot-before.stdout.txt) · [stderr](console/002-snapshot-before.stderr.txt) |
| 3 | t6 | 0 | 1237.415 | complete | [stdout](console/003-t6.stdout.txt) · [stderr](console/003-t6.stderr.txt) |
| 4 | snapshot-after | 0 | 0.007 | complete | [stdout](console/004-snapshot-after.stdout.txt) · [stderr](console/004-snapshot-after.stderr.txt) |
| 5 | guest-state-after | 0 | 11.218 | complete | [stdout](console/005-guest-state-after.stdout.txt) · [stderr](console/005-guest-state-after.stderr.txt) |
| 6 | guest-state-delta | 0 | 0.025 | complete | [stdout](console/006-guest-state-delta.stdout.txt) · [stderr](console/006-guest-state-delta.stderr.txt) |
| 7 | gate-healthy | 0 | 5.527 | complete | [stdout](console/007-gate-healthy.stdout.txt) · [stderr](console/007-gate-healthy.stderr.txt) |
| 8 | gate-units | 0 | 0.872 | complete | [stdout](console/008-gate-units.stdout.txt) · [stderr](console/008-gate-units.stderr.txt) |
| 9 | gate-tunnel-check | 0 | 0.008 | complete | [stdout](console/009-gate-tunnel-check.stdout.txt) · [stderr](console/009-gate-tunnel-check.stderr.txt) |

The full, sanitised argv of each command is in `commands.jsonl`.

## Contents

- `console/` stdout and stderr of every command; `environment/`, `tests/`, `analysis/` as named.
- `raw/` and `simulator/` hold the original artefacts byte for byte, with their own seals if they had one.
- `export_manifest.json` lists every file with its source path and SHA-256; `SHA256SUMS` seals this package.

A package here is a local copy. It is not published or admitted evidence and it is not an off-machine backup.
