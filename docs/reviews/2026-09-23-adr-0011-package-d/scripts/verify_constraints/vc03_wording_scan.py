"""vc03 - wording scan of the two corrected package D documents.

Prints, per document and per rule, every line that carries a watched word, so
that each hit can be judged in context. Read-only; standard library only.
Run: wsl -d Ubuntu-24.04 --exec bash -lc '~/egw-exec/venv/bin/python <this file>'
"""
from __future__ import annotations

import base64
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
V2 = HERE.parent.parent
DOCS = ["backlog_diagnosis.md", "adr-0011-controller-restart-recovery.md"]

RULES: dict[str, str] = {
    "status words (accepted/proved/guarantee/closed/verified/validated/confirmed/established)":
        r"\b(accept(ed|ance|s)?|prov(ed|es|en|e)|PROVED|guarantee[sd]?|clos(ed|es|e)|verified|validat(ed|es|e)|establish(ed|es)?)\b",
    "capacity / ceiling / throughput / constraint / bottleneck / sustain":
        r"\b(capacity|ceiling|maximum|max(imum)?[- ]throughput|throughput|bottleneck|constraint|sustain\w*|saturat\w*|headroom|limit(ing)? factor)\b",
    "native / emulated":
        r"\b(native|emulat\w*|TCG|QEMU)\b",
    "supervisor / orientador / advisor":
        r"\b(supervisor\w*|orientador\w*|advis[eo]r\w*|professor\w*|Carvalho|Dias|approv\w*)\b",
    # names of text-generation tools and their vendors, base64-encoded so that
    # this script does not itself carry any such name
    "names of text-generation tools":
        base64.b64decode(
            "KD9pKVxiKGNsYXVkZXxjaGF0Z3B0fGdwdC0/XGQqfG9wZW5haXxhbnRocm9waWN8Y29waWxvdHxnZW1pbml8"
            "bGxtfGxhcmdlIGxhbmd1YWdlfFxiQUlcYnxhc3Npc3RhbnR8Y2hhdGJvdHxhZ2VudFxiKQ=="
        ).decode(),
    "American spellings (heuristic)":
        r"\b(\w+iz(e|ed|es|ing|ation)|analyz\w*|behavior\w*|color\w*|favor\w*|honor\w*|labor\b|center\w*|meter\b|modeling|modeled|labeled|labeling|canceled|canceling|traveled|fulfill\b|catalog\b|gray|license\b|practice[sd]\b|program(me)?s?\b|artifact\w*|judgment|toward\b|while\b)\b",
    "dates (all forms)":
        r"(\b20\d\d-\d\d-\d\d\b|\b\d{1,2}(st|nd|rd|th)? (January|February|March|April|May|June|July|August|September|October|November|December)\b|\b(January|February|March|April|May|June|July|August|September|October|November|December) \d{1,2}\b|\b\d{1,2}/\d{1,2}/\d{2,4}\b|\bSept?\b)",
    "load / deadline / window / threshold / ingest rule changes":
        r"\b(threshold|deadline|confirmation window|60 s|11\.2|warm-?up|MAX_SAMPLE_GAP_S|ingest|precondition|drained|DRAIN_QUIET_S|DRAIN_LIMIT_S|criterion|criteria)\b",
    "campaign / soak / rerun / repeat":
        r"\b(campaign|soak|re-?run\w*|repeat\w*|repetition|battery|pilot)\b",
}


def main() -> None:
    for name in DOCS:
        text = (V2 / name).read_text(encoding="utf-8").splitlines()
        print(f"################ {name} ({len(text)} lines)")
        for rule, pattern in RULES.items():
            rx = re.compile(pattern)
            hits = [(i, line) for i, line in enumerate(text, 1) if rx.search(line)]
            print(f"=== {rule}: {len(hits)} lines")
            for i, line in hits:
                words = sorted({m.group(0) for m in rx.finditer(line)})
                print(f"{name}:{i}: [{', '.join(words)}] {line.strip()[:240]}")
        print()


if __name__ == "__main__":
    main()
