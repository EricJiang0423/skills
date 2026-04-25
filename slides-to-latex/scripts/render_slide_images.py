#!/usr/bin/env python3
"""Render source slide decks/PDFs into per-page images for multimodal QA.

The rendered images are evidence for the Code Agent. They are not final
deliverables and should stay outside the output PDF/LaTeX package.
"""

from __future__ import annotations

import argparse
import json
import platform
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from collect_slide_inputs import collect  # noqa: E402
import convert_presentation_to_pdf as ppt_pdf  # noqa: E402


SUPPORTED_EXTENSIONS = {".pdf", ".ppt", ".pptx"}


def source_key(path: Path) -> str:
    key = re.sub(r"[^A-Za-z0-9]+", "-", path.stem).strip("-").lower()
    return key or "source"


def natural_sort_key(path: Path) -> list[int | str]:
    parts: list[int | str] = []
    for chunk in re.split(r"(\d+)", path.name.lower()):
        if not chunk:
            continue
        parts.append(int(chunk) if chunk.isdigit() else chunk)
    return parts


def unique_paths(paths: list[Path]) -> list[Path]:
    seen: set[Path] = set()
    ordered: list[Path] = []
    for path in paths:
        resolved = path.expanduser().resolve()
        if resolved in seen:
            continue
        seen.add(resolved)
        ordered.append(resolved)
    return ordered


def unique_source_keys(files: list[Path]) -> dict[Path, str]:
    counts: dict[str, int] = {}
    keys: dict[Path, str] = {}
    for path in files:
        base = source_key(path)
        counts[base] = counts.get(base, 0) + 1
        keys[path] = base if counts[base] == 1 else f"{base}-{counts[base]:02d}"
    return keys


def inputs_from_json(path: Path) -> list[Path]:
    data = json.loads(path.read_text(encoding="utf-8"))
    paths: list[Path] = []
    if isinstance(data, dict) and isinstance(data.get("slides"), list):
        for slide in data["slides"]:
            source = slide.get("source_file")
            if source:
                paths.append(Path(source))
    elif isinstance(data, list):
        for item in data:
            if isinstance(item, dict) and item.get("path"):
                paths.append(Path(item["path"]))
            elif isinstance(item, str):
                paths.append(Path(item))
    else:
        raise SystemExit(f"Unsupported JSON input format: {path}")
    return [p for p in unique_paths(paths) if p.suffix.lower() in SUPPORTED_EXTENSIONS]


def load_inputs(input_path: Path) -> list[Path]:
    if input_path.suffix.lower() == ".json":
        files = inputs_from_json(input_path)
    else:
        files = collect(input_path)
    if not files:
        raise SystemExit(f"No slide/PDF inputs found: {input_path}")
    return files


def convert_deck_to_pdf(input_path: Path, pdf_dir: Path, allow_libreoffice: bool) -> Path:
    pdf_dir.mkdir(parents=True, exist_ok=True)
    output_path = pdf_dir / f"{input_path.stem}.pdf"
    if output_path.exists() and output_path.stat().st_mtime >= input_path.stat().st_mtime:
        return output_path

    if platform.system() == "Darwin" and ppt_pdf.has_powerpoint():
        return ppt_pdf.convert_with_powerpoint(input_path, pdf_dir)
    if allow_libreoffice and ppt_pdf.has_libreoffice():
        return ppt_pdf.convert_with_libreoffice(input_path, pdf_dir)
    raise RuntimeError(
        f"Cannot convert {input_path} to PDF. Install Microsoft PowerPoint, or rerun with "
        "--allow-libreoffice when LibreOffice is installed."
    )


def render_pdf_to_images(pdf_path: Path, output_dir: Path, key: str, kind: str, dpi: int) -> list[Path]:
    pdftoppm = shutil.which("pdftoppm")
    if not pdftoppm:
        raise RuntimeError("pdftoppm not found. Install Poppler to render slide images.")

    output_dir.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="slides-to-latex-render-") as tmp:
        prefix = Path(tmp) / key
        subprocess.run(
            [pdftoppm, "-r", str(dpi), "-png", str(pdf_path), str(prefix)],
            check=True,
        )
        raw_images = sorted(Path(tmp).glob(f"{key}-*.png"), key=natural_sort_key)
        if not raw_images:
            raise RuntimeError(f"pdftoppm produced no images for {pdf_path}")

        rendered: list[Path] = []
        noun = "slide" if kind == "slide" else "page"
        for index, raw in enumerate(raw_images, start=1):
            target = output_dir / f"{key}-{noun}-{index:03d}.png"
            if target.exists():
                target.unlink()
            shutil.move(str(raw), str(target))
            rendered.append(target)
    return rendered


def render_source(
    input_path: Path,
    output_dir: Path,
    pdf_dir: Path,
    key: str,
    allow_libreoffice: bool,
    dpi: int,
) -> dict[str, Any]:
    ext = input_path.suffix.lower()
    if ext == ".pdf":
        pdf_path = input_path
        kind = "page"
    elif ext in {".ppt", ".pptx"}:
        pdf_path = convert_deck_to_pdf(input_path, pdf_dir, allow_libreoffice)
        kind = "slide"
    else:
        raise RuntimeError(f"Unsupported input type: {input_path}")

    images = render_pdf_to_images(pdf_path, output_dir, key, kind, dpi)
    return {
        "source_file": str(input_path),
        "source_pdf": str(pdf_path),
        "source_key": key,
        "source_kind": kind,
        "page_count": len(images),
        "images": [
            {
                "index": index,
                "path": str(path),
                "filename": path.name,
            }
            for index, path in enumerate(images, start=1)
        ],
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Render slide/PDF inputs into QA page images.")
    parser.add_argument("input", help="Slide/PDF file, folder, input_manifest.json, or content_manifest.json.")
    parser.add_argument("--output-dir", required=True, help="Directory for rendered PNG images.")
    parser.add_argument("--pdf-dir", required=True, help="Directory for intermediate deck-to-PDF files.")
    parser.add_argument("--dpi", type=int, default=180, help="Rendering DPI. Default: 180.")
    parser.add_argument(
        "--allow-libreoffice",
        action="store_true",
        help="Allow LibreOffice conversion when PowerPoint is unavailable.",
    )
    parser.add_argument(
        "--manifest",
        default="",
        help="Optional render manifest path. Defaults to <output-dir>/render_manifest.json.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    input_path = Path(args.input).expanduser().resolve()
    output_dir = Path(args.output_dir).expanduser().resolve()
    pdf_dir = Path(args.pdf_dir).expanduser().resolve()
    manifest_path = (
        Path(args.manifest).expanduser().resolve()
        if args.manifest
        else output_dir / "render_manifest.json"
    )

    files = load_inputs(input_path)
    keys = unique_source_keys(files)
    records: list[dict[str, Any]] = []
    for file_path in files:
        records.append(
            render_source(
                file_path,
                output_dir,
                pdf_dir,
                keys[file_path],
                args.allow_libreoffice,
                args.dpi,
            )
        )

    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(
        json.dumps(
            {
                "schema": "slides-to-latex.rendered-slides.v1",
                "dpi": args.dpi,
                "sources": records,
                "images_count": sum(record["page_count"] for record in records),
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    print(f"Wrote {manifest_path}: {sum(record['page_count'] for record in records)} image(s).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
