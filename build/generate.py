#!/usr/bin/env python3
"""generate.py -- every host file for the pcp plug-in, from two sources.

  build/plugin.source.json                       identity: name, version, author, catalog, interface, skills
  plugins/pcp/skills/pcp/pcp.yaml      content: questions, stages, families, rubric, page budget, checks

Never edit a generated file. Edit a source, run this, run the tests.

Emits (host contracts per the vendors' docs, verified 2026-09-25):
  .claude-plugin/marketplace.json            Claude Code / Cowork catalog; also read by Codex (legacy), Grok, Devin
  .agents/plugins/marketplace.json           Codex + ChatGPT desktop catalog (canonical)
  .cursor-plugin/marketplace.json            Cursor catalog
  plugins/pcp/plugin.json                    Agent Plugins 1.0.0 manifest + extensions.com.openai (Codex, Cursor, Devin)
  plugins/pcp/.claude-plugin/plugin.json     Claude (Devin and Grok also read it)
  plugins/pcp/.cursor-plugin/plugin.json     Cursor plug-in format, so commands/ loads
  plugins/pcp/gemini-extension.json          Gemini CLI extension
  plugins/pcp/commands/pcp.toml              /pcp for Gemini CLI ({{args}}); every other host invokes the skill
  plugins/pcp/skills/pcp/SKILL.md  the skill, rendered from pcp.yaml
  plugins/pcp/skills/*/agents/openai.yaml    Codex / ChatGPT per-skill presentation
  plugins/pcp/skills/pcp/scripts|assets   renderer copied byte-for-byte from the talyx-pdf skill
  adapters/chat/{instructions.txt,pcp-knowledge.md} Gemini Gem / M365 Copilot (no scripts there)
  dist/perplexity/<skill>.zip                one upload per skill (not in --check; ignored by git)

Usage:
  python3 build/generate.py            write everything, run the skill checks, build the ZIPs
  python3 build/generate.py --check    exit 1 if any generated file differs from a fresh render
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import zipfile
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT / "build" / "plugin.source.json"
DIST = ROOT / "dist"
PLUGIN_SCHEMA = "https://agent-plugins.org/schemas/1.0.0/plugin.schema.json"
META = ("name", "version", "description", "author", "homepage", "repository", "license", "keywords")
PERPLEXITY = {"files": 100, "bytes": 10 * 1024 * 1024}     # upload UI limit (stricter than the API's 32 MiB)


def load():
    src = {k: v for k, v in json.loads(SOURCE.read_text()).items() if not k.startswith("_")}
    plugin = ROOT / "plugins" / src["name"]
    reg_path = plugin / "skills" / "pcp" / "pcp.yaml"
    raw = reg_path.read_bytes()
    return src, plugin, yaml.safe_load(raw), hashlib.sha256(raw).hexdigest()[:12]


def dump(obj):
    return json.dumps(obj, indent=2, ensure_ascii=False) + "\n"


def meta(src):
    return {k: src[k] for k in META if k in src}


# ── manifests and catalogs ───────────────────────────────────────────────────────────────────────

def agent_plugin_json(src):
    return {"$schema": PLUGIN_SCHEMA, **meta(src), "extensions": {"com.openai": {"interface": src["interface"]}}}


def catalog_entry(src):
    return {"name": src["name"], "description": src["description"], "version": src["version"],
            "author": src["author"], "homepage": src["homepage"], "license": src["license"],
            "category": src["category"], "keywords": src["keywords"], "source": f"./plugins/{src['name']}"}


def claude_style_catalog(src):
    m = src["marketplace"]
    return {"name": m["name"], "owner": m["owner"],
            "metadata": {"description": m["description"], "version": src["version"]},
            "plugins": [catalog_entry(src)]}


def codex_catalog(src):
    m = src["marketplace"]
    return {"name": m["name"], "interface": {"displayName": m["displayName"]},
            "plugins": [{"name": src["name"], "source": {"source": "local", "path": f"./plugins/{src['name']}"},
                         "policy": m["policy"], "category": src["interface"]["category"]}]}


def openai_skill_yaml(skill):
    q = json.dumps   # a JSON string literal is a valid YAML double-quoted scalar
    return ("interface:\n"
            f"  display_name: {q(skill['displayName'])}\n"
            f"  short_description: {q(skill['shortDescription'])}\n"
            f"  default_prompt: {q(skill['defaultPrompt'])}\n")


# ── the skill, rendered from pcp.yaml ────────────────────────────────────────────────────────────

def _rows(rows):
    return "\n".join(f"- **{r['id']}** {r['text']}  \n  _Fails when:_ {r['test']}" for r in rows)


def _inputs(inputs):
    lines = ["| Input | Type | Source | Required | Fallback |", "|---|---|---|---|---|"]
    lines += [f"| `{i['name']}` | {i['type']} | {i['source']} | {'yes' if i['required'] else 'no'} | {i['fallback']} |" for i in inputs]
    return "\n".join(lines)


def _context(ctx):
    return (f"**Context contract** -- read, in this order: {', '.join(ctx['order'])}. "
            f"Budget: {ctx['budget_words']} words. Not read: {', '.join(ctx['excluded'])}.")


QUESTION_TOOLS = """the host's structured-question tool, first option marked recommended:
  - Claude `AskUserQuestion` and Gemini `ask_user`: up to 4 questions per call, 2-4 options each.
  - Codex `request_user_input`: up to 3 questions per call and only 2-3 options each; it adds an "Other"
    free-text choice itself. For a 4-option question show the first 3 and name the 4th in the question
    text ("or choose Other and type: <label>"). If it answers "unavailable in Default mode", ask in chat
    instead and tell the user once that Codex shows these as a form in Plan mode, or after
    `codex features enable default_mode_request_user_input`.
  - Keep headers to 12 characters; you may shorten option labels, but apply the option `value`.
  - A free-text question (no options) always goes in plain chat.
  - No such tool: ask them all in one chat message with numbered options"""

RUNNING_PLUGIN = """## Running this skill

- **Paths.** Every `scripts/`, `assets/` and `pcp.yaml` path here is relative to this skill's folder -- the
  folder containing this SKILL.md. Resolve it to an absolute path before running anything. Never write
  into the skill folder: working files (`claims.jsonl`, `brief.md`, `script.md`) and the PDF go in the
  output folder (`--out <dir>`, default the user's current working folder).
- **Runtime.** Python 3.10+ with PyYAML. The PDF step also needs Playwright + Chromium + pypdf; if
  `scripts/talyx_pdf.py` reports them missing, ask the user before running
  `python3 scripts/talyx_pdf.py --setup` (it installs packages). Row S4-6 covers a host that cannot render.
- **Arguments.** `$ARGUMENTS` -- `"Full Name, Organisation"` or a CSV path (template:
  `assets/intake-template.csv`), plus optional `--recalibrate`, `--profile <name>`, `--out <dir>`. If that
  placeholder was not filled in (hosts other than Claude), read them from the user's message.
- **One copy.** Use only this skill's folder. Never search the disk for another pcp install: an older copy
  elsewhere is not this plug-in.
- **Say first** what was not found (coverage) before what was -- row S4-7."""

STAGE0_PLUGIN = """## Stage 0: Calibrate (once per user)

Run `python3 scripts/profile.py inspect [--profile <name>] [--recalibrate]`. It prints JSON; `questions`
holds exactly what to ask. The saved profile is per user and is reused by every later run. The rows
below (CAL-1 to CAL-7) are the rules; this is how to follow them:

- `status: complete` -- use `effective` and `profile_line` silently. Ask nothing.
- `status: missing`, `incomplete` or `recalibrate` -- ask the listed `questions` (with `recalibrate`, show
  each saved `current` answer as the default), using {tools}.
- Then, however the answers were collected, save them: write a JSON object
  `{{"Q1": "<option value or label>", ..., "Q8": "<free text>"}}` (null = skipped) to a temporary file in the
  output folder, run
  `python3 scripts/profile.py apply --answers-file <file> --base-sha256 <sha256 from inspect, or none> [--profile <name>]`,
  delete the file, and use the `effective` block it returns.
- `status: invalid` -- tell the user their saved setup cannot be read and ask whether to redo it. On yes,
  ask every question and apply with `--replace-invalid` (the old file is kept as a backup).
- `ok: false` from apply -- act on its `code`: `INVALID_ANSWER` map the answer to an option or ask again;
  `REQUIRED` ask that free-text question; `STALE` inspect again; `WRITE_DENIED` see CAL-7.
- Python unavailable -- ask the questions, use the answers for this run only, and say they were not saved.

| # | Chip | Question | Options | Sets |
|---|---|---|---|---|
{questions}

{rules}

Profile line (footer of every PDF): `{profile_line}`."""

STAGE0_CHAT = """## Stage 0: Calibrate (once per user)

This host runs no scripts. The saved setup is the **Saved setup** block at the end of this knowledge file.

- Every question has a saved answer there -- use them silently. Ask nothing.
- Otherwise ask ONLY the unanswered questions, using {tools}. A skipped question takes its first
  (Recommended) option, marked defaulted. Then output the complete updated **Saved setup** block in
  the same YAML shape -- each answer as `Q1: {{value: <option value or your text>, defaulted: false}}` under
  `profiles: default: answers:` -- and tell the user to replace the block in this knowledge file with it, so the
  next conversation does not ask again. Never claim it was saved: only the user can update the file.
- `--recalibrate` asks every question again, showing the saved answer.

| # | Chip | Question | Options | Sets |
|---|---|---|---|---|
{questions}

{rules}

Profile line (heading of every brief): `{profile_line}`."""

RENDER_PLUGIN = """## Render

```
python3 scripts/talyx_pdf.py --brief <out>/brief.md --script <out>/script.md --title "<Name> -- <Org>" \\
    --subtitle "Pre-call brief · <meeting date>" --footer "<profile line> · <status> · duf_pp <x> · coverage <a>/<b>" \\
    --max-pages {pages} --out <out>/<date>-<slug>.pdf
```

Read the JSON it prints: `ok: false` means there is no deliverable yet -- cut the named sections and render
again. Deliver the PDF path and the footer line, then delete `brief.md` and `script.md`.

## Debrief and ratchet

After the call, offer the four fields in `assets/debrief-template.yaml` and save the answers as
`debrief.yaml` beside the PDF. Never ask for more. Then `python3 scripts/eval.py improve <debrief.yaml>`
writes proposed registry changes beside the debrief as `pcp-proposals-<date>.patch`; it never edits the
skill. Proposals land only through the maintainers' ratchet (`evals/pcp_eval.py ratchet` in the source
repository)."""

RENDER_CHAT = """## Deliver

This host has no PDF renderer and cannot run the checks as code. Apply every check in the table above
yourself before answering, and say they were self-checked, not machine-run. Deliver ONE document: the
brief (B1-B9) then the meeting script (P1-P7), headed with the profile line, status and coverage. Say
plainly that it is not the Talyx PDF; the plug-in version renders that.

## Debrief

After the call, ask for the four debrief fields -- facts used (claim ids), questions that landed, band
accuracy per dimension (hit or miss), outcome -- and nothing else."""


def render_skill(src, R, sha, mode="plugin"):
    cal = R["calibration"]
    q_lines = []
    for q in cal["questions"]:
        opts = " / ".join(o["label"] for o in q["options"]) if q["options"] else "free text"
        q_lines.append(f"| {q['id']} | {q['header']} | {q['question']} | {opts} | {', '.join(q['sets'])} |")
    stage0 = (STAGE0_PLUGIN if mode == "plugin" else STAGE0_CHAT).format(
        tools=QUESTION_TOOLS, questions="\n".join(q_lines), rules=_rows(cal["rules"]),
        profile_line=" · ".join(cal["profile_line"]))
    fam_lines = [f"| {f['id']} | {f['name']} | {'/'.join(f['depth'])} | {'yes' if f['socmint'] else 'no'} | `{f['query']}` | {f['extract']} |"
                 for f in R["families"]]
    dims = "\n".join(f"| {d['id']} | {'; '.join(d['signals'])} | {d['meaning']['low']} | {d['meaning']['mid']} | {d['meaning']['high']} |"
                     for d in R["rubric"]["dimensions"])
    tiers = R["rubric"]["tiers"]
    brief = "\n".join(f"| {s['id']} | {s['title']} | {s['words']} | {s['content']} |" for s in R["brief"]["sections"])
    script = "\n".join(f"| {b['id']} | {b['title']} | {b['words']} | {b['content']} |" for b in R["script"]["blocks"])
    beats = "\n".join(f"- **{k}**: {' -> '.join(v)}" for k, v in R["script"]["beats_by_format"].items())
    checks = "\n".join(f"| {c['id']} | {c['name']} | `{c['cmd']}` | {c['passes_when']} |" for c in R["checks"] if "cmd" in c)
    excl, pb = R["exclusions"], R["page_budget"]
    stages = []
    for s in R["stages"]:
        block = [f"## Stage {s['id'][1]}: {s['name']}", "", "**Input contract** (declared before behaviour):", "",
                 _inputs(s["inputs"]), "", _context(s["context"]), ""]
        if s.get("outputs"):
            block += ["**Outputs:** " + "; ".join(f"`{o['name']}` ({', '.join(o.get('fields', [])) or o.get('note', '')})" for o in s["outputs"]), ""]
        block += ["**Rows:**", "", _rows(s["rows"]), ""]
        stages.append("\n".join(block))
    # frontmatter must be the first bytes of the file or hosts ignore it -- the marker goes after it
    head = (f"---\nname: {R['skill']['name']}\ndescription: {json.dumps(R['skill']['description'])}\n"
            f"argument-hint: {json.dumps(R['skill']['argument_hint'])}\n---\n{R['render_header'].format(sha=sha)}\n\n"
            if mode == "plugin" else f"{R['render_header'].format(sha=sha)}\n\n")
    running = RUNNING_PLUGIN + "\n\n" if mode == "plugin" else ""
    tail = RENDER_PLUGIN.format(pages=pb["total_pages"]) if mode == "plugin" else RENDER_CHAT
    return f"""{head}# Pre-call prep (v{src['version']})

Five stages, dependency-ordered: **calibrate once -> intake -> collect -> read -> brief + script -> debrief.**
Every stage declares its inputs before its behaviour, reads only its listed context, and follows rows
that each carry a falsification test. Every fact traces to a public source. Nothing is invented.
The deliverable is one 3-page PDF. Nothing else is emitted.

{running}{stage0}

{chr(10).join(stages)}
## Source families

Enabled per profile: `depth` filters the column, `target.kind` filters `kinds`, `socmint.scope` filters F6
to `{', '.join(R['research']['socmint_networks']['professional'])}` (professional) or the wider list (social) or none.
FULL status needs >= 1 C1/C2 claim in {R['research']['full_threshold']} families (by depth).

| Id | Family | Depth | SOCMINT | Query template | Extract |
|---|---|---|---|---|---|
{chr(10).join(fam_lines)}

Registers by domain: {'; '.join(f"{k}: " + ', '.join(r['name'] for r in v) for k, v in R['registers'].items() if v) or 'none'}.

**Exclusions (dropped before the writer, counted in coverage):** {', '.join(excl['base'])}.
By jurisdiction: {'; '.join(f"{k}: {', '.join(v)}" for k, v in excl['by_jurisdiction'].items() if v)}.

## Behavioral read (six dimensions)

Tiers: high = {tiers['high']['min_observations']} observations, {tiers['high']['corroborated_across_sources']} sources, a direct quote or action;
medium = {tiers['medium']['min_observations']} observations, {tiers['medium']['corroborated_across_sources']} source; low = role-inferred only (renders as "no read").

| Dimension | Signals | Low means | Mid means | High means |
|---|---|---|---|---|
{dims}

ACH mini (depth deep only): <= {R['rubric']['ach']['max_hypotheses']} hypotheses about what they want from this meeting, each with the claim that would disconfirm it.

## The PDF: pages 1-2 brief

Word budgets are the page budget; the engine renders on a {len(pb['ladder'])}-rung density ladder and fails, never spills, past {pb['total_pages']} pages.

| Id | Section | Words | Content |
|---|---|---|---|
{brief}

Domain vocabulary: {'; '.join(f"{k}: {', '.join(v)}" for k, v in R['brief']['vocab_by_domain'].items() if v)}.

## The PDF: page 3 meeting script

Beats by meeting format:
{beats}

| Id | Block | Words | Content |
|---|---|---|---|
{script}

Never say: {'; '.join(f'"{p}"' for p in R['guardrails']['never_say'])}.

## Checks (all pass before render)

| Id | Check | Command | Passes when |
|---|---|---|---|
{checks}

{tail}

## About

Made by Talyx AI, https://talyx.ai. Free to use under the licence in the plug-in's `LICENSE` file.
"""


def render_command_toml(R, sha):
    """Gemini CLI only: a /pcp slash command that activates the skill. Every other host invokes the skill itself."""
    body = (f"Input from the user: {{{{args}}}}\n\n"
            f"Activate the `{R['skill']['name']}` skill from THIS extension and follow it exactly, in stage order, "
            f"with that input as its arguments. Use only this extension's copy of the skill.\n")
    assert '"""' not in body and "\\" not in body
    return (f"# {R['render_header'].format(sha=sha)}\n"
            f"description = {json.dumps(R['skill']['command_description'])}\n"
            f'prompt = """\n{body}"""\n')


# ── chat adapters (hosts that take instructions + a knowledge file, and run no scripts) ────────────


CHAT_INSTRUCTIONS = """You are Talyx Pre-call Prep. Before a meeting you research the named person, company or deal from public sources only and write one cited brief plus a one-page meeting script.

Follow {knowledge} exactly, in stage order: calibrate, intake, collect, read, brief and script, debrief. It holds the questions, source families, exclusions, rubric, page budgets and checks. Where it and this text differ, it wins.

Calibration is asked once. The Saved setup block at the end of {knowledge} holds the saved answers. Ask only the questions it has no answer for, then give the user the updated block to paste into their copy of {knowledge}. Never say it was saved: only the user can update that file.

Never start research without a full name and an organisation. If two people match, stop and ask. Public sources only: nothing behind a login, no scraping. Every fact carries a numbered citation to a source you actually opened. Say what you could not find before what you found. Never invent a fact, a quote or a source.

This host has no PDF renderer and runs no code. Apply the checks yourself and say they were self-checked. Deliver one document and say it is not the Talyx PDF.
"""


def render_chat_knowledge(src, R, sha):
    body = render_skill(src, R, sha, mode="chat")
    blank = {"pcp_profile_format": 1, "profiles": {"default": {"answers": {}}}}
    return (body + "\n## Saved setup\n\nReplace this block with the one the assistant gives you after calibration.\n\n"
            "```yaml\n" + yaml.safe_dump(blank, sort_keys=False) + "```\n")


# ── checks ───────────────────────────────────────────────────────────────────────────────────────

def check_skills(plugin, files):
    """Portability checks on every SKILL.md as it will be written (the Agent Skills spec + host rules)."""
    fails = []
    for skill_dir in sorted((plugin / "skills").iterdir()):
        path = skill_dir / "SKILL.md"
        text = files.get(path) or path.read_text()
        fm = re.match(r"---\n(.*?)\n---\n", text, re.S)
        where = path.relative_to(ROOT)
        if not fm:
            fails.append(f"{where}: frontmatter must start the file (hosts ignore it otherwise)"); continue
        try:
            meta_ = yaml.safe_load(fm.group(1))
        except yaml.YAMLError as exc:
            fails.append(f"{where}: frontmatter is not valid YAML ({str(exc).splitlines()[0]})"); continue
        name, desc = str(meta_.get("name", "")), str(meta_.get("description", ""))
        if name != skill_dir.name or not re.fullmatch(r"[a-z0-9]+(-[a-z0-9]+)*", name):
            fails.append(f"{where}: name must equal the folder name and be lowercase-with-hyphens")
        if not desc or len(desc.encode()) > 1024 or not re.search(r"\bUse (when|for|to)\b", desc):
            fails.append(f"{where}: description missing, over 1024 bytes, or without a 'Use when' trigger")
        body = text[fm.end():]
        for pattern, why in ((r"\.\./", "reads above its own folder"), (r"\$\{?CLAUDE_", "uses a Claude-only variable"),
                             (r"(?<![\w/])~/\.\w", "names a machine-local dot-path"), (r"/Users/\w", "names a machine path")):
            if re.search(pattern, body):
                fails.append(f"{where}: {why} -- not portable across hosts")
        for ref in sorted(set(re.findall(r"`(?:python3 )?((?:scripts|assets)/[\w.-]+)", body))):
            if not (skill_dir / ref).exists() and not any(p == skill_dir / ref for p in files):
                fails.append(f"{where}: references {ref}, which is not in the skill folder")
    return fails


def check_registry(R):
    """An unquoted comma inside a YAML flow mapping silently splits a label into stray null keys
    (seen in pcp.yaml v2.0.0: seven calibration options and four row bases were truncated)."""
    fails = []

    def walk(x, path):
        if isinstance(x, dict):
            for k, v in x.items():
                if v is None:
                    fails.append(f"pcp.yaml {'/'.join(map(str, path))}: stray key {k!r} -- quote the value containing a comma")
                walk(v, path + [k])
        elif isinstance(x, list):
            for i, v in enumerate(x):
                walk(v, path + [i])
    walk(R, [])
    for q in R["calibration"]["questions"]:
        for o in q["options"]:
            if set(o) != {"label", "value", "description"}:
                fails.append(f"pcp.yaml calibration {q['id']}: option keys {sorted(o)} != label/value/description")
    return fails


def check_ladder(R):
    """pcp.yaml's page ladder and the renderer's LADDER are one parameter in two files -- values must match."""
    text = (ROOT / "plugins" / "pcp" / "skills" / "talyx-pdf" / "scripts" / "talyx_pdf.py").read_text()
    code = [dict(name=m[0], body_pt=float(m[1]), line_height=float(m[2]), para_gap_pt=int(m[3]), sec_gap_pt=int(m[4]))
            for m in re.findall(r'dict\(name="(\w+)",\s*body_pt=([\d.]+),\s*lh=([\d.]+),\s*para=(\d+),\s*sec=(\d+)\)', text)]
    reg = [dict(r, body_pt=float(r["body_pt"]), line_height=float(r["line_height"])) for r in R["page_budget"]["ladder"]]
    return [] if code == reg else [f"page ladder differs: pcp.yaml {reg} vs talyx_pdf.py {code}"]


# ── driver ───────────────────────────────────────────────────────────────────────────────────────

def render(src, plugin, R, sha):
    files: dict[Path, str | bytes] = {
        ROOT / ".claude-plugin" / "marketplace.json": dump(claude_style_catalog(src)),
        ROOT / ".cursor-plugin" / "marketplace.json": dump(claude_style_catalog(src)),
        ROOT / ".agents" / "plugins" / "marketplace.json": dump(codex_catalog(src)),
        plugin / "plugin.json": dump(agent_plugin_json(src)),
        plugin / ".claude-plugin" / "plugin.json": dump(meta(src)),
        plugin / ".cursor-plugin" / "plugin.json": dump(meta(src)),
        plugin / "gemini-extension.json": dump({k: src[k] for k in ("name", "version", "description")}),
        plugin / "commands" / "pcp.toml": render_command_toml(R, sha),
        plugin / "skills" / "pcp" / "SKILL.md": render_skill(src, R, sha),
    }
    for skill in src["skills"]:
        files[plugin / "skills" / skill["name"] / "agents" / "openai.yaml"] = openai_skill_yaml(skill)
    for owner, skills in src["shared"].items():
        base = plugin / "skills" / owner
        for f in sorted(p for d in ("scripts", "assets") for p in (base / d).rglob("*")
                        if p.is_file() and p.name != ".DS_Store" and "__pycache__" not in p.parts):
            for skill in skills:
                files[plugin / "skills" / skill / f.relative_to(base)] = f.read_bytes()
    files[ROOT / "adapters" / "chat" / "instructions.txt"] = CHAT_INSTRUCTIONS.format(knowledge="pcp-knowledge.md")
    files[ROOT / "adapters" / "chat" / "pcp-knowledge.md"] = render_chat_knowledge(src, R, sha)
    return files


def build_zips(plugin, src):
    out = DIST / "perplexity"
    out.mkdir(parents=True, exist_ok=True)
    made = []
    for skill in src["skills"]:
        folder = plugin / "skills" / skill["name"]
        members = sorted(p for p in folder.rglob("*") if p.is_file() and p.name != ".DS_Store" and "__pycache__" not in p.parts)
        if len(members) > PERPLEXITY["files"]:
            sys.exit(f"{skill['name']}: {len(members)} files exceeds Perplexity's {PERPLEXITY['files']}")
        tmp = out / f".{skill['name']}.zip.tmp"
        with zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as zf:
            for p in members:
                info = zipfile.ZipInfo(str(p.relative_to(folder)), date_time=(2026, 1, 1, 0, 0, 0))
                info.external_attr = (0o755 if p.suffix == ".py" else 0o644) << 16
                zf.writestr(info, p.read_bytes(), zipfile.ZIP_DEFLATED)
        if tmp.stat().st_size > PERPLEXITY["bytes"]:
            tmp.unlink(); sys.exit(f"{skill['name']}: ZIP exceeds Perplexity's {PERPLEXITY['bytes']} bytes")
        tmp.replace(out / f"{skill['name']}.zip")
        made.append((skill["name"], len(members), (out / f"{skill['name']}.zip").stat().st_size))
    return made


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--check", action="store_true", help="report drift instead of writing")
    a = ap.parse_args()
    src, plugin, R, sha = load()
    files = render(src, plugin, R, sha)

    def current(p):
        if not p.exists():
            return None
        return p.read_bytes() if isinstance(files[p], bytes) else p.read_text()

    drift = sorted(str(p.relative_to(ROOT)) for p in files if current(p) != files[p])
    problems = check_skills(plugin, files) + check_registry(R) + check_ladder(R)
    if a.check:
        for line in drift:
            print("out of date:", line)
        for line in problems:
            print("FAIL", line)
        print(f"{len(files) - len(drift)}/{len(files)} generated files up to date; {len(problems)} skill problems")
        return 1 if drift or problems else 0
    if problems:
        for line in problems:
            print("FAIL", line)
        print("Build failed -- nothing written, no ZIPs created or replaced.")
        return 1
    for rel in drift:
        p = ROOT / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        (p.write_bytes if isinstance(files[p], bytes) else p.write_text)(files[p])
    print(f"{src['name']} v{src['version']} (pcp.yaml sha256:{sha}): wrote {len(drift)} of {len(files)} generated files")
    for rel in drift:
        print("  ", rel)
    for name, count, size in build_zips(plugin, src):
        print(f"   dist/perplexity/{name}.zip  {count} files, {size} bytes")
    return 0


if __name__ == "__main__":
    sys.exit(main())
