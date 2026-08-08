"""Runner and output tests: paced loop, topics, manifest, sent_events.

Uses ``InMemoryPublisher`` and an injectable fake clock, so no broker and no
real sleeping are needed (plan section 5.6; CONTRACTS.md sections 1 and 7).
"""

import json
import re
import uuid

import pytest

from egw_simulator import __version__
from egw_simulator.devices import DEVICE_TYPES, make_devices, split_rate
from egw_simulator.envelope import EGW_UUID_NAMESPACE
from egw_simulator.output import SENT_EVENT_FIELDS, SentEventsWriter
from egw_simulator.publisher import InMemoryPublisher, PublishResult
from egw_simulator.runner import RunConfig, run, scheduled_times
from egw_simulator.scenarios import (
    DROPOUT_SCOPE_NOTE,
    InvalidInjector,
    dropout_windows,
    window_index,
)
from egw_simulator.validation import SchemaValidator

TS_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z$")


class FakeClock:
    """Monotonic fake: sleep() advances time instantly."""

    def __init__(self) -> None:
        self.t = 0.0

    def monotonic(self) -> float:
        return self.t

    def monotonic_ns(self) -> int:
        return int(self.t * 1e9)

    def sleep(self, seconds: float) -> None:
        assert seconds >= 0
        self.t += seconds


class DelayedAckPublisher:
    """Fake broker whose PUBACK arrives ``ack_delay_s`` after each publish.

    Mirrors the paho semantics on the injected fake clock: ``publish()``
    waits for the acknowledgement at most ``wait_budget_s``; if the ack
    delay fits the budget the puback is captured, otherwise the full budget
    is consumed (as a real timed wait would) and the puback is ``None``.
    """

    def __init__(self, clock: FakeClock, ack_delay_s: float) -> None:
        self.clock = clock
        self.ack_delay_s = ack_delay_s
        self.wait_budgets: list[float] = []
        self.drain_calls: list[float] = []
        self.connected = False

    def connect(self) -> None:
        self.connected = True

    def publish(self, topic, payload, *, wait_budget_s: float = 0.0):
        publish_ns = self.clock.monotonic_ns()
        self.wait_budgets.append(wait_budget_s)
        if wait_budget_s >= self.ack_delay_s:
            self.clock.sleep(self.ack_delay_s)
            return PublishResult(publish_ns, self.clock.monotonic_ns())
        self.clock.sleep(wait_budget_s)
        return PublishResult(publish_ns, None)

    def drain(self, timeout_s: float = 60.0) -> bool:
        self.drain_calls.append(timeout_s)
        return True

    def close(self) -> None:
        self.connected = False


@pytest.fixture(scope="module")
def validator() -> SchemaValidator:
    return SchemaValidator()


def make_config(tmp_path, **overrides) -> RunConfig:
    defaults = dict(
        scenario="smoke",
        seed=7,
        run_id="test-smoke-7",
        egw_id="egw-01",
        duration_s=2.0,
        aggregate_rate_hz=11.2,
        qos=1,
        broker_host="localhost",
        broker_port=8883,
        tls=True,
        ca_cert=None,
        output_dir=tmp_path,
    )
    defaults.update(overrides)
    return RunConfig(**defaults)


def read_jsonl(path):
    with open(path, encoding="utf-8") as fh:
        return [json.loads(line) for line in fh if line.strip()]


def expected_event_count(rate_hz: float, duration_s: float) -> dict:
    rates = split_rate(rate_hz)
    return {t: len(scheduled_times(rates[t], duration_s)) for t in DEVICE_TYPES}


# ---------------------------------------------------------------- smoke run

def test_smoke_run_topics_payloads_and_outputs(tmp_path, validator):
    config = make_config(tmp_path)
    publisher = InMemoryPublisher()
    result = run(config, publisher, clock=FakeClock(), validator=validator)

    expected = expected_event_count(11.2, 2.0)
    assert result.completed is True
    assert result.sent == sum(expected.values()) == len(publisher.records)
    assert result.intended_invalid == 0
    assert result.buffered_dropout == 0
    assert result.dropout_disconnects == 0
    # Non-dropout scenarios never touch the connection mid-run.
    assert publisher.disconnect_calls == 0
    assert publisher.reconnect_calls == 0

    devices = {d.device_uuid: d.device_type for d in make_devices(7)}
    seqs_per_device: dict[str, list[int]] = {u: [] for u in devices}
    for topic, payload_text, _ns in publisher.records:
        payload = json.loads(payload_text)
        device_uuid = payload["device_uuid"]
        # Exact topic layout (CONTRACTS.md section 1).
        assert topic == f"c2dt/egw-01/{device_uuid}/telemetry"
        assert payload["run_id"] == "test-smoke-7"
        assert payload["egw_id"] == "egw-01"
        assert payload["schema_version"] == "1.0.0"
        assert payload["device_type"] == devices[device_uuid]
        assert TS_RE.fullmatch(payload["ts"])
        expected_mid = uuid.uuid5(
            EGW_UUID_NAMESPACE,
            f"{payload['run_id']}:{device_uuid}:{payload['seq']}",
        )
        assert payload["message_id"] == str(expected_mid)
        validator.validate(payload)
        seqs_per_device[device_uuid].append(payload["seq"])

    # Per-device seq counters: 0..n-1 in publish order, per contract counts.
    for device_uuid, seqs in seqs_per_device.items():
        assert seqs == list(range(expected[devices[device_uuid]]))

    # sent_events.jsonl: one record per publish, exact field set and order.
    lines = read_jsonl(result.sent_events_path)
    assert len(lines) == result.sent
    for line in lines:
        assert list(line) == list(SENT_EVENT_FIELDS)
        assert line["run_id"] == "test-smoke-7"
        assert line["intended_invalid"] is False
        assert isinstance(line["publish_monotonic_ns"], int)
        assert isinstance(line["puback_monotonic_ns"], int)
    assert [line["message_id"] for line in lines] == [
        json.loads(p)["message_id"] for _, p, _ in publisher.records
    ]


def test_smoke_run_manifest_contents(tmp_path):
    config = make_config(tmp_path)
    result = run(config, InMemoryPublisher(), clock=FakeClock())

    raw = result.manifest_path.read_text(encoding="utf-8")
    assert "password" not in raw.lower()
    assert "username" not in raw.lower()
    manifest = json.loads(raw)

    assert manifest["protocol_version"] == "1.0"
    assert manifest["simulator_version"] == __version__
    assert manifest["scenario"] == "smoke"
    assert manifest["seed"] == 7
    assert manifest["run_id"] == "test-smoke-7"
    assert manifest["egw_id"] == "egw-01"
    assert manifest["devices"] == [
        {"device_type": d.device_type, "device_uuid": d.device_uuid}
        for d in make_devices(7)
    ]
    assert manifest["rates_hz"]["aggregate"] == pytest.approx(11.2)
    assert manifest["rates_hz"]["per_device"]["smartwatch"] == pytest.approx(1.0)
    assert manifest["rates_hz"]["per_device"]["smart_ring"] == pytest.approx(0.2)
    assert manifest["rates_hz"]["per_device"]["smart_clothing"] == pytest.approx(10.0)
    assert manifest["duration_s"] == 2.0
    assert manifest["qos"] == 1
    assert manifest["broker"] == {
        "host": "localhost",
        "port": 8883,
        "tls": True,
        "ca_cert": None,
    }
    assert manifest["git_commit"] is None or isinstance(manifest["git_commit"], str)
    assert TS_RE.fullmatch(manifest["started_utc"])
    assert TS_RE.fullmatch(manifest["finished_utc"])
    assert manifest["completed"] is True
    assert manifest["totals"] == {
        "sent": result.sent,
        "intended_invalid": 0,
        "buffered_dropout": 0,
        "dropout_disconnects": 0,
    }
    assert manifest["note"] is None  # scope note is dropout-reconnect only


@pytest.mark.parametrize("scenario", ["nominal", "smoke"])
def test_non_dropout_scenarios_never_touch_the_connection(tmp_path, scenario):
    """nominal/smoke are unaffected by the dropout machinery.

    No disconnect/reconnect call, no buffering: every event is published
    live, in schedule order, on the single connection the CLI opened.
    """
    config = make_config(
        tmp_path, scenario=scenario, run_id=f"test-{scenario}-conn", duration_s=2.0
    )
    publisher = InMemoryPublisher()
    publisher.connect()
    result = run(config, publisher, clock=FakeClock())
    assert result.completed is True
    assert result.buffered_dropout == 0
    assert result.dropout_disconnects == 0
    assert publisher.lifecycle == ["connect"]  # no disconnect/reconnect/close
    assert publisher.publish_connected == [True] * len(publisher.records)


def test_runner_is_deterministic_across_runs(tmp_path):
    config_a = make_config(tmp_path / "a")
    config_b = make_config(tmp_path / "b")
    pub_a, pub_b = InMemoryPublisher(), InMemoryPublisher()
    run(config_a, pub_a, clock=FakeClock())
    run(config_b, pub_b, clock=FakeClock())

    def strip_ts(payloads):
        return [{k: v for k, v in p.items() if k != "ts"} for p in payloads]

    assert strip_ts(pub_a.decoded_payloads()) == strip_ts(pub_b.decoded_payloads())
    assert [t for t, _, _ in pub_a.records] == [t for t, _, _ in pub_b.records]


# ------------------------------------------------------- invalid-payload run

def test_invalid_payload_run_marks_exactly_the_injected_events(tmp_path, validator):
    seed = 11
    config = make_config(
        tmp_path,
        scenario="invalid-payload",
        seed=seed,
        run_id="test-invalid-11",
        duration_s=4.0,
        aggregate_rate_hz=56.0,
    )
    publisher = InMemoryPublisher()
    result = run(config, publisher, clock=FakeClock())

    rates = split_rate(56.0)
    expected_flagged = set()
    for dev in make_devices(seed):
        injector = InvalidInjector(seed, dev.device_uuid)
        n_events = len(scheduled_times(rates[dev.device_type], 4.0))
        for seq in range(n_events):
            if injector.is_invalid(seq):
                expected_flagged.add((dev.device_uuid, seq))
    assert expected_flagged  # the scenario must actually inject something

    lines = read_jsonl(result.sent_events_path)
    flagged = {
        (line["device_uuid"], line["seq"]) for line in lines if line["intended_invalid"]
    }
    assert flagged == expected_flagged
    assert result.intended_invalid == len(expected_flagged)

    # Exactly the flagged events fail schema validation; all others pass.
    records_by_key = {}
    for _topic, payload_text, _ns in publisher.records:
        payload = json.loads(payload_text)
        records_by_key[(payload["device_uuid"], payload["seq"])] = payload
    assert set(records_by_key) == {(l["device_uuid"], l["seq"]) for l in lines}
    for key, payload in records_by_key.items():
        assert "intended_invalid" not in payload  # marker never in the payload
        assert validator.is_valid(payload) == (key not in expected_flagged)


# ----------------------------------------------------- dropout-reconnect run

def dropout_expectations(seed: int, rate_hz: float, duration: float):
    """Recompute the deterministic dropout bookkeeping used by the runner.

    Returns (windows, per-device scheduled counts, buffered (uuid, seq)
    set, number of windows containing at least one scheduled event).
    Windows are RUN-LEVEL (one shared MQTT connection), so a single
    ``dropout_windows(seed, duration)`` call covers all devices.
    """
    windows = dropout_windows(seed, duration)
    rates = split_rate(rate_hz)
    scheduled: dict[str, int] = {}
    buffered: set[tuple[str, int]] = set()
    windows_with_events: set[int] = set()
    for dev in make_devices(seed):
        times = scheduled_times(rates[dev.device_type], duration)
        scheduled[dev.device_uuid] = len(times)
        for seq, t in enumerate(times):
            w = window_index(t, windows)
            if w is not None:
                buffered.add((dev.device_uuid, seq))
                windows_with_events.add(w)
    return windows, scheduled, buffered, len(windows_with_events)


def test_dropout_run_buffers_window_events_and_flushes_in_order(tmp_path):
    """Real disconnect windows: buffer during, flush in order after.

    Covers the audit 7.3 / claim C10 semantics: every scheduled event is
    published exactly once (window events late, after the reconnect), seq
    stays strictly monotonic and gap-free, nothing is published while
    disconnected, and disconnect/reconnect run exactly once per window
    that contains at least one scheduled event.
    """
    seed = 5
    duration = 120.0  # two deterministic windows (one per 60 s)
    config = make_config(
        tmp_path,
        scenario="dropout-reconnect",
        seed=seed,
        run_id="test-dropout-5",
        duration_s=duration,
    )
    clock = FakeClock()
    publisher = InMemoryPublisher(clock=clock)
    publisher.connect()  # the CLI owns connect()/close() (publisher contract)
    result = run(config, publisher, clock=clock)

    windows, scheduled, buffered, n_active_windows = dropout_expectations(
        seed, 11.2, duration
    )
    assert len(windows) == 2
    assert buffered  # windows are >= 2 s; smart_clothing runs at 10 Hz

    # Every generated event is published exactly once: no skips, no dupes.
    lines = read_jsonl(result.sent_events_path)
    assert result.completed is True
    assert result.sent == sum(scheduled.values()) == len(lines)
    assert len({line["message_id"] for line in lines}) == len(lines)

    # Buffered accounting matches the deterministic window membership.
    assert result.buffered_dropout == len(buffered)
    assert result.dropout_disconnects == n_active_windows

    # No publish while disconnected: connection state at each publish.
    assert publisher.publish_connected == [True] * len(publisher.records)

    # disconnect/reconnect exactly once per window with scheduled events.
    assert publisher.disconnect_calls == n_active_windows
    assert publisher.reconnect_calls == n_active_windows
    # The runner itself never calls connect/close (the CLI owns those; the
    # single "connect" is the one issued above), and every disconnect is
    # followed by exactly one reconnect.
    assert publisher.lifecycle == (
        ["connect"] + ["disconnect", "reconnect"] * n_active_windows
    )

    # Flush preserves per-device seq order: strictly monotonic, gap-free
    # in actual PUBLISH order (live + flushed interleavings included).
    published: dict[str, list[int]] = {}
    for line in lines:
        published.setdefault(line["device_uuid"], []).append(line["seq"])
    for device_uuid, count in scheduled.items():
        assert published.get(device_uuid, []) == list(range(count))

    # Buffered events are published LATE: their publish instant lies at or
    # after the end of their window (never at the scheduled time), while
    # live events publish exactly on schedule under the fake clock.
    rates = split_rate(11.2)
    sched_time = {
        (dev.device_uuid, seq): t
        for dev in make_devices(seed)
        for seq, t in enumerate(
            scheduled_times(rates[dev.device_type], duration)
        )
    }
    for line in lines:
        key = (line["device_uuid"], line["seq"])
        t_sched_ns = int(sched_time[key] * 1e9)
        if key in buffered:
            w = window_index(sched_time[key], windows)
            flush_floor_ns = int(min(windows[w][1], duration) * 1e9)
            assert line["publish_monotonic_ns"] >= flush_floor_ns
            assert line["publish_monotonic_ns"] > t_sched_ns
        else:
            assert line["publish_monotonic_ns"] >= t_sched_ns

    # sent_events order matches publish order exactly.
    assert [line["message_id"] for line in lines] == [
        json.loads(p)["message_id"] for _, p, _ in publisher.records
    ]


def test_dropout_run_is_deterministic_per_seed(tmp_path):
    """Same seed => same windows => same buffered set and payloads."""
    config_a = make_config(
        tmp_path / "a",
        scenario="dropout-reconnect",
        seed=9,
        run_id="test-dropout-det",
        duration_s=60.0,
    )
    config_b = make_config(
        tmp_path / "b",
        scenario="dropout-reconnect",
        seed=9,
        run_id="test-dropout-det",
        duration_s=60.0,
    )
    pub_a, pub_b = InMemoryPublisher(), InMemoryPublisher()
    result_a = run(config_a, pub_a, clock=FakeClock())
    result_b = run(config_b, pub_b, clock=FakeClock())

    def strip_ts(payloads):
        return [{k: v for k, v in p.items() if k != "ts"} for p in payloads]

    # Identical publish order and payload content (except wall-clock ts).
    assert strip_ts(pub_a.decoded_payloads()) == strip_ts(pub_b.decoded_payloads())
    assert pub_a.lifecycle == pub_b.lifecycle
    assert result_a.sent == result_b.sent
    assert result_a.buffered_dropout == result_b.buffered_dropout > 0
    assert result_a.dropout_disconnects == result_b.dropout_disconnects > 0
    manifest_a = json.loads(result_a.manifest_path.read_text(encoding="utf-8"))
    manifest_b = json.loads(result_b.manifest_path.read_text(encoding="utf-8"))
    assert manifest_a["totals"] == manifest_b["totals"]


def test_dropout_manifest_records_buffered_redelivery_scope_note(tmp_path):
    """Manifest of dropout-reconnect states the real-disconnect semantics.

    The scenario performs a real client disconnect with device-side
    buffering and in-order flush on reconnect; broker-side/network-level
    faults remain test-harness territory. The harness reads this note for
    its dropout acceptance rule, so the text is asserted verbatim.
    """
    config = make_config(
        tmp_path,
        scenario="dropout-reconnect",
        run_id="test-dropout-note",
        duration_s=2.0,
    )
    result = run(config, InMemoryPublisher(), clock=FakeClock())
    manifest = json.loads(result.manifest_path.read_text(encoding="utf-8"))
    assert manifest["note"] == DROPOUT_SCOPE_NOTE
    assert "real client disconnect" in manifest["note"]
    assert "buffered" in manifest["note"]
    assert "published exactly once" in manifest["note"]
    assert "test-harness territory" in manifest["note"]


# ------------------------------------------------- best-effort puback capture

def test_delayed_acks_never_throttle_the_schedule(tmp_path):
    """CONTRACTS.md section 7 (v1.1): puback capture is best-effort.

    With a broker whose PUBACK takes 5 s and a high aggregate rate, the
    old blocking wait_for_publish would stretch the run to hours; the
    budgeted wait must keep the elapsed time at the nominal duration and
    record null pubacks.
    """
    clock = FakeClock()
    config = make_config(
        tmp_path,
        run_id="test-slow-acks",
        duration_s=2.0,
        aggregate_rate_hz=112.0,  # smart_clothing at 100 Hz
    )
    publisher = DelayedAckPublisher(clock, ack_delay_s=5.0)
    result = run(config, publisher, clock=clock)

    expected = expected_event_count(112.0, 2.0)
    assert result.completed is True
    assert result.sent == sum(expected.values())
    # Schedule not throttled: elapsed stays within the nominal duration.
    assert clock.t <= config.duration_s + 1e-6
    lines = read_jsonl(result.sent_events_path)
    assert len(lines) == result.sent
    assert all(line["puback_monotonic_ns"] is None for line in lines)
    # The wait budget never exceeds the gap to the next scheduled event.
    assert all(0.0 <= b <= 1.0 for b in publisher.wait_budgets)
    # End of run still performs the bounded drain for in-flight messages.
    assert publisher.drain_calls == [60.0]


def test_fast_acks_are_captured_within_the_budget(tmp_path):
    """At low rate with fast acks the puback fits the budget and is kept.

    Events whose budget is legitimately 0 (coincident schedule instants
    and the final event of the run) record null; every other event has a
    captured puback exactly ack_delay after its publish instant.
    """
    clock = FakeClock()
    ack_delay_s = 0.01
    config = make_config(
        tmp_path,
        run_id="test-fast-acks",
        duration_s=2.0,
        aggregate_rate_hz=11.2,
    )
    publisher = DelayedAckPublisher(clock, ack_delay_s=ack_delay_s)
    result = run(config, publisher, clock=clock)

    lines = read_jsonl(result.sent_events_path)
    assert len(lines) == result.sent
    captured = [l for l in lines if l["puback_monotonic_ns"] is not None]
    assert len(captured) >= int(0.8 * len(lines)) > 0
    for line in captured:
        delta_ns = line["puback_monotonic_ns"] - line["publish_monotonic_ns"]
        assert abs(delta_ns - ack_delay_s * 1e9) <= 1_000  # float rounding
    # Null pubacks happen exactly when the budget could not fit the ack.
    nulls = [
        line
        for line, budget in zip(lines, publisher.wait_budgets)
        if line["puback_monotonic_ns"] is None
    ]
    for line, budget in zip(lines, publisher.wait_budgets):
        assert (line["puback_monotonic_ns"] is None) == (budget < ack_delay_s)
    assert nulls  # coincident instants and the final event exist in this run
    assert publisher.drain_calls == [60.0]


def test_drain_can_be_disabled(tmp_path):
    clock = FakeClock()
    publisher = DelayedAckPublisher(clock, ack_delay_s=5.0)
    config = make_config(tmp_path, run_id="test-no-drain", duration_s=1.0)
    run(config, publisher, clock=clock, drain_timeout_s=0.0)
    assert publisher.drain_calls == []


class _FakeMessageInfo:
    """Stands in for paho's MQTTMessageInfo in drain/prune unit tests."""

    def __init__(self, published=False, exc: Exception | None = None) -> None:
        self._published = published
        self._exc = exc

    def is_published(self) -> bool:
        if self._exc is not None:
            raise self._exc
        return self._published

    def wait_for_publish(self, timeout=None) -> None:
        if self._exc is not None:
            raise self._exc
        # Not published and no error: behave like a paho timed-out wait.


def test_paho_drain_settles_acked_and_failed_messages():
    """drain() pops acked/permanently-failed infos, keeps unacked ones.

    paho's MQTTMessageInfo raises RuntimeError/ValueError from both
    is_published() and wait_for_publish() for messages that failed
    permanently or could not be queued; those must count as settled
    instead of crashing or blocking the bounded drain.
    """
    pytest.importorskip("paho.mqtt.client")
    from egw_simulator.publisher import PahoPublisher

    publisher = PahoPublisher("localhost", tls=False)  # never connected
    acked = _FakeMessageInfo(published=True)
    failed = _FakeMessageInfo(exc=RuntimeError("Message publish failed"))
    unqueued = _FakeMessageInfo(exc=ValueError("not queued"))
    publisher._pending.extend([acked, failed, unqueued])
    assert publisher.drain(timeout_s=0.2) is True
    assert not publisher._pending

    stuck = _FakeMessageInfo(published=False)
    publisher._pending.extend([acked, stuck])
    assert publisher.drain(timeout_s=0.05) is False
    assert list(publisher._pending) == [stuck]


# ------------------------------------------------- identifier re-validation

@pytest.mark.parametrize("bad_run_id", ["../x", "a/b", "run id", "", "x" * 65])
def test_run_config_rejects_path_escaping_run_id(tmp_path, bad_run_id):
    with pytest.raises(ValueError, match="run_id"):
        make_config(tmp_path, run_id=bad_run_id)


@pytest.mark.parametrize("bad_egw_id", ["../x", "egw/01", "egw 01", "", "e" * 65])
def test_run_config_rejects_topic_corrupting_egw_id(tmp_path, bad_egw_id):
    with pytest.raises(ValueError, match="egw_id"):
        make_config(tmp_path, egw_id=bad_egw_id)


def test_run_revalidates_ids_on_duck_typed_config(tmp_path):
    """run() re-checks ids even for configs built without RunConfig."""
    from types import SimpleNamespace

    base = dict(
        scenario="smoke",
        seed=7,
        run_id="ok-run",
        egw_id="egw-01",
        duration_s=1.0,
        aggregate_rate_hz=11.2,
        device_types=DEVICE_TYPES,
        qos=1,
        broker_host="localhost",
        broker_port=8883,
        tls=True,
        ca_cert=None,
        output_dir=tmp_path,
    )
    bad_run = SimpleNamespace(**{**base, "run_id": "../escape"})
    with pytest.raises(ValueError, match="run_id"):
        run(bad_run, InMemoryPublisher(), clock=FakeClock())
    bad_egw = SimpleNamespace(**{**base, "egw_id": "a/b"})
    with pytest.raises(ValueError, match="egw_id"):
        run(bad_egw, InMemoryPublisher(), clock=FakeClock())
    # Nothing may be written before validation fails.
    assert not (tmp_path / "../escape").exists()
    assert not (tmp_path / "ok-run").exists()


# ------------------------------------------------------------- writer guard

def test_sent_events_writer_enforces_exact_fields(tmp_path):
    path = tmp_path / "sent_events.jsonl"
    record = {
        "run_id": "r",
        "message_id": "m",
        "device_uuid": "d",
        "device_type": "smartwatch",
        "seq": 0,
        "publish_monotonic_ns": 1,
        "puback_monotonic_ns": None,
        "intended_invalid": False,
    }
    with SentEventsWriter(path) as writer:
        writer.write(record)
        with pytest.raises(ValueError):
            writer.write({**record, "extra": 1})
        with pytest.raises(ValueError):
            writer.write({k: v for k, v in record.items() if k != "seq"})
    lines = read_jsonl(path)
    assert len(lines) == 1
    assert list(lines[0]) == list(SENT_EVENT_FIELDS)
    assert lines[0]["puback_monotonic_ns"] is None
