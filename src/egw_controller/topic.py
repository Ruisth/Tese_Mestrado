"""Parsing/validation of the normative telemetry topic (CONTRACTS.md section 1).

Topic layout: ``c2dt/{egw_id}/{device_uuid}/telemetry``.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

TOPIC_PREFIX = "c2dt"
TOPIC_LEAF = "telemetry"

# Same lexical rules as the envelope schema (telemetry-envelope-v1.schema.json).
_ID_RE = re.compile(r"^[A-Za-z0-9._-]{1,64}$")
_UUID4_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$"
)


class TopicError(ValueError):
    """Raised when an MQTT topic does not match the telemetry topic contract."""


@dataclass(frozen=True, slots=True)
class TelemetryTopic:
    """Parsed components of a valid telemetry topic."""

    egw_id: str
    device_uuid: str


def parse_topic(topic: str) -> TelemetryTopic:
    """Parse ``c2dt/{egw_id}/{device_uuid}/telemetry`` or raise :class:`TopicError`."""
    parts = topic.split("/")
    if len(parts) != 4:
        raise TopicError(
            f"topic must have 4 segments (c2dt/{{egw_id}}/{{device_uuid}}/telemetry), "
            f"got {topic!r}"
        )
    prefix, egw_id, device_uuid, leaf = parts
    if prefix != TOPIC_PREFIX:
        raise TopicError(f"topic must start with {TOPIC_PREFIX!r}, got {topic!r}")
    if leaf != TOPIC_LEAF:
        raise TopicError(f"topic must end with {TOPIC_LEAF!r}, got {topic!r}")
    if not _ID_RE.fullmatch(egw_id):
        raise TopicError(f"invalid egw_id segment {egw_id!r} in topic {topic!r}")
    if not _UUID4_RE.fullmatch(device_uuid):
        raise TopicError(
            f"invalid device_uuid segment {device_uuid!r} in topic {topic!r} "
            "(lowercase UUID v4 required)"
        )
    return TelemetryTopic(egw_id=egw_id, device_uuid=device_uuid)
