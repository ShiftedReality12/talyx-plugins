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
import pathlib
import re
import shutil
import subprocess
import sys

HERE = pathlib.Path(__file__).resolve().parent
R = json.loads((HERE / "pcp.json").read_text())   # pcp.yaml as JSON (render_skill.py): no YAML library needed at run time
LEDGER = R["brief"]["sections"][-1]["id"]          # B10, the evidence ledger

CITE = re.compile(r"\[(\d+)\]")
TAGS, GRADES, CONFS = "Direct|Search|LinkedIn|Yours", "Measured|Derived|Inference|Not determined", "Primary|Reputable|Single source|Inferred"
# Printed ledger (Ben, Oct 13): | # | What it says | Source | Grade | Date |. Tag and confidence stay in claims.jsonl.
SRC_ROW = re.compile(r"^\|\s*\[(\d+)\]\s*\|\s*([^|]+?)\s*\|\s*([^|\s][^|]*?)\s*\|\s*(" + GRADES + r")\s*\|\s*"
                     r"((?:seen )?[A-Z][a-z]{2}(?: \d{1,2},)? \d{4})\s*\|", re.M)


def _tag(source):
    """The printed ledger has no Tag column: a source with no link is Yours, a linkedin.com link is LinkedIn."""
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

    def want(name):
        return which in ("all", name)

    if want("cites"):
        fails += cite_relevance(brief_md)
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
            if not any("linkedin.com/in/" in m.group(3).lower() for m in SRC_ROW.finditer(grid)):
                fails.append(f"C16 linkedin: {li['read']['search']}, yet no ledger row cites the linkedin.com/in profile it showed")
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
    import tempfile
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
        a, b = (lines.get(title[c]) for c in cols)
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
    import tempfile
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
          "linkedin", "cites", "quality"]


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
    lk = sub.add_parser("links"); lk.add_argument("pdf")
    rc = sub.add_parser("render"); rc.add_argument("pdf")
    ch = sub.add_parser("chat"); ch.add_argument("reply"); ch.add_argument("--target-nouns", default="")
    ch.add_argument("--experience"); ch.add_argument("--authority", choices=["high", "medium"])
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
        res = link_status(sorted(set(pdf_links(a.pdf))))
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
    if a.cmd == "ratchet":
        sys.exit(ratchet(a.record))
    if a.cmd == "improve":
        improve(a.debriefs)


if __name__ == "__main__":
    main()
