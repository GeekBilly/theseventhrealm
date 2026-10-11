#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
全站文字扫描器 —— 生僻字候选 + 专名候选

判据（可复现，不靠感觉）：
  汉字按 GB2312 区位分层 —— 16-55 区＝一级常用字；56-87 区＝二级次常用字；GB2312 之外＝大字区（基本都生僻）。
  默认候选线＝「二级次常用字 及 大字区」，可用 --level 调整。

用法：
  python3 scan-text-annotation.py                 # 扫默认页面集
  python3 scan-text-annotation.py --level strict  # 只收 GB2312 之外的字
  python3 scan-text-annotation.py --csv           # 导出逐字清单到 11-运营/data/

输出：
  · 每页汉字数 / 候选种类数
  · 候选生僻字 Top（按频次）
  · 专名候选（2-4 字高频 n-gram，供人工挑选）
"""
import argparse
import html
import pathlib
import re
import sys
from collections import Counter

ROOT = pathlib.Path(__file__).resolve().parents[2]

# 默认扫描集：站点正文页面（排除备份/校样归档）
PAGE_DIRS = [
    '03-页面',                # 根活动页（35 个）
    '03-页面/朝代页',          # 16 朝
]
EXCLUDE_DIRS = {'备份', '校样归档', '参考资料', '站点文件'}

SCRIPT_RE = re.compile(r'<(script|style)\b[^>]*>.*?</\1>', re.S | re.I)
COMMENT_RE = re.compile(r'<!--.*?-->', re.S)
TAG_RE = re.compile(r'<[^>]+>')
HAN_RE = re.compile(r'[\u4e00-\u9fff]')


def han_tier(ch: str) -> str:
    """返回汉字的字库分层：level1 / level2 / big5-outer / none"""
    if not HAN_RE.match(ch):
        return 'none'
    try:
        b = ch.encode('gb2312')
    except UnicodeEncodeError:
        return 'outer'          # GB2312 之外（GBK 大字区）
    qu = b[0] - 0xA0            # 区号
    return 'level1' if 16 <= qu <= 55 else 'level2'


def extract_text(path: pathlib.Path) -> str:
    s = path.read_text(encoding='utf-8', errors='replace')
    s = SCRIPT_RE.sub(' ', s)
    s = COMMENT_RE.sub(' ', s)
    s = TAG_RE.sub(' ', s)
    return html.unescape(s)


def collect_pages(level: str):
    files = []
    for d in PAGE_DIRS:
        p = ROOT / d
        if not p.exists():
            continue
        for f in sorted(p.glob('*.html')):
            if f.parent.name in EXCLUDE_DIRS:
                continue
            files.append(f)
    return files


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--level', default='default', choices=['strict', 'default'],
                    help='strict=只要 GB2312 之外的字；default=二级次常用字 + 之外')
    ap.add_argument('--csv', action='store_true', help='导出逐字清单')
    ap.add_argument('--ngram', type=int, default=12, help='专名候选输出条数')
    args = ap.parse_args()

    tiers = {'outer'} if args.level == 'strict' else {'level2', 'outer'}
    pages = collect_pages(args.level)

    total_han = 0
    rare = Counter()                 # 字 -> 次数
    rare_pages = Counter()           # 字 -> 出现在几个文件
    per_page = []
    all_text = []

    for f in pages:
        t = extract_text(f)
        all_text.append(t)
        hans = HAN_RE.findall(t)
        total_han += len(hans)
        cnt = Counter(hans)
        local = {c: n for c, n in cnt.items() if han_tier(c) in tiers}
        for c, n in local.items():
            rare[c] += n
            rare_pages[c] += 1
        per_page.append((str(f.relative_to(ROOT)), len(hans), len(local), sum(local.values())))

    print(f'扫描页面 {len(pages)} 个 · 汉字总量 {total_han:,} 字')
    print(f'候选生僻字：{len(rare)} 种 / 出现 {sum(rare.values()):,} 次')
    print(f'判据：{"GB2312 之外" if args.level=="strict" else "GB2312 二级次常用字 + 之外"}')

    print('\n【每页明细】（汉字数 / 候选种类 / 候选出现）')
    for name, n, kinds, hits in sorted(per_page, key=lambda x: -x[3]):
        print(f'  {kinds:4d} 种 {hits:6d} 次  {n:7,d} 字  {name}')

    print(f'\n【候选生僻字 Top 40（按频次）】')
    for c, n in rare.most_common(40):
        tier = han_tier(c)
        tag = '外' if tier == 'outer' else '二'
        print(f'  {c}  {n:5d} 次  散布 {rare_pages[c]:2d} 页  [{tag}]')

    # ---- 专名候选：2-4 字高频 n-gram ----
    print('\n【专名候选（高频 2-4 字串，供人工挑选）】')
    joined = ''.join(all_text)
    ng = Counter()
    for n in (2, 3, 4):
        seg = re.findall(r'[\u4e00-\u9fff]{%d}' % n, joined)
        ng.update(seg)
    # 过滤：频次 >= 8 且不是纯虚词组合
    stop = set('的一了是在有和不也要就都而为与之以及其之于此所者为所以及其'
               '这个我们你们他们它们可以因为所以但是然后如果虽然由于使得')
    cands = [(w, c) for w, c in ng.most_common(400)
             if c >= 8 and not (set(w) & set()) and len(set(w)) > 1
             and not any(ch in stop for ch in w)]
    for w, c in cands[:args.ngram * 3]:
        print(f'  {w}  {c}')

    if args.csv:
        out = ROOT / '11-运营/data/生僻字候选清单.csv'
        import csv as _csv
        with out.open('w', encoding='utf-8', newline='') as fh:
            w = _csv.writer(fh)
            w.writerow(['字', '出现次数', '散布页数', '字库分层', '建议拼音', '备注'])
            for c, n in rare.most_common():
                w.writerow([c, n, rare_pages[c],
                            {'outer': 'GB2312外', 'level2': '二级次常用'}[han_tier(c)], '', ''])
        print(f'\n已导出：{out}  （{len(rare)} 行，需人工填拼音后校一遍多音字）')


if __name__ == '__main__':
    main()
