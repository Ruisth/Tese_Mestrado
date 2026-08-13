# Thesis — Dissertation Sources and Research Protocol

Dissertation skeleton for the EGW project (Tema 1, C2DTA), based on the
official ISCTE LaTeX template (`../../Template_LaTeX/`). The dissertation body
is written in English; the Resumo is in Portuguese (integrated plan, header +
§4.3). The normative plan for structure and content is
[`../docs/governance/INTEGRATED_DEVELOPMENT_PLAN_2026.md`](../docs/governance/INTEGRATED_DEVELOPMENT_PLAN_2026.md) §6.

## Two representations of the same dissertation

The repository template asks for a Markdown-first `thesis/sections/` tree; the
institution requires the LaTeX template and that is what is submitted. Both
exist here, with one rule that keeps them from drifting:

| Tree | Role |
|---|---|
| `latex/` | **The single edited source.** Everything is written here. |
| `sections/` | **Generated mirror.** Overwritten on every generation run. |

```bash
python thesis/tools/generate_sections.py     # requires pandoc
```

Every generated file carries a `GENERATED FILE - DO NOT EDIT` banner naming its
source. The section-by-section mapping, and the three places where the
dissertation's six chapters do not line up with the template's eleven sections,
are documented in `manifest.yaml`.

Regenerate the mirror whenever the LaTeX changes, in the same commit — a stale
mirror is worse than no mirror, because it looks current.

## Layout

```
thesis/
├─ latex/
│  ├─ main.tex               # ISCTE template adapted; \input of the six chapters
│  ├─ imagens/               # iscte.png, ista.png (copied from Template_LaTeX)
│  └─ chapters/
│     ├─ 01_introduction.tex
│     ├─ 02_background.tex
│     ├─ 03_methodology.tex
│     ├─ 04_architecture.tex
│     ├─ 05_evaluation.tex   # empty result slots marked \todo{pending data-v1}
│     └─ 06_conclusions.tex
├─ refs/
│  └─ references.bib         # VERIFIED entries only ("% verified <date> via <source>")
├─ research/
│  ├─ literature_review_protocol.md   # structured scoping/narrative review protocol
│  ├─ search_log.csv                  # one row per executed query
│  └─ study_selection.csv             # one row per candidate record
└─ README.md
```

## How to compile

Requires a standard TeX Live installation (2022 or later, `scheme-full`
recommended: the template uses `amsbook`, `biblatex` with the `biber`
backend, `montserrat`, `acronym`, `enumitem`, `booktabs`, `xcolor` — all
present in TeX Live full).

Preferred (from `thesis/latex/`):

```sh
latexmk -pdf main.tex
```

Manual sequence:

```sh
pdflatex main
biber main
pdflatex main
pdflatex main
```

The bibliography is loaded from `../refs/references.bib` (relative to
`thesis/latex/`), so compile from inside `thesis/latex/`.

## Hard rules (normative)

1. **No number without evidence.** No quantitative result enters any chapter
   without raw data, a manifest, the analysis script, and a row in
   [`../docs/claim_evidence_matrix.md`](../docs/claim_evidence_matrix.md)
   (plan §6.3). Chapter 5's result slots are `\todo{pending data-v1}` markers
   and are filled only after the data freeze (`data-v1`, gate G5), exclusively
   from `experiments/results/raw/` via the single analysis pipeline.
2. **Zero `\todo` at submission.** `main.tex` defines
   `\newcommand{\todo}[1]{\textcolor{red}{[TODO: #1]}}`; the final PDF must
   contain no `\todo` occurrence (grep the sources before release).
3. **Forbidden claims** (plan §9.2): no invented numbers; no Raspberry Pi 5 /
   physical-hardware results; no SSI, blockchain or security achievements
   beyond the implemented TLS/authentication baseline; no absolute
   "no studies exist" statements (bound them to the review protocol).
4. **Verbatim RQs.** RQ1–RQ3 in Chapter 1 are quoted verbatim from plan §4.2
   and must not drift.
5. **Bibliography.** Only verified entries (each with a
   `% verified <date> via <source>` comment). The compass file is a leads
   list, never a citation source. Target: >= 30 verified sources by gate G6
   (2026-09-18) via `research/literature_review_protocol.md`.
6. **Placeholders.** `«STUDENT NAME»`-style front-matter fields are
   administrative placeholders; fill them manually, never with invented data.

## Chapter-to-plan mapping (plan §6.1; word targets are indicative only)

| File | Chapter | Mandatory content (plan §6.1) | Indicative target |
|---|---|---|---:|
| `chapters/01_introduction.tex` | 1 — Introduction | Problem, motivation, gap, RQs (verbatim §4.2), objectives, contributions-as-designed, delimitation | 2,500–3,000 words |
| `chapters/02_background.tex` | 2 — Background and Related Work | Edge, digital twins, IoT/wearables, Yocto, containers, MQTT, WoT; SSI as context only | 6,000–7,000 |
| `chapters/03_methodology.tex` | 3 — Research Methodology | DSR with build–evaluate cycle, review protocol, requirements, RQ→method→metric matrix (§4.2 + §7.2), experimental protocol (§7) | 4,000–5,000 |
| `chapters/04_architecture.tex` | 4 — Architecture and Implementation | Real implemented design only, mirroring `../src/CONTRACTS.md`; interfaces, EGW-OS, stack, simulator, security, reproducibility | 5,000–6,000 |
| `chapters/05_evaluation.tex` | 5 — Evaluation and Discussion | Measurement methodology now; results only after `data-v1`; RQ answers; threats to validity | 5,000–6,000 |
| `chapters/06_conclusions.tex` | 6 — Conclusions and Future Work | Contributions demonstrated (evidence-backed only), limitations, future work | 1,500–2,000 |

The global 25,000–30,000-word target is indicative and subordinate to the
official rules and to evidence quality (plan §6.1).

## Research protocol

The literature study is a **structured scoping/narrative review — not an
SLR**. Protocol, search strings, criteria, deduplication, snowballing,
verification rule and the CSV logging specification:
[`research/literature_review_protocol.md`](research/literature_review_protocol.md).
