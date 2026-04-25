#!/usr/bin/env python3
"""Parse a XeLaTeX/pdfLaTeX log file and report actionable errors.

Usage:
    python3 verify_latex.py <path-to-log>
        — or —
    python3 verify_latex.py <path-to-tex>   (reads the corresponding .log)

Exits with status 0 if the log shows a successful compile, 1 if there are
errors that need attention, 2 if the log file cannot be found.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path


ERROR_RE = re.compile(r"^! (.+)$")
FILE_LINE_RE = re.compile(r"^l\.(\d+) (.*)$")
MISSING_FIG_RE = re.compile(r"File `([^']+)' not found", re.IGNORECASE)
UNDEFINED_REF_RE = re.compile(
    r"Reference `([^']+)' on page \d+ undefined|there were undefined references",
    re.IGNORECASE,
)
UNDEFINED_CTRL_RE = re.compile(r"Undefined control sequence\.?\s*(?:\n|$)")
MISSING_PKG_RE = re.compile(r"! LaTeX Error: File `([^']+)\.sty' not found")
FONT_WARN_RE = re.compile(r"(?:Font shape|fontspec error|Font .*? could not be found)")
OVERFULL_RE = re.compile(r"Overfull \\[hv]box .*?lines? (\d+)")
EQUATION_RE = re.compile(r"\\begin\{(?:equation\*?|align\*?)\}(.*?)\\end\{(?:equation\*?|align\*?)\}", re.S)
GRAPHICS_RE = re.compile(r"\\includegraphics(?:\[[^\]]*\])?\{([^}]+)\}")
ITEM_RE = re.compile(r"^\s*\\item\s+(.*)$", re.M)
BEGIN_TABLE_RE = re.compile(r"\\begin\{(tabularx?|longtable)\}")
TABLE_BLOCK_RE = re.compile(r"\\begin\{(?P<env>tabularx?|longtable)\}.*?\\end\{(?P=env)\}", re.S)
PLACEHOLDER_RE = re.compile(
    r"LLM_REWRITE_REQUIRED|TODO\(multimodal\)|multimodal_slide_latex_rewrite|"
    r"Agent Reconstruction Required|Scaffold Notice|\\begin\{agentbox\}",
    re.IGNORECASE,
)
UNICODE_MATH_RE = re.compile(r"[α-ωΑ-Ω∑√≤≥≈∈∉∂±∞×÷₀-₉⁰-⁹]")
HALF_LATEX_PATTERNS = [
    (
        re.compile(r"(?<!\\)\bsqrt\s*\("),
        "Suspicious raw sqrt(...) notation; use \\sqrt{...} in math mode.",
    ),
    (
        re.compile(r"(?<!\\)\bSigma(?:w|[A-Za-z])?\b"),
        "Suspicious raw Sigma notation; use \\Sigma or rewrite the formula.",
    ),
    (
        re.compile(r"(?<!\\)\b(?:alpha|beta|gamma|delta|theta|lambda|mu|pi|rho|sigma|tau)_[A-Za-z0-9]"),
        "Suspicious raw Greek-name subscript; use LaTeX Greek commands in math mode.",
    ),
    (
        re.compile(r"(?<!\\)\b(?:alpha|beta|gamma|delta|theta|lambda|mu|pi|rho|sigma|tau)\^[A-Za-z0-9]"),
        "Suspicious raw Greek-name superscript; use LaTeX Greek commands in math mode.",
    ),
]


def _unescaped_dollars(line: str) -> int:
    count = 0
    escaped = False
    for ch in line:
        if ch == "\\" and not escaped:
            escaped = True
            continue
        if ch == "$" and not escaped:
            count += 1
        escaped = False
    return count


def _line_number(text: str, index: int) -> int:
    return text[:index].count("\n") + 1


def _non_comment_lines(text: str):
    for line_no, line in enumerate(text.splitlines(), start=1):
        if line.lstrip().startswith("%"):
            continue
        yield line_no, line


def _brace_args(text: str, start: int) -> list[str]:
    args: list[str] = []
    index = start
    while index < len(text):
        while index < len(text) and text[index].isspace():
            index += 1
        if index >= len(text) or text[index] != "{":
            break
        depth = 0
        begin = index + 1
        while index < len(text):
            ch = text[index]
            if ch == "\\":
                index += 2
                continue
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    args.append(text[begin:index])
                    index += 1
                    break
            index += 1
        else:
            break
    return args


def _expand_star_columns(spec: str) -> str:
    pattern = re.compile(r"\*\{(\d+)\}\{([^{}]*)\}")
    previous = None
    current = spec
    while current != previous:
        previous = current
        current = pattern.sub(lambda m: m.group(2) * int(m.group(1)), current)
    return current


def _column_count(spec: str) -> int:
    spec = _expand_star_columns(spec)
    spec = re.sub(r"[@!><]\{[^{}]*\}", "", spec)
    count = 0
    index = 0
    while index < len(spec):
        ch = spec[index]
        if ch in "lcrX":
            count += 1
            index += 1
            continue
        if ch in "pmb" and index + 1 < len(spec) and spec[index + 1] == "{":
            count += 1
            depth = 0
            index += 1
            while index < len(spec):
                if spec[index] == "{":
                    depth += 1
                elif spec[index] == "}":
                    depth -= 1
                    if depth == 0:
                        index += 1
                        break
                index += 1
            continue
        index += 1
    return count


def _table_specs(text: str) -> list[tuple[int, str, str, int]]:
    specs: list[tuple[int, str, str, int]] = []
    for match in BEGIN_TABLE_RE.finditer(text):
        args = _brace_args(text, match.end())
        if not args:
            continue
        spec = args[-1]
        specs.append((_line_number(text, match.start()), match.group(1), spec, _column_count(spec)))
    return specs


def _normalize_table_row(row: str) -> str:
    row = re.sub(r"%.*", "", row)
    row = re.sub(
        r"\\(?:toprule|midrule|bottomrule|hline|endfirsthead|endhead|endfoot|endlastfoot)\b",
        " ",
        row,
    )
    row = re.sub(r"\\(?:caption|label)\{[^{}]*\}", " ", row)
    row = re.sub(r"\\(?:textbf|emph|textit)\{([^{}]*)\}", r"\1", row)
    row = re.sub(r"\\[a-zA-Z]+\*?(?:\[[^\]]*\])?(?:\{[^{}]*\})?", " ", row)
    row = re.sub(r"\s*&\s*", " | ", row)
    row = re.sub(r"\s+", " ", row).strip(" |")
    return row.strip()


def _duplicated_table_rows(text: str) -> list[tuple[int, str]]:
    duplicated: list[tuple[int, str]] = []
    for block in TABLE_BLOCK_RE.finditer(text):
        rows = [_normalize_table_row(row) for row in re.split(r"\\\\", block.group(0))]
        rows = [row for row in rows if len(row) >= 8 and "|" in row]
        seen: dict[str, int] = {}
        for row in rows:
            seen[row] = seen.get(row, 0) + 1
        for row, count in seen.items():
            if count >= 3:
                duplicated.append((_line_number(text, block.start()), row[:100]))
                break
    return duplicated


def _normalize_figure_path(path: str) -> str:
    return Path(path).as_posix().lstrip("./")


def _default_manifest(tex_path: Path) -> Path | None:
    candidate = tex_path.parent / "manifest" / "content_manifest.json"
    return candidate if candidate.exists() else None


def _figure_statuses(manifest_path: Path) -> dict[str, str]:
    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    statuses: dict[str, str] = {}

    def add(figure: dict) -> None:
        path = figure.get("path")
        status = figure.get("status")
        if not path or not status:
            return
        key = _normalize_figure_path(str(path))
        # Prefer "keep" if duplicate records disagree between top-level and slide-level entries.
        if statuses.get(key) == "keep":
            return
        statuses[key] = str(status)

    for figure in data.get("figures", []):
        if isinstance(figure, dict):
            add(figure)
    for slide in data.get("slides", []):
        if not isinstance(slide, dict):
            continue
        for figure in slide.get("figures", []):
            if isinstance(figure, dict):
                add(figure)
    return statuses


def categorize(log_text: str) -> dict[str, list[str]]:
    errors: list[str] = []
    missing_files: list[str] = []
    missing_packages: list[str] = []
    undefined_refs: list[str] = []
    undefined_cmds: list[str] = []
    font_issues: list[str] = []
    overfull: list[str] = []

    lines = log_text.splitlines()
    for i, line in enumerate(lines):
        err = ERROR_RE.match(line.strip())
        if err:
            # Keep only the error line plus any "l.N" location line that follows,
            # to avoid including the next error's text as "context".
            snippet = [line.strip()]
            for j in range(i + 1, min(i + 4, len(lines))):
                nxt = lines[j].strip()
                if not nxt:
                    continue
                if nxt.startswith("!"):
                    break
                snippet.append(nxt)
                if nxt.startswith("l."):
                    break
            errors.append(" | ".join(snippet))
        m = MISSING_FIG_RE.search(line)
        if m:
            missing_files.append(m.group(1))
        m = MISSING_PKG_RE.search(line)
        if m:
            missing_packages.append(m.group(1))
        if UNDEFINED_REF_RE.search(line):
            undefined_refs.append(line.strip())
        if UNDEFINED_CTRL_RE.search(line):
            tail = " ".join(lines[i + 1 : i + 3]).strip()
            undefined_cmds.append(tail or line.strip())
        if FONT_WARN_RE.search(line):
            font_issues.append(line.strip())
        m = OVERFULL_RE.search(line)
        if m:
            overfull.append(line.strip())

    return {
        "errors": errors,
        "missing_files": sorted(set(missing_files)),
        "missing_packages": sorted(set(missing_packages)),
        "undefined_refs": undefined_refs[:10],
        "undefined_cmds": undefined_cmds[:10],
        "font_issues": font_issues[:10],
        "overfull": overfull[:10],
    }


def format_report(summary: dict[str, list[str]]) -> str:
    out: list[str] = []
    if summary["errors"]:
        out.append(f"❌  {len(summary['errors'])} error(s):")
        for e in summary["errors"][:10]:
            out.append(f"    {e}")
    if summary["missing_packages"]:
        out.append("❌  Missing LaTeX packages (install via TeX Live / MiKTeX):")
        for p in summary["missing_packages"]:
            out.append(f"    - {p}.sty")
    if summary["missing_files"]:
        out.append("❌  Missing files (check figures/ path and extension):")
        for f in summary["missing_files"]:
            out.append(f"    - {f}")
    if summary["undefined_cmds"]:
        out.append("⚠   Undefined control sequences:")
        for c in summary["undefined_cmds"]:
            out.append(f"    {c}")
    if summary["undefined_refs"]:
        out.append("⚠   Undefined refs (may resolve after second xelatex run):")
        for r in summary["undefined_refs"]:
            out.append(f"    {r}")
    if summary["font_issues"]:
        out.append("⚠   Font issues (check ctex/fontset=fandol on macOS):")
        for f in summary["font_issues"]:
            out.append(f"    {f}")
    if summary["overfull"]:
        out.append(f"ℹ   {len(summary['overfull'])} overfull box warning(s) (cosmetic)")
    if not any(out):
        out.append("✓  No errors detected.")
    return "\n".join(out)


def static_quality_checks(tex_path: Path, manifest_path: Path | None = None) -> dict[str, list[str]]:
    if tex_path.suffix != ".tex" or not tex_path.exists():
        return {"quality_errors": [], "quality_warnings": []}

    text = tex_path.read_text(encoding="utf-8", errors="replace")
    errors: list[str] = []
    warnings: list[str] = []
    stem = tex_path.stem

    if stem.endswith("-en") and re.search(r"\\usepackage(?:\[[^\]]*\])?\{ctex\}", text):
        errors.append("English output uses ctex; use the English template instead.")
    if stem.endswith("-en") and ("\\contentsname}{\u76ee\u5f55}" in text or "\\figurename}{\u56fe}" in text):
        errors.append("English output contains Chinese TOC/figure labels.")

    if "agent reconstruction required" in text.lower() or "\\begin{agentbox}" in text:
        errors.append("Output is still a scaffold; Code Agent reconstruction has not been completed.")
    if PLACEHOLDER_RE.search(text):
        errors.append("Output still contains multimodal rewrite placeholders or scaffold markers.")

    toc_path = tex_path.with_suffix(".toc")
    if "\\tableofcontents" in text and toc_path.exists() and toc_path.stat().st_size == 0:
        errors.append(f"Table of contents is empty: {toc_path.name}. Run xelatex twice and confirm sections are written.")

    for line_no, line in _non_comment_lines(text):
        if _unescaped_dollars(line) % 2 == 1:
            errors.append(f"Unbalanced dollar sign on line {line_no}: {line.strip()[:120]}")
            if len(errors) >= 20:
                break

    for line_no, line in _non_comment_lines(text):
        match = UNICODE_MATH_RE.search(line)
        if match:
            errors.append(
                f"Residual Unicode/math glyph on line {line_no}: '{match.group(0)}'. Rewrite as LaTeX math."
            )
            if len(errors) >= 20:
                break

    without_comments = "\n".join(line for _, line in _non_comment_lines(text))
    for pattern, message in HALF_LATEX_PATTERNS:
        match = pattern.search(without_comments)
        if match:
            warnings.append(f"{message} First occurrence near line {_line_number(without_comments, match.start())}.")

    for match in EQUATION_RE.finditer(text):
        body = re.sub(r"\\[a-zA-Z]+(?:\{[^}]*\})?", " ", match.group(1))
        words = re.findall(r"[A-Za-z]{4,}", body)
        math_ops = re.findall(r"[=+\-*/^_<>]|\\(?:alpha|beta|sigma|mu|rho|lambda|sum|sqrt)", match.group(1))
        if len(words) >= 5 and len(math_ops) <= 1:
            line_no = text[: match.start()].count("\n") + 1
            errors.append(f"Natural language appears inside display math near line {line_no}.")
            if len(errors) >= 20:
                break

    missing_figures = []
    for figure_path in GRAPHICS_RE.findall(text):
        if figure_path.startswith("#"):
            continue
        candidate = tex_path.parent / figure_path
        if not candidate.exists():
            missing_figures.append(figure_path)
    for figure_path in sorted(set(missing_figures))[:20]:
        errors.append(f"Missing figure referenced by LaTeX: {figure_path}")

    resolved_manifest = manifest_path or _default_manifest(tex_path)
    if manifest_path and not manifest_path.exists():
        errors.append(f"Manifest file not found: {manifest_path}")
    elif resolved_manifest and resolved_manifest.exists():
        try:
            statuses = _figure_statuses(resolved_manifest)
        except (OSError, json.JSONDecodeError) as exc:
            errors.append(f"Could not read figure manifest {resolved_manifest}: {exc}")
            statuses = {}
        if statuses:
            included = {_normalize_figure_path(path) for path in GRAPHICS_RE.findall(text) if not path.startswith("#")}
            keep = {path for path, status in statuses.items() if status == "keep"}
            forbidden = {
                path for path, status in statuses.items()
                if status in {"drop", "review"}
            }
            for path in sorted(included & forbidden)[:20]:
                errors.append(f"LaTeX includes a figure that manifest marks drop/review: {path}")
            missing_keep = sorted(keep - included)
            if missing_keep:
                errors.append(
                    "Manifest keep figure(s) missing from LaTeX: " + ", ".join(missing_keep[:10])
                )
            manifest_known = set(statuses)
            unknown_includes = sorted(included - manifest_known)
            if unknown_includes:
                warnings.append(
                    "LaTeX includes figure(s) not present in manifest: " + ", ".join(unknown_includes[:10])
                )
            included_manifest = included & manifest_known
            if len(included_manifest) != len(keep):
                errors.append(
                    f"Figure count mismatch: LaTeX includes {len(included_manifest)} manifest figure(s), "
                    f"manifest marks {len(keep)} keep."
                )

    for line_no, env, spec, count in _table_specs(text):
        if count > 12:
            errors.append(f"{env} near line {line_no} has {count} columns; rebuild/split the table for readability.")
        elif count > 8:
            warnings.append(f"{env} near line {line_no} has {count} columns; check readability against the slide.")

    for line_no, row in _duplicated_table_rows(text)[:10]:
        warnings.append(f"Possible duplicated table row near line {line_no}: {row}")

    items = [item.strip() for item in ITEM_RE.findall(text)]
    if len(items) >= 80:
        short = [
            item for item in items
            if len(item) <= 8 or re.fullmatch(r"[^A-Za-z]{1,16}", item)
        ]
        if len(short) / len(items) >= 0.12:
            errors.append(
                f"Fragmented itemize output detected: {len(short)} very short items out of {len(items)}."
            )

    review_count = text.count("\\begin{reviewbox}")
    if review_count > 25:
        warnings.append(f"High reviewbox count ({review_count}); final output likely still needs human/agent reconstruction.")

    return {"quality_errors": errors, "quality_warnings": warnings}


def format_quality_report(summary: dict[str, list[str]]) -> str:
    out: list[str] = []
    if summary["quality_errors"]:
        out.append(f"❌  {len(summary['quality_errors'])} quality gate error(s):")
        for item in summary["quality_errors"][:20]:
            out.append(f"    {item}")
    if summary["quality_warnings"]:
        out.append(f"⚠   {len(summary['quality_warnings'])} quality warning(s):")
        for item in summary["quality_warnings"][:10]:
            out.append(f"    {item}")
    if not out:
        out.append("✓  Static quality gates passed.")
    return "\n".join(out)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Parse a LaTeX .log for errors.")
    parser.add_argument("path", help="Path to .log (or .tex — will read the sibling .log).")
    parser.add_argument(
        "--manifest",
        help="Optional content_manifest.json for figure keep/drop consistency checks.",
    )
    parser.add_argument(
        "--static-only",
        action="store_true",
        help="Run only static quality gates; do not require a sibling .log file.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    target = Path(args.path).expanduser().resolve()
    manifest_path = Path(args.manifest).expanduser().resolve() if args.manifest else None
    log_path = target if target.suffix == ".log" else target.with_suffix(".log")
    if args.static_only:
        tex_path = target if target.suffix == ".tex" else log_path.with_suffix(".tex")
        quality = static_quality_checks(tex_path, manifest_path)
        print(format_quality_report(quality))
        return 1 if quality["quality_errors"] else 0

    if not log_path.exists():
        print(f"ERROR: log file not found: {log_path}", file=sys.stderr)
        return 2

    text = log_path.read_text(encoding="utf-8", errors="replace")
    summary = categorize(text)
    print(format_report(summary))
    quality = static_quality_checks(target if target.suffix == ".tex" else log_path.with_suffix(".tex"), manifest_path)
    print(format_quality_report(quality))

    has_errors = bool(
        summary["errors"]
        or summary["missing_files"]
        or summary["missing_packages"]
        or summary["undefined_cmds"]
        or quality["quality_errors"]
    )
    return 1 if has_errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
