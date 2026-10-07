# G3 session S3 (tests 8 and 9) — preparation delivered (2026-10-05)

Under the decision summary of 2026-10-04 (`2026-10-04_g3-t8-t9-s3-decision-summary.md`). No guest ran. G3 stays
`Not decided`.

## The package

`output_test/runs/2026-10-05/HIST_2026-10-05-g3-t8t9-host-preparation`: 288 files, `SHA256SUMS` sha256
`1dc610d18751dcccc17111ca94b6b465fd7819cb2b2b6298f5c85f5b6c23a72f`, every entry verified; secret sweep 0 files; record
outcome `prepared`. Its `README.md` quotes the record's decisive lines; `verification/check-notes.md` and
`verification/bench-notes.md` say what was checked and benched.

- **Operator script** `g3_battery.sh` sha256 `a77bd201a54d02620e625a620d2da796a8834289ec67daa808ed15324950f5cb`; step
  files and manifest `rows/rows.manifest.json` `678b9203…` (six lines of test 8 and four of test 9 extracted verbatim
  from the merged runbook with `-q2`, plus the exposure step).
- **Host, 08:41Z:** execution clone moved from `80e833f` (clean) to `8e492613…` (tree `2f05148…`, clean, branches
  unchanged; choice 1); every identity of the request's section 2 equal to the recorded value, the four added ones
  included; helper file `e5eba37e…` (545 lines) regenerated, predecessor kept; the five `-q2` identifiers unused on the
  host and on the guest's root file system; root file system `22e9da85…` before and after; T8 will be attempt02, T9
  attempt01. Row check against the clone and dry run: exit 0.

## What the checks found and what was done

- **One bounded check** before the scripts touched the host (two readers). Two material defects of the operator
  script, both corrected: (O1) `EGW_G3_RUI_GO` let a row start after a recorded halt, so T9 could have run after a T8
  halt; in S3 a halt now refuses every further row. (O2) a tunnel lost after line d and reopened by the step preamble
  passed silently; it is now a restoration and a halt (steps e, f, every step of T9, the gate). Also corrected: a row
  classified invalid instrumentation records a halt; the host and sealing scripts' minor points (command lines, an
  `-attemptNN` suffix for a half-made operator-records package, provenance text).
- **Benches** on the real step files against stubs: 38 scenarios, all PASS on the final bytes (including the real
  900 s wait expiring as "reboot not shown", output followed by 124 or 255 not counted, a genuine success counted,
  `-no-reboot` stopping before line a, a halt refusing T9 even with `EGW_G3_RUI_GO` set). The re-run found one defect
  of a correction (classify named no next step after its own halt), corrected and re-run.
- Found on the way: `debugfs` exits 0 on a missing directory; the first preparation's freshness read would have
  reported every identifier fresh over an empty listing. The S3 script requires the listing's `.` and `..`.

## Not verified anywhere but on the guest

The corrected test 8 lines and the operator script's T8 flow against a real reboot (ssh under `timeout` against a
booting guest, the QEMU same-process reading, the tunnel at line d), `wait_ready 3600` after a reboot, test 9 on this
candidate.

## For S3

- Rui's explicit authorisation of the session (for example the Project Manager's sentence of 2026-10-04: *"Autorizo a
  preparação e uma única sessão S3 com T8/T9, usando `8e49261`, com as quatro escolhas e as duas condições do parecer
  do PM. Sem rebuild, alterações ao candidato, repetições ou aceitação automática do G3. Entrega primeiro a preparação
  selada e aguarda o meu «estou presente» para arrancar. Guarda e verifica todos os resultados em `output_test`."*),
  then «estou presente» in the window.
- At the window: a fresh WSL keepalive with at least 6 h left and Windows kept awake (the script refuses `open S3`
  otherwise); about 30–45 min expected.

## Attended time

About 1.6 h attended for the preparation (three spells); about 4.3 h of agent and bench time unattended.
