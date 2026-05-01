---
name: notebooklm-lit-review
description: Query a project NotebookLM knowledge base for literature-grounded answers with Harvard citations. Covers notebook setup, effective querying, citation formatting, and the full PDF ingestion pipeline (BibTeX key renaming, OpenAlex/Semantic Scholar metadata, markitdown conversion, index maintenance). Use whenever analyzing, comparing, or citing papers from a managed academic reference corpus.
workflow_stage: research
compatibility:
  - claude-code
author: Eric Jiang
version: 1.0.0
tags:
  - NotebookLM
  - nlm
  - literature-review
  - citations
  - knowledge-base
  - academic
---

# NotebookLM Literature Review Skill

## Purpose

Use NotebookLM as a project knowledge base for literature-grounded research. Query a managed paper corpus and get answers with verifiable Harvard citations — never rely on training-data recall for literature claims.

## When to Use

- Analyzing, comparing, or reviewing papers from a reference corpus
- Finding methodological details, empirical results, or data sources from the literature
- Writing or updating literature reviews, method comparisons, or project design documents
- Checking what the literature says about a specific model, method, or finding
- Drafting any academic document that cites literature
- Ingesting new PDFs into the paper corpus

## NotebookLM Notebook Setup

- **Notebook name**: typically named after the research domain
- **Alias**: short handle used with `nlm` CLI (e.g., `macro`)
- **Sources**: PDFs and Markdown files uploaded to NotebookLM are the ground-truth corpus
- **Drift check**: NotebookLM source list may lag local corpus; verify with `nlm source list <alias>` before treating it as complete

## Query Workflow

### Step 1 — Check Auth

```bash
nlm login --check
```

If expired, ask the user to run `nlm login`.

### Step 2 — Query the Notebook

```bash
nlm notebook query <alias> "YOUR QUESTION HERE"
```

Best practices:
- Ask specific, focused questions rather than broad ones
- Include method names, paper keywords, or author names in the query
- For multi-topic questions, run 2-3 separate queries in parallel
- Use `--conversation-id` for follow-up questions on the same topic

### Step 3 — Map Answers to Citations

NotebookLM returns answers with numbered citations linked to source IDs. Cross-reference with `nlm source list <alias>` to identify the correct paper.

## Harvard Citation Format (MANDATORY)

Every literature claim MUST be backed by a Harvard-style citation.

**In-text**: `Author (Year)` or `(Author, Year)`

```
"Stock and Watson (2002) pioneered PCA for diffusion index construction."
"Dynamic factor models handle ragged-edge data (Bańbura et al., 2013)."
```

**Reference list**: Full Harvard format

```
Author, I. (Year) 'Title', *Journal*, Volume(Issue), pp. XX-YY.
```

**Rules**:
- Never present a factual claim from the literature without a Harvard citation
- If NotebookLM cannot confirm a claim because the source is absent or unsupported, explicitly state this and verify against the local PDF/Markdown
- Use `\cite{}` BibTeX keys internally when drafting, then expand to full Harvard format

## PDF Ingestion Pipeline

When a new PDF paper is downloaded, execute these steps in order.

### Step 1 — Rename PDF to BibTeX Key

```
author_author_year_keyword.pdf
```

- All lowercase, underscores between components
- First author last name, second author last name, year, distinctive title keywords
- Example: `stock_watson_2002_diffusion_indexes.pdf`

### Step 2 — Fetch Citation Metadata

Primary — OpenAlex:

```bash
curl -s "https://api.openalex.org/works?search=TITLE_HERE&per_page=3" | python3 -c "
import json, sys
data = json.load(sys.stdin)
for r in data.get('results', [])[:3]:
    print(f\"title: {r['title']}\")
    print(f\"cited_by_count: {r['cited_by_count']}\")
    print(f\"doi: {r.get('doi', 'N/A')}\")
    print('---')
"
```

Fallback — Semantic Scholar:

```bash
curl -s "https://api.semanticscholar.org/graph/v1/paper/search?query=TITLE_HERE&limit=3&fields=title,citationCount,year,authors" | python3 -c "
import json, sys
data = json.load(sys.stdin)
for p in data.get('data', [])[:3]:
    print(f\"title: {p['title']}\")
    print(f\"citationCount: {p['citationCount']}\")
    print(f\"year: {p.get('year', 'N/A')}\")
    authors = ', '.join(a['name'] for a in p.get('authors', []))
    print(f\"authors: {authors}\")
    print('---')
"
```

Record: `cited_by_count`, `source` (`OpenAlex` / `Semantic Scholar`), `checked_date` (YYYY-MM-DD).

### Step 3 — Add BibTeX Entry

Use `@article` for journal papers, `@techreport` for working papers. Include citation metadata in `note`:

```bibtex
@article{bibtex_key,
  author = {Last, First M. and Last, First M.},
  title = {Full Paper Title},
  journal = {Journal Name},
  year = {YYYY},
  volume = {VV},
  number = {NN},
  pages = {XX--YY},
  doi = {DOI},
  file = {pdf/bibtex_key.pdf},
  note = {Citation count: NNN, source: OpenAlex, checked YYYY-MM-DD.}
}
```

### Step 4 — Convert PDF to Markdown

Primary — `markitdown`:

```bash
markitdown "pdf/bibtex_key.pdf" > "papers/bibtex_key.md"
```

Fallback — `pdftotext` (image-heavy or complex-layout PDFs):

```bash
pdftotext -layout "pdf/bibtex_key.pdf" "papers/bibtex_key.md"
```

If both methods fail or produce content that does not match the expected paper, the PDF may be wrong — flag and re-download.

### Step 5 — Update Index

Add the paper to the appropriate section of the paper index, keeping the mapping between BibTeX key, Markdown path, and PDF path.

### Step 6 — Verify

```bash
# Confirm all files exist and content matches
ls -la "pdf/bibtex_key.pdf"
ls -la "papers/bibtex_key.md"

# Check first page of PDF matches expected paper
pdftotext -l 1 "pdf/bibtex_key.pdf" - | head -3

# Check Markdown is readable
head -3 "papers/bibtex_key.md"

# Confirm BibTeX entry is valid
grep -A 12 "bibtex_key" references.bib
```

## Quick Commands

```bash
# List all sources in the notebook
nlm source list <alias>

# Query the notebook
nlm notebook query <alias> "How does LDA compare to dictionary methods for FOMC text?"

# Follow up on a previous query
nlm notebook query <alias> "What about RoBERTa?" --conversation-id <id>

# Check notebook health
nlm notebook get <alias>

# Refresh source list (after adding new papers)
nlm source sync <alias>
```

## Anti-Patterns

1. **Never** rely on training-data recall for literature claims — always query NotebookLM first
2. **Never** present a factual claim from the literature without a Harvard citation
3. **Never** assume the NotebookLM source list matches the local corpus — check with `nlm source list` before querying
4. **Never** skip PDF content verification — a correctly-named PDF can contain wrong content
5. **Never** skip Markdown readability check — garbled Markdown silently degrades NotebookLM answers
6. **Don't** ask broad questions like "summarize all papers" — NotebookLM works best with focused queries
7. **Don't** forget to cross-reference NotebookLM citations with actual source IDs
