"""Tests for egw_controller.topic (CONTRACTS.md section 1).

Topic layout: ``c2dt/{egw_id}/{device_uuid}/telemetry``.
"""

from __future__ import annotations

import pytest

from egw_controller.topic import TelemetryTopic, TopicError, parse_topic

VALID_DEVICE_UUID = "1b46a1f5-9a3e-4c2d-8f6b-2d9e5a7c1b3d"


def test_valid_topic_parses() -> None:
    parsed = parse_topic(f"c2dt/egw-01/{VALID_DEVICE_UUID}/telemetry")
    assert parsed == TelemetryTopic(egw_id="egw-01", device_uuid=VALID_DEVICE_UUID)


def test_valid_topic_with_dotted_egw_id() -> None:
    parsed = parse_topic(f"c2dt/egw.lab_2-a/{VALID_DEVICE_UUID}/telemetry")
    assert parsed.egw_id == "egw.lab_2-a"
    assert parsed.device_uuid == VALID_DEVICE_UUID


@pytest.mark.parametrize(
    "topic",
    [
        "",
        "c2dt",
        "c2dt/egw-01/telemetry",  # 3 segments
        f"c2dt/egw-01/{VALID_DEVICE_UUID}/telemetry/extra",  # 5 segments
        f"other/egw-01/{VALID_DEVICE_UUID}/telemetry",  # wrong prefix
        f"C2DT/egw-01/{VALID_DEVICE_UUID}/telemetry",  # prefix is case-sensitive
        f"c2dt/egw-01/{VALID_DEVICE_UUID}/events",  # wrong leaf
        f"c2dt/egw-01/{VALID_DEVICE_UUID}/Telemetry",  # leaf is case-sensitive
        f"c2dt//{VALID_DEVICE_UUID}/telemetry",  # empty egw_id
        f"c2dt/egw 01/{VALID_DEVICE_UUID}/telemetry",  # space in egw_id
        f"c2dt/egw#01/{VALID_DEVICE_UUID}/telemetry",  # invalid char in egw_id
        f"c2dt/{'x' * 65}/{VALID_DEVICE_UUID}/telemetry",  # egw_id too long
        "c2dt/egw-01//telemetry",  # empty device_uuid
        "c2dt/egw-01/not-a-uuid/telemetry",
        # UUID v5 in the device segment (version nibble 5, not 4)
        "c2dt/egw-01/6b1a3f52-8c1e-5e2b-9f0d-c2d7a1e4b8a0/telemetry",
        # uppercase UUID rejected (contract requires the canonical lowercase form)
        f"c2dt/egw-01/{VALID_DEVICE_UUID.upper()}/telemetry",
        # wrong variant nibble (must be one of 89ab)
        "c2dt/egw-01/1b46a1f5-9a3e-4c2d-7f6b-2d9e5a7c1b3d/telemetry",
    ],
)
def test_invalid_topic_raises(topic: str) -> None:
    with pytest.raises(TopicError):
        parse_topic(topic)


def test_error_message_mentions_topic() -> None:
    bad = "c2dt/egw-01/not-a-uuid/telemetry"
    with pytest.raises(TopicError, match="not-a-uuid"):
        parse_topic(bad)
