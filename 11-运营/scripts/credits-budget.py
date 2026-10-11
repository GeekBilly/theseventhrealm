#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""积分预算与每日限额：算日额、记消耗、出图形化看板。

用法：
  python3 credits-budget.py                      今日简报（stdout）
  python3 credits-budget.py --log 12.5           记今天的实际消耗
  python3 credits-budget.py --log 8 --date 2026-10-03 --note 晨检
  python3 credits-budget.py --board              生成/刷新当月 HTML 看板
  python3 credits-budget.py --board --month 2026-11

预算模型（每月 500 积分，1 号到账）：
  日常池 = 500 - 重活池 90 - 缓冲（余量）
  日额按权重分配：工作日 1.0 / 生产日（周末整块）2.5
  单日硬上限 60，重活须从重活池支出并登记
"""
import argparse
import calendar
import csv
import datetime as dt
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "11-运营" / "data" / "credits-budget.csv"
REPORTS = ROOT / "11-运营" / "reports"

MONTHLY = 500          # 每月 1 号到账额度
HEAVY_POOL = 90        # 重活池：每月 ≤2 次，单次 ≤45
BUFFER = 54            # 月末缓冲：平时不动，最后 3 天释放
W_WEEKDAY, W_PROD = 1.0, 2.5
CAP = 60               # 单日硬上限
WEEK = ["一", "二", "三", "四", "五", "六", "日"]


# ---------- 基础计算 ----------
def month_days(y, m):
    n = calendar.monthrange(y, m)[1]
    return [dt.date(y, m, d) for d in range(1, n + 1)]


def day_type(d):
    return "生产日" if d.weekday() >= 5 else "工作日"


def baseline(y, m):
    """当月逐日基线日额：{date: 日额}"""
    ds = month_days(y, m)
    prod = sum(1 for d in ds if day_type(d) == "生产日")
    wk = len(ds) - prod
    pool = MONTHLY - HEAVY_POOL - BUFFER
    unit = pool / (wk * W_WEEKDAY + prod * W_PROD)
    return {d: round(unit * (W_PROD if day_type(d) == "生产日" else W_WEEKDAY), 1) for d in ds}


def read_used():
    """读台账：{date: (used, note)}"""
    out = {}
    if DATA.exists():
        with DATA.open(newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                try:
                    out[dt.date.fromisoformat(row["date"])] = (
                        float(row["used"] or 0), row.get("note", ""))
                except (ValueError, KeyError):
                    continue
    return out


def write_used(used_map):
    DATA.parent.mkdir(parents=True, exist_ok=True)
    with DATA.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["date", "type", "used", "note"])
        for d in sorted(used_map):
            used, note = used_map[d]
            w.writerow([d.isoformat(), day_type(d), used, note])


def today_limit(y, m, base, used_map, today):
    """动态可用额度：剩余可分配额 ÷ 剩余天数权重和 × 今日权重。

    月初正好等于基线日额；前面花超了，后面自动收紧；省着用，后面自动放宽。
    """
    ds = [d for d in month_days(y, m) if d >= today]
    if not ds:
        return 0.0
    spent = sum(v[0] for d, v in used_map.items() if d.month == m and d.year == y)
    left = (MONTHLY - HEAVY_POOL - BUFFER) - spent
    # 最后 3 天释放缓冲，避免月末被迫停摆
    if len(ds) <= 3:
        left += BUFFER
    wsum = sum(W_PROD if day_type(d) == "生产日" else W_WEEKDAY for d in ds)
    w = W_PROD if day_type(today) == "生产日" else W_WEEKDAY
    return max(0.0, round(min(left / wsum * w, CAP), 1))


def buffer_of(y, m):
    """缓冲 = 月额度 - 重活池 - 逐日基线日额合计（含取整误差）"""
    return round(MONTHLY - HEAVY_POOL - sum(baseline(y, m).values()), 1)


# ---------- 简报 ----------
def brief(y, m, today=None):
    today = today or dt.date.today()
    base = baseline(y, m)
    used_map = read_used()
    spent = sum(v[0] for d, v in used_map.items() if d.year == y and d.month == m)
    left_days = len([d for d in month_days(y, m) if d >= today])
    dyn = today_limit(y, m, base, used_map, today)
    bl = base.get(today, 0)
    print(f"{today.isoformat()}（周{WEEK[today.weekday()]}·{day_type(today)}）")
    print(f"  今日基线日额 : {bl} 分")
    print(f"  今日动态可用 : {dyn} 分（硬上限 {CAP}）")
    print(f"  本月已用     : {round(spent, 2)} / {MONTHLY} 分")
    print(f"  剩余额度     : {round(MONTHLY - spent, 2)} 分，剩余 {left_days} 天")
    heavy = sum(v[0] for d, v in used_map.items()
                if d.year == y and d.month == m and "重活" in (v[1] or ""))
    print(f"  重活池       : 已用 {round(heavy, 2)} / {HEAVY_POOL} 分（每月 ≤2 次，单次 ≤45）")
    print(f"  缓冲         : {buffer_of(y, m)} 分")
    if spent > MONTHLY * 0.8:
        print("  ⚠️ 已用超 80%：自动收紧，剩余天数内只做维护，停一切批量生产")
    elif dyn < bl * 0.6:
        print("  ⚠️ 动态额度低于基线 60%：前面花超了，今日只做维护类")


# ---------- 图形化看板 ----------
CSS = """
:root{--bg:#faf8f5;--card:#fff;--ink:#2b2b2b;--sub:#6b6b6b;--line:#e6e1da;
      --red:#b03a2e;--teal:#3b5f6b;--gold:#c9a227}
*{box-sizing:border-box}
body{margin:0;padding:28px;background:var(--bg);color:var(--ink);
     font:15px/1.6 -apple-system,"PingFang SC","Hiragino Sans GB","Microsoft YaHei",sans-serif}
.wrap{max-width:900px;margin:0 auto}
h1{font-size:22px;margin:0 0 4px}
.meta{color:var(--sub);font-size:13px;margin-bottom:20px}
.kpis{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin-bottom:18px}
.kpi{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:14px}
.kpi .k{font-size:12px;color:var(--sub)}
.kpi .v{font-size:24px;font-weight:600;margin-top:2px}
.kpi .s{font-size:12px;color:var(--sub);margin-top:2px}
.card{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:16px;margin-bottom:16px}
.card h2{font-size:15px;margin:0 0 12px}
svg{width:100%;height:auto;display:block}
.val{font-size:10px;font-weight:600;text-anchor:middle}
.lbl{font-size:10px;fill:#6b6b6b;text-anchor:middle}
table{width:100%;border-collapse:collapse;font-size:13px}
th,td{padding:6px 8px;border-bottom:1px solid var(--line);text-align:left}
th{color:var(--sub);font-weight:500;font-size:12px}
.legend{font-size:12px;color:var(--sub);margin-top:8px}
.legend i{display:inline-block;width:10px;height:10px;border-radius:2px;margin-right:4px}
.alert{background:#fdeceb;border:1px solid #f0c4bf;color:#8f2c22;border-radius:8px;padding:10px 12px;margin-bottom:16px}
.ok{background:#eef4f2;border:1px solid #cfe0dc;color:#25544b;border-radius:8px;padding:10px 12px;margin-bottom:16px}
@media(max-width:640px){.kpis{grid-template-columns:repeat(2,1fr)}}
"""


def build_board(y, m, today=None):
    today = today or dt.date.today()
    ds = month_days(y, m)
    base = baseline(y, m)
    used_map = read_used()
    spent = round(sum(v[0] for d, v in used_map.items() if d.year == y and d.month == m), 2)
    left = round(MONTHLY - spent, 2)
    left_days = len([d for d in ds if d >= today])
    dyn = today_limit(y, m, base, used_map, today)
    buf = buffer_of(y, m)

    # 图1：逐日柱形（已用朱红 + 剩余浅墨）
    n = len(ds)
    W, H = 900, 300
    pad_l, pad_b, pad_t = 46, 30, 24
    plot_w = W - pad_l - 16
    slot = plot_w / n
    bw = max(6.0, slot * 0.62)
    maxv = max([base[d] for d in ds] + [v[0] for v in used_map.values()] + [1])
    scale = (H - pad_b - pad_t) / (maxv * 1.15)
    bars = []
    for i, d in enumerate(ds):
        x = pad_l + i * slot + (slot - bw) / 2
        bl = base[d]
        used = used_map.get(d, (0, ""))[0]
        used_h = used * scale
        rest_h = max(0.0, (bl - used)) * scale
        y_used = H - pad_b - used_h
        y_rest = y_used - rest_h
        prod = day_type(d) == "生产日"
        top = "#3b5f6b" if prod else "#8a9ba0"
        bars.append(
            f'<rect x="{x:.1f}" y="{y_rest:.1f}" width="{bw:.1f}" height="{rest_h:.1f}" '
            f'rx="2" fill="{top}" opacity="0.55"/>')
        if used > 0:
            bars.append(
                f'<rect x="{x:.1f}" y="{y_used:.1f}" width="{bw:.1f}" height="{used_h:.1f}" '
                f'rx="2" fill="#b03a2e"/>')
            bars.append(
                f'<text x="{x + bw / 2:.1f}" y="{y_used - 4:.1f}" class="val" fill="#b03a2e">{used:g}</text>')
        if d.day in (1, 5, 10, 15, 20, 25, 31) or d == today:
            bars.append(f'<text x="{x + bw / 2:.1f}" y="{H - pad_b + 14:.1f}" class="lbl">{d.day}</text>')
        if d == today:
            bars.append(
                f'<rect x="{x - 1:.1f}" y="{pad_t - 8:.1f}" width="{bw + 2:.1f}" '
                f'height="{H - pad_b - pad_t + 8:.1f}" fill="none" stroke="#c9a227" stroke-width="1.2"/>')

    # 图2：累计曲线（计划 vs 实际）
    cum_p, cum_a, acc_p, acc_a = [], [], 0.0, 0.0
    for i, d in enumerate(ds):
        acc_p += base[d]
        acc_a += used_map.get(d, (0, ""))[0]
        cum_p.append((pad_l + i * slot + slot / 2, H - pad_b - acc_p * scale))
        cum_a.append((pad_l + i * slot + slot / 2, H - pad_b - acc_a * scale))
    pts_p = " ".join(f"{x:.1f},{y:.1f}" for x, y in cum_p)
    pts_a = " ".join(f"{x:.1f},{y:.1f}" for x, y in cum_a)

    rows = []
    for d in ds:
        used = used_map.get(d, (0, ""))[0]
        note = used_map.get(d, (0, ""))[1]
        diff = round(base[d] - used, 1)
        flag = "—" if d > today else ("✅" if diff >= 0 else "⚠️")
        rows.append(
            f"<tr><td>{d.isoformat()}</td><td>周{WEEK[d.weekday()]}</td><td>{day_type(d)}</td>"
            f"<td>{base[d]:g}</td><td>{used:g}</td><td>{diff:+g}</td><td>{flag}</td>"
            f"<td>{note}</td></tr>")

    alert = ""
    if spent > MONTHLY * 0.8:
        alert = ('<div class="alert">⚠️ 已用超 80%：进入收紧模式——只做维护，'
                 '停一切批量生产，优先靠签到与社区发文赚分</div>')
    else:
        pace = spent / max(1, len([d for d in ds if d <= today]))
        if pace > sum(base[d] for d in ds if d <= today) / max(1, len([d for d in ds if d <= today])) * 1.3:
            alert = ('<div class="alert">⚠️ 实际节奏快于计划 30%：后面几天自动收紧日额</div>')

    name = f"积分预算看板-{y}-{m:02d}.html"
    out = REPORTS / name
    html_doc = f"""<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>积分预算看板 · {y}-{m:02d}</title>
<style>{CSS}</style></head><body><div class="wrap">
<h1>积分预算看板 · {y} 年 {m} 月</h1>
<div class="meta">月额度 {MONTHLY} 分（每月 1 号到账）· 数据时点 {today.isoformat()} ·
日额由 <code>11-运营/scripts/credits-budget.py</code> 按「工作日 1.0 / 生产日 2.5」权重算出</div>
{alert or '<div class="ok">✅ 消耗在计划线内，按日额执行即可</div>'}

<div class="kpis">
  <div class="kpi"><div class="k">月额度 / 已用</div><div class="v">{spent:g}</div><div class="s">/{MONTHLY} 分</div></div>
  <div class="kpi"><div class="k">剩余额度</div><div class="v">{left:g}</div><div class="s">剩余 {left_days} 天</div></div>
  <div class="kpi"><div class="k">今日可花</div><div class="v">{dyn:g}</div><div class="s">基线 {base.get(today, 0):g} · 上限 {CAP}</div></div>
  <div class="kpi"><div class="k">重活池 / 缓冲</div><div class="v">{HEAVY_POOL}</div><div class="s">缓冲 {buf:g} 分</div></div>
</div>

<div class="card">
  <h2>逐日日额与已用（柱形图）</h2>
  <svg viewBox="0 0 {W} {H}" role="img" aria-label="逐日积分日额与已用柱状图">
    <line x1="{pad_l}" y1="{H - pad_b}" x2="{W - 16}" y2="{H - pad_b}" stroke="#e6e1da"/>
    {''.join(bars)}
  </svg>
  <div class="legend">
    <i style="background:#b03a2e"></i>已用　<i style="background:#8a9ba0;opacity:.55"></i>工作日剩余日额　
    <i style="background:#3b5f6b;opacity:.55"></i>生产日剩余日额　<i style="background:#c9a227"></i>今天
  </div>
</div>

<div class="card">
  <h2>累计消耗：计划 vs 实际</h2>
  <svg viewBox="0 0 {W} {H}" role="img" aria-label="累计积分消耗曲线">
    <line x1="{pad_l}" y1="{H - pad_b}" x2="{W - 16}" y2="{H - pad_b}" stroke="#e6e1da"/>
    <polyline points="{pts_p}" fill="none" stroke="#8a9ba0" stroke-width="1.8" stroke-dasharray="6 4"/>
    <polyline points="{pts_a}" fill="none" stroke="#b03a2e" stroke-width="2.2"/>
    <text x="{W - 20}" y="{pad_t + 6}" class="lbl" text-anchor="end" fill="#b03a2e">实际累计（红）</text>
    <text x="{W - 20}" y="{pad_t + 22}" class="lbl" text-anchor="end" fill="#8a9ba0">计划累计（灰虚线）</text>
  </svg>
</div>

<div class="card"><h2>{m} 月逐日明细</h2>
<table>
<tr><th>日期</th><th>星期</th><th>日型</th><th>日额</th><th>已用</th><th>结余</th><th>状态</th><th>备注</th></tr>
{''.join(rows)}
</table></div>
</div></body></html>
"""
    out.write_text(html_doc, encoding="utf-8")
    print(f"已生成：{out}")
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--log", type=float, help="记录当日实际消耗")
    ap.add_argument("--date", help="配合 --log 指定日期 YYYY-MM-DD")
    ap.add_argument("--note", default="", help="备注（重活请写「重活：xxx」）")
    ap.add_argument("--board", action="store_true", help="生成 HTML 看板")
    ap.add_argument("--month", help="指定月份 YYYY-MM")
    args = ap.parse_args()

    if args.month:
        y, m = (int(x) for x in args.month.split("-"))
    else:
        t = dt.date.today()
        y, m = t.year, t.month

    if args.log is not None:
        d = dt.date.fromisoformat(args.date) if args.date else dt.date.today()
        used_map = read_used()
        prev = used_map.get(d, (0.0, ""))[0]
        used_map[d] = (args.log, args.note)
        write_used(used_map)
        print(f"已记录 {d.isoformat()}（{day_type(d)}）消耗 {args.log} 分"
              + (f"（覆盖原 {prev:g}）" if prev else ""))
        return

    if args.board:
        build_board(y, m)
        return

    brief(y, m)


if __name__ == "__main__":
    sys.exit(main())
