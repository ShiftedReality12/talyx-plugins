# /pcp: pre-call prep

A free plug-in from [Talyx AI](https://talyx.ai). Type `/pcp` before a meeting and get **one 3-page
PDF**: a 2-page pre-call brief and a 1-page meeting script on the person, company or deal you are about
to meet, built from public sources, every fact cited. Runs in Claude Code, Claude desktop, Codex,
ChatGPT desktop, Grok, Cursor, Gemini CLI, Devin and Perplexity -- see the
[repository README](../../README.md) for install commands and which hosts are verified.

## What it does

0. **Calibrates once per user.** Eight quick questions the first time (role, domain, target kind,
   meeting shape, depth, social scope, jurisdiction, your offer). Saved per user and reused by every
   later run; only a question added in a later version is asked again. `--recalibrate` redoes them.
1. **Intake.** A name and an organisation, or a CSV of up to 8 rows.
2. **Collects.** Up to 12 public source families (identity, career, org news, voice, public social,
   affiliations, publications, registers, events, shared context, counter-evidence). Writes a
   coverage ledger: what was attempted, what was found, what failed. Excluded topics are dropped
   before anything is written.
3. **Reads behaviour.** Six dimensions, each scored only from cited observations; the evidence tier
   decides how far the script goes.
4. **Renders the PDF.** Pages 1-2 brief, page 3 script. Hard page gate: it fails rather than spills.
5. **Debrief.** Four fields after the call.

## Use

```text
/pcp "Full Name, Organisation"
/pcp path/to/intake.csv
/pcp --recalibrate
/pcp "Full Name, Organisation" --profile investor     # a second saved setup, e.g. for another role
```

Codex and ChatGPT: mention the **pre-call-prep** skill (`$pre-call-prep` in the CLI, `@` in the app).

The first PDF on a machine needs Playwright, Chromium and pypdf. The skill asks before installing them
(`python3 scripts/talyx_pdf.py --setup` from the skill folder).

## Your saved setup

Your calibration answers are saved once per user in `~/.pcp/profile.yaml` by the skill's
`scripts/profile.py`, which validates every answer against the questions in `pcp.yaml`, writes
atomically, never overwrites an unreadable file without asking (it keeps a backup), and holds any
number of named setups (`--profile <name>`). Set `PCP_PROFILE` to keep it somewhere else.

What that means per host:

| Host | Saved setup |
|---|---|
| Claude Code, Grok, Cursor, Gemini CLI, Devin | saved on first run, reused after |
| Codex / ChatGPT desktop | reading works in the sandbox; the first save writes outside the workspace, so approve that one write when asked |
| Claude desktop (Cowork), Perplexity | these run the skill in a sandbox whose home folder may not persist; if it does not, the questions come back in a new session |
| Gemini Gem, Microsoft 365 Copilot | no files: the assistant gives you a *Saved setup* block to paste into the knowledge file ([adapters](../../adapters)) |

## Licence

Free to use under `LICENSE`. Public professional record only; see the exclusions in
`skills/pre-call-prep/pcp.yaml`. Contributors: see the repository README.
