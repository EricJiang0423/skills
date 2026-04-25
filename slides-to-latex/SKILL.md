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

Rebuild PDF/PPT/PPTX lecture slides as academic LaTeX documents, with one
English version (`-en.tex`) generated first and one Chinese translation
(`-zh.tex`) generated from the verified English version.
The final documents must not retain full-slide screenshots; rendered pages are
temporary QA evidence only. Rewrite the source into academic prose, LaTeX
formulas, rebuilt tables, and properly captioned academic figures.

---

## Dependencies

Core dependency: **Pillow**. Install with `pip install -r requirements.txt`.

Optional:
- `pytesseract` + `tesseract` binary — OCR for figure classification
- `pdfplumber` + Poppler (`pdfimages`) — PDF extraction path
- ImageMagick (`convert`) or LibreOffice — EMF/WMF → PNG conversion

Do **not** ask the user for OpenAI/Anthropic API keys. Intelligent reconstruction is performed by
the running Code Agent itself: scripts produce structured evidence and reconstruction packets; the
agent reads those packets and writes final LaTeX in-context.

**Important:** XML/PDF extraction is only evidence. It is not an acceptable final representation for
formula-heavy, table-heavy, or bullet-heavy lecture slides. Before final delivery, the Code Agent must
perform a page-by-page LLM reconstruction pass, using both the rendered slide image and extracted
evidence, and must rewrite formulas, tables, bullet hierarchy, captions, and figure references.

See `requirements.txt` for exact versions and installation notes.

---

## Quick Reference

| Task | Preferred path |
| --- | --- |
| Collect inputs | `python3 "scripts/collect_slide_inputs.py" "<input>" --manifest "<work>/input_manifest.json"` |
| Extract PPTX content and images | `python3 "scripts/extract_pptx_assets.py" "<deck.pptx>" --output-dir "<out>"` |
| Extract PDF text, tables, and embedded images | `python3 "scripts/extract_pdf_figures.py" "<slides.pdf>" --output-dir "<out>"` (`pdfplumber` + `pdfimages`) |
| Build the content manifest | `python3 "scripts/build_content_manifest.py" "<out>/manifest/*-extraction.json" --output "<out>/manifest/content_manifest.json"` |
| Classify images with agent vision | Hard-filter first (size/dimensions/ratio/near-blank), then inspect each survivor visually plus OCR, decide keep/drop, and update the manifest |
| Render per-page visual evidence | `python3 "scripts/render_slide_images.py" "<input-or-manifest>" --output-dir "<tmp>/qa-rendered" --pdf-dir "<tmp>/qa-pdf"` |
| Build the per-page multimodal rewrite queue | `python3 "scripts/build_multimodal_rewrite_queue.py" "<out>/manifest/content_manifest.json" --output "<out>/manifest/multimodal_rewrite_queue.jsonl" --render-dir "<tmp>/qa-rendered" --render-manifest "<tmp>/qa-rendered/render_manifest.json"` |
| Initialize per-page LaTeX fragments | `python3 "scripts/init_rewrite_fragments.py" "<out>/manifest/multimodal_rewrite_queue.jsonl" --output-dir "<out>/rewrite_fragments"` |
| Assemble the final English document | `python3 "scripts/assemble_rewrite_fragments.py" "<out>/rewrite_fragments" --output "<out>/<name>-en.tex" --title "<course name>" --language en` |
| Generate scaffold and packets | `python3 "scripts/build_academic_latex.py" "<out>/manifest/content_manifest.json" --output "<out>/<name>-en.tex" --title "<course name>"` |
| Code Agent reconstructs the final English LaTeX | Read `multimodal_rewrite_queue.jsonl`, rendered images, and extracted evidence page by page; rewrite into final `<name>-en.tex` |
| Split English for translation | `sed -n 'START,ENDp' <name>-en.tex > <tmp>/zh-translation/weekN-en.tex` per section boundary |
| Parallel translate (N agents) | Launch one background Agent per week/lecture chunk with the translation prompt; collect `weekN-zh.tex` outputs |
| Parallel polish (N agents) | Launch one background Agent per translated chunk with the polish prompt; collect `weekN-zh-polished.tex` outputs |
| Assemble Chinese document | Concatenate preamble + polished chunks + `\end{document}` → `<name>-zh.tex` |
| PPTX visual QA | `python3 "scripts/convert_presentation_to_pdf.py" "<deck.pptx>" --output-dir "<work>/qa-pdf"` then `pdftoppm` |
| Final compile | Run `xelatex -interaction=nonstopmode -halt-on-error "<name>.tex"` twice for each English and Chinese version |
| Compile and quality diagnostics | `python3 "scripts/verify_latex.py" "<name>.tex" --manifest "<out>/manifest/content_manifest.json"`; use `--static-only` before compilation when no log exists yet |
| Final PDF screenshot QA | `pdftoppm -png -r 144 "<out>/<name>-en.pdf" "<tmp>/final-render/en-page"` and same for `-zh.pdf`; inspect cover, TOC, first page of each Week/Lecture section, all table/figure-heavy pages, and last page |
| Figure count check | `grep -c 'includegraphics' <name>-en.tex` must equal manifest `status:"keep"` count; if 0 with non-empty `figures/`, insert missing figures |
| Table width check | `grep -n 'begin{tabular}' <name>.tex \| grep -v 'tabularx\|tabular\*'` — audit each hit; replace narrow 2-3 column tables with `tabular*` or `tabularx` at explicit width |

---

## Output Contract

### Folder input

Create one merged output folder:

```text
<input-folder>/slides-to-latex-output/
├── <folder-name>-en.tex           ← English version (generated first)
├── <folder-name>-en.scaffold.tex  ← scaffold (intermediate; keep for reference)
├── <folder-name>-en.pdf           ← final compiled English PDF
├── <folder-name>-zh.tex           ← Chinese version (translated from English)
├── <folder-name>-zh.pdf           ← final compiled Chinese PDF
├── build/                         ← XeLaTeX aux files (.aux .log .out .toc missfont.log)
│   └── <folder-name>-en.aux / .log / .out / .toc (and zh counterparts)
├── rewrite_fragments/             ← per-page LaTeX fragments (NOT "rewrite_chunks")
│   ├── page-0001.tex
│   └── page-0001.task.json
├── figures/
│   ├── figure-001.<ext>
│   └── ...
└── manifest/
    ├── input_manifest.json
    ├── content_manifest.json
    ├── reconstruction_packets.json
    └── extraction_manifest.json
```

Always compile with `xelatex -output-directory=build` so aux files land in `build/`
and the root directory stays clean. Copy the finished PDF from `build/` to the root.

### Single file input

Create:

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

### Folder hygiene rules

- **No " 2" files**: macOS creates `file 2.ext` copies on duplicate writes. Delete them before delivery. Check with `ls *\ 2.*` and `ls *\ 2/`.
- **No aux files in root**: `.aux`, `.log`, `.out`, `.toc`, `missfont.log` belong in `build/`.
- **No `.DS_Store`**: remove with `find . -name '.DS_Store' -delete`.
- **Directory naming**: use `rewrite_fragments/` (never `rewrite_chunks/`); `figures/` and `manifest/` (never `figures 2/` or `manifest 2/`).
- After cleanup, `ls` should show only: `*.tex`, `*.pdf`, `build/`, `figures/`, `manifest/`, `rewrite_fragments/`.

Do not place final `slide-NNN.jpg` page screenshots in the output. If rendered slide images are
needed for QA, keep them under `/tmp/slides-to-latex-<slug>/qa-rendered/` and delete or leave
them outside the deliverable.

---

## Source Strategy

### PPTX/PPT first

For `.pptx`, do not default to converting to PDF. Prefer native Office Open XML extraction:

1. Unpack the PPTX.
2. Read `ppt/slides/slide*.xml` for text, shape order, and title candidates.
3. Read `ppt/slides/_rels/slide*.xml.rels` to map slide objects to `ppt/media/*`,
   charts, tables, diagrams, and embedded objects.
4. Copy real media assets into `figures/` using stable academic names.
5. Use PowerPoint/LibreOffice-to-PDF only for visual QA or as a fallback for objects that cannot
   be reconstructed from XML.

For legacy `.ppt`, convert to `.pptx` or PDF with PowerPoint/LibreOffice, then follow the closest
available path. Do not silently downgrade to low-fidelity screenshots.

### PDF path

For `.pdf`, do not render every page as a final image. Prefer:

1. `pdfplumber` for page text and tables.
2. `pdfimages -j -p` for embedded figures.
3. Page/region crops only when a chart or diagram is not available as an embedded image.
4. OCR only for scanned decks where no text layer exists.

PDF extraction writes the same slide/page-level schema as PPTX extraction: each PDF page becomes a
record with structured `text_blocks`, `plain_text_blocks`, `tables`, `figures`, and page-level
metadata. If `pdfimages` is unavailable, keep the `pdfplumber` text/table records and warn that
embedded images were skipped.

---

## Academic Reconstruction Rules

- **Mandatory LLM rewrite pass:** every final page/slide section must be rewritten by the Code
  Agent after inspecting the slide evidence. Never deliver lightly edited scaffold output.
- Use the rendered slide image as the visual source of truth for formula layout, table geometry,
  bullet hierarchy, chart/diagram selection, and whether an extracted image is meaningful.
- Write prose as paragraphs by default. Use `itemize` only for true source lists, taxonomies,
  procedures, or enumerated assumptions.
- Bullet points must be reconstructed semantically. Do not preserve extractor fragments such as
  slide numbers, single words, orphan punctuation, repeated heading fragments, or broken wrapped
  lines as separate `\item`s.
- Rewrite formulas in LaTeX. Do not paste Unicode math or OCR fragments into the final document.
- Use `equation`, `align`, or inline math depending on complexity.
- Keep variables and model names in English when standard: CAPM, alpha, beta, VaR, Expected
  Shortfall, Treynor-Black, Black-Litterman, KMV.
- Tables should be rebuilt with `tabular` and `booktabs`, not inserted as screenshots unless the
  table is visually inseparable from a diagram.
- Tables must be rebuilt from the visual slide/table intent, not merely from extracted cell order.
  Merge wrapped cells, repair headers, drop duplicated OCR/header rows, and choose `tabularx` or
  `longtable` only when the final table is readable.
- **Table centering rules** — apply these every time a table is written:
  - Always wrap every table in `\begin{center}…\end{center}` (or use `\centering` inside a `table`
    float).
  - For tables with 3 or more columns, or any table whose total content width is uncertain, prefer
    `tabularx{\textwidth}` over plain `tabular`. This guarantees the table spans the full text
    width and is visually centred.
  - For narrow data tables (2 columns, few rows), set a fixed width explicitly, e.g.
    `\begin{tabular*}{0.55\linewidth}{@{\extracolsep{\fill}}lr}`, rather than letting LaTeX
    shrink-fit the table to content width. A shrink-fit table centred on the page can still look
    left-aligned at a glance.
  - Use `@{}` on both ends of the column spec to remove default inter-column padding only when the
    table is already full-width (`\textwidth`). Do not use `@{}` on a narrow `tabular` — it makes
    the table flush-left within its (small) centre box.
  - Apply `\small` or `\footnotesize` to wide tables rather than letting them overflow the margin.
  - After compilation, visually inspect every table page in the screenshot QA. A table that is
    technically centred but narrow should be widened rather than accepted as-is.
- Every retained image must be a content image: chart, diagram, screenshot, figure, photo, or
  visual example. Decorative logos, repeated footers, background textures, and whole-slide images
  should normally be excluded.

### Section title format

Every `\section` must include the lecture/week identifier as a prefix, separated by a colon:

```latex
\section{Week 1: Investment Strategies and Risk Management}
\section{Lecture 3: Alternative Investments and Commodities}
```

- Use the identifier that matches the source folder or filename (e.g. `Week1_Pre_Sessional.pptx` →
  `Week 1:`; a file labelled `Lecture03` → `Lecture 3:`).
- Apply the same prefix format in the Chinese version:
  `\section{Week 1：投资策略与风险管理}` (use a full-width colon `：` in Chinese).
- Do not omit the identifier even when the slide deck title already contains a number.

- Figure captions must be academic and source-aware:

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

Before writing LaTeX, normalize formula text:

| Source glyph | LaTeX |
| --- | --- |
| `α`, `β`, `σ`, `μ`, `ρ`, `λ`, `τ`, `π` | `\alpha`, `\beta`, `\sigma`, `\mu`, `\rho`, `\lambda`, `\tau`, `\pi` |
| `∑`, `√`, `≤`, `≥`, `≈`, `∈` | `\sum`, `\sqrt{}`, `\le`, `\ge`, `\approx`, `\in` |
| subscripts/superscripts | use `_` and `^`, never Unicode subscript/superscript glyphs |

If a formula cannot be reconstructed with confidence, write the surrounding explanation and add a
manifest entry with `"needs_formula_review": true`; do not invent a formula.

---

## Workflow

1. **Collect inputs**
   - Use `collect_slide_inputs.py`.
   - Preserve natural ordering by folder and filename.
   - Exclude previous output folders, `figures/`, `images/`, caches, hidden folders, and QA render
     folders.

2. **Extract content**
   - PPTX: run `extract_pptx_assets.py`.
   - PDF: run `extract_pdf_figures.py`; it combines `pdfplumber` text/table extraction with
     `pdfimages` embedded-image extraction when Poppler is available.
   - Store raw extraction in `manifest/extraction_manifest.json`.

3. **Build content manifest**
   - One record per source slide/page.
   - Include source file, page/slide number, structured text blocks, plain text, extracted figures,
     tables, formulas, source language, and review flags.
   - For PPTX, text blocks must preserve `shape_id`, placeholder, paragraph level, layout bounds,
     and source order. Do not collapse them back to raw `a:t` runs.
   - The manifest must include `logical_sections`; the builder uses these to create agent packets.
   - Each figure carries a `status` field: `keep`, `drop`, or `review`.
   - At extraction time, figures pass through a **two-stage hard filter** before any AI review:
     - Stage 0 – PPTX: images referenced from `<p:bg>` (slide backgrounds) excluded entirely.
     - Stage 1 – File size < 5 KB → `drop` (`drop_reason: "too_small"`).
     - Stage 2 – Pixel dimensions < 80×80 → `drop` (`drop_reason: "tiny_dimensions"`).
     - Stage 3 – Aspect ratio > 8:1 → `drop` (`drop_reason: "banner_strip"` — header/footer strips).
     - Stage 4 – ≥ 95 % near-white pixels → `drop` (`drop_reason: "near_blank"` — gradient backgrounds).
     - All remaining figures → `review` for the AI classifier.

4. **Classify review figures** — hard filter first, then Code Agent vision
   - Only figures that survived all hard-filter stages above will have `status: "review"`.
   - Read the content manifest to get all `status: "review"` figures.
   - For each figure, read the image directly (vision) **and** run OCR (pytesseract, if installed)
     to extract any text/formula content from the slide.
   - Use both the visual content and the OCR text to decide keep or drop:
     - **keep**: chart, graph, or data visualization; Bloomberg terminal / financial data interface;
       table of numerical data; structural diagram, flowchart, or network; ETF/fund profile page;
       photo with academic content; any image where visual data or structure is primary.
     - **drop**: slide showing **only** equations or formulas with no chart element
       (formulas are reconstructed in LaTeX — the screenshot is redundant);
       slide with only bullet-point text or paragraph prose;
       decorative background, gradient, template art; logo, icon, watermark; near-blank image.
   - If OCR reveals that the entire image is mathematical notation with no chart present → drop.
   - Update `status` in both `slides[].figures[]` and the top-level `figures[]` array in the
     manifest, then write the file.
   - Do not ask for API keys. If batch scripts require external credentials, skip them and classify
     manually as the Code Agent by inspecting the images.

5. **Build scaffold and reconstruction packets**
   - Run `build_academic_latex.py`; it writes `<name>-en.scaffold.tex`, a compatibility
     `<name>-en.tex`, and `manifest/reconstruction_packets.json`.
   - The scaffold is source evidence, not a final deliverable. It intentionally contains
     `agentbox` warnings until the agent rewrites it.

6. **Build the multimodal rewrite queue**
   - Render the source deck/PDF pages for QA into a temporary directory with
     `render_slide_images.py`, for example `/tmp/slides-to-latex-<slug>/qa-rendered/`.
   - The renderer writes stable names such as `<deck-key>-slide-001.png` and a
     `render_manifest.json`; these images are visual evidence only and must not be included in the
     final LaTeX output as full-slide screenshots.
   - Run `build_multimodal_rewrite_queue.py` so every slide/page receives a rewrite task containing
     the rendered slide path, extracted text blocks, native tables, native charts, formula
     candidates, kept figures, and risk flags.
   - Pass the renderer's `render_manifest.json` with `--render-manifest` when available; this avoids
     filename-guessing errors when multiple inputs share similar names.
   - If no rendered slide image is available, create the queue anyway and mark
     `"rendered_slide_missing": true`; the agent must use the original source or extracted evidence
     and should warn that visual fidelity is reduced.

7. **Code Agent performs page-by-page multimodal English reconstruction**
   - Initialize editable fragments with `init_rewrite_fragments.py`; this creates one
     `rewrite_fragments/page-XXXX.tex` file and one sidecar task JSON per slide/page.
   - Process `manifest/multimodal_rewrite_queue.jsonl` and `rewrite_fragments/page-XXXX.task.json`
     one slide/page at a time.
   - For each item, inspect the rendered slide image directly when available. Use the visual slide as
     the source of truth for:
     - formula structure, line breaks, subscripts/superscripts, matrices, and derivation order;
     - table columns, headers, merged cells, footnotes, and row grouping;
     - bullet hierarchy and whether bullets should become prose;
     - which extracted figures are content figures and where they belong.
   - Rewrite each slide into its fragment before moving on. The fragment should contain only final
     English LaTeX body content for that slide/page, not a dump of extracted strings.
   - Preserve source-aware captions and labels for retained figures.
   - **Figure insertion is mandatory:** for every figure with `status: "keep"` in the manifest,
     insert a `\begin{figure}[htbp]` block in the LaTeX at the section where that figure's source
     slide falls. Use the standard caption template from Academic Reconstruction Rules. Do not skip
     figure insertion even if the surrounding prose was already written — figures belong in the
     same section as the slide that contained them.
   - After assembling fragments, run `grep -c 'includegraphics' "<name>-en.tex"` and compare to
     the manifest `status: "keep"` count. If the numbers do not match, return to the manifest,
     locate the missing kept figures by slide number, and insert them before proceeding.
   - Assemble fragments with `assemble_rewrite_fragments.py`. The assembler should fail unless all
     `LLM_REWRITE_REQUIRED` / `TODO(multimodal)` placeholders have been removed.
   - Overwrite `<name>-en.tex` with the assembled final English document. Remove scaffold-only
     `agentbox` warnings from the final file.
   - Never call OpenAI/Anthropic from Python for this step, and never ask the user for API keys.

8. **Parallel multi-agent Chinese translation**

   Split the verified final English LaTeX into one chunk per source deck/week (use the `\section`
   boundaries) and save each chunk as a temporary file, e.g.
   `<tmp>/zh-translation/week1-en.tex` … `weekN-en.tex`.

   Launch one background agent per chunk **in parallel** (single message, multiple Agent tool
   calls).  Each agent receives the following prompt template:

   ```
   You are a LaTeX academic translation expert.
   Translate the following English LaTeX lecture notes into Chinese.

   Rules:
   1. Preserve all LaTeX commands, math environments (equation, align, etc.), table
      environments, figure references, labels, and cross-references exactly.
   2. Translate only the English prose to Chinese.
   3. Keep standard finance terms in English: CAPM, alpha, beta, VaR, Expected Shortfall,
      Sharpe ratio, information ratio, tracking error, Treynor-Black, Black-Litterman, KMV,
      Bloomberg, ETF, hedge fund, portfolio, etc.
   4. Keep model names and person names in English.
   5. Section titles must include the Week/Lecture prefix:
      \section{Week N：Chinese topic title}  (full-width colon in Chinese)
   6. Output only valid LaTeX body content (no \documentclass, no \begin{document}).
   7. Write the translation to <tmp>/zh-translation/weekN-zh.tex.

   Content to translate:
   <paste chunk>
   ```

   Wait for all agents to complete.  Collect each `weekN-zh.tex` output; if an agent could not
   write the file due to permission, extract the translation from the agent result summary and
   write it yourself with the Write tool.

8b. **Parallel multi-agent Chinese polish**

   After all translation chunks are collected, launch one background polish agent per chunk **in
   parallel**.  Each agent receives the following prompt template:

   ```
   You are a Chinese academic writing expert specialising in finance and economics.
   Polish the following Chinese LaTeX lecture notes for fluency, consistency, and academic tone.

   Rules:
   1. Do NOT alter any LaTeX commands, math environments, table environments, figure references,
      labels, cross-references, or the \section{Week N：…} title prefix.
   2. Fix awkward or literal translations; use natural academic Chinese.
   3. Ensure consistent terminology throughout: use the same Chinese translation for each
      English concept (e.g. always 波动率 for volatility, not 波动性; always 期望缺口 for
      Expected Shortfall, etc.).
   4. Keep standard finance/model names in English (same list as the translation step).
   5. Do not add or remove content—only improve phrasing, sentence structure, and register.
   6. Output only valid LaTeX body content.
   7. Write the polished translation to <tmp>/zh-translation/weekN-zh-polished.tex.

   Content to polish:
   <paste weekN-zh.tex>
   ```

   Wait for all agents to complete.  Collect each `weekN-zh-polished.tex`; fall back to the
   unpolished translation if a polished version is unavailable.

   Assemble the final Chinese document:
   - Start from `references/latex-template-zh.tex` (or the xeCJK variant used on this system).
   - Concatenate all polished (or translated) chunks in week/lecture order.
   - Add `\end{document}`.
   - Write to `<out>/<name>-zh.tex`.

9. **Compile, screenshot-check, and verify**
   - Run XeLaTeX for each version (`-en.tex` then `-zh.tex`) until cross-reference and outline
     rerun warnings are gone; this usually means at least two runs.
   - Run `verify_latex.py <name>.tex --manifest manifest/content_manifest.json` to parse the log and
     enforce quality gates (missing figures, undefined commands, empty TOC, template language
     mismatch, bad `$`, natural-language display math, fragmented itemize output, scaffold residue,
     residual Unicode math, suspicious half-LaTeX formulas, over-wide tables, duplicated table rows,
     and manifest figure keep/drop consistency).
   - Run `verify_latex.py <name>.tex --static-only --manifest manifest/content_manifest.json` before
     compilation whenever the document is still being assembled and no `.log` exists yet.
   - Treat `Overfull \hbox`, `Overfull \vbox`, missing-character warnings, and severe underfull
     warnings inside tables or alignments as content-risk warnings. Do not dismiss them as cosmetic
     until the affected rendered PDF pages have been inspected visually.
   **Visual screenshot QA (mandatory for both -en.pdf and -zh.pdf):**

   Render the compiled final PDFs into temporary screenshots outside the deliverable:

   ```bash
   pdftoppm -png -r 144 "<out>/<name>-en.pdf" "/tmp/slides-to-latex-<slug>/final-render/en-page"
   pdftoppm -png -r 144 "<out>/<name>-zh.pdf" "/tmp/slides-to-latex-<slug>/final-render/zh-page"
   ```

   Use the Code Agent's own multimodal vision to inspect the following pages for **each** language
   version.  Do not skip this step even when compilation succeeded without errors.

   | Pages to inspect | What to check |
   | --- | --- |
   | Cover (page 1) | Title, author, date visible; no overflow |
   | Table of contents | All weeks/lectures listed; `Week N:` / `Lecture N:` prefixes present |
   | First page of each Week/Lecture section | Heading starts with `Week N:` or `Lecture N:` prefix; no scaffold markers |
   | Every table-heavy page | Table spans ≥ 60 % of text width and is visually centred; columns aligned; no clipping |
   | Every figure-heavy page | `\includegraphics` figure present (not placeholder text); caption includes source slide reference |
   | Figure count sanity | `grep -c 'includegraphics' <name>-en.tex` > 0; equals manifest `keep` count |
   | Last content page | Document ends cleanly; no orphaned headings |
   | Every page cited in a log warning | Text not clipped; no content outside page body |

   For the Chinese version additionally verify:
   - Chinese characters render correctly (no □ boxes or missing-glyph symbols).
   - Section titles use full-width colon `：`, not ASCII colon `:`.
   - Math and Chinese text on the same line do not collide or overflow.

   Fix and recompile when screenshot QA shows clipped text, text outside the page body, overlapped
   content, unreadable tables, truncated equations, missing glyphs, figures covering text, or
   meaningful content pushed into margins. Only after the screenshots look acceptable may remaining
   box warnings be described as harmless.
   - Use temporary source slide renders to verify that important diagrams were not missed, and use
     final PDF screenshots to verify that the compiled deliverable is readable.

---

## QA Rules

- `\includegraphics` paths must point to `figures/`, not `images/slide-NNN.jpg`.
- No final output may depend on full-slide screenshots.
- `\begin{figure}` count must match figures with `status: "keep"` in the manifest.
  **Silent failure check:** after every reconstruction or translation pass, run
  `grep -c 'includegraphics' <name>-en.tex`. If the result is `0` while `figures/` contains
  image files, the reconstruction agent skipped figure insertion — this must be corrected before
  delivery. Insert the missing figures using the manifest slide-number mapping to place each one
  in the correct section.
- Tables must not be left visually narrow or left-aligned. If any table page in the screenshot QA
  shows a table that occupies less than ~60 % of the text width or appears left-heavy, replace its
  column spec with a wider or `tabularx`-based equivalent and recompile.
- No figure with `status: "drop"` or `status: "review"` may appear in the LaTeX output.
- Formula-heavy pages must contain rewritten LaTeX equations, not raw extracted glyph strings.
- Formula-heavy pages must be compared against the rendered slide during the LLM pass. If the
  rendered equation cannot be read confidently, keep the surrounding explanation and add a visible
  `% TODO: formula review needed (source slide ...)` comment rather than inventing notation.
- Table-heavy pages must be visually checked against the rendered slide. The final table must have
  meaningful headers, aligned columns, and no duplicated header/body rows from extraction artifacts.
- Long bullet decks must be converted into paragraph-style academic notes except where list
  semantics are real.
- Bullet lists must not contain extractor noise: isolated slide numbers, one-word fragments,
  hanging punctuation, repeated title fragments, or wrapped line pieces as separate `\item`s.
- Before compiling, search for suspicious list fragments with a regex or by reading the generated
  LaTeX. If many very short items remain, run another LLM rewrite pass instead of deleting them
  mechanically.
- The final output directory must contain both `-en.tex` / `-en.pdf` and `-zh.tex` / `-zh.pdf`.
- Final `-en.tex` and `-zh.tex` must not contain `agentbox` or scaffold notices.
- Every `\section` in both language versions must begin with a `Week N:` or `Lecture N:` prefix.
  English: `\section{Week 1: Topic Title}`. Chinese: `\section{Week 1：中文标题}` (full-width colon).
- The Chinese version must be a faithful translation of the English version — not independently
  generated. LaTeX structure, math, and figure references must be identical between the two files.
- The Chinese version must be polished by a dedicated polish pass (step 8b) before assembly; raw
  machine-translation output is not acceptable as a final deliverable.
- Final PDF screenshot QA is mandatory. The Code Agent must inspect rendered PDF page screenshots
  with its own multimodal capability before delivery; external API calls are not required and must
  not be requested from the user.
- Overfull boxes are not automatically cosmetic. If any overfull or clipping-related warning remains,
  the affected PDF screenshots must be inspected and the content must not be clipped, hidden,
  overlapped, or pushed out of the readable page area.
- Any remaining overfull/underfull warnings in the final response must be described with the visual
  QA result, not merely ignored.
- The final output directory may keep `.tex`, `.pdf`, `figures/`, and `manifest/`. Remove LaTeX
  auxiliary files after successful compilation.

---

## Known Failure Modes

These are silent failures observed in practice. Both were confirmed on MSIN0274 ISRM (April 2026).

### 1 — Figures extracted but never inserted (zero `\includegraphics`)

**Symptom:** `figures/` directory contains dozens of image files; compiled PDF has no charts or
diagrams at all; `grep -c 'includegraphics' <name>-en.tex` returns `0`.

**Cause:** The reconstruction agent wrote prose and formulas slide-by-slide but never circled back
to insert figure blocks. This is a common omission when slides have many formula-heavy pages: the
agent focuses on equations and silently skips the figure insertion step.

**Detection:**
```bash
KEEP=$(python3 -c "
import json, sys
m = json.load(open('manifest/content_manifest.json'))
print(sum(1 for f in m.get('figures', []) if f.get('status') == 'keep'))
")
ACTUAL=$(grep -c 'includegraphics' <name>-en.tex)
echo "Keep: $KEEP  Actual: $ACTUAL"
```

**Fix:** Re-read the manifest; for each `status: "keep"` figure, find which `slide_number` it
belongs to, identify the corresponding `\section` in the LaTeX, and insert:
```latex
\begin{figure}[htbp]
  \centering
  \includegraphics[width=0.80\linewidth]{figures/figure-NNN.png}
  \caption{<description>. Source: Week N, slide NN.}
  \label{fig:weekN-description}
\end{figure}
```
at the end of that section's relevant subsection.  Recompile twice after inserting figures.

**Prevention:** Step 7 reconstruction checklist must include the figure-count comparison before
moving on. The Chinese translation step must copy all `\begin{figure}` blocks unchanged —
never translate or drop them.

---

### 2 — Tables visually left-aligned or disproportionately narrow

**Symptom:** Screenshot QA shows tables that appear left-aligned or occupy only ~30–50 % of page
width, even though they are inside `\begin{center}`.

**Cause:** Two sub-causes:

- *Shrink-fit narrow tables:* `\begin{tabular}{lrr}` with no width argument shrinks to content
  width. When that content is sparse (2 columns, short strings) the table is tiny, and even though
  it is technically centred the visual impression is left-heavy.
- *First column `l` in a wide table:* `tabularx{\textwidth}{@{}l X X X@{}}` fills full width
  but the `l` (left-align) first column makes text start flush-left, reinforcing the
  left-aligned impression.

**Detection:** Search for narrow tables:
```bash
grep -n 'begin{tabular}' <name>.tex | grep -v 'tabularx\|tabular\*'
```
Then for each hit, count columns — if ≤ 3 columns with short content, it is a shrink-fit
candidate.

**Fix:**
- Replace narrow `tabular` with `tabular*` at an explicit width:
  ```latex
  \begin{tabular*}{0.6\linewidth}{@{\extracolsep{\fill}}lrr}
  ```
- Or use `tabularx` for any table with mixed column types:
  ```latex
  \begin{tabularx}{0.75\textwidth}{@{}lXr@{}}
  ```
- Do not use `@{}` to strip padding on a narrow table — that makes it flush-left within its
  small centre box.  `@{}` is correct only on full-`\textwidth` tables.

**Prevention:** Default all new tables to `tabularx` at an explicit width.  Use plain `tabular`
only for single-row or single-column constructs.

---

## References and Scripts

- `references/latex-template.tex`: English academic LaTeX template.
- `references/latex-template-zh.tex`: Chinese academic LaTeX template.
- `references/structure-heuristics.md`: sectioning and topic grouping heuristics.
- `scripts/collect_slide_inputs.py`: natural-order input collection.
- `scripts/extract_pptx_assets.py`: native PPTX text/media extraction.
- `scripts/extract_pdf_figures.py`: PDF text/table extraction via `pdfplumber` plus embedded image extraction via `pdfimages`.
- `scripts/build_content_manifest.py`: merge extraction manifests into slide-level content records.
- `scripts/render_slide_images.py`: convert PPT/PPTX/PDF sources to per-slide/per-page PNGs for
  visual QA and multimodal reconstruction evidence; writes `render_manifest.json`.
- `scripts/build_multimodal_rewrite_queue.py`: create one LLM/multimodal rewrite task per
  slide/page so the Code Agent can reconstruct formulas, tables, bullets, and figure placement
  from rendered slide images plus extracted evidence.
- `scripts/init_rewrite_fragments.py`: create one editable `page-XXXX.tex` fragment and sidecar task
  JSON per rewrite queue item; existing fragments are preserved unless `--overwrite` is passed.
- `scripts/assemble_rewrite_fragments.py`: assemble rewritten fragments into a final LaTeX document
  and fail by default if any multimodal placeholder/scaffold marker remains.
- `scripts/build_academic_latex.py`: generate a conservative scaffold and
  `manifest/reconstruction_packets.json`; final prose must be rewritten by the Code Agent.
- `scripts/verify_latex.py`: parse a XeLaTeX `.log` and enforce final quality gates including
  scaffold residue, empty TOC, bad math, template language mismatch, fragmented itemize output,
  missing figures, formula/table smell checks, and manifest figure keep/drop consistency.
- `scripts/validate_codex_skill.py`: validate required Codex skill metadata, resources, and
  absence of debug bytecode/cache artifacts.
- `scripts/install_to_codex.py`: copy this skill into `$CODEX_HOME/skills/slides-to-latex`,
  excluding cache and debug artifacts.
- `scripts/convert_presentation_to_pdf.py`: QA/fallback conversion only.
