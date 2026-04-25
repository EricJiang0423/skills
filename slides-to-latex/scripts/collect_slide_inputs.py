#!/usr/bin/env python3
"""Collect slide input files from a single file or folder in natural order."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path


SLIDE_EXTENSIONS = {".pdf", ".ppt", ".pptx"}
EXCLUDED_DIR_NAMES = {
    ".git",
    ".pytest_cache",
    "__pycache__",
    "images",
    "figures",
    "manifest",
    "qa-rendered",
    "qa-pdf",
    "cache",
    "tmp",
    "slides-to-latex-output",
}


def natural_parts(value: str) -> list[int | str]:
    parts: list[int | str] = []
    for chunk in re.split(r"(\d+)", value.lower()):
        if not chunk:
            continue
        parts.append(int(chunk) if chunk.isdigit() else chunk)
    return parts


def is_excluded_dir(path: Path) -> bool:
    name = path.name
    return (
        name in EXCLUDED_DIR_NAMES
        or name.startswith(".")
        or name.startswith("slides-to-latex-")
        or name.endswith("-latex")
        or name.endswith("_latex")
    )


def collect(root: Path) -> list[Path]:
    if root.is_file():
        if root.suffix.lower() not in SLIDE_EXTENSIONS:
            raise SystemExit(f"Unsupported input file type: {root}")
        return [root]

    if not root.is_dir():
        raise SystemExit(f"Input path does not exist: {root}")

    results: list[Path] = []
    for path in root.rglob("*"):
        if any(is_excluded_dir(parent) for parent in path.parents if parent != root.parent):
            continue
        if path.is_file() and path.suffix.lower() in SLIDE_EXTENSIONS:
            results.append(path)

    return sorted(
        results,
        key=lambda path: (
            [natural_parts(part) for part in path.relative_to(root).parts[:-1]],
            natural_parts(path.stem),
            path.suffix.lower(),
        ),
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("input", help="Slide file or folder to collect.")
    parser.add_argument("--manifest", help="Optional JSON manifest output path.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    root = Path(args.input).expanduser().resolve()
    files = collect(root)

    payload = [
        {
            "index": index,
            "path": str(path),
            "name": path.name,
            "extension": path.suffix.lower(),
        }
        for index, path in enumerate(files, start=1)
    ]

    if args.manifest:
        manifest = Path(args.manifest)
        manifest.parent.mkdir(parents=True, exist_ok=True)
        manifest.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

    for item in payload:
        print(f"{item['index']:03d} {item['path']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
