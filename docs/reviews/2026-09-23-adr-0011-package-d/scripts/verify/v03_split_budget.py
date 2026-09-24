"""v03 - FIFO/busy checks, exact wait/own split, per-message budget, reconstruction vs sampled depth.

Checks backlog_diagnosis.md sections 4, 5, 8 (cross-check), 9.1 and ADR 0011 N.3.
Independent of the v2 scripts. Read-only; prints only.
"""
import bisect
from collections import Counter

from vc import NOM, NS, Nominal, hdr, metrics_rows, q, avg

n = Nominal()
W = n.dur_ns / NS
allm = n.merged()
N = len(allm)
rec = [e["received_monotonic_ns"] for e in allm]
ack = [e["ditto_ack_monotonic_ns"] for e in allm]

hdr("A. Order and busy checks")
print("messages", N, "(warm-up %d, measured %d)" % (sum(1 for e in allm if e["_ph"] == "w"), sum(1 for e in allm if e["_ph"] == "m")))
fifo = all(ack[i] < ack[i + 1] for i in range(N - 1))
print("acks strictly increasing in arrival order:", fifo)
ties = sum(1 for i in range(N - 1) if rec[i] == rec[i + 1])
print("arrival ties:", ties)
idle = [i for i in range(1, N) if rec[i] > ack[i - 1]]
print("messages arriving after predecessor's ack:", len(idle))
wl = [e for e in allm if e["_ph"] == "w"]
ml = [e for e in allm if e["_ph"] == "m"]
print("last warm-up arrival el %.6f ; first measured arrival el %.6f" % (n.el(wl[-1]["received_monotonic_ns"]), n.el(ml[0]["received_monotonic_ns"])))
print("last warm-up ack el %.6f ; first measured ack el %.6f" % (n.el(max(e["ditto_ack_monotonic_ns"] for e in wl)), n.el(min(e["ditto_ack_monotonic_ns"] for e in ml))))
print("first arrival el %.3f ; last ack el %.3f" % (n.el(rec[0]), n.el(ack[-1])))
mx = max(abs((e["ditto_ack_monotonic_ns"] - e["received_monotonic_ns"]) / 1e6 - e["latency_ms"]) for e in allm)
print("max |(ack-recv)/1e6 - latency_ms| = %.9f ms" % mx)
firstdev = {}
for e in allm:
    firstdev.setdefault(e["device_type"], e["_ph"])
print("first message per device phase:", firstdev)
print("attempts>1:", sum(1 for e in allm if e.get("attempts", 1) != 1), "; non-null error:", sum(1 for e in allm if e.get("error") is not None))
print("outcomes:", Counter(e["outcome"] for e in allm))
# Is the consumer necessarily continuously busy? The ack stamp precedes the line write; the next dequeue follows the write.
# "busy" here means only: a message was always waiting when the previous ack stamp was taken.

hdr("B. Exact split for the 6,720 measured messages")
idx = [i for i in range(N) if allm[i]["_ph"] == "m"]
wait = [(ack[i - 1] - rec[i]) / NS for i in idx]
own = [(ack[i] - ack[i - 1]) / 1e6 for i in idx]
lat = [(ack[i] - rec[i]) / NS for i in idx]
print("wait s: min %.3f p50 %.3f mean %.3f p95 %.3f max %.3f" % (min(wait), q(wait, 50), avg(wait), q(wait, 95), max(wait)))
print("own ms: min %.2f p50 %.2f mean %.2f p95 %.2f max %.2f" % (min(own), q(own, 50), avg(own), q(own, 95), max(own)))
share = [w / L for w, L in zip(wait, lat)]
print("sum wait / sum latency = %.4f %% ; per-message share p50 %.4f %% min %.4f %%" % (100 * sum(wait) / sum(lat), 100 * q(share, 50), 100 * min(share)))
i0 = idx[0]
print("first measured: latency %.6f = wait %.6f + own %.6f ; in controller at its arrival (incl. itself? no): %d" % (
    lat[0], wait[0], own[0] / 1000, bisect.bisect_right(rec, rec[i0]) - 1 - bisect.bisect_right(ack, rec[i0])))
print("  own share at the median-wait-share message: %.4f %%" % (100 - 100 * q(share, 50)))

hdr("C. Budget by population (mean inter-ack gap)")
S0, S1 = n.start_c, n.end_c


def pop(sel, name):
    g = [(ack[i] - ack[i - 1]) / 1e6 for i in range(1, N) if sel(i)]
    print("%-40s n=%5d mean %.2f ms p50 %.2f p95 %.2f 1/mean %.4f msg/s sum %.3f s" % (
        name, len(g), avg(g), q(g, 50), q(g, 95), 1000 / avg(g), sum(g) / 1000))
    return g


pop(lambda i: allm[i]["_ph"] == "m" and S0 < ack[i] <= S1, "M-in (measured, ack in window)")
pop(lambda i: allm[i]["_ph"] == "m" and ack[i] > S1, "M-after (measured, ack after end)")
pop(lambda i: allm[i]["_ph"] == "m", "M-all")
g = pop(lambda i: allm[i]["_ph"] == "w" and S0 < ack[i] <= S1, "W-in (warm-up, ack in window)")
D = pop(lambda i: S0 < ack[i] <= S1, "D (every ack in window)")
last_pre = max(a for a in ack if a <= S0)
last_in = max(a for a in ack if a <= S1)
print("D span last pre-window ack -> last in-window ack = %.6f s ; span/n = %.4f ms" % ((last_in - last_pre) / NS, (last_in - last_pre) / 1e6 / len(D)))
print("W-in share of D: %d/%d = %.2f %% ; time %.3f / %.3f s = %.2f %%" % (
    len(g), len(D), 100 * len(g) / len(D), sum(g) / 1000, sum(D) / 1000, 100 * sum(g) / sum(D)))
print("M-in by 60 s block of the ack:")
for k in range(10):
    a, b = S0 + 60 * k * NS, S0 + 60 * (k + 1) * NS
    gg = [(ack[i] - ack[i - 1]) / 1e6 for i in range(1, N) if allm[i]["_ph"] == "m" and a < ack[i] <= b and ack[i] <= S1]
    print("  el %3d..%3d n=%4d mean %s" % (60 * k, 60 * k + 60, len(gg), ("%.2f ms" % avg(gg)) if gg else "-"))
# same-device-mix claim for W-in vs M-in
wmix = Counter(allm[i]["device_type"] for i in range(1, N) if allm[i]["_ph"] == "w" and S0 < ack[i] <= S1)
mmix = Counter(allm[i]["device_type"] for i in range(1, N) if allm[i]["_ph"] == "m" and S0 < ack[i] <= S1)
print("device mix W-in", dict(wmix), "; M-in", dict(mmix))

hdr("D. Reconstruction vs sampled queue_depth")
rows = metrics_rows(NOM / "controller_metrics.csv")
srec = sorted(rec)
sack = sorted(ack)
diffs = []
for r in rows:
    c = n.hw2c(r["t"])
    ins = bisect.bisect_right(srec, c) - bisect.bisect_right(sack, c)
    waiting = max(ins - 1, 0)
    diffs.append(r["queue_depth"] - waiting)
print("samples %d mean diff %+.3f median %+.1f max|d| %d outside +-3: %d" % (
    len(diffs), avg(diffs), q(diffs, 50), max(abs(d) for d in diffs), sum(1 for d in diffs if abs(d) > 3)))
# sensitivity to the anchor: shift by the marker lag (0.018718 s) and by the guest-host wall offset
for sh in (-0.126, -0.018718, 0.018718, 0.126, 0.5, 1.0):
    dd = []
    for r in rows:
        c = n.hw2c(r["t"] + sh)
        ins = bisect.bisect_right(srec, c) - bisect.bisect_right(sack, c)
        dd.append(r["queue_depth"] - max(ins - 1, 0))
    print("  anchor shifted %+.3f s: mean %+.3f max|d| %d" % (sh, avg(dd), max(abs(d) for d in dd)))

hdr("E. Warm-up inheritance counts")


def insys(c):
    return bisect.bisect_right(srec, c) - bisect.bisect_right(sack, c)


wrec = sorted(e["received_monotonic_ns"] for e in wl)
wack = sorted(e["ditto_ack_monotonic_ns"] for e in wl)
print("warm-up in controller at el 0:", bisect.bisect_right(wrec, S0) - bisect.bisect_right(wack, S0))
print("warm-up acked after el 0:", sum(1 for a in wack if a > S0), "; arrived after el 0:", sum(1 for r in wrec if r > S0))
fm = ml[0]["received_monotonic_ns"]
print("warm-up in controller at first measured arrival:", bisect.bisect_right(wrec, fm) - bisect.bisect_right(wack, fm))
print("last warm-up ack el %.6f ; consumer time on warm-up after first measured arrival %.6f s" % (n.el(wack[-1]), (wack[-1] - fm) / NS))
print("in system at end:", insys(S1), "; warm-up among them:", bisect.bisect_right(wrec, S1) - bisect.bisect_right(wack, S1))
