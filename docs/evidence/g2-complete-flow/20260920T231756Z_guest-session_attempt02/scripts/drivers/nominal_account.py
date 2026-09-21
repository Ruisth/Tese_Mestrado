"""Account for every published identity of one harness run, at the harness fetch and after the drain.

Usage: nominal_account.py <raw run dir> <post-drain events.jsonl> <out dir>
                          [fetched|not-fetched|unknown]

The harness judges delivery on the events it fetched right after the 60 s
confirmation window (its sealed events.jsonl): a confirmation after the
controller-clock deadline is LATE, one with no record is LOST. This script
reports that row unchanged (compute_run_metrics), then follows each published
identity to the log fetched after the drain, so that "lost at the deadline"
can be told apart from "confirmed later" and from "no outcome at all".
Nothing here changes a count of the harness row. A post-drain log that was not
fetched, or not fetched completely, is recorded as such and every figure of
that tail is left null: a log nobody read is not an empty one, a transfer that
died mid-way is not a complete tail, and no eventual delivery is claimed from
either. Whether that fetch SUCCEEDED is the fourth argument, because it is what
the driver knows and what the file being on disk does not say; with no fourth
argument nothing is claimed either way and the log is reported as it was found,
which `after_drain_fetch` and `after_drain_note` then say. `nominal.sh` always
passes it. What that field publishes is the driver's claim only while there is
a log to make it about: a log that is not on disk is reported as `not-found`,
because a tail nobody can point at was not fetched, whatever the step said.

An accepted record whose ack instant the controller never emitted is counted
in its own bucket, ACCEPTED_NO_ACK: a missing ditto_ack_monotonic_ns is not an
instant, least of all the earliest one, so such an identity is never counted as
confirmed in time (2026-09-20).
"""
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

from egw_experiments.analyze import compute_run_metrics

raw, post, out = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3])
#: What the driver knows about its own fetch of the post-drain log: 'fetched'
#: (the transfer succeeded), 'not-fetched' (it failed or was never made),
#: 'unknown' (the step's own result could not be read) or, with no fourth
#: argument, 'unstated': the caller made no claim either way.
fetch = sys.argv[4] if len(sys.argv) > 4 else "unstated"
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
#: A post-drain log that is NOT THERE is not an empty one, and one whose
#: transfer did not succeed is not a complete tail: a fetch that failed would
#: otherwise leave every published identity counted as 'no outcome' against a
#: log nobody read, or the tail of a partial file read as the whole of it.
#: Either way the case is named and every figure of that tail is left null.
NOT_FETCHED = ("the post-drain event log was not fetched: no tail after the drain "
               "was observed, and none is claimed here")
NOT_FOUND = ("the driver reports the post-drain event log as fetched and it is not there: no "
             "tail after the drain was found, and none is claimed here")
PARTIAL = ("the post-drain event log is on disk but its fetch did not succeed: what it "
           "holds may be a partial tail, and no figure is claimed from it")
UNSTATED = ("whether the post-drain event log was fetched completely could not be "
            "established: what it holds may be a partial tail, and no figure is claimed "
            "from it")
AS_FOUND = ("nothing was said about the fetch of the post-drain event log, so the figures "
            "of that tail are of the log as it was found on disk; nominal.sh always says")
#: What is published as ``after_drain_fetch``: what the driver said, except
#: where the log it would be said of is not on disk at all. A tail that is not
#: there was not fetched, whatever the step reported, so what is published then
#: is what was FOUND and never the claim about it.
reported = fetch
if not post.is_file():
    tail_note, post_fetched, reported = NOT_FETCHED, False, "not-found"
    if fetch == "fetched":
        tail_note = NOT_FOUND
elif fetch == "fetched":
    tail_note, post_fetched = None, True
elif fetch == "unstated":
    # No fourth argument: the caller claimed nothing either way, so the log is
    # reported as it was found and the note says exactly that.
    tail_note, post_fetched = AS_FOUND, True
elif fetch == "not-fetched":
    tail_note, post_fetched = PARTIAL, False
else:
    # 'unknown', and anything else this script cannot read: nothing was
    # established, so no figure of that tail is published.
    tail_note, post_fetched = UNSTATED, False
after = [r for r in load(post) if r.get("run_id") == run_id]


#: Accepted, with no instant to judge the acceptance by.
ACCEPTED_NO_ACK = "accepted_no_ack_time"


def ack_instants(events):
    """The ditto_ack_monotonic_ns readings of ``events`` that are real instants.

    An absent, null or non-numeric reading is no instant at all: it is dropped
    here rather than read as 0, the earliest instant there is, which would
    count the identity as confirmed before any deadline."""
    values = []
    for e in events:
        value = e.get("ditto_ack_monotonic_ns")
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            values.append(value)
    return values


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
            acks = ack_instants(acc)
            if not acks:
                key = ACCEPTED_NO_ACK
            elif deadline is not None and min(acks) <= deadline:
                key = "accepted_in_time"
            else:
                key = "accepted_late"
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
    "after_drain": drain_counts if post_fetched else None,
    "after_drain_per_device": drain_devices if post_fetched else None,
    "after_drain_fetch": reported,
    "after_drain_note": tail_note,
    # Named on their own, so that a bucket of zero is stated and not simply
    # absent from the counts above.
    "accepted_without_ack_instant_at_fetch": fetch_counts.get(ACCEPTED_NO_ACK, 0),
    "accepted_without_ack_instant_after_drain":
        drain_counts.get(ACCEPTED_NO_ACK, 0) if post_fetched else None,
    "accepted_without_ack_instant_note": (
        "accepted identities whose ditto_ack_monotonic_ns the controller did not emit: "
        "there is no instant to compare with the deadline, so they are counted neither "
        "in time nor late"),
    "events_records_at_fetch": len(at_fetch),
    "events_records_after_drain": len(after) if post_fetched else None,
}
(out / "accounting.json").write_text(json.dumps(report, indent=2, default=str) + "\n", encoding="utf-8")
print(json.dumps(report, indent=2, default=str))
for where, counts in (("at the harness fetch", fetch_counts), ("after the drain", drain_counts)):
    if where == "after the drain" and not post_fetched:
        print(f"{run_id} after the drain: {tail_note}")
        continue
    print(f"{run_id} {where}: {len(valid)} published valid identities -> "
          + (", ".join(f"{key}={counts[key]}" for key in sorted(counts)) or "nothing")
          + f"; accepted with no ack instant (never counted as confirmed in time): "
          + str(counts.get(ACCEPTED_NO_ACK, 0)))
