"""v08 - controller_restart-r01 and -r02 figures of ADR 0011 sections 1.1-1.6, N8, and the proof sizing (R0x.10).

Written from the raw run directories, without the ADR's script. Read-only; prints only.
Clock domains: sent_events (harness monotonic -> harness wall through measured_started_monotonic_ns and
measured_window_utc.start; cross-checked against restart.started_monotonic_ns/started_utc), controller_metrics
(harness wall), events.jsonl (controller monotonic -> harness wall through the end marker), collector (guest wall).
"""
import sys
from collections import Counter

from vc import R01, R02, NS, hdr, iso, metrics_rows, res_rows, rj, rjl, ts


def run(path, tag):
    hdr("%s: %s" % (tag, path.name))
    m = rj(path / "manifest.json")
    sent = rjl(path / "sent_events.jsonl")
    ev = rjl(path / "events.jsonl")
    rows = metrics_rows(path / "controller_metrics.csv")
    col = res_rows(list((path / "logs" / "collector").glob("resources-*.csv"))[0])
    h0 = m["measured_started_monotonic_ns"]
    w0 = ts(m["measured_window_utc"]["start"])
    rs = m["restart"]
    # harness monotonic -> harness wall
    h2w = lambda h: w0 + (h - h0) / NS
    drift = (ts(rs["started_utc"]) - h2w(rs["started_monotonic_ns"]))
    print("anchor check: restart.started_utc - mapped(restart.started_monotonic_ns) = %.4f s" % drift)
    mk = m["controller_marker"]
    c2w = lambda c: ts(mk["polled_utc"]) + (c - mk["monotonic_ns"]) / NS
    print("%s.0 rate %s duration %s requested_at_s %s restart started %s finished %s rc %s ; events fetch started %s ; validity %s ; commit %s" % (
        tag, m["rate_msg_s"], m["duration_s"], rs["requested_at_s"], rs["started_utc"], rs["finished_utc"], rs["returncode"],
        m["events_fetch"]["attempts"][0]["started_utc"], m["validity"], m["commit"][:7]))
    print("   restart command wall - window start = %.3f s" % (ts(rs["started_utc"]) - w0))
    print("   warnings:", [w[:160] for w in m["warnings"]])
    # 1. outcomes
    oc = Counter(e["outcome"] for e in ev)
    have = {e["message_id"] for e in ev}
    no = [i for i, s in enumerate(sent, 1) if s["message_id"] not in have]
    print("%s.1 published %d valid %d with outcome %d without %d outcomes %s event lines %d unique ids in events %d" % (
        tag, len(sent), sum(1 for s in sent if not s["intended_invalid"]), len(sent) - len(no), len(no), dict(oc), len(ev), len(have)))
    blocks = []
    for i in no:
        if blocks and blocks[-1][1] == i - 1:
            blocks[-1][1] = i
        else:
            blocks.append([i, i])
    print("%s.2 no-outcome blocks (sent line ranges):" % tag, [(a, b, b - a + 1) for a, b in blocks])
    b1a, b1b = blocks[0]
    # 3. metrics
    falls = [r for i, r in enumerate(rows[1:], 1) if r["accepted"] < rows[i - 1]["accepted"]]
    first_new = falls[0]
    last_old = rows[rows.index(first_new) - 1]
    base = rows[0]
    print("%s.3 baseline line %d %s accepted %d rejected %d duplicate %d" % (tag, base["line"], base["ts_utc"], base["accepted"], base["rejected"], base["duplicate"]))
    print("   last old poll line %d %s accepted %d queue_depth %d dropped %d rejected %d duplicate %d" % (
        last_old["line"], last_old["ts_utc"], last_old["accepted"], last_old["queue_depth"], last_old["dropped"], last_old["rejected"], last_old["duplicate"]))
    print("   first new poll line %d %s accepted %d qd %d ; gap %.3f s ; falls %d" % (
        first_new["line"], first_new["ts_utc"], first_new["accepted"], first_new["queue_depth"], first_new["t"] - last_old["t"], len(falls)))
    print("   max dropped %d over %d samples ; final line %d %s qd %d" % (max(r["dropped"] for r in rows), len(rows), rows[-1]["line"], rows[-1]["ts_utc"], rows[-1]["queue_depth"]))
    print("   rejected/duplicate change during the old process: %d / %d" % (last_old["rejected"] - base["rejected"], last_old["duplicate"] - base["duplicate"]))
    # 4. accounting at the last old poll
    tp = last_old["t"]
    pub_by = sum(1 for s in sent if h2w(s["publish_monotonic_ns"]) <= tp)
    acc_d = last_old["accepted"] - base["accepted"]
    qd = last_old["queue_depth"]
    resid = pub_by - acc_d - qd
    acked_by = sum(1 for e in ev if c2w(e["ditto_ack_monotonic_ns"]) <= tp)
    ahead = b1a - 1
    ahead_ok = all(sent[i]["message_id"] in have for i in range(ahead))
    after_poll = ahead - acc_d
    print("%s.4 published by poll %d ; accepted delta %d [event acks by poll, cross-clock %d] ; qd %d ; residual %d" % (tag, pub_by, acc_d, acked_by, qd, resid))
    print("   identities with outcome ahead of block %d (all of sent 1..%d have one: %s) ; acks after poll %d ; still queued >= %d ; +residual %d" % (
        ahead, ahead, ahead_ok, after_poll, qd - after_poll, qd - after_poll + resid))
    g1 = sum(1 for i in range(b1a, b1b + 1) if h2w(sent[i - 1]["publish_monotonic_ns"]) <= tp)
    print("   block members published by poll %d ; ahead + members = %d vs published by poll %d" % (g1, ahead + g1, pub_by))
    # sensitivity: the last old poll's accepted vs the 'ahead' count is the same-domain difference; the cross-clock one:
    for sh in (-0.5, -0.1, 0.1, 0.5):
        print("   cross-clock acks by poll with anchor %+.1f s: %d" % (sh, sum(1 for e in ev if c2w(e["ditto_ack_monotonic_ns"]) + sh <= tp)))
    # 5. last old ack, first new delivery
    ev_sorted = ev  # file order
    last_old_ev = ev_sorted[ahead - 1]
    first_new_ev = ev_sorted[ahead]
    lo_w = c2w(last_old_ev["ditto_ack_monotonic_ns"])
    fn_w = c2w(first_new_ev["received_monotonic_ns"])
    print("%s.5 last old line %d %s seq %d ack %s ; first block identity sent line %d %s seq %d" % (
        tag, ahead, last_old_ev["device_type"], last_old_ev["seq"], iso(lo_w), b1a, sent[b1a - 1]["device_type"], sent[b1a - 1]["seq"]))
    print("   first new line %d %s seq %d received %s ; = sent line %d? %s" % (
        ahead + 1, first_new_ev["device_type"], first_new_ev["seq"], iso(fn_w), b1b + 1,
        sent[b1b]["message_id"] == first_new_ev["message_id"]))
    print("   last old ack - restart command %.3f s ; - last answered poll %.3f s" % (lo_w - ts(rs["started_utc"]), lo_w - tp))
    later = ev_sorted[ahead:]
    print("   lines after the gap %d ; all received after restart finished: %s ; min received - restart finished %.3f s" % (
        len(later), all(c2w(e["received_monotonic_ns"]) > ts(rs["finished_utc"]) for e in later),
        min(c2w(e["received_monotonic_ns"]) for e in later) - ts(rs["finished_utc"])))
    later_ids = {e["message_id"] for e in later}
    idx_later = [i for i, s in enumerate(sent, 1) if s["message_id"] in later_ids]
    print("   sent lines of those identities: %d..%d (all after block 1: %s)" % (min(idx_later), max(idx_later), min(idx_later) > b1b))
    print("   ack order equals file order: %s ; received order equals file order: %s" % (
        all(ev[i]["ditto_ack_monotonic_ns"] < ev[i + 1]["ditto_ack_monotonic_ns"] for i in range(len(ev) - 1)),
        all(ev[i]["received_monotonic_ns"] < ev[i + 1]["received_monotonic_ns"] for i in range(len(ev) - 1))))
    # 6. collector around the restart
    cc = [r for r in col if r["c"] == "egw-controller-1"]
    # the first row of the new container: the first controller row after the restart command whose memory
    # fell below half of the previous row's (the process was replaced)
    gaps = [(a, b) for a, b in zip(cc, cc[1:]) if b["t"] > ts(rs["started_utc"]) - 5 and b["mem"] < 0.5 * a["mem"]][:1]
    inst = sorted({r["t"] for r in col})
    cad = (len(inst) - 1) / (inst[-1] - inst[0])
    cc_rate = (len(cc) - 1) / (cc[-1]["t"] - cc[0]["t"])
    for a, b in gaps:
        print("%s.6 controller collector gap %s -> %s = %.1f s ; mem %d -> %d" % (tag, a["ts_utc"], b["ts_utc"], b["t"] - a["t"], a["mem"], b["mem"]))
    print("   cadence: instants %.4f /s ; controller rows %.4f /s ; max gap in file (any container) %.1f s" % (
        cad, cc_rate, max(b - a for a, b in zip(inst, inst[1:]))))
    bracket = [b for a, b in gaps][0]["t"]
    # 7. partition of block 1 by publication instant
    guest_minus_host = ts(mk["wall_utc"]) - ts(mk["polled_utc"])
    print("   marker: controller wall_utc - harness polled_utc = %+.3f s (guest wall offset through the marker)" % guest_minus_host)
    for label, lo_cut, br_cut in (("harness wall for the last ack; bracket guest row as is", lo_w, bracket),
                                  ("last ack through the controller's wall_utc (as the ADR's instants suggest)", lo_w + guest_minus_host, bracket),
                                  ("bracket row converted guest->harness wall", lo_w, bracket - guest_minus_host)):
        g = Counter()
        for i in range(b1a, b1b + 1):
            t = h2w(sent[i - 1]["publish_monotonic_ns"])
            if t <= tp:
                g["G1"] += 1
            elif t <= lo_cut:
                g["G2"] += 1
            elif t <= br_cut:
                g["G3a"] += 1
            else:
                g["G3b"] += 1
        print("%s.7 [%s] G1 %d G2 %d G3a %d G3b %d total %d" % (tag, label, g["G1"], g["G2"], g["G3a"], g["G3b"], sum(g.values())))
        lo_recv = qd - after_poll
        print("      bounds received-left: [%d, %d] ; published-while-unsubscribed: [%d, %d]" % (
            lo_recv, g["G1"] + g["G2"] + g["G3a"], g["G3b"], g["G3b"] + g["G3a"] + g["G2"] + resid))
    print("   acks between last answered poll and last old ack: %d in %.3f s = %.3f msg/s" % (
        after_poll, lo_w - tp, after_poll / (lo_w - tp)))
    # outage lengths
    print("%s.8 bracket -> first delivery %.3f s ; poll gap %.3f s ; restart cmd -> first delivery %.3f s" % (
        tag, fn_w - bracket, first_new["t"] - tp, fn_w - ts(rs["started_utc"])))
    for L in (fn_w - bracket, first_new["t"] - tp, fn_w - ts(rs["started_utc"])):
        print("   x 11.2 = %.1f" % (L * 11.2))
    # 9. post-drain second fetch
    print("%s.9 files in run dir:" % tag, sorted(p.name for p in path.iterdir()))
    # 10. queue at t+150 / t+300
    for s in (150, 300):
        r = [r for r in rows if r["t"] <= w0 + s][-1]
        print("%s.10 last sample within t+%d: line %d %s qd %d" % (tag, s, r["line"], r["ts_utc"], r["queue_depth"]))
    # 11. null puback among identities with an outcome
    print("%s.11 identities with outcome and null puback: %d ; null puback overall %d" % (
        tag, sum(1 for s in sent if s["message_id"] in have and s.get("puback_monotonic_ns") is None),
        sum(1 for s in sent if s.get("puback_monotonic_ns") is None)))
    # served rate of the old process in this run (its own evidence, not nominal-r01)
    print("   old process served rate (counter, baseline -> last old poll): %.4f msg/s over %.1f s ; 1867-type drain at that rate %.0f s" % (
        acc_d / (tp - base["t"]), tp - base["t"], qd / (acc_d / (tp - base["t"]))))
    return m


run(R01, "R01")
run(R02, "R02")
