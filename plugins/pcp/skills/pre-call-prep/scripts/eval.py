#!/usr/bin/env python3
"""eval.py -- the pcp run-time instrument: the brief is checked before it is rendered.

  duf <brief.md> [script.md] [--pages N]   decision-useful facts: bound / unbound / dropped / duf_pp (+ coverage)
  checks <brief.md> [script.md] [--all|--swap|--quotes|--custom-q|--sections|--budgets|--never-say|--outcome|--exclusions]
  improve <debrief.yaml>... [--out DIR]    propose row diffs as pcp-proposals-<date>.patch beside the debrief (never lands)

Maintainer commands (self-test, ratchet) live in the source repository: evals/pcp_eval.py.
Exit 0 = pass. Non-zero = fail, with the reason and the population on stdout. Every number prints its denominator.
"""
import argparse
import datetime as dt
import json
import pathlib
import re
import sys

import yaml

HERE = pathlib.Path(__file__).resolve().parent
R = yaml.safe_load((HERE.parent / "pcp.yaml").read_text())
K = R["check_rules"]

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
    body = [k for k in secs if k in K["duf_body_sections"]]
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
        for k in [k for k in secs if k in K["swap_sections"]]:
            for s in _sentences(secs[k]):
                if CITE.search(s):
                    continue
                if nouns and any(n in s.lower() for n in nouns):
                    continue
                fails.append(f"C1 swap: {k}: uncited, non-specific sentence: '{s[:70]}...'")
    if want("quotes"):
        qs = K["quote_section"]
        for q in re.finditer(r"[“\"]([^”\"]{12,})[”\"]", secs.get(qs, "")):
            tail = secs[qs][q.end(): q.end() + 40]
            if not CITE.search(tail):
                fails.append(f"C3 quotes: {qs} quote without [n]: '{q.group(1)[:50]}'")
    if want("custom-q"):
        cq, need_n = K["custom_q_section"], K["custom_q_min_cited"]
        n = sum(1 for ln in secs.get(cq, "").splitlines() if "?" in ln and CITE.search(ln))
        if n < need_n:
            fails.append(f"C4 custom_q: {n}/{need_n} questions in {cq} carry a [n]")
    if want("sections"):
        need = [s["id"] for s in R["brief"]["sections"]] + [b["id"] for b in R["script"]["blocks"] if b["id"] not in K["optional_blocks"]]
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
                if w > budgets[k] * (1 + K["budget_tolerance"]):
                    fails.append(f"C6 budgets: {k} {w} words > {budgets[k]} (+{K['budget_tolerance']:.0%})")
    if want("never-say"):
        for k, body in secs.items():
            if k in K["never_say_allowed_in"]:
                continue
            for p in R["guardrails"]["never_say"]:
                if p.lower() in body.lower():
                    fails.append(f"C7 never_say: '{p}' in {k}")
    if want("outcome"):
        mv = next(c["method_verbs"] for c in R["checks"] if "method_verbs" in c)
        for v in mv:
            if v.lower() in secs.get(K["outcome_section"], "").lower():
                fails.append(f"C8 outcome: method verb '{v}' in {K['outcome_section']}")
    if want("exclusions"):
        kws = K["exclusion_keywords"]
        body = "\n".join(v for k, v in secs.items() if k not in K["exclusion_scan_skips"])
        for topic, words in kws.items():
            for w in words:
                if w.lower() in body.lower():
                    fails.append(f"C9 exclusions: '{w}' ({topic}) in body")
    return fails


# ---------------------------------------------------------------- improve ------------------------------------
def improve(debriefs, out_dir=None):
    """Debriefs -> proposed pcp.yaml row diffs. Writes one patch file and nothing else; never edits the skill."""
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
    out_dir = pathlib.Path(out_dir) if out_dir else pathlib.Path(debriefs[0]).resolve().parent
    out = out_dir / f"pcp-proposals-{dt.date.today().isoformat()}.patch"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(props) + "\n" if props else "# no proposals\n")
    print("wrote", out, f"({len(props)} proposals) -- a maintainer applies them to pcp.yaml only if the ratchet holds")
    return out


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    d = sub.add_parser("duf"); d.add_argument("brief"); d.add_argument("script", nargs="?"); d.add_argument("--pages", type=int)
    c = sub.add_parser("checks"); c.add_argument("brief"); c.add_argument("script", nargs="?"); c.add_argument("--target-nouns", default="")
    for w in ["swap", "quotes", "custom-q", "sections", "budgets", "never-say", "outcome", "exclusions", "all"]:
        c.add_argument(f"--{w}", action="store_true")
    i = sub.add_parser("improve"); i.add_argument("debriefs", nargs="+"); i.add_argument("--out")
    a = ap.parse_args()

    if a.cmd == "duf":
        rep = duf(pathlib.Path(a.brief).read_text(), pathlib.Path(a.script).read_text() if a.script else "", a.pages)
        print(json.dumps(rep, indent=1)); sys.exit(0 if rep["ok"] else 1)
    if a.cmd == "checks":
        which = next((w for w in ["swap", "quotes", "custom-q", "sections", "budgets", "never-say", "outcome", "exclusions"] if getattr(a, w.replace("-", "_"))), "all")
        f = checks(pathlib.Path(a.brief).read_text(), pathlib.Path(a.script).read_text() if a.script else "", which,
                   [n.strip() for n in a.target_nouns.split(",")])
        print(f"checks ({which}): {len(f)} failures"); [print(" -", x) for x in f]; sys.exit(1 if f else 0)

    if a.cmd == "improve":
        improve(a.debriefs, a.out)


if __name__ == "__main__":
    main()
