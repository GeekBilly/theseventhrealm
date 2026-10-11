#!/usr/bin/env python3
"""按「slug 查 id → POST /pages/<id>」发布页面。

为什么不用 publish.sh：那个脚本用 sed 从 JSON 里抠 id（贪婪匹配取到最后一个 "id":），
实测在朝代页上会拿到错误 id（131/132/133，真实是 94–109）→ rest_post_invalid_id 且**静默失败**。
本脚本用 json 解析，取 d[0]['id']，并在发布后校验返回 id 一致。

用法：
  python3 11-运营/scripts/publish-by-id.py 03-页面/朝代页            # 目录内 *.html，文件名即 slug
  python3 11-运营/scripts/publish-by-id.py 03-页面/home-with-collection.html --id 13
  DRY=1 python3 11-运营/scripts/publish-by-id.py ...                   # 只体检不发布
"""
import json
import os
import pathlib
import subprocess
import sys
import urllib.request
import urllib.error

ROOT = pathlib.Path(__file__).resolve().parents[2]
SITE = 'https://theseventhrealm.com'
API = f'{SITE}/wp-json/wp/v2/pages'


def auth():
    """从钥匙串取应用密码（与 11-运营/wp-auth.sh 同源）。"""
    out = subprocess.run(
        ['security', 'find-generic-password', '-a', 'MollyBot_No.2',
         '-s', 'theseventhrealm-wp', '-w'],
        capture_output=True, text=True, check=True)
    return 'MollyBot_No.2', out.stdout.strip()


def req(url, user, pwd, data=None, method=None):
    """一律走 curl：Cloudflare 会拦 python-urllib 的默认 UA，且 Basic 头在重定向时易丢。"""
    cmd = ['curl', '-sL', '--max-time', '60', '-u', f'{user}:{pwd}',
           '-H', 'Content-Type: application/json',
           '--post301', '--post302', '--post303',
           '-w', '\n%{http_code}', url]
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
        return int(code or 0), {'message': body[:200]}


def find_id(slug, user, pwd):
    st, d = req(f'{API}?slug={slug}&status=any&per_page=1', user, pwd)
    if st != 200 or not isinstance(d, list) or not d:
        return None
    return d[0]['id']


def main():
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    forced = None
    for i, a in enumerate(sys.argv):
        if a == '--id' and i + 1 < len(sys.argv):
            forced = int(sys.argv[i + 1])
    dry = os.environ.get('DRY') == '1'
    user, pwd = auth()

    targets = []
    for a in args:
        p = ROOT / a
        if p.is_dir():
            targets += [(f.stem, f) for f in sorted(p.glob('*.html'))]
        elif p.exists():
            targets.append((p.stem.replace('-with-collection', ''), p))
    if not targets:
        print('没有目标文件'); return 1

    ok = fail = 0
    for slug, path in targets:
        html = path.read_text(encoding='utf-8')
        pid = forced if (len(targets) == 1 and forced) else find_id(slug, user, pwd)
        if not pid:
            print(f'  ✗ {slug:<10} 查不到 id，跳过'); fail += 1; continue
        if dry:
            print(f'  ✓ {slug:<10} id={pid:<5} {len(html)} 字节（DRY，未发）'); ok += 1; continue
        st, d = req(f'{API}/{pid}', user, pwd, {'content': html}, 'POST')
        if st == 200 and d.get('id') == pid:
            print(f'  ✓ {slug:<10} id={pid:<5} 已更新 → {d.get("link")}'); ok += 1
        else:
            msg = d.get('message') or d.get('code') or str(d)[:120]
            print(f'  ✗ {slug:<10} id={pid:<5} HTTP {st} {msg}'); fail += 1
    print(f'\n成功 {ok} / 失败 {fail}')
    return 1 if fail else 0


if __name__ == '__main__':
    sys.exit(main())
