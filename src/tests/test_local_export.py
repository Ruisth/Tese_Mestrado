"""Cases for egw_experiments.local_export: the local, per-attempt export to output_test.

They exercise what the work order of 2026-09-19 (2.B) asks the export to survive:
paths with spaces, an interrupted copy, a hash mismatch, a duplicate run id, a
failed test, secrets, missing artefacts, a crashed attempt and a historical
backfill. The project review of 2026-09-19 adds three more: an export path that
a link would redirect outside the chosen root (F1), a console capture that
failed while the command itself succeeded (F2), and a registered source root
that is itself a link (F4). The adversarial rounds that followed add the cases
at the end of this module, the last of them of 2026-09-20: `console/` itself
being a link, one rule for the capture verdict, an artefact named like a file
the export generates, and a record that must not stall. Everything runs on
temporary directories; nothing touches a guest.

NTFS junctions are covered by ``test_local_export_windows.py``, which runs on
native Windows only; the symlink cases here are skipped there, because creating
a symlink on Windows needs a privilege the student's account may not hold.
"""

from __future__ import annotations

import errno
import json
import os
import shutil
import sys
from pathlib import Path

import pytest

from egw_experiments import local_export as le
from egw_experiments.checksums import verify_sha256sums, write_sha256sums

SECRET = "s3cr3t-Password-value"
DISTINCTIVE = "content-only-reachable-through-the-link"

needs_symlinks = pytest.mark.skipif(
    os.name == "nt", reason="POSIX symlinks; NTFS junctions are covered in test_local_export_windows.py")


@pytest.fixture()
def roots(tmp_path: Path) -> tuple[Path, Path, Path]:
    attempts = tmp_path / "wsl attempts"
    dest = tmp_path / "Projeto Mestrado" / "output_test"
    env = tmp_path / "test.env"
    env.write_text(f"MOSQUITTO_SIMULATOR_PASSWORD={SECRET}\nEGW_ID=egw-01\n# comment\n", encoding="utf-8")
    return attempts, dest, env


@pytest.fixture()
def outside(tmp_path: Path) -> Path:
    """A directory outside every export root that nothing may create in or remove from."""
    kept = tmp_path / "outside" / "kept"
    kept.mkdir(parents=True)
    (kept / "sentinel.txt").write_text("sentinel\n", encoding="utf-8")
    return tmp_path / "outside"


def _tree(root: Path) -> dict[str, bytes | None]:
    """Every entry under ``root``: directories as ``None``, files by their bytes."""
    return {p.relative_to(root).as_posix(): (p.read_bytes() if p.is_file() else None)
            for p in sorted(root.rglob("*"))}


class _FailingSink:
    """A console file that stops accepting bytes, as a full disk would.

    ``partial`` is the shape a disk filling up mid-write really has: the
    operating system accepts the head of the chunk and then refuses, so the
    file holds bytes the counter never counted.
    """

    def __init__(self, real, limit: int, mode: str) -> None:
        self._real, self._limit, self._mode = real, limit, mode
        self._seen = 0

    def write(self, data: bytes) -> int:
        if self._mode in ("write", "partial") and self._seen >= self._limit:
            raise OSError(errno.ENOSPC, "No space left on device")
        if self._mode == "partial" and self._seen + len(data) > self._limit:
            head = data[: self._limit - self._seen]
            self._seen += len(head)
            self._real.write(head)
            self._real.flush()
            raise OSError(errno.ENOSPC, "No space left on device")
        self._seen += len(data)
        return self._real.write(data)

    def flush(self) -> None:
        if self._mode == "flush" and self._seen >= self._limit:
            raise OSError(errno.ENOSPC, "No space left on device")
        self._real.flush()

    def tell(self) -> int:
        return self._real.tell()

    def close(self) -> None:
        self._real.close()


class _LosingSink:
    """A console file whose buffered bytes never reach the disk: the close fails."""

    def __init__(self, real) -> None:
        self._real = real

    def write(self, data: bytes) -> int:
        return len(data)  # accepted into a buffer that is never written out

    def flush(self) -> None:
        return None

    def tell(self) -> int:
        return self._real.tell()

    def close(self) -> None:
        self._real.close()
        raise OSError(errno.EIO, "Input/output error")


class _BrokenEcho:
    """A terminal that has gone away: writing to it fails, the evidence does not."""

    def write(self, data: bytes) -> int:
        raise OSError(errno.EPIPE, "Broken pipe")

    def flush(self) -> None:
        raise OSError(errno.EPIPE, "Broken pipe")


class _BrokenStdout:
    buffer = _BrokenEcho()


@pytest.fixture()
def failing_console(monkeypatch):
    """Make the console file of the chosen streams fail after ``limit`` bytes."""
    def install(*, limit: int = 0, mode: str = "write", streams: tuple[str, ...] = ("stdout",)) -> None:
        real = le._open_console_pair

        def wrap(handle):
            return _LosingSink(handle) if mode == "lose-at-close" else _FailingSink(handle, limit, mode)

        def patched(attempt_dir, slug):
            seq, out_rel, err_rel, out_f, err_f = real(attempt_dir, slug)
            if "stdout" in streams:
                out_f = wrap(out_f)
            if "stderr" in streams:
                err_f = wrap(err_f)
            return seq, out_rel, err_rel, out_f, err_f

        monkeypatch.setattr(le, "_open_console_pair", patched)

    return install


def _raw_capsule(base: Path, run_id: str = "nominal-r01") -> Path:
    raw = base / "results" / "raw" / run_id
    (raw / "logs" / "collector").mkdir(parents=True)
    (raw / "manifest.json").write_text('{"validity": "invalid", "path": "/home/x/abs"}\r\n', encoding="utf-8")
    (raw / "logs" / "collector" / f"resources-{run_id}.csv").write_bytes(b"ts_utc,container\r\nline\n")
    write_sha256sums(raw)
    return raw


def _attempt(attempts: Path, dest: Path, **kw) -> Path:
    return le.new_attempt(attempts, kw.pop("scenario", "nominal"), "engineering", dest_root=dest, **kw)


def _all_bytes(root: Path) -> bytes:
    return b"".join(p.read_bytes() for p in root.rglob("*") if p.is_file())


def _link_to_dir(target: Path, link: Path) -> None:
    """A link to a directory: a symlink on POSIX, an NTFS junction on Windows.

    A symlink needs a privilege the student's account may not hold on Windows,
    so the junction stands in for it there; both are refused the same way.
    """
    if os.name == "nt":
        import _winapi

        _winapi.CreateJunction(str(target), str(link))
    else:
        link.symlink_to(target, target_is_directory=True)


def test_run_ids_are_windows_safe_unique_and_numbered(roots):
    attempts, dest, _ = roots
    a1 = _attempt(attempts, dest)
    a2 = _attempt(attempts, dest)
    other = _attempt(attempts, dest, scenario="Smartwatch slice 60 s")
    assert ":" not in a1.name
    assert a1.name.endswith("_nominal_attempt01")
    assert a2.name.endswith("_nominal_attempt02")
    assert other.name.endswith("_smartwatch-slice-60-s_attempt01")
    assert json.loads((a1 / "attempt.json").read_text())["status"] == "running"


def test_a_command_is_recorded_with_its_output_and_exit_code_and_no_secret(roots):
    attempts, dest, env = roots
    a = _attempt(attempts, dest)
    code = le.run_command(
        a, "echo", [sys.executable, "-c", "import sys; print('out'); print('err', file=sys.stderr); sys.exit(3)",
                    "--password", SECRET],
        secrets=le.load_secrets(env), echo=False,
    )
    assert code == 3
    rec = json.loads((a / "commands.jsonl").read_text().splitlines()[0])
    assert rec["exit_code"] == 3
    assert SECRET not in json.dumps(rec)
    assert "[REDACTED:MOSQUITTO_SIMULATOR_PASSWORD]" in rec["argv"]
    assert (a / rec["stdout"]).read_text().strip() == "out"
    assert (a / rec["stderr"]).read_text().strip() == "err"


def test_a_complete_export_keeps_bytes_seals_and_siblings(roots, tmp_path):
    attempts, dest, env = roots
    raw = _raw_capsule(tmp_path / "pilot")
    sim_root = tmp_path / "itest"
    (sim_root / "slice-01").mkdir(parents=True)
    (sim_root / "slice-01" / "sent_events.jsonl").write_text("{}\n")
    (sim_root / "slice-01.marker.json").write_text("{}")
    (sim_root / "slice-01.reconcile").mkdir()
    (sim_root / "slice-01.reconcile" / "table.csv").write_text("a\n")
    (sim_root / "slice-02.marker.json").write_text("{}")  # another run's sibling: not taken
    a = _attempt(attempts, dest)
    le.add_source(a, "raw", raw, role="harness capsule")
    le.add_source(a, "simulator", sim_root / "slice-01", siblings_glob="slice-01.*")
    le.run_command(a, "ok", [sys.executable, "-c", "print(1)"], echo=False)
    le.finish_attempt(a, "finished", instrumentation_validity="valid", system_outcome="pass", reason="all accounted")

    m = le.export_attempt(a, dest, secrets=le.load_secrets(env))

    pkg = Path(m["destination"]["package"])
    assert pkg.parent.parent.name == "runs" and " " in str(pkg)
    assert m["copy_verification"] == "verified"
    assert verify_sha256sums(pkg) == []
    assert verify_sha256sums(pkg / "raw" / "nominal-r01") == []  # the capsule's own seal still holds
    assert (pkg / "raw" / "nominal-r01" / "manifest.json").read_bytes().endswith(b"\r\n")  # bytes untouched
    assert (pkg / "simulator" / "slice-01.marker.json").is_file()
    assert (pkg / "simulator" / "slice-01.reconcile" / "table.csv").is_file()
    assert not (pkg / "simulator" / "slice-02.marker.json").exists()
    summary = (pkg / "SUMMARY.md").read_text()
    assert le.EMULATED_LABEL in summary
    assert "| Instrumentation validity | **valid** |" in summary and "| System outcome | **pass** |" in summary
    index = (dest / "INDEX.md").read_text()
    assert a.name in index and "verified" in index
    assert json.loads((a / "export" / "receipt.json").read_text())["state"] == "complete"
    assert not (dest / "incomplete" / a.name).exists()


def test_a_failed_test_stays_failed_after_a_good_export(roots):
    attempts, dest, env = roots
    a = _attempt(attempts, dest)
    code = le.run_command(a, "test", [sys.executable, "-c", "raise SystemExit(1)"], echo=False)
    le.finish_attempt(a, "failed", instrumentation_validity="valid", system_outcome="fail",
                      reason=f"test exited {code}")
    m = le.export_attempt(a, dest, secrets=le.load_secrets(env))
    summary = (Path(m["destination"]["package"]) / "SUMMARY.md").read_text()
    assert m["copy_verification"] == "verified"
    assert "| System outcome | **fail** |" in summary
    assert "| 1 | test | 1 |" in summary


def test_a_duplicate_export_is_a_no_op_and_a_tampered_package_is_refused(roots):
    attempts, dest, env = roots
    a = _attempt(attempts, dest)
    le.finish_attempt(a, "finished")
    m1 = le.export_attempt(a, dest)
    m2 = le.export_attempt(a, dest)
    assert m2["note"].startswith("already exported")
    pkg = Path(m1["destination"]["package"])
    (pkg / "attempt.json").write_text("{}")
    with pytest.raises(le.ExportError, match="already exists"):
        le.export_attempt(a, dest)


def test_a_hash_mismatch_keeps_the_package_incomplete_until_a_good_copy(roots):
    attempts, dest, env = roots
    a = _attempt(attempts, dest)
    (a / "tests" / "junit.xml").write_text("<testsuite/>")
    le.finish_attempt(a, "finished")

    def corrupting(src, dst, retries=2):
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_bytes(src.read_bytes() + b"x")
        return "mismatch", "0" * 64

    with pytest.raises(le.ExportError, match="did not verify"):
        le.export_attempt(a, dest, copier=corrupting)
    staging = dest / "incomplete" / a.name
    assert staging.is_dir() and not list((dest / "runs").rglob("SUMMARY.md"))
    assert "INCOMPLETE" in (dest / "INDEX.md").read_text()
    assert json.loads((a / "export" / "receipt.json").read_text())["state"] == "failed"

    m = le.export_attempt(a, dest)  # resumes and completes
    assert m["copy_verification"] == "verified" and not staging.exists()
    assert (Path(m["destination"]["package"]) / "tests" / "junit.xml").read_text() == "<testsuite/>"


def test_an_interrupted_copy_is_recovered_without_rerunning(roots):
    attempts, dest, env = roots
    a = _attempt(attempts, dest)
    for i in range(3):
        (a / "analysis" / f"t{i}.csv").write_text(str(i))
    le.finish_attempt(a, "finished")
    calls = {"n": 0}

    def dying(src, dst, retries=2):
        calls["n"] += 1
        if calls["n"] == 2:
            raise OSError("copy interrupted")
        return le._copy_verified(src, dst, retries)

    with pytest.raises(le.ExportError, match="operating-system error"):
        le.export_attempt(a, dest, copier=dying)
    assert (dest / "incomplete" / a.name).is_dir()
    assert json.loads((a / "export" / "receipt.json").read_text())["state"] == "failed"
    assert "INCOMPLETE" in (dest / "INDEX.md").read_text()
    results = le.recover(attempts, dest)
    assert results == [{"run_id": a.name, "result": "exported"}]
    assert len(list((dest / "runs").rglob("t*.csv"))) == 3


def test_the_real_copy_check_catches_a_corrupted_destination(roots, monkeypatch):
    attempts, dest, env = roots
    a = _attempt(attempts, dest)
    (a / "tests" / "junit.xml").write_text("<testsuite/>")
    le.finish_attempt(a, "finished")
    real = le.shutil.copyfile

    def corrupt(src, dst, *args, **kwargs):
        real(src, dst)
        with open(dst, "ab") as fh:
            fh.write(b"!")

    monkeypatch.setattr(le.shutil, "copyfile", corrupt)
    with pytest.raises(le.ExportError, match="did not verify"):
        le.export_attempt(a, dest)
    assert not list((dest / "runs").rglob("junit.xml"))


def test_secrets_are_excluded_with_a_redacted_derivative(roots, tmp_path):
    attempts, dest, env = roots
    a = _attempt(attempts, dest)
    (a / "environment" / "env-dump.txt").write_text(f"EGW_ID=egw-01\nMOSQUITTO_SIMULATOR_PASSWORD={SECRET}\n")
    (a / "environment" / "server.key").write_text("-----BEGIN PRIVATE KEY-----\nabc\n-----END PRIVATE KEY-----\n")
    le.finish_attempt(a, "finished")
    m = le.export_attempt(a, dest, secrets=le.load_secrets(env))
    pkg = Path(m["destination"]["package"])
    assert SECRET.encode() not in _all_bytes(pkg)
    assert b"BEGIN PRIVATE KEY" not in _all_bytes(pkg)
    assert not (pkg / "environment" / "env-dump.txt").exists()
    derivative = (pkg / "environment" / "env-dump.txt.sanitized").read_text()
    assert "[REDACTED:MOSQUITTO_SIMULATOR_PASSWORD]" in derivative and "EGW_ID=egw-01" in derivative
    assert not (pkg / "environment" / "server.key.sanitized").exists()
    assert {e["package_path"] for e in m["excluded"]} == {"environment/env-dump.txt", "environment/server.key"}
    assert "Excluded for secrets" in (pkg / "SUMMARY.md").read_text()
    assert (a / "environment" / "env-dump.txt").read_text().count(SECRET) == 1  # original untouched in WSL


def test_a_missing_artefact_is_declared_not_fabricated(roots, tmp_path):
    attempts, dest, env = roots
    a = _attempt(attempts, dest)
    le.add_source(a, "raw", tmp_path / "results" / "raw" / "never-written", role="harness capsule")
    le.update_attempt(a, {"expected_artefacts": ["raw/*/resources.csv"]})
    le.finish_attempt(a, "failed", system_outcome="fail", reason="harness did not start")
    m = le.export_attempt(a, dest)
    pkg = Path(m["destination"]["package"])
    assert m["missing_sources"][0]["path"].endswith("never-written")
    assert not (pkg / "raw").exists()
    summary = (pkg / "SUMMARY.md").read_text()
    assert "did not exist at export time" in summary and "`raw/*/resources.csv`: **missing**" in summary


def test_a_running_attempt_is_never_touched_unless_the_operator_names_it(roots):
    attempts, dest, env = roots
    a = _attempt(attempts, dest)
    with pytest.raises(le.ExportError, match="still marked running"):
        le.export_attempt(a, dest)
    # recover in another terminal while the attempt is still being driven:
    assert le.recover(attempts, dest)[0]["result"].startswith("running: not touched")
    assert json.loads((a / "attempt.json").read_text())["status"] == "running"
    assert not (dest / "runs").exists() or not list((dest / "runs").rglob(a.name))
    # the operator says its process died:
    le.run_command(a, "partial", [sys.executable, "-c", "print(1)"], echo=False)
    results = le.recover(attempts, dest, interrupt=[a.name])
    assert results[0]["result"] == "exported"
    pkg = next((dest / "runs").rglob(a.name))
    attempt = json.loads((pkg / "attempt.json").read_text())
    assert attempt["status"] == "interrupted" and attempt["system_outcome"] == "interrupted"
    last = json.loads((a / "commands.jsonl").read_text().splitlines()[-1])
    assert attempt["ended_utc"] == last["ended_utc"]  # not the time of the recovery


def test_a_package_finalised_from_an_earlier_state_is_not_reported_as_exported(roots):
    attempts, dest, env = roots
    a = _attempt(attempts, dest)
    le.finish_attempt(a, "interrupted", system_outcome="interrupted")
    le.export_attempt(a, dest)
    le.finish_attempt(a, "finished", system_outcome="pass")
    with pytest.raises(le.ExportError, match="earlier state"):
        le.export_attempt(a, dest)


def test_recover_goes_on_after_one_attempt_fails(roots):
    attempts, dest, env = roots
    bad = _attempt(attempts, dest)
    le.finish_attempt(bad, "finished")
    le.update_attempt(bad, {"run_id": "not a valid id"})
    good = _attempt(attempts, dest, scenario="other")
    le.finish_attempt(good, "finished")
    results = {r["run_id"]: r["result"] for r in le.recover(attempts, dest)}
    assert results[bad.name].startswith("export failed")
    assert results[good.name] == "exported"


def test_a_secret_in_an_attempt_field_never_reaches_the_summary(roots):
    attempts, dest, env = roots
    a = _attempt(attempts, dest)
    le.finish_attempt(a, "failed", system_outcome="fail", reason=f"broker refused --password {SECRET}")
    m = le.export_attempt(a, dest, secrets=le.load_secrets(env))
    pkg = Path(m["destination"]["package"])
    assert SECRET.encode() not in _all_bytes(pkg)
    assert "[REDACTED:MOSQUITTO_SIMULATOR_PASSWORD]" in (pkg / "SUMMARY.md").read_text()
    assert m["secret_scan"]["secret_values"] == ["MOSQUITTO_SIMULATOR_PASSWORD"]
    assert "| fail |" in (dest / "INDEX.md").read_text()  # verdicts read from the redacted attempt


def test_an_export_without_secret_values_says_so(roots):
    attempts, dest, env = roots
    a = _attempt(attempts, dest)
    le.finish_attempt(a, "finished")
    m = le.export_attempt(a, dest)
    assert "NO env file" in (Path(m["destination"]["package"]) / "SUMMARY.md").read_text()


def test_sources_with_the_same_name_get_distinct_folders(roots, tmp_path):
    attempts, dest, env = roots
    one = _raw_capsule(tmp_path / "a", "r01")
    two = _raw_capsule(tmp_path / "b", "r01")
    a = _attempt(attempts, dest)
    le.add_source(a, "raw", one)
    le.add_source(a, "raw", two)
    le.finish_attempt(a, "finished")
    pkg = Path(le.export_attempt(a, dest)["destination"]["package"])
    assert verify_sha256sums(pkg / "raw" / "r01") == []
    assert verify_sha256sums(pkg / "raw" / "source02-r01") == []


def test_names_that_differ_only_by_case_are_refused(roots, tmp_path):
    attempts, dest, env = roots
    a = _attempt(attempts, dest)
    (a / "analysis" / "Table.csv").write_text("1")
    (a / "analysis" / "table.csv").write_text("2")
    le.finish_attempt(a, "finished")
    if len(list((a / "analysis").iterdir())) < 2:
        pytest.skip("case-insensitive filesystem")
    with pytest.raises(le.ExportError, match="same package path on Windows"):
        le.export_attempt(a, dest)


def test_expected_artefact_patterns_do_not_cross_folders(roots, tmp_path):
    attempts, dest, env = roots
    raw = tmp_path / "results" / "raw" / "nominal-r01"
    (raw / "logs").mkdir(parents=True)
    (raw / "logs" / "manifest.json").write_text("{}")
    a = _attempt(attempts, dest)
    le.add_source(a, "raw", raw)
    le.update_attempt(a, {"expected_artefacts": ["raw/*/manifest.json"]})
    le.finish_attempt(a, "finished")
    summary = (Path(le.export_attempt(a, dest)["destination"]["package"]) / "SUMMARY.md").read_text()
    assert "`raw/*/manifest.json`: **missing**" in summary


def test_a_relative_source_is_recorded_absolute(roots, tmp_path, monkeypatch):
    attempts, dest, env = roots
    a = _attempt(attempts, dest)
    monkeypatch.chdir(tmp_path)
    le.add_source(a, "raw", "results/raw/later")
    path = json.loads((a / "sources.json").read_text())["sources"][0]["path"]
    # The separator is the running platform's, so the tail is compared by parts.
    assert Path(path).is_absolute() and Path(path).parts[-3:] == ("results", "raw", "later")


def test_a_command_never_overwrites_an_earlier_console_file(roots):
    attempts, dest, env = roots
    a = _attempt(attempts, dest)
    (a / "console" / "001-crashed.stdout.txt").write_text("kept")
    le.run_command(a, "next", [sys.executable, "-c", "print(2)"], echo=False)
    assert (a / "console" / "001-crashed.stdout.txt").read_text() == "kept"
    assert (a / "console" / "002-next.stdout.txt").is_file()


def test_a_historical_backfill_keeps_its_seal_and_is_indexed_as_historical(roots, tmp_path):
    attempts, dest, env = roots
    raw = _raw_capsule(tmp_path / "old", "controller_restart-r02")
    m = le.backfill(raw, attempts, dest, name="controller_restart-r02", scenario="controller restart",
                    date="2026-09-19", note="invalid run: resources not ingested", original_validity="invalid",
                    original_outcome="fail")
    pkg = Path(m["destination"]["package"])
    assert pkg.name == "HIST_controller_restart-r02" and pkg.parent.name == "2026-09-19"
    assert verify_sha256sums(pkg / "raw" / "controller_restart-r02") == []
    assert "Historical attempt" in (pkg / "SUMMARY.md").read_text()
    assert "*(historical)*" in (dest / "INDEX.md").read_text()
    # The same record again is the no-op; a different one is the next case.
    assert le.backfill(raw, attempts, dest, name="controller_restart-r02", scenario="controller restart",
                       date="2026-09-19", note="invalid run: resources not ingested",
                       original_validity="invalid",
                       original_outcome="fail")["note"].startswith("already exported")
    other = _raw_capsule(tmp_path / "elsewhere", "controller_restart-r02")
    with pytest.raises(le.ExportError, match="already used"):
        le.backfill(other, attempts, dest, name="controller_restart-r02", scenario="x", date="2026-09-19",
                    note="a different capsule under the same name")


@pytest.mark.parametrize("date", ["../../archive", "/tmp/elsewhere", "2026-9-19", "2026-02-30", ""])
def test_a_backfill_date_must_be_a_calendar_date(roots, tmp_path, date):
    attempts, dest, env = roots
    raw = _raw_capsule(tmp_path / "old")
    with pytest.raises(ValueError):
        le.backfill(raw, attempts, dest, name="x", scenario="x", date=date, note="x")
    assert not (attempts / "_historical").exists()
    assert not any(p.name.startswith("HIST_") for p in tmp_path.rglob("HIST_*"))


def test_the_index_never_loses_an_attempt(roots):
    attempts, dest, env = roots
    names = []
    for _ in range(3):
        a = _attempt(attempts, dest)
        le.finish_attempt(a, "finished")
        le.export_attempt(a, dest)
        names.append(a.name)
    (dest / "INDEX.md").unlink()
    le.rebuild_index(dest)
    index = (dest / "INDEX.md").read_text()
    assert all(n in index for n in names)
    assert names[-1] in (dest / "LATEST_SUMMARY.md").read_text()


def test_the_command_line_round_trip(roots, capsys):
    attempts, dest, env = roots
    assert le.main(["new", "--attempts-root", str(attempts), "--scenario", "cli", "--purpose", "engineering"]) == 0
    a = capsys.readouterr().out.strip()
    assert le.main(["exec", "--attempt", a, "--name", "false", "--secrets-env", str(env), "--",
                    sys.executable, "-c", "raise SystemExit(5)"]) == 5
    assert le.main(["set", "--attempt", a, "workload={\"devices\": 1}"]) == 0
    assert le.main(["finish", "--attempt", a, "--status", "failed", "--outcome", "fail", "--reason", "exit 5"]) == 0
    assert le.main(["export", "--attempt", a, "--dest-root", str(dest), "--secrets-env", str(env)]) == 0
    assert "verified" in capsys.readouterr().out
    assert le.main(["export", "--attempt", str(Path(a).parent / "nope"), "--dest-root", str(dest),
                    "--secrets-env", str(env)]) == 2
    with pytest.raises(SystemExit):  # the secret scan is not optional on the command line
        le.main(["export", "--attempt", a, "--dest-root", str(dest)])
    with pytest.raises(SystemExit):  # an empty destination would write into the current directory
        le.main(["export", "--attempt", a, "--dest-root", " ", "--secrets-env", str(env)])


@pytest.mark.skipif(not hasattr(os, "mkfifo"), reason="needs FIFOs")
def test_a_fifo_or_symlink_is_listed_and_never_read(roots, tmp_path):
    attempts, dest, env = roots
    capsule = tmp_path / "old-capsule"
    (capsule / "boot").mkdir(parents=True)
    (capsule / "boot" / "run.log").write_text("boot\n")
    os.mkfifo(capsule / "boot" / "run.stdin.fifo")  # reading it would block the export
    (capsule / "link").symlink_to(tmp_path)
    m = le.backfill(capsule, attempts, dest, name="old-capsule", scenario="session", date="2026-09-19",
                    note="unclosed session")
    pkg = Path(m["destination"]["package"])
    assert (pkg / "raw" / "old-capsule" / "boot" / "run.log").is_file()
    types = {s["package_path"]: s["type"] for s in m["skipped_special"]}
    assert types["raw/old-capsule/boot/run.stdin.fifo"].startswith("special file")
    assert types["raw/old-capsule/link"] == "symlink"
    assert "never read" in (pkg / "SUMMARY.md").read_text()


@pytest.mark.skipif(os.name == "nt", reason="POSIX path semantics")
def test_wsl_paths_are_mapped_for_the_summary():
    assert le._wsl_to_windows(Path("/mnt/c/Users/ruimf/Documents/Projeto Mestrado/output_test")) == \
        "C:\\Users\\ruimf\\Documents\\Projeto Mestrado\\output_test"


# --------------------------------------------------------------------------
# F2 — a console capture that failed while the command itself succeeded
# --------------------------------------------------------------------------


def test_a_failed_console_write_is_recorded_and_the_child_keeps_its_code(roots, failing_console):
    attempts, dest, _env = roots
    a = _attempt(attempts, dest)
    failing_console(limit=0, mode="write")
    rec = le.run_command_record(a, "probe", [sys.executable, "-c", "print('output that never lands')"], echo=False)
    assert rec["exit_code"] == 0  # the command did what it was asked to do
    out = rec["capture"]["stdout"]
    assert out["state"] == "failed" and out["bytes_received"] > 0 and out["bytes_kept"] == 0
    assert "No space left" in out["error"]
    assert rec["capture"]["stderr"]["state"] == "complete"
    failures = json.loads((a / "attempt.json").read_text())["capture_failures"]
    assert [f["stream"] for f in failures] == ["stdout"]
    assert failures[0]["seq"] == rec["seq"] and failures[0]["name"] == "probe"
    assert failures[0]["bytes_kept"] == 0 and failures[0]["bytes_received"] == out["bytes_received"]


def test_a_failed_console_flush_is_recorded_like_a_failed_write(roots, failing_console):
    attempts, dest, _env = roots
    a = _attempt(attempts, dest)
    failing_console(limit=0, mode="flush", streams=("stderr",))
    rec = le.run_command_record(
        a, "probe", [sys.executable, "-c", "import sys; print('kept'); print('lost', file=sys.stderr)"], echo=False)
    assert rec["exit_code"] == 0
    assert rec["capture"]["stdout"]["state"] == "complete"
    err = rec["capture"]["stderr"]
    assert err["state"] == "failed" and err["bytes_received"] > 0
    # What the console file really holds, not what the counter had reached:
    # the flush failed after the bytes of that chunk had been accepted.
    assert err["bytes_kept"] == (a / rec["stderr"]).stat().st_size <= err["bytes_received"]
    assert [f["stream"] for f in json.loads((a / "attempt.json").read_text())["capture_failures"]] == ["stderr"]


def test_a_capture_failure_exits_74_downgrades_the_verdict_and_shows_in_the_package(roots, failing_console, capsys):
    attempts, dest, env = roots
    assert le.main(["new", "--attempts-root", str(attempts), "--scenario", "capture", "--purpose",
                    "engineering"]) == 0
    a = capsys.readouterr().out.strip()
    failing_console(limit=0, mode="write")
    assert le.main(["exec", "--attempt", a, "--name", "probe", "--secrets-env", str(env), "--",
                    sys.executable, "-c", "print('output that never lands')"]) == le.EXIT_CAPTURE_FAILED
    assert le.main(["finish", "--attempt", a, "--status", "finished", "--validity", "valid",
                    "--outcome", "pass", "--reason", "the workload itself passed"]) == 0
    attempt = json.loads((Path(a) / "attempt.json").read_text())
    assert attempt["instrumentation_validity"] == "invalid"
    assert "downgraded from 'valid'" in attempt["validity_note"] and "stdout of probe" in attempt["validity_note"]
    assert attempt["system_outcome"] == "pass"  # what the system did is a separate verdict

    m = le.export_attempt(a, dest, secrets=le.load_secrets(env))
    summary = (Path(m["destination"]["package"]) / "SUMMARY.md").read_text(encoding="utf-8")
    assert "| Console capture | **INCOMPLETE**" in summary
    assert "stdout **INCOMPLETE**" in summary  # the commands table cannot look complete either
    assert "| Instrumentation validity | **invalid** |" in summary
    assert "| 1 | probe | 0 |" in summary  # the command's own exit code is untouched


def test_an_echo_failure_alone_is_not_a_loss_of_evidence(roots, monkeypatch):
    attempts, dest, env = roots
    a = _attempt(attempts, dest)
    monkeypatch.setattr(sys, "stdout", _BrokenStdout())
    assert le.main(["exec", "--attempt", str(a), "--name", "probe", "--secrets-env", str(env), "--",
                    sys.executable, "-c", "import sys; print('seen'); sys.exit(7)"]) == 7
    rec = json.loads((a / "commands.jsonl").read_text().splitlines()[-1])
    assert rec["exit_code"] == 7
    assert rec["capture"]["stdout"]["state"] == "complete"
    assert rec["capture"]["stdout"]["echo"].startswith("failed:")
    assert rec["capture"]["stdout"]["bytes_kept"] == rec["capture"]["stdout"]["bytes_received"] > 0
    assert json.loads((a / "attempt.json").read_text())["capture_failures"] == []
    assert (a / rec["stdout"]).read_text().strip() == "seen"


def test_a_failing_child_and_a_failing_capture_keep_both_facts(roots, failing_console, capsys):
    attempts, dest, env = roots
    assert le.main(["new", "--attempts-root", str(attempts), "--scenario", "capture", "--purpose",
                    "engineering"]) == 0
    a = capsys.readouterr().out.strip()
    failing_console(limit=0, mode="write")
    assert le.main(["exec", "--attempt", a, "--name", "probe", "--secrets-env", str(env), "--", sys.executable,
                    "-c", "import sys; print('lost'); sys.exit(3)"]) == le.EXIT_CAPTURE_FAILED
    rec = json.loads((Path(a) / "commands.jsonl").read_text().splitlines()[-1])
    assert rec["exit_code"] == 3  # the child's own code, not the capture's
    assert rec["capture"]["stdout"]["state"] == "failed"


def test_a_command_recorded_before_capture_state_existed_never_reads_as_complete(roots):
    attempts, dest, _env = roots
    a = _attempt(attempts, dest)
    le.run_command(a, "probe", [sys.executable, "-c", "print('out')"], echo=False)
    old = json.loads((a / "commands.jsonl").read_text().splitlines()[0])
    old.pop("capture")  # a record written before the export recorded capture state
    (a / "commands.jsonl").write_text(json.dumps(old) + "\n", encoding="utf-8")
    le.finish_attempt(a, "finished", instrumentation_validity="valid", system_outcome="pass")
    summary = (Path(le.export_attempt(a, dest)["destination"]["package"]) / "SUMMARY.md").read_text(encoding="utf-8")
    # Only what was measured: the cell may not pick one cause (a record from
    # before capture state existed) out of the several that look alike here.
    assert ("| Console capture | **not recorded** for 1 of 1 command record(s): they say nothing about "
            "whether their console files kept everything |") in summary
    assert "they ran before the export recorded" not in summary
    assert "| 1 | probe | 0 | " in summary and "not recorded" in summary.split("## Commands")[1]


def test_an_attempt_that_ran_no_command_says_the_capture_does_not_apply(roots):
    attempts, dest, _env = roots
    a = _attempt(attempts, dest)
    le.finish_attempt(a, "finished")
    summary = (Path(le.export_attempt(a, dest)["destination"]["package"]) / "SUMMARY.md").read_text(encoding="utf-8")
    assert "| Console capture | not applicable — no command was run through this attempt |" in summary


def test_a_recorded_capture_failure_stands_alone_when_the_attempt_list_is_lost(roots, failing_console):
    """The attempt's list is written after the record, so it can be lost; the record cannot be."""
    attempts, dest, _env = roots
    a = _attempt(attempts, dest)
    failing_console(limit=0, mode="write")
    le.run_command_record(a, "probe", [sys.executable, "-c", "print('output that never lands')"], echo=False)
    # the read-modify-write that carries the list was lost (a crash, a `set`,
    # an attempt directory that was not writable at that moment)
    data = json.loads((a / "attempt.json").read_text())
    data["capture_failures"] = []
    (a / "attempt.json").write_text(json.dumps(data), encoding="utf-8")
    assert le.capture_failed(json.loads((a / "commands.jsonl").read_text().splitlines()[-1]))

    le.finish_attempt(a, "finished", instrumentation_validity="valid", system_outcome="pass")
    attempt = json.loads((a / "attempt.json").read_text())
    assert attempt["instrumentation_validity"] == "invalid"  # the record alone downgrades it
    assert "stdout of probe" in attempt["validity_note"]
    assert [f["stream"] for f in attempt["capture_failures"]] == ["stdout"]  # and it is back in the list
    summary = (Path(le.export_attempt(a, dest)["destination"]["package"]) / "SUMMARY.md").read_text(encoding="utf-8")
    assert "| Console capture | **INCOMPLETE**" in summary
    assert "| Instrumentation validity | **invalid** |" in summary


def test_the_verdict_reads_the_records_even_when_the_attempt_field_is_empty():
    """The union, exercised directly: the field and the record disagree, the loss wins."""
    attempt = {"run_id": "20260919T120000Z_demo_attempt01", "status": "finished",
               "instrumentation_validity": "valid", "system_outcome": "pass", "capture_failures": []}
    commands = [{"seq": 1, "name": "demo", "exit_code": 0, "duration_s": 1.0,
                 "stdout": "console/001-demo.stdout.txt", "stderr": "console/001-demo.stderr.txt",
                 "capture": {"stdout": {"state": "failed", "bytes_received": 4096, "bytes_kept": 13,
                                        "error": "OSError: [Errno 28] No space left on device"},
                             "stderr": {"state": "complete", "bytes_received": 0, "bytes_kept": 0}}}]
    assert [f["stream"] for f in le.capture_failures(attempt, commands)] == ["stdout"]
    assert le._capture_verdict(attempt, commands).startswith("**INCOMPLETE**")


def test_a_capture_failure_that_cannot_be_recorded_in_the_attempt_still_exits_74(roots, failing_console,
                                                                                 monkeypatch, capsys):
    attempts, dest, env = roots
    a = _attempt(attempts, dest)
    real = le.update_attempt

    def blocked(attempt_dir, updates):
        if "capture_failures" in updates:
            raise OSError(errno.EACCES, "Permission denied")
        return real(attempt_dir, updates)

    failing_console(limit=0, mode="write")
    monkeypatch.setattr(le, "update_attempt", blocked)
    # 74 (the evidence is incomplete), never 2 (the tool itself failed)
    assert le.main(["exec", "--attempt", str(a), "--name", "probe", "--secrets-env", str(env), "--",
                    sys.executable, "-c", "print('output that never lands')"]) == le.EXIT_CAPTURE_FAILED
    assert "could not be written to attempt.json" in capsys.readouterr().err
    rec = json.loads((a / "commands.jsonl").read_text().splitlines()[-1])
    assert rec["capture"]["stdout"]["state"] == "failed"
    assert "Permission denied" in rec["capture"]["not_persisted"]
    assert json.loads((a / "attempt.json").read_text())["capture_failures"] == []

    monkeypatch.setattr(le, "update_attempt", real)
    le.finish_attempt(a, "finished", instrumentation_validity="valid", system_outcome="pass")
    assert json.loads((a / "attempt.json").read_text())["instrumentation_validity"] == "invalid"


def test_a_console_file_with_no_record_is_never_read_as_complete(roots):
    """An interrupted command leaves console files and no record: its output is unaccounted for."""
    attempts, dest, _env = roots
    a = _attempt(attempts, dest)
    le.run_command(a, "first", [sys.executable, "-c", "print('first command output')"], echo=False)
    (a / "console" / "002-long-probe.stdout.txt").write_bytes(b"evidence line 0\nevidence line 1\n")
    le.finish_attempt(a, "interrupted", system_outcome="interrupted")
    m = le.export_attempt(a, dest)
    summary = (Path(m["destination"]["package"]) / "SUMMARY.md").read_text(encoding="utf-8")
    assert "| Console capture | **INCOMPLETE**" in summary
    assert "console/002-long-probe.stdout.txt" in summary
    assert "Console output nobody accounted for" in summary
    assert [f["console"] for f in m["capture_failures"]] == ["console/002-long-probe.stdout.txt"]


def test_two_unaccounted_console_files_are_two_entries_and_stay_two(roots):
    """Two lost streams must not collapse onto one key, on this read or any later one."""
    attempts, dest, _env = roots
    a = _attempt(attempts, dest)
    (a / "console" / "001-first.stdout.txt").write_bytes(b"one\n")
    (a / "console" / "002-second.stdout.txt").write_bytes(b"two two\n")
    le.finish_attempt(a, "interrupted", system_outcome="interrupted")
    kept = ["console/001-first.stdout.txt", "console/002-second.stdout.txt"]
    assert sorted(f["console"] for f in json.loads((a / "attempt.json").read_text())["capture_failures"]) == kept

    # The stored list is read back and joined with the inventory on every
    # update: the identity used to store an entry must be the one used to find
    # it again, or the same file is admitted twice and the second is dropped.
    for _ in range(2):
        le.update_attempt(a, {"reason": "read again"})
    failures = json.loads((a / "attempt.json").read_text())["capture_failures"]
    assert sorted(f["console"] for f in failures) == kept
    m = le.export_attempt(a, dest)
    assert sorted(f["console"] for f in m["capture_failures"]) == kept
    summary = (Path(m["destination"]["package"]) / "SUMMARY.md").read_text(encoding="utf-8")
    assert "**INCOMPLETE** — 2 console stream(s) were not kept in full" in summary
    assert summary.count("- `console/001-first.stdout.txt`") == 1


def test_a_file_in_console_the_export_did_not_write_costs_no_run_its_validity(roots):
    """An editor's swap file or an operator's note is not a lost console stream."""
    attempts, dest, _env = roots
    a = _attempt(attempts, dest)
    le.run_command(a, "measured window", [sys.executable, "-c", "print('out')"], echo=False)
    (a / "console" / ".001-measured-window.stdout.txt.swp").write_bytes(b"swapfile")
    (a / "console" / "operator-notes.txt").write_bytes(b"read console/\n")
    le.finish_attempt(a, "finished", instrumentation_validity="valid", system_outcome="pass")
    attempt = json.loads((a / "attempt.json").read_text())
    assert attempt["instrumentation_validity"] == "valid" and attempt["capture_failures"] == []

    m = le.export_attempt(a, dest)
    assert [e["console"] for e in m["console_extra_files"]] == [
        "console/.001-measured-window.stdout.txt.swp", "console/operator-notes.txt"]
    assert m["capture_failures"] == []
    package = Path(m["destination"]["package"])
    summary = (package / "SUMMARY.md").read_text(encoding="utf-8")
    assert "| Instrumentation validity | **valid** |" in summary
    assert "| Console capture | **complete**" in summary
    assert "## Files in console/ this export did not write" in summary
    assert "`console/operator-notes.txt`: 14 byte(s)" in summary
    assert (package / "console" / "operator-notes.txt").is_file()  # listed as what it is, and still copied
    assert "| valid | pass |" in (dest / "INDEX.md").read_text(encoding="utf-8")


def test_an_interrupted_only_command_never_reads_as_not_applicable(roots):
    attempts, dest, _env = roots
    a = _attempt(attempts, dest)
    (a / "console" / "001-measured-window.stdout.txt").write_bytes(b"80 of the 230 bytes\n")
    le.finish_attempt(a, "interrupted", instrumentation_validity="valid", system_outcome="interrupted")
    attempt = json.loads((a / "attempt.json").read_text())
    assert attempt["instrumentation_validity"] == "invalid"  # unaccounted output is not valid evidence
    summary = (Path(le.export_attempt(a, dest)["destination"]["package"]) / "SUMMARY.md").read_text(encoding="utf-8")
    assert "not applicable" not in summary
    assert "| Console capture | **INCOMPLETE**" in summary


def test_a_console_file_of_a_running_attempt_is_not_yet_unaccounted_for(roots):
    """While the attempt runs, a console file with no record is a command in flight."""
    attempts, dest, _env = roots
    a = _attempt(attempts, dest)
    (a / "console" / "001-in-flight.stdout.txt").write_bytes(b"still being written\n")
    le.update_attempt(a, {"instrumentation_validity": "valid"})
    assert json.loads((a / "attempt.json").read_text())["instrumentation_validity"] == "valid"
    assert json.loads((a / "attempt.json").read_text())["capture_failures"] == []


def test_the_bytes_the_disk_accepted_before_failing_are_counted(roots, failing_console):
    """0 of 72000 kept would send a reader past a console file that does hold evidence."""
    attempts, dest, _env = roots
    a = _attempt(attempts, dest)
    failing_console(limit=4096, mode="partial")
    rec = le.run_command_record(
        a, "probe", [sys.executable, "-u", "-c", "import sys; sys.stdout.buffer.write(b'y' * 65536)"], echo=False)
    out = rec["capture"]["stdout"]
    kept_on_disk = (a / rec["stdout"]).stat().st_size
    assert out["state"] == "failed" and out["bytes_received"] == 65536
    assert out["bytes_kept"] == kept_on_disk == 4096
    failure = json.loads((a / "attempt.json").read_text())["capture_failures"][0]
    assert failure["bytes_kept"] == 4096
    le.finish_attempt(a, "finished")
    summary = (Path(le.export_attempt(a, dest)["destination"]["package"]) / "SUMMARY.md").read_text(encoding="utf-8")
    assert "4096 of 65536 bytes kept" in summary


def test_bytes_lost_at_the_close_are_not_counted_as_kept(roots, failing_console):
    """The mirror case: 'all of it kept' for a file that holds none of it."""
    attempts, dest, _env = roots
    a = _attempt(attempts, dest)
    failing_console(mode="lose-at-close")
    rec = le.run_command_record(a, "probe", [sys.executable, "-c", "print('buffered and lost')"], echo=False)
    out = rec["capture"]["stdout"]
    assert out["state"] == "failed" and out["error"].startswith("close:")
    assert out["bytes_received"] > 0
    assert out["bytes_kept"] == (a / rec["stdout"]).stat().st_size == 0


@pytest.mark.skipif(os.name == "nt", reason="POSIX signals: wait() returns -N for a killed child")
def test_a_child_killed_by_a_signal_exits_128_plus_the_signal(roots, capsys):
    attempts, dest, env = roots
    a = _attempt(attempts, dest)
    code = le.main(["exec", "--attempt", str(a), "--name", "killed child", "--secrets-env", str(env), "--",
                    sys.executable, "-u", "-c",
                    "import os, signal, sys; print('before the signal'); sys.stdout.flush(); "
                    "os.kill(os.getpid(), signal.SIGTERM)"])
    assert code == 128 + 15  # a status a caller can read, not 256 - 15
    assert "killed by SIGTERM" in capsys.readouterr().err
    rec = json.loads((a / "commands.jsonl").read_text().splitlines()[-1])
    assert rec["exit_code"] == -15 and rec["killed_by_signal"] == 15  # the raw value is kept
    assert rec["capture"]["stdout"]["state"] == "complete"  # the capture itself was fine
    le.finish_attempt(a, "failed", instrumentation_validity="valid", system_outcome="fail")
    summary = (Path(le.export_attempt(a, dest)["destination"]["package"]) / "SUMMARY.md").read_text(encoding="utf-8")
    assert "-15 (killed by SIGTERM)" in summary


def test_a_pipe_that_cannot_be_read_is_a_capture_failure(tmp_path):
    """The child's output stopped reaching the console file: that is evidence lost, not silence."""
    class _BrokenPipe:
        def __init__(self) -> None:
            self.calls = 0

        def read1(self, size: int) -> bytes:
            self.calls += 1
            if self.calls == 1:
                return b"first chunk kept\n"
            raise OSError(errno.EIO, "Input/output error")

    capture = le._Capture("stdout")
    sink = open(tmp_path / "console.txt", "xb")
    le._tee(_BrokenPipe(), sink, None, capture)  # never a traceback out of the thread
    capture.close(sink, tmp_path / "console.txt")
    record = capture.record()
    assert record["state"] == "failed" and record["error"].startswith("read:")
    assert "Input/output error" in record["error"]
    assert capture.failure(1, "probe", "console/001-probe.stdout.txt")["error"].startswith("read:")


# --------------------------------------------------------------------------
# F1 — no owned path may be redirected outside the chosen destination root
# --------------------------------------------------------------------------


@needs_symlinks
@pytest.mark.parametrize("linked", ["incomplete", "runs"])
def test_a_linked_top_level_folder_is_refused_before_anything_is_created(roots, outside, linked):
    attempts, dest, _env = roots
    a = _attempt(attempts, dest)
    le.finish_attempt(a, "finished")
    dest.mkdir(parents=True)
    (dest / linked).symlink_to(outside / "kept", target_is_directory=True)
    before = _tree(outside)
    with pytest.raises(le.UnsafePathError, match="it is a symlink"):
        le.export_attempt(a, dest)
    assert _tree(outside) == before
    assert sorted(p.name for p in dest.iterdir()) == [linked]


@needs_symlinks
def test_a_linked_staging_folder_is_refused(roots, outside):
    attempts, dest, _env = roots
    a = _attempt(attempts, dest)
    le.finish_attempt(a, "finished")
    (dest / "incomplete").mkdir(parents=True)
    (dest / "incomplete" / a.name).symlink_to(outside / "kept", target_is_directory=True)
    before = _tree(outside)
    with pytest.raises(le.UnsafePathError, match="it is a symlink"):
        le.export_attempt(a, dest)
    assert _tree(outside) == before
    assert not (dest / "runs").exists()


@needs_symlinks
def test_a_linked_folder_inside_a_resumed_staging_folder_is_never_written_through(roots, outside):
    attempts, dest, _env = roots
    a = _attempt(attempts, dest)
    le.run_command(a, "probe", [sys.executable, "-c", "print('console output')"], echo=False)
    le.finish_attempt(a, "finished")
    staging = dest / "incomplete" / a.name
    staging.mkdir(parents=True)
    (staging / "console").symlink_to(outside / "kept", target_is_directory=True)
    before = _tree(outside)
    with pytest.raises(le.UnsafePathError, match="it is a symlink"):
        le.export_attempt(a, dest)
    assert _tree(outside) == before  # the console files did not land in someone else's folder
    assert not (dest / "runs").exists()


@needs_symlinks
@pytest.mark.parametrize("leaf", ["export_manifest.json", "SUMMARY.md", "SHA256SUMS"])
def test_a_linked_file_inside_staging_is_never_written_through(roots, outside, leaf):
    attempts, dest, _env = roots
    a = _attempt(attempts, dest)
    (a / "analysis" / "table.csv").write_text("1\n")
    le.finish_attempt(a, "finished")
    staging = dest / "incomplete" / a.name
    staging.mkdir(parents=True)
    (staging / leaf).symlink_to(outside / "kept" / "sentinel.txt")
    before = _tree(outside)
    with pytest.raises(le.UnsafePathError, match="foreign"):
        le.export_attempt(a, dest)
    assert _tree(outside) == before
    assert not (dest / "runs").exists()


@needs_symlinks
def test_a_linked_final_date_folder_is_refused(roots, outside):
    attempts, dest, _env = roots
    a = _attempt(attempts, dest)
    le.finish_attempt(a, "finished")
    (dest / "runs").mkdir(parents=True)
    (dest / "runs" / le.run_date(a.name)).symlink_to(outside / "kept", target_is_directory=True)
    before = _tree(outside)
    with pytest.raises(le.UnsafePathError, match="it is a symlink"):
        le.export_attempt(a, dest)
    assert _tree(outside) == before
    assert not (dest / "incomplete").exists()


@needs_symlinks
@pytest.mark.parametrize("name", ["INDEX.md", "LATEST_SUMMARY.md", "README.md"])
def test_a_linked_index_file_is_never_written_through(roots, outside, name):
    attempts, dest, _env = roots
    a = _attempt(attempts, dest)
    le.finish_attempt(a, "finished")
    dest.mkdir(parents=True)
    (dest / name).symlink_to(outside / "kept" / "sentinel.txt")
    before = _tree(outside)
    with pytest.raises(le.UnsafePathError, match="it is a symlink"):
        le.export_attempt(a, dest)
    with pytest.raises(le.UnsafePathError, match="it is a symlink"):
        le.rebuild_index(dest)
    assert _tree(outside) == before


@needs_symlinks
def test_recover_goes_on_after_a_refused_path(roots, outside):
    attempts, dest, _env = roots
    bad = _attempt(attempts, dest)
    le.finish_attempt(bad, "finished")
    good = _attempt(attempts, dest, scenario="other")
    le.finish_attempt(good, "finished")
    (dest / "incomplete").mkdir(parents=True)
    (dest / "incomplete" / bad.name).symlink_to(outside / "kept", target_is_directory=True)
    before = _tree(outside)
    results = {r["run_id"]: r["result"] for r in le.recover(attempts, dest)}
    assert results[bad.name].startswith("export failed") and "refusing to use" in results[bad.name]
    assert results[good.name] == "exported"
    assert _tree(outside) == before
    assert (next((dest / "runs").rglob(good.name)) / "SUMMARY.md").is_file()


@needs_symlinks
def test_a_destination_root_that_is_a_link_writes_physically_inside_its_target(roots, tmp_path):
    attempts, _dest, _env = roots
    real = tmp_path / "real output_test"
    real.mkdir()
    link = tmp_path / "dest-link"
    link.symlink_to(real, target_is_directory=True)
    a = le.new_attempt(attempts, "nominal", "engineering")
    le.finish_attempt(a, "finished", instrumentation_validity="valid", system_outcome="pass")
    m = le.export_attempt(a, link)
    physical = Path(os.path.realpath(real))
    package = Path(m["destination"]["package"])
    assert package.is_relative_to(physical) and (package / "SUMMARY.md").is_file()
    assert (physical / "INDEX.md").is_file() and verify_sha256sums(package) == []


@needs_symlinks
def test_a_linked_package_folder_is_listed_as_refused_and_never_read(roots, outside):
    attempts, dest, _env = roots
    a = _attempt(attempts, dest)
    le.finish_attempt(a, "finished")
    le.export_attempt(a, dest)
    (outside / "kept" / "attempt.json").write_text('{"run_id": "not mine", "scenario": "foreign"}')
    (next((dest / "runs").iterdir()) / "20260919T000000Z_foreign_attempt99").symlink_to(
        outside / "kept", target_is_directory=True)
    (dest / "incomplete").mkdir(exist_ok=True)
    (dest / "incomplete" / "20260919T000000Z_foreign_attempt98").symlink_to(
        outside / "kept", target_is_directory=True)
    before = _tree(outside)
    le.rebuild_index(dest)
    index = (dest / "INDEX.md").read_text(encoding="utf-8")
    assert index.count("REFUSED: link") == 2
    assert "foreign_attempt99" in index and "foreign_attempt98" in index
    assert "foreign" not in index.replace("foreign_attempt99", "").replace("foreign_attempt98", "")
    assert a.name in index  # the real package is still listed
    assert _tree(outside) == before


# --------------------------------------------------------------------------
# F1 — a hard link is a second name for the same bytes, not a path to follow
# --------------------------------------------------------------------------


@pytest.mark.parametrize("name", ["INDEX.md", "LATEST_SUMMARY.md", "README.md"])
def test_a_hard_linked_index_file_is_refused_and_the_other_name_survives(roots, outside, name):
    attempts, dest, _env = roots
    a = _attempt(attempts, dest)
    le.finish_attempt(a, "finished")
    dest.mkdir(parents=True)
    victim = outside / "kept" / "sentinel.txt"
    os.link(victim, dest / name)  # no privilege needed, on NTFS or on ext4
    assert not le._link_like(dest / name) and os.lstat(dest / name).st_nlink == 2
    before = _tree(outside)
    with pytest.raises(le.UnsafePathError, match="hard link"):
        le.export_attempt(a, dest)
    with pytest.raises(le.UnsafePathError, match="hard link"):
        le.rebuild_index(dest)
    assert _tree(outside) == before  # the other name still holds its own bytes
    assert not (dest / "runs").exists()


@pytest.mark.parametrize("leaf", ["SUMMARY.md", "SHA256SUMS", "export_manifest.json"])
def test_a_hard_linked_leaf_in_staging_is_never_written_through(roots, outside, leaf):
    attempts, dest, _env = roots
    a = _attempt(attempts, dest)
    (a / "analysis" / "table.csv").write_text("1\n")
    le.finish_attempt(a, "finished")
    staging = dest / "incomplete" / a.name
    staging.mkdir(parents=True)
    os.link(outside / "kept" / "sentinel.txt", staging / leaf)
    before = _tree(outside)
    # The refusal states what the link count measured — a second name exists —
    # and not where that name is, which nothing here looked up.
    with pytest.raises(le.UnsafePathError, match="this file has 2 names") as excinfo:
        le.export_attempt(a, dest)
    assert "outside" not in str(excinfo.value)
    assert _tree(outside) == before
    assert not (dest / "runs").exists()  # the package was never sealed around the foreign inode
    assert os.lstat(outside / "kept" / "sentinel.txt").st_nlink == 2  # still the export's refusal, not a copy


def test_a_hard_linked_copy_destination_is_refused_before_the_bytes_are_written(roots, outside):
    """The staging path of a copied file is owned too, and so is its `.partial`."""
    attempts, dest, _env = roots
    a = _attempt(attempts, dest)
    (a / "analysis" / "table.csv").write_text("a,b\n1,2\n")
    le.finish_attempt(a, "finished")
    staging = dest / "incomplete" / a.name
    (staging / "analysis").mkdir(parents=True)
    os.link(outside / "kept" / "sentinel.txt", staging / "analysis" / "table.csv.partial")
    before = _tree(outside)
    with pytest.raises(le.UnsafePathError, match="hard link"):
        le.export_attempt(a, dest)
    assert _tree(outside) == before


@needs_symlinks
def test_a_link_planted_in_a_finalised_package_is_refused_and_listed(roots, outside):
    attempts, dest, _env = roots
    a = _attempt(attempts, dest)
    le.finish_attempt(a, "finished", instrumentation_validity="valid", system_outcome="pass")
    package = Path(le.export_attempt(a, dest)["destination"]["package"])
    (package / "console").symlink_to(outside / "kept", target_is_directory=True)
    # verify_sha256sums sees a linked directory as neither a file nor a
    # problem, so the seal alone would still say the package is intact.
    assert verify_sha256sums(package) == []

    with pytest.raises(le.UnsafePathError, match="foreign"):
        le.export_attempt(a, dest)
    le.rebuild_index(dest)
    index = (dest / "INDEX.md").read_text(encoding="utf-8")
    assert "REFUSED: link" in index
    assert _tree(outside) == {"kept": None, "kept/sentinel.txt": b"sentinel\n"}


@needs_symlinks
@pytest.mark.parametrize("name", ["attempt.json", "export_manifest.json"])
def test_a_linked_verdict_file_in_a_package_is_never_read_into_the_index(roots, outside, name):
    attempts, dest, _env = roots
    a = _attempt(attempts, dest)
    le.finish_attempt(a, "finished", instrumentation_validity="valid", system_outcome="pass")
    package = Path(le.export_attempt(a, dest)["destination"]["package"])
    (outside / "kept" / "foreign.json").write_text(
        '{"run_id": "leaked-from-outside", "scenario": "leaked-from-outside", '
        '"instrumentation_validity": "valid", "copy_verification": "verified"}', encoding="utf-8")
    (package / name).unlink()
    (package / name).symlink_to(outside / "kept" / "foreign.json")

    le.rebuild_index(dest)
    index = (dest / "INDEX.md").read_text(encoding="utf-8")
    assert "leaked-from-outside" not in index  # no verdict is read from outside the root
    assert "REFUSED: link" in index and a.name in index


def test_an_index_failure_after_finalisation_never_undoes_a_sealed_package(roots, monkeypatch):
    attempts, dest, _env = roots
    a = _attempt(attempts, dest)
    (a / "analysis" / "table.csv").write_text("a,b\n")
    le.finish_attempt(a, "finished", instrumentation_validity="valid", system_outcome="pass")
    real = le.rebuild_index
    calls = {"n": 0}

    def flaky(dest_root):
        calls["n"] += 1
        if calls["n"] == 1:
            raise OSError(errno.ENOSPC, "No space left on device")
        return real(dest_root)

    monkeypatch.setattr(le, "rebuild_index", flaky)
    m = le.export_attempt(a, dest)  # the package is finished; only the index is not
    package = Path(m["destination"]["package"])
    assert verify_sha256sums(package) == [] and m["copy_verification"] == "verified"
    assert "INDEX.md could not be rebuilt" in m["index_note"]
    receipt = json.loads((a / "export" / "receipt.json").read_text())
    assert receipt["state"] == "complete" and receipt["package"] == str(package)

    # and the next run heals the index without re-exporting anything
    monkeypatch.setattr(le, "rebuild_index", real)
    assert le.recover(attempts, dest) == []  # the complete receipt means nothing is left to do
    le.rebuild_index(dest)
    assert a.name in (dest / "INDEX.md").read_text(encoding="utf-8")


def test_a_second_export_of_a_verified_package_writes_the_complete_receipt(roots):
    attempts, dest, _env = roots
    a = _attempt(attempts, dest)
    le.finish_attempt(a, "finished")
    le.export_attempt(a, dest)
    (a / "export" / "receipt.json").write_text('{"state": "failed", "package": "gone"}', encoding="utf-8")
    m = le.export_attempt(a, dest)
    assert m["note"].startswith("already exported")
    assert json.loads((a / "export" / "receipt.json").read_text())["state"] == "complete"


def test_recover_reports_a_failure_instead_of_exiting_zero(roots, capsys):
    """`recover` is the documented remedy for a failed export: it cannot fail silently."""
    attempts, dest, env = roots
    a = _attempt(attempts, dest)
    le.finish_attempt(a, "finished")
    run_id = json.loads((a / "attempt.json").read_text())["run_id"]
    final = dest / "runs" / le.run_date(run_id) / run_id
    final.mkdir(parents=True)
    (final / "junk.txt").write_text("not this attempt's package\n")  # exists and does not verify

    code = le.main(["recover", "--attempts-root", str(attempts), "--dest-root", str(dest),
                    "--secrets-env", str(env)])
    out = capsys.readouterr()
    assert code == 2
    assert "export failed" in out.out and "were not exported" in out.err
    assert not (final / "SUMMARY.md").exists()


def test_recover_exits_zero_when_it_only_left_a_running_attempt_alone(roots, capsys):
    attempts, dest, env = roots
    _attempt(attempts, dest)  # still running: driven from another terminal
    assert le.main(["recover", "--attempts-root", str(attempts), "--dest-root", str(dest),
                    "--secrets-env", str(env)]) == 0
    assert "running: not touched" in capsys.readouterr().out


# --------------------------------------------------------------------------
# F4 — a registered source root that is itself a link
# --------------------------------------------------------------------------


@needs_symlinks
def test_a_linked_source_root_keeps_its_identity_and_is_never_read(roots, tmp_path):
    attempts, dest, _env = roots
    hidden = tmp_path / "hidden"
    hidden.mkdir()
    (hidden / "notes.txt").write_text(DISTINCTIVE + "\n")
    link = tmp_path / "capsule-link"
    link.symlink_to(hidden, target_is_directory=True)
    a = _attempt(attempts, dest)
    le.add_source(a, "raw", link, role="harness capsule")
    le.finish_attempt(a, "finished")
    recorded = json.loads((a / "sources.json").read_text())["sources"][0]["path"]
    assert Path(recorded).name == "capsule-link" and le._link_like(recorded)

    m = le.export_attempt(a, dest)
    package = Path(m["destination"]["package"])
    assert {s["package_path"]: s["type"] for s in m["skipped_special"]}["raw/capsule-link"] == "symlink"
    assert m["missing_sources"] == []
    assert not (package / "raw").exists()
    assert DISTINCTIVE.encode() not in _all_bytes(package)
    assert "never read" in (package / "SUMMARY.md").read_text(encoding="utf-8")


@needs_symlinks
def test_a_source_link_to_a_file_and_a_dangling_one_are_listed_not_read(roots, tmp_path):
    attempts, dest, _env = roots
    (tmp_path / "hidden.txt").write_text(DISTINCTIVE + "\n")
    (tmp_path / "file-link").symlink_to(tmp_path / "hidden.txt")
    (tmp_path / "dangling-link").symlink_to(tmp_path / "never-written")
    a = _attempt(attempts, dest)
    le.add_source(a, "raw", tmp_path / "file-link")
    le.add_source(a, "other", tmp_path / "dangling-link")
    le.finish_attempt(a, "finished")
    m = le.export_attempt(a, dest)
    types = {s["package_path"]: s["type"] for s in m["skipped_special"]}
    assert types["raw/file-link"] == "symlink" and types["other/dangling-link"] == "symlink"
    # A link that resolves to nothing is both: a link, listed and never read,
    # and an artefact that is not there, so the package may not claim that
    # nothing was missing.
    assert [m_["path"] for m_ in m["missing_sources"]] == [str(tmp_path / "dangling-link")]
    assert "resolves to nothing" in m["missing_sources"][0]["note"]
    assert {s["package_path"] for s in m["skipped_source_roots"]} == {"raw/file-link", "other/dangling-link"}
    summary = (Path(m["destination"]["package"]) / "SUMMARY.md").read_text(encoding="utf-8")
    assert "resolves to nothing" in summary
    assert "2 registered source root(s) skipped and NOT in this package" in summary
    assert DISTINCTIVE.encode() not in _all_bytes(Path(m["destination"]["package"]))


def test_a_skipped_source_root_is_visible_where_the_verdicts_are_read(roots, tmp_path):
    """A capsule that was not copied must be named beside the copy verdict, not only far below it."""
    hidden = tmp_path / "hidden"
    hidden.mkdir()
    (hidden / "events.jsonl").write_text(DISTINCTIVE + "\n")
    attempts, dest, _env = roots
    a = _attempt(attempts, dest)
    link = tmp_path / "capsule-link"
    _link_to_dir(hidden, link)
    le.add_source(a, "raw", link, role="harness raw run directory")
    le.finish_attempt(a, "finished", instrumentation_validity="valid", system_outcome="pass")

    m = le.export_attempt(a, dest)
    package = Path(m["destination"]["package"])
    assert [s["package_path"] for s in m["skipped_source_roots"]] == ["raw/capsule-link"]
    assert DISTINCTIVE.encode() not in _all_bytes(package)
    summary = (package / "SUMMARY.md").read_text(encoding="utf-8")
    copy_line = next(ln for ln in summary.splitlines() if ln.startswith("| Copy verification |"))
    assert "1 registered source root(s) skipped and NOT in this package: `raw/capsule-link`" in copy_line
    assert "1 source root(s) skipped" in (dest / "INDEX.md").read_text(encoding="utf-8")


@pytest.mark.parametrize("tail", [os.path.join("sub", ".."), os.path.join("sub", "."), ".."])
def test_a_source_path_with_a_dot_component_is_refused(roots, tmp_path, tail):
    """`..` survives Path.absolute(), and lstat then resolves the link chain it hides."""
    attempts, dest, _env = roots
    (tmp_path / "capsule" / "sub").mkdir(parents=True)
    (tmp_path / "capsule" / "notes.txt").write_text(DISTINCTIVE + "\n")
    # Built as a string: pathlib drops a '.' component, so the spelling given
    # on the command line is what must be judged.
    given = os.path.join(str(tmp_path / "capsule"), tail)
    a = _attempt(attempts, dest)
    with pytest.raises(ValueError, match=r"'\.' or '\.\.' component"):
        le.add_source(a, "raw", given)
    assert json.loads((a / "sources.json").read_text())["sources"] == []
    with pytest.raises(ValueError, match=r"'\.' or '\.\.' component"):
        le.backfill(given, attempts, dest, name="dotted", scenario="x",
                    date="2026-09-19", note="a path with a relative component")
    assert not (attempts / "_historical").exists()
    assert not (dest / "runs").exists()


@needs_symlinks
def test_backfill_refuses_a_linked_historical_source(roots, tmp_path):
    attempts, dest, _env = roots
    raw = _raw_capsule(tmp_path / "old", "controller_restart-r02")
    link = tmp_path / "capsule-link"
    link.symlink_to(raw, target_is_directory=True)
    with pytest.raises(le.ExportError, match="listed and never read") as excinfo:
        le.backfill(link, attempts, dest, name="linked", scenario="controller restart", date="2026-09-19",
                    note="a link instead of the capsule")
    assert os.path.realpath(link) in str(excinfo.value)  # the physical path to use instead
    assert not (attempts / "_historical").exists()
    assert not (dest / "runs").exists()


# --------------------------------------------------------------------------
# Third round: the corrections above, taken from the side they did not cover
# --------------------------------------------------------------------------


needs_real_permissions = pytest.mark.skipif(
    os.name == "nt" or (hasattr(os, "geteuid") and os.geteuid() == 0),
    reason="POSIX directory permissions, which root ignores")


def _finished(attempts: Path, dest: Path, **verdicts) -> Path:
    a = _attempt(attempts, dest)
    (a / "analysis" / "table.csv").write_text("a,b\n1,2\n", encoding="utf-8")
    le.finish_attempt(a, "finished", **({"instrumentation_validity": "valid",
                                         "system_outcome": "pass"} | verdicts))
    return a


@needs_symlinks
def test_a_capsule_reached_through_a_linked_parent_is_never_read(roots, tmp_path):
    """`nominal.sh` registers the raw directory before the harness creates it."""
    attempts, dest, _env = roots
    elsewhere = tmp_path / "another-disk" / "raw"
    (elsewhere / "nominal-r01").mkdir(parents=True)
    (elsewhere / "nominal-r01" / "events.jsonl").write_text(DISTINCTIVE + "\n", encoding="utf-8")
    pilot = tmp_path / "pilot"
    (pilot / "results").mkdir(parents=True)
    a = _attempt(attempts, dest)
    # results/raw does not exist yet, so the parent cannot be made physical at
    # registration; it becomes a link to another disk afterwards.
    le.add_source(a, "raw", pilot / "results" / "raw" / "nominal-r01", role="harness raw run directory")
    (pilot / "results" / "raw").symlink_to(elsewhere, target_is_directory=True)
    le.finish_attempt(a, "finished", instrumentation_validity="valid", system_outcome="pass")

    m = le.export_attempt(a, dest)
    package = Path(m["destination"]["package"])
    assert [s["package_path"] for s in m["skipped_source_roots"]] == ["raw/nominal-r01"]
    assert "reached through a symlink" in m["skipped_source_roots"][0]["type"]
    assert str(pilot / "results" / "raw") in m["skipped_source_roots"][0]["type"]  # the offending component
    assert [f for f in m["files"] if f["package_path"].startswith("raw/")] == []
    assert DISTINCTIVE.encode() not in _all_bytes(package)
    assert not (package / "raw").exists()


@needs_symlinks
def test_a_capsule_below_a_link_that_already_existed_is_recorded_physically(roots, tmp_path):
    """The same run must not get two provenances depending on when add-source ran."""
    attempts, dest, _env = roots
    elsewhere = tmp_path / "another-disk" / "egw-results"
    elsewhere.mkdir(parents=True)
    pilot = tmp_path / "pilot"
    pilot.mkdir()
    (pilot / "results").symlink_to(elsewhere, target_is_directory=True)
    a = _attempt(attempts, dest)
    # results/ is a link and results/raw/ does not exist yet: the parent is
    # made physical as far as the filesystem knows it, not left to lstat.
    le.add_source(a, "raw", pilot / "results" / "raw" / "nominal-r01", role="harness raw run directory")
    recorded = json.loads((a / "sources.json").read_text())["sources"][0]["path"]
    assert recorded == str(elsewhere / "raw" / "nominal-r01")

    (elsewhere / "raw" / "nominal-r01").mkdir(parents=True)
    (elsewhere / "raw" / "nominal-r01" / "events.jsonl").write_text(DISTINCTIVE + "\n", encoding="utf-8")
    le.finish_attempt(a, "finished", instrumentation_validity="valid", system_outcome="pass")
    m = le.export_attempt(a, dest)
    assert m["skipped_source_roots"] == [] and m["copy_verification"] == "verified"
    assert [f["source"] for f in m["files"] if f["package_path"].startswith("raw/")] == [
        str(elsewhere / "raw" / "nominal-r01" / "events.jsonl")]


@needs_symlinks
def test_a_sources_json_that_already_holds_a_dot_component_is_refused_on_the_read_side(roots, tmp_path):
    """An attempt registered before the write-side rule existed must not be read through."""
    attempts, dest, _env = roots
    hidden = tmp_path / "hidden"
    (hidden / "sub").mkdir(parents=True)
    (hidden / "notes.txt").write_text(DISTINCTIVE + "\n", encoding="utf-8")
    link = tmp_path / "capsule-link"
    link.symlink_to(hidden, target_is_directory=True)
    a = _finished(attempts, dest)
    # Written exactly as the pre-fix add_source would have left it.
    (a / "sources.json").write_text(json.dumps({"sources": [
        {"kind": "raw", "path": os.path.join(str(link), "sub", ".."), "siblings_glob": None,
         "role": "harness capsule", "added_utc": le.utc_now()}]}), encoding="utf-8")

    m = le.export_attempt(a, dest)
    package = Path(m["destination"]["package"])
    assert [s["package_path"] for s in m["skipped_source_roots"]] == ["raw/.."]
    assert "'.' or '..' component" in m["skipped_source_roots"][0]["type"]
    assert [f["package_path"] for f in m["files"] if f["package_path"].startswith("raw/")] == []
    assert DISTINCTIVE.encode() not in _all_bytes(package)


@needs_symlinks
def test_a_registered_artefact_below_the_root_is_counted_where_the_verdicts_are_read(roots, tmp_path):
    """The file a slice's verdict came from is not in the package: the verdicts must say so."""
    attempts, dest, _env = roots
    (tmp_path / "elsewhere").mkdir()
    (tmp_path / "elsewhere" / "events.jsonl").write_text(DISTINCTIVE + "\n", encoding="utf-8")
    (tmp_path / "elsewhere" / "reconcile.json").write_text(DISTINCTIVE + "\n", encoding="utf-8")
    itest = tmp_path / "itest"
    (itest / "slice-r01").mkdir(parents=True)
    (itest / "slice-r01" / "sent_events.jsonl").write_text("{}\n", encoding="utf-8")
    (itest / "slice-r01" / "events.jsonl").symlink_to(tmp_path / "elsewhere" / "events.jsonl")
    (itest / "slice-r01.reconcile.json").symlink_to(tmp_path / "elsewhere" / "reconcile.json")
    a = _attempt(attempts, dest)
    le.add_source(a, "simulator", itest / "slice-r01", siblings_glob="slice-r01.*")
    le.update_attempt(a, {"expected_artefacts": ["simulator/*.reconcile.json", "simulator/*/events.jsonl"]})
    le.finish_attempt(a, "finished", instrumentation_validity="valid", system_outcome="pass")

    m = le.export_attempt(a, dest)
    assert m["skipped_source_roots"] == []  # the root itself was real: the old accounting saw nothing
    assert sorted(s["package_path"] for s in m["skipped_registered_artefacts"]) == [
        "simulator/slice-r01.reconcile.json", "simulator/slice-r01/events.jsonl"]
    assert sorted(m["expected_artefacts_missing"]) == ["simulator/*.reconcile.json", "simulator/*/events.jsonl"]
    assert m["copy_verification"] == "verified; incomplete"
    summary = (Path(m["destination"]["package"]) / "SUMMARY.md").read_text(encoding="utf-8")
    copy_line = next(ln for ln in summary.splitlines() if ln.startswith("| Copy verification |"))
    assert "2 registered artefact(s) below a source root NOT in this package" in copy_line
    assert "2 declared expected artefact(s) matched nothing that was copied" in copy_line
    index = (dest / "INDEX.md").read_text(encoding="utf-8")
    assert "2 registered artefact(s) not copied; 2 expected artefact(s) missing" in index
    assert DISTINCTIVE.encode() not in _all_bytes(Path(m["destination"]["package"]))


def test_a_package_sealed_without_its_capsule_is_not_plainly_verified(roots, tmp_path, capsys):
    """One field is all some readers of an export have: it cannot say 'verified' alone."""
    attempts, dest, env = roots
    hidden = tmp_path / "hidden"
    hidden.mkdir()
    (hidden / "events.jsonl").write_text(DISTINCTIVE + "\n", encoding="utf-8")
    link = tmp_path / "capsule-link"
    _link_to_dir(hidden, link)
    a = _attempt(attempts, dest)
    le.add_source(a, "raw", link, role="harness raw run directory")
    le.finish_attempt(a, "finished", instrumentation_validity="valid", system_outcome="pass")

    assert le.main(["export", "--attempt", str(a), "--dest-root", str(dest), "--secrets-env", str(env)]) == 0
    out = capsys.readouterr().out
    assert "(verified; incomplete, " in out and "1 source root(s) skipped" in out
    package = dest / "runs" / le.run_date(a.name) / a.name
    m = json.loads((package / "export_manifest.json").read_text(encoding="utf-8"))
    assert m["copy_verification"] == "verified; incomplete"
    assert m["package_completeness"].startswith("incomplete: 1 registered source root(s)")
    receipt = json.loads((a / "export" / "receipt.json").read_text(encoding="utf-8"))
    assert receipt["state"] == "complete" and receipt["copy_verification"] == "verified; incomplete"
    assert DISTINCTIVE.encode() not in _all_bytes(package)


@pytest.mark.parametrize("how", ["truncated", "removed"])
def test_a_console_file_that_no_longer_holds_what_its_record_claims_is_a_capture_failure(roots, how):
    """Hashing a truncated file does not make the missing output come back."""
    attempts, dest, _env = roots
    a = _attempt(attempts, dest)
    code = le.run_command(a, "measured window", [sys.executable, "-c", "print('the measured evidence ' * 40)"],
                          echo=False)
    assert code == 0
    console = a / "console" / "001-measured-window.stdout.txt"
    kept = console.stat().st_size
    assert kept > 100
    if how == "truncated":
        with open(console, "r+b") as fh:
            fh.truncate(3)
    else:
        console.unlink()
    le.finish_attempt(a, "finished", instrumentation_validity="valid", system_outcome="pass")

    attempt = json.loads((a / "attempt.json").read_text(encoding="utf-8"))
    assert attempt["instrumentation_validity"] == "invalid"
    failure = next(f for f in attempt["capture_failures"] if f["stream"] == "stdout")
    assert failure["console"] == "console/001-measured-window.stdout.txt"
    assert (f"holds 3 byte(s); the record says {kept} were kept" in failure["error"] if how == "truncated"
            else "no longer in the attempt" in failure["error"])

    m = le.export_attempt(a, dest)
    summary = (Path(m["destination"]["package"]) / "SUMMARY.md").read_text(encoding="utf-8")
    assert "| Instrumentation validity | **invalid** |" in summary
    assert "| Console capture | **INCOMPLETE** — 1 console stream(s) were not kept in full" in summary
    assert [f["console"] for f in m["capture_failures"]] == ["console/001-measured-window.stdout.txt"]
    if how == "removed":
        assert "[stdout](console/001-measured-window.stdout.txt)" not in summary
        assert "stdout: not in this package" in summary


@needs_real_permissions
def test_a_console_directory_that_cannot_be_listed_is_never_a_complete_capture(roots):
    """A source of the verdict that goes silent has to say so, not read as silence."""
    attempts, dest, _env = roots
    a = _attempt(attempts, dest)
    le.run_command(a, "first", [sys.executable, "-c", "print('out')"], echo=False)
    os.chmod(a / "console", 0o300)
    try:
        le.finish_attempt(a, "finished", instrumentation_validity="valid", system_outcome="pass")
        attempt = json.loads((a / "attempt.json").read_text(encoding="utf-8"))
        assert attempt["instrumentation_validity"] == "invalid"
        assert any(f.get("unreadable") and f["console"] == "console" for f in attempt["capture_failures"])
        m = le.export_attempt(a, dest)
    finally:
        os.chmod(a / "console", 0o700)
    package = Path(m["destination"]["package"])
    assert not (package / "console").exists()  # not one console file reached the package
    summary = (package / "SUMMARY.md").read_text(encoding="utf-8")
    assert "| Instrumentation validity | **invalid** |" in summary
    assert "| Console capture | **INCOMPLETE**" in summary
    assert "the console directory could not be listed" in summary
    assert "| invalid | pass |" in (dest / "INDEX.md").read_text(encoding="utf-8")


def test_the_export_brings_the_attempt_to_its_own_capture_verdict_before_packaging(roots):
    """A package may not carry a verdict the page it sits on contradicts."""
    attempts, dest, _env = roots
    a = _attempt(attempts, dest)
    le.run_command(a, "first", [sys.executable, "-c", "print('out')"], echo=False)
    (a / "console" / "002-ghost.stdout.txt").write_bytes(b"22 bytes of evidence!\n")
    # An attempt.json written by something other than update_attempt: a driver,
    # a recovery by hand, an attempt closed by an older tool.
    data = json.loads((a / "attempt.json").read_text(encoding="utf-8"))
    data.update({"status": "finished", "ended_utc": le.utc_now(), "instrumentation_validity": "valid",
                 "system_outcome": "pass", "capture_failures": []})
    (a / "attempt.json").write_text(json.dumps(data), encoding="utf-8")

    m = le.export_attempt(a, dest)
    package = Path(m["destination"]["package"])
    packaged = json.loads((package / "attempt.json").read_text(encoding="utf-8"))
    assert packaged["instrumentation_validity"] == "invalid"
    assert [f["console"] for f in packaged["capture_failures"]] == ["console/002-ghost.stdout.txt"]
    assert "downgraded from 'valid'" in packaged["validity_note"]
    summary = (package / "SUMMARY.md").read_text(encoding="utf-8")
    assert "| Instrumentation validity | **invalid** |" in summary
    assert "| Console capture | **INCOMPLETE**" in summary
    assert "| invalid | pass |" in (dest / "INDEX.md").read_text(encoding="utf-8")
    # and the attempt on the WSL side now holds the same verdict
    assert json.loads((a / "attempt.json").read_text(encoding="utf-8"))["instrumentation_validity"] == "invalid"


def test_a_console_file_excluded_for_a_secret_never_reads_as_kept_in_full(roots):
    """The drivers pass --secrets-env because a guest command's stdout can carry one."""
    attempts, dest, env = roots
    a = _attempt(attempts, dest)
    le.run_command(a, "print the password", [sys.executable, "-c", f"print({SECRET!r})"],
                   secrets=le.load_secrets(env), echo=False)
    le.run_command(a, "plain", [sys.executable, "-c", "print('nothing secret')"], echo=False)
    le.finish_attempt(a, "finished", instrumentation_validity="valid", system_outcome="pass")

    m = le.export_attempt(a, dest, secrets=le.load_secrets(env))
    package = Path(m["destination"]["package"])
    original = "console/001-print-the-password.stdout.txt"
    assert not (package / original).exists()
    assert (package / (original + ".sanitized")).is_file()
    summary = (package / "SUMMARY.md").read_text(encoding="utf-8")
    assert "| Console capture | **complete on the WSL side**" in summary
    assert f"are NOT in this package: `{original}`" in summary
    assert f"[stdout]({original})" not in summary  # never a link to a file the package lacks
    assert f"[stdout, redacted]({original}.sanitized)" in summary
    assert "complete (stdout excluded for secrets; the package holds the redacted copy)" in summary
    assert SECRET.encode() not in _all_bytes(package)


def test_a_failure_on_a_convenience_file_still_lists_the_package_and_says_which_is_stale(roots, monkeypatch):
    """INDEX.md is the record: one unwritable pointer may not unlist every later package."""
    attempts, dest, _env = roots
    first = _finished(attempts, dest)
    le.export_attempt(first, dest)
    before_latest = (dest / "LATEST_SUMMARY.md").read_text(encoding="utf-8")
    real = le._Destination.write_text

    def refuse_latest(self, path, text):
        if path.name == "LATEST_SUMMARY.md":
            raise OSError(errno.EACCES, "Access is denied")
        return real(self, path, text)

    monkeypatch.setattr(le._Destination, "write_text", refuse_latest)
    second = _finished(attempts, dest)
    m = le.export_attempt(second, dest)  # the package is finished; one index file is not

    assert verify_sha256sums(Path(m["destination"]["package"])) == []
    assert m["index_note"].startswith("LATEST_SUMMARY.md could not be rebuilt")
    assert "INDEX.md was written and names it as stale" in m["index_note"]
    index = (dest / "INDEX.md").read_text(encoding="utf-8")
    assert second.name in index  # the sealed package is in the record, not lost until the lock goes
    assert "LATEST_SUMMARY.md" in index and "must not be read as the newest" in index
    # The pointer was not replaced, and no reader is left taking it for the
    # newest attempt: the record beside it says it is stale.
    assert (dest / "LATEST_SUMMARY.md").read_text(encoding="utf-8") == before_latest
    assert second.name not in before_latest
    assert not list(dest.glob("*.tmp"))
    # and the failure reaches the receipt, so no driver reads the export as wholly done
    receipt = json.loads((second / "export" / "receipt.json").read_text(encoding="utf-8"))
    # The record DOES name this package; it is the pointer beside it that is
    # stale. Saying it is not named would send the operator to look for a row
    # of INDEX.md that is there — while the state still stays away from a
    # plain `verified`, so the driver goes on refusing it.
    assert receipt["package_state"].startswith("verified; the destination's index names it;")
    assert "not named in the destination's index" not in receipt["package_state"]
    assert receipt["package_state"] != "verified"
    assert second.name in (dest / "INDEX.md").read_text(encoding="utf-8")
    assert "LATEST_SUMMARY.md" in receipt["index_note"]

    monkeypatch.setattr(le._Destination, "write_text", real)
    le.rebuild_index(dest)
    assert second.name in (dest / "INDEX.md").read_text(encoding="utf-8")
    assert second.name in (dest / "LATEST_SUMMARY.md").read_text(encoding="utf-8")
    assert "must not be read as the newest" not in (dest / "INDEX.md").read_text(encoding="utf-8")


def test_a_failure_on_the_record_itself_puts_the_other_generated_files_back(roots, monkeypatch):
    """The one file that may not be left behind the others is INDEX.md."""
    attempts, dest, _env = roots
    first = _finished(attempts, dest)
    le.export_attempt(first, dest)
    before_index = (dest / "INDEX.md").read_text(encoding="utf-8")
    before_latest = (dest / "LATEST_SUMMARY.md").read_text(encoding="utf-8")
    real = le._Destination.write_text

    def refuse_index(self, path, text):
        if path.name == "INDEX.md":
            raise OSError(errno.EACCES, "Access is denied")
        return real(self, path, text)

    monkeypatch.setattr(le._Destination, "write_text", refuse_index)
    second = _finished(attempts, dest)
    m = le.export_attempt(second, dest)

    assert verify_sha256sums(Path(m["destination"]["package"])) == []
    assert m["index_note"].startswith("INDEX.md could not be rebuilt")
    assert "LATEST_SUMMARY.md put back as it was" in m["index_note"]
    assert (dest / "INDEX.md").read_text(encoding="utf-8") == before_index
    assert (dest / "LATEST_SUMMARY.md").read_text(encoding="utf-8") == before_latest
    assert second.name not in (dest / "LATEST_SUMMARY.md").read_text(encoding="utf-8")
    assert not list(dest.glob("*.tmp"))


def test_two_names_inside_one_package_are_refused_for_what_was_measured(roots):
    """The link count says a second name exists; it does not say where."""
    attempts, dest, _env = roots
    a = _finished(attempts, dest)
    package = Path(le.export_attempt(a, dest)["destination"]["package"])
    os.link(package / "attempt.json", package / "analysis" / "duplicate.txt")

    le.rebuild_index(dest)
    index = (dest / "INDEX.md").read_text(encoding="utf-8")
    row = next(ln for ln in index.splitlines() if a.name in ln)
    assert "REFUSED: link" in row
    assert "this file has 2 names" in row and "outside" not in row


def test_a_plain_file_where_a_package_folder_goes_is_named_for_what_it_is(roots):
    attempts, dest, _env = roots
    a = _finished(attempts, dest)
    date_dir = dest / "runs" / le.run_date(a.name)
    date_dir.mkdir(parents=True)
    (date_dir / a.name).write_text("just an ordinary file\n", encoding="utf-8")
    with pytest.raises(le.UnsafePathError, match="it is a regular file where a directory is expected"):
        le.export_attempt(a, dest)


def test_recover_re_exports_a_package_that_is_no_longer_in_the_destination(roots, capsys):
    """`recover` is the remedy for evidence that did not reach output_test."""
    attempts, dest, env = roots
    a = _finished(attempts, dest)
    package = Path(le.export_attempt(a, dest)["destination"]["package"])
    assert json.loads((a / "export" / "receipt.json").read_text(encoding="utf-8"))["state"] == "complete"
    shutil.rmtree(package)  # tidied away in Explorer, or restored from an older copy

    assert le.main(["recover", "--attempts-root", str(attempts), "--dest-root", str(dest),
                    "--secrets-env", str(env)]) == 0
    assert "exported again: the package its receipt named is not in the destination" in capsys.readouterr().out
    assert (package / "export_manifest.json").is_file()
    assert verify_sha256sums(package) == []
    assert a.name in (dest / "INDEX.md").read_text(encoding="utf-8")
    # and a package that is really there is still left alone
    assert le.recover(attempts, dest) == []


@pytest.mark.skipif(not hasattr(os, "mkfifo"), reason="needs FIFOs")
def test_a_fifo_planted_in_a_finalised_package_is_refused_and_listed(roots):
    """Staging refuses one; a sealed package must not keep reporting itself clean."""
    attempts, dest, _env = roots
    a = _finished(attempts, dest)
    package = Path(le.export_attempt(a, dest)["destination"]["package"])
    os.mkfifo(package / "analysis" / "pipe")
    assert verify_sha256sums(package) == []  # the seal cannot see it: it is not a file to hash

    with pytest.raises(le.UnsafePathError, match="a FIFO"):
        le.export_attempt(a, dest)
    le.rebuild_index(dest)
    row = next(ln for ln in (dest / "INDEX.md").read_text(encoding="utf-8").splitlines() if a.name in ln)
    assert "REFUSED: special file" in row and "a FIFO" in row


def test_two_capture_failures_with_no_sequence_number_stay_two_and_stay_stable():
    """The identity an entry is stored under must be the one it is found by again.

    An entry the console pattern cannot explain has no sequence number and no
    stream. Keyed on those two, two of them collapse onto one key: the second
    is dropped on every re-read and the first is admitted twice, so the
    published count of lost streams is simply wrong.
    """
    def salvaged(letter: str) -> dict:
        return {"seq": None, "name": f"console/salvaged-{letter}.log", "stream": "unknown",
                "error": "it is a symlink; an export never creates one, so what it points at is not this "
                         "attempt's own evidence",
                "bytes_received": None, "bytes_kept": None, "console": f"console/salvaged-{letter}.log",
                "unreadable": True}

    attempt = {"run_id": "20260919T120000Z_demo_attempt01", "status": "finished",
               "instrumentation_validity": "invalid", "capture_failures": [salvaged("A"), salvaged("B")]}
    once = le.capture_failures(attempt, [], {})
    assert [f["console"] for f in once] == ["console/salvaged-A.log", "console/salvaged-B.log"]
    # Read back and joined again, as every update_attempt does: neither is
    # dropped and neither is admitted a second time.
    assert le.capture_failures({**attempt, "capture_failures": once}, [], {}) == once
    assert le._capture_verdict(attempt, [], {}).startswith("**INCOMPLETE** — 2 console stream(s)")


@needs_real_permissions
def test_an_attempt_that_cannot_be_updated_still_publishes_the_export_s_verdict(roots):
    """When the two verdicts cannot be made one, the package says which is the union."""
    attempts, dest, _env = roots
    a = _attempt(attempts, dest)
    le.run_command(a, "first", [sys.executable, "-c", "print('out')"], echo=False)
    (a / "console" / "002-ghost.stdout.txt").write_bytes(b"ghost output\n")
    data = json.loads((a / "attempt.json").read_text(encoding="utf-8"))
    data.update({"status": "finished", "ended_utc": le.utc_now(), "instrumentation_validity": "valid",
                 "system_outcome": "pass", "capture_failures": []})
    (a / "attempt.json").write_text(json.dumps(data), encoding="utf-8")
    (a / "export").mkdir()   # the receipt can still be written
    os.chmod(a, 0o500)       # but attempt.json can no longer be replaced
    try:
        m = le.export_attempt(a, dest)
    finally:
        os.chmod(a, 0o700)

    assert "could not be brought to this export's capture verdict" in m["capture_reconciliation"]
    assert [f["console"] for f in m["capture_failures"]] == ["console/002-ghost.stdout.txt"]
    package = Path(m["destination"]["package"])
    summary = (package / "SUMMARY.md").read_text(encoding="utf-8")
    assert "## The attempt's own verdict could not be updated" in summary
    assert "| Console capture | **INCOMPLETE**" in summary
    # The index reads the manifest as well as the packaged attempt, so the
    # stale 'valid' is never the row a supervisor sees.
    index = (dest / "INDEX.md").read_text(encoding="utf-8")
    assert "| invalid (console capture: see SUMMARY.md) |" in index


# --------------------------------------------------------------------------
# Fifth round: the console directory itself, one capture rule, and the record
# --------------------------------------------------------------------------


def test_a_console_directory_that_is_a_link_is_never_a_complete_capture(roots, tmp_path):
    """`exec` creates `console/` and nothing else does, so a link there is foreign.

    The operator's own story: `console/` is moved off a full disk and a link
    is left behind. `exec` goes on writing through it and the planner refuses
    it and copies nothing, so a verdict that read the streams behind the link
    would seal a package with no console evidence at all as a complete capture.
    """
    attempts, dest, _env = roots
    a = _attempt(attempts, dest)
    le.run_command(a, "measured window", [sys.executable, "-c", "print('the measured evidence')"], echo=False)
    elsewhere = tmp_path / "another-disk" / "console"
    elsewhere.parent.mkdir(parents=True)
    shutil.move(str(a / "console"), str(elsewhere))
    _link_to_dir(elsewhere, a / "console")
    assert (a / "console" / "001-measured-window.stdout.txt").is_file()  # still readable through the link

    le.finish_attempt(a, "finished", instrumentation_validity="valid", system_outcome="pass")
    attempt = json.loads((a / "attempt.json").read_text(encoding="utf-8"))
    assert attempt["instrumentation_validity"] == "invalid"
    assert sorted(f["console"] for f in attempt["capture_failures"]) == [
        "console", "console/001-measured-window.stderr.txt", "console/001-measured-window.stdout.txt"]
    assert all("the console directory is a" in f["error"] for f in attempt["capture_failures"])

    m = le.export_attempt(a, dest)
    package = Path(m["destination"]["package"])
    assert not (package / "console").exists()  # the planner refused it: not one console file was copied
    assert "console" in [f["console"] for f in m["capture_failures"]]
    summary = (package / "SUMMARY.md").read_text(encoding="utf-8")
    assert "| Instrumentation validity | **invalid** |" in summary
    assert "| Console capture | **INCOMPLETE**" in summary
    assert "**complete**" not in summary
    assert "| invalid | pass |" in (dest / "INDEX.md").read_text(encoding="utf-8")


@needs_real_permissions
def test_an_unlistable_console_never_says_a_stream_it_did_not_look_for_is_gone(roots):
    """A refusal states what was measured: an unlistable folder can still hold every file."""
    attempts, dest, _env = roots
    a = _attempt(attempts, dest)
    le.run_command(a, "first", [sys.executable, "-c", "print('out')"], echo=False)
    os.chmod(a / "console", 0o300)  # --wx: it cannot be listed, its files can still be opened
    try:
        le.finish_attempt(a, "finished", instrumentation_validity="valid", system_outcome="pass")
        attempt = json.loads((a / "attempt.json").read_text(encoding="utf-8"))
        m = le.export_attempt(a, dest)
    finally:
        os.chmod(a / "console", 0o700)

    lost = next(f for f in attempt["capture_failures"] if f["console"] == "console/001-first.stdout.txt")
    assert "the console directory could not be listed" in lost["error"]
    assert "no longer in the attempt" not in lost["error"]
    assert (a / "console" / "001-first.stdout.txt").is_file()  # it was there all along
    summary = (Path(m["destination"]["package"]) / "SUMMARY.md").read_text(encoding="utf-8")
    assert "no longer in the attempt" not in summary


def test_one_rule_decides_the_verdict_of_the_package_the_attempt_and_the_row(roots):
    """A stored list that already equals the union is not a verdict; the downgrade is."""
    attempts, dest, _env = roots
    a = _attempt(attempts, dest)
    le.run_command(a, "measured window", [sys.executable, "-c", "print('evidence')"], echo=False)
    # A record of a stream that failed, as a driver's own run leaves it behind.
    record = json.loads((a / "commands.jsonl").read_text(encoding="utf-8").splitlines()[0])
    record["capture"]["stdout"] = {"state": "failed", "bytes_received": 881, "bytes_kept": 12,
                                   "error": "OSError: [Errno 28] No space left on device",
                                   "echo": "not requested"}
    (a / "commands.jsonl").write_text(json.dumps(record) + "\n", encoding="utf-8")
    data = json.loads((a / "attempt.json").read_text(encoding="utf-8"))
    data.update({"status": "finished", "ended_utc": le.utc_now(), "instrumentation_validity": "valid",
                 "system_outcome": "pass", "validity_note": ""})
    commands, console = le._read_commands(a), le._console_inventory(a)
    data["capture_failures"] = le.capture_failures(data, commands, console)
    (a / "attempt.json").write_text(json.dumps(data), encoding="utf-8")
    # The premise: the stored list is already the union, so only the verdict
    # beside it is wrong.
    assert le.capture_failures(data, commands, console) == data["capture_failures"] != []

    m = le.export_attempt(a, dest)
    package = Path(m["destination"]["package"])
    packaged = json.loads((package / "attempt.json").read_text(encoding="utf-8"))
    summary = (package / "SUMMARY.md").read_text(encoding="utf-8")
    row = next(ln for ln in (dest / "INDEX.md").read_text(encoding="utf-8").splitlines() if a.name in ln)
    # The three records of one attempt, built from one function on one input.
    assert packaged["instrumentation_validity"] == "invalid"
    assert "downgraded from 'valid'" in packaged["validity_note"]
    assert "| Instrumentation validity | **invalid** |" in summary
    assert "| Console capture | **INCOMPLETE**" in summary
    assert "| invalid | pass |" in row
    assert json.loads((a / "attempt.json").read_text(encoding="utf-8"))["instrumentation_validity"] == "invalid"


@pytest.mark.parametrize("validity", ["not-applicable", "unknown"])
def test_a_lost_stream_downgrades_every_verdict_that_is_not_already_invalid(roots, validity):
    """`guest_session_close.sh` closes the ordinary session with --validity not-applicable."""
    attempts, dest, _env = roots
    a = _attempt(attempts, dest)
    le.run_command(a, "session close", [sys.executable, "-c", "print('closed')"], echo=False)
    (a / "console" / "001-session-close.stdout.txt").unlink()
    le.finish_attempt(a, "finished", instrumentation_validity=validity, system_outcome="pass")

    attempt = json.loads((a / "attempt.json").read_text(encoding="utf-8"))
    assert attempt["instrumentation_validity"] == "invalid"
    assert f"downgraded from {validity!r}" in attempt["validity_note"]
    m = le.export_attempt(a, dest)
    summary = (Path(m["destination"]["package"]) / "SUMMARY.md").read_text(encoding="utf-8")
    assert "| Instrumentation validity | **invalid** |" in summary
    assert f"| {validity} |" not in summary
    assert "| invalid | pass |" in (dest / "INDEX.md").read_text(encoding="utf-8")


def test_a_relative_source_path_is_refused_on_the_read_side(roots, tmp_path, monkeypatch):
    """Every driver runs the export from `$REPO/src`: a relative path names whatever sits there."""
    attempts, dest, _env = roots
    a = _finished(attempts, dest)
    (a / "sources.json").write_text(json.dumps({"sources": [
        {"kind": "raw", "path": os.path.join("elsewhere", "nominal-r01"), "siblings_glob": None,
         "role": "harness raw run directory", "added_utc": le.utc_now()}]}), encoding="utf-8")
    here = tmp_path / "some-working-directory"
    (here / "elsewhere" / "nominal-r01").mkdir(parents=True)
    (here / "elsewhere" / "nominal-r01" / "events.jsonl").write_text(DISTINCTIVE + "\n", encoding="utf-8")
    monkeypatch.chdir(here)

    m = le.export_attempt(a, dest)
    package = Path(m["destination"]["package"])
    assert [s["package_path"] for s in m["skipped_source_roots"]] == ["raw/nominal-r01"]
    assert "a relative path" in m["skipped_source_roots"][0]["type"]
    assert not (package / "raw").exists()
    assert DISTINCTIVE.encode() not in _all_bytes(package)
    assert m["copy_verification"] == "verified; incomplete"


@pytest.mark.parametrize("name", ["SUMMARY.md", "export_manifest.json", "SHA256SUMS"])
def test_an_artefact_named_like_a_generated_file_is_refused(roots, name):
    """The generated file would replace the copy while the manifest kept the copy's hash."""
    attempts, dest, _env = roots
    a = _finished(attempts, dest)
    notes = "an operator's notes, in a folder the drivers tell them to read\n"
    (a / name).write_text(notes, encoding="utf-8")
    with pytest.raises(le.ExportError, match="the name this export generates"):
        le.export_attempt(a, dest)
    assert not (dest / "runs").exists()  # nothing was sealed around it
    assert (a / name).read_text(encoding="utf-8") == notes  # and the notes are still in WSL


def test_an_artefact_named_like_a_redacted_derivative_is_refused(roots):
    """`*.sanitized` beside the file it would be derived from is a generated name too."""
    attempts, dest, _env = roots
    a = _finished(attempts, dest)
    (a / "analysis" / "table.csv.sanitized").write_text("not this export's derivative\n", encoding="utf-8")
    with pytest.raises(le.ExportError, match="the name this export generates for"):
        le.export_attempt(a, dest)
    assert not (dest / "runs").exists()


def test_a_registered_capsule_that_was_never_written_is_not_plainly_verified(roots, tmp_path, capsys):
    """A package sealed without its capsule reads alike whether it was refused or never written."""
    attempts, dest, env = roots
    a = _attempt(attempts, dest)
    le.add_source(a, "raw", tmp_path / "results" / "raw" / "never-written", role="harness raw run directory")
    le.finish_attempt(a, "finished", instrumentation_validity="valid", system_outcome="pass")

    assert le.main(["export", "--attempt", str(a), "--dest-root", str(dest), "--secrets-env", str(env)]) == 0
    out = capsys.readouterr().out
    assert "(verified; incomplete, " in out and "1 registered artefact(s) never written" in out
    package = dest / "runs" / le.run_date(a.name) / a.name
    m = json.loads((package / "export_manifest.json").read_text(encoding="utf-8"))
    assert m["copy_verification"] == "verified; incomplete"
    assert "1 registered artefact(s) that were never written" in m["package_completeness"]
    receipt = json.loads((a / "export" / "receipt.json").read_text(encoding="utf-8"))
    assert receipt["package_state"].startswith("verified; incomplete")
    assert "1 registered artefact(s) never written" in (dest / "INDEX.md").read_text(encoding="utf-8")


def test_the_receipt_names_the_state_of_the_package_in_one_field(roots):
    """One field is all the driver that reports the run reads of an export."""
    attempts, dest, _env = roots
    a = _finished(attempts, dest)
    le.export_attempt(a, dest)
    receipt = json.loads((a / "export" / "receipt.json").read_text(encoding="utf-8"))
    assert receipt["package_state"] == "verified"
    assert receipt["state"] == "complete" and receipt["index_note"] == ""


def test_recover_does_not_stay_silent_for_a_package_that_lost_files(roots, capsys):
    """A package that no longer verifies is not evidence that reached output_test."""
    attempts, dest, env = roots
    a = _finished(attempts, dest)
    package = Path(le.export_attempt(a, dest)["destination"]["package"])
    (package / "analysis" / "table.csv").unlink()  # a sync client that dropped a file, a tidy-up
    assert verify_sha256sums(package) == ["missing: analysis/table.csv"]

    code = le.main(["recover", "--attempts-root", str(attempts), "--dest-root", str(dest),
                    "--secrets-env", str(env)])
    out = capsys.readouterr()
    assert code == 2
    assert "export failed" in out.out and "does not verify" in out.out
    assert "were not exported" in out.err
    # The receipt no longer claims a verified package, and the package itself
    # was neither replaced nor emptied.
    receipt = json.loads((a / "export" / "receipt.json").read_text(encoding="utf-8"))
    assert receipt["state"] == "failed"
    assert receipt["package_state"].startswith("not in the destination")
    assert "no longer verifies" in receipt["package_state"]
    assert (package / "attempt.json").is_file()


# --------------------------------------------------------------------------
# Sixth round: one rule for everything inside the attempt, and a gate that
# compares the package with the attempt instead of with three file names
# --------------------------------------------------------------------------


@needs_symlinks
@pytest.mark.parametrize("name", ["attempt.json", "commands.jsonl", "sources.json"])
def test_a_file_of_the_attempt_left_as_a_link_is_counted_where_the_verdicts_are_read(roots, tmp_path,
                                                                                    capsys, name):
    """The rule `console/` was given, one level up, and never a list of names.

    The operator's own story again: the file is moved off a full disk and a
    link is left behind. The export reads THROUGH the link to build the
    package and the planner refuses to copy it, so a package reading
    `verified`, `complete` would be a complete record of a run whose own
    record it does not hold.
    """
    attempts, dest, env = roots
    a = _attempt(attempts, dest)
    le.run_command(a, "measured window", [sys.executable, "-c", "print('the measured evidence')"], echo=False)
    le.finish_attempt(a, "finished", instrumentation_validity="valid", system_outcome="pass")
    elsewhere = tmp_path / "another-disk"
    elsewhere.mkdir()
    shutil.move(str(a / name), str(elsewhere / name))
    (a / name).symlink_to(elsewhere / name)
    assert (a / name).is_file()  # still readable through the link: the export does read it

    assert le.main(["export", "--attempt", str(a), "--dest-root", str(dest), "--secrets-env", str(env)]) == 0
    out = capsys.readouterr().out
    assert "(verified; incomplete, " in out
    assert "1 file(s) or folder(s) of the attempt not copied" in out
    package = dest / "runs" / le.run_date(a.name) / a.name
    assert not (package / name).exists()  # it was refused, as a link always is
    m = json.loads((package / "export_manifest.json").read_text(encoding="utf-8"))
    assert [s["package_path"] for s in m["skipped_attempt_entries"]] == [name]
    assert m["copy_verification"] == "verified; incomplete"
    assert "1 file(s) or folder(s) of the attempt itself" in m["package_completeness"]
    # the one field a driver reads, and the row a reader reads
    receipt = json.loads((a / "export" / "receipt.json").read_text(encoding="utf-8"))
    assert receipt["package_state"] != "verified"
    assert receipt["package_state"].startswith("verified; incomplete")
    assert "file(s) or folder(s) of the attempt not copied" in (dest / "INDEX.md").read_text(encoding="utf-8")
    summary = (package / "SUMMARY.md").read_text(encoding="utf-8")
    assert f"`{name}` (symlink)" in summary
    if name == "commands.jsonl":
        # and the page never tells the reader to open a file it does not hold
        assert "`commands.jsonl` is **NOT in this package**" in summary
        assert "The full, sanitised argv of each command is in `commands.jsonl`." not in summary


def test_a_folder_of_the_attempt_that_is_a_link_is_counted_where_the_verdicts_are_read(roots, tmp_path):
    """`guest_session_open.sh` writes the mandatory guest-state record into `guest/`."""
    attempts, dest, _env = roots
    a = _attempt(attempts, dest)
    (a / "guest").mkdir()
    (a / "guest" / "guest-state-after-boot.txt").write_text(DISTINCTIVE + "\n", encoding="utf-8")
    elsewhere = tmp_path / "another-disk" / "guest"
    elsewhere.parent.mkdir(parents=True)
    shutil.move(str(a / "guest"), str(elsewhere))
    _link_to_dir(elsewhere, a / "guest")
    le.finish_attempt(a, "finished", instrumentation_validity="valid", system_outcome="pass")

    m = le.export_attempt(a, dest)
    package = Path(m["destination"]["package"])
    assert not (package / "guest").exists()
    assert DISTINCTIVE.encode() not in _all_bytes(package)
    assert [s["package_path"] for s in m["skipped_attempt_entries"]] == ["guest"]
    assert m["copy_verification"] == "verified; incomplete"
    receipt = json.loads((a / "export" / "receipt.json").read_text(encoding="utf-8"))
    assert receipt["package_state"].startswith("verified; incomplete")


@needs_real_permissions
def test_a_folder_of_the_attempt_that_cannot_be_listed_is_counted_and_says_so(roots):
    """A root-owned `guest/` is what the `sudo -n journalctl` step leaves behind in WSL."""
    attempts, dest, _env = roots
    a = _attempt(attempts, dest)
    (a / "guest").mkdir()
    (a / "guest" / "guest-state-after-boot.txt").write_text("degraded\n", encoding="utf-8")
    le.finish_attempt(a, "finished", instrumentation_validity="valid", system_outcome="pass")
    os.chmod(a / "guest", 0o000)
    try:
        m = le.export_attempt(a, dest)
    finally:
        os.chmod(a / "guest", 0o700)
    package = Path(m["destination"]["package"])
    assert not (package / "guest").exists()
    assert [s["package_path"] for s in m["skipped_attempt_entries"]] == ["guest"]
    assert m["skipped_attempt_entries"][0]["type"].startswith("unreadable directory")
    assert m["copy_verification"] == "verified; incomplete"
    summary = (package / "SUMMARY.md").read_text(encoding="utf-8")
    # "never read" would state a refusal this export did not make
    assert "`guest`: unreadable directory" in summary and "it could not be read" in summary
    assert "; listed here, never read" not in summary
    receipt = json.loads((a / "export" / "receipt.json").read_text(encoding="utf-8"))
    assert receipt["package_state"].startswith("verified; incomplete")


def test_a_console_file_added_after_the_seal_is_not_already_exported(roots):
    """A command interrupted before its record could be appended still wrote its stream."""
    attempts, dest, _env = roots
    a = _attempt(attempts, dest)
    le.run_command(a, "first", [sys.executable, "-c", "print('out')"], echo=False)
    le.finish_attempt(a, "finished", instrumentation_validity="valid", system_outcome="pass")
    package = Path(le.export_attempt(a, dest)["destination"]["package"])
    before = _tree(package)
    (a / "console" / "002-later.stdout.txt").write_bytes(b"output nobody accounted for\n")

    with pytest.raises(le.ExportError, match="finalised from an earlier state"):
        le.export_attempt(a, dest)
    assert _tree(package) == before  # the package is never replaced
    assert not (package / "console" / "002-later.stdout.txt").exists()


def test_a_registered_capsule_that_has_grown_is_not_already_exported(roots, tmp_path):
    """`backfill.sh` is built to be re-run and two of its capsules are still growing."""
    attempts, dest, _env = roots
    raw = _raw_capsule(tmp_path / "old", "sampler-fix")
    m = le.backfill(raw, attempts, dest, name="sampler-fix", scenario="sampler fix", date="2026-09-19",
                    note="unsealed candidate; session never closed", original_validity="unknown",
                    original_outcome="interrupted")
    package = Path(m["destination"]["package"])
    assert m["copy_verification"] == "verified"
    (raw / "session-journal.txt").write_text("the journal, recovered after the seal\n", encoding="utf-8")

    with pytest.raises(le.ExportError, match="finalised from an earlier state"):
        le.backfill(raw, attempts, dest, name="sampler-fix", scenario="sampler fix", date="2026-09-19",
                    note="unsealed candidate; session never closed", original_validity="unknown",
                    original_outcome="interrupted")
    assert not (package / "raw" / "sampler-fix" / "session-journal.txt").exists()


def test_a_file_of_a_registered_capsule_rewritten_after_the_seal_is_not_already_exported(roots, tmp_path):
    """Three file names cannot see a capsule whose own README was corrected."""
    attempts, dest, _env = roots
    raw = _raw_capsule(tmp_path / "old", "sampler-fix")
    (raw / "README.md").write_text("session never closed\n", encoding="utf-8")
    le.backfill(raw, attempts, dest, name="sampler-fix", scenario="sampler fix", date="2026-09-19",
                note="unsealed candidate", original_validity="unknown", original_outcome="interrupted")
    (raw / "README.md").write_text("session never closed; journal recovered\n", encoding="utf-8")

    with pytest.raises(le.ExportError, match="raw/sampler-fix/README.md"):
        le.backfill(raw, attempts, dest, name="sampler-fix", scenario="sampler fix", date="2026-09-19",
                    note="unsealed candidate", original_validity="unknown", original_outcome="interrupted")
    packaged = dest / "runs" / "2026-09-19" / "HIST_sampler-fix" / "raw" / "sampler-fix" / "README.md"
    assert packaged.read_text(encoding="utf-8") == "session never closed\n"


def test_a_corrected_historical_verdict_is_refused_and_never_discarded(roots, tmp_path, capsys):
    """The supervisor's correction lands after the backfill: it may not be dropped in silence."""
    attempts, dest, env = roots
    raw = _raw_capsule(tmp_path / "old", "sampler-fix")
    le.backfill(raw, attempts, dest, name="sampler-fix", scenario="sampler fix", date="2026-09-19",
                note="unsealed candidate; session never closed", original_validity="unknown",
                original_outcome="interrupted", secrets=le.load_secrets(env))
    package = dest / "runs" / "2026-09-19" / "HIST_sampler-fix"
    before = _tree(package)

    code = le.main(["backfill", "--source", str(raw), "--attempts-root", str(attempts),
                    "--dest-root", str(dest), "--name", "sampler-fix", "--scenario", "sampler fix",
                    "--date", "2026-09-19", "--validity", "invalid", "--outcome", "fail",
                    "--secrets-env", str(env),
                    "--note", "CORRECTED: the battery is not complete; T5 fails its deadline"])
    out = capsys.readouterr()
    assert code == 2
    assert "backfilled" not in out.out  # never reported as done
    for field in ("instrumentation_validity", "system_outcome", "reason"):
        assert field in out.err
    assert "another --name" in out.err
    # nothing was written, and the published package still says what it said
    assert _tree(package) == before
    packaged = json.loads((package / "attempt.json").read_text(encoding="utf-8"))
    assert packaged["instrumentation_validity"] == "unknown" and packaged["system_outcome"] == "interrupted"


@needs_symlinks
def test_a_console_entry_that_is_a_link_keeps_the_reason_the_inventory_measured(roots, tmp_path):
    """The export never established that the file is gone: it is there, and refused."""
    attempts, dest, _env = roots
    a = _attempt(attempts, dest)
    le.run_command(a, "measured window", [sys.executable, "-c", "print('the-evidence')"], echo=False)
    rel = "console/001-measured-window.stdout.txt"
    kept = (a / rel).stat().st_size
    elsewhere = tmp_path / "another-disk"
    elsewhere.mkdir()
    shutil.move(str(a / rel), str(elsewhere / "stdout.txt"))
    (a / rel).symlink_to(elsewhere / "stdout.txt")
    assert "the-evidence" in (a / rel).read_text(encoding="utf-8")  # readable, and not this attempt's

    le.finish_attempt(a, "finished", instrumentation_validity="valid", system_outcome="pass")
    attempt = json.loads((a / "attempt.json").read_text(encoding="utf-8"))
    failure = next(f for f in attempt["capture_failures"] if f["console"] == rel)
    assert "it is a symlink" in failure["error"]
    assert "no longer in the attempt" not in failure["error"]
    assert failure["bytes_kept"] is None  # nothing was measured; 0 would be a measurement

    summary = (Path(le.export_attempt(a, dest)["destination"]["package"]) / "SUMMARY.md").read_text(
        encoding="utf-8")
    assert "was kept is unknown" in summary
    assert f"0 of {kept} bytes kept" not in summary
    assert "no longer in the attempt" not in summary


def test_the_index_says_its_copy_column_is_the_verdict_recorded_at_seal_time(roots):
    """`rebuild_index` repeats each manifest; only `recover` re-checks a package."""
    attempts, dest, _env = roots
    a = _finished(attempts, dest)
    package = Path(le.export_attempt(a, dest)["destination"]["package"])
    (package / "analysis" / "table.csv").unlink()
    assert le.main(["index", "--dest-root", str(dest)]) == 0
    index = (dest / "INDEX.md").read_text(encoding="utf-8")
    assert "recorded when it was sealed" in index
    assert "`local_export recover` is what re-checks it" in index
    assert verify_sha256sums(package) == ["missing: analysis/table.csv"]
