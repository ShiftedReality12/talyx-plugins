<!-- GENERATED from pcp.yaml (sha256:ddde3e1ee80e) by render_skill.py -- edit pcp.yaml, never this file -->

# Checks: commands and when each passes

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
| C7 | never_say | `eval.py checks --never-say` | no never_say phrase appears outside P8; on a run whose jurisdiction keeps a formal register (guardrails.formal_opener: APAC, read from the Run row), P1 never calls the person by first name alone |
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
| C21 | battery | `eval.py checks --battery (the Run row); eval.py battery TRANSCRIPT --depth D [--brief brief.md or OUT.pdf] (the searches)` | the Run row ends 'N searches (B base) in M rounds' (a brief run before osint.battery.since is exempt; the base count is required from osint.battery.base_since), N at least the base pass plus the depth's round floor; in the run's history (Claude Code, Codex, ChatGPT or Claude app: eval.py battery reads each) the base pass comes first, one search per source type the depth enables that has a query template, each carrying its template's terms; then the rounds, each a 'Round N (name):' line in the reasoning and the searches after it or, without such lines, one step's batch of searches, every round the depth enables in order, at least the battery's queries per round and the share with an operator or a domain filter, round 1's LinkedIn query through the domain filter; no linkedin.com page requested and no browser tool called; the reply holds no round line or query list, no text between the first and the last search, and at most five status lines of 30 words (a subagent's own text is not the reply; the closing reply, the run's last message, is not a status line); the Run row's counts match the history |
| C22 | ask | `eval.py battery <history> [--profile ~/.pcp/profile.yaml] (also eval.py offer-conflict)` | every question goes through the host's native question tool (a typed numbered list only where the host has none, or after an empty answer), each call with its own line of the reply right before it saying what skip does; no search, page open or file work between the question and the answer; a popup that came back empty is typed in the reply, once; a request that names a business other than the saved offer was asked about before the first search |
| C23 | records | `eval.py records <folder with claims.jsonl, coverage.json, read.json> --depth <depth> --brief brief.md` | every claim has every field and valid tag, grade, confidence; coverage has every field, a count for each of the 12 source types equal to what claims.jsonl holds, rounds and searches, and a status S2-5 confirms; read.json has the six rubric dimensions with every field, the rubric's phrase for each band, and the tiers its observations support; the brief's source-type count, status and Evidence tier agree. Run it, and say what it reports, before the run is called done |
| C24 | kept | `eval.py kept <folder> [--allow N=dead or N=excluded]` | every cited fact of the draft eval.py assemble recorded at the folder's first build (draft.lock.json; brief.draft.md and script.draft.md unchanged) is still a ledger row of the final brief, which is what fields.json assembles to now; a fact dropped because its page is dead (cited nowhere else in the final, and not answering) or it touches an excluded topic is named with --allow N=dead or N=excluded, checked, and told to the user; a page, a URL or fit excuses nothing |
| C25 | grading | `eval.py checks --grading` | from grading.since, every ledger row prints its grade (Measured, Derived, Inference, Not determined), how it was found (Direct, Search, LinkedIn, Yours) and its strength as one plain word (Strong, Solid, Weak, Inferred); the note line keys the four; a strength is never stronger than its caps allow (a weak domain, a Search or LinkedIn tag, a Derived or Inference grade): a weak source never reads Strong or Solid |
| C26 | schema | `eval.py checks --schema; eval.py assemble --check <folder>` | brief.md and script.md have exactly the structure of the forms table: the masthead, every block's heading and title in order, only the labels its form allows with the required ones present, its tables' headers, B9's subheads, the ledger's header and label grid, the script's title and subtitle; and, where fields.json exists, both files are byte for byte what eval.py assemble builds from it |

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

