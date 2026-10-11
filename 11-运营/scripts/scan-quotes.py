#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""全站引号方向体检（只读，不动线上任何东西）。

判据：正文里左引号 “ 与右引号 ” 应当接近 1:1。某一侧远多于另一侧 = 开合方向被转错了。
根因见 11-运营/reports/引号写法问题-诊断-2026-10-07.md：
WordPress 的 wptexturize 按「前面是不是空白」判断开合，中文里引号前紧跟汉字 → 全判成闭合。

用法：
  python3 11-运营/scripts/scan-quotes.py              # 从线上 sitemap 取全站 URL 体检
  python3 11-运营/scripts/scan-quotes.py --local       # 体检本地 03-页面 源码（不联网）
  python3 11-运营/scripts/scan-quotes.py --file a.html b.html

退出码：有错向则 1（方便挂进自动化）。
"""
import argparse
import concurrent.futures as cf
import html
import pathlib
import re
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
SITE = 'https://theseventhrealm.com'
UA = 'Mozilla/5.0 (Macintosh) AppleWebKit/537.36 Chrome/124.0 Safari/537.36'


def strip_tags(raw: str) -> str:
    """去掉 script/style/标签，解实体 → 纯正文字符串"""
    raw = re.sub(r'<(script|style)\b.*?</\1>', '', raw, flags=re.S | re.I)
    m = re.search(r'<(main|article)\b.*?</\1>', raw, flags=re.S | re.I)
    body = m.group(0) if m else raw
    return html.unescape(re.sub(r'<[^>]+>', '\x00', body))


def count(text: str):
    L, R = text.count('“'), text.count('”')
    return L, R, abs(R - L)


def sample_of(text: str, width: int = 18) -> str:
    mm = list(re.finditer('[“”]', text))
    if not mm:
        return ''
    i = mm[0].start()
    return text[max(0, i - 14):i + width].replace('\n', ' ').replace('\x00', ' ')


def fetch(url: str):
    r = subprocess.run(['curl', '-sL', '--max-time', '45', '-A', UA,
                        '-w', '\n%{http_code}', url], capture_output=True, text=True)
    body, _, code = r.stdout.rpartition('\n')
    return body, code.strip()


def site_urls() -> list:
    xml, code = fetch(f'{SITE}/wp-sitemap-posts-page-1.xml')
    if code != '200':
        sys.exit(f'✗ sitemap 取不到（HTTP {code}）')
    return re.findall(r'<loc>(https://[^<]+)</loc>', xml)


def run(pairs: list, local=False) -> int:
    """pairs: [(名字, 正文串, 备注)] → 返回错向总数

    ⚠️ 本地模式必须额外看半角 `"`：**那是病因本身**。本地源码是 ASCII 直引号，
    要等线上 wptexturize 转完才会变成清一色右引号，所以本地只看左右引号数永远等于 0，
    什么都发现不了——得盯那个还没变异的字符。
    """
    total = 0
    head = f'{"半角\'":>6}' if local else ''
    print(f'{head}{"左“":>5}{"右”":>5}{"错向":>6}  对象　样例')
    for name, text, note in pairs:
        if text is None:
            print(f'{"—":>6}{"—":>5}{"—":>5}{"—":>6}  {name}　{note}')
            continue
        L, R, wrong = count(text)
        total += wrong
        n_ascii = text.count('"')
        flag = '—' if not max(L, R) else ('❌' if wrong else '✅')
        cell = f'{n_ascii:>6}' if local else ''
        if local and n_ascii:
            flag = '⚠ 源码含半角'
        print(f'{cell}{L:>5}{R:>5}{wrong:>6}  {flag} {name}　{sample_of(text) if max(L,R) else note}')
    print(f'\n合计错向 {total} 处')
    return total


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--local', action='store_true', help='体检本地 03-页面 源码')
    ap.add_argument('--file', nargs='*', help='指定本地文件')
    args = ap.parse_args()

    if args.file:
        pairs = []
        for f in args.file:
            p = pathlib.Path(f)
            if not p.exists():
                p = ROOT / f
            pairs.append((str(p.relative_to(ROOT)) if p.is_relative_to(ROOT) else str(p),
                          strip_tags(p.read_text(encoding='utf-8')), ''))
        return 1 if run(pairs, local=True) else 0

    if args.local:
        pairs = []
        for f in sorted((ROOT / '03-页面').rglob('*.html')):
            if '备份' in str(f) or '校样归档' in str(f):
                continue
            text = strip_tags(f.read_text(encoding='utf-8'))
            if re.search('[“”"\u300c]', text):
                pairs.append((str(f.relative_to(ROOT)), text, ''))
        return 1 if run(pairs, local=True) else 0

    urls = site_urls()

    def one(u):
        body, code = fetch(u)
        if code != '200':
            return (u.replace(SITE, '') or '/', None, f'HTTP {code}')
        return (u.replace(SITE, '') or '/', strip_tags(body), '')

    with cf.ThreadPoolExecutor(8) as ex:
        pairs = list(ex.map(one, urls))
    return 1 if run(pairs, local=True) else 0


if __name__ == '__main__':
    sys.exit(main())
