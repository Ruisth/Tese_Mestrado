"""The finite proof's failed-poll retry in the controller /metrics sampler
(egw_experiments.controller_metrics; PM brief of 2026-09-26 on PR #48 and r02,
section 3). The scheduling rule is tested on its own with explicit instants,
then the sampler's thread with a stub fetch: serial requests, the 50 ms wait
after a completed failure, the normal cadence after a success, the 60 s cap,
the stop event, and the unchanged default.
"""
from __future__ import annotations

import csv
import threading
import time
import urllib.error
from pathlib import Path

import pytest

from egw_experiments import controller_metrics as cm

URL = "http://127.0.0.1:8000"
SNAPSHOT = {"accepted": 1, "rejected": 0, "duplicate": 0, "failed": 0, "dropped": 0, "queue_depth": 0,
            "received": 1, "in_progress": 0, "processing_errors": 0, "unacked": 0, "mqtt_connection": 1,
            "mqtt_subscribed": True, "started_at": "2026-09-26T21:23:00Z", "wall_utc": "2026-09-26T21:23:01Z",
            "uptime_s": 1.0, "monotonic_ns": 1_000_000_000}


def _sampler(tmp_path: Path, **kwargs) -> cm.ControllerMetricsSampler:
    return cm.ControllerMetricsSampler(tmp_path / "controller_metrics.csv", URL, interval_s=1.0, **kwargs)


def _attempts(path: Path) -> list[dict[str, str]]:
    with open(path, encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


# --- the scheduling rule ----------------------------------------------------------


def test_the_default_sampler_keeps_the_rest_of_the_second_after_a_failed_poll(tmp_path: Path) -> None:
    s = _sampler(tmp_path)
    assert s.fast_retry_s is None
    assert s._next_wait(False, 10.0, 10.2) == pytest.approx(0.8)
    assert s._next_wait(False, 10.0, 15.0) == 0.0           # a timed-out poll: the next one at once, as before
    assert s._next_wait(True, 11.0, 11.1) == pytest.approx(0.9)
    assert (s.fast_retries, s.failure_episodes, s.cap_reached) == (0, 0, 0)


def test_fast_retry_waits_50_ms_after_a_completed_failure_and_the_rest_of_the_second_after_a_success(tmp_path: Path) -> None:
    s = _sampler(tmp_path, fast_retry_s=cm.FAST_RETRY_S)
    assert s._next_wait(False, 0.0, 0.001) == cm.FAST_RETRY_S == 0.05
    assert s._next_wait(False, 0.051, 0.052) == 0.05
    assert s._next_wait(True, 0.102, 0.152) == pytest.approx(0.95)   # success: the normal cadence again
    assert (s.fast_retries, s.failure_episodes) == (2, 1)


def test_a_slow_failed_request_is_followed_after_50_ms_never_at_once(tmp_path: Path) -> None:
    """A failure that took the whole five-second request timeout: the wait is
    still 50 ms (no busy loop, no overlap: the next request starts after it)."""
    s = _sampler(tmp_path, fast_retry_s=cm.FAST_RETRY_S)
    assert s._next_wait(False, 0.0, 5.0) == 0.05


def test_the_cap_ends_fast_retry_after_60_s_of_one_episode_and_a_success_starts_a_new_one(tmp_path: Path) -> None:
    s = _sampler(tmp_path, fast_retry_s=cm.FAST_RETRY_S)
    t, waits = 0.0, []
    while t < 61.0:                                         # failures, each taking 1 ms
        waits.append(s._next_wait(False, t, t + 0.001))
        t += 0.001 + waits[-1]
    assert set(waits[:-2]) == {0.05}                        # fast within the first 60 s of the episode
    assert waits[-1] == pytest.approx(0.999)                # then the normal cadence
    assert s.cap_reached == 1 and s.failure_episodes == 1
    before = s.fast_retries
    assert s._next_wait(False, t, t + 0.001) == pytest.approx(0.999)
    assert s.cap_reached == 1 and s.fast_retries == before  # counted once per episode
    assert s._next_wait(True, t + 1, t + 1.01) == pytest.approx(0.99)
    assert s._next_wait(False, t + 2, t + 2.001) == 0.05    # a new episode is fast again
    assert s.failure_episodes == 2


@pytest.mark.parametrize("kwargs", [{"fast_retry_s": 0.0}, {"fast_retry_s": 1.0}, {"fast_retry_s": -0.05},
                                    {"fast_retry_s": 0.05, "fast_retry_cap_s": 0.0}])
def test_settings_outside_their_range_are_refused(tmp_path: Path, kwargs: dict) -> None:
    with pytest.raises(ValueError):
        _sampler(tmp_path, **kwargs)


# --- the sampler's thread, with a stub fetch ----------------------------------------


class _Fetch:
    """A stub GET /metrics: fails the first `failures` calls (after `delay_s`),
    then answers; records every call's host instants and the peak number of
    calls in flight at once."""

    def __init__(self, failures: int, delay_s: float = 0.0, fail_always: bool = False) -> None:
        self.failures, self.delay_s, self.fail_always = failures, delay_s, fail_always
        self.calls: list[tuple[float, float]] = []
        self.in_flight = self.peak = 0
        self._lock = threading.Lock()

    def __call__(self, url: str, timeout_s: float = 5.0) -> dict:
        with self._lock:
            self.in_flight += 1
            self.peak = max(self.peak, self.in_flight)
            n = len(self.calls)
        start = time.monotonic()
        try:
            if self.delay_s:
                time.sleep(self.delay_s)
            if self.fail_always or n < self.failures:
                raise urllib.error.URLError("connection refused")
            return dict(SNAPSHOT)
        finally:
            with self._lock:
                self.calls.append((start, time.monotonic()))
                self.in_flight -= 1


def test_failed_polls_are_retried_every_50_ms_serially_then_the_normal_cadence_resumes(tmp_path: Path, monkeypatch) -> None:
    fetch = _Fetch(failures=5)
    monkeypatch.setattr(cm, "fetch_metrics", fetch)
    log = tmp_path / "controller_metrics.attempts.csv"
    with cm.ControllerMetricsSampler(tmp_path / "m.csv", URL, interval_s=0.5, fast_retry_s=0.05, attempts_path=log) as s:
        time.sleep(1.2)
    rows = _attempts(log)
    assert [r["outcome"] for r in rows[:6]] == ["error"] * 5 + ["ok"]
    assert [r["next_wait_s"] for r in rows[:5]] == ["0.050"] * 5
    assert 0.4 < float(rows[5]["next_wait_s"]) <= 0.5
    assert fetch.peak == 1                                  # never two requests at once
    for prev, nxt in zip(rows, rows[1:]):                   # each starts after the previous one ended and its wait
        gap = float(nxt["started_monotonic_s"]) - float(prev["finished_monotonic_s"])
        assert gap >= float(prev["next_wait_s"]) - 0.005, (prev, nxt)
    assert s.samples_written == sum(r["outcome"] == "ok" for r in rows)
    assert (s.fast_retries, s.failure_episodes, s.cap_reached, s.poll_errors) == (5, 1, 0, 5)
    assert rows[0]["error"] == "<urlopen error connection refused>"


def test_a_blocked_request_is_never_overlapped_and_is_followed_after_50_ms(tmp_path: Path, monkeypatch) -> None:
    fetch = _Fetch(failures=0, delay_s=0.3, fail_always=True)
    monkeypatch.setattr(cm, "fetch_metrics", fetch)
    log = tmp_path / "attempts.csv"
    with cm.ControllerMetricsSampler(tmp_path / "m.csv", URL, interval_s=1.0, fast_retry_s=0.05, attempts_path=log):
        time.sleep(1.0)
    assert fetch.peak == 1
    calls = sorted(fetch.calls)
    for (_, end), (start, _) in zip(calls, calls[1:]):
        assert start - end >= 0.045, calls
    assert all(r["next_wait_s"] == "0.050" for r in _attempts(log))


def test_the_stop_event_cancels_a_fast_retry_at_once(tmp_path: Path, monkeypatch) -> None:
    fetch = _Fetch(failures=0, fail_always=True)
    monkeypatch.setattr(cm, "fetch_metrics", fetch)
    s = cm.ControllerMetricsSampler(tmp_path / "m.csv", URL, interval_s=1.0, fast_retry_s=0.05,
                                    attempts_path=tmp_path / "a.csv")
    s.__enter__()
    time.sleep(0.3)
    started = time.monotonic()
    s.__exit__(None, None, None)
    assert time.monotonic() - started < 0.5
    calls = len(fetch.calls)
    time.sleep(0.2)
    assert len(fetch.calls) == calls                        # nothing polls after the stop
    assert s.fast_retries >= 3


def test_the_cap_holds_in_the_running_thread(tmp_path: Path, monkeypatch) -> None:
    """A cap of 0.3 s stands in for the 60 s one: after it the failures of the
    same episode are polled at the normal cadence."""
    fetch = _Fetch(failures=0, fail_always=True)
    monkeypatch.setattr(cm, "fetch_metrics", fetch)
    log = tmp_path / "a.csv"
    with cm.ControllerMetricsSampler(tmp_path / "m.csv", URL, interval_s=0.5, fast_retry_s=0.05,
                                     fast_retry_cap_s=0.3, attempts_path=log) as s:
        time.sleep(1.4)
    waits = [float(r["next_wait_s"]) for r in _attempts(log)]
    first_normal = next(i for i, w in enumerate(waits) if w > 0.05)
    assert all(w == 0.05 for w in waits[:first_normal]) and all(w > 0.4 for w in waits[first_normal:])
    assert s.cap_reached == 1 and s.failure_episodes == 1


def test_the_default_sampler_writes_no_attempts_log_and_never_retries_fast(tmp_path: Path, monkeypatch) -> None:
    fetch = _Fetch(failures=0, fail_always=True)
    monkeypatch.setattr(cm, "fetch_metrics", fetch)
    with cm.ControllerMetricsSampler(tmp_path / "m.csv", URL, interval_s=0.3) as s:
        time.sleep(0.5)
    assert s.fast_retry_s is None and s.attempts_path is None
    assert (s.fast_retries, s.failure_episodes) == (0, 0)
    assert not list(tmp_path.glob("*attempts*"))
    calls = sorted(fetch.calls)
    # the entry poll and the thread's first poll back to back, then one every 0.3 s
    assert len(calls) <= 4
