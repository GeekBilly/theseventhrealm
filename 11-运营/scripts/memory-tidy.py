#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""第七境 · 记忆 tidy：控 MEMORY.md 体积，把 p2 章节自动搬进分支目录。

规范见 11-运营/记忆与归档规范.md。指令写在章节标题下一行：
  <!-- tidy: rank=p2 | move-to=04-市场/长期结论.md | pointer=…… -->

用法：
  python3 11-运营/scripts/memory-tidy.py --check                    # 只体检
  python3 11-运营/scripts/memory-tidy.py --apply                    # 超预算才动手
  python3 11-运营/scripts/memory-tidy.py --apply --budget 8000

安全设计（重要）：
  - 只搬 rank=p2 的章节；没写指令的章节默认 p1，永不自动搬。
  - 搬运前写 MEMORY.md.bak；目标文件是**追加**，绝不覆盖。
  - 搬完在原地留下 pointer 行，不会失联。
"""
import argparse
import datetime
import os
import re
import shutil

ROOT = "/Users/billyhou/WorkBuddy/2026-09-25-15-56-17"
MEM = os.path.join(ROOT, ".workbuddy", "memory", "MEMORY.md")
REPORT_DIR = os.path.join(ROOT, "11-运营", "reports")

TIDY = re.compile(r"<!--\s*tidy:(.*?)-->", re.S)
FIELD = re.compile(r"(\w[\w-]*)\s*=\s*([^|]+)")


# ─────────────────────────────────────────────────────────────
# 动态预算：跟着项目规模走
# 规则见 11-运营/记忆与归档规范.md §五。设计要点：
#   · 基础不随规模变（原则/协作/凭据位置就那么多）
#   · 规模项**次线性**：项目变大时，记忆要更多用「指针」而不是更多「细节」
#   · 有硬顶：记忆每次会话全量注入，超长会被截断 → 截断后等于白记
# ─────────────────────────────────────────────────────────────
BASE = 4000          # 不随规模变：总原则指针 + 协作规范 + 凭据位置
PER_DOMAIN = 200     # 每个「活跃域」（约 2 条常驻 × 100 字符）
PER_SPEC = 100       # 每份「规范文档」（约 1 行指针 × 100 字符）
DOMAIN_FREE = 0      # 无免费额度 —— 公式越简单越不会被绕过
SPEC_FREE = 0
FLOOR, CAP = 5000, 12000

SKIP_DIRS = {".git", ".workbuddy", "99-归档", "node_modules", "__pycache__"}
SPEC_RE = re.compile(r"(README|手册|规范|流程|规则|总原则|约定|指南|SOP)", re.I)


def scan_scale():
    """量项目规模 → (活跃域数, 规范文档数, 目录数, md 总字符)

    为什么用「域数 + 规范文档数」而不是文件数：
    488 个商品文件不等于 488 条规矩，但**多一个功能域就多一组必须常驻的约束**，
    多一份规范文档就多一行必须留的指针。
    """
    doms = specs = ndirs = mdchars = 0
    try:
        tops = [d for d in os.listdir(ROOT)
                if os.path.isdir(os.path.join(ROOT, d))
                and d not in SKIP_DIRS and not d.startswith(".")]
    except OSError:
        return 0, 0, 0, 0
    for t in tops:
        n = 0
        for dp, dns, fns in os.walk(os.path.join(ROOT, t)):
            dns[:] = [d for d in dns if d not in SKIP_DIRS and not d.startswith(".")]
            ndirs += len(dns)
            n += len(fns)
            for f in fns:
                if not f.endswith(".md"):
                    continue
                if SPEC_RE.search(f):
                    specs += 1
                try:
                    with open(os.path.join(dp, f), encoding="utf-8", errors="ignore") as fh:
                        mdchars += len(fh.read())
                except OSError:
                    pass
        if n >= 5:                      # 活跃域 = 文件数 ≥5 的顶层域
            doms += 1
    return doms, specs, ndirs, mdchars


def auto_budget(verbose=False):
    doms, specs, ndirs, mdchars = scan_scale()
    b = (BASE
         + PER_DOMAIN * max(0, doms - DOMAIN_FREE)
         + PER_SPEC * max(0, specs - SPEC_FREE))
    clamped = max(FLOOR, min(CAP, b))
    scale = {"domains": doms, "specs": specs, "dirs": ndirs, "md_chars": mdchars}
    if verbose:
        print(f"  项目规模：活跃域 {doms} · 规范文档 {specs} 份 · 目录 {ndirs} · "
              f"md 合计 {mdchars:,} 字符")
        print(f"  动态预算 = {BASE} + {PER_DOMAIN}×({doms}−{DOMAIN_FREE})"
              f" + {PER_SPEC}×({specs}−{SPEC_FREE}) = {b} → 取 {clamped}"
              f"（区间 {FLOOR}–{CAP}）")
    return clamped, scale


def parse_fields(blob):
    return {k: v.strip() for k, v in FIELD.findall(blob)}


def load_sections(text):
    """按 '## ' 切块，返回 [(标题, 正文含指令, ...)]
    ⚠️ 本项目 MEMORY.md 的标题写作 '##A xxx'（**二级标题后紧跟字母、无空格**），
       旧正则 r"\\n(?=## )" 要求必须有空格 ⇒ 整个文件会被当成一块 __HEAD__，
       再叠加任一 p2 指令就会被整份搬空。此处放宽为 '##' 后接任意非 '#' 字符。
    """
    head, *rest = re.split(r"\n(?=##[^#\n])", text)
    blocks = [("__HEAD__", head)]
    for b in rest:
        lines = b.split("\n")
        blocks.append((lines[0], "\n".join(lines[1:])))
    return blocks


def meta_of(body, is_head=False):
    """解析章节标题正下方的 tidy 指令。

    安全约束（2026-10-16 加固）：
      · __HEAD__（文件头，含上位法与全局口径）**永不搬运**；
      · tidy 指令只在正文**开头 600 字符内**识别 —— 正文深处的 `<!-- tidy: -->`
        属于被搬运内容的一部分，不应被误当成当前章节的指令，
        否则整章会被自己的内容指挥搬走。
    """
    if is_head:
        return {"rank": "p0"}
    m = TIDY.search((body or "")[:600])
    if not m:
        return {"rank": "p1"}
    f = parse_fields(m.group(1))
    f.setdefault("rank", "p1")
    return f


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="只体检（默认行为，写了更清楚）")
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--budget", type=int, default=None,
                    help="手动指定预算；不给则按项目规模自动算")
    ap.add_argument("--auto", action="store_true",
                    help="按项目规模自动算预算（不写 --budget 时的默认行为）")
    args = ap.parse_args()

    scale = None
    if args.budget is None:
        args.budget, scale = auto_budget(verbose=True)
    else:
        print(f"  预算：手动指定 {args.budget} 字符（跳过自动计算）")

    text = open(MEM, encoding="utf-8").read()
    blocks = load_sections(text)
    total = len(text)
    infos = []
    for title, body in blocks:
        m = meta_of(body, is_head=(title == "__HEAD__"))
        infos.append({"title": title, "body": body, "rank": m.get("rank", "p1"),
                      "move": m.get("move-to"), "pointer": m.get("pointer")})

    line = "─" * 64
    print(line)
    print(f"MEMORY.md 体积体检 · {datetime.date.today()}")
    print(line)
    print(f"当前 {total} 字符 / 预算 {args.budget} 字符  "
          f"→ {'❌ 超预算 ' + str(total - args.budget) + ' 字符' if total > args.budget else '✅ 在预算内'}")
    print()
    print(f"{'字符':>6}  {'级别':<5} {'目标文件':<28} 章节")
    print(line)
    for i in infos:
        tgt = i["move"] or "—"
        print(f"{len(i['body']):>6}  {i['rank']:<5} {tgt:<28} {i['title'][:34]}")
    print(line)

    if scale and scale["specs"]:
        dens = total / scale["specs"]
        ratio = total / max(1, scale["md_chars"]) * 100
        print("\n效率指标（决定「该给多少」的不只是「现在有多少」）：")
        print(f"  记忆密度 {dens:.0f} 字符/份规范 "
              f"{'✅' if dens <= 250 else '❌ 偏胖 → 该下沉细节、多留指针'}（目标 ≤250）")
        print(f"  占全部 md 的 {ratio:.2f}% "
              f"{'✅' if ratio <= 0.60 else '❌ 偏胖'}（目标 ≤0.60%）")

    movable = sorted([i for i in infos if i["rank"] == "p2" and i["move"]],
                     key=lambda x: -len(x["body"]))

    if total <= args.budget or not args.apply:
        print("\n--check 模式或未超预算：不移动任何内容。" if not args.apply
              else "\n体积正常，--apply 无需动手。")
        if total > args.budget and movable:
            n = 0
            need = total - args.budget
            print(f"  提示：如需瘦身，将按 p2 从大到小搬 ——")
            for i in movable:
                print(f"    · {i['title'][:40]} ({len(i['body'])} 字符) → {i['move']}")
                n += len(i["body"])
                if n >= need:
                    break
        return

    shutil.copy(MEM, MEM + ".bak")
    report = [f"# 记忆整理 · {datetime.date.today()}", "",
              f"整理前 {total} 字符 → 目标 ≤ {args.budget} 字符", ""]
    moved = 0
    for info in movable:
        if len(open(MEM, encoding="utf-8").read()) <= args.budget:
            break
        target = os.path.join(ROOT, info["move"])
        os.makedirs(os.path.dirname(target), exist_ok=True)
        stamp = datetime.date.today().isoformat()
        pointer = info["pointer"] or f"详见 `{info['move']}`"
        body_clean = TIDY.sub("", info["body"]).strip()
        with open(target, "a", encoding="utf-8") as f:
            f.write(f"\n\n## {stamp} 归档自 MEMORY.md\n\n{body_clean}\n")
        new = []
        for title, body in load_sections(open(MEM, encoding="utf-8").read()):
            if title == info["title"]:
                new.append(f"{title}\n\n> {pointer}\n")
            else:
                new.append(title + "\n" + body if title != "__HEAD__" else body)
        open(MEM, "w", encoding="utf-8").write("\n".join(new).replace("\n\n\n", "\n\n"))
        moved += 1
        report.append(f"- `{info['title']}` （{len(info['body'])} 字符）→ `{info['move']}`，原地留指针：{pointer}")
        print(f"已搬：{info['title'][:40]} → {info['move']}")

    after = len(open(MEM, encoding="utf-8").read())
    report.append("")
    report.append(f"整理后：{after} 字符（搬出 {moved} 节，备份 MEMORY.md.bak）")
    os.makedirs(REPORT_DIR, exist_ok=True)
    rp = os.path.join(REPORT_DIR, f"记忆整理-{datetime.date.today()}.md")
    with open(rp, "w", encoding="utf-8") as f:
        f.write("\n".join(report) + "\n")
    print(f"\n整理后 {after} 字符（搬出 {moved} 节）· 报告 {rp}")


if __name__ == "__main__":
    main()
