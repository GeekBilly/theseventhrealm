#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
第七境 · Cloudflare 站点分析采集与看板

【重要背景 · 2026-09-30 实测】
  1. Analytics Engine SQL API（/analytics_engine/sql）当前对本站返回 403
     "Authorization error"，即便 Token 有 Account Analytics:Read 也一样；
     Cloudflare 社区 2026-09-08 有同类报告，连后台 Studio 都 403 → Cloudflare 侧问题。
     故本脚本不走 SQL API，改用 **GraphQL Analytics API**。
  2. Web Analytics（无 Cookie 那个）**不在 GraphQL schema 里**（已全量 introspect
     2045 个类型确认），只有 RUM（Browser Insights，另一个产品）。
     所以本脚本取的是 **Zone Analytics**：
     - 优点：有 visits（真实访次，按 IP + 30 分钟不活动去重）、页面/国家/设备维度
     - 缺点：包含爬虫；免费版不给 clientRefererHost / botManagementDecision
  3. **数据只能回溯约 3-4 天**（9-27 之前查不到任何数据）。
     → 必须每日采集落盘，否则历史永久丢失。本脚本每次重采最近 4 天并按日期 upsert。

用法：
  python3 cf-analytics.py collect     # 采集落盘（并入每日晨检）
  python3 cf-analytics.py report      # 生成图形化看板 站点看板.html
  python3 cf-analytics.py all         # 采集 + 出看板
  python3 cf-analytics.py raw "<GQL>" # 任意 GraphQL 查询（调试用）

凭据：macOS 钥匙串，服务名 cf-web-analytics，账号 theseventhrealm（不落盘、不进 git）
  security add-generic-password -a theseventhrealm -s cf-web-analytics -U -w "<API Token>"
"""
import json
import os
import subprocess
import sys
from datetime import datetime, timedelta, timezone

ACCOUNT_ID = "ca77a7e079201e70fc6496175993d976"
KEYCHAIN = ("cf-web-analytics", "theseventhrealm")
GQL_URL = "https://api.cloudflare.com/client/v4/graphql"

BASE = "/Users/billyhou/WorkBuddy/2026-09-25-15-56-17"
OUT_DIR = os.path.join(BASE, "04-市场/03-推广获客/数据回收/站点分析")
CSV_PATH = os.path.join(OUT_DIR, "站点数据.csv")
HTML_PATH = os.path.join(OUT_DIR, "站点看板.html")

# 回溯窗口：实测只有 3-4 天，多留 1 天余量
BACKFILL_DAYS = 4

# 爬虫/系统路径规则（命中即不计入「真实访次」）
# 说明：免费版拿不到 botManagementDecision，只能按路径过滤。
# 撞库扫描（/wp-login.php 单页 1721 次 > 首页 1037 次）是本站最大的噪声源。
BOT_PATH_PATTERNS = [
    "wp-login", "wp-admin", "xmlrpc", "wp-cron", "wp-includes", "wp-config",
    "wp-json", "admin-ajax", "setup-config", "?author=", "login",
    "favicon.ico", ".well-known", ".env", ".git",
]
# 站上所有真实内容页都是 WordPress 固定链接（/5000years/shang/ 这种，无扩展名），
# 故凡带脚本扩展名的请求一律不是人：撞库扫描最爱伪装成 .php / .xml
BOT_EXT = (".php", ".xml", ".ico", ".txt", ".env", ".asp", ".aspx", ".cgi",
           ".bak", ".sql", ".json", ".js", ".css", ".map")
BOT_PATH_PREFIX = ("//", "/wp-", "/wordpress", "/wp1", "/wp2", "/cms", "/2019")


def get_token():
    r = subprocess.run(
        ["security", "find-generic-password", "-a", KEYCHAIN[1], "-s", KEYCHAIN[0], "-w"],
        capture_output=True, text=True)
    return r.stdout.strip()


def gql(query, token):
    r = subprocess.run(
        ["curl", "-s", GQL_URL,
         "-H", "Authorization: Bearer %s" % token,
         "-H", "Content-Type: application/json",
         "--data", json.dumps({"query": query})],
        capture_output=True, text=True)
    try:
        return json.loads(r.stdout)
    except Exception:
        return {"errors": [{"message": "非 JSON 响应：%s" % r.stdout[:200]}]}


def fetch(dims, token, days=BACKFILL_DAYS, limit=200, order="sum_visits_DESC"):
    """取 html 请求的分组数据。"""
    start = (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%dT00:00:00Z")
    filt = 'datetime_geq:"%s", edgeResponseContentTypeName:"html"' % start
    q = ('{viewer{accounts(filter:{accountTag:"%s"}){'
         'httpRequestsAdaptiveGroups(limit:%d,filter:{%s},orderBy:[%s])'
         '{count sum{visits} dimensions{%s}}}}}') % (ACCOUNT_ID, limit, filt, order, dims)
    d = gql(q, token)
    if d.get("errors"):
        raise RuntimeError(d["errors"][0]["message"][:200])
    return d["data"]["viewer"]["accounts"][0]["httpRequestsAdaptiveGroups"]


def is_bot_path(path):
    p = (path or "").lower()
    for pat in BOT_PATH_PATTERNS:
        if pat in p:
            return True
    if p.endswith(BOT_EXT):
        return True
    return p.startswith(BOT_PATH_PREFIX)


def collect():
    token = get_token()
    if not token:
        print("✗ 钥匙串里没有 API Token。\n"
              "  security add-generic-password -a %s -s %s -U -w \"<Token>\"" % (KEYCHAIN[1], KEYCHAIN[0]))
        return 1
    os.makedirs(OUT_DIR, exist_ok=True)

    print("[1/4] 每日请求与访次 …")
    try:
        # 双维度（date × 维度）逐日精确聚合，避免用全局比例估算
        daily = fetch("date", token, limit=60, order="date_ASC")
        by_date_path = fetch("date clientRequestPath", token, limit=1000)
        by_date_dev = fetch("date clientDeviceType", token, limit=200)
        by_date_cn = fetch("date clientCountryName", token, limit=500)
    except RuntimeError as e:
        print("✗ 取数失败：%s" % e)
        return 1

    # 逐日拆分：真实内容页 vs 爬虫/系统
    daily_rows, clean_pages_all, bot_pages_all = {}, {}, {}
    for g in by_date_path:
        dt = g["dimensions"]["date"]
        path = g["dimensions"]["clientRequestPath"]
        v = g["sum"]["visits"]
        d = daily_rows.setdefault(dt, {"requests": 0, "visits": 0, "visits_clean": 0, "pages": {}})
        if is_bot_path(path):
            bot_pages_all[path] = bot_pages_all.get(path, 0) + v
        else:
            clean_pages_all[path] = clean_pages_all.get(path, 0) + v
            d["visits_clean"] += v
            d["pages"][path] = d["pages"].get(path, 0) + v
    for g in daily:
        dt = g["dimensions"]["date"]
        d = daily_rows.setdefault(dt, {"requests": 0, "visits": 0, "visits_clean": 0, "pages": {}})
        d["requests"] = g["count"]
        d["visits"] = g["sum"]["visits"]

    dev_by_date, cn_by_date = {}, {}
    for g in by_date_dev:
        dev_by_date.setdefault(g["dimensions"]["date"], {})[g["dimensions"]["clientDeviceType"]] = g["sum"]["visits"]
    for g in by_date_cn:
        cn_by_date.setdefault(g["dimensions"]["date"], []).append(
            (g["dimensions"]["clientCountryName"], g["sum"]["visits"]))

    clean_visits = sum(clean_pages_all.values())
    bot_visits = sum(bot_pages_all.values())
    total_visits = clean_visits + bot_visits
    ratio = (clean_visits / total_visits) if total_visits else 0

    def top_pages(dt, n=2):
        # daily_rows[dt]["pages"] 已是「当日 × 路径」的真实访次
        return sorted(daily_rows.get(dt, {}).get("pages", {}).items(), key=lambda x: -x[1])[:n]

    def dev_pct(dt, kind):
        dv = dev_by_date.get(dt, {})
        tot = sum(dv.values()) or 1
        return round(100 * dv.get(kind, 0) / tot, 1)

    def cn_top(dt, n=5):
        return sorted(cn_by_date.get(dt, []), key=lambda x: -x[1])[:n]

    clean_pages = [{"dimensions": {"clientRequestPath": p}, "sum": {"visits": v}}
                   for p, v in sorted(clean_pages_all.items(), key=lambda x: -x[1])]
    bot_pages = [{"dimensions": {"clientRequestPath": p}, "sum": {"visits": v}}
                 for p, v in sorted(bot_pages_all.items(), key=lambda x: -x[1])]
    # 窗口口径（不是"今天"）—— 今天样本太小，设备占比会失真
    dev = {}
    for d in dev_by_date.values():
        for k, v in d.items():
            dev[k] = dev.get(k, 0) + v
    dev_total = sum(dev.values()) or 1
    cn_all = {}
    for vs in cn_by_date.values():
        for c, v in vs:
            cn_all[c] = cn_all.get(c, 0) + v
    cn = sorted(cn_all.items(), key=lambda x: -x[1])[:5]

    # ---- 写 CSV（按日期 upsert） ----
    header = ("date,requests,visits,visits_clean,bot_pct,top1_path,top1_visits,"
              "top2_path,top2_visits,desktop_pct,mobile_pct,countries_top5,collected_at")
    rows = {}
    if os.path.exists(CSV_PATH):
        with open(CSV_PATH, encoding="utf-8") as f:
            for i, line in enumerate(f):
                line = line.rstrip("\n")
                if i == 0 or not line:
                    continue
                rows[line.split(",")[0]] = line
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    for dt, v in daily_rows.items():
        tp = top_pages(dt, 2)
        t1 = tp[0][0].replace(",", "，") if len(tp) > 0 else ""
        t1v = tp[0][1] if len(tp) > 0 else 0
        t2 = tp[1][0].replace(",", "，") if len(tp) > 1 else ""
        t2v = tp[1][1] if len(tp) > 1 else 0
        bot_pct = round(100 * (v["visits"] - v["visits_clean"]) / v["visits"], 1) if v["visits"] else 0
        rows[dt] = "%s,%d,%d,%d,%.1f,%s,%d,%s,%d,%.1f,%.1f,%s,%s" % (
            dt, v["requests"], v["visits"], v["visits_clean"], bot_pct,
            t1, t1v, t2, t2v, dev_pct(dt, "desktop"), dev_pct(dt, "mobile"),
            " ".join("%s:%d" % c for c in cn_top(dt)), now)


    # 追加更早的历史行时，把已存在的旧行保留（按日期字典序倒序输出）
    with open(CSV_PATH, "w", encoding="utf-8") as f:
        f.write(header + "\n")
        for dt in sorted(rows, reverse=True):
            f.write(rows[dt] + "\n")
    print("[4/4] 已写入 %s（%d 天）" % (CSV_PATH, len(rows)))

    detail = {
        "collected_at": now,
        "clean_pages": [{"path": g["dimensions"]["clientRequestPath"],
                         "visits": g["sum"]["visits"]} for g in clean_pages[:30]],
        "bot_pages": [{"path": g["dimensions"]["clientRequestPath"],
                       "visits": g["sum"]["visits"]} for g in bot_pages[:15]],
        "countries": cn,
        "devices": dev,
        "devices_pct": {k: round(100 * v / (sum(dev.values()) or 1), 1) for k, v in dev.items()},
        "visits_clean_total": clean_visits,
        "visits_bot_total": bot_visits,
    }
    with open(os.path.join(OUT_DIR, "明细-latest.json"), "w", encoding="utf-8") as f:
        json.dump(detail, f, ensure_ascii=False, indent=2)

    print("\n—— 快照（窗口 %d 天）——" % BACKFILL_DAYS)
    print("  真实访次 %d / 爬虫+系统 %d（噪声 %.1f%%）" % (clean_visits, bot_visits, 100 * (1 - ratio)))
    print("  设备：桌面 %.0f%% / 移动 %.0f%%" % (
        100 * dev.get("desktop", 0) / dev_total, 100 * dev.get("mobile", 0) / dev_total))
    print("  内容页 Top5（访次）：")
    for g in clean_pages[:5]:
        print("    %-42s %d" % (g["dimensions"]["clientRequestPath"], g["sum"]["visits"]))
    print("  最大噪声源 Top3：")
    for g in bot_pages[:3]:
        print("    %-42s %d" % (g["dimensions"]["clientRequestPath"], g["sum"]["visits"]))
    return 0


def report():
    if not os.path.exists(CSV_PATH):
        print("✗ 还没有数据，先跑 collect")
        return 1
    rows = []
    with open(CSV_PATH, encoding="utf-8") as f:
        next(f)
        for line in f:
            if line.strip():
                rows.append(line.rstrip("\n").split(","))
    rows.sort()
    detail = {}
    dp = os.path.join(OUT_DIR, "明细-latest.json")
    if os.path.exists(dp):
        detail = json.load(open(dp, encoding="utf-8"))

    dates = [r[0] for r in rows]
    clean = [int(r[3]) for r in rows]
    bot = [int(r[2]) - int(r[3]) for r in rows]
    mx = max(clean + bot) or 1

    def bars():
        out = []
        for d, a, b in zip(dates, clean, bot):
            out.append(
                '<div class="row"><span class="lb">%s</span>'
                '<div class="bar"><i style="width:%.1f%%;background:#8a6d3b"></i>'
                '<i style="width:%.1f%%;background:#d9a3a3"></i></div>'
                '<span class="vv">%d</span></div>' % (d, 100 * a / mx, 100 * b / mx, a))
        return "\n".join(out)

    pages = detail.get("clean_pages", [])[:12]
    pmx = max([p["visits"] for p in pages]) if pages else 1
    page_rows = "\n".join(
        '<div class="row"><span class="lb">%s</span>'
        '<div class="bar"><i style="width:%.1f%%;background:#8a6d3b"></i></div>'
        '<span class="vv">%d</span></div>' % (p["path"], 100 * p["visits"] / pmx, p["visits"])
        for p in pages)
    botp = detail.get("bot_pages", [])[:6]
    bmx = max([p["visits"] for p in botp]) if botp else 1
    bot_rows = "\n".join(
        '<div class="row"><span class="lb">%s</span>'
        '<div class="bar"><i style="width:%.1f%%;background:#b03030"></i></div>'
        '<span class="vv">%d</span></div>' % (p["path"], 100 * p["visits"] / bmx, p["visits"])
        for p in botp)
    dev = detail.get("devices", {})
    last = rows[-1] if rows else [""] * 13

    html = """<!doctype html><meta charset="utf-8"><title>第七境 · 站点看板</title>
<style>
 body{font-family:-apple-system,"PingFang SC",sans-serif;background:#faf8f4;color:#2b2b2b;
      margin:0;padding:28px 32px;max-width:920px}
 h1{font-size:20px;margin:0 0 4px;font-weight:600}
 .sub{font-size:12px;color:#8a8a8a;margin-bottom:24px}
 h2{font-size:14px;margin:26px 0 10px;font-weight:600;border-left:3px solid #8a6d3b;padding-left:8px}
 .row{display:flex;align-items:center;gap:10px;margin:5px 0;font-size:12px}
 .lb{width:220px;flex:none;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;color:#555}
 .bar{flex:1;height:15px;background:#ece7dd;border-radius:2px;overflow:hidden;display:flex}
 .bar i{height:100%%;display:block}
 .vv{width:56px;flex:none;text-align:right;font-variant-numeric:tabular-nums}
 .cards{display:flex;gap:12px;flex-wrap:wrap;margin:14px 0}
 .card{flex:1;min-width:150px;background:#fff;border:1px solid #e6e0d4;border-radius:6px;padding:12px 14px}
 .card .n{font-size:22px;font-weight:600}
 .card .t{font-size:11px;color:#8a8a8a;margin-top:2px}
 .note{font-size:12px;color:#777;background:#fff;border:1px dashed #ddd6c6;
       border-radius:6px;padding:10px 12px;line-height:1.7;margin-top:8px}
 .legend{font-size:11px;color:#888;margin:6px 0 10px}
 .sw{display:inline-block;width:10px;height:10px;border-radius:2px;margin-right:4px;vertical-align:middle}
</style>
<h1>第七境 · 站点看板</h1>
<div class="sub">数据源 Cloudflare Zone Analytics · 更新于 %(now)s · 判据见 站点分析-指标与决策映射.md</div>

<div class="cards">
 <div class="card"><div class="n">%(last_clean)s</div><div class="t">最近一日真实访次</div></div>
 <div class="card"><div class="n">%(bot_pct)s%%</div><div class="t">爬虫+系统噪声占比</div></div>
 <div class="card"><div class="n">%(desktop)s%%</div><div class="t">桌面端</div></div>
 <div class="card"><div class="n">%(mobile)s%%</div><div class="t">移动端</div></div>
 <div class="card"><div class="n">%(days)s</div><div class="t">已采集天数</div></div>
</div>

<h2>每日访次（深色＝真实内容页，浅红＝爬虫/系统）</h2>
<div class="legend"><span class="sw" style="background:#8a6d3b"></span>真实访次
 <span class="sw" style="background:#d9a3a3;margin-left:10px"></span>爬虫+系统</div>
%(bars)s

<h2>内容页 Top（真实访次）</h2>
%(page_rows)s

<h2>最大噪声源（不参与决策）</h2>
%(bot_rows)s

<div class="note">
<b>读数前必看</b><br>
· 本看板取的是 <b>Zone Analytics</b>，不是后台那个 Web Analytics —— 后者当前无公开 API。<br>
· 真实访次＝按 IP+30 分钟不活动去重后的 visits，已剔除 wp-login/xmlrpc/wp-includes 等系统路径。<br>
· 免费版拿不到来源域名与机器人判定字段，故「哪个渠道来的」暂时读不出。<br>
· <b>数据只能回溯 3–4 天</b>，所以曲线长度＝采集坚持的天数，断一天就永久缺一天。
</div>
""" % {
        "now": detail.get("collected_at", "-"),
        "last_clean": last[3] if len(last) > 3 else "-",
        "bot_pct": last[4] if len(last) > 4 else "-",
        "desktop": detail.get("devices_pct", {}).get("desktop", "-"),
        "mobile": detail.get("devices_pct", {}).get("mobile", "-"),
        "days": len(rows),
        "bars": bars(),
        "page_rows": page_rows or '<div class="note">暂无</div>',
        "bot_rows": bot_rows or '<div class="note">暂无</div>',
    }
    with open(HTML_PATH, "w", encoding="utf-8") as f:
        f.write(html)
    print("✓ 看板已生成 %s" % HTML_PATH)
    return 0


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "collect"
    if cmd == "collect":
        sys.exit(collect())
    elif cmd == "report":
        sys.exit(report())
    elif cmd == "all":
        sys.exit(collect() or report())
    elif cmd == "raw":
        t = get_token()
        print(json.dumps(gql(sys.argv[2], t), ensure_ascii=False, indent=2))
    else:
        print(__doc__)
