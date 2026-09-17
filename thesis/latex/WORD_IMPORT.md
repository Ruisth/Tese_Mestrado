# Word manuscript import into the supplied LaTeX template

Date: 2026-09-17. This is a source-preserving document conversion, not a new
scientific review, governance-plan amendment or gate decision.

## Authoritative inputs

- Manuscript: `Dissertation_Rui Duarte_Digital Twin Edge Gateway.docx`,
  supplied by the student from their university OneDrive directory.
- Layout: the student's local `Template_LaTeX/main.tex` and its two logo
  assets, not the previous dissertation draft or another report template.
- Input hashes and counts: [word-import-manifest.json](word-import-manifest.json).
- Baseline: `dev` at `cf6bc62f730aad58a0fa4301d0740cf00ca6eec6`.

The original Word file, template directory and the working checkout's unrelated
unpublished changes were not modified. The conversion was prepared in a separate
clone of the published baseline. The Word binary is not committed.

## Included content and empty sections

| Source item | LaTeX destination | Treatment |
|---|---|---|
| Title, author, student number, degree and academic year | `main.tex` | Transcribed into the supplied template's covers |
| Abbreviations | `abbreviations.tex` | All source cells retained |
| Introduction, five sections | `chapters/01_introduction.tex` | Source prose and lists retained |
| Theoretical Framework, nine sections | `chapters/02_background.tex` | Source prose and two tables retained |
| Research-process figure | `imagens/research-process.png` | Original embedded PNG, byte-identical |
| References 1–33 | `../refs/references.bib` | Complete source strings retained under keys `word01`–`word33` |
| Chapters 3–6 | Existing chapter files | Chapter/section headings and labels only |
| Dedication, acknowledgment, Resumo and Abstract | `main.tex` | Empty, with no sample text or TODO markers |
| Supervisor names and categories | Covers | Blank; not inferred |

The architecture chapter keeps its existing empty section headings so that the
repository's architecture/implementation mapping remains usable. Empty chapter
pages and two-sided blank versos are intentional, not evidence of completed
writing. The older draft remains recoverable in Git history; it is not silently
combined with this manuscript.

## Template fidelity

The supplied template's preamble is retained, with the bibliography path adjusted
to the existing repository layout and a title macro/import-support input added.
Its `amsbook` class, 12 pt size, `twoside`, A4 paper, 2.5 cm margins,
one-and-a-half line spacing, Montserrat cover styling, two covers, front-matter
sequence, page numbering and chapter-based numbering remain in use. Both logos
are byte-identical to the supplied assets.

The long title and student-number line require reducing the runs of four empty
cover lines to three, keeping each cover on one page. Additional packages in
`word-import-support.tex` support multi-page tables, ragged table cells, URL
wrapping and microtypography. Table headers repeat across page breaks. Captions
and numbering use LaTeX counters rather than the Word document's typed numbers.

This verifies use of the template selected by the student. It does not resolve
the separate question of whether it is the university's approved 2026 template.

## Bibliography and editorial boundary

The template retains IEEE `biblatex` and the Biber backend. Each reference is
stored as an `@misc` entry with its full, formatted source string in `note`.
A local driver prints that string; this avoids inventing structured metadata
that the supplied Word document does not encode. Numeric source citations are
converted into actual `\cite{wordNN}` commands. The standalone Chapter 2 entry
point preserves the full manuscript's reference numbering and reference list.

No prose, research claim, American spelling, grammatical issue or bibliographic
metadata has been silently corrected. In particular, reference 9's year 2027
and reference 22's extended source title remain as supplied. Their accuracy and
the remaining editorial work require a separate review. A successful import is
not bibliographic verification or academic acceptance.

## Verification

The [verification record](../../docs/evidence/word-import-2026-09-17/README.md)
holds the check results and reproducibility details.
Scoped Git attributes preserve the compiler logs byte-for-byte, including
their original line endings and whitespace, so checkout cannot invalidate
their evidence checksums.

Reproducible commands, from the repository root unless otherwise indicated:

```text
python thesis/tools/verify_word_import.py --source <original.docx> --template <Template_LaTeX>
python -m unittest discover -s thesis/tools -p "test_*.py" -v
python thesis/tools/generate_sections.py
python tools/ci/verify_evidence.py
python tools/ci/check_markdown_links.py
git diff --check
cd thesis/latex
latexmk -pdf -interaction=nonstopmode -halt-on-error main.tex
latexmk -pdf -interaction=nonstopmode -halt-on-error ch2_supervisor_draft.tex
```

PDF review checks covers, all page layouts, table continuations, the original
figure, reference numbering and deliberately empty sections. Repository CI
remains responsible for its full application-test and shell-check matrix; this
document conversion claims no new live gateway or ARM64 result.

## Rollback

Revert the import commit through a new pull request to restore the prior
manuscript and projection helper. No history rewrite, runtime/schema change,
raw experiment deletion or alteration to the existing evidence seals is needed.
