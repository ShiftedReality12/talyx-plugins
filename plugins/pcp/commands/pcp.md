<!-- GENERATED from pcp.yaml (sha256:e3aa4c7bd431) by render_skill.py -- edit pcp.yaml, never this file -->
---
description: Prepare for a meeting. Calibrates once, researches from public sources, reads behaviour, and writes ONE 3-page PDF (2-page brief + 1-page script).
argument-hint: "[intake.csv | \"Full Name, Organisation\"] [--recalibrate] [--profile <name>] [--out <dir>]"
---

# /pcp: pre-call prep

Input from the user: `$ARGUMENTS`

Follow the `pre-call-prep` skill in this plug-in exactly, in stage order:

0. **Calibrate** -- if `~/.pcp/profile.yaml` is missing/invalid or `--recalibrate` is present, ask the eight questions (two `AskUserQuestion` calls of four) and write the profile. Otherwise read it silently.
1. **Intake** -- resolve `$ARGUMENTS` (CSV path, `"Name, Org"`, or ask). Confirm the objective. Never start without a full name and an organisation.
2. **Collect** -- run the enabled source families; write `claims.jsonl` and the coverage ledger. Drop excluded claims before writing.
3. **Read** -- score six dimensions from claim ids only; set the evidence tier.
4. **Brief + script** -- write `brief.md` (B1-B9) and `script.md` (P1-P7); run `python3 eval.py checks` and `python3 eval.py duf`; rewrite until clean; render with `format/talyx_pdf.py --max-pages 3`. Deliver the PDF path and the footer line. Delete `brief.md`/`script.md` after a clean render.
5. **Debrief** -- offer the four-field debrief template; never ask for more.

Say what was NOT found (coverage) before what was.
