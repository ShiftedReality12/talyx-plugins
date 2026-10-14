---
name: pre-call-prep
description: >
  Prepare for an upcoming meeting with a named person, company or deal. A few one-time setup
  questions, research from public sources (plus LinkedIn through your browser and your own files, when
  you allow it), and ONE 3-page PDF: a 2-page Intelligence Brief and a 1-page meeting script, every fact
  cited. Use when the user mentions pre-call prep, meeting prep, call preparation, researching someone
  before a meeting, talking points, or shares an intake list. Do not use for general research unrelated
  to a meeting, or for notes on a meeting that has already happened.
---
<!-- GENERATED from pcp.yaml (sha256:d8247d8141b9) by render_skill.py -- edit pcp.yaml, never this file -->

# Pre-call prep (v3.1.0)

Stages, dependency-ordered: **setup once -> intake -> intelligence collection -> meeting approach -> Intelligence Brief -> debrief.**
Every stage declares its inputs before its behaviour, reads only its listed context, and follows rows
that each carry a falsification test. Every fact traces to a source. Nothing is invented.
The deliverable is one 3-page PDF, the Intelligence Brief. Nothing else is emitted.

## How PCP thinks (never in the output)

- Work the intelligence cycle: direction (setup and the meeting objective) -> collection -> processing (each fact gets a source, tag, grade and date; excluded topics are dropped) -> analysis -> the Intelligence Brief -> feedback (the debrief).
- Collection is open sources, the person's public social footprint, LinkedIn through the user's own session with permission, and the user's own files and answers.
- Meeting approach is human-source analysis from public evidence: each row is a cited observation and the caller's move. It never labels the person's character.
- Keep what was read apart from what was inferred (the grade). Check the one assumption the Take rests on (Strongest case against). On deep runs, weigh competing explanations of what they want.

**Plain words.** Nothing the user reads -- the PDF, replies, setup questions, the listing -- uses military, intelligence-trade or technical jargon. Their own quoted words are exempt. Never write a word banned: OSINT, SOCINT, SOCMINT, HUMINT, human intelligence, SIGINT, intelligence cycle, tradecraft, collection plan, competing hypotheses, ACH, target package, asset, source handling, exploitation, debrief, kill chain, dossier, duf_pp, claims.jsonl, read.json, source families, scrape, scraped, scraping, crawl, LLM, or an internal id
(C1-C4, F1-F12, row ids). Allowed only inside these phrases: asset manager, asset managers, asset management, asset & wealth management, asset and wealth management, asset class, asset classes, asset allocation, asset owner, asset owners, asset-light, asset-heavy, asset-backed, asset-based, asset-liability, asset and liability, asset base, asset quality, asset growth, asset mix, asset value, asset values, net asset value, asset price, asset prices, asset sale, asset sales, asset purchase, asset purchases, asset deal, asset finance, asset servicing, asset gathering, real asset, alternative asset, digital asset, fixed asset, financial asset, hard asset, single-asset, multi-asset.
Use "source types", not families; "the person you're meeting", not target. Call the deliverable the Intelligence Brief, nothing else.

## Stage 0: Setup (once)

Read `~/.pcp/profile.yaml`. Ask only the questions it has no answer for -- all of them the first time
or with `--recalibrate` -- using the host's question form (`AskUserQuestion` in Claude; else one chat
message with numbered options), first option recommended, in these calls: Q1+Q2+Q3+Q4 · Q5+Q6+Q7+Q9 · Q8 (free text). Then write the profile
(`pcp_profile_format: 1`, answers under `profiles: <name>: answers: Qn: {value, defaulted}`, plus `context`
and `linkedin` when set) and continue.

| # | Chip | Question | Options | Sets |
|---|---|---|---|---|
| Q1 | Your role | Who is making the call? | Founder / principal (Recommended) / Sales / BD / Advisor / relationship manager / Investor / allocator | caller.role, caller.authority_level |
| Q2 | Domain | Where do your targets mostly live? | General professional (Recommended) / Wealth management / Private equity / VC / Enterprise / SaaS | domain |
| Q3 | Target kind | Who do you usually prep for? | A person (Recommended) / A company or team / A deal or transaction / Mixed | target.kind_default |
| Q4 | Meeting | What is the typical call? | First intro (cold or warm) (Recommended) / Discovery / qualification / Pitch / close / Relationship / renewal | meeting.format_default |
| Q5 | Depth | Research depth versus speed? | Standard -- 12 source types, about 8 minutes (Recommended) / Fast -- 6 source types, about 3 minutes / Deep -- every source type + what they may want | research.depth |
| Q6 | Social | Public social footprint -- how far? | Professional only (Recommended) / Plus public X / Bluesky / Substack / None | socmint.scope |
| Q7 | Compliance | Jurisdiction and compliance posture? | US (Recommended) / UK / EU (GDPR strict) / Regulated sales (FINRA / FCA style) / APAC | jurisdiction |
| Q9 | Experience | How long have you been running meetings like this? | Experienced (Recommended) / Newer -- under two years / Top producer | caller.experience |
| Q8 | Your offer | In one line -- what do you offer, and what does a win in this meeting look like? If you have files about your business (a deck, a one-page summary, case studies -- PDF, Word, Markdown, text or CSV), add their paths and PCP will use them. (free text) | free text | caller.offer_one_line, meeting.win_definition, context.files |

- **CAL-1** Ask only the questions with no saved answer in ~/.pcp/profile.yaml -- all of them the first time, all again with --recalibrate. Otherwise read it silently.  
  _Fails when:_ A profile with Q1-Q8 answered and no Q9 -- the run asks Q9 only. A complete profile -- it asks nothing.
- **CAL-2** A skipped answer takes the first (Recommended) option and is stored with defaulted:true; the masthead's Prepared for and Depth show the saved answers.  
  _Fails when:_ Skip Q5 -- profile shows research.depth standard, defaulted true; the masthead reads "Depth standard".
- **CAL-3** The improve loop may PROPOSE a profile change (one line, with the debrief evidence) but never applies one without a yes.  
  _Fails when:_ Three debriefs with facts_used > 80% must produce a proposal, and the profile must be unchanged until answered.
- **CAL-4** Files named in Q8 (or later with --context <path>) are read once; their paths and a summary of at most 150 words go in the profile under context. Facts taken from them are tagged Yours, never presented as public. Supported: .pdf .docx .md .txt .csv. Any other file gets one line naming the supported types, and the profile is left unchanged.  
  _Fails when:_ Give a one-page file -- the profile holds its path and summary, and a fact from it prints with tag Yours. Give a .pptx -- one line names the supported types and profile.yaml's sha256 is unchanged.

## Stage 1: Intake

**Input contract** (declared before behaviour):

| Input | Type | Source | Required | Fallback |
|---|---|---|---|---|
| `arguments` | path.csv | 'Full Name, Organisation' | empty | $ARGUMENTS | yes | ask the required intake fields in one message |
| `profile` | yaml | ~/.pcp/profile.yaml | yes | run calibration |
| `meeting.objective` | text | intake row or one question | yes | ask: What do you want to walk out of this meeting with? |
| `target.kind` | person|company|deal | intake or profile.target.kind_default | yes | person |

**Context contract** -- read, in this order: profile, intake row, this stage's rows, references/socratic-questions.md. Budget: 900 words. Not read: reference files of later stages, prior briefs.

**Rows:**

- **S1-1** Do not start research without a full name and an organisation.  
  _Fails when:_ Run with a name only -- the run must ask, not search.
- **S1-2** Two or more people match the name: stop and ask which one. Wrong-person research is worse than none.  
  _Fails when:_ Seed an ambiguous name -- the run must present the candidates and stop.
- **S1-3** Up to 8 targets per run; research targets in parallel, write briefs in turn.  
  _Fails when:_ A 9-row CSV must be refused with the count.
- **S1-4** Ask the user only as references/socratic-questions.md says: when a trigger fires, at most 2 questions after setup, in one message, each skippable.  
  _Fails when:_ An intake with an objective and no relationship -- the run asks nothing before collection.

## Stage 2: Intelligence collection

**Input contract** (declared before behaviour):

| Input | Type | Source | Required | Fallback |
|---|---|---|---|---|
| `resolved_families` | list | families filtered by profile (kind, depth, socmint) | yes | none -- derived |
| `exclusions` | list | exclusions.base + exclusions.by_jurisdiction[profile.jurisdiction] | yes | none -- derived |
| `known_context` | text | intake Notes column, the user's answers, profile.context and any file the user gives | no | empty |

**Context contract** -- read, in this order: resolved_families with query templates, exclusions, target identity, known_context. Budget: 1200 words. Not read: rubric, brief structure, script structure.

**Outputs:** `claims.jsonl` (id, claim, family, url, retrieved_at, tag, grade, confidence, exclusion_hit); `coverage` (families_attempted, families_total, hits_by_family, failed_urls, linkedin, status)

**Rows:**

- **S2-1** Public sources, plus what the user gives PCP: their files and answers (tag Yours) and their own LinkedIn session (S2-7). No paid data the user has not supplied, no scraping.  
  _Fails when:_ A run with no browser, no files and no answers holds only Direct and Search facts.
- **S2-2** Every claim carries url (or the file name, for Yours), retrieved_at, tag Direct|Search|LinkedIn|Yours, grade Measured|Derived|Inference|Not determined, and confidence C1 (primary, dated) | C2 (reputable secondary) | C3 (single weak source) | C4 (inferred).  
  _Fails when:_ A claim missing any field is dropped by eval.py duf and counted as dropped.
- **S2-3** A claim that hits an exclusion is dropped BEFORE the writer sees it and counted in coverage.excluded; the ledger's Left out on purpose row names the topic, never the fact.  
  _Fails when:_ Seed a claim tagged exclusion health -- it must not appear in any output file.
- **S2-4** Coverage is a required output: families_attempted/families_total and hits per family. A run without coverage is not a run.  
  _Fails when:_ Disable WebFetch -- coverage must show 0/N attempted and status LIMITED, never FULL.
- **S2-5** Status FULL requires >= 1 C1/C2 claim in >= research.full_threshold[depth] families; else LIMITED, stamped in the masthead.  
  _Fails when:_ Remove all C1/C2 claims from one family below threshold -- status flips to LIMITED.
- **S2-6** Run the counter-evidence family last: search for what would contradict the strategic read.  
  _Fails when:_ With depth standard or deep, coverage must show family F12 attempted.
- **S2-7** LinkedIn, up to 3 people per run. If the host has a browser or computer-use tool, ask each run, in one line: 'Open LinkedIn in your browser to read <name>'s profile? Read-only. LinkedIn's terms bar automated access and it can restrict your account; they may see you viewed them; the page text goes to your AI provider. Yes / No -- or save their profile as a PDF (More > Save to PDF) and give me the file.' With a yes: open the profile by URL (from the intake or a web search, never LinkedIn's own search), confirm the name and employer match, then read the profile and at most 10 public posts from the last 90 days -- 5 page loads at most. Never message, connect, follow, like or comment; never open Contact info or posts limited to connections; infer nothing from the photo. Stop at any login wall, security check or restriction notice, save linkedin: paused in the profile, and do not try again until the user says it is resolved. Facts read there are tagged LinkedIn. Every run states LinkedIn's status, the same in two places: B4's last line and the Coverage row. Read: '**LinkedIn:** read in your session' and 'LinkedIn: read in your session'. No tool, a no, or a stop: '**LinkedIn:** not read: <reason>' and 'LinkedIn: not read: <reason>', the reason one of linkedin.reasons word for word; no fact is tagged LinkedIn, and Still open carries a LinkedIn question that closes the gap.  
  _Fails when:_ Answer No -- no LinkedIn page opens, B4 and Coverage both read 'LinkedIn: not read: you declined', and no ledger row is tagged LinkedIn (eval.py checks fails C16 otherwise; fixtures linkedin_missing.md, linkedin_declined_with_row.md).
- **S2-8** Source quality: prefer the primary source (the organisation, filings, the person's own words). Never cite a source_quality.exclude domain (people-search and unreachable sites); a source_quality.weak domain is at most C3 and never the only support for a fact on page 1. Cite a fact only where the ledger row says it: hypotheticals (Reverses if, Stop if) carry no citation. Before render, check every link: dead links are replaced or the fact is dropped; blocked links (the site refuses bots) are kept.  
  _Fails when:_ A brief citing mexc.com as C2 fails C18; a Reverses if line citing the intake row fails C17; the link check reports blocked separately from dead.

## Stage 3: Meeting approach

**Input contract** (declared before behaviour):

| Input | Type | Source | Required | Fallback |
|---|---|---|---|---|
| `claims.jsonl` | jsonl | S2 | yes | none |
| `rubric` | rows | pcp.yaml rubric | yes | none |
| `authority_level` | high|medium | profile.caller.authority_level | yes | medium |

**Context contract** -- read, in this order: rubric dimensions + bands, claims tagged family in F1/F5/F6/F7, authority_level. Budget: 1500 words. Not read: claims of other families, brief structure.

**Outputs:** `read.json` (dimension, band, evidence_tier, observation_ids, meeting_meaning)

**Rows:**

- **S3-1** Read each of the six dimensions only from observation_ids in claims.jsonl; a band with fewer observations than its tier minimum is reported as 'no read' -- never guessed from role.  
  _Fails when:_ A target with only role-archetype claims must render every dimension as tier low and the script must contain no influence sequence.
- **S3-2** B6's evidence tier is the highest tier at least three of the six dimensions reach (a no read counts as low). It gates page 3: low -> no Read the room (P5); high AND authority_level high -> Influence (P6). Otherwise P6 is left out.  
  _Fails when:_ Delete one corroborating claim -- the tier must drop and P6 must disappear on re-run.
- **S3-3** Every Your move in B6 is a rubric meaning in pcp.yaml, word for word, or No read; no band phrase is written in prose.  
  _Fails when:_ Grep B6 for a move not in rubric.*.meaning -- the run is rewritten.
- **S3-4** Depth deep adds what they may want: <= 3 hypotheses about what the person wants from this meeting, each with the claim that would disprove it.  
  _Fails when:_ Depth standard -- no hypotheses table in B8; depth deep -- the table, with a disproving claim [n] per hypothesis.

## Stage 4: Intelligence Brief

**Input contract** (declared before behaviour):

| Input | Type | Source | Required | Fallback |
|---|---|---|---|---|
| `claims.jsonl` | jsonl | S2 | yes | none |
| `read.json` | json | S3 | yes | none |
| `profile` | yaml | ~/.pcp/profile.yaml | yes | none |
| `page_budget` | rows | pcp.yaml brief + script | yes | none |

**Context contract** -- read, in this order: brief sections with word budgets, script beats and sections, claims (C1/C2 first), read.json, profile.caller, guardrails. Budget: 3000 words. Not read: rubric evidence lists, family query templates.

**Outputs:** `brief.md` (pages 1-2); `script.md` (page 3); `<out>/<date>-<slug>-intelligence-brief.pdf` (ONE 3-page PDF via format/talyx_pdf.py --style brief --brief-pages 2 --max-pages 3; the script on page 3)

**Rows:**

- **S4-1** Every fact in B1-B9 and the script cites a ledger number [n]; the ledger (B10) lists only cited facts, numbered in order of first use. A fact with no citation is a defect, not a style choice.  
  _Fails when:_ eval.py duf reports unbound or dangling > 0 -- the run must rewrite before render.
- **S4-2** Every sentence passes the swap test against caller.offer_one_line and the target: if another target's name would leave it true, delete it.  
  _Fails when:_ A brief with a sentence containing no claim id and no target-specific noun fails checks.swap.
- **S4-3** Render ONLY through format/talyx_pdf.py --style brief --brief-pages 2 --max-pages 3; never emit Markdown or HTML as the deliverable. The PDF is exactly 3 pages: the brief fills pages 1-2 (a short brief puts the evidence ledger on page 2 -- never filler) and the script is page 3. Check it with eval.py pdf.  
  _Fails when:_ The output directory contains exactly one .pdf and no .md/.html after a run; eval.py pdf on it exits 0 (3 pages, the script on page 3 only, the ledger on page 2).
- **S4-4** If the tightest density rung still overflows 3 pages, the run FAILS with the section word counts; it never truncates or spills.  
  _Fails when:_ Feed a 900-word section -- the engine must exit non-zero naming the section.
- **S4-5** The masthead's meta line carries meeting, prepared for, depth, sources, status and date; the ledger's Run row carries the run details; the footer carries only the Intelligence Brief, the person and the page numbers.  
  _Fails when:_ Extract page 1 text -- the meta line has all six fields; no page footer holds a metric.
- **S4-6** A block or line prints only as its Prints when says: a line PCP cannot fill from evidence is left out, or reads Not determined where its row says so. Never filler.  
  _Fails when:_ No recent wins found -- the Recent wins line is absent, not blank or padded.
- **S4-7** Every Not determined -- a **Label:** line or a table cell -- and every No read in B6 gets a question to ask in the room, in the ledger's Still open row as 'Label: question?', as references/socratic-questions.md says.  
  _Fails when:_ Write **Decision maker:** Not determined, or a | Not determined | table cell, with no question in Still open -- eval.py checks fails C12 (fixtures control_broken.md, gaps_table.md).
- **S4-8** Plain words: nothing printed uses a plain_words.banned term or an internal code; the person's own quoted words are exempt.  
  _Fails when:_ Put SOCMINT in B3 -- eval.py checks fails C11.
- **S4-9** Experience (Q9) shapes page 3 only: new -> P1, P3 and P4 each end with a **Why:** line of at most 12 words; top -> the Hook and each objection's answer are at most 15 words; experienced -> neither.  
  _Fails when:_ Set Q9 new -- P1, P3 and P4 each carry a Why line; set experienced -- none does. eval.py checks --experience <Q9> fails C15 otherwise (fixtures exp_new.md passes as new, exp_experienced_with_why.md fails as experienced).

## Stage 5: Debrief + ratchet

**Input contract** (declared before behaviour):

| Input | Type | Source | Required | Fallback |
|---|---|---|---|---|
| `debrief.yaml` | yaml | user, after the call (60 seconds, 4 fields) | no | skip loop |
| `ratchet.json` | json | evals/ratchet.json | yes | initialise empty |

**Context contract** -- read, in this order: ratchet floors, debrief rows, the pcp.yaml rows the debrief touches. Budget: 800 words. Not read: everything else.

**Rows:**

- **S5-1** A change to pcp.yaml lands only if eval.py ratchet passes: every frozen target's duf_pp >= its floor AND all checks pass. The floor is the best ever seen and only rises.  
  _Fails when:_ Lower a family weight so a target's duf_pp drops -- ratchet must exit non-zero and name the target.
- **S5-2** Debrief fields: facts_used[claim ids], questions_landed[ids], band_accuracy{dim: hit|miss}, outcome. Nothing else is asked.  
  _Fails when:_ The debrief template has exactly four fields.
- **S5-3** improve proposes row diffs (family weights, question templates, band phrases) as a patch with basis: debrief_id; it never edits SKILL.md and never lands a diff itself.  
  _Fails when:_ Run improve -- the only file written is evals/proposals/<date>.patch.

## Asking questions

When a question is needed -- of the user, or for the room -- read `references/socratic-questions.md` first.

## Source families

Enabled per profile: `depth` filters the column, `target.kind` filters `kinds`, `socmint.scope` filters F6
to `linkedin.com/posts, linkedin.com/pulse, youtube.com, podcasts` (professional) or the wider list (social) or none.
FULL status needs >= 1 C1/C2 claim in {'fast': 4, 'standard': 8, 'deep': 10} families (by depth).

| Id | Family | Depth | Social | Query template | Extract |
|---|---|---|---|---|---|
| F1 | identity | fast/standard/deep | no | `"{name}" "{org}" {title}` | current role + start date, prior roles, education, credentials, boards, awards |
| F2 | career timeline | standard/deep | no | `"{name}" {org} career OR joined OR appointed OR promoted` | dated moves; the last 24 months first |
| F3 | org news | fast/standard/deep | no | `"{org}" news OR announces OR partnership OR acquisition OR raises {year}` | deals, leadership changes, launches, growth or contraction, anything the target led |
| F4 | org self-description | standard/deep | no | `{org_website} about OR mission` | how the org describes itself in its own words |
| F5 | voice | fast/standard/deep | no | `"{name}" interview OR podcast OR panel OR quoted OR keynote` | exact quotes with URL; recurring themes; the words they use for their own work |
| F6 | public social | fast/standard/deep | yes | `"{name}" site:linkedin.com/posts OR site:x.com OR site:substack.com OR site:bsky.app` | public posts in the last 180 days; themes, tone, what they amplify; scope per profile.socmint.scope; LinkedIn per S2-7 |
| F7 | affiliations | standard/deep | no | `"{name}" board OR trustee OR advisory OR member OR association OR alumni` | boards, associations, alumni networks, speaking circuits |
| F8 | publications | standard/deep | no | `"{name}" author OR paper OR patent OR whitepaper OR book` | what they have published; the positions they defend in print |
| F9 | registers | fast/standard/deep | no | `by_domain` | regulator / registry facts (see registers); C1 by definition |
| F10 | events | standard/deep | no | `"{name}" OR "{org}" conference OR summit OR webinar {year}` | upcoming and recent appearances; a live hook for the opener |
| F11 | shared context | standard/deep | no | `known_context only (no search)` | shared people, prior touches, mutual affiliations, the user's notes, files and answers -- all tagged Yours |
| F12 | counter-evidence | standard/deep | no | `"{org}" lawsuit OR layoffs OR departure OR decline OR criticism -- filtered by exclusions` | what contradicts the strategic read; feeds the hypotheses; litigation stays excluded from the page |

Registers by domain: wealth: FINRA BrokerCheck, SEC IAPD, SEC EDGAR; pe: SEC EDGAR Form D / ADV, Companies House (UK); saas: Companies House (UK), SEC EDGAR.

**Exclusions (dropped before the writer, counted in coverage):** health, family matters outside the public professional record, political giving, litigation as a talking point, home address, personal finances.
By jurisdiction: eu: any claim older than 5 years that is not a current role, retention of claims.jsonl after render; regulated: performance claims, promissory language, comparative claims about named competitors.

**LinkedIn status (S2-7), in B4's last line and the Coverage row:** `LinkedIn: read in your session`, or
`LinkedIn: not read: <reason>` with one of these reasons, word for word: you declined; no browser here; login wall or security check; paused; scope none.

## Meeting approach (six dimensions)

Tiers: high = 3 observations, 2 sources, a direct quote or action;
medium = 2 observations, 1 source; low = role-inferred only (renders as "No read").

| Dimension | Row label (B6) | Signals | Low means | Mid means | High means |
|---|---|---|---|---|---|
| dominance | Pace and control | interrupts or redirects in recorded panels; directive language in posts; org-chart authority; first-person plural for the firm | Let them set the pace; ask before you propose. | Match their pace; propose once, then ask. | Lead with the outcome in one sentence; they decide fast and dislike preamble. |
| status_sensitivity | How they take recognition | titles and awards foregrounded in bios; name-drops; curated public image; response to public recognition | Skip the flattery; substance only. | Acknowledge one specific achievement, then move on. | Open with respect for a specific, recent, public achievement; never one-up. |
| information_appetite | Appetite for detail | length and density of their writing; data in their talks; questions they ask on panels; sources they cite | Headline and one proof point; offer detail only if asked. | Headline, two proof points, a source on request. | Bring the numbers and the sources; allow silence after a question. |
| risk_tolerance | Appetite for risk | career moves into or out of stability; public positions on new or unproven things; language of caution vs. opportunity | Reduce risk first: references, reversibility, small first step. | Pair the upside with the safeguard in the same sentence. | Lead with the upside and the speed; do not over-hedge. |
| ego_vulnerability | How they take disagreement | reaction to public criticism; defensiveness in interviews; credit-taking vs. credit-giving | Direct disagreement is fine; they separate idea from self. | Frame challenges as questions about the situation, not the person. | Never correct them in the room; ask a question that lets them arrive at it. |
| competitive_drive | How they keep score | benchmarks and rankings in their language; peer references; win/loss framing | Frame around their own goals, not peers. | One peer reference is useful; more is noise. | Name what peers are doing; they will want to be ahead of it. |

What they may want (depth deep only): <= 3 hypotheses about what they want from this meeting, each with the claim that would disprove it.

## The PDF: pages 1-2, the Intelligence Brief

`brief.md` starts with `# Full Name`, then the identity line (`**Organization** | Role, since year | City, if public`),
then the meta line (`Meeting: ... | Prepared for: ... | Depth: ... | Sources: n of 12 source types, n cited | Status FULL or LIMITED | Prepared Mon D, YYYY`).
Then one `## Bn Title` per block, in order. Word budgets are the page budget; the renderer fails, never spills, past 3 pages.

| Id | Block | Words | Prints when | Content |
|---|---|---|---|---|
| B1 | Take | 60 | always | One paragraph: **Take.** who they are and why this meeting matters to them now, in one sentence, every clause cited. **Evidence:** the one to three facts it rests on [n]. **Action:** the first move in the room. **Avoid:** the one move that loses the meeting. It adds no fact the blocks below don't cite. |
| B2 | Questions that close gaps | 210 | always | 5 numbered questions, each <= 20 words, on the fact it rests on [n]; under each, one indented bullet: **Decides:** what the answer settles for you. **Ask:** whom -- the person, or who else is in the room. Ordered by what they decide; the mix follows the meeting type (Q4). |
| B3 | Who they are | 110 | always | Bullets, label first: **Role:** title and since when [n] (required). **Path:** the prior roles that matter [n]. **The organization:** in its own words, plus one scale figure [n]. **What changed:** one to three dated items, newest first [n]. **Recent wins:** none to two dated, cited results [n]. Path, The organization and What changed read Not determined if not found; Recent wins is left out. From F1 F2 F3 F4 F9. |
| B4 | In their words | 90 | always | 2-3 bullets, label first: **Topic, where, when:** "their exact words" [n]. None found: one line of themes from their public presence [n]; nothing at all: Not determined. Then always one last line, not a bullet: **LinkedIn:** read in your session, or **LinkedIn:** not read: and the reason (S2-7). From F5 F6 F8 and LinkedIn. |
| B5 | Signals and what to do with them | 100 | always | A table: | Observable | What to do with it |, three rows in this order: their priority and the gap, in their words [n] -> why this meeting matters to them; where your offer connects (Q8) [n] -> the bridge: the outcome you offer, not the method; the trigger, why now [n] -> the urgency, never invented. From F3 F10 F11 and Q8. |
| B6 | Meeting approach | 170 | always | A table: | What the record shows | Your move |, six rows, one per rubric dimension, each starting with its label (Pace and control, How they take recognition, Appetite for detail, Appetite for risk, How they take disagreement, How they keep score): the cited observation [n] -> the rubric's move word for word, or No read. Then one line: **Evidence tier:** high, medium or low: it sets how far page 3 goes. A cited observation and a move, never a verdict on their character. |
| B7 | Who decides | 50 | always | Bullets: **Decision maker:** who signs off [n]. **The gate:** what must be true, or who must agree, before a yes [n]. **Relationship holder:** who the relationship runs through [n]. Unknown: Not determined, and a question in Still open. From F1 F3 F9 F11. |
| B8 | Strongest case against | 120 | always | Up to 3 bullets: **Against:** the best evidence against your read [n]. **Reverses if:** what would flip it. None found: No counter-evidence found. Deep runs only, then `### What they may want from this meeting` and a table | Hypothesis and why it fits | Test: who answers, and what would disprove it |, up to 3 rows, each with the claim that would disprove it [n]. From F12; litigation stays off the page. |
| B9 | Meeting angle | 120 | always | `### This meeting` then bullets: **Frame:** what this meeting is, in their terms; not a pitch. **Lands:** [n]. **Repels:** [n]. **What to bring:** one thing of value [n]. **The ask:** specific and bounded, who and how long [n] · **Fallback:** the smaller ask. **Stop if:** the answer that means drop the ask. `### Meeting two` then **Meeting two:** the next conversation if this one lands, on a fact from this brief. **Meeting three:** where it goes after that. `### After the meeting` then **Capture:** what to record from the room that the public record couldn't give. From Q8 and B3-B8. |
| B10 | Evidence ledger | 550 | always | One line: Unmarked facts are measured. {n} facts cited; status {FULL or LIMITED} at {n} of 12 source types. Then the table | # | What it says | Source | Grade | Date |, exactly one row per cited fact in order of first use (never grouped): [n] · the fact in about 8 words · [domain](url) (a file name for your own files) · Measured, Derived, Inference or Not determined · Mon D, YYYY. The tag (Direct, Search, LinkedIn, Yours) and confidence (C1-C4) stay in claims.jsonl, not on the page (Ben, Oct 13). Then a label grid (empty header row) with four rows: **Coverage** -- n of 12 source types, what was not found and why, and LinkedIn: read in your session, or LinkedIn: not read: and B4's reason. **Still open** -- each gap with the question that closes it in the room. **Left out on purpose** -- the excluded topics, never the facts. **Run** -- date · depth · meeting type · prepared for · jurisdiction · status · decision-useful facts per page. |

Domain vocabulary: wealth: book, AUM, custodian, fee compression, succession, next-gen; pe: dry powder, DPI, add-on, hold period, exit; saas: ARR, NRR, champion, security review, procurement, renewal.

## The PDF: page 3, the Meeting script

`script.md` starts with `# Meeting script`, then one line: *Facts select the moves; read the room, never the record · Full Name, Organization · Prepared Mon D, YYYY*.
Then one `## Pn Title` per section, in order; a section whose Prints when is not met is left out, not blank.

Beats by meeting format:
- **intro**: open -> credibility in one line -> one insight they did not have -> ask for the second meeting
- **discovery**: open -> situation question -> gap question -> impact question -> next-step test
- **close**: open -> restate their words -> the outcome -> the safeguard -> the ask
- **relationship**: open -> acknowledge what changed -> one thing of value -> one forward question

| Id | Section | Words | Prints when | Content |
|---|---|---|---|---|
| P1 | Open | 80 | always | Bullets: **Hook:** two sentences, said aloud, on a cited fact [n] -- in italics. **Credibility:** who you are, in one line, 30 seconds [n]. **Insight:** one thing they didn't have [n]. **Rule:** how to hold the opening's rapport through the questions. |
| P2 | Question order | 120 | always | Bullets: **Story:** **Process:** **Gate:** **History:** **Commitment:** -- B2's questions word for word, in the order the room needs, on the beats for the meeting type. |
| P3 | Objections: name it, then answer | 110 | always | 3 bullets: **Their likely objection:** *say it before they do, then the answer, at most 30 words* [n]. |
| P4 | Close | 80 | always | Bullets: **Restate:** ask what would make it an easy yes, then say it back in their words. **Real deadline:** a date that actually moves [n]. **The ask:** B9's ask · **Fallback:** B9's fallback. **Follow-up:** what you promise to send, and when. |
| P5 | Read the room (watch, do not assume) | 60 | evidence tier medium or high | Bullets: **Fast, wants the answer:** **Asks for terms and data:** **Talks about people:** **Big picture, ideas:** -- what you do, from B6. |
| P6 | Influence, one fact behind each | 80 | evidence tier high and caller authority high; each principle only where a cited fact backs it | Bullets, only for principles a cited fact backs: **Authority:** **Reciprocity:** **Commitment:** **Social proof:** **Liking:** **Scarcity:** (real limits only; never invented urgency) [n]. |
| P7 | If it stalls | 60 | always | 2-3 bullets: **The move:** what restarts the conversation, from a fact in this brief [n]. |
| P8 | Guardrails | 50 | always | Bullets: **Rule:** what never to promise or claim, for the jurisdiction (Q7). **Never say:** the guardrails.never_say phrases and the domain's forbidden claims, quoted. |
| P9 | Next step | 25 | always | One line: **Next step:** the one action and its date. |

Never say: "Does that make sense?"; "Is this helpful?"; "No pressure"; "You'd know better than me"; "Just checking in".

## Checks (all pass before render)

Run `python3 eval.py checks brief.md script.md --target-nouns "<Full Name>,<surname>,<Organization>,<their key programmes>" --experience <Q9: experienced, new, top> --authority <caller.authority_level: high, medium>`
and `python3 eval.py duf brief.md script.md`; rewrite until both are clean.

| Id | Check | Command | Passes when |
|---|---|---|---|
| C1 | swap | `eval.py checks --swap` | no sentence in B1 or B3-B8 lacks both a [n] and a target-specific noun (headings, the tier line and Not determined lines aside) |
| C2 | bound | `eval.py duf` | unbound == 0, dangling == 0, and every [n] in the body is a B10 row with source, tag, grade, conf. and date |
| C3 | quotes | `eval.py checks --quotes` | every quoted string in B4 has a [n] |
| C4 | custom_q | `eval.py checks --custom-q` | >= 2 questions in B2 carry a [n] |
| C5 | sections | `eval.py checks --sections` | B1-B10 and P1-P9 present in order (P5 and P6 may be left out per S3-2) |
| C6 | budgets | `eval.py checks --budgets` | no section exceeds its words by > 15% |
| C7 | never_say | `eval.py checks --never-say` | no never_say phrase appears outside P8 |
| C8 | outcome | `eval.py checks --outcome` | B5 contains no method verbs from checks.method_verbs |
| C9 | exclusions | `eval.py checks --exclusions` | no excluded topic keyword appears in the body |
| C10 | pages | `format/talyx_pdf.py --style brief --brief-pages 2 --max-pages 3; eval.py pdf` | exactly 3 pages: the brief on pages 1-2 with the evidence ledger last on page 2, the script on page 3, page 3 of 3 in the footer, a link for every ledger row not tagged Yours |
| C11 | plain | `eval.py checks --plain` | no plain_words.banned term or internal code outside quoted words |
| C12 | gaps | `eval.py checks --gaps` | every Not determined in B1-B9 (a **Label:** line or a table cell) and every No read in B6 has its label in B10's Still open row; Still open has at least one ? per gap; each Still open item is 'Label: question?', the question starting What, Who, How, When, Which, Where or If |
| C13 | conditional | `eval.py checks --conditional` | B8's hypotheses only when the meta line says Depth deep; P6 only when B6 says Evidence tier: high; P5 not at tier low; B3's Recent wins line only with a dated, cited result (never Not determined or blank) |
| C14 | layout | `eval.py checks --layout` | the brief has exactly the 9 blocks B1-B9 before B10, and B10 is its last block: no other block and nothing after the ledger |
| C15 | experience | `eval.py checks --experience <Q9>` | new: P1, P3 and P4 each have a **Why:** line of at most 12 words; experienced and top: no Why line; top: the Hook and each objection's answer are at most 15 words |
| C16 | linkedin | `eval.py checks --linkedin` | B4 has exactly one **LinkedIn:** line, read in your session or not read: one of linkedin.reasons; Coverage states the same; when not read, no ledger row is tagged LinkedIn and Still open has a LinkedIn question |
| C17 | cites | `eval.py checks --cites (eval.py cites brief.md --fetch reads the pages too)` | every cited sentence shares content with the ledger claim it cites (2+ content words, 1 when the claim is 3 words or fewer) and every [n] is a ledger row; a hypothetical (Reverses if, Stop if) carries no citation unless the row says it |
| C18 | quality | `eval.py checks --quality` | no ledger row cites a source_quality.exclude domain; a source_quality.weak domain is never C1 or C2 |
| C19 | render | `eval.py pdf (also eval.py render OUT.pdf)` | every page: no ink within 0.12in of a page edge, no word outside the 0.3in side margins; page 1: the logo is whole in the top-right masthead |

## Render

```
python3 format/talyx_pdf.py --style brief --brief brief.md --script script.md \
    --columns "B3|B4,B5|B6,B7|B8,P1+P2+P3+P4|P5+P6+P7+P8" --classification "INTERNAL | PREPARED FOR YOU | NOT FOR THE PERSON DESCRIBED" \
    --footer "Intelligence Brief · <Full Name>, <Organization> · Prepared for you (internal)" \
    --brief-pages 2 --max-pages 3 --out <dir>/<date>-<slug>-intelligence-brief.pdf
```

The PDF is exactly 3 pages: the brief fills pages 1-2 (a short brief puts the ledger on page 2, never
filler) and the script starts on page 3. Then `python3 eval.py pdf <the PDF> brief.md` must exit 0.

It uses Playwright's Chromium if installed, else the Chrome, Edge or Chromium already on the computer. If it
reports that neither is there, run `python3 format/talyx_pdf.py --setup` once and render again.

## Debrief and ratchet

After the call, `evals/debrief_template.yaml` (four fields). `python3 eval.py improve` proposes row diffs to
`pcp.yaml`; `python3 eval.py ratchet` lands them only if every frozen target holds its floor. The floor is the
best ever seen and only rises.

## About

Made by Talyx AI, https://talyx.ai. Free to use under the licence in the plug-in's `LICENSE` file.
