#!/usr/bin/env python3
"""eval.py -- the pcp instrument. The metric comes before the feature.

  duf <brief.md> [script.md] [--pages N]   decision-useful facts: bound / unbound / dropped / duf_pp (+ coverage)
  checks <brief.md> [script.md] [--all|--swap|--quotes|--custom-q|--sections|--budgets|--never-say|--outcome|--exclusions|--plain|--gaps|--conditional]
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
def _sentences(txt):
    txt = re.sub(r"\|.*\|", " ", txt)  # tables are rows, not sentences
    txt = "\n".join(ln for ln in txt.splitlines() if not re.match(r"\s*#|.*(?:Not determined|Evidence tier:)", ln))  # structure, not claims
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
        pw = R["plain_words"]
        own = QUOTED.sub(" ", md)
        hits = re.findall(r"\b(?:" + "|".join(re.escape(w) for w in pw["banned"]) + r")\b", own, re.I) + re.findall(pw["codes"], own)
        for h in sorted(set(hits)):
            fails.append(f"C11 plain: '{h}' outside quoted words")
    if want("gaps"):
        still = next((ln for ln in secs.get(LEDGER, "").splitlines() if "Still open" in ln), "")
        for k in [k for k in secs if re.match(r"B[1-9]$", k)]:
            for label in re.findall(r"\*\*([^*]+?):\*\*\s*Not determined", secs[k]):
                if label.lower() not in still.lower() or "?" not in still:
                    fails.append(f"C12 gaps: {k} '{label}' is Not determined with no question in Still open")
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
    f = checks((fx / "control_broken.md").read_text())
    print("negative control checks:", len(f), "failures:", *[" - " + x for x in f], sep="\n")
    for cid, what in (("C7", "never_say"), ("C9", "exclusions"), ("C11", "plain"), ("C12", "gaps"), ("C13", "conditional")):
        if not any(x.startswith(cid + " ") for x in f):
            print(f"FAIL negative control must trip {cid} ({what})"); ok = False
    if checks((fx / "control_12.md").read_text()):
        print("FAIL positive control must pass every check"); ok = False
    return ok


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


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    d = sub.add_parser("duf"); d.add_argument("brief"); d.add_argument("script", nargs="?"); d.add_argument("--pages", type=int)
    c = sub.add_parser("checks"); c.add_argument("brief"); c.add_argument("script", nargs="?"); c.add_argument("--target-nouns", default="")
    for w in ["swap", "quotes", "custom-q", "sections", "budgets", "never-say", "outcome", "exclusions", "plain", "gaps", "conditional", "all"]:
        c.add_argument(f"--{w}", action="store_true")
    sub.add_parser("concordance"); sub.add_parser("self-test")
    r = sub.add_parser("ratchet"); r.add_argument("--record", action="store_true")
    i = sub.add_parser("improve"); i.add_argument("debriefs", nargs="+")
    a = ap.parse_args()

    if a.cmd == "duf":
        rep = duf(pathlib.Path(a.brief).read_text(), pathlib.Path(a.script).read_text() if a.script else "", a.pages)
        print(json.dumps(rep, indent=1)); sys.exit(0 if rep["ok"] else 1)
    if a.cmd == "checks":
        which = next((w for w in ["swap", "quotes", "custom-q", "sections", "budgets", "never-say", "outcome", "exclusions", "plain", "gaps", "conditional"]
                      if getattr(a, w.replace("-", "_"))), "all")
        f = checks(pathlib.Path(a.brief).read_text(), pathlib.Path(a.script).read_text() if a.script else "", which,
                   [n.strip() for n in a.target_nouns.split(",")])
        print(f"checks ({which}): {len(f)} failures"); [print(" -", x) for x in f]; sys.exit(1 if f else 0)
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
