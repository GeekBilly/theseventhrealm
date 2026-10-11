#!/usr/bin/env python3
"""阶段三：给 16 个朝代页正文末尾生成「相关藏品」区块（只生成文件，不发布）。

用法：
    python3 11-运营/scripts/insert-related-collection.py

做三件事：
  ① 原文备份 → 11-运营/风险管控/站点改动备份-20261002/page-<id>-<名>-加相关藏品前.raw.html
  ② 生成发布 body → 11-运营/tmp-shop2/stage3/p<id>.body.json（{"content": "..."}）
  ③ 生成改后全文 → 11-运营/tmp-shop2/stage3/p<id>.after.html（供复核/配平检查）

锚点：正文最后一个 <h2> 区块之后、页尾 <p class="fineprint"> 之前
      —— 具体落在页面尾部的 <section>（含 div.era-nav）之前，即正文正文正文的末尾。
      这些页面**没有** <div class="fine">（只有 p.fineprint），按任务书「找不到 fine 就插在正文末尾」处理。
样式：与阶段二 17 个新页共用**同一份** <style>（同 build-dynasty-shop.py 的取法）。
"""

import importlib.util
import json
import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parents[2]
RAWDIR = ROOT / '11-运营/tmp-shop2/raw'
OUTDIR = ROOT / '11-运营/tmp-shop2/stage3'
BACKUPDIR = ROOT / '11-运营/风险管控/站点改动备份-20261002'


def load_module(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


bds = load_module(ROOT / '11-运营/scripts/build-dynasty-shop.py', 'bds')
ERAS = {e['slug']: e for e in bds.load_eras()}
CSS = bds.load_shared_css()

PAGES = [
    (94, 'sanhuang'), (95, 'xia'), (96, 'shang'), (97, 'zhou'),
    (98, 'qin'), (99, 'han'), (100, 'sanguo'), (101, 'jin'),
    (102, 'sui'), (103, 'tang'), (104, 'wudai'), (105, 'song'),
    (106, 'yuan'), (107, 'ming'), (108, 'qing'), (109, 'juexing'),
]


def block_for(slug):
    e = ERAS[slug]
    return (
        '{css}\n'
        '<div class="sr-collection">\n'
        '<h2>相关藏品</h2>\n'
        '<p class="price">{price}</p>\n'
        '<p><a class="cta" href="/collection/dynasty/{slug}/">{h1} · 壁纸与藏品 →</a></p>\n'
        '<p><a class="cta" href="/collection/dynasty/" '
        'style="background:transparent;border:1px solid #cfc7b8;color:#45423c">'
        '看看十六朝全套 →</a></p>\n'
        '</div>\n'
    ).format(css=CSS, price='预告价：单朝 ¥12 ｜ 商周套装 ¥19 ｜ 首发有折扣',
             slug=slug, h1=e['h1'])


def counts(html):
    return {
        'section': (len(re.findall(r'<section', html)), len(re.findall(r'</section>', html))),
        'div': (len(re.findall(r'<div', html)), len(re.findall(r'</div>', html))),
    }


def h2_index(raw):
    """正文 h2 个数（不含「留个邮箱」那个订阅标题）。"""
    hs = re.findall(r'<h2[^>]*>(.*?)</h2>', raw, re.S)
    return len([h for h in hs if '留个邮箱' not in h])


def main():
    OUTDIR.mkdir(parents=True, exist_ok=True)
    BACKUPDIR.mkdir(parents=True, exist_ok=True)
    report = []
    for pid, slug in PAGES:
        src = json.loads((RAWDIR / 'p{}.json'.format(pid)).read_text(encoding='utf-8'))
        raw = src['content']['raw']
        assert '加相关藏品前' not in raw
        e = ERAS[slug]

        # ① 备份
        bak = BACKUPDIR / 'page-{}-{}-加相关藏品前.raw.html'.format(pid, e['h1'])
        bak.write_text(raw, encoding='utf-8')

        # ② 找锚点：最后一个含 div.era-nav 的 <section>
        nav = raw.rfind('<div class="era-nav">')
        if nav < 0:
            report.append((pid, slug, 'ANCHOR-FAIL', 0, False))
            continue
        anchor = raw.rfind('<section', 0, nav)
        assert anchor > 0, pid

        after = raw[:anchor] + block_for(slug) + '\n' + raw[anchor:]
        c_before, c_after = counts(raw), counts(after)
        balanced = (c_after['section'][0] - c_after['section'][1]
                    == c_before['section'][0] - c_before['section'][1]
                    and c_after['div'][0] - c_after['div'][1]
                    == c_before['div'][0] - c_before['div'][1])

        (OUTDIR / 'p{}.after.html'.format(pid)).write_text(after, encoding='utf-8')
        (OUTDIR / 'p{}.body.json'.format(pid)).write_text(
            json.dumps({'content': after}, ensure_ascii=False), encoding='utf-8')
        (OUTDIR / 'p{}.meta.json'.format(pid)).write_text(
            json.dumps({'id': pid, 'slug': slug, 'h1': e['h1'],
                        'h2_before': h2_index(raw), 'anchor_at': anchor,
                        'backup': str(bak.relative_to(ROOT)),
                        'balanced': balanced}, ensure_ascii=False, indent=1),
            encoding='utf-8')
        report.append((pid, slug, e['h1'], h2_index(raw), balanced))
        print('p{:3d} {:10s} h2={:2d} anchor@{:6d} 配平={} 备份={}'.format(
            pid, slug, h2_index(raw), anchor, balanced, bak.name))

    bad = [r for r in report if r[4] is not True]
    print('\n共 {} 页；配平异常 {} 页'.format(len(report), len(bad)))
    if bad:
        print('⚠️', bad)
        raise SystemExit(1)


if __name__ == '__main__':
    main()
