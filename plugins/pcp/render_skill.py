#!/usr/bin/env python3
"""render_skill.py -- pcp.yaml -> SKILL.md, commands/pcp.md, the Socratic reference, INVENTORY.md and pcp.json.

The ONLY writer of those files. The Markdown ones carry a header with the registry sha256; eval.py
`concordance` re-renders to memory and diffs, so a hand edit to any of them fails the gate. pcp.json is
pcp.yaml as JSON: the scripts read it at run time, so a user needs no YAML library.

Usage:
  python3 render_skill.py            # write them
  python3 render_skill.py --check    # exit 1 if any differs from a fresh render, or the user-facing text breaks plain words
"""
import argparse
import hashlib
import json
import math
import pathlib
import re
import sys

import yaml

HERE = pathlib.Path(__file__).resolve().parent
REG = HERE / "pcp.yaml"


def load():
    raw = REG.read_bytes()
    return yaml.safe_load(raw), hashlib.sha256(raw).hexdigest()[:12]


def fill(R, text):
    """{deliverable}, {profile}, {script}, {collection} -> their one value in pcp.yaml `names`."""
    return re.sub(r"\{(deliverable|profile|script|collection)\}", lambda m: R["names"][m.group(1)], str(text))


def _rows(R, rows):
    return "\n".join(f"- **{r['id']}** {fill(R, r['text'])}  \n  _Fails when:_ {r['test']}" for r in rows)


def _inputs(inputs):
    lines = ["| Input | Type | Source | Required | Fallback |", "|---|---|---|---|---|"]
    for i in inputs:
        lines.append(f"| `{i['name']}` | {i['type']} | {i['source']} | {'yes' if i['required'] else 'no'} | {i['fallback']} |")
    return "\n".join(lines)


def _context(ctx):
    return (f"**Context contract** -- read, in this order: {', '.join(ctx['order'])}. "
            f"Budget: {ctx['budget_words']} words. Not read: {', '.join(ctx['excluded'])}.")


def description(R):
    """The skill's listing text: user-facing, so it is held to plain words."""
    n = R["names"]
    return (f"Prepare for an upcoming meeting with a named person, company or deal. A few one-time setup\n"
            f"  questions, research from public sources by targeted web search (LinkedIn only as its public search results\n"
            f"  show it, never your browser), plus your own files when you give them, and ONE 3-page PDF: a 2-page\n"
            f"  {n['deliverable']} and a 1-page meeting script, every fact\n"
            f"  cited. Use when the user mentions pre-call prep, meeting prep, call preparation, researching someone\n"
            f"  before a meeting, talking points, or shares an intake list. Do not use for general research unrelated\n"
            f"  to a meeting, or for notes on a meeting that has already happened.")


def render_skill(R, sha):
    n, cal, pb = R["names"], R["calibration"], R["page_budget"]
    qs = {q["id"]: q for q in cal["questions"]}
    q_lines = []
    for q in cal["questions"]:
        opts = " · ".join(f"{i}. {o['label']}" for i, o in enumerate(q["options"], 1)) if q["options"] else "free text"   # labels hold ' / '
        q_lines.append(f"| {q['id']} | {q['header']} | {q['question']} | {opts} | {', '.join(q['sets'].keys())} |")
    calls = " · ".join("+".join(c) + (" (free text)" if any(qs[i].get("free_text") for i in c) else "") for c in cal["calls"])
    fam_lines = [f"| {f['id']} | {f['name']} | {'/'.join(f['depth'])} | {'yes' if f['socmint'] else 'no'} | `{f['query']}` | {f['extract']} |"
                 for f in R["families"]]
    dims = "\n".join(
        f"| {d['id']} | {d['shows']} | {'; '.join(d['signals'])} | {d['meaning']['low']} | {d['meaning']['mid']} | {d['meaning']['high']} |"
        for d in R["rubric"]["dimensions"])
    tiers = R["rubric"]["tiers"]
    table = lambda items: "\n".join(f"| {s['id']} | {fill(R, s['title'])} | {s['words']} | {s['prints']} | {fill(R, s['content'])} |" for s in items)
    beats = "\n".join(f"- **{k}**: {' -> '.join(v)}" for k, v in R["script"]["beats_by_format"].items())
    checks = "\n".join(f"| {c['id']} | {c['name']} | `{c['cmd']}` | {c['passes_when']} |" for c in R["checks"] if "cmd" in c)
    excl = R["exclusions"]

    stages = []
    for s in R["stages"]:
        block = [f"## Stage {s['id'][1]}: {fill(R, s['name'])}", "", "**Input contract** (declared before behaviour):", "",
                 _inputs(s["inputs"]), "", _context(s["context"]), ""]
        if s.get("outputs"):
            block += ["**Outputs:** " + "; ".join(f"`{o['name']}` ({', '.join(o.get('fields', [])) or o.get('note', '')})" for o in s["outputs"]), ""]
        block += ["**Rows:**", "", _rows(R, s["rows"]), ""]
        stages.append("\n".join(block))

    # frontmatter must be the first bytes of the file or no host loads the skill -- the header goes after it
    return f"""---
name: pre-call-prep
description: >
  {description(R)}
---
{R['render_header'].format(sha=sha)}

# Pre-call prep (v{R['registry_version']})

Stages, dependency-ordered: **setup once -> intake -> {n['collection'].lower()} -> {n['profile'].lower()} -> {n['deliverable']} -> debrief.**
Every stage declares its inputs before its behaviour, reads only its listed context, and follows rows
that each carry a falsification test. Every fact traces to a source. Nothing is invented.
The deliverable is one 3-page PDF, the {n['deliverable']}. Nothing else is emitted.

**No shell or code tool (plain chat)?** Run the same stages anyway; never stop or refuse for lack of tools.
Research with the host's own web search and fetch tools. Keep claims, coverage and the behavioral read as the
records below, in your working notes, not in the reply: say one short status line, then nothing until a question or
the brief itself (S2-10). Apply the checks yourself. Then deliver the full {n['deliverable']} in chat
exactly as S4-10 says (label, page markers, every block, the ledger, the {n['script']}). Profile answers
given in the message stand in for the saved setup file.

## How PCP thinks (never in the output)

{chr(10).join('- ' + fill(R, c) for c in R['concepts'])}

**Sources never cited:** {', '.join(R['source_quality']['exclude'])}. **Weak (never C1/C2, never the only support on page 1):** {', '.join(R['source_quality']['weak'])}.

**Plain words.** {R['plain_words']['rule']} Never write a word banned: {', '.join(R['plain_words']['banned'])}, or an internal id
(C1-C4, F1-F12, row ids). Allowed only inside these phrases: {', '.join(R['plain_words']['allowed'])}.
Use "source types", not families; "the person you're meeting", not target. Call the deliverable the {n['deliverable']}, nothing else.

## Stage 0: Setup (once)

If `{cal['profile_path']}` is missing or invalid, or `{cal['reask_flag']}` is passed, ask these questions with
`AskUserQuestion` -- {calls}, first option recommended -- (the host's native question tool: the structured question tool in
ChatGPT, Codex and Grok), asking only those the saved profile has no answer for. A label such as 'Sales / BD' is one option.
{R['socratic']['ask_user']['how']['wait']} Only if the host has no question tool, or the tool returns no answer:
{R['socratic']['ask_user']['how']['fallback']} Then write the profile
(`pcp_profile_format: 1`, answers under `profiles: <name>: answers: Qn: {{value, defaulted}}`, plus `context`
and `linkedin` when set) and continue.

| # | Chip | Question | Options | Sets |
|---|---|---|---|---|
{chr(10).join(q_lines)}

{_rows(R, cal['rules'])}

{chr(10).join(stages)}
## Asking questions

When a question is needed -- of the user, or for the room -- read `references/socratic-questions.md` first.
{R['socratic']['ask_user']['how']['tool']} {R['socratic']['ask_user']['how']['wait']}

## Records (C23)

Keep three records while you work, in these files beside the brief (a host with no files keeps the same fields in its
working notes). Compose the brief from them alone (S4-12), and run `python3 eval.py records <folder> --depth <depth> --brief brief.md`
before you say the run is done.

| Record | File | Fields |
|---|---|---|
{chr(10).join(f"| {k} | `{v['file']}` | {', '.join(v['fields'])}{' -- ' + v['note'] if v.get('note') else ''} |" for k, v in R['records'].items())}

## Source families

Enabled per profile: `depth` filters the column, `target.kind` filters `kinds`, `socmint.scope` filters F6
to `{', '.join(R['research']['socmint_networks']['professional'])}` (professional) or the wider list (social) or none.
FULL status needs >= 1 C1/C2 claim in {R['research']['full_threshold']} families (by depth).

| Id | Family | Depth | SOCMINT | Query template | Extract |
|---|---|---|---|---|---|
{chr(10).join(fam_lines)}

Placeholders in the query templates and rounds: {'; '.join(f"`{{{k}}}` = {v}" for k, v in R['placeholders'].items())}.

Intake columns (assets/intake-template.csv) and what each sets:

| Column | Sets |
|---|---|
{chr(10).join(f"| {k} | {v} |" for k, v in R['intake_columns'].items())}

Registers by domain: {'; '.join(f"{k}: " + ', '.join(r['name'] for r in v) for k, v in R['registers'].items() if v) or 'none'}.

**Exclusions (dropped before the writer, counted in coverage):** {', '.join(excl['base'])}.
By jurisdiction: {'; '.join(f"{k}: {', '.join(v)}" for k, v in excl['by_jurisdiction'].items() if v)}.

{osint_section(R)}
The round plan with its reasons: `references/osint-search.md`.

**LinkedIn status (S2-7), in B4's last line and the Coverage row:** {' or '.join(f"`LinkedIn: {r}`" for r in R['linkedin']['read'].values())}, or
`LinkedIn: {R['linkedin']['not_read']}: <reason>` with one of these reasons, word for word: {'; '.join(R['linkedin']['reasons'])}.

## {n['profile']} (six dimensions)

Tiers: high = {tiers['high']['min_observations']} observations, {tiers['high']['corroborated_across_sources']} sources, a direct quote or action;
medium = {tiers['medium']['min_observations']} observations, {tiers['medium']['corroborated_across_sources']} source; low = role-inferred only (renders as "No read").

| Dimension | Row label (B6) | Signals | Low means | Mid means | High means |
|---|---|---|---|---|---|
{dims}

What they may want (depth deep only): <= {R['rubric']['ach']['max_hypotheses']} hypotheses about what they want from this meeting, each with the claim that would disprove it.

## The PDF: pages 1-2, the {n['deliverable']}

`brief.md` starts with `# Full Name`, then the identity line (`**Organization** | Role, since year | City, if public`),
then the meta line (`Meeting: ... | Prepared for: ... | Depth: ... | Sources: <types> of 12 source types, <the ledger's fact count> cited | Status FULL or LIMITED | Prepared Mon D, YYYY`).
Then one `## Bn Title` per block, in order. Word budgets are the page budget; the renderer fails, never spills, past {pb['total_pages']} pages.

| Id | Block | Words | Prints when | Content |
|---|---|---|---|---|
{table(R['brief']['sections'])}

Domain vocabulary: {'; '.join(f"{k}: {', '.join(v)}" for k, v in R['brief']['vocab_by_domain'].items() if v)}.

## The PDF: page 3, the {fill(R, R['script']['title'])}

`script.md` starts with `# {fill(R, R['script']['title'])}`, then one line: *{R['script']['subtitle']} · Full Name, Organization · Prepared Mon D, YYYY*.
Then one `## Pn Title` per section, in order; a section whose Prints when is not met is left out, not blank.

Beats by meeting format:
{beats}

| Id | Section | Words | Prints when | Content |
|---|---|---|---|---|
{table(R['script']['blocks'])}

{R['forms']['P8']['never']['label']} {'; '.join(f'"{p}"' for p in R['guardrails']['never_say'])}.
Forbidden claims by domain (P8 quotes the saved domain's): {'; '.join(f"{k}: " + ', '.join(f'"{x}"' for x in v) for k, v in R['guardrails']['forbidden_claims_by_domain'].items() if v)}.

## fields.json: what you fill (S4-13)

You never write brief.md or script.md. Fill `fields.json` -- the keys below, per block; text cites a claim as `[c<id>]` (claims.jsonl),
the assembler numbers the ledger -- then run `python3 eval.py assemble <folder>`. A key marked optional may be left out; `missing` prints
as shown. Labels print exactly as the forms table in pcp.yaml says.

| Block | Form | Keys |
|---|---|---|
{forms_table(R)}

## Checks (all pass before render)

Run `python3 eval.py checks brief.md script.md --target-nouns "<Full Name>,<surname>,<Organization>,<their key programmes>" --experience <{qs['Q9']['id']}: {', '.join(o['value'] for o in qs['Q9']['options'])}> --authority <caller.authority_level: high, medium>`
and `python3 eval.py duf brief.md script.md`; rewrite until both are clean. Before the first fit pass, copy the draft to
`brief.draft.md` (and the script to `script.draft.md`); after the last, run `python3 eval.py kept brief.draft.md brief.md --draft-script script.draft.md --final-script script.md` (C24: cut wording, never cited facts).
Then run `python3 eval.py battery --latest --depth <depth> --brief brief.md --profile ~/.pcp/profile.yaml`: it reads this
session's own history on Claude Code, Codex, and from the ChatGPT or Claude app export (`python3 eval.py battery conversations.json ...`),
so no host is "unavailable". Fix what it reports: open a cited page you never opened or drop its fact, correct the Run row,
keep the rounds out of the reply; say in the reply what cannot be fixed.
Check the links with `python3 eval.py links brief.md` (S2-8): replace a dead link or drop its fact.

| Id | Check | Command | Passes when |
|---|---|---|---|
{checks}

## Render

```
python3 format/talyx_pdf.py --style brief --brief brief.md --script script.md \\
    --columns "{pb['columns']}" --classification "{n['classification']}" \\
    --footer "{n['deliverable']} · <Full Name>, <Organization> · Prepared for you (internal)" \\
    --brief-pages {pb['brief_pages']} --max-pages {pb['total_pages']} --out <dir>/<date>-<slug>-intelligence-brief.pdf
```

The PDF is exactly {pb['total_pages']} pages: the brief fills pages 1-{pb['brief_pages']} (a short brief puts the ledger on page {pb['brief_pages']}, never
filler) and the script starts on page {pb['brief_pages'] + 1}. Then `python3 eval.py pdf <the PDF> brief.md` must exit 0.

It uses Playwright's Chromium if installed, else the Chrome, Edge or Chromium already on the computer. If it
reports that neither is there, run `python3 format/talyx_pdf.py --setup` once and render again.

## Debrief and ratchet

After the call, `evals/debrief_template.yaml` (four fields). `python3 eval.py improve` proposes row diffs to
`pcp.yaml`; `python3 eval.py ratchet` lands them only if every frozen target holds its floor. The floor is the
best ever seen and only rises.

## About

Made by Talyx AI, https://talyx.ai. Free to use under the licence in the plug-in's `LICENSE` file.
"""


def battery_rounds(R, depth):
    """S2-9: the rounds a depth runs -- every round with a source type the depth enables (eval.py C21 reads the same)."""
    on = {f["id"] for f in R["families"] if depth in f["depth"]}
    return [r["round"] for r in R["osint"]["rounds"] if on & set(r["types"])]


def forms_table(R):
    """The forms table as the model reads it: per block, the keys it fills and the labels they print under."""
    F, rows = R["forms"], []
    keyof = lambda f: f"`{f['key']}`" + (f" ({f['label'].rstrip(':.')})" if f.get("label") else "") + (" optional" if f.get("optional") else "") + (f" else '{f['missing']}'" if f.get("missing") else "")
    for b in R["brief"]["sections"] + R["script"]["blocks"]:
        s = F[b["id"]]
        if s["form"] in ("bullets", "labels_para"):
            ks = ", ".join(keyof(f) for f in s["fields"])
        elif s["form"] == "questions":
            ks = f"`b2`: {s['count'][0]} to {s['count'][1]} of " + ", ".join(f"`{f['key']}`" for f in s["item"])
        elif s["form"] == "quotes":
            ks = "`quotes`: list of `label`, `quote`, `cite`; or `themes`; the LinkedIn line is computed"
        elif s["form"] == "table":
            ks = f"`b5`: {len(s['rows'])} of `observable`, `action` (" + ", ".join(r['key'] for r in s['rows']) + ")"
        elif s["form"] == "profile_table":
            ks = "`b6`: one observation per rubric dimension id (" + ", ".join(d["id"] for d in R["rubric"]["dimensions"]) + "); the moves and the tier come from read.json"
        elif s["form"] == "case_against":
            ks = f"`against`: up to {s['max']} of `against`, `reverses_if`; `{s['confirm']['key']}`; deep: `hypotheses` of `hypothesis`, `test`"
        elif s["form"] == "angle":
            ks = ", ".join(keyof(f) + (f" + `{f['join']['key']}`" if f.get("join") else "") for sec in s["sections"] for f in sec["fields"])
        elif s["form"] == "ledger":
            ks = "computed from claims.jsonl, coverage.json and `still_open` (up to " + str(s["still_open_max"]) + " of `label`, `question`)"
        elif s["form"] == "question_order":
            ks = f"`beats`: list; `order`: B2 question numbers for " + ", ".join(x.lower() for x in s["order"])
        elif s["form"] == "objections":
            ks = f"`p3`: {s['count']} of `objection`, `answer`"
        elif s["form"] == "repeat":
            ks = f"`{s['key']}`: {s['count'][0]} to {s['count'][1]} moves"
        elif s["form"] == "guardrails":
            ks = "`rule`; the never-say list and the domain's forbidden claims are computed"
        else:
            ks = f"`{s['key']}`"
        rows.append(f"| {b['id']} | {s['form']} | {ks} |")
    t = R["forms"]["masthead"]
    rows.append("| masthead | -- | `target` (`name`, `org`, `role_since`, `city` only when a source confirms it), `meeting`, `prepared` (Mon D, YYYY) |")
    return "\n".join(rows)


def osint_section(R):
    """S2-7 / AID-63: the search rounds, from pcp.yaml osint -- in SKILL.md (so every host has them) and in the reference."""
    o, b = R["osint"], R["osint"]["battery"]
    floor = []
    for d, per in b["queries_per_round"].items():
        rs = battery_rounds(R, d)
        floor.append(f"| {d} | {', '.join(map(str, rs))} | {per} | {per * len(rs)} | {math.ceil(round(per * len(rs) * b['operator_share'], 6))} |")
    rounds = "\n".join(f"| {r['round']} | {r['name']} | {', '.join(r['types'])} | {r['goal']} | "
                       + "<br>".join(f"`{q}`" for q in r["queries"]) + f" | {fill(R, r['next'])} |" for r in o["rounds"])
    return f"""## Search rounds (S2-7)

{o['rule']}

| Depth | Rounds | Queries per round, at least | Searches, at least | With an operator or a domain filter, at least |
|---|---|---|---|---|
{chr(10).join(floor)}

**Operators.** {o['operators']}

{chr(10).join(f"**{h['host']}** (checked: {h['checked']}):" + chr(10) + chr(10).join('- ' + r for r in h['rules']) + chr(10) for h in o['hosts'])}
**Never.** {o['never']}

**Identity lock.** {o['identity_lock']} Example: {o['example']}

**Grading.**
{chr(10).join('- ' + g for g in o['grading'])}

| Round | Name | Source types | Goal | Queries (fill the braces; send at least the depth's count) | Then |
|---|---|---|---|---|---|
{rounds}
"""


def render_osint(R, sha):
    li = R["linkedin"]
    return f"""{R['render_header'].format(sha=sha)}

# Search rounds: the record by targeted web search

How PCP researches the person you're meeting: five rounds of targeted web searches, each refined from the
last, and LinkedIn only as its public search results show it. PCP never signs in, never opens LinkedIn and
never drives a browser.

**Why.** LinkedIn's User Agreement bars bots and automated tools that copy profiles, and lets LinkedIn restrict the
account that ran them, so reading a profile in your own signed-in browser put your account at risk. A search result
never touches LinkedIn: the search engine read the page, and PCP reads only what the result shows.

{osint_section(R).split(chr(10), 2)[2]}
## LinkedIn status

Every run says, in B4's last line and in the Coverage row: {' or '.join(f"`LinkedIn: {r}`" for r in li['read'].values())}, or
`LinkedIn: {li['not_read']}: <reason>` with one of: {'; '.join(li['reasons'])}. Check C16 holds the two lines to each other and to the ledger.

**A saved profile (optional).** When you give PCP the person's LinkedIn profile saved as a PDF (on their
profile: More > Save to PDF) or as copied text, it is read as your file: its facts are tagged Yours and cited by
the file name, and the status reads `LinkedIn: {li['read']['file']}`. PCP never waits for one. This path is under review.
"""


def render_socratic(R, sha):
    s = R["socratic"]
    trig = "\n".join(f"| {t['when']} | {t['ask']} |" for t in s["ask_user"]["triggers"])
    kinds = "\n".join(f"| {k['kind']} | {k['use']} | {k['example']} |" for k in s["room"]["kinds"])
    return f"""{R['render_header'].format(sha=sha)}

# Socratic questions

Two uses: questions PCP asks **you** when it needs something only you know, and questions it writes for
**the room** wherever the record could not answer.

## Asking the user

{s['ask_user']['rule']}

| When | Ask |
|---|---|
{trig}

## Questions for the room

{fill(R, s['room']['rule'])} Each question starts with {', '.join(s['room']['question_starts'][:-1])} or {s['room']['question_starts'][-1]}, and ends with a question mark.

| Kind | Use when | Example |
|---|---|---|
{kinds}
"""


def render_command(R, sha):
    n, pb = R["names"], R["page_budget"]
    calls_txt = f"{len(R['calibration']['calls'])} calls, first option recommended"
    # frontmatter must be the first bytes of the file or the host drops description and argument-hint -- header after it;
    # name: Cursor's plugin validator requires it on every command file (cursor/plugin-template, Oct 16)
    return f"""---
name: pcp
description: Prepare for a meeting. Sets up once, researches the person, and writes ONE {pb['total_pages']}-page PDF -- the {n['deliverable']} and a meeting script.
argument-hint: "[intake.csv | \\"Full Name, Organisation\\"] [--recalibrate] [--profile <name>] [--context <file>] [--out <dir>]"
---
{R['render_header'].format(sha=sha)}

# /pcp: pre-call prep

Input from the user: `$ARGUMENTS`

First load the `pre-call-prep` skill in this plug-in (Skill tool, or read `skills/pre-call-prep/SKILL.md`) -- the block schema, titles and budgets live there, not here. Never write a brief without it. Then follow it exactly, in stage order:

0. **Setup** -- ask the questions with `AskUserQuestion` ({calls_txt}), only those `{R['calibration']['profile_path']}` has no answer for (all with `--recalibrate`), a typed list only where the host has no question tool; read files given with `--context`.
1. **Intake** -- resolve `$ARGUMENTS` (CSV path, `"Name, Org"`, or ask). Never start without a full name and an organisation. Confirm the meeting objective: say it back in the one status line, and ask only as `references/socratic-questions.md` says.
2. **{n['collection']}** -- run the enabled source types in the search rounds of `references/osint-search.md` (LinkedIn only as its search results show it; never a browser); write `claims.jsonl` and the coverage ledger. Drop excluded claims before writing.
3. **{n['profile']}** -- read six dimensions from claim ids only; set the evidence tier.
4. **{n['deliverable']}** -- fill `fields.json` (SKILL.md lists its keys) and run `python3 eval.py assemble <folder>` -- it builds `brief.md` (B1-B10) and `script.md` (P1-P9) from the schema, never write them yourself; run `python3 eval.py checks brief.md script.md --target-nouns \"<name>,<org>\" --experience <Q9> --authority <caller.authority_level>` and `python3 eval.py duf brief.md script.md`; rewrite until clean; render with `format/talyx_pdf.py --style brief --brief-pages {pb['brief_pages']} --max-pages {pb['total_pages']}` and check it with `python3 eval.py pdf <the PDF> brief.md`. Deliver the PDF path and the run line (date · depth · status · facts · searches, from the ledger's Run row). Delete `brief.md`/`script.md` after a clean render.
5. **After the call** -- offer the four-field template in `evals/debrief_template.yaml`; never ask for more.

Say what was NOT found before what was.

**No shell or code tool (plain chat)?** Do not stop. Skip only the script steps (file writes, `eval.py`, the PDF
render): research with the host's web search, keep claims in the conversation, apply the checks yourself, and
deliver the full Intelligence Brief in chat in the S4-10 format -- first line the in-chat label, then
`--- Page 1 ---`, `--- Page 2 ---`, `--- Page 3 ---` with `# Meeting script`. Thin evidence still gets the full
3 parts with what was not found stated in each.
"""


def _status(R, b):
    """A block's inventory status from its own `prints:`."""
    return ("always", "") if b["prints"] == "always" else ("conditional", b["prints"])


def render_inventory(R, sha):
    fam = {f["id"]: f["name"] for f in R["families"]}
    src = lambda ss: ", ".join(f"{s} {fam[s]}" if s in fam else s for s in ss)
    reg = {b["id"]: (b, "1-2") for b in R["brief"]["sections"]} | {b["id"]: (b, "3") for b in R["script"]["blocks"]}
    rows = []
    for e in R["inventory"]["blocks"]:
        b, page = reg[e["id"]]
        st, when = _status(R, b)
        rows.append(f"| {e['id']} | {fill(R, b['title'])} | {page} | {e['produces']} | {src(e['sources'])} | {st} | {when or '--'} | {e.get('check', '--')} |")
    parts = [f"| {p['id']} | {p['part']} | {p['produces']} | {src(p['sources'])} | {p['status']} | {p.get('prints', '--')} | {p.get('check', '--')} |"
             for p in R["inventory"]["parts"]]
    count = lambda s: sum(1 for e in R["inventory"]["blocks"] if _status(R, reg[e["id"]][0])[0] == s) + \
        sum(1 for p in R["inventory"]["parts"] if p["status"] == s)
    return f"""{R['render_header'].format(sha=sha)}

# Inventory: what the {R['names']['deliverable']} prints (v{R['registry_version']})

Every part a user sees, what it produces, where its facts come from, and one status: **always**,
**conditional** (printed only as its Prints when says, enforced by the named check) or **removed**. Every part
has a decided status. Totals: {count('always')} always, {count('conditional')} conditional, {count('removed')} removed.

## Blocks ({len(rows)}, one per registry block)

| Id | Block | Page | Produces | Comes from | Status | Prints when | Enforced by |
|---|---|---|---|---|---|---|---|
{chr(10).join(rows)}

## Parts within and around the blocks

| Id | Part | Produces | Comes from | Status | Prints when | Enforced by |
|---|---|---|---|---|---|---|
{chr(10).join(parts)}
"""


def inventory_problems(R, inventory_md, skill_md):
    """Every registry block once; every conditional part with its Prints when and a real check; nothing unknown;
    a removed part named nowhere in SKILL.md."""
    out = []
    need = [b["id"] for b in R["brief"]["sections"]] + [b["id"] for b in R["script"]["blocks"]]
    have = [e["id"] for e in R["inventory"]["blocks"]]
    if sorted(have) != sorted(need) or len(have) != len(set(have)):
        out.append(f"inventory.blocks {have} must list each registry block once: {need}")
    checks = {c["id"] for c in R["checks"] if "id" in c}
    blocks = {b["id"]: b for b in R["brief"]["sections"] + R["script"]["blocks"]}
    for e in R["inventory"]["blocks"]:
        if e["id"] in blocks and _status(R, blocks[e["id"]])[0] == "conditional" and e.get("check") not in checks:
            out.append(f"inventory {e['id']}: conditional ({blocks[e['id']]['prints']}) with no check that enforces it")
    for p in R["inventory"]["parts"]:
        if p["status"] not in ("always", "conditional", "removed"):
            out.append(f"inventory {p['id']}: status {p['status']} -- always, conditional or removed")
        if p["status"] == "conditional" and not (p.get("prints") and p.get("check") in checks):
            out.append(f"inventory {p['id']}: conditional needs prints: and a check: that exists")
        if p.get("check") and p["check"] not in checks:
            out.append(f"inventory {p['id']}: check {p['check']} does not exist")
        if p["status"] == "removed" and p["part"].lower() in skill_md.lower():
            out.append(f"inventory {p['id']}: removed, yet SKILL.md names '{p['part']}'")
    if re.search(r"\b(?:unknown|TBD)\b", inventory_md, re.I):
        out.append("INVENTORY.md says unknown or TBD: every part is always, conditional or removed")
    return out


def plain_violations(R, texts):
    """Banned words in user-facing text: the names, the setup questions and the skill's listing text.
    A banned word inside a plain_words.allowed phrase (asset manager) is not the banned word."""
    pw = R["plain_words"]
    words = re.compile(r"\b(?:" + "|".join(re.escape(w) for w in pw["banned"]) + r")\b", re.I)
    allowed = re.compile(r"\b(?:" + "|".join(re.escape(w) for w in pw.get("allowed") or ["\x00"]) + r")\b", re.I)
    texts = [allowed.sub(" ", t) for t in texts]
    return sorted({m.group(0) for t in texts for pat in (words, re.compile(pw["codes"])) for m in pat.finditer(t)})


def internal_refs(R, texts):
    """Consumer-facing copy carries no internal notes (plain_words.internal): no team names, meeting notes, ticket or
    run ids, no '(Oct 14)' provenance. Those stay in pcp.yaml's basis fields and comments."""
    pat = re.compile(R["plain_words"]["internal"])
    return sorted({m.group(0) for t in texts for m in pat.finditer(t)})


def user_facing(R):
    out = [description(R), *R["names"].values()]
    for q in R["calibration"]["questions"]:
        out += [q["header"], q["question"], *[o["label"] + " " + o["description"] for o in q["options"]]]
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    a = ap.parse_args()
    R, sha = load()
    targets = {HERE / "skills/pre-call-prep/SKILL.md": render_skill(R, sha),
               HERE / "skills/pre-call-prep/references/socratic-questions.md": render_socratic(R, sha),
               HERE / "skills/pre-call-prep/references/osint-search.md": render_osint(R, sha),
               HERE / "commands/pcp.md": render_command(R, sha),
               HERE / "INVENTORY.md": render_inventory(R, sha),
               HERE / "pcp.json": json.dumps(R, ensure_ascii=False, separators=(",", ":"), default=str) + "\n",
               HERE / "format/layout.json": json.dumps({k: R[k] for k in ("page_budget", "layout", "balance", "colors")}, ensure_ascii=False, indent=1, default=str) + "\n"}
    if sorted(str(p.relative_to(HERE)) for p in targets) != sorted(R["generated_files"]):
        print("GENERATED FILES FAIL -- pcp.yaml generated_files differs from what this writes:",
              sorted(str(p.relative_to(HERE)) for p in targets))
        sys.exit(1)
    bad_words = plain_violations(R, user_facing(R))
    if bad_words:
        print("PLAIN WORDS FAIL -- user-facing text in pcp.yaml uses:", ", ".join(bad_words))
        sys.exit(1)
    leaked = internal_refs(R, [txt for path, txt in targets.items() if path.suffix == ".md"])
    if leaked:
        print("INTERNAL FAIL -- consumer-facing files carry internal notes:", ", ".join(leaked))
        sys.exit(1)
    inv = inventory_problems(R, targets[HERE / "INVENTORY.md"], targets[HERE / "skills/pre-call-prep/SKILL.md"])
    if inv:
        print("INVENTORY FAIL --", *inv, sep="\n  ")
        sys.exit(1)
    if a.check:
        bad = [str(p.relative_to(HERE)) for p, txt in targets.items() if not p.exists() or p.read_text() != txt]
        if bad:
            print("CONCORDANCE FAIL -- differs from pcp.yaml render:", ", ".join(bad))
            sys.exit(1)
        print("concordance OK", sha)
        return
    for p, txt in targets.items():
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(txt)
        print("wrote", p.relative_to(HERE), len(txt), "chars")


if __name__ == "__main__":
    main()
