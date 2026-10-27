#!/usr/bin/env python3
"""Every figure quoted in adr-0011-controller-restart-recovery.md, re-derived.

Read-only. Reads the raw run directories and the nominal attempt's analysis
directory; writes nothing except to stdout. Run as:

  wsl -d Ubuntu-24.04 --exec bash -lc '~/egw-exec/venv/bin/python \
    <review-record>/scripts/adr0011_figures.py'

Every duration and rate here is from an ARM64 guest emulated under QEMU/TCG.
Nothing here is native-hardware performance, and no rate below is a capacity.
Block labels (R01, R02, N, P, S) are the ones the ADR cites.

Round three (2026-09-21): controller stamps compared with harness instants are
mapped through the marker's polled_utc (harness wall), not its wall_utc (guest
wall); the restart runs' outcomes are split into on time and late; each run's
own old-process rates are added (R0x.12); N.7 uses the event-log construction
of backlog_diagnosis.md section 3.1; P.2 and P.3 include the 60 s confirmation
wait, and P.3 is a planning ceiling, not a bound.
"""
from __future__ import annotations

import csv
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

RAW = Path("/home/ruisth/egw-tcg/pilot/results/raw")
ATT = Path("/home/ruisth/egw-exec/attempts/"
           "20260919T195827Z_nominal-instrumentation-120-600_attempt01")


def utc(s: str) -> datetime:
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


def iso(d: datetime) -> str:
    return d.astimezone(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def jsonl(p: Path) -> list[dict]:
    with p.open(encoding="utf-8") as fh:
        return [json.loads(line) for line in fh if line.strip()]


def metrics_rows(p: Path) -> list[dict]:
    with p.open(encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    for i, r in enumerate(rows):
        r["_line"] = i + 2  # header is line 1
        r["_ts"] = utc(r["ts_utc"])
        for k in ("accepted", "rejected", "duplicate", "failed", "dropped", "queue_depth"):
            r[k] = int(r[k])
    return rows


class Clocks:
    """Harness monotonic -> harness wall, and controller monotonic -> harness wall, per manifest.

    Round three: every controller stamp that is compared with a harness instant
    (a poll, the restart command, a publication, the fetch) is mapped through the
    marker's `polled_utc` (the harness wall at which the marker was read), never
    through its `wall_utc` (the controller's own, i.e. the guest's, wall clock).
    Guest-wall collector rows are mapped to harness wall with the marker offset
    wall_utc - polled_utc; that assumes the offset measured at the marker held at
    the restart, which no artefact records (CONSISTENT-WITH, never PROVED).
    """

    def __init__(self, m: dict):
        self.h0_ns = m["measured_started_monotonic_ns"]
        self.h0_utc = utc(m["measured_window_utc"]["start"])
        mk = m["controller_marker"]
        self.c_ns = mk["monotonic_ns"]
        self.c_guest = utc(mk["wall_utc"])     # controller's own (guest) wall at the marker
        self.c_harness = utc(mk["polled_utc"])  # harness wall at which the marker was polled
        self.offset_s = (self.c_guest - self.c_harness).total_seconds()  # guest - harness

    def pub(self, ns: int) -> datetime:
        return self.h0_utc + timedelta(microseconds=(ns - self.h0_ns) / 1000)

    def ctl(self, ns: int) -> datetime:
        """Controller monotonic -> harness wall (through polled_utc)."""
        return self.c_harness - timedelta(microseconds=(self.c_ns - ns) / 1000)

    def ctl_guest(self, ns: int) -> datetime:
        """Controller monotonic -> guest wall (through wall_utc); shown for contrast only."""
        return self.c_guest - timedelta(microseconds=(self.c_ns - ns) / 1000)

    def guest_to_harness(self, d: datetime) -> datetime:
        return d - timedelta(seconds=self.offset_s)


def blocks(flags: list[bool]) -> list[tuple[int, int]]:
    """Maximal runs of True, as 1-based inclusive line ranges."""
    out, start = [], None
    for i, f in enumerate(flags):
        if f and start is None:
            start = i
        if not f and start is not None:
            out.append((start + 1, i))
            start = None
    if start is not None:
        out.append((start + 1, len(flags)))
    return out


def restart_run(run_id: str) -> None:
    d = RAW / run_id
    m = json.loads((d / "manifest.json").read_text(encoding="utf-8"))
    ck = Clocks(m)
    sent = jsonl(d / "sent_events.jsonl")
    ev = jsonl(d / "events.jsonl")
    rows = metrics_rows(d / "controller_metrics.csv")
    tag = "R01" if run_id.endswith("r01") else "R02"
    print(f"\n=== {tag}: {run_id} (validity={m['validity']}, harness commit {m['commit'][:7]})")
    print(f"{tag}.0 rate_msg_s={m['rate_msg_s']} duration_s={m['duration_s']} "
          f"restart.requested_at_s={m['restart']['requested_at_s']} "
          f"restart.started_utc={m['restart']['started_utc']} returncode={m['restart']['returncode']}")
    print(f"{tag}.0 events fetch started_utc={m['events_fetch']['attempts'][0]['started_utc']} "
          f"(the instant at which 'with an outcome' below is evaluated)")
    rs0, rf0 = utc(m["restart"]["started_utc"]), utc(m["restart"]["finished_utc"])
    print(f"{tag}.0 restart command started {m['restart']['started_utc']} finished {m['restart']['finished_utc']}: "
          f"{(rf0 - rs0).total_seconds():.3f} s (harness wall)")
    print(f"{tag}.0 marker: controller wall_utc - harness polled_utc = {ck.offset_s:+.3f} s "
          f"(guest wall minus harness wall at the marker)")
    import re
    for w in m.get("warnings", []):
        if "REJECTED" in w and "sampling gap" in w:
            n_gaps = re.search(r"(\d+) sampling gap\(s\)", w).group(1)
            listed = re.findall(r"container '([^']+)': (\S+) to (\S+) \(([\d.]+) s\)", w)
            print(f"{tag}.0 resource file REJECTED by the ingest rule (manifest 'warnings'): {n_gaps} sampling gap(s) "
                  f"over the 5 s limit; the warning lists {len(listed)} of them"
                  f"{' and is truncated' if w.rstrip().endswith('...') else ''}:")
            for c, a, b, s in listed:
                print(f"{tag}.0   {c}: {a} -> {b} ({s} s)")

    valid = [s for s in sent if not s.get("intended_invalid")]
    by_id = {}
    for e in ev:
        by_id.setdefault(e["message_id"], []).append(e)
    hist = {}
    for e in ev:
        hist[e["outcome"]] = hist.get(e["outcome"], 0) + 1
    has = [s["message_id"] in by_id for s in sent]
    print(f"{tag}.1 published={len(sent)} valid={len(valid)} with_outcome_at_fetch={sum(has)} "
          f"no_outcome_at_fetch={len(sent) - sum(has)} outcome_histogram={hist} "
          f"event_lines={len(ev)}")
    # on time / late among those with an outcome: controller clock against controller clock
    dl = m["confirmation_deadline_monotonic_ns"]
    first_acc = {}
    for e in ev:
        if e["outcome"] == "accepted":
            first_acc.setdefault(e["message_id"], e["ditto_ack_monotonic_ns"])
    on = sum(1 for a in first_acc.values() if a <= dl)
    dl_h = ck.ctl(dl)
    fetch0 = utc(m["events_fetch"]["attempts"][0]["started_utc"])
    newest = max(e["ditto_ack_monotonic_ns"] for e in ev)
    print(f"{tag}.1 with an outcome at the fetch = confirmed by the deadline {on} + after it {len(first_acc) - on} "
          f"(ack stamp against confirmation_deadline_monotonic_ns, both controller clock)")
    print(f"{tag}.1 deadline mapped to harness wall {iso(dl_h)}; fetch started {(fetch0 - dl_h).total_seconds():.3f} s "
          f"after it; newest acknowledgement in the copy {(newest - dl) / 1e9:+.3f} s from the deadline")
    bl = blocks([not h for h in has])
    for a, b in bl:
        print(f"{tag}.2 no-outcome block sent_events.jsonl:{a}-{b} size={b - a + 1}")

    # restart in the counters: the only fall of the cumulative 'accepted'
    falls = [i for i in range(1, len(rows)) if rows[i]["accepted"] < rows[i - 1]["accepted"]]
    print(f"{tag}.3 falls of cumulative accepted: {len(falls)} at controller_metrics.csv lines "
          f"{[rows[i]['_line'] for i in falls]}")
    i = falls[0]
    last_old, first_new = rows[i - 1], rows[i]
    base = rows[0]
    print(f"{tag}.3 baseline line {base['_line']} {base['ts_utc']} accepted={base['accepted']}")
    print(f"{tag}.3 last old-process poll line {last_old['_line']} {last_old['ts_utc']} "
          f"accepted={last_old['accepted']} queue_depth={last_old['queue_depth']} "
          f"dropped={last_old['dropped']}")
    print(f"{tag}.3 first new-process poll line {first_new['_line']} {first_new['ts_utc']} "
          f"accepted={first_new['accepted']} queue_depth={first_new['queue_depth']}; "
          f"poll gap {(first_new['_ts'] - last_old['_ts']).total_seconds():.3f} s")
    print(f"{tag}.3 dropped at every sample: max={max(r['dropped'] for r in rows)} over {len(rows)} samples; "
          f"final poll line {rows[-1]['_line']} {rows[-1]['ts_utc']} queue_depth={rows[-1]['queue_depth']}")

    # the old process's ledger at its last poll
    first_block_start = bl[0][0] - 1  # 0-based index of the first internal no-outcome identity
    pre_gap = sum(has[:first_block_start])
    pub_by_poll = sum(1 for s in sent if ck.pub(s["publish_monotonic_ns"]) <= last_old["_ts"])
    acc_delta = last_old["accepted"] - base["accepted"]
    qd = last_old["queue_depth"]
    drained_after = pre_gap - acc_delta
    still = qd - drained_after
    residual = pub_by_poll - (acc_delta + qd)
    members_by_poll = sum(1 for k in range(first_block_start, bl[0][1])
                          if ck.pub(sent[k]["publish_monotonic_ns"]) <= last_old["_ts"])
    acked_by_poll = sum(1 for e in ev if e.get("ditto_ack_monotonic_ns") is not None
                        and ck.ctl(e["ditto_ack_monotonic_ns"]) <= last_old["_ts"])
    print(f"{tag}.4 published by the last old poll                 {pub_by_poll}")
    print(f"{tag}.4   accepted delta at that poll ({last_old['accepted']} - {base['accepted']})   {acc_delta}"
          f"   [events.jsonl records acked by then, cross-clock: {acked_by_poll}]")
    print(f"{tag}.4   queue_depth at that poll                     {qd}")
    print(f"{tag}.4   residual (published - accepted - queued)     {residual}")
    print(f"{tag}.4 identities with an outcome before the gap       {pre_gap}")
    print(f"{tag}.4   drained after the poll ({pre_gap} - {acc_delta})          {drained_after}")
    print(f"{tag}.4   still queued when the process stopped        {still}")
    print(f"{tag}.4   + residual                                   {still + residual}")
    print(f"{tag}.4 block members published by that poll          {members_by_poll}")
    print(f"{tag}.4 check pre_gap + members_by_poll = {pre_gap + members_by_poll} vs published by poll {pub_by_poll}")

    # the old process's last acknowledgement and the new process's first delivery
    old_ids = {s["message_id"] for s in sent[:first_block_start]}
    old_ev = [e for e in ev if e["message_id"] in old_ids]
    new_ev = [e for e in ev if e["message_id"] not in old_ids]
    last_ack = max(old_ev, key=lambda e: e["ditto_ack_monotonic_ns"])
    first_new_ev = min(new_ev, key=lambda e: e["received_monotonic_ns"])
    last_ack_utc = ck.ctl(last_ack["ditto_ack_monotonic_ns"])
    first_rx_utc = ck.ctl(first_new_ev["received_monotonic_ns"])
    la_line = ev.index(last_ack) + 1
    fr_line = ev.index(first_new_ev) + 1
    print(f"{tag}.5 last old-process ack events.jsonl:{la_line} {last_ack['device_type']} seq {last_ack['seq']} "
          f"at {iso(last_ack_utc)} harness wall ({iso(ck.ctl_guest(last_ack['ditto_ack_monotonic_ns']))} "
          f"on the controller's own wall clock)")
    print(f"{tag}.5 first identity of the first block sent_events.jsonl:{bl[0][0]} "
          f"{sent[first_block_start]['device_type']} seq {sent[first_block_start]['seq']}")
    print(f"{tag}.5 first new-process delivery events.jsonl:{fr_line} {first_new_ev['device_type']} "
          f"seq {first_new_ev['seq']} received at {iso(first_rx_utc)} harness wall")
    rs = utc(m["restart"]["started_utc"])
    print(f"{tag}.5 old process wrote outcomes until {(last_ack_utc - rs).total_seconds():.3f} s after the restart "
          f"command started (controller stamp mapped to harness wall through polled_utc: cross-clock)")
    print(f"{tag}.5 its last outcome is {(last_ack_utc - last_old['_ts']).total_seconds():.3f} s after its last "
          f"answered poll (same mapping)")
    after_block = sum(has[bl[0][1]:])
    print(f"{tag}.5 identities with an outcome after the first block (all published after the outage): "
          f"{after_block} = {sum(has)} - {pre_gap}")

    # the death bracket from the collector (guest wall clock, 1 s resolution)
    col = d / "logs" / "collector" / f"resources-{run_id}.csv"
    with col.open(encoding="utf-8") as fh:
        crow = [r for r in csv.DictReader(fh) if r["container"] == "egw-controller-1"]
    ts = [utc(r["ts_utc"]) for r in crow]
    near = [(k, (ts[k] - ts[k - 1]).total_seconds()) for k in range(1, len(ts))
            if abs((ts[k] - rs).total_seconds()) < 60]
    kmax, gap = max(near, key=lambda t: t[1])
    upper = ts[kmax]
    span = (ts[-1] - ts[0]).total_seconds()
    print(f"{tag}.6 collector: egw-controller-1 gap around the restart {iso(ts[kmax - 1])} -> {iso(upper)} "
          f"= {gap:.1f} s; mem_bytes {crow[kmax - 1]['mem_bytes']} -> {crow[kmax]['mem_bytes']}; "
          f"cadence {(len(ts) - 1) / span:.4f} samples/s over the file")

    # partition of the first block by publication instant. G1 is cut on the harness wall alone
    # (PROVED); G2/G3a on a controller stamp mapped through polled_utc, G3a/G3b on a guest-wall
    # collector row (both CONSISTENT-WITH). The row is shown mapped to harness wall and as recorded.
    mem = sent[first_block_start:bl[0][1]]
    pubs = [ck.pub(s["publish_monotonic_ns"]) for s in mem]
    upper_h = ck.guest_to_harness(upper)
    for label, cut in (("collector row mapped to harness wall", upper_h), ("collector row as recorded (guest wall)", upper)):
        g1 = sum(1 for p in pubs if p <= last_old["_ts"])
        g2 = sum(1 for p in pubs if last_old["_ts"] < p <= last_ack_utc)
        g3a = sum(1 for p in pubs if last_ack_utc < p <= cut)
        g3b = sum(1 for p in pubs if p > cut)
        print(f"{tag}.7 [{label}] first block partition: G1(<= last poll)={g1} G2(poll, last ack]={g2} "
              f"G3a(last ack, bracket upper]={g3a} G3b(> bracket upper)={g3b} total={g1 + g2 + g3a + g3b}")
        print(f"{tag}.7 [{label}] bounds: received-then-discarded in [{still}, {still + residual + g2 + g3a}]; "
              f"published-never-delivered in [{g3b}, {g3b + g3a + g2 + residual}]")
    print(f"{tag}.7 clock-free ends: received-left lower bound {still} (poll ledger); "
          f"published-never-delivered upper bound {bl[0][1] - bl[0][0] + 1} - {still} = {bl[0][1] - bl[0][0] + 1 - still}")
    r = m["rate_msg_s"]
    print(f"{tag}.7 at the offered {r} msg/s, one second of publication = {r:.1f} identities")
    o1 = (first_rx_utc - upper_h).total_seconds()
    o2 = (first_new["_ts"] - last_old["_ts"]).total_seconds()
    o3 = (first_rx_utc - rs).total_seconds()
    print(f"{tag}.8 subscription-outage lengths (harness wall): bracket upper -> first delivery {o1:.3f} s (lower bound); "
          f"poll gap {o2:.3f} s; restart command -> first delivery {o3:.3f} s (upper bound)")
    print(f"{tag}.8 published at {r} msg/s across those outages: {r * o1:.1f} / {r * o2:.1f} / {r * o3:.1f} messages "
          f"(time-based; the identity-based bounds are in {tag}.7)")

    # the unresolved end-of-run block: no post-drain fetch exists for this run
    print(f"{tag}.9 post-drain second fetch present: {any(p.name.startswith('events.post') for p in d.iterdir())}")

    # queue_depth half-way to the planned restart, for the proof-run planning
    w0 = utc(m["measured_window_utc"]["start"])
    for t in (150.0, 300.0):
        cand = [x for x in rows if (x["_ts"] - w0).total_seconds() <= t]
        x = cand[-1]
        print(f"{tag}.10 queue_depth at the last sample within t+{t:.0f} s: line {x['_line']} "
              f"{x['ts_utc']} queue_depth={x['queue_depth']}")

    # PUBACK capture is best-effort in the simulator
    nulls = sum(1 for s in sent if s["message_id"] in by_id and s.get("puback_monotonic_ns") is None)
    print(f"{tag}.11 identities with an outcome whose puback_monotonic_ns is null: {nulls}")

    # this run's own old-process rates (an illustration of drain time, not a capacity)
    span = (last_old["_ts"] - base["_ts"]).total_seconds()
    r_in = acc_delta / span
    after_poll_s = (last_ack_utc - last_old["_ts"]).total_seconds()
    r_after = drained_after / after_poll_s
    print(f"{tag}.12 old process, counter, baseline -> last answered poll (harness wall only): "
          f"{acc_delta} in {span:.3f} s = {r_in:.4f} msg/s; {qd} queued at that rate: {qd / r_in:.0f} s")
    print(f"{tag}.12 old process, outcome lines after the last answered poll: {drained_after} in {after_poll_s:.3f} s "
          f"(cross-clock) = {r_after:.4f} msg/s; {qd} queued at that rate: {qd / r_after:.0f} s")


def nominal() -> None:
    d = RAW / "nominal-r01"
    m = json.loads((d / "manifest.json").read_text(encoding="utf-8"))
    sent = jsonl(d / "sent_events.jsonl")
    ev_fetch = jsonl(d / "events.jsonl")
    ev_post = jsonl(ATT / "analysis" / "events.post-drain.jsonl")
    ev_warm = jsonl(ATT / "analysis" / "warmup.events.jsonl")
    cmds = jsonl(ATT / "commands.jsonl")
    dl = m["confirmation_deadline_monotonic_ns"]
    end = m["controller_monotonic_at_run_end_ns"]
    print(f"\n=== N: nominal-r01 (validity={m['validity']}, harness commit {m['commit'][:7]}, "
          f"rate {m['rate_msg_s']} msg/s, warm-up {m['warmup_s']} s, window {m['duration_s']} s)")
    print(f"N.0 deadline = controller end marker + {m['confirmation_window_s']} s: "
          f"{end} + 60e9 = {dl} (equal: {dl == end + 60_000_000_000})")
    valid = {s["message_id"] for s in sent if not s.get("intended_invalid")}

    def pops(ev: list[dict]) -> tuple[int, int, int]:
        acc = {}
        for e in ev:
            if e["outcome"] == "accepted" and e["message_id"] in valid:
                acc.setdefault(e["message_id"], e["ditto_ack_monotonic_ns"])
        on = sum(1 for a in acc.values() if a <= dl)
        late = len(acc) - on
        return on, late, len(valid) - len(acc)

    fetch_utc = m["events_fetch"]["attempts"][0]["started_utc"]
    post = next(c for c in cmds if c["name"] == "fetch-post-drain-events")
    drain = next(c for c in cmds if c["name"] == "post-drain")
    on, late, none = pops(ev_fetch)
    print(f"N.1 at the harness fetch (sealed raw events.jsonl, fetch started {fetch_utc}): "
          f"records={len(ev_fetch)} on_time={on} late={late} no_outcome={none}")
    on2, late2, none2 = pops(ev_post)
    print(f"N.2 after the drain (analysis/events.post-drain.jsonl, commands.jsonl seq {post['seq']} "
          f"started {post['started_utc']}): records={len(ev_post)} on_time={on2} late={late2} no_outcome={none2}")
    print(f"N.2 of the {none} without an outcome at the fetch, late after the drain: "
          f"{late2 - late}; lost after the drain: {none2}")
    print(f"N.2 drained helper: commands.jsonl seq {drain['seq']} {drain['started_utc']} -> {drain['ended_utc']} "
          f"({drain['duration_s']} s, exit {drain['exit_code']})")

    # inside the controller at the window end (controller clock), warm-up included
    inside = 0
    for e in ev_post + ev_warm:
        rx = e["received_monotonic_ns"]
        ack = e.get("ditto_ack_monotonic_ns")
        if rx <= end and (ack is None or ack > end):
            inside += 1
    last_ack = max(e["ditto_ack_monotonic_ns"] for e in ev_post)
    after = sum(1 for e in ev_post if e["ditto_ack_monotonic_ns"] > end)
    dur = (last_ack - end) / 1e9
    print(f"N.3 identities inside the controller at the window end: {inside}")
    print(f"N.3 last acknowledgement {dur:.3f} s after the window end; acknowledgements after the end: {after}")

    rows = metrics_rows(d / "controller_metrics.csv")
    pk = max(rows, key=lambda r: r["queue_depth"])
    print(f"N.4 controller_metrics.csv: samples={len(rows)} max queue_depth={pk['queue_depth']} "
          f"(line {pk['_line']} {pk['ts_utc']}) = {100 * pk['queue_depth'] / 10000:.2f} % of 10,000; "
          f"max dropped={max(r['dropped'] for r in rows)}")

    # phase rates of one failed run (counter deltas; drain from the event log)
    w0, w1 = utc(m["measured_window_utc"]["start"]), utc(m["measured_window_utc"]["end"])
    pre = [r for r in rows if r["_ts"] < w0]
    win = [r for r in rows if w0 <= r["_ts"] <= w1]
    r_warm = (pre[-1]["accepted"] - pre[0]["accepted"]) / (pre[-1]["_ts"] - pre[0]["_ts"]).total_seconds()
    r_win = (win[-1]["accepted"] - win[0]["accepted"]) / (win[-1]["_ts"] - win[0]["_ts"]).total_seconds()
    r_drain = after / dur
    print(f"N.5 served rates by phase (one failed run; not a capacity): warm-up {r_warm:.4f} msg/s "
          f"({len(pre)} samples), measured window {r_win:.4f} msg/s ({len(win)} samples, "
          f"delta accepted {win[-1]['accepted'] - win[0]['accepted']}), drain without ingress {r_drain:.4f} msg/s")
    print("S.1 algebra on a serial consumer: an added per-message cost x turns a served rate r into 1/(1/r + x).")
    for x_ms in (1, 10, 50):
        cells = []
        for name, r in (("warm-up", r_warm), ("window", r_win), ("drain", r_drain)):
            nr = 1 / (1 / r + x_ms / 1000)
            cells.append(f"{name} {r:.3f}->{nr:.3f} ({100 * (nr - r) / r:+.2f} %)")
        print(f"S.1 x = {x_ms:>2} ms: " + "; ".join(cells))
    for q, who in ((1867, "r02"), (1487, "r01")):
        print(f"S.2 {q} queued ({who}, last old-process poll) served at the phase rates above: "
              f"{q / r_drain:.0f} s (drain rate) to {q / r_warm:.0f} s (warm-up rate)")

    # device mix of the measured run
    mix = {}
    for s in sent:
        mix[s["device_type"]] = mix.get(s["device_type"], 0) + 1
    top = max(mix.values())
    print(f"N.6 device mix of the {len(sent)} measured identities: {mix}; "
          f"largest share {100 * top / len(sent):.1f} % on one device; distinct device_uuid "
          f"{len({s['device_uuid'] for s in sent})}")

    # 60 s blocks of the measured window: event-log acknowledgements (warm-up and measured) in
    # (el 60k, el 60(k+1)], controller clock -- the same construction as backlog_diagnosis.md
    # section 3.1 (scripts/s02_rates_and_queue.py, section D), so both documents quote one series.
    import bisect
    c_start = end - (m["finished_monotonic_ns"] - m["measured_started_monotonic_ns"])
    acks = sorted(e["ditto_ack_monotonic_ns"] for e in ev_warm + ev_post)
    rates = []
    for k in range(10):
        lo = c_start + 60 * k * 1_000_000_000
        hi = lo + 60 * 1_000_000_000
        rates.append((bisect.bisect_right(acks, hi) - bisect.bisect_right(acks, lo)) / 60)
    print("N.7 served rate per 60 s block of the measured window, event log (msg/s): "
          + ", ".join(f"{r:.4f}" for r in rates) + f"; slowest {min(rates):.4f}, fastest {max(rates):.4f}")

    # proof-run planning arithmetic (planning only, not a prediction)
    print(f"P.1 a 300 s publication at {m['rate_msg_s']} msg/s = {m['rate_msg_s'] * 300:.0f} messages "
          f"(the nominal run published {len(sent)} measured + its warm-up over 720 s)")
    cw = m["confirmation_window_s"]
    for quiet in (130, 490):
        tot = quiet + 300 + cw + dur + quiet
        print(f"P.2 planning: quiet window {quiet} s + 300 s publication + {cw} s confirmation wait + {dur:.1f} s "
              f"(the nominal drain, a larger backlog) + quiet window {quiet} s = {tot:.0f} s = {tot / 60:.1f} min of guest time")
    for lim in (900, 1500):
        tot = lim + 300 + cw + lim
        print(f"P.3 planning ceiling with DRAIN_LIMIT_S={lim}: {lim} + 300 + {cw} + {lim} = {tot} s = {tot / 60:.1f} min; "
              f"NOT a bound: excludes the /ready wait, the restart command's own duration (R01.0, R02.0), "
              f"each drained reading's curl time, the fetches and the snapshots")


if __name__ == "__main__":
    print("adr0011_figures.py - ARM64 guest emulated under QEMU/TCG; no figure is native performance")
    restart_run("controller_restart-r01")
    restart_run("controller_restart-r02")
    nominal()
