"""The supplement of 2026-10-07 (the Project Manager's order, register line 4937): the recorder's emergency cleanup
keeps the partial capture inside the session's package (ops/g3_recorder_cleanup.sh), and the two clarifications of
the request's choices. Edits the supplement's copies of the README and the procedure only.
Usage: python fix_docs_supp.py <t6supp>"""
import sys
from pathlib import Path

T = Path(sys.argv[1])

LAUNCH = ("`MSYS_NO_PATHCONV=1 wsl -d Ubuntu-24.04 --exec bash -lc 'EGW_EXEC_REPO=$HOME/egw-exec/repo bash "
          "<P>/ops/g3_recorder_cleanup.sh'`")


def edit(name, pairs):
    p = T / name
    s = p.read_bytes().decode("utf-8")
    assert "\r\n" not in s, name
    for old, new in pairs:
        assert s.count(old) == 1, (name, old[:100])
        s = s.replace(old, new)
    p.write_bytes(s.encode("utf-8"))


edit("g3_battery.README.md", [
    ("""| for that unit only: the runbook's own cleanup (`bash $EGW_CLONE/tools/session/events_capture.sh cleanup controller_restart-r04`, the remedy `harness_cmd`'s own STOP names), by hand through `hx` on the attempt that is open (after `term t6` that is the session's attempt: the row's is already exported), three tries at most: recorded; then `close` again.""",
     """| for that unit only: `ops/g3_recorder_cleanup.sh` (supplement of 2026-10-07; below, "The recorder's emergency cleanup"), then `close` again only after its `OK:` line; its `HALT:` means do NOT close: hand back to Rui."""),
    ("""Only the runbook's own exist — the recorder's capture cleanup after `harness_cmd` answered 3 or after `term t6`
(bench F1), `tunnel_down && tunnel_up` — and each is run by hand through the frozen `hx` on the attempt that is open,
never to let the row go on.""",
     """Only the runbook's own exist — the recorder's capture cleanup after `harness_cmd` answered 3 or after `term t6`
(bench F1), run by `ops/g3_recorder_cleanup.sh` (below), and `tunnel_down && tunnel_up`, run by hand through the
frozen `hx` on the attempt that is open — never to let the row go on.

### The recorder's emergency cleanup (supplement of 2026-10-07)

**When:** after `term t6` (the ceiling) and after `T6=incomplete` (`harness_cmd` answered 3), **always, before
`close`** — also when no unit is listed active: a recorder stopped with its capture still only in the guest's
`/tmp/egw-events-controller_restart-r04` would pass the close's unit check and be lost at the power-off.

**Launch (one invocation, foreground):** """ + LAUNCH + """

**What it does:** the existing command, unchanged, `events_capture.sh cleanup controller_restart-r04 KEEP_DIR` of the
clone, with `KEEP_DIR` = `<session attempt>/recovery/events-partial-controller_restart-r04`, inside the session's
attempt, which the frozen close driver exports with the session's package. The command stops the unit if it is not
shown stopped, then copies the recorder's four files (`events.partial.jsonl`, `lifecycle.txt`, `start-facts.txt`,
`cli-stderr.txt`) as a partial capture, never as the run's `docker-events.log`, write-once; a staging folder that
holds some files (`KEEP_DIR.copy.*`) is kept and exported too. Each try is a recorded step of the session's attempt
(`recorder-cleanup-controller_restart-r04-tryN`) bounded by `timeout 120`; at most three tries. After a try that
ended 0, two recorded confirmations: the unit's state on the guest (`inactive` or `failed`) and the four files listed
with their sha256.

**Its answers:** `OK: … 'close' may run` (exit 0): run `close`. `HALT: … do NOT run 'close' …` (exit 1): stop there;
nothing was signalled or powered off; the guest's capture stays in its `/tmp` while the guest is up; hand back to
Rui (no forced power-off, no signal to QEMU). `REFUSED:` (exit 2): nothing ran (no open session, no S4 state
directory, or a subcommand of `g3_battery.sh` still holds its turn). A second invocation after an `OK` adds no try:
it confirms again. The script never runs `close`, never powers anything off and never signals any process."""),
])

edit("operator-procedure.md", [
    ("""(2) No row, recorder or collector running. After `term t6` (the ceiling) the recorder `egw-events-controller_restart-r04`
may be left running (bench F1): `close` then halts with nothing stopped; its remedy is the runbook's own cleanup
(`bash $EGW_CLONE/tools/session/events_capture.sh cleanup controller_restart-r04`) through `hx` on the session's
attempt, three tries at most, recorded, then `close` again; the harness's collector unit ends by itself at its
600 s bound. Any other unit left active: record it, stop nothing by hand, hand back to Rui.""",
     """(2) No row, recorder or collector running. After `term t6` (the ceiling) or `T6=incomplete`, **always before
`close`**: `ops/g3_recorder_cleanup.sh` (supplement of 2026-10-07; launch line and answers in the README, "The
recorder's emergency cleanup"). It runs the existing `events_capture.sh cleanup controller_restart-r04 KEEP_DIR` with
`KEEP_DIR` inside the session's package (`recovery/events-partial-controller_restart-r04`), each try a recorded step
bounded by 120 s, at most three, any incomplete copy kept; `close` runs only after its `OK:` line (the unit shown
stopped and the four files kept). A `HALT:` is a stop: no `close`, no forced power-off, no signal to QEMU; Rui
decides. The harness's collector unit ends by itself at its 600 s bound. Any other unit left active: record it, stop
nothing by hand, hand back to Rui."""),
    ("""(`restart_functional_recovery_s`). "Recovery within 120 s" is read on `restart_metrics_endpoint_recovery_s` (the
packet's T6 row: "endpoint recovery ≤ 120 s"; the runbook's Expected: samples resuming within 120 s), as the request
states in section 6; that reading is one of the request's stated choices, so another reading is Rui's decision before
S4, never at classification.""",
     """(`restart_functional_recovery_s`). "Recovery within 120 s" is read on `restart_metrics_endpoint_recovery_s` (the
packet's T6 row: "endpoint recovery ≤ 120 s"; the runbook's Expected: samples resuming within 120 s), as the request
states in section 6. *(2026-10-07, the Project Manager's opinion on the request's choices:)* that value measures from
the end of the restart command (the restart record's `finished_utc`) to the first `/metrics` sample after it — the HTTP
endpoint answering again; it measures neither the whole unavailability nor the functional recovery, which stays
reported separately; a missing or unreadable value never allows a pass. `--exactly-once` exit 1 is invalid
instrumentation, never a demonstrated failure of the controller."""),
])
print("docs edited")
