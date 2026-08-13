#!/usr/bin/env python3
"""Verify every tracked SHA256SUMS evidence seal without external tools."""

from __future__ import annotations

import hashlib
import re
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
SUM_RE = re.compile(r"^([0-9A-Fa-f]{64})  (.+)$")


def digest(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            hasher.update(block)
    return hasher.hexdigest()


def main() -> int:
    seals = sorted((REPO_ROOT / "docs" / "evidence").rglob("SHA256SUMS"))
    failures: list[str] = []
    checked = 0
    for seal in seals:
        for line_number, line in enumerate(seal.read_text(encoding="utf-8").splitlines(), 1):
            if not line.strip():
                continue
            match = SUM_RE.fullmatch(line)
            if match is None:
                failures.append(f"{seal.relative_to(REPO_ROOT)}:{line_number}: malformed entry")
                continue
            expected, relative_name = match.groups()
            candidate = seal.parent / Path(relative_name)
            if not candidate.is_file():
                failures.append(f"{seal.relative_to(REPO_ROOT)}:{line_number}: missing {relative_name}")
                continue
            actual = digest(candidate)
            checked += 1
            if actual.lower() != expected.lower():
                failures.append(
                    f"{seal.relative_to(REPO_ROOT)}:{line_number}: hash mismatch for {relative_name}"
                )

    if failures:
        print("Evidence integrity check failed:", file=sys.stderr)
        for failure in failures:
            print(f"- {failure}", file=sys.stderr)
        return 1
    print(f"Verified {checked} artefacts across {len(seals)} evidence seals.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
