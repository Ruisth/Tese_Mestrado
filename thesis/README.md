# Thesis: historical LaTeX conversion (2026-09-17) and research protocol

> **This directory holds a historical version, not the current dissertation.** The LaTeX tree is
> the conversion, on 2026-09-17, of the Word manuscript of that date. It holds:
>
> - Chapters 1 and 2 imported;
> - Chapters 3 to 6 as headings only.
>
> It has not changed since (commit `4ce29db`). The current manuscript is the student's Word file.
> It is maintained outside this repository and is not published here. Nothing in this directory
> replaces it or should be read as its content. The results that the current dissertation
> presents, with their data, are indexed in [`../docs/results.md`](../docs/results.md).

The conversion took the then-supplied
`Dissertation_Rui Duarte_Digital Twin Edge Gateway.docx` and used the supplied `Template_LaTeX` as
its formatting base. At that date it replaced an earlier LaTeX draft. Its page counts, word counts
and chapter-completeness statements describe the 2026-09-17 source only.

The manuscript title in that source is **Blockchain-powered Personal AI -- Digital Twin Edge
Gateway**, by Rui Miguel Franco Duarte (student number 94494), for the Master in
Telecommunications and Computer Engineering. These fields come from the Word source. Unknown
supervisor details remain blank.

## Source boundary and provenance

**What the import kept.** It preserves the supplied Word prose:

- the Introduction and the Theoretical Framework;
- three tables: the abbreviations table and two Chapter 2 tables;
- one research-process figure;
- 33 reference strings.

Chapters 3–6 keep their headings and, where present, empty structural sections only. Front-matter
sections without supplied content remain empty. No earlier draft prose, sample text, TODO marker
or invented completion text fills those gaps.

**Provenance.** The source DOCX SHA-256 is
`c589422a42318cf1635ad895cbe23cd24e2157ed569554a8ab3cd5dcaea25945`. See
[the import record](latex/WORD_IMPORT.md) and the
[machine-readable source manifest](latex/word-import-manifest.json) for provenance, scope and
verification evidence. The verification is sealed in
[`../docs/evidence/word-import-2026-09-17/`](../docs/evidence/word-import-2026-09-17/README.md).

**The template.** The conversion keeps the template's:

- `amsbook` class, 12 pt type, two-sided layout, A4 paper and 25 mm margins;
- Montserrat cover font and one-and-a-half line spacing;
- two covers and institutional logos.

Using this supplied template does **not** establish that it was the official 2026 template; that
question is supervisor decision D004, recorded as partly confirmed and reported by the student
([decision log](../docs/governance/supervisor_decision_log.csv)).

**What the conversion is.** It is a format conversion, not a scientific or bibliographic revision.
Integrated-Yocto wording comes from the supplied Word source. Its inclusion neither adopted a new
governance-plan version nor demonstrated implementation or supervisor approval. The import changed
no decision record and no claim state, and accepted no gate or claim.

**Dated note of 2026-09-18.** It concerns the imported 2026-09-17 text only. The
[governance plan](../docs/governance/INTEGRATED_DEVELOPMENT_PLAN_2026.md) was adopted separately,
as **version 2.0 with the QEMU-only execution amendment**, by a decision of the student. That was
not done by this import and not with supervisor approval. Chapter 1 of the imported text:

- states that the Yocto image boots as the operating system of a **native ARM64 virtual
  machine**;
- makes that an objective;
- describes an evaluation on a temporary, non-burstable native ARM64 virtual machine.

That evaluation was **outside the adopted scope** and was never carried out. The system was
evaluated under QEMU/TCG on an x86-64 host, as listed in [`../docs/results.md`](../docs/results.md).
The generated mirror under `sections/` was not edited to hide the divergence: an import never
silently corrects its source. The imported wording is therefore not a description of the
evaluated system.

## Source tree and generated mirror (historical version)

| Tree | Role |
|---|---|
| `latex/` | Editable source of the 2026-09-17 conversion |
| `sections/` | Generated Markdown mirror; never edit by hand |

```sh
python thesis/tools/generate_sections.py
```

The generator requires Pandoc. Regenerate the mirror in the same commit whenever the LaTeX
changes. Each generated file names its source in a `GENERATED FILE - DO NOT EDIT` banner. The
mapping is recorded in [manifest.yaml](manifest.yaml). Empty manuscript sections must stay empty
in the mirror as well.

## Layout and content of the conversion

```text
thesis/
├─ latex/
│  ├─ main.tex                   # supplied template with imported content
│  ├─ abbreviations.tex         # Word abbreviations table
│  ├─ word-import-support.tex   # formatting and verbatim-reference support
│  ├─ WORD_IMPORT.md            # import scope and verification record
│  ├─ word-import-manifest.json # source identity and inventory
│  ├─ imagens/                 # supplied logos and extracted research figure
│  ├─ ch2_supervisor_draft.tex  # derivative of the imported Chapter 2
│  └─ chapters/
│     ├─ 01_introduction.tex    # Word Introduction (2026-09-17)
│     ├─ 02_background.tex      # Word Theoretical Framework (2026-09-17)
│     ├─ 03_methodology.tex     # heading only
│     ├─ 04_architecture.tex    # headings only
│     ├─ 05_evaluation.tex      # heading only
│     └─ 06_conclusions.tex     # heading only
├─ refs/
│  └─ references.bib           # 33 reference strings preserved from Word
├─ research/                  # research records (see below)
├─ sections/                  # generated Markdown mirror
└─ manifest.yaml
```

## How to compile

The CI workflow still builds both documents of this historical version.

**Toolchain.** Use TeX Live with `latexmk`, Biber and the supplied template's packages, including:

- `amsbook`, `biblatex`, `montserrat`, `acronym` and `enumitem`;
- the table and graphics packages named in `latex/word-import-support.tex`.

On Debian/Ubuntu, install `cm-super` explicitly when using `--no-install-recommends`. The
template's font encoding with microtype expansion needs scalable T1 fonts. Without them, the CI
build failed with `auto expansion is only possible with scalable fonts`, although a complete local
TeX Live installation built successfully.

From `thesis/latex/`:

```sh
latexmk -pdf -interaction=nonstopmode -halt-on-error main.tex
latexmk -pdf -interaction=nonstopmode -halt-on-error ch2_supervisor_draft.tex
```

- **Manual sequence.** `pdflatex main`, `biber main`, then `pdflatex main` twice.
- **Bibliography path.** `../refs/references.bib`, relative to `thesis/latex/`.
- **Build outcomes** belong in the import record. The commands above are instructions, not a claim
  that a build passed.

## Bibliography and evidence boundaries

**Bibliography.** The template keeps IEEE `biblatex` with Biber. For this source-faithful import,
each Word reference is stored as the `note` of an `@misc` entry, with a custom driver that keeps
the supplied string. This is a documented import exception to the earlier convention of
structured, verified entries; no new metadata verification or correction is asserted. Do not
confuse the 33 imported strings with the separate historical research register or its earlier
verification counts.

**Rules for any further edit of this historical tree.** These are the project's evidence
discipline:

1. No quantitative project result without admitted raw data, a manifest, reproducible analysis
   and a corresponding [claim-evidence record](../docs/history/claim_evidence_matrix.md).
2. No invented implementation, physical-hardware, SSI, blockchain or security achievement.
   Word-source wording is not proof of an achievement.
3. Keep unprovided sections empty until separately authorised content exists. Do not restore
   former draft prose merely to complete the structure.
4. Do not infer supervisor approval of the title, RQs, template or manuscript from the
   conversion. Decisions D001 and D004 remain separate controls.
5. Never silently correct the source during an import.

## Research protocol and records

The [literature-review protocol](research/literature_review_protocol.md) and the research logs
are separate records. This conversion did not change their methods, searches or screening
outcomes.

**Protocol version 2.0.** On 2026-09-19, separately from the conversion, the protocol was revised
to version 2.0, a dated scoping-review protocol. The student reports the review type settled under
D003. The revision adds:

- the review question;
- the eligibility criteria;
- the charting fields;
- the five required outputs;
- the completion criterion;
- a working schedule.

It executed no search, screened no record and charted no study.

**Last changes.** The protocol was last changed on 2026-09-19. `search_log.csv` and
`study_selection.csv` were last changed in August 2026. They are kept as records of those dates.

**The current account.** The review as carried out is described in Section 2.1 of the current
manuscript, outside this repository. Section 2.1 of the imported 2026-09-17 text carries the
earlier description and was not updated in this tree.
