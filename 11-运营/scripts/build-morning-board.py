#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
第七境 · 每日晨检看板生成器

读取本地已有的晨检产物与台账，渲染一份水墨风 HTML 看板：
  - 站点分析  04-市场/03-推广获客/数据回收/站点分析/站点数据.csv
  - DeepSeek  11-运营/data/deepseek-balance.csv
  - 积分预算  11-运营/scripts/credits-budget.py（子进程，零积分）
  - 积分余额  11-运营/积分账本与产能测算.md 最后一条真实快照
  - 百度推送  11-运营/data/baidu-push.csv + baidu-pushed.txt
  - 站点体检  11-运营/data/morning-status.json（晨检写入，可选）
  - 当前待办  .workbuddy/memory/NOW.md

设计原则（与资料库纪律一致）：
  1. 零联网、零积分：所有数据来自本地已有文件，不重复取数。
  2. 数据缺失就写「本次未提供」，绝不编造、绝不沿用旧值冒充当日。
  3. 单一节点覆盖更新，不按天堆积快照。

用法：
  python3 11-运营/scripts/build-morning-board.py              # 只生成本地 HTML
  python3 11-运营/scripts/build-morning-board.py --upload     # 生成后覆盖更新资料库固定节点
"""
import os
import re
import csv
import json
import html
import subprocess
import sys
from datetime import datetime, date

ROOT = "/Users/billyhou/WorkBuddy/2026-09-25-15-56-17"
PY = "/Users/billyhou/.workbuddy/binaries/python/versions/3.13.12/bin/python3"
OUT = os.path.join(ROOT, "11-运营/reports/每日晨检看板.html")
FRAG = os.path.join(ROOT, "11-运营/reports/morning-fragment.html")

# 资料库固定节点：团队空间「第七境」› 00-工作台导航 › 每日晨检看板
BOARD_NODE_ID = "csMhWQGumhu0dSU3swjthz"
SPACE_ID = "vtgKWy99bZoF6oKAIzqfHt"
SKILL = "/Applications/WorkBuddy.app/Contents/Resources/app.asar.unpacked/resources/plugins/workbuddy-builtin/skills/library"

NA = "本次未提供"


def p(*a):
    return os.path.join(ROOT, *a)


def read_csv(path):
    if not os.path.exists(path):
        return []
    with open(path, encoding="utf-8", errors="ignore") as f:
        return list(csv.DictReader(f))


def tail_lines(path, n):
    if not os.path.exists(path):
        return []
    with open(path, encoding="utf-8", errors="ignore") as f:
        return f.read().splitlines()[-n:]


# ---------- 1. 站点分析 ----------
def load_traffic():
    rows = read_csv(p("04-市场/03-推广获客/数据回收/站点分析/站点数据.csv"))
    rows = [r for r in rows if r.get("date")]
    rows.sort(key=lambda r: r["date"])
    if not rows:
        return {"ok": False}
    today, prev = rows[-1], (rows[-2] if len(rows) > 1 else None)
    series = rows[-7:]
    try:
        v = int(float(today.get("visits") or 0))
        vc = int(float(today.get("visits_clean") or 0))
        pv = int(float(prev.get("visits") or 0)) if prev else None
        jump = (round((v - pv) / pv * 100) if pv else None)
    except ValueError:
        v = vc = jump = None
    return {
        "ok": True, "date": today["date"], "visits": v, "clean": vc,
        "bot": today.get("bot_pct"), "top1": today.get("top1_path"),
        "top1v": today.get("top1_visits"), "jump": jump,
        "collected": today.get("collected_at", ""),
        "series": [{"d": r["date"], "v": int(float(r.get("visits_clean") or 0))} for r in series],
        "days": len(rows),
    }


# ---------- 2. DeepSeek ----------
def load_deepseek():
    rows = read_csv(p("11-运营/data/deepseek-balance.csv"))
    rows = [r for r in rows if r.get("date")]
    if not rows:
        return {"ok": False}
    last, prev = rows[-1], (rows[-2] if len(rows) > 1 else None)
    try:
        cur = float(last.get("total") or 0)
        drop = round(cur - float(prev.get("total") or 0), 2) if prev else None
    except ValueError:
        return {"ok": False}
    # 停更检测
    try:
        lag = (date.today() - datetime.strptime(last["date"], "%Y-%m-%d").date()).days
    except ValueError:
        lag = None
    return {"ok": True, "date": last["date"], "time": last.get("time", ""),
            "total": cur, "drop": drop, "lag": lag,
            "granted": float(last.get("granted") or 0),
            "avail": str(last.get("isAvailable")).lower()}


# ---------- 3. 积分预算 ----------
def load_credits():
    out = {"ok": False, "raw": ""}
    try:
        r = subprocess.run([PY, p("11-运营/scripts/credits-budget.py")],
                           capture_output=True, text=True, timeout=90, cwd=ROOT)
        raw = (r.stdout or "").strip()
        out["raw"] = raw
    except Exception as e:
        out["raw"] = f"（调用失败：{e}）"
        return out
    def g(label):
        m = re.search(re.escape(label) + r"\s*[:：]\s*(.+)", raw)
        return m.group(1).strip() if m else NA
    out.update({
        "ok": bool(raw),
        "base": g("今日基线日额"), "dyn": g("今日动态可用"),
        "used": g("本月已用"), "heavy": g("重活池"),
        "buffer": g("缓冲"),
    })
    # 真实余额与跑道：取账本最后一条真实快照
    lines = tail_lines(p("11-运营/积分账本与产能测算.md"), 40)
    bal = None
    for ln in reversed(lines):
        # 数值允许 **791.17** 这种加粗写法 —— 2026-10-09 踩过：加粗后旧正则不认，
        # 于是跳过当天真实值、往前抓到 10-08 的「（未取到）」，看板白显示一天假警报。
        m = re.search(r"\|\s*(\d{4}-\d{2}-\d{2})\s*\|\s*\*{0,2}([\d.]+|（未取到）)\*{0,2}\s*\|", ln)
        if m:
            bal = {"date": m.group(1), "val": m.group(2)}
            break
    out["balance"] = bal
    # 真实周期额度（fetch-credits 口径），若账本里有记
    out["note"] = next((ln.strip() for ln in reversed(lines)
                        if "真实快照" in ln or "cycleTotal" in ln), "")
    return out


# ---------- 4. 百度推送 ----------
def load_baidu():
    pushed = p("11-运营/data/baidu-pushed.txt")
    n = len([l for l in tail_lines(pushed, 9999) if l.strip()])
    rows = read_csv(p("11-运营/data/baidu-push.csv"))
    last = rows[-1] if rows else {}
    return {"count": n, "last": last}


# ---------- 5. 站点体检（晨检写入的 JSON，可选） ----------
def load_status():
    f = p("11-运营/data/morning-status.json")
    if not os.path.exists(f):
        return {}
    try:
        return json.load(open(f, encoding="utf-8"))
    except Exception:
        return {}


# ---------- 6. 当前待办 ----------
def load_now():
    f = p(".workbuddy/memory/NOW.md")
    if not os.path.exists(f):
        return ""
    s = open(f, encoding="utf-8", errors="ignore").read()
    s = re.sub(r"^>.*\n?", "", s, flags=re.M)  # 去掉引用头
    return s.strip()[:1600]


# ---------- 渲染 ----------
# 样式一律以 .mb 为作用域前缀：本看板既要独立成页，也要作为片段内嵌进工作台的 tab，
# 裸的 * {} / body {} / h2 {} 会污染宿主页面。
# 设计变量复用 qj-theme.py（与门户页同一套水墨 token），口径见该文件注释。
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import qj_theme  # noqa: E402
import qj_refresh as qjr  # noqa: E402

CSS = qj_theme.FONTS + qj_theme.tokens(".mb") + """
.mb,.mb *{box-sizing:border-box}
.mb{color:var(--ink);font-family:var(--f-body);line-height:1.9;
 padding:0 0 24px;max-width:960px;margin:0 auto}
.mb img{max-width:100%;height:auto}
.mb header{padding:8px 0 24px;border-bottom:1px solid var(--line);margin-bottom:28px;
 position:relative;overflow:hidden}
.mb header .ghost{position:absolute;right:-10px;top:8px;font-family:var(--f-brush);
 font-size:clamp(90px,18vw,150px);color:rgba(26,26,24,.045);pointer-events:none;line-height:1}
.mb h1{font-family:var(--f-brush);font-size:32px;font-weight:400;letter-spacing:.14em}
.mb .sub{color:var(--ink2);font-size:14px;letter-spacing:.08em;margin-top:8px}
.mb .stamp{display:inline-block;border:1px solid var(--cinnabar);color:var(--cinnabar);
 padding:2px 10px;font-size:12px;letter-spacing:.14em;margin-top:14px}
.mb h2{font-family:var(--f-body);font-size:18px;font-weight:600;letter-spacing:.12em;
 margin:36px 0 16px;padding-left:12px;border-left:3px solid var(--cinnabar)}
.mb .grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(190px,1fr));gap:14px}
.mb .card{background:var(--wash);padding:20px 22px}
.mb .card .k{font-size:12px;color:var(--ink3);letter-spacing:.1em}
.mb .card .v{font-family:var(--f-brush);font-size:32px;line-height:1.3;margin-top:6px}
.mb .card .u{font-family:var(--f-body);font-size:13px;color:var(--ink2);margin-left:3px}
.mb .card .n{font-size:12px;color:var(--ink3);margin-top:6px;line-height:1.7}
.mb table{width:100%;border-collapse:collapse;background:var(--white);font-size:14px}
.mb th,.mb td{padding:9px 12px;text-align:left;border-bottom:1px solid var(--line)}
.mb th{font-size:12px;color:var(--ink3);letter-spacing:.08em;font-weight:500;background:var(--wash)}
.mb .ok{color:var(--ok)}.mb .warn{color:var(--warn)}
.mb .bad{color:var(--cinnabar)}.mb .na{color:var(--na)}
.mb .bars{display:flex;align-items:flex-end;gap:8px;height:88px;margin-top:10px}
.mb .bars .b{flex:1;background:var(--cinnabar);opacity:.72;position:relative}
.mb .bars .b span{position:absolute;bottom:-22px;left:0;right:0;text-align:center;
 font-size:10px;color:var(--ink3)}
.mb .spark{margin-bottom:26px}
.mb pre{background:var(--wash);padding:14px 16px;font-size:12.5px;
 font-family:"SF Mono",Menlo,monospace;color:var(--ink2);overflow-x:auto;white-space:pre-wrap;
 line-height:1.7}
.mb details{background:var(--wash);padding:0 18px;margin-top:12px}
.mb summary{cursor:pointer;padding:14px 0;font-size:14px;letter-spacing:.06em;color:var(--ink2)}
.mb details pre{background:none;padding:0 0 16px}
.mb ul{margin:12px 0 0 22px;font-size:14px;color:var(--ink2);line-height:1.9}
.mb li{margin-bottom:6px}
.mb code{font-family:"SF Mono",Menlo,monospace;font-size:12.5px;color:var(--ink2)}
.mb footer{margin-top:48px;padding-top:22px;border-top:1px solid var(--line);
 font-size:12.5px;color:var(--ink3);letter-spacing:.06em;line-height:1.9}
@media(max-width:600px){.mb h1{font-size:26px}.mb .card .v{font-size:26px}}
""" + qjr.CSS_MB

# 独立成页时的外壳（背景与字号由 body 提供）；内嵌进门户 tab 时不输出。
# 注意 @import 必须排在所有规则之前，否则整条被忽略。
PAGE_SHELL = (qj_theme.FONTS + qj_theme.tokens(":root")
              + "body{background:var(--wash);color:var(--ink);font-family:var(--f-body);"
                "margin:0;padding:0 20px 60px}")


def esc(s):
    return html.escape(str(s))


def card(k, v, u="", n="", cls=""):
    return (f'<div class="card"><div class="k">{esc(k)}</div>'
            f'<div class="v {cls}">{esc(v)}<span class="u">{esc(u)}</span></div>'
            f'<div class="n">{esc(n)}</div></div>')


def build():
    now = datetime.now()
    tr = load_traffic()
    ds = load_deepseek()
    cr = load_credits()
    bd = load_baidu()
    st = load_status()
    nows = load_now()

    # 站点体检
    ssl = st.get("ssl_days")
    http = st.get("http_code")
    jump301 = st.get("http_redirect")
    cf = st.get("cf_proxy")
    indexed = st.get("baidu_indexed")
    bpush = st.get("baidu_push")

    def cls_for(v, good, warnv=None):
        return "ok" if v == good else ("warn" if warnv and v == warnv else "bad")

    parts = []
    # 刷新按钮放在 header 里是刻意的：内嵌进工作台 tab 的片段从 parts[1] 开始，
    # 不含 header，因此不会出现两个按钮（门户自己有一个常驻在 tabbar）。
    parts.append(f'''<header><div class="ghost">晨</div>
<h1>每日晨检 · 看板</h1>
<div class="sub">第七境 · The Seventh Realm　|　{now:%Y 年 %m 月 %d 日}　{now:%H:%M} 生成</div>
<div class="stamp">数据来自本地台账 · 点「刷新数据」重新取数</div>
<div class="qjbar">
      {qjr.button("随时重新取数")}
    </div></header>''')

    # 一、站点健康
    parts.append("<h2>一 · 站点健康</h2><div class='grid'>")
    parts.append(card("首页响应", http or NA, "", st.get("http_note", ""),
                      "ok" if http == "200" else "na"))
    parts.append(card("证书剩余", (f"{ssl} 天" if ssl is not None else NA), "",
                      "", "ok" if (ssl or 0) >= 30 else "bad"))
    parts.append(card("HTTP→HTTPS", jump301 or NA, "", "", "ok" if jump301 in ("301", "308") else "warn"))
    parts.append(card("Cloudflare", cf or NA, "", "", "ok" if cf and "生效" in str(cf) else "warn"))
    parts.append("</div>")

    # 二、站点分析
    parts.append("<h2>二 · 站点流量</h2>")
    if tr.get("ok"):
        jc = "na"
        jt = ""
        if tr["jump"] is not None:
            jt = f"较前一日 {tr['jump']:+d}%"
            jc = "bad" if abs(tr["jump"]) >= 50 else "ok"
        parts.append("<div class='grid'>")
        parts.append(card("访次（{d}）".format(d=tr["date"]), tr["visits"] or NA, "", jt, jc))
        parts.append(card("净访次（去噪）", tr["clean"] or NA, "", "机器人占比 {bt}%".format(bt=tr["bot"])))
        parts.append(card("内容页 Top1", tr["top1"] or NA, "", "{v} 次".format(v=tr["top1v"])))
        parts.append(card("累计采集", "{d} 天".format(d=tr["days"]), "",
                          "采集于 {c}".format(c=tr["collected"])))
        parts.append("</div>")
        s = tr["series"]
        mx = max((x["v"] for x in s), default=1) or 1
        bars = "".join(
            f'<div class="b" style="height:{max(4, round(x["v"] / mx * 100))}%">'
            f'<span>{x["d"][5:]}</span></div>' for x in s)
        parts.append(f'<div class="spark"><div class="k" style="font-size:12px;color:#8a867e;'
                     f'letter-spacing:.1em">近 {len(s)} 日净访次</div><div class="bars">{bars}</div></div>')
    else:
        parts.append(f"<p class='na'>{NA}：未找到站点数据 CSV。</p>")

    # 三、积分
    parts.append("<h2>三 · 积分</h2>")
    if cr.get("ok"):
        parts.append("<div class='grid'>")
        parts.append(card("今日基线日额", cr["base"], "", "工作日 8 / 生产日 20"))
        parts.append(card("今日动态可用", cr["dyn"], "", "硬上限 60"))
        parts.append(card("本月已用", cr["used"], "", ""))
        parts.append(card("重活池", cr["heavy"], "", "每月 ≤2 次 · 单次 ≤45"))
        parts.append("</div>")
        if cr.get("balance"):
            b = cr["balance"]
            val = b["val"]
            stale = ""
            if val and "未取到" not in val:
                try:
                    lag = (date.today() - datetime.strptime(b["date"], "%Y-%m-%d").date()).days
                    if lag >= 1:
                        stale = f"快照 {b['date']}，已过去 {lag} 天"
                except ValueError:
                    pass
            parts.append(card("真实余额（账本）", val, "分", stale or f"快照日期 {b['date']}",
                              "warn" if stale else "ok"))
    else:
        parts.append(f"<p class='na'>{NA}：积分预算脚本未返回。</p>")
    if cr.get("raw"):
        parts.append(f"<details style='margin-top:12px'><summary>积分预算脚本原始输出</summary>"
                     f"<pre>{esc(cr['raw'])}</pre></details>")

    # 四、DeepSeek
    parts.append("<h2>四 · DeepSeek 余额</h2>")
    if ds.get("ok"):
        dc = "ok"
        note = f"较上次 {ds['drop']:+.2f} 元" if ds["drop"] is not None else ""
        if ds["total"] < 20:
            dc = "bad"
            note = "低于 ¥20，建议充值"
        elif ds["drop"] is not None and ds["drop"] <= -5:
            dc = "warn"
        if ds["lag"] is not None and ds["lag"] >= 3:
            dc = "warn"
            note += f"　⚠ 已 {ds['lag']} 天未记账，launchd 可能失效"
        parts.append("<div class='grid'>")
        parts.append(card("余额", f"¥{ds['total']:.2f}", "", note, dc))
        parts.append(card("记账时点", f"{ds['date']} {ds['time']}", "", "每日 21:00 自动记账"))
        parts.append(card("赠送余额", f"¥{ds['granted']:.2f}", "", "赠送部分有有效期" if ds["granted"] else "无"))
        parts.append(card("账户可用", "是" if ds["avail"] == "true" else "否", "", "",
                          "ok" if ds["avail"] == "true" else "bad"))
        parts.append("</div>")
    else:
        parts.append(f"<p class='na'>{NA}</p>")

    # 五、SEO 与推送
    parts.append("<h2>五 · SEO 与推送</h2><div class='grid'>")
    parts.append(card("百度收录", indexed or NA, "", ""))
    parts.append(card("已推送 URL", bd["count"], "条", "累计去重"))
    parts.append(card("本次推送", bpush or (bd["last"].get("result") if bd.get("last") else NA), "", ""))
    parts.append(card("推送额度", "10", "条/日", "API 提交"))
    parts.append("</div>")

    # 六、当前待办
    if nows:
        parts.append("<h2>六 · 当前待办（NOW.md）</h2>")
        parts.append(f"<details open><summary>展开 / 收起</summary><pre>{esc(nows)}</pre></details>")

    # 七、口径说明
    parts.append('''<h2>七 · 口径与纪律</h2><ul>
<li>本页数据<b>全部来自本地台账</b>，生成过程不联网、不消耗积分；站点体检项由晨检写入 <code>morning-status.json</code>，缺失即显示「本次未提供」。</li>
<li>积分「预算日额」是自定口径（每月 500），「真实余额」是平台账本快照，二者不同量级，<b>不可混用</b>。</li>
<li>本页每天<b>覆盖更新同一节点</b>，不按天堆积；历史曲线请以本地 <code>站点数据.csv</code> 为准。</li>
<li>真源始终在本地。本页是消费端只读副本，要改数据请改本地后重新生成。</li></ul>''')

    parts.append(f'''<footer>第七境 · 一个个人创作者　|　生成于 {now:%Y-%m-%d %H:%M}
　|　数据源：站点数据.csv · deepseek-balance.csv · credits-budget.py · 积分账本 · NOW.md</footer>''')

    body = "".join(parts)
    doc = ("<!DOCTYPE html><html lang='zh-CN'><head><meta charset='utf-8'>"
           "<meta name='viewport' content='width=device-width,initial-scale=1'>"
           "<title>第七境 · 每日晨检看板</title><style>" + PAGE_SHELL + CSS
           + "</style></head><body>"
           '<div class="mb">' + body + "</div>"
           "<script>" + qjr.js("mb") + "</script></body></html>")
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        f.write(doc)
    # 供工作台「今日晨检」tab 内嵌的片段（自带作用域化样式）。
    # 片段**不输出 header**：宿主 tab 已经有自己的标题与幽灵字，否则会重复两遍大标题。
    with open(FRAG, "w", encoding="utf-8") as f:
        f.write("<style>" + CSS + "</style>\n"
                + '<div class="mb">' + "".join(parts[1:]) + "</div>")
    return OUT


def upload(path):
    cmd = ["python3", f"{SKILL}/page/import_html.py", path,
           "--space-id", SPACE_ID, "--node-block-id", BOARD_NODE_ID]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
    out = (r.stdout or "") + (r.stderr or "")
    # ⚠️ import_html.py 业务失败时同样 exit 0，只输出一行 {"error":"..."}。
    # 只看 returncode 会把失败当成成功 —— 2026-10-11 就踩了这个坑：
    # 刷新日志写着「同步 ok」，云端页面却一直停在旧版本上，排查时完全没线索。
    # 所以这里必须检查输出内容，并以非零码退出，让 refresh-server 记下 FAIL。
    if r.returncode != 0 or '"error"' in out.lower():
        print("❌ 同步云端失败：" + out.strip()[:400], file=sys.stderr)
        return None
    return out


if __name__ == "__main__":
    out = build()
    print(f"已生成：{out}（{os.path.getsize(out)/1024:.1f} KB）")
    if "--upload" in sys.argv:
        # 上传前自检：不得残留第三方图片链接
        s = open(out, encoding="utf-8").read()
        bad = re.findall(r'(?:src|srcset)\s*=\s*["\'](?:https?:)?//[^"\']+', s)
        bad = [b for b in bad if "workbuddy" not in b and "codebuddy" not in b]
        if bad:
            print("❌ 存在第三方图片链接，已中止上传：", bad[:3])
            sys.exit(1)
        r1 = upload(out)
        if r1:
            print(r1.strip())
        # 顺带重建工作台：它的「晨检详报」tab 内嵌本看板片段，否则 tab 里永远是旧数据。
        # ⚠️ 无论上面上传成功与否都要跑 —— 上传失败不该连本地页面一起停在旧数据上。
        wb = os.path.join(ROOT, "11-运营/scripts/build-workbench.py")
        r2 = 0
        if os.path.exists(wb):
            r = subprocess.run([PY, wb, "--upload"], capture_output=True,
                               text=True, timeout=300, cwd=ROOT)
            print("工作台：" + (r.stdout or r.stderr).strip())
            r2 = r.returncode
        # 上传失败必须让调用方知道（非零码 ⇒ refresh-server 记 FAIL + 写原因）
        if r1 is None or r2 != 0:
            sys.exit(1)
