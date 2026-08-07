"""Idempotency cache: per-device ``last_seq`` plus a bounded LRU of message ids.

CONTRACTS.md section 4: reject a repeated ``message_id`` and any ``seq`` <=
the known ``last_seq``. The authoritative state lives in the twin's
``ingestion`` feature so it survives controller restarts; this local cache is
rebuilt via :meth:`DedupeCache.seed_from_twin` on the first event of each
device after startup.
"""

from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass, field
from typing import Any, Mapping

DEFAULT_MESSAGE_ID_CAPACITY = 1024


class UnknownDeviceError(KeyError):
    """Raised when a device is used before being seeded (see ``seed_from_twin``)."""


def _is_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


@dataclass(slots=True)
class _DeviceState:
    last_seq: int | None = None
    accepted_count: int = 0
    message_ids: OrderedDict[str, None] = field(default_factory=OrderedDict)


class DedupeCache:
    """Per-device duplicate detection with a bounded message-id LRU."""

    def __init__(self, message_id_capacity: int = DEFAULT_MESSAGE_ID_CAPACITY) -> None:
        if message_id_capacity < 1:
            raise ValueError("message_id_capacity must be >= 1")
        self._capacity = message_id_capacity
        self._devices: dict[str, _DeviceState] = {}

    def known_device(self, device_uuid: str) -> bool:
        return device_uuid in self._devices

    def seed_from_twin(
        self, device_uuid: str, twin: Mapping[str, Any] | None
    ) -> None:
        """Mark the device known, restoring state from the twin's ``ingestion`` feature.

        ``twin`` is the raw Ditto thing JSON (or ``None`` for a twin created just
        now, which starts empty). Missing/null ingestion properties are treated
        as unknown state.
        """
        state = _DeviceState()
        if twin is not None:
            features = twin.get("features") or {}
            ingestion = features.get("ingestion") or {}
            properties = ingestion.get("properties") or {}
            last_seq = properties.get("last_seq")
            if _is_int(last_seq):
                state.last_seq = last_seq
            last_message_id = properties.get("last_message_id")
            if isinstance(last_message_id, str) and last_message_id:
                state.message_ids[last_message_id] = None
            accepted_count = properties.get("accepted_count")
            if _is_int(accepted_count) and accepted_count >= 0:
                state.accepted_count = accepted_count
        self._devices[device_uuid] = state

    def _state(self, device_uuid: str) -> _DeviceState:
        try:
            return self._devices[device_uuid]
        except KeyError:
            raise UnknownDeviceError(
                f"device {device_uuid!r} not seeded; call seed_from_twin first"
            ) from None

    def check(self, device_uuid: str, message_id: str, seq: int) -> str | None:
        """Return a duplicate reason string, or ``None`` if the message is fresh."""
        state = self._state(device_uuid)
        if message_id in state.message_ids:
            return f"duplicate message_id {message_id}"
        if state.last_seq is not None and seq <= state.last_seq:
            return f"seq {seq} <= last_seq {state.last_seq}"
        return None

    def record(self, device_uuid: str, message_id: str, seq: int) -> None:
        """Record a confirmed (Ditto 2xx) message: advance seq, LRU and counter."""
        state = self._state(device_uuid)
        state.message_ids[message_id] = None
        state.message_ids.move_to_end(message_id)
        while len(state.message_ids) > self._capacity:
            state.message_ids.popitem(last=False)
        if state.last_seq is None or seq > state.last_seq:
            state.last_seq = seq
        state.accepted_count += 1

    def accepted_count(self, device_uuid: str) -> int:
        return self._state(device_uuid).accepted_count

    def last_seq(self, device_uuid: str) -> int | None:
        return self._state(device_uuid).last_seq
