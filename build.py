#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把 README.md 编译成可直接部署的静态页面（site/index.html）。

用法：
    python build.py

生成的 site/ 目录可以直接拖到 Cloudflare Pages 的「Upload assets」，
或者在 Pages 项目里把输出目录设为 site。
"""
import html
import os
import re
import unicodedata

ROOT = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(ROOT, "README.md")
OUT_DIR = os.path.join(ROOT, "site")
TITLE = "2026 低价机场推荐与对比指南"


def slug(text: str) -> str:
    """近似 GitHub 的标题锚点规则：小写、去标点、空格转连字符。"""
    out = []
    for ch in text.strip().lower():
        cat = unicodedata.category(ch)
        if ch in "-_ " or cat[0] in "LNM" or ch.isdigit():
            out.append(ch)
    return re.sub(r"\s+", "-", "".join(out)).strip()


def inline(text: str) -> str:
    text = html.escape(text, quote=False)
    text = re.sub(r"`([^`]+)`", r"<code>\1</code>", text)
    text = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", text)
    text = re.sub(
        r"\[([^\]]+)\]\(([^)\s]+)\)",
        lambda m: '<a href="%s" rel="noopener">%s</a>' % (m.group(2), m.group(1)),
        text,
    )
    return text


def render_table(rows):
    head, body = rows[0], rows[2:]
    cells = [c.strip() for c in head.strip("|").split("|")]
    out = ["<div class=\"table-wrap\"><table>", "<thead><tr>"]
    out += ["<th>%s</th>" % inline(c) for c in cells]
    out.append("</tr></thead><tbody>")
    for row in body:
        cs = [c.strip() for c in row.strip("|").split("|")]
        out.append("<tr>" + "".join("<td>%s</td>" % inline(c) for c in cs) + "</tr>")
    out.append("</tbody></table></div>")
    return "\n".join(out)


def render_quote(lines):
    alert = None
    first = lines[0].strip()
    m = re.match(r"\[!(TIP|NOTE|IMPORTANT|WARNING|CAUTION)\]", first)
    if m:
        alert = m.group(1).lower()
        lines = lines[1:]
    body = []
    for raw in lines:
        line = raw
        if line.startswith("- "):
            body.append("<li>%s</li>" % inline(line[2:]))
        elif line:
            body.append("<p>%s</p>" % inline(line))
    inner = []
    if "<li>" in "".join(body):
        inner.append("<ul>" + "".join(x for x in body if x.startswith("<li>")) + "</ul>")
        rest = [x for x in body if not x.startswith("<li>")]
        inner = rest + inner
    else:
        inner = body
    cls = "blockquote alert-%s" % alert if alert else "blockquote"
    label = {
        "tip": "提示",
        "note": "说明",
        "important": "重要",
        "warning": "注意",
        "caution": "警告",
    }.get(alert, "")
    head = '<div class="alert-title">%s</div>' % label if label else ""
    return '<div class="%s">%s%s</div>' % (cls, head, "".join(inner))


def convert(md: str) -> str:
    lines = md.split("\n")
    out, i = [], 0
    para = []

    def flush():
        if para:
            out.append("<p>%s</p>" % inline(" ".join(para)))
            para.clear()

    while i < len(lines):
        line = lines[i]
        s = line.strip()

        if not s:
            flush()
            i += 1
            continue

        if s.startswith("```"):
            flush()
            i += 1
            buf = []
            while i < len(lines) and not lines[i].strip().startswith("```"):
                buf.append(html.escape(lines[i]))
                i += 1
            i += 1
            out.append("<pre><code>%s</code></pre>" % "\n".join(buf))
            continue

        m = re.match(r"^(#{1,6})\s+(.*)$", s)
        if m:
            flush()
            level = len(m.group(1))
            text = m.group(2).strip()
            anchor = slug(text)
            out.append('<h%d id="%s">%s</h%d>' % (level, anchor, inline(text), level))
            i += 1
            continue

        if re.match(r"^(-{3,}|\*{3,})$", s):
            flush()
            out.append("<hr>")
            i += 1
            continue

        if s.startswith("|") and i + 1 < len(lines) and re.match(r"^\|[\s\-:|]+\|$", lines[i + 1].strip()):
            flush()
            rows = []
            while i < len(lines) and lines[i].strip().startswith("|"):
                rows.append(lines[i].strip())
                i += 1
            out.append(render_table(rows))
            continue

        if s.startswith(">"):
            flush()
            buf = []
            while i < len(lines) and lines[i].strip().startswith(">"):
                buf.append(lines[i].strip()[1:].strip())
                i += 1
            out.append(render_quote(buf))
            continue

        if s.startswith("- "):
            flush()
            items = []
            while i < len(lines) and lines[i].strip().startswith("- "):
                items.append("<li>%s</li>" % inline(lines[i].strip()[2:]))
                i += 1
            out.append("<ul>%s</ul>" % "".join(items))
            continue

        para.append(s)
        i += 1

    flush()
    return "\n".join(out)


CSS = """
:root { --fg:#1f2328; --muted:#59636e; --bg:#ffffff; --line:#d1d9e0; --accent:#0969da;
        --tip:#1a7f37; --tipbg:#f0fff4; --note:#0969da; --notebg:#f1f7ff;
        --warn:#9a6700; --warnbg:#fff8e6; }
@media (prefers-color-scheme: dark) {
  :root { --fg:#e6edf3; --muted:#9198a1; --bg:#0d1117; --line:#3d444d; --accent:#4493f8;
          --tip:#3fb950; --tipbg:#12261a; --note:#4493f8; --notebg:#101b2d;
          --warn:#d29922; --warnbg:#2a1f0d; }
}
* { box-sizing: border-box; }
body { margin:0; background:var(--bg); color:var(--fg);
  font:16px/1.75 -apple-system,BlinkMacSystemFont,"Segoe UI","PingFang SC","Hiragino Sans GB","Microsoft YaHei",sans-serif; }
main { max-width:840px; margin:0 auto; padding:40px 20px 80px; }
h1 { font-size:1.9em; line-height:1.3; margin:0 0 .6em; }
h2 { font-size:1.4em; margin:2em 0 .6em; padding-bottom:.3em; border-bottom:1px solid var(--line); }
h3 { font-size:1.1em; margin:1.6em 0 .5em; }
p { margin:.7em 0; }
a { color:var(--accent); text-decoration:none; }
a:hover { text-decoration:underline; }
code { background:rgba(127,127,127,.15); padding:.15em .35em; border-radius:4px; font-size:.9em; }
pre { background:rgba(127,127,127,.12); padding:14px; border-radius:8px; overflow:auto; }
hr { border:0; border-top:1px solid var(--line); margin:2.2em 0; }
ul { padding-left:1.4em; }
li { margin:.25em 0; }
.table-wrap { overflow-x:auto; margin:1em 0; }
table { border-collapse:collapse; width:100%; font-size:.92em; }
th,td { border:1px solid var(--line); padding:8px 10px; text-align:left; vertical-align:top; }
th { background:rgba(127,127,127,.1); white-space:nowrap; }
.blockquote { border-left:4px solid var(--muted); background:rgba(127,127,127,.07);
  padding:10px 14px; margin:1.1em 0; border-radius:0 6px 6px 0; }
.blockquote p { margin:.35em 0; }
.alert-title { font-weight:700; font-size:.85em; letter-spacing:.04em; margin-bottom:.2em; }
.alert-tip { border-color:var(--tip); background:var(--tipbg); }
.alert-tip .alert-title { color:var(--tip); }
.alert-note, .alert-important { border-color:var(--note); background:var(--notebg); }
.alert-note .alert-title, .alert-important .alert-title { color:var(--note); }
.alert-warning, .alert-caution { border-color:var(--warn); background:var(--warnbg); }
.alert-warning .alert-title, .alert-caution .alert-title { color:var(--warn); }
footer { margin-top:3em; color:var(--muted); font-size:.85em; text-align:center; }
"""

PAGE = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<meta name="description" content="2026 低价机场推荐与对比：套餐价格、流量额度、线路类型与注意事项，含 Clash / V2Ray / 小火箭订阅导入教程。">
<meta property="og:title" content="{title}">
<meta property="og:type" content="article">
<link rel="alternate" type="text/markdown" href="README.md">
<style>{css}</style>
</head>
<body>
<main>
{body}
<footer>内容整理自各机场官网公开页面，价格与套餐以官网为准。</footer>
</main>
</body>
</html>
"""


def main():
    with open(SRC, encoding="utf-8") as f:
        md = f.read()
    body = convert(md)
    os.makedirs(OUT_DIR, exist_ok=True)
    with open(os.path.join(OUT_DIR, "index.html"), "w", encoding="utf-8") as f:
        f.write(PAGE.format(title=TITLE, css=CSS, body=body))
    with open(os.path.join(OUT_DIR, "robots.txt"), "w", encoding="utf-8") as f:
        f.write("User-agent: *\nAllow: /\n")
    with open(os.path.join(OUT_DIR, "README.md"), "w", encoding="utf-8") as f:
        f.write(md)
    print("已生成 site/index.html，可直接部署到 Cloudflare Pages")


if __name__ == "__main__":
    main()
