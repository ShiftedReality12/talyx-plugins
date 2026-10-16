# Talyx Pre-call Prep for the Grok app

The Grok app takes instructions plus files. It is not known to run the plug-in's scripts in a Project (untested), so
this is the same reduced `/pcp` as the [chat hosts](../chat/README.md):

- **No PDF.** The brief and script come back in the chat as text, labelled as not the Talyx PDF.
- **Checks are self-applied** by the assistant, not run as code, and it says so.
- **Saved setup is a block you paste** at the end of `pcp-knowledge.md`, as for the chat hosts.

Both files are generated from `plugins/pcp/pcp.yaml` by `build/adapters.py`. Do not edit them by hand.

| File | Where it goes |
|---|---|
| [instructions.txt](instructions.txt) | the Project's **Instructions** |
| [pcp-knowledge.md](pcp-knowledge.md) | a file in the Project's **files** |

## Setup

1. In the Grok app or at grok.com, make a new **Project**. Name it **Talyx Pre-call Prep**.
2. Paste all of `instructions.txt` into the Project's instructions. Add `pcp-knowledge.md` to its files.
3. In a chat inside the Project, ask "Prep me for my call with <Full Name> at <Organisation>." The first
   time it asks the setup questions and gives you a *Saved setup* block.
4. Paste that block over the one at the end of your copy of `pcp-knowledge.md` and replace the file in
   the Project. New chats then skip setup.

Status: prepared to the Project setup described above; not yet run in the Grok app.
