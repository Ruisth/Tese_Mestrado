"""JSON Schema (draft 2020-12) validation for telemetry payloads.

Loads the schemas from ``EGW_SCHEMA_DIR`` and resolves the common-envelope
``$ref`` through a :class:`referencing.Registry` keyed by ``$id``
(``referencing`` ships with ``jsonschema`` >= 4.18). One compiled validator is
kept per ``device_type`` (CONTRACTS.md sections 2-3).

Validators are built with a :class:`jsonschema.FormatChecker` carrying our own
``date-time`` assertion, so the envelope's ``ts`` is genuinely validated rather
than merely annotated (see :func:`is_rfc3339_utc`).
"""

from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping

from jsonschema import Draft202012Validator, FormatChecker
from referencing import Registry, Resource

ENVELOPE_SCHEMA_FILE = "telemetry-envelope-v1.schema.json"

DEVICE_SCHEMA_FILES: Mapping[str, str] = {
    "smartwatch": "smartwatch-v1.schema.json",
    "smart_ring": "smart-ring-v1.schema.json",
    "smart_clothing": "smart-clothing-v1.schema.json",
}

_MAX_REPORTED_ERRORS = 3

#: Shape of an RFC 3339 UTC timestamp as CONTRACTS.md section 2 allows it:
#: ``Z`` suffix, optional fractional seconds of one to six digits. Mirrors the
#: envelope schema's ``ts`` pattern, which on its own only proves the
#: characters are digits (``2026-99-40T25:61:61Z`` satisfies it).
_RFC3339_UTC_RE = re.compile(
    r"(?P<date>\d{4}-\d{2}-\d{2})T(?P<time>\d{2}:\d{2}:\d{2})"
    r"(?P<fraction>\.\d{1,6})?Z"
)


def is_rfc3339_utc(value: Any) -> bool:
    """Return whether ``value`` is an RFC 3339 UTC timestamp (CONTRACTS.md section 2).

    Accepts ``YYYY-MM-DDThh:mm:ssZ``, with or without fractional seconds, and
    rejects impossible calendar or clock values (month 13, 30 February, hour
    24, second 61) by parsing the matched groups with the standard library.
    Non-string instances are not this format's concern and are left to the
    ``type`` keyword, per the JSON Schema format specification.

    Written by hand deliberately: ``jsonschema``'s stock ``FormatChecker`` has
    no ``date-time`` entry unless the optional ``rfc3339-validator`` package is
    installed, and the project takes no third-party dependency for this.
    """
    if not isinstance(value, str):
        return True
    match = _RFC3339_UTC_RE.fullmatch(value)
    if match is None:
        return False
    fraction = match["fraction"] or ""
    layout = "%Y-%m-%dT%H:%M:%S.%f" if fraction else "%Y-%m-%dT%H:%M:%S"
    try:
        datetime.strptime(f"{match['date']}T{match['time']}{fraction}", layout)
    except ValueError:
        return False
    return True


def build_format_checker() -> FormatChecker:
    """Return a format checker asserting the formats the contract relies on.

    Registration is per-instance, so the library-wide checker registry shared
    with any other ``jsonschema`` consumer in the process is left untouched.
    """
    checker = FormatChecker()
    checker.checks("date-time")(is_rfc3339_utc)
    return checker


class SchemaValidationError(ValueError):
    """Raised when a telemetry payload fails contract validation."""

    def __init__(self, message: str, errors: tuple[str, ...] = ()) -> None:
        super().__init__(message)
        self.errors = errors


def _load_schema(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as fh:
        schema = json.load(fh)
    Draft202012Validator.check_schema(schema)
    return schema


class SchemaRepository:
    """Compiled draft 2020-12 validators, one per known ``device_type``."""

    def __init__(self, schema_dir: Path | str) -> None:
        self._schema_dir = Path(schema_dir)
        envelope = _load_schema(self._schema_dir / ENVELOPE_SCHEMA_FILE)
        device_schemas = {
            device_type: _load_schema(self._schema_dir / filename)
            for device_type, filename in DEVICE_SCHEMA_FILES.items()
        }
        registry: Registry = Registry().with_resources(
            (schema["$id"], Resource.from_contents(schema))
            for schema in (envelope, *device_schemas.values())
        )
        format_checker = build_format_checker()
        self._validators: dict[str, Draft202012Validator] = {
            device_type: Draft202012Validator(
                schema, registry=registry, format_checker=format_checker
            )
            for device_type, schema in device_schemas.items()
        }

    @property
    def device_types(self) -> tuple[str, ...]:
        return tuple(self._validators)

    def validator_for(self, device_type: str) -> Draft202012Validator:
        try:
            return self._validators[device_type]
        except KeyError:
            raise SchemaValidationError(
                f"unknown device_type {device_type!r}; expected one of "
                f"{sorted(self._validators)}"
            ) from None

    def validate(self, payload: Any) -> None:
        """Validate a decoded payload; raise :class:`SchemaValidationError` on failure.

        The schema is selected by the payload's own ``device_type`` claim, so a
        payload carrying the wrong measurement fields for its claimed type fails
        (``const``/``required``/``unevaluatedProperties``). The claim must be a
        string before it is looked up: a JSON array or object there is
        unhashable and would otherwise escape the lookup as a ``TypeError``
        (ADR 0011, item 6); the error names the type found instead.
        """
        if not isinstance(payload, Mapping):
            raise SchemaValidationError(
                f"payload must be a JSON object, got {type(payload).__name__}"
            )
        device_type = payload.get("device_type")
        if not isinstance(device_type, str):
            raise SchemaValidationError(
                f"device_type must be a string, got {type(device_type).__name__}"
            )
        validator = self.validator_for(device_type)
        errors = sorted(validator.iter_errors(payload), key=lambda e: e.json_path)
        if errors:
            messages = tuple(
                f"{error.json_path}: {error.message}"
                for error in errors[:_MAX_REPORTED_ERRORS]
            )
            summary = "; ".join(messages)
            if len(errors) > _MAX_REPORTED_ERRORS:
                summary += f" (and {len(errors) - _MAX_REPORTED_ERRORS} more)"
            raise SchemaValidationError(
                f"schema validation failed: {summary}", errors=messages
            )
