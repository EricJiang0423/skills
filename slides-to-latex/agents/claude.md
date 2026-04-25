---
name: slides-to-latex
display_name: "Slides to LaTeX"
short_description: "Rebuild slide decks as bilingual academic LaTeX notes"
description: >
  Convert lecture slides, PDF decks, PPT files, and PPTX files into academic
  LaTeX study notes. Use this skill when the user asks to convert slides to
  LaTeX, rebuild lecture decks as academic notes, rewrite formulas, extract
  figures, avoid full-slide screenshots, or produce bilingual English and
  Chinese LaTeX outputs. The output must reconstruct prose, formulas, tables,
  and figures instead of pasting rendered slide images into the final PDF.
default_prompt: "Use $slides-to-latex to rebuild my slide deck as academic bilingual LaTeX notes without keeping full-slide screenshots."
targets:
  - claude
  - claude-code
---

Read `slides-to-latex/SKILL.md` from the repository root for the complete skill
instructions, then follow those instructions to rebuild the user's slides as
academic bilingual LaTeX notes.
