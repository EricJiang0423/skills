---
name: lecture-to-latex
description: Convert PDF lecture slides to bilingual (EN+CN) LaTeX structured notes with tables, formulas, and TikZ figures — designed for multi-week extensibility
workflow_stage: writing
compatibility:
  - claude-code
author: Eric Jiang
version: 1.0.0
tags:
  - LaTeX
  - pdf
  - lecture-notes
  - bilingual
  - academia
---

# Lecture to LaTeX Notes

## Purpose

Convert university lecture PDF slides into comprehensive, well-structured LaTeX notes in both English and Chinese. The output is designed for multi-week courses with a main file that `\include{}`s each week as sub-files.

## When to Use

- Converting PDF lecture slides to study notes
- Creating bilingual (EN + CN) academic notes from slides
- Building a multi-week course note system with extensibility
- Slides are image-based PDFs (no extractable text — needs OCR or `pdftotext`)

## Instructions

### Step 1: Survey the PDF and Environment

1. **Check available tools:**
   ```bash
   which pdftotext tesseract pdflatex xelatex
   python3 -c "import pytesseract; print('pytesseract ok')" 2>&1
   ```
   - `pdftotext` (poppler-utils) is the primary extraction tool — fast, no OCR needed for text-based PDFs
   - `tesseract` + `pytesseract` fallback for purely image-based slides

2. **Read PDF structure:**
   - Read pages 1-5 to understand the document type (text-based or image-based slides)
   - If text-based: use `pdftotext` to extract all pages to a `.txt` file
   - If image-based: use `pdftotext` first anyway — modern slide PDFs often have hidden text layers

3. **Count pages and estimate scope:**
   ```bash
   pdftotext lecture.pdf /tmp/lecture.txt && wc -l /tmp/lecture.txt
   ```

### Step 2: Extract All Content

1. Extract the full PDF to a temporary text file:
   ```bash
   pdftotext "/path/to/lecture.pdf" "/tmp/lecture_full.txt"
   ```

2. Read the extracted text in chunks (500 lines at a time) using the Read tool. Pay attention to:
   - Slide numbers (usually at the bottom of each slide)
   - Section headings and topic transitions
   - Tables (column-aligned text)
   - Mathematical formulas and notation
   - Bullet points and enumerations

3. Map out the lecture structure before writing any LaTeX:
   - Module info / admin
   - Main topics with subsections
   - Key definitions, theorems, examples
   - Tables and their data
   - Diagrams described in text

### Step 3: Set Up the LaTeX Project Structure

Create this file layout in the target `Note/` directory:

```
Note/
├── main.tex           # English main document
├── main_cn.tex        # Chinese main document (uses ctexart)
├── week1.tex          # English Week 1 notes
├── week1_cn.tex       # Chinese Week 1 notes
├── week2.tex          # (future weeks)
├── week2_cn.tex       # (future weeks)
└── ...
```

**`main.tex` (English) must include:**
```latex
\documentclass[11pt,a4paper]{article}
\usepackage[utf8]{inputenc}
\usepackage[T1]{fontenc}
\usepackage{amsmath,amssymb,amsthm}
\usepackage{booktabs,multirow,graphicx,hyperref,geometry}
\usepackage{enumitem,xcolor,tikz,caption,subcaption}
\usepackage{longtable,array,tabularx,float}
\geometry{margin=1in}

% Theorem environments
\newtheorem{definition}{Definition}[section]
\newtheorem{theorem}{Theorem}[section]
\newtheorem{remark}{Remark}[section]
\newtheorem{example}{Example}[section]

% Keypoint box (IMPORTANT: use lrbox to avoid brace-crossing errors)
\newsavebox{\keypointbox}
\newenvironment{keypoint}[1][]{%
    \vspace{4pt}
    \begin{lrbox}{\keypointbox}
    \begin{minipage}{\dimexpr\textwidth-2\fboxsep-2\fboxrule-2pt\relax}
        \ifx\relax#1\relax\else\textbf{#1}\\[2pt]\fi
}{%
    \end{minipage}
    \end{lrbox}
    \noindent\fbox{\usebox{\keypointbox}}
    \vspace{4pt}
}

% Custom commands
\newcommand{\fx}{\textit{FX}}
\newcommand{\bop}{\textit{BoP}}
\newcommand{\ims}{\textit{IMS}}

\title{...}
\begin{document}
\maketitle \tableofcontents \newpage
\include{week1}
% \include{week2} ...预留到 week5
\end{document}
```

**`main_cn.tex` (Chinese) must additionally include:**
```latex
\documentclass[11pt,a4paper]{ctexart}

% Font setup — use system fonts on macOS
\setCJKmainfont{Songti SC}[
    BoldFont       = {Songti SC},
    BoldFeatures   = {Weight=Bold},
    ItalicFont     = Kaiti SC,
    BoldItalicFont = Kaiti SC
]
\setCJKsansfont{Heiti SC}[BoldFont=Heiti SC]
\setCJKmonofont{STFangsong}
```

### Step 4: Write the Weekly LaTeX Files

Follow these formatting rules strictly:

#### 4a. Section Hierarchy
```latex
\section{Week N: Title}
\subsection{Major Topic}
\subsubsection{Subtopic}
\paragraph{Named concept} % for crisis names, etc.
```

#### 4b. Tables — Always Specify Column Widths
Tables in academic slides often overflow. **Always** use:
- `p{...cm}` for wide text columns
- `\small` for dense tables
- Never use bare `{lll}` — prefer `{p{2.5cm}p{5cm}p{4cm}}`

Example:
```latex
\begin{table}[H]
\centering
\caption{...}
\small
\begin{tabular}{p{3.5cm}p{8.5cm}}
\toprule
\textbf{Column A} & \textbf{Column B} \\
\midrule
...
\bottomrule
\end{tabular}
\end{table}
```

#### 4c. Mathematical Formulas
- Use `\begin{equation}...\end{equation}` for numbered equations
- Use `\begin{align}...\end{align}` for multi-line derivations
- Use `\[...\]` for unnumbered display math
- Inline math: `$...$`
- Subscripts: `\textsubscript{...}` in text mode, `_{...}` in math mode

#### 4d. TikZ Figures — Keep Them Simple
- Scale = 0.85 is a safe default
- Keep coordinate space within 7×5.5
- Don't put long text annotations inside TikZ — use the caption or surrounding text instead
- Label curves with `node[midway, above left]{...}`

#### 4e. Lists
Use `\begin{itemize}[nosep]` and `\begin{enumerate}[nosep]` for compact lists.

#### 4f. Key Insights
Wrap important takeaways in:
```latex
\begin{keypoint}[Key Insight]
...
\end{keypoint}
```
Or without title: `\begin{keypoint}...\end{keypoint}`

### Step 5: Write the Chinese Version

Key differences from English:
1. Use `ctexart` document class instead of `article`
2. Define `\newtheorem{definition}{定义}[section]` etc. with Chinese names
3. Translate all body text (but keep mathematical notation and code identifiers)
4. Keep table structures identical — just translate cell content
5. Use `\textbf{}` for bold — with the Songti SC Bold font setup it renders correctly
6. TikZ node text: translate but keep coordinates identical

### Step 6: Compile and Fix

1. **English:** `pdflatex -interaction=nonstopmode main.tex` (two passes)
2. **Chinese:** `xelatex -interaction=nonstopmode main_cn.tex` (two passes)

3. **Check for issues:**
   ```bash
   grep -E "^!|Overfull.*[0-9]{2}pt" main.log
   ```
   - `Overfull \hbox{...}` > 5pt: fix table widths or add line breaks
   - `! LaTeX Error:`: read the line number, fix the source
   - `<0.5pt` overfull: acceptable, ignore

4. **Common fixes:**
   - Wide tables → add `\small` + `p{}` columns
   - Long inline math → add `\ ` after `\textyen` or `\pounds` to allow line breaks
   - `\fcolorbox` errors → use the `lrbox` pattern (already in template)
   - Chinese bold not rendering → check font setup with `grep -i "font.*warning" log`

### Step 7: Clean Up
```bash
rm -f *.aux *.log *.out *.toc
```

## Anti-Patterns to Avoid

1. **Never** use `\fcolorbox{gray!40}{gray!10}{...\begin{minipage}...` — the brace-crossing will fail unpredictably. Always use the `lrbox` pattern.
2. **Never** use bare `{lll}` or `{ll}` column specs — always use `p{}` widths.
3. **Never** place long Chinese text inside TikZ `\node` at large x-coordinates (>7) — it will overflow the page.
4. **Never** leave `\end{center}` or `\end{itemize}` unclosed.
5. **Never** use `\（` (backslash + fullwidth parenthesis) — it's interpreted as a control sequence.
6. **Don't** add verbose docstrings or comments explaining WHAT the code does — the LaTeX is self-documenting.
7. **Don't** create analysis documents or README files unless explicitly asked.

## Typical Session Flow

1. User: "Read Week2/Lecture2.pdf, create notes in Note/"
2. Extract PDF → map structure → write `week2.tex` + `week2_cn.tex`
3. Uncomment `\include{week2}` in both main files
4. Compile both → check log → fix overfull tables → recompile → clean intermediates
5. Report: page counts and any notable issues

## Conversion Quality Checklist

Before declaring done, verify:
- [ ] All slide content is captured (no skipped sections)
- [ ] Tables use `p{}` columns and fit within `\textwidth`
- [ ] All `\begin{}` / `\end{}` pairs match
- [ ] TikZ figures compile without overlapping text
- [ ] Chinese bold renders as Songti SC Bold (not Heiti)
- [ ] Both PDFs compile with zero errors
- [ ] Intermediate files are cleaned up
