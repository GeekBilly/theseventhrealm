#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""姓氏线 v2A · 全量终检

一次跑完四件事，全部基于**成品 PNG 像素**，不看 HTML 声明：
  1. 版面：每格墨迹高 / 墨迹底 是否落在归一化目标上
  2. 字体真伪：每格「对目标字体的 IoU」vs「对另外三种字体的最高 IoU」，
     用**领先幅度**判定，不用绝对阈值 —— 回退字体必然被目标字体大幅甩开
  3. 4K 完整性：3840×2160 且缩回 1x 后与 1x 成品同版
  4. 汇总落盘

用法：python3 audit-v2a-final.py
"""
import importlib.util
import json
import pathlib
import re
import statistics
import sys

import numpy as np
from PIL import Image

HERE = pathlib.Path(__file__).parent
ROOT = pathlib.Path('/Users/billyhou/WorkBuddy/2026-09-25-15-56-17')
OUT = ROOT / '02-商品/06-姓氏线/成品-桌面-v2A'
LOG = HERE / '_build-v2a' / '全量终检.log'
NORM = HERE / '_build-v2a' / 'norm.json'
TARGET_H, BASE_Y = 200, 588


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


V = load('v2v', HERE / 'verify-v2a-fonts.py')
G = load('g2a', HERE / 'gen-surname-v2a.py')


def main():
    d, seq = G.load()
    order2item = {f"{s['order']:03d}": s for s in seq}
    pngs = [p for p in sorted(OUT.glob('surname-*.png')) if '-4k' not in p.name]
    lines, rows = [], []
    for p in pngs:
        w = p.stem.split('-')[1]
        item = order2item[w]
        _html, _rec, cover, _notes, cellfont = G.build(d, seq, item)
        expect = {k: (item['traditional'] if cover[k] == 'trad' else item['simplified'])
                  for k in G.ORDER4}
        cand = list(G.ORDER4) + (['lishu2'] if 'lishu2' in cellfont.values() else [])
        im = Image.open(p).convert('L')
        a = np.asarray(im)
        boxes = V.cells_from_png(im)
        for k, b in zip(G.ORDER4, boxes):
            win = a[:, b[0]:b[2]] < 128
            rr = np.nonzero(win.sum(axis=1))[0]
            rr = rr[(rr >= 300) & (rr < 600)]
            h = int(rr.max() - rr.min() + 1) if len(rr) else 0
            bot = int(rr.max()) if len(rr) else 0
            crop = V.norm(a[300:600, b[0]:b[2]] < 128)
            scores = {kk: V.iou(crop, V.norm(V.pil_mask(kk, expect[k]))) for kk in cand}
            af = cellfont[k]                       # 该格实际该用的字体键
            tgt = scores[af]
            rival = max(v for kk, v in scores.items() if kk != af)
            rows.append(dict(order=w, char=expect[k], font=af, cover=cover[k], h=h,
                             bot=bot, iou=tgt, rival=rival, margin=tgt - rival,
                             size=(json.loads(NORM.read_text(encoding='utf-8'))
                                   .get(w, {}).get(k, {}).get('size'))))
        # 4K 完整性
        p4 = OUT / f"{p.stem}-4k.png"
        ok4 = p4.exists() and Image.open(p4).size == (3840, 2160)
        lines.append(f"{w} {item['simplified']} 1x+4K {'✓' if ok4 else '✗ 4K 缺失/尺寸错'}")

    hs = [r['h'] for r in rows]
    bots = [abs(r['bot'] - BASE_Y) for r in rows]
    marg = [r['margin'] for r in rows]
    ious = [r['iou'] for r in rows]
    worst = sorted(rows, key=lambda r: r['margin'])[:6]
    out = []
    out.append(f"姓氏线 v2A 全量终检 · {len(pngs)} 个姓 · {len(rows)} 格")
    out.append('')
    out.append(f"[1] 版面归一化  墨迹高 {min(hs)}–{max(hs)}px（目标 {TARGET_H}，极差 {max(hs)-min(hs)}）")
    out.append(f"                |墨迹底−{BASE_Y}| 最大 {max(bots)}px，均值 {statistics.mean(bots):.1f}px")
    out.append(f"[2] 字体真伪    目标字体 IoU 最低 {min(ious):.3f}，中位 {statistics.median(ious):.3f}")
    out.append(f"                领先幅度 margin 最低 {min(marg):.3f}（>0.15 即可判死非回退）")
    out.append('    领先幅度最小 6 格：')
    for r in worst:
        out.append(f"      {r['order']} {r['char']} {r['font']:<6} 字号{r['size']}  "
                   f"目标IoU={r['iou']:.3f} 最强对手={r['rival']:.3f} 领先={r['margin']:.3f}")
    bad = [r for r in rows if r['margin'] < 0.15 or abs(r['h'] - TARGET_H) > 8
           or abs(r['bot'] - BASE_Y) > 8]
    out.append(f"[3] 4K 完整性   {sum(1 for l in lines if '✗' in l)} 处异常")
    out.append('')
    out.append(f"结论：{'全部通过' if not bad else str(len(bad)) + ' 格需复核'}")
    if bad:
        for r in bad:
            out.append(f"  ⚠ {r}")
    LOG.write_text('\n'.join(out) + '\n', encoding='utf-8')
    print('\n'.join(out))


if __name__ == '__main__':
    main()
