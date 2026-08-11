# Paper — IEEE Article (Deferred)

The scientific article is **out of scope until after the thesis submission**.
The integrated plan (§4.5) explicitly excludes "artigo científico e preparação
detalhada da defesa antes da submissão": if the thesis is submitted in
September 2026, October may be used for the paper without reopening the
submitted artefact. Nothing is drafted in this directory before then.

## Template to use when the paper starts

The paper follows the structure defined in the C2DTA Student Repository
Template (`../../C2DTA Student Repository Template.docx`):

```
paper/
├─ sections/
│  ├─ 01_abstract.md
│  ├─ 02_intro.md
│  ├─ 03_related-work.md
│  ├─ 04_method.md
│  ├─ 05_results.md
│  ├─ 06_discussion.md
│  └─ 07_conclusion.md
├─ figs/                  # images referenced in sections
├─ refs/
│  ├─ references.bib      # DOIs only (template rule: no arXiv/MDPI)
│  └─ venue-policy.md     # citation policy + venue checklist
├─ manifest.yaml          # section order + metadata for assembly
└─ README-GPT.md          # assembly prompt
```

Notes for that future work:

- Target style: IEEE conference format; word limit and venue set in
  `manifest.yaml` when the venue is chosen.
- The template's constraints (peer-reviewed DOIs only; C2DTA terminology;
  SSDT/SSPDT distinction) are revisited against the chosen venue's policy at
  that time. Where a template constraint conflicts with this repository's
  normative contracts (e.g. the contracts use the term "telemetry"
  normatively), the venue policy decision is recorded in
  `refs/venue-policy.md` before writing.
- All results in the paper come from the thesis evidence base
  (`../experiments/results/` + `../docs/claim_evidence_matrix.md`); the
  no-numbers-without-evidence rule applies unchanged.
