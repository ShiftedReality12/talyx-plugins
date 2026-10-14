#!/usr/bin/env python3
"""render_skill.py -- pcp.yaml -> SKILL.md, commands/pcp.md, the Socratic reference and pcp.json.

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
            f"  questions, research from public sources (plus LinkedIn through your browser and your own files, when\n"
            f"  you allow it), and ONE 3-page PDF: a 2-page {n['deliverable']} and a 1-page meeting script, every fact\n"
            f"  cited. Use when the user mentions pre-call prep, meeting prep, call preparation, researching someone\n"
            f"  before a meeting, talking points, or shares an intake list. Do not use for general research unrelated\n"
            f"  to a meeting, or for notes on a meeting that has already happened.")


def render_skill(R, sha):
    n, cal, pb = R["names"], R["calibration"], R["page_budget"]
    qs = {q["id"]: q for q in cal["questions"]}
    q_lines = []
    for q in cal["questions"]:
        opts = " / ".join(o["label"] for o in q["options"]) if q["options"] else "free text"
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

## How PCP thinks (never in the output)

{chr(10).join('- ' + fill(R, c) for c in R['concepts'])}

**Plain words.** {R['plain_words']['rule']} Never write a word banned: {', '.join(R['plain_words']['banned'])}, or an internal id
(C1-C4, F1-F12, row ids). Allowed only inside these phrases: {', '.join(R['plain_words']['allowed'])}.
Use "source types", not families; "the person you're meeting", not target. Call the deliverable the {n['deliverable']}, nothing else.

## Stage 0: Setup (once)

Read `{cal['profile_path']}`. Ask only the questions it has no answer for -- all of them the first time
or with `{cal['reask_flag']}` -- using the host's question form (`AskUserQuestion` in Claude; else one chat
message with numbered options), first option recommended, in these calls: {calls}. Then write the profile
(`pcp_profile_format: 1`, answers under `profiles: <name>: answers: Qn: {{value, defaulted}}`, plus `context`
and `linkedin` when set) and continue.

| # | Chip | Question | Options | Sets |
|---|---|---|---|---|
{chr(10).join(q_lines)}

{_rows(R, cal['rules'])}

{chr(10).join(stages)}
## Asking questions

When a question is needed -- of the user, or for the room -- read `references/socratic-questions.md` first.

## Source families

Enabled per profile: `depth` filters the column, `target.kind` filters `kinds`, `socmint.scope` filters F6
to `{', '.join(R['research']['socmint_networks']['professional'])}` (professional) or the wider list (social) or none.
FULL status needs >= 1 C1/C2 claim in {R['research']['full_threshold']} families (by depth).

| Id | Family | Depth | Social | Query template | Extract |
|---|---|---|---|---|---|
{chr(10).join(fam_lines)}

Registers by domain: {'; '.join(f"{k}: " + ', '.join(r['name'] for r in v) for k, v in R['registers'].items() if v) or 'none'}.

**Exclusions (dropped before the writer, counted in coverage):** {', '.join(excl['base'])}.
By jurisdiction: {'; '.join(f"{k}: {', '.join(v)}" for k, v in excl['by_jurisdiction'].items() if v)}.

## {n['profile']} (six dimensions)

Tiers: high = {tiers['high']['min_observations']} observations, {tiers['high']['corroborated_across_sources']} sources, a direct quote or action;
medium = {tiers['medium']['min_observations']} observations, {tiers['medium']['corroborated_across_sources']} source; low = role-inferred only (renders as "No read").

| Dimension | Row label (B6) | Signals | Low means | Mid means | High means |
|---|---|---|---|---|---|
{dims}

What they may want (depth deep only): <= {R['rubric']['ach']['max_hypotheses']} hypotheses about what they want from this meeting, each with the claim that would disprove it.

## The PDF: pages 1-2, the {n['deliverable']}

`brief.md` starts with `# Full Name`, then the identity line (`**Organization** | Role, since year | City, if public`),
then the meta line (`Meeting: ... | Prepared for: ... | Depth: ... | Sources: n of 12 source types, n cited | Status FULL or LIMITED | Prepared Mon D, YYYY`).
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

Never say: {'; '.join(f'"{p}"' for p in R['guardrails']['never_say'])}.

## Checks (all pass before render)

Run `python3 eval.py checks brief.md script.md --target-nouns "<Full Name>,<surname>,<Organization>,<their key programmes>" --experience <{qs['Q9']['id']}: {', '.join(o['value'] for o in qs['Q9']['options'])}>`
and `python3 eval.py duf brief.md script.md`; rewrite until both are clean.

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
    return f"""{R['render_header'].format(sha=sha)}
---
description: Prepare for a meeting. Sets up once, researches the person, and writes ONE {pb['total_pages']}-page PDF -- the {n['deliverable']} and a meeting script.
argument-hint: "[intake.csv | \\"Full Name, Organisation\\"] [--recalibrate] [--profile <name>] [--context <file>] [--out <dir>]"
---

# /pcp: pre-call prep

Input from the user: `$ARGUMENTS`

Follow the `pre-call-prep` skill in this plug-in exactly, in stage order:

0. **Setup** -- ask only the questions `{R['calibration']['profile_path']}` has no answer for (all with `--recalibrate`); read files given with `--context`.
1. **Intake** -- resolve `$ARGUMENTS` (CSV path, `"Name, Org"`, or ask). Never start without a full name and an organisation. Ask the user only as `references/socratic-questions.md` says.
2. **{n['collection']}** -- run the enabled source types, LinkedIn only with a yes each run; write `claims.jsonl` and the coverage ledger. Drop excluded claims before writing.
3. **{n['profile']}** -- score six dimensions from claim ids only; set the evidence tier.
4. **{n['deliverable']}** -- write `brief.md` (B1-B10) and `script.md` (P1-P9); run `python3 eval.py checks brief.md script.md --target-nouns \"<name>,<org>\" --experience <Q9>` and `python3 eval.py duf brief.md script.md`; rewrite until clean; render with `format/talyx_pdf.py --style brief --brief-pages {pb['brief_pages']} --max-pages {pb['total_pages']}` and check it with `python3 eval.py pdf <the PDF> brief.md`. Deliver the PDF path. Delete `brief.md`/`script.md` after a clean render.
5. **After the call** -- offer the four-field template in `evals/debrief_template.yaml`; never ask for more.

Say what was NOT found before what was.
"""


def plain_violations(R, texts):
    """Banned words in user-facing text: the names, the setup questions and the skill's listing text.
    A banned word inside a plain_words.allowed phrase (asset manager) is not the banned word."""
    pw = R["plain_words"]
    words = re.compile(r"\b(?:" + "|".join(re.escape(w) for w in pw["banned"]) + r")\b", re.I)
    allowed = re.compile(r"\b(?:" + "|".join(re.escape(w) for w in pw.get("allowed") or ["\x00"]) + r")\b", re.I)
    texts = [allowed.sub(" ", t) for t in texts]
    return sorted({m.group(0) for t in texts for pat in (words, re.compile(pw["codes"])) for m in pat.finditer(t)})


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
               HERE / "commands/pcp.md": render_command(R, sha),
               HERE / "pcp.json": json.dumps(R, ensure_ascii=False, separators=(",", ":"), default=str) + "\n"}
    bad_words = plain_violations(R, user_facing(R))
    if bad_words:
        print("PLAIN WORDS FAIL -- user-facing text in pcp.yaml uses:", ", ".join(bad_words))
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
