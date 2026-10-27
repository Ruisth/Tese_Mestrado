"""vc04 - cross-document consistency and the scripts that travel with the two
package D documents.

(a) the scripts named as sources by the two documents: any line carrying the
    name of a text-generation tool (the watch pattern is the one of vc03);
(b) the cross-references each document makes to the other, or to round one;
(c) the same quantity as each document's own script output states it: the
    served rate in 60 s blocks of nominal-r01's measured window.
Read-only; standard library only.
Run: wsl -d Ubuntu-24.04 --exec bash -lc '~/egw-exec/venv/bin/python <this file>'
"""
from __future__ import annotations

import base64
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
V2 = HERE.parent.parent
TOOLS = re.compile(base64.b64decode(
    "KD9pKVxiKGNsYXVkZXxjaGF0Z3B0fGdwdC0/XGQqfG9wZW5haXxhbnRocm9waWN8Y29waWxvdHxnZW1pbml8"
    "bGxtfGxhcmdlIGxhbmd1YWdlfFxiQUlcYnxhc3Npc3RhbnR8Y2hhdGJvdHxhZ2VudFxiKQ=="
).decode())


def lines(p: Path) -> list[str]:
    return p.read_text(encoding="utf-8").splitlines()


def main() -> None:
    print("== (a) travelling scripts: lines that carry a tool name (the name itself is masked)")
    for p in sorted((V2 / "scripts").glob("*")):
        if not p.is_file():
            continue
        for i, line in enumerate(lines(p), 1):
            if TOOLS.search(line):
                masked = TOOLS.sub("<tool-name>", line.strip())
                print(f"scripts/{p.name}:{i}: {masked[:200]}")
    print()
    print("== (b) cross-references between the two documents and to round one")
    pats = {
        "backlog_diagnosis.md": r"adr-recovery-draft|ADR draft|recovery ADR|5\.0 msg/s|two guest runs|comes first|0011",
        "adr-0011-controller-restart-recovery.md": r"backlog_diagnosis|capacity probe|section 7 would|5\.0 msg/s|5\.35|8\.57|T3",
    }
    for name, pat in pats.items():
        rx = re.compile(pat)
        for i, line in enumerate(lines(V2 / name), 1):
            if rx.search(line):
                print(f"{name}:{i}: {line.strip()[:220]}")
    print()
    print("== (c) served rate per 60 s block of the measured window, as each document's own output states it")
    for i, line in enumerate(lines(V2 / "out" / "adr0011_figures.out.txt"), 1):
        if line.startswith("N.7") or line.startswith("N.5"):
            print(f"out/adr0011_figures.out.txt:{i}: {line}")
    s02 = lines(V2 / "out" / "s02_rates_and_queue.out.txt")
    start = next(i for i, l in enumerate(s02) if "60 s blocks, aligned at el 0" in l)
    for j in range(start, start + 16):
        print(f"out/s02_rates_and_queue.out.txt:{j + 1}: {s02[j]}")
    for i, line in enumerate(s02, 1):
        if "30 s" in line and ("drain" in line.lower() or "window end +0" in line):
            print(f"out/s02_rates_and_queue.out.txt:{i}: {line}")
    g = next(i for i, l in enumerate(s02) if l.startswith("G."))
    for j in range(g, min(g + 6, len(s02))):
        print(f"out/s02_rates_and_queue.out.txt:{j + 1}: {s02[j]}")


if __name__ == "__main__":
    main()
