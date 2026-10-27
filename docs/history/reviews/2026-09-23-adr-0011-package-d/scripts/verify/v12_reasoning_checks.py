"""v12 - figures behind the reasoning objections (not figures of the documents themselves).

(a) backlog_diagnosis 9.1 "every measured message's wait includes that time": how many measured messages were
    actually in the controller while a warm-up message was being served (arrived before the last warm-up ack)?
(b) 7.1(2)/9.1 "none of the 3,593 ... was a warm-up message": decomposition of the end-of-window count.
(c) section 11.4 refutation band: largest in-window own passage and messages that 2.24 msg/s would bring meanwhile;
    passages longer than 3/2.24 s among the measured messages.
Read-only; prints only.
"""
from vc import NS, Nominal, hdr

n = Nominal()
allm = n.merged()
rec = [e["received_monotonic_ns"] for e in allm]
ack = [e["ditto_ack_monotonic_ns"] for e in allm]
wl = [i for i, e in enumerate(allm) if e["_ph"] == "w"]
ml = [i for i, e in enumerate(allm) if e["_ph"] == "m"]
last_w_ack = max(ack[i] for i in wl)
hdr("(a) measured messages that waited while warm-up messages were being served")
k = sum(1 for i in ml if rec[i] < last_w_ack)
print("measured arrivals before the last warm-up ack (el %.3f): %d of %d" % (n.el(last_w_ack), k, len(ml)))
print("measured arrivals after it: %d -- their waits contain no warm-up service time; any warm-up effect on them"
      " is the propagated shift that section 9.2 declares not derivable" % (len(ml) - k))
hdr("(b) the end-of-window count")
S0, S1 = n.start_c, n.end_c
ins0 = sum(1 for r in rec if r <= S0) - sum(1 for a in ack if a <= S0)
arrW = sum(1 for r in rec if S0 < r <= S1)
ackW = sum(1 for a in ack if S0 < a <= S1)
print("in controller at el 0: %d ; arrivals in window: %d ; acks in window: %d ; end: %d = %d + %d - %d" % (
    ins0, arrW, ackW, ins0 + arrW - ackW, ins0, arrW, ackW))
print("of the in-window acks, warm-up: %d ; of the in-window arrivals, warm-up: %d" % (
    sum(1 for i in wl if S0 < ack[i] <= S1), sum(1 for i in wl if S0 < rec[i] <= S1)))
hdr("(c) passages vs the proposed +-3 refutation band at 2.24 msg/s")
own = sorted(((ack[i] - ack[i - 1]) / NS, n.el(ack[i])) for i in ml)
thr = 3 / 2.24
print("threshold passage 3/2.24 = %.3f s ; measured passages longer: %d ; longest %.3f s at el %.1f" % (
    thr, sum(1 for o, _ in own if o > thr), own[-1][0], own[-1][1]))
allown = sorted((ack[i] - ack[i - 1]) / NS for i in range(1, len(allm)))
print("all passages (warm-up included) longer than %.3f s: %d ; longest %.3f s" % (thr, sum(1 for o in allown if o > thr), allown[-1]))

hdr("(d) restart runs: 'with an outcome at the fetch' split by the controller-clock deadline")
from vc import R01, R02, rj, rjl, ts, iso
for tag, path in (("r01", R01), ("r02", R02)):
    m = rj(path / "manifest.json")
    ev = rjl(path / "events.jsonl")
    dl = m["confirmation_deadline_monotonic_ns"]
    mk = m["controller_marker"]
    on = sum(1 for e in ev if e["outcome"] == "accepted" and e["ditto_ack_monotonic_ns"] <= dl)
    late = sum(1 for e in ev if e["outcome"] == "accepted" and e["ditto_ack_monotonic_ns"] > dl)
    newest = max(e["ditto_ack_monotonic_ns"] for e in ev)
    print("%s: with outcome %d = on time %d + late %d ; deadline (harness wall) %s ; fetch started %s ; newest ack deadline%+.3f s" % (
        tag, len(ev), on, late, iso(ts(mk["polled_utc"]) + 60), m["events_fetch"]["attempts"][0]["started_utc"], (newest - dl) / 1e9))
