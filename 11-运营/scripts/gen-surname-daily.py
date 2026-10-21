#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""姓氏日更 25 天 · 文案批量生成

数据源（只读，不改）：
  百家姓-交叉验证.json                     → 四个字、繁体、拼音、源流朝代/年份
  research/姓氏代表人物名单-首批100-2026-10-03.md → 每姓一位代表人物 + 一句话（正史有载）

产出：
  04-市场/03-推广获客/姓氏日更-202610/D{nn}-{四字}.md   × 25 篇

设计取舍：
  · 标题不写「第 N 天」——小红书标题里序号不带流量，改成「{四字}｜{首姓人}到{末姓人}，四种写法」
  · 正文每姓两行（姓名 / 一句话），不用长句，手机上一屏能扫完
  · 钩子固定三条：要原图→后台 dd「壁纸」；没看到自己的姓→报一个字；想要桌面版→在售
  · 标签固定 6 个大话题 + 4 个当篇姓氏「X氏」（姓氏圈子的实际搜索词是「X氏」不是「X」）
"""
import json
import pathlib
import re

ROOT = pathlib.Path('/Users/billyhou/WorkBuddy/2026-09-25-15-56-17')
OUT = ROOT / '04-市场/03-推广获客/姓氏日更-202610'
BODY = ROOT / '百家姓-交叉验证.json'
PEOPLE = ROOT / 'research/姓氏代表人物名单-首批100-2026-10-03.md'

BIG_TAGS = ['#百家姓', '#汉字之美', '#书法', '#手机壁纸', '#壁纸', '#东方美学']


def load_people():
    rows = {}
    for line in PEOPLE.read_text(encoding='utf-8').splitlines():
        if not line.startswith('|'):
            continue
        cells = [c.strip() for c in line.strip().strip('|').split('|')]
        if len(cells) < 7 or not cells[0].isdigit():
            continue
        rows[cells[1]] = {'star': cells[3].replace('**', '').strip(),
                          'era': cells[4], 'desc': cells[5]}
    return rows


def main():
    d = json.loads(BODY.read_text(encoding='utf-8'))
    seq = d['sequence'][:100]
    ppl = load_people()
    assert len(seq) == 100, f'前 100 姓取到 {len(seq)} 条'

    char2zip = {}
    for item in seq:
        import json as _j
        zip_ = d.get('pinyin_map', {}).get(item['simplified'], '')
        char2zip[item['simplified']] = zip_

    OUT.mkdir(parents=True, exist_ok=True)
    missing = []
    for day in range(25):
        four = seq[day * 4:day * 4 + 4]
        chars = [x['simplified'] for x in four]
        quad = ''.join(chars)
        stars = []
        for c in chars:
            p = ppl.get(c)
            if not p:
                missing.append(c)
                stars.append(None)
            else:
                stars.append(p)
        head = stars[0]['star'] if stars[0] else chars[0]
        tail = stars[-1]['star'] if stars[-1] else chars[-1]
        title = f'{quad}｜{head}到{tail}，四种写法'

        lines = [f'# D{day + 1:02d} · {quad}', '',
                 f'**标题**：{title}（{len(title)} 字）', '',
                 '**配图**（按句序 1→4，目录 `02-商品/06-姓氏线/成品-手机竖版/小红书-3x4/`）：'
                 + '、'.join(f'`{c}-1179x1572.png`' for c in chars), '',
                 '---', '',
                 '**正文**（直接粘贴）', '', '```']
        lines += [f'【第 {day + 1} 天 · {quad}】', '']
        for c, p in zip(chars, stars):
            if p:
                lines += [f'{c} · {p["star"]}', p['desc'], '']
            else:
                lines += [f'{c}', '（待补代表人物）', '']
        lines += [
            '—— 一个字，从碑刻到草书，走了三千年。',
            f'这四张是「{quad}」的四种写法，手机壁纸，原图我备好了。',
            '',
            '要原图：后台 dd 我「壁纸」，告诉你怎么领。',
            '【朝代 16 朝 + 百家姓 100 姓】两套，都在里面。',
            '没看到自己的姓？评论区报一个字，我做给你，做完私信你。',
            '',
            ' '.join(BIG_TAGS) + ' ' + ' '.join(f'#{c}氏' for c in chars),
            '```', '',
            '---', '',
            '**备注**：' + '；'.join(
                f'{c}={p["star"]}（{p["era"]}）' if p else f'{c}=缺' for c, p in zip(chars, stars)),
        ]
        (OUT / f'D{day + 1:02d}-{quad}.md').write_text('\n'.join(lines) + '\n', encoding='utf-8')

    print(f'生成 25 篇 → {OUT}')
    if missing:
        print('⚠️ 缺代表人物：', '、'.join(sorted(set(missing))))
    else:
        print('✓ 100 姓全部对上代表人物名单')


if __name__ == '__main__':
    main()
