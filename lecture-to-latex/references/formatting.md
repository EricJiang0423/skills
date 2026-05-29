# Formatting Reference

Load this file when creating or repairing note layout.

## Preambles

- Compile all note PDFs with `xelatex`. Do not mix `fontspec` with `pdflatex`.
- English notes use `article` plus `fontspec`.
- Chinese and bilingual notes use:

```latex
\documentclass[11pt,a4paper,fontset=none]{ctexart}
\setCJKmainfont{Songti SC}[
    BoldFont       = {Songti SC},
    BoldFeatures   = {Weight=Bold},
    ItalicFont     = {Songti SC},
    BoldItalicFont = {Songti SC}
]
\setCJKsansfont{Heiti SC}[BoldFont=Heiti SC]
\setCJKmonofont{Songti SC}
\setlength{\parindent}{0pt}
```

- Use `\geometry{margin=1in, headheight=15pt, headsep=8mm}` to avoid `fancyhdr` warnings.
- Include `\usetikzlibrary{arrows.meta,positioning,shapes.geometric}` when TikZ appears.

## Headers

- Do not put long lecture titles in the running header.
- English notes should use short marks such as `Week \thesection`.
- Bilingual notes should use a static short center header and `Bilingual Notes` on the right.
- If the user reports header overflow, shorten header text first; do not reduce the font until the content is already short.

## Chinese Notes

- Body text should not have first-line indentation: `\setlength{\parindent}{0pt}`.
- Use compact but readable list margins:

```latex
\setlist[itemize]{leftmargin=1.8em,itemsep=2pt,topsep=4pt}
\setlist[enumerate]{leftmargin=2.2em,itemsep=2pt,topsep=4pt}
\setlist[description]{style=nextline,leftmargin=2em,itemsep=2pt,topsep=4pt}
```

- Add English originals for technical terms on first occurrence in each major section: `在险价值（Value at Risk, VaR）`.
- Keep mathematical notation, ticker symbols, variable names, and source labels unchanged unless the source itself translates them.

## Bilingual Notes

- Use these environments:

```latex
\newenvironment{english}{\begin{quote}\itshape}{\end{quote}}
\newenvironment{cnblock}{\begin{quote}}{\end{quote}}
```

- Never define a `chinese` environment under `ctexart`; it can collide with ctex internals.
- Alternate English and Chinese at paragraph or concept level. Do not split a formula from its explanation unless the source does.
- Put bilingual chapter files in `chapters-bilingual/weekN_bilingual.tex`.

## Heading Depth

- Use `\section{Week N: ...}` for each week.
- Use `\subsection` for major lecture topics.
- Use `\subsubsection` only when a source section has real substance.
- For named examples, slide labels, or small concepts, prefer:

```latex
\medskip
\noindent\textbf{Named concept.}
```

- Do not turn every slide bullet into a heading. Preserve content while reducing heading fragmentation.

## Tables

- Never use bare `{lll}`, `{ll}`, or similar for content-heavy tables.
- Prefer fixed-width columns:

```latex
\begin{tabular}{p{0.24\textwidth}p{0.34\textwidth}p{0.34\textwidth}}
```

- Use `tabularx` for flexible text-heavy tables and `longtable` for multi-page tables.
- If a table creates a blank page or persistent overfull boxes, split it by topic or move details into a list.
- Reference readings and links should be bibliography-style lists, not large tables of URLs.

## Math And Worked Examples

- Use `equation` for important numbered formulas, `align` for derivations, and `\[...\]` for short unnumbered displays.
- Keep formula assumptions and parameter definitions next to the formula.
- For worked examples, copy source values exactly and show calculation steps only when they are supported by the source or follow directly from displayed formulas.

## TikZ

- Keep TikZ diagrams simple and within the page.
- Use `arrows.meta` and `>=Stealth`; avoid legacy arrow specs such as `-latex'`.
- Avoid long Chinese text inside nodes. Put long explanations in captions or surrounding prose.

## Keypoint Boxes

Use the `lrbox` pattern from the templates. Do not wrap a `minipage` directly inside a fragile `\fcolorbox{...}{...}{...}` body.
