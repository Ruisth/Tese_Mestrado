"""SHA256SUMS writing and verification for raw run directories (plan 5.8).

Format: one line per file, ``<sha256 hex>  <relative posix path>`` (two
spaces, the classic ``sha256sum`` coreutils format), sorted by path. The
``SHA256SUMS`` file itself is excluded from the listing.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

SUMS_FILENAME = "SHA256SUMS"

_CHUNK = 1 << 20  # 1 MiB


def sha256_file(path: str | Path) -> str:
    """Hex SHA-256 of a file, read in chunks."""
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        while True:
            chunk = fh.read(_CHUNK)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def _listed_files(run_dir: Path) -> list[Path]:
    return sorted(
        p
        for p in run_dir.rglob("*")
        if p.is_file() and p.relative_to(run_dir).as_posix() != SUMS_FILENAME
    )


def write_sha256sums(run_dir: str | Path) -> Path:
    """Write ``SHA256SUMS`` covering every file under ``run_dir``."""
    run_dir = Path(run_dir)
    lines = []
    for p in _listed_files(run_dir):
        rel = p.relative_to(run_dir).as_posix()
        lines.append(f"{sha256_file(p)}  {rel}")
    sums_path = run_dir / SUMS_FILENAME
    sums_path.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")
    return sums_path


def verify_sha256sums(run_dir: str | Path) -> list[str]:
    """Verify ``SHA256SUMS`` against the directory contents.

    Returns a list of human-readable problems; an empty list means the
    directory verifies cleanly. Detected problems: missing SHA256SUMS,
    malformed lines, missing files, digest mismatches (tampering) and files
    present on disk but not listed.
    """
    run_dir = Path(run_dir)
    sums_path = run_dir / SUMS_FILENAME
    problems: list[str] = []
    if not sums_path.is_file():
        return [f"missing: {SUMS_FILENAME}"]

    listed: dict[str, str] = {}
    for lineno, line in enumerate(
        sums_path.read_text(encoding="utf-8").splitlines(), start=1
    ):
        if not line.strip():
            continue
        digest, sep, name = line[:64], line[64:66], line[66:]
        if len(digest) != 64 or sep != "  " or not name:
            problems.append(f"malformed line {lineno}: {line!r}")
            continue
        listed[name] = digest.lower()

    for name, expected in sorted(listed.items()):
        target = run_dir / name
        if not target.is_file():
            problems.append(f"missing: {name}")
            continue
        actual = sha256_file(target)
        if actual != expected:
            problems.append(f"mismatch: {name}")

    on_disk = {p.relative_to(run_dir).as_posix() for p in _listed_files(run_dir)}
    for name in sorted(on_disk - set(listed)):
        problems.append(f"unlisted: {name}")

    return problems
