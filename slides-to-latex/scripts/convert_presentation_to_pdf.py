#!/usr/bin/env python3
"""Convert PPT/PPTX files to PDF, preferring local Microsoft PowerPoint."""

from __future__ import annotations

import argparse
import platform
import shutil
import subprocess
from pathlib import Path


POWERPOINT_APP = Path("/Applications/Microsoft PowerPoint.app")
POWERPOINT_BIN = POWERPOINT_APP / "Contents/MacOS/Microsoft PowerPoint"
LIBREOFFICE_BIN = Path("/Applications/LibreOffice.app/Contents/MacOS/soffice")
OSASCRIPT_BIN = Path("/usr/bin/osascript")


def has_powerpoint() -> bool:
    return POWERPOINT_APP.exists() or POWERPOINT_BIN.exists()


def has_libreoffice() -> bool:
    return LIBREOFFICE_BIN.exists() or shutil.which("soffice") is not None or shutil.which("libreoffice") is not None


def libreoffice_command() -> str:
    if LIBREOFFICE_BIN.exists():
        return str(LIBREOFFICE_BIN)
    found = shutil.which("soffice") or shutil.which("libreoffice")
    if not found:
        raise RuntimeError("LibreOffice was not found.")
    return found


def convert_with_powerpoint(input_path: Path, output_dir: Path) -> Path:
    output_path = output_dir / f"{input_path.stem}.pdf"
    osascript = str(OSASCRIPT_BIN if OSASCRIPT_BIN.exists() else "osascript")
    script = '''
on run argv
set inputPath to item 1 of argv
set outputPath to item 2 of argv
tell application "Microsoft PowerPoint"
  activate
  open (POSIX file inputPath)
  save active presentation in (POSIX file outputPath) as save as PDF
  close active presentation saving no
end tell
end run
'''
    try:
        subprocess.run(
            [osascript, "-e", script, str(input_path), str(output_path)],
            check=True,
        )
    except subprocess.CalledProcessError as exc:
        raise RuntimeError(
            "Microsoft PowerPoint failed to convert the file to PDF. Confirm that "
            "PowerPoint can open the file, and that macOS Privacy & Security allows "
            "the current terminal/app to control PowerPoint."
        ) from exc
    if not output_path.exists():
        raise RuntimeError(f"PowerPoint finished but the output PDF was not found: {output_path}")
    return output_path


def convert_with_libreoffice(input_path: Path, output_dir: Path) -> Path:
    command = libreoffice_command()
    subprocess.run(
        [
            command,
            "--headless",
            "--convert-to",
            "pdf",
            "--outdir",
            str(output_dir),
            str(input_path),
        ],
        check=True,
    )
    output_path = output_dir / f"{input_path.stem}.pdf"
    if not output_path.exists():
        raise RuntimeError(f"LibreOffice finished but the output PDF was not found: {output_path}")
    return output_path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("input", help="PPT or PPTX file to convert.")
    parser.add_argument("--output-dir", required=True, help="PDF output directory.")
    parser.add_argument(
        "--allow-libreoffice",
        action="store_true",
        help="Allow an installed LibreOffice copy when PowerPoint is unavailable.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    input_path = Path(args.input).expanduser().resolve()
    output_dir = Path(args.output_dir).expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    if input_path.suffix.lower() not in {".ppt", ".pptx"}:
        raise SystemExit(f"Input is not a PPT/PPTX file: {input_path}")
    if not input_path.exists():
        raise SystemExit(f"Input file does not exist: {input_path}")

    if platform.system() == "Darwin" and has_powerpoint():
        output = convert_with_powerpoint(input_path, output_dir)
        print(f"Converted with Microsoft PowerPoint: {output}")
        return 0

    if args.allow_libreoffice and has_libreoffice():
        output = convert_with_libreoffice(input_path, output_dir)
        print(f"Converted with LibreOffice: {output}")
        return 0

    raise SystemExit(
        "Microsoft PowerPoint was not detected. Ask the user whether LibreOffice "
        "is installed; if the user declines, stop instead of generating a "
        "low-fidelity substitute."
    )


if __name__ == "__main__":
    raise SystemExit(main())
