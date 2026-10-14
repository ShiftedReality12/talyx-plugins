#!/usr/bin/env python3
"""eval.py -- the pcp instrument. The metric comes before the feature.

  duf <brief.md> [script.md] [--pages N]   decision-useful facts: bound / unbound / dropped / duf_pp (+ coverage)
  checks <brief.md> [script.md] [--all|--swap|--quotes|--custom-q|--sections|--budgets|--never-say|--outcome|--exclusions|--plain|--gaps|--conditional|--layout]
  checks <OUT.pdf> --plain                  plain words on the printed text (masthead, band and footer included)
  pdf <OUT.pdf> [brief.md]                  the rendered PDF: page count, script on its page, ledger last before it, footer, links, plain words
  concordance                               SKILL.md + commands/pcp.md match a fresh render of pcp.yaml
  self-test                                 positive + negative controls: the counter is proven able to fail
  ratchet [--record]                        every frozen target's duf_pp >= its floor; --record raises floors
  improve <debrief.yaml>...                 propose row diffs as evals/proposals/<date>.patch (never lands)

Exit 0 = pass. Non-zero = fail, with the reason and the population on stdout. Every number prints its denominator.
"""
import argparse
import datetime as dt
import json
import pathlib
import re
import subprocess
import sys

HERE = pathlib.Path(__file__).resolve().parent
R = json.loads((HERE / "pcp.json").read_text())   # pcp.yaml as JSON (render_skill.py): no YAML library needed at run time
LEDGER = R["brief"]["sections"][-1]["id"]          # B10, the evidence ledger

CITE = re.compile(r"\[(\d+)\]")
TAGS, GRADES, CONFS = "Direct|Search|LinkedIn|Yours", "Measured|Derived|Inference|Not determined", "Primary|Reputable|Single source|Inferred"
SRC_ROW = re.compile(r"^\|\s*\[(\d+)\]\s*\|\s*([^|]+?)\s*\|\s*([^|\s][^|]*?)\s*\|\s*(" + TAGS + r")\s*\|\s*(" + GRADES + r")\s*\|\s*("
                     + CONFS + r")\s*\|\s*([A-Z][a-z]{2} \d{1,2}, \d{4})\s*\|", re.M)
H2 = re.compile(r"^##\s+(.+)$", re.M)
QUOTED = re.compile(r"[\u201c\"][^\u201d\"]*[\u201d\"]")   # their own words are exempt from plain words
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
            sources[int(m.group(1))] = dict(claim=m.group(2), source=m.group(3), tag=m.group(4), grade=m.group(5), conf=m.group(6), date=m.group(7))
        else:
            dropped += 1  # a [n] ledger row missing its source, tag, grade, conf. or date
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
    hits = re.findall(r"\b(?:" + "|".join(re.escape(w) for w in pw["banned"]) + r")\b", own, re.I) + re.findall(pw["codes"], own)
    return sorted(set(hits))


def _sentences(txt):
    txt = re.sub(r"\|.*\|", " ", txt)  # tables are rows, not sentences
    txt = "\n".join(ln for ln in txt.splitlines()   # structure and the registry's own fallback lines, not claims
                    if not re.match(r"\s*#|.*(?:Not determined|Evidence tier:|No counter-evidence found)", ln))
    return [s.strip() for s in re.split(r"(?<=[.!?])\s+", txt) if len(s.strip()) > 25]


def _gaps(secs):
    """[(block, label, 'Not determined'|'No read')]: each **Label:** Not determined line, each table row with a
    Not determined or No read cell (its label: the row's first other cell, up to a colon), in B1-B9."""
    out = []
    for k in [k for k in secs if re.match(r"B[1-9]$", k)]:
        out += [(k, label, "Not determined") for label in re.findall(r"\*\*([^*]+?):\*\*\s*Not determined", secs[k])]
        for ln in secs[k].splitlines():
            cells = [c.strip() for c in ln.strip().strip("|").split("|")] if ln.lstrip().startswith("|") else []
            gap = next((c.rstrip(".") for c in cells if c.rstrip(".") in ("Not determined", "No read")), None)
            if gap:
                other = next((c for c in cells if c.rstrip(".") != gap), "")
                label = CITE.sub("", re.sub(r"\*\*|\*", "", other)).split(":")[0].strip()
                out.append((k, label or gap, gap))
    return out


def _words(t):
    return len(WORD.findall(CITE.sub(" ", t.replace("*", ""))))


def checks(brief_md, script_md="", which="all", target_nouns=(), experience=None):
    """experience: the profile's Q9 answer (new|experienced|top); C15 runs only when it is given."""
    md = brief_md + "\n" + script_md
    secs = _sections(md)
    fails = []
    budgets = {s["id"]: s["words"] for s in R["brief"]["sections"]} | {b["id"]: b["words"] for b in R["script"]["blocks"]}

    def want(name):
        return which in ("all", name)

    if want("swap"):
        nouns = [n.lower() for n in target_nouns if n]
        for k in [k for k in secs if re.match(r"B1$|B[3-8]$", k)]:   # the blocks that state facts about the person
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
        kws = {"health": ["diagnos", "illness", "hospital"], "family": ["divorce", "his wife", "her husband", "children"],
               "political": ["donated to", "FEC", "campaign contribution"], "litigation": ["lawsuit", "sued", "plaintiff"]}
        body = "\n".join(v for k, v in secs.items() if k not in (LEDGER, "P8"))
        for topic, words in kws.items():
            for w in words:
                if w.lower() in body.lower():
                    fails.append(f"C9 exclusions: '{w}' ({topic}) in body")
    if want("plain"):
        for h in plain_hits(md):
            fails.append(f"C11 plain: '{h}' outside quoted words")
    if want("gaps"):
        still = next((ln for ln in secs.get(LEDGER, "").splitlines() if "Still open" in ln), "")
        gaps = _gaps(secs)
        for k, label, what in gaps:
            if label.lower() not in still.lower() or "?" not in still:
                fails.append(f"C12 gaps: {k} '{label}' is {what} with no question in Still open")
        if still.count("?") < len(gaps):
            fails.append(f"C12 gaps: {len(gaps)} gaps in B1-B9 but {still.count('?')} questions in Still open")
        starts = R["socratic"]["room"]["question_starts"]
        cell = re.sub(r"\*\*Still open\*\*|\*\*", "", still).strip(" |")
        for item in [i.strip() for i in re.split(r"\s+·\s+", cell) if i.strip()]:
            q = item.split(": ", 1)[1] if ": " in item else item
            if not (q.rstrip().endswith("?") and q.split()[0].strip("*_").capitalize() in starts) and (gaps or "?" in item):
                fails.append(f"C12 gaps: Still open item is not a question starting {'/'.join(starts)}: '{item[:60]}'")
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
        if "P5" in secs and tier == "low":
            fails.append("C13 conditional: P5 Read the room printed at evidence tier low")
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
    """The rendered PDF, as the reader gets it (C10, and C11 on the printed text). [] = pass; None = no PDF text tool."""
    pages = pdf_pages(pdf)
    if pages is None:
        return None
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
        foot = f"page {len(pages)} of {len(pages)}"
        if pages[-1].count(foot) != 1:
            fails.append(f"C10 pages: last page shows '{foot}' {pages[-1].count(foot)} times, need once")
    for h in plain_hits(re.sub(r"\s+", " ", "\n".join(pages))):
        fails.append(f"C11 plain: '{h}' printed in the PDF outside quoted words")
    if brief_md:
        rows = [m for m in SRC_ROW.finditer(brief_md) if m.group(4) != "Yours"]
        links = pdf_links(pdf)
        if len(links) < len(rows):
            fails.append(f"C10 links: {len(links)} links in the PDF < {len(rows)} ledger rows not tagged Yours")
    return fails


# ---------------------------------------------------------------- concordance --------------------------------
def concordance():
    try:
        r = subprocess.run([sys.executable, str(HERE / "render_skill.py"), "--check"], capture_output=True, text=True, timeout=60)
    except subprocess.TimeoutExpired:
        print("CONCORDANCE FAIL: render_skill.py --check exceeded 60s")
        return False
    print(r.stdout.strip())
    return r.returncode == 0


# ---------------------------------------------------------------- self-test ----------------------------------
def self_test():
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
    for name, kw in MUST_PASS:
        f = checks((fx / name).read_text(), **kw)
        if f:
            print(f"FAIL {name} {kw or ''} must pass every check:", *f, sep="\n - "); ok = False
        else:
            print(f"passes: {name} {kw or ''}")
    return ok


# fixture -> passes every check (with these arguments)
MUST_PASS = [
    ("control_12.md", {}),
    ("control_12.md", {"experience": "experienced"}),
    ("control_12.md", {"experience": "top"}),
    ("exp_new.md", {"experience": "new"}),
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
]


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


CHECKS = ["swap", "quotes", "custom-q", "sections", "budgets", "never-say", "outcome", "exclusions", "plain", "gaps", "conditional", "layout"]


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    d = sub.add_parser("duf"); d.add_argument("brief"); d.add_argument("script", nargs="?"); d.add_argument("--pages", type=int)
    c = sub.add_parser("checks"); c.add_argument("brief"); c.add_argument("script", nargs="?"); c.add_argument("--target-nouns", default="")
    for w in CHECKS + ["all"]:
        c.add_argument(f"--{w}", action="store_true")
    c.add_argument("--experience", choices=[o["value"] for q in R["calibration"]["questions"] if q["id"] == "Q9" for o in q["options"]],
                   help="the profile's Q9 answer: runs C15 with --all")
    p = sub.add_parser("pdf"); p.add_argument("pdf"); p.add_argument("brief", nargs="?")
    sub.add_parser("concordance"); sub.add_parser("self-test")
    r = sub.add_parser("ratchet"); r.add_argument("--record", action="store_true")
    i = sub.add_parser("improve"); i.add_argument("debriefs", nargs="+")
    a = ap.parse_args()

    if a.cmd == "duf":
        rep = duf(pathlib.Path(a.brief).read_text(), pathlib.Path(a.script).read_text() if a.script else "", a.pages)
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
                       [n.strip() for n in a.target_nouns.split(",")], a.experience)
        print(f"checks ({which}): {len(f)} failures"); [print(" -", x) for x in f]; sys.exit(1 if f else 0)
    if a.cmd == "pdf":
        f = pdf_check(a.pdf, pathlib.Path(a.brief).read_text() if a.brief else "")
        if f is None:
            print("pdf: no pdftotext or pypdf to read the PDF -- not run"); sys.exit(2)
        print(f"pdf {a.pdf}: {len(f)} failures"); [print(" -", x) for x in f]; sys.exit(1 if f else 0)
    if a.cmd == "concordance":
        sys.exit(0 if concordance() else 1)
    if a.cmd == "self-test":
        sys.exit(0 if self_test() else 1)
    if a.cmd == "ratchet":
        sys.exit(ratchet(a.record))
    if a.cmd == "improve":
        improve(a.debriefs)


if __name__ == "__main__":
    main()
