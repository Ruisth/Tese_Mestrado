"""v06 - resources (backlog_diagnosis.md section 6 and 7.1(3-4)).

Window instants are chosen two ways (guest wall through the marker's wall_utc; harness wall window) to show
whether the choice matters. Read-only; prints only.
"""
import bisect
from collections import defaultdict

from vc import NOM, NS, Nominal, hdr, metrics_rows, res_rows, q, avg, corr, interp_counter

n = Nominal()
R = res_rows(NOM / "resources.csv")
inst = sorted({r["t"] for r in R})
hdr("A. Coverage")
print("rows %d instants %d containers %s" % (len(R), len(inst), sorted({r["c"] for r in R})))
gaps = [b - a for a, b in zip(inst, inst[1:])]
print("max spacing %.3f ; gaps>2 s %d" % (max(gaps), sum(1 for g in gaps if g > 2)))
g0 = n.c2gw(n.start_c)
g1 = n.c2gw(n.end_c)
win_g = [t for t in inst if g0 < t <= g1]
win_h = [t for t in inst if n.win0 < t <= n.win1]
print("window in guest wall (%.3f..%.3f): %d instants ; harness-wall window: %d instants ; same set: %s" % (
    g0 % 60, g1 % 60, len(win_g), len(win_h), win_g == win_h))
print("instants after the guest-wall window end: %d ; before start: %d" % (sum(1 for t in inst if t > g1), sum(1 for t in inst if t <= g0)))
by = defaultdict(dict)
for r in R:
    by[r["t"]][r["c"]] = r
WIN = win_g

hdr("B. Per container, window")
cs = sorted({r["c"] for r in R})
for c in cs:
    v = [by[t][c]["cpu"] for t in WIN]
    mp = [by[t][c]["memp"] for t in WIN]
    print("%-22s mean %.2f p50 %.2f p95 %.2f max %.2f  mem%% max %.2f" % (c, avg(v), q(v, 50), q(v, 95), max(v), max(mp)))
tot = [sum(by[t][c]["cpu"] for c in cs) for t in WIN]
print("sum six: mean %.2f p50 %.2f p95 %.2f max %.2f ; >=300: %d ; >=350: %d ; >=380: %d" % (
    avg(tot), q(tot, 50), q(tot, 95), max(tot), sum(1 for x in tot if x >= 300), sum(1 for x in tot if x >= 350), sum(1 for x in tot if x >= 380)))
allmed = {c: q([by[t][c]["cpu"] for t in inst], 50) for c in cs}
print("medians over all instants:", {c: round(v, 2) for c, v in sorted(allmed.items(), key=lambda x: -x[1])})
mos = [by[t]["egw-mosquitto-1"]["mem"] for t in WIN]
print("mosquitto mem mean %.2f MiB (window) ; over all instants %.2f MiB" % (avg(mos) / 2**20, avg([by[t]["egw-mosquitto-1"]["mem"] for t in inst]) / 2**20))

hdr("C. Controller CPU vs busy time; shares")
ctl = [by[t]["egw-controller-1"]["cpu"] for t in WIN]
print("controller mean %.3f %% ; CPU-s over %d one-second instants %.2f ; / 600.107 s = %.3f %%" % (
    avg(ctl), len(WIN), sum(ctl) / 100, sum(ctl) / 100 / (n.dur_ns / NS) * 100))
means = {c: avg([by[t][c]["cpu"] for t in WIN]) for c in cs}
S = sum(means.values())
ditto = sum(v for c, v in means.items() if "ditto" in c)
print("shares: ditto %.2f %% mongo %.2f %% controller %.2f %% mosquitto %.2f %%" % (
    100 * ditto / S, 100 * means["egw-mongodb-1"] / S, 100 * means["egw-controller-1"] / S, 100 * means["egw-mosquitto-1"] / S))
print("per ack in window (3878): controller %.2f ms ; six %.2f ms" % (sum(ctl) / 100 / 3878 * 1000, sum(tot) / 100 / 3878 * 1000))
print("per measured ack in window (3127): controller %.2f ms" % (sum(ctl) / 100 / 3127 * 1000))

hdr("D. Acks/s against summed CPU")
acks = sorted([e["ditto_ack_monotonic_ns"] for e in n.post] + [e["ditto_ack_monotonic_ns"] for e in n.warm])
acks_m = sorted(e["ditto_ack_monotonic_ns"] for e in n.post)
rows = metrics_rows(NOM / "controller_metrics.csv")


def E(t, a=acks):
    c = n.gw2c(t)
    return bisect.bisect_right(a, c) - bisect.bisect_right(a, c - NS)


def C(t):
    th = t - (n.mk_guest - n.mk_host)   # guest wall -> harness wall through the marker
    return interp_counter(rows, "accepted", th) - interp_counter(rows, "accepted", th - 1)


e = [E(t) for t in WIN]
cc = [C(t) for t in WIN]
em = [E(t, acks_m) for t in WIN]
bands = [(150, 200), (200, 250), (250, 300), (300, 350), (350, 1e9)]
for lo, hi in bands:
    sel = [i for i, x in enumerate(tot) if lo <= x < hi]
    print("band %4d..%-5s n %3d  E %.3f  C %.3f" % (lo, "" if hi > 1e8 else hi, len(sel), avg([e[i] for i in sel]), avg([cc[i] for i in sel])))
print("below 150:", sum(1 for x in tot if x < 150))
print("Pearson r: E %.4f ; C %.4f ; measured-only E %.4f" % (corr(tot, e), corr(tot, cc), corr(tot, em)))
# same association with the CONTROLLER's own CPU removed from the sum
tot_nc = [sum(by[t][c]["cpu"] for c in cs if c != "egw-controller-1") for t in WIN]
print("Pearson r E vs sum without controller: %.4f ; E vs ditto trio: %.4f ; E vs controller cpu: %.4f ; E vs mongodb: %.4f" % (
    corr(tot_nc, e), corr([sum(by[t][c]["cpu"] for c in cs if "ditto" in c) for t in WIN], e), corr(ctl, e),
    corr([by[t]["egw-mongodb-1"]["cpu"] for t in WIN], e)))
# lag structure: E at t vs CPU at t+-1
for lag in (-2, -1, 1, 2):
    x = [tot[i] for i in range(len(WIN)) if 0 <= i + lag < len(WIN)]
    y = [e[i + lag] for i in range(len(WIN)) if 0 <= i + lag < len(WIN)]
    print("  r(sumCPU_t, E_t%+d) = %.4f" % (lag, corr(x, y)))
