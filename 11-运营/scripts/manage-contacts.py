#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""manage-contacts.py —— 第七境 客户库（订阅者）管理

一个 CSV 的轻量 CRM：入库 / 分组 / 查询 / 导出给 MailerLite / 退订 / 删除。
零依赖、零成本、数据在自己硬盘上，不依赖任何第三方平台。

数据文件：04-市场/05-客户库/客户库.csv
粘贴缓冲：04-市场/05-客户库/粘贴邮件到这里.txt

常用：
  python3 11-运营/scripts/manage-contacts.py import-mail            # 吃粘贴缓冲（默认直接入库）
  python3 11-运营/scripts/manage-contacts.py import-mail --dry      # 只看不写
  python3 11-运营/scripts/manage-contacts.py list --group 桌面横版开售
  python3 11-运营/scripts/manage-contacts.py stats
  python3 11-运营/scripts/manage-contacts.py export --group 桌面横版开售 --out /tmp/开售名单.csv
  python3 11-运营/scripts/manage-contacts.py bcc --group 桌面横版开售 --batch 50
  python3 11-运营/scripts/manage-contacts.py unsub --email a@b.com
  python3 11-运营/scripts/manage-contacts.py purge --email a@b.com  # 「删除我的数据」请求
"""

from __future__ import annotations

import argparse
import csv
import re
import shutil
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CUSTOMER_DIR = ROOT / "04-市场" / "05-客户库"
DB = CUSTOMER_DIR / "客户库.csv"
BUFFER = CUSTOMER_DIR / "粘贴邮件到这里.txt"
ARCHIVE_DIR = CUSTOMER_DIR / "留痕归档"

COLS = ["邮箱", "称呼", "分组", "来源", "同意时间", "状态", "退订时间", "备注", "更新时间"]

BUFFER_MARK = "以下是待处理内容"

# 缓冲文件的固定头部（清空时按此模板重写，保证每次状态一致）
BUFFER_HEADER = f"""# 粘贴缓冲：把从邮箱里复制出来的订阅邮件信息粘到本文件下面（这一行和下面几行说明留着别删）
#
# 怎么用：
#   1. 打开 sina 邮箱，逐封点开订阅邮件，把「发件人 / 主题 / 时间」三行整段复制
#   2. 粘贴到本文件的最下面（说明行之后）
#   3. 回项目里跑：python3 11-运营/scripts/manage-contacts.py import-mail
#   4. 成功入库后脚本会自动清空下面的内容，并把原文留痕到 留痕归档/
#
# 也接受更省事的形式：一行「邮箱 主题」，或者干脆只贴一串邮箱（会归到「一般订阅」）。
# 自己的邮箱（hello@ / sina 个人邮箱）与 noreply 类地址会被自动跳过。
#
# ---------------------------- {BUFFER_MARK} ----------------------------

"""

# 分组口径（唯一权威定义在 04-市场/05-客户库/README.md，改这里要同步改文档）
KNOWN_GROUPS = ["桌面横版开售", "壁纸领取", "众筹意向", "一般订阅"]
DEFAULT_GROUP = "一般订阅"

# 主题关键词 → 自动分组（顺序即优先级）
GROUP_RULES: list[tuple[str, str]] = [
    (r"桌面|横版|开售", "桌面横版开售"),
    (r"壁纸|领取|金句|手机", "壁纸领取"),
    (r"众筹|实体书|出版|装帧", "众筹意向"),
]

# 这些地址永远不会入库（自己人）
SELF_PATTERNS = [
    re.compile(r"@theseventhrealm\.com$", re.I),
    re.compile(r"^billy19870528@sina\.com$", re.I),
    re.compile(r"^(no-?reply|noreply|mailer-daemon|postmaster)@", re.I),
]

EMAIL_RE = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}")
SUBJECT_RE = re.compile(r"^\s*(?:主题|標題|标题|subject)\s*[:：]\s*(.+?)\s*$", re.I)
FROM_RE = re.compile(r"^\s*(?:发件人|寄件者|from)\s*[:：]\s*(.*)$", re.I)
DATE_RE = re.compile(r"^\s*(?:时间|日期|date)\s*[:：]\s*(.+?)\s*$", re.I)
TS_RE = re.compile(
    r"(\d{4})\s*[-/年.]\s*(\d{1,2})\s*[-/月.]\s*(\d{1,2})\s*日?"
    r"(?:\s*(\d{1,2})\s*[:：]\s*(\d{2}))?"
)


# --------------------------------------------------------------------------- 基础 IO


def die(msg: str, code: int = 1):
    print(f"❌ {msg}", file=sys.stderr)
    sys.exit(code)


def now_stamp() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M")


def load() -> list[dict]:
    if not DB.exists():
        return []
    with DB.open(encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    out = []
    for r in rows:
        if not (r.get("邮箱") or "").strip():
            continue
        out.append({c: (r.get(c) or "").strip() for c in COLS})
    return out


def save(rows: list[dict]):
    CUSTOMER_DIR.mkdir(parents=True, exist_ok=True)
    rows = sorted(rows, key=lambda r: (r["邮箱"].lower(),))
    with DB.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=COLS)
        w.writeheader()
        for r in rows:
            w.writerow({c: r.get(c, "") for c in COLS})


def is_self(addr: str) -> bool:
    return any(p.search(addr) for p in SELF_PATTERNS)


def norm_groups(raw: str) -> list[str]:
    parts = [p.strip() for p in re.split(r"[;；,，/|]", raw or "") if p.strip()]
    seen, out = set(), []
    for p in parts:
        if p not in seen:
            seen.add(p)
            out.append(p)
    return out


def pick_group(text: str) -> str:
    for pat, grp in GROUP_RULES:
        if re.search(pat, text or ""):
            return grp
    return DEFAULT_GROUP


def guess_time(text: str) -> str:
    m = TS_RE.search(text or "")
    if not m:
        return ""
    y, mo, d, hh, mm = m.groups()
    return f"{int(y):04d}-{int(mo):02d}-{int(d):02d}" + (f" {int(hh):02d}:{mm}" if hh else "")


# --------------------------------------------------------------------------- 邮件文本解析


def read_buffer_text() -> str:
    if not BUFFER.exists():
        die(f"找不到粘贴缓冲文件：{BUFFER}")
    raw = BUFFER.read_text(encoding="utf-8")
    if BUFFER_MARK in raw:
        head, _, tail = raw.partition(BUFFER_MARK)
        raw = tail
    return raw


def parse_block(text: str) -> list[dict]:
    """从任意「复制出来的邮件文字」里抽 邮箱 / 称呼 / 主题 / 时间。

    按「块」解析：网页邮箱里常见顺序是 发件人 → 主题 → 时间，所以不能见到邮箱就立刻定组，
    要等这一块结束（空行 / 下一封的发件人行 / 文本结束）再一起提交。
    """
    found: list[dict] = []
    seen: set[str] = set()
    S = {"addrs": [], "subject": "", "name": "", "when": "", "line": ""}

    def reset():
        S["addrs"], S["subject"], S["name"], S["when"], S["line"] = [], "", "", "", ""

    def add(addr: str, subject: str, name: str, when: str, line: str):
        addr = addr.strip().strip(".,;:<>()[]")
        if is_self(addr) or addr.lower() in seen:
            return
        seen.add(addr.lower())
        found.append(
            {
                "邮箱": addr,
                "称呼": name,
                "分组": pick_group(subject or line),
                "来源": "",
                "同意时间": when,
                "状态": "已订阅",
                "退订时间": "",
                "备注": "",
                "更新时间": now_stamp(),
                "_subject": subject,
            }
        )

    def flush():
        if not S["addrs"]:
            return  # 只有主题还没有收件人 → 保留，等下一行（主题可能排在发件人之前）
        for a in S["addrs"]:
            add(a, S["subject"], S["name"], S["when"], S["line"])
        reset()

    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            flush()
            continue

        m = SUBJECT_RE.match(stripped)
        if m:
            S["subject"] = m.group(1)
            continue

        m = DATE_RE.match(stripped)
        if m:
            S["when"] = guess_time(m.group(1)) or S["when"]
            continue

        m = FROM_RE.match(stripped)
        if m:
            flush()  # 上一封的收件人在此结账
            rest = m.group(1)
            nm = re.match(r"^(.+?)\s*<", rest)
            if nm:
                S["name"] = nm.group(1).strip().strip('"')
            S["addrs"] = [a for a in EMAIL_RE.findall(rest) if not is_self(a)]
            S["line"] = stripped
            if not S["when"]:
                S["when"] = guess_time(rest)
            if S["addrs"]:
                continue
            # 发件人栏里没有地址（如「侯炳利」三个字）→ 等下面几行里的地址
            continue

        addrs = [a for a in EMAIL_RE.findall(stripped) if not is_self(a)]
        if addrs:
            flush()
            tail = EMAIL_RE.sub(" ", stripped).strip(" \t-—|:")
            tail = re.sub(r"[（(].*?[)）]", "", tail).strip()
            for a in addrs:
                add(a, S["subject"] or tail, S["name"] if not tail else "", S["when"] or guess_time(stripped), stripped)
            reset()
            continue

        # 没有邮箱、但像主题的一行（邮件列表里常见的「订阅桌面版开售通知」）
        if not S["subject"] and re.search(r"[\u4e00-\u9fff]", stripped) and len(stripped) <= 60:
            S["subject"] = stripped

    flush()

    for it in found:
        subj = it.pop("_subject", "")
        it["备注"] = f"原主题：{subj}" if subj else ""
    return found


# --------------------------------------------------------------------------- 子命令


def cmd_add(a):
    rows = load()
    addr = a.email.strip()
    if is_self(addr):
        die(f"{addr} 是自己的地址，跳过。")
    if "@" not in addr:
        die(f"不像邮箱地址：{addr}")
    idx = next((i for i, r in enumerate(rows) if r["邮箱"].lower() == addr.lower()), None)
    groups = norm_groups(a.group) or [DEFAULT_GROUP]
    if idx is not None:
        old = rows[idx]
        merged = norm_groups(";".join([old["分组"]] + groups))
        old["分组"] = ";".join(merged)
        old["状态"] = "已订阅"
        old["退订时间"] = ""
        if a.name:
            old["称呼"] = a.name
        if a.source:
            old["来源"] = a.source
        old["更新时间"] = now_stamp()
        action = "更新"
        final_group = old["分组"]
    else:
        rows.append(
            {
                "邮箱": addr,
                "称呼": a.name or "",
                "分组": ";".join(groups),
                "来源": a.source or "手工",
                "同意时间": a.at or now_stamp(),
                "状态": "已订阅",
                "退订时间": "",
                "备注": a.note or "",
                "更新时间": now_stamp(),
            }
        )
        action = "新增"
        final_group = ";".join(groups)
    save(rows)
    print(f"✅ {action}：{addr} → {final_group}（来源 {a.source or '手工'}）")


def cmd_import_mail(a):
    src = Path(a.file).expanduser() if a.file else BUFFER
    if not src.exists():
        die(f"找不到文件：{src}")
    raw = src.read_text(encoding="utf-8")
    if src == BUFFER and BUFFER_MARK in raw:
        raw = raw.partition(BUFFER_MARK)[2]

    items = parse_block(raw)
    if a.group:
        for it in items:
            it["分组"] = a.group
    rows = load()
    by_mail = {r["邮箱"].lower(): r for r in rows}

    new, dup, reopen = [], [], []
    for it in items:
        it["来源"] = a.source or it["来源"] or "藏品页-mailto"
        key = it["邮箱"].lower()
        if key in by_mail:
            old = by_mail[key]
            g = norm_groups(";".join([old["分组"], it["分组"]]))
            if set(norm_groups(old["分组"])) != set(g):
                old["分组"] = ";".join(g)
                old["更新时间"] = now_stamp()
                dup.append(it["邮箱"])
            else:
                dup.append(it["邮箱"])
            if old["状态"] == "已退订":
                old["状态"] = "已订阅"
                old["退订时间"] = ""
                old["更新时间"] = now_stamp()
                reopen.append(it["邮箱"])
        else:
            rows.append(it)
            by_mail[key] = it
            new.append(it["邮箱"])

    print(f"📥 从 {src.name} 解析到 {len(items)} 个地址")
    for it in items:
        print(f"   · {it['邮箱']:<32} [{it['分组']}]  {it['同意时间'] or '时间未知'}")
    if dup:
        print(f"↩️  已存在（跳过/合并分组）：{len(dup)} 个 —— {', '.join(dup[:5])}{' …' if len(dup) > 5 else ''}")
    if reopen:
        print(f"🔓 原为退订、现重新订阅：{', '.join(reopen)}")

    if a.dry:
        print("\n（--dry 模式：未写入任何内容）")
        return
    if not items:
        print("⚠️  没解析出任何邮箱 —— 请检查粘贴内容里是否含 `发件人: 名字 <邮箱>` 或直接写了邮箱。")
        return

    save(rows)
    if src == BUFFER:
        ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime("%Y-%m-%d-%H%M")
        shutil.copyfile(src, ARCHIVE_DIR / f"粘贴-{stamp}.txt")
        BUFFER.write_text(BUFFER_HEADER, encoding="utf-8")
        print(f"🧹 缓冲已清空，原文留痕：留痕归档/粘贴-{stamp}.txt")
    print(f"✅ 入库完成：新增 {len(new)}，已存在 {len(dup)}；当前总计 {len(rows)} 人")


def cmd_list(a):
    rows = load()
    if a.group:
        want = set(norm_groups(a.group))
        rows = [r for r in rows if want & set(norm_groups(r["分组"]))]
    if not a.all:
        rows = [r for r in rows if r["状态"] == "已订阅"]
    if not rows:
        print("（空）")
        return
    print(f"{len(rows)} 人：")
    for r in rows:
        flag = "🚫" if r["状态"] == "已退订" else "  "
        print(f"{flag} {r['邮箱']:<32} [{r['分组']:<28}] {r['来源']:<14} {r['同意时间']}")


def cmd_stats(a):
    rows = load()
    live = [r for r in rows if r["状态"] == "已订阅"]
    print(f"总记录 {len(rows)}｜有效订阅 {len(live)}｜已退订 {len(rows) - len(live)}")
    print("\n按分组（仅有效）：")
    tally: dict[str, int] = {}
    for r in live:
        for g in norm_groups(r["分组"]):
            tally[g] = tally.get(g, 0) + 1
    for g, n in sorted(tally.items(), key=lambda kv: -kv[1]):
        print(f"  {g:<16} {n:>4} 人")
    src: dict[str, int] = {}
    for r in live:
        src[r["来源"] or "未标"] = src.get(r["来源"] or "未标", 0) + 1
    print("\n按来源（仅有效）：")
    for s, n in sorted(src.items(), key=lambda kv: -kv[1]):
        print(f"  {s:<16} {n:>4} 人")
    month = datetime.now().strftime("%Y-%m")
    recent = [r for r in live if r["同意时间"].startswith(month) or r["更新时间"].startswith(month)]
    print(f"\n本月新增/活跃：{len(recent)} 人（{month}）")
    cap = 250
    print(f"\nMailerLite 免费版上限 {cap} 人 → 余量 {cap - len(live)} 人")
    if len(live) > cap * 0.8:
        print("⚠️  已用掉 80% 以上，建议清理长期不活跃订阅者或评估升付费版。")


def cmd_export(a):
    rows = [r for r in load() if r["状态"] == "已订阅"]
    if a.group:
        want = set(norm_groups(a.group))
        rows = [r for r in rows if want & set(norm_groups(r["分组"]))]
    if not rows:
        print("（无符合条件的订阅者，未生成文件）")
        return
    out = Path(a.out).expanduser()
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["email", "name", "group"])
        for r in rows:
            w.writerow([r["邮箱"], r["称呼"], r["分组"]])
    print(f"✅ 导出 {len(rows)} 人 → {out}")
    print("   下一步：MailerLite → Subscribers → Groups → 新建/选择组 → Import → 上传该 CSV（映射 email / name）")


def cmd_bcc(a):
    rows = [r for r in load() if r["状态"] == "已订阅"]
    if a.group:
        want = set(norm_groups(a.group))
        rows = [r for r in rows if want & set(norm_groups(r["分组"]))]
    mails = [r["邮箱"] for r in rows]
    if not mails:
        print("（无符合条件的订阅者）")
        return
    print("⚠️  退路方案：用自己邮箱密送（BCC）群发容易被判垃圾邮件，且没有退订链接。")
    print("    优先走 MailerLite；此处仅在没有平台可用时使用。\n")
    b = max(1, a.batch)
    for i in range(0, len(mails), b):
        print(f"第 {i // b + 1} 批（{len(mails[i:i + b])} 人）：")
        print(",".join(mails[i:i + b]))
        print()


def cmd_unsub(a):
    rows = load()
    hit = 0
    for r in rows:
        if r["邮箱"].lower() == a.email.strip().lower():
            r["状态"] = "已退订"
            r["退订时间"] = now_stamp()
            r["更新时间"] = now_stamp()
            if a.reason:
                r["备注"] = (r["备注"] + "｜" if r["备注"] else "") + f"退订原因：{a.reason}"
            hit += 1
    if not hit:
        die(f"库里没有 {a.email}")
    save(rows)
    print(f"🚫 已标退订：{a.email}（记录保留，发信时自动排除）")


def cmd_purge(a):
    rows = load()
    keep = [r for r in rows if r["邮箱"].lower() != a.email.strip().lower()]
    if len(keep) == len(rows):
        die(f"库里没有 {a.email}")
    if not a.yes:
        print(f"将删除 1 条记录（{a.email}），当前共 {len(rows)} 条 → {len(keep)} 条。")
        print("确认请加 --yes 重跑。")
        return
    save(keep)
    print(f"🗑️  已删除 {a.email}（用于响应「删除我的数据」请求；不可恢复）")


# --------------------------------------------------------------------------- CLI


def main():
    p = argparse.ArgumentParser(description="第七境客户库（订阅者）管理", formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("add", help="手工加一个人")
    s.add_argument("--email", required=True)
    s.add_argument("--name", default="")
    s.add_argument("--group", default="")
    s.add_argument("--source", default="")
    s.add_argument("--at", default="")
    s.add_argument("--note", default="")
    s.set_defaults(func=cmd_add)

    s = sub.add_parser("import-mail", help="解析粘贴缓冲，批量入库")
    s.add_argument("file", nargs="?", help="默认 04-市场/05-客户库/粘贴邮件到这里.txt")
    s.add_argument("--group", default="", help="强制指定分组（覆盖自动判断）")
    s.add_argument("--source", default="")
    s.add_argument("--dry", action="store_true", help="只预览不写入")
    s.set_defaults(func=cmd_import_mail)

    s = sub.add_parser("list", help="列出订阅者")
    s.add_argument("--group", default="")
    s.add_argument("--all", action="store_true", help="含已退订")
    s.set_defaults(func=cmd_list)

    s = sub.add_parser("stats", help="分组/来源统计与余量")
    s.set_defaults(func=cmd_stats)

    s = sub.add_parser("export", help="导出 CSV（给 MailerLite 导入）")
    s.add_argument("--group", default="")
    s.add_argument("--out", required=True)
    s.set_defaults(func=cmd_export)

    s = sub.add_parser("bcc", help="输出密送名单（退路方案）")
    s.add_argument("--group", default="")
    s.add_argument("--batch", type=int, default=50)
    s.set_defaults(func=cmd_bcc)

    s = sub.add_parser("unsub", help="标为退订")
    s.add_argument("--email", required=True)
    s.add_argument("--reason", default="")
    s.set_defaults(func=cmd_unsub)

    s = sub.add_parser("purge", help="彻底删除一条记录")
    s.add_argument("--email", required=True)
    s.add_argument("--yes", action="store_true")
    s.set_defaults(func=cmd_purge)

    a = p.parse_args()
    a.func(a)


if __name__ == "__main__":
    main()
