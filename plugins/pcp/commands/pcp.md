<!-- GENERATED from pcp.yaml (sha256:7ab2f8560c18) by render_skill.py -- edit pcp.yaml, never this file -->
---
description: Prepare for a meeting. Sets up once, researches the person, and writes ONE 3-page PDF -- the Intelligence Brief and a meeting script.
argument-hint: "[intake.csv | \"Full Name, Organisation\"] [--recalibrate] [--profile <name>] [--context <file>] [--out <dir>]"
---

# /pcp: pre-call prep

Input from the user: `$ARGUMENTS`

Follow the `pre-call-prep` skill in this plug-in exactly, in stage order:

0. **Setup** -- ask only the questions `~/.pcp/profile.yaml` has no answer for (all with `--recalibrate`); read files given with `--context`.
1. **Intake** -- resolve `$ARGUMENTS` (CSV path, `"Name, Org"`, or ask). Never start without a full name and an organisation. Ask the user only as `references/socratic-questions.md` says.
2. **Intelligence collection** -- run the enabled source types, LinkedIn only with a yes each run; write `claims.jsonl` and the coverage ledger. Drop excluded claims before writing.
3. **Meeting approach** -- score six dimensions from claim ids only; set the evidence tier.
4. **Intelligence Brief** -- write `brief.md` (B1-B10) and `script.md` (P1-P9); run `python3 eval.py checks brief.md script.md --target-nouns "<name>,<org>" --experience <Q9>` and `python3 eval.py duf brief.md script.md`; rewrite until clean; render with `format/talyx_pdf.py --style brief --brief-pages 2 --max-pages 3` and check it with `python3 eval.py pdf <the PDF> brief.md`. Deliver the PDF path. Delete `brief.md`/`script.md` after a clean render.
5. **After the call** -- offer the four-field template in `evals/debrief_template.yaml`; never ask for more.

Say what was NOT found before what was.
