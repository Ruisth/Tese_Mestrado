"""The finite proof's failed-poll retry in the controller /metrics sampler
(egw_experiments.controller_metrics; PM brief of 2026-09-26 on PR #48 and r02,
section 3). The scheduling rule is tested on its own with explicit instants,
then the sampler's thread with a stub fetch: serial requests, the 50 ms wait
after a completed failure, the normal cadence after a success, the 60 s cap,
the stop event, and the unchanged default.
"""
from __future__ import annotations

import csv
import http.client
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


@pytest.mark.parametrize("fail_always", [True, False], ids=["retry-wait", "first-wait"])
def test_the_stop_event_cancels_every_wait_at_once(tmp_path: Path, monkeypatch, fail_always: bool) -> None:
    """Long waits, so that only the stop event can end them within a second:
    a retry wait of 5 s after failed polls, and the 10 s the thread keeps
    after a successful entry poll."""
    fetch = _Fetch(failures=0, fail_always=fail_always)
    monkeypatch.setattr(cm, "fetch_metrics", fetch)
    s = cm.ControllerMetricsSampler(tmp_path / "m.csv", URL, interval_s=10.0, fast_retry_s=5.0,
                                    attempts_path=tmp_path / "a.csv")
    s.__enter__()
    time.sleep(0.3)
    calls = len(fetch.calls)
    started = time.monotonic()
    s.__exit__(None, None, None)
    assert time.monotonic() - started < 1.0
    time.sleep(0.2)
    assert len(fetch.calls) == calls                        # nothing polls after the stop
    if fail_always:
        assert s.fast_retries >= 1 and calls == 1           # the entry poll, then a 5 s retry wait
    else:
        assert s._first_wait > 9.0 and calls == 1           # the entry poll, then the kept first wait


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
    assert s.fast_retry_s is None and s.attempts_path is None and s._first_wait == 0.0
    assert (s.fast_retries, s.failure_episodes) == (0, 0)
    assert not list(tmp_path.glob("*attempts*"))
    calls = sorted(fetch.calls)
    # as before this mode existed: the entry poll and the thread's first poll
    # back to back, then one every 0.3 s
    assert calls[1][0] - calls[0][1] < 0.1
    assert len(calls) <= 4


def test_an_attempts_log_without_the_retry_mode_is_refused(tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        _sampler(tmp_path, attempts_path=tmp_path / "a.csv")


# --- a typed HTTP failure (IncompleteRead) in the acquisition path ------------------


class _Sequence:
    """A stub GET /metrics answering from a script: an exception instance is
    raised, anything else answers the snapshot; the last item repeats."""

    def __init__(self, *script: object) -> None:
        self.script, self.calls = list(script), 0

    def __call__(self, url: str, timeout_s: float = 5.0) -> dict:
        item = self.script[min(self.calls, len(self.script) - 1)]
        self.calls += 1
        if isinstance(item, BaseException):
            raise item
        return dict(SNAPSHOT)


def _csv_rows(path: Path) -> list[list[str]]:
    with open(path, encoding="utf-8", newline="") as fh:
        return list(csv.reader(fh))[1:]


def test_an_incomplete_body_on_the_entry_poll_is_a_failed_poll_retried_after_50_ms(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(cm, "fetch_metrics", _Sequence(http.client.IncompleteRead(b"{\"acc", 40), "ok"))
    log = tmp_path / "a.csv"
    with cm.ControllerMetricsSampler(tmp_path / "m.csv", URL, interval_s=0.5, fast_retry_s=0.05, attempts_path=log) as s:
        time.sleep(0.3)
    rows = _attempts(log)
    assert rows[0]["outcome"] == "error" and rows[0]["error"].startswith("IncompleteRead: ")
    assert rows[0]["next_wait_s"] == "0.050" and rows[1]["outcome"] == "ok"
    assert s.poll_errors == 1 and s.last_error.startswith("IncompleteRead")
    # no row for the failed poll: every metrics row is a genuine reading
    assert len(_csv_rows(tmp_path / "m.csv")) == s.samples_written == sum(r["outcome"] == "ok" for r in rows)


def test_an_incomplete_body_in_the_running_thread_is_retried_and_the_sampler_recovers(tmp_path: Path, monkeypatch) -> None:
    fetch = _Sequence("ok", http.client.IncompleteRead(b"", 10), "ok")
    monkeypatch.setattr(cm, "fetch_metrics", fetch)
    log = tmp_path / "a.csv"
    with cm.ControllerMetricsSampler(tmp_path / "m.csv", URL, interval_s=0.2, fast_retry_s=0.05, attempts_path=log) as s:
        time.sleep(0.7)
        alive = s._thread.is_alive()
    assert alive                                            # the thread survived the typed failure
    rows = _attempts(log)
    assert [r["outcome"] for r in rows[:3]] == ["ok", "error", "ok"]
    assert rows[1]["error"].startswith("IncompleteRead: ") and rows[1]["next_wait_s"] == "0.050"
    assert s.poll_errors == 1 and (s.fast_retries, s.failure_episodes) == (1, 1)
    assert len(rows) >= 4                                   # it kept polling after the recovery
    assert len(_csv_rows(tmp_path / "m.csv")) == s.samples_written == len(rows) - 1


TYPED_FAILURES = [http.client.IncompleteRead(b"", 5), http.client.BadStatusLine(""), http.client.LineTooLong("header line")]
TYPED_IDS = ["IncompleteRead", "BadStatusLine", "LineTooLong"]


# --- the normal sampler (work order of 2026-09-29, deliverable B): a typed HTTP
# failure is a failed poll, as in the retry mode; cadence, timeout and stop unchanged


@pytest.mark.parametrize("exc", TYPED_FAILURES, ids=TYPED_IDS)
def test_the_default_sampler_counts_a_typed_http_failure_without_a_metrics_row(tmp_path: Path, monkeypatch, exc: Exception) -> None:
    """Until 2026-09-29 the default sampler let it propagate (LOG #C045); now it
    is counted and kept like any failed poll, with no row written."""
    monkeypatch.setattr(cm, "fetch_metrics", _Sequence(exc))
    s = _sampler(tmp_path)
    error = s._sample_once()
    assert error is not None and error.startswith(type(exc).__name__)
    assert (s.poll_errors, s.samples_written) == (1, 0)
    assert (s.fast_retries, s.failure_episodes) == (0, 0)


def test_a_typed_failure_on_the_default_entry_poll_is_counted_and_a_genuine_reading_follows(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(cm, "fetch_metrics", _Sequence(http.client.IncompleteRead(b"", 5), "ok"))
    with cm.ControllerMetricsSampler(tmp_path / "m.csv", URL, interval_s=0.3) as s:
        time.sleep(0.2)
        alive = s._thread.is_alive()
    assert alive
    assert s.poll_errors == 1 and s.last_error.startswith("IncompleteRead")
    assert s.samples_written >= 1 and len(_csv_rows(tmp_path / "m.csv")) == s.samples_written
    assert s._first_wait == 0.0 and not list(tmp_path.glob("*attempts*"))


class _Stamped(_Sequence):
    """A _Sequence that records each call's host instants and outcome."""

    def __init__(self, *script: object) -> None:
        super().__init__(*script)
        self.stamps: list[tuple[float, float, str]] = []

    def __call__(self, url: str, timeout_s: float = 5.0) -> dict:
        start = time.monotonic()
        try:
            result = super().__call__(url, timeout_s)
        except BaseException:
            self.stamps.append((start, time.monotonic(), "error"))
            raise
        self.stamps.append((start, time.monotonic(), "ok"))
        return result


def test_a_typed_failure_in_the_default_thread_is_counted_and_sampling_recovers_at_the_normal_cadence(tmp_path: Path, monkeypatch) -> None:
    fetch = _Stamped("ok", "ok", http.client.IncompleteRead(b"", 10), "ok")
    monkeypatch.setattr(cm, "fetch_metrics", fetch)
    with cm.ControllerMetricsSampler(tmp_path / "m.csv", URL, interval_s=0.2) as s:
        time.sleep(0.8)
        alive = s._thread.is_alive()
    assert alive                                            # the thread survived the typed failure
    outcomes = [o for _, _, o in fetch.stamps]
    assert outcomes[:4] == ["ok", "ok", "error", "ok"] and len(outcomes) >= 5
    failed_end, next_start = fetch.stamps[2][1], fetch.stamps[3][0]
    assert next_start - failed_end >= 0.15                  # the rest of the interval, no 50 ms retry
    assert s.poll_errors == 1 and s.fast_retries == 0
    assert len(_csv_rows(tmp_path / "m.csv")) == s.samples_written == len(outcomes) - 1


def test_the_default_sampler_writes_no_row_for_typed_failures(tmp_path: Path, monkeypatch) -> None:
    fetch = _Stamped(http.client.BadStatusLine(""))
    monkeypatch.setattr(cm, "fetch_metrics", fetch)
    with cm.ControllerMetricsSampler(tmp_path / "m.csv", URL, interval_s=0.1) as s:
        time.sleep(0.35)
    assert _csv_rows(tmp_path / "m.csv") == [] and s.samples_written == 0
    assert s.poll_errors == len(fetch.stamps) >= 2


def test_the_stop_event_ends_a_default_sampler_that_keeps_failing(tmp_path: Path, monkeypatch) -> None:
    fetch = _Stamped(http.client.IncompleteRead(b"", 5))
    monkeypatch.setattr(cm, "fetch_metrics", fetch)
    s = cm.ControllerMetricsSampler(tmp_path / "m.csv", URL, interval_s=10.0)
    s.__enter__()
    time.sleep(0.3)
    calls = len(fetch.stamps)
    started = time.monotonic()
    s.__exit__(None, None, None)
    assert time.monotonic() - started < 1.0 and not s._thread.is_alive()
    assert calls == 2                                       # the entry poll and the thread's immediate first poll
    time.sleep(0.2)
    assert len(fetch.stamps) == calls


@pytest.mark.parametrize("fast", [False, True], ids=["default", "fast-retry"])
def test_a_programming_error_in_the_acquisition_still_propagates(tmp_path: Path, monkeypatch, fast: bool) -> None:
    """Only the typed HTTP failures join the failed polls: no catch-all."""
    monkeypatch.setattr(cm, "fetch_metrics", _Sequence(TypeError("bug")))
    s = _sampler(tmp_path, fast_retry_s=cm.FAST_RETRY_S) if fast else _sampler(tmp_path)
    with pytest.raises(TypeError):
        s._sample_once()
    assert s.poll_errors == 0


def test_a_network_failure_keeps_its_plain_message(tmp_path: Path, monkeypatch) -> None:
    """RemoteDisconnected is an OSError: its message stays the plain one r03 recorded."""
    monkeypatch.setattr(cm, "fetch_metrics", _Sequence(http.client.RemoteDisconnected("Remote end closed connection without response")))
    s = _sampler(tmp_path)
    assert s._sample_once() == "Remote end closed connection without response"


@pytest.mark.parametrize("exc", [http.client.IncompleteRead(b"", 5), http.client.BadStatusLine("")],
                         ids=["IncompleteRead", "BadStatusLine"])
def test_the_retry_mode_counts_a_typed_http_failure_without_a_metrics_row(tmp_path: Path, monkeypatch, exc: Exception) -> None:
    monkeypatch.setattr(cm, "fetch_metrics", _Sequence(exc))
    s = _sampler(tmp_path, fast_retry_s=cm.FAST_RETRY_S)
    error = s._sample_once()
    assert error is not None and error.startswith(type(exc).__name__)
    assert (s.poll_errors, s.samples_written) == (1, 0)
