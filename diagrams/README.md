# Diagrams

## Diagram families

This directory now contains two deliberately separate diagram families:

| Source | Purpose | Normative status |
|---|---|---|
| [`architecture.md`](architecture.md) | Mermaid diagrams of the contracted P0 behaviour and current platform provisioning state | Must remain aligned with `src/CONTRACTS.md` v1.1 |
| [`c2dta_five_layer_reference.puml`](c2dta_five_layer_reference.puml) ([rendered SVG](c2dta_five_layer_reference.svg)) | Editable PlantUML reconstruction of the paper's five C2DTA layers, with implemented/configured P0 components distinguished from deferred paper components | Academic reference diagram; non-normative |
| [`two_layer_experimental_deployment.puml`](two_layer_experimental_deployment.puml) ([rendered SVG](two_layer_experimental_deployment.svg)) | Editable PlantUML view of the proposed separation between the Yocto/QEMU functional artefact and the native-ARM64 service stack | Proposal for D001; non-normative until supervisor approval |

The PlantUML diagrams do not extend the P0 contract. Grey components reproduce
the supplied paper's reference architecture only and are explicitly deferred.

Two readings the two-layer deployment diagram must never be given: the
native-ARM64 VM node is an **edge-class proxy** with a fixed resource
envelope, not a consumer-controlled physical gateway; and the smartwatch
workload is the paper-aligned profile while the smart-ring and smart-clothing
profiles are extensions introduced by this dissertation (see
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
[`plan v1.1`](../docs/governance/INTEGRATED_DEVELOPMENT_PLAN_2026.md)
(especially sections 3 and 5) and from [`src/CONTRACTS.md`](../src/CONTRACTS.md)
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

As of 2026-08-13 only the functional tier (WSL2 + QEMU) is provisioned. The
measurement instance in diagram 2 **does not exist**, so it carries the dashed
marking; the burstable integration instance also **does not exist** (only an
eligible SKU has been identified). Whenever a tier changes state, the label
changes in the same commit — an unmarked box
implying a machine that was never provisioned is documentation drift of exactly
the kind risk R26 covers.

Contract version currently reflected by `architecture.md`: **v1.1** (run-scoped
dedupe, `last_run_id` in the twin `ingestion` feature, `queue_depth`/`dropped`
counters on `GET /metrics`). When `src/CONTRACTS.md` is amended, bump the
version named here and in `architecture.md` in the SAME change; a stale version
string in either file is documentation drift (risk R26).
