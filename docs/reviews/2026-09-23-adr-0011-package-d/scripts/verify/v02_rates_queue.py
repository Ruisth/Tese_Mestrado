"""v02 - offered/arrival/served rates, fixed blocks, the queue, the drain.

Checks backlog_diagnosis.md sections 3, 7.1(5), 7.2(3), 11.2 (lowest rates)
and ADR 0011 N.3-N.5, N.7 (and the ADR's 5.35 msg/s slowest block).
Independent of the v2 scripts. Read-only; prints only.
"""
import math
from collections import Counter

from vc import NOM, NS, Nominal, Counter1D, hdr, iso, interp_counter, metrics_rows, ts, avg

n = Nominal()
W = n.dur_ns / NS  # 600.106644

hdr("A. Offered (sent_events.jsonl, harness monotonic)")
pubs = sorted(s["publish_monotonic_ns"] for s in n.sent)
f, l = n.el_host(pubs[0]), n.el_host(pubs[-1])
print("n %d first +%.6f last +%.6f" % (len(pubs), f, l))
r_nm1 = (len(pubs) - 1) / (l - f)
print("offered (n-1)/span %.6f ; n/span %.6f ; n/600.106644 %.6f ; n/600 %.6f" % (
    r_nm1, len(pubs) / (l - f), len(pubs) / W, len(pubs) / 600))
print("rounded to 4 dp: %.4f (plan 11.2000) -> equal at 4 dp: %s ; at 3 dp: %s" % (
    r_nm1, round(r_nm1, 4) == 11.2, round(r_nm1, 3) == 11.2))
blk = Counter(int(n.el_host(p) // 60) for p in pubs)
print("per 60 s block from window start (harness):", [blk[i] for i in range(10)])
print("device mix", Counter(s["device_type"] for s in n.sent))
print("warm-up device mix", Counter(e["device_type"] for e in n.warm))

hdr("B. Arrivals at the controller (controller monotonic)")
arr_m = sorted(e["received_monotonic_ns"] for e in n.post)
arr_w = sorted(e["received_monotonic_ns"] for e in n.warm)
print("measured arrivals (n-1)/span %.6f msg/s ; first el %.6f last el %.6f" % (
    (len(arr_m) - 1) / ((arr_m[-1] - arr_m[0]) / NS), n.el(arr_m[0]), n.el(arr_m[-1])))
print("warm-up arrivals: n %d first el %.6f last el %.6f" % (len(arr_w), n.el(arr_w[0]), n.el(arr_w[-1])))
ARR = Counter1D(arr_m + arr_w)
ACK = Counter1D([e["ditto_ack_monotonic_ns"] for e in n.post] + [e["ditto_ack_monotonic_ns"] for e in n.warm])
ackm = Counter1D([e["ditto_ack_monotonic_ns"] for e in n.post])

hdr("C. Served rate by phase")
rows = metrics_rows(NOM / "controller_metrics.csv")
pre = [r for r in rows if r["t"] < n.win0]
win = [r for r in rows if n.win0 <= r["t"] <= n.win1]
aft = [r for r in rows if r["t"] > n.win1]
print("samples pre/win/after/total", len(pre), len(win), len(aft), len(rows))
print("counters warm-up (first sample -> last pre-window sample): d %d over %.3f s = %.6f" % (
    pre[-1]["accepted"] - pre[0]["accepted"], pre[-1]["t"] - pre[0]["t"],
    (pre[-1]["accepted"] - pre[0]["accepted"]) / (pre[-1]["t"] - pre[0]["t"])))
print("counters warm-up (first sample -> first in-window sample): d %d over %.3f s = %.6f" % (
    win[0]["accepted"] - pre[0]["accepted"], win[0]["t"] - pre[0]["t"],
    (win[0]["accepted"] - pre[0]["accepted"]) / (win[0]["t"] - pre[0]["t"])))
dW = win[-1]["accepted"] - win[0]["accepted"]
tW = win[-1]["t"] - win[0]["t"]
cw = dW / tW
print("counters window first->last in-window sample: d %d over %.3f s = %.6f msg/s" % (dW, tW, cw))
ev_w = ACK.between(n.start_c, n.end_c)
print("event log acks in (el 0, el W]: %d ; /W = %.6f ; vs counters %+.4f %%" % (ev_w, ev_w / W, 100 * (ev_w / W / cw - 1)))
first_arr = min(arr_w)
print("event log warm-up acks (first arrival, el 0]: %d over %.3f s = %.6f" % (
    ACK.between(first_arr - 1, n.start_c), (n.start_c - first_arr) / NS,
    ACK.between(first_arr - 1, n.start_c) / ((n.start_c - first_arr) / NS)))
allacks = sorted([e["ditto_ack_monotonic_ns"] for e in n.post] + [e["ditto_ack_monotonic_ns"] for e in n.warm])
after = [a for a in allacks if a > n.end_c]
print("acks after window end %d ; last at el %.3f ; rate %d/(last-end) = %.6f ; (n-1)/(last-first after) = %.6f" % (
    len(after), n.el(after[-1]), len(after), len(after) / ((after[-1] - n.end_c) / NS),
    (len(after) - 1) / ((after[-1] - after[0]) / NS)))
print("offered/served(counters) %.6f ; net accumulation %.6f (using offered (n-1)/span)" % (r_nm1 / cw, r_nm1 - cw))

hdr("D. Fixed blocks, aligned at el 0 (event log; counters interpolated)")


def ctr_rate(a_el, b_el):
    ta = n.c2hw(n.start_c + a_el * NS)
    tb = n.c2hw(n.start_c + b_el * NS)
    return (interp_counter(rows, "accepted", tb) - interp_counter(rows, "accepted", ta)) / (b_el - a_el)


def blocks(width, lo=-120, hi=600):
    out = []
    a = lo
    while a < hi - 1e-9:
        b = a + width
        A = n.start_c + a * NS
        B = n.start_c + b * NS
        arr = ARR.between(A, B)
        ak = ACK.between(A, B)
        out.append((a, b, arr, ak, ak / width, ctr_rate(a, b)))
        a = b
    return out


for w in (60, 30):
    print("-- %d s blocks --" % w)
    bl = blocks(w)
    for a, b, arr, ak, r, c in bl:
        print("  %5d..%-5d arr %4d acks %4d ev %.4f ctr %.4f" % (a, b, arr, ak, r, c))
    print("  lowest ev %.4f at %s ; lowest in window %.4f ; highest in window %.4f" % (
        min(x[4] for x in bl), [x[:2] for x in bl if x[4] == min(y[4] for y in bl)],
        min(x[4] for x in bl if x[0] >= 0), max(x[4] for x in bl if x[0] >= 0)))
b10 = blocks(10)
print("-- 10 s blocks: lowest overall %.4f at %s ; lowest in window %.4f at %s" % (
    min(x[4] for x in b10), [x[:2] for x in b10 if x[4] == min(y[4] for y in b10)],
    min(x[4] for x in b10 if x[0] >= 0), [x[:2] for x in b10 if x[0] >= 0 and x[4] == min(y[4] for y in b10 if y[0] >= 0)]))
inw10 = [x for x in b10 if x[0] >= 0]
print("   in-window 10 s blocks with acks >= arrivals: %d of %d" % (sum(1 for x in inw10 if x[3] >= x[2]), len(inw10)))
print("   in-window 10 s blocks with acks >= arrivals counting only measured arrivals: %d" % (
    sum(1 for x in inw10 if x[3] >= Counter1D(arr_m).between(n.start_c + x[0] * NS, n.start_c + x[1] * NS))))
b1 = blocks(1, 0, 600)
print("   1 s bins in window with zero acks: %d of %d" % (sum(1 for x in b1 if x[3] == 0), len(b1)))
# window end is at 600.106644, not 600: note the last block edge
print("   note: block grid ends at el 600.000; window end el %.6f; acks in (600, W]: %d" % (
    W, ACK.between(n.start_c + 600 * NS, n.end_c)))

hdr("E. The queue")
zeros = [r["ts_utc"] for r in rows if r["queue_depth"] == 0]
print("samples with queue_depth 0:", zeros, "; first arrival harness wall", iso(n.c2hw(min(arr_w))))
for k in ("dropped", "rejected", "duplicate", "failed"):
    print("  max", k, max(r[k] for r in rows))
qd = [r["queue_depth"] for r in win]
dec = [(qd[i] - qd[i + 1]) for i in range(len(qd) - 1) if qd[i + 1] < qd[i]]
print("in-window samples %d first %d last %d min %d max %d ; decreases %d largest %d" % (
    len(qd), qd[0], qd[-1], min(qd), max(qd), len(dec), max(dec) if dec else 0))
print("max over all samples %d ; %.2f %% of 10000" % (max(r["queue_depth"] for r in rows), max(r["queue_depth"] for r in rows) / 100))


def insys(c):
    return ARR.le(c) - ACK.le(c)


print("in system at el 0: %d ; at window end: %d ; at deadline: %d" % (insys(n.start_c), insys(n.end_c), insys(n.deadline)))
print("growth reconstruction el0->end %d over %.3f s = %.4f msg/s" % (
    insys(n.end_c) - insys(n.start_c), W, (insys(n.end_c) - insys(n.start_c)) / W))
print("sampled growth %d over %.3f s ; deficit prediction (offered (n-1)/span - counter rate) x %.3f = %.2f" % (
    qd[-1] - qd[0], tW, tW, (r_nm1 - cw) * tW))
print("  alternative prediction with the arrival rate at the controller: %.2f" % (
    ((len(arr_m) - 1) / ((arr_m[-1] - arr_m[0]) / NS) - cw) * tW))

hdr("F. Around the window end and the drain (30 s blocks from the window end)")
E = n.end_c
for k in range(14):
    a = E + k * 30 * NS
    b = a + 30 * NS
    c = ACK.between(a, b)
    span = 30.0
    if b > allacks[-1]:
        span = (allacks[-1] - a) / NS
    print("  end+%3d..+%3d s (harness wall from %s): %3d acks = %.3f msg/s (per 30 s: %.3f)" % (
        k * 30, k * 30 + 30, iso(n.c2hw(a)), c, c / span, c / 30))
print("last 30 s of window (el 570..600): %.4f ; (W-30, W]: %.4f" % (
    ACK.between(n.start_c + 570 * NS, n.start_c + 600 * NS) / 30, ACK.between(E - 30 * NS, E) / 30))
print("first 30 s after end / window counter rate = %.4f" % (ACK.between(E, E + 30 * NS) / 30 / cw))
print("after deadline: %d acks over %.3f s = %.4f" % (ACK.between(n.deadline, allacks[-1]), (allacks[-1] - n.deadline) / NS,
                                                      ACK.between(n.deadline, allacks[-1]) / ((allacks[-1] - n.deadline) / NS)))
print("last metrics sample", rows[-1]["ts_utc"], "; stop hook started", [h["started_utc"] for h in n.m["collector_hooks"] if h["hook"] == "stop"])
print("fetch hook", [(h["started_utc"], h["finished_utc"]) for h in n.m["collector_hooks"] if h["hook"] == "fetch"])
print("10 s blocks el 560..640:", [round(ACK.between(n.start_c + a * NS, n.start_c + (a + 10) * NS) / 10, 1) for a in range(560, 640, 10)])
print("max 10 s drain block rate:", max(ACK.between(E + k * 10 * NS, E + (k + 1) * 10 * NS) / 10 for k in range(40)))

hdr("G. The ADR's N.7 blocks (5.35 .. 8.57): try plausible counter definitions")
# (i) sample nearest each 60 s edge on the harness wall grid from the window start
for label, grid in (("harness wall from measured_window_utc.start", n.win0),):
    vals = []
    for k in range(10):
        ta, tb = grid + 60 * k, grid + 60 * (k + 1)
        ra = min(rows, key=lambda r: abs(r["t"] - ta))
        rb = min(rows, key=lambda r: abs(r["t"] - tb))
        vals.append((rb["accepted"] - ra["accepted"]) / (rb["t"] - ra["t"]))
    print(label, "nearest samples, rate over sample span:", [round(v, 4) for v in vals])
    vals = []
    for k in range(10):
        ta, tb = grid + 60 * k, grid + 60 * (k + 1)
        vals.append((interp_counter(rows, "accepted", tb) - interp_counter(rows, "accepted", ta)) / 60)
    print(label, "interpolated:", [round(v, 4) for v in vals])
    # last sample at or before each edge, divided by 60
    vals = []
    for k in range(10):
        ta, tb = grid + 60 * k, grid + 60 * (k + 1)
        ra = [r for r in rows if r["t"] <= ta][-1]
        rb = [r for r in rows if r["t"] <= tb][-1]
        vals.append((rb["accepted"] - ra["accepted"]) / 60)
    print(label, "last sample <= edge, /60:", [round(v, 4) for v in vals])
    vals = []
    for k in range(10):
        ta, tb = grid + 60 * k, grid + 60 * (k + 1)
        ra = [r for r in rows if r["t"] <= ta][-1]
        rb = [r for r in rows if r["t"] <= tb][-1]
        vals.append((rb["accepted"] - ra["accepted"]) / (rb["t"] - ra["t"]))
    print(label, "last sample <= edge, /sample span:", [round(v, 4) for v in vals])
# (ii) consecutive groups of 60 in-window samples
vals = []
for k in range(10):
    g = win[60 * k: 60 * (k + 1) + 1]
    if len(g) > 1:
        vals.append((g[-1]["accepted"] - g[0]["accepted"]) / (g[-1]["t"] - g[0]["t"]))
print("groups of 60 in-window samples:", [round(v, 4) for v in vals])
