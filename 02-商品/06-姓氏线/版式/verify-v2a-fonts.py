#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""姓氏线 v2A · 截图成品「字体真伪」核验

不看 HTML 声明，直接量**最终 PNG**：把四体大字逐个切出来，与「用目标字体本地渲染的
同一字」做形状比对（IoU）。IoU 高 = Chrome 真的用了目标字体；IoU 低 = 被回退掉了。

用法：python3 verify-v2a-fonts.py 001 002 003 004
"""
import pathlib
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFont

ROOT = pathlib.Path('/Users/billyhou/WorkBuddy/2026-09-25-15-56-17')
OUT = ROOT / '02-商品/06-姓氏线/成品-桌面-v2A'
F = ROOT / '02-商品/02-素材/字体'
FONTS = {
    'serif': F / 'fonts/NotoSerifSC-Black.ttf',
    'lishu': F / '隶书/aoyagireisyosimo_ttf_2_01.ttf',
    'xing':  F / 'fonts/挚芒行.ttf',
    'cao':   F / 'fonts/柳建毛草.ttf',
    'lishu2': F / '隶书/AlimamaDaoLiTi-Regular-简体.ttf',   # 决策 B 备用隶书
}
ORDER4 = ('serif', 'lishu', 'xing', 'cao')
BAND = (300, 640)      # 四体大字的纵向区间（避开下方标签）
XLO, XHI = 150, 1700   # 右侧竖排《百家姓》引文要排除在扫描区外
FS = 232               # 与 CSS .cell .ch font-size 一致


def ink_mask(arr):
    return arr < 128


def cells_from_png(im):
    """在色带里按列投影切出 4 个字的包围盒。"""
    band = np.asarray(im.convert('L').crop((XLO, BAND[0], XHI, BAND[1])))
    col = ink_mask(band).sum(axis=0)
    groups, run = [], None
    for x, v in enumerate(col):
        if v > 0 and run is None:
            run = x
        elif v == 0 and run is not None:
            if x - run > 6:
                groups.append((run, x))
            run = None
    if run is not None:
        groups.append((run, len(col)))
    # 合并间隙 < 60px 的碎块：草书常有断笔（彭/于 的草书会裂成两段，间隙 ~20px）。
    # 四格之间的真实间隙是 104px（flex gap），故 60px 阈值绝不会把两格并成一块。
    merged = []
    for g in groups:
        if merged and g[0] - merged[-1][1] < 60:
            merged[-1] = (merged[-1][0], g[1])
        else:
            merged.append(list(g))
    # 掉碎屑（<80px 宽）：右侧竖排引文、朱砂点等
    big = [g for g in merged if g[1] - g[0] >= 80]
    if len(big) > 4:
        top = sorted(big, key=lambda g: g[1] - g[0], reverse=True)[:4]
        big = sorted(top, key=lambda g: g[0])
    elif len(big) < 4:
        # 仍不足 4 块：反复把「最近的两块」并起来，直到剩 4 块（绝不退化成等分）
        big = [list(g) for g in merged]
        while len(big) > 4:
            i = min(range(len(big) - 1), key=lambda j: big[j + 1][0] - big[j][1])
            big[i:i + 2] = [[big[i][0], big[i + 1][1]]]
        if len(big) != 4:           # 真兜底：等宽四等分
            big = [[int((im.width - 2 * XLO) * (i + .5) / 4 - 120),
                    int((im.width - 2 * XLO) * (i + .5) / 4 + 120)] for i in range(4)]
    out = []
    for x0, x1 in big:
        sub = band[:, max(0, x0 - 8):min(band.shape[1], x1 + 8)]
        rows = ink_mask(sub).sum(axis=1)
        ys = np.nonzero(rows)[0]
        y0, y1 = (ys[0], ys[-1]) if len(ys) else (0, sub.shape[0])
        out.append((XLO + max(0, x0 - 8), BAND[0] + int(y0),
                    XLO + min(band.shape[1], x1 + 8), BAND[0] + int(y1) + 1))
    return out


def norm(mask, size=200):
    ys, xs = np.nonzero(mask)
    if len(xs) == 0:
        return np.zeros((size, size), bool)
    m = mask[ys.min():ys.max() + 1, xs.min():xs.max() + 1]
    im = Image.fromarray((m * 255).astype(np.uint8))
    im = im.resize((size, size), Image.BILINEAR)
    return np.asarray(im) > 127


def pil_mask(key, ch):
    im = Image.new('L', (700, 700), 0)
    ImageDraw.Draw(im).text((60, 60), ch, font=ImageFont.truetype(str(FONTS[key]), FS), fill=255)
    return np.asarray(im) > 127


def iou(a, b):
    return (a & b).sum() / max(1, (a | b).sum())


def main():
    sys.path.insert(0, str(pathlib.Path(__file__).parent))
    import importlib
    G = importlib.import_module('gen-surname-v2a'.replace('-', '_')) if False else None
    # 直接 import（文件名带 - 时用 loader）
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        'genv2a', pathlib.Path(__file__).parent / 'gen-surname-v2a.py')
    G = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(G)
    d, seq = G.load()

    want = sys.argv[1:] or ['001', '002', '003', '004']
    rows = []
    for w in want:
        item = next((s for s in seq if f"{s['order']:03d}" == w), None)
        if item is None:
            print(f'  ✗ 数据里没有第 {w} 位')
            continue
        pngs = [p for p in sorted(OUT.glob(f'surname-{w}-*.png')) if '-4k' not in p.name]
        if not pngs:
            print(f'  ✗ 找不到 surname-{w}-*.png')
            continue
        _html, _rec, cover, _notes, _cf = G.build(d, seq, item)
        expect = {k: (item['simplified'] if cover[k] == 'ok' else
                      (item['traditional'] if cover[k] == 'trad' else item['simplified']))
                  for k in ORDER4}
        im = Image.open(pngs[0])
        boxes = cells_from_png(im)
        for k, box in zip(ORDER4, boxes):
            crop = norm(np.asarray(im.convert('L').crop(box)) < 128)
            v = iou(crop, norm(pil_mask(k, expect[k])))
            # 对照：同一格换成「另一种简体字形」的 IoU，用于判断是不是被系统字体回退
            alt = 'PingFang SC'
            rows.append((w, expect[k], k, v, cover[k]))
    print(f"{'序号':<5}{'字':<4}{'书体槽':<8}{'覆盖判定':<10}{'与目标字体IoU'}")
    print('-' * 52)
    for w, ch, k, v, cov in rows:
        mark = '✓ 真用了目标字体' if v >= .82 else ('△ 疑似回退' if v >= .6 else '✗ 明显不是目标字体')
        print(f'{w:<5}{ch:<4}{k:<10}{cov:<12}{v:.3f}  {mark}')
    bad = [r for r in rows if r[3] < .82]
    print()
    print(f'共核验 {len(rows)} 格，其中 {len(bad)} 格 IoU < 0.82')


if __name__ == '__main__':
    main()
