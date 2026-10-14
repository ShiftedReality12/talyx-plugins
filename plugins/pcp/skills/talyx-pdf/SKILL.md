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
python3 format/talyx_pdf.py --brief <brief.md> --script <script.md> [--gaps <gaps.md>] --out <x.pdf> --max-pages N \
    [--brief-pages N] [--script-subtitle "..."] [--script-after B5]
```

It uses Playwright's Chromium if installed, else the Chrome, Edge or Chromium already on the computer. With
none of them: `python3 format/talyx_pdf.py --setup` once (installs Playwright + Chromium + pypdf).

## Markdown contract

| Markdown | Renders as |
|---|---|
| `# Title` (first line) | document title (overridden by `--title`) |
| `## Heading` | numbered, bookmarked section (`01 Heading`); a leading `B3 ` id sets the printed number; `P2 ` ids number in order, so a left-out one leaves no gap; ids are stripped from the print |
| paragraphs, `- ` bullets, `1.` numbered items, `- [ ]` / `- [x]` checklist items | body at the rung's size; indent 2+ spaces for a sub-bullet (two levels) |
| `**Label:** text` | a label line: semibold label, hanging indent, no bullet |
| `> text` | a pull quote with an accent rule |
| `\| a \| b \|` pipe tables | house table (uppercase head, hairline rows); a first header cell of `#` makes a compact one-line-per-row sources table; an empty header row makes a label grid |
| `**bold**`, `*italic*`, `[label](https://…)`, `[n]` | emphasis and links; `[n]` prints as a small accent citation that never starts a line; ` -- ` prints as an em dash |
| `--script <file>`, `--gaps <file>` | each starts on a new page under its own masthead (its `# ` line, else "Meeting script" / "Before you walk in") |
| `--brief-pages N` | the brief fills exactly N pages with its last section (the evidence ledger) starting on page N, so the script starts on page N + 1; a short brief moves the ledger to page N, never padding; exits 3 if the brief ends before page N - 1 |
| `--script-after B5` | the script follows brief section B5; the rest of the brief continues after it, without a masthead |
| `--style brief` | the Intelligence Brief look: `--classification` line and logo stamp above the name; the lines under `# Name` print as its identity and meta lines; `## B1` is the Take box; brief blocks are unnumbered, script sections print `1.` |
| `--columns "B3\|B4,P1+P2\|P5"` | those sections side by side (`\|` between the columns, `+` within one); the first named section sets where the pair stands |

## The page gate (`--max-pages N`)

Renders on a four-rung density ladder (loose 11pt → compact 10pt). If the tightest rung still exceeds
N pages the command exits 2 with JSON naming the longest sections and their word counts. It never
truncates and never spills silently. A passing render prints `{"ok": true, "pages": n, "rung": ...}`.

## Rules

- **Rule 1** Read the JSON result; a run whose `ok` is false has no deliverable. _Fails when:_ a 4,000-word section renders 7 pages at compact and the command exits 2.
- **Rule 2** The footer is the caller's line (profile, status, metrics); default `Talyx AI · talyx.ai`. _Fails when:_ `--footer` text is absent from the last page's text extraction.
- **Rule 3** Never hand-edit the PDF or the HTML; change the Markdown and re-render. _Fails when:_ the PDF's text differs from a fresh render of its source.

Made by Talyx AI, https://talyx.ai. Free to use under the licence in the plug-in's `LICENSE` file.
