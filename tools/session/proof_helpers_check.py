"""Is the deployed helper file the runbook's section 6.1 heredoc, byte for byte?

Usage: proof_helpers_check.py <runbook.md> <deployed helper file>

The finite proof of ADR 0011 runs the runbook's own ``drained``, ``_mline``,
``metrics``, ``keep`` and ``config_identity`` through the deployed
``~/egw-tcg/itest-helpers.sh``: the harness hooks source that file, and the
driver's ``pre`` step calls it through the host preamble. The reviewed
functions are the ones in the runbook's heredoc (``qemu_integrated_gateway.md``
section 6.1, ``host$ cat > ~/egw-tcg/itest-helpers.sh <<'EOF'`` ... ``EOF``),
which ``regen_helpers.py`` writes to that file. A deployed file that differs
- an older generation, a hand edit - would drain, read and identify the run
with functions nobody reviewed, so the driver refuses to start on it.

The heredoc is extracted exactly as ``regen_helpers.py`` extracts it (the
start line, then every line up to the first line that is exactly ``EOF``,
newlines kept), and a test pins the two extractions to each other. The
comparison is on bytes: the heredoc body encoded as UTF-8 against the file
as it is on disk. Both sha256 values, the line counts and, when they differ,
the first differing line are printed, so the console record says what was
compared and how it differed.

Exit status: 0 byte-equal; 1 the file differs; 2 the runbook or the file
could not be read, or the runbook holds no such heredoc. Every non-zero end
prints ``STOP: proof_helpers_check: ...`` on stderr.
"""
from __future__ import annotations

import hashlib
import sys
from pathlib import Path

HEREDOC_START = "host$ cat > ~/egw-tcg/itest-helpers.sh <<'EOF'"
HEREDOC_END = "EOF"


def heredoc_body(runbook_text: str) -> str:
    """The body of the 6.1 heredoc, as regen_helpers.py finds it: the lines
    after the start line up to the first line that is exactly ``EOF``,
    newlines kept. Raises ValueError when the runbook holds no such block."""
    lines = runbook_text.splitlines(keepends=True)
    try:
        start = next(i for i, ln in enumerate(lines) if ln.startswith(HEREDOC_START))
        end = next(i for i in range(start + 1, len(lines)) if lines[i].rstrip("\n") == HEREDOC_END)
    except StopIteration:
        raise ValueError("the runbook holds no complete section 6.1 heredoc "
                         f"({HEREDOC_START!r} ... {HEREDOC_END!r})") from None
    return "".join(lines[start + 1:end])


def first_difference(expected: bytes, actual: bytes) -> str:
    """One sentence naming the first line that differs, or the length."""
    left = expected.split(b"\n")
    right = actual.split(b"\n")
    for number, (a, b) in enumerate(zip(left, right), start=1):
        if a != b:
            return (f"first difference at line {number}: runbook {a[:80]!r}, "
                    f"deployed {b[:80]!r}")
    if len(left) != len(right):
        return (f"the first {min(len(left), len(right))} line(s) are equal; the runbook has "
                f"{len(left)} line(s), the deployed file {len(right)}")
    return "the bytes differ although every line compares equal (line endings?)"


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print("STOP: proof_helpers_check: usage: proof_helpers_check.py <runbook.md> <deployed helper file>",
              file=sys.stderr)
        return 2
    runbook, deployed = Path(argv[0]), Path(argv[1])
    try:
        body = heredoc_body(runbook.read_text(encoding="utf-8"))
    except (OSError, ValueError, UnicodeDecodeError) as exc:
        print(f"STOP: proof_helpers_check: the runbook {runbook} could not be read as the 6.1 "
              f"heredoc ({exc}): nothing was compared", file=sys.stderr)
        return 2
    expected = body.encode("utf-8")
    try:
        actual = deployed.read_bytes()
    except OSError as exc:
        print(f"STOP: proof_helpers_check: the deployed helper file {deployed} could not be read "
              f"({exc}): nothing was compared", file=sys.stderr)
        return 2
    expected_lines = expected.count(b"\n")
    actual_lines = actual.count(b"\n")
    print(f"runbook:  {runbook}")
    print(f"  heredoc sha256 {hashlib.sha256(expected).hexdigest()} ({expected_lines} lines, "
          f"{len(expected)} bytes)")
    print(f"deployed: {deployed}")
    print(f"  file    sha256 {hashlib.sha256(actual).hexdigest()} ({actual_lines} lines, "
          f"{len(actual)} bytes)")
    if actual == expected:
        print("HELPERS OK: the deployed helper file is the runbook's section 6.1 heredoc, byte for byte")
        return 0
    print(f"STOP: proof_helpers_check: the deployed helper file {deployed} is NOT the runbook's "
          f"section 6.1 heredoc ({first_difference(expected, actual)}); regenerate it with "
          f"regen_helpers.py before the proof", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
