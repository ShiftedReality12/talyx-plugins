<!-- GENERATED from pcp.yaml (sha256:e2b17d79cae0) by render_skill.py -- edit pcp.yaml, never this file -->

# Checks and the test for each rule

Loaded by Stage 4 of SKILL.md.

## Checks

| Id | Check | Command | Passes when |
|---|---|---|---|
| C1 | swap | `eval.py checks --swap` | no sentence in B1-B9 -- the questions (B2) and the meeting angle (B9) included -- lacks both a [n] and a target-specific noun (headings, the tier line, Not determined lines and a whole line that is exactly a schema template aside) |
| C2 | bound | `eval.py duf; eval.py records <folder> --brief brief.md` | unbound == 0, dangling == 0, and every [n] in the body is a B10 row | [n] | what it says | source | grade | date |; and every cited row's claim in claims.jsonl keeps the url, tag, date and confidence 2.1.0 required (claim_requires) |
| C3 | quotes | `eval.py checks --quotes` | every quoted string in B4 has a [n] |
| C4 | custom_q | `eval.py checks --custom-q` | >= 2 questions in B2 carry a [n] |
| C5 | sections | `eval.py checks --sections` | B1-B10 and P1-P9 present in order (P5 and P6 may be left out per S3-2) |
| C6 | budgets | `eval.py checks --budgets` | no section exceeds its words by > 15% |
| C7 | never_say | `eval.py checks --never-say` | no never_say phrase appears outside P8 |
| C8 | outcome | `eval.py checks --outcome` | B1, B5 and B9 contain no method verbs from checks.method_verbs |
| C9 | exclusions | `eval.py checks --exclusions` | no excluded topic keyword appears in the body |
| C10 | pages | `format/talyx_pdf.py --style brief --brief-pages 2 --max-pages 3; eval.py pdf` | exactly 3 pages: the brief on pages 1-2 with the evidence ledger last on page 2, the script on page 3, page 3 of 3 in the footer, a link for every ledger row not tagged Yours; page 3's numbered sections run 1, 2, 3 ... with no gap when a section drops |
| C11 | plain | `eval.py checks --plain` | no plain_words.banned term or internal code outside quoted words |
| C12 | gaps | `eval.py checks --gaps` | Still open holds at most 4 items, and at least one while B1-B9 show a gap (a Not determined **Label:** line or table cell, or a No read in B6); each item is 'Label: question?', the label a gap above, the question starting What, Who, How, When, Which, Where or If |
| C13 | conditional | `eval.py checks --conditional` | B8's hypotheses only when the meta line says Depth deep; P6 only when B6 says Evidence tier: high; P5 not at tier low; B3's Recent wins line only with a dated, cited result (never Not determined or blank) |
| C14 | layout | `eval.py checks --layout` | the brief has exactly the 9 blocks B1-B9 before B10, and B10 is its last block: no other block and nothing after the ledger; B9 has one label per line (The ask with its Fallback excepted); nothing prints '(not confirmed)', and the identity line prints nothing unknown |
| C15 | experience | `eval.py checks --experience <Q9>` | new: P1, P3 and P4 each have a **Why:** line of at most 12 words; experienced and top: no Why line; top: the Hook and each objection's answer are at most 15 words |
| C16 | linkedin | `eval.py checks --linkedin` | B4 has exactly one **LinkedIn:** line: read from search results, read from your file, or not read: one of linkedin.reasons (a brief run before a linkedin.retired reason's day may give it); Coverage states the same; read from search results: a ledger row cites the linkedin.com/in profile the result showed; read from your file: no ledger row cites a linkedin.com/in profile (the file is cited); not read: no ledger row is tagged LinkedIn and Still open asks nothing about LinkedIn |
| C17 | cites | `eval.py checks --cites (eval.py cites brief.md --fetch reads the pages too)` | every cited sentence shares content with the ledger claim it cites (2+ content words, 1 when the claim is 3 words or fewer) and every [n] is a ledger row; a hypothetical (Reverses if, Stop if) carries no citation unless the row says it |
| C18 | quality | `eval.py checks --quality` | no ledger row cites a source_quality.exclude domain; a source_quality.weak domain is never C1 or C2; fewer than 3 ledger rows carry the run's own date unmarked (those are read dates: give the source's date, or 'seen' when it has none) |
| C19 | render | `eval.py pdf (also eval.py render OUT.pdf)` | every page: no ink within 0.12in of a page edge, no word outside the 0.3in side margins; no page ends more than 0.5in above its footer margin; the schema's pairs (B3|B4, B5|B6, B7|B8) print side by side; page 1: the logo is whole in the top-right masthead; no block runs across a page break: page 2 opens on Who decides (B7, as in the schema) and no table prints its header row on two pages |
| C20 | colors | `eval.py pdf (also eval.py render OUT.pdf)` | every printed character is Midnight #0F2744, black #000000 or white #FFFFFF (no gray: the page must read when printed); the hairline #E8EAED is for rules only, never text |
| C21 | battery | `eval.py checks --battery (the Run row); eval.py battery TRANSCRIPT --depth D [--brief brief.md or OUT.pdf] (the searches)` | the Run row ends 'N searches (B base) in M rounds' (a brief run before osint.battery.since is exempt; the base count is required from osint.battery.base_since), N at least the base pass plus the depth's round floor; in the run's history (Claude Code, Codex, ChatGPT or Claude app: eval.py battery reads each) the base pass comes first, one search per source type the depth enables that has a query template, each carrying its template's terms; then the rounds, each a 'Round N (name):' line in the reasoning and the searches after it or, without such lines, one step's batch of searches, every round the depth enables in order, at least the battery's queries per round and the share with an operator or a domain filter, round 1's LinkedIn query through the domain filter; no linkedin.com page requested and no browser tool called; the reply holds no round line or query list, no text between the first and the last search, and at most five status lines of 30 words (a subagent's own text is not the reply); the Run row's counts match the history |
| C22 | ask | `eval.py battery <history> [--profile ~/.pcp/profile.yaml] (also eval.py offer-conflict)` | every question goes through the host's native question tool (a typed numbered list only where the host has none, or after an empty answer), each call with its own line of the reply right before it saying what skip does; no search, page open or file work between the question and the answer; a popup that came back empty is asked again in the reply; a request that names a business other than the saved offer was asked about before the first search |
| C23 | records | `eval.py records <folder with claims.jsonl, coverage.json, read.json> --depth <depth> --brief brief.md` | every claim has every field and valid tag, grade, confidence; coverage has every field, a count for each of the 12 source types equal to what claims.jsonl holds, rounds and searches, and a status S2-5 confirms; read.json has the six rubric dimensions with every field, the rubric's phrase for each band, and the tiers its observations support; the brief's source-type count, status and Evidence tier agree. Run it, and say what it reports, before the run is called done |
| C24 | kept | `eval.py kept <folder> [--allow N=dead or N=excluded]` | every cited fact of the draft eval.py assemble recorded at the folder's first build (draft.lock.json; brief.draft.md and script.draft.md unchanged) is still a ledger row of the final brief, which is what fields.json assembles to now; a fact dropped because its page is dead (cited nowhere else in the final, and not answering) or it touches an excluded topic is named with --allow N=dead or N=excluded, checked, and told to the user; a page, a URL or fit excuses nothing |
| C25 | grading | `eval.py checks --grading` | from grading.since, every ledger row prints its grade (Measured, Derived, Inference, Not determined), how it was found (Direct, Search, LinkedIn, Yours) and its strength as one plain word (Strong, Solid, Weak, Inferred); the note line keys the four; a strength is never stronger than its caps allow (a weak domain, a Search or LinkedIn tag, a Derived or Inference grade): a weak source never reads Strong or Solid |
| C26 | schema | `eval.py checks --schema; eval.py assemble --check <folder>` | brief.md and script.md have exactly the structure of the forms table: the masthead, every block's heading and title in order, only the labels its form allows with the required ones present, its tables' headers, B9's subheads, the ledger's header and label grid, the script's title and subtitle; and, where fields.json exists, both files are byte for byte what eval.py assemble builds from it |

## Rule tests

Each rule fails when:

| Row | Fails when |
|---|---|
| CAL-1 | A profile with Q1-Q8 answered and no Q9 -- the run asks Q9 only. A complete profile -- it asks nothing. |
| CAL-2 | Skip Q5 -- profile shows research.depth standard, defaulted true; the masthead reads "Depth standard". |
| CAL-3 | Three debriefs with facts_used > 80% must produce a proposal, and the profile must be unchanged until answered. |
| CAL-4 | Give a one-page file -- the profile holds its path and summary, and a fact from it prints with tag Yours. Give a .pptx -- one line names the supported types and profile.yaml's sha256 is unchanged. |
| CAL-5 | A run on a host with a question tool whose reply types 'Reply with one number per line, such as 1, 4, 1, 1' fails eval.py battery (C22); a popup with no line of the reply of its own right before it (the second and third setup calls of the Claude desktop run, Oct 17, had none), or one the run did not wait for (searches before the user's answer), or one that came back empty and was not re-asked in the reply, fails it too. A saved offer 'transaction advisory' and a request about AI meeting prep -- eval.py offer-conflict exits 1 and the run asks first. |
| S1-1 | Run with a name only -- the run must ask, not search. |
| S1-2 | Seed an ambiguous name -- the run must present the candidates and stop. |
| S1-3 | A 9-row CSV must be refused with the count. |
| S1-4 | An intake with an objective and no relationship -- the run asks nothing before collection. A request about AI meeting prep with a saved transaction-advisory offer -- the run asks which offer to use before its first search (eval.py battery --profile fails C22 otherwise). |
| S2-1 | A run with no files and no answers holds only Direct, Search and LinkedIn facts, and its transcript requests no linkedin.com page the user did not give; a page that returns a login wall is in coverage.failed_urls. |
| S2-2 | A claim missing any field is dropped by eval.py duf and counted as dropped. |
| S2-3 | Seed a claim tagged exclusion health -- it must not appear in any output file. |
| S2-4 | Disable WebFetch -- coverage must show 0/N attempted and status LIMITED, never FULL. |
| S2-5 | Remove all C1/C2 claims from one family below threshold -- status flips to LIMITED. |
| S2-6 | With depth standard or deep, coverage must show family F12 attempted. |
| S2-7 | A run on a public executive requests no linkedin.com URL the user did not give and calls no browser tool (its transcript shows search calls only, for LinkedIn); the profile's search result is a ledger row cited to linkedin.com/in, and B4 and Coverage read 'LinkedIn: read from search results'. A LinkedIn post cited as [linkedin.com](...) fails C16. The identity-lock example reads 'not read: no matching profile'. A brief that says 'read in your browser' fails C16 (fixtures linkedin_search.md, linkedin_browser.md, linkedin_declined.md, linkedin_missing.md, linkedin_declined_with_row.md). |
| S2-8 | A brief citing mexc.com as C2 fails C18; a Reverses if line citing the intake row fails C17; the link check reports blocked separately from dead. |
| S2-9 | eval.py battery <the run's history> --depth <depth> (C21) fails a run that sends no base pass (fewer searches before its rounds than the depth's source types with a query template, or a source type whose template terms no search carries), skips a round its depth enables, splits a round over several steps, sends fewer than the battery's queries in a round or too few with operators, sends round 1's LinkedIn query as typed site: where the tool has a domain filter, prints a round line, a query list or any other text in the reply between its first and last search (S2-10), prints a Run row whose counts differ from the history, or cites a page it never requested (LinkedIn aside; a page that refused the fetch was requested). eval.py checks --battery fails a Run row from Oct 16 on that does not give the base count. |
| S2-10 | eval.py battery <the run's history> (C21) fails a reply that holds a 'Round N' line or any list of queries, a message between the first and the last search, a status of over 30 words or more than five of them; a Codex run that printed all ten rounds, a ChatGPT run that printed 'Round 1 (identity): query | query', and a Claude desktop run of Oct 17 that answered each of the host's check-in reminders with a progress note while it wrote the brief (10 status lines), fail it. |
| S2-11 | A Claude Code run with two targets starts two Agent subagents in one message and its reply holds only status lines (eval.py battery counts a subagent's own text apart from the reply and still counts its searches); a run on a host with no job runs the stage in the thread and still passes S2-10. |
| S3-1 | A target with only role-archetype claims must render every dimension as tier low and the script must contain no influence sequence. |
| S3-2 | Delete one corroborating claim -- the tier must drop and P6 must disappear on re-run. |
| S3-3 | Grep B6 for a move not in rubric.*.meaning -- the run is rewritten. |
| S3-4 | Depth standard -- no hypotheses table in B8; depth deep -- the table, with a disproving claim [n] per hypothesis. |
| S4-13 | A brief with a block renamed, a stray label, a table header changed, a block out of order or a hand edit after assembly fails eval.py checks --schema and eval.py assemble --check (self-test: assembled fixture passes, each mutation trips). |
| S4-1 | eval.py duf reports unbound or dangling > 0 -- the run must rewrite before render. |
| S4-2 | A brief with a sentence containing no claim id and no target-specific noun fails checks.swap. |
| S4-3 | On a script-capable host the output directory contains exactly one .pdf and no .md/.html after a run; eval.py pdf on it exits 0 (3 pages, the script on page 3 only, the ledger on page 2). |
| S4-11 | eval.py ratchet: every frozen target's duf_pp meets its floor at 10 pt and 3 pages. |
| S4-12 | A run whose coverage record lacks the per-source-type counts, or whose read.json lacks a field, fails eval.py records (fixtures records_broken/); a ledger row whose page is not in claims.jsonl fails it too; eval.py battery reads a Codex rollout, a ChatGPT and a Claude app export, and Claude Code's, without 'unavailable' (self-test). |
| S4-10 | Run with no Bash tool: the reply holds the label, the three page markers, every B1-B10 and P1-P9 title in order, a ledger row per cited [n], and no plain_words.banned word; eval.py chat on the saved reply exits 0. |
| S4-4 | Feed a 900-word section -- the engine must exit non-zero naming the section. Cut one cited fact from a draft to make it fit, or excuse it with --allow <page> or any reason but dead or excluded -- eval.py kept exits 1 and names the fact (the Codex run, Oct 16, cut 5 of 23; the Claude desktop run, Oct 17, cut 10 of 27 and excused each with --allow <page>: fixture kept_oct17). A first build whose page cannot hold its facts -- eval.py assemble writes nothing and records no draft. |
| S4-5 | Extract page 1 text -- the meta line has all six fields; no page footer holds a metric. |
| S4-6 | No recent wins found -- the Recent wins line is absent, not blank or padded. |
| S4-7 | Write five Still open questions, or one whose label is no gap above, or none while gaps exist -- eval.py checks fails C12 (fixtures control_broken.md, gaps_table.md). |
| S4-8 | Put SOCMINT in B3 -- eval.py checks fails C11. |
| S4-9 | Set Q9 new -- P1, P3 and P4 each carry a Why line; set experienced -- none does. eval.py checks --experience <Q9> fails C15 otherwise (fixtures exp_new.md passes as new, exp_experienced_with_why.md fails as experienced). |
| S5-1 | Lower a family weight so a target's duf_pp drops -- ratchet must exit non-zero and name the target. |
| S5-2 | The debrief template has exactly four fields. |
| S5-3 | Run improve -- the only file written is evals/proposals/<date>.patch. |

## The metric and the commands

- **metric:** duf_pp
- **definition:** decision-useful fact = a ledger number [n] that is (a) cited in B1-B9 or P1-P9, (b) a B10 row with what it says, source, grade and date (tag and confidence in claims.jsonl), (c) target-specific (passes swap). duf_pp = count / pages.
- **positive_control:** evals/fixtures/control_12.md
- **negative_control:** evals/fixtures/control_broken.md
- **frozen_targets_dir:** evals/targets
- **ratchet_file:** evals/ratchet.json
- **policy:** floor_is_best_ever_never_regress
- **baseline_required_before_claims:** True
- **Method verbs (C8):** we scrape, we ingest, our pipeline, our model, we crawl, our algorithm

Commands of `eval.py`: `eval.py duf`, `eval.py checks`, `eval.py pdf`, `eval.py cites`, `eval.py links`, `eval.py render`, `eval.py battery`, `eval.py records`, `eval.py kept`, `eval.py offer-conflict`, `eval.py chat`, `eval.py assemble`, `eval.py hardcoded`, `eval.py gates`, `eval.py versions`, `eval.py skill`, `eval.py parity`, `eval.py concordance`, `eval.py self-test`, `eval.py ratchet`, `eval.py improve`.

