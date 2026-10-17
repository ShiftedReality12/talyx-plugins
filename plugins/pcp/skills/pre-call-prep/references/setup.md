<!-- GENERATED from pcp.yaml (sha256:1df3c742667e) by render_skill.py -- edit pcp.yaml, never this file -->

# Setup, intake and how PCP thinks

Loaded by Stage 0 of SKILL.md.

## How PCP thinks (never in the output)

- Work the intelligence cycle: direction (setup and the meeting objective) -> collection -> processing (each fact gets a source, tag, grade and date; excluded topics are dropped) -> analysis -> the Intelligence Brief -> feedback (the debrief).
- Collection is public-source OSINT (and SOCMINT for the person's public social footprint): first each source type's own query (the base pass), then open sources found by targeted web search in rounds, each refined from the last (osint), the person's public social footprint, LinkedIn only as its public search results show it (never a browser session), and the user's own files and answers (a LinkedIn profile they save is one).
- Behavioral profile is human-source analysis from public evidence: each row is a cited observation and the caller's move. It never labels the person's character.
- Keep what was read apart from what was inferred (the grade). Check the one assumption the Take rests on (Strongest case against). On deep runs, weigh competing explanations of what they want.

## Setup questions

| # | Chip | Question | Options: label [value]: description | Sets | Used by |
|---|---|---|---|---|---|
| Q1 | Your role | Who is making the call? | 1. Founder / principal (Recommended) [principal]: You own the relationship and the offer. · 2. Sales / BD [sales]: You open and advance deals for your firm. · 3. Advisor / relationship manager [advisor]: Wealth, legal, accounting or other professional advisor. · 4. Investor / allocator [investor]: You deploy capital or diligence managers. | caller.role: value; caller.authority_level: principal->high, sales->medium, advisor->medium, investor->high | script.influence_depth, brief.value_next_step |
| Q2 | Domain | Where do your targets mostly live? | 1. General professional (Recommended) [general]: No domain assumptions; broadest source set. · 2. Wealth management [wealth]: Advisors, RIAs, family offices; adds BrokerCheck/IAPD registers. · 3. Private equity / VC [pe]: GPs, LPs, portfolio companies; adds fund/portfolio news families. · 4. Enterprise / SaaS [saas]: Buyers and champions in technology companies. | domain: value | families.registers, brief.vocab, guardrails.forbidden_claims |
| Q3 | Target kind | Who do you usually prep for? | 1. A person (Recommended) [person]: One named counterpart. · 2. A company or team [company]: An account; people come second. · 3. A deal or transaction [deal]: A live process with several parties. · 4. Mixed [mixed]: Decide per run from the intake. | target.kind_default: value | families.enabled_by_kind |
| Q4 | Meeting | What is the typical call? | 1. First intro (cold or warm) (Recommended) [intro]: Earn the second meeting. · 2. Discovery / qualification [discovery]: Learn enough to decide fit. · 3. Pitch / close [close]: Move to a decision. · 4. Relationship / renewal [relationship]: Deepen an existing relationship. | meeting.format_default: value | script.beats, brief.discovery_questions.mix |
| Q5 | Depth | Research depth versus speed? | 1. Standard -- 12 source types, about 8 minutes (Recommended) [standard]: Full public footprint, counter-evidence pass on. · 2. Fast -- 6 source types, about 3 minutes [fast]: Identity, org, voice, news, registers, social. No counter-evidence. · 3. Deep -- every source type + what they may want [deep]: Adds what they may want from the meeting, and a second pass on their network. | research.depth: value | families.enabled_by_depth, research.full_threshold, rubric.ach |
| Q6 | Social | Public social footprint -- how far? | 1. Professional only (Recommended) [professional]: Public bios, talks, podcasts, and LinkedIn as public search results show it. Never your browser or your account. · 2. Plus public X / Bluesky / Substack [social]: Public posts on open networks only. · 3. None [none]: No social sources at all. | socmint.scope: value | families.socmint |
| Q7 | Compliance | Jurisdiction and compliance posture? | 1. US (Recommended) [us]: Public professional record; standard exclusions. · 2. UK / EU (GDPR strict) [eu]: Adds minimisation -- claims.jsonl deleted after render. · 3. Regulated sales (FINRA / FCA style) [regulated]: Adds performance-claim and promissory-language guardrails. · 4. APAC [apac]: Standard exclusions; formal-register openers. | jurisdiction: value | exclusions, guardrails.never_say, retention |
| Q9 | Experience | How long have you been running meetings like this? | 1. Experienced (Recommended) [experienced]: The moves, without coaching. · 2. Newer -- under two years [new]: Each move on page 3 comes with a one-line why. · 3. Top producer [top]: The shortest lines; you adapt in the room. | caller.experience: value | script.why_lines, script.say_aloud_words |
| Q8 | Your offer | In one line -- what do you offer, and what does a win in this meeting look like? If you have files about your business (a deck, a one-page summary, case studies -- PDF, Word, Markdown, text or CSV), add their paths and PCP will use them. (free text) | free text | caller.offer_one_line: text; meeting.win_definition: text; context.files: paths | checks.swap_test, eval.duf_binding, brief.B9 |

## Asking questions

When a question is needed -- of the user, or for the room -- read `references/socratic-questions.md` first.
Ask with the host's native popup question tool: `AskUserQuestion` in Claude Code and Claude Cowork; the structured question tool in ChatGPT, Codex and Grok (request_user_input and its equivalents). First option recommended. Whichever way you ask, say it in one line of the reply before the call ('Two quick questions: answer in the popup, or skip and I'll use the recommended answers.'), then stop. Do no search, page open or file work until the user's next message or the tool's answer. Setup questions: a skip takes the recommended option, stored defaulted. A question from a trigger below: a skip means go on without the answer, and the gap stays Not determined. Ask each question once.

## Rules moved out of SKILL.md

The full text of the rows SKILL.md summarises; the rule is this text.

- **CAL-5** Questions use the host's native popup question tool (AskUserQuestion in Claude Code and Cowork; the structured question tool in ChatGPT, Codex and Grok): setup in calls of four, first option recommended, and every Socratic question the same way. A typed numbered list is the fallback only for a host with no such tool, or after a tool call that came back with no answer. Say in one line of the reply that you are asking and what skip does, then stop until the answer or the user's next message; do no research meanwhile. The saved offer (Q8) and domain (Q2) are checked against what the user asks for in this run: when the request names a different business, offer or domain, ask which to use before any search (the offer-conflict trigger, S1-4); use the answer for this run only unless the user says to change the saved one; on skip, use the saved one and say so in the Coverage row.

## Intake

Intake columns (assets/intake-template.csv) and what each sets:

| Column | Sets |
|---|---|
| Full Name | {name} |
| Organisation | {org} |
| Title/Role | {title} |
| Meeting Date | meeting.date: the date P4's real deadline and the last-90-days window count from |
| Meeting Objective | meeting.objective |
| Relationship | known_context (F11, tag Yours) |
| Relationship Length | known_context (F11, tag Yours) |
| LinkedIn URL | linkedin.given: read once with the page fetch (S2-7); a failure goes to coverage.failed_urls |
| Organisation Website | {org_website} |
| Additional URL 1 | a page the user wants read: fetch it, one claim per fact, tag Direct |
| Additional URL 2 | a page the user wants read: fetch it, one claim per fact, tag Direct |
| Additional URL 3 | a page the user wants read: fetch it, one claim per fact, tag Direct |
| Known Priorities | known_context (F11, tag Yours) |
| Icebreaker Notes | known_context (F11, tag Yours) |
| Specific Ask | meeting.win_definition: B9's ask starts from it |
| Notes | known_context (F11, tag Yours) |

