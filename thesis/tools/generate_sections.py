#!/usr/bin/env python3
"""Generate thesis/sections/*.md from the LaTeX sources.

The dissertation is written in LaTeX because the institution requires its
template and that is what gets submitted. The repository template, however,
expects a Markdown-first ``thesis/sections/`` tree. This script reconciles the
two: **LaTeX is the single source that is edited**, and the Markdown sections
are a GENERATED MIRROR, refreshed by running this script.

Never edit ``thesis/sections/*.md`` by hand - the next run overwrites it.

Mapping (documented in thesis/manifest.yaml):

    01_cover              <- latex/main.tex title block
    02_acknowledgements   <- latex/main.tex dedication + acknowledgment
    03_abstract           <- latex/main.tex Resumo + Abstract
    04_intro              <- latex/chapters/01_introduction.tex
    05_background         <- latex/chapters/02_background.tex
    06_architecture       <- latex/chapters/04_architecture.tex (design sections)
    07_implementation     <- latex/chapters/04_architecture.tex (built artefact)
    08_experiments        <- latex/chapters/03_methodology.tex
    09_results            <- latex/chapters/05_evaluation.tex
    10_conclusion         <- latex/chapters/06_conclusions.tex
    11_references         <- refs/references.bib

Chapter 4 is split by section because the repository template separates
architecture from implementation while the dissertation, following the plan's
chapter structure, keeps them in one chapter.

Requires pandoc on PATH (or at PANDOC_BIN).

    python thesis/tools/generate_sections.py
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

THESIS = Path(__file__).resolve().parents[1]
LATEX = THESIS / "latex"
SECTIONS = THESIS / "sections"

BANNER = (
    "<!-- GENERATED FILE - DO NOT EDIT.\n"
    "     Source: {source}\n"
    "     Regenerate with: python thesis/tools/generate_sections.py\n"
    "     The LaTeX tree under thesis/latex/ is the single edited source. -->\n\n"
)

#: Sections of chapter 4 that describe the DESIGN.
CH4_ARCHITECTURE = [
    "Overview",
    "Normative Interfaces",
    "Twin Model",
    "Security Considerations",
]
#: Sections of chapter 4 that describe the BUILT ARTEFACT.
CH4_IMPLEMENTATION = [
    "Platform Layer: EGW-OS",
    "Service Layer: Digital-Twin Stack",
    "Ingestion Controller",
    "Simulator",
    "Reproducibility and Evidence Structure",
]


def pandoc_bin() -> str:
    explicit = os.environ.get("PANDOC_BIN")
    if explicit and Path(explicit).is_file():
        return explicit
    found = shutil.which("pandoc")
    if found:
        return found
    for candidate in (
        Path(os.environ.get("LOCALAPPDATA", "")) / "Pandoc" / "pandoc.exe",
        Path("C:/Program Files/Pandoc/pandoc.exe"),
    ):
        if candidate.is_file():
            return str(candidate)
    sys.exit(
        "pandoc not found. Install it (winget install --id JohnMacFarlane.Pandoc) "
        "or set PANDOC_BIN."
    )


def neutralise(tex: str) -> str:
    """Replace project-specific macros pandoc cannot know about."""
    # Preserve literal separators from imported reference titles. Pandoc's
    # LaTeX reader otherwise drops this text symbol when writing Markdown.
    tex = tex.replace(r"\textbar{}", "|")
    # Sources compile from latex/, but generated pages live in sections/.
    tex = tex.replace(r"{imagens/", r"{../latex/imagens/")
    # A continued longtable header is a pagination aid, not a second data row.
    tex = re.sub(r"\\endfirsthead.*?\\endhead", r"\\endhead", tex, flags=re.S)
    # Pandoc cannot evaluate TeX dimension arithmetic in p-column definitions
    # and can consume numeric cell prefixes (e.g. '64-bit'). Widths belong to
    # PDF layout; the Markdown projection needs only the column count.
    def plain_columns(match: re.Match[str]) -> str:
        count = match[0].count(r">{\RaggedRight\arraybackslash}p{")
        return r"\begin{longtable}{" + "l" * count + "}" if count else match[0]

    tex = re.sub(r"(?m)^\\begin\{longtable\}\{[^\n]*\}$", plain_columns, tex)
    # The imported source uses stable numbered reference keys. GFM otherwise
    # drops unsupported citation nodes rather than preserving their markers.
    tex = re.sub(r"\\cite\{word(\d+)\}", lambda match: "[" + str(int(match[1])) + "]", tex)
    # \ac{TERM} / \acs / \acl -> TERM (acronym expansion lives in the PDF only)
    tex = re.sub(r"\\ac[sl]?\{([^}]*)\}", r"\1", tex)
    # \todo{...} -> a visible marker, so pending work stays pending in the mirror
    tex = re.sub(r"\\todo\{([^}]*)\}", r"\\textbf{[TODO: \1]}", tex)
    return tex


def convert(tex: str, pandoc: str) -> str:
    proc = subprocess.run(
        [pandoc, "--from=latex+raw_tex", "--to=gfm", "--wrap=none"],
        input=neutralise(tex),
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    if proc.returncode != 0:
        sys.exit(f"pandoc failed: {proc.stderr.strip()[:400]}")
    return proc.stdout.strip() + "\n"


def read(rel: str) -> str:
    return (LATEX / rel).read_text(encoding="utf-8")


def split_chapter4(titles: list[str]) -> str:
    """Return the \\section blocks of chapter 4 whose titles are in `titles`."""
    tex = read("chapters/04_architecture.tex")
    parts = re.split(r"(?m)^(\\section\{)", tex)
    kept: list[str] = []
    for i in range(1, len(parts), 2):
        block = parts[i] + parts[i + 1]
        match = re.match(r"\\section\{([^}]*)\}", block)
        if match and match.group(1) in titles:
            kept.append(block)
    missing = [t for t in titles if f"\\section{{{t}}}" not in tex]
    if missing:
        sys.exit(f"chapter 4 sections not found (renamed?): {missing}")
    return "\n\n".join(kept)


def extract_env(tex: str, start: str, end: str) -> str:
    match = re.search(re.escape(start) + r"(.*?)" + re.escape(end), tex, re.S)
    return match.group(1).strip() if match else ""


def extract_starred_chapter(tex: str, title: str) -> str:
    """Body of a \\chapter*{title} up to the next \\chapter/\\input/end."""
    match = re.search(
        r"\\chapter\*\{" + re.escape(title) + r"\}(.*?)(?=\\chapter|\\input|\\mainmatter|\\end\{document\})",
        tex,
        re.S,
    )
    return match.group(1).strip() if match else ""


def bib_entries(bib: Path) -> str:
    """A readable list of the bibliography keys and titles."""
    text = bib.read_text(encoding="utf-8")
    out: list[str] = []
    for entry in re.finditer(r"@(\w+)\s*\{\s*([^,]+),(.*?)\n\}", text, re.S):
        kind, key, body = entry.group(1), entry.group(2).strip(), entry.group(3)

        def field(name: str) -> str:
            m = re.search(name + r"\s*=\s*[{\"](.+?)[}\"]\s*,", body, re.S | re.I)
            return re.sub(r"\s+", " ", m.group(1)).strip(" {}") if m else ""

        bits = [b for b in (field("author"), field("title"), field("year")) if b]
        # A source-document import may preserve the complete formatted reference
        # in a note instead of guessing structured bibliographic metadata.
        # Match the outer note braces, including nested emphasis/link commands.
        if not bits:
            note = re.search(r"\bnote\s*=\s*\{(.*)\},?\s*$", body, re.S)
            if note:
                bits = [convert(note.group(1), pandoc_bin()).strip()]
        doi = field("doi")
        line = f"- **`{key}`** ({kind}) — " + ". ".join(bits)
        if doi:
            line += f". DOI: {doi}"
        out.append(line)
    return "\n".join(sorted(out))


def main() -> None:
    pandoc = pandoc_bin()
    SECTIONS.mkdir(parents=True, exist_ok=True)
    main_tex = read("main.tex")

    written: list[str] = []

    def emit(name: str, source: str, body: str) -> None:
        path = SECTIONS / f"{name}.md"
        path.write_text(BANNER.format(source=source) + body, encoding="utf-8", newline="\n")
        written.append(path.name)

    # --- front matter -----------------------------------------------------
    title = re.search(r"\\newcommand\{\\thesistitle\}\{([^}]*)\}", main_tex)
    cover = "# " + (title.group(1) if title else "Dissertation") + "\n\n"
    for pattern in (
        r"\\textit\{([^{}]*)\}\\\\",
        r"\\textit\{(Student number: [^{}]*)\}",
        r"(?m)^(Master in [^\n\\]+)\\\\",
        r"(?m)^(Lisbon, [^\n]+)$",
    ):
        value = re.search(pattern, main_tex)
        if value:
            cover += value[1] + "\n\n"
    abbreviations = LATEX / "abbreviations.tex"
    if abbreviations.is_file():
        cover += "\n# List of Acronyms\n\n" + convert(read("abbreviations.tex"), pandoc)
    emit("01_cover", "latex/main.tex (title block)", cover)

    ack = extract_env(main_tex, r"\begin{dedication}", r"\end{dedication}")
    ackn = extract_starred_chapter(main_tex, "Acknowledgment")
    emit(
        "02_acknowledgements",
        "latex/main.tex (dedication + acknowledgment)",
        convert("\\section*{Dedication}\n" + ack + "\n\n\\section*{Acknowledgment}\n" + ackn, pandoc),
    )

    resumo = extract_starred_chapter(main_tex, "Resumo")
    abstract = extract_starred_chapter(main_tex, "Abstract")
    emit(
        "03_abstract",
        "latex/main.tex (Resumo + Abstract)",
        convert("\\section*{Resumo}\n" + resumo + "\n\n\\section*{Abstract}\n" + abstract, pandoc),
    )

    # --- chapters ---------------------------------------------------------
    straight = {
        "04_intro": "chapters/01_introduction.tex",
        "05_background": "chapters/02_background.tex",
        "08_experiments": "chapters/03_methodology.tex",
        "09_results": "chapters/05_evaluation.tex",
        "10_conclusion": "chapters/06_conclusions.tex",
    }
    for name, rel in straight.items():
        emit(name, f"latex/{rel}", convert(read(rel), pandoc))

    emit(
        "06_architecture",
        "latex/chapters/04_architecture.tex (design sections)",
        convert("\\chapter{Architecture}\n" + split_chapter4(CH4_ARCHITECTURE), pandoc),
    )
    emit(
        "07_implementation",
        "latex/chapters/04_architecture.tex (implementation sections)",
        convert("\\chapter{Implementation}\n" + split_chapter4(CH4_IMPLEMENTATION), pandoc),
    )

    # --- references -------------------------------------------------------
    bib = THESIS / "refs" / "references.bib"
    emit(
        "11_references",
        "refs/references.bib",
        "# References\n\n"
        "Rendered by biblatex in the PDF. Listed here so the Markdown mirror is\n"
        "self-contained; `refs/references.bib` remains the single source.\n\n"
        + bib_entries(bib)
        + "\n",
    )

    print(f"generated {len(written)} sections in {SECTIONS}:")
    for name in sorted(written):
        print(f"  {name}")


if __name__ == "__main__":
    main()
