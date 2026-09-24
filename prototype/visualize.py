"""路由观测可视化——把盘上的运行状态渲染成一个自包含的 HTML 页。

守住 README 的红线：这不是「态势感知大屏」，而是一页「路由决策观测」，
只突出降噪 / 越用越准 / 风险档位三件事——降噪率多少、记住了什么、档位怎么拨。
读 last_run.json + memory.jsonl + 免疫记忆文件，生成 report.html（本地浏览器直接打开），
另写 report.fragment.html 供发布用。零依赖、零服务。

跑法：
    python3 main.py          # 先产生一次运行 → data/last_run.json
    python3 visualize.py     # 生成 report.html
"""
from __future__ import annotations

import html
import json
import math
import os

DATA = os.path.join(os.path.dirname(__file__), "data")
LAST_RUN = os.path.join(DATA, "last_run.json")
MEMORY = os.path.join(DATA, "memory.jsonl")
INNATE = os.path.join(DATA, "innate_rules.json")
TOLERANCE = os.path.join(DATA, "tolerance.json")
OUT = os.path.join(os.path.dirname(__file__), "report.html")
OUT_FRAGMENT = os.path.join(os.path.dirname(__file__), "report.fragment.html")

TITLE = "Soma路由观测"


def _esc(s) -> str:
    return html.escape(str(s))


def _load(path, default):
    if not os.path.exists(path):
        return default
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _load_lines(path):
    if not os.path.exists(path):
        return []
    out = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                out.append(json.loads(line))
    return out


CSS = """
:root {
  --bg: #f4f5f7;
  --surface: #ffffff;
  --surface-2: #fafbfc;
  --ink: #0b0b0b;
  --ink-2: #52514e;
  --muted: #898781;
  --hairline: #e4e5e8;
  --accent: #2a78d6;
  --accent-strong: #1c5cab;
  --accent-soft: #cde2fb;
  --teal: #1baf7a;
  --teal-soft: #c7ecdd;
  --critical: #d03b3b;
  --warning: #b7791f;
  --track: #eceef1;
  --shadow: 0 1px 2px rgba(11,11,11,0.05);
}
@media (prefers-color-scheme: dark) {
  :root:not([data-theme="light"]) {
    --bg: #0d0d0d;
    --surface: #1a1a19;
    --surface-2: #171716;
    --ink: #ffffff;
    --ink-2: #c3c2b7;
    --muted: #8a8a86;
    --hairline: #2c2c2a;
    --accent: #3987e5;
    --accent-strong: #6da7ec;
    --accent-soft: #184f95;
    --teal: #199e70;
    --teal-soft: #0f4a35;
    --critical: #e66767;
    --warning: #c98500;
    --track: #262624;
    --shadow: 0 1px 2px rgba(0,0,0,0.5);
  }
}
:root[data-theme="dark"] {
  --bg: #0d0d0d;
  --surface: #1a1a19;
  --surface-2: #171716;
  --ink: #ffffff;
  --ink-2: #c3c2b7;
  --muted: #8a8a86;
  --hairline: #2c2c2a;
  --accent: #3987e5;
  --accent-strong: #6da7ec;
  --accent-soft: #184f95;
  --teal: #199e70;
  --teal-soft: #0f4a35;
  --critical: #e66767;
  --warning: #c98500;
  --track: #262624;
  --shadow: 0 1px 2px rgba(0,0,0,0.5);
}

* { box-sizing: border-box; }
html { -webkit-text-size-adjust: 100%; }
body {
  margin: 0;
  background: var(--bg);
  color: var(--ink);
  font-family: system-ui, -apple-system, "Segoe UI", "PingFang SC", "Microsoft YaHei", sans-serif;
  line-height: 1.55;
  font-size: 15px;
}
.wrap { max-width: 1080px; margin: 0 auto; padding: 40px 24px 72px; }

/* header */
.masthead { display: flex; flex-direction: column; gap: 14px; margin-bottom: 28px; }
.eyebrow { font-size: 12px; letter-spacing: 0.14em; text-transform: uppercase; color: var(--muted); font-weight: 600; }
h1 { font-size: 30px; font-weight: 700; letter-spacing: -0.01em; margin: 0; line-height: 1.2; text-wrap: balance; }
.sub { color: var(--ink-2); max-width: 64ch; margin: 0; }
.meta { display: flex; flex-wrap: wrap; gap: 8px; }
.chip {
  display: inline-flex; align-items: center; gap: 6px;
  padding: 4px 11px; border-radius: 999px;
  background: var(--surface); border: 1px solid var(--hairline);
  font-size: 12.5px; color: var(--ink-2); font-variant-numeric: tabular-nums;
}
.chip b { color: var(--ink); font-weight: 600; }

/* sections */
section { margin-top: 34px; }
.sec-head { display: flex; align-items: baseline; gap: 12px; margin-bottom: 14px; }
.sec-head h2 { font-size: 19px; font-weight: 700; margin: 0; }
.sec-head .note { font-size: 12.5px; color: var(--muted); }
.card {
  background: var(--surface); border: 1px solid var(--hairline);
  border-radius: 12px; padding: 20px 22px; box-shadow: var(--shadow);
}
.grid { display: grid; gap: 14px; }
.g2 { grid-template-columns: 1fr 1fr; }
.g3 { grid-template-columns: repeat(3, 1fr); }
@media (max-width: 760px) { .g2, .g3 { grid-template-columns: 1fr; } }

/* hero number */
.hero { display: flex; align-items: baseline; gap: 14px; flex-wrap: wrap; }
.hero .num { font-size: 52px; font-weight: 750; letter-spacing: -0.02em; line-height: 1; font-variant-numeric: tabular-nums; color: var(--accent); }
.hero .cap { font-size: 14px; color: var(--ink-2); max-width: 30ch; }

/* funnel */
.funnel { display: flex; flex-direction: column; gap: 9px; margin-top: 16px; }
.frow { display: grid; grid-template-columns: 108px 1fr 60px; align-items: center; gap: 12px; }
.frow .lbl { font-size: 13px; color: var(--ink-2); text-align: right; }
.frow .count { font-size: 14px; font-weight: 650; font-variant-numeric: tabular-nums; text-align: left; }
.track { height: 20px; background: var(--track); border-radius: 5px; overflow: hidden; }
.fill { height: 100%; background: var(--accent); border-radius: 5px; transition: width .4s ease; }
.fill.teal { background: var(--teal); }
.fill.faint { background: var(--accent-soft); }

/* saved breakdown */
.saved { display: flex; flex-wrap: wrap; gap: 10px; margin-top: 16px; }
.stat {
  flex: 1 1 160px; background: var(--surface-2); border: 1px solid var(--hairline);
  border-radius: 10px; padding: 12px 14px;
}
.stat .v { font-size: 24px; font-weight: 700; font-variant-numeric: tabular-nums; }
.stat .k { font-size: 12.5px; color: var(--ink-2); }
.stat .d { font-size: 11.5px; color: var(--muted); margin-top: 2px; }

/* escalated list */
.escalated { display: flex; flex-direction: column; gap: 16px; }
.item { border: 1px solid var(--hairline); border-radius: 10px; padding: 14px 16px; background: var(--surface-2); }
.item .row1 { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; }
.item .sig { font-size: 15px; font-weight: 700; font-variant-numeric: tabular-nums; }
.item .who { color: var(--ink-2); font-size: 13px; }
.item .raw { font-size: 13.5px; color: var(--ink); margin: 8px 0 2px; }
.item .reason { font-size: 12.5px; color: var(--muted); }
.sigbar { position: relative; height: 14px; background: var(--track); border-radius: 4px; margin-top: 10px; }
.sigbar .conf { position: absolute; left: 0; top: 0; bottom: 0; background: var(--accent); border-radius: 4px 0 0 4px; }
.sigbar .boost { position: absolute; top: 0; bottom: 0; background: var(--teal); }
.sigbar .line { position: absolute; top: -4px; bottom: -4px; width: 2px; background: var(--critical); }
.sigbar .line::after { content: attr(data-lbl); position: absolute; top: -17px; left: 50%; transform: translateX(-50%); font-size: 10px; color: var(--critical); white-space: nowrap; }
.legend { display: flex; gap: 16px; font-size: 12px; color: var(--muted); margin-top: 8px; flex-wrap: wrap; }
.legend span::before { content: ""; display: inline-block; width: 10px; height: 10px; border-radius: 2px; margin-right: 5px; vertical-align: -1px; }
.legend .c::before { background: var(--accent); }
.legend .b::before { background: var(--teal); }

/* tags */
.tag { display: inline-flex; align-items: center; gap: 4px; font-size: 11.5px; font-weight: 600; padding: 2px 8px; border-radius: 5px; }
.tag.innate { background: var(--teal-soft); color: var(--teal); }
.tag.benign { background: var(--accent-soft); color: var(--accent-strong); }
.tag.warn { background: #f6e8c8; color: var(--warning); }
.tag.up { background: var(--accent); color: #fff; }
.tag.down { background: var(--track); color: var(--muted); }
.sup-item { padding: 9px 0; border-bottom: 1px dashed var(--hairline); }
.sup-item:last-child { border-bottom: none; }
.sup-why { font-size: 12px; color: var(--muted); font-weight: 600; }
.sup-raw { font-size: 12.5px; color: var(--ink-2); margin-top: 2px; font-variant-numeric: tabular-nums; }
.gedge { stroke: var(--muted); stroke-width: 1.5; opacity: 0.5; }
.gnode { font-size: 10px; fill: var(--ink-2); }
.gtype { font-size: 8px; fill: var(--muted); }
.graph-svg { display: block; margin: 0 auto 14px; }
.rpt-head { font-size: 13px; font-weight: 700; color: var(--ink); }
.rpt-verdict { display: inline-block; padding: 1px 8px; border-radius: 5px; font-size: 12px; font-weight: 600; margin-left: 6px; }

/* deep analysis */
details { border: 1px solid var(--hairline); border-radius: 10px; margin-top: 6px; background: var(--surface); }
details summary { cursor: pointer; padding: 10px 14px; font-size: 13px; font-weight: 600; color: var(--ink-2); list-style: none; }
details summary::before { content: "▸ "; color: var(--accent); }
details[open] summary::before { content: "▾ "; }
details .body { padding: 4px 16px 16px; font-size: 13.5px; white-space: pre-wrap; color: var(--ink-2); }

/* memory */
.mem { display: flex; flex-direction: column; gap: 12px; }
.mem-item { border-left: 3px solid var(--teal); padding: 4px 0 4px 14px; }
.mem-item .sum { font-size: 14px; }
.mem-item .ttps { display: flex; flex-wrap: wrap; gap: 6px; margin-top: 8px; }
.ttps .t { font-size: 11.5px; background: var(--teal-soft); color: var(--teal); padding: 2px 8px; border-radius: 5px; font-weight: 600; }
.kv { display: flex; flex-wrap: wrap; gap: 8px; }
.kv .k { font-size: 12px; background: var(--surface-2); border: 1px solid var(--hairline); border-radius: 6px; padding: 4px 9px; font-variant-numeric: tabular-nums; color: var(--ink-2); }

/* knob */
.knobs { display: grid; grid-template-columns: repeat(4, 1fr); gap: 10px; }
@media (max-width: 760px) { .knobs { grid-template-columns: repeat(2, 1fr); } }
.knob { border: 1px solid var(--hairline); border-radius: 10px; padding: 12px 14px; background: var(--surface-2); }
.knob.active { border-color: var(--accent); box-shadow: 0 0 0 1px var(--accent); }
.knob .name { font-weight: 700; font-size: 14px; }
.knob .vals { font-size: 12px; color: var(--muted); margin-top: 4px; font-variant-numeric: tabular-nums; }
.knob .vals b { color: var(--ink-2); font-weight: 600; }

.foot { margin-top: 40px; font-size: 12.5px; color: var(--muted); border-top: 1px solid var(--hairline); padding-top: 16px; }
.empty { color: var(--ink-2); padding: 24px; }
code { font-family: ui-monospace, "SF Mono", Menlo, monospace; font-size: 0.9em; background: var(--track); padding: 1px 5px; border-radius: 4px; }
"""


def _funnel_html(run) -> str:
    c = run["counts"]
    total = max(1, c["total"])
    stages = [
        ("信号总数", c["total"], "accent"),
        ("上板", c["surfaced"], "accent"),
        ("归案分量", c["components"], "accent"),
        ("顶出案件", c["escalated"], "accent"),
        ("唤醒系统2", c["wake"], "teal"),
    ]
    rows = []
    for label, n, cls in stages:
        pct = round(n / total * 100, 1)
        rows.append(
            f'<div class="frow"><div class="lbl">{_esc(label)}</div>'
            f'<div class="track"><div class="fill {cls}" style="width:{pct}%"></div></div>'
            f'<div class="count">{n}</div></div>'
        )
    return "".join(rows)


def _saved_html(run) -> str:
    c = run["counts"]
    items = [
        ("耐受抑制", c["tol_suppressed"], "已知好 · 白名单静默"),
        ("固有免疫秒拦", c["innate_hits"], "已知坏 · 规则秒拦"),
        ("杏仁核抑制", c["suppressed"], "便宜模型判低分静默"),
        ("顶出未深想", c["saved"], "预算不够 / 固有免疫已识"),
    ]
    parts = []
    for k, v, d in items:
        parts.append(f'<div class="stat"><div class="v">{v}</div><div class="k">{_esc(k)}</div><div class="d">{_esc(d)}</div></div>')
    return "".join(parts)


def _board_html(run) -> str:
    board = run.get("board", [])
    if not board:
        return '<div class="empty">黑板上没有事件——所有信号都在边缘被抑制了（见下方审计清单）。</div>'
    parts = []
    for e in board:
        tags = ""
        if e.get("innate"):
            tags += '<span class="tag innate">固有免疫秒拦</span> '
        if e.get("label") == "benign":
            tags += '<span class="tag benign">已确认误报</span> '
        if e.get("escalated"):
            tags += '<span class="tag up">顶出</span>'
        else:
            tags += '<span class="tag down">未顶出</span>'
        uid = e.get("correlation_uid", "")
        parts.append(
            f'<div class="item">'
            f'<div class="row1"><span class="sig">{e["confidence"]:.2f}</span>'
            f'<span class="who">[{_esc(e["time"])}] {_esc(e["source"])}/{_esc(e["type"])} · '
            f'asset={_esc(e["asset"])}</span>{tags}</div>'
            f'<div class="raw">{_esc(e["raw"])}</div>'
            f'<div class="reason">杏仁核：{_esc(e["reason"])}</div>'
            f'<div class="reason">归案：<code>{_esc(uid)}</code></div>'
            f'</div>'
        )
    return "".join(parts)


def _suppressed_html(run) -> str:
    supp = run.get("suppressed", [])
    if not supp:
        return '<div class="empty">本轮没有被抑制的信号。</div>'
    rows = []
    for s in supp:
        conf = f' · conf={s["confidence"]}' if s.get("confidence") is not None else ""
        rows.append(
            f'<div class="sup-item"><div class="sup-why">{_esc(s.get("why", ""))}</div>'
            f'<div class="sup-raw">{_esc(s["time"])} · {_esc(s["asset"])} {_esc(s["type"])}'
            f'{conf} · {_esc(s["raw"])}</div></div>'
        )
    return "".join(rows)


def _entity_fill(etype: str) -> str:
    return {"asset": "var(--accent)", "id": "var(--teal)", "ip": "#eb6834",
            "hash": "#e87ba4", "domain": "#eda100"}.get(etype, "var(--muted)")


def _graph_html(run) -> str:
    g = run.get("graph") or {}
    nodes = g.get("nodes", [])
    if not nodes:
        return '<div class="empty">没有实体图。</div>'
    n = len(nodes)
    cx, cy, R = 200, 150, (120 if n > 1 else 0)
    pos = []
    for i in range(n):
        ang = 2 * math.pi * i / n - math.pi / 2
        pos.append((cx + R * math.cos(ang), cy + R * math.sin(ang)))
    edge_marks = []
    for a, b in g.get("edges", []):
        if a < n and b < n:
            x1, y1 = pos[a]
            x2, y2 = pos[b]
            edge_marks.append(f'<line x1="{x1:.0f}" y1="{y1:.0f}" x2="{x2:.0f}" y2="{y2:.0f}" class="gedge"/>')
    node_marks = []
    for i, nd in enumerate(nodes):
        x, y = pos[i]
        fill = _entity_fill(nd["type"])
        node_marks.append(f'<circle cx="{x:.0f}" cy="{y:.0f}" r="13" fill="{fill}"/>')
        node_marks.append(f'<text x="{x:.0f}" y="{y:.0f}" dy="-20" text-anchor="middle" class="gnode">{_esc(nd["value"])}</text>')
        node_marks.append(f'<text x="{x:.0f}" y="{y:.0f}" dy="5" text-anchor="middle" class="gtype">{_esc(nd["type"])}</text>')
    svg = (f'<svg viewBox="0 0 400 300" class="graph-svg" role="img" aria-label="告警实体图">'
           + "".join(edge_marks) + "".join(node_marks) + "</svg>")

    comps = g.get("components", [])
    comp_rows = []
    for c in comps:
        ent_str = " · ".join(e["value"] for e in c.get("entities", []))
        comp_rows.append(f'<div class="sup-item"><div class="sup-why">案件 {_esc(c["id"])}</div>'
                         f'<div class="sup-raw">{_esc(ent_str)}</div></div>')
    comp_html = '<div class="mem" style="margin-top:8px">' + "".join(comp_rows) + "</div>" if comp_rows else ""
    return svg + comp_html


def _reports_html(run) -> str:
    reports = run.get("deep_reports", [])
    if not reports:
        return '<div class="empty">本轮没有案件进入深度分析（预算内无需要深想的案件）。</div>'
    parts = []
    for dr in reports:
        r = dr.get("report", {})
        verdict = r.get("verdict", "")
        parts.append(
            f'<details open><summary class="rpt-head">案件 {_esc(dr.get("component", ""))}'
            f'<span class="rpt-verdict">{_esc(verdict)}</span> · 置信度 {_esc(r.get("confidence", ""))}</summary>'
            f'<div class="body">'
        )
        if r.get("digest"):
            parts.append(f'<b>摘要</b>：{_esc(r["digest"])}\n')
        for ev in r.get("evidence", []):
            parts.append(f'• {_esc(ev.get("fact", ""))} → {_esc(ev.get("conclusion", ""))}\n')
        for ac in r.get("attack_chain", []):
            parts.append(f'↳ {_esc(ac.get("phase", ""))}: {_esc(ac.get("description", ""))}\n')
        iocs = r.get("iocs", [])
        if iocs:
            parts.append('<b>IOC</b>：' + "、".join(_esc(i.get("value", "")) for i in iocs) + "\n")
        unk = r.get("unknowns", [])
        if unk:
            parts.append('<b>待查</b>：' + "；".join(_esc(u) for u in unk) + "\n")
        rem = r.get("remediations", [])
        if rem:
            parts.append('<b>处置</b>：' + "；".join(_esc(x) for x in rem) + "\n")
        parts.append('</div></details>')
    return "".join(parts)


def _memory_html(memory, innate, tol) -> str:
    parts = []
    parts.append('<div class="sec-head"><h2>免疫耐受白名单</h2><span class="note">已知好 → 静默</span></div>')
    parts.append(f'<div class="card"><div class="kv">' + "".join(
        f'<span class="k">{_esc(a)} · {_esc(t)}</span>' for a, t in sorted(tol)
    ) + ("<span class='note' style='color:var(--muted)'>（空）</span>" if not tol else "") + "</div></div>")

    parts.append('<div class="sec-head"><h2>固有免疫规则</h2><span class="note">已知坏 → 边缘秒拦</span></div>')
    parts.append(f'<div class="card"><div class="kv">' + "".join(
        f'<span class="k">{_esc(a)} · {_esc(t)}</span>' for a, t in sorted(innate)
    ) + ("<span class='note' style='color:var(--muted)'>（空）</span>" if not innate else "") + "</div></div>")

    parts.append('<div class="sec-head"><h2>检索记忆</h2><span class="note">睡眠巩固夜里沉淀，跨天累积</span></div>')
    if not memory:
        parts.append('<div class="card"><div class="empty">还没有记忆——跑 <code>python3 consolidate.py</code> 巩固一次。</div></div>')
    else:
        items = []
        for m in memory:
            ttps = "".join(f'<span class="t">{_esc(t)}</span>' for t in m.get("ttps", []))
            items.append(
                f'<div class="mem-item"><div class="sum">{_esc(m.get("summary", ""))}</div>'
                f'<div class="ttps">{ttps}</div></div>'
            )
        parts.append(f'<div class="card"><div class="mem">' + "".join(items) + "</div></div>")
    return "".join(parts)


def _knob_html(run) -> str:
    presets = [
        ("宽松", 0.75, 0.85, 1), ("正常", 0.55, 0.75, 2),
        ("保守", 0.40, 0.62, 3), ("战时", 0.25, 0.45, 99),
    ]
    cur = run["knob"]["name"]
    parts = []
    for name, s, e, b in presets:
        active = " active" if name == cur else ""
        parts.append(
            f'<div class="knob{active}"><div class="name">{name}</div>'
            f'<div class="vals">抑制线 <b>{s}</b> · 顶出线 <b>{e}</b> · 预算 <b>{b}</b></div></div>'
        )
    return "".join(parts)


def build() -> str:
    run = _load(LAST_RUN, None)
    memory = _load_lines(MEMORY)
    innate = _load(INNATE, [])
    tol = _load(TOLERANCE, [])

    if run is None:
        body = ('<div class="card"><div class="empty">还没有运行数据。先跑 <code>python3 main.py</code> '
                '产生一次运行，再跑 <code>python3 visualize.py</code>。</div></div>')
        return body

    knob = run["knob"]
    c = run["counts"]
    hero = f'{c["wake"]}<span style="font-size:0.5em;color:var(--muted)"> / {c["total"]}</span>'

    body = f"""
<div class="wrap">
  <header class="masthead">
    <div class="eyebrow">Soma · 路由观测（不是告警大屏）</div>
    <h1>贵模型只醒了 {c["wake"]} 个案件</h1>
    <p class="sub">这页只讲三件事：<b>省</b>（把分析师从告警海里筛出来）、<b>学</b>（耐受与固有免疫记下了什么）、<b>调</b>（风险旋钮拨到哪一档）。</p>
    <div class="meta">
      <span class="chip">旋钮 <b>{_esc(knob["name"])}</b></span>
      <span class="chip">预算 <b>{knob["budget"]}</b> 次/轮</span>
      <span class="chip">信号源 <b>{_esc(run["input"])}</b></span>
      <span class="chip">杏仁核 <b>{_esc(run["system1_backend"])}</b></span>
      <span class="chip">系统2 <b>{_esc(run["system2_backend"])}</b></span>
    </div>
  </header>

  <section>
    <div class="sec-head"><h2>告警降噪</h2><span class="note">信号从进场到唤醒贵模型的漏斗</span></div>
    <div class="card">
      <div class="hero"><div class="num">{hero}</div><div class="cap">条信号里，只有这么多进入深度分析——其余被边缘筛掉，且每一条都留痕可查。</div></div>
      <div class="funnel">{_funnel_html(run)}</div>
      <div class="saved">{_saved_html(run)}</div>
    </div>
  </section>

  <section>
    <div class="sec-head"><h2>图 · 实体关联</h2><span class="note">实体为点、共现为边，连通分量 = 案件</span></div>
    <div class="card">{_graph_html(run)}</div>
  </section>

  <section>
    <div class="sec-head"><h2>黑板 · 全局工作空间</h2><span class="note">所有上板信号，按 correlation_uid 归案</span></div>
    <div class="card"><div class="escalated">{_board_html(run)}</div></div>
  </section>

  <section>
    <div class="sec-head"><h2>系统2 · 结构化调查</h2><span class="note">定性 / 证据 / IOC / 待查，反幻觉纪律</span></div>
    <div class="card"><div class="escalated">{_reports_html(run)}</div></div>
  </section>

  <section>
    <div class="sec-head"><h2>被抑制的信号 · 可审计</h2><span class="note">不是丢弃，是降级留痕——每条都能查为什么被压</span></div>
    <div class="card"><details open><summary>本轮降级 {len(run.get("suppressed", []))} 条</summary><div class="escalated">{_suppressed_html(run)}</div></details></div>
  </section>

  <section>
    <div class="sec-head"><h2>学 · 免疫记忆</h2><span class="note">越用越懂的累积</span></div>
    <div class="grid">{_memory_html(memory, innate, tol)}</div>
  </section>

  <section>
    <div class="sec-head"><h2>调 · 风险旋钮</h2><span class="note">当前档位高亮</span></div>
    <div class="knobs">{_knob_html(run)}</div>
  </section>

  <footer class="foot">
    黑板是路由决策点，不是展示屏——这页观测的是「降噪 / 越用越准 / 风险档位」，不是告警墙。<br>
    重新生成：<code>python3 main.py</code> → <code>python3 visualize.py</code>
  </footer>
</div>
"""
    return body


def main() -> None:
    body = build()
    fragment = f'<title>{TITLE}</title>\n<style>{CSS}</style>\n{body}'
    full = ("<!doctype html>\n<html lang=\"zh-CN\">\n<head>\n<meta charset=\"utf-8\">\n"
            "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">\n"
            f"<title>{TITLE}</title>\n<style>{CSS}</style>\n</head>\n<body>\n{body}\n</body>\n</html>\n")
    with open(OUT, "w", encoding="utf-8") as f:
        f.write(full)
    with open(OUT_FRAGMENT, "w", encoding="utf-8") as f:
        f.write(fragment)
    print(f"已生成 {os.path.basename(OUT)}（本地浏览器直接打开）")
    print(f"已生成 {os.path.basename(OUT_FRAGMENT)}（发布用片段）")


if __name__ == "__main__":
    main()
