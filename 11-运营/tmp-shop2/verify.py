#!/usr/bin/env python3
"""阶段二/三交付自检（改后版本）：逐页拉线上 raw，核对口径。

用法：python3 -u 11-运营/tmp-shop2/verify.py
"""

import importlib.util
import json
import pathlib
import re
import subprocess
import sys

ROOT = pathlib.Path('/Users/billyhou/WorkBuddy/2026-09-25-15-56-17')
RAW = ROOT / '11-运营/tmp-shop2/raw'
OUT = ROOT / '11-运营/tmp-shop2/verify'
SITE = 'https://theseventhrealm.com'

CHILDREN = [(345, 'sanhuang'), (346, 'xia'), (347, 'shang'), (348, 'zhou'),
            (349, 'qin'), (350, 'han'), (351, 'sanguo'), (352, 'jin'),
            (353, 'sui'), (354, 'tang'), (355, 'wudai'), (356, 'song'),
            (357, 'yuan'), (358, 'ming'), (359, 'qing'), (360, 'juexing')]
DYNASTY = [(94, 'sanhuang'), (95, 'xia'), (96, 'shang'), (97, 'zhou'),
           (98, 'qin'), (99, 'han'), (100, 'sanguo'), (101, 'jin'),
           (102, 'sui'), (103, 'tang'), (104, 'wudai'), (105, 'song'),
           (106, 'yuan'), (107, 'ming'), (108, 'qing'), (109, 'juexing')]
PRICE = '预告价：单朝 ¥12 ｜ 商周套装 ¥19 ｜ 首发有折扣'


def creds():
    out = subprocess.run(['bash', '-c',
                          '. "{}/11-运营/wp-auth.sh" >/dev/null 2>&1; echo "$WP_USER"; echo "$WP_APP_PASS"'.format(ROOT)],
                         capture_output=True, text=True, check=True).stdout.strip().splitlines()
    return out[0], out[1]


def fetch_raw(pid, user, pwd):
    OUT.mkdir(parents=True, exist_ok=True)
    dst = OUT / 'p{}.json'.format(pid)
    for n in range(5):
        if dst.exists():
            dst.unlink()          # ⚠️ curl -o 在连接失败时**不覆盖**旧文件，会读到上一次的陈旧结果
        code = subprocess.run(
            ['curl', '-s', '--noproxy', '*', '-u', '{}:{}'.format(user, pwd), '-m', '150',
             '{}/wp-json/wp/v2/pages/{}?context=edit'.format(SITE, pid), '-o', str(dst),
             '-w', '%{http_code}'], capture_output=True, text=True).stdout.strip()
        if code != '200' or not dst.exists():
            print('   retry pid={} http={}'.format(pid, code), flush=True)
            continue
        try:
            d = json.loads(dst.read_text(encoding='utf-8'))
            if 'content' in d and d['content'].get('raw') is not None:
                return d
        except Exception:
            pass
        print('   retry pid={} (JSON 解析失败) http={}'.format(pid, code), flush=True)
    return None


def text_of(html):
    t = re.sub(r'<style.*?</style>', '', html, flags=re.S)
    t = re.sub(r'<script.*?</script>', '', t, flags=re.S)
    return re.sub(r'<[^>]+>', '', t)


def style_ok(raw):
    m = re.search(r'<style>(.*?)</style>', raw, re.S)
    if not m:
        return False, False
    css = m.group(1)
    return ('\n\n' not in css), ('<p>' not in css and '</p>' not in css)


def balance(html):
    return {k: (len(re.findall('<{}'.format(k), html)), len(re.findall('</{}>'.format(k), html)))
            for k in ('section', 'div', 'ul', 'li', 'p', 'h2')}


def main():
    user, pwd = creds()
    spec = importlib.util.spec_from_file_location('bds', ROOT / '11-运营/scripts/build-dynasty-shop.py')
    bds = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(bds)
    H1 = {e['slug']: e['h1'] for e in bds.load_eras()}

    print('========== 阶段二：17 个新页 ==========', flush=True)
    pages = [(344, 'dynasty', '藏品 · 朝代', 'collection-dynasty')] + \
            [(i, s, '{} · 壁纸与藏品'.format(H1[s]), 'collection-dynasty-' + s) for i, s in CHILDREN]
    fails = []
    for pid, slug, title, fname in pages:
        d = fetch_raw(pid, user, pwd)
        if not d:
            print('❌ 拉不到', pid, slug, flush=True)
            fails.append((pid, '拉取失败'))
            continue
        raw = d['content']['raw']
        local = (ROOT / '03-页面/{}.html'.format(fname)).read_text(encoding='utf-8')
        txt = text_of(raw)
        no_blank, no_ptag = style_ok(raw)
        checks = {
            '内容与本地一致': raw.strip() == local.strip(),
            '标题对': d['title']['raw'] == title,
            'slug 对': d['slug'] == slug,
            '外层面板在': 'class="sr-collection"' in raw,
            '样式块无空行': no_blank,
            '样式块无 p': no_ptag,
            'HTML注释0': len(re.findall(r'<!--', raw)) == 0,
            '直引号0': ('"' not in txt and "'" not in txt),
            '无卖字': '卖' not in txt,
            '价格文案': (PRICE in txt) if slug != 'dynasty' else True,
            '无购买链接': ('立即购买' not in raw and '面包多' not in raw),
            '标签配平': all(v[0] - v[1] == 0 for k, v in balance(raw).items() if k in ('div', 'ul', 'li')),
        }
        bad = [k for k, v in checks.items() if not v]
        print('{:>4} {:<10} {:<20} {} [mod {}]'.format(pid, slug, title, '✅' if not bad else '❌ ' + ','.join(bad), d.get('modified')), flush=True)
        if bad:
            fails.append((pid, ','.join(bad)))

    print('\n========== 阶段三：16 个朝代页 ==========', flush=True)
    for pid, slug in DYNASTY:
        d = fetch_raw(pid, user, pwd)
        if not d:
            print('❌ 拉不到', pid, slug, flush=True)
            fails.append((pid, '拉取失败'))
            continue
        raw = d['content']['raw']
        bak = list((ROOT / '11-运营/风险管控/站点改动备份-20261002').glob('page-{}-*-加相关藏品前.raw.html'.format(pid)))[0]
        old = bak.read_text(encoding='utf-8')
        m = re.search(r'<style>.*?</style>\n<div class="sr-collection">\n<h2>相关藏品</h2>.*?</div>\n', raw, re.S)
        restored = raw[:m.start()] + raw[m.end():] if m else None
        txt = text_of(raw)
        no_blank, no_ptag = style_ok(raw)
        b_new, b_old = balance(raw), balance(old)
        checks = {
            '含相关藏品': '<h2>相关藏品</h2>' in raw,
            '价格文案': PRICE in txt,
            '本朝入口': 'href="/collection/dynasty/{}/"'.format(slug) in raw,
            '全套入口': raw.count('/collection/dynasty/"') >= 1,
            '入口共2条': len(re.findall(r'<a class="cta"', raw.split('相关藏品')[1])) == 2,
            '样式块无空行': no_blank,
            '样式块无 p': no_ptag,
            'HTML注释0': len(re.findall(r'<!--', raw)) == 0,
            '直引号0': ('"' not in txt and "'" not in txt),
            '原文首尾逐字未动': restored is not None and restored.strip() == old.strip(),
            '标签配平': all(v[0] - v[1] == b_old[k][0] - b_old[k][1] for k, v in b_new.items()),
            '原有外层在': ('class="prose"' in raw and 'era-nav' in raw and 'fineprint' in raw
                        and 'class="relic' in raw),
        }
        bad = [k for k, v in checks.items() if not v]
        print('{:>4} {:<10} {} [mod {}]'.format(pid, slug, '✅' if not bad else '❌ ' + ','.join(bad), d.get('modified')), flush=True)
        if bad:
            fails.append((pid, ','.join(bad)))
            if not checks['原文首尾逐字未动'] and restored is not None:
                print('     新={} 旧={}'.format(len(restored), len(old)), flush=True)
                for i, (a, b) in enumerate(zip(restored, old)):
                    if a != b:
                        print('     @{}: 新={!r} 旧={!r}'.format(i, restored[i - 40:i + 40], old[i - 40:i + 40]), flush=True)
                        break

    print('\n===== 结论 =====', flush=True)
    if fails:
        print('❌ 问题页：', fails, flush=True)
    else:
        print('✅ 33 页全部通过', flush=True)
    return 1 if fails else 0


if __name__ == '__main__':
    sys.exit(main())
