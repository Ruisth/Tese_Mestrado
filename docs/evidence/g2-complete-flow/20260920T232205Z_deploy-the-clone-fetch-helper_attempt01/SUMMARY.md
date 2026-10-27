# 20260920T232205Z_deploy-the-clone-fetch-helper_attempt01

**ARM64 EMULATED (QEMU/TCG)** — observations of an emulated guest, not native ARM64 performance.

| Field | Value |
|---|---|
| Purpose | engineering |
| Scenario | deploy the clone fetch helper |
| Status | finished |
| Started (UTC) | 2026-09-20T23:22:05.759279Z |
| Ended (UTC) | 2026-09-20T23:22:08.732190Z |
| Duration | 3.0 s |
| Seed | — |
| Workload | — |
| Identities | reason: the deployed tree lacked src/deployment/scripts/fetch-collector-output.sh, which the clone has since pull request 38; runbook 5.1 copies that tree to the guest<br>repo_commit: b7e0c83c3277f7469c05336f91949e7d1b89489a |

## Result

Three separate verdicts: whether the instrumentation produced valid evidence, what the system under test did, and whether this copy is intact. The console capture is part of the first: evidence that was not kept in full cannot make an attempt valid.

| Verdict | Value |
|---|---|
| Instrumentation validity | **valid** |
| Validity note | — |
| System outcome | **pass** |
| Console capture | **complete** — every command's stdout and stderr were kept in full |
| Copy verification | **verified** — 5 file(s) copied and verified by SHA-256; 0 excluded for secrets; 0 expected source(s) missing |
| Secret scan | values of the listed variables (names only) and PEM private keys were searched in every file |
| Reason | the clone fetch helper was deployed to /opt/egw/deployment/scripts (runbook 5.1); the deployed tree now holds every file of the clone |
| Next action | repeat the preflight |

## Commands

| # | Name | Exit code | Duration (s) | Console capture | Output |
|---|---|---|---|---|---|
| 1 | deploy-fetch-helper | 0 | 2.935 | complete | [stdout](console/001-deploy-fetch-helper.stdout.txt) · [stderr](console/001-deploy-fetch-helper.stderr.txt) |

The full, sanitised argv of each command is in `commands.jsonl`.

## Contents

- `console/` stdout and stderr of every command; `environment/`, `tests/`, `analysis/` as named.
- `raw/` and `simulator/` hold the original artefacts byte for byte, with their own seals if they had one.
- `export_manifest.json` lists every file with its source path and SHA-256; `SHA256SUMS` seals this package.

A package here is a local copy. It is not published or admitted evidence and it is not an off-machine backup.
