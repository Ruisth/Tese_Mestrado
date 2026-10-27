# Paper — IEEE Article (Deferred, not started)

> **Status: deferred. Nothing has been written.** This folder is a placeholder for a scientific
> article planned for after the dissertation. Each of the seven section files holds only a "Not
> started" notice, the bibliography has no entries and `figs/` holds only its README. Nothing here is part of the dissertation or of
> its results. The results are listed in [`../docs/results.md`](../docs/results.md).

## Why it is deferred

The scientific article is **out of scope until after the thesis submission**.
Section 4.5 of the adopted plan keeps the article and the detailed defence
preparation outside the mandatory core of the project and records the article as
**deferred, not deleted**: the student **reports** that a supervisor said it is
optional and not required for delivery, that it may improve the grade without any
guarantee, and that it therefore leaves mandatory acceptance and the critical
path. That is reported by the student, not a documented supervisor decision, and
it removes no obligation from the thesis itself. The article is considered after
the thesis and its evidence are secure. Nothing is drafted in this directory
before then. See
[`../docs/governance/INTEGRATED_DEVELOPMENT_PLAN_2026.md`](../docs/governance/INTEGRATED_DEVELOPMENT_PLAN_2026.md)
§4.5.

**Superseded planning dates.** When this file was last revised (2026-09-19), it
gave the planned submission as **2026-10-20**, with 2026-10-21 to 2026-10-31 as a
contingency window for essential corrections only, and it placed the article
outside that window. Those were the planning dates of that time. They are kept
here as a record and are not the current schedule. An earlier wording cited the
archived Portuguese v1.0 plan and assumed a September 2026 submission; both are
superseded as well.

## Template to use when the paper starts

The paper follows the structure defined in the C2DTA Student Repository
Template, a Word file kept outside this repository:

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
└─ manifest.yaml          # section order + metadata for assembly
```

The template also places an assembly prompt, `README-GPT.md`, in this folder.
That prompt was marked "not to be used yet". It is now kept as a record in
[`../docs/history/paper/README-GPT.md`](../docs/history/paper/README-GPT.md).
It names `thesis/sections/` as the dissertation; that folder is now the
historical mirror of the LaTeX conversion of 2026-09-17
([`../thesis/README.md`](../thesis/README.md)), not the current dissertation.

Notes for that future work:

- Target style: IEEE conference format; word limit and venue set in
  `manifest.yaml` when the venue is chosen.
- The template's constraints (peer-reviewed DOIs only; C2DTA terminology;
  SSDT/SSPDT distinction) are revisited against the chosen venue's policy at
  that time. Where a template constraint conflicts with this repository's
  normative contracts (e.g. the contracts use the term "telemetry"
  normatively), the venue policy decision is recorded in
  `refs/venue-policy.md` before writing.
- All results in the paper come from the thesis evidence base, now indexed in
  [`../docs/results.md`](../docs/results.md); the no-numbers-without-evidence
  rule applies unchanged. The pointers this file gave earlier were
  `../experiments/results/` (never filled, because the planned campaign was not
  run) and the claim–evidence matrix, now kept as a record in
  [`../docs/history/claim_evidence_matrix.md`](../docs/history/claim_evidence_matrix.md).
