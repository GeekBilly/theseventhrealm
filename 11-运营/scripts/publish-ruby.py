#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""按「CSV 对照表 → POST /pages/<id>」发布页面（按 ID 精确发布，绝不按 slug 猜）。

为什么不用 publish-by-id.py：它按 slug 查 id 取 d[0]，而 94–108（正文朝代页，parent=32）
与 345–360（藏品页变体，parent=344）**slug 同名**，按 slug 查会发错页。
本脚本吃人工确认过的 ID，发布前逐页核对 slug + parent，两个都对上才 POST。

用法：
  # 默认：行内注音对照表
  DRY=1 python3 publish-ruby.py                     # 只核对 + 备份，不 POST
  python3 publish-ruby.py --verify                  # 只做线上验收

  # 引号修正
  python3 publish-ruby.py --csv 11-运营/data/发布对照表-引号修正.csv --metric quote
  python3 publish-ruby.py --csv 11-运营/data/发布对照表-引号修正.csv --metric quote --verify

⚠️ 前台跑会被 SIGTERM（exit137，但 POST 其实已生效）→ **后台跑并落日志**：
  python3 publish-ruby.py ... > /tmp/pub.log 2>&1
"""
import argparse
import csv
import html
import json
import os
import pathlib
import re
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
SITE = 'https://theseventhrealm.com'
API = f'{SITE}/wp-json/wp/v2/pages'
CSV = ROOT / '11-运营/data/注音-发布对照表.csv'
UA = ('Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 '
      '(KHTML, like Gecko) Chrome/124.0 Safari/537.36')


def auth():
    out = subprocess.run(
        ['security', 'find-generic-password', '-a', 'MollyBot_No.2',
         '-s', 'theseventhrealm-wp', '-w'],
        capture_output=True, text=True, check=True)
    return 'MollyBot_No.2', out.stdout.strip()


def curl(url, user, pwd, data=None, method=None):
    cmd = ['curl', '-sL', '--max-time', '60', '-A', UA,
           '-u', f'{user}:{pwd}', '-H', 'Content-Type: application/json',
           '--post301', '--post302', '--post303', '-w', '\n%{http_code}', url]
    if data is not None:
        tmp = ROOT / '.tmp-payload.json'
        tmp.write_text(json.dumps(data, ensure_ascii=False), encoding='utf-8')
        cmd[1:1] = ['-X', method or 'POST']
        cmd += ['--data-binary', f'@{tmp}']
    out = subprocess.run(cmd, capture_output=True, text=True).stdout
    body, _, code = out.rpartition('\n')
    try:
        return int(code), json.loads(body)
    except Exception:
        return int(code or 0), {'message': body[:300]}


def plain(url, user, pwd):
    """抓前台页面（带 UA，防 CF 403）"""
    r = subprocess.run(['curl', '-sL', '--max-time', '60', '-A', UA,
                        '-u', f'{user}:{pwd}', '-w', '\n%{http_code}', url],
                       capture_output=True, text=True)
    body, _, code = r.stdout.rpartition('\n')
    return int(code or 0), body


def read_rows(csv_path: pathlib.Path):
    """读对照表 → [(本地文件, slug, id, parent, 期望数)]。数量列自动识别。"""
    with csv_path.open(encoding='utf-8-sig') as f:
        rd = list(csv.DictReader(f))
    cnt_col = next((c for c in rd[0] if '对数' in c or ('数' in c and '总' not in c)), None)
    out = []
    for r in rd:
        out.append((r['本地文件'], r['slug'], int(r['线上ID']), int(r.get('parent') or -1),
                    int(r[cnt_col]) if cnt_col else 0))
    return out


def measure(body: str, kind: str):
    """返回 (实测数, 备注)。正文 = 去 script/style、去标签、解 HTML 实体。"""
    raw = re.sub(r'<(script|style)\b.*?</\1>', '', body, flags=re.S | re.I)
    text = html.unescape(re.sub(r'<[^>]+>', '', raw))
    if kind == 'quote':
        L, R = text.count('\u201c'), text.count('\u201d')
        return max(L, R), ('' if L == R else f'⚠ 左右不等 左{L}/右{R}')
    # pinyin：含声调字母的括号串 → 自动排除 CSS 里的 @media(max-width:640px)
    return len(re.findall(r'[（(][A-Za-z]*[āáǎàēéěèīíǐìōóǒòūúǔùǖǘǚǜü]', text)), ''


def page_url(slug: str, parent: int) -> str:
    # 正文朝代页挂在父页 5000years 下，真实路径 /5000years/<slug>/；顶层页才是 /<slug>/
    return f'{SITE}/5000years/{slug}/' if parent == 32 else f'{SITE}/{slug}/'


def verify(plan, user, pwd, metric):
    print(f'\n== 线上验收（判据：{metric}）==')
    bad = 0
    for path, slug, pid, parent, expect in plan:
        url = page_url(slug, parent)
        st, body = plain(url, user, pwd)
        n, note = measure(body, metric)
        ok = (st == 200 and n >= expect and not note)
        bad += 0 if ok else 1
        print(f'  {"✓" if ok else "✗"} {url.replace(SITE, "")} HTTP {st}  {n}（期望 ≥{expect}） {note}')
    print('\n验收：全部通过' if not bad else f'\n验收：{bad} 页不达标')
    return 1 if bad else 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--csv', default=str(CSV), help='对照表 CSV')
    ap.add_argument('--metric', default='pinyin', choices=['pinyin', 'quote'], help='线上验收判据')
    ap.add_argument('--verify', action='store_true', help='只做线上验收，不发布')
    args = ap.parse_args()

    csv_path = pathlib.Path(args.csv)
    if not csv_path.is_absolute():
        csv_path = ROOT / csv_path
    DRY = os.environ.get('DRY') == '1'
    user, pwd = auth()
    plan_rows = read_rows(csv_path)
    stamp = csv_path.stem.replace('发布对照表-', '')
    backup_dir = ROOT / f'03-页面/备份/发布前-{args.metric}-{stamp}'

    print('== 一、发布前核对（slug + parent 必须对上）==')
    plan, bad = [], 0
    for path, slug, pid, parent, expect in plan_rows:
        fp = ROOT / path
        if not fp.exists():
            print(f'  ✗ #{pid:<4} {slug:<10} 本地缺文件 {path}')
            bad += 1
            continue
        st, d = curl(f'{API}/{pid}', user, pwd)
        if st != 200 or not isinstance(d, dict):
            print(f'  ✗ #{pid:<4} {slug:<10} GET HTTP {st} {d.get("message", "")[:80]}')
            bad += 1
            continue
        got_slug, got_parent = d.get('slug'), d.get('parent')
        ok = (got_slug == slug and got_parent == parent)
        bad += 0 if ok else 1
        print(f'  {"✓" if ok else "✗"} #{pid:<4} 期望 {slug}/{parent}  线上 {got_slug}/{got_parent}'
              f'  本地 {len(fp.read_text(encoding="utf-8"))} 字节')
        if ok:
            plan.append((path, slug, pid, parent, expect))
    if bad:
        print(f'\n{bad} 页核对不通过，已中止（未动线上）')
        return 1
    print(f'\n核对通过 {len(plan)} 页')

    if args.verify:
        return verify(plan, user, pwd, args.metric)

    print('\n== 二、备份线上原文（回滚点）==')
    backup_dir.mkdir(parents=True, exist_ok=True)
    for path, slug, pid, parent, expect in plan:
        st, d = curl(f'{API}/{pid}', user, pwd)
        out = backup_dir / f'{slug}-{pid}.html'
        out.write_text(d.get('content', {}).get('rendered', ''), encoding='utf-8')
        print(f'  ✓ {out.name}  {out.stat().st_size} 字节')
    print(f'  → {backup_dir.relative_to(ROOT)}')

    print('\n== 三、发布 ==')
    if DRY:
        print('  DRY=1：未 POST')
        return 0
    ok = fail = 0
    for path, slug, pid, parent, expect in plan:
        src = (ROOT / path).read_text(encoding='utf-8')
        st, d = curl(f'{API}/{pid}', user, pwd, {'content': src}, 'POST')
        if st == 200 and d.get('id') == pid:
            print(f'  ✓ #{pid:<4} {slug:<10} 已更新 → {d.get("link")}')
            ok += 1
        else:
            print(f'  ✗ #{pid:<4} {slug:<10} HTTP {st} {d.get("message") or d.get("code")}')
            fail += 1
    print(f'\n成功 {ok} / 失败 {fail}')
    (ROOT / '.tmp-payload.json').unlink(missing_ok=True)
    if fail:
        return 1
    return verify(plan, user, pwd, args.metric)


if __name__ == '__main__':
    sys.exit(main())
