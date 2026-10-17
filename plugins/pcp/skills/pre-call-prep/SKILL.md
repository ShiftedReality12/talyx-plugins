---
name: pre-call-prep
description: >
  Prepare for an upcoming meeting with a named person, company or deal. A few one-time setup
  questions, research from public sources by targeted web search (LinkedIn only as its public search results
  show it, never your browser), plus your own files when you give them, and ONE 3-page PDF: a 2-page
  Intelligence Brief and a 1-page meeting script, every fact
  cited. Use when the user mentions pre-call prep, meeting prep, call preparation, researching someone
  before a meeting, talking points, or shares an intake list. Do not use for general research unrelated
  to a meeting, or for notes on a meeting that has already happened.
---
<!-- GENERATED from pcp.yaml (sha256:2e44ead61a4c) by render_skill.py -- edit pcp.yaml, never this file -->

# Pre-call prep (v3.1.0)

Stages, dependency-ordered: **setup once -> intake -> intelligence collection -> behavioral profile -> Intelligence Brief -> debrief.**
This file is the procedure: for each step, what to do, where to stop and what must pass. Each step's **Load** line names the files
it reads: load them before the step, because they hold the tables, rules and wording this file leaves out. A **Config** line names
the keys a step may read from `pcp.json` (pcp.yaml as JSON); the scripts read it, so never edit or retype it.
Every fact traces to a source. Nothing is invented. The deliverable is one 3-page PDF, the Intelligence Brief. Nothing else is emitted.

**No shell or code tool (plain chat)?** Run the same stages anyway; never stop or refuse for lack of tools. Keep claims, coverage
and the behavioral read in your working notes, not in the reply: one short status line, then nothing until a question or the
brief itself (S2-10). Deliver the full Intelligence Brief in the chat as `references/in-chat.md` says.

Made by Talyx AI, https://talyx.ai. Free to use under the licence in the plug-in's `LICENSE` file.

## Stage 0: Setup (once)

**Load:** `references/setup.md` (how PCP thinks, the setup questions and rules CAL-1 to CAL-5, the intake columns); `references/socratic-questions.md` (when to ask the user, and the questions written for the room).

If `~/.pcp/profile.yaml` is missing or invalid, or `--recalibrate` is passed, ask these questions with
`AskUserQuestion` -- Q1+Q2+Q3+Q4 · Q5+Q6+Q7+Q9 · Q8 (free text), first option recommended -- (the host's native question tool: the structured question tool in
ChatGPT, Codex and Grok), asking only those the saved profile has no answer for. A label such as 'Sales / BD' is one option.
Whichever way you ask, say it in one line of the reply before the call ('Two quick questions: answer in the popup, or skip and I'll use the recommended answers.'), then stop. Do no search, page open or file work until the user's next message or the tool's answer. Setup questions: a skip takes the recommended option, stored defaulted. A question from a trigger below: a skip means go on without the answer, and the gap stays Not determined. Ask each question once. Only if the host has no question tool, or the tool returns no answer:
Type the questions in the reply, numbered, options numbered, only when the host has no such tool, or when the tool returns no answer (a popup that closes empty is not an answer): then end the message with 'Reply with your answers, or reply skip and I'll go on without them.' Then write the profile
(`pcp_profile_format: 1`, answers under `profiles: <name>: answers: Qn: {value, defaulted}`, plus `context`
and `linkedin` when set) and continue.

**Rows:**

- **CAL-1** Ask only the questions with no saved answer in ~/.pcp/profile.yaml -- all of them the first time, all again with --recalibrate. Otherwise read it silently.
- **CAL-2** A skipped answer takes the first (Recommended) option and is stored with defaulted:true; the masthead's Prepared for and Depth show the saved answers.
- **CAL-3** The improve loop may PROPOSE a profile change (one line, with the debrief evidence) but never applies one without a yes.
- **CAL-4** Files named in Q8 (or later with --context <path>) are read once; their paths and a summary of at most 150 words go in the profile under context. Facts taken from them are tagged Yours, never presented as public. Supported: .pdf .docx .md .txt .csv. Any other file gets one line naming the supported types, and the profile is left unchanged.
- **CAL-5** Ask every question with the host's native popup tool, and nothing else works until it is answered: say in one line of the reply what skip does, then stop. A typed list only where the host has no tool or the popup came back empty. Before any search, check the saved offer and domain against what this run asks for. Full rule: `references/setup.md`.

## Stage 1: Intake

**Load:** `references/socratic-questions.md` (when to ask the user, and the questions written for the room).

**Input contract** (declared before behaviour):

| Input | Type | Source | Required | Fallback |
|---|---|---|---|---|
| `arguments` | path.csv | 'Full Name, Organisation' | empty | $ARGUMENTS | yes | ask the required intake fields in one message |
| `profile` | yaml | ~/.pcp/profile.yaml | yes | run calibration |
| `meeting.objective` | text | intake row or one question | yes | ask: What do you want to walk out of this meeting with? |
| `target.kind` | person|company|deal | intake or profile.target.kind_default | yes | person |

**Context contract** -- read, in this order: profile, intake row, this stage's rows, references/socratic-questions.md. Budget: 900 words. Not read: reference files of later stages, prior briefs.

**Rows:**

- **S1-1** Do not start research without a full name and an organisation.
- **S1-2** Two or more people match the name: stop and ask which one. Wrong-person research is worse than none.
- **S1-3** Up to 8 targets per run; research targets in parallel, write briefs in turn.
- **S1-4** Ask the user only as references/socratic-questions.md says: when a trigger fires, at most 2 questions after setup, in one message, each skippable, asked with the native question tool and waited for (CAL-5). The offer-conflict trigger fires before the first search: run eval.py offer-conflict --saved '<Q8 offer>' --request '<what the user asked for>' (exit 1 = ask).

## Stage 2: Intelligence collection

**Load:** `references/collection.md` (the source types and their query templates, placeholders, registers, exclusions, source quality, the three records, LinkedIn status, rules S2-7, S2-9 and S2-11); `references/osint-search.md` (the search rounds, their queries, operators per host, the identity lock).

**Config:** `pcp.json` keys `families.*.weight`, `families.*.kinds`, `families.*.socmint`, `retention.*` -- the ratchet and duf weigh and filter source types by weight and kind; retention is the jurisdiction's rule for claims.jsonl.

**Input contract** (declared before behaviour):

| Input | Type | Source | Required | Fallback |
|---|---|---|---|---|
| `resolved_families` | list | families filtered by profile (kind, depth, socmint) | yes | none -- derived |
| `exclusions` | list | exclusions.base + exclusions.by_jurisdiction[profile.jurisdiction] | yes | none -- derived |
| `known_context` | text | intake Notes column, the user's answers, profile.context and any file the user gives | no | empty |

**Context contract** -- read, in this order: resolved_families with query templates, exclusions, target identity, known_context. Budget: 1200 words. Not read: rubric, brief structure, script structure.

**Outputs:** `claims.jsonl` (id, claim, family, url, retrieved_at, published, tag, grade, confidence, exclusion_hit); `coverage` (base (each source type's queries as sent), rounds (each query as sent, operators the search ignored), families_attempted, families_total, hits_by_family, failed_urls, linkedin, status)

**Rows:**

- **S2-1** Public sources found by targeted web search in rounds (osint), plus what the user gives: their files and answers (tag Yours), a LinkedIn profile they save among them (S2-7). LinkedIn itself only as its public search results show it; never a signed-in or automated browser. No paid data the user has not supplied; nothing collected in bulk. A page behind a login wall is a failed URL: list it in coverage.failed_urls and cite another source.
- **S2-2** Every claim carries url (or the file name, for Yours), retrieved_at, published (the source's own publication or event date; none when the source is undated), tag Direct|Search|LinkedIn|Yours, grade Measured|Derived|Inference|Not determined, and confidence C1 (primary, dated) | C2 (reputable secondary) | C3 (single weak source) | C4 (inferred).
- **S2-3** A claim that hits an exclusion is dropped BEFORE the writer sees it and counted in coverage.excluded; the ledger's Left out on purpose row names the topic, never the fact.
- **S2-4** Coverage is a required output: families_attempted/families_total and hits per family. A run without coverage is not a run.
- **S2-5** Status FULL requires >= 1 C1/C2 claim in >= research.full_threshold[depth] families; else LIMITED, stamped in the masthead.
- **S2-6** Run the counter-evidence family last: search for what would contradict the strategic read.
- **S2-7** LinkedIn only as a search result shows it, as the one address the user gives, or as a profile they saved; never sign in, never open or drive a browser. State which in the LinkedIn line and the Coverage row. Full rule: `references/collection.md`.
- **S2-8** Source quality: prefer the primary source (the organisation, filings, the person's own words). Never cite a source_quality.exclude domain (people-search and unreachable sites); a source_quality.weak domain is at most C3 and never the only support for a fact on page 1. Cite a fact only where the ledger row says it: hypotheticals (Reverses if, Stop if) carry no citation. Before render, check every link: dead links are replaced or the fact is dropped; blocked links (the site refuses bots) are kept.
- **S2-9** Two passes, both mandatory: the base pass (each enabled source type's own query, filled), then the rounds in references/osint-search.md; each round's queries go out together; the Run row counts both. Full rule: `references/collection.md`.
- **S2-10** Quiet research: at most one short status line per stage in the reply (at most 30 words, e.g. 'Researching <name>, <organization> for <objective>. The results go in the brief.' then 'Writing the brief.'), and nothing between: no round line, no query list, no source or progress note, no list of what was found. Search queries live in coverage.json's rounds and in your reasoning, and the Run row counts them ('N searches in M rounds'); they never appear in chat, whatever the host. A question (S1-4) or a stop for a wrong-person match is the only other text. A search call showing as a tool row in the host is the host's, not a message.
- **S2-11** Run collection as a background job where the host has one; take back the three records, not the pages. Full rule: `references/collection.md`.

## Stage 3: Behavioral profile

**Load:** `references/profile.md` (the six dimensions with their Low, Mid and High phrases, the evidence tiers, what they may want).

**Input contract** (declared before behaviour):

| Input | Type | Source | Required | Fallback |
|---|---|---|---|---|
| `claims.jsonl` | jsonl | S2 | yes | none |
| `rubric` | rows | pcp.yaml rubric | yes | none |
| `authority_level` | high|medium | profile.caller.authority_level | yes | medium |

**Context contract** -- read, in this order: rubric dimensions + bands, claims tagged family in F1/F5/F6/F7, authority_level. Budget: 1500 words. Not read: claims of other families, brief structure.

**Outputs:** `read.json` (dimension, band, evidence_tier, observation_ids, meeting_meaning)

**Rows:**

- **S3-1** Read each of the six dimensions only from observation_ids in claims.jsonl; a band with fewer observations than its tier minimum is reported as 'no read' -- never guessed from role.
- **S3-2** B6's evidence tier is the highest tier at least three of the six dimensions reach (a no read counts as low). It gates page 3: low -> no Read the room (P5); high AND authority_level high -> Influence (P6). Otherwise P6 is left out.
- **S3-3** Every Your move in B6 is a rubric meaning in pcp.yaml, word for word, or No read; no band phrase is written in prose.
- **S3-4** Depth deep adds what they may want: <= 3 hypotheses about what the person wants from this meeting, each with the claim that would disprove it.

## Stage 4: Intelligence Brief

**Load:** `references/brief.md` (plain words, the brief's blocks and the script's blocks with their word budgets, the fields.json keys, rules S4-4, S4-11, S4-12 and S4-13); `references/checks.md` (every check with its command, the test that makes each rule fail, the metric and the eval.py commands); `references/in-chat.md` (the brief delivered in the chat, rule S4-10), only when the host has no shell, python3 or browser engine, so no PDF can be made.

**Input contract** (declared before behaviour):

| Input | Type | Source | Required | Fallback |
|---|---|---|---|---|
| `claims.jsonl` | jsonl | S2 | yes | none |
| `read.json` | json | S3 | yes | none |
| `profile` | yaml | ~/.pcp/profile.yaml | yes | none |
| `page_budget` | rows | pcp.yaml brief + script | yes | none |

**Context contract** -- read, in this order: brief sections with word budgets, script beats and sections, claims (C1/C2 first), read.json, profile.caller, guardrails. Budget: 3000 words. Not read: rubric evidence lists, family query templates.

**Outputs:** `brief.md` (pages 1-2); `script.md` (page 3); `<out>/<date>-<slug>-intelligence-brief.pdf` (ONE 3-page PDF via format/talyx_pdf.py --style brief --brief-pages 2 --max-pages 3; the script on page 3)

**Rows:**

- **S4-13** Never write brief.md or script.md. Fill fields.json (the keys are in references/brief.md) and run `python3 eval.py assemble <folder>`. Full rule: `references/brief.md`.
- **S4-1** Every fact in B1-B9 and the script cites a ledger number [n]; the ledger (B10) lists only cited facts, numbered in order of first use. A fact with no citation is a defect, not a style choice.
- **S4-2** Every sentence passes the swap test against caller.offer_one_line and the target: if another target's name would leave it true, delete it.
- **S4-3** Where the host can run scripts and a browser engine (Claude Code, Claude Cowork, Codex, ChatGPT agent or work mode), render ONLY through format/talyx_pdf.py --style brief --brief-pages 2 --max-pages 3, never Markdown or HTML as the deliverable. The PDF is exactly 3 pages: the brief fills pages 1-2 (a short brief puts the evidence ledger on page 2 -- never filler) and the script is page 3. Check it with eval.py pdf. Where render is impossible, follow S4-10.
- **S4-11** Spend words on facts, not framing: count the distinct cited facts before rendering and replace filler with a cited fact. Full rule: `references/brief.md`.
- **S4-12** Compose from the three records alone, then run `python3 eval.py records <folder> --depth <depth> --brief brief.md` before you say the run is done. Full rule: `references/brief.md`.
- **S4-10** No shell, no python3 or no browser engine: deliver the full brief in the chat, never a summary, exactly as references/in-chat.md says. Full rule: `references/in-chat.md`.
- **S4-4** An overflow fails the run with the section word counts; fix it only by cutting words in the sections the renderer names, never a cited fact, a ledger row or a source, never the page settings. Full rule: `references/brief.md`.
- **S4-5** The masthead's meta line carries meeting, prepared for, depth, sources, status and date; the ledger's Run row carries the run details; the footer carries only the Intelligence Brief, the person and the page numbers. The identity line is organization | role, since year | city: the city only when a source confirms it; anything unconfirmed or unknown is left out, never printed as '(not confirmed)', 'not published' or 'Not determined'.
- **S4-6** A block or line prints only as its Prints when says: a line PCP cannot fill from evidence is left out, or reads Not determined where its row says so. Never filler.
- **S4-7** Every Not determined -- a **Label:** line or a table cell -- and every No read in B6 is a gap; the ledger's Still open row asks at most 4 of them, highest value first, as 'Label: question?', as references/socratic-questions.md says.
- **S4-8** Plain words: nothing printed uses a plain_words.banned term or an internal code; the person's own quoted words are exempt.
- **S4-9** Experience (Q9) shapes page 3 only: new -> P1, P3 and P4 each end with a **Why:** line of at most 12 words; top -> the Hook and each objection's answer are at most 15 words; experienced -> neither.

## Checks (all pass before render)

**Load:** `references/checks.md` (every check with its command, the test that makes each rule fail, the metric and the eval.py commands).

Run `python3 eval.py checks brief.md script.md --target-nouns "<Full Name>,<surname>,<Organization>,<their key programmes>" --experience <Q9: experienced, new, top> --authority <caller.authority_level: high, medium>`
and `python3 eval.py duf brief.md script.md`; rewrite until both are clean. Before the first fit pass, copy the draft to
`brief.draft.md` (and the script to `script.draft.md`); after the last, run `python3 eval.py kept brief.draft.md brief.md --draft-script script.draft.md --final-script script.md` (C24: cut wording, never cited facts).
Then run `python3 eval.py battery --latest --depth <depth> --brief brief.md --profile ~/.pcp/profile.yaml`: it reads this
session's own history on Claude Code, Codex, and from the ChatGPT or Claude app export (`python3 eval.py battery conversations.json ...`),
so no host is "unavailable". Fix what it reports: open a cited page you never opened or drop its fact, correct the Run row,
keep the rounds out of the reply; say in the reply what cannot be fixed.
Check the links with `python3 eval.py links brief.md` (S2-8): replace a dead link or drop its fact.

## Render

**Load:** `format/talyx_pdf.py`; `format/layout.json`.

**Config:** `format/layout.json` keys `page_budget.*` -- the renderer reads the page count, the ladder and the 10 pt floor from it.

```
python3 format/talyx_pdf.py --style brief --brief brief.md --script script.md \
    --columns "B3|B4,B5|B6,B7|B8,P1+P2+P3+P4|P5+P6+P7+P8" --classification "INTERNAL | PREPARED FOR YOU | NOT FOR THE PERSON DESCRIBED" \
    --footer "Intelligence Brief · <Full Name>, <Organization> · Prepared for you (internal)" \
    --brief-pages 2 --max-pages 3 --out <dir>/<date>-<slug>-intelligence-brief.pdf
```

The PDF is exactly 3 pages: the brief fills pages 1-2 (a short brief puts the ledger on page 2, never
filler) and the script starts on page 3. Then `python3 eval.py pdf <the PDF> brief.md` must exit 0.

It uses Playwright's Chromium if installed, else the Chrome, Edge or Chromium already on the computer. If it
reports that neither is there, run `python3 format/talyx_pdf.py --setup` once and render again.

Every flag the renderer takes: `--brief`, `--brief-pages`, `--classification`, `--columns`, `--footer`, `--gaps`, `--input`, `--max-pages`, `--out`, `--script`, `--script-after`, `--script-subtitle`, `--setup`, `--style`, `--subtitle`, `--title`.

## Stage 5: Debrief + ratchet

**Load:** `evals/debrief_template.yaml`; `evals/ratchet.json`.

**Config:** `pcp.json` keys `stages.*.rows.*.basis`, `calibration.rules.*.basis` -- improve cites a rule's basis when it proposes a change.

**Input contract** (declared before behaviour):

| Input | Type | Source | Required | Fallback |
|---|---|---|---|---|
| `debrief.yaml` | yaml | user, after the call (60 seconds, 4 fields) | no | skip loop |
| `ratchet.json` | json | evals/ratchet.json | yes | initialise empty |

**Context contract** -- read, in this order: ratchet floors, debrief rows, the pcp.yaml rows the debrief touches. Budget: 800 words. Not read: everything else.

**Rows:**

- **S5-1** A change to pcp.yaml lands only if eval.py ratchet passes: every frozen target's duf_pp >= its floor AND all checks pass. The floor is the best ever seen and only rises.
- **S5-2** Debrief fields: facts_used[claim ids], questions_landed[ids], band_accuracy{dim: hit|miss}, outcome. Nothing else is asked.
- **S5-3** improve proposes row diffs (family weights, question templates, band phrases) as a patch with basis: debrief_id; it never edits SKILL.md and never lands a diff itself.

After the call, `evals/debrief_template.yaml` (four fields). `python3 eval.py improve` proposes row diffs to
`pcp.yaml`; `python3 eval.py ratchet` lands them only if every frozen target holds its floor. The floor is the
best ever seen and only rises.
