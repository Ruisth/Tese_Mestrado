"""Local JSON Schema validation of payloads before publish (plan section 5.6).

Loads the real project schemas (draft 2020-12) from ``src/schemas`` and
resolves the envelope ``$ref`` through a ``referencing.Registry``, exactly as
the controller does, so a payload accepted here is accepted there.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

from jsonschema import Draft202012Validator
from referencing import Registry, Resource

#: Default schema directory: ``src/schemas`` next to this package
#: (CONTRACTS.md section 6, ``EGW_SCHEMA_DIR``).
DEFAULT_SCHEMA_DIR = Path(__file__).resolve().parent.parent / "schemas"

ENVELOPE_SCHEMA_FILE = "telemetry-envelope-v1.schema.json"

DEVICE_SCHEMA_FILES: dict[str, str] = {
    "smartwatch": "smartwatch-v1.schema.json",
    "smart_ring": "smart-ring-v1.schema.json",
    "smart_clothing": "smart-clothing-v1.schema.json",
}


def resolve_schema_dir(explicit: Path | str | None = None) -> Path:
    """Schema dir resolution: explicit arg > ``EGW_SCHEMA_DIR`` > default."""
    if explicit:
        return Path(explicit)
    env = os.environ.get("EGW_SCHEMA_DIR")
    if env:
        return Path(env)
    return DEFAULT_SCHEMA_DIR


def _load_json(path: Path) -> dict:
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


class SchemaValidator:
    """Draft 2020-12 validators for the three device schemas.

    The envelope schema is registered by its ``$id`` so the ``allOf/$ref`` in
    each device schema (including ``unevaluatedProperties: false``) resolves
    offline.
    """

    def __init__(self, schema_dir: Path | str | None = None) -> None:
        self.schema_dir = resolve_schema_dir(schema_dir)
        envelope = _load_json(self.schema_dir / ENVELOPE_SCHEMA_FILE)
        documents = {None: envelope}
        for device_type, filename in DEVICE_SCHEMA_FILES.items():
            documents[device_type] = _load_json(self.schema_dir / filename)
        registry = Registry().with_resources(
            (doc["$id"], Resource.from_contents(doc)) for doc in documents.values()
        )
        self._validators = {
            device_type: Draft202012Validator(documents[device_type], registry=registry)
            for device_type in DEVICE_SCHEMA_FILES
        }

    def validator_for(self, device_type: str) -> Draft202012Validator:
        try:
            return self._validators[device_type]
        except KeyError:
            raise ValueError(
                f"no schema for device_type {device_type!r}; "
                f"known: {', '.join(self._validators)}"
            ) from None

    def validate(self, payload: dict) -> None:
        """Raise ``jsonschema.ValidationError`` if the payload is invalid."""
        self.validator_for(payload.get("device_type")).validate(payload)

    def is_valid(self, payload: dict) -> bool:
        device_type = payload.get("device_type")
        if device_type not in self._validators:
            return False
        return self._validators[device_type].is_valid(payload)
