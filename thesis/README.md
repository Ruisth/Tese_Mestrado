# Thesis — Dissertation Sources and Research Protocol

The canonical LaTeX manuscript is the 2026-09-17 conversion of the supplied
`Dissertation_Rui Duarte_Digital Twin Edge Gateway.docx`, using the supplied
`Template_LaTeX` as its formatting base. This source snapshot supersedes the
previous dissertation draft; its earlier page counts, word counts and chapter
completeness statements do not describe the current manuscript.

The manuscript title is **Blockchain-powered Personal AI -- Digital Twin Edge
Gateway**, by Rui Miguel Franco Duarte (student number 94494), for the Master
in Telecommunications and Computer Engineering. These fields come from the
Word source. Unknown supervisor details remain blank.

## Source boundary and provenance

The import preserves the supplied Word prose: Introduction and Theoretical
Framework, three tables (the abbreviations table and two Chapter 2 tables),
one research-process figure and 33 reference strings. Chapters 3–6 retain
headings and, where present, empty structural sections only. Front-matter
sections without supplied content remain empty. No previous-draft prose,
sample text, TODO markers or invented completion text fills those gaps.

The source DOCX SHA-256 is
`c589422a42318cf1635ad895cbe23cd24e2157ed569554a8ab3cd5dcaea25945`.
See [the import record](latex/WORD_IMPORT.md) and the
[machine-readable source manifest](latex/word-import-manifest.json) for
provenance, scope and verification evidence.

The supplied template's `amsbook` class, 12 pt type, two-sided layout, A4
paper, 25 mm margins, Montserrat cover font, one-and-a-half line spacing,
two covers and institutional logos are retained. Use of this supplied
template does **not** establish that it is the current official 2026
template; that remains supervisor decision D004.

This is a format conversion, not a scientific or bibliographic revision.
In particular, integrated-Yocto wording comes from the supplied Word source;
its inclusion neither adopts a new governance-plan version nor demonstrates
implementation or supervisor approval. The repository's
[governance plan](../docs/governance/INTEGRATED_DEVELOPMENT_PLAN_2026.md),
decision records and claim states are unchanged. Any difference between the
source manuscript and those controls needs a separate, authorised alignment
decision. No gate or claim is accepted by this import.

## Canonical source and generated mirror

| Tree | Role |
|---|---|
| `latex/` | Canonical editable dissertation source. |
| `sections/` | Generated Markdown mirror; never edit by hand. |

```sh
python thesis/tools/generate_sections.py
```

The generator requires Pandoc. Regenerate the mirror whenever LaTeX changes,
in the same commit. Each generated file identifies its source in a
`GENERATED FILE - DO NOT EDIT` banner. The mapping is recorded in
[manifest.yaml](manifest.yaml); empty manuscript sections must remain empty
in the mirror as well.

## Layout and current content

```text
thesis/
├─ latex/
│  ├─ main.tex                   # supplied template with imported content
│  ├─ abbreviations.tex         # Word abbreviations table
│  ├─ word-import-support.tex   # formatting and verbatim-reference support
│  ├─ WORD_IMPORT.md            # import scope and verification record
│  ├─ word-import-manifest.json # source identity and inventory
│  ├─ imagens/                 # supplied logos and extracted research figure
│  ├─ ch2_supervisor_draft.tex  # derivative of the current Chapter 2
│  └─ chapters/
│     ├─ 01_introduction.tex    # Word Introduction
│     ├─ 02_background.tex      # Word Theoretical Framework
│     ├─ 03_methodology.tex     # heading only
│     ├─ 04_architecture.tex    # headings only
│     ├─ 05_evaluation.tex      # heading only
│     └─ 06_conclusions.tex     # heading only
├─ refs/
│  └─ references.bib           # 33 reference strings preserved from Word
├─ research/                  # existing research records, not re-audited
├─ sections/                  # generated Markdown mirror
└─ manifest.yaml
```

## How to compile

Use TeX Live with `latexmk`, Biber and the supplied template's packages,
including `amsbook`, `biblatex`, `montserrat`, `acronym` and `enumitem`.
The import also needs the table and graphics packages named in
`latex/word-import-support.tex`. CI installs the documented TeX toolchain
and builds both documents.
On Debian/Ubuntu, install `cm-super` explicitly when using
`--no-install-recommends`: scalable T1 fonts are needed for the template's
font encoding with microtype expansion. Without them, the CI build failed
with `auto expansion is only possible with scalable fonts` even though the
complete local TeX Live installation built successfully.

From `thesis/latex/`:

```sh
latexmk -pdf -interaction=nonstopmode -halt-on-error main.tex
latexmk -pdf -interaction=nonstopmode -halt-on-error ch2_supervisor_draft.tex
```

The manual main-document sequence is `pdflatex main`, `biber main`, then
`pdflatex main` twice. The bibliography path is `../refs/references.bib`,
relative to `thesis/latex/`. Build outcomes belong in the import record;
the commands above are instructions, not a claim that a build passed.

## Bibliography and evidence boundaries

The template retains IEEE `biblatex` with Biber. For this source-faithful
import, each Word reference is stored as an `@misc` entry's `note`, with a
custom driver preserving the supplied bibliographic string. This is a
documented import exception to the earlier structured, verified-entry
convention: no new metadata verification or correction is asserted.
The 33 imported strings must not be confused with the separate historical
research register or its earlier verification counts.

Future academic revisions must preserve the project's evidence discipline:

1. No quantitative project result without admitted raw data, a manifest,
   reproducible analysis and a corresponding
   [claim-evidence record](../docs/claim_evidence_matrix.md).
2. No invented implementation, physical-hardware, SSI, blockchain or security
   achievement. Word-source wording is not proof of an achievement.
3. Keep unprovided sections empty until separately authorised content exists;
   do not restore former draft prose merely to complete the structure.
4. Do not infer supervisor approval of the title, RQs, template or manuscript
   from the conversion. Decisions D001 and D004 remain separate controls.
5. Complete reference verification and remaining manuscript review before
   academic release; never silently correct the source during an import.

The existing [literature-review protocol](research/literature_review_protocol.md)
and research logs remain separate records. Their methods, searches and
screening outcomes are not changed by this conversion.
