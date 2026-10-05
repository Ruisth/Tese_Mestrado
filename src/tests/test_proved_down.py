"""The proved-down interval of decision 1a (adopted 2026-09-30, prospective).

Two halves, both pure and read from files only:

- ``egw_experiments.resources``: ``validate_resources_csv(..., proved_down=...)``
  applies the rule to the restarted container C alone - the whole-second
  convention, the effective end E = min(S, D + RESTART_RECOVERY_MAX_S), the
  edge rule resuming from E, rows between D and S and in S's own second
  rejected - and without the keyword (or with None) every problem text is
  the one the file always had;
- ``egw_experiments.proved_down``: the interval derived from a run directory
  (the restart record, the docker-events fetch and its coverage verdict, the
  capture, the StartedAt record), with ANY ambiguity giving no interval and
  the reason named.

Fixture F (map-1a section 9): the measured window 2026-10-01T10:00:00Z to
10:02:00Z; six containers sampled at every whole second of it, on host
``egw-guest``; the controller's rows 10:01:01 to 10:01:07 absent; the die at
10:01:00.400000000Z and the start at 10:01:06.300000000Z.
"""
from __future__ import annotations

import calendar
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from egw_experiments import resources
from egw_experiments.protocol import RESTART_RECOVERY_MAX_S


def _pd():
    """The derivation module, imported where it is used (the validator's cases need only resources)."""
    from egw_experiments import proved_down

    return proved_down


C = "egw-controller-1"
HOST = "egw-guest"
CONTAINERS = (
    "egw-mosquitto-1",
    "egw-mongodb-1",
    "egw-ditto-policies-1",
    "egw-ditto-things-1",
    "egw-ditto-gateway-1",
    C,
)
DAY = "2026-10-01"
NS = 1_000_000_000
CID = "3f" * 32


def _second(clock: str) -> datetime:
    return datetime.fromisoformat(f"{DAY}T{clock}+00:00")


def _ns(clock: str) -> int:
    """'HH:MM:SS[.fffffffff]' of DAY, as integer nanoseconds since the epoch."""
    whole, _, frac = clock.partition(".")
    return calendar.timegm(_second(whole).utctimetuple()) * NS + int((frac or "0").ljust(9, "0"))


def _epoch(clock: str) -> int:
    return calendar.timegm(_second(clock).utctimetuple())


def _csv(
    path: Path,
    *,
    end: str = "10:02:00",
    absent: dict[str, tuple[str, str] | list[tuple[str, str]]] | None = None,
    extra: tuple[tuple[str, str, str], ...] = (),
) -> Path:
    """Six containers at every whole second from 10:00:00 to ``end``; ``absent``
    maps a container to an inclusive range of seconds (or a list of ranges)
    without its rows; ``extra`` adds (second, container, 'cpu,mem,pct') rows
    in time order."""
    absent = {C: ("10:01:01", "10:01:07")} if absent is None else absent
    holes = {name: [spans] if isinstance(spans, tuple) else list(spans) for name, spans in absent.items()}
    lines = ["ts_utc,container,cpu_pct,mem_bytes,mem_pct,host"]
    t = _second("10:00:00")
    stop = _second(end)
    while t <= stop:
        clock = t.strftime("%H:%M:%S")
        for name in CONTAINERS:
            if any(_second(lo) <= t <= _second(hi) for lo, hi in holes.get(name, [])):
                continue
            lines.append(f"{DAY}T{clock}Z,{name},1.5,1048576,0.5,{HOST}")
        for at, name, values in extra:
            if at == clock:
                lines.append(f"{DAY}T{clock}Z,{name},{values},{HOST}")
        t += timedelta(seconds=1)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def _validate(path: Path, *, end: str = "10:02:00", **kwargs) -> list[str]:
    return resources.validate_resources_csv(
        path,
        expected_host=HOST,
        expected_window_s=(_second(end) - _second("10:00:00")).total_seconds(),
        expected_window_start_utc=f"{DAY}T10:00:00Z",
        expected_window_end_utc=f"{DAY}T{end}Z",
        **kwargs,
    )


def _interval(die: str = "10:01:00.4", start: str = "10:01:06.3", container: str = C):
    return resources.ProvedDownInterval(container=container, die_ns=_ns(die), start_ns=_ns(start))


U0_PROBLEM = (
    "1 sampling gap(s) exceed the protocol maximum of 5 s (MAX_SAMPLE_GAP_S): "
    "container 'egw-controller-1': 2026-10-01T10:01:00+00:00 to 2026-10-01T10:01:08+00:00 (8.0 s)"
)


# --------------------------------------------------------------------------
# The validator: without the interval, exactly what it always said
# --------------------------------------------------------------------------


def test_u0_without_the_interval_the_problem_text_is_the_pinned_one(tmp_path) -> None:
    path = _csv(tmp_path / "f.csv")
    assert _validate(path) == [U0_PROBLEM]
    assert _validate(path, proved_down=None) == [U0_PROBLEM]


@pytest.mark.parametrize(
    "absent",
    [
        {C: ("10:01:01", "10:01:07")},
        {C: [("10:00:21", "10:00:26"), ("10:01:01", "10:01:07")], "egw-mosquitto-1": ("10:01:01", "10:01:09")},
        {},
    ],
)
def test_proved_down_none_is_byte_identical_to_no_keyword(tmp_path, absent) -> None:
    path = _csv(tmp_path / "f.csv", absent=absent)
    assert _validate(path, proved_down=None) == _validate(path)


# --------------------------------------------------------------------------
# The validator with the interval (map-1a section 9, U1-U11)
# --------------------------------------------------------------------------


def test_u1_the_proved_down_gap_is_accepted_and_the_outcomes_recorded(tmp_path) -> None:
    path = _csv(tmp_path / "f.csv")
    outcome: dict = {}
    assert _validate(path, proved_down=_interval(), proved_down_outcome=outcome) == []
    assert outcome["applies"] is True and outcome["why_not"] is None
    assert outcome["container"] == C
    assert outcome["last_row_before_die"] == "2026-10-01T10:01:00+00:00"
    assert outcome["first_row_after_start"] == "2026-10-01T10:01:08+00:00"
    assert outcome["edge_gap_before_s"] == 0.0
    assert outcome["edge_gap_after_s"] == 2.0
    assert outcome["capped"] is False
    assert outcome["interval_s"] == pytest.approx(5.9)
    assert outcome["exempt_s"] == pytest.approx(5.9)
    assert outcome["rejected_rows"] == [] and outcome["rows_between"] == []
    assert outcome["rows_in_start_second"] == []


def test_the_pure_helper_gives_the_same_outcomes_from_the_containers_instants(tmp_path) -> None:
    instants = [_second("10:00:59"), _second("10:01:00"), _second("10:01:08"), _second("10:01:09")]
    outcome = resources.proved_down_outcomes(instants, _interval())
    assert outcome["applies"] is True
    assert (outcome["edge_gap_before_s"], outcome["edge_gap_after_s"]) == (0.0, 2.0)
    assert outcome["die_second_utc"] == "2026-10-01T10:01:00+00:00"
    assert outcome["start_second_utc"] == "2026-10-01T10:01:06+00:00"
    assert outcome["effective_end_second_utc"] == "2026-10-01T10:01:06+00:00"


def test_u2_a_long_hole_is_exempt_because_the_events_say_so_not_because_of_its_length(tmp_path) -> None:
    path = _csv(tmp_path / "f.csv", absent={C: ("10:00:31", "10:01:02")})
    outcome: dict = {}
    assert _validate(path, proved_down=_interval("10:00:30.5", "10:01:01.2"), proved_down_outcome=outcome) == []
    assert (outcome["edge_gap_before_s"], outcome["edge_gap_after_s"]) == (0.0, 2.0)


def test_u3_another_gap_of_the_restarted_container_still_fails_and_the_d_s_pair_is_not_listed(tmp_path) -> None:
    path = _csv(tmp_path / "f.csv", absent={C: [("10:00:21", "10:00:26"), ("10:01:01", "10:01:07")]})
    problems = _validate(path, proved_down=_interval())
    assert problems == [
        "1 sampling gap(s) exceed the protocol maximum of 5 s (MAX_SAMPLE_GAP_S): "
        "container 'egw-controller-1': 2026-10-01T10:00:20+00:00 to 2026-10-01T10:00:27+00:00 (7.0 s)"
    ]


def test_u4_an_edge_before_the_die_above_5_s_is_rejected(tmp_path) -> None:
    path = _csv(tmp_path / "f.csv", absent={C: ("10:00:55", "10:01:07")})
    outcome: dict = {}
    problems = _validate(path, proved_down=_interval(), proved_down_outcome=outcome)
    assert outcome["edge_gap_before_s"] == 6.0 and outcome["last_row_before_die"] == "2026-10-01T10:00:54+00:00"
    assert len(problems) == 1 and problems[0].startswith("1 sampling gap(s) exceed the protocol maximum of 5 s")
    assert "edge before the proved-down interval" in problems[0] and "(6.0 s)" in problems[0]


def test_u5_an_edge_after_the_start_above_5_s_is_rejected(tmp_path) -> None:
    path = _csv(tmp_path / "f.csv", absent={C: ("10:01:01", "10:01:11")})
    outcome: dict = {}
    problems = _validate(path, proved_down=_interval(), proved_down_outcome=outcome)
    assert outcome["edge_gap_after_s"] == 6.0 and outcome["first_row_after_start"] == "2026-10-01T10:01:12+00:00"
    assert len(problems) == 1
    assert "edge after the proved-down interval" in problems[0] and "(6.0 s)" in problems[0]


def test_u6_a_row_in_the_starts_own_second_is_rejected(tmp_path) -> None:
    path = _csv(tmp_path / "f.csv", absent={C: ("10:01:01", "10:01:05")})
    outcome: dict = {}
    problems = _validate(path, proved_down=_interval(), proved_down_outcome=outcome)
    assert outcome["rows_in_start_second"] == ["2026-10-01T10:01:06+00:00"]
    assert outcome["rejected_rows"] == ["2026-10-01T10:01:06+00:00"]
    assert len(problems) == 1
    assert "less than one sampling interval" in problems[0] and "2026-10-01T10:01:06+00:00" in problems[0]


@pytest.mark.parametrize("values", ["0.0,0,0.0", "7.5,2048,2.0"])
def test_u7_a_row_between_the_die_and_the_start_is_rejected_whatever_its_values(tmp_path, values) -> None:
    path = _csv(tmp_path / "f.csv", extra=(("10:01:03", C, values),))
    outcome: dict = {}
    problems = _validate(path, proved_down=_interval(), proved_down_outcome=outcome)
    assert outcome["rows_between"] == ["2026-10-01T10:01:03+00:00"]
    assert outcome["rejected_rows"] == ["2026-10-01T10:01:03+00:00"]
    assert any("stamped between the die" in p and "2026-10-01T10:01:03+00:00" in p for p in problems), problems
    assert problems


def test_u8_only_the_restarted_container_is_exempt_every_other_keeps_5_s(tmp_path) -> None:
    path = _csv(tmp_path / "f.csv", absent={C: ("10:01:01", "10:01:07"), "egw-mosquitto-1": ("10:01:01", "10:01:06")})
    problems = _validate(path, proved_down=_interval())
    assert problems == [
        "1 sampling gap(s) exceed the protocol maximum of 5 s (MAX_SAMPLE_GAP_S): "
        "container 'egw-mosquitto-1': 2026-10-01T10:01:00+00:00 to 2026-10-01T10:01:07+00:00 (7.0 s)"
    ]


def test_u9_a_capped_restart_resumes_the_ordinary_rule_from_d_plus_120_s(tmp_path) -> None:
    path = _csv(tmp_path / "f.csv", end="10:05:00", absent={C: ("10:01:01", "10:03:11")})
    outcome: dict = {}
    problems = _validate(path, end="10:05:00", proved_down=_interval("10:01:00.4", "10:03:10.2"),
                         proved_down_outcome=outcome)
    assert outcome["capped"] is True
    assert outcome["interval_s"] == pytest.approx(129.8)
    assert outcome["exempt_s"] == pytest.approx(RESTART_RECOVERY_MAX_S)
    assert outcome["effective_end_second_utc"] == "2026-10-01T10:03:00+00:00"
    assert outcome["edge_gap_after_s"] == 12.0
    assert len(problems) == 1 and "(12.0 s)" in problems[0], problems


def test_u10_a_capped_restart_whose_residual_gap_is_within_5_s_is_accepted(tmp_path) -> None:
    path = _csv(tmp_path / "f.csv", end="10:05:00", absent={C: ("10:01:01", "10:03:02")})
    outcome: dict = {}
    assert _validate(path, end="10:05:00", proved_down=_interval("10:01:00.4", "10:03:01.2"),
                     proved_down_outcome=outcome) == []
    assert outcome["capped"] is True
    assert outcome["edge_gap_after_s"] == 3.0
    assert outcome["first_row_after_start"] == "2026-10-01T10:03:03+00:00"


def test_u11_an_interval_without_rows_either_side_is_no_interval_and_the_ordinary_rule_stands(tmp_path) -> None:
    path = _csv(tmp_path / "f.csv")
    outcome: dict = {}
    problems = _validate(path, proved_down=_interval(container="egw-absent-1"), proved_down_outcome=outcome)
    assert problems == [U0_PROBLEM]
    assert outcome["applies"] is False and "no row" in outcome["why_not"]


def test_a_die_and_a_start_in_one_second_reject_the_row_of_that_second_conservatively(tmp_path) -> None:
    """sec(D) = sec(S): the row of that second may have been taken before D or less than 1 s after S; the rule
    cannot tell, so it is rejected (the conservative reading: a false rejection, never a false acceptance)."""
    path = _csv(tmp_path / "f.csv", absent={})
    outcome: dict = {}
    problems = _validate(path, proved_down=_interval("10:01:00.2", "10:01:00.7"), proved_down_outcome=outcome)
    assert "2026-10-01T10:01:00+00:00" in outcome["rows_in_start_second"]
    assert problems and any("less than one sampling interval" in p for p in problems)


# --------------------------------------------------------------------------
# The rows between D and S, each end pinned (review of 2026-09-30, round 1:
# rejecting only from sec(D) + 2 s, only to sec(S) - 2 s, or only to sec(E)
# when capped, all passed the cases above)
# --------------------------------------------------------------------------


def test_a_row_in_the_first_second_after_the_dies_second_is_between_d_and_s(tmp_path) -> None:
    """D = 10:01:00.4, S = 10:01:06.3: the row stamped 10:01:01 = sec(D) + 1 s is in (sec(D), sec(S))."""
    path = _csv(tmp_path / "f.csv", absent={C: ("10:01:02", "10:01:07")})
    outcome: dict = {}
    problems = _validate(path, proved_down=_interval(), proved_down_outcome=outcome)
    assert outcome["rows_between"] == ["2026-10-01T10:01:01+00:00"], outcome
    assert any("stamped between the die" in p and "2026-10-01T10:01:01+00:00" in p for p in problems), problems


def test_a_row_in_the_last_second_before_the_starts_second_is_between_d_and_s(tmp_path) -> None:
    """D = 10:01:00.4, S = 10:01:06.3: the row stamped 10:01:05 = sec(S) - 1 s is in (sec(D), sec(S))."""
    path = _csv(tmp_path / "f.csv", absent={C: [("10:01:01", "10:01:04"), ("10:01:06", "10:01:07")]})
    outcome: dict = {}
    problems = _validate(path, proved_down=_interval(), proved_down_outcome=outcome)
    assert outcome["rows_between"] == ["2026-10-01T10:01:05+00:00"], outcome
    assert outcome["rows_in_start_second"] == [] and outcome["edge_gap_after_s"] == 2.0, outcome
    assert any("stamped between the die" in p and "2026-10-01T10:01:05+00:00" in p for p in problems), problems


def test_a_capped_restart_rejects_a_row_between_the_effective_end_and_the_start(tmp_path) -> None:
    """Capped: D = 10:01:00.4, S = 10:03:02.4 (122 s), E = D + 120 s = 10:03:00.4. The edge after (10:03:00 to
    10:03:03, 3 s) is within 5 s, so only the rule on the rows between D and S can reject the row stamped
    10:03:01: after sec(E), but still before sec(S), when no instance was running."""
    path = _csv(tmp_path / "f.csv", end="10:05:00", absent={C: [("10:01:01", "10:03:00"), ("10:03:02", "10:03:02")]})
    outcome: dict = {}
    problems = _validate(path, end="10:05:00", proved_down=_interval("10:01:00.4", "10:03:02.4"),
                         proved_down_outcome=outcome)
    assert outcome["capped"] is True and outcome["effective_end_second_utc"] == "2026-10-01T10:03:00+00:00"
    assert outcome["edge_gap_after_s"] == 3.0, outcome
    assert outcome["rows_between"] == ["2026-10-01T10:03:01+00:00"], outcome
    assert any("stamped between the die" in p and "2026-10-01T10:03:01+00:00" in p for p in problems), problems


# --------------------------------------------------------------------------
# The derivation from the run directory
# --------------------------------------------------------------------------

D_CLOCK = "10:01:00.4"
S_CLOCK = "10:01:06.3"
T0 = _epoch("09:59:50")
T1 = _epoch("10:12:00")


def _event(action: str, name: str, cid: str, ns: int, **attrs: str) -> dict:
    return {"status": action, "id": cid, "from": f"stub/{name}:1", "Type": "container", "Action": action,
            "Actor": {"ID": cid, "Attributes": {"image": f"stub/{name}:1", "name": name, **attrs}},
            "scope": "local", "time": ns // NS, "timeNano": ns}


def _restart_events(die: str = D_CLOCK, start: str = S_CLOCK, cid: str = CID, start_cid: str | None = None) -> list:
    """A compose restart as Docker 25 documents it: kill (15), die, stop, start, restart."""
    d, s = _ns(die), _ns(start)
    return [
        _event("exec_create: sh -c true", "egw-mosquitto-1", "ab" * 32, d - 5 * NS),
        _event("kill", C, cid, d - 300_000_000, signal="15"),
        _event("die", C, cid, d, exitCode="0"),
        _event("stop", C, cid, d + 1_000_000),
        _event("start", C, start_cid or cid, s),
        _event("restart", C, start_cid or cid, s + 1_000_000),
        _event("exec_create: sh -c true", "egw-mosquitto-1", "ab" * 32, s + 5 * NS),
    ]


def _coverage(first: str = "coverage=complete", *, expected: str = "die,start", container: str = C,
              since: str = str(T0), until: str = str(T1), extra: tuple[str, ...] = ()) -> str:
    return "\n".join((
        first,
        f"requested_since_guest_epoch={since}",
        "requested_since_utc=2026-10-01T09:59:50Z",
        f"requested_until_guest_epoch={until}",
        "requested_until_utc=2026-10-01T10:12:00Z",
        "requested_until_note=the stop request of the docker-events fetch",
        "provenance=docker events --since <recorder since> --filter type=container --format {{json .}}",
        "clock=guest: every epoch here is the guest's date +%s or the daemon's timeNano; no host instant",
        f"expected={expected}",
        f"container={container}",
        "events_lines=7",
        "expected_found=die@2026-10-01T10:01:00Z,start@2026-10-01T10:01:06Z",
        "rule_R7=held: every expected event of egw-controller-1 is captured within the window",
        *extra,
    )) + "\n"


def _started_at(*, container: str = C, cid: str = CID, started_at: str = "2026-10-01T10:01:06.299812345Z",
                guest_epoch: str = str(T1 + 20), extra: tuple[str, ...] = ()) -> str:
    return "\n".join((f"container={container}", f"container_id={cid}", f"started_at={started_at}",
                      f"guest_epoch={guest_epoch}", *extra)) + "\n"


def _fetch(hook: str, dest: str, returncode: int = 0, dest_exists: bool = True) -> dict:
    return {"hook": hook, "returncode": returncode, "dest_exists": dest_exists, "dest_file": dest}


def _run_dir(
    tmp_path: Path,
    *,
    events: list | str | None = None,
    coverage: str | None = None,
    started_at: str | None = None,
    restart: dict | None = None,
    fetches: list | None = None,
    condition_id: str = "controller_restart",
) -> tuple[Path, dict]:
    run_dir = tmp_path / "raw" / "controller_restart-r01"
    sut = run_dir / "logs" / "sut"
    sut.mkdir(parents=True)
    events = _restart_events() if events is None else events
    if events != "absent":
        text = events if isinstance(events, str) else "".join(json.dumps(e) + "\n" for e in events)
        (sut / "docker-events.log").write_text(text, encoding="utf-8")
    if coverage != "absent":
        (sut / "docker-events.coverage.txt").write_text(_coverage() if coverage is None else coverage, "utf-8")
    if started_at != "absent":
        (sut / "controller-started-at.txt").write_text(_started_at() if started_at is None else started_at, "utf-8")
    manifest = {
        "condition_id": condition_id,
        "restart": {"executed": True, "returncode": 0} if restart is None else restart,
        "sut_log_fetches": [
            _fetch("broker_log", "logs/sut/broker.log"),
            _fetch("controller_log", "logs/sut/controller.log"),
            _fetch("docker_events", "logs/sut/docker-events.log"),
            _fetch("started_at", "logs/sut/controller-started-at.txt"),
        ] if fetches is None else fetches,
    }
    return run_dir, manifest


def test_the_constants_name_the_files_the_harness_writes() -> None:
    from egw_experiments import run as run_mod

    assert _pd().STARTED_AT_FILENAME == "controller-started-at.txt"
    assert _pd().CONTAINER == C
    assert run_mod.SUT_LOG_FILES["docker_events"] == "docker-events.log"


def test_a_good_capture_and_started_at_give_the_interval(tmp_path) -> None:
    run_dir, manifest = _run_dir(tmp_path)
    interval, why_not, facts = _pd().derive_proved_down(run_dir, manifest)
    assert why_not is None
    assert interval == resources.ProvedDownInterval(container=C, die_ns=_ns(D_CLOCK), start_ns=_ns(S_CLOCK))
    assert facts["container"] == C and facts["container_id"] == CID
    assert facts["die_ns"] == _ns(D_CLOCK) and facts["die_utc"] == "2026-10-01T10:01:00.400000000Z"
    assert facts["start_ns"] == _ns(S_CLOCK) and facts["start_utc"] == "2026-10-01T10:01:06.300000000Z"
    assert facts["effective_end_ns"] == _ns(S_CLOCK) and facts["capped"] is False
    assert facts["effective_end_utc"] == "2026-10-01T10:01:06.300000000Z"
    assert facts["started_at"] == "2026-10-01T10:01:06.299812345Z"
    assert facts["started_at_ns"] == _ns("10:01:06.299812345")
    assert facts["start_minus_started_at_s"] == pytest.approx(0.000187655)
    assert facts["interval_s"] == pytest.approx(5.9) and facts["exempt_s"] == pytest.approx(5.9)
    assert facts["die_exit_code"] == "0"


def test_the_derivation_reads_files_only_and_is_deterministic(tmp_path) -> None:
    run_dir, manifest = _run_dir(tmp_path)
    before = {p: p.read_bytes() for p in run_dir.rglob("*") if p.is_file()}
    first = _pd().derive_proved_down(run_dir, manifest)
    assert _pd().derive_proved_down(run_dir, manifest) == first
    assert {p: p.read_bytes() for p in run_dir.rglob("*") if p.is_file()} == before


@pytest.mark.parametrize("stamp, expected", [
    ("2026-10-01T10:01:06Z", _ns("10:01:06")),
    ("2026-10-01T10:01:06.3Z", _ns("10:01:06.3")),
    ("2026-10-01T10:01:06.123456789Z", _ns("10:01:06.123456789")),
    ("2026-10-01T10:01:06.1234567891Z", None),
    ("2026-10-01T10:01:06.3+00:00", None),
    ("2026-10-01 10:01:06Z", None),
    ("2026-13-01T10:01:06Z", None),
    ("", None),
])
def test_started_at_is_parsed_to_integer_nanoseconds(stamp, expected) -> None:
    assert _pd().parse_rfc3339_ns(stamp) == expected


@pytest.mark.parametrize("zero", [0xFF10, 0x0660], ids=["fullwidth", "arabic-indic"])
def test_a_started_at_in_digits_other_than_ascii_is_not_rfc_3339(tmp_path, zero) -> None:
    """Review of 2026-09-30, round 1: RFC 3339's DIGIT is ASCII 0-9 (fetch_started_at.sh checks [0-9]); a
    started_at in other Unicode decimal digits, which Python's regex digit class and int() both accept, is not of
    the record's form: it parses to nothing and gives no interval."""
    stamp = "2026-10-01T10:01:06.299812345Z".translate(
        str.maketrans("0123456789", "".join(chr(zero + i) for i in range(10)))
    )
    assert _pd().parse_rfc3339_ns(stamp) is None
    _no_interval(tmp_path, "StartedAt", started_at=_started_at(started_at=stamp))


def _no_interval(tmp_path: Path, words: str, **kwargs) -> dict:
    run_dir, manifest = _run_dir(tmp_path, **kwargs)
    interval, why_not, facts = _pd().derive_proved_down(run_dir, manifest)
    assert interval is None, facts
    assert why_not and words.lower() in why_not.lower(), why_not
    return facts


def test_an_incomplete_capture_gives_no_interval(tmp_path) -> None:
    _no_interval(tmp_path, "complete", coverage=_coverage("coverage=incomplete"))


def test_a_capture_whose_coverage_record_is_missing_gives_no_interval(tmp_path) -> None:
    _no_interval(tmp_path, "coverage", coverage="absent")


def test_a_capture_that_was_not_fetched_gives_no_interval(tmp_path) -> None:
    _no_interval(tmp_path, "docker-events", events="absent")
    fetches = [_fetch("docker_events", "logs/sut/docker-events.log", returncode=1, dest_exists=False),
               _fetch("started_at", "logs/sut/controller-started-at.txt")]
    _no_interval(tmp_path / "b", "docker-events", fetches=fetches)


@pytest.mark.parametrize("expected", ["none", "kill,die", "start"])
def test_a_capture_that_did_not_expect_the_restarts_die_and_start_gives_no_interval(tmp_path, expected) -> None:
    _no_interval(tmp_path, "expected", coverage=_coverage(expected=expected))


def test_a_capture_judged_on_another_container_gives_no_interval(tmp_path) -> None:
    _no_interval(tmp_path, "container", coverage=_coverage(container="egw-mongodb-1"))


def test_a_coverage_record_with_a_key_twice_is_ambiguous(tmp_path) -> None:
    _no_interval(tmp_path, "container", coverage=_coverage(extra=("container=egw-controller-1",)))


def test_zero_dies_give_no_interval(tmp_path) -> None:
    events = [e for e in _restart_events() if e["Action"] != "die"]
    _no_interval(tmp_path, "die", events=events)


def test_zero_starts_give_no_interval(tmp_path) -> None:
    events = [e for e in _restart_events() if e["Action"] != "start"]
    _no_interval(tmp_path, "start", events=events)


def test_two_dies_and_two_starts_are_more_than_one_candidate_pair(tmp_path) -> None:
    events = _restart_events() + _restart_events("10:03:00.1", "10:03:04.9")
    events.sort(key=lambda e: e["timeNano"])
    facts = _no_interval(tmp_path, "exactly one", events=events)
    assert facts["die_events_in_window"] == 2 and facts["start_events_in_window"] == 2


def test_two_starts_after_one_die_give_no_interval(tmp_path) -> None:
    events = _restart_events() + [_event("start", C, CID, _ns("10:01:30.0"))]
    events.sort(key=lambda e: e["timeNano"])
    _no_interval(tmp_path, "exactly one", events=events)


def test_a_start_before_the_die_gives_no_interval(tmp_path) -> None:
    _no_interval(tmp_path, "not after the die", events=_restart_events(die="10:01:06.3", start="10:01:00.4"))


def test_a_die_and_a_start_of_differing_containers_ids_give_no_interval(tmp_path) -> None:
    _no_interval(tmp_path, "different container ids", events=_restart_events(start_cid="4e" * 32))


def test_events_only_in_the_replay_before_run_t0_give_no_interval(tmp_path) -> None:
    """The recorder subscribes with a 120 s replay: a die/start pair older than RUN_T0 is history, not this run."""
    events = _restart_events(die="09:58:30.4", start="09:58:36.3")
    facts = _no_interval(tmp_path, "die", events=events)
    assert facts["die_events_in_window"] == 0 and facts["start_events_in_window"] == 0


def test_a_malformed_line_of_the_capture_gives_no_interval(tmp_path) -> None:
    text = "".join(json.dumps(e) + "\n" for e in _restart_events()) + '{"Action": "die", "timeNano": "1"}\n'
    _no_interval(tmp_path, "timeNano", events=text)


def test_started_at_more_than_1_s_from_the_start_gives_no_interval(tmp_path) -> None:
    _no_interval(tmp_path, "1 s", started_at=_started_at(started_at="2026-10-01T10:01:07.800000001Z"))
    run_dir, manifest = _run_dir(tmp_path / "ok", started_at=_started_at(started_at="2026-10-01T10:01:07.3Z"))
    assert _pd().derive_proved_down(run_dir, manifest)[0] is not None, "exactly 1 s is within the bound"


def test_a_started_at_record_of_another_container_id_gives_no_interval(tmp_path) -> None:
    _no_interval(tmp_path, "container id", started_at=_started_at(cid="4e" * 32))


def test_a_started_at_record_of_another_container_gives_no_interval(tmp_path) -> None:
    _no_interval(tmp_path, "container", started_at=_started_at(container="egw-mongodb-1"))


def test_a_started_at_read_before_the_start_gives_no_interval(tmp_path) -> None:
    _no_interval(tmp_path, "before the start", started_at=_started_at(guest_epoch=str(_epoch("10:01:05"))))


def test_a_missing_started_at_record_gives_no_interval(tmp_path) -> None:
    _no_interval(tmp_path, "StartedAt", started_at="absent")


@pytest.mark.parametrize("record", [
    "",
    _started_at(started_at=""),
    _started_at(guest_epoch="1790000000.5"),
    _started_at(cid="3F" * 32),
    _started_at(extra=("started_at=2026-10-01T10:01:06.3Z",)),
    _started_at(extra=("status=running",)),
])
def test_a_malformed_started_at_record_gives_no_interval(tmp_path, record) -> None:
    _no_interval(tmp_path, "StartedAt", started_at=record)


def test_a_whole_number_too_long_to_convert_gives_no_interval_and_never_raises(tmp_path) -> None:
    """Review of 2026-09-30, round 0: a guest epoch or a capture bound of digits only, but more of them than Python
    converts from text (sys.get_int_max_str_digits(), 4300 by default; fetch_started_at.sh checks digits only), is
    not of its form: no interval, never an exception - the derivation runs inside the harness, before its manifest
    is written."""
    huge = "9" * 5000
    _no_interval(tmp_path / "epoch", "StartedAt", started_at=_started_at(guest_epoch=huge))
    _no_interval(tmp_path / "since", "whole-number", coverage=_coverage(since=huge))
    _no_interval(tmp_path / "until", "whole-number", coverage=_coverage(until=huge))


def test_a_die_and_a_start_past_any_utc_instant_give_no_interval_and_never_raise(tmp_path) -> None:
    """The same for a window whose bounds convert but lie past the last UTC second text can name (year 9999): a die
    and a start inside it are not instants the rows' whole seconds can be compared with."""
    t0 = 10 ** 19
    events = [_event("die", C, CID, (t0 + 10) * NS, exitCode="0"), _event("start", C, CID, (t0 + 15) * NS)]
    _no_interval(tmp_path, "UTC", events=events, coverage=_coverage(since=str(t0), until=str(t0 + 100)))


def test_a_start_in_the_last_second_utc_text_can_name_gives_no_interval_and_never_raises(tmp_path) -> None:
    """Review of 2026-09-30, round 1: a start in 9999-12-31T23:59:59 can be named, but the second one sampling
    interval after its own - where the validator looks for the first row after the start - cannot, and the
    validator raised there, inside the harness's ingest. No row can be stamped after that second, so the
    derivation gives no interval; the ingest is never handed one it cannot judge."""
    last = calendar.timegm((9999, 12, 31, 23, 59, 59, 0, 0, 0))
    die_ns, start_ns = (last - 9) * NS + 400_000_000, last * NS + 500_000_000
    run_dir, manifest = _run_dir(
        tmp_path,
        events=[_event("die", C, CID, die_ns, exitCode="0"), _event("start", C, CID, start_ns)],
        coverage=_coverage(since=str(last - 59), until=str(last)),
        started_at=_started_at(started_at="9999-12-31T23:59:59.4Z", guest_epoch=str(last + 1)),
    )
    interval, why_not, _facts = _pd().derive_proved_down(run_dir, manifest)
    assert interval is None and "sampling interval after the start" in why_not, why_not
    rows = "".join(f"9999-12-31T23:59:{second:02d}Z,{name},1.5,1048576,0.5,{HOST}\n"
                   for second in range(20, 51) for name in ("egw-mosquitto-1", C))
    path = tmp_path / "f.csv"
    path.write_text("ts_utc,container,cpu_pct,mem_bytes,mem_pct,host\n" + rows, encoding="utf-8")
    assert resources.validate_resources_csv(path, expected_host=HOST, proved_down=interval) == []


def test_a_started_at_fetch_that_failed_gives_no_interval(tmp_path) -> None:
    fetches = [_fetch("docker_events", "logs/sut/docker-events.log"),
               _fetch("started_at", "logs/sut/controller-started-at.txt", returncode=1, dest_exists=False)]
    _no_interval(tmp_path, "StartedAt", fetches=fetches)


@pytest.mark.parametrize("restart", [
    {"executed": True, "returncode": 1},
    {"executed": False, "returncode": None},
    None,
])
def test_a_restart_that_did_not_execute_with_0_gives_no_interval(tmp_path, restart) -> None:
    run_dir, manifest = _run_dir(tmp_path)
    manifest["restart"] = restart
    interval, why_not, _ = _pd().derive_proved_down(run_dir, manifest)
    assert interval is None and "restart" in why_not


def test_another_condition_gives_no_interval(tmp_path) -> None:
    _no_interval(tmp_path, "controller_restart", condition_id="nominal")


# --------------------------------------------------------------------------
# The derivation's bounds, each pinned (review of 2026-09-30, round 0: a
# one-sided or wider StartedAt tolerance, several dies with one start, a
# start at the die's instant, a read stamped in S's own second and a window
# one second wider than R7's all passed the cases above)
# --------------------------------------------------------------------------


def test_a_started_at_of_the_old_instance_long_before_the_start_gives_no_interval(tmp_path) -> None:
    """|S - StartedAt| <= 1 s holds on both sides: a compose restart keeps the container id, so the StartedAt of
    the instance that died - long before S - must not pass."""
    _no_interval(tmp_path, "1 s", started_at=_started_at(started_at="2026-10-01T09:00:00.000000000Z"))


@pytest.mark.parametrize("started, granted", [
    ("2026-10-01T10:01:07.300000001Z", False),
    ("2026-10-01T10:01:05.299999999Z", False),
    ("2026-10-01T10:01:07.300000000Z", True),
    ("2026-10-01T10:01:05.300000000Z", True),
])
def test_started_at_exactly_1_s_from_the_start_on_either_side_is_the_bound(tmp_path, started, granted) -> None:
    run_dir, manifest = _run_dir(tmp_path, started_at=_started_at(started_at=started))
    interval, why_not, _ = _pd().derive_proved_down(run_dir, manifest)
    assert (interval is not None) is granted, why_not


def test_two_dies_and_one_start_give_no_interval(tmp_path) -> None:
    events = _restart_events() + [_event("die", C, CID, _ns("10:00:40.0"), exitCode="137")]
    events.sort(key=lambda e: e["timeNano"])
    facts = _no_interval(tmp_path, "exactly one", events=events)
    assert facts["die_events_in_window"] == 2 and facts["start_events_in_window"] == 1


def test_a_start_at_the_instant_of_the_die_gives_no_interval(tmp_path) -> None:
    _no_interval(tmp_path, "not after the die", events=_restart_events(die="10:01:00.4", start="10:01:00.4"),
                 started_at=_started_at(started_at="2026-10-01T10:01:00.4Z"))


def test_a_started_at_read_stamped_in_the_starts_own_second_gives_no_interval(tmp_path) -> None:
    """guest_epoch is whole seconds: 10:01:06 may be before S = 10:01:06.3, so it is not a read at or after S."""
    _no_interval(tmp_path, "before the start", started_at=_started_at(guest_epoch=str(_epoch("10:01:06"))))


def test_a_start_at_t1_plus_1_is_outside_the_capture_window(tmp_path) -> None:
    """The window is R7's [t0, t1 + 1): a start at exactly t1 + 1 s is outside it."""
    facts = _no_interval(tmp_path, "exactly one", events=_restart_events(start="10:01:06.0"),
                         coverage=_coverage(until=str(_epoch("10:01:05"))),
                         started_at=_started_at(started_at="2026-10-01T10:01:06.0Z"))
    assert facts["die_events_in_window"] == 1 and facts["start_events_in_window"] == 0


def test_a_die_1_ns_before_t0_is_in_the_replay_not_the_capture_window(tmp_path) -> None:
    facts = _no_interval(tmp_path, "exactly one", events=_restart_events(die="10:01:00.999999999"),
                         coverage=_coverage(since=str(_epoch("10:01:01"))))
    assert facts["die_events_in_window"] == 0 and facts["start_events_in_window"] == 1


def test_a_die_at_t0_and_a_start_1_ns_before_t1_plus_1_are_inside_the_capture_window(tmp_path) -> None:
    run_dir, manifest = _run_dir(
        tmp_path,
        events=_restart_events(die="10:01:01.0", start="10:01:06.999999999"),
        coverage=_coverage(since=str(_epoch("10:01:01")), until=str(_epoch("10:01:06"))),
        started_at=_started_at(started_at="2026-10-01T10:01:06.999999999Z"),
    )
    interval, why_not, facts = _pd().derive_proved_down(run_dir, manifest)
    assert interval is not None, why_not
    assert facts["die_events_in_window"] == 1 and facts["start_events_in_window"] == 1


# --------------------------------------------------------------------------
# The restart transition rule (option A of the T6 page, qualified; adopted by
# the student on 2026-10-05, prospective, for the new G3 T6 run): rows of the
# restarted controller stamped in (sec(D), sec(S)], sec(S) > sec(D), never
# past sec(E), admitted only on the same container's unambiguous
# disappeared -> appeared pair in the collector's own lifecycle record, at the
# positions option A names. Fixture: the real bytes of controller_restart-r03
# (fixtures/t6_r03/SOURCE.txt), whose verdict and package stay as they are.
# --------------------------------------------------------------------------

R03 = Path(__file__).resolve().parent / "fixtures" / "t6_r03"
R03_CSV = "resources-controller_restart-r03.csv"
R03_LIFECYCLE = R03_CSV + ".lifecycle.csv"
R03_CID = "a7428fc55b5398475a3acc100231ff67acb36a7177f6c6966363299c513ff787"
R03_MONGODB_ID = "946354a51791cc292044484726377d14d88e744390da29921180911e6d296c0c"
R03_HOST = "egw-qemu-integrated"
R03_DIE_NS = 1791034634060050589
R03_START_NS = 1791034638761573789
R03_WINDOW = ("2026-10-03T13:36:56Z", "2026-10-03T13:37:34Z")
R03_SHA256 = {
    R03_CSV: "4ddd162c7df9cd1de424cfb227af69eff7bc30422dd0fc9c0774a52b1479134d",
    R03_LIFECYCLE: "2df607851737d162813146843851f191409cb1d17be0f42eb91b9930566a1ea0",
    "docker-events.coverage.txt": "c61b71470844fa548cd721486466aee4a26d854dc85e3b446aaa5c60803ad247",
    "controller-started-at.txt": "fec6a235c23a23d30c020d04de566e597ae9fec1a0b81395555100f9f1745fcc",
    "docker-events.jsonl": "974299292e2dd42ac3bf68a7f44389b8d1c8d99603044704946dcc4e8639a9c0",
}
#: What the run-time ingest said of the collector's file on 2026-10-03 (the manifest's warning, after its prefix).
R03_REJECTIONS = [
    "1 row(s) of container 'egw-controller-1' stamped between the die at 2026-10-03T13:37:14.060050589Z and the "
    "start at 2026-10-03T13:37:18.761573789Z, when no instance of it was running to measure (the proved-down "
    "interval, decision 1a): rejected whatever their values: 2026-10-03T13:37:17+00:00",
    "1 row(s) of container 'egw-controller-1' stamped in the second of the start at 2026-10-03T13:37:18.761573789Z, "
    "less than one sampling interval (RESOURCE_SAMPLE_INTERVAL_S, 1 s) after it: the first row after the "
    "proved-down interval (decision 1a) must be at least one sampling interval after the start's second: "
    "2026-10-03T13:37:18+00:00",
]
R03_ROW_17 = "2026-10-03T13:37:17Z,egw-controller-1,0.00,2703360,1.01,egw-qemu-integrated"
R03_ROWS = [
    {"line": 134, "ts_utc": "2026-10-03T13:37:17Z", "cpu_pct": "0.00", "mem_bytes": "2703360", "mem_pct": "1.01"},
    {"line": 140, "ts_utc": "2026-10-03T13:37:18Z", "cpu_pct": "16.06", "mem_bytes": "3588096", "mem_pct": "1.34"},
]
R03_INSTANTS = ["2026-10-03T13:37:17+00:00", "2026-10-03T13:37:18+00:00"]
R03_PAIR = ("2026-10-03T13:37:12Z,disappeared,", "2026-10-03T13:37:16Z,appeared,")


def _sha256(path: Path) -> str:
    import hashlib

    return hashlib.sha256(path.read_bytes()).hexdigest()


def _r03(tmp_path: Path, *, csv=None, lifecycle=None) -> Path:
    """The fixture's collector CSV and lifecycle record, copied into ``tmp_path``; ``csv`` and ``lifecycle`` map
    the original text to the text written (``lifecycle`` "absent" writes none)."""
    tmp_path.mkdir(parents=True, exist_ok=True)
    text = (R03 / R03_CSV).read_text(encoding="utf-8")
    (tmp_path / R03_CSV).write_text(csv(text) if csv else text, encoding="utf-8", newline="\n")
    life = (R03 / R03_LIFECYCLE).read_text(encoding="utf-8")
    if lifecycle != "absent":
        (tmp_path / R03_LIFECYCLE).write_text(lifecycle(life) if lifecycle else life, encoding="utf-8", newline="\n")
    return tmp_path / R03_CSV


def _r03_interval() -> resources.ProvedDownInterval:
    return resources.ProvedDownInterval(container=C, die_ns=R03_DIE_NS, start_ns=R03_START_NS)


def _r03_witness(csv_path: Path, container_id: str = R03_CID):
    return _pd().read_lifecycle_witness(Path(f"{csv_path}.lifecycle.csv"), container_id)


def _r03_validate(csv_path: Path, **kwargs) -> list[str]:
    start, end = R03_WINDOW
    return resources.validate_resources_csv(
        csv_path,
        expected_host=R03_HOST,
        expected_window_s=38.0,
        expected_window_start_utc=start,
        expected_window_end_utc=end,
        proved_down=_r03_interval(),
        **kwargs,
    )


def _without(*seconds_and_names: tuple[str, str]):
    """A csv edit dropping the rows of (HH:MM:SS, container)."""
    def edit(text: str) -> str:
        drop = {f"2026-10-03T{second}Z,{name}," for second, name in seconds_and_names}
        return "".join(line for line in text.splitlines(keepends=True) if not any(line.startswith(d) for d in drop))
    return edit


def test_the_r03_fixture_is_the_sealed_runs_bytes() -> None:
    assert {name: _sha256(R03 / name) for name in R03_SHA256} == R03_SHA256
    assert _pd().LIFECYCLE_SUFFIX == ".lifecycle.csv" and _pd().LIFECYCLE_HEADER == "ts_utc,event,container_id,name"
    assert resources.TRANSITION_RULE == "1a-option-a-2026-10-05"


def test_the_r03_capture_and_started_at_give_the_interval_the_run_recorded(tmp_path) -> None:
    run_dir = tmp_path / "raw" / "controller_restart-r03"
    (run_dir / "logs" / "sut").mkdir(parents=True)
    for name, source in (("docker-events.log", "docker-events.jsonl"),
                         ("docker-events.coverage.txt", "docker-events.coverage.txt"),
                         ("controller-started-at.txt", "controller-started-at.txt")):
        (run_dir / "logs" / "sut" / name).write_bytes((R03 / source).read_bytes())
    manifest = {
        "condition_id": "controller_restart",
        "restart": {"executed": True, "returncode": 0},
        "sut_log_fetches": [_fetch("docker_events", "logs/sut/docker-events.log"),
                            _fetch("started_at", "logs/sut/controller-started-at.txt")],
    }
    interval, why_not, facts = _pd().derive_proved_down(run_dir, manifest)
    assert why_not is None and interval == _r03_interval()
    assert facts["container_id"] == R03_CID and facts["started_at"] == "2026-10-03T13:37:18.698631325Z"
    assert facts["die_utc"] == "2026-10-03T13:37:14.060050589Z" and facts["start_utc"] == "2026-10-03T13:37:18.761573789Z"
    assert facts["start_minus_started_at_s"] == pytest.approx(0.062942464) and facts["capped"] is False


def test_r03_without_the_transition_rule_is_rejected_exactly_as_on_2026_10_03(tmp_path) -> None:
    """Behaviour without activation: no witness, the two rows rejected in the words of the run's warning; without
    the interval, the ordinary 5 s rule (13:37:11 to 13:37:17)."""
    path = _r03(tmp_path)
    outcome: dict = {}
    assert _r03_validate(path, proved_down_outcome=outcome) == R03_REJECTIONS
    assert _r03_validate(path, transition_witness=None) == R03_REJECTIONS
    assert outcome["rejected_rows"] == R03_INSTANTS
    assert (outcome["edge_gap_before_s"], outcome["edge_gap_after_s"]) == (3.0, 1.0)
    assert "transition" not in " ".join(outcome)
    start, end = R03_WINDOW
    assert resources.validate_resources_csv(
        path, expected_host=R03_HOST, expected_window_s=38.0, expected_window_start_utc=start,
        expected_window_end_utc=end,
    ) == [
        "1 sampling gap(s) exceed the protocol maximum of 5 s (MAX_SAMPLE_GAP_S): container 'egw-controller-1': "
        "2026-10-03T13:37:11+00:00 to 2026-10-03T13:37:17+00:00 (6.0 s)"
    ]


def test_r03_transition_rows_are_admitted_on_the_lifecycle_pair_and_reported_separately(tmp_path) -> None:
    """A1: the real lifecycle record holds egw-controller-1's id disappeared at 13:37:12Z and appeared at 13:37:16Z,
    after the last row at or before sec(D) (13:37:11) and at or before the first transition row (13:37:17): both
    rows are transition rows, the file passes, and every 1a figure but the rejection is unchanged."""
    path = _r03(tmp_path)
    witness = _r03_witness(path)
    assert witness.problem is None and witness.container_id == R03_CID
    assert [(r.stamp.isoformat(), r.event) for r in witness.records] == [
        ("2026-10-03T13:32:11+00:00", "appeared"),
        ("2026-10-03T13:37:12+00:00", "disappeared"),
        ("2026-10-03T13:37:16+00:00", "appeared"),
    ]
    pd_outcome: dict = {}
    t_outcome: dict = {}
    assert _r03_validate(path, proved_down_outcome=pd_outcome, transition_witness=witness,
                         transition_outcome=t_outcome) == []
    assert t_outcome == {
        "rule": "1a-option-a-2026-10-05",
        "container": C,
        "container_id": R03_CID,
        "admitted": True,
        "why_not": None,
        "after_second_utc": "2026-10-03T13:37:14+00:00",
        "through_second_utc": "2026-10-03T13:37:18+00:00",
        "instants": R03_INSTANTS,
        "count": 2,
        "rows": R03_ROWS,
        "disappeared_utc": "2026-10-03T13:37:12+00:00",
        "appeared_utc": "2026-10-03T13:37:16+00:00",
    }
    assert pd_outcome["applies"] is True and pd_outcome["rejected_rows"] == []
    assert pd_outcome["rows_between"] == R03_INSTANTS[:1] and pd_outcome["rows_in_start_second"] == R03_INSTANTS[1:]
    assert (pd_outcome["edge_gap_before_s"], pd_outcome["edge_gap_after_s"]) == (3.0, 1.0)
    assert pd_outcome["last_row_before_die"] == "2026-10-03T13:37:11+00:00"
    assert pd_outcome["first_row_after_start"] == "2026-10-03T13:37:19+00:00"
    assert (R03 / R03_CSV).read_bytes() == path.read_bytes(), "the file is read, never changed"


def test_r03_observed_zero_variant_is_admitted_and_its_zeros_are_reported(tmp_path) -> None:
    """A zero actually measured is kept and counts like any reading: the 13:37:17 row as 0.00,0,0.00."""
    path = _r03(tmp_path, csv=lambda t: t.replace(R03_ROW_17, R03_ROW_17.replace("0.00,2703360,1.01", "0.00,0,0.00")))
    t_outcome: dict = {}
    assert _r03_validate(path, transition_witness=_r03_witness(path), transition_outcome=t_outcome) == []
    assert t_outcome["admitted"] is True
    assert t_outcome["rows"][0] == {"line": 134, "ts_utc": "2026-10-03T13:37:17Z", "cpu_pct": "0.00",
                                    "mem_bytes": "0", "mem_pct": "0.00"}


def test_zero_valued_transition_rows_without_the_pair_are_rejected_whatever_their_values(tmp_path) -> None:
    """A4/U7 kept: a zero alone proves nothing; without the lifecycle pair the rows are rejected as before."""
    path = _r03(
        tmp_path,
        csv=lambda t: t.replace(R03_ROW_17, R03_ROW_17.replace("0.00,2703360,1.01", "0.00,0,0.00")),
        lifecycle=lambda t: "".join(line for line in t.splitlines(keepends=True) if not line.startswith(R03_PAIR)),
    )
    t_outcome: dict = {}
    assert _r03_validate(path, transition_witness=_r03_witness(path), transition_outcome=t_outcome) == R03_REJECTIONS
    assert t_outcome["admitted"] is False and "not exactly one 'disappeared' then one 'appeared'" in t_outcome["why_not"]
    assert t_outcome["instants"] == R03_INSTANTS and t_outcome["count"] == 2


def _swap_pair_ids(text: str, cid: str, name: str | None = None) -> str:
    out = []
    for line in text.splitlines(keepends=True):
        if line.startswith(R03_PAIR):
            line = line.replace(R03_CID, cid)
            if name is not None:
                line = line.replace("egw-controller-1", name)
        out.append(line)
    return "".join(out)


@pytest.mark.parametrize("lifecycle, words", [
    pytest.param("absent", "could not be read", id="absent"),
    pytest.param(lambda t: "".join(x for x in t.splitlines(keepends=True) if not x.startswith(R03_PAIR[1])),
                 "is ['disappeared']", id="no-appeared"),
    pytest.param(lambda t: _swap_pair_ids(t, R03_MONGODB_ID, "egw-mongodb-1"), "is empty", id="wrong-container"),
    pytest.param(lambda t: _swap_pair_ids(t, "4e" * 32), "under another container id", id="name-of-another-id"),
    pytest.param(lambda t: _swap_pair_ids(t, R03_CID, "egw-mongodb-1"), "names it", id="id-of-another-name"),
    pytest.param(lambda t: t.replace(R03_PAIR[1], "2026-10-03T13:37:17Z,appeared,"), "late or inconsistent",
                 id="appeared-in-the-first-transition-rows-second"),
    pytest.param(lambda t: t.replace(R03_PAIR[1], "2026-10-03T13:37:19Z,appeared,"), "late", id="tardy-in-sec-S+1"),
    pytest.param(lambda t: t.replace(R03_PAIR[1], "2026-10-03T13:37:20Z,appeared,"), "is ['disappeared']",
                 id="tardy-after-the-first-row-after"),
    pytest.param(lambda t: t.replace(R03_PAIR[0], "2026-10-03T13:37:11Z,disappeared,"), "is ['appeared']",
                 id="disappeared-with-the-last-row-before"),
    pytest.param(lambda t: t.replace(R03_PAIR[0], "2026-10-03T13:37:12Z,appeared,")
                 .replace(R03_PAIR[1], "2026-10-03T13:37:16Z,disappeared,"), "is ['appeared', 'disappeared']",
                 id="reversed"),
    pytest.param(lambda t: t + f"2026-10-03T13:37:18Z,counter_reset,{R03_CID},egw-controller-1\n",
                 "is ['disappeared', 'appeared', 'counter_reset']", id="extra-event"),
    pytest.param(lambda t: t + f"2026-10-03T13:37:17Z,disappeared,{R03_CID},egw-controller-1\n"
                 f"2026-10-03T13:37:18Z,appeared,{R03_CID},egw-controller-1\n",
                 "is ['disappeared', 'appeared', 'disappeared', 'appeared']", id="two-pairs"),
    pytest.param(lambda t: t.replace("ts_utc,event,container_id,name", "ts_utc,event,id,name"), "header",
                 id="unreadable-header"),
    pytest.param(lambda t: t + "2026-10-03T13:40:00Z,appeared,ab\n", "not a lifecycle row", id="unreadable-row"),
    pytest.param(lambda t: t.replace(R03_PAIR[1], "2026-10-03T13:37:16.5Z,appeared,"), "not a lifecycle row",
                 id="unreadable-stamp"),
    pytest.param(lambda t: t.replace(R03_PAIR[1], "2026-10-03T13:37:16Z,started,"), "not a lifecycle row",
                 id="unreadable-event"),
    pytest.param(lambda t: t.replace(R03_PAIR[0], "2026-10-03T13:37:17Z,disappeared,"), "goes back in time",
                 id="out-of-order"),
    pytest.param(lambda t: t.replace("\n2026-10-03T13:37:12Z", "\n\n2026-10-03T13:37:12Z"), "not a lifecycle row",
                 id="empty-line"),
])
def test_a_missing_wrong_late_inconsistent_or_unreadable_witness_grants_nothing(tmp_path, lifecycle, words) -> None:
    path = _r03(tmp_path, lifecycle=lifecycle)
    t_outcome: dict = {}
    pd_outcome: dict = {}
    assert _r03_validate(path, proved_down_outcome=pd_outcome, transition_witness=_r03_witness(path),
                         transition_outcome=t_outcome) == R03_REJECTIONS
    assert t_outcome["admitted"] is False and words in t_outcome["why_not"], t_outcome["why_not"]
    assert t_outcome["instants"] == R03_INSTANTS and t_outcome["rows"] == R03_ROWS
    assert pd_outcome["rejected_rows"] == R03_INSTANTS


def test_a_lifecycle_record_that_is_not_utf_8_grants_nothing(tmp_path) -> None:
    path = _r03(tmp_path)
    life = Path(f"{path}.lifecycle.csv")
    life.write_bytes(life.read_bytes().replace(b"egw-mongodb-1", b"egw-mongodb-\xff"))
    witness = _r03_witness(path)
    assert witness.problem and "UTF-8" in witness.problem and witness.records == ()
    assert _r03_validate(path, transition_witness=witness) == R03_REJECTIONS


def test_a_witness_without_the_pairs_container_id_grants_nothing(tmp_path) -> None:
    path = _r03(tmp_path)
    for cid in (None, "", "A7" + R03_CID[2:]):
        witness = _r03_witness(path, cid)
        assert witness.problem and "container id" in witness.problem
        assert _r03_validate(path, transition_witness=witness) == R03_REJECTIONS


def _witness(*records: tuple[str, str], cid: str = CID, name: str = C):
    """A lifecycle witness of fixture F's container: (HH:MM:SS of DAY, event) rows."""
    return resources.LifecycleWitness(
        container=C,
        container_id=cid,
        records=tuple(resources.LifecycleRecord(_second(at), event, cid, name) for at, event in records),
    )


def test_a_die_and_a_start_in_one_second_keep_that_seconds_row_rejected_whatever_the_witness(tmp_path) -> None:
    """A8: sec(D) = sec(S) - no row is a transition row (sec(S) > sec(D) is required); the conservative case."""
    path = _csv(tmp_path / "f.csv", absent={})
    t_outcome: dict = {}
    problems = _validate(path, proved_down=_interval("10:01:00.2", "10:01:00.7"),
                         transition_witness=_witness(("10:00:59", "disappeared"), ("10:01:00", "appeared")),
                         transition_outcome=t_outcome)
    assert problems and any("less than one sampling interval" in p for p in problems)
    assert t_outcome["admitted"] is False and t_outcome["instants"] == []
    assert "one whole second" in t_outcome["why_not"]


def test_a_capped_restart_admits_transition_rows_up_to_sec_e_and_never_beyond(tmp_path) -> None:
    """A7: capped, D = 10:01:00.4, S = 10:03:02.4, E = D + 120 s = 10:03:00.4. The row at 10:01:30 lies in
    (sec(D), sec(E)] and is admitted on the pair; the row at 10:03:01, after sec(E) and before sec(S), is still
    rejected (the pinned 10:03:01 case), and so is a row in sec(S)."""
    witness = _witness(("10:01:01", "disappeared"), ("10:01:29", "appeared"))
    interval = _interval("10:01:00.4", "10:03:02.4")
    holes = [("10:01:01", "10:01:29"), ("10:01:31", "10:03:00"), ("10:03:02", "10:03:02")]
    path = _csv(tmp_path / "f.csv", end="10:05:00", absent={C: holes})
    t_outcome: dict = {}
    pd_outcome: dict = {}
    problems = _validate(path, end="10:05:00", proved_down=interval, proved_down_outcome=pd_outcome,
                         transition_witness=witness, transition_outcome=t_outcome)
    assert t_outcome["admitted"] is True and t_outcome["instants"] == ["2026-10-01T10:01:30+00:00"]
    assert t_outcome["through_second_utc"] == "2026-10-01T10:03:00+00:00"
    assert pd_outcome["rejected_rows"] == ["2026-10-01T10:03:01+00:00"] and pd_outcome["edge_gap_after_s"] == 3.0
    assert len(problems) == 1 and "stamped between the die" in problems[0], problems
    assert problems[0].endswith(": 2026-10-01T10:03:01+00:00"), problems
    path = _csv(tmp_path / "g.csv", end="10:05:00", absent={C: [("10:01:01", "10:01:29"), ("10:01:31", "10:03:01")]})
    problems = _validate(path, end="10:05:00", proved_down=interval, transition_witness=witness)
    assert len(problems) == 1 and "in the second of the start" in problems[0], problems
    path = _csv(tmp_path / "h.csv", end="10:05:00", absent={C: [("10:01:01", "10:01:29"), ("10:01:31", "10:03:02")]})
    assert _validate(path, end="10:05:00", proved_down=interval, transition_witness=witness) == []


def test_a_transition_row_neither_opens_nor_closes_an_edge(tmp_path) -> None:
    """The r03 rows with the controller's 13:37:19 to 13:37:24 rows removed: the transition rows (13:37:17,
    13:37:18) are admitted, but the edge after runs from sec(E) to the first row after sec(S) + 1 s (13:37:25):
    7.0 s, rejected. Likewise the edge before, from the last row at or before sec(D)."""
    after = [(f"13:37:{s}", C) for s in range(19, 25)]
    path = _r03(tmp_path / "after", csv=_without(*after))
    t_outcome: dict = {}
    problems = _r03_validate(path, transition_witness=_r03_witness(path), transition_outcome=t_outcome)
    assert t_outcome["admitted"] is True
    assert problems == [
        "1 sampling gap(s) exceed the protocol maximum of 5 s (MAX_SAMPLE_GAP_S): container 'egw-controller-1': "
        "the effective end's second 2026-10-03T13:37:18+00:00 to 2026-10-03T13:37:25+00:00 (edge after the "
        "proved-down interval, decision 1a) (7.0 s)"
    ]
    before = [(f"13:37:{s:02d}", C) for s in range(7, 12)]
    path = _r03(tmp_path / "before", csv=_without(*before))
    problems = _r03_validate(path, transition_witness=_r03_witness(path))
    assert problems == [
        "1 sampling gap(s) exceed the protocol maximum of 5 s (MAX_SAMPLE_GAP_S): container 'egw-controller-1': "
        "2026-10-03T13:37:06+00:00 to the die's second 2026-10-03T13:37:14+00:00 (edge before the proved-down "
        "interval, decision 1a) (8.0 s)"
    ]


def test_another_services_check_still_fails_with_the_transition_rows_admitted(tmp_path) -> None:
    path = _r03(tmp_path, csv=_without(*[(f"13:37:{s}", "egw-mosquitto-1") for s in range(10, 17)]))
    t_outcome: dict = {}
    problems = _r03_validate(path, transition_witness=_r03_witness(path), transition_outcome=t_outcome)
    assert t_outcome["admitted"] is True
    assert problems == [
        "1 sampling gap(s) exceed the protocol maximum of 5 s (MAX_SAMPLE_GAP_S): container 'egw-mosquitto-1': "
        "2026-10-03T13:37:09+00:00 to 2026-10-03T13:37:17+00:00 (8.0 s)"
    ]


def test_another_numeric_check_still_fails_on_an_admitted_transition_row(tmp_path) -> None:
    path = _r03(tmp_path, csv=lambda t: t.replace(R03_ROW_17, R03_ROW_17.replace("0.00,2703360", "0.00,nan")))
    t_outcome: dict = {}
    problems = _r03_validate(path, transition_witness=_r03_witness(path), transition_outcome=t_outcome)
    assert t_outcome["admitted"] is True
    assert problems == ["1 row(s) with a non-finite mem_bytes value (nan/inf are not measurements): line 134: 'nan'"]


@pytest.mark.parametrize("last, expected", [
    ("10:00:33", []),
    ("10:00:32", ["container 'egw-controller-1' has only 29 distinct sample instant(s); at least 30 are required "
                  "per container"]),
])
def test_admitted_transition_rows_count_for_the_per_container_distinct_instants(tmp_path, last, expected) -> None:
    """Distinct instants, not rows: the controller has 15 rows before its die (10:00:00-14), two transition rows
    (10:00:18, 10:00:19) and 13 or 12 after its start (10:00:21-33 or -32): 30 counts the minimum met, 29 not."""
    absent = {C: [("10:00:15", "10:00:17"), ("10:00:20", "10:00:20")]}
    if last != "10:00:33":
        absent[C].append(("10:00:33", "10:00:33"))
    path = _csv(tmp_path / "f.csv", end="10:00:33", absent=absent)
    t_outcome: dict = {}
    problems = _validate(path, end="10:00:33", proved_down=_interval("10:00:15.5", "10:00:19.6"),
                         transition_witness=_witness(("10:00:15", "disappeared"), ("10:00:17", "appeared")),
                         transition_outcome=t_outcome)
    assert t_outcome["admitted"] is True
    assert t_outcome["instants"] == ["2026-10-01T10:00:18+00:00", "2026-10-01T10:00:19+00:00"]
    assert problems == expected


@pytest.mark.parametrize("absent", [
    {C: ("10:01:01", "10:01:07")},
    {C: ("10:01:01", "10:01:05")},
    {C: ("10:00:55", "10:01:07"), "egw-mosquitto-1": ("10:01:01", "10:01:09")},
    {},
])
def test_without_a_witness_an_explicit_none_gives_exactly_what_the_default_gives(tmp_path, absent) -> None:
    path = _csv(tmp_path / "f.csv", absent=absent, extra=(("10:01:03", C, "0.0,0,0.0"),))
    plain: dict = {}
    given: dict = {}
    assert _validate(path, proved_down=_interval(), proved_down_outcome=plain) == _validate(
        path, proved_down=_interval(), proved_down_outcome=given, transition_witness=None
    )
    assert plain == given


def test_a_witness_without_the_interval_changes_nothing(tmp_path) -> None:
    path = _csv(tmp_path / "f.csv")
    t_outcome: dict = {}
    assert _validate(path, transition_witness=_witness(("10:01:01", "disappeared"), ("10:01:05", "appeared")),
                     transition_outcome=t_outcome) == [U0_PROBLEM]
    assert t_outcome == {}


def _r03_analysis(tmp_path: Path, csv_path: Path) -> dict:
    """analyze.py, unchanged, on a sealed run directory holding the file as its resources.csv and the fixture's
    measured window."""
    from egw_experiments import analyze
    from egw_experiments.checksums import write_sha256sums

    run_dir = tmp_path / "raw" / "controller_restart-r03"
    run_dir.mkdir(parents=True)
    start, end = R03_WINDOW
    (run_dir / "manifest.json").write_text(json.dumps({
        "run_id": "controller_restart-r03", "condition_id": "controller_restart", "scenario": "nominal",
        "measured_window_utc": {"start": start, "end": end}, "exclusion": None,
    }) + "\n", encoding="utf-8")
    (run_dir / "sent_events.jsonl").write_text("", encoding="utf-8")
    (run_dir / "events.jsonl").write_text("", encoding="utf-8")
    (run_dir / "resources.csv").write_bytes(csv_path.read_bytes())
    write_sha256sums(run_dir)
    return analyze.compute_run_metrics(run_dir)


def _controller(row: dict) -> dict:
    return next(r for r in row["_resources"] if r["container"] == C)


def test_admitted_transition_rows_enter_the_existing_coverage_and_aggregates_unchanged_in_form(tmp_path) -> None:
    """The file the rule admits is ingested byte for byte, so analyze.py's existing calculations read it as they
    read any file. Over the window 13:36:56-13:37:34 (38 s) the controller has 34 rows, 13:37:17 and 13:37:18
    among them: CPU mean 1999.43/34 %, memory mean 1,468,608,512/34 = 43,194,368 B; the capped per-sample coverage
    covers 15 + min(6, 5) + 1 + 1 + 15 = 37 s of 38. The denominators and formulas are analyze.py's own: the
    distinct instants of the whole file stay 39 (every other container sampled each second), and the 6.0 s from
    13:37:11 to the first transition row is still an interior gap above MAX_SAMPLE_GAP_S, so analyze.py's own
    per-container sufficiency stays False for the controller (as it would at 8.0 s without the transition rows)."""
    path = _r03(tmp_path / "in")
    assert _r03_validate(path, transition_witness=_r03_witness(path)) == []
    row = _r03_analysis(tmp_path / "a", path)
    ctl = _controller(row)
    assert ctl["samples"] == 34
    assert ctl["cpu_pct_mean"] == pytest.approx(1999.43 / 34)
    assert ctl["mem_bytes_mean"] == pytest.approx(43194368.0)
    assert ctl["cpu_pct_max"] == pytest.approx(103.12) and ctl["mem_bytes_max"] == 69947392
    assert ctl["coverage_pct"] == pytest.approx(100.0 * 37 / 38)
    assert ctl["max_gap_s"] == 6.0 and ctl["coverage_sufficient"] is False
    assert row["resources_distinct_instants"] == 39
    # The same file without the two rows, for contrast only (it is not what the rule ingests).
    bare = _r03(tmp_path / "bare", csv=_without(("13:37:17", C), ("13:37:18", C)))
    other = _controller(_r03_analysis(tmp_path / "b", bare))
    assert other["samples"] == 32 and other["mem_bytes_mean"] == pytest.approx(45697408.0)
    assert other["coverage_pct"] == pytest.approx(100.0 * 35 / 38) and other["max_gap_s"] == 8.0


def test_the_observed_zero_variant_enters_the_aggregates_with_its_zeros(tmp_path) -> None:
    path = _r03(tmp_path / "in", csv=lambda t: t.replace(R03_ROW_17, R03_ROW_17.replace("0.00,2703360,1.01",
                                                                                         "0.00,0,0.00")))
    assert _r03_validate(path, transition_witness=_r03_witness(path)) == []
    ctl = _controller(_r03_analysis(tmp_path / "a", path))
    assert ctl["samples"] == 34
    assert ctl["mem_bytes_mean"] == pytest.approx((1468608512 - 2703360) / 34)
    assert ctl["cpu_pct_mean"] == pytest.approx(1999.43 / 34)
