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
