"""EGW controller: MQTT-to-Ditto bridge for the C2DTA Edge Gateway.

Implements the normative contracts in ``src/CONTRACTS.md`` (sections 1-6, 9):
MQTT QoS 1 subscription, JSON Schema validation (draft 2020-12), idempotent
deduplication backed by the twin ``ingestion`` feature, Ditto merge-patch
updates with bounded retries, an append-only ``events.jsonl`` latency log and
a small FastAPI observability API.
"""

__all__ = ["__version__"]

__version__ = "0.1.0"
