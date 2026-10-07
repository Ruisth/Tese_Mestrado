"""The bench's finding F1 (2026-10-05): the ceiling path's recorder unit gets the runbook's own cleanup, recorded,
before the close; documents only (the script is unchanged). Usage: python fix_bench1.py <P>"""
import sys
from pathlib import Path

P = Path(sys.argv[1])


def edit(name, pairs):
    p = P / name
    s = p.read_bytes().decode("utf-8")
    assert "\r\n" not in s, name
    for old, new in pairs:
        assert s.count(old) == 1, (name, old[:100])
        s = s.replace(old, new)
    p.write_bytes(s.encode("utf-8"))


edit("g3_battery.README.md", [
    ("""Only `egw-events-controller_restart-r04` after `T6=incomplete` (`harness_cmd`'s cleanup failed) has a prescribed remedy | for that unit only: the runbook's own cleanup (`bash $EGW_CLONE/tools/session/events_capture.sh cleanup controller_restart-r04`), by hand through `hx` on the open attempt, three tries at most: a restoration, recorded; then `close`.""",
     """Only `egw-events-controller_restart-r04` has a prescribed remedy: after `T6=incomplete` (`harness_cmd`'s cleanup failed), and after `term t6` (S4, bench F1: the TERM to the row's group also ends the step's console pipe, so `harness_cmd`'s own cleanup can die before it runs) | for that unit only: the runbook's own cleanup (`bash $EGW_CLONE/tools/session/events_capture.sh cleanup controller_restart-r04`, the remedy `harness_cmd`'s own STOP names), by hand through `hx` on the attempt that is open (after `term t6` that is the session's attempt: the row's is already exported), three tries at most: recorded; then `close` again. The harness's collector unit `egw-resources-controller_restart-r04` ends by itself at its `--duration 600` bound: wait for it read-only and run `close` again."""),
    ("""Only the runbook's own exist — the recorder's capture cleanup after `harness_cmd` answered 3, `tunnel_down &&
tunnel_up` — and each is run by hand through the frozen `hx` on the attempt that is open, never to let the row go on.""",
     """Only the runbook's own exist — the recorder's capture cleanup after `harness_cmd` answered 3 or after `term t6`
(bench F1), `tunnel_down && tunnel_up` — and each is run by hand through the frozen `hx` on the attempt that is open,
never to let the row go on."""),
    ("""- `term t6` during the harness (TERM to the whole group, `harness_cmd`'s own trap and cleanup) is the battery's design
  and was not exercised for t6 in any bench.""",
     """- `term t6` during the harness (TERM to the whole group, `harness_cmd`'s own trap and cleanup) is the battery's design.
  The bench of the final script (`bench-notes.md`, F1) ran it against the test module's stubs: the TERM also ends the
  step's console pipe, `harness_cmd`'s cleanup died of SIGPIPE and the recorder unit stayed active, so `close` halted.
  With the real `events_capture.sh` (its guest command goes over `ssh`) the outcome is a race, not shown. The script
  is not changed for it: the close row above prescribes the runbook's own recorder cleanup, recorded, before `close`
  runs again. On the real harness and guest the path has never run."""),
    ("""- **On the guest, nothing of the S4 changes has run.** The changed paths were exercised in an isolated bench
  (`operator-record/bs4_op.sh`, eight scenarios, consoles beside it) with stub `ssh`, `git`, `pgrep`, `ps`,
  `sha256sum`, four stub session drivers and a stand-in `t6.sh` that writes what the runbook's block leaves on the
  host; the runbook's block itself (the harness, the hooks, `delta`, `acceptance --exactly-once`, `analyze`) was not
  run by this preparation.""",
     """- **On the guest, nothing of the S4 changes has run.** The changed paths were exercised in two isolated benches:
  the operator stream's (`operator-record/bs4_op.sh`, eight scenarios, a stand-in `t6.sh`) and the bench of the final
  script (`bench/`, `bench-notes.md`: the REAL `t6.sh` through the script with the real helper functions, 20 scenarios
  PASS), both with stub `ssh`, `git`, `pgrep`, `ps`, `sha256sum` and four stub session drivers. The harness, `analyze`
  and `itest_reconcile` were stand-ins giving each case's files and exit codes: the real harness, the transition
  rule's computation, `delta` and `acceptance --exactly-once` on real files were not run by this preparation."""),
])

edit("operator-procedure.md", [
    ("""(1) Fetches and cleanups first (the runbook's own, three tries at most; the guest's `/tmp` is lost at power-off).
(2) No row, recorder or collector running.""",
     """(1) Fetches and cleanups first (the runbook's own, three tries at most; the guest's `/tmp` is lost at power-off).
(2) No row, recorder or collector running. After `term t6` (the ceiling) the recorder `egw-events-controller_restart-r04`
may be left running (bench F1): `close` then halts with nothing stopped; its remedy is the runbook's own cleanup
(`bash $EGW_CLONE/tools/session/events_capture.sh cleanup controller_restart-r04`) through `hx` on the session's
attempt, three tries at most, recorded, then `close` again; the harness's collector unit ends by itself at its
600 s bound. Any other unit left active: record it, stop nothing by hand, hand back to Rui."""),
])

edit("request-draft.md", [
    ("""At 47 min the row receives TERM to its process group (never KILL, never QEMU) and is exported as interrupted. Host: a""",
     """At 47 min the row receives TERM to its process group (never KILL, never QEMU) and is exported as interrupted; the
Docker events recorder of r04 can then be left running (found by the preparation's bench): the runbook's own cleanup of
it, recorded, precedes the close. Host: a"""),
])
print("fixed")
