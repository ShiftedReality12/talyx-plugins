# Host and transcript tests (manual)

These need a live host and a real model, so no script runs them. Record each run here: date, version, who ran
it, pass or fail, and one line of evidence (the transcript line or the file). Host results are not a merge gate
(AID-10); the transcript tests are part of the AID-8 merge gate.

## Hosts (AID-10), v3.1.0

| Host | Install path | Result | Date | Evidence |
|---|---|---|---|---|
| Claude Code | `/plugin install pcp@talyx` | not run | | |
| Claude desktop (Cowork) | Customize > Plugins > Add marketplace | not run | | |
| Codex | `codex plugin add pcp@talyx` | not run | | |
| ChatGPT (desktop) | Plugins > Add marketplace | not run | | |
| Grok | `grok plugin install pcp@talyx-plugins --trust` | not run | | |
| Gemini CLI | `gemini extensions install ./talyx-plugins/plugins/pcp` | not run | | |
| Gemini (Antigravity CLI) | `agy plugin install <repo>` | not run | | |
| Cursor | team marketplace | not run | | |
| Devin | `devin plugins install talyx-ai/talyx-plugins#plugins/pcp` | not run | | |
| Perplexity | upload `adapters/perplexity/pre-call-prep.zip` | not run | | |
| Gemini app (Gem) | `adapters/chat/` | not run | | |
| Microsoft 365 Copilot | `adapters/chat/` | not run | | |

v3.0.0 was installed on Sep 28 in Claude Code, Codex, Grok, Gemini CLI, Antigravity and ChatGPT (AID-10); those
results do not carry over to 3.1.0.

## Transcript tests (one real `/pcp` run each)

| Test | Pass when | Result | Date | Evidence |
|---|---|---|---|---|
| T1 No questions before research | An intake with an objective and no relationship: the run asks 0 questions before research (S1-4) | not run | | |
| T2 Ambiguous name | Two people match: the run lists the candidates and stops (S1-2) | not run | | |
| T3 At most two questions | No objective and a relationship with no notes: at most 2 questions, in one message, each skippable (S1-4) | not run | | |
| T4 Context file | `/pcp --context sample-onepager.pdf`: `profile.yaml` holds the path and a summary of at most 150 words; a fact from the file is in the ledger tagged Yours (CAL-4) | not run | | |
| T5 Unsupported file | `/pcp --context deck.pptx`: one line naming .pdf .docx .md .txt .csv; `sha256sum ~/.pcp/profile.yaml` unchanged (CAL-4) | not run | | |
| T6 Missing Q9 | A profile with Q1-Q8 and no Q9: only Q9 is asked (CAL-1) | not run | | |
| T7 LinkedIn No | Answer No: the PDF says `LinkedIn: not read: you declined` in B4 and Coverage; no ledger row tagged LinkedIn (S2-7, C16) | not run | | |
| T8 Real person, end to end | `eval.py checks ... --experience <Q9>`, `eval.py duf ... --pdf OUT.pdf` and `eval.py pdf OUT.pdf brief.md` exit 0; `curl -sIL` on every ledger link returns < 400 | not run | | |
