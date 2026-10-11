#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
行内注音注入器 —— 把拼音放在词后面、用全角括号包起来（用户 2026-10-05 定的样式）：

    氾胜之（Fánshèngzhī）      ← 整词连写，只标一次
    羑里（Yǒulǐ）
    珷（wǔ）

取代上一版「字上方 <ruby>」的写法。为什么整词连写：逐字插括号会把人名切成
「氾（Fán）胜（shèng）之（zhī）」，读起来是碎的。

设计要点（沿用 annotate-ruby.py 踩出来的坑）：
  1. **只在文本节点内替换**：标签 / script / style / 注释 / HTML 实体一概不动，
     因此 href、alt、title、CSS 内容绝不会被误注。
  2. **幂等**：已存在「词（拼音）」原样跳过；重跑产出 0 处。
  3. **每页每词只标首次**：避免满屏拼音。
  4. **词表外置**：`11-运营/data/注音词表-行内.csv`，人工定词、人工定音，不靠自动注音。
  5. **可逆**：`--strip` 去掉「（拼音）」后逐字节还原原文。

大小写口径：专有名词（人名/地名/年号/篇名/器物名）首字母大写；普通词（絁·抔·胈·乂·珷·
神祇·束脩·叠词）全小写。

用法：
  python3 annotate-inline.py                 # dry-run
  python3 annotate-inline.py --apply         # 写入（自动备份）
  python3 annotate-inline.py --strip-ruby    # 褪掉旧的 ruby 注音（回退到原文）
  python3 annotate-inline.py --strip         # 褪掉行内注音（回退到原文）
"""
import argparse
import csv
import datetime
import pathlib
import re
import shutil
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
TABLE = ROOT / '11-运营/data/注音词表-行内.csv'
PAGE_DIR = ROOT / '03-页面/朝代页'

RUBY_RE = re.compile(r'<ruby>(.+?)<rp>\(</rp><rt>[^<]+</rt><rp>\)</rp></ruby>', re.S)
CSS_RE = re.compile(r'/\* ruby注音 \*/\s*ruby\{[^}]*\}\s*rt\{[^}]*\}\s*rp\{[^}]*\}\s*', re.S)


def load_table():
    """读人工定过的词表 → {页面slug: [(词, 拼音, 类型)]}"""
    out = {}
    if not TABLE.exists():
        sys.exit(f'✗ 缺词表：{TABLE}')
    for row in csv.DictReader(TABLE.open(encoding='utf-8-sig')):
        page = (row.get('页面') or '').strip()
        word = (row.get('词') or '').strip()
        py = (row.get('拼音') or '').strip()
        kind = (row.get('类型') or '').strip()
        if page and word and py:
            out.setdefault(page, []).append((word, py, kind))
    return out


def text_positions(s: str):
    """布尔掩码：该下标是否处于「可注音的纯文本」中。
    排除：HTML 标签区、script、style、注释、HTML 实体。"""
    n = len(s)
    safe = bytearray(b'\x01') * n
    i = 0
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
            if tag in ('script', 'style') and not lower.startswith('</', i):
                k = lower.find(f'</{tag}>', end)
                end = (n if k < 0 else k + len(tag) + 3)
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


def strip_ruby(s: str) -> str:
    """褪掉 <ruby> 注音：只留字，并移除注入的 CSS。"""
    s = RUBY_RE.sub(r'\1', s)
    return CSS_RE.sub('', s)


def strip_inline(s: str, words: list) -> str:
    """褪掉行内注音 → 词。三种形态都要能褪：
      全角「氾胜之（Fánshèngzhī）」／半角「彦悰(Yàncóng)」／并入「朱载堉（Zhūzàiyù，1536—1611）」。
    ⚠️ 并入形态不能整段替换成词——那样会把原文的生卒年一起吃掉。"""
    for w, py, _ in words:
        s = s.replace(f'{w}（{py}，', f'{w}（').replace(f'{w}({py},', f'{w}(')
        s = s.replace(f'{w}（{py}）', w).replace(f'{w}({py})', w)
    return s


def paren_depth(s: str, safe) -> list:
    """每个下标是否处在「未闭合的全角（」内部（只统计纯文本区的括号）。
    处在里面就改用半角括号，避免出现「（慧立、彦悰（Yàncóng）撰）」这种套娃。"""
    out = [0] * len(s)
    d = 0
    for i, ch in enumerate(s):
        if ch == '（':
            d += 1
        elif ch == '）':
            d = max(0, d - 1)
        out[i] = 1 if (d > 0 and safe[i]) else 0
    return out


def annotate(s: str, words: list) -> tuple:
    """返回 (新字符串, [(词, 拼音, 类型)])"""
    safe = text_positions(s)
    inside = paren_depth(s, safe)
    edits, hits = [], []
    for w, py, kind in words:
        # ⚠️ 幂等判据只比对「词（拼音」这一段，不带上右括号：
        # 有些位置是人工把拼音并进了原文已有的括号里（如「三联甗（Sānliányǎn，一件灶架…）」），
        # 写全角右括号会判成「没标过」而重复插入。
        if f'{w}（{py}' in s or f'{w}({py}' in s:   # 幂等：本页这个词已经标过
            continue                                 # （三种形态的左半段都一样，够用）
        pos = 0
        while True:
            i = s.find(w, pos)
            if i < 0:
                break
            # 必须整词都落在纯文本里。
            # ⚠️ 判「已标过」不能只看后面有没有左括号——原文里本来就有括号注释
            #   （如「三联甗（一件灶架…）」），会被误判成已标而整处漏掉。
            #   必须比对完整的「（拼音」。
            tail = s[i + len(w):]
            if all(safe[i:i + len(w)]) and not (tail.startswith(f'（{py}') or tail.startswith(f'({py}')):
                if inside[i]:
                    # ① 已在全角括号里 → 用半角，不套娃
                    marked, span = f'{w}({py})', len(w)
                elif tail.startswith('（'):
                    # ② 后面紧跟原文的注释括号 → 并进去，避免出现「（拼音）（1536—1611）」双括号。
                    #    ⚠️ span 要 +1 吃掉原文那个左括号，否则会写出「（拼音，（1536…」这种残废串。
                    marked, span = f'{w}（{py}，', len(w) + 1
                else:
                    # ③ 常规：词后加全角括号
                    marked, span = f'{w}（{py}）', len(w)
                edits.append((i, span, marked))
                hits.append((w, py, kind))
                break
            pos = i + 1
    out, last = [], 0
    for i, span, marked in sorted(edits):
        out.append(s[last:i])
        out.append(marked)
        last = i + span
    out.append(s[last:])
    return ''.join(out), hits


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--apply', action='store_true', help='实际写入（默认 dry-run）')
    ap.add_argument('--strip-ruby', action='store_true', help='褪掉旧 ruby 注音（回退原文）')
    ap.add_argument('--strip', action='store_true', help='褪掉行内注音（回退原文）')
    ap.add_argument('--files', nargs='*', help='指定文件，默认朝代页全部')
    args = ap.parse_args()

    table = load_table()
    files = [ROOT / f for f in args.files] if args.files else sorted(PAGE_DIR.glob('*.html'))

    stamp = datetime.date.today().strftime('%Y%m%d')
    backup_root = ROOT / f'03-页面/备份/行内注音前-{stamp}'
    total_files, total_hits, details = 0, [], []

    for f in files:
        if not f.exists():
            print('  ⚠️ 不存在：', f)
            continue
        slug = f.stem
        words = table.get(slug, [])
        s = f.read_text(encoding='utf-8')

        if args.strip_ruby or args.strip:
            new = strip_ruby(s)
            if args.strip:
                new = strip_inline(new, words)
            if new == s:
                continue
            if args.apply:
                tgt = backup_root / f.relative_to(ROOT / '03-页面')
                tgt.parent.mkdir(parents=True, exist_ok=True)
                if not tgt.exists():        # 备份一旦存在绝不覆盖（回滚点不能被污染）
                    shutil.copy2(f, tgt)
                f.write_text(new, encoding='utf-8')
            print(f'  {f.relative_to(ROOT)}  褪注音 {len(s) - len(new)} 字节')
            total_files += 1
            continue

        if not words:
            continue
        new, hits = annotate(s, words)
        if not hits:
            continue
        # 先把残留的 ruby 褪干净（换样式时旧写法不该留着）
        if '<ruby>' in new:
            new = strip_ruby(new)
        details.append((str(f.relative_to(ROOT)), len(hits),
                        '，'.join(f'{w}（{p}）' for w, p, _ in hits)))
        total_hits.extend(hits)
        total_files += 1
        if args.apply:
            tgt = backup_root / f.relative_to(ROOT / '03-页面')
            tgt.parent.mkdir(parents=True, exist_ok=True)
            if not tgt.exists():
                shutil.copy2(f, tgt)
            f.write_text(new, encoding='utf-8')

    tag = '已写入' if args.apply else 'DRY-RUN'
    print(f'[{tag}] 命中 {total_files} 个文件 / {len(total_hits)} 处注音\n')
    for name, n, words_str in sorted(details, key=lambda x: -x[1]):
        print(f'  {n:3d} 处  {name}')
        print(f'        {words_str}')
    if args.apply:
        print(f'\n备份目录：{backup_root}')
    elif not (args.strip or args.strip_ruby):
        print('\n未写入。加 --apply 实际执行。')


if __name__ == '__main__':
    main()
