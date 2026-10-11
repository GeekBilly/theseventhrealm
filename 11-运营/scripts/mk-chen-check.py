#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""「臣」字核验图：宋体基准 vs 各版左偏旁放大"""
import os

from PIL import Image, ImageDraw, ImageFont

D = "/Users/billyhou/WorkBuddy/2026-09-25-15-56-17/02-商品/02-素材/底纹"
FONT = "/System/Library/Fonts/Supplemental/Songti.ttc"
BG = (250, 248, 245)
INK = (26, 26, 24)
MUTED = (110, 104, 96)
RED = (158, 43, 37)

H = 460


def paste_on_paper(im, pad=14):
    im = im.convert("RGBA")
    base = Image.new("RGBA", (im.width + pad * 2, im.height + pad * 2), BG + (255,))
    base.alpha_composite(im, (pad, pad))
    return base


def scale_h(im, h=H):
    return im.resize((max(1, int(round(im.width * h / im.height))), h), Image.LANCZOS)


# 1) 宋体「臣」基准
ref = Image.new("RGB", (520, 620), "white")
d = ImageDraw.Draw(ref)
f = ImageFont.truetype(FONT, 500, index=0)
bb = d.textbbox((0, 0), "臣", font=f)
d.text((260 - (bb[2] - bb[0]) // 2 - bb[0], 310 - (bb[3] - bb[1]) // 2 - bb[1]),
       "臣", font=f, fill=(8, 8, 8))
items = [("宋体「臣」基准", scale_h(paste_on_paper(ref)))]

# 2) 锁定C 稿里的左偏旁
g = Image.open(os.path.join(D, "探赜书法-锁定C-行楷大字.png")).convert("RGB")
items.append(("毛笔稿（锁定C）左偏旁",
              scale_h(paste_on_paper(g.crop((258, 750, 530, 1405))))))

# 3) v6 合成印章（放大版，看结构）
v = Image.open(os.path.join(D, "印章-探赜-v6big-竖排.png"))
items.append(("合成印章 v6 左偏旁",
              scale_h(paste_on_paper(v.crop((14, 222, 126, 482))))))

# 4) 直出A 印章里的左偏旁
z = Image.open(os.path.join(D, "印章-探赜-直出A-竖排.png"))
items.append(("直出印章 左偏旁",
              scale_h(paste_on_paper(z.crop((4, 90, 64, 192))))))

PAD, GAP, TOP = 46, 50, 116
W = PAD * 2 + sum(i[1].width for i in items) + GAP * (len(items) - 1)
Hc = TOP + H + 92
cv = Image.new("RGB", (W, Hc), BG)
dd = ImageDraw.Draw(cv)
f_t = ImageFont.truetype(FONT, 30, index=0)
f_s = ImageFont.truetype(FONT, 17, index=0)
f_c = ImageFont.truetype(FONT, 21, index=0)

dd.text((PAD, 26), "「臣」字核验：左偏旁到底写作臣还是目", font=f_t, fill=RED)
dd.text((PAD, 64), "臣＝右侧竖画断成上下两段、底横向左伸出框外；目＝右侧竖画一根通到底、四周封口",
        font=f_s, fill=MUTED)

x = PAD
for tag, im in items:
    cv.paste(im.convert("RGB"), (x, TOP))
    dd.text((x + im.width // 2, TOP + H + 18), tag, font=f_c, fill=INK, anchor="ma")
    x += im.width + GAP

p = os.path.join(D, "印章-探赜-臣字核验.png")
cv.save(p)
print(p, cv.size)
