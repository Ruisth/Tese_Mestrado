#!/usr/bin/env python3
"""s06 - the resource picture of the measured window of nominal-r01.
READ-ONLY; stdout only.

resources.csv: one row per container per instant, cgroup v2 inside the guest;
cpu_pct = 100 * d(usage_usec) / d(elapsed), so 100 = one vCPU and the guest's
four vCPUs are 400 (collect-resources.sh:60-67). Only the six service
containers are sampled: nothing else in the guest, nothing on the host.
Window instants: ts_utc within measured_window_utc (harness wall; the manifest
assumes the guest and host wall clocks are synchronised).
"""

from __future__ import annotations

import bisect
import math
import re
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import ATT, NS, Run, header, mean, pct, pearson  # noqa: E402

r = Run()
rows = r.resources_csv()
inst = sorted({x["t"] for x in rows})
by_t = defaultdict(dict)
for x in rows:
    by_t[x["t"]][x["container"]] = x
svcs = sorted({x["container"] for x in rows})
win_t = [t for t in inst if r.win_start_wall <= t <= r.win_end_wall]
after_t = [t for t in inst if t > r.win_end_wall]

header("A. Coverage")
print(f"rows {len(rows)}, instants {len(inst)}, services {len(svcs)}; window instants {len(win_t)}, "
      f"after the window {len(after_t)}")
gaps = [b - a for a, b in zip(inst, inst[1:])]
print(f"instant spacing: max {max(gaps):.3f} s, gaps > 2 s: {sum(1 for g in gaps if g > 2)}")

header("B. Per service, measured window")
print(f"{'service':<22}{'cpu mean':>9}{'p50':>8}{'p95':>8}{'max':>8}{'mem% max':>10}")
for s in svcs:
    c = [by_t[t][s]["cpu"] for t in win_t]
    mp = [by_t[t][s]["mem_pct"] for t in win_t]
    print(f"{s:<22}{mean(c):>9.2f}{pct(c, 50):>8.2f}{pct(c, 95):>8.2f}{max(c):>8.2f}{max(mp):>10.2f}")
summed = [sum(by_t[t][s]["cpu"] for s in svcs) for t in win_t]
print(f"summed six: mean {mean(summed):.2f}  p50 {pct(summed, 50):.2f}  p95 {pct(summed, 95):.2f}  "
      f"max {max(summed):.2f}  (of 400)")
for th in (300, 350, 380):
    print(f"instants with summed >= {th}: {sum(1 for x in summed if x >= th)} of {len(summed)}")
med = {s: pct([by_t[t][s]["cpu"] for t in win_t], 50) for s in svcs}
top = max(med, key=med.get)
print(f"highest in-window median: {top} {med[top]:.2f} %")
med_all = {s: pct([by_t[t][s]["cpu"] for t in inst], 50) for s in svcs}
print("medians over all instants:", {s: round(v, 2) for s, v in sorted(med_all.items(), key=lambda kv: -kv[1])[:2]})
mosq = [by_t[t]["egw-mosquitto-1"]["mem"] / 2**20 for t in win_t]
print(f"egw-mosquitto-1 memory mean {mean(mosq):.2f} MiB")

header("C. Controller CPU against the consumer's busy time")
ctrl = [by_t[t]["egw-controller-1"]["cpu"] for t in win_t]
cpu_s = sum(ctrl) / 100.0  # each instant covers ~1 s
win_s = r.win_end_wall - r.win_start_wall
frac = mean(ctrl) / 100.0
print(f"controller CPU: mean {mean(ctrl):.3f} % of one vCPU over {len(win_t)} instants "
      f"-> {cpu_s:.2f} CPU-s in {win_s:.3f} s")
print(f"the {cpu_s:.2f} CPU-s are summed over the {len(win_t)} one-second instants; divided by the "
      f"{win_s:.3f} s window instead: {cpu_s / win_s * 100:.3f} %")
print(f"the consumer was busy the whole window (s03 A); share of that time the whole controller "
      f"container was on CPU <= {frac * 100:.2f} %, so >= {(1 - frac) * 100:.2f} % was not")
msgs = r.all_messages()
acks = sorted(e["ditto_ack_monotonic_ns"] for e in msgs)
n_w = bisect.bisect_right(acks, r.ctrl_end) - bisect.bisect_right(acks, r.ctrl_start)
print(f"per ack inside the window (all {n_w} acks, 751 of them warm-up): controller "
      f"{cpu_s / n_w * 1000:.2f} ms CPU; six services {sum(summed) / 100 / n_w * 1000:.2f} ms CPU")
tri = sum(sum(by_t[t][s]["cpu"] for t in win_t) for s in svcs if "ditto" in s)
mon = sum(by_t[t]["egw-mongodb-1"]["cpu"] for t in win_t)
tot = sum(summed)
print(f"shares of the six: Ditto trio {tri / tot * 100:.2f} %, MongoDB {mon / tot * 100:.2f} %, "
      f"controller {sum(ctrl) / tot * 100:.2f} %")

header("D. Association between acknowledgements and summed CPU (two methods)")
# E: every ack (warm-up + measured) mapped to guest wall through the controller's
#    own wall reading at the end marker; instant T covers (T-1, T].
gw = sorted(r.ctrl_to_guest_wall(a) for a in acks)
ev = []
for t in win_t:
    ev.append(bisect.bisect_right(gw, t) - bisect.bisect_right(gw, t - 1.0))
# C: counter 'accepted' (harness wall) linearly interpolated at T-1 and T, with the guest-wall
#    resource instant T first mapped to harness wall through the marker's offset
#    (controller wall_utc - harness polled_utc): round three. Without that mapping the guest
#    instant was read as harness wall, which is not "the same second".
GUEST_MINUS_HARNESS = r.marker_guest_wall - r.marker_host_wall
met = r.metrics_csv()
mt = [s["t"] for s in met]


def acc(t):
    i = bisect.bisect_left(mt, t)
    if i == 0:
        return met[0]["accepted"]
    if i >= len(met):
        return met[-1]["accepted"]
    a, b = met[i - 1], met[i]
    return a["accepted"] + (b["accepted"] - a["accepted"]) * (t - a["t"]) / (b["t"] - a["t"])


ct = [acc(t - GUEST_MINUS_HARNESS) - acc(t - GUEST_MINUS_HARNESS - 1.0) for t in win_t]
ct_unmapped = [acc(t) - acc(t - 1.0) for t in win_t]
print(f"marker offset, guest wall - harness wall: {GUEST_MINUS_HARNESS:+.3f} s (applied to C)")
bands = [(150, 200), (200, 250), (250, 300), (300, 350), (350, 1000)]
print(f"{'summed CPU band':<16}{'instants':>9}{'acks/s (E)':>12}{'acks/s (C)':>12}")
for lo, hi in bands:
    idx = [i for i, x in enumerate(summed) if lo <= x < hi]
    if idx:
        print(f"{lo:>4}..{hi if hi < 1000 else '':<10}{len(idx):>9}{mean(ev[i] for i in idx):>12.3f}"
              f"{mean(ct[i] for i in idx):>12.3f}")
below = [i for i, x in enumerate(summed) if x < 150]
print(f"instants below 150: {len(below)}")
print(f"Pearson r (acks, summed CPU): E {pearson(ev, summed):+.4f}; C {pearson(ct, summed):+.4f}")
print("for contrast only, C without the offset (round two): " + ", ".join(
    f"{mean(ct_unmapped[i] for i in [j for j, x in enumerate(summed) if lo <= x < hi]):.3f}" for lo, hi in bands)
    + f"; r {pearson(ct_unmapped, summed):+.4f}")
print(f"mean acks/s over window instants: E {mean(ev):.4f}, C {mean(ct):.4f}")

header("E. Guest state after the run (console/010-guest-state-after.stdout.txt)")
txt = (ATT / "console" / "010-guest-state-after.stdout.txt").read_text()
for line in txt.splitlines():
    if re.search(r"OOMKilled=", line):
        print("  " + line)
