#!/usr/bin/env python3
"""The broker-hold measurement (ADR 0011, condition C3; package D, gate item 1, section 7).

One bounded, broker-only measurement of the pinned Mosquitto 2.0.22 alone: does
it accept and honour an in-flight window ``W`` = 4,999, hold 4,999 and then
4,999 plus a queue of real-sized QoS 1 messages for a non-acknowledging
persistent session within its 128 MiB limit, show where a full queue drops, and
keep and redeliver the held messages, in per-device order, after the subscriber
is killed? It is an engineering diagnostic, not a G3 run: it changes no
threshold, load, deadline or rule, needs no controller change, no image rebuild
and no Ditto, and one run supports the broker-side premise for that run only.

This module holds the host-side clients and the verdict; the session driver
``tools/session/broker_measure.sh`` sequences the phases P0 to P8 and the guest
recorder ``tools/probe/guest/probe_recorder.sh`` samples the broker's cgroup.

Sub-commands (every record is JSON Lines with the host's UTC instant and its
monotonic instant; no secret ever reaches argv or a record):

* ``generate``  — the 6,099 real payloads, regenerated with the repository's own
  simulator (nominal three-device mix, the nominal seed, a fresh 11-character
  run id so that sizes stay 273 to 320 B), in nominal order with their
  scheduled offsets; a fake clock, so nothing is published and nothing waits.
* ``publish``   — publishes a slice of them at the nominal cadence as
  ``egw-simulator`` (QoS 1) and records each PUBACK; exits 0 only when every
  message of the slice was published and acknowledged.
* ``hold``      — the holding subscriber ``egw-probe-hold`` (never the
  controller's id): MQTT 3.1.1, ``clean_session=False``, ``manual_ack=True``,
  QoS 1 on the telemetry filter; records every delivery with its DUP flag and
  acknowledges nothing unless ``--ack`` (phase P7).
* ``sysreader`` — ``egw-probe-sys``, clean session, QoS 0 on ``$SYS/#``; records
  every value with its instant.
* ``discard``   — ends the persistent session of ``egw-probe-hold`` by
  connecting once with a clean session (phase P8).
* ``verdict``   — reads the records and applies S1–S5, R1–R6 and the
  inconclusive rules of the design; prints the verdict and writes it as JSON.

Exit statuses: 0 done (``verdict``: supports), 1 a valid negative
(``publish``: not every message acknowledged; ``verdict``: refutes), 2 a
prerequisite (a connection refused, a file missing, a bad argument), 3 the
verdict is inconclusive.
"""
from __future__ import annotations

import argparse
import base64
import csv
import hashlib
import json
import os
import signal
import sys
import threading
import time
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

#: The topic filter the controller subscribes to (CONTRACTS.md section 1).
TELEMETRY_FILTER = "c2dt/+/+/telemetry"
#: The client ids of the probe. None of them is the controller's.
HOLD_CLIENT_ID = "egw-probe-hold"
SYS_CLIENT_ID = "egw-probe-sys"
PUB_CLIENT_ID = "egw-probe-pub"
#: The nominal aggregate rate (plan section 7.1; egw_simulator.devices).
NOMINAL_RATE_HZ = 11.2
#: paho-mqtt 2.1.0 is the locked client of the simulator and the controller.
PAHO_VERSION = "2.1.0"
#: The $SYS topics the verdict reads (mosquitto(8), 2.0.x).
SYS_STORE = "$SYS/broker/store/messages/count"
SYS_INFLIGHT = "$SYS/broker/messages/inflight"
SYS_DROPPED = "$SYS/broker/publish/messages/dropped"
SYS_CONNECTED = "$SYS/broker/clients/connected"
SYS_DISCONNECTED = "$SYS/broker/clients/disconnected"
SYS_VERSION = "$SYS/broker/version"

EXIT_DONE = 0
EXIT_NEGATIVE = 1
EXIT_PREREQUISITE = 2
EXIT_INCONCLUSIVE = 3


# --------------------------------------------------------------------------
# small helpers
# --------------------------------------------------------------------------

def utc_now() -> str:
    """The host's UTC instant with millisecond resolution."""
    dt = datetime.now(timezone.utc)
    return dt.strftime("%Y-%m-%dT%H:%M:%S") + f".{dt.microsecond // 1000:03d}Z"


def parse_utc(text: str) -> float:
    """Seconds since the epoch of an RFC 3339 UTC instant (``Z``), or raise."""
    t = text.strip()
    if not t.endswith("Z"):
        raise ValueError(f"not a UTC instant: {text!r}")
    t = t[:-1]
    fmt = "%Y-%m-%dT%H:%M:%S.%f" if "." in t else "%Y-%m-%dT%H:%M:%S"
    return datetime.strptime(t, fmt).replace(tzinfo=timezone.utc).timestamp()


class Recorder:
    """Append-only JSON Lines writer; every record carries both instants."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._fh = open(self.path, "a", encoding="utf-8", newline="\n")
        self._lock = threading.Lock()
        self.count = 0

    def write(self, event: str, **fields) -> dict:
        record = {"event": event, "t_utc": utc_now(), "t_mono_ns": time.monotonic_ns(), **fields}
        line = json.dumps(record, separators=(",", ":"), sort_keys=False)
        with self._lock:
            self._fh.write(line + "\n")
            self._fh.flush()
            self.count += 1
        return record

    def close(self) -> None:
        with self._lock:
            if not self._fh.closed:
                self._fh.flush()
                self._fh.close()


def read_jsonl(path: str | Path) -> list[dict]:
    out: list[dict] = []
    with open(path, encoding="utf-8") as fh:
        for n, line in enumerate(fh, 1):
            line = line.strip()
            if not line:
                continue
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError as exc:
                raise ValueError(f"{path}:{n}: not JSON: {exc}") from None
    return out


def password_from_env(name: str) -> str:
    """The secret is read from the environment, never from argv."""
    value = os.environ.get(name)
    if not value:
        raise SystemExit(f"prerequisite: the environment variable {name} is not set (the password is never passed on the command line)")
    return value


def sha256_file(path: str | Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 16), b""):
            h.update(chunk)
    return h.hexdigest()


# --------------------------------------------------------------------------
# paho client factory (injectable for the tests)
# --------------------------------------------------------------------------

def make_paho_client(*, client_id: str, clean_session: bool, manual_ack: bool,
                     username: str | None, password: str | None,
                     tls: bool, ca_cert: str | None):
    """A paho-mqtt 2.x client, MQTT 3.1.1, callback API version 2."""
    import paho.mqtt.client as mqtt  # lazy: the tests use a fake

    client = mqtt.Client(
        callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
        client_id=client_id,
        clean_session=clean_session,
        protocol=mqtt.MQTTv311,
        manual_ack=manual_ack,
    )
    if username is not None:
        client.username_pw_set(username, password)
    if tls:
        if ca_cert:
            client.tls_set(ca_certs=str(ca_cert))
        else:
            client.tls_set()
    # No automatic reconnect: a reconnection would be a second session
    # resumption the records could not tell from the first.
    client.reconnect_delay_set(min_delay=3600, max_delay=3600)
    return client


def _reason_text(reason_code) -> str:
    try:
        return f"{int(reason_code.value)}:{reason_code.getName()}"
    except Exception:  # a fake, or an int
        return str(reason_code)


def _is_failure(reason_code) -> bool:
    try:
        return bool(reason_code.is_failure)
    except AttributeError:
        return bool(reason_code)


# --------------------------------------------------------------------------
# generate
# --------------------------------------------------------------------------

class _FakeClock:
    """A monotonic clock that only advances when asked to sleep."""

    def __init__(self) -> None:
        self._t = 0.0

    def monotonic(self) -> float:
        return self._t

    def monotonic_ns(self) -> int:
        return int(self._t * 1e9)

    def sleep(self, seconds: float) -> None:
        if seconds > 0:
            self._t += seconds


def generate_messages(*, seed: int, run_id: str, egw_id: str, count: int,
                      rate_hz: float, work_dir: Path) -> list[dict]:
    """The first ``count`` messages of a nominal run, in generation order.

    Runs the repository's simulator loop against an in-memory publisher and a
    fake clock: the payloads, the device mix, the ``message_id``s and the
    per-device ``seq`` are exactly what the simulator would publish for that
    seed and run id; only ``ts`` differs, as it does between any two runs.
    The loop's own evidence (``manifest.json``, ``sent_events.jsonl``) is kept
    under ``work_dir`` as the provenance of the generated set.
    """
    from egw_simulator.publisher import InMemoryPublisher
    from egw_simulator.runner import RunConfig, run

    if count <= 0:
        raise ValueError("count must be positive")
    duration_s = count / rate_hz + 30.0
    clock = _FakeClock()
    publisher = InMemoryPublisher(clock=clock)
    publisher.connect()
    config = RunConfig(
        scenario="nominal", seed=seed, run_id=run_id, egw_id=egw_id,
        duration_s=duration_s, aggregate_rate_hz=rate_hz, qos=1,
        broker_host="none", broker_port=0, tls=False, ca_cert=None,
        output_dir=work_dir,
    )
    result = run(config, publisher, clock=clock)
    if not result.completed or len(publisher.records) < count:
        raise RuntimeError(f"the simulator produced {len(publisher.records)} messages, fewer than {count}")
    first_ns = publisher.records[0][2]
    messages: list[dict] = []
    for i, (topic, payload, mono_ns) in enumerate(publisher.records[:count]):
        body = json.loads(payload)
        messages.append({
            "i": i,
            "t_offset_s": round((mono_ns - first_ns) / 1e9, 6),
            "topic": topic,
            "message_id": body["message_id"],
            "device_uuid": body["device_uuid"],
            "device_type": body["device_type"],
            "seq": body["seq"],
            "bytes": len(payload.encode("utf-8")),
            "payload_b64": base64.b64encode(payload.encode("utf-8")).decode("ascii"),
        })
    return messages


def cmd_generate(args) -> int:
    work_dir = Path(args.work_dir)
    work_dir.mkdir(parents=True, exist_ok=True)
    messages = generate_messages(seed=args.seed, run_id=args.run_id, egw_id=args.egw_id,
                                 count=args.count, rate_hz=args.rate, work_dir=work_dir)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w", encoding="utf-8", newline="\n") as fh:
        for m in messages:
            fh.write(json.dumps(m, separators=(",", ":")) + "\n")
    sizes = [m["bytes"] for m in messages]
    devices = defaultdict(int)
    for m in messages:
        devices[m["device_type"]] += 1
    print(f"generated: count={len(messages)} run_id={args.run_id} seed={args.seed} "
          f"bytes_min={min(sizes)} bytes_max={max(sizes)} "
          f"span_s={messages[-1]['t_offset_s']:.3f} devices={dict(devices)} sha256={sha256_file(out)}")
    return EXIT_DONE


# --------------------------------------------------------------------------
# publish
# --------------------------------------------------------------------------

def publish_slice(messages: list[dict], *, first: int, count: int, rate_hint: float,
                  client, recorder: Recorder, host: str, port: int,
                  connect_timeout_s: float, drain_s: float,
                  clock=time, stop_flag: threading.Event | None = None) -> dict:
    """Publish ``messages[first:first+count]`` at the generated cadence.

    Message ``k`` of the slice is due ``t_offset_s[k] - t_offset_s[first]``
    seconds after the first one, so the slice keeps the nominal three-device
    cadence (aggregate ``rate_hint`` msg/s). Each PUBACK instant is recorded by
    ``mid``; at the end a bounded drain waits for the acknowledgements still
    missing. Returns the counts.
    """
    if first < 0 or count <= 0 or first + count > len(messages):
        raise ValueError(f"slice [{first}, {first + count}) is outside the {len(messages)} messages")
    connected = threading.Event()
    connect_reason: list = []
    pubacks: dict[int, tuple[int, str]] = {}
    lock = threading.Lock()

    def on_connect(c, userdata, flags, reason_code, properties=None):
        connect_reason.append(_reason_text(reason_code))
        if not _is_failure(reason_code):
            connected.set()

    def on_publish(c, userdata, mid, reason_code=None, properties=None):
        with lock:
            pubacks[mid] = (time.monotonic_ns(), utc_now())

    client.on_connect = on_connect
    client.on_publish = on_publish
    client.connect(host, port, keepalive=60)
    client.loop_start()
    if not connected.wait(connect_timeout_s):
        client.loop_stop()
        recorder.write("connect_failed", host=host, port=port, reason=connect_reason[:1])
        raise ConnectionError(f"MQTT connect to {host}:{port} not acknowledged within {connect_timeout_s:.0f} s")
    recorder.write("connected", host=host, port=port, client_id=PUB_CLIENT_ID, reason=connect_reason[0],
                   first=first, count=count, rate_hint=rate_hint)
    t0_offset = messages[first]["t_offset_s"]
    start = clock.monotonic()
    published: list[dict] = []
    for k in range(count):
        m = messages[first + k]
        due = start + (m["t_offset_s"] - t0_offset)
        while True:
            delay = due - clock.monotonic()
            if delay <= 0:
                break
            clock.sleep(min(delay, 0.05))
        if stop_flag is not None and stop_flag.is_set():
            break
        payload = base64.b64decode(m["payload_b64"])
        mono = time.monotonic_ns()
        info = client.publish(m["topic"], payload, qos=1)
        rec = {"i": m["i"], "mid": info.mid, "rc": int(info.rc), "message_id": m["message_id"],
               "device_uuid": m["device_uuid"], "seq": m["seq"], "bytes": len(payload),
               "due_offset_s": round(m["t_offset_s"] - t0_offset, 6), "publish_mono_ns": mono}
        published.append(rec)
    # the bounded drain: every PUBACK still missing gets at most drain_s
    deadline = time.monotonic() + drain_s
    while time.monotonic() < deadline:
        with lock:
            missing = [r for r in published if r["mid"] not in pubacks]
        if not missing:
            break
        time.sleep(0.05)
    with lock:
        for r in published:
            ack = pubacks.get(r["mid"])
            r["puback_mono_ns"] = ack[0] if ack else None
            r["puback_utc"] = ack[1] if ack else None
            recorder.write("published", **r)
    acked = sum(1 for r in published if r["puback_mono_ns"] is not None)
    client.disconnect()
    client.loop_stop()
    summary = {"first": first, "count": count, "published": len(published), "acked": acked,
               "unacked": len(published) - acked, "span_s": round(time.monotonic() - start, 3)}
    recorder.write("end", **summary)
    return summary


def cmd_publish(args, client_factory=make_paho_client) -> int:
    messages = read_jsonl(args.messages)
    password = password_from_env(args.password_env)
    client = client_factory(client_id=args.client_id, clean_session=True, manual_ack=False,
                            username=args.username, password=password,
                            tls=not args.no_tls, ca_cert=args.ca_cert)
    recorder = Recorder(args.record)
    try:
        summary = publish_slice(messages, first=args.first, count=args.count, rate_hint=args.rate,
                                client=client, recorder=recorder, host=args.host, port=args.port,
                                connect_timeout_s=args.connect_timeout, drain_s=args.drain)
    except (ConnectionError, OSError) as exc:
        print(f"STOP: publish: {exc}", file=sys.stderr)
        return EXIT_PREREQUISITE
    finally:
        recorder.close()
    print(f"published: first={summary['first']} count={summary['count']} published={summary['published']} "
          f"acked={summary['acked']} unacked={summary['unacked']} span_s={summary['span_s']}")
    if summary["published"] != summary["count"] or summary["unacked"]:
        print(f"NOT EXACT: the slice was not published and acknowledged in full "
              f"({summary['published']} of {summary['count']} published, {summary['unacked']} unacknowledged)")
        return EXIT_NEGATIVE
    return EXIT_DONE


# --------------------------------------------------------------------------
# hold (the holding subscriber)
# --------------------------------------------------------------------------

def _parse_delivery(msg) -> dict:
    fields = {"topic": msg.topic, "mid": msg.mid, "dup": bool(msg.dup), "qos": int(msg.qos),
              "retain": bool(msg.retain), "bytes": len(msg.payload)}
    try:
        body = json.loads(msg.payload.decode("utf-8"))
        fields["message_id"] = body.get("message_id")
        fields["device_uuid"] = body.get("device_uuid")
        fields["seq"] = body.get("seq")
    except (ValueError, UnicodeDecodeError):
        fields["message_id"] = None
        fields["device_uuid"] = None
        fields["seq"] = None
        fields["undecodable"] = True
    return fields


def run_hold(*, client, recorder: Recorder, host: str, port: int, topic: str,
             ack: bool, stop_file: Path | None, expect: int | None, idle_s: float,
             limit_s: float, connect_timeout_s: float, poll_s: float = 0.2,
             clock=time) -> dict:
    """Subscribe and record until told to stop.

    Ends when ``stop_file`` appears, when ``limit_s`` has elapsed, or, if
    ``expect`` is given, once at least ``expect`` deliveries were received and
    ``idle_s`` seconds passed with no further one. The session is left in
    place by a clean DISCONNECT (a persistent session survives it); phase P4
    kills this process instead, from outside, so that no DISCONNECT is sent.
    """
    connected = threading.Event()
    subscribed = threading.Event()
    state = {"received": 0, "acked": 0, "last_ns": None, "session_present": None,
             "granted": None, "connect_reason": None, "disconnects": 0}
    lock = threading.Lock()

    def on_connect(c, userdata, flags, reason_code, properties=None):
        sp = getattr(flags, "session_present", None)
        state["session_present"] = bool(sp) if sp is not None else None
        state["connect_reason"] = _reason_text(reason_code)
        recorder.write("connect", session_present=state["session_present"], reason=state["connect_reason"])
        if not _is_failure(reason_code):
            connected.set()
            c.subscribe(topic, qos=1)

    def on_subscribe(c, userdata, mid, reason_code_list, properties=None):
        granted = [_reason_text(r) for r in reason_code_list]
        state["granted"] = granted
        recorder.write("subscribe", topic=topic, granted=granted)
        subscribed.set()

    def on_message(c, userdata, msg):
        fields = _parse_delivery(msg)
        with lock:
            state["received"] += 1
            state["last_ns"] = time.monotonic_ns()
            n = state["received"]
        acked_now = False
        if ack:
            rc = c.ack(msg.mid, msg.qos)
            acked_now = int(getattr(rc, "value", rc)) == 0
            if acked_now:
                with lock:
                    state["acked"] += 1
        recorder.write("delivery", n=n, acked=acked_now, **fields)

    def on_disconnect(c, userdata, disconnect_flags, reason_code, properties=None):
        with lock:
            state["disconnects"] += 1
        recorder.write("disconnect", reason=_reason_text(reason_code))

    client.on_connect = on_connect
    client.on_subscribe = on_subscribe
    client.on_message = on_message
    client.on_disconnect = on_disconnect
    client.connect(host, port, keepalive=60)
    client.loop_start()
    if not connected.wait(connect_timeout_s):
        client.loop_stop()
        raise ConnectionError(f"MQTT connect to {host}:{port} not acknowledged within {connect_timeout_s:.0f} s")
    if not subscribed.wait(connect_timeout_s):
        client.loop_stop()
        raise ConnectionError(f"SUBSCRIBE to {topic} not acknowledged within {connect_timeout_s:.0f} s")
    print(f"SUBSCRIBED: topic={topic} granted={state['granted']} session_present={state['session_present']} ack={ack}", flush=True)
    start = clock.monotonic()
    why = "limit"
    while True:
        now = clock.monotonic()
        if stop_file is not None and stop_file.exists():
            why = "stop-file"
            break
        if now - start >= limit_s:
            why = "limit"
            break
        with lock:
            received = state["received"]
            last_ns = state["last_ns"]
        if expect is not None and received >= expect and last_ns is not None \
                and (time.monotonic_ns() - last_ns) / 1e9 >= idle_s:
            why = "expected-and-idle"
            break
        clock.sleep(poll_s)
    client.disconnect()
    client.loop_stop()
    summary = {"received": state["received"], "acked": state["acked"], "why": why,
               "session_present": state["session_present"], "granted": state["granted"],
               "span_s": round(clock.monotonic() - start, 3)}
    recorder.write("end", **summary)
    return summary


def cmd_hold(args, client_factory=make_paho_client) -> int:
    password = password_from_env(args.password_env)
    client = client_factory(client_id=args.client_id, clean_session=False, manual_ack=True,
                            username=args.username, password=password,
                            tls=not args.no_tls, ca_cert=args.ca_cert)
    recorder = Recorder(args.record)
    try:
        summary = run_hold(client=client, recorder=recorder, host=args.host, port=args.port,
                           topic=args.topic, ack=args.ack,
                           stop_file=Path(args.stop_file) if args.stop_file else None,
                           expect=args.expect, idle_s=args.idle, limit_s=args.limit,
                           connect_timeout_s=args.connect_timeout)
    except (ConnectionError, OSError) as exc:
        print(f"STOP: hold: {exc}", file=sys.stderr)
        return EXIT_PREREQUISITE
    finally:
        recorder.close()
    print(f"hold end: received={summary['received']} acked={summary['acked']} why={summary['why']} "
          f"session_present={summary['session_present']} span_s={summary['span_s']}")
    return EXIT_DONE


# --------------------------------------------------------------------------
# sysreader
# --------------------------------------------------------------------------

def run_sysreader(*, client, recorder: Recorder, host: str, port: int, stop_file: Path,
                  limit_s: float, connect_timeout_s: float, poll_s: float = 0.5, clock=time) -> dict:
    connected = threading.Event()
    subscribed = threading.Event()
    state = {"received": 0, "version": None, "granted": None}
    lock = threading.Lock()

    def on_connect(c, userdata, flags, reason_code, properties=None):
        recorder.write("connect", reason=_reason_text(reason_code),
                       session_present=bool(getattr(flags, "session_present", False)))
        if not _is_failure(reason_code):
            connected.set()
            c.subscribe("$SYS/#", qos=0)

    def on_subscribe(c, userdata, mid, reason_code_list, properties=None):
        state["granted"] = [_reason_text(r) for r in reason_code_list]
        recorder.write("subscribe", topic="$SYS/#", granted=state["granted"])
        subscribed.set()

    def on_message(c, userdata, msg):
        try:
            value = msg.payload.decode("utf-8")
        except UnicodeDecodeError:
            value = base64.b64encode(msg.payload).decode("ascii")
        with lock:
            state["received"] += 1
        if msg.topic == SYS_VERSION and state["version"] is None:
            state["version"] = value
            print(f"SYS: {SYS_VERSION} = {value}", flush=True)
        recorder.write("sys", topic=msg.topic, value=value)

    client.on_connect = on_connect
    client.on_subscribe = on_subscribe
    client.on_message = on_message
    client.connect(host, port, keepalive=60)
    client.loop_start()
    if not connected.wait(connect_timeout_s):
        client.loop_stop()
        raise ConnectionError(f"MQTT connect to {host}:{port} not acknowledged within {connect_timeout_s:.0f} s")
    if not subscribed.wait(connect_timeout_s):
        client.loop_stop()
        raise ConnectionError(f"SUBSCRIBE to $SYS/# not acknowledged within {connect_timeout_s:.0f} s")
    granted = state["granted"] or []
    if any(g.startswith("128") or "Unspecified" in g or "NotAuthorized" in g for g in granted):
        client.disconnect()
        client.loop_stop()
        raise ConnectionError(f"SUBSCRIBE to $SYS/# refused: granted={granted} (the measurement acl must grant 'topic read $SYS/#')")
    print(f"SUBSCRIBED: topic=$SYS/# granted={granted}", flush=True)
    start = clock.monotonic()
    while not stop_file.exists() and clock.monotonic() - start < limit_s:
        clock.sleep(poll_s)
    client.disconnect()
    client.loop_stop()
    summary = {"received": state["received"], "version": state["version"],
               "span_s": round(clock.monotonic() - start, 3)}
    recorder.write("end", **summary)
    return summary


def cmd_sysreader(args, client_factory=make_paho_client) -> int:
    password = password_from_env(args.password_env)
    client = client_factory(client_id=args.client_id, clean_session=True, manual_ack=False,
                            username=args.username, password=password,
                            tls=not args.no_tls, ca_cert=args.ca_cert)
    recorder = Recorder(args.record)
    try:
        summary = run_sysreader(client=client, recorder=recorder, host=args.host, port=args.port,
                                stop_file=Path(args.stop_file), limit_s=args.limit,
                                connect_timeout_s=args.connect_timeout)
    except (ConnectionError, OSError) as exc:
        print(f"STOP: sysreader: {exc}", file=sys.stderr)
        return EXIT_PREREQUISITE
    finally:
        recorder.close()
    print(f"sysreader end: received={summary['received']} version={summary['version']} span_s={summary['span_s']}")
    return EXIT_DONE


# --------------------------------------------------------------------------
# discard (P8)
# --------------------------------------------------------------------------

def run_discard(*, client, recorder: Recorder, host: str, port: int, connect_timeout_s: float) -> dict:
    connected = threading.Event()
    state = {"session_present": None, "reason": None}

    def on_connect(c, userdata, flags, reason_code, properties=None):
        sp = getattr(flags, "session_present", None)
        state["session_present"] = bool(sp) if sp is not None else None
        state["reason"] = _reason_text(reason_code)
        if not _is_failure(reason_code):
            connected.set()

    client.on_connect = on_connect
    client.connect(host, port, keepalive=60)
    client.loop_start()
    ok = connected.wait(connect_timeout_s)
    client.disconnect()
    client.loop_stop()
    recorder.write("discard", client_id=HOLD_CLIENT_ID, connected=ok,
                   session_present=state["session_present"], reason=state["reason"])
    if not ok:
        raise ConnectionError(f"MQTT connect to {host}:{port} not acknowledged within {connect_timeout_s:.0f} s")
    return state


def cmd_discard(args, client_factory=make_paho_client) -> int:
    password = password_from_env(args.password_env)
    client = client_factory(client_id=args.client_id, clean_session=True, manual_ack=False,
                            username=args.username, password=password,
                            tls=not args.no_tls, ca_cert=args.ca_cert)
    recorder = Recorder(args.record)
    try:
        state = run_discard(client=client, recorder=recorder, host=args.host, port=args.port,
                            connect_timeout_s=args.connect_timeout)
    except (ConnectionError, OSError) as exc:
        print(f"STOP: discard: {exc}", file=sys.stderr)
        return EXIT_PREREQUISITE
    finally:
        recorder.close()
    # A clean-session connect to a client id that held a persistent session
    # answers session_present=0 (MQTT 3.1.1, 3.2.2.2): nothing is left to resume.
    print(f"discarded: client_id={args.client_id} session_present={state['session_present']} reason={state['reason']}")
    return EXIT_DONE


# --------------------------------------------------------------------------
# verdict
# --------------------------------------------------------------------------

def _load_phases(path) -> dict[str, dict]:
    phases: dict[str, dict] = {}
    for rec in read_jsonl(path):
        name = rec.get("phase")
        if not name:
            continue
        p = phases.setdefault(name, {})
        p.update({k: v for k, v in rec.items() if k != "phase"})
    return phases


def _phase_epoch(phases: dict, name: str, edge: str) -> float | None:
    p = phases.get(name)
    if not p:
        return None
    key = f"{edge}_utc"
    if key in p and p[key]:
        try:
            return parse_utc(p[key])
        except ValueError:
            return None
    return None


def _sys_series(sys_records: list[dict], topic: str) -> list[tuple[float, str]]:
    out = []
    for r in sys_records:
        if r.get("event") == "sys" and r.get("topic") == topic:
            try:
                out.append((parse_utc(r["t_utc"]), str(r.get("value"))))
            except (KeyError, ValueError):
                continue
    return out


def _last_before(series: list[tuple[float, str]], t: float | None):
    """The last value at or before ``t`` (or the last value at all)."""
    if not series:
        return None
    if t is None:
        return series[-1][1]
    chosen = None
    for ts, v in series:
        if ts <= t + 0.5:
            chosen = v
        else:
            break
    return chosen


def _int(value) -> int | None:
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return None


def _read_recorder_csv(path) -> list[dict]:
    rows = []
    with open(path, encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(line for line in fh if not line.startswith("#"))
        for row in reader:
            rows.append(row)
    return rows


def _first_copies_in_order(deliveries: list[dict]) -> tuple[dict[str, dict], list[dict]]:
    """First delivery of each message_id, in receive order, and the later copies."""
    first: dict[str, dict] = {}
    later: list[dict] = []
    for d in deliveries:
        mid = d.get("message_id")
        if mid is None:
            continue
        if mid in first:
            later.append(d)
        else:
            first[mid] = d
    return first, later


def _per_device_order_breaks(first_copies: dict[str, dict]) -> list[dict]:
    """Devices whose first copies, in receive order, are not in ascending seq."""
    last_seq: dict[str, int] = {}
    breaks = []
    for mid, d in first_copies.items():
        dev, seq = d.get("device_uuid"), d.get("seq")
        if dev is None or seq is None:
            continue
        prev = last_seq.get(dev)
        if prev is not None and seq < prev:
            breaks.append({"device_uuid": dev, "message_id": mid, "seq": seq, "after_seq": prev})
        last_seq[dev] = max(prev, seq) if prev is not None else seq
    return breaks


def compute_verdict(*, params: dict, phases: dict, broker_log: list[str],
                    publish_p2: list[dict], publish_p5: list[dict],
                    hold_p1: list[dict], hold_p7: list[dict],
                    sys_records: list[dict], recorder_rows: list[dict],
                    guest_offset_s: float = 0.0) -> dict:
    """Apply the design's rules to the records. Pure: no I/O."""
    W = int(params.get("W", 4999))
    Q = int(params.get("Q", 1000))
    A = int(params.get("A", 4999))
    B = int(params.get("B", 1100))
    memory_max_expected = int(params.get("memory_max", 134217728))
    gap_limit_s = float(params.get("recorder_gap_limit_s", 5.0))

    supports: dict[str, bool | None] = {}
    refutes: dict[str, bool | None] = {}
    inconclusive: list[str] = []
    figures: dict = {}
    notes: list[str] = []

    p2_pub = [r for r in publish_p2 if r.get("event") == "published"]
    p5_pub = [r for r in publish_p5 if r.get("event") == "published"]
    p2_ids = [r["message_id"] for r in p2_pub]
    p5_ids = [r["message_id"] for r in p5_pub]
    p2_set = set(p2_ids)
    p5_set = set(p5_ids)
    d1 = [r for r in hold_p1 if r.get("event") == "delivery"]
    d7 = [r for r in hold_p7 if r.get("event") == "delivery"]
    end_p2 = _phase_epoch(phases, "P2", "end")
    end_p3 = _phase_epoch(phases, "P3", "end")
    end_p4 = _phase_epoch(phases, "P4", "end")
    end_p5 = _phase_epoch(phases, "P5", "end")
    end_p6 = _phase_epoch(phases, "P6", "end")
    end_p1 = _phase_epoch(phases, "P1", "end")
    start_p2 = _phase_epoch(phases, "P2", "start")
    start_p7 = _phase_epoch(phases, "P7", "start")
    end_p7 = _phase_epoch(phases, "P7", "end")
    start_p0 = _phase_epoch(phases, "P0", "start")

    # --- the publisher's exact counts (inconclusive otherwise) --------------
    p2_end = next((r for r in publish_p2 if r.get("event") == "end"), None)
    p5_end = next((r for r in publish_p5 if r.get("event") == "end"), None)
    if len(p2_pub) != A or not p2_end or p2_end.get("unacked", 1) != 0 or len(p2_set) != A:
        inconclusive.append(f"the publisher did not publish and get acknowledged exactly A={A} messages in P2 "
                            f"({len(p2_pub)} published, {len(p2_set)} distinct, unacked={p2_end.get('unacked') if p2_end else 'no end record'})")
    if len(p5_pub) != B or not p5_end or p5_end.get("unacked", 1) != 0 or len(p5_set) != B:
        inconclusive.append(f"the publisher did not publish and get acknowledged exactly B={B} messages in P5 "
                            f"({len(p5_pub)} published, {len(p5_set)} distinct, unacked={p5_end.get('unacked') if p5_end else 'no end record'})")

    # --- $SYS -------------------------------------------------------------------
    store = _sys_series(sys_records, SYS_STORE)
    inflight = _sys_series(sys_records, SYS_INFLIGHT)
    dropped = _sys_series(sys_records, SYS_DROPPED)
    version = _sys_series(sys_records, SYS_VERSION)
    connected = _sys_series(sys_records, SYS_CONNECTED)
    disconnected = _sys_series(sys_records, SYS_DISCONNECTED)
    figures["broker_version"] = version[0][1] if version else None
    if not store or not dropped:
        inconclusive.append("$SYS could not be read: no store/messages/count or publish/messages/dropped values were recorded")
    store_p0 = _int(_last_before(store, start_p2)) if start_p2 else (_int(store[0][1]) if store else None)
    store_end_p2 = _int(_last_before(store, end_p2))
    store_end_p3 = _int(_last_before(store, end_p3))
    store_end_p4 = _int(_last_before(store, end_p4))
    store_end_p6 = _int(_last_before(store, end_p6))
    store_end_p7 = _int(_last_before(store, end_p7))
    dropped_end_p4 = _int(_last_before(dropped, end_p4))
    dropped_end_p6 = _int(_last_before(dropped, end_p6))
    dropped_final = _int(dropped[-1][1]) if dropped else None
    inflight_max_p2p3 = None
    for ts, v in inflight:
        if (start_p2 is None or ts >= start_p2 - 0.5) and (end_p3 is None or ts <= end_p3 + 0.5):
            iv = _int(v)
            if iv is not None and (inflight_max_p2p3 is None or iv > inflight_max_p2p3):
                inflight_max_p2p3 = iv
    figures.update({
        "store_p0": store_p0, "store_end_p2": store_end_p2, "store_end_p3": store_end_p3,
        "store_end_p4": store_end_p4, "store_end_p6": store_end_p6, "store_end_p7": store_end_p7,
        "dropped_end_p4": dropped_end_p4, "dropped_end_p6": dropped_end_p6, "dropped_final": dropped_final,
        "inflight_max_p2_p3": inflight_max_p2p3,
        "clients_connected_last": _int(connected[-1][1]) if connected else None,
        "clients_disconnected_end_p4": _int(_last_before(disconnected, end_p4)),
    })
    # any drop before the end of P4 is read against the P0 baseline of the counter
    dropped_p0 = _int(_last_before(dropped, start_p2)) if start_p2 else (_int(dropped[0][1]) if dropped else None)
    figures["dropped_p0"] = dropped_p0
    drops_by_p4 = (dropped_end_p4 - dropped_p0) if (dropped_end_p4 is not None and dropped_p0 is not None) else None
    figures["drops_through_p4"] = drops_by_p4

    # --- S1: the broker started with the added lines and logged no error ------
    started = any("mosquitto version" in ln and "starting" in ln for ln in broker_log)
    # Mosquitto reports a configuration it refuses as 'Error: ...' (an unknown
    # variable, an invalid value) and exits; a broker that started and logs no
    # such line accepted the five added lines.
    config_errors = [ln.strip() for ln in broker_log if "Error" in ln or "Unknown configuration variable" in ln]
    supports["S1"] = started and not config_errors
    refutes["R1"] = (not started) or bool(config_errors)
    figures["broker_log_started"] = started
    figures["broker_log_error_lines"] = config_errors[:20]

    # --- S2 / R2: the window reached W ----------------------------------------
    d1_first, d1_later = _first_copies_in_order(d1)
    d1_distinct = len(d1_first)
    d1_dup_before_kill = sum(1 for d in d1 if d.get("dup"))
    d1_unknown = [d["message_id"] for d in d1_first.values() if d["message_id"] not in p2_set][:10]
    # The window reached W: A distinct deliveries were held by the end of P3,
    # every one of them a P2 message. $SYS's inflight peak is a figure beside
    # it, not a second condition: it is sampled every sys_interval only.
    supports["S2"] = d1_distinct >= A and not d1_unknown
    refutes["R2"] = d1_distinct < A
    figures.update({"p1_p3_distinct_deliveries": d1_distinct, "p1_p3_deliveries": len(d1),
                    "p1_p3_dup_deliveries": d1_dup_before_kill, "p1_p3_unknown_ids": d1_unknown,
                    "p1_p3_later_copies": len(d1_later)})
    if d1_unknown:
        notes.append("deliveries in P1-P3 carried message_ids the publisher did not publish in P2")

    # --- S3 / R3: no drop while held <= W; every first-4999 id redelivered in P7 --
    d7_first, d7_later = _first_copies_in_order(d7)
    missing_p2_in_p7 = [m for m in p2_ids if m not in d7_first]
    supports["S3"] = (drops_by_p4 == 0) and not missing_p2_in_p7
    refutes["R3"] = (drops_by_p4 is not None and drops_by_p4 > 0) or (bool(p2_ids) and bool(missing_p2_in_p7) and bool(d7))
    figures.update({"p7_deliveries": len(d7), "p7_distinct": len(d7_first), "p7_later_copies": len(d7_later),
                    "p2_ids_missing_in_p7": len(missing_p2_in_p7),
                    "p7_dup_flag_on_first_copies_of_p2": sum(1 for m in p2_ids if m in d7_first and d7_first[m].get("dup")),
                    "p7_session_present": next((r.get("session_present") for r in hold_p7 if r.get("event") == "connect"), None)})

    # --- S4 / R4: memory held, no OOM, no restart ----------------------------
    def _row_int(row, key):
        return _int(row.get(key))

    ooms = 0
    oom_kills = 0
    restarts_max = 0
    not_running = 0
    peak = None
    peak_row = None
    mem_max_seen = set()
    gaps = []
    prev_epoch = None
    p2_epoch = (start_p2 - guest_offset_s) if start_p2 else None
    p7_end_epoch = (end_p7 - guest_offset_s) if end_p7 else None
    for row in recorder_rows:
        ep = _row_int(row, "epoch")
        o, ok_, rs = _row_int(row, "ev_oom"), _row_int(row, "ev_oom_kill"), _row_int(row, "restarts")
        ooms = max(ooms, o or 0)
        oom_kills = max(oom_kills, ok_ or 0)
        restarts_max = max(restarts_max, rs or 0)
        if row.get("state") not in (None, "", "running", "?"):
            not_running += 1
        mm = _row_int(row, "mem_max")
        if mm is not None:
            mem_max_seen.add(mm)
        cur = _row_int(row, "mem_peak")
        if cur is None:
            cur = _row_int(row, "mem_current")
        if cur is not None and (peak is None or cur > peak):
            peak, peak_row = cur, row
        if ep is not None:
            if prev_epoch is not None and p2_epoch is not None and p7_end_epoch is not None \
                    and ep >= p2_epoch and prev_epoch <= p7_end_epoch and ep - prev_epoch > gap_limit_s:
                gaps.append((prev_epoch, ep))
            prev_epoch = ep
    if not recorder_rows:
        inconclusive.append("the guest recorder produced no rows")
    if gaps:
        inconclusive.append(f"the guest recorder has {len(gaps)} gap(s) over {gap_limit_s:.0f} s inside P2-P7 (first: {gaps[0]})")
    mem_ok = ooms == 0 and oom_kills == 0 and restarts_max == 0 and not_running == 0
    supports["S4"] = bool(recorder_rows) and mem_ok
    refutes["R4"] = ooms > 0 or oom_kills > 0 or restarts_max > 0
    figures.update({
        "memory_max_values": sorted(mem_max_seen), "memory_max_expected": memory_max_expected,
        "memory_max_as_expected": mem_max_seen == {memory_max_expected} if mem_max_seen else None,
        "oom_events": ooms, "oom_kill_events": oom_kills, "container_restarts": restarts_max,
        "samples_not_running": not_running, "recorder_rows": len(recorder_rows), "recorder_gaps": len(gaps),
        "memory_peak_bytes": peak,
        "memory_peak_margin_bytes": (memory_max_expected - peak) if peak is not None else None,
        "memory_peak_anon": _row_int(peak_row, "anon") if peak_row else None,
        "memory_peak_file": _row_int(peak_row, "file") if peak_row else None,
    })

    def _anon_at(t_host: float | None):
        if t_host is None:
            return None
        target = t_host - guest_offset_s
        best = None
        for row in recorder_rows:
            ep = _row_int(row, "epoch")
            if ep is not None and ep <= target + 0.5:
                best = row
            elif ep is not None and ep > target + 0.5:
                break
        return _row_int(best, "anon") if best else None

    anon_p1, anon_p3, anon_p6 = _anon_at(end_p1), _anon_at(end_p3), _anon_at(end_p6)
    figures.update({"anon_end_p1": anon_p1, "anon_end_p3": anon_p3, "anon_end_p6": anon_p6})
    if anon_p1 is not None and anon_p3 is not None:
        figures["anon_per_message_p2_bytes"] = round((anon_p3 - anon_p1) / A, 1)
    if anon_p3 is not None and anon_p6 is not None and store_end_p6 is not None and store_end_p4 is not None \
            and store_end_p6 > store_end_p4:
        figures["anon_per_message_p5_bytes"] = round((anon_p6 - anon_p3) / (store_end_p6 - store_end_p4), 1)

    # --- P5 discrimination (recorded, a sizing finding) ------------------------
    drops_p5 = (dropped_end_p6 - dropped_end_p4) if (dropped_end_p6 is not None and dropped_end_p4 is not None) else None
    figures["drops_in_p5_p6"] = drops_p5
    if store_end_p6 == A + Q and drops_p5 == B - Q:
        figures["queue_accounting"] = "above the held in-flight messages (store W+Q, dropped B-Q)"
    elif store_end_p6 == A and drops_p5 == B:
        figures["queue_accounting"] = "in total while the client is offline (store W, dropped B)"
    else:
        figures["queue_accounting"] = f"other, recorded as observed (store {store_end_p6}, dropped in P5-P6 {drops_p5})"

    # --- S5 / R5 / R6: the session kept, everything held redelivered, in order --
    held_expected = store_end_p6
    redelivered_distinct = len(d7_first)
    refutes["R5"] = held_expected is not None and bool(d7) and redelivered_distinct < held_expected
    breaks = _per_device_order_breaks(d7_first)
    refutes["R6"] = bool(breaks)
    store_back = (store_end_p7 is not None and store_p0 is not None and store_end_p7 <= store_p0)
    supports["S5"] = held_expected is not None and redelivered_distinct >= held_expected and not breaks and store_back
    figures.update({"held_at_end_p6": held_expected, "p7_redelivered_distinct": redelivered_distinct,
                    "p7_order_breaks": breaks[:10], "p7_order_breaks_count": len(breaks),
                    "store_back_to_baseline": store_back})
    if not store_back and held_expected is not None and redelivered_distinct >= held_expected:
        notes.append("P7 redelivered everything held but the store did not return to its P0 value within P7")

    # --- the disconnection line in P4 -----------------------------------------
    disc_lines = [ln.strip() for ln in broker_log if HOLD_CLIENT_ID in ln and
                  ("closed its connection" in ln or "disconnect" in ln.lower() or "Socket error" in ln)]
    figures["p4_disconnection_lines"] = disc_lines[:5]
    p4 = phases.get("P4", {})
    if not p4.get("disconnection_seen") and not disc_lines:
        inconclusive.append("the broker's disconnection line for egw-probe-hold never appeared in P4")
    if p4.get("limit_reached"):
        inconclusive.append("P4 reached its limit before the disconnection line")
    if phases.get("P7", {}).get("limit_reached"):
        inconclusive.append("P7 reached its limit")
    for name, p in phases.items():
        if p.get("stop_rule_reached"):
            inconclusive.append(f"a stop rule was reached in {name}: {p.get('stop_rule_reached')}")
    if phases.get("tunnel_failed"):
        inconclusive.append("the tunnel failed")

    # --- the answer -------------------------------------------------------------
    refuted = [k for k, v in refutes.items() if v]
    all_support = all(supports.get(k) for k in ("S1", "S2", "S3", "S4", "S5"))
    if refuted:
        result = "refutes"
    elif inconclusive:
        result = "inconclusive"
    elif all_support:
        result = "supports"
    else:
        result = "inconclusive"
        inconclusive.append("not every support condition holds and no refuting result was observed: "
                            + ", ".join(k for k, v in supports.items() if not v))
    return {"result": result, "supports": supports, "refutes": refutes, "refuted": refuted,
            "inconclusive": inconclusive, "figures": figures, "notes": notes,
            "params": {"W": W, "Q": Q, "A": A, "B": B, "memory_max": memory_max_expected},
            "rule": "supports only if every one of S1-S5 holds; any of R1-R6 refutes option 5 as configured; "
                    "an inconclusive run is not passing (ADR 0011, C3; gate item 1, section 7)"}


def cmd_verdict(args) -> int:
    def _opt(path):
        return read_jsonl(path) if path and Path(path).exists() else []

    params = json.loads(Path(args.params).read_text(encoding="utf-8")) if args.params else {}
    phases = _load_phases(args.phases) if args.phases and Path(args.phases).exists() else {}
    broker_log = Path(args.broker_log).read_text(encoding="utf-8", errors="replace").splitlines() \
        if args.broker_log and Path(args.broker_log).exists() else []
    rows = _read_recorder_csv(args.recorder) if args.recorder and Path(args.recorder).exists() else []
    verdict = compute_verdict(
        params=params, phases=phases, broker_log=broker_log,
        publish_p2=_opt(args.publish_p2), publish_p5=_opt(args.publish_p5),
        hold_p1=_opt(args.hold_p1), hold_p7=_opt(args.hold_p7),
        sys_records=_opt(args.sys), recorder_rows=rows,
        guest_offset_s=float(params.get("guest_offset_s", 0.0)),
    )
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(verdict, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"VERDICT: {verdict['result']}")
    print("supports: " + " ".join(f"{k}={'yes' if v else 'no'}" for k, v in verdict["supports"].items()))
    print("refutes: " + " ".join(f"{k}={'yes' if v else 'no'}" for k, v in verdict["refutes"].items()))
    for reason in verdict["inconclusive"]:
        print(f"inconclusive: {reason}")
    for note in verdict["notes"]:
        print(f"note: {note}")
    f = verdict["figures"]
    print(f"figures: store p0={f.get('store_p0')} end_p2={f.get('store_end_p2')} end_p6={f.get('store_end_p6')} "
          f"end_p7={f.get('store_end_p7')}; dropped through_p4={f.get('drops_through_p4')} in_p5_p6={f.get('drops_in_p5_p6')}; "
          f"inflight max P2-P3={f.get('inflight_max_p2_p3')}; P7 distinct={f.get('p7_redelivered_distinct')} "
          f"order breaks={f.get('p7_order_breaks_count')}; memory peak={f.get('memory_peak_bytes')} "
          f"margin={f.get('memory_peak_margin_bytes')} anon/msg P2={f.get('anon_per_message_p2_bytes')}; "
          f"queue accounting: {f.get('queue_accounting')}")
    return {"supports": EXIT_DONE, "refutes": EXIT_NEGATIVE, "inconclusive": EXIT_INCONCLUSIVE}[verdict["result"]]


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------

def _add_broker_args(p: argparse.ArgumentParser, *, username: str, client_id: str, password_env: str) -> None:
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=8883)
    p.add_argument("--username", default=username)
    p.add_argument("--password-env", default=password_env,
                   help="name of the environment variable that holds the password (never the password itself)")
    p.add_argument("--client-id", default=client_id)
    p.add_argument("--ca-cert", default=None)
    p.add_argument("--no-tls", action="store_true", help="plain TCP (local functional checks only)")
    p.add_argument("--connect-timeout", type=float, default=30.0)
    p.add_argument("--record", required=True, help="JSON Lines record this client appends to")


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="broker_hold", description=__doc__.split("\n\n")[0])
    sub = p.add_subparsers(dest="command", required=True)

    s = sub.add_parser("generate", help="regenerate the real payloads in nominal order")
    s.add_argument("--seed", type=int, default=42)
    s.add_argument("--run-id", default="brkhold-r01", help="11 characters like nominal-r01, so sizes stay 273-320 B")
    s.add_argument("--egw-id", default="egw-01")
    s.add_argument("--count", type=int, default=6099)
    s.add_argument("--rate", type=float, default=NOMINAL_RATE_HZ)
    s.add_argument("--work-dir", required=True, help="where the simulator's own provenance is written")
    s.add_argument("--out", required=True)
    s.set_defaults(func=cmd_generate)

    s = sub.add_parser("publish", help="publish a slice of the generated messages at the nominal cadence")
    s.add_argument("--messages", required=True)
    s.add_argument("--first", type=int, required=True)
    s.add_argument("--count", type=int, required=True)
    s.add_argument("--rate", type=float, default=NOMINAL_RATE_HZ)
    s.add_argument("--drain", type=float, default=60.0, help="seconds to wait for the last acknowledgements")
    _add_broker_args(s, username="egw-simulator", client_id=PUB_CLIENT_ID, password_env="MOSQUITTO_SIMULATOR_PASSWORD")
    s.set_defaults(func=cmd_publish)

    s = sub.add_parser("hold", help="the holding subscriber (persistent session, manual acknowledgement)")
    s.add_argument("--topic", default=TELEMETRY_FILTER)
    s.add_argument("--ack", action="store_true", help="acknowledge each delivery after recording it (phase P7)")
    s.add_argument("--stop-file", default=None)
    s.add_argument("--expect", type=int, default=None, help="end once this many deliveries arrived and --idle passed")
    s.add_argument("--idle", type=float, default=30.0)
    s.add_argument("--limit", type=float, default=3600.0)
    _add_broker_args(s, username="egw-controller", client_id=HOLD_CLIENT_ID, password_env="MOSQUITTO_CONTROLLER_PASSWORD")
    s.set_defaults(func=cmd_hold)

    s = sub.add_parser("sysreader", help="record every $SYS value")
    s.add_argument("--stop-file", required=True)
    s.add_argument("--limit", type=float, default=3600.0)
    _add_broker_args(s, username="egw-controller", client_id=SYS_CLIENT_ID, password_env="MOSQUITTO_CONTROLLER_PASSWORD")
    s.set_defaults(func=cmd_sysreader)

    s = sub.add_parser("discard", help="end the persistent session of the holding subscriber")
    _add_broker_args(s, username="egw-controller", client_id=HOLD_CLIENT_ID, password_env="MOSQUITTO_CONTROLLER_PASSWORD")
    s.set_defaults(func=cmd_discard)

    s = sub.add_parser("verdict", help="apply S1-S5, R1-R6 and the inconclusive rules to the records")
    s.add_argument("--params", default=None, help="JSON with W, Q, A, B, memory_max, guest_offset_s")
    s.add_argument("--phases", required=True)
    s.add_argument("--broker-log", required=True)
    s.add_argument("--publish-p2", required=True)
    s.add_argument("--publish-p5", required=True)
    s.add_argument("--hold-p1", required=True)
    s.add_argument("--hold-p7", required=True)
    s.add_argument("--sys", required=True)
    s.add_argument("--recorder", required=True)
    s.add_argument("--out", required=True)
    s.set_defaults(func=cmd_verdict)
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return int(args.func(args))
    except SystemExit as exc:  # our own prerequisite messages
        if isinstance(exc.code, str):
            print(f"STOP: {exc.code}", file=sys.stderr)
            return EXIT_PREREQUISITE
        raise
    except (FileNotFoundError, ValueError) as exc:
        print(f"STOP: {exc}", file=sys.stderr)
        return EXIT_PREREQUISITE


if __name__ == "__main__":
    signal.signal(signal.SIGTERM, lambda *_: sys.exit(143))
    sys.exit(main())
