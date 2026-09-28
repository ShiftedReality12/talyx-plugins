# Talyx Pre-call Prep (`pcp`)

A free plug-in from [Talyx AI](https://talyx.ai) for advisors and professional-services firms. Name the
person, company or deal you are about to meet and get **one 3-page PDF**: a 2-page brief and a 1-page
meeting script, built from public sources, every fact cited.

## Install

### Claude desktop (Cowork)

1. Open **Customize** in the sidebar, then **Plugins**.
2. Select **Add marketplace** and enter `talyx-ai/talyx-plugins`.
3. Find **pcp** and select **Install**.

For the whole firm (Team or Enterprise), an Owner adds it once: **Organization settings > Plugins & skills >
Marketplaces > Add plugins > Sync from GitHub**, then sets **pcp** to *Installed by default* or *Required*.
Claude syncs only private or internal repositories for an organization, so sync a private copy of this one.

### ChatGPT (desktop app)

1. Open **Plugins** in the sidebar, select the arrow next to **Create**, then **Add marketplace**.
2. Enter `talyx-ai/talyx-plugins` as the source, ref `main`, and select **Add marketplace**.
3. Find **Talyx Pre-call Prep** and install it. Start a new chat.

For the whole workspace, an admin imports it once: **Admin > Plugins > Add > Import marketplace**, source
`https://github.com/talyx-ai/talyx-plugins`, **Path** empty, then sets the installation policy.

Use it from the desktop app: the PDF is made on your computer.

### Every other host

| Host | Install | Checked |
|---|---|---|
| Claude Code | `/plugin marketplace add talyx-ai/talyx-plugins`, then `/plugin install pcp@talyx` | installed; full run to the PDF |
| Codex | `codex plugin marketplace add talyx-ai/talyx-plugins`, then `codex plugin add pcp@talyx` | installed; both skills found |
| Gemini (Antigravity CLI) | `agy plugin install https://github.com/talyx-ai/talyx-plugins` | validated and installed |
| Gemini CLI (Code Assist plans) | `gemini extensions install https://github.com/talyx-ai/talyx-plugins` | validated; both skills found |
| Grok | `grok plugin install talyx-ai/talyx-plugins --trust` | installed |
| Cursor | add this repository as a team marketplace, or clone it to `~/.cursor/plugins/local/pcp` | not yet run in Cursor |
| Devin | `devin plugins install talyx-ai/talyx-plugins` | not yet run in Devin |
| Perplexity | download [`adapters/perplexity/pcp.zip`](adapters/perplexity/pcp.zip) and upload it as a skill | not yet run in Perplexity |
| Gemini app (Gem), Microsoft 365 Copilot | paste two files; no scripts, so no PDF: see [adapters/chat](adapters/chat) | not yet run there |

Claude desktop and ChatGPT follow each vendor's published steps and have not yet been run end to end.

## Use

Ask: *"Prep me for my call with Jane Doe at Acme Capital."* To call it by name: `/pcp:pcp` in Claude,
`$pcp` in ChatGPT and Codex, `/pcp` in Cursor and Grok.

```text
/pcp "Full Name, Organisation"
/pcp path/to/intake.csv
/pcp --recalibrate
```

The first time, it asks eight quick setup questions. The first PDF on a computer needs Playwright,
Chromium and pypdf; it asks before installing them.

## What it does

0. **Calibrates once.** Eight questions: your role, domain, target kind, meeting shape, depth, social
   scope, jurisdiction and your offer. Saved in `~/.pcp/profile.yaml` and never asked again unless you
   pass `--recalibrate`.
1. **Intake.** A name and an organisation, or a CSV of up to 8 rows.
2. **Collects.** Up to 12 public source families and a coverage ledger: what was tried, found and
   failed. Excluded topics are dropped before anything is written.
3. **Reads behaviour.** Six dimensions, each scored only from cited observations.
4. **Renders the PDF.** Pages 1-2 brief, page 3 script. It fails rather than spill onto a fourth page.
5. **Debrief.** Four fields after the call.

Public professional record only; see the exclusions in `skills/pcp/pcp.yaml`.

## Your saved setup

| Host | Saved setup |
|---|---|
| Claude Code, Codex, Grok, Cursor, Gemini, Devin | saved on the first run and reused (Codex may ask to approve the write outside its sandbox) |
| Claude desktop (Cowork), ChatGPT, Perplexity | saved if the host keeps your home folder between sessions; if not, the questions come back |
| Gemini app (Gem), Microsoft 365 Copilot | no files: the assistant gives you a *Saved setup* block to paste into the knowledge file |

## Where each host's adapter lives

The repository root is the plug-in; each host reads its own file.

| Host | Files |
|---|---|
| Claude desktop, Claude Code | `.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json` |
| ChatGPT, Codex | `.codex-plugin/plugin.json`, `.agents/plugins/marketplace.json`, `skills/*/agents/openai.yaml` |
| Gemini (Antigravity), any Agent Plugins host | `plugin.json` |
| Gemini CLI | `gemini-extension.json` |
| Grok | `.grok-plugin/plugin.json` |
| Cursor | `.cursor-plugin/plugin.json`, `.cursor-plugin/marketplace.json` |
| Devin | `.devin-plugin/plugin.json` |
| Perplexity | `adapters/perplexity/pcp.zip` |
| Gemini app, Microsoft 365 Copilot | `adapters/chat/` |

Every host runs the same two skills: `skills/pcp` (the entry point) and `skills/talyx-pdf` (the PDF renderer).

## Maintainers

Two sources; everything else is generated, and `--check` fails on any hand edit.

- `build/plugin.source.json`: name, version, author, catalogs, the ChatGPT/Codex presentation, the skill list.
- `skills/pcp/pcp.yaml`: questions, stages, source families, rubric, page budget, checks.

```text
python3 build/generate.py                   # write every host file
python3 build/generate.py --check           # exit 1 on drift or a portability problem
python3 -m pip install -r tests/requirements.txt
python3 -m unittest discover -s tests       # packaging and portability tests
python3 evals/pcp_eval.py self-test         # the counter is proven able to fail
python3 evals/pcp_eval.py ratchet           # frozen targets hold their floors
```

## Licence

Free to use under the terms in [LICENSE](LICENSE). Talyx AI keeps all rights in the plug-in.
