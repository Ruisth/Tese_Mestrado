"""Environment-driven configuration (CONTRACTS.md section 6, ``EGW_`` prefix)."""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Mapping

_TRUE_VALUES = frozenset({"1", "true", "yes", "on"})
_FALSE_VALUES = frozenset({"0", "false", "no", "off"})

_AUTH_MODES = frozenset({"pre", "basic"})


class ConfigError(ValueError):
    """Raised when an ``EGW_*`` environment variable holds an invalid value."""


def _get_str(env: Mapping[str, str], key: str, default: str) -> str:
    value = env.get(key)
    if value is None or value == "":
        return default
    return value


def _get_optional(env: Mapping[str, str], key: str) -> str | None:
    value = env.get(key)
    if value is None or value == "":
        return None
    return value


def _get_bool(env: Mapping[str, str], key: str, default: bool) -> bool:
    raw = env.get(key)
    if raw is None or raw == "":
        return default
    lowered = raw.strip().lower()
    if lowered in _TRUE_VALUES:
        return True
    if lowered in _FALSE_VALUES:
        return False
    raise ConfigError(f"{key} must be a boolean value, got {raw!r}")


def _get_int(env: Mapping[str, str], key: str, default: int) -> int:
    raw = env.get(key)
    if raw is None or raw == "":
        return default
    try:
        return int(raw)
    except ValueError as exc:
        raise ConfigError(f"{key} must be an integer, got {raw!r}") from exc


@dataclass(frozen=True, slots=True)
class Settings:
    """Controller settings; defaults follow CONTRACTS.md section 6 exactly."""

    egw_id: str = "egw-01"
    mqtt_host: str = "localhost"
    mqtt_port: int = 8883
    mqtt_username: str | None = None
    mqtt_password: str | None = None
    mqtt_tls: bool = True
    mqtt_ca_cert: str | None = None
    mqtt_topic_filter: str = "c2dt/+/+/telemetry"
    ditto_base_url: str = "http://ditto-gateway:8080"
    ditto_auth_mode: str = "pre"
    ditto_preauth_subject: str = "pre:egw-controller"
    ditto_username: str | None = None
    ditto_password: str | None = None
    schema_dir: str = "src/schemas"
    event_log_dir: str = "./data/events"
    http_port: int = 8000
    retry_max: int = 3
    retry_backoff_ms: int = 200

    def __post_init__(self) -> None:
        if self.ditto_auth_mode not in _AUTH_MODES:
            raise ConfigError(
                f"EGW_DITTO_AUTH_MODE must be one of {sorted(_AUTH_MODES)}, "
                f"got {self.ditto_auth_mode!r}"
            )
        if self.ditto_auth_mode == "basic" and not (
            self.ditto_username and self.ditto_password
        ):
            raise ConfigError(
                "EGW_DITTO_USERNAME and EGW_DITTO_PASSWORD are required when "
                "EGW_DITTO_AUTH_MODE=basic"
            )
        if self.retry_max < 1:
            raise ConfigError("EGW_RETRY_MAX must be >= 1")
        if self.retry_backoff_ms < 0:
            raise ConfigError("EGW_RETRY_BACKOFF_MS must be >= 0")
        for name, port in (("EGW_MQTT_PORT", self.mqtt_port), ("EGW_HTTP_PORT", self.http_port)):
            if not 1 <= port <= 65535:
                raise ConfigError(f"{name} must be in 1..65535, got {port}")

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> "Settings":
        """Build settings from ``EGW_*`` variables (``os.environ`` by default)."""
        e: Mapping[str, str] = os.environ if env is None else env
        return cls(
            egw_id=_get_str(e, "EGW_ID", "egw-01"),
            mqtt_host=_get_str(e, "EGW_MQTT_HOST", "localhost"),
            mqtt_port=_get_int(e, "EGW_MQTT_PORT", 8883),
            mqtt_username=_get_optional(e, "EGW_MQTT_USERNAME"),
            mqtt_password=_get_optional(e, "EGW_MQTT_PASSWORD"),
            mqtt_tls=_get_bool(e, "EGW_MQTT_TLS", True),
            mqtt_ca_cert=_get_optional(e, "EGW_MQTT_CA_CERT"),
            mqtt_topic_filter=_get_str(e, "EGW_MQTT_TOPIC_FILTER", "c2dt/+/+/telemetry"),
            ditto_base_url=_get_str(e, "EGW_DITTO_BASE_URL", "http://ditto-gateway:8080"),
            ditto_auth_mode=_get_str(e, "EGW_DITTO_AUTH_MODE", "pre").strip().lower(),
            ditto_preauth_subject=_get_str(
                e, "EGW_DITTO_PREAUTH_SUBJECT", "pre:egw-controller"
            ),
            ditto_username=_get_optional(e, "EGW_DITTO_USERNAME"),
            ditto_password=_get_optional(e, "EGW_DITTO_PASSWORD"),
            schema_dir=_get_str(e, "EGW_SCHEMA_DIR", "src/schemas"),
            event_log_dir=_get_str(e, "EGW_EVENT_LOG_DIR", "./data/events"),
            http_port=_get_int(e, "EGW_HTTP_PORT", 8000),
            retry_max=_get_int(e, "EGW_RETRY_MAX", 3),
            retry_backoff_ms=_get_int(e, "EGW_RETRY_BACKOFF_MS", 200),
        )
