<!-- GENERATED from pcp.yaml (sha256:955f9b4c32cc) by render_skill.py -- edit pcp.yaml, never this file -->
---
name: pre-call-prep
description: >
  Prepare for an upcoming meeting with a named person, company or deal. Eight one-time calibration
  questions, public-source OSINT/SOCMINT collection with a coverage ledger, a six-dimension
  behavioral read, and ONE 3-page PDF: a 2-page brief plus a 1-page meeting script. Use when the
  user mentions pre-call prep, meeting prep, call preparation, researching someone before a
  meeting, talking points, or shares an intake list. Do not use for general research unrelated to
  a meeting, or for notes on a meeting that has already happened.
---

# Pre-call prep (v2.0.0)

Five stages, dependency-ordered: **calibrate once -> intake -> collect -> read -> brief + script -> debrief.**
Every stage declares its inputs before its behaviour, reads only its listed context, and follows rows
that each carry a falsification test. Every fact traces to a public source. Nothing is invented.
The deliverable is one 3-page PDF. Nothing else is emitted.

## Stage 0: Calibrate (once)

If `~/.pcp/profile.yaml` is missing or invalid, or `--recalibrate` is passed, ask these eight
questions with `AskUserQuestion` -- two calls of four, first option recommended -- then write the
profile and continue. Otherwise read the profile silently.

| # | Chip | Question | Options | Sets |
|---|---|---|---|---|
| Q1 | Your role | Who is making the call? | Founder / principal (Recommended) / Sales / BD / Advisor / relationship manager / Investor / allocator | caller.role, caller.authority_level |
| Q2 | Domain | Where do your targets mostly live? | General professional (Recommended) / Wealth management / Private equity / VC / Enterprise / SaaS | domain |
| Q3 | Target kind | Who do you usually prep for? | A person (Recommended) / A company or team / A deal or transaction / Mixed | target.kind_default |
| Q4 | Meeting | What is the typical call? | First intro (cold or warm) (Recommended) / Discovery / qualification / Pitch / close / Relationship / renewal | meeting.format_default |
| Q5 | Depth | Research depth versus speed? | Standard -- 12 families / Fast -- 6 families / Deep -- all families + competing hypotheses | research.depth |
| Q6 | SOCMINT | Public social footprint -- how far? | Professional only (Recommended) / Plus public X / Bluesky / Substack / None | socmint.scope |
| Q7 | Compliance | Jurisdiction and compliance posture? | US (Recommended) / UK / EU (GDPR strict) / Regulated sales (FINRA / FCA style) / APAC | jurisdiction |
| Q8 | Your offer | In one line -- what do you offer, and what does a win in this meeting look like? (free text) | free text | caller.offer_one_line, meeting.win_definition |

- **CAL-1** Ask all eight questions only when ~/.pcp/profile.yaml is missing, invalid, or --recalibrate is passed. Otherwise read it silently.  
  _Fails when:_ Delete the profile and run -- the run must ask. Run again -- it must not.
- **CAL-2** A skipped answer takes the first (Recommended) option and is stored with defaulted:true; the PDF footer shows the profile line.  
  _Fails when:_ Skip Q5 -- profile shows research.depth standard, defaulted true; footer reads "standard".
- **CAL-3** The improve loop may PROPOSE a profile change (one line, with the debrief evidence) but never applies one without a yes.  
  _Fails when:_ Three debriefs with facts_used > 80% must produce a proposal, and the profile must be unchanged until answered.

Profile line (footer of every PDF): `role · domain · depth · jurisdiction`.

## Stage 1: Intake

**Input contract** (declared before behaviour):

| Input | Type | Source | Required | Fallback |
|---|---|---|---|---|
| `arguments` | path.csv | 'Full Name, Organisation' | empty | $ARGUMENTS | yes | ask the required intake fields in one message |
| `profile` | yaml | ~/.pcp/profile.yaml | yes | run calibration |
| `meeting.objective` | text | intake row or one question | yes | ask: What do you want to walk out of this meeting with? |
| `target.kind` | person|company|deal | intake or profile.target.kind_default | yes | person |

**Context contract** -- read, in this order: profile, intake row, this stage's rows. Budget: 600 words. Not read: reference files of later stages, prior briefs.

**Rows:**

- **S1-1** Do not start research without a full name and an organisation.  
  _Fails when:_ Run with a name only -- the run must ask, not search.
- **S1-2** Two or more people match the name: stop and ask which one. Wrong-person research is worse than none.  
  _Fails when:_ Seed an ambiguous name -- the run must present the candidates and stop.
- **S1-3** Up to 8 targets per run; research targets in parallel, write briefs in turn.  
  _Fails when:_ A 9-row CSV must be refused with the count.

## Stage 2: Collection

**Input contract** (declared before behaviour):

| Input | Type | Source | Required | Fallback |
|---|---|---|---|---|
| `resolved_families` | list | families filtered by profile (kind, depth, socmint) | yes | none -- derived |
| `exclusions` | list | exclusions.base + exclusions.by_jurisdiction[profile.jurisdiction] | yes | none -- derived |
| `known_context` | text | intake Notes column | no | empty |

**Context contract** -- read, in this order: resolved_families with query templates, exclusions, target identity, known_context. Budget: 1200 words. Not read: rubric, brief structure, script structure.

**Outputs:** `claims.jsonl` (id, claim, family, url, retrieved_at, tag, confidence, exclusion_hit); `coverage` (families_attempted, families_total, hits_by_family, failed_urls, status)

**Rows:**

- **S2-1** Public sources only. Nothing behind a login, no paid data the user has not supplied, no scraping.  
  _Fails when:_ A LinkedIn login wall counts as a failed URL and appears in coverage.failed_urls.
- **S2-2** Every claim carries url, retrieved_at, tag DIRECT|SEARCH, and confidence C1 (primary, dated) | C2 (reputable secondary) | C3 (single weak source) | C4 (inferred).  
  _Fails when:_ A claim missing any field is dropped by eval.py claims and counted in coverage.dropped.
- **S2-3** A claim that hits an exclusion is dropped BEFORE the writer sees it and counted in coverage.excluded; the brief's guardrails say a topic was left out, never which fact.  
  _Fails when:_ Seed a claim tagged exclusion health -- it must not appear in any output file.
- **S2-4** Coverage is a required output: families_attempted/families_total and hits per family. A run without coverage is not a run.  
  _Fails when:_ Disable WebFetch -- coverage must show 0/N attempted and status LIMITED, never FULL.
- **S2-5** Status FULL requires >= 1 C1/C2 claim in >= research.full_threshold[depth] families; else LIMITED, stamped on page 1.  
  _Fails when:_ Remove all C1/C2 claims from one family below threshold -- status flips to LIMITED.
- **S2-6** Run the counter-evidence family last: search for what would contradict the strategic read.  
  _Fails when:_ With depth standard or deep, coverage must show family F12 attempted.

## Stage 3: Behavioral read

**Input contract** (declared before behaviour):

| Input | Type | Source | Required | Fallback |
|---|---|---|---|---|
| `claims.jsonl` | jsonl | S2 | yes | none |
| `rubric` | rows | pcp.yaml rubric | yes | none |
| `authority_level` | high|medium | profile.caller.authority_level | yes | medium |

**Context contract** -- read, in this order: rubric dimensions + bands, claims tagged family in F1/F5/F6/F7, authority_level. Budget: 1500 words. Not read: claims of other families, brief structure.

**Outputs:** `read.json` (dimension, band, evidence_tier, observation_ids, meeting_meaning)

**Rows:**

- **S3-1** Score each of the six dimensions only from observation_ids in claims.jsonl; a band with fewer observations than its tier minimum is reported as 'no read' -- never guessed from role.  
  _Fails when:_ A target with only role-archetype claims must render every dimension as tier low and the script must contain no influence sequence.
- **S3-2** Evidence tier gates script depth: low -> opener + questions; medium -> + framing; high -> + influence sequence (only if authority_level high).  
  _Fails when:_ Delete one corroborating claim -- the tier must drop and the influence sequence must disappear on re-run.
- **S3-3** Every band phrase on the page is a rubric row in pcp.yaml; no band phrase is written in prose.  
  _Fails when:_ Grep the brief for a band phrase not in rubric.*.meaning -- concordance fails.
- **S3-4** Depth deep adds an ACH mini: <= 3 hypotheses about what the target wants from this meeting, each with the claim that would disconfirm it.  
  _Fails when:_ Depth standard -- no ACH block; depth deep -- ACH block with a disconfirming claim id per hypothesis.

## Stage 4: Brief + script

**Input contract** (declared before behaviour):

| Input | Type | Source | Required | Fallback |
|---|---|---|---|---|
| `claims.jsonl` | jsonl | S2 | yes | none |
| `read.json` | json | S3 | yes | none |
| `profile` | yaml | ~/.pcp/profile.yaml | yes | none |
| `page_budget` | rows | pcp.yaml brief + script | yes | none |

**Context contract** -- read, in this order: brief sections with word budgets, script beats, claims (C1/C2 first), read.json, profile.caller, guardrails. Budget: 3000 words. Not read: rubric evidence lists, family query templates.

**Outputs:** `brief.md` (pages 1-2); `script.md` (page 3); `<out>/<date>-<slug>.pdf` (ONE 3-page PDF via format/talyx_pdf.py --max-pages 3)

**Rows:**

- **S4-1** Every fact in the brief cites a claim id [n]; the Sources block lists only cited claims. A fact with no citation is a defect, not a style choice.  
  _Fails when:_ eval.py duf reports unbound > 0 -- the run must rewrite before render.
- **S4-2** Every sentence passes the swap test against caller.offer_one_line and the target: if another target's name would leave it true, delete it.  
  _Fails when:_ A brief with a sentence containing no claim id and no target-specific noun fails checks.swap.
- **S4-3** Render ONLY through format/talyx_pdf.py with --max-pages 3; never emit Markdown or HTML as the deliverable.  
  _Fails when:_ The output directory contains exactly one .pdf and no .md/.html after a run.
- **S4-4** If the tightest density rung still overflows 3 pages, the run FAILS with the section word counts; it never truncates or spills.  
  _Fails when:_ Feed a 900-word section -- the engine must exit non-zero naming the section.
- **S4-5** The PDF footer carries: profile line, research status, duf_pp, coverage fraction.  
  _Fails when:_ Extract page-3 footer text -- all four fields present.

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

## Source families

Enabled per profile: `depth` filters the column, `target.kind` filters `kinds`, `socmint.scope` filters F6
to `linkedin.com/posts, linkedin.com/pulse, youtube.com, podcasts` (professional) or the wider list (social) or none.
FULL status needs >= 1 C1/C2 claim in {'fast': 4, 'standard': 8, 'deep': 10} families (by depth).

| Id | Family | Depth | SOCMINT | Query template | Extract |
|---|---|---|---|---|---|
| F1 | identity | fast/standard/deep | no | `"{name}" "{org}" {title}` | current role + start date, prior roles, education, credentials, boards, awards |
| F2 | career timeline | standard/deep | no | `"{name}" {org} career OR joined OR appointed OR promoted` | dated moves; the last 24 months first |
| F3 | org news | fast/standard/deep | no | `"{org}" news OR announces OR partnership OR acquisition OR raises {year}` | deals, leadership changes, launches, growth or contraction, anything the target led |
| F4 | org self-description | standard/deep | no | `{org_website} about OR mission` | how the org describes itself in its own words |
| F5 | voice | fast/standard/deep | no | `"{name}" interview OR podcast OR panel OR quoted OR keynote` | exact quotes with URL; recurring themes; the words they use for their own work |
| F6 | public social | fast/standard/deep | yes | `"{name}" site:linkedin.com/posts OR site:x.com OR site:substack.com OR site:bsky.app` | public posts in the last 180 days; themes, tone, what they amplify; scope per profile.socmint.scope |
| F7 | affiliations | standard/deep | no | `"{name}" board OR trustee OR advisory OR member OR association OR alumni` | boards, associations, alumni networks, speaking circuits |
| F8 | publications | standard/deep | no | `"{name}" author OR paper OR patent OR whitepaper OR book` | what they have published; the positions they defend in print |
| F9 | registers | fast/standard/deep | no | `by_domain` | regulator / registry facts (see registers); C1 by definition |
| F10 | events | standard/deep | no | `"{name}" OR "{org}" conference OR summit OR webinar {year}` | upcoming and recent appearances; a live hook for the opener |
| F11 | shared context | standard/deep | no | `known_context only (no search)` | shared people, prior touches, mutual affiliations named by the caller |
| F12 | counter-evidence | standard/deep | no | `"{org}" lawsuit OR layoffs OR departure OR decline OR criticism -- filtered by exclusions` | what contradicts the strategic read; feeds ACH; litigation stays excluded from the page |

Registers by domain: wealth: FINRA BrokerCheck, SEC IAPD, SEC EDGAR; pe: SEC EDGAR Form D / ADV, Companies House (UK); saas: Companies House (UK), SEC EDGAR.

**Exclusions (dropped before the writer, counted in coverage):** health, family matters outside the public professional record, political giving, litigation as a talking point, home address, personal finances.
By jurisdiction: eu: any claim older than 5 years that is not a current role, retention of claims.jsonl after render; regulated: performance claims, promissory language, comparative claims about named competitors.

## Behavioral read (six dimensions)

Tiers: high = 3 observations, 2 sources, a direct quote or action;
medium = 2 observations, 1 source; low = role-inferred only (renders as "no read").

| Dimension | Signals | Low means | Mid means | High means |
|---|---|---|---|---|
| dominance | interrupts or redirects in recorded panels; directive language in posts; org-chart authority; first-person plural for the firm | Let them set the pace; ask before you propose. | Match their pace; propose once, then ask. | Lead with the outcome in one sentence; they decide fast and dislike preamble. |
| status_sensitivity | titles and awards foregrounded in bios; name-drops; curated public image; response to public recognition | Skip the flattery; substance only. | Acknowledge one specific achievement, then move on. | Open with respect for a specific, recent, public achievement; never one-up. |
| information_appetite | length and density of their writing; data in their talks; questions they ask on panels; sources they cite | Headline and one proof point; offer detail only if asked. | Headline, two proof points, a source on request. | Bring the numbers and the sources; allow silence after a question. |
| risk_tolerance | career moves into or out of stability; public positions on new or unproven things; language of caution vs. opportunity | Reduce risk first: references, reversibility, small first step. | Pair the upside with the safeguard in the same sentence. | Lead with the upside and the speed; do not over-hedge. |
| ego_vulnerability | reaction to public criticism; defensiveness in interviews; credit-taking vs. credit-giving | Direct disagreement is fine; they separate idea from self. | Frame challenges as questions about the situation, not the person. | Never correct them in the room; ask a question that lets them arrive at it. |
| competitive_drive | benchmarks and rankings in their language; peer references; win/loss framing | Frame around their own goals, not peers. | One peer reference is useful; more is noise. | Name what peers are doing; they will want to be ahead of it. |

ACH mini (depth deep only): <= 3 hypotheses about what they want from this meeting, each with the claim that would disconfirm it.

## The PDF: pages 1-2 brief

Word budgets are the page budget; the engine renders on a 4-rung density ladder and fails, never spills, past 3 pages.

| Id | Section | Words | Content |
|---|---|---|---|
| B1 | Snapshot | 140 | Role, path, credentials (F1/F2). Org in its own words + what changed (F3/F4). Status + coverage line. |
| B2 | In their words | 90 | 2-3 exact quotes with [n]; or 'Themes from their public presence' if none (F5/F6). |
| B3 | Strategic read | 120 | Why this meeting matters to THEM. Pressure, priority, where the caller's offer connects. Counter-evidence acknowledged in one clause (F12). |
| B4 | Behavioral read | 110 | Six rows: dimension | band | meaning-for-the-meeting | [n]. 'no read' where tier is missing. Tier gate line. |
| B5 | Discovery questions | 180 | 4-6 questions, each <= 40 words, each with 'What the answer tells you' and a [n]. Mix set by meeting.format. |
| B6 | Their situation framed | 110 | Gap -> Bridge (outcome, not method) -> Urgency, in their language, each step with a [n]. |
| B7 | Value and next step | 80 | One thing of value to bring; the ask; the fallback ask. |
| B8 | Guardrails | 90 | Pace/language from B4; [UNVERIFIED] items to confirm; topics left out on purpose; never-say list. |
| B9 | Sources | 160 | Cited claims only: [n] claim -- URL -- DIRECT|SEARCH -- C-level -- date. Coverage fraction on the last line. |

Domain vocabulary: wealth: book, AUM, custodian, fee compression, succession, next-gen; pe: dry powder, DPI, add-on, hold period, exit; saas: ARR, NRR, champion, security review, procurement, renewal.

## The PDF: page 3 meeting script

Beats by meeting format:
- **intro**: open -> credibility in one line -> one insight they did not have -> ask for the second meeting
- **discovery**: open -> situation question -> gap question -> impact question -> next-step test
- **close**: open -> restate their words -> the outcome -> the safeguard -> the ask
- **relationship**: open -> acknowledge what changed -> one thing of value -> one forward question

| Id | Block | Words | Content |
|---|---|---|---|
| P1 | Open | 40 | <= 2 sentences; names a [n]. |
| P2 | Beats | 200 | One line per beat from beats_by_format, each with the [n] it rests on. |
| P3 | Questions | 150 | 5 questions verbatim from B5, ordered for the room. |
| P4 | If they say | 120 | 3 objection -> response pairs, each response <= 30 words. |
| P5 | Influence sequence | 60 | ONLY if tier high AND authority high: 3 moves from B4 meanings. Otherwise this block is omitted, not blank. |
| P6 | Close and ask | 50 | The ask, the fallback, the follow-up promise. |
| P7 | Never say | 40 | guardrails.never_say + jurisdiction rows. |

Never say: "Does that make sense?"; "Is this helpful?"; "No pressure"; "You'd know better than me"; "Just checking in".

## Checks (all pass before render)

| Id | Check | Command | Passes when |
|---|---|---|---|
| C1 | swap | `eval.py checks --swap` | no sentence in B1-B7 lacks both a [n] and a target-specific noun |
| C2 | bound | `eval.py duf` | unbound == 0 and every [n] in the body exists in B9 with url+tag+date |
| C3 | quotes | `eval.py checks --quotes` | every quoted string in B2 has a [n] |
| C4 | custom_q | `eval.py checks --custom-q` | >= 2 questions in B5 carry a [n] |
| C5 | sections | `eval.py checks --sections` | B1-B9 and P1-P7 present in order (P5 may be omitted per S3-2) |
| C6 | budgets | `eval.py checks --budgets` | no section exceeds its words by > 15% |
| C7 | never_say | `eval.py checks --never-say` | no never_say phrase appears outside P7/B8 |
| C8 | outcome | `eval.py checks --outcome` | B6 Bridge contains no method verbs from checks.method_verbs |
| C9 | exclusions | `eval.py checks --exclusions` | no excluded topic keyword appears in the body |
| C10 | pages | `format/talyx_pdf.py --max-pages 3` | rendered page count == 3 |

## Render

```
python3 format/talyx_pdf.py --brief brief.md --script script.md --title "<Name> -- <Org>" \
    --subtitle "Pre-call brief · <meeting date>" --footer "<profile line> · <status> · duf_pp <x> · coverage <a>/<b>" \
    --max-pages 3 --out <dir>/<date>-<slug>.pdf
```

## Debrief and ratchet

After the call, `evals/debrief_template.yaml` (four fields). `python3 eval.py improve` proposes row diffs to
`pcp.yaml`; `python3 eval.py ratchet` lands them only if every frozen target holds its floor. The floor is the
best ever seen and only rises.

## About

Made by Talyx AI, https://talyx.ai. Free to use under the licence in the plug-in's `LICENSE` file.
