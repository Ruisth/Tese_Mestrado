"""The final review of the S4 request and operator documents (2026-10-05; facts R1-R7, consistency C1-C10).
Usage: python fix_review_final.py <P>"""
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


edit("request-draft.md", [
    # C8
    ("""criterion amended on 2026-10-05 (decision record `docs/governance/g3-t5-t6-decisions-2026-10-05.md`, LOG #C052) with
option A's transition rule (LOG #C053).""",
     """criterion amended on 2026-10-05 (decision record `docs/governance/g3-t5-t6-decisions-2026-10-05.md`, LOG #C052) with
option A's transition rule (LOG #C053); S4 is a run made after that adoption."""),
    # R1, C6
    ("""preflight at the session's open; about 35–45 min of guest occupation; row ceiling 47 min; whatever the result, the
attempt is exported to `output_test` and the session closed in a controlled way; no repeat, no build, no change to the
candidate or to a criterion.""",
     """preflight at the session's open; about 30–40 min of guest occupation; row ceiling 47 min; whatever the result, the
attempt is exported to `output_test` and the session closed in a controlled way; no repeat, no build, no change to the
candidate beyond the collector the preflight installs, no change to a criterion."""),
    # R1
    ("""| T6 | about 20–25 min (S2's row: 19 min) | ceiling 47 min (the packet's) |
| Stop and close | about 1.5 min | none of its own |""",
     """| T6 | about 20–25 min (S2's row: 20 min, its step 19 min) | ceiling 47 min (the packet's) |
| Classification | about 2 min | — |
| Stop and close | about 1.5 min | none of its own |"""),
    # C4
    ("""Each halts the session: nothing is repeated; the attempt is classified and exported as it stands; the session is closed
in a controlled way and handed back to Rui. QEMU is never killed or re-launched without Rui's decision.""",
     """Each halts the session: nothing is repeated; the attempt is classified and exported as it stands; the session is closed
in a controlled way whenever the guest answers, and handed back to Rui. If the guest does not answer while QEMU runs,
the state is preserved, nothing is signalled and Rui decides in the window. QEMU is never killed or re-launched without
Rui's decision."""),
    # C2
    ("""2. Instrumentation: a step status 97 or 74; an export, transcript or snapshot failure.
3. A failed gate: not six healthy services within 900 s; a recorder or collector unit active; an OOM kill.
4. The row past its ceiling.
5. Guest, tunnel, WSL or keepalive lost.
6. Any restoration: nothing on the guest is started, restarted or recreated by hand.""",
     """2. Instrumentation: a step status 97 or 74; an export, transcript or snapshot failure; a usage exit 2 of `delta` or
   `acceptance`.
3. A failed gate: not six healthy services within 900 s; a recorder or collector unit active; an OOM kill; an
   unexpected restart or replacement.
4. The row past its ceiling; no row starts after the 3 h start cut-off.
5. Guest, tunnel, WSL or keepalive lost.
6. Any restoration: nothing on the guest is started, restarted or recreated by hand (as in S3; a controller left
   stopped by the test's restart is a failure the record shows, and the close's stop covers it)."""),
    # C1
    ("""| Pass | `T6=ok` (harness exit 0, run sealed, drain `quiet`); recovery within 120 s""",
     """| Pass | `T6=ok` (harness exit 0, run sealed, drain `quiet`); the controller restarted once mid-run (the restart record at +300 s with exit 0, the capture's `die` and `start`, the gate's `EXPECTED-RESTART` for `egw-controller-1`); recovery within 120 s"""),
    # C3
    ("""| Invalid instrumentation | harness exit 1 with an instrumentation reason (the configuration identity and a rejected `resources.csv` included); `delta` 1 or 2; `--exactly-once` exit 1 |
| Inconclusive | `harness_cmd` 3 |""",
     """| Invalid instrumentation | harness exit 1 with an instrumentation reason (the configuration identity and a rejected `resources.csv` included); `delta` 1 or 2; `--exactly-once` exit 1 or 2; no endpoint recovery value (`analyze`: insufficient instrumentation) |
| Inconclusive | `harness_cmd` 3; a row interrupted at the ceiling (exported `interrupted`, not demonstrated) |"""),
    # C7
    ("""Reported beside the result, deciding nothing:""",
     """A `delta` MISMATCH or a duplicate-only identity is a valid failure with the cause not established: the result note
reports no defect of the system for it (packet sections 5 and 6). Reported beside the result, deciding nothing:"""),
    # R5, C10
    ("""## 7. Preparation (delivered; no guest)

Package `output_test/runs/2026-10-05/HIST_2026-10-05-g3-t6-host-preparation` (its seal is given in the hand-off).""",
     """## 7. Preparation (sealed; no guest)

Package `output_test/runs/2026-10-05/HIST_2026-10-05-g3-t6-host-preparation` (its seal is given in the hand-off)."""),
    # R7
    ("""- **Step file:** `t6.sh` (`ec8ac010…`) equals runbook lines 1421–1428 byte for byte; checked against the moved clone.""",
     """- **Step file:** `t6.sh` (`ec8ac010…`) equals runbook lines 1421–1428 byte for byte once the `host$ ` prompt is
  removed; checked against the moved clone."""),
    # R4, C9
    ("""helper functions, stand-ins for the harness, `analyze` and the guest: 25 scenarios PASS, the script unchanged; one
  adversarial reading of the bench (one material point, the ceiling path of section 4, now in the procedure).""",
     """helper functions, stand-ins for the harness, `analyze`, `itest_reconcile` (`delta`, `--exactly-once`), the four
  session drivers and the guest: 25 scenarios PASS, the script unchanged (not exercised: the ceiling and the cut-off in
  real time, statuses 97 and 74, an export failure); one adversarial reading of the bench (one material point, the
  ceiling path of section 4, now in the procedure)."""),
    # R6, R2
    ("""- **Verified nowhere but on the guest:** the real harness with the transition rule, the collector's uptime bounds,
  `--exactly-once` on a real post-drain copy, and `term` on the real harness.""",
     """- **Not yet verified, and verifiable only on the guest:** the items of section 8 and `term` on the real harness."""),
    # R2, C9
    ("""- Unverified on the guest (Appendix B item 24): the transition rule on a live restart, the collector's uptime bounds,
  the exactly-once line on a real post-drain copy.""",
     """- Unverified on the guest (Appendix B items 23 and 24): the transition rule on a live restart, the collector's uptime
  bounds, the exactly-once line on a real post-drain copy, `delta`'s N1 options (`--restart-evidence`) on a real run
  directory, `fetch_started_at.sh`, the Docker events of a compose restart on the guest's engine."""),
    # C6, R3
    ("""do pedido de 2026-10-05; sem repetições, sem alterações ao candidato e sem aceitação automática do G3."*

Two points are choices of this request; say so if either should be otherwise: (1) "recovery within 120 s" read on
`restart_metrics_endpoint_recovery_s`, the packet's endpoint recovery, with the functional recovery reported beside it
(section 6); (2) after a TERM at the ceiling, the runbook's own recorder cleanup, recorded, before the close
(section 4).""",
     """do pedido de 2026-10-05; sem repetições, sem alterações ao candidato além do novo coletor instalado pelo preflight e sem
aceitação automática do G3."*

Three points are choices of this request; say so if any should be otherwise: (1) "recovery within 120 s" read on
`restart_metrics_endpoint_recovery_s`, the packet's endpoint recovery, with the functional recovery reported beside it
(section 6); (2) after a TERM at the ceiling, the runbook's own recorder cleanup, recorded, before the close
(section 4); (3) `--exactly-once` exit 1 (inputs not read) classed as invalid instrumentation, as test 6's row treats
`delta` 1, where the packet's test 3 row classed `acceptance` 1 as inconclusive (section 6)."""),
])

edit("operator-procedure.md", [
    # C1, C3 (the procedure's copy of the table follows the request's)
    ("""| Pass | `T6=ok` (harness exit 0, run sealed, drain `quiet`); recovery within 120 s;""",
     """| Pass | `T6=ok` (harness exit 0, run sealed, drain `quiet`); the controller restarted once mid-run (the restart record at +300 s with exit 0, the capture's `die` and `start`, the gate's `EXPECTED-RESTART` for `egw-controller-1`); recovery within 120 s (`restart_metrics_endpoint_recovery_s`);"""),
    ("""`delta` 1 or 2; `--exactly-once` exit 1 |
| Inconclusive | `harness_cmd` 3 |""",
     """`delta` 1 or 2; `--exactly-once` exit 1 or 2; no endpoint recovery value (`analyze`: insufficient instrumentation) |
| Inconclusive | `harness_cmd` 3; a row interrupted at the ceiling (exported `interrupted`, not demonstrated; not classified again) |"""),
    # C7
    ("""Rules that stand beside the table, unchanged from the packet and the request:""",
     """A `delta` MISMATCH or a duplicate-only identity is a valid failure with the cause not established: the result note
reports no defect of the system for it (packet sections 5 and 6). Rules that stand beside the table, unchanged from
the packet and the request:"""),
])

edit("g3_battery.README.md", [
    # C5
    ("""the REAL `t6.sh` through the script with the real helper functions, 20 scenarios
  PASS)""",
     """the REAL `t6.sh` through the script with the real helper functions, 25 scenarios
  PASS, 1,222 checks)"""),
])
print("fixed")
