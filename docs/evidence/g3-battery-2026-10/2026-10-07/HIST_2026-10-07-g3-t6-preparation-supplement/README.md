# G3 session S4 (test 6 only) — preparation supplement (2026-10-07)

**What this is.** A supplement to the sealed preparation `HIST_2026-10-05-g3-t6-host-preparation` (268 files,
`SHA256SUMS` `34715555…`), which stays as sealed: its `SHA256SUMS` was verified before and after this package was
made. Order: the Project Manager's opinion of 2026-10-07 (register line 4937), relayed by Rui: the emergency procedure
for the run's Docker events recorder stopped the recorder but named no place to keep its partial capture, which the
guest's power-off at the close would then lose. Only that procedure is corrected; no pull request, no change to the
candidate, no general battery. No guest ran.

## The correction

- **`ops/g3_recorder_cleanup.sh`** (new; sha256 `71ff2ceb496ae60d71ef50bb076f10f5d8bb798422afa97ad1a3dd1b239d7b3b`): after `term t6` or `T6=incomplete`, always before
  `close`, it runs the existing command of the clone, unchanged — `events_capture.sh cleanup controller_restart-r04
  KEEP_DIR` (`1fd9792`, sha256 `b06b8678…`) — with `KEEP_DIR` explicit inside the session's attempt,
  `recovery/events-partial-controller_restart-r04`, which the frozen close driver exports with the session's package.
  The four files (`events.partial.jsonl`, `lifecycle.txt`, `start-facts.txt`, `cli-stderr.txt`) are kept as a partial
  capture, never as the run's `docker-events.log`; a staging folder holding some files (`KEEP_DIR.copy.*`) is kept and
  exported too.
- Each try is a recorded step of the session's attempt, bounded by `timeout 120`; at most three tries.
- `close` runs only after the script's `OK:` line: the unit shown stopped on the guest and the four files kept (both
  confirmations recorded). Otherwise `HALT:`: no `close`, no forced power-off, no signal to QEMU; Rui decides.
- `g3_battery.README.md` and `operator-procedure.md`: the close row, the restorations paragraph, a section "The
  recorder's emergency cleanup" with the launch line, and the controlled close's item (2) (diffs in
  `verification/diffs/`). The steps script `g3_battery.sh` (`7a63b361…`) is unchanged.
- The Project Manager's two clarifications, written into the procedure: "recovery within 120 s" read on
  `restart_metrics_endpoint_recovery_s` measures from the end of the restart command to the first `/metrics` sample
  after it — neither the whole unavailability nor the functional recovery, which stays reported separately — and a
  missing or unreadable value never allows a pass; `--exactly-once` exit 1 is invalid instrumentation, never a
  demonstrated failure of the controller.

## The one offline verification

`bench/bsupp_run.sh` (built by `make_bsupp.py` from the sealed bench's `bs4_run.sh`: its helpers unchanged but for
three path lines; `bsupp_setup.sh` is the sealed `bs4_setup.sh` reading the sealed predecessor plan `c195bd3f…`
instead of the host's, which holds r04 since the preparation). On the path the procedure is for: open S4, row t6 with
the harness stand-in asleep, `term t6` — the recorder unit left active (the preparation's finding F1, reproduced) —
then, in the bench copy only, the REAL `events_capture.sh` of `1fd9792` in place of the test module's stub, the new
script, then `close`. Four cases, each a console in `bench/record/`:

| Case | Fault | Observed | Checks |
|---|---|---|---|
| `supp-ok` | none | try 1 exit 0; the four files kept, equal to the guest's; both confirmations recorded; a second invocation adds no try; `close` exit 0; the session's package holds `recovery/events-partial-controller_restart-r04/` and its `SHA256SUMS` verifies | 60 PASS |
| `supp-retry` | the copy of `cli.stderr` fails once | try 1 exit 1 (3 of 4 copied, the incomplete folder kept and named); try 2 exit 0; `close`; the package holds the four files and the incomplete folder | 55 PASS |
| `supp-hang` | the copy of `events.jsonl` hangs once | try 1 ended by the bound, exit 124, after about 120 s; the hung copy ended; try 2 exit 0; `close` | 52 PASS |
| `supp-halt` | the unit is never shown stopped | three tries exit 1, nothing copied, `HALT: … do NOT run 'close'`; no close, no power-off, the fake QEMU unchanged, the session still open | 38 PASS |

In every case the steps script run was `g3_battery.sh` `7a63b361…` (unchanged) and nothing was written outside
`/tmp/g3-s4-bench/` and this folder; the bench read the sealed predecessor plan and S3's sealed gate record only.

Not verified: the real guest's `systemctl`, `ssh` and `scp` (stubs answered the cleanup script and the copies), the
frozen close driver's export of a real session (the stub close driver exported the bench's session through the same
export tool), and the path on a real TERM of the real harness.
