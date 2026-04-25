---
name: slides-to-latex
description: >
  Convert lecture slides, PDF decks, PPT files, and PPTX files into academic
  LaTeX study notes. Use this skill when the user asks to convert slides to
  LaTeX, rebuild lecture decks as academic notes, rewrite formulas, extract
  figures, avoid full-slide screenshots, or produce bilingual English and
  Chinese LaTeX outputs. The output must reconstruct prose, formulas, tables,
  and figures instead of pasting rendered slide images into the final PDF.
metadata:
  short-description: Slides/PDF to academic LaTeX notes
---

# Slides to Academic LaTeX

Rebuild PDF/PPT/PPTX lecture slides as academic LaTeX documents. One English
version (`-en.tex`) is generated first; one Chinese translation (`-zh.tex`) is
generated from the verified English version. The final documents must not retain
full-slide screenshots — rendered pages are temporary QA evidence only. Rewrite
the source into academic prose, LaTeX formulas, rebuilt tables, and properly
captioned academic figures.

Intelligent reconstruction is performed by the Code Agent itself: scripts produce
structured evidence and reconstruction packets; the agent reads those packets and
writes final LaTeX in-context. **Never ask the user for OpenAI/Anthropic API
keys.** XML/PDF extraction is evidence only — before delivery the agent must do
a page-by-page multimodal rewrite using both rendered slide images and extracted
evidence.

---

## Dependencies

Core: **Pillow** and **pdfplumber** (`pip install -r requirements.txt`).

Optional:
- `pytesseract` + `tesseract` binary — OCR for figure classification
- Poppler (`pdfimages`, `pdftoppm`) — embedded image extraction and PDF rendering
- ImageMagick (`convert`) or LibreOffice — EMF/WMF → PNG conversion

See `requirements.txt` for exact versions and installation notes.

---

## Quick Reference (scripts only)

| Task | Command |
| --- | --- |
| Collect inputs | `python3 scripts/collect_slide_inputs.py "<input>" --manifest "<work>/input_manifest.json"` |
| Extract PPTX content and images | `python3 scripts/extract_pptx_assets.py "<deck.pptx>" --output-dir "<out>"` |
| Extract PDF text/tables/images | `python3 scripts/extract_pdf_figures.py "<slides.pdf>" --output-dir "<out>"` |
| Build content manifest | `python3 scripts/build_content_manifest.py "<out>/manifest/*-extraction.json" --output "<out>/manifest/content_manifest.json"` |
| Render per-page QA images | `python3 scripts/render_slide_images.py "<input-or-manifest>" --output-dir "<tmp>/qa-rendered" --pdf-dir "<tmp>/qa-pdf"` |
| Build the multimodal rewrite queue | `python3 scripts/build_multimodal_rewrite_queue.py "<out>/manifest/content_manifest.json" --output "<out>/manifest/multimodal_rewrite_queue.jsonl" --render-dir "<tmp>/qa-rendered" --render-manifest "<tmp>/qa-rendered/render_manifest.json"` |
| Initialize per-page LaTeX fragments | `python3 scripts/init_rewrite_fragments.py "<out>/manifest/multimodal_rewrite_queue.jsonl" --output-dir "<out>/rewrite_fragments"` |
| Generate scaffold and packets | `python3 scripts/build_academic_latex.py "<out>/manifest/content_manifest.json" --output "<out>/<name>-en.scaffold.tex" --title "<course name>"` |
| Assemble final English document | `python3 scripts/assemble_rewrite_fragments.py "<out>/rewrite_fragments" --output "<out>/<name>-en.tex" --title "<course name>" --language en` (figure-count alignment is enforced; pass `--manifest <path>` to override the default `<out>/manifest/content_manifest.json` lookup) |
| PPTX visual QA fallback | `python3 scripts/convert_presentation_to_pdf.py "<deck.pptx>" --output-dir "<work>/qa-pdf"` |
| Final compile | `xelatex -output-directory=build -interaction=nonstopmode -halt-on-error "<name>.tex"` (run twice) |
| Quality diagnostics | `python3 scripts/verify_latex.py "<name>.tex" --manifest "<out>/manifest/content_manifest.json"` (use `--static-only` before compilation) |
| Final PDF screenshot QA | `pdftoppm -png -r 144 "<name>-en.pdf" "<tmp>/final-render/en-page"` and same for `-zh.pdf` |
| Cleanup before delivery | `python3 scripts/cleanup_output.py "<out>"` |
| Sync agent metadata from SKILL frontmatter | `python3 scripts/sync_agent_metadata.py` (`--check` for CI) |

The agent-driven steps (multimodal page rewrite, parallel translation, parallel
polish, screenshot inspection) are described in **Workflow** below.

---

## Output Contract

### Folder input

```text
<input-folder>/slides-to-latex-output/
├── <folder-name>-en.tex           ← English version (generated first)
├── <folder-name>-en.scaffold.tex  ← scaffold (intermediate; keep for reference)
├── <folder-name>-en.pdf
├── <folder-name>-zh.tex           ← Chinese version (translated from English)
├── <folder-name>-zh.pdf
├── build/                         ← XeLaTeX aux files (.aux .log .out .toc)
├── rewrite_fragments/             ← per-page LaTeX fragments (page-XXXX.tex)
├── figures/
└── manifest/
    ├── input_manifest.json
    ├── content_manifest.json
    ├── reconstruction_packets.json
    └── extraction_manifest.json
```

Compile with `xelatex -output-directory=build` so aux files land in `build/`.
Copy the finished PDF from `build/` to the root.

### Single file input

```text
<input-stem>-latex/
├── <input-stem>-en.tex
├── <input-stem>-en.pdf
├── <input-stem>-zh.tex
├── <input-stem>-zh.pdf
├── build/
├── rewrite_fragments/
├── figures/
└── manifest/
```

### Folder hygiene

Before delivery, run `python3 scripts/cleanup_output.py "<out>"`. It removes
macOS `" 2"` duplicates, `.DS_Store`, and stray aux files in the root (build/
contents are preserved). After cleanup, `ls` should show only `*.tex`, `*.pdf`,
`build/`, `figures/`, `manifest/`, `rewrite_fragments/`.

Directory naming: `rewrite_fragments/` (never `rewrite_chunks/`); `figures/`
and `manifest/` (never `figures 2/`). Do not place final `slide-NNN.jpg` page
screenshots in the output — keep QA renders under
`/tmp/slides-to-latex-<slug>/qa-rendered/` only.

---

## Source Strategy

### PPTX/PPT first

For `.pptx`, prefer native Office Open XML extraction. Do not default to PDF.

1. Unpack the PPTX.
2. Read `ppt/slides/slide*.xml` for text, shape order, and title candidates.
3. Read `ppt/slides/_rels/slide*.xml.rels` to map slide objects to `ppt/media/*`,
   charts, tables, diagrams, and embedded objects.
4. Copy real media into `figures/` using stable academic names.
5. Use PowerPoint/LibreOffice → PDF only for visual QA or as a fallback for
   objects that cannot be reconstructed from XML.

For legacy `.ppt`, convert to `.pptx` or PDF first. Do not silently downgrade to
low-fidelity screenshots.

### PDF path

For `.pdf`, do not render every page as a final image. Prefer:

1. `pdfplumber` for page text and tables.
2. `pdfimages -j -p` for embedded figures.
3. Page/region crops only when a chart or diagram is not available as an embedded
   image.
4. OCR only for scanned decks where no text layer exists.

PDF extraction writes the same slide-level schema as PPTX extraction. If
`pdfimages` is unavailable, keep the `pdfplumber` text/table records and warn
that embedded images were skipped.

---

## Academic Reconstruction Rules

- **Mandatory multimodal rewrite:** every final page section must be rewritten
  by the Code Agent after inspecting the rendered slide image. The visual slide
  is the source of truth for formula layout, table geometry, bullet hierarchy,
  chart selection, and whether an extracted image is meaningful.
- Write prose as paragraphs by default. Use `itemize` only for true source
  lists, taxonomies, procedures, or enumerated assumptions.
- Reconstruct bullets semantically. Do not preserve extractor fragments (slide
  numbers, single words, orphan punctuation, repeated heading fragments, broken
  wrapped lines) as separate `\item`s.
- Rewrite formulas in LaTeX (`equation`, `align`, or inline as appropriate).
  Never paste Unicode math or OCR fragments into the final document.
- Keep variables and model names in English when standard: CAPM, alpha, beta,
  VaR, Expected Shortfall, Treynor-Black, Black-Litterman, KMV.
- Rebuild tables from the visual slide intent, not raw extracted cell order.
  Merge wrapped cells, repair headers, drop duplicated OCR/header rows.
- Every retained image must be a content image (chart, diagram, screenshot,
  data figure, photo). Decorative logos, repeated footers, background textures,
  and whole-slide images should be excluded.

### Table layout

Apply every time a table is written:

- Wrap every table in `\begin{center}…\end{center}` (or use `\centering` inside
  a `table` float).
- For tables with ≥ 3 columns or any uncertain total width: use
  `\begin{tabularx}{\textwidth}{…}` with `X` columns. This guarantees the
  table spans the full text width and is visually centred.
- For narrow data tables (2 columns, few rows): set a fixed width explicitly,
  e.g. `\begin{tabular*}{0.55\linewidth}{@{\extracolsep{\fill}}lr}`. A
  shrink-fit table centred on the page can still look left-aligned.
- Use `@{}` to remove inter-column padding **only** on full-`\textwidth`
  tables. On narrow tables `@{}` makes the table flush-left within its small
  centre box.
- Apply `\small` or `\footnotesize` to wide tables rather than letting them
  overflow the margin.
- After compilation, visually inspect every table page in screenshot QA. A
  table that is technically centred but narrow should be widened, not accepted.

### Section title format

Every `\section` must include the lecture/week identifier as a prefix:

```latex
\section{Week 1: Investment Strategies and Risk Management}
\section{Lecture 3: Alternative Investments and Commodities}
```

Use the identifier matching the source folder/filename (`Week1_Pre_Sessional.pptx`
→ `Week 1:`; `Lecture03` → `Lecture 3:`). In Chinese use a full-width colon:
`\section{Week 1：投资策略与风险管理}`. Do not omit the identifier even when the
deck title already contains a number.

### Figure captions

```latex
\begin{figure}[htbp]
  \centering
  \includegraphics[width=0.72\linewidth]{figures/figure-001.png}
  \caption{Mean-variance efficient frontier. Source: Week 1, slide 34.}
  \label{fig:week1-efficient-frontier}
\end{figure}
```

---

## Formula Policy

Normalize formula text before writing LaTeX:

| Source glyph | LaTeX |
| --- | --- |
| `α`, `β`, `σ`, `μ`, `ρ`, `λ`, `τ`, `π` | `\alpha`, `\beta`, `\sigma`, `\mu`, `\rho`, `\lambda`, `\tau`, `\pi` |
| `∑`, `√`, `≤`, `≥`, `≈`, `∈` | `\sum`, `\sqrt{}`, `\le`, `\ge`, `\approx`, `\in` |
| sub/superscripts | use `_` and `^`, never Unicode glyphs |

If a formula cannot be reconstructed with confidence, write the surrounding
explanation, add `"needs_formula_review": true` to the manifest entry, and
leave a `% TODO: formula review needed (source slide ...)` comment. Do not
invent a formula.

---

## Workflow

### 1. Collect inputs

Run `collect_slide_inputs.py`. Preserve natural ordering by folder and
filename. Exclude previous output folders, `figures/`, `images/`, caches,
hidden folders, and QA render folders.

### 2. Extract content

- PPTX: `extract_pptx_assets.py`.
- PDF: `extract_pdf_figures.py` (`pdfplumber` text/tables + `pdfimages`
  embedded images).
- Store raw extraction in `manifest/extraction_manifest.json`.

### 3. Build content manifest

One record per source slide/page. Include source file, page/slide number,
structured text blocks, plain text, extracted figures, tables, formulas, source
language, and review flags.

For PPTX, text blocks must preserve `shape_id`, placeholder, paragraph level,
layout bounds, and source order — do not collapse them back to raw `a:t` runs.
The manifest must include `logical_sections`; the builder uses these to create
agent packets.

Each figure carries `status`: `keep`, `drop`, or `review`. At extraction time
figures pass through a two-stage hard filter before any AI review:

- Stage 0 (PPTX) — images referenced from `<p:bg>` (slide backgrounds) excluded.
- Stage 1 — file size < 5 KB → `drop` (`drop_reason: "too_small"`).
- Stage 2 — pixel dimensions < 80×80 → `drop` (`tiny_dimensions`).
- Stage 3 — aspect ratio > 8:1 → `drop` (`banner_strip`).
- Stage 4 — ≥ 95% near-white pixels → `drop` (`near_blank`).
- All survivors → `review` for the agent classifier.

### 4. Classify review figures

For each `status: "review"` figure, the agent reads the image directly (vision)
and runs OCR (pytesseract, if installed). Decide keep/drop:

- **keep**: chart/graph/data visualization; Bloomberg terminal or financial
  data interface; numerical data table; structural diagram, flowchart, or
  network; ETF/fund profile page; photo with academic content; any image where
  visual data or structure is primary.
- **drop**: slide showing only equations/formulas with no chart element
  (formulas are reconstructed in LaTeX — the screenshot is redundant); slide
  with only bullet-point text or paragraph prose; decorative background;
  logo/icon/watermark; near-blank image.

If OCR shows the entire image is mathematical notation with no chart present →
drop. Update `status` in both `slides[].figures[]` and the top-level
`figures[]` array, then write the file.

### 5. Build scaffold and reconstruction packets

Run `build_academic_latex.py`; it writes `<name>-en.scaffold.tex`, a
compatibility `<name>-en.tex`, and `manifest/reconstruction_packets.json`. The
scaffold is source evidence, not a deliverable — it intentionally contains
`agentbox` warnings until the agent rewrites it.

### 6. Build the multimodal rewrite queue

Render the source deck/PDF pages for QA into a temporary directory with
`render_slide_images.py` (e.g. `/tmp/slides-to-latex-<slug>/qa-rendered/`).
The renderer writes stable names like `<deck-key>-slide-001.png` and a
`render_manifest.json`; these images are evidence only and must not be
included in the final LaTeX.

Run `build_multimodal_rewrite_queue.py` so every slide receives a rewrite task
containing the rendered slide path, extracted text blocks, native tables,
charts, formula candidates, kept figures, and risk flags. Pass the renderer's
`render_manifest.json` with `--render-manifest` when available.

If no rendered slide image is available, mark `"rendered_slide_missing": true`
and warn that visual fidelity is reduced.

### 7. Multimodal English reconstruction (Code Agent)

1. Initialize editable fragments with `init_rewrite_fragments.py`. This creates
   one `rewrite_fragments/page-XXXX.tex` and one sidecar `task.json` per slide.
2. Process `manifest/multimodal_rewrite_queue.jsonl` and the matching
   `rewrite_fragments/page-XXXX.task.json` one slide at a time. Inspect the
   rendered slide image directly. Use the visual slide as the source of truth
   for formula structure, table geometry, bullet hierarchy, and which extracted
   figures belong where.
3. **Insert every kept figure.** For each figure with `status: "keep"`, place a
   `\begin{figure}[htbp]` block in the LaTeX at the section where that figure's
   source slide falls. Use the standard caption template above.
4. Assemble fragments with `assemble_rewrite_fragments.py`. The assembler
   refuses to run when (a) any `LLM_REWRITE_REQUIRED` / `TODO(multimodal)` /
   scaffold marker remains, or (b) the number of `\includegraphics` in the
   fragments does not equal the manifest `keep` count. If it fails on (b),
   locate the missing kept figures by `slide_number` and insert them before
   re-running.
5. Overwrite `<name>-en.tex` with the assembled document. Strip any
   scaffold-only `agentbox` warnings.

### 8. Parallel multi-agent Chinese translation

Split the verified English LaTeX into one chunk per source deck/week (use the
`\section` boundaries) and save each chunk as
`<tmp>/zh-translation/weekN-en.tex`.

Launch one background agent per chunk **in parallel** (single message, multiple
Agent tool calls). Prompt template:

```
You are a LaTeX academic translation expert.
Translate the following English LaTeX lecture notes into Chinese.

Rules:
1. Preserve all LaTeX commands, math environments, table environments, figure
   references, labels, and cross-references exactly.
2. Translate only the English prose to Chinese.
3. **Do not translate, modify, reorder, or delete any \begin{figure}...\end{figure}
   block. Copy figure environments through verbatim — only the caption text
   inside \caption{...} may be translated.**
4. Keep standard finance terms in English: CAPM, alpha, beta, VaR, Expected
   Shortfall, Sharpe ratio, information ratio, tracking error, Treynor-Black,
   Black-Litterman, KMV, Bloomberg, ETF, hedge fund, portfolio, etc.
5. Keep model names and person names in English.
6. Section titles must include the Week/Lecture prefix:
   \section{Week N：Chinese topic title}  (full-width colon)
7. Output only valid LaTeX body content (no \documentclass, no \begin{document}).
8. Write the translation to <tmp>/zh-translation/weekN-zh.tex.

Content to translate:
<paste chunk>
```

Wait for all agents to complete. If an agent could not write the file due to
permissions, extract the translation from the agent result and write it
yourself.

### 9. Parallel multi-agent Chinese polish

After all translation chunks are collected, launch one background polish agent
per chunk **in parallel**. Prompt template:

```
You are a Chinese academic writing expert specialising in finance and economics.
Polish the following Chinese LaTeX lecture notes for fluency, consistency, and
academic tone.

Rules:
1. Do NOT alter any LaTeX commands, math environments, table environments,
   figure references, labels, cross-references, or the \section{Week N：…}
   title prefix.
2. **Do not modify, reorder, or delete any \begin{figure}...\end{figure}
   block. Polish caption prose only; the figure environment itself must be
   preserved verbatim.**
3. Fix awkward or literal translations; use natural academic Chinese.
4. Ensure consistent terminology throughout (e.g. always 波动率 for volatility,
   always 期望缺口 for Expected Shortfall).
5. Keep standard finance/model names in English (same list as the translation
   step).
6. Do not add or remove content — only improve phrasing.
7. Output only valid LaTeX body content.
8. Write the polished translation to <tmp>/zh-translation/weekN-zh-polished.tex.

Content to polish:
<paste weekN-zh.tex>
```

Wait for all agents to complete. Fall back to the unpolished translation if a
polished version is unavailable.

Assemble the final Chinese document:
- Start from `references/latex-template-zh.tex` (or the xeCJK variant used on
  this system).
- Concatenate all polished (or translated) chunks in week/lecture order.
- Append `\end{document}`.
- Write to `<out>/<name>-zh.tex`.

### 10. Compile, verify, and screenshot-QA

1. Run XeLaTeX twice for each language (`-en.tex`, then `-zh.tex`).
2. Run `verify_latex.py <name>.tex --manifest manifest/content_manifest.json`
   to enforce quality gates (see **QA Gates** below). Use `--static-only`
   before compilation when no `.log` exists yet.
3. Render final PDFs into temporary screenshots and inspect them with the
   agent's multimodal vision:

   ```bash
   pdftoppm -png -r 144 "<out>/<name>-en.pdf" "/tmp/slides-to-latex-<slug>/final-render/en-page"
   pdftoppm -png -r 144 "<out>/<name>-zh.pdf" "/tmp/slides-to-latex-<slug>/final-render/zh-page"
   ```

   Inspect for **each** language version:

   | Pages to inspect | What to check |
   | --- | --- |
   | Cover (page 1) | Title/author/date visible; no overflow |
   | Table of contents | All weeks/lectures listed with `Week N:` / `Lecture N:` prefixes |
   | First page of each section | Heading starts with the prefix; no scaffold markers |
   | Every table-heavy page | Table spans ≥ 60% of text width and is visually centred; no clipping |
   | Every figure-heavy page | `\includegraphics` figure present (not placeholder); caption includes source slide reference |
   | Last content page | Document ends cleanly; no orphaned headings |
   | Every page cited in a log warning | Text not clipped; nothing outside the page body |

   For the Chinese version additionally verify: Chinese characters render
   (no □ boxes); section titles use full-width colon `：`; math + Chinese on
   the same line do not collide.

4. Treat `Overfull \hbox`, `Overfull \vbox`, and missing-character warnings as
   content risks until the affected pages have been visually inspected. Fix
   and recompile when screenshots show clipped text, overlap, unreadable
   tables, truncated equations, missing glyphs, or content pushed into margins.
5. Run `python3 scripts/cleanup_output.py "<out>"` to remove macOS duplicates,
   `.DS_Store`, and stray root aux files before delivery.

---

## QA Gates and Failure Modes

### Gates enforced by tools

| Gate | Tool / location |
| --- | --- |
| No placeholder/scaffold markers in fragments | `assemble_rewrite_fragments.py` |
| Fragment `\includegraphics` count == manifest `keep` count | `assemble_rewrite_fragments.py` (Failure Mode 1) |
| English `.tex` does not load `ctex`; no Chinese TOC labels | `verify_latex.py` |
| No scaffold/agentbox/multimodal placeholders | `verify_latex.py` |
| Table of contents not empty | `verify_latex.py` |
| Balanced `$` in non-comment lines | `verify_latex.py` |
| No residual Unicode math glyphs | `verify_latex.py` |
| No natural-language paragraphs inside display math | `verify_latex.py` |
| Every `\includegraphics` path resolves on disk | `verify_latex.py` |
| Manifest `keep`/`drop` consistency (no drop/review figures referenced) | `verify_latex.py --manifest …` |
| Tables with > 12 columns rejected; > 8 columns warned | `verify_latex.py` |
| Fragmented itemize output (many 1-word items) | `verify_latex.py` |

If a gate fires, fix the underlying issue — do not bypass with
`--allow-placeholders` or `--skip-figure-check` outside debugging.

### Gates the agent must enforce visually

These cannot be checked statically and must be verified during step 10
screenshot QA:

- `\section` titles begin with `Week N:` or `Lecture N:` (full-width `：` in
  Chinese). LaTeX structure, math, and figure references must be identical
  between `-en.tex` and `-zh.tex`.
- Every kept figure appears in the section corresponding to its source slide.
- Tables span ≥ 60% of text width and are visually centred (see Failure Mode 2).
- Long bullet decks have been converted to paragraph-style academic notes
  except where list semantics are real.
- Final files contain no `agentbox` or scaffold notices.
- The Chinese version is a faithful translation of the English version, not
  independently generated. Polish (step 9) is mandatory; raw machine
  translation is not an acceptable deliverable.
- Overfull-box warnings reported in the final response must be paired with the
  visual QA result on the affected page, not dismissed as cosmetic.

### Failure Mode 1 — figures extracted but never inserted

**Symptom:** `figures/` contains dozens of files; compiled PDF has no charts;
`grep -c 'includegraphics' <name>-en.tex` returns `0`.

**Cause:** The reconstruction agent wrote prose and formulas slide-by-slide
but never circled back to insert figure blocks. Common when slides are
formula-heavy.

**Defence:** `assemble_rewrite_fragments.py` now compares
`fragments/*.tex` `\includegraphics` count to manifest `keep` count and refuses
to assemble when they disagree. The translation/polish prompts in steps 8–9
also forbid modifying figure environments.

**Manual recovery if assembly already failed:** for each `status: "keep"` figure
in the manifest, find its `slide_number`, identify the corresponding `\section`
in the LaTeX, and insert at the end of that section's relevant subsection:

```latex
\begin{figure}[htbp]
  \centering
  \includegraphics[width=0.80\linewidth]{figures/figure-NNN.png}
  \caption{<description>. Source: Week N, slide NN.}
  \label{fig:weekN-description}
\end{figure}
```

Recompile twice after inserting figures.

### Failure Mode 2 — tables visually left-aligned or disproportionately narrow

**Symptom:** Screenshot QA shows tables that appear left-aligned or occupy only
~30–50% of page width, even though they are inside `\begin{center}`.

**Cause:**
- *Shrink-fit narrow tables:* `\begin{tabular}{lrr}` with no width argument
  shrinks to content width. Sparse content makes the table tiny.
- *First column `l` in a wide table:* `tabularx{\textwidth}{@{}l X X X@{}}`
  fills full width, but the `l` first column makes text start flush-left,
  reinforcing a left-aligned impression.

**Detection:**
```bash
grep -n 'begin{tabular}' <name>.tex | grep -v 'tabularx\|tabular\*'
```
For each hit, count columns. ≤ 3 columns with short content is a shrink-fit
candidate.

**Fix:** Replace narrow `tabular` with `tabular*` at an explicit width, or use
`tabularx` for any table with mixed column types. See **Table layout** above
for the exact rules. Default new tables to `tabularx` at an explicit width;
use plain `tabular` only for single-row or single-column constructs.

---

## References and Scripts

### References (`references/`)

- `_common-preamble.tex` — shared preamble loaded by both LaTeX templates.
- `latex-template.tex` — English academic template (loads the shared preamble).
- `latex-template-zh.tex` — Chinese academic template (xeCJK + shared preamble).
- `structure-heuristics.md` — sectioning and topic grouping heuristics.

Editing `_common-preamble.tex` updates both templates.

### Scripts (`scripts/`)

- `collect_slide_inputs.py` — natural-order input collection.
- `extract_pptx_assets.py` — native PPTX text/media extraction.
- `extract_pdf_figures.py` — PDF text/table extraction (`pdfplumber`) plus
  embedded image extraction (`pdfimages`).
- `build_content_manifest.py` — merge extraction manifests into slide-level
  content records.
- `render_slide_images.py` — convert PPT/PPTX/PDF sources to per-slide PNGs
  for visual QA; writes `render_manifest.json`.
- `build_multimodal_rewrite_queue.py` — create one rewrite task per slide so
  the Code Agent can reconstruct from rendered slides plus extracted evidence.
- `init_rewrite_fragments.py` — create one editable `page-XXXX.tex` fragment
  and sidecar task JSON per rewrite queue item; existing fragments preserved
  unless `--overwrite` is passed.
- `assemble_rewrite_fragments.py` — assemble rewritten fragments into a final
  document. Refuses to run on placeholder/scaffold residue or on
  fragment-vs-manifest figure-count mismatch.
- `build_academic_latex.py` — generate a conservative scaffold and
  `manifest/reconstruction_packets.json`; final prose must be rewritten by
  the Code Agent.
- `verify_latex.py` — parse a XeLaTeX `.log` and enforce static quality gates
  (see **QA Gates** above).
- `cleanup_output.py` — remove macOS `" 2"` duplicates, `.DS_Store`, and
  stray root aux files. Run before delivery.
- `convert_presentation_to_pdf.py` — QA/fallback conversion only.
- `sync_agent_metadata.py` — regenerate `agents/claude.md` and
  `agents/codex.yaml` from `SKILL.md` frontmatter (`--check` for CI).
- `validate_codex_skill.py` — validate required Codex skill metadata.
- `install_to_codex.py` — copy this skill into
  `$CODEX_HOME/skills/slides-to-latex`, excluding cache and debug artifacts.
