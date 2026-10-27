# 20261003T132936Z_g3-qualification-t6_attempt01

**ARM64 EMULATED (QEMU/TCG)** — observations of an emulated guest, not native ARM64 performance.

| Field | Value |
|---|---|
| Purpose | official |
| Scenario | G3 qualification t6 |
| Status | failed |
| Started (UTC) | 2026-10-03T13:29:36.679048Z |
| Ended (UTC) | 2026-10-03T13:51:04.173970Z |
| Duration | 1287.5 s |
| Seed | — |
| Workload | battery: G3 qualifying battery (decision packet of 2026-10-01, revision 2; authorised 2026-10-02)<br>egw_clone: /home/ruisth/egw-exec/repo<br>harness_run_id: controller_restart-r03<br>helper_sha256: e5eba37e529a47885a8aea0e718d25ac71ce1e31a0c1a381b4520fe4c914b4fb<br>host_uptime_at_row_start_s: 439<br>host_uptime_baseline_s: 25<br>ids_note: None<br>itest_run_ids: []<br>row: t6<br>row_ceiling_min: 47<br>rows_manifest_sha256: cfca6a9397715d0c95881a2c824cad83a95e73727a500351920faf5552ad230c<br>runbook: {'commit': '80e833f44f647fe9cd8f5e99d3abf3c444de95aa', 'lines': 1614, 'path': 'docs/setup/qemu_integrated_gateway.md', 'sha256': 'c55a2d3b68fe7bc463d99fb2c4456e1d6462ceb7eae8e16495aaf1d1fecd74ae'}<br>session: 20261003T132249Z_guest-session_attempt09<br>session_elapsed_at_row_start_s: 414<br>session_label: S2<br>step_files: {'t6.sh': 'ebc9700c8968b633990e0a198027bbfb5d6a246e3828e696cf8a5467b36d3400'}<br>step_source_lines: {'t6.sh': '1421-1427'}<br>steps_script_sha256: fd652ec928ce9e9570f03fa526b83473a6706a17d81b5ade9c2dbc6b42e44ac1 |
| Identities | drivers_sha256: 4a6a572dc1e2b54754c3a8dec38e6d2392227efc61ee710886ad9ad5729a39a5<br>export_tool_sha256: 544c9b3d451f0a6c3391102ac4031fe93bee79a0b0b9bcd6f41c893592d2422b<br>repo_commit: 80e833f44f647fe9cd8f5e99d3abf3c444de95aa<br>repo_dirty_lines: 0 |

## Result

Three separate verdicts: whether the instrumentation produced valid evidence, what the system under test did, and whether this copy is intact. The console capture is part of the first: evidence that was not kept in full cannot make an attempt valid.

| Verdict | Value |
|---|---|
| Instrumentation validity | **invalid** |
| Validity note | — |
| System outcome | **unknown** |
| Console capture | **complete** — every command's stdout and stderr were kept in full |
| Copy verification | **verified** — 93 file(s) copied and verified by SHA-256; 0 excluded for secrets; 0 expected source(s) missing |
| Secret scan | values of the listed variables (names only) and PEM private keys were searched in every file |
| Reason | INVALID INSTRUMENTATION (packet section 5, T6 row: resources.csv rejected, HR=1 with an instrumentation reason). Plan entry controller_restart-r03 (seed 2189910495, 600 s at 11.2 msg/s, compose restart of the controller at 300 s), fresh (F6 fresh), the configuration identity written, the recorder ready at the guest's T0. The harness ran to completion and exited 1: the SUT collector's file was REJECTED under the adopted rule 1a, so the run is marked invalid (no SUT resources; resources.csv missing) and is NOT sealed. The proved-down interval itself was established as the rule requires (restart exit 0; capture complete with one die at 13:37:14.06Z and one start at 13:37:18.76Z of egw-controller-1; StartedAt read and matching; interval 4.70 s, not capped; edge gaps 3.0 s before and 1.0 s after, both within 5 s), but the collector wrote two rows of egw-controller-1 inside it: one stamped 13:37:17Z (cpu 0.00, mem 2.7 MB: a row between the die and the start) and one stamped 13:37:18Z (in the second of the start, less than one sampling interval after it); the rule rejects such rows whatever their values, and the whole file with them. Everything else of the row's chain worked: the restart-evidence hooks (before and after twin snapshots, a quiet drain of 13:43:10-13:48:20Z, the post-drain copy), the three SUT fetches and the StartedAt fetch ended 0, the capture is complete, the recorder unit was inactive before its cleanup, and the gate after the row passed (the controller restarted in place as expected; no OOM; six services healthy). The delta line and the C12 reading did not run (T6=stop), as the runbook orders. OBSERVED ON THIS INVALID RUN, REPORTED ONLY, NOT QUALIFYING EVIDENCE: per_run.csv sent_valid 6720, delivered_unique 4718, lost 2002 (82 late), double_accepted 0; restart downtime evidenced; endpoint recovery 11.9 s and functional recovery 4.75 s after the restart (within the 120 s bound); 17 failed /metrics polls of the normal sampler during the restart. Had the run been valid, lost 2002 would have failed C12's zero-lost obligation (decision 3), the same throughput finding as nominal-r02 (S1 row 2). G3 is not met on T6 by this run; a repeat is a new decision, not taken here. For the Project Manager: under rule 1a as adopted, a collector row of the restarted container inside the proved-down interval (here the new instance's near-empty cgroup, 1.7 s before Docker recorded its start) invalidates the harness run; whether that is the intended reading is a decision, not a correction. |
| Next action | row t7-mongo (the row's gate passed and no halt condition of packet section 4 holds; T6 stays invalid) |

## Commands

| # | Name | Exit code | Duration (s) | Console capture | Output |
|---|---|---|---|---|---|
| 1 | guest-state-before | 0 | 11.879 | complete | [stdout](console/001-guest-state-before.stdout.txt) · [stderr](console/001-guest-state-before.stderr.txt) |
| 2 | snapshot-before | 0 | 0.013 | complete | [stdout](console/002-snapshot-before.stdout.txt) · [stderr](console/002-snapshot-before.stderr.txt) |
| 3 | t6 | 0 | 1146.706 | complete | [stdout](console/003-t6.stdout.txt) · [stderr](console/003-t6.stderr.txt) |
| 4 | snapshot-after | 0 | 0.008 | complete | [stdout](console/004-snapshot-after.stdout.txt) · [stderr](console/004-snapshot-after.stderr.txt) |
| 5 | guest-state-after | 0 | 11.478 | complete | [stdout](console/005-guest-state-after.stdout.txt) · [stderr](console/005-guest-state-after.stderr.txt) |
| 6 | guest-state-delta | 0 | 0.03 | complete | [stdout](console/006-guest-state-delta.stdout.txt) · [stderr](console/006-guest-state-delta.stderr.txt) |
| 7 | gate-healthy | 0 | 4.678 | complete | [stdout](console/007-gate-healthy.stdout.txt) · [stderr](console/007-gate-healthy.stderr.txt) |
| 8 | gate-units | 0 | 1.211 | complete | [stdout](console/008-gate-units.stdout.txt) · [stderr](console/008-gate-units.stderr.txt) |
| 9 | gate-tunnel-check | 0 | 0.01 | complete | [stdout](console/009-gate-tunnel-check.stdout.txt) · [stderr](console/009-gate-tunnel-check.stderr.txt) |

The full, sanitised argv of each command is in `commands.jsonl`.

## Contents

- `console/` stdout and stderr of every command; `environment/`, `tests/`, `analysis/` as named.
- `raw/` and `simulator/` hold the original artefacts byte for byte, with their own seals if they had one.
- `export_manifest.json` lists every file with its source path and SHA-256; `SHA256SUMS` seals this package.

A package here is a local copy. It is not published or admitted evidence and it is not an off-machine backup.
