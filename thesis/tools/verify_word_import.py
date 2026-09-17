#!/usr/bin/env python3
"""Read-only fidelity checks for this source-locked Word import.

Usage: python thesis/tools/verify_word_import.py --source manuscript.docx \
           --template /path/to/Template_LaTeX

Requires Pandoc and Python's standard library only. No files are changed.
This compares content, not rendered page layout or bibliographic correctness.
Whitespace, straight/curly quotes and automatic heading/caption numbering are
normalised. Source grammar, spelling, dates and citation positions are not.
The fixed source block ranges are intentional: its SHA-256 is checked first.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
from zipfile import ZipFile


THESIS = Path(__file__).resolve().parents[1]
LATEX = THESIS / "latex"
COMPARABLE = {"Header", "Para", "Plain", "BlockQuote", "OrderedList"}


def normalise(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip().translate(
        str.maketrans({"’": "'", "“": '"', "”": '"'})
    )


def text(node: object) -> str:
    if isinstance(node, list):
        return "".join(text(child) for child in node)
    if not isinstance(node, dict):
        return ""
    kind, value = node.get("t"), node.get("c")
    if kind == "Str":
        return value
    if kind in {"Space", "SoftBreak", "LineBreak"}:
        return " "
    if kind in {"Para", "Plain"}:
        return text(value) + "\n"
    if kind == "Header":
        return re.sub(r"^(Chapter \d+\.|\d+\.\d+\.)\s*", "", text(value[2])) + "\n"
    if kind == "Cite":
        return ", ".join(
            "[" + str(int(citation["citationId"].removeprefix("word"))) + "]"
            for citation in value[0]
        )
    if kind == "Link":
        return text(value[1])
    if kind == "Image":
        return "[IMAGE]"
    if kind == "Quoted":
        return '"' + text(value[1]) + '"'
    if kind == "RawInline":
        return "'" if "textquotesingle" in value[1] else "|" if "textbar" in value[1] else ""
    if kind == "RawBlock":
        return ""
    return text(value)


def nodes(value: object, kind: str) -> list[dict]:
    found = []
    if isinstance(value, dict):
        if value.get("t") == kind:
            found.append(value)
        for child in value.values():
            found.extend(nodes(child, kind))
    elif isinstance(value, list):
        for child in value:
            found.extend(nodes(child, kind))
    return found


def table_rows(table: dict) -> list[list[str]]:
    value = table["c"]
    rows = list(value[3][1])
    for body in value[4]:
        rows.extend(body[2] + body[3])
    rows.extend(value[5][1])
    return [[normalise(text(cell[4])) for cell in row[1]] for row in rows]


def find_pandoc(explicit: str | None) -> str:
    candidates = [explicit, os.environ.get("PANDOC_BIN"), shutil.which("pandoc")]
    candidates += [
        str(Path(os.environ.get("LOCALAPPDATA", "")) / "Pandoc" / "pandoc.exe"),
        "C:/Program Files/Pandoc/pandoc.exe",
    ]
    for candidate in candidates:
        if candidate and Path(candidate).is_file():
            return candidate
    raise RuntimeError("Pandoc not found; use --pandoc or PANDOC_BIN")


def verify(args: argparse.Namespace) -> dict:
    pandoc = find_pandoc(args.pandoc)
    errors: list[str] = []
    checks: dict[str, object] = {}

    def check(name: str, condition: bool, detail: object = True) -> None:
        checks[name] = detail if condition else False
        if not condition:
            errors.append(name)

    def convert(value: str, source_format: str, target_format: str = "json") -> str:
        return subprocess.run(
            [pandoc, "-f", source_format, "-t", target_format], input=value,
            capture_output=True, text=True, encoding="utf-8", check=True,
        ).stdout

    def parse(value: str, source_format: str = "latex") -> dict:
        return json.loads(convert(value, source_format))

    def read(relative: str) -> str:
        return (THESIS / relative).read_text(encoding="utf-8")

    def digest(path: Path) -> str:
        return hashlib.sha256(path.read_bytes()).hexdigest()

    manifest = json.loads(read("latex/word-import-manifest.json"))
    source_hash = digest(args.source)
    check("source_sha256", source_hash == manifest["source_sha256"], source_hash)
    check("source_size", args.source.stat().st_size == manifest["source_bytes"])
    for filename, expected in manifest["template_sha256"].items():
        path = args.template.joinpath(*re.split(r"[/\\]", filename))
        check("template_hash:" + filename.replace("\\", "/"), path.is_file() and digest(path) == expected)
    if not checks["source_sha256"]:
        return {"ok": False, "checks": checks, "errors": errors}

    source = json.loads(subprocess.run(
        [pandoc, str(args.source), "-f", "docx", "-t", "json"],
        capture_output=True, text=True, encoding="utf-8", check=True,
    ).stdout)["blocks"]
    headers = [b for b in source[29:91] if b["t"] == "Header"]
    check("source_chapters", sum(b["c"][0] == 1 for b in headers) == 2, 2)
    check("source_sections", sum(b["c"][0] == 2 for b in headers) == 14, 14)
    check("source_tables", len(nodes(source, "Table")) == 3, 3)

    source_prose: list[dict] = []
    tex_prose: list[dict] = []
    mirror_prose: list[dict] = []
    mirror_documents: dict[str, dict] = {}
    chapter_documents: dict[str, dict] = {}
    chapter_ranges = [("01_introduction", "04_intro", 29, 52, 5), ("02_background", "05_background", 52, 91, 9)]
    for chapter, mirror, start, stop, sections in chapter_ranges:
        tex = read("latex/chapters/" + chapter + ".tex")
        doc = parse(tex)
        chapter_documents[chapter] = doc
        check(chapter + ":chapters", len(re.findall(r"\\chapter\{", tex)) == 1)
        check(chapter + ":sections", len(re.findall(r"\\section\{", tex)) == sections, sections)
        source_prose.extend(b for i, b in enumerate(source[start:stop], start)
                            if b["t"] in COMPARABLE and i not in {46, 47, 56, 87})
        tex_prose.extend(b for b in doc["blocks"] if b["t"] in COMPARABLE)
        # Rendering GFM to HTML then reading HTML includes embedded HTML tables
        # and figures, which a direct GFM-to-JSON read leaves as raw blocks.
        mirrored = parse(convert(read("sections/" + mirror + ".md"), "gfm", "html"), "html")
        mirror_documents[mirror] = mirrored
        mirror_prose.extend(b for b in mirrored["blocks"] if b["t"] in COMPARABLE)

    expected_text = [normalise(text(b)) for b in source_prose]
    for label, actual in [("latex", tex_prose), ("mirror", mirror_prose)]:
        check(label + "_comparable_blocks", len(actual) == len(source_prose) == 56, 56)
        actual_text = [normalise(text(b)) for b in actual]
        check(label + "_body_text_and_citations", actual_text == expected_text)
        if actual_text != expected_text:
            errors.extend(label + ":body_block:" + str(i + 1)
                          for i, (a, b) in enumerate(zip(expected_text, actual_text)) if a != b)

    # Parse table cells independently. Pandoc's LaTeX table parser can consume
    # numeric cell text when the column specification contains \dimexpr.
    source_table_rows = [table_rows(source[i]) for i in (28, 57, 88)]
    actual_table_rows = []
    for filename in ("abbreviations.tex", "chapters/02_background.tex"):
        tex = read("latex/" + filename)
        for body in re.findall(r"\\begin\{longtable\}.*?\n\\toprule\n(.*?)\\end\{longtable\}", tex, re.S):
            body = re.sub(r"\\midrule\\endfirsthead.*?\\midrule\\endhead", "", body, flags=re.S)
            body = re.sub(r"\\bottomrule\\endfoot|\\addlinespace\[3pt\]", "", body)
            rows = []
            for row in re.split(r"\\\\", body):
                if row.strip():
                    rows.append([normalise(text(parse(cell)["blocks"]))
                                 for cell in re.split(r"(?<!\\)&", row.strip())])
            actual_table_rows.append(rows)
    cell_count = sum(len(row) for table in source_table_rows for row in table)
    check("source_table_cells", cell_count == 117, cell_count)
    check("latex_table_cells", actual_table_rows == source_table_rows, cell_count)
    cover = parse(convert(read("sections/01_cover.md"), "gfm", "html"), "html")
    mirror_tables = nodes(cover, "Table") + nodes(mirror_documents["05_background"], "Table")
    check("mirror_table_cells", [table_rows(t) for t in mirror_tables] == source_table_rows, cell_count)
    for index, table in zip((56, 87), nodes(mirror_documents["05_background"], "Table")):
        check("mirror_table_caption:" + str(index), normalise(text(table["c"][1])) == re.sub(r"^Table \d+\.\d+\. ", "", normalise(text(source[index]))))

    references = re.findall(r"@misc\{(word\d+),\s*note\s*=\s*\{(.*?)\},\s*\}", read("refs/references.bib"), re.S)
    source_references = [re.sub(r"^\[\d+\]\s*", "", normalise(text(b))) for b in source[92:125]]
    check("references", len(references) == len(source_references) == 33, 33)
    check("reference_keys", [key for key, _ in references] == [f"word{i:02d}" for i in range(1, 34)])
    rendered_references = [normalise(text(parse(note.replace(r"\textbar{}", "|"))["blocks"])) for _, note in references]
    check("latex_reference_strings", rendered_references == source_references)
    mirror_references = re.findall(r"^- \*\*`word\d+`\*\* \(misc\) — (.*)$", read("sections/11_references.md"), re.M)
    check("mirror_reference_strings", [normalise(text(parse(line, "gfm")["blocks"])) for line in mirror_references] == source_references)

    figures = nodes(chapter_documents["01_introduction"], "Figure")
    source_images = nodes(source[29:91], "Image")
    check("source_figures", len(source_images) == len(figures) == 1, 1)
    if len(source_images) == len(figures) == 1:
        image_target = source_images[0]["c"][2][0]
        with ZipFile(args.source) as archive:
            image_bytes = archive.read("word/" + image_target)
        generated_image = LATEX / "imagens/research-process.png"
        check("figure_bytes", generated_image.read_bytes() == image_bytes, hashlib.sha256(image_bytes).hexdigest())
        check("figure_caption", normalise(text(figures[0]["c"][1])) == re.sub(r"^Figure 1\.1\. ", "", normalise(text(source[47]))))
        mirror_images = nodes(mirror_documents["04_intro"], "Image")
        check("mirror_figure", len(mirror_images) == 1 and (THESIS / "sections" / mirror_images[0]["c"][2][0]).resolve() == generated_image.resolve())
        mirror_figures = nodes(mirror_documents["04_intro"], "Figure")
        check("mirror_figure_caption", len(mirror_figures) == 1 and normalise(text(mirror_figures[0]["c"][1])) == re.sub(r"^Figure 1\.1\. ", "", normalise(text(source[47]))))
    for index, table in zip((56, 87), nodes(chapter_documents["02_background"], "Table")):
        check("table_caption:" + str(index), normalise(text(table["c"][1])) == re.sub(r"^Table \d+\.\d+\. ", "", normalise(text(source[index]))))

    main = read("latex/main.tex")
    original_preamble = (args.template / "main.tex").read_text(encoding="utf-8").split(r"\begin{document}")[0]
    imported_preamble = main.split(r"\begin{document}")[0]
    imported_preamble = imported_preamble.replace(r"\addbibresource{../refs/references.bib}", r"\addbibresource{references.bib}")
    imported_preamble = re.sub(r"\\newcommand\{\\thesistitle\}\{[^\n]*\}\s*", "", imported_preamble)
    imported_preamble = imported_preamble.replace(r"\input{word-import-support}", "")
    uncomment = lambda value: normalise(re.sub(r"(?m)%.*$", "", value))
    check("template_preamble", uncomment(original_preamble) == uncomment(imported_preamble))
    check("template_two_covers", len(re.findall(r"\\includegraphics\[width=6\.03cm\]\{imagens/(?:iscte|ista)\}", main)) == 2)
    for logo in ("iscte.png", "ista.png"):
        check("template_logo:" + logo, (LATEX / "imagens" / logo).read_bytes() == (args.template / "imagens" / logo).read_bytes())
    for filename in ("03_methodology", "04_architecture", "05_evaluation", "06_conclusions"):
        value = re.sub(r"(?m)%.*$", "", read("latex/chapters/" + filename + ".tex"))
        value = re.sub(r"\\(?:chapter|section|subsection|label)\{[^}]*\}", "", value)
        check("headings_only:" + filename, not value.strip())
    for filename in ("02_acknowledgements", "03_abstract", "06_architecture", "07_implementation", "08_experiments", "09_results", "10_conclusion"):
        document = parse(read("sections/" + filename + ".md"), "gfm")
        substantive = [b for b in document["blocks"] if b["t"] != "RawBlock"]
        check("mirror_headings_only:" + filename, all(b["t"] == "Header" for b in substantive))
    dedication = re.search(r"\\begin\{dedication\}(.*?)\\end\{dedication\}", main, re.S)
    check("empty_dedication", dedication is not None and not dedication[1].strip())
    for heading, end in (("Acknowledgment", r"\\chapter"), ("Resumo", r"\\chapter"), ("Abstract", r"\\tableofcontents")):
        match = re.search(r"\\chapter\*\{" + heading + r"\}(.*?)(?=" + end + ")", main, re.S)
        check("empty_frontmatter:" + heading, match is not None and not match[1].strip())
    check("no_completion_placeholders", not re.search(r"\b(?:TODO|TBD|PLACEHOLDER|Write here|Escrever aqui)\b", main))
    return {"ok": not errors, "checks": checks, "errors": errors}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--template", required=True, type=Path)
    parser.add_argument("--pandoc")
    args = parser.parse_args()
    try:
        result = verify(args)
    except (OSError, ValueError, KeyError, subprocess.CalledProcessError, RuntimeError) as exc:
        result = {"ok": False, "errors": [str(exc)]}
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
