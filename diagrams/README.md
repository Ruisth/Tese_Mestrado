# Diagrams

## Diagram families

This directory contains deliberately separate diagram families. The operational
Mermaid diagrams carry the deployment design of record; the PlantUML sources are
the academic reference diagram and one historical figure.

| Source | Purpose | Normative status |
|---|---|---|
| [`architecture.md`](architecture.md) | Mermaid diagrams of the contracted P0 behaviour and current platform provisioning state | Must remain aligned with `src/CONTRACTS.md` v1.1 |
| [`c2dta_five_layer_reference.puml`](c2dta_five_layer_reference.puml) ([rendered SVG](c2dta_five_layer_reference.svg)) | Editable PlantUML reconstruction of the paper's five C2DTA layers, with implemented/configured P0 components distinguished from deferred paper components | Academic reference diagram; non-normative |
| [`two_layer_experimental_deployment.puml`](two_layer_experimental_deployment.puml) ([rendered SVG](two_layer_experimental_deployment.svg)) | Editable PlantUML view of the separation between the Yocto/QEMU functional artefact and a native-ARM64 service stack | **Historical.** Superseded on 2026-09-18 by the integrated emulated deployment of the adopted plan v2.0; it was never approved by the supervisors and must not be reused as the architecture of record |
| [`architecture.md`](architecture.md), deployment diagram | Mermaid view of the **integrated emulated deployment**: the Yocto ARM64 guest under QEMU/TCG with the six containers inside it and the generator outside | The deployment design of record under the adopted plan v2.0 |

The PlantUML diagrams do not extend the P0 contract. Grey components reproduce
the supplied paper's reference architecture only and are explicitly deferred.

Two readings the deployment diagram must never be given. First, the four
virtual CPUs and 8 GiB of the guest are **emulator settings**, not a
demonstrated equivalence to a four-core physical gateway, and no timing read
from this topology is a performance result: the system under test is an ARM64
guest emulated on an x86-64 workstation. Second, the smartwatch workload is
the paper-aligned profile while the smart-ring and smart-clothing profiles are
extensions introduced by this dissertation (see
[`../docs/academic/c2dta_p0_traceability.md`](../docs/academic/c2dta_p0_traceability.md),
comparison rules 6–8).
Green/yellow P0 components are further qualified as code/configuration,
provisioned infrastructure or evidence; drawing a component never upgrades its
evidence maturity.

Render the PlantUML sources with a local PlantUML installation, for example:

```text
plantuml -charset UTF-8 -tsvg c2dta_five_layer_reference.puml two_layer_experimental_deployment.puml
```

The committed SVGs were generated and visually checked on 2026-08-13 with the
official native PlantUML 1.2026.6 release (Git commit `6287b33`). The verified
Windows AMD64 release archive had SHA-256
`a27961a865880a1a91db77fd196f317128732d668e6e20c4c20dc6f633b32e9f`.
The editable `.puml` files remain the source artefacts; regenerate the SVG in
the same change whenever a source changes.

## Operational Mermaid diagrams

The diagrams in `architecture.md` are written as fenced Mermaid blocks: they
render natively on GitHub/GitLab and in VS Code (Markdown Preview Mermaid
Support extension), or can be exported to SVG/PNG with mermaid-cli, e.g.
`mmdc -i architecture.md -o architecture.svg` (mermaid-cli is a rendering
convenience only, not a project dependency). All three diagrams are derived
directly from the normative
[`plan v2.0`](../docs/governance/INTEGRATED_DEVELOPMENT_PLAN_2026.md)
(adopted 2026-09-18 with the QEMU-only execution amendment; especially its
scientific-contract and preconditions sections) and from
[`src/CONTRACTS.md`](../src/CONTRACTS.md)
**v1.1** - they document contracted
interfaces and implemented behaviour only, never aspirational features, and
must be updated in the same change whenever CONTRACTS.md changes.

## Drawn is not deployed

That rule governs *behaviour*: a diagram never shows a topic, endpoint or
outcome that is not contracted and implemented. It does not by itself say which
machines exist. Deployment tiers are therefore labelled explicitly, and a
reader must not infer existence from a box:

| Marking | Meaning |
|---|---|
| `PROVISIONED` | The platform exists and has run the work shown |
| `PLANNED, NOT PROVISIONED` (dashed subgraph) | Contracted by the plan; not deployed, nothing in it has run |
| `FUTURE WORK, NOT BUILT AND NOT BOOTED` (dashed node) | Documented as future work by the adopted plan, unverified; nothing in it exists and nothing is requested |

As of 2026-09-18 the provisioned platform is the WSL2 workstation and the
integrated Yocto ARM64 guest emulated on it, which has built, booted and run
the six-container stack. **The adopted baseline has no native tier**: no
native or burstable ARM64 instance exists, none is requested, and the nodes
that represented them are removed from the deployment diagram rather than left
dashed. Whenever a platform changes state, the label changes in the same commit
— an unmarked box implying a machine that was never provisioned is
documentation drift of exactly the kind risk R26 covers. Drawing a component
never upgrades its evidence maturity: the stack ran once in the guest on
2026-09-18 and that record is candidate evidence held outside the repository.

## Deferred: the PlantUML sources and their SVGs

Two statements inside the PlantUML sources predate 2026-09-18 and are now
inaccurate: `two_layer_experimental_deployment.puml` is titled as a proposed
two-layer deployment and carries a native measurement host, and
`c2dta_five_layer_reference.puml` labels the P0 core "live ARM64 evidence
pending" although emulated functional evidence now exists. Editing a `.puml`
source obliges regenerating its SVG in the same change, and no PlantUML
installation is available where this change was prepared, so the sources and
their SVGs are left byte-for-byte as they are rather than allowed to diverge
from their rendered output. The corrections are therefore recorded here:

- The two-layer deployment diagram is **historical** and superseded by the
  integrated emulated deployment in `architecture.md`. Its notes about a
  non-burstable native host and a burstable integration host describe future
  native work only; what survives is the stronger rule that emulated runs give
  functional and integration evidence and support no performance inference of
  any kind. Its note "Only a non-burstable native-ARM64 host may support RQ3
  results." is replaced by: "RQ3 is bounded to the specified QEMU/TCG
  environment. Emulated timing and resource figures are informational and
  labelled emulated; they are never native ARM64 capacity or performance, and
  no native host is required by the adopted plan."
- In the five-layer reference, read "P0 artefact exists; live ARM64 evidence
  pending" as "P0 artefact exists; emulated functional evidence only, no
  admitted claim", and read the note "it does not yet contain a live
  native-ARM64 vertical-slice result" as "it contains no admitted
  vertical-slice result; the emulated run of 2026-09-18 is unsealed functional
  evidence, and no native result exists".

Regenerate both sources and their SVGs together, with the documented PlantUML
command above, in the first change made on a machine that has PlantUML
installed.

Contract version currently reflected by `architecture.md`: **v1.1** (run-scoped
dedupe, `last_run_id` in the twin `ingestion` feature, `queue_depth`/`dropped`
counters on `GET /metrics`). When `src/CONTRACTS.md` is amended, bump the
version named here and in `architecture.md` in the SAME change; a stale version
string in either file is documentation drift (risk R26).
