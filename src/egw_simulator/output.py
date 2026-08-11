"""Per-run evidence outputs: manifest.json and sent_events.jsonl.

CONTRACTS.md section 7 (binding): every run writes ``manifest.json``
(scenario, seed, commit, config, timestamps, protocol version) and
``sent_events.jsonl`` with exactly the fields in ``SENT_EVENT_FIELDS``.
Secrets (username/password) are never written to either file.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

from . import __version__
from .envelope import PROTOCOL_VERSION

#: Exact field set and order of each sent_events.jsonl record
#: (CONTRACTS.md section 7; plan section 5.8).
SENT_EVENT_FIELDS: tuple[str, ...] = (
    "run_id",
    "message_id",
    "device_uuid",
    "device_type",
    "seq",
    "publish_monotonic_ns",
    "puback_monotonic_ns",
    "intended_invalid",
)


def detect_git_commit(cwd: str | Path | None = None) -> str | None:
    """Best-effort ``git rev-parse HEAD``; ``None`` when unavailable.

    Never raises: missing git binary, non-repository directories and
    timeouts all degrade to ``None`` (recorded as JSON null in the
    manifest).
    """
    directory = Path(cwd) if cwd is not None else Path(__file__).resolve().parent
    try:
        proc = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=str(directory),
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    commit = proc.stdout.strip()
    if proc.returncode == 0 and commit:
        return commit
    return None


class SentEventsWriter:
    """Streaming JSON Lines writer enforcing the exact record contract.

    Records are written (and flushed) one per publish so that long runs
    (soak) leave usable evidence even if interrupted. Keys are emitted in
    ``SENT_EVENT_FIELDS`` order; missing or extra keys are an error.
    """

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self._fh = open(self.path, "w", encoding="utf-8", newline="\n")
        self.count = 0

    def write(self, record: dict) -> None:
        missing = [k for k in SENT_EVENT_FIELDS if k not in record]
        extra = [k for k in record if k not in SENT_EVENT_FIELDS]
        if missing or extra:
            raise ValueError(
                f"sent_events record contract violation: missing={missing}, extra={extra}"
            )
        ordered = {key: record[key] for key in SENT_EVENT_FIELDS}
        self._fh.write(json.dumps(ordered, separators=(",", ":")) + "\n")
        self._fh.flush()
        self.count += 1

    def close(self) -> None:
        if not self._fh.closed:
            self._fh.flush()
            self._fh.close()

    def __enter__(self) -> "SentEventsWriter":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()


def write_manifest(
    path: str | Path,
    *,
    scenario: str,
    seed: int,
    run_id: str,
    egw_id: str,
    devices,
    aggregate_rate_hz: float,
    per_device_rates_hz: dict,
    duration_s: float,
    qos: int,
    broker: dict,
    git_commit: str | None,
    started_utc: str,
    finished_utc: str,
    completed: bool,
    totals: dict,
    note: str | None = None,
) -> None:
    """Write manifest.json for one run (CONTRACTS.md section 7).

    ``devices`` is a sequence of objects with ``device_type`` and
    ``device_uuid`` attributes (DeviceSpec). ``broker`` must already be
    secret-free: host, port, tls, ca_cert only. ``note`` carries an
    optional scenario scope statement (used by dropout-reconnect); it is
    always emitted, as JSON null when absent, so the manifest shape is
    stable across scenarios.
    """
    forbidden = {"username", "password"} & {k.lower() for k in broker}
    if forbidden:
        raise ValueError(f"broker description must not contain secrets: {forbidden}")
    manifest = {
        "protocol_version": PROTOCOL_VERSION,
        "simulator_version": __version__,
        "scenario": scenario,
        "seed": seed,
        "run_id": run_id,
        "egw_id": egw_id,
        "devices": [
            {"device_type": d.device_type, "device_uuid": d.device_uuid}
            for d in devices
        ],
        "rates_hz": {
            "aggregate": aggregate_rate_hz,
            "per_device": dict(per_device_rates_hz),
        },
        "duration_s": duration_s,
        "qos": qos,
        "broker": dict(broker),
        "git_commit": git_commit,
        "started_utc": started_utc,
        "finished_utc": finished_utc,
        "completed": completed,
        "totals": dict(totals),
        "note": note,
    }
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(manifest, fh, indent=2)
        fh.write("\n")
