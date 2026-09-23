#!/usr/bin/env python3
"""render_skill.py -- pcp.yaml -> skills/pre-call-prep/SKILL.md + commands/pcp.md.

The ONLY writer of those two files. Both carry a header with the registry sha256; eval.py
`concordance` re-renders to memory and diffs, so a hand edit to either file fails the gate.

Usage:
  python3 render_skill.py            # write both files
  python3 render_skill.py --check    # exit 1 if either file differs from a fresh render
"""
import argparse
import hashlib
import pathlib
import sys

import yaml

HERE = pathlib.Path(__file__).resolve().parent
REG = HERE / "pcp.yaml"


def load():
    raw = REG.read_bytes()
    return yaml.safe_load(raw), hashlib.sha256(raw).hexdigest()[:12]


def _rows(rows):
    out = []
    for r in rows:
        out.append(f"- **{r['id']}** {r['text']}  \n  _Fails when:_ {r['test']}")
    return "\n".join(out)


def _inputs(inputs):
    lines = ["| Input | Type | Source | Required | Fallback |", "|---|---|---|---|---|"]
    for i in inputs:
        lines.append(f"| `{i['name']}` | {i['type']} | {i['source']} | {'yes' if i['required'] else 'no'} | {i['fallback']} |")
    return "\n".join(lines)


def _context(ctx):
    return (f"**Context contract** -- read, in this order: {', '.join(ctx['order'])}. "
            f"Budget: {ctx['budget_words']} words. Not read: {', '.join(ctx['excluded'])}.")


def render_skill(R, sha):
    cal = R["calibration"]
    q_lines = []
    for q in cal["questions"]:
        opts = " / ".join(o["label"] for o in q["options"]) if q["options"] else "free text"
        q_lines.append(f"| {q['id']} | {q['header']} | {q['question']} | {opts} | {', '.join(q['sets'].keys())} |")
    fam_lines = []
    for f in R["families"]:
        fam_lines.append(f"| {f['id']} | {f['name']} | {'/'.join(f['depth'])} | {'yes' if f['socmint'] else 'no'} | `{f['query']}` | {f['extract']} |")
    dims = "\n".join(
        f"| {d['id']} | {'; '.join(d['signals'])} | {d['meaning']['low']} | {d['meaning']['mid']} | {d['meaning']['high']} |"
        for d in R["rubric"]["dimensions"])
    tiers = R["rubric"]["tiers"]
    brief = "\n".join(f"| {s['id']} | {s['title']} | {s['words']} | {s['content']} |" for s in R["brief"]["sections"])
    script = "\n".join(f"| {b['id']} | {b['title']} | {b['words']} | {b['content']} |" for b in R["script"]["blocks"])
    beats = "\n".join(f"- **{k}**: {' -> '.join(v)}" for k, v in R["script"]["beats_by_format"].items())
    checks = "\n".join(f"| {c['id']} | {c['name']} | `{c['cmd']}` | {c['passes_when']} |" for c in R["checks"] if "cmd" in c)
    excl = R["exclusions"]
    pb = R["page_budget"]

    stages = []
    for s in R["stages"]:
        block = [f"## Stage {s['id'][1]}: {s['name']}", "", "**Input contract** (declared before behaviour):", "", _inputs(s["inputs"]), "",
                 _context(s["context"]), ""]
        if s.get("outputs"):
            block += ["**Outputs:** " + "; ".join(f"`{o['name']}` ({', '.join(o.get('fields', [])) or o.get('note', '')})" for o in s["outputs"]), ""]
        block += ["**Rows:**", "", _rows(s["rows"]), ""]
        stages.append("\n".join(block))

    return f"""{R['render_header'].format(sha=sha)}
---
name: pre-call-prep
description: >
  Prepare for an upcoming meeting with a named person, company or deal. Eight one-time calibration
  questions, public-source OSINT/SOCMINT collection with a coverage ledger, a six-dimension
  behavioral read, and ONE 3-page PDF: a 2-page brief plus a 1-page meeting script. Use when the
  user mentions pre-call prep, meeting prep, call preparation, researching someone before a
  meeting, talking points, or shares an intake list. Do not use for general research unrelated to
  a meeting, or for notes on a meeting that has already happened.
---

# Pre-call prep (v{R['registry_version']})

Five stages, dependency-ordered: **calibrate once -> intake -> collect -> read -> brief + script -> debrief.**
Every stage declares its inputs before its behaviour, reads only its listed context, and follows rows
that each carry a falsification test. Every fact traces to a public source. Nothing is invented.
The deliverable is one 3-page PDF. Nothing else is emitted.

## Stage 0: Calibrate (once)

If `{cal['profile_path']}` is missing or invalid, or `{cal['reask_flag']}` is passed, ask these eight
questions with `AskUserQuestion` -- two calls of four, first option recommended -- then write the
profile and continue. Otherwise read the profile silently.

| # | Chip | Question | Options | Sets |
|---|---|---|---|---|
{chr(10).join(q_lines)}

{_rows(cal['rules'])}

Profile line (footer of every PDF): `role · domain · depth · jurisdiction`.

{chr(10).join(stages)}
## Source families

Enabled per profile: `depth` filters the column, `target.kind` filters `kinds`, `socmint.scope` filters F6
to `{', '.join(R['research']['socmint_networks']['professional'])}` (professional) or the wider list (social) or none.
FULL status needs >= 1 C1/C2 claim in {R['research']['full_threshold']} families (by depth).

| Id | Family | Depth | SOCMINT | Query template | Extract |
|---|---|---|---|---|---|
{chr(10).join(fam_lines)}

Registers by domain: {'; '.join(f"{k}: " + ', '.join(r['name'] for r in v) for k, v in R['registers'].items() if v) or 'none'}.

**Exclusions (dropped before the writer, counted in coverage):** {', '.join(excl['base'])}.
By jurisdiction: {'; '.join(f"{k}: {', '.join(v)}" for k, v in excl['by_jurisdiction'].items() if v)}.

## Behavioral read (six dimensions)

Tiers: high = {tiers['high']['min_observations']} observations, {tiers['high']['corroborated_across_sources']} sources, a direct quote or action;
medium = {tiers['medium']['min_observations']} observations, {tiers['medium']['corroborated_across_sources']} source; low = role-inferred only (renders as "no read").

| Dimension | Signals | Low means | Mid means | High means |
|---|---|---|---|---|
{dims}

ACH mini (depth deep only): <= {R['rubric']['ach']['max_hypotheses']} hypotheses about what they want from this meeting, each with the claim that would disconfirm it.

## The PDF: pages 1-2 brief

Word budgets are the page budget; the engine renders on a {len(pb['ladder'])}-rung density ladder and fails, never spills, past {pb['total_pages']} pages.

| Id | Section | Words | Content |
|---|---|---|---|
{brief}

Domain vocabulary: {'; '.join(f"{k}: {', '.join(v)}" for k, v in R['brief']['vocab_by_domain'].items() if v)}.

## The PDF: page 3 meeting script

Beats by meeting format:
{beats}

| Id | Block | Words | Content |
|---|---|---|---|
{script}

Never say: {'; '.join(f'"{p}"' for p in R['guardrails']['never_say'])}.

## Checks (all pass before render)

| Id | Check | Command | Passes when |
|---|---|---|---|
{checks}

## Render

```
python3 format/talyx_pdf.py --brief brief.md --script script.md --title "<Name> -- <Org>" \\
    --subtitle "Pre-call brief · <meeting date>" --footer "<profile line> · <status> · duf_pp <x> · coverage <a>/<b>" \\
    --max-pages {pb['total_pages']} --out <dir>/<date>-<slug>.pdf
```

## Debrief and ratchet

After the call, `evals/debrief_template.yaml` (four fields). `python3 eval.py improve` proposes row diffs to
`pcp.yaml`; `python3 eval.py ratchet` lands them only if every frozen target holds its floor. The floor is the
best ever seen and only rises.

## About

Made by Talyx AI, https://talyx.ai. Free to use under the licence in the plug-in's `LICENSE` file.
"""


def render_command(R, sha):
    return f"""{R['render_header'].format(sha=sha)}
---
description: Prepare for a meeting. Calibrates once, researches from public sources, reads behaviour, and writes ONE 3-page PDF (2-page brief + 1-page script).
argument-hint: "[intake.csv | \\"Full Name, Organisation\\"] [--recalibrate] [--profile <name>] [--out <dir>]"
---

# /pcp: pre-call prep

Input from the user: `$ARGUMENTS`

Follow the `pre-call-prep` skill in this plug-in exactly, in stage order:

0. **Calibrate** -- if `{R['calibration']['profile_path']}` is missing/invalid or `--recalibrate` is present, ask the eight questions (two `AskUserQuestion` calls of four) and write the profile. Otherwise read it silently.
1. **Intake** -- resolve `$ARGUMENTS` (CSV path, `"Name, Org"`, or ask). Confirm the objective. Never start without a full name and an organisation.
2. **Collect** -- run the enabled source families; write `claims.jsonl` and the coverage ledger. Drop excluded claims before writing.
3. **Read** -- score six dimensions from claim ids only; set the evidence tier.
4. **Brief + script** -- write `brief.md` (B1-B9) and `script.md` (P1-P7); run `python3 eval.py checks` and `python3 eval.py duf`; rewrite until clean; render with `format/talyx_pdf.py --max-pages 3`. Deliver the PDF path and the footer line. Delete `brief.md`/`script.md` after a clean render.
5. **Debrief** -- offer the four-field debrief template; never ask for more.

Say what was NOT found (coverage) before what was.
"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    a = ap.parse_args()
    R, sha = load()
    targets = {HERE / "skills/pre-call-prep/SKILL.md": render_skill(R, sha), HERE / "commands/pcp.md": render_command(R, sha)}
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
