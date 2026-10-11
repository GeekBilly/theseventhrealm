#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
成书稿构建脚本（③ 阶段）

用法：  python3 build-book.py

做四件事：
  1) 由 历史长卷/事件库/all.csv 生成 01-年表.md（按朝分组，113 节点）
  2) 把 历史长卷/朝代稿/<slug>.md 转成 正文/NN-<朝代>.md（去掉内部版本说明、11-运营 对照表；引用出处移到索引）
  3) 汇总 16 稿的引用出处 → 03-引用索引.md（分章 + 去重典籍名录）
  4) 把 卷首/年表/16 章/引用索引/后记 合成 上下五千年.md（全书单一文件）

幂等：可反复运行，输出会被覆盖。
"""

import csv
import os
import re
from collections import OrderedDict

BASE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(BASE)                      # 01-内容/
DRAFT = os.path.join(ROOT, "历史长卷", "朝代稿")
EVENTS = os.path.join(ROOT, "历史长卷", "事件库", "all.csv")
BODY = os.path.join(BASE, "正文")
OUT = os.path.join(BASE, "上下五千年.md")

# 章序：(slug, 章名, 年表分组用的朝代名)
CHAPTERS = [
    ("sanhuang", "三皇五帝", "三皇五帝"),
    ("xia", "夏", "夏"),
    ("shang", "商", "商"),
    ("zhou", "周", "周"),
    ("qin", "秦", "秦"),
    ("han", "汉", "汉"),
    ("sanguo", "三国", "三国"),
    ("jin", "两晋南北朝", "两晋南北朝"),
    ("sui", "隋", "隋"),
    ("tang", "唐", "唐"),
    ("wudai", "五代十国", "五代十国"),
    ("song", "宋", "宋"),
    ("yuan", "元", "元"),
    ("ming", "明", "明"),
    ("qing", "清", "清"),
    ("juexing", "觉醒年代", "觉醒年代"),
]

CN = "零一二三四五六七八九十"


def cn_num(n):
    """1 → 一；10 → 十；16 → 十六（章序号用）"""
    d = "零一二三四五六七八九"
    n = int(n)
    if n < 10:
        return d[n]
    if n == 10:
        return "十"
    if n < 20:
        return "十" + d[n - 10]
    return d[n // 10] + "十" + (d[n % 10] if n % 10 else "")


def year_cn(n):
    """前1046 → 前一〇四六；1912 → 一九一二（用于章序号旁的年份显示）"""
    n = abs(int(n))
    digits = "".join(CN[int(c)] for c in str(n))
    return digits


def fmt_year(y):
    y = int(y)
    return "前 %d" % (-y) if y < 0 else str(y)


# ---------------- 1) 年表 ----------------
def build_chronology():
    rows = []
    with open(EVENTS, encoding="utf-8-sig") as fh:
        for r in csv.DictReader(fh):
            rows.append(r)

    order = {dyn: i for i, (_, _, dyn) in enumerate(CHAPTERS)}
    groups = OrderedDict()
    for r in rows:
        groups.setdefault(r["所属朝代"], []).append(r)

    lines = ["# 年表", "",
             "> 113 个节点，按朝代分组，组内按年份升序。"
             "年份栏：**「前 X」表示公元前**；传说纪年与确年不详者在事件栏注明（传说 / 约 / 有争议）。",
             "> 底本：`历史长卷/事件库/all.csv`。改动事件库后重跑 `build-book.py` 即可同步。", ""]

    for _, _, dyn in CHAPTERS:
        items = groups.get(dyn, [])
        if not items:
            continue
        items.sort(key=lambda r: int(r["年份"]))
        span = "%s — %s" % (fmt_year(items[0]["年份"]), fmt_year(items[-1]["年份"]))
        lines.append("## %s（%s）· %d 条" % (dyn, span, len(items)))
        lines.append("")
        lines.append("| 年份 | 事件 | 一句话 |")
        lines.append("|---|---|---|")
        for r in items:
            ev = r["事件"].replace("|", "｜")
            on = r["一句话"].replace("|", "｜")
            lines.append("| %s | %s | %s |" % (fmt_year(r["年份"]), ev, on))
        lines.append("")

    lines.append("---")
    lines.append("")
    lines.append("合计 %d 条。" % len(rows))
    path = os.path.join(BASE, "01-年表.md")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines))
    return len(rows), path


# ---------------- 2) 章节 ----------------
def split_sections(text):
    """按 '## ' 切成 [(标题, 内容)]，文档开头部分标题为 None"""
    parts = re.split(r"\n(?=## )", text)
    out = []
    for p in parts:
        p = p.strip("\n")
        if not p.strip():
            continue
        m = re.match(r"## (.+)", p)
        if m:
            out.append((m.group(1).strip(), p[m.end(1):].lstrip("\n")))
        else:
            out.append((None, p))
    return out


def build_chapter(idx, slug, name):
    src = os.path.join(DRAFT, "%s.md" % slug)
    s = open(src, encoding="utf-8").read()

    # 取首行标题里的起止年
    m = re.match(r"# (.+?)（(.+?)）", s)
    title_raw, years = (m.group(1).strip(), m.group(2).strip()) if m else (name, "")

    # 去掉开头的内部版本说明（> 引用块）
    s = re.sub(r"^(>\s.*\n)+", "", s, count=1)

    secs = split_sections(s)
    keep, cites, dispute = [], [], None
    for head, body in secs:
        if head is None:
            continue
        if head.startswith("附："):
            continue                                  # 11-运营 对照表不出书
        if head.startswith("引用出处"):
            for ln in body.splitlines():
                ln = ln.strip()
                if ln.startswith("- "):
                    cites.append(ln[2:].strip())
                elif ln.startswith("说明：") and not ln.startswith("---"):
                    dispute = ln[3:].strip()
            continue
        keep.append((head, body.rstrip()))

    head_line = "# 第%s章 · %s" % (cn_num(idx + 1), name)
    if years:
        head_line += "（%s）" % years

    out = [head_line, ""]
    if years:
        out += ["> %s" % years, ""]
    for head, body in keep:
        out += ["## %s" % head, "", body, ""]
    if dispute:
        while out and out[-1] in ("", "---"):
            out.pop()
        out += ["", "---", "", "## 本朝争议", "", dispute, ""]

    path = os.path.join(BODY, "%02d-%s.md" % (idx + 1, name))
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(out).rstrip() + "\n")
    return path, cites, (title_raw, years)


# ---------------- 3) 引用索引 ----------------
BOOK_RE = re.compile(r"[《【]([^》】]{2,})[》】]")


def build_index(all_cites):
    lines = ["# 引用索引", "",
             "> 全书 16 章引用出处汇总。上编按章列出，下编是去重后的典籍名录。"
             "凡正文中以「有争议 / 一般认为」标出的议题，均在各章末尾的「本朝争议」中集中说明。", ""]

    lines += ["## 上编 · 分章出处", ""]
    for idx, (slug, name) in enumerate([(c[0], c[1]) for c in CHAPTERS]):
        cites = all_cites.get(slug, [])
        lines.append("### 第%s章 · %s（%d 条）" % (cn_num(idx + 1), name, len(cites)))
        lines.append("")
        for c in cites:
            lines.append("- %s" % c)
        lines.append("")

    books = OrderedDict()
    for slug, cites in all_cites.items():
        for c in cites:
            for b in BOOK_RE.findall(c):
                b = b.strip()
                if len(b) < 2:
                    continue
                book = b.split(" · ")[0].split(" ·")[0].strip()   # 去掉篇名，只留书名
                if len(book) < 2:
                    continue
                books.setdefault(book, set()).add(slug)

    lines += ["---", "", "## 下编 · 典籍名录（去重，按书名归并）", "",
              "共 %d 种（书名后为该书被引用的章；具体篇目见上编各章）。" % len(books), ""]
    for b, slugs in sorted(books.items(), key=lambda kv: -len(kv[1])):
        names = "、".join(CHAPTERS[[c[0] for c in CHAPTERS].index(s)][1] for s in slugs)
        lines.append("- **%s** —— %s" % (b, names))
    lines.append("")

    path = os.path.join(BASE, "03-引用索引.md")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines))
    return len(books), path


# ---------------- 4) 合成全书 ----------------
def assemble():
    parts = []
    for f in ["00-卷首.md", "01-年表.md"]:
        p = os.path.join(BASE, f)
        if os.path.exists(p):
            parts.append(open(p, encoding="utf-8").read().rstrip())
    parts.append("# 正文")
    for idx, (slug, name) in enumerate([(c[0], c[1]) for c in CHAPTERS]):
        p = os.path.join(BODY, "%02d-%s.md" % (idx + 1, name))
        if os.path.exists(p):
            parts.append(open(p, encoding="utf-8").read().rstrip())
    for f in ["03-引用索引.md", "04-后记.md"]:
        p = os.path.join(BASE, f)
        if os.path.exists(p):
            parts.append(open(p, encoding="utf-8").read().rstrip())
    with open(OUT, "w", encoding="utf-8") as fh:
        fh.write("\n\n---\n\n".join(parts) + "\n")
    return OUT


def main():
    n, p1 = build_chronology()
    print("年表：%d 节点 → %s" % (n, p1))
    all_cites = OrderedDict()
    total = 0
    for i, (slug, name, _) in enumerate(CHAPTERS):
        path, cites, meta = build_chapter(i, slug, name)
        all_cites[slug] = cites
        total += len(cites)
        print("第 %2d 章 %-6s 引用 %2d 条 → %s" % (i + 1, name, len(cites), os.path.basename(path)))
    nb, p3 = build_index(all_cites)
    print("引用索引：%d 条出处 / %d 种典籍 → %s" % (total, nb, p3))
    print("全书 → %s" % assemble())


if __name__ == "__main__":
    main()
