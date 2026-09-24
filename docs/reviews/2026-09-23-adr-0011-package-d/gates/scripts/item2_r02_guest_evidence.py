#!/usr/bin/env python3
"""Package D, gate item 2: what r02's guest-side evidence says about the restart.

Read-only. Inputs:
  - the raw run directories (manifest, sent_events.jsonl, the harness copy of
    events.jsonl, controller_metrics.csv) under /home/ruisth/egw-tcg/pilot/results/raw;
  - the files copied read-only out of the guest's rootfs image by
    item2_extract_guest.sh (the guest's own copy of each restart run's
    events.jsonl and the persistent journal of the guest boot in which r02 ran);
  - the docker json-file log lines found in the guest's data-disk image by
    item2_carve_data_disk.sh (residual bytes of deleted container logs).
Writes nothing except to stdout. Run as:

  wsl -d Ubuntu-24.04 --exec bash -lc '~/egw-exec/venv/bin/python \
      <review-record>/gates/scripts/item2_r02_guest_evidence.py'

Every instant is from an ARM64 guest emulated under QEMU/TCG or from the
harness host. Nothing here is a capacity or a native-hardware figure.
Block labels (E, J, B, P, X) are the ones the gate note cites.
"""
from __future__ import annotations

import csv
import hashlib
import json
import re
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path

RAW = Path("/home/ruisth/egw-tcg/pilot/results/raw")
HERE = Path(__file__).resolve().parent
EXT = HERE.parent / "item2_extract"
GUEST_EV = {
    "controller_restart-r02": EXT / "opt__egw__deployment__data__events__controller_restart-r02__events.jsonl",
    "controller_restart-r01": EXT / "opt__egw__deployment__data__events__controller_restart-r01__events.jsonl",
}
JOURNALS = [
    EXT / "var__log__journal__164be2431eb24037a415dd1641011fa6__system@1ce5b55b1e384e95abac528e90f476a9-0000000000002a76-00065bcaad8a43ea.journal",
    EXT / "var__log__journal__164be2431eb24037a415dd1641011fa6__user-1000@1ce5b55b1e384e95abac528e90f476a9-0000000000002a75-00065bcaad86cf14.journal",
]
CARVE = EXT / "data_disk_jsonlog_2026-09-19T00.txt"
CONTROLLER_CONTAINER = "9b2098915ade19660d43960189390249db7cc9ef7516650551afa1b0eb5f9e91"
CLIENT_ID = "egw-controller-egw-01"


def utc(s: str) -> datetime:
    s = s.replace("Z", "+00:00")
    m = re.match(r"^(.*\.\d{6})\d*(\+00:00)$", s)  # trim nanoseconds to microseconds
    if m:
        s = m.group(1) + m.group(2)
    return datetime.fromisoformat(s)


def iso(d: datetime) -> str:
    return d.astimezone(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def jsonl(p: Path) -> list[dict]:
    with p.open(encoding="utf-8") as fh:
        return [json.loads(line) for line in fh if line.strip()]


def sha256(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


class Clocks:
    """Same mappings as pkgD/v2/scripts/adr0011_figures.py (round three)."""

    def __init__(self, m: dict):
        self.h0_ns = m["measured_started_monotonic_ns"]
        self.h0_utc = utc(m["measured_window_utc"]["start"])
        mk = m["controller_marker"]
        self.c_ns = mk["monotonic_ns"]
        self.c_guest = utc(mk["wall_utc"])
        self.c_harness = utc(mk["polled_utc"])
        self.offset_s = (self.c_guest - self.c_harness).total_seconds()  # guest - harness

    def pub(self, ns: int) -> datetime:
        return self.h0_utc + timedelta(microseconds=(ns - self.h0_ns) / 1000)

    def ctl(self, ns: int) -> datetime:
        return self.c_harness - timedelta(microseconds=(self.c_ns - ns) / 1000)

    def ctl_guest(self, ns: int) -> datetime:
        return self.c_guest - timedelta(microseconds=(self.c_ns - ns) / 1000)

    def guest_to_harness(self, d: datetime) -> datetime:
        return d - timedelta(seconds=self.offset_s)


def blocks(flags: list[bool]) -> list[tuple[int, int]]:
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


def event_logs(run_id: str, tag: str) -> dict:
    d = RAW / run_id
    m = json.loads((d / "manifest.json").read_text(encoding="utf-8"))
    ck = Clocks(m)
    sent = jsonl(d / "sent_events.jsonl")
    fetched_b = (d / "events.jsonl").read_bytes()
    guest_b = GUEST_EV[run_id].read_bytes()
    print(f"\n=== {tag}: {run_id}")
    print(f"{tag}.E0 harness copy: {len(fetched_b)} bytes sha256 {sha256(fetched_b)}")
    print(f"{tag}.E0 guest copy:   {len(guest_b)} bytes sha256 {sha256(guest_b)}")
    pre = guest_b[:len(fetched_b)]
    print(f"{tag}.E0 first {len(fetched_b)} bytes of the guest copy sha256 {sha256(pre)} -> "
          f"{'IDENTICAL to the harness copy' if pre == fetched_b else 'DIFFERENT from the harness copy'}")
    fetched = [json.loads(x) for x in fetched_b.decode().splitlines() if x.strip()]
    guest = [json.loads(x) for x in guest_b.decode().splitlines() if x.strip()]
    extra = guest[len(fetched):]
    hist_e = {}
    for e in extra:
        hist_e[e["outcome"]] = hist_e.get(e["outcome"], 0) + 1
    hist_g = {}
    for e in guest:
        hist_g[e["outcome"]] = hist_g.get(e["outcome"], 0) + 1
    print(f"{tag}.E1 lines: harness copy {len(fetched)}, guest copy {len(guest)}, written after the harness copy "
          f"{len(extra)}; outcomes in those {hist_e}; outcomes in the whole guest copy {hist_g}")
    runs = {e["run_id"] for e in guest}
    print(f"{tag}.E1 run_id values in the guest copy: {sorted(runs)}")

    has_f = {e["message_id"] for e in fetched}
    has_g = {e["message_id"] for e in guest}
    acc = {}
    for e in guest:
        if e["outcome"] == "accepted":
            acc[e["message_id"]] = acc.get(e["message_id"], 0) + 1
    dbl = sum(1 for v in acc.values() if v > 1)
    print(f"{tag}.E2 identities with an outcome: harness copy {len(has_f)}, guest copy {len(has_g)}; "
          f"identities with two or more 'accepted' lines in the guest copy: {dbl}")
    sent_ids = [s["message_id"] for s in sent]
    not_sent = has_g - set(sent_ids)
    print(f"{tag}.E2 guest-copy identities absent from sent_events.jsonl: {len(not_sent)}")
    bl_f = blocks([s not in has_f for s in sent_ids])
    bl_g = blocks([s not in has_g for s in sent_ids])
    print(f"{tag}.E3 no-outcome blocks, harness copy: {[(a, b, b - a + 1) for a, b in bl_f]}")
    print(f"{tag}.E3 no-outcome blocks, guest copy:   {[(a, b, b - a + 1) for a, b in bl_g]}")
    for a, b in bl_f:
        members = sent_ids[a - 1:b]
        got = sum(1 for x in members if x in has_g)
        print(f"{tag}.E3 harness-copy block sent_events.jsonl:{a}-{b} ({b - a + 1}): "
              f"{got} have an outcome in the guest copy, {b - a + 1 - got} have none")
    # where the extra lines sit in sent order
    pos = {x: i + 1 for i, x in enumerate(sent_ids)}
    ex_lines = sorted(pos[e["message_id"]] for e in extra if e["message_id"] in pos)
    if ex_lines:
        print(f"{tag}.E4 the {len(extra)} later lines cover sent_events.jsonl:{ex_lines[0]}-{ex_lines[-1]} "
              f"(distinct identities {len(set(ex_lines))})")
    dl = m["confirmation_deadline_monotonic_ns"]
    late_extra = sum(1 for e in extra if e["ditto_ack_monotonic_ns"] > dl)
    print(f"{tag}.E4 later lines acknowledged after confirmation_deadline_monotonic_ns: {late_extra} of {len(extra)}")
    if extra:
        last = max(guest, key=lambda e: e["ditto_ack_monotonic_ns"])
        print(f"{tag}.E4 newest acknowledgement in the guest copy: {iso(ck.ctl(last['ditto_ack_monotonic_ns']))} "
              f"harness wall ({iso(ck.ctl_guest(last['ditto_ack_monotonic_ns']))} controller wall), "
              f"{(last['ditto_ack_monotonic_ns'] - dl) / 1e9:.3f} s after the deadline")
        fetch0 = utc(m["events_fetch"]["attempts"][0]["started_utc"])
        first_extra = min(extra, key=lambda e: e["ditto_ack_monotonic_ns"])
        print(f"{tag}.E4 oldest acknowledgement among the later lines: "
              f"{iso(ck.ctl(first_extra['ditto_ack_monotonic_ns']))} harness wall; harness fetch started "
              f"{iso(fetch0)}")
    # per device: accepted lines in the whole guest copy and the highest seq accepted (what a later
    # read of each twin's ingestion feature would be compared with)
    per = {}
    for e in guest:
        if e["outcome"] == "accepted":
            d_ = per.setdefault((e["device_type"], e["device_uuid"]), [0, -1])
            d_[0] += 1
            d_[1] = max(d_[1], e["seq"])
    for (dt, du), (n, mx) in sorted(per.items()):
        print(f"{tag}.E5 {dt} {du}: accepted lines {n}, highest seq accepted {mx}")
    return {"m": m, "ck": ck, "sent": sent, "fetched": fetched, "guest": guest, "bl_f": bl_f, "has_g": has_g}


def journal() -> dict:
    cmd = ["journalctl", "--utc", "-o", "short-iso-precise", "--no-pager",
           "--since", "2026-09-19 00:03:00 UTC", "--until", "2026-09-19 00:30:00 UTC"]
    for j in JOURNALS:
        cmd += ["--file", str(j)]
    out = subprocess.run(cmd, capture_output=True, text=True, check=True).stdout.splitlines()
    keep = re.compile(r"(9b2098915ade|port 6\(|connect_to 127\.0\.0\.1 port 8000|failed to exit)")
    print("\n=== J: guest journal, boot f99873bd9ff940259ae1135c277d9d86 (lines naming the controller "
          "container, its bridge port or the forwarded port 8000), 00:18:00Z-00:19:00Z")
    res = {}
    for line in out:
        if not ("2026-09-19T00:18:" in line[:30]) or not keep.search(line):
            continue
        print("J1 " + line[:420])
        m = re.search(r'time="([^"]+)" level=info msg="Container failed to exit within (\d+)s of signal (\d+) - using the force"', line)
        if m:
            res["force"] = utc(m.group(1))
            res["timeout_s"] = int(m.group(2))
            res["signal"] = int(m.group(3))
        m = re.search(r'exitStatus="\{(\d+) (\S+ \S+) \+0000 UTC\}"', line)
        if m:
            res["exit_code"] = int(m.group(1))
            res["exit_at"] = utc(m.group(2).replace(" ", "T") + "Z")
        m = re.search(r"execDuration=(\S+)", line)
        if m:
            res["exec"] = m.group(1)
        if "Started libcontainer container " + CONTROLLER_CONTAINER in line:
            res["started"] = utc(line[:32])
    stops = [l for l in out if "9b2098915ade" in l and "2026-09-19T00:" in l[:20]]
    print(f"J2 journal lines naming the controller container between 00:03Z and 00:30Z: {len(stops)}")
    for l in stops:
        if "failed to exit" in l or "ShouldRestart" in l or "Started libcontainer" in l or "scope: Deactivated" in l:
            print("J2 " + l[:300])
    return res


def broker() -> dict:
    """Docker json-file lines found in the data-disk image (residual bytes, not preserved files)."""
    print("\n=== B: broker log lines for client egw-controller-egw-01 found in the data-disk image "
          "(offset: json line)")
    res = {"lines": []}
    if not CARVE.exists():
        print("B0 carve output absent")
        return res
    seen = {}
    for raw in CARVE.read_text(encoding="utf-8", errors="replace").splitlines():
        if raw.startswith("#") or ":" not in raw:
            continue
        off, js = raw.split(":", 1)
        try:
            j = json.loads(js)
        except json.JSONDecodeError:
            continue
        seen.setdefault((j["time"], j["log"]), []).append(int(off))
    broker_like = {k: v for k, v in seen.items() if re.match(r"^2026-09-19T\d\d:\d\d:\d\d: ", k[1])}
    print(f"B0 distinct json lines stamped 2026-09-19T00 in the image: {len(seen)}; of them in the "
          f"broker's text format: {len(broker_like)}")
    for (t, log), offs in sorted(broker_like.items()):
        if CLIENT_ID in log or re.search(r"(?i)drop|queue|outgoing", log):
            print(f"B1 {t} | {log.rstrip()} | offsets {offs}")
            res["lines"].append((utc(t), log.rstrip()))
    for (t, log), offs in sorted(broker_like.items()):
        if "egw-simulator-controller_restart-r02" in log:
            print(f"B1 {t} | {log.rstrip()} | offsets {offs}")
    # continuity of the recovered broker lines over the run: the healthcheck probes every 30 s
    # (mosquitto.conf:42-45) and the store is saved every 60 s (autosave_interval), so a longer
    # silence would mean lines missing from what was recovered
    ts = sorted(utc(t) for (t, log) in broker_like if "2026-09-19T00:03:30" <= t <= "2026-09-19T00:29:00")
    gaps = [(ts[k - 1], ts[k]) for k in range(1, len(ts)) if (ts[k] - ts[k - 1]).total_seconds() > 35]
    offs_all = sorted(o for (t, log), v in broker_like.items() for o in v)
    print(f"B3 broker-format lines 00:03:30-00:29Z: {len(ts)}, first {iso(ts[0])}, last {iso(ts[-1])}; "
          f"silences over 35 s: {[(iso(a), iso(b)) for a, b in gaps]}; byte offsets span "
          f"{offs_all[0]}-{offs_all[-1]}")
    between = [(t, log) for (t, log) in broker_like if "2026-09-19T00:18:" in t or "2026-09-19T00:19:" in t]
    print(f"B2 broker-format lines stamped 00:18-00:19Z in the image: {len(between)}")
    for t, log in sorted(between):
        print(f"B2 {t} | {log.rstrip()[:200]}")
    return res


def carved_lines() -> dict:
    seen = {}
    if not CARVE.exists():
        return seen
    for raw in CARVE.read_text(encoding="utf-8", errors="replace").splitlines():
        if raw.startswith("#") or ":" not in raw:
            continue
        off, js = raw.split(":", 1)
        try:
            j = json.loads(js)
        except json.JSONDecodeError:
            continue
        seen.setdefault((j["time"], j["log"]), []).append(int(off))
    return seen


def controller_log(r: dict) -> dict:
    """The controller container's own json-file lines found in the data-disk image, checked line by
    line against the preserved event log: every outcome line of the old process's last minutes
    should have one Ditto PATCH log line for the same thing just before its acknowledgement stamp."""
    ck, guest, sent = r["ck"], r["guest"], r["sent"]
    seen = carved_lines()
    ctl = []
    for (t, log), offs in seen.items():
        s = log.strip()
        if s.startswith("INFO:     ") or '"logger": "egw_controller' in s or '"logger": "httpx"' in s:
            ts = None
            if s.startswith("{"):
                try:
                    ts = utc(json.loads(s)["ts"])
                except (json.JSONDecodeError, KeyError):
                    ts = None
            ctl.append((utc(t), ts, s, min(offs)))
    ctl.sort()
    print("\n=== C: controller container log lines found in the data-disk image (engine time | line)")
    lo, hi = utc("2026-09-19T00:18:19.000Z"), utc("2026-09-19T00:18:49.000Z")
    for t, ts, s, off in ctl:
        if lo <= t <= hi and "HTTP Request: PATCH" not in s and "GET /metrics" not in s:
            print(f"C1 {iso(t)} | {s[:220]} | offset {off}")
    patches = [(t, ts, s) for t, ts, s, off in ctl if "HTTP Request: PATCH http://ditto-gateway" in s]
    ok = [p for p in patches if "204 No Content" in p[2]]
    print(f"C2 PATCH lines stamped 2026-09-19T00: {len(patches)} (with 204: {len(ok)})")
    # match the old process's outcome lines acknowledged from 00:17:00Z (controller wall) to its death
    first_block = r["bl_f"][0][0]
    old_ids = {s["message_id"] for s in sent[:first_block - 1]}
    old = [e for e in guest if e["message_id"] in old_ids]
    w0, w1 = utc("2026-09-19T00:17:00.000Z"), utc("2026-09-19T00:18:31.000Z")
    sel = [e for e in old if w0 <= ck.ctl_guest(e["ditto_ack_monotonic_ns"]) <= w1]
    pt = [(ts, s) for t, ts, s in ok if ts is not None and w0 - timedelta(seconds=5) <= ts <= w1]
    inner = {k for k, (ts, s) in enumerate(pt) if w0 + timedelta(seconds=0.5) <= ts <= w1}
    used, matched, worst = set(), 0, 0.0
    for e in sel:
        a = ck.ctl_guest(e["ditto_ack_monotonic_ns"])
        cands = [(abs((a - ts).total_seconds()), k) for k, (ts, s) in enumerate(pt)
                 if k not in used and e["device_uuid"] in s and -0.5 <= (a - ts).total_seconds() <= 0.5]
        if cands:
            d, k = min(cands)
            used.add(k)
            matched += 1
            worst = max(worst, d)
    print(f"C3 old-process outcome lines acknowledged 00:17:00Z-death (controller wall): {len(sel)}; each matched "
          f"to a distinct PATCH 204 line for the same thing within 0.5 s: {matched}; largest gap {worst * 1000:.1f} ms; "
          f"PATCH 204 lines stamped 00:17:00.5Z-00:18:31Z left unmatched: {len(inner - used)}")
    last_ack = max(ck.ctl_guest(e["ditto_ack_monotonic_ns"]) for e in old)
    after = [(ts, s) for ts, s in pt if ts > last_ack]
    print(f"C4 old process's last acknowledgement stamp {iso(last_ack)} (controller wall); PATCH 204 lines "
          f"logged after it by the old process: {len(after)}")
    post =[e for e in old if ck.ctl(e["ditto_ack_monotonic_ns"]) > utc("2026-09-19T00:18:19.443Z")]
    pt_post = [(ts, s) for ts, s in pt if ck.guest_to_harness(ts) > utc("2026-09-19T00:18:19.443Z")]
    print(f"C5 after the last answered poll (00:18:19.443Z harness): outcome lines {len(post)}, PATCH 204 lines "
          f"{len(pt_post)}")
    inst = {}
    for t, ts, s, off in ctl:
        if not (lo <= t <= hi):
            continue
        if s.startswith("INFO:     Shutting down"):
            inst["shutting_down"] = t
        if '"MQTT disconnected"' in s:
            inst["mqtt_disconnected"] = ts
        if '"MQTT connected; subscription requested"' in s:
            inst["sub_requested"] = ts
        if '"MQTT subscription granted; bridge ready"' in s:
            inst["sub_granted"] = ts
    after_sd = [ts for ts, s in pt if "shutting_down" in inst and ts > inst["shutting_down"]]
    shown = ", ".join(f"{k}: {iso(v)}" for k, v in inst.items())
    print(f"C6 controller instants (guest wall): {shown}; PATCH 204 lines after 'Shutting down': {len(after_sd)}")
    return inst


def partition(r: dict, j: dict, b: dict, c: dict) -> None:
    m, ck, sent, bl = r["m"], r["ck"], r["sent"], r["bl_f"]
    rows = list(csv.DictReader((RAW / "controller_restart-r02" / "controller_metrics.csv").open(encoding="utf-8")))
    acc = [int(x["accepted"]) for x in rows]
    fall = next(i for i in range(1, len(rows)) if acc[i] < acc[i - 1])
    last_poll = utc(rows[fall - 1]["ts_utc"])
    first_new_poll = utc(rows[fall]["ts_utc"])
    disc = [t for t, log in b["lines"] if log.endswith(f"Client {CLIENT_ID} disconnected.")
            and t.isoformat() < "2026-09-19T00:19"]
    conn = [(t, log) for t, log in b["lines"] if f"as {CLIENT_ID} (" in log]
    subs = [t for t, log in b["lines"] if log.endswith(f"{CLIENT_ID} 1 c2dt/+/+/telemetry")]
    print("\n=== P: controller_restart-r02, the internal block cut on the broker's instants")
    for t, log in conn:
        print(f"P0 connect {iso(t)} | {log}")
    if not disc or not subs:
        print("P0 broker instants unavailable; no partition")
        return
    t_disc = max(d for d in disc if d < first_new_poll)
    t_sub = min(s for s in subs if s > t_disc)
    # 1 s text stamps give a floor for each event; the json time is when the engine read the line
    floor = lambda d: d.replace(microsecond=0)
    off = ck.offset_s
    print(f"P0 marker offset guest - harness = {off:+.3f} s (manifest controller_marker); applied to every guest instant")
    print(f"P0 old client disconnect: json time {iso(t_disc)} guest; text second {iso(floor(t_disc))}")
    print(f"P0 new subscription:      json time {iso(t_sub)} guest; text second {iso(floor(t_sub))}")
    print(f"P0 last answered old poll {iso(last_poll)} harness; first answered new poll {iso(first_new_poll)} harness")
    a, bnd = bl[0]
    mem = sent[a - 1:bnd]
    pubs = [ck.pub(s["publish_monotonic_ns"]) for s in mem]
    print(f"P0 block sent_events.jsonl:{a}-{bnd} ({len(mem)}): first published {iso(pubs[0])}, "
          f"last published {iso(pubs[-1])} harness wall")
    nxt = ck.pub(sent[bnd]["publish_monotonic_ns"])
    print(f"P0 first identity after the block, sent_events.jsonl:{bnd + 1}, published {iso(nxt)} harness wall")

    def cut(label: str, d_disc: datetime, d_sub: datetime) -> tuple[int, int, int, int]:
        """G1 is cut on the harness wall alone; the broker instants are guest wall mapped at the
        marker offset. If the disconnect maps before the last poll, the G1 members published
        after it are reported apart (g1_after) and stay in G1, so the total is always the block."""
        hd, hs = ck.guest_to_harness(d_disc), ck.guest_to_harness(d_sub)
        lo = max(hd, last_poll)
        g1 = sum(1 for p in pubs if p <= last_poll)
        g1_after = sum(1 for p in pubs if hd < p <= last_poll)
        gA = sum(1 for p in pubs if last_poll < p <= lo)
        gB = sum(1 for p in pubs if lo < p <= hs)
        gC = sum(1 for p in pubs if p > hs)
        print(f"P1 [{label}] G1 <= last poll {g1} (of which published after the disconnect {g1_after}) | "
              f"(last poll, disconnect {iso(hd)}] {gA} | (later of the two, subscription {iso(hs)}] {gB} | "
              f"after the subscription {gC} | total {g1 + gA + gB + gC}")
        return g1, gA, gB + g1_after, gC

    res = [cut("broker json times", t_disc, t_sub)]
    if c.get("mqtt_disconnected") and c.get("sub_requested"):
        res.append(cut("controller's own stamps 'MQTT disconnected' / 'subscription requested'",
                       c["mqtt_disconnected"], c["sub_requested"]))
    if c.get("shutting_down"):
        res.append(cut("earliest disconnect ('Shutting down', engine time) / broker json subscription",
                       c["shutting_down"], t_sub))
    # The boundary identities bound the guest-minus-harness offset near the subscription: the last
    # block member (no outcome) was published before the subscription took effect and the next
    # identity (with an outcome) after it. Publication-to-broker transit is ignored.
    t_sub_lo = c.get("sub_requested", floor(t_sub))
    off_hi = (t_sub - pubs[-1]).total_seconds()
    off_lo = (t_sub_lo - nxt).total_seconds()
    print(f"P4 offset guest - harness implied by the boundary identities: between {off_lo:+.3f} and "
          f"{off_hi:+.3f} s (marker: {off:+.3f} s)")
    for o in (off_lo, off_hi):
        sh = off - o  # moving a guest instant by (off - o) makes guest_to_harness apply offset o
        res.append(cut(f"broker json times, offset {o:+.3f} s", t_disc + timedelta(seconds=sh),
                       t_sub + timedelta(seconds=sh)))
    for sh in (-0.5, +0.5):
        cut(f"broker json times, offset shifted {sh:+.1f} s (outside the implied window; for scale)",
            t_disc + timedelta(seconds=sh), t_sub + timedelta(seconds=sh))
    nosub = [x[2] for x in res]
    maybe = [x[1] for x in res]
    print(f"P2 published while no subscription for {CLIENT_ID} existed: {min(nosub)} to {max(nosub)} over the "
          f"readings above (the +-0.5 s rows excluded); published after the last poll and before the disconnect: "
          f"{min(maybe)} to {max(maybe)}")
    # every published identity (not only the block) inside the no-subscription interval
    hd, hs = ck.guest_to_harness(t_disc), ck.guest_to_harness(t_sub)
    inside = [i for i, s in enumerate(sent) if hd < ck.pub(s["publish_monotonic_ns"]) <= hs]
    with_out = sum(1 for i in inside if sent[i]["message_id"] in r["has_g"])
    print(f"P3 all identities published inside (disconnect, subscription] on json times: {len(inside)} "
          f"(sent_events.jsonl:{inside[0] + 1}-{inside[-1] + 1}); with an outcome in the guest copy: {with_out}")
    after = [i for i, s in enumerate(sent) if ck.pub(s["publish_monotonic_ns"]) > hs]
    wo = sum(1 for i in after[:200] if sent[i]["message_id"] not in r["has_g"])
    print(f"P3 of the first 200 identities published after the subscription, without an outcome in the guest copy: {wo}")
    if j:
        sigterm_est = j["force"] - timedelta(seconds=j["timeout_s"])
        print("\n=== X: stop timeline, guest wall (and harness wall at the marker offset)")
        for lab, t in (("last answered old poll (a harness instant, shown on guest wall)", last_poll + timedelta(seconds=off)),
                       ("signal 15 sent, at the latest (force time - timeout)", sigterm_est),
                       ("broker logs the old client's disconnect", t_disc),
                       ("engine gives up on signal 15 and forces the stop", j["force"]),
                       ("old process's last outcome (controller wall at the marker)", None),
                       ("exit status recorded by the engine", j["exit_at"]),
                       ("new container started (systemd)", j.get("started")),
                       ("new client connected (broker)", conn[-1][0] if conn else None),
                       ("new subscription (broker)", t_sub)):
            if t is None:
                last_old = max((e for e in r["guest"] if e["message_id"] in {s["message_id"] for s in sent[:a - 1]}),
                               key=lambda e: e["ditto_ack_monotonic_ns"])
                t = ck.ctl_guest(last_old["ditto_ack_monotonic_ns"])
            print(f"X1 {iso(t)} guest  {iso(ck.guest_to_harness(t))} harness  {lab}")
        print(f"X2 signal {j['signal']}, timeout {j['timeout_s']} s, exit status {j['exit_code']} "
              f"(= 128 + {j['exit_code'] - 128}), execDuration {j['exec']}")


def main() -> None:
    r02 = event_logs("controller_restart-r02", "R02")
    event_logs("controller_restart-r01", "R01")
    j = journal()
    b = broker()
    c = controller_log(r02)
    partition(r02, j, b, c)


if __name__ == "__main__":
    main()
