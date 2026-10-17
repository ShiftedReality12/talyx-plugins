<!-- GENERATED from pcp.yaml (sha256:a18c120a8ff1) by render_skill.py -- edit pcp.yaml, never this file -->

# Collection: source types, records and LinkedIn

Loaded by Stage 2 of SKILL.md.

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
| F6 | public social | fast/standard/deep | yes | `"{name}" site:linkedin.com/posts OR site:x.com OR site:substack.com OR site:bsky.app` | public posts in the last 180 days; themes, tone, what they amplify; scope per profile.socmint.scope; LinkedIn per S2-7 |
| F7 | affiliations | standard/deep | no | `"{name}" board OR trustee OR advisory OR member OR association OR alumni` | boards, associations, alumni networks, speaking circuits |
| F8 | publications | standard/deep | no | `"{name}" author OR paper OR patent OR whitepaper OR book` | what they have published; the positions they defend in print |
| F9 | registers | fast/standard/deep | no | `by_domain` | regulator / registry facts (see registers); C1 by definition |
| F10 | events | standard/deep | no | `"{name}" OR "{org}" conference OR summit OR webinar {year}` | upcoming and recent appearances; a live hook for the opener |
| F11 | shared context | standard/deep | no | `known_context only (no search)` | shared people, prior touches, mutual affiliations, the user's notes, files and answers -- all tagged Yours |
| F12 | counter-evidence | standard/deep | no | `"{org}" lawsuit OR layoffs OR departure OR decline OR criticism -- filtered by exclusions` | what contradicts the strategic read; feeds the hypotheses; litigation stays excluded from the page |

Placeholders in the query templates and rounds: `{name}` = the intake's Full Name; `{org}` = the intake's Organisation; `{title}` = the intake's Title/Role, else the role F1 finds; `{org_website}` = the intake's Organisation Website, else the organisation's own site found by F1; `{org_domain}` = org_website's host without www., e.g. microsoft.com; `{year}` = the current year, four digits; `{date_90_days_ago}` = today minus 90 days, YYYY-MM-DD; `{carry}` = a name, firm, programme, topic or gap the base pass or an earlier round found (the slots written in braces with a description, e.g. {a prior firm from round 1}).

Registers by domain: wealth: FINRA BrokerCheck (https://brokercheck.finra.org), SEC IAPD (https://adviserinfo.sec.gov), SEC EDGAR (https://www.sec.gov/edgar); pe: SEC EDGAR Form D / ADV (https://www.sec.gov/edgar), Companies House (UK) (https://find-and-update.company-information.service.gov.uk); saas: Companies House (UK) (https://find-and-update.company-information.service.gov.uk), SEC EDGAR (https://www.sec.gov/edgar).

**Exclusions (dropped before the writer, counted in coverage):** health, family matters outside the public professional record, political giving, litigation as a talking point, home address, personal finances.
By jurisdiction: eu: any claim older than 5 years that is not a current role, retention of claims.jsonl after render; regulated: performance claims, promissory language, comparative claims about named competitors.

**Sources never cited:** goodfest.westfield.com, peoplefinders.com, spokeo.com, whitepages.com, beenverified.com, radaris.com, truthfinder.com, mylife.com. **Weak (never C1/C2, never the only support on page 1):** thefabulous.co, mexc.com, medium.com, substack.com, quora.com, reddit.com, wikipedia.org, crunchbase.com, zoominfo.com, rocketreach.co, signalhire.com, contactout.com, theorg.com, famousbirthdays.com, celebsages.com, wealthygorilla.com, idcrawl.com.

## Records (C23)

Keep three records while you work, in these files beside the brief (a host with no files keeps the same fields in its
working notes). Compose the brief from them alone (S4-12), and run `python3 eval.py records <folder> --depth <depth> --brief brief.md`
before you say the run is done.

| Record | File | Fields |
|---|---|---|
| claims | `claims.jsonl` | id, claim, says, page, family, url, retrieved_at, published, tag, grade, confidence, exclusion_hit |
| coverage | `coverage.json` | base, rounds, searches, attempted, families_attempted, families_total, hits_by_family, c1c2_by_family, failed_urls, excluded, dropped, linkedin, status -- hits_by_family and c1c2_by_family hold one count for each of the 12 source types (F1-F12, 0 when none); attempted lists the source types searched; failed_urls lists each URL that refused (a login wall, 404) with its status; base lists, for each source type the depth enables that has a query template, the queries its base-pass search sent; rounds lists each round with the queries it sent and any operator the search ignored; searches is the total sent, base and rounds; excluded and dropped count the claims removed (S2-2, S2-3); status is FULL or LIMITED as S2-5 says |
| read | `read.json` | dimension, band, evidence_tier, observation_ids, meeting_meaning -- six rows, one per rubric dimension; meeting_meaning is the rubric's phrase for the band word for word, or No read; a no read has tier low and no observation_ids; the tier needs its minimum observations (rubric.tiers); the page's Evidence tier is the highest tier at least three rows reach |

**LinkedIn status (S2-7), in B4's last line and the Coverage row:** `LinkedIn: read from search results` or `LinkedIn: read from your file` or `LinkedIn: read from the link you gave`, or
`LinkedIn: not read: <reason>` with one of these reasons, word for word: you declined; scope none; no matching profile.

## Rules moved out of SKILL.md

The full text of the rows SKILL.md summarises; the rule is this text.

- **S2-7** LinkedIn is read the way the rest of the record is: by targeted web search in rounds (osint; references/osint-search.md), from the result text the host's search tool returns. Never sign in, and never open or drive a browser session (osint.never). A LinkedIn address the user gives (the intake's LinkedIn URL column, or in their message) is read once with the host's plain page fetch: it is theirs, so no identity lock; a login wall or a refusal is a failed URL (coverage.failed_urls) and the run goes on from search results. A profile the user saves (PDF or copied text) is read as their file. Any other linkedin.com page is never requested. With social scope none, or when the user says not to, run no LinkedIn query: 'not read: scope none' or 'not read: you declined'. A LinkedIn search result is used only once it passes the identity lock (osint.identity_lock); when none passes: 'not read: no matching profile'. Its facts are graded as osint.grading says: tag LinkedIn, C3, cited [linkedin.com, search result](the URL the result lists) -- a profile, post or article alike, since none is opened -- dated 'seen <today>', and 'per their LinkedIn' in a sentence that rests on it alone. When the user gives the person's LinkedIn profile saved as a PDF or copied text, read it as their file (tag Yours, cited by the file name; 'read from your file'); a given link read in full is tag LinkedIn, cited [linkedin.com: the link you gave](the address), status 'read from the link you gave'; the run never waits for either. Every run states LinkedIn's status, the same in two places, B4's last line and the Coverage row: '**LinkedIn:** read from search results' or 'read from your file', or '**LinkedIn:** not read: <reason>', the reason one of linkedin.reasons word for word; not read: no fact is tagged LinkedIn. An unread LinkedIn is stated in Coverage only, never as a Still open question.
- **S2-9** Research is two passes, both mandatory. (1) The base pass -- the collection the original plug-in always ran: for every source type the depth enables (Standard and Deep 12, Fast 5), send its query template from the source-types table with its placeholders filled, and extract what its Extract column says, one claim per fact (S2-2). The target kind and social scope filter the types as the table does (a company or deal drops the person-only types and queries on {org}; scope none sends no F6 query; scope social adds X, Bluesky and Substack). F1 goes first and settles who the person is (two people match: stop and ask, S1-2); F11 is the user's own notes and needs no search; F12, the counter-evidence, goes last (S2-6). Count each source type's hits and its C1/C2 claims (S2-4, S2-5). (2) The search rounds on top (osint): refinement of the base pass, never a replacement for it -- round 1 (the identity lock, its LinkedIn query among them) to round 5, in order, each round at least the battery's queries, most with an advanced operator or the tool's domain filter, and from round 1 on they carry what the base pass and the rounds before found. Send each round's queries together, in one step, and no other search until the next round. Keep each round's line, 'Round N (name): <query> | <query> | ...', in your reasoning and in coverage.rounds only, never in the reply (S2-10). Coverage reports both passes: n of 12 source types in the base pass, and the Run row ends 'N searches (B base) in M rounds'. Neither pass replaces reading: open the page behind every result you cite (LinkedIn aside) -- before you write the ledger, check each row's link against the pages you opened, and open the rest or drop their facts -- and the fact floor (S4-11) still holds.
- **S2-11** Run collection as a background job where the host has one, and take back only the records. Claude Code and Cowork: one Agent (Task) subagent per target, all in one message (S1-3), each in the foreground of the turn so its result is awaited; Codex: a sub-agent through the host's spawn tool, or a detached exec job; ChatGPT agent and work mode: the host's own background task. Brief each job with the intake row, the profile, the exclusions and S2-1 to S2-9; it runs rounds 1-5, opens the pages it cites, writes claims.jsonl, coverage.json and read.json (records, C23) and returns the folder and one line. The rounds then run inside the job, which the host shows as one task row. Do not narrate, poll or print a job's progress. Where the host has no background job, run the same stage in this thread, quietly (S2-10).

