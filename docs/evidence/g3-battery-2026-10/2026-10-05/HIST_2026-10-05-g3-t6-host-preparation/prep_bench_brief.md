# Bench of the S4 operator script (test 6 only) — brief (2026-10-05)

Read `P/brief.md` first (hard rules 1–8 apply unchanged; P, S, OT as defined there). You own `P/bench/` and
`P/bench-notes.md`; you may correct `P/g3_battery.sh` ONLY for a defect a bench shows (each correction under a comment
`S4 (bench <scenario>, 2026-10-05)`, re-run every scenario on the final bytes afterwards). Never touch the other files of
`P/`.

## The bench

Build on S3b's bench, `S/g3/s3bprep/bench/` (`bs3b_setup.sh`, `bs3b_run.sh`, `bs3b_all.sh`, `bs3b_stubs.py`,
`bs3b_untouched.sh`, `bs3b_env.sh`, `bs3b_fixture.sh`): copy what you need into `P/bench/` as `bs4_*`, change what S4
needs, keep the rest. Every scenario lives under `/tmp/g3-s4-bench/<scenario>` (refuse any other path), `HOME` and every
`EGW_*` inside it, stubs first on `PATH`, a fake QEMU process (a bash loop with a real `/proc/PID/cmdline`). The bench's
repository copy is taken from the read-only worktree `S/t6m` (the merged tree `14f89c4`), with the runbook blob
`P/runbook.1fd9792.md` as the clone's runbook; the four session drivers are stubs in the copy only. The helper file and
`tunnel.sh` are written by the runbook's own heredocs (sha256 compared with `e5eba37e…` and `38f5cae9…`). The script runs
IN PLACE (`P/g3_battery.sh`, with `P/rows/`). The `sha256sum` stub must answer the S4 expected root file system value
(`6fce1688…`), and the collector check must see the clone copy's real collector (`9e678b02…`).

The REAL step file `P/rows/t6.sh` runs in the step shell with the REAL helper functions of the regenerated helper file
(`harness_cmd`, `wait_ready`, `drained`, `config_identity`, `events_start`, `stop`, …); what those helpers call is
stubbed. Reuse the repository's own stubs (`S/t6m/src/tests/test_runbook_itest_helpers.py`: `STUB_SSH`, `STUB_CURL`,
`STUB_PYTHON`, `STUB_SCP`, `STUB_SS`, `STUB_SLEEP`, `STUB_TIMEOUT`, `STUB_SUDO`, `STUB_DOCKER`, the `Bench` class and the
test 6 tests at lines 1191-1420 and 1657-1770, which show how the module itself drives test 6's lines and what files the
helpers expect, e.g. `identity_capture`). The module's `STUB_PYTHON` records the harness's argv and exits with
`harness_rc` but writes no run directory: add, in the bench's venv `python` wrapper, a harness stand-in for
`-m egw_experiments run` that writes `~/egw-tcg/pilot/results/raw/<run_id>/` the way the harness would for the case under
test (`manifest.json` with `drain.outcome`, `resources_proved_down`, `resources_transition_rows`; `SHA256SUMS`;
`events.post-drain.jsonl`; `logs/simulator/<run_id>/sent_events.jsonl` and its `manifest.json`; `logs/sut/controller.log`)
and exits with the case's code; an `analyze` stand-in that writes `processed/per_run.csv`; `itest_reconcile` `delta`
and `acceptance` exit codes per case (`rec_delta_rc`, `rec_acceptance_rc`); `plan-supplement` is never called by the
row. Say in the notes which parts are real and which are stand-ins.

## Scenarios (each console saved as `P/bench/record/<scenario>.console.txt`, starting with the sha256 of the script run)

1. **pass**: open S4 (stub drivers end 0), row t6 (harness 0, drain `quiet`, `delta` 0, `--exactly-once` 0, analyze 0),
   classify (`complete valid pass …`), close. Show: the console's `test 6:` lines, the transition-record line, the
   attempt's name `…_g3-qualification-t6_attempt02`, the authority text in the workload field, the snapshot before/after,
   `guest_state_delta.py --expect-restarted egw-controller-1`, the gate after, close's `compose stop -t 130`.
2. **labels**: `open S1`, `open S2`, `open S3` refused (exit 2, the consumed-authority text); `row t8`, `row t9`,
   `row t5` refused as unknown; `open S4` a second time refused while open.
3. **freshness**: (a) `~/egw-tcg/pilot/results/raw/controller_restart-r04` exists: row refused, nothing started;
   (b) r04 not in the plan; (c) r04 with status other than `planned`; (d) `~/egw-tcg/itest/controller_restart-r04.twins.before.json`
   exists; (e) S2's `…_g3-qualification-t6_attempt01` present in the attempts directory: admitted; (f) another earlier
   t6 attempt present: NOT FRESH; (g) the export tool names the new attempt `…_attempt03`: halt before any step.
4. **identities**: at open (a) the clone's collector differs from `9e678b02…`; (b) `drivers_sha256` differs; (c) the root
   file system differs from `6fce1688…`: halt, nothing started; (d) the gate record differs from S2's: halt before t6.
5. **preflight non-zero**: the stub preflight ends non-zero (exit 1, and exit 3): HALT at open, no environment copy, no
   gate; no exception path exists (grep the script: no `EXCEPTION`, no `s3b_preflight_exception`).
6. **row outcomes** (the runbook's own lines, through the operator script): harness exit 1 (INVALID) → `T6=stop`, no
   `delta`, no `--exactly-once`; harness exit 2 → the "not started" line; harness exit 3 → `T6=incomplete`; drain
   `gave-up` → `T6=gaveup`, no `delta`; `delta` 4 → its STOP line, and `--exactly-once` still runs (line 1427 reads `T6`
   only); `--exactly-once` 4 and 1 →
   their STOP lines. In each, the attempt stays open for classification and a halt is recorded only where the script
   records one (say which).
7. **term**: `term t6` while the harness stand-in sleeps: TERM to the row's process group, the attempt exported as
   interrupted, the fake QEMU and the keepalive untouched.
8. **after a halt**: a recorded halt refuses a second `row t6`; `classify` then `close` work.
9. **integrity**: the script changed while the session is open → `row` refused; a row file changed → refused (manifest).

After the benches: no fake process left; nothing written outside `/tmp/g3-s4-bench` and `P/bench/`; the real
`~/egw-exec`, `~/egw-tcg` (plan sha256 `c195bd3f…`) and `OT` untouched (hashes or listing times before and after).

Deliver `P/bench-notes.md`: per scenario what was run, expected, observed (quote the decisive console lines), PASS or
FAIL; every defect found, the correction (line numbers) and the re-run; the final sha256 of `P/g3_battery.sh`; what was
NOT benched and why.
