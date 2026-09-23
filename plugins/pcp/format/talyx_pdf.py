#!/usr/bin/env python3
"""talyx_pdf.py -- portable Talyx house-style (masthead-alt) Markdown -> PDF, with a hard page gate.

Self-contained: this file + assets/archivo-variable.woff2 + assets/talyx-logo-navy-base64.txt.
Needs: playwright (+ chromium) and pypdf or pymupdf for the page count.  `python3 talyx_pdf.py --setup` installs them.

Markdown it understands (minimal, generic):
  `# Title`            document title (overridden by --title)
  `## Heading`         numbered, bookmarked section
  paragraphs, `- ` bullets, `| a | b |` pipe tables, **bold**, *italic*, [n] citations

Usage:
  talyx_pdf.py --input doc.md --out doc.pdf [--title ..] [--subtitle ..] [--footer ..] [--max-pages N]
  talyx_pdf.py --brief brief.md --script script.md --out x.pdf --max-pages 3     # script starts on its own page

--max-pages N: renders on a density ladder (loose -> compact). If the tightest rung still overflows, exits 2
naming the longest sections. It never truncates and never spills silently. Exit 0 prints: pages, rung, path.
"""
import argparse
import base64
import html
import json
import pathlib
import re
import subprocess
import sys
import tempfile

HERE = pathlib.Path(__file__).resolve().parent
ASSETS = HERE / "assets"
ACCENT, INK, HAIR, MIDNIGHT = "#1C3A66", "#000000", "#E8EAED", "#0F2744"

LADDER = [
    dict(name="loose",   body_pt=11.0, lh=1.42, para=6, sec=12),
    dict(name="normal",  body_pt=10.5, lh=1.36, para=5, sec=10),
    dict(name="tight",   body_pt=10.0, lh=1.30, para=4, sec=8),
    dict(name="compact", body_pt=10.0, lh=1.24, para=3, sec=6),
]


# ---------------------------------------------------------------- markdown -> html --------------------------
def typo(t):
    t = re.sub(r'(^|[\s(\[*])"', "\\1\u201c", t); t = t.replace('"', "\u201d")
    t = re.sub(r"(^|[\s(\[*])'", "\\1\u2018", t); t = t.replace("'", "\u2019")
    return t.replace(" - ", " \u2013 ").replace("->", "\u2192")


def inl(t):
    t = html.escape(typo(t), quote=False)
    t = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", t)
    t = re.sub(r"(?<!\*)\*([^*]+?)\*(?!\*)", r"<em>\1</em>", t)
    t = re.sub(r"\[(\d+)\]", r'<span class="cite">[\1]</span>', t)
    return t


def _table(lines):
    rows = [[c.strip() for c in ln.strip().strip("|").split("|")] for ln in lines if not re.match(r"^\s*\|?\s*:?-+", ln)]
    if not rows:
        return ""
    head = "".join(f"<th>{inl(c)}</th>" for c in rows[0])
    body = "".join("<tr>" + "".join(f"<td>{inl(c)}</td>" for c in r) + "</tr>" for r in rows[1:])
    return f"<table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table>"


def body_html(txt):
    out, para, bullets, table = [], [], [], []

    def flush():
        nonlocal para, bullets, table
        if para: out.append(f"<p>{inl(' '.join(para))}</p>"); para = []
        if bullets: out.append("<ul>" + "".join(f"<li>{inl(b)}</li>" for b in bullets) + "</ul>"); bullets = []
        if table: out.append(_table(table)); table = []

    for ln in txt.splitlines():
        s = ln.rstrip()
        if not s.strip():
            flush(); continue
        if s.lstrip().startswith("|"):
            if para or bullets: flush()
            table.append(s); continue
        if re.match(r"^\s*[-*]\s+", s):
            if para or table: flush()
            bullets.append(re.sub(r"^\s*[-*]\s+", "", s)); continue
        if re.match(r"^###\s+", s):
            flush(); out.append(f'<div class="sub">{inl(re.sub(r"^###\s+", "", s))}</div>'); continue
        if bullets or table: flush()
        para.append(s.strip())
    flush()
    return "\n".join(out)


def sections(md, start_num=1):
    """[(num, title, html)] from ## headings; a leading # line is returned as the title."""
    title = None
    m = re.match(r"^\s*#\s+(.+?)\s*$", md.split("\n", 1)[0])
    if m:
        title = m.group(1); md = md.split("\n", 1)[1] if "\n" in md else ""
    parts = re.split(r"^##\s+(.+)$", md, flags=re.M)
    secs = []
    if parts[0].strip():
        secs.append((None, None, body_html(parts[0])))
    for i in range(1, len(parts), 2):
        secs.append((start_num + len([s for s in secs if s[0]]), parts[i].strip(), body_html(parts[i + 1])))
    return title, secs


def sec_html(num, title, body):
    if title is None:
        return f'<div class="sec"><div class="sec-body">{body}</div></div>'
    t = inl(re.sub(r"^[BP]\d+\s+", "", title))  # strip Bn/Pn ids from the printed title
    return (f'<div class="sec"><div class="sec-head" data-bm="{html.escape(title)}">'
            f'<span class="sec-num">{num:02d}</span> <span class="sec-title">{t}</span></div>'
            f'<div class="sec-body">{body}</div></div>')


# ---------------------------------------------------------------- document --------------------------------
def css(rung, footer):
    archivo = base64.b64encode((ASSETS / "archivo-variable.woff2").read_bytes()).decode()
    b, lh, pg, sg = rung["body_pt"], rung["lh"], rung["para"], rung["sec"]
    return f"""
@font-face {{ font-family:'Archivo'; font-weight:100 900; src:url(data:font/woff2;base64,{archivo}) format('woff2'); }}
@page {{ size: Letter; margin: 0.55in 0 0.6in 0;
  @bottom-left {{ content: "{html.escape(footer)}"; font-family:'Archivo'; font-size:7.5pt; color:{ACCENT}; padding-left:0.5in; }}
  @bottom-right {{ content: "Page " counter(page) " of " counter(pages); font-family:'Archivo'; font-size:7.5pt; color:{ACCENT}; padding-right:0.5in; }} }}
html {{ -webkit-print-color-adjust:exact; }}
body {{ font-family:'Archivo', -apple-system, sans-serif; color:{INK}; margin:0; hyphens:auto; -webkit-hyphens:auto; font-variant-ligatures:common-ligatures; }}
.page-content {{ padding:0 0.5in; position:relative; }}
.masthead-alt {{ padding-top:0.15in; margin:0 0 0.22in 0; font-family:'Archivo'; hyphens:none; }}
.mh-alt-logo {{ position:absolute; top:0.05in; right:0.15in; width:88px; height:auto; }}
.mh-alt-titles {{ padding-right:1.2in; }}
.mh-alt-title {{ font-size:22pt; font-weight:800; letter-spacing:-0.02em; line-height:1.02; color:{MIDNIGHT}; }}
.mh-alt-role {{ font-size:10.5pt; font-weight:500; color:{ACCENT}; margin-top:5px; }}
.sec {{ margin:0; }}
.sec-head {{ display:block; line-height:1.0; padding-bottom:3px; margin:{sg}pt 0 {max(sg-6,3)}pt; break-after:avoid; bookmark-level:1; bookmark-label:attr(data-bm); }}
.sec:first-child .sec-head {{ margin-top:0; }}
.sec-num {{ font-size:9.5pt; font-weight:700; color:{ACCENT}; font-variant-numeric:lining-nums tabular-nums; }}
.sec-title {{ font-size:12.5pt; font-weight:700; letter-spacing:-0.01em; color:{MIDNIGHT}; }}
.sub {{ font-size:{b}pt; font-weight:700; color:{ACCENT}; margin:{pg}pt 0 2pt; }}
p {{ font-size:{b}pt; line-height:{lh}; margin:0 0 {pg}pt; max-width:6.6in; }}
ul {{ margin:0 0 {pg}pt; padding-left:14px; max-width:6.6in; }}
li {{ font-size:{b}pt; line-height:{lh}; margin:{max(pg-3,1)}pt 0; }}
li > strong:first-child {{ font-weight:700; }} strong {{ font-weight:600; }} em {{ font-style:italic; font-weight:400; }}
.cite {{ color:{ACCENT}; font-size:0.8em; font-weight:500; font-variant-numeric:tabular-nums; }}
table {{ border-collapse:collapse; width:100%; margin:0 0 {pg}pt; table-layout:auto; break-inside:auto; }}
tr {{ break-inside:avoid; }} thead {{ display:table-header-group; }}
th {{ font-size:{b-1.5}pt; font-weight:500; text-transform:uppercase; letter-spacing:0.04em; color:{ACCENT}; text-align:left; padding:3px 6px 3px 0; border-bottom:1.25px solid {ACCENT}; }}
td {{ font-size:{b-0.5}pt; line-height:{lh}; padding:3px 6px 3px 0; border-bottom:0.5px solid {HAIR}; vertical-align:top; overflow-wrap:anywhere; }}
tbody tr:last-child td {{ border-bottom:1.25px solid {INK}; }}
.pagebreak {{ break-before:page; }}
.pagebreak .masthead-alt {{ padding-top:0; }}
"""


def build_doc(title, subtitle, secs_html, rung, footer, script_html=None, script_title=None, script_sub=None):
    logo = "data:image/png;base64," + (ASSETS / "talyx-logo-navy-base64.txt").read_text().strip()
    mh = lambda t, s: (f'<div class="masthead-alt"><img class="mh-alt-logo" src="{logo}"/><div class="mh-alt-titles">'
                       f'<div class="mh-alt-title">{inl(t)}</div>' + (f'<div class="mh-alt-role">{inl(s)}</div>' if s else "") + "</div></div>")
    body = mh(title, subtitle) + "".join(secs_html)
    if script_html:
        body += '<div class="pagebreak">' + mh(script_title or "Meeting script", script_sub or subtitle) + "".join(script_html) + "</div>"
    return (f'<!doctype html><html lang="en"><head><meta charset="utf-8"><title>{html.escape(title)}</title>'
            f"<style>{css(rung, footer)}</style></head><body><div class=\"page-content\">{body}</div></body></html>")


# ---------------------------------------------------------------- render --------------------------------
def page_count(path):
    try:
        import fitz
        with fitz.open(str(path)) as d:
            return d.page_count
    except ImportError:
        from pypdf import PdfReader
        return len(PdfReader(str(path)).pages)


def render_html(doc, out_path):
    from playwright.sync_api import sync_playwright
    with tempfile.NamedTemporaryFile(suffix=".html", delete=False, mode="w", encoding="utf-8") as tf:
        tf.write(doc); tmp = tf.name
    try:
        with sync_playwright() as p:
            br = p.chromium.launch()
            try:
                pg = br.new_page()
                pg.goto(pathlib.Path(tmp).as_uri())
                pg.evaluate("document.fonts.ready")
                pg.pdf(path=str(out_path), print_background=True, prefer_css_page_size=True, outline=True)
            finally:
                br.close()
    finally:
        pathlib.Path(tmp).unlink(missing_ok=True)
    return page_count(out_path)


def word_report(md):
    _, secs = sections(md)
    return sorted(((len(re.sub(r"<[^>]+>", " ", h).split()), t or "(preamble)") for _, t, h in secs), reverse=True)[:4]


def run(a):
    brief_md = pathlib.Path(a.brief or a.input).read_text()
    title, brief_secs = sections(brief_md)
    title = a.title or title or pathlib.Path(a.brief or a.input).stem
    brief_html = [sec_html(n, t, h) for n, t, h in brief_secs]
    script_html = script_title = None
    if a.script:
        script_md = pathlib.Path(a.script).read_text()
        st, ssecs = sections(script_md)
        script_title = st or "Meeting script"
        script_html = [sec_html(n, t, h) for n, t, h in ssecs]
    out = pathlib.Path(a.out).expanduser()
    out.parent.mkdir(parents=True, exist_ok=True)
    rungs = LADDER if a.max_pages else LADDER[:1]
    last = None
    for rung in rungs:
        doc = build_doc(title, a.subtitle, brief_html, rung, a.footer, script_html, script_title, a.subtitle)
        pages = render_html(doc, out)
        last = (rung["name"], pages)
        if not a.max_pages or pages <= a.max_pages:
            print(json.dumps(dict(ok=True, pages=pages, rung=rung["name"], path=str(out), max_pages=a.max_pages)))
            return 0
    longest = word_report(brief_md) + (word_report(pathlib.Path(a.script).read_text()) if a.script else [])
    print(json.dumps(dict(ok=False, pages=last[1], rung=last[0], max_pages=a.max_pages, path=str(out),
                          reason="overflow at tightest rung -- cut these sections", longest_sections=longest)))
    return 2


def setup():
    cmds = [[sys.executable, "-m", "pip", "install", "-q", "playwright", "pypdf"], [sys.executable, "-m", "playwright", "install", "chromium"]]
    for c in cmds:
        print("$", " ".join(c)); subprocess.run(c, check=True)
    print("setup OK")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--input"); ap.add_argument("--brief"); ap.add_argument("--script")
    ap.add_argument("--out"); ap.add_argument("--title"); ap.add_argument("--subtitle", default="")
    ap.add_argument("--footer", default="Talyx AI · talyx.ai"); ap.add_argument("--max-pages", type=int)
    ap.add_argument("--setup", action="store_true")
    a = ap.parse_args()
    if a.setup:
        return setup()
    if not (a.input or a.brief) or not a.out:
        ap.error("--input (or --brief [--script]) and --out are required")
    return run(a)


if __name__ == "__main__":
    sys.exit(main() or 0)
