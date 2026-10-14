#!/usr/bin/env python3
"""adapters.py -- every host's install files for the pcp plug-in, from build/plugin.source.json.

The plug-in is plugins/pcp, as in v2.0.0. Its skill and command are written by plugins/pcp/render_skill.py
from pcp.yaml; this writes only what each host needs to find and install it:

  .claude-plugin/marketplace.json            catalog: Claude desktop (Cowork), Claude Code; also Antigravity
  .agents/plugins/marketplace.json           catalog: ChatGPT, Codex
  .cursor-plugin/marketplace.json            catalog: Cursor
  .grok-plugin/marketplace.json              catalog: Grok
  plugins/pcp/.claude-plugin/plugin.json     Claude
  plugins/pcp/.codex-plugin/plugin.json      ChatGPT, Codex (presentation; plugin.json carries none)
  plugins/pcp/.cursor-plugin/plugin.json     Cursor
  plugins/pcp/.grok-plugin/plugin.json       Grok
  plugins/pcp/.devin-plugin/plugin.json      Devin
  plugins/pcp/plugin.json                    Agent Plugins 1.0.0: Gemini (Antigravity CLI), any other host
  plugins/pcp/gemini-extension.json          Gemini CLI
  plugins/pcp/skills/*/  eval.py, pcp.yaml, format/, evals/   exact copies of the plug-in files each skill
                                             names, at the same relative paths: hosts without the /pcp
                                             command resolve them from the skill's own folder
  adapters/perplexity/pre-call-prep.zip      Perplexity: the pre-call-prep skill folder
  adapters/chat/{instructions.txt,pcp-knowledge.md}   Gemini app (Gem), Microsoft 365 Copilot: no scripts,
                                             no PDF; the chat wording lives here, pcp.yaml stays as it is
  adapters/grok/{instructions.txt,pcp-knowledge.md}   the Grok app (a Project): the same two files

Usage:
  python3 build/adapters.py            write them
  python3 build/adapters.py --check    exit 1 if any differs from a fresh render
"""
import argparse
import copy
import hashlib
import importlib.util
import io
import json
import pathlib
import re
import sys
import zipfile

import yaml

ROOT = pathlib.Path(__file__).resolve().parent.parent
PLUGIN = ROOT / "plugins" / "pcp"
SRC = {k: v for k, v in json.loads((ROOT / "build" / "plugin.source.json").read_text()).items() if not k.startswith("_")}
META = {k: SRC[k] for k in ("name", "version", "description", "author", "homepage", "repository", "license", "keywords")}
RENDERER = ["format/talyx_pdf.py", "format/assets/archivo-variable.woff2", "format/assets/talyx-logo-navy-base64.txt"]
# the plug-in files each skill's instructions name (v2.0.0 paths, relative to the plug-in)
NAMED = {"pre-call-prep": ["eval.py", "pcp.yaml", "pcp.json", *RENDERER, "evals/debrief_template.yaml", "evals/ratchet.json"],
         "talyx-pdf": RENDERER}


def dump(obj):
    return json.dumps(obj, indent=2, ensure_ascii=False) + "\n"


def catalog():
    m = SRC["marketplace"]
    entry = {"name": SRC["name"], "description": SRC["description"], "version": SRC["version"], "author": SRC["author"],
             "homepage": SRC["homepage"], "license": SRC["license"], "category": SRC["category"],
             "keywords": SRC["keywords"], "source": "./plugins/pcp"}
    return {"name": m["name"], "owner": m["owner"], "metadata": {"description": m["description"], "version": SRC["version"]},
            "plugins": [entry]}


def codex_catalog():
    m = SRC["marketplace"]
    return {"name": m["name"], "interface": {"displayName": m["displayName"]},
            "plugins": [{"name": SRC["name"], "source": {"source": "local", "path": "./plugins/pcp"},
                         "policy": m["policy"], "category": SRC["interface"]["category"]}]}


def perplexity_zip(files):
    """The pre-call-prep folder as it will be written. Deterministic: stored, fixed dates and modes, sorted."""
    skill = PLUGIN / "skills" / "pre-call-prep"
    members = {p.relative_to(skill).as_posix(): p.read_bytes() for p in skill.rglob("*")
               if p.is_file() and p.name != ".DS_Store" and "__pycache__" not in p.parts}
    prefix = "plugins/pcp/skills/pre-call-prep/"
    members |= {rel[len(prefix):]: data for rel, data in files.items() if rel.startswith(prefix)}
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_STORED) as zf:
        for rel in sorted(members):
            info = zipfile.ZipInfo(rel, date_time=(2026, 1, 1, 0, 0, 0))
            info.create_system, info.external_attr = 3, (0o755 if rel.endswith(".py") else 0o644) << 16
            zf.writestr(info, members[rel])
    return buf.getvalue()


# ── the chat adapter (Gemini app, Microsoft 365 Copilot): no scripts, no files, no PDF ─────────────────

# pcp.yaml items reworded or left out for a host that runs no code; everything else is rendered as is
CHAT_ROWS = {
    "S4-11": {"text": "Fact density (the ratchet's metric, decision-useful facts per page, never drops). Standard depth aims at 18 or more distinct cited facts across the 3 pages, at least 6 per page. Spend words on facts, not framing: a line that can carry a new cited fact carries one; cut uncited connective sentences; each B2 question, B3 bullet, B5 row, B8 bullet and P3 answer rests on a different [n] where the evidence allows. Before writing Not determined for Role since, Path, The organization or Decision maker, run one targeted search of the primary source (official bio, annual report or proxy statement, newsroom); for a public company these are almost always public. The ledger's What it says stays under 8 words so each row is one line. Each No read or Not determined also costs a Still open question, so evidence that fills a gap frees space for a fact: search two long-form interviews or earnings-call remarks for the six reads before writing No read. Keep each Still open question under 10 words. Before rendering, count the distinct cited facts: below 18, replace a repeated [n], an uncited line or a filled-in-able gap with a new cited fact from the claims, then re-check fit; if the brief overflows, cut words, not facts.", "test": "On the frozen targets, decision-useful facts per page meet each floor at 10 pt and 3 pages."},
    "CAL-1": {"text": "Ask only the questions the Saved setup block has no answer for -- all of them the first time, all again with --recalibrate. Otherwise read it silently.",
              "test": "An empty Saved setup block -- the run asks every question. A complete one -- it asks none."},
    "CAL-2": {"text": "A skipped answer takes the first (Recommended) option and is stored with defaulted:true; the heading shows Prepared for and Depth.",
              "test": "Skip Q5 -- the Saved setup block shows Q5 standard, defaulted true; the heading reads \"Depth: standard\"."},
    "CAL-3": None,   # the improve loop is a script
    "CAL-4": {"text": "Files the user attaches about their business are read once; a summary of at most 150 words goes in the Saved setup block under context. Facts from them are tagged Yours, never presented as public. Supported: .pdf .docx .md .txt .csv. Any other file gets one line naming the supported types, and the Saved setup block is not changed.",
              "test": "Attach a one-page file -- the updated Saved setup block holds its summary, and a fact from it carries tag Yours. Attach a .pptx -- one line names the supported types and no new block is given."},
    "S2-2": {"test": "A claim missing any field is dropped and counted in coverage.dropped."},
    "S2-7": {"text": "LinkedIn only from a profile the user saves and attaches; never open LinkedIn. Ask once, in one line: 'Do you have <name>'s LinkedIn profile saved as a PDF (on their profile: More > Save to PDF) or as copied text? Attach it and I'll use it as your file; nothing else from LinkedIn is read.' Attached: its facts are tagged Yours, the source is the file name, and B4's last line is '**LinkedIn:** read from your file' and the Coverage row 'LinkedIn: read from your file'. Not attached: '**LinkedIn:** not read: file not given' and 'LinkedIn: not read: file not given'; no fact is tagged LinkedIn, and Still open asks nothing about LinkedIn.",
             "test": "No attachment -- B4 and Coverage both read 'LinkedIn: not read: file not given' and Still open asks nothing about LinkedIn; a profile PDF attached -- both read 'read from your file' and its facts carry tag Yours (check C16)."},
    "S4-1": {"test": "Check C2 finds unbound > 0 -- the answer is rewritten before it is delivered."},
    "S4-3": None, "S4-4": None,   # the PDF renderer
    "S4-10": {"text": "This host cannot make the PDF, so always deliver the full brief in the chat, never a summary: first line exactly 'Intelligence Brief (in chat: this app cannot make the PDF, so the same 3 pages follow as text)'; the heading lines; '--- Page 1 ---' and B1-B6; '--- Page 2 ---' and B7-B10 with the 5-column ledger and its Coverage / Still open / Left out on purpose / Run rows; '--- Page 3 ---' and '# Meeting script' with P1-P9. Same blocks, order, titles, word budgets, citations, grades and plain-words rules. Apply the checks yourself and end with 'Checks: self-reviewed, not run as code'.",
              "test": "The reply holds the label, the three page markers and every block title in order."},
    "S4-5": {"text": "The heading's meta line carries meeting, prepared for, depth, sources, status and date; the ledger's Run row carries the run details.",
             "test": "The heading has all six fields."},
    "S4-7": {"test": "Write **Decision maker:** Not determined with no question in Still open -- check C12 fails."},
    "S4-8": {"test": "Put SOCMINT in B3 -- check C11 fails."},
    "S4-9": {"test": "Set Q9 new -- P1, P3 and P4 each carry a Why line; set experienced -- none does. Check C15 fails otherwise."},
}
CHAT_INPUTS = {"arguments": {"type": "'Full Name, Organisation' | a pasted list", "source": "the user's message"},
               "profile": {"source": "Saved setup block"}}

CHAT_STAGE0 = """This host runs no scripts. The saved setup is the **Saved setup** block at the end of this knowledge file.

- Every question has a saved answer there -- use them silently. Ask nothing.
- Otherwise ask ONLY the unanswered questions, in one chat message with numbered options, first option recommended.
- A skipped question takes its first (Recommended) option, marked defaulted.
- Then output the complete updated **Saved setup** block in the same YAML shape -- each answer as
  `Q1: {value: <option value or your text>, defaulted: false}` under `profiles: default: answers:` -- and tell
  the user to replace the block in this knowledge file with it, so the next conversation does not ask again.
  Never claim it was saved: only the user can update the file.
- `--recalibrate` in the user's message asks every question again, showing the saved answer."""

CHAT_DELIVER = """## Deliver

This host has no PDF renderer and cannot run the checks as code. Apply every check in the table above
yourself before answering, and say they were self-checked, not machine-run. Deliver ONE document: the
{deliverable} (B1-B10) then the {script} (P1-P9), headed with the identity and meta lines. Say what
was NOT found before what was. Say plainly that it is not the Talyx PDF; the plug-in version
renders that.

## After the call

After the call, ask for four things -- facts used (claim ids), questions that landed, band
accuracy per dimension (hit or miss), outcome -- and nothing else.

"""

CHAT_INSTRUCTIONS = """You are Talyx Pre-call Prep. Before a meeting you research the named person, company or deal from public sources and the user's own files, and write one cited Intelligence Brief plus a one-page meeting script.

Follow pcp-knowledge.md exactly, in stage order: calibrate, intake, collect, read, brief and script, after the call. It holds the questions, source types, exclusions, rubric, page budgets and checks. Where it and this text differ, it wins.

Calibration is asked once. The Saved setup block at the end of pcp-knowledge.md holds the saved answers. Ask only the questions it has no answer for, then give the user the updated block to paste into their copy of pcp-knowledge.md. Never say it was saved: only the user can update that file.

Never start research without a full name and an organisation. If two people match, stop and ask. Public sources, plus files the user attaches: you cannot open LinkedIn here, so offer to read a profile the user saves as a PDF. Every fact carries a numbered citation to a source you actually opened. Say what you could not find before what you found. Never invent a fact, a quote or a source.

This host has no PDF renderer and runs no code. Apply the checks yourself and say they were self-checked. Deliver one document and say it is not the Talyx PDF.
"""


def _chat_registry(R):
    """pcp.yaml as a no-script host sees it: CHAT_ROWS / CHAT_INPUTS applied, the PDF outputs, the ratchet
    stage and the page check left out."""
    C = copy.deepcopy(R)

    def rows(items):
        return [{**r, **CHAT_ROWS[r["id"]]} if CHAT_ROWS.get(r["id"]) else r for r in items
                if not (r["id"] in CHAT_ROWS and CHAT_ROWS[r["id"]] is None)]
    C["calibration"]["rules"] = rows(C["calibration"]["rules"])
    C["stages"] = [s for s in C["stages"] if s["id"] != "S5"]   # the chat file's own Debrief asks the four fields
    for s in C["stages"]:
        s["rows"] = rows(s["rows"])
        s["inputs"] = [{**i, **CHAT_INPUTS[i["name"]]} if i["name"] in CHAT_INPUTS else i for i in s["inputs"]]
        if s["id"] == "S4":
            s.pop("outputs", None)   # brief.md, script.md and the PDF are files
    C["checks"] = [c for c in C["checks"] if c.get("id") != "C10"]
    return C


def _section(text, heading, new, until):
    """Replace from `heading` up to (not including) `until` with `new`."""
    a = text.index(heading)
    return text[:a] + new + text[text.index(until, a):]


def chat_knowledge():
    sys.dont_write_bytecode = True   # importing the renderer must not leave __pycache__ in the plug-in
    spec = importlib.util.spec_from_file_location("render_skill", PLUGIN / "render_skill.py")
    rs = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(rs)
    raw = (PLUGIN / "pcp.yaml").read_bytes()
    R = yaml.safe_load(raw)
    C = _chat_registry(R)
    text = rs.render_skill(C, hashlib.sha256(raw).hexdigest()[:12])
    text = text[text.index("\n---\n") + 5:]   # a knowledge file has no skill frontmatter
    n = R["names"]
    text = text.replace(f"The deliverable is one 3-page PDF, the {n['deliverable']}.", f"The deliverable is one document: the {n['deliverable']}, then the {n['script']}.")
    text = text.replace("`references/socratic-questions.md`", "the Socratic questions section below").replace("references/socratic-questions.md", "the Socratic questions section below")
    s0 = text.index("## Stage 0")
    text = text[:s0] + "## Stage 0: Calibrate (once)\n\n" + CHAT_STAGE0 + "\n\n" + text[text.index("| # | Chip", s0):]
    text = text.replace(f"## The PDF: pages 1-2, the {n['deliverable']}", f"## The {n['deliverable']}").replace(f"## The PDF: page 3, the {n['script']}", f"## The {n['script']}")
    text = re.sub(r"Word budgets are the page budget; the renderer fails[^\n]*",
                  "Word budgets are length limits: cut to fit, never run over (check C6).", text)
    checks = "\n".join(["| Id | Check | Passes when |", "|---|---|---|"] +
                       [f"| {c['id']} | {c['name']} | {c['passes_when']} |" for c in C["checks"] if "cmd" in c])
    text = _section(text, "## Checks", f"## Checks (all pass before delivery)\n\n{checks}\n\n", "## Render")
    text = _section(text, "## Render", CHAT_DELIVER.format(**n), "## About")
    socratic = rs.render_socratic(R, hashlib.sha256(raw).hexdigest()[:12]).split("\n", 2)[2]   # without its generated-file header
    blank = {"pcp_profile_format": 1, "profiles": {"default": {"answers": {}}}}
    return (text + "\n" + socratic.replace("# Socratic questions", "## Socratic questions", 1)
            + "\n## Saved setup\n\nReplace this block with the one the assistant gives you after setup.\n\n"
            "```yaml\n" + yaml.safe_dump(blank, sort_keys=False) + "```\n")


# user-facing documents, held to plain words like the listing; a README's contributor section is not user-facing
USER_DOCS = {"README.md": None, "plugins/pcp/README.md": "## How it is built (for contributors)",
             "adapters/chat/README.md": None, "adapters/grok/README.md": None}


def check_listing(files):
    """The listing text every host shows, the READMEs and the chat instructions are user-facing: plain words
    (pcp.yaml plain_words)."""
    spec = importlib.util.spec_from_file_location("render_skill", PLUGIN / "render_skill.py")
    rs = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(rs)
    R = yaml.safe_load((PLUGIN / "pcp.yaml").read_text())
    texts = {"build/plugin.source.json listing text": [SRC["description"], *[v for v in SRC["interface"].values() if isinstance(v, str)],
                                                      *SRC["interface"]["defaultPrompt"]],
             "adapters/chat/instructions.txt": [files["adapters/chat/instructions.txt"]]}
    for rel, stop in USER_DOCS.items():
        t = (ROOT / rel).read_text()
        texts[rel] = [t.split(stop)[0] if stop else t]
    out = []
    for where, ts in texts.items():
        bad = rs.plain_violations(R, ts)
        if bad:
            out.append(f"{where} uses {', '.join(bad)} -- plain words")
    return out


def check_names(files):
    """The deliverable has one name: no other name (pcp.yaml plain_words.names_banned) anywhere in the repo or in
    what this writes. A line that lists banned words is the list itself, not a use."""
    R = yaml.safe_load((PLUGIN / "pcp.yaml").read_text())
    pat = re.compile(r"\b(?:" + "|".join(re.escape(w) for w in R["plain_words"]["names_banned"]) + r")\b", re.I)
    texts = {p.relative_to(ROOT).as_posix(): p.read_bytes() for p in ROOT.rglob("*")
             if p.is_file() and ".git" not in p.relative_to(ROOT).parts and "__pycache__" not in p.parts}
    texts |= {rel: (d if isinstance(d, bytes) else d.encode()) for rel, d in files.items()}
    out = []
    for rel, data in sorted(texts.items()):
        try:
            text = data.decode()
        except UnicodeDecodeError:
            continue   # the zip, fonts, images: the zip's text members are checked as the files they copy
        for i, ln in enumerate(text.splitlines(), 1):
            if "banned" in ln:
                continue
            for m in pat.finditer(ln):
                out.append(f"{rel}:{i} uses '{m.group(0)}' -- the deliverable is the {R['names']['deliverable']}")
    return out


def check_version():
    """One version everywhere: pcp.yaml registry_version is the plug-in's version (plugin.source.json)."""
    reg = str(yaml.safe_load((PLUGIN / "pcp.yaml").read_text())["registry_version"])
    return [] if reg == SRC["version"] else [f"pcp.yaml registry_version {reg} != build/plugin.source.json version {SRC['version']}"]


def check_chat(text):
    """A chat host has no scripts or files: the knowledge file must never send the model to one, and must carry
    the Socratic questions itself."""
    body = text.split("\n", 1)[1]   # line 1 is the generated-file header
    hits = sorted(set(re.findall(r"scripts/[\w.-]*|\b[\w-]+\.py\b|~/\.\w+|\$ARGUMENTS|AskUserQuestion", body)))
    out = [f"adapters/chat/pcp-knowledge.md names {', '.join(hits)} -- reword it in CHAT_ROWS / CHAT_INPUTS"] if hits else []
    if body.count("\n## Socratic questions\n") != 1:
        out.append("adapters/chat/pcp-knowledge.md must hold one '## Socratic questions' section")
    return out


def check_zip(data):
    """The Perplexity skill must carry the Socratic reference exactly once (SKILL.md sends the model to it)."""
    names = zipfile.ZipFile(io.BytesIO(data)).namelist()
    n = names.count("references/socratic-questions.md")
    return [] if n == 1 else [f"adapters/perplexity/pre-call-prep.zip holds references/socratic-questions.md {n} times, need 1"]


# ── driver ──────────────────────────────────────────────────────────────────────────────────────────

def render():
    p = "plugins/pcp/"
    files = {
        ".claude-plugin/marketplace.json": dump(catalog()),
        ".agents/plugins/marketplace.json": dump(codex_catalog()),
        ".cursor-plugin/marketplace.json": dump(catalog()),
        ".grok-plugin/marketplace.json": dump(catalog()),
        p + ".claude-plugin/plugin.json": dump(META),
        p + ".codex-plugin/plugin.json": dump({**META, "skills": "./skills/", "interface": SRC["interface"]}),
        p + ".cursor-plugin/plugin.json": dump({**META, "displayName": SRC["interface"]["displayName"]}),
        p + ".grok-plugin/plugin.json": dump({**META, "skills": "./skills/"}),
        p + ".devin-plugin/plugin.json": dump(META),
        p + "plugin.json": dump({"$schema": "https://agent-plugins.org/schemas/1.0.0/plugin.schema.json", **META}),
        p + "gemini-extension.json": dump({k: SRC[k] for k in ("name", "version", "description")}),
    }
    for skill, names in NAMED.items():
        for rel in names:
            files[f"{p}skills/{skill}/{rel}"] = (PLUGIN / rel).read_bytes()
    files["adapters/perplexity/pre-call-prep.zip"] = perplexity_zip(files)
    files["adapters/chat/instructions.txt"] = CHAT_INSTRUCTIONS
    files["adapters/chat/pcp-knowledge.md"] = chat_knowledge()
    files["adapters/grok/instructions.txt"] = files["adapters/chat/instructions.txt"]   # the Grok app: the same chat brief (S4-10)
    files["adapters/grok/pcp-knowledge.md"] = files["adapters/chat/pcp-knowledge.md"]
    return files


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--check", action="store_true")
    a = ap.parse_args()
    files = render()
    problems = (check_chat(files["adapters/chat/pcp-knowledge.md"]) + check_zip(files["adapters/perplexity/pre-call-prep.zip"])
                + check_listing(files) + check_names(files) + check_version())
    drift = [rel for rel, data in files.items()
             if not (ROOT / rel).exists() or (ROOT / rel).read_bytes() != (data if isinstance(data, bytes) else data.encode())]
    for line in problems:
        print("FAIL", line)
    if a.check:
        for rel in drift:
            print("out of date:", rel)
        print(f"{len(files) - len(drift)}/{len(files)} generated files up to date; {len(problems)} problems")
        return 1 if drift or problems else 0
    if problems:
        return 1
    for rel in drift:
        path = ROOT / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(files[rel] if isinstance(files[rel], bytes) else files[rel].encode())
        print("wrote", rel)
    return 0


if __name__ == "__main__":
    sys.exit(main())
