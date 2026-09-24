"""v04 - Little's law over the stated 'empty-to-empty interval' (backlog_diagnosis.md section 8).

Checks which interval T the figures 1,125.348 s / L 1,904.4154 / lambda 7.1658 / W 265.7652 belong to,
and what the same computation gives over the interval the text names (the two /metrics snapshots).
Read-only; prints only.
"""
import random

from vc import NS, Nominal, hdr

n = Nominal()
allm = n.merged()
rec = [e["received_monotonic_ns"] for e in allm]
ack = [e["ditto_ack_monotonic_ns"] for e in allm]
soj = sum((a - r) for a, r in zip(ack, rec)) / NS
cnt = len(allm)
sb, sa = n.snap_before, n.snap_after
print("snapshots: before wall %s mono %d ; after wall %s mono %d" % (sb["wall_utc"], sb["monotonic_ns"], sa["wall_utc"], sa["monotonic_ns"]))


def little(T0, T1, label):
    T = (T1 - T0) / NS
    # integral of N(t) over [T0,T1] by events: each message contributes its overlap with [T0,T1]
    integ = sum(max(0, min(a, T1) - max(r, T0)) for r, a in zip(rec, ack)) / NS
    L = integ / T
    lam = cnt / T
    Wm = soj / cnt
    hdr(label)
    print("T %.3f s ; integral N dt %.3f ; sum sojourn %.3f ; L %.4f ; lambda %.4f ; W %.4f ; L/(lambda W) %.10f" % (
        T, integ, soj, L, lam, Wm, L / (lam * Wm)))


little(min(rec), max(ack), "A. T = first arrival -> last acknowledgement (what the figures use?)")
little(sb["monotonic_ns"], sa["monotonic_ns"], "B. T = the two /metrics snapshots the text names as the interval")

hdr("C. Identity on fabricated departures")
random.seed(1)
fab = [r + int(random.uniform(0, 900) * NS) for r in rec]
T0, T1 = min(rec), max(fab)
integ = sum(a - r for r, a in zip(rec, fab)) / NS
T = (T1 - T0) / NS
print("U(0,900): L/(lambda W) = %.10f" % ((integ / T) / ((cnt / T) * (integ / cnt))))
