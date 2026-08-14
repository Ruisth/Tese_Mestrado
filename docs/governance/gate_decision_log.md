# Formal gate-decision log

> **Decision-only authority.** `PROGRESS.md` remains the sole source of current
> operational state. This log records only formal gate outcomes and the dated
> decision record that supports them. Producing evidence, passing CI, merging a
> pull request or remaining silent never changes a gate to accepted.

Updated: 2026-08-14.

Permitted formal outcomes are `Not decided`, `Accepted`, `Rejected` and `Cut`.
An outcome other than `Not decided` requires a date, the decision authority and
a durable decision record. `LOG.md` may record that the action occurred, but it
is a diary and is not the decision authority.

| Gate | Formal outcome | Decided at | Decision authority | Evidence available | Decision record | Notes |
|---|---|---|---|---|---|---|
| G0 | Not decided | — | — | [Current operational state](../../PROGRESS.md) | — | Alignment email, D001–D010 request, university ARM64 request and off-machine copy remain incomplete. |
| G1 | **Accepted** | 2026-08-14 | Student (Rui Duarte) | [Clean build and strict five-boot seal](../evidence/g1-yocto-qemu/2026-08-14-clean-build-f0e19d5/README.md) | This row, merged through a pull request under the six required checks; narrative in `LOG.md` #C015 | Accepted against the plan v1.1/v1.2 §4 criterion: clean identified checkout build `f0e19d5` (5,715 tasks) and five strict boots (`qemu-g1r2-01..05`), each passing all seven required assertions with exact `systemd=running`, zero failed units and a clean shutdown; the failed first attempt is preserved in the same capsule. **Scope of the decision:** functional platform layer only. It validates no claim (C01/C02 stay partial pending admission), supports no performance statement, and leaves D006 (second-operator reproduction) a separate supervisor decision. |
| G2 | Not decided | — | — | [Current operational state](../../PROGRESS.md) | — | Native ARM64 deployment and a live vertical slice do not exist. |
| G3 | Not decided | — | — | [Current operational state](../../PROGRESS.md) | — | Live integration/recovery evidence does not exist. |
| G4 | Not decided | — | — | [Current operational state](../../PROGRESS.md) | — | Micro-pilot and `exp-v1` freeze have not occurred. |
| G5 | Not decided | — | — | [Current operational state](../../PROGRESS.md) | — | Official 95-run campaign has not occurred. |
| G6 | Not decided | — | — | [Current operational state](../../PROGRESS.md) | — | Sealed-data analysis and claim admission have not occurred. |
| G7 | Not decided | — | — | [Current operational state](../../PROGRESS.md) | — | Complete thesis/reproduction package and final review have not occurred. |
