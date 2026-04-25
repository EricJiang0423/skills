#!/usr/bin/env python3
"""Regenerate ``agents/claude.md`` and ``agents/codex.yaml`` from ``SKILL.md``.

The ``description`` field lives in three files (``SKILL.md`` frontmatter,
``agents/claude.md`` frontmatter, ``agents/codex.yaml`` interface) and used to
drift. This script makes ``SKILL.md`` the single source of truth for
``name``/``description``/``short-description``; per-agent fields
(``default_prompt``, ``targets``, ``policy``) are preserved in place via
constants below.

Usage:
    python3 scripts/sync_agent_metadata.py [--check]

With ``--check``, exits 1 if the agent files are out of sync (intended for CI).
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "SKILL.md"
CLAUDE_MD = ROOT / "agents" / "claude.md"
CODEX_YAML = ROOT / "agents" / "codex.yaml"

DEFAULT_PROMPT = (
    "Use $slides-to-latex to rebuild my slide deck as academic bilingual "
    "LaTeX notes without keeping full-slide screenshots."
)
DISPLAY_NAME = "Slides to LaTeX"
SHORT_DESCRIPTION = "Rebuild slide decks as bilingual academic LaTeX notes"
CLAUDE_TARGETS = ("claude", "claude-code")


def parse_skill_frontmatter(text: str) -> dict[str, str]:
    match = re.match(r"^---\n(.*?)\n---", text, re.S)
    if not match:
        raise SystemExit("ERROR: SKILL.md has no YAML frontmatter.")
    body = match.group(1)
    fields: dict[str, str] = {}
    key: str | None = None
    buffer: list[str] = []

    def flush() -> None:
        if key is not None:
            fields[key] = " ".join(part.strip() for part in buffer).strip()

    for line in body.splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if re.match(r"^[A-Za-z][\w-]*\s*:", line) and not line.startswith(" "):
            flush()
            new_key, _, value = line.partition(":")
            key = new_key.strip()
            value = value.strip()
            if value in {">", "|", ">+", "|+", ">-", "|-"}:
                buffer = []
            else:
                buffer = [value]
        else:
            buffer.append(line)
    flush()
    return fields


def render_claude_md(name: str, description: str) -> str:
    description = description.strip().replace("\n", " ")
    targets = "\n".join(f"  - {t}" for t in CLAUDE_TARGETS)
    return (
        "---\n"
        f"name: {name}\n"
        f"display_name: \"{DISPLAY_NAME}\"\n"
        f"short_description: \"{SHORT_DESCRIPTION}\"\n"
        "description: >\n"
        f"  {description}\n"
        f"default_prompt: \"{DEFAULT_PROMPT}\"\n"
        "targets:\n"
        f"{targets}\n"
        "---\n"
        "\n"
        "Read `slides-to-latex/SKILL.md` from the repository root for the complete skill\n"
        "instructions, then follow those instructions to rebuild the user's slides as\n"
        "academic bilingual LaTeX notes.\n"
    )


def render_codex_yaml() -> str:
    return (
        "interface:\n"
        f"  display_name: \"{DISPLAY_NAME}\"\n"
        f"  short_description: \"{SHORT_DESCRIPTION}\"\n"
        f"  default_prompt: \"{DEFAULT_PROMPT}\"\n"
        "\n"
        "policy:\n"
        "  allow_implicit_invocation: true\n"
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--check", action="store_true", help="Exit 1 if agent files are out of sync.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    fields = parse_skill_frontmatter(SKILL.read_text(encoding="utf-8"))
    name = fields.get("name") or "slides-to-latex"
    description = fields.get("description") or SHORT_DESCRIPTION

    rendered_claude = render_claude_md(name, description)
    rendered_codex = render_codex_yaml()
    targets = [
        (CLAUDE_MD, rendered_claude),
        (CODEX_YAML, rendered_codex),
    ]

    drift = []
    for path, rendered in targets:
        current = path.read_text(encoding="utf-8") if path.exists() else ""
        if current != rendered:
            drift.append(path)

    if args.check:
        if drift:
            for path in drift:
                print(f"OUT OF SYNC: {path.relative_to(ROOT)}")
            return 1
        print("OK: agent metadata is in sync with SKILL.md.")
        return 0

    for path, rendered in targets:
        path.write_text(rendered, encoding="utf-8")
        print(f"wrote {path.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
