# Chat-host adaptations

Gemini Apps (Gems) and Microsoft 365 Copilot agents take instructions plus a knowledge file. They run no
scripts, so this is a reduced version of `/pcp`:

- **No PDF.** The brief and script come back as one document, labelled as not the Talyx PDF.
- **Checks are self-applied** by the assistant, not run as code, and it says so.
- **Saved setup is a block you paste.** After calibration the assistant gives you an updated
  *Saved setup* block. Replace the block at the end of your copy of `pcp-knowledge.md` and re-upload it;
  the next chat then asks nothing.

Both files in each folder are generated from `plugins/pcp/skills/pre-call-prep/pcp.yaml` by
`build/generate.py`. Do not edit them by hand.

- [Gemini Apps (Gem)](gemini/README.md)
- [Microsoft 365 Copilot](m365-copilot/README.md)

Status: prepared to each host's documented setup; not yet run in either host.
