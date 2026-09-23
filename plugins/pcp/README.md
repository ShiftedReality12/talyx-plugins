# /pcp: pre-call prep for Claude Code

A free Claude Code plug-in from [Talyx AI](https://talyx.ai) for wealth advisors and professional-services firms. Type `/pcp` before a meeting and get a structured pre-call brief on the person you are about to meet, built from public sources, with every fact sourced.

## What it does

1. **Intake.** Give it a name and an organisation, or a CSV of up to 8 people. It asks for the meeting objective if you have not given one.
2. **Public-source research.** Four passes per person: identity, the links you supplied, the organisation's recent news, and the person's own words. Every fact is tagged with its source. If two people share the name, it stops and asks.
3. **A structured pre-call brief.** Ten sections: header, snapshot, strategic read, opening, discovery questions, their situation framed, value and next step, guardrails, a follow-up note draft, and a source log. Every brief passes eight quality checks before hand-over.

Briefs are saved as Markdown in `./pcp-briefs/`. Nothing is invented: facts that could not be confirmed are marked `[UNVERIFIED]` or left out.

## Install

In Claude Code, add the Talyx marketplace, then install the plug-in:

```
/plugin marketplace add talyx-ai/talyx-plugins
/plugin install pcp@talyx
```

The marketplace lives at https://github.com/talyx-ai/talyx-plugins.

## Use

```
/pcp "Full Name, Organisation"
/pcp path/to/intake.csv
/pcp
```

With no argument, `/pcp` asks for the intake fields. The CSV layout is in `skills/pre-call-prep/assets/intake-template.csv`.

## Good to know

- Public sources only. It never asks for logins or private data.
- The brief is preparation material, not advice. If you work in a regulated firm, follow your firm's review policy before using any of it with a client.
- It leaves personal topics that do not belong in a first meeting out of the brief, and says so.

## Licence

Free to use, for you and your organisation. You may not sell it or redistribute it for a fee. Copyright Talyx AI; Talyx AI retains all intellectual property. Briefs you create with it are yours. Full terms in [LICENSE](LICENSE).

## About Talyx AI

Talyx builds intelligence that business depends on: compounding intelligence for advisors and professional-services firms, so every meeting starts with an information advantage. /pcp is one small, free example of that method. Learn more at https://talyx.ai.
