# Word manuscript import verification

Date: 2026-09-17. Scope: manuscript fidelity, supplied-template provenance,
document builds and repository integrity. No gateway runtime or experimental
claim is verified by this record.

The source identity and template hashes are recorded in
[the import manifest](../../../thesis/latex/word-import-manifest.json).
[The import record](../../../thesis/latex/WORD_IMPORT.md) explains the exact
scope, intentional blank sections and bibliography-preservation policy.

## Recorded checks

The machine-readable `verification.json`, command outputs and `SHA256SUMS` in
this directory record the final pre-commit checks. The pull-request body names
the committed revision; the verification record does not claim a self-referential
commit hash or a clean tree before the import was committed.

- Independent source comparison: 56 comparable body blocks, 117 table cells,
  33 complete reference strings, 14 source sections and one embedded PNG.
- Supplied template: original preamble lineage, class/layout settings and
  byte-identical logos; only documented content/typesetting adaptations.
- Empty sections: Chapters 3–6 and unprovided front matter contain no prior
  prose, TODO text or sample content.
- Document builds: full dissertation and standalone Chapter 2.
- Markdown projection: regression tests and byte-stable regeneration, including
  reference strings, numeric citations, table data and relative image links.
- Repository integrity: evidence seals, local Markdown links and whitespace.

## Visual inspection

All 43 pages of `main.pdf` were inspected in a page-layout overview; the
research-process figure and both chapter tables were additionally inspected
at page size. Covers fit on their own pages; there is no clipped or overlapping
content. Chapters 1–2 occupy 11 body pages. The 10-page Chapter 2 extract is
generated from the same source and preserves reference numbering.

The full draft includes deliberately empty front-matter/chapter pages and
two-sided blank versos. Three `Underfull \\vbox` diagnostics in the full build
concern vertical page filling; there are no overfull boxes or unresolved
citations/references. Page count is a formatting outcome, not writing progress.

The source Word's scientific statements, spelling and bibliographic metadata
were preserved, not academically endorsed. The original document is required
to rerun the source comparison and is not included in Git. Existing historical
evidence seals are unchanged.
