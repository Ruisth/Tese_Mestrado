# G3 — decisions of 2026-10-05 on T5's interpretation and T6's criterion

**Decision record.** The student's decisions of 2026-10-05: «Para o T5 seguimos a recomendação do Senior Project
Manager, para o T6 seguimos com a opção 2». Both are prospective in effect; neither alters data, a package, a seal
or an earlier verdict, and neither accepts a family, a gate or a claim. G3 stays `Not decided` in the
[gate decision log](gate_decision_log.md). Narrative: LOG #C052. The sources are the Project Manager's register entry
of 2026-10-05, 13:42 WEST, and the one-page T6 choice of the same date (both held locally, outside the repository).

## T5 — the interpretation of the disconnection count

Row 7 of the battery, `itest-dropout-01-q1` (2026-10-02,
[results addendum](g3-battery-2026-10-results.md)): the broker log bounded to the run holds four connections and four
disconnection lines. **Adopted reading:** three deliberate fault disconnects, each followed by a reconnect, plus the
simulator's normal terminal teardown, reported separately. With that reading the row's classification is **Pass**,
as sealed. Kept as recorded: the 2,016 messages confirmed in time (`lost` 0, `late` 0), the 3 deliberate dropouts and
165 buffered records, and the `check` warning about C10 (a documented layout mismatch). **No C10 claim is admitted.**

## T6 — the criterion of the controller-restart family (option 2)

**Adopted criterion, for test 6 only, for runs made after 2026-10-05** (it replaces, for test 6, the timed-family
obligation of decision 3 of 2026-09-30 in
[the pending-decisions page](proposals/2026-09-29-g3-pending-decisions.md)):

> T6 passes when the controller is restarted once mid-run with recovery within 120 s, every valid message is accepted
> exactly once in the post-drain copy (none absent, none duplicate-only, `double_accepted` 0), and every `delta` line
> reads OK. `lost` and `late_confirmations` against the marker plus 60 s are reported for T6 beside the result and
> recorded as a sizing finding; they are not a pass condition of T6. This applies to runs made after its dated
> adoption only.

**Where it is written:** the runbook's "Timed families" paragraph and test 6's Expected paragraph
([`qemu_integrated_gateway.md`](../setup/qemu_integrated_gateway.md), dated amendments that keep the earlier text for
earlier runs), and the G3 paragraph of plan section 4.3
([`INTEGRATED_DEVELOPMENT_PLAN_2026.md`](INTEGRATED_DEVELOPMENT_PLAN_2026.md)).

**Consequences:**

- Every other timed family keeps `lost = 0` and `late_confirmations = 0` against the marker plus 60 s: test 1's three
  runs, test 2, test 4's sequence reset, test 5 and test 8's post-reboot smoke.
- C12 cannot claim timely delivery at the nominal rate under TCG; the shortfall (`controller_restart-r03`: 2,002 of
  6,720 beyond the deadline; `nominal-r02`, without a restart: 2,136) is a sizing finding. The campaign's C12
  condition and its gate in `analyze.py` are unchanged; C12 stays pending in the
  [claim matrix](../claim_evidence_matrix.md).
- `controller_restart-r03` stays invalid and is not re-judged.

**Not decided:** a lower load, a longer deadline, C12 as pilot-only.

## What test 6 still needs

*(Updated 2026-10-05, later: the student adopted option A of the T6 page with the Project Manager's conditions —
admissible transition rows count for the distinct instants, the existing coverage calculations and the existing
aggregates — and authorised one offline tooling pull request; LOG #C053. Items 0 to 3 are implemented there, offline,
with regressions; nothing has run on the guest.)*

0. "Accepted exactly once", judged per identity: `itest_reconcile acceptance --exactly-once` on the post-drain copy,
   a guarded line of test 6's block after `delta` (exit 1: not evaluated; exit 4: test 6 fails). The plain
   `acceptance` finds absent identities only, and `delta` compares the twins with the accepted lines, not with the sent
   identities.
1. The collection-validity rule: option A, qualified, as `run --restart-transition-rule 1a-option-a-2026-10-05`
   (explicit; without it every run behaves as before). Transition rows of the restarted controller in
   sec(D) < t ≤ min(sec(S), sec(E)) are admitted only on the same container's unambiguous disappeared → appeared pair in
   the run's lifecycle record; they are reported separately in the manifest (`resources_transition_rows`); every other
   check, D/S/E, the 120 s cap, both 5 s edges and the other services are unchanged; `analyze.py` is unchanged. Options
   B and C are not implemented; the four F2 qualifications are fixed in the
   [T6 page](proposals/2026-10-03-t6-sampling-versus-restart-events.md).
2. `collector-duration` judged on the collector's paired uptime bounds from one boot (`uptime_s=` and `boot_id=` on
   its `start:` and `stop:` records), UTC kept for coverage and diagnosis, the tolerance unchanged; missing, malformed,
   reversed or cross-boot bounds fail closed. The collector's sha256 changes (instrumentation, not the system under
   test).
3. A fresh plan entry, `controller_restart-r04` (the frozen load: 11.2 msg/s for 600 s, restart at 300 s), to be
   added to the host's pilot plan at the next preparation by `python -m egw_experiments plan-supplement --plan <pilot
   plan> --entry g3-t6`; r01–r03 untouched.
4. Then, after a preparation that records the new tooling identity, installs the new collector through the preflight
   and adds r04, one separately authorised bounded session on the unchanged candidate.
