#!/usr/bin/env python3
"""Build one Code Agent multimodal rewrite task per slide/page.

This script does not call any model API. It packages extracted evidence and
optional rendered-slide paths so the running Code Agent can perform the
required page-by-page LLM/vision reconstruction pass in-context.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any


def block_text(block: Any) -> str:
    if isinstance(block, dict):
        value = block.get("text", "")
    else:
        value = block
    return re.sub(r"\s+", " ", str(value)).strip()


def source_key(source_file: str) -> str:
    stem = Path(source_file).stem
    return re.sub(r"[^A-Za-z0-9]+", "-", stem).strip("-").lower()


def candidate_render_paths(render_dir: Path, source_file: str, slide_no: int) -> list[Path]:
    """Return likely rendered-slide filenames without enforcing one renderer."""
    key = source_key(source_file)
    candidates = [
        render_dir / f"{key}-slide-{slide_no:03d}.png",
        render_dir / f"{key}-slide-{slide_no:03d}.jpg",
        render_dir / f"{key}-page-{slide_no:03d}.png",
        render_dir / f"{key}-page-{slide_no:03d}.jpg",
        render_dir / f"slide-{slide_no:03d}.png",
        render_dir / f"slide-{slide_no:03d}.jpg",
        render_dir / f"page-{slide_no:03d}.png",
        render_dir / f"page-{slide_no:03d}.jpg",
    ]
    return candidates


def find_rendered_slide(render_dir: Path | None, source_file: str, slide_no: int) -> str:
    if render_dir is None:
        return ""
    for candidate in candidate_render_paths(render_dir, source_file, slide_no):
        if candidate.exists():
            return str(candidate)
    # Fallback: tolerate renderer-specific names as long as source key and slide number appear.
    key = source_key(source_file)
    patterns = [
        f"*{key}*{slide_no:03d}*.png",
        f"*{key}*{slide_no:03d}*.jpg",
        f"*{slide_no:03d}*.png",
        f"*{slide_no:03d}*.jpg",
    ]
    for pattern in patterns:
        matches = sorted(render_dir.glob(pattern))
        if matches:
            return str(matches[0])
    return ""


def load_render_index(render_manifest: Path | None) -> dict[tuple[str, int], str]:
    if render_manifest is None:
        return {}
    data = json.loads(render_manifest.read_text(encoding="utf-8"))
    index: dict[tuple[str, int], str] = {}
    for source in data.get("sources", []):
        source_file = str(source.get("source_file", ""))
        for image in source.get("images", []):
            try:
                slide_no = int(image.get("index"))
            except (TypeError, ValueError):
                continue
            path = str(image.get("path", ""))
            if source_file and path:
                index[(source_file, slide_no)] = path
    return index


def short_item_count(texts: list[str]) -> int:
    count = 0
    for text in texts:
        stripped = re.sub(r"[^A-Za-z0-9%$]+", "", text)
        if len(stripped) <= 8:
            count += 1
    return count


def risk_summary(slide: dict) -> list[str]:
    flags = list(slide.get("risk_flags", []))
    texts = [block_text(t) for t in slide.get("plain_text_blocks", []) if block_text(t)]
    if short_item_count(texts) >= 3:
        flags.append("bullet_fragment_review")
    if slide.get("formula_candidates"):
        flags.append("formula_visual_review")
    if slide.get("tables"):
        flags.append("table_visual_review")
    if any(fig.get("status") == "keep" for fig in slide.get("figures", [])):
        flags.append("figure_placement_review")
    return sorted(set(flags))


def compact_slide(slide: dict, render_dir: Path | None, render_index: dict[tuple[str, int], str]) -> dict:
    source_file = str(slide.get("source_file", ""))
    slide_no = int(slide.get("source_slide") or 0)
    rendered = render_index.get((source_file, slide_no), "") if slide_no else ""
    if not rendered:
        rendered = find_rendered_slide(render_dir, source_file, slide_no) if slide_no else ""
    text_blocks = slide.get("text_blocks", [])
    plain_texts = [block_text(t) for t in slide.get("plain_text_blocks", []) if block_text(t)]
    kept_figures = [
        fig for fig in slide.get("figures", [])
        if fig.get("status") == "keep"
    ]
    review_figures = [
        fig for fig in slide.get("figures", [])
        if fig.get("status") == "review"
    ]
    return {
        "task_type": "multimodal_slide_latex_rewrite",
        "global_slide": slide.get("global_slide"),
        "source_file": source_file,
        "source_kind": slide.get("source_kind", "slide"),
        "source_slide": slide_no,
        "slide_title": slide.get("slide_title", ""),
        "rendered_slide": rendered,
        "rendered_slide_missing": not bool(rendered),
        "rewrite_contract": {
            "inspect_rendered_slide_first": bool(rendered),
            "rewrite_bullets_semantically": True,
            "rebuild_formulas_as_latex": True,
            "rebuild_tables_for_readability": True,
            "match_kept_figures_to_context": True,
            "do_not_emit_scaffold_or_review_boxes": True,
        },
        "quality_focus": risk_summary(slide),
        "text_blocks": text_blocks,
        "plain_text_blocks": plain_texts,
        "formula_candidates": slide.get("formula_candidates", []),
        "tables": slide.get("tables", []),
        "charts": slide.get("charts", []),
        "kept_figures": kept_figures,
        "review_figures": review_figures,
        "speaker_notes": slide.get("speaker_notes", []),
        "llm_prompt": (
            "Rewrite this slide/page into polished academic LaTeX. Use the rendered slide "
            "as the visual source of truth when available. Repair formula notation, table "
            "structure, bullet hierarchy, and figure placement. Convert extractor fragments "
            "into prose or meaningful lists. Return only final LaTeX body content for this "
            "slide, without scaffold warning boxes."
        ),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("content_manifest", help="Path to manifest/content_manifest.json.")
    parser.add_argument("--output", required=True, help="Output JSONL rewrite queue.")
    parser.add_argument(
        "--render-dir",
        default="",
        help="Optional directory containing rendered slide/page images for visual review.",
    )
    parser.add_argument(
        "--render-manifest",
        default="",
        help="Optional render_manifest.json from render_slide_images.py; preferred over filename guessing.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    manifest_path = Path(args.content_manifest).expanduser().resolve()
    output = Path(args.output).expanduser().resolve()
    render_dir = Path(args.render_dir).expanduser().resolve() if args.render_dir else None
    render_manifest = Path(args.render_manifest).expanduser().resolve() if args.render_manifest else None
    if render_manifest and not render_manifest.exists():
        raise SystemExit(f"render manifest not found: {render_manifest}")
    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    output.parent.mkdir(parents=True, exist_ok=True)

    render_index = load_render_index(render_manifest)
    tasks = [compact_slide(slide, render_dir, render_index) for slide in data.get("slides", [])]
    with output.open("w", encoding="utf-8") as handle:
        for task in tasks:
            handle.write(json.dumps(task, ensure_ascii=False) + "\n")

    missing = sum(1 for task in tasks if task["rendered_slide_missing"])
    print(f"Wrote {output}: {len(tasks)} rewrite task(s), {missing} missing rendered slide(s).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
