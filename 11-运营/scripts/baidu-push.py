#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
第七境 · 百度「API 提交（主动推送）」推送脚本

背景：百度 sitemap 提交入口对本站 disabled（无 ICP 备案 + 全新站），
主路径改走 API 提交（旧称「主动推送」），额度与 sitemap 独立。

用法：
    python3 11-运营/scripts/baidu-push.py --plan        # 只看推送计划，不发请求
    python3 11-运营/scripts/baidu-push.py --limit 1     # 试推 1 条（做配额对照实验）
    python3 11-运营/scripts/baidu-push.py --limit 10    # 按优先级推 10 条
    python3 11-运营/scripts/baidu-push.py --all         # 推全部（受额度限制，超额会被拒）

凭据：从钥匙串读（source 11-运营/baidu-push-auth.sh），也可 BD_TOKEN=xxx 临时给。
     token 绝不硬编码进本文件。

去重：已成功推送的 URL 记在 11-运营/data/baidu-pushed.txt，默认跳过（--force 可重推）。
"""

import argparse
import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
SITEMAP = ROOT / "03-页面" / "站点文件" / "sitemap-baidu.xml"
PUSHED_LOG = ROOT / "11-运营" / "data" / "baidu-pushed.txt"
PUSH_CSV = ROOT / "11-运营" / "data" / "baidu-push.csv"

ENDPOINT = "http://data.zz.baidu.com/urls"

# 优先级：越靠前越先推。匹配用「路径包含」，按顺序判定
PRIORITY = [
    ("首页/道境", ["theseventhrealm.com/"]),
    ("五千年总览", ["/5000years/"]),
    ("藏品页", ["/collection/"]),
    ("朝代页", ["/5000years/"]),
    ("法务页", ["/about/", "/contact/", "/privacy/", "/terms/", "/disclaimer/"]),
]


def get_token() -> str:
    tok = os.environ.get("BD_TOKEN")
    if tok:
        return tok.strip()
    try:
        return subprocess.run(
            ["security", "find-generic-password", "-a", "theseventhrealm",
             "-s", "baidu-ziyuan-push", "-w"],
            capture_output=True, text=True, timeout=10,
        ).stdout.strip()
    except Exception:
        return ""


def get_site() -> str:
    return os.environ.get("BD_SITE", "https://theseventhrealm.com")


def load_urls() -> list[str]:
    if not SITEMAP.exists():
        sys.exit(f"✗ 找不到 sitemap：{SITEMAP}（先跑 build-baidu-sitemap.py）")
    xml = SITEMAP.read_text(encoding="utf-8")
    return re.findall(r"<loc>([^<]+)</loc>", xml)


def sort_urls(urls: list[str]) -> list[str]:
    """按 PRIORITY 分组排序；组内**保持 sitemap 原顺序**（= 朝代时间顺序），不用字典序。"""
    idx = {u: i for i, u in enumerate(urls)}

    def rank_of(path: str) -> int:
        # ① 首页：精确
        if path == "/":
            return 0
        # ② 五千年总览：精确（否则会吞掉全部朝代页）
        if path == "/5000years/":
            return 1
        # ③ 藏品页
        if path.startswith("/collection/"):
            return 2
        # ④ 朝代页（总览之外的 /5000years/ 子页）
        if path.startswith("/5000years/"):
            return 3
        # ⑤ 法务页
        if any(path.startswith(p) for p in ("/about/", "/contact/", "/privacy/",
                                            "/terms/", "/disclaimer/")):
            return 4
        return 9

    def key(u: str) -> tuple:
        path = u.replace("https://theseventhrealm.com", "") or "/"
        return (rank_of(path), idx[u])

    return sorted(urls, key=key)


def load_pushed() -> set[str]:
    if not PUSHED_LOG.exists():
        return set()
    return {l.strip() for l in PUSHED_LOG.read_text(encoding="utf-8").splitlines() if l.strip()}


def push(site: str, token: str, urls: list[str]) -> dict:
    payload = "\n".join(urls)
    req = urllib.request.Request(
        f"{ENDPOINT}?site={urllib.parse.quote(site, safe=':/')}&token={token}",
        data=payload.encode("utf-8"),
        headers={"Content-Type": "text/plain"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return {"http": r.status, "body": r.read().decode("utf-8", "ignore")}
    except urllib.error.HTTPError as e:
        return {"http": e.code, "body": e.read().decode("utf-8", "ignore")}
    except Exception as e:
        return {"http": 0, "body": str(e)}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--plan", action="store_true", help="只看计划")
    ap.add_argument("--limit", type=int, default=0, help="本次最多推几条")
    ap.add_argument("--all", action="store_true", help="推全部未推过的")
    ap.add_argument("--force", action="store_true", help="忽略已推送记录")
    args = ap.parse_args()

    site, token = get_site(), get_token()
    if not token:
        sys.exit("✗ 拿不到 BD_TOKEN：先 source 11-运营/baidu-push-auth.sh")

    all_urls = sort_urls(load_urls())
    pushed = set() if args.force else load_pushed()
    todo = [u for u in all_urls if u not in pushed]

    print(f"站点：{site}")
    print(f"sitemap 共 {len(all_urls)} 条 | 已推过 {len(all_urls) - len(todo)} 条 | 待推 {len(todo)} 条")

    # --plan 时按全部待推展示计划（否则 --limit 默认 0 会误报"没有待推送的 URL"）
    n = len(todo) if (args.all or args.plan) else min(args.limit, len(todo))
    if n <= 0:
        print("没有待推送的 URL（用 --force 可重推）")
        return 0
    batch = todo[:n]

    print(f"\n本次推送 {len(batch)} 条：")
    for u in batch:
        print("  ", u.replace("https://theseventhrealm.com", "") or "/")

    if args.plan:
        print("\n[--plan] 未实际发送")
        return 0

    res = push(site, token, batch)
    print(f"\nHTTP {res['http']}")
    print(res["body"][:600])

    # 只在明确成功时才记去重日志
    body = res["body"]
    ok = res["http"] == 200 and '"success"' in body and '"error"' not in body
    if ok:
        PUSHED_LOG.parent.mkdir(parents=True, exist_ok=True)
        with PUSHED_LOG.open("a", encoding="utf-8") as f:
            for u in batch:
                f.write(u + "\n")
        PUSH_CSV.parent.mkdir(parents=True, exist_ok=True)
        new = PUSH_CSV.exists() is False
        with PUSH_CSV.open("a", encoding="utf-8") as f:
            if new:
                f.write("time,count,remain,success\n")
            m_remain = re.search(r'"remain":(\d+)', body)
            m_succ = re.search(r'"success":(\d+)', body)
            f.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')},{len(batch)},"
                    f"{m_remain.group(1) if m_remain else ''},"
                    f"{m_succ.group(1) if m_succ else ''}\n")
        print(f"\n✅ 已记录到 {PUSHED_LOG.relative_to(ROOT)}")
    else:
        print("\n⚠️ 未判定为成功，未写去重日志（避免漏记导致重复消耗额度）")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
