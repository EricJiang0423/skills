# QA Reference

Load this file before the final pass or when the user reports missing content, bad pages, headers, blank pages, or compile artifacts.

## Source Coverage Audit

- Confirm every expected week has a chapter file in each requested language.
- Compare chapter line counts and topic counts. A much shorter week needs re-reading unless the source is genuinely short.
- Search for empty shells:

```bash
rg "\\\\sub(section|subsection)\\{[^}]+\\}\\s*$" chapters-en chapters-cn chapters-bilingual
rg "TODO|TBD|placeholder|lorem|to be completed" .
```

- Check that all slide sections, practice questions, worked examples, tables, diagrams, caveats, and readings appear in the notes.
- Keep raw extracts in `extracted-txt/`; use them to answer later "are you sure this is complete?" questions.

## Numerical Fidelity

- For each formula-based example, verify source values from PPT/transcript/raw extract before finalizing.
- Do not silently substitute plausible numbers.
- If the source has inconsistent figures, write a short note explaining the convention or reconcile using the primary source.
- Typical high-risk items: VaR/ES, Cornish-Fisher, GARCH/FHS, drawdown, Sharpe/Sortino, Black-Litterman, Treynor-Black, futures roll, swaps, PCA, KMV, ETF/AP examples.

## Compile Pass

Run two passes for each requested main file:

```bash
xelatex -interaction=nonstopmode main.tex
xelatex -interaction=nonstopmode main.tex
xelatex -interaction=nonstopmode main_cn.tex
xelatex -interaction=nonstopmode main_cn.tex
xelatex -interaction=nonstopmode main_bilingual.tex
xelatex -interaction=nonstopmode main_bilingual.tex
```

Check logs:

```bash
rg "^!|LaTeX Error|Undefined control sequence|Missing .* inserted|Overfull \\\\hbox|Package fancyhdr Warning|Font Warning|There were undefined references" *.log
```

Fix before delivery:

- Any `!` error or undefined control sequence.
- `fancyhdr` headheight warnings.
- Overfull boxes that are visible, table-related, or larger than a few points.
- Missing citations, missing includes, undefined references, or missing fonts.

## Visual/Layout Checks

- Inspect pages named by the user and pages around long tables.
- Check for blank pages, clipped headers, page-number overlap, table overflow, and Chinese text indentation.
- Bilingual PDFs are longer; ensure the header still fits on dense pages.
- If screenshots show a bad page, identify the corresponding chapter source and fix the layout there, not only the main template.

## Cleanup

Clean recursively, including chapter directories. Prefer the bundled script:

```bash
scripts/latex_cleanup.sh .
```

Delete only LaTeX intermediates, never source `.tex`, raw extracts, or final PDFs.

## Final Report

Report the PDFs produced, the compile status, and any remaining source limitations. If content was reconciled from conflicting sources, mention the convention used.
