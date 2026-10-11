#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""底纹墨深量测（风格对齐唯一判据，零积分）

为什么一定要在**成品**上量，而不是在素材上量（2026-10-04 踩坑）：
  素材 950×1360 贴进成品后被缩到 height=1000（×0.735），LANCZOS 重采样会把
  极淡的雾平均掉 → 同一个素材，素材域量得 覆盖 34.8%/中位 .065，
  成品域只有 10.6%/.078。**两者差 3 倍，口径必须固定在成品域。**

量什么：
  底纹框内的墨深 d = (255 − 灰度)/255
    · 覆盖率 = d > (255−250)/255 的像素占比（"有没有墨"）
    · 中位 / p90 / IQR / 最浓 = 只统计有墨像素（"浓淡节奏"）

用法：
  python3 measure-figure-ink.py 成品.png                  # 自动算框（需 --fig 素材）
  python3 measure-figure-ink.py 成品.png --fig 素材.png --height 1000
  python3 measure-figure-ink.py a.png b.png --box 1221,80,1920,1080
  python3 measure-figure-ink.py 成品.png --ink-only       # 顺手量左大字区是否被动过
"""
import argparse
import pathlib
import sys

import numpy as np
from PIL import Image

TH = (255 - 250) / 255          # 覆盖率阈值（成品灰度 < 250）


def box_auto(canvas_w, canvas_h, fig_wh, height):
    """.figure 是 right:0;bottom:0;height:H → 宽 = 素材宽/素材高 × H"""
    fw, fh = fig_wh
    w = round(fw / fh * height)
    return (int(max(0, canvas_w - w)), int(max(0, canvas_h - height)), canvas_w, canvas_h)


def to_gray(png):
    """⚠️ Chrome 截出来的是 RGBA，透明区直接 convert('L') 会变成**纯黑**（灰度 0），
    量出来"最浓 1.000"全是假的。必须先合成到白底。"""
    im = Image.open(png)
    if im.mode in ('RGBA', 'LA') or (im.mode == 'P' and 'transparency' in im.info):
        im = im.convert('RGBA')
        bg = Image.new('RGBA', im.size, (255, 255, 255, 255))
        im = Image.alpha_composite(bg, im).convert('RGB')
    return np.asarray(im.convert('L')).astype(np.float32)


def stat(png, box):
    g = to_gray(png)
    x0, y0, x1, y1 = box
    s = (255.0 - g[y0:y1, x0:x1]) / 255.0
    cov = 100 * (s > TH).mean()
    v = s[s > TH]
    if v.size == 0:
        return cov, 0, 0, 0, 0
    q1, q3 = np.percentile(v, [25, 75])
    return cov, float(np.median(v)), float(np.percentile(v, 90)), float(q3 - q1), float(v.max())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('pngs', nargs='+', type=pathlib.Path)
    ap.add_argument('--box', help='x0,y0,x1,y1；不传则按 --fig/--height 自动算')
    ap.add_argument('--fig', type=pathlib.Path, help='底纹素材（自动算框时必填）')
    ap.add_argument('--height', type=float, default=1000.0,
                    help='模板 .figure 的 CSS height，1000(std 1080 档)/1156(Mac 2496 档)')
    ap.add_argument('--ink-only', action='store_true',
                    help='额外量左大字区 x<900（应与无底纹校样一致，变了说明底纹跑左边去了）')
    a = ap.parse_args()

    print('%-42s %6s %7s %7s %7s %7s' % ('成品', '覆盖%', '中位', 'p90', 'IQR', '最浓'))
    for p in a.pngs:
        im = Image.open(p)
        if a.box:
            box = tuple(int(x) for x in a.box.replace('，', ',').split(','))
        elif a.fig:
            fw, fh = Image.open(a.fig).size
            box = box_auto(im.size[0], im.size[1], (fw, fh), a.height)
        else:
            sys.exit('需要 --box 或 --fig（自动算框）')
        cov, med, p90, iqr, mx = stat(p, box)
        print('%-42s %6.1f %7.3f %7.3f %7.3f %7.3f  box=%s' %
              ('%s/%s' % (p.parent.name, p.name), cov, med, p90, iqr, mx, box))
        if a.ink_only:
            g = to_gray(p)
            print('%44s左大字区(x<900) 覆盖 %.3f%%' % ('', 100 * ((255 - g[:, :900]) / 255 > TH).mean()))


if __name__ == '__main__':
    main()
