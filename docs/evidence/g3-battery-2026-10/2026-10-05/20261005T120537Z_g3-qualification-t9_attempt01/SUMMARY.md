# 20261005T120537Z_g3-qualification-t9_attempt01

**ARM64 EMULATED (QEMU/TCG)** — observations of an emulated guest, not native ARM64 performance.

| Field | Value |
|---|---|
| Purpose | official |
| Scenario | G3 qualification t9 |
| Status | finished |
| Started (UTC) | 2026-10-05T12:05:38.277090Z |
| Ended (UTC) | 2026-10-05T12:11:33.098007Z |
| Duration | 354.8 s |
| Seed | — |
| Workload | battery: G3 qualification, session S3 (second opening): tests 8 and 9 only (request of 2026-10-04; decision summary output_test/decisions/2026-10-04_g3-t8-t9-s3-decision-summary.md; authorisation of 2026-10-05 with the prospective exception for collector-duration, output_test/decisions/2026-10-05_g3-s3b-exception-authorisation.md)<br>egw_clone: /home/ruisth/egw-exec/repo<br>harness_run_id: None<br>helper_sha256: e5eba37e529a47885a8aea0e718d25ac71ce1e31a0c1a381b4520fe4c914b4fb<br>host_uptime_at_row_start_s: 2654<br>host_uptime_baseline_s: 1331<br>ids_note: (d)+(e) use itest-acl-<UTC stamp>, taken by the row itself (see its console)<br>itest_run_ids: ['itest-tls-wrongca-q2', 'itest-auth-wrongpw-q2', 'itest-notls-q2']<br>row: t9<br>row_ceiling_min: 25<br>rows_manifest_sha256: 678b92031e09213780bc3790be1473358746693fc1d86088891ff2697f340c5d<br>runbook: {'commit': '8e492613d36490a560ae56beabd6d5c2c01a8696', 'lines': 1623, 'path': 'docs/setup/qemu_integrated_gateway.md', 'sha256': '4acf8de679d26024dd463dd8c096a5c3e66b7ab5ec5a397f1a7bf08768f2a9db'}<br>session: 20261005T114428Z_guest-session_attempt11<br>session_elapsed_at_row_start_s: 1323<br>session_label: S3<br>step_files: {'t9-a.sh': '34be9077366b587ae976db89e7aaaeda2bcdbcf8d3976af8254d5a5219169dac', 't9-b.sh': '29e7e98099e9bb30c58c4b141b87b4bf886ccd082a42da31a0c3b8656a4c4d5b', 't9-c.sh': 'e95f9f153a766f0ab0f21fefb4b93e0893578be80d863b411c1dfc1f64fbbf43', 't9-de.sh': '4ad835244e065df402034f3f552938ce2e7b7c50a43f776db4b4c06078c2b6ae', 't9-exposure.sh': 'ec18b22a643203a1c2d9bc9a9519b5b4a6f69de65df9944d832f09744428fe9c'}<br>step_source_lines: {'t9-a.sh': '1509-1510', 't9-b.sh': '1511-1524', 't9-c.sh': '1525-1527', 't9-de.sh': '1528-1534', 't9-exposure.sh': 'prose-only, runbook line 1537'}<br>steps_script_sha256: 42de225aedfd25fa0f4975276bf2880e146c2ad66a4624f811487ba61ea0f034 |
| Identities | drivers_sha256: 4a6a572dc1e2b54754c3a8dec38e6d2392227efc61ee710886ad9ad5729a39a5<br>export_tool_sha256: 544c9b3d451f0a6c3391102ac4031fe93bee79a0b0b9bcd6f41c893592d2422b<br>repo_commit: 8e492613d36490a560ae56beabd6d5c2c01a8696<br>repo_dirty_lines: 0 |

## Result

Three separate verdicts: whether the instrumentation produced valid evidence, what the system under test did, and whether this copy is intact. The console capture is part of the first: evidence that was not kept in full cannot make an attempt valid.

| Verdict | Value |
|---|---|
| Instrumentation validity | **valid** |
| Validity note | — |
| System outcome | **pass** |
| Console capture | **complete** — every command's stdout and stderr were kept in full |
| Copy verification | **verified** — 69 file(s) copied and verified by SHA-256; 0 excluded for secrets; 0 expected source(s) missing |
| Secret scan | values of the listed variables (names only) and PEM private keys were searched in every file |
| Reason | Every Expected item of test 9 met: (a) itest-tls-wrongca-q2 exit 1, CERTIFICATE_VERIFY_FAILED; (b) itest-auth-wrongpw-q2 exit 1 after the 15 s wait, the broker log bounded to (b) shows Client egw-simulator-itest-auth-wrongpw-q2 disconnected, not authorised; (c) itest-notls-q2 exit 1, the bounded log shows SSL wrong version number; (d) probe exit 0, verdict PASS, unauthorised subscriber 0 deliveries, changed fields [], controller untouched; (e) anonymous refused rc 5, one refusal line, anon.out 0 bytes, not accepted in the broker log; exposure: root ssh refused (publickey), QEMU forwards only 127.0.0.1:2222 and 127.0.0.1:8883 (8000/8080 are the project tunnel), guest controller 127.0.0.1:8000, gateway 127.0.0.1:8080, mongodb no published port; gate pass with the guest state compared (0 faults, 0 problems). Observation: the broker container healthcheck appears as egw-healthcheck disconnected, not authorised in the bounded logs. |
| Next action | close the session (last row of S3) |

## Commands

| # | Name | Exit code | Duration (s) | Console capture | Output |
|---|---|---|---|---|---|
| 1 | guest-state-before | 0 | 13.821 | complete | [stdout](console/001-guest-state-before.stdout.txt) · [stderr](console/001-guest-state-before.stderr.txt) |
| 2 | t9-a | 0 | 0.355 | complete | [stdout](console/002-t9-a.stdout.txt) · [stderr](console/002-t9-a.stderr.txt) |
| 3 | t9-b | 0 | 25.683 | complete | [stdout](console/003-t9-b.stdout.txt) · [stderr](console/003-t9-b.stderr.txt) |
| 4 | t9-c | 0 | 24.242 | complete | [stdout](console/004-t9-c.stdout.txt) · [stderr](console/004-t9-c.stderr.txt) |
| 5 | t9-de | 0 | 228.216 | complete | [stdout](console/005-t9-de.stdout.txt) · [stderr](console/005-t9-de.stderr.txt) |
| 6 | t9-exposure | 0 | 1.818 | complete | [stdout](console/006-t9-exposure.stdout.txt) · [stderr](console/006-t9-exposure.stderr.txt) |
| 7 | guest-state-after | 0 | 9.982 | complete | [stdout](console/007-guest-state-after.stdout.txt) · [stderr](console/007-guest-state-after.stderr.txt) |
| 8 | guest-state-delta | 0 | 0.025 | complete | [stdout](console/008-guest-state-delta.stdout.txt) · [stderr](console/008-guest-state-delta.stderr.txt) |
| 9 | gate-healthy | 0 | 7.294 | complete | [stdout](console/009-gate-healthy.stdout.txt) · [stderr](console/009-gate-healthy.stderr.txt) |
| 10 | gate-units | 0 | 1.003 | complete | [stdout](console/010-gate-units.stdout.txt) · [stderr](console/010-gate-units.stderr.txt) |
| 11 | gate-tunnel-check | 0 | 0.009 | complete | [stdout](console/011-gate-tunnel-check.stdout.txt) · [stderr](console/011-gate-tunnel-check.stderr.txt) |

The full, sanitised argv of each command is in `commands.jsonl`.

## Contents

- `console/` stdout and stderr of every command; `environment/`, `tests/`, `analysis/` as named.
- `raw/` and `simulator/` hold the original artefacts byte for byte, with their own seals if they had one.
- `export_manifest.json` lists every file with its source path and SHA-256; `SHA256SUMS` seals this package.

A package here is a local copy. It is not published or admitted evidence and it is not an off-machine backup.
