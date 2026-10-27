# 20261003T140639Z_g3-qualification-t7-ditto_attempt01

**ARM64 EMULATED (QEMU/TCG)** — observations of an emulated guest, not native ARM64 performance.

| Field | Value |
|---|---|
| Purpose | official |
| Scenario | G3 qualification t7-ditto |
| Status | finished |
| Started (UTC) | 2026-10-03T14:06:39.759133Z |
| Ended (UTC) | 2026-10-03T14:22:43.849721Z |
| Duration | 964.1 s |
| Seed | — |
| Workload | battery: G3 qualifying battery (decision packet of 2026-10-01, revision 2; authorised 2026-10-02)<br>egw_clone: /home/ruisth/egw-exec/repo<br>harness_run_id: None<br>helper_sha256: e5eba37e529a47885a8aea0e718d25ac71ce1e31a0c1a381b4520fe4c914b4fb<br>host_uptime_at_row_start_s: 2720<br>host_uptime_baseline_s: 25<br>ids_note: None<br>itest_run_ids: ['itest-ditto-fault-01-q1']<br>row: t7-ditto<br>row_ceiling_min: 41<br>rows_manifest_sha256: cfca6a9397715d0c95881a2c824cad83a95e73727a500351920faf5552ad230c<br>runbook: {'commit': '80e833f44f647fe9cd8f5e99d3abf3c444de95aa', 'lines': 1614, 'path': 'docs/setup/qemu_integrated_gateway.md', 'sha256': 'c55a2d3b68fe7bc463d99fb2c4456e1d6462ceb7eae8e16495aaf1d1fecd74ae'}<br>session: 20261003T132249Z_guest-session_attempt09<br>session_elapsed_at_row_start_s: 2695<br>session_label: S2<br>step_files: {'t7-ditto.sh': '23ea0b99fa9f3e7eccbe429e42d51a9b2c68d9cc2d0b4c641a0ab7b306cc74e0'}<br>step_source_lines: {'t7-ditto.sh': '1440-1458, 1477-1480'}<br>steps_script_sha256: fd652ec928ce9e9570f03fa526b83473a6706a17d81b5ade9c2dbc6b42e44ac1 |
| Identities | drivers_sha256: 4a6a572dc1e2b54754c3a8dec38e6d2392227efc61ee710886ad9ad5729a39a5<br>export_tool_sha256: 544c9b3d451f0a6c3391102ac4031fe93bee79a0b0b9bcd6f41c893592d2422b<br>repo_commit: 80e833f44f647fe9cd8f5e99d3abf3c444de95aa<br>repo_dirty_lines: 0 |

## Result

Three separate verdicts: whether the instrumentation produced valid evidence, what the system under test did, and whether this copy is intact. The console capture is part of the first: evidence that was not kept in full cannot make an attempt valid.

| Verdict | Value |
|---|---|
| Instrumentation validity | **valid** |
| Validity note | — |
| System outcome | **pass** |
| Console capture | **complete** — every command's stdout and stderr were kept in full |
| Copy verification | **verified** — 50 file(s) copied and verified by SHA-256; 0 excluded for secrets; 0 expected source(s) missing |
| Secret scan | values of the listed variables (names only) and PEM private keys were searched in every file |
| Reason | PASS (packet section 5; T7 not timed). itest-ditto-fault-01-q1 (seed 42, scenario nominal, 300 s, 3360 messages; egw-ditto-things-1 stopped by the fault job at +90 s for 45 s), the first run ever of this sub-check: PROCEDURE COMPLETE, no STOP, empty stderr; T7 = 0 (run complete, interruption shown, recovery shown, instrumentation complete). INTERRUPTION SHOWN: ditto-things stop exit 0, running -> exited at 14:10:56Z; RECOVERY SHOWN: start exit 0, exited -> running at 14:11:55Z; the /ready poller was still running when stopped. The Docker events capture is complete with the expected die, stop and start of egw-ditto-things-1; the controller and broker logs bounded to this run were read; the recorder unit was inactive before its cleanup. Outcomes: accepted 3355 at the first attempt, failed 5, each after 3 attempts with a ReadTimeout against Ditto while ditto-things was down (a timeout, as expected); accepted resumed after the recovery; every delta line OK (twins +300/+60/+2995; /metrics accepted +3355, failed +5). The optional N1 report: n1_applied_unconfirmed 0, duplicate_only_unexplained 0. Reported beside, deciding nothing: lost 1895, of which 1890 late confirmations and 5 failed, double_accepted 0. Gate after the row: pass (ditto-things restarted in place as expected at its 768 MiB limit; no memory-cgroup OOM; six services healthy). With row t7-mongo passed, both faults of T7 passed. |
| Next action | row t8 |

## Commands

| # | Name | Exit code | Duration (s) | Console capture | Output |
|---|---|---|---|---|---|
| 1 | guest-state-before | 0 | 13.332 | complete | [stdout](console/001-guest-state-before.stdout.txt) · [stderr](console/001-guest-state-before.stderr.txt) |
| 2 | t7-ditto | 0 | 894.269 | complete | [stdout](console/002-t7-ditto.stdout.txt) · [stderr](console/002-t7-ditto.stderr.txt) |
| 3 | guest-state-after | 0 | 10.806 | complete | [stdout](console/003-guest-state-after.stdout.txt) · [stderr](console/003-guest-state-after.stderr.txt) |
| 4 | guest-state-delta | 0 | 0.02 | complete | [stdout](console/004-guest-state-delta.stdout.txt) · [stderr](console/004-guest-state-delta.stderr.txt) |
| 5 | gate-healthy | 0 | 5.876 | complete | [stdout](console/005-gate-healthy.stdout.txt) · [stderr](console/005-gate-healthy.stderr.txt) |
| 6 | gate-units | 0 | 0.285 | complete | [stdout](console/006-gate-units.stdout.txt) · [stderr](console/006-gate-units.stderr.txt) |
| 7 | gate-tunnel-check | 0 | 0.01 | complete | [stdout](console/007-gate-tunnel-check.stdout.txt) · [stderr](console/007-gate-tunnel-check.stderr.txt) |

The full, sanitised argv of each command is in `commands.jsonl`.

## Contents

- `console/` stdout and stderr of every command; `environment/`, `tests/`, `analysis/` as named.
- `raw/` and `simulator/` hold the original artefacts byte for byte, with their own seals if they had one.
- `export_manifest.json` lists every file with its source path and SHA-256; `SHA256SUMS` seals this package.

A package here is a local copy. It is not published or admitted evidence and it is not an off-machine backup.
