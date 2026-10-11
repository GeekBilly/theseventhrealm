#!/usr/bin/env python3
# 读取余额账本 CSV → 生成自包含 HTML 图表（纯内联 SVG，无外部依赖）
# 由 deepseek-balance-log.sh 在每次记账后自动调用，零成本。
import csv, os, datetime

BASE = "/Users/billyhou/WorkBuddy/2026-09-25-15-56-17"
CSV_PATH = BASE + "/11-运营/data/deepseek-balance.csv"
OUT_PATH = BASE + "/11-运营/reports/DeepSeek-余额曲线.html"

W, H = 880, 300
PAD_L, PAD_R, PAD_T, PAD_B = 60, 24, 28, 46


def load():
    rows = []
    if not os.path.exists(CSV_PATH):
        return rows
    with open(CSV_PATH, encoding="utf-8") as f:
        for r in csv.DictReader(f):
            try:
                rows.append({
                    "date": r["date"], "time": r["time"],
                    "total": float(r["total"]),
                    "granted": float(r["granted"] or 0),
                    "toppedUp": float(r["toppedUp"] or 0),
                    "avail": str(r["isAvailable"]),
                })
            except Exception:
                continue
    return rows


def by_day(rows):
    d = {}
    for r in rows:
        d[r["date"]] = r
    return [(k, d[k]) for k in sorted(d)]


def fmt(v):
    return ("%.2f" % v).rstrip("0").rstrip(".")


def line_chart(pts):
    """余额折线图"""
    n = len(pts)
    if n == 0:
        return '<p class="empty">暂无数据</p>'
    vals = [v for _, v in pts]
    vmin, vmax = min(vals), max(vals)
    if vmax - vmin < 1e-9:
        vmin, vmax = vmin - 1, vmax + 1
    span = vmax - vmin
    vmin -= span * 0.15
    vmax += span * 0.15

    def X(i):
        if n == 1:
            return PAD_L + (W - PAD_L - PAD_R) / 2
        return PAD_L + (W - PAD_L - PAD_R) * i / (n - 1)

    def Y(v):
        return PAD_T + (H - PAD_T - PAD_B) * (vmax - v) / (vmax - vmin)

    s = ['<svg viewBox="0 0 %d %d" class="chart" role="img">' % (W, H)]
    # 网格与 Y 轴刻度
    for k in range(5):
        v = vmin + (vmax - vmin) * k / 4
        y = Y(v)
        s.append('<line x1="%d" y1="%.1f" x2="%d" y2="%.1f" class="grid"/>' % (PAD_L, y, W - PAD_R, y))
        s.append('<text x="%d" y="%.1f" class="ytick">%.1f</text>' % (PAD_L - 8, y + 4, v))
    s.append('<line x1="%d" y1="%d" x2="%d" y2="%d" class="axis"/>' % (PAD_L, PAD_T, PAD_L, H - PAD_B))
    s.append('<line x1="%d" y1="%d" x2="%d" y2="%d" class="axis"/>' % (PAD_L, H - PAD_B, W - PAD_R, H - PAD_B))

    if n == 1:
        x, y = X(0), Y(vals[0])
        s.append('<circle cx="%.1f" cy="%.1f" r="6" class="dot"/>' % (x, y))
        s.append('<text x="%.1f" y="%.1f" class="vlabel">¥%s</text>' % (x, y - 14, fmt(vals[0])))
    else:
        d = " ".join("%.1f,%.1f" % (X(i), Y(v)) for i, (_, v) in enumerate(pts))
        s.append('<polyline points="%s" class="line"/>' % d)
        for i, (_, v) in enumerate(pts):
            s.append('<circle cx="%.1f" cy="%.1f" r="4.5" class="dot"/>' % (X(i), Y(v)))
        # 只标首末与极值，避免拥挤
        for i in {0, n - 1}:
            s.append('<text x="%.1f" y="%.1f" class="vlabel">¥%s</text>' % (X(i), Y(pts[i][1]) - 12, fmt(pts[i][1])))

    # X 轴标签（最多 7 个）
    step = max(1, (n + 6) // 7)
    for i in range(0, n, step):
        lab = pts[i][0][5:]
        s.append('<text x="%.1f" y="%d" class="xtick">%s</text>' % (X(i), H - PAD_B + 20, lab))
    if (n - 1) % step != 0:
        s.append('<text x="%.1f" y="%d" class="xtick">%s</text>' % (X(n - 1), H - PAD_B + 20, pts[-1][0][5:]))
    s.append("</svg>")
    return "".join(s)


def bar_chart(daily):
    """每日变化柱形图（正=充值，负=消耗）"""
    items = [(d, r["total"] - prev) for (d, r), prev in
             zip(daily[1:], [x[1]["total"] for x in daily[:-1]])]
    if not items:
        return '<p class="empty">需要至少两天数据才能显示每日变化</p>'
    vals = [v for _, v in items]
    m = max(abs(v) for v in vals) or 1
    bw = (W - PAD_L - PAD_R) / len(items)
    zero = PAD_T + (H - PAD_T - PAD_B) / 2
    half = (H - PAD_T - PAD_B) / 2 - 10

    s = ['<svg viewBox="0 0 %d %d" class="chart" role="img">' % (W, H)]
    s.append('<line x1="%d" y1="%.1f" x2="%d" y2="%.1f" class="axis"/>' % (PAD_L, zero, W - PAD_R, zero))
    for i, (d, v) in enumerate(items):
        h = abs(v) / m * half
        x = PAD_L + bw * i + bw * 0.25
        w = bw * 0.5
        # 中国习惯：消耗(负)用绿，充值(正)用红
        cls = "bar-down" if v < 0 else ("bar-up" if v > 0 else "bar-flat")
        if v == 0:
            h = 2
            s.append('<rect x="%.1f" y="%.1f" width="%.1f" height="2" class="%s"/>' % (x, zero - 2, w, cls))
        elif v < 0:
            s.append('<rect x="%.1f" y="%.1f" width="%.1f" height="%.1f" class="%s"/>' % (x, zero, w, h, cls))
        else:
            s.append('<rect x="%.1f" y="%.1f" width="%.1f" height="%.1f" class="%s"/>' % (x, zero - h, w, h, cls))
        if abs(v) > 1e-9:
            ty = zero + h + 14 if v < 0 else zero - h - 6
            s.append('<text x="%.1f" y="%.1f" class="vlabel sm">%s%s</text>'
                     % (x + w / 2, ty, "-" if v < 0 else "+", fmt(abs(v))))
        s.append('<text x="%.1f" y="%d" class="xtick">%s</text>' % (x + w / 2, H - PAD_B + 20, d[5:]))
    s.append("</svg>")
    return "".join(s)


CSS = """
:root{--ink:#2b2b2b;--sub:#6b6b6b;--line:#e3ded6;--paper:#fbfaf7;--red:#b23a2e;--green:#2f7a4f;--blue:#3b6ea5}
*{box-sizing:border-box}
body{margin:0;padding:28px;background:var(--paper);color:var(--ink);
 font:14px/1.6 -apple-system,"PingFang SC","Helvetica Neue",sans-serif}
h1{margin:0 0 4px;font-size:20px;font-weight:600;letter-spacing:.5px}
.meta{color:var(--sub);font-size:12px;margin-bottom:20px}
.kpis{display:flex;gap:14px;flex-wrap:wrap;margin-bottom:24px}
.kpi{background:#fff;border:1px solid var(--line);border-radius:8px;padding:14px 18px;min-width:132px}
.kpi .k{font-size:12px;color:var(--sub)}
.kpi .v{font-size:22px;font-weight:600;margin-top:4px}
.kpi .v.warn{color:var(--red)}
h2{font-size:15px;font-weight:600;margin:26px 0 10px;padding-left:9px;border-left:3px solid var(--red)}
.chart{width:100%;height:auto;background:#fff;border:1px solid var(--line);border-radius:8px}
.grid{stroke:var(--line);stroke-width:1}
.axis{stroke:#c9c2b6;stroke-width:1}
.line{fill:none;stroke:var(--blue);stroke-width:2.2;stroke-linejoin:round}
.dot{fill:var(--blue)}
.bar-down{fill:var(--green)} .bar-up{fill:var(--red)} .bar-flat{fill:#c9c2b6}
text{font-size:11px;fill:var(--sub)}
.ytick{text-anchor:end} .xtick{text-anchor:middle}
.vlabel{text-anchor:middle;fill:var(--ink);font-size:12px;font-weight:600}
.vlabel.sm{font-size:10px;font-weight:500}
table{border-collapse:collapse;width:100%;background:#fff;border:1px solid var(--line);border-radius:8px;overflow:hidden}
th,td{padding:8px 12px;text-align:left;border-bottom:1px solid var(--line);font-size:13px}
th{background:#f4f1ec;font-weight:600} tr:last-child td{border-bottom:none}
.empty{color:var(--sub);padding:16px;background:#fff;border:1px solid var(--line);border-radius:8px}
.foot{color:var(--sub);font-size:12px;margin-top:18px}
"""


def main():
    rows = load()
    daily = by_day(rows)
    cur = daily[-1][1] if daily else None
    prev_total = daily[-2][1]["total"] if len(daily) >= 2 else None
    delta = (cur["total"] - prev_total) if (cur and prev_total is not None) else None
    low = cur["total"] < 20 if cur else False

    kpi = []
    if cur:
        kpi.append(("当前余额", "¥" + fmt(cur["total"]), low))
        kpi.append(("较上一天", ("—" if delta is None else ("%s¥%s" % ("-" if delta < 0 else "+", fmt(abs(delta))))), False))
        kpi.append(("充值余额", "¥" + fmt(cur["toppedUp"]), False))
        kpi.append(("赠送余额", "¥" + fmt(cur["granted"]), False))
        kpi.append(("记账天数", "%d 天" % len(daily), False))

    kp = "".join('<div class="kpi"><div class="k">%s</div><div class="v%s">%s</div></div>'
                 % (k, " warn" if w else "", v) for k, v, w in kpi)

    recent = list(reversed(rows))[:14]
    tb = "".join("<tr><td>%s %s</td><td>¥%s</td><td>¥%s</td><td>%s</td></tr>"
                 % (r["date"], r["time"], fmt(r["total"]), fmt(r["granted"]), r["avail"])
                 for r in recent)

    warn = ""
    if cur and low:
        warn = '<p class="empty" style="border-color:var(--red);color:var(--red)">余额低于 ¥20，建议尽快充值。</p>'

    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    doc = """<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>DeepSeek 余额曲线</title><style>%s</style></head>
<body>
<h1>DeepSeek 余额曲线</h1>
<div class="meta">更新于 %s · 共 %d 条记录 · 数据源 11-运营/data/deepseek-balance.csv</div>
%s
<div class="kpis">%s</div>
%s
<h2>余额走势</h2>%s
<h2>每日变化</h2>%s
<h2>最近记录</h2>
<table><thead><tr><th>时间</th><th>余额</th><th>赠送</th><th>可用</th></tr></thead><tbody>%s</tbody></table>
<div class="foot">每天 21:00 由系统定时任务自动记账并刷新本页，不消耗 AI 积分。</div>
</body></html>
""" % (CSS, now, len(rows), warn, kp,
       "", line_chart([(d, r["total"]) for d, r in daily]), bar_chart(daily), tb)

    os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        f.write(doc)
    print("chart written: %s (%d rows)" % (OUT_PATH, len(rows)))


if __name__ == "__main__":
    main()
