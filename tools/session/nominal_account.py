"""Account for every published identity of one harness run, at the harness fetch and after the drain.

Usage: nominal_account.py <raw run dir> <post-drain events.jsonl> <out dir>

The harness judges delivery on the events it fetched right after the 60 s
confirmation window (its sealed events.jsonl): a confirmation after the
controller-clock deadline is LATE, one with no record is LOST. This script
reports that row unchanged (compute_run_metrics), then follows each published
identity to the log fetched after the drain, so that "lost at the deadline"
can be told apart from "confirmed later" and from "no outcome at all".
Nothing here changes a count of the harness row.
"""
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

from egw_experiments.analyze import compute_run_metrics

raw, post, out = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3])
out.mkdir(parents=True, exist_ok=True)
manifest = json.loads((raw / "manifest.json").read_text(encoding="utf-8"))
deadline = manifest.get("confirmation_deadline_monotonic_ns")
run_id = manifest["run_id"]


def load(path):
    rows = []
    if path.is_file():
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                rows.append(json.loads(line))
    return rows


sent = [r for r in load(raw / "sent_events.jsonl") if r.get("run_id") == run_id]
valid = [r for r in sent if not r.get("intended_invalid")]
at_fetch = [r for r in load(raw / "events.jsonl") if r.get("run_id") == run_id]
after = [r for r in load(post) if r.get("run_id") == run_id]


def classify(events):
    by_id = defaultdict(list)
    for e in events:
        by_id[e["message_id"]].append(e)
    result = Counter()
    per_device = defaultdict(Counter)
    for s in valid:
        outs = by_id.get(s["message_id"], [])
        acc = [e for e in outs if e.get("outcome") == "accepted"]
        if acc:
            ack = min(e.get("ditto_ack_monotonic_ns") or 0 for e in acc)
            key = "accepted_in_time" if deadline is not None and ack <= deadline else "accepted_late"
        elif outs:
            key = "other_outcome:" + ",".join(sorted({e.get("outcome", "?") for e in outs}))
        else:
            key = "no_outcome"
        result[key] += 1
        per_device[s["device_type"]][key] += 1
    return dict(result), {k: dict(v) for k, v in per_device.items()}


row = compute_run_metrics(raw) or {}
row.pop("_resources", None)
fetch_counts, fetch_devices = classify(at_fetch)
drain_counts, drain_devices = classify(after)
report = {
    "run_id": run_id,
    "label": "ARM64 EMULATED (QEMU/TCG); diagnostic accounting, not a campaign result",
    "manifest_validity": manifest.get("validity"),
    "manifest_validity_reasons": manifest.get("validity_reasons"),
    "confirmation_deadline_clock_domain": manifest.get("confirmation_deadline_clock_domain"),
    "controller_marker": manifest.get("controller_marker"),
    "harness_row": {k: row.get(k) for k in (
        "confirmation_deadline_source", "sent_total", "sent_valid", "delivered_unique", "lost",
        "late_confirmations", "duplicates", "double_accepted", "failed", "intended_invalid_accepted",
        "latency_ms_p50", "latency_ms_p95", "latency_ms_max", "warnings")},
    "published_valid_identities": len(valid),
    "at_harness_fetch": fetch_counts,
    "at_harness_fetch_per_device": fetch_devices,
    "after_drain": drain_counts,
    "after_drain_per_device": drain_devices,
    "events_records_at_fetch": len(at_fetch),
    "events_records_after_drain": len(after),
}
(out / "accounting.json").write_text(json.dumps(report, indent=2, default=str) + "\n", encoding="utf-8")
print(json.dumps(report, indent=2, default=str))
