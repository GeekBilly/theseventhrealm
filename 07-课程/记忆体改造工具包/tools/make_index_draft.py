#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
《谁动了我的 Token》· 索引改造稿生成器 v1.0
==================================================

它做什么
    读你的主记忆文件，把它拆成三堆：
      · 该留在上层的（每次都用得上的规矩）
      · 该下沉成一行摘要的（步骤、细则）
      · 该归档的（日志、已完成的事）
    然后生成一份**新的**改造稿文件，告诉你照着怎么改。

它不做什么
    · **绝不修改、删除、移动你的任何原文件**（只新建一个改造稿）
    · 不联网、不上传、不收集任何信息
    · 不替你做判断：哪条该留哪条该沉，它只按文字特征给建议，最终由你拍板

用法
    python3 make-index-draft.py                  # 自动在当前目录找
    python3 make-index-draft.py ~/my-project
    python3 make-index-draft.py . --main MEMORY.md --out 改造稿.md

依赖：Python 3.8+，只用标准库，零安装。
"""

import argparse
import re
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from memory_doctor import (  # noqa: E402
    ACTION_BY_CAT, find_main, read_text, split_sections, zh_len,
)

# 建议的下沉文件名（按类别给一个默认名，用户可改）
DEFAULT_NAME = {
    "步骤候选": "操作细则",
    "日志候选": "过程记录",
    "归档候选": "归档",
}


def suggest_filename(title, used):
    """从标题里提炼一个简短文件名，避开重名。"""
    t = re.sub(r"^[\d\.\s]+", "", title).strip()
    t = re.sub(r"^[一二三四五六七八九十]+[、.．]\s*", "", t).strip()
    t = re.sub(r"[（(].*?[)）]", "", t).strip()
    t = re.sub(r"[\s\-—_:：,，、]+", "", t)
    t = t[:14] or "未命名"
    name = f"{t}.md"
    i = 2
    while name in used:
        name = f"{t}-{i}.md"
        i += 1
    used.add(name)
    return name


def build_draft(root, main_path, sections):
    keep, sink, archive = [], [], []
    used = set()

    for s in sections:
        title = s["title"]
        cat = s["category"]
        if s["action"].startswith("保留"):
            keep.append(s)
        elif cat == "日志候选" or cat == "归档候选":
            archive.append(s)
        else:
            fn = suggest_filename(title, used)
            s["suggest_file"] = fn
            s["suggest_dir"] = "记忆库/" + fn
            sink.append(s)

    L = []
    W = L.append
    W("# 索引改造稿（这是稿子，不是你的原文件）")
    W("")
    W(f"- 原文件：`{main_path}`（**本次没有改动它**）")
    W(f"- 生成时间：{date.today().isoformat()}")
    W("")
    W("> 怎么用：照着下面三段，把原文件改成「上层只留第一段 + 第二段的一行摘要」。")
    W("> 改完跑一次 `memory-doctor.py`，看第一个数字有没有降下来。")
    W("")

    W("## 一、留在上层（直接保留）")
    W("")
    if keep:
        W(f"共 {len(keep)} 节，合计 {sum(s['chars'] for s in keep)} 字符。")
        W("")
        for s in keep:
            W(f"- **{s['title']}**（{s['chars']} 字符）")
    else:
        W("_没有识别到明确的保留段。_")
    W("")

    W("## 二、下沉成一行摘要")
    W("")
    W("每一节：新建一个文件放正文，上层只留一行摘要。")
    W("**摘要要写到「读完这一行就知道要不要打开那个文件」为止。**")
    W("")
    if sink:
        for s in sink:
            W(f"### {s['title']}（{s['chars']} 字符）")
            W("")
            W(f"- 新建文件：`{s['suggest_dir']}`")
            W(f"- 上层留这一行（自己补全尖括号里的内容）：")
            W("")
            W(f"  > {s['title']} — <一句话说清这个文件管什么、什么时候该打开它>")
            W("")
    else:
        W("_没有识别到需要下沉的节。_")
    W("")

    W("## 三、归档（不参与每次注入）")
    W("")
    if archive:
        W("这些内容每次都被重发一遍，但一周都没被读过。")
        W("**建议移到一个归档文件里，上层不再留条目。**")
        W("")
        for s in archive:
            W(f"- **{s['title']}**（{s['chars']} 字符）— 建议移到 `归档/{s['title'][:12]}.md`")
    else:
        W("_没有识别到明显的日志/归档段。_")
    W("")

    # 改造后的样子
    W("## 四、改造后的上层长这样（示意）")
    W("")
    keep_title = keep[0]["title"] if keep else "（你的主文件）"
    W("```markdown")
    W(f"# {keep_title}")
    W("")
    for s in keep[1:]:
        W(f"## {s['title']}")
        W("")
        W("（这一节的正文原样保留）")
        W("")
    for s in sink:
        W(f"- {s['title']} — <一句话摘要>")
    W("```")
    W("")
    W("---")
    W("")
    W("*《谁动了我的 Token》· 记忆体改造工具包*")
    W("*一个个人创作者 · hello@theseventhrealm.com*")
    return "\n".join(L)


def main():
    ap = argparse.ArgumentParser(
        description="生成索引改造稿（只新建文件，绝不改动原文件）")
    ap.add_argument("root", nargs="?", default=".", help="项目目录")
    ap.add_argument("--main", help="主记忆文件路径")
    ap.add_argument("--out", help="改造稿输出路径（默认与原文件同目录）")
    args = ap.parse_args()

    root = Path(args.root).expanduser().resolve()
    if not root.is_dir():
        print(f"❌ 找不到目录：{root}", file=sys.stderr)
        return 2

    main_path = find_main(root, args.main)
    if not main_path:
        print("❌ 没找到主记忆文件。用 --main 明确指定路径。", file=sys.stderr)
        return 2

    text = read_text(main_path)
    sections = []
    for title, body in split_sections(text):
        from memory_doctor import classify
        cat, score = classify(title + "\n" + body, body=body)
        sections.append({
            "title": title[:60],
            "chars": zh_len(body),
            "category": cat,
            "action": ACTION_BY_CAT.get(cat, "保留"),
        })

    out = Path(args.out).expanduser() if args.out else main_path.parent / "MEMORY-索引改造稿.md"
    if not out.is_absolute():
        out = root / out
    if out.exists():
        print(f"❌ 输出文件已存在，为避免覆盖我不动它：{out}\n"
              f"   请换一个 --out 路径，或先把它改名。", file=sys.stderr)
        return 1

    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(build_draft(root, main_path, sections), encoding="utf-8")
    print(f"✅ 改造稿已生成：{out}")
    print(f"   你的原文件 `{main_path}` **没有被改动**。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
