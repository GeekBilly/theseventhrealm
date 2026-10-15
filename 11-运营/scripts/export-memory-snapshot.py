#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
export-memory-snapshot.py —— 把 .workbuddy/memory/ 里的「活约定」导出成可被 Git 跟踪的快照。

为什么需要它
    .gitignore 第 34 行把整个 .workbuddy/ 排除了（理由成立：里面有会话上下文和个人信息）。
    代价是：MEMORY.md（每次会话开头自动注入的长期约定）和全部日志既不在 Git 里，
    也不在 Mac mini 的每日 03:00 拉取里。MacBook 一挂，这份「我睁眼就知道的事」就没了——
    而它恰恰是最难重建的：项目文件能 clone，约定只能靠回忆。

做什么
    读 .workbuddy/memory/MEMORY.md（+ NOW.md），脱敏后写入
    11-运营/reports/MEMORY快照-YYYYMM.md（同月覆盖，次月自动开新文件）。
    --full 时额外带上该月全部日志，写入 MEMORY快照-YYYYMM-归档.md
    ⭐ 两个文件名刻意分开：否则每日轻量快照会把整月日志冲掉，
       反过来若锁住同名文件，月末前的 MEMORY 更新又会进不了备份。

用法
    python3 export-memory-snapshot.py                    # MEMORY.md + NOW.md（当月文件名）
    python3 export-memory-snapshot.py --full             # 再追加当月全部日志
    python3 export-memory-snapshot.py --full --month 202610  # 指定月份（月初归档上月用）
    python3 export-memory-snapshot.py --dry-run          # 只报告会不会变，不写盘

参数
    --month YYYYMM   指定快照归属月份，默认＝当前月。
                     ⭐ 月度归档任务跑在**次月 1 日**并传上月的月份：
                     月末当天跑会把「当天还没写完的日志」归档进去，月初跑拿到的才是整月完整版。

纪律
    - 幂等：内容未变则不写盘（避免每天一次无意义 diff）
    - 零积分：纯本地文件读写，不联网、不调模型
    - 失败降级：任何异常都只打印原因并 exit 0，绝不阻塞调用方（qj-sync.sh）
"""

import os
import re
import sys
import glob
from datetime import datetime

ROOT = os.environ.get("QJ_ROOT") or os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
MEM_DIR = os.path.join(ROOT, ".workbuddy", "memory")
OUT_DIR = os.path.join(ROOT, "11-运营", "reports")
OUT_NAME = "MEMORY快照-{}.md"
ARCHIVE_NAME = "MEMORY快照-{}-归档.md"   # --full 走这个文件名，与每日轻量版互不覆盖
LOG_MARK = "## 当月日志"   # 归档版（--full）的特征标记，轻量版不得覆盖它

# ---------- 脱敏规则 ----------
# memory 里目前没有密码和真邮箱，但加一层总没错：将来万一有人把 token 写进去
REDACT = [
    # 苹果中转隐私邮箱（项目内已知有真值，永不上云）
    (re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]*privaterelay\.appleid\.com"), "[relay-redacted]"),
    # 各类密钥形态
    (re.compile(r"sk-[A-Za-z0-9]{12,}"), "[key-redacted]"),
    (re.compile(r"ghp_[A-Za-z0-9]{12,}"), "[key-redacted]"),
    (re.compile(r"eyJ[A-Za-z0-9_-]{20,}"), "[jwt-redacted]"),
    (re.compile(r"(?i)\b(password|passwd|token|api[_-]?key|secret)\b\s*[:=]\s*\S{6,}"),
     lambda m: f"{m.group(1)}: [redacted]"),
]
# 这两个是公开的、且仓库里本来就有，不算泄露，保留
KEEP_OK = {"GeekBilly@users.noreply.github.com", "git@github.com"}
# 自有域名邮箱全站公开（仓库里已有 920 处），同样不算泄露 ⇒ 自检时跳过
KEEP_SUFFIX = ("@theseventhrealm.com",)


EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")


def redact(text: str) -> str:
    for pat, rep in REDACT:
        text = pat.sub(rep, text)
    # 🔴 兜底：白名单之外的一切邮箱一律打码。
    # 只用黑名单会漏——2026-10-16 实测日志里出现个人邮箱 billy…@sina.com，
    # 而 .workbuddy/ 被排除在 Git 之外的原因之一就是它含个人信息。
    return EMAIL_RE.sub(
        lambda m: m.group(0)
        if (m.group(0) in KEEP_OK or m.group(0).endswith(KEEP_SUFFIX))
        else "[email-redacted]",
        text,
    )


def read(path: str) -> str:
    try:
        with open(path, encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        return ""
    except Exception as e:
        print(f"  ⚠️ 读不了 {os.path.basename(path)}：{e}")
        return ""


def parse_month(argv) -> str:
    """--month YYYYMM；默认取当前月。"""
    if "--month" in argv:
        i = argv.index("--month")
        if i + 1 < len(argv):
            v = argv[i + 1].strip()
            if re.fullmatch(r"\d{6}", v):
                return v
            print(f"  ⚠️ --month 格式应为 YYYYMM，收到「{v}」，回退当月")
    return datetime.now().strftime("%Y%m")


def main() -> int:
    full = "--full" in sys.argv
    dry = "--dry-run" in sys.argv

    now = datetime.now()
    month = parse_month(sys.argv)
    ym_disp = f"{month[:4]}-{month[4:6]}"
    # ⭐ 归档版（含日志）用独立文件名：否则每日轻量快照会把整月日志冲掉，
    #    反过来若锁住同名文件，月末前的 MEMORY 更新又会进不了备份（两难 → 拆文件解决）
    out_path = os.path.join(OUT_DIR, (ARCHIVE_NAME if full else OUT_NAME).format(month))

    memory = read(os.path.join(MEM_DIR, "MEMORY.md"))
    nowdoc = read(os.path.join(MEM_DIR, "NOW.md"))
    if not memory and not nowdoc:
        print("  ⚠️ MEMORY.md / NOW.md 都没读到，跳过快照")
        return 0

    n_mem = len(memory)
    n_now = len(nowdoc)

    scope = f"含 {ym_disp} 全部日志" if full else "不含日志（--full 可加）"
    parts = [
        f"# 第七境 · MEMORY 快照（{ym_disp}）\n",
        f"> 本文件由 `11-运营/scripts/export-memory-snapshot.py` **自动生成**，请勿手改（下轮会覆盖）。\n",
        "> 生成时间：{}　|　源：`.workbuddy/memory/MEMORY.md`　|　{}\n".format(
            now.strftime("%Y-%m-%d %H:%M"), scope),
        # 归档上月时，MEMORY/NOW 是「导出时刻」的版本，不是当月历史版本——写明免得误读
        (f"> ⚠️ 本文件归档的是 **{ym_disp}** 的日志；其中 MEMORY.md / NOW.md 为"
         f"导出时刻（{now.strftime('%Y-%m-%d')}）的当前版本，非当月历史版。\n"
         if month != now.strftime("%Y%m") else ""),
        "\n---\n",
        "\n## 为什么有这个文件\n",
        "\n`.gitignore` 把整个 `.workbuddy/` 排除在版本控制之外，所以 MEMORY.md 与每日日志\n",
        "**既不在 Git 里，也不在 Mac mini 的每日拉取里**。本快照是它们唯一的异地备份。\n",
        "\n## 恢复方法\n",
        "\n1. 从本文件「MEMORY.md 全文」一节起，把内容复制回 `.workbuddy/memory/MEMORY.md`\n",
        "2. **注意**：快照是脱敏版（邮箱/密钥会被替换成占位符）。\n",
        "   真邮箱的唯一来源永远是本地《11-运营/风险管控/账号与邮箱链路清单.md》，该文件不可删。\n",
        "3. 日志不在快照里（默认）。要备份当月日志请手动跑 `--full`。\n",
        "\n---\n",
    ]

    if nowdoc:
        parts += ["\n## NOW.md（当前状态）\n\n", redact(nowdoc).strip(), "\n"]
    parts += ["\n---\n", "\n## MEMORY.md 全文\n\n", redact(memory).strip(), "\n"]

    if full:
        logs = sorted(glob.glob(os.path.join(MEM_DIR, f"{month[:4]}-{month[4:6]}-*.md")))
        if logs:
            parts.append("\n---\n\n## 当月日志\n")
            for p in logs:
                body = redact(read(p)).strip()
                if body:
                    parts.append(f"\n### {os.path.basename(p)[:-3]}\n\n{body}\n")

    content = "".join(parts)

    if dry:
        print(f"  [dry-run] 将写入 {os.path.basename(out_path)}｜{len(content)} 字符"
              f"（MEMORY {n_mem} / NOW {n_now}）")
        return 0

    os.makedirs(OUT_DIR, exist_ok=True)
    # 幂等：内容没变就不写盘
    try:
        if os.path.exists(out_path):
            with open(out_path, encoding="utf-8") as f:
                existing = f.read()
            if existing == content:
                print(f"  · 快照无变化，未写盘（{os.path.basename(out_path)}）")
                return 0
            # 🔴 不许用「轻量版」覆盖已归档的「含日志版」
            #    （qj-sync 每次 push 都跑一次轻量快照，文件名与归档版相同）
            if not full and LOG_MARK in existing:
                print(f"  · {os.path.basename(out_path)} 已是含日志的归档版，"
                      f"轻量快照不覆盖（要刷新 MEMORY 部分请加 --full）")
                return 0
    except Exception:
        pass

    with open(out_path, "w", encoding="utf-8") as f:
        f.write(content)

    # 泄露自检
    leaked = [e for e in re.findall(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", content)
              if e not in KEEP_OK and not e.endswith(KEEP_SUFFIX)]
    tail = f"｜泄露自检 {len(leaked)} 个" + (f" ⚠️ {leaked[:3]}" if leaked else "✅（仅公开地址）")
    print(f"  · MEMORY 快照已更新：11-运营/reports/{os.path.basename(out_path)}"
          f"（{len(content)} 字符，MEMORY {n_mem} / NOW {n_now}）{tail}")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:
        print(f"  ⚠️ 快照导出失败（不阻塞同步）：{e}")
        sys.exit(0)
