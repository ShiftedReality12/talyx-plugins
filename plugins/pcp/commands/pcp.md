---
description: Prepare for a meeting. Sets up once, researches the person, and writes ONE 3-page PDF -- the Intelligence Brief and a meeting script.
argument-hint: "[intake.csv | \"Full Name, Organisation\"] [--recalibrate] [--profile <name>] [--context <file>] [--out <dir>]"
---
<!-- GENERATED from pcp.yaml (sha256:54aae2fe828d) by render_skill.py -- edit pcp.yaml, never this file -->

# /pcp: pre-call prep

Input from the user: `$ARGUMENTS`

First load the `pre-call-prep` skill in this plug-in (Skill tool, or read `skills/pre-call-prep/SKILL.md`) -- the block schema, titles and budgets live there, not here. Never write a brief without it. Then follow it exactly, in stage order:

0. **Setup** -- ask only the questions `~/.pcp/profile.yaml` has no answer for (all with `--recalibrate`); read files given with `--context`.
1. **Intake** -- resolve `$ARGUMENTS` (CSV path, `"Name, Org"`, or ask). Never start without a full name and an organisation. Ask the user only as `references/socratic-questions.md` says.
2. **Intelligence collection** -- run the enabled source types in the search rounds of `references/osint-search.md` (LinkedIn only as its search results show it; never a browser); write `claims.jsonl` and the coverage ledger. Drop excluded claims before writing.
3. **Behavioral profile** -- read six dimensions from claim ids only; set the evidence tier.
4. **Intelligence Brief** -- write `brief.md` (B1-B10) and `script.md` (P1-P9); run `python3 eval.py checks brief.md script.md --target-nouns "<name>,<org>" --experience <Q9> --authority <caller.authority_level>` and `python3 eval.py duf brief.md script.md`; rewrite until clean; render with `format/talyx_pdf.py --style brief --brief-pages 2 --max-pages 3` and check it with `python3 eval.py pdf <the PDF> brief.md`. Deliver the PDF path. Delete `brief.md`/`script.md` after a clean render.
5. **After the call** -- offer the four-field template in `evals/debrief_template.yaml`; never ask for more.

Say what was NOT found before what was.

**No shell or code tool (plain chat)?** Do not stop. Skip only the script steps (file writes, `eval.py`, the PDF
render): research with the host's web search, keep claims in the conversation, apply the checks yourself, and
deliver the full Intelligence Brief in chat in the S4-10 format -- first line the in-chat label, then
`--- Page 1 ---`, `--- Page 2 ---`, `--- Page 3 ---` with `# Meeting script`. Thin evidence still gets the full
3 parts with what was not found stated in each.
