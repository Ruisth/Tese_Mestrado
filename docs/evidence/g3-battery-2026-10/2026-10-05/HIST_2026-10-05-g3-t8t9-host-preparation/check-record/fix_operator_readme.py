"""Findings O1-O4 of the bounded check of the S3 preparation (2026-10-05).
Usage: python fix_operator.py <s3prep dir>"""
import sys
from pathlib import Path

P = Path(sys.argv[1])


def edit(path, pairs):
    p = P / path
    s = p.read_bytes().decode("utf-8")
    assert "\r\n" not in s, path
    for old, new in pairs:
        assert s.count(old) == 1, (path, old[:80])
        s = s.replace(old, new)
    p.write_bytes(s.encode("utf-8"))


edit_skip = ([
    # O1: in S3 a recorded halt ends the session; EGW_G3_RUI_GO no longer lets a row start after it
    ('''    if [ -n "$(state_get "$f" halt)" ]; then
        [ -n "${EGW_G3_RUI_GO:-}" ] || refuse "NOT STARTED: session $LABEL has a recorded halt ($(state_get "$f" halt)). A halt cancels further progress until Rui directs otherwise; with his explicit go, set EGW_G3_RUI_GO to his words (they are recorded)"
        go=$EGW_G3_RUI_GO
        echo "session $LABEL has a recorded halt; EGW_G3_RUI_GO is set and is recorded: $go"
    fi
''',
     '''    # S3 (bounded check of 2026-10-05, O1): a recorded halt ends the session. No variable
    # lets a further row start after it (decision summary, choice 2: a procedural,
    # instrumentation or safe-state halt does not permit continuation; request, section 5:
    # "Test 9 is then not run"). EGW_G3_RUI_GO is read by 'close' outside the script only.
    if [ -n "$(state_get "$f" halt)" ]; then
        refuse "NOT STARTED: session $LABEL has a recorded halt ($(state_get "$f" halt)). In S3 a halt ends the session (decision summary, choice 2; request, section 5): classify the row if it awaits classification, then 'close', then hand back to Rui"
    fi
'''),
    # O2 (gate): a tunnel found down after the row and reopened by the preamble is a restoration: the gate fails
    ('''    if grep -q '^TUNNEL UP$' "$(console_of gate-tunnel-check)" 2> /dev/null; then
        echo "NOTE: the tunnel was DOWN after the row and the preamble of hx reopened it (TUNNEL UP in the gate's console): name it in the classification"
        row_set gate_tunnel "found down after the row and reopened by the preamble of hx"
    fi
''',
     '''    # S3 (bounded check of 2026-10-05, O2): that reopening is a restoration of a lost tunnel
    # (request, section 5, items 7 and 9): the gate fails, so a halt is recorded and no
    # further row starts.
    if grep -q '^TUNNEL UP$' "$(console_of gate-tunnel-check)" 2> /dev/null; then
        echo "NOTE: the tunnel was DOWN after the row and the preamble of hx reopened it (TUNNEL UP in the gate's console): a restoration, and in S3 a halt"
        row_set gate_tunnel "found down after the row and reopened by the preamble of hx"
        GATE_BAD+=("the tunnel was found down after the row and reopened by the preamble of hx (request, section 5, items 7 and 9)")
    fi
'''),
    # O2 (steps e and f): a TUNNEL UP printed by the preamble of a step after line d is a lost tunnel restored
    ('''    run_step t8-e-state T8=reconnected || return
    if ! no_stop t8-e-state; then''',
     '''    run_step t8-e-state T8=reconnected || return
    # S3 (bounded check of 2026-10-05, O2): after line d only the preamble of hx can print
    # 'TUNNEL UP' (no later step line calls tunnel_up): the tunnel line d reopened and the
    # check above confirmed was lost and restored - a halt (request, section 5, items 7, 9).
    if grep -q '^TUNNEL UP$' "$(console_of t8-e-state)" 2> /dev/null; then
        halt "row t8: the preamble of hx reopened a lost tunnel before step e (TUNNEL UP in its console; request, section 5, items 7 and 9): step f was NOT run, and T9 is not run"
        return
    fi
    if ! no_stop t8-e-state; then'''),
    ('''    run_step t8-f-smoke T8=ok || return
    # The key keeps its meaning: step f, the smoke line, was reached and ran.
    row_set t8_reached_smoke''',
     '''    run_step t8-f-smoke T8=ok || return
    # The key keeps its meaning: step f, the smoke line, was reached and ran.
    row_set t8_reached_smoke'''),
    ('''    smoke=$(row_itest_ids t8)
    f=$(console_of t8-f-smoke)
    if ! no_stop t8-f-smoke; then''',
     '''    smoke=$(row_itest_ids t8)
    f=$(console_of t8-f-smoke)
    if grep -q '^TUNNEL UP$' "$f" 2> /dev/null; then   # S3 (O2), as after step e
        row_set t8_smoke "halt: the preamble of hx reopened a lost tunnel before the smoke"
        halt "row t8: the preamble of hx reopened a lost tunnel before step f (TUNNEL UP in its console; request, section 5, items 7 and 9): T9 is not run; the row is classified by what its consoles show"
        return
    fi
    if ! no_stop t8-f-smoke; then'''),
    # O2 (test 9): the same after every step
    ('''        run_step "$st" || return
        prev=$st
    done
}''',
     '''        run_step "$st" || return
        # S3 (bounded check of 2026-10-05, O2): no line of test 9 calls tunnel_up, so a
        # 'TUNNEL UP' is the preamble of hx restoring a lost tunnel - a halt (request,
        # section 5, items 7 and 9); no later step of T9 is run.
        if grep -q '^TUNNEL UP$' "$(console_of "$st")" 2> /dev/null; then
            halt "row t9: the preamble of hx reopened a lost tunnel before step $st (TUNNEL UP in its console; request, section 5, items 7 and 9): every later step of T9 was NOT run"
            return
        fi
        prev=$st
    done
}'''),
    # O3: a row classified invalid instrumentation records a halt
    ('''        "invalid instrumentation") echo "NOTE: invalid instrumentation of the shared chain is a halt condition (packet section 4, halt 2). If this is one, do not run a further row: 'close' and hand back to Rui." ;;''',
     '''        # S3 (bounded check of 2026-10-05, O3): recorded as a halt, so that no further row starts.
        "invalid instrumentation") halt "row $ROW_SLUG is classified invalid instrumentation (request, section 5 item 2; decision summary, choice 2): no further row of S3 starts" ;;'''),
])

edit("g3_battery.README.md", [
    ("recorded halt (unless `EGW_G3_RUI_GO`)", "recorded halt (in S3 without exception)"),
    ('''A halt stops the script there; it closes nothing (except at `close` with the guest gone) and is recorded in the
session's state file once the session is in use. No further row starts until Rui directs otherwise
(`EGW_G3_RUI_GO="<his words>"`, recorded). **After any''',
     '''A halt before a row's steps ends the invocation there. A halt inside the steps ends the row's steps, but the
evidence reads and the gate still run, after which the row awaits classification. Nothing is closed, except at
`close` with the guest gone. Every halt is recorded in the session's state file once the session is in use. **No
further row of S3 starts after a halt** (no variable lifts this; `EGW_G3_RUI_GO` is read only by `close` for a
session closed outside the script). A tunnel that the preamble of `hx` reopens after line d (steps e and f, every
step of T9, the gate after a row) is a restoration and a halt. A row classified invalid instrumentation records a
halt too. **After any'''),
])
print("applied")
