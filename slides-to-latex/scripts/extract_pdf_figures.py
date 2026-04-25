#!/usr/bin/env python3
"""Extract PDF text, tables, and embedded images for academic LaTeX rebuilds."""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any


try:
    import pdfplumber
except ImportError:  # pragma: no cover - exercised by environments without pdfplumber
    pdfplumber = None


IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".ppm", ".pbm", ".pgm", ".tif", ".tiff", ".jp2"}


def natural_key(path: Path) -> tuple[int, str]:
    matches = re.findall(r"\d+", path.stem)
    if matches:
        return (int(matches[-1]), path.name)
    return (10**9, path.name)


def parse_pdfimages_list(stdout: str) -> list[dict[str, str]]:
    rows = []
    for line in stdout.splitlines():
        line = line.strip()
        if not line or line.startswith("page ") or line.startswith("---"):
            continue
        parts = line.split()
        if len(parts) < 15 or not parts[0].isdigit():
            continue
        rows.append(
            {
                "page": parts[0],
                "num": parts[1],
                "type": parts[2],
                "width": parts[3],
                "height": parts[4],
                "color": parts[5],
                "components": parts[6],
                "bits": parts[7],
                "encoding": parts[8],
                "interp": parts[9],
                "object_id": parts[10],
                "x_ppi": parts[12],
                "y_ppi": parts[13],
                "size": parts[14],
            }
        )
    return rows


def _pdf_figure_status(file_path: Path, row: dict) -> tuple[str, str]:
    """Return (status, drop_reason) using pdfimages metadata and file size."""
    size = file_path.stat().st_size
    if size < 5_000:
        return "drop", "too_small"

    try:
        w = int(row["width"]) if row.get("width", "").isdigit() else 0
        h = int(row["height"]) if row.get("height", "").isdigit() else 0
    except (ValueError, KeyError):
        w, h = 0, 0

    if w > 0 and h > 0:
        if w < 80 or h < 80:
            return "drop", "tiny_dimensions"

    return "review", ""


def _clean_text(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _line_blocks_from_text(text: str, page_number: int) -> list[dict]:
    blocks: list[dict] = []
    order = 1
    for line in text.splitlines():
        clean = _clean_text(line)
        if not clean:
            continue
        blocks.append(
            {
                "order": order,
                "shape_id": "",
                "shape_name": f"pdf-page-{page_number}-line-{order}",
                "shape_type": "pdf_text",
                "placeholder": "",
                "paragraph_index": 1,
                "paragraph_level": 0,
                "bounds": {},
                "text": clean,
            }
        )
        order += 1
    return blocks


def _tables_from_pdfplumber(raw_tables: list) -> list[dict]:
    tables: list[dict] = []
    for index, raw_table in enumerate(raw_tables or [], start=1):
        rows: list[list[str]] = []
        for row in raw_table or []:
            clean_row = [_clean_text(cell) for cell in row]
            if any(clean_row):
                rows.append(clean_row)
        if rows:
            tables.append(
                {
                    "order": index,
                    "shape_id": "",
                    "shape_name": f"pdf-table-{index}",
                    "bounds": {},
                    "rows": rows,
                }
            )
    return tables


def extract_pdfplumber_pages(pdf_path: Path) -> list[dict]:
    """Extract page-level text and tables with pdfplumber when available."""
    if pdfplumber is None:
        return []

    pages: list[dict] = []
    with pdfplumber.open(str(pdf_path)) as pdf:
        for page_number, page in enumerate(pdf.pages, start=1):
            text = page.extract_text(x_tolerance=1.5, y_tolerance=3) or ""
            tables = page.extract_tables() or []
            text_blocks = _line_blocks_from_text(text, page_number)
            pages.append(
                {
                    "source_file": str(pdf_path),
                    "page": page_number,
                    "slide_title": None,
                    "text_blocks": text_blocks,
                    "plain_text_blocks": [block["text"] for block in text_blocks],
                    "tables": _tables_from_pdfplumber(tables),
                    "speaker_notes": [],
                    "figures": [],
                    "charts": [],
                    "pdfplumber": {
                        "width": page.width,
                        "height": page.height,
                        "text_extracted": bool(text_blocks),
                        "tables_count": len(tables),
                    },
                }
            )
    return pages


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("pdf", help="Input .pdf file.")
    parser.add_argument("--output-dir", required=True, help="Output directory.")
    parser.add_argument("--figure-prefix", default="figure", help="Academic figure filename prefix.")
    parser.add_argument(
        "--start",
        type=int,
        default=1,
        help="First figure number to use when merging multiple sources.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    pdf_path = Path(args.pdf).expanduser().resolve()
    output_dir = Path(args.output_dir).expanduser().resolve()
    figures_dir = output_dir / "figures"
    manifest_dir = output_dir / "manifest"
    figures_dir.mkdir(parents=True, exist_ok=True)
    manifest_dir.mkdir(parents=True, exist_ok=True)

    if pdf_path.suffix.lower() != ".pdf":
        raise SystemExit(f"Input is not a .pdf file: {pdf_path}")
    if not pdf_path.exists():
        raise SystemExit(f"Input file does not exist: {pdf_path}")
    has_pdfimages = shutil.which("pdfimages") is not None
    image_rows: list[dict[str, str]] = []
    if has_pdfimages:
        list_result = subprocess.run(
            ["pdfimages", "-list", str(pdf_path)],
            check=True,
            text=True,
            capture_output=True,
        )
        image_rows = parse_pdfimages_list(list_result.stdout)

    pages = extract_pdfplumber_pages(pdf_path)
    pages_by_number = {page["page"]: page for page in pages}
    figures = []
    if has_pdfimages:
        with tempfile.TemporaryDirectory(prefix="slides-to-latex-pdfimages-") as tmp:
            prefix = Path(tmp) / "image"
            subprocess.run(
                ["pdfimages", "-j", "-p", str(pdf_path), str(prefix)],
                check=True,
            )
            extracted = sorted(
                [path for path in Path(tmp).iterdir() if path.suffix.lower() in IMAGE_SUFFIXES],
                key=natural_key,
            )

            for offset, source in enumerate(extracted, start=args.start):
                suffix = ".jpg" if source.suffix.lower() == ".jpeg" else source.suffix.lower()
                target_name = f"{args.figure_prefix}-{offset:03d}{suffix}"
                target = figures_dir / target_name
                shutil.copy2(source, target)
                row = image_rows[offset - args.start] if offset - args.start < len(image_rows) else {}

                status, drop_reason = _pdf_figure_status(target, row)
                figures.append(
                    {
                        "figure_number": offset,
                        "path": f"figures/{target_name}",
                        "source_file": str(pdf_path),
                        "source_page": int(row["page"]) if row.get("page", "").isdigit() else None,
                        "pdfimages": row,
                        "status": status,
                        "drop_reason": drop_reason,
                        "caption": "",
                        "label": "",
                    }
                )
                page_number = figures[-1]["source_page"]
                if page_number:
                    page_record = pages_by_number.setdefault(
                        page_number,
                        {
                            "source_file": str(pdf_path),
                            "page": page_number,
                            "slide_title": None,
                            "text_blocks": [],
                            "plain_text_blocks": [],
                            "tables": [],
                            "speaker_notes": [],
                            "figures": [],
                            "charts": [],
                            "pdfplumber": {
                                "width": None,
                                "height": None,
                                "text_extracted": False,
                                "tables_count": 0,
                            },
                        },
                    )
                    page_record["figures"].append(figures[-1])

    manifest = {
        "source": str(pdf_path),
        "type": "pdf",
        "slides": [pages_by_number[key] for key in sorted(pages_by_number)],
        "figures": figures,
        "pdfimages_count": len(image_rows),
        "pdfplumber_available": pdfplumber is not None,
        "pdfimages_available": has_pdfimages,
    }
    manifest_path = manifest_dir / f"{pdf_path.stem}-extraction.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if pdfplumber is None:
        print("WARNING: pdfplumber is not installed; extracted embedded images only.")
    if not has_pdfimages:
        print("WARNING: pdfimages is not installed; skipped embedded image extraction.")
    print(f"Extracted {len(pages_by_number)} PDF page records and {len(figures)} images from {pdf_path}.")
    print(manifest_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
