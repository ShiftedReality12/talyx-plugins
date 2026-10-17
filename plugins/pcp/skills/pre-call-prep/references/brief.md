<!-- GENERATED from pcp.yaml (sha256:b45e6e98f12b) by render_skill.py -- edit pcp.yaml, never this file -->

# The brief and the script: blocks, fields and writing rules

Loaded by Stage 4 of SKILL.md.

**Plain words.** Nothing the user reads -- the PDF, replies, setup questions, the listing -- uses military, intelligence-trade or technical jargon, or a grade or rule code (C3, S2-9): say 'a single, weaker source'. The closing reply too: after the call, offer 'after-call notes' (four fields), never a debrief. Their own quoted words are exempt. Never write a word banned: OSINT, SOCINT, SOCMINT, HUMINT, human intelligence, SIGINT, intelligence cycle, tradecraft, collection plan, competing hypotheses, ACH, target package, asset, source handling, exploitation, debrief, kill chain, dossier, duf_pp, claims.jsonl, read.json, source families, scrape, scraped, scraping, crawl, LLM, or an internal id
(C1-C4, F1-F12, row ids). Allowed only inside these phrases: asset manager, asset managers, asset management, asset & wealth management, asset and wealth management, asset class, asset classes, asset allocation, asset owner, asset owners, asset-light, asset-heavy, asset-backed, asset-based, asset-liability, asset and liability, asset base, asset quality, asset growth, asset mix, asset value, asset values, net asset value, asset price, asset prices, asset sale, asset sales, asset purchase, asset purchases, asset deal, asset finance, asset servicing, asset gathering, real asset, alternative asset, digital asset, fixed asset, financial asset, hard asset, single-asset, multi-asset.
Use "source types", not families; "the person you're meeting", not target. Call the deliverable the Intelligence Brief, nothing else.

## The PDF: pages 1-2, the Intelligence Brief

`brief.md` starts with `# Full Name`, then the identity line (`**Organization** | Role, since year | City, if public`),
then the meta line (`Meeting: ... | Prepared for: ... | Depth: ... | Sources: <types> of 12 source types, <the ledger's fact count> cited | Status FULL or LIMITED | Prepared Mon D, YYYY`).
Then one `## Bn Title` per block, in order. Word budgets are the page budget; the renderer fails, never spills, past 3 pages.

| Id | Block | Words | Prints when | Content |
|---|---|---|---|---|
| B1 | Take | 45 | always | One paragraph: **Take.** who they are and why this meeting matters to them now, in one sentence, every clause cited. **Evidence:** the one to three facts it rests on [n]. **Action:** the first move in the room, on the fact behind it [n]. **Avoid:** the one move that loses the meeting, on the fact that shows why [n] -- never a generic line. It adds no fact the blocks below don't cite. |
| B2 | Questions that close gaps | 130 | always | 4 to 6 numbered questions, each <= 40 words, on the fact it rests on [n]; under each, one indented bullet: **Decides:** what the answer tells you. **Ask:** whom -- the person, or who else is in the room. Ordered by what they decide; the mix follows the meeting type (Q4). |
| B3 | Who they are | 80 | always | Bullets, label first: **Role:** title and since when [n] (required). **Path:** the prior roles that matter, with education and credentials [n]. **The organization:** in its own words, plus one scale figure [n]. **What changed:** one to three dated items, newest first [n]. **Recent wins:** none to two dated, cited results [n]. Path, The organization and What changed read Not determined if not found; Recent wins is left out. From F1 F2 F3 F4 F9. |
| B4 | In their words | 60 | always | 2-3 bullets, label first: **Topic, where, when:** "their exact words" [n]. None found: one line of themes from their public presence [n]; nothing at all: Not determined. Then always one last line, not a bullet: **LinkedIn:** read from search results, **LinkedIn:** read from your file, or **LinkedIn:** not read: and the reason (S2-7). From F5 F6 F8 and LinkedIn. |
| B5 | Signals and what to do with them | 65 | always | A table: | Observable | What to do with it |, three rows in this order: their priority and the gap, in their words [n] -> why this meeting matters to them; where your offer connects (Q8) [n] -> the bridge: the outcome you offer, not the method; the trigger, why now [n] -> the urgency, never invented. From F3 F10 F11 and Q8. |
| B6 | Behavioral profile | 110 | always | A table: | What the record shows | Your move |, six rows, one per rubric dimension, each starting with its label (Pace and control, How they take recognition, Appetite for detail, Appetite for risk, How they take disagreement, How they keep score) and a colon: the cited observation in at most 8 words [n] -> the rubric's move word for word. A dimension with no evidence is the bare label and No read (| Pace and control | No read |), never "none found". Then one line: **Evidence tier:** high, medium or low (it governs page 3). A cited observation and a move, never a verdict on their character. |
| B7 | Who decides | 25 | always | Bullets: **Decision maker:** who signs off [n]. **The gate:** what must be true, or who must agree, before a yes [n]. **Relationship holder:** who the relationship runs through [n]. Unknown: Not determined (a gap Still open may ask). From F1 F3 F9 F11. |
| B8 | Strongest case against | 70 | always | Up to 3 bullets: **Against:** the best evidence against your read [n]. **Reverses if:** what would flip it. **Confirm first:** each fact the brief leans on that is graded Inference or Not determined (outside the behavioral profile), marked [UNVERIFIED], with the question that settles it [n]; none: leave the bullet out. None found against: No counter-evidence found. Deep runs only, then `### What they may want from this meeting` and a table | Hypothesis and why it fits | Test: who answers, and what would disprove it |, up to 3 rows, each with the claim that would disprove it [n]. From F12; litigation stays off the page. |
| B9 | Meeting angle | 90 | always | One label per bullet (only The ask and its Fallback share one). `### This meeting` then bullets: **Frame:** what this meeting is, in their terms; not a pitch. **Lands:** [n]. **Repels:** [n]. **What to bring:** one thing of value [n]. **The ask:** specific and bounded, who and how long [n] · **Fallback:** the smaller ask. **Stop if:** the answer that means drop the ask. `### Meeting two` then **Meeting two:** the next conversation if this one lands, on a fact from this brief. **Meeting three:** where it goes after that. `### After the meeting` then **Capture:** what to record from the room that the public record couldn't give. From Q8 and B3-B8. |
| B10 | Evidence ledger | 405 | always | One line: {n} facts cited; status {FULL or LIMITED} at {n} of 12 source types; the strength key. A weak source never reads Strong or Solid. Dates are the sources' own; 'seen' marks the day an undated source was read. Then the table | # | What it says | Source | Grade | Date |, exactly one row per cited fact in order of first use (never grouped): [n] · the fact in at most 30 characters · [domain](url), then ' · ' and how it was found: Direct, Search, LinkedIn or Yours (a file name for your own files is Yours) · the grade Measured, Derived, Inference or Not determined, then ' · ' and the source's strength as one plain word from grading.words (Strong, Solid, Weak, Inferred; the ledger's note line keys them: 'Strong: primary, dated' ...) · the source's own date, Mon D, YYYY, or Mon YYYY when the source gives only a month (claims.jsonl published); only for an undated source, the day it was read, marked 'seen Mon D, YYYY'. The tag and the strength print on the page (C25) and stay in claims.jsonl as tag and confidence (C1-C4); the codes themselves never print. Then a label grid (empty header row) with four rows: **Coverage** -- n of 12 source types in the base pass, the rounds run (M of N), what was not found and why, and LinkedIn: read from search results, LinkedIn: read from your file, or LinkedIn: not read: and B4's reason. **Still open** -- at most 4 gaps, highest value first, each with the question that closes it in the room ('Label: question?', joined by ' · '). **Left out on purpose** -- the excluded topics, never the facts. **Run** -- date · depth · meeting type · prepared for (role) · domain · jurisdiction · status · decision-useful facts per page · N searches (B base) in M rounds (both passes as sent, S2-9). |

Domain vocabulary: wealth: book, AUM, custodian, fee compression, succession, next-gen; pe: dry powder, DPI, add-on, hold period, exit; saas: ARR, NRR, champion, security review, procurement, renewal.

## The PDF: page 3, the Meeting script

`script.md` starts with `# Meeting script`, then one line: *Facts choose the moves; read the room, not the record · Full Name, Organization · Prepared Mon D, YYYY*.
Then one `## Pn Title` per section, in order; a section whose Prints when is not met is left out, not blank.

Beats by meeting format:
- **intro**: open -> credibility in one line -> one insight they did not have -> ask for the second meeting
- **discovery**: open -> situation question -> gap question -> impact question -> next-step test
- **close**: open -> restate their words -> the outcome -> the safeguard -> the ask
- **relationship**: open -> acknowledge what changed -> one thing of value -> one forward question

| Id | Section | Words | Prints when | Content |
|---|---|---|---|---|
| P1 | Open | 70 | always | Bullets: **Hook:** two sentences, said aloud, on a cited fact [n] -- in italics. **Credibility:** who you are, in one line, 30 seconds [n]. **Insight:** one thing they didn't have [n]. **Rule:** how to hold the opening's rapport through the questions. |
| P2 | Question order | 130 | always | Bullets: **Beats:** one line per beat of the meeting type (script.beats_by_format for Q4), each on the [n] it rests on. Then **Story:** **Process:** **Gate:** **History:** **Commitment:** -- B2's questions word for word, in the order the room needs. |
| P3 | Objections: name it, then answer | 90 | always | 3 bullets: **Their likely objection:** *say it before they do, then the answer, at most 30 words* [n]. |
| P4 | Close | 70 | always | Bullets: **Restate:** ask what would make it an easy yes, then say it back in their words. **Real deadline:** a date that actually moves [n]. **The ask:** B9's ask · **Fallback:** B9's fallback. **Follow-up:** what you promise to send, and when. |
| P5 | Read the room (watch, do not assume) | 50 | evidence tier medium or high | Bullets: **Fast, wants the answer:** **Asks for terms and data:** **Talks about people:** **Big picture, ideas:** -- what you do, from B6. |
| P6 | Influence, one fact behind each | 70 | evidence tier high and caller authority high; each principle only where a cited fact backs it | Bullets, only for principles a cited fact backs: **Authority:** **Reciprocity:** **Commitment:** **Social proof:** **Liking:** **Scarcity:** (real limits only; never invented urgency) [n]. |
| P7 | If it stalls | 50 | always | 2-3 bullets: **The move:** what restarts the conversation, from a fact in this brief [n]. |
| P8 | Guardrails | 45 | always | Bullets: **Rule:** what never to promise or claim, for the jurisdiction (Q7). **Never say:** the guardrails.never_say phrases and the domain's forbidden claims, quoted. |
| P9 | Next step | 25 | always | One line: **Next step:** the one action and its date. |

Never say: "Does that make sense?"; "Is this helpful?"; "No pressure"; "You'd know better than me"; "Just checking in".
Forbidden claims by domain (P8 quotes the saved domain's): wealth: "guaranteed", "outperform", "beat the market"; pe: "guaranteed return", "no downside"; saas: "unlimited", "zero risk".

## fields.json: what you fill (S4-13)

You never write brief.md or script.md. Fill `fields.json` -- the keys below, per block; text cites a claim as `[c<id>]` (claims.jsonl),
the assembler numbers the ledger -- then run `python3 eval.py assemble <folder>`. A key marked optional may be left out; `missing` prints
as shown. Labels print exactly as the forms table in pcp.yaml says.

| Block | Form | Keys |
|---|---|---|
| B1 | labels_para | `take` (Take), `evidence` (Evidence), `action` (Action), `avoid` (Avoid) |
| B2 | questions | `b2`: 4 to 6 of `q`, `decides`, `ask` |
| B3 | bullets | `role` (Role) else 'Not determined', `path` (Path) else 'Not determined', `organization` (The organization) else 'Not determined', `changed` (What changed) else 'Not determined', `wins` (Recent wins) optional |
| B4 | quotes | `quotes`: list of `label`, `quote`, `cite`; or `themes`; the LinkedIn line is computed |
| B5 | table | `b5`: 3 of `observable`, `action` (priority, offer, trigger) |
| B6 | profile_table | `b6`: one observation per rubric dimension id (dominance, status_sensitivity, information_appetite, risk_tolerance, ego_vulnerability, competitive_drive); the moves and the tier come from read.json |
| B7 | bullets | `decision_maker` (Decision maker) else 'Not determined', `gate` (The gate) else 'Not determined', `relationship_holder` (Relationship holder) else 'Not determined' |
| B8 | case_against | `against`: up to 3 of `against`, `reverses_if`; `confirm_first`; deep: `hypotheses` of `hypothesis`, `test` |
| B9 | angle | `frame` (Frame), `lands` (Lands), `repels` (Repels), `bring` (What to bring), `ask` (The ask) + `fallback`, `stop_if` (Stop if), `meeting_two` (Meeting two), `meeting_three` (Meeting three), `capture` (Capture) |
| B10 | ledger | computed from claims.jsonl, coverage.json and `still_open` (up to 4 of `label`, `question`) |
| P1 | bullets | `hook` (Hook), `credibility` (Credibility), `insight` (Insight), `rule` (Rule) |
| P2 | question_order | `beats`: list; `order`: B2 question numbers for story, process, gate, history, commitment |
| P3 | objections | `p3`: 3 of `objection`, `answer` |
| P4 | bullets | `restate` (Restate), `deadline` (Real deadline), `ask` (The ask), `followup` (Follow-up) |
| P5 | bullets | `fast` (Fast, wants the answer), `data` (Asks for terms and data), `people` (Talks about people), `ideas` (Big picture, ideas) |
| P6 | bullets | `authority` (Authority) optional, `reciprocity` (Reciprocity) optional, `commitment` (Commitment) optional, `social_proof` (Social proof) optional, `liking` (Liking) optional, `scarcity` (Scarcity) optional |
| P7 | repeat | `moves`: 2 to 3 moves |
| P8 | guardrails | `rule`; the never-say list and the domain's forbidden claims are computed |
| P9 | line | `next_step` |
| masthead | -- | `target` (`name`, `org`, `role_since`, `city` only when a source confirms it), `meeting`, `prepared` (Mon D, YYYY) |

## Rules moved out of SKILL.md

The full text of the rows SKILL.md summarises; the rule is this text.

- **S4-4** If the tightest density rung still overflows 3 pages, the run FAILS with the section word counts; it never truncates or spills. An overflow is fixed only by cutting words in the sections the renderer names -- shorter sentences, shorter 'What it says' cells, fewer adjectives; never a cited fact, a ledger row or a source -- and never --columns, --brief-pages or --max-pages, never dropping or moving a block. Before the first fit pass, copy the complete draft (brief.draft.md and script.draft.md); after the last, run eval.py kept brief.draft.md brief.md --draft-script script.draft.md --final-script script.md (C24): it must find every cited fact still in the ledger and still cited, in the brief or the script. A fact dropped for another reason (a dead link, an excluded topic) is named to the user and passed to eval.py kept with --allow <page>.
- **S4-11** Fact density (the ratchet's metric, decision-useful facts per page, never drops). Standard depth aims at 18 or more distinct cited facts across the 3 pages, at least 6 per page. Spend words on facts, not framing: a line that can carry a new cited fact carries one; cut uncited connective sentences; each B2 question, B3 bullet, B5 row, B8 bullet and P3 answer rests on a different [n] where the evidence allows. Before writing Not determined for Role since, Path, The organization or Decision maker, run one targeted search of the primary source (official bio, annual report or proxy statement, newsroom); for a public company these are almost always public. The ledger's What it says stays under 8 words so each row is one line. Each No read or Not determined is a gap on the page, so evidence that fills one frees space for a fact: search two long-form interviews or earnings-call remarks for the six reads before writing No read. Keep each Still open question under 10 words. Before rendering, run eval.py duf: below 6.0 per page, replace a repeated [n], an uncited line or a filled-in-able gap with a new cited fact from the claims, then re-check fit; if the brief overflows, cut words, not facts.
- **S4-12** Compose from the records, then validate before 'done'. Write brief.md and script.md from claims.jsonl, coverage.json and read.json alone (records, C23): a fact, a ledger row or a source that is not in claims.jsonl is not in the brief, and a script that carries the facts or wording itself (a compose file with the claims typed into it) is not the brief. Complete and validate the records first (eval.py records <folder> --depth <depth> --brief brief.md), then compose, then run the checks (eval.py checks, duf, pdf, links, kept, battery). The closing reply names each check and its result and says the run is done only when every one has passed; a check that could not run is named with the reason and what was done instead, never reported as 'unavailable' when the host's history file can be read (eval.py battery --latest, or pass the file: Claude Code, the newest ~/.claude/projects/<folder>/*.jsonl; Codex, the ~/.codex/sessions/**/rollout-*.jsonl that carries $CODEX_THREAD_ID; ChatGPT or the Claude app, the conversations.json of the account's data export).
- **S4-13** The model never writes brief.md or script.md. Fill fields.json -- one entry per field of the forms table, each claim cited as [c<id>], the ledger numbers assigned by the assembler -- then run `python3 eval.py assemble <folder>`: it builds both files from the forms table, claims.jsonl, coverage.json, read.json and the saved profile, the same structure every run, with the masthead, the behavioral profile's moves, the ledger (grade, how found, strength, date), the Coverage, Left out on purpose and Run rows computed, not typed. A problem it reports is fixed in fields.json or the records, never in the output. Check the structure with `python3 eval.py assemble --check <folder>` (C26). A host with no shell writes the in-chat brief by S4-10 and checks it with the same forms table.

