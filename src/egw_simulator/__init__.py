"""Unified wearable telemetry simulator for the C2DTA Edge Gateway.

Implements plan sections 4.3 and 5.6 and CONTRACTS.md sections 1-3 and 7:
three deterministic device profiles (smartwatch, smart_ring, smart_clothing),
six scenarios, paced MQTT publishing (QoS 1, TLS) and per-run evidence
outputs (manifest.json + sent_events.jsonl).

This module is intentionally import-light: heavy dependencies (jsonschema,
paho-mqtt) are only imported by the modules that need them.
"""

__version__ = "0.1.0"
