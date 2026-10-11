#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
爬虫可达性自检 —— 验证 Cloudflare 是否放行了搜索引擎爬虫。

背景（2026-09-30 实测）：
  Baiduspider 被两层封锁：
    ① robots.txt（君子协定层）—— Cloudflare 托管内容写了 Disallow: /
    ② 边缘 WAF / AI Crawl Control（硬拦层）—— 直接返回 403
  只解一层无效，必须两层都通过，本脚本才算 PASS。

用法：
  python3 11-运营/scripts/check-crawler-access.py            # 默认测这些venthrealm.com
  python3 11-运营/scripts/check-crawler-access.py <域名>     # 测别的域名
"""
import subprocess
import sys
import urllib.parse

# 需要放行的搜索引擎爬虫。前四个百度系是重点。

CRAWLERS = [
    ("Baiduspider",       "Mozilla/5.0 (compatible; Baiduspider/2.0; +http://www.baidu.com/search/spider.html)"),
    ("Baiduspider-image", "Mozilla/5.0 (compatible; Baiduspider-image/1.0; +http://www.baidu.com/search/spider.html)"),
    ("Baiduspider-mobile","Mozilla/5.0 (compatible; Baiduspider-mobile/2.0; +http://www.baidu.com/search/spider.html)"),
    ("Baiduspider-render","Mozilla/5.0 (compatible; Baiduspider-render/2.0; +http://www.baidu.com/search/spider.html)"),
    ("Googlebot",         "Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)"),
    ("bingbot",           "Mozilla/5.0 (compatible; bingbot/2.0; +http://www.bing.com/bingbot.htm)"),
    ("Sogou Spider",      "Sogou web spider/4.0(+http://www.sogou.com/docs/help/webmasters.htm#07)"),
    ("360Spider",         "Mozilla/5.0 (compatible; 360Spider; http://www.so.com/help/help_3_2.html)"),
]

def http_code(url, ua=None):
    cmd = ["curl", "-s", "-o", "/dev/null", "-w", "%{http_code}", "-L",
           "--max-time", "25", url]
    if ua:
        cmd += ["-A", ua]
    try:
        out = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        return out.stdout.strip()
    except Exception:
        return "ERR"

def fetch(url, ua=None):
    cmd = ["curl", "-s", "-L", "--max-time", "25", url]
    if ua:
        cmd += ["-A", ua]
    try:
        out = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        return out.stdout
    except Exception:
        return ""

def main():
    host = sys.argv[1] if len(sys.argv) > 1 else "theseventhrealm.com"
    base = "https://" + host
    url = base + "/5000years/shang/"

    print()
    print("=" * 62)
    print("  爬虫可达性自检 · %s" % host)
    print("=" * 62)

    # ---------- 第一层：边缘是否被硬拦 ----------
    print()
    print("【第一层】边缘 WAF / AI Crawl Control —— 是否硬拦")
    print("-" * 62)
    failed = []
    for name, ua in CRAWLERS:
        code = http_code(url, ua)
        if code == "200":
            mark = "✅ PASS"
        elif code in ("403", "406"):
            mark = "❌ 被拦"
            failed.append(name)
        else:
            mark = "⚠️ 异常 %s" % code
            failed.append(name)
        print("  %-20s %-8s %s" % (name, code, mark))

    # ---------- 第二层：robots.txt 是否写了 Disallow ----------
    print()
    print("【第二层】robots.txt —— 是否声明禁止")
    print("-" * 62)
    robots = fetch(base + "/robots.txt")
    if not robots:
        print("  ⚠️ 取不到 robots.txt（可能被拦或超时）")
    lines = robots.split("\n")
    blocked_ua = []
    cur = None
    for ln in lines:
        s = ln.strip()
        low = s.lower()
        if low.startswith("user-agent:"):
            cur = s.split(":", 1)[1].strip()
        elif low.startswith("disallow:") and cur:
            rule = s.split(":", 1)[1].strip()
            if rule == "/":
                blocked_ua.append(cur)
    keywords = ("baidu", "sogou", "360", "googlebot", "bingbot")
    hits = [u for u in blocked_ua if any(k in u.lower() for k in keywords)]
    if hits:
        for u in hits:
            print("  ❌ %s → Disallow: /" % u)
        if not failed:
            failed.append("(robots.txt 层面)")
    elif blocked_ua:
        print("  ✅ 搜索引擎爬虫在 robots.txt 里没有被 Disallow")
        print("     （另有 %d 个 UA 被禁，属 AI 训练类，与搜索无关："
              % len(blocked_ua))
        print("      %s …）" % ", ".join(blocked_ua[:6]))
    else:
        print("  ✅ robots.txt 里没有任何 Disallow: / 规则")

    # 是否仍能读到 CF 托管段的痕迹
    if "Cloudflare Managed" in robots:
        print("  ⚠️ 检测到 '# Cloudflare Managed' 段仍在 —— 托管 robots.txt 尚未关闭")

    # ---------- 结论 ----------
    print()
    print("=" * 62)
    if not failed:
        print("  🎉 全部通过：两层都已放行，百度可以正常抓取。")
        print()
        print("  注意：爬虫会缓存 robots.txt（百度约 24h–数天），")
        print("        并不意味着立刻收录，给它 1–7 天再来。")
    else:
        print("  ⚠️ 尚未完全放行：%s" % "、".join(failed))
        print()
        print("  两层要分别处理：")
        print("   ① 硬拦层 → Cloudflare 后台 AI Crawl Control / Security > Bots")
        print("   ② 声明层 → Security Settings > Bot traffic")
        print("              > 「Set your preference to block training in robots.txt」关掉")
    print("=" * 62)
    print()
    return 0 if not failed else 1

if __name__ == "__main__":
    sys.exit(main())
