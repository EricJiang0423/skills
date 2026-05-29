# AllExercises Reference

Load this file when the task includes mock exams, answer booklets, weekly examples, practice questions, or "把所有例题整理到 AllExercises".

## Scope

Include paper-exam style material:

- Lecture worked examples and numerical examples.
- Practice questions embedded in slides or notes.
- Mock/exam questions and teacher-solution questions when provided.
- Short interpretation questions tied to a displayed formula, table, or result.

Exclude unless the user explicitly asks:

- Large Excel, coding, or coursework tasks.
- Pure reference tables with no question.
- Duplicate versions of the same conceptual prompt.
- Data tables that are not used by any included question.

## Coverage Audit

- Audit all weeks, not only the newest or most visible week.
- Search for labels such as `Practice Questions`, `Worked Example`, `Numerical Example`, `Example`, `Exercise`, `Question`, `Solution`, `计算`, `例题`, `练习`.
- Compare the final exercise list against every lecture chapter and raw extract.
- If Week 4 and Week 5 share the same example, merge once and label it `Week 4/5`.

## Booklet Modes

When useful, generate both:

- Blank answer booklet: questions only, with no answer-space bloat unless the user asks for writing space.
- Solutions-only booklet: worked answers and explanations without blank answer boxes.

Use clear environments such as:

```latex
\newif\ifsolutiononly
% \solutiononlytrue

\newenvironment{solutionbox}{...}{...}
\newenvironment{aisolutionbox}{...}{...}
```

Mark AI-derived solutions or reconstructed solutions with `aisolutionbox` when they are not directly from a teacher solution.

## Organization

- Group by source: mock/exam material first if requested, then weekly lecture worked examples.
- Number lecture examples as a separate part, for example `Part E -- Weekly Lecture Worked Examples`.
- Keep source labels in question headings: week, topic, and source type.
- Do not over-expand conceptual bullets into artificial exam questions unless the user asks for that style.

## Verification

- Compile both modes when both are requested.
- Remove unnecessary first-page blank space and unused data tables.
- Confirm the final booklet contains examples from every week that has examples.
