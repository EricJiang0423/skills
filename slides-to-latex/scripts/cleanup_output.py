#!/usr/bin/env python3
"""Clean a slides-to-latex output directory before delivery.

Removes:
  - macOS duplicate copies created on overwrite (``foo 2.tex`` / ``foo 2/``).
  - ``.DS_Store`` files anywhere under the directory.
  - LaTeX auxiliary files left in the root (``.aux .log .out .toc .fls .fdb_latexmk
    .synctex.gz missfont.log``); auxiliary files inside ``build/`` are preserved.

Usage:
    python3 cleanup_output.py <output-dir>            # remove offenders
    python3 cleanup_output.py <output-dir> --dry-run  # only list them
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path


DUPLICATE_RE = re.compile(r" \d+(\.[A-Za-z0-9]+)?$")
AUX_SUFFIXES = {
    ".aux",
    ".log",
    ".out",
    ".toc",
    ".fls",
    ".fdb_latexmk",
    ".synctex.gz",
}
AUX_NAMES = {"missfont.log"}


def _is_duplicate(name: str) -> bool:
    """Match macOS-generated duplicates: ``name 2.ext``, ``name 3``."""
    stem = name
    suffix = ""
    if "." in name:
        stem, _, ext = name.rpartition(".")
        suffix = "." + ext
    return bool(re.search(r" \d+$", stem)) and (suffix or True)


def collect_targets(root: Path) -> list[Path]:
    targets: list[Path] = []
    for path in sorted(root.rglob("*")):
        rel = path.relative_to(root)
        if path.is_file():
            if path.name == ".DS_Store":
                targets.append(path)
                continue
            if _is_duplicate(path.name):
                targets.append(path)
                continue
            # Aux files in root only — keep build/ contents.
            if path.parent == root:
                if path.suffix in AUX_SUFFIXES or path.name in AUX_NAMES:
                    targets.append(path)
        elif path.is_dir():
            if _is_duplicate(path.name):
                targets.append(path)
    return targets


def remove(path: Path) -> None:
    if path.is_dir():
        for child in sorted(path.rglob("*"), reverse=True):
            if child.is_file() or child.is_symlink():
                child.unlink(missing_ok=True)
            elif child.is_dir():
                child.rmdir()
        path.rmdir()
    else:
        path.unlink(missing_ok=True)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("directory", help="Output directory to clean.")
    parser.add_argument("--dry-run", action="store_true", help="Only print what would be removed.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    root = Path(args.directory).expanduser().resolve()
    if not root.is_dir():
        print(f"ERROR: not a directory: {root}", file=sys.stderr)
        return 2

    targets = collect_targets(root)
    if not targets:
        print(f"OK: {root} is already clean.")
        return 0

    label = "Would remove" if args.dry_run else "Removing"
    for path in targets:
        print(f"{label}: {path.relative_to(root)}")
        if not args.dry_run:
            remove(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
