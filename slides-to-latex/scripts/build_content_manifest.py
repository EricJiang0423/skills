#!/usr/bin/env python3
"""Merge extraction manifests into a slide-level content manifest."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path


def load_extraction(path: Path) -> dict:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(payload, list):
        if not payload:
            raise ValueError(f"Empty extraction manifest: {path}")
        return payload[0]
    if isinstance(payload, dict):
        return payload
    raise ValueError(f"Unexpected extraction manifest format: {path}")


MATH_TOKENS = ("α", "β", "σ", "μ", "ρ", "λ", "τ", "π", "∑", "√", "≤", "≥", "≈")
FORMULA_RE = re.compile(
    r"(\b[A-Za-z][A-Za-z0-9_]*\s*=|[+\-*/^=<>]\s*[-+A-Za-z0-9]|[A-Za-z]\([^)]*\))"
)


def block_text(block: str | dict) -> str:
    if isinstance(block, dict):
        return re.sub(r"\s+", " ", str(block.get("text", ""))).strip()
    return re.sub(r"\s+", " ", str(block)).strip()


def normalize_text_blocks(blocks: list) -> list[dict]:
    """Return paragraph-level block dicts while preserving legacy manifests."""
    normalized: list[dict] = []
    for i, block in enumerate(blocks, start=1):
        if isinstance(block, dict):
            text = block_text(block)
            if not text:
                continue
            normalized.append(
                {
                    "order": int(block.get("order") or i),
                    "shape_id": str(block.get("shape_id", "")),
                    "shape_name": str(block.get("shape_name", "")),
                    "shape_type": str(block.get("shape_type", "text")),
                    "placeholder": str(block.get("placeholder", "")),
                    "paragraph_index": int(block.get("paragraph_index") or 1),
                    "paragraph_level": int(block.get("paragraph_level") or 0),
                    "bounds": block.get("bounds") or {},
                    "text": text,
                }
            )
        else:
            text = block_text(block)
            if text:
                normalized.append(
                    {
                        "order": i,
                        "shape_id": "",
                        "shape_name": "",
                        "shape_type": "legacy_text",
                        "placeholder": "",
                        "paragraph_index": 1,
                        "paragraph_level": 0,
                        "bounds": {},
                        "text": text,
                    }
                )
    return sorted(normalized, key=lambda b: (b["order"], b["paragraph_index"]))


def plain_texts(blocks: list[dict]) -> list[str]:
    return [b["text"] for b in blocks if b.get("text")]


def formula_candidates(texts: list[str]) -> list[str]:
    candidates: list[str] = []
    for text in texts:
        if len(text) > 180:
            continue
        if any(token in text for token in MATH_TOKENS) or FORMULA_RE.search(text):
            candidates.append(text)
    return candidates


def risk_flags(texts: list[str], tables: list[dict], charts: list[dict]) -> list[str]:
    flags: list[str] = []
    if not texts and not tables and not charts:
        flags.append("no_text_extracted")
    short = [t for t in texts if len(t) <= 3 or re.fullmatch(r"[\W\d]+", t)]
    if texts and len(short) / len(texts) >= 0.25:
        flags.append("fragmented_text")
    if len(texts) >= 20 and sum(1 for t in texts if len(t) <= 12) / len(texts) >= 0.5:
        flags.append("possible_table_or_ocr_fragments")
    if tables and any(len(t.get("rows", [])) > 18 for t in tables):
        flags.append("large_table")
    if formula_candidates(texts):
        flags.append("formula_candidates")
    return flags


def section_title_from_slide(source_file: str, slide: dict) -> str:
    title = slide.get("slide_title")
    if title:
        return str(title)
    for text in slide.get("plain_text_blocks", []):
        if 3 <= len(text) <= 120 and not text.isdigit():
            return text
    return re.sub(r"[_-]+", " ", Path(source_file).stem).strip()


def build_logical_sections(slides: list[dict], max_packet_slides: int = 12) -> list[dict]:
    sections: list[dict] = []
    current_source = None
    current_section: dict | None = None
    for slide in slides:
        source_file = slide.get("source_file", "")
        if source_file != current_source:
            if current_section:
                sections.append(current_section)
            current_source = source_file
            current_section = {
                "section_id": f"section-{len(sections) + 1:03d}",
                "source_file": source_file,
                "title": section_title_from_slide(source_file, slide),
                "slides": [],
                "packets": [],
            }
        assert current_section is not None
        current_section["slides"].append(slide["global_slide"])
    if current_section:
        sections.append(current_section)

    for section in sections:
        slide_ids = section["slides"]
        packets = []
        for start in range(0, len(slide_ids), max_packet_slides):
            chunk = slide_ids[start : start + max_packet_slides]
            packets.append(
                {
                    "packet_id": f"{section['section_id']}-packet-{len(packets) + 1:02d}",
                    "slide_start": chunk[0],
                    "slide_end": chunk[-1],
                    "slides": chunk,
                    "reconstruction_status": "agent_required",
                }
            )
        section["packets"] = packets
    return sections


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "manifests",
        nargs="+",
        help="Extraction manifest JSON files.",
    )
    parser.add_argument("--output", required=True, help="Output content_manifest.json path.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    output = Path(args.output).expanduser().resolve()
    output.parent.mkdir(parents=True, exist_ok=True)

    slides: list[dict] = []
    global_slide = 1

    for item in args.manifests:
        manifest_path = Path(item).expanduser().resolve()
        extraction = load_extraction(manifest_path)
        source = extraction.get("source", "")

        for slide in extraction.get("slides", []):
            text_blocks = normalize_text_blocks(slide.get("text_blocks", []))
            plain_blocks = slide.get("plain_text_blocks") or plain_texts(text_blocks)
            plain_blocks = [block_text(b) for b in plain_blocks if block_text(b)]
            slide_figures = slide.get("figures", [])
            slide_charts = slide.get("charts", [])
            slide_tables = slide.get("tables", [])
            speaker_notes = slide.get("speaker_notes", [])
            slide_title = slide.get("slide_title")
            formulas = formula_candidates(plain_blocks)
            slides.append(
                {
                    "global_slide": global_slide,
                    "source_file": slide.get("source_file", source),
                    "source_slide": slide.get("slide") or slide.get("page"),
                    "source_kind": "page" if slide.get("page") else "slide",
                    "slide_title": slide_title,
                    "text_blocks": text_blocks,
                    "plain_text_blocks": plain_blocks,
                    "tables": slide_tables,
                    "speaker_notes": speaker_notes,
                    "figures": slide_figures,
                    "charts": slide_charts,
                    "formula_candidates": formulas,
                    "risk_flags": risk_flags(plain_blocks, slide_tables, slide_charts),
                    "needs_formula_review": bool(formulas),
                    "needs_chart_rebuild": any(
                        c.get("status") != "data_extracted" for c in slide_charts
                    ),
                    "notes": "",
                }
            )
            global_slide += 1

    # Derive top-level figures and charts from slides (single source of truth).
    # classify_figures.py and build_academic_latex.py must always read from
    # slides[].figures[] — the top-level lists are kept only for counting.
    figures = [fig for s in slides for fig in s.get("figures", [])]
    charts = [c for s in slides for c in s.get("charts", [])]
    logical_sections = build_logical_sections(slides)

    payload = {
        "slides_count": len(slides),
        "figures_count": len(figures),
        "charts_count": len(charts),
        "logical_sections_count": len(logical_sections),
        "slides": slides,
        "logical_sections": logical_sections,
        "figures": figures,
        "charts": charts,
    }
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(
        f"Wrote {output}: {len(slides)} slides, "
        f"{len(figures)} figures, {len(charts)} charts."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
