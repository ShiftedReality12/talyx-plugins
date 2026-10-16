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
  talyx_pdf.py --brief brief.md --script script.md [--gaps gaps.md] --out x.pdf --max-pages N
      # each later part starts on its own page under its own masthead
  talyx_pdf.py --style brief --brief brief.md --script script.md --columns "B3|B4,P1+P2|P5+P6" \
      --classification "INTERNAL | ..." --out x.pdf --brief-pages N --max-pages N
      # the Intelligence Brief look: the brief's lines under `# Name` are its identity and meta lines; section
      # B1 is the Take box; --columns sets blocks side by side (| between columns, + within a column)

--max-pages N: renders on a density ladder (loose -> compact). If the tightest rung still overflows, exits 2
naming the longest sections. It never truncates and never spills silently. Exit 0 prints: pages, rung, path.
--brief-pages N: the first part (the brief) fills exactly N pages and its last section (the evidence ledger) starts
on page N, so the next part (the script) starts on page N + 1. When the sections before the ledger end on page N - 1,
the ledger moves to page N (never padding); when they end earlier still, exits 3. With a one-page script and
--max-pages N + 1 the PDF is exactly N + 1 pages: the ledger last on page N, the script on the last page.
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
# Ben, Oct 14: three colours, so the page reads when printed -- Midnight, black and white for all text and fills;
# the hairline is for rules only, never text (brand/BRAND.md)
# every number and colour of the page lives in pcp.yaml (page_budget, layout, balance, colors); render_skill.py writes them to
# layout.json beside this file, and eval.py hardcoded fails a literal here
LAYOUT = json.loads((HERE / "layout.json").read_text())
L, BAL, PB = LAYOUT["layout"], LAYOUT["balance"], LAYOUT["page_budget"]
MIDNIGHT, INK, WHITE, HAIR = (LAYOUT["colors"][k] for k in ("midnight", "ink", "white", "hair"))
rung = lambda r: dict(r, lh=r["line_height"], para=r["para_gap_pt"], sec=r["sec_gap_pt"])   # the registry's names, the renderer's short ones
LADDER = [rung(dict(r, mh=tuple(r["mh"]), page=tuple(r["page"]))) for r in PB["ladder"]]
BRIEF_LADDER = [rung(r) for r in PB["brief_ladder"]]
SZ = PB["text_sizes_pt"]
BODY_PT_FLOOR = PB["body_pt_floor"]


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
        h = inl(c)   # no keep(): in a narrow cell two glued words strand the word before; CSS text-wrap:pretty instead
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
        m = re.match(r"^([BP])(\d+)\s", parts[i].strip())   # a Bn id sets the printed number
        num = (int(m.group(2)) if m and m.group(1) == "B"   # Pn count in order, so an omitted block leaves no gap
               else start_num + len([s for s in secs if s[0]]))
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
        body = {"B6": b6_html, "B9": b9_html, "B10": b10_html}.get(sid and sid.group(0).strip(), lambda b: b)(body)
        return (f'<div class="sec{" sec-" + sid.group(0).strip().lower() if sid else ""}"><h2 class="sec-head">'
                f'{num_html}<span class="sec-title">{t}</span></h2><div class="sec-body">{body}</div></div>')
    return (f'<div class="sec{ref}"><h2 class="sec-head">'
            f'<span class="sec-num">{num:02d}</span> <span class="sec-title">{t}</span></h2>'
            f'<div class="sec-body">{body}</div></div>')


NO_READ = re.compile(r"(?:no read|none found|nothing found|not determined)\.?", re.I)


def b6_html(body):
    """B6: each row leads with its dimension label, set in bold. The dimensions with no read print as ONE line under
    the table, not a row each (Daniel, Oct 14); when no dimension has a read, that line stands in for the table. Their
    labels and any cited text print once each; only the repeated 'No read' / 'none found' markers go."""
    labels, notes = [], []

    def take(m):
        label, _, rest = m.group(1).strip().partition(":")
        labels.append(label.strip())
        rest = rest.strip()
        if rest and not NO_READ.fullmatch(re.sub(r"<[^>]+>", "", rest).strip()) and rest not in notes:
            notes.append(rest)
        return ""
    body = re.sub(r"<tr><td>((?:(?!</td>).)*)</td><td>\s*No read\.?\s*</td></tr>", take, body, flags=re.I)
    body = re.sub(r"<tr><td>([^<:]{3,40}):\s*", r'<tr><td><strong class="dim">\1:</strong> ', body)
    if labels:
        line = (f'<p class="lbl noread"><strong>No read:</strong> {" · ".join(labels)}'
                + (f" \u2014 {'; '.join(notes)}" if notes else "") + "</p>")
        body = re.sub(r"<table[^>]*>(?:(?!</table>).)*<tbody></tbody></table>", "", body)   # every row was No read
        body = body.replace("</table>", "</table>" + line, 1) if "</table>" in body else line + body
    return body


def b9_html(body):
    """B9: its subheads are lettered as in the schema (A. This meeting, B. Meeting two, C. After the meeting)."""
    letters = iter("ABCDEFGH")   # by position: a run that letters some heads itself gets no second A.
    return re.sub(r'<div class="sub">(?:[A-H]\. )?', lambda m: f'<div class="sub">{next(letters)}. ', body)


def b10_html(body):
    """B10: Still open prints one question per line; a grade of Measured is quiet ink and weight marks the others;
    a source shows its domain without www."""
    def bullets(m):
        items = [i.strip() for i in re.split(r"\s+·\s+", m.group(2)) if i.strip()]
        return m.group(1) + '<ul class="open">' + "".join(f"<li>{i}</li>" for i in items) + "</ul></td></tr>"
    body = re.sub(r"(<tr><td><strong>Still open</strong></td><td>)((?:(?!</td>).)*)</td></tr>", bullets, body)
    body = re.sub(r"<td>(Measured|Derived|Inference|Not determined)</td>",
                  lambda m: f'<td class="grade g-{m.group(1).split()[0].lower()}">{m.group(1)}</td>', body)
    return re.sub(r'(<a href="[^"]+">)www\.', r"\1", body)


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


# --style brief: each side-by-side row of the brief takes the column split (40-60% .. 60-40%) at which it is shortest,
# so its two columns end together (no blank quadrant) and the row needs the least height on its page; at each split,
# each two-column table in the row first takes the first-column width (30-70%) at which it is shortest. It runs in the
# page once the fonts have loaded, so it measures with the printed font at the printed width. Then pages 1 and 2 keep
# the rung's type and each spreads what is left on it between its blocks, rows and bullets, so neither ends in a
# blank band (Daniel, Oct 14: every page fully used, no dead space).
# The script (page 3) flows its blocks in order down the left column and on into the right, which end together;
# then it takes the largest type (the rung's size up to 2pt more) and leading that still fit its one page, and spreads
# what is left between its sections and bullets, so a short script fills the page instead of ending in a blank band.
BALANCE = "<script>const CFG = " + json.dumps(BAL) + ";" + """
function shortest(lo, hi, step, set, height) {   // the lowest height; of settings within 1px of it, the nearest to 50
  const tries = [];
  for (let p = lo; p <= hi; p += step) { set(p); tries.push({p, h: height()}); }
  const low = Math.min(...tries.map(t => t.h));
  set(tries.filter(t => t.h <= low + 1).sort((x, y) => Math.abs(x.p - 50) - Math.abs(y.p - 50))[0].p);
}
function balanceRow(row) {
  const cols = [...row.children], tables = [...row.querySelectorAll('table:not(.src)')];
  const fit = () => tables.forEach(t => shortest(...CFG.table_split, p => t.style.setProperty('--c1', p + '%'), () => t.offsetHeight));
  shortest(...CFG.col_split, p => { row.style.gridTemplateColumns = p + 'fr ' + (100 - p) + 'fr'; fit(); },
           () => Math.max(...cols.map(c => c.offsetHeight)));
}
function balance() {
  document.querySelectorAll('.part-0 .two').forEach(balanceRow);
  document.querySelectorAll('.part-0').forEach(fillBrief);
  document.querySelectorAll('.part-1').forEach(fill);
}
const LIMIT = (CFG.page_in - CFG.margin_top_in - CFG.margin_bottom_in - CFG.spare_in) * CFG.px_per_in;   // a page's content height in CSS px, less 0.2in to spare
function spread(els, height, limit = LIMIT) {   // the most --fill (space between blocks, rows and bullets) that still fits
  const set = g => els.forEach(e => e.style.setProperty('--fill', g + 'px'));
  let lo = 0, hi = CFG.spread_max_px;
  for (let i = 0; i < CFG.spread_steps; i++) { const g = (lo + hi) / 2; set(g); if (height() <= limit) lo = g; else hi = g; }
  set(lo);
}
function fillBrief(part) {   // pages 1 and 2 keep the rung's type; what is left on each page goes between its blocks
  const kids = [...part.children], k = kids.findIndex(e => e.matches('.two:has(.sec-b7), .sec-b7'));
  if (k < 1) return;
  const first = (CFG.margin_top_in - CFG.first_top_in) * CFG.px_per_in;   // page 1's top margin is 0.30in (@page :first), the others 0.42in
  const pages = [[part, kids.slice(0, k), LIMIT + first], [kids[k], kids.slice(k), LIMIT]];
  for (const [top, els, limit] of pages) {
    const height = () => Math.max(...els.map(e => e.getBoundingClientRect().bottom)) - top.getBoundingClientRect().top;
    if (height() <= limit) spread(els, height, limit);
  }
  part.querySelectorAll('.two').forEach(balanceRow);   // the wider spacing can move the best column split
}
function fill(part) {
  const limit = LIMIT;
  const base = parseFloat(getComputedStyle(part).fontSize) * 0.75;   // the rung's body size in pt: the floor
  let fits = false;
  for (let pt = base + CFG.enlarge_pt; pt >= base - 0.01 && !fits; pt -= CFG.enlarge_step_pt) {
    for (const lh of pt > base ? CFG.open_leading : CFG.open_leading.concat([''])) {   // larger type keeps open leading
      part.style.fontSize = pt + 'pt'; part.style.lineHeight = lh;
      if (part.offsetHeight <= limit) { fits = true; break; }
    }
  }
  if (!fits) { part.style.fontSize = part.style.lineHeight = ''; return; }   // the page gate moves to a tighter rung
  spread([part], () => part.offsetHeight);   // what is left goes between the sections and bullets, never a band at the bottom
}
document.fonts.ready.then(balance);
</script>"""


# ---------------------------------------------------------------- document --------------------------------
def css(rung, footer):
    archivo = base64.b64encode((ASSETS / "archivo-variable.woff2").read_bytes()).decode()
    b, lh, pg, sg = rung["body_pt"], rung["lh"], rung["para"], rung["sec"]
    (mt, mb), cp, (top, bottom) = rung["mh"], rung["cell"], rung["page"]
    return f"""
@font-face {{ font-family:'Archivo'; font-weight:{L['font_face__font-weight']} {L['font_face__font-weight_2']}; src:url(data:font/woff2;base64,{archivo}) format('woff2'); }}
@page {{ size: Letter; margin: {top}in 0 {bottom}in 0;
  @bottom-left {{ content: "{html.escape(footer)}"; font-family:'Archivo'; font-size:{L['bottom_left__font-size']}; color:{MIDNIGHT}; padding-left:{L['bottom_left__padding-left']}; }}
  @bottom-right {{ content: "Page " counter(page) " of " counter(pages); font-family:'Archivo'; font-size:{L['bottom_right__font-size']}; color:{MIDNIGHT}; padding-right:{L['bottom_right__padding-right']}; }} }}
html {{ -webkit-print-color-adjust:exact; }}
body {{ font-family:'Archivo', -apple-system, sans-serif; color:{INK}; margin:0; hyphens:manual; -webkit-hyphens:manual; font-variant-ligatures:common-ligatures; }}
.page-content {{ padding:0 {L['page_content__padding']}; position:relative; }}
.masthead-alt {{ position:relative; padding-top:{mt}in; margin:0 0 {mb}in 0; font-family:'Archivo'; hyphens:none; }}
.mh-alt-logo {{ position:absolute; top:{L['mh_alt_logo__top']}; right:{L['mh_alt_logo__right']}; width:{L['mh_alt_logo__width']}; height:auto; }}
.mh-alt-titles {{ padding-right:{L['mh_alt_titles__padding-right']}; }}
.mh-alt-title {{ margin:0; font-size:{L['mh_alt_title__font-size']}; font-weight:{L['mh_alt_title__font-weight']}; letter-spacing:{L['mh_alt_title__letter-spacing']}; line-height:{L['mh_alt_title__line-height']}; color:{MIDNIGHT}; }}
.mh-alt-role {{ font-size:{L['mh_alt_role__font-size']}; font-weight:{L['mh_alt_role__font-weight']}; color:{MIDNIGHT}; margin-top:{L['mh_alt_role__margin-top']}; }}
.sec {{ margin:0; }}
.sec-head {{ display:block; font-size:inherit; font-weight:inherit; line-height:{L['sec_head__line-height']}; padding-bottom:{L['sec_head__padding-bottom']}; margin:{sg}pt 0 {max(sg-L['sec_head__expr'],L['sec_head__expr_2'])}pt; break-after:avoid; }}
.sec:first-child .sec-head {{ margin-top:0; }}
.sec-num {{ font-size:{L['sec_num__font-size']}; font-weight:{L['sec_num__font-weight']}; color:{MIDNIGHT}; font-variant-numeric:lining-nums tabular-nums; }}
.sec-title {{ font-size:{L['sec_title__font-size']}; font-weight:{L['sec_title__font-weight']}; letter-spacing:{L['sec_title__letter-spacing']}; color:{MIDNIGHT}; }}
.sub {{ font-size:{b}pt; font-weight:{L['sub__font-weight']}; color:{MIDNIGHT}; margin:{pg}pt 0 {L['sub__margin']}; }}
p {{ font-size:{b}pt; line-height:{lh}; margin:0 0 {pg}pt; max-width:{L['p__max-width']}; }}
blockquote {{ font-size:{b + L['blockquote__expr']}pt; line-height:{lh}; margin:0 0 {pg}pt; padding:{L['blockquote__padding']} 0 {L['blockquote__padding_2']} calc({L['blockquote__padding_3']} - {L['blockquote__padding_4']}); border-left:{L['blockquote__border-left']} solid {MIDNIGHT}; max-width:{L['blockquote__max-width']}; }}
ul, ol {{ margin:0 0 {pg}pt; padding-left:{L['ul_ol__padding-left']}; max-width:{L['ul_ol__max-width']}; }}
ol > li::marker {{ color:{MIDNIGHT}; font-weight:{L['ol_li_marker__font-weight']}; font-variant-numeric:tabular-nums; }}
li {{ font-size:{b}pt; line-height:{lh}; margin:{max(pg-L['li__expr'],L['li__expr_2'])}pt 0; }}
li > ul, li > ol {{ margin:{max(pg-L['li_ul_li_ol__expr'],L['li_ul_li_ol__expr_2'])}pt 0 {max(pg-L['li_ul_li_ol__expr_3'],L['li_ul_li_ol__expr_4'])}pt; padding-left:{L['li_ul_li_ol__padding-left']}; }}
li li {{ margin:{max(pg-L['li_li__expr'],L['li_li__expr_2'])}pt 0; }}
li.check {{ list-style-type:"\\2610\\00a0\\00a0"; }} li.check.done {{ list-style-type:"\\2611\\00a0\\00a0"; }}
p.lbl {{ padding-left:{L['p_lbl__padding-left']}; text-indent:{L['p_lbl__text-indent']}; margin-bottom:{max(pg-L['p_lbl__expr'],L['p_lbl__expr_2'])}pt; max-width:none; }}
ul, ul ul {{ list-style-type:disc; }}
.hang {{ display:block; padding-left:{L['hang__padding-left']}; text-indent:{L['hang__text-indent']}; }} .hang > .num {{ display:inline-block; width:{L['hang_num__width']}; text-indent:0; }}
.amp {{ font-family:'Helvetica Neue', Helvetica, Arial, sans-serif; }}
p.lbl > strong:first-child + em {{ margin-left:{L['p_lbl_strong_first_child_em__margin-left']}; }}
.num {{ color:{MIDNIGHT}; font-weight:{L['num__font-weight']}; font-variant-numeric:tabular-nums; }}
table.kv td:first-child, table.kv th:first-child {{ white-space:nowrap; }}
p.lbl > strong:first-child, li > strong:first-child, blockquote > strong:first-child {{ color:{MIDNIGHT}; font-weight:{L['p_lbl_strong_first_child_li_strong_first__font-weight']}; }}
strong {{ font-weight:{L['strong__font-weight']}; }} em {{ font-style:italic; font-weight:{L['em__font-weight']}; }}
a {{ color:{MIDNIGHT}; text-decoration:underline; text-decoration-thickness:{L['a__text-decoration-thickness']}; text-underline-offset:{L['a__text-underline-offset']}; }}
.cite {{ color:{MIDNIGHT}; font-size:{L['cite__font-size']}; font-weight:{L['cite__font-weight']}; font-variant-numeric:tabular-nums; }}
table {{ border-collapse:collapse; width:100%; margin:0 0 {pg}pt; table-layout:auto; break-inside:avoid; }}
table.src {{ break-inside:auto; }}
td:last-child, th:last-child {{ padding-right:0; }}
tr {{ break-inside:avoid; }} thead {{ display:table-header-group; }}
th {{ font-size:{b-L['th__expr']}pt; font-weight:{L['th__font-weight']}; text-transform:uppercase; letter-spacing:{L['th__letter-spacing']}; color:{MIDNIGHT}; text-align:left; padding:{cp}px {L['th__padding']} {cp}px 0; border-bottom:{L['th__border-bottom']} solid {MIDNIGHT}; }}
td {{ font-size:{b-L['td__expr']}pt; line-height:{lh}; padding:{cp}px {L['td__padding']} {cp}px 0; border-bottom:{L['td__border-bottom']} solid {HAIR}; vertical-align:top; overflow-wrap:anywhere; text-wrap:pretty; }}
tbody tr:last-child td {{ border-bottom:{L['tbody_tr_last_child_td__border-bottom']} solid {INK}; }}
table.src td {{ white-space:nowrap; overflow-wrap:normal; }}
/* everything in a Sources section is reference material: one small size and fixed compact rows at every density */
.sec.ref td {{ font-size:{L['sec_ref_td__font-size']}; line-height:{L['sec_ref_td__line-height']}; padding:{L['sec_ref_td__padding']} {L['sec_ref_td__padding_2']} {L['sec_ref_td__padding_3']} 0; }} .sec.ref th {{ font-size:{L['sec_ref_th__font-size']}; padding:{L['sec_ref_th__padding']} {L['sec_ref_th__padding_2']} {L['sec_ref_th__padding_3']} 0; }}
.sec.ref table {{ margin-bottom:{L['sec_ref_table__margin-bottom']}; }}
table.src td:nth-child(2) {{ white-space:normal; width:100%; }}
table.grid td {{ font-size:{b}pt; padding:{max(cp - L['table_grid_td__expr'], L['table_grid_td__expr_2'])}px {L['table_grid_td__padding']} {max(cp - L['table_grid_td__expr_3'], L['table_grid_td__expr_4'])}px 0; }}
table.grid td:first-child {{ width:{L['table_grid_td_first_child__width']}; font-weight:{L['table_grid_td_first_child__font-weight']}; color:{MIDNIGHT}; }}
table.grid tbody tr:last-child td {{ border-bottom:{L['table_grid_tbody_tr_last_child_td__border-bottom']} solid {HAIR}; }}
.pagebreak {{ break-before:page; }}
.pagebreak .masthead-alt {{ padding-top:0; }}
"""


def brief_css(rung, footer):
    """--style brief: the approved schema's look (Oct 8) -- classification band, Take box, small-caps heads, two columns."""
    archivo = base64.b64encode((ASSETS / "archivo-variable.woff2").read_bytes()).decode()
    b, lh, pg, sg, cp = rung["body_pt"], rung["lh"], rung["para"], rung["sec"], rung["cell"]
    return f"""
@font-face {{ font-family:'Archivo'; font-weight:{L['font_face__font-weight_3']} {L['font_face__font-weight_4']}; src:url(data:font/woff2;base64,{archivo}) format('woff2'); }}
@page {{ size: Letter; margin: {L['page__margin']} 0 {L['page__margin_2']} 0;
  @bottom-left {{ content: "{html.escape(footer)}"; font-family:'Archivo'; font-size:{SZ['footer']}pt; color:{MIDNIGHT}; padding-left:{L['bottom_left__padding-left_2']}; }}
  @bottom-right {{ content: "page " counter(page) " of " counter(pages); font-family:'Archivo'; font-size:{SZ['footer']}pt; color:{MIDNIGHT}; padding-right:{L['bottom_right__padding-right_2']}; }} }}
@page :first {{ margin-top:{L['page_first__margin-top']}; }}   /* the logo stamp starts page 1 inside the printable area: a negative margin clipped its top */
html {{ -webkit-print-color-adjust:exact; }}
body {{ font-family:'Archivo', sans-serif; color:{MIDNIGHT}; margin:0; font-size:{b}pt; line-height:{lh}; }}
.page-content {{ padding:0 {L['page_content__padding_2']}; }}
.stamp {{ display:flex; justify-content:flex-end; margin:0 {L['stamp__margin']} {L['stamp__margin_2']} 0; }} .stamp img {{ width:{L['stamp_img__width']}; height:auto; }}
.band {{ display:flex; align-items:center; height:{L['band__height']}; border-bottom:{L['band__border-bottom']} solid {HAIR}; margin-bottom:{L['band__margin-bottom']}; }}
.cls {{ font-size:{SZ['band']}pt; font-weight:{L['cls__font-weight']}; letter-spacing:{L['cls__letter-spacing']}; color:{MIDNIGHT}; }}
h1.name {{ font-size:{SZ['name']}pt; font-weight:{L['h1_name__font-weight']}; margin:0 0 {L['h1_name__margin']}; }}
.part-0 > .sec.pre p:first-child {{ font-size:{SZ['preline']}pt; font-weight:{L['part_0_sec_pre_p_first_child__font-weight']}; color:{MIDNIGHT}; margin:0 0 {L['part_0_sec_pre_p_first_child__margin']}; }}
.part-0 > .sec.pre p + p {{ font-size:{SZ['meta']}pt; color:{MIDNIGHT}; line-height:{L['part_0_sec_pre_p_p__line-height']}; margin:0 0 {L['part_0_sec_pre_p_p__margin']}; }}
.sec.pre p strong {{ font-weight:{L['sec_pre_p_strong__font-weight']}; }}
h1.h, .sec-head {{ display:block; font-size:{SZ['sec_head']}pt; font-weight:{L['h1_h_sec_head__font-weight']}; letter-spacing:{L['h1_h_sec_head__letter-spacing']}; text-transform:uppercase; color:{MIDNIGHT};
  border-bottom:{L['h1_h_sec_head__border-bottom']} solid {HAIR}; padding-bottom:{L['h1_h_sec_head__padding-bottom']}; margin:calc({sg}pt + var(--fill, 0px)) 0 {L['h1_h_sec_head__margin']}; break-after:avoid; }}
/* one heading rhythm: a block's last line carries no bottom margin, so every head sits {sg}pt below the text above it */
.sec-body > :last-child, .sec-body > :last-child > li:last-child {{ margin-bottom:0; }}
h1.h {{ margin-top:0; }} .part-1 > .sec.pre p {{ font-size:{SZ['meta']}pt; color:{MIDNIGHT}; margin:{L['part_1_sec_pre_p__margin']} 0 {L['part_1_sec_pre_p__margin_2']}; }}
p {{ margin:0 0 {pg}pt; }} p.lbl {{ margin:0 0 {pg}pt; }}
ul, ol {{ margin:0 0 {pg}pt; padding-left:{L['ul_ol__padding-left_2']}; }} li {{ margin:0 0 calc({L['li__margin']} + var(--fill, {L['li__margin_2']}) / 4); }} li > ul, li > ol {{ margin:{L['li_ul_li_ol__margin']} 0 0; }}
strong {{ font-weight:{L['strong__font-weight_2']}; }} em {{ font-style:italic; }}
a {{ color:{MIDNIGHT}; text-decoration:underline; text-decoration-thickness:{L['a__text-decoration-thickness_2']}; text-underline-offset:{L['a__text-underline-offset_2']}; }}
.cite {{ color:{MIDNIGHT}; font-size:{L['cite__font-size_2']}; font-weight:{L['cite__font-weight_2']}; }}
.sub {{ font-size:{SZ['sub']}pt; font-weight:{L['sub__font-weight_2']}; margin:{L['sub__margin_2']} 0 {L['sub__margin_3']}; }} .sec-b9 .sub {{ margin-top:calc({L['sec_b9_sub__margin-top']} + var(--fill, {L['sec_b9_sub__margin-top_2']}) / 2); }} .sec-b9 .sub:first-child {{ margin-top:0; }}
.two {{ display:grid; grid-template-columns:{L['two__grid-template-columns']} {L['two__grid-template-columns_2']}; column-gap:{L['two__column-gap']}; align-items:start; break-inside:avoid; }}
@media screen {{ body {{ width:{L['body__width']}; }} }}   /* BALANCE measures at the printed width */
/* the schema's page 2 opens on Who decides | Strongest case against: B1-B6 are page 1, even when page 1 has room */
.part-0 .two:has(.sec-b7), .part-0 > .sec-b7 {{ break-before:page; }} .part-0 .sec-b7 .sec-head, .part-0 .sec-b8 .sec-head {{ margin-top:{sg}pt; }}
.sec-b1 .sec-head {{ display:none; }}
.sec-b1 .sec-body {{ background:{MIDNIGHT}; color:{WHITE}; font-size:{b}pt; line-height:{L['sec_b1_sec_body__line-height']}; padding:{L['sec_b1_sec_body__padding']} {L['sec_b1_sec_body__padding_2']}; border-radius:{L['sec_b1_sec_body__border-radius']}; margin-top:{L['sec_b1_sec_body__margin-top']}; }}
.sec-b1 p {{ margin:0; }} .sec-b1 strong, .sec-b1 a, .sec-b1 .cite {{ color:{WHITE}; }}
.sec-b2 ol {{ padding-left:{L['sec_b2_ol__padding-left']}; }} .sec-b2 ol > li {{ font-size:{b + L['sec_b2_ol_li__expr']}pt; font-weight:{L['sec_b2_ol_li__font-weight']}; }}
.sec-b2 li > ul {{ list-style:none; padding-left:0; }} .sec-b2 li li {{ font-size:{SZ['decides']}pt; font-weight:{L['sec_b2_li_li__font-weight']}; color:{MIDNIGHT}; margin:0; }}
.sec-b2 li li strong {{ color:{MIDNIGHT}; }}
table {{ border-collapse:collapse; width:100%; margin:0 0 {pg}pt; break-inside:avoid; }} tr {{ break-inside:avoid; }}
table.src {{ break-inside:auto; }}
th {{ text-align:left; font-size:{SZ['th']}pt; font-weight:{L['th__font-weight_2']}; letter-spacing:{L['th__letter-spacing_2']}; text-transform:uppercase; color:{MIDNIGHT};
  padding:0 {L['th__padding_2']} {L['th__padding_3']} 0; border-bottom:{L['th__border-bottom_2']} solid {HAIR}; }}
td {{ vertical-align:top; padding:calc({cp}pt + var(--fill, 0px) / 4) {L['td__padding_2']} calc({cp}pt + var(--fill, 0px) / 4) 0; border-bottom:{L['td__border-bottom_2']} solid {HAIR}; text-wrap:pretty; }}
.sec-b5 td:first-child {{ width:var(--c1, 48%); }} .sec-b6 td:first-child {{ width:var(--c1, 55%); }} .sec-b8 td:first-child {{ width:var(--c1, 50%); }}
.sec-b6 td {{ padding-top:calc({max(cp - L['sec_b6_td__expr'], L['sec_b6_td__expr_2'])}pt + var(--fill, 0px) / 4); padding-bottom:calc({max(cp - L['sec_b6_td__expr_3'], L['sec_b6_td__expr_4'])}pt + var(--fill, 0px) / 4); }}
.sec-b6 p.noread {{ margin:{L['sec_b6_p_noread__margin']} 0 {pg}pt; }}
/* the ledger block (B10) is one scale: its note line small, its table and its label grid one size, one grid */
.sec-b10 .sec-body > p:first-child {{ font-size:{SZ['ledger_note']}pt; color:{MIDNIGHT}; margin:0 0 {L['sec_b10_sec_body_p_first_child__margin']}; }}
.sec-b10 table td {{ font-size:{SZ['ledger']}pt; line-height:{L['sec_b10_table_td__line-height']}; padding:calc({L['sec_b10_table_td__padding']} + var(--fill, {L['sec_b10_table_td__padding_2']}) / 4) {L['sec_b10_table_td__padding_3']} calc({L['sec_b10_table_td__padding_4']} + var(--fill, {L['sec_b10_table_td__padding_5']}) / 4) 0; }}
table.src td {{ white-space:nowrap; }} table.src td:nth-child(2) {{ white-space:normal; }}
table.src td:nth-child(1) {{ width:4%; }} table.src td:nth-child(2) {{ width:36%; }} table.src td:nth-child(3) {{ width:24%; }} table.src td:nth-child(4) {{ width:18%; }} table.src td:nth-child(5) {{ width:14%; }}
table.src td:first-child .cite {{ font-size:{L['table_src_td_first_child_cite__font-size']}; color:{MIDNIGHT}; font-variant-numeric:tabular-nums; }}
table.src td.grade {{ font-size:{SZ['grade']}pt; font-weight:{L['table_src_td_grade__font-weight']}; letter-spacing:{L['table_src_td_grade__letter-spacing']}; text-transform:uppercase; color:{MIDNIGHT}; }}
table.src td.g-derived, table.src td.g-inference, table.src td.g-not {{ font-weight:{L['table_src_td_g_derived_table_src_td_g_in__font-weight']}; }}
table.grid {{ margin-top:{L['table_grid__margin-top']}; }} table.grid td:first-child {{ width:{L['table_grid_td_first_child__width_2']}; white-space:nowrap; font-weight:{L['table_grid_td_first_child__font-weight_2']}; }}
.sec-b10 ul.open {{ margin:0; padding-left:{L['sec_b10_ul_open__padding-left']}; }} .sec-b10 ul.open li {{ margin:0; }}
.sec-p9 .sec-head {{ display:none; }} .sec-p9 {{ margin-top:calc({L['sec_p9__margin-top']} + var(--fill, {L['sec_p9__margin-top_2']})); }}
/* page 3 reads as one flow down the left column and on into the right; a bullet never splits, a head keeps its first line */
.part-1 .two {{ display:block; columns:2; column-gap:{L['part_1_two__column-gap']}; }} .part-1 .two > div {{ display:contents; }}
.part-1 li, .part-1 p {{ break-inside:avoid; }}
.part-1 .two > div:first-child > .sec:first-child .sec-head {{ margin-top:{sg}pt; }}
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
            f"<style>{sheet}</style></head><body><div class=\"page-content\">{body}</div>"
            f"{BALANCE if style == 'brief' else ''}</body></html>")


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
                    pg.evaluate("document.fonts.ready")   # the page's own fonts.ready callback (BALANCE) runs first
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
                                "--virtual-time-budget=10000",   # print after the page's fonts.ready script, on every Chromium
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


def fill_brief(parts, rung, a, out):
    """--brief-pages N: the brief (the first part) fills exactly N pages and its last section (the evidence ledger)
    starts on page N, so the next part starts on page N + 1. When the sections before the ledger end before page N,
    the ledger moves to page N; nothing is padded. Returns the parts to render, None if the brief overflows N pages
    at this rung, False if it cannot fill them (the sections before the ledger end before page N - 1)."""
    t, s, h = parts[0]
    pages = lambda ps: render_html(build_doc(ps, rung, a.footer, a.style, a.classification), out)
    k = pages([(t, s, h[:-1])])           # where the sections before the ledger end
    if k > a.brief_pages:
        return None
    if k < a.brief_pages - 1:
        return False
    if k == a.brief_pages - 1:            # the ledger would start on page N - 1: it starts page N instead
        parts = [(t, s, h[:-1] + ['<div class="pagebreak">' + h[-1] + "</div>"])] + parts[1:]
    return parts if pages(parts[:1]) == a.brief_pages else None


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
        doc_parts = parts
        if a.brief_pages and len(parts) > 1:   # the next part (the script) must start on page brief_pages + 1
            fit = fill_brief(parts, rung, a, out)
            if fit is None:                    # the brief overflows its pages at this rung: try a tighter one
                last = (rung["name"], None); continue
            if fit is False:
                out.unlink(missing_ok=True)
                print(json.dumps(dict(ok=False, path=None, rung=rung["name"], brief_pages=a.brief_pages,
                                      reason="the brief cannot fill its pages even with its last section on a page of its own")))
                return 3
            doc_parts = fit
        pages = render_html(build_doc(doc_parts, rung, a.footer, a.style, a.classification), out)
        set_outline_titles(out, names)
        last = (rung["name"], pages)
        if not a.max_pages or pages <= a.max_pages:
            print(json.dumps(dict(ok=True, pages=pages, rung=rung["name"], path=str(out), max_pages=a.max_pages,
                                  brief_pages=a.brief_pages)))
            return 0
    longest = sorted((w for md in mds for w in word_report(md)), reverse=True)[:4]
    out.unlink(missing_ok=True)   # no deliverable exists: never leave an over-length PDF to be picked up
    print(json.dumps(dict(ok=False, pages=last[1], rung=last[0], max_pages=a.max_pages, path=None,
                          reason=("overflow at tightest rung -- cut these sections" if last[1] is not None else
                                  f"the brief overflows its {a.brief_pages} pages at the tightest rung -- cut these sections"),
                          longest_sections=longest)))
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
    ap.add_argument("--brief-pages", type=int, help="the first part fills exactly N pages; the next part starts on page N + 1")
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
