# G3 — T6 collection validity: Option A adopted, with the Project Manager's conditions (2026-10-05)

**Rui's words, 2026-10-05:** «Minha autorização: Segue a opção A do Senior Project Manager», given on the Project
Manager's opinion (register entry "2026-10-05 15:14 WEST") and its proposed sentence: «Aprovo a Opção A com as
condições do PM, contando as leituras de transição válidas nos três usos indicados. Autorizo o bloco offline das três
entregas, num único PR. Não autorizo alterações ao sistema nem uma sessão; essa autorização será posterior.»

## The rule adopted (prospective, for the new G3 T6 run)

The T6 proposal's **option A**, qualified: readings of the restarted controller taken during the restart transition,
zero values actually measured included, **count** for the 30 distinct instants, **take part** in the existing coverage
calculations and **enter** the existing descriptive CPU/RAM aggregates, within the current analysis window.

Conditions (adopted together, register entry of 15:14 WEST):
- every raw row and byte kept, observed zeros included; no interpolation, no synthetic zeros, no deletion, no
  replacement of a missing sample, and the outage is never declared measured;
- only the restarted controller, with the existing D/S/StartedAt/complete-capture prerequisites and matching identity;
  transition stamps in sec(D) < t ≤ sec(S), sec(S) > sec(D), never beyond sec(E) when capped; the same-second case
  stays conservative;
- the same container's unambiguous disappeared → appeared pair in this run's lifecycle record, at the positions option
  A specifies; a missing, wrong, late, inconsistent or unreadable witness grants nothing; a zero alone proves nothing;
- distinct observed instants counted, not rows times services; every per-container minimum and measured-window
  restriction kept; the coverage formula, its denominator and the edges of the lifecycle exemption unchanged;
- D/S/E, the 120 s cap, both 5 s edge checks and the rules of the five other services unchanged; transition count,
  stamps and values reported separately;
- the aggregates describe cgroup resources in the window, not a ready service; the lifecycle witness is the same
  instrument, not independent proof;
- the rule's identity recorded for the new G3 T6 run; no campaign criterion adopted; r03's verdict and packages
  unchanged (its fixture may exercise the code offline).
`analyze.py` is not changed. Options B and C are not implemented. The F2 qualifications are fixed in the proposal's
prose.

## The offline block authorised (one pull request)

1. Option A as above, with regressions.
2. `collector-duration` judged on paired guest-monotonic start/stop bounds from the same boot, UTC kept separately for
   coverage and diagnosis, the existing tolerance kept; missing, malformed, reversed or cross-boot bounds never fall
   back to UTC or pass.
3. One fresh T6 plan entry with the original load and durations, no identifier overwritten.

One targeted regression selection, one consolidated review, CI on the final head, evidence in `output_test` with the
identity captured first; a checkpoint at 2 attended hours if unfinished. **Not authorised:** any change to the system
under test (no controller change, no build), any session. G3 stays `Not decided` until a valid T6 under the adopted
criteria exists.
