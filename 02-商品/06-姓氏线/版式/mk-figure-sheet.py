#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""姓氏线 · 人物底纹版式对比图（多版并排）

用法：
  python3 mk-figure-sheet.py --out 试版/_人物底纹-五版对比.png \
      "原版（远山+幽灵字）=/path/a.png" "人物左下=/path/b.png" ...
"""
import argparse
import pathlib

from PIL import Image, ImageDraw, ImageFont

SONG = '/System/Library/Fonts/Supplemental/Songti.ttc'
MUTED = (140, 133, 120)
INK = (26, 26, 24)
BG = (247, 245, 240)
LINE = (206, 200, 189)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', required=True)
    ap.add_argument('items', nargs='+', help='标签=图片路径')
    ap.add_argument('--cols', type=int, default=2)
    ap.add_argument('--tile-w', type=int, default=640)
    a = ap.parse_args()

    items = []
    for it in a.items:
        label, _, path = it.rpartition('=')
        im = Image.open(path).convert('RGB')
        w = a.tile_w
        h = round(im.height * w / im.width)
        items.append((label, im.resize((w, h), Image.LANCZOS)))

    tw, th = a.tile_w, items[0][1].height
    cols = a.cols
    rows = (len(items) + cols - 1) // cols
    pad, gap, cap = 26, 22, 38
    W = cols * tw + (cols - 1) * gap + pad * 2
    H = rows * (th + cap) + (rows - 1) * gap + pad * 2
    out = Image.new('RGB', (W, H), BG)
    d = ImageDraw.Draw(out)
    f = ImageFont.truetype(SONG, 26)
    fs = ImageFont.truetype(SONG, 17)

    for i, (label, im) in enumerate(items):
        r, c = divmod(i, cols)
        x = pad + c * (tw + gap)
        y = pad + r * (th + cap + gap)
        d.text((x, y + 4), label, font=f, fill=INK)
        d.rectangle([x, y + cap - 4, x + tw - 1, y + cap + th - 5], outline=LINE)
        out.paste(im, (x, y + cap))
        # 右下角标注尺寸
        d.text((x + tw - 4, y + cap + th - 22), f'{im.width}×{im.height}',
               font=fs, fill=MUTED, anchor='ra')

    p = pathlib.Path(a.out)
    p.parent.mkdir(parents=True, exist_ok=True)
    out.save(p)
    print(f'{p}  {out.size[0]}×{out.size[1]}')


if __name__ == '__main__':
    main()
