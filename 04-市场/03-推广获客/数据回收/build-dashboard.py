#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""S1 冷启动看板（HTML，图形化）。

用法：python3 build-dashboard.py
输出：同目录 看板.html

═══ 2026-10-11 重写说明（重要，别倒退） ═══
旧版是 **海外线 + 邮箱 KPI** 的产物：三张卡是 Instagram / Pinterest / Reddit，
主 KPI 是「邮箱 100 个」。转到国内后这套完全失效——
用户记了小红书的数据，看板上**一张卡都显示不出来**。
本次改为国内实际在跑的三平台：小红书（主）/ 抖音（同步）/ B站（中视频）。

另注意一个已被论证的结构性问题（见 04-市场/03-推广获客/推广效果观测与下一步判据-2026-10-11.md）：
小红书不允许往站外导流，所以「站点访次」这个旧主 KPI **在小红书上测不到**。
S1 阶段因此改看平台内指标：曝光 / 赞 / 藏 / 评，其中**收藏率**是壁纸类内容最硬的指标。
"""
import csv, os, datetime, html

DIR = os.path.dirname(os.path.abspath(__file__))
CSV = os.path.join(DIR, "发布数据.csv")
OUT = os.path.join(DIR, "看板.html")

# ── 判据阈值 ───────────────────────────────────────────────
# ⚠️ 全部是「待校准的预设值」，不是经验证的标准。
# 我们还没有任何一条真实数据，第 1 条发出后的前 4 条是用来**建立基线**的，
# 不是用来判定成败的。基线拿到后回头改这里的数字。
#
# 唯一的硬判据只有一条：曝光是否低到异常 —— 那说明不是内容问题，
# 是账号/违规/图片重复的系统性故障，要停下排查而不是继续发帖。
IMPRESSIONS_FLOOR = 100   # 曝光低于此 → 疑似限流或账号异常，先排查
SAVE_RATE_LINE = 0.03     # 收藏/曝光 ≥3% 视为「内容被认可」（壁纸类）
PLATFORMS = [
    # key, 显示名, 别名（小写匹配）, 主指标
    ("xhs", "小红书（主）", ["小红书", "xhs", "rednote", "red"], "曝光"),
    ("dy", "抖音（同步）", ["抖音", "douyin", "dy"], "播放"),
    ("bili", "B站（中视频）", ["b站", "bili", "bilibili", "哔哩"], "播放"),
]

rows = []
if os.path.exists(CSV):
    with open(CSV, encoding="utf-8") as f:
        for r in csv.DictReader(f):
            if not r.get("date"):
                continue

            def num(k):
                v = (r.get(k) or "").strip()
                return int(float(v)) if v.replace(".", "").isdigit() else 0

            rows.append({
                "date": r["date"].strip(),
                "platform": (r.get("platform") or "").strip(),
                "asset": (r.get("asset") or "").strip(),
                "impressions": num("impressions"), "likes": num("likes"),
                "saves": num("saves"), "comments": num("comments"),
                "clicks": num("clicks"), "emails": num("emails"),
                "note": (r.get("note") or "").strip(),
            })

today = datetime.date.today()
first = min([datetime.date.fromisoformat(r["date"]) for r in rows], default=None)
day_n = (today - first).days + 1 if first else 0
total_emails = sum(r["emails"] for r in rows)
total_impr = sum(r["impressions"] for r in rows)


def plat_of(aliases):
    low = [(r, r["platform"].lower()) for r in rows]
    return [r for r, p in low if any(a in p for a in aliases)]


def verdict_of(rs, main_label):
    """按平台给出状态。

    诚实版：数据不够就明说「数据不足」，绝不假装判定。
    只有「曝光异常低」这一条会直接判「需排查」——那是故障信号不是成败信号。
    """
    if not rs:
        return ("未发布", "#8b8b8b", "⬜")
    # 只拿「已发布至少满一天」的记录判断：当天发的流量池还没跑完，判低是冤枉它
    matured = [r for r in rs if datetime.date.fromisoformat(r["date"]) < today]
    if not matured:
        return ("今日发布·待观察", "#9a6700", "🟡")
    best_impr = max(r["impressions"] for r in matured)
    if best_impr == 0:
        return ("待填曝光", "#9a6700", "🟡")
    if best_impr < IMPRESSIONS_FLOOR:
        return (f"曝光偏低·需排查（最好 {best_impr}）", "#b3592b", "🔴")
    # 有真实曝光了
    tot_impr = sum(r["impressions"] for r in rs)
    tot_save = sum(r["saves"] for r in rs)
    rate = tot_save / tot_impr if tot_impr else 0
    if rate >= SAVE_RATE_LINE:
        return (f"收藏率 {rate:.1%} ≥ {SAVE_RATE_LINE:.0%}", "#1a7f37", "✅")
    return ("基线观测中", "#9a6700", "🟡")


def card(title, main_label, rs, vtuple):
    txt, color, icon = vtuple
    tot_impr = sum(r["impressions"] for r in rs)
    tot_save = sum(r["saves"] for r in rs)
    tot_like = sum(r["likes"] for r in rs)
    tot_cmt = sum(r["comments"] for r in rs)
    rate = (tot_save / tot_impr) if tot_impr else 0
    li = (
        f"<div class='kv'><span>{main_label}</span><b>{tot_impr}</b></div>"
        f"<div class='kv'><span>赞</span><b>{tot_like}</b></div>"
        f"<div class='kv'><span>收藏</span><b>{tot_save}</b></div>"
        f"<div class='kv'><span>评论</span><b>{tot_cmt}</b></div>"
        f"<div class='kv'><span>收藏率</span><b>{rate:.1%}</b></div>"
        f"<div class='kv'><span>已发</span><b>{len(rs)}</b></div>"
    )
    return f"""<div class="card">
      <div class="chead"><h3>{html.escape(title)}</h3>
      <span class="tag" style="background:{color}1a;color:{color}">{icon} {html.escape(txt)}</span></div>
      <div class="kvs">{li}</div></div>"""


cards = []
for key, name, aliases, main_label in PLATFORMS:
    rs = plat_of(aliases)
    cards.append(card(name, main_label, rs, verdict_of(rs, main_label)))

known = set()
for _, _, aliases, _ in PLATFORMS:
    for a in aliases:
        known.add(a)
unknown = sorted({r["platform"] for r in rows
                  if not any(a in r["platform"].lower() for a in known)})

# 每日曝光柱形（比邮箱更能反映冷启动是否起量）
by_day = {}
for r in rows:
    by_day[r["date"]] = by_day.get(r["date"], 0) + r["impressions"]
days = sorted(by_day)
max_day = max(by_day.values(), default=1) or 1
bars = "".join(
    f'<div class="barcol"><div class="bar" style="height:{max(2, round(by_day[d] / max_day * 90))}px"></div>'
    f'<div class="barv">{by_day[d]}</div><div class="barl">{d[5:]}</div></div>'
    for d in days) or '<div class="empty">还没有数据 —— 发完就回来记一笔：./log.sh -p 小红书 -a 商-字形演变 -i 320 -l 18 -s 12 -c 2</div>'

state = (f'S1 第 {day_n} 天' if day_n else '未开始')
if not rows:
    lead = "还没有任何发布数据。第一条发出后回填，这里才有意义。"
else:
    lead = f"判据阈值目前是预设值，前 4 条用来建立基线，不用来断成败。"

unknown_html = ""
if unknown:
    unknown_html = (f"<p class='note'>⚠️ 明细里有尚未归类的平台：{html.escape('、'.join(unknown))}"
                    f" —— 请核对大小写，或在脚本 <code>PLATFORMS</code> 里补别名。</p>")

pane = f"""<!doctype html><html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>第七境 · S1 冷启动看板</title><style>
:root{{--bg:#faf9f7;--card:#fff;--ink:#20201e;--sub:#6b6b66;--line:#e6e3dd;--gold:#8a6d3b;}}
*{{box-sizing:border-box}}
body{{margin:0;padding:28px 20px 48px;background:var(--bg);color:var(--ink);
 font:15px/1.6 -apple-system,"PingFang SC","Noto Sans CJK SC",sans-serif;}}
.wrap{{max-width:880px;margin:0 auto}}
h1{{font-size:22px;margin:0 0 4px}} .lead{{color:var(--sub);font-size:13px;margin-bottom:22px}}
.kpi{{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:20px 22px;margin-bottom:18px}}
.kpi .big{{font-size:38px;font-weight:600;letter-spacing:-1px}}
.kpi .big small{{font-size:15px;color:var(--sub);font-weight:400}}
.meta{{color:var(--sub);font-size:12px}}
.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(250px,1fr));gap:14px;margin-bottom:18px}}
.card{{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:16px 18px}}
.chead{{display:flex;align-items:center;justify-content:space-between;gap:8px;margin-bottom:10px}}
.chead h3{{margin:0;font-size:15px}}
.tag{{font-size:12px;padding:3px 9px;border-radius:20px;white-space:nowrap}}
.kvs .kv{{display:flex;justify-content:space-between;padding:5px 0;border-top:1px dashed var(--line);font-size:13px}}
.kvs .kv:first-child{{border-top:0}} .kvs span{{color:var(--sub)}}
.chart{{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:18px 20px;margin-bottom:18px}}
.chart h3{{margin:0 0 14px;font-size:15px}}
.bars{{display:flex;align-items:flex-end;gap:10px;height:130px}}
.barcol{{display:flex;flex-direction:column;align-items:center;justify-content:flex-end;height:130px}}
.bar{{width:34px;background:linear-gradient(180deg,#b08d57,#8a6d3b);border-radius:4px 4px 0 0}}
.barv{{font-size:11px;color:var(--sub);margin-top:4px}} .barl{{font-size:10px;color:#9a978f}}
.empty{{color:var(--sub);font-size:13px;padding:20px 0}}
table{{width:100%;border-collapse:collapse;font-size:13px;background:var(--card);
 border:1px solid var(--line);border-radius:14px;overflow:hidden}}
th,td{{padding:9px 12px;text-align:left;border-bottom:1px solid var(--line)}}
th{{background:#f4f1eb;font-weight:600;font-size:12px;color:var(--sub)}}
tr:last-child td{{border-bottom:0}}
.note{{color:var(--sub);font-size:12px}} .num{{text-align:right;font-variant-numeric:tabular-nums}}
.week{{background:#fff;border:1px solid var(--line);border-left:3px solid var(--gold);
 border-radius:8px;padding:12px 16px;font-size:13px;margin-top:18px}}
.badbox{{background:#fdf3f1;border:1px solid #f0d9d3;border-left:3px solid #b3592b;
 border-radius:8px;padding:12px 16px;font-size:13px;margin-bottom:18px}}
code{{background:#f0ede7;padding:1px 5px;border-radius:4px;font-size:12px}}
</style></head><body><div class="wrap">
<h1>第七境 · S1 冷启动看板</h1>
<div class="lead">{html.escape(lead)}　·　生成于 {today.isoformat()}　·　{state}</div>

<div class="kpi">
  <div class="big">{total_impr} <small>累计曝光</small></div>
  <div class="meta">已发 <b>{len(rows)}</b> 条　·　累计邮箱 {total_emails}</div>
</div>

<div class="badbox"><b>⚠️ 别用这个看板判断「推广有没有效果」</b><br>
小红书不允许往站外导流（笔记、简介都不能放可点链接），所以无论我们在小红书做得多好，
都不会体现为站点访次的增长。看站点流量请用 <code>站点分析/站点看板.html</code>，
但那衡量的是 <b>SEO 与直接访问</b>，不是社交平台推广。<br>
<span class="note">本阶段唯一有意义的社交侧指标，是上面三张卡里的平台内数据。</span></div>

<div class="grid">
  {"".join(cards)}
</div>

<div class="chart"><h3>每日曝光</h3><div class="bars">{bars}</div></div>

<h3 style="font-size:15px;margin:22px 0 10px">发布明细（{len(rows)} 条）</h3>
<table><tr><th>日期</th><th>平台</th><th>内容</th><th class="num">曝光</th><th class="num">赞</th>
<th class="num">藏</th><th class="num">评</th><th class="num">外链</th><th class="num">邮箱</th><th>备注</th></tr>
{"".join(f"<tr><td>{r['date']}</td><td>{html.escape(r['platform'])}</td><td>{html.escape(r['asset'])}</td>"
         f"<td class='num'>{r['impressions']}</td><td class='num'>{r['likes']}</td><td class='num'>{r['saves']}</td>"
         f"<td class='num'>{r['comments']}</td><td class='num'>{r['clicks']}</td><td class='num'><b>{r['emails']}</b></td>"
         f"<td class='note'>{html.escape(r['note'])}</td></tr>" for r in rows)
 or "<tr><td colspan='10' class='note'>暂无 —— 发出第一条后回填</td></tr>"}
</table>
{unknown_html}

<div class="week"><b>记一笔</b>（App 里的数字，30 秒）：<br>
<code>./log.sh -p 小红书 -a 商-字形演变 -i 320 -l 18 -s 12 -c 2</code><br>
<code>./log.sh -p 抖音 -a 商-字形演变 -i 500 -l 20 -s 5 -c 1</code><br>
然后 <code>python3 build-dashboard.py</code> 刷新本页。<br>
<span class="note">判据阈值在脚本顶部 &#40;<code>IMPRESSIONS_FLOOR</code> / <code>SAVE_RATE_LINE</code>&#41;，
前 4 条拿到真实数据后回头校准。</span></div>

</div></body></html>"""

with open(OUT, "w", encoding="utf-8") as f:
    f.write(pane)
print(f"已生成 {OUT}（{len(rows)} 条记录，累计曝光 {total_impr}）")
if not rows:
    print("⚠️ 无任何发布数据：发布数据.csv 目前只有表头。")
