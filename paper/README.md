# Paper — IEEE Article (Deferred)

The scientific article is **out of scope until after the thesis submission**.
Section 4.5 of the adopted plan keeps the article and the detailed defence
preparation outside P0 and records the article as **deferred, not deleted**: the
student **reports** that a supervisor said it is optional and not required for
delivery, that it may improve the grade without any guarantee, and that it
therefore leaves mandatory acceptance and the critical path. That is reported by
the student, not a documented supervisor decision, and it removes no obligation
from the thesis itself. Planned submission is **2026-10-20**, with 2026-10-21 to
2026-10-31 a contingency window for essential corrections only; the article is
considered after the thesis and its evidence are secure, not inside that window.
Nothing is drafted in this directory before then. The earlier wording here cited
the archived Portuguese v1.0 plan and assumed a September 2026 submission; both
are superseded. See
[`../docs/governance/INTEGRATED_DEVELOPMENT_PLAN_2026.md`](../docs/governance/INTEGRATED_DEVELOPMENT_PLAN_2026.md)
§4.5.

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
