# 20260928T210147Z_finite-proof-adr-0011_attempt03

**ARM64 EMULATED (QEMU/TCG)** — observations of an emulated guest, not native ARM64 performance.

| Field | Value |
|---|---|
| Purpose | engineering |
| Scenario | finite proof (ADR 0011) |
| Status | finished |
| Started (UTC) | 2026-09-28T21:01:47.287556Z |
| Ended (UTC) | 2026-09-28T21:26:58.957196Z |
| Duration | 1511.7 s |
| Seed | 265481284 |
| Workload | condition: controller_restart<br>devices: smartwatch, smart ring, smart clothing (nominal mix)<br>duration_s: 300<br>engineering_diagnostic_not_a_g3_run: True<br>fault: SIGKILL of the controller's container followed by a start (proof_restart_controller.sh)<br>harness_run_id: proof-adr0011-r03<br>metrics_fast_retry: a failed /metrics poll is retried after 50 ms, at most 60 s per failure episode (controller_metrics.attempts.csv)<br>proof: the finite proof (ADR 0011)<br>rate_msg_s: 11.2<br>restart_at_s: 150<br>scenario: nominal<br>session: 20260928T205412Z_guest-session_attempt06<br>values: {'DRAIN_LIMIT_S': 900, 'DRAIN_QUIET_S': 490, 'DRAIN_STEP_S': 5, 'EGW_HEALTH_LIMIT_S': 1200, 'EGW_HEALTH_STEP_S': 15, 'EGW_PROOF_ATTEMPT_LIMIT_S': 3000, 'EGW_PROOF_BASE': '/home/ruisth/egw-tcg/proof/results', 'EGW_PROOF_DURATION_S': 300, 'EGW_PROOF_EXTENSION': 'no', 'EGW_PROOF_EXTENSION_LIMIT_S': 1790, 'EGW_PROOF_HEALTHY_RECORD': '/home/ruisth/egw-exec/attempts/20260928T210104Z_g2-gate-preconditions_attempt04/console/001-services-healthy.stdout.txt', 'EGW_PROOF_MASTER_SEED': 20260925, 'EGW_PROOF_PLAN': '/home/ruisth/egw-tcg/proof/plan-proof-adr0011-r03.json', 'EGW_PROOF_RATE': 11.2, 'EGW_PROOF_RESTART_AT_S': 150, 'EGW_PROOF_RUNBOOK': '/home/ruisth/egw-exec/repo/docs/setup/qemu_integrated_gateway.md', 'EGW_READY_LIMIT_S': 300, 'expected_source_commit': '489bc9e5b5b0660026ea2630b8d1d124049ba2ce', 'extension_fetch_limit_s': 300, 'extension_restart_limit_after_grace_s': 300}<br>warmup_s: 0 |
| Identities | drivers_sha256: 761df315a4702b5b128d31f9cac546ec7d810125c767bf2c850750cd4450139e<br>export_tool_sha256: 544c9b3d451f0a6c3391102ac4031fe93bee79a0b0b9bcd6f41c893592d2422b<br>repo_commit: b65a06ddc02842cd6464555e319ee4cc5e0d1bfb<br>repo_dirty_lines: 0 |

## Result

Three separate verdicts: whether the instrumentation produced valid evidence, what the system under test did, and whether this copy is intact. The console capture is part of the first: evidence that was not kept in full cannot make an attempt valid.

| Verdict | Value |
|---|---|
| Instrumentation validity | **valid** |
| Validity note | — |
| System outcome | **pass** |
| Console capture | **complete** — every command's stdout and stderr were kept in full |
| Copy verification | **verified** — 121 file(s) copied and verified by SHA-256; 0 excluded for secrets; 0 expected source(s) missing |
| Secret scan | values of the listed variables (names only) and PEM private keys were searched in every file |
| Reason | the proof's evaluator: supports (evaluate exit 0); manifest validity invalid (no SUT resources: timed runs require the VM-side collector output (deployment/scripts/collect-resources.sh, ingested via --resources-from); CPU/RAM on the SUT are essential for RQ3; override only with --allow-missing-resources; mandatory artefact(s) missing from the run directory: resources.csv — the run is incomplete for its condition kind, so it is marked invalid and NOT sealed (no SHA256SUMS); recover the missing evidence with 'collect' or repeat the run under a new run identity) kept as recorded, admitted for the proof only as E-12 states (harness_admission form 'sampling-gap-only') (harness exit 1; restart shown: yes; delta exit 4); the guest was left with stack=healthy restart_shown=yes |
| Next action | the result stands for this run only: one run supports the property for that run and does not prove it in general; the candidate freeze and any resumption of G3 runs are separate decisions |

## Commands

| # | Name | Exit code | Duration (s) | Console capture | Output |
|---|---|---|---|---|---|
| 1 | helpers-check | 0 | 0.021 | complete | [stdout](console/001-helpers-check.stdout.txt) · [stderr](console/001-helpers-check.stderr.txt) |
| 2 | collector-copy | 0 | 0.93 | complete | [stdout](console/002-collector-copy.stdout.txt) · [stderr](console/002-collector-copy.stderr.txt) |
| 3 | collector-sync | 0 | 1.068 | complete | [stdout](console/003-collector-sync.stdout.txt) · [stderr](console/003-collector-sync.stderr.txt) |
| 4 | guest-clock | 0 | 1.504 | complete | [stdout](console/004-guest-clock.stdout.txt) · [stderr](console/004-guest-clock.stderr.txt) |
| 5 | session-facts | 0 | 0.024 | complete | [stdout](console/005-session-facts.stdout.txt) · [stderr](console/005-session-facts.stderr.txt) |
| 6 | containers-before | 0 | 7.751 | complete | [stdout](console/006-containers-before.stdout.txt) · [stderr](console/006-containers-before.stderr.txt) |
| 7 | healthy-rule | 0 | 0.031 | complete | [stdout](console/007-healthy-rule.stdout.txt) · [stderr](console/007-healthy-rule.stderr.txt) |
| 8 | services-healthy | 0 | 6.434 | complete | [stdout](console/008-services-healthy.stdout.txt) · [stderr](console/008-services-healthy.stderr.txt) |
| 9 | healthy-rule-check | 0 | 0.025 | complete | [stdout](console/009-healthy-rule-check.stdout.txt) · [stderr](console/009-healthy-rule-check.stderr.txt) |
| 10 | sut-environment | 0 | 3.566 | complete | [stdout](console/010-sut-environment.stdout.txt) · [stderr](console/010-sut-environment.stderr.txt) |
| 11 | sut-environment-fetch | 0 | 0.612 | complete | [stdout](console/011-sut-environment-fetch.stdout.txt) · [stderr](console/011-sut-environment-fetch.stderr.txt) |
| 12 | guest-state-before | 0 | 11.332 | complete | [stdout](console/012-guest-state-before.stdout.txt) · [stderr](console/012-guest-state-before.stderr.txt) |
| 13 | controller-process-before | 0 | 0.097 | complete | [stdout](console/013-controller-process-before.stdout.txt) · [stderr](console/013-controller-process-before.stderr.txt) |
| 14 | proof-plan | 0 | 0.04 | complete | [stdout](console/014-proof-plan.stdout.txt) · [stderr](console/014-proof-plan.stderr.txt) |
| 15 | ready | 0 | 0.432 | complete | [stdout](console/015-ready.stdout.txt) · [stderr](console/015-ready.stderr.txt) |
| 16 | pre | 0 | 479.608 | complete | [stdout](console/016-pre.stdout.txt) · [stderr](console/016-pre.stderr.txt) |
| 17 | identity-check | 0 | 0.016 | complete | [stdout](console/017-identity-check.stdout.txt) · [stderr](console/017-identity-check.stderr.txt) |
| 18 | tunnel-ready | 0 | 0.009 | complete | [stdout](console/018-tunnel-ready.stdout.txt) · [stderr](console/018-tunnel-ready.stderr.txt) |
| 19 | harness-run | 1 | 972.868 | complete | [stdout](console/019-harness-run.stdout.txt) · [stderr](console/019-harness-run.stderr.txt) |
| 20 | eligibility | 0 | 0.066 | complete | [stdout](console/020-eligibility.stdout.txt) · [stderr](console/020-eligibility.stderr.txt) |
| 21 | controller-process-after | 0 | 0.053 | complete | [stdout](console/021-controller-process-after.stdout.txt) · [stderr](console/021-controller-process-after.stderr.txt) |
| 22 | containers-after | 0 | 7.266 | complete | [stdout](console/022-containers-after.stdout.txt) · [stderr](console/022-containers-after.stderr.txt) |
| 23 | restart-shown | 0 | 0.02 | complete | [stdout](console/023-restart-shown.stdout.txt) · [stderr](console/023-restart-shown.stderr.txt) |
| 24 | metrics-after | 0 | 0.2 | complete | [stdout](console/024-metrics-after.stdout.txt) · [stderr](console/024-metrics-after.stderr.txt) |
| 25 | delta | 4 | 0.08 | complete | [stdout](console/025-delta.stdout.txt) · [stderr](console/025-delta.stderr.txt) |
| 26 | guest-state-after | 0 | 10.317 | complete | [stdout](console/026-guest-state-after.stdout.txt) · [stderr](console/026-guest-state-after.stderr.txt) |
| 27 | guest-state-delta | 0 | 0.024 | complete | [stdout](console/027-guest-state-delta.stdout.txt) · [stderr](console/027-guest-state-delta.stderr.txt) |
| 28 | services-healthy-after | 0 | 5.066 | complete | [stdout](console/028-services-healthy-after.stdout.txt) · [stderr](console/028-services-healthy-after.stderr.txt) |
| 29 | evaluate | 0 | 0.157 | complete | [stdout](console/029-evaluate.stdout.txt) · [stderr](console/029-evaluate.stderr.txt) |

The full, sanitised argv of each command is in `commands.jsonl`.

## Expected artefacts

- `raw/*/manifest.json`: present
- `raw/*/sent_events.jsonl`: present
- `raw/*/events.jsonl`: present
- `raw/*/events.post-drain.jsonl`: present
- `raw/*/twins.before.json`: present
- `raw/*/twins.after.json`: present
- `raw/*/configuration_identity.json`: present
- `raw/*/controller_metrics.csv`: present
- `raw/*/logs/collector/resources-proof-adr0011-r03.csv`: present
- `raw/*/logs/sut/broker.log`: present
- `raw/*/logs/sut/controller.log`: present
- `raw/*/logs/sut/docker-events.log`: present
- `analysis/proof_session.json`: present
- `analysis/proof_verdict.json`: present
- `analysis/snapshots/*.config_identity.json`: present
- `analysis/snapshots/*.metrics.before.json`: present
- `analysis/snapshots/*.metrics.after.json`: present
- `analysis/snapshots/*.twins.before.json`: present
- `analysis/snapshots/*.twins.after.json`: present
- `analysis/snapshots/*.restart.txt`: present
- `environment/proof_plan.json`: present
- `environment/sut_environment.json`: present
- `environment/clocks.txt`: present
- `environment/containers.before.txt`: present
- `environment/containers.after.txt`: present
- `environment/helpers-check.txt`: present

## Contents

- `console/` stdout and stderr of every command; `environment/`, `tests/`, `analysis/` as named.
- `raw/` and `simulator/` hold the original artefacts byte for byte, with their own seals if they had one.
- `export_manifest.json` lists every file with its source path and SHA-256; `SHA256SUMS` seals this package.

A package here is a local copy. It is not published or admitted evidence and it is not an off-machine backup.
