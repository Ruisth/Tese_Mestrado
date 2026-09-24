"""Independent loaders for the refutation pass (package D, v2 verification).

Written from the raw files, NOT importing the v2 scripts' common.py.
Every source is opened read-only; the scripts print to standard output only.
Standard library only.
"""
from __future__ import annotations

import bisect
import csv
import json
import math
from datetime import datetime, timezone
from pathlib import Path

NOM = Path("/home/ruisth/egw-tcg/pilot/results/raw/nominal-r01")
ATT = Path("/home/ruisth/egw-exec/attempts/"
           "20260919T195827Z_nominal-instrumentation-120-600_attempt01")
ANA = ATT / "analysis"
R01 = Path("/home/ruisth/egw-tcg/pilot/results/raw/controller_restart-r01")
R02 = Path("/home/ruisth/egw-tcg/pilot/results/raw/controller_restart-r02")
NS = 10**9


def rj(p):
    with open(p, "r", encoding="utf-8") as fh:
        return json.load(fh)


def rjl(p):
    out = []
    with open(p, "r", encoding="utf-8") as fh:
        for line in fh:
            if line.strip():
                out.append(json.loads(line))
    return out


def ts(s: str) -> float:
    return datetime.fromisoformat(s.replace("Z", "+00:00")).timestamp()


def iso(t: float) -> str:
    return datetime.fromtimestamp(t, tz=timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def q(values, p):
    """numpy-default linear percentile, written independently."""
    s = sorted(values)
    n = len(s)
    if n == 0:
        return None
    h = (n - 1) * p / 100.0
    i = int(math.floor(h))
    j = min(i + 1, n - 1)
    return s[i] + (s[j] - s[i]) * (h - i)


def avg(v):
    v = list(v)
    return sum(v) / len(v)


def corr(x, y):
    n = len(x)
    mx = sum(x) / n
    my = sum(y) / n
    a = sum((u - mx) * (w - my) for u, w in zip(x, y))
    b = math.sqrt(sum((u - mx) ** 2 for u in x) * sum((w - my) ** 2 for w in y))
    return a / b


def metrics_rows(path):
    rows = []
    with open(path, "r", newline="", encoding="utf-8") as fh:
        for i, r in enumerate(csv.DictReader(fh), start=2):  # file line number
            d = {"line": i, "ts_utc": r["ts_utc"], "t": ts(r["ts_utc"])}
            for k, v in r.items():
                if k != "ts_utc":
                    d[k] = int(v)
            rows.append(d)
    return rows


def res_rows(path):
    rows = []
    with open(path, "r", newline="", encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            rows.append({"t": ts(r["ts_utc"]), "ts_utc": r["ts_utc"], "c": r["container"],
                         "cpu": float(r["cpu_pct"]), "mem": int(r["mem_bytes"]),
                         "memp": float(r["mem_pct"])})
    return rows


class Nominal:
    def __init__(self):
        m = rj(NOM / "manifest.json")
        self.m = m
        self.end_c = m["controller_monotonic_at_run_end_ns"]
        self.h0 = m["measured_started_monotonic_ns"]
        self.h1 = m["finished_monotonic_ns"]
        self.dur_ns = self.h1 - self.h0
        self.start_c = self.end_c - self.dur_ns        # window start, controller clock
        self.deadline = m["confirmation_deadline_monotonic_ns"]
        self.mk_host = ts(m["controller_marker"]["polled_utc"])
        self.mk_guest = ts(m["controller_marker"]["wall_utc"])
        self.win0 = ts(m["measured_window_utc"]["start"])
        self.win1 = ts(m["measured_window_utc"]["end"])
        self.sent = rjl(NOM / "sent_events.jsonl")
        self.sealed = rjl(NOM / "events.jsonl")
        self.post = rjl(ANA / "events.post-drain.jsonl")
        self.warm = rjl(ANA / "warmup.events.jsonl")
        self.acct = rj(ANA / "accounting.json")
        self.cmds = rjl(ATT / "commands.jsonl")
        self.snap_before = rj(ANA / "snapshots" / "nominal-r01.metrics.before.json")
        self.snap_after = rj(ANA / "snapshots" / "nominal-r01.metrics.after.json")

    def el(self, c_ns):
        return (c_ns - self.start_c) / NS

    def el_host(self, h_ns):
        return (h_ns - self.h0) / NS

    def c2hw(self, c_ns):
        """controller monotonic -> harness wall, through the end marker."""
        return self.mk_host + (c_ns - self.end_c) / NS

    def hw2c(self, t):
        return self.end_c + (t - self.mk_host) * NS

    def c2gw(self, c_ns):
        return self.mk_guest + (c_ns - self.end_c) / NS

    def gw2c(self, t):
        return self.end_c + (t - self.mk_guest) * NS

    def merged(self):
        allm = [dict(e, _ph="w") for e in self.warm] + [dict(e, _ph="m") for e in self.post]
        allm.sort(key=lambda e: e["received_monotonic_ns"])
        return allm


class Counter1D:
    """count of sorted stamps <= x."""

    def __init__(self, stamps):
        self.s = sorted(stamps)

    def le(self, x):
        return bisect.bisect_right(self.s, x)

    def lt(self, x):
        return bisect.bisect_left(self.s, x)

    def between(self, a, b):
        """a < s <= b"""
        return self.le(b) - self.le(a)


def interp_counter(rows, key, t):
    """Linear interpolation of a cumulative counter at harness wall t."""
    ts_ = [r["t"] for r in rows]
    i = bisect.bisect_right(ts_, t)
    if i == 0:
        return float(rows[0][key])
    if i >= len(rows):
        return float(rows[-1][key])
    a, b = rows[i - 1], rows[i]
    if b["t"] == a["t"]:
        return float(b[key])
    return a[key] + (b[key] - a[key]) * (t - a["t"]) / (b["t"] - a["t"])


def hdr(s):
    print()
    print("#" * 78)
    print("# " + s)
    print("#" * 78)
