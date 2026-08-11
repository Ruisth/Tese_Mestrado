# Assembly prompt for the conference paper

**Status: not to be used yet.** The paper is deferred until the dissertation is
submitted (plan section 4.5). Assembling it earlier competes for the hours the
dissertation needs.

When the time comes, the assembly is mechanical: the paper is *extracted* from
the dissertation, never written in parallel with it. Everything it claims must
already be backed by archived evidence.

## Prompt

> Assemble `paper-assembled.md` from the files listed in `paper/manifest.yaml`,
> in the order given there.
>
> Rules:
>
> 1. Every factual claim must already appear in the dissertation
>    (`thesis/sections/`). Do not introduce a claim, a number or a comparison
>    that is not there. If something reads as a gap, report it instead of
>    filling it.
> 2. Every quantitative value must be traceable to `experiments/results/` and
>    to the run identifiers named in `experiments/results.md`. A value with no
>    traceable origin is removed, not rounded or hedged.
> 3. Cite only entries present in `paper/refs/references.bib`, which is a
>    filtered subset of the dissertation bibliography under the policy in
>    `refs/venue-policy.md`. Never add a reference during assembly.
> 4. Respect the word limit in `manifest.yaml`. Cut discussion before cutting
>    method or threats to validity.
> 5. Keep the limitations honest: the platform, scope and evaluation boundaries
>    stated in the dissertation carry over unchanged.
> 6. Figures come from `paper/figs/`, exported from
>    `experiments/results/figures/`. Do not redraw or re-render them.
>
> Output a single Markdown file. Do not modify any source section.

## After assembly

- Check the terminology question recorded in `refs/venue-policy.md` has been
  settled with the supervisor.
- Confirm no claim in the paper is stronger than the same claim in the
  dissertation.
- Convert to the venue template only after the content is final.
