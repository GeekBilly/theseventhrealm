#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""indexnow-push.py —— 把站点 URL 主动推给 Bing / Yandex / Seznam / Naver

用法
    python3 11-运营/scripts/indexnow-push.py            # 自检 + 推送尚未提交过的 URL
    python3 11-运营/scripts/indexnow-push.py --dry      # 只列清单，不真推
    python3 11-运营/scripts/indexnow-push.py --all      # 忽略去重，全量重推
    python3 11-运营/scripts/indexnow-push.py --limit N  # 本次最多推 N 条

为什么需要它（2026-10-01 实测确立）
    Google 侧我们不能主动提交（Search Console 需登录 google.com → 触 R-20 跨境信道），
    只能靠 robots.txt 里已声明的 sitemap 被动发现。而 IndexNow 是一条**零账号**的通道：
    不需要注册、不需要登录任何站长后台、不提交任何身份信息，一次 POST 即可通知
    **Bing / Yandex / Seznam / Naver**（Bing 还给 DuckDuckGo 供索引）。
    合规判断见 11-运营/REQ-2026-10-01-01 第二节。

关键事实（别踩）
    * key 文件必须放在**站点根目录** public_html/{key}.txt，且内容严格等于 key。
      放在 wp-content/uploads/ 下提交也可能返回 200（「已接收」），但搜索引擎回抓
      校验会失败 → **静默无效**。故本脚本运行前必须做 §0 自检，不满足直接退出。
    * IndexNow 只负责「来爬」，不保证收录；内容过于单薄的页推了也不会被索引。
    * 单次上限 10000 URL，本站规模远未触及。
"""

import argparse
import csv
import json
import subprocess
import sys
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
KEY_FILE = ROOT / '03-页面' / '站点文件' / 'indexnow-key.txt'
PUSHED_FILE = ROOT / '11-运营' / 'data' / 'indexnow-pushed.txt'
LOG_CSV = ROOT / '11-运营' / 'data' / 'indexnow-push.csv'
SITEMAP_INDEX = 'https://theseventhrealm.com/wp-sitemap.xml'
ENDPOINT = 'https://api.indexnow.org/indexnow'
HOST = 'theseventhrealm.com'
NS = '{http://www.sitemaps.org/schemas/sitemap/0.9}'


def die(msg):
    print(f'❌ {msg}')
    sys.exit(1)


def read_key():
    if not KEY_FILE.exists():
        die(f'找不到 key 文件 {KEY_FILE}')
    key = KEY_FILE.read_text(encoding='utf-8').strip()
    if len(key) != 32:
        die(f'key 应为 32 位十六进制，实际 {len(key)} 位')
    return key


# ⚠️ 必须伪装浏览器 UA。2026-10-04 站点加固后，CF 会拦截 curl/python 的默认 UA：
#    首页与 txt 文件均返回 403（"Sorry, you have been blocked"），换成浏览器 UA 立刻 200/404 正常。
#    不带 UA 的请求拿到的不是站点内容，而是 CF 的错误页——会让人误判成「页面坏了」。
UA = ('Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 '
      '(KHTML, like Gecko) Chrome/126.0 Safari/537.36')


def curl(url, timeout=30, extra=None):
    """统一用 curl 取数，并强制带浏览器 UA。

    为什么不用 urllib：CF 会拦截 python-urllib 的默认 UA（实测直接抛 HTTPError）。
    """
    cmd = ['curl', '-sL', '--max-time', str(timeout), '-A', UA, url]
    if extra:
        cmd[2:2] = extra
    try:
        return subprocess.run(cmd, capture_output=True, timeout=timeout + 10)
    except Exception as e:
        raise RuntimeError(f'curl 失败：{e}')


def step0_verify_key(key):
    """提交前的硬自检：根目录下的 key 文件必须公开可达，且内容严格等于 key。"""
    url = f'https://{HOST}/{key}.txt'
    try:
        r = curl(url, extra=['-w', '\n%{http_code}'])
    except Exception as e:
        die(f'key 文件不可达（{url}）：{e}\n'
            f'  → 是否已用 cPanel 上传到 public_html 根目录？见 REQ-2026-10-01-01 §三')
    text = r.stdout.decode('utf-8', 'ignore')
    lines = text.rstrip('\n').split('\n')
    code = lines[-1].strip()
    body = '\n'.join(lines[:-1]).strip()
    if code != '200':
        die(f'key 文件返回 HTTP {code}，应为 200（URL：{url}）')
    if body != key:
        die(f'key 文件内容不匹配：线上 {body[:20]}… vs 本地 {key[:20]}…')
    print(f'✅ key 自检通过：{url}')


def fetch_urls():
    """从线上 sitemap 索引展开，取其中所有 URL（按出现顺序）。"""
    r = curl(SITEMAP_INDEX)
    root = ET.fromstring(r.stdout)
    subs = [loc.text for loc in root.iter(f'{NS}loc')]
    urls = []
    for sub in subs:
        if not (sub.startswith(f'https://{HOST}/wp-sitemap-posts-')):
            continue
        if not ('-post-' in sub or '-page-' in sub):
            continue
        r = curl(sub)
        try:
            rr = ET.fromstring(r.stdout)
        except Exception as e:
            print(f'  ⚠️ 跳过子图 {sub}（解析失败：{e}）')
            continue
        for tag in rr.iter(f'{NS}loc'):
            u = (tag.text or '').strip()
            if u.startswith(f'https://{HOST}/'):
                urls.append(u)
    # 去重保序
    seen, out = set(), []
    for u in urls:
        if u not in seen:
            seen.add(u)
            out.append(u)
    return out


def load_pushed():
    if not PUSHED_FILE.exists():
        return set()
    return {l.strip() for l in PUSHED_FILE.read_text(encoding='utf-8').splitlines() if l.strip()}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--dry', action='store_true', help='只列清单不真推')
    ap.add_argument('--all', action='store_true', help='忽略去重，全量重推')
    ap.add_argument('--limit', type=int, default=0, help='本次最多推 N 条（0=不限）')
    ap.add_argument('--skip-verify', action='store_true', help='跳过 key 自检（仅供本地调试）')
    a = ap.parse_args()

    key = read_key()
    if not a.skip_verify:
        step0_verify_key(key)
    else:
        print('⚠️ 已跳过 key 自检')

    urls = fetch_urls()
    print(f'站点共发现 {len(urls)} 个 URL')
    if a.all:
        todo = urls
    else:
        pushed = load_pushed()
        todo = [u for u in urls if u not in pushed]
    if a.limit:
        todo = todo[:a.limit]

    print(f'本次待推 {len(todo)} 条' + ('（--dry，不真推）' if a.dry else ''))
    for u in todo:
        print('  ·', u)
    if not todo:
        print('没有新的 URL 需要推送。')
        return
    if a.dry:
        return

    payload = json.dumps({
        'host': HOST,
        'key': key,
        'keyLocation': f'https://{HOST}/{key}.txt',
        'urlList': todo,
    }).encode('utf-8')
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    # body 从 stdin 喂给 curl（--data-binary @-），避免命令行转义与长度问题
    try:
        r = subprocess.run(
            ['curl', '-s', '-X', 'POST', ENDPOINT, '--max-time', '40',
             '-H', 'Content-Type: application/json; charset=utf-8',
             '-w', '\n%{http_code}', '--data-binary', '@-'],
            input=payload, capture_output=True, timeout=60)
        text = r.stdout.decode('utf-8', 'ignore')
        lines = text.rstrip('\n').split('\n')
        code = int(lines[-1].strip() or 0)
        body = '\n'.join(lines[:-1]).strip()
    except Exception as e:
        print(f'❌ 请求失败：{e}')
        LOG_CSV.parent.mkdir(parents=True, exist_ok=True)
        with LOG_CSV.open('a', newline='', encoding='utf-8') as f:
            csv.writer(f).writerow([now, len(todo), '000', f'ERROR {e}'])
        return

    print(f'返回 HTTP {code} · {body[:200] or "(空响应)"}')
    # IndexNow 成功返回 200（有时 202），且 body 为空或不含 error
    ok = code in (200, 202) and 'error' not in body.lower()
    if ok:
        PUSHED_FILE.parent.mkdir(parents=True, exist_ok=True)
        with PUSHED_FILE.open('a', encoding='utf-8') as f:
            for u in todo:
                f.write(u + '\n')
        print(f'✅ 已推送 {len(todo)} 条（去重文件已更新）')
    else:
        print('⚠️ 未视为成功，去重文件未更新（不会重复扣费，可重试）')

    LOG_CSV.parent.mkdir(parents=True, exist_ok=True)
    new = LOG_CSV.exists() and LOG_CSV.stat().st_size == 0
    with LOG_CSV.open('a', newline='', encoding='utf-8') as f:
        w = csv.writer(f)
        if new:
            w.writerow(['时间', '条数', 'HTTP', '响应'])
        w.writerow([now, len(todo), code, body[:200]])


if __name__ == '__main__':
    main()
