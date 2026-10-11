#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""印章对比图：原印「七境」vs 新「探赜」（含清理前后 A/B）

用法：
    python3 mk-seal-compare.py 输出.png 标签1=路径1 标签2=路径2 ...
"""
import os
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFont

SEAL_DIR = "/Users/billyhou/WorkBuddy/2026-09-25-15-56-17/02-商品/02-素材/底纹"
FONT = "/System/Library/Fonts/Supplemental/Songti.ttc"

BG = (250, 248, 245)
INK = (26, 26, 24)
MUTED = (110, 104, 96)
RED = (158, 43, 37)

ZOOM_H = 340          # 放大展示高度
REAL_H = 110          # 壁纸角标实际高度


def on_paper(img, pad=10, bg=BG):
    """贴到纸色底上（原印是透明底）"""
    im = img.convert("RGBA")
    W, H = im.width + pad * 2, im.height + pad * 2
    base = Image.new("RGBA", (W, H), bg + (255,))
    base.alpha_composite(im, (pad, pad))
    return base


def fit_h(img, h):
    w = int(round(img.width * h / img.height))
    return img.resize((w, h), Image.LANCZOS)


def main():
    out = sys.argv[1]
    items = []
    for a in sys.argv[2:]:
        tag, path = a.split("=", 1)
        items.append((tag, path))

    zoomed = [fit_h(on_paper(Image.open(p)), ZOOM_H) for _, p in items]
    reals = [fit_h(on_paper(Image.open(p)), REAL_H) for _, p in items]

    gap = 44
    n = len(items)
    colw = [max(zoomed[i].width, reals[i].width) for i in range(n)]
    W = sum(colw) + gap * (n + 1)
    top = 96
    H = top + ZOOM_H + 40 + 30 + REAL_H + 74

    canvas = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(canvas)

    f_title = ImageFont.truetype(FONT, 30, index=0)
    f_sub = ImageFont.truetype(FONT, 17, index=0)
    f_cap = ImageFont.truetype(FONT, 21, index=0)
    f_px = ImageFont.truetype(FONT, 16, index=0)

    d.text((gap, 26), "印章换字：原印「七境」 vs 新「探赜」", font=f_title, fill=RED)
    d.text((gap, 64), "上排＝放大看笔锋与笔道干净度；下排＝缩到壁纸角标实际高度（110px）",
           font=f_sub, fill=MUTED)

    x = gap
    for i, (tag, path) in enumerate(items):
        z, r = zoomed[i], reals[i]
        cx = x + colw[i] // 2
        canvas.paste(z, (cx - z.width // 2, top))
        cy = top + ZOOM_H + 40
        d.text((cx, cy), tag, font=f_cap, fill=INK, anchor="ma")
        cy += 30
        canvas.paste(r, (cx - r.width // 2, cy))
        real = Image.open(path)
        d.text((cx, cy + REAL_H + 12), f"{real.width}×{real.height} px",
               font=f_px, fill=MUTED, anchor="ma")
        x += colw[i] + gap

    canvas.save(out)
    print(out, canvas.size)


if __name__ == "__main__":
    main()
