#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
fetch-library-docs.py —— 把资料库（Library）里的一棵文档子树批量下载为本地 Markdown。

为什么要有这个脚本：资料库服务端返回的是「组件 XML」（Heading / Paragraph / Table /
TableCell / Mark / Code / BlockQuote / Divider …），不是 Markdown，复制粘贴拿不到可用的
文件。本脚本一次跑完：递归列树 → 逐篇取全文 → XML 转 Markdown → 按映射表落盘。

用法（两步走，改名可人工审定、可回滚）：

  # ① 只出映射表，不下载。--mode flat｜series 决定改名规则
  python3 11-运营/scripts/fetch-library-docs.py --plan \
      --space-id <spaceId> --root-node-id <nodeId> \
      --out-dir "01-内容/写作" --mode flat \
      --map 11-运营/data/fetch-library-docs.csv

  # ② 人工改过 CSV 之后，按 CSV 下载落盘（可多次重跑，已存在默认跳过）
  python3 11-运营/scripts/fetch-library-docs.py --apply \
      --map 11-运营/data/fetch-library-docs.csv [--force]

约定：
  · kind != doc 的节点（folder / web / page）不下载，映射表里标 skipped
  · 目标路径是相对 --out-dir 的相对路径；CSV 里每行自带 out_dir，② 不需再传
  · 中文引号、反斜杠续行（`\\`+换行）在转换时还原为正常换行
"""
import argparse
import csv
import json
import re
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

SKILL_DIR = Path(
    "/Applications/WorkBuddy.app/Contents/Resources/app.asar.unpacked/resources"
    "/plugins/workbuddy-builtin/skills/library"
)
SPACE_API = SKILL_DIR / "space_api.py"
DOC_READ = SKILL_DIR / "doc" / "get_doc_reviews.py"
PY = sys.executable

UNSEEN_TAGS = set()
FIELDS = ["node_id", "kind", "cloud_path", "title", "out_dir", "target", "bytes", "status", "note"]


# ---------------------------------------------------------------- 资料库读取
def list_nodes(space_id, parent_id=None):
    """列出一层子节点，自动翻页。"""
    nodes, offset = [], 0
    while True:
        cmd = [PY, str(SPACE_API), "space.workspace.list-nodes",
               "--space-id", space_id, "--limit", "100", "--offset", str(offset)]
        if parent_id:
            cmd += ["--parent-node-id", parent_id]
        r = subprocess.run(cmd, capture_output=True, text=True, cwd=str(SKILL_DIR))
        if not r.stdout.strip():
            raise RuntimeError("list-nodes 空返回：%s" % r.stderr[:300])
        data = json.loads(r.stdout)["data"]
        nodes.extend(data["nodes"])
        if not data.get("hasMore"):
            break
        offset = data["offset"] + data["limit"]
    return nodes


def walk(space_id, parent_id=None, trail=None):
    """深度优先遍历子树，yield (node, trail)。trail 不含 root 自身。"""
    trail = trail or []
    for n in list_nodes(space_id, parent_id):
        t = trail + [n["title"]]
        yield n, t
        if n.get("nodes"):
            yield from walk(space_id, n["id"], t)


def fetch_doc(node_id):
    """取一篇文档的原始正文（组件 XML + front matter）。"""
    r = subprocess.run([PY, str(DOC_READ), "--page-id", node_id],
                       capture_output=True, text=True, cwd=str(SKILL_DIR))
    if not r.stdout.strip():
        return None, "空返回：%s" % r.stderr[:200]
    return r.stdout, None


# ---------------------------------------------------------------- 命名规则
CN_DIGIT = {"零": 0, "一": 1, "二": 2, "三": 3, "四": 4, "五": 5,
            "六": 6, "七": 7, "八": 8, "九": 9, "十": 10}


def cn2int(s):
    if s.isdigit():
        return int(s)
    if s in CN_DIGIT:
        return CN_DIGIT[s]
    if "十" in s:
        a, _, b = s.partition("十")
        return (CN_DIGIT.get(a, 1) if a else 1) * 10 + (CN_DIGIT.get(b, 0) if b else 0)
    total = 0
    for ch in s:
        total = total * 10 + CN_DIGIT.get(ch, 0)
    return total


def sanitize(name):
    """按项目命名规范清洗：去括号补充、空格/下划线转连字符、去非法字符。"""
    s = name.strip()
    s = re.sub(r"[（(]\s*[^）)]*\s*[)）]", "", s)   # 括号内容丢弃（信息留映射表与 README）
    s = s.replace(" ", "-").replace("\u3000", "-").replace("_", "-")
    s = re.sub(r"\s*-\s*", "-", s)
    s = re.sub(r"-{2,}", "-", s)
    s = re.sub(r'[\\/:*?"<>|\n\r\t]', "", s)
    return s.strip("-.")


def chapter_no(title):
    m = re.search(r"第\s*([0-9]+)\s*章", title)
    if m:
        return int(m.group(1)), m.group(1)
    m = re.search(r"第([一二三四五六七八九十百]+)章", title)
    if m:
        return cn2int(m.group(1)), m.group(1)
    return None, None


def material_index(title):
    """非章节稿件的固定排序：梗概 → 大纲 → 人物 → 世界观 → 背景 → 其它。"""
    if "故事梗概" in title:
        return 0
    if "大纲" in title:
        return 1
    if "人物" in title:
        return 2
    if "世界观" in title or "设定" in title:
        return 3
    if "背景" in title:
        return 4
    return 5


def flat_target(trail, used):
    """平铺模式：标题已是 NN-主题 格式，直接清洗成文件名。"""
    title = trail[-1]
    base = sanitize(title)
    name = base + ".md"
    i = 2
    while name in used:
        name = "%s-v%d.md" % (base, i)
        i += 1
    used.add(name)
    return name


def series_target(trail, used):
    """分卷模式：一级目录 = 部，文件 = 00-09 前置材料 / 10+ 章节。"""
    parts = []
    for i, t in enumerate(trail):
        if i < len(trail) - 1:                      # 目录层
            m = re.search(r"第\s*([一二三四五六七八九十]+)\s*部", t)
            if m:
                name = re.sub(r"^.*?第[^部]*部\s*-\s*", "", t)
                parts.append("%02d-%s" % (cn2int(m.group(1)), sanitize(name)))
            elif "大纲" in t or "时间线" in t:
                parts.append("00-" + sanitize(t))
            else:
                parts.append(sanitize(t))
            continue
        # 文件层
        no, cn = chapter_no(t)
        if no is not None:
            rest = sanitize(re.sub(r"第[0-9一二三四五六七八九十百]+\s*章", "", t))
            parts.append("%02d-第%s章-%s.md" % (9 + no, cn, rest) if rest
                         else "%02d-第%s章.md" % (9 + no, cn))
        else:
            parts.append("%02d-%s.md" % (material_index(t), sanitize(t)))
    target = "/".join(parts)
    if target in used:                               # 极小概率撞名，加序号
        stem, dot, ext = target.rpartition(".")
        i = 2
        while "%s-v%d.%s" % (stem, i, ext) in used:
            i += 1
        target = "%s-v%d.%s" % (stem, i, ext)
    used.add(target)
    return target


# ---------------------------------------------------------------- XML → Markdown
FM_RE = re.compile(r"^---\n(.*?)\n---\n", re.S)
TAG_RE = re.compile(r"<(/?)([A-Za-z][\w.-]*)((?:\s+[A-Za-z][\w:-]+(?:=\"[^\"]*\")?)*)\s*(/?)>")


def _fix_bare_attrs(m):
    """<Mark bold> → <Mark bold="1">；闭合标签原样返回。"""
    close, tag, attrs, self_closing = m.groups()
    if close:
        return m.group(0)
    parts = [a if "=" in a else a + '="1"' for a in attrs.split()]
    return "<%s%s%s>" % (tag, (" " + " ".join(parts)) if parts else "", self_closing)


def clean_text(s):
    if not s:
        return ""
    s = re.sub(r"\\\n[ \t]*", "\n", s)      # 服务端用 \+换行 表示软换行
    s = s.replace('\\"', '"').replace("\\'", "'")
    s = re.sub(r"\n[ \t]{2,}", "\n", s)     # 去掉 XML 序列化缩进
    return s.strip()


def inline(el):
    parts = [el.text or ""]
    for c in el:
        parts.append(inline_node(c))
        parts.append(c.tail or "")
    return "".join(parts)


def inline_node(el):
    t = inline(el)
    tag = el.tag
    if tag == "Mark":
        attrs = [k for k in el.attrib if k != "id"]
        if "code" in attrs:
            t = "`%s`" % t
        if "bold" in attrs:
            t = "**%s**" % t
        if "italic" in attrs:
            t = "*%s*" % t
        if "strikethrough" in attrs:
            t = "~~%s~~" % t
        return t
    if tag == "Link":
        href = el.get("href") or el.get("url") or ""
        return "[%s](%s)" % (t, href) if href else t
    if tag in ("Br", "Break"):
        return "\n"
    return t


def render_children(el):
    return "".join(render_node(c) for c in el)


def render_node(el):
    tag = el.tag
    if tag == "Heading":
        lv = min(int(el.get("level", 1)), 6)
        txt = clean_text(inline(el))
        return ("#" * lv) + " " + txt + "\n\n" if txt else ""
    if tag == "Paragraph":
        txt = clean_text(inline(el))
        return txt + "\n\n" if txt else ""
    if tag == "BlockQuote":
        inner = (clean_text(el.text or "") + "\n\n" + render_children(el)).strip()
        if not inner:
            return ""
        return "\n".join(("> " + l).rstrip() for l in inner.splitlines()) + "\n\n"
    if tag == "Divider":
        return "---\n\n"
    if tag == "Code":
        lang = el.get("language", "")
        code = (el.text or "").strip("\n")
        return "```%s\n%s\n```\n\n" % (lang, code)
    if tag == "Table":
        rows = []
        for tr in el:
            if tr.tag != "TableRow":
                continue
            rows.append([clean_text(inline(td)).replace("|", "\\|")
                         for td in tr if td.tag == "TableCell"])
        if not rows:
            return ""
        width = max(len(r) for r in rows)
        out = ["| " + " | ".join(rows[0] + [""] * (width - len(rows[0]))) + " |",
               "|" + "|".join(["---"] * width) + "|"]
        for r in rows[1:]:
            out.append("| " + " | ".join(r + [""] * (width - len(r))) + " |")
        return "\n".join(out) + "\n\n"
    if tag in ("ListItem", "BulletListItem", "OrderedListItem", "NumberedListItem",
               "TaskListItem", "ToggleListItem"):
        inner = render_children(el).strip()
        if not inner:
            return ""
        marker = "1. " if ("Ordered" in tag or "Numbered" in tag) else "- "
        if tag == "TaskListItem":
            marker = "- [ ] " if el.get("checked") in (None, "false") else "- [x] "
        lines = inner.splitlines()
        return marker + lines[0] + "\n" + "".join("  " + l + "\n" for l in lines[1:])
    if tag.endswith("List"):          # BulletList / OrderedList / NumberedList / List
        # 列表容器里常见「纯文本 + 子元素」混排，只渲染子元素会吃掉 el.text
        head = clean_text(el.text or "")
        return (head + "\n\n" if head else "") + render_children(el) + "\n"

    if tag == "Mark":                                # 加粗段落：Mark 直接挂在块级位置
        txt, attrs = clean_text(inline(el)), [k for k in el.attrib if k != "id"]
        if "code" in attrs:
            txt = "`%s`" % txt
        if "bold" in attrs:
            txt = "**%s**" % txt
        if "italic" in attrs:
            txt = "*%s*" % txt
        return txt + "\n\n" if txt else ""
    if tag in ("Link", "Br", "Break", "Text", "Span"):
        txt = clean_text(inline(el))
        return txt + "\n\n" if txt else ""

    UNSEEN_TAGS.add(tag)
    head = clean_text(el.text or "")
    inner = render_children(el)
    body = (head + "\n\n" if head else "") + inner
    return body if body.strip() else ""


def cn_count(s):
    return len(re.findall(r"[\u4e00-\u9fff]", s))


def convert(raw):
    """组件 XML → Markdown，返回 (markdown, 警告)。"""
    title, body = None, raw
    m = FM_RE.match(raw)
    if m:
        for line in m.group(1).splitlines():
            if line.startswith("title:"):
                title = line.split(":", 1)[1].strip()
        body = raw[m.end():]
    body = re.sub(r"^KS_[A-Z_]+\t.*$", "", body, flags=re.M)   # 去掉脚本输出自带的元信息行
    # XML 1.0 不允许的控制字符（\x0b 等在旧稿里真实存在，不剔除会导致整篇解析失败）
    body = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", body)
    # 服务端会把 <Mark bold> 写成裸属性（非法 XML），补成 bold="1" 才能解析
    body = TAG_RE.sub(_fix_bare_attrs, body)
    body = re.sub(r"&(?!(?:amp|lt|gt|quot|apos|#\d+|#x[0-9a-fA-F]+);)", "&amp;", body)
    try:
        root = ET.fromstring("<root>\n%s\n</root>" % body)
    except ET.ParseError as e:
        text = re.sub(r"</?[A-Za-z][^>]*>", "", body)
        text = clean_text(text)
        text = re.sub(r"\n{2,}", "\n\n", text)                 # 降级路径同样压空行
        return "# %s\n\n%s\n" % (title or "", text), "XML 解析失败，已降级为纯文本：%s" % e
    md = render_children(root)
    md = re.sub(r"\n{3,}", "\n\n", md).strip() + "\n"
    if title and not md.lstrip().startswith("#"):
        md = "# %s\n\n%s" % (title, md)
    return md, None


# ---------------------------------------------------------------- 主流程
def cmd_plan(args):
    nodes = list(walk(args.space_id, args.root_node_id))
    used, rows = set(), []
    for n, trail in nodes:
        cloud = " / ".join(trail)
        if n["kind"] != "doc":
            rows.append(dict(node_id=n["id"], kind=n["kind"], cloud_path=cloud, title=n["title"],
                             out_dir=args.out_dir, target="", bytes="", status="skipped",
                             note="非文档节点，不下载"))
            continue
        target = (flat_target if args.mode == "flat" else series_target)(trail, used)
        rows.append(dict(node_id=n["id"], kind=n["kind"], cloud_path=cloud, title=n["title"],
                         out_dir=args.out_dir, target=target, bytes="", status="planned", note=""))
    write_csv(args.map, rows)
    docs = sum(1 for r in rows if r["kind"] == "doc")
    print("映射表已写入：%s" % args.map)
    print("共 %d 个节点，其中文档 %d 篇（跳过 %d 个非文档节点）"
          % (len(rows), docs, len(rows) - docs))
    print("下一步：人工过一遍 target 列，确认后跑 --apply")


def cmd_apply(args):
    rows = read_csv(args.map)
    base_done = base_skip = base_fail = 0
    for r in rows:
        if r["kind"] != "doc" or not r["target"]:
            continue
        out = Path(r["out_dir"]) / r["target"]
        if out.exists() and not args.force:
            base_skip += 1
            continue
        raw, err = fetch_doc(r["node_id"])
        if err:
            r["status"], r["note"] = "failed", err
            base_fail += 1
            continue
        md, warn = convert(raw)
        # 字数守恒：转换后中文字符不应明显少于原文，差太多说明有内容被吃掉
        c_src, c_out = cn_count(raw), cn_count(md)
        if c_src >= 50 and c_out < c_src * 0.85:
            warn = (warn + " " if warn else "") + "⚠️中文字符 %d→%d，疑似丢内容" % (c_src, c_out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(md, encoding="utf-8")
        r["bytes"], r["status"] = str(len(md.encode("utf-8"))), "done"
        r["note"] = warn or ""
        base_done += 1
        print("  ✓ %s → %s (%s 字节)" % (r["title"], out, r["bytes"]))
    write_csv(args.map, rows)
    print("\n完成：下载 %d 篇 / 已存在跳过 %d / 失败 %d" % (base_done, base_skip, base_fail))
    degraded = [r for r in rows if r["status"] == "done" and r["note"]]
    if degraded:
        print("⚠️ 降级 %d 篇（正文含异常字符，格式可能不全）：" % len(degraded))
        for r in degraded:
            print("    - %s" % r["target"])
    if UNSEEN_TAGS:
        print("⚠️ 出现未识别标签（已按纯文本降级）：%s" % ", ".join(sorted(UNSEEN_TAGS)))


def write_csv(path, rows):
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        w.writerows(rows)


def read_csv(path):
    with Path(path).open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def main():
    ap = argparse.ArgumentParser(description="资料库文档子树 → 本地 Markdown")
    ap.add_argument("--plan", action="store_true", help="只生成映射表")
    ap.add_argument("--apply", action="store_true", help="按映射表下载落盘")
    ap.add_argument("--space-id")
    ap.add_argument("--root-node-id")
    ap.add_argument("--out-dir", help="本地目标根目录（相对工作区根）")
    ap.add_argument("--mode", choices=["flat", "series"], default="flat",
                    help="flat=标题已带 NN- 前缀直接清洗；series=按部/章重新编号")
    ap.add_argument("--map", default="11-运营/data/fetch-library-docs.csv")
    ap.add_argument("--force", action="store_true", help="覆盖已存在文件")
    a = ap.parse_args()
    if a.plan == a.apply:
        ap.error("必须且只能指定 --plan 或 --apply")
    if a.plan and not (a.space_id and a.root_node_id and a.out_dir):
        ap.error("--plan 需要 --space-id / --root-node-id / --out-dir")
    (cmd_plan if a.plan else cmd_apply)(a)


if __name__ == "__main__":
    main()
