# 20261003T142310Z_g3-qualification-t8_attempt01

**ARM64 EMULATED (QEMU/TCG)** — observations of an emulated guest, not native ARM64 performance.

| Field | Value |
|---|---|
| Purpose | official |
| Scenario | G3 qualification t8 |
| Status | failed |
| Started (UTC) | 2026-10-03T14:23:11.018329Z |
| Ended (UTC) | 2026-10-03T14:37:50.009244Z |
| Duration | 879.0 s |
| Seed | — |
| Workload | battery: G3 qualifying battery (decision packet of 2026-10-01, revision 2; authorised 2026-10-02)<br>egw_clone: /home/ruisth/egw-exec/repo<br>harness_run_id: None<br>helper_sha256: e5eba37e529a47885a8aea0e718d25ac71ce1e31a0c1a381b4520fe4c914b4fb<br>host_uptime_at_row_start_s: 3740<br>host_uptime_baseline_s: 25<br>ids_note: itest-reboot-q1 is the prefix of the reboot snapshots and of the boot id file, not a run id<br>itest_run_ids: ['itest-post-reboot-01-q1']<br>row: t8<br>row_ceiling_min: 135<br>rows_manifest_sha256: cfca6a9397715d0c95881a2c824cad83a95e73727a500351920faf5552ad230c<br>runbook: {'commit': '80e833f44f647fe9cd8f5e99d3abf3c444de95aa', 'lines': 1614, 'path': 'docs/setup/qemu_integrated_gateway.md', 'sha256': 'c55a2d3b68fe7bc463d99fb2c4456e1d6462ceb7eae8e16495aaf1d1fecd74ae'}<br>session: 20261003T132249Z_guest-session_attempt09<br>session_elapsed_at_row_start_s: 3715<br>session_label: S2<br>step_files: {'t8-a-reboot.sh': 'bb2d76e5ea3630b72fc39810f528766f549d0fc3f97667102874a3c77242a5c3', 't8-b-return.sh': 'f8259e353019bd02e604344292a07208c8b1116098af47b31f90b1a932a097c7', 't8-c-snapshot.sh': '9a60f8d6f75b99a573c91f5353a8b8963c641000974389ffd7867ce2477e73a2', 't8-d-smoke.sh': 'f541f1caf33787327fe2d437da9c4994e540ce1346aa2987aca89a19e5514d53'}<br>step_source_lines: {'t8-a-reboot.sh': '1486-1488', 't8-b-return.sh': '1489-1490', 't8-c-snapshot.sh': '1491', 't8-d-smoke.sh': '1492'}<br>steps_script_sha256: fd652ec928ce9e9570f03fa526b83473a6706a17d81b5ade9c2dbc6b42e44ac1 |
| Identities | drivers_sha256: 4a6a572dc1e2b54754c3a8dec38e6d2392227efc61ee710886ad9ad5729a39a5<br>export_tool_sha256: 544c9b3d451f0a6c3391102ac4031fe93bee79a0b0b9bcd6f41c893592d2422b<br>repo_commit: 80e833f44f647fe9cd8f5e99d3abf3c444de95aa<br>repo_dirty_lines: 0 |

## Result

Three separate verdicts: whether the instrumentation produced valid evidence, what the system under test did, and whether this copy is intact. The console capture is part of the first: evidence that was not kept in full cannot make an attempt valid.

| Verdict | Value |
|---|---|
| Instrumentation validity | **valid** |
| Validity note | — |
| System outcome | **inconclusive** |
| Console capture | **complete** — every command's stdout and stderr were kept in full |
| Copy verification | **verified; incomplete** — 30 file(s) copied and verified by SHA-256; 0 excluded for secrets; 1 expected source(s) missing |
| Secret scan | values of the listed variables (names only) and PEM private keys were searched in every file |
| Reason | INCONCLUSIVE / NOT DEMONSTRATED (packet section 5, T8 row: QEMU never exited), with a HALT (packet section 4, halt 5). Step a ran as written: wait_ready, drained, the pre-reboot twin snapshot (label pre-reboot, seed 42, three devices) and the boot id d22195a1... recorded, then 'sudo systemctl reboot' over ssh. The guest rebooted: its journal shows the previous boot ending cleanly at 14:25:44Z (systemd shutting down) and the new boot 76471e31... starting at 14:26:15Z; the six containers were started again by 14:26:46Z on the same container objects, unaided, and were healthy; /var/lib/docker is on /dev/vdb; the 35 event directories, the ten -q1 ones among them, are intact; no kernel OOM line in the previous boot (read-only evidence step t8-post-reboot-evidence on the session attempt, and the row's guest-state-after). But the QEMU process did NOT exit: the launcher of this session runs QEMU without -no-reboot (its command line carries no such option), so the guest rebooted inside the same process and ports 2222/8883 stayed busy. The runbook's line 1487 ('QEMU exits (-no-reboot). Re-launch exactly as in 3.3') assumed otherwise, and the steps script, built on that assumption, waited 600 s for the exit and then halted without signalling QEMU, as the packet orders. Steps b, c and d (the boot-id comparison that prints REBOOT SHOWN, the post-reboot twin snapshot and its comparison, the post-reboot smoke itest-post-reboot-01-q1) were therefore NOT run: the reboot was observed, but test 8's Expected list was not evaluated, so T8 is not demonstrated, and never a pass. T9 is not run after this halt. Gate after the row: pass (state recorded, not compared across the reboot; six services healthy; no unit active; the tunnel reopened by the preamble). For the Project Manager: the T8 procedure rests on a QEMU exit that this launcher does not produce; the in-place reboot that did happen is the behaviour test 8 wants to observe (stack back unaided, data disk persistent), and a corrected procedure (steps b to d run on the rebooted guest, with the boot ids compared) would be a decision, not a correction made here. |
| Next action | close (controlled close, hand back to Rui); T9 not run |

## Commands

| # | Name | Exit code | Duration (s) | Console capture | Output |
|---|---|---|---|---|---|
| 1 | guest-state-before | 0 | 14.108 | complete | [stdout](console/001-guest-state-before.stdout.txt) · [stderr](console/001-guest-state-before.stderr.txt) |
| 2 | t8-a-reboot | 0 | 136.293 | complete | [stdout](console/002-t8-a-reboot.stdout.txt) · [stderr](console/002-t8-a-reboot.stderr.txt) |
| 3 | t8-wait-qemu-exit | 1 | 584.24 | complete | [stdout](console/003-t8-wait-qemu-exit.stdout.txt) · [stderr](console/003-t8-wait-qemu-exit.stderr.txt) |
| 4 | guest-state-after | 0 | 16.81 | complete | [stdout](console/004-guest-state-after.stdout.txt) · [stderr](console/004-guest-state-after.stderr.txt) |
| 5 | gate-healthy | 0 | 10.048 | complete | [stdout](console/005-gate-healthy.stdout.txt) · [stderr](console/005-gate-healthy.stderr.txt) |
| 6 | gate-units | 0 | 1.156 | complete | [stdout](console/006-gate-units.stdout.txt) · [stderr](console/006-gate-units.stderr.txt) |
| 7 | gate-tunnel-check | 0 | 0.773 | complete | [stdout](console/007-gate-tunnel-check.stdout.txt) · [stderr](console/007-gate-tunnel-check.stderr.txt) |

The full, sanitised argv of each command is in `commands.jsonl`.

## Missing artefacts

- `simulator` itest run itest-post-reboot-01-q1: the simulator's directory with the fetched events.jsonl, and every itest-post-reboot-01-q1.* sibling the helpers write (transcript, marker, metrics, twins, reconcile, copies, .sut/): `/home/ruisth/egw-tcg/itest/itest-post-reboot-01-q1` did not exist at export time

## Contents

- `console/` stdout and stderr of every command; `environment/`, `tests/`, `analysis/` as named.
- `raw/` and `simulator/` hold the original artefacts byte for byte, with their own seals if they had one.
- `export_manifest.json` lists every file with its source path and SHA-256; `SHA256SUMS` seals this package.

A package here is a local copy. It is not published or admitted evidence and it is not an off-machine backup.
