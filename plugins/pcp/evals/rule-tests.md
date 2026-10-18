<!-- GENERATED from pcp.yaml (sha256:766c3fe90a1c) by render_skill.py -- edit pcp.yaml, never this file -->

# Rule tests and worked examples (for developers)

For developers and eval.py: no step of SKILL.md loads this file, so none of it is read at run time. Every rule is in SKILL.md or a reference a step loads; this file holds only how each rule is made to fail, and the worked examples behind the in-chat self-check.

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

## Worked examples

The numbers are the items of the S4-10 self-check.

- **S4-10** (2) **Take.** Jane Doe has led Alder Grey since 2021 [1] and buys patience [3]. **Evidence:** her 2021 start [1] and her letter's 'we buy patience' [3]. **Action:** open on her letter [3]. **Avoid:** a fee-led pitch [4].
- **S4-10** (3) **Next step:** send the one-page example by Oct 17.
- **S4-10** (4) **Reverses if:** she names a tooling owner. / **Stop if:** they say tooling is settled. / **Capture:** who owns AI choices.
- **S4-10** (5) Decision maker: Who signs off?
- **S4-10** (6) **Recent wins:** Jul 30, 2026: Azure passed $100 billion [3].
- **S4-10** (7) 'Outside prep may look redundant to Microsoft [4].', never a bare 'Outside prep may look redundant.'
- **S4-10** (8) '## Take', '## Questions that close gaps'
- **S4-10** (10) 'seen Oct 14, 2026'
- **S4-10** (12) no donations, no FEC filings
- **S4-10** (14) 'called for an AI emergency brake [3]' cites '| [3] | Called for an AI emergency brake |', not '| [3] | Oct 10 post: contain the model |'
