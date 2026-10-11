#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""upload-media.py —— 成品/多媒体直传站点媒体库（不用打包压缩）

用法
    python3 11-运营/scripts/upload-media.py <文件或目录>...    # 传指定文件（目录则递归）
    python3 11-运营/scripts/upload-media.py --scan             # 扫成品目录，只传没传过的
    python3 11-运营/scripts/upload-media.py --dir <目录>       # 传任意目录（如历史样张）
    python3 11-运营/scripts/upload-media.py --scan --dry       # 只列清单，不真传
    python3 11-运营/scripts/upload-media.py --scan --force     # 忽略台账，全部重传

关键事实（2026-09-30 实测，别再踩）
    * 必须用 multipart（-F）。raw binary（--data-binary）在 >1MB 时会被源站挡回
      413 Payload Too Large，看起来像"体积上限"，其实是编码方式的问题；
      multipart 实测 6.9MB 的 zip 也能 201 成功。
    * 幂等靠 sha256 台账 11-运营/data/uploaded-media.csv，重复跑不会重复传。
    * 宽或高 >2560 的图，WP 会另生成 -scaled 版本且 source_url 指向它；
      本脚本检测到 original_image 会把 URL 指回原图，保证下载到的是原始分辨率。
    * 上传后做一次 HEAD 校验，content-length 与本地不一致就报警。
"""

import argparse
import csv
import hashlib
import json
import mimetypes
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
AUTH = ROOT / '11-运营' / 'wp-auth.sh'
LEDGER = ROOT / '11-运营' / 'data' / 'uploaded-media.csv'

# --scan 默认扫这些目录（成品与交付包）。
# 历史样张（02-商品/05-承接站/样张）有 80+ 张各版本，不在默认范围内，用 --dir 单独指定。
SCAN_DIRS = [
    '02-商品/03-字形线/成品',
    '02-商品/04-金句线/成品',
    '02-商品/04-金句线/交付包',
]
ALLOW_EXT = {'.png', '.jpg', '.jpeg', '.webp', '.gif', '.zip', '.pdf', '.mp3', '.mp4'}
SKIP_SUFFIX = ('-mac.html', '.html', '.css', '.md')   # 样张目录里混着 html 源文件，跳过

# ⚠️ 2026-10-08：站点 WAF 规则 03 会 block `curl/` 与 `python-requests` 等脚本 UA，
#    导致 WP REST 返回 HTML（403）而不是 JSON。所有 curl 调用必须带浏览器 UA。
UA = ('Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) '
      'AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
CURL_UA = ['-A', UA]


def load_auth():
    out = subprocess.run(
        ['bash', '-c', f'source "{AUTH}" && printf "%s\\t%s\\t%s" "$SITE" "$WP_USER" "$WP_APP_PASS"'],
        capture_output=True, text=True)
    if out.returncode != 0 or out.stdout.count('\t') != 2:
        sys.exit('凭据装载失败，检查 11-运营/wp-auth.sh 与钥匙串服务 theseventhrealm-wp')
    site, user, pw = out.stdout.strip().split('\t')
    return site.rstrip('/'), user, pw


def now():
    import datetime
    return datetime.datetime.now().strftime('%F %T')


def sha256(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


def load_ledger():
    rows, by_hash = [], {}
    if LEDGER.exists():
        with open(LEDGER, encoding='utf-8', newline='') as f:
            for r in csv.DictReader(f):
                rows.append(r)
                by_hash[r['sha256']] = r
    return rows, by_hash


def save_ledger(rows):
    LEDGER.parent.mkdir(parents=True, exist_ok=True)
    cols = ['time', 'sha256', 'local_path', 'bytes', 'remote_name', 'url', 'media_id', 'scaled']
    with open(LEDGER, 'w', encoding='utf-8', newline='') as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        for r in rows:
            w.writerow({c: r.get(c, '') for c in cols})


def mime_of(path):
    m = mimetypes.guess_type(str(path))[0]
    return m or 'application/octet-stream'


IMAGE_EXT = {'.png', '.jpg', '.jpeg', '.webp', '.gif'}


def find_existing(site, user, pw, name, size):
    """查媒体库是否已有同一份文件（避免 WP 自动改名成 xxx-1.png 留下一堆副本）。
    匹配规则：
      图片 —— 按文件名（含去掉 -scaled、以及 original_image 的原图名）；
              注意 media_details.filesize 记的是**缩放后**的大小，不能拿来对图片比对。
      其余（zip/pdf/音视频，不会被 WP 缩放）—— 先按文件名，再按字节数兜底，
              这样交付包改名上传过也能认出来。
    命中返回 (id, 可用URL)，否则 None。"""
    import urllib.parse
    out = subprocess.run(['curl', '-s', *CURL_UA, '-u', f'{user}:{pw}',
                          f'{site}/wp-json/wp/v2/media?per_page=100'
                          f'&_fields=id,source_url,media_details'],
                         capture_output=True, text=True)
    try:
        items = json.loads(out.stdout)
    except json.JSONDecodeError:
        return None
    if not isinstance(items, list):
        return None

    is_image = Path(name).suffix.lower() in IMAGE_EXT
    for it in items:
        url = it.get('source_url', '')
        det = it.get('media_details', {}) or {}
        orig = det.get('original_image')
        base = url.rsplit('/', 1)[-1]
        if base == name or orig == name or base.replace('-scaled', '') == name:
            return it['id'], (url.rsplit('/', 1)[0] + '/' + orig if orig else url)
    if not is_image:
        for it in items:
            if (it.get('media_details') or {}).get('filesize') == size:
                return it['id'], it.get('source_url', '')
    return None


def upload(site, user, pw, path):
    """用 multipart 上传单个文件，返回 (media_id, url, scaled_bool)；失败返回 (None, err, False)。"""
    cmd = ['curl', '-s', *CURL_UA, '-u', f'{user}:{pw}', '-X', 'POST',
           '-F', f'file=@{path};filename={path.name};type={mime_of(path)}',
           f'{site}/wp-json/wp/v2/media']
    out = subprocess.run(cmd, capture_output=True, text=True)
    if not out.stdout.strip():
        return None, f'curl 无返回（stderr: {out.stderr.strip()[:120]}）', False
    try:
        d = json.loads(out.stdout)
    except json.JSONDecodeError:
        # 413 之类的响应不是 JSON
        return None, f'非 JSON 响应：{out.stdout.strip()[:120]}', False
    if 'id' not in d:
        return None, d.get('message', json.dumps(d, ensure_ascii=False)[:120]), False

    url = d.get('source_url', '')
    det = d.get('media_details', {}) or {}
    scaled = False
    if det.get('original_image'):
        # WP 对 >2560px 的图生成了 -scaled，source_url 指向它；改指回原图
        scaled = True
        url = url.rsplit('/', 1)[0] + '/' + det['original_image']
    return d['id'], url, scaled


def verify(url, local_path):
    """回读远端文件比对字节数。返回 (ok, 远端大小)。
    用 GET 丢弃响应体取 size_download —— HEAD 经 CF 时 %{content_length} 会拿到 -1，不可靠。"""
    out = subprocess.run(['curl', '-sL', *CURL_UA, '-o', '/dev/null', '-w', '%{http_code} %{size_download}', url],
                         capture_output=True, text=True)
    try:
        code, size = out.stdout.split()
        size = int(size)
    except ValueError:
        return False, -1
    if code != '200':
        return False, size
    return size == os.path.getsize(local_path), size


def collect(paths, scan, dirs=()):
    files = []
    if scan:
        for d in SCAN_DIRS:
            base = ROOT / d
            if base.exists():
                files += [p for p in base.rglob('*') if p.is_file()]
    for p in list(paths) + list(dirs):
        q = Path(p)
        if not q.is_absolute():
            q = ROOT / p
        if q.is_dir():
            files += [x for x in q.rglob('*') if x.is_file()]
        elif q.is_file():
            files.append(q)
    seen, out = set(), []
    for f in files:
        if f.suffix.lower() not in ALLOW_EXT:
            continue
        if f.name.endswith(SKIP_SUFFIX):
            continue
        if f.resolve() in seen:
            continue
        seen.add(f.resolve())
        out.append(f)
    return sorted(out)


def main():
    ap = argparse.ArgumentParser(description='成品/多媒体直传站点媒体库')
    ap.add_argument('paths', nargs='*', help='文件或目录（相对工作区根）')
    ap.add_argument('--scan', action='store_true', help='扫描成品目录')
    ap.add_argument('--dir', action='append', default=[], help='额外目录，可多次指定')
    ap.add_argument('--dry', action='store_true', help='只列清单不上传')
    ap.add_argument('--force', action='store_true', help='忽略台账，全部重传')
    args = ap.parse_args()

    if not args.scan and not args.paths and not args.dir:
        ap.print_help()
        sys.exit(1)

    files = collect(args.paths, args.scan, args.dir)
    if not files:
        print('没有符合条件的文件（检查扩展名白名单：' + ' '.join(sorted(ALLOW_EXT)) + '）')
        return

    rows, by_hash = load_ledger()
    todo, skip = [], []
    for f in files:
        h = sha256(f)
        if (not args.force) and h in by_hash:
            skip.append((f, by_hash[h]['url']))
        else:
            todo.append((f, h))

    print(f'候选 {len(files)} 个：待传 {len(todo)}，已在台账 {len(skip)}')
    for f, url in skip:
        print(f'  · 跳过 {f.relative_to(ROOT)}  →  {url}')
    if args.dry or not todo:
        if args.dry:
            for f, _ in todo:
                print(f'  + 待传 {f.relative_to(ROOT)}  {os.path.getsize(f)/1024:.0f} KB')
        return

    site, user, pw = load_auth()
    ok = fail = 0
    for f, h in todo:
        rel = f.relative_to(ROOT)
        size = os.path.getsize(f)

        # 媒体库已有同名附件就复用，避免 WP 改名成 xxx-1.png 留下一堆副本
        hit = None if args.force else find_existing(site, user, pw, f.name, size)
        if hit:
            mid, url = hit
            good, remote = verify(url, f)
            print(f'  = 复用 {rel}  id={mid} ' + ('OK' if good else f'⚠ 远端 {remote} ≠ 本地 {size}'))
            print(f'      {url}')
            rows.append({'time': now(), 'sha256': h, 'local_path': str(rel), 'bytes': size,
                         'remote_name': f.name, 'url': url, 'media_id': mid, 'scaled': 'reused'})
            ok += 1
            continue

        print(f'  ↑ 上传 {rel}  {size/1024:.0f} KB …', end=' ', flush=True)
        mid, url, scaled = upload(site, user, pw, f)
        if mid is None:
            print(f'失败：{url}')
            fail += 1
            continue
        good, remote = verify(url, f)
        flag = 'OK' if good else f'⚠ 远端 {remote} ≠ 本地 {size}'
        print(f'id={mid} {flag}')
        print(f'      {url}' + ('   （WP 生成了 -scaled，已指回原图）' if scaled else ''))
        rows.append({'time': now(),
                     'sha256': h, 'local_path': str(rel), 'bytes': size,
                     'remote_name': f.name, 'url': url, 'media_id': mid,
                     'scaled': 'yes' if scaled else ''})
        ok += 1

    save_ledger(rows)
    print(f'\n完成：成功 {ok}，失败 {fail}；台账 {LEDGER.relative_to(ROOT)}')


if __name__ == '__main__':
    main()
