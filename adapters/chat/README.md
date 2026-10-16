# Talyx Pre-call Prep for chat hosts (Gemini Gem, Microsoft 365 Copilot)

These hosts take instructions plus a knowledge file and run no scripts, so this is a reduced `/pcp`:

- **No PDF.** The brief and script come back as one document, labelled as not the Talyx PDF.
- **Checks are self-applied** by the assistant, not run as code, and it says so.
- **Saved setup is a block you paste.** After calibration the assistant gives you an updated *Saved
  setup* block. Replace the block at the end of your copy of `pcp-knowledge.md` and re-upload it; the
  next chat then asks nothing.

Both files are generated from `plugins/pcp/pcp.yaml` by `build/adapters.py`.
Do not edit them by hand.

| File | Where it goes |
|---|---|
| [instructions.txt](instructions.txt) | the Gem's **Instructions** / the agent's **Instructions** |
| [pcp-knowledge.md](pcp-knowledge.md) | the Gem's **Knowledge** |
| [pcp-knowledge.txt](pcp-knowledge.txt) | the Copilot agent's **Knowledge** (Copilot takes .txt, not .md; same text) |

## Gemini Apps (Gem)

1. In a computer browser open `gemini.google.com` → **Gems** → **New Gem** (if you have never made a Gem, open
   **Settings and help** first). Name it **Talyx Pre-call Prep**.
2. Paste all of `instructions.txt` into **Instructions**. Under **Knowledge**, upload `pcp-knowledge.md`. **Save**.
3. Ask "Prep me for my call with <Full Name> at <Organisation>." The first time it asks the calibration
   questions and gives you a *Saved setup* block.
4. Paste that block over the one at the end of your copy of `pcp-knowledge.md`, replace the Knowledge
   file in the Gem, and save. New chats then skip calibration.

Google is moving Gems to skills: from November 2026 on personal accounts, from March 2027 on Workspace business
accounts. Check this setup again after the move.

[Google: use Gems](https://support.google.com/gemini/answer/15146780) ·
[Google: add files to a Gem](https://support.google.com/gemini/answer/15235603)

## Microsoft 365 Copilot agent

Requires a Microsoft 365 work tenant with Agent Builder (not consumer Copilot or GitHub Copilot), and a Microsoft 365
Copilot licence or usage billing for the file upload.

1. In Microsoft 365 Copilot choose **New agent → Skip to configure**. Name it **Talyx Pre-call Prep**.
2. Paste all of `instructions.txt` into **Instructions**. Under **Knowledge → Upload**, add
   `pcp-knowledge.txt`. Under **Knowledge**, turn on **Search all websites** and leave **Only use specified
   sources** off. **Create**. (If an admin has turned web search off, the agent answers without searching and
   shows no error: the brief then says what it could not find.)
3. Ask "Prep me for my call with <Full Name> at <Organisation>." The first time it asks the calibration
   questions and gives you a *Saved setup* block.
4. Paste that block over the one at the end of your copy of `pcp-knowledge.txt` and replace the
   Knowledge file. New chats then skip calibration.

[Microsoft: add knowledge to an agent](https://learn.microsoft.com/en-us/microsoft-365/copilot/extensibility/agent-builder-add-knowledge)

Status: prepared to each host's documented setup; not yet run in either host. Check that a new chat
recalls the pasted setup and asks nothing.
