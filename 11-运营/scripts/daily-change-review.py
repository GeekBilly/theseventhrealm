#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""第七境 · 每日改动评审（把改动拉出来，决定要不要上线）

数据源：~/.workbuddy/changes-index/*.json —— WorkBuddy 本地记录的文件级变更索引
（每个会话每个请求一条记录：filePath / action / additions / deletions / createdAt），
不依赖 git（本项目没有 git），也不需要联网，零积分成本。

用法：
  python3 11-运营/scripts/daily-change-review.py                 # 默认近 24 小时
  python3 11-运营/scripts/daily-change-review.py --hours 48      # 补拉更长窗口
  python3 11-运营/scripts/daily-change-review.py --md            # 只打印不落盘（默认落盘）
输出：
  11-运营/reports/每日改动评审-<日期>.md  并同时打印到 stdout
"""
import argparse
import datetime
import glob
import hashlib
import json
import os
import sys
import zipfile

ROOT = "/Users/billyhou/WorkBuddy/2026-09-25-15-56-17"
INDEX_DIR = os.path.expanduser("~/.workbuddy/changes-index")
OUT_DIR = os.path.join(ROOT, "11-运营", "reports")

# 分类规则：顺序敏感，先命中为准。
# (分类名, 路径前缀, 是否属于「会影响线上」)
RULES = [
    ("网站设计·可上线", ("03-页面/", "seventhrealm-child/", "05-发布包/"), True),
    ("产品资产", ("02-商品/", "06-品牌/"), False),
    ("内容稿件", ("01-内容/",), False),
    ("市场推广", ("04-市场/", "09-社区/"), False),
    ("运营与工具", ("11-运营/", "10-规划/", "07-课程/", "08-音频/"), False),
]

PUBLISH_MAP = {
    # 已上线 URL（有则用于提示，不影响判定）。维护在这里，key＝本地文件相对路径。
    "03-页面/collection.html": "/collection/",
}

# 下游联动：改了上游，别忘了还要跑这一段才算完。
DOWNSTREAM = [
    (("01-内容/历史长卷/朝代稿/",),
     "改了朝代稿 → 需 `11-运营/朝代页流水线/sync-from-drafts.py` → `11-运营/朝代页流水线/build.py` 重生成 "
     "`03-页面/朝代页/*.html`，再走 `11-运营/朝代页流水线/publish.sh`（上线前先 `11-运营/scripts/backup-site.sh`）"),
    (("02-商品/03-字形线/", "02-商品/04-金句线/", "02-商品/05-承接站/"),
     "商品线有改动 → 动到版式/样张后，成品图与承接站要重新生成（`02-商品/05-承接站/build-catalog.py`）"),
    (("seventhrealm-child/",),
     "子主题改动 → 归到「主题包批量上传」，攒够一批再传，不要单文件传"),
    (("03-页面/",),
     "页面 HTML 改动 → 发前跑私密信息体检，再用 `11-运营/scripts/publish-page.sh` / `11-运营/publish-pages.sh`"),
]


def md5_of(path):
    return hashlib.md5(open(path, "rb").read()).hexdigest()


def latest_pack():
    """最新一个发布包 zip；返回 (路径, {zip内相对路径: md5})"""
    zs = sorted(glob.glob(os.path.join(ROOT, "05-发布包", "*.zip")),
                key=os.path.getmtime)  # 按修改时间取最新，不能按文件名（会选中不带版本号的最旧包）
    if not zs:
        return None, {}
    zpath = zs[-1]
    try:
        with zipfile.ZipFile(zpath) as z:
            names = z.namelist()
            return zpath, {n: hashlib.md5(z.read(n)).hexdigest() for n in names
                           if not n.endswith("/")}
    except Exception:
        return None, {}


def in_pack(rel, md5):
    """判断本地文件是否与最新发布包里同名文件内容一致（＝已经上传过了）"""
    zpath, table = latest_pack()
    if not zpath:
        return None
    for cand in {rel, rel.split("/", 1)[1] if "/" in rel else rel}:
        if cand in table and table[cand] == md5:
            return os.path.basename(zpath)
    return None


def classify(rel):
    for name, prefixes, online in RULES:
        for p in prefixes:
            if rel.startswith(p):
                return name, online
    return "其他", False


def tier(rel, action, adds, dels):
    """给「会影响线上」的文件判发布档位。返回 (档位, 理由)"""
    base = os.path.basename(rel)
    churn = adds + dels
    if rel.startswith("seventhrealm-child/") or rel.endswith((".php", ".css")):
        return ("C 需真机验收",
                "改动了子主题/全局样式，一次上线影响全站，且主题包上传是稀缺操作")
    if rel.startswith("05-发布包/"):
        return ("C 需真机验收", "发布包＝整批交付快照，上线前须完整走一遍全站 URL 复核")
    if action == "create":
        return ("B 先本地预览", "新增页面，本地渲染过一遍视觉再铺")
    if churn <= 80 and rel.startswith("03-页面/朝代页/"):
        return ("A 可直接铺", "已上线同类朝代页的小幅改动，结构未变")
    if churn <= 30:
        return ("A 可直接铺", "文本级小幅改动")
    return ("B 先本地预览", f"改动量较大（+{adds} −{dels}），建议先看一眼渲染结果")


def load_changes(since_ms):
    out = {}
    for path in glob.glob(os.path.join(INDEX_DIR, "*.json")):
        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            continue
        for ch in data.get("changes", []):
            ts = ch.get("createdAt") or 0
            if ts < since_ms:
                continue
            for item in ch.get("files", []):
                fp = item.get("filePath") or ""
                if not fp.startswith(ROOT + "/"):
                    continue
                rel = fp[len(ROOT) + 1:]
                cur = out.get(rel)
                add = item.get("additions") or 0
                dele = item.get("deletions") or 0
                action = item.get("action") or "modify"
                if cur is None or ts > cur["ts"]:
                    out[rel] = {"ts": ts, "adds": add, "dels": dele,
                                "action": action}
                else:
                    cur["adds"] += add
                    cur["dels"] += dele
    return out


def judge_of(t, why, rel):
    """拼出一句话判定：档位 + 会覆盖哪个 URL + 理由"""
    url = PUBLISH_MAP.get(rel)
    return f"**{t}**" + (f"（将覆盖 {url}）" if url else "") + f" — {why}"


def human(n):
    return f"{n}B" if n < 1024 else f"{n / 1024:.1f}KB"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--hours", type=float, default=24.0)
    ap.add_argument("--md", action="store_true", help="只打印，不写文件")
    ap.add_argument("--top", type=int, default=8, help="非上线类每类最多列出几条，其余折叠计数")
    args = ap.parse_args()

    now = datetime.datetime.now()
    since = now - datetime.timedelta(hours=args.hours)
    since_ms = int(since.timestamp() * 1000)

    changes = load_changes(since_ms)
    if not changes:
        msg = f"## 每日改动评审 · {now:%Y-%m-%d}\n\n窗口：近 {args.hours:g} 小时（自 {since:%m-%d %H:%M}）→ **无改动**。\n"
        print(msg)
        return

    buckets = {}
    for rel, info in changes.items():
        cat, online = classify(rel)
        buckets.setdefault(cat, {"online": online, "items": []})["items"].append((rel, info))

    online_items = []
    lines = [
        f"## 每日改动评审 · {now:%Y-%m-%d}",
        "",
        f"窗口：近 {args.hours:g} 小时（自 {since:%m-%d %H:%M}）｜共 {len(changes)} 个文件变更",
        "",
    ]

    order = [r[0] for r in RULES] + ["其他"]
    for cat in order:
        b = buckets.get(cat)
        if not b:
            continue
        lines.append(f"### {cat}（{len(b['items'])}）")
        lines.append("")
        lines.append("| 文件 | 动作 | 增删 | 大小 | 判定 |")
        lines.append("|---|---|---|---|---|")
        # 上线类全列；其余按改动量 Top N，剩下折叠，避免刷屏
        items = b["items"]
        rest = []
        if not b["online"] and len(items) > args.top:
            items = sorted(items, key=lambda kv: -(kv[1]["adds"] + kv[1]["dels"]))[:args.top]
            shown = {k for k, _ in items}
            rest = [kv for kv in b["items"] if kv[0] not in shown]
        for rel, info in sorted(items):
            exists = os.path.exists(os.path.join(ROOT, rel))
            size = os.path.getsize(os.path.join(ROOT, rel)) if exists else 0
            size_s = human(size) if exists else "（已删除）"
            act = {"create": "新增", "modify": "修改", "delete": "删除"}.get(info["action"], info["action"])
            if b["online"]:
                t, why = tier(rel, info["action"], info["adds"], info["dels"])
                # 主题/静态资源：若与最新发布包内容一致，说明已经上传过了，别再报 C 档
                packed = None
                if exists and t.startswith("C"):
                    packed = in_pack(rel, md5_of(os.path.join(ROOT, rel)))
                if packed:
                    t = "✅ 已随发布包上线"
                    why = f"与最新发布包 `{packed}` 内容逐字节一致，无需再传"
                    online_items.append((rel, t, f"**{t}** — {why}"))
                    lines.append(f"| `{rel}` | {act} | +{info['adds']} −{info['dels']} | {size_s} | **{t}** — {why} |")
                    continue
                online_items.append((rel, t, judge_of(t, why, rel)))
                lines.append(f"| `{rel}` | {act} | +{info['adds']} −{info['dels']} | {size_s} | {judge_of(t, why, rel)} |")
            else:
                lines.append(f"| `{rel}` | {act} | +{info['adds']} −{info['dels']} | {size_s} | 内部文件，不影响线上 |")
        if rest:
            r_add = sum(i["adds"] for _, i in rest)
            r_del = sum(i["dels"] for _, i in rest)
            names = "、".join(f"`{r}`" for r, _ in rest[:4])
            lines.append(f"| …另有 {len(rest)} 个文件（累计 +{r_add} −{r_del}）| — | — | — | {names} 等 |")
        lines.append("")

    hits = []
    for prefixes, tip in DOWNSTREAM:
        if any(rel.startswith(p) for p in prefixes for rel in changes):
            hits.append(tip)
    if hits:
        lines.append("### 下游联动（改了上游，别忘了跑完下游）")
        lines.append("")
        for tip in hits:
            lines.append(f"- {tip}")
        lines.append("")

    if online_items:
        lines.append("### 待你拍板（影响线上的部分）")
        lines.append("")
        for rel, t, judge in online_items:
            lines.append(f"- `{rel}` → {judge}")
        lines.append("")
        lines.append("> 规则：A＝直铺；B＝本地渲染预览后再铺；C＝需真机（草稿预览/cPanel 子域）验收。详见 11-运营/每日上线评审流程.md")
    else:
        lines.append("### 待你拍板")
        lines.append("")
        lines.append("本次窗口内**没有影响线上的改动**，无需上线决策。")
    lines.append("")

    md = "\n".join(lines)
    print(md)
    if not args.md:
        os.makedirs(OUT_DIR, exist_ok=True)
        out = os.path.join(OUT_DIR, f"每日改动评审-{now:%Y-%m-%d}.md")
        with open(out, "w", encoding="utf-8") as f:
            f.write(md)
        print(f"\n[已写入] {out}", file=sys.stderr)


if __name__ == "__main__":
    main()
