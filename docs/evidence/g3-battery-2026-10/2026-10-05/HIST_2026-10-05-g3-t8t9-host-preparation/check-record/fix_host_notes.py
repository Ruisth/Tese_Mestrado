"""Replace section 6 of host-notes.md (findings H1, H2, H5, H6, H8 of the bounded check). Usage: python fix_host_notes.py <host-notes.md>"""
import sys
from pathlib import Path

p = Path(sys.argv[1])
s = p.read_bytes().decode("utf-8")
assert "\r\n" not in s
a = s.index("## 6. Command lines for the operator")
b = s.index("## 7. Deviations from the brief")
NEW = r'''## 6. Command lines for the operator

Each BLOCK below is ONE `wsl -d Ubuntu-24.04 --exec bash -lc '…'` invocation (login shell; `MSYS_NO_PATHCONV=1` when
launched from the Windows shell) and begins with its own assignments: a new `bash -lc` keeps no variable of a previous
one. `P` is the WSL path of the preparation folder.

**Host preparation** (no QEMU, no open session). It writes, in the clone: the fetched objects (and any tag that follows
them), `FETCH_HEAD`, HEAD with its reflog, the index and the ten working-tree files that differ between `80e833f…` and
`8e49261…`; `~/egw-tcg/itest-helpers.sh`, rewritten, with its predecessor kept beside it as
`itest-helpers.sh.e5eba37e529a`; the record folder; nothing outside these.

    P=<WSL path of s3prep>; bash "$P/g3_hostprep.sh" "$P/record"; echo "exit=$?"

Expected: last line `outcome=prepared (at …)`, exit 0. A `STOP:` line ends it with `outcome=failed` and exit 1; exit 2
means the record folder already holds a console (use another folder: nothing is overwritten). A stop after the
checkout leaves the clone at `8e49261…` (the script reverts nothing).

**Then** the row checker in clone mode and the dry run, with their consoles kept in the record folder (which
`seal_prep.sh` copies whole); both must end with exit 0 before sealing:

    P=<WSL path of s3prep>; bash "$P/g3_check_rows.sh" "$P/rows" > "$P/record/rows-check-clone-mode.console.txt" 2>&1; echo "exit=$?" | tee -a "$P/record/rows-check-clone-mode.console.txt"
    P=<WSL path of s3prep>; bash "$P/g3_rows_dryrun.sh" "$P/rows" "$P/g3_check_rows.sh" "$P/runbook.8e49261.md" > "$P/record/rows-dryrun.console.txt" 2>&1; echo "exit=$?" | tee -a "$P/record/rows-dryrun.console.txt"

**Seal the preparation** (writes `output_test`; reads the real `.env` for the sweep, printing names only):

    P=<WSL path of s3prep>; OT="/mnt/c/Users/ruimf/Documents/Projeto Mestrado/output_test"; D=$(date -u +%F); bash "$P/seal_prep.sh" "$P" "$P/operator-procedure.md" "$OT/runs/$D/HIST_$D-g3-t8t9-host-preparation"; echo "exit=$?"; (cd "$OT/runs/$D/HIST_$D-g3-t8t9-host-preparation" && sha256sum -c --quiet SHA256SUMS && echo verified)

Exit 0: sealed, record `prepared`. Exit 3: sealed, record not `prepared`. Exit 2: refused, nothing created (the text
says what is missing). Exit 1: a secret value or a private-key header is in the copy, which is left unsealed: report
it, delete nothing. After a FAILED host preparation, seal its record first with the default record folder (exit 3 is
expected), then, after a second run into another record folder, seal that one as
`…/HIST_$D-g3-t8t9-host-preparation-attempt02` with the new record folder as fourth argument; the session uses the
package whose record ends `prepared`.

**During S3** (only after Rui's authorisation and his go in the window):

    P=<WSL path of s3prep>; bash "$P/ops/g3_go.sh" open S3     # then: row t8 | row t9 | close
    P=<WSL path of s3prep>; bash "$P/ops/g3_wait.sh" row t8    # waits again for a subcommand already launched

For `open` and `row` an optional third argument is the wait in minutes (default 170); for `close` it is given as
`close session <minutes>`.

**Seal the operator records after the close.** `DP` is the date in the name of the SEALED preparation package (a
literal: recomputing it on the day of S3 would name a folder that does not exist); `DS` is the UTC date folder that
holds the session's packages. The classification notes are expected in `$P/ops/notes/` as in S1 and S2.

    P=<WSL path of s3prep>; OT="/mnt/c/Users/ruimf/Documents/Projeto Mestrado/output_test"; DP=<date of the preparation package>; DS=<UTC date folder of the session>; bash "$P/ops/seal_ops.sh" S3 "$P/ops" "$OT/runs/$DS/HIST_$DS-g3-t8t9-s3-operator-records" "$OT/runs/$DP/HIST_$DP-g3-t8t9-host-preparation"; echo "exit=$?"; (cd "$OT/runs/$DS/HIST_$DS-g3-t8t9-s3-operator-records" && sha256sum -c --quiet SHA256SUMS && echo verified)

Only if `seal_ops.sh` was interrupted after its copy began (never to pass a sweep that stopped):

    P=<WSL path of s3prep>; OT="/mnt/c/Users/ruimf/Documents/Projeto Mestrado/output_test"; DP=<…>; DS=<…>; bash "$P/ops/seal_ops_finish.sh" S3 "$OT/runs/$DS/HIST_$DS-g3-t8t9-s3-operator-records" "$OT/runs/$DP/HIST_$DP-g3-t8t9-host-preparation"; echo "exit=$?"

A half-made operator-records package that `seal_ops_finish.sh` also refuses is left as it is; the records are then
sealed again under `HIST_$DS-g3-t8t9-s3-operator-records-attempt02` (both scripts accept that suffix), and the
half-made one is named in the result note.

'''
s = s[:a] + NEW + s[b:]
p.write_bytes(s.encode("utf-8"))
print("section 6 replaced")
