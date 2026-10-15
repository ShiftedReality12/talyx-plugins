<!-- GENERATED from pcp.yaml (sha256:ce5f24e5e311) by render_skill.py -- edit pcp.yaml, never this file -->

# Search rounds: the record by targeted web search

How PCP researches the person you're meeting: five rounds of targeted web searches, each refined from the
last, and LinkedIn only as its public search results show it. PCP never signs in, never opens LinkedIn and
never drives a browser.

**Why.** LinkedIn's User Agreement bars bots and automated tools that copy profiles, and lets LinkedIn restrict the
account that ran them, so reading a profile in your own signed-in browser put your account at risk. A search result
never touches LinkedIn: the search engine read the page, and PCP reads only what the result shows.

The battery is mandatory (S2-9): every round whose source types the run's depth enables, in order, each with at least osint.battery.queries_per_round queries, most of them carrying an advanced operator or the tool's domain filter. Before each round, write one line in the conversation, 'Round N (name): <query> | <query> | ...', the queries as they will be sent (coverage.rounds); then send them. From round 2 on, the queries carry the names, firms, programmes and topics the rounds before found: each round is refined from the last. A round is skipped only when the depth turns all its source types off, never for convenience; a round that finds nothing still counts, and its gap goes to Coverage.

| Depth | Rounds | Queries per round, at least | Searches, at least | With an operator or a domain filter, at least |
|---|---|---|---|---|
| fast | 1, 3, 4 | 3 | 9 | 7 |
| standard | 1, 2, 3, 4, 5 | 4 | 20 | 14 |
| deep | 1, 2, 3, 4, 5 | 5 | 25 | 18 |

**Operators.** Write each query as its round lists it, then send it the way the host's search takes it (osint.hosts). An operator here is site:, intitle:, inurl:, filetype:, after:, before:, OR, an exclusion (-) or the tool's domain filter; quotes alone are not one. When the results show an operator was ignored, log it on the round's line, rerun once with plain quoted terms, and filter the results yourself by their URLs, titles and dates. An ignored operator leaves a gap; it never shows that nothing exists.

**Claude (Claude Code and the Claude apps): the WebSearch tool** (checked: Oct 15, 2026):
- site: goes in allowed_domains (one call per domain set) and out of the query text: typed site: is ignored (site:linkedin.com/in returned Wikipedia and wage sites; allowed_domains [linkedin.com] returned the profile). Round 1's LinkedIn query is always the domain-filtered one.
- filetype:pdf stays in the query, and only results whose URL ends .pdf count for it: the tool ignores the operator (1 PDF in 10 results).
- after: and before: become the month and year in the query ('October 2026'), and results dated outside the window are dropped: the tool ignores the operators.
- intitle: stays in the query, and results without the term in their title are dropped: it is honoured only in part. inurl: and quotes work as written (checked); OR and an exclusion (-) are sent as written.
- On a query without allowed_domains, blocked_domains takes the never-cited domains (source_quality.exclude).

**ChatGPT, Grok, Perplexity, Gemini and other hosts** (checked: not tested):
- Write each query as listed, operators included; where the search tool has a domain or recency setting, use it for site: and the date window.
- Apply the ignored-operator rule whenever the results show an operator was dropped.

**Never.** Use only the result text the host's search tool returns for linkedin.com: never request a linkedin.com URL (profiles, posts or Pulse articles; an article republished elsewhere is opened there), never sign in anywhere, never open or drive a browser session (no computer use, no browser extension), and quote snippets minimally. The search provider's terms govern the query. Collect on the professional role only: the exclusions apply to every round, and a result that touches them by accident stays out of the brief.

**Identity lock.** A LinkedIn result is a lead, not an identity. Use it only when (a) its headline or current role names the person and gives the organisation as their current position (not past experience or a post), and one other detail agrees with the organisation as found elsewhere (its city or region, or its web domain); or (b) a second independent source (the organisation's own site, a filing, a news article) ties that profile or that exact role to the person. A generic title (Owner, President, Founder) counts only with the organisation. A detail that contradicts (another city, another firm) rejects it. A profile URL seen only as a link on another page, with no result of its own, is a lead for the domain-filtered search, not a second profile. Two or more profiles pass: use none. Never pick by guess. Example: Intake 'Mark Brown, Precision Metal Fab'. The firm's own site says Odessa, TX; the only LinkedIn result reads 'Mark Brown - Owner - Precision Metal Fab | Greater Cleveland'. The location contradicts, so nothing from it is used: '**LinkedIn:** not read: no matching profile'.

**Grading.**
- Open the page behind a result before citing it and grade the page (C1 primary and dated, C2 reputable secondary); LinkedIn is the one source cited from its search result. A page that refuses the fetch (a bot wall, 401 or 403) keeps its fact at C3, logged 'not opened': a gap, not a finding that the fact is false. A page that is gone (404 or 410) is dead: cite another source or drop the fact (S2-8).
- A LinkedIn result: tag LinkedIn, Measured for what the result shows (text across an ellipsis is not quoted as one), C3, the source written [linkedin.com, search result](the profile URL the result lists), the date 'seen <today>'. A fact resting on it alone says so in the sentence ('per their LinkedIn'); a role seen only there never prints as confirmed current.
- Items with one origin (a press release, a wire story, the person's own bio: shown by attribution, a link or near-identical wording) count as one source, graded by that origin; a speaker bio, a company bio and their LinkedIn are one self-reported source. Corroboration needs a second item with a different origin.

| Round | Name | Source types | Goal | Queries (fill the braces; send at least the depth's count) | Then |
|---|---|---|---|---|---|
| 1 | identity lock | F1, F9 | one person, one current role, one profile, or a stop | `site:linkedin.com/in "{name}" "{org}"`<br>`site:{org_domain} "{name}"`<br>`"{name}" "{org}" {title}`<br>`"{name}" {title} -"{org}" (namesakes: the same name at another firm or city)`<br>`"{name}" "{org}" site:{a register for the domain, e.g. sec.gov, brokercheck.finra.org}` | Two or more people could be the one you're meeting: stop and ask (S1-2). The organisation's own site and one other source tie the person to it: identity locked. Nothing ties them: continue on the organisation and say so in Coverage. |
| 2 | role and history | F2, F7 | dated moves, boards, how they got here | `"{name}" (intitle:bio OR inurl:bio OR inurl:leadership OR inurl:speakers OR inurl:team)`<br>`"{name}" appointed OR joined OR named OR promoted "{org}"`<br>`site:linkedin.com/in "{name}" "{a prior firm from round 1}"`<br>`"{name}" board OR trustee OR advisory`<br>`"{name}" "{a prior firm or school from round 1}"` | Each prior firm and board found here becomes a term in rounds 3 and 4. |
| 3 | last 90 days | F3, F10 | what changed for them and the organisation in the last 90 days | `"{name}" OR "{org}" announces OR appointed OR launches after:{date_90_days_ago}`<br>`site:{org_domain} inurl:news OR inurl:press "{name}"`<br>`"{org}" results OR funding OR acquisition OR partnership after:{date_90_days_ago}`<br>`"{name}" conference OR summit OR keynote {this year}`<br>`"{org}" "{a programme, deal or firm from round 2}" after:{date_90_days_ago}` | A dated event here is the opener's hook and B3's Recent wins line. |
| 4 | their own words | F5, F6, F8 | quotes with a date and a link | `"{name}" interview OR podcast OR keynote OR panel`<br>`filetype:pdf "{name}" "{org}"`<br>`"{name}" site:youtube.com OR site:linkedin.com/pulse OR site:linkedin.com/posts`<br>`"{name}" "{a topic from rounds 2-3}"`<br>`intitle:"{name}" transcript OR remarks OR letter` | Their recurring words feed In their words and the Behavioral profile. |
| 5 | gaps and counter-evidence | F12, F11 | only what is still Not determined, and what contradicts the read | `"{name}" OR "{org}" decides OR approves OR budget OR committee`<br>`"{org}" layoffs OR departure OR decline OR criticism (the exclusions still apply)`<br>`"{org}" "{a gap still Not determined: who decides, the gate, the timing}"`<br>`site:{org_domain} "{the gap term}" (the organisation in its own words on the open gap)`<br>`"{org}" "{the claim the Take rests on}" -"{name}" (who disagrees with the read)` | What is still open after this round becomes a Still open question in the room. |

## LinkedIn status

Every run says, in B4's last line and in the Coverage row: `LinkedIn: read from search results` or `LinkedIn: read from your file`, or
`LinkedIn: not read: <reason>` with one of: you declined; scope none; no matching profile. Check C16 holds the two lines to each other and to the ledger.

**A saved profile (optional).** When you give PCP the person's LinkedIn profile saved as a PDF (on their
profile: More > Save to PDF) or as copied text, it is read as your file: its facts are tagged Yours and cited by
the file name, and the status reads `LinkedIn: read from your file`. PCP never waits for one. This path is under review.
