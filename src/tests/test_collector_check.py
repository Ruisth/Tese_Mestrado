"""Fail-closed cases for tools/session/collector_check.py (F3, project review of 2026-09-19).

The script under test is the repository file itself, run exactly as the
preflight driver runs it: five positional arguments, exit 0 (no problem) or 1
(any problem), and ``<dir>/collector-check.json`` written either way. Only the
fetched collector output it reads is built here, in a temporary directory;
nothing of the guest, QEMU, Docker or the network takes part.

The positive case is a genuine one: its CSV really passes
``validate_resources_csv`` for the collector's own start..stop window (the
6-column header, 44 distinct instants per service, every host equal to the SUT
node, 95 % of the window covered and no gap above MAX_SAMPLE_GAP_S), and its
closing record accounts for every sampling round it took. Removing one record
from its diagnostics, or one counter from its closing summary, is therefore the
whole difference between the run that was accepted and the one that must not be.
"""
from __future__ import annotations

import importlib.util
import itertools
import json
import os
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path

import pytest

import egw_experiments.resources as resources_mod
import egw_experiments.run as run_mod

SRC_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = SRC_DIR.parent
SCRIPT = REPO_ROOT / "tools" / "session" / "collector_check.py"
if not SCRIPT.is_file():
    pytest.skip(f"{SCRIPT} is not in this tree", allow_module_level=True)

RUN = "preflight-r01"
NODE = "egw-sut"
SHA = "ab" * 32
SERVICES = ["egw-controller-1", "egw-mosquitto-1"]
#: The collector's own bounds: its start line opens the window, its closing
#: summary closes it. The samples sit strictly inside, one second apart.
WINDOW_START = "2026-09-07T10:00:00Z"
WINDOW_END = "2026-09-07T10:00:45Z"
SAMPLE_SECONDS = range(1, 45)

#: The counters of the closing summary, in the order collect-resources.sh
#: writes them: the samples it took, then what it could not measure.
STOP_FIELDS = (
    ("samples", str(len(SAMPLE_SECONDS))),
    ("utc_gap_seconds", "0"),
    ("withheld_samples", "0"),
    ("withheld_elapsed_s", "0.00"),
    ("withheld_runs_unmeasured", "0"),
    ("withheld_open_at_stop", "0"),
)
#: The figures whose absence or 'unknown' leaves the record unreadable: every
#: one the closing summary writes beside its sample count.
COUNTERS = tuple(name for name, _ in STOP_FIELDS if name != "samples")
#: What each figure reads as when the closing summary is complete and nothing
#: was withheld.
CLEAN_COUNTERS = {name: default for name, default in STOP_FIELDS if name != "samples"}


def _stop(drop: str | None = None, **fields: object) -> str:
    """The closing summary, with the named counters replaced or one dropped.

    The default accounts for every sampling round: 44 samples, none withheld,
    no forward UTC gap and no run of withheld samples open at the stop."""
    written = [
        (name, str(fields.get(name, default)))
        for name, default in STOP_FIELDS
        if name != drop
    ]
    return (
        f"{WINDOW_END} stop: "
        + " ".join(f"{name}={value}" for name, value in written)
        + " calibrations=1 pacing=wall-clock"
    )


#: The three records collect-resources.sh writes through diag(), as it writes
#: them: the timestamp, a space, then the message.
RECORDS = {
    "start": (
        f"{WINDOW_START} start: collector_sha256={SHA} host={NODE} source=cgroup "
        "interval=1s duration=45s pacing: wall-clock; timestamps: date; "
        f"expected services: {','.join(SERVICES)}"
    ),
    "inventory": (
        f"{WINDOW_END} inventory: observed={','.join(SERVICES)} "
        f"expected={','.join(SERVICES)} missing=none unnamed_ids=0"
    ),
    "stop": _stop(),
}


def _csv_rows(*, host: str = NODE, seconds=SAMPLE_SECONDS, zone: str = "Z") -> str:
    """The collector's CSV. ``zone`` spells the UTC of ``ts_utc``: the guest
    collector writes ``Z`` through awk strftime, and
    ``egw_experiments.resources.parse_csv_timestamp`` -- the parser the ingest
    and validate_resources_csv use on the same cells -- also accepts an
    explicit ``+00:00`` offset."""
    lines = ["ts_utc,container,cpu_pct,mem_bytes,mem_pct,host"]
    for second in seconds:
        for name in SERVICES:
            lines.append(
                f"2026-09-07T10:00:{second:02d}{zone},{name},10.0,1048576,1.0,{host}"
            )
    return "\n".join(lines) + "\n"


def _capsule(
    directory: Path,
    *,
    records: list[str] | None = None,
    csv_text: str | None = None,
    lifecycle: bool = True,
    self_test: bool = False,
    node: str | None = NODE,
    environment: bool = True,
) -> Path:
    """One fetched collector output in ``directory``; returns the environment file.

    ``records`` names the diagnostics lines to write, in order (keys of
    :data:`RECORDS`, or a literal line); the default is the complete set.
    """
    directory.mkdir(parents=True, exist_ok=True)
    base = directory / f"resources-{RUN}.csv"
    base.write_text(_csv_rows() if csv_text is None else csv_text, encoding="utf-8")
    keys = list(RECORDS) if records is None else records
    Path(f"{base}.diagnostics.log").write_text(
        "".join(RECORDS.get(key, key) + "\n" for key in keys), encoding="utf-8"
    )
    if lifecycle:
        Path(f"{base}.lifecycle.csv").write_text(
            "ts_utc,event,container_id,name\n"
            + "".join(
                f"{WINDOW_START},named,{i:012d},{name}\n"
                for i, name in enumerate(SERVICES)
            ),
            encoding="utf-8",
        )
    if self_test:
        Path(f"{base}.self-test").write_text("self_test=1\n", encoding="utf-8")
    sut = directory.parent / "sut_environment.json"
    if environment:
        sut.write_text(
            json.dumps({"node": node, "kernel": "6.6.0"} if node else {"kernel": "6.6.0"}),
            encoding="utf-8",
        )
    return sut


def _check(
    directory: Path,
    sut: Path,
    *,
    expect: str = ",".join(SERVICES),
    want_sha: str = SHA,
    args: list[str] | None = None,
) -> tuple[int, dict]:
    """Run the script as preflight.sh does; returns (exit code, written report)."""
    env = dict(os.environ)
    env["PYTHONPATH"] = os.pathsep.join(
        [str(SRC_DIR), env["PYTHONPATH"]] if env.get("PYTHONPATH") else [str(SRC_DIR)]
    )
    argv = (
        [str(directory), RUN, expect, want_sha, str(sut)] if args is None else args
    )
    result = subprocess.run(
        [sys.executable, str(SCRIPT), *argv],
        capture_output=True, text=True, timeout=300, check=False, env=env,
    )
    assert result.returncode in (0, 1), result.stdout + result.stderr
    report_path = directory / "collector-check.json"
    assert report_path.is_file(), result.stdout + result.stderr
    report = json.loads(report_path.read_text(encoding="utf-8"))
    # What the driver reads on stdout is what the report holds.
    assert json.loads(result.stdout) == report
    return result.returncode, report


def _problems(report: dict) -> str:
    return " | ".join(report["problems"])


# ---------------------------------------------------------------------------
# The positive case, and the one it becomes when a bound goes missing
# ---------------------------------------------------------------------------
def test_a_complete_collector_output_passes(tmp_path) -> None:
    sut = _capsule(tmp_path / "analysis" / "collector")
    code, report = _check(tmp_path / "analysis" / "collector", sut)
    assert report["problems"] == []
    assert code == 0
    assert report["resource_validation"] == "run"
    assert report["deployed_sha256"] == SHA
    assert report["window"] == [WINDOW_START, WINDOW_END]
    assert report["samples"] == len(SAMPLE_SECONDS)
    assert report["distinct_instants"] == len(SAMPLE_SECONDS)
    assert report["distinct_instants_in_window"] == len(SAMPLE_SECONDS)
    assert report["closing_counters"] == CLEAN_COUNTERS
    assert report["rows_per_service"] == {
        name: len(SAMPLE_SECONDS) for name in SERVICES
    }
    assert report["unexpected_names"] == []
    # What the start record asked of the collector is recorded and read
    # against the closing record (2026-09-20).
    assert report["declared_expected_services"] == ",".join(SERVICES)
    assert report["declared_interval_s"] == 1.0
    assert report["declared_duration_s"] == 45.0
    assert report["window_seconds"] == 45
    assert report["rounds_the_declared_interval_implies"] == 46
    assert report["closing_record_reconciliation"] == "run"
    # A clean output has nothing to observe either.
    assert report["observations"] == []


def test_a_missing_closing_record_fails_and_says_the_validation_did_not_run(
    tmp_path,
) -> None:
    """The exact path F3 names: everything else is in order.

    The start hash is the wanted one, the inventory reports no missing
    service, the lifecycle companion is there and every expected service has
    rows -- only the closing summary never arrived. That used to pass with the
    resource validation quietly skipped.
    """
    directory = tmp_path / "analysis" / "collector"
    sut = _capsule(directory, records=["start", "inventory"])
    code, report = _check(directory, sut)
    assert code == 1
    assert report["stop_line"] is None
    assert "no 'stop:' line in the diagnostics" in _problems(report)
    assert report["resource_validation"].startswith("not run")
    assert "the resource validation did NOT run" in _problems(report)
    assert "UNCHECKED" in _problems(report)
    # The reconciliation could not be made either, and says so rather than
    # leaving its figures null beside nothing (2026-09-20).
    assert report["closing_record_reconciliation"].startswith("not run")
    assert "the closing record was NOT reconciled with the CSV" in _problems(report)
    # Nothing else was wrong with this output.
    assert report["deployed_sha256"] == SHA
    assert "has no rows" not in _problems(report)
    assert "inventory reports missing services" not in _problems(report)


# ---------------------------------------------------------------------------
# Missing, malformed, duplicated and reversed bounds
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    "records, expected",
    [
        # Absent.
        (["inventory", "stop"], "no 'start:' line"),
        (["start", "stop"], "no 'inventory:' line"),
        (["start", "inventory"], "no 'stop:' line"),
        ([], "no diagnostics companion"),
        # Duplicated: two collectors appended to the same files.
        (["start", "start", "inventory", "stop"], "2 'start:' lines"),
        (["start", "inventory", "inventory", "stop"], "2 'inventory:' lines"),
        (["start", "inventory", "stop", "stop"], "2 'stop:' lines"),
        # Malformed: no usable timestamp, no sample count, no missing= field.
        (
            ["start", "inventory", "stop: samples=44 utc_gap_seconds=0"],
            "no strictly valid leading UTC timestamp",
        ),
        (
            ["2026-09-32T10:00:00Z start: collector_sha256=" + SHA,
             "inventory", "stop"],
            "no strictly valid leading UTC timestamp",
        ),
        (
            ["start", "inventory", f"{WINDOW_END} stop: samples=unknown "
             "utc_gap_seconds=0 withheld_samples=3"],
            "no integer samples= count",
        ),
        (
            ["start", f"{WINDOW_END} inventory: observed=a expected=a unnamed_ids=0",
             "stop"],
            "has no 'missing=' field",
        ),
        (
            [f"{WINDOW_START} start: collector_sha256=not-a-hash", "inventory",
             "stop"],
            "no usable collector_sha256",
        ),
        # Reversed: in line order, and in time.
        (["stop", "start", "inventory"], "records are out of order"),
        (["start", "stop", "inventory"], "records are out of order"),
        (
            ["start", "inventory",
             f"{WINDOW_START} stop: samples=44 utc_gap_seconds=0"],
            "is not earlier than its stop",
        ),
    ],
)
def test_unusable_bounds_fail_and_stop_the_resource_validation(
    tmp_path, records: list[str], expected: str
) -> None:
    directory = tmp_path / "analysis" / "collector"
    sut = _capsule(directory, records=records)
    code, report = _check(directory, sut)
    assert code == 1
    assert expected in _problems(report), _problems(report)
    assert report["resource_validation"].startswith("not run"), _problems(report)
    assert "UNCHECKED" in _problems(report)


# ---------------------------------------------------------------------------
# A closing record that cannot account for the samples it took (2026-09-20)
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("counter", COUNTERS)
def test_a_counter_the_collector_could_not_read_makes_the_record_unusable(
    tmp_path, counter: str
) -> None:
    """A figure the collector could not compute is written as 'unknown' -- its
    closing awk cannot read the state file at all -- and the record is then as
    unreadable as one without a 'samples=' count, so the resource validation
    must not run on its window."""
    directory = tmp_path / "analysis" / "collector"
    sut = _capsule(directory, records=["start", "inventory", _stop(**{counter: "unknown"})])
    code, report = _check(directory, sut)
    assert code == 1
    assert f"the collector's 'stop:' line carries {counter}=unknown" in _problems(report)
    assert "its closing record cannot be read" in _problems(report)
    assert report["closing_counters"][counter] == "unknown"
    assert report["resource_validation"].startswith("not run")
    assert "UNCHECKED" in _problems(report)


@pytest.mark.parametrize("counter", COUNTERS)
def test_a_counter_the_closing_record_never_states_is_a_problem(
    tmp_path, counter: str
) -> None:
    """The deployed collector is the clean clone's (the start hash is checked
    here), so its closing summary carries all of these counters: a record
    without one has been truncated or edited."""
    directory = tmp_path / "analysis" / "collector"
    sut = _capsule(directory, records=["start", "inventory", _stop(drop=counter)])
    code, report = _check(directory, sut)
    assert code == 1
    assert f"the collector's 'stop:' line has no '{counter}=' field" in _problems(report)
    assert report["closing_counters"][counter] is None
    assert report["resource_validation"].startswith("not run")


@pytest.mark.parametrize(
    "fields, expected",
    [
        ({"withheld_runs_unmeasured": 2},
         "the collector reports withheld_runs_unmeasured=2: 2 run(s) of "
         "withheld samples whose elapsed time could not be measured"),
        ({"withheld_open_at_stop": 1},
         "the collector reports withheld_open_at_stop=1: 1 withheld sample(s) "
         "of a run still open when the collector stopped"),
    ],
)
def test_elapsed_time_in_neither_count_is_a_problem_of_its_own(
    tmp_path, fields: dict, expected: str
) -> None:
    """The two counters that really are unaccounted evidence: samples whose
    elapsed time no accepted sample has measured. The record is still
    readable, so the resource validation runs and is added to it."""
    directory = tmp_path / "analysis" / "collector"
    sut = _capsule(directory, records=["start", "inventory", _stop(**fields)])
    code, report = _check(directory, sut)
    assert code == 1
    assert expected in _problems(report), _problems(report)
    assert "accounted for nowhere" in _problems(report)
    assert report["resource_validation"] == "run"


def test_a_forward_clock_step_does_not_invalidate_a_run(tmp_path) -> None:
    """P1 of the review of 2026-09-20: utc_gap_seconds is not lost evidence.

    collect-resources.sh:117-120 says in the collector's own words that a wall
    clock stepped FORWARD adds to this count 'although no time passed
    unsampled'. The CSV here is the clean one with a single second missing:
    every spacing is at most 2 s, far inside the protocol's MAX_SAMPLE_GAP_S,
    and validate_resources_csv -- the authority on the spacing -- passes it.
    The count is recorded in the report, in the collector's words, and the run
    stands.
    """
    directory = tmp_path / "analysis" / "collector"
    stepped = [second for second in SAMPLE_SECONDS if second != 20]
    sut = _capsule(
        directory,
        records=["start", "inventory",
                 _stop(samples=len(stepped) + 1, utc_gap_seconds=1)],
        csv_text=_csv_rows(seconds=stepped),
    )
    code, report = _check(directory, sut)
    assert report["problems"] == []
    assert code == 0
    assert report["closing_counters"]["utc_gap_seconds"] == "1"
    assert report["resource_validation"] == "run"
    observed = " | ".join(report["observations"])
    assert "the collector reports utc_gap_seconds=1" in observed
    assert "although no time passed unsampled" in observed
    assert "validate_resources_csv against the protocol's MAX_SAMPLE_GAP_S" in observed


def test_withheld_samples_alone_do_not_invalidate_a_run(tmp_path) -> None:
    """The pacing artefact the collector is designed to absorb.

    47 rounds less the 3 withheld are the 44 accounted rounds, whose 44
    instants the CSV carries; what they cost is stated (withheld_elapsed_s)
    and is in both counts, so nothing is unaccounted for.
    """
    directory = tmp_path / "analysis" / "collector"
    sut = _capsule(
        directory,
        records=["start", "inventory",
                 _stop(samples=47, withheld_samples=3, withheld_elapsed_s="2.00")],
    )
    code, report = _check(directory, sut)
    assert report["problems"] == []
    assert code == 0
    assert report["closing_counters"]["withheld_samples"] == "3"
    assert report["closing_counters"]["withheld_elapsed_s"] == "2.00"
    observed = " | ".join(report["observations"])
    assert "the collector reports withheld_samples=3 (2.00 s of elapsed time)" in observed


def test_elapsed_time_without_a_withheld_count_is_a_contradiction(tmp_path) -> None:
    """The fabricated zero (2026-09-20): collect-resources.sh's closing awk
    falls back to 0 for the withheld count when it cannot read its state file,
    while the elapsed figure it kept is not zero. The count is then no
    evidence that nothing was withheld, and the record contradicts itself."""
    directory = tmp_path / "analysis" / "collector"
    sut = _capsule(
        directory,
        records=["start", "inventory",
                 _stop(withheld_samples=0, withheld_elapsed_s="12.50")],
    )
    code, report = _check(directory, sut)
    assert code == 1
    assert (
        "the collector reports withheld_elapsed_s=12.50 while withheld_samples=0"
    ) in _problems(report)
    assert "contradicts itself" in _problems(report)
    assert report["closing_counters"]["withheld_elapsed_s"] == "12.50"


def test_more_rounds_withheld_than_taken_cannot_be_read(tmp_path) -> None:
    """P3 of the review of 2026-09-20: a withheld sample IS a completed round.

    ``samples=`` counts every round the loop completed, withheld ones
    included (``collect-resources.sh:1287``), so ``withheld_samples <=
    samples`` holds of every record that can be read at all; the two counters
    come from different places (the shell loop and the closing awk's state
    line). A record that breaks it is refused, and the reconciliation is
    reported as NOT run rather than switched off in silence -- until today the
    negative difference quietly disabled the two rules that rest on it.
    """
    directory = tmp_path / "analysis" / "collector"
    sut = _capsule(
        directory,
        records=["start", "inventory",
                 _stop(samples=46, withheld_samples=50,
                       withheld_elapsed_s="40.00")],
    )
    code, report = _check(directory, sut)
    assert code == 1
    assert (
        "the closing record states withheld_samples=50 against samples=46: "
        "more rounds withheld than taken, so the record cannot be read"
    ) in _problems(report), _problems(report)
    assert report["closing_record_reconciliation"].startswith("not run"), report
    assert "the closing record was NOT reconciled with the CSV" in _problems(report)


def test_rounds_that_wrote_no_row_are_recorded_not_judged(tmp_path) -> None:
    """P1 of the review of 2026-09-20: the reconciliation must not invent a
    threshold of its own.

    45 rounds, none of them withheld, and 40 instants in the window: four
    rounds beyond the priming one wrote no row at all
    (``collect-resources.sh:1100``, ``:1274``, ``:684``, ``:711``: a round
    whose inputs could not be read is counted and writes nothing). What that
    costs the evidence is spacing and coverage, and the authority on both is
    validate_resources_csv, on the real instants -- which passes this CSV
    (the four seconds are dropped one at a time, so no gap reaches
    MAX_SAMPLE_GAP_S). So the shortfall is recorded, and a run whose CPU/RAM
    evidence the protocol accepts is not refused here.

    The rounds themselves are a record the collector could have written: 45
    stamped rounds fit in its own 45 s window, which is what the rule above
    them is about (2026-09-20). With the 60 rounds this case carried until
    today the capsule was itself impossible, so it could not tell the two
    rules apart.
    """
    directory = tmp_path / "analysis" / "collector"
    kept = [second for second in SAMPLE_SECONDS if second % 10]
    sut = _capsule(
        directory,
        records=["start", "inventory", _stop(samples=45)],
        csv_text=_csv_rows(seconds=kept),
    )
    code, report = _check(directory, sut)
    assert report["problems"] == []
    assert code == 0
    assert report["distinct_instants_in_window"] == 40
    assert report["closing_record_reconciliation"] == "run"
    observed = " | ".join(report["observations"])
    assert (
        "the closing record accounts for samples=45 less withheld_samples=0 = 45 "
        "stamped sampling round(s), and the CSV carries 40 distinct instant(s) "
        "inside the collector's window "
        f"{WINDOW_START}..{WINDOW_END}: 4 round(s)"
    ) in observed, observed
    assert "wrote no row at all" in observed
    # Everything the rule is not about still passed.
    assert report["resource_validation"] == "run"
    assert "validate_resources_csv: " not in _problems(report)


def test_one_lost_round_does_not_refuse_a_real_capsule(tmp_path) -> None:
    """The boundary the two real capsules of 2026-09-19 sit on.

    Each closed with exactly one round more than the instants of its CSV, so a
    reconciliation that tolerates the priming round and nothing else refuses
    the very next run that loses one round anywhere in 720 -- one failed
    ``docker stats`` poll -- although every spacing is 2 s and the coverage
    99.9 %. Here: the nominal geometry with one round lost.
    """
    directory = tmp_path / "analysis" / "collector"
    capsule = dict(REAL_CAPSULES["nominal-r01"])
    stamps = _timeline(capsule["start"], capsule["instants"] + 1)[1:]
    del stamps[300]  # the round whose poll returned nothing
    rows = ["ts_utc,container,cpu_pct,mem_bytes,mem_pct,host"]
    for stamp in stamps:
        for name in SERVICES:
            rows.append(f"{stamp},{name},10.0,1048576,1.0,{NODE}")
    sut = _capsule(
        directory,
        records=[
            f"{capsule['start']} start: collector_sha256={SHA} host={NODE} "
            "source=auto interval=1s duration=840s pacing: p; timestamps: t; "
            f"expected services: {','.join(SERVICES)}",
            f"{capsule['stop']} inventory: observed={','.join(SERVICES)} "
            f"expected={','.join(SERVICES)} missing=none unnamed_ids=0",
            f"{capsule['stop']} stop: samples={capsule['samples']} "
            "utc_gap_seconds=1 withheld_samples=0 withheld_elapsed_s=0.00 "
            "withheld_runs_unmeasured=0 withheld_open_at_stop=0 "
            "calibrations=1 pacing=wall-clock",
        ],
        csv_text="\n".join(rows) + "\n",
    )
    code, report = _check(directory, sut)
    assert report["problems"] == []
    assert code == 0
    assert report["distinct_instants_in_window"] == capsule["instants"] - 1
    assert report["resource_validation"] == "run"
    assert "wrote no row at all" in " | ".join(report["observations"])


def test_withheld_samples_never_invalidate_a_run(tmp_path) -> None:
    """P1 of the review of 2026-09-20: withheld rounds must not invalidate a
    run through the rounds the window implies either.

    A withheld sample IS a completed sampling round that stamps no second
    (``collect-resources.sh:422-427``) and ``samples=`` counts it (``:1287``),
    so the count legitimately exceeds what the stamped window allows by
    exactly the withheld count. This is the capsule of
    ``test_withheld_samples_alone_do_not_invalidate_a_run`` with eight
    withheld samples instead of three: 52 rounds less the 8 withheld are the
    44 accounted rounds whose instants the CSV carries.
    """
    directory = tmp_path / "analysis" / "collector"
    sut = _capsule(
        directory,
        records=["start", "inventory",
                 _stop(samples=52, withheld_samples=8, withheld_elapsed_s="6.00")],
    )
    code, report = _check(directory, sut)
    assert report["problems"] == []
    assert code == 0
    observed = " | ".join(report["observations"])
    assert (
        "the closing record states samples=52, more rounds than its own 45 s "
        "window at the interval=1s the 'start:' line declares allows (46)"
    ) in observed, observed
    assert "a sampling round that stamped no second" in observed


@pytest.mark.parametrize(
    "samples, withheld, elapsed",
    [
        # No round withheld: the raw count and the accounted one are equal.
        (20, 0, "0.00"),
        # The case the bound of 2026-09-20 let through until today: 46 rounds
        # less the 3 withheld are 43 stamped ones, and the CSV carries 44
        # instants -- one instant more than any round of this run can have
        # stamped, since a withheld round stamps none at all.
        (46, 3, "2.00"),
    ],
)
def test_more_instants_than_sampling_rounds_is_a_problem(
    tmp_path, samples: int, withheld: int, elapsed: str
) -> None:
    """Rows that cannot exist: a round stamps at most one instant and a
    withheld round stamps none, so a CSV with more distinct instants inside
    the window than the rounds the closing record ACCOUNTS FOR holds instants
    of another collector's run (concatenated or edited evidence)."""
    directory = tmp_path / "analysis" / "collector"
    sut = _capsule(
        directory,
        records=[
            "start",
            "inventory",
            _stop(
                samples=samples,
                withheld_samples=withheld,
                withheld_elapsed_s=elapsed,
            ),
        ],
    )
    code, report = _check(directory, sut)
    assert code == 1
    assert (
        "the CSV carries 44 distinct instant(s) inside the collector's window "
        f"{WINDOW_START}..{WINDOW_END}, more than the samples={samples} less "
        f"withheld_samples={withheld} = {samples - withheld} sampling round(s) "
        "its closing record accounts for: a round stamps at most one instant "
        "and a withheld round stamps none at all, so the CSV holds instants "
        "the collector did not stamp"
    ) in _problems(report), _problems(report)


def test_a_csv_with_no_instant_in_the_window_is_a_problem(tmp_path) -> None:
    """The other contradiction inside one record: 44 stamped rounds and not
    one instant of the CSV inside the collector's own window."""
    directory = tmp_path / "analysis" / "collector"
    sut = _capsule(
        directory,
        csv_text=_csv_rows(seconds=SAMPLE_SECONDS).replace("T10:00:", "T11:00:"),
    )
    code, report = _check(directory, sut)
    assert code == 1
    assert (
        "the closing record accounts for samples=44 less withheld_samples=0 = 44 "
        "stamped sampling round(s), and the CSV carries no instant at all inside "
        f"the collector's window {WINDOW_START}..{WINDOW_END}"
    ) in _problems(report), _problems(report)


def test_the_instants_are_counted_with_the_ingests_own_parser(tmp_path) -> None:
    """P3 of the review of 2026-09-20: one parser for the CSV's cells.

    ``parse_csv_timestamp`` -- what validate_resources_csv and the whole
    ingest read ``ts_utc`` with -- accepts an explicit ``+00:00`` offset as
    well as the collector's trailing ``Z``. A capsule the protocol passes must
    not be refused here over the spelling: with a strict parser of this
    script's own, every instant fell outside the window and the capsule was
    refused for carrying none.
    """
    directory = tmp_path / "analysis" / "collector"
    sut = _capsule(directory, csv_text=_csv_rows(zone="+00:00"))
    code, report = _check(directory, sut)
    assert report["problems"] == []
    assert code == 0
    assert report["distinct_instants_in_window"] == len(SAMPLE_SECONDS)
    assert report["resource_validation"] == "run"


def test_the_priming_round_writes_no_row_and_is_allowed_for(tmp_path) -> None:
    """The shape of a real run: the collector's first round only primes each
    container's CPU delta, so a clean output carries one instant fewer than the
    rounds it accounts for (nominal-r01 of 2026-09-19 closed with samples=721
    and carries 720 instants)."""
    directory = tmp_path / "analysis" / "collector"
    sut = _capsule(directory, records=["start", "inventory", _stop(samples=45)])
    code, report = _check(directory, sut)
    assert report["problems"] == []
    assert code == 0
    assert report["samples"] == 45
    assert report["distinct_instants_in_window"] == 44


# ---------------------------------------------------------------------------
# The two real capsules of 2026-09-19 (their figures, not their paths)
# ---------------------------------------------------------------------------
#: What the collector really wrote on this machine, copied from the two
#: capsules the campaign already holds: the 45 s preflight
#: (resources-preflight-20260919T193753Z.csv) and the 120+600 s nominal run
#: (raw/nominal-r01). Each closed with one round more than the instants its
#: CSV carries, because the first round only primes the CPU deltas. A rule
#: that refuses either of these refuses the evidence the thesis rests on.
REAL_CAPSULES = {
    "preflight-45s": {
        "start": "2026-09-19T19:37:55Z",
        "stop": "2026-09-19T19:38:40Z",
        "interval": "1s",
        "duration": "45s",
        "samples": 46,
        "instants": 45,
    },
    "nominal-r01": {
        "start": "2026-09-19T20:00:45Z",
        "stop": "2026-09-19T20:12:47Z",
        "interval": "1s",
        # The collector is given more than the run needs; the stop hook's
        # SIGTERM ends it after the measured window (722 s of the 840 s).
        "duration": "840s",
        "samples": 721,
        "instants": 720,
    },
}


def _timeline(first: str, count: int) -> list[str]:
    """``count`` whole-second UTC stamps, one per second, from ``first``."""
    begin = datetime.strptime(first, "%Y-%m-%dT%H:%M:%SZ")
    return [
        (begin + timedelta(seconds=offset)).strftime("%Y-%m-%dT%H:%M:%SZ")
        for offset in range(count)
    ]


def _capsule_like(directory: Path, capsule: dict) -> Path:
    """One collector output with the figures of a real capsule.

    The instants begin one second after the start record, as the collector's
    do: its first round only primes the CPU deltas and writes no row.
    """
    stamps = _timeline(capsule["start"], capsule["instants"] + 1)[1:]
    rows = ["ts_utc,container,cpu_pct,mem_bytes,mem_pct,host"]
    for stamp in stamps:
        for name in SERVICES:
            rows.append(f"{stamp},{name},10.0,1048576,1.0,{NODE}")
    records = [
        f"{capsule['start']} start: collector_sha256={SHA} host={NODE} source=auto "
        f"interval={capsule['interval']} duration={capsule['duration']} pacing: "
        "wall-clock seconds; timestamps: awk systime(); expected services: "
        f"{','.join(SERVICES)}",
        f"{capsule['stop']} inventory: observed={','.join(SERVICES)} "
        f"expected={','.join(SERVICES)} missing=none unnamed_ids=0",
        f"{capsule['stop']} stop: samples={capsule['samples']} utc_gap_seconds=0 "
        "withheld_samples=0 withheld_elapsed_s=0.00 withheld_runs_unmeasured=0 "
        "withheld_open_at_stop=0 calibrations=1 pacing=wall-clock",
    ]
    return _capsule(directory, records=records, csv_text="\n".join(rows) + "\n")


@pytest.mark.parametrize("name", sorted(REAL_CAPSULES))
def test_a_real_capsule_of_2026_09_19_passes(tmp_path, name: str) -> None:
    """The regression that binds the rule to the evidence: neither the 45 s
    preflight nor the 120+600 s nominal run may be refused, and the closing
    record of each reconciles with its CSV through the priming round."""
    capsule = REAL_CAPSULES[name]
    directory = tmp_path / "analysis" / "collector"
    sut = _capsule_like(directory, capsule)
    code, report = _check(directory, sut)
    assert report["problems"] == []
    assert code == 0
    assert report["resource_validation"] == "run"
    assert report["samples"] == capsule["samples"]
    assert report["distinct_instants_in_window"] == capsule["instants"]
    assert report["samples"] - report["distinct_instants_in_window"] == 1
    # The half that seals the measured runs reads the same capsule the same
    # way, down to the words: nominal-r01 went through THAT one.
    harness = run_mod.inspect_collector_outputs(
        directory / f"resources-{RUN}.csv", list(SERVICES)
    )
    assert harness["problems"] == []
    assert harness["stop_counters"] == report["closing_counters"]
    assert harness["samples"] == report["samples"]
    assert harness["distinct_instants_in_window"] == (
        report["distinct_instants_in_window"]
    )
    assert harness["observations"] == report["observations"]


def test_the_nominal_capsule_records_the_duration_it_never_reached(
    tmp_path,
) -> None:
    """nominal-r01 declared duration=840s and closed a 722 s window, because
    the stop hook ends the collector after the measured run. That is recorded
    in the report and is NOT a problem; what the collection must satisfy is
    judged on the real instants.

    The reason given says what is true of THIS half as well (P3 of the review
    of 2026-09-20): here the window handed to validate_resources_csv is the
    collector's own, so a collection that ended early is validated against
    itself and the figure below is the only trace of it.
    """
    directory = tmp_path / "analysis" / "collector"
    sut = _capsule_like(directory, REAL_CAPSULES["nominal-r01"])
    code, report = _check(directory, sut)
    assert code == 0
    assert report["window_seconds"] == 722
    assert report["declared_duration_s"] == 840.0
    assert report["rounds_the_declared_interval_implies"] == 723
    assert report["declared_duration_shortfall_s"] == 118.0
    observed = " | ".join(report["observations"])
    assert (
        "the collector's window is 722 s, 118 s shorter than the duration=840s"
    ) in observed, observed
    assert (
        "the coverage is judged by validate_resources_csv over the window it "
        "is given, which in the preflight check is the collector's own"
    ) in observed, observed


def test_a_collection_that_ended_early_reports_how_early(tmp_path) -> None:
    """P3 of the review of 2026-09-20: on this side the collector's own window
    is the only window there is, so a collection that stopped at 31 s of the
    45 s it was asked for reconciles with itself at full coverage and clears
    MIN_DISTINCT_SAMPLE_INSTANTS by one instant.

    Nothing in the fetched output says whether the collector was ended early
    on purpose (the stop hook's SIGTERM does exactly that after a timed run,
    which is why this cannot be a verdict here), so the shortfall is reported
    as a number, in seconds, for the driver that knows what it asked for.
    """
    directory = tmp_path / "analysis" / "collector"
    early = range(1, 32)
    stop_at = "2026-09-07T10:00:31Z"
    sut = _capsule(
        directory,
        records=[
            "start",
            f"{stop_at} inventory: observed={','.join(SERVICES)} "
            f"expected={','.join(SERVICES)} missing=none unnamed_ids=0",
            f"{stop_at} stop: samples={len(early) + 1} utc_gap_seconds=0 "
            "withheld_samples=0 withheld_elapsed_s=0.00 "
            "withheld_runs_unmeasured=0 withheld_open_at_stop=0 "
            "calibrations=1 pacing=wall-clock",
        ],
        csv_text=_csv_rows(seconds=early),
    )
    code, report = _check(directory, sut)
    assert code == 0
    assert report["window_seconds"] == 31
    assert report["declared_duration_shortfall_s"] == 14.0
    assert report["resource_validation"] == "run"
    assert (
        "the collector's window is 31 s, 14 s shorter than the duration=45s"
    ) in " | ".join(report["observations"])


# ---------------------------------------------------------------------------
# The start record against the closing record (2026-09-20)
# ---------------------------------------------------------------------------
def test_a_rate_below_the_declared_interval_is_recorded_not_judged(
    tmp_path,
) -> None:
    """One instant every 5 s where 1 s was declared: 121 rounds where the
    interval implies about 601. Every spacing is still 5 s, which is what
    MAX_SAMPLE_GAP_S allows, so validate_resources_csv -- the authority --
    passes the CSV and the figure is recorded, not turned into a verdict of
    this check's own."""
    directory = tmp_path / "analysis" / "collector"
    start, stop = "2026-09-19T19:00:00Z", "2026-09-19T19:10:00Z"
    stamps = [s for i, s in enumerate(_timeline(start, 601)) if i % 5 == 0]
    rows = ["ts_utc,container,cpu_pct,mem_bytes,mem_pct,host"]
    for stamp in stamps:
        for name in SERVICES:
            rows.append(f"{stamp},{name},10.0,1048576,1.0,{NODE}")
    sut = _capsule(
        directory,
        records=[
            f"{start} start: collector_sha256={SHA} host={NODE} source=auto "
            f"interval=1s duration=600s pacing: p; timestamps: t; expected "
            f"services: {','.join(SERVICES)}",
            f"{stop} inventory: observed={','.join(SERVICES)} "
            f"expected={','.join(SERVICES)} missing=none unnamed_ids=0",
            f"{stop} stop: samples=121 utc_gap_seconds=480 withheld_samples=0 "
            "withheld_elapsed_s=0.00 withheld_runs_unmeasured=0 "
            "withheld_open_at_stop=0 calibrations=1 pacing=wall-clock",
        ],
        csv_text="\n".join(rows) + "\n",
    )
    code, report = _check(directory, sut)
    assert report["problems"] == []
    assert code == 0
    assert report["resource_validation"] == "run"
    assert report["rounds_the_declared_interval_implies"] == 601
    observed = " | ".join(report["observations"])
    assert "the collector took 121 sampling round(s)" in observed
    assert "it did not reach its declared rate" in observed
    assert "the collector reports utc_gap_seconds=480" in observed


def test_more_rounds_than_the_stamped_window_can_hold_is_a_problem(
    tmp_path,
) -> None:
    """A closing record that cannot be true (P2 of the review of 2026-09-20).

    600 rounds, none of them withheld, inside a stamped window of 45 s. An
    accepted round stamps a second strictly after the last stamped one
    (``collect-resources.sh:422-427`` withholds every other sample and writes
    no rows for it), so at most 46 rounds can have been stamped in a 45 s
    window, and the closing record counts every round it withheld: with
    ``withheld_samples=0`` there is no mechanism left by which 600 rounds can
    have been taken there. The record is refused, rather than left to certify
    its own completeness through its other figures.

    The interval-based figure beside it stays the observation it is: it is
    the DECLARED interval that 600 rounds contradict, and a collector may
    legitimately pace otherwise.
    """
    directory = tmp_path / "analysis" / "collector"
    sut = _capsule(directory, records=["start", "inventory", _stop(samples=600)])
    code, report = _check(directory, sut)
    assert code == 1
    assert (
        "the closing record states samples=600 less withheld_samples=0 = 600 "
        f"stamped sampling round(s) inside its own 45 s window {WINDOW_START}.."
        f"{WINDOW_END}: an accepted round stamps a second strictly after the "
        "last one, so at most 46 of them can have been stamped there (one "
        "more for the closing record's own stamp), and the record cannot be "
        "true"
    ) in _problems(report), _problems(report)
    assert (
        "the closing record states samples=600, more rounds than its own 45 s "
        "window at the interval=1s the 'start:' line declares allows (46)"
    ) in " | ".join(report["observations"]), report["observations"]


def test_a_collector_pacing_faster_than_it_declared_is_not_refused(
    tmp_path,
) -> None:
    """The bound is the stamped SECONDS, not the declared interval.

    A collector given ``interval=5s`` that really samples every second closes
    121 rounds over its own 120 s window: far more than the 25 rounds the
    declared interval implies, and exactly the shape the rule above must not
    punish. Every second of the window is stamped, the CSV passes
    validate_resources_csv, and only the interval figure is observed.
    """
    directory = tmp_path / "analysis" / "collector"
    start, stop = "2026-09-19T09:00:00Z", "2026-09-19T09:02:00Z"
    rows = ["ts_utc,container,cpu_pct,mem_bytes,mem_pct,host"]
    for stamp in _timeline(start, 121)[1:]:
        for name in SERVICES:
            rows.append(f"{stamp},{name},10.0,1048576,1.0,{NODE}")
    sut = _capsule(
        directory,
        records=[
            f"{start} start: collector_sha256={SHA} host={NODE} source=auto "
            "interval=5s duration=120s pacing: p; timestamps: t; expected "
            f"services: {','.join(SERVICES)}",
            f"{stop} inventory: observed={','.join(SERVICES)} "
            f"expected={','.join(SERVICES)} missing=none unnamed_ids=0",
            f"{stop} stop: samples=121 utc_gap_seconds=0 withheld_samples=0 "
            "withheld_elapsed_s=0.00 withheld_runs_unmeasured=0 "
            "withheld_open_at_stop=0 calibrations=1 pacing=wall-clock",
        ],
        csv_text="\n".join(rows) + "\n",
    )
    code, report = _check(directory, sut)
    assert report["problems"] == []
    assert code == 0
    assert report["window_seconds"] == 120
    assert report["distinct_instants_in_window"] == 120
    assert report["rounds_the_declared_interval_implies"] == 25
    assert report["resource_validation"] == "run"


def test_an_inventory_judged_against_no_expected_set_is_a_problem(
    tmp_path,
) -> None:
    """A collector started without --expect-services writes 'none declared'
    and then 'missing=none': it was asked about nothing, so its inventory
    proves nothing about the services this check was given."""
    directory = tmp_path / "analysis" / "collector"
    sut = _capsule(
        directory,
        records=[
            f"{WINDOW_START} start: collector_sha256={SHA} host={NODE} "
            "source=cgroup interval=1s duration=45s pacing: wall-clock; "
            "timestamps: date; expected services: none declared",
            f"{WINDOW_END} inventory: observed={','.join(SERVICES)} "
            "expected=none-declared missing=none unnamed_ids=0",
            RECORDS["stop"],
        ],
    )
    code, report = _check(directory, sut)
    assert code == 1
    assert report["declared_expected_services"] == "none declared"
    assert (
        "the collector's 'start:' line declares expected services 'none declared'"
    ) in _problems(report)
    assert "judged against another set" in _problems(report)


def test_a_collector_given_another_expected_set_is_a_problem(tmp_path) -> None:
    directory = tmp_path / "analysis" / "collector"
    sut = _capsule(
        directory,
        records=[
            f"{WINDOW_START} start: collector_sha256={SHA} host={NODE} "
            "source=cgroup interval=1s duration=45s pacing: wall-clock; "
            f"timestamps: date; expected services: {SERVICES[0]}",
            RECORDS["inventory"],
            RECORDS["stop"],
        ],
    )
    code, report = _check(directory, sut)
    assert code == 1
    assert (
        f"the collector's 'start:' line declares expected services '{SERVICES[0]}'"
    ) in _problems(report)


# ---------------------------------------------------------------------------
# The preflight half and the harness half apply ONE rule
# ---------------------------------------------------------------------------
def _about_the_closing_record(entries: list[str]) -> set[str]:
    """The entries that judge the closing record, whichever half wrote them."""
    return {
        entry
        for entry in entries
        if "'stop:' line" in entry
        or entry.startswith("the collector reports")
        or entry.startswith("the closing record")
        or "distinct instant(s)" in entry
        or "sampling round(s)" in entry
        or "shorter than the duration=" in entry
        or "the measured window is reversed or empty" in entry
        or "records are out of order" in entry
    }


#: A CSV whose rows carry no ``ts_utc`` column at all: its rows cannot be
#: placed in the collector's window, so neither half may reconcile anything.
NO_TIMESTAMP_CSV = "container,cpu_pct,mem_bytes,mem_pct,host\n" + "".join(
    f"{name},10.0,1048576,1.0,{NODE}\n" for name in SERVICES
)


@pytest.mark.parametrize(
    "stop, csv_text",
    [
        # Clean, then each shape the rule has to decide on: a figure the
        # collector could not compute, one it never stated, elapsed time in
        # neither count, the contradiction, a forward clock step, withheld
        # samples, rounds that wrote no row, and instants no round stamped.
        (_stop(), None),
        (_stop(utc_gap_seconds="unknown"), None),
        (_stop(drop="withheld_samples"), None),
        (_stop(withheld_runs_unmeasured=2, withheld_open_at_stop=1), None),
        (_stop(withheld_elapsed_s="12.50"), None),
        (_stop(samples=45, utc_gap_seconds=1), _csv_rows(seconds=range(1, 44))),
        (_stop(samples=47, withheld_samples=3, withheld_elapsed_s="2.00"), None),
        (_stop(samples=60), None),
        (_stop(samples=20), None),
        # A closing record the collector did not stamp: neither half may read
        # it as a bound, and neither may reconcile silently (2026-09-20).
        (_stop()[len(WINDOW_END) + 1:], None),
        # A window whose stop is not after its start -- a wall clock stepped
        # back between the two records -- reversed and empty: neither half may
        # read a record against it, and neither may seal a length from it
        # (2026-09-20).
        (f"{WINDOW_START} " + _stop()[len(WINDOW_END) + 1:], None),
        ("2026-09-07T09:59:35Z " + _stop()[len(WINDOW_END) + 1:], None),
        # A CSV the reconciliation cannot use, and one whose ts_utc carries an
        # explicit UTC offset instead of the collector's trailing Z: the
        # instants must be counted by the same parser on both sides.
        (_stop(), NO_TIMESTAMP_CSV),
        (_stop(), _csv_rows(zone="+00:00")),
    ],
)
def test_both_halves_report_the_same_closing_record(
    tmp_path, stop: str, csv_text
) -> None:
    """The same capsule through the preflight check and through the harness's
    ``inspect_collector_outputs``: what each says about the closing record --
    its problems AND what it records without judging -- must be the same set,
    or a run could be refused by one half and sealed by the other."""
    directory = tmp_path / "analysis" / "collector"
    sut = _capsule(
        directory, records=["start", "inventory", stop], csv_text=csv_text
    )
    _code, report = _check(directory, sut)
    harness = run_mod.inspect_collector_outputs(
        directory / f"resources-{RUN}.csv", list(SERVICES)
    )
    assert _about_the_closing_record(harness["problems"]) == (
        _about_the_closing_record(report["problems"])
    )
    assert _about_the_closing_record(harness["observations"]) == (
        _about_the_closing_record(report["observations"])
    )
    assert harness["samples"] == report["samples"]
    assert harness["distinct_instants_in_window"] == (
        report["distinct_instants_in_window"]
    )
    assert harness["closing_record_reconciliation"] == (
        report["closing_record_reconciliation"]
    )
    assert harness["stop_counters"] == report["closing_counters"]


@pytest.mark.parametrize(
    "order", sorted(itertools.permutations(("start", "inventory", "stop")))
)
def test_both_halves_read_the_records_in_the_same_order(
    tmp_path, order: tuple[str, ...]
) -> None:
    """The three records, each stamped in the collector's own order, in every
    file order they can be written in.

    ``collect-resources.sh`` writes the start before the loop, the inventory
    when the stop hook's SIGTERM ends it and the closing record last, so any
    other order is concatenated or edited evidence. Until 2026-09-20 the two
    halves held two UNEQUAL copies of that rule -- this one compared the whole
    chain, the harness only asked whether the closing record came before the
    other two -- and a diagnostics holding ``inventory -> start -> stop`` was
    refused here and sealed ``valid`` by the half that seals the nominal and
    slice runs.
    """
    directory = tmp_path / "analysis" / "collector"
    sut = _capsule(directory, records=list(order))
    code, report = _check(directory, sut)
    harness = run_mod.inspect_collector_outputs(
        directory / f"resources-{RUN}.csv", list(SERVICES)
    )
    clean = list(order) == ["start", "inventory", "stop"]
    assert (code == 0) == clean, _problems(report)
    assert (harness["problems"] == []) == clean, harness["problems"]
    assert _about_the_closing_record(harness["problems"]) == (
        _about_the_closing_record(report["problems"])
    )
    if not clean:
        where = ", ".join(
            f"{kind} line {order.index(kind) + 1}"
            for kind in ("start", "inventory", "stop")
        )
        assert f"records are out of order ({where})" in _problems(report)
        # A capsule whose records do not describe one clean run has no
        # unambiguous window, so the resource validation must not run on it
        # either -- the rule that keeps the coverage from being left unchecked.
        assert report["resource_validation"].startswith("not run")
        assert "UNCHECKED" in _problems(report)


def test_both_halves_read_the_first_record_of_a_duplicated_kind(tmp_path) -> None:
    """Two collectors appended to one output: both halves must read the SAME
    closing record, and therefore seal the same window for the same bytes.

    ``one_record`` here keeps ``found[0]``; until 2026-09-20 the harness half
    overwrote its record on every match and kept the LAST, so this capsule was
    reported with a 45 s window here and a 95 s window there. Both halves
    refuse it over the duplicate counts, so no verdict diverged -- but the
    figures the two reports carried about one set of bytes did, and the rule
    stayed safe only while the duplicate count was never relaxed.
    """
    second_start = "2026-09-07T10:00:50Z"
    second_end = "2026-09-07T10:01:35Z"
    directory = tmp_path / "analysis" / "collector"
    sut = _capsule(
        directory,
        records=[
            RECORDS["start"],
            RECORDS["inventory"],
            RECORDS["stop"],
            f"{second_start} start: collector_sha256={SHA} host={NODE} "
            "source=cgroup interval=1s duration=45s pacing: wall-clock; "
            f"timestamps: date; expected services: {','.join(SERVICES)}",
            f"{second_end} inventory: observed={','.join(SERVICES)} "
            f"expected={','.join(SERVICES)} missing=none unnamed_ids=0",
            second_end + " " + _stop()[len(WINDOW_END) + 1:],
        ],
    )
    code, report = _check(directory, sut)
    harness = run_mod.inspect_collector_outputs(
        directory / f"resources-{RUN}.csv", list(SERVICES)
    )
    assert code == 1
    assert harness["problems"] != []
    # The first collector's window, in both halves, down to the bytes read.
    assert report["window"] == [WINDOW_START, WINDOW_END]
    assert harness["window"] == report["window"]
    assert report["window_seconds"] == 45
    assert harness["window_seconds"] == report["window_seconds"]
    assert harness["stop_line"] == report["stop_line"]
    assert harness["inventory"] == report["inventory"]
    assert harness["samples"] == report["samples"] == len(SAMPLE_SECONDS)
    assert harness["distinct_instants_in_window"] == (
        report["distinct_instants_in_window"]
    )
    # Both halves count the duplicates and refuse the capsule for it. They
    # word that count differently -- this one names the lines the records sit
    # on -- which is why the sentences themselves are not compared here; what
    # had to stop differing is the record each of them read, asserted above.
    assert "2 'stop:' lines" in _problems(report)
    assert any("2 'stop:' lines" in problem for problem in harness["problems"])


def test_the_runbook_states_the_one_stamped_round_exemption() -> None:
    """The runbook's invalidating list against the rule both halves apply.

    A closing record accounting for exactly one stamped round accounts for the
    priming round, which writes no row at all
    (``collect-resources.sh:80-82``), so a CSV with no instant inside the
    collector's window is clean there and the rule bites only above one round
    (``run.py``: ``elif accounted > 1 and instants_in_window == 0``). Until
    2026-09-20 the runbook stated that contradiction without the exemption --
    'or not one instant inside it beside stamped rounds' -- so a reader
    checking a capsule against the runbook would have called invalid a capsule
    the code accepts.
    """

    def problems(samples: int) -> list[str]:
        return run_mod.reconcile_closing_record(
            samples=samples,
            withheld=0,
            instants_in_window=0,
            csv_readable=True,
            window=(WINDOW_START, WINDOW_END),
            window_seconds=45,
            interval_s=1.0,
            duration_s=45.0,
            record_lines=(1, 2, 3),
        )["problems"]

    assert problems(1) == []
    assert any("cannot both be true" in problem for problem in problems(2))
    runbook = (
        REPO_ROOT / "docs" / "setup" / "qemu_integrated_gateway.md"
    ).read_text(encoding="utf-8")
    assert (
        "or not one instant inside it while the record accounts for more than "
        "the single priming round"
    ) in runbook
    assert "or not one instant inside it beside stamped rounds" not in runbook


def test_the_two_halves_read_the_closing_record_by_the_same_rule() -> None:
    """``inspect_collector_outputs`` seals the timed runs and this script
    checks the preflight: the table that says what each figure counts, which
    of them are elapsed time in neither count, which is a decimal and what the
    protocol judges instead must be the same in both, or a closing record
    could be unusable on one side and clean on the other.

    The reconciliation itself is not a second copy of the same words: both
    halves call ONE function (2026-09-20), so the rule cannot drift apart
    again.
    """
    spec = importlib.util.spec_from_file_location("collector_check_module", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert module.CLOSING_COUNTERS == run_mod._CLOSING_COUNTERS
    assert module.DECIMAL_COUNTERS == run_mod._DECIMAL_COUNTERS
    assert module.UNMEASURED_COUNTERS == run_mod._UNMEASURED_COUNTERS
    assert module.JUDGED_ELSEWHERE == run_mod._JUDGED_ELSEWHERE
    assert module.reconcile_closing_record is run_mod.reconcile_closing_record
    # And one parser for the cells of the CSV, the ingest's own.
    assert module.parse_csv_timestamp is resources_mod.parse_csv_timestamp


# ---------------------------------------------------------------------------
# The validation itself, and the inputs it needs
# ---------------------------------------------------------------------------
def test_the_resource_validation_really_runs_on_a_usable_window(tmp_path) -> None:
    """A CSV that cannot be ingested is rejected THROUGH validate_resources_csv.

    Ten instants are far below MIN_DISTINCT_SAMPLE_INSTANTS and cover a
    fraction of the window: the old skip would have let this output through
    with one row per service and a clean inventory.
    """
    directory = tmp_path / "analysis" / "collector"
    sut = _capsule(directory, csv_text=_csv_rows(seconds=range(1, 11)))
    code, report = _check(directory, sut)
    assert code == 1
    assert report["resource_validation"] == "run"
    assert "validate_resources_csv: " in _problems(report)
    assert "distinct sample instant" in _problems(report)


def test_a_csv_from_another_host_is_rejected(tmp_path) -> None:
    directory = tmp_path / "analysis" / "collector"
    sut = _capsule(directory, csv_text=_csv_rows(host="another-machine"))
    code, report = _check(directory, sut)
    assert code == 1
    assert "do not match the SUT node/hostname" in _problems(report)


@pytest.mark.parametrize(
    "kwargs, expected",
    [
        ({"environment": False}, "could not be read"),
        ({"node": None}, "carries no 'node'"),
    ],
)
def test_an_unusable_sut_environment_stops_the_validation(
    tmp_path, kwargs: dict, expected: str
) -> None:
    directory = tmp_path / "analysis" / "collector"
    sut = _capsule(directory, **kwargs)
    code, report = _check(directory, sut)
    assert code == 1
    assert expected in _problems(report)
    assert report["resource_validation"] == "not run: the SUT node is unknown"
    assert "UNCHECKED" in _problems(report)


# ---------------------------------------------------------------------------
# The other problems the check must not let through
# ---------------------------------------------------------------------------
def test_a_self_test_marker_is_a_problem(tmp_path) -> None:
    directory = tmp_path / "analysis" / "collector"
    sut = _capsule(directory, self_test=True)
    code, report = _check(directory, sut)
    assert code == 1
    assert "NOT a measurement" in _problems(report)


def test_a_deployed_collector_that_is_not_the_clones_is_a_problem(tmp_path) -> None:
    directory = tmp_path / "analysis" / "collector"
    sut = _capsule(directory)
    code, report = _check(directory, sut, want_sha="cd" * 32)
    assert code == 1
    assert f"deployed collector hash {SHA} is not the clean clone's" in _problems(report)


@pytest.mark.parametrize(
    "kwargs, expected",
    [
        ({"lifecycle": False}, "no lifecycle companion"),
        ({"csv_text": ""}, "has no 'container'/'ts_utc' column"),
    ],
)
def test_a_missing_companion_or_unusable_csv_is_a_problem(
    tmp_path, kwargs: dict, expected: str
) -> None:
    directory = tmp_path / "analysis" / "collector"
    sut = _capsule(directory, **kwargs)
    code, report = _check(directory, sut)
    assert code == 1
    assert expected in _problems(report)


def test_an_expected_service_without_rows_is_a_problem(tmp_path) -> None:
    directory = tmp_path / "analysis" / "collector"
    sut = _capsule(directory)
    code, report = _check(directory, sut, expect=",".join(SERVICES + ["egw-ditto-1"]))
    assert code == 1
    assert "expected service egw-ditto-1 has no rows" in _problems(report)


def test_no_expected_services_is_a_problem(tmp_path) -> None:
    directory = tmp_path / "analysis" / "collector"
    sut = _capsule(directory)
    code, report = _check(directory, sut, expect="")
    assert code == 1
    assert "no expected services were given" in _problems(report)


# ---------------------------------------------------------------------------
# The report is always written, and the interface is positional
# ---------------------------------------------------------------------------
def test_the_report_is_written_even_when_the_check_raises(tmp_path) -> None:
    """A truncated diagnostics file is not valid UTF-8; the check still reports."""
    directory = tmp_path / "analysis" / "collector"
    sut = _capsule(directory)
    Path(directory / f"resources-{RUN}.csv.diagnostics.log").write_bytes(
        RECORDS["start"].encode("utf-8") + b"\n\xff\xfe stop: samples=44\n"
    )
    code, report = _check(directory, sut)
    assert code == 1
    assert "collector_check raised" in _problems(report)
    assert "UnicodeDecodeError" in _problems(report)


def test_wrong_arguments_are_a_problem_not_a_traceback(tmp_path) -> None:
    directory = tmp_path / "analysis" / "collector"
    sut = _capsule(directory)
    code, report = _check(directory, sut, args=[str(directory), RUN, "a", SHA])
    assert code == 1
    assert "wrong number of arguments (4)" in _problems(report)
    assert report["resource_validation"] == "not run"


def test_no_arguments_at_all_exit_1_with_the_usage(tmp_path) -> None:
    result = subprocess.run(
        [sys.executable, str(SCRIPT)],
        capture_output=True, text=True, timeout=300, check=False,
        env={**os.environ, "PYTHONPATH": str(SRC_DIR)},
    )
    assert result.returncode == 1
    assert "usage: collector_check.py" in result.stderr
