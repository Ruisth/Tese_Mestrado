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


def markdown_files() -> list[Path]:
    return sorted(
        path
        for path in REPO_ROOT.rglob("*.md")
        if not any(part in {".git", "backups", ".venv", "venv"} for part in path.parts)
        # Exact historical snapshots intentionally retain their original,
        # now-obsolete workspace links. Current documents link to the archive,
        # but the archive itself is not rewritten to make it look current.
        and "docs/governance/archive" not in path.relative_to(REPO_ROOT).as_posix()
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
