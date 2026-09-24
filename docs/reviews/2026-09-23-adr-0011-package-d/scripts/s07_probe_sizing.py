#!/usr/bin/env python3
"""s07 - sizing of the one bounded measurement proposed next, against the
LOWEST served rate nominal-r01 showed (not its average). READ-ONLY; stdout.

The proposed offered rate R and publication length are inputs chosen in the
document; this script checks them against the run's own lowest block rates
and prints the arithmetic the document quotes.
"""

from __future__ import annotations

import bisect
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import NS, Run, header  # noqa: E402

R = 2.24          # msg/s, one fifth of 11.2, same 1:0.2:10 split
PUB_S = 720       # s of publication = nominal-r01's 120 s warm-up + 600 s window
CONF_S = 60       # the unchanged confirmation window
SPLIT = {"smartwatch": 1.0, "smart_ring": 0.2, "smart_clothing": 10.0}

r = Run()
msgs = r.all_messages()
acks = sorted(e["ditto_ack_monotonic_ns"] for e in msgs)


def cnt(lo, hi):
    return bisect.bisect_right(acks, hi) - bisect.bisect_right(acks, lo)


header("A. The run's served rate: lowest blocks, and the averages it must not be sized on")
res = {}
for w in (60, 30, 10):
    rates = []
    for b in range(-120 // w, 600 // w):
        lo = r.ctrl_start + b * w * NS
        rates.append((cnt(lo, lo + w * NS) / w, b * w))
    mn = min(rates)
    mn_win = min(x for x in rates if x[1] >= 0)
    res[w] = mn[0]
    print(f"{w:>3} s blocks el -120..600: lowest {mn[0]:.4f} msg/s at el {mn[1]}..{mn[1] + w}; "
          f"lowest inside the window {mn_win[0]:.4f} at el {mn_win[1]}..{mn_win[1] + w}")
print("(10 s blocks are shown only to expose the spread; a 10 s block holds ~50 acks)")
print("window average (counters, s02) 6.457048 msg/s and drain 8.863682 msg/s: NOT used for sizing")

header("B. The proposed offered rate against the lowest rates")
tot = sum(SPLIT.values())
per = {d: R * v / tot for d, v in SPLIT.items()}
n_msgs = {d: per[d] * PUB_S for d in per}
N = sum(n_msgs.values())
print(f"R = {R} msg/s; per device {', '.join(f'{d} {v:.3f} Hz' for d, v in per.items())}")
print(f"messages in {PUB_S} s: {', '.join(f'{d} {v:.1f}' for d, v in n_msgs.items())}; total {N:.1f}")
for w in (60, 30):
    print(f"R / lowest {w} s block ({res[w]:.4f}) = {R / res[w]:.3f}; headroom {res[w] - R:+.4f} msg/s; "
          f"service needed for all {N:.0f} at that rate {N / res[w]:.1f} s of {PUB_S} s")
print(f"R / lowest 10 s block ({res[10]:.4f}) = {R / res[10]:.3f}")
print(f"R / nominal offered rate = {R / 11.2:.3f}")

import json  # noqa: E402
plan = json.loads(Path("/home/ruisth/egw-tcg/pilot/campaign_plan.json").read_text())
rates = sorted({x["rate_msg_s"] for x in plan["runs"] if x["rate_msg_s"] is not None})
print(f"campaign plan (~/egw-tcg/pilot/campaign_plan.json): {len(plan['runs'])} runs; "
      f"distinct offered rates {rates}; lowest {rates[0]} msg/s")

header("C. Detection and time budget")
# Round three: the refutation no longer compares two instants against the +-3 agreement band
# of s03 D. That band measures agreement between two instruments, not how much the queue
# fluctuates: one slow passage at the end of publication could breach it. How many measured
# passages of nominal-r01 were long enough for three messages to arrive at R on average:
own = []
for k in range(1, len(msgs)):
    if msgs[k]["phase"] == "measured":
        own.append(((msgs[k]["ditto_ack_monotonic_ns"] - msgs[k - 1]["ditto_ack_monotonic_ns"]) / NS,
                    r.el(msgs[k]["ditto_ack_monotonic_ns"])))
thr = 3 / R
longest = max(own)
print(f"passage long enough for 3 arrivals at {R} msg/s: 3 / {R} = {thr:.3f} s; measured passages of "
      f"nominal-r01 longer than that: {sum(1 for o, _ in own if o > thr)} of {len(own)}; "
      f"longest {longest[0]:.3f} s (acknowledged at el {longest[1]:.1f})")
c = {x["seq"]: x for x in r.commands()}
print(f"precondition 'drained' in the nominal attempt: {c[3]['duration_s']} s (commands.jsonl seq 3)")
exp_s = c[3]["duration_s"] + PUB_S + CONF_S + 135
print(f"expected guest time ~ {c[3]['duration_s']:.0f} + {PUB_S} + {CONF_S} + ~135 (post quiet window) "
      f"= {exp_s:.0f} s = {exp_s / 60:.1f} min")
exp490 = c[3]["duration_s"] + PUB_S + CONF_S + 495
print(f"with DRAIN_QUIET_S=490 after the run: ~{exp490:.0f} s = {exp490 / 60:.1f} min")
# Planning ceiling, NOT a bound. 'wait' gives up only after the 60 s window plus its
# --extra-timeout (default 120 s: itest_reconcile.py:235, :604); 'pre' first runs wait_ready
# (READY_LIMIT_S default 60 s: itest-helpers.sh:179); 'drained' checks DRAIN_LIMIT_S only
# between readings, each of which may take up to 30 s (curl --max-time 30, itest-helpers.sh:30);
# fetches, snapshots and 'accounted' are not counted.
EXTRA_WAIT_S, READY_S, LIMIT_S = 120, 60, 900
old = LIMIT_S + PUB_S + CONF_S + LIMIT_S
ceil = READY_S + LIMIT_S + PUB_S + CONF_S + EXTRA_WAIT_S + LIMIT_S
print(f"the round-two 'hard bound' {LIMIT_S} + {PUB_S} + {CONF_S} + {LIMIT_S} = {old} s = {old / 60:.1f} min is not a bound")
print(f"planning ceiling with the helpers' defaults: wait_ready {READY_S} + drained {LIMIT_S} + publication {PUB_S} "
      f"+ wait {CONF_S} + {EXTRA_WAIT_S} + drained {LIMIT_S} = {ceil} s = {ceil / 60:.1f} min before the excluded terms; "
      f"it excludes each drained reading's curl time past its limit, fetches, snapshots and 'accounted'")
