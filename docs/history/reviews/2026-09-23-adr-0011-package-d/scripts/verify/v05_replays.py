"""v05 - the two warm-up replays of backlog_diagnosis.md section 9.2, rebuilt from their wording.

R-msg : each measured message keeps its own observed occupancy (ack_k - ack_{k-1}); server empty at the
        first measured arrival.
R-slot: the server keeps the durations of its observed service slots after el 0, in order; server empty at el 0.
Also: what is exactly derivable without a service model (bounds), to test the claim that nothing is.
Read-only; prints only.
"""
from vc import NS, Nominal, hdr, avg

n = Nominal()
allm = n.merged()
N = len(allm)
rec = [e["received_monotonic_ns"] for e in allm]
ack = [e["ditto_ack_monotonic_ns"] for e in allm]
idx = [i for i in range(N) if allm[i]["_ph"] == "m"]
S0 = n.start_c
DL = n.deadline


def replay(durs, start, label):
    t = start
    idle = 0
    out = []
    for j, i in enumerate(idx):
        if rec[i] > t:
            idle += 1
            t = rec[i]
        t = t + durs[j]
        out.append(t)
    shift = [(ack[i] - o) / NS for i, o in zip(idx, out)]
    lat = [(o - rec[i]) / NS for i, o in zip(idx, out)]
    ontime = sum(1 for o in out if o <= DL)
    hdr(label)
    print("idle before %d ; mean latency %.3f s ; shift min %.6f mean %.6f max %.6f ; on time %d (+%d) ; late %d" % (
        idle, avg(lat), min(shift), avg(shift), max(shift), ontime, ontime - 3794, len(idx) - ontime))


own = [ack[i] - ack[i - 1] for i in idx]
replay(own, rec[idx[0]], "R-msg (message-indexed own durations; empty at first measured arrival)")

post0 = [k for k in range(N) if ack[k] > S0]
slots_a = [ack[k] - ack[k - 1] for k in post0]            # first slot starts at the last pre-el-0 ack
replay(slots_a, S0, "R-slot a (slots = inter-ack gaps of the acks after el 0; empty at el 0)")
slots_b = [ack[post0[0]] - S0] + [ack[k] - ack[k - 1] for k in post0[1:]]   # first slot truncated at el 0
replay(slots_b, S0, "R-slot b (first slot measured from el 0)")

hdr("Observed, for reference")
print("observed on time 3794 ; observed mean latency %.3f" % avg([(ack[i] - rec[i]) / NS for i in idx]))
