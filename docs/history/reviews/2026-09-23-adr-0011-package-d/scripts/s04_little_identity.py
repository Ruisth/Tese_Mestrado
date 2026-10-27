#!/usr/bin/env python3
"""s04 - Little's law over the empty-to-empty interval of nominal-r01, shown
to be an identity rather than a check. READ-ONLY; stdout only.

Over an interval that starts and ends with an empty system, the area under
N(t) built from the arrival and departure stamps equals the sum of the
sojourn times built from the same stamps: integral N dt = sum (d_i - a_i).
So L = lambda * W holds for ANY set of stamps with d_i >= a_i. Part C proves
it numerically by fabricating departures and getting the same ratio of 1.
"""

from __future__ import annotations

import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import NS, Run, header  # noqa: E402

r = Run()
msgs = r.all_messages()
b, a = r.snapshot("before"), r.snapshot("after")


def little(pairs):
    """pairs of (arrival_ns, departure_ns); returns (area, sum_w, T, L, lam, W)."""
    ev = [(x, 1) for x, _ in pairs] + [(y, -1) for _, y in pairs]
    ev.sort()
    t0, t1 = ev[0][0], ev[-1][0]
    area, n, last = 0, 0, t0
    for t, d in ev:
        area += n * (t - last)
        n += d
        last = t
    sum_w = sum(y - x for x, y in pairs)
    T = (t1 - t0) / NS
    L = area / NS / T
    lam = len(pairs) / T
    W = sum_w / NS / len(pairs)
    return area / NS, sum_w / NS, T, L, lam, W


header("A. The interval is empty at both ends (controller /metrics snapshots)")
print(f"before {b['wall_utc']}: queue_depth {b['queue_depth']}, in_progress {b['in_progress']}, accepted {b['accepted']}")
print(f"after  {a['wall_utc']}: queue_depth {a['queue_depth']}, in_progress {a['in_progress']}, accepted {a['accepted']}")
print(f"messages in the interval: {len(msgs)} (= {a['accepted']} - {b['accepted']})")

header("B. The observed stamps")
pairs = [(e["received_monotonic_ns"], e["ditto_ack_monotonic_ns"]) for e in msgs]
area, sw, T, L, lam, W = little(pairs)
print(f"integral N dt {area:.3f} msg*s; sum of sojourns {sw:.3f} msg*s; T {T:.3f} s")
print(f"L {L:.4f}, lambda {lam:.4f} msg/s, W {W:.4f} s, L/(lambda W) = {L / (lam * W):.10f}")

header("C. The same computation on fabricated departures (identity demonstration)")
rng = random.Random(20260921)
for label, fab in (
    ("departure = arrival + U(0, 900 s), order ignored",
     [(x, x + int(rng.uniform(0, 900) * NS)) for x, _ in pairs]),
    ("departure = arrival + 1 ms", [(x, x + 1_000_000) for x, _ in pairs]),
):
    area, sw, T, L, lam, W = little(fab)
    print(f"{label:<52} L/(lambda W) = {L / (lam * W):.10f}")
print("Any stamps give 1: the ratio cannot corroborate the measurement chain.")
