"""Paced, deterministic run loop of the wearable simulator (plan section 5.6).

Scheduling is based on ``time.monotonic()`` with drift correction: event k of
a device is due at ``start + k / rate`` (absolute target, product form), so
sleep jitter never accumulates. Every payload is validated against its JSON
Schema BEFORE publish, except the intentionally invalid events of the
``invalid-payload`` scenario, which are marked only in the simulator's own
record (``intended_invalid``), never in the payload.

The loop publishes through the ``Publisher`` protocol and, on completion (or
interruption), writes the per-run evidence outputs ``manifest.json`` and
``sent_events.jsonl`` under ``<output_dir>/<run_id>/``.

PUBACK capture is best-effort (CONTRACTS.md section 7, v1.1): each publish
receives a wait budget of ``max(0, next_scheduled_event_time - now)``, so
waiting for the QoS 1 acknowledgement can never delay the schedule. A
bounded drain at end of run gives the last in-flight message(s) a capped
window before disconnect. No primary metric uses the puback field.

dropout-reconnect (plan section 7.2; see ``DROPOUT_SCOPE_NOTE``): the run
has deterministic run-level disconnect windows. At the first event scheduled
inside a window the publisher's connection is dropped
(``publisher.disconnect()``, socket close); events scheduled inside the
window keep being GENERATED on schedule (a real wearable keeps sampling) and
are buffered in order; at window end — the first event scheduled after the
window, or the window end itself when the run tail is covered — the
publisher reconnects and the buffer is flushed in order BEFORE live
publishing resumes. Flushed publishes use a zero puback wait budget, so the
flush never blocks live events longer than their own budget. ``seq`` stays
strictly monotonic and gap-free; every generated event is published exactly
once, and buffered events carry their ACTUAL (late) publish instant in
``publish_monotonic_ns``.
"""

from __future__ import annotations

import heapq
import json
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from .devices import DEVICE_TYPES, DeviceSpec, make_devices, split_rate
from .envelope import build_envelope, rfc3339_utc_ms
from .output import SentEventsWriter, detect_git_commit, write_manifest
from .profiles import MeasurementProfile, make_profile
from .publisher import DEFAULT_DRAIN_TIMEOUT_S, Publisher
from .scenarios import (
    DROPOUT_SCOPE_NOTE,
    SCENARIOS,
    InvalidInjector,
    dropout_windows,
    window_index,
)
from .validation import SchemaValidator

#: Telemetry topic layout (CONTRACTS.md section 1).
TOPIC_TEMPLATE = "c2dt/{egw_id}/{device_uuid}/telemetry"

#: Identifier pattern for run_id and egw_id (CONTRACTS.md section 2). Both
#: land in filesystem paths and in the MQTT topic, so they are re-validated
#: here for programmatic callers, not only in the CLI.
RUN_ID_RE = re.compile(r"^[A-Za-z0-9._-]{1,64}$")

#: Strict-inequality guard against float artifacts at the run boundary.
SCHEDULE_EPSILON_S = 1e-9


class Clock(Protocol):
    """Injectable time source: real monotonic clock or a test fake."""

    def monotonic(self) -> float: ...

    def sleep(self, seconds: float) -> None: ...


class MonotonicClock:
    """Production clock: ``time.monotonic`` / ``time.sleep``."""

    def monotonic(self) -> float:
        return time.monotonic()

    def sleep(self, seconds: float) -> None:
        time.sleep(seconds)


def scheduled_times(rate_hz: float, duration_s: float) -> list[float]:
    """Reference schedule of one device: event k at ``k / rate_hz``.

    Membership uses the exact product-form comparison of the run loop
    (``k * interval < duration - SCHEDULE_EPSILON_S``), so tests can
    recompute expected event counts without float divergence.
    """
    if rate_hz <= 0:
        raise ValueError("rate must be positive")
    interval = 1.0 / rate_hz
    times: list[float] = []
    k = 0
    while k * interval < duration_s - SCHEDULE_EPSILON_S:
        times.append(k * interval)
        k += 1
    return times


def _validate_identifiers(run_id: str, egw_id: str) -> None:
    """Reject identifiers that could escape paths or corrupt the topic.

    ``run_id`` names the output directory and ``egw_id`` is a topic level
    (CONTRACTS.md sections 1-2), so both must match
    ``^[A-Za-z0-9._-]{1,64}$`` even for programmatic callers that bypass
    the CLI (e.g. ``run_id='../x'`` or ``egw_id='a/b'``).
    """
    if not isinstance(run_id, str) or not RUN_ID_RE.fullmatch(run_id):
        raise ValueError(
            "run_id must match ^[A-Za-z0-9._-]{1,64}$ (CONTRACTS.md section 2)"
        )
    if not isinstance(egw_id, str) or not RUN_ID_RE.fullmatch(egw_id):
        raise ValueError(
            "egw_id must match ^[A-Za-z0-9._-]{1,64}$ (CONTRACTS.md section 2)"
        )


@dataclass(frozen=True)
class RunConfig:
    """Concrete configuration of one run (defaults already resolved)."""

    scenario: str
    seed: int
    run_id: str
    egw_id: str
    duration_s: float
    aggregate_rate_hz: float
    device_types: tuple[str, ...] = DEVICE_TYPES
    qos: int = 1
    broker_host: str = "localhost"
    broker_port: int = 8883
    tls: bool = True
    ca_cert: str | None = None
    output_dir: str | Path = "results/raw"

    def __post_init__(self) -> None:
        _validate_identifiers(self.run_id, self.egw_id)


@dataclass(frozen=True)
class RunResult:
    """Summary of one completed (or interrupted) run.

    ``buffered_dropout`` counts the events generated inside disconnect
    windows and buffered device-side; in a completed run every one of them
    was flushed (published late), so they are included in ``sent``.
    ``dropout_disconnects`` counts the disconnect/reconnect cycles actually
    performed (one per window that contained at least one scheduled event).
    """

    run_id: str
    sent: int
    intended_invalid: int
    buffered_dropout: int
    dropout_disconnects: int
    completed: bool
    run_dir: Path
    manifest_path: Path
    sent_events_path: Path


@dataclass
class _DeviceState:
    spec: DeviceSpec
    interval_s: float
    profile: MeasurementProfile
    injector: InvalidInjector | None
    seq: int = 0


def run(
    config: RunConfig,
    publisher: Publisher,
    *,
    clock: Clock | None = None,
    validator: SchemaValidator | None = None,
    drain_timeout_s: float = DEFAULT_DRAIN_TIMEOUT_S,
) -> RunResult:
    """Execute one simulation run and write its evidence outputs.

    The publisher must already be connected (the CLI owns its lifecycle).
    Determinism (plan section 5.6): for a fixed (scenario, seed, run_id,
    egw_id, device_types, rate, duration), device UUIDs, payload sequences,
    injected-invalid positions, disconnect windows and therefore the exact
    set of buffered events are identical across runs; only ``ts`` and the
    monotonic timing fields differ (buffered events are inherently
    published late).

    Each live publish gets a puback wait budget equal to the free time
    until the next scheduled event (0 when none is left or the loop is
    behind), so acknowledgement capture never throttles the schedule;
    flushed publishes use a zero budget; ``drain_timeout_s`` bounds the
    end-of-run wait for the last in-flight message(s).

    dropout-reconnect: run-level window membership of each event's
    scheduled time drives the buffer/flush transitions (module docstring);
    ``publisher.disconnect()`` / ``publisher.reconnect()`` are called
    exactly once per window that contains at least one scheduled event, and
    nothing is ever published while disconnected.
    """
    try:
        spec = SCENARIOS[config.scenario]
    except KeyError:
        raise ValueError(
            f"unknown scenario {config.scenario!r}; valid: {', '.join(SCENARIOS)}"
        ) from None
    if config.duration_s <= 0:
        raise ValueError("duration_s must be positive")
    # Re-validate even though RunConfig.__post_init__ already does: run()
    # may receive a duck-typed config object built without the dataclass.
    _validate_identifiers(config.run_id, config.egw_id)
    clock = clock if clock is not None else MonotonicClock()
    validator = validator if validator is not None else SchemaValidator()

    devices = make_devices(config.seed, list(config.device_types))
    rates = split_rate(config.aggregate_rate_hz, list(config.device_types))
    states: list[_DeviceState] = []
    for dev in devices:
        states.append(
            _DeviceState(
                spec=dev,
                interval_s=1.0 / rates[dev.device_type],
                profile=make_profile(dev.device_type, config.seed, dev.device_uuid),
                injector=(
                    InvalidInjector(config.seed, dev.device_uuid, spec.invalid_ratio)
                    if spec.invalid_ratio
                    else None
                ),
            )
        )

    # Run-level disconnect windows (dropout-reconnect only): the simulator
    # holds ONE MQTT connection for all devices, so windows are shared.
    windows: tuple[tuple[float, float], ...] = (
        tuple(dropout_windows(config.seed, config.duration_s))
        if spec.dropout
        else ()
    )

    run_dir = Path(config.output_dir) / config.run_id
    try:
        # Raw simulator evidence is write-once. mkdir(exist_ok=False) is the
        # atomic guard and deliberately runs before timestamps, writers or
        # manifests are created. Repeating an experiment therefore requires
        # a new run_id; an existing directory is never inspected, truncated
        # or repaired in place.
        run_dir.mkdir(parents=True, exist_ok=False)
    except FileExistsError as exc:
        raise FileExistsError(
            f"simulator run directory already exists: {run_dir}; raw run "
            "evidence is write-once, so repeat with a new run_id"
        ) from exc
    manifest_path = run_dir / "manifest.json"
    sent_events_path = run_dir / "sent_events.jsonl"

    started_utc = rfc3339_utc_ms()
    git_commit = detect_git_commit()
    sent = intended_invalid_count = buffered_dropout = disconnects = 0
    completed = False

    # Lazy merged schedule: heap of (due_time_s, device_index, k). The k-th
    # event of a device is due at k * interval (product form, no drift).
    heap: list[tuple[float, int, int]] = []
    for idx in range(len(states)):
        if 0.0 < config.duration_s - SCHEDULE_EPSILON_S:
            heapq.heappush(heap, (0.0, idx, 0))

    writer = SentEventsWriter(sent_events_path)
    start_mono = clock.monotonic()

    # dropout-reconnect state: index of the window the publisher is
    # currently disconnected for (None = connected) and the device-side
    # buffer of (topic, payload_bytes, record_base) awaiting the flush.
    open_window: int | None = None
    buffer: list[tuple[str, bytes, dict]] = []

    def flush_buffer() -> None:
        """Publish the buffered window events in order (buffered redelivery).

        Called immediately after ``publisher.reconnect()``. Buffer order is
        generation order, so per-device ``seq`` order is preserved. Each
        flushed publish uses a zero puback wait budget — the flush must
        never block the schedule of live events longer than their own
        budget — and its record carries the ACTUAL (late) publish instant.
        """
        nonlocal sent
        for buffered_topic, buffered_payload, record_base in buffer:
            flush_result = publisher.publish(
                buffered_topic, buffered_payload, wait_budget_s=0.0
            )
            writer.write(
                {
                    **record_base,
                    "publish_monotonic_ns": flush_result.publish_monotonic_ns,
                    "puback_monotonic_ns": flush_result.puback_monotonic_ns,
                }
            )
            sent += 1
        buffer.clear()

    def pace_until(t_target_s: float) -> None:
        """Sleep until ``start + t_target_s``; no-op when already behind."""
        while True:
            delay = (start_mono + t_target_s) - clock.monotonic()
            if delay <= 0:
                break
            clock.sleep(delay)

    try:
        while heap:
            t_sched, idx, k = heapq.heappop(heap)
            state = states[idx]
            t_next = (k + 1) * state.interval_s
            if t_next < config.duration_s - SCHEDULE_EPSILON_S:
                heapq.heappush(heap, (t_next, idx, k + 1))

            # Pace on the absolute target; if behind schedule, publish
            # immediately (catch-up) without altering the payload sequence.
            pace_until(t_sched)

            # dropout-reconnect transitions, driven by run-level window
            # membership of the event's SCHEDULED time (deterministic per
            # seed). Ordered after pacing so the disconnect happens at the
            # first in-window event and the reconnect strictly after the
            # window has ended in wall-clock terms.
            w = window_index(t_sched, windows) if windows else None
            if w is not None:
                if open_window is None:
                    publisher.disconnect()
                    disconnects += 1
                    open_window = w
                elif w != open_window:
                    # No live event fell between two windows: settle the
                    # previous window (reconnect + in-order flush), then
                    # open the new one.
                    publisher.reconnect()
                    flush_buffer()
                    publisher.disconnect()
                    disconnects += 1
                    open_window = w
            elif open_window is not None:
                # First event scheduled after the open window: reconnect
                # and flush the buffer BEFORE resuming live publishing.
                publisher.reconnect()
                flush_buffer()
                open_window = None

            # Events are ALWAYS generated on schedule — inside a window a
            # real wearable keeps sampling — so seq stays gap-free.
            seq = state.seq
            state.seq += 1
            payload = build_envelope(
                run_id=config.run_id,
                egw_id=config.egw_id,
                device_uuid=state.spec.device_uuid,
                device_type=state.spec.device_type,
                seq=seq,
            )
            payload.update(state.profile.next())

            is_invalid = state.injector is not None and state.injector.is_invalid(seq)
            if is_invalid:
                payload = state.injector.mutate(payload, seq)
                intended_invalid_count += 1
            else:
                validator.validate(payload)  # raises on internal bug

            topic = TOPIC_TEMPLATE.format(
                egw_id=config.egw_id, device_uuid=state.spec.device_uuid
            )
            payload_bytes = json.dumps(payload, separators=(",", ":")).encode("utf-8")
            record_base = {
                "run_id": config.run_id,
                "message_id": payload["message_id"],
                "device_uuid": state.spec.device_uuid,
                "device_type": state.spec.device_type,
                "seq": seq,
                "intended_invalid": is_invalid,
            }

            if open_window is not None:
                # Disconnected: buffer in generation order; published (and
                # recorded) on flush, so nothing is sent while offline.
                buffer.append((topic, payload_bytes, record_base))
                buffered_dropout += 1
                continue

            # Best-effort puback capture (CONTRACTS.md section 7): the wait
            # budget is the free time until the next scheduled event, so the
            # acknowledgement round-trip can never delay the schedule.
            wait_budget_s = (
                max(0.0, (start_mono + heap[0][0]) - clock.monotonic())
                if heap
                else 0.0
            )
            result = publisher.publish(
                topic, payload_bytes, wait_budget_s=wait_budget_s
            )
            writer.write(
                {
                    **record_base,
                    "publish_monotonic_ns": result.publish_monotonic_ns,
                    "puback_monotonic_ns": result.puback_monotonic_ns,
                }
            )
            sent += 1

        if open_window is not None:
            # The last scheduled events fell inside a window: wait for the
            # window to actually end (never past the run duration), then
            # reconnect and flush so every generated event is published.
            pace_until(min(windows[open_window][1], config.duration_s))
            publisher.reconnect()
            flush_buffer()
            open_window = None

        completed = True
        # Bounded end-of-run drain: give the last in-flight QoS 1
        # message(s) a capped window to be acknowledged before disconnect.
        # Records already written with a null puback are never revisited.
        if drain_timeout_s > 0.0:
            publisher.drain(drain_timeout_s)
    finally:
        writer.close()
        write_manifest(
            manifest_path,
            scenario=config.scenario,
            seed=config.seed,
            run_id=config.run_id,
            egw_id=config.egw_id,
            devices=devices,
            aggregate_rate_hz=config.aggregate_rate_hz,
            per_device_rates_hz=rates,
            duration_s=config.duration_s,
            qos=config.qos,
            broker={
                "host": config.broker_host,
                "port": config.broker_port,
                "tls": config.tls,
                "ca_cert": config.ca_cert,
            },
            git_commit=git_commit,
            started_utc=started_utc,
            finished_utc=rfc3339_utc_ms(),
            completed=completed,
            totals={
                "sent": sent,
                "intended_invalid": intended_invalid_count,
                "buffered_dropout": buffered_dropout,
                "dropout_disconnects": disconnects,
            },
            note=DROPOUT_SCOPE_NOTE if spec.dropout else None,
        )
    return RunResult(
        run_id=config.run_id,
        sent=sent,
        intended_invalid=intended_invalid_count,
        buffered_dropout=buffered_dropout,
        dropout_disconnects=disconnects,
        completed=completed,
        run_dir=run_dir,
        manifest_path=manifest_path,
        sent_events_path=sent_events_path,
    )
