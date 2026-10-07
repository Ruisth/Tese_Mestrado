# 20261002T152710Z_g3-qualification-t1-harness_attempt01

**ARM64 EMULATED (QEMU/TCG)** — observations of an emulated guest, not native ARM64 performance.

| Field | Value |
|---|---|
| Purpose | official |
| Scenario | G3 qualification t1-harness |
| Status | finished |
| Started (UTC) | 2026-10-02T15:27:10.850326Z |
| Ended (UTC) | 2026-10-02T15:43:48.590351Z |
| Duration | 997.7 s |
| Seed | — |
| Workload | battery: G3 qualifying battery (decision packet of 2026-10-01, revision 2; authorised 2026-10-02)<br>egw_clone: /home/ruisth/egw-exec/repo<br>harness_run_id: nominal-r02<br>helper_sha256: e5eba37e529a47885a8aea0e718d25ac71ce1e31a0c1a381b4520fe4c914b4fb<br>host_uptime_at_row_start_s: 1635<br>host_uptime_baseline_s: 24<br>ids_note: None<br>itest_run_ids: []<br>row: t1-harness<br>row_ceiling_min: 35<br>rows_manifest_sha256: cfca6a9397715d0c95881a2c824cad83a95e73727a500351920faf5552ad230c<br>runbook: {'commit': '80e833f44f647fe9cd8f5e99d3abf3c444de95aa', 'lines': 1614, 'path': 'docs/setup/qemu_integrated_gateway.md', 'sha256': 'c55a2d3b68fe7bc463d99fb2c4456e1d6462ceb7eae8e16495aaf1d1fecd74ae'}<br>session: 20261002T150133Z_guest-session_attempt08<br>session_elapsed_at_row_start_s: 1611<br>session_label: S1<br>step_files: {'t1-harness-analyze.sh': 'd0fb59187c8fad3626c04c15b703911e599586a20231ba7c27849209b6e647c8', 't1-harness.sh': 'd6194365dfac0f3eac539d198777452872c01f1a276c77b866ff1b267f09d39c'}<br>step_source_lines: {'t1-harness-analyze.sh': 'prose-only, runbook line 1320', 't1-harness.sh': '1310-1313'}<br>steps_script_sha256: fd652ec928ce9e9570f03fa526b83473a6706a17d81b5ade9c2dbc6b42e44ac1 |
| Identities | drivers_sha256: 4a6a572dc1e2b54754c3a8dec38e6d2392227efc61ee710886ad9ad5729a39a5<br>export_tool_sha256: 544c9b3d451f0a6c3391102ac4031fe93bee79a0b0b9bcd6f41c893592d2422b<br>repo_commit: 80e833f44f647fe9cd8f5e99d3abf3c444de95aa<br>repo_dirty_lines: 0 |

## Result

Three separate verdicts: whether the instrumentation produced valid evidence, what the system under test did, and whether this copy is intact. The console capture is part of the first: evidence that was not kept in full cannot make an attempt valid.

| Verdict | Value |
|---|---|
| Instrumentation validity | **valid** |
| Validity note | — |
| System outcome | **pass** |
| Console capture | **complete** — every command's stdout and stderr were kept in full |
| Copy verification | **verified** — 86 file(s) copied and verified by SHA-256; 0 excluded for secrets; 0 expected source(s) missing |
| Secret scan | values of the listed variables (names only) and PEM private keys were searched in every file |
| Reason | PASS of T1's harness Expected list, the artefact chain (packet section 2 row 2; decision 1b): plan entry nominal-r02 (seed 246295039, 120 s warm-up + 600 s at 11.2 msg/s), no STOP, empty stderr. Manifest validity valid with no validity reason and no warning; the capsule sealed and its SHA256SUMS verifying (36 files); collector.problems empty; no mandatory artefact missing; resources.csv ingested from the SUT collector with 682 rows and 682 distinct instants for each of the six services (the unchanged ingest rule held); the three SUT fetches ended 0 and the Docker events capture was judged complete; the capsule's sut_environment.json is the preflight's current capture (f6a53cee..., QEMU 8.2.7 TCG, ARM64 EMULATED, shared x86-64 host). Gate after the row: pass. DELIVERY, REPORTED AS MEASURED AND NOT A CRITERION OF THIS ROW: sent_valid 6720, delivered_unique 4584, lost 2136 (late_confirmations 111 among them), double_accepted 0, deadline source controller-marker. This row is not a passed 30 s smoke, not a performance approval and not a successful nominal delivery, and it does not count towards C14; the delivery figures are a sizing finding for the pilot (the nominal rate is not served in time under TCG). |
| Next action | row t2 |

## Commands

| # | Name | Exit code | Duration (s) | Console capture | Output |
|---|---|---|---|---|---|
| 1 | guest-state-before | 0 | 13.942 | complete | [stdout](console/001-guest-state-before.stdout.txt) · [stderr](console/001-guest-state-before.stderr.txt) |
| 2 | snapshot-before | 0 | 0.013 | complete | [stdout](console/002-snapshot-before.stdout.txt) · [stderr](console/002-snapshot-before.stderr.txt) |
| 3 | t1-harness | 0 | 908.371 | complete | [stdout](console/003-t1-harness.stdout.txt) · [stderr](console/003-t1-harness.stderr.txt) |
| 4 | snapshot-after-harness | 0 | 0.006 | complete | [stdout](console/004-snapshot-after-harness.stdout.txt) · [stderr](console/004-snapshot-after-harness.stderr.txt) |
| 5 | t1-harness-analyze | 0 | 0.842 | complete | [stdout](console/005-t1-harness-analyze.stdout.txt) · [stderr](console/005-t1-harness-analyze.stderr.txt) |
| 6 | snapshot-after | 0 | 0.009 | complete | [stdout](console/006-snapshot-after.stdout.txt) · [stderr](console/006-snapshot-after.stderr.txt) |
| 7 | guest-state-after | 0 | 18.203 | complete | [stdout](console/007-guest-state-after.stdout.txt) · [stderr](console/007-guest-state-after.stderr.txt) |
| 8 | guest-state-delta | 0 | 0.022 | complete | [stdout](console/008-guest-state-delta.stdout.txt) · [stderr](console/008-guest-state-delta.stderr.txt) |
| 9 | gate-healthy | 0 | 4.613 | complete | [stdout](console/009-gate-healthy.stdout.txt) · [stderr](console/009-gate-healthy.stderr.txt) |
| 10 | gate-units | 0 | 1.023 | complete | [stdout](console/010-gate-units.stdout.txt) · [stderr](console/010-gate-units.stderr.txt) |
| 11 | gate-tunnel-check | 0 | 0.01 | complete | [stdout](console/011-gate-tunnel-check.stdout.txt) · [stderr](console/011-gate-tunnel-check.stderr.txt) |

The full, sanitised argv of each command is in `commands.jsonl`.

## Contents

- `console/` stdout and stderr of every command; `environment/`, `tests/`, `analysis/` as named.
- `raw/` and `simulator/` hold the original artefacts byte for byte, with their own seals if they had one.
- `export_manifest.json` lists every file with its source path and SHA-256; `SHA256SUMS` seals this package.

A package here is a local copy. It is not published or admitted evidence and it is not an off-machine backup.
