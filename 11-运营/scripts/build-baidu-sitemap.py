#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
build-baidu-sitemap.py —— 生成可提交百度的「非索引型」sitemap

背景（2026-09-30 实测）
  百度「资源提交 → 普通收录 → sitemap」有两条硬约束：
    1) 索引型 sitemap（顶层 <sitemapindex>）**不予处理**，且一旦存在还会阻止提交新文件；
       WordPress 自带的 /wp-sitemap.xml 恰好就是索引型 → 不能提交它。
    2) 存量文件配额通常只有 **1 条** → 只能交 1 个文件。

做法
  把 wp-sitemap 的子图（posts-* / page-*）里的 <loc> 合并成一个扁平 <urlset> 文件，
  排除 taxonomies-*（分类归档）与 users-*（作者归档，属隐私项，R-24 精神），
  输出到 03-页面/站点文件/sitemap-baidu.xml，再由人工经 cPanel 上传到站点根目录。

用法
  python3 11-运营/scripts/build-baidu-sitemap.py            # 生成
  python3 11-运营/scripts/build-baidu-sitemap.py --check    # 生成 + 逐个 HEAD 验证 URL 可访问
"""

import argparse
import pathlib
import re
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone

SITE = "https://theseventhrealm.com"
INDEX_URL = f"{SITE}/wp-sitemap.xml"
OUT = pathlib.Path(__file__).resolve().parents[2] / "03-页面" / "站点文件" / "sitemap-baidu.xml"

# 只收内容型子图；归档型（分类 / 作者）不入 sitemap
KEEP_SUB = re.compile(r"wp-sitemap-(posts|page)-")
UA = "Mozilla/5.0 (compatible; seventhrealm-sitemap-builder/1.0)"


def fetch(url: str, tries: int = 3) -> str:
    """带重试的 GET；失败一次即降级（成本控制优先，不做长重试循环）。"""
    last = None
    for _ in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=30) as r:
                return r.read().decode("utf-8", "ignore")
        except Exception as e:  # noqa: BLE001
            last = e
    raise SystemExit(f"[FAIL] {url} 取不到：{last}")


def locs(xml: str) -> list[str]:
    return [m.strip() for m in re.findall(r"<loc>\s*([^<]+?)\s*</loc>", xml)]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="生成后逐个 HEAD 验证 URL")
    args = ap.parse_args()

    index = fetch(INDEX_URL)
    if "<sitemapindex" not in index:
        print("[WARN] 顶层不是 sitemapindex，结构已变，请人工复核后再用")

    subs = [u for u in locs(index) if KEEP_SUB.search(u)]
    skipped = [u for u in locs(index) if u not in subs]
    print(f"子图 {len(subs)} 个（采用） / {len(skipped)} 个（跳过）：")
    for u in skipped:
        print(f"  - 跳过 {u.rsplit('/', 1)[-1]}")

    entries: list[tuple[str, str]] = []
    for sub in subs:
        xml = fetch(sub)
        las = re.findall(r"<url>.*?</url>", xml, re.S)
        for blk in las:
            u = locs(blk)
            if not u:
                continue
            lm = re.search(r"<lastmod>\s*([^<]+?)\s*</lastmod>", blk)
            entries.append((u[0], lm.group(1) if lm else ""))

    # 去重（保留首次出现）
    seen, uniq = set(), []
    for u, lm in entries:
        if u not in seen:
            seen.add(u)
            uniq.append((u, lm))

    if not uniq:
        raise SystemExit("[FAIL] 没解析到任何 URL，中止（不要写出空 sitemap）")
    if len(uniq) > 50000:
        raise SystemExit(f"[FAIL] {len(uniq)} 条 > 百度上限 50000 条")

    body = ['<?xml version="1.0" encoding="UTF-8"?>',
            '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    for u, lm in uniq:
        body.append("  <url>")
        body.append(f"    <loc>{u}</loc>")
        if lm:
            body.append(f"    <lastmod>{lm}</lastmod>")
        body.append("  </url>")
    body.append("</urlset>")
    xml_out = "\n".join(body) + "\n"

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(xml_out, encoding="utf-8")
    size = OUT.stat().st_size

    print(f"\n生成：{OUT.relative_to(OUT.parents[2])}")
    print(f"URL 数：{len(uniq)}   大小：{size} bytes（百度上限 50000 条 / 10MB）")
    print(f"顶层标签：{'urlset ✅ 非索引型' if '<urlset' in xml_out else '❌ 异常'}")
    print(f"生成时间：{datetime.now(timezone.utc).astimezone():%Y-%m-%d %H:%M:%S}")
    print("\nURL 清单：")
    for u, _ in uniq:
        print(f"  {u}")

    if args.check:
        print("\n逐个验证可访问性（HEAD）：")
        bad = 0
        for u, _ in uniq:
            try:
                req = urllib.request.Request(u, headers={"User-Agent": UA}, method="HEAD")
                with urllib.request.urlopen(req, timeout=20) as r:
                    code = r.status
            except urllib.error.HTTPError as e:
                code = e.code
            except Exception:  # noqa: BLE001
                code = 0
            flag = "" if code == 200 else "  ← 注意"
            if code != 200:
                bad += 1
            print(f"  {code}  {u}{flag}")
        print(f"\n非 200 的：{bad} 条")
        return 1 if bad else 0

    print("\n下一步：由人工经 cPanel 上传到 public_html（与 baidu_verify_*.html 同目录），"
          "地址 https://theseventhrealm.com/sitemap-baidu.xml 应返回 200。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
