#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""印章实测图（v5b）：① 笔道极限放大对比  ② 贴回壁纸真实位置

用法：
    python3 mk-seal-zoom.py
"""
import importlib.util
import os

import numpy as np
from PIL import Image, ImageDraw, ImageFont

D = "/Users/billyhou/WorkBuddy/2026-09-25-15-56-17/02-商品/02-素材/底纹"
WP = "/Users/billyhou/WorkBuddy/2026-09-25-15-56-17/02-商品/05-承接站/样张/jin-phone-iphone.png"
FIT_PY = "/Users/billyhou/WorkBuddy/2026-09-25-15-56-17/11-运营/scripts/gen-seal-tanze-fit.py"
FONT = "/System/Library/Fonts/Supplemental/Songti.ttc"
BG = (250, 248, 245)
INK = (26, 26, 24)
MUTED = (110, 104, 96)
RED = (158, 43, 37)

OLD = os.path.join(D, "印章-探赜-v4rawB-竖排.png")      # 旧法（未清理）
NEW = os.path.join(D, "印章-探赜-v5b-竖排.png")         # 新法 v5b（清理后）

_spec = importlib.util.spec_from_file_location("sealfit", FIT_PY)
sealfit = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(sealfit)


def stroke_px(path):
    """内区平均笔画宽（腐蚀法，剔除外圈）"""
    a = np.asarray(Image.open(path).convert("RGBA"))[:, :, 3] < 128
    r = sealfit.RING
    a[:r["t"], :] = a[-r["b"]:, :] = False
    a[:, :r["l"]] = a[:, -r["l"]:] = False
    return sealfit.stroke_w(a)


def zoom_char(img, h, box_frac):
    im = img.convert("RGBA")
    x0, y0, x1, y1 = [int(v * (im.width if i % 2 == 0 else im.height))
                      for i, v in enumerate(box_frac)]
    c = im.crop((x0, y0, x1, y1))
    w = int(round(c.width * h / c.height))
    return c.resize((w, h), Image.NEAREST)


def stroke_zoom():
    old = Image.open(OLD)
    new = Image.open(NEW)
    box = (0.06, 0.48, 0.94, 1.0)          # 下半字「赜」
    Z = 420
    zo, zn = zoom_char(old, Z, box), zoom_char(new, Z, box)

    pad, gap, top = 46, 60, 108
    W = pad * 2 + zo.width + zn.width + gap
    H = top + Z + 96
    cv = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(cv)
    f_t = ImageFont.truetype(FONT, 30, index=0)
    f_s = ImageFont.truetype(FONT, 17, index=0)
    f_c = ImageFont.truetype(FONT, 22, index=0)

    d.text((pad, 26), "笔道极限放大：「赜」字（近邻采样）", font=f_t, fill=RED)
    d.text((pad, 64), "旧法（硬阈值抠图）笔道被细碎白纹啃出红点、边缘毛糙；"
                      "新法 v5b（墨迹清理）笔道饱满、边界利落", font=f_s, fill=MUTED)

    x = pad
    for z, tag, path in ((zo, "旧法（未清理）", OLD), (zn, "新法 v5b（清理后）", NEW)):
        px = Image.open(path)
        cv.paste(z.convert("RGB"), (x, top))
        d.text((x + z.width // 2, top + Z + 16), tag, font=f_c, fill=INK, anchor="ma")
        d.text((x + z.width // 2, top + Z + 50),
               f"笔画 {stroke_px(path):.2f}px · 全印 {px.width}×{px.height}",
               font=f_s, fill=MUTED, anchor="ma")
        x += z.width + gap
    p = os.path.join(D, "印章-探赜-v5b笔道放大.png")
    cv.save(p)
    print(p, cv.size)


def on_wallpaper():
    wp = Image.open(WP).convert("RGBA")
    w, h = wp.size
    old = Image.open(OLD).convert("RGBA")
    new = Image.open(NEW).convert("RGBA")
    sh = 120
    fit = lambda im: im.resize((int(round(im.width * sh / im.height)), sh), Image.LANCZOS)
    o, n = fit(old), fit(new)
    y = int(h * 0.898)
    comp = wp.copy()
    comp.alpha_composite(o, (w // 2 - o.width - 6, y))
    comp.alpha_composite(n, (w // 2 + 6, y))

    crop = comp.crop((0, int(h * 0.855), w, int(h * 0.95)))
    crop = crop.resize((int(crop.width * 1.4), int(crop.height * 1.4)), Image.LANCZOS)

    pad, top = 40, 92
    W = crop.width + pad * 2
    H = top + crop.height + 90
    cv = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(cv)
    f_t = ImageFont.truetype(FONT, 28, index=0)
    f_s = ImageFont.truetype(FONT, 17, index=0)
    d.text((pad, 24), "贴回壁纸底部真实位置（左＝旧法，右＝新法 v5b）", font=f_t, fill=RED)
    d.text((pad, 60), "实际使用尺寸（印高 120px）下，白字边缘毛刺与笔道红点是否可见",
           font=f_s, fill=MUTED)
    cv.paste(crop.convert("RGB"), (pad, top))
    p = os.path.join(D, "印章-探赜-v5b壁纸实测.png")
    cv.save(p)
    print(p, cv.size)


if __name__ == "__main__":
    stroke_zoom()
    on_wallpaper()
