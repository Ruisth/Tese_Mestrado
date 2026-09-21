# HIST_2026-09-18-stack-images-provisioning

**ARM64 EMULATED (QEMU/TCG)** — observations of an emulated guest, not native ARM64 performance.

**Historical attempt, copied as it was preserved.** Its validity is the one it had; the copy does not upgrade it.

| Field | Value |
|---|---|
| Purpose | engineering |
| Scenario | stack image provisioning |
| Status | finished |
| Started (UTC) | — |
| Ended (UTC) | — |
| Duration | unknown |
| Seed | — |
| Workload | — |
| Identities | — |

## Result

Three separate verdicts: whether the instrumentation produced valid evidence, what the system under test did, and whether this copy is intact.

| Verdict | Value |
|---|---|
| Instrumentation validity | **unknown** |
| System outcome | **unknown** |
| Copy verification | **verified** — 29 file(s) copied and verified by SHA-256; 0 excluded for secrets; 0 expected source(s) missing |
| Reason | candidate capsule; image identities; sealed locally; not admitted |
| Next action | — |

## Contents

- `console/` stdout and stderr of every command; `environment/`, `tests/`, `analysis/` as named.
- `raw/` and `simulator/` hold the original artefacts byte for byte, with their own seals if they had one.
- `export_manifest.json` lists every file with its source path and SHA-256; `SHA256SUMS` seals this package.

A package here is a local copy. It is not published or admitted evidence and it is not an off-machine backup.
