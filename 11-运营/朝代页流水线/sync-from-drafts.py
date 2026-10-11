#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把 01-内容/历史长卷/朝代稿/<slug>.md 解析成 11-运营/朝代页流水线/bodies.py。

设计原则：**不手抄正文**。线上朝代页的正文永远由朝代稿生成，
改稿后重跑本脚本 + build.py 即可同步（与成书稿 build-book.py 同一套分节规则）。

eras.py 只保留静态元数据（slug/seo/h1/sub/ghost/seal/verse/src），
lead/body/relic/close/fin/cites/dispute 一律以本脚本生成的 BODIES 为准。

用法： python3 sync-from-drafts.py            # 生成 bodies.py 并打印体检
       python3 sync-from-drafts.py --check    # 只体检，不写文件
"""

import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))          # 工作区根
DRAFT = os.path.join(ROOT, "01-内容", "历史长卷", "朝代稿")
OUT_PY = os.path.join(HERE, "bodies.py")

SLUGS = ["sanhuang", "xia", "shang", "zhou", "qin", "han", "sanguo", "jin",
         "sui", "tang", "wudai", "song", "yuan", "ming", "qing", "juexing"]

# 需要原样跳过的小节（内部用，不上线）
SKIP_HEADS = ("附：", "引用出处")


def esc(s):
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def inline(s):
    """行内标记：**加粗** → <strong>。先转义再替换。"""
    s = esc(s)
    return re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", s)


def md(s):
    """书名号不转义（esc 已处理 < >，书名号是中文字符，安全）。"""
    return s


def render_block(raw):
    """一段原始文本 → [(kind, html)]，kind ∈ p / quote"""
    out, buf = [], []

    def flush():
        if buf:
            out.append(("p", "".join(buf)))
            buf.clear()

    for ln in raw.splitlines():
        s = ln.strip()
        if s.startswith("> "):                       # 引用行（如利簋铭文）
            flush()
            out.append(("quote", s[2:].strip()))
        elif s == "":
            flush()
        else:
            buf.append(s)
    flush()
    return [(k, inline(v)) for k, v in out]


def parse_relic(raw):
    """三卡：- **字：德。** 说明文字"""
    cards = []
    for ln in raw.splitlines():
        s = ln.strip()
        if not s.startswith("- "):
            continue
        s = s[2:].strip()
        m = re.match(r"^\*\*(.)(：|:)(.+?)\*\*\s*(.*)$", s)
        if not m:
            raise ValueError("三卡解析失败：%s" % s[:40])
        k, title, desc = m.group(1), m.group(3).rstrip("。"), m.group(4)
        cards.append((k, inline(title), inline(desc)))
    return cards


def parse(path):
    text = open(path, encoding="utf-8").read()

    # 头部：# 标题（可能带年份）；其前的 > 版本说明行一律跳过
    years, started = "", False
    heads, bodies = [], []
    cur_head, cur_buf = None, []

    for ln in text.splitlines():
        if not started:
            if ln.startswith("# "):
                started = True
                m = re.search(r"[（(](.+?)[）)]", ln)
                years = m.group(1) if m else ""
            continue
        if ln.startswith("## "):
            if cur_head is not None:
                heads.append(cur_head)
                bodies.append("\n".join(cur_buf))
            cur_head, cur_buf = ln[3:].strip(), []
        else:
            cur_buf.append(ln)
    if cur_head is not None:
        heads.append(cur_head)
        bodies.append("\n".join(cur_buf))

    data = {"years": years, "lead": [], "body": [], "relic": [], "close": [],
            "fin": "", "cites": [], "dispute": "", "nsec": 0}

    for h, b in zip(heads, bodies):
        if h.startswith(SKIP_HEADS):
            if h.startswith("引用出处"):
                for ln in b.splitlines():
                    ln = ln.strip()
                    if ln.startswith("- "):
                        data["cites"].append(ln[2:].strip())
                    elif ln.startswith("说明："):
                        data["dispute"] = ln[3:].strip()
            continue
        if h == "导语":
            data["lead"] = render_block(b)
        elif h.startswith("字 · 物 · 事") or h.startswith("字 · 物 · 事"):
            data["relic"] = parse_relic(b)
        elif h == "收尾":
            data["close"] = render_block(b)
        elif h == "终句":
            # 稿里「## 终句」后常跟一条 --- 分隔线，必须滤掉
            data["fin"] = inline(" ".join(
                x.strip() for x in b.splitlines()
                if x.strip() and not x.strip().startswith("---")))
        else:
            data["body"].append((inline(h), render_block(b)))
    data["nsec"] = len(data["body"])
    return data


def main():
    check_only = "--check" in sys.argv
    all_data, errors, warnings = {}, [], []

    for slug in SLUGS:
        p = os.path.join(DRAFT, slug + ".md")
        if not os.path.exists(p):
            errors.append("缺少稿件：" + slug)
            continue
        try:
            d = parse(p)
        except Exception as ex:
            errors.append("%s 解析失败：%s" % (slug, ex))
            continue
        all_data[slug] = d

        # 体检
        if not d["lead"]:
            errors.append("%s 缺导语" % slug)
        if len(d["relic"]) != 3:
            errors.append("%s 三卡 %d 条（应为 3）" % (slug, len(d["relic"])))
        if not d["fin"]:
            errors.append("%s 缺终句" % slug)
        if d["nsec"] < 3:
            errors.append("%s 小节仅 %d 节" % (slug, d["nsec"]))
        nchar = sum(len(v) for _, blk in d["body"] for _, v in blk)
        print("  %-9s 节 %2d  段 %3d  卡 %d  引用 %2d  正文中字符 %5d  %s"
              % (slug, d["nsec"], sum(len(b) for _, b in d["body"]),
                 len(d["relic"]), len(d["cites"]), nchar, d["years"]))

        # 重复句检测：插入段落时最容易把同一句复制两遍（隋稿赵州桥就中过）
        for h, blk in d["body"]:
            text = "".join(v for _, v in blk)
            seen = {}
            for x in re.split(r"[。！？]", text):
                x = x.strip()
                if len(x) >= 12:
                    seen[x] = seen.get(x, 0) + 1
            for x, c in seen.items():
                if c >= 2:
                    warnings.append("%s · %s —— 重复 %d 次：%s……"
                                    % (slug, h[:14], c, x[:34]))

    if warnings:
        print("\n重复句告警（人工确认，不阻断）：")
        for w in warnings:
            print("  ! " + w)

    if errors:
        print("\n体检未通过：")
        for e in errors:
            print("  - " + e)
        sys.exit(1)

    if check_only:
        print("\n--check：仅体检，未写入。")
        return

    with open(OUT_PY, "w", encoding="utf-8") as fh:
        fh.write("# -*- coding: utf-8 -*-\n")
        fh.write('"""由 sync-from-drafts.py 自动生成，**请勿手改**。\n')
        fh.write("来源：01-内容/历史长卷/朝代稿/<slug>.md。改稿后重跑本目录的 sync-from-drafts.py。\n")
        fh.write('正文已转为 HTML 片段（**加粗** → <strong>，> 引用 → quote 段）。"""\n\n')
        fh.write("BODIES = {\n")
        for slug in SLUGS:
            d = all_data[slug]
            fh.write("    %r: {\n" % slug)
            fh.write("        'years': %r,\n" % d["years"])
            fh.write("        'lead': %r,\n" % d["lead"])
            fh.write("        'body': [\n")
            for h, blk in d["body"]:
                fh.write("            (%r, %r),\n" % (h, blk))
            fh.write("        ],\n")
            fh.write("        'relic': %r,\n" % (d["relic"],))
            fh.write("        'close': %r,\n" % d["close"])
            fh.write("        'fin': %r,\n" % d["fin"])
            fh.write("        'cites': %r,\n" % (d["cites"],))
            fh.write("        'dispute': %r,\n" % d["dispute"])
            fh.write("    },\n")
        fh.write("}\n")
    print("\n已生成：%s（%d 朝）" % (OUT_PY, len(all_data)))


if __name__ == "__main__":
    main()
