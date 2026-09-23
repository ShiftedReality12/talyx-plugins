# /pcp: pre-call prep for Claude Code (v2)

A free Claude Code plug-in from [Talyx AI](https://talyx.ai). Type `/pcp` before a meeting and get
**one 3-page PDF**: a 2-page pre-call brief and a 1-page meeting script on the person, company or
deal you are about to meet, built from public sources, every fact cited.

## What it does

0. **Calibrates once.** Eight quick questions the first time (role, domain, target kind, meeting
   shape, depth, social scope, jurisdiction, your offer). Stored in `~/.pcp/profile.yaml`; never
   asked again unless you pass `--recalibrate`.
1. **Intake.** A name and an organisation, or a CSV of up to 8 rows.
2. **Collects.** Up to 12 public source families (identity, career, org news, voice, public social,
   affiliations, publications, registers, events, shared context, counter-evidence). Writes a
   coverage ledger: what was attempted, what was found, what failed. Excluded topics are dropped
   before anything is written.
3. **Reads behaviour.** Six dimensions, each scored only from cited observations; the evidence tier
   decides how far the script goes.
4. **Renders the PDF.** Pages 1-2 brief (snapshot, their words, strategic read, behavioral read,
   discovery questions, situation framed, value + next step, guardrails, sources). Page 3 script
   (open, beats, questions, objections, close, never-say). Hard page gate: it fails rather than
   spills.
5. **Debrief.** Four fields after the call feed proposals back into the registry; a change lands only
   if it does not regress any frozen eval target.

## Install

```
/plugin marketplace add talyx-ai/talyx-plugins
/plugin install pcp@talyx
python3 format/talyx_pdf.py --setup      # once per machine: Playwright + Chromium + pypdf
```

## Use

```
/pcp "Full Name, Organisation"
/pcp path/to/intake.csv
/pcp --recalibrate
```

## How it is built (for contributors)

Three files. Everything else is generated or frozen.

| File | Role |
|---|---|
| `pcp.yaml` | The registry: every question, parameter, source family, rubric band, page budget, instruction row (with its falsification test) |
| `render_skill.py` | Renders `skills/pre-call-prep/SKILL.md` and `commands/pcp.md` from the registry. The only writer. |
| `eval.py` | The instrument: `duf` (decision-useful facts per page), `checks`, `concordance`, `self-test`, `ratchet`, `improve` |

`format/talyx_pdf.py` is the portable house-style renderer (also exposed as the `talyx-pdf` skill).

Contract: edit `pcp.yaml`, run `python3 render_skill.py`, then `python3 eval.py concordance && python3 eval.py self-test && python3 eval.py ratchet`. A hand edit to a generated file fails concordance. A registry change that lowers any frozen target's `duf_pp` below its floor fails the ratchet.

## Licence

Free to use under `LICENSE`. Public professional record only; see the exclusions in `pcp.yaml`.
