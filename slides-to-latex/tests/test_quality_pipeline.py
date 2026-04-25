from __future__ import annotations

import importlib.util
import json
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


def _write_tex(path: Path, body: str) -> None:
    path.write_text(body, encoding="utf-8")


def _write_manifest(path: Path, figures: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"figures": figures, "slides": []}), encoding="utf-8")


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


class VerifyLatexQualityGateTests(unittest.TestCase):
    """Each quality gate in verify_latex.static_quality_checks gets one fixture."""

    def setUp(self) -> None:
        self.verifier = load_script("verify_latex")

    def _check(self, body: str, *, manifest: list[dict] | None = None, name: str = "doc-en.tex") -> dict:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)
        tex = root / name
        _write_tex(tex, body)
        # Provide a populated .toc so the empty-TOC gate doesn't fire by default.
        tex.with_suffix(".toc").write_text("\\contentsline {section}{Foo}{1}\n", encoding="utf-8")
        manifest_path: Path | None = None
        if manifest is not None:
            manifest_path = root / "manifest" / "content_manifest.json"
            _write_manifest(manifest_path, manifest)
        return self.verifier.static_quality_checks(tex, manifest_path)

    def test_english_file_using_ctex_is_rejected(self) -> None:
        result = self._check("\\documentclass{article}\n\\usepackage{ctex}\n\\begin{document}x\\end{document}\n")
        joined = "\n".join(result["quality_errors"])
        self.assertIn("ctex", joined)

    def test_scaffold_marker_is_rejected(self) -> None:
        result = self._check(
            "\\documentclass{article}\n\\begin{document}\n"
            "\\begin{agentbox}{Scaffold Notice}placeholder\\end{agentbox}\n"
            "\\end{document}\n"
        )
        joined = "\n".join(result["quality_errors"]).lower()
        self.assertIn("scaffold", joined)

    def test_empty_toc_is_rejected(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)
        tex = root / "doc-en.tex"
        _write_tex(tex, "\\documentclass{article}\n\\begin{document}\n\\tableofcontents\nx\n\\end{document}\n")
        tex.with_suffix(".toc").write_text("", encoding="utf-8")
        result = self.verifier.static_quality_checks(tex)
        self.assertTrue(any("Table of contents is empty" in e for e in result["quality_errors"]))

    def test_unbalanced_dollar_is_rejected(self) -> None:
        result = self._check("\\documentclass{article}\n\\begin{document}\nValue is 80$\n\\end{document}\n")
        self.assertTrue(any("Unbalanced dollar" in e for e in result["quality_errors"]))

    def test_residual_unicode_math_is_rejected(self) -> None:
        result = self._check(
            "\\documentclass{article}\n\\begin{document}\nReturn α and σ are key.\n\\end{document}\n"
        )
        self.assertTrue(any("Residual Unicode" in e for e in result["quality_errors"]))

    def test_natural_language_in_display_math_is_rejected(self) -> None:
        result = self._check(
            "\\documentclass{article}\n\\begin{document}\n"
            "\\begin{equation*}This is natural language inside display math fully here\\end{equation*}\n"
            "\\end{document}\n"
        )
        self.assertTrue(any("Natural language" in e for e in result["quality_errors"]))

    def test_missing_figure_file_is_rejected(self) -> None:
        result = self._check(
            "\\documentclass{article}\n\\begin{document}\n"
            "\\includegraphics{figures/missing.png}\n"
            "\\end{document}\n"
        )
        self.assertTrue(any("Missing figure" in e for e in result["quality_errors"]))

    def test_manifest_drop_figure_in_latex_is_rejected(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)
        figdir = root / "figures"
        figdir.mkdir()
        (figdir / "drop.png").write_bytes(b"")
        result = self._check(
            "\\documentclass{article}\n\\begin{document}\n"
            "\\includegraphics{figures/drop.png}\n"
            "\\end{document}\n",
            manifest=[{"path": "figures/drop.png", "status": "drop"}],
        )
        # File exists, but manifest marks it drop — this gate must fire.
        # Note: _check() built its own tmpdir; rebuild here so the figure file exists alongside the .tex.
        # (Easier: write inline.)
        tex = root / "doc-en.tex"
        _write_tex(
            tex,
            "\\documentclass{article}\n\\begin{document}\n"
            "\\includegraphics{figures/drop.png}\n"
            "\\end{document}\n",
        )
        tex.with_suffix(".toc").write_text("\\contentsline {section}{x}{1}\n", encoding="utf-8")
        manifest = root / "manifest" / "content_manifest.json"
        _write_manifest(manifest, [{"path": "figures/drop.png", "status": "drop"}])
        result = self.verifier.static_quality_checks(tex, manifest)
        self.assertTrue(
            any("manifest marks drop" in e for e in result["quality_errors"]),
            result["quality_errors"],
        )

    def test_table_with_too_many_columns_is_rejected(self) -> None:
        cols = "l" * 13
        result = self._check(
            "\\documentclass{article}\n\\begin{document}\n"
            f"\\begin{{tabular}}{{{cols}}}a\\\\\\end{{tabular}}\n"
            "\\end{document}\n"
        )
        self.assertTrue(any("columns" in e for e in result["quality_errors"]))

    def test_clean_document_passes(self) -> None:
        result = self._check(
            "\\documentclass{article}\n\\begin{document}\n"
            "\\section{Intro}\n"
            "Mean and variance: $\\mu$ and $\\sigma$.\n"
            "\\end{document}\n"
        )
        self.assertEqual(result["quality_errors"], [])


class AssembleFragmentFigureCheckTests(unittest.TestCase):
    """Cover the figure-count alignment guard added to assemble_rewrite_fragments."""

    def setUp(self) -> None:
        self.assembler = load_script("assemble_rewrite_fragments")

    def _setup(self, fragment_body: str, manifest_figures: list[dict]) -> tuple[Path, Path]:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)
        frag_dir = root / "rewrite_fragments"
        frag_dir.mkdir()
        (frag_dir / "page-0001.tex").write_text(fragment_body, encoding="utf-8")
        manifest = root / "manifest" / "content_manifest.json"
        _write_manifest(manifest, manifest_figures)
        return frag_dir, manifest

    def test_keep_count_matches_includegraphics(self) -> None:
        frag_dir, manifest = self._setup(
            "Body\n\\includegraphics{figures/figure-001.png}\n",
            [{"path": "figures/figure-001.png", "status": "keep"}],
        )
        records = self.assembler.load_manifest(frag_dir)
        errors = self.assembler.check_figure_alignment(frag_dir, records, manifest)
        self.assertEqual(errors, [])

    def test_missing_includegraphics_is_rejected(self) -> None:
        frag_dir, manifest = self._setup(
            "Prose without any figure block.\n",
            [{"path": "figures/figure-001.png", "status": "keep"}],
        )
        records = self.assembler.load_manifest(frag_dir)
        errors = self.assembler.check_figure_alignment(frag_dir, records, manifest)
        self.assertTrue(errors and "Figure count mismatch" in errors[0])

    def test_commented_includegraphics_is_not_counted(self) -> None:
        frag_dir, manifest = self._setup(
            "% \\includegraphics{figures/figure-001.png}\nProse only.\n",
            [{"path": "figures/figure-001.png", "status": "keep"}],
        )
        records = self.assembler.load_manifest(frag_dir)
        errors = self.assembler.check_figure_alignment(frag_dir, records, manifest)
        self.assertTrue(errors)


class CleanupOutputTests(unittest.TestCase):
    def test_targets_macos_duplicates_dsstore_and_root_aux(self) -> None:
        cleanup = load_script("cleanup_output")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "doc.tex").write_text("x", encoding="utf-8")
            (root / "doc 2.tex").write_text("x", encoding="utf-8")
            (root / ".DS_Store").write_text("", encoding="utf-8")
            (root / "doc.aux").write_text("", encoding="utf-8")
            build = root / "build"
            build.mkdir()
            (build / "doc.aux").write_text("", encoding="utf-8")
            names = sorted(p.relative_to(root).as_posix() for p in cleanup.collect_targets(root))
            self.assertEqual(names, [".DS_Store", "doc 2.tex", "doc.aux"])


class SyncAgentMetadataTests(unittest.TestCase):
    def test_check_succeeds_after_sync(self) -> None:
        sync = load_script("sync_agent_metadata")
        fields = sync.parse_skill_frontmatter((ROOT / "SKILL.md").read_text(encoding="utf-8"))
        self.assertEqual(fields.get("name"), "slides-to-latex")
        rendered_claude = sync.render_claude_md(fields["name"], fields["description"])
        self.assertEqual(rendered_claude, sync.CLAUDE_MD.read_text(encoding="utf-8"))
        self.assertEqual(sync.render_codex_yaml(), sync.CODEX_YAML.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
