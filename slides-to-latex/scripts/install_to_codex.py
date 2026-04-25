#!/usr/bin/env python3
"""Install this skill into $CODEX_HOME/skills/slides-to-latex."""

from __future__ import annotations

import argparse
import os
import shutil
from pathlib import Path


SKILL_ROOT = Path(__file__).resolve().parents[1]
SKILL_NAME = "slides-to-latex"
EXCLUDE_NAMES = {
    "__pycache__",
    ".pytest_cache",
    ".DS_Store",
}
EXCLUDE_SUFFIXES = {
    ".pyc",
    ".pyo",
    ".aux",
    ".log",
    ".out",
    ".toc",
}
MACOS_DATALESS_FLAG = 0x40000000


def codex_home() -> Path:
    return Path(os.environ.get("CODEX_HOME", Path.home() / ".codex")).expanduser()


def should_ignore(path: Path) -> bool:
    if path.name in EXCLUDE_NAMES:
        return True
    if path.suffix in EXCLUDE_SUFFIXES:
        return True
    return False


def is_dataless(path: Path) -> bool:
    flags = getattr(path.stat(), "st_flags", 0)
    return bool(flags & MACOS_DATALESS_FLAG)


def dataless_sources(source: Path) -> list[Path]:
    files: list[Path] = []
    for path in source.rglob("*"):
        relative = path.relative_to(source)
        if any(part in EXCLUDE_NAMES for part in relative.parts):
            continue
        if should_ignore(path) or not path.is_file():
            continue
        try:
            if is_dataless(path):
                files.append(relative)
        except OSError:
            continue
    return files


def copy_file(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, destination)
    try:
        destination.chmod(source.stat().st_mode & 0o777)
    except OSError:
        pass


def copy_tree(source: Path, destination: Path) -> None:
    for path in source.rglob("*"):
        relative = path.relative_to(source)
        if any(part in EXCLUDE_NAMES for part in relative.parts):
            continue
        if should_ignore(path):
            continue
        target = destination / relative
        if path.is_dir():
            target.mkdir(parents=True, exist_ok=True)
        elif path.is_file():
            copy_file(path, target)


def copy_skill(destination: Path, overwrite: bool) -> None:
    unavailable = dataless_sources(SKILL_ROOT)
    if unavailable:
        sample = "\n".join(f"  - {path}" for path in unavailable[:12])
        raise SystemExit(
            "Some skill files are macOS dataless/cloud placeholders and must be materialized "
            "before installation:\n"
            f"{sample}\n"
            "Open them locally or run a file-provider/iCloud download, then retry."
        )
    if destination.exists():
        if not overwrite:
            raise SystemExit(f"Destination already exists: {destination}\nUse --overwrite to replace it.")
        shutil.rmtree(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.mkdir(parents=True, exist_ok=True)
    copy_tree(SKILL_ROOT, destination)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Install slides-to-latex as a local Codex skill.")
    parser.add_argument(
        "--destination",
        default=str(codex_home() / "skills" / SKILL_NAME),
        help="Destination skill directory. Defaults to $CODEX_HOME/skills/slides-to-latex.",
    )
    parser.add_argument("--overwrite", action="store_true", help="Replace an existing destination.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    destination = Path(args.destination).expanduser().resolve()
    copy_skill(destination, args.overwrite)
    print(destination)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
