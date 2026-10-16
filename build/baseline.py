#!/usr/bin/env python3
"""baseline.py -- freeze the original talyx-ai plug-in (2.1.0) as plugins/pcp/evals/baseline-2.1.0.json.

The no-drift guard (`eval.py parity`) compares the live registry with this manifest: every rule id, parameter, source family, grade
field, layout size, setup question, eval check, eval subcommand and renderer flag of 2.1.0. The manifest is written once, from the
upstream ref, and then only read; changing it is a decision for Daniel, never a side effect of a session.

  python3 build/baseline.py [--ref upstream/main] [--write]
"""
import argparse, json, pathlib, re, subprocess, sys
import yaml

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT = ROOT / "plugins/pcp/evals/baseline-2.1.0.json"


def git_show(ref, path):
    return subprocess.run(["git", "show", f"{ref}:{path}"], cwd=ROOT, capture_output=True, text=True, check=True).stdout


def flatten(o, path=()):
    """{path: leaf}. A list of dicts that carry an id is keyed by the id; any other list is one leaf."""
    out = {}
    if isinstance(o, dict):
        for k, v in o.items():
            out.update(flatten(v, path + (str(k),)))
    elif isinstance(o, list) and o and all(isinstance(x, dict) and ("id" in x or len(x) == 1) for x in o):
        for x in o:
            key = x["id"] if "id" in x else next(iter(x))
            out.update(flatten({k: v for k, v in x.items() if k != "id"} if "id" in x else x[key], path + (str(key),)))
    else:
        out[".".join(path)] = o
    return out


KIND = [("stages.", "rule"), ("calibration.questions", "question"), ("calibration.rules", "rule"), ("families", "family"), ("research", "param"),
        ("page_budget", "layout"), ("brief.sections", "block"), ("script", "block"), ("rubric", "param"), ("checks", "check"),
        ("exclusions", "param"), ("registers", "param"), ("guardrails", "param"), ("retention", "param"), ("eval", "param")]


def kind_of(p):
    return next((k for pre, k in KIND if p.startswith(pre)), "param")


def build(ref):
    reg = yaml.safe_load(git_show(ref, "plugins/pcp/pcp.yaml"))
    items = {}
    for p, v in flatten(reg).items():
        if p.startswith(("generated_files", "render_header", "registry_version")):
            continue
        items[p] = dict(kind=kind_of(p), value=v)
    ev = git_show(ref, "plugins/pcp/eval.py")
    for name in re.findall(r'sub\.add_parser\("([\w-]+)"', ev):
        items[f"eval.subcommand.{name}"] = dict(kind="command", value=True)
    for name in re.findall(r'c\.add_argument\(f?"--([\w-]+)"', ev) + re.findall(r'for w in CHECKS[^\n]*', ev):
        pass
    m = re.search(r"CHECKS = \[(.*?)\]", ev, re.S)
    for name in re.findall(r'"([\w-]+)"', m.group(1)) if m else []:
        items[f"eval.check_flag.{name}"] = dict(kind="command", value=True)
    pdf = git_show(ref, "plugins/pcp/format/talyx_pdf.py")
    for flag in re.findall(r'add_argument\("(--[\w-]+)"', pdf):
        items[f"renderer.flag.{flag}"] = dict(kind="command", value=True)
    return {"source": f"{ref} ({subprocess.run(['git', 'rev-parse', '--short', ref], cwd=ROOT, capture_output=True, text=True).stdout.strip()}), talyx-ai plug-in 2.1.0",
            "count": len(items), "items": items}


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--ref", default="upstream/main")
    ap.add_argument("--write", action="store_true")
    a = ap.parse_args()
    b = build(a.ref)
    if a.write:
        OUT.write_text(json.dumps(b, indent=1, ensure_ascii=False, sort_keys=True, default=str) + "\n")
        print("wrote", OUT.relative_to(ROOT), b["count"], "items")
    else:
        print(b["source"], b["count"], "items (use --write)")
