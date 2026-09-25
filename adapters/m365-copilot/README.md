# Talyx Pre-call Prep -- Microsoft 365 Copilot agent

Requires a Microsoft 365 work tenant with Agent Builder (not consumer Copilot or GitHub Copilot).

1. In Microsoft 365 Copilot choose **New agent → Skip to configure**. Name it **Talyx Pre-call Prep**.
2. Paste all of [agent-instructions.txt](agent-instructions.txt) into **Instructions**.
3. Under **Knowledge → Upload**, add [pcp-knowledge.md](pcp-knowledge.md). Allow web search. **Create**.
4. Ask "Prep me for my call with <Full Name> at <Organisation>." The first time it asks the calibration
   questions and gives you a *Saved setup* block.
5. Paste that block over the one at the end of your copy of `pcp-knowledge.md` and replace the
   Knowledge file. New chats then skip calibration.

[Microsoft: add knowledge to an agent](https://learn.microsoft.com/en-us/microsoft-365/copilot/extensibility/agent-builder-add-knowledge)

Status: not yet run in Copilot. Check that a new chat recalls the pasted setup and asks nothing.
