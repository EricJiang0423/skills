#!/usr/bin/env python3
"""Assemble rewritten per-slide LaTeX fragments into a final document."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any


PLACEHOLDER_RE = re.compile(
    r"LLM_REWRITE_REQUIRED|TODO\(multimodal\)|multimodal_slide_latex_rewrite|"
    r"Agent Reconstruction Required|Scaffold Notice|\\begin\{agentbox\}",
    re.IGNORECASE,
)

LATEX_ESCAPES = {
    "\\": r"\textbackslash{}",
    "&": r"\&",
    "%": r"\%",
    "$": r"\$",
    "#": r"\#",
    "_": r"\_",
    "{": r"\{",
    "}": r"\}",
    "~": r"\textasciitilde{}",
    "^": r"\textasciicircum{}",
}


def latex_escape(value: Any) -> str:
    return "".join(LATEX_ESCAPES.get(ch, ch) for ch in str(value))


def infer_language(output: Path, explicit: str) -> str:
    if explicit != "auto":
        return explicit
    return "zh" if output.stem.endswith("-zh") else "en"


def final_preamble(title: str, language: str) -> str:
    if language == "zh":
        ctex = r"\usepackage[UTF8, zihao=-4, fontset=fandol]{ctex}" + "\n"
        subtitle = "Academic Lecture Notes"
        toc_name = ""
        fig_name = ""
    else:
        ctex = ""
        subtitle = "Academic Lecture Notes"
        toc_name = r"\renewcommand{\contentsname}{Contents}" + "\n"
        fig_name = r"\renewcommand{\figurename}{Figure}" + "\n"
    return (
        "% ============================================================\n"
        "%  slides-to-latex final document\n"
        "% ============================================================\n"
        "\\documentclass[11pt, a4paper]{article}\n"
        + ctex
        + "\\usepackage[top=2.4cm,bottom=2.4cm,left=2.1cm,right=2.1cm]{geometry}\n"
        "\\usepackage{graphicx}\n"
        "\\usepackage{xcolor}\n"
        "\\usepackage{xurl}\n"
        "\\usepackage{hyperref}\n"
        "\\usepackage{amsmath,amssymb,mathtools}\n"
        "\\usepackage{booktabs,tabularx,longtable,array}\n"
        "\\usepackage{enumitem}\n"
        "\\usepackage[most]{tcolorbox}\n"
        "\\usepackage{caption}\n"
        "\\usepackage{subcaption}\n"
        "\\usepackage{titlesec}\n"
        "\\usepackage{fancyhdr}\n"
        "\\usepackage{microtype}\n"
        "\\hypersetup{colorlinks=true,linkcolor=blue!55!black,citecolor=green!45!black,urlcolor=cyan!65!black}\n"
        "\\captionsetup{font=small,labelfont=bf}\n"
        "\\setlist[itemize]{leftmargin=1.4em,itemsep=0.2em,topsep=0.2em}\n"
        "\\setlist[enumerate]{leftmargin=1.6em,itemsep=0.2em,topsep=0.2em}\n"
        "\\titleformat{\\section}{\\Large\\bfseries\\color{blue!65!black}}{\\thesection}{0.8em}{}[\\titlerule]\n"
        "\\titleformat{\\subsection}{\\large\\bfseries\\color{blue!45!black}}{\\thesubsection}{0.8em}{}\n"
        "\\titleformat{\\subsubsection}{\\normalsize\\bfseries\\color{black}}{\\thesubsubsection}{0.7em}{}\n"
        "\\pagestyle{fancy}\n"
        "\\setlength{\\headheight}{14pt}\n"
        "\\fancyhf{}\n"
        f"\\lhead{{\\small {latex_escape(title)}}}\n"
        f"\\rhead{{\\small {latex_escape(subtitle)}}}\n"
        "\\cfoot{\\thepage}\n"
        "\\renewcommand{\\headrulewidth}{0.4pt}\n"
        + toc_name
        + fig_name
        + "\\newtcolorbox{conceptbox}[1]{colback=blue!3,colframe=blue!45!black,title=#1,fonttitle=\\bfseries,arc=2pt,boxrule=0.4pt,breakable}\n"
        "\\newtcolorbox{takeawaybox}[1]{colback=green!3,colframe=green!40!black,title=#1,fonttitle=\\bfseries,arc=2pt,boxrule=0.4pt,breakable}\n"
        "\\newtcolorbox{notesbox}[1]{colback=gray!5,colframe=gray!55!black,title=#1,fonttitle=\\bfseries,arc=2pt,boxrule=0.3pt,breakable}\n"
        "\\newcommand{\\academicfigure}[4]{%\n"
        "  \\begin{figure}[htbp]\n"
        "    \\centering\n"
        "    \\includegraphics[width=#2\\linewidth,keepaspectratio]{#1}\n"
        "    \\caption{#3}\n"
        "    \\label{#4}\n"
        "  \\end{figure}}\n"
        "\\sloppy\n"
    )


def load_manifest(fragments_dir: Path) -> list[dict[str, Any]]:
    manifest_path = fragments_dir / "fragment_manifest.json"
    if not manifest_path.exists():
        return [
            {"fragment": path.name, "source_file": "", "source_slide": ""}
            for path in sorted(fragments_dir.glob("page-*.tex"))
        ]
    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    return list(data.get("fragments", []))


def section_title_for(source_file: str) -> str:
    stem = Path(source_file).stem if source_file else "Slides"
    stem = re.sub(r"[_-]+", " ", stem).strip()
    return stem or "Slides"


def validate_fragments(fragments_dir: Path, records: list[dict[str, Any]]) -> list[str]:
    errors: list[str] = []
    if not records:
        errors.append(f"No page-*.tex fragments found in {fragments_dir}")
        return errors
    for record in records:
        path = fragments_dir / record["fragment"]
        if not path.exists():
            errors.append(f"Missing fragment: {path.name}")
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        if not text.strip():
            errors.append(f"Empty fragment: {path.name}")
            continue
        if PLACEHOLDER_RE.search(text):
            errors.append(f"Placeholder/scaffold marker remains in {path.name}")
    return errors


def assemble(fragments_dir: Path, output: Path, title: str, language: str, allow_placeholders: bool) -> int:
    records = load_manifest(fragments_dir)
    errors = validate_fragments(fragments_dir, records)
    if errors and not allow_placeholders:
        for error in errors[:40]:
            print(f"ERROR: {error}", file=sys.stderr)
        if len(errors) > 40:
            print(f"ERROR: ... {len(errors) - 40} more issue(s)", file=sys.stderr)
        return 1

    lines = [final_preamble(title, language)]
    subtitle = "Academic Lecture Notes"
    lines.append(f"\\title{{{latex_escape(title)}\\\\[0.3em]{{\\normalsize {latex_escape(subtitle)}}}}}\n")
    lines.append("\\author{Generated with slides-to-latex}\n")
    lines.append("\\date{\\today}\n")
    lines.append("\\begin{document}\n\\maketitle\n\\tableofcontents\n\\newpage\n")

    current_source: str | None = None
    for record in records:
        source_file = str(record.get("source_file") or "")
        if source_file != current_source:
            current_source = source_file
            lines.append("\n\\section{" + latex_escape(section_title_for(source_file)) + "}\n")
        fragment_path = fragments_dir / record["fragment"]
        body = fragment_path.read_text(encoding="utf-8", errors="replace").strip()
        lines.append("\n" + body + "\n")

    lines.append("\n\\end{document}\n")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("".join(lines), encoding="utf-8")
    print(output)
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Assemble rewritten fragments into a final LaTeX document.")
    parser.add_argument("fragments_dir", help="Directory containing page-XXXX.tex fragments.")
    parser.add_argument("--output", required=True, help="Final .tex output path.")
    parser.add_argument("--title", default="Academic Lecture Notes")
    parser.add_argument("--language", choices=["auto", "en", "zh"], default="auto")
    parser.add_argument(
        "--allow-placeholders",
        action="store_true",
        help="Assemble even when placeholder markers remain. Intended only for debugging.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    fragments_dir = Path(args.fragments_dir).expanduser().resolve()
    output = Path(args.output).expanduser().resolve()
    language = infer_language(output, args.language)
    return assemble(fragments_dir, output, args.title, language, args.allow_placeholders)


if __name__ == "__main__":
    raise SystemExit(main())
