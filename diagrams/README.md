# Diagrams

The diagrams in `architecture.md` are written as fenced Mermaid blocks: they
render natively on GitHub/GitLab and in VS Code (Markdown Preview Mermaid
Support extension), or can be exported to SVG/PNG with mermaid-cli, e.g.
`mmdc -i architecture.md -o architecture.svg` (mermaid-cli is a rendering
convenience only, not a project dependency). All three diagrams are derived
directly from the normative plan (`PLANO_DESENVOLVIMENTO_INTEGRADO_EDGE_GATEWAY_2026.md`
section 5) and from `src/CONTRACTS.md` v1.0 - they document contracted
interfaces and implemented behaviour only, never aspirational features, and
must be updated in the same change whenever CONTRACTS.md changes.
