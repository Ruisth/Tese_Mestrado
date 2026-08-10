# Diagrams

The diagrams in `architecture.md` are written as fenced Mermaid blocks: they
render natively on GitHub/GitLab and in VS Code (Markdown Preview Mermaid
Support extension), or can be exported to SVG/PNG with mermaid-cli, e.g.
`mmdc -i architecture.md -o architecture.svg` (mermaid-cli is a rendering
convenience only, not a project dependency). All three diagrams are derived
directly from the normative plan (`PLANO_DESENVOLVIMENTO_INTEGRADO_EDGE_GATEWAY_2026.md`
section 5) and from `src/CONTRACTS.md` **v1.1** - they document contracted
interfaces and implemented behaviour only, never aspirational features, and
must be updated in the same change whenever CONTRACTS.md changes.

Contract version currently reflected by `architecture.md`: **v1.1** (run-scoped
dedupe, `last_run_id` in the twin `ingestion` feature, `queue_depth`/`dropped`
counters on `GET /metrics`). When `src/CONTRACTS.md` is amended, bump the
version named here and in `architecture.md` in the SAME change; a stale version
string in either file is documentation drift (risk R26).
