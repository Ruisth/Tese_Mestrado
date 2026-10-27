# G3 session S4 (test 6 only) — preparation delivered (2026-10-05)

Under the Project Manager's order after the merges of pull requests #55, #56 and #57 (relayed by Rui on 2026-10-05).
No guest ran. G3 stays `Not decided`. The request: `2026-10-05_g3-t6-session-request.md` (this folder).

## The package

`output_test/runs/2026-10-05/HIST_2026-10-05-g3-t6-host-preparation`: 268 files, `SHA256SUMS` sha256
`34715555f87e7ad3e8f48fe7cc847425b08c65276c82994dd4ea2dd065baafd4`, every entry verified; secret sweep 0 files (four secret variables, PEM headers); record outcome `prepared`. Its `README.md` says what each folder
holds; `verification/` holds the notes of the rows, operator, host and bench streams.

- **Merges checked:** `8cff703` (#55), `99ddf40` (#56), `1fd9792` (#57) on `dev`; the tree of `1fd9792` is `14f89c4`, the
  tree of the reviewed head `e375026`.
- **Host, 20:19Z:** the execution clone moved from `8e49261` (clean) to `1fd9792` (clean, branches unchanged); every
  identity of the request's section 2 equal; helpers `e5eba37e…` (545 lines) regenerated, predecessor kept; r04 unused
  on the host and on the guest's root file system; root file system `6fce1688…` before and after; data disk listed;
  the pilot plan `c195bd3f…` → `61d55940…` (r04, seed 1715385812, `planned`; the predecessor kept in the record). The
  row checker in clone mode: `ROW FILES OK`.
- **Operator script** `g3_battery.sh` `7a63b361…`; step file `t6.sh` `ec8ac010…`; manifest `rows/rows.manifest.json`
  `7d2a0f0d…`.

## What the checks found and what was done

- **One bounded check** (two readers) of the three streams' work: one material point — the procedure left the
  recovery value that decides "within 120 s" to Rui at classification; the request now states it (the packet's
  endpoint recovery, the functional one reported beside) and names it as a choice. Nine minor or wording points
  applied (the procedure's halt classes and console lines, the close remedy's scope, the sealing script refuses
  attempt-shaped names, two host checks that passed on a failed `git` now fail closed, the sealing command lines).
- **Bench** of the final script: 25 scenarios PASS on the real `t6.sh` and the real helper functions, with stand-ins for
  the harness, `analyze`, `itest_reconcile` and the guest; the script needed no correction.
- **One adversarial reading** of the bench: one material point — on the ceiling path (`term t6` during the harness),
  the TERM to the row's group also ends the step's console pipe, `harness_cmd`'s own cleanup can die before it runs,
  and the recorder unit stays active, so `close` halts. Not changed in the script (the step shell the three earlier
  sessions ran is kept); the README, the procedure and the request now prescribe the runbook's own recorder cleanup,
  recorded, before the close. One minor point: four of the pass scenario's checks cannot fail under the stubs; noted.
- **Final review** of the request and the operator documents (two readers): no material point; seven factual points (the occupation estimate, the stubbed parts named in full, the unverified items of Appendix B items 23 and 24, wording) and ten consistency points (the restart-once evidence in the pass row, the packet's stop rules carried over, the classes of `--exactly-once` exit 1 and 2, a missing recovery value and an interrupted row, the close when the guest is silent, the collector's install named as the one change, the packet's 'cause not established' rule, the amended criterion's date condition) applied before sealing; `--exactly-once` exit 1 is now the request's third stated choice.

## Correction of an earlier report

PR #57's description said the two failures of the final selection were "under the WSL clock". The Project Manager
noted that this is not shown. The description now reads: 2,475 passed and 2 failed (two real-time collector tests);
that module re-run alone on the final head, 242 passed; both results are kept; the failures are intermittent and their
cause is not established. Both packages (`…-integrated-attempt02`, `…-attempt03`) stay as sealed.

## Not verified anywhere but on the guest

The real harness with `--restart-transition-rule` on a live restart, the collector's uptime bounds, `--exactly-once` on
a real post-drain copy, `term` on the real harness, and the frozen preflight's collector install and deployed-tree
comparison against the moved clone.

## For S4

- Rui's explicit authorisation of one session (the request's section 9), then «estou presente» in the window.
- At the window: a fresh WSL keepalive with at least 6 h left and Windows kept awake; about 35–45 min expected.

## Attended time

About 1.3 h attended (2026-10-05 18:15–20:35Z, in spells between the workflows); about 2 h of agent and bench time unattended (build and check 46 min, bench and its adversarial reading 61 min, final review 11 min).
