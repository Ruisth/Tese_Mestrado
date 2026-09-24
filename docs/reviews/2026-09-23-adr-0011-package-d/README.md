# Review record of ADR 0011 — package D (2026-09-20 to 2026-09-24)

This directory is the review record that
[ADR 0011](../../adr/0011-controller-restart-recovery.md) cites: the analyses
its figures depend on, the four gate notes that answer its gate items, the
refutation check applied to the folded record, the verification reports, the
review annex and the decision request the student answered. It is a record,
not a decision: nothing here accepts a gate, admits a claim or changes a rule.
The ADR's relative citations (`gates/…`, `scripts/…`, `out/…`,
`backlog_diagnosis.md`, `adr-0011-review-annex.md`) resolve from this
directory. Line numbers inside these files refer to the versions of the other
files as they were when each was written; the ADR's own line numbers moved as
it was revised, so a citation of the form ADR `:n` is approximate.

| file | what it is |
|---|---|
| `controller_today.md`, `restart_evidence.md` | the first analyses (2026-09-20): the controller's behaviour read from the source at `35fe8bb`, and the two restart runs' evidence |
| `backlog_diagnosis.md` (v3) | the diagnosis of the delivery backlog under QEMU/TCG (`nominal-r01`), with its scripts under `scripts/` and outputs under `out/` |
| `gates/item1_broker_limits.md` … `item4_drained.md` | the four gate notes of 2026-09-21 (I1–I4), with their scripts (`gates/scripts/`, `gates/item4_*.sh|py`), outputs (`gates/out/`, `gates/item4_*.out.txt`) and the hashes of the documentation they read (`gates/sources/SHA256SUMS.txt`) |
| `gates/check.md` | the refutation check of the folded record (18 findings), applied on 2026-09-23 |
| `adr-0011-review-annex.md` | the corrections to the unnumbered draft of 2026-09-20 and of the second review round |
| `verify_figures.md`, `verify_constraints.md` | the verification of the record's figures and constraints (`scripts/verify/`, `scripts/verify_constraints/`, outputs under `scripts/verify/out/` and `out/verify_constraints/`) |
| `decision_request.md` | the decision request of 2026-09-21 in English, updated with the broker measurement's result (2026-09-23) and the project manager's corrections D1–D3 (2026-09-23); the student answered it, with the project manager's note of 2026-09-24, on 2026-09-24 |

**Not kept here, and where it is.** The third-party documentation copies the
gate notes read (`gates/sources/`: the mosquitto.org pages, the change log,
the MQTT 3.1.1 standard, `mosquitto.conf(5)` of 2.0.22) are identified by
`gates/sources/SHA256SUMS.txt` and are not committed; `html2txt.py` is the
converter used. The guest files extracted for item 2 (`gates/item2_extract/`:
the journal, both restart runs' event logs and the lines carved from the data
disk) are the evidence package
`output_test/runs/2026-09-21/HIST_2026-09-21-r02-guest-disk-recovery` held
outside the repository; `gates/out/item2_extract.SHA256SUMS.txt` lists their
hashes. Superseded versions of the notes (`gates/prefold/`, `gates/precheck/`)
are not kept; the review annex and `gates/check.md` record what changed. The
Portuguese decision page the student answered, and the project manager's
notes, are held with the project manager's records outside the repository.
Scripts cite their working directory as `<review-record>` or `<scratchpad>`:
they were run from a session scratchpad that no longer exists, against the
inputs each names, and are kept for reading, not for re-running as they are.
