"""Tests for egw_controller.config (CONTRACTS.md section 6, ``EGW_`` prefix)."""

from __future__ import annotations

import pytest

from egw_controller.config import ConfigError, Settings


def test_defaults_match_contracts_section_6() -> None:
    settings = Settings.from_env({})
    assert settings.egw_id == "egw-01"
    assert settings.mqtt_host == "localhost"
    assert settings.mqtt_port == 8883
    assert settings.mqtt_username is None
    assert settings.mqtt_password is None
    assert settings.mqtt_tls is True
    assert settings.mqtt_ca_cert is None
    assert settings.mqtt_topic_filter == "c2dt/+/+/telemetry"
    assert settings.ditto_base_url == "http://ditto-gateway:8080"
    assert settings.ditto_auth_mode == "pre"
    assert settings.ditto_preauth_subject == "pre:egw-controller"
    assert settings.ditto_username is None
    assert settings.ditto_password is None
    assert settings.schema_dir == "src/schemas"
    assert settings.event_log_dir == "./data/events"
    assert settings.http_port == 8000
    assert settings.retry_max == 3
    assert settings.retry_backoff_ms == 200


def test_full_env_override() -> None:
    env = {
        "EGW_ID": "egw-lab",
        "EGW_MQTT_HOST": "broker.local",
        "EGW_MQTT_PORT": "1883",
        "EGW_MQTT_USERNAME": "egw-controller",
        "EGW_MQTT_PASSWORD": "secret",
        "EGW_MQTT_TLS": "false",
        "EGW_MQTT_CA_CERT": "/certs/ca.crt",
        "EGW_MQTT_TOPIC_FILTER": "c2dt/egw-lab/+/telemetry",
        "EGW_DITTO_BASE_URL": "http://localhost:8080",
        "EGW_DITTO_AUTH_MODE": "basic",
        "EGW_DITTO_PREAUTH_SUBJECT": "pre:other",
        "EGW_DITTO_USERNAME": "ditto",
        "EGW_DITTO_PASSWORD": "ditto",
        "EGW_SCHEMA_DIR": "./schemas",
        "EGW_EVENT_LOG_DIR": "/data/events",
        "EGW_HTTP_PORT": "8081",
        "EGW_RETRY_MAX": "5",
        "EGW_RETRY_BACKOFF_MS": "100",
    }
    settings = Settings.from_env(env)
    assert settings.egw_id == "egw-lab"
    assert settings.mqtt_host == "broker.local"
    assert settings.mqtt_port == 1883
    assert settings.mqtt_username == "egw-controller"
    assert settings.mqtt_password == "secret"
    assert settings.mqtt_tls is False
    assert settings.mqtt_ca_cert == "/certs/ca.crt"
    assert settings.mqtt_topic_filter == "c2dt/egw-lab/+/telemetry"
    assert settings.ditto_base_url == "http://localhost:8080"
    assert settings.ditto_auth_mode == "basic"
    assert settings.ditto_preauth_subject == "pre:other"
    assert settings.ditto_username == "ditto"
    assert settings.ditto_password == "ditto"
    assert settings.schema_dir == "./schemas"
    assert settings.event_log_dir == "/data/events"
    assert settings.http_port == 8081
    assert settings.retry_max == 5
    assert settings.retry_backoff_ms == 100


@pytest.mark.parametrize("raw", ["1", "true", "TRUE", "yes", "on"])
def test_bool_true_values(raw: str) -> None:
    assert Settings.from_env({"EGW_MQTT_TLS": raw}).mqtt_tls is True


@pytest.mark.parametrize("raw", ["0", "false", "False", "no", "off"])
def test_bool_false_values(raw: str) -> None:
    assert Settings.from_env({"EGW_MQTT_TLS": raw}).mqtt_tls is False


def test_empty_string_falls_back_to_default() -> None:
    settings = Settings.from_env({"EGW_ID": "", "EGW_MQTT_PORT": ""})
    assert settings.egw_id == "egw-01"
    assert settings.mqtt_port == 8883


def test_invalid_bool_raises() -> None:
    with pytest.raises(ConfigError):
        Settings.from_env({"EGW_MQTT_TLS": "banana"})


def test_invalid_int_raises() -> None:
    with pytest.raises(ConfigError):
        Settings.from_env({"EGW_MQTT_PORT": "not-a-port"})


def test_invalid_auth_mode_raises() -> None:
    with pytest.raises(ConfigError):
        Settings.from_env({"EGW_DITTO_AUTH_MODE": "token"})


def test_basic_auth_requires_credentials() -> None:
    with pytest.raises(ConfigError):
        Settings.from_env({"EGW_DITTO_AUTH_MODE": "basic"})
    settings = Settings.from_env(
        {
            "EGW_DITTO_AUTH_MODE": "basic",
            "EGW_DITTO_USERNAME": "u",
            "EGW_DITTO_PASSWORD": "p",
        }
    )
    assert settings.ditto_auth_mode == "basic"


def test_retry_max_must_be_positive() -> None:
    with pytest.raises(ConfigError):
        Settings.from_env({"EGW_RETRY_MAX": "0"})


def test_retry_backoff_must_be_non_negative() -> None:
    with pytest.raises(ConfigError):
        Settings.from_env({"EGW_RETRY_BACKOFF_MS": "-1"})


@pytest.mark.parametrize(
    ("key", "value"),
    [("EGW_MQTT_PORT", "0"), ("EGW_MQTT_PORT", "65536"), ("EGW_HTTP_PORT", "0")],
)
def test_out_of_range_port_raises(key: str, value: str) -> None:
    with pytest.raises(ConfigError):
        Settings.from_env({key: value})
