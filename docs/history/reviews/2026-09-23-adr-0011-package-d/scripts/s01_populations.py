#!/usr/bin/env python3
"""s01 - the three outcome populations of nominal-r01 and the instant at which
each was collected. READ-ONLY; writes only to standard output.

Populations (by identity, against the controller-clock deadline
= controller end marker + 60 s):
  in time  : accepted record with ditto_ack <= deadline
  late     : accepted record with ditto_ack  > deadline
  no outcome at a collection point : no record for the identity in that file
Collection points:
  (1) the sealed harness fetch   raw/nominal-r01/events.jsonl
  (2) the separate post-drain observation   analysis/events.post-drain.jsonl
"""

from __future__ import annotations

import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import ANA, NS, RAW, Run, header, mean, pct, raw_lines, utc  # noqa: E402

r = Run()
m = r.manifest

header("0. Platform and anchors (sut_environment.json, loadgen_environment.json, manifest.json)")
import json as _json  # noqa: E402
from common import RAW as _RAW  # noqa: E402
sut = _json.loads((_RAW / "sut_environment.json").read_text())
lg = _json.loads((_RAW / "loadgen_environment.json").read_text())
print(f"SUT: {sut['os_pretty_name']}; {sut['uname_a'].split()[2]}; nproc {sut['nproc']}; "
      f"mem_total_kb {sut['mem_total_kb']}; machine {sut['uname_a'].split()[-2]}")
print(f"load generator host: {lg['machine']}, cpu_count {lg['cpu_count']}, kernel {lg['kernel_release']}")
mk = m["controller_marker"]
print(f"end marker: monotonic_ns {mk['monotonic_ns']}, polled_utc {mk['polled_utc']}, lag_s {mk['lag_s']}")
print(f"measured duration (harness monotonic): {r.host_dur_ns / NS:.6f} s; window start (controller) "
      f"{r.ctrl_start} ns; validity {m['validity']}, deviations {m['deviations']}")

header("A. Deadline and identities")
print(f"controller end marker (ns)            : {r.ctrl_end}")
print(f"confirmation_deadline_monotonic_ns    : {r.deadline}")
print(f"deadline - end marker                 : {(r.deadline - r.ctrl_end) / NS:.9f} s "
      f"(confirmation_window_s = {m['confirmation_window_s']})")
valid = [e for e in r.sent if not e["intended_invalid"]]
ids = sorted({e["message_id"] for e in valid})  # sorted: output order independent of hash seed
dev_of = {e["message_id"]: e["device_type"] for e in valid}
print(f"published records / valid / unique ids: {len(r.sent)} / {len(valid)} / {len(ids)}")
per_uuid = Counter(e["device_uuid"] for e in valid)
top_uuid, top_n = per_uuid.most_common(1)[0]
print(f"distinct device_uuid: {len(per_uuid)}; largest single twin: {top_n} of {len(valid)} "
      f"= {top_n / len(valid) * 100:.4f} % ({dev_of[next(e['message_id'] for e in valid if e['device_uuid'] == top_uuid)]})")
print(f"publish records with a null puback_monotonic_ns: "
      f"{sum(1 for e in r.sent if e['puback_monotonic_ns'] is None)} (a simulator capture field; "
      f"not used to define any population below)")

header("B. The sealed fetch is a prefix of the post-drain file")
sl = raw_lines(RAW / "events.jsonl")
pl = raw_lines(ANA / "events.post-drain.jsonl")
same = sum(1 for a, b in zip(sl, pl) if a == b)
print(f"sealed lines {len(sl)}, post-drain lines {len(pl)}, "
      f"first {len(sl)} lines byte-identical: {same == len(sl)} ({same})")


def classify(records):
    seen = {}
    out = Counter()
    per_dev = {}
    outcomes = Counter(e["outcome"] for e in records)
    for e in records:
        seen.setdefault(e["message_id"], e)
    cls = {}
    for mid in ids:
        e = seen.get(mid)
        if e is None:
            c = "no_outcome"
        elif e["outcome"] == "accepted" and e["ditto_ack_monotonic_ns"] <= r.deadline:
            c = "in_time"
        elif e["outcome"] == "accepted":
            c = "late"
        else:
            c = "other:" + e["outcome"]
        cls[mid] = c
        out[c] += 1
        per_dev.setdefault(dev_of[mid], Counter())[c] += 1
    return cls, out, per_dev, outcomes, len(seen), len(records)


header("C. Population counts at each collection point")
cls_f, cnt_f, dev_f, oc_f, uniq_f, n_f = classify(r.sealed)
cls_p, cnt_p, dev_p, oc_p, uniq_p, n_p = classify(r.post)
print(f"(1) sealed harness fetch : records {n_f}, unique ids {uniq_f}, outcomes {dict(oc_f)}")
print(f"    in time {cnt_f['in_time']}, late {cnt_f['late']}, no outcome {cnt_f['no_outcome']}")
for d in sorted(dev_f):
    print(f"      {d:<15} {dict(dev_f[d])}")
print(f"(2) post-drain observation: records {n_p}, unique ids {uniq_p}, outcomes {dict(oc_p)}")
print(f"    in time {cnt_p['in_time']}, late {cnt_p['late']}, no outcome {cnt_p['no_outcome']}")
for d in sorted(dev_p):
    print(f"      {d:<15} {dict(dev_p[d])}")
hr = r.accounting["harness_row"]
print(f"accounting.json harness_row: delivered_unique {hr['delivered_unique']}, lost {hr['lost']}, "
      f"late_confirmations {hr['late_confirmations']}")
print(f"accounting.json at_harness_fetch {r.accounting['at_harness_fetch']}, "
      f"after_drain {r.accounting['after_drain']}")
trans = Counter((cls_f[mid], cls_p[mid]) for mid in ids)
print("transitions fetch -> post-drain:", dict(trans))
print(f"shares of 6,720: in time {cnt_p['in_time'] / len(ids) * 100:.2f} %, "
      f"not in time {(len(ids) - cnt_p['in_time']) / len(ids) * 100:.2f} %")

header("D. Collection instants")
ack_f = [e["ditto_ack_monotonic_ns"] for e in r.sealed if e["ditto_ack_monotonic_ns"]]
ack_p = [e["ditto_ack_monotonic_ns"] for e in r.post if e["ditto_ack_monotonic_ns"]]
ef = m["events_fetch"]["attempts"][0]
print(f"harness wall at the marker (polled_utc)      : {m['controller_marker']['polled_utc']}")
print(f"deadline mapped to harness wall              : {utc(r.ctrl_to_host_wall(r.deadline))}")
print(f"(1) sealed fetch: scp started (manifest)     : {ef['started_utc']}")
cmds = {c['seq']: c for c in r.commands()}
print(f"    harness-run command ended (commands.jsonl seq 4): {cmds[4]['ended_utc']}")
last_f = max(ack_f)
print(f"    latest ack in the sealed file            : deadline {(last_f - r.deadline) / NS:+.3f} s "
      f"-> harness wall {utc(r.ctrl_to_host_wall(last_f))}")
print(f"    scp start - deadline (harness wall)      : "
      f"{(__import__('common').iso(ef['started_utc']) - r.ctrl_to_host_wall(r.deadline)):.3f} s")
_iso = __import__("common").iso
print(f"    harness command end - deadline           : "
      f"{_iso(cmds[4]['ended_utc']) - r.ctrl_to_host_wall(r.deadline):.3f} s")
print(f"    post-drain scp start - sealed scp start  : "
      f"{_iso(cmds[6]['started_utc']) - _iso(ef['started_utc']):.3f} s")
late_f = sorted(e["ditto_ack_monotonic_ns"] for e in r.sealed
                if e["outcome"] == "accepted" and e["ditto_ack_monotonic_ns"] > r.deadline)
print(f"    the {len(late_f)} late at the fetch: acks from deadline "
      f"{(late_f[0] - r.deadline) / NS:+.3f} s to {(late_f[-1] - r.deadline) / NS:+.3f} s")
print(f"(2) post-drain: 'drained' (seq 5) {cmds[5]['started_utc']} -> {cmds[5]['ended_utc']}")
from common import ATT  # noqa: E402
for f in ("003-pre", "005-post-drain"):
    first = (ATT / "console" / f"{f}.stdout.txt").read_text().splitlines()[0]
    print(f"    console/{f}.stdout.txt: {first}")
print(f"    fetch scp (seq 6) {cmds[6]['started_utc']} -> {cmds[6]['ended_utc']}")
last_p = max(ack_p)
print(f"    latest ack in the post-drain file        : deadline {(last_p - r.deadline) / NS:+.3f} s "
      f"-> harness wall {utc(r.ctrl_to_host_wall(last_p))}")
snap = r.snapshot("after")
print(f"    /metrics after snapshot {snap['wall_utc']}: accepted {snap['accepted']}, received "
      f"{snap['received']}, queue_depth {snap['queue_depth']}, in_progress {snap['in_progress']}, "
      f"dropped {snap['dropped']}, processing_errors {snap['processing_errors']}")
print(f"    snapshot monotonic - latest ack          : {(snap['monotonic_ns'] - last_p) / NS:.3f} s")
before = r.snapshot("before")
print(f"    before snapshot accepted {before['accepted']}; 60 + 1,344 + 6,720 = {60 + 1344 + 6720}")
nf = [mid for mid in ids if cls_f[mid] == "no_outcome"]
pa = {e["message_id"]: e for e in r.post}
acks_nf = sorted(pa[mid]["ditto_ack_monotonic_ns"] for mid in nf)
print(f"    the {len(nf)} with no outcome at the fetch: eventual acks from deadline "
      f"{(acks_nf[0] - r.deadline) / NS:+.3f} s to {(acks_nf[-1] - r.deadline) / NS:+.3f} s")
rec_after = sum(1 for e in r.post if e["received_monotonic_ns"] > r.deadline)
inside = sum(1 for e in r.post if e["received_monotonic_ns"] <= r.deadline
             and e["ditto_ack_monotonic_ns"] > r.deadline)
print(f"    measured identities received after the deadline: {rec_after}")
print(f"    received <= deadline and acked after it  : {inside} "
      f"(the same predicate as 'late' once every identity has arrived: not an independent figure)")

header("E. Latency (s) per population - each tied to its collection point")


def lat(vals, label):
    v = [x / 1000.0 for x in vals]
    print(f"{label:<58} n={len(v):>5}  mean {mean(v):8.3f}  p50 {pct(v, 50):8.3f}  "
          f"p95 {pct(v, 95):8.3f}  p99 {pct(v, 99):8.3f}  max {max(v):8.3f}")


lat([e["latency_ms"] for e in r.sealed if cls_f[e["message_id"]] == "in_time"],
    "(1) in time, sealed fetch  [harness row population]")
lat([e["latency_ms"] for e in r.sealed if cls_f[e["message_id"]] == "late"],
    "(1) late at the sealed fetch")
lat([e["latency_ms"] for e in r.sealed], "(1) every record in the sealed fetch")
lat([e["latency_ms"] for e in r.post if cls_p[e["message_id"]] == "late"],
    "(2) late, post-drain")
lat([e["latency_ms"] for e in r.post], "(2) every record, post-drain")
print(f"harness_row: p50 {hr['latency_ms_p50'] / 1000:.6f}  p95 {hr['latency_ms_p95'] / 1000:.6f}  "
      f"max {hr['latency_ms_max'] / 1000:.6f} s")
inr = sorted(e["latency_ms"] for e in r.sealed if cls_f[e["message_id"]] == "in_time")
print(f"reproduced to the microsecond: p50 {abs(pct(inr, 50) - hr['latency_ms_p50']) < 1e-3}, "
      f"p95 {abs(pct(inr, 95) - hr['latency_ms_p95']) < 1e-3}, max {abs(inr[-1] - hr['latency_ms_max']) < 1e-3}")
