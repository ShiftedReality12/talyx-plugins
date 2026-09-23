---
name: talyx-pdf
description: >
  Render any Markdown file to a print-quality PDF in the Talyx house style (masthead title, numbered
  bookmarked sections, Archivo type, footer with page numbers) with a hard page limit. Use when the
  user asks for a PDF of a brief, memo, script or report, or when another skill in this plug-in needs
  its deliverable as a PDF. Portable: no Talyx-internal dependency.
---

# talyx-pdf

One command, one PDF, one page gate.

```
python3 format/talyx_pdf.py --input <doc.md> --out <doc.pdf> [--title "..."] [--subtitle "..."] \
    [--footer "..."] [--max-pages N]
python3 format/talyx_pdf.py --brief <brief.md> --script <script.md> --out <x.pdf> --max-pages 3
```

First run on a machine: `python3 format/talyx_pdf.py --setup` (installs Playwright + Chromium + pypdf).

## Markdown contract

| Markdown | Renders as |
|---|---|
| `# Title` (first line) | document title (overridden by `--title`) |
| `## Heading` | numbered, bookmarked section (`01 Heading`); a leading `B3 ` / `P2 ` id is stripped from the print |
| paragraphs, `- ` bullets | body at the rung's size |
| `\| a \| b \|` pipe tables | house table (uppercase head, hairline rows) |
| `**bold**`, `*italic*`, `[n]` | emphasis; `[n]` prints as a small accent citation |
| `--script <file>` | starts on a new page with its own masthead |

## The page gate (`--max-pages N`)

Renders on a four-rung density ladder (loose 11pt → compact 10pt). If the tightest rung still exceeds
N pages the command exits 2 with JSON naming the longest sections and their word counts. It never
truncates and never spills silently. A passing render prints `{"ok": true, "pages": n, "rung": ...}`.

## Rules

- **Rule 1** Read the JSON result; a run whose `ok` is false has no deliverable. _Fails when:_ a 4,000-word section renders 7 pages at compact and the command exits 2.
- **Rule 2** The footer is the caller's line (profile, status, metrics); default `Talyx AI · talyx.ai`. _Fails when:_ `--footer` text is absent from the last page's text extraction.
- **Rule 3** Never hand-edit the PDF or the HTML; change the Markdown and re-render. _Fails when:_ the PDF's text differs from a fresh render of its source.

Made by Talyx AI, https://talyx.ai. Free to use under the licence in the plug-in's `LICENSE` file.
