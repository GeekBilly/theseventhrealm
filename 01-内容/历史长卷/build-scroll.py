#!/usr/bin/env python3
"""长卷（`/5000years/`）内容扩写：把事件库 119 个节点回填进 16 个朝代块。

用法：
    python3 01-内容/历史长卷/build-scroll.py

幂等：先摘掉已有的 `<ul class="nodes">…</ul>`，再按 `事件库/all.csv` 重新生成。
生成物（两个文件保持同步，勿手改）：
    content-5000years.html  ← 粘进 WP「自定义 HTML」区块的正文片段
    5000years.html          ← 整页源码（本地预览 / 交给 ops 的完整版）

数据来源：`事件库/all.csv`（年份,事件,一句话,所属朝代；负数为公元前）。
"""

import csv
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent
CSV = ROOT / '事件库' / 'all.csv'
TARGETS = ['content-5000years.html', '5000years.html']

NODES_CSS = """
/* 长卷 · 事件节点（由 build-scroll.py 生成，勿手改） */
.era .nodes{list-style:none;padding:0;margin:16px auto 0;max-width:580px;text-align:left}
.era .nodes li{font-size:13px;line-height:1.8;color:#5a554c;padding:5px 0;
 border-top:1px dashed rgba(26,26,24,.13)}
.era .nodes li:first-child{border-top:0}
.era .nodes b{font-family:Georgia,"Times New Roman",serif;font-weight:600;
 color:#26241f;margin-right:10px}
.era .nodes .say{display:block;color:#8a8478;font-size:12.5px}
"""

# 朝代块：<div class="era …"> … </div>（两空格缩进，与现有文件一致）
ERA_RE = re.compile(r'(  <div class="era[^"]*"[^>]*>\n)(.*?)(\n  </div>)', re.S)


def cn(s):
    return len(re.findall(r'[\u4e00-\u9fff]', s))


def norm(s):
    """把标题里的朝代名归一：去标签、去「周 · 春秋战国」里的后半段。"""
    return re.sub(r'<[^>]+>', '', s).split('·')[0].strip()


def fmt_year(y):
    y = int(y)
    return f'前 {abs(y)} 年' if y < 0 else f'{y} 年'


def load_nodes():
    """读 all.csv，按朝代归组；返回 (按出现顺序的朝代名, {朝代: [(年份, 事件, 一句话)]})"""
    order, by = [], {}
    with CSV.open(encoding='utf-8-sig', newline='') as f:
        for row in csv.DictReader(f):
            era = row['所属朝代'].strip()
            if era not in by:
                by[era] = []
                order.append(era)
            by[era].append((fmt_year(row['年份'].strip()),
                            row['事件'].strip(),
                            row['一句话'].strip()))
    return order, by


def expand(html, by):
    """在每朝 note 段之后插入事件节点列表。"""
    used, missing = 0, []

    def repl(m):
        nonlocal used
        head, body, tail = m.group(1), m.group(2), m.group(3)
        name = norm(re.search(r'<h3>(.*?)</h3>', body).group(1))
        body = re.sub(r'\n    <ul class="nodes">.*?</ul>', '', body, flags=re.S)
        nodes = by.get(name)
        if not nodes:
            missing.append(name)
            return m.group(0)
        used += len(nodes)
        ul = '\n    <ul class="nodes">\n' + ''.join(
            f'      <li><b>{y}</b>{ev}<span class="say">{say}</span></li>\n'
            for y, ev, say in nodes
        ) + '    </ul>'
        cut = body.rfind('</p>') + 4          # note 段之后（ghost 是 span，不受影响）
        return head + body[:cut] + ul + body[cut:] + tail

    out = ERA_RE.sub(repl, html)
    return out, used, missing


def ensure_css(html):
    if '.era .nodes' in html:
        return html, False
    i = html.rfind('</style>')
    if i < 0:
        print(f'  ⚠️ 未找到 </style>，跳过样式注入')
        return html, False
    return html[:i] + NODES_CSS + html[i:], True


def main():
    order, by = load_nodes()
    total = sum(len(v) for v in by.values())
    print(f'事件库：{len(order)} 朝 / {total} 个节点')

    for name in TARGETS:
        p = ROOT / name
        before = p.read_text(encoding='utf-8')
        after, used, missing = expand(before, by)
        after, css_added = ensure_css(after)
        if after == before:
            print(f'  ↺ {name} 无变化')
            continue
        p.write_text(after, encoding='utf-8')
        print(f'  ✓ {name}  {cn(before)} → {cn(after)} 中文字符'
              f'（+{cn(after) - cn(before)}，写入 {used} 个节点'
              f'{"，补样式" if css_added else ""}）')
        if missing:
            print(f'    ⚠️ 事件库里没匹配到：{missing}')

    if sum(len(v) for v in by.values()) != 119:
        print('⚠️ 节点总数不是 119，检查 all.csv', file=sys.stderr)


if __name__ == '__main__':
    main()
