"""Regression tests for the hash-enforced ARM64 runtime-lock procedure."""

from __future__ import annotations

import hashlib
import subprocess
import sys
from pathlib import Path


SRC_DIR = Path(__file__).resolve().parents[1]
LOCK_SCRIPT = SRC_DIR / "deployment" / "scripts" / "generate-runtime-lock.sh"


def _pip_hash_check(requirements: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            "-m",
            "pip",
            "install",
            "--disable-pip-version-check",
            "--dry-run",
            "--ignore-installed",
            "--no-deps",
            "--no-index",
            "--require-hashes",
            "--requirement",
            str(requirements),
        ],
        capture_output=True,
        text=True,
        check=False,
    )


def test_runtime_lock_procedure_seals_build_and_runtime_dependencies() -> None:
    script = LOCK_SCRIPT.read_text(encoding="utf-8")

    assert "--all-build-deps" in script
    assert "--allow-unsafe" in script
    assert "--generate-hashes" in script
    assert "--require-hashes" in script
    assert "--no-build-isolation" in script
    assert "--no-deps" in script
    assert "pip check" in script


def test_pip_hash_mode_rejects_a_dependency_without_a_hash(tmp_path) -> None:
    wheel = tmp_path / "egw_dummy-1.0-py3-none-any.whl"
    wheel.write_bytes(b"dummy wheel bytes")
    requirements = tmp_path / "unhashed.lock"
    requirements.write_text(
        f"egw-dummy @ {wheel.as_uri()}\n",
        encoding="utf-8",
    )

    result = _pip_hash_check(requirements)

    assert result.returncode != 0
    assert "hash" in (result.stdout + result.stderr).lower()


def test_pip_hash_mode_rejects_a_dependency_changed_after_lock(tmp_path) -> None:
    wheel = tmp_path / "egw_dummy-1.0-py3-none-any.whl"
    original = b"original wheel bytes"
    wheel.write_bytes(original)
    locked_hash = hashlib.sha256(original).hexdigest()
    requirements = tmp_path / "changed.lock"
    requirements.write_text(
        f"egw-dummy @ {wheel.as_uri()} --hash=sha256:{locked_hash}\n",
        encoding="utf-8",
    )
    wheel.write_bytes(b"tampered wheel bytes")

    result = _pip_hash_check(requirements)

    assert result.returncode != 0
    output = (result.stdout + result.stderr).lower()
    assert "hash" in output
    assert "match" in output or "expected" in output
