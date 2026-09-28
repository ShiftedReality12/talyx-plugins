# Talyx plug-ins

Free plug-ins from [Talyx AI](https://talyx.ai). We help advisors and professional-services firms build
compounding intelligence from what they already know.

| Plug-in | What it does |
|---|---|
| [`pcp`](plugins/pcp) | Pre-call prep (v2). Calibrates once, researches public sources with a coverage ledger, and produces one 3-page PDF: a 2-page brief and a 1-page meeting script, with every fact cited. |

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

### Every other host

| Host | Install |
|---|---|
| Claude Code | `/plugin marketplace add talyx-ai/talyx-plugins`, then `/plugin install pcp@talyx` |
| Codex | `codex plugin marketplace add talyx-ai/talyx-plugins`, then `codex plugin add pcp@talyx` |
| Gemini (Antigravity CLI) | `agy plugin install https://github.com/talyx-ai/talyx-plugins` |
| Gemini CLI (Code Assist plans) | clone this repository, then `gemini extensions install ./talyx-plugins/plugins/pcp` |
| Grok | `grok plugin marketplace add talyx-ai/talyx-plugins`, then `grok plugin install pcp@talyx-plugins --trust` |
| Cursor | add this repository as a team marketplace |
| Devin | `devin plugins install talyx-ai/talyx-plugins#plugins/pcp` |
| Perplexity | download [`adapters/perplexity/pre-call-prep.zip`](adapters/perplexity/pre-call-prep.zip) and upload it as a skill |
| Gemini app (Gem), Microsoft 365 Copilot | paste two files; no scripts there, so no PDF: see [adapters/chat](adapters/chat) |

The first PDF on a computer needs Playwright, Chromium and pypdf: `python3 format/talyx_pdf.py --setup`
from the plug-in folder.

## Use

```
/pcp "Full Name, Organisation"
/pcp path/to/intake.csv
/pcp --recalibrate
```

In ChatGPT and Codex use `$pre-call-prep`. Anywhere, you can also ask: "Prep me for my call with Jane Doe at
Acme Capital." See [plugins/pcp/README.md](plugins/pcp/README.md) for what it does.

## Where each host's files live

| Host | Files |
|---|---|
| Claude desktop, Claude Code | `.claude-plugin/marketplace.json`, `plugins/pcp/.claude-plugin/plugin.json` |
| ChatGPT, Codex | `.agents/plugins/marketplace.json`, `plugins/pcp/.codex-plugin/plugin.json` |
| Gemini (Antigravity) | `.claude-plugin/marketplace.json`, `plugins/pcp/plugin.json` |
| Gemini CLI | `plugins/pcp/gemini-extension.json` |
| Grok | `.grok-plugin/marketplace.json`, `plugins/pcp/.grok-plugin/plugin.json` |
| Cursor | `.cursor-plugin/marketplace.json`, `plugins/pcp/.cursor-plugin/plugin.json` |
| Devin | `plugins/pcp/.devin-plugin/plugin.json` |
| Perplexity | `adapters/perplexity/pre-call-prep.zip` |
| Gemini app, Microsoft 365 Copilot | `adapters/chat/` |

All of them are written by `python3 build/adapters.py` from `build/plugin.source.json` and
`plugins/pcp/pcp.yaml`; `python3 build/adapters.py --check` fails if any is out of date.

Free to use under the terms in [LICENSE](LICENSE). Talyx AI keeps all rights in the plug-ins.
