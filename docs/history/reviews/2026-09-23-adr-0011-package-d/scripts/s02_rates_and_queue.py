#!/usr/bin/env python3
"""s02 - offered, arrival and served rates of nominal-r01, block by block,
and the queue they produced. READ-ONLY; writes only to standard output.

Two instruments for the served rate, never merged:
  counters  controller_metrics.csv 'accepted' (harness wall, ~1 Hz polls)
  event log ditto_ack_monotonic_ns of warmup.events.jsonl + events.post-drain.jsonl
            (controller monotonic); every ack counts, whoever's message it is.
"""

from __future__ import annotations

import bisect
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import NS, Run, header, mean  # noqa: E402

r = Run()
m = r.manifest
msgs = r.all_messages()
arr = sorted(e["received_monotonic_ns"] for e in msgs)
acks = sorted(e["ditto_ack_monotonic_ns"] for e in msgs)
arr_meas = sorted(e["received_monotonic_ns"] for e in r.post)
met = r.metrics_csv()

header("A. Offered rate (sent_events.jsonl, harness monotonic)")
pub = sorted(e["publish_monotonic_ns"] for e in r.sent)
span = (pub[-1] - pub[0]) / NS
print(f"n {len(pub)}, first {(pub[0] - r.host_start) / NS:+.6f} s, last {(pub[-1] - r.host_start) / NS:+.6f} s")
print(f"offered rate (n-1)/span                : {(len(pub) - 1) / span:.6f} msg/s (plan {m['rate_msg_s']})")
blocks = []
for b in range(10):
    lo, hi = r.host_start + b * 60 * NS, r.host_start + (b + 1) * 60 * NS
    blocks.append(sum(1 for p in pub if lo <= p < hi))
print(f"per 60 s block from the window start   : {blocks}")
print(f"  -> {min(blocks) / 60:.4f} .. {max(blocks) / 60:.4f} msg/s")
print(f"intended_invalid                       : {sum(1 for e in r.sent if e['intended_invalid'])}")

header("B. Arrivals at the controller (controller monotonic)")
print(f"measured arrivals (n-1)/span           : "
      f"{(len(arr_meas) - 1) / ((arr_meas[-1] - arr_meas[0]) / NS):.6f} msg/s")
print(f"first / last measured arrival el       : {r.el(arr_meas[0]):+.6f} / {r.el(arr_meas[-1]):+.6f} s")
print(f"first warm-up arrival el               : {r.el(arr[0]):+.6f} s")


def count_between(sorted_ns, lo, hi):
    return bisect.bisect_right(sorted_ns, hi) - bisect.bisect_right(sorted_ns, lo)


header("C. Served rate by phase")
pre = [s for s in met if s["t"] < r.win_start_wall]
win = [s for s in met if r.win_start_wall <= s["t"] <= r.win_end_wall]
post = [s for s in met if s["t"] > r.win_end_wall]
print(f"metric samples: before window {len(pre)}, in window {len(win)}, after {len(post)}, total {len(met)}")
wu_rate = (pre[-1]["accepted"] - pre[0]["accepted"]) / (pre[-1]["t"] - pre[0]["t"])
w_rate = (win[-1]["accepted"] - win[0]["accepted"]) / (win[-1]["t"] - win[0]["t"])
print(f"counters, warm-up  : d_accepted {pre[-1]['accepted'] - pre[0]['accepted']} over "
      f"{pre[-1]['t'] - pre[0]['t']:.3f} s = {wu_rate:.6f} msg/s")
print(f"counters, window   : d_accepted {win[-1]['accepted'] - win[0]['accepted']} over "
      f"{win[-1]['t'] - win[0]['t']:.3f} s = {w_rate:.6f} msg/s")
n_wu = count_between(acks, arr[0], r.ctrl_start)
n_w = count_between(acks, r.ctrl_start, r.ctrl_end)
n_d = count_between(acks, r.ctrl_end, acks[-1])
print(f"event log, warm-up : {n_wu} acks between the first arrival and el 0 "
      f"({(r.ctrl_start - arr[0]) / NS:.3f} s) = {n_wu / ((r.ctrl_start - arr[0]) / NS):.6f} msg/s")
print(f"event log, window  : {n_w} acks in (el 0, el {r.el(r.ctrl_end):.3f}] = "
      f"{n_w / ((r.ctrl_end - r.ctrl_start) / NS):.6f} msg/s")
print(f"event log, drain   : {n_d} acks after the window end, last at el {r.el(acks[-1]):+.3f} s; "
      f"{n_d} / (last ack - window end) = {n_d / ((acks[-1] - r.ctrl_end) / NS):.6f} msg/s")
ev_w = n_w / ((r.ctrl_end - r.ctrl_start) / NS)
print(f"event log vs counters, window: {(ev_w / w_rate - 1) * 100:+.4f} %")
off = (len(pub) - 1) / span
print(f"utilisation offered/served(counters, window) = {off / w_rate:.6f}; "
      f"net accumulation = {off - w_rate:.6f} msg/s")

header("D. Served rate in fixed blocks (lowest block matters for sizing)")


def acc_at(t):
    """accepted counter linearly interpolated at harness wall t."""
    ts = [s["t"] for s in met]
    i = bisect.bisect_left(ts, t)
    if i == 0:
        return met[0]["accepted"]
    if i >= len(met):
        return met[-1]["accepted"]
    a, b = met[i - 1], met[i]
    return a["accepted"] + (b["accepted"] - a["accepted"]) * (t - a["t"]) / (b["t"] - a["t"])


for width in (60, 30):
    print(f"-- {width} s blocks, aligned at el 0, from el -120 to el 600 --")
    print(f"{'block (s)':>14} {'arrivals':>9} {'acks(ev)':>9} {'ev msg/s':>9} {'ctr msg/s':>9}")
    evs, ctrs = [], []
    for b in range(-120 // width, 600 // width):
        lo = r.ctrl_start + b * width * NS
        hi = lo + width * NS
        na = count_between(arr, lo, hi)
        nk = count_between(acks, lo, hi)
        tl = r.win_start_wall + b * width
        cr = (acc_at(tl + width) - acc_at(tl)) / width
        evs.append((nk / width, b * width))
        ctrs.append((cr, b * width))
        print(f"{b * width:>6}..{(b + 1) * width:<6} {na:>9} {nk:>9} {nk / width:>9.4f} {cr:>9.4f}")
    lo_e = min(evs)
    lo_c = min(ctrs)
    print(f"lowest {width} s block: event log {lo_e[0]:.4f} msg/s at el {lo_e[1]}..{lo_e[1] + width}; "
          f"counters {lo_c[0]:.4f} msg/s at el {lo_c[1]}..{lo_c[1] + width}")
    wv = [x for x, s in evs if s >= 0]
    print(f"in-window {width} s blocks (event log): min {min(wv):.4f}, max {max(wv):.4f} msg/s")

print("-- 10 s blocks inside the window: blocks where acks >= arrivals --")
cnt = 0
tot = 0
for b in range(60):
    lo = r.ctrl_start + b * 10 * NS
    hi = lo + 10 * NS
    tot += 1
    if count_between(acks, lo, hi) >= count_between(arr, lo, hi):
        cnt += 1
print(f"{cnt} of {tot} ten-second blocks")
secs = [(count_between(acks, r.ctrl_start + i * NS, r.ctrl_start + (i + 1) * NS)) for i in range(600)]
print(f"1 s bins in the window with zero acks  : {sum(1 for s in secs if s == 0)} of 600")

header("E. The queue")
zeros = [s for s in met if s["queue_depth"] == 0]
print(f"samples {len(met)}; samples with queue_depth 0: {len(zeros)} at "
      f"{[s['ts_utc'] for s in zeros]}")
print(f"first arrival (harness wall)           : {__import__('common').utc(r.ctrl_to_host_wall(arr[0]))}")
print(f"'dropped' non-zero in any sample       : {any(s['dropped'] for s in met)}; "
      f"rejected/duplicate/failed non-zero: {any(s['rejected'] or s['duplicate'] or s['failed'] for s in met)}")
qd = [s["queue_depth"] for s in win]
print(f"in-window samples {len(win)}: first {qd[0]}, last {qd[-1]}, min {min(qd)}, max {max(qd)}, "
      f"mean {mean(qd):.2f}")
dec = [(win[i]["queue_depth"] - win[i + 1]["queue_depth"]) for i in range(len(win) - 1)
       if win[i + 1]["queue_depth"] < win[i]["queue_depth"]]
print(f"in-window consecutive-sample decreases : {len(dec)}, largest {max(dec) if dec else 0}")


def in_system(t_ns):
    return bisect.bisect_right(arr, t_ns) - bisect.bisect_right(acks, t_ns)


for label, t in (("window start", r.ctrl_start), ("window end", r.ctrl_end), ("deadline", r.deadline)):
    n = in_system(t)
    print(f"reconstructed in system at {label:<12}: {n} ({n - 1} waiting + 1 in service)")
g_obs = qd[-1] - qd[0]
dt = win[-1]["t"] - win[0]["t"]
print(f"growth, sampled first->last in-window  : {qd[0]} -> {qd[-1]} = {g_obs} over {dt:.3f} s")
print(f"growth predicted by the deficit        : {off - w_rate:.6f} x {dt:.3f} = {(off - w_rate) * dt:.2f}")
g_rec = in_system(r.ctrl_end) - in_system(r.ctrl_start)
print(f"growth, reconstruction el 0 -> window end: {g_rec} over {(r.ctrl_end - r.ctrl_start) / NS:.3f} s "
      f"= {g_rec / ((r.ctrl_end - r.ctrl_start) / NS):.4f} msg/s")

header("F. Around the window end (event log, all acks)")
for lo_s, hi_s in ((540, 600), (600, 630), (600, 660)):
    n = count_between(acks, r.ctrl_start + lo_s * NS, r.ctrl_start + hi_s * NS)
    print(f"el {lo_s}..{hi_s}: {n} acks = {n / (hi_s - lo_s):.4f} msg/s")
n30 = count_between(acks, r.ctrl_end, r.ctrl_end + 30 * NS)
print(f"first 30 s after the window end: {n30} acks = {n30 / 30:.4f} msg/s; "
      f"/ window counter rate = {n30 / 30 / w_rate:.4f}")
print("10 s blocks from el 560 to el 640:")
for b in range(56, 64):
    lo = r.ctrl_start + b * 10 * NS
    print(f"  el {b * 10}..{b * 10 + 10}: {count_between(acks, lo, lo + 10 * NS) / 10:.1f} msg/s")
print(f"metric samples end at {met[-1]['ts_utc']}; resource collector stop hook "
      f"{m['collector_hooks'][1]['started_utc']}; last publish el "
      f"{(pub[-1] - r.host_start) / NS:+.3f} s (harness)")

header("G. The drain in 30 s blocks after the window end (no ingress), event log")
common = __import__("common")
for b in range(0, 14):
    lo = r.ctrl_end + b * 30 * NS
    hi = min(lo + 30 * NS, acks[-1])
    if hi <= lo:
        break
    k = count_between(acks, lo, hi)
    print(f"  window end +{b * 30:>3}..+{b * 30 + 30:<3} s (harness wall from "
          f"{common.utc(r.ctrl_to_host_wall(lo))}): {k:>3} acks = {k / ((hi - lo) / NS):6.3f} msg/s")
n_after_dl = count_between(acks, r.deadline, acks[-1])
print(f"after the deadline: {n_after_dl} acks over {(acks[-1] - r.deadline) / NS:.3f} s = "
      f"{n_after_dl / ((acks[-1] - r.deadline) / NS):.4f} msg/s")
hooks = m["collector_hooks"]
print(f"collector fetch hook {hooks[2]['started_utc']} -> {hooks[2]['finished_utc']}; "
      f"events scp {m['events_fetch']['attempts'][0]['started_utc']}")
