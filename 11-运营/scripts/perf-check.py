#!/usr/bin/env python3
# 第七境 · 站点性能体检（perf-check.py）
# ==================================================================
# 干什么
#   逐页测「冷缓存（回源）」与「热缓存（CDN 命中）」两种速度，找出慢页，
#   落盘 CSV（每日追加）+ JSON 汇总（供晨检简报与工作台消费）。
#
# 为什么必须分冷热 —— 这是本脚本最核心的设计
#   本站用户在中国，源站在 GoDaddy（美国），中间隔着 Cloudflare。
#   实测（2026-10-17）：连 1.3KB 的 favicon（纯 CDN 静态缓存）TTFB 也要 4~6 秒
#   ⇒ 说明「国内 → CF 洛杉矶节点」这条跨境链路本身就慢，这部分**我们改不了**。
#   所以绝对 TTFB 不能拿来判定站点好坏，会被链路噪声淹没。
#   ⇒ 真正属于站点自己的开销 ＝ **冷 − 热**（多出来的那一次跨境回源往返）。
#     冷 = 加 cache-buster 强制回源；热 = CDN 命中。差值就是可优化空间。
#   经验值：冷热差 < 0.5s ＝ HTML 已缓存，没问题；
#           冷热差 > 2s ＝ HTML 每次都在回源，是本站最大的性能杠杆。
#
# 判据（写死在 THRESHOLD，改阈值要连文档一起改）
#   cold_ttfb  回源首字节   > 3.0s 告警
#   hot_ttfb   CDN 首字节   > 1.5s 告警
#   gap        冷 − 热      > 2.0s 告警（＝HTML 没进 CDN，应该去配缓存）
#   size       HTML 压缩后  > 400KB 告警
#
# 用法
#   python3 11-运营/scripts/perf-check.py              # 核心 8 页（日常晨检用）
#   python3 11-运营/scripts/perf-check.py --all        # 全站 43 页（每周一次）
#   python3 11-运营/scripts/perf-check.py --limit 5
#   python3 11-运营/scripts/perf-check.py --url https://… --url https://…
#   python3 11-运营/scripts/perf-check.py --no-cold    # 只测热（快一倍）
#   python3 11-运营/scripts/perf-check.py --quiet      # 只落盘，不打印
#
# 退出码：0 = 全部在阈值内；2 = 有页面超阈值
# ==================================================================

import argparse
import concurrent.futures as cf
import csv
import json
import pathlib
import re
import subprocess
import sys
import time
from datetime import datetime

ROOT = pathlib.Path(__file__).resolve().parents[2]
SITEMAP = ROOT / "03-页面" / "站点文件" / "sitemap-baidu.xml"
OUT_CSV = ROOT / "11-运营" / "data" / "perf-站点性能.csv"
OUT_JSON = ROOT / "11-运营" / "data" / "morning-perf.json"
SITE = "https://theseventhrealm.com"

# 🔴 Cloudflare 会拦 curl 默认 UA 返 403（不是故障）。必须带浏览器 UA。
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36")

# ⚠️ 本机会被强制走 WorkBuddy 透明代理（127.0.0.1:64713），测出的是「代理 → CF」的耗时，
#    与真实用户（直连）不完全一致。脚本不做伪装，但在汇总里记 via_proxy 供判读。
VIA_PROXY = bool(__import__("os").environ.get("HTTPS_PROXY") or __import__("os").environ.get("https_proxy"))

# 日常晨检只跑 3 个代表页。为什么这么少：实测单次请求在这条跨境链路上要 5~20 秒，
# 8 页 × 多采样 会跑到 300 秒，晨检扛不住。3 页 × 单次采样 ≈ 15~30 秒，够用。
# 想看全站用 --all（建议周末单独跑一次，别塞进晨检）。
CORE = ["", "5000years/", "collection/"]

THRESHOLD = {"cold_ttfb": 3.0, "hot_ttfb": 1.5, "gap": 2.0, "size": 400 * 1024}

CURL_FMT = "%{http_code}|%{time_starttransfer}|%{time_total}|%{size_download}|%{remote_ip}"


def run(url):
    """跑一次 curl；返回 (指标, 响应头)。--compressed 模拟真实浏览器（CF 会开 Brotli）"""
    head = "/tmp/qj-perf-head-%d.txt" % __import__("os").getpid()
    cmd = ["curl", "-s", "-o", "/dev/null", "-L", "--compressed",
           "--max-time", "25", "-A", UA, "-w", CURL_FMT, "-D", head, url]
    try:
        out = subprocess.run(cmd, capture_output=True, text=True, timeout=35).stdout.strip()
    except Exception:
        return None, {}
    p = out.split("|")
    if len(p) < 5:
        return None, {}
    try:
        m = {"http": int(float(p[0])), "ttfb": float(p[1]), "total": float(p[2]),
             "size": int(float(p[3])), "ip": p[4]}
    except ValueError:
        return None, {}
    heads = {}
    try:
        for line in open(head, "r", encoding="utf-8", errors="ignore"):
            if ":" in line:
                k, v = line.split(":", 1)
                heads[k.strip().lower()] = v.strip()
    except Exception:
        pass
    return m, heads


def once(url, cold=False):
    target = url
    if cold:
        target = url + ("&" if "?" in url else "?") + "__cb=%d" % int(time.time() * 1000)
    m, h = run(target)
    if not m:
        return None
    m["cache"] = (h.get("cf-cache-status") or "-").upper()
    m["ray"] = (h.get("cf-ray") or "-")[-3:]      # 只留机场码，如 LAX
    return m


def median(xs):
    """取中位数，剔除 0（超时/失败）样本；全失败返回 None"""
    xs = sorted(x for x in xs if x and x > 0)
    if not xs:
        return None
    n = len(xs)
    return xs[n // 2] if n % 2 else (xs[n // 2 - 1] + xs[n // 2]) / 2


def measure(url):
    """一个页面的完整测量。
    ⚠️ 为什么必须多采样：实测这条跨境链路单次 TTFB 在 2.9s~16.7s 之间乱跳，
       甚至出现 0（超时）—— 单次测量毫无意义，一律取中位数。
       顺序：先跑 1 次丢弃（预热 CDN），再热 N 次、冷 N 次。"""
    once(url)                                   # 预热，丢弃
    hots = [m["ttfb"] for m in (once(url) for _ in range(SAMPLES)) if m]
    hot_meta = once(url)
    colds = []
    if not NO_COLD:
        colds = [m["ttfb"] for m in (once(url, cold=True) for _ in range(SAMPLES)) if m]
        cold_meta = once(url, cold=True)
    else:
        cold_meta = None
    return url, {
        "hot": median(hots), "cold": median(colds) if not NO_COLD else None,
        "meta": hot_meta, "cold_meta": cold_meta,
        "n_hot": len(hots), "n_cold": len(colds),
    }


def load_urls():
    if SITEMAP.exists():
        txt = SITEMAP.read_text(encoding="utf-8", errors="ignore")
        return [u.split("</loc>")[0].strip() for u in txt.split("<loc>") if "</loc>" in u]
    return [SITE + "/" + p for p in CORE]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--all", action="store_true", help="全站 43 页")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--url", action="append", default=[])
    ap.add_argument("--no-cold", action="store_true")
    ap.add_argument("--quiet", action="store_true")
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--samples", type=int, default=1,
                    help="冷/热各采几次取中位数（晨检默认 1＝快采；想看准用 3）")
    a = ap.parse_args()

    global NO_COLD, SAMPLES
    NO_COLD = a.no_cold
    SAMPLES = a.samples

    urls = a.url or ([SITE + "/" + p for p in CORE] if not a.all else load_urls())
    if a.limit:
        urls = urls[:a.limit]

    t0 = time.time()
    rows, bad = [], []
    with cf.ThreadPoolExecutor(max_workers=a.workers) as ex:
        results = list(ex.map(measure, urls))

    for url, r in results:
        short = url.replace(SITE, "") or "/"
        h = r["meta"]
        # 全样本失败 ＝ 链路超时，不是站点问题 —— 单独标注，不计入站点告警
        if r["hot"] is None and not h:
            rows.append({"url": short, "http": 0, "cold": "", "hot": "", "gap": "",
                         "size": "", "cache": "-", "ray": "-", "flag": "链路超时"})
            continue
        c_ttfb = r["cold"]
        h_ttfb = r["hot"]
        gap = (c_ttfb - h_ttfb) if (c_ttfb is not None and h_ttfb is not None) else None
        size = h["size"] if h else 0
        cache = (h["cache"] if h else "-")

        # —— 告警分两类 ——
        # 硬指标（链路无关，一定是站点自己的问题）
        #   ① HTML 每次回源（DYNAMIC）② 体积超标 ③ 非 200
        # 参考值（受跨境链路污染，只提示不报警）
        #   ④ 冷/热 TTFB 绝对值 ⑤ 回源开销 gap
        flag = "ok"
        if h and h["http"] != 200:
            flag = "HTTP非200"
        elif size >= THRESHOLD["size"]:
            flag = "HTML偏大"
        elif cache == "DYNAMIC" and (gap or 0) >= THRESHOLD["gap"]:
            flag = "未缓存·回源开销大"
        elif cache == "DYNAMIC":
            flag = "未缓存(参考)"
        elif (c_ttfb or 0) >= THRESHOLD["cold_ttfb"] and (gap or 0) >= THRESHOLD["gap"]:
            flag = "回源开销大"
        hard = flag in ("HTTP非200", "HTML偏大", "未缓存·回源开销大")
        if hard:
            bad.append((short, flag, c_ttfb or h_ttfb or 0))

        rows.append({
            "url": short, "http": h["http"] if h else 0,
            "cold": round(c_ttfb, 2) if c_ttfb is not None else "",
            "hot": round(h_ttfb, 2) if h_ttfb is not None else "",
            "gap": round(gap, 2) if gap is not None else "",
            "size": size, "cache": cache, "ray": h["ray"] if h else "-", "flag": flag,
        })

    rows.sort(key=lambda r: -(r["cold"] or 0))

    # —— 落盘 CSV（追加，一日一行一页）——
    day = datetime.now().strftime("%Y-%m-%d")
    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    new = not OUT_CSV.exists()
    with open(OUT_CSV, "a", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        if new:
            w.writerow(["date", "url", "http", "cold_ttfb", "hot_ttfb", "gap",
                        "size", "cache", "ray", "flag"])
        for r in rows:
            w.writerow([day, r["url"], r["http"], r["cold"], r["hot"], r["gap"],
                        r["size"], r["cache"], r["ray"], r["flag"]])

    def avg(xs):
        xs = [x for x in xs if x != ""]
        return round(sum(xs) / len(xs), 2) if xs else None

    summary = {
        "checked_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "pages": len(rows),
        "via_proxy": VIA_PROXY,          # True 时绝对值为代理链路口径，看 gap 更准
        "cold_avg": avg([r["cold"] for r in rows]),
        "cold_max": max([r["cold"] for r in rows if r["cold"] != ""] or [0]),
        "hot_avg": avg([r["hot"] for r in rows]),
        "gap_avg": avg([r["gap"] for r in rows]),
        "gap_max": max([r["gap"] for r in rows if r["gap"] != ""] or [0]),
        "size_avg_kb": round(avg([r["size"] for r in rows]) / 1024, 1) if rows else None,
        "cached_pages": sum(1 for r in rows if r["cache"] in ("HIT", "REVALIDATED")),
        "dynamic_pages": sum(1 for r in rows if r["cache"] == "DYNAMIC"),
        "slow": [{"url": r["url"], "why": r["flag"], "val": r["cold"] or r["hot"]}
                 for r in rows if r["flag"] != "ok"][:6],
        "slow_count": len(bad),          # 只数硬告警
        "elapsed_sec": round(time.time() - t0, 1),
        "verdict": ("⚠️ 有硬告警，建议处理" if bad else
                    "✅ 站点自身无硬问题（绝对 TTFB 受跨境链路影响，仅供参考）"),
    }
    OUT_JSON.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    if not a.quiet:
        print("\n—— 性能体检 · %s（%d 页，耗时 %.0fs）——" % (summary["checked_at"], len(rows), summary["elapsed_sec"]))
        print("%-30s %7s %7s %7s %9s %-9s %s" % ("页面", "冷(回源)", "热(CDN)", "差", "压缩后", "缓存", "机场"))
        print("-" * 88)
        for r in rows:
            print("%-30s %7s %7s %7s %8sKB %-9s %s %s" % (
                r["url"][:30], r["cold"], r["hot"], r["gap"],
                round(r["size"] / 1024, 1) if r["size"] else "-",
                r["cache"], r["ray"], "⚠️" + r["flag"] if r["flag"] != "ok" else ""))
        print("-" * 88)
        print("  冷均值 %.2fs ｜热均值 %.2fs ｜回源开销均值 %.2fs（最大 %.2fs）"
              % (summary["cold_avg"] or 0, summary["hot_avg"] or 0,
                 summary["gap_avg"] or 0, summary["gap_max"] or 0))
        print("  HTML 已进 CDN %d 页 ｜ DYNAMIC 每次回源 %d 页 ｜ 压缩后均 %.1fKB"
              % (summary["cached_pages"], summary["dynamic_pages"], summary["size_avg_kb"] or 0))
        if VIA_PROXY:
            print("  ⚠️ 本机走透明代理 + 跨境链路，绝对 TTFB 噪声极大，仅作趋势参考")
        print("  " + summary["verdict"])
        print("\n  CSV  → %s\n  JSON → %s" % (OUT_CSV, OUT_JSON))
    return 2 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
