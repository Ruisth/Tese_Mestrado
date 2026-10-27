# S3 preparation — the one bounded check, what was applied, and the host preparation (2026-10-05)

## The check

One read-only check of the revised tooling before it touched the host, by two independent readers: (1) the operator
script `g3_battery.sh` with its README, operator procedure and step files; (2) the host-preparation, sealing, launcher
and row scripts. Their reports are in `check-record/` (`check-operator.md`/`.json`, `check-host.md`/`.json`; the
session's working path is masked as `<S>`). The first reader's run stopped on a usage limit and was run again; the
second reader's result was kept from the first run.

| Reader | Material | Minor | Wording |
|---|---|---|---|
| Operator script | 2 | 1 | 1 |
| Host preparation and sealing | 0 | 4 | 4 |

## Applied (scripts in `check-record/fix_*.py`)

- **O1 (material).** `row` accepted `EGW_G3_RUI_GO` to start a row after a recorded halt: the only path by which T9
  could start after a T8 halt, contrary to choice 2 and to the request's section 5. In S3 a recorded halt now refuses
  every further row, without exception; the variable is read only by `close` for a session closed outside the script.
- **O2 (material).** A tunnel lost after line d and reopened by the step preamble (`tunnel_check || tunnel_up`) was
  silent: the gate printed a note and passed, and steps e, f and every step of T9 did not look. Now a `TUNNEL UP`
  printed by the preamble of step e, step f, any T9 step or the gate after a row is a restoration and a halt (request,
  section 5, items 7 and 9). Steps b and c are excluded (the reboot killed the tunnel), as is line d (its own line).
- **O3 (minor).** A row classified invalid instrumentation now records a halt (it printed a note only).
- **O4 (wording).** The README says what still runs after a halt inside the steps (evidence reads, the gate).
- **H1-H8.** The operator's command lines (host-notes section 6) are one invocation per block with their own
  assignments, with the row check in clone mode and the dry run kept in the record folder; both sealing scripts of the
  operator records accept an `-attemptNN` suffix after a half-made package; the sealed README states the provenance of
  each diff correctly; two unreviewed digests were moved out of the folder before sealing; the write list of the host
  preparation and the failed-run sealing order are stated. The sealing bench was run again on the corrected scripts:
  76 PASS, 0 FAIL (`host-record/seal_bench.after-check.console.txt`).

The operator script changed (sha256 `142a5aad…` → `6009da1e…`), so every bench was run again, with six new scenarios
for O1-O3 (s13-s18). That pass found one defect of the correction itself (s18): after O3's halt, `classify` exited
before printing its next step (`close`); the halt was recorded and row t9 refused, only the guidance was missing. It
was corrected (classify now prints `Next: 'close', then hand back to Rui` before exiting on any halt of its own; the
README's table of halts names the new halt), giving the final sha256
`a77bd201a54d02620e625a620d2da796a8834289ec67daa808ed15324950f5cb`, and every scenario was run once more on those
bytes: `bench-notes.md` and `bench/record/final-pass.driver.txt`.

## Checked by the reader and left as it is

- The wait before line b (condition A): every poll is one recorded step run under `timeout min(20, remaining)`, never
  0; the budget starts at the end of step a on `/proc/uptime`; a poll counts only with exit status 0 and a whole answer
  of the kernel's boot-id form different from the saved one; 74 is a halt of its own; nothing resets the row's start
  instant or ceiling. The poll's ssh is the frozen `gx`'s own command (same key, port, user and known-hosts file), so
  the real host behaves as for S2's post-reboot read.
- Condition B: the script never starts, restarts or recreates anything on the guest, and never signals QEMU.
- The step files: byte-identical to the runbook blob with `-q2` removed; the carrier chain is the runbook's.
- The host preparation: the local-changes stop comes before any fetch or checkout; no reset, clean, stash or forced
  option anywhere; nothing written outside the clone, the helper file (predecessor kept) and the record folder.
- One point the reader could not settle: `verify_candidate` runs `git status --porcelain` in the Yocto checkout at the
  start of each row, with QEMU running. Read on 2026-10-05: the build directory `src/yocto/build-integrated/` that the
  launcher writes in is ignored by the checkout's `.gitignore`, and the status was clean after S1's and S2's closes, so
  a false halt there is not expected.

## The host preparation (record/)

Run once, on 2026-10-05 at 08:41Z, after the second reader's report and before the first reader's: `outcome=prepared`.
The execution clone moved from `80e833f…` (clean) to `8e492613d36490a560ae56beabd6d5c2c01a8696` (tree `2f05148…`,
clean, every branch unchanged); every identity of the request's section 2 matched, the four added ones included
(kernel, `qemuboot.conf`, the QEMU binary, the Yocto checkout at `489bc9e`, clean); the helper file regenerated from
the merged runbook is `e5eba37e…`, 545 lines, byte for byte the section 6.1 heredoc (its predecessor, the same bytes,
kept as `itest-helpers.sh.e5eba37e529a`); the five `-q2` identifiers unused on the host and on the guest's root file
system (read offline, `debugfs -c`, 37 entries including `.` and `..`); the root file system at `22e9da85…` before and
after the listing; T8's earlier attempt01 found in both places and no other attempt of t8 or t9. Then the row checker
in clone mode (exit 0) and the dry run (exit 0): `record/rows-check-clone-mode.console.txt`, `record/rows-dryrun.console.txt`.

Disclosed: on 2026-10-04 a read of the clone with a plain `git status` refreshed its index (the `.git` folder's time
changed); HEAD, tree and the clean status did not change.

## Not changed by this check

The candidate (no build, no image, no configuration), the frozen drivers, the runbook, any criterion. No guest ran.
