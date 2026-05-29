---
name: lecture-to-latex
description: "Convert lecture slides, transcripts, teacher solutions, and existing course material into source-faithful English, Chinese, and bilingual LaTeX lecture notes. Use for slides-to-notes, PPTX/PDF to LaTeX, bilingual notes, multi-week course notes, exam-style exercise booklets, AllExercises extraction, 讲义, 课件转LaTeX, 双语笔记, 例题整理."
workflow_stage: writing
compatibility:
  - claude-code
author: Eric Jiang
version: 1.2.0
tags:
  - LaTeX
  - pdf
  - pptx
  - lecture-notes
  - bilingual
  - academia
  - chinese
  - exercises
---
# Lecture to LaTeX

Create complete, source-faithful course notes from lecture PDFs/PPTX/transcripts and related material. The default deliverables are English notes, Chinese notes, and optionally a bilingual parallel version; when exam preparation is in scope, also create an `AllExercises` booklet.

## Core Rules

- Build from sources, not memory. Extract raw text and keep it in `extracted-txt/` for later checks.
- For multi-week courses, make a source map before writing: week number, source files, transcript/teacher-solution availability, and expected topic list.
- Do not declare completion while any week has empty headings, unusually thin content, missing examples, or unresolved source conflicts.
- Verify every numerical worked example against PPT/transcript/raw extract. If two sources disagree, prefer the primary source and explain the bridge in the notes.
- Compile every requested PDF, inspect logs, fix layout problems, then recursively clean LaTeX intermediates.

## Output Contract

Use this structure unless the existing project already has a compatible layout:

```text
LectureNotes/
├── main.tex
├── main_cn.tex
├── main_bilingual.tex              # optional
├── chapters-en/
│   └── weekN.tex
├── chapters-cn/
│   └── weekN_cn.tex
├── chapters-bilingual/             # optional
│   └── weekN_bilingual.tex
└── extracted-txt/
    ├── weekN_pptx_extracted.txt
    └── source_map.md               # recommended for multi-week work
```

Copy the templates from `resources/templates/` before writing new projects:

- `main_en.tex` -> `main.tex`
- `main_cn.tex` -> `main_cn.tex`
- `main_bilingual.tex` -> `main_bilingual.tex`

## Workflow

1. **Inventory sources**
   - Locate all lecture PDFs/PPTX, transcripts, teacher solutions, readings, prior notes, and mock/exam files.
   - Infer the week/module list from filenames and slide titles.
   - For each week, record expected sources and topics in `extracted-txt/source_map.md` or an equivalent working checklist.

2. **Extract raw content**
   - PDF: use `pdftotext` first, even for slide PDFs with images.
   - PPTX: use `scripts/extract_pptx_text.py` or a `python-pptx` equivalent, saving one raw extract per lecture.
   - Image-only material: use OCR only after confirming `pdftotext` is insufficient.

3. **Plan coverage before drafting**
   - Read extracts in chunks and map slide titles, examples, formula blocks, tables, reading lists, and practice questions.
   - Compare week lengths and heading density. A week with only shells or much less content than neighboring weeks needs source re-reading.

4. **Write notes**
   - English chapters go in `chapters-en/weekN.tex`; Chinese chapters go in `chapters-cn/weekN_cn.tex`.
   - Bilingual chapters go in `chapters-bilingual/weekN_bilingual.tex` and alternate `english` / `cnblock` blocks.
   - Preserve all substantive slide content, including caveats, labels, footnotes, and numerical assumptions.
   - Use concise prose to connect fragmented slide bullets; do not invent unsupported derivations or numbers.

5. **Apply formatting standards**
   - Read `references/formatting.md` when creating or repairing LaTeX layout.
   - Use `xelatex` for English, Chinese, and bilingual notes.
   - Chinese notes use `ctexart`, `fontset=none`, Songti SC, and `\parindent=0pt`.
   - Bilingual notes use `cnblock`; never define a `chinese` environment under `ctexart`.

6. **Optional exercise booklet**
   - If the user asks for exam prep, mock answers, or all worked examples, read `references/exercises.md`.
   - Audit every week before claiming `AllExercises` is complete.

7. **Compile and QA**
   - Read `references/qa.md` before the final pass.
   - Run `xelatex -interaction=nonstopmode` twice for each requested main file.
   - Check logs for errors, meaningful overfull boxes, missing refs, headheight warnings, and font warnings.
   - Inspect reported bad pages, blank pages, and header overflow.
   - Clean LaTeX intermediates recursively, including files emitted inside chapter directories. Prefer `scripts/latex_cleanup.sh`.

## Common Failure Modes

- Missing week content: a chapter compiles but contains only headings or a few slide titles.
- Numeric drift: formulas/examples copied from memory instead of PPT/transcript values.
- Header overflow: long course titles in `fancyhdr`; use short marks or static bilingual headers.
- CJK environment collision: `ctexart` already defines `\chinese`; use `cnblock`.
- TikZ arrow failure: use `arrows.meta` and `>=Stealth`, not legacy `-latex'`.
- Wide reference tables: use bibliography-style lists for readings and links.
- Exercise undercoverage: `AllExercises` includes a few representative questions but misses lecture worked examples.

## References

- `references/formatting.md`: LaTeX style, Chinese/bilingual conventions, tables, headings, TikZ, references.
- `references/qa.md`: source coverage audit, compile checks, visual/layout QA, cleanup.
- `references/exercises.md`: `AllExercises` extraction rules and booklet modes.
