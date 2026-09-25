#!/usr/bin/env python3
"""pcp_eval.py -- maintainer instrument for the pcp registry (source repository only; never installed).

  self-test                 positive + negative controls: the counter is proven able to fail
  ratchet [--record]        every frozen target's duf_pp >= its floor; --record raises floors
  improve <debrief.yaml>... runtime scripts/eval.py improve, writing to evals/proposals/ (never lands)

Concordance (generated files match pcp.yaml) is `python3 build/generate.py --check`.
The duf/checks/improve logic is imported from the installed skill's scripts/eval.py -- one implementation.
"""
import argparse
import datetime as dt
import importlib.util
import json
import pathlib
import sys

import yaml

HERE = pathlib.Path(__file__).resolve().parent
REPO = HERE.parent
SKILL = REPO / "plugins/pcp/skills/pre-call-prep"
_spec = importlib.util.spec_from_file_location("pcp_eval_runtime", SKILL / "scripts/eval.py")
ev = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ev)
R = ev.R
E = {k: REPO / R["eval"][k] for k in ("positive_control", "negative_control", "frozen_targets_dir", "ratchet_file")}


def self_test():
    pos = ev.duf(E["positive_control"].read_text())
    neg = ev.duf(E["negative_control"].read_text())
    ok = True
    print("positive control:", json.dumps(pos))
    if not (pos["bound"] == 12 and pos["unbound"] == 0 and pos["dropped"] == 0 and pos["ok"]):
        print("FAIL positive control expected bound 12 / unbound 0 / dropped 0"); ok = False
    print("negative control:", json.dumps(neg))
    if not (neg["unbound"] == 3 and neg["dropped"] == 1 and not neg["ok"]):
        print("FAIL negative control expected unbound 3 / dropped 1 / ok False"); ok = False
    f = ev.checks(E["negative_control"].read_text())
    print("negative control checks:", len(f), "failures:", *[" - " + x for x in f], sep="\n")
    if not any(x.startswith("C7") for x in f) or not any(x.startswith("C9") for x in f):
        print("FAIL negative control must trip C7 (never_say) and C9 (exclusions)"); ok = False
    return ok


def ratchet(record=False):
    rf = E["ratchet_file"]
    floors = json.loads(rf.read_text()) if rf.exists() else {"policy": R["eval"]["policy"], "floors": {}}
    tdir = E["frozen_targets_dir"]
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
        print("floors written", rf.relative_to(REPO))
    print(f"ratchet population: {len(runs)} targets, {len(bad)} regress")
    return 1 if bad else 0


def improve(debriefs):
    return ev.improve(debriefs, HERE / "proposals")


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
