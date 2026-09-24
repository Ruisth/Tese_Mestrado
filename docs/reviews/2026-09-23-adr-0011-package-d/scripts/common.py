"""Shared, read-only loaders and clock anchors for the package-D v2 scripts.

Every source is opened read-only; nothing is written anywhere except to
standard output by the calling script. Standard library only.

Clock domains (never mixed for latency):
  controller monotonic  events.jsonl, events.post-drain.jsonl, warmup.events.jsonl
  harness monotonic     sent_events.jsonl
  harness wall (UTC)    controller_metrics.csv ts_utc, manifest *_utc, commands.jsonl
  guest wall (UTC)      resources.csv ts_utc (written inside the guest)
"""

from __future__ import annotations

import csv
import json
import math
from datetime import datetime, timezone
from pathlib import Path

RAW = Path("/home/ruisth/egw-tcg/pilot/results/raw/nominal-r01")
ATT = Path(
    "/home/ruisth/egw-exec/attempts/"
    "20260919T195827Z_nominal-instrumentation-120-600_attempt01"
)
ANA = ATT / "analysis"
NS = 1_000_000_000


def jsonl(path: Path) -> list[dict]:
    with path.open("r", encoding="utf-8") as fh:
        return [json.loads(line) for line in fh if line.strip()]


def raw_lines(path: Path) -> list[str]:
    with path.open("r", encoding="utf-8") as fh:
        return [line.rstrip("\n") for line in fh if line.strip()]


def iso(ts: str) -> float:
    """ISO-8601 UTC string -> POSIX seconds (float)."""
    return datetime.fromisoformat(ts.replace("Z", "+00:00")).timestamp()


def utc(t: float) -> str:
    return (
        datetime.fromtimestamp(t, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3]
        + "Z"
    )


def pct(values, p: float):
    """The harness's own percentile (analyze.py:499-516): linear interpolation,
    rank = (n-1)*p/100 on the sorted sample (numpy's default)."""
    if not values:
        return None
    s = sorted(values)
    if len(s) == 1:
        return float(s[0])
    rank = (len(s) - 1) * (p / 100.0)
    lo, hi = math.floor(rank), math.ceil(rank)
    if lo == hi:
        return float(s[lo])
    return float(s[lo] + (s[hi] - s[lo]) * (rank - lo))


def mean(v):
    v = list(v)
    return sum(v) / len(v) if v else float("nan")


def pearson(x, y):
    n = len(x)
    mx, my = sum(x) / n, sum(y) / n
    sxy = sum((a - mx) * (b - my) for a, b in zip(x, y))
    sxx = sum((a - mx) ** 2 for a in x)
    syy = sum((b - my) ** 2 for b in y)
    return sxy / math.sqrt(sxx * syy)


class Run:
    """All sources of nominal-r01 plus the anchors, loaded once."""

    def __init__(self) -> None:
        self.manifest = json.loads((RAW / "manifest.json").read_text())
        self.accounting = json.loads((ANA / "accounting.json").read_text())
        m = self.manifest
        self.ctrl_end = m["controller_monotonic_at_run_end_ns"]
        self.host_start = m["measured_started_monotonic_ns"]
        self.host_end = m["finished_monotonic_ns"]
        self.host_dur_ns = self.host_end - self.host_start
        self.ctrl_start = self.ctrl_end - self.host_dur_ns
        self.deadline = m["confirmation_deadline_monotonic_ns"]
        mk = m["controller_marker"]
        # harness wall at which the marker was polled <-> controller monotonic
        self.marker_host_wall = iso(mk["polled_utc"])
        # the controller's own (guest) wall clock at the same reading
        self.marker_guest_wall = iso(mk["wall_utc"])
        self.win_start_wall = iso(m["measured_window_utc"]["start"])
        self.win_end_wall = iso(m["measured_window_utc"]["end"])

        self.sent = jsonl(RAW / "sent_events.jsonl")
        self.sealed = jsonl(RAW / "events.jsonl")
        self.post = jsonl(ANA / "events.post-drain.jsonl")
        self.warm = jsonl(ANA / "warmup.events.jsonl")

    # --- clock helpers ---------------------------------------------------
    def el(self, ctrl_ns: int) -> float:
        """Seconds since the window start, controller domain."""
        return (ctrl_ns - self.ctrl_start) / NS

    def ctrl_to_host_wall(self, ctrl_ns: int) -> float:
        return self.marker_host_wall + (ctrl_ns - self.ctrl_end) / NS

    def ctrl_to_guest_wall(self, ctrl_ns: int) -> float:
        return self.marker_guest_wall + (ctrl_ns - self.ctrl_end) / NS

    def host_wall_to_ctrl(self, t: float) -> int:
        return self.ctrl_end + round((t - self.marker_host_wall) * NS)

    # --- other sources ---------------------------------------------------
    @staticmethod
    def metrics_csv() -> list[dict]:
        out = []
        with (RAW / "controller_metrics.csv").open("r", newline="") as fh:
            for r in csv.DictReader(fh):
                d = {k: int(v) for k, v in r.items() if k != "ts_utc"}
                d["t"] = iso(r["ts_utc"])
                d["ts_utc"] = r["ts_utc"]
                out.append(d)
        return out

    @staticmethod
    def resources_csv() -> list[dict]:
        out = []
        with (RAW / "resources.csv").open("r", newline="") as fh:
            for r in csv.DictReader(fh):
                out.append(
                    {
                        "t": iso(r["ts_utc"]),
                        "ts_utc": r["ts_utc"],
                        "container": r["container"],
                        "cpu": float(r["cpu_pct"]),
                        "mem": int(r["mem_bytes"]),
                        "mem_pct": float(r["mem_pct"]),
                    }
                )
        return out

    @staticmethod
    def commands() -> list[dict]:
        return jsonl(ATT / "commands.jsonl")

    @staticmethod
    def snapshot(label: str) -> dict:
        return json.loads(
            (ANA / "snapshots" / f"nominal-r01.metrics.{label}.json").read_text()
        )

    # --- merged service sequence -----------------------------------------
    def all_messages(self) -> list[dict]:
        """Warm-up + measured records, each tagged, sorted by arrival."""
        msgs = []
        for e in self.warm:
            msgs.append(dict(e, phase="warmup"))
        for e in self.post:
            msgs.append(dict(e, phase="measured"))
        msgs.sort(key=lambda e: e["received_monotonic_ns"])
        return msgs


def header(title: str) -> None:
    print()
    print("=" * 78)
    print(title)
    print("=" * 78)
