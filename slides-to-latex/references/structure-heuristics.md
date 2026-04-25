# Structure Detection Heuristics

Extended rules for identifying section-divider slides across common
presentation styles used in academic and corporate settings.

---

## Universal signals (apply to all styles)

A slide is a **section divider** when ALL of:
- Fewer than 25 words of extractable text
- No bullet-point markers (`•`, `-`, `*`, `–`, or `\item` equivalent)
- No equation content (no `$`, `\frac`, `\int`, etc.)
- Title text is significantly larger than surrounding slides (detected
  visually by reading the rasterized image)

A slide is **definitely content** when ANY of:
- Contains a numbered list or bullet points with ≥ 3 items
- Contains an equation or code block
- Contains a data table
- Has a two-column layout with body text on both sides

---

## Style-specific rules

### Beamer (dark theme — common in CS/math lectures)

Section dividers typically have:
- Dark/colored full-bleed background
- Single large white or light-colored text, centered
- No footer/header decorations
- Often accompanied by a section number (e.g., "§2", "2.")

Detection: rasterize the page. If the dominant color is non-white and
there are ≤ 2 text regions, classify as section divider.

### Beamer (default/light theme)

Section dividers often use the `\section{...}` automatically generated
"section page" which shows:
- The section title in a prominent font
- A subtle progress bar or navigation dots at the top
- No slide body content

### PowerPoint / Keynote (academic)

Common patterns:
- Slide with a bold title only and a decorative horizontal rule underneath
- Slide with a colored banner/bar at top, title text, and empty body
- "Agenda" or "Outline" slides — treat these as **content** slides, not
  section dividers (they are typically slide 2–3 and list the sections)

### Corporate PowerPoint

Section dividers may look like:
- A full-bleed image with a text overlay
- A gradient background with a centered title
- A "divider" template with the section number on the left and title on
  the right

---

## Handling "Agenda / Outline" slides

Agenda slides (typically page 2–4 in a deck) list all the sections.
They are **not** section dividers; they are content slides. However,
they are goldmines for structure inference:

1. If an agenda slide is detected, parse its list items as the section
   titles for the whole deck.
2. Map those titles to subsequent section-divider slides.
3. If the agenda lists topics but no matching section-divider slides
   are found later, synthesize `\section{}` entries based on the agenda.

---

## Fallback: automatic structure inference (no dividers found)

When no section dividers are detected:

1. Read the first 3–5 words of each slide's text.
2. Cluster slides by semantic similarity (rough grouping is fine —
   look for thematic shifts in vocabulary).
3. Assign a section break at each major theme transition.
4. Name the section in English based on the dominant keywords, then
   translate the section name to Chinese.

Typical academic lecture groupings:
- Opening / Motivation / Background (slides 1–5)
- Core Theory / Methods (slides 6–15)
- Examples / Case Studies (slides 16–22)
- Results / Evaluation (slides 23–28)
- Conclusion / Future Work (slides 29–end)

Use these as a backup taxonomy only if semantic clustering fails.

---

## Handling mixed-language slides

Some decks have:
- English titles + Chinese body text
- Chinese slide numbers/section labels + English content

In these cases:
- Detect language per text block, not per slide
- The slide is a section divider if structure signals are met regardless
  of which language the title is in
- In the `\section{}` macro, put whichever language is the title as the
  primary and translate the other

---

## Equation and diagram slides

Slides that are primarily a single large equation or diagram with minimal
text are **content slides**, not section dividers — even if they have
little text. They should be rendered as `\slideentry{}{}{}` with the
image being the primary content and minimal text in the columns:

```latex
\slideentry{15}{%
  % English
  Key result: the closed-form solution (see slide image).
  Derivation is in §3 of the notes.
}{%
  % Chinese translation placeholder
  Key result translated into the target language.
  Derivation reference translated into the target language.
}
```
