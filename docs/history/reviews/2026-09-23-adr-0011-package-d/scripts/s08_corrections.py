#!/usr/bin/env python3
"""s08 - the figures behind the round-three corrections of backlog_diagnosis.md.
READ-ONLY; writes only to standard output. Standard library only.

A  measured messages that waited while warm-up messages were being served (section 9.1)
B  the end-of-window count decomposed by instant (sections 7.1 and 9.1)
C  Little's law: the interval the figures use, and the interval the snapshots bound (section 8)
D  the drain after the window end: full 30 s blocks and the last, partial one (section 7.1)
E  the platform files: when the SUT environment was captured, against the run (header)

Every duration here is from an ARM64 guest emulated under QEMU/TCG; none is native.
"""

from __future__ import annotations

import bisect
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import NS, RAW, Run, header, iso  # noqa: E402

r = Run()
msgs = r.all_messages()                      # warm-up + measured, by arrival
wu = [e for e in msgs if e["phase"] == "warmup"]
me = [e for e in msgs if e["phase"] == "measured"]
arr = sorted(e["received_monotonic_ns"] for e in msgs)
acks = sorted(e["ditto_ack_monotonic_ns"] for e in msgs)

header("A. Measured messages in the controller while warm-up messages were served")
last_wu_ack = max(e["ditto_ack_monotonic_ns"] for e in wu)
before = sum(1 for e in me if e["received_monotonic_ns"] < last_wu_ack)
print(f"last warm-up acknowledgement: el {r.el(last_wu_ack):+.6f} s")
print(f"measured messages that arrived before it: {before} of {len(me)}; after it: {len(me) - before}")
print("the waits of the latter contain no warm-up service time (FIFO, no interleaving: s03 A)")

header("B. The number in the controller at the window end, by count")
S0, S1 = r.ctrl_start, r.ctrl_end
in0 = bisect.bisect_right(arr, S0) - bisect.bisect_right(acks, S0)
arr_w = bisect.bisect_right(arr, S1) - bisect.bisect_right(arr, S0)
ack_w = bisect.bisect_right(acks, S1) - bisect.bisect_right(acks, S0)
in1 = bisect.bisect_right(arr, S1) - bisect.bisect_right(acks, S1)
wu_ack_w = sum(1 for e in wu if S0 < e["ditto_ack_monotonic_ns"] <= S1)
wu_arr_w = sum(1 for e in wu if S0 < e["received_monotonic_ns"] <= S1)
print(f"in the controller at el 0: {in0}; arrivals in (el 0, window end]: {arr_w} "
      f"({wu_arr_w} warm-up); acknowledgements in it: {ack_w} ({wu_ack_w} of warm-up messages)")
print(f"in the controller at the window end: {in1} = {in0} + {arr_w} - {ack_w} "
      f"(check: {in0 + arr_w - ack_w == in1})")
print(f"warm-up messages among them: {sum(1 for e in wu if e['ditto_ack_monotonic_ns'] > S1)}")

header("C. Little's law over the two intervals (controller clock)")
b, a = r.snapshot("before"), r.snapshot("after")
print(f"snapshot 'before': wall_utc {b['wall_utc']} (the controller's own, i.e. guest, wall clock), "
      f"monotonic {b['monotonic_ns']}, queue_depth {b['queue_depth']}, in_progress {b['in_progress']}")
print(f"snapshot 'after' : wall_utc {a['wall_utc']} (the controller's own, i.e. guest, wall clock), "
      f"monotonic {a['monotonic_ns']}, queue_depth {a['queue_depth']}, in_progress {a['in_progress']}")
sum_w = sum(e["ditto_ack_monotonic_ns"] - e["received_monotonic_ns"] for e in msgs) / NS
n = len(msgs)
W = sum_w / n
for label, t0, t1 in (
    ("busy interval: first arrival -> last acknowledgement", arr[0], acks[-1]),
    ("snapshot interval: 'before' -> 'after'", b["monotonic_ns"], a["monotonic_ns"]),
):
    T = (t1 - t0) / NS
    L = sum_w / T        # the integral of N dt equals the sum of sojourns when N is 0 at both ends
    lam = n / T
    print(f"{label}: el {r.el(t0):+.3f} -> {r.el(t1):+.3f}, T {T:.3f} s; L {L:.4f}, lambda {lam:.4f} msg/s, "
          f"W {W:.4f} s, L/(lambda W) = {L / (lam * W):.10f}")
print(f"with no arrivals: from the last arrival to the last acknowledgement "
      f"{(acks[-1] - arr[-1]) / NS:.2f} s of the busy interval")

header("D. The drain after the window end, in 30 s blocks (event log, controller clock)")
last = acks[-1]
full = []
for k in range(0, 20):
    lo = S1 + k * 30 * NS
    hi = lo + 30 * NS
    if lo >= last:
        break
    if hi <= last:
        c = bisect.bisect_right(acks, hi) - bisect.bisect_right(acks, lo)
        full.append((k, c / 30))
    else:
        c = bisect.bisect_right(acks, last) - bisect.bisect_right(acks, lo)
        span = (last - lo) / NS
        print(f"last, partial block: window end +{k * 30}..+{(last - S1) / NS:.3f} s: {c} acknowledgements "
              f"in {span:.3f} s = {c / span:.3f} msg/s")
after90 = [x for k, x in full if k >= 3]
print(f"full 30 s blocks from window end +90 s: {len(after90)}, {min(after90):.3f} .. {max(after90):.3f} msg/s")

header("E. The platform files")
sut = json.loads((RAW / "sut_environment.json").read_text())
cap = sut["captured_utc"]
lag_h = (r.win_start_wall - iso(cap)) / 3600
print(f"sut_environment.json captured_utc {cap}; measured window start {r.manifest['measured_window_utc']['start']}; "
      f"captured {lag_h:.1f} h before the window start")
print("the harness copies it in with --sut-env-from (~/egw-tcg/itest-helpers.sh:244), so it describes that earlier capture, "
      "not the run's own boot")
