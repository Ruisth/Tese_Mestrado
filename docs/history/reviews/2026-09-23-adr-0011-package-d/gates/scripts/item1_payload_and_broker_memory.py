"""Item 1 (broker limits): read-only figures.

Block A - the size of the real telemetry payloads and topics of `nominal-r01`,
regenerated with the repository's own simulator code (src/egw_simulator at the
checked-out tree, identical to 35fe8bb for that directory) from the seed, run
id, egw id and device set recorded in the run's simulator manifest. Only the
`ts` field is not reproducible (wall clock); its length is fixed by
rfc3339_utc_ms, so a fixed timestamp of the same format is injected.

Block B - the broker container's memory as sampled by the collector in the
three preserved runs (nominal-r01, controller_restart-r01, -r02).

Nothing is written except this script's stdout. No guest is contacted.
"""

from __future__ import annotations

import csv
import json
import statistics
import sys
from collections import Counter
from pathlib import Path

REPO_SRC = Path("/home/ruisth/egw-exec/repo/src")
RAW = Path("/home/ruisth/egw-tcg/pilot/results/raw")
sys.path.insert(0, str(REPO_SRC))

from egw_simulator.devices import make_devices  # noqa: E402
from egw_simulator.envelope import build_envelope  # noqa: E402
from egw_simulator.profiles import make_profile  # noqa: E402
from egw_simulator.runner import TOPIC_TEMPLATE  # noqa: E402

MiB = 2**20


def block_a() -> None:
    run = RAW / "nominal-r01"
    sim = json.loads((run / "logs/simulator/nominal-r01/manifest.json").read_text())
    seed, run_id, egw_id = sim["seed"], sim["run_id"], sim["egw_id"]
    types = [d["device_type"] for d in sim["devices"]]
    devices = make_devices(seed, types)
    recorded = {d["device_type"]: d["device_uuid"] for d in sim["devices"]}
    for dev in devices:
        assert dev.device_uuid == recorded[dev.device_type], "device uuid mismatch"
    sent = Counter()
    ids = {}
    with (run / "sent_events.jsonl").open() as fh:
        for line in fh:
            r = json.loads(line)
            sent[r["device_type"]] += 1
            ids[(r["device_uuid"], r["seq"])] = r["message_id"]
    fixed_ts = "2026-09-19T20:02:45.797Z"  # same format and length as rfc3339_utc_ms
    sizes = {}
    topic_len = {}
    mismatched_ids = 0
    for dev in devices:
        profile = make_profile(dev.device_type, seed, dev.device_uuid)
        per = []
        for seq in range(sent[dev.device_type]):
            payload = build_envelope(
                run_id=run_id,
                egw_id=egw_id,
                device_uuid=dev.device_uuid,
                device_type=dev.device_type,
                seq=seq,
                ts=fixed_ts,
            )
            payload.update(profile.next())
            if ids.get((dev.device_uuid, seq)) != payload["message_id"]:
                mismatched_ids += 1
            per.append(len(json.dumps(payload, separators=(",", ":")).encode("utf-8")))
        sizes[dev.device_type] = per
        topic_len[dev.device_type] = len(
            TOPIC_TEMPLATE.format(egw_id=egw_id, device_uuid=dev.device_uuid).encode("utf-8")
        )
    allp = [s for v in sizes.values() for s in v]
    print("[A.0] run", run_id, "seed", seed, "egw_id", egw_id, "devices", types)
    print("[A.1] identities regenerated", len(allp), "sent_events rows", sum(sent.values()),
          "message_id mismatches", mismatched_ids)
    for t, v in sizes.items():
        print(f"[A.2] {t}: n={len(v)} payload bytes min={min(v)} median={statistics.median(v)} "
              f"max={max(v)} mean={statistics.fmean(v):.1f}; topic bytes={topic_len[t]}")
    print(f"[A.3] all: payload bytes min={min(allp)} median={statistics.median(allp)} "
          f"max={max(allp)} mean={statistics.fmean(allp):.1f} sum={sum(allp)}")
    tmax = max(topic_len.values())
    for n in (3593, 4999, 5000, 9999):
        print(f"[A.4] {n} messages x max payload {max(allp)} B = {n * max(allp)} B "
              f"= {n * max(allp) / MiB:.3f} MiB; with max topic {tmax} B: "
              f"{n * (max(allp) + tmax) / MiB:.3f} MiB")
    budget = 128 * MiB
    for n in (3593, 4999):
        print(f"[A.5] 128 MiB / {n} = {budget / n:.1f} B per message "
              f"(= {budget / n / 1024:.2f} KiB), before any baseline is subtracted")


def block_b() -> None:
    for run in ("nominal-r01", "controller_restart-r01", "controller_restart-r02"):
        path = RAW / run / "logs/collector" / f"resources-{run}.csv"
        rows = [r for r in csv.DictReader(path.open()) if r["container"].endswith("mosquitto-1")]
        mem = [int(r["mem_bytes"]) for r in rows]
        pct = [float(r["mem_pct"]) for r in rows]
        imax = max(range(len(mem)), key=mem.__getitem__)
        print(f"[B.{run}] file {path}; broker rows {len(rows)} "
              f"({rows[0]['ts_utc']} .. {rows[-1]['ts_utc']}); mem_bytes min={min(mem)} "
              f"median={statistics.median(mem)} max={max(mem)} at {rows[imax]['ts_utc']} "
              f"({min(mem) / MiB:.2f} / {statistics.median(mem) / MiB:.2f} / {max(mem) / MiB:.2f} MiB); "
              f"mem_pct max={max(pct)}; implied memory.max={max(mem) / max(pct) * 100 / MiB:.2f} MiB")


if __name__ == "__main__":
    block_a()
    block_b()
