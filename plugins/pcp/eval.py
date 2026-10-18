#!/usr/bin/env python3
"""eval.py -- the pcp instrument. The metric comes before the feature.

  duf <brief.md> [script.md] [--pages N | --pdf OUT.pdf]   decision-useful facts: bound / unbound / dropped / duf_pp (+ coverage);
                                            --pdf divides by the rendered PDF's real page count
  checks <brief.md> [script.md] [--all|--swap|--quotes|--custom-q|--sections|--budgets|--never-say|--outcome|--exclusions|--plain|--gaps|--conditional|--layout]
  checks <OUT.pdf> --plain                  plain words on the printed text (masthead, band and footer included)
  pdf <OUT.pdf> [brief.md]                  the rendered PDF: page count, script on its page, ledger last before it, footer, links, plain words
  concordance                               SKILL.md + commands/pcp.md match a fresh render of pcp.yaml
  self-test [--require-pdf]                 positive + negative controls: every check is proven able to fail
                                            (renders and reads two PDFs when a Chromium and pdftotext/pypdf exist)
  ratchet [--record]                        every frozen target's duf_pp >= its floor; --record raises floors
  improve <debrief.yaml>...                 propose row diffs as evals/proposals/<date>.patch (never lands)

Exit 0 = pass. Non-zero = fail, with the reason and the population on stdout. Every number prints its denominator.
"""
import argparse
import datetime as dt
import html
import json
import math
import pathlib
import re
import shutil
import subprocess
import sys
import tempfile

HERE = pathlib.Path(__file__).resolve().parent
R = json.loads((HERE / "pcp.json").read_text())   # pcp.yaml as JSON (render_skill.py): no YAML library needed at run time
LEDGER = R["brief"]["sections"][-1]["id"]          # B10, the evidence ledger

CITE = re.compile(r"\[(\d+)\]")
TAGS, GRADES, CONFS = "Direct|Search|LinkedIn|Yours", "Measured|Derived|Inference|Not determined", "Primary|Reputable|Single source|Inferred"
# Printed ledger (Ben, Oct 13): | # | What it says | Source | Grade | Date |. Tag and confidence stay in claims.jsonl.
SRC_ROW = re.compile(r"^\|\s*\[(\d+)\]\s*\|\s*([^|]+?)\s*\|\s*([^|\s][^|]*?)\s*\|\s*(" + GRADES + r")(?:\s*·[^|]*)?\s*\|\s*"
                     r"((?:seen )?[A-Z][a-z]{2}(?: \d{1,2},)? \d{4})\s*\|", re.M)


def _tag(source):
    """The printed ledger has no Tag column: a source with no link is Yours, a linkedin.com link is LinkedIn."""
    m = re.search(r" · (Direct|Search|LinkedIn|Yours)\s*$", source)
    if m:
        return m.group(1)
    if not re.search(r"https?://", source):
        return "Yours"
    return "LinkedIn" if "linkedin.com" in source.lower() else "Direct"

H2 = re.compile(r"^##\s+(.+)$", re.M)
QUOTED = re.compile(r"[\u201c\"][^\u201d\"\n]{0,300}[\u201d\"]")   # their own words are exempt from plain words; one line, <= 300
                                                                    # characters, so a stray quote mark cannot exempt the rest of the page
WORD = re.compile(r"\S*\w\S*")
LINK_URL = re.compile(r"\]\([^)]*\)")


def _sections(md):
    """{title: body} in order, keyed by the leading Bn/Pn id if present else the title."""
    out, titles = {}, list(H2.finditer(md))
    for i, m in enumerate(titles):
        body = md[m.end(): titles[i + 1].start() if i + 1 < len(titles) else len(md)]
        key = m.group(1).strip()
        mid = re.match(r"([BP]\d+)\b", key)
        out[mid.group(1) if mid else key] = body.strip()
    return out


def _body_ids(secs):
    return [k for k in secs if re.match(r"B[1-9]$|P[1-9]$", k)]


# ---------------------------------------------------------------- duf ---------------------------------------
def duf(brief_md, script_md="", pages=None):
    md = brief_md + "\n" + script_md
    secs = _sections(md)
    sources = {}
    dropped = 0
    for ln in secs.get(LEDGER, "").splitlines():
        if not re.match(r"^\|\s*\[\d+\]", ln):
            continue
        m = SRC_ROW.match(ln)
        if m:
            sources[int(m.group(1))] = dict(claim=m.group(2), source=m.group(3), tag=_tag(m.group(3)), grade=m.group(4), date=m.group(5))
        else:
            dropped += 1  # a [n] ledger row missing its source, grade or date
    cited = set()
    for k in _body_ids(secs):
        cited |= {int(n) for n in CITE.findall(secs[k])}
    bound = sorted(cited & set(sources))
    dangling = sorted(cited - set(sources))       # cited in the body, absent from the ledger
    unbound = sorted(set(sources) - cited)         # in the ledger, never used by a move
    pages = pages or R["page_budget"]["total_pages"]
    cov = re.search(r"(\d+)\s+of\s+(\d+)\s+source types", md, re.I)
    rep = dict(bound=len(bound), unbound=len(unbound), dangling=len(dangling), dropped=dropped,
               sources_total=len(sources) + dropped, pages=pages, duf_pp=round(len(bound) / pages, 2),
               coverage=(f"{cov.group(1)}/{cov.group(2)}" if cov else "MISSING"),
               population=f"body sections {_body_ids(secs) or 'NONE'}; source rows {len(sources)+dropped}")
    rep["ok"] = rep["dangling"] == 0 and rep["unbound"] == 0 and rep["dropped"] == 0 and rep["coverage"] != "MISSING"
    return rep


# ---------------------------------------------------------------- checks -------------------------------------
def plain_hits(text):
    """plain_words.banned terms and internal codes outside quoted words; a banned word inside a
    plain_words.allowed phrase (asset manager) is the finance term, not the banned word."""
    pw = R["plain_words"]
    own = QUOTED.sub(" ", text)
    if pw.get("allowed"):
        own = re.sub(r"\b(?:" + "|".join(re.escape(w) for w in pw["allowed"]) + r")\b", " ", own, flags=re.I)
    words = pw["banned"] + pw.get("names_banned", [])   # the deliverable has one name (Intelligence Brief)
    hits = re.findall(r"\b(?:" + "|".join(re.escape(w) for w in words) + r")\b", own, re.I) + re.findall(pw["codes"], own)
    return sorted(set(hits))


# a period that ends no sentence: a title, "No. 2", "Oct. 12", "U.S. economy" (the Barra chat run split at "No.")
ABBR = re.compile(r"\b(?:Mr|Mrs|Ms|Dr|U\.S|e\.g|i\.e)\.|\b(?:No|Nos|Inc|Co|Corp|Ltd|vs|St|Jan|Feb|Mar|Apr|Jun|Jul|Aug|Sept?|Oct|Nov|Dec)\.(?=\s+[a-z0-9])")
QUOTE_SPAN = re.compile(r'"[^"\n]*"|\u201c[^\u201d\n]*\u201d')


def template_lines():
    """C1 (swap): the only lines that state no fact, as the registry writes them -- one regex each, matched against the whole line.
    A gap line ('- **Role:** Not determined'), a fallback ('- Not determined', '- No counter-evidence found'), the tier line and the
    LinkedIn status line. A line that merely contains 'Not determined' or 'Evidence tier:' is a sentence like any other: it must carry
    a [n] or a target-specific noun (2.1.0 exempted nothing)."""
    F, li, out = R["forms"], R["linkedin"], []
    bullet = r"(?:[-*]\s+)?"
    for spec in F.values():
        for f in spec.get("fields", []) if isinstance(spec, dict) else []:
            if f.get("missing"):
                out.append(bullet + r"\*\*" + re.escape(f["label"]) + r"\*\*\s+" + re.escape(f["missing"]) + r"\.?")
    out.append(r"[-*]\s+(?:" + "|".join(re.escape(F[b]["none"]) for b in ("B4", "B8")) + r")\.?")
    out.append(r"\*\*Evidence tier:\*\*\s+(?:high|medium|low)(?:" + re.escape(F["B6"]["tier"].split("{tier}")[1]) + r")?\.?")
    reasons = li["reasons"] + list(li.get("retired", {}))
    out.append(r"(?:[-*]\s+)?\*\*LinkedIn:\*\*\s+(?:" + "|".join(re.escape(r) for r in li["read"].values())
               + "|" + re.escape(li["not_read"]) + ": (?:" + "|".join(re.escape(r) for r in reasons) + r"))\.?")
    return re.compile(r"\s*(?:" + "|".join(out) + r")\s*")


def _sentences(txt):
    txt = re.sub(r"\|.*\|", " ", txt)  # tables are rows, not sentences
    tpl = template_lines()
    txt = "\n".join(ln for ln in txt.splitlines()   # headings and the registry's own template lines, whole-line matches only
                    if not re.match(r"\s*#", ln) and not tpl.fullmatch(ln))
    hide = lambda m: m.group(0).translate(str.maketrans(".!?", "\x00\x01\x02"))   # a quote is one span, cited after it
    txt = QUOTE_SPAN.sub(hide, ABBR.sub(hide, txt))
    back = str.maketrans("\x00\x01\x02", ".!?")
    return [s.strip().translate(back) for s in re.split(r"(?<=[.!?])\s+(?!\[\d)", txt) if len(s.strip()) > 25]   # "Inc. [1]": the cite is this sentence's


def _gaps(secs):
    """[(block, label, 'Not determined'|'No read')]: each **Label:** Not determined line, each table row with a
    Not determined or No read cell (its label: the row's first other cell, up to a colon), in B1-B9."""
    out = []
    for k in [k for k in secs if re.match(r"B[1-9]$", k)]:
        out += [(k, label, "Not determined") for label in re.findall(r"\*\*([^*]+?):\*\*\s*[*_]?Not determined", secs[k])]
        for ln in secs[k].splitlines():
            cells = [re.sub(r"\*\*|\*|_", "", c).strip() for c in ln.strip().strip("|").split("|")] if ln.lstrip().startswith("|") else []
            hit = next((m for m in (re.fullmatch(r"(?:([^:]+):\s*)?(Not determined|No read)\.?", c) for c in cells) if m), None)
            if hit:   # "Not determined" alone, or "The trigger: Not determined" in one cell
                gap = hit.group(2)
                other = hit.group(1) or next((c for c in cells if c != hit.group(0)), "")
                label = CITE.sub("", other).split(":")[0].strip()
                out.append((k, label or gap, gap))
    return out


def _day(text):
    return dt.datetime.strptime(text, "%b %d, %Y").date()


def _url_day(src):
    """The date in a source's URL path (/2026/10/14/ or 2026-10-14), None when it has none or it is not a date."""
    m = re.search(r"/(20\d\d)[/-](\d{1,2})[/-](\d{1,2})(?!\d)", src)
    try:
        return dt.date(*map(int, m.groups())) if m else None
    except ValueError:
        return None


def _words(t):
    return len(WORD.findall(CITE.sub(" ", t.replace("*", ""))))


def exclusion_hits(text):
    """C9's matches in a text: each 2.1.0 keyword from the start of a word (`*` any ending, else a whole word), then each listed compound
    as an exact whole word. Returns (the words matched, topic, compound?) in the registry's order, the first match of each."""
    out, ex = [], R["exclusions"]
    for topic, words in ex["keywords"].items():
        for w in words:
            stem = w.endswith("*")
            m = re.search(r"\b(?:" + re.escape(w.rstrip("*")) + (r"\w*" if stem else "") + r")" + ("" if stem else r"\b"), text, re.I)
            if m:
                out.append((m.group(0), topic, False))
        for c in ex["compounds"].get(topic, []):
            m = re.search(r"\b" + re.escape(c) + r"\b", text, re.I)
            if m:
                out.append((m.group(0), topic, True))
    return out


def checks(brief_md, script_md="", which="all", target_nouns=(), experience=None, authority=None):
    """experience: the profile's Q9 answer (new|experienced|top); C15 runs only when it is given."""
    md = brief_md + "\n" + script_md
    secs = _sections(md)
    fails = []
    budgets = {s["id"]: s["words"] for s in R["brief"]["sections"]} | {b["id"]: b["words"] for b in R["script"]["blocks"]}
    prepared = re.search(r"Prepared\s+([A-Z][a-z]{2} \d{1,2}, \d{4})", brief_md)
    dens = R["page_budget"]["density"]
    if prepared and _day(prepared.group(1)) < dt.date.fromisoformat(str(dens["since"])):
        budgets = budgets | dens["legacy_words"]   # a brief written before the 10 pt density refit keeps its day's budgets (the frozen targets)

    def want(name):
        return which in ("all", name)

    if want("cites"):
        fails += cite_relevance(brief_md)
        mast = re.search(r"Sources: (\d+) of \d+ source types, (\d+) cited", brief_md)   # R12, R12c (Oct 16) printed
        line = re.search(r"(\d+) facts cited; status \w+ at (\d+) of \d+ source types", brief_md)   # the type count twice
        rows = len({m.group(1) for m in SRC_ROW.finditer(secs.get(LEDGER, ""))})
        if mast and rows and int(mast.group(2)) != rows:
            fails.append(f"C17 cites: the masthead says {mast.group(2)} cited; the ledger lists {rows} facts")
        if mast and line and mast.group(1) != line.group(2):
            fails.append(f"C17 cites: the masthead says {mast.group(1)} source types; the ledger line says {line.group(2)}")
    if want("grading"):
        fails += grading_check(brief_md)
    if which == "schema":   # not in --all: the loose fixtures are not assembled briefs; assemble runs it on every real one
        fails += schema_check(brief_md, script_md)
    if want("quality"):
        fails += source_quality(ledger(brief_md))
        run = re.search(r"\*\*Run\*\*\s*\|\s*([A-Z][a-z]{2} \d{1,2}, \d{4})", brief_md)
        day = run and _day(run.group(1))   # a URL dated the run day (/2026/10/14/) proves the source is: an earnings day
        same = [m.group(1) for m in SRC_ROW.finditer(brief_md) if run and m.group(5) == run.group(1) and _url_day(m.group(3)) != day]
        if len(same) >= 3:   # v6 Moynihan dated all 20 rows the run day: read dates, not the sources' own
            fails.append(f"C18 quality: rows {same} carry the run's date {run.group(1)} unmarked; give each source's own date, "
                         "or 'seen <date>' when it has none")
    if want("swap"):
        nouns = [n.lower() for n in target_nouns if n]
        for k in [k for k in secs if re.match(r"B[1-9]$", k)]:   # every block that states a fact or a question about the person (2.1.0: B1-B7 of its nine)
            for s in _sentences(secs[k]):
                if CITE.search(s):
                    continue
                if nouns and any(n in s.lower() for n in nouns):
                    continue
                fails.append(f"C1 swap: {k}: uncited, non-specific sentence: '{s[:70]}...'")
    if want("quotes"):
        for q in re.finditer(r"[“\"]([^”\"]{12,})[”\"]", secs.get("B4", "")):
            tail = secs["B4"][q.end(): q.end() + 40]
            if not CITE.search(tail):
                fails.append(f"C3 quotes: B4 quote without [n]: '{q.group(1)[:50]}'")
    if want("custom-q"):
        n = sum(1 for ln in secs.get("B2", "").splitlines() if "?" in ln and CITE.search(ln))
        if n < 2:
            fails.append(f"C4 custom_q: {n}/2 questions in B2 carry a [n]")
    if want("sections"):
        need = [s["id"] for s in R["brief"]["sections"]] + [b["id"] for b in R["script"]["blocks"] if b["prints"] == "always"]
        present = [k for k in secs if re.match(r"[BP]\d+$", k)]
        missing = [i for i in need if i not in present]
        order = [k for k in present if k in need]
        if missing:
            fails.append(f"C5 sections: missing {missing} (present {present})")
        elif order != [i for i in need if i in order]:
            fails.append(f"C5 sections: out of order {order}")
    if want("budgets"):
        for k, body in secs.items():
            if k in budgets:
                w = len(WORD.findall(LINK_URL.sub("]", body)))   # pipes, rules and link targets are not words
                if w > budgets[k] * 1.15:
                    fails.append(f"C6 budgets: {k} {w} words > {budgets[k]} (+15%)")
        if not (prepared and _day(prepared.group(1)) < dt.date.fromisoformat(str(dens["since"]))):   # 2.1.0's caps on the parts 2.1.0 had (R3)
            blk = {b["id"]: b for b in R["script"]["blocks"]}
            hook = re.search(r"\*\*Hook:\*\*(.*)", secs.get("P1", ""))
            if hook and blk["P1"].get("hook_words"):
                w, n = len(WORD.findall(CITE.sub(" ", hook.group(1)))), len(_sentences(hook.group(1).replace("*", "")))
                if w > blk["P1"]["hook_words"] * 1.15 or n > 2:
                    fails.append(f"C6 budgets: P1's Hook is {w} words in {n} sentences; 2.1.0's opening: at most 2 sentences and {blk['P1']['hook_words']} words (+15%)")
            close = " ".join(m for m in re.findall(r"\*\*(?:The ask|Fallback|Follow-up):\*\*([^*\n]*)", secs.get("P4", "")))
            if close and blk["P4"].get("close_words") and len(WORD.findall(CITE.sub(" ", close))) > blk["P4"]["close_words"] * 1.15:
                fails.append(f"C6 budgets: P4's ask, fallback and follow-up are {len(WORD.findall(CITE.sub(' ', close)))} words; 2.1.0's close: {blk['P4']['close_words']} (+15%)")
    if want("never-say"):
        for k, body in secs.items():
            if k == "P8":
                continue
            for p in R["guardrails"]["never_say"]:
                if p.lower() in body.lower():
                    fails.append(f"C7 never_say: '{p}' in {k}")
    if want("outcome"):
        mv = next(c["method_verbs"] for c in R["checks"] if "method_verbs" in c)
        for blk in ("B1", "B5", "B9"):   # 2.1.0 read one block (its B6, the bridge); the offer is stated in these three now
            for v in mv:
                if v.lower() in secs.get(blk, "").lower():
                    fails.append(f"C8 outcome: method verb '{v}' in {blk}")
    if want("exclusions"):   # C9: pcp.yaml exclusions.keywords (from the start of a word; `*` any ending) and exclusions.compounds (exact whole words)
        body = "\n".join(v for k, v in secs.items() if k not in (LEDGER, "P8"))
        for hit, topic, compound in exclusion_hits(body):
            fails.append(f"C9 exclusions: '{hit}' ({topic}{', a compound' if compound else ''}) in body")
    if want("plain"):
        for h in plain_hits(md):
            fails.append(f"C11 plain: '{h}' outside quoted words")
    if want("gaps"):
        still = next((ln for ln in secs.get(LEDGER, "").splitlines() if "Still open" in ln), "")
        gaps = _gaps(secs)
        room = R["socratic"]["room"]
        starts, cap = room["question_starts"], room["max_open"]
        cell = re.sub(r"\*\*Still open\*\*|\*\*", "", still).strip(" |")
        items = [i.strip() for i in re.split(r"\s+·\s+", cell) if i.strip()]
        asked = [q for i in items for q in re.findall(r"[^?]*\?", i)]   # two questions in one item count as two
        if gaps and not asked:   # Daniel, Oct 14: at most 4 questions, highest value first -- not one per gap
            fails.append(f"C12 gaps: {len(gaps)} gaps in B1-B9 but no question in Still open")
        if len(asked) > cap:
            fails.append(f"C12 gaps: Still open asks {len(asked)} questions; at most {cap}, highest value first")
        labels = {g[1].lower() for g in gaps}
        for item in [i for i in items if "?" in i]:
            if item.split(": ", 1)[0].strip("*_ ").lower() not in labels:
                fails.append(f"C12 gaps: Still open item '{item[:40]}' is not on a gap above (a Not determined or No read label)")
        for item in items:
            q = item.split(": ", 1)[1] if ": " in item else item
            first = re.match(r"[*_\s]*([A-Za-z]+)", q)   # What's, Who'd: the question word without its contraction
            if not (q.rstrip().endswith("?") and first and first.group(1).capitalize() in starts) and (gaps or "?" in item):
                fails.append(f"C12 gaps: Still open item is not a question starting {'/'.join(starts)}: '{item[:60]}'")
    if want("linkedin"):
        li = R["linkedin"]
        run = re.search(r"\*\*Run\*\*\s*\|\s*([A-Z][a-z]{2} \d{1,2}, \d{4})", brief_md)
        reasons = li["reasons"] + [r for r, until in li["retired"].items()   # a frozen run keeps the reasons of its day
                                   if run and _day(run.group(1)) < dt.date.fromisoformat(str(until))]
        status = (rf"({'|'.join(re.escape(r) for r in li['read'].values())}|"
                  rf"{re.escape(li['not_read'])}: ({'|'.join(re.escape(r) for r in reasons)}))")
        lines = re.findall(r"^\*\*LinkedIn:\*\*.*$", secs.get("B4", ""), re.M)
        b4 = re.match(r"^\*\*LinkedIn:\*\* " + status + r"\.?\s*$", lines[0]) if len(lines) == 1 else None
        grid = secs.get(LEDGER, "")
        cov = next((ln for ln in grid.splitlines() if "**Coverage**" in ln), "").replace("*", "")   # **LinkedIn:** prints as LinkedIn:
        if not b4:
            fails.append(f"C16 linkedin: B4 needs exactly one line '**LinkedIn:** <{' | '.join(li['read'].values())}>' or "
                         f"'**LinkedIn:** {li['not_read']}: <{' | '.join(li['reasons'])}>' (found {lines or 'none'})")
        elif f"LinkedIn: {b4.group(1)}" not in cov:
            fails.append(f"C16 linkedin: Coverage does not say 'LinkedIn: {b4.group(1)}' as B4 does")
        elif b4.group(1) == li["read"]["search"]:   # AID-63: the profile's search result is a ledger row, cited to its URL
            rows = [m for m in SRC_ROW.finditer(grid) if "linkedin.com" in m.group(3).lower()]
            if not any("linkedin.com/in/" in m.group(3).lower() for m in rows):
                fails.append(f"C16 linkedin: {li['read']['search']}, yet no ledger row cites the linkedin.com/in profile it showed")
            bare = [m.group(1) for m in rows if "search result" not in m.group(3).lower()]
            if bare:   # R11b (Oct 15) cited a LinkedIn post as [linkedin.com](...), as if the page had been read
                fails.append(f"C16 linkedin: ledger rows {bare} cite linkedin.com without 'search result'; "
                             "every LinkedIn row (profile, post or article) is cited [linkedin.com, search result](its URL)")
        elif b4.group(1) == li["read"]["link"]:   # D2: the link the user gave, read once with the page fetch: its profile is a ledger row
            rows = [m for m in SRC_ROW.finditer(grid) if "linkedin.com/in/" in m.group(3).lower()]
            if not rows:
                fails.append(f"C16 linkedin: {li['read']['link']}, yet no ledger row cites the linkedin.com/in address the user gave")
        elif b4.group(1) == li["read"]["file"]:   # the saved profile is the user's file: cited by its name, tagged Yours
            profile = [m.group(1) for m in SRC_ROW.finditer(grid) if "linkedin.com/in/" in m.group(3).lower()]
            if profile:
                fails.append(f"C16 linkedin: {li['read']['file']}, yet ledger rows {profile} cite a LinkedIn profile page; cite the file")
        elif b4.group(2):   # not read
            tagged = [m.group(1) for m in SRC_ROW.finditer(grid) if _tag(m.group(3)) == "LinkedIn"]
            if tagged:
                fails.append(f"C16 linkedin: LinkedIn {li['not_read']}, yet ledger rows {tagged} are tagged LinkedIn")
            still = next((ln for ln in grid.splitlines() if "Still open" in ln), "")
            if any("linkedin" in i.lower() and "?" in i for i in re.split(r"\s+·\s+|\|", still)):   # Oct 14: an unread LinkedIn is stated in Coverage, not asked
                fails.append("C16 linkedin: LinkedIn not read belongs in Coverage only, not as a Still open question")
    if want("battery"):   # C21: the Run row states the battery as sent (S2-9); briefs run before osint.battery.since are exempt
        run = re.search(r"\*\*Run\*\*\s*\|\s*([A-Z][a-z]{2} \d{1,2}, \d{4})([^\n]*)", brief_md)
        if run and _day(run.group(1)) >= dt.date.fromisoformat(str(R["osint"]["battery"]["since"])):
            said = RUN_COUNTS.search(run.group(2))
            depth = re.search(r"Depth:\s*(fast|standard|deep)", brief_md, re.I)
            has_base = _day(run.group(1)) >= dt.date.fromisoformat(str(R["osint"]["battery"]["base_since"]))
            if not said:
                fails.append("C21 battery: the Run row does not end 'N searches (B base) in M rounds' (both passes as sent)")
            elif has_base and said.group(2) is None:
                fails.append(f"C21 battery: the Run row says '{said.group(0)}'; from {R['osint']['battery']['base_since']} it gives the base pass: 'N searches (B base) in M rounds'")
            elif depth:
                need, per, _ = battery_floor(depth.group(1).lower())
                base_min = len(base_families(depth.group(1).lower())) if has_base else 0
                if int(said.group(3)) < len(need) or int(said.group(1)) < per * len(need) + base_min or (has_base and int(said.group(2)) < base_min):
                    fails.append(f"C21 battery: the Run row says {said.group(0)}; a {depth.group(1).lower()} run sends at least "
                                 f"{base_min + per * len(need)} searches ({base_min} base) in {len(need)} rounds")
    if experience and which == "all":
        why = {k: re.findall(r"\*\*Why:\*\*\s*(.+)", secs[k]) for k in secs if re.match(r"P\d+$", k)}
        if experience == "new":
            for k in ("P1", "P3", "P4"):
                if not why.get(k):
                    fails.append(f"C15 experience: new -- {k} has no **Why:** line")
                fails += [f"C15 experience: new -- {k} Why line is {_words(w)} words > 12" for w in why.get(k, []) if _words(w) > 12]
        elif any(why.values()):
            fails.append(f"C15 experience: {experience} -- Why lines in {[k for k, v in why.items() if v]}; only new gets them")
        if experience == "top":
            lines = re.findall(r"\*\*Hook:\*\*\s*(.+)", secs.get("P1", "")) + \
                re.findall(r"^\s*[-*]\s+\*\*.+?:\*\*\s*(.+)$", secs.get("P3", ""), re.M)
            fails += [f"C15 experience: top -- '{t[:40]}...' is {_words(t)} words > 15" for t in lines if _words(t) > 15]
    if want("layout"):
        b9 = secs.get("B9", "")
        for ln in [x for x in b9.splitlines() if x.strip() and not x.lstrip().startswith("#")]:   # bullets and plain lines
            labels = [a or b for a, b in re.findall(r"\*\*([^*]+?):\*\*|\*\*([^*]+?)\*\*:", ln)]   # **Label:** or **Label**:
            if len([x for x in labels if not (x == "Fallback" and "The ask" in labels)]) > 1:
                fails.append(f"C14 layout: B9 bullet carries {len(labels)} labels {labels}; one label per bullet (The ask with its Fallback excepted)")
        if re.search(r"\((?:not confirmed|unconfirmed)\)", md, re.I):
            fails.append("C14 layout: '(not confirmed)' printed; leave an unconfirmed item out")
        ident = (md.split("\n", 2) + ["", ""])[1]   # the identity line under '# Full Name'
        if re.search(r"not confirmed|unconfirmed|not published|not determined", ident, re.I):
            fails.append(f"C14 layout: the identity line prints what is not known ('{ident[:80]}'); leave it out")
        brief = re.split(r"^# ", md, maxsplit=2, flags=re.M)   # ['', name + brief, script ...]: the brief ends at the next `# `
        bsecs = list(_sections("# " + brief[1] if len(brief) > 1 else md))
        blocks = [s["id"] for s in R["brief"]["sections"]][:-1]
        if LEDGER not in bsecs:
            fails.append(f"C14 layout: no {LEDGER} evidence ledger in the brief (blocks {bsecs})")
        else:
            before, after = bsecs[:bsecs.index(LEDGER)], bsecs[bsecs.index(LEDGER) + 1:]
            if before != blocks:
                fails.append(f"C14 layout: {len(before)} blocks before {LEDGER}, need the {len(blocks)} blocks {blocks[0]}-{blocks[-1]} "
                             f"(found {before})")
            if after:
                fails.append(f"C14 layout: {LEDGER} is not the last block of the brief (after it: {after})")
    if want("conditional"):
        if "What they may want" in secs.get("B8", "") and not re.search(r"Depth:\s*deep", md, re.I):
            fails.append("C13 conditional: B8 has hypotheses but the meta line is not Depth deep")
        tier = re.search(r"Evidence tier:\**\s*(high|medium|low)", secs.get("B6", ""), re.I)
        tier = tier.group(1).lower() if tier else "low"
        if "P6" in secs and tier != "high":
            fails.append(f"C13 conditional: P6 Influence printed at evidence tier {tier}")
        if "P6" in secs and authority and authority != "high":   # Ben, Oct 13: caller-authority gate as well as tier
            fails.append(f"C13 conditional: P6 Influence printed with caller authority {authority} (needs high)")
        if "P5" in secs and tier == "low":
            fails.append("C13 conditional: P5 Read the room printed at evidence tier low")
        cap6 = next(b for b in R["script"]["blocks"] if b["id"] == "P6").get("max_moves")
        moves6 = len(re.findall(r"^\s*[-*] ", secs.get("P6", ""), re.M))
        if cap6 and moves6 > cap6:   # 2.1.0's '3 moves from B4 meanings' (its B4 is B6 now)
            fails.append(f"C13 conditional: P6 Influence has {moves6} moves; at most {cap6}, each from a B6 meaning")
        for w in re.findall(r"\*\*Recent wins:\*\*(.*)", secs.get("B3", "")):
            if not (CITE.search(w) and re.search(r"\b(?:19|20)\d\d\b|\b[A-Z][a-z]{2} \d{1,2}\b", w)) or "Not determined" in w:
                fails.append(f"C13 conditional: B3 Recent wins printed without a dated, cited result: '{w.strip()[:50]}'")
    return fails


# ---------------------------------------------------------------- the rendered PDF ---------------------------
def pdf_pages(path):
    """The text of each page: pdftotext (poppler) if installed, else pypdf. None if neither is."""
    try:
        r = subprocess.run(["pdftotext", "-enc", "UTF-8", str(path), "-"], capture_output=True, text=True, timeout=60)
        if r.returncode == 0:
            return r.stdout.split("\f")[:-1] if r.stdout.endswith("\f") else r.stdout.split("\f")
    except (OSError, subprocess.TimeoutExpired):
        pass
    try:
        from pypdf import PdfReader
        return [p.extract_text() or "" for p in PdfReader(str(path)).pages]
    except ImportError:
        return None


def pdf_links(path):
    """The link targets (/URI) in the PDF: pypdf if installed, else poppler's pdfinfo -url, else the raw bytes."""
    try:
        from pypdf import PdfReader
        return [a.get_object()["/A"]["/URI"] for p in PdfReader(str(path)).pages for a in p.get("/Annots") or []
                if "/A" in a.get_object() and "/URI" in a.get_object()["/A"]]
    except ImportError:
        pass
    try:
        r = subprocess.run(["pdfinfo", "-url", str(path)], capture_output=True, text=True, timeout=60)
        if r.returncode == 0:
            return [ln.split()[-1] for ln in r.stdout.splitlines()[1:] if ln.strip()]
    except (OSError, subprocess.TimeoutExpired):
        pass
    return [m.decode("latin-1") for m in re.findall(rb"/URI\s*\(([^)]*)\)", pathlib.Path(path).read_bytes())]


def link_targets(path):
    """The links a brief cites: a PDF's link targets, or brief.md's markdown links (S2-8 checks them before render;
    R12d, Oct 16, ran `links brief.md` and got '0 total' from a reader that took only PDFs)."""
    if str(path).lower().endswith(".pdf"):
        return pdf_links(path)
    return re.findall(r"\]\((https?://[^)\s]+)\)", pathlib.Path(path).read_text())


def _flat(t):
    """Letter-spaced, upper-cased headings (E V I D E N C E  L E D G E R) compare as EVIDENCELEDGER."""
    return re.sub(r"\s+", "", t).upper()


def pdf_check(pdf, brief_md=""):
    """The rendered PDF, as the reader gets it (C10, C11 on the printed text, C19 nothing cut off, C20 three colours).
    [] = pass; None = no PDF text tool."""
    pages = pdf_pages(pdf)
    if pages is None:
        return None
    if shutil.which("pdftoppm"):
        c19 = render_check(pdf)
    else:
        c19 = []
    pb, n = R["page_budget"], R["names"]
    total, bp = pb["total_pages"], pb["brief_pages"]
    fails = []
    if len(pages) != total:
        fails.append(f"C10 pages: {len(pages)} pages, need exactly {total}")
    script = _flat(n["script"])
    if pages:
        on_brief = sum(_flat(p).count(script) for p in pages[:bp])
        if on_brief:
            fails.append(f"C10 pages: '{n['script']}' on pages 1-{bp} ({on_brief}x); the script starts on page {bp + 1}")
        if len(pages) > bp and script not in _flat(pages[bp]):
            fails.append(f"C10 pages: page {bp + 1} does not start the {n['script']}")
        ledger = _flat(R["brief"]["sections"][-1]["title"])
        lp = [i + 1 for i, p in enumerate(pages) if ledger in _flat(p)]
        if lp != [bp]:
            fails.append(f"C10 pages: the {R['brief']['sections'][-1]['title']} is on page(s) {lp or 'none'}, need page {bp}")
        else:
            tail = _flat(pages[bp - 1]).split(ledger, 1)[1]
            titles = {s["id"]: re.sub(r"\{(\w+)\}", lambda m: n[m.group(1)], s["title"]) for s in R["brief"]["sections"][1:-1]}
            later = [k for k, t in titles.items() if _flat(t) in tail]   # B1's head is hidden (the Take box)
            if later:
                fails.append(f"C10 pages: block titles after the ledger on page {bp}: {later}")
        if n["deliverable"] not in re.sub(r"\s+", " ", pages[0]):
            fails.append(f"C10 pages: page 1 does not name the {n['deliverable']}")
        fails += script_numbers(pages[-1], len(pages))
        foot = f"page {len(pages)} of {len(pages)}"
        if pages[-1].count(foot) != 1:
            fails.append(f"C10 pages: last page shows '{foot}' {pages[-1].count(foot)} times, need once")
    for h in plain_hits(re.sub(r"\s+", " ", "\n".join(pages))):
        fails.append(f"C11 plain: '{h}' printed in the PDF outside quoted words")
    if brief_md and re.search(r"^\*\*LinkedIn:\*\* " + re.escape(R["linkedin"]["not_read"]), brief_md, re.M):
        said = re.sub(r"\s+", " ", "\n".join(pages)).count(f"LinkedIn: {R['linkedin']['not_read']}")
        if said < 2:
            fails.append(f"C16 linkedin: the PDF says 'LinkedIn: {R['linkedin']['not_read']}' {said} times, need B4 and Coverage")
    if brief_md:
        rows = [m for m in SRC_ROW.finditer(brief_md) if _tag(m.group(3)) != "Yours"]
        links = pdf_links(pdf)
        if len(links) < len(rows):
            fails.append(f"C10 links: {len(links)} links in the PDF < {len(rows)} ledger rows not tagged Yours")
    return fails + c19 + text_colors(pdf) + block_breaks(pages, brief_md)


def script_numbers(page, n):
    """C10: page 3's section heads are numbered 1, 2, 3 ... with no gap when P5 or P6 drops (Oct 14). A head prints
    in capitals, so a numbered body line (it has lower case) never counts."""
    nums = sorted(int(x) for x in re.findall(r"^(\d) ?\.\s+[A-Z][^a-z\n]*$", page, re.M))
    return [f"C10 pages: page {n}'s sections are numbered {nums}; number them 1-{len(nums)} with no gap"] \
        if nums and nums != list(range(1, len(nums) + 1)) else []


def block_breaks(pages, brief_md=""):
    """C19: no block of the brief runs across a page break (v6 printed half of B6 at the top of page 2). Page 2 opens on
    Who decides (B7), as in the schema, and no table's header row prints on two pages (a split table repeats it)."""
    bp = R["page_budget"]["brief_pages"]
    b7 = _flat(next(s["title"] for s in R["brief"]["sections"] if s["id"] == "B7"))   # the schema's page 2 opens on B7
    fails = []
    for i, p in enumerate(pages[1:bp], 2):
        body = [ln for ln in p.splitlines() if ln.strip() and not re.match(r"\s*page \d+ of \d+", ln)]   # pypdf reads the footer first
        first = re.sub(r"\s+", "", body[0] if body else "")   # titles print in capitals
        if not first.startswith(b7):
            fails.append(f"C19 render: page {i} opens on '{first[:30]}', not on {b7} (B7): a block ran across the page or moved")
    for head in re.findall(r"^\|(.+)\|[ \t]*\n\|[ \t:|-]+\|[ \t]*$", brief_md, re.M):
        cells = [re.sub(r"\s+", "", c).upper() for c in head.split("|") if c.strip() not in ("", "#")]
        on = [i + 1 for i, p in enumerate(pages[:bp]) if cells and all(c in re.sub(r"\s+", "", p) for c in cells)]
        if len(on) > 1:   # headers print in capitals, so body text never matches
            fails.append(f"C19 render: the table '| {head.strip()} |' is split across pages {on}")
    return fails


# ---------------------------------------------------------------- concordance --------------------------------
def concordance():
    try:
        r = subprocess.run([sys.executable, str(HERE / "render_skill.py"), "--check"], capture_output=True, text=True, timeout=60)
    except subprocess.TimeoutExpired:
        print("CONCORDANCE FAIL: render_skill.py --check exceeded 60s")
        return False
    print(r.stdout.strip())
    if r.returncode != 0 and r.stderr.strip():
        print(r.stderr.strip()[-600:])   # e.g. no PyYAML: say why, never fail silently
    return r.returncode == 0


# ---------------------------------------------------------------- self-test ----------------------------------
def self_test(require_pdf=False):
    fx = HERE / "evals/fixtures"
    pos = duf((fx / "control_12.md").read_text())
    neg = duf((fx / "control_broken.md").read_text())
    ok = True
    print("positive control:", json.dumps(pos))
    if not (pos["bound"] == 12 and pos["unbound"] == 0 and pos["dropped"] == 0 and pos["ok"]):
        print("FAIL positive control expected bound 12 / unbound 0 / dropped 0"); ok = False
    print("negative control:", json.dumps(neg))
    if not (neg["unbound"] == 3 and neg["dropped"] == 1 and not neg["ok"]):
        print("FAIL negative control expected unbound 3 / dropped 1 / ok False"); ok = False
    for name, kw, must in MUST_TRIP:
        f = checks((fx / name).read_text(), **kw)
        print(f"{name} checks:", len(f), "failures:", *[" - " + x for x in f], sep="\n")
        for cid in must:
            if any(x.startswith(cid + " ") for x in f):
                print(f"tripped: {cid} by {name}")
            else:
                print(f"FAIL {name} must trip {cid}"); ok = False
    # ---- C1 (swap): only a line that is exactly a schema template is exempt; a claim smuggled into a near-template line fails
    nouns, F = ["alder grey", "doe"], R["forms"]
    def swap(body, block="B3"):
        return [x for x in checks(f"## {block} Title\n{body}\n", which="swap", target_nouns=nouns) if x.startswith("C1 ")]
    tier_line = F["B6"]["tier"].format(tier="high")
    li_line = "**LinkedIn:** " + R["linkedin"]["read"]["search"]
    exact = {"a gap line": ("B3", "- **Role:** Not determined"), "a fallback line": ("B8", "- No counter-evidence found"),
             "the tier line": ("B6", tier_line), "the LinkedIn status line": ("B4", li_line),
             "a fallback theme line": ("B4", "- Not determined")}
    smuggled = {"a claim after 'Not determined'": ("B3", "- **Role:** Not determined, though the firm is among the largest in the industry and has grown for a decade."),
                "a claim before 'Not determined'": ("B3", "- **Path:** Rose through the ranks of the industry very quickly, then Not determined."),
                "a claim after the tier line": ("B6", tier_line + " The industry is changing quickly and every leader is feeling the pressure."),
                "a claim in the tier line's place": ("B6", "**Evidence tier:** high: every leader in the industry responds to a deadline this way."),
                "a claim after the fallback": ("B8", "- No counter-evidence found, because every leader in the industry likes this kind of offer."),
                "a claim after the LinkedIn status": ("B4", li_line + ". Every executive in the industry keeps a profile like this one."),
                "a reverses-if line with no noun": ("B8", "- **Against:** Alder Grey is expanding [1]. **Reverses if:** the industry turns against this kind of firm for a decade.")}
    bad_ex = [k for k, (b_, x) in exact.items() if swap(x, b_)]
    bad_sm = [k for k, (b_, x) in smuggled.items() if not swap(x, b_)]
    if bad_ex or bad_sm:
        print("FAIL C1 swap exemptions: template-exact lines that failed", bad_ex, "| smuggled claims that passed", bad_sm); ok = False
    else:
        print(f"passes: C1 swap exempts exactly {len(exact)} template lines (gap, fallback, tier, LinkedIn status); tripped by {len(smuggled)} claims smuggled into near-template lines")
    ids = {c["id"] for c in R["checks"] if "id" in c}
    blocks = {b["id"]: b for b in R["brief"]["sections"] + R["script"]["blocks"]}
    conditional = [(e["id"], blocks[e["id"]]["prints"], e.get("check")) for e in R["inventory"]["blocks"] if blocks[e["id"]]["prints"] != "always"]
    conditional += [(p["id"], p.get("prints"), p.get("check")) for p in R["inventory"]["parts"] if p["status"] == "conditional"]
    for pid, prints, cid in conditional:
        if cid not in ids:
            print(f"FAIL inventory {pid}: prints only when '{prints}' but no check enforces it (check: {cid})"); ok = False
    cf = chat_check((fx / "chat_control.md").read_text(), FIXTURE_NOUNS)
    if cf:
        print("FAIL chat_control.md (S4-10 in-chat fallback) must pass:", *cf, sep="\n - "); ok = False
    else:
        print("passes: chat_control.md (S4-10 in-chat brief)")
    if any(x.startswith("S4-10") for x in chat_check((fx / "chat_broken.md").read_text())):
        print("tripped: S4-10 by chat_broken.md (no label, page 2 marker missing)")
    else:
        print("FAIL chat_broken.md must trip S4-10"); ok = False
    print(f"inventory: {len(conditional)} conditional parts, each enforced by a check:", ", ".join(f"{p} {c}" for p, _, c in conditional))
    if script_numbers("1. OPEN\n2. QUESTION ORDER\n3 . O B J E C T I O N S\n4. CLOSE\n6. IF IT STALLS\n1. What did they say?\n", 3):
        print("tripped: C10 by a page 3 numbered 1, 2, 3, 4, 6 (a gap where P5 dropped)")
    else:
        print("FAIL C10 must trip on page-3 numbers 1, 2, 3, 4, 6"); ok = False
    split = block_breaks((fx / "split_table_pages.txt").read_text().split("\f"), (fx / "control_12.md").read_text())
    if len(split) == 2 and "page 2 opens on 'WHATTHERECORD" in split[0] and "split across pages [1, 2]" in split[1]:
        print("tripped: C19 by split_table_pages.txt (a v6 render: page 2 opens on the rest of B6's table)")
    else:
        print("FAIL split_table_pages.txt must trip C19 twice (page 2 opens inside a block; B6 split):", split); ok = False
    pypdf_page2 = "page 2 of 3Intelligence Brief · Jane Doe, Alder Grey Capital · Prepared for you (internal)\nW H O  D E C I D E S\nDecision maker"
    if block_breaks(["", pypdf_page2]):
        print("FAIL C19 must read past the footer line pypdf puts first:", block_breaks(["", pypdf_page2])); ok = False
    elif not block_breaks(["", pypdf_page2.replace("W H O  D E C I D E S", "W H A T  T H E  R E C O R D")]):
        print("FAIL C19 must still trip when page 2 opens on another block after the footer line"); ok = False
    else:
        print("passes: C19 reads past pypdf's footer line; trips when page 2 opens on another block")
    c12 = (fx / "control_12.md").read_text()
    blind = [   # (case, check id, the control_12.md edit the check missed before Oct 14)
        ("C12 on a gap in a table cell ('The gate: *Not determined*') with no question asked", "C12",
         c12.replace("- **The gate:** Not determined", "| Item | Read |\n|---|---|\n| The gate: *Not determined* | none |")
            .replace("The gate: what must be true before the committee says yes?", "none")),
        ("C12 on two questions in one Still open item", "C12",
         c12.replace("The gate: what must be true before the committee says yes? |",
                     "The gate: who signs? What must be true? Who else? When? Why now? |")),
        ("C14 on '**Label**:' twice in one B9 bullet", "C14",
         c12.replace("- **What to bring:** the introduction", "- **What to bring**: the deck. **Why**: the introduction")),
        ("C14 on a Fallback without The ask", "C14",
         c12.replace("- **What to bring:** the introduction", "- **What to bring:** the deck. **Fallback:** the introduction")),
        ("C14 on '(Unconfirmed)'", "C14", c12.replace("the introduction to the custodian [12]", "the custodian (Unconfirmed) [12]")),
        ("C16 on 'read from your file' while a ledger row cites a LinkedIn profile page", "C16",
         (fx / "linkedin_search.md").read_text().replace("read from search results", "read from your file")),
        ("C17 on a masthead that prints the source-type count as the facts cited", "C17",
         c12.replace("source types, 12 cited", "source types, 10 cited")),
        ("C16 on a LinkedIn row cited as linkedin.com, not as its search result", "C16",
         (fx / "linkedin_search.md").read_text().replace("Fact 6 about Alder Grey Capital | [linkedin.com, search result]",
                                                        "Fact 6 about Alder Grey Capital | [linkedin.com]")),
        ("C16 on 'read from search results' with no ledger row citing the profile", "C16",
         c12.replace("read from your file", "read from search results")),
        ("C16 on the reason 'file not given' in a run from Oct 15 (AID-63: search reads LinkedIn now)", "C16",
         (fx / "linkedin_declined.md").read_text().replace("you declined", "file not given").replace("| Sep 20, 2026 ·", "| Oct 15, 2026 ·")),
        ("C16 on a bold Coverage label that states another status than B4", "C16",
         (fx / "linkedin_search.md").read_text().replace("· LinkedIn: read from search results |", "· **LinkedIn:** read from your file |")),
        ("C16 on the retired reason 'no browser here' (the R9 run skipped the saved-PDF question)", "C16",
         (fx / "linkedin_declined.md").read_text().replace("not read: you declined", "not read: no browser here")),
        ("C16 on an unread LinkedIn asked inside another Still open item", "C16",
         (fx / "linkedin_declined.md").read_text().replace("says yes? |", "says yes? · The gate: could you share the LinkedIn profile? |")),
    ]
    bold = (fx / "linkedin_search.md").read_text().replace("· LinkedIn: read from search results |", "· **LinkedIn:** read from search results |")
    if [x for x in checks(bold) if x.startswith("C16 ")]:   # the Oct 15 chat reply A5: the same words, printed bold
        print("FAIL C16 must pass a Coverage row whose LinkedIn label is bold"); ok = False
    else:
        print("passes: C16 on a bold '**LinkedIn:**' label in Coverage (it prints the same words)")
    old = (fx / "linkedin_declined.md").read_text().replace("you declined", "file not given")   # Sep 20: before AID-63
    if [x for x in checks(old) if x.startswith("C16 ")]:
        print("FAIL C16 must pass 'file not given' in a run before Oct 15 (the frozen Oct 14 targets)"); ok = False
    else:
        print("passes: C16 on 'file not given' in a run before Oct 15 (the frozen targets keep the reasons of their day)")
    for case, cid, md in blind:
        if any(x.startswith(cid + " ") for x in checks(md)):
            print(f"tripped: {case}")
        else:
            print(f"FAIL {case} must trip {cid}"); ok = False
    q = c12.replace("- **Against:** the close date has moved once before this year [11].",
                    '- **Against:** she said "you can\'t let it just rip" [11].')
    q = re.sub(r"^\| \[11\] \|[^|]*\|", '| [11] | "can\'t let it just rip" |', q, flags=re.M)
    if [x for x in checks(q) if x.startswith("C17 ")]:
        print("FAIL C17 must pass a sentence that quotes its ledger claim word for word (a claim of short words)"); ok = False
    elif not [x for x in checks(q.replace("you can\'t let it just rip", "it can go sideways")) if x.startswith("C17 ")]:
        print("FAIL C17 must still trip when the sentence does not hold the short claim"); ok = False
    else:
        print("passes: C17 on a sentence quoting a short-word claim; trips when it quotes something else")
    words = c12.replace("the introduction to the custodian [12]", "the introduction to the custodian [12]; it may affect her effect on issued notes")
    if [x for x in checks(words) if x.startswith("C9 ")]:
        print("FAIL C9 must pass 'affect', 'effect' and 'issued' (no FEC, no sued inside them)"); ok = False
    elif not [x for x in checks(words.replace("issued notes", "notes filed with the FEC")) if x.startswith("C9 ")]:
        print("FAIL C9 must still trip on 'filed with the FEC'"); ok = False
    else:
        print("passes: C9 on 'affect', 'effect', 'issued'; trips on 'filed with the FEC'")
    dd = (fx / "dates_read_day.md").read_text()
    dated = re.sub(r"\(https://example\.org/(\d+)\)", r"(https://example.org/2026/09/20/\1)", dd)
    if [x for x in checks(dated) if x.startswith("C18 ")]:
        print("FAIL C18 must pass rows dated the run day whose URLs carry that date (an earnings day)"); ok = False
    elif not [x for x in checks(dated.replace("/2026/09/20/", "/2026/09/19/")) if x.startswith("C18 ")]:
        print("FAIL C18 must still trip when the URLs carry another date"); ok = False
    else:
        print("passes: C18 on run-day rows whose URLs carry the run day; trips when the URLs carry another day")
    cell = c12.replace("- **The gate:** Not determined", "| Item | Read |\n|---|---|\n| The gate: *Not determined* | none |")
    if [x for x in checks(cell) if x.startswith("C12 ")]:
        print("FAIL C12 must read 'The gate: *Not determined*' in a table cell as the gap Still open asks about"); ok = False
    for name, kw in MUST_PASS:
        f = checks((fx / name).read_text(), **kw)
        if f:
            print(f"FAIL {name} {kw or ''} must pass every check:", *f, sep="\n - "); ok = False
        else:
            print(f"passes: {name} {kw or ''}")
    ss = _sentences('Fortune ranks her No. 2 on its list [14]. "We are focused. That is where we are" [3].\n'
                    'She has led many large teams over a long career. It holds [2]. Started Alder Grey, Inc. [1]; CEO since 2021 [8].')
    if ss == ['Fortune ranks her No. 2 on its list [14].', '"We are focused. That is where we are" [3].',
              "She has led many large teams over a long career.", "Started Alder Grey, Inc. [1]; CEO since 2021 [8]."]:
        print("passes: C1 sentences: 'No. 2', a quoted period and 'Inc. [1]' end no sentence; an uncited sentence still stands alone")
    else:
        print("FAIL C1 sentence split:", ss); ok = False
    hits = {h.lower() for h in plain_hits((fx / "jargon.md").read_text())}
    if hits != {w.lower() for w in JARGON}:
        print(f"FAIL jargon.md: C11 must list exactly {JARGON} (got {sorted(hits)})"); ok = False
    else:
        print(f"tripped: C11 by jargon.md, each of {len(JARGON)} words; 'asset manager' and quoted words exempt")
    if plain_hits(" ".join(FINANCE)):
        print(f"FAIL C11 must pass ordinary finance terms (got {plain_hits(' '.join(FINANCE))})"); ok = False
    elif plain_hits('He is 6\'2" tall.\nShe is a valued asset [1].\n"We buy patience" [3]') != ["asset"]:
        print("FAIL C11: a stray quote mark must not exempt the lines after it"); ok = False
    else:
        print(f"passes: C11 on {len(FINANCE)} finance terms; a stray quote mark exempts nothing after its line")
    rounds_only = (fx / "battery_standard.jsonl").read_text().splitlines()   # the five rounds, 20 searches: rc2's whole research
    base_q = ['"Jane Doe" "Alder Grey Capital" managing partner', '"Jane Doe" Alder Grey career OR joined OR appointed OR promoted',
              '"Alder Grey Capital" news OR announces OR partnership OR acquisition OR raises 2026', 'aldergrey.example about OR mission',
              '"Jane Doe" interview OR podcast OR panel OR quoted OR keynote', '"Jane Doe" site:x.com OR site:substack.com OR site:bsky.app',
              '"Jane Doe" board OR trustee OR advisory OR member OR association OR alumni', '"Jane Doe" author OR paper OR patent OR whitepaper OR book',
              '"Jane Doe" site:sec.gov', '"Jane Doe" OR "Alder Grey Capital" conference OR summit OR webinar 2026',
              '"Alder Grey Capital" lawsuit OR layoffs OR departure OR decline OR criticism']
    def base_steps(qs, step=6):   # the base pass: each source type's template, sent in steps
        return [json.dumps({"type": "assistant", "message": {"id": f"base{i}", "content": [{"type": "tool_use", "id": f"tb{i}{k}", "name": "WebSearch", "input": {"query": q}}
                                                                                           for k, q in enumerate(qs[i:i + step])]}}) for i in range(0, len(qs), step)]
    base_lines = base_steps(base_q)
    bt = [rounds_only[0]] + base_lines + rounds_only[1:]   # C21: a synthetic standard run, 11 base + 20 round searches
    ROW = "| **Run** | Oct 16, 2026 · standard · US · FULL · 31 searches (11 base) in 5 rounds |"
    f, summary = battery(bt, "standard", ROW)
    if f:
        print("FAIL battery_standard.jsonl must pass C21:", summary, *f, sep="\n - "); ok = False
    else:
        print(f"passes: C21 on battery_standard.jsonl ({summary}) and its Run row")
    r1 = next(i for i, ln in enumerate(bt) if "Round 1 (" in ln)
    li_typed = bt[r1].replace('"query": "\\"Jane Doe\\" \\"Alder Grey Capital\\"", "allowed_domains": ["linkedin.com"]',
                             '"query": "site:linkedin.com/in \\"Jane Doe\\" \\"Alder Grey Capital\\""')
    plain = [re.sub(r'"query": "[^"]*(?:\\"[^"]*)*", "allowed_domains": \[[^\]]*\]', '"query": "Jane Doe news"', ln) for ln in bt]
    plain = [re.sub(r'"query": "(?:[^"\\]|\\.)*"', '"query": "Jane Doe news"', ln) for ln in plain]
    first = '{"type": "assistant", "message": {"content": [{"type": "tool_use", "name": "WebSearch", "input": {"query": "Jane Doe"}}]}}'
    fetch = '{"type": "assistant", "message": {"content": [{"type": "tool_use", "name": "WebFetch", "input": {"url": "https://www.linkedin.com/in/jane-doe-example"}}]}}'
    chrome = '{"type": "assistant", "message": {"content": [{"type": "tool_use", "name": "mcp__claude-in-chrome__navigate", "input": {}}]}}'
    r3 = next(i for i, ln in enumerate(bt) if "Round 3 (" in ln)
    r2 = next(i for i, ln in enumerate(bt) if "Round 2 (" in ln)
    r4 = next(i for i, ln in enumerate(bt) if "Round 4 (" in ln)
    short4 = bt[r4][:bt[r4].rindex(', {"type": "tool_use"')] + "]}}"
    cases = [("round 3 left out", bt[:r3] + bt[r3 + 2:], "", "not run"),
             ("no operators or filters", plain, "", "carry an operator"),
             ("round 1's LinkedIn query typed as site:", bt[:r1] + [li_typed] + bt[r1 + 1:], "", "typed site:"),
             ("a linkedin.com page requested", bt + [fetch], "", "linkedin.com page"),
             ("a browser tool called", bt + [chrome], "", "browser tool"),
             ("round 3 before round 2", bt[:r2] + bt[r3:r3 + 2] + bt[r2:r3] + bt[r3 + 2:], "", "order"),
             ("round 4 one query short", bt[:r4] + [short4] + bt[r4 + 1:], "", "fewer than 4"),
             ("a Run row that miscounts", bt, "| **Run** | Oct 16, 2026 · standard · 30 searches (11 base) in 5 rounds |", "the history shows"),
             ("a Run row with no base count", bt, "| **Run** | Oct 16, 2026 · standard · 31 searches in 5 rounds |", "no base count"),
             ("no base pass (the five rounds alone, rc2's whole research)", rounds_only, "", "no base pass"),
             ("a source type (F4, the organisation in its own words) never searched", [ln for ln in bt if "aldergrey.example about" not in ln]
              + [], "", "never searched in the base pass")]
    bare = [re.sub(r'\{"type": "thinking", "thinking": "Round [^}]*\}, ', "", ln) for ln in bt]   # the round lines dropped
    f, summary = battery(bare, "standard")
    if f:
        print("FAIL C21 must pass the same searches without round lines, one batch per round:", summary, f); ok = False
    else:
        print(f"passes: C21 on battery_standard.jsonl without its round lines ({summary}): each batch is a round")
    single = []
    for ln in bare:   # the same searches, one per step: no batch is a round of 4
        e = json.loads(ln)
        tools = [x for x in (e.get("message", {}).get("content") or []) if x.get("type") == "tool_use"] if e.get("type") == "assistant" else []
        single += [json.dumps({"type": "assistant", "message": {"content": [t]}}) for t in tools] if tools else [ln]
    cases.append(("the same searches one per step, no round lines", single, "", "fewer than"))
    e2 = json.loads(bt[r2]); c = e2["message"]["content"]   # round 2's line and its 4 searches, sent in two steps
    halves = [{"type": "assistant", "message": {"content": c[:3]}}, {"type": "assistant", "message": {"content": c[3:]}}]
    cases.append(("round 2 sent over two steps under its line", bt[:r2] + [json.dumps(h) for h in halves] + bt[r2 + 1:], "", "several steps"))
    first = [bt[0]] + [ln if i == r1 else re.sub(r'\{"type": "thinking", "thinking": "Round [^}]*\}, ', "", ln) for i, ln in enumerate(bt[1:], 1)]
    f, summary = battery(first, "standard")
    if f or any("Round 2 (" in ln for ln in first):
        print("FAIL C21 must pass round 1's line followed by rounds 2-5 as one batch each, unnamed:", summary, f); ok = False
    else:
        print(f"passes: C21 when only round 1's line is stated and each later round is one batch ({summary})")
    dk = fx / "battery_desktop"   # the Oct 17 Claude desktop shape: the research job in its own file, each parallel search its own line, gap fill after round 5
    dfiles = [dk / "session.jsonl", dk / "session/subagents/agent-fixture.jsonl"]
    drow = "| **Run** | Oct 17, 2026 · deep · US · FULL · 55 searches (14 base) in 5 rounds |"
    f, summary = battery(history_lines(dfiles), "deep", drow)
    if f or "55 searches (14 base) in 5 rounds" not in summary or "per round [6, 7, 7, 6, 6]" not in summary:
        print("FAIL C21 must read battery_desktop as 14 base, rounds of 6, 7, 7, 6 and 6, then 9 later searches:", summary, f); ok = False
    else:
        print(f"passes: C21 and C22 on battery_desktop, a Claude desktop run whose job keeps its own file ({summary})")
    dmain = [json.loads(x) for x in dfiles[0].read_text().splitlines()]
    djob = dfiles[1].read_text().splitlines()
    def dl(rows): return [json.dumps(x) for x in rows] + djob
    q2 = next(i for i, x in enumerate(dmain) if "toolu_q2" in json.dumps(x) and x["type"] == "assistant")
    early = dict(dmain[q2], message={"id": "m2b", "role": "assistant", "content": [{"type": "tool_use", "id": "toolu_e", "name": "WebSearch", "input": {"query": "Jane Doe"}}]})
    for name, lines, row, want in (
            ("the job's file read after the main file, not by time", [ln for p in dfiles for ln in p.read_text().splitlines()], "", "between the first and the last search"),
            ("a Run row that counts the two gap-fill steps as rounds 6 and 7", history_lines(dfiles), drow.replace("in 5 rounds", "in 7 rounds"), "the history shows"),
            ("the second setup call with no skip line of its own", dl(dmain[:q2 - 1] + dmain[q2:]), drow, "no line of the reply before it"),
            ("a search before the popup's answer", dl(dmain[:q2 + 1] + [early] + dmain[q2 + 1:]), drow, "kept working after asking")):
        f, _ = battery(lines, "deep", row)
        if not any(want in x for x in f):
            print(f"FAIL C21/C22 must trip on {name} (want '{want}'):", f); ok = False
        else:
            print(f"tripped: {'C22' if 'skip' in name or 'popup' in name else 'C21'} by {name}")
    row = "| [{n}] | Fact | [{h}]({u}) | Measured | Oct 1, 2026 |\n"
    read = (row.format(n=1, h="aldergrey.example", u="https://www.aldergrey.example/team/#jane")
            + row.format(n=2, h="linkedin.com, search result", u="https://www.linkedin.com/in/jane-doe-example")
            + "| **Run** | Oct 16, 2026 · standard · US · FULL · 31 searches (11 base) in 5 rounds |\n")
    said = '{"type": "result", "result": "Treat it as C3 (single weak source). I can send the four-field debrief."}'
    cases.append(("a reply that says C3 and debrief", bt + [said], "", "C11 reply"))
    cases.append(("a ledger page the run never opened", bt, read + row.format(n=3, h="news.example", u="https://news.example/jane-doe"), "never opened"))
    moved = ['{"type": "assistant", "message": {"content": [{"type": "tool_use", "id": "toolu_r", "name": "WebFetch", "input": {"url": "https://old.example/a"}}]}}',
             '{"type": "user", "message": {"content": [{"type": "tool_result", "tool_use_id": "toolu_r", "content": "REDIRECT DETECTED: https://new.example/a"}]}}']
    f, _ = battery(bt + moved, "standard", read + row.format(n=3, h="new.example", u="https://new.example/a"))
    if f:
        print("FAIL C21 must pass a ledger of opened pages (one by redirect), its LinkedIn row unopened:", f); ok = False
    else:
        print("passes: C21 on a ledger whose pages the run opened (www., a fragment, a redirect), LinkedIn cited from its search result")
    plain = '{"type": "result", "result": "Treat it as a single, weaker source. After the call, I can take your after-call notes."}'
    f, _ = battery(bt + [plain], "standard")
    if f:
        print("FAIL C11 must pass a plain reply:", f); ok = False
    else:
        print("passes: C11 on a plain closing reply ('a single, weaker source', 'after-call notes')")
    for case, lines, brief, want_msg in cases:
        f, _ = battery(lines, "standard", brief)
        if any(want_msg in x for x in f):
            print(f"tripped: C21 by {case}")
        else:
            print(f"FAIL C21 must trip on {case} (got {f})"); ok = False
    # ---- hard-coded values (C27): the page and the wording come from pcp.yaml; a literal in a render script is caught
    if hardcoded_check():
        print("FAIL hardcoded must pass on the shipped scripts:", *hardcoded_check(), sep="\n - "); ok = False
    else:
        lay = json.loads((HERE / "format/layout.json").read_text())
        print(f"passes: C27 the renderer holds no layout number or colour ({len(lay['layout'])} layout values, {len(lay['balance'])} balance values, "
              f"{len(lay['colors'])} colours, the ladders and {len(lay['page_budget']['text_sizes_pt'])} text sizes are in pcp.yaml)")
    with tempfile.TemporaryDirectory() as td:
        root = pathlib.Path(td)
        (root / "format").mkdir()
        for rel in ("format/talyx_pdf.py", "format/layout.json", "render_skill.py", "pcp.yaml", "skills/pre-call-prep/SKILL.md", "skills/pre-call-prep/assets/intake-template.csv"):
            (root / rel).parent.mkdir(parents=True, exist_ok=True)
            (root / rel).write_text((HERE / rel).read_text())
        (root / "format/assets").mkdir()
        for asset in (HERE / "format/assets").iterdir():   # the renderer reads its font and logo when it builds a page's CSS
            (root / "format/assets" / asset.name).write_bytes(asset.read_bytes())
        base_css, base_rs = (root / "format/talyx_pdf.py").read_text(), (root / "render_skill.py").read_text()
        base_md = (root / "skills/pre-call-prep/SKILL.md").read_text()
        phrase = R["families"][0]["extract"]   # F1's extract: a value pcp.yaml owns, 20+ characters, several words
        lay0 = (root / "format/layout.json").read_text()
        (root / "format/layout.json").write_text(lay0.replace('"ledger": 10', '"ledger": 9.5'))
        f = hardcoded_check(root)
        (root / "format/layout.json").write_text(lay0)
        print("tripped: C27 sizes by a ledger set to 9.5 pt (the floor is 10)" if any("below the 10.0 pt floor" in x for x in f)
              else f"FAIL C27 sizes must trip on 9.5 pt text (got {f})")
        ok = ok and any("below the 10.0 pt floor" in x for x in f)
        for case, rel, new_text, want in (
                ("a CSS number in the renderer", "format/talyx_pdf.py", base_css.replace("{L['page_content__padding']}", "0.55in", 1), "talyx_pdf.py's CSS"),
                ("a colour in the renderer", "format/talyx_pdf.py", base_css + '\nX = "#123456"\n', "holds a colour"),
                ("a decimal in the balance script", "format/talyx_pdf.py", base_css.replace("CFG.spare_in", "0.2", 1), "balance script"),
                ("a block title spelled in render_skill.py", "render_skill.py", base_rs + '\nX = "Strongest case against"\n', "render_skill.py"),
                ("a registry value typed into SKILL.md's template (render_skill.py)", "render_skill.py", base_rs.replace("This file is the procedure:", "Identity: " + phrase + ". This file is the procedure:", 1), "writes"),
                ("a registry value typed into SKILL.md by hand", "skills/pre-call-prep/SKILL.md", base_md + "\nIdentity means " + phrase + ".\n", "typed in by hand")):
            (root / rel).write_text(new_text)
            f = hardcoded_check(root)
            (root / rel).write_text({"format/talyx_pdf.py": base_css, "render_skill.py": base_rs}.get(rel, base_md))
            if any(want in x for x in f):
                print(f"tripped: C27 by {case}")
            else:
                print(f"FAIL C27 must trip on {case} (got {f})"); ok = False
    # ---- skill (C29): SKILL.md is the procedure, capped, every step names its files, every 2.1.0 item is reachable
    sf, ss = skill_check()
    if sf:
        print("FAIL skill must pass on the shipped plug-in:", *sf[:5], sep="\n - "); ok = False
    else:
        print(f"passes: C29 skill: SKILL.md {ss['size']} characters (cap {ss['max']}, target {ss['target']}); {ss['steps_named']} of {ss['steps']} steps name the files they load; "
              f"reachable {ss['reachable']}/{ss['total']} baseline items ({', '.join(f'{k} {v}' for k, v in sorted(ss['how'].items()))})")
    real = (HERE / SKILL_DIR / "SKILL.md").read_text()
    pad = lambda n: real + "\n<!-- " + "x" * (n - len(real.encode()) - len("\n<!--  -->")) + " -->"
    at_cap, over = pad(R["skill"]["max_chars"]), pad(R["skill"]["max_chars"] + 1)
    if len(at_cap.encode()) != R["skill"]["max_chars"] or len(over.encode()) != R["skill"]["max_chars"] + 1:
        print("FAIL skill self-test: the padded copies are not exactly the cap and the cap plus one"); ok = False
    elif any("characters" in x for x in skill_check(skill_text=at_cap)[0]) or not any("characters" in x for x in skill_check(skill_text=over)[0]):
        print(f"FAIL C29 must pass SKILL.md at exactly {R['skill']['max_chars']} characters and fail it at {R['skill']['max_chars'] + 1}"); ok = False
    else:
        print(f"passes: C29 size cap: SKILL.md at {R['skill']['max_chars']} characters passes, at {R['skill']['max_chars'] + 1} fails")
    loadline = re.search(r"^\*\*Load:\*\*.*profile\.md.*$", real, re.M).group(0)
    cfgline = re.search(r"^\*\*Config:\*\* `pcp.json` keys `families.*$", real, re.M).group(0)
    for case, text, want in (
            ("a step with no Load line", real.replace(loadline + "\n\n", "", 1), "names no file"),
            ("a step that loads a file that is not there", real.replace("references/profile.md", "references/nope.md", 1), "does not exist"),
            ("a reference no step loads, whose 2.1.0 items are then in no loaded file", real.replace(loadline, "**Load:** `references/checks.md`.", 1), "baseline items are in neither"),
            ("a reference no step loads", real.replace(loadline, "**Load:** `references/checks.md`.", 1), "loaded by no step"),
            ("a Config line that claims keys its file does not hold", real.replace(cfgline, "**Config:** `pcp.json` keys `families.*.nonexistent` -- none.", 1), "holds none"),
            ("a Config line that drops the keys families need", real.replace(cfgline, "", 1), "baseline items are in neither")):
        f = skill_check(skill_text=text)[0]
        if any(want in x for x in f):
            print(f"tripped: C29 by {case}")
        else:
            print(f"FAIL C29 must trip on {case} (wanted '{want}'; got {f[:2]})"); ok = False
    # ---- --latest finds a session's subagent transcripts too (a background collection job keeps its searches there)
    with tempfile.TemporaryDirectory() as td:
        import os
        cfg, work = pathlib.Path(td) / "cfg", pathlib.Path(td) / "work"
        work.mkdir()
        proj = cfg / "projects" / re.sub(r"[^A-Za-z0-9]", "-", str(work.resolve()))
        (proj / "sess1" / "subagents").mkdir(parents=True)
        (proj / "sess1.jsonl").write_text("{}\n")
        (proj / "sess1" / "subagents" / "agent-a.jsonl").write_text("{}\n")
        old = os.environ.get("CLAUDE_CONFIG_DIR")
        os.environ["CLAUDE_CONFIG_DIR"] = str(cfg)
        try:
            found = [p.name for p in find_history(host="claude", cwd=work)]
        finally:
            os.environ.pop("CLAUDE_CONFIG_DIR") if old is None else os.environ.update(CLAUDE_CONFIG_DIR=old)
        if found != ["sess1.jsonl", "agent-a.jsonl"]:
            print(f"FAIL --latest must return the session's file and its subagent transcript, under $CLAUDE_CONFIG_DIR (got {found})"); ok = False
        else:
            print("passes: battery --latest reads the session file and its subagent transcripts, under $CLAUDE_CONFIG_DIR")
    # ---- versions (C30): one version everywhere; a manifest, a marketplace entry, a header or the changelog that disagrees fails
    vf, vfound = versions_check()
    if vf:
        print("FAIL versions must agree on the shipped repo:", *vf[:5], sep="\n - "); ok = False
    else:
        print(f"passes: C30 versions: {len(vfound)} version strings in {len({x[0] for x in vfound})} files all say {vfound[0][2]}")
    if (HERE.parents[1] / "build").is_dir():
        with tempfile.TemporaryDirectory() as td:
            repo = pathlib.Path(td)
            for rel in VERSION_FILES:
                if (HERE.parents[1] / rel).exists():
                    (repo / rel).parent.mkdir(parents=True, exist_ok=True)
                    (repo / rel).write_text((HERE.parents[1] / rel).read_text())
            cur = vfound[0][2]
            for rel, old, new in (("plugins/pcp/.codex-plugin/plugin.json", f'"version": "{cur}"', '"version": "9.9.9"'),
                                  (".claude-plugin/marketplace.json", f'"version": "{cur}",\n      "author"', '"version": "9.9.9",\n      "author"'),
                                  ("plugins/pcp/skills/pre-call-prep/SKILL.md", f"(v{cur})", "(v9.9.9)"),
                                  ("plugins/pcp/CHANGELOG.md", f"## [{cur}]", "## [9.9.9]"),
                                  ("build/plugin.source.json", f'"version": "{cur}"', '"version": "9.9.9"')):
                f = repo / rel
                if not f.exists() or old not in f.read_text():
                    print(f"FAIL versions self-test: no '{old[:30]}' in {rel} to change"); ok = False; continue
                raw = f.read_text()
                f.write_text(raw.replace(old, new, 1))
                bad, _ = versions_check(repo)
                f.write_text(raw)
                if any(rel in x for x in bad):
                    print(f"tripped: C30 by a version that disagrees in {rel}")
                else:
                    print(f"FAIL C30 must trip on a different version in {rel} (got {bad})"); ok = False
    # ---- gates: every 2.1.0 gate is at least as strict now; a loosened gate is caught by the table itself
    rows_g, fails_g = gates_table()
    if fails_g:
        print("FAIL gates must show no gate looser than 2.1.0:", *fails_g, sep="\n - "); ok = False
    else:
        n_g = {v: sum(1 for r in rows_g if r[4] == v) for v in ("same", "stricter", "looser")}
        print(f"passes: gates: {len(rows_g)} rows against 2.1.0: {n_g['same']} same, {n_g['stricter']} stricter, {n_g['looser']} looser")
    with tempfile.TemporaryDirectory() as td:
        import importlib.util
        root = pathlib.Path(td)
        for rel in ("eval.py", "render_skill.py", "pcp.json", "evals/baseline-2.1.0.json", "evals/ref21.py", "format/talyx_pdf.py", "format/layout.json"):
            (root / rel).parent.mkdir(parents=True, exist_ok=True)
            (root / rel).write_text((HERE / rel).read_text())
        src = (root / "eval.py").read_text()
        for case, old, new, want in (
                ("C9 stems read as whole words again (2.1.0's inflections hospitalization, divorces, lawsuits no longer trip)", "stem = w.endswith(\"*\")", "stem = False", "C9"),
                ("C1 read in B1 and B3-B8 only again (the questions and the meeting angle unread)", 're.match(r"B[1-9]$", k)]:   # every block that states', 're.match(r"B1$|B[3-8]$", k)]:   # every block that states', "C1"),
                ("C7 not enforcing one never-say phrase", 'if p.lower() in body.lower():\n                    fails.append(f"C7', 'if p.lower() in body.lower() and p != R["guardrails"]["never_say"][0]:\n                    fails.append(f"C7', "C7")):
            if old not in src:
                print(f"FAIL gates self-test: the text to loosen for '{case}' is not in eval.py"); ok = False; continue
            (root / "eval.py").write_text(src.replace(old, new, 1))
            spec = importlib.util.spec_from_file_location("eval_loosened", root / "eval.py")
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            _, f = mod.gates_table(root)
            if any(x.startswith(f"gates: {want} ") for x in f):
                print(f"tripped: gates by {case}")
            else:
                print(f"FAIL gates must report {want} looser for: {case} (got {f[:2]})"); ok = False
        (root / "eval.py").write_text(src)
        pj = json.loads((HERE / "pcp.json").read_text())
        for case, drop in (("C9 compound list without countersued", "countersued"), ("C9 compound list without schoolchildren", "schoolchildren")):
            for topic in pj["exclusions"]["compounds"]:
                if drop in pj["exclusions"]["compounds"][topic]:
                    pj["exclusions"]["compounds"][topic].remove(drop)
            (root / "pcp.json").write_text(json.dumps(pj))
            spec = importlib.util.spec_from_file_location("eval_loosened", root / "eval.py")
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            _, f = mod.gates_table(root)
            if any(x.startswith("gates: C9 ") for x in f):
                print(f"tripped: gates by a loosened compound list ({case[3:]})")
            else:
                print(f"FAIL gates must report C9 looser for: {case} (got {f[:2]})"); ok = False
        (root / "pcp.json").write_text((HERE / "pcp.json").read_text())
    # ---- C9 (Daniel, Oct 17): word-start keywords plus the compound list
    c9 = lambda w: any(x.startswith("C9 ") for x in checks(f"## B3 Title\nShe mentioned {w} once.\n", which="exclusions"))
    inflect = ["diagnosed", "diagnostic", "illness", "illnesses", "hospital", "hospitalization", "hospitalised", "divorce", "divorced", "divorces", "his wife", "her husband",
               "children", "donated to", "FEC", "campaign contribution", "campaign contributions", "lawsuit", "lawsuits", "sued", "plaintiff", "plaintiffs"]
    comps = [c for v in R["exclusions"]["compounds"].values() for c in v]
    missed = [w for w in inflect if not c9(w)] + [c for c in comps if not c9(c)] + [w for w in ("Countersued", "COUNTERSUING") if not c9(w)]
    fired = [w for w in ("issued", "pursued", "effect", "affected", "reissued", "sue") if c9(w)]
    if missed or fired:
        print(f"FAIL C9: must trip on {missed}; must not trip on {fired}"); ok = False
    else:
        print(f"passes: C9 trips on countersued and {len(comps)} listed compounds and on all {len(inflect)} 2.1.0 word forms; issued, pursued, effect, affected do not")
    # ---- parity (C28): nothing of the 2.1.0 baseline is removed or weakened without an approved decision
    pf, ps = parity()
    if pf:
        print("FAIL parity must pass on the shipped registry:", *pf[:5], sep="\n - "); ok = False
    else:
        print(f"passes: C28 parity: {ps['total']} items of the 2.1.0 baseline, {ps['kept']} kept, {ps['approved']} changed with an approved decision, "
              f"{ps['open']} open, {ps['unapproved']} unapproved; {ps['locked']} schema sections locked")
    import copy
    def mutated(fn):
        r2 = copy.deepcopy(R); fn(r2); return r2
    for case, fn, want in (
            ("a source type removed (F4)", lambda r: r["families"].remove(next(f for f in r["families"] if f["id"] == "F4")), "families.F4"),
            ("the FULL threshold weakened (standard 8 to 6)", lambda r: r["research"]["full_threshold"].update(standard=6), "research.full_threshold"),
            ("a rule's text weakened (S1-2)", lambda r: r["stages"][0]["rows"][1].update(text="Two or more people match: pick one."), "S1-2"),
            ("a setup question dropped (Q3)", lambda r: r["calibration"]["questions"].remove(next(q for q in r["calibration"]["questions"] if q["id"] == "Q3")), "Q3"),
            ("a grade field dropped from the claims", lambda r: r["records"]["claims"]["fields"].remove("tag"), "schema section 'records'"),
            ("a ledger form label changed", lambda r: r["forms"]["B1"]["fields"][0].update(label="Summary."), "schema section 'forms'"),
            ("a strength cap loosened (weak domain C3 to C1)", lambda r: r["grading"]["caps"].update(weak_domain="C1"), "schema section 'grading'"),
            ("a layout size changed", lambda r: r["page_budget"]["text_sizes_pt"].update(ledger=8), "schema section 'page_budget'"),
            ("the ledger set to 9.5 pt (Daniel's pin: 10 pt)", lambda r: r["page_budget"]["text_sizes_pt"].update(ledger=9.5), "below the pinned minimum"),
            ("the text floor lowered to 9.5 pt", lambda r: r["page_budget"].update(text_floor_pt=9.5), "Daniel pinned it at 10.0"),
            ("Q2's private-equity option reworded (Daniel, Oct 17: 2.1's text)", lambda r: r["calibration"]["questions"][1]["options"][2].update(description="GPs, LPs, portfolio companies; adds fund and portfolio news."), "Daniel pinned it at"),
            ("Q7's EU option reworded (Daniel, Oct 17: 2.1's text)", lambda r: r["calibration"]["questions"][6]["options"][1].update(description="Adds minimisation: working notes are deleted once the PDF renders."), "Daniel pinned it at"),
            ("the ledger source link changed from the domain (Daniel, Oct 17)", lambda r: r["grading"].update(source_link="url"), "Daniel pinned it at"),
            ("a brief rung's body set to 9 pt (Ben, Oct 13)", lambda r: r["page_budget"]["brief_ladder"][0].update(body_pt=9.0), "entries with body_pt below 10")):
        f, _ = parity(reg=mutated(fn))
        if any(want in x for x in f):
            print(f"tripped: C28 by {case}")
        else:
            print(f"FAIL C28 must trip on {case} (wanted '{want}'; got {f[:2]})"); ok = False
    with tempfile.TemporaryDirectory() as td:
        rt = pathlib.Path(td); (rt / "evals").mkdir()
        for fn in ("baseline-2.1.0.json", "DECISIONS.yaml", "schema.lock.json"):
            (rt / "evals" / fn).write_text((HERE / "evals" / fn).read_text())
        for fn in ("eval.py", "format/talyx_pdf.py"):
            (rt / fn).parent.mkdir(parents=True, exist_ok=True); (rt / fn).write_text((HERE / fn).read_text())
        weak = mutated(lambda r: r["research"]["full_threshold"].update(standard=6))
        with open(rt / "evals/DECISIONS.yaml", "a") as fh:
            fh.write('  - covers: ["research.full_threshold.standard"]\n    status: approved\n    by: test\n    source: self-test\n')
        f, _ = parity(root=rt, reg=weak)
        print("passes: C28 lets an approved decision cover a change" if not any("full_threshold" in x for x in f) else "FAIL an approved decision must cover its change"); ok = ok and not any("full_threshold" in x for x in f)
        (rt / "evals/baseline-2.1.0.json").write_text((rt / "evals/baseline-2.1.0.json").read_text().replace("Two or more people", "Two or more persons", 1))
        f, _ = parity(root=rt)
        if any("baseline-2.1.0.json was edited" in x for x in f):
            print("tripped: C28 by an edit to the frozen baseline")
        else:
            print("FAIL C28 must trip on an edit to baseline-2.1.0.json"); ok = False
    if ps["open"] or parity(strict=True)[0]:
        print(f"FAIL parity --strict must pass on the shipped registry: {ps['open']} decisions are still open"); ok = False
    else:
        print("passes: C28 --strict: no decision is open")
    with tempfile.TemporaryDirectory() as td:
        rt = pathlib.Path(td); (rt / "evals").mkdir()
        for fn in ("baseline-2.1.0.json", "DECISIONS.yaml", "schema.lock.json"):
            (rt / "evals" / fn).write_text((HERE / "evals" / fn).read_text())
        for fn in ("eval.py", "format/talyx_pdf.py"):
            (rt / fn).parent.mkdir(parents=True, exist_ok=True); (rt / fn).write_text((HERE / fn).read_text())
        with open(rt / "evals/DECISIONS.yaml", "a") as fh:
            fh.write('  - covers: ["research.full_threshold.standard"]\n    status: open\n    by: test\n    source: self-test\n')
        f, _ = parity(root=rt, reg=mutated(lambda r: r["research"]["full_threshold"].update(standard=6)), strict=True)
        if any("still open" in x for x in f):
            print("tripped: C28 --strict by a change whose decision is still open")
        else:
            print("FAIL parity --strict must fail an open decision"); ok = False
    # ---- D2 (a LinkedIn address the user gives may be read, no other) and MUST-FIX 8 (a subagent's own text is not the reply)
    li_url = "https://www.linkedin.com/in/jane-doe-example"
    user_msg = json.dumps({"type": "user", "message": {"role": "user", "content": f"Jane Doe, Alder Grey Capital. Her profile: {li_url}"}})
    fetch_li = lambda u: json.dumps({"type": "assistant", "message": {"id": "m-li", "content": [{"type": "tool_use", "id": "t-li", "name": "WebFetch", "input": {"url": u}}]}})
    g = battery([user_msg, fetch_li(li_url)] + bt[1:], "standard", ROW)[0]
    o = battery([user_msg, fetch_li("https://www.linkedin.com/in/someone-else")] + bt[1:], "standard", ROW)[0]
    if any("linkedin.com page was requested" in x for x in g) or not any("did not give" in x for x in o):
        print("FAIL D2: a LinkedIn page the user gave passes C21, any other linkedin.com page fails:", g, o); ok = False
    else:
        print("passes: D2 C21 allows the one LinkedIn address the user gave; tripped by any other linkedin.com page")
    side = json.dumps({"type": "assistant", "isSidechain": True, "message": {"id": "sub1", "content": [{"type": "text", "text": "Round 2 (role): query | query | query | query, searching now."}]}})
    mid = next(i for i, ln in enumerate(bt) if "Round 3" in ln)
    f = battery(bt[:mid] + [side] + bt[mid:], "standard", ROW)[0]
    if any("quiet" in x for x in f):
        print("FAIL a subagent's own text (isSidechain) must not count as the reply:", f); ok = False
    else:
        print("passes: C21 does not count a subagent's own text as the reply, and still counts its searches")
    # ---- quiet research (S2-10): rounds and progress stay out of the reply
    def msg(kind, text):
        return json.dumps({"type": "assistant", "message": {"content": [{"type": kind, kind if kind == "thinking" else "text": text}]}})
    run_row = ROW
    in_reply = [ln.replace('{"type": "thinking", "thinking": "Round', '{"type": "text", "text": "Round') for ln in bt]
    r3 = next(i for i, ln in enumerate(bt) if "Round 3" in ln)
    for case, lines, want_msg in (("a round line printed in the reply", in_reply, "round line went out in the reply"),
                                  ("a progress message between searches", bt[:r3] + [msg("text", "Two rounds done; searching their own words next.")] + bt[r3:], "between the first and the last search")):
        f, _ = battery(lines, "standard", run_row)
        if any(want_msg in x for x in f):
            print(f"tripped: C21 by {case}")
        else:
            print(f"FAIL C21 must trip on {case} (got {f})"); ok = False
    f, _ = battery([msg("text", "Researching Jane Doe, Alder Grey Capital. The results go in the brief.")] + bt, "standard", run_row)
    if f:
        print("FAIL C21 must pass one short status before the first search:", f); ok = False
    else:
        print("passes: C21 on one short status before the first search, rounds kept in the reasoning")
    # ---- every host's own history is readable (no 'unavailable'): Claude Code, Codex, ChatGPT, the Claude app
    for name, host, want in (("history_codex.jsonl", "Codex", None), ("history_chatgpt.json", "ChatGPT export", None), ("history_claudeapp.json", "Claude app export", None),
                             ("history_codex_noisy.jsonl", "Codex", "round line went out in the reply"),
                             ("history_codex_widget.jsonl", "Codex", "no line of the reply before it")):
        f, summary = battery((fx / name).read_text().splitlines(), "standard", run_row)
        if want is None and (f or not summary.startswith(host) or "31 searches (11 base) in 5 rounds" not in summary):
            print(f"FAIL {name} must pass C21 and C22 as a {host} history with 31 searches (11 base) in 5 rounds:", summary, f); ok = False
        elif want is not None and not any(want in x for x in f):
            print(f"FAIL {name} must trip ({want}); got {f}"); ok = False
        else:
            print(f"{'passes' if want is None else 'tripped'}: C21/C22 on {name} ({host}: {summary.split(': ', 1)[1]})" if want is None else f"tripped: {want} by {name} ({host})")
    widget = battery((fx / "history_codex_widget.jsonl").read_text().splitlines(), "standard", run_row)[0]
    for part in ("no line of the reply before it", "came back with no answer", "kept working after asking"):
        if any(part in x for x in widget):
            print(f"tripped: C22 {part} (a popup with no lead-in line, no answer, the run went on)")
        else:
            print(f"FAIL C22 must trip: {part} (got {widget})"); ok = False
    asked = [msg("text", "1. Who else has a say in custodian choices at Alder Grey?\n\nReply with your answer, or reply skip and I'll go on without it."),
             json.dumps({"type": "assistant", "message": {"content": [{"type": "tool_use", "name": "AskUserQuestion", "input": {"questions": [{"question": "Who else has a say in custodian choices at Alder Grey?"}]}}]}}),
             json.dumps({"type": "user", "message": {"role": "user", "content": "skip"}})]
    f, _ = battery(asked + bt, "standard", run_row)
    if any(x.startswith("C22") for x in f):
        print("FAIL C22 must pass a question written in the reply, with a skip rule, then the user's answer before the searches:", f); ok = False
    else:
        print("passes: C22 on a question in the reply with its skip rule, the run waiting for the answer")
    typed = [msg("text", "Setup: 1. Who is making the call? (1 Founder, 2 Sales) 2. Domain? (1 General, 2 Wealth) 3. Depth? 4. Where? Reply with one number per line, such as 1, 4, 1, 1.")]
    popup_init = json.dumps({"type": "system", "subtype": "init", "tools": ["WebSearch", "WebFetch", "Bash", "AskUserQuestion"]})
    f, _ = battery([popup_init] + typed + bt[1:], "standard", run_row)
    if any("typed in the reply" in x for x in f):
        print("tripped: C22 by setup questions typed out ('one number per line') where the host has a question tool (the ChatGPT regression)")
    else:
        print("FAIL C22 must trip on a typed setup list where the host has a question tool:", f); ok = False
    f, _ = battery([popup_init] + typed + bt[1:], "standard", run_row, popup=False)
    if any(x.startswith("C22") for x in f):
        print("FAIL C22 must allow a typed list where the host has no question tool:", f); ok = False
    else:
        print("passes: C22 on a typed list where the host has no question tool (the fallback)")
    if any(x.startswith("C22") for x in battery(typed + bt, "standard", run_row)[0]) or not any("typed in the reply" in x for x in battery([popup_init] + typed + bt[1:], "standard", run_row)[0]):
        print("FAIL C22 must read the host's tool list: no AskUserQuestion = fallback allowed, AskUserQuestion listed = a typed list fails"); ok = False
    else:
        print("passes: C22 reads the session's tool list (typed list allowed without a question tool, a failure with one)")
    bt = [popup_init] + bt[1:]
    empty = [msg("text", "One quick question: answer in the popup, or skip and I'll go on without it."),
             '{"type": "assistant", "message": {"content": [{"type": "tool_use", "id": "q1", "name": "AskUserQuestion", "input": {"questions": [{"question": "Who else has a say in custodian choices at Alder Grey?"}]}}]}}',
             '{"type": "user", "message": {"content": [{"type": "tool_result", "tool_use_id": "q1", "content": "The user doesn\'t want to proceed with this tool use."}]}}']
    f, _ = battery(empty + bt, "standard", run_row)
    if any("came back with no answer" in x for x in f):
        print("tripped: C22 by a popup that came back empty and was not asked again in the reply")
    else:
        print("FAIL C22 must trip on an empty popup that is not re-asked:", f); ok = False
    again = empty + [msg("text", "The popup closed with no answer. Who else has a say in custodian choices at Alder Grey? Reply, or reply skip and I'll go on without it."),
                     json.dumps({"type": "user", "message": {"role": "user", "content": "skip"}})]
    f, _ = battery(again + bt, "standard", run_row)
    if any(x.startswith("C22") for x in f):
        print("FAIL C22 must pass an empty popup asked again in the reply, then the user's answer:", f); ok = False
    else:
        print("passes: C22 on an empty popup asked again in the reply (the typed fallback), then the user's answer")
    prof = "Transaction advisory for mid-market sellers"
    for case, req, expect in (("AI meeting prep against a saved transaction-advisory offer", "Satya Nadella, Microsoft -- first introduction; I want a second meeting about AI meeting prep for his executive team.", True),
                              ("the same business in other words", "Jane Doe, Alder Grey -- I want to talk about transaction advisory for her firm's sale.", False),
                              ("a request with no stated purpose", "Jane Doe, Alder Grey Capital", False)):
        got = bool(offer_conflict(prof, req))
        if got != expect:
            print(f"FAIL offer-conflict on {case}: expected {expect}"); ok = False
        else:
            print(f"{'tripped' if expect else 'passes'}: C22 offer conflict on {case}")
    f, _ = battery([json.dumps({"type": "user", "message": {"role": "user", "content": "Satya Nadella, Microsoft -- I want a second meeting about AI meeting prep for his executive team."}})] + bt,
                   "standard", run_row, profile=prof)
    if any("conflicts with the request" in x for x in f):
        print("tripped: C22 by a saved offer that conflicts with the request and no question before the first search")
    else:
        print("FAIL C22 must trip on a saved-offer conflict with no question:", f); ok = False
    # ---- records (C23): the three records are complete and agree
    rec_dir = fx / "records_ok"
    c12_md = c12
    if records_check(rec_dir, "standard", c12_md):
        print("FAIL records_ok must pass C23:", records_check(rec_dir, "standard", c12_md)); ok = False
    else:
        print("passes: C23 on records_ok (12 claims, 12 source-type counts, six dimensions) against control_12.md")
    def broken(edit, name):
        with tempfile.TemporaryDirectory() as td:
            for fn in ("claims.jsonl", "coverage.json", "read.json"):
                (pathlib.Path(td) / fn).write_text((rec_dir / fn).read_text())
            edit(pathlib.Path(td))
            return records_check(td, "standard", c12_md)
    def jedit(fn, mut):
        def go(d):
            j = json.loads((d / fn).read_text()); mut(j); (d / fn).write_text(json.dumps(j))
        return go
    def jedit_lines(cid, mut):   # edit one claim of claims.jsonl, by id
        def go(d):
            rows = [json.loads(x) for x in (d / "claims.jsonl").read_text().splitlines()]
            for r in rows:
                if r["id"] == cid:
                    mut(r)
            (d / "claims.jsonl").write_text("\n".join(json.dumps(r) for r in rows))
        return go
    for case, edit, want in (
            ("a coverage record without per-source-type counts", jedit("coverage.json", lambda j: j.pop("hits_by_family")), "hits_by_family"),
            ("a coverage record that skips one source type", jedit("coverage.json", lambda j: j["hits_by_family"].pop("F12")), "must hold a count for each"),
            ("a coverage count that disagrees with the claims", jedit("coverage.json", lambda j: j["hits_by_family"].update(F3=5)), "claims.jsonl holds"),
            ("a FULL status the claims do not support", jedit("coverage.json", lambda j: j.update(status="LIMITED")), "coverage.status"),
            ("a coverage record without its rounds", jedit("coverage.json", lambda j: j.pop("rounds")), "lacks"),
            ("a behavioral record missing a field", jedit("read.json", lambda j: j[0].pop("observation_ids")), "lacks"),
            ("a behavioral record with five dimensions", jedit("read.json", lambda j: j.pop()), "six dimensions"),
            ("a band whose move is not the rubric's", jedit("read.json", lambda j: j[0].update(meeting_meaning="Be nice.")), "word for word"),
            ("a tier its observations cannot carry", jedit("read.json", lambda j: j[0].update(observation_ids=[3])), "needs 3 observations"),
            ("a claim missing a field", lambda d: (d / "claims.jsonl").write_text("\n".join(json.dumps({k: v for k, v in json.loads(x).items() if k != "grade"} if i == 0 else json.loads(x))
                                                                                           for i, x in enumerate((d / "claims.jsonl").read_text().splitlines()))), "lacks"),
            ("a cited claim with an empty tag", jedit_lines(1, lambda c: c.update(tag="")), "2.1.0 C2"),
            ("a cited claim with no retrieved_at date", jedit_lines(2, lambda c: c.pop("retrieved_at")), "2.1.0 C2"),
            ("a cited claim with an empty confidence", jedit_lines(3, lambda c: c.update(confidence=None)), "2.1.0 C2"),
            ("a ledger row whose page is not in claims.jsonl", lambda d: (d / "claims.jsonl").write_text("\n".join(x for x in (d / "claims.jsonl").read_text().splitlines() if '"id": 5,' not in x)), "does not hold")):
        f = broken(edit, case)
        if any(want in x for x in f):
            print(f"tripped: C23 by {case}")
        else:
            print(f"FAIL C23 must trip on {case} (got {f})"); ok = False
    # ---- assemble (C26): the brief is built from the schema, never written; grading (C25): weak sources never read strong
    import yaml as _y
    prof_ok = _y.safe_load((fx / "profile_ok.yaml").read_text())
    ab, asc, aprobs = assemble(rec_dir, prof_ok)
    afail = aprobs + schema_check(ab, asc) + grading_check(ab) + checks(ab, asc, "all", ["Jane Doe", "Doe", "Alder Grey Capital"], "experienced", "high")
    if afail:
        print("FAIL assemble(records_ok) must build a brief that passes schema, grading and every check:", *afail, sep="\n - "); ok = False
    else:
        print(f"passes: C26 and C25 on the assembled brief (12 facts, {len(re.findall(chr(10) + '## ', ab))} blocks) and every other check")
    with tempfile.TemporaryDirectory() as tg:   # S2-9: a search after round 5 is logged as a 'gap fill' entry: counted in N, never in M
        tg = pathlib.Path(tg)
        for x in rec_dir.iterdir():
            if x.is_file():
                shutil.copy(x, tg / x.name)
        cv = json.loads((tg / "coverage.json").read_text())
        n0, m0 = cv["searches"], len([r for r in cv["rounds"] if r.get("queries")])
        cv["rounds"].append({"round": "gap fill", "queries": ['"Jane Doe" Alder Grey managing partner 2026', '"Alder Grey Capital" investment committee']})
        cv["searches"] = n0 + 2
        (tg / "coverage.json").write_text(json.dumps(cv))
        gb = assemble(tg, prof_ok)[0]
        row = RUN_COUNTS.search(re.sub(r"\s+", " ", gb))
        if records_check(tg, "standard") or not row or (int(row.group(1)), int(row.group(3))) != (n0 + 2, m0):
            print(f"FAIL S2-9: a gap-fill entry must count in N ({n0 + 2}) and not in M ({m0}), and pass the records:", row and row.group(0), records_check(tg, "standard")); ok = False
        else:
            print(f"passes: S2-9 gap fill: the Run row says {row.group(0)} (two gap-fill searches in N, rounds 1-5 in M); records pass")
    mut = {"a block renamed": (lambda b, s: (b.replace("## B3 Who they are", "## B3 About them"), s), "titled"),
           "a block out of order": (lambda b, s: (b.replace("## B7 Who decides", "## B8 Strongest case against", 1), s), "blocks are"),
           "a label its form does not have": (lambda b, s: (b.replace("- **The gate:**", "- **Gatekeeper:**"), s), "which its form does not have"),
           "a table header changed": (lambda b, s: (b.replace("| Observable | What to do with it |", "| Signal | Action |"), s), "table header"),
           "the tier line gone": (lambda b, s: (re.sub(r"\*\*Evidence tier:\*\*[^\n]*", "", b), s), "tier line"),
           "the ledger's label grid reordered": (lambda b, s: (b.replace("| **Still open** |", "| **Open items** |"), s), "label grid"),
           "a subhead of B9 renamed": (lambda b, s: (b.replace("### Meeting two", "### Next meeting"), s), "subheads"),
           "the masthead's meta line rewritten": (lambda b, s: (b.replace("Meeting: ", "Call: ", 1), s), "meta line"),
           "the script's title changed": (lambda b, s: (b, s.replace("# Meeting script", "# Call script", 1)), "script must open"),
           "a script section out of order": (lambda b, s: (b, s.replace("## P1 Open", "## P9 Next step", 1)), "script's sections")}
    for case, (fn, want) in mut.items():
        mb, ms = fn(ab, asc)
        f = schema_check(mb, ms)
        if any(want in x for x in f):
            print(f"tripped: C26 by {case}")
        else:
            print(f"FAIL C26 must trip on {case} (wanted '{want}'; got {f})"); ok = False
    with tempfile.TemporaryDirectory() as td:
        for fn in ("claims.jsonl", "coverage.json", "read.json", "fields.json"):
            (pathlib.Path(td) / fn).write_text((rec_dir / fn).read_text())
        (pathlib.Path(td) / "brief.md").write_text(ab); (pathlib.Path(td) / "script.md").write_text(asc)
        if assembled_matches(td, prof_ok):
            print("FAIL assemble --check must pass the files assemble wrote:", assembled_matches(td, prof_ok)); ok = False
        else:
            print("passes: C26 assemble --check on the files assemble wrote")
        (pathlib.Path(td) / "brief.md").write_text(ab.replace("Raising a second vehicle", "Raising a second fund"))
        if any("differs from what eval.py assemble builds" in x for x in assembled_matches(td, prof_ok)):
            print("tripped: C26 by a hand edit to brief.md after assembly")
        else:
            print("FAIL C26 must trip on a hand edit to brief.md"); ok = False
        fj = json.loads((rec_dir / "fields.json").read_text()); fj["b1"].pop("avoid")
        (pathlib.Path(td) / "fields.json").write_text(json.dumps(fj))
        if any("needs 'avoid'" in x for x in assemble(td, prof_ok)[2]):
            print("tripped: C26 by a field left empty in fields.json (B1 avoid)")
        else:
            print("FAIL assemble must report a missing required field"); ok = False
    gcases = {"a weak domain read Strong": (lambda b: re.sub(r"(\[thefabulous\.co\]\(https://thefabulous\.co/12\)[^|]*\| )[^|]+\|", "\\1Measured · Strong |", b), "weak"),
              "an Inference row read Strong": (lambda b: re.sub(r"(Sets agendas on panels \|[^|]*\| )[^|]+\|", "\\1Inference · Strong |", b), "caps"),
              "a Search row read Solid": (lambda b: re.sub(r"(Fact 6 about Alder Grey \|[^|]*\| )[^|]+\|", "\\1Derived · Solid |", b), "caps"),
              "the strength key left out": (lambda b: re.sub(r"Strength: [^.]*\.", "", b), "key the strengths"),
              "a row with no tag": (lambda b: b.replace("(https://example.org/1) · Direct", "(https://example.org/1)"), "how it was found"),
              "a source printed as its full URL": (lambda b: b.replace("[example.org](https://example.org/1)", "[https://example.org/1](https://example.org/1)"), "never the full URL"),
              "a source printed as a bare URL": (lambda b: b.replace("[example.org](https://example.org/2)", "https://example.org/2"), "bare URL"),
              "a row with no strength": (lambda b: b.replace("Measured · Strong", "Measured", 1), "no source strength")}
    weak_ab = ab.replace("[example.org](https://example.org/12)", "[thefabulous.co](https://thefabulous.co/12)")   # the real regression: a weak domain printed Measured
    for case, (fn, want) in gcases.items():
        f = grading_check(fn(weak_ab if "weak" in want else ab))
        if any(want in x for x in f):
            print(f"tripped: C25 by {case}")
        else:
            print(f"FAIL C25 must trip on {case} (got {f})"); ok = False
    c_weak = dict(id=1, url="https://thefabulous.co/pod/x", tag="Direct", grade="Measured", confidence="C1")
    if effective_conf(c_weak) != "C3" or effective_conf(dict(c_weak, url="https://sec.gov/x")) != "C1" or effective_conf(dict(c_weak, url="https://sec.gov/x", tag="Search")) != "C3" or effective_conf(dict(c_weak, url="https://sec.gov/x", grade="Inference")) != "C4":
        print("FAIL effective_conf: a weak domain, a Search tag and an Inference grade must each cap a C1 claim"); ok = False
    else:
        print("passes: a C1 claim from a weak domain prints Weak (C3), from a Search result Weak, an Inference Inferred; from sec.gov, Measured and Direct, Strong")
    if "F2" in [f["id"] for f in base_families("standard", "company")] or "F6" in [f["id"] for f in base_families("standard", "person", "none")] or 2 in battery_floor("standard", "company")[0]:
        print("FAIL a company target must drop the person-only source types and round 2; scope none must drop F6"); ok = False
    else:
        print("passes: target kind and social scope steer the base pass (company drops F2 F5 F6 F7 and round 2; scope none drops F6)")
    # ---- kept facts (C24): a fit pass cuts wording, never cited facts
    dead = lambda urls: [(u, 404, "dead") for u in urls]   # link checks, offline: the page is gone / it answers
    alive = lambda urls: [(u, 200, "ok") for u in urls]
    cut = re.sub(r"^\| \[12\].*\n", "", c12, flags=re.M).replace(" [12]", "").replace("12 facts cited", "11 facts cited").replace("12 cited", "11 cited")
    shorter = c12.replace("Introduction to the custodian offered", "Custodian introduction offered").replace("Sets agendas on panels", "Sets panel agendas")
    same = c12.replace("https://example.org/4", "https://example.org/3")   # rows 3 and 4 cite one page on one day
    cut4 = re.sub(r"^\| \[4\].*\n", "", same, flags=re.M).replace(" [4]", "")
    for case, draft, final, allow, status, want in (
            ("a cited fact cut to fit the page", c12, cut, (), dead, "are gone"),
            ("the same fact cut, named by its number as a dead link (404)", c12, cut, ("12=dead",), dead, None),
            ("the same fact excused by its page's URL (the Oct 17 bypass)", c12, cut, ("https://example.org/12",), dead, "excuses nothing"),
            ("the same fact excused for fit", c12, cut, ("12=fit",), dead, "excuses nothing"),
            ("the same fact named dead while its page answers (200)", c12, cut, ("12=dead",), alive, "answers"),
            ("the same fact named excluded with no excluded topic", c12, cut, ("12=excluded",), dead, "touches no excluded topic"),
            ("shorter wording, every fact kept", c12, shorter, (), dead, None),
            ("one of three facts from the same page and day cut", same, cut4, (), dead, "are gone"),
            ("that fact named dead while its page is still cited", same, cut4, ("4=dead",), dead, "still cited")):
        f = kept_check(draft, final, allow, status=status)
        if (want is None and f) or (want and not any(want in x for x in f)):
            print(f"FAIL C24 on {case}: expected {'a pass' if want is None else repr(want)}, got {f}"); ok = False
        else:
            print(f"{'passes' if want is None else 'tripped'}: C24 on {case}")
    # the real run (Claude desktop, Oct 17, Andy Sieg at Citi, recovered from its transcript and records): the first draft cited 27 facts, the
    # PDF 18; eval.py kept passed only because every cut was excused with --allow <page>
    ko = fx / "kept_oct17"
    kprof = _y.safe_load((ko / "profile.yaml").read_text())
    d27, s27 = (ko / "brief.draft.md").read_text(), (ko / "script.draft.md").read_text()
    f18, sc18 = (ko / "brief.final.md").read_text(), (ko / "script.final.md").read_text()
    oct17_allow = ["https://www.efinancialcareers.com/news/andy-sieg-citi-wealth", "https://www.citigroup.com/global/about-us/leadership/andy-sieg",
                   "https://www.citigroup.com/global/news/press-release/2026/citi-wealth-unveils-citi-sky-ai-powered-member-google-cloud-deepmind-technologies",
                   "https://www.citigroup.com/rcs/citigpa/storage/public/investor-day/citi-ID26-wealth-presentation-transcript.pdf",
                   "https://www.bankingdive.com/news/citi-andy-sieg-strategy-wealth-business/718852/",
                   "https://citigroup.com/rcs/citigpa/storage/public/b-of-a-2025-conference-transcript.pdf", "your message (intake)"]
    gone = {6, 10, 29, 42, 43, 47, 53, 56, 61, 81}   # the ten claims the fit passes cut (claim 63 was added)
    with tempfile.TemporaryDirectory() as tk:
        tk = pathlib.Path(tk)
        for x in ("claims.jsonl", "coverage.json", "read.json", "fields.json"):
            shutil.copy(ko / x, tk / x)
        print_line = record_draft(tk, d27, s27, json.loads((ko / "draft.facts.json").read_text()), "deep")
        bk, sk, pk, ok18 = assemble(tk, kprof, "deep", want_order=True)
        (tk / "brief.md").write_text(bk); (tk / "script.md").write_text(sk)
        cases = [("the Oct 17 fit passes (27 cited facts to 18)", (), dead, ["10 of the draft's 27"] + [f"(claim {c})" for c in sorted(gone)]),
                 ("the same with the run's own --allow pages", oct17_allow, dead, ["excuses nothing", "10 of the draft's 27"]),
                 ("a cut fact named dead while its page answers (efinancialcareers, 200 on Oct 17)", ("9=dead",), alive, ["answers", "10 of the draft's 27"]),
                 ("a cut fact named dead while its page is still cited (the Investor Day transcript)", ("5=dead",), dead, ["still cited", "10 of the draft's 27"])]
        draft_ids = json.loads((ko / "draft.facts.json").read_text())
        if draft_ids.index(10) + 1 != 9 or draft_ids.index(42) + 1 != 5:
            print("FAIL kept_oct17: the draft's ledger numbers moved (claim 10 is [9], claim 42 [5])"); ok = False
        for case, allow, status, wants in cases:
            f, summ = kept_folder(tk, allow, kprof, status)
            if all(any(w in x for x in f) for w in wants):
                print(f"tripped: C24 by {case} ({summ})")
            else:
                print(f"FAIL C24 must trip on {case} (want {wants}):", f); ok = False
        (tk / "brief.draft.md").write_text(bk)   # a 'draft' copied after the cuts
        f, _ = kept_folder(tk, (), kprof, dead)
        if any("not the draft eval.py assemble recorded" in x for x in f):
            print("tripped: C24 by a draft copy taken after the cuts (its sha256 is not the one assemble recorded)")
        else:
            print("FAIL C24 must refuse a draft copied after the cuts:", f); ok = False
        (tk / "draft.lock.json").unlink()
        f, _ = kept_folder(tk, (), kprof, dead)
        if not any("no draft.lock.json" in x for x in f):
            print("FAIL C24 must fail a folder with no recorded draft:", f); ok = False
        else:
            print("tripped: C24 by a folder with no recorded draft")
    f = kept_check(d27, f18, oct17_allow, s27, sc18, status=dead)
    if not (any("excuses nothing" in x for x in f) and any("are gone" in x for x in f)):
        print("FAIL C24 (two files) must trip on the Oct 17 draft and final with its --allow pages:", f); ok = False
    else:
        print("tripped: C24 by the Oct 17 draft and PDF brief as two files, with the run's --allow pages")
    f = kept_check(d27, (ko / "brief.kept.md").read_text(), (), s27, s27, status=dead)
    if f:
        print("FAIL C24 must pass the Oct 17 draft's 27 facts kept with shorter wording:", f); ok = False
    else:
        print(f"passes: C24 on the Oct 17 draft's {count_facts(d27)} cited facts all kept, wording cut in the S4-4 order (brief.kept.md)")
    with tempfile.TemporaryDirectory() as tk:   # the ledger sizes the draft: 27 facts do not fit, so the first build refuses them
        tk = pathlib.Path(tk)
        for x in ("claims.jsonl", "coverage.json", "read.json"):
            shutil.copy(ko / x, tk / x)
        fj = json.loads((ko / "fields.json").read_text())
        (tk / "fields.json").write_text(json.dumps(fj))
        b18, s18x, p18, o18 = assemble(tk, kprof, "deep", want_order=True)
        record_draft(tk, b18, s18x, o18, "deep")
        fj["b9"]["frame"] = "Citi advisors rebalance across platforms [c50]; not a pitch."   # wording only, every fact kept
        fj["b9"]["capture"] = "who approves vendors; Advyzon's gaps."
        (tk / "fields.json").write_text(json.dumps(fj))
        bk, sk, pk = assemble(tk, kprof, "deep")
        (tk / "brief.md").write_text(bk); (tk / "script.md").write_text(sk)
        f, summ = kept_folder(tk, (), kprof, dead)
        if f or p18 or pk:
            print("FAIL C24 must pass the Oct 17 final as a draft, reworded with every fact kept:", f, p18, pk); ok = False
        else:
            print(f"passes: C24 on a run folder whose fit pass cut only wording ({summ})")
    with tempfile.TemporaryDirectory() as tk:   # the page sizes the draft: the first build is rendered once and recorded only if it fits
        tk = pathlib.Path(tk)
        for x in ("claims.jsonl", "coverage.json", "read.json"):
            shutil.copy(ko / x, tk / x)
        b27f = json.loads((ko / "fields.json").read_text())
        nine = ["Citi Sky unveiled (Apr 22) [c29]", "net flows his test [c56]", "four-layer plan [c42]", "Advyzon this fall [c43]", "credits Moore and Glenfield [c47]",
                "best-in-class [c53]", "$38B net new [c61]", "US retail bank [c10]", "Merrill since 1992 [c6]"]
        b27f["b3"]["changed"] = b27f["b3"]["changed"] + nine   # the run's 27 facts, the nine extra as short cited mentions
        (tk / "fields.json").write_text(json.dumps(b27f))
        if trial_fit(*assemble(tk, kprof, "deep")[:2], b27f) is None:
            print(("FAIL" if require_pdf else "skipped:") + " C26 first-build fit: no browser engine to render the first build"); ok = ok and not require_pdf
        else:
            out, code = build(tk, kprof, "deep")
            wanted = json.loads((tk / "draft.wanted.json").read_text()) if (tk / "draft.wanted.json").exists() else []
            if code == 1 and not (tk / "draft.lock.json").exists() and not (tk / "brief.md").exists() and len(wanted) == 27:
                print("tripped: C26 assemble by a first build citing the run's 27 facts, more than its page holds (rendered once: nothing written, no draft recorded, the 27 kept in draft.wanted.json)")
            else:
                print("FAIL a first build that does not fit must write nothing and record no draft:", out, wanted); ok = False
            (tk / "fields.json").write_text((ko / "fields.json").read_text())   # the strongest 18, as the run printed them
            out, code = build(tk, kprof, "deep")
            f, summ = kept_folder(tk, (), kprof, dead)
            if code or f or "could not hold 9 more" not in summ:
                print("FAIL the 18-fact build must be recorded as the draft and name the 9 the page could not hold:", out, f, summ); ok = False
            else:
                print(f"passes: C24 on the 18 facts the page holds, recorded as the draft; kept names the 9 left out for the user ({summ[:90]}...)")
    late = c12.replace("| Sep 20, 2026 · standard", "| Oct 15, 2026 · standard")
    for case, md, trips in (("a Run row from before Oct 15 without counts (frozen targets)", c12, False),
                            ("a Run row from Oct 15 without counts", late, True),
                            ("a Run row from Oct 15 below the standard floor", late.replace("· FULL |", "· FULL · 9 searches in 3 rounds |"), True),
                            ("a Run row from Oct 15 with 20 searches in 5 rounds", late.replace("· FULL |", "· FULL · 20 searches in 5 rounds |"), False),
                            ("a Run row from Oct 16 without the base count", late.replace("Oct 15", "Oct 16").replace("· FULL |", "· FULL · 20 searches in 5 rounds |"), True),
                            ("a Run row from Oct 16 below the base floor", late.replace("Oct 15", "Oct 16").replace("· FULL |", "· FULL · 25 searches (5 base) in 5 rounds |"), True),
                            ("a Run row from Oct 16 with 31 searches (11 base) in 5 rounds", late.replace("Oct 15", "Oct 16").replace("· FULL |", "· FULL · 31 searches (11 base) in 5 rounds |"), False)):
        got = [x for x in checks(md, which="battery") if x.startswith("C21 ")]
        if bool(got) != trips:
            print(f"FAIL C21 on {case}: expected {'a failure' if trips else 'a pass'}, got {got}"); ok = False
        else:
            print(f"{'tripped' if trips else 'passes'}: C21 on {case}")
    n_md = len(link_targets(fx / "control_12.md"))   # S2-8: links are checked from brief.md before render
    n_row = len([m for m in SRC_ROW.finditer((fx / "control_12.md").read_text()) if "http" in m.group(3)])
    if n_md != n_row or not n_md or link_targets(fx / "split_table_pages.txt"):
        print(f"FAIL links must read brief.md's {n_row} linked ledger rows (got {n_md})"); ok = False
    else:
        print(f"passes: links reads brief.md's {n_md} linked ledger rows, as before render")
    pat = re.compile(R["plain_words"]["internal"])   # consumer-facing copy carries no internal notes (render_skill.py, adapters.py)
    leaks = ["not on the page (Ben, Oct 13)", "the Ben/Danny call", "the R10b run", "Optional (AID-62)", "Notes by Gemini",
             "from the meeting notes", "print side by side (Oct 14: a thin run)", "Daniel decides"]
    clean = ["Gemini CLI (Code Assist plans)", "send the one-page example by Oct 17.", "the tightest rung", "B10, C21 and S2-9",
             "a benchmark, not a Benefit", "Prepared Oct 15, 2026", "an R&D budget"]
    shipped = [f for f in ["skills/pre-call-prep/SKILL.md", "SKILL.md", "commands/pcp.md", "INVENTORY.md", "README.md"] if (HERE / f).exists()]
    shipped += [str(f.relative_to(HERE)) for d in ("skills/pre-call-prep/references", "references") if (HERE / d).is_dir() for f in (HERE / d).glob("*.md")]
    missed, false = [t for t in leaks if not pat.search(t)], [t for t in clean if pat.search(t)]
    dirty = {f: sorted(set(pat.findall((HERE / f).read_text()))) for f in shipped if pat.search((HERE / f).read_text())}
    if missed or false or dirty:
        print("FAIL internal notes in consumer copy: missed", missed, "| false hits", false, "| shipped files", dirty); ok = False
    else:
        print(f"passes: consumer copy free of internal notes ({len(shipped)} shipped files); tripped by {len(leaks)} leaks, none of {len(clean)} clean lines")
    # ---- the audit's loosenings against 2.1.0 (R2-R5), each closed: each case trips, its control passes
    generic = "The whole industry is changing quickly and every leader feels the pressure."
    for blk_id, what in (("B2", "the questions"), ("B9", "the meeting angle")):   # 2.1.0's B5 and B7, outside 3.1.1's B1-B7 sweep
        bad = [x for x in checks(f"## {blk_id} Title\n{generic}\n", "", "swap", FIXTURE_NOUNS) if x.startswith("C1") and blk_id in x]
        good = checks(f"## {blk_id} Title\n{generic[:-1]} [1].\n", "", "swap", FIXTURE_NOUNS)
        if bad and not good:
            print(f"tripped: C1 by a generic, uncited sentence in {blk_id} ({what}); the same sentence cited passes")
        else:
            print(f"FAIL C1 must read {blk_id}: {bad or 'no trip'} / control {good}"); ok = False
    hook2 = "Jane Doe runs Alder Grey [1]. She says patience wins [2]."
    close_ok = "thirty minutes with Jane Doe [1] · **Fallback:** fifteen minutes [2].\n- **Follow-up:** the one-page example within a day."
    close_long = " ".join(["thirty minutes with Jane Doe and her operations partner at Alder Grey"] * 5) + close_ok[len("thirty minutes with Jane Doe"):]
    tier_hi = "## B6 Behavioral profile\n**Evidence tier:** high: it sets how far page 3 goes\n"
    p6 = lambda n: "## P6 Influence\n" + "".join(f"- **{k}:** Jane Doe's move at Alder Grey [{i}].\n" for i, k in enumerate(["Authority", "Reciprocity", "Liking", "Scarcity"][:n], 1))
    for case, which, want, bad_md, good_md in (
            ("a Hook of three sentences (2.1.0's opening: two)", "budgets", "P1's Hook",
             f"## P1 Open\n- **Hook:** *{hook2} She also hires slowly [3].*\n", f"## P1 Open\n- **Hook:** *{hook2}*\n"),
            ("a Hook of 2 sentences over 2.1.0's 40 words", "budgets", "P1's Hook",
             f"## P1 Open\n- **Hook:** *Jane Doe runs {' and '.join(['Alder Grey Capital'] * 12)} [1]. She says patience wins [2].*\n", f"## P1 Open\n- **Hook:** *{hook2}*\n"),
            ("an ask, fallback and follow-up over 2.1.0's 50 words", "budgets", "P4's ask",
             f"## P4 Close\n- **The ask:** {close_long}\n", f"## P4 Close\n- **The ask:** {close_ok}\n"),
            ("four influence moves (2.1.0: 3 moves from the behavioral read)", "conditional", "at most 3", tier_hi + p6(4), tier_hi + p6(3))):
        bad = [x for x in checks("Prepared Oct 18, 2026\n" + bad_md, "", which, FIXTURE_NOUNS, None, "high") if want in x]
        good = [x for x in checks("Prepared Oct 18, 2026\n" + good_md, "", which, FIXTURE_NOUNS, None, "high") if want in x]
        if bad and not good:
            print(f"tripped: {'C13' if which == 'conditional' else 'C6'} by {case}; the control within 2.1.0's cap passes")
        else:
            print(f"FAIL must trip on {case}: {bad or 'no trip'} / control {good}"); ok = False
    caps = {s["id"]: s["words"] for s in R["brief"]["sections"]} | {b["id"]: b["words"] for b in R["script"]["blocks"]}
    held = []
    for blk_id in ("B3", "B9", "P3", "P6", "P8"):   # the per-block caps R3 put back, read from pcp.yaml
        over = f"Prepared Oct 18, 2026\n## {blk_id} Title\n" + "word " * (int(caps[blk_id] * 1.15) + 1) + "\n"
        at = f"Prepared Oct 18, 2026\n## {blk_id} Title\n" + "word " * caps[blk_id] + "\n"
        if any(f"C6 budgets: {blk_id} " in x for x in checks(over, "", "budgets")) and not checks(at, "", "budgets"):
            held.append(f"{blk_id} {caps[blk_id]}")
        else:
            print(f"FAIL C6 must hold {blk_id} to {caps[blk_id]} words (+15%)"); ok = False
    if len(held) == 5:
        print(f"tripped: C6 by {', '.join(held)} words one word over their cap (+15%); each at its cap passes")
    s21 = "Public sources only. Nothing behind a login, no paid data the user has not supplied, no scraping."
    s21_row = next(r for st in R["stages"] for r in st["rows"] if r["id"] == "S2-1")["text"]
    skill_txt = (HERE / SKILL_DIR / "SKILL.md").read_text() if (HERE / SKILL_DIR / "SKILL.md").exists() else s21
    if not (s21_row.startswith(s21) and s21 in skill_txt and "tagged Yours" in s21_row):
        print("FAIL S2-1 must carry 2.1.0's public-sources sentence word for word, with the user's own material tagged Yours"); ok = False
    else:
        print(f"passes: S2-1 opens with 2.1.0's '{s21}' (pcp.yaml and SKILL.md); the user's own material stays tagged Yours")
    pdf = pdf_self_test(fx)
    if pdf is None:
        print("SKIP the PDF checks: no Chromium, or no pdftotext / pypdf, on this computer"
              + (" -- FAIL (--require-pdf)" if require_pdf else ""))
        ok = ok and not require_pdf
    else:
        ok = ok and pdf
    return ok


JARGON = ["SOCINT", "HUMINT", "human intelligence", "intelligence cycle", "collection plan", "target package", "asset",
          "source handling", "exploitation", "debrief"]   # jargon.md: one always-banned word per block
FINANCE = ["Runs J.P. Morgan Asset & Wealth Management [3].", "Asset and wealth management grew 12% [4].", "Net asset value rose 6% [5].",
           "Citi's asset quality held [2].", "BNY's asset servicing arm [6].", "Closed the asset sale on Mar 3, 2026 [2]."]   # C11 must pass


def pdf_self_test(fx):
    """Render control_12.md and jargon.md the way SKILL.md says, then read them back: the control passes `pdf`,
    the jargon PDF's printed text trips C11 on every word, and control_12.md rendered with --brief-pages 3 (4 pages,
    the ledger on page 3) trips C10. None if this computer cannot render or read a PDF."""
    import importlib.util
    sys.dont_write_bytecode = True   # importing the renderer must not leave __pycache__ in the plug-in
    spec = importlib.util.spec_from_file_location("talyx_pdf", HERE / "format/talyx_pdf.py")
    tp = importlib.util.module_from_spec(spec); spec.loader.exec_module(tp)
    try:
        import playwright  # noqa: F401
    except ImportError:
        if not tp.system_chrome():
            return None
    if shutil.which("pdftotext") is None and importlib.util.find_spec("pypdf") is None:
        return None
    ok, pb, n = True, R["page_budget"], R["names"]
    heads = tp.b9_html('<div class="sub">A. This meeting</div><div class="sub">Meeting two</div><div class="sub">After the meeting</div>')
    if re.findall(r'class="sub">([A-H])\. ', heads) == ["A", "B", "C"]:
        print("passes: B9 subheads lettered A, B, C by position when the brief letters only the first")
    else:
        print("FAIL B9 subheads must be lettered A, B, C by position:", heads); ok = False
    # ---- D3 density proof: 18 cited facts, 10 pt and up, assembled from fields.json, rendered headless to the 3 pages the schema allows
    dd = fx / "density_standard"
    with tempfile.TemporaryDirectory() as tmp2:
        import yaml as _y
        for fn in ("claims.jsonl", "coverage.json", "read.json", "fields.json"):
            pathlib.Path(tmp2, fn).write_text((dd / fn).read_text())
        brief_d, script_d, probs_d = assemble(tmp2, _y.safe_load((dd / "profile.yaml").read_text()))
        pathlib.Path(tmp2, "brief.md").write_text(brief_d); pathlib.Path(tmp2, "script.md").write_text(script_d)
        out_d = pathlib.Path(tmp2, "out.pdf")
        cmd = [sys.executable, str(HERE / "format/talyx_pdf.py"), "--style", "brief", "--brief", str(pathlib.Path(tmp2, "brief.md")), "--script", str(pathlib.Path(tmp2, "script.md")),
               "--columns", pb["columns"], "--classification", n["classification"], "--footer", f"{n['deliverable']} · Satya Nadella, Microsoft",
               "--brief-pages", str(pb["brief_pages"]), "--max-pages", str(pb["total_pages"]), "--out", str(out_d)]
        run_d = subprocess.run(cmd, capture_output=True, text=True)
        try:
            res = json.loads(run_d.stdout)
        except ValueError:
            res = {"ok": False, "reason": run_d.stdout[:120] + run_d.stderr[:120]}
        rep_d = duf(brief_d, script_d, pb["total_pages"])
        fails_d = probs_d + ([] if res.get("ok") else [f"render failed: {res.get('reason')}"]) + (pdf_check(out_d, brief_d) or [] if res.get("ok") else []) \
            + (render_check(out_d) + text_colors(out_d) if res.get("ok") else []) + checks(brief_d, script_d, "all", ["Satya Nadella", "Nadella", "Microsoft", "Copilot"], "experienced", "high") \
            + records_check(tmp2, "standard", brief_d)
        floor = min(v["duf_pp"] for v in json.loads((HERE / R["eval"]["ratchet_file"]).read_text())["floors"].values())
        if fails_d or rep_d["bound"] != 18 or rep_d["duf_pp"] < floor:
            print(f"FAIL density proof: 18 facts at {min(pb['text_sizes_pt'][k] for k in pb['text_sizes_pt'] if k not in pb['text_floor_exempt'])} pt must fit {pb['total_pages']} pages and pass every check "
                  f"(bound {rep_d['bound']}, duf_pp {rep_d['duf_pp']} vs floor {floor}):", *fails_d, sep="\n - "); ok = False
        else:
            print(f"passes: D3 density: {rep_d['bound']} cited facts, duf_pp {rep_d['duf_pp']} (floor {floor}), every reader-facing size at {pb['text_floor_pt']} pt or more, {res['pages']} pages at the {res['rung']} rung, "
                  "assembled from fields.json, headless")
    with tempfile.TemporaryDirectory() as tmp:
        for name, layout in (("control_12.md", True), ("jargon.md", True), ("control_12.md", False)):
            md = (fx / name).read_text()
            cut = [m.start() for m in re.finditer(r"^# ", md, re.M)][1]
            b, s, out = pathlib.Path(tmp, "brief.md"), pathlib.Path(tmp, "script.md"), pathlib.Path(tmp, name[:-3] + ".pdf")
            b.write_text(md[:cut]); s.write_text(md[cut:])
            pages = (["--brief-pages", str(pb["brief_pages"]), "--max-pages", str(pb["total_pages"])] if layout   # as SKILL.md says
                     else ["--brief-pages", str(pb["brief_pages"] + 1), "--max-pages", str(pb["total_pages"] + 1)])   # the brief over 3 pages
            r = subprocess.run([sys.executable, str(HERE / "format/talyx_pdf.py"), "--style", "brief", "--brief", str(b), "--script", str(s),
                                "--columns", pb["columns"], "--classification", n["classification"],
                                "--footer", f"{n['deliverable']} · Jane Doe, Alder Grey Capital · Prepared for you (internal)",
                                *pages, "--out", str(out)],
                               capture_output=True, text=True, timeout=300)
            if r.returncode != 0:
                print(f"FAIL render {name}: exit {r.returncode} {r.stdout.strip()} {r.stderr.strip()[-300:]}"); ok = False; continue
            f = pdf_check(out, md[:cut])
            if f is None:
                return None
            if not layout:
                if any(x.startswith("C10 ") for x in f):
                    print("tripped: C10 by control_12.pdf rendered with --brief-pages 3 (4 pages, the ledger on page 3)")
                else:
                    print("FAIL control_12.pdf rendered with --brief-pages 3 must trip C10 (got", f, ")"); ok = False
            elif name == "control_12.md":
                print(f"pdf control_12: {len(f)} failures (C10, C11, C19, C20)", *f, sep="\n - ")
                ok = ok and not f
                stacked = pathlib.Path(tmp, "stacked.pdf")   # C19 must fail a render whose schema pairs are stacked
                subprocess.run([sys.executable, str(HERE / "format/talyx_pdf.py"), "--style", "brief", "--brief", str(b), "--script", str(s),
                                "--columns", "B3+B4|B5+B6,B7+B8|B9," + pb["columns"].split(",", 3)[3], "--classification", n["classification"],
                                "--footer", "Intelligence Brief · Jane Doe, Alder Grey Capital · Prepared for you (internal)",
                                "--brief-pages", str(pb["brief_pages"]), "--max-pages", str(pb["total_pages"]), "--out", str(stacked)],
                               capture_output=True, text=True, timeout=300)
                if stacked.exists() and len([x for x in side_by_side(stacked) if "side by side" in x]) == 3:
                    print("tripped: C19 by control_12.pdf rendered with B3|B4, B5|B6 and B7|B8 stacked (three pairs)")
                else:
                    print("FAIL C19 must trip on all three stacked pairs (got", side_by_side(stacked) if stacked.exists() else "no render", ")"); ok = False
                clipped = pathlib.Path(tmp, "clipped.pdf")   # C19 must fail a logo whose top a page margin cuts off
                logo = "data:image/png;base64," + (HERE / "format/assets/talyx-logo-navy-base64.txt").read_text().strip()
                tp.render_html("<!doctype html><style>@page { size: Letter; margin: 0.42in 0 0.62in 0; } body { margin: 0; }"
                               ".stamp { display: flex; justify-content: flex-end; padding: 0 0.5in; margin-top: -0.12in; }</style>"
                               f'<div class="stamp"><img src="{logo}" style="width:90px"/></div>' + "<p>Text.</p>" * 60, clipped)
                if any("logo cut off" in x for x in render_check(clipped)):
                    print("tripped: C19 by a logo whose top the page margin cuts off")
                else:
                    print("FAIL C19 must trip on a clipped logo (got", render_check(clipped), ")"); ok = False
                grey = pathlib.Path(tmp, "grey.pdf")   # C20 must fail grey text (the Oct 14 footer, #8B95A1) and pass the three
                tp.render_html('<!doctype html><body style="color:#0F2744"><p>Midnight.</p><p style="color:#000">Black.</p>'
                               '<p style="background:#0F2744;color:#fff">White on Midnight.</p>'
                               '<p style="color:#8B95A1">page 1 of 3</p><p style="color:#5F6B78">MEASURED</p></body>', grey)
                if len(text_colors(grey)) == 2:
                    print("tripped: C20 by grey text (two greys); Midnight, black and white pass")
                elif shutil.which("pdftohtml"):
                    print("FAIL C20 must trip on exactly the two greys (got", text_colors(grey), ")"); ok = False
                else:
                    print("SKIP C20: no pdftohtml (poppler) on this computer")
                short = pathlib.Path(tmp, "short.pdf")   # C19 must be able to fail on a page that ends in a blank band
                tp.render_html("<!doctype html><style>@page { size: Letter; margin: 0.42in 0.55in 0.62in; }</style>"
                               "<p>One line, then nothing to the foot of the page.</p>", short)
                if any("blank band" in x for x in render_check(short)):
                    print("tripped: C19 by a page that ends in a blank band")
                else:
                    print("FAIL C19 must trip on a page that ends in a blank band (got", render_check(short), ")"); ok = False
                if shutil.which("gs"):   # C19 must be able to fail: shift the page so the logo runs off the top-right
                    sh = pathlib.Path(tmp, "shifted.pdf")
                    subprocess.run(["gs", "-q", "-o", str(sh), "-sDEVICE=pdfwrite", "-c", "<</PageOffset [60 40]>> setpagedevice",
                                    "-f", str(out)], capture_output=True, timeout=120)
                    rf = render_check(sh) if sh.exists() else []
                    if any("logo" in x for x in rf):
                        print("tripped: C19 by control_12.pdf shifted off the page (logo cut off)")
                    else:
                        print("FAIL C19: a shifted PDF must trip the logo check (got", rf, ")"); ok = False
            else:
                got = {re.match(r"C11 plain: '(.+?)'", x).group(1).lower() for x in f if x.startswith("C11 ")}
                if got != {w.lower() for w in JARGON}:
                    print(f"FAIL jargon.pdf: C11 on the printed text must list exactly {JARGON} (got {sorted(got)})"); ok = False
                else:
                    print(f"tripped: C11 by jargon.pdf (the printed text), each of {len(JARGON)} words")
    return ok


# fixture -> passes every check (with these arguments)
FIXTURE_NOUNS = ["Jane Doe", "Doe", "Alder Grey Capital"]   # the target the fixtures are about; the command line passes them (--target-nouns)
MUST_PASS = [
    ("control_12.md", {"target_nouns": FIXTURE_NOUNS}),
    ("control_12.md", {"experience": "experienced", "target_nouns": FIXTURE_NOUNS}),
    ("control_12.md", {"experience": "top", "target_nouns": FIXTURE_NOUNS}),
    ("exp_new.md", {"experience": "new", "target_nouns": FIXTURE_NOUNS}),
    ("linkedin_declined.md", {"target_nouns": FIXTURE_NOUNS}),
    ("linkedin_search.md", {"target_nouns": FIXTURE_NOUNS}),
]


# fixture -> the checks it must trip; self-test fails if any is not tripped (each check is proven able to fail)
MUST_TRIP = [
    ("control_broken.md", {}, ["C7", "C9", "C11", "C12", "C13"]),
    ("layout_broken.md", {}, ["C14"]),
    ("gaps_table.md", {}, ["C12"]),
    ("gaps_statement.md", {}, ["C12"]),
    ("exp_experienced_with_why.md", {"experience": "experienced"}, ["C15"]),
    ("control_12.md", {"experience": "new"}, ["C15"]),
    ("exp_top_long.md", {"experience": "top"}, ["C15"]),
    ("linkedin_missing.md", {}, ["C16"]),
    ("linkedin_declined_with_row.md", {}, ["C16"]),
    ("linkedin_browser.md", {}, ["C16"]),   # AID-63 (Oct 15): no browser session reads LinkedIn; the status is retired
    ("recent_wins_unsourced.md", {}, ["C13"]),
    ("cites_broken.md", {}, ["C17", "C18"]),
    ("control_12.md", {"authority": "medium"}, ["C13"]),
    ("b9_merged.md", {}, ["C14"]),
    ("dates_read_day.md", {}, ["C18"]),
]



# ---------------------------------------------------------------- cites (C17, C18) -----------------------------
STOP = set("""the and for with that this from their they them have has had was were are been being into over about
than then when what which who whom whose where while will would could should may might must can not but also its
his her she him our your you per via just only more most very each every some such other first second third last
said says asked does did done make made take took""".split())
LEDGER_ROW = re.compile(r"^\|\s*\[(\d+)\]\s*\|([^|]*)\|([^|]*)\|([^|]*)\|", re.M)


def _stems(t):
    t = CITE.sub(" ", t.lower().replace("*", " "))
    return {w[:5] for w in re.findall(r"[a-z0-9$%.]+", t) if (len(w) >= 4 or any(c.isdigit() for c in w))
            and w.strip(".") not in STOP} - {""}


def ledger(md):
    rows = {}
    for m in LEDGER_ROW.finditer(md):
        url = re.search(r"\((https?://[^)\s]+)\)", m.group(3))
        rows[int(m.group(1))] = {"claim": m.group(2).strip(), "source": m.group(3).strip(), "url": url.group(1) if url else "",
                                 "tag": _tag(m.group(3)), "grade": m.group(4).strip(), "conf": ""}
    return rows


def _domain(url):
    d = re.sub(r"^https?://", "", url).split("/")[0].lower()
    return d[4:] if d.startswith("www.") else d


def source_quality(rows, claims=None):
    """C18: excluded domains never cited; weak domains never C1/C2. Confidence is in the run file (claims.jsonl),
    not the printed ledger, so the weak-domain test runs only when claims.jsonl is given."""
    q, fails = R.get("source_quality", {}), []
    for c in claims or []:
        for r in rows.values():
            if r["url"] and r["url"] == c.get("url"):
                r["conf"] = str(c.get("confidence", ""))
    for n, r in rows.items():
        if not r["url"]:
            continue
        d = _domain(r["url"])
        if any(d == x or d.endswith("." + x) for x in q.get("exclude", [])):
            fails.append(f"C18 source quality: [{n}] {d} is on the exclude list")
        elif any(d == x or d.endswith("." + x) for x in q.get("weak", [])) and re.search(r"C1|C2|primary|reputable", r["conf"], re.I):
            fails.append(f"C18 source quality: [{n}] {d} is a weak domain; confidence must be C3 or lower, not '{r['conf']}'")
    return fails


CITE_TESTED = {"Take", "Evidence", "Role", "Path", "The organization", "What changed", "Recent wins", "Decision maker",
               "The gate", "Relationship holder", "Against", "Reverses if", "Stop if", "Capture"}


def cite_relevance(md, fetch=False):
    """C17: each cited sentence shares content with the ledger claim it cites (>= 2 stems, or 1 when the claim
    has <= 3). With fetch, a sentence that fails the ledger test passes if >= 3 of its stems appear on the page."""
    rows, fails, pages = ledger(md), [], {}
    secs = _sections(md)
    for k in [k for k in secs if re.match(r"B[1-9]$|P[1-9]$", k)]:
        prev = set()   # per block: a row's first use is tested; a later "Reverses if: it holds [11]" restates it
        for s in _sentences(secs[k]):
            for part in re.split(r"(?<=\])[;,.]?\s+(?=\*\*|[A-Z])", s):
                ns = [int(x) for x in CITE.findall(part)]
                if not ns:
                    continue
                if set(ns) <= prev:   # "Reverses if: it holds [11]" after a claim on [11]: same fact, already tested
                    continue
                prev |= set(ns)
                lab = re.match(r"[-*\s]*\*\*([^*:]+):?\*\*", part)
                lab = lab.group(1).strip() if lab else ""
                # moves (what to do) cite the fact behind them; only statements of fact and hypotheticals are tested
                if k.startswith("P") or k == "B2" or (lab and lab not in CITE_TESTED and k != "B4") or (not lab and k not in ("B1", "B4")):
                    continue
                ss = _stems(part)
                ok, missing = False, []
                for n in ns:
                    r = rows.get(n)
                    if not r:
                        missing.append(n); continue
                    cs = _stems(r["claim"])
                    flat = lambda t: re.sub(r"[^a-z0-9$%]+", " ", t.lower().replace("\u2019", "'").replace("'", "")).strip()
                    if len(ss & cs) >= (1 if len(cs) <= 3 else 2) or (flat(r["claim"]) and f" {flat(r['claim'])} " in f" {flat(part)} "):
                        ok = True   # or the sentence quotes the claim word for word ("can't let it just rip": no stems)
                    elif fetch and r["url"]:
                        if r["url"] not in pages:
                            pages[r["url"]] = _fetch_text(r["url"])
                        if pages[r["url"]] and len({w for w in ss if w in pages[r["url"]]}) >= 3:
                            ok = True
                if missing:
                    fails.append(f"C17 cites: {k}: [{','.join(map(str, missing))}] not in the ledger: '{part[:60]}...'")
                elif not ok:
                    fails.append(f"C17 cites: {k}: cited source does not support the sentence: '{part[:70]}...'")
    return fails


UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130 Safari/537.36"


def _get(url, timeout=15):
    import urllib.request, urllib.error
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "text/html,*/*"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.read(400000).decode("utf-8", "ignore")
    except urllib.error.HTTPError as e:
        return e.code, ""
    except Exception as e:  # DNS, TLS, timeout
        return 0, str(e)[:80]


def _fetch_text(url):
    code, body = _get(url)
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", body)).lower() if 200 <= code < 400 else ""


BLOCKED = {401, 403, 405, 406, 429, 451, 999}


def link_status(urls):
    """ok / blocked (the site refuses bots: 401/403/429/999 -- not evidence the page is gone) / dead (404/410/5xx/DNS)."""
    out = []
    for u in urls:
        code, _ = _get(u)
        kind = "ok" if 200 <= code < 400 else "blocked" if code in BLOCKED else "dead"
        out.append((u, code, kind))
    return out



# ---------------------------------------------------------------- render (C19) --------------------------------
def _pgm(path):
    data = open(path, "rb").read()
    parts, i = [], 0
    while len(parts) < 4:   # P5 w h maxval, whitespace separated
        while data[i:i + 1].isspace():
            i += 1
        j = i
        while not data[j:j + 1].isspace():
            j += 1
        parts.append(data[i:j]); i = j
    w, h = int(parts[1]), int(parts[2])
    return w, h, data[i + 1:]


LOGO_ASPECT = 0.806   # the ink of format/assets/talyx-logo-navy-base64.txt: 697 x 562 px, height / width


def side_by_side(pdf):
    """C19: each side-by-side pair of the schema (page_budget.columns: B3|B4, B5|B6, B7|B8) prints its two titles
    on one line, one per column (the R9 run, Oct 14, stacked them to fit two pages instead of cutting words)."""
    if shutil.which("pdftotext") is None:
        return []
    x = subprocess.run(["pdftotext", "-bbox-layout", str(pdf), "-"], capture_output=True, text=True).stdout
    flat = lambda t: re.sub(r"\s+", "", t).upper()
    lines, page = {}, 0
    for blk in re.split(r"(?=<page |<line )", x):
        if blk.startswith("<page "):
            page += 1; continue
        m = re.match(r'<line xMin="([\d.]+)" yMin="([\d.]+)"', blk)
        if m:
            lines.setdefault(flat(" ".join(re.findall(r">([^<]+)</word>", blk))), (page, float(m.group(1)), float(m.group(2))))
    title = {s["id"]: flat(s["title"].format(**R["names"])) for s in R["brief"]["sections"]}
    fails = []
    for group in R["page_budget"]["columns"].split(","):
        cols = [c.split("+")[0] for c in group.split("|")]
        if len(cols) != 2 or not all(c in title for c in cols):
            continue   # the script's columns (page 3) flow; only the brief's pairs are fixed
        first = lambda ttl: lines.get(ttl) or next((v for k, v in lines.items() if len(k) >= 10 and ttl.startswith(k)), None)   # a long title may wrap: its first line counts
        a, b = (first(title[c]) for c in cols)
        if not (a and b and a[0] == b[0] and abs(a[2] - b[2]) <= 6 and b[1] - a[1] >= 150):
            at = lambda v: f"page {v[0]}, x {v[1]:.0f}, y {v[2]:.0f}" if v else "not found"
            fails.append(f"C19 render: {cols[0]} and {cols[1]} do not print side by side as the schema's columns "
                         f"({cols[0]} {at(a)}; {cols[1]} {at(b)}): cut words to fit, never change --columns")
    return fails


def render_check(pdf, dpi=72):
    """C19: nothing is cut off and no page ends in a blank band. Per page: no ink within 0.12in of any page edge;
    no word box outside the 0.3in side margins or past the page; the last ink above the 0.62in footer margin ends
    within 0.5in of it; page 1 shows the logo whole in the top-right masthead (its ink box sits inside the page
    with a clear gap on every side)."""
    fails, edge, side = [], int(0.12 * dpi), 0.3 * 72
    with tempfile.TemporaryDirectory() as td:
        subprocess.run(["pdftoppm", "-gray", "-r", str(dpi), str(pdf), f"{td}/p"], check=True)
        pages = sorted(pathlib.Path(td).glob("p-*.pgm"))
        for n, pg in enumerate(pages, 1):
            w, h, px = _pgm(pg)
            ink = lambda x, y: px[y * w + x] < 200
            for name, xs, ys in (("top", range(w), range(edge)), ("bottom", range(w), range(h - edge, h)),
                                 ("left", range(edge), range(h)), ("right", range(w - edge, w), range(h))):
                if any(ink(x, y) for y in ys for x in xs):
                    fails.append(f"C19 render: page {n}: ink within 0.12in of the {name} edge (clipped or bleeding)")
            foot = h - int(0.62 * dpi)   # Daniel, Oct 14: every page fully used, no dead space
            last = next((y for y in range(foot, 0, -1) if any(ink(x, y) for x in range(w))), 0)
            if foot - last > 0.5 * dpi:
                fails.append(f"C19 render: page {n} ends {(foot - last) / dpi:.1f}in above its footer margin (a blank band)")
            if n == 1:   # logo: top-right quarter-inch band down to 1.3in, right of 5.5in
                x0, y0, x1, y1 = int(5.5 * dpi), 0, w, int(1.3 * dpi)
                pts = [(x, y) for y in range(y0, y1) for x in range(x0, x1) if ink(x, y)]
                if not pts:
                    fails.append("C19 render: page 1: no logo in the top-right masthead")
                else:
                    bx0, by0 = min(p[0] for p in pts), min(p[1] for p in pts)
                    bx1, by1 = max(p[0] for p in pts), max(p[1] for p in pts)
                    if by0 <= edge or bx1 >= w - edge or (bx1 - bx0) < 0.6 * dpi or (by1 - by0) < 0.4 * dpi:
                        fails.append(f"C19 render: page 1: logo cut off or too small (box {bx0},{by0}-{bx1},{by1} px at {dpi} dpi)")
                    elif (by1 - by0) / (bx1 - bx0) < 0.92 * LOGO_ASPECT:   # a page margin cut its top flat (Oct 14)
                        fails.append(f"C19 render: page 1: logo cut off: printed {(by1 - by0) / (bx1 - bx0):.2f} high per unit wide, "
                                     f"the logo is {LOGO_ASPECT}")
    fails += side_by_side(pdf)
    r = subprocess.run(["pdftotext", "-bbox", str(pdf), "-"], capture_output=True, text=True)
    page, pw, ph = 0, 612.0, 792.0
    for ln in r.stdout.splitlines():
        m = re.search(r'<page width="([\d.]+)" height="([\d.]+)"', ln)
        if m:
            page += 1; pw, ph = float(m.group(1)), float(m.group(2)); continue
        m = re.search(r'xMin="([\d.]+)" yMin="([\d.]+)" xMax="([\d.]+)" yMax="([\d.]+)">([^<]*)<', ln)
        if m:
            x0, y0, x1, y1 = map(float, m.groups()[:4])
            if x0 < side or x1 > pw - side or y0 < 0 or y1 > ph:
                fails.append(f"C19 render: page {page}: word '{m.group(5)}' outside the margins (x {x0:.0f}-{x1:.0f} of {pw:.0f}pt)")
    return fails



COLORS = {"#0F2744": "Midnight", "#000000": "black", "#FFFFFF": "white"}   # brand/BRAND.md, the brief's three


def text_colors(pdf):
    """C20: every printed character is Midnight, black or white (Ben, Oct 14: "get rid of that gray ... three colors";
    grey text is lost when the page is printed). Reads each text run's fill colour with poppler's pdftohtml."""
    if shutil.which("pdftohtml") is None:
        return []
    x = subprocess.run(["pdftohtml", "-xml", "-i", "-q", "-stdout", str(pdf)], capture_output=True, text=True).stdout
    rgb = lambda h: [int(h[i:i + 2], 16) for i in (1, 3, 5)]
    ok = lambda h: any(all(abs(a - b) <= 2 for a, b in zip(rgb(h), rgb(c))) for c in COLORS)   # poppler rounds a channel down
    bad = {f: c.upper() for f, c in re.findall(r'<fontspec id="(\d+)"[^>]*color="(#[0-9a-fA-F]{6})"', x) if not ok(c)}
    seen, page = {}, 0
    for ln in x.splitlines():
        page += ln.startswith("<page ")
        m = re.match(r'<text [^>]*font="(\d+)"[^>]*>(.*)</text>', ln)
        if m and m.group(1) in bad:
            seen.setdefault(bad[m.group(1)], []).append((page, html.unescape(re.sub(r"<[^>]+>", "", m.group(2))).strip()))
    return [f"C20 colors: {len(v)} text run{'s' * (len(v) != 1)} print in {c}, e.g. page {v[0][0]} '{v[0][1][:40]}'; text is "
            + ", ".join(f"{k} {h}" for h, k in COLORS.items()) + " only" for c, v in seen.items()]


# ---------------------------------------------------------------- battery (C21) ----------------------------------
OPERATOR = re.compile(r"\b(?:site|intitle|inurl|filetype|after|before|allintitle|allinurl):|\bOR\b|(?:^|\s)-[\"\w]")
RUN_COUNTS = re.compile(r"(\d+) searches(?: \((\d+) base\))? in (\d+) rounds")   # N total, B in the base pass, M rounds
BROWSER_TOOL = re.compile(r"chrome|computer|browser|playwright", re.I)
URL = re.compile(r"https?://[^\s\"'<>)\]]+")


def _page(url):
    """A URL as the page it names: no scheme, www., fragment, trailing slash or utm_ tags."""
    import urllib.parse
    p = urllib.parse.urlsplit(url.strip().rstrip(".,;"))
    q = "&".join(x for x in p.query.split("&") if x and not x.startswith("utm_"))
    return p.netloc.lower().removeprefix("www.") + p.path.rstrip("/") + ("?" + q if q else "")


def enabled(depth, kind="person", scope="professional"):
    """The source types a run enables: the depth column, the target kind (company and deal targets drop person-only types) and the
    social scope (none: no public-social type). Same filter as the source-types table in SKILL.md."""
    return [f for f in R["families"] if depth in f["depth"] and kind in f["kinds"] and not (scope == "none" and f["socmint"])]


def base_families(depth, kind="person", scope="professional"):
    """S2-9 base pass: the source types enabled that have a search template of their own. F11 reads the user's
    notes (no search); F9 searches the registers of the user's domain (none for a general one), so neither is required."""
    return [f for f in enabled(depth, kind, scope) if not str(f["query"]).startswith(("known_context", "by_domain"))]


def family_sig(f):
    """The terms of a source type's query template that make it that type: placeholders, quotes, OR and the filter left out."""
    q = re.sub(r"\{[^}]*\}", " ", str(f["query"]).split(" -- ")[0])
    return [w for w in (x.lower().removeprefix("site:") for x in re.findall(r"[A-Za-z][\w.:/-]*", q)) if w not in ("or", "and", "site", "") and len(w) > 2]


def family_sent(f, queries):
    """Did one of the base-pass queries carry this source type's template terms? Half of them, at least one (F1's template is
    all placeholders: any base search is its). F6 also counts a search filtered to one of its networks."""
    sig = family_sig(f)
    nets = R["research"]["socmint_networks"]["social"]
    for q in queries:
        text, doms = q.get("query", "").lower(), " ".join(q.get("domains") or []).lower()
        if not sig or sum(1 for w in sig if w in text) >= max(1, len(sig) // 2) or (f["id"] == "F6" and any(n.split("/")[0] in doms for n in nets if "." in n)):
            return True
    return False


def battery_floor(depth, kind="person", scope="professional"):
    """S2-9: the rounds a depth runs (every round with a source type the depth enables), the queries each round sends
    at least, and how many of all of them carry an operator or a domain filter. render_skill.py prints the same table."""
    b = R["osint"]["battery"]
    on = {f["id"] for f in enabled(depth, kind, scope)}
    need = [r["round"] for r in R["osint"]["rounds"] if on & set(r["types"])]
    per = b["queries_per_round"][depth]
    return need, per, math.ceil(round(per * len(need) * b["operator_share"], 6))


# ---------------------------------------------------------------- history: one reader for every host -------------------
# The battery (C21), quiet research (C21), questions (C22) are read from the run's own history, not its report. Hosts keep
# that history in different files; each is read into the same events, so no host is "unavailable":
#   Claude Code / Agent SDK  stream-json or ~/.claude/projects/<folder>/<session>.jsonl   (assistant / user / result lines)
#   Codex                    ~/.codex/sessions/YYYY/MM/DD/rollout-<time>-<thread id>.jsonl (response_item / event_msg lines)
#   ChatGPT app              the export's conversations.json (a mapping of messages)
#   Claude app               the export's conversations.json (chat_messages with content blocks)
# An event is a dict: kind text | thinking | user | search | open | ask | browser | shell | result | redirect, plus step
# (the tool step it belongs to: searches of one step are one round), and text / query / filtered / url / name / questions.
HOST_FILES = ("Claude Code: the newest ~/.claude/projects/<folder>/*.jsonl; Codex: ~/.codex/sessions/**/rollout-*<$CODEX_THREAD_ID>.jsonl; "
              "ChatGPT or the Claude app: the conversations.json from the account's data export")
ASK_TOOL = re.compile(r"ask|question|user_input", re.I)


def _blocks_claude(e, ev, st):
    """One Claude Code / Agent SDK line (stream-json and session files share it)."""
    if e.get("type") == "system" and e.get("subtype") == "init":
        ev.append(dict(kind="tools", names=e.get("tools") or [])); return
    if e.get("type") == "result" and e.get("result"):
        ev.append(dict(kind="result", text=e["result"])); return
    if e.get("type") == "user":
        c = e.get("message", {}).get("content")
        if isinstance(c, str):
            ev.append(dict(kind="user", text=c))
        for x in c if isinstance(c, list) else []:
            if x.get("type") == "text":
                ev.append(dict(kind="user", text=x.get("text", "")))
            elif x.get("type") == "tool_result":
                body = json.dumps(x.get("content"))
                ev.append(dict(kind="tool_result", id=x.get("tool_use_id"), text=body))
                if re.search(r"redirect", body, re.I):
                    ev.append(dict(kind="redirect", id=x.get("tool_use_id"), urls=URL.findall(body.replace("\\n", " "))))
        return
    if e.get("type") != "assistant":
        return
    st["n"] += 1
    step = e.get("message", {}).get("id") or f"line-{st['n']}"   # stream-json splits one message's blocks over lines
    side = bool(e.get("isSidechain") or e.get("parent_tool_use_id"))   # a subagent's own messages: not the reply
    for x in e.get("message", {}).get("content") or []:
        t = x.get("type")
        if t == "text":
            ev.append(dict(kind="text", text=x.get("text", ""), step=step, side=side))
        elif t == "thinking":
            ev.append(dict(kind="thinking", text=x.get("thinking") or x.get("text") or "", step=step))
        elif t == "tool_use":
            name, inp = x.get("name", ""), x.get("input") or {}
            if name == "WebSearch":
                ev.append(dict(kind="search", step=step, query=inp.get("query", ""),
                               filtered=bool(inp.get("allowed_domains") or inp.get("blocked_domains")),
                               domains=inp.get("allowed_domains") or []))
            elif name == "WebFetch":
                ev.append(dict(kind="open", step=step, url=inp.get("url", ""), id=x.get("id")))
            elif name == "Bash" and re.search(r"\b(?:curl|wget)\b", inp.get("command", "")):
                ev.append(dict(kind="shell", step=step, urls=URL.findall(inp["command"]), command=inp["command"]))
            elif ASK_TOOL.search(name):
                ev.append(dict(kind="ask", step=step, name=name, id=x.get("id"), questions=_ask_texts(inp)))
            elif name in ("Agent", "Task"):
                ev.append(dict(kind="delegate", step=step, name=name, text=str(inp.get("description", ""))))
            if BROWSER_TOOL.search(name):
                ev.append(dict(kind="browser", step=step, name=name))


def _ask_texts(obj):
    """Every question string a question widget's arguments carry (question, title, prompt, label, header)."""
    out = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k in ("question", "title", "prompt", "text", "message") and isinstance(v, str):
                out.append(v)
            else:
                out += _ask_texts(v)
    elif isinstance(obj, list):
        for v in obj:
            out += _ask_texts(v)
    return out


JS_Q = re.compile(r"""\bq\s*:\s*(?:'((?:[^'\\]|\\.)*)'|"((?:[^"\\]|\\.)*)"|`((?:[^`\\]|\\.)*)`)\s*(?:,\s*domains\s*:\s*\[([^\]]*)\])?""")


def _js_unescape(s):
    return re.sub(r"\\(.)", lambda m: {"n": "\n", "t": "\t"}.get(m.group(1), m.group(1)), s)


def _blocks_codex(e, ev, st):
    """One Codex rollout line. Searches and page opens are the app's own item_completed events (web.search); each
    carries the queries it sent. Their domain filters are only in the script that sent them (domains:[...]), so those are
    read from the exec call's text."""
    p = e.get("payload") or {}
    if e.get("type") == "response_item":
        t = p.get("type")
        if t == "message":
            txt = "".join(x.get("text", "") for x in p.get("content") or [] if isinstance(x, dict))
            if p.get("role") == "assistant":
                ev.append(dict(kind="text", text=txt, step=st["call"]))
            elif p.get("role") == "user" and txt.strip() and not txt.lstrip().startswith(("<", "# AGENTS")):
                ev.append(dict(kind="user", text=txt))
        elif t == "reasoning":
            summ = " ".join(x.get("text", "") for x in p.get("summary") or [] if isinstance(x, dict))
            ev.append(dict(kind="thinking", text=summ, step=st["call"]))
        elif t == "function_call_output":
            out = p.get("output")
            ev.append(dict(kind="tool_result", id=p.get("call_id"), text=out if isinstance(out, str) else json.dumps(out)))
        elif t in ("custom_tool_call", "function_call"):
            st["call"] += 1
            body = p.get("input") or p.get("arguments") or ""
            name = p.get("name", "")
            if t == "function_call" and ASK_TOOL.search(name):
                try:
                    qs = _ask_texts(json.loads(body))
                except ValueError:
                    qs = [body]
                ev.append(dict(kind="ask", step=st["call"], name=name, id=p.get("call_id"), questions=qs))
            for m in JS_Q.finditer(body):
                q = _js_unescape(next(g for g in m.groups()[:3] if g is not None))
                if m.group(4) and re.search(r"\w", m.group(4)):
                    st["filters"].setdefault(q, [])
                    st["filters"][q] += re.findall(r"[\"'`]([^\"'`]+)[\"'`]", m.group(4))
            for tool in set(re.findall(r"\btools\.(\w+)\(", body)):
                if BROWSER_TOOL.search(tool):
                    ev.append(dict(kind="browser", step=st["call"], name=tool))
            if re.search(r"\b(?:curl|wget)\b", body):
                ev.append(dict(kind="shell", step=st["call"], urls=URL.findall(body), command=body))
            for u in re.findall(r"open\s*:\s*\[([^\]]*)\]", body):   # web__run({open:[{ref_id:"https://..."}]})
                ev.append(dict(kind="open", step=st["call"], url=" ".join(URL.findall(u)), planned=True))
        return
    if e.get("type") == "event_msg" and p.get("type") == "item_completed":
        it = p.get("item") or {}
        if it.get("kind") == "web.search":
            a = it.get("action") or {}
            if a.get("type") == "search":
                for q in a.get("queries") or ([a["query"]] if a.get("query") else []):
                    doms = st["filters"].get(q, [])
                    ev.append(dict(kind="search", step=st["call"], query=q, filtered=bool(doms), domains=doms))
            elif a.get("type") == "openPage" and a.get("url"):
                ev.append(dict(kind="open", step=st["call"], url=a["url"]))


def _parts_text(content):
    if not isinstance(content, dict):
        return str(content or "")
    parts = content.get("parts")
    if parts:
        return "\n".join(x if isinstance(x, str) else (x.get("text", "") if isinstance(x, dict) else "") for x in parts)
    return content.get("text") or ""


def _chatgpt(conv, ev):
    """One ChatGPT export conversation: walk the message tree from the current node back to the root. Searches are the
    assistant's tool calls to the browser tool (search("..."), a JSON search_query list) or the message's own search queries."""
    mp = conv.get("mapping") or {}
    chain, node = [], conv.get("current_node") or next(reversed(mp), None)
    while node and node in mp:
        chain.append(mp[node]); node = mp[node].get("parent")
    for n, nd in enumerate(reversed(chain)):
        m = nd.get("message") or {}
        role = (m.get("author") or {}).get("role")
        c = m.get("content") or {}
        ctype, text, step = c.get("content_type"), _parts_text(c), m.get("id") or f"msg-{n}"
        rcp = m.get("recipient") or "all"
        if role == "user" and ctype in ("text", "multimodal_text") and text.strip():
            ev.append(dict(kind="user", text=text))
        elif role == "assistant" and rcp == "all" and ctype in ("text", "multimodal_text") and text.strip():
            ev.append(dict(kind="text", text=text, step=step))
        elif role == "assistant" and ctype in ("thoughts", "reasoning_recap"):
            ev.append(dict(kind="thinking", text=text or json.dumps(c.get("thoughts", "")), step=step))
        elif role == "assistant" and rcp != "all":   # a tool call: browser / web / web.run
            qs = [m_.group(1) or m_.group(2) for m_ in re.finditer(r"""search\(\s*(?:"((?:[^"\\]|\\.)*)"|'((?:[^'\\]|\\.)*)')""", text)]
            try:
                j = json.loads(text)
            except ValueError:
                j = None
            doms = {}
            if isinstance(j, dict):
                for x in j.get("search_query", []):
                    if isinstance(x, dict):
                        qs.append(x.get("q", "")); doms[x.get("q", "")] = x.get("domains") or []
                for x in j.get("open", []) or []:
                    if isinstance(x, dict) and str(x.get("ref_id", "")).startswith("http"):
                        ev.append(dict(kind="open", step=step, url=x["ref_id"]))
            for q in qs:
                ev.append(dict(kind="search", step=step, query=_js_unescape(q), filtered=bool(doms.get(q)), domains=doms.get(q, [])))
            for u in re.findall(r"""open_url\(\s*["']([^"']+)""", text):
                ev.append(dict(kind="open", step=step, url=u))
        sq = (m.get("metadata") or {}).get("search_model_queries") or {}
        for q in sq.get("queries", []) if isinstance(sq, dict) else []:
            ev.append(dict(kind="search", step=step, query=q, filtered=False, domains=[]))
        for x in (m.get("metadata") or {}).get("search_result_groups") or []:
            for r in x.get("entries", []) if isinstance(x, dict) else []:
                pass   # results are not requests


def _claude_app(conv, ev):
    for n, m in enumerate(conv.get("chat_messages") or []):
        step = m.get("uuid") or f"msg-{n}"
        if m.get("sender") == "human":
            ev.append(dict(kind="user", text=m.get("text") or " ".join(x.get("text", "") for x in m.get("content") or [] if isinstance(x, dict))))
            continue
        blocks = m.get("content") or [dict(type="text", text=m.get("text", ""))]
        for x in blocks:
            t = x.get("type")
            if t == "text" and (x.get("text") or "").strip():
                ev.append(dict(kind="text", text=x["text"], step=step))
            elif t == "thinking":
                ev.append(dict(kind="thinking", text=x.get("thinking", ""), step=step))
            elif t == "tool_use":
                name, inp = x.get("name", ""), x.get("input") or {}
                if re.search(r"web_search|WebSearch", name):
                    ev.append(dict(kind="search", step=step, query=inp.get("query", ""),
                                   filtered=bool(inp.get("allowed_domains") or inp.get("blocked_domains")), domains=inp.get("allowed_domains") or []))
                elif re.search(r"web_fetch|WebFetch", name):
                    ev.append(dict(kind="open", step=step, url=inp.get("url", ""), id=x.get("id")))
                elif ASK_TOOL.search(name):
                    ev.append(dict(kind="ask", step=step, name=name, id=x.get("id"), questions=_ask_texts(inp)))
                if BROWSER_TOOL.search(name):
                    ev.append(dict(kind="browser", step=step, name=name))


def read_history(lines):
    """The events of one run, whatever host kept them. `lines` is the file's lines (jsonl) or its whole text (json);
    an already-read event list passes through. Returns (events, host)."""
    if lines and isinstance(lines[0], dict):
        return lines, "events"
    text = "\n".join(ln.rstrip("\n") for ln in lines)
    host, ev = None, []
    try:
        data = json.loads(text)   # a whole-file export; a .jsonl history is many documents, so this fails and the lines are read
    except ValueError:
        data = None
    convs = data if isinstance(data, list) else [data] if isinstance(data, dict) else []
    if convs and isinstance(convs[0], dict) and "mapping" in convs[0]:
        host = "ChatGPT export"
        for c in convs:
            _chatgpt(c, ev)
        return ev, host
    if convs and isinstance(convs[0], dict) and "chat_messages" in convs[0]:
        host = "Claude app export"
        for c in convs:
            _claude_app(c, ev)
        return ev, host
    st = {"n": 0, "call": 0, "filters": {}}
    for line in text.splitlines():
        try:
            e = json.loads(line)
        except ValueError:
            continue
        if not isinstance(e, dict):
            continue
        if host is None:
            host = "Codex" if e.get("type") in ("session_meta", "response_item", "event_msg", "turn_context", "world_state", "token_usage_record") else "Claude Code"
        (_blocks_codex if host == "Codex" else _blocks_claude)(e, ev, st)
    return ev, host or "Claude Code"


def find_history(host=None, cwd=None, home=None):
    """The history files this host keeps for the current session (--latest), the run's own first: Claude Code's project folder for
    the working folder (under $CLAUDE_CONFIG_DIR when set, else ~/.claude) plus the transcripts of the subagents that session started
    (<session>/subagents/*.jsonl: a background collection job's searches are there, not in the main file), or the Codex rollout whose
    name carries $CODEX_THREAD_ID (else the newest). Returns a list of paths, [] when there is none."""
    import os
    home = pathlib.Path(home) if home else pathlib.Path.home()
    tid = os.environ.get("CODEX_THREAD_ID", "")
    if host in (None, "codex") and (tid or host == "codex"):
        files = sorted((home / ".codex/sessions").glob("**/rollout-*.jsonl"), key=lambda p: p.stat().st_mtime, reverse=True)
        hit = [p for p in files if tid and tid in p.name]
        if hit or (host == "codex" and files):
            return [(hit or files)[0]]
    root = pathlib.Path(os.environ["CLAUDE_CONFIG_DIR"]) if os.environ.get("CLAUDE_CONFIG_DIR") else home / ".claude"
    folder = re.sub(r"[^A-Za-z0-9]", "-", str(pathlib.Path(cwd or os.getcwd()).resolve()))
    files = sorted((root / "projects" / folder).glob("*.jsonl"), key=lambda p: p.stat().st_mtime, reverse=True) if (root / "projects" / folder).is_dir() else []
    if not files:
        return []
    main = files[0]
    return [main] + sorted((main.parent / main.stem / "subagents").glob("*.jsonl"), key=lambda p: p.stat().st_mtime)


def history_lines(files):
    """The lines of a run's history files, read as one history. Claude Code and Claude desktop keep a subagent's transcript in its own
    file (<session>/subagents/*.jsonl) and its searches ran while the main thread waited, so the lines of every file are merged by
    their timestamps (a line with none keeps its place after the line before it). Read one file after the other, a search the main
    thread made after the job came back sits before all of the job's searches and every reply after it reads as 'between searches'
    (Oct 17). A Codex rollout or an app export is read as given."""
    texts = [pathlib.Path(t).read_text() for t in files]
    def stamped(text):
        try:
            json.loads(text)
            return False   # one JSON document: an app export
        except ValueError:
            pass
        rows = [json.loads(ln) for ln in text.splitlines() if ln.strip().startswith("{")]
        return any("timestamp" in r for r in rows) and not any(r.get("type") in ("session_meta", "response_item", "event_msg") for r in rows)
    if len(texts) < 2 or not all(stamped(t) for t in texts):
        return [ln for t in texts for ln in t.splitlines()]
    keyed = []
    for fi, text in enumerate(texts):
        last = ""
        for li, ln in enumerate(text.splitlines()):
            try:
                e = json.loads(ln)
            except ValueError:
                e = None
            last = max(last, str(e.get("timestamp") or "")) if isinstance(e, dict) else last   # a file keeps its own order
            keyed.append(((last, fi, li), ln))
    return [ln for _, ln in sorted(keyed, key=lambda x: x[0])]


def _content_words(t):
    return {w for w in re.findall(r"\b(?:ai|[a-z][a-z'-]{2,})\b", t.lower()) if w not in STOP}


STOP = set("ai software platform solution solutions service services tool tools technology company business "   # words every offer shares: they never show two offers are the same
           "the and for are but not you your with that this from have has had was were will can could would should about into over than then them they their "
           "who what when where which how why any all one two out our its his her him she who whom also use used using per via get got let may might "
           "meeting call prep prepare first second time want need new".split())


def offer_conflict(saved, request):
    """C22: the saved offer (Q8) and the request name different businesses. The clear case only: the request states a purpose
    (about / sell / pitch / offer / discuss / my ...) whose content words share none with the saved offer or the saved domain's
    vocabulary. A judgment call stays the model's; this flags the one it must not miss. Returns the request's purpose words or []."""
    purpose = re.findall(r"(?:about|sell(?:ing)?|pitch(?:ing)?|offer(?:ing)?|discuss(?:ing)?|propos(?:e|ing)|introduc(?:e|ing)|demo)\s+([^.;\n]{3,120})", request, re.I)
    words = set().union(*[_content_words(p) for p in purpose]) if purpose else set()
    # the domain's own vocabulary counts as the saved business too (Q2)
    sv = _content_words(saved)
    sv_stems = {w[:5] for w in sv}
    shared = {w for w in words if w[:5] in sv_stems}
    return sorted(words) if len(words) >= 2 and not shared else []


# ---------------------------------------------------------------- battery (C21), questions (C22) -------------------
ROUND_LIST = re.compile(r"\bRounds?\s+\d\b[^\n]{0,90}(?:\||`[^`]+`[^\n]*`[^`]+`|\"[^\"]+\"[^\n]*\"[^\"]+\")")


def _round_heads(t):
    return re.findall(r"^\W*Round (\d)\s*\(", t or "", re.M)


def battery(lines, depth="standard", brief="", cited=None, profile=None, popup=None, kind="person", scope="professional"):
    """C21 and C22, read from the run's history (read_history: Claude Code, Codex, ChatGPT, Claude app). Returns
    (failures, summary).

    C21. S2-9 sends a round's queries together, in one step, so each step's batch of searches is one round. A 'Round N
    (name): ...' line in the reasoning gives its number; a batch with no line takes the number after the round before it.
    Quiet: the reply carries no round line and no text between the first search and the last (one short status before the
    first search, a question or a stop aside): Codex (Oct 16) printed all ten rounds in chat. With the brief, every page
    its ledger cites (the PDF's links, or the brief.md's) must be one the run requested, LinkedIn aside. C11 also reads each
    reply the user got.
    C22. A question is written in the reply (visible, with its skip rule), and the run waits for the answer: no search, page
    or file work between the question and the user's next message. A saved offer (profile) that conflicts with the request
    needs a question before the first search."""
    ev, host = read_history(lines)
    fails, batches, named, order = [], {}, {}, []
    given = [u for e in ev if e["kind"] == "user" for u in URL.findall(e.get("text", "")) if "linkedin.com" in u.lower()]   # D2: the user's own link
    pending, early, opened, fetch_ids = None, [], set(), set()
    searches = [e for e in ev if e["kind"] == "search"]
    first_s = next((i for i, e in enumerate(ev) if e["kind"] == "search"), None)
    last_s = max((i for i, e in enumerate(ev) if e["kind"] == "search"), default=None)
    for i, e in enumerate(ev):
        k = e["kind"]
        if k in ("text", "thinking"):
            heads = _round_heads(e["text"])
            if heads:
                pending = int(heads[-1])
                if k == "text" and not e.get("side"):
                    fails.append(f"C21 quiet: a round line went out in the reply ('Round {heads[-1]} (...'): keep each round's line in your reasoning; "
                                 "the Run row counts them ('N searches (B base) in M rounds')")
            elif k == "text" and not e.get("side") and ROUND_LIST.search(e["text"]):
                fails.append("C21 quiet: the reply lists a round's queries ('" + ROUND_LIST.search(e["text"]).group(0)[:50] + "'): search queries live in coverage.json, never in chat")
        elif k == "search":
            s = e["step"]
            if s not in batches:
                batches[s], named[s], pending = [], pending, None
                order.append(s)
            batches[s].append(e)
        elif k == "open":
            opened.add(_page(e["url"])); fetch_ids.add(e.get("id"))
            if "linkedin.com" in e["url"].lower() and not any(_page(e["url"]) == _page(u) for u in given):
                fails.append(f"C21 battery: a linkedin.com page was requested ({e['url']}) that the user did not give; "
                             "LinkedIn is read from search results, or from the one address the user gives")
        elif k == "redirect" and e.get("id") in fetch_ids:
            opened.update(_page(u) for u in e["urls"])
        elif k == "shell":
            opened.update(_page(u) for u in e["urls"])
            if re.search(r"(?:curl|wget)[^\n]*linkedin\.com", e["command"]):
                fails.append("C21 battery: a shell command requested linkedin.com; LinkedIn is read from search results only")
        elif k == "browser":
            fails.append(f"C21 battery: the browser tool {e['name']} was called; research never drives a browser")
    if first_s is not None:   # quiet: no reply text between the first and the last search, a question aside
        loud = [e for i, e in enumerate(ev) if e["kind"] == "text" and not e.get("side") and first_s < i < last_s and e["text"].strip()
                and not any(x["kind"] == "ask" for x in ev[i + 1:i + 3]) and not _round_heads(e["text"])]
        if loud:
            fails.append(f"C21 quiet: {len(loud)} reply message{'s' * (len(loud) != 1)} between the first and the last search "
                         f"(e.g. '{loud[0]['text'].strip()[:60]}'): write nothing in the reply until the brief; results go in the brief")
    shown = [i for i, e in enumerate(ev) if e["kind"] == "text" and not e.get("side") and e["text"].strip()]
    final = shown[-1] if shown else None   # the last reply is the closing reply, not a status
    status = [ev[i] for i in shown if i != final and not any(x["kind"] == "ask" for x in ev[i + 1:i + 3])]
    long = [e for e in status if len(e["text"].split()) > 30]
    if long:
        fails.append(f"C21 quiet: {len(long)} status message{'s' * (len(long) != 1)} over 30 words (e.g. '{long[0]['text'].strip()[:50]}...'): one short status line per stage")
    if first_s is not None and len(status) > 5:
        fails.append(f"C21 quiet: {len(status)} status messages in the reply; at most one per stage (five)")
    need, per, ops_min = battery_floor(depth, kind, scope)
    req = base_families(depth, kind, scope)
    lined = any(v is not None for v in named.values())
    later = []   # search steps after the last round (a gap fill, a check while writing): counted in N, never a round
    if lined:   # round lines name the rounds; the searches before the first one are the base pass
        base_steps = order[:next(i for i, s in enumerate(order) if named[s] is not None)]
    else:
        # no lines: the base pass is the first steps that together carry every source type's template; the next batches, one per
        # round, are the rounds, and any step after them is a later search. With no such prefix, the last batches are the rounds
        # (a Claude desktop job, Oct 17: two gap-fill steps after round 5 were read as rounds 4 and 5, and round 1 as part of the base)
        cover = next((i + 1 for i in range(len(order)) if all(family_sent(f, [q for s in order[:i + 1] for q in batches[s]]) for f in req)), None)
        if cover is None or not req:
            base_steps = order[:max(0, len(order) - len(need))]
        else:
            base_steps, later = order[:cover], order[cover + len(need):]
    base = [q for s in base_steps for q in batches[s]]
    rounds, steps, n = {}, {}, 0
    for s in order[len(base_steps):len(order) - len(later)]:
        qs = batches[s]
        if named[s] is not None:
            n = named[s]
        else:
            n += 1
        rounds.setdefault(n, []).extend(qs); steps[n] = steps.get(n, 0) + 1
    split = sorted(k for k, v in steps.items() if v > 1)
    if split:
        fails.append(f"C21 battery: rounds {split} went out over several steps; send each round's queries together, once")
    sent = [q for qs in rounds.values() for q in qs]
    done = [n for n in rounds if rounds[n]]
    ops = sum(1 for q in sent if q.get("filtered") or OPERATOR.search(q.get("query", "")))
    lacking = [f for f in req if not family_sent(f, base)]
    if not base:
        fails.append(f"C21 base: no base pass before the rounds; send each source type's query template first ({len(req)} for a {depth} run, S2-9)")
    elif lacking:
        fails.append(f"C21 base: {len(lacking)} of {len(req)} source types never searched in the base pass: "
                     + ", ".join(f"{f['id']} {f['name']}" for f in lacking[:5]) + (" ..." if len(lacking) > 5 else "")
                     + "; the rounds add to the base pass and never replace it")
    missing = [n for n in need if n not in done]
    if missing:
        fails.append(f"C21 battery: rounds {missing} not run; a {depth} run runs rounds {need}")
    extra = [n for n in done if n not in need]
    if extra:
        fails.append(f"C21 battery: {len(extra)} more rounds than the battery's {len(need)}: send each round's queries together, once")
    if done != sorted(done):
        fails.append(f"C21 battery: rounds ran in the order {done}, not 1 to 5")
    short = {n: len(rounds[n]) for n in need if 0 < len(rounds.get(n, [])) < per}
    if short:
        fails.append(f"C21 battery: rounds {short} sent fewer than {per} queries each")
    if ops < ops_min:
        fails.append(f"C21 battery: {ops} of {len(sent)} round queries carry an operator or a domain filter; a {depth} run needs {ops_min}")
    skip_li = re.search(r"LinkedIn:\**\s*not read: (?:scope none|you declined)", brief)
    li = [q for q in rounds.get(1, []) if "linkedin.com" in " ".join(q.get("domains") or []) or "linkedin.com" in q.get("query", "")]
    if not skip_li and not li:
        fails.append("C21 battery: round 1 sent no LinkedIn query")
    elif li and not any("linkedin.com" in " ".join(q.get("domains") or []) for q in li):
        fails.append("C21 battery: round 1's LinkedIn query typed site: into a search that ignores it; use the domain filter (allowed_domains)")
    after = [q for s in later for q in batches[s]]
    total = len(sent) + len(base) + len(after)
    tail = f" and {len(after)} later search{'es' * (len(after) != 1)} in {len(later)} step{'s' * (len(later) != 1)}" if later else ""
    if brief:
        said = RUN_COUNTS.search(re.sub(r"\s+", " ", brief))
        runday = re.search(r"\*\*Run\*\*\s*\|\s*([A-Z][a-z]{2} \d{1,2}, \d{4})", brief)
        need_base = bool(runday) and _day(runday.group(1)) >= dt.date.fromisoformat(str(R["osint"]["battery"]["base_since"]))
        if not said:
            fails.append("C21 battery: the brief's Run row does not say 'N searches (B base) in M rounds'")
        elif need_base and said.group(2) is None:
            fails.append("C21 battery: the Run row gives no base count; it says 'N searches (B base) in M rounds'")
        elif (int(said.group(1)), int(said.group(3))) != (total, len(done)) or (said.group(2) is not None and int(said.group(2)) != len(base)):
            fails.append(f"C21 battery: the Run row says {said.group(0)}; the history shows {total} searches ({len(base)} base) in {len(done)} rounds{tail}")
    fails += ask_check(ev, profile, popup)
    replies = [e["text"] for e in ev if e["kind"] == "result"] or [next((e["text"] for e in reversed(ev) if e["kind"] == "text"), "")]
    for i, reply in enumerate(replies, 1):   # a session file has no result line: its last text is the reply
        hits = plain_hits(reply)
        if hits:
            fails.append(f"C11 reply: reply {i} to the user says {hits}; plain words only (a grade is 'a single, weaker source'; "
                         "after the call, 'after-call notes')")
    pages = list(dict.fromkeys(_page(u) for u in (URL.findall(brief) if cited is None else cited)))
    unread = [p for p in pages if p and "linkedin.com" not in p and p not in opened]
    if unread:
        fails.append(f"C21 battery: the ledger cites {len(unread)} page{'s' * (len(unread) != 1)} the run never opened "
                     f"({', '.join(unread[:3])}{' ...' if len(unread) > 3 else ''}): open the page behind a result before citing it, or drop its fact")
    return fails, (f"{host}: {total} searches ({len(base)} base) in {len(done)} rounds {done}{tail}, {ops} round queries with an operator or a domain filter; "
                   f"per round {[len(rounds[n]) for n in done]}")


TYPED_LIST = re.compile(r"one number per line|reply with (?:the |a |one )?(?:option )?numbers?\b|answer with (?:the )?numbers?|such as \d, ?\d", re.I)
NOT_ANSWERED = re.compile(r'^\W*$|"accepted"\s*:\s*true\W*$|declin|dismiss|doesn.t want|no answer|cancel', re.I)


def ask_check(ev, profile=None, popup=None):
    """C22: questions go through the host's native popup tool (MUST-FIX 7: a ChatGPT run typed the setup questions out where
    upstream used AskUserQuestion); a typed list is only the fallback where the host has no such tool, or after a popup that
    came back empty. One line of the reply before the call says what skip does; the run then waits."""
    fails = []
    tools = next((e["names"] for e in ev if e["kind"] == "tools"), None)
    if popup is None:   # not told: the session's own tool list, else assume the host has a question tool
        popup = any(ASK_TOOL.search(n) for n in tools) if tools is not None else True
    results = {e["id"]: e["text"] for e in ev if e["kind"] == "tool_result"}
    result_at = {e["id"]: i for i, e in enumerate(ev) if e["kind"] == "tool_result"}
    ask_ids = {e.get("id") for e in ev if e["kind"] == "ask" and e.get("id")}
    first_s = next((i for i, x in enumerate(ev) if x["kind"] == "search"), len(ev))
    empty_at = []
    for i, e in enumerate(ev):
        if e["kind"] != "ask":
            continue
        win = ev[max(0, i - 4):i]   # each question call has its own line: one written before an earlier call or its answer does not count
        cut = max((j + 1 for j, x in enumerate(win) if x["kind"] == "ask" or (x["kind"] == "tool_result" and x.get("id") in ask_ids)), default=0)
        said = " ".join(x["text"] for x in win[cut:] if x["kind"] == "text")
        if not re.search(r"\bskip\b", said, re.I):
            fails.append(f"C22 ask: the question tool '{e['name']}' ('{(e['questions'] or [''])[0][:40]}') was called with no line of the reply "
                         "before it saying what skip does, its own line after any earlier question ('Two quick questions: answer in the popup, or skip and I'll use the recommended answers.')")
        later = next((j for j in range(i + 1, len(ev)) if ev[j]["kind"] == "user"), len(ev))
        body = results.get(e.get("id"))
        empty = body is not None and bool(NOT_ANSWERED.search(body.strip())) and not re.search(r"answered|selected|\w=\w|\"=\"", body)
        if body is not None and not empty:   # a popup's answer comes back as its own tool result: the wait ends there
            later = min(later, result_at[e["id"]])
        if empty:
            empty_at.append(i)
            retyped = any(x["kind"] == "text" and "?" in x["text"] and len(_content_words(" ".join(e["questions"])) & _content_words(x["text"])) >= 2 for x in ev[i + 1:later])
            if not retyped:
                fails.append(f"C22 ask: the question tool '{e['name']}' came back with no answer and the question was not asked again in the reply; "
                             "a popup that closes empty is not an answer: type the question and wait")
        moved = [x for x in ev[i + 1:later] if x["kind"] in ("search", "open", "shell")]
        if moved:
            fails.append(f"C22 ask: the run kept working after asking ({len(moved)} searches or page opens before the user's answer); "
                         "end the turn and wait for the answer or 'skip'")
    if popup:
        for i, x in enumerate(ev[:first_s]):
            if x["kind"] != "text" or "|" in x["text"]:
                continue
            numbered = len(re.findall(r"^\s*\d+[.)]\s+\S", x["text"], re.M))
            typed = TYPED_LIST.search(x["text"]) or (numbered >= 3 and "?" in x["text"])
            after_popup = any(y["kind"] == "ask" for y in ev[max(0, i - 6):i]) and bool(empty_at)
            if typed and not any(y["kind"] == "ask" for y in ev[i + 1:i + 4]) and not after_popup:
                fails.append("C22 ask: the questions were typed in the reply ('" + (TYPED_LIST.search(x["text"]) or re.search(r"\S.*", x["text"])).group(0)[:50]
                             + "') where the host has a question tool; ask with AskUserQuestion (the structured question tool in ChatGPT, Codex, Grok), "
                             "and type only where the host has none")
                break
    if profile:
        req = next((x["text"] for x in ev if x["kind"] == "user"), "")
        asked = any(x["kind"] == "ask" or (x["kind"] == "text" and "?" in x["text"] and re.search(r"saved|setup|offer", x["text"], re.I))
                    for x in ev[:first_s])
        diff = offer_conflict(profile, req)
        if diff and not asked:
            fails.append(f"C22 ask: the saved offer ('{profile[:50]}') conflicts with the request ({', '.join(diff[:4])}), and no question came before the first search")
    return fails


# ---------------------------------------------------------------- records (C23): claims, coverage, behavioral read -----
def _load_json(path):
    try:
        return json.loads(pathlib.Path(path).read_text()), None
    except (OSError, ValueError) as err:
        return None, f"{pathlib.Path(path).name}: {err.__class__.__name__}: {str(err)[:80]}"


def records_check(folder, depth="standard", brief=""):
    """C23: the run's three records are complete and agree with each other before the run is called done.
      claims.jsonl  every claim has every field of pcp.yaml records.claims, valid tag, grade and confidence, a unique id
      coverage.json every field of records.coverage; hits_by_family and attempted cover all 12 source types; the counts equal
                    what claims.jsonl holds; status is FULL only when S2-5 says so
      read.json     six dimensions, each with every field of records.read; a band that matches its meaning; no read means no
                    observations and tier low; observation ids exist; a tier needs its minimum observations
    With the brief: its tier line, status and 'n of 12 source types' agree with the records."""
    rec, d = R["records"], pathlib.Path(folder)
    fam = [f["id"] for f in R["families"]]
    fails = []
    cp = d / rec["claims"]["file"]
    claims = []
    if not cp.exists():
        fails.append(f"C23 records: {cp.name} is missing")
    else:
        for n, ln in enumerate(cp.read_text().splitlines(), 1):
            if not ln.strip():
                continue
            try:
                claims.append(json.loads(ln))
            except ValueError:
                fails.append(f"C23 records: {cp.name} line {n} is not JSON")
        for c in claims:
            gone = [k for k in rec["claims"]["fields"] if k not in c]
            if gone:
                fails.append(f"C23 records: claim {c.get('id', '?')} lacks {gone}")
            for k, ok in (("tag", rec["claims"]["tag"]), ("grade", rec["claims"]["grade"]), ("confidence", rec["claims"]["confidence"]),
                          ("family", fam)):
                if k in c and c[k] not in ok:
                    fails.append(f"C23 records: claim {c.get('id', '?')} has {k} '{c[k]}'; one of {ok}")
        ids = [c.get("id") for c in claims]
        if len(ids) != len(set(ids)):
            fails.append("C23 records: claim ids repeat")
        if not claims:
            fails.append(f"C23 records: {cp.name} holds no claims")
    if brief and claims:   # stage isolation (S4-12): the brief holds only what the record holds
        have = {_page(c.get("url", "")) for c in claims if str(c.get("url", "")).startswith("http")} | {str(c.get("url", "")).lower() for c in claims}
        for k, rows in ledger_facts(brief).items():
            if k[0] and k[0] not in have and not any(k[0] in h or h in k[0] for h in have if h):
                fails.append(f"C23 records: ledger row [{rows[0]['n']}] cites {k[0]}, which claims.jsonl does not hold; the brief holds only what the records hold (S4-12)")
    if brief and claims:   # C2 (2.1.0): every cited fact has url + tag + date + C-level. The page prints them as the ledger's source, grade and date;
        # the record holds them in full, so a ledger row whose claim lacks one is a fact 2.1.0 would have dropped
        keys = {k[0] for k in ledger_facts(brief)}
        for c in claims:
            u = str(c.get("url", ""))
            page = _page(u) if u.startswith("http") else u.lower()
            if not any(k == page or (page and (k in page or page in k)) for k in keys):
                continue
            gone = [f for f in next(x for x in R["checks"] if x.get("id") == "C2")["claim_requires"] if not str(c.get(f) or "").strip()]
            if gone:
                fails.append(f"C23 records: claim {c.get('id', '?')} is a cited ledger row, yet claims.jsonl has no {gone} for it; every cited fact keeps its url, tag, date and confidence (2.1.0 C2)")
    cv, err = _load_json(d / rec["coverage"]["file"])
    if err:
        fails.append(f"C23 records: {err} (the coverage record)")
    else:
        gone = [k for k in rec["coverage"]["fields"] if k not in cv]
        if gone:
            fails.append(f"C23 records: coverage lacks {gone}")
        for k in ("hits_by_family", "c1c2_by_family"):
            have = cv.get(k)
            if not isinstance(have, dict) or sorted(have) != sorted(fam):
                fails.append(f"C23 records: coverage.{k} must hold a count for each of the {len(fam)} source types {fam[0]}-{fam[-1]} "
                             f"(got {sorted(have) if isinstance(have, dict) else have})")
        att = cv.get("attempted")
        if not isinstance(att, list) or cv.get("families_attempted") != len(att) or cv.get("families_total") != len(fam):
            fails.append(f"C23 records: coverage.families_attempted ({cv.get('families_attempted')}) must be the length of coverage.attempted "
                         f"({att}) and families_total {len(fam)}")
        live = [c for c in claims if not c.get("exclusion_hit")]
        if isinstance(cv.get("hits_by_family"), dict) and claims:
            for f in fam:
                got = sum(1 for c in live if c.get("family") == f)
                if cv["hits_by_family"].get(f) != got:
                    fails.append(f"C23 records: coverage.hits_by_family.{f} is {cv['hits_by_family'].get(f)}; claims.jsonl holds {got}")
                    break
        if isinstance(cv.get("c1c2_by_family"), dict) and claims:
            for f in fam:
                got = sum(1 for c in live if c.get("family") == f and c.get("confidence") in ("C1", "C2"))
                if cv["c1c2_by_family"].get(f) != got:
                    fails.append(f"C23 records: coverage.c1c2_by_family.{f} is {cv['c1c2_by_family'].get(f)}; claims.jsonl holds {got}")
                    break
        if claims:
            if cv.get("excluded") != sum(1 for c in claims if c.get("exclusion_hit")):
                fails.append(f"C23 records: coverage.excluded is {cv.get('excluded')}; claims.jsonl marks "
                             f"{sum(1 for c in claims if c.get('exclusion_hit'))} as an exclusion hit")
            need = R["research"]["full_threshold"][depth]
            enough = sum(1 for f in fam if sum(1 for c in live if c.get("family") == f and c.get("confidence") in ("C1", "C2")) >= 1)
            want = "FULL" if enough >= need else "LIMITED"
            if cv.get("status") not in ("FULL", "LIMITED") or cv.get("status") != want:
                fails.append(f"C23 records: coverage.status is '{cv.get('status')}'; {enough} source types hold a C1 or C2 claim, a {depth} run needs {need}: {want}")
        if not isinstance(cv.get("rounds"), list) or not cv.get("rounds"):
            fails.append("C23 records: coverage.rounds must list each round with the queries it sent")
        else:
            need_r = battery_floor(depth)[0]
            have_r = [r.get("round") for r in cv["rounds"] if isinstance(r, dict) and r.get("queries")]
            if [x for x in need_r if x not in have_r]:
                fails.append(f"C23 records: coverage.rounds lacks rounds {[x for x in need_r if x not in have_r]}")
            sent = sum(len(r.get("queries", [])) for r in cv["rounds"] if isinstance(r, dict))
            bq = cv.get("base") if isinstance(cv.get("base"), dict) else {}
            nb = sum(len(v) for v in bq.values() if isinstance(v, list))
            lacking = [f["id"] for f in base_families(depth) if not bq.get(f["id"])]
            if lacking:
                fails.append(f"C23 records: coverage.base lacks the base-pass queries of {lacking}; each source type the depth enables is searched with its own template (S2-9)")
            if cv.get("searches") != sent + nb:
                fails.append(f"C23 records: coverage.searches is {cv.get('searches')}; its base lists {nb} queries and its rounds {sent}")
        if brief:
            m = re.search(r"(\d+)\s+of\s+(\d+)\s+source types", brief, re.I)
            if m and cv.get("families_attempted") is not None and int(m.group(1)) != cv.get("families_attempted"):
                fails.append(f"C23 records: the brief says {m.group(1)} of {m.group(2)} source types; coverage.families_attempted is {cv.get('families_attempted')}")
            st = re.search(r"\b(FULL|LIMITED)\b", brief)
            if st and cv.get("status") and st.group(1) != cv["status"]:
                fails.append(f"C23 records: the brief says {st.group(1)}; coverage.status is {cv['status']}")
    rd, err = _load_json(d / rec["read"]["file"])
    if err:
        fails.append(f"C23 records: {err} (the behavioral record)")
    else:
        rows = rd.get("dimensions") if isinstance(rd, dict) else rd
        rows = rows if isinstance(rows, list) else []
        dims = {x["id"]: x for x in R["rubric"]["dimensions"]}
        have = [r.get("dimension") for r in rows if isinstance(r, dict)]
        if sorted(have) != sorted(dims):
            fails.append(f"C23 records: read.json must hold exactly the six dimensions {sorted(dims)} (got {sorted(h for h in have if h)})")
        tiers = R["rubric"]["tiers"]
        cids = {c.get("id") for c in claims}
        got_tiers = []
        for r in rows:
            if not isinstance(r, dict):
                continue
            dim = r.get("dimension", "?")
            gone = [k for k in rec["read"]["fields"] if k not in r]
            if gone:
                fails.append(f"C23 records: read.json {dim} lacks {gone}"); continue
            band, tier, obs = r["band"], r["evidence_tier"], r["observation_ids"]
            if band not in rec["read"]["bands"] or tier not in tiers:
                fails.append(f"C23 records: read.json {dim} has band '{band}', tier '{tier}'; bands {rec['read']['bands']}, tiers {list(tiers)}"); continue
            want = "No read" if band == "no read" else dims.get(dim, {}).get("meaning", {}).get(band)
            if want and r["meeting_meaning"] != want:
                fails.append(f"C23 records: read.json {dim} meeting_meaning is not the rubric's '{want[:40]}...' for band {band} (S3-3: word for word)")
            if band == "no read" and (obs or tier != "low"):
                fails.append(f"C23 records: read.json {dim} is no read, so tier low and no observation_ids")
            if band != "no read" and len(obs) < tiers[tier]["min_observations"]:
                fails.append(f"C23 records: read.json {dim} is tier {tier}, which needs {tiers[tier]['min_observations']} observations; it lists {len(obs)}")
            if claims and [o for o in obs if o not in cids]:
                fails.append(f"C23 records: read.json {dim} cites observation ids {[o for o in obs if o not in cids]} that claims.jsonl does not hold")
            got_tiers.append(tier)
        if len(got_tiers) == 6:
            rank = {"low": 0, "medium": 1, "high": 2}
            overall = max((t for t in rank if sum(1 for g in got_tiers if rank[g] >= rank[t]) >= 3), key=lambda t: rank[t], default="low")
            m = re.search(r"Evidence tier:\**\s*(high|medium|low)", brief, re.I)
            if m and m.group(1).lower() != overall:
                fails.append(f"C23 records: the brief's Evidence tier is {m.group(1).lower()}; read.json gives {overall} (S3-2: the highest tier at least three dimensions reach)")
    return fails


# ---------------------------------------------------------------- kept facts (C24): cut wording, never facts ------
def ledger_facts(md):
    """The cited facts of a brief: one per ledger row, grouped by the page it cites (a file name for the user's own files) and the row's
    date. Rows from one page and day are counted, not merged: three facts from one podcast are three facts."""
    out = {}
    for m in SRC_ROW.finditer(md):
        src = m.group(3)
        u = re.search(r"\]\((https?://[^)\s]+)", src) or re.search(r"(https?://[^\s|)]+)", src)
        key = (_page(u.group(1)) if u else re.sub(r"\s+", " ", re.sub(r"[\[\]*]", "", src.split(" · ")[0])).strip().lower(), m.group(5))
        out.setdefault(key, []).append(dict(n=int(m.group(1)), what=m.group(2)))
    return out


def count_facts(md):
    return sum(len(v) for v in ledger_facts(md).values())


ALLOW = re.compile(r"^\s*(\d+)\s*=\s*(dead|excluded)\s*$")   # --allow N=dead | N=excluded: one fact of the draft's ledger, one reason
DRAFT_LOCK = "draft.lock.json"


def _row_url(md, n):
    """The full link of ledger row [n], or '' (your request, your file)."""
    for m in SRC_ROW.finditer(md):
        if int(m.group(1)) == n:
            u = re.search(r"\]\((https?://[^)\s]+)", m.group(3)) or re.search(r"(https?://[^\s|)]+)", m.group(3))
            return u.group(1) if u else ""
    return ""


def _allowed(allow, facts, final_pages, status=None, excluded=None):
    """Read --allow N=dead|excluded against the draft's facts {n: (page, url, text)}. dead: the page is cited nowhere in the final and
    does not answer (eval.py links: 404, 410, 5xx or no answer; a page that answers, or refuses bots, keeps its fact, S2-8); excluded:
    the fact trips an exclusion keyword (C9) or its claim carries exclusion_hit. Anything else -- a page, a URL, a reason such as fit --
    excuses nothing. Returns (allowed {n: reason}, failures)."""
    ok, fails = {}, []
    status = status or link_status
    for x in allow:
        m = ALLOW.match(str(x))
        if not m:
            fails.append(f"C24 kept: --allow '{str(x)[:70]}' excuses nothing: name one fact of the draft and why it was dropped, "
                         "--allow N=dead or N=excluded (N its number in the draft's ledger); a page, a URL or fit is never a reason (S4-4)")
            continue
        n, why = int(m.group(1)), m.group(2)
        if n not in facts:
            fails.append(f"C24 kept: --allow {n}={why}: the draft's ledger has no fact [{n}]"); continue
        page, url, text = facts[n]
        if why == "dead":
            if not url:
                fails.append(f"C24 kept: --allow {n}=dead: [{n}] '{text[:40]}' has no link to go dead (your request or your file)"); continue
            if page in final_pages:
                fails.append(f"C24 kept: --allow {n}=dead: [{n}] '{text[:40]}': its page {page} is still cited in the final brief, so it is not dead"); continue
            u, code, kind = status([url])[0]
            if kind != "dead":
                fails.append(f"C24 kept: --allow {n}=dead: [{n}] '{text[:40]}': {page} answers ({code}, {kind}); a page that answers or "
                             "refuses bots keeps its fact (S2-8)"); continue
        elif not (exclusion_hits(text) or (excluded and excluded(n))):
            fails.append(f"C24 kept: --allow {n}=excluded: [{n}] '{text[:40]}' touches no excluded topic (C9) and its claim has no exclusion_hit"); continue
        ok[n] = why
    return ok, fails


def kept_check(draft_md, final_md, allow=(), draft_script="", final_script="", status=None, told=None):
    """C24: a fit pass cuts wording, never cited facts (the Codex run, Oct 16: 23 cited facts cut to 18 to fit 3 pages; the Claude desktop
    run, Oct 17: 27 cut to 18, every cut excused with --allow <page>). Every ledger row of the first complete draft is still a ledger
    row of the final brief (counted per page and date) and still cited in a sentence there. --allow N=dead|excluded names one draft fact
    dropped for that reason (checked, see _allowed) and told to the user; nothing else excuses a cut. Returns the failures."""
    a, b = ledger_facts(draft_md), ledger_facts(final_md)
    facts = {r["n"]: (k[0], _row_url(draft_md, r["n"]), r["what"]) for k, rows in a.items() for r in rows}
    ok, fails = _allowed(allow, facts, {k[0] for k in b}, status)
    if told is not None:
        told += [f"[{n}] {facts[n][2][:40]} ({why})" for n, why in sorted(ok.items())]
    lost = []
    for k, rows in a.items():
        gone = len(rows) - len(b.get(k, [])) - sum(1 for r in rows if r["n"] in ok)
        if gone > 0:
            lost += [(k, r) for r in [r for r in rows if r["n"] not in ok][-gone:]]
    if lost:
        fails.append(f"C24 kept: {len(lost)} of the draft's {count_facts(draft_md)} cited facts are gone from the final brief ({count_facts(final_md)} remain): "
                     + "; ".join(f"[{v['n']}] {v['what'][:40]} ({k[0]})" for k, v in lost[:4])
                     + (" ..." if len(lost) > 4 else "") + " -- cut wording, never facts; a fact that will not fit keeps its ledger row and a "
                     "short cited mention (S4-4); redo the fit")
    def cited_in(brief, script):
        secs, cited = _sections(brief + "\n" + script), set()
        for k in _body_ids(secs):
            cited |= {int(n) for n in CITE.findall(secs[k])}
        return cited
    before, cited = cited_in(draft_md, draft_script), cited_in(final_md, final_script)   # the script cites facts too (P1 Credibility, P9 Next step)
    silent = [r["n"] for k, rows in b.items() for r in rows if k in a and r["n"] in before and r["n"] not in cited]
    if silent:
        fails.append(f"C24 kept: facts {silent} are still in the ledger but no sentence cites them any more; the fact was cut, not the wording")
    return fails


def record_draft(folder, brief, script, order, depth):
    """The first complete draft, taken by eval.py assemble the first time it builds the brief -- so it is always taken before any fit
    pass, whatever order the run works in: brief.draft.md, script.draft.md and draft.lock.json (their sha256, the time, the depth and
    the ledger's claim ids). Never rewritten: a later build is held to it by eval.py kept <folder>. Returns a line for the run's log."""
    import hashlib
    d = pathlib.Path(folder)
    lock = d / DRAFT_LOCK
    if lock.exists():
        j = json.loads(lock.read_text())
        return f"first draft: {len(j.get('facts', []))} cited facts (recorded {j.get('taken')}); this build: {len(order)}; eval.py kept {folder} compares them"
    (d / "brief.draft.md").write_text(brief); (d / "script.draft.md").write_text(script)
    sha = lambda t: hashlib.sha256(t.encode()).hexdigest()
    w = d / "draft.wanted.json"
    wanted = [c for c in (json.loads(w.read_text()) if w.exists() else []) if c not in order]   # cited by a first build that did not fit
    lock.write_text(json.dumps({"taken": dt.datetime.now().isoformat(timespec="seconds"), "depth": depth, "facts": list(order), "not_held": wanted,
                                "brief_sha256": sha(brief), "script_sha256": sha(script)}, indent=1) + "\n")
    return f"first complete draft recorded: {len(order)} cited facts ({DRAFT_LOCK}, brief.draft.md, script.draft.md); every later build is held to it (eval.py kept {folder})"


def trial_fit(brief, script, fj):
    """The first build rendered once, as the run renders it (format/talyx_pdf.py --style brief, 2 + 1 pages): the renderer's report
    ({'ok': ..., 'longest_sections': ...}), or None where it cannot render (no browser engine: the in-chat path, S4-10)."""
    tool = HERE / "format" / "talyx_pdf.py"
    if not tool.exists():
        return None
    pb, t = R["page_budget"], fj.get("target") or {}
    with tempfile.TemporaryDirectory() as td:
        b, sc = pathlib.Path(td, "brief.md"), pathlib.Path(td, "script.md")
        b.write_text(brief); sc.write_text(script)
        try:
            r = subprocess.run([sys.executable, str(tool), "--style", "brief", "--brief", str(b), "--script", str(sc), "--columns", pb["columns"],
                                "--classification", R["names"]["classification"], "--footer", f"{R['names']['deliverable']} · {t.get('name', '')}, {t.get('org', '')}",
                                "--brief-pages", str(pb["brief_pages"]), "--max-pages", str(pb["total_pages"]), "--out", str(pathlib.Path(td, "trial.pdf"))],
                               capture_output=True, text=True, timeout=300)
            return json.loads(r.stdout.strip().splitlines()[-1])
        except (subprocess.SubprocessError, ValueError, IndexError):
            return None


def build(folder, profile=None, depth=None, render=True):
    """`eval.py assemble <folder>`: build brief.md and script.md from fields.json and the records. The first build of a folder is its
    first complete draft (record_draft): it is rendered once first, and only a build whose 3 pages fit is recorded, because nothing in it
    may be cut afterwards. A first build that does not fit writes nothing; the facts it cited are kept in draft.wanted.json, so the run can
    name the ones the page could not hold. Returns (lines to print, exit code)."""
    d = pathlib.Path(folder)
    brief, script, probs, order = assemble(d, profile, depth, want_order=True)
    if probs:
        return [f"assemble {folder}: {len(probs)} problems; fix fields.json, then run again", *[" - " + x for x in probs]], 1
    depth = depth or _answers(profile).get("Q5") or "standard"
    if not (d / DRAFT_LOCK).exists() and render:
        fit = trial_fit(brief, script, _load_json(d / "fields.json")[0] or {})
        if fit is not None and fit.get("ok") is False:
            w = d / "draft.wanted.json"
            wanted = list(dict.fromkeys((json.loads(w.read_text()) if w.exists() else []) + list(order)))
            w.write_text(json.dumps(wanted) + "\n")
            return [f"assemble {folder}: the first build does not fit the {R['page_budget']['total_pages']} pages ({fit.get('reason', '')}; longest: "
                    + ", ".join(f"{n} {w_} words" for w_, n in (fit.get("longest_sections") or [])[:4]) + "); nothing written, no draft recorded",
                    f" - cut wording first, in the S4-4 order; if the ledger (one line per fact, {len(order)} now) still overflows, cite fewer facts, "
                    "the strongest first, and name the ones left out to the user (kept in draft.wanted.json): every fact of the recorded draft stays to the end"], 1
    (d / "brief.md").write_text(brief); (d / "script.md").write_text(script)
    f = schema_check(brief, script) + grading_check(brief)
    out = [f"assembled {folder}/brief.md and script.md; schema and grading: {len(f)} failures", *[" - " + x for x in f], record_draft(d, brief, script, order, depth)]
    return out, 1 if f else 0


def kept_folder(folder, allow=(), profile=None, status=None):
    """C24 on a run folder: the draft eval.py assemble recorded (draft.lock.json, its files unchanged) against the brief fields.json
    builds now, fact by fact (claim ids, so renumbering or a reworded 'What it says' cell hides nothing). Returns (failures, summary)."""
    import hashlib
    d = pathlib.Path(folder)
    lock = d / DRAFT_LOCK
    if not lock.exists():
        return [f"C24 kept: {folder} has no {DRAFT_LOCK}: eval.py assemble records the first complete draft the first time it builds the "
                "brief; it cannot be recorded later, so this run cannot show that no fact was cut"], "no recorded draft"
    j = json.loads(lock.read_text())
    sha = lambda t: hashlib.sha256(t.encode()).hexdigest()
    fails = []
    draft_md = (d / "brief.draft.md").read_text() if (d / "brief.draft.md").exists() else ""
    draft_sc = (d / "script.draft.md").read_text() if (d / "script.draft.md").exists() else ""
    if sha(draft_md) != j.get("brief_sha256") or sha(draft_sc) != j.get("script_sha256"):
        fails.append(f"C24 kept: brief.draft.md or script.draft.md is not the draft eval.py assemble recorded at {j.get('taken')} (changed or replaced)")
    brief, script, probs, order = assemble(d, profile, j.get("depth"), want_order=True)
    if probs:
        return fails + [f"C24 kept: fields.json does not assemble ({probs[0]})"], "no final"
    on_disk = ((d / "brief.md").read_text() if (d / "brief.md").exists() else "", (d / "script.md").read_text() if (d / "script.md").exists() else "")
    if on_disk != (brief, script):
        fails.append("C24 kept: brief.md and script.md are not what eval.py assemble builds from fields.json now (C26): assemble, then run kept")
    claims = {}
    for ln in (d / R["records"]["claims"]["file"]).read_text().splitlines():
        if ln.strip():
            c = json.loads(ln); claims[c["id"]] = c
    draft = list(j.get("facts", []))
    url = lambda cid: str(claims.get(cid, {}).get("url", ""))
    facts = {i: (_page(url(cid)) if url(cid).startswith("http") else url(cid).lower(), url(cid) if url(cid).startswith("http") else "",
                 f"{claims.get(cid, {}).get('says', '')} {claims.get(cid, {}).get('claim', '')}") for i, cid in enumerate(draft, 1)}
    final_pages = {_page(url(cid)) for cid in order if url(cid).startswith("http")}
    ok, af = _allowed(allow, facts, final_pages, status, excluded=lambda n: bool(claims.get(draft[n - 1], {}).get("exclusion_hit")))
    fails += af
    lost = [(i, cid) for i, cid in enumerate(draft, 1) if cid not in order and i not in ok]
    if lost:
        fails.append(f"C24 kept: {len(lost)} of the draft's {len(draft)} cited facts are gone from the final brief ({len(order)} cited now): "
                     + "; ".join(f"[{i}] {claims.get(cid, {}).get('says', '')[:40]} (claim {cid})" for i, cid in lost[:10])
                     + (" ..." if len(lost) > 10 else "") + " -- cut wording, never facts; a fact that will not fit keeps its ledger row and "
                     "a short cited mention (S4-4); redo the fit")
    kept = sum(1 for cid in draft if cid in order)
    told = "; ".join(f"[{n}] {facts[n][2].strip()[:40]} ({why})" for n, why in sorted(ok.items()))
    held = [claims.get(c, {}).get("says", f"claim {c}") for c in j.get("not_held", [])]
    return fails, (f"draft {len(draft)} cited facts (recorded {j.get('taken')}), final {len(order)}; {kept} of {len(draft)} kept"
                   + (f"; dropped with a reason the user is told: {told}" if told else "")
                   + (f"; the page could not hold {len(held)} more, named to the user: {'; '.join(held)}" if held else ""))


def effective_conf(c):
    """The strength a claim may print: its own confidence, capped by the weakest of the caps in pcp.yaml grading.caps (a weak
    domain, how it was found, its grade). Weak sources never read as strong, whatever the writer thought of them."""
    g, ranks = R["grading"], ["C1", "C2", "C3", "C4"]
    caps = [c.get("confidence") if c.get("confidence") in ranks else "C3"]
    u = str(c.get("url", ""))
    d = _domain(u) if u.startswith("http") else ""
    if d and any(d == w or d.endswith("." + w) for w in R.get("source_quality", {}).get("weak", [])):
        caps.append(g["caps"]["weak_domain"])
    caps.append(g["caps"]["tag"].get(c.get("tag")))
    caps.append(g["caps"]["grade"].get(c.get("grade")))
    return max((x for x in caps if x in ranks), key=ranks.index)


# ---------------------------------------------------------------- assemble (C26): the brief is built, never written -------
# The model fills fields.json (text per field of pcp.yaml `forms`, claims cited as [c<id>]); this builds brief.md and script.md
# from the forms table, claims.jsonl, coverage.json, read.json and the saved profile: the same structure every run.
CLAIM_REF = re.compile(r"\[c(\d+)\]")
MON = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


def _fmt_date(s, read_day=""):
    """A claim's published date as the ledger prints it; an undated source prints 'seen <day it was read>'."""
    m = re.match(r"(\d{4})-(\d{2})(?:-(\d{2}))?", str(s or ""))
    if m:
        mo = MON[int(m.group(2)) - 1]
        return f"{mo} {int(m.group(3))}, {m.group(1)}" if m.group(3) else f"{mo} {m.group(1)}"
    m = re.match(r"(\d{4})-(\d{2})-(\d{2})", str(read_day or ""))
    return f"seen {MON[int(m.group(2)) - 1]} {int(m.group(3))}, {m.group(1)}" if m else "seen"


def _answers(profile):
    """The saved answers {Qn: value}: the first named profile of ~/.pcp/profile.yaml."""
    pr = profile or {}
    first = next(iter((pr.get("profiles") or {}).values()), {}) if isinstance(pr, dict) else {}
    return {k: (v.get("value") if isinstance(v, dict) else v) for k, v in (first.get("answers") or {}).items()}


def _label_of(qid, value):
    q = next((x for x in R["calibration"]["questions"] if x["id"] == qid), {})
    o = next((x for x in q.get("options", []) if x["value"] == value), None)
    return re.sub(r"\s*\(Recommended\)", "", o["label"]) if o else str(value or "")


def assemble(folder, profile=None, depth=None, want_order=False):
    """Build brief.md and script.md in `folder` from fields.json + the three records + the profile. Returns (brief, script, problems),
    and with want_order the ledger's claim ids in order (C24 compares facts by claim, so renumbering or a reworded cell hides nothing).
    Problems are missing fields, unknown claim ids and uncited text where a form demands a citation: the run fixes fields.json, never
    the output."""
    d, F = pathlib.Path(folder), R["forms"]
    probs = []
    fj, err = _load_json(d / "fields.json")
    if err:
        return ("", "", [f"C26 assemble: {err}"]) + (([],) if want_order else ())
    claims = {}
    for ln in (d / R["records"]["claims"]["file"]).read_text().splitlines():
        if ln.strip():
            c = json.loads(ln)
            claims[c["id"]] = c
    cov, _ = _load_json(d / R["records"]["coverage"]["file"])
    cov = cov or {}
    rd, _ = _load_json(d / R["records"]["read"]["file"])
    rows = (rd.get("dimensions") if isinstance(rd, dict) else rd) or []
    ans = _answers(profile)
    depth = depth or ans.get("Q5") or "standard"
    authority = {"principal": "high", "investor": "high"}.get(ans.get("Q1"), "medium")
    order = []   # claim ids by first use in the page: the ledger's numbers
    num = lambda cid: order.index(cid) + 1

    def cite(text, key, where):
        def sub(m):
            cid = int(m.group(1))
            if cid not in claims or claims[cid].get("exclusion_hit"):
                probs.append(f"C26 assemble: {where} cites [c{cid}], which is not a usable claim in claims.jsonl")
                return "[?]"
            if cid not in order:
                order.append(cid)
            return f"[{num(cid)}]"
        return CLAIM_REF.sub(sub, str(text or "").strip())

    def field(src, f, where, optional=False):
        v = (src or {}).get(f["key"])
        if isinstance(v, list) and f.get("list"):
            v = f["list"].join(str(x).strip().rstrip(".") for x in v if str(x).strip())
        v = str(v or "").strip()
        if not v:
            if f.get("optional") or optional:
                return None
            if f.get("missing"):
                return f["missing"]
            probs.append(f"C26 assemble: {where} needs '{f['key']}'")
            return ""
        out = cite(v, f["key"], f"{where}.{f['key']}")
        if f.get("cite") and not CLAIM_REF.search(v) and out != f.get("missing"):
            probs.append(f"C26 assemble: {where}.{f['key']} cites no claim ([c<id>])")
        return out

    def bullets(block, spec_fields):
        out = []
        for f in spec_fields:
            txt = "" if f.get("auto") else field(fj.get(block.lower()), f, block)
            if txt is None:
                continue
            if f.get("italic"):
                txt = f"*{txt}*"
            line = f"- **{f['label']}** {txt}"
            if f.get("auto"):   # P4: the ask and its fallback are B9's, word for word
                src, key = f["auto"].split(".")
                a = (fj.get(src.lower()) or {}).get("ask")
                line = f"- **{f['label']}** {cite(a, key, src).rstrip('. ')}"
            if f.get("join"):
                j = f["join"]
                fb = (fj.get(j["auto"].split(".")[0].lower()) or {}).get(j["key"]) if j.get("auto") else (fj.get(block.lower()) or {}).get(j["key"])
                if fb:
                    line += f"{j['sep']}**{j['label']}** {cite(fb, j['key'], block)}"
            out.append(line)
        return out

    # ---- tier, conditions
    rank = {"low": 0, "medium": 1, "high": 2}
    tiers = [r.get("evidence_tier", "low") for r in rows if isinstance(r, dict)]
    tier = max((t for t in rank if sum(1 for g in tiers if rank[g] >= rank[t]) >= 3), key=lambda t: rank[t], default="low")
    # ---- the blocks, in the registry's order
    B = {}
    f1 = F["B1"]; b1 = fj.get("b1") or {}
    B["B1"] = " ".join(f"**{f['label']}** {field(b1, f, 'B1')}" for f in f1["fields"])
    f2 = F["B2"]; qs = fj.get("b2") or []
    if not f2["count"][0] <= len(qs) <= f2["count"][1]:
        probs.append(f"C26 assemble: B2 needs {f2['count'][0]} to {f2['count'][1]} questions (got {len(qs)})")
    lines = []
    for i, q in enumerate(qs, 1):
        qf, df, af = f2["item"]
        lines.append(f"{i}. {field(q, qf, f'B2.{i}')}")
        lines.append(f"   - **{df['label']}** {str(q.get('decides', '')).strip().rstrip('.')}. **{af['label']}** {str(q.get('ask', '')).strip().rstrip('.')}.")
    B["B2"] = "\n".join(lines)
    B["B3"] = "\n".join(bullets("B3", F["B3"]["fields"]))
    f4 = F["B4"]; b4 = fj.get("b4") or {}
    qlines = []
    for q in b4.get("quotes") or []:
        qlines.append(f"- **{str(q.get('label', '')).strip().rstrip(':')}:** \"{str(q.get('quote', '')).strip().strip(chr(34))}\" {cite(q.get('cite', ''), 'cite', 'B4')}".rstrip())
    if not qlines:
        qlines = [f"- {field(b4, {'key': f4['themes_key'], 'cite': True, 'missing': f4['none']}, 'B4')}"]
    li = cov.get("linkedin") or "not read"
    B["B4"] = "\n".join(qlines) + "\n\n" + f4["linkedin"].format(status=li if li.startswith(("read", "not read")) else f"read from {li}")
    f5 = F["B5"]; b5 = fj.get("b5") or []
    t5 = [f"| {f5['header'][0]} | {f5['header'][1]} |", "|---|---|"]
    for i, rf in enumerate(f5["rows"]):
        r = b5[i] if i < len(b5) else {}
        t5.append(f"| {field(r, {'key': 'observable', 'cite': True}, f'B5.{rf['key']}')} | {str(r.get('action', '')).strip()} |")
    B["B5"] = "\n".join(t5)
    f6 = F["B6"]; b6 = fj.get("b6") or {}
    t6 = [f"| {f6['header'][0]} | {f6['header'][1]} |", "|---|---|"]
    for dim in R["rubric"]["dimensions"]:
        r = next((x for x in rows if isinstance(x, dict) and x.get("dimension") == dim["id"]), {})
        if not r or r.get("band") == "no read":
            t6.append(f"| {dim['shows']} | {f6['none']} |")
        else:
            t6.append(f"| {dim['shows']}: {field(b6, {'key': dim['id'], 'cite': True}, 'B6')} | {dim['meaning'][r['band']]} |")
    B["B6"] = "\n".join(t6) + "\n\n" + f6["tier"].format(tier=tier)
    B["B7"] = "\n".join(bullets("B7", F["B7"]["fields"]))
    f8 = F["B8"]; b8 = fj.get("b8") or {}
    cl = []
    for i, it in enumerate((b8.get("against") or [])[:f8["max"]]):
        a, rv = f8["item"]
        cl.append(f"- **{a['label']}** {field(it, a, f'B8.{i + 1}')} **{rv['label']}** {str(it.get(rv['key'], '')).strip()}")
    conf = str(b8.get(f8["confirm"]["key"]) or "").strip()
    if conf:
        cl.append(f"- **{f8['confirm']['label']}** {f8['confirm']['marker']} {cite(conf, 'confirm_first', 'B8')}")
    if not cl:
        cl = [f"- {f8['none']}"]
    if depth == "deep":
        h = f8["hypotheses"]; hy = b8.get("hypotheses") or []
        cl += ["", f"### {h['head']}", f"| {h['header'][0]} | {h['header'][1]} |", "|---|---|"]
        cl += [f"| {cite(x.get('hypothesis', ''), 'hypothesis', 'B8')} | {cite(x.get('test', ''), 'test', 'B8')} |" for x in hy[:h['max']]]
    B["B8"] = "\n".join(cl)
    f9 = F["B9"]; b9 = fj.get("b9") or {}
    nl = []
    for sec in f9["sections"]:
        nl.append(f"### {sec['head']}")
        for f in sec["fields"]:
            txt = field(b9, f, "B9", optional=True)
            if txt is None:
                continue
            line = f"- **{f['label']}** {txt.rstrip('. ') if f.get('join') else txt}"
            if f.get("join") and b9.get(f["join"]["key"]):
                line += f"{f['join']['sep']}**{f['join']['label']}** {cite(b9[f['join']['key']], f['join']['key'], 'B9')}"
            nl.append(line)
    B["B9"] = "\n".join(nl)
    # ---- page 3
    S = {}
    S["P1"] = "\n".join(bullets("P1", F["P1"]["fields"]))
    f2p = F["P2"]; p2 = fj.get("p2") or {}
    bl = [f"- **{f2p['beats']['label']}** {cite(x, 'beats', 'P2')}" for x in (p2.get("beats") or [])]
    ordr = p2.get("order") or {}
    for lab in f2p["order"]:
        i = ordr.get(lab.lower())
        if isinstance(i, int) and 1 <= i <= len(qs):
            bl.append(f"- **{lab}:** {field(qs[i - 1], {'key': 'q', 'cite': True}, 'P2')}")
        else:
            probs.append(f"C26 assemble: P2.order needs '{lab.lower()}': the number of the B2 question that goes there")
    S["P2"] = "\n".join(bl)
    f3 = F["P3"]; ob = fj.get("p3") or []
    if len(ob) != f3["count"]:
        probs.append(f"C26 assemble: P3 needs {f3['count']} objections (got {len(ob)})")
    S["P3"] = "\n".join(f"- **\"{str(o.get('objection', '')).strip().strip(chr(34))}\":** *{field(o, f3['item'][1], 'P3')}*" for o in ob)
    S["P4"] = "\n".join(bullets("P4", F["P4"]["fields"]))
    S["P5"] = "\n".join(bullets("P5", F["P5"]["fields"])) if rank[tier] >= 1 else ""
    S["P6"] = "\n".join(bullets("P6", F["P6"]["fields"])) if tier == "high" and authority == "high" else ""
    cap6 = next(b for b in R["script"]["blocks"] if b["id"] == "P6").get("max_moves")
    if cap6 and len([ln for ln in S["P6"].splitlines() if ln.lstrip().startswith("- ")]) > cap6:
        probs.append(f"C26 assemble: P6 fills {len([ln for ln in S['P6'].splitlines() if ln.lstrip().startswith('- ')])} principles; at most {cap6} moves, each from a B6 meaning")
    f7 = F["P7"]; mv = (fj.get("p7") or {}).get(f7["key"]) or []
    if not f7["count"][0] <= len(mv) <= f7["count"][1]:
        probs.append(f"C26 assemble: P7 needs {f7['count'][0]} to {f7['count'][1]} moves (got {len(mv)})")
    S["P7"] = "\n".join(f"- **{f7['label']}** {cite(m, 'moves', 'P7')}" for m in mv)
    f8p = F["P8"]; p8 = fj.get("p8") or {}
    dom = ans.get("Q2") or "general"
    never = [f'"{x}"' for x in R["guardrails"]["never_say"]] + [f'"{x}"' for x in R["guardrails"]["forbidden_claims_by_domain"].get(dom, [])]
    S["P8"] = f"- **{f8p['rule']['label']}** {str(p8.get('rule', '')).strip()}\n- **{f8p['never']['label']}** {f8p['never']['sep'].join(never)}"
    S["P9"] = f"**{F['P9']['label']}** {field(fj.get('p9'), {'key': F['P9']['key'], 'cite': True}, 'P9')}"
    # ---- the ledger, numbered by first use
    for c in claims.values():
        pass
    facts = len(order)
    status = cov.get("status", "LIMITED")
    att, tot = cov.get("families_attempted", 0), cov.get("families_total", len(R["families"]))
    f10 = F["B10"]
    led = [f10["note"].format(cited=facts, status=status, attempted=att, total=tot, key=" · ".join(R["grading"]["strength"].values())), "",
           "| " + " | ".join(f10["header"]) + " |", "|" + "---|" * len(f10["header"])]
    for i, cid in enumerate(order, 1):
        c = claims[cid]
        if len(str(c.get("says") or "")) > f10["says_max_chars"]:
            probs.append(f"C26 assemble: claim {cid}'s 'says' is {len(c['says'])} characters; the ledger row is one line, at most {f10['says_max_chars']}")
        url = str(c.get("url", ""))
        tag = c.get("tag", "Direct")
        if url.startswith("http"):
            dom_ = _domain(url)
            label = f"{dom_}, search result" if tag == "LinkedIn" and c.get("page", "") in ("", "search result") else dom_
            src = f"[{label}]({url}) · {tag}"
        else:
            src = f"{url} · {tag}"
        stren = R["grading"]["words"][effective_conf(c)]
        led.append(f"| [{i}] | {c.get('says') or c.get('claim', '')} | {src} | {c.get('grade', 'Measured')} · {stren} | {_fmt_date(c.get('published'), c.get('retrieved_at'))} |")
    nf = [f["name"] for f in R["families"] if not cov.get("hits_by_family", {}).get(f["id"])]
    need = battery_floor(depth)[0]
    rr = [r for r in cov.get("rounds", []) if isinstance(r, dict) and r.get("queries") and r.get("round") in need]   # a gap fill counts in N, not M (S2-9)
    so = (fj.get("still_open") or [])[:f10["still_open_max"]]
    day = str(fj.get("prepared", ""))
    run = (f"{day} · {depth} · {str(fj.get('meeting', '')).split(':')[0].lower()} · {_label_of('Q1', ans.get('Q1')).lower()} · {_label_of('Q2', ans.get('Q2')).lower()}"
           f" · {_label_of('Q7', ans.get('Q7'))} · {status} · {round(facts / R['page_budget']['total_pages'], 2)} decision-useful facts per page"
           f" · {cov.get('searches', 0)} searches ({sum(len(v) for v in (cov.get('base') or {}).values())} base) in {len(rr)} rounds")
    grid = ["| | |", "|---|---|",
            f"| **{f10['grid'][0]}** | {att} of {tot} source types in the base pass · rounds {len(rr)} of {len(need)}"
            + (f" · Not found: {', '.join(nf)}" if nf else "") + f" · LinkedIn: {li if li.startswith(('read', 'not read')) else 'read from ' + li} |",
            f"| **{f10['grid'][1]}** | " + " · ".join(f"{x['label']}: {x['question']}" for x in so) + " |",
            f"| **{f10['grid'][2]}** | {', '.join(R['exclusions']['printed'])} |",
            f"| **{f10['grid'][3]}** | {run} |"]
    B["B10"] = "\n".join(led) + "\n\n" + "\n".join(grid)
    # ---- the masthead and the pages
    t, m = fj.get("target") or {}, F["masthead"]
    city = f" | {t['city']}" if t.get("city") else ""
    head = [f"# {t.get('name', '')}", m["identity"].format(org=t.get("org", ""), role_since=t.get("role_since", ""), city=city),
            m["meta"].format(meeting=fj.get("meeting", ""), role=_label_of("Q1", ans.get("Q1")), depth=depth, attempted=att, total=tot,
                             cited=facts, status=status, date=day)]
    name = lambda s: fill_names(s)
    ids = [b["id"] for b in R["brief"]["sections"]]
    brief = "\n".join(head) + "\n\n" + "\n\n".join(f"## {b['id']} {fill_names(b['title'])}\n{B[b['id']]}" for b in R["brief"]["sections"]) + "\n"
    sc = R["script"]
    script = (f"# {fill_names(sc['title'])}\n*{sc['subtitle']} · {t.get('name', '')}, {t.get('org', '')} · Prepared {day}*\n\n"
              + "\n\n".join(f"## {b['id']} {fill_names(b['title'])}\n{S[b['id']]}" for b in sc["blocks"] if S.get(b["id"]).strip()) + "\n")
    # the ledger is one line per cited fact, so its length is set by how many facts the brief cites: over its budget (C6, +15%), the page
    # cannot hold them and a fit pass would have to cut facts. Choose the strongest facts before the first build (S4-4); nothing is cut after it.
    b10 = next(x for x in R["brief"]["sections"] if x["id"] == LEDGER)["words"]
    lw = len(WORD.findall(LINK_URL.sub("]", _sections(brief + "\n" + script).get(LEDGER, ""))))   # exactly as C6 counts it
    if order and lw > b10 * 1.15:
        probs.append(f"C26 assemble: the evidence ledger is {lw} words for {len(order)} cited facts, over its budget of {b10} (+15%): cite fewer facts in "
                     "fields.json before the first build, the strongest first -- every fact of the first build stays to the end (S4-4)")
    # the page's [n] numbers came from the text above: any block assembled before a later one numbered them in this order
    return (brief, script, probs, list(order)) if want_order else (brief, script, probs)


def fill_names(s):
    return re.sub(r"\{(deliverable|profile|script|collection)\}", lambda m: R["names"][m.group(1)], str(s))


# ---------------------------------------------------------------- grading on the page (C25) and the schema (C26) ---
def ledger_cells(md):
    """Every ledger row of a brief as its cells: n, says, source, grade cell, date."""
    sec = _sections(md).get(LEDGER, "")
    out = []
    for ln in sec.splitlines():
        m = re.match(r"^\|\s*\[(\d+)\]\s*\|(.*)\|\s*$", ln)
        if m:
            cells = [c.strip() for c in ln.strip().strip("|").split("|")]
            if len(cells) >= 5:
                out.append(dict(n=int(m.group(1)), says=cells[1], source=cells[2], grade=cells[3], date=cells[4]))
    return out


def grading_check(md):
    """C25: the source grade is on the page in plain words (Daniel, Oct 16): every ledger row has its grade (Measured, Derived,
    Inference, Not determined) AND how it was found (Direct, Search, LinkedIn, Yours) AND its strength in plain words
    (Strong: primary, dated ... Inferred); a weak domain never reads Strong or Solid. Briefs prepared before grading.since are
    exempt (the frozen targets)."""
    g = R["grading"]
    day = re.search(r"Prepared\s+([A-Z][a-z]{2} \d{1,2}, \d{4})", md)
    if day and _day(day.group(1)) < dt.date.fromisoformat(str(g["since"])):
        return []
    fails, strengths = [], list(g["words"].values())
    weak = R.get("source_quality", {}).get("weak", [])
    sec = _sections(md).get(LEDGER, "")
    if ledger_cells(md) and not all(v in sec for v in g["strength"].values()):
        fails.append("C25 grading: the ledger's note line must key the strengths: " + " · ".join(g["strength"].values()))
    for r in ledger_cells(md):
        grade, _, strength = r["grade"].partition(" · ")
        tag = r["source"].rsplit(" · ", 1)[-1].strip() if " · " in r["source"] else ""
        if grade.strip() not in GRADES.split("|"):
            fails.append(f"C25 grading: [{r['n']}] grade '{grade}' is not one of {GRADES}")
        if tag not in g["tags"]:
            fails.append(f"C25 grading: [{r['n']}] source '{r['source'][:40]}' lacks how it was found: ' · ' and one of {g['tags']}")
        if strength.strip() not in strengths:
            fails.append(f"C25 grading: [{r['n']}] has no source strength; the grade cell reads 'Measured · <one of {strengths}>'")
        u = re.search(r"\]\((https?://[^)\s]+)", r["source"])
        ranks = ["C1", "C2", "C3", "C4"]
        inv = {v: k for k, v in g["words"].items()}
        caps = [g["caps"]["tag"].get(tag), g["caps"]["grade"].get(grade.strip())]
        is_weak = bool(u) and any(_domain(u.group(1)) == w or _domain(u.group(1)).endswith("." + w) for w in weak)
        if is_weak:
            caps.append(g["caps"]["weak_domain"])
        cap = max((x for x in caps if x in ranks), key=ranks.index, default="C1")
        if strength.strip() in inv and ranks.index(inv[strength.strip()]) < ranks.index(cap):
            why = "a weak domain" if is_weak and cap == g["caps"]["weak_domain"] else f"tag {tag}, grade {grade.strip()}"
            fails.append(f"C25 grading: [{r['n']}] reads '{strength.strip()}' but {why} caps it at '{g['words'][cap]}'; a weak source never reads as strong")
        shown = re.match(r"\s*\[([^\]]*)\]\(https?://", r["source"])
        if u and g["source_link"] == "domain" and shown and shown.group(1) not in (_domain(u.group(1)), f"{_domain(u.group(1))}, search result"):
            fails.append(f"C25 grading: [{r['n']}] prints '{shown.group(1)[:50]}' as its source; it prints the domain '{_domain(u.group(1))}' as a link to the full address, never the full URL")
        if u and "linkedin.com" in u.group(1) and tag != "LinkedIn":
            fails.append(f"C25 grading: [{r['n']}] cites linkedin.com but is tagged '{tag}'")
        if not u and re.search(r"https?://", r["source"]):
            fails.append(f"C25 grading: [{r['n']}] prints a bare URL as its source; it prints the domain as a link to the full address")
        if not u and tag != "Yours":
            fails.append(f"C25 grading: [{r['n']}] has no link, so it is the user's own: tag Yours (got '{tag}')")
    return fails


def _labels(spec):
    """(all labels, required labels) a form allows on its block."""
    allow, need = set(), set()
    def add(f, req=True):
        if f.get("label"):
            allow.add(f["label"])
            if req and not (f.get("optional") or f.get("missing") is None and False):
                need.add(f["label"])
    form = spec.get("form")
    if form in ("bullets", "labels_para"):
        for f in spec["fields"]:
            add(f, not f.get("optional"))
            if f.get("join"):
                allow.add(f["join"]["label"])
    elif form == "questions":
        for f in spec["item"]:
            if f.get("label"):
                allow.add(f["label"]); need.add(f["label"])
    elif form == "case_against":
        for f in spec["item"]:
            allow.add(f["label"])
        allow.add(spec["confirm"]["label"])
    elif form == "angle":
        for s in spec["sections"]:
            for f in s["fields"]:
                allow.add(f["label"])
                if f.get("join"):
                    allow.add(f["join"]["label"])
    elif form == "question_order":
        allow |= {spec["beats"]["label"]} | {x + ":" for x in spec["order"]}
        need |= {x + ":" for x in spec["order"]}
    elif form == "repeat":
        allow.add(spec["label"]); need.add(spec["label"])
    elif form == "guardrails":
        allow |= {spec["rule"]["label"], spec["never"]["label"]}; need |= {spec["rule"]["label"], spec["never"]["label"]}
    elif form == "line":
        allow.add(spec["label"]); need.add(spec["label"])
    elif form == "quotes":
        allow.add("LinkedIn:")
    return allow, need


LABEL = re.compile(r"\*\*([^*\n]+?)\*\*")


def _subtitle_ok(line):
    """The script's second line opens with the registry's subtitle, or with a retired one for a script prepared before that day."""
    if line.startswith("*" + R["script"]["subtitle"]):
        return True
    m = re.search(r"Prepared ([A-Z][a-z]{2} \d{1,2}, \d{4})", line)
    return any(line.startswith("*" + k) and m and _day(m.group(1)) < dt.date.fromisoformat(str(until))
               for k, until in R["script"].get("subtitle_retired", {}).items())


def schema_check(brief_md, script_md="", depth=None, tier=None, authority=None):
    """C26: the brief and the script have exactly the registry's structure -- the masthead, every block's heading and title in
    order, only the labels its form allows with the required ones present, its tables' headers, B9's subheads, the ledger's
    header and label grid, page 3's heading and subtitle. The model never writes these files (eval.py assemble does); a
    brief that deviates was not assembled from the schema."""
    F, fails = R["forms"], []
    lines = brief_md.splitlines()
    if not lines or not re.match(r"^# \S", lines[0]):
        fails.append("C26 schema: the brief must open with '# Full Name'")
    elif len(lines) < 3 or not re.match(r"^\*\*[^*]+\*\* \| ", lines[1]):
        fails.append("C26 schema: line 2 must be the identity line '**Organization** | Role, since year[ | City]'")
    else:
        pat = re.escape(F["masthead"]["meta"])
        for key in re.findall(r"\\\{(\w+)\\\}", pat):
            pat = pat.replace(r"\{" + key + r"\}", r"(?P<" + key + r">.+?)")
        if not re.match("^" + pat + "$", lines[2]):
            fails.append("C26 schema: line 3 must be the meta line '" + F["masthead"]["meta"] + "'")
    secs = list(H2.finditer(brief_md))
    want = [(b["id"], fill_names(b["title"])) for b in R["brief"]["sections"]]
    got = [(re.match(r"([BP]\d+)\s+(.*)", m.group(1)).groups() if re.match(r"([BP]\d+)\s", m.group(1)) else (m.group(1), "")) for m in secs]
    if [g[0] for g in got] != [w[0] for w in want]:
        fails.append(f"C26 schema: the brief's blocks are {[g[0] for g in got]}; the schema's are {[w[0] for w in want]}, in that order")
    for gid, gt in got:
        wt = dict(want).get(gid)
        if wt and gt.strip() != wt:
            fails.append(f"C26 schema: block {gid} is titled '{gt.strip()}'; the schema's title is '{wt}'")
    bodies = _sections(brief_md)
    for b in R["brief"]["sections"]:
        body, spec = bodies.get(b["id"], ""), F[b["id"]]
        allow, need = _labels(spec)
        used = {m.group(1).strip() for m in LABEL.finditer(body)}
        if spec["form"] == "questions":
            used = {x.strip() for x in re.findall(r"^\s+- \*\*([^*]+)\*\*", body, re.M)} | {x.strip() for x in re.findall(r"\. \*\*([^*]+)\*\*", body)}
        if spec["form"] in ("quotes", "profile_table", "ledger", "table"):
            used = {u for u in used if u in ("LinkedIn:", "Evidence tier:")} if spec["form"] != "quotes" else {u for u in used if u == "LinkedIn:"}
        stray = sorted(u for u in used if allow and u not in allow and spec["form"] not in ("quotes", "profile_table", "ledger", "table"))
        if stray:
            fails.append(f"C26 schema: {b['id']} prints {stray}, which its form does not have (allowed: {sorted(allow)})")
        lacking = sorted(n for n in need if n not in used and not (b["id"] == "B8"))
        if lacking and spec["form"] not in ("angle",):
            fails.append(f"C26 schema: {b['id']} lacks {lacking}")
        if spec["form"] == "table" and f"| {spec['header'][0]} | {spec['header'][1]} |" not in body:
            fails.append(f"C26 schema: {b['id']}'s table header must be '| {spec['header'][0]} | {spec['header'][1]} |'")
        if spec["form"] == "profile_table":
            if f"| {spec['header'][0]} | {spec['header'][1]} |" not in body:
                fails.append(f"C26 schema: B6's table header must be '| {spec['header'][0]} | {spec['header'][1]} |'")
            lab = [d["shows"] for d in R["rubric"]["dimensions"]]
            rows = [ln for ln in body.splitlines() if ln.startswith("|") and not ln.startswith(("| What", "|---"))]
            if [re.split(r"[:|]", r.strip("| "))[0].strip() for r in rows] != lab:
                fails.append(f"C26 schema: B6 must have the six rows {lab}, in that order")
            if not re.search(r"\*\*Evidence tier:\*\* (?:high|medium|low): it sets how far page 3 goes", body):
                fails.append("C26 schema: B6 must end with the tier line '" + spec["tier"] + "'")
        if spec["form"] == "angle":
            heads = re.findall(r"^### (.+)$", body, re.M)
            if heads != [s["head"] for s in spec["sections"]]:
                fails.append(f"C26 schema: B9's subheads must be {[s['head'] for s in spec['sections']]} (got {heads})")
        if spec["form"] == "questions":
            n = len(re.findall(r"^\d+\. ", body, re.M))
            if not spec["count"][0] <= n <= spec["count"][1]:
                fails.append(f"C26 schema: B2 has {n} questions; the schema allows {spec['count'][0]} to {spec['count'][1]}")
        if spec["form"] == "ledger":
            if "| " + " | ".join(spec["header"]) + " |" not in body:
                fails.append("C26 schema: B10's table header must be '| " + " | ".join(spec["header"]) + " |'")
            grid = [re.match(r"\| \*\*([^*]+)\*\*", ln).group(1) for ln in body.splitlines() if re.match(r"\| \*\*([^*]+)\*\* \|", ln)]
            if grid != spec["grid"]:
                fails.append(f"C26 schema: B10's label grid must be {spec['grid']} (got {grid})")
    if script_md:
        sl = script_md.splitlines()
        title = fill_names(R["script"]["title"])
        if not sl or sl[0].strip() != f"# {title}":
            fails.append(f"C26 schema: the script must open with '# {title}'")
        elif len(sl) < 2 or not (_subtitle_ok(sl[1]) and sl[1].rstrip().endswith("*")):
            fails.append("C26 schema: the script's second line must be '*" + R["script"]["subtitle"] + " · Full Name, Organization · Prepared Mon D, YYYY*'")
        ps = [(re.match(r"(P\d+)", m.group(1)).group(1) if re.match(r"P\d+", m.group(1)) else m.group(1)) for m in H2.finditer(script_md)]
        order = [b["id"] for b in R["script"]["blocks"]]
        if [p for p in ps if p in order] != [o for o in order if o in ps] or set(ps) - set(order):
            fails.append(f"C26 schema: the script's sections {ps} must be a subset of {order}, in that order")
        for opt, cond in (("P5", tier in (None, "medium", "high")), ("P6", True)):
            pass
        sb = _sections(script_md)
        for b in R["script"]["blocks"]:
            if b["id"] not in sb:
                continue
            allow, need = _labels(F[b["id"]])
            used = {m.group(1).strip() for m in LABEL.finditer(sb[b["id"]])}
            if F[b["id"]]["form"] == "objections":
                continue
            stray = sorted(u for u in used if allow and u not in allow)
            if stray:
                fails.append(f"C26 schema: {b['id']} prints {stray}, which its form does not have")
            lacking = sorted(n for n in need if n not in used)
            if lacking and F[b["id"]]["form"] != "bullets":
                fails.append(f"C26 schema: {b['id']} lacks {lacking}")
    return fails


def assembled_matches(folder, profile=None, depth=None):
    """C26: brief.md and script.md in the folder are byte-for-byte what `assemble` builds from fields.json and the records: not
    hand-written, not hand-edited."""
    d = pathlib.Path(folder)
    brief, script, probs = assemble(d, profile, depth)
    fails = list(probs)
    for name, want in (("brief.md", brief), ("script.md", script)):
        have = (d / name).read_text() if (d / name).exists() else None
        if have is None:
            fails.append(f"C26 schema: {name} is missing; run eval.py assemble {folder}")
        elif have != want:
            fails.append(f"C26 schema: {name} differs from what eval.py assemble builds from fields.json; change fields.json and assemble again, never the file")
    return fails


# ---------------------------------------------------------------- hard-coded values (C27) -----------------------------
def registry_tokens():
    """Every wording the registry owns, as (token, where): titles, labels, names, statuses, phrases. A script that spells one of
    these itself instead of reading it from pcp.yaml has a value that can drift from the registry."""
    out = {}
    def add(s, where):
        s = str(s).strip()
        if len(s) >= 10 and not re.fullmatch(r"[\d.\s:|/-]*", s):
            out.setdefault(s, where)
    for b in R["brief"]["sections"] + R["script"]["blocks"]:
        add(b["title"], f"{b['id']} title")
    def walk(o, where):
        if isinstance(o, dict):
            for k, v in o.items():
                if k == "label":
                    add(v, f"{where} label")
                walk(v, where)
        elif isinstance(o, list):
            for v in o:
                walk(v, where)
    walk(R["forms"], "forms")
    for f in R["families"]:
        add(f["name"], f"{f['id']} name")
    for r in R["osint"]["rounds"]:
        add(r["name"], f"round {r['round']} name")
    for x in R["guardrails"]["never_say"]:
        add(x, "never_say")
    for d in R["rubric"]["dimensions"]:
        add(d["shows"], f"{d['id']} row label")
    for k, v in R["names"].items():
        add(v, f"names.{k}")
    for v in R["grading"]["strength"].values():
        add(v, "grading.strength")
    for v in R["linkedin"]["read"].values():
        add(v, "linkedin.read")
    for v in R["linkedin"]["reasons"]:
        add(v, "linkedin.reasons")
    for k in ("title", "subtitle"):
        add(R["script"][k], f"script.{k}")
    for fmt, beats in R["script"]["beats_by_format"].items():
        for b in beats:
            add(b, f"beats.{fmt}")
    return out


def _py_strings(path, skip=()):
    """The string constants of a Python file's code, apart from the named functions (test data) and docstrings."""
    import ast
    tree = ast.parse(pathlib.Path(path).read_text())
    doc = set()
    for n in ast.walk(tree):
        if isinstance(n, (ast.FunctionDef, ast.ClassDef, ast.Module)) and n.body and isinstance(n.body[0], ast.Expr) and isinstance(getattr(n.body[0], "value", None), ast.Constant):
            doc.add(id(n.body[0].value))
    out = []
    def visit(node, skipping=False):
        for c in ast.iter_child_nodes(node):
            sk = skipping or (isinstance(c, ast.FunctionDef) and c.name in skip)
            if isinstance(c, ast.Constant) and isinstance(c.value, str) and id(c) not in doc and not sk:
                out.append((c.lineno, c.value))
            visit(c, sk)
    visit(tree)
    return out


def size_floor_check(root=None):
    """C27 (sizes): every text size the brief style prints is at the floor (pcp.yaml page_budget.text_floor_pt: 10 pt, Ben Oct 13: 10 pt body on
    every rung) or above, apart from the footer, the classification band and [n] marks. Reads the CSS the renderer builds for each rung,
    so a value that slips below the floor in pcp.yaml, layout.json or the renderer is caught before a page is drawn."""
    import importlib.util
    here = pathlib.Path(root or HERE)
    pb = json.loads((here / "format/layout.json").read_text())["page_budget"]
    spec = importlib.util.spec_from_file_location("tp_sizes", here / "format/talyx_pdf.py")
    tp = importlib.util.module_from_spec(spec); sys.dont_write_bytecode = True; spec.loader.exec_module(tp)
    floor, exempt, fails = pb["text_floor_pt"], pb["text_floor_exempt_selectors"], []
    for r in tp.BRIEF_LADDER + tp.LADDER:
        if r["body_pt"] < floor:
            fails.append(f"C27 sizes: rung {r['name']} body is {r['body_pt']} pt; the floor is {floor} pt")
    low = {}
    for rung in tp.BRIEF_LADDER:
        css = tp.brief_css(rung, "f")
        for m in re.finditer(r"([^{}]+)\{([^{}]*)\}", css):
            sel = m.group(1).strip()
            if any(x in sel for x in exempt):
                continue
            for fm in re.finditer(r"(?<![\w-])font-size:\s*([\d.]+)pt", m.group(2)):
                if float(fm.group(1)) < floor - 1e-6:
                    low[(sel[:50], float(fm.group(1)))] = rung["name"]
    fails += [f"C27 sizes: '{s}' is {v} pt, below the {floor} pt floor" for (s, v) in sorted(low)]
    return fails


def skill_literals(root):
    """C27 (SKILL.md): the procedure holds no value the registry owns. Two ways it can:
      - render_skill.py's template spells a registry value (a title, a label, a list, a query, a rule) instead of reading it. Found by
        rendering SKILL.md from a registry whose every such value is replaced by a marker: a value that survives was typed into the template;
      - SKILL.md was edited by hand: a line the registry does not render that holds one of its values."""
    import copy
    import importlib.util
    sys.dont_write_bytecode = True
    spec = importlib.util.spec_from_file_location("rs_hardcoded", root / "render_skill.py")
    rs = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(rs)
    reg, sha = rs.load()
    skip = ("skill", "render_header", "generated_files", "registry_version")
    leaves = {}

    def walk(o, path=()):
        if isinstance(o, dict):
            for k, v in o.items():
                if not (len(path) == 0 and k in skip):
                    walk(v, path + (str(k),))
        elif isinstance(o, list):
            for i, v in enumerate(o):
                walk(v, path + (str(i),))
        elif isinstance(o, str) and len(o.strip()) >= 20 and " " in o.strip():   # a phrase, not a name or a path (those are words the template may use)
            leaves.setdefault(o.strip(), ".".join(path))
    walk(reg)
    marks = {tok: f"@@{i}@@" for i, tok in enumerate(leaves)}

    def perturb(o, top=True):
        if isinstance(o, dict):
            return {k: (v if top and k in skip else perturb(v, False)) for k, v in o.items()}
        if isinstance(o, list):
            return [perturb(v, False) for v in o]
        return marks.get(o.strip(), o) if isinstance(o, str) else o
    fails = []
    typed = rs.render_skill(perturb(reg), sha)
    for tok, where in leaves.items():
        if tok in typed:
            fails.append(f"C27 hardcoded: render_skill.py writes '{tok[:60]}' ({where}) into SKILL.md itself; read it from pcp.yaml")
    disk = (root / SKILL_DIR / "SKILL.md").read_text() if (root / SKILL_DIR / "SKILL.md").exists() else ""
    fresh = set(rs.render_skill(reg, sha).splitlines())
    for n, ln in enumerate(disk.splitlines(), 1):
        if ln not in fresh:
            hit = next(((tok, where) for tok, where in leaves.items() if tok in ln), None)
            if hit:
                fails.append(f"C27 hardcoded: SKILL.md line {n} holds '{hit[0][:60]}' ({hit[1]}) typed in by hand; edit pcp.yaml and run render_skill.py")
    return fails


def hardcoded_check(root=None):
    """C27: the page, the setup and the wording come from pcp.yaml, not from the scripts. Fails when
      - talyx_pdf.py holds a CSS number, a colour or a ladder of its own (every one is in layout.json, written from pcp.yaml),
      - render_skill.py spells a registry title, label, name, status or phrase instead of reading it,
      - a placeholder in a query template or round is not declared in `placeholders`, or an intake column has no mapping,
      - the renderer's page margins and the balance script's differ."""
    fails, here = [], pathlib.Path(root or HERE)
    css = (here / "format/talyx_pdf.py").read_text()
    for m in re.finditer(r'return f"""(.*?)"""', css, re.S):
        s = re.sub(r"\{\{|\}\}", "", m.group(1)); s = re.sub(r"\{[^{}]*\}", "", s)
        lit = [x for x in re.findall(r"(?<![\w#.\-])(-?\d+(?:\.\d+)?)(?:pt|in|px|em|%|fr)\b", s) if float(x) != 0]
        if lit:
            fails.append(f"C27 hardcoded: talyx_pdf.py's CSS holds the number(s) {sorted(set(lit))}; move them to pcp.yaml layout")
    if re.search(r"""["':\s]#[0-9A-Fa-f]{6}\b""", css):
        fails.append("C27 hardcoded: talyx_pdf.py holds a colour; colours live in pcp.yaml colors")
    if re.search(r"^(?:LADDER|BRIEF_LADDER|SZ)\s*=\s*[\[(d]", css, re.M) and "LAYOUT" not in css:
        fails.append("C27 hardcoded: talyx_pdf.py holds a ladder or a size table of its own")
    js = re.search(r'BALANCE = "<script>.*?</script>"', css, re.S)
    if js:
        body = re.sub(r"//[^\n]*", "", js.group(0))
        lit = sorted({x for x in re.findall(r"(?<![\w.])(\d+\.\d+)(?![\w])", body) if x not in ("0.75", "0.01")})
        if lit:
            fails.append(f"C27 hardcoded: the balance script holds the decimal number(s) {lit}; they belong in pcp.yaml balance")
    lay = json.loads((here / "format/layout.json").read_text()) if (here / "format/layout.json").exists() else {}
    if lay and (lay["balance"]["margin_top_in"], lay["balance"]["margin_bottom_in"]) != tuple(float(re.search(r"[\d.]+", lay["layout"][k]).group(0)) for k in ("page__margin_top", "page__margin_bottom")) \
            if all(k in lay.get("layout", {}) for k in ("page__margin_top", "page__margin_bottom")) else False:
        fails.append("C27 hardcoded: the balance script's page margins differ from the renderer's")
    tokens = registry_tokens()
    for line, s in _py_strings(here / "render_skill.py"):
        for tok, where in tokens.items():
            if tok in s and len(s) < 400:
                fails.append(f"C27 hardcoded: render_skill.py line {line} spells '{tok}' ({where}); read it from the registry")
                break
    ph = set(R["placeholders"])
    for f in R["families"]:
        for name in re.findall(r"\{(\w+)\}", str(f["query"])):
            if name not in ph:
                fails.append(f"C27 hardcoded: {f['id']}'s query uses {{{name}}}, which pcp.yaml placeholders does not declare")
    for r in R["osint"]["rounds"]:
        for q in r["queries"]:
            for name in re.findall(r"\{(\w+)\}", q):
                if name not in ph:
                    fails.append(f"C27 hardcoded: round {r['round']} uses {{{name}}}, which pcp.yaml placeholders does not declare")
    fails += size_floor_check(here)
    fails += skill_literals(here)
    csv = here / "skills/pre-call-prep/assets/intake-template.csv"
    if csv.exists():
        cols = csv.read_text().splitlines()[0].split(",")
        missing = [c for c in cols if c not in R["intake_columns"]]
        if missing:
            fails.append(f"C27 hardcoded: intake columns {missing} have no mapping in pcp.yaml intake_columns")
    return fails


# ---------------------------------------------------------------- parity: the no-drift guard ---------------------------
def _flatten(o, path=()):
    """{path: leaf}, the scheme build/baseline.py froze 2.1.0 with: a list of dicts that carry an id is keyed by it."""
    out = {}
    if isinstance(o, dict):
        for k, v in o.items():
            out.update(_flatten(v, path + (str(k),)))
    elif isinstance(o, list) and o and all(isinstance(x, dict) and ("id" in x or len(x) == 1) for x in o):
        for x in o:
            key = x["id"] if "id" in x else next(iter(x))
            out.update(_flatten({k: v for k, v in x.items() if k != "id"} if "id" in x else x[key], path + (str(key),)))
    else:
        out[".".join(path)] = o
    return out


def _live_items(root, reg=None):
    reg = reg or R
    items = {p: v for p, v in _flatten({k: v for k, v in reg.items() if k not in ("generated_files", "render_header", "registry_version")}).items()}
    ev = (root / "eval.py").read_text()
    for name in re.findall(r'sub\.add_parser\("([\w-]+)"', ev):
        items[f"eval.subcommand.{name}"] = True
    m = re.search(r"CHECKS = \[(.*?)\]", ev, re.S)
    for name in re.findall(r'"([\w-]+)"', m.group(1)) if m else []:
        items[f"eval.check_flag.{name}"] = True
    for flag in re.findall(r'add_argument\("(--[\w-]+)"', (root / "format/talyx_pdf.py").read_text()):
        items[f"renderer.flag.{flag}"] = True
    return items


LOCKED = ("forms", "grading", "records", "placeholders", "intake_columns", "colors", "balance", "page_budget", "osint", "linkedin", "source_quality", "families")


def schema_lock(reg=None):
    """sha256 of each schema section of the live registry: the brief's forms, the grading, the records, the page budget and so on."""
    import hashlib
    reg = reg or R
    return {k: hashlib.sha256(json.dumps(reg[k], sort_keys=True, default=str, ensure_ascii=False).encode()).hexdigest()[:12] for k in LOCKED}


def _covers(base, live):
    """The live value holds everything the baseline value did: equal, or a list of dicts whose entries each hold the baseline's keys
    (an added key is not a weakening)."""
    if isinstance(base, dict) and isinstance(live, dict):
        return all(k in live and _covers(v, live[k]) for k, v in base.items())
    if isinstance(base, list) and isinstance(live, list) and len(base) == len(live) and any(isinstance(x, dict) for x in base):
        return all(_covers(x, y) for x, y in zip(base, live))
    return json.dumps(base, sort_keys=True, default=str) == json.dumps(live, sort_keys=True, default=str)


def parity(root=None, strict=False, update_lock=False, approve=None, reg=None):
    """The no-drift guard. Every item of the frozen 2.1.0 baseline (rule ids, parameters, source families, grade fields, layout sizes,
    setup questions, eval checks and subcommands, renderer flags) is KEPT (equal), CHANGED (a different value) or REMOVED. A change or
    a removal passes only when evals/DECISIONS.yaml has an entry with status approved that covers it (an fnmatch pattern on the item
    id); status open is listed and fails under --strict. A schema section whose hash differs from evals/schema.lock.json fails unless an
    approved decision carries its new hash. Returns (failures, summary dict)."""
    import fnmatch
    import yaml
    root = pathlib.Path(root or HERE)
    base = json.loads((root / "evals/baseline-2.1.0.json").read_text())
    dec = yaml.safe_load((root / "evals/DECISIONS.yaml").read_text()) or {}
    decisions = dec.get("decisions", [])
    live = _live_items(root, reg)
    stat = {"kept": [], "changed": [], "removed": []}
    for pid, it in base["items"].items():
        if pid not in live:
            stat["removed"].append(pid)
        elif not _covers(it["value"], live[pid]):
            stat["changed"].append(pid)
        else:
            stat["kept"].append(pid)
    def cover(pid):
        hit = [d for d in decisions if any(fnmatch.fnmatch(pid, pat) for pat in d.get("covers", []))]
        return ("approved" if any(d.get("status") == "approved" for d in hit) else "open" if hit else "none")
    fails, tally = [], {"approved": 0, "open": 0, "none": 0}
    open_ids = []
    for kind in ("removed", "changed"):
        for pid in stat[kind]:
            c = cover(pid)
            tally[c] += 1
            if c == "none":
                fails.append(f"C28 parity: {pid} was {kind} from the 2.1.0 baseline and no approved entry in evals/DECISIONS.yaml covers it")
            elif c == "open":
                open_ids.append(pid)
                if strict:
                    fails.append(f"C28 parity: {pid} was {kind} from the 2.1.0 baseline; its decision is still open (--strict)")
    # pins: values Daniel has fixed, checked on every run, whatever else is approved (a pin changes only by editing DECISIONS.yaml itself)
    def at(path, reg_):
        o = reg_
        for k in path.split("."):
            o = o[int(k)] if isinstance(o, list) else o[k]
        return o
    for pin in dec.get("pins", []):
        try:
            v = at(pin["path"], reg or R)
        except (KeyError, IndexError, ValueError, TypeError):
            fails.append(f"C28 parity: pinned value {pin['path']} is gone"); continue
        if "equals" in pin and v != pin["equals"]:
            fails.append(f"C28 parity: {pin['path']} is {v}; Daniel pinned it at {pin['equals']} ({pin.get('why', '')})")
        if "min" in pin:
            vals = v.items() if isinstance(v, dict) else [(None, x) for x in (v if isinstance(v, list) else [v])]
            low = [(k, x) for k, x in vals if k not in pin.get("except", []) and isinstance(x, (int, float)) and x < pin["min"]]
            if low:
                fails.append(f"C28 parity: {pin['path']} holds {low}, below the pinned minimum {pin['min']} ({pin.get('why', '')})")
        if "each_min" in pin:   # every item of a list: its key at least min
            low = [x for x in at(pin["path"], reg or R) if x[pin["each_min"]["key"]] < pin["each_min"]["min"]]
            if low:
                fails.append(f"C28 parity: {pin['path']} has {len(low)} entries with {pin['each_min']['key']} below {pin['each_min']['min']} ({pin.get('why', '')})")
    lock_path = root / "evals/schema.lock.json"
    import hashlib
    now = schema_lock(reg)
    now["_baseline"] = hashlib.sha256((root / "evals/baseline-2.1.0.json").read_bytes()).hexdigest()[:12]   # the frozen baseline is never edited
    old = json.loads(lock_path.read_text()) if lock_path.exists() else {}
    if approve:   # an explicit act: who approves the new hashes, and where it is recorded
        new = [k for k, sha in now.items() if old.get(k) != sha and k != "_baseline"]
        if new:
            with open(root / "evals/DECISIONS.yaml", "a") as fh:
                for k in new:
                    fh.write(f"  - covers: [\"lock:{k}@{now[k]}\"]\n    status: approved\n    by: {json.dumps(approve['by'])}\n    date: {dt.date.today().isoformat()}\n"
                             f"    source: {json.dumps(approve['source'])}\n    summary: {json.dumps(f'schema section {k} changed from ' + old.get(k, 'none') + ' to ' + now[k])}\n")
            decisions = (yaml.safe_load((root / "evals/DECISIONS.yaml").read_text()) or {}).get("decisions", [])
    if approve:
        lock_path.write_text(json.dumps(now, indent=1, sort_keys=True) + "\n")
    elif update_lock:   # a silent update would defeat the guard: write the lock only when every changed section has its approved decision
        pending = [k for k, sha in now.items() if k != "_baseline" and old.get(k) != sha
                   and not any(d.get("status") == "approved" and f"lock:{k}@{sha}" in d.get("covers", []) for d in decisions)]
        if not pending:
            lock_path.write_text(json.dumps(now, indent=1, sort_keys=True) + "\n")
            old = dict(now)
    for k, sha in now.items():
        if k == "_baseline":
            if old.get(k) != sha:
                fails.append(f"C28 parity: evals/baseline-2.1.0.json was edited ({old.get(k, 'none')} -> {sha}); the baseline is the original plug-in and never changes")
            continue
        if old.get(k) != sha:
            ok = any(d.get("status") == "approved" and f"lock:{k}@{sha}" in d.get("covers", []) for d in decisions)
            if not ok:
                fails.append(f"C28 parity: schema section '{k}' changed (lock {old.get(k, 'none')} -> {sha}); add an approved decision covering 'lock:{k}@{sha}' to evals/DECISIONS.yaml, then run eval.py parity --update-lock")
    return fails, dict(total=len(base["items"]), kept=len(stat["kept"]), changed=len(stat["changed"]), removed=len(stat["removed"]),
                       approved=tally["approved"], open=tally["open"], unapproved=tally["none"], open_ids=open_ids,
                       changed_ids=stat["changed"], removed_ids=stat["removed"], locked=len(now) - 1)


# ---------------------------------------------------------------- skill (C29): the procedure is lean, nothing is lost ---------------
SKILL_DIR = "skills/pre-call-prep"
LOAD_LINE = re.compile(r"^\*\*Load:\*\*(.*)$", re.M)
CONFIG_LINE = re.compile(r"^\*\*Config:\*\* `([^`]+)` keys (.*?) -- ", re.M)


def _norm(s):
    return re.sub(r"\s+", " ", str(s))


def skill_sections(md):
    """[(heading, body)] of SKILL.md's `## ` sections: each is a step (or the checks, the render)."""
    return [(s.split("\n", 1)[0][3:].strip(), s) for s in re.split(r"(?m)^(?=## )", md)[1:]]


def skill_loads(md):
    """Per step: the files its **Load:** line names, in backticks after the label or a semicolon."""
    out = {}
    for head, body in skill_sections(md):
        paths = []
        for ln in LOAD_LINE.findall(body):
            paths += re.findall(r"(?:^|;)\s*`([^`]+)`", ln)
        out[head] = paths
    return out


def item_reach(pid, value, corpus, scopes, names=None):
    """How a 2.1.0 baseline item is reached now: 'config' (a Config line names its key), 'command' (an eval or renderer command the
    loaded text names), 'text' (every string and number of its current value is in SKILL.md or a loaded reference), 'trivial' (nothing
    to find: a boolean or an empty value), or None."""
    import fnmatch
    if any(fnmatch.fnmatch(pid, pat) and pid in ids for ids, pat in scopes):
        return "config"
    if pid.startswith("eval.subcommand."):
        return "command" if f"eval.py {pid.split('.')[-1]}" in corpus else None
    if pid.startswith("eval.check_flag."):
        return "command" if f"--{pid.split('.', 2)[-1]}" in corpus else None
    if pid.startswith("renderer.flag."):
        return "command" if pid.split(".", 2)[-1] in corpus else None
    leaves, stack = [], [value]
    while stack:
        v = stack.pop()
        if isinstance(v, dict):
            stack += list(v.values())
        elif isinstance(v, list):
            stack += v
        elif isinstance(v, str):
            leaves.append(re.sub(r"\{(deliverable|profile|script|collection)\}", lambda m: (names or {}).get(m.group(1), m.group(0)), v))
        elif isinstance(v, (int, float)) and not isinstance(v, bool):
            leaves.append(v)
    if not leaves:
        return "trivial"
    norm = _norm(corpus)
    ids = [s for s in pid.split(".") if re.fullmatch(r"[BPQ]\d+", s)]   # a block or question id: its number must sit on one line with it
    for v in leaves:
        if isinstance(v, str):
            if _norm(v) not in norm:
                return None
        elif ids:
            if not any(all(re.search(r"(?<![\w-])" + i + r"(?![\w-])", ln) for i in ids) and re.search(r"(?<![\w.])" + re.escape(str(v)) + r"(?![\w])", ln)
                       for ln in corpus.splitlines()):
                return None
        elif not re.search(r"(?<![\w.])" + re.escape(str(v)) + r"(?![\w])", norm):
            return None
    return "text"


def skill_check(root=None, reg=None, skill_text=None):
    """C29: SKILL.md holds the procedure and nothing is lost.
      - SKILL.md is at most skill.max_chars (bytes, as `wc -c` counts them);
      - every step (each `## ` section) opens with a **Load:** line naming files that exist, and every reference file of
        skill.files is loaded by some step;
      - every one of the 2.1.0 baseline's items is reached: its current value is in SKILL.md or in a file a step loads, or a
        **Config:** line of a step names its key in pcp.json. Reported as reachable n/N.
    Returns (failures, summary)."""
    root = pathlib.Path(root or HERE)
    reg = reg or R
    sk, sd = reg["skill"], root / SKILL_DIR
    md = skill_text if skill_text is not None else (sd / "SKILL.md").read_text()
    fails = []
    size = len(md.encode())
    if size > sk["max_chars"]:
        fails.append(f"C29 skill: SKILL.md is {size} characters; the cap is {sk['max_chars']}. Move rules and tables to a reference (pcp.yaml skill)")
    loads, corpus, named = skill_loads(md), md, set()
    for head, paths in loads.items():
        if not paths:
            fails.append(f"C29 skill: step '{head}' names no file it loads; open it with a **Load:** line")
        for rel in paths:
            named.add(rel)
            f = sd / rel
            if not f.exists():
                fails.append(f"C29 skill: step '{head}' loads {rel}, which does not exist in {SKILL_DIR}/")
            elif rel.endswith(".md"):
                corpus += "\n" + f.read_text()
    for fid, f in sk["files"].items():
        if f["path"] not in named:
            fails.append(f"C29 skill: {f['path']} is loaded by no step of SKILL.md")
    scopes = []   # (the keys the file really holds, a pattern the Config line names): a line cannot claim a key its file lacks
    import fnmatch
    for file, keys in CONFIG_LINE.findall(md):
        if not (sd / file).exists():
            fails.append(f"C29 skill: a Config line names {file}, which does not exist in {SKILL_DIR}/")
            continue
        if (root / file).exists() and (root / file).read_bytes() != (sd / file).read_bytes():
            fails.append(f"C29 skill: {SKILL_DIR}/{file} differs from {file}; run build/adapters.py to copy it")
        ids = set(_flatten(json.loads((sd / file).read_text())))
        for pat in re.findall(r"`([^`]+)`", keys):
            if not any(fnmatch.fnmatch(i, pat) for i in ids):
                fails.append(f"C29 skill: a Config line names the keys '{pat}' of {file}, which holds none")
            scopes.append((ids, pat))
    base = json.loads((root / "evals/baseline-2.1.0.json").read_text())["items"]
    live = _live_items(root, reg)
    how, lost = {}, []
    for pid in base:
        r = item_reach(pid, live[pid], corpus, scopes, reg["names"]) if pid in live else None
        if r:
            how[r] = how.get(r, 0) + 1
        else:
            lost.append(pid)
    if lost:
        fails.append(f"C29 skill: {len(lost)} of {len(base)} baseline items are in neither SKILL.md nor a file a step loads: " + ", ".join(lost[:12]) + (" ..." if len(lost) > 12 else ""))
    return fails, dict(size=size, steps=len(loads), steps_named=sum(1 for p in loads.values() if p), total=len(base), reachable=len(base) - len(lost),
                       how=how, lost=lost, max=sk["max_chars"], target=sk["target_chars"])


# ---------------------------------------------------------------- versions (C30): one version everywhere ----------------------
VERSION_FILES = {   # path from the repo root -> how its version is written
    "plugins/pcp/pcp.yaml": "registry", "plugins/pcp/pcp.json": "json:registry_version", "build/plugin.source.json": "json:version",
    "plugins/pcp/plugin.json": "json:version", "plugins/pcp/gemini-extension.json": "json:version",
    "plugins/pcp/.claude-plugin/plugin.json": "json:version", "plugins/pcp/.codex-plugin/plugin.json": "json:version",
    "plugins/pcp/.cursor-plugin/plugin.json": "json:version", "plugins/pcp/.devin-plugin/plugin.json": "json:version",
    "plugins/pcp/.grok-plugin/plugin.json": "json:version",
    ".claude-plugin/marketplace.json": "marketplace", ".cursor-plugin/marketplace.json": "marketplace", ".grok-plugin/marketplace.json": "marketplace",
    "plugins/pcp/skills/pre-call-prep/pcp.yaml": "registry", "plugins/pcp/skills/pre-call-prep/pcp.json": "json:registry_version",
    "plugins/pcp/skills/pre-call-prep/SKILL.md": "title", "plugins/pcp/INVENTORY.md": "title",
    "adapters/chat/pcp-knowledge.md": "title", "adapters/chat/pcp-knowledge.txt": "title", "adapters/grok/pcp-knowledge.md": "title",
    "plugins/pcp/CHANGELOG.md": "changelog",
}


def version_strings(repo):
    """[(file, where, version)] for every version string of the plug-in in the repo. Files absent from a partial checkout are skipped."""
    out = []
    for rel, how in VERSION_FILES.items():
        f = pathlib.Path(repo) / rel
        if not f.exists():
            continue
        text = f.read_text()
        if how == "registry":
            out += [(rel, "registry_version", m) for m in re.findall(r"^registry_version:\s*([\w.-]+)", text, re.M)]
            out += [(rel, "header", m) for m in re.findall(r"registry for the pcp plug-in \(v([\w.-]+)\)", text)]
        elif how.startswith("json:"):
            out.append((rel, how[5:], str(json.loads(text).get(how[5:]))))
        elif how == "marketplace":
            j = json.loads(text)
            out.append((rel, "metadata.version", str(j["metadata"]["version"])))
            out += [(rel, f"plugins[{e['name']}].version", str(e["version"])) for e in j["plugins"]]
        elif how == "title":
            out += [(rel, "title", m) for m in re.findall(r"^# (?:Pre-call prep|Inventory: .*?) \(v([\w.-]+)\)", text, re.M)]
        elif how == "changelog":
            m = re.search(r"^## \[(\d[\w.-]*)\]", text, re.M)
            out.append((rel, "newest entry", m.group(1) if m else "none"))
    return out


def versions_check(repo=None):
    """C30: every version string agrees with pcp.yaml's registry_version: the manifest of each host, the marketplace entries, the build source,
    pcp.json, the skill folder's copies, the generated headers and the newest CHANGELOG entry. Returns (failures, [(file, where, version)])."""
    repo = pathlib.Path(repo or HERE.parents[1])
    found = version_strings(repo)
    want = next((v for f, w, v in found if f == "plugins/pcp/pcp.yaml" and w == "registry_version"), None)
    if want is None:
        return ["C30 versions: plugins/pcp/pcp.yaml has no registry_version"], found
    return [f"C30 versions: {f} ({w}) says {v}; pcp.yaml registry_version is {want}" for f, w, v in found if v != want], found


# ---------------------------------------------------------------- gates: no gate looser than 2.1.0 ------------------
GATE_ROLE = {"B1": ["B1", "B3"], "B2": ["B4"], "B3": ["B1", "B5", "B8"], "B4": ["B6"], "B5": ["B2"], "B6": ["B5", "B9"], "B7": ["B9"]}   # 2.1.0 block -> where its role is now


def _want(path, name):
    """'file:line' of the check `if want("name")` in eval.py or evals/ref21.py."""
    for i, ln in enumerate(pathlib.Path(path).read_text().splitlines(), 1):
        if f'if want("{name}")' in ln:
            return f"{pathlib.Path(path).name}:{i}"
    return f"{pathlib.Path(path).name}:?"


def _loc(path, pattern):
    """'file:line' of the first line of a file matching a pattern."""
    for i, ln in enumerate(pathlib.Path(path).read_text().splitlines(), 1):
        if re.search(pattern, ln):
            return f"{pathlib.Path(path).name}:{i}"
    return f"{pathlib.Path(path).name}:?"


def _ref21(root):
    """The 2.1.0 checks (evals/ref21.py, verbatim) loaded with the 2.1.0 registry from the frozen baseline."""
    import importlib.util
    base = json.loads((root / "evals/baseline-2.1.0.json").read_text())["items"]
    spec = importlib.util.spec_from_file_location("ref21", root / "evals/ref21.py")
    ref = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(ref)
    v = lambda k: base[k]["value"]
    ids = lambda kind, key: sorted({k.split(".")[2] for k in base if k.startswith(f"{kind}.{key}.") and k.endswith(".words")})
    ref.R = {"brief": {"sections": [{"id": i, "words": v(f"brief.sections.{i}.words")} for i in ids("brief", "sections")]},
             "script": {"blocks": [{"id": i, "words": v(f"script.blocks.{i}.words")} for i in ids("script", "blocks")]},
             "guardrails": {"never_say": v("guardrails.never_say")}, "checks": [{"method_verbs": v("checks.method_verbs")}],
             "page_budget": {"total_pages": v("page_budget.total_pages")}}
    return ref, base


def _verdict(lost, gained):
    return "looser" if lost else ("stricter" if gained else "same")


def gates_table(root=None):
    """Every 2.1.0 gate against its live counterpart: C1-C10, the rubric, guardrails, exclusions, retention and the page budget.
    Each row runs the frozen 2.1.0 check (evals/ref21.py) and the live check on the same probes, or compares the values the baseline froze.
    A probe a gate must catch (a true hit) that 2.1.0 flagged and the live check does not makes the row 'looser'; a match inside
    a word that was a false hit (2.1.0 read 'issued' as 'sued') is listed as removed, not as a loss. Rows: (id, what, v21, now, verdict,
    evidence). Returns (rows, failures)."""
    root = pathlib.Path(root or HERE)
    ref, base = _ref21(root)
    live = _live_items(root)
    N = {"alder grey", "jane doe", "doe"}
    nouns = sorted(N)
    rows, fails = [], []
    mine, theirs = root / "eval.py", root / "evals/ref21.py"

    def add(gid, what, v21, now, verdict, evidence):
        rows.append((gid, what, v21, now, verdict, evidence))
        if verdict == "looser":
            fails.append(f"gates: {gid} ({what}) is looser than 2.1.0: 2.1.0 {v21} | now {now}")

    flag = lambda fn, md, which, cid, nn=nouns: any(x.startswith(cid) for x in fn(md, "", which, nn))
    blk = lambda i, body: f"## {i} Title\n{body}\n"
    generic = "The whole industry is changing quickly and every leader feels the pressure."
    # ---- C1 swap: where a generic, uncited sentence is caught
    f21 = {b for b in [f"B{i}" for i in range(1, 10)] if flag(ref.checks, blk(b, generic), "swap", "C1")}
    fnow = {b for b in [f"B{i}" for i in range(1, 10)] if flag(checks, blk(b, generic), "swap", "C1")}
    lost = {b for b in f21 if not any(m in fnow for m in GATE_ROLE[b])}
    gained = fnow - {m for b in f21 for m in GATE_ROLE[b]}
    smug = "- **Role:** Not determined, though the firm is the largest in its industry and has grown for a decade."
    tier = R["forms"]["B6"]["tier"].format(tier="high") + " The industry is changing quickly and every leader feels the pressure."
    smuggled = [flag(checks, blk("B3", smug), "swap", "C1"), flag(checks, blk("B6", tier), "swap", "C1"),
                flag(checks, blk("B8", "- No counter-evidence found, because every leader in the industry likes this kind of offer."), "swap", "C1")]
    if not all(smuggled):
        lost.add("smuggled claim")
    add("C1", "swap test: a generic sentence with no [n] and no target noun fails", f"blocks {sorted(f21)} (7 of 9)", f"blocks {sorted(fnow)} ({len(fnow)} of 9); only a whole line that is exactly a schema template is exempt, a claim added to one fails ({sum(smuggled)} of {len(smuggled)} probes)",
        _verdict(lost, gained), f"{_want(mine, "swap")} (live), {_want(theirs, "swap")} (2.1.0); eval.py self-test: 'C1 swap exempts exactly 5 template lines'")
    # ---- C2 bound: every [n] bound to a source row with url + tag + date + C-level
    def doc21(rows_, cites, cov=True):
        body = " ".join(f"Fact {i} about Jane Doe [{i}]." for i in cites)
        return f"## B1 Snapshot\n{body}\n\n## B9 Sources\n" + "\n".join(rows_) + "\n" + ("coverage 5/12\n" if cov else "")

    def docnow(rows_, cites, cov=True):
        body = " ".join(f"Fact {i} about Jane Doe [{i}]." for i in cites)
        key = " · ".join(R["grading"]["strength"].values())
        return (f"## B1 Take\n{body}\n\n## B10 Evidence ledger\n" + ("5 of 12 source types. " if cov else "") + f"Strength: {key}.\n" + "\n".join(rows_)
                + "\n\nPrepared Oct 17, 2026\n")
    r21 = lambda i, date="2026-01-02", tag="DIRECT", conf="C1": f"[{i}] fact {i} -- https://example.org/{i} -- {tag} -- {conf} -- {date}"
    rn = lambda i, date="Jan 2, 2026", tag=" · Direct", strength="Strong": f"| [{i}] | fact {i} | [example.org](https://example.org/{i}){tag} | Measured · {strength} | {date} |"
    ok_now = lambda md: duf(md)["ok"] and not grading_check(md)
    if not (ref.duf(doc21([r21(1)], [1]))["ok"] and ok_now(docnow([rn(1)], [1]))):
        fails.append("gates: the C2 control (one cited row with every field) must pass both 2.1.0 and now")
    probes = {   # name: (2.1.0 document, live document)
        "an uncited row (unbound)": (doc21([r21(1), r21(2)], [1]), docnow([rn(1), rn(2)], [1])),
        "a cite with no row (dangling)": (doc21([r21(1)], [1, 2]), docnow([rn(1)], [1, 2])),
        "a row with no date": (doc21([r21(1, date="")], [1]), docnow([rn(1, date="")], [1])),
        "a row with no tag": (doc21([r21(1).replace(" -- DIRECT", "")], [1]), docnow([rn(1, tag="")], [1])),
        "a row with no C-level": (doc21([r21(1).replace(" -- C1", "")], [1]), docnow([rn(1, strength="").replace("Measured · ", "Measured")], [1])),
        "no coverage line": (doc21([r21(1)], [1], False), docnow([rn(1)], [1], False)),
    }
    f21 = {n for n, (d21, _) in probes.items() if not ref.duf(d21)["ok"]}
    fnow = {n for n, (_, dn) in probes.items() if not ok_now(dn)}
    add("C2", "every [n] is a source row with url, tag, date and C-level; none unbound, none dangling", f"{len(f21)} of {len(probes)} probes flagged (a row missing any field is dropped)",
        f"{len(fnow)} of {len(probes)} probes flagged (duf plus the page's tag and strength, C25); claims.jsonl keeps url, tag, retrieved_at and confidence for every cited row (C23, 8b)",
        _verdict(f21 - fnow, fnow - f21), f"{_loc(mine, 'def duf')}, {_loc(mine, 'def grading_check')}, {_loc(mine, 'claim_requires')} (live), {_loc(theirs, 'def duf')} (2.1.0); self-test: 'C23 ... 2.1.0 C2'")
    # ---- C3 quotes, C4 custom questions: the same rule, the block renamed
    q = 'He said "we want every meeting prepared the same way" at the keynote.'
    add("C3", "a quoted string of 12+ characters in the quotes block carries a [n]", "B2 (In their words)", "B4 (In their words)",
        _verdict({"q"} if flag(ref.checks, blk("B2", q), "quotes", "C3", []) and not flag(checks, blk("B4", q), "quotes", "C3", []) else set(), set()),
        f"{_want(mine, "quotes")} (live), {_want(theirs, "quotes")} (2.1.0)")
    one = "1. What drives it? [1]\n2. What slows it?\n3. Who decides?"
    two = "1. What drives it? [1]\n2. What slows it? [2]\n3. Who decides?"
    s21 = (flag(ref.checks, blk("B5", one), "custom-q", "C4", []), flag(ref.checks, blk("B5", two), "custom-q", "C4", []))
    snow = (flag(checks, blk("B2", one), "custom-q", "C4", []), flag(checks, blk("B2", two), "custom-q", "C4", []))
    add("C4", "at least 2 of the questions carry a [n]", "B5, threshold 2", "B2, threshold 2; the assembler also requires a [c<id>] on every question",
        _verdict({"c4"} if s21 != snow else set(), set()), f"{_want(mine, "custom-q")} (live), {_want(theirs, "custom-q")} (2.1.0)")
    # ---- C5 sections present, in order
    ids21 = [f"B{i}" for i in range(1, 10)] + ["P1", "P2", "P3", "P4", "P6", "P7"]
    idsnow = [b["id"] for b in R["brief"]["sections"]] + [b["id"] for b in R["script"]["blocks"] if b["prints"] == "always"]
    mk = lambda ids_: "".join(blk(i, "Text [1].") for i in ids_)
    miss21 = [i for i in ids21 if flag(ref.checks, mk([x for x in ids21 if x != i]), "sections", "C5", [])]
    missnow = [i for i in idsnow if flag(checks, mk([x for x in idsnow if x != i]), "sections", "C5", [])]
    add("C5", "the required blocks are present, in order", f"{len(miss21)} of {len(ids21)} required blocks (B1-B9, P1-P4, P6, P7)", f"{len(missnow)} of {len(idsnow)} required blocks (B1-B10, P1-P4, P7-P9; P5 and P6 only as C13 allows)",
        _verdict({1} if len(missnow) < len(miss21) or len(miss21) != len(ids21) or len(missnow) != len(idsnow) else set(), {1} if len(missnow) > len(miss21) else set()),
        f"{_want(mine, "sections")} (live), {_want(theirs, "sections")} (2.1.0)")
    # ---- C6 word budgets: +15% per block, the budgets themselves
    words = lambda n: " ".join(["word"] * n)
    tol = {}
    for name, fn, bud in (("2.1.0", ref.checks, base["brief.sections.B1.words"]["value"]), ("now", checks, live["brief.sections.B1.words"])):
        tol[name] = (flag(fn, blk("B1", words(int(bud * 1.14))), "budgets", "C6", []), flag(fn, blk("B1", words(int(bud * 1.16) + 1)), "budgets", "C6", []))
    tot = lambda items, kind: sum(v["value"] if isinstance(v, dict) else v for k, v in items.items() if k.startswith(kind) and k.endswith(".words"))
    b21, bnow, s21, snow = tot(base, "brief.sections."), tot(live, "brief.sections."), tot(base, "script.blocks."), tot(live, "script.blocks.")
    same_tol = tol["2.1.0"] == tol["now"] == (False, True)
    add("C6", "no block exceeds its word budget by more than 15%; the budgets are the page budget", f"+15% (114% passes, 116% fails: {tol['2.1.0'] == (False, True)}); brief {b21} words, script {s21}",
        f"+15% ({tol['now'] == (False, True)}); brief {bnow} words, script {snow}",
        "looser" if (not same_tol or bnow > b21 or snow > s21) else ("stricter" if (bnow < b21 or snow < s21) else "same"),
        f"{_want(mine, "budgets")} (live), {_want(theirs, "budgets")} (2.1.0); pcp.yaml brief.sections / script.blocks words")
    # ---- C7 never say: the phrases, and where they may appear
    phrases = base["guardrails.never_say"]["value"]
    ph = " ".join(phrases)
    a21 = {k: flag(ref.checks, blk(k, ph), "never-say", "C7", []) for k in ("B1", "B8", "P7")}
    anow = {k: flag(checks, blk(k, ph), "never-say", "C7", []) for k in ("B1", "B8", "P7", "P8")}
    each21 = {x for x in phrases if flag(ref.checks, blk("B1", x), "never-say", "C7", [])}
    eachnow = {x for x in phrases if flag(checks, blk("B1", x), "never-say", "C7", [])}
    ex21 = [k for k, fl in a21.items() if not fl]            # 2.1.0 exempts B8 and P7
    exnow = [k for k, fl in anow.items() if not fl]          # now: P8 only
    add("C7", "no never-say phrase appears outside the guardrails block", f"{len(each21)} of {len(phrases)} phrases flagged; exempt blocks {ex21}", f"{len(eachnow)} of {len(live['guardrails.never_say'])} phrases flagged; exempt block {exnow}",
        _verdict(each21 - eachnow, {1} if len(exnow) < len(ex21) else set()),
        f"{_want(mine, 'never-say')} (live), {_want(theirs, 'never-say')} (2.1.0)")
    # ---- C8 outcome, not method
    verbs = base["checks.method_verbs"]["value"]
    vb = " ".join(verbs)
    f21 = {b for b in ("B6",) if flag(ref.checks, blk(b, vb), "outcome", "C8", [])}
    fnow = {b for b in ("B1", "B5", "B6", "B9") if flag(checks, blk(b, vb), "outcome", "C8", [])}
    add("C8", "the offer is stated as an outcome: no method verb", f"{len(verbs)} verbs; read in {sorted(f21)} (the bridge)", f"{len(live['checks.method_verbs'])} verbs; read in {sorted(fnow)} (where the offer is stated)",
        _verdict({1} if (not fnow or len(live["checks.method_verbs"]) < len(verbs)) else set(), {1} if len(fnow) > len(f21) else set()),
        f"{_want(mine, "outcome")} (live), {_want(theirs, "outcome")} (2.1.0)")
    # ---- C9 exclusions: 2.1.0's keywords, every inflection of each; a hit inside another word was a false hit
    kw = ["diagnosed", "diagnostic", "illness", "illnesses", "hospital", "hospitalization", "divorce", "divorced", "divorces", "his wife", "her husband", "children",
          "donated to", "FEC", "campaign contribution", "campaign contributions", "lawsuit", "lawsuits", "sued", "plaintiff", "plaintiffs"]
    compounds = ["misdiagnosed", "misdiagnosis", "undiagnosed", "rehospitalization", "grandchildren", "stepchildren", "schoolchildren", "countersued", "coplaintiff"]   # real words that hold a 2.1.0 keyword mid-word
    beyond = ["countersue", "countersuing", "countersuit"]   # real compounds no 2.1.0 keyword reached
    kw = kw + compounds
    benign = ["issued", "pursued", "effect", "affected"]   # 2.1.0 matched 'sued' and 'fec' inside these
    ff21 = {w for w in kw if flag(ref.checks, blk("B3", f"She mentioned {w} once."), "exclusions", "C9", [])}
    ffnow = {w for w in kw if flag(checks, blk("B3", f"She mentioned {w} once."), "exclusions", "C9", [])}
    bf21 = {w for w in benign if flag(ref.checks, blk("B3", f"It was {w} in 2025."), "exclusions", "C9", [])}
    bfnow = {w for w in benign if flag(checks, blk("B3", f"It was {w} in 2025."), "exclusions", "C9", [])}
    exempt21 = [k for k in ("B8", "B9", "P7") if not flag(ref.checks, blk(k, "She was divorced."), "exclusions", "C9", [])]
    exemptnow = [k for k in ("B8", "B9", "B10", "P7", "P8") if not flag(checks, blk(k, "She was divorced."), "exclusions", "C9", [])]
    gain = {w for w in beyond if flag(checks, blk("B3", f"She mentioned {w} once."), "exclusions", "C9", []) and not flag(ref.checks, blk("B3", f"She mentioned {w} once."), "exclusions", "C9", [])}
    add("C9", "no excluded topic (health, family, political giving, litigation) in the body", f"{len(ff21)} of {len(kw)} word forms flagged (substring match); exempt blocks {exempt21}; {len(bf21)} of {len(benign)} look-alikes flagged", f"{len(ffnow)} of {len(kw)} word forms flagged (every 2.1.0 inflection, and {len([w for w in compounds if w in ffnow])} of {len(compounds)} compounds by pcp.yaml exclusions.compounds; {len(gain)} of {len(beyond)} compounds 2.1.0 never reached); exempt blocks {exemptnow}. Remains looser: a keyword inside an unrelated word ({sorted(bf21 - bfnow)}) and a compound not in the list",
        _verdict(ff21 - ffnow, {1} if len(exemptnow) < len(exempt21) else set()),
        f"{_want(mine, "exclusions")} (live), {_want(theirs, "exclusions")} (2.1.0); the look-alikes were two chat-run false hits")
    # ---- C10 pages: exactly 3
    pb21, pbnow = base["page_budget.total_pages"]["value"], live["page_budget.total_pages"]
    enforced = bool(re.search(r'len\(pages\) != total', mine.read_text()))
    add("C10", "the PDF is exactly 3 pages", f"page count == {pb21}; the renderer exits 2 past --max-pages", f"page count == {pbnow} (C10 pages), the script on page 3, the ledger last on page 2, a link per ledger row; the renderer exits 2 past --max-pages",
        _verdict(set() if (pbnow == pb21 and enforced) else {1}, {1}), f"{_loc(mine, 'C10 pages: .*pages, need exactly')} (live); pcp.yaml page_budget.total_pages; eval.py self-test: 'C10 by control_12.pdf rendered with --brief-pages 3'")
    # ---- values the baseline froze: rubric, guardrails, exclusions, retention, page budget
    def group(gid, what, prefixes, enforce21, enforcenow, evidence, extra_stricter=False):
        keys = [k for k in base if any(k.startswith(p) for p in prefixes)]
        same = [k for k in keys if k in live and _covers(base[k]["value"], live[k])]
        diff = [k for k in keys if k not in same]
        add(gid, what, f"{len(keys)} items; {enforce21}", f"{len(same)} of {len(keys)} identical" + (f"; {len(diff)} differ: {diff[:4]}" if diff else "") + f"; {enforcenow}",
            "looser" if diff else ("stricter" if extra_stricter else "same"), evidence)
    group("rubric", "six dimensions (signals, Low/Mid/High phrases), the three tiers (3 / 2 / 1 observations, 2 sources and a quote or action for high), what they may want (up to 3, each with a disproving claim)",
          ("rubric.",), "read by the model; no script checked them", "C23 checks each tier's minimum observations, the band phrase word for word and the tier line (eval.py records)",
          f"eval.py parity --list (none of rubric.* changed); {_loc(mine, 'needs .* observations')}", True)
    group("guardrails", "the five never-say phrases and the forbidden claims per domain", ("guardrails.",), "never_say checked by C7; forbidden claims text only", "never_say checked by C7 (narrower exemption); the domain's forbidden claims are printed in P8 by the assembler",
          "eval.py parity --list (none of guardrails.* changed); C7 row above", True)
    group("exclusions", "the base exclusions and the exclusions per jurisdiction", ("exclusions.",), "base and jurisdiction lists in the registry; C9 keywords", "same lists; C9 row above",
          "eval.py parity --list (none of exclusions.* changed); C9 row above")
    enforced_ret = any(re.search(r'\[\s*["\']retention["\']\s*\]|get\(\s*["\']retention["\']', (root / f).read_text()) for f in ("eval.py", "render_skill.py", "format/talyx_pdf.py"))
    group("retention", "retention of claims.jsonl by jurisdiction (default, eu)", ("retention.",), "registry values; no script reads them", "same values; no script reads them" if not enforced_ret else "same values; enforced",
          f"eval.py parity --list (none of retention.* changed); grep -n 'retention' eval.py render_skill.py format/talyx_pdf.py reads the registry only")
    t = base["page_budget.ladder"]["value"]
    bodies21 = sorted({r["body_pt"] for r in t})
    pbj = json.loads((root / "format/layout.json").read_text())["page_budget"]
    sizes = {k: v for k, v in pbj["text_sizes_pt"].items() if k not in pbj["text_floor_exempt"]}
    small21 = 9.5   # upstream talyx_pdf.py: td at body - 0.5 pt on the 10 pt rungs; th 8.5 pt, cites 8 pt, footer 7.5 pt
    keys = [k for k in base if k.startswith("page_budget.")]
    same = [k for k in keys if k in live and _covers(base[k]["value"], live[k])]
    add("page_budget", "3 pages (brief 2, script 1), body 10 pt floor, the density ladder, the type scale", f"{len(keys)} items: pages 3/2/1, floor 10, ladder bodies {bodies21}; smallest table text {small21} pt, headers 8.5 pt, cites 8 pt",
        f"{len(same)} of {len(keys)} identical; every reader-facing size at least {min(sizes.values())} pt (footer {pbj['text_sizes_pt']['footer']} pt and the classification band stay small as the footer did); pinned in evals/DECISIONS.yaml",
        "looser" if (len(same) != len(keys) or min(sizes.values()) < small21 or pbj["text_floor_pt"] < base["page_budget.body_pt_floor"]["value"]) else "stricter",
        f"eval.py parity (pins: page_budget.text_floor_pt, body_pt_floor, text_sizes_pt, brief_ladder); {_loc(mine, 'def size_floor_check')}")
    return rows, fails


# ---------------------------------------------------------------- chat (S4-10) ----------------------------------
CHAT_LABEL = "Intelligence Brief (in chat"


def chat_check(text, target_nouns=(), experience=None, authority=None):
    """S4-10: the in-chat fallback is the same brief as text. Label first, page markers 1-2-3 in order, then the
    normal checks (sections, order, citations, ledger, plain words) on the brief and script parts."""
    fails = []
    lines = [ln for ln in text.splitlines() if ln.strip()]
    if not lines or not lines[0].strip().lstrip("*#> ").startswith(CHAT_LABEL):
        fails.append("S4-10 chat: the first line must be the in-chat label 'Intelligence Brief (in chat: ...)'")
    pos = [text.find(f"--- Page {i} ---") for i in (1, 2, 3)]
    if -1 in pos or pos != sorted(pos):
        fails.append(f"S4-10 chat: page markers '--- Page 1/2/3 ---' missing or out of order ({pos})")
    n = R["names"]
    titles = {re.sub(r"\{(\w+)\}", lambda m: n[m.group(1)], x["title"]).lower(): x["id"]
              for x in R["brief"]["sections"] + R["script"]["blocks"]}
    def add_id(m):
        t = m.group(1).strip()
        if re.match(r"[BP]\d+\b", t):
            return m.group(0)
        num = re.match(r"\d+\.?\s+(.+)$", t)   # page 3's sections print numbered, as in the PDF; brief blocks never do
        if num:
            key = titles.get(num.group(1).lower().rstrip(':'), '')
            return f"## {key} {num.group(1)}" if key.startswith("P") else m.group(0)
        return f"## {titles.get(t.lower().rstrip(':'), '')} {t}".replace("##  ", "## ")
    body = re.sub(r"^## (.+)$", add_id, re.sub(r"^--- Page \d ---\s*$", "", text, flags=re.M), flags=re.M)
    m = re.search(r"^# " + re.escape(n["script"]) + r"\s*$", body, re.M | re.I)
    if not m or (pos[2] != -1 and m.start() < 0):
        fails.append(f"S4-10 chat: no '# {n['script']}' heading for page 3")
        return fails
    if pos[2] != -1 and text.find("# " + n["script"]) < pos[2]:
        fails.append(f"S4-10 chat: '# {n['script']}' must come after '--- Page 3 ---'")
    brief, script = body[:m.start()], body[m.start():]
    # S4-10's own closing lines (the self-review note and the after-call offer) are not part of P9
    script = re.split(r"^\**(?:Checks: self-reviewed|After the call)", script, maxsplit=1, flags=re.M)[0]
    fails += checks(brief, script, "all", target_nouns, experience, authority)
    rep = duf(brief, script)
    if not rep["ok"]:
        fails.append(f"S4-10 chat: citations and ledger do not bind ({ {k: rep[k] for k in ('unbound', 'dangling', 'dropped')} })")
    return fails


# ---------------------------------------------------------------- ratchet ------------------------------------
def ratchet(record=False):
    rf = HERE / R["eval"]["ratchet_file"]
    floors = json.loads(rf.read_text()) if rf.exists() else {"policy": R["eval"]["policy"], "floors": {}}
    tdir = HERE / R["eval"]["frozen_targets_dir"]
    runs = sorted(tdir.glob("*/latest/brief.md"))
    if not runs:
        print(f"ratchet: 0 rendered frozen targets under {tdir} (baseline not yet measured) -- nothing to compare; exit 2")
        return 2
    bad = []
    for b in runs:
        tid = b.parents[1].name
        s = b.parent / "script.md"
        rep = duf(b.read_text(), s.read_text() if s.exists() else "")
        floor = floors["floors"].get(tid, {}).get("duf_pp", 0)
        status = "OK" if rep["duf_pp"] >= floor and rep["ok"] else "REGRESS"
        print(f"{tid}: duf_pp {rep['duf_pp']} floor {floor} checks_ok {rep['ok']} -> {status}")
        if status != "OK":
            bad.append(tid)
        if record and rep["ok"] and rep["duf_pp"] > floor:
            floors["floors"][tid] = {"duf_pp": rep["duf_pp"], "recorded": dt.date.today().isoformat()}
    if record:
        if not bad:
            floors["baseline"] = {"measured": True, "date": dt.date.today().isoformat(), "targets": len(runs),
                                  "command": "eval.py ratchet --record (each target: a real /pcp run with its target.yaml)"}
        rf.write_text(json.dumps(floors, indent=2))
        print("floors written", rf.relative_to(HERE))
    print(f"ratchet population: {len(runs)} targets, {len(bad)} regress")
    return 1 if bad else 0


# ---------------------------------------------------------------- improve ------------------------------------
def improve(debriefs):
    import yaml   # the debrief is YAML; only this command needs the library
    props = []
    for p in debriefs:
        d = yaml.safe_load(pathlib.Path(p).read_text())
        used = set(d.get("facts_used", []))
        fam_hits = d.get("facts_by_family", {})  # optional: {F1: [ids]}
        for fam, ids in fam_hits.items():
            if ids and not (used & set(ids)):
                props.append(f"# basis: {p}\n- family {fam}: weight -0.1 (0 of {len(ids)} facts used)")
        for dim, hit in d.get("band_accuracy", {}).items():
            if hit == "miss":
                props.append(f"# basis: {p}\n- rubric {dim}: review signals (band missed in the room)")
    out = HERE / "evals/proposals" / f"{dt.date.today().isoformat()}.patch"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(props) or "# no proposals\n")
    print("wrote", out.relative_to(HERE), f"({len(props)} proposals) -- apply to pcp.yaml by hand-review, then `eval.py ratchet`")


CHECKS = ["swap", "quotes", "custom-q", "sections", "budgets", "never-say", "outcome", "exclusions", "plain", "gaps", "conditional", "layout",
          "linkedin", "cites", "quality", "battery", "grading", "schema"]


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    d = sub.add_parser("duf"); d.add_argument("brief"); d.add_argument("script", nargs="?"); d.add_argument("--pages", type=int)
    d.add_argument("--pdf", help="the rendered PDF: duf_pp divides by its real page count")
    c = sub.add_parser("checks"); c.add_argument("brief"); c.add_argument("script", nargs="?"); c.add_argument("--target-nouns", default="")
    for w in CHECKS + ["all"]:
        c.add_argument(f"--{w}", action="store_true")
    c.add_argument("--authority", choices=["high", "medium"], help="profile caller.authority_level; C13 gates P6 on it")
    c.add_argument("--experience", choices=[o["value"] for q in R["calibration"]["questions"] if q["id"] == "Q9" for o in q["options"]],
                   help="the profile's Q9 answer: runs C15 with --all")
    p = sub.add_parser("pdf"); p.add_argument("pdf"); p.add_argument("brief", nargs="?")
    ct = sub.add_parser("cites"); ct.add_argument("brief"); ct.add_argument("--fetch", action="store_true"); ct.add_argument("--claims")
    lk = sub.add_parser("links"); lk.add_argument("pdf", metavar="brief.md|OUT.pdf")
    rc = sub.add_parser("render"); rc.add_argument("pdf")
    bt = sub.add_parser("battery", aliases=["history"], help="C21 + C22 from the run's own history, any host: " + HOST_FILES)
    bt.add_argument("transcripts", nargs="*", help="the run's history file(s), in order: Claude Code .jsonl, a Codex rollout .jsonl, a ChatGPT or Claude app conversations.json")
    bt.add_argument("--latest", action="store_true", help="read this host's newest history file for the current session")
    bt.add_argument("--depth", default="standard", choices=["fast", "standard", "deep"])
    bt.add_argument("--brief", help="brief.md or the PDF: its Run row counts must match the transcript")
    bt.add_argument("--kind", default="person", choices=["person", "company", "deal"], help="the target kind (profile target.kind): company and deal runs drop person-only source types")
    bt.add_argument("--scope", default="professional", choices=["professional", "social", "none"], help="the social scope (profile socmint.scope): none sends no public-social query")
    bt.add_argument("--no-popup", action="store_true", help="the host has no native question tool: a typed question list is then the fallback, not a failure")
    bt.add_argument("--profile", help="the saved profile (~/.pcp/profile.yaml): a saved offer that conflicts with the request needs a question first")
    rcd = sub.add_parser("records", help="C23: claims.jsonl, coverage.json and read.json are complete and agree, before the run is called done")
    rcd.add_argument("folder"); rcd.add_argument("--depth", default="standard", choices=["fast", "standard", "deep"]); rcd.add_argument("--brief")
    kp = sub.add_parser("kept", help="C24: the final brief holds every cited fact of the first complete draft (cut wording, never facts); "
                        "give the run folder: the draft is the one eval.py assemble recorded")
    kp.add_argument("draft", metavar="FOLDER | DRAFT"); kp.add_argument("final", nargs="?"); kp.add_argument("--draft-script", default=""); kp.add_argument("--final-script", default="")
    kp.add_argument("--allow", action="append", default=[], metavar="N=dead|excluded",
                    help="one fact of the draft's ledger, [N], dropped because its page is dead or it touches an excluded topic (checked; told to the user); never fit")
    kp.add_argument("--profile", default=str(pathlib.Path.home() / ".pcp/profile.yaml"))
    oc = sub.add_parser("offer-conflict", help="C22: does the request name a different business than the saved offer?")
    oc.add_argument("--saved", required=True); oc.add_argument("--request", required=True)
    ch = sub.add_parser("chat"); ch.add_argument("reply"); ch.add_argument("--target-nouns", default="")
    ch.add_argument("--experience"); ch.add_argument("--authority", choices=["high", "medium"])
    asm = sub.add_parser("assemble", help="C26: build brief.md and script.md from fields.json, the records and the profile (the model never writes them)")
    asm.add_argument("folder"); asm.add_argument("--profile", default=str(pathlib.Path.home() / ".pcp/profile.yaml"))
    asm.add_argument("--depth", choices=["fast", "standard", "deep"]); asm.add_argument("--check", action="store_true", help="fail unless brief.md and script.md are exactly what assemble builds")
    sub.add_parser("hardcoded", help="C27: no value the registry owns is hard-coded in the render scripts")
    gt = sub.add_parser("gates", help="every 2.1.0 gate (C1-C10, rubric, guardrails, exclusions, retention, page budget) against the live one: same, stricter or looser; any looser fails")
    gt.add_argument("--md", action="store_true", help="print the table as Markdown")
    sub.add_parser("versions", help="C30: every version string in the repo (host manifests, marketplaces, generated headers, CHANGELOG) agrees with pcp.yaml's registry_version")
    sub.add_parser("skill", help="C29: SKILL.md is at most skill.max_chars, every step names the files it loads, every 2.1.0 baseline item is reachable")
    pr = sub.add_parser("parity", help="C28: the no-drift guard: nothing of the 2.1.0 baseline is removed or weakened without an approved decision")
    pr.add_argument("--strict", action="store_true", help="also fail every decision that is still open")
    pr.add_argument("--update-lock", action="store_true", help="write evals/schema.lock.json from the live registry (after an approved decision)")
    pr.add_argument("--approve-locks", action="store_true", help="record an approved decision for every changed schema section (needs --by and --source), then lock it")
    pr.add_argument("--by"); pr.add_argument("--source")
    pr.add_argument("--list", action="store_true", help="print every changed or removed item and how it is covered")
    sub.add_parser("concordance")
    st = sub.add_parser("self-test"); st.add_argument("--require-pdf", action="store_true", help="fail, not skip, when no PDF can be rendered and read")
    r = sub.add_parser("ratchet"); r.add_argument("--record", action="store_true")
    i = sub.add_parser("improve"); i.add_argument("debriefs", nargs="+")
    a = ap.parse_args()

    if a.cmd == "duf":
        pages = a.pages
        if a.pdf:
            pp = pdf_pages(a.pdf)
            if pp is None:
                print("duf --pdf: no pdftotext or pypdf to count the PDF's pages -- use --pages N"); sys.exit(2)
            pages = len(pp)
        rep = duf(pathlib.Path(a.brief).read_text(), pathlib.Path(a.script).read_text() if a.script else "", pages)
        print(json.dumps(rep, indent=1)); sys.exit(0 if rep["ok"] else 1)
    if a.cmd == "checks":
        which = next((w for w in CHECKS if getattr(a, w.replace("-", "_"))), "all")
        if a.brief.lower().endswith(".pdf"):   # the printed text: only plain words can be read back from a PDF
            if which != "plain":
                sys.exit(f"checks on a PDF: only --plain (got --{which}); use `eval.py pdf` for the layout")
            pages = pdf_pages(a.brief)
            if pages is None:
                print("checks (plain): no pdftotext or pypdf to read the PDF -- not run"); sys.exit(2)
            f = [f"C11 plain: '{h}' printed in the PDF outside quoted words" for h in plain_hits(re.sub(r"\s+", " ", "\n".join(pages)))]
        else:
            f = checks(pathlib.Path(a.brief).read_text(), pathlib.Path(a.script).read_text() if a.script else "", which,
                       [n.strip() for n in a.target_nouns.split(",")], a.experience, a.authority)
        print(f"checks ({which}): {len(f)} failures"); [print(" -", x) for x in f]; sys.exit(1 if f else 0)
    if a.cmd == "pdf":
        f = pdf_check(a.pdf, pathlib.Path(a.brief).read_text() if a.brief else "")
        if f is None:
            print("pdf: no pdftotext or pypdf to read the PDF -- not run"); sys.exit(2)
        print(f"pdf {a.pdf}: {len(f)} failures"); [print(" -", x) for x in f]; sys.exit(1 if f else 0)
    if a.cmd in ("parity", "hardcoded", "skill", "gates", "versions") and not (HERE / "render_skill.py").exists():
        sys.exit(f"{a.cmd}: a maintainer check; it needs the plug-in checkout (render_skill.py, evals/baseline-2.1.0.json), not the copy inside a skill folder")
    if a.cmd == "parity":
        if a.approve_locks and not (a.by and a.source):
            sys.exit("parity --approve-locks needs --by <who decided> and --source <where it is recorded>")
        f, s = parity(strict=a.strict, update_lock=a.update_lock, approve={"by": a.by, "source": a.source} if a.approve_locks else None)
        print(f"parity: {s['total']} items of the 2.1.0 baseline: {s['kept']} kept, {s['changed']} changed, {s['removed']} removed; "
              f"of the {s['changed'] + s['removed']}: {s['approved']} approved, {s['open']} open, {s['unapproved']} unapproved; {s['locked']} schema sections locked")
        if a.list:
            print("changed:", *s["changed_ids"], sep="\n  "); print("removed:", *s["removed_ids"], sep="\n  ")
        print(*[" - " + x for x in f], f"{len(f)} failures", sep="\n")
        sys.exit(1 if f else 0)
    if a.cmd == "versions":
        f, found = versions_check()
        print(f"versions: {len(found)} version strings in {len({x[0] for x in found})} files, pcp.yaml says {next((v for fl, w, v in found if fl == 'plugins/pcp/pcp.yaml' and w == 'registry_version'), '?')}")
        print(*[" - " + x for x in f], f"{len(f)} failures", sep="\n")
        sys.exit(1 if f else 0)
    if a.cmd == "gates":
        rows, f = gates_table()
        if a.md:
            print("| Gate | What | 2.1.0 | Now | Verdict | Evidence |", "|---|---|---|---|---|---|", sep="\n")
            for r in rows:
                print("| " + " | ".join(str(x).replace("|", "/") for x in r) + " |")
        else:
            for r in rows:
                print(f"{r[0]:12} {r[4]:8} 2.1.0: {r[2]} | now: {r[3]}")
        n = {v: sum(1 for r in rows if r[4] == v) for v in ("same", "stricter", "looser")}
        print(f"gates: {len(rows)} rows: {n['same']} same, {n['stricter']} stricter, {n['looser']} looser")
        print(*[" - " + x for x in f], f"{len(f)} failures", sep="\n")
        sys.exit(1 if f else 0)
    if a.cmd == "skill":
        f, s = skill_check()
        print(f"skill: SKILL.md {s['size']} characters (cap {s['max']}, target {s['target']}); {s['steps_named']} of {s['steps']} steps name the files they load; "
              f"reachable {s['reachable']}/{s['total']} baseline items ({', '.join(f'{k} {v}' for k, v in sorted(s['how'].items()))})")
        print(*[" - " + x for x in f], f"{len(f)} failures", sep="\n")
        sys.exit(1 if f else 0)
    if a.cmd == "hardcoded":
        f = hardcoded_check()
        print(f"hardcoded: {len(f)} failures", *[" - " + x for x in f], sep="\n")
        sys.exit(1 if f else 0)
    if a.cmd == "concordance":
        sys.exit(0 if concordance() else 1)
    if a.cmd == "self-test":
        sys.exit(0 if self_test(a.require_pdf) else 1)
    if a.cmd == "cites":
        md = pathlib.Path(a.brief).read_text()
        cl = [json.loads(x) for x in pathlib.Path(a.claims).read_text().splitlines() if x.strip()] if a.claims else None
        f = cite_relevance(md, fetch=a.fetch) + source_quality(ledger(md), cl)
        print("\n".join(f) or "cites: every cited sentence matches its ledger row; 0 failures")
        sys.exit(1 if f else 0)
    if a.cmd == "links":
        res = link_status(sorted(set(link_targets(a.pdf))))
        for u, c, k in res:
            print(f"{k:8} {c:4} {u}")
        dead = [r for r in res if r[2] == "dead"]
        print(f"links: {len(res)} total, {sum(r[2]=='ok' for r in res)} ok, {sum(r[2]=='blocked' for r in res)} blocked by the site (bot wall, not a failure), {len(dead)} dead")
        sys.exit(1 if dead else 0)
    if a.cmd == "chat":
        f = chat_check(pathlib.Path(a.reply).read_text(), [x.strip() for x in a.target_nouns.split(",") if x.strip()], a.experience, a.authority)
        print("\n".join(f) or "chat: in-chat brief follows the schema; 0 failures")
        sys.exit(1 if f else 0)
    if a.cmd == "render":
        f = render_check(a.pdf) + text_colors(a.pdf)
        print("\n".join(f) or "render: nothing clipped, logo whole, no blank band, text in the three colours; 0 failures")
        sys.exit(1 if f else 0)
    if a.cmd in ("battery", "history"):
        text, cited = "", None
        if a.brief:
            pdf = a.brief.lower().endswith(".pdf")
            text = "\n".join(pdf_pages(a.brief) or []) if pdf else pathlib.Path(a.brief).read_text()
            cited = pdf_links(a.brief) if pdf else None
        files = list(a.transcripts)
        if a.latest or not files:
            found = find_history()
            if not found:
                sys.exit("history: no history file found for this session. Pass it: " + HOST_FILES)
            files = [str(f) for f in found]
        saved = ""
        if a.profile and pathlib.Path(a.profile).exists():
            import yaml
            pr = yaml.safe_load(pathlib.Path(a.profile).read_text()) or {}
            saved = str(((pr.get("profiles") or {}).get(next(iter(pr.get("profiles") or {}), ""), {}).get("answers", {}).get("Q8", {}) or {}).get("value", ""))
        f, summary = battery(history_lines(files), a.depth, text, cited, saved, False if a.no_popup else None, a.kind, a.scope)
        print(f"history: {summary}", *[" - " + x for x in f], f"{len(f)} failures", sep="\n")
        sys.exit(1 if f else 0)
    if a.cmd == "assemble":
        prof = None
        if pathlib.Path(a.profile).exists():
            import yaml
            prof = yaml.safe_load(pathlib.Path(a.profile).read_text())
        if a.check:
            f = assembled_matches(a.folder, prof, a.depth)
            print(f"assemble --check {a.folder}: {len(f)} failures", *[" - " + x for x in f], sep="\n")
            sys.exit(1 if f else 0)
        out, code = build(a.folder, prof, a.depth)
        print(*out, sep="\n")
        sys.exit(code)
        sys.exit(1 if f else 0)
    if a.cmd == "records":
        f = records_check(a.folder, a.depth, pathlib.Path(a.brief).read_text() if a.brief else "")
        print(f"records {a.folder}: {len(f)} failures", *[" - " + x for x in f], sep="\n")
        sys.exit(1 if f else 0)
    if a.cmd == "kept":
        if a.final is None:
            if not pathlib.Path(a.draft).is_dir():
                sys.exit("kept: give the run folder (eval.py kept <folder>), or two files (eval.py kept <draft brief.md> <final brief.md>)")
            prof = None
            if pathlib.Path(a.profile).exists():
                import yaml
                prof = yaml.safe_load(pathlib.Path(a.profile).read_text())
            f, summary = kept_folder(a.draft, a.allow, prof)
            print(f"kept {a.draft}: {summary}; {len(f)} failures", *[" - " + x for x in f], sep="\n")
            sys.exit(1 if f else 0)
        import hashlib
        rd = lambda x: pathlib.Path(x).read_text() if x else ""
        f, told, lockp = [], [], pathlib.Path(a.draft).resolve().parent / DRAFT_LOCK
        if lockp.exists() and hashlib.sha256(rd(a.draft).encode()).hexdigest() != json.loads(lockp.read_text()).get("brief_sha256"):
            f.append(f"C24 kept: {a.draft} is not the draft eval.py assemble recorded in {lockp.parent} (a copy taken later, or changed): run eval.py kept {lockp.parent}")
        f += kept_check(rd(a.draft), rd(a.final), a.allow, rd(a.draft_script), rd(a.final_script), told=told)
        print(f"kept: draft {count_facts(rd(a.draft))} cited facts, final {count_facts(rd(a.final))}"
              + (f"; dropped with a reason the user is told: {'; '.join(told)}" if told else "") + f"; {len(f)} failures",
              *[" - " + x for x in f], sep="\n")
        sys.exit(1 if f else 0)
    if a.cmd == "offer-conflict":
        diff = offer_conflict(a.saved, a.request)
        print("conflict: ask before collection" if diff else "no conflict", ", ".join(diff))
        sys.exit(1 if diff else 0)
    if a.cmd == "ratchet":
        sys.exit(ratchet(a.record))
    if a.cmd == "improve":
        improve(a.debriefs)


if __name__ == "__main__":
    main()
