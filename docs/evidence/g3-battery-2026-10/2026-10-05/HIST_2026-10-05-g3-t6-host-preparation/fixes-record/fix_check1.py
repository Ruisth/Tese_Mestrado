"""The bounded check of the S4 preparation (2026-10-05): the procedure, README, seal and bench-brief points.
Usage: python fix_check1.py <P>"""
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


edit("operator-procedure.md", [
    # OP-4: the line-1425 else branch and the unexpected drain outcome
    ("""`STOP: test 6: the harness run was not sealed, or it exited N …` with the `[harness] INVALID:` lines above it (exit 1, the reasons) |""",
     """`STOP: test 6: the harness run was not sealed, or it exited N …` with the `[harness] INVALID:` lines above it (exit 1, the reasons); `STOP: test 6: the harness exited 0 but the manifest's drain outcome is '…'` (classified by the manifest); `STOP: test 6: controller_restart-r04 refused as already used (F6='…'), no seed, not ready, not drained or no configuration identity - the harness run was NOT started` (the else branch of line 1425: not started) |"""),
    ("""any non-zero is followed by `STOP: test 6: delta NOT run … or it exited non-zero` |""",
     """any non-zero is followed by `STOP: test 6: delta NOT run … or it exited non-zero`. With `T6` not `ok` the same `STOP` shows `(T6='<value>')` and `delta` did not run: it adds nothing to the class `T6` already gives |"""),
    ("""The exit status itself is not printed: the line that precedes the `STOP` names it |""",
     """The exit status itself is not printed: the line that precedes the `STOP` names it. With `T6` not `ok` the `STOP` shows `(T6='<value>')` and the check did not run. The line reads `T6` only, so it also runs after a `delta` MISMATCH |"""),
    # OP-1: the endpoint recovery decides
    ("""the row `run_id=controller_restart-r04`: `restart_metrics_endpoint_recovery_s` and `restart_functional_recovery_s` (with `restart_functional_recovery_source`; the bound is 120 s, `RESTART_RECOVERY_MAX_S`),""",
     """the row `run_id=controller_restart-r04`: **`restart_metrics_endpoint_recovery_s`** decides "recovery within 120 s" (`RESTART_RECOVERY_MAX_S`; request, section 6); `restart_functional_recovery_s` and `restart_functional_recovery_source` are reported beside it,"""),
    # OP-5: the broker values are nested
    ("""`broker_conf_sha256` `ea37827c…`; `max_inflight_messages` 4999, `max_queued_messages` 1000, `max_inflight_bytes` 0, `max_queued_bytes` 0, `persistent_client_expiration` `1h`, `sys_interval` 10;""",
     """`broker_conf_sha256` `ea37827c…`; `broker_conf_values`: `max_inflight_messages` 4999, `max_queued_messages` 1000, `max_inflight_bytes` 0, `max_queued_bytes` 0, `persistent_client_expiration` `1h`, `sys_interval` 10;"""),
    # OP-2: halts before the step, each case named
    ("""transcript or export failure, is instrumentation (request, section 5 item 2); a halt before the step (the gate's image
record, the attempt's name) ran nothing, and an attempt that exists is classified not started. A failed gate after the""",
     """transcript or export failure, is instrumentation (request, section 5 item 2). Halts before the step: the gate's image
record halt creates no attempt (nothing to classify); the attempt-name halt is classified `not-applicable/not-run`; the
halts after the attempt exists and before the step (attempt fields, copies, sources, guest state before, snapshot
before) are instrumentation, `invalid/unknown`. A failed gate after the"""),
    ("""sizing finding), `resources_transition_rows`, `resources_proved_down`, the N1 report. The request does not say which
of the two recovery columns is "recovery within 120 s": the packet's T6 row of 2026-10-01 names the endpoint recovery,
and `analyze.py` calls the functional one "the readiness gate". Both are read and written in the result note; if they
fall on different sides of 120 s, the class is Rui's decision, not the operator's.""",
     """sizing finding), `resources_transition_rows`, `resources_proved_down`, the N1 report, and the functional recovery
(`restart_functional_recovery_s`). "Recovery within 120 s" is read on `restart_metrics_endpoint_recovery_s` (the
packet's T6 row: "endpoint recovery ≤ 120 s"; the runbook's Expected: samples resuming within 120 s), as the request
states in section 6; that reading is one of the request's stated choices, so another reading is Rui's decision before
S4, never at classification."""),
])

edit("g3_battery.README.md", [
    # OP-2
    ("""| no step of the row was run | classify by cause (instrumentation: `invalid/unknown`); `close`; hand back |""",
     """| no step of the row was run | classify `invalid/unknown` (instrumentation; the same in the operator procedure); `close`; hand back |"""),
    # OP-3
    ("""| `harness_cmd`'s cleanup failed (its `STOP` and `T6=incomplete` say so) | the runbook's own cleanup (`bash $EGW_CLONE/tools/session/events_capture.sh cleanup controller_restart-r04`), by hand through `hx` on the open attempt, three tries at most: a restoration, recorded; then `close` |""",
     """| read the unit's name in the `g3-close-units` console. Only `egw-events-controller_restart-r04` after `T6=incomplete` (`harness_cmd`'s cleanup failed) has a prescribed remedy | for that unit only: the runbook's own cleanup (`bash $EGW_CLONE/tools/session/events_capture.sh cleanup controller_restart-r04`), by hand through `hx` on the open attempt, three tries at most: a restoration, recorded; then `close`. Any other active unit (an `egw-resources-*` one, or another run id): no prescribed cleanup in S4; record it, stop nothing by hand, hand back to Rui |"""),
])

edit("seal_prep.sh", [
    # F1: no name the export tool numbers attempts by
    ("""mkdir -p "$PKG" || exit 2
cp -r "$REC" "$PKG/part1-record" || exit 1""",
     """# S4 (bounded check of 2026-10-05, F1): nothing sealed may carry a name the export tool numbers attempts by
# (<stamp>_<slug>_attemptNN): such a name under output_test would shift S4's attempt number and halt row t6.
bad=$(find "$REC" "$SRC/rows" "$SRC/bench" "$SRC"/*-record -regextype posix-extended \\
    -regex '.*/[0-9]{8}T[0-9]{6}Z_[A-Za-z0-9-]+(_[A-Za-z0-9-]+)*_attempt[0-9]{2,}' -print 2>&1)
[ -z "$bad" ] || refuse "the preparation holds names the export tool numbers attempts by: $bad"

mkdir -p "$PKG" || exit 2
cp -r "$REC" "$PKG/part1-record" || exit 1"""),
    # F5
    ("""echo "copied: ${LEFT:-nothing} (base/ holds the copies the diffs were made against; the other files are copies of the"
echo "repository's files at 1fd9792 given to the preparation for reading)." """.rstrip(" "),
     """echo "copied: ${LEFT:-nothing} (base/ holds the copies the diffs were made against; preflight.1fd9792.sh and"
echo "test_runbook_itest_helpers.1fd9792.py are copies of the repository's files at 1fd9792 given for reading; any other"
echo "entry named is a working folder of the preparation, not part of it)." """.rstrip(" ")),
])

edit("bench-brief.md", [
    # F4
    ("""`gave-up` → `T6=gaveup`, no `delta`; `delta` 4 → its STOP line and `--exactly-once` not run; `--exactly-once` 4 and 1 →""",
     """`gave-up` → `T6=gaveup`, no `delta`; `delta` 4 → its STOP line, and `--exactly-once` still runs (line 1427 reads `T6`
   only); `--exactly-once` 4 and 1 →"""),
])
print("fixed")
