#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""素材域「成品效果」秒级预览 —— 调底纹参数时不必渲成品。

原理：成品里底纹的显示 = 素材缩到「高度 = .figure 的 height」后，乘模板 opacity，
      与白纸底合成。本脚本按同一算式在素材域重现，秒出、零积分、不占 Chrome。

用法：
    python preview-figure.py 试版/an-E简洁/*.png 试版/an-F极简/*.png -o 试版/对比.png
    python preview-figure.py /*.png --height 1000 --opacity .32 --cols 4

⚠️ 它**只是预览**：真验收仍要渲成品（缩放插值、DOM 合成顺序都会略有差异）。
"""
import argparse
import pathlib

import numpy as np
from PIL import Image, ImageDraw, ImageFont

OPACITY = 0.32        # 必须与模板 .figure{opacity} 一致
INK = (255.0 - 26.0) / 255.0


def font(sz):
    for p in ['/System/Library/Fonts/PingFang.ttc',
              '/System/Library/Fonts/STHeiti Medium.ttc',
              '/Library/Fonts/Arial Unicode.ttf']:
        if pathlib.Path(p).exists():
            try:
                return ImageFont.truetype(p, sz)
            except Exception:
                pass
    return ImageFont.load_default()


def render(path, height, opacity):
    """素材 → 成品中底纹的显示效果（RGB 图）。"""
    im = Image.open(path).convert('RGBA')
    w = max(1, int(round(im.size[0] * height / im.size[1])))
    im = im.resize((w, height), Image.LANCZOS)
    a = np.asarray(im).astype(np.float32)
    alpha = a[..., 3] / 255.0 * opacity
    ink = np.asarray(im)[..., :3].astype(np.float32).mean(axis=2)
    # 纸白 255 上，以 alpha 强度压上墨色
    g = 255.0 * (1 - alpha) + ink * alpha
    return Image.fromarray(np.clip(g, 0, 255).astype(np.uint8)).convert('RGB')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('figs', nargs='+')
    ap.add_argument('-o', '--out', default='试版/_preview.png')
    ap.add_argument('--height', type=int, default=1000, help='.figure 的 height（1080 档=1000）')
    ap.add_argument('--opacity', type=float, default=OPACITY)
    ap.add_argument('--cols', type=int, default=4)
    ap.add_argument('--max-w', type=int, default=340, help='每格最大宽（预览尺度）')
    a = ap.parse_args()

    # 标签用「目录名」（试版一档一个目录，目录名才区分得开）；同名文件不在目录里时退回文件名
    def label(p):
        q = pathlib.Path(p)
        return q.parent.name if q.parent.name not in ('', '.') else q.stem
    tiles = [(label(p), render(p, a.height, a.opacity)) for p in a.figs]
    scale = min(a.max_w / max(t.size[0] for _, t in tiles), 1.0)
    tw = int(tiles[0][1].size[0] * scale)
    th = int(tiles[0][1].size[1] * scale)
    cols = min(a.cols, len(tiles))
    rows = (len(tiles) + cols - 1) // cols
    pad, top = 18, 40
    W = cols * tw + (cols + 1) * pad
    H = top + rows * (th + top) + pad
    cv = Image.new('RGB', (W, H), (236, 234, 229))
    d = ImageDraw.Draw(cv)
    f = font(19)
    d.text((pad, 10), '底纹「成品显示效果」预览（素材域模拟：高度 %d × opacity %.2f）'
           % (a.height, a.opacity), fill=(40, 38, 34), font=f)
    for i, (name, t) in enumerate(tiles):
        r, c = divmod(i, cols)
        x = pad + c * (tw + pad)
        y = top + r * (th + top)
        cv.paste(t.resize((tw, th), Image.LANCZOS), (x, y))
        d.rectangle([x, y, x + tw, y + th], outline=(168, 163, 153), width=1)
        d.text((x, y - 26), name, fill=(40, 38, 34), font=f)
    out = pathlib.Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    cv.save(out)
    print('已生成', out, cv.size, '（%d 格）' % len(tiles))


if __name__ == '__main__':
    main()
