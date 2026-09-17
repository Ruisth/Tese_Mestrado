"""Regression checks for source-faithful dissertation Markdown generation."""
import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

MODULE = Path(__file__).with_name("generate_sections.py")
spec = importlib.util.spec_from_file_location("generate_sections", MODULE)
generator = importlib.util.module_from_spec(spec)
spec.loader.exec_module(generator)


class WordImportMirrorTests(unittest.TestCase):
    def test_literal_reference_separator_is_preserved(self):
        self.assertEqual(generator.neutralise(r"Title \textbar{} IEEE"), "Title | IEEE")

    def test_numbered_word_citations_survive_markdown_generation(self):
        self.assertEqual(generator.neutralise(r"Text \cite{word01}, \cite{word33}."), "Text [1], [33].")

    def test_pdf_column_dimensions_do_not_reach_markdown_parser(self):
        column = r">{\RaggedRight\arraybackslash}p{\dimexpr .5\linewidth-\tabcolsep\relax}"
        tex = r"\begin{longtable}{@{}" + column * 2 + "@{}}\nARM64 & 64-bit ARM architecture"
        self.assertEqual(generator.neutralise(tex), "\\begin{longtable}{ll}\nARM64 & 64-bit ARM architecture")

    def test_image_path_is_relative_to_generated_sections(self):
        self.assertEqual(
            generator.neutralise(r"\includegraphics[width=\linewidth]{imagens/research-process.png}"),
            r"\includegraphics[width=\linewidth]{../latex/imagens/research-process.png}",
        )

    def test_continuation_header_is_not_a_duplicate_data_row(self):
        self.assertEqual(
            generator.neutralise(r"Heading\endfirsthead Heading\endhead Data"),
            r"Heading\endhead Data",
        )

    def test_verbatim_note_keeps_nested_latex(self):
        note = r"A. Author, \emph{A title}, 2026, \url{https://example.org/}."
        with tempfile.TemporaryDirectory() as directory:
            bib = Path(directory) / "references.bib"
            bib.write_text("@misc{word01,\n  note = {" + note + "},\n}\n", encoding="utf-8")
            with patch.object(generator, "pandoc_bin", return_value="pandoc"), patch.object(generator, "convert", return_value="converted reference\n") as convert:
                self.assertEqual(generator.bib_entries(bib), "- **`word01`** (misc) — converted reference")
                convert.assert_called_once_with(note, "pandoc")

    def test_structured_reference_metadata_still_works(self):
        with tempfile.TemporaryDirectory() as directory:
            bib = Path(directory) / "references.bib"
            bib.write_text("@article{example,\n author = {A. Author},\n title = {A title},\n year = {2026},\n doi = {10.1234/example},\n}\n", encoding="utf-8")
            self.assertEqual(generator.bib_entries(bib), "- **`example`** (article) — A. Author. A title. 2026. DOI: 10.1234/example")


if __name__ == "__main__":
    unittest.main()
