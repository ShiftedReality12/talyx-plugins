# Changelog

All notable changes to the pcp plug-in. Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/); versions follow `VERSIONING.md`.
The version of record is `registry_version` in `pcp.yaml`; `eval.py versions` fails if any manifest, marketplace entry, generated header or the
newest entry below disagrees with it.

## [3.1.2] - 2026-10-18

A patch: fixes and wording, nothing of 2.1.0 removed or weakened (parity 0 removed, 0 open; gates 0 looser; reachability 403/403).
Branch `restore-2026-10-16`, tag `pcp-v3.1.2`.

### Fixed
- **Cited facts are no longer lost to fit the page.** The Oct 17 Claude desktop run cut its brief from 27 cited facts to 18 and excused each cut as
  allowed. Now `eval.py assemble` records the draft itself: the folder's first build that fits its 3 pages, with a lock file. `eval.py kept <folder>`
  compares the final against that record, and `eval.py battery` fails a run whose history removes or rewrites the recorded draft. A cut is excused only for a dead page or an excluded topic (`--allow N=dead` or `N=excluded`), never for
  fit or by naming a page. A fit pass cuts in a fixed order: wording, then the ledger cells, the "What they may want" table, uncited framing, and an
  uncited optional row. A fact that no longer fits in its block keeps its ledger row and a short cited mention. Fixture `kept_oct17`: the real
  27 -> 18 cut fails, the bypass fails, and the same 27 facts in shorter wording pass. Body text stays 10 pt on 3 pages.
- **The search check reads Claude desktop runs correctly.** A Claude desktop session keeps its research in subagent files; `eval.py battery` now reads them
  in time order and splits the base pass from the rounds by what each search carries. Its counts match an independent count of the Oct 17 run
  (rounds 6, 7, 7, 6, 6; 14 base; 9 later searches).
- **The two real misses of that run are fixed in behaviour.** Each setup question call gets its own skip line right before it. The run stays quiet
  through writing and checking: a host's progress reminder is answered by the stage's one status line. The checker was not loosened.

### Restored to 2.1.0's strictness
- The swap test (C1) reads every fact block B1-B9, including the questions (B2) and the meeting angle (B9).
- 2.1.0's block caps where a block maps: the meeting angle 80, guardrails 40, influence 60 with at most 3 moves, each from the behavioral profile;
  the opening's hook at most 2 sentences and 40 words; the ask, fallback and follow-up together at most 50 words. The brief stays 1,080 words.
- "Public sources only. Nothing behind a login, no paid data the user has not supplied, no scraping." is back, word for word. The user's own
  notes and files stay tagged Yours.
- The in-chat fallback (a host that cannot make the PDF) stays, approved by Daniel on Oct 13.

### Setup questions
- No setup text says "targets", "Target kind", "news families" or "claims.jsonl", except Q2's and Q7's original wording, which stays under
  Daniel's Oct 17 decision (open for him to revisit). The render fails if any of these words comes back.
- Fast says 5 source types (it runs 5). Deep promises what runs: "what they may want" and more searches per round, not a network pass that was
  never built. APAC's "formal-register openers" is now built: the opening calls the person by title and family name, never the first name alone.

### Leaner
- The test behind each rule and the in-chat worked examples moved to `evals/rule-tests.md`, which nothing loads at run time. Repeated rules have one
  home and pointers. The ten contradictions found by the Oct 17 audit are resolved: seven by a fix, and three (Q2's and Q7's words) by the
  plain-words rule naming that wording as its one exception, while it stays under Daniel's lock. Words a run reads: SKILL.md 3,232 -> 3,142; with its references,
  15,239 -> 14,318 (PDF host) and 16,132 -> 15,057 (in chat); the chat apps' knowledge file 11,297 -> 10,631 (`wc -w`, 7ee48fb -> the tag).
- goodfest.westfield.com left the never-cite list (added without a reason). thefabulous.co stays on the weak list, with its reason. The rubric's
  "2.0.0-public" is explained as the rubric's own label.

## [3.1.1] - 2026-10-17

**3.1.1 supersedes the "3.1.0" on `origin/main` at `32badc4`.** That commit (and the `pcp-3.1.0-rc1` / `pcp-3.1.0-rc2` tags, and any copy installed from it)
is the pre-restore build: it carries the version 3.1.0 but not the restore, the trim or the decisions below. Hosts that cached "3.1.0" need this
release to see an update. Branch `restore-2026-10-16`, tag `pcp-v3.1.1`.

### Restored toward the original talyx-ai 2.1.0 (nothing of 2.1.0 removed; a no-drift guard added)
- A frozen 2.1.0 baseline (`evals/baseline-2.1.0.json`, 403 items) and `evals/DECISIONS.yaml`: `eval.py parity` fails any item of 2.1.0 that is removed or
  weakened without an approved decision, and any schema section (forms, grading, records, page budget and others) that changes without one.
  Now 297 kept, 106 changed, 0 removed, 0 open.
- Research is 2.1's per-source-type base pass plus the five search rounds on top; rounds never print in chat (one short status line); a background
  collection job where the host has one.
- Setup questions go through the host's native question tool (typed list only as the fallback), are asked once with an explicit skip rule, and a saved
  offer that conflicts with the request is asked about first (`eval.py offer-conflict`).
- Source grading on the page: grade, how found and one plain strength word, capped by the weakest link (C25). The brief is assembled from `fields.json`
  by `eval.py assemble` against the schema (C26), never written by hand. Records check (C23) and "cut wording, never cited facts" (C24).
- Every layout number, colour and size is in `pcp.yaml` (`format/layout.json` is generated); body text is 10 pt (`eval.py hardcoded`, pinned).
- A history reader for Claude Code, Codex, ChatGPT and Claude-app exports (`eval.py battery`).

### Daniel's Oct 17 decisions
- Q2 (private equity) and Q7 (UK / EU) option text reverted to 2.1's exact wording; one exact-string plain-words exemption, pinned.
- CAL-1 approved: ask only the setup questions with no saved answer (a returning user is asked a new Q9 only).
- Ledger sources print as their domain, linked to the full address; C25 fails a full or bare URL.
- C9 exclusions: word-start matching of 2.1's keywords (every inflection trips) plus an explicit list of 22 real compounds (`exclusions.compounds`).

### Changed
- **Trim:** `SKILL.md` is the procedure only, 82,768 -> 20,772 bytes (cap 30,000). Each step names the files it loads; the tables, long rules and wording
  are generated references (`references/setup`, `collection`, `profile`, `brief`, `checks`, `in-chat` and the two existing ones) loaded at the step
  that needs them. The chat apps' knowledge file is unchanged. `eval.py skill` checks the cap, that every step names its files, and that every 2.1.0
  item is reachable (403/403).
- Gates are no looser than 2.1.0 (`eval.py gates`: 5 same, 10 stricter, 0 looser): C1 reads B1-B9 and exempts only whole lines that are exactly a schema
  template; C2 checks url, tag, date and confidence in `claims.jsonl` for every cited row; C8 reads B1, B5 and B9; the brief's word budget is 2.1's 1,080.

### Fixed
- `eval.py battery --latest` read no searches from a background collection job (Claude Code keeps a subagent's transcript in its own file) and ignored
  `$CLAUDE_CONFIG_DIR`; it now reads the session's subagent transcripts too.

### Added
- `eval.py versions` (C30), `eval.py skill` (C29), `eval.py gates`, `eval.py parity` (C28), `eval.py hardcoded` (C27), `CHANGELOG.md`, `VERSIONING.md`.

## [3.1.0] - 2026-10-13 to 2026-10-16

Built on 3.0.0 over `pcp-3.1.0-rc1` (`45f423e`) and `pcp-3.1.0-rc2` (`32badc4`, also `origin/main`). Superseded by 3.1.1.

### Added
- Plain words (a banned-word list and one name for the deliverable), the script always on page 3, the Socratic questions reference on every host, experience
  levels (Q9, C15), LinkedIn status lines (C16), a component inventory, a ledger citation check (C17) and source-quality check (C18), a mandatory
  five-round search battery proved from the run's own transcript (C21), three-colour print (C20), a render check (C19), an in-chat fallback for hosts with no
  shell, a Grok chat adapter, 10 pt body on every density rung.
- LinkedIn read only as search-result text, never a browser (AID-63).

## [3.0.0] - 2026-10-12

### Changed
- The Intelligence Brief in the approved nine-block schema plus the evidence ledger (B1-B10) and a nine-section script; fixes from the first live run.

## [2.1.0] - 2026-09-28 (talyx-ai `upstream/main`, `993a8be`)

### Changed
- Install on every host; behaviour exactly as 2.0.0. The standard this plug-in is
  held to (`evals/baseline-2.1.0.json`).

## [2.0.0] - 2026-09-23

### Changed
- One 3-page PDF (a 2-page brief and a 1-page script), one-time calibration, a coverage ledger.

## [1.0.0] - 2026-09-23

### Added
- The Talyx plug-ins marketplace and `/pcp` pre-call prep.
