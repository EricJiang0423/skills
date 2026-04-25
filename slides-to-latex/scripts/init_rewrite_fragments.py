#!/usr/bin/env python3
"""Create one editable LaTeX fragment file per multimodal rewrite task."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any


def latex_comment(value: Any) -> str:
    text = re.sub(r"\s+", " ", str(value)).strip()
    return text.replace("\n", " ")


def fragment_stem(task: dict[str, Any], index: int) -> str:
    slide_no = task.get("global_slide") or index
    try:
        numeric = int(slide_no)
    except (TypeError, ValueError):
        numeric = index
    return f"page-{numeric:04d}"


def load_tasks(queue_path: Path) -> list[dict[str, Any]]:
    tasks: list[dict[str, Any]] = []
    with queue_path.open("r", encoding="utf-8") as handle:
        for line_no, line in enumerate(handle, start=1):
            stripped = line.strip()
            if not stripped:
                continue
            try:
                task = json.loads(stripped)
            except json.JSONDecodeError as exc:
                raise SystemExit(f"Invalid JSONL on line {line_no}: {exc}") from exc
            tasks.append(task)
    if not tasks:
        raise SystemExit(f"No rewrite tasks found: {queue_path}")
    return tasks


def placeholder_fragment(task: dict[str, Any]) -> str:
    title = task.get("slide_title") or f"Slide {task.get('source_slide', '?')}"
    focus = ", ".join(task.get("quality_focus", [])) or "general reconstruction"
    return (
        "% slides-to-latex fragment\n"
        f"% task_type: {latex_comment(task.get('task_type', ''))}\n"
        f"% global_slide: {latex_comment(task.get('global_slide', ''))}\n"
        f"% source_file: {latex_comment(task.get('source_file', ''))}\n"
        f"% source_slide: {latex_comment(task.get('source_slide', ''))}\n"
        f"% rendered_slide: {latex_comment(task.get('rendered_slide', ''))}\n"
        f"% quality_focus: {latex_comment(focus)}\n"
        "% LLM_REWRITE_REQUIRED\n"
        f"\\subsubsection*{{Slide {task.get('source_slide', '?')}: {title}}}\n"
        "% TODO(multimodal): Inspect the rendered slide image and task evidence, then replace this\n"
        "% entire placeholder with final academic LaTeX body content for this slide/page.\n"
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Initialize editable per-page LaTeX fragments.")
    parser.add_argument("queue", help="Path to multimodal_rewrite_queue.jsonl.")
    parser.add_argument("--output-dir", required=True, help="Directory for page-XXXX.tex fragments.")
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Overwrite existing fragment files. By default existing files are preserved.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    queue_path = Path(args.queue).expanduser().resolve()
    output_dir = Path(args.output_dir).expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    tasks = load_tasks(queue_path)
    manifest: list[dict[str, Any]] = []
    created = 0
    preserved = 0
    for index, task in enumerate(tasks, start=1):
        stem = fragment_stem(task, index)
        tex_path = output_dir / f"{stem}.tex"
        task_path = output_dir / f"{stem}.task.json"
        if args.overwrite or not tex_path.exists():
            tex_path.write_text(placeholder_fragment(task), encoding="utf-8")
            created += 1
        else:
            preserved += 1
        if args.overwrite or not task_path.exists():
            task_path.write_text(json.dumps(task, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        manifest.append(
            {
                "index": index,
                "fragment": tex_path.name,
                "task": task_path.name,
                "global_slide": task.get("global_slide"),
                "source_file": task.get("source_file"),
                "source_kind": task.get("source_kind"),
                "source_slide": task.get("source_slide"),
                "slide_title": task.get("slide_title", ""),
                "rendered_slide": task.get("rendered_slide", ""),
                "quality_focus": task.get("quality_focus", []),
            }
        )

    (output_dir / "fragment_manifest.json").write_text(
        json.dumps(
            {
                "schema": "slides-to-latex.rewrite-fragments.v1",
                "queue": str(queue_path),
                "fragments": manifest,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    print(f"Wrote {output_dir}: {created} fragment(s) created, {preserved} preserved.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
