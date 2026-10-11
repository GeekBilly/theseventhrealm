#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
生僻字注音注入器 —— 给页面 HTML 的生僻字加上 <ruby> 拼音。

设计要点（都是踩过的坑）：
  1. **只在文本节点内替换**：先扫描全串标记「标签 / script / style / 注释」区间，落在这
     些区间里的字符一个都不动，因此 href、alt、title、CSS 内容绝不会被误注。
  2. **幂等**：已有 <ruby>…</ruby> 区间整体排除；重复跑不会嵌套。
  3. **同页首次**：默认 mode=first，同一个字在一个页面只标第一次出现，避免满屏拼音。
  4. **不重建 HTML**：按字符偏移从后往前精确插入，其余字节逐字保留，diff 最干净。
  5. **字音表外置**：`11-运营/data/生僻字表.csv`，人工校过的读音，不靠自动注音。

用法：
  python3 annotate-ruby.py                    # dry-run，只看命中共多少字
  python3 annotate-ruby.py --apply            # 实际写入（自动备份到 备份/注音前-<日期>/）
  python3 annotate-ruby.py --mode all         # 每个字每处都标（默认 first）
  python3 annotate-ruby.py --level level2     # 放宽到 GB2312 二级字（会标得多很多）
"""
import argparse
import csv
import datetime
import html
import pathlib
import re
import shutil
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
TABLE = ROOT / '11-运营/data/生僻字表.csv'

PAGE_DIR = '03-页面/朝代页'          # 正文朝代页（线上 id 94-109，父页 32 5000years）
GLOB_FILES = [
    '03-页面/朝代页/*.html',          # 正文朝代页 16 个
    '03-页面/collection-dynasty-*.html',  # 藏品页下的朝代子页（线上 id 345-360）
    '03-页面/collection.html',
    '03-页面/faq.html',
]
EXCLUDE = {'备份', '校样归档', '参考资料', '站点文件'}

RUBY_CSS = """/* ruby注音 */
ruby{ruby-align:center;}
rt{font-size:.52em;line-height:1;letter-spacing:0;opacity:.72;font-weight:400;-webkit-text-size-adjust:none;}
rp{display:none;}
"""


def load_table():
    """读人工校过的字音表 → {字: 拼音}"""
    out = {}
    if not TABLE.exists():
        sys.exit(f'✗ 缺字音表：{TABLE}')
    for row in csv.DictReader(TABLE.open(encoding='utf-8-sig')):
        w = (row.get('字') or '').strip()
        p = (row.get('拼音') or '').strip()
        if w and p:
            out[w] = p
    return out


def tier(ch: str) -> str:
    try:
        q = ch.encode('gb2312')[0] - 0xA0
        return 'level1' if 16 <= q <= 55 else 'level2'
    except UnicodeEncodeError:
        return 'outer'


def text_positions(s: str):
    """返回布尔掩码：该下标是否处于「可被注音的纯文本」中。
    排除：HTML 标签区、script、style、注释、已有 ruby 区。"""
    n = len(s)
    safe = bytearray(b'\x01') * n          # 先全标安全
    i, stack = 0, []
    lower = s.lower()
    while i < n:
        if s.startswith('<!--', i):
            j = s.find('-->', i)
            j = n if j < 0 else j + 3
            safe[i:j] = b'\x00' * (j - i)
            i = j
            continue
        if s[i] == '<':
            m = re.match(r'</?([a-zA-Z][\w:-]*)', s[i:])
            if not m:
                i += 1
                continue
            tag = m.group(1).lower()
            j = s.find('>', i)
            if j < 0:
                break
            end = j + 1
            # script/style 整块吞掉
            if tag in ('script', 'style') and not lower.startswith('</', i):
                k = lower.find(f'</{tag}>', end)
                end = (n if k < 0 else k + len(tag) + 3)
            safe[i:end] = b'\x00' * (end - i)
            # ruby 区间整体排除（连同 rt/rp）
            if tag == 'ruby' and not lower.startswith('</', i):
                k = lower.find('</ruby>', end)
                end = (n if k < 0 else k + 7)
                safe[i:end] = b'\x00' * (end - i)
            i = end
            continue
        if s[i] == '&':
            j = s.find(';', i)
            if 0 < j < i + 12:
                safe[i:j + 1] = b'\x00' * (j + 1 - i)
                i = j + 1
                continue
        i += 1
    return safe


def annotate(s: str, table: dict, mode: str, level: str) -> tuple:
    """返回 (新字符串, [(字, 拼音)] 已标注清单)"""
    tiers = {'outer'} if level == 'outer' else {'outer', 'level2'}
    safe = text_positions(s)
    hits = []
    used = set()
    if mode == 'first':
        # ⭐ 幂等关键点：本文件里已标过音的字，一律视作「已用」。
        # 否则重跑时，上一轮因 first 模式跳过的重复位置会被再次当成首次，越跑越多。
        used |= set(re.findall(r'<ruby>(.+?)<rp>', s))
    edits = []                              # (index, 插入串)
    for i, ch in enumerate(s):
        if not safe[i]:
            continue
        if '\u4e00' <= ch <= '\u9fff' and tier(ch) in tiers and ch in table:
            if mode == 'first' and ch in used:
                continue
            used.add(ch)
            py = table[ch]
            edits.append((i, f'<ruby>{ch}<rp>(</rp><rt>{py}</rt><rp>)</rp></ruby>'))
            hits.append((ch, py))
    # 从前往后构建（不混下标）
    out, last = [], 0
    for i, ins in edits:
        out.append(s[last:i])
        out.append(ins)
        last = i + 1                        # 跳过被注音的那个字
    out.append(s[last:])
    return ''.join(out), hits


def ensure_css(s: str) -> str:
    """在内联 <style> 里追加 ruby 样式，幂等"""
    if '/* ruby注音 */' in s:
        return s
    m = re.search(r'</style>', s, re.I)
    if not m:
        return s
    return s[:m.start()] + RUBY_CSS + s[m.start():]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--apply', action='store_true', help='实际写入（默认 dry-run）')
    ap.add_argument('--mode', default='first', choices=['first', 'all'])
    ap.add_argument('--level', default='outer', choices=['outer', 'level2'])
    ap.add_argument('--files', nargs='*', help='指定文件，默认全部')
    args = ap.parse_args()

    table = load_table()
    if args.files:
        files = [ROOT / f for f in args.files]
    else:
        files = []
        for pattern in GLOB_FILES:
            files += sorted(p for p in (ROOT / pathlib.PurePosixPath(pattern).parent)
                            .glob(pathlib.PurePosixPath(pattern).name)
                            if p.parent.name not in EXCLUDE)
        files = sorted(set(files))

    stamp = datetime.date.today().strftime('%Y%m%d')
    backup_root = ROOT / f'03-页面/备份/注音前-{stamp}'
    total_files, total_hits = 0, []
    details = []

    for f in files:
        if not f.exists():
            print('  ⚠️ 不存在：', f)
            continue
        s = f.read_text(encoding='utf-8')
        new, hits = annotate(s, table, args.mode, args.level)
        if not hits:
            continue
        if '/* ruby注音 */' not in new:
            new = ensure_css(new)
        details.append((str(f.relative_to(ROOT)), len(hits),
                        ', '.join(f'{c}({p})' for c, p in hits)))
        total_hits.extend(hits)
        total_files += 1
        if args.apply:
            rel = f.relative_to(ROOT / '03-页面')
            tgt = backup_root / rel
            tgt.parent.mkdir(parents=True, exist_ok=True)
            if tgt.exists():
                # ⭐ 备份一旦存在绝不覆盖 —— 否则重跑时备份会被「已注音」的版本污染，回滚点就没了
                pass
            else:
                shutil.copy2(f, tgt)
            f.write_text(new, encoding='utf-8')

    tag = '已写入' if args.apply else 'DRY-RUN'
    print(f'[{tag}] 命中 {total_files} 个文件 / {len(total_hits)} 处注音 '
          f'（mode={args.mode}, level={args.level}, 字音表 {len(table)} 字）\n')
    for name, n, words in sorted(details, key=lambda x: -x[1]):
        print(f'  {n:3d} 处  {name}')
        print(f'        {words[:150]}')
    if args.apply:
        print(f'\n备份目录：{backup_root}')
    else:
        print('\n未写入。加 --apply 实际执行。')


if __name__ == '__main__':
    main()
