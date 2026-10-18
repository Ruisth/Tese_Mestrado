#!/usr/bin/env python3
"""Decide, from the serial console log alone, whether the Debian first boot completed.

    firstboot_check.py <console.log>

The first boot of the ``debian13`` scenario runs cloud-init against the rendered NoCloud seed and
ends by powering the guest off (``power_state: poweroff``). It counts as complete only when the
log shows BOTH markers, in this order: cloud-init's completion line (``Cloud-init v. ... finished
at ...``) and the kernel's ``reboot: Power down``. A power-down that precedes the completion line
means cloud-init did not finish (the power_state timeout fired, or something else shut the guest
down), so it is not accepted.

Prints ``FIRSTBOOT: ok finished=<line no> powerdown=<line no>`` and the completion line itself
(``FIRSTBOOT-INFO:``). Lines that look like trouble (``Failed to start``, ``Traceback``,
``E: Unable``, ``dpkg: error``, cloud-init ``WARNING``) are echoed as ``FIRSTBOOT-WARN:`` lines;
they are information, not a verdict.

A console log must never carry a secret: a ``-----BEGIN`` line is fatal (``KEY-ERROR``), except
the two public blocks cloud-init prints on purpose (``-----BEGIN SSH HOST KEY FINGERPRINTS-----``
and ``-----BEGIN SSH HOST KEY KEYS-----``, public host keys); ``PRIVATE KEY`` is fatal anywhere.
The offending text is never echoed, only its line number.

Exit codes: 0 complete; 1 a marker is missing or out of order; 2 the log cannot be read;
3 private-key material in the log.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

# Case-sensitive on purpose: systemd's "Finished cloud-init-local.service ..." unit lines must not count.
FINISHED_RE = re.compile(r"Cloud-init v\. .* finished at|cloud-init.*finished")
POWERDOWN_RE = re.compile(r"reboot: Power down")
WARN_RE = re.compile(r"Failed to start|Traceback|E: Unable|dpkg: error|cloud-init.*WARNING")
BEGIN_RE = re.compile(r"-----BEGIN")
PUBLIC_BLOCK_RE = re.compile(r"-----BEGIN SSH HOST KEY (FINGERPRINTS|KEYS)-----")
PRIVATE_RE = re.compile(r"PRIVATE KEY")


def check(lines: list[str]) -> tuple[int, list[str]]:
    """Return (exit code, report lines) for the console log's lines."""
    report: list[str] = []
    finished_at = None
    powerdown_at = None
    for number, line in enumerate(lines, start=1):
        if PRIVATE_RE.search(line) or (BEGIN_RE.search(line) and not PUBLIC_BLOCK_RE.search(line)):
            report.append(f"KEY-ERROR: line {number} holds private-key material; the console log is not clean")
            return 3, report
        if WARN_RE.search(line):
            report.append(f"FIRSTBOOT-WARN: {line.rstrip()}")
        if finished_at is None and FINISHED_RE.search(line):
            finished_at = number
        if POWERDOWN_RE.search(line):
            powerdown_at = number
    missing = []
    if finished_at is None:
        missing.append("finished (no cloud-init completion line)")
    if powerdown_at is None:
        missing.append("powerdown (no 'reboot: Power down')")
    if missing:
        report.append("FIRSTBOOT: missing " + "; ".join(missing))
        return 1, report
    if powerdown_at < finished_at:
        report.append(f"FIRSTBOOT: powerdown (line {powerdown_at}) precedes finished (line {finished_at}): "
                      "cloud-init did not complete before the guest went down")
        return 1, report
    report.append(f"FIRSTBOOT: ok finished={finished_at} powerdown={powerdown_at}")
    report.append(f"FIRSTBOOT-INFO: {lines[finished_at - 1].rstrip()}")
    return 0, report


def main(argv: list[str]) -> int:
    if len(argv) != 2 or argv[1] in ("-h", "--help"):
        print("usage: firstboot_check.py <console.log>", file=sys.stderr)
        return 2
    path = Path(argv[1])
    try:
        text = path.read_bytes().decode("utf-8", "replace")
    except OSError as exc:
        print(f"STOP: console log unreadable: {exc}", file=sys.stderr)
        return 2
    code, report = check(text.splitlines())
    for line in report:
        print(line)
    return code


if __name__ == "__main__":
    sys.exit(main(sys.argv))
