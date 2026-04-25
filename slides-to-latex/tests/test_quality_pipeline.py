from __future__ import annotations

import importlib.util
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def load_script(name: str):
    path = ROOT / "scripts" / f"{name}.py"
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


class SlidesToLatexPipelineTests(unittest.TestCase):
    def test_pptx_text_extraction_uses_paragraph_blocks(self) -> None:
        extractor = load_script("extract_pptx_assets")
        xml = b"""<?xml version="1.0" encoding="UTF-8"?>
        <p:sld xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main"
               xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main">
          <p:cSld><p:spTree>
            <p:nvGrpSpPr/><p:grpSpPr/>
            <p:sp>
              <p:nvSpPr><p:cNvPr id="7" name="Content Placeholder 1"/><p:nvPr><p:ph type="body"/></p:nvPr></p:nvSpPr>
              <p:spPr><a:xfrm><a:off x="1" y="2"/><a:ext cx="3" cy="4"/></a:xfrm></p:spPr>
              <p:txBody>
                <a:p><a:pPr lvl="1"/><a:r><a:t>Protect the king = </a:t></a:r><a:r><a:t>protect downside</a:t></a:r></a:p>
              </p:txBody>
            </p:sp>
          </p:spTree></p:cSld>
        </p:sld>"""
        blocks = extractor.structured_text_blocks_from_slide(xml)
        self.assertEqual(len(blocks), 1)
        self.assertEqual(blocks[0]["text"], "Protect the king = protect downside")
        self.assertEqual(blocks[0]["shape_id"], "7")
        self.assertEqual(blocks[0]["placeholder"], "body")
        self.assertEqual(blocks[0]["paragraph_level"], 1)
        self.assertEqual(blocks[0]["bounds"]["cx"], 3)

    def test_builder_writes_english_without_ctex_and_packets(self) -> None:
        builder = load_script("build_academic_latex")
        data = {
            "slides": [
                {
                    "global_slide": 1,
                    "source_file": "Week1_Pre_Sessional.pptx",
                    "source_slide": 1,
                    "slide_title": "Risk and Return",
                    "text_blocks": [
                        {"order": 1, "paragraph_index": 1, "paragraph_level": 0, "text": "Expected return and variance"},
                        {"order": 2, "paragraph_index": 1, "paragraph_level": 0, "text": "sigma = 20%"},
                    ],
                    "plain_text_blocks": ["Risk and Return", "Expected return and variance", "sigma = 20%"],
                    "speaker_notes": ["Explain why variance matters."],
                    "tables": [],
                    "charts": [],
                    "figures": [],
                    "risk_flags": [],
                    "formula_candidates": ["sigma = 20%"],
                }
            ],
            "logical_sections": [
                {
                    "section_id": "section-001",
                    "title": "Risk and Return",
                    "source_file": "Week1_Pre_Sessional.pptx",
                    "slides": [1],
                    "packets": [{"packet_id": "section-001-packet-01", "slide_start": 1, "slide_end": 1, "slides": [1]}],
                }
            ],
        }
        latex = builder.build_latex(data, "MSIN0274", "en")
        self.assertNotIn("ctex", latex)
        self.assertIn("Scaffold Notice", latex)
        packets = builder.build_reconstruction_packets(data, "MSIN0274")
        self.assertFalse(packets["requires_external_api"])
        self.assertEqual(packets["packets"][0]["slides"][0]["source_slide"], 1)

    def test_verify_quality_gate_rejects_bad_output(self) -> None:
        verifier = load_script("verify_latex")
        with tempfile.TemporaryDirectory() as tmp:
            tex = Path(tmp) / "bad-en.tex"
            tex.write_text(
                "\\documentclass{article}\n"
                "\\usepackage{ctex}\n"
                "\\begin{document}\n"
                "\\tableofcontents\n"
                "\\begin{agentbox}{Scaffold Notice}x\\end{agentbox}\n"
                "\\begin{equation*}This is natural language in display math\\end{equation*}\n"
                "June = 80$\n"
                "\\end{document}\n",
                encoding="utf-8",
            )
            tex.with_suffix(".toc").write_text("", encoding="utf-8")
            quality = verifier.static_quality_checks(tex)
            joined = "\n".join(quality["quality_errors"])
            self.assertIn("ctex", joined)
            self.assertIn("scaffold", joined.lower())
            self.assertIn("Unbalanced dollar", joined)
            self.assertIn("Natural language", joined)

    def test_pdf_helpers_create_page_blocks_and_tables(self) -> None:
        pdf_extractor = load_script("extract_pdf_figures")
        blocks = pdf_extractor._line_blocks_from_text("Title\n\nRow A   10", 3)
        self.assertEqual([block["text"] for block in blocks], ["Title", "Row A 10"])
        self.assertEqual(blocks[0]["shape_type"], "pdf_text")
        tables = pdf_extractor._tables_from_pdfplumber(
            [[["Name", "Value"], ["Alpha", "1.23"], [None, ""]]]
        )
        self.assertEqual(tables[0]["rows"], [["Name", "Value"], ["Alpha", "1.23"]])

    def test_content_manifest_accepts_pdf_pages(self) -> None:
        manifest_builder = load_script("build_content_manifest")
        slides = [
            {
                "global_slide": 1,
                "source_file": "lecture.pdf",
                "source_slide": 7,
                "source_kind": "page",
                "slide_title": None,
                "plain_text_blocks": ["PDF page title"],
            }
        ]
        sections = manifest_builder.build_logical_sections(slides)
        self.assertEqual(sections[0]["title"], "PDF page title")


if __name__ == "__main__":
    unittest.main()
