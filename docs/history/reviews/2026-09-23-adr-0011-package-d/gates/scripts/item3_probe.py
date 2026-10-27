"""Item 3 probe: which deliveries end without an outcome line, read-only.

Imports the controller from the repository tree without writing bytecode
(sys.dont_write_bytecode; run with python -B as well) and exercises the real
ControllerService.run() loop with in-memory fakes. Nothing is written to
disk: the event sink is a list, except in case C, whose EventLogger points at
a directory under /proc that cannot be created. No network, no broker, no
guest.

Run (from Windows):
  wsl -d Ubuntu-24.04 --exec bash -lc \
    '~/egw-exec/venv/bin/python -B <gates>/scripts/item3_probe.py'
"""

from __future__ import annotations

import asyncio
import errno
import io
import json
import sys

sys.dont_write_bytecode = True
REPO_SRC = "/home/ruisth/egw-exec/repo/src"
sys.path.insert(0, REPO_SRC)

import httpx  # noqa: E402
import paho.mqtt  # noqa: E402
from paho.mqtt.client import CallbackAPIVersion, Client, MQTTMessage  # noqa: E402

from egw_controller.dedupe import DedupeCache  # noqa: E402
from egw_controller.ditto import DittoClient  # noqa: E402
from egw_controller.events import EventLogger  # noqa: E402
from egw_controller.metrics import MetricsCounters  # noqa: E402
from egw_controller.schema import SchemaRepository  # noqa: E402
from egw_controller.service import (  # noqa: E402
    ControllerService,
    InboundMessage,
    derive_message_id,
)

SCHEMAS = f"{REPO_SRC}/schemas"
EGW = "egw-01"
DEV = "0b7f4c1e-2d3a-4b5c-8d9e-0f1a2b3c4d5e"  # a lowercase UUID v4
TOPIC = f"c2dt/{EGW}/{DEV}/telemetry"
RUN = "probe-item3"


def valid_payload(seq: int) -> bytes:
    return json.dumps(
        {
            "schema_version": "1.0.0",
            "run_id": RUN,
            "message_id": derive_message_id(RUN, DEV, seq),
            "seq": seq,
            "ts": "2026-09-21T10:00:00.000Z",
            "egw_id": EGW,
            "device_uuid": DEV,
            "device_type": "smartwatch",
            "heart_rate_bpm": 70,
            "lat": 38.7,
            "lon": -9.1,
        }
    ).encode()


class ListEvents:
    """In-memory event sink with the one method the service calls."""

    def __init__(self) -> None:
        self.lines: list[dict] = []

    def log(self, event) -> None:  # noqa: ANN001
        self.lines.append(event.to_dict())


class FakeDitto:
    def __init__(self, twin=None) -> None:  # noqa: ANN001
        self.twin = twin
        self.patches = 0

    async def get_twin(self, device_uuid):  # noqa: ANN001
        return self.twin

    async def ensure_twin(self, **kw) -> int:  # noqa: ANN003
        return 2

    async def patch_thing(self, device_uuid, patch) -> int:  # noqa: ANN001
        self.patches += 1
        return 1

    async def is_ready(self) -> bool:
        return True


def ditto_with_get_body(body: bytes, ctype: str) -> DittoClient:
    """Real DittoClient over httpx.MockTransport answering every GET 200."""

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "GET":
            return httpx.Response(200, content=body, headers={"content-type": ctype})
        return httpx.Response(204)

    client = httpx.AsyncClient(
        transport=httpx.MockTransport(handler), base_url="http://ditto.probe"
    )
    return DittoClient(base_url="http://ditto.probe", client=client)


async def run_case(label: str, payloads: list[bytes], ditto, events) -> None:  # noqa: ANN001
    repo = SchemaRepository(SCHEMAS)
    metrics = MetricsCounters()
    svc = ControllerService(
        repository=repo,
        dedupe=DedupeCache(),
        ditto=ditto,
        events=events,
        metrics=metrics,
    )
    task = asyncio.create_task(svc.run())
    for p in payloads:
        svc.submit(InboundMessage(topic=TOPIC, payload=p, received_monotonic_ns=1))
    await svc.stop()
    await task
    snap = metrics.snapshot()
    lines = getattr(events, "lines", None)
    patches = getattr(ditto, "patches", None)
    print(
        f"[{label}] delivered={len(payloads)} "
        f"lines={'n/a' if lines is None else len(lines)} "
        f"outcomes={[l['outcome'] for l in lines] if lines is not None else 'n/a'} "
        f"received={snap['received']} processing_errors={snap['processing_errors']} "
        f"in_progress={snap['in_progress']} queue_depth={svc.queue_depth()} "
        f"patches={patches}"
    )


async def case_marker_order() -> None:
    """G. A delivery scheduled before stop() lands behind the marker."""
    repo = SchemaRepository(SCHEMAS)
    metrics = MetricsCounters()
    events = ListEvents()
    svc = ControllerService(
        repository=repo, dedupe=DedupeCache(), ditto=FakeDitto(), events=events,
        metrics=metrics,
    )
    task = asyncio.create_task(svc.run())
    await asyncio.sleep(0)  # let the consumer block on get()
    loop = asyncio.get_running_loop()
    # As mqtt.py:199 does from the network thread (here from the loop thread,
    # which appends to the same FIFO of ready callbacks).
    loop.call_soon_threadsafe(
        svc.submit,
        InboundMessage(topic=TOPIC, payload=valid_payload(1), received_monotonic_ns=1),
    )
    await svc.stop()  # appends the marker; does not yield when not full
    await task
    snap = metrics.snapshot()
    print(
        f"[G marker-order] lines={len(events.lines)} received={snap['received']} "
        f"queue_depth_after_consumer_ended={svc.queue_depth()}"
    )


def case_json_exceptions() -> None:
    """F. Exception classes json.loads raises for two payload shapes."""
    for label, text in (
        ("deep nesting", "[" * 200000),
        ("5000-digit integer", "1" * 5000),
    ):
        try:
            json.loads(text)
        except Exception as exc:  # noqa: BLE001
            print(
                f"[F json.loads {label}] {type(exc).__name__}; "
                f"is JSONDecodeError={isinstance(exc, json.JSONDecodeError)}; "
                f"is ValueError={isinstance(exc, ValueError)}"
            )


def case_flush_failure() -> None:
    """E. What CPython keeps after a failed flush of a text file."""

    class FailOnceRaw(io.RawIOBase):
        def __init__(self) -> None:
            self.data = bytearray()
            self.fail = True

        def writable(self) -> bool:
            return True

        def write(self, b) -> int:  # noqa: ANN001
            if self.fail:
                raise OSError(errno.ENOSPC, "No space left on device (simulated)")
            self.data += bytes(b)
            return len(b)

    raw = FailOnceRaw()
    fh = io.TextIOWrapper(io.BufferedWriter(raw), encoding="utf-8", newline="\n")
    fh.write("line-1\n")
    try:
        fh.flush()
        print("[E] first flush did not raise")
    except OSError as exc:
        print(f"[E] first flush raised {type(exc).__name__} errno={exc.errno}")
    raw.fail = False
    fh.write("line-2\n")
    fh.flush()
    print(f"[E] raw contents after a later successful flush: {bytes(raw.data)!r}")


def case_paho() -> None:
    """H. paho-mqtt: ack() semantics and on_message exceptions, no network."""
    print(f"[H] paho-mqtt version {paho.mqtt.__version__}")
    auto = Client(CallbackAPIVersion.VERSION2, client_id="probe-auto")
    rc = auto.ack(7, 1)
    print(
        f"[H] manual_ack=False: ack(7,1) rc={int(rc)} queued_packets={len(auto._out_packet)}"
    )
    man = Client(CallbackAPIVersion.VERSION2, client_id="probe-man", manual_ack=True)
    rc = man.ack(7, 1)
    print(
        f"[H] manual_ack=True, never connected: ack(7,1) rc={int(rc)} "
        f"queued_packets={len(man._out_packet)} "
        f"packet={bytes(man._out_packet[0]['packet']).hex() if man._out_packet else None}"
    )
    rc0 = man.ack(8, 0)
    print(f"[H] manual_ack=True: ack(8,0) rc={int(rc0)} queued_packets={len(man._out_packet)}")
    print(f"[H] default clean_session for MQTT 3.1.1: {man._clean_session}; "
          f"suppress_exceptions default: {man.suppress_exceptions}")

    def raising_on_message(client, userdata, message):  # noqa: ANN001
        _ = message.topic  # as mqtt.py:195 does

    man.on_message = raising_on_message
    bad = MQTTMessage(mid=9, topic=b"c2dt/\xff/x/telemetry")
    try:
        man._handle_on_message(bad)
        print("[H] on_message with invalid UTF-8 topic: no exception")
    except Exception as exc:  # noqa: BLE001
        print(f"[H] on_message with invalid UTF-8 topic: {type(exc).__name__} propagates out of _handle_on_message")


async def main() -> None:
    print(f"python {sys.version.split()[0]}; repository source {REPO_SRC}")
    # D. Controls.
    await run_case("D control valid", [valid_payload(1)], FakeDitto(), ListEvents())
    await run_case("D control malformed JSON", [b"{"], FakeDitto(), ListEvents())
    # A. Payload-driven exceptions that escape process().
    await run_case("A1 deep nesting", [b"[" * 200000], FakeDitto(), ListEvents())
    await run_case(
        "A2 5000-digit integer", [b'{"seq": ' + b"1" * 5000 + b"}"], FakeDitto(), ListEvents()
    )
    await run_case(
        "A3 device_type is a list",
        [json.dumps({"device_type": [], "run_id": RUN}).encode()],
        FakeDitto(),
        ListEvents(),
    )
    # A4. A poison delivery followed by a valid one: does the consumer go on?
    await run_case(
        "A4 poison then valid", [b"[" * 200000, valid_payload(2)], FakeDitto(), ListEvents()
    )
    # B. Ditto-response-driven exceptions during first-contact seeding.
    await run_case(
        "B1 GET twin 200 non-JSON body",
        [valid_payload(1)],
        ditto_with_get_body(b"<html>proxy</html>", "text/html"),
        ListEvents(),
    )
    await run_case(
        "B2 GET twin 200 JSON list",
        [valid_payload(1)],
        ditto_with_get_body(b"[]", "application/json"),
        ListEvents(),
    )
    # C. Event-log write fails after the PATCH succeeded.
    ditto = FakeDitto(twin={"features": {"ingestion": {"properties": {}}}})
    await run_case(
        "C event log unwritable", [valid_payload(1)], ditto, EventLogger("/proc/egw-item3-probe")
    )
    await case_marker_order()


if __name__ == "__main__":
    asyncio.run(main())
    case_json_exceptions()
    case_flush_failure()
    case_paho()
