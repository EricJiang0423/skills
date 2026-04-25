#!/usr/bin/env python3
"""Build a conservative LaTeX scaffold and agent reconstruction packets.

This script intentionally does not call OpenAI, Anthropic, or any other model
API. It prepares faithful source evidence for the Code Agent to rewrite using
its own LLM context, while still producing a compilable scaffold for review.
"""

from __future__ import annotations

import argparse
import json
import math
import re
from datetime import date, timedelta
from pathlib import Path
from typing import Any


AGENDA_KEYWORDS = ("agenda", "outline", "contents", "topics", "overview", "today")
MATH_CHARS = "αβγδεθλμπρστΣ∑√≤≥≈±∞∂"

MATH_REPLACEMENTS = {
    "α": r"\alpha", "β": r"\beta", "γ": r"\gamma", "δ": r"\delta",
    "ε": r"\epsilon", "θ": r"\theta", "λ": r"\lambda", "μ": r"\mu",
    "π": r"\pi", "ρ": r"\rho", "σ": r"\sigma", "τ": r"\tau",
    "ω": r"\omega", "Σ": r"\Sigma", "∑": r"\sum", "√": r"\sqrt{}",
    "≤": r"\le", "≥": r"\ge", "≈": r"\approx", "∈": r"\in",
    "→": r"\to", "⇒": r"\Rightarrow", "−": "-", "×": r"\times",
}

_ARROW_MARKER = "\x00\x00ARROW\x00\x00"
_UNICODE_PRE_ESCAPE = {
    "": _ARROW_MARKER,
    "": _ARROW_MARKER,
    "→": _ARROW_MARKER,
    "⇒": _ARROW_MARKER,
    "": "",
    "": "",
    "‑": "-",
    "–": "-",
    "—": "-",
}
_CHAR_ESCAPES = {
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


def latex_escape(text: Any) -> str:
    value = str(text)
    for src, dst in _UNICODE_PRE_ESCAPE.items():
        value = value.replace(src, dst)
    escaped = "".join(_CHAR_ESCAPES.get(ch, ch) for ch in value)
    return escaped.replace(_ARROW_MARKER, r"\(\to\)")


def block_text(block: str | dict) -> str:
    if isinstance(block, dict):
        return re.sub(r"\s+", " ", str(block.get("text", ""))).strip()
    return re.sub(r"\s+", " ", str(block)).strip()


def normalize_text_blocks(blocks: list) -> list[dict]:
    normalized: list[dict] = []
    for i, block in enumerate(blocks, start=1):
        if isinstance(block, dict):
            text = block_text(block)
            if not text:
                continue
            normalized.append(
                {
                    "order": int(block.get("order") or i),
                    "paragraph_index": int(block.get("paragraph_index") or 1),
                    "paragraph_level": int(block.get("paragraph_level") or 0),
                    "placeholder": str(block.get("placeholder", "")),
                    "shape_name": str(block.get("shape_name", "")),
                    "text": text,
                }
            )
        else:
            text = block_text(block)
            if text:
                normalized.append(
                    {
                        "order": i,
                        "paragraph_index": 1,
                        "paragraph_level": 0,
                        "placeholder": "",
                        "shape_name": "",
                        "text": text,
                    }
                )
    return sorted(normalized, key=lambda b: (b["order"], b["paragraph_index"]))


def slide_texts(slide: dict) -> list[str]:
    blocks = slide.get("plain_text_blocks")
    if blocks:
        return [block_text(b) for b in blocks if block_text(b)]
    return [b["text"] for b in normalize_text_blocks(slide.get("text_blocks", []))]


def title_from_blocks(blocks: list[str], fallback: str) -> str:
    for block in blocks:
        text = re.sub(r"\s+", " ", block).strip()
        if 3 <= len(text) <= 120 and not text.isdigit():
            return text[:100]
    return fallback


def source_label(slide: dict) -> str:
    stem = Path(slide.get("source_file", "")).stem
    stem = re.sub(r"[_-]Pre[_-]Sessional", "", stem, flags=re.I)
    stem = re.sub(r"[_-]+", " ", stem).strip()
    unit = "page" if slide.get("source_kind") == "page" else "slide"
    return f"{stem}, {unit} {slide.get('source_slide', '?')}"


def label_for_figure(path: str) -> str:
    stem = Path(path).stem.replace("_", "-")
    return f"fig:{stem}"


def is_url(text: str) -> bool:
    return bool(re.match(r"https?://", text.strip()))


def render_text_value(text: str) -> str:
    return r"\url{" + text.strip() + "}" if is_url(text) else latex_escape(text)


def is_formula_candidate(text: str) -> bool:
    if len(text) > 160:
        return False
    if "$" in text or "£" in text or "€" in text:
        return False
    wordy = re.findall(r"[A-Za-z]{5,}", text)
    if wordy and not any(ch in text for ch in MATH_CHARS):
        return False
    if any(ch in text for ch in MATH_CHARS):
        return True
    if re.search(r"^[A-Za-z][A-Za-z0-9_() ]{0,24}\s*=\s*[-+A-Za-z0-9()./%^ ]+$", text):
        return True
    if re.search(r"\b(VaR|ES|DD|PD|LGD|EAD|CAPM|Sharpe|Sortino)\b.*=", text):
        return True
    return False


def formula_to_latex(text: str) -> str:
    converted = text.strip()
    for source, target in MATH_REPLACEMENTS.items():
        converted = converted.replace(source, target)
    converted = converted.replace("²", "^2").replace("³", "^3")
    converted = converted.replace("%", r"\%")
    converted = converted.replace("&", r"\&")
    converted = re.sub(r"\s+", " ", converted).strip()
    return converted


def looks_fragmented(texts: list[str]) -> bool:
    if len(texts) < 8:
        return False
    short_count = sum(1 for text in texts if len(text) <= 12 or re.fullmatch(r"[\W\d]+", text))
    return short_count / len(texts) >= 0.45


def looks_like_true_list(blocks: list[dict]) -> bool:
    texts = [b["text"] for b in blocks]
    if len(texts) < 3 or looks_fragmented(texts):
        return False
    levels = {b.get("paragraph_level", 0) for b in blocks}
    placeholders = " ".join(b.get("placeholder", "") for b in blocks).lower()
    if levels != {0} or "body" in placeholders:
        return True
    short_count = sum(1 for text in texts if len(text) <= 120)
    sentence_count = sum(1 for text in texts if re.search(r"[.!?]\s+[A-Z]", text))
    return short_count / len(texts) >= 0.75 and sentence_count <= 1


def merge_fragments(texts: list[str]) -> list[str]:
    merged: list[str] = []
    for raw in texts:
        text = raw.strip()
        if not text or text in {".", ",", ":", ";", "-", "–", "—", "•"}:
            continue
        if not merged:
            merged.append(text)
            continue
        previous = merged[-1]
        join_previous = (
            len(text) <= 20
            and not previous.endswith((".", "?", "!", ";", ":"))
            and (
                text[0].islower()
                or previous.endswith(("=", "(", "/", "-"))
                or previous.lower().split()[-1:] in (["of"], ["and"], ["the"], ["to"], ["in"])
            )
        )
        if join_previous and len(previous) + len(text) <= 180:
            merged[-1] = f"{previous} {text}"
        else:
            merged.append(text)
    return merged


def chunk_paragraphs(texts: list[str], max_chars: int = 720) -> list[str]:
    paragraphs: list[str] = []
    current = ""
    for text in texts:
        candidate = f"{current} {text}".strip() if current else text
        if current and len(candidate) > max_chars:
            paragraphs.append(current)
            current = text
        else:
            current = candidate
    if current:
        paragraphs.append(current)
    return paragraphs


def render_itemize(texts: list[str]) -> str:
    lines = ["\\begin{itemize}\n"]
    for text in texts:
        lines.append(f"  \\item {render_text_value(text)}\n")
    lines.append("\\end{itemize}\n")
    return "".join(lines)


def excel_serial_to_date(value: str) -> str | None:
    if not re.fullmatch(r"\d{5}", value.strip()):
        return None
    serial = int(value)
    if not 20_000 <= serial <= 80_000:
        return None
    # Excel's serial day 1 is 1900-01-01, with the historical leap-year bug.
    return (date(1899, 12, 30) + timedelta(days=serial)).isoformat()


def format_cell(value: Any) -> str:
    text = str(value).strip()
    maybe_date = excel_serial_to_date(text)
    if maybe_date:
        return maybe_date
    try:
        number = float(text.replace(",", ""))
    except ValueError:
        return text
    if math.isfinite(number):
        if abs(number) >= 100:
            return f"{number:,.2f}".rstrip("0").rstrip(".")
        return f"{number:.4f}".rstrip("0").rstrip(".")
    return text


def render_longtable(headers: list[str], rows: list[list[Any]], caption: str, label: str) -> str:
    if not rows:
        return ""
    width = max(len(headers), *(len(row) for row in rows))
    headers = (headers + [f"Column {i}" for i in range(len(headers) + 1, width + 1)])[:width]
    col_spec = "p{0.24\\linewidth}" + "p{0.16\\linewidth}" * (width - 1)
    lines = [
        "\\begingroup\n",
        "\\small\n",
        "\\setlength{\\LTleft}{0pt}\n",
        "\\setlength{\\LTright}{0pt}\n",
        f"\\begin{{longtable}}{{{col_spec}}}\n",
        f"\\caption{{{latex_escape(caption)}}}\\label{{{label}}}\\\\\n",
        "\\toprule\n",
        " & ".join(latex_escape(h) for h in headers) + " \\\\\n",
        "\\midrule\n",
        "\\endfirsthead\n",
        "\\toprule\n",
        " & ".join(latex_escape(h) for h in headers) + " \\\\\n",
        "\\midrule\n",
        "\\endhead\n",
    ]
    for row in rows:
        padded = (row + [""] * width)[:width]
        lines.append(" & ".join(render_text_value(format_cell(cell)) for cell in padded) + " \\\\\n")
    lines.extend(["\\bottomrule\n", "\\end{longtable}\n", "\\endgroup\n"])
    return "".join(lines)


def render_native_tables(slide: dict) -> str:
    parts: list[str] = []
    for i, table in enumerate(slide.get("tables", []), start=1):
        rows = table.get("rows") or []
        if not rows:
            continue
        headers = [str(cell) for cell in rows[0]]
        body = rows[1:] if len(rows) > 1 else rows
        caption = f"Native PowerPoint table. Source: {source_label(slide)}."
        parts.append(render_longtable(headers, body, caption, f"tbl:slide-{slide.get('global_slide')}-{i}"))
    return "\n".join(parts)


def chart_rows(chart: dict) -> tuple[list[str], list[list[Any]]]:
    data = chart.get("chart_data") or {}
    series = data.get("series") or []
    if not series:
        return [], []
    categories: list[str] = []
    for serie in series:
        if serie.get("categories"):
            categories = serie["categories"]
            break
    max_len = max(len(serie.get("values", [])) for serie in series)
    if not categories:
        categories = [str(i + 1) for i in range(max_len)]
    headers = ["Category"] + [serie.get("name") or f"Series {i + 1}" for i, serie in enumerate(series)]
    rows: list[list[Any]] = []
    for i, category in enumerate(categories):
        row = [category]
        for serie in series:
            values = serie.get("values", [])
            row.append(values[i] if i < len(values) else "")
        rows.append(row)
    return headers, rows


def render_charts(slide: dict) -> str:
    parts: list[str] = []
    for i, chart in enumerate(slide.get("charts", []), start=1):
        if chart.get("status") != "data_extracted" or not chart.get("chart_data"):
            parts.append(
                "\\begin{reviewbox}{Chart Requires Agent Reconstruction}\n"
                f"Source: {latex_escape(source_label(slide))}. The native chart could not be extracted "
                "as structured data; inspect the slide evidence before final delivery.\n"
                "\\end{reviewbox}\n"
            )
            continue
        headers, rows = chart_rows(chart)
        title = chart.get("chart_data", {}).get("title") or "Extracted chart data"
        parts.append(
            render_longtable(
                headers,
                rows,
                f"{title}. Source: {source_label(slide)}.",
                f"tbl:chart-{slide.get('global_slide')}-{i}",
            )
        )
    return "\n".join(parts)


def render_text_blocks(slide: dict) -> str:
    blocks = normalize_text_blocks(slide.get("text_blocks", []))
    texts = slide_texts(slide)
    if not texts:
        return "\\begin{reviewbox}{No Text Extracted}\nNo text was extracted from this slide. Inspect figures or the original deck.\n\\end{reviewbox}\n"

    title = slide.get("slide_title") or ""
    body_texts = [text for text in texts if text != title]
    formula_texts = [text for text in body_texts if is_formula_candidate(text)]
    prose_texts = [text for text in body_texts if text not in formula_texts]

    parts: list[str] = []
    if looks_like_true_list(blocks):
        parts.append(render_itemize(merge_fragments(prose_texts)))
    else:
        for paragraph in chunk_paragraphs(merge_fragments(prose_texts)):
            parts.append(render_text_value(paragraph) + "\n\n")

    for formula in formula_texts[:8]:
        parts.append("\\begin{equation*}\n  " + formula_to_latex(formula) + "\n\\end{equation*}\n")
    if len(formula_texts) > 8:
        parts.append(
            "\\begin{reviewbox}{Additional Formula Candidates}\n"
            + "; ".join(latex_escape(f) for f in formula_texts[8:])
            + "\n\\end{reviewbox}\n"
        )
    if "fragmented_text" in slide.get("risk_flags", []):
        parts.append(
            "\\begin{reviewbox}{Fragmented Source Evidence}\n"
            "The source extraction looked fragmented. The Code Agent must inspect this slide packet "
            "and rewrite this block before final delivery.\n"
            "\\end{reviewbox}\n"
        )
    return "".join(parts)


def render_speaker_notes(notes: list[str]) -> str:
    clean = [block_text(note) for note in notes if block_text(note)]
    if not clean:
        return ""
    return (
        "\\begin{notesbox}{Speaker Notes}\n"
        + latex_escape(" ".join(clean))
        + "\n\\end{notesbox}\n"
    )


def render_figures(slide: dict, seen_figure_paths: set[str]) -> str:
    lines: list[str] = []
    for figure in slide.get("figures", []):
        if figure.get("status") != "keep":
            continue
        figure_path = figure.get("path")
        if not figure_path or figure_path in seen_figure_paths:
            continue
        seen_figure_paths.add(figure_path)
        slide_title = slide.get("slide_title") or title_from_blocks(slide_texts(slide), f"Slide {slide.get('source_slide', '?')}")
        caption = f"{slide_title}. Source: {source_label(slide)}."
        lines.append("\\begin{figure}[htbp]\n")
        lines.append("  \\centering\n")
        lines.append(
            "  \\includegraphics[width=0.72\\linewidth,height=0.42\\textheight,keepaspectratio]"
            f"{{{figure_path}}}\n"
        )
        lines.append("  \\caption{" + latex_escape(caption) + "}\n")
        lines.append("  \\label{" + label_for_figure(figure_path) + "}\n")
        lines.append("\\end{figure}\n")
    return "".join(lines)


def build_preamble(title: str, language: str) -> str:
    if language == "zh":
        heading = "Academic Lecture Notes"
        ctex = r"\usepackage[UTF8, zihao=-4, fontset=fandol]{ctex}" + "\n"
        toc_name = ""
        fig_name = ""
    else:
        heading = "Academic Lecture Notes"
        ctex = ""
        toc_name = r"\renewcommand{\contentsname}{Contents}" + "\n"
        fig_name = r"\renewcommand{\figurename}{Figure}" + "\n"
    return (
        "% ============================================================\n"
        "%  slides-to-latex scaffold — agent reconstruction required\n"
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
        "\\titleformat{\\section}{\\Large\\bfseries\\color{blue!65!black}}{\\thesection}{0.8em}{}[\\titlerule]\n"
        "\\titleformat{\\subsection}{\\large\\bfseries\\color{blue!45!black}}{\\thesubsection}{0.8em}{}\n"
        "\\titleformat{\\subsubsection}{\\normalsize\\bfseries\\color{black}}{\\thesubsubsection}{0.7em}{}\n"
        "\\pagestyle{fancy}\n"
        "\\setlength{\\headheight}{14pt}\n"
        "\\fancyhf{}\n"
        f"\\lhead{{\\small {latex_escape(title)}}}\n"
        f"\\rhead{{\\small {heading}}}\n"
        "\\cfoot{\\thepage}\n"
        "\\renewcommand{\\headrulewidth}{0.4pt}\n"
        + toc_name
        + fig_name
        + "\\newtcolorbox{notesbox}[1]{colback=gray!5,colframe=gray!55!black,title=#1,fonttitle=\\bfseries,arc=2pt,boxrule=0.3pt,breakable}\n"
        "\\newtcolorbox{reviewbox}[1]{colback=yellow!7,colframe=yellow!45!black,title=#1,fonttitle=\\bfseries,arc=2pt,boxrule=0.4pt,breakable}\n"
        "\\newtcolorbox{agentbox}[1]{colback=red!3,colframe=red!45!black,title=#1,fonttitle=\\bfseries,arc=2pt,boxrule=0.4pt,breakable}\n"
        "\\sloppy\n"
    )


def derive_section_title(source_file: str, first_slide: dict) -> str:
    title = first_slide.get("slide_title")
    if title and 3 <= len(str(title)) <= 120:
        return str(title)
    return title_from_blocks(slide_texts(first_slide), re.sub(r"[_-]+", " ", Path(source_file).stem).strip())


def is_agenda_slide(slide: dict, position_in_deck: int) -> bool:
    if position_in_deck > 4:
        return False
    texts = slide_texts(slide)
    if len(texts) < 3:
        return False
    candidates = " ".join([texts[0], str(slide.get("slide_title") or "")]).lower()
    return any(keyword in candidates for keyword in AGENDA_KEYWORDS)


def is_divider_slide(slide: dict) -> bool:
    texts = slide_texts(slide)
    if not texts or any(f.get("status") == "keep" for f in slide.get("figures", [])):
        return False
    total_words = sum(len(text.split()) for text in texts)
    if len(texts) <= 2 and 2 <= total_words <= 12:
        return not any(ch in " ".join(texts) for ch in MATH_CHARS + "=<>")
    return False


def render_slide(slide: dict, seen_figure_paths: set[str], position_in_deck: int) -> str:
    texts = slide_texts(slide)
    slide_title = slide.get("slide_title") or title_from_blocks(texts, f"Slide {slide.get('source_slide', '?')}")
    if is_divider_slide(slide):
        return "\n\\subsection{" + latex_escape(slide_title) + "}\n"

    lines = [
        "\n\\subsubsection*{"
        + latex_escape(f"Slide {slide.get('source_slide', '?')}: {slide_title}")
        + "}\n",
        "\\begin{agentbox}{Agent Reconstruction Required}\n",
        "This scaffold preserves source evidence. The Code Agent must rewrite it into final academic prose before delivery. ",
        f"Source: {latex_escape(source_label(slide))}.\n",
        "\\end{agentbox}\n",
    ]
    if is_agenda_slide(slide, position_in_deck):
        lines.append(render_itemize(merge_fragments([t for t in texts if t != slide_title])))
    else:
        lines.append(render_text_blocks(slide))
    lines.append(render_native_tables(slide))
    lines.append(render_charts(slide))
    lines.append(render_speaker_notes(slide.get("speaker_notes", [])))
    lines.append(render_figures(slide, seen_figure_paths))
    return "".join(lines)


def build_latex(data: dict, title: str, language: str = "en") -> str:
    lines = [build_preamble(title, language)]
    note = "Scaffold generated from structured slide evidence; Code Agent reconstruction required."
    lines.append("\\title{" + latex_escape(title) + r"\\[0.3em]{\normalsize Academic Lecture Notes}}" + "\n")
    lines.append(r"\author{slides-to-latex scaffold}" + "\n")
    lines.append(r"\date{\today}" + "\n")
    lines.append("\\begin{document}\n\\maketitle\n")
    lines.append("\\begin{agentbox}{Scaffold Notice}\n" + latex_escape(note) + "\n\\end{agentbox}\n")
    lines.append("\\tableofcontents\n\\newpage\n")

    file_first_slide: dict[str, dict] = {}
    deck_positions: dict[str, int] = {}
    for slide in data.get("slides", []):
        sf = Path(slide.get("source_file", "")).name
        file_first_slide.setdefault(sf, slide)

    current_file: str | None = None
    seen_figure_paths: set[str] = set()
    for slide in data.get("slides", []):
        source_file = Path(slide.get("source_file", "")).name
        if source_file != current_file:
            current_file = source_file
            deck_positions[source_file] = 0
            section_title = derive_section_title(source_file, file_first_slide.get(source_file, {}))
            lines.append("\n\\section{" + latex_escape(section_title) + "}\n")
        deck_positions[source_file] += 1
        lines.append(render_slide(slide, seen_figure_paths, deck_positions[source_file]))
    lines.append("\n\\end{document}\n")
    return "".join(lines)


def compact_slide_packet(slide: dict) -> dict:
    kept_figures = [
        {
            "path": figure.get("path"),
            "caption": figure.get("caption", ""),
            "status": figure.get("status"),
        }
        for figure in slide.get("figures", [])
        if figure.get("status") == "keep"
    ]
    return {
        "global_slide": slide.get("global_slide"),
        "source_file": slide.get("source_file"),
        "source_slide": slide.get("source_slide"),
        "slide_title": slide.get("slide_title"),
        "text_blocks": normalize_text_blocks(slide.get("text_blocks", [])),
        "plain_text_blocks": slide_texts(slide),
        "speaker_notes": slide.get("speaker_notes", []),
        "formula_candidates": slide.get("formula_candidates", []),
        "tables": slide.get("tables", []),
        "charts": slide.get("charts", []),
        "kept_figures": kept_figures,
        "risk_flags": slide.get("risk_flags", []),
    }


def build_reconstruction_packets(data: dict, title: str) -> dict:
    slide_by_id = {slide.get("global_slide"): slide for slide in data.get("slides", [])}
    packets: list[dict] = []
    for section in data.get("logical_sections", []):
        for packet in section.get("packets", []):
            packet_slides = [slide_by_id[sid] for sid in packet.get("slides", []) if sid in slide_by_id]
            packets.append(
                {
                    "packet_id": packet.get("packet_id"),
                    "course_title": title,
                    "section_title": section.get("title"),
                    "source_file": section.get("source_file"),
                    "slide_start": packet.get("slide_start"),
                    "slide_end": packet.get("slide_end"),
                    "agent_task": (
                        "Rewrite this packet into final academic LaTeX prose using the Code Agent's own LLM. "
                        "Do not call external APIs. Preserve all source information, convert formulas carefully, "
                        "and keep source slide references."
                    ),
                    "slides": [compact_slide_packet(slide) for slide in packet_slides],
                }
            )
    if not packets:
        packets.append(
            {
                "packet_id": "all-slides",
                "course_title": title,
                "section_title": title,
                "source_file": "",
                "slide_start": 1,
                "slide_end": len(data.get("slides", [])),
                "agent_task": "Rewrite this packet into final academic LaTeX prose using the Code Agent's own LLM.",
                "slides": [compact_slide_packet(slide) for slide in data.get("slides", [])],
            }
        )
    return {
        "schema": "slides-to-latex.reconstruction-packets.v1",
        "requires_external_api": False,
        "requires_code_agent_rewrite": True,
        "packets": packets,
    }


def infer_language(output: Path, explicit: str) -> str:
    if explicit != "auto":
        return explicit
    return "zh" if output.stem.endswith("-zh") else "en"


def scaffold_path_for(output: Path) -> Path:
    if output.stem.endswith(".scaffold"):
        return output
    return output.with_name(output.stem + ".scaffold" + output.suffix)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("content_manifest")
    parser.add_argument("--output", required=True)
    parser.add_argument("--title", default="Academic Lecture Notes")
    parser.add_argument("--language", choices=["auto", "en", "zh"], default="auto")
    parser.add_argument(
        "--packets-output",
        help="Optional reconstruction packet path. Defaults to <output-dir>/manifest/reconstruction_packets.json.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    manifest = Path(args.content_manifest).expanduser().resolve()
    output = Path(args.output).expanduser().resolve()
    data = json.loads(manifest.read_text(encoding="utf-8"))
    output.parent.mkdir(parents=True, exist_ok=True)

    language = infer_language(output, args.language)
    latex = build_latex(data, args.title, language)
    scaffold_output = scaffold_path_for(output)
    scaffold_output.write_text(latex, encoding="utf-8")
    if output != scaffold_output:
        output.write_text(latex, encoding="utf-8")

    packets_output = (
        Path(args.packets_output).expanduser().resolve()
        if args.packets_output
        else output.parent / "manifest" / "reconstruction_packets.json"
    )
    packets_output.parent.mkdir(parents=True, exist_ok=True)
    packets_output.write_text(
        json.dumps(build_reconstruction_packets(data, args.title), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    print(output)
    print(scaffold_output)
    print(packets_output)
    print(
        f"slides={data.get('slides_count', 0)} "
        f"figures={data.get('figures_count', 0)} "
        f"charts={data.get('charts_count', 0)} "
        "requires_agent_rewrite=true"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
