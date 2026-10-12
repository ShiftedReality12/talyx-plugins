#!/usr/bin/env python3
"""talyx_pdf.py -- portable Talyx house-style (masthead-alt) Markdown -> PDF, with a hard page gate.

Self-contained: this file + assets/archivo-variable.woff2 + assets/talyx-logo-navy-base64.txt.
Needs a Chromium: Playwright's if installed, else the Chrome, Edge or Chromium already on the computer.
`python3 talyx_pdf.py --setup` installs Playwright's (and pypdf, for bookmark names). Nothing else.

Markdown it understands (minimal, generic):
  `# Title`            document title (overridden by --title); a later part's `# ` line is that part's masthead
  `## Heading`         numbered, bookmarked section
  paragraphs, `- ` bullets (indent 2+ spaces for a sub-bullet), `1.` numbered lists, `- [ ]` checklist items,
  `| a | b |` pipe tables (a table whose first header cell is `#` is a compact one-line-per-row sources table),
  `**Label:** text` label lines (hanging indent, no bullet), `> text` a pull quote, **bold**, *italic*, [label](url) links,
  [n] citations, " -- " em dash

Usage:
  talyx_pdf.py --input doc.md --out doc.pdf [--title ..] [--subtitle ..] [--footer ..] [--max-pages N]
  talyx_pdf.py --brief brief.md --script script.md [--gaps gaps.md] --out x.pdf --max-pages 3
      # each later part starts on its own page under its own masthead
  talyx_pdf.py --style brief --brief brief.md --script script.md --columns "B3|B4,P1+P2|P5+P6" \
      --classification "INTERNAL | ..." --out x.pdf --max-pages 3
      # the Intelligence Brief look: the brief's lines under `# Name` are its identity and meta lines; section
      # B1 is the Take box; --columns sets blocks side by side (| between columns, + within a column)

--max-pages N: renders on a density ladder (loose -> compact). If the tightest rung still overflows, exits 2
naming the longest sections. It never truncates and never spills silently. Exit 0 prints: pages, rung, path.
"""
import argparse
import base64
import html
import json
import os
import pathlib
import re
import shutil
import subprocess
import sys
import tempfile

HERE = pathlib.Path(__file__).resolve().parent
ASSETS = HERE / "assets"
ACCENT, INK, HAIR, MIDNIGHT = "#1C3A66", "#000000", "#E8EAED", "#0F2744"

LADDER = [
    dict(name="loose",   body_pt=11.0, lh=1.42, para=6, sec=12, mh=(0.15, 0.22), cell=3, page=(0.55, 0.6)),
    dict(name="normal",  body_pt=10.5, lh=1.36, para=5, sec=10, mh=(0.15, 0.22), cell=3, page=(0.55, 0.6)),
    dict(name="tight",   body_pt=10.0, lh=1.30, para=4, sec=8,  mh=(0.15, 0.22), cell=3, page=(0.55, 0.6)),
    dict(name="compact", body_pt=10.0, lh=1.24, para=3, sec=6,  mh=(0.05, 0.14), cell=1.5, page=(0.45, 0.55)),
]
# --style brief: Ben's format (the approved Oct 8 schema), about 9 pt
BRIEF_LADDER = [
    dict(name="normal",  body_pt=9.0, lh=1.33, para=3, sec=11, cell=2.6),
    dict(name="tight",   body_pt=8.7, lh=1.29, para=2, sec=9,  cell=2.0),
    dict(name="compact", body_pt=8.4, lh=1.25, para=2, sec=7,  cell=1.5),
]
GREY, BRIEF_ACCENT = "#8B95A1", "#1C3A66"


# ---------------------------------------------------------------- markdown -> html --------------------------
def typo(t):
    t = re.sub(r'(^|[\s(\[*])"', "\\1\u201c", t); t = t.replace('"', "\u201d")
    t = re.sub(r"(^|[\s(\[*])'", "\\1\u2018", t); t = t.replace("'", "\u2019")
    t = t.replace(" -- ", " \u2014 ")
    return t.replace(" - ", " \u2013 ").replace("->", "\u2192")


LINK = re.compile(r"\[([^\]]+)\]\((https?://[^)\s]+)\)")
LABEL = re.compile(r"^\*\*[^*]+:\*\*")                      # a line led by `**Label:**`
ITEM = re.compile(r"^(\s*)([-*]|\d+\.)\s+(\[[ xX]\]\s+)?")   # bullet, numbered item, checklist item


def inl(t):
    links = []

    def stash(m):
        links.append(m.groups()); return f"\x00{len(links) - 1}\x00"
    t = re.sub(r"[ \t]+(?=\[\d+\])", "\u00a0", t)          # a citation never starts a line
    t = html.escape(typo(LINK.sub(stash, t)), quote=False)
    t = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", t)
    t = re.sub(r"(?<!\*)\*([^*]+?)\*(?!\*)", r"<em>\1</em>", t)
    t = re.sub(r"\[(\d+)\]", r'<span class="cite">[\1]</span>', t)
    t = t.replace("&amp;", '<span class="amp">&amp;</span>')
    return re.sub("\x00(\\d+)\x00", lambda m: '<a href="{}">{}</a>'.format(
        html.escape(links[int(m.group(1))][1]), html.escape(typo(links[int(m.group(1))][0]), quote=False)), t)


def _table(lines):
    rows = [[c.strip() for c in ln.strip().strip("|").split("|")] for ln in lines if not re.match(r"^\s*\|?\s*:?-+", ln)]
    if not rows:
        return ""
    def cell(c):
        h = inl(keep(c))
        m = re.match(r"(\d+)\.\s", h)
        return f'<span class="hang"><span class="num">{m.group(1)}.</span>{h[m.end():]}</span>' if m else h
    body = "".join("<tr>" + "".join(f"<td>{cell(c)}</td>" for c in r) + "</tr>" for r in rows[1:])
    if not any(rows[0]):   # an empty header row: a label grid (bold label column, no column heads)
        return f'<table class="grid"><tbody>{body}</tbody></table>'
    short_keys = len(rows[0]) == 2 and max(len(r[0]) for r in rows) <= 40
    cls = ' class="src"' if rows[0][0] == "#" else (' class="kv"' if short_keys else "")
    head = "".join(f"<th>{inl(c)}</th>" for c in rows[0])
    return f"<table{cls}><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table>"


def keep(t):
    """Glue the last word (and any citation after it) to the word before, so no line ends a block with one word."""
    t = re.sub(r"[ \t]+(?=\[\d+\])", "\u00a0", t)
    return "\u00a0".join(t.rsplit(" ", 1)) if t.count(" ") >= 3 else t


def _list(items):
    """items: [(level 0|1, 'ul'|'ol', text, checked-or-None)] -> nested lists, at most two levels."""
    out, stack = [], []                       # stack: open list tags, each with an open <li>
    for lvl, tag, txt, check in items:
        lvl = min(lvl, len(stack))            # never more than one level deeper than the item before
        while len(stack) > lvl + 1 or (len(stack) == lvl + 1 and stack[-1] != tag):
            out.append(f"</li></{stack.pop()}>")
        if len(stack) == lvl + 1:
            out.append("</li>")
        else:
            out.append(f"<{tag}>"); stack.append(tag)
        out.append({None: "<li>", False: '<li class="check">', True: '<li class="check done">'}[check] + inl(keep(txt)))
    while stack:
        out.append(f"</li></{stack.pop()}>")
    return "".join(out)


def body_html(txt):
    out, para, items, table = [], [], [], []
    label = False

    def flush():
        nonlocal para, items, table, label
        if para: out.append(("<p class=\"lbl\">" if label else "<p>") + inl(keep(" ".join(para))) + "</p>"); para = []
        if items: out.append(_list(items)); items = []
        if table: out.append(_table(table)); table = []
        label = False

    for ln in txt.splitlines():
        s = ln.rstrip().expandtabs(4)
        if not s.strip():
            flush(); continue
        if s.lstrip().startswith("|"):
            if para or items: flush()
            table.append(s); continue
        m = ITEM.match(s)
        if m:
            if para or table: flush()
            check = None if m.group(3) is None else m.group(3).strip().lower() == "[x]"
            items.append((0 if len(m.group(1)) < 2 else 1, "ol" if m.group(2)[0].isdigit() else "ul", s[m.end():], check))
            continue
        if s.startswith("> "):
            flush(); out.append(f"<blockquote>{inl(keep(s[2:].strip()))}</blockquote>"); continue
        if re.match(r"^###\s+", s):
            flush(); out.append('<div class="sub">' + inl(re.sub(r"^###\s+", "", s)) + '</div>'); continue
        if items or table or LABEL.match(s.strip()):
            flush()
        label = label or (not para and bool(LABEL.match(s.strip())))
        para.append(s.strip())
    flush()
    return "\n".join(out)


def sections(md, start_num=1, line_per_para=False):
    """[(num, title, html)] from ## headings; a leading # line is returned as the title.
    line_per_para: each line before the first ## is its own paragraph (the brief's identity and meta lines)."""
    title = None
    m = re.match(r"^\s*#\s+(.+?)\s*$", md.split("\n", 1)[0])
    if m:
        title = m.group(1); md = md.split("\n", 1)[1] if "\n" in md else ""
    parts = re.split(r"^##\s+(.+)$", md, flags=re.M)
    secs = []
    if parts[0].strip():
        pre = "\n\n".join(ln for ln in parts[0].splitlines() if ln.strip()) if line_per_para else parts[0]
        secs.append((None, None, body_html(pre)))
    for i in range(1, len(parts), 2):
        m = re.match(r"^[BP](\d+)\s", parts[i].strip())   # a Bn/Pn id sets the printed number
        num = int(m.group(1)) if m else start_num + len([s for s in secs if s[0]])
        secs.append((num, parts[i].strip(), body_html(parts[i + 1])))
    return title, secs


def sec_html(num, title, body, style="house"):
    if title is None:
        return f'<div class="sec pre"><div class="sec-body">{body}</div></div>'
    t = inl(re.sub(r"^[BP]\d+\s+", "", title))  # strip Bn/Pn ids from the printed title
    ref = " ref" if re.search(r"\bsources\b", title, re.I) else ""
    if style == "brief":   # brief blocks print no number; script sections print "1."
        sid = re.match(r"([BP])(\d+)\s", title)
        num_html = f'<span class="sec-num">{num}.</span> ' if sid and sid.group(1) == "P" else ""
        return (f'<div class="sec{" sec-" + sid.group(0).strip().lower() if sid else ""}"><h2 class="sec-head">'
                f'{num_html}<span class="sec-title">{t}</span></h2><div class="sec-body">{body}</div></div>')
    return (f'<div class="sec{ref}"><h2 class="sec-head">'
            f'<span class="sec-num">{num:02d}</span> <span class="sec-title">{t}</span></h2>'
            f'<div class="sec-body">{body}</div></div>')


def columns(secs, htmls, spec):
    """--columns "B3|B4,P1+P2|P5": wrap the named sections side by side, where the first of them stands."""
    ids = [(re.match(r"([BP]\d+)\s", t or "") or [None, None])[1] for _, t, _ in secs]
    groups = [[c.split("+") for c in g.split("|")] for g in (spec or "").split(",") if g]
    out, used = [], set()
    for i, sid in enumerate(ids):
        if i in used:
            continue
        g = next((g for g in groups if sid in sum(g, [])), None)
        if g is None:
            out.append(htmls[i]); continue
        cols = [[j for j, x in enumerate(ids) if x in col] for col in g]
        used |= {j for c in cols for j in c}
        out.append('<div class="two">' + "".join("<div>" + "".join(htmls[j] for j in c) + "</div>" for c in cols) + "</div>")
    return out


# ---------------------------------------------------------------- document --------------------------------
def css(rung, footer):
    archivo = base64.b64encode((ASSETS / "archivo-variable.woff2").read_bytes()).decode()
    b, lh, pg, sg = rung["body_pt"], rung["lh"], rung["para"], rung["sec"]
    (mt, mb), cp, (top, bottom) = rung["mh"], rung["cell"], rung["page"]
    return f"""
@font-face {{ font-family:'Archivo'; font-weight:100 900; src:url(data:font/woff2;base64,{archivo}) format('woff2'); }}
@page {{ size: Letter; margin: {top}in 0 {bottom}in 0;
  @bottom-left {{ content: "{html.escape(footer)}"; font-family:'Archivo'; font-size:7.5pt; color:{ACCENT}; padding-left:0.5in; }}
  @bottom-right {{ content: "Page " counter(page) " of " counter(pages); font-family:'Archivo'; font-size:7.5pt; color:{ACCENT}; padding-right:0.5in; }} }}
html {{ -webkit-print-color-adjust:exact; }}
body {{ font-family:'Archivo', -apple-system, sans-serif; color:{INK}; margin:0; hyphens:manual; -webkit-hyphens:manual; font-variant-ligatures:common-ligatures; }}
.page-content {{ padding:0 0.5in; position:relative; }}
.masthead-alt {{ position:relative; padding-top:{mt}in; margin:0 0 {mb}in 0; font-family:'Archivo'; hyphens:none; }}
.mh-alt-logo {{ position:absolute; top:0.05in; right:-0.35in; width:88px; height:auto; }}
.mh-alt-titles {{ padding-right:1.2in; }}
.mh-alt-title {{ margin:0; font-size:22pt; font-weight:800; letter-spacing:-0.02em; line-height:1.02; color:{MIDNIGHT}; }}
.mh-alt-role {{ font-size:10.5pt; font-weight:500; color:{ACCENT}; margin-top:5px; }}
.sec {{ margin:0; }}
.sec-head {{ display:block; font-size:inherit; font-weight:inherit; line-height:1.0; padding-bottom:3px; margin:{sg}pt 0 {max(sg-6,3)}pt; break-after:avoid; }}
.sec:first-child .sec-head {{ margin-top:0; }}
.sec-num {{ font-size:9.5pt; font-weight:700; color:{ACCENT}; font-variant-numeric:lining-nums tabular-nums; }}
.sec-title {{ font-size:12.5pt; font-weight:700; letter-spacing:-0.01em; color:{MIDNIGHT}; }}
.sub {{ font-size:{b}pt; font-weight:700; color:{ACCENT}; margin:{pg}pt 0 2pt; }}
p {{ font-size:{b}pt; line-height:{lh}; margin:0 0 {pg}pt; max-width:6.6in; }}
blockquote {{ font-size:{b + 0.5}pt; line-height:{lh}; margin:0 0 {pg}pt; padding:1pt 0 1pt calc(16px - 2.5px); border-left:2.5px solid {ACCENT}; max-width:6.6in; }}
ul, ol {{ margin:0 0 {pg}pt; padding-left:16px; max-width:6.6in; }}
ol > li::marker {{ color:{ACCENT}; font-weight:700; font-variant-numeric:tabular-nums; }}
li {{ font-size:{b}pt; line-height:{lh}; margin:{max(pg-3,1)}pt 0; }}
li > ul, li > ol {{ margin:{max(pg-4,1)}pt 0 {max(pg-2,2)}pt; padding-left:16px; }}
li li {{ margin:{max(pg-4,1)}pt 0; }}
li.check {{ list-style-type:"\\2610\\00a0\\00a0"; }} li.check.done {{ list-style-type:"\\2611\\00a0\\00a0"; }}
p.lbl {{ padding-left:16px; text-indent:-16px; margin-bottom:{max(pg-2,2)}pt; max-width:none; }}
ul, ul ul {{ list-style-type:disc; }}
.hang {{ display:block; padding-left:16px; text-indent:-16px; }} .hang > .num {{ display:inline-block; width:16px; text-indent:0; }}
.amp {{ font-family:'Helvetica Neue', Helvetica, Arial, sans-serif; }}
p.lbl > strong:first-child + em {{ margin-left:-0.12em; }}
.num {{ color:{ACCENT}; font-weight:700; font-variant-numeric:tabular-nums; }}
table.kv td:first-child, table.kv th:first-child {{ white-space:nowrap; }}
p.lbl > strong:first-child, li > strong:first-child, blockquote > strong:first-child {{ color:{MIDNIGHT}; font-weight:600; }}
strong {{ font-weight:600; }} em {{ font-style:italic; font-weight:400; }}
a {{ color:{ACCENT}; text-decoration:underline; text-decoration-thickness:0.5px; text-underline-offset:1.5px; }}
.cite {{ color:{ACCENT}; font-size:0.8em; font-weight:500; font-variant-numeric:tabular-nums; }}
table {{ border-collapse:collapse; width:100%; margin:0 0 {pg}pt; table-layout:auto; break-inside:avoid; }}
table.src {{ break-inside:auto; }}
td:last-child, th:last-child {{ padding-right:0; }}
tr {{ break-inside:avoid; }} thead {{ display:table-header-group; }}
th {{ font-size:{b-1.5}pt; font-weight:500; text-transform:uppercase; letter-spacing:0.04em; color:{ACCENT}; text-align:left; padding:{cp}px 14px {cp}px 0; border-bottom:1.25px solid {ACCENT}; }}
td {{ font-size:{b-0.5}pt; line-height:{lh}; padding:{cp}px 14px {cp}px 0; border-bottom:0.5px solid {HAIR}; vertical-align:top; overflow-wrap:anywhere; }}
tbody tr:last-child td {{ border-bottom:1.25px solid {INK}; }}
table.src td {{ white-space:nowrap; overflow-wrap:normal; }}
/* everything in a Sources section is reference material: one small size and fixed compact rows at every density */
.sec.ref td {{ font-size:8pt; line-height:1.15; padding:1.5px 9px 1.5px 0; }} .sec.ref th {{ font-size:7pt; padding:1px 9px 2px 0; }}
.sec.ref table {{ margin-bottom:6pt; }}
table.src td:nth-child(2) {{ white-space:normal; width:100%; }}
table.grid td {{ font-size:{b}pt; padding:{max(cp - 1, 1)}px 10px {max(cp - 1, 1)}px 0; }}
table.grid td:first-child {{ width:1.2in; font-weight:700; color:{MIDNIGHT}; }}
table.grid tbody tr:last-child td {{ border-bottom:0.5px solid {HAIR}; }}
.pagebreak {{ break-before:page; }}
.pagebreak .masthead-alt {{ padding-top:0; }}
"""


def brief_css(rung, footer):
    """--style brief: the approved schema's look (Oct 8) -- classification band, Take box, small-caps heads, two columns."""
    archivo = base64.b64encode((ASSETS / "archivo-variable.woff2").read_bytes()).decode()
    b, lh, pg, sg, cp = rung["body_pt"], rung["lh"], rung["para"], rung["sec"], rung["cell"]
    A = BRIEF_ACCENT
    return f"""
@font-face {{ font-family:'Archivo'; font-weight:100 900; src:url(data:font/woff2;base64,{archivo}) format('woff2'); }}
@page {{ size: Letter; margin: 0.42in 0 0.62in 0;
  @bottom-left {{ content: "{html.escape(footer)}"; font-family:'Archivo'; font-size:7.2pt; color:{GREY}; padding-left:0.55in; }}
  @bottom-right {{ content: "page " counter(page) " of " counter(pages); font-family:'Archivo'; font-size:7.2pt; color:{GREY}; padding-right:0.55in; }} }}
html {{ -webkit-print-color-adjust:exact; }}
body {{ font-family:'Archivo', sans-serif; color:{MIDNIGHT}; margin:0; font-size:{b}pt; line-height:{lh}; }}
.page-content {{ padding:0 0.55in; }}
.stamp {{ display:flex; justify-content:flex-end; margin:-0.12in -0.05in 3pt 0; }} .stamp img {{ width:90px; height:auto; }}
.band {{ display:flex; align-items:center; height:18pt; border-bottom:1pt solid {HAIR}; margin-bottom:9pt; }}
.cls {{ font-size:7.8pt; font-weight:600; letter-spacing:0.16em; color:{A}; }}
h1.name {{ font-size:14.2pt; font-weight:700; margin:0 0 2pt; }}
.part-0 > .sec.pre p:first-child {{ font-size:9pt; font-weight:700; color:{A}; margin:0 0 4pt; }}
.part-0 > .sec.pre p + p {{ font-size:7.5pt; color:{GREY}; line-height:1.4; margin:0 0 7pt; }}
.sec.pre p strong {{ font-weight:700; }}
h1.h, .sec-head {{ display:block; font-size:7.8pt; font-weight:700; letter-spacing:0.18em; text-transform:uppercase; color:{A};
  border-bottom:1pt solid {HAIR}; padding-bottom:3pt; margin:{sg}pt 0 5pt; break-after:avoid; }}
h1.h {{ margin-top:0; }} .part-1 > .sec.pre p {{ font-size:7.5pt; color:{GREY}; margin:-2pt 0 5pt; }}
p {{ margin:0 0 {pg}pt; }} p.lbl {{ margin:0 0 {pg}pt; }}
ul, ol {{ margin:0 0 {pg}pt; padding-left:11pt; }} li {{ margin:0 0 3pt; }} li > ul, li > ol {{ margin:1pt 0 0; }}
strong {{ font-weight:700; }} em {{ font-style:italic; }}
a {{ color:{A}; text-decoration:underline; text-decoration-thickness:0.5px; text-underline-offset:1.5px; }}
.cite {{ color:{A}; font-size:0.8em; font-weight:500; }}
.sub {{ font-size:8.8pt; font-weight:700; margin:2pt 0 3pt; }}
.two {{ display:grid; grid-template-columns:1fr 1fr; column-gap:0.28in; }}
.sec-b1 .sec-head {{ display:none; }}
.sec-b1 .sec-body {{ background:{A}; color:#F8F6F3; font-size:9.3pt; line-height:1.45; padding:8pt 11pt; border-radius:6pt; margin-top:2pt; }}
.sec-b1 p {{ margin:0; }} .sec-b1 strong, .sec-b1 a {{ color:#fff; }} .sec-b1 .cite {{ color:#DDE5F0; }}
.sec-b2 ol {{ padding-left:15pt; }} .sec-b2 ol > li {{ font-size:{b + 0.9}pt; font-weight:600; }}
.sec-b2 li > ul {{ list-style:none; padding-left:0; }} .sec-b2 li li {{ font-size:7.8pt; font-weight:400; color:{GREY}; margin:0; }}
.sec-b2 li li strong {{ color:{GREY}; }}
table {{ border-collapse:collapse; width:100%; margin:0 0 {pg}pt; }} tr {{ break-inside:avoid; }}
th {{ text-align:left; font-size:7.4pt; font-weight:700; letter-spacing:0.08em; text-transform:uppercase; color:{A};
  padding:0 6pt 3pt 0; border-bottom:1pt solid {HAIR}; }}
td {{ vertical-align:top; padding:{cp}pt 6pt {cp}pt 0; border-bottom:0.6pt solid {HAIR}; }}
.sec-b5 td:first-child {{ width:48%; }} .sec-b6 td:first-child {{ width:42%; }} .sec-b8 td:first-child {{ width:50%; }}
table.src td {{ font-size:7.6pt; padding:2pt 6pt 2pt 0; white-space:nowrap; }} table.src td:nth-child(2) {{ white-space:normal; width:100%; }}
table.src td:nth-child(5) {{ font-size:6.8pt; font-weight:700; letter-spacing:0.06em; text-transform:uppercase; color:#1A7F64; }}
table.grid {{ margin-top:6pt; }} table.grid td:first-child {{ width:1.35in; white-space:nowrap; font-weight:700; }}
.sec-p9 .sec-head {{ display:none; }} .sec-p9 {{ margin-top:12pt; font-size:9.6pt; }}
.pagebreak {{ break-before:page; }}
"""


def build_doc(parts, rung, footer, style="house", classification=""):
    """parts: [(masthead title or None, subtitle, [section html])]; every part after the first starts on a new page."""
    logo = "data:image/png;base64," + (ASSETS / "talyx-logo-navy-base64.txt").read_text().strip()
    if style == "brief":
        sheet = brief_css(rung, footer)
        mh = lambda t, s, i: "" if t is None else (f'<h1 class="h">{inl(t)}</h1>' if i else (
            f'<div class="stamp"><img src="{logo}"/></div>'
            + (f'<div class="band"><div class="cls">{inl(classification)}</div></div>' if classification else "")
            + f'<h1 class="name">{inl(t)}</h1>'))
        wrap = lambda i, inner: f'<div class="part part-{i}">{inner}</div>'
    else:
        sheet = css(rung, footer)
        mh = lambda t, s, i: "" if t is None else (
            f'<div class="masthead-alt"><img class="mh-alt-logo" src="{logo}"/><div class="mh-alt-titles">'
            f'<h1 class="mh-alt-title">{inl(t)}</h1>' + (f'<div class="mh-alt-role">{inl(s)}</div>' if s else "") + "</div></div>")
        wrap = lambda i, inner: inner
    body = "".join(('<div class="pagebreak">' if i else "") + wrap(i, mh(t, s, i) + "".join(h)) + ("</div>" if i else "")
                   for i, (t, s, h) in enumerate(parts))
    return (f'<!doctype html><html lang="en"><head><meta charset="utf-8"><title>{html.escape(typo(parts[0][0] or ""))}</title>'
            f"<style>{sheet}</style></head><body><div class=\"page-content\">{body}</div></body></html>")


# ---------------------------------------------------------------- render --------------------------------
def page_count(path):
    try:
        import fitz
        with fitz.open(str(path)) as d:
            return d.page_count
    except ImportError:
        pass
    try:
        from pypdf import PdfReader
        return len(PdfReader(str(path)).pages)
    except ImportError:   # no PDF library: the page tree's /Count (Chromium writes it in plain text)
        data = pathlib.Path(path).read_bytes()
        counts = [int(n) for d in re.findall(rb"<<[^<>]*/Type\s*/Pages\b[^<>]*>>", data) for n in re.findall(rb"/Count\s+(\d+)", d)]
        return max(counts) if counts else len(re.findall(rb"/Type\s*/Page\b(?!s)", data))


CHROMES = ["/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
           "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
           "/Applications/Chromium.app/Contents/MacOS/Chromium",
           "/Applications/Brave Browser.app/Contents/MacOS/Brave Browser",
           r"C:\Program Files\Google\Chrome\Application\chrome.exe",
           r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
           "google-chrome", "google-chrome-stable", "chromium", "chromium-browser", "microsoft-edge", "msedge"]


def system_chrome():
    """A Chromium already on the computer, for hosts without Playwright's."""
    for c in [os.environ.get("TALYX_PDF_CHROME"), *CHROMES]:
        path = c and (c if os.path.isabs(c) else shutil.which(c))
        if path and os.path.exists(path):
            return path
    return None


def render_html(doc, out_path):
    with tempfile.NamedTemporaryFile(suffix=".html", delete=False, mode="w", encoding="utf-8") as tf:
        tf.write(doc); tmp = tf.name
    try:
        try:
            from playwright.sync_api import sync_playwright
            with sync_playwright() as p:
                br = p.chromium.launch()
                try:
                    pg = br.new_page()
                    pg.goto(pathlib.Path(tmp).as_uri())
                    pg.evaluate("document.fonts.ready")
                    pg.pdf(path=str(out_path), print_background=True, prefer_css_page_size=True, outline=True, tagged=True)
                finally:
                    br.close()
        except Exception:   # no Playwright, or no browser for it: use the computer's own Chromium
            chrome = system_chrome()
            if not chrome:
                sys.exit(json.dumps(dict(ok=False, path=None, reason="no Chromium on this computer: run "
                                         "`python3 format/talyx_pdf.py --setup` once, then render again")))
            with tempfile.TemporaryDirectory() as prof:
                subprocess.run([chrome, "--headless=new", "--disable-gpu", "--no-first-run", "--no-default-browser-check",
                                f"--user-data-dir={prof}", "--no-pdf-header-footer", "--generate-pdf-document-outline",
                                f"--print-to-pdf={out_path}", pathlib.Path(tmp).as_uri()],
                               check=True, capture_output=True, timeout=120)
    finally:
        pathlib.Path(tmp).unlink(missing_ok=True)
    return page_count(out_path)


def outline_titles(parts_md):
    """Bookmark names in document order: each masthead title, then '01 Snapshot', ... for its sections."""
    names = []
    for title, secs in parts_md:
        if title:
            names.append(typo(title))
        plain = lambda s: typo(re.sub(r"^[BP]\d+\s+|\*", "", s))
        names += ["%02d %s" % (n, plain(t)) for n, t, _ in secs if t]
    return names


def set_outline_titles(path, names):
    """Chromium names a bookmark from layout fragments, so a heading moved by a page break can read
    '05Discovery questionsDiscovery questions'. Rewrite each bookmark, in order, only when the count matches."""
    try:
        from pypdf import PdfWriter
        from pypdf.generic import NameObject, TextStringObject
    except ImportError:
        return
    w = PdfWriter(clone_from=str(path))
    items, node = [], w.root_object.get("/Outlines")
    def walk(first):
        while first is not None:
            item = first.get_object(); items.append(item)
            walk(item.get("/First")); first = item.get("/Next")
    walk(node.get_object().get("/First") if node is not None else None)
    if len(items) != len(names):
        return
    for item, name in zip(items, names):
        item[NameObject("/Title")] = TextStringObject(name)
    w.write(str(path))


def word_report(md):
    _, secs = sections(md)
    return sorted(((len(re.sub(r"<[^>]+>", " ", h).split()), t or "(preamble)") for _, t, h in secs), reverse=True)[:4]


def run(a):
    first = a.brief or a.input
    brief = a.style == "brief"
    mds = [pathlib.Path(first).read_text()]
    title, secs = sections(mds[0], line_per_para=brief)
    cut = len(secs)
    if a.script_after:   # the brief continues on a new page after the script, without a masthead
        cut = next((i + 1 for i, (_, t, _) in enumerate(secs) if t and t.split()[0] == a.script_after), None)
        if cut is None:
            sys.exit(f"--script-after {a.script_after}: no such section in {first}")
    htmls = lambda ss: columns(ss, [sec_html(n, t, h, a.style) for n, t, h in ss], a.columns)
    parts = [(a.title or title or pathlib.Path(first).stem, a.subtitle, htmls(secs[:cut]))]
    part_secs = [secs[:cut]]
    for path, default, sub in ((a.script, "Meeting script", a.script_subtitle or a.subtitle), (a.gaps, "Before you walk in", "")):
        if path:
            mds.append(pathlib.Path(path).read_text())
            t, ssecs = sections(mds[-1])
            parts.append((t or default, sub, htmls(ssecs))); part_secs.append(ssecs)
    if secs[cut:]:
        parts.append((None, "", htmls(secs[cut:]))); part_secs.append(secs[cut:])
    out = pathlib.Path(a.out).expanduser()
    out.parent.mkdir(parents=True, exist_ok=True)
    ladder = BRIEF_LADDER if brief else LADDER
    rungs = ladder if a.max_pages else ladder[:1]
    last = None
    names = outline_titles([(p[0], s) for p, s in zip(parts, part_secs)])
    for rung in rungs:
        pages = render_html(build_doc(parts, rung, a.footer, a.style, a.classification), out)
        set_outline_titles(out, names)
        last = (rung["name"], pages)
        if not a.max_pages or pages <= a.max_pages:
            print(json.dumps(dict(ok=True, pages=pages, rung=rung["name"], path=str(out), max_pages=a.max_pages)))
            return 0
    longest = sorted((w for md in mds for w in word_report(md)), reverse=True)[:4]
    out.unlink(missing_ok=True)   # no deliverable exists: never leave an over-length PDF to be picked up
    print(json.dumps(dict(ok=False, pages=last[1], rung=last[0], max_pages=a.max_pages, path=None,
                          reason="overflow at tightest rung -- cut these sections", longest_sections=longest)))
    return 2


def setup():
    cmds = [[sys.executable, "-m", "pip", "install", "-q", "playwright", "pypdf"], [sys.executable, "-m", "playwright", "install", "chromium"]]
    for c in cmds:
        print("$", " ".join(c)); subprocess.run(c, check=True)
    print("setup OK")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--input"); ap.add_argument("--brief"); ap.add_argument("--script"); ap.add_argument("--gaps")
    ap.add_argument("--script-subtitle", help="masthead subtitle for the script page (default: --subtitle)")
    ap.add_argument("--script-after", help="brief section id (e.g. B5): the script follows it; the rest of the brief follows the script")
    ap.add_argument("--out"); ap.add_argument("--title"); ap.add_argument("--subtitle", default="")
    ap.add_argument("--footer", default="Talyx AI · talyx.ai"); ap.add_argument("--max-pages", type=int)
    ap.add_argument("--style", choices=["house", "brief"], default="house", help="brief: the Intelligence Brief look")
    ap.add_argument("--columns", default="", help='side-by-side sections, e.g. "B3|B4,P1+P2|P5+P6"')
    ap.add_argument("--classification", default="", help="--style brief: the line above the name")
    ap.add_argument("--setup", action="store_true")
    a = ap.parse_args()
    if a.setup:
        return setup()
    if not (a.input or a.brief) or not a.out:
        ap.error("--input (or --brief [--script] [--gaps]) and --out are required")
    return run(a)


if __name__ == "__main__":
    sys.exit(main() or 0)
