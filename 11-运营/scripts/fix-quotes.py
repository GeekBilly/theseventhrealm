#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
正文引号修正器 —— 把源码里的 ASCII 直引号 `"` 换成确定的全角弯引号 “ ”。

为什么必须改源码（而不是让 WordPress 转）：WP 的 wptexturize 按**英文规则**判断开合——
看引号前一个字符是不是空白。中文里引号前紧跟汉字、一个空格都没有，于是每个都被判成
"闭合" → 全变成右引号。实测唐页 3 个左 / 91 个右。详见
`11-运营/reports/引号写法问题-诊断-2026-10-07.md`。

设计要点：
  1. **开合靠顺序配对，不靠上下文猜**。整篇正文里第 1/3/5… 个 `"` 是开，第 2/4/6… 个是闭。
     （上下文猜测正是 WP 翻车的那条路，别重蹈覆辙。）
  2. **只在文本节点内替换**：标签属性、script、style、注释、HTML 实体一概不碰。
  3. **英文语境跳过**：引号两侧都非汉字的（如英文法务页 `"THE SEVENTH REALM"`）保持原样，
     英文本来就该用直引号。
  4. **幂等**：源码里没有半角引号 → 直接跳过，重跑产出 0 处。
  5. **可逆**：`--strip` 把 “ ” 换回 `"`。
     ⚠️ 它是"全角一律换回半角"的粗暴操作：原本就写全角的位置也会被换掉。
     实测 18 个文件里 17 个逐字节还原，唯一例外是 `han.html`——它原文混了 3 对全角，
     被一并换回半角了。**权威回滚点是 `--apply` 生成的备份目录，优先用它整目录覆盖。**
  6. 奇数个引号 = 一定有问题（有落单的）→ **该文件整体跳过并报警**，绝不猜。

用法：
  python3 fix-quotes.py                     # dry-run
  python3 fix-quotes.py --apply             # 写入（自动备份）
  python3 fix-quotes.py --strip             # 回退到半角原文
  python3 fix-quotes.py --check             # 只体检：统计每个文件的半角引号数与是否为奇数
"""
import argparse
import datetime
import pathlib
import re
import shutil
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
PAGE_DIR = ROOT / '03-页面'
SKIP_DIRS = {'备份', '校样归档'}
OPEN, CLOSE = '\u201c', '\u201d'
CJK = re.compile(r'[\u4e00-\u9fff\u3000-\u303f\uff00-\uffef]')


def text_positions(s: str):
    """布尔掩码：该下标是否处于「纯文本」中。
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


def neighbors(s: str, i: int, width: int = 6):
    """取位置 i 左右最近的文字（跳过标签）"""
    left = re.sub(r'<[^>]+>', '', s[max(0, i - 40):i])[-width:]
    right = re.sub(r'<[^>]+>', '', s[i + 1:i + 41])[:width]
    return left, right


def targets(path: pathlib.Path):
    if path.is_file():
        return [path]
    return sorted(f for f in PAGE_DIR.rglob('*.html')
                  if not SKIP_DIRS & set(f.relative_to(PAGE_DIR).parts))


def process(s: str, strip: bool):
    """返回 (新串, 报告文本 or None)"""
    if strip:
        n = len(re.findall(r'[\u201c\u201d]', s))
        if not n:
            return (s, None)
        return (s.replace(OPEN, '"').replace(CLOSE, '"'), f'{n:>5} 处已还原为半角')

    safe = text_positions(s)
    hits = [i for i, ch in enumerate(s) if ch == '"' and safe[i]]
    if not hits:
        return (s, None)
    if len(hits) % 2:
        # 有落单的引号，顺序配对会全盘错位 —— 交给人工，不猜
        return (s, f'✗ {len(hits)} 个引号（奇数），跳过')

    edits, skipped_en, report = [], 0, []
    for k, i in enumerate(hits):
        left, right = neighbors(s, i)
        if not (CJK.search(left) or CJK.search(right)):
            skipped_en += 1
            continue
        edits.append((i, OPEN if k % 2 == 0 else CLOSE))
        if len(report) < 2:
            seg = re.sub(r'<[^>]+>', '', s[max(0, i - 16):i + 18]).replace('\n', ' ')
            report.append(f'      …{seg}…')

    if not edits:
        # 全部是英文语境（保持原样）——不算「涉及」，否则幂等复跑永远报 2 个文件
        return (s, None)
    out, last = [], 0
    for i, ch in edits:
        out.append(s[last:i])
        out.append(ch)
        last = i + 1
    out.append(s[last:])
    note = f'{len(edits):>5} 处 → “ ”' + (f'（{skipped_en} 处英文语境保持原样）' if skipped_en else '')
    return (''.join(out), note + ('\n' + '\n'.join(report) if report else ''))


def backup(f: pathlib.Path, root: pathlib.Path):
    tgt = root / f.relative_to(PAGE_DIR)
    tgt.parent.mkdir(parents=True, exist_ok=True)
    if not tgt.exists():          # 备份一旦存在绝不覆盖（回滚点不能被污染）
        shutil.copy2(f, tgt)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--apply', action='store_true')
    ap.add_argument('--strip', action='store_true', help='回退：全角换回半角')
    ap.add_argument('--file', nargs='*')
    args = ap.parse_args()

    files = [ROOT / p for p in args.file] if args.file else targets(PAGE_DIR)
    stamp = datetime.date.today().strftime('%Y%m%d')
    broot = ROOT / f'03-页面/备份/改引号前-{stamp}'

    changed = odd = 0
    for f in files:
        if not f.exists():
            print('  ⚠ 不存在', f)
            continue
        s = f.read_text(encoding='utf-8')
        new, note = process(s, args.strip)
        if note is None:
            continue
        rel = str(f.relative_to(ROOT))
        if note.startswith('✗'):
            odd += 1
            print(f'  {rel}\n      {note}')
            continue
        print(f'  {rel}\n      {note}')
        changed += 1
        if args.apply and new != s:
            backup(f, broot)
            f.write_text(new, encoding='utf-8')

    tag = '已写入' if args.apply else 'DRY-RUN'
    print(f'\n[{tag}] 涉及 {changed} 个文件；跳过 {odd} 个（奇数引号，需人工）')
    if args.apply and changed:
        print(f'备份目录：{broot}')
    else:
        print('未写入。加 --apply 执行。')
    return 1 if odd else 0


if __name__ == '__main__':
    sys.exit(main())
