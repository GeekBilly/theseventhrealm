#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""第七境 · 每日上下文瘦身与会话交接

为什么要有这个脚本：
  会话成本 ≈ 会话历史长度，而每个新会话还会**固定注入** MEMORY.md + NOW.md。
  压这两个＝直接砍掉每天的「起步价」，是所有降本手段里唯一能天天生效的。

  注意一个反直觉的事实：**每日日志不进上下文**（只有 MEMORY.md / NOW.md 会被注入），
  所以本脚本的主力是压 MEMORY + NOW，日志只在超阈值时提醒蒸馏，绝不自动删。

用法：
  python3 context-daily-slim.py --check              # 只体检（默认）
  python3 context-daily-slim.py --apply              # 压缩 + 生成交接文档
  python3 context-daily-slim.py --check --json       # 晨检机器读

安全设计：
  - 🔴 **只移动不删除**：NOW.md 非核心区块整段 append 进 NOW-下沉-*.md（原文一字不改）
  - 🔴 **保护工作台**：NOW.md 里被 build-workbench.py 依赖的三个标题（正在进行／下一步／阻塞）永不搬
  - MEMORY.md 的压减**委托**给既有 memory-tidy.py（它自带超预算判断 + .bak + 追加 + pointer），
    本脚本不重复实现，避免出现第二套记忆处理逻辑
  - 未命中 file-history-unavailable 全部降级：任何异常都 exit 0，不阻塞晨检
"""
import argparse
import datetime
import json
import os
import re
import subprocess
import sys

ROOT = "/Users/billyhou/WorkBuddy/2026-09-25-15-56-17"
MEM_DIR = os.path.join(ROOT, ".workbuddy", "memory")
MEM_MD = os.path.join(MEM_DIR, "MEMORY.md")
NOW_MD = os.path.join(MEM_DIR, "NOW.md")
REPORT_DIR = os.path.join(ROOT, "11-运营", "reports")
SCRIPTS = os.path.join(ROOT, "11-运营", "scripts")
HANDOFF = os.path.join(REPORT_DIR, "会话交接-latest.md")
TIDY = os.path.join(SCRIPTS, "memory-tidy.py")
PY = sys.executable or "/Users/billyhou/.workbuddy/binaries/python/versions/3.13.12/bin/python3"

NOW_BUDGET = 6000        # NOW.md 目标上限字符（约 4k tokens）
LOG_WARN = 30000         # 单日日志提醒阈值（不自动处理，只提示）
HANDOFF_NOW_MAX = 4000   # 交接文档里引用 NOW.md 的最大字符

# build-workbench.py 的 parse_now_actions() 依赖这三个标题，动了工作台就废
CORE_HEAD = ("正在进行", "下一步", "阻塞", "拍板")
# 反过来：这些章节是流水/规则，不该占占每天都要付的注入成本
SINK_HEAD = ("刚完成", "临时上下文", "待处理", "本文件不写什么")


def today():
    return datetime.date.today().isoformat()


def read(p):
    try:
        with open(p, encoding="utf-8", errors="ignore") as f:
            return f.read()
    except OSError:
        return ""


def write(p, s):
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w", encoding="utf-8") as f:
        f.write(s)


def append(p, s):
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "a", encoding="utf-8") as f:
        f.write(s)


def nchar(p):
    """字符数（**不是**字节）。

    必须与 memory-tidy.py 的口径对齐：中文 UTF-8 是 3 字节/字，用 getsize 会把体积虚报近一倍，
    两个脚本得出不一致的结论最难排查。模型计费按 token 走，字符比字节更接近真实口径。
    """
    try:
        with open(p, encoding="utf-8", errors="ignore") as f:
            return len(f.read())
    except OSError:
        return 0


def est_tokens(chars):
    """中文为主的内容，粗估 1 token ≈ 1.5 字符。只用于给量级，不用于计费。"""
    return int(chars / 1.5)


# ────────────────────────────────────────────────────────────
# 1) MEMORY.md：委托给 memory-tidy.py
# ────────────────────────────────────────────────────────────
def tidy_memory(apply_):
    if not os.path.exists(TIDY):
        return {"ok": False, "note": "找不到 memory-tidy.py，跳过", "before": nchar(MEM_MD), "after": nchar(MEM_MD)}
    before = nchar(MEM_MD)
    after = before
    note = "未超预算或仅体检"
    if apply_:
        try:
            r = subprocess.run([PY, TIDY, "--apply"], capture_output=True, text=True, timeout=180)
            after = nchar(MEM_MD)
            if r.returncode == 0 and after != before:
                note = "已执行 --apply（p2 章节搬出，原位留指针）"
            elif after == before:
                note = "memory-tidy 判定无需搬运"
            else:
                note = "memory-tidy 返回 %d" % r.returncode
        except Exception as e:
            note = "调用失败（降级跳过）：%s" % type(e).__name__
    return {"ok": True, "note": note, "before": before, "after": after}


# ────────────────────────────────────────────────────────────
# 2) NOW.md：非核心区块下沉
# ────────────────────────────────────────────────────────────
def split_blocks(text):
    """按 `## ` 切块，返回 [(标题, 正文), ...]，第一块是文件头部。"""
    parts = re.split(r"^## ", text, flags=re.M)
    head = parts[0]
    blocks = []
    for b in parts[1:]:
        lines = b.splitlines()
        blocks.append((lines[0].strip() if lines else "", "\n".join(lines[1:])))
    return head, blocks


def slim_now(apply_):
    before = nchar(NOW_MD)
    text = read(NOW_MD)
    if not text:
        return {"before": before, "after": before, "moved": [], "note": "NOW.md 不存在或为空"}
    head, blocks = split_blocks(text)
    keep, sink = [], []
    for title, body in blocks:
        if any(k in title for k in CORE_HEAD):
            keep.append((title, body))
        elif "<!-- keep -->" in body:
            keep.append((title, body))          # 显式标记的保护位
        else:
            sink.append((title, body))
    after = before
    moved = []
    if sink and apply_:
        sink_file = os.path.join(MEM_DIR, "NOW-下沉-%s.md" % datetime.date.today().strftime("%Y%m%d"))
        buf = ["\n\n<!-- sink %s 由 context-daily-slim.py 自动下沉 -->\n" % datetime.datetime.now().isoformat(timespec="seconds")]
        for title, body in sink:
            buf.append("## %s\n%s" % (title, body.strip()))
            moved.append(title)
        append(sink_file, "\n".join(buf) + "\n")

        out = head.rstrip() + "\n"
        for title, body in keep:
            out += "\n## %s\n%s\n" % (title, body.strip())
        write(NOW_MD, out)
        after = nchar(NOW_MD)
    elif sink:
        moved = [t for t, _ in sink]
    return {"before": before, "after": after, "moved": moved,
            "note": ("已下沉（原文进 NOW-下沉-*.md，工作台三段保留）" if (sink and apply_) else "无需下沉")}


# ────────────────────────────────────────────────────────────
# 3) 会话交接文档：新会话读这一个，不读历史
# ────────────────────────────────────────────────────────────
def recent_reports(limit=10):
    try:
        me = os.path.basename(HANDOFF)
        items = [f for f in os.listdir(REPORT_DIR)
                 if f.endswith((".md", ".html")) and f != me]
    except OSError:
        return []
    items.sort(key=lambda f: os.path.getmtime(os.path.join(REPORT_DIR, f)), reverse=True)
    return items[:limit]


def today_headlines():
    p = os.path.join(MEM_DIR, "%s.md" % today())
    s = read(p)
    if not s:
        return []
    return [ln.lstrip("# ").strip() for ln in s.splitlines() if ln.startswith("## ")]


def build_handoff(apply_):
    now_txt = read(NOW_MD)
    now_body = re.sub(r"^>.*\n?", "", now_txt, flags=re.M).strip()
    # 去掉 NOW.md 自己的一级标题：否则它会被嵌套成交接文档的二级标题，结构错乱
    now_body = re.sub(r"^#\s*NOW[^\n]*\n", "", now_body).strip()
    if len(now_body) > HANDOFF_NOW_MAX:
        now_body = now_body[:HANDOFF_NOW_MAX] + "\n\n> ⚠️ 此处截断，完整版见 `.workbuddy/memory/NOW.md`\n"
    heads = today_headlines()
    reps = recent_reports()
    ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")

    body = [
        "# 会话交接 · 最新状态\n",
        "> 本文件由 `11-运营/scripts/context-daily-slim.py` 每日自动生成（最近一次：%s）。" % ts,
        "> **新会话开工只读这一个文件**。历史会话上下文不要依赖——它越长，每条消息的发送成本越高。\n",
        "## 一、当前状态（来自 NOW.md）\n",
        now_body or "_（NOW.md 为空）_",
        "\n## 二、长期规则入口\n",
        "- **入口**：`.workbuddy/memory/MEMORY.md`（判据＋指针，当前 %d 字符）" % nchar(MEM_MD),
        "- **下沉细节**：`.workbuddy/memory/MEMORY-下沉-*.md`（MEMORY.md 里删繁就简后搬出的一切）",
        "- **NOW 流水**：`.workbuddy/memory/NOW-下沉-*.md`（本文件的历史流水）\n",
        "## 三、今日动态\n",
    ]
    if heads:
        body += ["- " + h for h in heads]
    else:
        body.append("- （今日尚无日志标题）")
    body += [
        "\n## 四、可用报表（按需精读，不要全目录扫描）\n",
        "| 文档 | 说明 |",
        "|---|---|",
    ]
    for f in reps:
        body.append("| `%s` | 见该文件开头说明 |" % f)
    body += [
        "\n## 五、新会话纪律\n",
        "1. **不读会话历史**——需要背景就到本文第二节的入口，或到 `11-运营/reports/` 精读单份文档。",
        "2. **一个主题一个会话**——主题做完就开新会话，结论落 `11-运营/reports/`，不要靠历史传递。",
        "3. **全树操作限定子目录**——`02-商品` 4G 素材会让全目录扫描超时。",
        "4. **记忆只移动不删除**——压减前必须先把原文落到下沉文件。",
    ]
    out = "\n".join(body) + "\n"
    if apply_:
        write(HANDOFF, out)
    return {"path": HANDOFF, "chars": len(out), "written": apply_}


# ────────────────────────────────────────────────────────────
# 4) 汇总
# ────────────────────────────────────────────────────────────
def scan_logs():
    """日志不进上下文，只在超阈值时提醒——避免每天自动破坏历史。"""
    big = []
    try:
        for f in sorted(os.listdir(MEM_DIR)):
            if re.fullmatch(r"\d{4}-\d{2}-\d{2}\.md", f):
                n = nchar(os.path.join(MEM_DIR, f))
                if n > LOG_WARN:
                    big.append((f, n))
    except OSError:
        pass
    return big


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    apply_ = a.apply

    try:
        r_mem = tidy_memory(apply_)
        r_now = slim_now(apply_)
        r_hof = build_handoff(apply_)
        logs = scan_logs()
    except Exception as e:                      # 任何异常都降级，不阻塞晨检
        print("⚠️ 上下文瘦身失败（已降级跳过）：%s: %s" % (type(e).__name__, e))
        print(json.dumps({"status": "degraded"}, ensure_ascii=False) if a.json else "")
        return 0

    inj_before = r_mem["before"] + r_now["before"]
    inj_after = r_mem["after"] + r_now["after"]
    d = {
        "status": "ok",
        "mode": "apply" if apply_ else "check",
        "memory": r_mem,
        "now": r_now,
        "handoff": r_hof,
        "inject_before": inj_before,
        "inject_after": inj_after,
        "inject_saved": inj_before - inj_after,
        "inject_tokens_est": est_tokens(inj_after),
        "now_over_budget": r_now["after"] > NOW_BUDGET,
        "big_logs": logs,
    }

    if a.json:
        print(json.dumps(d, ensure_ascii=False, indent=2))
        return 0

    print("=== 每日上下文瘦身%s ===" % ("" if apply_ else "（体检，未改文件）"))
    print("MEMORY.md : %d → %d 字符  （%s）" % (r_mem["before"], r_mem["after"], r_mem["note"]))
    print("NOW.md    : %d → %d 字符  （%s）" % (r_now["before"], r_now["after"], r_now["note"]))
    if r_now["moved"]:
        print("            %s：%s" % ("已下沉章节" if apply_ else "待下沉章节（--apply 后）",
                                " / ".join(r_now["moved"])))
    print("交接文档  : %s（%d 字符，%s）" % (os.path.relpath(r_hof["path"], ROOT), r_hof["chars"],
                                        "已写" if r_hof["written"] else "未写（体检模式）"))
    print("注入开销  : %d → %d 字符（省 %d），约 %d tokens" %
          (inj_before, inj_after, d["inject_saved"], d["inject_tokens_est"]))
    if d["now_over_budget"]:
        print("⚠️ NOW.md 仍超 %d 字符预算，建议收工时手动精简" % NOW_BUDGET)
    if logs:
        print("ℹ️ 超大日志（不进上下文，仅提醒蒸馏）：%s" %
              ", ".join("%s %s字符" % (f, format(n, ",")) for f, n in logs))
    return 0


if __name__ == "__main__":
    sys.exit(main())
