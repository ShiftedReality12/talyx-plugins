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


def _sentences(txt):
    txt = re.sub(r"\|.*\|", " ", txt)  # tables are rows, not sentences
    txt = "\n".join(ln for ln in txt.splitlines()   # structure and the registry's own fallback lines, not claims
                    if not re.match(r"\s*#|.*(?:Not determined|Evidence tier:|No counter-evidence found)", ln))
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


def checks(brief_md, script_md="", which="all", target_nouns=(), experience=None, authority=None):
    """experience: the profile's Q9 answer (new|experienced|top); C15 runs only when it is given."""
    md = brief_md + "\n" + script_md
    secs = _sections(md)
    fails = []
    budgets = {s["id"]: s["words"] for s in R["brief"]["sections"]} | {b["id"]: b["words"] for b in R["script"]["blocks"]}
    prepared = re.search(r"Prepared\s+([A-Z][a-z]{2} \d{1,2}, \d{4})", brief_md)
    dens = R["page_budget"]["density"]
    if prepared and _day(prepared.group(1)) < dt.date.fromisoformat(str(dens["since"])):
        budgets = budgets | dens["legacy_words"]   # a brief written before the 9.5 pt density keeps its day's budgets (the frozen targets)

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
        for k in [k for k in secs if re.match(r"B1$|B[3-8]$", k)]:   # the blocks that state facts about the person
            for s in _sentences(secs[k]):
                if CITE.search(s):
                    continue
                if re.match(r"[-*\s]*\*\*(LinkedIn|Reverses if|Stop if):\*\*", s):   # the mandated status line (S2-7, C16) states no fact
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
    if want("never-say"):
        for k, body in secs.items():
            if k == "P8":
                continue
            for p in R["guardrails"]["never_say"]:
                if p.lower() in body.lower():
                    fails.append(f"C7 never_say: '{p}' in {k}")
    if want("outcome"):
        mv = next(c["method_verbs"] for c in R["checks"] if "method_verbs" in c)
        for v in mv:
            if v.lower() in secs.get("B5", "").lower():
                fails.append(f"C8 outcome: method verb '{v}' in B5")
    if want("exclusions"):
        kws = {"health": [r"diagnos\w*", "illness", r"hospital(?:i[sz]ed|s)?"],   # whole words: "effect" holds no FEC,
               "family": [r"divorced?", "his wife", "her husband", "children"],          # "issued" no sued (two chat runs)
               "political": ["donated to", "FEC", r"campaign contributions?"], "litigation": [r"lawsuits?", "sued", r"plaintiffs?"]}
        body = "\n".join(v for k, v in secs.items() if k not in (LEDGER, "P8"))
        for topic, words in kws.items():
            for w in words:
                m = re.search(r"\b(?:" + w + r")\b", body, re.I)
                if m:
                    fails.append(f"C9 exclusions: '{m.group(0)}' ({topic}) in body")
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
    ids = {c["id"] for c in R["checks"] if "id" in c}
    blocks = {b["id"]: b for b in R["brief"]["sections"] + R["script"]["blocks"]}
    conditional = [(e["id"], blocks[e["id"]]["prints"], e.get("check")) for e in R["inventory"]["blocks"] if blocks[e["id"]]["prints"] != "always"]
    conditional += [(p["id"], p.get("prints"), p.get("check")) for p in R["inventory"]["parts"] if p["status"] == "conditional"]
    for pid, prints, cid in conditional:
        if cid not in ids:
            print(f"FAIL inventory {pid}: prints only when '{prints}' but no check enforces it (check: {cid})"); ok = False
    cf = chat_check((fx / "chat_control.md").read_text())
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
        for rel in ("format/talyx_pdf.py", "format/layout.json", "render_skill.py", "skills/pre-call-prep/assets/intake-template.csv"):
            (root / rel).parent.mkdir(parents=True, exist_ok=True)
            (root / rel).write_text((HERE / rel).read_text())
        base_css, base_rs = (root / "format/talyx_pdf.py").read_text(), (root / "render_skill.py").read_text()
        for case, rel, new_text, want in (
                ("a CSS number in the renderer", "format/talyx_pdf.py", base_css.replace("{L['page_content__padding']}", "0.55in", 1), "talyx_pdf.py's CSS"),
                ("a colour in the renderer", "format/talyx_pdf.py", base_css + '\nX = "#123456"\n', "holds a colour"),
                ("a decimal in the balance script", "format/talyx_pdf.py", base_css.replace("CFG.spare_in", "0.2", 1), "balance script"),
                ("a block title spelled in render_skill.py", "render_skill.py", base_rs + '\nX = "Strongest case against"\n', "render_skill.py")):
            (root / rel).write_text(new_text)
            f = hardcoded_check(root)
            (root / rel).write_text(base_css if rel.endswith("pdf.py") else base_rs)
            if any(want in x for x in f):
                print(f"tripped: C27 by {case}")
            else:
                print(f"FAIL C27 must trip on {case} (got {f})"); ok = False
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
            ("a layout size changed", lambda r: r["page_budget"]["text_sizes_pt"].update(ledger=8), "schema section 'page_budget'")):
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
    f, _ = parity(strict=True)
    if any("still open" in x for x in f):
        print(f"tripped: C28 --strict on the {ps['open']} decisions that are still open")
    else:
        print("FAIL parity --strict must fail an open decision"); ok = False
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
              "a Search row read Solid": (lambda b: re.sub(r"(Fact 6 about Alder Grey Capital \|[^|]*\| )[^|]+\|", "\\1Derived · Solid |", b).replace("career profile", "career profile"), "caps"),
              "the strength key left out": (lambda b: re.sub(r"Strength: [^.]*\.", "", b), "key the strengths"),
              "a row with no tag": (lambda b: b.replace("(https://example.org/1) · Direct", "(https://example.org/1)"), "how it was found"),
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
    cut = re.sub(r"^\| \[12\].*\n", "", c12, flags=re.M).replace(" [12]", "").replace("12 facts cited", "11 facts cited").replace("12 cited", "11 cited")
    shorter = c12.replace("Introduction to the custodian offered", "Custodian introduction offered").replace("Sets agendas on panels", "Sets panel agendas")
    for case, final, allow, trips in (("a cited fact cut to fit the page", cut, (), True),
                                      ("the same fact cut, named as a dead link", cut, ("https://example.org/12",), False),
                                      ("shorter wording, every fact kept", shorter, (), False)):
        f = kept_check(c12, final, allow)
        if bool(f) != trips:
            print(f"FAIL C24 on {case}: expected {'a failure' if trips else 'a pass'}, got {f}"); ok = False
        else:
            print(f"{'tripped' if trips else 'passes'}: C24 on {case}")
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
MUST_PASS = [
    ("control_12.md", {}),
    ("control_12.md", {"experience": "experienced"}),
    ("control_12.md", {"experience": "top"}),
    ("exp_new.md", {"experience": "new"}),
    ("linkedin_declined.md", {}),
    ("linkedin_search.md", {}),
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


def find_history(host=None, cwd=None):
    """The newest history file this host keeps for the current session (--latest): Claude Code's project folder for the
    working folder, or the Codex rollout whose name carries $CODEX_THREAD_ID (else the newest). Returns a path or None."""
    import os
    home = pathlib.Path.home()
    tid = os.environ.get("CODEX_THREAD_ID", "")
    if host in (None, "codex") and (tid or host == "codex"):
        files = sorted((home / ".codex/sessions").glob("**/rollout-*.jsonl"), key=lambda p: p.stat().st_mtime, reverse=True)
        hit = [p for p in files if tid and tid in p.name]
        if hit or (host == "codex" and files):
            return (hit or files)[0]
    folder = re.sub(r"[^A-Za-z0-9]", "-", str(pathlib.Path(cwd or os.getcwd()).resolve()))
    files = sorted((home / ".claude/projects" / folder).glob("*.jsonl"), key=lambda p: p.stat().st_mtime, reverse=True) if (home / ".claude/projects" / folder).is_dir() else []
    return files[0] if files else None


def _content_words(t):
    return {w for w in re.findall(r"\b(?:ai|[a-z][a-z'-]{2,})\b", t.lower()) if w not in STOP}


STOP = set("the and for are but not you your with that this from have has had was were will can could would should about into over than then them they their "
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
    lined = any(v is not None for v in named.values())
    if lined:   # round lines name the rounds; the searches before the first one are the base pass
        base_steps = order[:next(i for i, s in enumerate(order) if named[s] is not None)]
    else:       # no lines: the last batches, one per round, are the rounds; the batches before them are the base pass
        base_steps = order[:max(0, len(order) - len(need))]
    base = [q for s in base_steps for q in batches[s]]
    rounds, steps, n = {}, {}, 0
    for s in order[len(base_steps):]:
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
    req = base_families(depth, kind, scope)
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
    total = len(sent) + len(base)
    if brief:
        said = RUN_COUNTS.search(re.sub(r"\s+", " ", brief))
        runday = re.search(r"\*\*Run\*\*\s*\|\s*([A-Z][a-z]{2} \d{1,2}, \d{4})", brief)
        need_base = bool(runday) and _day(runday.group(1)) >= dt.date.fromisoformat(str(R["osint"]["battery"]["base_since"]))
        if not said:
            fails.append("C21 battery: the brief's Run row does not say 'N searches (B base) in M rounds'")
        elif need_base and said.group(2) is None:
            fails.append("C21 battery: the Run row gives no base count; it says 'N searches (B base) in M rounds'")
        elif (int(said.group(1)), int(said.group(3))) != (total, len(done)) or (said.group(2) is not None and int(said.group(2)) != len(base)):
            fails.append(f"C21 battery: the Run row says {said.group(0)}; the history shows {total} searches ({len(base)} base) in {len(done)} rounds")
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
    return fails, f"{host}: {total} searches ({len(base)} base) in {len(done)} rounds {done}, {ops} round queries with an operator or a domain filter"


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
    first_s = next((i for i, x in enumerate(ev) if x["kind"] == "search"), len(ev))
    empty_at = []
    for i, e in enumerate(ev):
        if e["kind"] != "ask":
            continue
        said = " ".join(x["text"] for x in ev[max(0, i - 4):i] if x["kind"] == "text")
        if not re.search(r"\bskip\b", said, re.I):
            fails.append(f"C22 ask: the question tool '{e['name']}' was called with no line of the reply before it saying what skip does "
                         "('Two quick questions: answer in the popup, or skip and I'll use the recommended answers.')")
        later = next((j for j in range(i + 1, len(ev)) if ev[j]["kind"] == "user"), len(ev))
        body = results.get(e.get("id"))
        if body is not None and NOT_ANSWERED.search(body.strip()) and not re.search(r"answered|selected|\w=\w|\"=\"", body):
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
        for k, v in ledger_facts(brief).items():
            if k[0] and k[0] not in have and not any(k[0] in h or h in k[0] for h in have if h):
                fails.append(f"C23 records: ledger row [{v['n']}] cites {k[0]}, which claims.jsonl does not hold; the brief holds only what the records hold (S4-12)")
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
    """The cited facts of a brief: one per ledger row, keyed by the page it cites (a file name for the user's own files)
    and the row's date, with the number that cites it."""
    out = {}
    for m in SRC_ROW.finditer(md):
        src = m.group(3)
        u = re.search(r"\]\((https?://[^)\s]+)", src) or re.search(r"(https?://[^\s|)]+)", src)
        key = (_page(u.group(1)) if u else re.sub(r"\s+", " ", re.sub(r"[\[\]*]", "", src)).strip().lower(), m.group(5))
        out[key] = dict(n=int(m.group(1)), what=m.group(2))
    return out


def kept_check(draft_md, final_md, allow=()):
    """C24: a fit pass cuts wording, never cited facts (the Codex run, Oct 16: 23 cited facts cut to 18 to fit 3 pages). Every
    ledger row of the first complete draft is still a ledger row of the final brief, still cited in a sentence there, unless the
    user is told why (--allow <page>: a dead link, an excluded topic). Returns the failures."""
    a, b = ledger_facts(draft_md), ledger_facts(final_md)
    ok = {_page(x) if x.startswith("http") else x.lower() for x in allow}
    lost = [(k, v) for k, v in a.items() if k not in b and k[0] not in ok]
    fails = []
    if lost:
        fails.append(f"C24 kept: {len(lost)} of the draft's {len(a)} cited facts are gone from the final brief ({len(b)} remain): "
                     + "; ".join(f"[{v['n']}] {v['what'][:40]} ({k[0]})" for k, v in lost[:4])
                     + (" ..." if len(lost) > 4 else "") + " -- cut wording, never facts (S4-4)")
    secs = _sections(final_md)
    cited = set()
    for k in _body_ids(secs):
        cited |= {int(n) for n in CITE.findall(secs[k])}
    silent = [v["n"] for k, v in b.items() if k in a and v["n"] not in cited]
    if silent:
        fails.append(f"C24 kept: facts {silent} are still in the ledger but no sentence cites them any more; the fact was cut, not the wording")
    return fails


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


def assemble(folder, profile=None, depth=None):
    """Build brief.md and script.md in `folder` from fields.json + the three records + the profile. Returns (brief, script, problems).
    Problems are missing fields, unknown claim ids and uncited text where a form demands a citation: the run fixes fields.json, never
    the output."""
    d, F = pathlib.Path(folder), R["forms"]
    probs = []
    fj, err = _load_json(d / "fields.json")
    if err:
        return "", "", [f"C26 assemble: {err}"]
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
    rr = [r for r in cov.get("rounds", []) if isinstance(r, dict) and r.get("queries")]
    need = battery_floor(depth)[0]
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
    # the page's [n] numbers came from the text above: any block assembled before a later one numbered them in this order
    return brief, script, probs


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
        if u and "linkedin.com" in u.group(1) and tag != "LinkedIn":
            fails.append(f"C25 grading: [{r['n']}] cites linkedin.com but is tagged '{tag}'")
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
    kp = sub.add_parser("kept", help="C24: the final brief holds every cited fact of the first complete draft (cut wording, never facts)")
    kp.add_argument("draft"); kp.add_argument("final"); kp.add_argument("--allow", action="append", default=[], metavar="PAGE",
                    help="a page whose fact was dropped for a reason the user is told (dead link, excluded topic)")
    oc = sub.add_parser("offer-conflict", help="C22: does the request name a different business than the saved offer?")
    oc.add_argument("--saved", required=True); oc.add_argument("--request", required=True)
    ch = sub.add_parser("chat"); ch.add_argument("reply"); ch.add_argument("--target-nouns", default="")
    ch.add_argument("--experience"); ch.add_argument("--authority", choices=["high", "medium"])
    asm = sub.add_parser("assemble", help="C26: build brief.md and script.md from fields.json, the records and the profile (the model never writes them)")
    asm.add_argument("folder"); asm.add_argument("--profile", default=str(pathlib.Path.home() / ".pcp/profile.yaml"))
    asm.add_argument("--depth", choices=["fast", "standard", "deep"]); asm.add_argument("--check", action="store_true", help="fail unless brief.md and script.md are exactly what assemble builds")
    sub.add_parser("hardcoded", help="C27: no value the registry owns is hard-coded in the render scripts")
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
    if a.cmd in ("parity", "hardcoded") and not (HERE / "render_skill.py").exists():
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
            files = [str(found)]
        saved = ""
        if a.profile and pathlib.Path(a.profile).exists():
            import yaml
            pr = yaml.safe_load(pathlib.Path(a.profile).read_text()) or {}
            saved = str(((pr.get("profiles") or {}).get(next(iter(pr.get("profiles") or {}), ""), {}).get("answers", {}).get("Q8", {}) or {}).get("value", ""))
        f, summary = battery([ln for t in files for ln in open(t)], a.depth, text, cited, saved, False if a.no_popup else None, a.kind, a.scope)
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
        brief, script, probs = assemble(a.folder, prof, a.depth)
        if probs:
            print(f"assemble {a.folder}: {len(probs)} problems; fix fields.json, then run again", *[" - " + x for x in probs], sep="\n")
            sys.exit(1)
        pathlib.Path(a.folder, "brief.md").write_text(brief); pathlib.Path(a.folder, "script.md").write_text(script)
        f = schema_check(brief, script) + grading_check(brief)
        print(f"assembled {a.folder}/brief.md and script.md; schema and grading: {len(f)} failures", *[" - " + x for x in f], sep="\n")
        sys.exit(1 if f else 0)
    if a.cmd == "records":
        f = records_check(a.folder, a.depth, pathlib.Path(a.brief).read_text() if a.brief else "")
        print(f"records {a.folder}: {len(f)} failures", *[" - " + x for x in f], sep="\n")
        sys.exit(1 if f else 0)
    if a.cmd == "kept":
        f = kept_check(pathlib.Path(a.draft).read_text(), pathlib.Path(a.final).read_text(), a.allow)
        print(f"kept: draft {len(ledger_facts(pathlib.Path(a.draft).read_text()))} cited facts, final {len(ledger_facts(pathlib.Path(a.final).read_text()))}; {len(f)} failures",
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
