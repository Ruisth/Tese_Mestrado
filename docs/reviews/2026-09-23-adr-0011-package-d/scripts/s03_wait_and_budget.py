#!/usr/bin/env python3
"""s03 - FIFO and continuous-busy checks, the exact per-message split of
latency into queue wait and the work between the two stamps, the per-message
budget over explicitly named populations, and the independent cross-check of
the event stream against the sampled queue_depth. READ-ONLY; stdout only.

With one consumer, FIFO service and a consumer that never idles, for message k
in service order:
    wait_k = ack_{k-1} - arrival_k          (time behind earlier messages)
    own_k  = ack_k - ack_{k-1}              (inter-acknowledgement gap)
    latency_k = wait_k + own_k              (exactly)
own_k is everything the consumer did between two acknowledgement stamps: the
previous message's event-log write and flush, dequeue, decode, validation,
dedupe, merge-patch, the Ditto PATCH, and any time the consumer was runnable
but not scheduled. Nothing inside own_k is stamped.
"""

from __future__ import annotations

import bisect
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import NS, Run, header, mean, pct  # noqa: E402

r = Run()
msgs = r.all_messages()
n = len(msgs)

header("A. Order checks over all 8,064 messages (warm-up + measured)")
ack_in_arr_order = [e["ditto_ack_monotonic_ns"] for e in msgs]
fifo = all(ack_in_arr_order[i] < ack_in_arr_order[i + 1] for i in range(n - 1))
print(f"messages {n}; acknowledgements strictly increasing in arrival order (FIFO): {fifo}")
wu_arr_max = max(e["received_monotonic_ns"] for e in r.warm)
me_arr_min = min(e["received_monotonic_ns"] for e in r.post)
wu_ack_max = max(e["ditto_ack_monotonic_ns"] for e in r.warm)
me_ack_min = min(e["ditto_ack_monotonic_ns"] for e in r.post)
print(f"last warm-up arrival {r.el(wu_arr_max):+.6f} s < first measured arrival "
      f"{r.el(me_arr_min):+.6f} s: {wu_arr_max < me_arr_min}")
print(f"last warm-up ack {r.el(wu_ack_max):+.6f} s < first measured ack {r.el(me_ack_min):+.6f} s: "
      f"{wu_ack_max < me_ack_min}")
idle = [k for k in range(1, n) if msgs[k]["received_monotonic_ns"] > msgs[k - 1]["ditto_ack_monotonic_ns"]]
print(f"messages that arrived after the previous ack (consumer idle before them): {len(idle)}")
print(f"=> consumer continuously busy from the first arrival (el {r.el(msgs[0]['received_monotonic_ns']):+.3f} s) "
      f"to the last ack (el {r.el(msgs[-1]['ditto_ack_monotonic_ns']):+.3f} s): {len(idle) == 0}")
lat_check = max(abs((e["ditto_ack_monotonic_ns"] - e["received_monotonic_ns"]) / 1e6 - e["latency_ms"])
                for e in msgs)
print(f"max |(ack-received)/1e6 - latency_ms| : {lat_check:.6f} ms")
seeded = {}
for e in msgs:
    seeded.setdefault(e["device_uuid"], e)
print("first message per device:", {v["device_type"]: v["phase"] for v in seeded.values()})
print(f"attempts > 1: {sum(1 for e in msgs if e['attempts'] != 1)}; non-null error: "
      f"{sum(1 for e in msgs if e['error'] is not None)}")

header("B. Exact wait / own split for the 6,720 measured messages")
wait, own, share = [], [], []
first_meas = None
for k in range(1, n):
    e = msgs[k]
    if e["phase"] != "measured":
        continue
    w = (msgs[k - 1]["ditto_ack_monotonic_ns"] - e["received_monotonic_ns"]) / NS
    o = (e["ditto_ack_monotonic_ns"] - msgs[k - 1]["ditto_ack_monotonic_ns"]) / NS
    wait.append(w)
    own.append(o)
    share.append(w / (w + o))
    if first_meas is None:
        first_meas = (k, e, w, o)
k, e, w, o = first_meas
ahead = bisect.bisect_right(sorted(x["received_monotonic_ns"] for x in msgs), e["received_monotonic_ns"] - 1) \
    - bisect.bisect_right(sorted(x["ditto_ack_monotonic_ns"] for x in msgs), e["received_monotonic_ns"])
print(f"first measured message: arrival el {r.el(e['received_monotonic_ns']):+.6f}, ack el "
      f"{r.el(e['ditto_ack_monotonic_ns']):+.6f}, latency {e['latency_ms'] / 1000:.6f} s = wait {w:.6f} + own {o:.6f}; "
      f"messages in the controller at its arrival: {ahead}")
print(f"wait (s)   : min {min(wait):.3f}  p50 {pct(wait, 50):.3f}  mean {mean(wait):.3f}  max {max(wait):.3f}")
print(f"own  (ms)  : min {min(own) * 1000:.2f}  p50 {pct(own, 50) * 1000:.2f}  mean {mean(own) * 1000:.2f}  "
      f"p95 {pct(own, 95) * 1000:.2f}  max {max(own) * 1000:.2f}")
print(f"wait share of latency: min {min(share) * 100:.4f} %  p50 {pct(share, 50) * 100:.4f} %")
print(f"sum wait / sum latency over the 6,720: {sum(wait) / (sum(wait) + sum(own)) * 100:.4f} %")

header("C. The per-message budget (mean inter-acknowledgement gap) by population")
gap = {}
for k in range(1, n):
    gap[k] = (msgs[k]["ditto_ack_monotonic_ns"] - msgs[k - 1]["ditto_ack_monotonic_ns"]) / NS


def pop(pred, label):
    v = [gap[k] for k in range(1, n) if pred(msgs[k])]
    mu = mean(v)
    print(f"{label:<66} n={len(v):>5}  mean {mu * 1000:7.2f} ms  p50 {pct(v, 50) * 1000:7.2f}  "
          f"p95 {pct(v, 95) * 1000:7.2f}  1/mean {1 / mu:.4f} msg/s")
    return v


inwin = lambda e: r.ctrl_start < e["ditto_ack_monotonic_ns"] <= r.ctrl_end
pop(lambda e: e["phase"] == "measured" and inwin(e),
    "M-in: measured messages acked inside the window (ingress running)")
pop(lambda e: e["phase"] == "measured" and e["ditto_ack_monotonic_ns"] > r.ctrl_end,
    "M-after: measured messages acked after the window end (no ingress)")
pop(lambda e: e["phase"] == "measured", "M-all: all 6,720 measured messages")
pop(lambda e: e["phase"] == "warmup" and inwin(e), "W-in: warm-up messages acked inside the window")
dv = pop(inwin, "D (the draft's 154.77 ms): every ack inside the window")
print(f"W-in share of D: messages {sum(1 for k in range(1, n) if msgs[k]['phase'] == 'warmup' and inwin(msgs[k]))}"
      f"/{len(dv)}; server time "
      f"{sum(gap[k] for k in range(1, n) if msgs[k]['phase'] == 'warmup' and inwin(msgs[k])):.3f}"
      f"/{sum(dv):.3f} s")
print("-- M-in by 60 s block of the ack (el) --")
for b in range(10):
    lo, hi = r.ctrl_start + b * 60 * NS, r.ctrl_start + (b + 1) * 60 * NS
    v = [gap[k] for k in range(1, n)
         if msgs[k]["phase"] == "measured" and lo < msgs[k]["ditto_ack_monotonic_ns"] <= hi]
    if v:
        print(f"  el {b * 60:>3}..{(b + 1) * 60:<3}  n={len(v):>4}  mean {mean(v) * 1000:7.2f} ms")
    else:
        print(f"  el {b * 60:>3}..{(b + 1) * 60:<3}  n=   0  (only warm-up messages served)")
d_first = max(k for k in range(n) if msgs[k]["ditto_ack_monotonic_ns"] <= r.ctrl_start)
d_last = max(k for k in range(n) if msgs[k]["ditto_ack_monotonic_ns"] <= r.ctrl_end)
span = (msgs[d_last]["ditto_ack_monotonic_ns"] - msgs[d_first]["ditto_ack_monotonic_ns"]) / NS
print(f"identity: sum of D gaps = last in-window ack - last pre-window ack = {span:.6f} s; "
      f"mean = span/{d_last - d_first} = {span / (d_last - d_first) * 1000:.4f} ms; "
      f"its reciprocal is the served rate of that population by construction")

header("D. Independent cross-check: event-stream reconstruction vs sampled queue_depth")
arr = sorted(x["received_monotonic_ns"] for x in msgs)
acks = sorted(x["ditto_ack_monotonic_ns"] for x in msgs)
diffs = []
for s in r.metrics_csv():
    t = r.host_wall_to_ctrl(s["t"])
    ins = bisect.bisect_right(arr, t) - bisect.bisect_right(acks, t)
    waiting = max(0, ins - 1)
    diffs.append(waiting - s["queue_depth"])
ad = [abs(d) for d in diffs]
print(f"samples {len(diffs)}: mean diff {mean(diffs):+.3f}, median {pct(diffs, 50):+.1f}, "
      f"max |diff| {max(ad)}, samples outside +/-3: {sum(1 for d in ad if d > 3)}")
print("(anchor: harness wall polled_utc of the controller marker <-> end marker monotonic)")
