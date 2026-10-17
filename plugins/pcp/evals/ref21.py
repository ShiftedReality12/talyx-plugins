"""The 2.1.0 checks, frozen verbatim: talyx-ai plugins/pcp/eval.py at upstream/main 993a8be (CITE ... checks).

Never edited. `eval.py gates` runs these beside the live checks on the same probes, so a gate that is looser than 2.1.0 is a
measurement, not an opinion. `R` is the registry as 2.1.0 had it: eval.py fills it from evals/baseline-2.1.0.json before a call."""
import re

R = {}   # filled by eval.py gates: brief.sections, script.blocks (words), guardrails.never_say, checks (method_verbs), page_budget

CITE = re.compile(r"\[(\d+)\]")
SRC_ROW = re.compile(r"^\s*(?:-|\d+\.)?\s*\[(\d+)\]\s*(.+?)\s+--\s+(\S+)\s+--\s+(DIRECT|SEARCH)\s+--\s+(C[1-4])\s+--\s+(\d{4}-\d{2}-\d{2})", re.M)
H2 = re.compile(r"^##\s+(.+)$", re.M)


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
    body = [k for k in secs if re.match(r"B[1-8]$|P[1-6]$", k)]
    return body


# ---------------------------------------------------------------- duf ---------------------------------------
def duf(brief_md, script_md="", pages=None):
    md = brief_md + "\n" + script_md
    secs = _sections(md)
    sources = {}
    dropped = 0
    src_block = secs.get("B9", "")
    for ln in src_block.splitlines():
        if not re.search(r"\[\d+\]", ln):
            continue
        m = SRC_ROW.match(ln)
        if m:
            sources[int(m.group(1))] = dict(claim=m.group(2), url=m.group(3), tag=m.group(4), conf=m.group(5), date=m.group(6))
        else:
            dropped += 1  # a [n] row in Sources missing url/tag/conf/date
    cited = set()
    for k in _body_ids(secs):
        cited |= {int(n) for n in CITE.findall(secs[k])}
    bound = sorted(cited & set(sources))
    dangling = sorted(cited - set(sources))       # cited in body, absent from B9
    unbound = sorted(set(sources) - cited)         # in B9, never used by a move
    pages = pages or R["page_budget"]["total_pages"]
    cov = re.search(r"coverage\s+(\d+)\s*/\s*(\d+)", md, re.I)
    rep = dict(bound=len(bound), unbound=len(unbound), dangling=len(dangling), dropped=dropped,
               sources_total=len(sources) + dropped, pages=pages, duf_pp=round(len(bound) / pages, 2),
               coverage=(f"{cov.group(1)}/{cov.group(2)}" if cov else "MISSING"),
               population=f"body sections {_body_ids(secs) or 'NONE'}; source rows {len(sources)+dropped}")
    rep["ok"] = rep["dangling"] == 0 and rep["unbound"] == 0 and rep["dropped"] == 0 and rep["coverage"] != "MISSING"
    return rep


# ---------------------------------------------------------------- checks -------------------------------------
def _sentences(txt):
    txt = re.sub(r"\|.*\|", " ", txt)  # tables are rows, not sentences
    return [s.strip() for s in re.split(r"(?<=[.!?])\s+", txt) if len(s.strip()) > 25]


def checks(brief_md, script_md="", which="all", target_nouns=()):
    md = brief_md + "\n" + script_md
    secs = _sections(md)
    fails = []
    budgets = {s["id"]: s["words"] for s in R["brief"]["sections"]} | {b["id"]: b["words"] for b in R["script"]["blocks"]}

    def want(name):
        return which in ("all", name)

    if want("swap"):
        nouns = [n.lower() for n in target_nouns if n]
        for k in [k for k in secs if re.match(r"B[1-7]$", k)]:
            for s in _sentences(secs[k]):
                if CITE.search(s):
                    continue
                if nouns and any(n in s.lower() for n in nouns):
                    continue
                fails.append(f"C1 swap: {k}: uncited, non-specific sentence: '{s[:70]}...'")
    if want("quotes"):
        for q in re.finditer(r"[“\"]([^”\"]{12,})[”\"]", secs.get("B2", "")):
            tail = secs["B2"][q.end(): q.end() + 40]
            if not CITE.search(tail):
                fails.append(f"C3 quotes: B2 quote without [n]: '{q.group(1)[:50]}'")
    if want("custom-q"):
        n = sum(1 for ln in secs.get("B5", "").splitlines() if "?" in ln and CITE.search(ln))
        if n < 2:
            fails.append(f"C4 custom_q: {n}/2 questions in B5 carry a [n]")
    if want("sections"):
        need = [s["id"] for s in R["brief"]["sections"]] + [b["id"] for b in R["script"]["blocks"] if b["id"] != "P5"]
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
                w = len(body.split())
                if w > budgets[k] * 1.15:
                    fails.append(f"C6 budgets: {k} {w} words > {budgets[k]} (+15%)")
    if want("never-say"):
        for k, body in secs.items():
            if k in ("B8", "P7"):
                continue
            for p in R["guardrails"]["never_say"]:
                if p.lower() in body.lower():
                    fails.append(f"C7 never_say: '{p}' in {k}")
    if want("outcome"):
        mv = next(c["method_verbs"] for c in R["checks"] if "method_verbs" in c)
        for v in mv:
            if v.lower() in secs.get("B6", "").lower():
                fails.append(f"C8 outcome: method verb '{v}' in B6")
    if want("exclusions"):
        kws = {"health": ["diagnos", "illness", "hospital"], "family": ["divorce", "his wife", "her husband", "children"],
               "political": ["donated to", "FEC", "campaign contribution"], "litigation": ["lawsuit", "sued", "plaintiff"]}
        body = "\n".join(v for k, v in secs.items() if k not in ("B8", "B9", "P7"))
        for topic, words in kws.items():
            for w in words:
                if w.lower() in body.lower():
                    fails.append(f"C9 exclusions: '{w}' ({topic}) in body")
    return fails
