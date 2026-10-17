# Host and transcript tests (manual)

These need a live host and a real model, so no script runs them. Record each run here: date, version, who ran
it, pass or fail, and one line of evidence (the transcript line or the file). Host results are not a merge gate
(AID-10); the transcript tests are part of the AID-8 merge gate.

## Hosts (AID-10), v3.1.1

| Host | Install path | Result | Date | Evidence |
|---|---|---|---|---|
| Claude Code | `/plugin install pcp@talyx` | pass, headless (`claude -p`, plugin loaded from the working tree with `--plugin-dir`, not installed; Claude Sonnet 5.5, 2.1.302, account acct4); 3.1.0 tree 47c4659, run by Claude for Daniel, T1 T3 T6 and a Stage 4 run | 2026-10-17 | the skill loaded each step's references from its Load line (setup.md, socratic-questions.md, collection.md, osint-search.md, profile.md, brief.md, checks.md); transcripts in ~/Downloads/pcp-finish/trim-2026-10-17/host-tests/ |
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
results do not carry over to 3.1.1.

## Transcript tests (one real `/pcp` run each)

| Test | Pass when | Result | Date | Evidence |
|---|---|---|---|---|
| T1 No questions before research | An intake with an objective and no relationship: the run asks 0 questions before research (S1-4) | pass | 2026-10-17 | Claude Code headless, fictional target Jane Doe at Alder Grey Capital, full saved setup: no question and no tool call asking one before the first search; one status line, then a background collection job (S2-11); `eval.py battery <session> <subagent>` : 36 searches (11 base) in 5 rounds, 25 with an operator or domain filter, 0 failures (host-tests/H2-*.jsonl) |
| T2 Ambiguous name | Two people match: the run lists the candidates and stops (S1-2) | not run | | |
| T3 At most two questions | No objective and a relationship with no notes: at most 2 questions, in one message, each skippable (S1-4) | pass | 2026-10-17 | Claude Code headless: one message, 2 questions (objective; the earlier meeting), each with a skip option and the line 'reply skip and I'll go on without them', no research before the answer (host-tests/H3-two-questions.jsonl) |
| T4 Context file | `/pcp --context sample-onepager.pdf`: `profile.yaml` holds the path and a summary of at most 150 words; a fact from the file is in the ledger tagged Yours (CAL-4) | not run | | |
| T5 Unsupported file | `/pcp --context deck.pptx`: one line naming .pdf .docx .md .txt .csv; `sha256sum ~/.pcp/profile.yaml` unchanged (CAL-4) | not run | | |
| T6 Missing Q9 | A profile with Q1-Q8 and no Q9: only Q9 is asked (CAL-1) | pass | 2026-10-17 | Claude Code headless: asked Q9 only; the question tool is not offered in `claude -p` (ToolSearch found none), so the typed list with the skip rule was the fallback; no research before the answer (host-tests/H1-q9-missing.jsonl) |
| T7 LinkedIn by search only | A public executive: the transcript shows no linkedin.com request and no browser tool; B4 and Coverage both read `LinkedIn: read from search results` with the profile's search result in the ledger, or `LinkedIn: not read: no matching profile` with no row tagged LinkedIn (S2-7, C16) | not run | | |
| T8 Real person, end to end | `eval.py checks ... --experience <Q9>`, `eval.py duf ... --pdf OUT.pdf`, `eval.py pdf OUT.pdf brief.md` and, on the run's transcript, `eval.py battery <transcript> --depth <Q5> --brief OUT.pdf` (C21) exit 0; `curl -sIL` on every ledger link returns < 400 | not run | | |

Notes on the 2026-10-17 runs (3.1.0 after the trim pass): the harness gave the saved setup file by path in the prompt (a fictional target, no real prospect; `HOME` cannot be moved without losing the login), set `TALYX_PDF_CHROME` to the headless shell, and capped turns. A fifth run started at Stage 4 from the fixture records (host-tests/H4-stage4.jsonl): the skill loaded references/brief.md and references/checks.md, wrote fields.json, assembled, and rendered `2026-10-17-jane-doe-intelligence-brief.pdf`; `eval.py pdf`, `render` and `checks --plain` on that PDF exit 0 (3 pages). T2, T4, T5, T7 and T8 were not run: T8 needs a real person and no lookup on a real prospect was authorised. The popup question tool (AskUserQuestion) was not available in `claude -p`, so the native-popup path is not exercised here; the interactive run is still open.
