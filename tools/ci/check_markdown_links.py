#!/usr/bin/env python3
"""Fail when a repository-local Markdown link has no target.

The checker deliberately ignores web/mail links, anchors and template values.
It is dependency-free so the same command runs locally and in GitHub Actions.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import unquote


REPO_ROOT = Path(__file__).resolve().parents[2]
LINK_RE = re.compile(r"!?\[[^\]]*\]\((<[^>]+>|[^)\s]+)(?:\s+['\"][^'\"]*['\"])?\)")
FENCE_RE = re.compile(r"^\s*(```|~~~)")
SKIP_PREFIXES = ("http://", "https://", "mailto:", "tel:", "data:")
# A sealed evidence package as the local export tool names it: one attempt
# ("<UTC stamp>_<slug>_attemptNN") or a historical record ("HIST_...").
PACKAGE_RE = re.compile(r"^(\d{8}T\d{6}Z_.+_attempt\d+|HIST_.+)$")


def in_sealed_package(path: Path) -> bool:
    """True when the file belongs to a sealed evidence package under
    docs/evidence: an ancestor directory is named as a package and its own
    SHA256SUMS lists the file. Such a file is captured bytes - a copy of a
    repository document kept by a preparation or a review keeps its original
    relative links, which do not resolve from inside the package - and the
    package's seal, not this checker, vouches for it. A capsule's own README,
    outside every package, is still checked."""

    relative = path.relative_to(REPO_ROOT)
    if relative.parts[:2] != ("docs", "evidence"):
        return False
    for ancestor in path.parents:
        if ancestor == REPO_ROOT / "docs" / "evidence":
            return False
        seal = ancestor / "SHA256SUMS"
        if PACKAGE_RE.match(ancestor.name) and seal.is_file():
            listed = path.relative_to(ancestor).as_posix()
            for line in seal.read_text(encoding="utf-8").splitlines():
                name = line[66:] if len(line) > 66 else ""
                if name.removeprefix("./") == listed:
                    return True
    return False


def markdown_files() -> list[Path]:
    return sorted(
        path
        for path in REPO_ROOT.rglob("*.md")
        if not any(part in {".git", "backups", ".venv", "venv"} for part in path.parts)
        # Exact historical snapshots intentionally retain their original,
        # now-obsolete workspace links. Current documents link to the archive,
        # but the archive itself is not rewritten to make it look current.
        and "docs/governance/archive" not in path.relative_to(REPO_ROOT).as_posix()
        # Sealed evidence packages are captured bytes as well (in_sealed_package).
        and not in_sealed_package(path)
    )


def visible_markdown(text: str) -> str:
    """Remove fenced code blocks, whose link-like examples are not links."""

    lines: list[str] = []
    fence: str | None = None
    for line in text.splitlines():
        match = FENCE_RE.match(line)
        if match:
            marker = match.group(1)
            if fence is None:
                fence = marker
            elif marker == fence:
                fence = None
            continue
        if fence is None:
            lines.append(line)
    return "\n".join(lines)


def target_path(source: Path, raw_target: str) -> Path | None:
    target = raw_target.strip("<>")
    if not target or target.startswith("#") or target.lower().startswith(SKIP_PREFIXES):
        return None
    if "{" in target or "}" in target:
        return None
    target = unquote(target.split("#", 1)[0].split("?", 1)[0])
    if not target:
        return None
    if re.match(r"^[A-Za-z]:[/\\]", target):
        return None
    if target.startswith("/"):
        return REPO_ROOT / target.lstrip("/")
    return source.parent / target


def main() -> int:
    failures: list[str] = []
    for source in markdown_files():
        text = visible_markdown(source.read_text(encoding="utf-8"))
        for match in LINK_RE.finditer(text):
            raw_target = match.group(1)
            path = target_path(source, raw_target)
            if path is not None and not path.exists():
                relative_source = source.relative_to(REPO_ROOT).as_posix()
                failures.append(f"{relative_source}: missing target {raw_target}")

    if failures:
        print("Local Markdown link check failed:", file=sys.stderr)
        for failure in failures:
            print(f"- {failure}", file=sys.stderr)
        return 1
    print(f"Checked local links in {len(markdown_files())} Markdown files.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
