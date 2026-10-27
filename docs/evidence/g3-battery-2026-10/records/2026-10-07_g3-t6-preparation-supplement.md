# G3 session S4 (test 6 only) — preparation supplement delivered (2026-10-07)

Under the Project Manager's opinion of 2026-10-07 (register line 4937), relayed by Rui: one operational correction
before S4 is authorised. No guest ran; no pull request; the candidate unchanged. G3 stays `Not decided`.

## The package

`output_test/runs/2026-10-07/HIST_2026-10-07-g3-t6-preparation-supplement`: 29 files, `SHA256SUMS` sha256
`74dbe1a9c8faf6ea1359c6cdac059ec21b98314669e454bc31a3d79fe71750f6`, every entry verified; secret sweep 0 files. The sealed preparation
`HIST_2026-10-05-g3-t6-host-preparation` (268 files, `34715555…`) is unchanged and verified before and after.

## The correction (only the recorder's emergency procedure)

- New `ops/g3_recorder_cleanup.sh` (`71ff2ceb…`): after `term t6` or `T6=incomplete`, **always before `close`**, the
  existing `events_capture.sh cleanup controller_restart-r04 KEEP_DIR`, unchanged, with `KEEP_DIR` explicit inside the
  session's package (`<session attempt>/recovery/events-partial-controller_restart-r04`), so the four files are kept
  as a partial capture and exported with the session at the close.
- Each try a recorded step bounded by `timeout 120`; at most three; any incomplete copy (`KEEP_DIR.copy.*`) kept and
  exported.
- `close` only after its `OK:` line (unit shown stopped on the guest, the four files present, both recorded);
  otherwise `HALT:` — no close, no forced power-off, no signal to QEMU; Rui decides.
- README and procedure updated for this path; `g3_battery.sh` (`7a63b361…`) unchanged.
- The PM's two clarifications written into the procedure: the endpoint recovery (`restart_metrics_endpoint_recovery_s`)
  measures from the end of the restart command to the first `/metrics` answer after it, not the whole unavailability
  nor the functional recovery (reported separately), and a missing or unreadable value never allows a pass;
  `--exactly-once` exit 1 is invalid instrumentation, never a demonstrated controller failure.

## The one offline verification

On the bench of the sealed preparation, the path itself: open S4, row t6, `term t6` (recorder left active, finding F1
reproduced), the REAL `events_capture.sh` of `1fd9792` against a stub guest, the new script, `close`:
- `supp-ok`: try 1 kept the four files; close; the session's package holds them and verifies (60 checks PASS);
- `supp-retry`: one copy failed in try 1, the incomplete copy kept; try 2 complete; close (55 PASS);
- `supp-hang`: one copy hung in try 1, ended by the 120 s bound (exit 124); try 2 complete; close (52 PASS);
- `supp-halt`: the unit never shown stopped: three tries, `HALT`, no close, nothing signalled (38 PASS).

Not verified: the real guest's `systemctl`, `ssh` and `scp`, the real close driver's export, a real TERM of the real
harness.

## Next

Rui's explicit authorisation of one session S4 (`controller_restart-r04`, tools `1fd9792`, request of 2026-10-05 with
this supplement; no automatic repeat, no further change), then «estou presente». A pass of T6 does not close G3: the
evidence is consolidated and the closing opinion follows separately.

## Attended time

About 0.4 h attended (2026-10-07 11:05–11:28Z); the offline verification ran unattended (about 4 min per round).
