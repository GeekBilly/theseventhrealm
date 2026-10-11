#!/usr/bin/env python3
"""生成 原文/00-索引.md：把散在各子目录的录文文件编成一份总目。

用法：python3 build-index.py

说明：
  - 只读取录文文件的标题、引文条目数与字数，不改动任何录文内容（幂等）。
  - 00-索引.md 是本脚本的产物，**勿手改**；改录文后重跑本脚本即可。
"""

import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE / "原文"

# 目录 → 一句话说明（与 README 的目录结构保持一致）
DIR_DESC = {
    "01-正史": "纪传体正史，一事多书者并列",
    "02-经部": "五经与传，今古文与成书年代多有争议",
    "03-诸子": "道、法、墨、兵、儒，同一事常有两版本",
    "04-史部别体": "编年、杂史、行记、制度文献与清人考据",
    "05-科技与笔记": "科技专著与笔记杂著，多为「只见于此」的孤证",
    "06-集部诗文": "文章与诗词，作史料用而非作文学用",
    "07-小说戏曲": "小说戏曲**不是史源**，只作「后世如何理解前代」的材料",
    "08-简牍与出土文献": "出土文书，与传世文献对读（争议最密集处）",
    "09-近现代论著": "近现代学术论著（含 B 类只登记书目）",
    "10-条约与官方文件": "条约与官方文件（C 类官方文件可录可上线）",
    "11-图像与碑刻": "D 类图碑画，**只登记不复刻图像**",
}


def stat(md: Path):
    s = md.read_text(encoding="utf-8")
    title = ""
    for line in s.split("\n"):
        if line.startswith("# "):
            title = line[2:].strip()
            break
    # 录文条目的层级不统一：汇编卷用 ## 引文 N，单书文件用 ### 引文 N
    n = len(re.findall(r"^#{2,3}\s*(引文|附引)", s, flags=re.M))
    chars = len(re.findall(r"[\u4e00-\u9fff]", s))
    # 收录行（头部表格里的「收录」项）
    inc = ""
    m = re.search(r"^\|\s*收录\s*\|(.+)\|", s, flags=re.M)
    if m:
        inc = m.group(1).strip().replace("**", "")
    return title, n, chars, inc


def main():
    files = sorted(
        p for p in ROOT.rglob("*.md") if p.name != "00-索引.md"
    )
    out = []
    out.append("# 录文总索引")
    out.append("")
    out.append("> ⚠️ **本文件由 `build-index.py` 生成，勿手改。** 改了任何录文后重跑 `python3 build-index.py`。")
    out.append("")
    tot_f = tot_n = tot_c = 0
    by_dir = {}
    for p in files:
        by_dir.setdefault(p.parent.name, []).append(p)

    for d in sorted(by_dir):
        out.append("---")
        out.append("")
        desc = DIR_DESC.get(d, "")
        out.append(f"## {d}" + (f" · {desc}" if desc else ""))
        out.append("")
        out.append("| 文件 | 收录 | 引文 | 字数 |")
        out.append("|---|---|---:|---:|")
        sub_n = sub_c = 0
        for p in by_dir[d]:
            title, n, chars, inc = stat(p)
            # 写带子目录的相对路径：00-索引.md 在「原文/」根，裸文件名点不开
            rel = f"{d}/{p.name}" if p.parent.name != ROOT.name else p.name
            out.append(f"| `{rel}` | {inc or title} | {n} | {chars:,} |")
            sub_n += n
            sub_c += chars
            tot_f += 1
        tot_n += sub_n
        tot_c += sub_c
        out.append(f"| **小计** | **{len(by_dir[d])} 个文件** | **{sub_n}** | **{sub_c:,}** |")
        out.append("")

    out.append("---")
    out.append("")
    out.append("## 合计")
    out.append("")
    out.append("| 项 | 数 |")
    out.append("|---|---:|")
    out.append(f"| 录文文件 | {tot_f} |")
    out.append(f"| 引文条目 | {tot_n} |")
    out.append(f"| 中文字符 | {tot_c:,} |")
    out.append("")
    out.append("> ⚠️ **看索引时请同时记住一件事**：")
    out.append("> **条目数不等于可靠度。** 绝大多数条目仍标「节录·待校」或「需核」，")
    out.append("> **上线前须逐条核对点校本的卷次与文字。**（详见 `../README.md` 第四节末的说明）")
    out.append("")

    tgt = ROOT / "00-索引.md"
    tgt.write_text("\n".join(out), encoding="utf-8")
    print("写出 %s" % tgt)
    print("文件 %d / 引文 %d 条 / 中文 %s 字" % (tot_f, tot_n, f"{tot_c:,}"))


if __name__ == "__main__":
    main()
