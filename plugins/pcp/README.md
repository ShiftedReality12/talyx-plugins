# /pcp: pre-call prep for Claude Code (v3)

A free Claude Code plug-in from [Talyx AI](https://talyx.ai). Type `/pcp` before a meeting and get
**one 3-page PDF**: a 2-page Intelligence Brief and a 1-page meeting script on the person, company or
deal you are about to meet, built from public sources (plus LinkedIn and your own files, when you allow
it), every fact cited.

## What it does

0. **Sets up once.** Nine quick questions the first time (role, domain, target kind, meeting
   shape, depth, social scope, jurisdiction, experience, your offer and any files about your
   business). Stored in `~/.pcp/profile.yaml`; never asked again unless you pass `--recalibrate`.
1. **Intake.** A name and an organisation, or a CSV of up to 8 rows.
2. **Intelligence collection.** Up to 12 public source types (identity, career, org news, voice,
   public social, affiliations, publications, registers, events, shared context, counter-evidence),
   LinkedIn through your own browser if you say yes that run, and your own files and notes. Excluded
   topics are dropped before anything is written.
3. **Meeting approach.** Six dimensions, each read only from cited observations; the evidence tier
   decides how far the script goes.
4. **The Intelligence Brief.** Pages 1-2: the Take, questions that close gaps, who they are, in their
   words, signals, meeting approach, who decides, strongest case against, meeting angle, and the
   evidence ledger. Page 3: the meeting script. Whatever the record could not show becomes a question
   to ask in the room. Hard page gate: it fails rather than spills.
5. **After the call.** Four fields feed proposals back into the registry; a change lands only
   if it does not regress any frozen eval target.

## Install

```
/plugin marketplace add talyx-ai/talyx-plugins
/plugin install pcp@talyx
```

The PDF uses the Chrome, Edge or Chromium already on your computer. With none of them, run
`python3 format/talyx_pdf.py --setup` once.

## Use

```
/pcp "Full Name, Organisation"
/pcp path/to/intake.csv
/pcp --recalibrate
/pcp --context path/to/your-deck.pdf      # add files about your business at any time
```

## How it is built (for contributors)

Three files. Everything else is generated or frozen.

| File | Role |
|---|---|
| `pcp.yaml` | The registry: every name, question, parameter, source family, rubric band, page budget, instruction row (with its falsification test) |
| `render_skill.py` | Renders `skills/pre-call-prep/SKILL.md`, its `references/socratic-questions.md`, `commands/pcp.md` and `pcp.json` (the registry as JSON, so the scripts need no YAML library) from the registry. The only writer. |
| `eval.py` | The instrument: `duf` (decision-useful facts per page), `checks`, `concordance`, `self-test`, `ratchet`, `improve` |

`format/talyx_pdf.py` is the portable house-style renderer (also exposed as the `talyx-pdf` skill).

Contract: edit `pcp.yaml`, run `python3 render_skill.py`, then `python3 eval.py concordance && python3 eval.py self-test && python3 eval.py ratchet`. A hand edit to a generated file fails concordance. A registry change that lowers any frozen target's `duf_pp` below its floor fails the ratchet.

## Licence

Free to use under `LICENSE`. Public professional record only; see the exclusions in `pcp.yaml`.
