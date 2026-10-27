"""Tests for egw_experiments.checksums (plan 5.8 evidence integrity)."""
from __future__ import annotations

import re
from pathlib import Path

from egw_experiments import checksums


def _make_run_dir(tmp_path: Path) -> Path:
    run_dir = tmp_path / "raw" / "nominal-r01"
    (run_dir / "logs").mkdir(parents=True)
    (run_dir / "manifest.json").write_text('{"run_id": "nominal-r01"}\n', "utf-8")
    (run_dir / "events.jsonl").write_text('{"outcome": "accepted"}\n', "utf-8")
    (run_dir / "logs" / "simulator.log").write_text("started\n", "utf-8")
    return run_dir


def test_write_and_verify_round_trip(tmp_path) -> None:
    run_dir = _make_run_dir(tmp_path)
    sums_path = checksums.write_sha256sums(run_dir)
    assert sums_path == run_dir / "SHA256SUMS"
    assert checksums.verify_sha256sums(run_dir) == []


def test_sums_format_is_sha256_two_spaces_relative_posix_path(tmp_path) -> None:
    run_dir = _make_run_dir(tmp_path)
    checksums.write_sha256sums(run_dir)
    lines = (run_dir / "SHA256SUMS").read_text("utf-8").splitlines()
    assert len(lines) == 3  # SHA256SUMS itself is never listed
    for line in lines:
        assert re.fullmatch(r"[0-9a-f]{64}  [^ ].*", line), line
    names = [line[66:] for line in lines]
    assert names == sorted(names)
    assert "logs/simulator.log" in names  # posix separators, relative paths


def test_verify_detects_tampering(tmp_path) -> None:
    run_dir = _make_run_dir(tmp_path)
    checksums.write_sha256sums(run_dir)
    (run_dir / "events.jsonl").write_text('{"outcome": "tampered"}\n', "utf-8")
    problems = checksums.verify_sha256sums(run_dir)
    assert problems == ["mismatch: events.jsonl"]


def test_verify_detects_missing_and_unlisted_files(tmp_path) -> None:
    run_dir = _make_run_dir(tmp_path)
    checksums.write_sha256sums(run_dir)
    (run_dir / "events.jsonl").unlink()
    (run_dir / "extra.txt").write_text("not listed\n", "utf-8")
    problems = checksums.verify_sha256sums(run_dir)
    assert "missing: events.jsonl" in problems
    assert "unlisted: extra.txt" in problems


def test_verify_reports_absent_sums_file(tmp_path) -> None:
    run_dir = _make_run_dir(tmp_path)
    assert checksums.verify_sha256sums(run_dir) == ["missing: SHA256SUMS"]


def test_verify_reports_malformed_lines(tmp_path) -> None:
    run_dir = _make_run_dir(tmp_path)
    checksums.write_sha256sums(run_dir)
    sums_path = run_dir / "SHA256SUMS"
    sums_path.write_text(sums_path.read_text("utf-8") + "not-a-sum-line\n", "utf-8")
    problems = checksums.verify_sha256sums(run_dir)
    assert any(problem.startswith("malformed line") for problem in problems)
