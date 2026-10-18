<!-- GENERATED from pcp.yaml (sha256:28d15cfc0130) by render_skill.py -- edit pcp.yaml, never this file -->

# Inventory: what the Intelligence Brief prints (v3.1.1)

Every part a user sees, what it produces, where its facts come from, and one status: **always**,
**conditional** (printed only as its Prints when says, enforced by the named check) or **removed**. Every part
has a decided status. Totals: 30 always, 5 conditional, 0 removed.

## Blocks (19, one per registry block)

| Id | Block | Page | Produces | Comes from | Status | Prints when | Enforced by |
|---|---|---|---|---|---|---|---|
| B1 | Take | 1-2 | the one-paragraph read: Take, Evidence, Action, Avoid | B2-B9 | always | -- | -- |
| B2 | Questions that close gaps | 1-2 | five questions, each on a cited fact, with what the answer decides and whom to ask | F1 identity, F3 org news, F5 voice, F11 shared context, Q4 | always | -- | -- |
| B3 | Who they are | 1-2 | role, path, the organization, what changed and recent wins | F1 identity, F2 career timeline, F3 org news, F4 org self-description, F9 registers | always | -- | -- |
| B4 | In their words | 1-2 | their own words, quoted and cited, and the LinkedIn status line | F5 voice, F6 public social, F8 publications, LinkedIn | always | -- | -- |
| B5 | Signals and what to do with them | 1-2 | three signals -- their priority, where your offer connects, why now -- and what to do with each | F3 org news, F10 events, F11 shared context, Q8 | always | -- | -- |
| B6 | Behavioral profile | 1-2 | six observations and the move each one implies, and the evidence tier | F1 identity, F5 voice, F6 public social, F7 affiliations | always | -- | -- |
| B7 | Who decides | 1-2 | decision maker, the gate and the relationship holder | F1 identity, F3 org news, F9 registers, F11 shared context | always | -- | -- |
| B8 | Strongest case against | 1-2 | the best evidence against the read and what would reverse it | F12 counter-evidence | always | -- | -- |
| B9 | Meeting angle | 1-2 | the frame, what lands and repels, what to bring, the ask and fallback, meetings two and three, what to capture | Q8, B3-B8 | always | -- | -- |
| B10 | Evidence ledger | 1-2 | every cited fact with what it says, source, grade and date; then Coverage, Still open, Left out on purpose and Run | F1-F12, Q8 | always | -- | -- |
| P1 | Open | 3 | the hook said aloud, credibility, one insight, the rapport rule | B3, B4, Q8 | always | -- | -- |
| P2 | Question order | 3 | B2's questions in the order the room needs | B2, Q4 | always | -- | -- |
| P3 | Objections: name it, then answer | 3 | the likely objections, named first, each with a short answer | B5, B8 | always | -- | -- |
| P4 | Close | 3 | restate, a real deadline, the ask and fallback, the follow-up | B9 | always | -- | -- |
| P5 | Read the room (watch, do not assume) | 3 | what to do for each way they show up in the room | B6 | conditional | evidence tier medium or high | C13 |
| P6 | Influence, one fact behind each | 3 | influence principles, only where a cited fact backs one | B6, Q1 | conditional | evidence tier high and caller authority high; each principle only where a cited fact backs it | C13 |
| P7 | If it stalls | 3 | what restarts a stalled conversation, from a fact in the brief | B3-B9 | always | -- | -- |
| P8 | Guardrails | 3 | what never to promise or say, for the jurisdiction and domain | Q2, Q7 | always | -- | -- |
| P9 | Next step | 3 | the one next step and its date | B9 | always | -- | -- |

## Parts within and around the blocks

| Id | Part | Produces | Comes from | Status | Prints when | Enforced by |
|---|---|---|---|---|---|---|
| band | Classification band | the line above the name | names.classification | always | -- | -- |
| name | Name | the person's full name | S1 | always | -- | -- |
| identity | Identity line | organization, role and since when, city if public | F1 identity | always | -- | -- |
| meta | Meta line | meeting, prepared for, depth, sources, status, date | profile, S2 | always | -- | -- |
| footer | Footer | the deliverable's name, the person, page N of 3 | renderer | always | -- | C10 |
| B3.recent_wins | Recent wins line (B3) | none to two dated, cited results | F3 org news, F5 voice | conditional | a dated, cited result was found; otherwise the line is left out | C13 |
| B3.not_found | Path, The organization, What changed (B3) | the fact, or Not determined (a gap Still open may ask) | F1 identity, F2 career timeline, F3 org news, F4 org self-description | always | -- | C12 |
| B4.linkedin | LinkedIn line (B4) | read from search results, read from your file, or not read and the reason | S2-7 | always | -- | C16 |
| B6.no_read | No read rows (B6) | No read where a dimension lacks evidence (a gap Still open may ask) | S3-1 | always | -- | C12 |
| B7.relationship_holder | Relationship holder (B7) | who the relationship runs through, or Not determined (a gap Still open may ask) | F11 shared context, F1 identity | always | -- | C12 |
| B8.hypotheses | What they may want (B8) | up to three hypotheses, each with the claim that would disprove it | F12 counter-evidence, S3-4 | conditional | Depth deep | C13 |
| B10.coverage | Coverage row (B10) | n of 12 source types, what was not found, LinkedIn status | S2-4, S2-7 | always | -- | C16 |
| B10.still_open | Still open row (B10) | at most 4 questions for the room, highest value first | socratic.room | always | -- | C12 |
| B10.left_out | Left out on purpose row (B10) | the excluded topics, never the facts | exclusions | always | -- | -- |
| B10.run | Run row (B10) | date, depth, meeting type, prepared for, jurisdiction, status | profile | always | -- | -- |
| P.why | Why lines (P1, P3, P4) | one line on why each move works | Q9 | conditional | Q9 experience new | C15 |
