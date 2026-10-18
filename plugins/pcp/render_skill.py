#!/usr/bin/env python3
"""render_skill.py -- pcp.yaml -> SKILL.md (the procedure), the references each step loads, commands/pcp.md, INVENTORY.md, pcp.json and format/layout.json.

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
    """The rows as rules (the chat knowledge file reads them at run time); each row's test is the developers', in skill.dev_file."""
    return "\n".join(f"- **{r['id']}** {fill(R, r['text'])}" for r in rows)


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


def _ctx(R):
    """The values the section texts below fill in: names, the setup tables, the families table, the rubric, the checks."""
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
    return n, cal, pb, qs, q_lines, calls, fam_lines, dims, tiers, table, beats, checks, excl


def stage_block(R, s):
    """A stage as the full skill prints it: its input contract, context, outputs and every row with its test."""
    block = [f"## Stage {s['id'][1]}: {fill(R, s['name'])}", "", "**Input contract** (declared before behaviour):", "",
             _inputs(s["inputs"]), "", _context(s["context"]), ""]
    if s.get("outputs"):
        block += ["**Outputs:** " + "; ".join(f"`{o['name']}` ({', '.join(o.get('fields', [])) or o.get('note', '')})" for o in s["outputs"]), ""]
    block += ["**Rows:**", "", _rows(R, s["rows"]), ""]
    return "\n".join(block)


def t_chat(R):
    """The plain-chat paragraph: what a host with no shell or code tool does."""
    n = R["names"]
    return f"""**No shell or code tool (plain chat)?** Run the same stages anyway; never stop or refuse for lack of tools.
Research with the host's own web search and fetch tools. Keep claims, coverage and the behavioral read as the
records below, in your working notes, and keep the reply quiet as S2-10 says. Apply the checks yourself. Then deliver the full {n['deliverable']} in chat
exactly as S4-10 says (label, page markers, every block, the ledger, the {n['script']}). Profile answers
given in the message stand in for the saved setup file.

"""


def p_head(R, sha):
    """Frontmatter and the opening paragraphs (the frontmatter must be the first bytes of the file or no host loads the skill)."""
    n = R["names"]
    return f"""---
name: pre-call-prep
description: >
  {description(R)}
---
{R['render_header'].format(sha=sha)}

# Pre-call prep (v{R['registry_version']})

Stages, dependency-ordered: **setup once -> intake -> {n['collection'].lower()} -> {n['profile'].lower()} -> {n['deliverable']} -> debrief.**
Every stage declares its inputs before its behaviour, reads only its listed context, and follows its rows.
Every fact traces to a public source, or to the user's own notes and answers, tagged Yours. Nothing is invented.
The deliverable is one 3-page PDF, the {n['deliverable']}. Nothing else is emitted.

{t_chat(R)}"""


def t_concepts(R):
    """How PCP thinks."""
    return f"""## How PCP thinks (never in the output)

{chr(10).join('- ' + fill(R, c) for c in R['concepts'])}

"""


def t_source_lists(R):
    """The domains never cited and the weak ones."""
    return f"""**Sources never cited:** {', '.join(R['source_quality']['exclude'])}. **Weak (never C1/C2, never the only support on page 1):** {', '.join(R['source_quality']['weak'])}.

"""


def t_plain_words(R):
    """The plain-words rule, its banned and allowed lists."""
    n = R["names"]
    return f"""**Plain words.** {R['plain_words']['rule']} Never write a word banned: {', '.join(R['plain_words']['banned'])}, or an internal id
(C1-C4, F1-F12, row ids). Allowed only inside these phrases: {', '.join(R['plain_words']['allowed'])}.
Use "source types", not families; "the person you're meeting", not target. Call the deliverable the {n['deliverable']}, nothing else.
The one exception is the setup's own wording, kept on purpose, word for word: {'; '.join(f"'{x}'" for x in R['plain_words']['exempt'])}.

"""


def p_concepts(R):
    """How PCP thinks, the sources never cited and the plain words."""
    return t_concepts(R) + t_source_lists(R) + t_plain_words(R)


def p_setup_ask(R):
    """Stage 0: how the setup questions are asked."""
    n, cal, pb, qs, q_lines, calls, fam_lines, dims, tiers, table, beats, checks, excl = _ctx(R)
    return f"""## Stage 0: Setup (once)

If `{cal['profile_path']}` is missing or invalid, or `{cal['reask_flag']}` is passed, ask these questions with
`AskUserQuestion` (the host's native question tool) in three calls -- {calls}, first option recommended -- asking only those the
saved profile has no answer for. A label such as 'Sales / BD' is one option. Each call has its own skip line right before it, and
nothing else runs until the answer (CAL-5; how to ask: `{R['skill']['files']['setup']['path']}`). Then write the profile
(`pcp_profile_format: 1`, answers under `profiles: <name>: answers: Qn: {{value, defaulted}}`, plus `context`
and `linkedin` when set) and continue.

"""


def p_setup_table(R):
    """The setup questions table."""
    n, cal, pb, qs, q_lines, calls, fam_lines, dims, tiers, table, beats, checks, excl = _ctx(R)
    return f"""| # | Chip | Question | Options | Sets |
|---|---|---|---|---|
{chr(10).join(q_lines)}

"""


def p_setup_rules(R):
    """The calibration rows with their tests."""
    n, cal, pb, qs, q_lines, calls, fam_lines, dims, tiers, table, beats, checks, excl = _ctx(R)
    return f"""{_rows(R, cal['rules'])}

"""


def p_asking(R):
    """Asking questions."""
    n, cal, pb, qs, q_lines, calls, fam_lines, dims, tiers, table, beats, checks, excl = _ctx(R)
    return f"""## Asking questions

When a question is needed -- of the user, or for the room -- read `references/socratic-questions.md` first.
{R['socratic']['ask_user']['how']['tool']} {R['socratic']['ask_user']['how']['wait']}
{R['socratic']['ask_user']['how']['fallback']}

"""


def p_records(R):
    """The three records."""
    n, cal, pb, qs, q_lines, calls, fam_lines, dims, tiers, table, beats, checks, excl = _ctx(R)
    return f"""## Records (C23)

Keep three records while you work, in these files beside the brief (a host with no files keeps the same fields in its
working notes). Compose the brief from them alone (S4-12), and run `python3 eval.py records <folder> --depth <depth> --brief brief.md`
before you say the run is done.

| Record | File | Fields |
|---|---|---|
{chr(10).join(f"| {k} | `{v['file']}` | {', '.join(v['fields'])}{' -- ' + v['note'] if v.get('note') else ''} |" for k, v in R['records'].items())}

"""


def t_families(R):
    """The source types table and the placeholders their queries fill."""
    n, cal, pb, qs, q_lines, calls, fam_lines, dims, tiers, table, beats, checks, excl = _ctx(R)
    return f"""## Source families

Enabled per profile: `depth` filters the column, `target.kind` filters `kinds`, `socmint.scope` filters F6
to `{', '.join(R['research']['socmint_networks']['professional'])}` (professional) or the wider list (social) or none.
FULL status needs >= 1 C1/C2 claim in {R['research']['full_threshold']} families (by depth).

| Id | Family | Depth | SOCMINT | Query template | Extract |
|---|---|---|---|---|---|
{chr(10).join(fam_lines)}

Placeholders in the query templates and rounds: {'; '.join(f"`{{{k}}}` = {v}" for k, v in R['placeholders'].items())}.

"""


def t_intake_columns(R):
    """The intake CSV's columns and what each sets."""
    return f"""Intake columns (assets/intake-template.csv) and what each sets:

| Column | Sets |
|---|---|
{chr(10).join(f"| {k} | {v} |" for k, v in R['intake_columns'].items())}

"""


def t_registers(R):
    """Registers by domain and the exclusions."""
    excl = R["exclusions"]
    return f"""Registers by domain: {'; '.join(f"{k}: " + ', '.join(r['name'] for r in v) for k, v in R['registers'].items() if v) or 'none'}.

**Exclusions (dropped before the writer, counted in coverage):** {', '.join(excl['base'])}.
By jurisdiction: {'; '.join(f"{k}: {', '.join(v)}" for k, v in excl['by_jurisdiction'].items() if v)}.

"""


def p_sources(R):
    """Source types, placeholders, intake columns, registers, exclusions."""
    return t_families(R) + t_intake_columns(R) + t_registers(R)


def t_osint(R):
    """The search rounds, from the registry."""
    return f"""{osint_section(R)}
The round plan with its reasons: `references/osint-search.md`.

"""


def t_linkedin(R):
    """The LinkedIn status lines."""
    return f"""**LinkedIn status (S2-7), in B4's last line and the Coverage row:** {' or '.join(f"`LinkedIn: {r}`" for r in R['linkedin']['read'].values())}, or
`LinkedIn: {R['linkedin']['not_read']}: <reason>` with one of these reasons, word for word: {'; '.join(R['linkedin']['reasons'])}.

"""


def p_rounds(R):
    """The search rounds and the LinkedIn status lines."""
    return t_osint(R) + t_linkedin(R)


def p_profile(R):
    """The behavioral profile: dimensions and tiers."""
    n, cal, pb, qs, q_lines, calls, fam_lines, dims, tiers, table, beats, checks, excl = _ctx(R)
    return f"""## {n['profile']} (six dimensions)

Tiers: high = {tiers['high']['min_observations']} observations, {tiers['high']['corroborated_across_sources']} sources, a direct quote or action;
medium = {tiers['medium']['min_observations']} observations, {tiers['medium']['corroborated_across_sources']} source; low = role-inferred only (renders as "No read").

| Dimension | Row label (B6) | Signals | Low means | Mid means | High means |
|---|---|---|---|---|---|
{dims}

What they may want (depth deep only): <= {R['rubric']['ach']['max_hypotheses']} hypotheses about what they want from this meeting, each with the claim that would disprove it.

"""


def p_brief(R):
    """The brief blocks."""
    n, cal, pb, qs, q_lines, calls, fam_lines, dims, tiers, table, beats, checks, excl = _ctx(R)
    return f"""## The PDF: pages 1-2, the {n['deliverable']}

`brief.md` starts with `# Full Name`, then the identity line (`**Organization** | Role, since year | City, if public`),
then the meta line (`Meeting: ... | Prepared for: ... | Depth: ... | Sources: <types> of 12 source types, <the ledger's fact count> cited | Status FULL or LIMITED | Prepared Mon D, YYYY`).
Then one `## Bn Title` per block, in order. Word budgets are the page budget; the renderer fails, never spills, past {pb['total_pages']} pages.

| Id | Block | Words | Prints when | Content |
|---|---|---|---|---|
{table(R['brief']['sections'])}

Domain vocabulary: {'; '.join(f"{k}: {', '.join(v)}" for k, v in R['brief']['vocab_by_domain'].items() if v)}.

"""


def p_script(R):
    """The meeting script blocks."""
    n, cal, pb, qs, q_lines, calls, fam_lines, dims, tiers, table, beats, checks, excl = _ctx(R)
    return f"""## The PDF: page 3, the {fill(R, R['script']['title'])}

`script.md` starts with `# {fill(R, R['script']['title'])}`, then one line: *{R['script']['subtitle']} · Full Name, Organization · Prepared Mon D, YYYY*.
Then one `## Pn Title` per section, in order; a section whose Prints when is not met is left out, not blank.

Beats by meeting format:
{beats}

| Id | Section | Words | Prints when | Content |
|---|---|---|---|---|
{table(R['script']['blocks'])}

{R['forms']['P8']['never']['label']} {'; '.join(f'"{p}"' for p in R['guardrails']['never_say'])}.
Forbidden claims by domain (P8 quotes the saved domain's): {'; '.join(f"{k}: " + ', '.join(f'"{x}"' for x in v) for k, v in R['guardrails']['forbidden_claims_by_domain'].items() if v)}.

"""


def p_fields(R):
    """fields.json: what the model fills."""
    n, cal, pb, qs, q_lines, calls, fam_lines, dims, tiers, table, beats, checks, excl = _ctx(R)
    return f"""## fields.json: what you fill (S4-13)

You never write brief.md or script.md. Fill `fields.json` -- the keys below, per block; text cites a claim as `[c<id>]` (claims.jsonl),
the assembler numbers the ledger -- then run `python3 eval.py assemble <folder>`. A key marked optional may be left out; `missing` prints
as shown. Labels print exactly as the forms table in pcp.yaml says.

| Block | Form | Keys |
|---|---|---|
{forms_table(R)}

"""


def t_checks_intro(R):
    """The checks: how to run them."""
    n, cal, pb, qs, q_lines, calls, fam_lines, dims, tiers, table, beats, checks, excl = _ctx(R)
    return f"""## Checks (all pass before render)

Run `python3 eval.py checks brief.md script.md --target-nouns "<Full Name>,<surname>,<Organization>,<their key programmes>" --experience <{qs['Q9']['id']}: {', '.join(o['value'] for o in qs['Q9']['options'])}> --authority <caller.authority_level: high, medium>`
and `python3 eval.py duf brief.md script.md`; fix fields.json until both are clean. Every cited fact of the draft (the folder's first build
that fits, recorded by `eval.py assemble`) stays: after the last fit pass, run `python3 eval.py kept <folder>` (C24; S4-4 gives the cut order).
Then run `python3 eval.py battery --latest --depth <depth> --brief brief.md --profile ~/.pcp/profile.yaml`: it reads this
session's own history on Claude Code, Codex, and from the ChatGPT or Claude app export (`python3 eval.py battery conversations.json ...`),
so no host is "unavailable". Fix what it reports: open a cited page you never opened or drop its fact, correct the Run row,
keep the rounds out of the reply; say in the reply what cannot be fixed.
Check the links with `python3 eval.py links brief.md` (S2-8): replace a dead link or drop its fact.

"""


def t_checks_table(R):
    """The checks table: id, name, command, passes when."""
    n, cal, pb, qs, q_lines, calls, fam_lines, dims, tiers, table, beats, checks, excl = _ctx(R)
    return f"""| Id | Check | Command | Passes when |
|---|---|---|---|
{checks}

"""


def p_checks(R):
    """The checks."""
    return t_checks_intro(R) + t_checks_table(R)


def p_render(R):
    """The render command."""
    n, cal, pb, qs, q_lines, calls, fam_lines, dims, tiers, table, beats, checks, excl = _ctx(R)
    return f"""## Render

```
python3 format/talyx_pdf.py --style brief --brief brief.md --script script.md \\
    --columns "{pb['columns']}" --classification "{n['classification']}" \\
    --footer "{n['deliverable']} · <Full Name>, <Organization> · Prepared for you (internal)" \\
    --brief-pages {pb['brief_pages']} --max-pages {pb['total_pages']} --out <dir>/<date>-<slug>-intelligence-brief.pdf
```

Then `python3 eval.py pdf <the PDF> brief.md` must exit 0 ({pb['total_pages']} pages, as S4-3 says).

It uses Playwright's Chromium if installed, else the Chrome, Edge or Chromium already on the computer. If it
reports that neither is there, run `python3 format/talyx_pdf.py --setup` once and render again.

"""


def p_debrief(R):
    """Debrief and ratchet."""
    n, cal, pb, qs, q_lines, calls, fam_lines, dims, tiers, table, beats, checks, excl = _ctx(R)
    return f"""## Debrief and ratchet

After the call: `evals/debrief_template.yaml`, then `python3 eval.py improve` and `python3 eval.py ratchet` (S5-1 to S5-3).

"""


def p_about(R):
    """About."""
    n, cal, pb, qs, q_lines, calls, fam_lines, dims, tiers, table, beats, checks, excl = _ctx(R)
    return f"""## About

Made by Talyx AI, https://talyx.ai. Free to use under the licence in the plug-in's `LICENSE` file.
"""


def render_skill_full(R, sha):
    """The whole of the plug-in as one document, every section in order: the chat apps' knowledge file (build/adapters.py) reads this."""
    return (p_head(R, sha) + p_concepts(R) + p_setup_ask(R) + p_setup_table(R) + p_setup_rules(R)
            + "\n".join(stage_block(R, s) for s in R["stages"]) + "\n"
            + p_asking(R) + p_records(R) + p_sources(R) + p_rounds(R) + p_profile(R) + p_brief(R) + p_script(R) + p_fields(R)
            + p_checks(R) + p_render(R) + p_debrief(R) + p_about(R))


# ---- the lean skill: the procedure in SKILL.md, everything else in references/*.md (pcp.yaml `skill`) ----------------------

def _entry(R, x):
    """One item of a Load list as (path, holds, when): a file id of skill.files, or a plug-in path the scripts read."""
    f = x if isinstance(x, dict) else {"file": x}
    reg = R["skill"]["files"].get(f["file"])
    return (reg["path"], reg["holds"], f.get("when")) if reg else (f["file"], f.get("holds"), f.get("when"))


def load_line(R, load):
    """`**Load:** <path> (what it holds); ...` -- the line a step opens with, naming each file it reads."""
    parts = []
    for x in load:
        path, holds, when = _entry(R, x)
        parts.append(f"`{path}`" + (f" ({holds})" if holds else "") + (f", only when {when}" if when else ""))
    return "**Load:** " + "; ".join(parts) + "."


def config_line(R, step):
    """`**Config:** <file> -- keys ...` for a step that may read keys from pcp.json, or ''."""
    rows = [c for c in R["skill"]["config"] if c["step"] == step]
    return "".join(f"**Config:** `{c['file']}` keys " + ", ".join(f"`{k}`" for k in c["keys"]) + f" -- {c['why']}.\n\n" for c in rows)


def step_load(R, step):
    s = next(x for x in R["skill"]["steps"] if x["id"] == step)
    return load_line(R, s["load"]) + "\n\n" + config_line(R, step)


def setup_table_full(R):
    """The setup questions as the reference prints them: every option with its value and description, what each answer sets,
    and what consumes it (the popup tool shows the descriptions; the saved value is the second word)."""
    lines = ["| # | Chip | Question | Options: label [value]: description | Sets | Used by |", "|---|---|---|---|---|---|"]
    for q in R["calibration"]["questions"]:
        opts = " · ".join(f"{i}. {o['label']} [{o['value']}]: {o['description']}" for i, o in enumerate(q["options"], 1)) if q["options"] else "free text"
        sets = "; ".join(f"{k}: {v}" for k, v in q["sets"].items())
        lines.append(f"| {q['id']} | {q['header']} | {q['question']} | {opts} | {sets} | {', '.join(q.get('consumed_by', []))} |")
    return "\n".join(lines) + "\n\n"


def registers_full(R):
    """Registers by domain with their addresses, and the exclusions."""
    regs = "; ".join(f"{k}: " + ", ".join(f"{r['name']} ({r['url']})" for r in v) for k, v in R["registers"].items() if v) or "none"
    base = t_registers(R)
    return base.replace(base.split("\n\n", 1)[0], f"Registers by domain: {regs}.", 1)


def instrument(R):
    """The metric, its controls and the commands of eval.py (parsed from the script, the one source of its commands)."""
    ev = (HERE / "eval.py").read_text()
    cmds = ", ".join(f"`eval.py {c}`" for c in re.findall(r'sub\.add_parser\("([\w-]+)"', ev))
    verbs = next(c["method_verbs"] for c in R["checks"] if "method_verbs" in c)
    e = R["eval"]
    return ("## The metric and the commands\n\n" + "\n".join(f"- **{k}:** {v}" for k, v in e.items())
            + f"\n- **Method verbs (C8):** {', '.join(verbs)}\n\nCommands of `eval.py`: {cmds}.\n\n")


def renderer_flags(R):
    """Every flag format/talyx_pdf.py takes, parsed from the script."""
    flags = sorted(set(re.findall(r'add_argument\("(--[\w-]+)"', (HERE / "format/talyx_pdf.py").read_text())))
    return ", ".join(f"`{f}`" for f in flags)


def rows_lean(R, rows):
    """A stage's rows as the procedure prints them: the rule as written, or its stub and where the full rule is. No tests (checks.md)."""
    moved = R["skill"]["rows_in_reference"]
    out = []
    for r in rows:
        if r["id"] in moved:
            m = moved[r["id"]]
            out.append(f"- **{r['id']}** {m['stub']} Full rule: `{R['skill']['files'][m['file']]['path']}`.")
        else:
            out.append(f"- **{r['id']}** {fill(R, r['text'])}")
    return "\n".join(out)


def rows_full(R, rows, ids):
    """The full text of the named rows (no tests), for the reference that holds them."""
    by = {r["id"]: r for r in rows}
    return "\n".join(f"- **{i}** {fill(R, by[i]['text'])}" for i in ids)


def moved_ids(R, fid):
    return [i for i, m in R["skill"]["rows_in_reference"].items() if m["file"] == fid]


def all_rows(R):
    return R["calibration"]["rules"] + [r for s in R["stages"] for r in s["rows"]]


def lean_stage(R, s):
    """A stage of the lean skill: Load line, input contract, context, outputs, rows."""
    block = [f"## Stage {s['id'][1]}: {fill(R, s['name'])}", "", step_load(R, s["id"]).rstrip("\n"), "",
             "**Input contract** (declared before behaviour):", "", _inputs(s["inputs"]), "", _context(s["context"]), ""]
    if s.get("outputs"):
        block += ["**Outputs:** " + "; ".join(f"`{o['name']}` ({', '.join(o.get('fields', [])) or o.get('note', '')})" for o in s["outputs"]), ""]
    block += ["**Rows:**", "", rows_lean(R, s["rows"]), ""]
    if s["id"] == "S5":
        block += [p_debrief(R).split("\n\n", 1)[1].rstrip("\n"), ""]
    return "\n".join(block)


def lean_head(R, sha):
    """Frontmatter (the first bytes of the file) and the opening: what this file is and how a step loads its files."""
    n = R["names"]
    return f"""---
name: pre-call-prep
description: >
  {description(R)}
---
{R['render_header'].format(sha=sha)}

# Pre-call prep (v{R['registry_version']})

Stages, dependency-ordered: **setup once -> intake -> {n['collection'].lower()} -> {n['profile'].lower()} -> {n['deliverable']} -> debrief.**
This file is the procedure: for each step, what to do, where to stop and what must pass. Each step's **Load** line names the files
it reads: load them before the step, because they hold the tables, rules and wording this file leaves out. A **Config** line names
the keys a step may read from `pcp.json` (pcp.yaml as JSON); the scripts read it, so never edit or retype it.
Every fact traces to a public source, or to the user's own notes and answers, tagged Yours. Nothing is invented. The deliverable is one 3-page PDF, the {n['deliverable']}. Nothing else is emitted.

**No shell or code tool (plain chat)?** Run the same stages anyway; never stop or refuse for lack of tools: `{R['skill']['files']['in_chat']['path']}` says how (S4-10).

Made by Talyx AI, https://talyx.ai. Free to use under the licence in the plug-in's `LICENSE` file.

"""


def lean_stage0(R):
    """Stage 0: the ask step, the calibration rows (the long ones as stubs)."""
    ask = p_setup_ask(R).split("\n\n", 1)
    return (ask[0] + "\n\n" + step_load(R, "S0") + ask[1] + "**Rows:**\n\n" + rows_lean(R, R["calibration"]["rules"]) + "\n\n")


def lean_checks(R):
    """The checks step: how to run them; the table is in the reference."""
    ck = R["skill"]["checks_step"]
    intro = t_checks_intro(R).split("\n\n", 1)
    return f"## {ck['title']}\n\n" + load_line(R, ck["load"]) + "\n\n" + intro[1]


def lean_render(R):
    rd = R["skill"]["render_step"]
    body = p_render(R).split("\n\n", 1)
    return (f"## {rd['title']}\n\n" + load_line(R, rd["load"]) + "\n\n" + config_line(R, "render") + body[1].rstrip("\n")
            + f"\n\nEvery flag the renderer takes: {renderer_flags(R)}.\n")


def render_skill(R, sha):
    """SKILL.md: the procedure. Everything the steps load is in the references (render_refs)."""
    st = {s["id"]: s for s in R["stages"]}
    return (lean_head(R, sha) + lean_stage0(R) + "\n".join(lean_stage(R, st[i]) for i in ("S1", "S2", "S3", "S4")) + "\n"
            + lean_checks(R) + lean_render(R).rstrip("\n") + "\n\n" + lean_stage(R, st["S5"]))


def ref_head(R, sha, fid):
    f = R["skill"]["files"][fid]
    steps = ", ".join(f"Stage {x['id'][1]}" for x in R["skill"]["steps"] if any((y if isinstance(y, str) else y["file"]) == fid for y in x["load"]))
    return f"{R['render_header'].format(sha=sha)}\n\n# {f['title']}\n\nLoaded by {steps or 'the checks step'} of SKILL.md.\n\n"


def rule_tests(R):
    """The test that makes each rule fail, for every row (SKILL.md prints the rule, not its test)."""
    rows = "\n".join(f"| {r['id']} | {r['test']} |" for r in all_rows(R))
    return f"## Rule tests\n\nEach rule fails when:\n\n| Row | Fails when |\n|---|---|\n{rows}\n\n"


def render_dev(R, sha):
    """evals/rule-tests.md: the rule tests and the worked examples, for developers and eval.py. No step of SKILL.md loads it."""
    d = R["skill"]["dev_file"]
    ex = "\n".join(f"- **{r['id']}** {x}" for r in all_rows(R) for x in r.get("examples", []))
    return (f"{R['render_header'].format(sha=sha)}\n\n# {d['title']}\n\nFor developers and eval.py: no step of SKILL.md loads this file, "
            "so none of it is read at run time. Every rule is in SKILL.md or a reference a step loads; this file holds only how each rule "
            "is made to fail, and the worked examples behind the in-chat self-check.\n\n" + rule_tests(R)
            + (f"## Worked examples\n\nThe numbers are the items of the S4-10 self-check.\n\n{ex}\n" if ex else ""))


def render_refs(R, sha):
    """{path: text} of the generated references a step loads (the Socratic and search-round references have their own renderers)."""
    F = R["skill"]["files"]
    moved = lambda fid: ("## Rules moved out of SKILL.md\n\nThe full text of the rows SKILL.md summarises; the rule is this text.\n\n"
                         + rows_full(R, all_rows(R), moved_ids(R, fid)) + "\n\n") if moved_ids(R, fid) else ""
    out = {
        "setup": ref_head(R, sha, "setup") + t_concepts(R) + "## Setup questions\n\n" + setup_table_full(R) + p_asking(R) + moved("setup")
                 + "## Intake\n\n" + t_intake_columns(R),
        "collection": ref_head(R, sha, "collection") + t_families(R) + registers_full(R) + t_source_lists(R) + p_records(R) + t_linkedin(R) + moved("collection"),
        "profile": ref_head(R, sha, "profile") + f"Rubric version {R['rubric']['version']}: the rubric's own label, not the plug-in's (v{R['registry_version']}); its six dimensions, tiers and phrases are unchanged since that label; only each dimension's printed name (shows) was added since.\n\n" + p_profile(R),
        "brief": ref_head(R, sha, "brief") + t_plain_words(R) + p_brief(R) + p_script(R) + p_fields(R) + moved("brief"),
        "checks": ref_head(R, sha, "checks") + t_checks_table(R).replace("| Id | Check", "## Checks\n\n| Id | Check", 1) + instrument(R),
        "in_chat": ref_head(R, sha, "in_chat") + "## Plain chat\n\n" + t_chat(R) + moved("in_chat"),
    }
    return {F[k]["path"]: v for k, v in out.items()}


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

Every run says which, in B4's last line and in the Coverage row, in the words `{R['skill']['files']['collection']['path']}` gives (S2-7); C16 checks them.

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

First load the `pre-call-prep` skill in this plug-in (Skill tool, or read `skills/pre-call-prep/SKILL.md`) and the references each step of it loads -- the block schema, titles and budgets live there, not here. Never write a brief without it. Then follow it exactly, in stage order:

0. **Setup** -- ask the questions with `AskUserQuestion` ({calls_txt}), only those `{R['calibration']['profile_path']}` has no answer for (all with `--recalibrate`), a typed list only where the host has no question tool; read files given with `--context`.
1. **Intake** -- resolve `$ARGUMENTS` (CSV path, `"Name, Org"`, or ask). Never start without a full name and an organisation. Confirm the meeting objective: say it back in the one status line, and ask only as `references/socratic-questions.md` says.
2. **{n['collection']}** -- run the enabled source types in the search rounds of `references/osint-search.md` (LinkedIn only as its search results show it; never a browser); write `claims.jsonl` and the coverage ledger. Drop excluded claims before writing.
3. **{n['profile']}** -- read six dimensions from claim ids only; set the evidence tier.
4. **{n['deliverable']}** -- fill `fields.json` (`references/brief.md` lists its keys) and run `python3 eval.py assemble <folder>` -- it builds `brief.md` (B1-B10) and `script.md` (P1-P9) from the schema, never write them yourself; run `python3 eval.py checks brief.md script.md --target-nouns \"<name>,<org>\" --experience <Q9> --authority <caller.authority_level>` and `python3 eval.py duf brief.md script.md`; rewrite until clean; render with `format/talyx_pdf.py --style brief --brief-pages {pb['brief_pages']} --max-pages {pb['total_pages']}` and check it with `python3 eval.py pdf <the PDF> brief.md`. Deliver the PDF path and the run line (date · depth · status · facts · searches, from the ledger's Run row). Delete `brief.md`/`script.md` after a clean render.
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


def exact_removed(text, exempt):
    """text without the exempt strings, each matched whole."""
    for s in exempt:
        text = text.replace(s, " ")
    return text


def plain_violations(R, texts):
    """Banned words in user-facing text: the names, the setup questions and the skill's listing text (plain_words.banned, and
    plain_words.setup_banned: 'targets', 'Target kind', 'news families', 'claims.jsonl', Oct 18). A banned word inside a
    plain_words.allowed phrase (asset manager) is not the banned word; a plain_words.exempt string (Q2's and Q7's 2.1.0 text) is skipped whole."""
    pw = R["plain_words"]
    words = re.compile(r"\b(?:" + "|".join(re.escape(w) for w in pw["banned"] + pw.get("setup_banned", [])) + r")\b", re.I)
    allowed = re.compile(r"\b(?:" + "|".join(re.escape(w) for w in pw.get("allowed") or ["\x00"]) + r")\b", re.I)
    exempt = pw.get("exempt") or []   # exact strings Daniel kept from 2.1.0 (pcp.yaml plain_words.exempt); never a pattern
    texts = [allowed.sub(" ", exact_removed(t, exempt)) for t in texts]
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
    skill_md = render_skill(R, sha)
    refs = {HERE / "skills/pre-call-prep" / path: text for path, text in render_refs(R, sha).items()}
    targets = {HERE / "skills/pre-call-prep/SKILL.md": skill_md,
               HERE / "skills/pre-call-prep/references/socratic-questions.md": render_socratic(R, sha),
               HERE / "skills/pre-call-prep/references/osint-search.md": render_osint(R, sha),
               **refs,
               HERE / R["skill"]["dev_file"]["path"]: render_dev(R, sha),
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
    inv = inventory_problems(R, targets[HERE / "INVENTORY.md"], skill_md + "\n".join(refs.values()))
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
