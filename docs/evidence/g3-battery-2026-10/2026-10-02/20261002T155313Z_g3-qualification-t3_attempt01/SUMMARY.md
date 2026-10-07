# 20261002T155313Z_g3-qualification-t3_attempt01

**ARM64 EMULATED (QEMU/TCG)** — observations of an emulated guest, not native ARM64 performance.

| Field | Value |
|---|---|
| Purpose | official |
| Scenario | G3 qualification t3 |
| Status | finished |
| Started (UTC) | 2026-10-02T15:53:13.364816Z |
| Ended (UTC) | 2026-10-02T16:01:32.617118Z |
| Duration | 499.3 s |
| Seed | — |
| Workload | battery: G3 qualifying battery (decision packet of 2026-10-01, revision 2; authorised 2026-10-02)<br>egw_clone: /home/ruisth/egw-exec/repo<br>harness_run_id: None<br>helper_sha256: e5eba37e529a47885a8aea0e718d25ac71ce1e31a0c1a381b4520fe4c914b4fb<br>host_uptime_at_row_start_s: 3285<br>host_uptime_baseline_s: 24<br>ids_note: None<br>itest_run_ids: ['itest-invalid-01-q1']<br>row: t3<br>row_ceiling_min: 37<br>rows_manifest_sha256: cfca6a9397715d0c95881a2c824cad83a95e73727a500351920faf5552ad230c<br>runbook: {'commit': '80e833f44f647fe9cd8f5e99d3abf3c444de95aa', 'lines': 1614, 'path': 'docs/setup/qemu_integrated_gateway.md', 'sha256': 'c55a2d3b68fe7bc463d99fb2c4456e1d6462ceb7eae8e16495aaf1d1fecd74ae'}<br>session: 20261002T150133Z_guest-session_attempt08<br>session_elapsed_at_row_start_s: 3261<br>session_label: S1<br>step_files: {'t3.sh': '9731c836d334d9534109d8da738b63243c483286303016ba7df1ad42371497f6'}<br>step_source_lines: {'t3.sh': '1345-1373'}<br>steps_script_sha256: fd652ec928ce9e9570f03fa526b83473a6706a17d81b5ade9c2dbc6b42e44ac1 |
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
| Reason | PASS (packet section 5; decision 3, T3 not timed). itest-invalid-01-q1 (seed 42, scenario invalid-payload, 120 s, 1344 messages, 67 intended invalid): the run id was fresh on the host and on the guest (F3 fresh), PROCEDURE COMPLETE, no STOP, empty stderr. The copy fetched after the final drain equals the guest's log byte for byte and was kept write-once as itest-invalid-01-q1.events.post-drain.jsonl (C3 ok). Acceptance by the end of the drain: valid 1277, accepted 1277, never accepted 0 (exit 0). intended_invalid 67, rejected 67, intended_invalid accepted 0, valid rejected 0; every delta line OK (twins 114/23/1140; /metrics accepted +1277, rejected +67). The 67 rejections are in the controller log bounded to this run (lines 1449, rejected 67; first error: schema validation failed, accel_y not a number). Reported, deciding nothing for T3: lost 0, late_confirmations 0, double_accepted 0, failed 0. Gate after the row: pass. |
| Next action | row t4-replay |

## Commands

| # | Name | Exit code | Duration (s) | Console capture | Output |
|---|---|---|---|---|---|
| 1 | guest-state-before | 0 | 11.122 | complete | [stdout](console/001-guest-state-before.stdout.txt) · [stderr](console/001-guest-state-before.stderr.txt) |
| 2 | t3 | 0 | 438.423 | complete | [stdout](console/002-t3.stdout.txt) · [stderr](console/002-t3.stderr.txt) |
| 3 | guest-state-after | 0 | 11.574 | complete | [stdout](console/003-guest-state-after.stdout.txt) · [stderr](console/003-guest-state-after.stderr.txt) |
| 4 | guest-state-delta | 0 | 0.027 | complete | [stdout](console/004-guest-state-delta.stdout.txt) · [stderr](console/004-guest-state-delta.stderr.txt) |
| 5 | gate-healthy | 0 | 6.945 | complete | [stdout](console/005-gate-healthy.stdout.txt) · [stderr](console/005-gate-healthy.stderr.txt) |
| 6 | gate-units | 0 | 0.974 | complete | [stdout](console/006-gate-units.stdout.txt) · [stderr](console/006-gate-units.stderr.txt) |
| 7 | gate-tunnel-check | 0 | 0.01 | complete | [stdout](console/007-gate-tunnel-check.stdout.txt) · [stderr](console/007-gate-tunnel-check.stderr.txt) |

The full, sanitised argv of each command is in `commands.jsonl`.

## Contents

- `console/` stdout and stderr of every command; `environment/`, `tests/`, `analysis/` as named.
- `raw/` and `simulator/` hold the original artefacts byte for byte, with their own seals if they had one.
- `export_manifest.json` lists every file with its source path and SHA-256; `SHA256SUMS` seals this package.

A package here is a local copy. It is not published or admitted evidence and it is not an off-machine backup.
