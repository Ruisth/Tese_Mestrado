"""v01 - populations, collection instants, latency by population.

Checks backlog_diagnosis.md sections 0-2 and ADR 0011 section 1.7.
Independent of the v2 scripts. Read-only; prints only.
"""
import json
from collections import Counter, defaultdict

from vc import NOM, ANA, ATT, NS, Nominal, hdr, iso, q, avg, rj, ts

n = Nominal()
m = n.m

hdr("0. Platform and anchors")
sut = rj(NOM / "sut_environment.json")
lg = rj(NOM / "loadgen_environment.json")
print("sut_environment.json:", json.dumps(sut)[:600])
print("loadgen_environment.json:", json.dumps(lg)[:600])
print("marker monotonic_ns", m["controller_marker"]["monotonic_ns"], "== controller_monotonic_at_run_end_ns",
      m["controller_monotonic_at_run_end_ns"])
print("marker polled_utc", m["controller_marker"]["polled_utc"], "lag_s", m["controller_marker"]["lag_s"],
      "wall_utc (controller/guest)", m["controller_marker"]["wall_utc"])
print("measured duration harness monotonic: %.6f s" % (n.dur_ns / NS))
print("validity", m["validity"], "deviations", m["deviations"], "warnings", m["warnings"])
print("window start, controller clock ns:", n.start_c)

hdr("A. Deadline")
print("deadline", n.deadline, "deadline - marker = %.9f s" % ((n.deadline - n.end_c) / NS),
      "confirmation_window_s", m["confirmation_window_s"])
print("deadline mapped to harness wall via marker:", iso(n.c2hw(n.deadline)))

hdr("B. Prefix property of the two copies")
with open(NOM / "events.jsonl", "rb") as fh:
    sealed_lines = [l for l in fh.read().split(b"\n") if l.strip()]
with open(ANA / "events.post-drain.jsonl", "rb") as fh:
    post_lines = [l for l in fh.read().split(b"\n") if l.strip()]
same = sum(1 for a, b in zip(sealed_lines, post_lines) if a == b)
print("sealed lines", len(sealed_lines), "post lines", len(post_lines),
      "identical leading lines", same, "all sealed lines are the leading lines of post:",
      same == len(sealed_lines))

hdr("C. Populations by identity")
sent_ids = {s["message_id"]: s for s in n.sent}
print("sent records", len(n.sent), "unique ids", len(sent_ids),
      "intended_invalid true", sum(1 for s in n.sent if s["intended_invalid"]))
print("sent records with null puback_monotonic_ns", sum(1 for s in n.sent if s.get("puback_monotonic_ns") is None))


def classify(events):
    acc = defaultdict(list)
    oc = Counter()
    for e in events:
        oc[e["outcome"]] += 1
        if e["outcome"] == "accepted":
            acc[e["message_id"]].append(e)
    cls = {}
    for mid in sent_ids:
        if mid not in acc:
            cls[mid] = "none"
        else:
            first = min(acc[mid], key=lambda e: e["ditto_ack_monotonic_ns"])
            cls[mid] = "in" if first["ditto_ack_monotonic_ns"] <= n.deadline else "late"
    return cls, oc, acc


cs, ocs, accs = classify(n.sealed)
cp, ocp, accp = classify(n.post)
print("sealed outcomes", dict(ocs), "classes", Counter(cs.values()))
print("post outcomes", dict(ocp), "classes", Counter(cp.values()))
print("ids in sealed not in sent:", len({e['message_id'] for e in n.sealed} - set(sent_ids)),
      "; ids in post not in sent:", len({e['message_id'] for e in n.post} - set(sent_ids)))
print("repeated accepted ids sealed/post:", sum(1 for v in accs.values() if len(v) > 1),
      sum(1 for v in accp.values() if len(v) > 1))
tr = Counter((cs[i], cp[i]) for i in sent_ids)
print("transitions sealed->post", dict(tr))
per = defaultdict(Counter)
for i, s in sent_ids.items():
    per[s["device_type"]][cs[i]] += 1
for d in sorted(per):
    print("  per device at the fetch", d, dict(per[d]))
print("accounting.json at_harness_fetch_per_device", json.dumps(n.acct["at_harness_fetch_per_device"]))
nin = sum(1 for v in cs.values() if v == "in")
print("in time share %.4f %% ; not in time %.4f %%" % (100 * nin / 6720, 100 * (6720 - nin) / 6720))

hdr("D. Collection instants")
c4 = [c for c in n.cmds if c["seq"] == 4][0]
c5 = [c for c in n.cmds if c["seq"] == 5][0]
c6 = [c for c in n.cmds if c["seq"] == 6][0]
scp1 = ts(m["events_fetch"]["attempts"][0]["started_utc"])
dl_hw = n.c2hw(n.deadline)
print("sealed scp start", m["events_fetch"]["attempts"][0]["started_utc"], "-> deadline + %.3f s" % (scp1 - dl_hw))
print("cmd seq4 harness-run ended", c4["ended_utc"], "-> deadline + %.3f s" % (ts(c4["ended_utc"]) - dl_hw))
mx_sealed = max(e["ditto_ack_monotonic_ns"] for e in n.sealed)
print("newest ack in sealed: deadline + %.3f s ; harness wall %s" % ((mx_sealed - n.deadline) / NS, iso(n.c2hw(mx_sealed))))
late85 = [min(accs[i], key=lambda e: e["ditto_ack_monotonic_ns"])["ditto_ack_monotonic_ns"] for i in sent_ids if cs[i] == "late"]
print("P2 (late at fetch) ack range after deadline: %.3f .. %.3f s" % ((min(late85) - n.deadline) / NS, (max(late85) - n.deadline) / NS))
print("cmd seq5 drained", c5["started_utc"], "->", c5["ended_utc"], "duration", c5["duration_s"])
print("cmd seq6 scp", c6["started_utc"], "->", c6["ended_utc"])
print("post scp start - sealed scp start = %.3f s" % (ts(c6["started_utc"]) - scp1))
with open(ATT / "console" / "005-post-drain.stdout.txt") as fh:
    print("console/005:", fh.read().strip())
mx_post = max(e["ditto_ack_monotonic_ns"] for e in n.post)
print("newest ack in post: deadline + %.3f s ; harness wall %s ; window end + %.3f s" % (
    (mx_post - n.deadline) / NS, iso(n.c2hw(mx_post)), (mx_post - n.end_c) / NS))
sa = n.snap_after
sb = n.snap_before
print("after snapshot (controller wall_utc, guest clock):", sa["wall_utc"], {k: sa[k] for k in ("accepted", "received", "queue_depth", "in_progress", "dropped", "processing_errors")})
print("after snapshot monotonic - newest ack: %.3f s" % ((sa["monotonic_ns"] - mx_post) / NS))
print("before snapshot", sb["wall_utc"], {k: sb[k] for k in ("accepted", "received", "queue_depth", "in_progress")})
p3 = [i for i in sent_ids if cs[i] == "none"]
p3acks = [min(accp[i], key=lambda e: e["ditto_ack_monotonic_ns"])["ditto_ack_monotonic_ns"] for i in p3]
p3recv = [min(accp[i], key=lambda e: e["ditto_ack_monotonic_ns"])["received_monotonic_ns"] for i in p3]
print("P3: received before deadline", sum(1 for r in p3recv if r <= n.deadline), "of", len(p3),
      "; acked after deadline %.3f .. %.3f s" % ((min(p3acks) - n.deadline) / NS, (max(p3acks) - n.deadline) / NS))
print("P3: received before the WINDOW END (controller marker)", sum(1 for r in p3recv if r <= n.end_c))
print("measured identities received after deadline:", sum(1 for e in n.post if e["received_monotonic_ns"] > n.deadline))

hdr("E. Latency (s) by population, harness percentile convention")


def lat_of(acc, ids):
    return [min(acc[i], key=lambda e: e["ditto_ack_monotonic_ns"])["latency_ms"] / 1000 for i in ids]


def row(name, v):
    print("%-38s n=%5d mean %.3f p50 %.3f p95 %.3f p99 %.3f max %.3f" % (
        name, len(v), avg(v), q(v, 50), q(v, 95), q(v, 99), max(v)))


row("P1 in time (sealed)", lat_of(accs, [i for i in sent_ids if cs[i] == "in"]))
row("P2 late at fetch (sealed)", lat_of(accs, [i for i in sent_ids if cs[i] == "late"]))
row("P2' late (post)", lat_of(accp, [i for i in sent_ids if cp[i] == "late"]))
row("all 6720 (post)", lat_of(accp, list(sent_ids)))
hr = n.acct["harness_row"]
print("accounting harness_row p50/p95/max ms:", hr["latency_ms_p50"], hr["latency_ms_p95"], hr["latency_ms_max"])
v = sorted(lat_of(accs, [i for i in sent_ids if cs[i] == "in"]))
print("P1 p50/p95/max ms, recomputed: %.6f %.6f %.6f" % (q(v, 50) * 1000, q(v, 95) * 1000, max(v) * 1000))
