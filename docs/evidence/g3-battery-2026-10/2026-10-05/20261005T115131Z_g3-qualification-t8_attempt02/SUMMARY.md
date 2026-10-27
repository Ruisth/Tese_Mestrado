# 20261005T115131Z_g3-qualification-t8_attempt02

**ARM64 EMULATED (QEMU/TCG)** — observations of an emulated guest, not native ARM64 performance.

| Field | Value |
|---|---|
| Purpose | official |
| Scenario | G3 qualification t8 |
| Status | finished |
| Started (UTC) | 2026-10-05T11:51:30.184162Z |
| Ended (UTC) | 2026-10-05T12:05:09.388177Z |
| Duration | 819.2 s |
| Seed | — |
| Workload | battery: G3 qualification, session S3 (second opening): tests 8 and 9 only (request of 2026-10-04; decision summary output_test/decisions/2026-10-04_g3-t8-t9-s3-decision-summary.md; authorisation of 2026-10-05 with the prospective exception for collector-duration, output_test/decisions/2026-10-05_g3-s3b-exception-authorisation.md)<br>egw_clone: /home/ruisth/egw-exec/repo<br>harness_run_id: None<br>helper_sha256: e5eba37e529a47885a8aea0e718d25ac71ce1e31a0c1a381b4520fe4c914b4fb<br>host_uptime_at_row_start_s: 1770<br>host_uptime_baseline_s: 1331<br>ids_note: itest-reboot-q2 is the prefix of the reboot snapshots, of the boot id file and of the pre-reboot container set, not a run id<br>itest_run_ids: ['itest-post-reboot-01-q2']<br>row: t8<br>row_ceiling_min: 135<br>rows_manifest_sha256: 678b92031e09213780bc3790be1473358746693fc1d86088891ff2697f340c5d<br>runbook: {'commit': '8e492613d36490a560ae56beabd6d5c2c01a8696', 'lines': 1623, 'path': 'docs/setup/qemu_integrated_gateway.md', 'sha256': '4acf8de679d26024dd463dd8c096a5c3e66b7ab5ec5a397f1a7bf08768f2a9db'}<br>session: 20261005T114428Z_guest-session_attempt11<br>session_elapsed_at_row_start_s: 439<br>session_label: S3<br>step_files: {'t8-a-reboot.sh': '00ff23db999e4ad5460c93010721e393d60c34fd4e596666cef9fd35fda8aa43', 't8-b-wait-boot-id.sh': 'f38f7fad40980359b6f3ea59142f8a2f0199a3d80a942e7b36826ddfdd9cade7', 't8-c-unaided.sh': 'df4ff611057b4f5a7df40b8b8f0fb2818eed43011c2c10109d7cc0881a7da39d', 't8-d-tunnel.sh': 'dbffd3defbdfbbadce3218bde6c4562d77b0e1813bd70a0562e6f921844809f5', 't8-e-state.sh': '00d100f7232b93fe5e425f603b7915514b24e67258b692603fa335b99293f593', 't8-f-smoke.sh': '874ef658228e30e19b561a6f5306b698e0665f3701c2fb28ab0d13feddb6dc76'}<br>step_source_lines: {'t8-a-reboot.sh': '1486-1495', 't8-b-wait-boot-id.sh': '1496', 't8-c-unaided.sh': '1497', 't8-d-tunnel.sh': '1498', 't8-e-state.sh': '1499', 't8-f-smoke.sh': '1500'}<br>steps_script_sha256: 42de225aedfd25fa0f4975276bf2880e146c2ad66a4624f811487ba61ea0f034 |
| Identities | drivers_sha256: 4a6a572dc1e2b54754c3a8dec38e6d2392227efc61ee710886ad9ad5729a39a5<br>export_tool_sha256: 544c9b3d451f0a6c3391102ac4031fe93bee79a0b0b9bcd6f41c893592d2422b<br>repo_commit: 8e492613d36490a560ae56beabd6d5c2c01a8696<br>repo_dirty_lines: 0 |

## Result

Three separate verdicts: whether the instrumentation produced valid evidence, what the system under test did, and whether this copy is intact. The console capture is part of the first: evidence that was not kept in full cannot make an attempt valid.

| Verdict | Value |
|---|---|
| Instrumentation validity | **valid** |
| Validity note | — |
| System outcome | **pass** |
| Console capture | **complete** — every command's stdout and stderr were kept in full |
| Copy verification | **verified** — 83 file(s) copied and verified by SHA-256; 0 excluded for secrets; 0 expected source(s) missing |
| Secret scan | values of the listed variables (names only) and PEM private keys were searched in every file |
| Reason | Every Expected item of test 8 met on the corrected procedure: reboot shown inside the same QEMU process (boot id fc85c700 -> 0a780c6e, guest answering 27 s after the reboot command, no -no-reboot on the command line); the six container objects listed running again unaided (read 2), no start by hand; persistence shown (35 event directories intact, /var/lib/docker on /dev/vdb); tunnel reopened by line d; stack ready, the three seed-42 twins identical (exists true), controller started_at changed; post-reboot smoke itest-post-reboot-01-q2: 336 sent, lost 0, late_confirmations 0, every delta OK, PROCEDURE COMPLETE (p95 57.6 s, max 58.8 s against the 60 s deadline); no OOM line in the previous boot, restarts 0, oomkilled false; gate pass. No STOP line. |
| Next action | row t9 (T8 classified pass with its gate passed); the timed margin of the smoke (p95 57.6 s of 60 s) is recorded as an observation |

## Commands

| # | Name | Exit code | Duration (s) | Console capture | Output |
|---|---|---|---|---|---|
| 1 | guest-state-before | 0 | 14.839 | complete | [stdout](console/001-guest-state-before.stdout.txt) · [stderr](console/001-guest-state-before.stderr.txt) |
| 2 | t8-qemu-before | 0 | 0.015 | complete | [stdout](console/002-t8-qemu-before.stdout.txt) · [stderr](console/002-t8-qemu-before.stderr.txt) |
| 3 | t8-a-reboot | 0 | 148.095 | complete | [stdout](console/003-t8-a-reboot.stdout.txt) · [stderr](console/003-t8-a-reboot.stderr.txt) |
| 4 | t8-wait-ssh | 255 | 0.472 | complete | [stdout](console/004-t8-wait-ssh.stdout.txt) · [stderr](console/004-t8-wait-ssh.stderr.txt) |
| 5 | t8-wait-ssh | 255 | 6.174 | complete | [stdout](console/005-t8-wait-ssh.stdout.txt) · [stderr](console/005-t8-wait-ssh.stderr.txt) |
| 6 | t8-wait-ssh | 0 | 0.766 | complete | [stdout](console/006-t8-wait-ssh.stdout.txt) · [stderr](console/006-t8-wait-ssh.stderr.txt) |
| 7 | t8-qemu-after | 0 | 0.01 | complete | [stdout](console/007-t8-qemu-after.stdout.txt) · [stderr](console/007-t8-qemu-after.stderr.txt) |
| 8 | t8-b-wait-boot-id | 0 | 1.358 | complete | [stdout](console/008-t8-b-wait-boot-id.stdout.txt) · [stderr](console/008-t8-b-wait-boot-id.stderr.txt) |
| 9 | t8-c-unaided | 0 | 41.653 | complete | [stdout](console/009-t8-c-unaided.stdout.txt) · [stderr](console/009-t8-c-unaided.stderr.txt) |
| 10 | t8-d-tunnel | 0 | 0.81 | complete | [stdout](console/010-t8-d-tunnel.stdout.txt) · [stderr](console/010-t8-d-tunnel.stderr.txt) |
| 11 | t8-tunnel-check | 0 | 0.005 | complete | [stdout](console/011-t8-tunnel-check.stdout.txt) · [stderr](console/011-t8-tunnel-check.stderr.txt) |
| 12 | t8-e-state | 0 | 173.984 | complete | [stdout](console/012-t8-e-state.stdout.txt) · [stderr](console/012-t8-e-state.stderr.txt) |
| 13 | t8-f-smoke | 0 | 343.723 | complete | [stdout](console/013-t8-f-smoke.stdout.txt) · [stderr](console/013-t8-f-smoke.stderr.txt) |
| 14 | t8-previous-boot-journal | 0 | 4.097 | complete | [stdout](console/014-t8-previous-boot-journal.stdout.txt) · [stderr](console/014-t8-previous-boot-journal.stderr.txt) |
| 15 | t8-previous-boot-oom | 0 | 4.769 | complete | [stdout](console/015-t8-previous-boot-oom.stdout.txt) · [stderr](console/015-t8-previous-boot-oom.stderr.txt) |
| 16 | guest-state-after | 0 | 13.146 | complete | [stdout](console/016-guest-state-after.stdout.txt) · [stderr](console/016-guest-state-after.stderr.txt) |
| 17 | gate-healthy | 0 | 4.0 | complete | [stdout](console/017-gate-healthy.stdout.txt) · [stderr](console/017-gate-healthy.stderr.txt) |
| 18 | gate-units | 0 | 1.0 | complete | [stdout](console/018-gate-units.stdout.txt) · [stderr](console/018-gate-units.stderr.txt) |
| 19 | gate-tunnel-check | 0 | 0.009 | complete | [stdout](console/019-gate-tunnel-check.stdout.txt) · [stderr](console/019-gate-tunnel-check.stderr.txt) |

The full, sanitised argv of each command is in `commands.jsonl`.

## Contents

- `console/` stdout and stderr of every command; `environment/`, `tests/`, `analysis/` as named.
- `raw/` and `simulator/` hold the original artefacts byte for byte, with their own seals if they had one.
- `export_manifest.json` lists every file with its source path and SHA-256; `SHA256SUMS` seals this package.

A package here is a local copy. It is not published or admitted evidence and it is not an off-machine backup.
