#!/usr/bin/env python3
"""pcp_eval.py -- maintainer instrument for the pcp registry (source repository only; never installed).

  self-test                 positive + negative controls: the counter is proven able to fail
  ratchet [--record]        every frozen target's duf_pp >= its floor; --record raises floors
  improve <debrief.yaml>... propose row diffs as evals/proposals/<date>.patch (never lands)

Concordance (generated files match pcp.yaml) is `python3 build/generate.py --check`.
The duf/checks logic is imported from the installed skill's scripts/eval.py -- one implementation.
"""
import argparse
import datetime as dt
import importlib.util
import json
import pathlib
import sys

import yaml

HERE = pathlib.Path(__file__).resolve().parent
SKILL = HERE.parent / "plugins/pcp/skills/pre-call-prep"
_spec = importlib.util.spec_from_file_location("pcp_eval_runtime", SKILL / "scripts/eval.py")
ev = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ev)
R = ev.R


def self_test():
    fx = HERE / "fixtures"
    pos = ev.duf((fx / "control_12.md").read_text())
    neg = ev.duf((fx / "control_broken.md").read_text())
    ok = True
    print("positive control:", json.dumps(pos))
    if not (pos["bound"] == 12 and pos["unbound"] == 0 and pos["dropped"] == 0 and pos["ok"]):
        print("FAIL positive control expected bound 12 / unbound 0 / dropped 0"); ok = False
    print("negative control:", json.dumps(neg))
    if not (neg["unbound"] == 3 and neg["dropped"] == 1 and not neg["ok"]):
        print("FAIL negative control expected unbound 3 / dropped 1 / ok False"); ok = False
    f = ev.checks((fx / "control_broken.md").read_text())
    print("negative control checks:", len(f), "failures:", *[" - " + x for x in f], sep="\n")
    if not any(x.startswith("C7") for x in f) or not any(x.startswith("C9") for x in f):
        print("FAIL negative control must trip C7 (never_say) and C9 (exclusions)"); ok = False
    return ok


def ratchet(record=False):
    rf = HERE / "ratchet.json"
    floors = json.loads(rf.read_text()) if rf.exists() else {"policy": R["eval"]["policy"], "floors": {}}
    tdir = HERE / "targets"
    runs = sorted(tdir.glob("*/latest/brief.md"))
    if not runs:
        print(f"ratchet: 0 rendered frozen targets under {tdir} (baseline not yet measured) -- nothing to compare; exit 2")
        return 2
    bad = []
    for b in runs:
        tid = b.parents[1].name
        s = b.parent / "script.md"
        rep = ev.duf(b.read_text(), s.read_text() if s.exists() else "")
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


def improve(debriefs):
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
    out = HERE / "proposals" / f"{dt.date.today().isoformat()}.patch"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(props) or "# no proposals\n")
    print("wrote", out.relative_to(HERE), f"({len(props)} proposals) -- apply to pcp.yaml by hand-review, then `pcp_eval.py ratchet`")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("self-test")
    r = sub.add_parser("ratchet"); r.add_argument("--record", action="store_true")
    i = sub.add_parser("improve"); i.add_argument("debriefs", nargs="+")
    a = ap.parse_args()
    if a.cmd == "self-test":
        return 0 if self_test() else 1
    if a.cmd == "ratchet":
        return ratchet(a.record)
    improve(a.debriefs)
    return 0


if __name__ == "__main__":
    sys.exit(main())
