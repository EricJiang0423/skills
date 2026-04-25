#!/usr/bin/env python3
"""Validate this folder as a Codex skill package."""

from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MACOS_DATALESS_FLAG = 0x40000000


def fail(message: str) -> str:
    return f"ERROR: {message}"


def read(path: Path) -> str:
    if is_dataless(path):
        return ""
    return path.read_text(encoding="utf-8", errors="replace")


def is_dataless(path: Path) -> bool:
    try:
        return bool(getattr(path.stat(), "st_flags", 0) & MACOS_DATALESS_FLAG)
    except OSError:
        return False


def parse_frontmatter(text: str) -> dict[str, str]:
    if not text.startswith("---\n"):
        return {}
    end = text.find("\n---", 4)
    if end == -1:
        return {}
    frontmatter = text[4:end]
    values: dict[str, str] = {}
    for line in frontmatter.splitlines():
        if ":" not in line or line.startswith(" "):
            continue
        key, value = line.split(":", 1)
        values[key.strip()] = value.strip().strip('"')
    return values


def frontmatter_text(text: str) -> str:
    if not text.startswith("---\n"):
        return ""
    end = text.find("\n---", 4)
    if end == -1:
        return ""
    return text[4:end]


def validate() -> list[str]:
    errors: list[str] = []

    skill_md = ROOT / "SKILL.md"
    openai_yaml = ROOT / "agents" / "openai.yaml"
    required = [
        skill_md,
        openai_yaml,
        ROOT / "references" / "latex-template.tex",
        ROOT / "references" / "latex-template-zh.tex",
        ROOT / "scripts" / "extract_pptx_assets.py",
        ROOT / "scripts" / "extract_pdf_figures.py",
        ROOT / "scripts" / "build_content_manifest.py",
        ROOT / "scripts" / "build_academic_latex.py",
        ROOT / "scripts" / "render_slide_images.py",
        ROOT / "scripts" / "build_multimodal_rewrite_queue.py",
        ROOT / "scripts" / "init_rewrite_fragments.py",
        ROOT / "scripts" / "assemble_rewrite_fragments.py",
        ROOT / "scripts" / "verify_latex.py",
    ]
    for path in required:
        if not path.exists():
            errors.append(fail(f"missing required file: {path.relative_to(ROOT)}"))

    if skill_md.exists():
        skill_text = read(skill_md)
        values = parse_frontmatter(skill_text)
        raw_frontmatter = frontmatter_text(skill_text)
        if values.get("name") != "slides-to-latex":
            errors.append(fail("SKILL.md frontmatter must set name: slides-to-latex"))
        description = raw_frontmatter
        if "slides" not in description.lower() and "deck" not in description.lower():
            errors.append(fail("SKILL.md description should clearly trigger on slide/deck conversion"))

    if openai_yaml.exists():
        yaml = read(openai_yaml)
        for key in ("display_name", "short_description", "default_prompt"):
            if key not in yaml:
                errors.append(fail(f"agents/openai.yaml missing interface.{key}"))
        if "$slides-to-latex" not in yaml:
            errors.append(fail("agents/openai.yaml default_prompt must mention $slides-to-latex"))
        if "allow_implicit_invocation: true" not in yaml:
            errors.append(fail("agents/openai.yaml should allow implicit invocation"))

    forbidden = []
    for path in ROOT.rglob("*"):
        if "__pycache__" in path.parts or path.suffix == ".pyc":
            forbidden.append(path.relative_to(ROOT))
    if forbidden:
        errors.append(fail("debug bytecode/cache artifacts present: " + ", ".join(map(str, forbidden[:10]))))

    return errors


def main() -> int:
    errors = validate()
    if errors:
        print("\n".join(errors), file=sys.stderr)
        return 1
    print(f"OK: {ROOT} is a Codex-compatible slides-to-latex skill.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
