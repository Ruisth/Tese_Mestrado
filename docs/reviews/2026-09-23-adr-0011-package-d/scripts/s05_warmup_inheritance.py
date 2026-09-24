#!/usr/bin/env python3
"""s05 - what the measured window inherited from the warm-up, what of it is
observed, and why no counterfactual figure survives. READ-ONLY; stdout only.

Observed (no model): counts at named instants, and how long the consumer spent
on warm-up work after the first measured arrival.

Counterfactual ("what if the window had started empty"): two replays of the
observed service durations, differing ONLY in what a duration is attached to.
  R-msg  each measured message keeps its own observed inter-ack gap
         (the replay behind the verification's 126.32 s / +982 / 1,944)
  R-slot the server keeps the durations of its observed service slots after
         el 0, in order (the replay behind the first draft's 101.16 s / +749
         / 2,177; its script is scripts/queue_inherited_shift.py of round one)
Both start from an empty controller; arrivals are the observed ones. Neither
assumption is testable with this run's data; the output shows they disagree.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import NS, Run, header, mean  # noqa: E402

r = Run()
msgs = r.all_messages()
n = len(msgs)
wu = [e for e in msgs if e["phase"] == "warmup"]
me = [e for e in msgs if e["phase"] == "measured"]

header("A. Observed: warm-up messages at named instants")
t0 = r.ctrl_start
t_first = me[0]["received_monotonic_ns"]
in_at = lambda t: sum(1 for e in wu if e["received_monotonic_ns"] <= t < e["ditto_ack_monotonic_ns"])
print(f"in the controller at el 0                 : {in_at(t0)}")
print(f"acknowledged after el 0                   : {sum(1 for e in wu if e['ditto_ack_monotonic_ns'] > t0)}")
print(f"arrived after el 0                        : {sum(1 for e in wu if e['received_monotonic_ns'] > t0)} "
      f"(at el {r.el(max(e['received_monotonic_ns'] for e in wu)):+.6f} s)")
print(f"in the controller at the first measured arrival (el {r.el(t_first):+.6f}): {in_at(t_first - 1)}")
last_wu = max(e["ditto_ack_monotonic_ns"] for e in wu)
print(f"last warm-up ack                          : el {r.el(last_wu):+.6f} s")
print(f"consumer time on warm-up work after the first measured arrival: {(last_wu - t_first) / NS:.6f} s")
print(f"warm-up acks after el 0 and their summed inter-ack gaps: "
      f"{sum(1 for e in wu if e['ditto_ack_monotonic_ns'] > t0)} / "
      f"{(last_wu - max(e['ditto_ack_monotonic_ns'] for e in msgs if e['ditto_ack_monotonic_ns'] <= t0)) / NS:.3f} s")
in_end = sum(1 for e in msgs if e["received_monotonic_ns"] <= r.ctrl_end < e["ditto_ack_monotonic_ns"])
in_start = sum(1 for e in msgs if e["received_monotonic_ns"] <= t0 < e["ditto_ack_monotonic_ns"])
print(f"in the controller at el 0 / at the window end: {in_start} / {in_end}; growth inside the window "
      f"{in_end - in_start}")
print(f"of the {in_end} at the window end, warm-up messages: "
      f"{sum(1 for e in wu if e['ditto_ack_monotonic_ns'] > r.ctrl_end)}")

header("B. Two replays from an empty controller (NOT findings; shown to test exactness)")
arr = [e["received_monotonic_ns"] for e in me]
obs_ack = [e["ditto_ack_monotonic_ns"] for e in me]
k0 = msgs.index(me[0])
own = [(msgs[k]["ditto_ack_monotonic_ns"] - msgs[k - 1]["ditto_ack_monotonic_ns"]) for k in range(k0, n)]
all_after = sorted(e["ditto_ack_monotonic_ns"] for e in msgs if e["ditto_ack_monotonic_ns"] > t0)
slot = [all_after[0] - t0] + [all_after[i] - all_after[i - 1] for i in range(1, len(all_after))]


def replay(durs, start):
    prev, dep, idle = start, [], 0
    for a, s in zip(arr, durs):
        st = max(a, prev)
        if a > prev:
            idle += 1
        prev = st + s
        dep.append(prev)
    return dep, idle


def report(label, dep, idle):
    lat = [(d - a) / NS for d, a in zip(dep, arr)]
    shift = [(o - d) / NS for o, d in zip(obs_ack, dep)]
    ok = sum(1 for d in dep if d <= r.deadline)
    print(f"{label}")
    print(f"   replayed messages {len(dep)}; server idle before {idle} of them")
    print(f"   mean latency {mean(lat):.3f} s (observed {mean((o - a) / NS for o, a in zip(obs_ack, arr)):.3f} s)")
    print(f"   shift: min {min(shift):.6f}  mean {mean(shift):.6f}  max {max(shift):.6f} s")
    print(f"   acknowledged by the deadline {ok} (observed 3794; {ok - 3794:+d}); still late {len(dep) - ok}")


report("R-msg  (message-indexed durations, server empty at the first measured arrival)",
       *replay(own, t_first))
report("R-slot (slot-indexed durations after el 0, server empty at el 0)",
       *replay(slot, t0))
print("The two replays use the same observed durations and disagree on every")
print("derived figure; the data cannot say which attachment (if either) holds.")
