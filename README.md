# Talyx plug-ins

Free plug-ins from [Talyx AI](https://talyx.ai). We help advisors and professional-services firms build
compounding intelligence from what they already know.

| Plug-in | What it does |
|---|---|
| [`pcp`](plugins/pcp) | Pre-call prep. Calibrates once per user, researches public sources with a coverage ledger, and produces one 3-page PDF: a 2-page brief and a 1-page meeting script, with every fact cited. |

## Install

One repository serves every host; each host reads its own catalog or manifest.

| Host | Install | Status |
|---|---|---|
| Claude Code | `/plugin marketplace add talyx-ai/talyx-plugins` then `/plugin install pcp@talyx` | verified: install + live run |
| Claude desktop (Cowork) | Customize → Plugins → Add marketplace → *Add from a repository* → `https://github.com/talyx-ai/talyx-plugins` → install **pcp** | not yet verified |
| Codex CLI | `codex plugin marketplace add talyx-ai/talyx-plugins` then `codex plugin add pcp@talyx` | verified: install + skill discovery |
| ChatGPT desktop (Work locally) | Plugins → Add → Add a marketplace → paste the repository address → install **pcp** | not yet verified |
| Grok Build | `grok plugin marketplace add talyx-ai/talyx-plugins`, then `grok plugin install pcp@<marketplace> --trust` (`grok plugin marketplace list` shows the name) | verified: install |
| Cursor | Team marketplace from this repository, or copy `plugins/pcp` to `~/.cursor/plugins/local/pcp` | not yet verified |
| Gemini CLI | clone, then `gemini extensions install ./plugins/pcp` | not yet verified |
| Devin | `devin plugins install talyx-ai/talyx-plugins#plugins/pcp` | not yet verified |
| Perplexity | upload `dist/perplexity/pre-call-prep.zip` (built by `build/generate.py`) | not yet verified |
| Gemini Apps (Gem), Microsoft 365 Copilot | chat adaptations without scripts or PDF: see [adapters/](adapters) | not yet verified |

"Verified" means installed through that host's own CLI and exercised. Every other row is generated to
the host's published contract and still needs a run in that host. See [plugins/pcp/README.md](plugins/pcp/README.md)
for use, the saved setup and per-host limits.

## Repository layout

```text
.claude-plugin/marketplace.json   Claude Code / Cowork catalog (Codex, Grok and Devin also read it)
.agents/plugins/marketplace.json  Codex + ChatGPT catalog
.cursor-plugin/marketplace.json   Cursor catalog
plugins/pcp/                      the installable plug-in -- the only folder a host installs
  plugin.json                     Agent Plugins 1.0.0 manifest (+ OpenAI interface)
  .claude-plugin/ .cursor-plugin/ gemini-extension.json   host manifests
  commands/pcp.md, pcp.toml       /pcp (Markdown for Claude/Cursor/Grok, TOML for Gemini)
  skills/pre-call-prep/           self-contained skill: SKILL.md, pcp.yaml, scripts/, assets/
  skills/talyx-pdf/               self-contained Markdown -> PDF skill
adapters/                         Gemini Gem + Microsoft 365 Copilot instructions and knowledge file
build/                            plugin.source.json + generate.py, the shared renderer, schemas
evals/                            maintainer instrument: controls, frozen targets, ratchet
tests/                            packaging, portability and saved-setup tests
```

## Maintainers

Two sources; everything else is generated.

- `build/plugin.source.json` -- name, version, author, catalogs, the OpenAI interface, the skill list.
- `plugins/pcp/skills/pre-call-prep/pcp.yaml` -- questions, stages, source families, rubric, page budget, checks.

```text
python3 build/generate.py                   # write every host file, check skills, build dist/ ZIPs
python3 build/generate.py --check           # exit 1 on any drift or portability problem
python3 -m pip install -r tests/requirements.txt
python3 -m unittest discover -s tests       # packaging, portability, profile writer
python3 evals/pcp_eval.py self-test         # the counter is proven able to fail
python3 evals/pcp_eval.py ratchet           # frozen targets hold their floors
```

A hand edit to a generated file fails `--check`. The build refuses a skill that reads above its own
folder, uses a Claude-only variable, names a machine path, references a script it does not ship, or
has frontmatter that is not valid YAML at the top of the file.

Free to use under the terms in [LICENSE](LICENSE). Talyx AI keeps all rights in the plug-ins.
