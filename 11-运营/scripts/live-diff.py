#!/usr/bin/env python3
"""线上 vs 本地 实质比对 —— 发布前的"该不该发"判定器。

背景：WordPress 在保存/渲染 content 时会做两件事，造成"看起来不同其实一样"：
  1) wpautop  → 自动补 <p>/<br> 包裹
  2) wptexturize → 引号破折号省略号美化（" → ”，-- → —）
第三方还会有 Cloudflare Email Obfuscation 之类改写。
直接字符串比对必报假警报（历史上已误报两次：一次主题包、一次 16 朝页）。

**关键：比对对象是 `content.raw`（context=edit），不是 `rendered`。**
`rendered` 经过 `the_content` 过滤器，会混入主题运行时注入的内容（本项目实测：子主题会在每页末尾
注入「☷藏品・把五千年带在身边→」共 13 字），导致每页都"多出 13 字"的假差异——发布既消不掉也
不会破坏它，只会让你以为该发。raw 才是我们真正写进去的东西，比对它才准。

本脚本再做三层归一化后比：
  - 去 style/script
  - 去成对标签与属性
  - HTML 实体解码 + 标点字形归一（各类引号/破折号/省略号/间隔号统一）
长度相同且归一化后相同 → 判定「线上已是最新版，无需发布」。

用法：
  python3 11-运营/scripts/live-diff.py --parent 32 --dir 03-页面/朝代页   # 按父页批量
  python3 11-运营/scripts/live-diff.py --map "94:sanhuang,95:xia"          # 精确 id:slug
  python3 11-运营/scripts/live-diff.py --parent 32 --dir ... --verbose      # 打印差异样本

退出码：0 = 全部一致（无需发布）；1 = 有实质差异（该发）；2 = 取数失败。
凭据从 11-运营/wp-auth.sh 装载。
"""
import argparse
import html
import json
import os
import re
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SITE = "https://theseventhrealm.com"          # 必须 apex，www 会 301 吞掉请求

STRIP = re.compile(r"</?(p|br|div|span|section|article|header|footer|nav|ul|ol|li|"
                   r"h[1-6]|table|thead|tbody|tr|td|th|details|summary|blockquote|"
                   r"figure|figcaption|hr|dl|dt|dd|pre|code|em|strong|i|b|a)\b[^>]*>", re.I)

# 标点字形归一化表：WP 美化产物 → 标准形
PUNCT = {
    "\u201c": '"', "\u201d": '"', "\u2018": "'", "\u2019": "'",
    "\u300c": '"', "\u300d": '"', "\u300e": '"', "\u300f": '"',
    "\u2014": "-", "\u2013": "-", "\u2015": "-", "\u2500": "-",
    "\u2026": "...", "\u22ef": "...",
    "\u00a0": " ", "\u3000": " ", "\u200b": "", "\ufeff": "",
    "\u00b7": "\u30fb", "\u2027": "\u30fb",
}
PUNCT_RE = re.compile("|".join(map(re.escape, PUNCT)))


def normalize(s):
    s = re.sub(r"<(style|script)\b.*?</\1>", "", s, flags=re.S | re.I)
    s = re.sub(r"<!--.*?-->", "", s, flags=re.S)
    s = STRIP.sub("", s)
    s = re.sub(r"<[^>]+>", "", s)
    s = html.unescape(s)
    s = PUNCT_RE.sub(lambda m: PUNCT[m.group()], s)
    return re.sub(r"\s+", "", s)


def load_auth():
    """从 11-运营/wp-auth.sh 装载 WP_USER / WP_APP_PASS（不落盘）。"""
    sh = os.path.join(ROOT, "11-运营", "wp-auth.sh")
    if not os.path.exists(sh):
        return None, None
    probe = ("set -a; . " + repr(sh).replace("'", "") + " >/dev/null 2>&1; "
             "printf '%s\\n%s' \"${WP_USER:-}\" \"${WP_APP_PASS:-}\"")
    out = subprocess.run(["bash", "-c", probe], capture_output=True, text=True).stdout
    parts = out.split("\n")
    return (parts[0].strip(), parts[1].strip()) if len(parts) >= 2 else (None, None)


def fetch(user, pwd, url):
    cmd = ["curl", "-s", "-L", "--max-time", "30", "-u", f"{user}:{pwd}", url]
    r = subprocess.run(cmd, capture_output=True, text=True)
    try:
        return json.loads(r.stdout)
    except Exception:
        sys.stderr.write(f"取数失败 {url}\n{r.stdout[:200]}\n")
        return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--parent", type=int, help="父页面 ID，如 32")
    ap.add_argument("--dir", help="本地 HTML 目录（文件名需为 <slug>.html）")
    ap.add_argument("--map", help="精确指定 id:slug，逗号分隔")
    ap.add_argument("--verbose", action="store_true", help="打印首个差异样本")
    a = ap.parse_args()

    user, pwd = load_auth()
    if not user or not pwd:
        sys.stderr.write("✗ 凭据未装载（401？见 MEMORY.md B 节：重生成应用密码后写回钥匙串）\n")
        return 2

    if a.map:
        pairs = [x.split(":") for x in a.map.split(",") if ":" in x]
    elif a.parent:
        got = fetch(user, pwd, f"{SITE}/wp-json/wp/v2/pages?parent={a.parent}"
                               f"&per_page=100&_fields=id,slug")
        if not isinstance(got, list):
            return 2
        pairs = [(p["id"], p["slug"]) for p in sorted(got, key=lambda x: x["id"])]
    else:
        sys.stderr.write("需要 --parent 或 --map\n")
        return 2

    print(f"比对 {len(pairs)} 页（已归一化的可见文本，忽略 WP 排版噪音）\n")
    print(f'{"id":<6}{"slug":<11}{"线上":>7}{"本地":>7}  判定')
    diff = []
    for pid, slug in pairs:
        # context=edit 才能拿到 raw（未经 the_content 过滤器的存储内容）
        d = fetch(user, pwd, f"{SITE}/wp-json/wp/v2/pages/{pid}?context=edit&_fields=slug,content")
        if not isinstance(d, dict) or "content" not in d:
            print(f"{pid:<6}{slug:<11}  ✗ 取不到线上内容（context=edit 需要编辑权限）")
            diff.append((pid, slug, None, None, None, None))
            continue
        c = d["content"] or {}
        live = normalize(c.get("raw") or c.get("rendered") or "")
        local_path = os.path.join(ROOT, a.dir or "", f"{slug}.html")
        if not os.path.exists(local_path):
            print(f"{pid:<6}{slug:<11}  ✗ 本地缺 {local_path}")
            diff.append((pid, slug, None, None, None, None))
            continue
        local = normalize(open(local_path, encoding="utf-8").read())
        ok = live == local
        print(f'{pid:<6}{slug:<11}{len(live):>7}{len(local):>7}  '
              f'{"✓ 线上已是最新" if ok else "✗ 有实质差异"}')
        if not ok:
            n = min(len(live), len(local))
            k = next((i for i in range(n) if live[i] != local[i]), n)
            diff.append((pid, slug, k, live, local, None))

    ndiff = len(diff)
    print(f"\n结论：{len(pairs) - ndiff} 页已是最新 / {ndiff} 页待发布")
    if ndiff and a.verbose:
        for pid, slug, k, live, local, _ in diff[:3]:
            if live is None:
                continue
            print(f"\n--- {slug} 首个差异 @{k} ---")
            print("  线上:", repr(live[max(0, k - 60):k + 60]))
            print("  本地:", repr(local[max(0, k - 60):k + 60]))
    return 1 if ndiff else 0


if __name__ == "__main__":
    sys.exit(main())
