#!/usr/bin/env python3
"""阶段三复核（修正版）：直接用已拉取的线上 raw（verify/p*.json）核对，
不再发起网络请求。

上一版把 `原文首尾逐字未动` 写错了：正则从**页面第一个** <style>（页面自带的）
开始匹配，等于把整页挖掉，必然不等。本版改为按 `<h2>相关藏品</h2>` 定位插入块。
"""
import json
import pathlib
import re
import sys

ROOT = pathlib.Path('/Users/billyhou/WorkBuddy/2026-09-25-15-56-17')
V = ROOT / '11-运营/tmp-shop2/verify'
S3 = ROOT / '11-运营/tmp-shop2/stage3'
BAK = ROOT / '11-运营/风险管控/站点改动备份-20261002'
PRICE = '预告价：单朝 ¥12 ｜ 周套装'.replace('周套装', '商周套装') + ' ¥19 ｜ 首发有折扣'

DYNASTY = [(94, 'sanhuang'), (95, 'xia'), (96, 'shang'), (97, 'zhou'),
           (98, 'qin'), (99, 'han'), (100, 'sanguo'), (101, 'jin'),
           (102, 'sui'), (103, 'tang'), (104, 'wudai'), (105, 'song'),
           (106, 'yuan'), (107, 'ming'), (108, 'qing'), (109, 'juexing')]


def text_of(h):
    t = re.sub(r'<style.*?</style>', '', h, flags=re.S)
    t = re.sub(r'<script.*?</script>', '', t, flags=re.S)
    return re.sub(r'<[^>]+>', '', t)


def balance(h):
    return {k: (len(re.findall('<' + k, h)), len(re.findall('</' + k + '>', h)))
            for k in ('section', 'div', 'ul', 'li', 'p', 'h2', 'style')}


def main():
    rows, fails = [], []
    for pid, slug in DYNASTY:
        raw = json.loads((V / 'p{}.json'.format(pid)).read_text(encoding='utf-8'))['content']['raw']
        local = (S3 / 'p{}.after.html'.format(pid)).read_text(encoding='utf-8')
        bak = list(BAK.glob('page-{}-*-加相关藏品前.raw.html'.format(pid)))[0].read_text(encoding='utf-8')
        txt = text_of(raw)

        # 精确抠掉插入块：<h2>相关藏品</h2> 之前最近的 <style> 起，到它自己的 </div> 止
        k = raw.find('<h2>相关藏品</h2>')
        s = raw.rfind('<style>', 0, k)
        e = raw.find('</div>', k) + len('</div>')
        restored = raw[:s] + raw[e:]

        st = re.search(r'<style>(.*?)</style>', raw[s:], re.S).group(1)
        blk = raw[k:]
        b_new, b_old = balance(raw), balance(bak)
        checks = {
            '线上内容 == 本地生成文件': raw.strip() == local.strip(),
            '含相关藏品': '<h2>相关藏品</h2>' in raw,
            '价格文案': PRICE in txt,
            '本朝入口': 'href="/collection/dynasty/{}/"'.format(slug) in raw,
            '全套入口': '<a class="cta" href="/collection/dynasty/"' in raw,
            '入口共2条': len(re.findall(r'<a class="cta"', blk)) == 2,
            '样式块无空行': '\n\n' not in st,
            '样式块无 p': '<p>' not in st and '</p>' not in st,
            'HTML注释0': len(re.findall(r'<!--', raw)) == 0,
            '直引号0': '"' not in txt and "'" not in txt,
            '插入块无卖字': '卖' not in text_of(blk),
            '未出现立即购买': '立即购买' not in raw and '面包多' not in raw,
            '原文未动（忽略插入处空白）': re.sub(r'\s+', '', restored) == re.sub(r'\s+', '', bak),
            '标签配平不变': all(v[0] - v[1] == b_old[x][0] - b_old[x][1] for x, v in b_new.items()),
            '原有容器在': all(x in raw for x in ['class="prose"', 'era-nav', 'fineprint', 'class="relic', 'class="cites"', 'class="finale"']),
        }
        bad = [x for x, v in checks.items() if not v]
        rows.append((pid, slug, bad))
        print('{:>4} {:<10} {}'.format(pid, slug, '✅' if not bad else '❌ ' + ','.join(bad)), flush=True)
        if bad:
            fails.append((pid, bad))
            if not checks['原文未动（忽略插入处空白）']:
                print('     restored={} bak={}'.format(len(restored), len(bak)), flush=True)
                for i, (a, b) in enumerate(zip(restored, bak)):
                    if a != b:
                        print('     @{} 新={!r}'.format(i, restored[i - 50:i + 50]), flush=True)
                        print('     @{} 旧={!r}'.format(i, bak[i - 50:i + 50]), flush=True)
                        break
    print('\n阶段三：{} / 16 通过'.format(16 - len(fails)))
    return 1 if fails else 0


if __name__ == '__main__':
    sys.exit(main())
