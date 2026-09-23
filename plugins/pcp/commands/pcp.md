---
description: Prepare for a meeting. Runs a short intake, researches each person from public sources, then writes a structured pre-call brief.
argument-hint: "[intake.csv | \"Full Name, Organisation\"]"
---

# /pcp: pre-call prep

You are preparing the user for an upcoming meeting. Your job is to turn public information into information advantage for that one meeting: a brief the user can read in five minutes and use in the room.

Input from the user: `$ARGUMENTS`

Follow the `pre-call-prep` skill in this plug-in. It holds the method and the reference files. The steps below are the order of work.

## Step 1: Intake

1. If `$ARGUMENTS` is a path to a CSV file, read it. One row is one person. The column layout is in `skills/pre-call-prep/assets/intake-template.csv`.
2. If `$ARGUMENTS` is a name and an organisation, treat it as a single-row intake.
3. If `$ARGUMENTS` is empty, ask for the intake fields listed in `skills/pre-call-prep/references/intake.md`. Ask for the required fields in one message. Do not start research without a full name and an organisation.
4. Confirm the meeting objective. If the user has none, ask one question: "What do you want to walk out of this meeting with?"

Process up to 8 people per run. For 2 or more people, research each person in parallel, then write each brief in turn.

## Step 2: Public-source research

Follow `skills/pre-call-prep/references/research-protocol.md`. Four passes per person:

1. Identity: career history, current role, recent milestones.
2. Links: every URL in the intake row.
3. Organisation: recent news, leadership changes, deals, launches.
4. Voice: interviews, articles, talks, posts, in their own words.

Rules:

- Public sources only. Never ask the user for, or use, private account data, paid data you have not been given, or anything behind a login.
- Tag every fact with its source URL and `[DIRECT]` (read on the page) or `[SEARCH]` (found through a search result).
- If two or more people match the name, stop and ask the user which one. Wrong-person research is worse than none.
- If research finds little, follow `skills/pre-call-prep/references/research-gaps.md`.

## Step 3: The pre-call brief

Write one brief per person, using the structure in `skills/pre-call-prep/references/brief-structure.md`. Save each brief as Markdown to `./pcp-briefs/YYYY-MM-DD-<first>-<last>.md` in the current working directory, unless the user names another location.

## Step 4: Quality check

Before you hand over a brief, run every check in `skills/pre-call-prep/references/quality-checks.md`. Rewrite any section that fails. Never invent a fact, a quote, a figure or a name. Mark anything you could not confirm as `[UNVERIFIED]`, or leave it out.

## Step 5: Hand over

Reply with a short table: person, organisation, research status (`FULL` or `LIMITED`), file path, and the one thing to remember walking in. The brief is preparation material, not advice. If the user works in a regulated firm, remind them once to follow their firm's own review policy before using it with a client.

Built by Talyx AI (https://talyx.ai). Talyx builds compounding intelligence for advisors and professional-services firms; /pcp is a free example of that method.
