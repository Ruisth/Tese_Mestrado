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
| G0 | Not decided | — | — | [Current operational state](../../PROGRESS.md) | — | Alignment email, D001–D008 request, university ARM64 request and off-machine copy remain incomplete. |
| G1 | Not decided | — | — | [Clean build and strict five-boot seal](../evidence/g1-yocto-qemu/2026-08-14-clean-build-f0e19d5/README.md) | — | Technical evidence is produced and sealed. D006 remains a separate supervisor decision; no formal gate outcome has been recorded. |
| G2 | Not decided | — | — | [Current operational state](../../PROGRESS.md) | — | Native ARM64 deployment and a live vertical slice do not exist. |
| G3 | Not decided | — | — | [Current operational state](../../PROGRESS.md) | — | Live integration/recovery evidence does not exist. |
| G4 | Not decided | — | — | [Current operational state](../../PROGRESS.md) | — | Micro-pilot and `exp-v1` freeze have not occurred. |
| G5 | Not decided | — | — | [Current operational state](../../PROGRESS.md) | — | Official 95-run campaign has not occurred. |
| G6 | Not decided | — | — | [Current operational state](../../PROGRESS.md) | — | Sealed-data analysis and claim admission have not occurred. |
| G7 | Not decided | — | — | [Current operational state](../../PROGRESS.md) | — | Complete thesis/reproduction package and final review have not occurred. |
