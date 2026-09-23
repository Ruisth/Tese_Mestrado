"""Cases for tools/probe/broker_hold.py (the broker-hold measurement of ADR 0011, C3).

The clients are exercised against a fake paho client that replays deliveries
and acknowledgements synchronously; ``generate`` runs the real simulator loop
with a fake clock; ``verdict`` is fed hand-written records for a supporting
run and for each refuting and inconclusive shape. Nothing here touches a
broker, the guest or the network, and nothing here is evidence about the
pinned Mosquitto: it shows only that the tool applies the design's rules.
"""
from __future__ import annotations

import importlib.util
import json
import sys
import threading
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
MODULE = REPO_ROOT / "tools" / "probe" / "broker_hold.py"


def _load():
    spec = importlib.util.spec_from_file_location("broker_hold", MODULE)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["broker_hold"] = mod
    spec.loader.exec_module(mod)
    return mod


bh = _load()


# --------------------------------------------------------------------------
# a fake paho client
# --------------------------------------------------------------------------

class Reason:
    def __init__(self, value=0, name="Success"):
        self.value = value
        self._name = name

    @property
    def is_failure(self):
        return self.value >= 128

    def getName(self):
        return self._name


class Flags:
    def __init__(self, session_present=False):
        self.session_present = session_present


class Info:
    def __init__(self, mid):
        self.mid = mid
        self.rc = 0


class Msg:
    def __init__(self, topic, payload, mid, dup=False, qos=1):
        self.topic = topic
        self.payload = payload
        self.mid = mid
        self.dup = dup
        self.qos = qos
        self.retain = False


class FakeClient:
    """Replays the broker's side synchronously.

    ``deliveries`` are handed to ``on_message`` right after the SUBACK;
    ``session_present`` is what the CONNACK carries; ``puback_delay`` publishes
    are acknowledged immediately unless ``ack_missing`` names their index.
    """

    def __init__(self, *, deliveries=(), session_present=False, ack_missing=(), granted=1,
                 refuse_connect=False):
        self.deliveries = list(deliveries)
        self.session_present = session_present
        self.ack_missing = set(ack_missing)
        self.granted = granted
        self.refuse_connect = refuse_connect
        self.on_connect = None
        self.on_subscribe = None
        self.on_message = None
        self.on_publish = None
        self.on_disconnect = None
        self.acks = []
        self.published = []
        self.subscriptions = []
        self.disconnected = False
        self._mid = 0
        self.kwargs = {}

    def connect(self, host, port, keepalive=60):
        self.host, self.port = host, port

    def loop_start(self):
        if self.refuse_connect:
            self.on_connect(self, None, Flags(False), Reason(135, "NotAuthorized"), None)
            return
        self.on_connect(self, None, Flags(self.session_present), Reason(0), None)

    def loop_stop(self):
        pass

    def subscribe(self, topic, qos=0):
        self.subscriptions.append((topic, qos))
        if self.on_subscribe:
            self.on_subscribe(self, None, 1, [Reason(self.granted, f"GrantedQoS{self.granted}")], None)
        for m in self.deliveries:
            self.on_message(self, None, m)

    def publish(self, topic, payload, qos=1):
        self._mid += 1
        info = Info(self._mid)
        self.published.append((topic, payload, qos, info.mid))
        if (self._mid - 1) not in self.ack_missing and self.on_publish:
            self.on_publish(self, None, info.mid, Reason(0), None)
        return info

    def ack(self, mid, qos):
        self.acks.append((mid, qos))
        return Reason(0)

    def disconnect(self):
        self.disconnected = True


def _delivery(message_id, device, seq, mid, dup=False, run_id="brkhold-r01"):
    payload = json.dumps({"message_id": message_id, "device_uuid": device, "seq": seq, "run_id": run_id}).encode()
    return Msg(f"c2dt/egw-01/{device}/telemetry", payload, mid, dup=dup)


# --------------------------------------------------------------------------
# hold
# --------------------------------------------------------------------------

def test_hold_records_every_delivery_and_acknowledges_nothing_without_ack(tmp_path):
    client = FakeClient(deliveries=[_delivery("m1", "d1", 0, 1), _delivery("m2", "d1", 1, 2, dup=True)])
    rec = bh.Recorder(tmp_path / "hold.jsonl")
    stop = tmp_path / "stop"
    stop.write_text("")
    summary = bh.run_hold(client=client, recorder=rec, host="h", port=1, topic=bh.TELEMETRY_FILTER,
                          ack=False, stop_file=stop, expect=None, idle_s=0, limit_s=5, connect_timeout_s=1)
    rec.close()
    assert summary["received"] == 2 and summary["acked"] == 0 and summary["why"] == "stop-file"
    assert client.acks == []
    assert client.subscriptions == [(bh.TELEMETRY_FILTER, 1)]
    records = bh.read_jsonl(tmp_path / "hold.jsonl")
    events = [r["event"] for r in records]
    assert events[:2] == ["connect", "subscribe"] and events[-1] == "end"
    deliveries = [r for r in records if r["event"] == "delivery"]
    assert [d["message_id"] for d in deliveries] == ["m1", "m2"]
    assert [d["dup"] for d in deliveries] == [False, True]
    assert all(d["acked"] is False for d in deliveries)
    assert records[0]["session_present"] is False


def test_hold_with_ack_acknowledges_each_delivery_after_recording_it_and_ends_when_expected_and_idle(tmp_path):
    client = FakeClient(deliveries=[_delivery("m1", "d1", 0, 7, dup=True), _delivery("m2", "d2", 0, 8, dup=True)],
                        session_present=True)
    rec = bh.Recorder(tmp_path / "hold.jsonl")
    summary = bh.run_hold(client=client, recorder=rec, host="h", port=1, topic=bh.TELEMETRY_FILTER,
                          ack=True, stop_file=None, expect=2, idle_s=0.0, limit_s=5, connect_timeout_s=1)
    rec.close()
    assert summary == {**summary, "received": 2, "acked": 2, "why": "expected-and-idle", "session_present": True}
    assert client.acks == [(7, 1), (8, 1)]
    records = bh.read_jsonl(tmp_path / "hold.jsonl")
    assert records[0]["event"] == "connect" and records[0]["session_present"] is True
    assert all(d["acked"] is True for d in records if d["event"] == "delivery")


def test_hold_reports_a_refused_connection_as_a_prerequisite(tmp_path):
    client = FakeClient(refuse_connect=True)
    rec = bh.Recorder(tmp_path / "hold.jsonl")
    with pytest.raises(ConnectionError):
        bh.run_hold(client=client, recorder=rec, host="h", port=1, topic=bh.TELEMETRY_FILTER, ack=False,
                    stop_file=None, expect=None, idle_s=0, limit_s=1, connect_timeout_s=0.2)
    rec.close()


def test_hold_cli_never_takes_the_password_from_argv(tmp_path, monkeypatch):
    monkeypatch.delenv("MOSQUITTO_CONTROLLER_PASSWORD", raising=False)
    rc = bh.main(["hold", "--record", str(tmp_path / "r.jsonl"), "--stop-file", str(tmp_path / "s")])
    assert rc == bh.EXIT_PREREQUISITE


# --------------------------------------------------------------------------
# publish
# --------------------------------------------------------------------------

def _messages(n, devices=("d1", "d2"), rate=11.2):
    out = []
    for i in range(n):
        dev = devices[i % len(devices)]
        payload = json.dumps({"message_id": f"m{i}", "device_uuid": dev, "seq": i // len(devices)})
        out.append({"i": i, "t_offset_s": round(i / rate, 6), "topic": f"c2dt/egw-01/{dev}/telemetry",
                    "message_id": f"m{i}", "device_uuid": dev, "device_type": "smartwatch", "seq": i // len(devices),
                    "bytes": len(payload), "payload_b64": bh.base64.b64encode(payload.encode()).decode()})
    return out


class FastClock:
    def __init__(self):
        self.t = 0.0

    def monotonic(self):
        return self.t

    def sleep(self, s):
        self.t += s


def test_publish_slice_publishes_exactly_the_slice_in_order_and_records_each_puback(tmp_path):
    msgs = _messages(10)
    client = FakeClient()
    rec = bh.Recorder(tmp_path / "pub.jsonl")
    summary = bh.publish_slice(msgs, first=3, count=4, rate_hint=11.2, client=client, recorder=rec,
                               host="h", port=1, connect_timeout_s=1, drain_s=0.5, clock=FastClock())
    rec.close()
    assert summary["published"] == 4 and summary["acked"] == 4 and summary["unacked"] == 0
    assert [json.loads(p[1])["message_id"] for p in client.published] == ["m3", "m4", "m5", "m6"]
    assert all(p[2] == 1 for p in client.published)
    records = [r for r in bh.read_jsonl(tmp_path / "pub.jsonl") if r["event"] == "published"]
    assert [r["message_id"] for r in records] == ["m3", "m4", "m5", "m6"]
    assert all(r["puback_mono_ns"] is not None for r in records)
    assert records[0]["due_offset_s"] == 0.0 and records[1]["due_offset_s"] == pytest.approx(1 / 11.2, abs=1e-6)
    assert client.disconnected


def test_publish_slice_counts_a_missing_puback_as_not_exact(tmp_path):
    msgs = _messages(5)
    client = FakeClient(ack_missing={1})
    rec = bh.Recorder(tmp_path / "pub.jsonl")
    summary = bh.publish_slice(msgs, first=0, count=3, rate_hint=11.2, client=client, recorder=rec,
                               host="h", port=1, connect_timeout_s=1, drain_s=0.2, clock=FastClock())
    rec.close()
    assert summary["published"] == 3 and summary["acked"] == 2 and summary["unacked"] == 1


def test_publish_slice_refuses_a_slice_outside_the_messages(tmp_path):
    with pytest.raises(ValueError):
        bh.publish_slice(_messages(3), first=2, count=2, rate_hint=11.2, client=FakeClient(),
                         recorder=bh.Recorder(tmp_path / "p.jsonl"), host="h", port=1,
                         connect_timeout_s=1, drain_s=0, clock=FastClock())


# --------------------------------------------------------------------------
# sysreader and discard
# --------------------------------------------------------------------------

def test_sysreader_records_every_value_and_the_version(tmp_path, capsys):
    client = FakeClient(deliveries=[Msg("$SYS/broker/version", b"mosquitto version 2.0.22", 1, qos=0),
                                    Msg("$SYS/broker/store/messages/count", b"7", 2, qos=0)], granted=0)
    rec = bh.Recorder(tmp_path / "sys.jsonl")
    stop = tmp_path / "stop"
    stop.write_text("")
    summary = bh.run_sysreader(client=client, recorder=rec, host="h", port=1, stop_file=stop, limit_s=5,
                               connect_timeout_s=1)
    rec.close()
    assert summary["received"] == 2 and summary["version"] == "mosquitto version 2.0.22"
    values = [(r["topic"], r["value"]) for r in bh.read_jsonl(tmp_path / "sys.jsonl") if r["event"] == "sys"]
    assert values == [("$SYS/broker/version", "mosquitto version 2.0.22"), ("$SYS/broker/store/messages/count", "7")]
    assert "SYS: $SYS/broker/version = mosquitto version 2.0.22" in capsys.readouterr().out


def test_sysreader_reports_a_refused_sys_subscription(tmp_path):
    client = FakeClient(granted=128)
    rec = bh.Recorder(tmp_path / "sys.jsonl")
    stop = tmp_path / "stop"
    stop.write_text("")
    with pytest.raises(ConnectionError, match=r"\$SYS/# refused"):
        bh.run_sysreader(client=client, recorder=rec, host="h", port=1, stop_file=stop, limit_s=1, connect_timeout_s=1)
    rec.close()


def test_discard_records_the_session_present_flag_of_a_clean_connect(tmp_path):
    client = FakeClient(session_present=False)
    rec = bh.Recorder(tmp_path / "d.jsonl")
    state = bh.run_discard(client=client, recorder=rec, host="h", port=1, connect_timeout_s=1)
    rec.close()
    assert state["session_present"] is False and client.disconnected
    assert bh.read_jsonl(tmp_path / "d.jsonl")[0]["event"] == "discard"


# --------------------------------------------------------------------------
# generate (the real simulator loop with a fake clock)
# --------------------------------------------------------------------------

egw_simulator = pytest.importorskip("egw_simulator", reason="the simulator package is not importable here")


def test_generate_reproduces_the_nominal_mix_in_order_with_real_sizes(tmp_path):
    msgs = bh.generate_messages(seed=42, run_id="brkhold-r01", egw_id="egw-01", count=300, rate_hz=11.2,
                                work_dir=tmp_path / "w1")
    again = bh.generate_messages(seed=42, run_id="brkhold-r01", egw_id="egw-01", count=300, rate_hz=11.2,
                                 work_dir=tmp_path / "w2")
    assert len(msgs) == 300
    assert [m["message_id"] for m in msgs] == [m["message_id"] for m in again]
    assert [m["i"] for m in msgs] == list(range(300))
    offsets = [m["t_offset_s"] for m in msgs]
    assert offsets == sorted(offsets) and offsets[0] == 0.0
    # the nominal aggregate: 300 messages span about 300 / 11.2 s
    assert offsets[-1] == pytest.approx(299 / 11.2, rel=0.05)
    sizes = [m["bytes"] for m in msgs]
    assert 250 <= min(sizes) and max(sizes) <= 340
    per_device = {}
    for m in msgs:
        last = per_device.get(m["device_uuid"])
        assert last is None or m["seq"] == last + 1, "per-device seq must be gap-free and ascending"
        per_device[m["device_uuid"]] = m["seq"]
    assert set(m["device_type"] for m in msgs) == {"smartwatch", "smart_ring", "smart_clothing"}
    assert (tmp_path / "w1" / "brkhold-r01" / "sent_events.jsonl").exists()


def test_generate_cli_writes_the_messages_file(tmp_path, capsys):
    out = tmp_path / "messages.jsonl"
    rc = bh.main(["generate", "--count", "50", "--work-dir", str(tmp_path / "w"), "--out", str(out)])
    assert rc == 0
    assert len(bh.read_jsonl(out)) == 50
    assert "generated: count=50" in capsys.readouterr().out


# --------------------------------------------------------------------------
# verdict
# --------------------------------------------------------------------------

T0 = 1_800_000_000  # an epoch second; the records are placed relative to it


def _utc(epoch: float) -> str:
    from datetime import datetime, timezone
    dt = datetime.fromtimestamp(epoch, tz=timezone.utc)
    return dt.strftime("%Y-%m-%dT%H:%M:%S") + f".{dt.microsecond // 1000:03d}Z"


def _phases(**overrides):
    # P0 0-60, P1 60-70, P2 70-150, P3 150-200, P4 200-205, P5 205-240, P6 240-280, P7 280-320, P8 320-350
    bounds = {"P0": (0, 60), "P1": (60, 70), "P2": (70, 150), "P3": (150, 200), "P4": (200, 205),
              "P5": (205, 240), "P6": (240, 280), "P7": (280, 320), "P8": (320, 350)}
    phases = {}
    for name, (s, e) in bounds.items():
        phases[name] = {"start_utc": _utc(T0 + s), "end_utc": _utc(T0 + e)}
    phases["P4"]["disconnection_seen"] = True
    for k, v in overrides.items():
        phases.setdefault(k, {}).update(v)
    return phases


def _pub(ids, devices, start, unacked=0):
    recs = []
    for k, (mid, dev) in enumerate(zip(ids, devices)):
        recs.append({"event": "published", "t_utc": _utc(T0 + start + k), "i": k, "mid": k + 1, "rc": 0,
                     "message_id": mid, "device_uuid": dev, "seq": k // 2, "bytes": 300,
                     "puback_mono_ns": None if k < unacked else 1})
    recs.append({"event": "end", "t_utc": _utc(T0 + start + len(ids)), "published": len(ids),
                 "acked": len(ids) - unacked, "unacked": unacked})
    return recs


def _hold(deliveries, start, session_present):
    recs = [{"event": "connect", "t_utc": _utc(T0 + start), "session_present": session_present, "reason": "0:Success"},
            {"event": "subscribe", "t_utc": _utc(T0 + start), "granted": ["1:GrantedQoS1"]}]
    for k, (mid, dev, seq, dup) in enumerate(deliveries):
        recs.append({"event": "delivery", "t_utc": _utc(T0 + start + 1 + k * 0.01), "n": k + 1, "mid": k + 1,
                     "dup": dup, "qos": 1, "topic": f"c2dt/egw-01/{dev}/telemetry", "message_id": mid,
                     "device_uuid": dev, "seq": seq, "bytes": 300, "acked": session_present})
    recs.append({"event": "end", "t_utc": _utc(T0 + start + 10), "received": len(deliveries)})
    return recs


def _sys(points):
    """points: list of (offset_s, topic, value)."""
    recs = [{"event": "connect", "t_utc": _utc(T0), "reason": "0:Success", "session_present": False},
            {"event": "sys", "t_utc": _utc(T0 + 1), "topic": bh.SYS_VERSION, "value": "mosquitto version 2.0.22"}]
    for off, topic, value in points:
        recs.append({"event": "sys", "t_utc": _utc(T0 + off), "topic": topic, "value": str(value)})
    return recs


def _recorder(n=350, gap_at=None, oom_kill=0, restarts=0, anon_step=1000):
    rows = []
    for k in range(n):
        if gap_at is not None and gap_at <= k < gap_at + 8:
            continue
        rows.append({"ts_utc": _utc(T0 + k), "epoch": str(T0 + k), "mem_current": str(20_000_000 + k * anon_step),
                     "mem_max": "134217728", "mem_peak": str(20_000_000 + k * anon_step), "anon": str(10_000_000 + k * anon_step),
                     "file": "5000000", "active_file": "1", "inactive_file": "2", "ev_max": "0", "ev_oom": "0",
                     "ev_oom_kill": str(oom_kill if k > 250 else 0), "db_bytes": "100", "state": "running",
                     "restarts": str(restarts if k > 250 else 0)})
    return rows


BROKER_LOG = [
    "2026-09-24T10:00:00: mosquitto version 2.0.22 starting",
    "2026-09-24T10:00:00: Config loaded from /mosquitto/config/mosquitto.conf.",
    "2026-09-24T10:00:00: Opening ipv4 listen socket on port 8883.",
    "2026-09-24T10:01:10: New client connected from 10.0.2.2:5000 as egw-probe-hold (p2, c0, k60, u'egw-controller').",
    "2026-09-24T10:03:20: Client egw-probe-hold closed its connection.",
    "2026-09-24T10:04:40: New client connected from 10.0.2.2:5001 as egw-probe-hold (p2, c0, k60, u'egw-controller').",
]

A, B, W, Q = 6, 4, 6, 2
P2_IDS = [f"a{k}" for k in range(A)]
P2_DEV = ["d1", "d2"] * (A // 2)
P5_IDS = [f"b{k}" for k in range(B)]
P5_DEV = ["d1", "d2"] * (B // 2)
PARAMS = {"W": W, "Q": Q, "A": A, "B": B, "memory_max": 134217728, "recorder_gap_limit_s": 5}


def _supporting_records():
    p1 = _hold([(mid, dev, k // 2, False) for k, (mid, dev) in enumerate(zip(P2_IDS, P2_DEV))], 60, False)
    # held at the end of P6: the 6 in flight plus Q = 2 queued of the 4 published in P5 (queue above the window)
    held = [(mid, dev, k // 2, True) for k, (mid, dev) in enumerate(zip(P2_IDS, P2_DEV))] + \
           [(mid, dev, 3 + k // 2, False) for k, (mid, dev) in enumerate(zip(P5_IDS[:Q], P5_DEV[:Q]))]
    p7 = _hold(held, 280, True)
    sysp = [(50, bh.SYS_STORE, 0), (50, bh.SYS_DROPPED, 0), (50, bh.SYS_INFLIGHT, 0),
            (149, bh.SYS_STORE, A), (149, bh.SYS_INFLIGHT, A), (149, bh.SYS_DROPPED, 0),
            (199, bh.SYS_STORE, A), (204, bh.SYS_STORE, A), (204, bh.SYS_DROPPED, 0), (204, bh.SYS_DISCONNECTED, 1),
            (239, bh.SYS_STORE, A + Q), (239, bh.SYS_DROPPED, B - Q),
            (279, bh.SYS_STORE, A + Q), (279, bh.SYS_DROPPED, B - Q),
            (319, bh.SYS_STORE, 0), (319, bh.SYS_DROPPED, B - Q), (319, bh.SYS_CONNECTED, 2)]
    return {"params": PARAMS, "phases": _phases(), "broker_log": BROKER_LOG,
            "publish_p2": _pub(P2_IDS, P2_DEV, 70), "publish_p5": _pub(P5_IDS, P5_DEV, 205),
            "hold_p1": p1, "hold_p7": p7, "sys_records": _sys(sysp), "recorder_rows": _recorder()}


def test_verdict_supports_when_every_condition_holds():
    v = bh.compute_verdict(**_supporting_records())
    assert v["inconclusive"] == []
    assert v["refuted"] == []
    assert all(v["supports"][k] for k in ("S1", "S2", "S3", "S4", "S5")), v["supports"]
    assert v["result"] == "supports"
    f = v["figures"]
    assert f["store_end_p6"] == A + Q and f["drops_in_p5_p6"] == B - Q
    assert f["queue_accounting"].startswith("above the held")
    assert f["p7_dup_flag_on_first_copies_of_p2"] == A
    assert f["memory_max_as_expected"] is True
    assert f["anon_per_message_p2_bytes"] == pytest.approx((200 - 70) * 1000 / A, rel=0.01)
    assert f["p7_session_present"] is True


def test_verdict_r2_when_the_window_holds_fewer_than_a():
    r = _supporting_records()
    r["hold_p1"] = [x for x in r["hold_p1"] if not (x["event"] == "delivery" and x["message_id"] == "a5")]
    v = bh.compute_verdict(**r)
    assert v["refutes"]["R2"] is True and v["result"] == "refutes" and "R2" in v["refuted"]


def test_verdict_r3_when_the_broker_drops_while_held_at_most_w():
    r = _supporting_records()
    r["sys_records"] = _sys([(50, bh.SYS_STORE, 0), (50, bh.SYS_DROPPED, 0), (149, bh.SYS_STORE, A),
                             (149, bh.SYS_DROPPED, 1), (204, bh.SYS_DROPPED, 1), (279, bh.SYS_STORE, A + Q),
                             (279, bh.SYS_DROPPED, 1 + B - Q), (319, bh.SYS_STORE, 0)])
    v = bh.compute_verdict(**r)
    assert v["refutes"]["R3"] is True and v["result"] == "refutes"
    assert v["figures"]["drops_through_p4"] == 1


def test_verdict_r4_on_an_oom_kill_or_a_restart():
    r = _supporting_records()
    r["recorder_rows"] = _recorder(oom_kill=1)
    v = bh.compute_verdict(**r)
    assert v["refutes"]["R4"] is True and v["result"] == "refutes"
    r["recorder_rows"] = _recorder(restarts=1)
    assert bh.compute_verdict(**r)["refutes"]["R4"] is True


def test_verdict_r5_when_fewer_are_redelivered_than_the_store_held():
    r = _supporting_records()
    r["hold_p7"] = [x for x in r["hold_p7"] if not (x["event"] == "delivery" and x["message_id"] == "b1")]
    v = bh.compute_verdict(**r)
    assert v["refutes"]["R5"] is True and v["result"] == "refutes"
    assert v["figures"]["p7_redelivered_distinct"] == A + Q - 1


def test_verdict_r6_on_a_per_device_order_break_of_first_copies():
    r = _supporting_records()
    deliveries = [x for x in r["hold_p7"] if x["event"] == "delivery"]
    others = [x for x in r["hold_p7"] if x["event"] != "delivery"]
    # a4 (d1, seq 2) arrives before a2 (d1, seq 1): a break for d1
    a2 = next(d for d in deliveries if d["message_id"] == "a2")
    a4 = next(d for d in deliveries if d["message_id"] == "a4")
    swapped = []
    for d in deliveries:
        if d is a2:
            swapped.append(a4)
        elif d is a4:
            swapped.append(a2)
        else:
            swapped.append(d)
    r["hold_p7"] = others[:2] + swapped + others[2:]
    v = bh.compute_verdict(**r)
    assert v["refutes"]["R6"] is True and v["result"] == "refutes"
    assert v["figures"]["p7_order_breaks"][0]["device_uuid"] == "d1"


def test_verdict_later_copies_are_recorded_and_not_judged_for_order():
    r = _supporting_records()
    dup_again = dict(next(x for x in r["hold_p7"] if x["event"] == "delivery" and x["message_id"] == "a0"))
    r["hold_p7"].insert(-1, dup_again)  # a0 (d1, seq 0) delivered again at the end
    v = bh.compute_verdict(**r)
    assert v["result"] == "supports" and v["figures"]["p7_later_copies"] == 1


@pytest.mark.parametrize("shape, says", [
    ("recorder-gap", "gap"),
    ("publisher-not-exact", "publisher did not publish"),
    ("p7-limit", "P7 reached its limit"),
    ("no-sys", "$SYS could not be read"),
    ("no-disconnection-line", "disconnection line"),
    ("stop-rule", "stop rule"),
])
def test_verdict_is_inconclusive_and_not_passing_for_each_inconclusive_shape(shape, says):
    r = _supporting_records()
    if shape == "recorder-gap":
        r["recorder_rows"] = _recorder(gap_at=100)
    elif shape == "publisher-not-exact":
        r["publish_p2"] = _pub(P2_IDS, P2_DEV, 70, unacked=1)
    elif shape == "p7-limit":
        r["phases"] = _phases(P7={"limit_reached": True})
    elif shape == "no-sys":
        r["sys_records"] = _sys([])
    elif shape == "no-disconnection-line":
        r["phases"] = _phases(P4={"disconnection_seen": False})
        r["broker_log"] = [ln for ln in BROKER_LOG if "closed its connection" not in ln]
    elif shape == "stop-rule":
        r["phases"] = _phases(setup={"stop_rule_reached": "the stack was not stopped within 300 s"})
    v = bh.compute_verdict(**r)
    assert v["result"] == "inconclusive", v
    assert any(says in reason for reason in v["inconclusive"]), v["inconclusive"]


def test_verdict_a_refutation_stands_even_when_the_run_is_also_inconclusive():
    r = _supporting_records()
    r["recorder_rows"] = _recorder(gap_at=100, oom_kill=1)
    v = bh.compute_verdict(**r)
    assert v["result"] == "refutes" and v["inconclusive"]


def test_verdict_r1_when_the_broker_refuses_the_configuration():
    r = _supporting_records()
    r["broker_log"] = ["2026-09-24T10:00:00: Error: Invalid max_inflight_messages value (70000)."]
    v = bh.compute_verdict(**r)
    assert v["refutes"]["R1"] is True and v["supports"]["S1"] is False and v["result"] == "refutes"


def test_verdict_in_total_accounting_is_recorded_not_refuting():
    r = _supporting_records()
    # the store stays at A while the client is away and every P5 message is dropped
    r["sys_records"] = _sys([(50, bh.SYS_STORE, 0), (50, bh.SYS_DROPPED, 0), (149, bh.SYS_STORE, A),
                             (204, bh.SYS_STORE, A), (204, bh.SYS_DROPPED, 0), (239, bh.SYS_STORE, A),
                             (239, bh.SYS_DROPPED, B), (279, bh.SYS_STORE, A), (279, bh.SYS_DROPPED, B),
                             (319, bh.SYS_STORE, 0), (319, bh.SYS_DROPPED, B)])
    p7 = _hold([(mid, dev, k // 2, True) for k, (mid, dev) in enumerate(zip(P2_IDS, P2_DEV))], 280, True)
    r["hold_p7"] = p7
    v = bh.compute_verdict(**r)
    assert v["result"] == "supports"
    assert v["figures"]["queue_accounting"].startswith("in total")


def test_verdict_cli_writes_the_json_and_exits_by_result(tmp_path):
    r = _supporting_records()
    files = {}
    for name in ("publish_p2", "publish_p5", "hold_p1", "hold_p7", "sys_records"):
        p = tmp_path / f"{name}.jsonl"
        p.write_text("".join(json.dumps(x) + "\n" for x in r[name]), encoding="utf-8")
        files[name] = p
    phases = tmp_path / "phases.jsonl"
    with open(phases, "w", encoding="utf-8") as fh:
        for name, p in r["phases"].items():
            fh.write(json.dumps({"phase": name, **p}) + "\n")
    rec = tmp_path / "recorder.csv"
    cols = list(r["recorder_rows"][0].keys())
    with open(rec, "w", encoding="utf-8") as fh:
        fh.write("# probe_recorder container=x\n" + ",".join(cols) + "\n")
        for row in r["recorder_rows"]:
            fh.write(",".join(row[c] for c in cols) + "\n")
        fh.write("# stop samples=350\n")
    (tmp_path / "broker.log").write_text("\n".join(r["broker_log"]) + "\n", encoding="utf-8")
    (tmp_path / "params.json").write_text(json.dumps(PARAMS), encoding="utf-8")
    out = tmp_path / "verdict.json"
    rc = bh.main(["verdict", "--params", str(tmp_path / "params.json"), "--phases", str(phases),
                  "--broker-log", str(tmp_path / "broker.log"), "--publish-p2", str(files["publish_p2"]),
                  "--publish-p5", str(files["publish_p5"]), "--hold-p1", str(files["hold_p1"]),
                  "--hold-p7", str(files["hold_p7"]), "--sys", str(files["sys_records"]),
                  "--recorder", str(rec), "--out", str(out)])
    assert rc == 0
    verdict = json.loads(out.read_text(encoding="utf-8"))
    assert verdict["result"] == "supports" and verdict["figures"]["recorder_rows"] == 350


def test_per_device_order_breaks_only_compare_first_copies_per_device():
    first = {"x1": {"device_uuid": "d1", "seq": 0}, "y1": {"device_uuid": "d2", "seq": 5},
             "x2": {"device_uuid": "d1", "seq": 1}, "y2": {"device_uuid": "d2", "seq": 4}}
    breaks = bh._per_device_order_breaks(first)
    assert [b["device_uuid"] for b in breaks] == ["d2"]
