# Talyx Pre-call Prep for chat hosts (Gemini Gem, Microsoft 365 Copilot)

These hosts take instructions plus a knowledge file and run no scripts, so this is a reduced `/pcp`:

- **No PDF.** The brief and script come back as one document, labelled as not the Talyx PDF.
- **Checks are self-applied** by the assistant, not run as code, and it says so.
- **Saved setup is a block you paste.** After calibration the assistant gives you an updated *Saved
  setup* block. Replace the block at the end of your copy of `pcp-knowledge.md` and re-upload it; the
  next chat then asks nothing.

Both files are generated from `plugins/pcp/skills/pre-call-prep/pcp.yaml` by `build/generate.py`.
Do not edit them by hand.

| File | Where it goes |
|---|---|
| [instructions.txt](instructions.txt) | the Gem's **Instructions** / the agent's **Instructions** |
| [pcp-knowledge.md](pcp-knowledge.md) | the Gem's **Knowledge** / the agent's **Knowledge** |

## Gemini Apps (Gem)

1. In a computer browser open `gemini.google.com` → **Gems** → **New Gem**. Name it **Talyx Pre-call Prep**.
2. Paste all of `instructions.txt` into **Instructions**. Under **Knowledge**, upload `pcp-knowledge.md`. **Save**.
3. Ask "Prep me for my call with <Full Name> at <Organisation>." The first time it asks the calibration
   questions and gives you a *Saved setup* block.
4. Paste that block over the one at the end of your copy of `pcp-knowledge.md`, replace the Knowledge
   file in the Gem, and save. New chats then skip calibration.

[Google: use Gems](https://support.google.com/gemini/answer/15146780) ·
[Google: add files to a Gem](https://support.google.com/gemini/answer/15235603)

## Microsoft 365 Copilot agent

Requires a Microsoft 365 work tenant with Agent Builder (not consumer Copilot or GitHub Copilot).

1. In Microsoft 365 Copilot choose **New agent → Skip to configure**. Name it **Talyx Pre-call Prep**.
2. Paste all of `instructions.txt` into **Instructions**. Under **Knowledge → Upload**, add
   `pcp-knowledge.md`. Allow web search. **Create**.
3. Ask "Prep me for my call with <Full Name> at <Organisation>." The first time it asks the calibration
   questions and gives you a *Saved setup* block.
4. Paste that block over the one at the end of your copy of `pcp-knowledge.md` and replace the
   Knowledge file. New chats then skip calibration.

[Microsoft: add knowledge to an agent](https://learn.microsoft.com/en-us/microsoft-365/copilot/extensibility/agent-builder-add-knowledge)

Status: prepared to each host's documented setup; not yet run in either host. Check that a new chat
recalls the pasted setup and asks nothing.
