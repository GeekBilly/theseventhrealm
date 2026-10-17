#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""批量拉取线上页面正文原文（context=edit 的 content.raw），存为备份。

为什么不用 ?context=edit 一次拉全部：站点返回体超过约 190KB 会被截断，
json.loads 失败。这里逐页拉、逐页校验，失败即报出 id 而不是静默跳过。

用法：
  python3 11-运营/scripts/pull-pages-raw.py --dir 11-运营/上线备份/spacing-20261017
  python3 11-运营/scripts/pull-pages-raw.py --ids 13,32,86 --dir /tmp/x
"""
import argparse
import json
import pathlib
import subprocess
import sys
import urllib.parse

ROOT = pathlib.Path(__file__).resolve().parents[2]
SITE = "https://theseventhrealm.com"
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36")

# 全站页面：首页 / 总览 / 关于与法务 / 朝代 16 / 藏品 / FAQ / 英文 / 藏品子页 17
ALL_IDS = ([13, 32, 86, 87, 88, 89, 90] + list(range(94, 110)) +
           [134, 189, 193] + list(range(344, 361)))


def auth():
    out = subprocess.run(
        ["security", "find-generic-password", "-a", "MollyBot_No.2",
         "-s", "theseventhrealm-wp", "-w"],
        capture_output=True, text=True, check=True)
    return "MollyBot_No.2", out.stdout.strip()


def fetch(pid, user, pwd):
    q = urllib.parse.urlencode({"context": "edit", "_fields": "id,slug,modified,content"})
    url = f"{SITE}/wp-json/wp/v2/pages/{pid}?{q}"
    r = subprocess.run(
        ["curl", "-sL", "--max-time", "60", "-u", f"{user}:{pwd}",
         "-A", UA, "-H", "Accept: application/json", "--compressed", url],
        capture_output=True, text=True)
    return r.stdout


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", required=True)
    ap.add_argument("--ids", default="")
    a = ap.parse_args()

    ids = [int(x) for x in a.ids.split(",") if x.strip()] if a.ids else ALL_IDS
    outdir = ROOT / a.dir
    outdir.mkdir(parents=True, exist_ok=True)
    user, pwd = auth()

    ok, bad = [], []
    for pid in ids:
        raw = fetch(pid, user, pwd)
        try:
            d = json.loads(raw)
            if "content" not in d:
                raise ValueError(d.get("code", "no content"))
        except Exception as e:
            bad.append((pid, str(e)[:80], len(raw)))
            print(f"  ✗ {pid}: {str(e)[:60]} ({len(raw)} 字节)")
            continue
        body = d["content"]["raw"]
        (outdir / f"{pid:03d}-{d.get('slug', 'x')}.html").write_text(body, encoding="utf-8")
        (outdir / f"{pid:03d}-{d.get('slug', 'x')}.json").write_text(
            json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")
        ok.append((pid, d.get("slug"), len(body), d.get("modified")))
        print(f"  ✓ {pid:>3} {d.get('slug', ''):14s} {len(body):>7d} 字符")

    print(f"\n完成 {len(ok)} 页，失败 {len(bad)} 页 → {outdir}")
    if bad:
        print("失败清单：", bad)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
