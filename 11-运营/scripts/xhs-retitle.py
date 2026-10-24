#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
姓氏日更 25 篇文案 · 标题与正文统一改版（2026-10-25 用户定）

标题格式（用户 2026-10-25 定）：`百家姓手机壁纸｜{四姓}，原图私信我`（18 字，不截断）
同时：
  ① 从源头删掉标题行末尾的「（N 字）」字数标注（不再依赖 xhs-draft.mjs 剥离）
  ② 正文首句 `【第 N 天 · XXXX】` → `{四姓}，四个姓，四种写法。`
  ③ 钩子改一步动作：`后台 dd 我「壁纸」，告诉你怎么领` → `后台发我「壁纸」，高清图私给你`
  ④ 报姓钩子：`没看到自己的姓？…做给你，做完私信你` → `没有你的姓？…我做完私信你`
  ⑤ 品类句：`…的四种写法，手机壁纸，…` → `…的手机壁纸，无水印，…`

用法：
    python3 11-运营/scripts/xhs-retitle.py --dry              # 只打印变化，不写盘
    python3 11-运营/scripts/xhs-retitle.py --apply             # 落盘
    python3 11-运营/scripts/xhs-retitle.py --dry --only=D06    # 只看某一篇

幂等：只匹配旧格式，已改过的篇再跑无变化。零联网零积分。
"""
import os, re, sys

DRAFT_DIR = "/Users/billyhou/WorkBuddy/2026-09-25-15-56-17/04-市场/03-推广获客/姓氏日更-202610"
TITLE_TPL = "百家姓手机壁纸｜{s}，原图私信我"

# (标签, 正则, 替换函数) —— 替换函数签名 (match, 四姓)
RULES = [
    ("标题行", r"\*\*标题\*\*：[^\n]*",
     lambda m, s: "**标题**：" + TITLE_TPL.format(s=s)),
    ("正文首句", r"【第\s*\d+\s*天\s*·\s*[^\]】]*】",
     lambda m, s: f"{s}，四个姓，四种写法。"),
    ("钩子", r"要原图：[^，]*，\s*告诉你怎么领。",
     lambda m, s: "要原图：后台发我「壁纸」，高清图私给你。"),
    ("报姓钩子", r"没看到自己的姓\？[^。]*，\s*做完私信你。",
     lambda m, s: "没有你的姓？评论区报一个字，我做完私信你。"),
    ("品类句", r"这四张是「([^」]*)」的四种写法，手机壁纸，",
     lambda m, s: f"这四张是「{m.group(1)}」的手机壁纸，无水印，"),
]


def surname_of(fname):
    m = re.match(r"^D\d\d-(.+)\.md$", fname)
    return m.group(1) if m else None


def process(path, s, apply):
    src = open(path, encoding="utf-8").read()
    out, hits = src, []
    for label, pat, tpl in RULES:
        new, n = re.subn(pat, lambda m: tpl(m, s), out)
        if n:
            hits.append(f"{label}×{n}")
            out = new
    if hits and apply:
        open(path, "w", encoding="utf-8").write(out)
    return hits


def main():
    dry = "--dry" in sys.argv
    apply = "--apply" in sys.argv
    only = None
    for a in sys.argv:
        if a.startswith("--only="):
            only = [x.strip() for x in a.split("=", 1)[1].split(",") if x.strip()]

    if not (dry or apply):
        print("必须指定 --dry 或 --apply")
        sys.exit(2)

    files = sorted(f for f in os.listdir(DRAFT_DIR) if re.match(r"^D\d\d-.+\.md$", f))
    if only:
        files = [f for f in files if f.split("-")[0] in only]

    changed = 0
    for f in files:
        s = surname_of(f)
        if not s:
            continue
        hits = process(os.path.join(DRAFT_DIR, f), s, apply)
        if hits:
            changed += 1
        print(f"{f[:3]}  {','.join(hits) if hits else '无变化（已是新版）'}")

    print(f"\n{'[干跑] ' if dry else ''}共 {len(files)} 篇，本次改了 {changed} 篇")
    if dry:
        print("未写盘。确认后跑：python3 11-运营/scripts/xhs-retitle.py --apply")


if __name__ == "__main__":
    main()
