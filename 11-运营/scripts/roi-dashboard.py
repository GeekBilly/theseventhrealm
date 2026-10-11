#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""第七境 · 投入产出（ROI）看板

把散在五本台账里的数据合成一张图，并对「策略调整规则」做触发判定。

用法：
    python3 11-运营/scripts/roi-dashboard.py            # stdout 简报 + 刷新 HTML
    python3 11-运营/scripts/roi-dashboard.py --quiet    # 只刷新 HTML
    python3 11-运营/scripts/roi-dashboard.py --csv      # 只输出机器可读的一行 JSON

读：
    11-运营/data/deepseek-balance.csv   （token 成本，每日自动记）
    11-运营/data/credits-budget.csv     （积分消耗）
    11-运营/data/revenue.csv            （收入，成交后手动记）
    04-市场/03-推广获客/数据回收/发布数据.csv （流量/互动）
    04-市场/05-客户库/客户库.csv        （邮件名单）
写：
    11-运营/reports/ROI看板.html

规则与阈值见 11-运营/成本管控/投入产出比-模型与策略-2026-10-02.md
"""
import argparse
import csv
import datetime
import json
import os
import re
import sys

ROOT = "/Users/billyhou/WorkBuddy/2026-09-25-15-56-17"
D = os.path.join(ROOT, "11-运营", "data")
REPORTS = os.path.join(ROOT, "11-运营", "reports")

# 阈值（与策略文档保持一致，改这里要同步改文档）
TH = dict(session_cost_warn=20.0, balance_low=20.0, list_slow=5.0,
          zero_order_days=14, roi_quarter_floor=500.0, list_quarter_floor=200.0)


def read_csv(path):
    if not os.path.exists(path):
        return []
    with open(path, encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def num(x, d=0.0):
    try:
        return float(str(x).replace(",", "").strip())
    except Exception:
        return d


# ── 1. token 成本：余额台账里所有「下降」之和 ──
def token_cost():
    rows = read_csv(os.path.join(D, "deepseek-balance.csv"))
    spend = 0.0
    prev = None
    pts = []
    for r in rows:
        b = num(r.get("total"), None)
        if b is None:
            continue
        pts.append((r.get("date", ""), b))
        if prev is not None and b < prev:
            spend += prev - b
        prev = b
    return spend, (pts[-1][1] if pts else None), pts


# ── 2. 收入 ──
def revenue():
    rows = read_csv(os.path.join(D, "revenue.csv"))
    amt = sum(num(r.get("amount")) for r in rows)
    net = sum(num(r.get("net")) for r in rows)
    orders = sum(int(num(r.get("qty"), 1)) for r in rows)
    return amt, net, orders, rows


# ── 3. 名单 ──
def maillist():
    p = os.path.join(ROOT, "04-市场", "05-客户库", "客户库.csv")
    rows = read_csv(p)
    return len(rows), rows


# ── 4. 流量 ──
def traffic():
    p = os.path.join(ROOT, "04-市场", "03-推广获客", "数据回收", "发布数据.csv")
    rows = read_csv(p)
    imp = sum(num(r.get("曝光") or r.get("impressions")) for r in rows)
    return len(rows), imp


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--quiet", action="store_true")
    ap.add_argument("--csv", action="store_true")
    a = ap.parse_args()

    cost, balance, pts = token_cost()
    rev, net, orders, rev_rows = revenue()
    n_list, list_rows = maillist()
    n_posts, imp = traffic()

    roi = (net / cost) if cost > 0 else None
    per_order = (cost / orders) if orders else None
    per_list = (cost / n_list) if n_list else None

    # ── 触发判定 ──
    alerts = []
    if balance is not None and balance < TH["balance_low"]:
        alerts.append(f"🔴 余额 ¥{balance:.2f} < ¥{TH['balance_low']} → 暂停非必要工作")
    if cost > 0:
        recent = []
        for i in range(1, len(pts)):
            if pts[i][1] < pts[i - 1][1]:
                recent.append(pts[i - 1][1] - pts[i][1])
        if recent and recent[-1] > TH["session_cost_warn"]:
            alerts.append(f"🟡 最近一次消耗 ¥{recent[-1]:.2f} > ¥{TH['session_cost_warn']} → 拆 agent / 缩短主会话")
    if rev_rows:
        last = max(r.get("date", "") for r in rev_rows)
        try:
            days = (datetime.date.today() - datetime.date.fromisoformat(last)).days
            if days > 30:
                alerts.append(f"🟡 距最近一单已 {days} 天 → 检查流量与档位")
        except Exception:
            pass
    elif cost > 0:
        alerts.append("⚪ 尚无收入（正常，SKU 未上架）")

    out = dict(cost=round(cost, 2), balance=balance, revenue=round(rev, 2),
               net=round(net, 2), orders=orders, roi=round(roi, 2) if roi else None,
               cost_per_order=round(per_order, 2) if per_order else None,
               cost_per_lead=round(per_list, 2) if per_list else None,
               maillist=n_list, posts=n_posts, impressions=int(imp), alerts=alerts)

    if a.csv:
        print(json.dumps(out, ensure_ascii=False))
        return

    if not a.quiet:
        L = "─" * 60
        print(L); print("第七境 · 投入产出简报 ·", datetime.date.today()); print(L)
        print(f"  💸 token 成本累计   ¥{cost:>8.2f}")
        print(f"  💰 当前余额         ¥{(balance or 0):>8.2f}")
        print(f"  📈 收入累计         ¥{rev:>8.2f}   （实收 ¥{net:.2f}，{orders} 单）")
        print(f"  📬 邮件名单         {n_list:>8d} 人")
        print(f"  📝 已发布内容       {n_posts:>8d} 条")
        print()
        if orders:
            print(f"  ROI（现金口径）      {roi:>8.2f} 倍")
            print(f"  每单 token 成本      ¥{per_order:>8.2f}")
        else:
            print("  ROI                   —（还没有收入）")
            if n_list:
                print(f"  每个名单的获取成本   ¥{per_list:>8.2f}")
        if alerts:
            print(); print("  ── 触发告警 ──")
            for x in alerts:
                print("   ", x)
        print(L)

    # ── HTML ──
    try:
        spark = ""
        if len(pts) > 1:
            vals = [p[1] for p in pts]
            lo, hi = min(vals), max(vals)
            W, H = 560, 90
            step = W / max(1, len(vals) - 1)
            d = " ".join(f"{i*step:.0f},{H-((v-lo)/(hi-lo or 1))*(H-8)-4:.1f}"
                         for i, v in enumerate(vals))
            spark = (f'<svg width="{W}" height="{H}" style="background:#fafafa;border:1px solid #eee">'
                     f'<polyline points="{d}" fill="none" stroke="#b03826" stroke-width="2"/></svg>')
        html = f"""<!doctype html><meta charset="utf-8"><title>第七境 · ROI 看板</title>
<style>body{{font-family:-apple-system,"PingFang SC",sans-serif;max-width:760px;margin:40px auto;color:#222;line-height:1.7}}
h1{{font-size:20px}} .k{{display:inline-block;min-width:200px}} .v{{font-weight:600}}
.tag{{background:#f5f2ec;padding:2px 8px;border-radius:4px;font-size:13px}}
.alert{{background:#fff4f2;border-left:3px solid #b03826;padding:8px 12px;margin:6px 0}}</style>
<h1>第七境 · 投入产出看板</h1>
<p class="tag">生成于 {datetime.datetime.now():%Y-%m-%d %H:%M} · 标定单价 ¥0.0553 / 1M token</p>
<p><span class="k">Token 成本累计</span><span class="v">¥{cost:.2f}</span></p>
<p><span class="k">当前余额</span><span class="v">¥{(balance or 0):.2f}</span></p>
<p><span class="k">收入累计</span><span class="v">¥{rev:.2f}</span>（实收 ¥{net:.2f} · {orders} 单）</p>
<p><span class="k">邮件名单</span><span class="v">{n_list}</span> 人</p>
<p><span class="k">ROI（现金口径）</span><span class="v">{'%.2f 倍'%roi if roi else '—'}</span></p>
<h2 style="font-size:15px;margin-top:28px">余额曲线</h2>{spark or '<p>无数据</p>'}
<h2 style="font-size:15px;margin-top:28px">告警</h2>
{''.join(f'<div class="alert">{x}</div>' for x in alerts) or '<p>无</p>'}
<p style="color:#888;font-size:12px;margin-top:32px">规则见 11-运营/成本管控/投入产出比-模型与策略-2026-10-02.md</p>
"""
        os.makedirs(REPORTS, exist_ok=True)
        rp = os.path.join(REPORTS, "ROI看板.html")
        open(rp, "w", encoding="utf-8").write(html)
        if not a.quiet:
            print(f"  看板已刷新：{rp}")
    except Exception as e:
        print(f"  ! HTML 生成失败：{e}", file=sys.stderr)


if __name__ == "__main__":
    main()
