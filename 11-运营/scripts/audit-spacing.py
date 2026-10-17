#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""全站垂直节奏审计：把每个页面实际生效的间距值列出来。

只认「页面正文里的内联 <style>」——qijing.css 是主题文件，改不了，
所以覆盖只能靠页面内联；审计也只看内联，避免误以为改了主题就全站生效。

用法：
  python3 11-运营/scripts/audit-spacing.py 11-运营/上线备份/spacing-20261017
  python3 11-运营/scripts/audit-spacing.py --css      # 只看主题样式表
"""
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
SKIP_MARKERS = ("wp-block-synced", "ml-form-embedContainer", "wp-smiley",
                "skip-link", ".qjcos-")

KEYS = [
    ("section", r"section\s*\{[^}]*?\bpadding\s*:\s*([^;}]+)"),
    (".verse", r"\.verse\s*\{[^}]*?\bpadding\s*:\s*([^;}]+)"),
    (".prose p", r"\.prose\s+p\s*\{[^}]*?\bmargin\s*:\s*([^;}]+)"),
    (".prose h2", r"\.prose\s+h2\s*\{[^}]*?\bmargin\s*:\s*([^;}]+)"),
    (".finale", r"\.finale\s*\{[^}]*?\bpadding\s*:\s*([^;}]+)"),
    (".final-line", r"\.final-line\s*\{[^}]*?\bmargin[^:]*:\s*([^;}]+)"),
    ("footer", r"footer\s*\{[^}]*?\bpadding\s*:\s*([^;}]+)"),
]


def styles(text):
    """抽出页面自己写的 style 块（跳过 WP 生成的与动画片段）。"""
    out = []
    for m in re.finditer(r"<style[^>]*>(.*?)</style>", text, re.S):
        b = m.group(1)
        if len(b) > 20000:
            continue
        head = b.lstrip()[:160]
        if any(k in head for k in SKIP_MARKERS):
            continue
        out.append(b)
    return "\n".join(out)


def main():
    if "--css" in sys.argv:
        p = ROOT / "seventhrealm-child/assets/qijing.css"
        css = p.read_text(encoding="utf-8")
        print("主题样式表", p)
        for name, pat in KEYS:
            for m in re.finditer(pat, css):
                print(f"  {name:12s} {m.group(1).strip()}")
        return

    d = pathlib.Path(sys.argv[1]) if len(sys.argv) > 1 else None
    if not d or not d.exists():
        sys.exit("用法：audit-spacing.py <备份目录> | --css")

    rows = []
    for f in sorted(d.glob("*.html")):
        s = f.read_text(encoding="utf-8")
        css = styles(s)
        vals = {}
        for name, pat in KEYS:
            m = re.search(pat, css)
            if m:
                vals[name] = m.group(1).strip()
        rows.append((f.stem, len(re.findall(r"<section", s)), vals))

    # 按 section padding 分组汇总
    from collections import Counter
    c = Counter(v.get("section", "(未覆盖→主题 68px)") for _, _, v in rows)
    print("=== section padding 分布（页面内联覆盖）===")
    for k, n in c.most_common():
        print(f"  {n:>2} 页  {k}")
    print("\n=== 逐页明细（只列有覆盖的）===")
    for name, nsec, v in rows:
        if v:
            print(f"  {name:22s} section×{nsec}  " +
                  " | ".join(f"{k}={val}" for k, val in v.items()))
    print(f"\n共 {len(rows)} 页；有内联覆盖 {sum(1 for _, _, v in rows if v)} 页")


if __name__ == "__main__":
    main()
