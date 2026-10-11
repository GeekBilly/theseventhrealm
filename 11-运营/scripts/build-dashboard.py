#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
把 fetch-credits.sh 输出的 JSON 渲染成带柱形图的 HTML 仪表盘。

用法：
  11-运营/scripts/fetch-credits.sh | 11-运营/scripts/build-dashboard.py
  11-运营/scripts/build-dashboard.py credits.json          # 也可直接读文件
  11-运营/scripts/build-dashboard.py credits.json -o out.html

输出默认为 11-运营/reports/积分仪表盘-<日期>.html
"""
import json
import sys
import os
import datetime

ROOT = "/Users/billyhou/WorkBuddy/2026-09-25-15-56-17"
OUT_DIR = os.path.join(ROOT, "11-运营", "reports")

MONTH_NEED_LOW = 200
MONTH_NEED_HIGH = 400
RED_LINE_DAYS = 15


def load_json(args):
    if args and args[0] not in ("-o", "--out"):
        with open(args[0], encoding="utf-8") as f:
            return json.load(f)
    return json.load(sys.stdin)


def parse_by_day(by_day):
    out = []
    for item in by_day or []:
        if isinstance(item, str) and ":" in item:
            d, v = item.split(":", 1)
            out.append((d, float(v)))
        elif isinstance(item, (list, tuple)):
            out.append((str(item[0]), float(item[1])))
    return sorted(out)


def esc(s):
    return (str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))


def build_html(data):
    by_day = parse_by_day(data.get("byDay"))
    remain = float(data.get("remain", 0))
    avg7 = float(data.get("avg7") or 0)
    sum7 = float(data.get("sum7") or sum(v for _, v in by_day))
    cycle_used = data.get("cycleUsed")
    cycle_total = data.get("cycleTotal")
    fetched = data.get("fetchedAt", "")

    light = [v for _, v in by_day if v < 20]
    baseline = round(sum(light) / len(light), 2) if light else 0
    runway_avg = round(remain / avg7, 1) if avg7 else 0
    runway_base = round(remain / baseline, 1) if baseline else 0
    month_burn = round(avg7 * 30)
    gap_need = max(0, MONTH_NEED_HIGH - remain)
    over = max(0, month_burn - MONTH_NEED_HIGH)
    alert = runway_avg < RED_LINE_DAYS

    # 柱形图
    max_v = max((v for _, v in by_day), default=1) or 1
    chart_w, chart_h = 720, 260
    pad_l, pad_b, pad_t = 56, 46, 16
    n = max(len(by_day), 1)
    slot = (chart_w - pad_l - 20) / n
    bar_w = min(slot * 0.56, 56)
    bars = []
    for i, (d, v) in enumerate(by_day):
        h = (v / max_v) * (chart_h - pad_b - pad_t)
        x = pad_l + slot * i + (slot - bar_w) / 2
        y = chart_h - pad_b - h
        heavy = v > 200
        color = "#b03a2e" if heavy else "#3b5f6b"
        label = d[5:]
        bars.append(
            f'<rect x="{x:.1f}" y="{y:.1f}" width="{bar_w:.1f}" height="{h:.1f}" rx="3" fill="{color}"/>'
            f'<text x="{x + bar_w / 2:.1f}" y="{y - 7:.1f}" class="val" fill="{color}">{v:g}</text>'
            f'<text x="{x + bar_w / 2:.1f}" y="{chart_h - pad_b + 20:.1f}" class="lbl">{esc(label)}</text>'
        )
    avg_y = chart_h - pad_b - (avg7 / max_v) * (chart_h - pad_b - pad_t)
    bars.append(
        f'<line x1="{pad_l}" y1="{avg_y:.1f}" x2="{chart_w - 10}" y2="{avg_y:.1f}" '
        f'stroke="#c9a227" stroke-width="1.5" stroke-dasharray="6 4"/>'
        f'<text x="{chart_w - 12}" y="{avg_y - 6:.1f}" class="avg" text-anchor="end">日均 {avg7:g}</text>'
    )

    runway_pct = min(100, runway_avg / RED_LINE_DAYS * 100) if avg7 else 100
    runway_color = "#b03a2e" if alert else "#3b5f6b"

    alert_html = (
        '<div class="alert">🔴 红线报警：按近 7 日均值，跑道仅 '
        f'{runway_avg} 天（&lt; {RED_LINE_DAYS} 天）→ 暂停批量壁纸生产，优先赚分</div>'
        if alert else
        f'<div class="ok">✅ 跑道 {runway_avg} 天，高于 {RED_LINE_DAYS} 天红线</div>'
    )

    cyc = f"{cycle_used:g} / {cycle_total:g}" if cycle_used is not None else "—"

    return f"""<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>积分仪表盘 · {esc(fetched[:10])}</title>
<style>
  :root{{ --bg:#faf8f5; --card:#fff; --ink:#2b2b2b; --sub:#6b6b6b; --line:#e6e1da; --red:#b03a2e; --teal:#3b5f6b; }}
  *{{box-sizing:border-box}}
  body{{margin:0;padding:28px;background:var(--bg);color:var(--ink);
       font:15px/1.6 -apple-system,"PingFang SC","Hiragino Sans GB","Microsoft YaHei",sans-serif}}
  .wrap{{max-width:860px;margin:0 auto}}
  h1{{font-size:22px;margin:0 0 4px}}
  .meta{{color:var(--sub);font-size:13px;margin-bottom:20px}}
  .kpis{{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin-bottom:18px}}
  .kpi{{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:14px}}
  .kpi .k{{font-size:12px;color:var(--sub)}}
  .kpi .v{{font-size:24px;font-weight:600;margin-top:2px}}
  .kpi .s{{font-size:12px;color:var(--sub);margin-top:2px}}
  .card{{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:16px;margin-bottom:16px}}
  .card h2{{font-size:15px;margin:0 0 12px}}
  svg{{width:100%;height:auto;display:block}}
  .val{{font-size:11px;font-weight:600;text-anchor:middle}}
  .lbl{{font-size:11px;fill:#6b6b6b;text-anchor:middle}}
  .avg{{font-size:11px;fill:#c9a227}}
  .bar{{height:10px;background:#ece7e0;border-radius:6px;overflow:hidden;margin-top:6px}}
  .bar span{{display:block;height:100%;background:{runway_color};width:{runway_pct:.0f}%}}
  .alert{{background:#fdeceb;border:1px solid #f0c4bf;color:#8f2c22;border-radius:8px;padding:10px 12px;margin-bottom:16px}}
  .ok{{background:#eef4f2;border:1px solid #cfe0dc;color:#25544b;border-radius:8px;padding:10px 12px;margin-bottom:16px}}
  table{{width:100%;border-collapse:collapse;font-size:14px}}
  th,td{{padding:7px 8px;border-bottom:1px solid var(--line);text-align:left}}
  th{{color:var(--sub);font-weight:500;font-size:12px}}
  ul{{margin:8px 0 0;padding-left:20px}} li{{margin:3px 0}}
  .todo{{color:var(--sub)}}
  @media(max-width:640px){{.kpis{{grid-template-columns:repeat(2,1fr)}}}}
</style></head><body><div class="wrap">
<h1>积分仪表盘</h1>
<div class="meta">数据时点 {esc(fetched)} · 来源：WorkBuddy 官方接口自动取数</div>

{alert_html}

<div class="kpis">
  <div class="kpi"><div class="k">当前余额</div><div class="v">{remain:g}</div><div class="s">体验版 · 周期已用 {cyc}</div></div>
  <div class="kpi"><div class="k">近 7 日日均消耗</div><div class="v">{avg7:g}</div><div class="s">7 日合计 {sum7:g}</div></div>
  <div class="kpi"><div class="k">可支撑天数</div><div class="v" style="color:{runway_color}">{runway_avg:g}</div>
    <div class="s">轻活基线口径 {runway_base:g} 天</div>
    <div class="bar"><span></span></div></div>
  <div class="kpi"><div class="k">月度需求缺口</div><div class="v">{gap_need:.0f}</div><div class="s">按日均月耗 {month_burn:g}（超上限 {over:g}）</div></div>
</div>

<div class="card">
  <h2>近 7 日逐日消耗（柱形图）</h2>
  <svg viewBox="0 0 {chart_w} {chart_h}" role="img" aria-label="近7日积分消耗柱状图">
    <line x1="{pad_l}" y1="{chart_h - pad_b}" x2="{chart_w - 10}" y2="{chart_h - pad_b}" stroke="#e6e1da"/>
    {''.join(bars)}
  </svg>
  <div class="meta" style="margin:8px 0 0">深色柱＝重活日（单日 &gt;200 分）；虚线＝7 日均值。轻活基线 {baseline:g} 分/天。</div>
</div>

<div class="card"><h2>逐日明细</h2>
<table><tr><th>日期</th><th>消耗（分）</th><th>类型</th></tr>
{''.join(f'<tr><td>{esc(d)}</td><td>{v:g}</td><td>{"重活日" if v > 200 else "常规"}</td></tr>' for d, v in by_day)}
</table></div>

<div class="card"><h2>今日行动</h2><ul>
  <li>签到：客户端左下角头像 → 领取今日礼包（第 7 天 1000 分，断签可用补登卡）</li>
  <li class="todo">赚分：社区发文 1000 分/篇（精选再 +2000），稿子在 <code>09-社区/</code> 目录，一篇篇发</li>
  <li class="todo">{'⏸ 暂停批量壁纸生产（红线生效）' if alert else '壁纸生产可按计划进行'}</li>
</ul></div>
</div></body></html>
"""


def main():
    args = [a for a in sys.argv[1:]]
    out = None
    if "-o" in args:
        i = args.index("-o")
        out = args[i + 1]
        args = args[:i]
    data = load_json(args)
    html = build_html(data)
    if out is None:
        day = datetime.date.today().isoformat()
        out = os.path.join(OUT_DIR, f"积分仪表盘-{day}.html")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        f.write(html)
    print(out)


if __name__ == "__main__":
    main()
