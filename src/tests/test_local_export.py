"""Cases for egw_experiments.local_export: the local, per-attempt export to output_test.

They exercise what the work order of 2026-09-19 (2.B) asks the export to survive:
paths with spaces, an interrupted copy, a hash mismatch, a duplicate run id, a
failed test, secrets, missing artefacts, a crashed attempt and a historical
backfill. Everything runs on temporary directories; nothing touches a guest.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pytest

from egw_experiments import local_export as le
from egw_experiments.checksums import verify_sha256sums, write_sha256sums

SECRET = "s3cr3t-Password-value"


@pytest.fixture()
def roots(tmp_path: Path) -> tuple[Path, Path, Path]:
    attempts = tmp_path / "wsl attempts"
    dest = tmp_path / "Projeto Mestrado" / "output_test"
    env = tmp_path / "test.env"
    env.write_text(f"MOSQUITTO_SIMULATOR_PASSWORD={SECRET}\nEGW_ID=egw-01\n# comment\n", encoding="utf-8")
    return attempts, dest, env


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
    assert Path(path).is_absolute() and path.endswith("results/raw/later")


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
    assert le.backfill(raw, attempts, dest, name="controller_restart-r02", scenario="x", date="2026-09-19",
                       note="again")["note"].startswith("already exported")
    other = _raw_capsule(tmp_path / "elsewhere", "controller_restart-r02")
    with pytest.raises(le.ExportError, match="already used"):
        le.backfill(other, attempts, dest, name="controller_restart-r02", scenario="x", date="2026-09-19",
                    note="a different capsule under the same name")


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
