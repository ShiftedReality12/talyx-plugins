---
name: pre-call-prep
description: >
  Prepare for an upcoming meeting with a named person. Runs a short intake, researches the
  person and their organisation from public sources, then writes a structured pre-call brief
  with sourced facts, discovery questions, an opening, guardrails and a follow-up note draft.
  Use when the user mentions pre-call prep, meeting prep, call preparation, researching someone
  before a meeting, talking points for a call, or shares an intake list of names and
  organisations. Do not use for general web research unrelated to a meeting, or for notes on a
  meeting that has already happened.
---

# Pre-call prep

One method, three stages: **intake, then public-source research, then a structured pre-call brief.** Every fact in the brief traces to a public source. Nothing is invented.

## Stage 1: Intake

Read `references/intake.md`. Collect, at minimum, the person's full name and organisation, the meeting date and the meeting objective. A CSV template is at `assets/intake-template.csv`. One row is one person; up to 8 people per run.

Classify the meeting from the objective:

- **Prospect**: the person may become a client. The brief builds toward a clear next step.
- **Referral source**: the person knows people who may become clients. The brief builds toward specific introductions.
- **Partner**: the person's firm could work alongside the user's firm. The brief builds toward a shared opportunity.
- **Relationship**: an existing client or contact. The brief builds toward deepening the relationship.

If the objective is unclear, choose **Referral source** unless research shows a direct need.

## Stage 2: Public-source research

Read `references/research-protocol.md`. Four passes per person: identity, links, organisation, voice. Compile a research file per person with a source log. If research is thin, read `references/research-gaps.md`.

Hard rules:

- Public sources only.
- Every fact carries a source URL and a `[DIRECT]` or `[SEARCH]` tag.
- Two or more people with the same name: stop and ask the user to confirm the right one.
- Never invent organisation names, deals, figures, titles, dates or quotes. Unconfirmed facts are marked `[UNVERIFIED]` or left out.
- Leave out anything personal that a professional would not raise in a first meeting: health, family matters not in the public professional record, political giving, litigation. Note in the guardrails that it was left out on purpose.

## Stage 3: The pre-call brief

Read `references/brief-structure.md` and write the brief in that order. Then run every check in `references/quality-checks.md` and rewrite what fails.

Save each brief as Markdown to `./pcp-briefs/YYYY-MM-DD-<first>-<last>.md` unless the user names another location.

## Reference files

| Stage | File | Contents |
|-------|------|----------|
| 1 | `references/intake.md` | Intake fields, required and optional |
| 2 | `references/research-protocol.md` | The four research passes and the source log |
| 2 | `references/research-gaps.md` | What to do when a source fails or research is thin |
| 3 | `references/brief-structure.md` | The brief, section by section |
| 3 | `references/quality-checks.md` | The checks every brief passes before hand-over |

Read only the file the current stage needs.

## About

Made by Talyx AI, https://talyx.ai. Free to use under the licence in the plug-in's `LICENSE` file.
