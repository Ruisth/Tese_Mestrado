# G3 — T5 interpretation and T6 criterion: Rui's decisions (2026-10-05)

**Rui's words, 2026-10-05:** «Para o T5 seguimos a recomendação do Senior Project Manager, para o T6 seguimos com a
opção 2».

Both decisions are prospective in effect and alter no data, package, seal or earlier verdict. G3 stays `Not decided`.

## T5 — the interpretation of the disconnection count (the Project Manager's recommendation, register entry 2026-10-05 13:42 WEST)

**Adopted reading.** In row 7 of the battery (`itest-dropout-01-q1`, 2026-10-02), the bounded broker log's four
connections and four disconnection lines are read as **three deliberate fault disconnects, each followed by a
reconnect, plus the simulator's normal terminal teardown, reported separately**. With that reading the row's
classification is **Pass**, as sealed.

**Kept as recorded:** the 2,016 messages confirmed in time (2,016 of 2,016, `lost` 0, `late` 0), the 3 deliberate
dropouts and 165 buffered records, and the `check` warning about C10 (a documented layout mismatch).

**Not admitted:** no C10 claim (the campaign condition's evidence is separate and absent). No data changes and the
package is untouched.

## T6 — Option 2 of the decision page of 2026-10-05 (`2026-10-05_g3-t6-decision-page.md`)

**Adopted criterion for test 6, prospective, for test 6 only** (replaces, for test 6, the timed-family obligation of
decision 3 of 2026-09-30):

> T6 passes when the controller is restarted once mid-run with recovery within 120 s, every valid message is accepted
> exactly once in the post-drain copy (none absent, none duplicate-only, `double_accepted` 0), and every `delta` line
> reads OK. `lost` and `late_confirmations` against the marker plus 60 s are reported for T6 beside the result and
> recorded as a sizing finding; they are not a pass condition of T6. This applies to runs made after its dated
> adoption only.

**Consequences, as the page states them:**

- Decision 3 is reversed for test 6 alone; every other timed family (test 1's three runs, test 2, test 4's sequence
  reset, test 5, test 8's post-reboot smoke) keeps `lost = 0` and `late_confirmations = 0` against the marker plus
  60 s.
- Plan section 4.3's G3 paragraph is amended in the same dated decision (the exact text is in the repository's
  decision record, LOG #C052): "no threshold moved" holds for every family except test 6's delivery deadline, which is
  reported and recorded as a sizing finding.
- C12 cannot claim timely delivery at the nominal rate under TCG. The dissertation states the shortfall
  (`controller_restart-r03`: 2,002 of 6,720 beyond the deadline; `nominal-r02`: 2,136) as a sizing finding. The
  campaign's C12 condition and its gate are not changed by this decision.
- `controller_restart-r03` stays invalid; nothing is re-judged. T6 needs one valid new run on the unchanged candidate,
  after the offline tooling prerequisites: a collection-validity rule adopted prospectively (the T6 page's option A
  with the Project Manager's F2 qualifications, which needs Rui's explicit choice on whether transition rows,
  zero-valued ones included, count for the 30-instant and coverage checks and the aggregates); `collector-duration`
  judged on paired monotonic bounds; a new `controller_restart` plan entry. Each of these, and the session, is a
  separate step; no session is authorised by this decision.
- Not decided and not proposed: a lower load, a longer deadline, C12 as pilot-only.
