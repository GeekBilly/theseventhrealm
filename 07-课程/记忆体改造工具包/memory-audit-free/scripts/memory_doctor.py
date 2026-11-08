#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
《谁动了我的 Token》· 记忆体体检工具 v1.0
==================================================

它做什么
    读你的项目记忆文件，算出三件事：
      1. 你的记忆文件现在多大？（每次对话都要被塞进去一遍）
      2. 里面有多少是「每次都用得上」的，有多少是「以防万一」的？
      3. 压到目标大小，你每月能少烧多少额度？

它不做什么
    · 不修改、不删除、不移动你的任何文件（只读）
    · 不联网，不上传，不收集任何信息
    · 不猜你的项目是什么，只按文字特征做启发式判断

用法
    python3 memory-doctor.py                  # 自动在当前目录找
    python3 memory-doctor.py ~/my-project     # 指定项目目录
    python3 memory-doctor.py . --main MEMORY.md --subdir 记忆库 --subdir docs
    python3 memory-doctor.py . --json         # 输出 JSON，便于你自己再做处理

依赖：Python 3.8+，只用标准库，零安装。
"""

import argparse
import json
import os
import re
import sys
from pathlib import Path

# ── 配置 ──────────────────────────────────────────────────────────────

# 主记忆文件的候选名（按优先级）
MAIN_CANDIDATES = [
    "MEMORY.md", "MEMORY.MD", "memory.md",
    "MEMORY-主索引.md", "AGENTS.md", "CLAUDE.md", ".memory.md",
]

# 下沉目录的候选名
SUBDIR_CANDIDATES = [
    "记忆库", "记忆", "memory", "memories", "docs/memory", ".workbuddy/memory",
    "docs/记忆库", "notes", "knowledge",
]

# 建议的目标大小（字符）。超过就该压。
TARGET_BUDGET = 3000

# 分类启发式关键词（顺序即优先级）
RULES = {
    "索引候选": [
        "索引", "目录", "路由", "导航", "红线", "宪法", "真源", "导航表",
        "速查", "指路", "分层",
    ],
    "归档候选": [
        "已完成", "已上线", "已归档", "已发布", "做完了", "结项", "归档",
        "完成记录", "历史遗留", "旧版", "作废",
    ],
    "日志候选": [
        "日志", "流水", "执行记录", "每日", "晨检", "巡检", "变更记录",
        "快照", "时间线", "过程记录",
    ],
    "步骤候选": [
        "第一步", "第二步", "第三步", "步骤", "操作流程", "流程如下",
        "如何操作", "教程", "步骤如下", "先执行", "再执行", "操作手册",
        "怎么改", "如何修改",
    ],
    "原则候选": [
        "不要", "必须", "禁止", "铁律", "优先", "红线", "一律", "只能",
        "务必", "永远", "口径",
    ],
}

# 章节标题的正则（## / ### / # 开头）。允许标题符后无空格（有些人的文件写成 "##A 宪法"）
HEADING_RE = re.compile(r"^(#{1,4})\s*(\S.*?)\s*$", re.M)
DATE_HEAD_RE = re.compile(r"(20\d{2})[-年/](\d{1,2})[-月/](\d{1,2})")
LOG_LINE_RE = re.compile(r"^\s*[-*]\s*\d{4}-\d{2}-\d{2}")
ONLY_NUM_HEAD_RE = re.compile(r"^[\d\.\s]+$")

# 类别 → 处置动作
ACTION_BY_CAT = {
    "索引候选": "保留在上层",
    "原则候选": "保留在上层",
    "保留候选": "保留在上层",
    "步骤候选": "下沉成一行摘要",
    "日志候选": "归档（不参与注入）",
    "归档候选": "归档（已做完）",
}


def zh_len(s):
    """中文字符按 1 计，英文按 0.5 计，粗略衡量「体量」。"""
    n = 0.0
    for ch in s:
        n += 0.5 if ord(ch) < 128 else 1.0
    return int(round(n))


def find_main(root, explicit=None):
    if explicit:
        p = Path(explicit).expanduser()
        if not p.is_absolute():
            p = root / p
        return p if p.exists() else None
    for name in MAIN_CANDIDATES:
        p = root / name
        if p.exists() and p.is_file():
            return p
    # 再兜一层：根目录下含 memory 关键字的 md
    try:
        for p in sorted(root.glob("*.md")):
            if "memory" in p.name.lower() or "记忆" in p.name:
                return p
    except OSError:
        pass
    return None


def find_subdirs(root, explicit_list):
    dirs = []
    if explicit_list:
        for d in explicit_list:
            p = Path(d).expanduser()
            if not p.is_absolute():
                p = root / p
            if p.is_dir():
                dirs.append(p)
        return dirs
    for name in SUBDIR_CANDIDATES:
        p = root / name
        if p.is_dir():
            dirs.append(p)
    # 去重
    seen, out = set(), []
    for d in dirs:
        r = str(d.resolve())
        if r not in seen:
            seen.add(r)
            out.append(d)
    return out


def classify(text, body=None, title=None):
    """给一段文字打分，返回 (类别, 得分)。

    规则顺序＝优先级：
        索引 > 归档 > 日志 > 步骤 > 原则 > 保留（默认保守）
    标题里带日期或带「记录」→ 日志；但「索引」类关键词优先级更高，
    所以纯索引文件（标题带日期）不会被误判成日志。
    """
    body = body if body is not None else text
    title = title if title is not None else ""
    low = text.lower()
    scores = {}
    for cat, kws in RULES.items():
        scores[cat] = sum(low.count(k.lower()) for k in kws)

    # 正文里成片出现日期条目 → 日志
    date_lines = len(re.findall(r"^\s*[-*]?\s*20\d{2}[-/]\d{1,2}[-/]\d{1,2}", body, re.M))
    if date_lines >= 2:
        scores["日志候选"] += date_lines

    # 标题本身带日期 / 带「记录」→ 日志候选
    if DATE_HEAD_RE.search(title):
        scores["日志候选"] += 3
    if re.search(r"记录|日志|流水|快照", title):
        scores["日志候选"] += 2
    if date_lines >= 2:
        scores["日志候选"] += date_lines
    if DATE_HEAD_RE.search(body) and date_lines == 0:
        # 正文有日期但不是条目行（例如「2026-11-08 · 纯索引」这种抬头）→ 不加日志分
        pass

    # 命中索引类关键词就直接判索引（索引层天然是上层）
    if scores["索引候选"] > 0:
        return "索引候选", scores["索引候选"]

    best = max(scores, key=lambda k: scores[k])
    if scores[best] == 0:
        return "保留候选", 0
    return best, scores[best]


def split_sections(text):
    """把主记忆文件切成若干节：(标题, 正文)。"""
    parts = []
    matches = list(HEADING_RE.finditer(text))
    if not matches:
        return [("（无标题，整份文件）", text)]
    if matches[0].start() > 0:
        parts.append(("（开头前言）", text[: matches[0].start()]))
    for i, m in enumerate(matches):
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        parts.append((m.group(2).strip(), text[m.start(): end]))
    return parts


def read_text(p):
    for enc in ("utf-8", "utf-8-sig", "gb18030", "latin-1"):
        try:
            return p.read_text(encoding=enc)
        except (UnicodeDecodeError, OSError):
            continue
    return ""


def scan(root, main_path, subdirs):
    result = {
        "root": str(root),
        "main": None,
        "sections": [],
        "subfiles": [],
        "orphans": [],
        "missing_refs": [],
    }

    text = read_text(main_path)
    result["main"] = {
        "path": str(main_path),
        "chars": zh_len(text),
        "raw_bytes": len(text.encode("utf-8")),
        "lines": text.count("\n") + 1,
        "sections": len(split_sections(text)),
    }

    # 分节 + 分类
    for title, body in split_sections(text):
        cat, score = classify(title + "\n" + body, body=body, title=title)
        result["sections"].append({
            "title": title[:60],
            "chars": zh_len(body),
            "category": cat,
            "score": score,
            "action": ACTION_BY_CAT.get(cat, "保留"),
        })

    # 下沉文件
    names = []
    for d in subdirs:
        try:
            for p in sorted(d.rglob("*.md")):
                if p.name == main_path.name and p.resolve() == main_path.resolve():
                    continue
                body = read_text(p)
                names.append(p.name)
                result["subfiles"].append({
                    "path": str(p),
                    "name": p.name,
                    "chars": zh_len(body),
                })
        except OSError:
            continue

    # 引用关系：主文件里提到了哪些下沉文件的名字
    for f in result["subfiles"]:
        stem = Path(f["name"]).stem
        if f["name"] in text or stem in text:
            f["referenced"] = True
        else:
            f["referenced"] = False
            result["orphans"].append(f["name"])

    # 主文件里提到的 md 路径，但磁盘上找不到
    # 允许带相对路径（如 11-运营/记忆库/xxx.md），在多个可能位置探测
    search_dirs = [root, main_path.parent] + list(subdirs)
    for m in re.finditer(r"[\w\u4e00-\u9fff\-/\.]+\.md", text):
        nm = m.group(0)
        if nm in names or nm == main_path.name:
            continue
        if any((d / nm).exists() for d in search_dirs):
            continue
        # 只写了文件名、且文件确实不在任何下沉目录里 → 真·失效引用
        base = Path(nm).name
        if base in names:
            continue
        if nm not in result["missing_refs"]:
            result["missing_refs"].append(nm)

    return result


def analyze(res):
    total = res["main"]["chars"]
    keep = sum(s["chars"] for s in res["sections"] if s["action"].startswith("保留"))
    sink = sum(s["chars"] for s in res["sections"] if not s["action"].startswith("保留"))
    ratio = (sink / total * 100) if total else 0

    # 只有「下沉」类节压成一行摘要（约 40 字/节）；归档/日志节直接移出注入
    n_sink_sections = sum(1 for s in res["sections"] if s["action"].startswith("下沉"))
    n_gone_sections = sum(1 for s in res["sections"]
                          if s["action"].startswith("归档"))
    after = min(keep + n_sink_sections * 40, total)

    sub_total = sum(f["chars"] for f in res["subfiles"])
    orphans = len(res["orphans"])

    # 成本估算：高度 ≈ 主记忆体量（字符）；token ≈ 字符 × 0.7
    def tok(c):
        return int(c * 0.7)

    saved_pct = ((total - after) / total * 100) if total else 0

    return {
        "total": total,
        "keep": keep,
        "sink": sink,
        "sink_ratio": round(ratio, 1),
        "after": after,
        "saved_pct": round(saved_pct, 1),
        "n_sections": len(res["sections"]),
        "n_sink_sections": n_sink_sections,
        "sub_total": sub_total,
        "n_subfiles": len(res["subfiles"]),
        "orphans": orphans,
        "orphan_chars": sum(
            f["chars"] for f in res["subfiles"] if not f.get("referenced")
        ),
        "tokens_now": tok(total),
        "tokens_after": tok(after),
        "tokens_saved": tok(total) - tok(after),
        "missing_refs": res["missing_refs"],
    }


def report(res, a, rounds_per_month=None, cost_per_1k=None):
    L = []
    W = L.append
    W("# 记忆体体检报告")
    W("")
    W(f"扫描目录：`{res['root']}`")
    W(f"主记忆文件：`{res['main']['path']}`")
    W("")
    W("## 一、三个数字（先量清楚）")
    W("")
    W("| # | 要量的东西 | 你的数字 |")
    W("|---|---|---|")
    W(f"| 1 | 记忆文件现在多少字符 | **{a['total']}** |")
    W(f"| 2 | 里面「每次都用得上」的部分 | **{a['keep']}** |")
    W(f"| 3 | 「以防万一」的部分（占比） | **{a['sink']}**（{a['sink_ratio']}%） |")
    W("")
    if a["total"] > TARGET_BUDGET:
        W(f"> ⚠️ 超过建议上限 **{TARGET_BUDGET}** 字符。"
          f"每次对话都要重发一遍，这就是账单被扣掉的地方。")
    else:
        W(f"> ✅ 在建议上限 {TARGET_BUDGET} 字符以内，控制得不错。")
    W("")

    W("## 二、哪些节该留着，哪些该下沉")
    W("")
    W("| 章节 | 体量 | 判断 |")
    W("|---|---|---|")
    for s in res["sections"]:
        W(f"| {s['title']} | {s['chars']} | {s['action']} |")
    W("")

    W("## 三、下沉文件体检")
    W("")
    W(f"- 下沉文件 **{a['n_subfiles']}** 个，合计 **{a['sub_total']}** 字符")
    W(f"- **孤儿文件 {a['orphans']}** 个（主文件里从没提到过，白占地方）：")
    if res["orphans"]:
        for f in res["subfiles"]:
            if not f.get("referenced"):
                W(f"  - `{f['name']}`（{f['chars']} 字符）")
    else:
        W("  - 无，说明索引和内容是对得上的 👍")
    if a["missing_refs"]:
        W(f"- ⚠️ 主文件里引用了但磁盘上找不到：**{', '.join(a['missing_refs'][:8])}**")
    W("")

    W("## 四、压到目标大小能省多少")
    W("")
    W(f"- 现在：**{a['total']}** 字符 ≈ **{a['tokens_now']:,}** tokens/次注入")
    W(f"- 改造后：**{a['after']}** 字符 ≈ **{a['tokens_after']:,}** tokens/次注入")
    W(f"- 每次省 **{a['tokens_saved']:,}** tokens（降 **{a['saved_pct']}%）")
    W("")

    if rounds_per_month and cost_per_1k:
        monthly_saved = a["tokens_saved"] * rounds_per_month / 1000 * cost_per_1k
        W(f"**按你填的数字算**：每月 {rounds_per_month} 轮 × "
          f"每千 token ¥{cost_per_1k} → 每月约省 **¥{monthly_saved:.0f}**，"
          f"一年约 **¥{monthly_saved * 12:.0f}**。")
        W("")
        W("> 怎么填这两个数：`--rounds` 是你一天大概开几轮对话 × 30；"
          "`--cost` 是你用的模型每千 token 多少钱（按你账单上的实际单价填，别用官方的）。")
        W("")

    W("## 五、下一步")
    W("")
    W("1. 看第二节的表，把「下沉成一行摘要」和「归档」两类标出来；")
    W("2. 运行 `make-index-draft.py` 生成改造稿（**它只写新文件，绝不碰你的原文件**）；")
    W("3. 对照着改，改完再跑一次本脚本，看第一个数字有没有降下来。")
    W("")
    return "\n".join(L)


def main():
    ap = argparse.ArgumentParser(
        description="《谁动了我的 Token》记忆体体检工具（只读，不改任何文件）")
    ap.add_argument("root", nargs="?", default=".", help="项目目录（默认当前目录）")
    ap.add_argument("--main", help="主记忆文件路径（不填则自动找）")
    ap.add_argument("--subdir", action="append", default=[],
                    help="下沉目录，可重复指定")
    ap.add_argument("--rounds", type=int, help="每月对话轮数（用于算省钱）")
    ap.add_argument("--cost", type=float, help="每千 token 的价格（元）")
    ap.add_argument("--json", action="store_true", help="输出 JSON")
    args = ap.parse_args()

    root = Path(args.root).expanduser().resolve()
    if not root.is_dir():
        print(f"❌ 找不到目录：{root}", file=sys.stderr)
        return 2

    main_path = find_main(root, args.main)
    if not main_path:
        print("❌ 没找到主记忆文件。\n"
              "   本工具会在项目根目录找这些名字之一：\n"
              "     " + "、".join(MAIN_CANDIDATES) + "\n"
              "   或用 --main 明确指定路径。", file=sys.stderr)
        return 2

    subdirs = find_subdirs(root, args.subdir)
    res = scan(root, main_path, subdirs)
    a = analyze(res)

    if args.json:
        print(json.dumps({"summary": a, "report": res}, ensure_ascii=False, indent=2))
        return 0

    print(report(res, a, args.rounds, args.cost))
    if a["total"] > TARGET_BUDGET:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
