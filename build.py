#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把 README.md 编译成可直接部署的静态站点（输出到 site/）。

环境变量（Cloudflare Pages 里在「设置 → 环境变量」配置，本地也可临时设置）：
    SITE_URL            站点根地址，用于生成 sitemap.xml，例如 https://pcpcpc.ccwu.cc
    CF_ANALYTICS_TOKEN  Cloudflare Web Analytics 的 token，填了才会注入统计脚本

本地构建：        python build.py
Cloudflare 构建：  构建命令 python3 build.py，输出目录 site
"""
import datetime
import html
import os
import re
import unicodedata

ROOT = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(ROOT, "README.md")
OUT_DIR = os.path.join(ROOT, "site")

SITE_TITLE = "2026 低价机场推荐与对比指南"
SITE_DESC = "2026 低价机场推荐与对比：套餐价格、流量额度、线路类型与注意事项，含 Clash / V2Ray / 小火箭订阅导入教程。"
SITE_URL = os.environ.get("SITE_URL", "https://pcpcpc.ccwu.cc").rstrip("/")
CF_TOKEN = os.environ.get("CF_ANALYTICS_TOKEN", "").strip()
TODAY = datetime.date.today().isoformat()


def slug(text: str) -> str:
    out = []
    for ch in text.strip().lower():
        cat = unicodedata.category(ch)
        if ch in "-_ " or cat[0] in "LNM" or ch.isdigit():
            out.append(ch)
    return re.sub(r"\s+", "-", "".join(out)).strip()


def _link(m):
    text, url = m.group(1), m.group(2)
    if url.startswith("http"):
        return '<a href="%s" target="_blank" rel="noopener noreferrer">%s</a>' % (url, text)
    return '<a href="%s" rel="noopener">%s</a>' % (url, text)


def inline(text: str) -> str:
    text = html.escape(text, quote=False)
    text = re.sub(r"`([^`]+)`", r"<code>\1</code>", text)
    text = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", text)
    text = re.sub(r"\[([^\]]+)\]\(([^)\s]+)\)", _link, text)
    return text


def render_table(rows):
    head, body = rows[0], rows[2:]
    cells = [c.strip() for c in head.strip("|").split("|")]
    out = ['<div class="table-wrap"><table>', "<thead><tr>"]
    out += ["<th>%s</th>" % inline(c) for c in cells]
    out.append("</tr></thead><tbody>")
    for row in body:
        cs = [c.strip() for c in row.strip("|").split("|")]
        out.append("<tr>" + "".join("<td>%s</td>" % inline(c) for c in cs) + "</tr>")
    out.append("</tbody></table></div>")
    return "\n".join(out)


def render_quote(lines):
    alert = None
    m = re.match(r"\[!(TIP|NOTE|IMPORTANT|WARNING|CAUTION)\]", lines[0].strip()) if lines else None
    if m:
        alert = m.group(1).lower()
        lines = lines[1:]
    items, paras = [], []
    for line in lines:
        if line.startswith("- "):
            items.append("<li>%s</li>" % inline(line[2:]))
        elif line:
            paras.append("<p>%s</p>" % inline(line))
    inner = paras + (["<ul>%s</ul>" % "".join(items)] if items else [])
    label = {"tip": "提示", "note": "说明", "important": "重要",
             "warning": "注意", "caution": "警告"}.get(alert, "")
    head = '<div class="alert-title">%s</div>' % label if label else ""
    cls = "blockquote alert-%s" % alert if alert else "blockquote"
    return '<div class="%s">%s%s</div>' % (cls, head, "".join(inner))


def heading(level, text):
    anchor = slug(text)
    link = ' <a class="anchor" href="#%s" aria-hidden="true">#</a>' % anchor
    cls = ' class="hero-title"' if level == 1 else ""
    return '<h%d id="%s"%s>%s%s</h%d>' % (level, anchor, cls, inline(text), link, level)


def convert(md: str):
    lines = md.split("\n")
    out, toc = [], []
    i = 0
    para = []

    def flush():
        if para:
            out.append("<p>%s</p>" % inline(" ".join(para)))
            para.clear()

    while i < len(lines):
        s = lines[i].strip()

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
            level, text = len(m.group(1)), m.group(2).strip()
            out.append(heading(level, text))
            if level == 2 and text != "目录":
                toc.append((slug(text), re.sub(r"\*\*", "", text)))
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
    return "\n".join(out), toc


def add_section_toc(body: str) -> str:
    parts = re.split(r'(?=<h2 id=")', body)
    out = []
    for part in parts:
        m = re.match(r'<h2 id="[^"]+"[^>]*>.*?</h2>', part, re.S)
        if not m:
            out.append(part)
            continue
        head, rest = part[:m.end()], part[m.end():]
        subs = re.findall(r'<h3 id="([^"]+)"[^>]*>(.*?)</h3>', rest, re.S)
        subs = [(a, re.sub(r"<[^>]+>", "", t).strip()) for a, t in subs]
        if len(subs) >= 2:
            chips = "".join('<a href="#%s">%s</a>' % (a, t) for a, t in subs)
            rest = '<div class="section-toc">%s</div>' % chips + rest
        out.append(head + rest)
    return "".join(out)


CSS = """
:root{
  --bg:#eef2f9; --bg-2:#e4ebf6;
  --fg:#0f1729; --muted:#5b6b82;
  --panel:rgba(255,255,255,.72); --panel-solid:#f8fafd;
  --line:rgba(15,23,41,.10); --line-strong:rgba(15,23,41,.16);
  --accent:#2f6bff; --accent-2:#0fb6c9; --accent-soft:rgba(47,107,255,.09);
  --tip:#12924f; --tip-bg:rgba(18,146,79,.08); --tip-line:rgba(18,146,79,.35);
  --note:#2f6bff; --note-bg:rgba(47,107,255,.07); --note-line:rgba(47,107,255,.32);
  --warn:#b7791f; --warn-bg:rgba(183,121,31,.09); --warn-line:rgba(183,121,31,.35);
  --radius:12px;
  --shadow:0 1px 2px rgba(15,23,41,.04),0 8px 24px -12px rgba(15,23,41,.18);
}
html[data-theme="dark"]{
  --bg:#060a13; --bg-2:#0a1120;
  --fg:#e7eefc; --muted:#8fa1bb;
  --panel:rgba(19,26,40,.66); --panel-solid:#0e1522;
  --line:rgba(160,190,255,.14); --line-strong:rgba(160,190,255,.22);
  --accent:#5b9cff; --accent-2:#2fd8e8; --accent-soft:rgba(91,156,255,.14);
  --tip:#39d98a; --tip-bg:rgba(57,217,138,.09); --tip-line:rgba(57,217,138,.34);
  --note:#5b9cff; --note-bg:rgba(91,156,255,.10); --note-line:rgba(91,156,255,.34);
  --warn:#e0a83c; --warn-bg:rgba(224,168,60,.10); --warn-line:rgba(224,168,60,.34);
  --shadow:0 1px 2px rgba(0,0,0,.35),0 10px 30px -14px rgba(0,0,0,.6);
}
*{box-sizing:border-box}
html{scroll-behavior:smooth;scroll-padding-top:80px}
body{
  margin:0;color:var(--fg);
  background:
    radial-gradient(1100px 520px at 82% -12%, rgba(47,107,255,.16), transparent 62%),
    radial-gradient(900px 480px at 8% 4%, rgba(15,182,201,.13), transparent 60%),
    linear-gradient(180deg,var(--bg),var(--bg-2));
  background-attachment:fixed;
  font:16.5px/1.8 -apple-system,BlinkMacSystemFont,"Segoe UI","PingFang SC","Hiragino Sans GB","Microsoft YaHei",sans-serif;
  -webkit-font-smoothing:antialiased;
}
/* 细网格底纹，营造科技感 */
body::before{
  content:"";position:fixed;inset:0;pointer-events:none;z-index:0;
  background-image:
    linear-gradient(to right,rgba(47,107,255,.06) 1px,transparent 1px),
    linear-gradient(to bottom,rgba(47,107,255,.06) 1px,transparent 1px);
  background-size:44px 44px;
  -webkit-mask-image:radial-gradient(circle at 50% 0%,#000 0%,transparent 72%);
          mask-image:radial-gradient(circle at 50% 0%,#000 0%,transparent 72%);
}
html[data-theme="dark"] body::before{
  background-image:
    linear-gradient(to right,rgba(120,170,255,.09) 1px,transparent 1px),
    linear-gradient(to bottom,rgba(120,170,255,.09) 1px,transparent 1px);
}

#progress{position:fixed;top:0;left:0;height:3px;width:0;z-index:60;
  background:linear-gradient(90deg,var(--accent),var(--accent-2));
  box-shadow:0 0 12px rgba(47,107,255,.55);transition:width .1s linear}

/* 全宽布局：侧栏紧贴左侧，正文在右侧居中 */
.layout{position:relative;z-index:1;display:grid;
  grid-template-columns:208px minmax(0,1fr);align-items:start}
main{min-width:0;max-width:820px;margin:0 auto;padding:34px 30px 100px}

/* 左侧目录：贴左、通栏高、文字完整显示 */
.toc{position:sticky;top:0;height:100vh;max-height:100vh;overflow:auto;
  padding:24px 14px 28px 18px;font-size:13px;line-height:1.45;
  border-right:1px solid var(--line);
  background:linear-gradient(180deg,rgba(47,107,255,.07),rgba(47,107,255,0) 46%);
  -webkit-backdrop-filter:blur(6px);backdrop-filter:blur(6px);scrollbar-width:thin}
html[data-theme="dark"] .toc{
  background:linear-gradient(180deg,rgba(91,156,255,.10),rgba(91,156,255,0) 46%)}
.toc h4{margin:0 0 10px;padding-left:6px;font-size:10.5px;letter-spacing:.14em;color:var(--muted);
  text-transform:uppercase;font-weight:700}
.toc a{display:block;padding:5px 8px;margin:1px 0;border-radius:7px;color:var(--muted);
  text-decoration:none;border-left:2px solid transparent;white-space:normal;word-break:break-word;
  transition:color .15s,background .15s,border-color .15s}
.toc a:hover{color:var(--fg);background:var(--accent-soft)}
.toc a.active{color:var(--accent);background:var(--accent-soft);border-left-color:var(--accent);font-weight:600}

.hero-title{font-size:2.05em;line-height:1.3;margin:0 0 .5em;letter-spacing:-.015em;
  background:linear-gradient(120deg,var(--fg) 18%,var(--accent) 62%,var(--accent-2) 96%);
  -webkit-background-clip:text;background-clip:text;color:transparent}
.chips{display:flex;flex-wrap:wrap;gap:8px;margin:0 0 22px}
.chip{font-size:.82em;padding:5px 13px;border-radius:999px;color:var(--muted);text-decoration:none;
  border:1px solid var(--line-strong);background:var(--panel);backdrop-filter:blur(8px);
  transition:.18s}
.chip:hover{color:var(--accent);border-color:var(--accent);transform:translateY(-1px);
  box-shadow:0 6px 18px -8px rgba(47,107,255,.55)}

h1,h2,h3,h4{line-height:1.36;font-weight:700}
h2{position:relative;font-size:1.36em;margin:2.3em 0 .75em;padding-bottom:.42em;
  border-bottom:1px solid var(--line);border-radius:4px;transition:background .35s}
h2::after{content:"";position:absolute;left:0;bottom:-1px;width:52px;height:2px;border-radius:2px;
  background:linear-gradient(90deg,var(--accent),var(--accent-2))}
h3{font-size:1.06em;margin:1.85em 0 .5em;padding-left:10px;border-left:3px solid var(--accent);
  border-radius:2px;transition:background .35s}
h2:target,h3:target{background:var(--accent-soft)}
.anchor{opacity:0;visibility:hidden;margin-left:.35em;font-size:.72em;color:var(--muted);
  font-weight:400;text-decoration:none;user-select:none;transition:opacity .15s}
@media (hover:hover){
  h2:hover .anchor,h3:hover .anchor{opacity:.6;visibility:visible}
  .anchor:hover{opacity:1;color:var(--accent)}
}
.section-toc{display:flex;flex-wrap:wrap;gap:7px;margin:.1em 0 1.3em}
.section-toc a{font-size:.8em;padding:4px 11px;border-radius:999px;color:var(--muted);text-decoration:none;
  border:1px solid var(--line);background:var(--panel);transition:.16s}
.section-toc a:hover{color:var(--accent);border-color:var(--accent);background:var(--accent-soft)}

p{margin:.8em 0}
a{color:var(--accent);text-decoration:none}
a:hover{text-decoration:underline;text-underline-offset:3px}
strong{font-weight:650}
code{background:var(--accent-soft);padding:.16em .4em;border-radius:6px;font-size:.88em;
  font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace}
pre{background:var(--panel-solid);padding:16px;border-radius:var(--radius);overflow:auto;
  border:1px solid var(--line);box-shadow:var(--shadow)}
hr{border:0;height:1px;margin:2.6em 0;
  background:linear-gradient(90deg,transparent,var(--line-strong),transparent)}
ul{padding-left:1.3em;margin:.7em 0}
li{margin:.3em 0}
li::marker{color:var(--accent)}

.table-wrap{margin:1.1em 0;border:1px solid var(--line-strong);border-radius:var(--radius);
  overflow:auto;-webkit-overflow-scrolling:touch;background:var(--panel);
  backdrop-filter:blur(10px);box-shadow:var(--shadow)}
table{border-collapse:collapse;width:100%;font-size:.9em;background:transparent}
th,td{border-bottom:1px solid var(--line);border-right:1px solid var(--line);padding:10px 13px;
  text-align:left;vertical-align:top}
th:last-child,td:last-child{border-right:0}
tr:last-child td{border-bottom:0}
th{background:var(--accent-soft);font-weight:700;white-space:nowrap;font-size:.95em;letter-spacing:.02em}
tbody tr{transition:background .15s}
tbody tr:nth-child(even){background:rgba(47,107,255,.035)}
tbody tr:hover{background:var(--accent-soft)}

.blockquote{margin:1.2em 0;padding:12px 16px;border-radius:0 var(--radius) var(--radius) 0;
  border-left:3px solid var(--muted);background:var(--panel);backdrop-filter:blur(8px)}
.blockquote p{margin:.4em 0}
.alert-title{font-weight:700;font-size:.78em;letter-spacing:.12em;margin-bottom:.35em}
.alert-tip{border-color:var(--tip-line);background:var(--tip-bg)}
.alert-tip .alert-title{color:var(--tip)}
.alert-note,.alert-important{border-color:var(--note-line);background:var(--note-bg)}
.alert-note .alert-title,.alert-important .alert-title{color:var(--note)}
.alert-warning,.alert-caution{border-color:var(--warn-line);background:var(--warn-bg)}
.alert-warning .alert-title,.alert-caution .alert-title{color:var(--warn)}

.fab{position:fixed;right:20px;bottom:22px;display:flex;flex-direction:column;gap:10px;z-index:50}
.fab button{width:42px;height:42px;border-radius:50%;cursor:pointer;font-size:17px;
  color:var(--fg);border:1px solid var(--line-strong);background:var(--panel);
  backdrop-filter:blur(10px);box-shadow:var(--shadow);transition:.18s}
.fab button:hover{transform:translateY(-2px);border-color:var(--accent);color:var(--accent)}
#toTop{opacity:0;pointer-events:none}
#toTop.show{opacity:1;pointer-events:auto}

footer{margin-top:3.4em;padding-top:18px;border-top:1px solid var(--line);
  color:var(--muted);font-size:.83em}

@media (max-width:960px){
  .layout{grid-template-columns:1fr}
  .toc{position:static;height:auto;max-height:none;border-right:0;border-bottom:1px solid var(--line);
    padding:12px 16px;margin-bottom:6px;background:none;
    -webkit-backdrop-filter:none;backdrop-filter:none}
  .toc h4{display:none}
  .toc a{display:inline-block;margin:2px 4px 2px 0;border-left:0;border:1px solid var(--line);
    white-space:normal;overflow:visible;text-overflow:clip}
  main{max-width:none;padding:22px 16px 96px}
  .hero-title{font-size:1.55em}
  h2{font-size:1.22em}
  th,td{padding:8px 10px;font-size:.94em}
}
@media print{.toc,.fab,#progress,body::before{display:none}.layout{display:block}}
"""

JS = """
(function(){
  var root=document.documentElement, KEY='doc-theme';
  var saved=localStorage.getItem(KEY);
  if(saved){root.setAttribute('data-theme',saved);}
  else if(window.matchMedia('(prefers-color-scheme: dark)').matches){root.setAttribute('data-theme','dark');}
  var btn=document.getElementById('theme');
  function paint(){btn.textContent=root.getAttribute('data-theme')==='dark'?'☀️':'🌙';}
  paint();
  btn.addEventListener('click',function(){
    var next=root.getAttribute('data-theme')==='dark'?'light':'dark';
    root.setAttribute('data-theme',next);localStorage.setItem(KEY,next);paint();
  });

  var bar=document.getElementById('progress'), top=document.getElementById('toTop');
  function onScroll(){
    var h=document.documentElement, max=h.scrollHeight-h.clientHeight;
    bar.style.width=(max>0?h.scrollTop/max*100:0)+'%';
    top.classList.toggle('show',h.scrollTop>600);
  }
  document.addEventListener('scroll',onScroll,{passive:true});onScroll();
  top.addEventListener('click',function(){window.scrollTo({top:0,behavior:'smooth'});});

  var links=[].slice.call(document.querySelectorAll('.toc a'));
  var heads=links.map(function(a){return document.getElementById(a.getAttribute('href').slice(1));});
  function setActive(){
    var idx=0;
    for(var i=0;i<heads.length;i++){
      if(heads[i] && heads[i].getBoundingClientRect().top<=130) idx=i;
    }
    links.forEach(function(a,i){a.classList.toggle('active',i===idx);});
  }
  document.addEventListener('scroll',setActive,{passive:true});setActive();
})();
"""

ANALYTICS = """<script defer src="https://static.cloudflareinsights.com/beacon.min.js" data-cf-beacon='{{"token": "{token}"}}'></script>"""

PAGE = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{title}</title>
<meta name="description" content="{desc}">
<meta name="theme-color" content="#2f6bff">
<link rel="canonical" href="{url}/">
<meta property="og:title" content="{title}">
<meta property="og:description" content="{desc}">
<meta property="og:type" content="article">
<meta property="og:url" content="{url}/">
<meta name="twitter:card" content="summary">
<link rel="alternate" type="text/markdown" href="README.md">
<style>{css}</style>
{analytics}
</head>
<body>
<div id="progress"></div>
<div class="layout">
  <aside class="toc">
    <h4>目录</h4>
    {toc}
  </aside>
  <main>
    {body}
    <footer>内容整理自各机场官网公开页面，价格与套餐以官网为准。</footer>
  </main>
</div>
<div class="fab">
  <button id="toTop" title="回到顶部" aria-label="回到顶部">↑</button>
  <button id="theme" title="切换深色模式" aria-label="切换深色模式">🌙</button>
</div>
<script>{js}</script>
</body>
</html>
"""

NOT_FOUND = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>页面不存在 · __TITLE__</title>
<meta name="robots" content="noindex">
<style>
body{margin:0;min-height:100vh;display:flex;align-items:center;justify-content:center;
  color:#0f1729;background:
    radial-gradient(900px 420px at 78% -10%, rgba(47,107,255,.18), transparent 60%),
    radial-gradient(700px 380px at 10% 6%, rgba(15,182,201,.14), transparent 58%),
    linear-gradient(180deg,#eef2f9,#e4ebf6);
  font:16.5px/1.8 -apple-system,BlinkMacSystemFont,"PingFang SC","Microsoft YaHei",sans-serif}
@media (prefers-color-scheme: dark){
  body{color:#e7eefc;background:
    radial-gradient(900px 420px at 78% -10%, rgba(91,156,255,.18), transparent 60%),
    radial-gradient(700px 380px at 10% 6%, rgba(47,216,232,.12), transparent 58%),
    linear-gradient(180deg,#060a13,#0a1120)}
}
.box{max-width:520px;padding:34px;text-align:center;border-radius:16px;
  border:1px solid rgba(127,150,190,.25);background:rgba(255,255,255,.6);
  -webkit-backdrop-filter:blur(12px);backdrop-filter:blur(12px);
  box-shadow:0 18px 42px -22px rgba(15,23,41,.45)}
@media (prefers-color-scheme: dark){.box{background:rgba(19,26,40,.62)}}
h1{font-size:1.5em;margin:0 0 .45em;
  background:linear-gradient(120deg,#0f1729,#2f6bff 70%,#0fb6c9);
  -webkit-background-clip:text;background-clip:text;color:transparent}
@media (prefers-color-scheme: dark){
  h1{background:linear-gradient(120deg,#e7eefc,#5b9cff 70%,#2fd8e8);
     -webkit-background-clip:text;background-clip:text;color:transparent}
}
p{color:#5b6b82;margin:.6em 0 1.7em}
@media (prefers-color-scheme: dark){p{color:#8fa1bb}}
a{display:inline-block;padding:11px 24px;border-radius:999px;color:#fff;text-decoration:none;
  background:linear-gradient(120deg,#2f6bff,#0fb6c9);box-shadow:0 10px 24px -12px rgba(47,107,255,.95)}
a:hover{filter:brightness(1.06)}
</style>
</head>
<body>
<div class="box">
  <h1>404 · 这个链接可能已经失效了</h1>
  <p>页面不存在，或者作者的链接地址调整过了。</p>
  <a href="/">回到首页看最新内容</a>
</div>
</body>
</html>
"""


def main():
    with open(SRC, encoding="utf-8") as f:
        md = f.read()
    body, heads = convert(md)
    body = add_section_toc(body)

    chips = "".join(
        '<a class="chip" href="#%s">%s</a>' % (a, t)
        for a, t in heads
        if t in ("整体对比（价格、流量与线路）", "机场怎么买怎么用（注册到导入客户端）", "常见搜索问题")
    )
    if chips:
        body = body.replace("</h1>", '</h1>\n<div class="chips">%s</div>' % chips, 1)

    toc_html = "\n".join('<a href="#%s" title="%s">%s</a>' % (a, t, t) for a, t in heads)
    analytics = ANALYTICS.format(token=CF_TOKEN) if CF_TOKEN else ""

    os.makedirs(OUT_DIR, exist_ok=True)
    with open(os.path.join(OUT_DIR, "index.html"), "w", encoding="utf-8") as f:
        f.write(PAGE.format(title=SITE_TITLE, desc=SITE_DESC, url=SITE_URL,
                            css=CSS, js=JS, toc=toc_html, body=body, analytics=analytics))
    with open(os.path.join(OUT_DIR, "404.html"), "w", encoding="utf-8") as f:
        f.write(NOT_FOUND.replace("__TITLE__", SITE_TITLE))
    with open(os.path.join(OUT_DIR, "sitemap.xml"), "w", encoding="utf-8") as f:
        f.write('<?xml version="1.0" encoding="UTF-8"?>\n'
                '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
                '  <url>\n    <loc>%s/</loc>\n    <lastmod>%s</lastmod>\n'
                '    <changefreq>weekly</changefreq>\n    <priority>1.0</priority>\n'
                '  </url>\n</urlset>\n' % (SITE_URL, TODAY))
    with open(os.path.join(OUT_DIR, "robots.txt"), "w", encoding="utf-8") as f:
        f.write("User-agent: *\nAllow: /\n\nSitemap: %s/sitemap.xml\n" % SITE_URL)
    with open(os.path.join(OUT_DIR, "README.md"), "w", encoding="utf-8") as f:
        f.write(md)
    with open(os.path.join(OUT_DIR, "_headers"), "w", encoding="utf-8") as f:
        f.write("/*\n  X-Content-Type-Options: nosniff\n"
                "  Referrer-Policy: strict-origin-when-cross-origin\n"
                "  Cache-Control: public, max-age=600\n")
    print("构建完成：site/（%d 个章节，域名 %s）" % (len(heads), SITE_URL))


if __name__ == "__main__":
    main()
