"""The identity accounting of one nominal run (tools/session/nominal_account.py).

The script under test is the repository file itself, run exactly as nominal.sh
runs it: three positional arguments (the raw run directory, the post-drain
event log and the output directory) and ``<out>/accounting.json`` written.
Only the logs it reads are built here, in a temporary directory; nothing of the
guest, QEMU, the controller or the network takes part.

What these cases are about (project review of 2026-09-19, finding of
2026-09-20): an accepted record whose ``ditto_ack_monotonic_ns`` the controller
never emitted has no instant to compare with the confirmation deadline. Reading
it as 0 -- the earliest instant there is -- silently moved such an identity from
"late" to "in time" in both the harness-fetch and the after-drain counts, the
two the project manager's delivery split is read from. It now has a bucket of
its own and is counted neither in time nor late.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

SRC_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = SRC_DIR.parent
SCRIPT = REPO_ROOT / "tools" / "session" / "nominal_account.py"
if not SCRIPT.is_file():
    pytest.skip(f"{SCRIPT} is not in this tree", allow_module_level=True)

RUN = "nominal-demo"
#: The controller-clock instant the harness judges a confirmation by.
DEADLINE = 1_000_000

#: One published identity per case, with the outcome record the event log
#: holds for it: the two shapes with no ack instant, one confirmed before the
#: deadline and one after it.
RECORDS = {
    "no-ack-field": {"outcome": "accepted"},
    "null-ack": {"outcome": "accepted", "ditto_ack_monotonic_ns": None},
    "in-time": {"outcome": "accepted", "ditto_ack_monotonic_ns": DEADLINE - 1},
    "late": {"outcome": "accepted", "ditto_ack_monotonic_ns": DEADLINE + 1},
}


def _capsule(
    directory: Path,
    *,
    records: dict[str, dict] | None = None,
    deadline: int | None = DEADLINE,
    device_type: str = "sensor",
) -> tuple[Path, Path, Path]:
    """One raw run directory, its post-drain log and an output directory.

    Every key of ``records`` is a published (valid) identity; its value is the
    outcome record the event logs carry for it. An identity without a record is
    simply absent from the logs.
    """
    records = RECORDS if records is None else records
    raw = directory / "raw"
    raw.mkdir(parents=True, exist_ok=True)
    manifest = {
        "run_id": RUN,
        "confirmation_deadline_clock_domain": "controller",
        "validity": "valid",
    }
    if deadline is not None:
        manifest["confirmation_deadline_monotonic_ns"] = deadline
    (raw / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    (raw / "sent_events.jsonl").write_text(
        "".join(
            json.dumps(
                {"run_id": RUN, "message_id": key, "device_type": device_type}
            )
            + "\n"
            for key in records
        ),
        encoding="utf-8",
    )
    events = "".join(
        json.dumps({"run_id": RUN, "message_id": key, **record}) + "\n"
        for key, record in records.items()
    )
    (raw / "events.jsonl").write_text(events, encoding="utf-8")
    post = directory / "events.post-drain.jsonl"
    post.write_text(events, encoding="utf-8")
    return raw, post, directory / "analysis"


def _account(raw: Path, post: Path, out: Path) -> tuple[dict, str]:
    """Run the script as nominal.sh does; returns (report, stdout)."""
    env = dict(os.environ)
    env["PYTHONPATH"] = os.pathsep.join(
        [str(SRC_DIR), env["PYTHONPATH"]] if env.get("PYTHONPATH") else [str(SRC_DIR)]
    )
    result = subprocess.run(
        [sys.executable, str(SCRIPT), str(raw), str(post), str(out)],
        capture_output=True, text=True, timeout=300, check=False, env=env,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    report = json.loads((out / "accounting.json").read_text(encoding="utf-8"))
    return report, result.stdout


def test_an_accepted_identity_without_an_ack_instant_is_never_in_time(
    tmp_path,
) -> None:
    """The count nominal.sh reports, at the fetch and after the drain."""
    report, stdout = _account(*_capsule(tmp_path))
    for where in ("at_harness_fetch", "after_drain"):
        assert report[where] == {
            "accepted_no_ack_time": 2,
            "accepted_in_time": 1,
            "accepted_late": 1,
        }, where
    assert report["published_valid_identities"] == 4
    assert report["accepted_without_ack_instant_at_fetch"] == 2
    assert report["accepted_without_ack_instant_after_drain"] == 2
    # Per device as well: the bucket is not lost on the way to the breakdown.
    assert report["at_harness_fetch_per_device"]["sensor"][
        "accepted_no_ack_time"
    ] == 2
    # The printed summary names the bucket, whatever the counts hold.
    assert stdout.count(
        "accepted with no ack instant (never counted as confirmed in time): 2"
    ) == 2


def test_a_run_whose_acks_are_all_real_is_counted_as_before(tmp_path) -> None:
    """The shape of the sealed nominal-r01 run: every accepted record carries
    a real ack instant, so the buckets are the two the harness row is read
    from and the new one is reported as zero."""
    records = {
        "in-time": RECORDS["in-time"],
        "late": RECORDS["late"],
        "no-outcome": None,
    }
    raw, post, out = _capsule(
        tmp_path, records={k: v for k, v in records.items() if v is not None}
    )
    # The third identity was published and never answered.
    (raw / "sent_events.jsonl").write_text(
        (raw / "sent_events.jsonl").read_text(encoding="utf-8")
        + json.dumps(
            {"run_id": RUN, "message_id": "no-outcome", "device_type": "sensor"}
        )
        + "\n",
        encoding="utf-8",
    )
    report, _stdout = _account(raw, post, out)
    assert report["at_harness_fetch"] == {
        "accepted_in_time": 1,
        "accepted_late": 1,
        "no_outcome": 1,
    }
    assert report["accepted_without_ack_instant_at_fetch"] == 0
    assert report["accepted_without_ack_instant_after_drain"] == 0


@pytest.mark.parametrize("ack", [None, True], ids=["null", "bool"])
def test_an_ack_that_is_not_a_number_is_no_instant(tmp_path, ack: object) -> None:
    """Whatever the controller wrote instead of an instant, it is not read as
    one: a boolean is not a nanosecond count either, although Python would
    happily compare it with the deadline.

    A value of another type altogether (a string, a list, an object) cannot be
    exercised through the script: ``compute_run_metrics``
    (``src/egw_experiments/analyze.py``, which this accounting only reports)
    compares it with the deadline itself and raises first.
    """
    report, _stdout = _account(
        *_capsule(
            tmp_path,
            records={
                "odd": {"outcome": "accepted", "ditto_ack_monotonic_ns": ack}
            },
        )
    )
    assert report["at_harness_fetch"] == {"accepted_no_ack_time": 1}


def test_without_a_deadline_an_ack_less_identity_is_still_apart(tmp_path) -> None:
    """A manifest without a confirmation deadline leaves every confirmation
    late (unchanged); the identities with no instant at all stay in their own
    bucket, so the two reasons are never mixed."""
    report, _stdout = _account(*_capsule(tmp_path, deadline=None))
    assert report["at_harness_fetch"] == {
        "accepted_no_ack_time": 2,
        "accepted_late": 2,
    }
